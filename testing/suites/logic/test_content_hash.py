"""Unit + property tests for :mod:`pixelart_creator.logic.content_hash` (S11, no Qt).

Covers the Phase-11 content-hash primitive (ADR-0030 §3; REQ-P11-DATA-004,
REQ-P11-LOGIC-006): determinism of :func:`content_hash`, the byte-exact
canonicalization of :func:`canonical_json_bytes`, and the defensive
:func:`is_valid_hash` gate. Hypothesis proves determinism/idempotence and
key-order-independence hold across generated inputs.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.content_hash import (
    ContentHashError,
    canonical_json_bytes,
    content_hash,
    is_valid_hash,
    same_content,
)

# A JSON-scalar strategy for building canonicalizable objects.
_json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**9), max_value=10**9),
    st.text(max_size=32),
)


# --------------------------------------------------------------------------- #
# content_hash — determinism                                                   #
# --------------------------------------------------------------------------- #


def test_same_bytes_same_hash() -> None:
    assert content_hash(b"pixel-art") == content_hash(b"pixel-art")


def test_different_bytes_different_hash() -> None:
    assert content_hash(b"sprite-a") != content_hash(b"sprite-b")


def test_hash_is_64_char_lowercase_hex() -> None:
    digest = content_hash(b"anything")
    assert len(digest) == 64
    assert is_valid_hash(digest)


def test_content_hash_accepts_bytearray_matching_bytes() -> None:
    assert content_hash(bytearray(b"abc")) == content_hash(b"abc")


def test_content_hash_rejects_str() -> None:
    with pytest.raises(ContentHashError):
        content_hash("not-bytes")  # type: ignore[arg-type]


@given(st.binary(max_size=256))
def test_content_hash_deterministic_property(blob: bytes) -> None:
    # Same bytes -> identical, valid digest across repeated calls (determinism).
    first = content_hash(blob)
    assert first == content_hash(bytes(blob))
    assert is_valid_hash(first)


# --------------------------------------------------------------------------- #
# same_content — the "unchanged" detector                                      #
# --------------------------------------------------------------------------- #


def test_same_content_true_for_identical_bytes() -> None:
    assert same_content(b"frame", b"frame") is True


def test_same_content_false_for_differing_bytes() -> None:
    assert same_content(b"frame-1", b"frame-2") is False


def test_same_content_rejects_non_bytes() -> None:
    with pytest.raises(ContentHashError):
        same_content("a", b"b")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# canonical_json_bytes — byte-exact canonicalization                           #
# --------------------------------------------------------------------------- #


def test_canonical_json_bytes_key_order_independent() -> None:
    a = canonical_json_bytes({"b": 1, "a": 2})
    b = canonical_json_bytes({"a": 2, "b": 1})
    assert a == b


def test_canonical_json_bytes_is_compact_utf8() -> None:
    # Compact separators, no ASCII escaping (ensure_ascii=False), sorted keys.
    assert canonical_json_bytes({"z": "ñ", "a": 1}) == '{"a":1,"z":"ñ"}'.encode("utf-8")


def test_canonical_json_bytes_rejects_non_serialisable() -> None:
    with pytest.raises(ContentHashError):
        canonical_json_bytes({"bad": {1, 2, 3}})  # a set is not JSON-serialisable


@given(st.lists(st.tuples(st.text(min_size=1, max_size=8), _json_scalars), max_size=8))
def test_canonicalization_is_permutation_invariant(pairs) -> None:
    # De-dup keys, then build two dicts with opposite insertion order; their
    # canonical bytes (and therefore hashes) must be identical (ADR-0030 §3).
    mapping = dict(pairs)
    forward = {k: mapping[k] for k in mapping}
    reverse = {k: mapping[k] for k in reversed(list(mapping))}
    assert canonical_json_bytes(forward) == canonical_json_bytes(reverse)
    assert content_hash(canonical_json_bytes(forward)) == content_hash(
        canonical_json_bytes(reverse)
    )


# --------------------------------------------------------------------------- #
# is_valid_hash — defensive gate                                               #
# --------------------------------------------------------------------------- #


def test_is_valid_hash_accepts_well_formed() -> None:
    assert is_valid_hash("a" * 64) is True
    assert is_valid_hash("0123456789abcdef" * 4) is True


def test_is_valid_hash_rejects_wrong_length() -> None:
    assert is_valid_hash("a" * 63) is False
    assert is_valid_hash("a" * 65) is False


def test_is_valid_hash_rejects_uppercase() -> None:
    assert is_valid_hash("A" * 64) is False


def test_is_valid_hash_rejects_non_hex() -> None:
    assert is_valid_hash("g" * 64) is False


def test_is_valid_hash_rejects_non_str() -> None:
    assert is_valid_hash(None) is False
    assert is_valid_hash(b"a" * 64) is False
    assert is_valid_hash(12345) is False
