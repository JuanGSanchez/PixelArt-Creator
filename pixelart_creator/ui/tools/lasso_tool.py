"""Lasso selection tool (REQ-P2-UI-005): freehand path -> auto-closed mask."""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.selection import SelectionMask, lasso_mask
from pixelart_creator.ui.tools.base import ToolContext
from pixelart_creator.ui.tools.selection_base import SelectionTool

Coord = Tuple[int, int]


class LassoTool(SelectionTool):
    """Freehand drag traces a polygon; release builds the auto-closed lasso mask."""

    tool_id = "select_lasso"

    def __init__(self) -> None:
        super().__init__()
        self._points: List[Coord] = []

    def label(self) -> str:
        """Distinct translated name / undo-menu label for this tool (AGT-07)."""
        return QCoreApplication.translate("tools", "Lasso Select")

    def begin(self, x: int, y: int, ctx: ToolContext) -> None:
        self._points = [(x, y)]
        ctx.scene.show_polygon_preview(self._points, ctx.active_color)

    def update(self, x: int, y: int, ctx: ToolContext) -> None:
        if not self._points or self._points[-1] != (x, y):
            self._points.append((x, y))
            ctx.scene.show_polygon_preview(self._points, ctx.active_color)

    def build(
        self, sx: int, sy: int, x: int, y: int, ctx: ToolContext
    ) -> Optional[SelectionMask]:
        points = self._points if self._points else [(sx, sy), (x, y)]
        self._points = []
        return lasso_mask(ctx.buffer.width, ctx.buffer.height, points)
