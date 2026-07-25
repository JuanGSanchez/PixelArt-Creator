"""View-only scope + cross-document isolation over the live token-mode relay.

Phase-13 Slice-13E, task T13E-B06 (ADR-0036 §1 + Addendum A.3/A.4; spec
REQ-P13-WEB-002/-005; acceptance **SC-P13-WEB-002-1**, **SC-P13-WEB-005-2**). Drives the
in-process :class:`~sync_backend.server.SyncServer` in token mode and proves the
per-connection binding the verified token establishes:

* a token minted for **project A** can never reach **project B** — a cross-document JOIN
  is dropped and no backlog leaks (SC-P13-WEB-002-1);
* a ``scope:"view"`` connection's UPDATE (mutation) frame is dropped — never broadcast,
  never appended to the store — while JOIN / LEAVE / PRESENCE still work
  (SC-P13-WEB-005-2), and an ``edit``-scope peer's UPDATE *does* converge (contrast);
* the shipped editor path (NO ``share_secret``, full scope) still converges — the
  backend remains backward compatible (ADR-0036 §Consequences).

Qt-free, in-process, DEFAULT gate.
"""

from __future__ import annotations

import asyncio
import json

from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.convergence import MetadataOp
from pixelart_creator.logic.realtime_apply import encode_update as encode_crdt
from sync_backend.server import SyncServer
from sync_backend.store import UpdateStore
from web_viewer.tests._helpers import (
    AUD,
    ISS,
    NOW_VALID,
    SECRET,
    blocking,
    connect,
    drain,
    mint_token,
    poll_until,
    seed_update_frame,
)

PROJECT_A = "project-alpha"
PROJECT_B = "project-beta"


def _token_server(store=None, now=NOW_VALID):
    return SyncServer(
        store=store,
        share_secret=SECRET,
        expected_iss=ISS,
        expected_aud=AUD,
        time_source=lambda: float(now),
    )


# --------------------------------------------------------------------------- #
# Cross-document isolation: a project-A token cannot reach project B.
# --------------------------------------------------------------------------- #


def test_project_a_token_cannot_access_project_b():
    """SC-P13-WEB-002-1: the connection is bound to the verified ``project_id``; a JOIN
    for any OTHER document is dropped and its backlog never reaches the viewer."""

    async def scenario():
        store = UpdateStore()
        store.append(PROJECT_A, seed_update_frame(PROJECT_A, "alpha-only"))
        store.append(PROJECT_B, seed_update_frame(PROJECT_B, "beta-secret"))
        server = _token_server(store=store)
        host, port = await server.start()
        token = mint_token(PROJECT_A, scope="view")  # bound to A only
        viewer = None
        try:
            viewer = await connect(f"ws://{host}:{port}/?token={token}")

            # Cross-document JOIN for B is dropped: no backlog, no data leak.
            await blocking(viewer.join, PROJECT_B)
            assert await drain(viewer, PROJECT_B) == ()

            # The in-project JOIN for A is honoured: the viewer gets A's backlog.
            await blocking(viewer.join, PROJECT_A)
            frames = await poll_until(viewer, PROJECT_A, 1)
            assert len(frames) == 1
            assert sync_protocol.decode_message(frames[0]).document_id == PROJECT_A
        finally:
            if viewer is not None:
                await blocking(viewer.close)
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# View scope: UPDATE dropped; JOIN/LEAVE/PRESENCE work; edit-scope UPDATE converges.
# --------------------------------------------------------------------------- #


def test_view_scope_update_dropped_but_presence_and_leave_work():
    """SC-P13-WEB-005-2: a ``scope:"view"`` UPDATE is dropped (no broadcast, no store
    append); PRESENCE relays and LEAVE unsubscribes; an ``edit`` peer's UPDATE persists
    and relays (view-only enforcement is scope-specific, not blanket)."""

    async def scenario():
        store = UpdateStore()  # empty: we watch what does / does not get appended
        server = _token_server(store=store)
        host, port = await server.start()
        viewer = editor = None
        try:
            view_token = mint_token(PROJECT_A, scope="view")
            edit_token = mint_token(PROJECT_A, scope="edit")
            viewer = await connect(f"ws://{host}:{port}/?token={view_token}")
            editor = await connect(f"ws://{host}:{port}/?token={edit_token}")
            await blocking(viewer.join, PROJECT_A)
            await blocking(editor.join, PROJECT_A)

            # (1) A view-scope UPDATE is dropped: editor sees nothing, nothing stored.
            view_blob = encode_crdt([MetadataOp("k", "view-mutation", 1, 0)])
            await blocking(viewer.send_update, PROJECT_A, view_blob)
            assert await drain(editor, PROJECT_A) == ()
            assert server.store.backlog(PROJECT_A) == ()

            # (2) PRESENCE from the view connection DOES relay (JOIN worked for both).
            await blocking(
                viewer.send_presence,
                PROJECT_A,
                json.dumps({"member_id": "viewer"}).encode("utf-8"),
            )
            presence = await poll_until(editor, PROJECT_A, 1)
            assert sync_protocol.decode_message(presence[0]).kind is (
                sync_protocol.ControlKind.PRESENCE
            )
            assert server.store.backlog(PROJECT_A) == ()  # presence never persisted

            # (3) An edit-scope UPDATE converges: broadcast to the viewer + persisted.
            edit_blob = encode_crdt([MetadataOp("k", "edit-mutation", 2, 0)])
            await blocking(editor.send_update, PROJECT_A, edit_blob)
            got = await poll_until(viewer, PROJECT_A, 1)
            assert sync_protocol.decode_message(got[0]).blob == edit_blob
            assert len(server.store.backlog(PROJECT_A)) == 1

            # (4) LEAVE unsubscribes the viewer: a later edit update is not delivered.
            await blocking(viewer.leave, PROJECT_A)
            await blocking(
                editor.send_update,
                PROJECT_A,
                encode_crdt([MetadataOp("k", "after-leave", 3, 0)]),
            )
            assert await drain(viewer, PROJECT_A) == ()
        finally:
            if viewer is not None:
                await blocking(viewer.close)
            if editor is not None:
                await blocking(editor.close)
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Backward compatibility: the shipped editor path (no share_secret) still converges.
# --------------------------------------------------------------------------- #


def test_editor_path_without_share_secret_still_converges():
    """A plain SyncServer (no ``share_secret``) needs no token and relays updates as
    before — the web-viewer token path is strictly opt-in, so editor clients are
    unaffected (ADR-0036 backward-compatibility clause)."""

    async def scenario():
        server = SyncServer()  # editor path: NO token, NO handshake gate
        host, port = await server.start()
        uri = f"ws://{host}:{port}"
        ta = tb = None
        try:
            ta = await connect(uri)
            tb = await connect(uri)
            await blocking(ta.join, PROJECT_A)
            await blocking(tb.join, PROJECT_A)
            blob = encode_crdt([MetadataOp("title", "shared", 1, 1)])
            await blocking(ta.send_update, PROJECT_A, blob)
            frames = await poll_until(tb, PROJECT_A, 1)
            assert sync_protocol.decode_message(frames[0]).blob == blob
            assert len(server.store.backlog(PROJECT_A)) == 1
        finally:
            if ta is not None:
                await blocking(ta.close)
            if tb is not None:
                await blocking(tb.close)
            await server.stop()

    asyncio.run(scenario())
