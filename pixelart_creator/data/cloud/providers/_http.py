# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Injectable HTTP seam for the real cloud provider adapters (zero Qt, S11).

Phase-10 Slice A tail (ADR-0026 §2/§3; spec REQ-P10-DATA-007/-008; Researcher §1/§6).
The real Drive / OneDrive / Dropbox adapters talk to their REST APIs through **one
small, injectable transport** defined here — never a provider SDK type. Two things
matter:

* **Isolation (Article I / REQ-P10-DATA-007).** The only network type any provider
  adapter sees is :class:`HttpResponse` (plain ``status`` / ``headers`` / ``body``
  bytes) and the :class:`HttpClient` protocol. No ``urllib``/``requests``/SDK type,
  and no provider-specific exception, ever appears in the adapters' own public
  surface — HTTP failures are normalised to :class:`HttpError` (a ``CloudError``).
* **Testability without live credentials (Article IV / CL-B2).** Because the adapters
  depend only on the :class:`HttpClient` *protocol*, AGT-04's contract tests inject a
  **mock / recorded** client and drive the whole ``CloudPort`` contract with **no
  network and no credentials**. The real :class:`UrllibHttpClient` (stdlib ``urllib``,
  no new dependency) is the credential-/network-gated path exercised only under the
  ``cloud_live`` marker, out of the CI gate.

Every response body is **untrusted input** (Article VII): :func:`decode_json` and
:func:`read_body` size-cap the payload against
:data:`~pixelart_creator.logic.constants.MAX_CLOUD_PROJECT_BYTES` *before* decoding and
**never** ``eval``/``exec`` it (``json.loads`` only), so a hostile/oversized provider
response cannot exhaust memory or execute code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable
from urllib.parse import urlencode

from pixelart_creator.data.cloud.port import CloudDataError, CloudError
from pixelart_creator.logic.constants import MAX_CLOUD_PROJECT_BYTES

__all__ = [
    "HttpError",
    "HttpResponse",
    "HttpClient",
    "UrllibHttpClient",
    "decode_json",
    "read_body",
    "with_query",
    "token_transport_from_http",
]


class HttpError(CloudError):
    """Raised on a transport-level HTTP failure (connect / non-2xx / decode).

    Subclasses ``CloudError`` so provider HTTP failures stay inside the
    ``data/cloud/`` error family — no ``urllib``/SDK exception type leaks above the
    port (REQ-P10-DATA-007). :attr:`status` carries the HTTP status when known.
    """

    def __init__(self, message: str, *, status: Optional[int] = None) -> None:
        """Create the error, recording the HTTP ``status`` when one is known."""
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HttpResponse:
    """A normalized HTTP response — the ONLY network type the adapters observe.

    Attributes:
        status: The HTTP status code.
        headers: Response headers (case is provider-dependent; look up defensively).
        body: The raw response body bytes (already size-capped by the client).
    """

    status: int
    body: bytes = b""
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Whether the status is a 2xx success."""
        return 200 <= self.status < 300


@runtime_checkable
class HttpClient(Protocol):
    """The injectable HTTP transport every real provider adapter depends on.

    A single method keeps the seam trivial to mock. Implementations MUST size-cap the
    body they return (see :func:`read_body`) and MUST NOT raise a provider/urllib type
    upward — normalise transport failures to :class:`HttpError`.
    """

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> HttpResponse:
        """Perform one HTTP request and return a normalized :class:`HttpResponse`."""
        ...


def with_query(url: str, params: Optional[Mapping[str, str]]) -> str:
    """Return ``url`` with ``params`` appended as a query string (pure)."""
    if not params:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urlencode(dict(params))}"


def read_body(raw: Any, cap: int = MAX_CLOUD_PROJECT_BYTES) -> bytes:
    """Read a response stream defensively, rejecting anything over ``cap`` bytes.

    Reads at most ``cap + 1`` bytes so an unbounded/hostile body is rejected with
    :class:`CloudDataError` *before* it can exhaust memory (Article VII), rather than
    trusting a ``Content-Length`` header.
    """
    data = raw.read(cap + 1) if hasattr(raw, "read") else bytes(raw)
    if len(data) > cap:
        raise CloudDataError(
            f"HTTP response body exceeds MAX_CLOUD_PROJECT_BYTES ({cap})"
        )
    return bytes(data)


def decode_json(response: HttpResponse) -> Dict[str, Any]:
    """Defensively decode a JSON-object response body (never ``eval``/``exec``).

    The body is already size-capped by the client; here it is UTF-8/JSON decoded and
    required to be a JSON object. Malformed input raises :class:`CloudDataError`
    (Article VII untrusted-input defence).

    Raises:
        CloudDataError: If the body is not valid UTF-8 JSON or is not a JSON object.
    """
    if len(response.body) > MAX_CLOUD_PROJECT_BYTES:
        raise CloudDataError(
            f"HTTP JSON body exceeds MAX_CLOUD_PROJECT_BYTES "
            f"({MAX_CLOUD_PROJECT_BYTES})"
        )
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudDataError(
            f"provider response is not valid UTF-8 JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise CloudDataError("provider JSON response must decode to an object")
    return payload


def token_transport_from_http(http: HttpClient) -> Any:
    """Adapt an :class:`HttpClient` into the auth module's ``TokenTransport``.

    :mod:`pixelart_creator.data.cloud.auth` performs the OAuth token exchange/refresh
    through an injected ``(url, form) -> mapping`` callable so it stays network-free and
    provider-agnostic. This wires that callable onto the real HTTP client: it POSTs the
    form ``application/x-www-form-urlencoded`` and defensively decodes the JSON reply.
    """

    def _transport(url: str, form: Mapping[str, str]) -> Mapping[str, Any]:
        response = http.request(
            "POST",
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=urlencode(dict(form)).encode("utf-8"),
        )
        # The token endpoint returns JSON on both success and RFC 6749 error; decode
        # either (auth._require_token_response inspects the "error" field).
        return decode_json(response)

    return _transport


class UrllibHttpClient:
    """A real, stdlib-``urllib`` :class:`HttpClient` — credential/network-gated.

    The concrete network path exercised ONLY under the ``cloud_live`` marker (out of
    the CI gate, CL-B2). It uses ``urllib.request`` (no third-party HTTP dependency),
    size-caps every body via :func:`read_body`, and normalises any ``urllib`` error to
    :class:`HttpError` so no ``urllib`` type escapes the ``data/cloud/`` boundary.
    """

    def __init__(self, *, timeout_s: float = 30.0) -> None:
        """Create the client with a per-request ``timeout_s`` (seconds)."""
        self._timeout_s = float(timeout_s)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
        params: Optional[Mapping[str, str]] = None,
        body: Optional[bytes] = None,
    ) -> HttpResponse:  # pragma: no cover - network-gated, out of CI (cloud_live)
        """Perform the request over ``urllib``; normalise failures to HttpError."""
        import urllib.error
        import urllib.request

        full_url = with_query(url, params)
        request = urllib.request.Request(full_url, data=body, method=method.upper())
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            # noqa: S310 - https provider endpoints only (loopback http is auth's).
            with urllib.request.urlopen(request, timeout=self._timeout_s) as raw:
                return HttpResponse(
                    status=int(raw.status),
                    body=read_body(raw),
                    headers={k.lower(): v for k, v in raw.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            # A non-2xx still carries a (JSON) body the adapter may want to inspect.
            payload = read_body(exc) if exc.fp is not None else b""
            return HttpResponse(
                status=int(exc.code),
                body=payload,
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
            )
        except urllib.error.URLError as exc:
            raise HttpError(f"HTTP transport error for {full_url}: {exc}") from exc
