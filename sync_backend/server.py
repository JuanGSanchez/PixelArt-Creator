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

import logging
import re
import time
from http import HTTPStatus
from typing import Callable, Dict, Optional, Set, Tuple
from urllib.parse import parse_qs, urlsplit

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from pixelart_creator.logic import share_token, sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.share_token import SecretLike, ShareTokenError
from sync_backend.store import StoreError, UpdateStore

__all__ = ["BackendError", "SyncServer"]

#: The read-only token scope (ADR-0036 §1 / Addendum A.4). A connection whose verified
#: token carries this scope may observe (JOIN/LEAVE/PRESENCE) but never mutate (UPDATE)
#: — enforced in :meth:`SyncServer._dispatch` (WEB-002/-005). The scope-string
#: vocabulary is format-intrinsic to the share-token contract (module-local, BF-2).
_VIEW_SCOPE = "view"

#: Redacts a ``token=<value>`` query parameter from any log record (ADR-0036 Addendum
#: A.2 (2): the backend MUST NOT emit the raw token in a logged request line). Matches
#: the value up to the next ``&`` / whitespace / quote so only the secret is masked.
_TOKEN_REDACTION_RE = re.compile(r"(token=)[^&\s\"']+")


class _TokenRedactingFilter(logging.Filter):
    """A logging filter that masks ``token=<value>`` in every emitted record.

    Attached to the ``websockets`` server logger only when token verification is active
    (the web-viewer handshake), so the query-string share token (Addendum A.1) can never
    reach a log sink verbatim — including the framework's DEBUG raw-request line
    ``< GET <path> HTTP/1.1`` where ``<path>`` carries ``?token=…`` (Addendum A.2).
    """

    @staticmethod
    def _scrub(value: object) -> object:
        if isinstance(value, str):
            return _TOKEN_REDACTION_RE.sub(r"\1<redacted>", value)
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._scrub(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(self._scrub(arg) for arg in record.args)
            elif isinstance(record.args, dict):
                record.args = {
                    key: self._scrub(val) for key, val in record.args.items()
                }
        return True


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
        share_secret: Optional[SecretLike] = None,
        expected_iss: Optional[str] = None,
        expected_aud: Optional[str] = None,
        time_source: Callable[[], float] = time.time,
    ) -> None:
        """Configure the relay.

        Web-viewer token verification is **opt-in** (mirroring the ``cloud_live``
        optional pattern): engaged only when ``share_secret`` is supplied (viewer mode).
        With no ``share_secret`` the relay behaves exactly as the shipped editor-path
        server — no handshake token is read or required — so the existing editor clients
        and their tests are unaffected (ADR-0036 §Consequences: backward compatibility).

        Args:
            host: Bind host (loopback by default — CI never opens an external port).
            port: Bind port; ``0`` picks an ephemeral free port (the CI default).
            store: The update-log persistence (a fresh in-memory
                :class:`~sync_backend.store.UpdateStore` by default).
            share_secret: When set, the operator-provided HMAC signing secret that
                engages share-link-token verification in the ``websockets``
                ``process_request`` handshake (ADR-0036 §1). ``expected_iss`` and
                ``expected_aud`` are then required. Never committed to the repo.
            expected_iss: The issuer the handshake accepts (required iff
                ``share_secret``).
            expected_aud: The audience the handshake accepts (required iff
                ``share_secret``).
            time_source: Clock (seconds) passed to
                :func:`~pixelart_creator.logic.share_token.verify` as ``now`` —
                injectable for deterministic tests; defaults to :func:`time.time`.

        Raises:
            BackendError: If ``share_secret`` is given without both ``expected_iss`` and
                ``expected_aud``.
        """
        if share_secret is not None and (expected_iss is None or expected_aud is None):
            raise BackendError(
                "share_secret requires both expected_iss and expected_aud"
            )
        self._host = host
        self._port = port
        self._store = store if store is not None else UpdateStore()
        self._rooms: Dict[str, Set[ServerConnection]] = {}
        self._joined: Dict[ServerConnection, Set[str]] = {}
        self._server: Optional[object] = None
        self._bound: Optional[Tuple[str, int]] = None
        # Web-viewer token config (None ⇒ token verification disabled, editor path).
        self._share_secret = share_secret
        self._expected_iss = expected_iss
        self._expected_aud = expected_aud
        self._time_source = time_source
        # Per-connection (project_id, scope) binding set at the verified handshake; a
        # connection present here is a token-scoped viewer connection (Addendum A.3).
        self._scope: Dict[ServerConnection, Tuple[str, str]] = {}
        self._logger: Optional[logging.Logger] = None
        if share_secret is not None:
            logger = logging.getLogger(f"sync_backend.server.{id(self):x}")
            logger.addFilter(_TokenRedactingFilter())
            self._logger = logger

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
        connect clients to ``ws://{host}:{port}``. When a ``share_secret`` was
        configured, a ``process_request`` hook verifies the query-string share token at
        the handshake (ADR-0036 §2 / Addendum A.1) and a token-redacting logger is
        installed (A.2).
        """
        process_request = (
            self._process_request if self._share_secret is not None else None
        )
        server = await serve(
            self._handler,
            self._host,
            self._port,
            process_request=process_request,
            logger=self._logger,
        )
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

    def _process_request(
        self, connection: ServerConnection, request: Request
    ) -> Optional[Response]:
        """Verify the query-string share token at the WS handshake (web-viewer mode).

        The ``websockets`` ``process_request`` hook (ADR-0036 §2 step 3 / Addendum A.1):
        read the ``token`` query parameter from ``request.path`` with
        :func:`~urllib.parse.urlsplit` + :func:`~urllib.parse.parse_qs`, verify it via
        the pure :func:`~pixelart_creator.logic.share_token.verify` seam against the
        configured secret + ``expected_iss``/``expected_aud``, and — on any failure
        (missing / expired / bad-signature / wrong ``iss``/``aud``) — reject the
        handshake with an HTTP **401/403** response, serving **no** project data. On
        success the connection is **bound** to the token's ``project_id`` (==
        ``document_id``) + scope (Addendum A.3), enforced in :meth:`_dispatch`. The
        ``&p=`` share-link hint is
        **never** trusted for scoping; only the verified ``project_id`` claim is
        authoritative. The token is verified, never stored (ADR-0027 / Addendum A.2).

        Returns:
            ``None`` to accept the handshake, or an HTTP :class:`Response` to reject it.
        """
        assert self._share_secret is not None  # set iff this hook is installed
        token = self._read_token(request.path)
        if token is None:
            return connection.respond(HTTPStatus.UNAUTHORIZED, "missing share token\n")
        try:
            claims = share_token.verify(
                token,
                self._share_secret,
                expected_iss=self._expected_iss or "",
                expected_aud=self._expected_aud or "",
                now=self._time_source(),
            )
        except ShareTokenError:
            # Verify-never-leak: reject without echoing the token or the failure detail.
            return connection.respond(HTTPStatus.FORBIDDEN, "invalid share token\n")
        self._scope[connection] = (str(claims["project_id"]), str(claims["scope"]))
        return None

    @staticmethod
    def _read_token(path: str) -> Optional[str]:
        """Return the ``token`` query-string parameter of ``path``, or ``None``.

        Reads only the ``token`` parameter (Addendum A.1); the ``p`` project hint is
        intentionally ignored — the authoritative project identity is the verified
        claim.
        """
        params = parse_qs(urlsplit(path).query)
        values = params.get("token")
        if not values or not values[0]:
            return None
        return values[0]

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

        # Token-scoped (web-viewer) connections are BOUND to one project + scope
        # (Addendum A.3/A.4). A frame for any other document is dropped (a token for
        # project A can never reach project B), and an UPDATE (mutation) on a
        # ``scope:"view"`` connection is dropped (view-only, WEB-002/-005). Editor-path
        # connections have no binding and are unaffected (backward compatible).
        binding = self._scope.get(connection)
        if binding is not None:
            bound_project_id, scope = binding
            if document_id != bound_project_id:
                return  # serve nothing for a document other than the token's project
            if kind is sync_protocol.ControlKind.UPDATE and scope == _VIEW_SCOPE:
                return  # view-only token: reject the mutation frame

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
        self._scope.pop(connection, None)  # release any token scope binding
