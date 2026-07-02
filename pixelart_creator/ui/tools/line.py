"""Line tool (REQ-P1-UI-015): preview on drag, commit one command on release."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.ui.tools.base import Stroke, Tool, ToolContext


class LineTool(Tool):
    """Previews a straight line during drag; commits ``drawing.line`` on release.

    The preview does not mutate the buffer and pushes no command until release
    (CL-11), so the undo stack is never polluted by an in-progress drag.
    """

    tool_id = "line"

    def __init__(self) -> None:
        self._start: Optional[Tuple[int, int]] = None

    def label(self) -> str:
        """Translated undo-menu label for a line."""
        return QCoreApplication.translate("tools", "Line")

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        self._start = (x, y)
        ctx.scene.show_line_preview(x, y, x, y, ctx.active_color)

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        ctx.scene.show_line_preview(sx, sy, x, y, ctx.active_color)

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        ctx.scene.hide_line_preview()
        stroke = Stroke(ctx.buffer)
        stroke.line(sx, sy, x, y, ctx.active_color)
        command = stroke.to_command(ctx.scene.refresh_rect, self.label())
        if command is not None:
            ctx.undo_stack.push(command)
        self._start = None
