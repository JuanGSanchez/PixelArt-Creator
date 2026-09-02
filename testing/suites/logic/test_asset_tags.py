"""Unit + property tests for :mod:`pixelart_creator.logic.asset_tags` (S11, no Qt).

Covers the reversible do/undo tag ops (HIS-1 pattern; REQ-P11-LOGIC-002,
REQ-P11-DATA-003): add/remove, idempotence (add-present / remove-absent = no-op),
the do/undo reversibility contract, and the factory-time bound checks driven from
``logic/constants`` (not literals).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.asset_catalog import AssetDescriptor, AssetKind
from pixelart_creator.logic.asset_tags import (
    AssetTagError,
    make_add_tag,
    make_remove_tag,
)
from pixelart_creator.logic.constants import MAX_TAG_BYTES, MAX_TAGS_PER_ASSET

HASH = "c" * 64


def descriptor(tags=frozenset()) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id="a", kind=AssetKind.SPRITE, name="Hero", content_hash=HASH, tags=tags
    )


# --------------------------------------------------------------------------- #
# Validation                                                                   #
# --------------------------------------------------------------------------- #


def test_add_rejects_non_descriptor_entry() -> None:
    with pytest.raises(AssetTagError):
        make_add_tag("nope", "hero")  # type: ignore[arg-type]


def test_add_rejects_empty_or_non_str_tag() -> None:
    with pytest.raises(AssetTagError):
        make_add_tag(descriptor(), "")
    with pytest.raises(AssetTagError):
        make_add_tag(descriptor(), 5)  # type: ignore[arg-type]


def test_add_rejects_tag_over_max_tag_bytes() -> None:
    with pytest.raises(AssetTagError):
        make_add_tag(descriptor(), "x" * (MAX_TAG_BYTES + 1))


def test_add_rejects_when_would_exceed_max_tags() -> None:
    full = frozenset(f"t{i}" for i in range(MAX_TAGS_PER_ASSET))
    with pytest.raises(AssetTagError):
        make_add_tag(descriptor(full), "one-more")


def test_remove_rejects_non_descriptor_entry() -> None:
    with pytest.raises(AssetTagError):
        make_remove_tag("nope", "hero")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# add — do / undo / idempotence                                                #
# --------------------------------------------------------------------------- #


def test_add_tag_do_adds_and_undo_restores() -> None:
    original = descriptor(frozenset({"hero"}))
    do, undo = make_add_tag(original, "enemy")
    added = do()
    assert added.tags == frozenset({"hero", "enemy"})
    assert undo().tags == frozenset({"hero"})
    assert undo() == original


def test_add_present_tag_is_noop() -> None:
    original = descriptor(frozenset({"hero"}))
    do, undo = make_add_tag(original, "hero")
    assert do() == original
    assert undo() == original


# --------------------------------------------------------------------------- #
# remove — do / undo / idempotence                                             #
# --------------------------------------------------------------------------- #


def test_remove_tag_do_removes_and_undo_restores() -> None:
    original = descriptor(frozenset({"hero", "enemy"}))
    do, undo = make_remove_tag(original, "enemy")
    removed = do()
    assert removed.tags == frozenset({"hero"})
    assert undo().tags == frozenset({"hero", "enemy"})
    assert undo() == original


def test_remove_absent_tag_is_noop() -> None:
    original = descriptor(frozenset({"hero"}))
    do, undo = make_remove_tag(original, "ghost")
    assert do() == original
    assert undo() == original


# --------------------------------------------------------------------------- #
# Reversibility property: undo(do()) == original for both ops                  #
# --------------------------------------------------------------------------- #


_tag = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=8,
)


@given(existing=st.frozensets(_tag, max_size=8), tag=_tag)
def test_add_then_undo_is_identity(existing, tag) -> None:
    original = descriptor(frozenset(existing))
    do, undo = make_add_tag(original, tag)
    do()
    assert undo() == original


@given(existing=st.frozensets(_tag, max_size=8), tag=_tag)
def test_remove_then_undo_is_identity(existing, tag) -> None:
    original = descriptor(frozenset(existing))
    do, undo = make_remove_tag(original, tag)
    do()
    assert undo() == original
