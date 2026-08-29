"""Portable-bundle import-defence tests (Slice 13B, Article VII, no Qt).

Covers REQ-P13-DATA-008 / SC-P13-DATA-008-1 and -008-2 (ADR-0037 §2): the ``.pixbundle``
importer treats its input as **fully untrusted** and

* rejects a **traversal-crafted** bundle — an entry with ``../``, an absolute path, a
  backslash/symlink escape — raising :class:`AssetExportError` and writing **nothing**
  outside the import target (target dir + its parent stay unpolluted);
* rejects an **oversized** bundle — over ``MAX_BUNDLE_BYTES`` / ``MAX_BUNDLE_ENTRIES`` /
  ``MAX_BUNDLE_ENTRY_BYTES`` (incl. a **lying header** vs streamed content) — with no
  partial write;
* rejects a **malformed / unknown-``schema_version``** bundle;
* rejects a **hash-mismatch** blob;
* is proven **``eval``/``exec``-free** on the import path by a source audit.

Malicious archives are hand-crafted with stdlib :mod:`zipfile`. T13B-06.
"""

from __future__ import annotations

import ast
import inspect
import json
import stat
import zipfile
from pathlib import Path

import pytest

from pixelart_creator.data import asset_export
from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_export import (
    BUNDLE_BLOBS_DIRNAME,
    BUNDLE_MANIFEST_FILENAME,
    BUNDLE_PROJECT_FILENAME,
    AssetExportError,
    _extract_member_streamed,
    export_project_bundle,
    import_project_bundle,
)
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.document import Document

RED = (255, 0, 0, 255)


# --------------------------------------------------------------------------- #
# Fixtures + archive-crafting helpers                                          #
# --------------------------------------------------------------------------- #


def _document() -> Document:
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.fill(RED)
    return doc


def _valid_fixture() -> tuple[ContentAddressableStore, AssetCatalog, list[str]]:
    cas = ContentAddressableStore()
    content_hash = cas.put(b"asset-bytes")
    catalog = AssetCatalog().add(
        AssetDescriptor(
            asset_id="a1",
            kind=AssetKind.SPRITE,
            name="Hero",
            content_hash=content_hash,
        )
    )
    return cas, catalog, ["a1"]


def _valid_bundle(dest: Path) -> Path:
    """Write a genuine ``.pixbundle`` and return its path."""
    cas, catalog, ids = _valid_fixture()
    return export_project_bundle(_document(), ids, catalog, cas, dest)


def _read_members(bundle: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(bundle, mode="r") as archive:
        return {
            info.filename: archive.read(info.filename) for info in archive.infolist()
        }


def _write_members(
    dest: Path,
    members: dict[str, bytes],
    *,
    symlink_names: frozenset[str] = frozenset(),
) -> Path:
    """Write ``members`` (name -> bytes) into a zip at ``dest`` and return it.

    Names in ``symlink_names`` are stamped with symlink mode bits so the importer's
    "regular files only, no symlink" guarantee can be exercised.
    """
    with zipfile.ZipFile(dest, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            info = zipfile.ZipInfo(filename=name)
            info.compress_type = zipfile.ZIP_DEFLATED
            if name in symlink_names:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            else:
                info.external_attr = 0o644 << 16
            archive.writestr(info, payload)
    return dest


def _import(bundle: Path, target: Path) -> None:
    import_project_bundle(bundle, ContentAddressableStore(), target)


# --------------------------------------------------------------------------- #
# Traversal / zip-slip rejection — nothing written outside the target          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "evil_name",
    [
        "../escape.txt",
        "sub/../../escape.txt",
        "/abs/escape.txt",
        "..\\escape.txt",  # portability: ok (intentional malicious backslash payload)
        "sub\\nested.txt",  # portability: ok (intentional malicious backslash payload)
    ],
    ids=["dotdot", "nested-dotdot", "absolute", "backslash-dotdot", "backslash"],
)
def test_traversal_entry_rejected_no_pollution(evil_name: str, tmp_path: Path) -> None:
    """A traversal/zip-slip entry is rejected; the target parent stays unpolluted."""
    workdir = tmp_path / "work"
    workdir.mkdir()
    target = workdir / "imported"
    bundle = _write_members(tmp_path / "evil.pixbundle", {evil_name: b"pwned"})

    before = sorted(p.name for p in workdir.iterdir())
    with pytest.raises(AssetExportError):
        _import(bundle, target)

    # Nothing written at or outside the target.
    assert not target.exists()
    assert sorted(p.name for p in workdir.iterdir()) == before
    # The traversal destination (one level up from the scratch dir) was never written.
    assert not (tmp_path / "escape.txt").exists()


def test_symlink_entry_creates_no_symlink_and_writes_nothing(tmp_path: Path) -> None:
    """A symlink-attributed member never yields a symlink and pollutes nothing.

    The importer writes members as regular files only (no ``os.symlink``); this entry
    is safe-named so it extracts, but the bundle is otherwise incomplete so the import
    is rejected — leaving no target and no symlink anywhere.
    """
    workdir = tmp_path / "work"
    workdir.mkdir()
    target = workdir / "imported"
    bundle = _write_members(
        tmp_path / "link.pixbundle",
        {f"{BUNDLE_BLOBS_DIRNAME}/evil": b"/etc/passwd"},
        symlink_names=frozenset({f"{BUNDLE_BLOBS_DIRNAME}/evil"}),
    )
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()
    # No symlink materialised anywhere under the work dir.
    for path in workdir.rglob("*"):
        assert not path.is_symlink()


def test_existing_target_is_refused(tmp_path: Path) -> None:
    bundle = _valid_bundle(tmp_path / "b")
    target = tmp_path / "already"
    target.mkdir()
    with pytest.raises(AssetExportError):
        _import(bundle, target)


# --------------------------------------------------------------------------- #
# Size / count caps — oversized, too-many, header cap, lying-header stream cap  #
# --------------------------------------------------------------------------- #


def test_oversized_total_bytes_rejected(tmp_path: Path, monkeypatch) -> None:
    bundle = _valid_bundle(tmp_path / "b")
    monkeypatch.setattr(asset_export, "MAX_BUNDLE_BYTES", 4)  # smaller than any bundle
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()  # no partial write


def test_too_many_entries_rejected(tmp_path: Path, monkeypatch) -> None:
    bundle = _valid_bundle(tmp_path / "b")
    monkeypatch.setattr(asset_export, "MAX_BUNDLE_ENTRIES", 1)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_entry_header_size_cap_rejected(tmp_path: Path, monkeypatch) -> None:
    """A member whose declared (header) uncompressed size over the cap is rejected."""
    bundle = _valid_bundle(tmp_path / "b")
    monkeypatch.setattr(asset_export, "MAX_BUNDLE_ENTRY_BYTES", 2)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_streamed_extraction_cap_catches_lying_header(
    tmp_path: Path, monkeypatch
) -> None:
    """The per-entry cap is re-enforced mid-stream, so a lying header cannot slip past.

    Exercises the streamed-extraction guard directly: with the cap set below the
    member's true size, ``_extract_member_streamed`` aborts before finishing the write
    (a header under-reporting its size cannot exhaust memory/disk), leaving no complete
    file at the destination.
    """
    payload = b"x" * 4096
    archive_path = _write_members(tmp_path / "big.zip", {"blobs/big.blob": payload})
    monkeypatch.setattr(asset_export, "MAX_BUNDLE_ENTRY_BYTES", 64)
    dest = tmp_path / "out.blob"
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        info = archive.getinfo("blobs/big.blob")
        with pytest.raises(AssetExportError):
            _extract_member_streamed(archive, info, dest)
    # The streamed write was aborted before the full payload landed.
    assert not dest.exists() or dest.stat().st_size < len(payload)


# --------------------------------------------------------------------------- #
# Malformed / unknown-version / not-a-zip                                       #
# --------------------------------------------------------------------------- #


def test_not_a_zip_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "garbage.pixbundle"
    bundle.write_bytes(b"this is not a zip archive at all")
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_missing_manifest_rejected(tmp_path: Path) -> None:
    members = _read_members(_valid_bundle(tmp_path / "b"))
    members.pop(BUNDLE_MANIFEST_FILENAME)
    bundle = _write_members(tmp_path / "no-manifest.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_unknown_schema_version_rejected(tmp_path: Path) -> None:
    members = _read_members(_valid_bundle(tmp_path / "b"))
    members[BUNDLE_MANIFEST_FILENAME] = json.dumps(
        {"format": "pixbundle", "schema_version": "999"}
    ).encode("utf-8")
    bundle = _write_members(tmp_path / "bad-version.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_malformed_manifest_json_rejected(tmp_path: Path) -> None:
    members = _read_members(_valid_bundle(tmp_path / "b"))
    members[BUNDLE_MANIFEST_FILENAME] = b"{not valid json"
    bundle = _write_members(tmp_path / "bad-manifest.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


def test_malformed_project_payload_rejected(tmp_path: Path) -> None:
    members = _read_members(_valid_bundle(tmp_path / "b"))
    members[BUNDLE_PROJECT_FILENAME] = b"not a json payload"
    bundle = _write_members(tmp_path / "bad-project.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


# --------------------------------------------------------------------------- #
# Content-hash tamper defence                                                   #
# --------------------------------------------------------------------------- #


def test_hash_mismatch_blob_rejected(tmp_path: Path) -> None:
    """A blob whose bytes no longer match its content-hash key is rejected."""
    members = _read_members(_valid_bundle(tmp_path / "b"))
    blob_names = [n for n in members if n.startswith(f"{BUNDLE_BLOBS_DIRNAME}/")]
    assert blob_names  # sanity: the fixture bundles a blob
    for name in blob_names:
        members[name] = b"tampered-content-that-does-not-match-the-hash"
    bundle = _write_members(tmp_path / "tampered.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


# --------------------------------------------------------------------------- #
# No partial-valid write on any rejection                                       #
# --------------------------------------------------------------------------- #


def test_rejection_leaves_no_target(tmp_path: Path) -> None:
    """After a rejected import, the target directory does not exist at all."""
    members = _read_members(_valid_bundle(tmp_path / "b"))
    members.pop(BUNDLE_PROJECT_FILENAME)  # structurally incomplete -> rejected
    bundle = _write_members(tmp_path / "incomplete.pixbundle", members)
    target = tmp_path / "imported"
    with pytest.raises(AssetExportError):
        _import(bundle, target)
    assert not target.exists()


# --------------------------------------------------------------------------- #
# Source audit — zero eval/exec on the import path (SC-P13-DATA-008-2)          #
# --------------------------------------------------------------------------- #


def test_source_audit_no_eval_or_exec_on_import_path() -> None:
    """The whole ``asset_export`` module (import path included) never eval/exec.

    Collapses all whitespace so ``eval (`` / ``exec (`` are caught too; ``execute(``
    never matches ``exec(`` because the trailing ``ute`` breaks the substring.
    """
    compact = "".join(inspect.getsource(asset_export).split())
    assert "eval(" not in compact
    assert "exec(" not in compact


def test_source_audit_no_eval_or_exec_call_nodes() -> None:
    """AST-level audit: no ``eval``/``exec`` call node exists in the module."""
    tree = ast.parse(inspect.getsource(asset_export))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec"}


def test_import_path_functions_do_not_reference_eval_exec() -> None:
    """The specific import-path callables carry no ``eval``/``exec`` token."""
    for func in (
        import_project_bundle,
        _extract_member_streamed,
        asset_export._safe_member_relpath,
        asset_export._load_bundle_manifest,
        asset_export._reconstruct_project,
    ):
        compact = "".join(inspect.getsource(func).split())
        assert "eval(" not in compact
        assert "exec(" not in compact
