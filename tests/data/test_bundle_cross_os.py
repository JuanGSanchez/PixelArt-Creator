"""Cross-OS portable-bundle import round-trip tests (Slice 13B, no Qt).

Covers REQ-P13-DATA-007 / SC-P13-DATA-007-1 (ADR-0037 §3): a ``.pixbundle`` exported on
one OS imports **model-equal** on another — same layers/frames/tilemaps/palettes/tags —
with **all referenced assets present and resolvable**, including **non-ASCII**
(accented / CJK / emoji) and **case-distinct** (``Hero.png`` / ``hero.png``) names.

A single CI host cannot run three OSes, so the six ordered OS pairs of the matrix are
**simulated** by exercising the portability-sensitive dimensions the matrix would catch:
POSIX forward-slash internal archive paths (never OS backslashes), UTF-8 text, and
case-distinct names. Per ADR-0037 the contract is **model-equality on import** — not a
byte-identical archive — so equality is asserted on the reconstructed model, using the
deterministic canonical PIO-1 payload. Hypothesis drives the display-name property.

T13B-05.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_export import (
    export_project_bundle,
    import_project_bundle,
)
from pixelart_creator.data.project_io import serialize
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import canonical_json_bytes
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)

#: A deliberately mixed non-ASCII display name: accented Latin, CJK, and an emoji.
NON_ASCII_NAME = "café_日本語_🎨.png"

#: The six ordered OS pairs the CI matrix (REQ-P13-BUILD-001) exercises. The bundle
#: round-trip is OS-independent by construction; parametrising over the pairs documents
#: that the same portability contract holds for every source->target leg.
OS_PAIRS = [
    ("windows", "linux"),
    ("windows", "macos"),
    ("linux", "windows"),
    ("linux", "macos"),
    ("macos", "windows"),
    ("macos", "linux"),
]


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _two_tile_source() -> PixelBuffer:
    src = PixelBuffer(32, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, RED)
    src.fill_rect(16, 0, 16, 16, BLUE)
    return src


def _rich_document() -> Document:
    """A representative project: multi-layer, animated, tilemapped, non-ASCII names."""
    doc = Document(
        8,
        8,
        palette=Palette([RED, GREEN, BLUE]),
        metadata={"author": "José 🎨", "名前": "日本語"},
    )
    doc.frames[0].layers[0].buffer.fill(RED)
    doc.frames[0].layers[0].name = NON_ASCII_NAME
    doc.add_frame().layers[0].buffer.fill(GREEN)
    doc.make_add_tag_command("marche", 0, 1, mode=PlaybackMode.PING_PONG).execute()
    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=1)
    doc.tilesets.append(ts)
    tm = Tilemap(name="Monde_🗺️", tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("sol", opacity=0.75))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2).execute()
    doc.tilemaps.append(tm)
    return doc


def _catalog_with_names(
    names: list[str],
) -> tuple[ContentAddressableStore, AssetCatalog, list[str]]:
    """Return a CAS + catalog whose descriptors carry the given display ``names``."""
    cas = ContentAddressableStore()
    catalog = AssetCatalog()
    ids: list[str] = []
    for index, name in enumerate(names):
        asset_id = f"asset-{index}"
        content_hash = cas.put(f"blob-{index}".encode("utf-8"))
        catalog = catalog.add(
            AssetDescriptor(
                asset_id=asset_id,
                kind=AssetKind.SPRITE,
                name=name,
                content_hash=content_hash,
            )
        )
        ids.append(asset_id)
    return cas, catalog, ids


# --------------------------------------------------------------------------- #
# Portability dimension: POSIX forward-slash internal archive paths            #
# --------------------------------------------------------------------------- #


def test_bundle_uses_only_forward_slash_internal_paths(tmp_path: Path) -> None:
    """Every archive member name uses ``/`` — never an OS backslash (ADR-0037 §1).

    A backslash separator would resolve wrongly on a POSIX host; this is the dimension
    a Windows->Linux matrix leg would otherwise catch.
    """
    cas, catalog, ids = _catalog_with_names(["Hero.png", "hero.png"])
    out = export_project_bundle(_rich_document(), ids, catalog, cas, tmp_path / "b")
    with zipfile.ZipFile(out, mode="r") as archive:
        names = archive.namelist()
    assert names
    for name in names:
        assert "\\" not in name


# --------------------------------------------------------------------------- #
# Model-equal round-trip across every ordered OS pair                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source_os,target_os",
    OS_PAIRS,
    ids=[f"{src}->{dst}" for src, dst in OS_PAIRS],
)
def test_round_trip_is_model_equal_across_os_pairs(
    source_os: str, target_os: str, tmp_path: Path
) -> None:
    """A bundle exported on the source OS imports model-equal on the target OS.

    Model-equality (not byte-identical archives) is the ADR-0037 contract; asserted on
    the deterministic canonical PIO-1 payload of the reconstructed document, plus every
    referenced asset present + resolvable in the fresh target CAS.
    """
    doc = _rich_document()
    cas, catalog, ids = _catalog_with_names([NON_ASCII_NAME, "Hero.png", "hero.png"])
    resolved = {catalog.get(i).content_hash for i in ids}
    out = export_project_bundle(doc, ids, catalog, cas, tmp_path / f"{source_os}")

    fresh = ContentAddressableStore()
    imported_doc, imported_catalog = import_project_bundle(
        out, fresh, tmp_path / f"import-{target_os}"
    )
    # Model-equal project (layers/frames/tilemaps/palettes/tags/metadata).
    assert canonical_json_bytes(serialize(imported_doc)) == canonical_json_bytes(
        serialize(doc)
    )
    # All referenced assets present + resolvable.
    assert sorted(d.asset_id for d in imported_catalog.entries()) == sorted(ids)
    for content_hash in resolved:
        assert fresh.has(content_hash)
        assert fresh.get(content_hash)  # bytes resolvable


# --------------------------------------------------------------------------- #
# Non-ASCII display names survive the round-trip                               #
# --------------------------------------------------------------------------- #


def test_non_ascii_names_preserved_through_round_trip(tmp_path: Path) -> None:
    names = ["café.png", "日本語.png", "art_🎨.png"]
    cas, catalog, ids = _catalog_with_names(names)
    out = export_project_bundle(_rich_document(), ids, catalog, cas, tmp_path / "b")

    fresh = ContentAddressableStore()
    _doc, imported_catalog = import_project_bundle(out, fresh, tmp_path / "imported")
    got = {d.asset_id: d.name for d in imported_catalog.entries()}
    for asset_id, name in zip(ids, names):
        assert got[asset_id] == name


# --------------------------------------------------------------------------- #
# Case-distinct names are preserved (no case-folding collision)                #
# --------------------------------------------------------------------------- #


def test_case_distinct_names_preserved_through_round_trip(tmp_path: Path) -> None:
    """``Hero.png`` and ``hero.png`` remain distinct + both resolvable on import.

    A case-folding import would collapse the pair (the bug a case-sensitive Linux leg
    would surface); the round-trip must keep both.
    """
    cas, catalog, ids = _catalog_with_names(["Hero.png", "hero.png"])
    upper_hash = catalog.get(ids[0]).content_hash
    lower_hash = catalog.get(ids[1]).content_hash
    assert upper_hash != lower_hash  # distinct content -> distinct hash

    out = export_project_bundle(_rich_document(), ids, catalog, cas, tmp_path / "b")
    fresh = ContentAddressableStore()
    _doc, imported_catalog = import_project_bundle(out, fresh, tmp_path / "imported")
    names = {d.asset_id: d.name for d in imported_catalog.entries()}
    assert names[ids[0]] == "Hero.png"
    assert names[ids[1]] == "hero.png"
    assert names[ids[0]] != names[ids[1]]
    assert fresh.get(upper_hash) != fresh.get(lower_hash)


# --------------------------------------------------------------------------- #
# Property: arbitrary unicode display names round-trip faithfully              #
# --------------------------------------------------------------------------- #

_UNICODE_NAME = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "So", "Sm")),
    min_size=1,
    max_size=24,
)


@given(name=_UNICODE_NAME)
def test_unicode_display_name_round_trips(name: str, tmp_path_factory) -> None:
    """Any generated unicode display name survives export->import model-equal."""
    cas, catalog, ids = _catalog_with_names([name])
    out_dir = tmp_path_factory.mktemp("cross-os-prop")
    out = export_project_bundle(_rich_document(), ids, catalog, cas, out_dir / "b")
    fresh = ContentAddressableStore()
    _doc, imported_catalog = import_project_bundle(out, fresh, out_dir / "imported")
    restored = {d.asset_id: d.name for d in imported_catalog.entries()}
    assert restored[ids[0]] == name
