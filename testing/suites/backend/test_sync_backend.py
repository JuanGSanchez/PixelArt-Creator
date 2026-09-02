"""Integration tests for the real-time sync backend (Phase-10 Slice C).

Covers REQ-P10-BACKEND-001/-002 over localhost, IN the CI gate (CL-B4) — distinct from
the out-of-CI live-provider OAuth. Each test starts a :class:`~sync_backend.server.
SyncServer` in-process on an ephemeral loopback port and drives it with the real
``websockets`` client (through the shipped
:class:`~pixelart_creator.data.cloud.ws_transport.WebSocketTransport`, so the client path
is exercised too). The blocking client runs on an executor thread while the server's
event loop owns the main thread (see the harness note); every scenario tears the server
down in ``finally`` so no loop/task/socket leaks under ``pytest -n auto``.

Proven:

* **Multi-client convergence.** Two clients exchange CRDT updates via the relay and
  converge to the SAME document (REQ-P10-BACKEND-001, REQ-P10-LOGIC-007).
* **Backlog replay.** A late-joining client receives the persisted update backlog.
* **Presence relay, not persisted.** Presence reaches peers but is never stored.
* **Untrusted input.** A malformed / oversized frame is DROPPED, not crashed — the
  relay keeps serving valid traffic afterwards (REQ-P10-BACKEND-002, Article VII).
* **No tokens.** The backend package handles no credentials/tokens and imports no
  ``data``/``ui``/Qt (REQ-P10-BACKEND-002 / CL-B3).
* **Clean lifecycle.** ``address`` is invalid before start and after stop.
"""

from __future__ import annotations

import ast
import asyncio
import time
from pathlib import Path

import pytest

import sync_backend.store as store_module
from pixelart_creator.data.cloud.transport import TransportError
from pixelart_creator.data.cloud.ws_transport import WebSocketTransport
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import MetadataOp, RasterOp, converge
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.realtime_apply import (
    RealtimeState,
    apply_remote,
    encode_update,
)
from sync_backend.server import BackendError, SyncServer
from sync_backend.store import StoreError, UpdateStore

TILE = CRDT_TILE_SIZE_PX
DOC = "backend-doc"


def _solid_tile(value):
    return bytes([value]) * (TILE * TILE * 4)


# --------------------------------------------------------------------------- #
# Executor-driven blocking-client helpers (server loop stays on the main thread).
# --------------------------------------------------------------------------- #


async def _blocking(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


async def _connect(uri):
    return await _blocking(WebSocketTransport, uri)


async def _poll_until(transport, document_id, count, deadline=5.0):
    """Poll until ``count`` frames have arrived (or the deadline elapses)."""
    frames = []
    end = time.monotonic() + deadline
    while len(frames) < count and time.monotonic() < end:
        frames.extend(await _blocking(transport.poll, document_id))
        if len(frames) < count:
            await asyncio.sleep(0.02)
    return tuple(frames)


async def _drain(transport, document_id, window=0.2):
    """Best-effort drain of anything already queued (for backlog/no-op assertions)."""
    end = time.monotonic() + window
    frames = []
    while time.monotonic() < end:
        got = await _blocking(transport.poll, document_id)
        frames.extend(got)
        await asyncio.sleep(0.02)
    return tuple(frames)


# --------------------------------------------------------------------------- #
# UpdateStore unit surface (pure, no server).
# --------------------------------------------------------------------------- #


def test_store_appends_ordered_backlog():
    store = UpdateStore()
    store.append(DOC, b"one")
    store.append(DOC, b"two")
    assert store.backlog(DOC) == (b"one", b"two")


def test_store_documents_are_sorted():
    store = UpdateStore()
    store.append("b", b"x")
    store.append("a", b"y")
    assert store.documents() == ("a", "b")


def test_store_clear_drops_the_log():
    store = UpdateStore()
    store.append(DOC, b"x")
    store.clear(DOC)
    assert store.backlog(DOC) == ()


def test_store_backlog_of_unknown_document_is_empty():
    assert UpdateStore().backlog("nope") == ()


def test_store_enforces_bound(monkeypatch):
    monkeypatch.setattr(store_module, "_MAX_BACKLOG_UPDATES", 2)
    store = UpdateStore()
    store.append(DOC, b"1")
    store.append(DOC, b"2")
    with pytest.raises(StoreError):
        store.append(DOC, b"3")  # backend refuses to grow without bound


# --------------------------------------------------------------------------- #
# Lifecycle.
# --------------------------------------------------------------------------- #


def test_address_before_start_raises():
    server = SyncServer()
    with pytest.raises(BackendError):
        _ = server.address


def test_start_binds_loopback_and_stop_resets_address():
    async def scenario():
        server = SyncServer()
        try:
            host, port = await server.start()
            assert host in ("127.0.0.1", "::1")
            assert port > 0
            assert server.address == (host, port)
            assert isinstance(server.store, UpdateStore)
        finally:
            await server.stop()
        with pytest.raises(BackendError):
            _ = server.address

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Multi-client convergence.
# --------------------------------------------------------------------------- #


def test_two_clients_converge_over_the_relay():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = tb = None
        try:
            ta = await _connect(uri)
            tb = await _connect(uri)
            await _blocking(ta.join, DOC)
            await _blocking(tb.join, DOC)

            base = Document(2 * TILE, TILE)
            doc_a = converge(base, [], site_id=1)
            doc_b = converge(base, [], site_id=2)
            state_a, state_b = RealtimeState(), RealtimeState()

            ops_a = [
                MetadataOp("title", "from-a", 1, 1),
                RasterOp(0, 1, 0, 0, _solid_tile(0x11), TILE, TILE, 5, 1),
            ]
            ops_b = [
                MetadataOp("author", "from-b", 1, 2),
                RasterOp(0, 1, 1, 0, _solid_tile(0x22), TILE, TILE, 5, 2),
            ]
            blob_a, blob_b = encode_update(ops_a), encode_update(ops_b)

            apply_remote(doc_a, blob_a, site_id=1, state=state_a)
            apply_remote(doc_b, blob_b, site_id=2, state=state_b)
            await _blocking(ta.send_update, DOC, blob_a)
            await _blocking(tb.send_update, DOC, blob_b)

            for frame in await _poll_until(ta, DOC, 1):
                msg = sync_protocol.decode_message(frame)
                if msg.kind is sync_protocol.ControlKind.UPDATE:
                    apply_remote(doc_a, msg.blob, site_id=1, state=state_a)
            for frame in await _poll_until(tb, DOC, 1):
                msg = sync_protocol.decode_message(frame)
                if msg.kind is sync_protocol.ControlKind.UPDATE:
                    apply_remote(doc_b, msg.blob, site_id=2, state=state_b)

            assert doc_a.metadata == {"title": "from-a", "author": "from-b"}
            assert doc_b.metadata == doc_a.metadata
            for doc in (doc_a, doc_b):
                arr = doc.frames[0].layers[0].buffer.data
                assert (arr[0:TILE, 0:TILE] == 0x11).all()
                assert (arr[0:TILE, TILE : 2 * TILE] == 0x22).all()

            # The backend persisted both peers' updates (presence would not persist).
            assert len(server.store.backlog(DOC)) == 2
        finally:
            if ta is not None:
                await _blocking(ta.close)
            if tb is not None:
                await _blocking(tb.close)
            await server.stop()

    asyncio.run(scenario())


def test_late_joiner_receives_backlog():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = late = None
        try:
            ta = await _connect(uri)
            await _blocking(ta.join, DOC)
            blob = encode_update([MetadataOp("k", "v", 1, 0)])
            await _blocking(ta.send_update, DOC, blob)
            await asyncio.sleep(0.1)  # let the server persist before the late join

            late = await _connect(uri)
            await _blocking(late.join, DOC)
            frames = await _poll_until(late, DOC, 1)
            assert len(frames) == 1
            assert sync_protocol.decode_message(frames[0]).blob == blob
        finally:
            if ta is not None:
                await _blocking(ta.close)
            if late is not None:
                await _blocking(late.close)
            await server.stop()

    asyncio.run(scenario())


def test_presence_relays_but_is_not_persisted():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = tb = None
        try:
            ta = await _connect(uri)
            tb = await _connect(uri)
            await _blocking(ta.join, DOC)
            await _blocking(tb.join, DOC)
            import json

            await _blocking(
                ta.send_presence,
                DOC,
                json.dumps({"member_id": "alice"}).encode("utf-8"),
            )
            frames = await _poll_until(tb, DOC, 1)
            assert sync_protocol.decode_message(frames[0]).kind is (
                sync_protocol.ControlKind.PRESENCE
            )
            assert server.store.backlog(DOC) == ()  # presence never persisted
        finally:
            if ta is not None:
                await _blocking(ta.close)
            if tb is not None:
                await _blocking(tb.close)
            await server.stop()

    asyncio.run(scenario())


def test_stop_without_start_is_a_noop():
    async def scenario():
        await SyncServer().stop()  # never started — must not raise

    asyncio.run(scenario())


def test_leave_stops_delivery_over_the_relay():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = tb = None
        try:
            ta = await _connect(uri)
            tb = await _connect(uri)
            await _blocking(ta.join, DOC)
            await _blocking(tb.join, DOC)
            await _blocking(tb.leave, DOC)  # tb unsubscribes
            await _blocking(
                ta.send_update, DOC, encode_update([MetadataOp("k", "v", 1, 0)])
            )
            assert await _drain(tb, DOC) == ()  # left client receives nothing
        finally:
            if ta is not None:
                await _blocking(ta.close)
            if tb is not None:
                await _blocking(tb.close)
            await server.stop()

    asyncio.run(scenario())


def test_ws_transport_presence_validation_and_empty_poll():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = None
        try:
            ta = await _connect(uri)
            await _blocking(ta.join, DOC)
            # Empty poll returns () (nothing pending on the joined document).
            assert await _blocking(ta.poll, DOC) == ()
            # Presence payload must be bytes.
            with pytest.raises(TransportError):
                await _blocking(ta.send_presence, DOC, {"member_id": "x"})
            # Presence bytes must be valid UTF-8 JSON.
            with pytest.raises(CloudValidationError):
                await _blocking(ta.send_presence, DOC, b"\xff\xfe not json")
        finally:
            if ta is not None:
                await _blocking(ta.close)
            await server.stop()

    asyncio.run(scenario())


def test_backend_drops_update_when_store_is_full(monkeypatch):
    async def scenario():
        monkeypatch.setattr(store_module, "_MAX_BACKLOG_UPDATES", 0)
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = tb = None
        try:
            ta = await _connect(uri)
            tb = await _connect(uri)
            await _blocking(ta.join, DOC)
            await _blocking(tb.join, DOC)
            await _blocking(
                ta.send_update, DOC, encode_update([MetadataOp("k", "v", 1, 0)])
            )
            # The store refused the append (bound 0); the update is neither persisted
            # nor broadcast, and the relay survives (no crash).
            assert await _drain(tb, DOC) == ()
            assert server.store.backlog(DOC) == ()
        finally:
            if ta is not None:
                await _blocking(ta.close)
            if tb is not None:
                await _blocking(tb.close)
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Untrusted-input defence (Article VII) — malformed dropped, server survives.
# --------------------------------------------------------------------------- #


def test_malformed_frame_is_dropped_and_relay_keeps_serving():
    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        victim = None
        attacker = None
        try:
            victim = await _connect(uri)
            await _blocking(victim.join, DOC)

            # A hostile raw client sends an app-level malformed frame (well-formed at the
            # WebSocket layer, garbage to the sync protocol), then valid traffic on the
            # SAME connection — proving the relay drops the bad frame without crashing or
            # tearing the connection, and keeps serving.
            from websockets.sync.client import connect

            attacker = await _blocking(connect, uri)
            await _blocking(attacker.send, sync_protocol.encode_join(DOC))
            await _blocking(attacker.send, b"garbage-not-json")  # dropped by _dispatch
            await _blocking(
                attacker.send,
                b'{"v": 1, "kind": "bogus", "doc": "backend-doc"}',  # bad kind, dropped
            )
            valid = encode_update([MetadataOp("k", "survived", 1, 0)])
            await _blocking(attacker.send, sync_protocol.encode_update(DOC, valid))

            frames = await _poll_until(victim, DOC, 1)
            # The relay dropped the malformed frames and still relayed the valid update —
            # no crash, no eval/exec, no memory blowup (Article VII).
            assert len(frames) == 1
            assert sync_protocol.decode_message(frames[0]).blob == valid
            assert (
                len(server.store.backlog(DOC)) == 1
            )  # only the valid update persisted
        finally:
            if attacker is not None:
                await _blocking(attacker.close)
            if victim is not None:
                await _blocking(victim.close)
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# No credentials / tokens ever handled by the backend (CL-B3 / REQ-P10-BACKEND-002).
# --------------------------------------------------------------------------- #


def _imported_modules(path: Path):
    """The set of module names a Python file imports (AST — not docstring prose)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _backend_py_files():
    return sorted(Path(store_module.__file__).resolve().parent.glob("*.py"))


def test_backend_imports_no_credential_or_token_machinery():
    # The backend must never acquire/store secrets: tokens stay in the client's
    # data/cloud + OS keyring (CL-B3). Proven by its imports, not by prose.
    forbidden_prefixes = ("keyring", "oauthlib", "requests_oauthlib", "cryptography")
    for path in _backend_py_files():
        for module in _imported_modules(path):
            assert not module.startswith(
                forbidden_prefixes
            ), f"{path.name} imports credential machinery {module!r}"


def test_backend_imports_no_data_or_ui_or_qt():
    forbidden_prefixes = (
        "pixelart_creator.data",
        "pixelart_creator.ui",
        "PySide6",
    )
    for path in _backend_py_files():
        for module in _imported_modules(path):
            assert not module.startswith(
                forbidden_prefixes
            ), f"{path.name} imports {module!r} (outside its allowed deps)"
