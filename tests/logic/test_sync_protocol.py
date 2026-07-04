"""Tests for pixelart_creator.logic.sync_protocol (Phase-10 Slice C, no Qt).

Covers the pure wire-protocol framing shared by the client transport and the out-of-layer
backend relay (ADR-0027 §4; REQ-P10-DATA-010, REQ-P10-BACKEND-002, Article VII). Proves
the encode/decode round-trip for every message kind and the untrusted-input rejection
surface of :func:`decode_message`: oversized frames, non-bytes, invalid UTF-8/JSON,
non-object frames, unknown version, unknown kind, bad ``document_id``, and malformed
update/presence bodies — all rejected with :class:`CloudValidationError`, never
``eval``/``exec``'d.
"""

from __future__ import annotations

import base64
import json

import pytest

from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.constants import MAX_CRDT_UPDATE_BYTES
from pixelart_creator.logic.sync_protocol import (
    ControlKind,
    SyncMessage,
    decode_message,
    encode_join,
    encode_leave,
    encode_presence,
    encode_update,
)

DOC = "doc-1"


# --------------------------------------------------------------------------- #
# Round-trips.
# --------------------------------------------------------------------------- #


def test_join_round_trip():
    msg = decode_message(encode_join(DOC))
    assert msg == SyncMessage(kind=ControlKind.JOIN, document_id=DOC)


def test_leave_round_trip():
    msg = decode_message(encode_leave(DOC))
    assert msg == SyncMessage(kind=ControlKind.LEAVE, document_id=DOC)


def test_update_round_trip():
    blob = b"a crdt update blob"
    msg = decode_message(encode_update(DOC, blob))
    assert msg.kind is ControlKind.UPDATE
    assert msg.document_id == DOC
    assert msg.blob == blob


def test_presence_round_trip():
    msg = decode_message(encode_presence(DOC, {"member_id": "alice"}))
    assert msg.kind is ControlKind.PRESENCE
    assert msg.presence["member_id"] == "alice"


def test_frames_are_deterministic():
    assert encode_join(DOC) == encode_join(DOC)
    assert encode_update(DOC, b"x") == encode_update(DOC, b"x")


# --------------------------------------------------------------------------- #
# Encode-side validation.
# --------------------------------------------------------------------------- #


def test_encode_update_rejects_oversized_blob():
    with pytest.raises(CloudValidationError):
        encode_update(DOC, b"x" * (MAX_CRDT_UPDATE_BYTES + 1))


def test_encode_rejects_empty_document_id():
    with pytest.raises(CloudValidationError):
        encode_join("")


def test_encode_rejects_overlong_document_id():
    with pytest.raises(CloudValidationError):
        encode_join("d" * 2000)


def test_encode_presence_rejects_missing_member_id():
    with pytest.raises(CloudValidationError):
        encode_presence(DOC, {"cursor": {"x": 1}})


# --------------------------------------------------------------------------- #
# decode_message — untrusted-input rejection surface (Article VII).
# --------------------------------------------------------------------------- #


def test_decode_rejects_non_bytes():
    with pytest.raises(CloudValidationError):
        decode_message("not bytes")  # type: ignore[arg-type]


def test_decode_rejects_oversized_frame():
    with pytest.raises(CloudValidationError):
        decode_message(b"x" * (MAX_CRDT_UPDATE_BYTES * 2 + 5000))


def test_decode_rejects_invalid_utf8_json():
    with pytest.raises(CloudValidationError):
        decode_message(b"\xff\xfe not json")


def test_decode_rejects_non_object_frame():
    with pytest.raises(CloudValidationError):
        decode_message(b"[1, 2, 3]")


def test_decode_rejects_unknown_version():
    frame = json.dumps({"v": 2, "kind": "join", "doc": DOC}).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_unknown_kind():
    frame = json.dumps({"v": 1, "kind": "explode", "doc": DOC}).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_missing_document_id():
    frame = json.dumps({"v": 1, "kind": "join"}).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_update_blob_not_str():
    frame = json.dumps({"v": 1, "kind": "update", "doc": DOC, "blob": 123}).encode(
        "utf-8"
    )
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_update_blob_not_base64():
    frame = json.dumps(
        {"v": 1, "kind": "update", "doc": DOC, "blob": "!!!not base64!!!"}
    ).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_oversized_update_blob_after_base64():
    body = base64.b64encode(b"x" * (MAX_CRDT_UPDATE_BYTES + 1)).decode("ascii")
    frame = json.dumps({"v": 1, "kind": "update", "doc": DOC, "blob": body}).encode(
        "utf-8"
    )
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_presence_not_a_mapping():
    frame = json.dumps(
        {"v": 1, "kind": "presence", "doc": DOC, "presence": "nope"}
    ).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_decode_rejects_presence_missing_member_id():
    frame = json.dumps(
        {"v": 1, "kind": "presence", "doc": DOC, "presence": {"cursor": {"x": 1}}}
    ).encode("utf-8")
    with pytest.raises(CloudValidationError):
        decode_message(frame)


def test_control_kind_vocabulary():
    assert {k.value for k in ControlKind} == {"join", "leave", "update", "presence"}
