"""Selection overlay & floating-move acceptance (REQ-P2-UI-007).

Scenarios SC-U007-1 (the active selection shows a high-contrast outline legible in
both themes), SC-U007-2 (dragging inside the selection moves it; release commits
ONE undoable command) and SC-U007-3 (undo restores the pre-move pixels exactly).
Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.tools import RectSelectTool
from testing.suites.ui._ui_helpers import move, press, release

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def test_sc_u007_1_outline_high_contrast_both_themes(make_view):
    """SC-U007-1: the active selection renders a dual-contrast marching-ants edge."""
    view, scene, _stack = make_view(16, 16)
    view.set_selection(rect_mask(16, 16, 2, 2, 6, 6))
    overlay = scene._selection_overlay
    assert overlay._edges, "a non-empty selection must produce boundary edges"
    # Legible in BOTH themes without animation: a dark pen under a light pen.
    assert overlay._dark != overlay._light
    assert overlay._dark.alpha() > 0 and overlay._light.alpha() > 0
    # Clearing the selection clears the overlay.
    view.clear_selection()
    assert not scene._selection_overlay._edges


def test_sc_u007_2_drag_moves_selection_one_command(make_view):
    """SC-U007-2: dragging inside the selection moves it as ONE undoable command."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    press(view, 3, 3)  # press inside the selection -> floating move
    move(view, 5, 3)
    release(view, 5, 3)  # commit (dx=2, dy=0)
    assert stack.count() == 1
    assert buf.get_pixel(5, 3) == RED  # lifted pixel re-stamped at the offset
    assert buf.get_pixel(3, 3) == TRANSPARENT  # vacated area cleared (cut-move)


def test_sc_u007_3_undo_restores_premove_pixels(make_view):
    """SC-U007-3: undo restores the pre-move pixels exactly (one step)."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    before = buf.copy()
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    press(view, 3, 3)
    move(view, 5, 3)
    release(view, 5, 3)
    stack.undo()
    assert scene.active_buffer() == before
