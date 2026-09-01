# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tool controllers (REQ-P1-UI-011..016).

Thin presentation controllers that translate canvas mouse events into
``logic/drawing.py`` primitives and push **one** :class:`PaintCommand` per
completed interaction (CL-9). They hold **no** domain math (Article I) — all
pixel geometry lives in ``logic/drawing.py``.
"""

from __future__ import annotations

from pixelart_creator.ui.tools.base import Tool, ToolContext
from pixelart_creator.ui.tools.dither_tool import DitherTool
from pixelart_creator.ui.tools.ellipse_tool import EllipseTool
from pixelart_creator.ui.tools.eraser import EraserTool
from pixelart_creator.ui.tools.fill import FloodFillTool
from pixelart_creator.ui.tools.lasso_tool import LassoTool
from pixelart_creator.ui.tools.line import LineTool
from pixelart_creator.ui.tools.magic_wand_tool import MagicWandTool
from pixelart_creator.ui.tools.pencil import PencilTool
from pixelart_creator.ui.tools.picker import PickerTool
from pixelart_creator.ui.tools.rect_select_tool import RectSelectTool
from pixelart_creator.ui.tools.rectangle_tool import RectangleTool
from pixelart_creator.ui.tools.selection_base import SelectionTool
from pixelart_creator.ui.tools.shape_base import ShapeTool

__all__ = [
    "Tool",
    "ToolContext",
    "PencilTool",
    "EraserTool",
    "FloodFillTool",
    "LineTool",
    "PickerTool",
    "ShapeTool",
    "RectangleTool",
    "EllipseTool",
    "SelectionTool",
    "RectSelectTool",
    "LassoTool",
    "MagicWandTool",
    "DitherTool",
]
