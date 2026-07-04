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

#: Called (no args) on both redo and undo of a pixel edit to drop the LayerGroup
#: flatten caches so a stale composite can never be served after the edit (D4;
#: AGT-03 ``Document.invalidate_caches`` via ``CanvasScene.invalidate_group_caches``).
InvalidateCallback = Callable[[], None]

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
        invalidate: Optional cache-safety hook fired **before** the repaint on
            both redo and undo (D4). It drops the LayerGroup flatten caches
            (``CanvasScene.invalidate_group_caches`` → ``Document.invalidate_caches``)
            so the region recomposite triggered by ``refresh`` cannot read a stale
            group composite for the edited pixels. ``None`` when the target buffer
            is not a composited RGBA layer.
    """

    def __init__(
        self,
        edit: PixelEdit,
        refresh: RefreshCallback,
        dirty_rect: QRectF,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
        *,
        invalidate: Optional[InvalidateCallback] = None,
    ) -> None:
        super().__init__(text or edit.label, parent)
        self._edit = edit
        self._refresh = refresh
        self._dirty_rect = QRectF(dirty_rect)
        self._invalidate = invalidate
        self._applied = True  # record_edit already applied it once.

    def redo(self) -> None:
        """Re-apply the edit (skipping the redundant first apply-on-push)."""
        if self._applied:
            self._applied = False
        else:
            self._edit.execute()
        # Drop stale group caches BEFORE the region recomposite the repaint fires.
        if self._invalidate is not None:
            self._invalidate()
        self._refresh(self._dirty_rect)

    def undo(self) -> None:
        """Revert exactly the pixels the edit changed, then repaint them."""
        self._edit.undo()
        self._applied = False
        if self._invalidate is not None:
            self._invalidate()
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


class FrameCommand(LogicCommand):
    """One ``QUndoCommand`` per frame/tag operation (T5C-02/-05, REQ-P5-UI-015).

    Wraps the **unapplied** :class:`~pixelart_creator.logic.history.Command` a
    ``logic/document`` frame or tag builder returns — add / remove / reorder /
    duplicate frame, set frame duration, add / edit / remove tag. Exactly like
    :class:`LogicCommand`, ``redo()`` applies the logic command on push (and on
    every later redo) and ``undo()`` reverts it exactly
    (``apply ∘ undo = identity``), so each timeline/tag edit is exactly one
    undoable step whose inverse restores the exact prior document state
    (REQ-P5-UI-015). Selection / scrub / playback / onion view-settings mutate no
    document state and therefore create **no** ``FrameCommand`` (CL-13).

    The ``refresh`` callback supplies only the Qt-side follow-up — invalidate the
    per-frame composite cache (indices shift on a structural frame op),
    recomposite/repaint the canvas, and rebuild the timeline strip + tag spans.
    No domain maths lives in this bridge (Article I / S11): the reversible logic
    is entirely the wrapped ``document`` command.

    Args:
        command: The unapplied reversible frame/tag-op command to bridge.
        refresh: Callback (no args) refreshing the timeline + canvas after apply
            or revert.
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        command: Command,
        refresh: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        """Bridge an unapplied frame/tag command to one ``QUndoCommand``."""
        super().__init__(command, refresh, text, parent)


class LayerCommand(LogicCommand):
    """One ``QUndoCommand`` per layer-tree operation (T12, REQ-P4-UI-013).

    Wraps the **unapplied** :class:`~pixelart_creator.logic.history.Command` a
    ``logic/document`` layer op returns — set opacity / visibility / lock /
    blend-mode, add / remove / duplicate / move, group / ungroup, attach / detach
    mask, set reference, create smart layer. Like :class:`LogicCommand`,
    ``redo()`` applies the logic command on push (and on every later redo) and
    ``undo()`` reverts it exactly (``apply ∘ undo = identity``), so each layer op
    is exactly one undoable step whose inverse restores the exact prior tree
    state.

    The ``refresh`` callback supplies **only** the Qt-side follow-up — a
    dirty-rect / whole-stack recomposite of the canvas plus a layer-panel sync
    (REQ-P4-UI-012/-013). No domain maths lives in this bridge (Article I / S11):
    the reversible logic is entirely the wrapped ``document`` command.

    Args:
        command: The unapplied reversible layer-op command to bridge.
        refresh: Callback (no args) recompositing the canvas + syncing the panel
            after apply or revert.
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        command: Command,
        refresh: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        super().__init__(command, refresh, text, parent)


class TilesetCommand(LogicCommand):
    """One ``QUndoCommand`` per tileset edit (T6E-02/-03, REQ-P6-UI-002/-003/-013).

    Wraps the **unapplied** :class:`~pixelart_creator.logic.history.Command` a
    ``logic/tileset`` builder returns — ``make_reslice_command`` (re-slice the
    source grid) or ``make_edit_tile_command`` (paint a source tile so every
    linked instance updates live, REQ-P6-LOGIC-004/-006) — plus the
    ``logic/document`` ``make_add/remove_tileset_command`` attach/detach ops. Like
    :class:`LogicCommand`, ``redo()`` applies the logic command on push (and on
    every later redo) and ``undo()`` reverts it exactly, so each tileset edit is
    exactly one undoable step whose inverse restores the prior state
    (REQ-P6-UI-013). The ``refresh`` callback supplies only the Qt-side follow-up
    — rebuild the tile-grid thumbnails and repaint any tilemap canvas showing
    linked instances of the edited tile. No domain maths lives here (Article I).

    Args:
        command: The unapplied reversible tileset-op command to bridge.
        refresh: Callback (no args) rebuilding the tileset grid + repainting the
            canvas after apply or revert.
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        command: Command,
        refresh: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        """Bridge an unapplied tileset command to one ``QUndoCommand``."""
        super().__init__(command, refresh, text, parent)


class AutomationCommand(LogicCommand):
    """One ``QUndoCommand`` per automation **edit** (T8E-06, REQ-P8-UI-009).

    Wraps the single reversible :class:`~pixelart_creator.logic.history.Command`
    an automation run produces — a script run / macro replay (a
    :class:`~pixelart_creator.logic.history.GroupCommand` from
    ``logic.scripting.dispatch`` / ``logic.macro.replay``), a batch recolour
    (``logic.batch_ops``), or a procedural generation (``logic.procgen``) — so the
    **whole** automation edit lands on the active document's undo stack as exactly
    **one** undoable step whose inverse restores the exact pre-run state
    (REQ-P8-UI-009). The engine runs off the GUI thread on
    :class:`~pixelart_creator.ui.automation_worker.Automation_Controller`, which
    leaves the live document in its original state and marshals the **unapplied**
    command back; this bridge then applies it on the GUI thread on ``push``
    (``redo()`` → ``command.execute()``) and reverts it exactly on ``undo()``, so
    the observable mutation is strictly GUI-thread (Qt model affinity).

    Recording a macro, enabling/disabling a plugin, and script/panel selection are
    view/session state and create **no** ``AutomationCommand`` (CL-8). No domain
    maths lives here (Article I / S11): the reversible logic is entirely the
    wrapped engine command.

    Args:
        command: The unapplied reversible automation command to bridge.
        rebind: Callback (no args) recompositing / rebinding the canvas + panels
            after apply or revert (a whole-document automation edit can touch any
            layer, so callers pass a full refresh).
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command.
    """

    def __init__(
        self,
        command: Command,
        rebind: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        """Bridge an unapplied automation command to one ``QUndoCommand``."""
        super().__init__(command, rebind, text, parent)


class TilemapCommand(LogicCommand):
    """One ``QUndoCommand`` per tilemap edit (T6F-02/-03/-04, REQ-P6-UI-005..008).

    Wraps the **unapplied** :class:`~pixelart_creator.logic.history.Command` a
    ``logic/tilemap`` builder returns — ``make_stamp_command`` /
    ``make_erase_command`` / ``make_fill_rect_command`` (each folds in any
    auto-tile neighbour re-resolution, REQ-P6-LOGIC-011) and the layer ops
    ``make_add/remove/move_layer_command`` /
    ``make_set_layer_visibility_command`` / ``make_attach_tileset_command`` — plus
    the ``logic/document`` ``make_add/remove_tilemap_command``. Like
    :class:`LogicCommand`, ``redo()`` applies the logic command on push (and on
    every later redo) and ``undo()`` reverts it exactly, so each stamp / erase /
    fill / layer op is exactly one undoable step that restores the exact prior
    cells — including any neighbour cells whose display gid an auto-tile stamp
    re-resolved (REQ-P6-UI-013, SC-UI-009-1). The ``refresh`` callback supplies
    only the Qt-side follow-up — invalidate the affected (dirty) rect on the
    tilemap canvas and sync the layer panel. No domain maths lives here
    (Article I / S11).

    Args:
        command: The unapplied reversible tilemap-op command to bridge.
        refresh: Callback (no args) invalidating the dirty rect + syncing the
            layer panel after apply or revert.
        text: Undo-menu label; defaults to the command's own label.
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        command: Command,
        refresh: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        """Bridge an unapplied tilemap command to one ``QUndoCommand``."""
        super().__init__(command, refresh, text, parent)
