# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared stdlib-``urllib`` JSON POST + bounded retry for the real adapters (private).

Phase-14 Slice 14D (skill ``llm-adapter-normalization`` step 5; Researcher ``ad2616c7``
R4.1/R4.3). The single transport seam both real :class:`~pixelart_creator.data.llm.port.
LLMPort` adapters (the OpenAI-compatible core + the native-Anthropic translator) POST
through, so the ``urllib`` handling (which gives no pooling/retry/timeout niceties) is
written **once**: endpoint scheme/host validation (TLS-only off loopback), a bounded
hand-rolled retry within :data:`~pixelart_creator.logic.constants.ASSISTANT_REQUEST_
TIMEOUT_S`, and normalization of **every** transport/HTTP/parse failure into the port's
:class:`~pixelart_creator.data.llm.port.LLMResponseError` — so a raw
``urllib``/``json`` type never leaks above the port (REQ-P14-DATA-007).

**Stdlib only.** ``urllib.request``/``urllib.error``/``urllib.parse``, ``json``, ``ssl``
— no new dependency (REQ-P14-DATA-004). **No provider key is ever logged** — auth
headers are passed opaquely to ``urllib`` and never rendered into an error message.
Module-private (leading underscore): not part of the ``data/llm`` public surface.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Mapping
from urllib.parse import urlparse

from pixelart_creator.data.llm.port import LLMResponseError

__all__ = ["validate_endpoint", "post_json"]

#: Hosts for which a plaintext ``http://`` endpoint is tolerated — the local model
#: runtimes the OpenAI-compatible core must cover (Ollama, llama.cpp): traffic never
#: leaves the machine, so TLS is not required. Any non-loopback host MUST be
#: ``https://`` (Researcher ``ad2616c7`` R4.3 TLS-only posture). Module-local vocab.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def validate_endpoint(url: str) -> str:
    """Validate a user-supplied endpoint URL (untrusted, R4.3); return it unchanged.

    A user-configured endpoint is untrusted input. Only ``https`` is accepted for a
    remote host; plaintext ``http`` is tolerated **only** for a loopback host (local
    Ollama / llama.cpp). Anything else is rejected as an
    :class:`~pixelart_creator.data.llm.port.LLMResponseError` before any network I/O.

    Raises:
        LLMResponseError: If the scheme is not http/https, or a non-loopback host is
            addressed over plaintext http.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise LLMResponseError(
            f"provider endpoint must be http(s), got scheme {parsed.scheme!r}"
        )
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in _LOOPBACK_HOSTS:
        raise LLMResponseError(
            "plaintext http endpoint is permitted only for a loopback host "
            "(local model runtime); use https for a remote provider"
        )
    if not host:
        raise LLMResponseError("provider endpoint has no host")
    return url


def _safe_decode(raw: bytes) -> Dict[str, Any]:
    """Decode+parse a response body to a JSON object, else ``LLMResponseError``."""
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise LLMResponseError("provider response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("provider response was not a JSON object")
    return parsed


def post_json(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    *,
    timeout: float,
    retries: int,
) -> Dict[str, Any]:
    """POST ``payload`` as JSON to ``url``; return the parsed JSON-object response.

    Hand-rolls the retry/timeout ``urllib`` does not provide (R4.1): the request is
    attempted up to ``retries + 1`` times, each bounded by ``timeout`` seconds, retrying
    a timeout / transient transport error / retryable 5xx and re-raising a normalized
    :class:`~pixelart_creator.data.llm.port.LLMResponseError` on a 4xx or on exhaustion.
    A raw ``urllib.HTTPError``/``URLError``/``json`` error never escapes (the untrusted-
    response boundary, REQ-P14-DATA-007). ``headers`` (incl. the auth header) is passed
    opaquely to ``urllib`` and never logged.

    Args:
        url: The validated provider endpoint (see :func:`validate_endpoint`).
        headers: Request headers (auth + any provider version header).
        payload: The request body, JSON-serialised here.
        timeout: Per-attempt socket timeout, seconds
            (:data:`~pixelart_creator.logic.constants.ASSISTANT_REQUEST_TIMEOUT_S`).
        retries: Bounded retry count after the first attempt
            (:data:`~pixelart_creator.logic.constants.ASSISTANT_REQUEST_MAX_RETRIES`).

    Returns:
        The parsed JSON-object response body.

    Raises:
        LLMResponseError: On endpoint rejection, a non-2xx / non-retryable status,
            transport failure after exhausting retries, or an unparseable body.
    """
    validate_endpoint(url)
    data = json.dumps(dict(payload)).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        request.add_header(key, value)
    request.add_header("Content-Type", "application/json")
    context = ssl.create_default_context()

    attempts = max(1, retries + 1)
    raw: bytes | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(  # noqa: S310 - scheme validated above
                request, timeout=timeout, context=context
            ) as response:
                raw = response.read()
            break
        except urllib.error.HTTPError as exc:
            # 4xx is a caller/config error (never retry); 5xx is transient (retry).
            if 500 <= exc.code < 600 and attempt < attempts - 1:
                continue
            raise LLMResponseError(f"provider returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < attempts - 1:
                continue
            raise LLMResponseError(
                f"provider request failed after {attempts} attempt(s)"
            ) from exc

    assert raw is not None  # a break happened; every non-break path raised
    return _safe_decode(raw)
