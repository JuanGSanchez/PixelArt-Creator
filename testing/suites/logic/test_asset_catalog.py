"""Unit tests for :mod:`pixelart_creator.logic.asset_catalog` (S11, no Qt).

Covers the pure catalog identity model (ADR-0030 §1; REQ-P11-DATA-001,
REQ-P11-LOGIC-001): descriptor validation (identity/kind/name/hash/tags/metadata/
path), the tag/metadata caps enforced from ``logic/constants`` (not literals), and the
immutable, deterministic :class:`AssetCatalog` (add/remove/get/entries, stable id
ordering, uniqueness + count cap).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic import asset_catalog
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.constants import (
    MAX_CATALOG_ASSETS,
    MAX_METADATA_BYTES,
    MAX_TAG_BYTES,
    MAX_TAGS_PER_ASSET,
)

HASH_A = "a" * 64
HASH_B = "b" * 64


def make_descriptor(
    asset_id: str = "asset-1",
    kind: AssetKind = AssetKind.SPRITE,
    name: str = "Hero",
    content_hash: str = HASH_A,
    **kwargs,
) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=content_hash,
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# AssetKind vocabulary                                                         #
# --------------------------------------------------------------------------- #


def test_asset_kind_values() -> None:
    assert {k.value for k in AssetKind} == {
        "sprite",
        "animation",
        "tileset",
        "tilemap",
        "palette",
    }


# --------------------------------------------------------------------------- #
# AssetDescriptor — valid construction for every kind                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("kind", list(AssetKind))
def test_descriptor_constructs_for_every_kind(kind: AssetKind) -> None:
    desc = make_descriptor(kind=kind)
    assert desc.kind is kind
    assert desc.tags == frozenset()
    assert dict(desc.metadata) == {}
    assert desc.path is None


def test_descriptor_is_frozen_and_comparable() -> None:
    a = make_descriptor()
    b = make_descriptor()
    assert a == b
    with pytest.raises(Exception):
        a.name = "changed"  # type: ignore[misc]


def test_descriptor_keeps_valid_tags_metadata_path() -> None:
    desc = make_descriptor(
        tags={"hero", "enemy"},
        metadata={"author": "j", "frames": 4, "loop": True, "note": None},
        path="library/hero.pixproj",
    )
    assert desc.tags == frozenset({"hero", "enemy"})
    assert dict(desc.metadata) == {
        "author": "j",
        "frames": 4,
        "loop": True,
        "note": None,
    }
    assert desc.path == "library/hero.pixproj"


# --------------------------------------------------------------------------- #
# AssetDescriptor — field validation                                          #
# --------------------------------------------------------------------------- #


def test_descriptor_rejects_empty_asset_id() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(asset_id="")


def test_descriptor_rejects_non_str_asset_id() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(asset_id=123)  # type: ignore[arg-type]


def test_descriptor_rejects_non_kind() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(kind="sprite")  # type: ignore[arg-type]


def test_descriptor_rejects_empty_name() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(name="")


def test_descriptor_rejects_empty_content_hash() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(content_hash="")


def test_descriptor_rejects_non_str_path() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(path=123)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Tag caps — enforced from constants, not literals                            #
# --------------------------------------------------------------------------- #


def test_descriptor_rejects_non_iterable_tags() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(tags=123)  # type: ignore[arg-type]


def test_descriptor_rejects_empty_or_non_str_tag() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(tags={""})
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(tags={5})  # type: ignore[arg-type]


def test_descriptor_rejects_tag_over_max_tag_bytes() -> None:
    over = "x" * (MAX_TAG_BYTES + 1)
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(tags={over})


def test_descriptor_rejects_more_than_max_tags() -> None:
    tags = {f"tag-{i}" for i in range(MAX_TAGS_PER_ASSET + 1)}
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(tags=tags)


def test_descriptor_allows_exactly_max_tags() -> None:
    tags = {f"tag-{i}" for i in range(MAX_TAGS_PER_ASSET)}
    desc = make_descriptor(tags=tags)
    assert len(desc.tags) == MAX_TAGS_PER_ASSET


# --------------------------------------------------------------------------- #
# Metadata caps                                                                #
# --------------------------------------------------------------------------- #


def test_descriptor_rejects_non_mapping_metadata() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(metadata=["not", "a", "mapping"])  # type: ignore[arg-type]


def test_descriptor_rejects_non_str_metadata_key() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(metadata={1: "x"})  # type: ignore[dict-item]


def test_descriptor_rejects_non_scalar_metadata_value() -> None:
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(metadata={"nested": {"a": 1}})


def test_descriptor_rejects_metadata_over_max_bytes() -> None:
    big = {"blob": "y" * (MAX_METADATA_BYTES + 1)}
    with pytest.raises(AssetCatalogModelError):
        make_descriptor(metadata=big)


# --------------------------------------------------------------------------- #
# AssetCatalog — construction, uniqueness, ordering, count cap                #
# --------------------------------------------------------------------------- #


def test_empty_catalog_has_no_entries() -> None:
    assert AssetCatalog().entries() == ()


def test_catalog_rejects_non_descriptor_member() -> None:
    with pytest.raises(AssetCatalogModelError):
        AssetCatalog(descriptors=("nope",))  # type: ignore[arg-type]


def test_catalog_rejects_duplicate_id_in_constructor() -> None:
    a = make_descriptor(asset_id="dup")
    b = make_descriptor(asset_id="dup", name="Other")
    with pytest.raises(AssetCatalogModelError):
        AssetCatalog(descriptors=(a, b))


def test_catalog_entries_sorted_by_asset_id() -> None:
    z = make_descriptor(asset_id="z")
    a = make_descriptor(asset_id="a")
    m = make_descriptor(asset_id="m")
    cat = AssetCatalog(descriptors=(z, a, m))
    assert [d.asset_id for d in cat.entries()] == ["a", "m", "z"]


def test_catalog_constructor_count_cap(monkeypatch) -> None:
    monkeypatch.setattr(asset_catalog, "MAX_CATALOG_ASSETS", 1)
    a = make_descriptor(asset_id="a")
    b = make_descriptor(asset_id="b")
    with pytest.raises(AssetCatalogModelError):
        AssetCatalog(descriptors=(a, b))


def test_max_catalog_assets_is_the_named_constant() -> None:
    # The cap comes from logic/constants (not an inlined literal).
    assert asset_catalog.MAX_CATALOG_ASSETS == MAX_CATALOG_ASSETS


# --------------------------------------------------------------------------- #
# AssetCatalog — add / remove / get (immutability)                            #
# --------------------------------------------------------------------------- #


def test_add_returns_new_catalog_leaving_original_unchanged() -> None:
    base = AssetCatalog()
    added = base.add(make_descriptor(asset_id="a"))
    assert base.entries() == ()
    assert [d.asset_id for d in added.entries()] == ["a"]


def test_add_rejects_non_descriptor() -> None:
    with pytest.raises(AssetCatalogModelError):
        AssetCatalog().add("nope")  # type: ignore[arg-type]


def test_add_rejects_duplicate_id() -> None:
    cat = AssetCatalog().add(make_descriptor(asset_id="a"))
    with pytest.raises(AssetCatalogModelError):
        cat.add(make_descriptor(asset_id="a", name="Dup"))


def test_add_at_cap_raises(monkeypatch) -> None:
    monkeypatch.setattr(asset_catalog, "MAX_CATALOG_ASSETS", 1)
    cat = AssetCatalog().add(make_descriptor(asset_id="a"))
    with pytest.raises(AssetCatalogModelError):
        cat.add(make_descriptor(asset_id="b"))


def test_remove_returns_new_catalog() -> None:
    cat = (
        AssetCatalog()
        .add(make_descriptor(asset_id="a"))
        .add(make_descriptor(asset_id="b"))
    )
    smaller = cat.remove("a")
    assert [d.asset_id for d in smaller.entries()] == ["b"]
    # original untouched (immutable)
    assert [d.asset_id for d in cat.entries()] == ["a", "b"]


def test_remove_unknown_raises() -> None:
    with pytest.raises(AssetCatalogModelError):
        AssetCatalog().remove("ghost")


def test_get_returns_matching_or_none() -> None:
    desc = make_descriptor(asset_id="a")
    cat = AssetCatalog().add(desc)
    assert cat.get("a") == desc
    assert cat.get("unknown") is None
