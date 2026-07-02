"""Tool-controller acceptance tests (REQ-P1-UI-011..016).

Scenarios SC-UI-011-1 (one active tool), SC-UI-012-1 (pencil), SC-UI-013-1
(eraser), SC-UI-014-1/-2 (fill + no-op), SC-UI-015-1 (line preview/commit),
SC-UI-016-1 (colour picker). Both themes.
"""

from __future__ import annotations

from pixelart_creator.ui.tools import (
    EraserTool,
    FloodFillTool,
    LineTool,
    PencilTool,
    PickerTool,
)
from tests.ui._ui_helpers import click_pixel, move, press, release

GREEN = (30, 190, 60, 255)
YELLOW = (240, 220, 40, 255)
CYAN = (0, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def test_sc_ui_011_1_exactly_one_tool_active(make_view):
    """SC-UI-011-1: selecting a tool makes exactly that tool active."""
    view, _scene, _stack = make_view(32, 32)
    pencil = PencilTool()
    eraser = EraserTool()
    view.set_tool(pencil)
    assert view.active_tool() is pencil
    view.set_tool(eraser)
    assert view.active_tool() is eraser
    assert view.active_tool() is not pencil


def test_sc_ui_012_1_pencil_paints_active_colour(make_view):
    """SC-UI-012-1: the pencil paints with the active colour, one command."""
    view, scene, stack = make_view(32, 32)
    view.set_tool(PencilTool())
    view.set_active_color(GREEN)
    click_pixel(view, 2, 2)
    assert scene.active_buffer().get_pixel(2, 2) == GREEN
    assert stack.count() == 1


def test_sc_ui_013_1_eraser_clears_to_default(make_view):
    """SC-UI-013-1: the eraser clears an RGBA pixel to transparent, one command."""
    view, scene, stack = make_view(32, 32)
    scene.active_buffer().set_pixel(2, 2, RED)
    view.set_tool(EraserTool())
    click_pixel(view, 2, 2)
    assert scene.active_buffer().get_pixel(2, 2) == TRANSPARENT
    assert stack.count() == 1


def test_sc_ui_014_1_fill_fills_region_one_command(make_view):
    """SC-UI-014-1: flood-fill fills the contiguous region as one command."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(FloodFillTool())
    view.set_active_color(YELLOW)
    click_pixel(view, 8, 8)
    buf = scene.active_buffer()
    assert buf.get_pixel(0, 0) == YELLOW
    assert buf.get_pixel(15, 15) == YELLOW
    assert buf.get_pixel(8, 8) == YELLOW
    assert stack.count() == 1


def test_sc_ui_014_2_fill_on_matching_region_is_noop(make_view):
    """SC-UI-014-2: fill with the seed's colour changes nothing, no command."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(FloodFillTool())
    view.set_active_color(TRANSPARENT)  # equals the empty seed pixel
    before = scene.active_buffer().copy()
    click_pixel(view, 8, 8)
    assert scene.active_buffer() == before
    assert stack.count() == 0


def test_sc_ui_015_1_line_previews_then_commits_one_command(make_view):
    """SC-UI-015-1: line previews during drag, commits one command on release."""
    view, scene, stack = make_view(16, 16)
    view.set_tool(LineTool())
    view.set_active_color(BLACK)
    press(view, 0, 0)
    move(view, 4, 0)
    # During drag: a preview exists but no command is pushed yet (CL-11).
    assert scene._preview_item is not None
    assert stack.count() == 0
    release(view, 4, 0)
    buf = scene.active_buffer()
    for x in range(5):
        assert buf.get_pixel(x, 0) == BLACK
    assert stack.count() == 1
    assert scene._preview_item is None  # preview cleared on commit


def test_sc_ui_016_1_picker_sets_active_colour_no_command(make_view, qtbot):
    """SC-UI-016-1: the picker sets the active colour, mutates nothing, no command."""
    view, scene, stack = make_view(16, 16)
    scene.active_buffer().set_pixel(5, 5, CYAN)
    before = scene.active_buffer().copy()
    view.set_tool(PickerTool())
    with qtbot.waitSignal(view.colorPicked, timeout=1000) as blocker:
        click_pixel(view, 5, 5)
    assert blocker.args[0] == CYAN
    assert view.active_color() == CYAN
    assert scene.active_buffer() == before
    assert stack.count() == 0
