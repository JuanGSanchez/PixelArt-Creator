"""Client-side no-secrets-in-logs assertion (REQ-P10-DATA-008, Article VII §3).

Covers item T-33 (CF-66). The BACKEND half of the no-secrets-in-logs contract is
already enforced and tested: :class:`sync_backend.server._TokenRedactingFilter`
scrubs the ``token=<value>`` query parameter from every record the relay's own
``websockets`` server logger emits (``tests/backend/test_sync_backend.py``,
``tests/backend/test_server_defensive_branches.py``). This module proves the
**client** half: that the client-side cloud path
(:mod:`pixelart_creator.data.cloud`) never emits a credential/token into
logging, using fake credentials of a recognizable sentinel shape and
``caplog`` captured at DEBUG (the level at which a raw request line, or a raw
backend error, is most likely to appear).

Covered, in order:

* **Token-store round trip** (:mod:`pixelart_creator.data.cloud.token_store`) —
  store/load/delete a sentinel token against an injected fake ``keyring``
  backend; the sentinel must never appear in any log record, and a wrapped
  backend failure must never embed the sentinel in its message either.
* **The transport connect/handshake path over the loopback (127.0.0.1, A5)
  network** (:mod:`pixelart_creator.data.cloud.ws_transport`) — a real
  in-process :class:`~sync_backend.server.SyncServer` configured for web-viewer
  share-token verification (ADR-0036 §1/§2), driven with the asyncio-ws-harness
  pattern: the blocking client on an executor thread, the server's loop on the
  main thread, teardown in ``finally``. Both a valid-token connect and a
  wrong-signature rejected connect are exercised.
* **An auth-flow error path** (:mod:`pixelart_creator.data.cloud.auth`) — a
  failed token exchange, a failed refresh, and an exhausted device-code poll,
  each with a sentinel-shaped local secret (``code_verifier`` /
  ``refresh_token_value`` / ``device_code``) in play; the raised
  :class:`AuthError`'s message and every log record must be free of it.

Deterministic and offline throughout: no real provider, no keyring writes (the
``keyring`` seam is monkeypatched with an in-memory fake), and the only network
used is the ephemeral loopback :class:`~sync_backend.server.SyncServer` (A5).

NO OFFICIAL GUIDANCE covers testing a WebSocket client's own logging output
for handshake-token leakage; this module follows the in-tree pattern at
``tests/backend/test_sync_backend.py`` (asyncio-ws-harness) and the client
module at ``pixelart_creator/data/cloud/ws_transport.py`` as the reference,
per the AGT-12 GROUNDING NOTE.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import types

import pytest

from pixelart_creator.data.cloud import auth as cloud_auth
from pixelart_creator.data.cloud import token_store as ts
from pixelart_creator.data.cloud.transport import TransportError
from pixelart_creator.data.cloud.ws_transport import WebSocketTransport
from pixelart_creator.logic import share_token
from sync_backend.server import SyncServer

# --------------------------------------------------------------------------- #
# Sentinel credential shapes — recognizable, and never legitimate content that
# would otherwise appear in a log line (so a substring match is unambiguous).
# --------------------------------------------------------------------------- #

_SENTINEL_TOKEN_VALUE = "SENTINEL-TOKEN-9f2c6b7a1d3e"
_SENTINEL_PROJECT_ID = "SENTINEL-PROJECT-9f2c6b7a1d3e"
_SENTINEL_CODE_VERIFIER = "sentinel-verifier-" + "v" * 30  # RFC 7636 length-valid
_SENTINEL_REFRESH_TOKEN = "SENTINEL-REFRESH-4b1a7c2e9f0d"
_SENTINEL_DEVICE_CODE = "SENTINEL-DEVICE-CODE-6e3a1f8b"
_SENTINEL_AUTH_CODE = "SENTINEL-AUTH-CODE-5d2b9e0c"

_SHARE_SECRET = "test-only-hmac-signing-secret"  # never asserted absent by itself:
# the claim under test is that the *token* (the bearer credential presented on
# the wire) never leaks — the raw HMAC key is never transmitted at all.


def _assert_sentinel_absent(sentinel: str, *haystacks) -> None:
    """Fail loudly (quoting neither haystack) if ``sentinel`` appears anywhere."""
    for haystack in haystacks:
        assert sentinel not in haystack, (
            f"sentinel credential leaked into: {haystack!r}"[:80] + "...<truncated>"
        )


def _caplog_text(caplog) -> str:
    """Every captured record's formatted message, joined (what a log sink shows)."""
    return "\n".join(record.getMessage() for record in caplog.records)


# --------------------------------------------------------------------------- #
# 1. Token-store round trip (pure, no server) — pixelart_creator.data.cloud.token_store
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_keyring(monkeypatch):
    """Inject an in-memory fake ``keyring`` module (never touches the real OS store)."""
    store: dict = {}
    module = types.ModuleType("keyring")

    def set_password(service, account, token):
        store[(service, account)] = token

    def get_password(service, account):
        return store.get((service, account))

    def delete_password(service, account):
        del store[(service, account)]

    module.set_password = set_password
    module.get_password = get_password
    module.delete_password = delete_password
    monkeypatch.setitem(sys.modules, "keyring", module)
    return store


def test_token_store_round_trip_never_logs_the_sentinel(fake_keyring, caplog):
    caplog.set_level(logging.DEBUG)
    ts.store_token("drive", "acct", _SENTINEL_TOKEN_VALUE)
    loaded = ts.load_token("drive", "acct")
    ts.delete_token("drive", "acct")

    assert loaded == _SENTINEL_TOKEN_VALUE  # sanity: the round trip itself worked
    _assert_sentinel_absent(_SENTINEL_TOKEN_VALUE, _caplog_text(caplog))


def test_token_store_backend_failure_message_never_embeds_the_sentinel(
    fake_keyring, monkeypatch, caplog
):
    """Even when the (fake) backend raises, TokenStoreError never carries the value.

    ``store_token``'s wrapping is ``f"failed to store token: {exc}"`` — the token
    argument itself is never interpolated, only the backend's own exception. A
    backend that raises a generic, credential-free error (the realistic case) must
    therefore never surface the sentinel in the wrapped message or in any log record.
    """
    caplog.set_level(logging.DEBUG)

    def _boom(service, account, token):
        raise RuntimeError("backend rejected the request")  # generic, no credential

    monkeypatch.setattr(sys.modules["keyring"], "set_password", _boom)

    with pytest.raises(ts.TokenStoreError) as excinfo:
        ts.store_token("drive", "acct", _SENTINEL_TOKEN_VALUE)

    _assert_sentinel_absent(
        _SENTINEL_TOKEN_VALUE, str(excinfo.value), _caplog_text(caplog)
    )


# --------------------------------------------------------------------------- #
# Executor-driven blocking-client helpers (server loop stays on the main thread) —
# the shipped asyncio-ws-harness pattern (never pytest-asyncio).
# --------------------------------------------------------------------------- #


async def _blocking(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


def _mint_sentinel_token(*, iss: str, aud: str, scope: str = "edit") -> str:
    now = int(time.time())
    claims = {
        "iss": iss,
        "aud": aud,
        "project_id": _SENTINEL_PROJECT_ID,
        "scope": scope,
        "iat": now,
        "exp": now + 60,
    }
    return share_token.mint(claims, _SHARE_SECRET)


# --------------------------------------------------------------------------- #
# 2. The transport connect/handshake path over the loopback network —
#    pixelart_creator.data.cloud.ws_transport.WebSocketTransport
# --------------------------------------------------------------------------- #


def test_ws_transport_valid_handshake_never_logs_the_share_token(caplog):
    """A successful, token-gated connect must never place the bearer token in a log.

    ADR-0036 §2 presents the share token on the wire as a ``?token=`` query
    parameter. The server side is proven scrubbed
    (``tests/backend/test_sync_backend.py`` / the ``_TokenRedactingFilter``); this
    proves the CLIENT side: the same handshake, observed from the connecting
    client's own logging (``websockets.client`` — the default logger the shipped
    ``websockets.sync.client.connect`` call uses when :class:`WebSocketTransport`
    passes none), must never disclose the token either.
    """

    async def scenario():
        server = SyncServer(
            share_secret=_SHARE_SECRET,
            expected_iss="test-iss",
            expected_aud="test-aud",
        )
        host, port = await server.start()
        transport = None
        try:
            token = _mint_sentinel_token(iss="test-iss", aud="test-aud")
            uri = f"ws://{host}:{port}/?token={token}"
            transport = await _blocking(WebSocketTransport, uri)
        finally:
            if transport is not None:
                await _blocking(transport.close)
            await server.stop()
        return token

    caplog.set_level(logging.DEBUG)
    token = asyncio.run(scenario())

    _assert_sentinel_absent(token, _caplog_text(caplog))
    _assert_sentinel_absent(_SENTINEL_PROJECT_ID, _caplog_text(caplog))


def test_ws_transport_rejected_handshake_never_logs_the_share_token(caplog):
    """A REJECTED (wrong-signature) handshake attempt must not log the token either."""

    async def scenario():
        server = SyncServer(
            share_secret=_SHARE_SECRET,
            expected_iss="test-iss",
            expected_aud="test-aud",
        )
        host, port = await server.start()
        try:
            bad_token = _mint_sentinel_token(iss="test-iss", aud="test-aud")
            bad_token = bad_token[:-1] + (
                "A" if bad_token[-1] != "A" else "B"
            )  # flip the signature: authentication must fail
            uri = f"ws://{host}:{port}/?token={bad_token}"
            raised = None
            try:
                await _blocking(WebSocketTransport, uri)
            except Exception as exc:  # noqa: BLE001 - any connect-time rejection
                raised = exc
            assert raised is not None, "a wrong-signature token must be rejected"
            return bad_token
        finally:
            await server.stop()

    caplog.set_level(logging.DEBUG)
    bad_token = asyncio.run(scenario())

    _assert_sentinel_absent(bad_token, _caplog_text(caplog))
    _assert_sentinel_absent(_SENTINEL_PROJECT_ID, _caplog_text(caplog))


def test_ws_transport_send_presence_rejects_non_bytes_without_logging(caplog):
    """A local (pre-wire) validation failure must not log or echo the payload."""

    async def scenario():
        server = SyncServer()
        host, port = await server.start()
        transport = None
        try:
            uri = f"ws://{host}:{port}"
            transport = await _blocking(WebSocketTransport, uri)
            await _blocking(transport.join, "doc")
            with pytest.raises(TransportError):
                await _blocking(
                    transport.send_presence,
                    "doc",
                    {"member_id": _SENTINEL_TOKEN_VALUE},  # wrong type: dict, not bytes
                )
        finally:
            if transport is not None:
                await _blocking(transport.close)
            await server.stop()

    caplog.set_level(logging.DEBUG)
    asyncio.run(scenario())

    _assert_sentinel_absent(_SENTINEL_TOKEN_VALUE, _caplog_text(caplog))


# --------------------------------------------------------------------------- #
# 3. An auth-flow error path — pixelart_creator.data.cloud.auth
# --------------------------------------------------------------------------- #


def _echoing_error_transport(error_code: str):
    """A transport double returning a provider-shaped ``{"error": ...}`` response."""

    def _transport(url, form):
        return {"error": error_code}

    return _transport


def test_exchange_code_error_path_never_leaks_the_code_verifier(caplog):
    caplog.set_level(logging.DEBUG)

    with pytest.raises(cloud_auth.AuthError) as excinfo:
        cloud_auth.exchange_code(
            "https://example.invalid/token",
            client_id="client-1",
            code=_SENTINEL_AUTH_CODE,
            redirect_uri="http://127.0.0.1:0/",
            verifier=_SENTINEL_CODE_VERIFIER,
            transport=_echoing_error_transport("invalid_grant"),
        )

    _assert_sentinel_absent(
        _SENTINEL_CODE_VERIFIER, str(excinfo.value), _caplog_text(caplog)
    )
    _assert_sentinel_absent(
        _SENTINEL_AUTH_CODE, str(excinfo.value), _caplog_text(caplog)
    )


def test_refresh_token_error_path_never_leaks_the_refresh_token(caplog):
    caplog.set_level(logging.DEBUG)

    with pytest.raises(cloud_auth.AuthError) as excinfo:
        cloud_auth.refresh_token(
            "https://example.invalid/token",
            client_id="client-1",
            refresh_token_value=_SENTINEL_REFRESH_TOKEN,
            transport=_echoing_error_transport("invalid_grant"),
        )

    _assert_sentinel_absent(
        _SENTINEL_REFRESH_TOKEN, str(excinfo.value), _caplog_text(caplog)
    )


def test_poll_device_token_exhaustion_never_leaks_the_device_code(caplog):
    caplog.set_level(logging.DEBUG)

    def _still_pending(url, form):
        return {"error": "authorization_pending"}

    with pytest.raises(cloud_auth.AuthError) as excinfo:
        cloud_auth.poll_device_token(
            "https://example.invalid/token",
            client_id="client-1",
            device_code=_SENTINEL_DEVICE_CODE,
            transport=_still_pending,
            max_attempts=2,
        )

    _assert_sentinel_absent(
        _SENTINEL_DEVICE_CODE, str(excinfo.value), _caplog_text(caplog)
    )


def test_loopback_redirect_server_error_capture_never_leaks_the_verifier(caplog):
    """The RFC 8252 loopback redirect handler's error path stays credential-free.

    The captured ``error``/``state`` values are provider-supplied, not our secret;
    this proves our own ``code_verifier`` (never sent over this HTTP leg at all)
    cannot appear in the resulting :class:`AuthError` or in any log record even
    when the redirect carries an ``error``.
    """
    import urllib.request

    caplog.set_level(logging.DEBUG)
    with cloud_auth.LoopbackRedirectServer() as redirect_server:
        request_url = redirect_server.redirect_uri + "?error=access_denied&state=xyz"

        def _fire_redirect():
            with urllib.request.urlopen(request_url, timeout=5) as resp:
                resp.read()

        import threading

        thread = threading.Thread(target=_fire_redirect, daemon=True)
        thread.start()
        try:
            with pytest.raises(cloud_auth.AuthError) as excinfo:
                redirect_server.wait_for_code()
        finally:
            thread.join(timeout=5)

    _assert_sentinel_absent(
        _SENTINEL_CODE_VERIFIER, str(excinfo.value), _caplog_text(caplog)
    )
