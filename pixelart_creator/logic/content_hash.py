# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Deterministic content-hash primitive — pure, zero Qt (S11).

The content-hash primitive Phase 11 **introduces** (ADR-0030 §3; the shipped tree has
no such primitive — ``logic/version_history.py`` keys by an opaque ``version_id``, and
``hashlib`` appears only in ``data/export_io.py`` / ``data/cloud/auth.py``). A content
hash is the single deterministic function that serves as **both** the CAS key
(``data/asset_cas.py``) and the "did this asset change?" change-detector that drives
revision creation and break re-validation.

:func:`content_hash` computes a **SHA-256 hex digest over canonicalized asset bytes**
with stdlib :mod:`hashlib` — **no new runtime dependency** (PL11-D5). Equal
canonicalized
bytes ⇒ equal hash ⇒ "unchanged"; :func:`same_content` is the detector built on it.

**Canonicalization is defined byte-exactly** by :func:`canonical_json_bytes`: a
JSON-serialisable object is encoded with ``sort_keys=True``, compact ``(",", ":")``
separators, and ``ensure_ascii=False`` (UTF-8), so the same logical asset always yields
byte-identical bytes — stable across sessions and platforms (ADR-0030 §3). Callers that
already hold canonical bytes (e.g. a PIO-1 ``.pixproj`` payload built through
:func:`canonical_json_bytes`) pass them straight to :func:`content_hash`.

Pure and deterministic: no wall-clock, no randomness, no locale. This module is a leaf —
it imports only the standard library — so ``check_layering`` / ``check_cycles`` stay
exit 0.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

__all__ = [
    "ContentHashError",
    "content_hash",
    "same_content",
    "canonical_json_bytes",
    "is_valid_hash",
]

#: The hashing algorithm name — a module-local, algorithm-intrinsic string (ADR-0001
#: exemption, like the Bayer-matrix values / GID flag masks; NOT a numeric tuning value
#: for :mod:`~pixelart_creator.logic.constants`).
_HASH_ALGORITHM = "sha256"

#: SHA-256 hex-digest length, 64 chars (algorithm-intrinsic — ADR-0001). Used by
#: :func:`is_valid_hash` to validate an untrusted hash string defensively.
_HASH_HEX_LEN = 64

#: The lowercase hex alphabet a valid digest is drawn from (algorithm-intrinsic).
_HEX_ALPHABET = frozenset("0123456789abcdef")


class ContentHashError(ValueError):
    """Raised when a value offered for hashing is not raw bytes (type defence)."""


def content_hash(blob: bytes) -> str:
    """Return the deterministic SHA-256 hex digest of ``blob`` (REQ-P11-DATA-004).

    Args:
        blob: The canonicalized asset bytes to address/verify. Must be ``bytes`` or
            ``bytearray`` (a ``str`` is rejected — hashing is over bytes, so the caller
            chooses the encoding via :func:`canonical_json_bytes`).

    Returns:
        A 64-character lowercase hex SHA-256 digest, stable across sessions/platforms.

    Raises:
        ContentHashError: If ``blob`` is not ``bytes``/``bytearray``.
    """
    if not isinstance(blob, (bytes, bytearray)):
        raise ContentHashError(f"content_hash expects bytes, got {type(blob).__name__}")
    return hashlib.new(_HASH_ALGORITHM, bytes(blob)).hexdigest()


def same_content(a: bytes, b: bytes) -> bool:
    """Return whether ``a`` and ``b`` hash equal — the "unchanged" detector.

    ``same_content(a, b)`` is ``content_hash(a) == content_hash(b)``
    (REQ-P11-LOGIC-006): identical canonicalized bytes are "unchanged" (⇒ no new
    revision, no dependent re-validation); any difference is "changed".

    Raises:
        ContentHashError: If either argument is not ``bytes``/``bytearray``.
    """
    return content_hash(a) == content_hash(b)


def canonical_json_bytes(obj: Any) -> bytes:
    """Encode ``obj`` to canonical, byte-exact JSON bytes (the canonicalization scheme).

    The single definition of "canonicalized asset bytes" (ADR-0030 §3): keys are sorted,
    separators are compact (``","`` / ``":"``), non-ASCII is preserved (UTF-8). Two
    logically-equal objects therefore produce byte-identical output regardless of key
    insertion order — so :func:`content_hash` is a stable identity.

    Args:
        obj: Any JSON-serialisable object (dict/list/str/int/float/bool/None).

    Returns:
        The UTF-8-encoded canonical JSON bytes.

    Raises:
        ContentHashError: If ``obj`` is not JSON-serialisable.
    """
    try:
        text = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError) as exc:
        raise ContentHashError(f"object is not JSON-serialisable: {exc}") from exc
    return text.encode("utf-8")


def is_valid_hash(value: Any) -> bool:
    """Return whether ``value`` is a well-formed content-hash string.

    A defensive predicate for untrusted input (a sidecar / imported reference field): a
    valid hash is a lowercase 64-char hex string. Used by the ``data/`` loaders before a
    hash is trusted as a CAS key or a store filename (Article VII).
    """
    return (
        isinstance(value, str)
        and len(value) == _HASH_HEX_LEN
        and all(ch in _HEX_ALPHABET for ch in value)
    )
