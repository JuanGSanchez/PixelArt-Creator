"""Magic-wand selection tool (REQ-P2-UI-006): contiguous colour region + tolerance."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.constants import MAGIC_WAND_DEFAULT_TOLERANCE
from pixelart_creator.logic.selection import SelectionMask, wand_mask
from pixelart_creator.ui.tools.base import ToolContext
from pixelart_creator.ui.tools.selection_base import SelectionTool


class MagicWandTool(SelectionTool):
    """Click selects the contiguous same-colour region (tolerance-adjustable)."""

    tool_id = "select_wand"
    #: A wand click always (re)selects; it never starts a floating move.
    _allow_move = False

    def __init__(self) -> None:
        """Start with the default exact-match colour tolerance (CL-1)."""
        super().__init__()
        #: Colour tolerance; default exact match (CL-1). Set by the shell control.
        self.tolerance: int = MAGIC_WAND_DEFAULT_TOLERANCE

    def set_tolerance(self, tolerance: int) -> None:
        """Set the magic-wand colour tolerance (squared-RGBA units; 0 = exact)."""
        self.tolerance = int(tolerance)

    def label(self) -> str:
        """Distinct translated name for this tool (AGT-07; move is disabled)."""
        return QCoreApplication.translate("tools", "Magic Wand")

    def build(
        self, sx: int, sy: int, x: int, y: int, ctx: ToolContext
    ) -> Optional[SelectionMask]:
        """Build the mask of pixels contiguous with (x, y) within the tolerance."""
        return wand_mask(ctx.buffer, x, y, tolerance=self.tolerance)
