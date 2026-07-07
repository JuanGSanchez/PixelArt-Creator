"""Portable-bundle export / round-trip tests for ``asset_export`` (Slice 13B, no Qt).

Covers REQ-P13-DATA-006 / SC-P13-DATA-006-1 (ADR-0037): a single ``.pixbundle`` file
is **self-contained** — it embeds the ``.pixproj`` project payload AND every referenced
CAS blob, with **no dangling external reference** (every reference resolves inside the
bundle) — and the exporter **reuses the shipped ``asset_export`` reference-set
resolution** (no re-implemented CAS: the bundled blob set is exactly the resolved
reference set, dedup honoured, unreferenced blobs excluded). A project WITH referenced
assets and the empty/no-reference edge both round-trip model-equal on import.

Zero Qt; deterministic; Hypothesis for the blob-set property. T13B-04.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import ASSETS_DIRNAME
from pixelart_creator.data.asset_export import (
    BUNDLE_BLOBS_DIRNAME,
    BUNDLE_MANIFEST_FILENAME,
    BUNDLE_PROJECT_FILENAME,
    BUNDLE_SUFFIX,
    export_project_assets,
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

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _document() -> Document:
    """Return a small multi-frame, tagged, palettised project (deterministic)."""
    doc = Document(6, 4, palette=Palette([RED, GREEN, BLUE]))
    doc.frames[0].layers[0].buffer.fill(RED)
    doc.add_frame().layers[0].buffer.fill(GREEN)
    doc.make_add_tag_command("walk", 0, 1, mode=PlaybackMode.LOOP).execute()
    return doc


def _catalog_with_blobs() -> tuple[ContentAddressableStore, AssetCatalog, dict]:
    """Return a CAS + catalog with three referenced blobs + one unreferenced blob.

    ``a1`` and ``a3`` deliberately reference the **same** bytes so the dedup contract
    (one stored blob per distinct content hash) can be asserted.
    """
    cas = ContentAddressableStore()
    shared = cas.put(b"shared-bytes")
    hashes = {
        "a1": shared,
        "a2": cas.put(b"blob-2"),
        "a3": shared,
        "extra": cas.put(b"never-referenced"),
    }
    catalog = (
        AssetCatalog()
        .add(
            AssetDescriptor(
                asset_id="a1",
                kind=AssetKind.SPRITE,
                name="Hero",
                content_hash=hashes["a1"],
                path="assets/hero.pixproj",
            )
        )
        .add(
            AssetDescriptor(
                asset_id="a2",
                kind=AssetKind.TILESET,
                name="Tiles",
                content_hash=hashes["a2"],
            )
        )
        .add(
            AssetDescriptor(
                asset_id="a3",
                kind=AssetKind.PALETTE,
                name="Pal",
                content_hash=hashes["a3"],
            )
        )
    )
    return cas, catalog, hashes


def _zip_names(bundle: Path) -> list[str]:
    with zipfile.ZipFile(bundle, mode="r") as archive:
        return archive.namelist()


def _blob_hashes_in_bundle(bundle: Path) -> set[str]:
    """Return the set of content hashes embedded under ``blobs/`` in the archive."""
    prefix = f"{BUNDLE_BLOBS_DIRNAME}/"
    return {
        Path(name).stem
        for name in _zip_names(bundle)
        if name.startswith(prefix) and name.endswith(".blob")
    }


# --------------------------------------------------------------------------- #
# One self-contained file with the expected members                           #
# --------------------------------------------------------------------------- #


def test_export_produces_one_pixbundle_file(tmp_path: Path) -> None:
    cas, catalog, _ = _catalog_with_blobs()
    out = export_project_bundle(_document(), ["a1", "a2"], catalog, cas, tmp_path / "b")
    assert out.suffix == BUNDLE_SUFFIX
    assert out.is_file()
    assert zipfile.is_zipfile(out)  # one self-contained archive, not a directory


def test_bundle_replaces_non_pixbundle_suffix(tmp_path: Path) -> None:
    cas, catalog, _ = _catalog_with_blobs()
    out = export_project_bundle(
        _document(), ["a1"], catalog, cas, tmp_path / "project.zip"
    )
    assert out.suffix == BUNDLE_SUFFIX
    assert out.name == "project.pixbundle"


def test_bundle_embeds_manifest_project_and_catalog(tmp_path: Path) -> None:
    cas, catalog, _ = _catalog_with_blobs()
    out = export_project_bundle(_document(), ["a1", "a2"], catalog, cas, tmp_path / "b")
    names = set(_zip_names(out))
    assert BUNDLE_MANIFEST_FILENAME in names
    assert BUNDLE_PROJECT_FILENAME in names
    assert "catalog.json" in names
    assert f"{ASSETS_DIRNAME}/a1.json" in names
    assert f"{ASSETS_DIRNAME}/a2.json" in names


def test_bundle_embeds_the_project_payload_faithfully(tmp_path: Path) -> None:
    """The embedded ``project.pixproj`` is exactly the canonical PIO-1 payload."""
    doc = _document()
    cas, catalog, _ = _catalog_with_blobs()
    out = export_project_bundle(doc, ["a1"], catalog, cas, tmp_path / "b")
    with zipfile.ZipFile(out, mode="r") as archive:
        embedded = archive.read(BUNDLE_PROJECT_FILENAME)
    assert embedded == canonical_json_bytes(serialize(doc))


# --------------------------------------------------------------------------- #
# Every referenced blob is embedded — no dangling external reference           #
# --------------------------------------------------------------------------- #


def test_bundle_embeds_every_referenced_blob(tmp_path: Path) -> None:
    cas, catalog, h = _catalog_with_blobs()
    out = export_project_bundle(_document(), ["a1", "a2"], catalog, cas, tmp_path / "b")
    embedded = _blob_hashes_in_bundle(out)
    assert h["a1"] in embedded
    assert h["a2"] in embedded


def test_bundle_has_no_dangling_external_reference(tmp_path: Path) -> None:
    """Every catalog reference resolves to a blob INSIDE the bundle (self-contained)."""
    cas, catalog, _ = _catalog_with_blobs()
    out = export_project_bundle(
        _document(), ["a1", "a2", "a3"], catalog, cas, tmp_path / "b"
    )
    embedded = _blob_hashes_in_bundle(out)
    # Read the bundled catalog and prove every referenced content hash is present.
    fresh = ContentAddressableStore()
    document, imported_catalog = import_project_bundle(
        out, fresh, tmp_path / "imported"
    )
    assert document is not None
    for descriptor in imported_catalog.entries():
        assert descriptor.content_hash in embedded  # no external dependency


def test_bundled_blob_set_equals_resolved_reference_set(tmp_path: Path) -> None:
    """The exporter reuses the shipped reference resolution: blobs == resolved refs.

    Proves no re-implemented CAS: the embedded blob set is EXACTLY the set the shipped
    ``export_project_assets`` reference resolution produces — the unreferenced blob is
    excluded and the two references to shared bytes dedup to a single blob.
    """
    cas, catalog, h = _catalog_with_blobs()
    reference_ids = ["a1", "a2", "a3"]
    out = export_project_bundle(
        _document(), reference_ids, catalog, cas, tmp_path / "b"
    )
    embedded = _blob_hashes_in_bundle(out)
    resolved = {catalog.get(i).content_hash for i in reference_ids}
    assert embedded == resolved
    # a1 and a3 share bytes -> exactly one blob, not two (dedup).
    assert h["a1"] == h["a3"]
    assert len(embedded) == 2
    # The unreferenced blob is never bundled.
    assert h["extra"] not in embedded


def test_export_bundle_matches_shipped_directory_reference_resolution(
    tmp_path: Path,
) -> None:
    """The single-file blob set equals the shipped directory exporter's blob set.

    Cross-checks that ``export_project_bundle`` composes ``export_project_assets`` (the
    shipped reference-set resolution) rather than re-deriving the CAS contents.
    """
    cas, catalog, _ = _catalog_with_blobs()
    reference_ids = ["a1", "a2", "a3"]
    out = export_project_bundle(
        _document(), reference_ids, catalog, cas, tmp_path / "b"
    )
    bundle_blobs = _blob_hashes_in_bundle(out)

    directory = tmp_path / "dir-bundle"
    export_project_assets(reference_ids, catalog, cas, directory)
    directory_blobs = {
        p.stem for p in (directory / BUNDLE_BLOBS_DIRNAME).glob("*.blob")
    }
    assert bundle_blobs == directory_blobs


# --------------------------------------------------------------------------- #
# Round-trip (with references) and the empty/no-reference edge                 #
# --------------------------------------------------------------------------- #


def test_export_import_round_trip_with_references(tmp_path: Path) -> None:
    doc = _document()
    cas, catalog, h = _catalog_with_blobs()
    out = export_project_bundle(doc, ["a1", "a2"], catalog, cas, tmp_path / "b")

    fresh = ContentAddressableStore()
    imported_doc, imported_catalog = import_project_bundle(
        out, fresh, tmp_path / "imported"
    )
    # Model-equal project.
    assert canonical_json_bytes(serialize(imported_doc)) == canonical_json_bytes(
        serialize(doc)
    )
    # Every referenced asset present + resolvable in the fresh CAS.
    assert sorted(d.asset_id for d in imported_catalog.entries()) == ["a1", "a2"]
    assert fresh.get(h["a1"]) == b"shared-bytes"
    assert fresh.get(h["a2"]) == b"blob-2"


def test_export_import_empty_reference_edge(tmp_path: Path) -> None:
    """A project with NO referenced assets still bundles + round-trips intact."""
    doc = _document()
    cas = ContentAddressableStore()
    catalog = AssetCatalog()
    out = export_project_bundle(doc, [], catalog, cas, tmp_path / "empty")
    assert out.is_file()
    # No blobs embedded, but the payload + manifest + catalog are.
    assert _blob_hashes_in_bundle(out) == set()
    names = set(_zip_names(out))
    assert BUNDLE_PROJECT_FILENAME in names
    assert BUNDLE_MANIFEST_FILENAME in names

    fresh = ContentAddressableStore()
    imported_doc, imported_catalog = import_project_bundle(
        out, fresh, tmp_path / "imported"
    )
    assert list(imported_catalog.entries()) == []
    assert canonical_json_bytes(serialize(imported_doc)) == canonical_json_bytes(
        serialize(doc)
    )


# --------------------------------------------------------------------------- #
# Property: the embedded blob set is always exactly the resolved reference set  #
# --------------------------------------------------------------------------- #


@given(subset=st.lists(st.sampled_from(["a1", "a2", "a3"]), max_size=6))
def test_blob_set_always_equals_resolved_reference_set(
    subset: list[str], tmp_path_factory
) -> None:
    """Over any (deduped) reference subset, embedded blobs == resolved reference set."""
    cas, catalog, _ = _catalog_with_blobs()
    out_dir = tmp_path_factory.mktemp("bundle-prop")
    out = export_project_bundle(_document(), subset, catalog, cas, out_dir / "b")
    embedded = _blob_hashes_in_bundle(out)
    resolved = {catalog.get(i).content_hash for i in set(subset)}
    assert embedded == resolved
