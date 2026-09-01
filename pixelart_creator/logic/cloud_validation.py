# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure untrusted-input validators for collaboration payloads (zero Qt, S11).

Phase-10 Slice B/C (ADR-0028 §1; spec REQ-P10-DATA-009/-010, REQ-P10-BACKEND-002,
Article VII — CENTRAL). Collaboration payloads that cross a trust boundary — CRDT
update blobs, comment payloads, membership payloads, and presence/awareness messages
— are **untrusted input**. This module is the single, pure, deterministic defence:
every validator schema-checks its input against **strict caps** defined once in
:mod:`pixelart_creator.logic.constants` (``MAX_CRDT_UPDATE_BYTES``,
``MAX_COMMENT_BYTES``, ``MAX_SHARED_MEMBERS``, ``MAX_COMMENTS_PER_PROJECT``),
rejects oversized/malformed input with :class:`CloudValidationError`, and **never**
``eval``/``exec``'s anything.

Being pure ``logic/`` (zero Qt, depends only on ``constants``), it is importable by
**both** the client ``data/cloud/`` transport/shared adapter **and** the out-of-layer
``sync_backend/`` relay (ADR-0027 §4) — the backend reuses these caps + message schema
without importing ``data/``. The size-cap-before-decode discipline mirrors the Slice-A
``data/cloud/port.deserialize_project`` defence (REQ-P10-DATA-006).

The :class:`CrdtMessageKind` vocabulary is module-local enumerated vocabulary
(ADR-0001 / BF-2, the ``BlendMode``/``PlaybackMode`` precedent), not a constant.
"""

from __future__ import annotations

import enum
from typing import Any, Mapping

from pixelart_creator.logic.constants import (
    MAX_COMMENT_BYTES,
    MAX_CRDT_UPDATE_BYTES,
    MAX_SHARED_MEMBERS,
)

__all__ = [
    "CloudValidationError",
    "CrdtMessageKind",
    "MEMBER_ROLES",
    "validate_crdt_update",
    "validate_comment",
    "validate_membership",
    "validate_presence",
]


class CloudValidationError(ValueError):
    """Raised when an untrusted collaboration payload is malformed or oversized.

    A subclass of ``ValueError`` (the Phase-1 convention); a caller in
    ``data/cloud/`` or ``sync_backend/`` catches it and surfaces / rejects the
    payload without crashing (Article VII: no crash, no silent corruption, no
    memory exhaustion, never ``eval``/``exec``).
    """


class CrdtMessageKind(enum.Enum):
    """The wire-message vocabulary the transport / backend relay carry (ADR-0028 §2).

    Module-local enumerated vocabulary (ADR-0001 / BF-2), shared by the client
    transport and the backend so both agree on the message taxonomy without a
    numeric constant. ``PRESENCE`` messages are ephemeral (never persisted).
    """

    #: A structured-metadata CRDT update (pycrdt-encoded tree/sequence update).
    STRUCTURED_UPDATE = "structured_update"
    #: A raster tile/region last-writer-wins update.
    RASTER_UPDATE = "raster_update"
    #: An ephemeral awareness/presence message (cursor/selection).
    PRESENCE = "presence"


#: The bounded, provider-agnostic member-role vocabulary a membership payload may
#: carry. Kept module-local (enumerated vocabulary, ADR-0001).
MEMBER_ROLES = frozenset({"owner", "editor", "viewer"})

#: Defensive cap on the number of keys any single validated payload mapping may
#: carry — guards against a hostile payload with a pathological key count
#: (Article VII). Intrinsic to the validator (not a tuning value), so module-local.
_MAX_PAYLOAD_KEYS = 64

#: Defensive cap on the length of a scalar string field (id / name / role / kind)
#: — an id is short by construction; a hostile mega-string is rejected before use.
_MAX_FIELD_CHARS = 1024


def _require_mapping(payload: Any, what: str) -> Mapping[str, Any]:
    """Return ``payload`` as a mapping, or raise if it is not a bounded mapping.

    Rejects non-mappings and mappings with a pathological key count or non-string
    keys (Article VII) — the first line of every payload validator.
    """
    if not isinstance(payload, Mapping):
        raise CloudValidationError(
            f"{what} must be a mapping, got {type(payload).__name__}"
        )
    if len(payload) > _MAX_PAYLOAD_KEYS:
        raise CloudValidationError(
            f"{what} has {len(payload)} keys, exceeds {_MAX_PAYLOAD_KEYS}"
        )
    for key in payload:
        if not isinstance(key, str):
            raise CloudValidationError(
                f"{what} keys must be str, got {type(key).__name__}"
            )
    return payload


def _require_field_str(payload: Mapping[str, Any], key: str, what: str) -> str:
    """Return a required non-empty, length-bounded string field, or raise."""
    if key not in payload:
        raise CloudValidationError(f"{what} is missing required field {key!r}")
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise CloudValidationError(
            f"{what} field {key!r} must be a non-empty str, got {value!r}"
        )
    if len(value) > _MAX_FIELD_CHARS:
        raise CloudValidationError(
            f"{what} field {key!r} length {len(value)} exceeds {_MAX_FIELD_CHARS}"
        )
    return value


def validate_crdt_update(blob: bytes) -> bytes:
    """Validate an untrusted CRDT-update blob against ``MAX_CRDT_UPDATE_BYTES``.

    The size cap is applied **before** any decode (the payload is never passed to a
    decoder / ``eval`` / ``exec``): this module only bounds and type-checks the raw
    bytes; the actual CRDT decode happens later inside the convergence model. Returns
    the blob unchanged when valid, so a caller can write
    ``blob = validate_crdt_update(blob)`` at the trust boundary.

    Args:
        blob: The raw, untrusted CRDT-update bytes.

    Returns:
        The same ``blob`` when it is bytes within the cap.

    Raises:
        CloudValidationError: If ``blob`` is not ``bytes``/``bytearray``, is empty,
            or exceeds ``MAX_CRDT_UPDATE_BYTES``.
    """
    if not isinstance(blob, (bytes, bytearray)):
        raise CloudValidationError(
            f"CRDT update must be bytes, got {type(blob).__name__}"
        )
    if len(blob) == 0:
        raise CloudValidationError("CRDT update is empty")
    if len(blob) > MAX_CRDT_UPDATE_BYTES:
        raise CloudValidationError(
            f"CRDT update {len(blob)} bytes exceeds MAX_CRDT_UPDATE_BYTES "
            f"({MAX_CRDT_UPDATE_BYTES})"
        )
    return bytes(blob)


def validate_comment(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate an untrusted comment payload (schema + ``MAX_COMMENT_BYTES``).

    Required schema: ``comment_id`` (non-empty str), ``author_id`` (non-empty str),
    ``text`` (str, UTF-8 byte length ``<= MAX_COMMENT_BYTES``). Optional:
    ``resolved`` (bool), ``parent_id`` (non-empty str, for threading), ``region``
    (a mapping of small ints locating the comment on the canvas). The ``text`` byte
    cap is measured on its UTF-8 encoding so a multi-byte payload cannot smuggle
    past a character count (Article VII). Never ``eval``/``exec``'d.

    Args:
        payload: The untrusted comment mapping.

    Returns:
        The validated ``payload`` (same object).

    Raises:
        CloudValidationError: On a missing/ill-typed field or oversized text.
    """
    payload = _require_mapping(payload, "comment payload")
    _require_field_str(payload, "comment_id", "comment payload")
    _require_field_str(payload, "author_id", "comment payload")
    text = payload.get("text")
    if not isinstance(text, str):
        raise CloudValidationError(
            f"comment payload field 'text' must be a str, got {text!r}"
        )
    encoded_len = len(text.encode("utf-8"))
    if encoded_len > MAX_COMMENT_BYTES:
        raise CloudValidationError(
            f"comment text {encoded_len} bytes exceeds MAX_COMMENT_BYTES "
            f"({MAX_COMMENT_BYTES})"
        )
    if "resolved" in payload and not isinstance(payload["resolved"], bool):
        raise CloudValidationError(
            f"comment payload field 'resolved' must be a bool, "
            f"got {payload['resolved']!r}"
        )
    if "parent_id" in payload:
        _require_field_str(payload, "parent_id", "comment payload")
    if "region" in payload:
        _require_mapping(payload["region"], "comment region")
    return payload


def validate_membership(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate an untrusted membership payload (schema + ``MAX_SHARED_MEMBERS``).

    Required schema: ``project_id`` (non-empty str), ``members`` (a sequence of member
    mappings, ``<= MAX_SHARED_MEMBERS`` of them). Each member requires ``member_id``
    (non-empty str) and ``role`` (one of :data:`MEMBER_ROLES`). The member cap is
    enforced before iterating the members so a hostile payload cannot exhaust memory
    (Article VII). Never ``eval``/``exec``'d.

    Args:
        payload: The untrusted membership mapping.

    Returns:
        The validated ``payload`` (same object).

    Raises:
        CloudValidationError: On a missing/ill-typed field, an unknown role, or more
            than ``MAX_SHARED_MEMBERS`` members.
    """
    payload = _require_mapping(payload, "membership payload")
    _require_field_str(payload, "project_id", "membership payload")
    members = payload.get("members")
    if not isinstance(members, (list, tuple)):
        raise CloudValidationError(
            f"membership payload field 'members' must be a list, got {members!r}"
        )
    if len(members) > MAX_SHARED_MEMBERS:
        raise CloudValidationError(
            f"membership has {len(members)} members, exceeds MAX_SHARED_MEMBERS "
            f"({MAX_SHARED_MEMBERS})"
        )
    seen: set[str] = set()
    for member in members:
        member = _require_mapping(member, "member entry")
        member_id = _require_field_str(member, "member_id", "member entry")
        role = _require_field_str(member, "role", "member entry")
        if role not in MEMBER_ROLES:
            raise CloudValidationError(
                f"member role {role!r} is not one of {sorted(MEMBER_ROLES)}"
            )
        if member_id in seen:
            raise CloudValidationError(f"duplicate member_id {member_id!r}")
        seen.add(member_id)
    return payload


def validate_presence(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate an untrusted, ephemeral presence/awareness payload (schema-only).

    Presence is ephemeral (never persisted into the ``.pixproj`` or the sidecar) so it
    carries no persistence cap, but it is still untrusted input: required ``member_id``
    (non-empty str); optional ``cursor`` / ``selection`` (bounded mappings). Rejects
    malformed input; never ``eval``/``exec``'d.

    Args:
        payload: The untrusted presence mapping.

    Returns:
        The validated ``payload`` (same object).

    Raises:
        CloudValidationError: On a missing/ill-typed field.
    """
    payload = _require_mapping(payload, "presence payload")
    _require_field_str(payload, "member_id", "presence payload")
    if "cursor" in payload:
        _require_mapping(payload["cursor"], "presence cursor")
    if "selection" in payload:
        _require_mapping(payload["selection"], "presence selection")
    return payload
