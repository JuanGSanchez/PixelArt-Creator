# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared OAuth session + base provider adapter (zero Qt, S11).

Phase-10 Slice A tail (ADR-0026 §1/§2/§3; spec REQ-P10-DATA-001/-007/-008; Researcher
§1/§2). The three real provider adapters (Drive / OneDrive / Dropbox) share:

* :class:`OAuthConfig` — a provider's client id + authorization/token/device endpoints
  + scope, all values (no secrets are hard-coded here — the client id is passed in by
  the caller, and no client *secret* is used: desktop PKCE is a public-client flow,
  RFC 8252).
* :class:`ProviderAuth` — the **real OAuth Authorization-Code + PKCE over loopback**
  wiring (reusing the shipped, tested :mod:`pixelart_creator.data.cloud.auth` PKCE core
  and :class:`~pixelart_creator.data.cloud.auth.LoopbackRedirectServer`) plus **real
  OS-keyring** token storage (reusing :mod:`pixelart_creator.data.cloud.token_store` —
  this is the REAL keyring path, where ``keyring`` becomes a hard dependency). The
  refresh token is persisted in the keyring keyed ``pixelart-creator:cloud:{provider}``;
  the short-lived access token is refreshed on demand and kept in memory only. Tokens
  **never** leave ``data/cloud/`` (Article VII §3, REQ-P10-DATA-008).
* :class:`BaseProviderAdapter` — a partial :class:`~pixelart_creator.data.cloud.port.
  CloudPort` that owns the authenticated-request plumbing (Bearer header, one automatic
  refresh-and-retry on ``401``, defensive JSON/bytes decode) over the injectable
  :class:`~pixelart_creator.data.cloud.providers._http.HttpClient` seam. Each concrete
  provider implements only the verb → REST mapping and its capability model.

Nothing here (or in the subclasses) exposes a provider SDK type, a ``urllib`` type, a
token, or a provider-specific exception above the ``data/cloud/`` boundary
(REQ-P10-DATA-007). The whole surface is driveable by a mock :class:`HttpClient`, so
AGT-04 can assert ``CloudPort``-contract conformance with no network/credentials.
"""

from __future__ import annotations

import secrets
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from pixelart_creator.data.cloud import auth as _auth
from pixelart_creator.data.cloud import token_store as _token_store
from pixelart_creator.data.cloud.port import CloudDataError, CloudPort
from pixelart_creator.data.cloud.providers._http import (
    HttpClient,
    HttpError,
    HttpResponse,
    UrllibHttpClient,
    decode_json,
    token_transport_from_http,
)
from pixelart_creator.logic.constants import MAX_CLOUD_PROJECT_BYTES
from pixelart_creator.logic.version_history import CloudVersion

__all__ = ["OAuthConfig", "ProviderAuth", "BaseProviderAdapter", "build_versions"]


def _coerce_size(value: Any) -> int:
    """Coerce an untrusted provider size field to a bounded, non-negative int.

    Provider ``size`` fields are untrusted (Article VII): a non-int, negative, or
    over-cap value is a malformed response.

    Raises:
        CloudDataError: If ``value`` is not a non-negative int within
            ``MAX_CLOUD_PROJECT_BYTES``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise CloudDataError(f"provider size field must be an int, got {value!r}")
    if value < 0 or value > MAX_CLOUD_PROJECT_BYTES:
        raise CloudDataError(
            f"provider size field {value} outside 0..MAX_CLOUD_PROJECT_BYTES"
        )
    return value


def build_versions(
    entries: "list[tuple[str, int]]",
) -> "tuple[CloudVersion, ...]":
    """Build a normalized, ordered version tuple from ``(revision_id, size)`` pairs.

    ``entries`` MUST be in **ascending** (oldest-first) order; each pair's provider
    revision id becomes both the port ``version_id`` and the ``remote_revision_id``
    (the local↔remote reconciliation map, BF-2), and its position becomes the 0-based
    monotonic ``ordinal`` / ``created_marker`` (deterministic — never a wall-clock
    read). Sizes are validated + bounded.

    Raises:
        CloudDataError: If a revision id is not a non-empty str or a size is invalid.
    """
    versions = []
    for ordinal, (revision_id, size) in enumerate(entries):
        if not isinstance(revision_id, str) or not revision_id:
            raise CloudDataError(
                f"provider revision id must be a non-empty str, got {revision_id!r}"
            )
        versions.append(
            CloudVersion(
                version_id=revision_id,
                ordinal=ordinal,
                created_marker=ordinal,
                size_bytes=_coerce_size(size),
                remote_revision_id=revision_id,
            )
        )
    return tuple(versions)


#: A ``ui/``-supplied callback that opens ``url`` in the SYSTEM browser (RFC 8252 — no
#: embedded webview). Only this human-facing step touches ``ui/``; the crypto/network
#: stay in ``data/`` (Researcher §2.4).
BrowserOpener = Callable[[str], None]


@dataclass(frozen=True)
class OAuthConfig:
    """A provider's OAuth endpoints + public-client id + scope (no secret).

    Attributes:
        client_id: The registered public (native-app) client id. Not a secret under
            RFC 8252 PKCE; supplied by the caller, never committed.
        authorization_endpoint: The provider authorize URL (browser is pointed here).
        token_endpoint: The provider token URL (code exchange + refresh).
        scope: The space-delimited OAuth scope string.
        device_endpoint: The RFC 8628 device-authorization URL, when supported.
    """

    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    scope: str
    device_endpoint: Optional[str] = None


class ProviderAuth:
    """Real OAuth (PKCE-over-loopback) + OS-keyring token isolation for one provider.

    Reuses the shipped PKCE core / loopback server (``cloud.auth``) and the keyring
    token store (``cloud.token_store``); this module does not re-implement either.
    """

    def __init__(
        self,
        provider: str,
        account: str,
        config: OAuthConfig,
        *,
        http: Optional[HttpClient] = None,
        token_transport: Optional[_auth.TokenTransport] = None,
    ) -> None:
        """Bind auth to ``(provider, account)``.

        Args:
            provider: Provider key for the keyring service name (e.g. ``"drive"``).
            account: The provider account identifier (keyring username).
            config: The provider's :class:`OAuthConfig`.
            http: The injectable HTTP client used to build the default token
                transport. Defaults to the real :class:`UrllibHttpClient` (out of CI).
            token_transport: An explicit ``(url, form) -> mapping`` transport (tests
                inject this to stay network-free). Overrides ``http`` when given.
        """
        self._provider = provider
        self._account = account
        self._config = config
        self._http: HttpClient = http if http is not None else UrllibHttpClient()
        self._token_transport: _auth.TokenTransport = (
            token_transport
            if token_transport is not None
            else token_transport_from_http(self._http)
        )
        self._access_token: Optional[str] = None

    def connect(self, open_browser: BrowserOpener) -> None:
        """Run the real Authorization-Code + PKCE loopback flow and store the token.

        Generates a PKCE ``S256`` pair, binds an ephemeral ``127.0.0.1`` redirect
        listener, asks ``ui/`` to open the authorize URL in the system browser, waits
        for the redirect, exchanges the code, and persists the refresh token in the OS
        keyring. The access token is kept in memory only.

        Raises:
            AuthError: On a PKCE/state/exchange failure (from ``cloud.auth``).
        """
        pkce = _auth.create_pkce_pair()
        state = secrets.token_urlsafe(24)
        with _auth.LoopbackRedirectServer() as server:
            redirect_uri = server.redirect_uri
            url = _auth.build_authorization_url(
                self._config.authorization_endpoint,
                client_id=self._config.client_id,
                redirect_uri=redirect_uri,
                pkce=pkce,
                scope=self._config.scope,
                state=state,
            )
            open_browser(url)
            code, _state = server.wait_for_code(expected_state=state)
        tokens = _auth.exchange_code(
            self._config.token_endpoint,
            client_id=self._config.client_id,
            code=code,
            redirect_uri=redirect_uri,
            verifier=pkce.verifier,
            transport=self._token_transport,
        )
        self._store_tokens(tokens)

    def _store_tokens(self, tokens: Mapping[str, Any]) -> None:
        """Persist the refresh token to the keyring; cache the access token."""
        access = tokens.get("access_token")
        if isinstance(access, str) and access:
            self._access_token = access
        refresh = tokens.get("refresh_token")
        if isinstance(refresh, str) and refresh:
            _token_store.store_token(self._provider, self._account, refresh)

    def access_token(self) -> str:
        """Return a valid access token, refreshing from the keyring token if needed.

        Raises:
            AuthError: If no token is cached and no stored refresh token exists
                (the provider is not connected), or the refresh fails.
        """
        if self._access_token is not None:
            return self._access_token
        refresh = _token_store.load_token(self._provider, self._account)
        if not refresh:
            raise _auth.AuthError(
                f"provider {self._provider!r} is not connected (no stored token)"
            )
        tokens = _auth.refresh_token(
            self._config.token_endpoint,
            client_id=self._config.client_id,
            refresh_token_value=refresh,
            transport=self._token_transport,
        )
        self._store_tokens(tokens)
        assert self._access_token is not None
        return self._access_token

    def force_refresh(self) -> str:
        """Drop the cached access token and refresh a new one (used on a 401)."""
        self._access_token = None
        return self.access_token()

    def is_connected(self) -> bool:
        """Whether a token is cached or a refresh token is stored (no token exposed)."""
        if self._access_token is not None:
            return True
        try:
            return _token_store.load_token(self._provider, self._account) is not None
        except _token_store.TokenStoreError:
            return False

    def disconnect(self) -> None:
        """Forget the cached access token and delete the stored refresh token."""
        self._access_token = None
        _token_store.delete_token(self._provider, self._account)


class BaseProviderAdapter(CloudPort):
    """Authenticated-request plumbing shared by the real provider adapters.

    Owns the Bearer-header injection, a single automatic refresh-and-retry on ``401``,
    and defensive JSON/bytes decode over the injectable HTTP seam. Concrete providers
    implement the ``CloudPort`` verbs (the REST mapping) and :meth:`capabilities`.
    """

    def __init__(
        self, auth: ProviderAuth, *, http: Optional[HttpClient] = None
    ) -> None:
        """Bind the adapter to a :class:`ProviderAuth` and an HTTP client.

        Args:
            auth: The provider's authenticated session.
            http: The injectable HTTP client. Defaults to the real
                :class:`UrllibHttpClient` (credential/network-gated, out of CI).
        """
        self._auth = auth
        self._http: HttpClient = http if http is not None else UrllibHttpClient()

    def is_connected(self) -> bool:
        """Return the provider-agnostic connected flag (no token exposed to ``ui/``)."""
        return self._auth.is_connected()

    # -- authenticated transport ------------------------------------------- #

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> HttpResponse:
        """Perform an authenticated request; refresh-and-retry once on ``401``.

        Raises:
            HttpError: On a non-2xx response (other than the retried ``401``) or a
                transport failure (normalised — no ``urllib``/SDK type escapes).
        """
        response = self._http.request(
            method,
            url,
            headers=self._with_auth(headers, self._auth.access_token()),
            params=params,
            body=body,
        )
        if response.status == 401:
            # Access token likely expired — refresh once and retry (RFC 6749).
            response = self._http.request(
                method,
                url,
                headers=self._with_auth(headers, self._auth.force_refresh()),
                params=params,
                body=body,
            )
        if not response.ok:
            raise HttpError(
                f"{method} {url} failed with HTTP {response.status}",
                status=response.status,
            )
        return response

    @staticmethod
    def _with_auth(headers: Optional[Mapping[str, str]], token: str) -> Dict[str, str]:
        """Return ``headers`` with a Bearer ``Authorization`` header added."""
        merged: Dict[str, str] = dict(headers or {})
        merged["Authorization"] = f"Bearer {token}"
        return merged

    def _get_json(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, str]] = None,
    ) -> Dict[str, Any]:
        """GET ``url`` and defensively decode a JSON object (untrusted input)."""
        return decode_json(self._request("GET", url, params=params))

    def _post_json(
        self,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """POST to ``url`` and defensively decode a JSON object (untrusted input)."""
        return decode_json(self._request("POST", url, headers=headers, body=body))

    @staticmethod
    def _require_field(payload: Mapping[str, Any], key: str) -> Any:
        """Return ``payload[key]`` or raise :class:`CloudDataError` if missing.

        Provider responses are untrusted (Article VII): a missing expected field is a
        malformed response, not an attribute error.
        """
        if key not in payload:
            raise CloudDataError(f"provider response missing expected field {key!r}")
        return payload[key]

    # -- concrete providers implement the CloudPort verbs + capabilities --- #

    @abstractmethod
    def capabilities(self) -> Any:  # -> CloudCapabilities
        """Return this provider's normalized :class:`CloudCapabilities`."""
