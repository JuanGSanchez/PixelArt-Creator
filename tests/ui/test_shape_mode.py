"""Shape filled / outline mode acceptance (REQ-P2-UI-003).

Scenarios SC-U003-1 (outline commits the perimeter only; filled commits the
interior) and SC-U003-2 (the mode control is tr()-wrapped and keyboard-reachable —
a11y, both themes). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import RectangleTool
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
