"""Floating-selection move/copy controller (REQ-P2-UI-030..035).

:class:`FloatingMoveController` routes the lift → move/copy → commit/cancel
lifecycle of a **non-destructive** floating selection. It owns at most one active
:class:`~pixelart_creator.logic.selection.FloatingSelection` and binds the
Qt-free logic surface to the canvas:

- ``begin`` lifts the masked pixels of the active buffer into a float (no buffer
  mutation) and shows the scene preview;
- ``update`` sets the live integer offset and the :class:`FloatMode` (Ctrl =
  COPY, CL-F5; Alt is the shipped CL-4 subtract, never copy) and asks the scene
  to recomposite only the dirty region;
- ``commit`` (release / Enter / tool-switch) pushes **exactly one**
  :class:`~pixelart_creator.ui.commands.LogicCommand` wrapping the unapplied
  ``commit_floating`` command, then follows the selection mask to the destination;
- ``cancel`` (Escape) discards the float — a pure no-op, since the base buffer was
  never written (ADR-0009 D1).

No domain math lives here (Article I / S11): the vacate/composite/commit maths are
all in ``logic/selection``; this controller only orchestrates the logic calls and
the scene overlay, and wraps the returned reversible command for Qt's undo stack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Protocol

from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.history import PixelEdit
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.logic.selection import (
    FloatingSelection,
    FloatMode,
    SelectionMask,
    commit_floating,
    lift_selection,
)
from pixelart_creator.ui.commands import LogicCommand

if TYPE_CHECKING:
    from pixelart_creator.ui.canvas_scene import CanvasScene

#: Notified ``(active, copy)`` whenever the float state changes (view → shell hint).
StateCallback = Callable[[bool, bool], None]

#: Sets the active selection mask after a commit (mask follows to the destination).
SetSelection = Callable[[Optional[SelectionMask]], None]


class LiftContext(Protocol):
    """The slice of ``ToolContext`` a lift needs (avoids a base↔tool import cycle).

    ``ToolContext`` (``ui/tools/base``) satisfies this structurally, so a lift can
    be typed without importing ``base`` — which would form a graph cycle with the
    ``base → floating_move`` seam import (``check_cycles``, Article I).
    """

    selection: Optional[SelectionMask]
    buffer: PixelBuffer
    scene: "CanvasScene"
    undo_stack: QUndoStack
    set_selection: Optional[SetSelection]
    target: Optional[EditTarget]


class FloatingMoveController:
    """Owns one active floating move/copy for a single view's canvas.

    Stateless between gestures: :meth:`begin` captures everything a later
    :meth:`commit`/:meth:`cancel` needs (buffer, scene, undo stack, origin mask),
    so Enter/Escape/tool-switch can finish a float without the originating
    :class:`~pixelart_creator.ui.tools.base.ToolContext`.
    """

    def __init__(self) -> None:
        """Create an idle controller with no active float."""
        self._floating: Optional[FloatingSelection] = None
        self._scene: Optional["CanvasScene"] = None
        self._buffer: Optional[PixelBuffer] = None
        self._undo_stack: Optional[QUndoStack] = None
        self._set_selection: Optional[SetSelection] = None
        self._origin_mask: Optional[SelectionMask] = None
        self._target: Optional[EditTarget] = None
        self._label = ""
        #: Optional observer (set by the view) fed ``(is_active, is_copy)``.
        self.state_changed: Optional[StateCallback] = None

    # -- state -----------------------------------------------------------

    def is_active(self) -> bool:
        """Whether a float is currently lifted (pre-commit)."""
        return self._floating is not None

    def is_copy(self) -> bool:
        """Whether the active float is in COPY mode."""
        return self._floating is not None and self._floating.mode is FloatMode.COPY

    # -- lifecycle -------------------------------------------------------

    def begin(self, x: int, y: int, ctx: LiftContext, *, label: str) -> bool:
        """Lift the active selection into a float if ``(x, y)`` is inside it.

        Returns ``True`` when a float was started (a MOVE at offset ``(0, 0)``;
        COPY is entered later by :meth:`update` when Ctrl is held). Returns
        ``False`` when there is no active, non-empty selection under the cursor —
        the caller then falls through to the build tools (REQ-P2-UI-030).
        """
        selection = ctx.selection
        if selection is None or selection.is_empty or not selection.is_selected(x, y):
            return False
        self._floating = lift_selection(ctx.buffer, selection, FloatMode.MOVE)
        self._scene = ctx.scene
        self._buffer = ctx.buffer
        self._undo_stack = ctx.undo_stack
        self._set_selection = ctx.set_selection
        self._origin_mask = selection
        self._target = ctx.target
        self._label = label
        ctx.scene.begin_floating(self._floating)
        ctx.scene.set_selection_move_offset(0, 0)
        self._notify()
        return True

    def update(self, dx: int, dy: int, *, copy: bool) -> None:
        """Set the live offset + mode; refresh the region preview (UI-031/-032).

        Switching MOVE↔COPY re-lifts the float with the new mode; this is sound
        because the base buffer is never written during a float, so the re-read
        colours equal the original snapshot (ADR-0009 D2). The marching-ants
        overlay follows the float to the offset.
        """
        if self._floating is None or self._scene is None:
            return
        mode = FloatMode.COPY if copy else FloatMode.MOVE
        if mode is not self._floating.mode:
            assert self._buffer is not None and self._origin_mask is not None
            self._floating = lift_selection(self._buffer, self._origin_mask, mode)
        self._floating.set_offset(dx, dy)
        self._scene.update_floating(self._floating)
        self._scene.set_selection_move_offset(dx, dy)
        self._notify()

    def commit(self) -> None:
        """Commit the float as exactly ONE undoable command (REQ-P2-UI-033/-035).

        A zero-change commit (zero offset, or a move onto identical pixels — CL-F8)
        pushes **no** command. On a real change the selection mask follows to the
        destination (SC-U033-4). Idempotent when no float is active.
        """
        if self._floating is None:
            return
        floating = self._floating
        scene = self._scene
        undo_stack = self._undo_stack
        set_selection = self._set_selection
        origin = self._origin_mask
        buffer = self._buffer
        target = self._target
        label = self._label
        dx, dy = floating.offset
        self._reset()
        assert buffer is not None and scene is not None and undo_stack is not None
        command = commit_floating(buffer, floating, target=target)
        if isinstance(command, PixelEdit) and len(command) == 0:
            # No net pixel change — no spurious undo step (CL-F8).
            scene.end_floating()
            scene.set_selection_move_offset(0, 0)
            self._notify()
            return
        undo_stack.push(LogicCommand(command, scene.refresh_all, label))
        scene.end_floating()
        scene.set_selection_move_offset(0, 0)
        if set_selection is not None and origin is not None:
            moved = origin.translate(dx, dy)
            set_selection(moved if not moved.is_empty else None)
        self._notify()

    def cancel(self) -> None:
        """Discard the active float (Escape) — no command, buffer untouched.

        Non-destructive by construction (REQ-P2-UI-034 / ADR-0009 D1): nothing was
        written during the float, so the pre-move canvas is restored exactly and
        the selection mask returns to its pre-lift position.
        """
        if self._floating is None:
            return
        scene = self._scene
        self._reset()
        if scene is not None:
            scene.end_floating()
            scene.set_selection_move_offset(0, 0)
        self._notify()

    # -- internals -------------------------------------------------------

    def _reset(self) -> None:
        """Drop all references to the finished float (release the buffers)."""
        self._floating = None
        self._scene = None
        self._buffer = None
        self._undo_stack = None
        self._set_selection = None
        self._origin_mask = None
        self._target = None
        self._label = ""

    def _notify(self) -> None:
        if self.state_changed is not None:
            self.state_changed(self.is_active(), self.is_copy())
