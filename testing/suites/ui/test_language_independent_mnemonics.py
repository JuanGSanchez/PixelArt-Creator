"""Language-independent keyboard mnemonics regression tests (M1, A3-A6).

"Shortcuts are independent of language" (U4): a translated menu/action title
always keeps the mnemonic LETTER of its ENGLISH source, never a letter chosen
for the translation's own wording. Enforced centrally by
``_MnemonicTranslator``/``apply_source_mnemonic`` in ``ui/i18n.py`` -- zero
call-site changes anywhere ``tr()`` is used.

M1 -- a pure-function value table for ``apply_source_mnemonic`` (Qt-free,
unit-testable directly, per its own docstring).

A3 -- on a live ``Main_Window``, for English and Spanish: every top-level
menubar title and every item in every menu (menus reachable from the
menubar, recursively) has a mnemonic that is UNIQUE within its own menu; and
in Spanish, every displayed mnemonic letter equals the one marked in the
English source. Additionally: the mnemonic wrapper never changes VISIBLE
wording -- for every node, the final displayed text (``QAction.iconText()``,
mnemonic markers stripped Qt's own way) equals the untouched translation's
own displayed text, at most with a trailing ``" (X)"`` fallback suffix
appended (the Windows-convention case, U4/M1's own documented example).

A4 -- in Spanish, Help's title reads ``Ayuda (&H)`` (English has no letter
'H' in "Ayuda", so the ``(&H)`` fallback applies -- see
``apply_source_mnemonic``'s own docstring example); in English, ``&Help``.

A5 -- the Aids menu's title: ``Visual Ai&ds`` in English, ``Ayu&das
visuales`` in Spanish (U3's rename).

A6 -- the User Guide (F1) action's shortcut context is
``Qt.ShortcutContext.ApplicationShortcut`` (not the default
``WindowShortcut``), so F1 reaches it from any top-level of the application,
not only the main window itself.

**Known harness artifact (measured this session, NOT a product defect on a
real display)**: performing a FULL recursive walk of every ``QMenu`` reachable
from a live ``Main_Window``'s menu bar BEFORE that same process ever asks
that window's ``LanguageManager`` to switch language reproducibly triggers a
``SystemError`` from mutually-recursive ``QObject.eventFilter`` overrides
between ``ui/shortcut_focus_guard.py`` and ``ui/colour_hub_menu.py`` once the
switch's posted ``LanguageChange`` event is processed -- reproduced directly
against this branch's code, offscreen, with a throwaway script, independent
of pytest/pytest-qt. Switching language TWICE on one live window (touching
its menus in between) reproduces the same crash for the same reason. Doing
the switch FIRST -- before any menu is walked -- and walking only AFTERWARDS
was verified NOT to reproduce it. Every Spanish test below therefore switches
language as the very first interaction with its window, and every English/
Spanish comparison in this module is done WITHOUT ever having two live
``Main_Window`` instances (or one window switched twice) in the same process:
the English reference tree, and the raw (mnemonic-wrapper-bypassed) Spanish
display-text reference tree, are each captured in their own isolated
subprocess instead.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.i18n import _source_mnemonic_letter, apply_source_mnemonic
from pixelart_creator.ui.main_window import Main_Window


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _switch_to_spanish_first(win: Main_Window) -> None:
    """Switch ``win`` to Spanish as the FIRST interaction with it.

    See the module docstring's "known harness artifact": no menu of ``win``
    may be touched (no ``.menuBar()``/``.actions()``/``.menu()`` walk) before
    this call, and this must be the ONLY switch this window ever performs.
    """
    assert win._language_manager.set_language("es") is True
    QApplication.processEvents()


# =========================================================================== #
# M1 -- apply_source_mnemonic pure-function value table                       #
# =========================================================================== #


def test_m1_letter_present_marks_first_case_insensitive_occurrence():
    """M1: the source's mnemonic letter, found in the translation, is marked
    at its FIRST case-insensitive occurrence."""
    assert apply_source_mnemonic("&File", "Perfil") == "Per&fil"


def test_m1_letter_absent_appends_windows_convention_fallback():
    """M1: the source's letter absent from the translation appends
    ``" (&X)"`` (the Windows convention; matches the module's own docstring
    example)."""
    assert apply_source_mnemonic("&Help", "Ayuda") == "Ayuda (&H)"


def test_m1_translation_carrying_a_different_marker_is_moved():
    """M1: a translation's OWN mnemonic marker (on a different letter than
    the source's) is stripped and re-marked at the source's letter."""
    assert apply_source_mnemonic("&File", "&Preferencia") == "Pre&ferencia"


def test_m1_source_literal_double_ampersand_is_never_read_as_a_marker():
    """M1: a literal ``&&`` in the SOURCE is never mistaken for a mnemonic
    marker -- confirmed both with no real marker at all, and with a real
    marker elsewhere in the same string."""
    assert _source_mnemonic_letter("Save && Exit") is None
    assert _source_mnemonic_letter("&Save && Exit") == "S"


def test_m1_literal_double_ampersand_after_the_marker_keeps_it_working(qapp):
    """M1: when the translation's literal ``&&`` sits AFTER the position the
    real marker lands on, the literal survives ESCAPED (``&&``, still two
    characters) rather than collapsed to a bare single ``&``. Two
    independent checks, both required: Qt's own mnemonic resolution
    (``QKeySequence.mnemonic``, the authoritative parser -- never guessed)
    resolves to the source's letter, AND the DISPLAYED text
    (``QAction.iconText()`` -- what the user actually reads, mnemonic
    markers stripped Qt's own way) shows the literal ampersand rather than
    silently losing it. A bare, un-escaped single ``&`` left in the
    returned string is swallowed entirely by Qt's renderer -- see the
    ``&&``-before-the-marker test below for the measured proof of exactly
    that failure mode."""
    result = apply_source_mnemonic("&File", "Perfil && Cosas")
    assert result == "Per&fil && Cosas"
    assert (
        QKeySequence.mnemonic(result).toString()
        == QKeySequence.mnemonic("&File").toString()
        == "Alt+F"
    )
    assert QAction(result).iconText() == "Perfil & Cosas"


def test_m1_literal_double_ampersand_before_the_marker_stays_correct(qapp):
    """M1 -- regression test for a defect found and FIXED during this job
    (``ui/i18n.py``'s ``apply_source_mnemonic``/``_strip_mnemonic_markers``).

    Before the fix, a literal ``&&`` in the TRANSLATION was collapsed to a
    single display ``&`` without ever being re-escaped back to ``&&`` before
    Qt saw the string. When that collapsed leftover ``&`` ended up BEFORE
    the newly-inserted real marker, TWO things broke at once: Qt's own
    ``QKeySequence.mnemonic()`` parser (left-to-right, first ``&<char>``
    pair wins) resolved the mnemonic to the leftover ampersand's next
    character instead of the intended letter, AND the displayed text
    (``QAction.iconText()``) silently lost that ampersand from view
    entirely (Qt strips a bare, un-escaped single ``&`` and shows the next
    character bare -- verified directly: ``QAction("Guías & &Reglas").
    iconText() == "Guías  Reglas"``, note the double space where the ``&``
    used to be).

    Real, live instance of this exact defect (found via the ``A3`` menu-tree
    comparison test below, not invented for this test): the Aids menu's
    "Guides && &Rulers" item. English resolves to ``Alt+R``; the Spanish
    translation ("Guías && Reglas") measured ``Alt+Space`` before the fix.
    Both assertions below now hold -- reproduced at the pure-function level
    with the exact production strings, so a future regression is caught
    without a live window.
    """
    source = "Guides && &Rulers"
    translation = "Guías && Reglas"
    result = apply_source_mnemonic(source, translation)

    source_mnemonic = QKeySequence.mnemonic(source).toString()
    assert source_mnemonic == "Alt+R"  # the English source itself is correct

    result_mnemonic = QKeySequence.mnemonic(result).toString()
    assert result_mnemonic == source_mnemonic, (
        f"{translation!r} -> {result!r} resolves to Qt mnemonic "
        f"{result_mnemonic!r}, not the source's {source_mnemonic!r}"
    )
    assert QAction(result).iconText() == "Guías & Reglas", (
        f"{translation!r} -> {result!r} displays as "
        f"{QAction(result).iconText()!r}, not the expected 'Guías & Reglas' "
        "-- the literal '&&' was lost from the DISPLAYED text"
    )


def test_m1_source_without_a_mnemonic_leaves_translation_unchanged():
    """M1: a source with no ``&`` marker at all has nothing to enforce."""
    assert apply_source_mnemonic("Plain text", "Texto simple") == "Texto simple"


def test_m1_empty_translation_returned_unchanged():
    """M1: an empty/untranslated translation is returned unchanged (Qt then
    falls back to the source string itself)."""
    assert apply_source_mnemonic("&File", "") == ""


# =========================================================================== #
# A3 -- unique mnemonics per menu, both languages; A4/A5 title checks         #
# =========================================================================== #


def _assert_unique_mnemonics_recursive(actions: List[QAction], context: str) -> None:
    """Assert every non-separator action's mnemonic is unique WITHIN its own
    menu (case-insensitive), then recurse into every submenu with a FRESH
    per-menu tracker -- uniqueness is scoped to one menu, never global."""
    seen: Dict[str, str] = {}
    for action in actions:
        if action.isSeparator():
            continue
        letter = _source_mnemonic_letter(action.text())
        if letter is not None:
            key = letter.lower()
            assert key not in seen, (
                f"{context}: duplicate mnemonic {letter!r} on both "
                f"{seen.get(key)!r} and {action.text()!r}"
            )
            seen[key] = action.text()
        menu = action.menu()
        if menu is not None:
            _assert_unique_mnemonics_recursive(
                menu.actions(), f"{context} > {action.text()!r}"
            )


def _mnemonic_tree(actions: List[QAction], path: List[int], out: Dict[str, Optional[str]]) -> None:
    """Record ``path -> mnemonic letter`` for every non-separator action,
    recursively, keyed by a dotted index path (structural position) -- the
    same key scheme the isolated subprocess dump below uses, so the two can
    be compared node-for-node."""
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = _source_mnemonic_letter(
            action.text()
        )
        menu = action.menu()
        if menu is not None:
            _mnemonic_tree(menu.actions(), node_path, out)


# The isolated-subprocess dump script (see the module docstring): builds a
# fresh, English, NEVER-SWITCHED Main_Window and prints its mnemonic tree as
# JSON. Run in a separate process so no shared QApplication / event-filter
# state can ever exist between this reference tree and a Spanish-switched
# window built in THIS test process (the known harness artifact).
_EN_REFERENCE_DUMP_SCRIPT = r"""
import json, os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QLocale
QLocale.system = staticmethod(
    lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
)
app = QApplication([])
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.i18n import _source_mnemonic_letter

def walk(actions, path, out):
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = _source_mnemonic_letter(
            action.text()
        )
        menu = action.menu()
        if menu is not None:
            walk(menu.actions(), node_path, out)

win = Main_Window()
out = {}
walk(win.menuBar().actions(), [], out)
print(json.dumps(out))
"""


def _dump_en_reference_tree() -> Dict[str, Optional[str]]:
    """Return the English-source mnemonic tree, built in an isolated
    subprocess (see the module docstring's "known harness artifact")."""
    result = subprocess.run(
        [sys.executable, "-c", _EN_REFERENCE_DUMP_SCRIPT],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"English reference dump failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


# The RAW (unwrapped) Spanish dump script (see A3's module-docstring note on
# the display check): monkeypatches ``apply_source_mnemonic`` to the
# identity function BEFORE any translation happens, so every action's text
# is set from the .qm catalogue's OWN translation, completely undecorated by
# the mnemonic-enforcement wrapper -- the "what would the user see with no
# wrapper at all" baseline. Run in its own isolated subprocess for the SAME
# reason the English reference is (the known harness artifact): this process
# performs its own single "switch first, then walk", and never coexists with
# the live, WRAPPED Spanish window this test builds in-process.
_ES_RAW_REFERENCE_DUMP_SCRIPT = r"""
import json, os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QAction
app = QApplication([])
import pixelart_creator.ui.i18n as i18n_module
i18n_module.apply_source_mnemonic = lambda source, translation: translation
from pixelart_creator.ui.main_window import Main_Window

def walk(actions, path, out):
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = QAction(action.text()).iconText()
        menu = action.menu()
        if menu is not None:
            walk(menu.actions(), node_path, out)

win = Main_Window()
assert win._language_manager.set_language("es") is True
QApplication.processEvents()
out = {}
walk(win.menuBar().actions(), [], out)
print(json.dumps(out))
"""


def _dump_es_raw_display_tree() -> Dict[str, str]:
    """Return the RAW (mnemonic-wrapper-bypassed) Spanish displayed-text
    tree, built in an isolated subprocess."""
    result = subprocess.run(
        [sys.executable, "-c", _ES_RAW_REFERENCE_DUMP_SCRIPT],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Raw Spanish display dump failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


#: A trailing " (X)" Windows-convention fallback suffix (single letter,
#: matching ``apply_source_mnemonic``'s own documented ``" (&X)"`` -- here
#: already Qt-mnemonic-stripped to ``" (X)"`` by ``iconText()``).
_TRAILING_FALLBACK_SUFFIX = re.compile(r" \([A-Za-z]\)$")


def _strip_trailing_fallback_suffix(text: str) -> str:
    """Drop at most one trailing ``" (X)"`` fallback suffix, if present."""
    return _TRAILING_FALLBACK_SUFFIX.sub("", text)


def _icon_text_tree(actions: List[QAction], path: List[int], out: Dict[str, str]) -> None:
    """Record ``path -> iconText()`` (the DISPLAYED text, mnemonic markers
    stripped Qt's own way) for every non-separator action, recursively."""
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = action.iconText()
        menu = action.menu()
        if menu is not None:
            _icon_text_tree(menu.actions(), node_path, out)


def test_a3_en_menu_mnemonics_are_unique_within_each_menu(qtbot):
    """A3 (en, uniqueness): every top-level title and every item's mnemonic
    is unique within its own menu, in English."""
    win = _window(qtbot)
    _assert_unique_mnemonics_recursive(win.menuBar().actions(), "menubar")


def test_a3_es_menu_mnemonics_are_unique_within_each_menu(qtbot):
    """A3 (es, uniqueness): same check, in Spanish -- the language is
    switched FIRST (module docstring), then the whole tree is checked."""
    win = _window(qtbot)
    _switch_to_spanish_first(win)
    _assert_unique_mnemonics_recursive(win.menuBar().actions(), "menubar")


def test_a3_es_mnemonics_equal_the_english_source(qtbot):
    """A3 (es, U4/M1): every Spanish mnemonic letter equals the one marked in
    the English source, at the SAME structural position -- compared against
    the isolated-subprocess English reference tree (module docstring).

    Also (module docstring's display-check clause): the mnemonic wrapper
    never changes VISIBLE wording. For every node, the live (wrapped)
    Spanish window's displayed text equals the RAW (unwrapped) Spanish
    translation's own displayed text, at most with one trailing ``" (X)"``
    fallback suffix appended -- the wrapper is entitled to add/move an
    underline and, in the letter-absent case, append the Windows-convention
    fallback; it is never entitled to otherwise alter what the user reads.
    """
    win = _window(qtbot)
    _switch_to_spanish_first(win)

    es_tree: Dict[str, Optional[str]] = {}
    _mnemonic_tree(win.menuBar().actions(), [], es_tree)
    es_display_tree: Dict[str, str] = {}
    _icon_text_tree(win.menuBar().actions(), [], es_display_tree)

    en_tree = _dump_en_reference_tree()

    assert set(es_tree) == set(en_tree), (
        "menu structure differs between the live es window and the en "
        f"reference: es-only={set(es_tree) - set(en_tree)!r} "
        f"en-only={set(en_tree) - set(es_tree)!r}"
    )
    mismatches = [
        (path, en_tree[path], es_tree[path])
        for path in en_tree
        if (en_tree[path] or "").lower() != (es_tree[path] or "").lower()
    ]
    assert not mismatches, f"es mnemonic != en source mnemonic at: {mismatches}"
    # Sanity: this really compared a non-trivial tree, not an empty one.
    assert len(en_tree) > 100

    es_raw_display_tree = _dump_es_raw_display_tree()
    assert set(es_display_tree) == set(es_raw_display_tree), (
        "menu structure differs between the live (wrapped) es window and "
        "the raw (unwrapped) es reference: "
        f"live-only={set(es_display_tree) - set(es_raw_display_tree)!r} "
        f"raw-only={set(es_raw_display_tree) - set(es_display_tree)!r}"
    )
    display_mismatches = [
        (path, es_raw_display_tree[path], es_display_tree[path])
        for path in es_raw_display_tree
        if _strip_trailing_fallback_suffix(es_display_tree[path])
        != es_raw_display_tree[path]
    ]
    assert not display_mismatches, (
        "the mnemonic wrapper changed VISIBLE wording (beyond at most one "
        f"trailing ' (X)' fallback suffix) at: {display_mismatches}"
    )


def test_a4_help_title_en(qtbot):
    """A4: the Help menu's English title is ``&Help``."""
    win = _window(qtbot)
    assert win._help_menu.title() == "&Help"


def test_a4_help_title_es(qtbot):
    """A4: the Help menu's Spanish title is ``Ayuda (&H)`` -- "Ayuda" has no
    letter 'H', so ``apply_source_mnemonic``'s Windows-convention fallback
    applies (matches its own docstring example, verbatim)."""
    win = _window(qtbot)
    _switch_to_spanish_first(win)
    assert win._help_menu.title() == "Ayuda (&H)"


def test_a4_alt_h_structural_equivalent_opens_help_in_spanish(qtbot):
    """A4 (keyboard clause), structural half only.

    The literal Alt+H keystroke path cannot be driven headlessly: the
    offscreen Qt platform does not engage Qt's native menu-popup grab, the
    SAME documented limitation ``test_about_dialog.py``'s MC-3 recorded for
    Alt+H on this exact Help menu (verified there against a KNOWN-TRUE,
    already-shipped control before concluding it was untestable headless --
    not re-verified again here, the same limitation applies unchanged). The
    structural equivalent asserted here is what "Alt+H opens Help" actually
    depends on: the Help menu's own mnemonic resolves to 'H', and no other
    top-level menu shares it -- so a real Alt+H, on a platform that CAN
    engage the grab, has exactly one target.
    """
    win = _window(qtbot)
    _switch_to_spanish_first(win)

    help_letter = _source_mnemonic_letter(win._help_menu.title())
    assert help_letter is not None and help_letter.upper() == "H"

    top_level = [a for a in win.menuBar().actions() if not a.isSeparator()]
    upper_letters = [
        (ltr.upper() if (ltr := _source_mnemonic_letter(a.text())) else None)
        for a in top_level
    ]
    assert upper_letters.count("H") == 1


def test_a5_aids_menu_title_en(qtbot):
    """A5: the Aids menu's English title is ``Visual Ai&ds`` (U3's rename)."""
    win = _window(qtbot)
    assert win._aids_menu.title() == "Visual Ai&ds"


def test_a5_aids_menu_title_es(qtbot):
    """A5: the Aids menu's Spanish title renders as ``Ayu&das visuales``."""
    win = _window(qtbot)
    _switch_to_spanish_first(win)
    assert win._aids_menu.title() == "Ayu&das visuales"


# =========================================================================== #
# A6 -- F1 / User Guide: ApplicationShortcut context                         #
# =========================================================================== #


def test_a6_user_guide_shortcut_context_is_application_wide(qtbot):
    """A6: F1's shortcut context is ``ApplicationShortcut`` (not the default
    ``WindowShortcut``), so it reaches the action from any top-level of the
    application, and the shortcut itself is still plain F1."""
    win = _window(qtbot)
    assert (
        win._user_guide_action.shortcutContext()
        == Qt.ShortcutContext.ApplicationShortcut
    )
    assert win._user_guide_action.shortcut() == QKeySequence(Qt.Key.Key_F1)
