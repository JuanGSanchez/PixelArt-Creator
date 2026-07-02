"""Tool controllers (REQ-P1-UI-011..016).

Thin presentation controllers that translate canvas mouse events into
``logic/drawing.py`` primitives and push **one** :class:`PaintCommand` per
completed interaction (CL-9). They hold **no** domain math (Article I) — all
pixel geometry lives in ``logic/drawing.py``.
"""

from __future__ import annotations

from pixelart_creator.ui.tools.base import Tool, ToolContext
from pixelart_creator.ui.tools.eraser import EraserTool
from pixelart_creator.ui.tools.fill import FloodFillTool
from pixelart_creator.ui.tools.line import LineTool
from pixelart_creator.ui.tools.pencil import PencilTool
from pixelart_creator.ui.tools.picker import PickerTool

__all__ = [
    "Tool",
    "ToolContext",
    "PencilTool",
    "EraserTool",
    "FloodFillTool",
    "LineTool",
    "PickerTool",
]
