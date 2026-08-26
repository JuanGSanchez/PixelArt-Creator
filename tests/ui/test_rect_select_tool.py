"""Rectangle selection-tool acceptance (REQ-P2-UI-004).

Scenarios SC-U004-1 (press-drag sets a rectangle selection matching the region)
and SC-U004-2 (Shift adds / Alt subtracts from the existing selection, CL-4).
Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.tools import RectSelectTool
from tests.ui._ui_helpers import move, press, release, viewport_point_for_pixel

LEFT = Qt.MouseButton.LeftButton
NO_BTN = Qt.MouseButton.NoButton


def _mev(view, etype, x, y, button, buttons, mod):
    # Routed through the view's own CURRENT mapping (view.mapFromScene), never
    # a hand-computed offset -- see _ui_helpers.viewport_point_for_pixel.
    point = viewport_point_for_pixel(view, x, y)
    pt = QPointF(point.x(), point.y())
    return QMouseEvent(etype, pt, pt, button, buttons, mod)


def _drag_mod(view, x0, y0, x1, y1, mod):
    """Press-drag-release carrying a keyboard modifier at the press (combine)."""
    view.mousePressEvent(
        _mev(view, QEvent.Type.MouseButtonPress, x0, y0, LEFT, LEFT, mod)
    )
    view.mouseMoveEvent(_mev(view, QEvent.Type.MouseMove, x1, y1, NO_BTN, LEFT, mod))
    view.mouseReleaseEvent(
        _mev(view, QEvent.Type.MouseButtonRelease, x1, y1, LEFT, NO_BTN, mod)
    )


def test_sc_u004_1_drag_sets_rectangle_selection(make_view):
    """SC-U004-1: a press-drag sets a rectangle selection over the dragged region."""
    view, _scene, _stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    press(view, 2, 2)
    move(view, 5, 6)
    release(view, 5, 6)
    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2) and mask.is_selected(5, 6)
    assert not mask.is_selected(0, 0)
    assert not mask.is_selected(6, 6)
    assert mask.bounds() == (2, 2, 5, 6)


def test_sc_u004_2_shift_adds_alt_subtracts(make_view):
    """SC-U004-2: Shift-drag adds a region; Alt-drag subtracts (CL-4)."""
    # Add: an initial rectangle plus a disjoint Shift-drag rectangle -> union.
    view, _scene, _stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    _drag_mod(view, 1, 1, 3, 3, Qt.KeyboardModifier.NoModifier)
    _drag_mod(view, 8, 8, 10, 10, Qt.KeyboardModifier.ShiftModifier)
    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # first region kept
    assert mask.is_selected(9, 9)  # second region added

    # Subtract: Alt-drag removes an overlapping sub-region.
    view2, _s2, _st2 = make_view(16, 16)
    view2.set_tool(RectSelectTool())
    _drag_mod(view2, 2, 2, 8, 8, Qt.KeyboardModifier.NoModifier)
    _drag_mod(view2, 5, 5, 8, 8, Qt.KeyboardModifier.AltModifier)
    mask2 = view2.active_selection()
    assert mask2 is not None
    assert mask2.is_selected(3, 3)  # outside the subtracted box
    assert not mask2.is_selected(6, 6)  # inside the subtracted box


def test_press_outside_existing_selection_starts_new(make_view):
    """Pressing OUTSIDE an active selection begins a new selection (not a move)."""
    view, _scene, stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    view.set_selection(rect_mask(16, 16, 1, 1, 3, 3))
    press(view, 9, 9)  # outside the current selection -> new selection drag
    move(view, 12, 12)
    release(view, 12, 12)
    mask = view.active_selection()
    assert mask is not None and mask.is_selected(10, 10)
    assert not mask.is_selected(2, 2)  # replaced, not moved
    assert stack.count() == 0  # a (re)selection is not an undoable buffer edit


def test_zero_offset_move_pushes_no_command(make_view):
    """A press-inside then release at the same pixel is a no-op move (no command)."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    scene.active_buffer().set_pixel(3, 3, (230, 30, 30, 255))
    before = scene.active_buffer().copy()
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    press(view, 3, 3)
    release(view, 3, 3)  # dx == dy == 0
    assert stack.count() == 0
    assert scene.active_buffer() == before


def test_subtract_to_empty_clears_selection(make_view):
    """An Alt-drag that subtracts the whole selection clears it to None."""
    view, _scene, _stack = make_view(16, 16)
    view.set_tool(RectSelectTool())
    view.set_selection(rect_mask(16, 16, 2, 2, 5, 5))
    _drag_mod(view, 2, 2, 5, 5, Qt.KeyboardModifier.AltModifier)  # subtract all
    assert view.active_selection() is None
