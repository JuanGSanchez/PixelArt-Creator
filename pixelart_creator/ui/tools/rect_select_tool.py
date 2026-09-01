# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Rectangle selection tool (REQ-P2-UI-004): drag a rectangle mask + combine."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.selection import SelectionMask, rect_mask
from pixelart_creator.ui.tools.base import ToolContext
from pixelart_creator.ui.tools.selection_base import SelectionTool


class RectSelectTool(SelectionTool):
    """Press-drag builds a rectangle :class:`SelectionMask` (live dashed preview)."""

    tool_id = "select_rect"

    def label(self) -> str:
        """Distinct translated name / undo-menu label for this tool."""
        return QCoreApplication.translate("tools", "Rectangle Select")

    def begin(self, x: int, y: int, ctx: ToolContext) -> None:
        """Show the initial zero-size dashed rectangle preview at (x, y)."""
        ctx.scene.show_shape_preview(
            "rectangle", x, y, x, y, ctx.active_color, dashed=True
        )

    def update(self, x: int, y: int, ctx: ToolContext) -> None:
        """Update the dashed rectangle preview to the current cursor position."""
        sx, sy = self._start if self._start else (x, y)
        ctx.scene.show_shape_preview(
            "rectangle", sx, sy, x, y, ctx.active_color, dashed=True
        )

    def build(
        self, sx: int, sy: int, x: int, y: int, ctx: ToolContext
    ) -> Optional[SelectionMask]:
        """Build the rectangle mask spanning the drag."""
        return rect_mask(ctx.buffer.width, ctx.buffer.height, sx, sy, x, y)
