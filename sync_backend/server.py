"""Asyncio WebSocket sync-relay server (Phase-10 Slice C) — OUTSIDE the three layers.

ADR-0027 §1/§2/§4/§6; spec REQ-P10-BACKEND-001/-002, CL-B4. :class:`SyncServer` relays
CRDT updates + ephemeral awareness/presence across the peers of a shared ``document_id``
and **persists** the per-document update log (:mod:`sync_backend.store`) so a
late-joining client catches up. It is a separate top-level component (not a client
layer): it imports **no** ``pixelart_creator.ui``/``pixelart_creator.data``/Qt and never
receives or stores provider OAuth tokens (REQ-P10-BACKEND-002) — it reuses only the pure
``pixelart_creator.logic`` framing/validation (ADR-0027 §5).

**Untrusted-input defence (REQ-P10-BACKEND-002, Article VII).** Every ingested frame is
decoded + validated through the pure :mod:`pixelart_creator.logic.sync_protocol`
(schema + ``MAX_CRDT_UPDATE_BYTES`` caps, never ``eval``/``exec``); a malformed frame
is dropped with no crash, no code execution, and no memory exhaustion (the store
is bounded). **CI-testability (REQ-P10-BACKEND-001).** :meth:`SyncServer.start` binds an
ephemeral loopback port in-process, so the full client↔backend loop runs over localhost
in the CI gate.
"""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError
from sync_backend.store import StoreError, UpdateStore

__all__ = ["BackendError", "SyncServer"]


class BackendError(RuntimeError):
    """Raised on a backend lifecycle error (e.g. reading the address before start)."""


class SyncServer:
    """An asyncio WebSocket relay of CRDT updates + presence across a document's peers.

    One connection may join several documents; the server tracks a per-document set of
    connections ("rooms") and, on each inbound frame, validates it and routes by kind:
    JOIN (subscribe + replay the persisted backlog to the joiner), UPDATE (persist +
    broadcast to the document's other peers), PRESENCE (broadcast only — never
    persisted), LEAVE (unsubscribe). Malformed frames are dropped defensively.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        store: Optional[UpdateStore] = None,
    ) -> None:
        """Configure the relay.

        Args:
            host: Bind host (loopback by default — CI never opens an external port).
            port: Bind port; ``0`` picks an ephemeral free port (the CI default).
            store: The update-log persistence (a fresh in-memory
                :class:`~sync_backend.store.UpdateStore` by default).
        """
        self._host = host
        self._port = port
        self._store = store if store is not None else UpdateStore()
        self._rooms: Dict[str, Set[ServerConnection]] = {}
        self._joined: Dict[ServerConnection, Set[str]] = {}
        self._server: Optional[object] = None
        self._bound: Optional[Tuple[str, int]] = None

    @property
    def store(self) -> UpdateStore:
        """Return the backend's update-log store, exposed for test inspection."""
        return self._store

    @property
    def address(self) -> Tuple[str, int]:
        """The bound ``(host, port)``; valid only after :meth:`start`.

        Raises:
            BackendError: If the server has not been started.
        """
        if self._bound is None:
            raise BackendError("server not started")
        return self._bound

    async def start(self) -> Tuple[str, int]:
        """Start the relay on an ephemeral loopback port; return the bound address.

        In-process spin-up for CI (REQ-P10-BACKEND-001): ``await server.start()`` then
        connect clients to ``ws://{host}:{port}``.
        """
        server = await serve(self._handler, self._host, self._port)
        self._server = server
        sock = next(iter(server.sockets))
        host, port = sock.getsockname()[:2]
        self._bound = (str(host), int(port))
        return self._bound

    async def stop(self) -> None:
        """Stop the relay and wait for it to close (clean CI teardown)."""
        if self._server is not None:
            self._server.close()  # type: ignore[attr-defined]
            await self._server.wait_closed()  # type: ignore[attr-defined]
            self._server = None
            self._bound = None

    async def _handler(self, connection: ServerConnection) -> None:
        """Serve one client connection: validate + route every inbound frame."""
        self._joined[connection] = set()
        try:
            async for raw in connection:
                frame = raw.encode("utf-8") if isinstance(raw, str) else raw
                await self._dispatch(connection, bytes(frame))
        except ConnectionClosed:  # pragma: no cover - network teardown timing
            pass
        finally:
            self._cleanup(connection)

    async def _dispatch(self, connection: ServerConnection, frame: bytes) -> None:
        """Validate one untrusted frame and route it (drop it on any violation)."""
        try:
            message = sync_protocol.decode_message(frame)  # Article VII: validate first
        except CloudValidationError:
            # Untrusted-input defence: reject malformed/oversized frames silently —
            # no crash, no eval/exec, no memory growth (REQ-P10-BACKEND-002).
            return
        document_id = message.document_id
        kind = message.kind

        if kind is sync_protocol.ControlKind.JOIN:
            self._rooms.setdefault(document_id, set()).add(connection)
            self._joined[connection].add(document_id)
            for backlog_frame in self._store.backlog(document_id):  # late-join catch-up
                await self._safe_send(connection, backlog_frame)
        elif kind is sync_protocol.ControlKind.LEAVE:
            self._unsubscribe(connection, document_id)
        elif kind is sync_protocol.ControlKind.UPDATE:
            try:
                self._store.append(document_id, frame)  # persist (bounded)
            except StoreError:
                return  # document at its bound — refuse without crashing
            await self._broadcast(document_id, frame, sender=connection)
        elif kind is sync_protocol.ControlKind.PRESENCE:
            await self._broadcast(
                document_id, frame, sender=connection
            )  # not persisted

    async def _broadcast(
        self, document_id: str, frame: bytes, *, sender: ServerConnection
    ) -> None:
        """Relay ``frame`` to every peer of ``document_id`` except the sender."""
        for peer in list(self._rooms.get(document_id, set())):
            if peer is sender:
                continue
            await self._safe_send(peer, frame)

    @staticmethod
    async def _safe_send(connection: ServerConnection, frame: bytes) -> None:
        """Send a frame, ignoring a peer that has disconnected mid-broadcast."""
        try:
            await connection.send(frame)
        except ConnectionClosed:  # pragma: no cover - network teardown timing
            pass

    def _unsubscribe(self, connection: ServerConnection, document_id: str) -> None:
        room = self._rooms.get(document_id)
        if room is not None:
            room.discard(connection)
        self._joined.get(connection, set()).discard(document_id)

    def _cleanup(self, connection: ServerConnection) -> None:
        """Drop a closed connection from every room it had joined."""
        for document_id in self._joined.pop(connection, set()):
            room = self._rooms.get(document_id)
            if room is not None:
                room.discard(connection)
