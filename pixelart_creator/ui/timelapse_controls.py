# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Timelapse recorder + playback controls (REQ-P9-UI-009/-015..-022) — Qt only.

``Timelapse_Controls`` records a **reproducible** edit session: one frame per
committed undoable command (the Procreate cadence). It wires the active
document's ``QUndoStack`` command-commit path — a *forward* index change (a
push or redo, never an undo) — to
:func:`~pixelart_creator.logic.timelapse.record_frame`, appending a
``TimelapseFrame(index, command_id)`` to an immutable
:class:`~pixelart_creator.logic.timelapse.TimelapseSession`. Frames whose
command has been discarded by a push-after-undo are dropped **at the moment
of the discard** via
:func:`~pixelart_creator.logic.timelapse.drop_discarded` (REQ-P9-LOGIC-017) —
load-bearing for every later verdict, not merely for the user notice
(plan §8.2).

**Historical replay (D-12).** Play/pause/stop, an absolute seek, a speed
selector (:data:`~pixelart_creator.logic.constants.TIMELAPSE_PLAYBACK_SPEEDS`)
and a ``k of n`` readout drive
:func:`~pixelart_creator.logic.timelapse.replay` through one of the two
:mod:`~pixelart_creator.ui.timelapse_playback` providers — the live,
in-session ``QUndoStack``
(:class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`)
or a loaded, cross-session payload
(:class:`~pixelart_creator.ui.timelapse_playback.Snapshot_Document_Provider`).
Whichever substrate serves it, every rendered frame is emitted on
:attr:`Timelapse_Controls.frameReady`. **One control surface, one wired
display target so far:** the production host
(``ui/main_window.py``) forwards ``frameReady`` to
:class:`~pixelart_creator.ui.timelapse_frame_view.Timelapse_Frame_View`
only while :meth:`is_reopened_recording` is true, so that widget's
"reopened recording" banner (REQ-P9-UI-024) is never shown over the
user's own current work. There is, as of this wiring pass, **no display
target for an in-session (history) playback** — the active canvas does
not consume ``frameReady``; only its **read-only lock** is wired: the
production host connects :attr:`playbackEditLockChanged` to refuse
document edits on the active tab while playback runs or is paused
mid-sequence (REQ-P9-UI-016), disabling that tab's view and the shared
undo/redo actions. :attr:`playbackEditLockChanged` is only ever emitted
``True`` while :meth:`is_reopened_recording` is false — a reopened
recording's review never borrows or locks whatever document happens to
be open (REQ-P9-UI-024's "must not quietly borrow the active one").

**The verdict-to-words boundary (plan §8.2, Ruling B).** Every
:class:`~pixelart_creator.logic.timelapse.ReconstructionBlocker` code maps to
exactly **one** ``tr()``-wrapped sentence here, and
``Reconstructability.detail`` is **never** rendered into the surface — not in
a label, not in a status line, not in a tooltip. Two of
``REQ-P9-UI-019``'s five refusal cases are decided in **this layer alone**,
because ``reconstructability`` deliberately does not decide them: (b) a
session recorded against a different document (``logic/`` has no document
identity) and (c) an empty session (the verdict is ``ok=True`` for one — it
simply has nothing to play).

Recording is **view/session state**: it pushes **no** ``QUndoCommand`` and
never mutates the document (REQ-P9-UI-010), and playback is equally inert —
:class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`
borrows the live ``QUndoStack`` only for the single ``replay()`` call that
renders every requested frame, and restores its position, content and
undo/redo availability in a ``finally`` **before** the rendered frames are
ever shown — so pausing or stopping the already-rendered playback never
re-touches the document (REQ-P9-LOGIC-016). While playback is running **or
paused mid-sequence**, :attr:`playbackEditLockChanged` tells a host to refuse
document edits.

A save/load now goes through the **schema-2 payload** functions
(:func:`~pixelart_creator.data.timelapse_io.save_session_payload`,
:func:`~pixelart_creator.data.timelapse_io.load_session_payload`), not the
schema-1 command-manifest-only ``save_session``/``load_session`` — a schema-1
save can never carry a replayable payload and therefore can never raise the
size refusal below; pointing here at schema-1 would make that refusal
unreachable code. A save refused for exceeding the payload size limit is told
apart from every other save failure **by exception type**
(:class:`~pixelart_creator.data.timelapse_io.TimelapsePayloadTooLargeError`, a
:class:`~pixelart_creator.data.timelapse_io.TimelapseIOError` subclass), never
by reading ``str(exc)`` — plan §8.2 B-3. The words shown are this
widget's own ``tr()``-wrapped sentence; none of the subclass's size/bound
attributes reach a user-visible surface.

Strings are ``tr()``-wrapped with a ``changeEvent`` retranslate
(REQ-P9-UI-014).

**Every raw-exception-string surface once present in this file is now
closed.** Three failure paths used to render ``str(exc)`` (or an exception
attribute) straight into a user-facing widget; all three are fixed the same
way — caught **by exception type**, shown only as this widget's own
``tr()``-wrapped sentence, with no ``str(exc)``, ``exc.args`` or other
exception detail ever reaching the surface. ``_on_save``/``_on_load`` catch
``TimelapsePayloadTooLargeError`` and ``TimelapseIOError`` by type, each with
its own distinct sentence so an oversize refusal never reads like a malformed
payload (plan §8.2 B-3). ``_record_committed`` catches ``TimelapseError``
by type and shows a fixed sentence for the ``MAX_TIMELAPSE_FRAMES`` refusal —
the only cause reachable through this widget's call (``record_frame`` reuses
``TimelapseError`` for a ``command_id`` contract violation too, but that
argument is always the live ``QUndoStack``'s own forward index here, never a
value this widget could pass invalidly), so no message-text parsing was
needed to tell causes apart. This file is consistent throughout: every
failure path shows only this widget's own words.

**QA-found data-integrity defects fixed (D1-D3, and D4 closed 2026-08-18 by the
Q-21 stable-identity amendment — see below).** A
:class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`
steps the SAME live ``QUndoStack`` this widget listens to for commits; the
``self._replaying`` guard (set for the whole borrow/step/restore span of
:meth:`_render_all` and :meth:`_build_payload_tables`) stops that internal
stepping from being recorded as a user commit or misread as a discard
(D1, REQ-P9-UI-018). The same handler judges a discard only while the
session's own document (``self._document_id``) is the one currently bound,
rather than unconditionally against whichever stack happens to be active —
rebinding to an unrelated document no longer prunes a foreign session down
(D2, REQ-P9-UI-020).

**D4 closed (REQ-P9-LOGIC-022, Q-21, plan §10.1/§10.2 — added 2026-08-18).**
``command_id`` **is still** the raw, reusable ``QUndoStack`` position (D4's
root cause), so a discard-then-re-record still legitimately lands a brand-new
command under the same numeral — that is required behaviour, not a bug
(REQ-P9-UI-010's "one frame per commit" does not pause for a discard). What
closes D4 is that ``command_id`` is **no longer a frame's identity**: this
widget now mints a stable :data:`~pixelart_creator.logic.timelapse.FrameId`
(``f"{self._recording_id}:{self._next_ordinal}"``, a per-recording
:mod:`secrets` draw beside a monotone, never-rewound ordinal — DEP-12g) on
**every** recorded frame, so two frames that share a ``command_id`` across a
discard-then-re-record never share a ``frame_id``. The old
``self._is_command_alive``/``self._discard_boundary`` QA fix — which used to
tell a genuine discarding push apart from plain redo navigation by probing
whether Qt had deleted the previously captured ``QUndoCommand`` object — is
**superseded, not merely removed**: the new mechanism no longer needs that
distinction, because every forward index change (redo included) is treated
uniformly as one recording *event*, minting its own identity every time
(REQ-P9-UI-023's shipped cadence is unchanged: one frame per forward index
change while recording is on). :attr:`_id_at_index` (``Dict[int, FrameId]``)
tracks, per stack index, the identity minted the last time that index was
reached forward; on every forward change to ``i`` every entry with key
``>= i`` is evicted **before** any new mint — an event-time observation, exact
because nothing has been reused yet — and :func:`drop_discarded` is called
with the survivors so a stale frame is dropped **by identity**, never by a
position/count boundary (REQ-P9-LOGIC-017, as restated). The same live set
becomes :class:`History_Document_Provider`'s ``HISTORY`` extent, so a frame
whose position is still in the live stack's range but whose identity was
evicted is now genuinely detected as unreachable (``SC-L022-5``, R5), never
silently resolved by falling back to a count- or range-derived boundary — the
exact discrimination D4's cross-layer residual could not make without an
identity. ``reset()`` mints a **new** ``self._recording_id`` (not merely a
fresh empty session): keeping the old id while restarting the ordinal would
reissue every identity of the previous recording within one application
session — the one hole this shape has, closed by construction.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

import numpy as np
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.snapshot_store import snapshot_of
from pixelart_creator.data.timelapse_io import (
    TimelapseIOError,
    TimelapsePayload,
    TimelapsePayloadTooLargeError,
    load_session_payload,
    save_session_payload,
)
from pixelart_creator.logic.constants import (
    TIMELAPSE_PLAYBACK_FPS_DEFAULT,
    TIMELAPSE_PLAYBACK_SPEEDS,
    TIMELAPSE_RECORDING_ID_BYTES,
)
from pixelart_creator.logic.content_hash import canonical_json_bytes, content_hash
from pixelart_creator.logic.timelapse import (
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
    FrameId,
    ReconstructionBlocker,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
    drop_discarded,
    new_session,
    reconstructability,
    record_frame,
    replay,
)
from pixelart_creator.ui.timelapse_playback import (
    History_Document_Provider,
    Snapshot_Document_Provider,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    from pixelart_creator.logic.document import Document

#: A Document -> RGBA ``ndarray`` renderer (e.g. wrapping ``blend.composite_stack``),
#: injected by the host rather than authored here (S11 — no domain/composite
#: maths in this widget).
Renderer = Callable[["Document"], "np.ndarray"]

#: Returns the currently active document for a bound ``QUndoStack`` (S11 — this
#: widget reads it, it never derives it).
DocumentGetter = Callable[[], "Document"]


class Timelapse_Controls(QWidget):
    """Record, save/load and play back the per-committed-command timelapse session."""

    #: Emitted with the current frame count after a record / load / reset.
    frameCountChanged = Signal(int)
    #: Emitted with one reconstructed RGBA ``ndarray`` per displayed frame,
    #: whichever substrate served it (in-session or a loaded payload).
    frameReady = Signal(object)
    #: Emitted ``True`` while document edits must be refused (playing or
    #: paused mid-sequence), ``False`` once playback stops or completes.
    playbackEditLockChanged = Signal(bool)
    #: Emitted with the number of frames dropped by a discarded branch
    #: (REQ-P9-UI-021), once per occurrence.
    framesDropped = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the record/save/load/playback controls with an empty session."""
        super().__init__(parent)
        #: The per-recording identity half (REQ-P9-LOGIC-022; plan §10.1) —
        #: one :mod:`secrets` draw, minted once per recording (here, and again
        #: on every :meth:`reset`). Never an adversarial-strength token
        #: (``TIMELAPSE_RECORDING_ID_BYTES``' own docstring): it only has to
        #: not collide, and it is paid for on every frame.
        self._recording_id: str = secrets.token_hex(TIMELAPSE_RECORDING_ID_BYTES)
        #: The monotone ordinal half — only ever ``+= 1``, never reset,
        #: rewound, or derived from ``len(session.frames)``: every rewrite
        #: path rebuilds the frames *tuple*, and a counter living inside it
        #: would rewind with it (plan §10.1).
        self._next_ordinal: int = 0
        self._session: TimelapseSession = new_session(recording_id=self._recording_id)
        self._recording = False
        self._stack: Optional[QUndoStack] = None
        self._document_getter: Optional[DocumentGetter] = None
        self._renderer: Optional[Renderer] = None
        self._last_index = 0
        #: The id of the document this session was recorded against
        #: (REQ-P9-UI-020) — ``None`` until the first frame is recorded.
        self._document_id: Optional[object] = None
        #: The id of the document currently bound (the active tab).
        self._active_document_id: Optional[object] = None
        #: stack index -> the FrameId minted the last time that index was
        #: reached forward (plan §10.2). On every forward index change to
        #: ``i``, every entry with key ``>= i`` is evicted **before** any new
        #: mint — an event-time observation, exact because nothing has been
        #: reused yet, never a resolution-time inference from a count. Its
        #: value set is both the surviving-identity set passed to
        #: :func:`~pixelart_creator.logic.timelapse.drop_discarded` and the
        #: live HISTORY extent handed to
        #: :class:`~pixelart_creator.ui.timelapse_playback.History_Document_Provider`.
        self._id_at_index: Dict[int, FrameId] = {}
        #: Set by :meth:`load_reopened_recording` when reviewing a loaded,
        #: cross-session payload rather than the live in-session history.
        self._payload: Optional[TimelapsePayload] = None

        self._rendered_frames: Tuple["np.ndarray", ...] = ()
        self._playback_pos = 0
        self._playing = False
        #: ``True`` only while this widget is itself driving the bound
        #: ``QUndoStack`` through a provider (a historical render or a save's
        #: payload snapshot pass) — every ``indexChanged`` this causes is
        #: this widget's own bookkeeping, never a user commit, and must not
        #: be recorded or misread as a discard boundary (D1 fix; see
        #: ``_render_all``/``_build_payload_tables``).
        self._replaying = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)

        self._record_button = QPushButton(self)
        self._record_button.setCheckable(True)
        self._record_button.toggled.connect(self._on_record_toggled)
        self._save_button = QPushButton(self)
        self._save_button.clicked.connect(self._on_save)
        self._load_button = QPushButton(self)
        self._load_button.clicked.connect(self._on_load)
        self._count_label = QLabel(self)

        self._play_button = QPushButton(self)
        self._play_button.setCheckable(True)
        self._play_button.toggled.connect(self._on_play_toggled)
        self._stop_button = QPushButton(self)
        self._stop_button.clicked.connect(self._on_stop)
        self._seek_slider = QSlider(Qt.Orientation.Horizontal, self)
        self._seek_slider.setMinimum(0)
        self._seek_slider.setMaximum(0)
        self._seek_slider.setEnabled(False)
        self._seek_slider.valueChanged.connect(self._on_seek)
        self._speed_combo = QComboBox(self)
        for speed in TIMELAPSE_PLAYBACK_SPEEDS:
            self._speed_combo.addItem(f"{speed:g}x", speed)
        self._speed_combo.setCurrentIndex(
            list(TIMELAPSE_PLAYBACK_SPEEDS).index(1.0)
            if 1.0 in TIMELAPSE_PLAYBACK_SPEEDS
            else 0
        )
        self._reason_label = QLabel(self)
        self._reason_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.addWidget(self._record_button)
        controls.addWidget(self._save_button)
        controls.addWidget(self._load_button)
        playback_controls = QHBoxLayout()
        playback_controls.addWidget(self._play_button)
        playback_controls.addWidget(self._stop_button)
        playback_controls.addWidget(self._speed_combo)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addLayout(playback_controls)
        layout.addWidget(self._seek_slider)
        layout.addWidget(self._count_label)
        layout.addWidget(self._reason_label)
        self._retranslate()
        self._update_play_availability()

    # -- undo-stack binding (command-commit capture) ----------------------

    def bind_undo_stack(
        self,
        stack: Optional[QUndoStack],
        document_getter: Optional[DocumentGetter] = None,
        document_id: Optional[object] = None,
    ) -> None:
        """Bind the active document's undo stack (document open / tab switch).

        Records one frame on each **forward** index change (a push/redo),
        never on an undo (a backward move). View state only — no document
        mutation. Closing the document or switching tabs stops and restores
        first (REQ-P9-UI-016): any live playback is stopped before the
        rebind. Recording **pauses** while a different document is active and
        **resumes** when this session's own document (``document_id``) is
        active again (REQ-P9-UI-020) — ``document_getter``/``document_id``
        are optional so existing call sites that bind only the stack keep
        working; without them, save/playback report they need a bound
        document rather than guessing one.
        """
        self._on_stop()
        if self._stack is not None:
            try:
                self._stack.indexChanged.disconnect(self._on_stack_index_changed)
            except (RuntimeError, TypeError):
                pass
        self._stack = stack
        self._document_getter = document_getter
        self._active_document_id = document_id
        self._last_index = stack.index() if stack is not None else 0
        if stack is not None:
            stack.indexChanged.connect(self._on_stack_index_changed)
        self._update_play_availability()

    def set_renderer(self, renderer: Optional[Renderer]) -> None:
        """Inject the ``Document`` -> RGBA renderer used to produce played frames.

        No composite/render maths is authored in this widget (S11) — the
        host supplies it (e.g. wrapping ``blend.composite_stack``).
        """
        self._renderer = renderer

    def _evict_stale_identities(self, index: int) -> None:
        """Evict every ``_id_at_index`` entry with key ``>= index`` (plan §10.2).

        Called **before** any new mint, on a forward index change to
        ``index``: those stack positions were just truncated by the push (or
        are about to be re-minted by a redo treated as a fresh recording
        event — see the module docstring's D4 note) — an event-time
        observation, exact because nothing has been reused yet, never a
        resolution-time inference from a count.
        """
        for stale_index in [key for key in self._id_at_index if key >= index]:
            del self._id_at_index[stale_index]

    def _on_stack_index_changed(self, index: int) -> None:
        if self._replaying:
            # D1 fix: this index change was caused by this widget's own
            # provider stepping the stack (a historical render or a save's
            # payload snapshot pass, never a user commit) — track the
            # position so the arithmetic below stays correct once real
            # commits resume, but neither record it as a frame nor treat it
            # as a discard boundary (REQ-P9-UI-018: playback "modifies no
            # recorded frame", unconditionally).
            self._last_index = index
            return
        forward = index > self._last_index
        self._last_index = index
        if self._stack is None:
            return
        dropped = 0
        # D2 fix: a session belongs to one document (REQ-P9-UI-020). Judging
        # discards against whichever stack happens to be *currently* bound —
        # rather than the stack this session was actually recorded against —
        # would be meaningless once rebound to an unrelated document. Gate
        # exactly like the recording check below: only judge discards while
        # this session's own document (or no document yet) is active.
        if self._document_id is None or self._active_document_id == self._document_id:
            if forward:
                self._evict_stale_identities(index)
            # REQ-P9-LOGIC-022(c)/(e); plan §10.2: removal is decided by
            # identity — the surviving set is this session's own live
            # index -> identity map, never a position or count boundary.
            before = len(self._session.frames)
            self._session = drop_discarded(
                self._session, frozenset(self._id_at_index.values())
            )
            dropped = before - len(self._session.frames)
            if dropped:
                self.framesDropped.emit(dropped)
                self._set_reason_text(
                    self.tr(
                        "%n frame(s) were dropped because the edits they recorded "
                        "were undone and replaced.",
                        "",
                        dropped,
                    )
                )
                self._emit_count()
        if (
            self._recording
            and forward
            and self._active_document_id == self._document_id
        ):
            self._record_committed(index)
        self._update_play_availability(keep_reason_text=bool(dropped))

    def _record_committed(self, command_id: int) -> None:
        # Mint the identity (plan §10.1): a per-recording secrets draw beside
        # a monotone ordinal that is only ever incremented, never rewound —
        # this widget is the only thing with a session, a counter and an
        # entropy source; logic/timelapse.py validates what it is given, it
        # never generates one (REQ-P9-LOGIC-009).
        frame_id: FrameId = f"{self._recording_id}:{self._next_ordinal}"
        self._next_ordinal += 1
        try:
            # command_id: the stable ordinal of the committed history command.
            self._session = record_frame(self._session, command_id, frame_id=frame_id)
        except TimelapseError:
            # Frame budget exceeded -> stop recording, surface a user-facing
            # notice. Caught by TYPE, never by reading str(exc): record_frame()
            # raises this same TimelapseError for a non-negative-int contract
            # violation on ``command_id`` too, but that argument is always the
            # live QUndoStack's own forward index here, so the only case this
            # widget can actually reach is the MAX_TIMELAPSE_FRAMES refusal —
            # one exception type, one reachable cause, one tr()-wrapped
            # sentence (mirrors the TimelapsePayloadTooLargeError/TimelapseIOError
            # treatment in _on_save/_on_load below; plan §8.2 B-3). The
            # ordinal drawn above is simply never reused for another frame —
            # (b) forbids reuse, it does not forbid a gap.
            self._recording = False
            self._record_button.setChecked(False)
            QMessageBox.warning(
                self,
                self.tr("Recording stopped"),
                self.tr(
                    "Recording was stopped because it reached the maximum "
                    "number of frames. The frames already recorded are kept. "
                    "Save this recording, or reset it to start a new one."
                ),
            )
            return
        # REQ-P9-LOGIC-022; plan §10.2: this stack position now resolves to
        # the identity just minted for it.
        self._id_at_index[command_id] = frame_id
        self._emit_count()
        # The play-availability recompute is left to the caller
        # (``_on_stack_index_changed``), which always runs one right after
        # this returns — doing it here too would run before that final call
        # and, with a drop notice already showing this same cycle (D3 fix),
        # would clobber it a step early even though the outer call is told
        # to preserve it (REQ-P9-UI-021: reported once, not overwritten).

    # -- session state ----------------------------------------------------

    def session(self) -> TimelapseSession:
        """Return the current immutable timelapse session."""
        return self._session

    def is_recording(self) -> bool:
        """Return whether recording is active."""
        return self._recording

    def is_reopened_recording(self) -> bool:
        """Return whether the current session is a loaded, payload-carrying file.

        ``True`` once :meth:`_on_load`/:meth:`load_reopened_recording` has
        served a payload (REQ-P9-UI-024) and not yet reset/re-recorded —
        the host uses this to route ``frameReady`` to
        :class:`~pixelart_creator.ui.timelapse_frame_view.Timelapse_Frame_View`
        only for a reopened recording, never for the user's own in-session
        work.
        """
        return self._payload is not None

    def frame_count(self) -> int:
        """Return the number of recorded frames."""
        return len(self._session.frames)

    def reset(self) -> None:
        """Discard the recorded session (document open / new session).

        Mints a **new** ``recording_id`` (plan §10.1) — it does not merely
        clear the frames. Keeping the old id while restarting the ordinal
        would reissue every identity of the previous recording inside one
        application session; that is the one hole REQ-P9-LOGIC-022(b)'s
        construction has, and this closes it.
        """
        self._on_stop()
        self._recording_id = secrets.token_hex(TIMELAPSE_RECORDING_ID_BYTES)
        self._next_ordinal = 0
        self._id_at_index = {}
        self._session = new_session(recording_id=self._recording_id)
        self._recording = False
        self._document_id = None
        self._payload = None
        self._record_button.setChecked(False)
        self._emit_count()
        self._update_play_availability()

    def _on_record_toggled(self, checked: bool) -> None:
        if checked:
            if self._session.frames and self._document_id != self._active_document_id:
                # REQ-P9-UI-020: an existing session belongs to one document;
                # resuming it requires that document to be active again.
                self._record_button.setChecked(False)
                QMessageBox.information(
                    self,
                    self.tr("Different document"),
                    self.tr(
                        "This recording belongs to a different document. Switch "
                        "to that document to resume it, or reset first to start "
                        "a new one here."
                    ),
                )
                return
            self._payload = None
            if not self._session.frames:
                self._document_id = self._active_document_id
        self._recording = bool(checked)
        self._retranslate_record()

    # -- persistence (binds to data/timelapse_io, schema 2) ----------------

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Timelapse"),
            "",
            self.tr("Timelapse (*.pixtimelapse)"),
        )
        if not path:
            return
        try:
            snapshots, blobs, updated_session = self._build_payload_tables()
        except TimelapseError:
            QMessageBox.warning(
                self,
                self.tr("Save failed"),
                self.tr(
                    "This recording could not be saved because a recorded "
                    "state could not be reconstructed from the current history."
                ),
            )
            return
        try:
            save_session_payload(updated_session, snapshots, blobs, path)
        except TimelapsePayloadTooLargeError:
            # Per plan §8.2 B-3: dispatch on the TYPE, never on str(exc)/exc.args
            # or any developer-only size/bound attribute of the subclass — none of
            # those may reach a user-visible surface, tooltips included. This
            # sentence is deliberately distinct from the generic TimelapseIOError
            # sentence below so an oversize refusal never reads like a malformed
            # payload (REQ-P9-DATA-004, SC-D004-4).
            QMessageBox.warning(
                self,
                self.tr("Save failed"),
                self.tr(
                    "This recording was not saved because it is too large. "
                    "Nothing was written. Discard some frames and try again."
                ),
            )
            return
        except TimelapseIOError:
            # The generic (non-oversize) save-failure path — malformed table,
            # unwritable path, etc. Fixed the same way as the oversize refusal
            # above (this file's second reported raw-exception-string surface,
            # plan §8.4/module docstring): caught by type, no str(exc)/exc.args
            # or any exception detail reaches the surface — only this widget's
            # own tr()-wrapped sentence, deliberately distinct from the oversize
            # sentence so the two reasons never read alike.
            QMessageBox.warning(
                self,
                self.tr("Save failed"),
                self.tr(
                    "This recording could not be saved. The file could not be "
                    "written, or its data could not be encoded."
                ),
            )
            return
        self._session = updated_session

    def _build_payload_tables(
        self,
    ) -> "Tuple[Dict[str, Dict[str, Any]], Dict[str, str], TimelapseSession]":
        """Snapshot every recorded frame's own state via the bound history.

        Builds a schema-3, identity-bearing payload from the **in-session**
        history so a saved recording is replayable cross-session
        (REQ-P9-DATA-004, REQ-P9-DATA-005): this is the payload path a save
        must use — the schema-1 command-manifest-only ``save_session`` never
        carries a payload and therefore can never raise the size refusal,
        which was the unreachable-code gap this task closes. Every recorded
        frame already carries its own stable ``frame_id`` (minted at record
        time, plan §10.1) — this pass carries it through unchanged, and the
        session's own ``recording_id`` travels with it (``serialize_payload``
        requires both, REQ-P9-DATA-005).

        Raises:
            TimelapseError: If no document is bound, or a recorded frame's
                state cannot be reconstructed from the current history
                (propagated from the underlying provider/document read).
        """
        if self._stack is None or self._document_getter is None:
            raise TimelapseError("no bound document to snapshot")
        provider = History_Document_Provider(self._stack, self._document_getter)
        snapshots: Dict[str, Dict[str, Any]] = {}
        blobs: Dict[str, str] = {}
        updated_frames = []
        # D1 fix (same root cause as _render_all): this pass also steps the
        # live, listened-to QUndoStack one frame at a time to snapshot it —
        # suspend recording/discard bookkeeping for the same reason.
        self._replaying = True
        try:
            with provider:
                for frame in self._session.frames:
                    document = provider(frame)
                    snapshot, frame_blobs = snapshot_of(document)
                    snapshot_id = content_hash(canonical_json_bytes(snapshot))
                    snapshots[snapshot_id] = snapshot
                    blobs.update(frame_blobs)
                    updated_frames.append(
                        TimelapseFrame(
                            index=frame.index,
                            command_id=frame.command_id,
                            snapshot_id=snapshot_id,
                            frame_id=frame.frame_id,
                        )
                    )
        finally:
            self._replaying = False
        updated_session = TimelapseSession(
            schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
            frames=tuple(updated_frames),
            recording_id=self._session.recording_id,
        )
        return snapshots, blobs, updated_session

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Timelapse"),
            "",
            self.tr("Timelapse (*.pixtimelapse)"),
        )
        if not path:
            return
        try:
            payload = load_session_payload(path)
        except TimelapseIOError:
            # Malformed / unknown-version / unreadable manifest -> user-facing
            # error, never a crash. Fixed the same way as the oversize refusal
            # (this file's second reported raw-exception-string surface, plan
            # §8.4/module docstring): caught by type, no str(exc) or exception
            # detail reaches the surface — only this widget's own tr()-wrapped
            # sentence.
            QMessageBox.warning(
                self,
                self.tr("Open failed"),
                self.tr(
                    "This file could not be opened. It is missing, unreadable, "
                    "or not a valid timelapse recording."
                ),
            )
            return
        self._on_stop()
        self._session = payload.session
        self._payload = payload
        self._recording = False
        self._record_button.setChecked(False)
        self._emit_count()
        self._update_play_availability()

    def load_reopened_recording(self, payload: TimelapsePayload) -> None:
        """Enter review mode for an already-loaded schema-2 payload.

        Equivalent to what :meth:`_on_load` does after a successful open;
        exposed so a host that has already called
        :func:`~pixelart_creator.data.timelapse_io.load_session_payload` (e.g.
        re-opening a recently saved recording) does not have to round-trip
        through a file dialog.
        """
        self._on_stop()
        self._session = payload.session
        self._payload = payload
        self._recording = False
        self._record_button.setChecked(False)
        self._emit_count()
        self._update_play_availability()

    # -- playback (D-12) ---------------------------------------------------

    def _current_provider(self):
        """Return the provider matching the current mode, or ``None``.

        The HISTORY provider is handed this session's own live identity set
        (plan §10.2) — ``frozenset(self._id_at_index.values())`` — so its
        ``extent()`` is identity-keyed rather than a count- or range-derived
        boundary (REQ-P9-LOGIC-022(c)).
        """
        if self._payload is not None:
            return Snapshot_Document_Provider(self._payload)
        if self._stack is not None and self._document_getter is not None:
            return History_Document_Provider(
                self._stack,
                self._document_getter,
                reachable_frame_ids=frozenset(self._id_at_index.values()),
            )
        return None

    def _play_refusal(self) -> Optional[str]:
        """Return the one ``tr()``-wrapped refusal sentence, or ``None`` if playable.

        Maps every ``ReconstructionBlocker`` code to exactly one sentence and
        decides the two cases ``reconstructability`` deliberately leaves to
        this layer — (b) a different document, (c) an empty session (plan
        §8.2) — before ever building a provider/extent.
        """
        if not self._session.frames:
            return self.tr("There is nothing recorded to play yet.")
        if (
            self._payload is None
            and self._document_id is not None
            and self._active_document_id != self._document_id
        ):
            return self.tr(
                "This recording belongs to a different document. Switch to "
                "that document to play it."
            )
        provider = self._current_provider()
        if provider is None or self._renderer is None:
            return self.tr("Playback is not available yet.")
        verdict = reconstructability(self._session, provider.extent())
        if verdict.ok:
            return None
        return self._blocker_message(verdict.blocker)

    def _blocker_message(self, blocker: Optional[ReconstructionBlocker]) -> str:
        """Map one ``ReconstructionBlocker`` code to its one user-facing sentence.

        ``Reconstructability.detail`` is never read here or shown anywhere —
        plan §8.2 B-3.
        """
        if blocker is ReconstructionBlocker.NO_PAYLOAD:
            # REQ-P9-UI-019(a): a schema-1 recording — the history it
            # references is gone, so no faithful reconstruction exists.
            return self.tr(
                "This recording was saved in a form that cannot be replayed."
            )
        if blocker is ReconstructionBlocker.PAYLOAD_INCOMPLETE:
            # REQ-P9-UI-019(e)
            return self.tr(
                "This recording's saved data is incomplete and cannot be "
                "fully replayed."
            )
        if blocker is ReconstructionBlocker.BEYOND_EXTENT:
            # REQ-P9-UI-019(d)
            return self.tr(
                "Some recorded frames are no longer reachable in the current "
                "history and cannot be played."
            )
        if blocker is ReconstructionBlocker.SUBSTRATE_MISMATCH:
            return self.tr(
                "This recording's history no longer matches; it cannot be "
                "replayed from here."
            )
        if blocker is ReconstructionBlocker.NO_IDENTITY:
            # REQ-P9-UI-019(f); REQ-P9-DATA-005; Q-21. A schema-2
            # (payload-bearing but identity-less) recording — its frames
            # cannot be told apart reliably, so it is not replayed rather
            # than replayed possibly-wrongly. Distinguishable from clause
            # (a)'s (schema-1, no payload at all) and clause (e)'s
            # (truncated/unreadable payload) sentences above — selected by
            # blocker CODE, never by matching text. No repair, no upgrade,
            # no "play anyway" is offered: there is nothing to repair it
            # from (spec §0b.1).
            return self.tr(
                "This recording was saved in an earlier form whose frames "
                "cannot be told apart reliably, so it will not be replayed."
            )
        return self.tr("This recording cannot be played.")

    def _update_play_availability(self, *, keep_reason_text: bool = False) -> None:
        """Recompute the play button's enabled state and the reason label.

        ``keep_reason_text`` leaves ``_reason_label`` alone (only the play
        button state is recomputed) — used right after a drop notice was
        just set, so the frames-dropped notice (REQ-P9-UI-021) is not
        immediately clobbered by a play-availability sentence in the same
        handler call.
        """
        reason = self._play_refusal()
        self._play_button.setEnabled(reason is None or self._playing)
        if keep_reason_text:
            return
        self._set_reason_text(reason or "")
        self._reason_label.setVisible(reason is not None)

    def _on_play_toggled(self, checked: bool) -> None:
        if checked:
            self._start_or_resume_playback()
        else:
            self._pause_playback()

    def _start_or_resume_playback(self) -> None:
        if not self._rendered_frames:
            reason = self._play_refusal()
            if reason is not None:
                self._play_button.setChecked(False)
                QMessageBox.information(self, self.tr("Cannot play"), reason)
                return
            try:
                self._rendered_frames = self._render_all()
            except TimelapseError:
                self._play_button.setChecked(False)
                QMessageBox.warning(
                    self,
                    self.tr("Playback failed"),
                    self.tr("This recording could not be replayed."),
                )
                return
            self._playback_pos = 0
            self._seek_slider.setMaximum(max(0, len(self._rendered_frames) - 1))
        self._playing = True
        self._seek_slider.setEnabled(True)
        # REQ-P9-UI-024: reviewing a reopened (payload) recording touches no
        # open document, so it must never lock one either — only an
        # in-session (history) playback engages the read-only lock.
        if self._payload is None:
            self.playbackEditLockChanged.emit(True)
        self._timer.start(self._interval_ms())
        self._retranslate_play()

    def _render_all(self) -> "Tuple[np.ndarray, ...]":
        assert self._renderer is not None  # guarded by _play_refusal
        provider = self._current_provider()
        assert provider is not None  # guarded by _play_refusal
        # D1 fix: a History_Document_Provider steps the SAME live QUndoStack
        # this widget listens to for commits (_on_stack_index_changed); every
        # forward step this replay makes is otherwise indistinguishable from
        # a genuine new commit, so playback would record new frames from its
        # own replay (REQ-P9-UI-018). Suspend that handler's recording/
        # discard bookkeeping for the whole borrow/step/restore span.
        self._replaying = True
        try:
            if isinstance(provider, History_Document_Provider):
                return provider.replay_all(self._session, self._renderer)
            return replay(self._session, provider, self._renderer)
        finally:
            self._replaying = False

    def _pause_playback(self) -> None:
        self._timer.stop()
        self._playing = False
        # Editing stays refused while paused mid-sequence (REQ-P9-UI-016) —
        # gated the same way as the play-start emit above (REQ-P9-UI-024).
        if self._payload is None:
            self.playbackEditLockChanged.emit(True)
        self._retranslate_play()

    def _on_stop(self) -> None:
        self._timer.stop()
        was_active = self._playing or bool(self._rendered_frames)
        self._playing = False
        self._playback_pos = 0
        self._rendered_frames = ()
        self._seek_slider.setEnabled(False)
        self._seek_slider.setValue(0)
        if self._play_button.isChecked():
            self._play_button.setChecked(False)
        if was_active and self._payload is None:
            self.playbackEditLockChanged.emit(False)
        self._emit_count()
        self._retranslate_play()

    def _on_timer(self) -> None:
        if self._playback_pos >= len(self._rendered_frames):
            self._on_stop()
            return
        self.frameReady.emit(self._rendered_frames[self._playback_pos])
        self._seek_slider.blockSignals(True)
        self._seek_slider.setValue(self._playback_pos)
        self._seek_slider.blockSignals(False)
        self._emit_count()
        self._playback_pos += 1

    def _interval_ms(self) -> int:
        speed = self._speed_combo.currentData()
        speed = float(speed) if speed else 1.0
        fps = TIMELAPSE_PLAYBACK_FPS_DEFAULT * speed
        return max(1, int(round(1000 / fps)))

    def _on_seek(self, value: int) -> None:
        if not self._rendered_frames:
            return
        self._playback_pos = max(0, min(value, len(self._rendered_frames) - 1))
        self.frameReady.emit(self._rendered_frames[self._playback_pos])
        self._emit_count()

    # -- i18n -------------------------------------------------------------

    def _emit_count(self) -> None:
        total = len(self._session.frames)
        if self._rendered_frames:
            self._set_count_text(
                self.tr("Frame {0} of {1}").format(
                    min(self._playback_pos + 1, total), total
                )
            )
        else:
            self._set_count_text(self.tr("Recorded frames: {0}").format(total))
        self.frameCountChanged.emit(total)

    def _set_reason_text(self, text: str) -> None:
        """Set the refusal-reason label's text and keep it exposed to AT.

        REQ-P9-UI-022: a screen-reader user must be told the same reason a
        sighted user reads on the label -- so ``accessibleDescription`` is
        mirrored here on every change, never only at construction (a name
        or description correct only at construction is a defect in slow
        motion: this label's text changes as the recording, the document
        binding, and the reconstructability verdict change). The
        accessible NAME stays the fixed, translated role label set in
        ``_retranslate`` so the widget still makes sense read aloud with
        no reason text shown yet.
        """
        self._reason_label.setText(text)
        self._reason_label.setAccessibleDescription(text)

    def _set_count_text(self, text: str) -> None:
        """Set the frame-count label's text and keep it exposed to AT.

        Same gap as :meth:`_set_reason_text` above (REQ-P9-UI-022 finding):
        this label's text also changes across the widget's lifetime
        (recorded count, then ``k of n`` during playback) and was equally
        unnamed/undescribed to assistive technology.
        """
        self._count_label.setText(text)
        self._count_label.setAccessibleDescription(text)

    def _retranslate_record(self) -> None:
        self._record_button.setText(
            self.tr("Stop Recording") if self._recording else self.tr("Record")
        )

    def _retranslate_play(self) -> None:
        self._play_button.setText(
            self.tr("Pause") if self._playing else self.tr("Play")
        )

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Timelapse"))
        self.setAccessibleName(self.tr("Timelapse controls"))
        self._save_button.setText(self.tr("Save…"))
        self._load_button.setText(self.tr("Open…"))
        self._stop_button.setText(self.tr("Stop"))
        self._seek_slider.setAccessibleName(self.tr("Timelapse position"))
        self._speed_combo.setAccessibleName(self.tr("Playback speed"))
        # REQ-P9-UI-022: give both status labels a name that makes sense
        # read aloud out of visual context; the matching description is
        # kept current on every text change by ``_set_reason_text``/
        # ``_set_count_text`` above, never only here at (re)translate time.
        self._reason_label.setAccessibleName(self.tr("Playback refusal reason"))
        self._count_label.setAccessibleName(self.tr("Recorded frame count"))
        self._retranslate_record()
        self._retranslate_play()
        self._emit_count()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the control strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
