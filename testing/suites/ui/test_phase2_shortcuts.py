"""Phase-2 tool keyboard-shortcut acceptance (a11y, REQ-P2-UI-001..006).

Every new Phase-2 tool must be reachable by a single-key shortcut (keyboard
operability, Article V). Re-verifies the UI layer's shortcut assignment for the shape
(rectangle/ellipse) and selection (select_rect/select_lasso/select_wand) tools,
avoiding the OTHER six shipped tools' keys. Runs under both themes via the
autouse ``theme`` fixture (shortcut binding is theme-invariant).

**Updated for the input-scheme home-row remap** (the input-scheme spec,
REQ-IS-UI-001/-002): the Aseprite-adjacent letters this module
used to assert (R/O/M/Q/W for these five tools, disjoint from the old B/E/G/L/I
Phase-1 set) were retired wholesale — none of B G I L M O R is bound to anything
any more. ``_NEW_TOOL_SHORTCUTS`` now carries the CURRENT letters the remap
assigned these five tools, and the disjointness check now compares them against
the CURRENT letters of the other six shipped tools (pencil/picker/eraser/fill/
dither/line) rather than the retired Phase-1 set — the same protection the
original assertion gave (catch an accidental double-binding across the full
eleven-tool registry), kept meaningful instead of deleted at exactly the moment
a remap makes it most valuable.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence

from pixelart_creator.ui.main_window import Main_Window

#: New-tool id -> expected shortcut, post input-scheme remap.
_NEW_TOOL_SHORTCUTS = {
    "rectangle": "S",
    "ellipse": "Shift+W",
    "select_rect": "D",
    "select_lasso": "E",
    "select_wand": "Shift+E",
}

#: The other six shipped tools' CURRENT keys (pencil/picker/eraser/fill/dither/
#: line) -- the disjointness partner set, updated in step with the remap so the
#: assertion still catches a real double-binding rather than comparing against
#: retired letters that can no longer collide with anything.
_OTHER_TOOL_SHORTCUTS = {"A", "Shift+A", "Q", "F", "Shift+F", "W"}


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


@pytest.mark.parametrize("tool_id,key", sorted(_NEW_TOOL_SHORTCUTS.items()))
def test_new_tool_shortcut_bound_and_activates(qtbot, tool_id, key):
    """Each new tool action carries its key and activation selects that tool."""
    win = _window(qtbot)
    action = win._tool_actions[tool_id]
    assert not action.shortcut().isEmpty()
    assert action.shortcut() == QKeySequence(key)
    assert key in action.toolTip()  # the key is discoverable in the tooltip
    # Triggering the action makes exactly that tool the active controller.
    action.trigger()
    assert win.active_tab().view.active_tool() is win._tools[tool_id]


def test_new_tool_shortcuts_disjoint_from_phase1(qtbot):
    """The five tracked keys never collide with the other six shipped tools'
    keys, and carry no duplicate among themselves -- the double-binding guard
    this module exists for, re-pointed at the current scheme."""
    win = _window(qtbot)
    new_keys = set(_NEW_TOOL_SHORTCUTS.values())
    assert new_keys.isdisjoint(_OTHER_TOOL_SHORTCUTS)
    assert len(new_keys) == len(_NEW_TOOL_SHORTCUTS)  # no duplicates
    # And, directly against the live action registry (not just the two
    # hard-coded sets above): every one of the eleven bound sequences is
    # still pairwise distinct.
    all_sequences = [a.shortcut().toString() for a in win._tool_actions.values()]
    assert len(all_sequences) == len(set(all_sequences)) == 11
