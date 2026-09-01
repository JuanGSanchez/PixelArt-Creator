# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
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

from typing import Callable, Optional, Sequence

from PySide6.QtCore import QRectF
from PySide6.QtGui import QUndoCommand

from pixelart_creator.logic.asset_catalog import AssetDescriptor
from pixelart_creator.logic.asset_tags import TagOp
from pixelart_creator.logic.branch_recording import inverse_traces
from pixelart_creator.logic.document import Document, Layer, iter_layers
from pixelart_creator.logic.edit_trace import EditTrace
from pixelart_creator.logic.history import Command, PixelEdit
from pixelart_creator.logic.pixel_buffer import PixelBuffer

#: Called with the dirty rect (scene/pixel coords) after every apply/revert so
#: the view can repaint only the affected region (D5).
RefreshCallback = Callable[[QRectF], None]

#: Called with the descriptor produced by a tag do/undo so the library session
#: can swap it into the in-memory catalog and notify the panels (PL11-D3).
ApplyDescriptorCallback = Callable[[AssetDescriptor], None]

#: Called (no args) on both redo and undo of a pixel edit to drop the LayerGroup
#: flatten caches so a stale composite can never be served after the edit (D4;
#: the logic layer's ``Document.invalidate_caches`` via
#: ``CanvasScene.invalidate_group_caches``).
InvalidateCallback = Callable[[], None]

#: Called (no args) after a whole-buffer / dimension-changing op so the view can
#: rebind the scene and repaint (dirty-rect scope belongs to the rendering
#: and performance layer, not here).
RebindCallback = Callable[[], None]

#: Called with the traces one reversible op produced and whether they describe
#: an undo, so an attached branching session can append them to the active
#: branch's op-log (T13, ``REQ-P10-UI-025``; binds to
#: ``Branching_Session.record_traces``, ``ui/branching_panel.py``). Fired after
#: a successful ``redo()`` with the command's own :meth:`Command.edit_trace`
#: (``inverse=False``) and after a successful ``undo()`` with the **inverse**
#: of those same traces (``inverse=True``) — the log is append-only and
#: last-writer-wins (plan §3.3), so an undo appends the inverse rather than
#: popping the forward entry. ``None`` on every command class when no
#: branching session is attached (T14/T15 wiring); this module mints no op and
#: computes no domain maths of its own (Article I) — it only calls the Qt-free
#: :func:`~pixelart_creator.logic.branch_recording.inverse_traces` to turn a
#: command's fixed, build-time trace into the value an undo must record, then
#: hands both directions to the callback unchanged.
RecordTraceCallback = Callable[[Sequence[EditTrace], bool], None]


def _fire_record_trace(
    command: Command,
    record_trace: Optional[RecordTraceCallback],
    document: Optional[Document],
    *,
    inverse: bool,
) -> None:
    """Report ``command``'s traces to ``record_trace``, inverted on undo (T13).

    A no-op whenever ``record_trace`` is ``None`` (no branching session
    attached) or the command reports no traces at all (the honest empty
    default, ``Command.edit_trace``) — a mainline edit or an untraced command
    class costs nothing here and mints nothing (plan §7 risk R-1: the *absence*
    of a trace is read downstream as ``unaccounted``, never guessed).

    On ``inverse=True`` the **caller** (this bridge) computes the inverse
    traces itself, via :func:`~pixelart_creator.logic.branch_recording.
    inverse_traces`, against ``document`` **after** the command's own
    :meth:`Command.undo` has already run — ``Branching_Session.record_traces``
    never inverts anything (``ui/branching_panel.py``); it only mints and
    stamps whatever it is handed (plan §3.3).
    """
    if record_trace is None:
        return
    traces = command.edit_trace()
    if not traces:
        return
    if inverse:
        # ``document`` is required whenever a command actually reports traces
        # and this is an undo — without it the prior value cannot be read, and
        # recording the forward (post-do) value instead would silently
        # corrupt the merge (plan §3.3). Fail loud rather than invent a value
        # (Article II).
        if document is None:
            raise ValueError(
                "record_trace is attached but no document was supplied to "
                "invert this command's traces on undo"
            )
        traces = inverse_traces(traces, document)
    record_trace(traces, inverse)


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
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge a pre-applied :class:`PixelEdit` to one ``QUndoCommand``.

        Args:
            record_trace: Optional callback reporting this edit's
                :class:`~pixelart_creator.logic.edit_trace.RasterTrace` s to an
                attached branching session (T13, ``REQ-P10-UI-025``).
            document: The live :class:`~pixelart_creator.logic.document.Document`
                this edit's buffer belongs to; required whenever ``record_trace``
                is given (used to invert the traces on undo).
        """
        super().__init__(text or edit.label, parent)
        self._edit = edit
        self._refresh = refresh
        self._dirty_rect = QRectF(dirty_rect)
        self._invalidate = invalidate
        self._applied = True  # record_edit already applied it once.
        self._record_trace = record_trace
        self._document = document

    def bind_recording(
        self,
        record_trace: Optional[RecordTraceCallback],
        document: Optional[Document],
    ) -> None:
        """Attach a branch-recording sink after construction (T-DRAW-01).

        Lets a caller that does not build this command itself — the
        interception point in ``ui/canvas_view.py``'s recording undo-stack
        wrapper, which every one of the six ``ui/tools/`` drawing controllers'
        already-shipped ``ctx.undo_stack.push(command)`` call routes through —
        bind the active branch's :data:`RecordTraceCallback` and live
        :class:`~pixelart_creator.logic.document.Document` without editing each
        tool controller's own ``PaintCommand``/``LogicCommand`` construction
        call. A no-op on any value already set at construction time (never
        silently overwrites an explicit binding).
        """
        if self._record_trace is None and record_trace is not None:
            self._record_trace = record_trace
        if self._document is None and document is not None:
            self._document = document

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
        _fire_record_trace(
            self._edit, self._record_trace, self._document, inverse=False
        )

    def undo(self) -> None:
        """Revert exactly the pixels the edit changed, then repaint them."""
        self._edit.undo()
        self._applied = False
        if self._invalidate is not None:
            self._invalidate()
        self._refresh(self._dirty_rect)
        _fire_record_trace(self._edit, self._record_trace, self._document, inverse=True)


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied logic :class:`Command` to one ``QUndoCommand``.

        Args:
            record_trace: Optional callback reporting this command's
                :meth:`~pixelart_creator.logic.history.Command.edit_trace` to an
                attached branching session (T13, ``REQ-P10-UI-025``).
            document: The live :class:`~pixelart_creator.logic.document.Document`
                this command acts on; required whenever ``record_trace`` is given
                (used to invert the traces on undo).
        """
        super().__init__(text or command.label, parent)
        self._command = command
        self._rebind = rebind
        self._record_trace = record_trace
        self._document = document

    def bind_recording(
        self,
        record_trace: Optional[RecordTraceCallback],
        document: Optional[Document],
    ) -> None:
        """Attach a branch-recording sink after construction (T-DRAW-01).

        Same post-construction binding as :meth:`PaintCommand.bind_recording` —
        see that docstring. Every ``LogicCommand`` subclass (``FrameCommand``,
        ``LayerCommand``, ``TilesetCommand``, ``AutomationCommand``,
        ``TilemapCommand``) inherits this unchanged.
        """
        if self._record_trace is None and record_trace is not None:
            self._record_trace = record_trace
        if self._document is None and document is not None:
            self._document = document

    def redo(self) -> None:
        """Apply (or re-apply) the logic command, then repaint/rebind."""
        self._command.execute()
        self._rebind()
        _fire_record_trace(
            self._command, self._record_trace, self._document, inverse=False
        )

    def undo(self) -> None:
        """Revert the logic command exactly, then repaint/rebind."""
        self._command.undo()
        self._rebind()
        _fire_record_trace(
            self._command, self._record_trace, self._document, inverse=True
        )


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied frame/tag command to one ``QUndoCommand``."""
        super().__init__(
            command, refresh, text, parent, record_trace=record_trace, document=document
        )


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied layer-tree command to one ``QUndoCommand``."""
        super().__init__(
            command, refresh, text, parent, record_trace=record_trace, document=document
        )


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied tileset command to one ``QUndoCommand``."""
        super().__init__(
            command, refresh, text, parent, record_trace=record_trace, document=document
        )


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied automation command to one ``QUndoCommand``."""
        super().__init__(
            command, rebind, text, parent, record_trace=record_trace, document=document
        )


class AssistantCommand(QUndoCommand):
    """One grouped ``QUndoCommand`` per AI-assistant turn (REQ-P14-UI-003, T14E-04).

    A single agentic turn (``logic.assistant.run_turn``) may apply **several**
    allow-listed DSL ops — each already a reversible
    :class:`~pixelart_creator.logic.history.Command` (a ``GroupCommand`` from the
    trusted ``scripting.dispatch``). This wrapper composes the whole turn's ordered
    commands into **one** undoable step so the user undoes an entire assistant edit
    in a single action.

    Like :class:`AutomationCommand`, the off-GUI-thread worker
    (:mod:`~pixelart_creator.ui.assistant_worker`) leaves the live document in its
    **original** state and marshals back the ordered **unapplied** commands; this
    bridge then applies them on the GUI thread on ``push`` (``redo()`` →
    ``command.execute()`` in order) and reverts them exactly on ``undo()`` (in
    reverse order), so the observable mutation is strictly GUI-thread (Qt model
    affinity) and ``apply ∘ undo = identity`` for the whole turn.

    The wrapper renders the outcome of the **logic-level** tiered gate; it never
    relaxes it. A reversible tool-call auto-ran (no confirm) and a destructive one
    only ran after the caller's explicit confirmation
    (:class:`~pixelart_creator.logic.assistant.ConfirmationRequest`); either way the
    resulting edit is captured here as one undoable step. A chat-only turn, a
    connect/config action, or a confirm/deny produces **no** command and therefore
    **no** ``AssistantCommand`` (the caller pushes nothing). No domain maths lives
    here (Article I / S11): the reversible logic is entirely the wrapped commands.

    Args:
        commands: The turn's ordered, unapplied reversible logic commands.
        rebind: Callback (no args) recompositing / rebinding the canvas + panels
            after apply or revert (an assistant edit can touch any layer, so
            callers pass a full refresh).
        text: Undo-menu label; the caller supplies a translatable label.
        parent: Optional parent command.
    """

    def __init__(
        self,
        commands: "tuple[Command, ...]",
        rebind: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge one turn's ordered unapplied commands to a single ``QUndoCommand``.

        Args:
            record_trace: Optional callback reporting each sub-command's own
                :meth:`~pixelart_creator.logic.history.Command.edit_trace` to an
                attached branching session (T13, ``REQ-P10-UI-025``) — fired once
                per sub-command, in the same order they execute/undo, so a
                multi-op turn is recorded as the same ordered sequence of traces
                a single-command bridge would produce.
            document: The live :class:`~pixelart_creator.logic.document.Document`
                the turn acts on; required whenever ``record_trace`` is given.
        """
        super().__init__(text, parent)
        self._commands = tuple(commands)
        self._rebind = rebind
        self._record_trace = record_trace
        self._document = document

    def redo(self) -> None:
        """Apply (or re-apply) every command in order, then repaint/rebind."""
        for command in self._commands:
            command.execute()
            _fire_record_trace(
                command, self._record_trace, self._document, inverse=False
            )
        self._rebind()

    def undo(self) -> None:
        """Revert every command in reverse order, then repaint/rebind."""
        for command in reversed(self._commands):
            command.undo()
            _fire_record_trace(
                command, self._record_trace, self._document, inverse=True
            )
        self._rebind()


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
        *,
        record_trace: Optional[RecordTraceCallback] = None,
        document: Optional[Document] = None,
    ) -> None:
        """Bridge an unapplied tilemap command to one ``QUndoCommand``."""
        super().__init__(
            command, refresh, text, parent, record_trace=record_trace, document=document
        )


class _AssetTagCommand(QUndoCommand):
    """Bridge a pure asset-tag do/undo pair to one ``QUndoCommand`` (Phase 11).

    The one new undoable Phase-11 operation (PL11-D3, REQ-P11-UI-002): a tag
    add / remove. The reversible maths lives entirely in the Qt-free
    :mod:`pixelart_creator.logic.asset_tags` builder, which returns a
    :data:`~pixelart_creator.logic.asset_tags.TagOp` — a ``(do, undo)`` pair of
    no-argument callables each returning the resulting
    :class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor`. This bridge
    holds **no** domain logic (Article I / S11): ``redo()`` applies ``do`` on
    push (and on every later redo) and ``undo()`` applies ``undo``, and both hand
    the produced descriptor to ``apply`` so the library session swaps it into the
    in-memory catalog and notifies the panels. Bound-exceeding tag input is
    rejected by the ``asset_tags`` factory *before* the command is built (so it
    never enters the stack); this bridge only sequences an already-valid op.

    Args:
        tag_op: The ``(do, undo)`` pair from ``make_add_tag`` / ``make_remove_tag``.
        apply: Callback given the descriptor produced by ``do`` / ``undo``; it
            replaces the entry in the catalog and refreshes the bound panels.
        text: Undo-menu label (translatable, supplied by the panel).
        parent: Optional parent command (macro support).
    """

    def __init__(
        self,
        tag_op: TagOp,
        apply: ApplyDescriptorCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
    ) -> None:
        """Capture the tag do/undo pair and the catalog-apply callback."""
        super().__init__(text, parent)
        self._do, self._undo = tag_op
        self._apply = apply

    def redo(self) -> None:
        """Apply (or re-apply) the tag op, then swap the new descriptor in."""
        self._apply(self._do())

    def undo(self) -> None:
        """Restore the prior descriptor exactly, then swap it back in."""
        self._apply(self._undo())


class AddTagCommand(_AssetTagCommand):
    """One ``QUndoCommand`` adding a tag to an asset (REQ-P11-UI-002 / PL11-D3).

    Wraps the :func:`~pixelart_creator.logic.asset_tags.make_add_tag` do/undo
    pair; ``redo()`` reinstates the tag, ``undo()`` restores the exact prior tag
    set. See :class:`_AssetTagCommand` for the sequencing contract.
    """


class RemoveTagCommand(_AssetTagCommand):
    """One ``QUndoCommand`` removing a tag from an asset (REQ-P11-UI-002 / PL11-D3).

    Wraps the :func:`~pixelart_creator.logic.asset_tags.make_remove_tag` do/undo
    pair; ``redo()`` removes the tag, ``undo()`` restores it. See
    :class:`_AssetTagCommand` for the sequencing contract.
    """


class CanvasResizeCommand(QUndoCommand):
    """One ``QUndoCommand`` for a whole-document canvas resize (F3, F1/FIX-05).

    Wraps :meth:`~pixelart_creator.logic.document.Document.resize_canvas`,
    which already resizes every layer/mask buffer in every frame (a
    non-destructive crop/pad) and updates ``Document.width``/``height``.
    ``resize_canvas`` **replaces** each ``Layer.buffer``/``Layer.mask`` with a
    new :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` rather than
    returning an inverse, so a second ``resize_canvas`` call back to the old
    dimensions would not be a true undo — a resize that crops content cannot
    be reversed by growing back (the cropped pixels are gone). This bridge
    therefore snapshots every frame's ``(layer, buffer, mask)`` triple via the
    public :func:`~pixelart_creator.logic.document.iter_layers` walk **before**
    the first ``redo()`` and restores those exact objects on ``undo()`` — a
    byte-exact revert regardless of whether the resize grew or cropped the
    canvas. No domain maths lives here (Article I / S11): the reversible logic
    is entirely ``Document.resize_canvas`` plus this plain object
    snapshot/restore, and every frame's flatten caches are dropped through the
    public :meth:`~pixelart_creator.logic.document.Document.invalidate_caches`
    exactly as ``resize_canvas`` itself does on the forward path.

    Args:
        document: The live document to resize.
        new_width: Target canvas width, px (already validated against
            ``MAX_CANVAS_WIDTH`` by the caller's dialog and by
            ``PixelBuffer``'s own ceiling check).
        new_height: Target canvas height, px.
        rebind: Callback (no args) rebinding the scene + clearing any stale
            selection after apply or revert (whole-buffer / dimension-changing
            op, so callers pass a full scene rebind, mirroring
            :class:`LogicCommand`'s ``dims_change`` branch).
        text: Undo-menu label; the caller supplies a translatable label.
        parent: Optional parent command (macro support).
        offset_x: Where the old content lands on the new canvas, x (0 = the
            existing content stays anchored at the top-left; default).
        offset_y: Where the old content lands on the new canvas, y.
    """

    def __init__(
        self,
        document: Document,
        new_width: int,
        new_height: int,
        rebind: RebindCallback,
        text: str = "",
        parent: Optional[QUndoCommand] = None,
        *,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> None:
        """Snapshot ``document``, then apply the resize once (mirrors ``PaintCommand``).

        ``resize_canvas`` runs here, at construction time, and any
        :class:`~pixelart_creator.logic.pixel_buffer.PixelBufferError` it
        raises (e.g. a ceiling breach) propagates to the **caller** before the
        command ever reaches the undo stack — exactly the pattern
        ``ui/main_window.py._on_scale`` already uses around
        ``transform.make_transform_command``, so a bad size surfaces as one
        caught exception, never a command left half-built on the stack.
        """
        super().__init__(text, parent)
        self._document = document
        self._new_width = new_width
        self._new_height = new_height
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._rebind = rebind
        self._old_width = document.width
        self._old_height = document.height
        self._snapshot: list[tuple[Layer, PixelBuffer, Optional[PixelBuffer]]] = []
        for frame in document.frames:
            for layer in iter_layers(frame.layers):
                self._snapshot.append((layer, layer.buffer, layer.mask))
        document.resize_canvas(
            new_width, new_height, offset_x=offset_x, offset_y=offset_y
        )
        self._applied = True  # the constructor already applied it once.

    def redo(self) -> None:
        """Re-apply the resize (skipping the redundant first apply), then rebind."""
        if self._applied:
            self._applied = False
        else:
            self._document.resize_canvas(
                self._new_width,
                self._new_height,
                offset_x=self._offset_x,
                offset_y=self._offset_y,
            )
        self._rebind()

    def undo(self) -> None:
        """Restore every layer/mask's exact prior buffer, then rebind."""
        for layer, buffer, mask in self._snapshot:
            layer.buffer = buffer
            layer.mask = mask
        self._document.width = self._old_width
        self._document.height = self._old_height
        for frame_index in range(len(self._document.frames)):
            self._document.invalidate_caches(frame_index=frame_index)
        self._applied = False
        self._rebind()
