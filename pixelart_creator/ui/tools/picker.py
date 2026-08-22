"""Colour-picker tool (REQ-P1-UI-016): read a pixel, set the active colour."""

from __future__ import annotations

from pixelart_creator.logic import drawing
from pixelart_creator.ui.tools.base import Tool, ToolContext


class PickerTool(Tool):
    """Reads the colour under the cursor and sets it as the active colour (S4).

    Picking does not mutate the buffer and pushes no undo command (CL-10). For
    an RGBA buffer the picked value is an RGBA tuple set directly; an indexed
    pixel is resolved to its palette colour.
    """

    tool_id = "picker"

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        """Read the pixel at (x, y) and set it as the active colour; mutate nothing."""
        if not ctx.buffer.in_bounds(x, y):
            return
        value = drawing.pick_color(ctx.buffer, x, y)
        if isinstance(value, tuple):
            ctx.set_active_color(value)
            return
        # Indexed buffer: `value` is a palette index (REQ-P1-UI-016). Resolve it
        # to its RGBA colour through the context's palette resolver so
        # `set_active_color` runs the same active-swatch path as an RGBA pick;
        # `Main_Window._set_active_color` then aligns the paint-by-index value
        # to the matching palette entry (REQ-P3-UI-014), so a subsequent stroke
        # paints with the picked index. A stale index with no matching palette
        # entry (or no resolver, e.g. a bare test context) resolves to `None`
        # and the pick is a silent no-op, never a crash.
        if ctx.resolve_palette_color is not None:
            color = ctx.resolve_palette_color(value)
            if color is not None:
                ctx.set_active_color(color)
