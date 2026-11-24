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

The access-key oracle for every shipped language (REQ-L10N-UI-004,
SC-L10N-UI-004-1 to -4). The last section of this module generalises A3 and A4
from Spanish to every language the product ships, discovered from the compiled
catalogues and not named here:

* one isolated subprocess per language and per mode (the existing pattern, for
  the reason the harness artifact above gives), run one at a time, so no more
  than the pytest process and one child are ever alive; the English reference,
  the language's own display text (wrapper bypassed) and the language's real
  tree are each read in their own child, and a child's result is kept for the
  rest of the process, because the autouse ``theme`` parameter runs every test
  twice and an access key does not depend on the theme;
* the oracle prints the languages it discovered and, per language, its node
  count, and **fails with ``N of 8 required languages were examined`` when it
  discovers fewer than eight** (SC-L10N-UI-004-2, shown failing on a folder that
  holds only the English and Spanish catalogues);
* the comparator is a pure function, shown failing on a changed letter, a
  duplicate letter, an altered wording, a doubled suffix, a missing node and an
  empty tree;
* the M1 value table gains Japanese, Simplified Chinese, Korean and Russian
  rows (SC-L10N-UI-004-3, -4); the suffix pattern ``_TRAILING_FALLBACK_SUFFIX``
  is the one this module has always carried and is not edited;
* the children never touch the user's own settings or configuration folder: each
  redirects ``QSettings`` and the application-config location into a scratch
  folder under pytest's own base temp.

How macOS presents the appended ``(&X)`` cannot be measured on a
non-macOS host: ``test_reports_qts_reading_of_the_appended_suffix`` prints, on
every platform, what Qt itself reads from the suffix, so that the macOS CI log
carries the measurement. It does not see a native macOS menu being drawn.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple, cast

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, qt_set_sequence_auto_mnemonic
from PySide6.QtWidgets import QApplication, QMenu

import pixelart_creator.ui.i18n as i18n_module
from pixelart_creator.ui.i18n import (
    _CATALOGUE_PREFIX,
    _CATALOGUE_SUFFIX,
    FALLBACK_LANGUAGE,
    LanguageManager,
    _default_translations_dir,
    _source_mnemonic_letter,
    apply_source_mnemonic,
)
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


def test_m1_literal_double_ampersand_after_the_marker_keeps_it_working(
    qapp, _qt_auto_mnemonic_enabled
):
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


def test_m1_literal_double_ampersand_before_the_marker_stays_correct(
    qapp, _qt_auto_mnemonic_enabled
):
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
        menu = cast(Optional[QMenu], action.menu())
        if menu is not None:
            _assert_unique_mnemonics_recursive(
                menu.actions(), f"{context} > {action.text()!r}"
            )


def _mnemonic_tree(
    actions: List[QAction], path: List[int], out: Dict[str, Optional[str]]
) -> None:
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
        menu = cast(Optional[QMenu], action.menu())
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


def _icon_text_tree(
    actions: List[QAction], path: List[int], out: Dict[str, str]
) -> None:
    """Record ``path -> iconText()`` (the DISPLAYED text, mnemonic markers
    stripped Qt's own way) for every non-separator action, recursively."""
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = action.iconText()
        menu = cast(Optional[QMenu], action.menu())
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


# =========================================================================== #
# The access-key oracle for every shipped language                            #
# =========================================================================== #

#: How many languages the oracle must examine (REQ-L10N-UI-004: eight).
REQUIRED_LANGUAGE_COUNT = 8

#: Seconds one isolated child may take: one window, one switch, one walk.
_CHILD_TIMEOUT_SECONDS = 100

#: One node of a menu tree: its source-letter reading and the text a user reads.
Node = Dict[str, Optional[str]]
#: A menu tree, keyed by the dotted index path of each non-separator action.
Tree = Dict[str, Node]


class _Dump(NamedTuple):
    """What one isolated child reports: its menu tree and the Help title."""

    nodes: Tree
    help_title: str


def _shipped_language_codes(translations_dir: Optional[Path] = None) -> List[str]:
    """Return the codes of the compiled catalogues in ``translations_dir``.

    English first, then every ``pixelart_<code>.qm`` in file-name order -- the
    product's own rule, read here without Qt so that the parametrisation below
    can be built when the module is collected. ``test_oracle_discovers_*``
    compares it with ``LanguageManager.available_languages()``, so the two
    cannot drift apart unnoticed.
    """
    folder = (
        translations_dir
        if translations_dir is not None
        else _default_translations_dir()
    )
    codes = [FALLBACK_LANGUAGE]
    if folder.is_dir():
        for qm in sorted(folder.glob(f"{_CATALOGUE_PREFIX}*{_CATALOGUE_SUFFIX}")):
            code = qm.stem[len(_CATALOGUE_PREFIX) :]
            if code and code not in codes:
                codes.append(code)
    return codes


_SHIPPED_CODES = _shipped_language_codes()


def _discover_languages(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    translations_dir: Optional[Path] = None,
) -> List[str]:
    """Return the languages the product itself finds in ``translations_dir``.

    Asked of a real ``LanguageManager``, which registers itself as the
    application's manager when built; ``monkeypatch`` puts the registry back at
    teardown, so asking leaves nothing changed. No language is switched.
    """
    monkeypatch.setattr(i18n_module, "_APP_MANAGER", i18n_module._APP_MANAGER)
    manager = LanguageManager(qapp, translations_dir=translations_dir)
    return manager.available_languages()


def _assert_enough_languages(codes: Sequence[str]) -> None:
    """Fail, stating ``N of 8``, unless at least eight languages were found."""
    assert len(codes) >= REQUIRED_LANGUAGE_COUNT, (
        f"{len(codes)} of {REQUIRED_LANGUAGE_COUNT} required languages were "
        f"examined: {list(codes)!r}"
    )


# One child per language and mode, in its own process (module docstring). It
# redirects QSettings and the application-config folder into the scratch folder
# it is given (argv[3]) before anything reads either, so it never reads or
# writes the user's own store, and pins the system locale to English as the UI
# suite's conftest does. mode "raw" replaces apply_source_mnemonic with the
# identity BEFORE the window exists, so every text is the catalogue's own.
_LANGUAGE_DUMP_SCRIPT = r"""
import json, os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
code, mode, scratch = sys.argv[1], sys.argv[2], sys.argv[3]
from PySide6.QtCore import QCoreApplication, QLocale, QSettings, QStandardPaths
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication
QLocale.system = staticmethod(
    lambda: QLocale(QLocale.Language.English, QLocale.Country.UnitedStates)
)
for fmt in (QSettings.Format.NativeFormat, QSettings.Format.IniFormat):
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(fmt, scope, scratch)
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
config_dir = os.path.join(scratch, "appconfig")
os.makedirs(config_dir, exist_ok=True)
QStandardPaths.writableLocation = staticmethod(lambda *a, **k: config_dir)
from pixelart_creator.ui.app import APPLICATION_NAME, ORGANIZATION_NAME
QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
QCoreApplication.setApplicationName(APPLICATION_NAME)
app = QApplication([])
import pixelart_creator.ui.i18n as i18n_module
if mode == "raw":
    i18n_module.apply_source_mnemonic = lambda source, translation: translation
from pixelart_creator.ui.i18n import _source_mnemonic_letter
from pixelart_creator.ui.main_window import Main_Window

def walk(actions, path, out):
    for index, action in enumerate(actions):
        if action.isSeparator():
            continue
        node_path = path + [index]
        out[".".join(str(i) for i in node_path)] = {
            "letter": _source_mnemonic_letter(action.text()),
            "display": QAction(action.text()).iconText(),
        }
        menu = action.menu()
        if menu is not None:
            walk(menu.actions(), node_path, out)

win = Main_Window()
if code != "en":
    assert win._language_manager.set_language(code) is True
    QApplication.processEvents()
out = {}
help_title = win._help_menu.title()
walk(win.menuBar().actions(), [], out)
print(json.dumps({"nodes": out, "help_title": help_title}))
"""

#: The children's results, kept for the process: ``(code, mode) -> _Dump``.
_DUMP_CACHE: Dict[Tuple[str, str], _Dump] = {}


def _language_dump(code: str, mode: str, scratch_root: Path) -> _Dump:
    """Return ``code``'s menu tree in ``mode`` (``"wrapped"`` or ``"raw"``).

    Read in a fresh child on the first request and kept after that. Children
    are only ever started one at a time, from this one function.
    """
    key = (code, mode)
    cached = _DUMP_CACHE.get(key)
    if cached is not None:
        return cached
    scratch = scratch_root / f"{code}-{mode}"
    scratch.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-c", _LANGUAGE_DUMP_SCRIPT, code, mode, str(scratch)],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_CHILD_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        f"{mode} dump of {code!r} failed (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    dump = _Dump(nodes=payload["nodes"], help_title=payload["help_title"])
    _DUMP_CACHE[key] = dump
    return dump


@pytest.fixture(scope="module")
def _children_scratch(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The folder the children redirect their settings and config into."""
    return tmp_path_factory.mktemp("children")


def _path_order(path: str) -> List[int]:
    """Sort key putting dotted index paths in menu order."""
    return [int(part) for part in path.split(".")]


def _oracle_problems(reference: Tree, nodes: Tree, raw: Optional[Tree]) -> List[str]:
    """Return every way ``nodes`` breaks the access-key rule against English.

    ``reference`` is the English tree, ``nodes`` the language's own, ``raw`` the
    language's display text with the wrapper bypassed (``None`` for English,
    which has no catalogue). Four rules, one problem line per breach: the same
    menu structure as English; the same access-key letter as English at every
    node; no letter used twice within one menu; and a wrapper that never
    changes what the user reads, beyond at most one trailing `` (X)``.
    """
    if not nodes:
        return ["no node was examined"]
    problems: List[str] = []
    extra = sorted(set(nodes) - set(reference), key=_path_order)
    missing = sorted(set(reference) - set(nodes), key=_path_order)
    if extra or missing:
        problems.append(
            f"menu structure differs from English: extra {extra!r}, "
            f"missing {missing!r}"
        )
    for path in sorted(set(nodes) & set(reference), key=_path_order):
        wanted = (reference[path]["letter"] or "").lower()
        found = (nodes[path]["letter"] or "").lower()
        if wanted != found:
            problems.append(
                f"{path}: access key {found!r}, the English source has "
                f"{wanted!r} (shown {nodes[path]['display']!r})"
            )
    seen: Dict[Tuple[str, str], str] = {}
    for path in sorted(nodes, key=_path_order):
        letter = nodes[path]["letter"]
        if letter is None:
            continue
        menu = path.rpartition(".")[0]
        first = seen.setdefault((menu, letter.lower()), path)
        if first != path:
            problems.append(
                f"{path}: access key {letter!r} is also on {first} in menu "
                f"{menu or 'menubar'!r}"
            )
    if raw is not None:
        if set(raw) != set(nodes):
            problems.append(
                "menu structure differs from the raw catalogue tree: "
                f"live-only {sorted(set(nodes) - set(raw))!r}, "
                f"raw-only {sorted(set(raw) - set(nodes))!r}"
            )
        for path in sorted(set(nodes) & set(raw), key=_path_order):
            shown = nodes[path]["display"] or ""
            own = raw[path]["display"] or ""
            if _strip_trailing_fallback_suffix(shown) != own:
                problems.append(
                    f"{path}: the wrapper changed VISIBLE wording, "
                    f"{own!r} became {shown!r}"
                )
    return problems


_LANGUAGE_NAMES = pytest.mark.parametrize("code", _SHIPPED_CODES, ids=_SHIPPED_CODES)


def test_oracle_discovers_eight_languages(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-L10N-UI-004-1/-2: the oracle discovers the languages and prints them;
    fewer than eight would fail it, stating ``N of 8``.

    The discovery is the product's own (``LanguageManager``), and the list the
    per-language cases below are built from at collection time is the same.
    """
    codes = _discover_languages(qapp, monkeypatch)
    print(
        f"oracle: {len(codes)} of {REQUIRED_LANGUAGE_COUNT} languages "
        f"discovered: {codes!r}"
    )
    _assert_enough_languages(codes)
    assert codes == _SHIPPED_CODES


def _folder_holding(tmp_path: Path, codes: Sequence[str]) -> Path:
    """Return a scratch translations folder with copies of ``codes``' catalogues.

    The copies are made from the shipped ``.qm`` files; the shipped folder is
    only read.
    """
    folder = tmp_path / "translations"
    folder.mkdir()
    shipped = _default_translations_dir()
    for code in codes:
        name = f"{_CATALOGUE_PREFIX}{code}{_CATALOGUE_SUFFIX}"
        shutil.copyfile(shipped / name, folder / name)
    return folder


def test_a_folder_with_english_and_spanish_only_fails_stating_2_of_8(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SC-L10N-UI-004-2 (planted): English and Spanish alone fail the oracle,
    and the failure says ``2 of 8 required languages were examined``."""
    folder = _folder_holding(tmp_path, ["es"])
    codes = _discover_languages(qapp, monkeypatch, folder)
    assert codes == ["en", "es"]
    with pytest.raises(AssertionError) as caught:
        _assert_enough_languages(codes)
    assert "2 of 8 required languages were examined" in str(caught.value)


def test_seven_languages_fail_stating_7_of_8(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SC-L10N-UI-004-2 (planted): one shipped catalogue missing is one too
    few, whichever language it is, and the count in the message follows."""
    for left_out in [c for c in _SHIPPED_CODES if c != FALLBACK_LANGUAGE]:
        base = tmp_path / left_out
        base.mkdir()
        folder = _folder_holding(
            base,
            [c for c in _SHIPPED_CODES if c not in (FALLBACK_LANGUAGE, left_out)],
        )
        codes = _discover_languages(qapp, monkeypatch, folder)
        assert left_out not in codes
        with pytest.raises(AssertionError) as caught:
            _assert_enough_languages(codes)
        assert f"{len(codes)} of 8 required languages were examined" in str(
            caught.value
        )


def test_an_empty_folder_fails_stating_1_of_8(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SC-L10N-UI-004-2 (planted): no catalogue at all leaves English alone."""
    folder = _folder_holding(tmp_path, [])
    codes = _discover_languages(qapp, monkeypatch, folder)
    assert codes == ["en"]
    with pytest.raises(AssertionError) as caught:
        _assert_enough_languages(codes)
    assert "1 of 8 required languages were examined" in str(caught.value)


@_LANGUAGE_NAMES
def test_language_keeps_the_english_access_keys(
    code: str, _children_scratch: Path, _qt_auto_mnemonic_enabled: None
) -> None:
    """SC-L10N-UI-004-1: in ``code``, every node's access-key letter equals the
    English node's, no letter repeats within a menu, and the wrapper changes
    nothing a user reads beyond one trailing ``" (X)"``. Prints the language and
    its node count, which must be non-zero (and, for English, more than 100)."""
    reference = _language_dump(FALLBACK_LANGUAGE, "wrapped", _children_scratch).nodes
    nodes = _language_dump(code, "wrapped", _children_scratch).nodes
    raw = (
        None
        if code == FALLBACK_LANGUAGE
        else _language_dump(code, "raw", _children_scratch).nodes
    )
    problems = _oracle_problems(reference, nodes, raw)
    with_letter = sum(1 for node in nodes.values() if node["letter"])
    suffixed = (
        0
        if raw is None
        else sum(
            1 for p in nodes if p in raw and nodes[p]["display"] != raw[p]["display"]
        )
    )
    print(
        f"oracle language={code} nodes={len(nodes)} with_access_key={with_letter} "
        f"suffix_appended={suffixed}"
    )
    assert nodes, f"{code}: no node was examined"
    assert len(reference) > 100
    assert not problems, f"{code}: {len(problems)} problem(s): {problems[:10]!r}"


@pytest.mark.parametrize(
    "code",
    [c for c in _SHIPPED_CODES if c != FALLBACK_LANGUAGE],
    ids=[c for c in _SHIPPED_CODES if c != FALLBACK_LANGUAGE],
)
def test_help_title_keeps_alt_h(
    code: str, _children_scratch: Path, _qt_auto_mnemonic_enabled: None
) -> None:
    """SC-L10N-UI-004-3: the Help menu's access key is Alt+H in ``code``.

    When the language's own word for Help holds no ``h`` in either case, the
    title ends with `` (&H)`` with exactly one space before the half-width
    parenthesis; when it does hold one, the letter is marked in the word and no
    suffix is added (spec scenario outline's own "Given").
    """
    title = _language_dump(code, "wrapped", _children_scratch).help_title
    own = QAction(_language_dump(code, "raw", _children_scratch).help_title).iconText()
    suffix = " (&H)"
    assert QKeySequence.mnemonic(title).toString() == "Alt+H", title
    if "h" not in own.lower():
        assert title.endswith(suffix), (own, title)
        assert not title[: -len(suffix)].endswith(" "), title
        outcome = "suffix appended"
    else:
        assert not title.endswith(suffix), (own, title)
        outcome = "letter marked in the word"
    print(f"oracle help language={code} own={own!r} title={title!r} -> {outcome}")


# --- the comparator, shown failing -------------------------------------------


def _node(letter: Optional[str], display: str) -> Node:
    return {"letter": letter, "display": display}


def _planted_reference() -> Tree:
    return {
        "0": _node("F", "File"),
        "0.0": _node("N", "New"),
        "0.1": _node("O", "Open"),
        "1": _node("E", "Edit"),
    }


def test_comparator_accepts_a_language_that_keeps_every_rule() -> None:
    """The comparator reports nothing for a language that keeps every rule,
    including the one allowed trailing suffix."""
    nodes = {
        "0": _node("F", "Fichier (F)"),
        "0.0": _node("N", "Nouveau"),
        "0.1": _node("O", "Ouvrir"),
        "1": _node("E", "Edition"),
    }
    raw = {
        "0": _node(None, "Fichier"),
        "0.0": _node(None, "Nouveau"),
        "0.1": _node(None, "Ouvrir"),
        "1": _node(None, "Edition"),
    }
    assert _oracle_problems(_planted_reference(), nodes, raw) == []


def test_comparator_reports_a_changed_letter() -> None:
    """A translator's own letter at one node is reported, with its path."""
    nodes = _planted_reference()
    nodes["0.1"] = _node("V", "Ouvrir")
    problems = _oracle_problems(_planted_reference(), nodes, None)
    assert len(problems) == 1 and problems[0].startswith("0.1: access key 'v'")


def test_comparator_reports_a_letter_used_twice_in_one_menu() -> None:
    """Two nodes of one menu sharing a letter is reported, even when English
    has the same fault; the same letter in two different menus is not."""
    shared = _planted_reference()
    shared["0.1"] = _node("N", "Open")
    problems = _oracle_problems(shared, shared, None)
    assert len(problems) == 1 and "is also on 0.0 in menu '0'" in problems[0]
    elsewhere = _planted_reference()
    elsewhere["1"] = _node("N", "Edit")
    assert _oracle_problems(elsewhere, elsewhere, None) == []


def test_comparator_reports_altered_wording_and_a_doubled_suffix() -> None:
    """The wrapper may add one trailing suffix and nothing else: a different
    word, or a second suffix, is reported."""
    reference = _planted_reference()
    raw = {path: _node(None, str(node["display"])) for path, node in reference.items()}
    one = {**reference, "0.1": _node("O", "Open (O)")}
    assert _oracle_problems(reference, one, raw) == []
    altered = {**reference, "0.1": _node("O", "Opened (O)")}
    twice = {**reference, "0.1": _node("O", "Open (O) (O)")}
    for bad in (altered, twice):
        problems = _oracle_problems(reference, bad, raw)
        assert len(problems) == 1 and "changed VISIBLE wording" in problems[0]


def test_comparator_reports_a_missing_node_and_an_empty_tree() -> None:
    """A node English has and the language lacks is reported; so is a tree
    with no node at all."""
    reference = _planted_reference()
    short = {p: n for p, n in reference.items() if p != "1"}
    problems = _oracle_problems(reference, short, None)
    assert len(problems) == 1 and "missing ['1']" in problems[0]
    assert _oracle_problems(reference, {}, None) == ["no node was examined"]


# --- the M1 value table, CJK and Cyrillic ------------------------------------

#: ``(id, source, translation, expected)``. Every expectation follows from the
#: three rules of REQ-L10N-UI-004: mark the first case-insensitive occurrence of
#: the source letter; else append `` (&X)`` with one space; drop the translator's
#: own marker, keep its letter, and keep ``&&`` literal. The Cyrillic rows use
#: only Cyrillic letters. The homoglyph row begins with CYRILLIC CAPITAL LETTER
#: ES, which looks like a Latin ``C`` and is not one; the guard test after the
#: table reads every letter's Unicode name, so a replaced letter fails there.
_M1_CJK_CYRILLIC = [
    ("ja-letter-absent", "&File", "ファイル", "ファイル (&F)"),
    ("zh_CN-letter-absent", "&File", "文件", "文件 (&F)"),
    ("ko-letter-absent", "&File", "파일", "파일 (&F)"),
    (
        "ja-latin-word-marked",
        "Export as &PNG",
        "PNG として書き出す",
        "&PNG として書き出す",
    ),
    ("ja-own-marker-same-letter", "&Open", "開く(&O)", "開く(&O)"),
    ("ja-own-marker-other-letter", "&File", "ファイル(&X)", "ファイル(X) (&F)"),
    ("zh_CN-literal-ampersand", "&Save && Exit", "保存 && 退出", "保存 && 退出 (&S)"),
    ("ru-letter-absent", "&File", "Файл", "Файл (&F)"),
    ("ru-latin-word-marked", "Export as &PNG", "Экспорт в PNG", "Экспорт в &PNG"),
    ("ru-own-marker-dropped", "&File", "&Файл", "Файл (&F)"),
    ("ru-homoglyph-not-matched", "&Copy", "Сохранить", "Сохранить (&C)"),
]


@pytest.mark.parametrize(
    "source, translation, expected",
    [row[1:] for row in _M1_CJK_CYRILLIC],
    ids=[row[0] for row in _M1_CJK_CYRILLIC],
)
def test_m1_cjk_and_cyrillic_rows(
    source: str,
    translation: str,
    expected: str,
    qapp: QApplication,
    _qt_auto_mnemonic_enabled: None,
) -> None:
    """M1 / SC-L10N-UI-004-3, -4: the value table's CJK and Cyrillic rows, and
    Qt's own reading of each result is the English source's letter."""
    result = apply_source_mnemonic(source, translation)
    assert result == expected
    letter = _source_mnemonic_letter(source)
    assert letter is not None
    assert QKeySequence.mnemonic(result).toString() == f"Alt+{letter.upper()}"


def test_m1_the_cyrillic_rows_really_use_cyrillic_letters() -> None:
    """The homoglyph guard: every letter of the Cyrillic words the table uses is
    a Cyrillic letter, never a Latin look-alike a tool replaced."""
    for word in ("Файл", "Экспорт", "Сохранить"):
        names = [unicodedata.name(ch) for ch in word]
        assert all(name.startswith("CYRILLIC") for name in names), (word, names)


# --- How macOS presents the appended suffix ----------------------------------


def test_reports_qts_reading_of_the_appended_suffix(qapp: QApplication) -> None:
    """The macOS case (reported, not asserted for macOS): what Qt itself reads from the
    appended suffix on this platform.

    Printed so the macOS CI log carries the measurement: the displayed text, and
    the mnemonic Qt resolves with the platform's own default and with the
    sequence mnemonics forced on. It does not see a native menu being drawn.
    """
    title = "Ayuda (&H)"
    shown = QAction(title).iconText()
    platform_default = QKeySequence.mnemonic(title).toString()
    qt_set_sequence_auto_mnemonic(True)
    try:
        forced = QKeySequence.mnemonic(title).toString()
    finally:
        qt_set_sequence_auto_mnemonic(sys.platform != "darwin")
    print(
        f"suffix reading: platform={sys.platform} shown={shown!r} "
        f"mnemonic_platform_default={platform_default!r} mnemonic_forced={forced!r}"
    )
    assert shown == "Ayuda (H)"
    assert forced == "Alt+H"
