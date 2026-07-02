"""Tool-controller guard/no-op branch coverage (REQ-P1-UI-011..016; CL-9/-12).

These exercise the controllers' defensive no-op paths (a move/release with no
active stroke, an off-buffer or unchanged interaction, indexed-mode erase, an
out-of-bounds or indexed pick) directly through a :class:`ToolContext`, proving
the "no command when nothing changed" contract. Both themes.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.tools import EraserTool, LineTool, PencilTool, PickerTool
from pixelart_creator.ui.tools.base import Stroke, ToolContext, bounding_rect

RED = (230, 30, 30, 255)
BLUE = (40, 90, 220, 255)


def _ctx(scene, color=BLUE, picked=None):
    if picked is None:
        picked = []
    return ToolContext(
        buffer=scene.active_buffer(),
        active_color=color,
        undo_stack=QUndoStack(),
        scene=scene,
        set_active_color=picked.append,
    )


def _rgba_scene():
    return CanvasScene(Document(16, 16, palette=Palette([RED, BLUE])))


def _indexed_scene():
    doc = Document(16, 16, mode=ColorMode.INDEXED, palette=Palette([RED, BLUE]))
    return CanvasScene(doc)


def test_pencil_move_release_without_press_are_noops():
    """A pencil move/release with no active stroke does nothing (guard)."""
    scene = _rgba_scene()
    ctx = _ctx(scene)
    tool = PencilTool()
    tool.on_move(1, 1, ctx)  # no prior on_press
    tool.on_release(1, 1, ctx)
    assert ctx.undo_stack.count() == 0


def test_line_move_release_without_press_are_noops():
    """A line move/release with no start point does nothing (guard, CL-11)."""
    scene = _rgba_scene()
    ctx = _ctx(scene)
    tool = LineTool()
    tool.on_move(2, 2, ctx)
    tool.on_release(2, 2, ctx)
    assert ctx.undo_stack.count() == 0


def test_line_off_buffer_press_release_pushes_no_command():
    """A line entirely off-buffer commits no command (CL-12)."""
    scene = _rgba_scene()
    ctx = _ctx(scene)
    tool = LineTool()
    tool.on_press(100, 100, ctx)
    tool.on_release(120, 120, ctx)
    assert ctx.undo_stack.count() == 0


def test_stroke_no_change_yields_no_command():
    """Re-painting a pixel with its existing value yields no command (diff-empty)."""
    scene = _rgba_scene()
    scene.active_buffer().set_pixel(0, 0, BLUE)
    stroke = Stroke(scene.active_buffer())
    stroke.pencil(0, 0, BLUE)  # value unchanged
    assert stroke.to_command(scene.refresh_rect, "noop") is None


def test_bounding_rect_and_last_rect_helpers():
    """bounding_rect of an empty set is empty; last_rect wraps bounding_rect."""
    assert bounding_rect(set()) == QRectF()
    stroke = Stroke(_rgba_scene().active_buffer())
    assert stroke.last_rect({(1, 1), (3, 4)}) == bounding_rect({(1, 1), (3, 4)})


def test_eraser_value_indexed_is_zero():
    """The eraser clears an indexed buffer to index 0 (REQ-P1-UI-013)."""
    scene = _indexed_scene()
    ctx = _ctx(scene)
    assert EraserTool().value(ctx) == 0


def test_eraser_value_rgba_is_transparent():
    """The eraser clears an RGBA buffer to transparent (REQ-P1-UI-013)."""
    scene = _rgba_scene()
    ctx = _ctx(scene)
    assert EraserTool().value(ctx) == TRANSPARENT


def test_picker_out_of_bounds_sets_nothing():
    """A picker click outside the buffer sets no active colour (guard)."""
    scene = _rgba_scene()
    picked: list = []
    ctx = _ctx(scene, picked=picked)
    PickerTool().on_press(100, 100, ctx)
    assert picked == []


def test_picker_indexed_pixel_sets_nothing_directly():
    """Picking an indexed pixel (an int, not an RGBA tuple) sets no colour."""
    scene = _indexed_scene()
    scene.active_buffer().set_pixel(3, 3, 1)
    picked: list = []
    ctx = _ctx(scene, picked=picked)
    PickerTool().on_press(3, 3, ctx)
    assert picked == []  # an int index is not applied as the active RGBA colour


def test_plain_buffer_helpers_unused_paths():
    """A bare PixelBuffer round-trips through Stroke without a scene refresh."""
    buf = PixelBuffer(4, 4)
    stroke = Stroke(buf)
    stroke.pencil(1, 1, BLUE)
    assert stroke.touched_rect() == bounding_rect({(1, 1)})
