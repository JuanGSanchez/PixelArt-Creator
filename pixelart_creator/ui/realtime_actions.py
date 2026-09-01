# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Real-time collaboration session seam (REQ-P10-UI-013; ADR-0027 §7).

Phase-10 Slice C. :class:`Realtime_Session` is the **GUI-thread** provider-agnostic
seam that binds the real-time UI (the live-cursor overlay + local broadcast) to the
Qt-free real-time stack:

* the off-GUI-thread :class:`~pixelart_creator.ui.realtime_worker.Realtime_Client`
  polls/writes the :class:`~pixelart_creator.data.cloud.transport.TransportPort` and
  hands inbound **framed bytes** back over a queued signal;
* this session, **on the GUI thread**, decodes each frame with the pure
  :mod:`pixelart_creator.logic.sync_protocol` (Article VII — never ``eval``/``exec``),
  and for a CRDT ``UPDATE`` folds it onto the *live* ``Document`` via
  :func:`~pixelart_creator.logic.realtime_apply.apply_remote` (in place, dirty-region
  scoped — the Article VI re-entry point AGT-10 profiles) then reports the touched
  rects via :func:`~pixelart_creator.logic.realtime_apply.dirty_regions` so the caller
  repaints **only** those tiles; a ``PRESENCE`` frame drives the live-cursor overlay.

Because ``apply_remote`` mutates the ``Document`` and the scene reads it, the whole
decode → apply → repaint path **must** run on the GUI thread — this class owns that
marshalling. The worker never touches the document. A shared
:class:`~pixelart_creator.logic.realtime_apply.RealtimeState` gives strong eventual
consistency (out-of-order / duplicate frames converge; a stale patch is dropped).

Outbound: :meth:`push_local_update` encodes local convergence operations and broadcasts
them (recording them in the session state so our own echo is a no-op);
:meth:`push_local_cursor` broadcasts an ephemeral presence payload. ``ui/`` never sees a
provider type or a token (REQ-P10-DATA-007/-008) — only the abstract client + normalized
value objects.
"""

from __future__ import annotations

import json
from typing import Optional, Sequence

from PySide6.QtCore import QObject, Signal

from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.convergence import Operation
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import (
    RealtimeError,
    RealtimeState,
    apply_remote,
    dirty_regions,
    encode_update,
)
from pixelart_creator.ui.realtime_worker import (
    Realtime_Client,
    TransportFactory,
)


class Realtime_Session(QObject):
    """GUI-thread seam that applies remote updates + broadcasts local activity.

    Holds the off-thread :class:`Realtime_Client`, the local ``site_id`` and
    ``member_id``, the live ``Document``, and the session
    :class:`~pixelart_creator.logic.realtime_apply.RealtimeState`. Bind the overlay +
    scene to its signals; call :meth:`connect_realtime` to join a shared document.
    """

    #: ``(connected,)`` — the real-time connection state changed.
    connectionChanged = Signal(bool)
    #: ``(regions,)`` — a remote CRDT update was applied to the live document; carries
    #: the tuple of :class:`~pixelart_creator.logic.realtime_apply.DirtyRegion` rects
    #: the caller must repaint (empty for a structured-only update).
    remoteUpdateApplied = Signal(object)
    #: ``(presence_mapping,)`` — an ephemeral presence payload arrived (member_id +
    #: optional cursor/selection); drives the live-cursor overlay.
    presenceReceived = Signal(object)
    #: ``(message,)`` — a malformed/oversized frame or transport error was rejected
    #: (surfaced, never a crash — Article VII).
    errorOccurred = Signal(str)

    def __init__(
        self,
        transport_factory: Optional[TransportFactory] = None,
        *,
        site_id: int = 0,
        client: Optional[Realtime_Client] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Create an inactive session bound to ``transport_factory`` / ``client``.

        ``client`` is injectable for tests (a fake client that emits frames directly);
        otherwise a :class:`Realtime_Client` is built over ``transport_factory``.
        """
        super().__init__(parent)
        self._client = client or Realtime_Client(transport_factory, parent=self)
        self._client.frameReceived.connect(self._on_frame)
        self._client.connectionChanged.connect(self.connectionChanged)
        self._client.errorOccurred.connect(self.errorOccurred)
        self._site_id = int(site_id)
        self._member_id = ""
        self._document: Optional[Document] = None
        self._document_id: Optional[str] = None
        self._state = RealtimeState()

    # -- binding ----------------------------------------------------------

    def client(self) -> Realtime_Client:
        """Return the underlying off-thread realtime client, for teardown and tests."""
        return self._client

    def set_document(self, document: Optional[Document]) -> None:
        """Bind the live document remote updates are applied to (on tab switch)."""
        self._document = document

    def set_transport_factory(self, factory: TransportFactory) -> None:
        """Set the transport factory used on the next :meth:`connect_realtime`."""
        self._client.set_transport_factory(factory)

    def is_connected(self) -> bool:
        """Return whether the real-time worker is currently joined."""
        return self._client.is_active()

    def active_document_id(self) -> Optional[str]:
        """Return the joined shared-document id, or ``None``."""
        return self._document_id

    # -- connect / disconnect ---------------------------------------------

    def connect_realtime(self, document_id: str, member_id: str) -> None:
        """Join ``document_id``'s real-time relay as ``member_id`` (fresh state)."""
        self._document_id = document_id
        self._member_id = member_id
        self._state = RealtimeState()
        self._client.connect_realtime(document_id)

    def disconnect_realtime(self) -> None:
        """Leave the relay (reconnectable); keeps the carrier alive."""
        self._client.disconnect_realtime()
        self._document_id = None

    def shutdown(self) -> None:
        """Deterministically tear the client + worker down (window close; idempotent).

        Delegates to :meth:`Realtime_Client.shutdown_realtime` — stops + joins the
        worker thread (bounded) so no socket/worker survives into GC, then releases the
        carrier. Wire this into ``MainWindow.shutdown_prewarm`` **before** the dependent
        overlay widgets are torn down.
        """
        self._client.shutdown_realtime()
        self._document = None
        self._document_id = None

    # -- outbound ---------------------------------------------------------

    def push_local_update(self, ops: Sequence[Operation]) -> None:
        """Encode + broadcast local ``ops`` (recorded so our own echo is dropped).

        The local document is edited through the normal HIS-1 path; this only
        *broadcasts* those edits as a CRDT-update blob. Recording the ops in the session
        state means a relayed echo of our own update is a no-op (strong eventual
        consistency). A malformed op / oversized blob surfaces via
        :attr:`errorOccurred`, never a crash.
        """
        if not ops or not self._client.is_active():
            return
        try:
            blob = encode_update(ops)
        except (RealtimeError, CloudValidationError) as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return
        self._state.accept(ops)
        self._client.send_update(blob)

    def push_local_cursor(
        self,
        x: int,
        y: int,
        selection: Optional[dict] = None,
    ) -> None:
        """Broadcast the local cursor (+ optional selection) as ephemeral presence.

        Presence is never persisted (ADR-0028 §4). A missing member id (no active
        session) makes this a no-op.
        """
        if not self._member_id or not self._client.is_active():
            return
        payload: dict = {
            "member_id": self._member_id,
            "cursor": {"x": int(x), "y": int(y)},
        }
        if selection is not None:
            payload["selection"] = selection
        try:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return
        self._client.send_presence(data)

    # -- inbound (GUI thread — where the document + scene live) -----------

    def _on_frame(self, document_id: str, frame: object) -> None:
        """Decode + route one inbound framed message on the GUI thread (Article VII).

        Every failure path is caught and surfaced via :attr:`errorOccurred`: a
        malformed/oversized frame (``CloudValidationError``) or an unapplyable update
        (``RealtimeError``) is rejected without crashing the app or corrupting the
        document.
        """
        if not isinstance(frame, (bytes, bytearray)):
            return
        try:
            message = sync_protocol.decode_message(bytes(frame))
        except CloudValidationError as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return
        if message.kind is sync_protocol.ControlKind.UPDATE:
            self._apply_update(message.blob)
        elif message.kind is sync_protocol.ControlKind.PRESENCE:
            if message.presence is not None:
                self.presenceReceived.emit(dict(message.presence))

    def _apply_update(self, blob: Optional[bytes]) -> None:
        """Fold a validated CRDT-update ``blob`` onto the live document (GUI thread)."""
        if blob is None or self._document is None:
            return
        try:
            apply_remote(self._document, blob, site_id=self._site_id, state=self._state)
            regions = dirty_regions(blob)
        except (RealtimeError, CloudValidationError) as exc:
            self.errorOccurred.emit(f"{type(exc).__name__}: {exc}")
            return
        self.remoteUpdateApplied.emit(regions)
