"""Phase-2 tool keyboard-shortcut acceptance (a11y, REQ-P2-UI-001..006).

Every new Phase-2 tool must be reachable by a single-key shortcut (keyboard
operability, Article V). Re-verifies the AGT-05 shortcut assignment for the shape
(R/O) and selection (M/Q/W) tools, avoiding the Phase-1 set (B/E/G/L/I). Runs under
both themes via the autouse ``theme`` fixture (shortcut binding is theme-invariant).
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence

from pixelart_creator.ui.main_window import Main_Window

#: New-tool id -> expected single-key shortcut (AGT-05, Aseprite-adjacent).
_NEW_TOOL_SHORTCUTS = {
    "rectangle": "R",
    "ellipse": "O",
    "select_rect": "M",
    "select_lasso": "Q",
    "select_wand": "W",
}


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
    """The Phase-2 keys never collide with the Phase-1 tool set (B/E/G/L/I)."""
    win = _window(qtbot)
    phase1 = {"B", "E", "G", "L", "I"}
    new_keys = set(_NEW_TOOL_SHORTCUTS.values())
    assert new_keys.isdisjoint(phase1)
    assert len(new_keys) == len(_NEW_TOOL_SHORTCUTS)  # no duplicates
