"""Shape filled / outline mode acceptance (REQ-P2-UI-003).

Scenarios SC-U003-1 (outline commits the perimeter only; filled commits the
interior) and SC-U003-2 (the mode control is tr()-wrapped and keyboard-reachable —
a11y, both themes). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import RectangleTool
from pixelart_creator.ui.tools.shape_base import ShapeTool
from tests.ui._ui_helpers import move, press, release

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u003_1_outline_vs_filled(make_view):
    """SC-U003-1: outline mode paints the perimeter only; filled paints inside."""
    # Outline (default, CL-17): interior stays clear.
    view, scene, _stack = make_view(16, 16)
    outline = RectangleTool()
    outline.set_filled(False)
    view.set_tool(outline)
    view.set_active_color(RED)
    press(view, 0, 0)
    move(view, 6, 6)
    release(view, 6, 6)
    assert scene.active_buffer().get_pixel(3, 3) == TRANSPARENT
    assert scene.active_buffer().get_pixel(0, 0) == RED

    # Filled: the same drag now fills the interior.
    view2, scene2, _stack2 = make_view(16, 16)
    filled = RectangleTool()
    filled.set_filled(True)
    view2.set_tool(filled)
    view2.set_active_color(RED)
    press(view2, 0, 0)
    move(view2, 6, 6)
    release(view2, 6, 6)
    assert scene2.active_buffer().get_pixel(3, 3) == RED


def test_shape_commit_is_mask_constrained(make_view):
    """A shape commit with an active selection writes only masked pixels (P2-LOGIC-006).

    Exercises the mask-constrained commit branch of the shared shape controller:
    a filled rectangle drawn across the whole buffer paints only the pixels inside
    the active selection; unmasked pixels stay clear.
    """
    view, scene, stack = make_view(16, 16)
    filled = RectangleTool()
    filled.set_filled(True)
    view.set_tool(filled)
    view.set_active_color(RED)
    view.set_selection(rect_mask(16, 16, 4, 4, 8, 8))  # constrain to a sub-box
    press(view, 0, 0)
    move(view, 15, 15)
    release(view, 15, 15)
    buf = scene.active_buffer()
    assert buf.get_pixel(6, 6) == RED  # inside the selection -> painted
    assert buf.get_pixel(1, 1) == TRANSPARENT  # outside the selection -> untouched
    assert stack.count() == 1


def test_sc_u003_2_mode_control_translatable_and_reachable(qtbot):
    """SC-U003-2: the filled-mode control is tr()-wrapped + keyboard-operable."""
    win = _window(qtbot)
    action = win._filled_action
    assert action.text() != ""  # tr()-wrapped label (accessible name for AT)
    assert action.isCheckable()  # a toggle, operable from the keyboard menu path
    # Toggling propagates to both shape tools (shared option).
    action.setChecked(True)
    assert win._rectangle_tool.filled is True
    assert win._ellipse_tool.filled is True


# =========================================================================
# ShapeTool controller contract (P2-UI-001..003) -- the abstract subclass
# hooks, and the two no-active-drag / zero-net-change guards no scripted
# RectangleTool/EllipseTool drag through the UI ever reaches.
# =========================================================================


def test_shape_tool_abstract_hooks_raise_not_implemented():
    """``ShapeTool`` itself declares ``kind``/``label``/``_draw_op`` abstract
    (``NotImplementedError``) -- proving ``RectangleTool``/``EllipseTool``
    must, and do, override every one of them."""
    tool = ShapeTool()
    with pytest.raises(NotImplementedError):
        tool.kind()
    with pytest.raises(NotImplementedError):
        tool.label()
    with pytest.raises(NotImplementedError):
        tool._draw_op(None, 0, 0, 0, 0, None)


def test_shape_tool_on_move_and_on_release_noop_without_a_prior_press():
    """``on_move``/``on_release`` are documented drag continuations -- called
    with no drag in progress (``self._start is None``, e.g. a stray event
    delivered outside a press/move/release sequence) they are silent no-ops,
    never touching ``ctx``."""
    tool = ShapeTool()
    tool.on_move(5, 5, None)  # no exception, nothing to update
    tool.on_release(5, 5, None)  # no exception, nothing to commit
    assert tool._start is None


def test_shape_commit_with_zero_net_change_pushes_no_command(make_view):
    """A shape drawn entirely over already-matching pixels changes nothing --
    ``Stroke.to_command`` returns ``None`` and no undo entry is pushed (the
    ``command is not None`` guard's False branch)."""
    view, scene, stack = make_view(16, 16)
    buf = scene.active_buffer()
    buf.fill_rect(0, 0, 16, 16, RED)  # the whole buffer is already RED
    tool = RectangleTool()
    tool.set_filled(True)
    view.set_tool(tool)
    view.set_active_color(RED)

    press(view, 2, 2)
    move(view, 6, 6)
    release(view, 6, 6)

    assert stack.count() == 0  # zero net change -> no command pushed
    assert buf.get_pixel(4, 4) == RED  # unchanged, still red
