"""Flood-fill tool (REQ-P1-UI-014): fill the contiguous region as one command."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from pixelart_creator.ui.tools.base import Stroke, Tool, ToolContext


class FloodFillTool(Tool):
    """Fills the contiguous region at the clicked pixel with the active colour.

    An in-bounds seed on an already-matching region (or an off-buffer click)
    changes nothing and pushes no command (CL-14/-12), mirroring the logic no-op.
    """

    tool_id = "fill"

    def label(self) -> str:
        """Translated undo-menu label for a fill."""
        return QCoreApplication.translate("tools", "Fill")

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        stroke = Stroke(ctx.buffer)
        # Paint-by-index on an indexed buffer; RGBA elsewhere (REQ-P3-UI-014).
        stroke.flood_fill(x, y, ctx.paint_value())
        command = stroke.to_command(ctx.scene.refresh_rect, self.label())
        if command is not None:
            ctx.undo_stack.push(command)
