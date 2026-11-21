"""Texts that used to be set once are re-set in every language.

REQ-L10N-UI-001 says that choosing a language re-sets every visible menu item,
tooltip, accessible name and label to that language, and REQ-L10N-UI-002 says
the start-up language must show in the same places. Three sites were set when
their widget was built and never again:

* Edit > Undo and Edit > Redo (Qt fixes the prefix when it creates the action,
  and again whenever a command's text changes);
* the colour wheel's preview accessible name, ``Current colour %1``;
* the timelapse reason label (``There is nothing recorded to play yet.``, and a
  frames-dropped notice that is already showing).

The oracle is the catalogue file, never the code under test. The expected text
is read from the language's own ``.ts`` file for the reused (context, source)
pair, and is the source text for English. Undo and Redo are compared after the
access-key presentation is removed from both sides (the ``&`` and a trailing
`` (X)``; ``&&`` stays a literal ampersand); the access key itself is asserted
separately, through ``QKeySequence.mnemonic``, to be Alt+U and Alt+R in every
language (REQ-L10N-UI-004). That reader consults a process-wide Qt flag whose
default differs by platform (off on macOS), so every case here forces the flag on
for its duration (the ``_qt_auto_mnemonic_enabled`` fixture) and the verdict does
not depend on the platform. The one exception to reading the ``.ts`` is the
numerus frames-dropped notice: its expected text comes from a plain
``QTranslator`` loaded straight from the shipped ``.qm``, which is Qt's own
plural lookup and not product code.

Every language is installed through the app's own path: the window's own
``LanguageManager`` for a live switch, and the manager that ``Main_Window`` runs
at start-up (fed by the system locale, which is replaced for the case) for the
start-up cases. English is restored after each case, so the cases are safe
under ``-n auto``. A known-true signal per language guards every case: for any
language but English the File menu title (or, for the widgets built without a
window, the translated File title) differs from ``&File``, so a case cannot pass
because nothing was installed. Both themes run via the autouse ``theme`` fixture.

What is deliberately not asserted: a command's own text keeps the language it
was pushed in, so after a switch the command part of the label is compared only
with the group's own ``undoText()``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Callable, Iterator, List, Tuple, cast

import pytest
from PySide6.QtCore import QCoreApplication, QLocale, QTranslator
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoCommand
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget
from pixelart_creator.ui.i18n import (
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

# --------------------------------------------------------------------------- #
# The catalogue oracle                                                        #
# --------------------------------------------------------------------------- #

#: The number of languages the finished product ships (English included).
EXPECTED_LANGUAGE_COUNT = 8

#: Switch for the language-count floor. ``False`` holds it: the floor in force is
#: 1, so the zero-examined guard still bites and every run prints ``HELD`` and how
#: many of the eight were discovered. The commit that brings the eighth catalogue
#: flips it to ``True``.
EIGHT_LANGUAGE_FLOOR_ENFORCED = True

_MAIN_WINDOW = "Main_Window"
_WHEEL = "Colour_Wheel_Widget"
_TIMELAPSE = "Timelapse_Controls"

_UNDO_SOURCE = "&Undo"
_REDO_SOURCE = "&Redo"
_FILE_SOURCE = "&File"
_WHEEL_SOURCE = "Current colour %1"
_NOTHING_SOURCE = "There is nothing recorded to play yet."
_DROPPED_SOURCE = (
    "%n frame(s) were dropped because the edits they recorded "
    "were undone and replaced."
)

#: A command text no catalogue translates and no language changes.
_COMMAND_TEXT = "Probe command 0042"

#: How many recorded frames the drop-notice cases discard (a count whose plural
#: form differs from one in some languages, so the count really is re-rendered).
_DROPPED_COUNT = 3

_SETTLE_TIMEOUT_MS = 2000


def _discover_languages() -> Tuple[str, ...]:
    """Return the languages the app itself offers, English first."""
    manager = LanguageManager(cast(QCoreApplication, QCoreApplication.instance()))
    return tuple(manager.available_languages())


#: The languages the app discovers (a ``pixelart_<code>.qm`` beside English).
LANGUAGES = _discover_languages()


def _language_floor() -> int:
    """Return the language-count floor in force: 8 once enforced, else 1."""
    return EXPECTED_LANGUAGE_COUNT if EIGHT_LANGUAGE_FLOOR_ENFORCED else 1


def _catalogue_text(code: str, context: str, source: str) -> str:
    """Return the text the ``.ts`` file of ``code`` holds for (context, source).

    Read from the catalogue file itself, never from ``translate()``. English has
    no translation and shows the source. A missing, duplicated, unfinished or
    empty entry fails here, so the expected text is never a guess.
    """
    if code == FALLBACK_LANGUAGE:
        return source
    path = _default_translations_dir() / f"pixelart_{code}.ts"
    root = ET.parse(path).getroot()
    found = [
        message
        for scope in root.iter("context")
        if scope.findtext("name") == context
        for message in scope.iter("message")
        if message.findtext("source") == source
    ]
    assert len(found) == 1, f"{path.name}: {len(found)} entries for {context!r}"
    translation = found[0].find("translation")
    assert translation is not None and translation.text, f"{path.name}: no text"
    assert translation.get("type") != "unfinished", f"{path.name}: unfinished"
    return translation.text


def _numerus_text(code: str, context: str, source: str, count: int) -> str:
    """Return the plural form Qt picks for ``count``, read from the shipped ``.qm``.

    This is Qt's lookup (a ``QTranslator`` of our own, not the app's), so the
    product plays no part in the expected text. English has no catalogue and
    shows the source with ``%n`` replaced by the count.
    """
    if code == FALLBACK_LANGUAGE:
        return source.replace("%n", str(count))
    translator = QTranslator()
    path = _default_translations_dir() / f"pixelart_{code}.qm"
    assert translator.load(str(path)), f"{path.name}: did not load"
    text = translator.translate(context, source, "", count)
    assert text, f"{path.name}: no plural form for {source!r}"
    return text.replace("%n", str(count))


_TRAILING_KEY = re.compile(r"\s*\(\w\)\s*$")
_AMPERSAND = re.compile(r"&(&?)")


def _plain(text: str) -> str:
    """Remove the access-key presentation: ``&`` markers and a trailing `` (X)``.

    ``&&`` is a literal ampersand and stays one.
    """
    return _TRAILING_KEY.sub("", _AMPERSAND.sub(r"\1", text))


def _mnemonic(text: str) -> str:
    """Return the access key Qt reads from ``text`` as ``Alt+<letter>`` text."""
    return QKeySequence.mnemonic(text).toString()


def _prefix_of(composed: str, command: str) -> str:
    """Return the part of ``composed`` before `` <command>``; fail if it is absent."""
    suffix = f" {command}"
    assert composed.endswith(suffix), f"{composed!r} does not end with {suffix!r}"
    return composed[: -len(suffix)]


def _hex_of(rgba: Tuple[int, int, int, int]) -> str:
    """Return ``#RRGGBB`` for an RGBA tuple (written out here, not imported)."""
    red, green, blue, _alpha = rgba
    return f"#{red:02X}{green:02X}{blue:02X}"


def _assert_language_in_force(code: str) -> None:
    """Known-true signal: a translated File title exists for every non-English code.

    Asks the application's translators directly for ``&File`` in the main window's
    context. Without it a case could pass because no translator was installed.
    """
    shown = QCoreApplication.translate(_MAIN_WINDOW, _FILE_SOURCE)
    if code == FALLBACK_LANGUAGE:
        assert shown == _FILE_SOURCE, f"English shows {shown!r} for {_FILE_SOURCE!r}"
    else:
        assert shown != _FILE_SOURCE, f"{code}: no translator is in force"


def _expected_prefixes(code: str) -> Tuple[str, str]:
    """Return the catalogue's Undo and Redo prefixes for ``code``."""
    return (
        _catalogue_text(code, _MAIN_WINDOW, _UNDO_SOURCE),
        _catalogue_text(code, _MAIN_WINDOW, _REDO_SOURCE),
    )


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _access_keys_are_read_by_qt(_qt_auto_mnemonic_enabled) -> None:
    """Every case reads access keys with Qt's mnemonic reader switched on.

    Without it the reader answers an empty key for every text on a platform whose
    default is off, whatever the product's text carries.
    """


@pytest.fixture
def language(qapp) -> Iterator[Callable[[str], None]]:
    """Install a language through the app's own manager; restore English after.

    The restore runs in teardown even when the case fails, so a translator never
    leaks into another case on the same worker (safe under ``-n auto``).
    """
    manager = LanguageManager(qapp)

    def install(code: str) -> None:
        assert manager.set_language(code) is True, f"{code!r} did not load"
        assert manager.current_language() == code

    try:
        yield install
    finally:
        manager.set_language(FALLBACK_LANGUAGE)


@pytest.fixture
def make_window(qtbot, monkeypatch) -> Iterator[Callable[..., Main_Window]]:
    """Build main windows; each one is returned to English in teardown.

    ``make_window(code)`` builds the window the way the app starts: the system
    locale reports ``code`` and ``Main_Window`` installs the matching language
    itself. ``make_window()`` builds it in English. The window's own manager
    switches back to English afterwards, even when the case fails.
    """
    built: List[Main_Window] = []

    def build(code: str = FALLBACK_LANGUAGE) -> Main_Window:
        monkeypatch.setattr(QLocale, "system", staticmethod(lambda: QLocale(code)))
        window = Main_Window()
        qtbot.addWidget(window)
        built.append(window)
        assert window._language_manager.current_language() == code
        _assert_language_in_force(code)
        return window

    try:
        yield build
    finally:
        for window in built:
            window._language_manager.set_language(FALLBACK_LANGUAGE)
        QApplication.processEvents()


def _switch(window: Main_Window, code: str) -> None:
    """Switch ``window`` to ``code`` through its own manager, then settle."""
    assert window._language_manager.set_language(code) is True, f"{code!r} not loaded"
    QApplication.processEvents()
    assert window._language_manager.current_language() == code
    _assert_language_in_force(code)


def _stack(window: Main_Window):
    """Return the active undo stack, failing if the window has none."""
    stack = window._undo_group.activeStack()
    assert stack is not None, "the window has no active undo stack"
    return stack


def _push_command(window: Main_Window) -> None:
    """Push one command with a fixed, language-neutral text on the active stack."""
    _stack(window).push(QUndoCommand(_COMMAND_TEXT))
    assert window._undo_group.undoText() == _COMMAND_TEXT


def _assert_bare(window: Main_Window, code: str) -> None:
    """Both actions show only the translated prefix, with the right access keys."""
    undo, redo = _expected_prefixes(code)
    for action, expected, key in (
        (window._undo_action, undo, "Alt+U"),
        (window._redo_action, redo, "Alt+R"),
    ):
        shown = action.text()
        assert _plain(shown) == _plain(expected), (
            f"{code}: {action.objectName() or 'action'} shows {shown!r}, "
            f"the catalogue holds {expected!r}"
        )
        assert _mnemonic(shown) == key, f"{code}: {shown!r} has key {_mnemonic(shown)}"


def _assert_composed(
    action: QAction, expected_prefix: str, key: str, command: str, code: str
) -> None:
    """The action reads ``<translated prefix> <command>`` with the right key."""
    shown = action.text()
    assert _plain(_prefix_of(shown, command)) == _plain(expected_prefix), (
        f"{code}: shows {shown!r}, the catalogue prefix is {expected_prefix!r}, "
        f"the command is {command!r}"
    )
    assert _mnemonic(shown) == key, f"{code}: {shown!r} has key {_mnemonic(shown)}"


# --------------------------------------------------------------------------- #
# Controls on the instrument                                                  #
# --------------------------------------------------------------------------- #


def test_the_app_discovers_its_languages():
    """REQ-L10N-UI-001: the per-language cases have something to run over.

    Prints the count and the state of the eight-language floor. Zero is a
    failure, never a pass over an empty set.
    """
    floor = _language_floor()
    state = "ENFORCED" if EIGHT_LANGUAGE_FLOOR_ENFORCED else "HELD"
    print(
        f"languages discovered: {len(LANGUAGES)} {sorted(LANGUAGES)}; "
        f"floor {floor} ({state}, expected at ship: {EXPECTED_LANGUAGE_COUNT})"
    )
    assert len(LANGUAGES) > 0, "no language was discovered"
    assert FALLBACK_LANGUAGE in LANGUAGES
    assert len(LANGUAGES) >= floor, (
        f"discovered {len(LANGUAGES)} languages {sorted(LANGUAGES)}, "
        f"the floor in force is {floor}"
    )


def test_the_comparison_helpers_accept_and_reject():
    """Control: the normaliser and the access-key reader can fail, and do.

    Written with literals so the product plays no part. The normaliser removes
    the marker and a trailing letter in brackets, keeps ``&&`` as an ampersand,
    and tells two different prefixes apart; the reader finds the key in a
    composed label and finds none where there is none.
    """
    assert _plain("&Undo") == "Undo"
    assert _plain("Wiede&rholen") == "Wiederholen"
    assert _plain("Rückgängig (&U)") == "Rückgängig"
    assert _plain("元に戻す (&U)") == "元に戻す"
    assert _plain("Save && Quit") == "Save & Quit"
    assert _plain("&Undo") != _plain("Rückgängig (&U)")
    assert _mnemonic("&Undo") == "Alt+U"
    assert _mnemonic("Rückgängig (&U) Probe") == "Alt+U"
    assert _mnemonic("Wiede&rholen") == "Alt+R"
    assert _mnemonic("Undo") == ""
    assert _prefix_of("&Undo Probe", "Probe") == "&Undo"
    assert _numerus_text("en", _TIMELAPSE, _DROPPED_SOURCE, 3).startswith("3 frame(s)")


# --------------------------------------------------------------------------- #
# Edit > Undo and Redo                                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("code", LANGUAGES)
def test_undo_and_redo_show_the_start_up_language(make_window, code):
    """REQ-L10N-UI-002, REQ-L10N-UI-004: Undo and Redo open in the start-up language.

    The window is built as the app builds it, with the language installed by
    ``Main_Window`` itself from the system locale. With nothing on the stack each
    item shows the catalogue's prefix alone, with the English-letter access key
    (Alt+U and Alt+R), and in no language but English does it show the English word.
    """
    window = make_window(code)

    assert window._undo_action in window._edit_menu.actions()
    assert window._redo_action in window._edit_menu.actions()
    _assert_bare(window, code)
    if code != FALLBACK_LANGUAGE:
        assert window._undo_action.text() != _UNDO_SOURCE
        assert window._redo_action.text() != _REDO_SOURCE


@pytest.mark.parametrize("code", LANGUAGES)
def test_undo_and_redo_follow_a_live_switch_and_back(make_window, code):
    """REQ-L10N-UI-001, REQ-L10N-UI-004: a live switch re-sets Undo and Redo.

    Built in English, switched to the language, then back to English: the texts
    follow each time, ``&Undo`` and ``&Redo`` in English, the catalogue's prefix
    in the language, with the same access keys throughout.
    """
    window = make_window()
    assert window._undo_action.text() == _UNDO_SOURCE
    assert window._redo_action.text() == _REDO_SOURCE

    _switch(window, code)
    _assert_bare(window, code)
    if code != FALLBACK_LANGUAGE:
        assert window._undo_action.text() != _UNDO_SOURCE
        assert window._redo_action.text() != _REDO_SOURCE

    _switch(window, FALLBACK_LANGUAGE)
    assert window._undo_action.text() == _UNDO_SOURCE
    assert window._redo_action.text() == _REDO_SOURCE
    _assert_bare(window, FALLBACK_LANGUAGE)


@pytest.mark.parametrize("code", LANGUAGES)
def test_a_command_on_the_stack_reads_translated_prefix_then_command(make_window, code):
    """REQ-L10N-UI-001, REQ-L10N-UI-002, REQ-L10N-UI-004: prefix + command text.

    At start-up in the language: with one command pushed the undo text is the
    catalogue's prefix, a space and the command; the redo side stays a bare
    prefix. After an undo the sides swap, and after a redo they swap back. The
    access keys stay Alt+U and Alt+R in every state.
    """
    window = make_window(code)
    undo_prefix, redo_prefix = _expected_prefixes(code)

    _push_command(window)
    _assert_composed(window._undo_action, undo_prefix, "Alt+U", _COMMAND_TEXT, code)
    assert _plain(window._redo_action.text()) == _plain(redo_prefix)
    assert _mnemonic(window._redo_action.text()) == "Alt+R"

    _stack(window).undo()
    assert window._undo_group.redoText() == _COMMAND_TEXT
    _assert_composed(window._redo_action, redo_prefix, "Alt+R", _COMMAND_TEXT, code)
    assert _plain(window._undo_action.text()) == _plain(undo_prefix)
    assert _mnemonic(window._undo_action.text()) == "Alt+U"

    _stack(window).redo()
    assert window._undo_group.undoText() == _COMMAND_TEXT
    _assert_composed(window._undo_action, undo_prefix, "Alt+U", _COMMAND_TEXT, code)
    assert _plain(window._redo_action.text()) == _plain(redo_prefix)


@pytest.mark.parametrize("code", LANGUAGES)
def test_a_command_on_the_stack_survives_a_live_switch(make_window, code):
    """REQ-L10N-UI-001, REQ-L10N-UI-004: the prefix changes language, the command stays.

    Built in English with a command pushed (``&Undo <command>``), then switched
    to the language with the command still on the stack: the prefix is the new
    language's, and the part after it equals the group's own ``undoText()``.
    That is all that is asserted about the command part (it keeps the language
    it was pushed in). After an undo the redo side follows the same rule, and
    switching back restores the English prefix.
    """
    window = make_window()
    undo_prefix, redo_prefix = _expected_prefixes(code)
    _push_command(window)
    assert window._undo_action.text() == f"{_UNDO_SOURCE} {_COMMAND_TEXT}"

    _switch(window, code)
    command_part = window._undo_group.undoText()
    _assert_composed(window._undo_action, undo_prefix, "Alt+U", command_part, code)
    assert _plain(window._redo_action.text()) == _plain(redo_prefix)

    _stack(window).undo()
    _switch(window, FALLBACK_LANGUAGE)
    assert window._redo_action.text() == f"{_REDO_SOURCE} {_COMMAND_TEXT}"
    _switch(window, code)
    command_part = window._undo_group.redoText()
    _assert_composed(window._redo_action, redo_prefix, "Alt+R", command_part, code)
    assert _plain(window._undo_action.text()) == _plain(undo_prefix)

    _switch(window, FALLBACK_LANGUAGE)
    assert window._redo_action.text() == f"{_REDO_SOURCE} {_COMMAND_TEXT}"
    assert window._undo_action.text() == _UNDO_SOURCE


def _assert_tooltips(window: Main_Window, code: str, where: str) -> None:
    """Neither tooltip is the English word, and each follows its action's text.

    The tooltip is Qt's own derivation from the action text, so it equals that
    text with the access-key presentation removed.
    """
    for action, english in (
        (window._undo_action, "Undo"),
        (window._redo_action, "Redo"),
    ):
        tip = action.toolTip()
        assert _plain(tip) == _plain(
            action.text()
        ), f"{code} {where}: tooltip {tip!r} does not follow text {action.text()!r}"
        if code != FALLBACK_LANGUAGE:
            assert tip != english, f"{code} {where}: tooltip is {english!r}"


@pytest.mark.parametrize("code", LANGUAGES)
def test_undo_and_redo_tooltips_at_start_up(make_window, code):
    """REQ-L10N-UI-002: the start-up language shows in the Undo and Redo tooltips.

    In every language but English neither tooltip equals ``Undo`` or ``Redo``,
    with nothing on the stack and with a command on it.
    """
    window = make_window(code)
    _assert_tooltips(window, code, "at start-up")
    _push_command(window)
    _assert_tooltips(window, code, "with a command")


@pytest.mark.parametrize("code", LANGUAGES)
def test_undo_and_redo_tooltips_follow_a_live_switch(make_window, code):
    """REQ-L10N-UI-001: a live switch re-sets the Undo and Redo tooltips.

    Built in English, switched to the language: in every language but English
    neither tooltip equals ``Undo`` or ``Redo``, with nothing on the stack and
    with a command on it, and switching back restores the English tooltips.
    """
    window = make_window()
    _switch(window, code)
    _assert_tooltips(window, code, "after a switch")
    _push_command(window)
    _assert_tooltips(window, code, "after a switch, with a command")
    _switch(window, FALLBACK_LANGUAGE)
    _assert_tooltips(window, FALLBACK_LANGUAGE, "after switching back")
    assert window._undo_action.toolTip() == f"Undo {_COMMAND_TEXT}"


# --------------------------------------------------------------------------- #
# The colour wheel's preview name                                             #
# --------------------------------------------------------------------------- #


def _wheel_name(widget: Colour_Wheel_Widget) -> str:
    """Return the preview's accessible name (the widget's observable text)."""
    return widget._preview.accessibleName()


@pytest.mark.parametrize("code", LANGUAGES)
def test_the_preview_name_is_in_the_language_it_was_built_in(qtbot, language, code):
    """REQ-L10N-UI-002: a wheel built in the language names its colour in it.

    The name is the catalogue's ``Current colour %1`` with the colour's hex text
    in place of ``%1``, both for the colour the widget starts with and for one set
    afterwards.
    """
    language(code)
    _assert_language_in_force(code)
    template = _catalogue_text(code, _WHEEL, _WHEEL_SOURCE)
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)

    first = _hex_of(widget.current_rgba())
    assert _wheel_name(widget) == template.replace("%1", first)
    widget.set_color(QColor(18, 52, 86))
    second = _hex_of(widget.current_rgba())
    assert second != first, "the colour did not change"
    assert _wheel_name(widget) == template.replace("%1", second)
    if code != FALLBACK_LANGUAGE:
        assert not _wheel_name(widget).startswith("Current colour")


@pytest.mark.parametrize("code", LANGUAGES)
def test_the_preview_name_follows_a_live_switch(qtbot, language, code):
    """REQ-L10N-UI-001: a live switch re-names the preview with the same colour.

    Built in English with a colour set, switched to the language, then back: the
    name is the catalogue text with the unchanged hex, and the colour itself does
    not move.
    """
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)
    widget.set_color(QColor(18, 52, 86))
    colour = widget.current_rgba()
    hex_text = _hex_of(colour)
    assert _wheel_name(widget) == _WHEEL_SOURCE.replace("%1", hex_text)

    language(code)
    QApplication.processEvents()
    _assert_language_in_force(code)
    template = _catalogue_text(code, _WHEEL, _WHEEL_SOURCE)
    assert _wheel_name(widget) == template.replace("%1", hex_text)
    assert widget.current_rgba() == colour
    if code != FALLBACK_LANGUAGE:
        assert not _wheel_name(widget).startswith("Current colour")

    language(FALLBACK_LANGUAGE)
    QApplication.processEvents()
    assert _wheel_name(widget) == _WHEEL_SOURCE.replace("%1", hex_text)


# --------------------------------------------------------------------------- #
# The timelapse reason label                                                  #
# --------------------------------------------------------------------------- #


def _shown_controls(qtbot) -> Timelapse_Controls:
    """Return a shown ``Timelapse_Controls`` with nothing recorded."""
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    controls.show()
    qtbot.waitExposed(controls)
    return controls


def _assert_reason(controls: Timelapse_Controls, expected: str, where: str) -> None:
    """The reason label shows ``expected``, exposed to assistive technology too."""
    label = controls._reason_label
    assert (
        label.text() == expected
    ), f"{where}: shows {label.text()!r}, not {expected!r}"
    assert label.accessibleDescription() == expected, (
        f"{where}: description is {label.accessibleDescription()!r}, "
        f"not {expected!r}"
    )


@pytest.mark.parametrize("code", LANGUAGES)
def test_the_reason_label_is_in_the_language_it_was_built_in(qtbot, language, code):
    """REQ-L10N-UI-002: with nothing recorded the reason reads in the start-up language.

    Text and accessible description both equal the catalogue's sentence, and the
    label is shown.
    """
    language(code)
    _assert_language_in_force(code)
    expected = _catalogue_text(code, _TIMELAPSE, _NOTHING_SOURCE)
    controls = _shown_controls(qtbot)

    _assert_reason(controls, expected, f"{code} at start-up")
    assert not controls._reason_label.isHidden()
    if code != FALLBACK_LANGUAGE:
        assert controls._reason_label.text() != _NOTHING_SOURCE


@pytest.mark.parametrize("code", LANGUAGES)
def test_the_reason_label_follows_a_live_switch_and_back(qtbot, language, code):
    """REQ-L10N-UI-001: a live switch re-sets the reason and its description.

    Built in English with nothing recorded, switched to the language, then back:
    text and accessible description follow each time, the label stays visible and
    the play button keeps its state.
    """
    controls = _shown_controls(qtbot)
    _assert_reason(controls, _NOTHING_SOURCE, "English at start-up")
    play_enabled = controls._play_button.isEnabled()

    language(code)
    QApplication.processEvents()
    _assert_language_in_force(code)
    expected = _catalogue_text(code, _TIMELAPSE, _NOTHING_SOURCE)
    _assert_reason(controls, expected, f"{code} after a switch")
    assert not controls._reason_label.isHidden()
    assert controls._play_button.isEnabled() == play_enabled
    if code != FALLBACK_LANGUAGE:
        assert controls._reason_label.text() != _NOTHING_SOURCE

    language(FALLBACK_LANGUAGE)
    QApplication.processEvents()
    _assert_reason(controls, _NOTHING_SOURCE, "English after switching back")
    assert not controls._reason_label.isHidden()
    assert controls._play_button.isEnabled() == play_enabled


def _raise_drop_notice(qtbot, make_view) -> Timelapse_Controls:
    """Raise a frames-dropped notice the way the playback tests raise it.

    Records four real edits on a real canvas view, undoes three of them and makes
    one new edit, which discards the three undone frames. The ``framesDropped``
    observer is connected before the edit; it must report the count.
    """
    view, scene, stack = make_view()
    prepare_for_click(view)
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    controls.show()
    qtbot.waitExposed(controls)
    document = scene._document
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls._record_button.setChecked(True)
    for offset in range(4):
        view.set_active_color((40 + offset * 50, 90, 220, 255))
        click_pixel(view, 5 + offset * 10, 5)
    assert controls.frame_count() == 4
    for _ in range(_DROPPED_COUNT):
        stack.undo()

    view.set_active_color((240, 220, 40, 255))
    with qtbot.waitSignal(controls.framesDropped, timeout=_SETTLE_TIMEOUT_MS) as seen:
        click_pixel(view, 60, 60)
    assert seen.args == [_DROPPED_COUNT]
    return controls


@pytest.mark.parametrize("code", LANGUAGES)
def test_a_showing_drop_notice_is_re_rendered_with_its_count(
    qtbot, language, make_view, code
):
    """REQ-L10N-UI-001: a switch re-renders a notice already showing, same count.

    The notice is raised in English (three frames dropped). After a switch to the
    language it is the catalogue's plural form for three, with the same count and
    the label still visible, and its accessible description is the same text.
    Switching back restores the English notice. The play button and the recorded
    frame count do not change.
    """
    controls = _raise_drop_notice(qtbot, make_view)
    english = _numerus_text(FALLBACK_LANGUAGE, _TIMELAPSE, _DROPPED_SOURCE, 3)
    _assert_reason(controls, english, "English notice")
    play_enabled = controls._play_button.isEnabled()
    frames = controls.frame_count()

    language(code)
    QApplication.processEvents()
    _assert_language_in_force(code)
    expected = _numerus_text(code, _TIMELAPSE, _DROPPED_SOURCE, _DROPPED_COUNT)
    assert str(_DROPPED_COUNT) in expected, f"{code}: the count is not in {expected!r}"
    _assert_reason(controls, expected, f"{code} notice after a switch")
    assert not controls._reason_label.isHidden()
    assert controls._play_button.isEnabled() == play_enabled
    assert controls.frame_count() == frames
    if code != FALLBACK_LANGUAGE:
        assert controls._reason_label.text() != english

    language(FALLBACK_LANGUAGE)
    QApplication.processEvents()
    _assert_reason(controls, english, "English notice after switching back")
    assert not controls._reason_label.isHidden()


@pytest.mark.parametrize("code", LANGUAGES)
def test_a_drop_notice_raised_in_the_language_reads_in_it(
    qtbot, language, make_view, code
):
    """REQ-L10N-UI-002: a notice raised while the language is in force reads in it.

    The language is installed first, then three frames are dropped: the label
    shows the catalogue's plural form for three, and its description matches.
    """
    language(code)
    _assert_language_in_force(code)
    controls = _raise_drop_notice(qtbot, make_view)

    expected = _numerus_text(code, _TIMELAPSE, _DROPPED_SOURCE, _DROPPED_COUNT)
    _assert_reason(controls, expected, f"{code} notice raised in the language")
    assert not controls._reason_label.isHidden()
