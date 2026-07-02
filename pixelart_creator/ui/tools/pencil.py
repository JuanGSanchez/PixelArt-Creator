"""Pencil tool (REQ-P1-UI-012): paint pixels with the active colour."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.pixel_buffer import PixelValue
from pixelart_creator.ui.tools.base import Stroke, Tool, ToolContext, bounding_rect


class PencilTool(Tool):
    """Paints the clicked/dragged pixel(s), coalescing a drag into one command."""

    tool_id = "pencil"

    def __init__(self) -> None:
        self._stroke: Optional[Stroke] = None
        self._last: Optional[Tuple[int, int]] = None

    def label(self) -> str:
        """Translated undo-menu label for a pencil stroke."""
        return QCoreApplication.translate("tools", "Pencil")

    def value(self, ctx: ToolContext) -> PixelValue:
        """The value plotted (overridden by the eraser)."""
        return ctx.active_color

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        self._stroke = Stroke(ctx.buffer)
        self._stroke.pencil(x, y, self.value(ctx))
        self._last = (x, y)
        ctx.scene.refresh_rect(bounding_rect({(x, y)}))

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._stroke is None or self._last is None:
            return
        lx, ly = self._last
        self._stroke.line(lx, ly, x, y, self.value(ctx))
        ctx.scene.refresh_rect(bounding_rect({(lx, ly), (x, y)}))
        self._last = (x, y)

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._stroke is None:
            return
        command = self._stroke.to_command(ctx.scene.refresh_rect, self.label())
        if command is not None:
            ctx.undo_stack.push(command)
        self._stroke = None
        self._last = None
