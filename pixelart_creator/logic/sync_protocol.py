# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure real-time sync wire protocol — framing + validation (zero Qt, S11).

Phase-10 Slice C (ADR-0027 §4; spec REQ-P10-DATA-010, REQ-P10-BACKEND-001/-002,
Article VII). The client transport (``data/cloud/{loopback,ws}_transport.py``) and the
out-of-layer relay (``sync_backend/server.py``) exchange a small, versioned, JSON-framed
message set — ``{join, leave, update, presence}`` — over the wire. This module is the
**single, pure, deterministic** definition of that framing, so **both** sides import the
same encoder/decoder and Article VII caps without the backend ever importing ``data/``
(it depends only on pure ``logic/``: :mod:`~pixelart_creator.logic.cloud_validation` +
:mod:`~pixelart_creator.logic.constants`).

Every inbound frame is **untrusted input**: :func:`decode_message` size-caps the raw
bytes against ``MAX_CRDT_UPDATE_BYTES`` **before** any decode, JSON-parses (never
``eval``/``exec``), checks the message vocabulary, and delegates the payload to the
shipped pure validators (``validate_crdt_update`` for CRDT blobs, ``validate_presence``
for awareness payloads). Malformed/oversized input raises
:class:`~pixelart_creator.logic.cloud_validation.CloudValidationError` — the caller
rejects it without crashing (no crash, no silent corruption, no memory exhaustion).

The :class:`ControlKind` vocabulary is module-local enumerated vocabulary (ADR-0001 /
BF-2, the ``BlendMode``/``PlaybackMode``/``CrdtMessageKind`` precedent), not a constant.
"""

from __future__ import annotations

import base64
import enum
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from pixelart_creator.logic.cloud_validation import (
    CloudValidationError,
    validate_crdt_update,
    validate_presence,
)
from pixelart_creator.logic.constants import MAX_CRDT_UPDATE_BYTES

__all__ = [
    "ControlKind",
    "SyncMessage",
    "encode_update",
    "encode_presence",
    "encode_join",
    "encode_leave",
    "decode_message",
]

#: Wire-protocol version. A decoder rejects a frame tagged with any other version.
_PROTOCOL_VERSION = 1

#: Defensive ceiling, bytes, on a whole framed message. A frame wraps a CRDT blob (or a
#: presence payload) in a small JSON envelope with a base64 body (~4/3 expansion); this
#: bounds the envelope generously above ``MAX_CRDT_UPDATE_BYTES`` so the raw frame is
#: capped *before* JSON decode (Article VII). Intrinsic to the framing, so module-local.
_MAX_FRAME_BYTES = MAX_CRDT_UPDATE_BYTES * 2 + 4096

#: Defensive cap on a ``document_id`` string field length (an id is short by
#: construction; a hostile mega-string is rejected before use, Article VII).
_MAX_DOCUMENT_ID_CHARS = 1024


class ControlKind(enum.Enum):
    """The real-time wire-message vocabulary (ADR-0027 §4).

    Module-local enumerated vocabulary (ADR-0001 / BF-2), shared by the client
    transport and the backend relay so both agree on the taxonomy without a numeric
    constant. ``JOIN``/``LEAVE`` are session control; ``UPDATE`` carries a (persisted)
    CRDT blob; ``PRESENCE`` carries an ephemeral awareness payload (never persisted).
    """

    #: Subscribe a connection to a document's relay (server replies with the backlog).
    JOIN = "join"
    #: Unsubscribe a connection from a document's relay.
    LEAVE = "leave"
    #: A CRDT-update blob (persisted + relayed to the document's other peers).
    UPDATE = "update"
    #: An ephemeral awareness/presence payload (relayed, never persisted).
    PRESENCE = "presence"


@dataclass(frozen=True)
class SyncMessage:
    """A decoded, validated wire frame (the normalized transport/backend unit).

    Attributes:
        kind: The :class:`ControlKind` of the frame.
        document_id: The shared-document id the frame targets.
        blob: For :attr:`ControlKind.UPDATE`, the validated CRDT-update bytes; ``None``
            otherwise.
        presence: For :attr:`ControlKind.PRESENCE`, the validated presence mapping;
            ``None`` otherwise.
    """

    kind: ControlKind
    document_id: str
    blob: Optional[bytes] = None
    presence: Optional[Mapping[str, Any]] = None


def _require_document_id(document_id: object) -> str:
    """Return ``document_id`` as a bounded non-empty str, or raise."""
    if not isinstance(document_id, str) or not document_id:
        raise CloudValidationError(
            f"document_id must be a non-empty str, got {document_id!r}"
        )
    if len(document_id) > _MAX_DOCUMENT_ID_CHARS:
        raise CloudValidationError(
            f"document_id length {len(document_id)} exceeds {_MAX_DOCUMENT_ID_CHARS}"
        )
    return document_id


def _encode(kind: ControlKind, document_id: str, body: Mapping[str, Any]) -> bytes:
    """Serialise one frame to canonical, deterministic JSON bytes."""
    frame = {
        "v": _PROTOCOL_VERSION,
        "kind": kind.value,
        "doc": _require_document_id(document_id),
        **body,
    }
    return json.dumps(frame, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_update(document_id: str, blob: bytes) -> bytes:
    """Frame a CRDT-update ``blob`` for ``document_id`` (validated before framing).

    The blob is checked against ``MAX_CRDT_UPDATE_BYTES`` (``validate_crdt_update``)
    before it is base64-wrapped, so an oversized update never reaches the wire.

    Raises:
        CloudValidationError: If ``blob`` is not bytes, empty, or oversized.
    """
    checked = validate_crdt_update(blob)
    return _encode(
        ControlKind.UPDATE,
        document_id,
        {"blob": base64.b64encode(checked).decode("ascii")},
    )


def encode_presence(document_id: str, payload: Mapping[str, Any]) -> bytes:
    """Frame an ephemeral presence ``payload`` for ``document_id`` (validated first).

    Raises:
        CloudValidationError: If ``payload`` is not a valid presence mapping.
    """
    validated = validate_presence(payload)
    return _encode(ControlKind.PRESENCE, document_id, {"presence": dict(validated)})


def encode_join(document_id: str) -> bytes:
    """Frame a JOIN control message for ``document_id``."""
    return _encode(ControlKind.JOIN, document_id, {})


def encode_leave(document_id: str) -> bytes:
    """Frame a LEAVE control message for ``document_id``."""
    return _encode(ControlKind.LEAVE, document_id, {})


def decode_message(raw: bytes) -> SyncMessage:
    """Decode + validate an untrusted wire frame into a :class:`SyncMessage`.

    The untrusted-input defence (Article VII, REQ-P10-BACKEND-002): ``raw`` is
    size-capped **before** decode, JSON-parsed (never ``eval``/``exec``), its version +
    vocabulary checked, and the payload delegated to the shipped pure validators
    (``validate_crdt_update`` / ``validate_presence``). Both the client transport and
    the backend relay call this at their trust boundary.

    Args:
        raw: The raw, untrusted frame bytes.

    Returns:
        The decoded, validated :class:`SyncMessage`.

    Raises:
        CloudValidationError: If ``raw`` is not bytes, oversized, not valid UTF-8 JSON,
            not a JSON object, carries an unknown version/kind, or its payload fails the
            corresponding validator.
    """
    if not isinstance(raw, (bytes, bytearray)):
        raise CloudValidationError(
            f"sync frame must be bytes, got {type(raw).__name__}"
        )
    if len(raw) > _MAX_FRAME_BYTES:
        raise CloudValidationError(
            f"sync frame {len(raw)} bytes exceeds {_MAX_FRAME_BYTES}"
        )
    try:
        frame = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudValidationError(
            f"sync frame is not valid UTF-8 JSON: {exc}"
        ) from exc
    if not isinstance(frame, dict):
        raise CloudValidationError("sync frame must decode to a JSON object")
    if frame.get("v") != _PROTOCOL_VERSION:
        raise CloudValidationError(
            f"unsupported sync protocol version {frame.get('v')!r}"
        )
    kind_value = frame.get("kind")
    try:
        kind = ControlKind(kind_value)
    except ValueError as exc:
        raise CloudValidationError(f"unknown sync message kind {kind_value!r}") from exc
    document_id = _require_document_id(frame.get("doc"))

    if kind is ControlKind.UPDATE:
        body = frame.get("blob")
        if not isinstance(body, str):
            raise CloudValidationError("update frame 'blob' must be a base64 str")
        try:
            blob = base64.b64decode(body, validate=True)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise CloudValidationError(
                f"update frame 'blob' is not base64: {exc}"
            ) from exc
        return SyncMessage(
            kind=kind, document_id=document_id, blob=validate_crdt_update(blob)
        )

    if kind is ControlKind.PRESENCE:
        presence = frame.get("presence")
        if not isinstance(presence, Mapping):
            raise CloudValidationError("presence frame 'presence' must be a mapping")
        return SyncMessage(
            kind=kind, document_id=document_id, presence=validate_presence(presence)
        )

    return SyncMessage(kind=kind, document_id=document_id)
