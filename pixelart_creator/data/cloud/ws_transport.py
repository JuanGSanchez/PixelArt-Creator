"""Real WebSocket client transport (zero Qt, S11) — Phase-10 Slice C.

ADR-0027 §2/§3; spec REQ-P10-DATA-010. A concrete
:class:`~pixelart_creator.data.cloud.transport.TransportPort` that talks to the
:class:`~sync_backend.server.SyncServer` over a real WebSocket, using the
well-maintained ``websockets`` library (its synchronous client, so the port is a
plain blocking interface driven off the GUI thread via ``ui/cloud_worker.py``). It
implements the **same** port as the in-memory loopback, so no transport/provider type
leaks above the port (REQ-P10-DATA-007) and the client code is transport-agnostic.

This is the **network-gated, out-of-CI** path (``pytest.mark.cloud_live``): CI exercises
real-time through the loopback transport + the in-process backend instead (ADR-0027 §3,
CL-B4). Outbound blobs are size-capped and framed by the pure
:mod:`pixelart_creator.logic.sync_protocol`; inbound frames are validated by the same
pure code (Article VII), so a malformed frame is rejected without ``eval``/``exec``.

``websockets`` is imported **lazily** inside the constructor so importing this module
(e.g. for the layering/type gate) never requires the dependency to be installed.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

from pixelart_creator.data.cloud.transport import TransportError, TransportPort
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError

__all__ = ["WebSocketTransport"]

#: Default receive-drain timeout, seconds — a short non-blocking poll window. Intrinsic
#: to this out-of-CI transport (not a shared tuning value), so module-local.
_POLL_TIMEOUT_S = 0.01


class WebSocketTransport(TransportPort):
    """A :class:`TransportPort` over a real ``websockets`` connection (out of CI).

    One connection multiplexes every joined document; :meth:`poll` drains whatever has
    arrived, buffering per-document so a caller polling one document does not lose
    another's frames.
    """

    def __init__(self, uri: str) -> None:
        """Connect to the sync backend at ``uri`` (e.g. ``ws://127.0.0.1:8765``).

        Raises:
            TransportError: If ``websockets`` is unavailable or the connect fails.
        """
        try:
            from websockets.sync.client import connect
        except ImportError as exc:  # pragma: no cover - dep-gated, out of CI
            raise TransportError(
                "the 'websockets' dependency is required for WebSocketTransport"
            ) from exc
        try:
            self._conn = connect(uri)
        except OSError as exc:  # pragma: no cover - network-gated, out of CI
            raise TransportError(
                f"cannot connect to sync backend at {uri}: {exc}"
            ) from exc
        self._buffers: Dict[str, Deque[bytes]] = {}

    def _send(self, frame: bytes) -> None:
        try:
            self._conn.send(frame)
        except Exception as exc:  # pragma: no cover - network-gated, out of CI
            raise TransportError(f"send failed: {exc}") from exc

    def _drain_socket(self) -> None:
        """Pull arrived frames into the per-document buffers (non-blocking)."""
        from websockets.exceptions import ConnectionClosed

        while True:
            try:
                raw = self._conn.recv(timeout=_POLL_TIMEOUT_S)
            except TimeoutError:
                return
            except ConnectionClosed as exc:  # pragma: no cover - network-gated
                raise TransportError(f"connection closed: {exc}") from exc
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            message = sync_protocol.decode_message(raw)  # validates (Article VII)
            self._buffers.setdefault(message.document_id, deque()).append(bytes(raw))

    def join(self, document_id: str) -> None:
        """Send a JOIN control frame for ``document_id``."""
        self._send(sync_protocol.encode_join(document_id))

    def leave(self, document_id: str) -> None:
        """Send a LEAVE control frame for ``document_id``."""
        self._send(sync_protocol.encode_leave(document_id))

    def send_update(self, document_id: str, blob: bytes) -> None:
        """Frame + send a CRDT-update blob (size-capped before framing)."""
        self._send(sync_protocol.encode_update(document_id, blob))

    def send_presence(self, document_id: str, payload: bytes) -> None:
        """Frame + send an ephemeral presence payload (validated; never persisted)."""
        if not isinstance(payload, (bytes, bytearray)):
            raise TransportError(
                f"presence payload must be bytes, got {type(payload).__name__}"
            )
        try:
            mapping: Any = json.loads(bytes(payload).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CloudValidationError(
                f"presence payload is not valid UTF-8 JSON: {exc}"
            ) from exc
        self._send(sync_protocol.encode_presence(document_id, mapping))

    def poll(self, document_id: str) -> Tuple[bytes, ...]:
        """Drain the socket and return inbound framed messages for ``document_id``."""
        self._drain_socket()
        queue: Optional[Deque[bytes]] = self._buffers.get(document_id)
        if not queue:
            return ()
        frames = tuple(queue)
        queue.clear()
        return frames

    def close(self) -> None:
        """Close the underlying WebSocket connection."""
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - best-effort teardown
            pass
