"""Shared test helpers for the ``web_viewer`` share-token integration tests (no Qt).

Reuses the ``tests/backend`` harness shape: an in-process
:class:`~sync_backend.server.SyncServer` on an ephemeral loopback port, driven by the
real blocking ``websockets`` client from an executor thread so the server's asyncio
loop keeps the main thread (AGT-03 harness note). Adds share-link-token minting/forging
helpers built with **stdlib only** (mirroring
:mod:`pixelart_creator.logic.share_token`), so a test can mint a valid token or forge a
tampered / ``alg:"none"`` / wrong-claim one and present it at the live handshake.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Mapping, Optional, Tuple

from pixelart_creator.data.cloud.ws_transport import WebSocketTransport
from pixelart_creator.logic import share_token, sync_protocol
from pixelart_creator.logic.constants import SHARE_TOKEN_MAX_TTL_S
from pixelart_creator.logic.convergence import MetadataOp
from pixelart_creator.logic.realtime_apply import encode_update as encode_crdt

#: Operator signing secret + issuer/audience the test backend is configured with. Never
#: a real secret — a fixed test literal (ADR-0036 §1: the secret is operator-provided
#: and never committed; this is a throwaway used only inside the in-process suite).
SECRET = "test-operator-share-secret-do-not-ship"
ISS = "pixelart.test.issuer"
AUD = "web-viewer-test"

#: A deterministic clock (seconds). Tokens are minted with ``iat``/``exp`` around this
#: so the injected ``time_source`` makes the handshake fully deterministic (no wall
#: clock, no flakiness).
IAT = 1_000_000
NOW_VALID = IAT + 60  # within (iat, exp) for a default-TTL token
NOW_EXPIRED = IAT + SHARE_TOKEN_MAX_TTL_S + 10_000  # well past any valid exp


def make_claims(
    project_id: str,
    *,
    iss: str = ISS,
    aud: str = AUD,
    scope: str = "view",
    iat: int = IAT,
    ttl: int = 3600,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a claim mapping for :func:`share_token.mint` (defaults are all valid)."""
    claims: Dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "project_id": project_id,
        "scope": scope,
        "iat": iat,
        "exp": iat + ttl,
    }
    claims.update(extra)
    return claims


def mint_token(project_id: str, *, secret: str = SECRET, **claim_kw: Any) -> str:
    """Mint a signed share-link token for ``project_id`` (see :func:`make_claims`)."""
    return share_token.mint(make_claims(project_id, **claim_kw), secret)


def _b64url(obj: Mapping[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def forge_token(
    header: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    secret: str = SECRET,
) -> str:
    """Forge a ``header.payload.sig`` token with a **correct** HMAC over ``secret``.

    Signs so the constant-time signature compare PASSES — used to reach the ``alg`` /
    ``typ`` downgrade checks (e.g. an ``alg:"none"`` header that is nonetheless signed),
    which :func:`share_token.verify` guards after authenticating the segments.
    """
    header_b64 = _b64url(header)
    payload_b64 = _b64url(payload)
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{signing_input}.{sig_b64}"


def tamper(token: str) -> str:
    """Return ``token`` with its payload flipped so the signature no longer matches."""
    header_b64, payload_b64, sig_b64 = token.split(".")
    # Flip one base64url char in the payload segment (deterministically).
    flipped = ("B" if payload_b64[0] != "B" else "C") + payload_b64[1:]
    return f"{header_b64}.{flipped}.{sig_b64}"


def seed_update_frame(document_id: str, marker: str) -> bytes:
    """Build one valid persisted UPDATE wire-frame carrying ``marker`` metadata."""
    blob = encode_crdt([MetadataOp("k", marker, 1, 0)])
    return sync_protocol.encode_update(document_id, blob)


# --------------------------------------------------------------------------- #
# Executor-driven blocking-client helpers (server loop stays on the main thread).
# Mirrors tests/backend/test_sync_backend.py.
# --------------------------------------------------------------------------- #


async def blocking(func, *args):
    """Run a blocking client call on the default executor (off the event loop)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)


async def connect(uri: str) -> WebSocketTransport:
    """Open the shipped :class:`WebSocketTransport` (``uri`` may carry ``?token=``)."""
    return await blocking(WebSocketTransport, uri)


async def poll_until(transport, document_id, count, deadline=5.0) -> Tuple[bytes, ...]:
    """Poll until ``count`` frames have arrived for ``document_id`` (or timeout)."""
    frames: list = []
    end = time.monotonic() + deadline
    while len(frames) < count and time.monotonic() < end:
        frames.extend(await blocking(transport.poll, document_id))
        if len(frames) < count:
            await asyncio.sleep(0.02)
    return tuple(frames)


async def drain(transport, document_id, window=0.3) -> Tuple[bytes, ...]:
    """Best-effort drain of anything queued for ``document_id`` within ``window``."""
    end = time.monotonic() + window
    frames: list = []
    while time.monotonic() < end:
        frames.extend(await blocking(transport.poll, document_id))
        await asyncio.sleep(0.02)
    return tuple(frames)


async def handshake_status(uri: str) -> Optional[int]:
    """Attempt a raw connect; return the rejection HTTP status, or ``None`` if accepted.

    ``None`` means the handshake was ACCEPTED (the connection opened and was closed).
    An integer (401/403) means the backend rejected the upgrade at ``process_request``
    — proving the client obtained NO project data.
    """
    from websockets.exceptions import InvalidStatus
    from websockets.sync.client import connect as raw_connect

    def _try() -> Optional[int]:
        try:
            conn = raw_connect(uri)
        except InvalidStatus as exc:
            return int(exc.response.status_code)
        conn.close()
        return None

    return await blocking(_try)
