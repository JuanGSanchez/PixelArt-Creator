# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Provider-agnostic OAuth helpers: PKCE, loopback capture, token exchange.

Phase-10 Slice A (ADR-0026 §3; spec REQ-P10-DATA-008). Zero Qt, zero
provider SDK. Holds the desktop-auth building blocks that are pure and testable
without a live provider:

* **PKCE (RFC 7636)** — :func:`create_pkce_pair` / :func:`verify_challenge`: the pure,
  deterministic ``code_verifier`` -> ``S256`` ``code_challenge`` crypto (the unit-
  testable core, SC test target).
* **Authorization URL (RFC 8252)** — :func:`build_authorization_url`: a pure query
  builder; only *launching the system browser* is delegated to ``ui/`` (never an
  embedded webview).
* **Loopback redirect capture (RFC 8252)** — :class:`LoopbackRedirectServer`: a
  single-request ``127.0.0.1`` listener on an ephemeral port that captures the
  ``code``/``state`` from the redirect, testable over localhost with no external
  network.
* **Token exchange / refresh / Device Grant (RFC 8628)** — :func:`exchange_code`,
  :func:`refresh_token`, :func:`request_device_code`, :func:`poll_device_token`:
  parameterised on an injected ``transport`` callable ``(url, form) -> mapping`` so
  the flow is provider-agnostic and testable without network. The real HTTP transport
  (and the provider endpoints) live in the credential-gated real adapters, out of
  Slice A — no ``urllib``/HTTP type appears above the port.

Tokens returned here are handed to :mod:`pixelart_creator.data.cloud.token_store`;
they never leave ``data/cloud/`` (REQ-P10-DATA-008, Article VII §3).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import TracebackType
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Type
from urllib.parse import parse_qs, urlencode, urlparse

from pixelart_creator.data.cloud.port import CloudError
from pixelart_creator.logic.constants import CLOUD_RETRY_LIMIT

__all__ = [
    "AuthError",
    "PkcePair",
    "TokenTransport",
    "create_pkce_pair",
    "verify_challenge",
    "build_authorization_url",
    "LoopbackRedirectServer",
    "exchange_code",
    "refresh_token",
    "request_device_code",
    "poll_device_token",
]

#: RFC 7636 §4.1 code-verifier length bounds.
_VERIFIER_MIN_LEN = 43
_VERIFIER_MAX_LEN = 128
#: RFC 7636 unreserved verifier alphabet.
_VERIFIER_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)

#: An injected token-endpoint transport: ``(url, form_fields) -> json mapping``.
TokenTransport = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


class AuthError(CloudError):
    """Raised on an OAuth/PKCE failure (bad verifier, state mismatch, no token)."""


def _b64url_nopad(raw: bytes) -> str:
    """Base64url-encode ``raw`` with padding stripped (RFC 7636)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class PkcePair:
    """A PKCE verifier/challenge pair (``S256``).

    Attributes:
        verifier: The high-entropy ``code_verifier`` (kept client-side).
        challenge: The ``code_challenge`` sent in the authorization request.
        method: The transform method — always ``"S256"``.
    """

    verifier: str
    challenge: str
    method: str = "S256"


def _generate_verifier(n_bytes: int = 32) -> str:
    """Generate a random RFC 7636 code verifier (43 chars for 32 bytes)."""
    return _b64url_nopad(secrets.token_bytes(n_bytes))


def _validate_verifier(verifier: str) -> None:
    if not isinstance(verifier, str):
        raise AuthError(f"code_verifier must be a str, got {verifier!r}")
    if not (_VERIFIER_MIN_LEN <= len(verifier) <= _VERIFIER_MAX_LEN):
        raise AuthError(
            f"code_verifier length {len(verifier)} outside "
            f"{_VERIFIER_MIN_LEN}..{_VERIFIER_MAX_LEN} (RFC 7636)"
        )
    if any(ch not in _VERIFIER_ALPHABET for ch in verifier):
        raise AuthError("code_verifier contains characters outside the RFC 7636 set")


def _s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64url_nopad(digest)


def create_pkce_pair(*, verifier: Optional[str] = None) -> PkcePair:
    """Create an ``S256`` PKCE pair (deterministic given ``verifier``).

    Args:
        verifier: An explicit code verifier (for deterministic tests). If ``None``,
            a cryptographically random one is generated.

    Raises:
        AuthError: If ``verifier`` is malformed (length / alphabet, RFC 7636).
    """
    if verifier is None:
        verifier = _generate_verifier()
    _validate_verifier(verifier)
    return PkcePair(
        verifier=verifier, challenge=_s256_challenge(verifier), method="S256"
    )


def verify_challenge(verifier: str, challenge: str) -> bool:
    """Return whether ``challenge`` is the ``S256`` challenge of ``verifier``.

    Uses a constant-time comparison. Raises :class:`AuthError` on a malformed
    verifier.
    """
    _validate_verifier(verifier)
    if not isinstance(challenge, str):
        raise AuthError(f"challenge must be a str, got {challenge!r}")
    return hmac.compare_digest(_s256_challenge(verifier), challenge)


def build_authorization_url(
    authorization_endpoint: str,
    *,
    client_id: str,
    redirect_uri: str,
    pkce: PkcePair,
    scope: str,
    state: str,
) -> str:
    """Build the RFC 8252 Authorization-Code + PKCE authorization URL (pure).

    The caller (``ui/``) opens the result in the *system browser*.
    """
    for name, value in (
        ("authorization_endpoint", authorization_endpoint),
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("scope", scope),
        ("state", state),
    ):
        if not isinstance(value, str) or not value:
            raise AuthError(f"{name} must be a non-empty str, got {value!r}")
    if not isinstance(pkce, PkcePair):
        raise AuthError(f"pkce must be a PkcePair, got {pkce!r}")
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": pkce.method,
        }
    )
    sep = "&" if "?" in authorization_endpoint else "?"
    return f"{authorization_endpoint}{sep}{query}"


class LoopbackRedirectServer:
    """A single-request ``127.0.0.1`` listener that captures the OAuth redirect.

    RFC 8252 loopback interface redirection. Bind to an ephemeral port
    (``port=0``), put the resulting :attr:`redirect_uri` in the authorization
    request, then call :meth:`wait_for_code` to block for one redirect and return
    the ``(code, state)`` query values. Testable over localhost with no external
    network. Use as a context manager to guarantee the socket is closed.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        """Bind an HTTP listener on ``host``/``port`` (``0`` = ephemeral)."""
        self._captured: Dict[str, str] = {}
        self._host = host
        server = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(
                self,
            ) -> None:  # noqa: N802 - required BaseHTTPRequestHandler name
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                for key in ("code", "state", "error"):
                    if key in params and params[key]:
                        server._captured[key] = params[key][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Authorization received. You may close this window.")

            def log_message(self, *_args: Any) -> None:  # silence stderr logging
                return

        self._httpd = HTTPServer((host, port), _Handler)

    @property
    def port(self) -> int:
        """Return the bound TCP port number the redirect server listens on."""
        return int(self._httpd.server_address[1])

    @property
    def redirect_uri(self) -> str:
        """The loopback redirect URI to register in the authorization request."""
        return f"http://{self._host}:{self.port}/"

    def wait_for_code(self, expected_state: Optional[str] = None) -> Tuple[str, str]:
        """Handle one redirect request and return the captured ``(code, state)``.

        Raises:
            AuthError: If the provider returned an ``error``, no ``code`` arrived,
                or ``expected_state`` does not match the returned ``state`` (CSRF).
        """
        self._httpd.handle_request()
        if "error" in self._captured:
            raise AuthError(f"authorization error: {self._captured['error']}")
        code = self._captured.get("code")
        state = self._captured.get("state", "")
        if not code:
            raise AuthError("no authorization code received on the loopback redirect")
        if expected_state is not None and not hmac.compare_digest(
            expected_state, state
        ):
            raise AuthError("state mismatch on the loopback redirect (possible CSRF)")
        return code, state

    def close(self) -> None:
        """Close the underlying socket."""
        self._httpd.server_close()

    def __enter__(self) -> "LoopbackRedirectServer":
        """Enter the context manager, returning this server instance."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager, closing the underlying socket."""
        self.close()


def _require_token_response(response: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(response, Mapping):
        raise AuthError(f"token response must be a mapping, got {response!r}")
    if "error" in response:
        raise AuthError(f"token endpoint error: {response['error']}")
    if not response.get("access_token"):
        raise AuthError("token response missing access_token")
    return response


def exchange_code(
    token_endpoint: str,
    *,
    client_id: str,
    code: str,
    redirect_uri: str,
    verifier: str,
    transport: TokenTransport,
) -> Mapping[str, Any]:
    """Exchange an authorization ``code`` + PKCE ``verifier`` for tokens.

    ``transport`` performs the actual POST (injected so this stays network-free and
    provider-agnostic). Returns the validated token mapping.
    """
    _validate_verifier(verifier)
    form = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    return _require_token_response(transport(token_endpoint, form))


def refresh_token(
    token_endpoint: str,
    *,
    client_id: str,
    refresh_token_value: str,
    transport: TokenTransport,
) -> Mapping[str, Any]:
    """Refresh an access token from a stored refresh token via ``transport``."""
    if not isinstance(refresh_token_value, str) or not refresh_token_value:
        raise AuthError("refresh_token_value must be a non-empty str")
    form = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token_value,
    }
    return _require_token_response(transport(token_endpoint, form))


def request_device_code(
    device_endpoint: str,
    *,
    client_id: str,
    scope: str,
    transport: TokenTransport,
) -> Mapping[str, Any]:
    """Begin the RFC 8628 Device Authorization Grant (fallback flow).

    Returns the device-authorization mapping (``device_code``, ``user_code``,
    ``verification_uri``, ...) for ``ui/`` to display.
    """
    form = {"client_id": client_id, "scope": scope}
    response = transport(device_endpoint, form)
    if not isinstance(response, Mapping) or not response.get("device_code"):
        raise AuthError("device authorization response missing device_code")
    return response


def poll_device_token(
    token_endpoint: str,
    *,
    client_id: str,
    device_code: str,
    transport: TokenTransport,
    max_attempts: int = CLOUD_RETRY_LIMIT,
) -> Mapping[str, Any]:
    """Poll the token endpoint for a Device-Grant token (bounded attempts).

    Bounded by ``max_attempts`` (defaults to ``CLOUD_RETRY_LIMIT``): a
    still-``authorization_pending`` response is retried; any other error, or
    exhausting the attempts, raises :class:`AuthError`.
    """
    if not isinstance(device_code, str) or not device_code:
        raise AuthError("device_code must be a non-empty str")
    if max_attempts <= 0:
        raise AuthError("max_attempts must be > 0")
    form = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": client_id,
        "device_code": device_code,
    }
    last_error = "authorization_pending"
    for _ in range(max_attempts):
        response = transport(token_endpoint, form)
        if isinstance(response, Mapping) and response.get("access_token"):
            return _require_token_response(response)
        last_error = (
            str(response.get("error", "authorization_pending"))
            if isinstance(response, Mapping)
            else "invalid_response"
        )
        if last_error != "authorization_pending":
            raise AuthError(f"device token error: {last_error}")
    raise AuthError(f"device token not granted within {max_attempts} attempts")
