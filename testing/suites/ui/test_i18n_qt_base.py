"""UI tests for Qt's own catalogues (REQ-L10N-UI-005, REQ-AV-UI-012).

``LanguageManager`` installs a SECOND :class:`~PySide6.QtCore.QTranslator` holding
Qt's own ``qtbase_<code>.qm`` catalogue beside the application catalogue, so text
Qt itself generates (the macOS application-menu "About %1", and every standard
:class:`~PySide6.QtWidgets.QDialogButtonBox` button) follows the active language.

What is covered, by scenario id:

* **SC-L10N-UI-005-1** with each of ``fr``, ``de``, ``ru``, ``zh_CN``, ``ko`` and
  ``ja`` active in turn, a standard Cancel button reads something other than
  "Cancel" and equals Qt's own translation of Cancel for that language. The
  expected word is read straight from the language's ``qtbase_<code>.qm`` with a
  translator the test builds itself, never through ``LanguageManager``, so the
  product cannot supply its own answer. A catalogue Qt does not ship on the
  operating system under test fails with its path named (the gap is the result,
  never a skip). The test prints the language, the operating system and both
  words, so each operating system's run shows what it measured.
* **REQ-L10N-UI-005, degraded mode** with the Qt translations directory empty the
  language still switches, the application catalogue is active, Qt's own words
  stay English and a warning is logged, for the six languages and for ``es``.
* the ``es`` catalogue the feature began with (the macOS application-menu text
  and the Cancel button), kept as it was.

Measured on this machine (Windows, PySide6 6.11.1, ``QT_QPA_PLATFORM=offscreen``):
the wheel carries ``qtbase_<code>.qm`` for all seven languages above, and loading
one directly translates ``QPlatformTheme`` "Cancel" and the button's text alike.
The Linux and macOS wheels are measured only by their own CI runs.

Instruments and their controls. A check that reports "nothing wrong" is worth
something only if it would have reported a failure, so each one is shown failing:

* the Cancel verdict against English still active and against another language's
  catalogue active (it reports "still English" and "not Qt's word");
* the catalogue reader against an empty directory (it fails naming the path);
* the process guard against a replaced ``QLocale.system`` and against a language
  left installed.

No test leaves the process changed. Every window here pins ``QLocale.system`` to
English through a patch the fixture undoes itself, and an enclosing guard reads
the pin, the default locale and the words of both catalogues before and after
every test, so a fixture that stopped restoring what it patches fails the test
that leaked, not some later one.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QDialogButtonBox

from pixelart_creator.ui.i18n import FALLBACK_LANGUAGE, LanguageManager

#: The six languages SC-L10N-UI-005-1 names, in the scenario's order.
NEW_LANGUAGES = ("fr", "de", "ru", "zh_CN", "ko", "ja")

#: The context Qt files its standard-button words under.
QT_BUTTON_CONTEXT = "QPlatformTheme"

#: One source string per catalogue, each read as English when nothing is installed.
ENGLISH_SOURCES = (
    (QT_BUTTON_CONTEXT, "Cancel"),
    ("MAC_APPLICATION_MENU", "About %1"),
    ("Main_Window", "Untitled"),
)


def qt_translations_dir() -> str:
    """Return the directory Qt's own catalogues are looked up in."""
    return QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)


def qt_own_cancel(code: str, directory: str | None = None) -> str:
    """Return Qt's own translation of Cancel for ``code``, read from its catalogue.

    A translator built here, outside ``LanguageManager``, loads
    ``qtbase_<code>.qm`` and answers the standard-button context. A missing
    catalogue, or one that answers with the English word, fails with the path and
    the operating system named.
    """
    where = qt_translations_dir() if directory is None else directory
    translator = QTranslator()
    assert translator.load(f"qtbase_{code}", where), (
        f"Qt ships no qtbase_{code} catalogue under {where!r} on {sys.platform}: "
        "its Cancel button cannot be shown in that language"
    )
    word = translator.translate(QT_BUTTON_CONTEXT, "Cancel")
    assert word and word != "Cancel", (
        f"qtbase_{code} under {where!r} on {sys.platform} has no translation of "
        f"Cancel (it answered {word!r})"
    )
    return word


def cancel_button_text(qtbot) -> str:
    """Return the text of a standard Cancel button built now."""
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    qtbot.addWidget(box)
    button = box.button(QDialogButtonBox.StandardButton.Cancel)
    assert button is not None
    return button.text()


def cancel_problems(text: str, expected: str) -> list[str]:
    """Return what is wrong with a Cancel button reading ``text`` (empty if nothing)."""
    problems = []
    if text == "Cancel":
        problems.append("the button still reads the English word Cancel")
    if text != expected:
        problems.append(f"the button reads {text!r}, Qt's own word is {expected!r}")
    return problems


def pin_english_system_locale(patch: pytest.MonkeyPatch) -> None:
    """Make ``QLocale.system()`` answer English, through ``patch`` so it is undoable."""
    patch.setattr(
        QLocale,
        "system",
        staticmethod(
            lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
        ),
    )


def process_snapshot() -> tuple[object, str]:
    """Return what the guard compares: the ``system`` attribute and default locale."""
    return QLocale.__dict__.get("system"), QLocale().name()


def process_leaks(before: tuple[object, str]) -> list[str]:
    """Return how the process now differs from ``before``, one line each."""
    problems = []
    if QLocale.__dict__.get("system") is not before[0]:
        problems.append("QLocale.system was replaced and not put back")
    if QLocale().name() != before[1]:
        problems.append(
            f"the default locale was {before[1]!r} and is now {QLocale().name()!r}"
        )
    for context, source in ENGLISH_SOURCES:
        word = QCoreApplication.translate(context, source)
        if word != source:
            problems.append(
                f"{context}: {source!r} reads {word!r}, a catalogue is left"
            )
    return problems


@pytest.fixture
def _process_as_found() -> Iterator[None]:
    """Fail the test that leaves the process changed, after every undo has run."""
    before = process_snapshot()
    yield
    assert process_leaks(before) == []


@pytest.fixture(autouse=True)
def _english_start_language(_process_as_found: None) -> Iterator[None]:
    """Make ``QLocale.system`` resolve to English for the test, then put it back.

    The patch is undone inside this fixture, before the guard it depends on reads
    the process, so a pin that was not restored is reported by the test that made
    it. Every ``LanguageManager`` here is built fresh with an explicit
    ``set_language`` call and never reads the system locale, so the assertions do
    not depend on the host's locale either; the pin keeps that explicit.
    """
    with pytest.MonkeyPatch.context() as patch:
        pin_english_system_locale(patch)
        yield


@pytest.fixture
def language_manager(qapp) -> Iterator[LanguageManager]:
    """Yield a fresh manager and put the interface back to English afterwards."""
    manager = LanguageManager(qapp)
    try:
        yield manager
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_qt_base_catalogue_translates_mac_application_menu_and_reverts(qtbot, qapp):
    """After ``set_language("es")`` Qt's own MAC_APPLICATION_MENU text is
    Spanish; switching back to "en" reverts it to English."""
    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        translated = QCoreApplication.translate("MAC_APPLICATION_MENU", "About %1")
        assert translated == "Acerca de %1"

        assert manager.set_language(FALLBACK_LANGUAGE) is True
        reverted = QCoreApplication.translate("MAC_APPLICATION_MENU", "About %1")
        assert reverted == "About %1"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_qt_base_catalogue_translates_a_standard_dialog_button(qtbot, qapp):
    """The deliberate side effect this suite asserts: a
    :class:`QDialogButtonBox` standard Cancel button reads in Spanish once
    Qt's own base catalogue is active (proof the SECOND translator, not just
    the app one, is installed)."""
    manager = LanguageManager(qapp)
    try:
        assert manager.set_language("es") is True
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        qtbot.addWidget(box)
        button = box.button(QDialogButtonBox.StandardButton.Cancel)
        assert button.text() == "Cancelar"
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_qt_base_catalogue_missing_directory_degrades_with_a_warning(
    qtbot, qapp, tmp_path, monkeypatch, caplog
):
    """With the Qt translations path pointed at an EMPTY directory,
    ``set_language("es")`` still returns ``True``, the APP catalogue is still
    active, and a warning is logged -- with no exception.

    ``QLibraryInfo.path`` is the literal API that locates Qt's own catalogues;
    it is a Qt class staticmethod, monkeypatchable at the class level (a plain
    ``monkeypatch.setattr`` swap that takes effect and restores cleanly).
    """
    monkeypatch.setattr(
        QLibraryInfo, "path", staticmethod(lambda *_a, **_k: str(tmp_path))
    )
    manager = LanguageManager(qapp)
    try:
        with caplog.at_level(logging.WARNING):
            result = manager.set_language("es")
        assert result is True
        assert manager.current_language() == "es"
        # The APP catalogue is unaffected by the missing Qt catalogue.
        assert QCoreApplication.translate("Main_Window", "Untitled") == "Sin título"
        assert any(record.levelno >= logging.WARNING for record in caplog.records), (
            "expected a warning to be logged for the missing qtbase catalogue "
            f"directory; got: {[r.message for r in caplog.records]!r}"
        )
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


@pytest.mark.parametrize("code", NEW_LANGUAGES)
def test_sc_l10n_ui_005_1_standard_cancel_button_follows_the_language(
    qtbot, language_manager, code
):
    """SC-L10N-UI-005-1: with ``code`` active a standard Cancel button reads
    something other than "Cancel" and equals Qt's own translation of Cancel."""
    expected = qt_own_cancel(code)
    assert language_manager.set_language(code) is True
    text = cancel_button_text(qtbot)
    print(f"Cancel under {code} on {sys.platform}: {text!r}; Qt's own: {expected!r}")
    assert cancel_problems(text, expected) == []


def test_sc_l10n_ui_005_1_six_languages_in_turn_then_english_again(
    qtbot, language_manager
):
    """SC-L10N-UI-005-1: on ONE manager the six languages are chosen in turn and
    each Cancel button equals that language's own catalogue word, so a catalogue
    switched away from is never left installed; English reads Cancel again."""
    assert cancel_button_text(qtbot) == "Cancel"
    examined = {}
    for code in NEW_LANGUAGES:
        expected = qt_own_cancel(code)
        assert language_manager.set_language(code) is True
        examined[code] = cancel_button_text(qtbot)
        assert cancel_problems(examined[code], expected) == [], code
    assert len(set(examined.values())) == len(NEW_LANGUAGES), examined
    assert language_manager.set_language(FALLBACK_LANGUAGE) is True
    assert cancel_button_text(qtbot) == "Cancel"
    print(f"{len(examined)} languages examined on {sys.platform}: {examined}")
    assert len(examined) == 6


def test_sc_l10n_ui_005_1_control_the_verdict_reports_english_and_another_language(
    qtbot, language_manager
):
    """Control: the verdict the scenario test relies on is shown failing.

    With English active a Cancel button reads the source word, so the verdict
    against French lists both defects; with Japanese active it reads a word that
    is not English yet is not French either, so only the equality defect shows.
    """
    expected_fr = qt_own_cancel("fr")
    english = cancel_problems(cancel_button_text(qtbot), expected_fr)
    assert language_manager.set_language("ja") is True
    other = cancel_problems(cancel_button_text(qtbot), expected_fr)
    print(f"control, English active: {english}")
    print(f"control, ja active, fr expected: {other}")
    assert len(english) == 2
    assert "still reads the English word" in english[0]
    assert len(other) == 1
    assert "Qt's own word is" in other[0]


def test_sc_l10n_ui_005_1_control_a_missing_catalogue_fails_naming_the_path(
    tmp_path,
):
    """Control: the catalogue reader fails, naming the path, where Qt ships none."""
    with pytest.raises(AssertionError) as raised:
        qt_own_cancel("fr", directory=str(tmp_path))
    print(f"control, empty directory: {str(raised.value).splitlines()[0]}")
    assert "ships no qtbase_fr catalogue" in str(raised.value)
    assert repr(str(tmp_path)) in str(raised.value)


@pytest.mark.parametrize("code", (*NEW_LANGUAGES, "es"))
def test_req_l10n_ui_005_missing_qt_catalogue_degrades_for_each_language(
    qtbot, qapp, tmp_path, monkeypatch, caplog, code
):
    """REQ-L10N-UI-005: with Qt's translations directory empty the language still
    switches, the application catalogue is active, a warning is logged, and Qt's
    own Cancel stays English, so the gap is visible and nothing is half-installed."""
    monkeypatch.setattr(
        QLibraryInfo, "path", staticmethod(lambda *_a, **_k: str(tmp_path))
    )
    manager = LanguageManager(qapp)
    try:
        with caplog.at_level(logging.WARNING):
            assert manager.set_language(code) is True
        assert manager.current_language() == code
        file_title = QCoreApplication.translate("Main_Window", "&File")
        print(f"{code} with no Qt catalogue: File menu {file_title!r}")
        assert file_title != "&File"
        assert QCoreApplication.translate(QT_BUTTON_CONTEXT, "Cancel") == "Cancel"
        assert any(record.levelno >= logging.WARNING for record in caplog.records)
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


def test_the_locale_pin_puts_back_what_it_patches():
    """The pin the fixture applies is undone by the patch that applied it.

    A second pin is applied and undone inside the test: the attribute ends as it
    was, and while it was in place ``QLocale.system()`` answered English.
    """
    before = QLocale.__dict__.get("system")
    with pytest.MonkeyPatch.context() as patch:
        pin_english_system_locale(patch)
        assert QLocale.__dict__.get("system") is not before
        assert QLocale.system().name() == "en_US"
    assert QLocale.__dict__.get("system") is before


def test_control_the_process_guard_reports_a_leaked_pin_and_a_leaked_language(
    qapp,
):
    """Control: the guard that every test runs under is shown failing.

    A pin applied the way the old fixture applied it, a plain assignment with
    nothing undoing it, and a language left installed are each reported, then put
    back so the guard around this test finds the process as it was.
    """
    before = process_snapshot()
    pinned = before[0]
    manager = LanguageManager(qapp)
    try:
        setattr(QLocale, "system", staticmethod(lambda: QLocale("en_US")))
        leaked_pin = process_leaks(before)
        setattr(QLocale, "system", pinned)
        assert manager.set_language("fr") is True
        leaked_language = process_leaks(before)
    finally:
        setattr(QLocale, "system", pinned)
        manager.set_language(FALLBACK_LANGUAGE)
    print(f"control, a pin not put back: {leaked_pin}")
    print(f"control, a language left installed: {leaked_language}")
    assert leaked_pin == ["QLocale.system was replaced and not put back"]
    assert len(leaked_language) == len(ENGLISH_SOURCES)
    assert all("a catalogue is left" in line for line in leaked_language)
    assert process_leaks(before) == []
