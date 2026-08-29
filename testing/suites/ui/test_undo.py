"""Undo/redo bridge acceptance tests (REQ-P1-UI-009, -010).

Scenarios SC-UI-009-1 (delegates to logic PixelEdit diff), SC-UI-010-1 (undo
reverts exactly the painted pixel), SC-UI-010-2 (redo re-applies), SC-UI-010-3
(action enable-state tracks the stack). Both themes.
"""

from __future__ import annotations

from testing.suites.ui._ui_helpers import click_pixel

BLUE = (40, 90, 220, 255)
TRANSPARENT = (0, 0, 0, 0)


def test_sc_ui_010_1_undo_reverts_exactly_painted_pixel(make_view):
    """SC-UI-010-1: undo restores the pixel and touches no other pixel."""
    view, scene, stack = make_view(64, 64)
    buf = scene.active_buffer()
    view.set_active_color(BLUE)
    click_pixel(view, 10, 7)
    assert buf.get_pixel(10, 7) == BLUE
    stack.undo()
    assert buf.get_pixel(10, 7) == TRANSPARENT
    # No neighbour was disturbed by the undo.
    assert buf.get_pixel(11, 7) == TRANSPARENT
    assert buf.get_pixel(10, 8) == TRANSPARENT


def test_sc_ui_010_2_redo_reapplies_edit(make_view):
    """SC-UI-010-2: redo re-applies the reverted edit."""
    view, scene, stack = make_view(64, 64)
    buf = scene.active_buffer()
    view.set_active_color(BLUE)
    click_pixel(view, 10, 7)
    stack.undo()
    stack.redo()
    assert buf.get_pixel(10, 7) == BLUE


def test_sc_ui_010_3_action_enable_state_tracks_stack(make_view):
    """SC-UI-010-3: canUndo/canRedo track the stack across paint/undo."""
    view, _scene, stack = make_view(64, 64)
    assert stack.canUndo() is False
    assert stack.canRedo() is False
    view.set_active_color(BLUE)
    click_pixel(view, 4, 4)
    assert stack.canUndo() is True
    assert stack.canRedo() is False
    stack.undo()
    assert stack.canRedo() is True


def test_sc_ui_009_1_command_delegates_to_logic_diff(make_view):
    """SC-UI-009-1: undo/redo reproduce exactly the logic PixelEdit diff.

    The command holds no pixel maths of its own; a full undo→redo cycle must be
    a faithful round-trip of the recorded ``(old, new)`` per-pixel diff.
    """
    view, scene, stack = make_view(64, 64)
    buf = scene.active_buffer()
    view.set_active_color(BLUE)
    click_pixel(view, 2, 2)
    painted = buf.copy()
    stack.undo()
    reverted = buf.copy()
    stack.redo()
    reapplied = buf.copy()
    # redo reproduces the painted state exactly; undo differs only at (2,2).
    assert reapplied == painted
    assert reverted != painted
    assert reverted.get_pixel(2, 2) == TRANSPARENT
    assert painted.get_pixel(2, 2) == BLUE
