"""UI tests for plural forms (REQ-L10N-UI-006).

A count-bearing message goes through Qt's numerus mechanism, so the form shown
is chosen by the active language's own plural rule and not by a hand-written
singular/plural branch. What is covered, by scenario id:

* **SC-L10N-UI-006-1** with Russian active, a count-bearing message shown for
  1, 3, 5, 11, 21, 22 and 25 uses the forms one, few, many, many, one, few and
  many.
* **SC-L10N-UI-006-2** with French active, the same message shown for 0, 1 and 2
  uses the forms singular, singular and plural.
* **SC-L10N-UI-006-3** with each of ``zh_CN``, ``ko`` and ``ja`` active in turn,
  the message shown for 1 and for 5 uses the same form (they have only one).

How a form is told. The forms of every count-bearing message are read from the
language's ``.ts`` source with ElementTree, never through the product. The text
Qt shows for a count (``QCoreApplication.translate`` with the count, which is
what ``tr(..., n)`` calls) is compared with the form this module expects for that
count, with ``%n`` replaced by the count. The expected form per count is written
in this module from the scenarios; nothing is computed from the product's own
rules. A message whose forms are all different can tell one form from another;
the number of such messages is printed per language, and a language with none
fails, because a verdict that cannot tell the forms apart proves nothing. A
message that is not finished, or whose source or forms carry ``&`` or ``%L``
(mnemonics and localised numbers, which other tests own), is left out, and the
number left out is printed.

Instruments and their controls. A check that reports "nothing wrong" is worth
something only if it would have reported a failure, so each one is shown failing:

* English active, judged against the Russian forms (every count is reported);
* a Russian catalogue that is really the French one, so the wrong plural rule and
  the wrong words are both in place (every count is reported);
* the English rule (one form for 1, another for everything else) judged against
  Russian and French, and a form that changes with the count judged against a
  one-form language (only the counts the wrong rule gets wrong are reported);
* a verdict over no messages (it fails, with the reason);
* the catalogue reader over a directory that holds no catalogue (it fails naming
  the path).

``PIXELART_PLURALS_CATALOGUE_DIR`` names a directory of compiled ``.qm`` files
to measure instead of the shipped ones. It exists to show these tests fail
against a defective set of compiled catalogues; unset, the shipped ones are
measured. The ``.ts`` forms are always read from the shipped directory.

No test leaves the process changed: every manager is put back to English, and a
guard reads the default locale and an English word after every test.
"""

from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QLocale

import pixelart_creator
from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, LanguageManager

#: Where the shipped catalogues (``.ts`` source and compiled ``.qm``) live.
SHIPPED_DIR = Path(pixelart_creator.__file__).resolve().parent / "i18n"

#: Names a directory of compiled catalogues to measure instead of the shipped ones.
CATALOGUE_DIR_ENV = "PIXELART_PLURALS_CATALOGUE_DIR"

#: The characters that put a message outside what this module judges.
UNJUDGED_MARKERS = ("&", "%L")


@dataclass(frozen=True)
class Expectation:
    """What one language's plural rule must do, written from the scenarios."""

    language: str
    form_names: tuple[str, ...]
    form_for_count: Mapping[int, int]

    @property
    def counts(self) -> tuple[int, ...]:
        """Return the counts the scenario shows, in its order."""
        return tuple(self.form_for_count)


EXPECTATIONS = {
    "ru": Expectation(
        "ru",
        ("one", "few", "many"),
        {1: 0, 3: 1, 5: 2, 11: 2, 21: 0, 22: 1, 25: 2},
    ),
    "fr": Expectation("fr", ("singular", "plural"), {0: 0, 1: 0, 2: 1}),
    "zh_CN": Expectation("zh_CN", ("only",), {1: 0, 5: 0}),
    "ko": Expectation("ko", ("only",), {1: 0, 5: 0}),
    "ja": Expectation("ja", ("only",), {1: 0, 5: 0}),
}

#: The scenarios' own wording of the forms for each language's counts.
RUSSIAN_SCENARIO_FORMS = ["one", "few", "many", "many", "one", "few", "many"]
FRENCH_SCENARIO_FORMS = ["singular", "singular", "plural"]

ONE_FORM_LANGUAGES = ("zh_CN", "ko", "ja")


@dataclass(frozen=True)
class CountMessage:
    """One count-bearing message and its forms, read from a ``.ts`` file."""

    context: str
    source: str
    disambiguation: str | None
    forms: tuple[str, ...]

    @property
    def key(self) -> str:
        """Return a printable name for the message."""
        return f"{self.context}: {self.source}"

    @property
    def forms_differ(self) -> bool:
        """Return whether every form is a different text."""
        return len(set(self.forms)) == len(self.forms)


@dataclass(frozen=True)
class Catalogue:
    """The count-bearing messages one ``.ts`` file offers for judging."""

    total: int
    messages: tuple[CountMessage, ...]


Translate = Callable[[CountMessage, int], str]


def read_count_messages(code: str, directory: Path = SHIPPED_DIR) -> Catalogue:
    """Return the finished count-bearing messages of ``pixelart_<code>.ts``.

    Fails with the path named when the file is absent, so a gap is the result and
    never a silent zero.
    """
    path = directory / f"pixelart_{code}.ts"
    assert path.is_file(), f"no catalogue source for {code!r} at {str(path)!r}"
    root = ElementTree.parse(path).getroot()
    total = 0
    kept: list[CountMessage] = []
    for context in root.findall("context"):
        name = context.findtext("name") or ""
        for message in context.findall("message"):
            if message.get("numerus") != "yes":
                continue
            total += 1
            translation = message.find("translation")
            if translation is None or translation.get("type") is not None:
                continue
            forms = tuple(
                form.text or "" for form in translation.findall("numerusform")
            )
            source = message.findtext("source") or ""
            if not forms or any(not form for form in forms):
                continue
            texts = (source, *forms)
            if any(marker in text for text in texts for marker in UNJUDGED_MARKERS):
                continue
            kept.append(
                CountMessage(
                    context=name,
                    source=source,
                    disambiguation=message.findtext("comment") or None,
                    forms=forms,
                )
            )
    return Catalogue(total=total, messages=tuple(kept))


def shown(template: str, count: int) -> str:
    """Return ``template`` as Qt shows it for ``count`` (``%n`` replaced)."""
    return template.replace("%n", str(count))


def qt_translate(message: CountMessage, count: int) -> str:
    """Return what the active catalogue makes of ``message`` for ``count``."""
    return QCoreApplication.translate(
        message.context, message.source, message.disambiguation, count
    )


@dataclass
class Verdict:
    """What the plural check found for one language."""

    language: str
    examined: int = 0
    distinguishing: int = 0
    problems: list[str] = field(default_factory=list)
    flagged_counts: set[int] = field(default_factory=set)


def judge(
    expectation: Expectation,
    messages: tuple[CountMessage, ...],
    translate: Translate,
) -> Verdict:
    """Compare what ``translate`` shows with the form each count must take."""
    verdict = Verdict(expectation.language)
    form_count = len(expectation.form_names)
    for message in messages:
        verdict.examined += 1
        if len(message.forms) != form_count:
            verdict.problems.append(
                f"{message.key}: the catalogue holds {len(message.forms)} forms, "
                f"{form_count} expected"
            )
            continue
        if message.forms_differ and form_count > 1:
            verdict.distinguishing += 1
        for count, index in expectation.form_for_count.items():
            wanted = shown(message.forms[index], count)
            seen = translate(message, count)
            if seen != wanted:
                verdict.flagged_counts.add(count)
                verdict.problems.append(
                    f"{message.key}: for {count} expected the "
                    f"{expectation.form_names[index]} form {wanted!r}, shown {seen!r}"
                )
    if verdict.examined == 0:
        verdict.problems.append("no count-bearing message was examined")
    if form_count > 1 and verdict.distinguishing == 0:
        verdict.problems.append(
            "no message has forms that differ, so no form could be told from another"
        )
    return verdict


def observed_form_names(
    expectation: Expectation, message: CountMessage, translate: Translate
) -> list[str]:
    """Return the name of the form ``translate`` shows for each scenario count."""
    names = []
    for count in expectation.counts:
        text = translate(message, count)
        matches = [
            index
            for index, form in enumerate(message.forms)
            if shown(form, count) == text
        ]
        names.append(
            expectation.form_names[matches[0]] if len(matches) == 1 else "unknown"
        )
    return names


def first_distinguishing(messages: tuple[CountMessage, ...]) -> CountMessage:
    """Return the first message whose forms all differ (there must be one)."""
    for message in messages:
        if message.forms_differ:
            return message
    raise AssertionError("no count-bearing message has forms that all differ")


def catalogue_dir_under_test() -> Path | None:
    """Return the compiled-catalogue directory to measure, ``None`` for the shipped."""
    value = os.environ.get(CATALOGUE_DIR_ENV)
    return Path(value) if value else None


def measure(manager: LanguageManager, code: str) -> tuple[Verdict, list[str]]:
    """Make ``code`` active, judge it, print what was seen, return verdict and names.

    The names are the forms the scenario names, observed on the first message whose
    forms all differ, so they are not a guess made from a message that repeats one.
    """
    assert manager.set_language(code) is True, f"no compiled catalogue for {code!r}"
    assert manager.current_language() == code
    expectation = EXPECTATIONS[code]
    catalogue = read_count_messages(code)
    verdict = judge(expectation, catalogue.messages, qt_translate)
    sample = first_distinguishing(catalogue.messages)
    names = observed_form_names(expectation, sample, qt_translate)
    print(
        f"{code}: {catalogue.total} count-bearing messages in the catalogue, "
        f"{verdict.examined} examined, {catalogue.total - verdict.examined} left out, "
        f"{verdict.distinguishing} with forms that all differ; "
        f"sample {ascii(sample.key)}"
    )
    for count, name in zip(expectation.counts, names):
        print(f"  {count} -> {ascii(qt_translate(sample, count))} ({name})")
    return verdict, names


@pytest.fixture(autouse=True)
def _process_as_found() -> Iterator[None]:
    """Fail the test that leaves the default locale or a catalogue changed."""
    locale_before = QLocale().name()
    yield
    problems = []
    if QLocale().name() != locale_before:
        problems.append(
            f"the default locale was {locale_before!r} and is now {QLocale().name()!r}"
        )
    word = QCoreApplication.translate("Main_Window", "Untitled")
    if word != "Untitled":
        problems.append(f"Main_Window: 'Untitled' reads {word!r}, a catalogue is left")
    assert problems == []


@pytest.fixture
def language_manager(qapp) -> Iterator[LanguageManager]:
    """Yield a fresh manager and put the interface back to English afterwards."""
    manager = LanguageManager(qapp, translations_dir=catalogue_dir_under_test())
    try:
        yield manager
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_sc_l10n_ui_006_1_russian_counts_take_three_forms(language_manager):
    """SC-L10N-UI-006-1: Russian shown for 1, 3, 5, 11, 21, 22 and 25 uses the
    forms one, few, many, many, one, few and many, on every count-bearing message."""
    verdict, names = measure(language_manager, "ru")
    assert verdict.problems == []
    assert verdict.examined > 0
    assert names == RUSSIAN_SCENARIO_FORMS


def test_sc_l10n_ui_006_2_french_treats_zero_as_singular(language_manager):
    """SC-L10N-UI-006-2: French shown for 0, 1 and 2 uses the forms singular,
    singular and plural, on every count-bearing message."""
    verdict, names = measure(language_manager, "fr")
    assert verdict.problems == []
    assert verdict.examined > 0
    assert names == FRENCH_SCENARIO_FORMS


@pytest.mark.parametrize("code", ONE_FORM_LANGUAGES)
def test_sc_l10n_ui_006_3_one_form_languages_use_the_same_form(language_manager, code):
    """SC-L10N-UI-006-3: with ``code`` active the message shown for 1 and for 5
    uses the same form, and the catalogue holds that one form only."""
    verdict, names = measure(language_manager, code)
    assert verdict.problems == []
    assert verdict.examined > 0
    assert names == ["only", "only"]
    assert names[0] == names[1]


def test_the_five_languages_in_turn_on_one_manager(language_manager):
    """SC-L10N-UI-006-1, -2 and -3 on ONE manager: each language is chosen in turn
    and judged, then Russian again, so a catalogue switched away from is never
    left installed and a form from the one before never reaches the next."""
    order = ("ru", "fr", "ja", "ko", "zh_CN", "ru")
    for code in order:
        verdict, names = measure(language_manager, code)
        assert verdict.problems == [], code
        assert verdict.examined > 0, code
    assert names == RUSSIAN_SCENARIO_FORMS
    print(f"{len(order)} switches judged in turn: {', '.join(order)}")


def test_control_english_active_fails_the_russian_verdict(language_manager):
    """Control: with English active the Russian verdict reports every count."""
    assert language_manager.set_language(FALLBACK_LANGUAGE) is True
    catalogue = read_count_messages("ru")
    verdict = judge(EXPECTATIONS["ru"], catalogue.messages, qt_translate)
    print(
        f"control, English active: {len(verdict.problems)} problems, "
        f"counts {sorted(verdict.flagged_counts)}"
    )
    assert verdict.examined > 0
    assert verdict.flagged_counts == set(EXPECTATIONS["ru"].counts)


def test_control_a_wrong_catalogue_fails_the_russian_verdict(qapp, tmp_path):
    """Control: a Russian catalogue that is the French one (a copy, in scratch)
    carries the wrong rule and the wrong words, and every count is reported."""
    shutil.copyfile(SHIPPED_DIR / "pixelart_fr.qm", tmp_path / "pixelart_ru.qm")
    manager = LanguageManager(qapp, translations_dir=tmp_path)
    try:
        assert manager.set_language("ru") is True
        catalogue = read_count_messages("ru")
        verdict = judge(EXPECTATIONS["ru"], catalogue.messages, qt_translate)
    finally:
        manager.set_language(FALLBACK_LANGUAGE)
    print(
        f"control, French catalogue as ru: {len(verdict.problems)} problems, "
        f"counts {sorted(verdict.flagged_counts)}"
    )
    assert verdict.examined > 0
    assert verdict.flagged_counts == set(EXPECTATIONS["ru"].counts)


def english_rule(message: CountMessage, count: int) -> str:
    """Show the first form for 1 and the second for every other count."""
    return shown(message.forms[0 if count == 1 else 1], count)


@pytest.mark.parametrize(
    ("code", "wrongly_shown"),
    (("ru", {5, 11, 21, 25}), ("fr", {0})),
)
def test_control_the_english_rule_is_reported(code, wrongly_shown):
    """Control: the English rule gets exactly these counts wrong for ``code``, and
    the verdict reports exactly those, not the ones the rule happens to get right."""
    catalogue = read_count_messages(code)
    verdict = judge(EXPECTATIONS[code], catalogue.messages, english_rule)
    print(f"control, English rule on {code}: counts {sorted(verdict.flagged_counts)}")
    assert verdict.flagged_counts == wrongly_shown


def test_control_a_form_that_changes_with_the_count_is_reported_for_one_form():
    """Control: a one-form language that shows a different text for 5 than for 1
    is reported at 5 only."""

    def plural_marker(message: CountMessage, count: int) -> str:
        return shown(message.forms[0], count) + ("" if count == 1 else "s")

    catalogue = read_count_messages("ja")
    verdict = judge(EXPECTATIONS["ja"], catalogue.messages, plural_marker)
    print(f"control, a second form for ja: counts {sorted(verdict.flagged_counts)}")
    assert verdict.flagged_counts == {5}


def test_control_a_verdict_over_no_messages_fails():
    """Control: judging no message at all is reported, with the reason."""
    verdict = judge(EXPECTATIONS["ru"], (), qt_translate)
    print(f"control, no messages: {verdict.problems}")
    assert verdict.examined == 0
    assert "no count-bearing message was examined" in verdict.problems


def test_control_a_catalogue_source_that_is_absent_fails_naming_the_path(tmp_path):
    """Control: the reader fails, naming the path, where there is no catalogue."""
    with pytest.raises(AssertionError) as raised:
        read_count_messages("ru", tmp_path)
    print(f"control, empty directory: {ascii(str(raised.value))}")
    assert repr(str(tmp_path / "pixelart_ru.ts")) in str(raised.value)
