"""Rectangle shape-tool acceptance (REQ-P2-UI-001, -003).

Scenarios SC-U001-1 (live preview during drag), SC-U001-2 (release commits exactly
one undoable command), SC-U001-3 (undo removes the whole rectangle in one step,
redo restores it), SC-U001-4 (the commit uses the active colour). Every test runs
under both light and dark themes via the autouse ``theme`` fixture (conftest).
"""

from __future__ import annotations

from PySide6.QtWidgets import QGraphicsRectItem

from pixelart_creator.ui.tools import RectangleTool
from tests.ui._ui_helpers import move, press, release

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _perimeter_painted(buf, color) -> bool:
    for x in range(0, 5):
        if buf.get_pixel(x, 0) != color or buf.get_pixel(x, 4) != color:
            return False
    for y in range(0, 5):
        if buf.get_pixel(0, y) != color or buf.get_pixel(4, y) != color:
            return False
    return True


def test_sc_u001_1_live_preview_during_drag(make_view):
    """SC-U001-1: press-drag shows a live rectangle preview (both themes)."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    press(view, 1, 1)
    move(view, 5, 5)
    # A vector preview item exists mid-drag and no command has been pushed yet.
    assert isinstance(scene._shape_preview, QGraphicsRectItem)
    assert stack.count() == 0


def test_sc_u001_2_release_commits_one_command(make_view):
    """SC-U001-2: release commits the rectangle as exactly ONE command."""
    view, scene, stack = make_view(16, 16)
    tool = RectangleTool()  # default: outline (CL-17)
    view.set_tool(tool)
    view.set_active_color(RED)
    press(view, 0, 0)
    move(view, 4, 4)
    release(view, 4, 4)
    assert stack.count() == 1
    assert scene._shape_preview is None  # preview cleared on commit
    buf = scene.active_buffer()
    assert _perimeter_painted(buf, RED)
    assert buf.get_pixel(2, 2) == TRANSPARENT  # outline: interior untouched


def test_sc_u001_3_undo_removes_whole_rect_redo_restores(make_view):
    """SC-U001-3: undo removes the rectangle in one step; redo restores it."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    before = scene.active_buffer().copy()
    press(view, 0, 0)
    move(view, 4, 4)
    release(view, 4, 4)
    assert stack.count() == 1
    stack.undo()
    assert scene.active_buffer() == before  # one undoable step
    stack.redo()
    assert _perimeter_painted(scene.active_buffer(), RED)


def test_sc_u001_4_commit_uses_active_colour(make_view):
    """SC-U001-4: the committed rectangle uses the active colour (S2)."""
    view, scene, _stack = make_view(16, 16)
    view.set_tool(RectangleTool())
    view.set_active_color(RED)
    press(view, 2, 2)
    move(view, 6, 6)
    release(view, 6, 6)
    assert scene.active_buffer().get_pixel(2, 2) == RED
