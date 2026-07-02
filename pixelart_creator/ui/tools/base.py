"""Tool-controller contract + stroke helper (REQ-P1-UI-011; CL-9/-12).

A :class:`Tool` maps floored pixel coordinates (CL-12) to ``logic/drawing.py``
primitives and, via :class:`Stroke`, coalesces a whole click-drag into a single
reversible :class:`~pixelart_creator.logic.history.PixelEdit` (CL-9) wrapped in a
:class:`~pixelart_creator.ui.commands.PaintCommand`. The controllers hold no
pixel math — that lives in ``logic/drawing.py`` (Article I). This module only
performs undo bookkeeping (capture-before / diff-after, the same pattern as
:func:`logic.history.record_edit`) and Qt wiring.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Set, Tuple

from PySide6.QtCore import QRectF
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic import drawing
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.history import PixelChange, PixelEdit
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.commands import PaintCommand

Coord = Tuple[int, int]


def bounding_rect(coords: Set[Coord]) -> QRectF:
    """Return the inclusive pixel bounding rect of ``coords`` (empty if none)."""
    if not coords:
        return QRectF()
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    x0, y0 = min(xs), min(ys)
    return QRectF(x0, y0, max(xs) - x0 + 1, max(ys) - y0 + 1)


class Stroke:
    """Accumulates a drag's pixel changes into one reversible edit (CL-9).

    A snapshot is taken at construction; primitives mutate the live buffer and
    report the coordinates they touched. :meth:`to_command` diffs the touched
    pixels against the snapshot to build a minimal :class:`PixelEdit`.
    """

    def __init__(self, buffer: PixelBuffer) -> None:
        self._buffer = buffer
        self._before = buffer.copy()
        self._touched: Set[Coord] = set()

    def pencil(self, x: int, y: int, value: PixelValue) -> None:
        """Plot a single pixel through ``drawing.pencil``."""
        self._touched.update(drawing.pencil(self._buffer, x, y, value))

    def line(self, x0: int, y0: int, x1: int, y1: int, value: PixelValue) -> None:
        """Plot a Bresenham segment through ``drawing.line`` (gap-free drag)."""
        self._touched.update(drawing.line(self._buffer, x0, y0, x1, y1, value))

    def flood_fill(self, x: int, y: int, value: PixelValue) -> None:
        """Fill the contiguous region through ``drawing.flood_fill``."""
        self._touched.update(drawing.flood_fill(self._buffer, x, y, value))

    def last_rect(self, coords: Set[Coord]) -> QRectF:
        """Bounding rect of a coord set (for live dirty-rect refresh, D5)."""
        return bounding_rect(coords)

    def touched_rect(self) -> QRectF:
        """Bounding rect of every pixel touched so far."""
        return bounding_rect(self._touched)

    def to_command(
        self,
        refresh: Callable[[QRectF], None],
        label: str,
    ) -> Optional[PaintCommand]:
        """Build a :class:`PaintCommand`, or ``None`` if nothing changed (CL-12/-14)."""
        changes: List[PixelChange] = []
        for x, y in sorted(self._touched):
            old = self._before.get_pixel(x, y)
            new = self._buffer.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
        if not changes:
            return None
        edit = PixelEdit(self._buffer, changes, label=label)
        return PaintCommand(edit, refresh, self.touched_rect(), text=label)


class ToolContext:
    """The live editing context handed to a tool for one interaction.

    Attributes:
        buffer: The active layer buffer being edited.
        active_color: The active RGBA colour.
        undo_stack: The active document's undo stack.
        scene: The canvas scene (for dirty-rect refresh + line preview).
        set_active_color: Callback the picker uses to set the active colour.
    """

    def __init__(
        self,
        buffer: PixelBuffer,
        active_color: RGBA,
        undo_stack: QUndoStack,
        scene: CanvasScene,
        set_active_color: Callable[[RGBA], None],
    ) -> None:
        self.buffer = buffer
        self.active_color = active_color
        self.undo_stack = undo_stack
        self.scene = scene
        self.set_active_color = set_active_color


class Tool:
    """Abstract active-tool controller (one active at a time, REQ-P1-UI-011)."""

    #: Stable identifier used by the toolbar/shortcuts.
    tool_id: str = "tool"

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle a left-button press at floored pixel ``(x, y)``."""

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle a left-drag move at floored pixel ``(x, y)``."""

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle the left-button release that completes the interaction."""
