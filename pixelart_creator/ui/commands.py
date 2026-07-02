"""Qt undo bridge — the sole Qt-aware undo module (REQ-P1-UI-009, -010; C1/F1).

``PaintCommand`` wraps a Qt-free :class:`~pixelart_creator.logic.history.PixelEdit`
(captured by :func:`~pixelart_creator.logic.history.record_edit`) so a
:class:`QUndoStack` can drive it. ``LogicCommand`` wraps **any** unapplied
:class:`~pixelart_creator.logic.history.Command` returned by the Phase-2 logic
builders (selection move, flip / rotate-90 / scale, RotSprite, symmetry stroke,
pixel-perfect stroke, tiled edit). ``redo()``/``undo()`` **delegate** to the
logic command — this module holds **no** domain math (Article I); it only bridges
Qt's undo framework to the logic command and schedules a repaint/rebind (D5).

``QUndoStack``/``QUndoCommand`` are imported from ``PySide6.QtGui`` (moved from
``QtWidgets`` in Qt6 — F1). ``LogicCommand`` is the single wrapper class every new
mutating op reuses, so the QUndoStack in this module stays the only undo system
(C1) and no domain logic leaks into the widgets (S11).

Phase-3 note: a colour-hub pick (wheel / harmony / favourite) sets the **active
paint colour** — a tool-state change, not a buffer mutation — so it creates **no**
``QUndoCommand`` and never touches the undo stack (REQ-P3-UI-006, T17). The Slice-3C
mutating ops all reuse :class:`LogicCommand` (T21): the buffer ops
(dither / constraint / cycle / swap) pass the unapplied ``PixelEdit`` returned by
their ``logic`` builder, and the palette-editor edits (add / remove / reorder /
import) pass a :class:`~pixelart_creator.logic.history.FunctionCommand` whose
do/undo replace the shared ``Palette``'s contents in place (plan §10). ``redo()``
fires on push (applying the op) and every later redo/undo delegates to the logic
command, so each op is exactly one reversible step with **zero** domain maths in
this bridge (Article I / S11).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QUndoCommand

from pixelart_creator.logic.history import Command, PixelEdit

#: Called with the dirty rect (scene/pixel coords) after every apply/revert so
#: the view can repaint only the affected region (D5).
RefreshCallback = Callable[[QRectF], None]

#: Called (no args) after a whole-buffer / dimension-changing op so the view can
#: rebind the scene and repaint (dirty-rect scope is AGT-10's concern).
RebindCallback = Callable[[], None]


class PaintCommand(QUndoCommand):
    """A single undoable stroke: one :class:`PixelEdit`, one dirty rect (CL-9).

    The ``edit`` has already been applied to its buffer by ``record_edit`` (it
    was built with ``execute=False`` semantics), so the first ``redo()`` — which
    :meth:`QUndoStack.push` fires automatically — must **not** re-apply it;
    subsequent redos (after an undo) re-run ``execute()``.

    Args:
        edit: The reversible pixel edit to bridge.
        refresh: Callback repainting the dirty rect (D5); receives ``dirty_rect``.
        dirty_rect: Bounding rect of the changed pixels, in scene/pixel coords.
        text: Undo-menu label; defaults to the edit's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        edit: PixelEdit,
        refresh: RefreshCallback,
        dirty_rect: QRectF,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        super().__init__(text or edit.label, parent)
        self._edit = edit
        self._refresh = refresh
        self._dirty_rect = QRectF(dirty_rect)
        self._applied = True  # record_edit already applied it once.

    def redo(self) -> None:
        """Re-apply the edit (skipping the redundant first apply-on-push)."""
        if self._applied:
            self._applied = False
        else:
            self._edit.execute()
        self._refresh(self._dirty_rect)

    def undo(self) -> None:
        """Revert exactly the pixels the edit changed, then repaint them."""
        self._edit.undo()
        self._applied = False
        self._refresh(self._dirty_rect)


class LogicCommand(QUndoCommand):
    """Bridge for an **unapplied** logic :class:`Command` (Phase-2 mutating ops).

    Unlike :class:`PaintCommand` (whose edit was pre-applied by ``record_edit``),
    the Phase-2 builders — ``selection.move_selection``,
    ``transform.make_transform_command``, ``rotsprite.make_rotsprite_command``,
    ``tiled.make_tiled_command`` — return their command **unapplied**. Qt's
    :meth:`QUndoStack.push` fires ``redo()`` once on push, which applies it; every
    later redo/undo delegates to the logic command's ``execute()``/``undo()``, so
    the whole op is exactly one undoable step (SC-U*-3) with the inverse being the
    logic command's own inverse (``apply ∘ undo = identity``, NFR-3).

    Args:
        command: The unapplied reversible logic command to bridge.
        rebind: Callback repainting/rebinding the view after apply or revert.
            Whole-buffer / dimension-changing ops pass a scene rebind; same-size
            edits pass a full-buffer refresh.
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        command: Command,
        rebind: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        super().__init__(text or command.label, parent)
        self._command = command
        self._rebind = rebind

    def redo(self) -> None:
        """Apply (or re-apply) the logic command, then repaint/rebind."""
        self._command.execute()
        self._rebind()

    def undo(self) -> None:
        """Revert the logic command exactly, then repaint/rebind."""
        self._command.undo()
        self._rebind()
