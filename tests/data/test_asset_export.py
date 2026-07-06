"""Unit tests for ``pixelart_creator.data.asset_export`` (S11, no Qt).

Covers cross-project reuse export (ADR-0030 §5; REQ-P11-DATA-005): export bundles
EXACTLY the blobs a project's references resolve to (not the whole CAS); the artifact
opens self-contained on a fresh CAS; import is defended against a path-traversal entry
(``..`` / absolute) and against oversized / malformed input, raising
``AssetExportError`` (a ``ProjectIOError`` subclass); the advisory path is dropped so
the bundle is relocatable; and the module uses no ``eval``/``exec``/``pickle``.
T11-3-07.
"""

from __future__ import annotations

import ast
import json

import pytest

from pixelart_creator.data import asset_export
from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import ASSETS_DIRNAME
from pixelart_creator.data.asset_export import (
    BUNDLE_BLOBS_DIRNAME,
    AssetExportError,
    _resolve_within,
    export_project_assets,
    import_project_assets,
)
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)


def _fixture() -> tuple[ContentAddressableStore, AssetCatalog, dict]:
    """Return a CAS + catalog with three referenced blobs and one unreferenced blob."""
    cas = ContentAddressableStore()
    hashes = {
        "a1": cas.put(b"blob-1"),
        "a2": cas.put(b"blob-2"),
        "a3": cas.put(b"blob-3"),
    }
    # An extra blob NOT referenced by any exported id (must never be bundled).
    hashes["extra"] = cas.put(b"unreferenced-blob")
    catalog = (
        AssetCatalog()
        .add(
            AssetDescriptor(
                asset_id="a1",
                kind=AssetKind.SPRITE,
                name="A1",
                content_hash=hashes["a1"],
                path="assets/a1.pixproj",
            )
        )
        .add(
            AssetDescriptor(
                asset_id="a2",
                kind=AssetKind.TILESET,
                name="A2",
                content_hash=hashes["a2"],
            )
        )
        .add(
            AssetDescriptor(
                asset_id="a3",
                kind=AssetKind.PALETTE,
                name="A3",
                content_hash=hashes["a3"],
            )
        )
    )
    return cas, catalog, hashes


# --------------------------------------------------------------------------- #
# AssetExportError is a ProjectIOError                                          #
# --------------------------------------------------------------------------- #


def test_asset_export_error_is_project_io_error() -> None:
    assert issubclass(AssetExportError, ProjectIOError)


# --------------------------------------------------------------------------- #
# Export bundles EXACTLY the referenced blobs (not the whole CAS)              #
# --------------------------------------------------------------------------- #


def test_export_bundles_exactly_the_referenced_blobs(tmp_path) -> None:
    cas, catalog, h = _fixture()
    out = tmp_path / "bundle"
    export_project_assets(["a1", "a2"], catalog, cas, out)

    bundle_cas = ContentAddressableStore(
        LocalBlobBackend(root=out / BUNDLE_BLOBS_DIRNAME)
    )
    # Exactly the two referenced blobs are present.
    assert bundle_cas.has(h["a1"]) is True
    assert bundle_cas.has(h["a2"]) is True
    # The third catalog asset and the unreferenced blob are NOT bundled.
    assert bundle_cas.has(h["a3"]) is False
    assert bundle_cas.has(h["extra"]) is False


def test_export_drops_advisory_path_for_relocatability(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    out = tmp_path / "bundle"
    export_project_assets(["a1"], catalog, cas, out)
    sidecar = json.loads((out / ASSETS_DIRNAME / "a1.json").read_text(encoding="utf-8"))
    assert sidecar["path"] is None  # advisory path dropped -> self-contained


# --------------------------------------------------------------------------- #
# The artifact opens self-contained                                            #
# --------------------------------------------------------------------------- #


def test_exported_bundle_imports_self_contained(tmp_path) -> None:
    cas, catalog, h = _fixture()
    out = tmp_path / "bundle"
    export_project_assets(["a1", "a2"], catalog, cas, out)

    fresh = ContentAddressableStore()
    imported = import_project_assets(out, fresh)
    assert sorted(d.asset_id for d in imported.entries()) == ["a1", "a2"]
    # The referenced bytes are now resident in the fresh CAS (verified fetch).
    assert fresh.get(h["a1"]) == b"blob-1"
    assert fresh.get(h["a2"]) == b"blob-2"


# --------------------------------------------------------------------------- #
# Import defence — path traversal, malformed, oversized, missing blob          #
# --------------------------------------------------------------------------- #


def test_import_rejects_path_traversal_sidecar(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    out = tmp_path / "bundle"
    export_project_assets(["a1"], catalog, cas, out)
    # Poison the sidecar's advisory path so it escapes the bundle root.
    sidecar_path = out / ASSETS_DIRNAME / "a1.json"
    data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    data["path"] = "../../escape.pixproj"
    sidecar_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssetExportError):
        import_project_assets(out, ContentAddressableStore())


def test_import_rejects_malformed_bundle(tmp_path) -> None:
    # A directory with no catalog index is malformed input.
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(AssetExportError):
        import_project_assets(empty, ContentAddressableStore())


def test_import_rejects_missing_blob(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    out = tmp_path / "bundle"
    export_project_assets(["a1"], catalog, cas, out)
    # Remove the bundled blob so the referenced content is unresolvable on import.
    for blob_file in (out / BUNDLE_BLOBS_DIRNAME).iterdir():
        blob_file.unlink()
    with pytest.raises(AssetExportError):
        import_project_assets(out, ContentAddressableStore())


def test_import_rejects_non_cas() -> None:
    with pytest.raises(AssetExportError):
        import_project_assets("bundle", "not-a-cas")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Export input defence                                                         #
# --------------------------------------------------------------------------- #


def test_export_rejects_non_catalog(tmp_path) -> None:
    cas = ContentAddressableStore()
    with pytest.raises(AssetExportError):
        export_project_assets(
            ["a1"], "not-a-catalog", cas, tmp_path / "b"  # type: ignore[arg-type]
        )


def test_export_rejects_non_cas(tmp_path) -> None:
    with pytest.raises(AssetExportError):
        export_project_assets(
            ["a1"],
            AssetCatalog(),
            "not-a-cas",  # type: ignore[arg-type]
            tmp_path / "b",
        )


def test_export_rejects_reference_ids_as_string(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    # A bare string is a common mistake for a sequence of ids -> rejected.
    with pytest.raises(AssetExportError):
        export_project_assets(
            "a1", catalog, cas, tmp_path / "b"  # type: ignore[arg-type]
        )


def test_export_rejects_non_str_reference_id(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    with pytest.raises(AssetExportError):
        export_project_assets(
            [123], catalog, cas, tmp_path / "b"  # type: ignore[list-item]
        )


def test_export_rejects_unhashable_reference_id(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    with pytest.raises(AssetExportError):
        export_project_assets(
            [["nested"]], catalog, cas, tmp_path / "b"  # type: ignore[list-item]
        )


def test_export_rejects_over_cap_reference_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(asset_export, "MAX_CATALOG_ASSETS", 1)
    cas, catalog, _ = _fixture()
    with pytest.raises(AssetExportError):
        export_project_assets(["a1", "a2"], catalog, cas, tmp_path / "b")


def test_export_rejects_reference_not_in_catalog(tmp_path) -> None:
    cas, catalog, _ = _fixture()
    with pytest.raises(AssetExportError):
        export_project_assets(["ghost"], catalog, cas, tmp_path / "b")


def test_export_rejects_missing_blob_in_cas(tmp_path) -> None:
    # A catalog descriptor whose content_hash is not in the source CAS cannot resolve.
    from pixelart_creator.logic.content_hash import content_hash

    cas = ContentAddressableStore()
    dangling = content_hash(b"never-stored")
    catalog = AssetCatalog().add(
        AssetDescriptor(
            asset_id="a4", kind=AssetKind.SPRITE, name="A4", content_hash=dangling
        )
    )
    with pytest.raises(AssetExportError):
        export_project_assets(["a4"], catalog, cas, tmp_path / "b")


def test_export_wraps_mkdir_os_error(tmp_path) -> None:
    # A file where the export root must be created -> mkdir fails, wrapped.
    cas, catalog, _ = _fixture()
    blocker = tmp_path / "file"
    blocker.write_bytes(b"x")
    with pytest.raises(AssetExportError):
        export_project_assets(["a1"], catalog, cas, blocker / "under-a-file")


# --------------------------------------------------------------------------- #
# _resolve_within — the bundle containment guard                               #
# --------------------------------------------------------------------------- #


def test_resolve_within_accepts_contained(tmp_path) -> None:
    resolved = _resolve_within(tmp_path, BUNDLE_BLOBS_DIRNAME)
    assert resolved == tmp_path.resolve() / BUNDLE_BLOBS_DIRNAME


def test_resolve_within_rejects_escape(tmp_path) -> None:
    with pytest.raises(AssetExportError):
        _resolve_within(tmp_path, "../evil")


# --------------------------------------------------------------------------- #
# No eval/exec/pickle (source scan)                                            #
# --------------------------------------------------------------------------- #


def test_module_uses_no_eval_exec_or_pickle() -> None:
    with open(asset_export.__file__, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec"}
        if isinstance(node, ast.Import):
            assert all(alias.name != "pickle" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module != "pickle"
