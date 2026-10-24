"""Contract tests for ``scripts/check_catalogues.py`` (ADR-0047).

Contract asserted here, taken from the script's own header::

    check_catalogues.py [lint] CATALOGUE [CATALOGUE ...] [--source EN.ts] [--json]
    check_catalogues.py worklist FILE --catalogue TS [--json]
    check_catalogues.py inventory-plurals --catalogue EN.ts --py-dir DIR [--json]
    EXIT CODES: 0 clean ; 1 findings reported, or nothing examined ;
        2 usage or read error.

Method. Every fixture is a scratch catalogue, worklist or source tree built
under ``tmp_path`` and handed to the script by its own flags; the tracked
catalogues are never read. Each REGRESSION CASE below is a function that
drives the script through a clean fixture (exit 0) and a broken one (exit 1,
the finding named, the JSON parsed by field). A case is registered together
with one or more MUTANTS: a copy of the script, made under ``tmp_path``, with
one guarded line altered so that the rule the case defends is gone. The case
is then run twice by the module's generic tests, once against the real script
(it must hold) and once against each broken copy (it must raise an
``AssertionError``), so a case that cannot tell a working script from a
broken one fails the suite at once. A mutant whose anchor text is not found
exactly once also fails, so a renamed line cannot silently disarm a control.

The registry, the scratch-catalogue writer and the broken-copy builder below
are shared with the sibling module for the worklist script.
"""

from __future__ import annotations

import dataclasses
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

import pytest

from .conftest import SCRIPTS_DIR, ScriptRun

CHECK = "check_catalogues.py"
WORKLIST = "ts_worklist.py"
SCRIPT_NAMES = (CHECK, WORKLIST)


# --------------------------------------------------------------------------- #
# Scratch catalogues.
# --------------------------------------------------------------------------- #
@dataclasses.dataclass(frozen=True)
class Msg:
    """One message of a scratch catalogue, written the way Qt's tools write it.

    ``translation`` is a string for a plain message and a list of forms for a
    numerus one. ``raw``, when given, replaces the escaped body of a plain
    translation verbatim (to plant a spelling the importer must not rewrite).
    """

    source: str
    translation: str | list[str] = ""
    kind: str = ""
    numerus: bool = False
    disambiguation: str = ""
    comment: str = ""
    context: str = "Panel"
    raw: str | None = None


def _message_lines(message: Msg, number: int) -> list[str]:
    """Return the lines of one ``<message>`` element."""
    attribute = ' numerus="yes"' if message.numerus else ""
    lines = [
        f"    <message{attribute}>",
        f'        <location filename="../ui/panel.py" line="{number}"/>',
        f"        <source>{escape(message.source)}</source>",
    ]
    if message.disambiguation:
        lines.append(f"        <comment>{escape(message.disambiguation)}</comment>")
    if message.comment:
        lines.append(f"        <extracomment>{escape(message.comment)}</extracomment>")
    kind = f' type="{message.kind}"' if message.kind else ""
    if isinstance(message.translation, list):
        lines.append(f"        <translation{kind}>")
        lines.extend(
            f"            <numerusform>{escape(form)}</numerusform>"
            for form in message.translation
        )
        lines.append("        </translation>")
    else:
        body = message.raw if message.raw is not None else escape(message.translation)
        lines.append(f"        <translation{kind}>{body}</translation>")
    lines.append("    </message>")
    return lines


def ts_text(
    language: str,
    messages: list[Msg],
    *,
    source_language: str = "en",
    newline: str = "\n",
) -> str:
    """Return the text of a ``.ts`` file holding ``messages``."""
    root = '<TS version="2.1"'
    if language:
        root += f' language="{language}"'
    root += f' sourcelanguage="{source_language}">'
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<!DOCTYPE TS>", root]
    contexts: dict[str, list[Msg]] = {}
    for message in messages:
        contexts.setdefault(message.context, []).append(message)
    number = 0
    for name, group in contexts.items():
        lines.extend(["<context>", f"    <name>{escape(name)}</name>"])
        for message in group:
            number += 1
            lines.extend(_message_lines(message, number))
        lines.append("</context>")
    lines.append("</TS>")
    return newline.join(lines) + newline


def write_ts(path: Path, language: str, messages: list[Msg], **options) -> Path:
    """Write a scratch catalogue as UTF-8 bytes and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ts_text(language, messages, **options).encode("utf-8"))
    return path


def put(
    work: Path,
    folder: str,
    code: str,
    messages: list[Msg],
    language: str | None = None,
    **options,
) -> Path:
    """Write ``work/<folder>/pixelart_<code>.ts`` and return its path.

    ``language`` is the catalogue's own attribute, ``code`` the file's; they
    differ only in the fixtures that plant a mismatch.
    """
    path = work / folder / f"pixelart_{code}.ts"
    return write_ts(path, code if language is None else language, messages, **options)


# --------------------------------------------------------------------------- #
# Running a script, real or broken.
# --------------------------------------------------------------------------- #
class Tools(NamedTuple):
    """A folder holding the two scripts under test (real or broken copies)."""

    folder: Path

    def run(self, script: str, args: list[str], cwd: Path) -> ScriptRun:
        """Run ``script`` as a subprocess in ``cwd`` and return what it did."""
        completed = subprocess.run(
            [sys.executable, str(self.folder / script), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        return ScriptRun(completed.returncode, completed.stdout, completed.stderr)

    def json(self, script: str, args: list[str], cwd: Path) -> tuple[ScriptRun, dict]:
        """Run ``script``, require its stdout to be one JSON object, parse it."""
        run = self.run(script, args, cwd)
        try:
            payload = json.loads(run.stdout)
        except ValueError:
            raise AssertionError(
                f"stdout of {script} {args} is not JSON: exit {run.returncode}, "
                f"stdout {run.stdout[:300]!r}, stderr {run.stderr[:300]!r}"
            ) from None
        assert isinstance(payload, dict), payload
        return run, payload


class Edit(NamedTuple):
    """One text replacement applied to one script of a broken copy."""

    script: str
    old: str
    new: str


class Mutant(NamedTuple):
    """A labelled set of edits that makes a broken copy of the scripts."""

    label: str
    edits: tuple[Edit, ...]


def mutant(label: str, *edits: Edit) -> Mutant:
    """Build a mutant from its label and its edits."""
    return Mutant(label, edits)


def make_broken(folder: Path, broken: Mutant) -> Tools:
    """Copy both scripts into ``folder`` and apply ``broken``'s edits.

    The files are read and written as bytes. An anchor that is not found
    exactly once, or an edit that leaves a script that does not compile,
    raises: a control must fail for the reason it names and for no other.
    """
    folder.mkdir(parents=True)
    for name in SCRIPT_NAMES:
        shutil.copyfile(SCRIPTS_DIR / name, folder / name)
    for edit in broken.edits:
        target = folder / edit.script
        data = target.read_bytes()
        old, new = edit.old.encode("utf-8"), edit.new.encode("utf-8")
        if b"\r\n" in data:
            old, new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
        found = data.count(old)
        assert found == 1, f"{broken.label}: anchor found {found}x in {edit.script}"
        data = data.replace(old, new)
        compile(data, edit.script, "exec")
        target.write_bytes(data)
    return Tools(folder)


class Case(NamedTuple):
    """A regression case and the broken copies it must fail against."""

    name: str
    run: Callable[[Tools, Path], None]
    mutants: tuple[Mutant, ...]


class Registry:
    """The regression cases of one test module."""

    def __init__(self) -> None:
        """Start with no cases."""
        self.cases: list[Case] = []

    def regression(self, *mutants: Mutant):
        """Register the decorated ``case_<name>`` function with its mutants."""

        def register(function):
            name = function.__name__.removeprefix("case_")
            self.cases.append(Case(name, function, mutants))
            return function

        return register

    def real(self) -> list:
        """Return the pytest parameters of the real-script run, one per case."""
        return [pytest.param(case, id=case.name) for case in self.cases]

    def broken(self) -> list:
        """Return the pytest parameters of the broken-copy runs."""
        return [
            pytest.param(case, one, id=f"{case.name}--{one.label}")
            for case in self.cases
            for one in case.mutants
        ]


REGISTRY = Registry()


def edit(old: str, new: str, script: str = CHECK) -> Edit:
    """Build an edit of ``check_catalogues.py`` unless ``script`` says otherwise."""
    return Edit(script, old, new)


# --------------------------------------------------------------------------- #
# Small readers of the script's JSON.
# --------------------------------------------------------------------------- #
def lint(tools: Tools, work: Path, *paths: Path, source: Path | None = None):
    """Run the lint mode with ``--json`` and return ``(run, payload)``."""
    args = ["lint", *map(str, paths), "--json"]
    if source is not None:
        args += ["--source", str(source)]
    run, payload = tools.json(CHECK, args, work)
    assert payload["mode"] == "lint"
    assert payload["exit"] == run.returncode
    return run, payload


def findings(payload: dict, index: int = 0) -> list[dict]:
    """Return the findings of the ``index``-th catalogue of a lint report."""
    return payload["catalogues"][index]["findings"]


def checks(found: list[dict]) -> list[str]:
    """Return the sorted check names of a list of findings."""
    return sorted(item["check"] for item in found)


def assert_clean(tools: Tools, work: Path, *paths: Path, examined: int) -> None:
    """Assert that linting ``paths`` exits 0 with ``examined`` live messages."""
    run, payload = lint(tools, work, *paths)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert payload["examined_total"] == examined
    assert payload["findings_total"] == 0
    assert payload["exit"] == 0


def assert_flagged(
    tools: Tools, work: Path, path: Path, expected: list[str], **options
) -> list[dict]:
    """Assert that linting ``path`` exits 1 with exactly the ``expected`` checks."""
    run, payload = lint(tools, work, path, **options)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert checks(findings(payload)) == sorted(expected), findings(payload)
    return findings(payload)


# --------------------------------------------------------------------------- #
# Lint mode: the plural-form count of each language.
# --------------------------------------------------------------------------- #
RUSSIAN_FORMS = ["%n слой", "%n слоя", "%n слоёв"]


@REGISTRY.regression(
    mutant("russian-takes-two-forms", edit('    "ru": 3,\n', '    "ru": 2,\n')),
)
def case_russian_numerus_needs_three_forms(tools: Tools, work: Path) -> None:
    """A Russian numerus message with two forms exits 1 naming it; three pass."""
    two = put(work, "two", "ru", [Msg("%n layer(s)", RUSSIAN_FORMS[:2], numerus=True)])
    run, payload = lint(tools, work, two)
    assert run.returncode == 1, run.stderr
    [finding] = findings(payload)
    assert finding["check"] == "numerus-forms"
    assert finding["context"] == "Panel"
    assert finding["source"] == "%n layer(s)"
    assert finding["detail"] == "2 form(s) present, 3 required"
    text = tools.run(CHECK, ["lint", str(two)], work)
    assert text.returncode == 1
    assert "numerus-forms" in text.stdout and "%n layer(s)" in text.stdout

    three = put(work, "three", "ru", [Msg("%n layer(s)", RUSSIAN_FORMS, numerus=True)])
    assert_clean(tools, work, three, examined=1)

    blank = [RUSSIAN_FORMS[0], "", RUSSIAN_FORMS[2]]
    gap = put(work, "gap", "ru", [Msg("%n layer(s)", blank, numerus=True)])
    [empty] = assert_flagged(tools, work, gap, ["empty"])
    assert empty["detail"] == "form 2: translation is empty"


FORM_COUNTS = {"fr": 2, "de": 2, "es": 2, "zh_CN": 1, "ko": 1, "ja": 1}


@REGISTRY.regression(
    mutant("chinese-takes-two-forms", edit('    "zh": 1,\n', '    "zh": 2,\n')),
    mutant("german-takes-three-forms", edit('    "de": 2,\n', '    "de": 3,\n')),
)
def case_each_language_has_its_qt_form_count(tools: Tools, work: Path) -> None:
    """Each shipped language accepts its own form count and refuses its neighbours."""
    for code, count in FORM_COUNTS.items():
        for forms, ok in ((count, True), (count + 1, False), (count - 1, False)):
            words = [f"forma {number}" for number in range(forms)]
            message = Msg("%n layer(s)", words, numerus=True)
            path = put(work, f"{code}-{forms}", code, [message])
            if ok:
                assert_clean(tools, work, path, examined=1)
                continue
            [found] = assert_flagged(tools, work, path, ["numerus-forms"])
            assert found["detail"] == f"{forms} form(s) present, {count} required"


# --------------------------------------------------------------------------- #
# Lint mode: the ampersand rules.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant("lone-ampersand-passes", edit("    if tr_lone:\n", "    if False:\n")),
)
def case_a_lone_ampersand_is_refused(tools: Tools, work: Path) -> None:
    """A translator-typed access-key marker exits 1; a kept ``&&`` pair is clean."""
    typed = put(work, "typed", "es", [Msg("&Open", "&Abrir")])
    [found] = assert_flagged(tools, work, typed, ["lone-ampersand"])
    assert found["source"] == "&Open"
    assert "1 '&'" in found["detail"]
    text = tools.run(CHECK, ["lint", str(typed)], work)
    assert text.returncode == 1 and "lone-ampersand" in text.stdout

    # A literal ampersand that lost half of its pair is both findings.
    lost = put(work, "lost", "es", [Msg("Save && Exit", "Guardar & Salir")])
    assert_flagged(tools, work, lost, ["ampersand-pairs", "lone-ampersand"])

    clean = put(
        work,
        "clean",
        "es",
        [Msg("&Close", "Cerrar"), Msg("Save && Exit", "Guardar && Salir")],
    )
    assert_clean(tools, work, clean, examined=2)


@REGISTRY.regression(
    mutant(
        "pair-count-not-compared",
        edit("    if src_pairs != tr_pairs:\n", "    if False:\n"),
    ),
)
def case_the_double_ampersand_pairs_must_match(tools: Tools, work: Path) -> None:
    """A translation that drops the source's ``&&`` exits 1; keeping it is clean."""
    dropped = put(work, "dropped", "es", [Msg("Save && Exit", "Guardar y Salir")])
    [found] = assert_flagged(tools, work, dropped, ["ampersand-pairs"])
    assert found["detail"] == "source has 1 '&&', translation has 0"
    kept = put(work, "kept", "es", [Msg("Save && Exit", "Guardar && Salir")])
    assert_clean(tools, work, kept, examined=1)


# --------------------------------------------------------------------------- #
# Lint mode: placeholder, markup and entity parity.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "placeholders-not-compared",
        edit("    if src_ph != tr_ph:\n", "    if False:\n"),
    ),
)
def case_placeholders_must_match_in_kind_and_number(tools: Tools, work: Path) -> None:
    """A dropped ``%2`` or a ``%L1`` turned into ``%1`` exits 1; a reorder is clean."""
    lost = put(work, "lost", "es", [Msg("Layer %1 of %2", "Capa %1")])
    [found] = assert_flagged(tools, work, lost, ["placeholders"])
    assert found["detail"] == "source has [%1, %2], translation has [%1]"
    localised = put(work, "localised", "es", [Msg("Total: %L1", "Total: %1")])
    assert_flagged(tools, work, localised, ["placeholders"])
    moved = put(work, "moved", "es", [Msg("Layer %1 of %2", "De %2, la capa %1")])
    assert_clean(tools, work, moved, examined=1)


@REGISTRY.regression(
    mutant(
        "count-placeholder-always-compared",
        edit(
            "        found = [p for p in found if not COUNT_PLACEHOLDER.match(p)]\n",
            "        found = list(found)\n",
        ),
    ),
)
def case_the_count_placeholder_is_exempt_only_when_plural(
    tools: Tools, work: Path
) -> None:
    """A form that spells the number out may omit ``%n``; a plain message may not."""
    forms = ["Один слой", "%n слоя", "%n слоёв"]
    plural = put(work, "plural", "ru", [Msg("%n layer(s)", forms, numerus=True)])
    assert_clean(tools, work, plural, examined=1)
    plain = put(work, "plain", "es", [Msg("%n items", "elementos")])
    [found] = assert_flagged(tools, work, plain, ["placeholders"])
    assert found["detail"] == "source has [%n], translation has [none]"


@REGISTRY.regression(
    mutant(
        "markup-not-compared", edit("    if src_tags != tr_tags:\n", "    if False:\n")
    ),
)
def case_markup_tags_must_match(tools: Tools, work: Path) -> None:
    """An unclosed tag or a lost ``<br/>`` exits 1; matching tags are clean."""
    unclosed = put(
        work, "unclosed", "es", [Msg("<b>Bold</b> text", "<b>Negrita texto")]
    )
    assert_flagged(tools, work, unclosed, ["markup"])
    broken = put(work, "break", "es", [Msg("Line<br/>Break", "Linea Salto")])
    assert_flagged(tools, work, broken, ["markup"])
    kept = put(
        work,
        "kept",
        "es",
        [Msg("<b>Bold</b> text", "<B>Negrita</B> texto"), Msg("A<br/>B", "A<br/>B")],
    )
    assert_clean(tools, work, kept, examined=2)


@REGISTRY.regression(
    mutant(
        "entities-not-compared", edit("    if src_ent != tr_ent:\n", "    if False:\n")
    ),
)
def case_character_entities_must_match(tools: Tools, work: Path) -> None:
    """A dropped ``&amp;`` entity exits 1; it is not mistaken for a lone ``&``."""
    dropped = put(work, "dropped", "es", [Msg("Fish &amp; chips", "Pescado y patatas")])
    assert_flagged(tools, work, dropped, ["entities"])
    kept = put(work, "kept", "es", [Msg("Fish &amp; chips", "Pescado &amp; patatas")])
    assert_clean(tools, work, kept, examined=1)


# --------------------------------------------------------------------------- #
# Lint mode: unfinished, empty, vanished and identity catalogues.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "unfinished-passes",
        edit("        if pending and not catalogue.identity:\n", "        if False:\n"),
    ),
)
def case_an_unfinished_translation_is_a_finding(tools: Tools, work: Path) -> None:
    """A message still marked unfinished exits 1 in a translated catalogue."""
    pending = put(work, "pending", "es", [Msg("Close", "", kind="unfinished")])
    [found] = assert_flagged(tools, work, pending, ["unfinished"])
    assert found["source"] == "Close"
    done = put(work, "done", "es", [Msg("Close", "Cerrar")])
    assert_clean(tools, work, done, examined=1)


@REGISTRY.regression(
    mutant(
        "identity-flags-unfinished",
        edit(
            "        if pending and not catalogue.identity:\n", "        if pending:\n"
        ),
    ),
)
def case_the_source_catalogue_may_stay_unfinished(tools: Tools, work: Path) -> None:
    """A catalogue that translates into its own language skips the unfinished rule."""
    source = put(work, "source", "en", [Msg("Open", "", kind="unfinished")])
    run, payload = lint(tools, work, source)
    assert run.returncode == 0, (run.stdout, run.stderr)
    record = payload["catalogues"][0]
    assert record["identity"] is True
    assert record["examined"] == 1 and record["findings"] == []


@REGISTRY.regression(
    mutant(
        "empty-passes", edit("        if not text.strip():\n", "        if False:\n")
    ),
)
def case_a_finished_but_empty_translation_is_a_finding(
    tools: Tools, work: Path
) -> None:
    """A finished message with no text exits 1; the same text filled in is clean."""
    empty = put(work, "empty", "es", [Msg("Open", "  ")])
    [found] = assert_flagged(tools, work, empty, ["empty"])
    assert found["detail"] == "translation is empty"
    filled = put(work, "filled", "es", [Msg("Open", "Abrir")])
    assert_clean(tools, work, filled, examined=1)


@REGISTRY.regression(
    mutant(
        "dead-messages-are-live",
        edit(
            "        return self.kind not in DEAD_KINDS\n",
            "        return True\n",
        ),
    ),
)
def case_vanished_and_obsolete_messages_are_not_examined(
    tools: Tools, work: Path
) -> None:
    """Dead messages are left out of the denominator and are not linted."""
    messages = [
        Msg("Open", "Abrir"),
        Msg("Close", "Cerrar"),
        Msg("Old &", "", kind="vanished"),
        Msg("Older %1", "Viejo", kind="obsolete"),
    ]
    path = put(work, "dead", "es", messages)
    run, payload = lint(tools, work, path)
    assert run.returncode == 0, (run.stdout, run.stderr)
    record = payload["catalogues"][0]
    assert record["examined"] == 2
    assert record["excluded_vanished_or_obsolete"] == 2
    assert payload["examined_total"] == 2
    text = tools.run(CHECK, ["lint", str(path)], work)
    assert text.returncode == 0
    assert f"{path}: examined 2" in text.stdout
    assert "examined 2 live message(s), 0 finding(s)" in text.stdout


@REGISTRY.regression(
    mutant(
        "empty-is-silent-and-passes",
        edit(
            "    if not live:\n",
            "    if False:\n",
        ),
        edit(
            "    code = EXIT_FINDINGS if total or examined == 0 else EXIT_OK\n",
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant("empty-is-not-named", edit("    if not live:\n", "    if False:\n")),
)
def case_a_catalogue_with_no_live_message_examines_nothing(
    tools: Tools, work: Path
) -> None:
    """An empty catalogue, or one holding only dead messages, exits 1."""
    empty = put(work, "empty", "es", [])
    run, payload = lint(tools, work, empty)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["examined_total"] == 0
    assert checks(findings(payload)) == ["nothing-examined"]
    text = tools.run(CHECK, ["lint", str(empty)], work)
    assert text.returncode == 1
    assert "examined 0 live message(s)" in text.stdout
    assert "nothing examined" in text.stdout

    dead = put(work, "dead", "es", [Msg("Old", "Viejo", kind="vanished")])
    run, payload = lint(tools, work, dead)
    assert run.returncode == 1
    assert payload["examined_total"] == 0
    assert payload["catalogues"][0]["excluded_vanished_or_obsolete"] == 1

    good = put(work, "good", "es", [Msg("Open", "Abrir")])
    run, payload = lint(tools, work, good, empty)
    assert run.returncode == 1, "an empty catalogue among good ones still fails"
    assert payload["examined_total"] == 1


# --------------------------------------------------------------------------- #
# Lint mode: the language attribute and the source catalogue.
# --------------------------------------------------------------------------- #
@REGISTRY.regression(
    mutant(
        "attribute-mismatch-passes",
        edit("    elif code != catalogue.language:\n", "    elif False:\n"),
    ),
)
def case_the_language_attribute_must_match_the_file_code(
    tools: Tools, work: Path
) -> None:
    """A French file that says German exits 1 naming both; a missing one too."""
    wrong = put(work, "wrong", "fr", [Msg("Open", "Ouvrir")], language="de")
    [found] = assert_flagged(tools, work, wrong, ["language-attribute"])
    assert found["detail"] == (
        "language attribute 'de' differs from the file code 'fr'"
    )
    text = tools.run(CHECK, ["lint", str(wrong)], work)
    assert text.returncode == 1 and "language-attribute" in text.stdout

    unnamed = put(work, "unnamed", "fr", [Msg("Open", "Ouvrir")], language="")
    [found] = assert_flagged(tools, work, unnamed, ["language-attribute"])
    assert found["detail"] == "no language attribute"

    nocode = write_ts(work / "nocode" / "catalogue.ts", "fr", [Msg("Open", "Ouvrir")])
    [found] = assert_flagged(tools, work, nocode, ["language-attribute"])
    assert "cannot read a language code" in found["detail"]

    right = put(work, "right", "fr", [Msg("Open", "Ouvrir")])
    assert_clean(tools, work, right, examined=1)


@REGISTRY.regression(
    mutant(
        "unknown-language-passes",
        edit(
            "    if catalogue.language and plural_forms is None:\n", "    if False:\n"
        ),
    ),
)
def case_a_language_without_a_known_form_count_is_reported(
    tools: Tools, work: Path
) -> None:
    """A catalogue in a language the script has no plural rule for exits 1."""
    other = put(work, "other", "pt", [Msg("Open", "Abrir")])
    [found] = assert_flagged(tools, work, other, ["language-unknown"])
    assert "'pt'" in found["detail"]


@REGISTRY.regression(
    mutant(
        "source-not-consulted",
        edit(
            "        if source_keys is not None and message.key not in source_keys:\n",
            "        if False:\n",
        ),
    ),
)
def case_a_message_absent_from_the_source_catalogue_is_refused(
    tools: Tools, work: Path
) -> None:
    """With ``--source`` a translated key the English file lacks exits 1."""
    english = put(
        work,
        "en",
        "en",
        [Msg("Open", "", kind="unfinished"), Msg("Close", "", kind="unfinished")],
    )
    matching = put(work, "ok", "es", [Msg("Open", "Abrir"), Msg("Close", "Cerrar")])
    run, payload = lint(tools, work, matching, source=english)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert payload["source"] == str(english)

    extra = put(work, "extra", "es", [Msg("Open", "Abrir"), Msg("Quit", "Salir")])
    [found] = assert_flagged(tools, work, extra, ["absent-from-source"], source=english)
    assert found["source"] == "Quit"

    # The key includes the disambiguation: the same text under another one is new.
    menu = put(work, "menu", "es", [Msg("Open", "Abrir", disambiguation="menu")])
    [found] = assert_flagged(tools, work, menu, ["absent-from-source"], source=english)
    assert found["source"] == "Open"

    # The source may be listed among the catalogues without failing itself.
    run, payload = lint(tools, work, english, matching, source=english)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert [r["examined"] for r in payload["catalogues"]] == [2, 2]


@REGISTRY.regression(
    mutant(
        "default-mode-is-wrong",
        edit(
            '        argv.insert(0, "lint")\n', '        argv.insert(0, "worklist")\n'
        ),
    ),
)
def case_without_a_mode_word_the_lint_runs(tools: Tools, work: Path) -> None:
    """``check_catalogues.py FILE`` and ``check_catalogues.py lint FILE`` agree."""
    path = put(work, "bare", "es", [Msg("Open", "Abrir")])
    bare = tools.run(CHECK, [str(path), "--json"], work)
    named = tools.run(CHECK, ["lint", str(path), "--json"], work)
    assert bare.returncode == named.returncode == 0, (bare.stderr, named.stderr)
    assert json.loads(bare.stdout) == json.loads(named.stdout)
    assert json.loads(bare.stdout)["mode"] == "lint"


@REGISTRY.regression(
    mutant(
        "read-error-exits-1",
        edit("        return EXIT_ERROR\n", "        return EXIT_FINDINGS\n"),
    ),
)
def case_an_unreadable_input_exits_2(tools: Tools, work: Path) -> None:
    """A missing file, malformed XML, a wrong root or a bad worklist exit 2."""
    good = put(work, "good", "es", [Msg("Open", "Abrir")])
    missing = tools.run(CHECK, ["lint", str(work / "nope.ts")], work)
    assert missing.returncode == 2 and missing.stderr.startswith("error:")
    assert missing.stdout == ""

    garbage = work / "garbage" / "pixelart_es.ts"
    garbage.parent.mkdir()
    garbage.write_bytes(b"<TS><context>")
    assert tools.run(CHECK, ["lint", str(garbage)], work).returncode == 2

    wrong_root = work / "root" / "pixelart_es.ts"
    wrong_root.parent.mkdir()
    wrong_root.write_bytes(b"<NotTS/>")
    result = tools.run(CHECK, ["lint", str(wrong_root)], work)
    assert result.returncode == 2 and "not <TS>" in result.stderr

    no_source = tools.run(CHECK, ["lint", str(good), "--source", "nope.ts"], work)
    assert no_source.returncode == 2

    listing = work / "list.json"
    listing.write_text("[]", encoding="utf-8")
    result = tools.run(
        CHECK, ["worklist", str(listing), "--catalogue", str(good)], work
    )
    assert result.returncode == 2 and "not a JSON object" in result.stderr
    result = tools.run(
        CHECK, ["worklist", str(work / "no.json"), "--catalogue", str(good)], work
    )
    assert result.returncode == 2


# --------------------------------------------------------------------------- #
# The plural inventory.
# --------------------------------------------------------------------------- #
PANEL_SOURCE = """\
class Panel:
    def build(self, items, index, frame_count, layer_count, count):
        shown = self.tr("Showing %1 items").arg(len(items))
        frame = self.tr("Frame %1").arg(index)
        total = self.tr("Total {n} layers").format(n=layer_count)
        jump = self.tr("Jump to %1").replace("%1", str(frame_count))
        used = QCoreApplication.translate("Panel", "Spaces %1 used").arg(len(items))
        aware = self.tr("Aware %1", n=count).arg(count)
        return shown, frame, total, jump, used, aware
"""

OTHER_SOURCE = 'label = tr("Open")\n'

INVENTORY_ENGLISH = [
    Msg("Delete layer(s)?", "", kind="unfinished"),
    Msg("%n frame(s) dropped", ["", ""], kind="unfinished", numerus=True),
    Msg("%n item selected", "", kind="unfinished"),
    Msg("Showing %1 items", "", kind="unfinished"),
    Msg("Frame %1", "", kind="unfinished"),
    Msg("Total {n} layers", "", kind="unfinished"),
    Msg("Jump to %1", "", kind="unfinished"),
    Msg("Spaces %1 used", "", kind="unfinished"),
    Msg("Aware %1", "", kind="unfinished"),
    Msg("Open", "", kind="unfinished"),
    Msg("Old %n thing", "", kind="vanished"),
]


def _line_of(source: str, fragment: str) -> int:
    """Return the 1-based line of ``source`` that holds ``fragment``."""
    for number, line in enumerate(source.splitlines(), start=1):
        if fragment in line:
            return number
    raise AssertionError(f"{fragment!r} not in the fixture source")


def _source_tree(work: Path, name: str) -> Path:
    """Write the scratch Python tree of the inventory cases and return its root."""
    root = work / name
    (root / "ui").mkdir(parents=True)
    (root / "ui" / "panel.py").write_text(PANEL_SOURCE, encoding="utf-8")
    (root / "other.py").write_text(OTHER_SOURCE, encoding="utf-8")
    (root / "notes.txt").write_text('tr("Ignored %n")\n', encoding="utf-8")
    return root


@REGISTRY.regression(
    mutant(
        "dead-messages-are-counted",
        edit(
            '        "examined": len(live),\n        "python_files": files,\n',
            '        "examined": len(catalogue.messages),\n'
            '        "python_files": files,\n',
        ),
    ),
    mutant(
        "percent-n-rule-is-dead",
        edit(
            're.search(r"%L?n", message.source)', 're.search(r"%L?nn", message.source)'
        ),
    ),
    mutant("aware-sites-are-listed", edit('if not s["aware"]', 'if s["aware"]')),
)
def case_the_inventory_lists_count_bearing_messages(tools: Tools, work: Path) -> None:
    """Non-plural messages that carry a count are listed, with the count printed."""
    english = put(work, "en", "en", INVENTORY_ENGLISH)
    tree = _source_tree(work, "src")
    args = ["inventory-plurals", "--catalogue", str(english), "--py-dir", str(tree)]
    run, payload = tools.json(CHECK, [*args, "--json"], work)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["mode"] == "inventory-plurals" and payload["exit"] == 1
    # 11 messages in the catalogue, 1 of them vanished: the denominator is 10.
    assert payload["examined"] == 10
    assert payload["python_files"] == 2
    assert payload["call_sites"] == 7
    listed = {item["source"]: item for item in payload["listed"]}
    assert {name: item["rules"] for name, item in listed.items()} == {
        "Delete layer(s)?": ["optional-plural-suffix"],
        "%n item selected": ["percent-n-without-numerus"],
        "Showing %1 items": ["count-argument"],
        "Total {n} layers": ["count-argument"],
        "Jump to %1": ["count-argument"],
        "Spaces %1 used": ["count-argument"],
    }
    for name, fragment in (
        ("Showing %1 items", "Showing"),
        ("Total {n} layers", "Total"),
        ("Jump to %1", "Jump"),
        ("Spaces %1 used", "Spaces"),
    ):
        site = f"ui/panel.py:{_line_of(PANEL_SOURCE, fragment)}"
        assert listed[name]["call_sites"] == [site]
    # Not listed: plural aware, not count-like, already numerus, vanished.
    for name in ("Aware %1", "Frame %1", "%n frame(s) dropped", "Old %n thing"):
        assert name not in listed

    text = tools.run(CHECK, args, work)
    assert text.returncode == 1
    assert (
        "examined 10 live message(s) and 7 tr() call site(s) in 2 file(s); " "6 listed"
    ) in text.stdout

    # A catalogue whose counts are all plural aware is clean, and says what it read.
    aware_only = put(
        work,
        "aware",
        "en",
        [
            Msg("%n frame(s)", ["", ""], kind="unfinished", numerus=True),
            Msg("Open", "", kind="unfinished"),
        ],
    )
    quiet = work / "quiet"
    quiet.mkdir()
    (quiet / "a.py").write_text('x = self.tr("%n frame(s)", None, count)\n')
    clean_args = ["--catalogue", str(aware_only), "--py-dir", str(quiet), "--json"]
    run, payload = tools.json(CHECK, ["inventory-plurals", *clean_args], work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert payload["examined"] == 2 and payload["python_files"] == 1
    assert payload["call_sites"] == 1 and payload["listed"] == []


@REGISTRY.regression(
    mutant(
        "no-python-files-is-fine",
        edit(
            '    blind = record["examined"] == 0 or record["python_files"] == 0\n',
            '    blind = record["examined"] == 0\n',
        ),
    ),
)
def case_an_inventory_that_read_nothing_fails(tools: Tools, work: Path) -> None:
    """No Python file, or no live message, means nothing was examined: exit 1."""
    english = put(work, "en", "en", [Msg("Open", "", kind="unfinished")])
    bare = work / "bare"
    bare.mkdir()
    base = ["inventory-plurals", "--catalogue", str(english), "--py-dir", str(bare)]
    run = tools.run(CHECK, base, work)
    assert run.returncode == 1 and "nothing examined" in run.stdout
    run, payload = tools.json(CHECK, [*base, "--json"], work)
    assert run.returncode == 1 and payload["python_files"] == 0

    (bare / "a.py").write_text("x = 1\n", encoding="utf-8")
    run = tools.run(CHECK, base, work)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert "nothing examined" not in run.stdout

    empty = put(work, "empty", "en", [])
    run = tools.run(
        CHECK,
        ["inventory-plurals", "--catalogue", str(empty), "--py-dir", str(bare)],
        work,
    )
    assert run.returncode == 1 and "nothing examined" in run.stdout


@REGISTRY.regression(
    mutant(
        "any-catalogue-is-accepted",
        edit("    if not catalogue.identity:\n", "    if False:\n"),
    ),
)
def case_the_inventory_runs_over_the_source_language_only(
    tools: Tools, work: Path
) -> None:
    """A translated catalogue is refused with exit 2, not inventoried."""
    translated = put(work, "es", "es", [Msg("Open", "Abrir")])
    run = tools.run(
        CHECK,
        ["inventory-plurals", "--catalogue", str(translated), "--py-dir", str(work)],
        work,
    )
    assert run.returncode == 2, (run.stdout, run.stderr)
    assert "source-language" in run.stderr


# --------------------------------------------------------------------------- #
# The worklist mode.
# --------------------------------------------------------------------------- #
WORKLIST_CATALOGUE = [
    Msg("Open", "Abrir"),
    Msg("%n layer(s)", ["%n capa", "%n capas"], numerus=True),
    Msg("Menu", "Menú", comment="Menu item"),
    Msg("Save", "Guardar"),
    Msg("Layer %1", "Capa %1"),
    Msg("Close", "Cerrar"),
    Msg("Old", "Viejo", kind="vanished"),
]


def entry(source: str, translation, **options) -> dict:
    """Build a worklist entry for the ``Panel`` context."""
    forms = len(translation) if isinstance(translation, list) else 1
    return {
        "context": options.get("context", "Panel"),
        "source": source,
        "disambiguation": None,
        "comment": options.get("comment"),
        "numerus": options.get("numerus", False),
        "forms_required": options.get("forms_required", forms),
        "translation": translation,
        "note": "",
    }


def worklist_document(entries: list, **header) -> dict:
    """Build a worklist document for the Spanish scratch catalogue."""
    document = {
        "schema": 1,
        "language": "es",
        "batch": "screen",
        "instance": 1,
        "mode": "new",
        "source_catalogue": "pixelart_es.ts",
        "source_sha256": "0" * 64,
        "rules": [],
        "entries": entries,
    }
    document.update(header)
    return document


def lint_worklist(tools: Tools, work: Path, document: dict, catalogue: Path):
    """Write ``document`` beside ``work`` and run the worklist mode over it."""
    path = work / "worklist.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    args = ["worklist", str(path), "--catalogue", str(catalogue), "--json"]
    run, payload = tools.json(CHECK, args, work)
    assert payload["mode"] == "worklist"
    assert payload["exit"] == run.returncode
    return run, payload


CLEAN_ENTRIES = [
    entry("Open", ["Abrir"]),
    entry("%n layer(s)", ["%n capa", "%n capas"], numerus=True),
    entry("Menu", ["Menú"], comment="Menu item"),
]


@REGISTRY.regression(
    mutant(
        "duplicate-passes", edit("        if key in seen:\n", "        if False:\n")
    ),
    mutant(
        "vanished-key-is-known",
        edit(
            "    index = {m.key: m for m in catalogue.live_messages()}\n"
            "    seen = set()\n",
            "    index = {m.key: m for m in catalogue.messages}\n    seen = set()\n",
        ),
    ),
    mutant(
        "numerus-flag-passes",
        edit(
            '        if bool(entry.get("numerus")) != message.numerus:\n',
            "        if False:\n",
        ),
    ),
    mutant(
        "comment-passes",
        edit(
            "        if comment is not None and comment != message.extra_comment:\n",
            "        if False:\n",
        ),
    ),
    mutant(
        "forms-required-passes",
        edit(
            '        if entry.get("forms_required") != required '
            "and required is not None:\n",
            "        if False:\n",
        ),
    ),
    mutant(
        "translation-type-passes",
        edit(
            "        if not isinstance(forms, list) "
            "or not all(isinstance(f, str) for f in forms):\n",
            "        if False:\n",
        ),
    ),
)
def case_a_worklist_entry_is_judged_on_its_own(tools: Tools, work: Path) -> None:
    """Each defective entry is named by its number; the good one is not."""
    catalogue = put(work, "cat", "es", WORKLIST_CATALOGUE)
    run, payload = lint_worklist(
        tools, work, worklist_document(CLEAN_ENTRIES), catalogue
    )
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert payload["examined_total"] == 3 and payload["findings_total"] == 0

    entries = [
        entry("Open", ["Abrir"]),  # 1: good
        entry("Open", ["Abrir"]),  # 2: the same key twice
        entry("Nowhere", ["Nada"]),  # 3: not in the catalogue
        entry("Old", ["Viejo"]),  # 4: only a vanished message
        entry("%n layer(s)", ["%n capa", "%n capas"], numerus=False),  # 5
        entry("Menu", ["Menú"], comment="Wrong comment"),  # 6
        entry("Save", ["Guardar"], forms_required=2),  # 7
        entry("Layer %1", ["Capa"]),  # 8: placeholder lost
        entry("Close", "Cerrar"),  # 9: translation is not a list
    ]
    run, payload = lint_worklist(tools, work, worklist_document(entries), catalogue)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["examined_total"] == 9
    by_entry: dict[int, list[str]] = {}
    for found in payload["record"]["findings"]:
        number = int(re.match(r"entry (\d+)", found["detail"]).group(1))
        by_entry.setdefault(number, []).append(found["check"])
    assert by_entry == {
        2: ["duplicate-entry"],
        3: ["unknown-key"],
        4: ["unknown-key"],
        5: ["numerus-flag"],
        6: ["comment-mismatch"],
        7: ["numerus-forms"],
        8: ["placeholders"],
        9: ["worklist-schema"],
    }


@REGISTRY.regression(
    mutant(
        "schema-passes",
        edit('    if worklist.get("schema") != 1:\n', "    if False:\n"),
    ),
    mutant(
        "language-passes",
        edit(
            '    if worklist.get("language") != catalogue.language:\n',
            "    if False:\n",
        ),
    ),
    mutant(
        "catalogue-name-passes",
        edit("    if named != os.path.basename(catalogue.path):\n", "    if False:\n"),
    ),
)
def case_a_worklist_must_describe_the_catalogue_it_is_checked_against(
    tools: Tools, work: Path
) -> None:
    """A wrong schema, language or catalogue name exits 1, each one named."""
    catalogue = put(work, "cat", "es", WORKLIST_CATALOGUE)
    bad = worklist_document(
        CLEAN_ENTRIES, schema=2, language="fr", source_catalogue="pixelart_fr.ts"
    )
    run, payload = lint_worklist(tools, work, bad, catalogue)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert checks(payload["record"]["findings"]) == [
        "language-attribute",
        "worklist-catalogue",
        "worklist-schema",
    ]
    # The entries themselves were still examined.
    assert payload["examined_total"] == 3


@REGISTRY.regression(
    mutant(
        "empty-worklist-passes",
        edit("    if not entries:\n", "    if False:\n"),
        edit(
            "    code = EXIT_FINDINGS "
            'if total or record["examined"] == 0 else EXIT_OK\n',
            "    code = EXIT_FINDINGS if total else EXIT_OK\n",
        ),
    ),
    mutant(
        "empty-worklist-not-named", edit("    if not entries:\n", "    if False:\n")
    ),
)
def case_a_worklist_without_entries_examines_nothing(tools: Tools, work: Path) -> None:
    """An empty worklist exits 1 and says so, in JSON and in text."""
    catalogue = put(work, "cat", "es", WORKLIST_CATALOGUE)
    run, payload = lint_worklist(tools, work, worklist_document([]), catalogue)
    assert run.returncode == 1, (run.stdout, run.stderr)
    assert payload["examined_total"] == 0
    assert checks(payload["record"]["findings"]) == ["nothing-examined"]
    path = work / "worklist.json"
    text = tools.run(
        CHECK, ["worklist", str(path), "--catalogue", str(catalogue)], work
    )
    assert text.returncode == 1 and "nothing examined" in text.stdout


# --------------------------------------------------------------------------- #
# The generic tests: every case against the real script and its broken copies.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", REGISTRY.real())
def test_case_holds_on_the_real_script(case: Case, tmp_path: Path) -> None:
    """The clean fixture exits 0 and the broken one exits 1, as the case states."""
    work = tmp_path / "work"
    work.mkdir()
    case.run(Tools(SCRIPTS_DIR), work)


@pytest.mark.parametrize(("case", "broken"), REGISTRY.broken())
def test_case_fails_on_a_broken_copy(
    case: Case, broken: Mutant, tmp_path: Path
) -> None:
    """With the defended rule removed from a copy of the script the case fails."""
    tools = make_broken(tmp_path / "scripts", broken)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(AssertionError):
        case.run(tools, work)


def test_every_case_has_a_broken_copy() -> None:
    """A case registered without a mutant would be a control that controls nothing."""
    assert REGISTRY.cases
    assert [case.name for case in REGISTRY.cases if not case.mutants] == []


def test_an_unmodified_copy_behaves_like_the_real_script(tmp_path: Path) -> None:
    """The broken-copy machinery is neutral: a copy with no edit passes the cases."""
    tools = make_broken(tmp_path / "scripts", Mutant("unmodified", ()))
    for case in REGISTRY.cases[:3]:
        work = tmp_path / case.name
        work.mkdir()
        case.run(tools, work)
