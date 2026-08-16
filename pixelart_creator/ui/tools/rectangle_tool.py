"""Rectangle shape tool (REQ-P2-UI-001, -003): live preview, commit as one command."""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic import drawing
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue
from pixelart_creator.ui.tools.shape_base import ShapeTool

Coord = Tuple[int, int]


class RectangleTool(ShapeTool):
    """Drags out a rectangle; commits ``drawing.rectangle`` on release (SC-U001)."""

    tool_id = "rectangle"

    def kind(self) -> str:
        """Return the rectangle preview kind."""
        return "rectangle"

    def label(self) -> str:
        """Return the translated undo-menu label for a rectangle."""
        return QCoreApplication.translate("tools", "Rectangle")

    def _draw_op(
        self,
        buffer: PixelBuffer,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        value: PixelValue,
    ) -> List[Coord]:
        """Delegate to ``drawing.rectangle`` (outline/filled per the shared mode)."""
        return drawing.rectangle(buffer, x0, y0, x1, y1, value, filled=self.filled)
