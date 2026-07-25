"""Shared selection-tool controller: build masks, combine, and move (P2-UI-004..007).

:class:`SelectionTool` factors the rectangle / lasso / magic-wand controllers'
common behaviour. When a press lands **inside** the active selection (no Shift add
gesture) it starts a **non-destructive floating** move/copy through the view's
:class:`~pixelart_creator.ui.tools.floating_move.FloatingMoveController`
(REQ-P2-UI-030..034): drag updates the offset, Ctrl during the drag switches
to COPY (CL-F5), and release commits **one**
:class:`~pixelart_creator.ui.commands.LogicCommand`. Pressing **outside** the mask
previews and, on release, builds a new :class:`SelectionMask` combined with the
current selection by the Shift-add / Alt-subtract modifiers (CL-4). All mask
geometry and the vacate/composite maths live in ``logic/selection`` (Article I /
S11); this controller only routes input.
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt

from pixelart_creator.logic.selection import (
    COMBINE_ADD,
    COMBINE_REPLACE,
    COMBINE_SUBTRACT,
    SelectionMask,
)
from pixelart_creator.ui.tools.base import Tool, ToolContext

Coord = Tuple[int, int]

#: Modifier that, held during an in-selection drag, switches MOVE → COPY (CL-F5).
#: Ctrl ONLY — Alt stays the shipped CL-4 interior subtract gesture (REQ-P2-UI-004).
_COPY_MODIFIERS = Qt.KeyboardModifier.ControlModifier


class SelectionTool(Tool):
    """Abstract selection controller (preview + combine + floating move)."""

    #: Whether an in-selection press starts a floating move (False for the wand,
    #: whose click always (re)selects rather than moving).
    _allow_move = True

    def __init__(self) -> None:
        self._start: Optional[Coord] = None
        self._moving = False

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
        selection = ctx.selection
        controller = ctx.floating_controller
        # A Shift OR Alt press routes to the build path (combine add / subtract),
        # so the shipped CL-4 interior combine gestures are preserved: only a plain
        # interior press (MOVE) or a Ctrl interior press (COPY) starts a floating
        # move (CL-F5). Alt is the shipped subtract modifier (REQ-P2-UI-004 /
        # SC-U004-2) and must never be read as a copy trigger on the floating path.
        shift = bool(ctx.modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(ctx.modifiers & Qt.KeyboardModifier.AltModifier)
        inside = (
            self._allow_move
            and selection is not None
            and not selection.is_empty
            and selection.is_selected(x, y)
        )
        if inside and not shift and not alt and controller is not None:
            if controller.begin(x, y, ctx, label=self.label()):
                self._moving = True
                return
        self.begin(x, y, ctx)

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        if self._moving:
            sx, sy = self._start
            copy = bool(ctx.modifiers & _COPY_MODIFIERS)
            if ctx.floating_controller is not None:
                ctx.floating_controller.update(x - sx, y - sy, copy=copy)
            return
        self.update(x, y, ctx)

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        if self._start is None:
            return
        sx, sy = self._start
        self._start = None
        if self._moving:
            self._moving = False
            if ctx.floating_controller is not None:
                ctx.floating_controller.commit()
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
