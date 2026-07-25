"""Colour-picker tool (REQ-P1-UI-016): read a pixel, set the active colour."""

from __future__ import annotations

from pixelart_creator.logic import drawing
from pixelart_creator.ui.tools.base import Tool, ToolContext


class PickerTool(Tool):
    """Reads the colour under the cursor and sets it as the active colour (S4).

    Picking does not mutate the buffer and pushes no undo command (CL-16). For
    an RGBA buffer the picked value is an RGBA tuple set directly; an indexed
    pixel is resolved to its palette colour.
    """

    tool_id = "picker"

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        if not ctx.buffer.in_bounds(x, y):
            return
        value = drawing.pick_color(ctx.buffer, x, y)
        if isinstance(value, tuple):
            ctx.set_active_color(value)
