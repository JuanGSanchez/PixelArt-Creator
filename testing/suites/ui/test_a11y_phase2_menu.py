"""Phase-2 accessibility re-verification: menu reachability + distinct names.

Re-verifies the UI layer's a11y fixes:

* **A11Y-P2-1** — the *filled shapes*, *pixel-perfect*, and *forced AA-off* drawing
  modes are reachable from the **View** menu with a keyboard **mnemonic**
  (Alt+V,D / Alt+V,P / Alt+V,A), not toolbar-only. Maps to REQ-P2-UI-003 (SC-U003-2),
  -012 (SC-U012-2), -014 (SC-U014-1) keyboard-operability + NFR-7.
* **A11Y-P2-2** — the flip actions carry direct accelerators **Shift+H** / **Shift+V**
  (REQ-P2-UI-009, SC-U009-3 keyboard reachability + NFR-7).
* **Distinct selection-tool names** — the rectangle / lasso / magic-wand selection
  tools expose distinct, non-ambiguous accessible names (screen-reader clarity,
  REQ-P2-UI-004..006 + NFR-7), and none collides with a shape-tool name.

Every test runs twice via the autouse ``theme`` fixture (both themes); menu wiring,
mnemonics, and shortcuts are theme-invariant but the parity run is asserted for free.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence

from pixelart_creator.ui.main_window import Main_Window

#: The three access-key tests below (the View menu's own letter, the three
#: drawing-mode letters, and their distinctness) assert the letter on EVERY
#: operating system, macOS included: ``REQ-L10N-UI-004`` says nothing about
#: macOS, and neither do ``REQ-P2-UI-003``, ``-004`` or ``-009``.
#: ``QKeySequence.mnemonic()`` reads a process-wide flag that Qt itself
#: defaults to OFF on macOS (``qt_set_sequence_auto_mnemonic``); with it off the
#: call returns an empty sequence for every string, whatever marker the string
#: carries. That is a difference in the ORACLE's platform default, not a macOS
#: stripping of the product's ``&`` markers. So each of the three tests requests
#: the ``_qt_auto_mnemonic_enabled`` fixture (``conftest.py``), which forces the
#: flag on for the test and restores the platform default afterwards. What this
#: proves on macOS: the marker the product wrote names the right letter. It does
#: not prove that an Alt key press reaches the item, which native macOS menus do
#: not offer.


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# -- A11Y-P2-1: drawing-mode toggles reachable via the View menu + mnemonic ----

#: View-menu drawing-mode toggle attr -> expected mnemonic key sequence.
_VIEW_MENU_MNEMONICS = {
    "_filled_action": "Alt+D",  # "Fille&d Shapes"  -> Alt+V,D
    "_pixel_perfect_action": "Alt+P",  # "&Pixel Perfect"  -> Alt+V,P
    "_aa_off_action": "Alt+A",  # "&Anti-aliasing Off" -> Alt+V,A
}


def test_view_menu_has_mnemonic_itself(qtbot, _qt_auto_mnemonic_enabled):
    """The View menu is itself Alt-reachable (Alt+V), the prefix of every chord."""
    win = _window(qtbot)
    assert QKeySequence.mnemonic(win._view_menu.title()) == QKeySequence("Alt+V")


@pytest.mark.parametrize("attr,expected", sorted(_VIEW_MENU_MNEMONICS.items()))
def test_a11y_p2_1_drawing_mode_toggle_in_view_menu_with_mnemonic(
    qtbot, _qt_auto_mnemonic_enabled, attr, expected
):
    """A11Y-P2-1: each drawing-mode toggle is in the View menu with its mnemonic."""
    win = _window(qtbot)
    action = getattr(win, attr)
    # Present in the View menu (keyboard-navigable menu path, not toolbar-only).
    assert action in win._view_menu.actions()
    # A toggle, operable from the keyboard.
    assert action.isCheckable()
    assert action.text() != ""  # tr()-wrapped accessible name
    # Carries the expected Alt mnemonic (Alt+V, <letter>), on every OS: the
    # fixture makes Qt's oracle read the marker on macOS as well (see the note
    # at the top of the module).
    assert QKeySequence.mnemonic(action.text()) == QKeySequence(expected)


def test_a11y_p2_1_view_menu_mnemonics_are_distinct(qtbot, _qt_auto_mnemonic_enabled):
    """The View-menu drawing-mode mnemonics do not collide with each other."""
    win = _window(qtbot)
    seqs = [
        QKeySequence.mnemonic(getattr(win, attr).text())
        for attr in _VIEW_MENU_MNEMONICS
    ]
    assert len(seqs) == len(set(seqs))  # all distinct
    assert all(not s.isEmpty() for s in seqs)  # every one actually resolves


# -- A11Y-P2-2: flip actions carry Shift+H / Shift+V accelerators --------------

_FLIP_SHORTCUTS = {
    "_flip_h_action": "Shift+H",
    "_flip_v_action": "Shift+V",
}


@pytest.mark.parametrize("attr,expected", sorted(_FLIP_SHORTCUTS.items()))
def test_a11y_p2_2_flip_actions_have_shift_accelerators(qtbot, attr, expected):
    """A11Y-P2-2: flip-H/flip-V are keyboard-triggerable via Shift+H / Shift+V."""
    win = _window(qtbot)
    action = getattr(win, attr)
    assert not action.shortcut().isEmpty()
    assert action.shortcut() == QKeySequence(expected)


def test_a11y_p2_2_flip_accelerators_disjoint_from_tool_keys(qtbot):
    """The Shift+flip accelerators never collide with the single-key tool shortcuts."""
    win = _window(qtbot)
    flip_seqs = {
        win._flip_h_action.shortcut().toString(),
        win._flip_v_action.shortcut().toString(),
    }
    tool_seqs = {
        a.shortcut().toString()
        for a in win._tool_actions.values()
        if not a.shortcut().isEmpty()
    }
    assert flip_seqs.isdisjoint(tool_seqs)


# -- Distinct selection-tool names ---------------------------------------------

_SELECTION_TOOL_IDS = ("select_rect", "select_lasso", "select_wand")
_SHAPE_TOOL_IDS = ("rectangle", "ellipse")


def test_selection_tools_expose_distinct_names(qtbot):
    """The 3 selection tools expose distinct, non-empty accessible names."""
    win = _window(qtbot)
    names = [win._tool_actions[t].text() for t in _SELECTION_TOOL_IDS]
    assert all(n != "" for n in names)  # every tool is named
    assert len(names) == len(set(names))  # all three are distinct


def test_selection_tool_names_disjoint_from_shape_tool_names(qtbot):
    """A selection tool's name never duplicates a shape tool's (no ambiguity)."""
    win = _window(qtbot)
    sel_names = {win._tool_actions[t].text() for t in _SELECTION_TOOL_IDS}
    shape_names = {win._tool_actions[t].text() for t in _SHAPE_TOOL_IDS}
    assert sel_names.isdisjoint(shape_names)
    # And the rectangle-select name is not merely the shape's "Rectangle".
    assert win._tool_actions["select_rect"].text() != (
        win._tool_actions["rectangle"].text()
    )


def test_all_tool_names_are_unique(qtbot):
    """No two tool actions share an accessible name (screen-reader clarity)."""
    win = _window(qtbot)
    names = [a.text() for a in win._tool_actions.values()]
    assert len(names) == len(set(names))
