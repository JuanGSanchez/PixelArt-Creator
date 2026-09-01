# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Ellipse shape tool (REQ-P2-UI-002, -003): live preview, commit as one command."""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic import drawing
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue
from pixelart_creator.ui.tools.shape_base import ShapeTool

Coord = Tuple[int, int]


class EllipseTool(ShapeTool):
    """Drags out an ellipse; commits ``drawing.ellipse`` on release (SC-U002)."""

    tool_id = "ellipse"

    def kind(self) -> str:
        """Return the ellipse preview kind."""
        return "ellipse"

    def label(self) -> str:
        """Return the translated undo-menu label for an ellipse."""
        return QCoreApplication.translate("tools", "Ellipse")

    def _draw_op(
        self,
        buffer: PixelBuffer,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        value: PixelValue,
    ) -> List[Coord]:
        """Delegate to ``drawing.ellipse`` (outline/filled per the shared mode)."""
        return drawing.ellipse(buffer, x0, y0, x1, y1, value, filled=self.filled)
