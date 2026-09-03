# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure signed share-link token — mint + verify (zero Qt, zero ``data/``, S11).

Phase-13 (ADR-0036 §1 + Addendum A; spec REQ-P13-WEB-002/-005, Article VII).
The web viewer (``web_viewer/``) is a vanilla HTML/CSS/JS client that views a **shared**
project over the shipped ``sync_backend/`` ``websockets`` relay, gated by a per-project
**signed share-link bearer token**. This module is the **single, pure, deterministic**
definition of that token's format + validation, so **both** the minting side (the
desktop share action / an operator tool) and the backend handshake verify against the
identical surface — the ``sync_protocol`` single-sourcing precedent.

The token is a compact, URL-safe, ``HMAC-SHA256``-signed bearer token — a JWT-shaped
``header.payload.sig`` triple, each segment base64url-encoded — built with **stdlib
only** (``hmac`` + ``hashlib`` + ``base64`` + ``json``); **no JWT library, no new
dependency** (spec §10 D1; ADR-0036 §1). It depends only on pure
:mod:`pixelart_creator.logic.constants` (the ``SHARE_TOKEN_MAX_TTL_S`` lifetime cap +
the ``SHARE_TOKEN_MAX_CHARS`` length cap), so it stays a ``logic/`` leaf importable by
the client and the out-of-layer backend without either importing ``data/`` or Qt.

**Untrusted-input defence (Article VII).** A presented token is untrusted:
:func:`verify` length-caps the raw string against ``SHARE_TOKEN_MAX_CHARS`` **before**
any decode, splits the three segments, recomputes the ``HMAC-SHA256`` over the encoded
``header.payload`` and compares it in **constant time** (:func:`hmac.compare_digest`) —
authenticating the token **before** the JSON is parsed — then parses ``json``-only
(never ``eval``/``exec``), pins ``alg == "HS256"`` (an ``alg`` of ``"none"`` or anything
else is rejected — the classic JWT downgrade is refused), and enforces ``exp`` present +
in the future + ``exp - iat <= SHARE_TOKEN_MAX_TTL_S``, ``iss``/``aud`` match, and the
``project_id``/``scope`` claims (with ``sub``, when present, required to equal
``project_id`` — Addendum A.3). Any failure raises :class:`ShareTokenError` yielding
**no claims** (verify-never-leak); the signing secret is never logged and (per ADR-0027
/ Addendum A.2) the token is verified, never stored.

``verify`` takes ``now`` as an explicit parameter (no hidden clock import) so it is
deterministic + testable; the production caller passes ``time.time()``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any, Dict, Mapping, Union

from pixelart_creator.logic.constants import (
    SHARE_TOKEN_MAX_CHARS,
    SHARE_TOKEN_MAX_TTL_S,
)

__all__ = [
    "ShareTokenError",
    "Claims",
    "mint",
    "verify",
]

#: A decoded/validated token's claim mapping (the ``payload`` object).
Claims = Dict[str, Any]

#: A signing secret may be supplied as ``str`` (UTF-8 encoded) or raw ``bytes``.
SecretLike = Union[str, bytes]

#: The fixed, validated JOSE header. ``alg`` is **pinned** (never read from input to
#: select the algorithm — verify always uses HMAC-SHA256 and additionally asserts this
#: value), so the "alg=none"/algorithm-substitution family is structurally refused. The
#: header/type/algorithm string vocabulary is format-intrinsic and module-local
#: (ADR-0001 / BF-2, the ``sync_protocol`` / ``cloud_validation`` enumerated-vocabulary
#: precedent), not a numeric constant.
_ALG = "HS256"
_TYP = "share+jwt"

#: The claim keys :func:`mint` requires present (Addendum A.8). ``sub`` is derived
#: (defaults to ``project_id``) and ``jti`` is optional, so neither is required here.
_REQUIRED_MINT_CLAIMS = ("iss", "aud", "project_id", "scope", "iat", "exp")

#: Defensive cap on a scalar string claim length (id / issuer / audience / scope). An id
#: is short by construction; a hostile mega-string is rejected before use (Article VII).
#: Intrinsic to this validator (mirrors ``cloud_validation._MAX_FIELD_CHARS`` /
#: ``sync_protocol._MAX_DOCUMENT_ID_CHARS``), so module-local.
_MAX_CLAIM_CHARS = 1024


def _as_secret_bytes(secret: SecretLike) -> bytes:
    """Return the signing secret as ``bytes`` (UTF-8 for a ``str``), or raise."""
    if isinstance(secret, str):
        if not secret:
            raise ShareTokenError("signing secret must be non-empty")
        return secret.encode("utf-8")
    if isinstance(secret, (bytes, bytearray)):
        if len(secret) == 0:
            raise ShareTokenError("signing secret must be non-empty")
        return bytes(secret)
    raise ShareTokenError(
        f"signing secret must be str or bytes, got {type(secret).__name__}"
    )


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode ``data`` with padding stripped (JOSE convention)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    """Base64url-decode a padding-stripped ``segment`` (strict), or raise.

    Raises:
        ShareTokenError: If the segment is not valid base64url.
    """
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (ValueError, binascii.Error) as exc:
        raise ShareTokenError("token segment is not valid base64url") from exc


def _canonical_json_bytes(obj: Mapping[str, Any]) -> bytes:
    """Serialise a mapping to canonical, deterministic JSON bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(secret: bytes, signing_input: str) -> bytes:
    """Return the raw ``HMAC-SHA256`` of ``signing_input`` under ``secret``."""
    return hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()


class ShareTokenError(ValueError):
    """Raised when a share-link token cannot be minted or fails verification.

    A subclass of ``ValueError`` (the ``CloudValidationError``/``ProjectIOError``
    Phase-1 convention). It is raised with a **generic** message that never echoes the
    token, the secret, or the expected signature — verification failure must not leak an
    oracle (Article VII; ADR-0036 §1: "any failure raises ``ShareTokenError`` and yields
    no claims"). The backend handshake catches it and rejects the connection (HTTP
    401/403) without serving any project data.
    """


def mint(claims: Mapping[str, Any], secret: SecretLike) -> str:
    """Mint a signed share-link token from ``claims`` under ``secret``.

    Builds the fixed ``{"alg": "HS256", "typ": "share+jwt"}`` header, canonicalises the
    payload, and appends the base64url ``HMAC-SHA256`` signature over
    ``base64url(header) + "." + base64url(payload)``. Per Addendum A.3 the canonical
    project-identity claim is ``project_id``; ``sub`` is set equal to it when the caller
    does not supply one (advisory/JWT-interop) — :func:`verify` rejects any token whose
    ``sub`` diverges from ``project_id``.

    Minting requires the essential claims to be present + well-typed but deliberately
    does **not** enforce the lifetime/expiry/issuer policy (that is :func:`verify`'s
    authoritative gate on the untrusted boundary), so a caller — or a test — can
    construct an over-long-TTL or otherwise-invalid token and prove ``verify`` rejects
    it.

    Args:
        claims: The payload claims. Must contain ``iss``, ``aud``, ``project_id``,
            ``scope`` (non-empty, length-bounded strings) and ``iat``, ``exp`` (integer
            seconds). ``sub`` defaults to ``project_id``; ``jti`` (a unique id) is
            optional. Extra claims are preserved verbatim.
        secret: The operator-provided signing secret (``str`` or ``bytes``; never
            committed to the repo — ADR-0036 §1 secret management).

    Returns:
        The compact ``header.payload.sig`` token string.

    Raises:
        ShareTokenError: If a required claim is missing/ill-typed, a ``sub`` is supplied
            that differs from ``project_id``, or the encoded token exceeds
            ``SHARE_TOKEN_MAX_CHARS``.
    """
    secret_bytes = _as_secret_bytes(secret)
    if not isinstance(claims, Mapping):
        raise ShareTokenError(f"claims must be a mapping, got {type(claims).__name__}")

    payload: Claims = dict(claims)
    for key in _REQUIRED_MINT_CLAIMS:
        if key not in payload:
            raise ShareTokenError(f"claims missing required field {key!r}")
    for key in ("iss", "aud", "project_id", "scope"):
        _require_claim_str(payload, key)
    for key in ("iat", "exp"):
        _require_claim_int(payload, key)

    project_id = payload["project_id"]
    if "sub" in payload:
        if payload["sub"] != project_id:
            raise ShareTokenError("sub must equal project_id")
    else:
        payload["sub"] = project_id

    header = {"alg": _ALG, "typ": _TYP}
    header_b64 = _b64url_encode(_canonical_json_bytes(header))
    payload_b64 = _b64url_encode(_canonical_json_bytes(payload))
    signing_input = f"{header_b64}.{payload_b64}"
    sig_b64 = _b64url_encode(_sign(secret_bytes, signing_input))
    token = f"{signing_input}.{sig_b64}"

    if len(token) > SHARE_TOKEN_MAX_CHARS:
        raise ShareTokenError(
            f"minted token length {len(token)} exceeds SHARE_TOKEN_MAX_CHARS "
            f"({SHARE_TOKEN_MAX_CHARS})"
        )
    return token


def verify(
    token: object,
    secret: SecretLike,
    *,
    expected_iss: str,
    expected_aud: str,
    now: float,
) -> Claims:
    """Verify an untrusted share-link ``token`` and return its validated claims.

    The full untrusted-input gate, in order (Article VII; ADR-0036 §1 + Addendum A):

    1. Type-check + **length-cap** the raw string against ``SHARE_TOKEN_MAX_CHARS``
       *before* any decode; split into exactly three ``header.payload.sig`` segments.
    2. Recompute ``HMAC-SHA256`` over ``header.payload`` and compare it to the presented
       signature in **constant time** (:func:`hmac.compare_digest`) — the token is
       authenticated **before** its JSON is parsed.
    3. Only then ``json``-parse the header + payload (never ``eval``/``exec``); pin
       ``alg == "HS256"`` (an absent/``"none"``/other ``alg`` is rejected — no
       downgrade) and ``typ == "share+jwt"``.
    4. Enforce claims: ``iss == expected_iss``, ``aud == expected_aud``; ``project_id``
       and ``scope`` present (non-empty, bounded strings); ``sub`` — when present —
       equal to ``project_id`` (Addendum A.3); ``iat``/``exp`` integer seconds with a
       positive lifetime, ``exp - iat <= SHARE_TOKEN_MAX_TTL_S``, and ``now < exp``.

    Args:
        token: The untrusted token string as presented on the handshake.
        secret: The operator-provided signing secret (``str`` or ``bytes``).
        expected_iss: The issuer this deployment accepts.
        expected_aud: The audience this deployment accepts.
        now: The current time, seconds since the epoch (the caller passes
            ``time.time()``); taken as a parameter so verification is deterministic.

    Returns:
        The validated claims mapping (a fresh ``dict`` including ``project_id`` and
        ``scope``).

    Raises:
        ShareTokenError: On any type/length/format/signature/``alg``/claim/expiry
            violation. The message never echoes the token, the secret, or the computed
            signature (no verification oracle).
    """
    secret_bytes = _as_secret_bytes(secret)

    if not isinstance(token, str):
        raise ShareTokenError(f"token must be a str, got {type(token).__name__}")
    if not token:
        raise ShareTokenError("token is empty")
    if len(token) > SHARE_TOKEN_MAX_CHARS:
        raise ShareTokenError(
            f"token length {len(token)} exceeds SHARE_TOKEN_MAX_CHARS "
            f"({SHARE_TOKEN_MAX_CHARS})"
        )

    segments = token.split(".")
    if len(segments) != 3:
        raise ShareTokenError("token must have three segments")
    header_b64, payload_b64, sig_b64 = segments

    # --- Authenticate BEFORE parsing: constant-time HMAC compare over the raw segments.
    presented_sig = _b64url_decode(sig_b64)
    expected_sig = _sign(secret_bytes, f"{header_b64}.{payload_b64}")
    if not hmac.compare_digest(presented_sig, expected_sig):
        raise ShareTokenError("token signature is invalid")

    # --- Now the segments are authenticated: json-only parse (never eval/exec).
    header = _decode_json_object(header_b64, "header")
    if header.get("alg") != _ALG:
        # Never trust an input-chosen algorithm ("none"/anything but HS256).
        raise ShareTokenError("token alg is not HS256")
    if header.get("typ") != _TYP:
        raise ShareTokenError("token typ is not share+jwt")

    claims = _decode_json_object(payload_b64, "payload")

    if claims.get("iss") != expected_iss:
        raise ShareTokenError("token iss does not match")
    if claims.get("aud") != expected_aud:
        raise ShareTokenError("token aud does not match")

    project_id = _require_claim_str(claims, "project_id")
    _require_claim_str(claims, "scope")
    if "sub" in claims and claims["sub"] != project_id:
        raise ShareTokenError("token sub does not match project_id")

    iat = _require_claim_int(claims, "iat")
    exp = _require_claim_int(claims, "exp")
    if exp <= iat:
        raise ShareTokenError("token exp must be after iat")
    if exp - iat > SHARE_TOKEN_MAX_TTL_S:
        raise ShareTokenError("token lifetime exceeds SHARE_TOKEN_MAX_TTL_S")
    if not now < exp:
        raise ShareTokenError("token is expired")

    return claims


def _decode_json_object(segment: str, what: str) -> Claims:
    """Base64url-decode + ``json``-parse a segment into a JSON object, or raise.

    Raises:
        ShareTokenError: If the segment is not base64url, not valid UTF-8 JSON, or does
            not decode to a JSON object.
    """
    raw = _b64url_decode(segment)
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ShareTokenError(f"token {what} is not valid UTF-8 JSON") from exc
    if not isinstance(obj, dict):
        raise ShareTokenError(f"token {what} must be a JSON object")
    return obj


def _require_claim_str(claims: Mapping[str, Any], key: str) -> str:
    """Return a required non-empty, length-bounded string claim, or raise."""
    value = claims.get(key)
    if not isinstance(value, str) or not value:
        raise ShareTokenError(f"claim {key!r} must be a non-empty str")
    if len(value) > _MAX_CLAIM_CHARS:
        raise ShareTokenError(f"claim {key!r} length exceeds {_MAX_CLAIM_CHARS}")
    return value


def _require_claim_int(claims: Mapping[str, Any], key: str) -> int:
    """Return a required integer-seconds claim, or raise.

    Rejects ``bool`` (an ``int`` subclass in Python) and non-integers so a truthy
    ``exp``/``iat`` cannot slip past a naive ``isinstance(_, int)`` check.
    """
    value = claims.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ShareTokenError(f"claim {key!r} must be an integer")
    return value
