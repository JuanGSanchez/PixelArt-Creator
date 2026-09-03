"""Tests for pixelart_creator.data.cloud.auth (Phase-10 Slice A, no Qt).

Covers the pure, network-free desktop-auth building blocks (REQ-P10-DATA-008,
research §2): the PKCE ``S256`` verifier/challenge crypto, verifier
validation, the authorization-URL builder, the loopback redirect capture over
``127.0.0.1`` (driven by a client thread — no external network), and the
token-exchange / refresh / Device-Grant flows through an injected DI transport
(no HTTP, no real provider).
"""

from __future__ import annotations

import base64
import hashlib
import threading
import urllib.request

import pytest

from pixelart_creator.data.cloud.auth import (
    AuthError,
    LoopbackRedirectServer,
    PkcePair,
    build_authorization_url,
    create_pkce_pair,
    exchange_code,
    poll_device_token,
    refresh_token,
    request_device_code,
    verify_challenge,
)
from pixelart_creator.data.cloud.port import CloudError

# --- PKCE (RFC 7636) -------------------------------------------------------- #


def test_create_pkce_pair_deterministic_given_verifier():
    verifier = "a" * 43
    pair = create_pkce_pair(verifier=verifier)
    assert isinstance(pair, PkcePair)
    assert pair.verifier == verifier
    assert pair.method == "S256"
    # Independently recompute the S256 challenge to prove correctness.
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert pair.challenge == expected
    # Determinism: same verifier -> same challenge.
    assert create_pkce_pair(verifier=verifier).challenge == pair.challenge


def test_create_pkce_pair_random_is_self_verifiable():
    pair = create_pkce_pair()
    assert 43 <= len(pair.verifier) <= 128
    assert verify_challenge(pair.verifier, pair.challenge) is True


def test_two_random_pairs_differ():
    assert create_pkce_pair().verifier != create_pkce_pair().verifier


def test_verify_challenge_rejects_wrong_challenge():
    pair = create_pkce_pair(verifier="b" * 43)
    assert verify_challenge(pair.verifier, "not-the-challenge") is False


def test_verify_challenge_rejects_non_str_challenge():
    with pytest.raises(AuthError):
        verify_challenge("b" * 43, 123)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["short", "a" * 129])
def test_verifier_length_bounds(bad):
    with pytest.raises(AuthError):
        create_pkce_pair(verifier=bad)


def test_verifier_alphabet_enforced():
    # 43 chars but containing a disallowed character.
    with pytest.raises(AuthError):
        create_pkce_pair(verifier="!" + "a" * 42)


def test_verifier_non_str_rejected():
    with pytest.raises(AuthError):
        create_pkce_pair(verifier=12345)  # type: ignore[arg-type]


# --- authorization URL builder ---------------------------------------------- #


def test_build_authorization_url_contains_pkce_params():
    pair = create_pkce_pair(verifier="c" * 43)
    url = build_authorization_url(
        "https://auth.example/oauth",
        client_id="cid",
        redirect_uri="http://127.0.0.1:5555/",
        pkce=pair,
        scope="files",
        state="xyz",
    )
    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert f"code_challenge={pair.challenge}" in url
    assert url.startswith("https://auth.example/oauth?")


def test_build_authorization_url_appends_with_ampersand_when_query_present():
    pair = create_pkce_pair(verifier="c" * 43)
    url = build_authorization_url(
        "https://auth.example/oauth?foo=bar",
        client_id="cid",
        redirect_uri="http://127.0.0.1:5555/",
        pkce=pair,
        scope="files",
        state="xyz",
    )
    assert "oauth?foo=bar&response_type=code" in url


def test_build_authorization_url_rejects_empty_field():
    pair = create_pkce_pair(verifier="c" * 43)
    with pytest.raises(AuthError):
        build_authorization_url(
            "",
            client_id="cid",
            redirect_uri="http://127.0.0.1:5555/",
            pkce=pair,
            scope="files",
            state="xyz",
        )


def test_build_authorization_url_rejects_non_pkce():
    with pytest.raises(AuthError):
        build_authorization_url(
            "https://auth.example/oauth",
            client_id="cid",
            redirect_uri="http://127.0.0.1:5555/",
            pkce="not-a-pair",  # type: ignore[arg-type]
            scope="files",
            state="xyz",
        )


# --- loopback redirect capture (RFC 8252) over localhost -------------------- #


def _hit(url: str) -> None:
    try:
        urllib.request.urlopen(url, timeout=5).read()
    except Exception:
        pass


def test_loopback_captures_code_and_state():
    with LoopbackRedirectServer() as server:
        assert server.port > 0
        assert server.redirect_uri.startswith("http://127.0.0.1:")
        target = f"{server.redirect_uri}?code=AUTHCODE&state=st8"
        client = threading.Thread(target=_hit, args=(target,))
        client.start()
        code, state = server.wait_for_code(expected_state="st8")
        client.join(timeout=5)
    assert code == "AUTHCODE"
    assert state == "st8"


def test_loopback_state_mismatch_raises():
    with LoopbackRedirectServer() as server:
        target = f"{server.redirect_uri}?code=AUTHCODE&state=WRONG"
        client = threading.Thread(target=_hit, args=(target,))
        client.start()
        with pytest.raises(AuthError):
            server.wait_for_code(expected_state="expected")
        client.join(timeout=5)


def test_loopback_error_response_raises():
    with LoopbackRedirectServer() as server:
        target = f"{server.redirect_uri}?error=access_denied"
        client = threading.Thread(target=_hit, args=(target,))
        client.start()
        with pytest.raises(AuthError):
            server.wait_for_code()
        client.join(timeout=5)


def test_loopback_missing_code_raises():
    with LoopbackRedirectServer() as server:
        target = f"{server.redirect_uri}?state=only"
        client = threading.Thread(target=_hit, args=(target,))
        client.start()
        with pytest.raises(AuthError):
            server.wait_for_code()
        client.join(timeout=5)


# --- token exchange / refresh via DI transport (no network) ----------------- #


def _ok_transport(url, form):
    return {"access_token": "AT", "refresh_token": "RT", "_form": dict(form)}


def test_exchange_code_via_transport():
    captured = {}

    def transport(url, form):
        captured["url"] = url
        captured["form"] = dict(form)
        return {"access_token": "AT"}

    result = exchange_code(
        "https://token",
        client_id="cid",
        code="CODE",
        redirect_uri="http://127.0.0.1:1/",
        verifier="d" * 43,
        transport=transport,
    )
    assert result["access_token"] == "AT"
    assert captured["form"]["grant_type"] == "authorization_code"
    assert captured["form"]["code_verifier"] == "d" * 43


def test_exchange_code_bad_verifier_raises():
    with pytest.raises(AuthError):
        exchange_code(
            "https://token",
            client_id="cid",
            code="CODE",
            redirect_uri="http://127.0.0.1:1/",
            verifier="short",
            transport=_ok_transport,
        )


def test_exchange_code_missing_access_token_raises():
    with pytest.raises(AuthError):
        exchange_code(
            "https://token",
            client_id="cid",
            code="CODE",
            redirect_uri="http://127.0.0.1:1/",
            verifier="d" * 43,
            transport=lambda url, form: {"no": "token"},
        )


def test_exchange_code_error_response_raises():
    with pytest.raises(AuthError):
        exchange_code(
            "https://token",
            client_id="cid",
            code="CODE",
            redirect_uri="http://127.0.0.1:1/",
            verifier="d" * 43,
            transport=lambda url, form: {"error": "invalid_grant"},
        )


def test_exchange_code_non_mapping_response_raises():
    with pytest.raises(AuthError):
        exchange_code(
            "https://token",
            client_id="cid",
            code="CODE",
            redirect_uri="http://127.0.0.1:1/",
            verifier="d" * 43,
            transport=lambda url, form: "not-a-mapping",
        )


def test_refresh_token_via_transport():
    result = refresh_token(
        "https://token",
        client_id="cid",
        refresh_token_value="RT",
        transport=_ok_transport,
    )
    assert result["access_token"] == "AT"
    assert result["_form"]["grant_type"] == "refresh_token"


def test_refresh_token_rejects_empty_refresh():
    with pytest.raises(AuthError):
        refresh_token(
            "https://token",
            client_id="cid",
            refresh_token_value="",
            transport=_ok_transport,
        )


# --- device grant (RFC 8628) ------------------------------------------------ #


def test_request_device_code_returns_mapping():
    resp = request_device_code(
        "https://device",
        client_id="cid",
        scope="files",
        transport=lambda url, form: {"device_code": "DC", "user_code": "UC"},
    )
    assert resp["device_code"] == "DC"


def test_request_device_code_missing_device_code_raises():
    with pytest.raises(AuthError):
        request_device_code(
            "https://device",
            client_id="cid",
            scope="files",
            transport=lambda url, form: {"nope": 1},
        )


def test_poll_device_token_default_max_attempts_is_cloud_retry_limit():
    # REQ-P10-LOGIC-005 (R-25): retry never fails transiently -- the default
    # bound on Device-Grant polling attempts IS constants.CLOUD_RETRY_LIMIT,
    # by identity (S12: no duplicated magic number).
    import inspect

    from pixelart_creator.logic.constants import CLOUD_RETRY_LIMIT

    default = inspect.signature(poll_device_token).parameters["max_attempts"].default
    assert default is CLOUD_RETRY_LIMIT


def test_poll_device_token_succeeds_after_pending():
    calls = {"n": 0}

    def transport(url, form):
        calls["n"] += 1
        if calls["n"] < 2:
            return {"error": "authorization_pending"}
        return {"access_token": "AT"}

    result = poll_device_token(
        "https://token",
        client_id="cid",
        device_code="DC",
        transport=transport,
        max_attempts=5,
    )
    assert result["access_token"] == "AT"
    assert calls["n"] == 2


def test_poll_device_token_hard_error_raises():
    with pytest.raises(AuthError):
        poll_device_token(
            "https://token",
            client_id="cid",
            device_code="DC",
            transport=lambda url, form: {"error": "access_denied"},
        )


def test_poll_device_token_exhausts_attempts():
    with pytest.raises(AuthError):
        poll_device_token(
            "https://token",
            client_id="cid",
            device_code="DC",
            transport=lambda url, form: {"error": "authorization_pending"},
            max_attempts=2,
        )


def test_poll_device_token_non_mapping_pending_then_exhausts():
    with pytest.raises(AuthError):
        poll_device_token(
            "https://token",
            client_id="cid",
            device_code="DC",
            transport=lambda url, form: "garbage",
            max_attempts=1,
        )


def test_poll_device_token_rejects_empty_device_code():
    with pytest.raises(AuthError):
        poll_device_token(
            "https://token",
            client_id="cid",
            device_code="",
            transport=_ok_transport,
        )


def test_poll_device_token_rejects_bad_max_attempts():
    with pytest.raises(AuthError):
        poll_device_token(
            "https://token",
            client_id="cid",
            device_code="DC",
            transport=_ok_transport,
            max_attempts=0,
        )


# --- exception hierarchy ---------------------------------------------------- #


def test_auth_error_is_cloud_error():
    assert issubclass(AuthError, CloudError)
    assert issubclass(AuthError, ValueError)
