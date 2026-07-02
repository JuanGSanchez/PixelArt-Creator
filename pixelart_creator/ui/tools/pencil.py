"""Pencil tool (REQ-P1-UI-012): paint pixels with the active colour.

Extended for Phase 2 with three orthogonal freehand modes routed through the
logic layer: **symmetry** mirrors each plotted pixel via ``logic.symmetry.mirror``
(REQ-P2-UI-011); **pixel-perfect** cleans the committed path via
``logic.pixel_perfect.pixel_perfect`` (REQ-P2-UI-012); **tiled** wraps the stroke
on the torus via ``logic.tiled.make_tiled_command`` (REQ-P2-UI-015). No pixel
geometry lives here — every mode delegates to ``logic/`` (Article I / S11).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.pixel_buffer import PixelValue
from pixelart_creator.logic.pixel_perfect import pixel_perfect
from pixelart_creator.logic.selection import _trace_line  # unclipped Bresenham (S11)
from pixelart_creator.logic.tiled import make_tiled_command, wrap
from pixelart_creator.ui.commands import LogicCommand
from pixelart_creator.ui.tools.base import (
    Stroke,
    Tool,
    ToolContext,
    bounding_rect,
    mirror_coords,
)

Coord = Tuple[int, int]


class PencilTool(Tool):
    """Paints the clicked/dragged pixel(s), coalescing a drag into one command."""

    tool_id = "pencil"

    def __init__(self) -> None:
        self._stroke: Optional[Stroke] = None
        self._last: Optional[Coord] = None
        self._raw: List[Coord] = []
        self._collect = False

    def label(self) -> str:
        """Translated undo-menu label for a pencil stroke."""
        return QCoreApplication.translate("tools", "Pencil")

    def value(self, ctx: ToolContext) -> PixelValue:
        """The value plotted (overridden by the eraser)."""
        return ctx.active_color

    def _plot_segment(self, coords: List[Coord], ctx: ToolContext) -> None:
        """Stamp a segment's symmetry mirrors and record it for deferred modes."""
        if self._stroke is None:
            return
        self._stroke.stamp(mirror_coords(coords, ctx), self.value(ctx))
        if self._collect:
            for c in coords:
                if not self._raw or self._raw[-1] != c:
                    self._raw.append(c)

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        self._stroke = Stroke(ctx.buffer)
        self._collect = ctx.pixel_perfect or ctx.tiled
        self._raw = []
        self._last = (x, y)
        if ctx.tiled:
            # Tiled mode: never drop off-buffer coords — wrap them (REQ-P2-UI-015).
            self._plot_tiled([(x, y)], ctx)
            return
        coords = self._stroke.pencil(x, y, self.value(ctx))
        self._plot_segment(coords, ctx)
        ctx.scene.refresh_rect(bounding_rect({(x, y)}))

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._stroke is None or self._last is None:
            return
        lx, ly = self._last
        if ctx.tiled:
            # Trace the full (unclipped) drag segment so cross-edge coords wrap.
            self._plot_tiled(_trace_line(lx, ly, x, y), ctx)
            self._last = (x, y)
            return
        coords = self._stroke.line(lx, ly, x, y, self.value(ctx))
        self._plot_segment(coords, ctx)
        ctx.scene.refresh_rect(bounding_rect({(lx, ly), (x, y)}))
        self._last = (x, y)

    def _plot_tiled(self, raw_coords: List[Coord], ctx: ToolContext) -> None:
        """Wrap each raw coord onto the torus and stamp it live (REQ-P2-UI-015).

        In tiled mode every coordinate is valid: an out-of-buffer coord wraps via
        :func:`logic.tiled.wrap` (CL-14) instead of being dropped by
        ``drawing._plot``, so a stroke crossing an edge paints the opposite edge.
        The wrapped coords are stamped for the live preview and recorded so
        :func:`make_tiled_command` commits the same torus-wrapped edit on release
        (fixes DEFECT UI-P2-01 / SC-U015-2). The wrap math stays in ``logic`` (S11).
        """
        if self._stroke is None:
            return
        value = self.value(ctx)
        w, h = ctx.buffer.width, ctx.buffer.height
        wrapped = [wrap(cx, cy, w, h) for cx, cy in raw_coords]
        self._stroke.stamp(wrapped, value)
        self._stroke.stamp(mirror_coords(wrapped, ctx), value)
        if self._collect:
            for c in wrapped:
                if not self._raw or self._raw[-1] != c:
                    self._raw.append(c)
        ctx.scene.refresh_rect(bounding_rect(set(wrapped)))

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._stroke is None:
            return
        if ctx.tiled:
            self._commit_tiled(ctx)
        elif ctx.pixel_perfect:
            self._commit_pixel_perfect(ctx)
        else:
            command = self._stroke.to_command(ctx.scene.refresh_rect, self.label())
            if command is not None:
                ctx.undo_stack.push(command)
        self._stroke = None
        self._last = None
        self._raw = []

    def _commit_tiled(self, ctx: ToolContext) -> None:
        """Rebuild the stroke as a torus-wrapped edit (one reversible command)."""
        assert self._stroke is not None
        value = self.value(ctx)
        coords = list(self._raw)
        coords.extend(mirror_coords(self._raw, ctx))
        self._stroke.revert_touched()  # discard the live in-bounds preview
        command = make_tiled_command(ctx.buffer, lambda: (coords, value))
        ctx.undo_stack.push(LogicCommand(command, ctx.scene.refresh_all, self.label()))

    def _commit_pixel_perfect(self, ctx: ToolContext) -> None:
        """Recommit the stroke as an elbow-cleaned 1-px path (one command)."""
        assert self._stroke is not None
        value = self.value(ctx)
        cleaned = pixel_perfect(self._raw)
        self._stroke.revert_touched()  # discard the live raw path
        self._stroke.stamp(cleaned, value)
        self._stroke.stamp(mirror_coords(cleaned, ctx), value)
        command = self._stroke.to_command(ctx.scene.refresh_rect, self.label())
        if command is not None:
            ctx.undo_stack.push(command)
