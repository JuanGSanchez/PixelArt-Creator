# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Client-side real-time transport port (zero Qt, S11) — Phase-10 Slice C.

ADR-0027 §3; spec REQ-P10-DATA-010. A provider-agnostic :class:`TransportPort` carries
**CRDT updates** and **ephemeral awareness/presence** between a client and the sync
backend. It is pure ``data/`` (zero Qt) and exposes **no** transport/provider type in
its signatures (REQ-P10-DATA-007) — a WebSocket, a WebRTC channel, or the in-memory
loopback all implement the *same* port. Two implementations ship:

* :class:`~pixelart_creator.data.cloud.loopback_transport.LoopbackTransport` — an
  in-memory relay for CI (no network/credentials);
* :class:`~pixelart_creator.data.cloud.ws_transport.WebSocketTransport` — a real
  WebSocket client, credential-/network-gated and **out of the CI gate**.

Every payload crossing the boundary is **untrusted input** (Article VII): outbound
CRDT blobs are size-capped (``validate_crdt_update``, ``MAX_CRDT_UPDATE_BYTES``) and
framed by the pure :mod:`pixelart_creator.logic.sync_protocol`; inbound frames are
decoded + validated by the same pure code, so a malformed/oversized frame is rejected
without ``eval``/``exec`` and without a crash. The framing lives in pure ``logic/`` so
the out-of-layer ``sync_backend/`` reuses it without importing ``data/`` (ADR-0027 §4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple

from pixelart_creator.data.cloud.port import CloudError

__all__ = ["TransportError", "TransportPort"]


class TransportError(CloudError):
    """Raised on a transport failure (connect/send/recv), provider-agnostically.

    Subclasses ``CloudError`` so transport failures stay inside the ``data/cloud/``
    error family — no transport/provider type leaks above the port
    (REQ-P10-DATA-007).
    """


class TransportPort(ABC):
    """The one provider-agnostic real-time transport interface (ADR-0027 §3).

    Carries CRDT updates + presence for a shared ``document_id``. Blobs are opaque
    bytes at this boundary (validated by the pure
    :mod:`~pixelart_creator.logic.sync_protocol` / ``cloud_validation`` layer); the port
    never inspects artwork. Implementations frame outbound payloads and decode/validate
    inbound frames; :meth:`poll` returns already-validated inbound **framed** message
    bytes, which the caller routes with ``sync_protocol.decode_message``.
    """

    @abstractmethod
    def join(self, document_id: str) -> None:
        """Subscribe this client to ``document_id`` (server sends the backlog)."""

    @abstractmethod
    def leave(self, document_id: str) -> None:
        """Unsubscribe this client from ``document_id``'s relay."""

    @abstractmethod
    def send_update(self, document_id: str, blob: bytes) -> None:
        """Send a CRDT-update ``blob`` for ``document_id`` (size-capped before send).

        Raises:
            CloudValidationError: If ``blob`` exceeds ``MAX_CRDT_UPDATE_BYTES`` / is
                not bytes (rejected at the trust boundary before it reaches the wire).
            TransportError: On a transport-level failure.
        """

    @abstractmethod
    def send_presence(self, document_id: str, payload: bytes) -> None:
        """Send an ephemeral presence ``payload`` (JSON bytes) for ``document_id``.

        Presence is never persisted (ADR-0028 §4). ``payload`` is the UTF-8 JSON
        encoding of a presence mapping; it is validated at the boundary.

        Raises:
            CloudValidationError: If the payload is not a valid presence mapping.
            TransportError: On a transport-level failure.
        """

    @abstractmethod
    def poll(self, document_id: str) -> Tuple[bytes, ...]:
        """Return inbound framed messages for ``document_id`` since the last poll.

        Each element is a validated framed message (decode with
        ``sync_protocol.decode_message`` to route update vs presence). Returns an empty
        tuple when nothing is pending. Non-blocking.
        """
