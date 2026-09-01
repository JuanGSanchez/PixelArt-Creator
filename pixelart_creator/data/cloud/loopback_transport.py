# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""In-memory loopback transport for CI (zero Qt, S11) — Phase-10 Slice C.

ADR-0027 §3; spec REQ-P10-DATA-010, REQ-P10-BACKEND-001. A hermetic, deterministic
implementation of :class:`~pixelart_creator.data.cloud.transport.TransportPort` with
**no network and no credentials**, so the client↔client real-time loop (and, with the
in-process backend, the client↔backend loop) is exercised **in the CI gate**.

A shared :class:`LoopbackHub` plays the relay role: multiple :class:`LoopbackTransport`
clients attach to one hub, and an update/presence sent by one client is relayed to the
document's other subscribers. The hub **persists** the ordered CRDT-update log per
document (like the real backend, ADR-0027 §4) so a late-joining client receives the
backlog on :meth:`~LoopbackTransport.join`; presence is ephemeral (never persisted). The
hub validates **every** published frame through the pure
:mod:`pixelart_creator.logic.sync_protocol` (schema + ``MAX_CRDT_UPDATE_BYTES`` caps, no
``eval``/``exec``), so the untrusted-input defence runs on the loopback path too.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Deque, Dict, List, Set, Tuple

from pixelart_creator.data.cloud.transport import TransportError, TransportPort
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError

__all__ = ["LoopbackHub", "LoopbackTransport"]


class LoopbackHub:
    """An in-memory relay shared by :class:`LoopbackTransport` clients (CI only).

    Holds, per ``document_id``: the persisted ordered update-frame backlog, the set of
    subscribed client ids, and per-client inbound queues. All operations are synchronous
    and deterministic; there is no threading, network, or clock.
    """

    def __init__(self) -> None:
        """Create an empty hub."""
        self._next_client_id = 0
        self._backlog: Dict[str, List[bytes]] = {}
        self._rooms: Dict[str, Set[int]] = {}
        self._inbound: Dict[int, Dict[str, Deque[bytes]]] = {}

    def register(self) -> int:
        """Register a new client and return its unique id."""
        client_id = self._next_client_id
        self._next_client_id += 1
        self._inbound[client_id] = {}
        return client_id

    def subscribe(self, client_id: int, document_id: str) -> None:
        """Subscribe ``client_id`` to ``document_id`` and deliver the update backlog."""
        self._rooms.setdefault(document_id, set()).add(client_id)
        queue = self._inbound[client_id].setdefault(document_id, deque())
        for frame in self._backlog.get(document_id, ()):  # late-join catch-up
            queue.append(frame)

    def unsubscribe(self, client_id: int, document_id: str) -> None:
        """Unsubscribe ``client_id`` from ``document_id``."""
        room = self._rooms.get(document_id)
        if room is not None:
            room.discard(client_id)

    def publish(self, sender_id: int, frame: bytes) -> None:
        """Validate + relay a framed message; persist it when it is a CRDT update.

        Raises:
            CloudValidationError: If ``frame`` is malformed/oversized (untrusted-input
                defence — the hub never relays an invalid frame).
        """
        message = sync_protocol.decode_message(frame)  # validates (Article VII)
        document_id = message.document_id
        if message.kind is sync_protocol.ControlKind.UPDATE:
            self._backlog.setdefault(document_id, []).append(frame)
        room = self._rooms.get(document_id, set())
        for client_id in sorted(room):
            if client_id == sender_id:
                continue
            self._inbound[client_id].setdefault(document_id, deque()).append(frame)

    def drain(self, client_id: int, document_id: str) -> Tuple[bytes, ...]:
        """Return + clear the inbound frames queued for ``client_id`` on a document."""
        queue = self._inbound[client_id].get(document_id)
        if not queue:
            return ()
        frames = tuple(queue)
        queue.clear()
        return frames


class LoopbackTransport(TransportPort):
    """A CI :class:`TransportPort` backed by an in-memory :class:`LoopbackHub`.

    Construct several over one hub to model several collaborators; convergence over the
    loopback is byte-identical to convergence over the real backend (the frames are the
    same). No network, no credentials, fully deterministic.
    """

    def __init__(self, hub: LoopbackHub) -> None:
        """Attach a new client to ``hub``."""
        self._hub = hub
        self._client_id = hub.register()

    @property
    def client_id(self) -> int:
        """This client's hub id (for test assertions)."""
        return self._client_id

    def join(self, document_id: str) -> None:
        """Subscribe to ``document_id`` and receive its persisted update backlog."""
        self._hub.subscribe(self._client_id, document_id)

    def leave(self, document_id: str) -> None:
        """Unsubscribe from ``document_id``."""
        self._hub.unsubscribe(self._client_id, document_id)

    def send_update(self, document_id: str, blob: bytes) -> None:
        """Frame + relay a CRDT-update blob (size-capped before framing)."""
        frame = sync_protocol.encode_update(document_id, blob)
        self._hub.publish(self._client_id, frame)

    def send_presence(self, document_id: str, payload: bytes) -> None:
        """Frame + relay an ephemeral presence payload (validated; never persisted).

        Raises:
            CloudValidationError: If ``payload`` is not a valid UTF-8 JSON presence
                mapping.
            TransportError: If ``payload`` is not bytes.
        """
        if not isinstance(payload, (bytes, bytearray)):
            raise TransportError(
                f"presence payload must be bytes, got {type(payload).__name__}"
            )
        try:
            mapping = json.loads(bytes(payload).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CloudValidationError(
                f"presence payload is not valid UTF-8 JSON: {exc}"
            ) from exc
        frame = sync_protocol.encode_presence(document_id, mapping)
        self._hub.publish(self._client_id, frame)

    def poll(self, document_id: str) -> Tuple[bytes, ...]:
        """Return inbound framed messages queued for this client on ``document_id``."""
        return self._hub.drain(self._client_id, document_id)
