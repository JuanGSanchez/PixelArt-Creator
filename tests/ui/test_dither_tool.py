"""Dithering-brush acceptance tests (REQ-P3-UI-008).

One test per acceptance criterion for :class:`DitherTool` driven through the
canvas view headlessly:

* SC-U008-1 an ordered/Bayer stroke commits as ONE undoable command whose output
  uses only palette colours (⊆ palette); undo restores the buffer exactly.
* SC-U008-2 a Floyd–Steinberg stroke commits as ONE undoable command (⊆ palette).
* SC-U008-3 the dither tool is tr()-wrapped and mode-selectable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import numpy as np

from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.tools.dither_tool import (
    MODE_FLOYD_STEINBERG,
    MODE_ORDERED,
    DitherTool,
)
from tests.ui._ui_helpers import drag_path

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]
REGION = [(2, 2), (2, 2), (9, 9)]


def _region_colors(buffer, x0, y0, x1, y1):
    return {
        tuple(int(v) for v in buffer.get_pixel(x, y))
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
    }


def _prepare(make_view, mode):
    view, scene, stack = make_view()
    palette = Palette(STARTER)
    # Seed the region with a mid grey so dithering resolves to >1 palette colour.
    buffer = scene.active_buffer()
    for y in range(2, 10):
        for x in range(2, 10):
            buffer.set_pixel(x, y, (128, 128, 128, 255))
    tool = DitherTool()
    tool.set_palette(palette)
    tool.set_mode(mode)
    view.set_tool(tool)
    return view, scene, stack, buffer, palette


# -- SC-U008-1 (ordered stroke: one command, ⊆ palette, undoable) --------------


def test_sc_u008_1_ordered_stroke_is_one_command_subset_of_palette(make_view):
    """SC-U008-1: an ordered dither is one undoable command; output ⊆ palette."""
    view, _scene, stack, buffer, palette = _prepare(make_view, MODE_ORDERED)
    before = buffer.data.copy()
    drag_path(view, REGION)
    assert stack.count() == 1
    assert _region_colors(buffer, 2, 2, 9, 9).issubset(set(palette.colors()))
    stack.undo()
    assert np.array_equal(buffer.data, before)


# -- SC-U008-2 (Floyd–Steinberg stroke: one command, ⊆ palette) ----------------


def test_sc_u008_2_floyd_steinberg_stroke_is_one_command_subset(make_view):
    """SC-U008-2: a Floyd–Steinberg dither is one undoable command; output ⊆ palette."""
    view, _scene, stack, buffer, palette = _prepare(make_view, MODE_FLOYD_STEINBERG)
    drag_path(view, REGION)
    assert stack.count() == 1
    assert _region_colors(buffer, 2, 2, 9, 9).issubset(set(palette.colors()))


# -- SC-U008-3 (tr()-wrapped label + mode selectable, both themes) -------------


def test_sc_u008_3_tool_label_and_modes(qtbot):
    """SC-U008-3: the tool carries a translated label and switches modes."""
    tool = DitherTool()
    assert tool.label() != ""
    tool.set_mode(MODE_FLOYD_STEINBERG)
    assert tool.mode() == MODE_FLOYD_STEINBERG
    tool.set_mode(MODE_ORDERED)
    assert tool.mode() == MODE_ORDERED


# -- guard / edge-path coverage (defensive branches) ---------------------------


def test_invalid_mode_is_ignored(qtbot):
    """An unrecognised mode is rejected, leaving the current mode intact."""
    tool = DitherTool()
    tool.set_mode("bogus")
    assert tool.mode() == MODE_ORDERED


def _ctx(scene, buffer, stack):
    from pixelart_creator.ui.tools.base import ToolContext

    return ToolContext(
        buffer=buffer,
        active_color=(0, 0, 0, 255),
        undo_stack=stack,
        scene=scene,
        set_active_color=lambda _c: None,
    )


def test_move_and_release_without_press_are_no_ops(make_scene):
    """on_move / on_release before a press do nothing (start is None)."""
    from PySide6.QtGui import QUndoStack

    scene = make_scene()
    tool = DitherTool()
    tool.set_palette(Palette(STARTER))
    ctx = _ctx(scene, scene.active_buffer(), QUndoStack())
    tool.on_move(3, 3, ctx)  # no press yet
    tool.on_release(3, 3, ctx)  # no press yet
    assert ctx.undo_stack.count() == 0


def test_release_without_palette_is_no_op(make_scene):
    """A release with no bound palette commits nothing."""
    from PySide6.QtGui import QUndoStack

    scene = make_scene()
    tool = DitherTool()  # no palette bound
    ctx = _ctx(scene, scene.active_buffer(), QUndoStack())
    tool.on_press(2, 2, ctx)
    tool.on_release(6, 6, ctx)
    assert ctx.undo_stack.count() == 0


def test_release_on_indexed_buffer_is_no_op(make_scene):
    """Dithering requires an RGBA buffer; an indexed buffer is a safe no-op."""
    from PySide6.QtGui import QUndoStack

    from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

    scene = make_scene()
    tool = DitherTool()
    tool.set_palette(Palette(STARTER))
    indexed = PixelBuffer(16, 16, ColorMode.INDEXED)
    ctx = _ctx(scene, indexed, QUndoStack())
    tool.on_press(2, 2, ctx)
    tool.on_release(6, 6, ctx)
    assert ctx.undo_stack.count() == 0
