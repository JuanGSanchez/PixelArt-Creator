"""Dithering brush tool (REQ-P3-UI-008): ordered / Floyd–Steinberg onto a palette.

``DitherTool`` is a rectangular-region controller: a click-drag defines the target
region (a live dashed preview, D5) and, on release, the region is dithered onto the
active palette as **one** undoable command. The dither maths live in
:mod:`pixelart_creator.logic.dither`; this controller only maps the drag to a
:class:`~pixelart_creator.logic.selection.SelectionMask`, calls
:func:`~pixelart_creator.logic.dither.make_dither_command`, and wraps the returned
reversible :class:`~pixelart_creator.logic.history.Command` in one
:class:`~pixelart_creator.ui.commands.LogicCommand` (SC-U008-1/-2). No pixel maths
live here (Article I / S11). Dithering requires an RGBA buffer and a non-empty
palette; otherwise the interaction is a safe no-op.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QCoreApplication

from pixelart_creator.logic.dither import DitherError, make_dither_command
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.commands import LogicCommand
from pixelart_creator.ui.tools.base import Tool, ToolContext

Coord = Tuple[int, int]

#: The two dither modes accepted by ``logic.dither.make_dither_command``.
MODE_ORDERED = "ordered"
MODE_FLOYD_STEINBERG = "floyd_steinberg"


class DitherTool(Tool):
    """Drag a region, release to dither it onto the active palette (one command)."""

    tool_id = "dither"

    def __init__(self) -> None:
        """Start in ordered-dither mode with no bound palette and no active drag."""
        self._mode = MODE_ORDERED
        self._palette: Optional[Palette] = None
        self._start: Optional[Coord] = None

    # -- configuration (set by the shell) --------------------------------

    def set_mode(self, mode: str) -> None:
        """Select ``'ordered'`` or ``'floyd_steinberg'`` dithering."""
        if mode in (MODE_ORDERED, MODE_FLOYD_STEINBERG):
            self._mode = mode

    def mode(self) -> str:
        """Return the active dither mode."""
        return self._mode

    def set_palette(self, palette: Optional[Palette]) -> None:
        """Bind the active document palette (the dither target)."""
        self._palette = palette

    def label(self) -> str:
        """Return the translated undo-menu label for a dither commit."""
        return QCoreApplication.translate("tools", "Dither")

    # -- interaction ------------------------------------------------------

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        """Record the drag's start corner."""
        self._start = (x, y)

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        """Show a live dashed rectangle preview of the dither region."""
        if self._start is None:
            return
        sx, sy = self._start
        ctx.scene.show_shape_preview(
            "rectangle", sx, sy, x, y, ctx.active_color, filled=False, dashed=True
        )

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        """Dither the dragged region onto the active palette as one command."""
        if self._start is None:
            return
        sx, sy = self._start
        self._start = None
        ctx.scene.hide_shape_preview()
        if self._palette is None or len(self._palette) == 0:
            return
        if ctx.buffer.mode is not ColorMode.RGBA:
            return
        mask = rect_mask(ctx.buffer.width, ctx.buffer.height, sx, sy, x, y)
        if mask.is_empty:
            return
        try:
            command = make_dither_command(ctx.buffer, self._palette, self._mode, mask)
        except (DitherError, PaletteError):
            return
        ctx.undo_stack.push(LogicCommand(command, ctx.scene.refresh_all, self.label()))


__all__ = ["DitherTool", "MODE_ORDERED", "MODE_FLOYD_STEINBERG"]
