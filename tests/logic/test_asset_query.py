"""Unit + property tests for :mod:`pixelart_creator.logic.asset_query` (S11, no Qt).

Covers the pure, deterministic search/filter query (REQ-P11-LOGIC-003): filter by
name substring (case-insensitive), by tag(s) (AND), by kind, their intersection,
empty-query-returns-full, no-match, bounded result count, argument validation, and —
via Hypothesis — determinism (same catalog + same query = byte-identical result).
T11-1-06.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_query import AssetQueryError, query

HASH = "d" * 64


def desc(asset_id, name, kind=AssetKind.SPRITE, tags=frozenset()):
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=HASH,
        tags=frozenset(tags),
    )


def sample_catalog() -> AssetCatalog:
    return AssetCatalog(
        descriptors=(
            desc("s1", "Hero Sprite", AssetKind.SPRITE, {"hero", "player"}),
            desc("s2", "Enemy Sprite", AssetKind.SPRITE, {"enemy"}),
            desc("a1", "Hero Walk", AssetKind.ANIMATION, {"hero", "walk"}),
            desc("t1", "Ground Tiles", AssetKind.TILESET, {"ground"}),
        )
    )


# --------------------------------------------------------------------------- #
# Empty query returns the full catalog in stable order                        #
# --------------------------------------------------------------------------- #


def test_empty_query_returns_full_catalog_sorted() -> None:
    cat = sample_catalog()
    result = query(cat)
    assert [d.asset_id for d in result] == ["a1", "s1", "s2", "t1"]
    assert result == cat.entries()


# --------------------------------------------------------------------------- #
# Filter by each dimension                                                     #
# --------------------------------------------------------------------------- #


def test_filter_by_tag() -> None:
    result = query(sample_catalog(), tags=["hero"])
    assert {d.asset_id for d in result} == {"a1", "s1"}


def test_filter_by_multiple_tags_is_and() -> None:
    result = query(sample_catalog(), tags=["hero", "walk"])
    assert [d.asset_id for d in result] == ["a1"]


def test_filter_by_kind() -> None:
    result = query(sample_catalog(), kind=AssetKind.SPRITE)
    assert {d.asset_id for d in result} == {"s1", "s2"}


def test_filter_by_name_substring_case_insensitive() -> None:
    result = query(sample_catalog(), name="hero")
    assert {d.asset_id for d in result} == {"a1", "s1"}


def test_combined_name_tag_kind_intersect() -> None:
    result = query(sample_catalog(), name="hero", tags=["hero"], kind=AssetKind.SPRITE)
    assert [d.asset_id for d in result] == ["s1"]


def test_no_match_returns_empty() -> None:
    assert query(sample_catalog(), tags=["nonexistent"]) == ()


def test_result_count_is_bounded_by_catalog_size() -> None:
    cat = sample_catalog()
    assert len(query(cat, name="e")) <= len(cat.entries())


# --------------------------------------------------------------------------- #
# Argument validation                                                          #
# --------------------------------------------------------------------------- #


def test_query_rejects_non_catalog() -> None:
    with pytest.raises(AssetQueryError):
        query("not-a-catalog")  # type: ignore[arg-type]


def test_query_rejects_non_str_name() -> None:
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), name=5)  # type: ignore[arg-type]


def test_query_rejects_non_kind() -> None:
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), kind="sprite")  # type: ignore[arg-type]


def test_query_rejects_bare_str_tags() -> None:
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), tags="hero")  # type: ignore[arg-type]


def test_query_rejects_non_sequence_tags() -> None:
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), tags=123)  # type: ignore[arg-type]


def test_query_rejects_empty_or_non_str_tag_element() -> None:
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), tags=[""])
    with pytest.raises(AssetQueryError):
        query(sample_catalog(), tags=[5])  # type: ignore[list-item]


# --------------------------------------------------------------------------- #
# Determinism (Hypothesis)                                                     #
# --------------------------------------------------------------------------- #

_ids = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=1,
    max_size=6,
)


@st.composite
def _catalogs(draw):
    n = draw(st.integers(min_value=0, max_value=6))
    ids = draw(st.lists(_ids, min_size=n, max_size=n, unique=True))
    descriptors = []
    for i in ids:
        kind = draw(st.sampled_from(list(AssetKind)))
        tags = draw(
            st.frozensets(st.sampled_from(["hero", "enemy", "walk"]), max_size=3)
        )
        descriptors.append(desc(i, f"name-{i}", kind, tags))
    return AssetCatalog(descriptors=tuple(descriptors))


@given(
    cat=_catalogs(),
    name=st.one_of(st.none(), st.sampled_from(["name", "x", "a"])),
    tags=st.lists(st.sampled_from(["hero", "enemy"]), max_size=2),
    kind=st.one_of(st.none(), st.sampled_from(list(AssetKind))),
)
def test_query_is_deterministic(cat, name, tags, kind) -> None:
    first = query(cat, name=name, tags=tags, kind=kind)
    second = query(cat, name=name, tags=tags, kind=kind)
    assert first == second
    # Result preserves the catalog's stable asset_id ordering and is a subset.
    ids = [d.asset_id for d in first]
    assert ids == sorted(ids)
    assert set(first).issubset(set(cat.entries()))
