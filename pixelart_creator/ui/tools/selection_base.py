"""Shared selection-tool controller: build masks, combine, and move (P2-UI-004..007).

:class:`SelectionTool` factors the rectangle / lasso / magic-wand controllers'
common behaviour. When a press lands inside the active selection (no add/subtract
modifier) it starts a floating **move** (cut-move, CL-6) committed on release as
**one** :class:`~pixelart_creator.ui.commands.LogicCommand` via
``selection.move_selection``; otherwise the subclass previews and, on release,
builds a new :class:`SelectionMask` that is combined with the current selection by
the Shift-add / Alt-subtract modifiers (CL-4). All mask geometry lives in
``logic/selection`` (Article I / S11).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt

from pixelart_creator.logic.selection import (
    COMBINE_ADD,
    COMBINE_REPLACE,
    COMBINE_SUBTRACT,
    SelectionMask,
    move_selection,
)
from pixelart_creator.ui.commands import LogicCommand
from pixelart_creator.ui.tools.base import Tool, ToolContext

Coord = Tuple[int, int]


class SelectionTool(Tool):
    """Abstract selection controller (preview + combine + floating move)."""

    #: Whether an in-selection press starts a floating move (False for the wand,
    #: whose click always (re)selects rather than moving).
    _allow_move = True

    def __init__(self) -> None:
        self._start: Optional[Coord] = None
        self._moving = False
        self._move_mask: Optional[SelectionMask] = None

    # -- subclass hooks --------------------------------------------------

    def label(self) -> str:
        """Return the translated undo-menu label for a move of this selection."""
        raise NotImplementedError

    def begin(self, x: int, y: int, ctx: ToolContext) -> None:
        """Start the selection preview (subclass)."""

    def update(self, x: int, y: int, ctx: ToolContext) -> None:
        """Update the selection preview during the drag (subclass)."""

    def build(
        self, sx: int, sy: int, x: int, y: int, ctx: ToolContext
    ) -> Optional[SelectionMask]:
        """Build the new mask from the drag/click (subclass)."""
        raise NotImplementedError

    # -- combine ---------------------------------------------------------

    @staticmethod
    def _combine_mode(modifiers: Qt.KeyboardModifier) -> str:
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return COMBINE_ADD
        if modifiers & Qt.KeyboardModifier.AltModifier:
            return COMBINE_SUBTRACT
        return COMBINE_REPLACE

    # -- interaction -----------------------------------------------------

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        self._start = (x, y)
        self._moving = False
        self._move_mask = None
        selection = ctx.selection
        adjusting = bool(
            ctx.modifiers
            & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier)
        )
        if (
            self._allow_move
            and selection is not None
            and not selection.is_empty
            and not adjusting
        ):
            if selection.is_selected(x, y):
                self._moving = True
                self._move_mask = selection
                return
        self.begin(x, y, ctx)

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        if self._moving:
            sx, sy = self._start
            ctx.scene.set_selection_move_offset(x - sx, y - sy)
            return
        self.update(x, y, ctx)

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        self._start = None
        if self._moving:
            self._commit_move(sx, sy, x, y, ctx)
            return
        ctx.scene.hide_shape_preview()
        new_mask = self.build(sx, sy, x, y, ctx)
        if new_mask is None or ctx.set_selection is None:
            return
        current = ctx.selection
        if current is None or current.is_empty:
            result = new_mask
        else:
            result = current.combine(new_mask, self._combine_mode(ctx.modifiers))
        ctx.set_selection(result if not result.is_empty else None)

    def _commit_move(self, sx: int, sy: int, x: int, y: int, ctx: ToolContext) -> None:
        mask = self._move_mask
        self._moving = False
        self._move_mask = None
        ctx.scene.set_selection_move_offset(0, 0)
        dx, dy = x - sx, y - sy
        if mask is None or (dx == 0 and dy == 0):
            return
        command = move_selection(ctx.buffer, mask, dx, dy)
        ctx.undo_stack.push(LogicCommand(command, ctx.scene.refresh_all, self.label()))
        if ctx.set_selection is not None:
            moved = mask.translate(dx, dy)
            ctx.set_selection(moved if not moved.is_empty else None)
