"""Left-click paint acceptance tests (REQ-P1-UI-006).

Scenarios SC-UI-006-1 (click paints + one command), SC-UI-006-2 (drag coalesces
to one command), SC-UI-006-3 (off-buffer click is a no-op). Both themes.
"""

from __future__ import annotations

from tests.ui._ui_helpers import click_pixel, drag_path

BLUE = (40, 90, 220, 255)


def test_sc_ui_006_1_click_paints_pixel_one_command(make_view):
    """SC-UI-006-1: a left-click paints the target pixel and pushes one command."""
    view, scene, stack = make_view(64, 64)
    view.set_active_color(BLUE)
    click_pixel(view, 10, 7)
    assert scene.active_buffer().get_pixel(10, 7) == BLUE
    assert stack.count() == 1


def test_sc_ui_006_2_drag_paints_all_pixels_one_command(make_view):
    """SC-UI-006-2: a drag paints every covered pixel as exactly one command."""
    view, scene, stack = make_view(64, 64)
    view.set_active_color(BLUE)
    drag_path(view, [(0, 0), (1, 0), (2, 0), (3, 0)])
    buf = scene.active_buffer()
    for x in range(4):
        assert buf.get_pixel(x, 0) == BLUE
    assert stack.count() == 1  # QUndoStack depth increased by exactly 1


def test_sc_ui_006_3_click_outside_buffer_is_noop(make_view):
    """SC-UI-006-3: a click resolving outside the buffer changes nothing."""
    view, scene, stack = make_view(64, 64)
    before = scene.active_buffer().copy()
    click_pixel(view, 100, 100)  # outside (0,0,64,64)
    assert scene.active_buffer() == before
    assert stack.count() == 0
