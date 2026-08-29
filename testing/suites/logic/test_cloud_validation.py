"""Tests for pixelart_creator.logic.cloud_validation (Phase-10 Slice B, no Qt).

The untrusted-input validators (Article VII, REQ-P10-DATA-009/-010,
REQ-P10-BACKEND-002): every collaboration payload that crosses a trust boundary is
schema-validated against strict caps defined once in ``logic.constants`` and is
**never** ``eval``/``exec``'d. These tests exercise each validator's happy path, its
boundary at every cap, and its rejection of malformed / oversized input, plus an
AST-level guard proving no Slice-B module contains an ``eval``/``exec`` call.
"""

from __future__ import annotations

import ast

import pytest

from pixelart_creator.logic import cloud_validation as cv
from pixelart_creator.logic.cloud_validation import (
    MEMBER_ROLES,
    CloudValidationError,
    CrdtMessageKind,
    validate_comment,
    validate_crdt_update,
    validate_membership,
    validate_presence,
)
from pixelart_creator.logic.constants import (
    MAX_COMMENT_BYTES,
    MAX_CRDT_UPDATE_BYTES,
    MAX_SHARED_MEMBERS,
)

# --- validate_crdt_update: size-cap-BEFORE-decode (Article VII) -------------- #


def test_crdt_update_valid_returns_same_bytes():
    blob = b"\x01\x02\x03opaque-crdt-update"
    assert validate_crdt_update(blob) == blob


def test_crdt_update_accepts_bytearray_and_normalises_to_bytes():
    out = validate_crdt_update(bytearray(b"abc"))
    assert out == b"abc"
    assert isinstance(out, bytes)


def test_crdt_update_at_cap_boundary_is_accepted():
    blob = b"\x00" * MAX_CRDT_UPDATE_BYTES
    assert validate_crdt_update(blob) == blob


def test_crdt_update_one_over_cap_is_rejected():
    with pytest.raises(CloudValidationError):
        validate_crdt_update(b"\x00" * (MAX_CRDT_UPDATE_BYTES + 1))


def test_crdt_update_empty_is_rejected():
    with pytest.raises(CloudValidationError):
        validate_crdt_update(b"")


@pytest.mark.parametrize("bad", ["a string", 123, None, ["bytes"]])
def test_crdt_update_non_bytes_is_rejected(bad):
    with pytest.raises(CloudValidationError):
        validate_crdt_update(bad)  # type: ignore[arg-type]


# --- validate_comment -------------------------------------------------------- #


def _comment(**over):
    payload = {"comment_id": "c1", "author_id": "a1", "text": "hello"}
    payload.update(over)
    return payload


def test_comment_minimal_valid():
    assert validate_comment(_comment()) == _comment()


def test_comment_with_optional_fields_valid():
    payload = _comment(resolved=True, parent_id="c0", region={"x": 1, "y": 2})
    assert validate_comment(payload) is payload


def test_comment_text_at_byte_cap_is_accepted():
    validate_comment(_comment(text="x" * MAX_COMMENT_BYTES))


def test_comment_text_one_byte_over_cap_is_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(text="x" * (MAX_COMMENT_BYTES + 1)))


def test_comment_multibyte_text_measured_by_utf8_bytes_not_chars():
    # A 2-byte char: char count is under the cap, byte count is over it.
    chars = (MAX_COMMENT_BYTES // 2) + 1
    text = "é" * chars  # 'é' encodes to 2 UTF-8 bytes
    assert len(text) <= MAX_COMMENT_BYTES  # would pass a naive char count
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(text=text))


@pytest.mark.parametrize("missing", ["comment_id", "author_id"])
def test_comment_missing_required_field_rejected(missing):
    payload = _comment()
    del payload[missing]
    with pytest.raises(CloudValidationError):
        validate_comment(payload)


def test_comment_text_not_str_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(text=123))


def test_comment_resolved_not_bool_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(resolved="yes"))


def test_comment_parent_id_empty_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(parent_id=""))


def test_comment_region_not_mapping_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(region=[1, 2]))


def test_comment_non_mapping_payload_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_comment_too_many_keys_rejected():
    payload = _comment()
    for i in range(cv._MAX_PAYLOAD_KEYS + 1):
        payload[f"extra{i}"] = "x"
    with pytest.raises(CloudValidationError):
        validate_comment(payload)


def test_comment_non_str_key_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment({"comment_id": "c", "author_id": "a", "text": "t", 7: "x"})


def test_comment_overlong_id_field_rejected():
    with pytest.raises(CloudValidationError):
        validate_comment(_comment(comment_id="x" * (cv._MAX_FIELD_CHARS + 1)))


# --- validate_membership ----------------------------------------------------- #


def _membership(n=2, project_id="p1"):
    return {
        "project_id": project_id,
        "members": [{"member_id": f"m{i}", "role": "editor"} for i in range(n)],
    }


def test_membership_valid():
    payload = _membership()
    assert validate_membership(payload) is payload


def test_membership_at_member_cap_accepted():
    validate_membership(_membership(n=MAX_SHARED_MEMBERS))


def test_membership_one_over_cap_rejected():
    with pytest.raises(CloudValidationError):
        validate_membership(_membership(n=MAX_SHARED_MEMBERS + 1))


def test_membership_missing_project_id_rejected():
    payload = _membership()
    del payload["project_id"]
    with pytest.raises(CloudValidationError):
        validate_membership(payload)


def test_membership_members_not_a_list_rejected():
    with pytest.raises(CloudValidationError):
        validate_membership({"project_id": "p", "members": "nope"})


def test_membership_member_missing_id_rejected():
    with pytest.raises(CloudValidationError):
        validate_membership({"project_id": "p", "members": [{"role": "editor"}]})


def test_membership_unknown_role_rejected():
    payload = {"project_id": "p", "members": [{"member_id": "m", "role": "admin"}]}
    with pytest.raises(CloudValidationError):
        validate_membership(payload)


def test_membership_duplicate_member_id_rejected():
    payload = {
        "project_id": "p",
        "members": [
            {"member_id": "dup", "role": "editor"},
            {"member_id": "dup", "role": "viewer"},
        ],
    }
    with pytest.raises(CloudValidationError):
        validate_membership(payload)


def test_membership_member_entry_not_mapping_rejected():
    with pytest.raises(CloudValidationError):
        validate_membership({"project_id": "p", "members": ["m1"]})


def test_every_member_role_is_accepted():
    for role in sorted(MEMBER_ROLES):
        payload = {"project_id": "p", "members": [{"member_id": "m", "role": role}]}
        assert validate_membership(payload) is payload


# --- validate_presence ------------------------------------------------------- #


def test_presence_minimal_valid():
    payload = {"member_id": "m1"}
    assert validate_presence(payload) is payload


def test_presence_with_cursor_and_selection_valid():
    payload = {"member_id": "m", "cursor": {"x": 1}, "selection": {"a": 2}}
    assert validate_presence(payload) is payload


def test_presence_missing_member_id_rejected():
    with pytest.raises(CloudValidationError):
        validate_presence({"cursor": {"x": 1}})


def test_presence_cursor_not_mapping_rejected():
    with pytest.raises(CloudValidationError):
        validate_presence({"member_id": "m", "cursor": [1, 2]})


def test_presence_selection_not_mapping_rejected():
    with pytest.raises(CloudValidationError):
        validate_presence({"member_id": "m", "selection": "nope"})


# --- vocabulary + Article VII no-eval/exec guard ----------------------------- #


def test_crdt_message_kind_vocabulary():
    assert {k.value for k in CrdtMessageKind} == {
        "structured_update",
        "raster_update",
        "presence",
    }


@pytest.mark.parametrize(
    "module_name",
    [
        "pixelart_creator.logic.cloud_validation",
        "pixelart_creator.logic.convergence",
        "pixelart_creator.data.cloud.shared_adapter",
    ],
)
def test_no_eval_or_exec_call_in_slice_b_modules(module_name):
    """Article VII: no Slice-B module may contain an ``eval``/``exec`` call.

    A source-string scan would false-positive on the docstrings (which discuss
    ``eval``/``exec``), so this parses the AST and asserts no *call* to a name or
    attribute ``eval``/``exec`` exists — a robust untrusted-input regression guard.
    """
    import importlib

    module = importlib.import_module(module_name)
    with open(module.__file__, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                assert func.id not in {"eval", "exec"}
            elif isinstance(func, ast.Attribute):
                assert func.attr not in {"eval", "exec"}
