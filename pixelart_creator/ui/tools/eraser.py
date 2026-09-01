# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Eraser tool (REQ-P1-UI-013): clear pixels to the buffer default."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelValue
from pixelart_creator.ui.tools.base import ToolContext
from pixelart_creator.ui.tools.pencil import PencilTool

#: Indexed buffers erase to palette index 0 (the buffer's own default value).
_INDEXED_ERASE_VALUE = 0


class EraserTool(PencilTool):
    """Clears the clicked/dragged pixel(s): RGBA→transparent, indexed→index 0."""

    tool_id = "eraser"

    def label(self) -> str:
        """Return the translated undo-menu label for an eraser stroke."""
        return QCoreApplication.translate("tools", "Eraser")

    def value(self, ctx: ToolContext) -> PixelValue:
        """Return the erase value for the active buffer's colour mode."""
        if ctx.buffer.mode is ColorMode.RGBA:
            return TRANSPARENT
        return _INDEXED_ERASE_VALUE
