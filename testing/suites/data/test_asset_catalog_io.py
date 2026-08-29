"""Unit tests for :mod:`pixelart_creator.data.asset_catalog_io` (S11, no Qt).

Covers catalog/sidecar persistence + the PIO-1 payload composition (ADR-0030 §1/§2;
REQ-P11-DATA-001/-002/-003/-007): catalog round-trip, ``store_asset``/``load_asset``
via the shipped PIO-1 serialiser (no second serialiser) with content-hash dedup, and
the Article VII UNTRUSTED-load defence — JSON-only, schema+caps rejection of malformed/
oversized/wrong-type input, metadata scalar guard, and that ``AssetCatalogError`` is a
``ProjectIOError`` subclass. Path-traversal rejection lives in ``test_asset_paths.py``.
T11-1-10.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import asset_catalog_io as cio
from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import (
    AssetCatalogError,
    load_asset,
    load_catalog,
    save_catalog,
    store_asset,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import content_hash
from pixelart_creator.logic.document import Document

HASH_A = content_hash(b"a")
HASH_B = content_hash(b"b")


def descriptor(asset_id="asset-1", **kwargs) -> AssetDescriptor:
    fields = dict(
        asset_id=asset_id,
        kind=AssetKind.SPRITE,
        name="Hero",
        content_hash=HASH_A,
    )
    fields.update(kwargs)
    return AssetDescriptor(**fields)


# --------------------------------------------------------------------------- #
# AssetCatalogError is a ProjectIOError (PIO-1 family)                          #
# --------------------------------------------------------------------------- #


def test_asset_catalog_error_is_project_io_error() -> None:
    assert issubclass(AssetCatalogError, ProjectIOError)


# --------------------------------------------------------------------------- #
# save_catalog / load_catalog round-trip                                       #
# --------------------------------------------------------------------------- #


def test_catalog_roundtrip_preserves_entries(tmp_path) -> None:
    catalog = (
        AssetCatalog()
        .add(
            descriptor(
                asset_id="a",
                tags=frozenset({"hero"}),
                metadata={"author": "j", "frames": 4},
                path="assets/a.pixproj",
            )
        )
        .add(descriptor(asset_id="b", kind=AssetKind.TILESET, name="Tiles"))
    )
    save_catalog(catalog, tmp_path)
    reloaded = load_catalog(tmp_path)
    assert [d.asset_id for d in reloaded.entries()] == ["a", "b"]
    a = reloaded.get("a")
    assert a is not None
    assert a.tags == frozenset({"hero"})
    assert dict(a.metadata) == {"author": "j", "frames": 4}
    assert reloaded.get("b").kind is AssetKind.TILESET


def test_save_rejects_non_catalog(tmp_path) -> None:
    with pytest.raises(AssetCatalogError):
        save_catalog("not-a-catalog", tmp_path)  # type: ignore[arg-type]


def test_save_wraps_mkdir_os_error(tmp_path) -> None:
    blocker = tmp_path / "file"
    blocker.write_bytes(b"x")
    with pytest.raises(AssetCatalogError):
        save_catalog(AssetCatalog(), blocker / "under-a-file")


def test_save_wraps_sidecar_write_os_error(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    def boom(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(AssetCatalogError):
        save_catalog(AssetCatalog().add(descriptor(asset_id="a")), tmp_path)


def test_save_wraps_index_write_os_error(tmp_path, monkeypatch) -> None:
    from pathlib import Path

    def boom(self, *args, **kwargs):
        raise OSError("disk full")

    # Empty catalog writes no sidecars, so the failure is the index write.
    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(AssetCatalogError):
        save_catalog(AssetCatalog(), tmp_path)


# --------------------------------------------------------------------------- #
# load_catalog — untrusted-input defence (index level)                         #
# --------------------------------------------------------------------------- #


def _write_index(root, obj) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / cio.INDEX_FILENAME).write_text(json.dumps(obj), encoding="utf-8")


def test_load_missing_index_raises(tmp_path) -> None:
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_index_not_json_raises(tmp_path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / cio.INDEX_FILENAME).write_text("{not json", encoding="utf-8")
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_index_not_object_raises(tmp_path) -> None:
    _write_index(tmp_path, ["not", "an", "object"])
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_wrong_format_raises(tmp_path) -> None:
    _write_index(tmp_path, {"format": "other", "schema_version": "1", "asset_ids": []})
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_unsupported_schema_version_raises(tmp_path) -> None:
    _write_index(
        tmp_path,
        {"format": cio.FORMAT_NAME, "schema_version": "999", "asset_ids": []},
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_asset_ids_not_list_raises(tmp_path) -> None:
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": "nope",
        },
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_over_max_catalog_assets_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cio, "MAX_CATALOG_ASSETS", 1)
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": ["a", "b"],
        },
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_non_str_asset_id_raises(tmp_path) -> None:
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": [123],
        },
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_missing_sidecar_raises(tmp_path) -> None:
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": ["ghost"],
        },
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_load_duplicate_id_wrapped(tmp_path, monkeypatch) -> None:
    # Two index entries pointing at the same valid sidecar -> AssetCatalog rejects
    # the duplicate id; the loader wraps AssetCatalogModelError as AssetCatalogError.
    save_catalog(AssetCatalog().add(descriptor(asset_id="a")), tmp_path)
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": ["a", "a"],
        },
    )
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


# --------------------------------------------------------------------------- #
# Sidecar-level defence (via a crafted sidecar)                                #
# --------------------------------------------------------------------------- #


def _write_sidecar(tmp_path, asset_id, payload) -> None:
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": [asset_id],
        },
    )
    assets = tmp_path / cio.ASSETS_DIRNAME
    assets.mkdir(parents=True, exist_ok=True)
    (assets / f"{asset_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _good_sidecar(asset_id="a"):
    return {
        "asset_id": asset_id,
        "kind": "sprite",
        "name": "Hero",
        "content_hash": HASH_A,
        "tags": [],
        "metadata": {},
        "path": None,
    }


def test_sidecar_roundtrip_via_crafted(tmp_path) -> None:
    _write_sidecar(tmp_path, "a", _good_sidecar())
    reloaded = load_catalog(tmp_path)
    assert reloaded.get("a").name == "Hero"


def test_sidecar_not_object_raises(tmp_path) -> None:
    _write_sidecar(tmp_path, "a", ["not", "an", "object"])
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_missing_asset_id_raises(tmp_path) -> None:
    bad = _good_sidecar()
    del bad["asset_id"]
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_missing_name_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["name"] = ""
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_invalid_content_hash_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["content_hash"] = "not-a-hash"
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_unknown_kind_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["kind"] = "unknown-kind"
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_non_str_kind_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["kind"] = 5
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_tags_not_list_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["tags"] = "hero"
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_tag_not_str_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["tags"] = [5]
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_metadata_not_object_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["metadata"] = ["nope"]
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_metadata_key_not_str_raises(tmp_path) -> None:
    # JSON object keys are always strings, so inject via a crafted raw file.
    _write_index(
        tmp_path,
        {
            "format": cio.FORMAT_NAME,
            "schema_version": cio.CATALOG_SCHEMA_VERSION,
            "asset_ids": ["a"],
        },
    )
    assets = tmp_path / cio.ASSETS_DIRNAME
    assets.mkdir(parents=True, exist_ok=True)
    # metadata with a non-scalar value trips the descriptor's scalar guard.
    payload = _good_sidecar()
    payload["metadata"] = {"nested": {"deep": 1}}
    (assets / "a.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


def test_sidecar_path_not_str_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["path"] = 123
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)


# --------------------------------------------------------------------------- #
# store_asset / load_asset — PIO-1 composition (no second serialiser)          #
# --------------------------------------------------------------------------- #


def test_store_then_load_asset_reconstructs_equivalent_document() -> None:
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.set_pixel(1, 1, (255, 0, 0, 255))
    cas = ContentAddressableStore()
    catalog, desc = store_asset(
        doc,
        AssetCatalog(),
        cas,
        asset_id="sprite-1",
        kind=AssetKind.SPRITE,
        name="Hero",
        tags=["hero"],
        metadata={"frames": 1},
    )
    assert desc.asset_id == "sprite-1"
    assert catalog.get("sprite-1") is desc
    reloaded = load_asset(desc, cas)
    assert reloaded.width == 4 and reloaded.height == 4
    assert reloaded.frames[0].layers[0].buffer.get_pixel(1, 1) == (255, 0, 0, 255)


def test_store_identical_documents_dedup_to_same_hash() -> None:
    cas = ContentAddressableStore()
    catalog = AssetCatalog()
    doc1 = Document(2, 2)
    doc2 = Document(2, 2)
    catalog, d1 = store_asset(
        doc1, catalog, cas, asset_id="a", kind=AssetKind.SPRITE, name="A"
    )
    catalog, d2 = store_asset(
        doc2, catalog, cas, asset_id="b", kind=AssetKind.SPRITE, name="B"
    )
    assert d1.content_hash == d2.content_hash  # identical payload -> one blob


def test_store_asset_duplicate_id_raises() -> None:
    cas = ContentAddressableStore()
    catalog, _ = store_asset(
        Document(2, 2),
        AssetCatalog(),
        cas,
        asset_id="a",
        kind=AssetKind.SPRITE,
        name="A",
    )
    with pytest.raises(AssetCatalogError):
        store_asset(
            Document(3, 3),
            catalog,
            cas,
            asset_id="a",
            kind=AssetKind.SPRITE,
            name="Dup",
        )


def test_load_asset_rejects_non_descriptor() -> None:
    with pytest.raises(AssetCatalogError):
        load_asset("nope", ContentAddressableStore())  # type: ignore[arg-type]


def test_load_asset_rejects_non_json_payload() -> None:
    cas = ContentAddressableStore()
    digest = cas.put(b"\xff\xfe not json at all")
    desc = descriptor(asset_id="x", content_hash=digest)
    with pytest.raises(AssetCatalogError):
        load_asset(desc, cas)


# --------------------------------------------------------------------------- #
# reference_key persistence (T17-A, ruling P11-R8, plan §3.10) — additive     #
# append per the T17-A dispatch                                               #
# --------------------------------------------------------------------------- #


def test_catalog_roundtrip_preserves_reference_key(tmp_path) -> None:
    """T17-A Done-when #5: a descriptor with a non-empty ``reference_key``
    round-trips through ``save_catalog``/``load_catalog``."""
    ref_key = content_hash(b"the reference-candidate bytes")
    catalog = AssetCatalog().add(
        descriptor(
            asset_id="a",
            kind=AssetKind.TILESET,
            reference_key=ref_key,
        )
    )
    save_catalog(catalog, tmp_path)
    reloaded = load_catalog(tmp_path)
    entry = reloaded.get("a")
    assert entry is not None
    assert entry.reference_key == ref_key


def test_catalog_roundtrip_preserves_default_empty_reference_key(tmp_path) -> None:
    """A descriptor whose ``reference_key`` was never set (the default ``""``,
    e.g. a kind that is never a reference target) round-trips as ``""``, not
    as a missing field or ``None``."""
    catalog = AssetCatalog().add(descriptor(asset_id="a"))
    save_catalog(catalog, tmp_path)
    reloaded = load_catalog(tmp_path)
    assert reloaded.get("a").reference_key == ""


def test_sidecar_written_by_current_code_carries_reference_key_key(tmp_path) -> None:
    """The sidecar JSON on disk actually carries the ``"reference_key"`` key
    (not just that the round trip happens to work) — proves
    ``_serialise_descriptor`` writes it, not merely that ``_parse_descriptor``
    tolerates its absence."""
    ref_key = content_hash(b"sidecar content")
    catalog = AssetCatalog().add(
        descriptor(asset_id="a", kind=AssetKind.SPRITE, reference_key=ref_key)
    )
    save_catalog(catalog, tmp_path)
    raw = json.loads(
        (tmp_path / cio.ASSETS_DIRNAME / "a.json").read_text(encoding="utf-8")
    )
    assert raw["reference_key"] == ref_key


def test_sidecar_without_reference_key_parses_as_empty_string(tmp_path) -> None:
    """T17-A Done-when #5: a sidecar written **before** ``reference_key``
    existed (no such key at all in its JSON — the pre-T8-B shape) parses
    with ``reference_key == ""`` and raises nothing — the backward-compat
    read path, no schema bump (T8-B report, measured: ``payload.get(...)``
    already tolerated unknown/absent keys)."""
    pre_reference_key_sidecar = _good_sidecar()
    assert "reference_key" not in pre_reference_key_sidecar  # the pre-T8-B shape
    _write_sidecar(tmp_path, "a", pre_reference_key_sidecar)

    reloaded = load_catalog(tmp_path)

    entry = reloaded.get("a")
    assert entry is not None
    assert entry.reference_key == ""


def test_sidecar_reference_key_not_str_raises(tmp_path) -> None:
    bad = _good_sidecar()
    bad["reference_key"] = 123
    _write_sidecar(tmp_path, "a", bad)
    with pytest.raises(AssetCatalogError):
        load_catalog(tmp_path)
