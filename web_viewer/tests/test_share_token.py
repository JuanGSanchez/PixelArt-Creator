"""Share-link token: pure verify surface + the live token-enforcing handshake.

Phase-13 Slice-13E, task T13E-B06 (ADR-0036 §1 + Addendum A; spec REQ-P13-WEB-002/-005;
acceptance **SC-P13-WEB-005-1/-2**, **SC-P13-WEB-002-1**). Two layers, one file:

* **Pure** unit + Hypothesis coverage of
  :func:`~pixelart_creator.logic.share_token.verify` — a valid token round-trips; an
  expired / wrong-``aud`` / wrong-``iss`` / bad-signature / ``alg:"none"`` / over-TTL
  token each raises :class:`~pixelart_creator.logic.share_token.ShareTokenError`
  yielding no claims.
* **Live** handshake over an in-process :class:`~sync_backend.server.SyncServer` started
  with ``share_secret=…``: a valid, correctly-scoped, in-project token lets a
  ``websockets`` client connect and receive that project's JOIN backlog; every rejected
  token is refused at the handshake (HTTP 401/403) so the client receives NO data.
* A **source audit** asserting ZERO ``eval``/``exec`` on the web-input path and NO new
  (non-stdlib) dependency in the pure token module.

Qt-free and self-contained (no external server), so it runs in the DEFAULT test gate.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import pixelart_creator.logic.share_token as share_token_module
import sync_backend.server as server_module
from pixelart_creator.logic import sync_protocol
from pixelart_creator.logic.constants import SHARE_TOKEN_MAX_TTL_S
from pixelart_creator.logic.share_token import ShareTokenError, verify
from sync_backend.server import SyncServer
from sync_backend.store import UpdateStore
from web_viewer.tests._helpers import (
    AUD,
    IAT,
    ISS,
    NOW_EXPIRED,
    NOW_VALID,
    SECRET,
    connect,
    forge_token,
    handshake_status,
    make_claims,
    mint_token,
    poll_until,
    seed_update_frame,
    tamper,
)

DOC = "project-alpha"


# --------------------------------------------------------------------------- #
# Pure verify() surface (deterministic, no server).
# --------------------------------------------------------------------------- #


def test_valid_token_verifies_and_returns_claims():
    token = mint_token(DOC, scope="view", iat=IAT, ttl=3600)
    claims = verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)
    assert claims["project_id"] == DOC
    assert claims["scope"] == "view"
    assert claims["iss"] == ISS and claims["aud"] == AUD


def test_expired_token_is_rejected():
    token = mint_token(DOC, iat=IAT, ttl=3600)
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_EXPIRED)


def test_wrong_audience_is_rejected():
    token = mint_token(DOC, aud="some-other-audience")
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_wrong_issuer_is_rejected():
    token = mint_token(DOC, iss="some-other-issuer")
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_bad_signature_is_rejected():
    # Same claims, a DIFFERENT signing secret -> signature mismatch.
    token = mint_token(DOC, secret="a-completely-different-secret")
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_tampered_payload_is_rejected():
    token = tamper(mint_token(DOC))
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_alg_none_token_is_rejected_even_when_correctly_signed():
    # A correctly-HMAC-signed token whose header downgrades alg to "none" must still be
    # refused (the classic JWT alg-substitution attack): verify pins alg == HS256.
    forged = forge_token(
        {"alg": "none", "typ": "share+jwt"},
        make_claims(DOC),
    )
    with pytest.raises(ShareTokenError):
        verify(forged, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_wrong_typ_token_is_rejected():
    forged = forge_token(
        {"alg": "HS256", "typ": "jwt"},
        make_claims(DOC),
    )
    with pytest.raises(ShareTokenError):
        verify(forged, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


def test_over_ttl_token_is_rejected_even_when_not_yet_expired():
    # exp - iat exceeds the lifetime cap; now is BEFORE exp (not expired), so this
    # isolates the TTL-cap branch (SHARE_TOKEN_MAX_TTL_S).
    token = mint_token(DOC, iat=IAT, ttl=SHARE_TOKEN_MAX_TTL_S + 1)
    now_before_exp = IAT + 5
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=now_before_exp)


def test_max_ttl_token_at_the_cap_is_accepted():
    # Boundary: exp - iat == cap is allowed (the reject is strictly ``>`` the cap).
    token = mint_token(DOC, iat=IAT, ttl=SHARE_TOKEN_MAX_TTL_S)
    claims = verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=IAT + 5)
    assert claims["project_id"] == DOC


# --------------------------------------------------------------------------- #
# Pure edge-case coverage of mint()/verify() error branches (Article VII gate).
# These drive the untrusted-input rejection paths the live handshake relies on,
# using stdlib-only forging to reach branches past the signature check.
# --------------------------------------------------------------------------- #

_HEADER = {"alg": "HS256", "typ": "share+jwt"}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _forge_segments(header_b64: str, payload_b64: str, secret: str = SECRET) -> str:
    """Assemble a token from raw segments with a CORRECT HMAC (bypasses mint)."""
    signing_input = f"{header_b64}.{payload_b64}"
    sig = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_b64(sig)}"


def _verify(token):
    return verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


# --- mint() rejections -----------------------------------------------------------


def test_mint_rejects_empty_string_secret():
    with pytest.raises(ShareTokenError):
        mint_token(DOC, secret="")


def test_mint_accepts_bytes_secret_and_round_trips():
    token = share_token_module.mint(make_claims(DOC), b"raw-bytes-secret")
    claims = verify(
        token, b"raw-bytes-secret", expected_iss=ISS, expected_aud=AUD, now=NOW_VALID
    )
    assert claims["project_id"] == DOC


def test_mint_rejects_empty_bytes_secret():
    with pytest.raises(ShareTokenError):
        share_token_module.mint(make_claims(DOC), b"")


def test_mint_rejects_non_str_bytes_secret():
    with pytest.raises(ShareTokenError):
        share_token_module.mint(make_claims(DOC), 12345)  # type: ignore[arg-type]


def test_mint_rejects_non_mapping_claims():
    with pytest.raises(ShareTokenError):
        share_token_module.mint(["not", "a", "mapping"], SECRET)  # type: ignore


def test_mint_rejects_missing_required_claim():
    with pytest.raises(ShareTokenError):
        share_token_module.mint({"aud": AUD}, SECRET)  # missing iss/project_id/...


def test_mint_rejects_sub_diverging_from_project_id():
    with pytest.raises(ShareTokenError):
        mint_token(DOC, sub="a-different-subject")


def test_mint_accepts_explicit_matching_sub():
    # sub explicitly supplied and equal to project_id is honoured (no divergence).
    token = share_token_module.mint(make_claims(DOC, sub=DOC), SECRET)
    assert _verify(token)["sub"] == DOC


def test_mint_rejects_token_exceeding_max_chars():
    # An oversized (unchecked) extra claim inflates the token past the char cap.
    with pytest.raises(ShareTokenError):
        mint_token(DOC, note="x" * 20_000)


# --- verify() format rejections --------------------------------------------------


def test_verify_rejects_non_str_token():
    with pytest.raises(ShareTokenError):
        _verify(12345)


def test_verify_rejects_empty_token():
    with pytest.raises(ShareTokenError):
        _verify("")


def test_verify_rejects_token_over_max_chars():
    with pytest.raises(ShareTokenError):
        _verify("x" * 9000)


def test_verify_rejects_wrong_segment_count():
    with pytest.raises(ShareTokenError):
        _verify("only.two")


def test_verify_rejects_non_base64_signature():
    # A one-char segment pads to "a===", which is an invalid base64 length -> raises in
    # _b64url_decode (before the signature compare).
    with pytest.raises(ShareTokenError):
        _verify("aa.bb.a")


def test_verify_rejects_non_json_header():
    token = _forge_segments(
        _b64(b"not-json-at-all"), _b64(json.dumps(make_claims(DOC)).encode("utf-8"))
    )
    with pytest.raises(ShareTokenError):
        _verify(token)


def test_verify_rejects_non_object_payload():
    header_b64 = _b64(json.dumps(_HEADER).encode("utf-8"))
    token = _forge_segments(header_b64, _b64(b"[1, 2, 3]"))  # JSON array, not object
    with pytest.raises(ShareTokenError):
        _verify(token)


# --- verify() claim rejections (correctly signed, so the claim gate is reached) ---


def test_verify_rejects_sub_diverging_from_project_id():
    token = forge_token(_HEADER, {**make_claims(DOC), "sub": "other-subject"})
    with pytest.raises(ShareTokenError):
        _verify(token)


def test_verify_rejects_exp_not_after_iat():
    token = forge_token(_HEADER, {**make_claims(DOC), "iat": 1000, "exp": 1000})
    with pytest.raises(ShareTokenError):
        _verify(token)


def test_verify_rejects_empty_project_id():
    token = forge_token(_HEADER, {**make_claims(DOC), "project_id": ""})
    with pytest.raises(ShareTokenError):
        _verify(token)


def test_verify_rejects_overlong_project_id_claim():
    token = forge_token(_HEADER, make_claims("x" * 2000))
    with pytest.raises(ShareTokenError):
        _verify(token)


def test_verify_rejects_boolean_iat_claim():
    # bool is an int subclass; the validator must still reject a truthy iat.
    token = forge_token(_HEADER, {**make_claims(DOC), "iat": True})
    with pytest.raises(ShareTokenError):
        _verify(token)


# --------------------------------------------------------------------------- #
# Hypothesis: property coverage of the mint -> verify round trip + claim rejection.
# --------------------------------------------------------------------------- #

# Bounded, portable strategies (no surrogates; lengths well under the claim cap).
_id_text = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=64,
)
_scope_text = st.sampled_from(["view", "edit", "comment", "owner"])
_iat = st.integers(min_value=1, max_value=2_000_000_000)
_ttl = st.integers(min_value=1, max_value=SHARE_TOKEN_MAX_TTL_S)


@settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(project_id=_id_text, scope=_scope_text, iat=_iat, ttl=_ttl)
def test_property_valid_token_round_trips(project_id, scope, iat, ttl):
    token = mint_token(project_id, scope=scope, iat=iat, ttl=ttl)
    now = iat + ttl // 2  # strictly inside (iat, exp) for ttl >= 1... ensure < exp
    if now >= iat + ttl:  # ttl == 1 -> now == iat, still < exp; guard defensively
        now = iat
    claims = verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=now)
    assert claims["project_id"] == project_id
    assert claims["scope"] == scope
    assert claims["sub"] == project_id  # mint defaults sub == project_id (Addendum A.3)


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(project_id=_id_text, bad_aud=_id_text)
def test_property_audience_mismatch_always_rejected(project_id, bad_aud):
    if bad_aud == AUD:
        bad_aud += "-x"
    token = mint_token(project_id, aud=bad_aud)
    with pytest.raises(ShareTokenError):
        verify(token, SECRET, expected_iss=ISS, expected_aud=AUD, now=NOW_VALID)


# --------------------------------------------------------------------------- #
# Live handshake over the in-process token-mode SyncServer (SC-P13-WEB-005-1).
# --------------------------------------------------------------------------- #


def _token_server(store=None, now=NOW_VALID):
    """A SyncServer in web-viewer token mode with a deterministic injected clock."""
    return SyncServer(
        store=store,
        share_secret=SECRET,
        expected_iss=ISS,
        expected_aud=AUD,
        time_source=lambda: float(now),
    )


def test_valid_token_connects_and_receives_join_backlog():
    """SC-P13-WEB-005-1: a valid, unexpired, in-scope, in-project token connects and
    the viewer receives that project's persisted JOIN backlog."""

    async def scenario():
        store = UpdateStore()
        store.append(DOC, seed_update_frame(DOC, "backlog-payload"))
        server = _token_server(store=store)
        host, port = await server.start()
        token = mint_token(DOC, scope="view", iat=IAT, ttl=3600)
        uri = f"ws://{host}:{port}/?token={token}"
        viewer = None
        try:
            viewer = await connect(uri)  # handshake accepted (valid token)
            await blocking_join(viewer, DOC)
            frames = await poll_until(viewer, DOC, 1)
            assert len(frames) == 1
            message = sync_protocol.decode_message(frames[0])
            assert message.kind is sync_protocol.ControlKind.UPDATE
            assert message.document_id == DOC
        finally:
            if viewer is not None:
                await close(viewer)
            await server.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "make_bad, expected_status",
    [
        ("expired", 403),
        ("wrong_aud", 403),
        ("wrong_iss", 403),
        ("bad_sig", 403),
        ("tampered", 403),
        ("alg_none", 403),
        ("over_ttl", 403),
        ("missing", 401),
    ],
)
def test_rejected_tokens_are_refused_at_handshake(make_bad, expected_status):
    """SC-P13-WEB-005-2: every invalid token is refused at the WS handshake (401/403)
    and NO project data is served (the connection never opens)."""

    async def scenario():
        # Seed the target project so a *successful* connect WOULD leak data; the point
        # is that these rejected handshakes never reach it.
        store = UpdateStore()
        store.append(DOC, seed_update_frame(DOC, "secret-backlog"))
        # For the expired case the server clock is advanced past exp; otherwise a
        # normal in-window clock so only the token defect (not the clock) rejects.
        now = NOW_EXPIRED if make_bad == "expired" else NOW_VALID
        server = _token_server(store=store, now=now)
        host, port = await server.start()
        try:
            token = _bad_token(make_bad)
            if token is None:
                uri = f"ws://{host}:{port}/"  # missing token entirely
            else:
                uri = f"ws://{host}:{port}/?token={token}"
            status = await handshake_status(uri)
            assert status == expected_status
        finally:
            await server.stop()

    asyncio.run(scenario())


def _bad_token(kind):
    if kind == "missing":
        return None
    if kind == "expired":
        return mint_token(DOC, iat=IAT, ttl=3600)  # rejected by advanced clock
    if kind == "wrong_aud":
        return mint_token(DOC, aud="not-this-audience")
    if kind == "wrong_iss":
        return mint_token(DOC, iss="not-this-issuer")
    if kind == "bad_sig":
        return mint_token(DOC, secret="a-different-operator-secret")
    if kind == "tampered":
        return tamper(mint_token(DOC))
    if kind == "alg_none":
        return forge_token({"alg": "none", "typ": "share+jwt"}, make_claims(DOC))
    if kind == "over_ttl":
        return mint_token(DOC, iat=IAT, ttl=SHARE_TOKEN_MAX_TTL_S + 1)
    raise AssertionError(f"unknown bad-token kind {kind!r}")


def test_rejected_token_client_gets_no_backlog_frames():
    """SC-P13-WEB-005-2 (data-leak guard): after a rejected handshake the client holds
    an open, working connection to nothing — a *valid* peer is unaffected, and the
    rejected raw attempt yields zero frames because it never connected."""

    async def scenario():
        store = UpdateStore()
        store.append(DOC, seed_update_frame(DOC, "private"))
        server = _token_server(store=store)
        host, port = await server.start()
        good = None
        try:
            # A rejected connect never opens -> the attacker obtains no frames.
            bad_token = mint_token(DOC, aud="wrong")
            status = await handshake_status(f"ws://{host}:{port}/?token={bad_token}")
            assert status == 403

            # Meanwhile a valid viewer connects and DOES get the backlog (control).
            good_token = mint_token(DOC, scope="view")
            good = await connect(f"ws://{host}:{port}/?token={good_token}")
            await blocking_join(good, DOC)
            frames = await poll_until(good, DOC, 1)
            assert len(frames) == 1
        finally:
            if good is not None:
                await close(good)
            await server.stop()

    asyncio.run(scenario())


# --------------------------------------------------------------------------- #
# Tiny transport helpers local to this module (executor-driven).
# --------------------------------------------------------------------------- #


async def blocking_join(transport, document_id):
    from web_viewer.tests._helpers import blocking

    await blocking(transport.join, document_id)


async def close(transport):
    from web_viewer.tests._helpers import blocking

    await blocking(transport.close)


# --------------------------------------------------------------------------- #
# Source audit: ZERO eval/exec on the web-input path + NO new dependency (D1).
# --------------------------------------------------------------------------- #


def _web_input_path_files():
    """The Python files on the untrusted web-input path (token + handshake)."""
    files = [
        Path(share_token_module.__file__).resolve(),  # the pure token seam
        Path(server_module.__file__).resolve(),  # the token-enforcing handshake
    ]
    # Optionally include the web_viewer Python side (stdlib-only dev server).
    import web_viewer

    web_root = Path(web_viewer.__file__).resolve().parent
    files.extend(sorted(web_root.glob("*.py")))
    return files


def _calls_named(path, names):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in names:
                found.add(func.id)
            elif isinstance(func, ast.Attribute) and func.attr in names:
                found.add(func.attr)
    return found


def test_no_eval_or_exec_on_the_web_input_path():
    for path in _web_input_path_files():
        source = path.read_text(encoding="utf-8")
        # AST-level: no eval()/exec() call nodes anywhere on the path.
        assert not _calls_named(
            path, {"eval", "exec"}
        ), f"{path.name} contains an eval/exec call"
        # Textual belt-and-braces (catches getattr-style obfuscation of the literal).
        assert "eval(" not in source, f"{path.name} contains 'eval(' text"
        assert "exec(" not in source, f"{path.name} contains 'exec(' text"


def _imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module)
    return roots


def test_share_token_introduces_no_new_dependency():
    # share_token.py is stdlib-only (+ the pure logic.constants leaf): the signed-token
    # contract adds NO Python dependency (ADR-0036 §1 / spec §10 D1 "no JWT library").
    path = Path(share_token_module.__file__).resolve()
    allowed_prefixes = ("pixelart_creator.logic",)
    stdlib = set(sys.stdlib_module_names)
    for imported in _imported_roots(path):
        root = imported.split(".")[0]
        assert root in stdlib or imported.startswith(
            allowed_prefixes
        ), f"share_token.py imports non-stdlib/non-logic module {imported!r}"
