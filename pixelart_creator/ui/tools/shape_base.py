"""Shared shape-tool controller: live preview + commit-on-release (P2-UI-001..003).

:class:`ShapeTool` factors the rectangle/ellipse controllers' common behaviour: a
press-drag shows a live vector preview (no buffer mutation, no undo entry), and
release commits the shape as **one** :class:`~pixelart_creator.ui.commands.PaintCommand`
via the ``logic/drawing`` primitive. A shared filled/outline option (default
outline, CL-17) is passed to the primitive's ``filled=`` at commit. When a
selection is active the commit is mask-constrained (REQ-P2-LOGIC-006); when a
symmetry axis is active the drawn pixels are mirrored (REQ-P2-LOGIC-011). No
pixel geometry lives here — it is all in ``logic/drawing`` + ``logic/selection``
(Article I / S11).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue
from pixelart_creator.logic.selection import apply_masked
from pixelart_creator.ui.tools.base import Stroke, Tool, ToolContext, mirror_coords

Coord = Tuple[int, int]


class ShapeTool(Tool):
    """Abstract rectangle/ellipse controller (live preview, single-command commit)."""

    def __init__(self) -> None:
        self._start: Optional[Coord] = None
        #: Shared filled/outline mode; default outline (CL-17). Set by the shell.
        self.filled: bool = False

    # -- shared option (REQ-P2-UI-003) -----------------------------------

    def set_filled(self, filled: bool) -> None:
        """Set filled (vs outline) mode for the shape commit."""
        self.filled = bool(filled)

    # -- subclass hooks --------------------------------------------------

    def kind(self) -> str:
        """Return the preview kind (``"rectangle"`` / ``"ellipse"``)."""
        raise NotImplementedError

    def label(self) -> str:
        """Return the translated undo-menu label."""
        raise NotImplementedError

    def _draw_op(
        self,
        buffer: PixelBuffer,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        value: PixelValue,
    ) -> List[Coord]:
        """Run the ``logic/drawing`` primitive; return the changed coords."""
        raise NotImplementedError

    # -- interaction -----------------------------------------------------

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        self._start = (x, y)
        ctx.scene.show_shape_preview(
            self.kind(), x, y, x, y, ctx.active_color, filled=self.filled
        )

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        ctx.scene.show_shape_preview(
            self.kind(), sx, sy, x, y, ctx.active_color, filled=self.filled
        )

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        self._start = None
        ctx.scene.hide_shape_preview()
        # Commit with the mode-correct value (index on indexed buffers, P3-UI-014);
        # previews above use the RGBA active_color for display.
        value = ctx.paint_value()
        stroke = Stroke(ctx.buffer)

        def op(buffer: PixelBuffer) -> List[Coord]:
            return self._draw_op(buffer, sx, sy, x, y, value)

        mask = ctx.selection if ctx.selection and not ctx.selection.is_empty else None
        if mask is None:
            drawn = op(ctx.buffer)
            stroke.absorb(drawn)
            stroke.stamp(mirror_coords(drawn, ctx), value)
        else:
            drawn = apply_masked(ctx.buffer, op, mask)
            stroke.absorb(drawn)
            mirrored = [c for c in mirror_coords(drawn, ctx) if mask.is_selected(*c)]
            stroke.stamp(mirrored, value)

        command = stroke.to_command(
            ctx.scene.refresh_rect, self.label(), ctx.scene.invalidate_group_caches
        )
        if command is not None:
            ctx.undo_stack.push(command)
