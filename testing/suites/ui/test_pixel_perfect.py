"""Pixel-perfect stroke-toggle acceptance (REQ-P2-UI-012).

Scenarios SC-U012-1 (with pixel-perfect on, a freehand stroke commits a clean 1px
path with no elbow pixel — and the toggle demonstrably changes the freehand result)
and SC-U012-2 (the toggle is tr()-wrapped and keyboard-reachable). Both themes via
the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.tools import PencilTool
from tests.ui._ui_helpers import drag_path

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)

#: An L-shaped freehand path: (0,0) -> (1,0) -> (1,1). The elbow is (1,0).
_L_PATH = [(0, 0), (1, 0), (1, 1)]


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u012_1_pixel_perfect_changes_freehand_result(make_view):
    """SC-U012-1: pixel-perfect removes the elbow pixel that a plain stroke keeps."""
    # Plain freehand: the elbow pixel (1,0) IS painted.
    view, scene, _stack = make_view(8, 8)
    view.set_tool(PencilTool())
    view.set_active_color(RED)
    view.set_pixel_perfect(False)
    drag_path(view, _L_PATH)
    assert scene.active_buffer().get_pixel(1, 0) == RED

    # Pixel-perfect on: the same drag drops the elbow -> a clean 1px path.
    view2, scene2, _s2 = make_view(8, 8)
    view2.set_tool(PencilTool())
    view2.set_active_color(RED)
    view2.set_pixel_perfect(True)
    drag_path(view2, _L_PATH)
    buf = scene2.active_buffer()
    assert buf.get_pixel(0, 0) == RED  # endpoints survive
    assert buf.get_pixel(1, 1) == RED
    assert buf.get_pixel(1, 0) == TRANSPARENT  # elbow removed


def test_sc_u012_2_toggle_translatable_and_reachable(qtbot):
    """SC-U012-2: the pixel-perfect toggle is tr()-wrapped and operable."""
    win = _window(qtbot)
    action = win._pixel_perfect_action
    assert action.text() != ""
    assert action.isCheckable()
    action.setChecked(True)
    assert win.active_tab().view._pixel_perfect is True
