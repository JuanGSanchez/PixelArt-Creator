"""Magic-wand selection-tool acceptance (REQ-P2-UI-006).

Scenarios SC-U006-1 (a click selects the contiguous colour region as the active
mask) and SC-U006-2 (the tolerance control changes the selected extent). Both
themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from pixelart_creator.ui.tools import MagicWandTool
from tests.ui._ui_helpers import click_pixel

RED = (230, 30, 30, 255)
NEAR_RED = (230, 30, 40, 255)  # differs from RED by 10 in the blue channel


def _fill_block(buf, x0, y0, x1, y1, color):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            buf.set_pixel(x, y, color)


def test_sc_u006_1_click_selects_contiguous_region(make_view):
    """SC-U006-1: a wand click selects the contiguous same-colour region only."""
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    _fill_block(buf, 0, 0, 3, 3, RED)  # block A
    _fill_block(buf, 10, 10, 12, 12, RED)  # separate block B (same colour)
    tool = MagicWandTool()
    tool.set_tolerance(0)
    view.set_tool(tool)
    click_pixel(view, 1, 1)
    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # inside block A
    assert not mask.is_selected(11, 11)  # block B is not contiguous with A


def test_sc_u006_2_tolerance_changes_extent(make_view):
    """SC-U006-2: raising the tolerance includes an adjacent near-colour pixel."""
    view, scene, _stack = make_view(16, 16)
    buf = scene.active_buffer()
    _fill_block(buf, 0, 0, 3, 3, RED)
    buf.set_pixel(4, 0, NEAR_RED)  # a near-colour pixel adjacent to the block

    exact = MagicWandTool()
    exact.set_tolerance(0)
    view.set_tool(exact)
    click_pixel(view, 1, 0)
    tight = view.active_selection()
    assert tight is not None and not tight.is_selected(4, 0)

    view.clear_selection()
    loose = MagicWandTool()
    loose.set_tolerance(2000)  # squared-RGBA units; comfortably includes NEAR_RED
    view.set_tool(loose)
    click_pixel(view, 1, 0)
    wide = view.active_selection()
    assert wide is not None and wide.is_selected(4, 0)
    assert wide.count() > tight.count()
