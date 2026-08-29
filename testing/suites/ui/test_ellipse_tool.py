"""Ellipse shape-tool acceptance (REQ-P2-UI-002, -003).

Scenarios SC-U002-1 (live ellipse preview during drag), SC-U002-2 (release commits
exactly one undoable command), SC-U002-3 (undo removes the ellipse in one step).
Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsEllipseItem

from pixelart_creator.ui.tools import EllipseTool
from testing.suites.ui._ui_helpers import move, press, release

BLUE = (40, 90, 220, 255)


def _painted_count(buf, color) -> int:
    return sum(
        1
        for y in range(buf.height)
        for x in range(buf.width)
        if buf.get_pixel(x, y) == color
    )


def test_sc_u002_1_live_preview_during_drag(make_view):
    """SC-U002-1: press-drag shows a live ellipse preview (both themes)."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(EllipseTool())
    view.set_active_color(BLUE)
    press(view, 1, 1)
    move(view, 8, 6)
    assert isinstance(scene._shape_preview, QGraphicsEllipseItem)
    assert stack.count() == 0


def test_sc_u002_2_release_commits_one_command(make_view):
    """SC-U002-2: release commits the ellipse as exactly ONE command."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(EllipseTool())
    view.set_active_color(BLUE)
    press(view, 1, 1)
    move(view, 10, 8)
    release(view, 10, 8)
    assert stack.count() == 1
    assert scene._shape_preview is None
    assert _painted_count(scene.active_buffer(), BLUE) > 0


def test_sc_u002_3_undo_removes_ellipse_one_step(make_view):
    """SC-U002-3: undo removes the ellipse in one step; redo restores it."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(EllipseTool())
    view.set_active_color(BLUE)
    before = scene.active_buffer().copy()
    press(view, 1, 1)
    move(view, 10, 8)
    release(view, 10, 8)
    stack.undo()
    assert scene.active_buffer() == before
    stack.redo()
    assert _painted_count(scene.active_buffer(), BLUE) > 0
