"""Unit tests for :mod:`pixelart_creator.data.asset_ingress` (S11, no Qt).

D2 re-scope
2026-08-21, ruling P11-R1 / plan.md §3.3: the untrusted-input attack matrix
(malformed / oversized / cap-violating / hash-mismatched / path-escaping,
each rejected at step 1 before any write) plus the atomic order's own
assertions —

1. **The guaranteed invariant** — a failure injected at the catalog commit
   (step 4) leaves ``load_catalog`` showing no new entry, and every entry it
   *does* show has retrievable, hash-verified bytes. *No catalog entry
   without its bytes.*
2. **The tolerated state, asserted as tolerated** — after that same failure
   the blob **may still be present** (never asserted absent — the API
   cannot remove it); retrying the same registration succeeds and adds NO
   second blob (``put`` dedups).
3. **Step 2 (``cas.has``) is a dedup observation**, proved by registering
   identical content twice: two catalog entries, one stored blob, and the
   second call reports ``already_present=True``.

The old ``has_blob``-based rollback text (a removed blob after a failed
run) is superseded and is NOT asserted anywhere in this module — no removal
API exists on the CAS/blob stack and none is added to make a test pass.

Also covers the artifact-format seams (ruling P11-R5/P11-R6): ``ARTIFACT_SUFFIX``
distinctness, ``canonical_bytes`` equals what ``register`` stores, and the
``.pixbundle`` / ``pixassetartifact`` format boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pixelart_creator.data import asset_ingress as ai
from pixelart_creator.data import project_io
from pixelart_creator.data.asset_cas import CasError, ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import AssetCatalogError, load_catalog
from pixelart_creator.data.asset_export import BUNDLE_FORMAT_NAME, BUNDLE_SCHEMA_VERSION
from pixelart_creator.data.asset_ingress import (
    ARTIFACT_FORMAT_NAME,
    ARTIFACT_SCHEMA_VERSION,
    ARTIFACT_SUFFIX,
    IngressError,
    _parse_artifact_entry,
    canonical_bytes,
    export_subset,
    import_artifact,
    register,
)
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.constants import (
    MAX_BUNDLE_BYTES,
    MAX_BUNDLE_ENTRIES,
    MAX_TAG_BYTES,
    MAX_TAGS_PER_ASSET,
)
from pixelart_creator.logic.content_hash import canonical_json_bytes, content_hash
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset

# --------------------------------------------------------------------------- #
# Temp-tree discipline — every catalog root is a scratch tree created via     #
# pytest's own tmp_path/tmp_path_factory machinery (portable — no hardcoded   #
# drive-letter path; the project's own path_portability_check gate rejects   #
# those), deleted per test by pytest's own tmp-dir retention. Catalog         #
# persistence needs real files; the CAS backend below does not.               #
# --------------------------------------------------------------------------- #


class _SpyBackend(LocalBlobBackend):
    """An in-memory backend recording call order + counts (no filesystem)."""

    def __init__(self) -> None:
        super().__init__(root=None)
        self.calls: List[str] = []

    def has_blob(self, content_hash_key: str) -> bool:
        self.calls.append("has")
        return super().has_blob(content_hash_key)

    def put_blob(self, content_hash_key: str, blob: bytes) -> None:
        self.calls.append("put")
        super().put_blob(content_hash_key, blob)

    def get_blob(self, content_hash_key: str) -> bytes:
        self.calls.append("get")
        return super().get_blob(content_hash_key)

    @property
    def put_count(self) -> int:
        return self.calls.count("put")


def _cas(backend: Optional[_SpyBackend] = None) -> ContentAddressableStore:
    return ContentAddressableStore(backend if backend is not None else _SpyBackend())


def _doc(width: int = 2, height: int = 2) -> Document:
    return Document(width, height)


def _assert_every_entry_has_bytes(
    catalog: AssetCatalog, cas: ContentAddressableStore
) -> None:
    """The absolute invariant: no catalog entry without its bytes."""
    for descriptor in catalog.entries():
        blob = cas.get(descriptor.content_hash)  # raises CasError if missing/mismatched
        assert content_hash(blob) == descriptor.content_hash


def _artifact_entry(
    *,
    asset_id: str = "e1",
    name: str = "Entry",
    kind: str = "sprite",
    payload: Optional[Dict[str, Any]] = None,
    content_hash_value: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    if payload is None:
        payload = {"x": 1}
    blob = canonical_json_bytes(payload)
    if content_hash_value is None:
        content_hash_value = content_hash(blob)
    return {
        "asset_id": asset_id,
        "name": name,
        "kind": kind,
        "content_hash": content_hash_value,
        "tags": tags if tags is not None else [],
        "metadata": metadata if metadata is not None else {},
        "path": path,
        "payload": payload,
    }


def _artifact_bytes(
    entries: List[Any],
    *,
    format_name: str = ARTIFACT_FORMAT_NAME,
    schema_version: str = ARTIFACT_SCHEMA_VERSION,
) -> bytes:
    manifest = {
        "format": format_name,
        "schema_version": schema_version,
        "entries": entries,
    }
    return json.dumps(manifest).encode("utf-8")


# --------------------------------------------------------------------------- #
# IngressError is a ProjectIOError (PIO-1 family)                             #
# --------------------------------------------------------------------------- #


def test_ingress_error_is_project_io_error() -> None:
    assert issubclass(IngressError, ProjectIOError)


# --------------------------------------------------------------------------- #
# ARTIFACT_SUFFIX                                                             #
# --------------------------------------------------------------------------- #


def test_artifact_suffix_is_pixasset_and_distinct_from_bundle_suffix() -> None:
    from pixelart_creator.data.asset_export import BUNDLE_SUFFIX

    assert ARTIFACT_SUFFIX == ".pixasset"
    assert ARTIFACT_SUFFIX != BUNDLE_SUFFIX


# --------------------------------------------------------------------------- #
# canonical_bytes — equals what register stores                              #
# --------------------------------------------------------------------------- #


class TestCanonicalBytes:
    def test_pure_deterministic_for_same_document(self) -> None:
        doc = _doc(3, 3)
        first = canonical_bytes(doc)
        second = canonical_bytes(doc)
        assert first == second

    def test_equals_register_stored_bytes_same_hash(self, tmp_path: Path) -> None:
        doc = _doc(2, 2)
        doc.frames[0].layers[0].buffer.set_pixel(0, 0, (10, 20, 30, 255))
        expected_bytes = canonical_bytes(doc)
        expected_hash = content_hash(expected_bytes)

        cas = _cas()
        _, descriptor, _ = register(
            doc, AssetCatalog(), cas, tmp_path, name="Hero", kind=AssetKind.SPRITE
        )
        assert descriptor.content_hash == expected_hash
        stored = cas.get(descriptor.content_hash)
        assert stored == expected_bytes

    def test_raises_ingress_error_on_unserialisable_document(self, monkeypatch) -> None:
        def boom(document):
            raise ProjectIOError("cannot serialise")

        monkeypatch.setattr(project_io, "serialize", boom)
        with pytest.raises(IngressError):
            canonical_bytes(_doc())


# --------------------------------------------------------------------------- #
# register — attack matrix at step 1 (validate first, write nothing)          #
# --------------------------------------------------------------------------- #


class TestRegisterValidation:
    def test_rejects_non_catalog(self, tmp_path: Path) -> None:
        with pytest.raises(IngressError):
            register(
                _doc(),
                "not-a-catalog",
                _cas(),
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
            )  # type: ignore[arg-type]

    def test_rejects_non_cas(self, tmp_path: Path) -> None:
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                "not-a-cas",
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
            )  # type: ignore[arg-type]

    def test_rejects_path_escaping_root(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                cas,
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
                path="../escape.pixproj",
            )
        assert backend.calls == []  # nothing written — rejected before step 2

    def test_rejects_invalid_name_writes_nothing(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                cas,
                tmp_path,
                name="",
                kind=AssetKind.SPRITE,
            )
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()

    def test_rejects_tag_count_cap_violation_against_constant(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        too_many_tags = [f"t{i}" for i in range(MAX_TAGS_PER_ASSET + 1)]
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                cas,
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
                tags=too_many_tags,
            )
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()

    def test_accepts_tag_count_at_cap(self, tmp_path: Path) -> None:
        at_cap_tags = [f"t{i}" for i in range(MAX_TAGS_PER_ASSET)]
        _, descriptor, _ = register(
            _doc(),
            AssetCatalog(),
            _cas(),
            tmp_path,
            name="A",
            kind=AssetKind.SPRITE,
            tags=at_cap_tags,
        )
        assert len(descriptor.tags) == MAX_TAGS_PER_ASSET

    def test_catalog_add_rejection_wrapped_as_ingress_error_writes_nothing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A step-1 catalog-model rejection (e.g. the catalog reports itself
        full) is wrapped as IngressError before any CAS write."""
        backend = _SpyBackend()
        cas = _cas(backend)

        def boom(self, entry):
            raise AssetCatalogModelError("catalog full")

        monkeypatch.setattr(AssetCatalog, "add", boom)
        with pytest.raises(IngressError):
            register(
                _doc(), AssetCatalog(), cas, tmp_path, name="A", kind=AssetKind.SPRITE
            )
        assert backend.calls == []


# --------------------------------------------------------------------------- #
# register — the atomic order itself                                          #
# --------------------------------------------------------------------------- #


class TestRegisterAtomicOrder:
    def test_has_observed_before_put_dedup_observation_not_rollback_guard(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        _, _, already_present = register(
            _doc(), AssetCatalog(), cas, tmp_path, name="A", kind=AssetKind.SPRITE
        )
        assert already_present is False
        assert backend.calls[0] == "has"
        assert "put" in backend.calls
        assert backend.calls.index("has") < backend.calls.index("put")

    def test_dedup_two_registrations_identical_content_one_blob_two_entries(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        doc1 = _doc(2, 2)
        doc2 = _doc(2, 2)  # byte-identical canonical content
        catalog, d1, present1 = register(
            doc1, AssetCatalog(), cas, tmp_path, name="A", kind=AssetKind.SPRITE
        )
        catalog, d2, present2 = register(
            doc2, catalog, cas, tmp_path, name="B", kind=AssetKind.SPRITE
        )
        assert present1 is False
        assert present2 is True  # step 2 dedup observation, proved
        assert d1.content_hash == d2.content_hash
        assert d1.asset_id != d2.asset_id
        assert len(catalog.entries()) == 2
        assert backend.put_count == 1  # one stored blob for two catalog entries
        _assert_every_entry_has_bytes(catalog, cas)

    def test_step4_commit_failure_no_new_catalog_entry_invariant_holds(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)

        def boom(new_catalog, root):
            raise AssetCatalogError("injected commit failure")

        monkeypatch.setattr(ai, "save_catalog", boom)
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                cas,
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
            )

        # Guaranteed invariant: no committed catalog shows the failed entry.
        with pytest.raises(AssetCatalogError):
            load_catalog(tmp_path)  # nothing was ever committed

        # Tolerated state: the blob MAY be present — asserted as present, not
        # asserted absent (the API cannot remove it).
        assert backend.put_count == 1

    def test_retry_after_commit_failure_succeeds_and_adds_no_second_blob(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        doc = _doc(2, 2)

        def boom(new_catalog, root):
            raise AssetCatalogError("injected commit failure")

        monkeypatch.setattr(ai, "save_catalog", boom)
        with pytest.raises(IngressError):
            register(
                doc, AssetCatalog(), cas, tmp_path, name="A", kind=AssetKind.SPRITE
            )
        assert backend.put_count == 1  # the tolerated orphan blob

        monkeypatch.undo()  # restore the real save_catalog for the retry
        catalog, descriptor, already_present = register(
            doc,
            AssetCatalog(),
            cas,
            tmp_path,
            name="A-retry",
            kind=AssetKind.SPRITE,
        )
        assert already_present is True  # reclaimed by dedup, per the module docstring
        assert backend.put_count == 1  # NO second blob written
        loaded = load_catalog(tmp_path)
        assert [d.asset_id for d in loaded.entries()] == [descriptor.asset_id]
        _assert_every_entry_has_bytes(loaded, cas)

    def test_step3_blob_write_failure_commits_nothing(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)

        def boom(self, blob):
            raise CasError("injected store failure")

        monkeypatch.setattr(ContentAddressableStore, "put", boom)
        with pytest.raises(IngressError):
            register(
                _doc(),
                AssetCatalog(),
                cas,
                tmp_path,
                name="A",
                kind=AssetKind.SPRITE,
            )
        assert not (tmp_path / "catalog.json").exists()


# --------------------------------------------------------------------------- #
# register — reference_key computation (ruling P11-R8, plan §3.10)           #
# --------------------------------------------------------------------------- #


class TestRegisterReferenceKey:
    def test_sprite_registration_computes_non_empty_reference_key(
        self, tmp_path: Path
    ) -> None:
        from pixelart_creator.logic.asset_edges import reference_bytes
        from pixelart_creator.logic.content_hash import content_hash as _hash

        buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=(255, 0, 0, 255))
        doc = Document.from_buffer(buf, name="hero")
        _, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="Hero", kind=AssetKind.SPRITE
        )
        assert descriptor.reference_key != ""
        assert descriptor.reference_key == _hash(reference_bytes(doc, AssetKind.SPRITE))

    def test_tileset_registration_with_exactly_one_tileset_computes_reference_key(
        self, tmp_path: Path
    ) -> None:
        buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=(0, 0, 255, 255))
        tileset = Tileset(buf, tile_width=4, tile_height=4, name="TS")
        doc = Document(4, 4, mode=ColorMode.RGBA)
        doc.tilesets.append(tileset)
        _, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="Tiles", kind=AssetKind.TILESET
        )
        assert descriptor.reference_key != ""

    def test_tileset_registration_with_zero_tilesets_degrades_to_empty_reference_key(
        self, tmp_path: Path
    ) -> None:
        doc = Document(4, 4, mode=ColorMode.RGBA)  # no tilesets attached
        _, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="Tiles", kind=AssetKind.TILESET
        )
        assert descriptor.reference_key == ""  # ambiguity -> "no edge", never an error

    def test_tileset_registration_with_two_tilesets_degrades_to_empty_reference_key(
        self, tmp_path: Path
    ) -> None:
        buf_a = PixelBuffer(4, 4, ColorMode.RGBA, fill=(255, 0, 0, 255))
        buf_b = PixelBuffer(4, 4, ColorMode.RGBA, fill=(0, 0, 255, 255))
        doc = Document(4, 4, mode=ColorMode.RGBA)
        doc.tilesets.extend(
            [
                Tileset(buf_a, tile_width=4, tile_height=4, name="A"),
                Tileset(buf_b, tile_width=4, tile_height=4, name="B"),
            ]
        )
        _, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="Tiles", kind=AssetKind.TILESET
        )
        assert (
            descriptor.reference_key == ""
        )  # ambiguous -> "no edge", never a wrong one

    @pytest.mark.parametrize(
        "kind", [AssetKind.ANIMATION, AssetKind.TILEMAP, AssetKind.PALETTE]
    )
    def test_never_target_kinds_always_record_empty_reference_key(
        self, tmp_path: Path, kind: AssetKind
    ) -> None:
        """ANIMATION/TILEMAP/PALETTE can never **be** a reference target
        (plan §3.10) — ``register`` records ``""`` regardless of document
        shape, never attempting (and never erroring on) a derivation."""
        doc = _doc(4, 4)
        _, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="X", kind=kind
        )
        assert descriptor.reference_key == ""

    def test_reference_key_round_trips_through_save_and_load_catalog(
        self, tmp_path: Path
    ) -> None:
        buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=(255, 0, 0, 255))
        doc = Document.from_buffer(buf, name="hero")
        catalog, descriptor, _ = register(
            doc, AssetCatalog(), _cas(), tmp_path, name="Hero", kind=AssetKind.SPRITE
        )
        reloaded = load_catalog(tmp_path)
        assert (
            reloaded.get(descriptor.asset_id).reference_key == descriptor.reference_key
        )


# --------------------------------------------------------------------------- #
# import_artifact — untrusted-input attack matrix (step 1, before any write)  #
# --------------------------------------------------------------------------- #


class TestImportArtifactUntrustedInput:
    def test_rejects_non_bytes(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            # type: ignore[arg-type]
            import_artifact("not-bytes", AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_malformed_utf8(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            import_artifact(b"\xff\xfe\x00\x01", AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_malformed_json(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            import_artifact(b"{not json", AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_non_object_manifest(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        with pytest.raises(IngressError):
            import_artifact(b"[]", AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_wrong_format_marker_dot_pixbundle_content(
        self, tmp_path: Path
    ) -> None:
        """A .pixbundle's bytes handed to import_artifact are rejected on the
        format marker (the extended validation clause) — the artifact parser is where
        the two formats are kept apart."""
        backend = _SpyBackend()
        cas = _cas(backend)
        bundle_like = json.dumps(
            {
                "format": BUNDLE_FORMAT_NAME,
                "schema_version": BUNDLE_SCHEMA_VERSION,
                "assets": [],
            }
        ).encode("utf-8")
        with pytest.raises(IngressError, match="not a pixassetartifact"):
            import_artifact(bundle_like, AssetCatalog(), cas, tmp_path)
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()

    def test_rejects_unsupported_schema_version(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        artifact = _artifact_bytes([], schema_version="99")
        with pytest.raises(IngressError):
            import_artifact(artifact, AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_entries_not_a_list(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        manifest = {
            "format": ARTIFACT_FORMAT_NAME,
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "entries": "not-a-list",
        }
        with pytest.raises(IngressError):
            import_artifact(
                json.dumps(manifest).encode("utf-8"), AssetCatalog(), cas, tmp_path
            )
        assert backend.calls == []

    def test_rejects_oversized_artifact_against_max_bundle_bytes(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        monkeypatch.setattr(ai, "MAX_BUNDLE_BYTES", 16)
        artifact = _artifact_bytes([])  # well over the patched 16-byte cap
        assert len(artifact) > ai.MAX_BUNDLE_BYTES
        with pytest.raises(IngressError, match="MAX_BUNDLE_BYTES"):
            import_artifact(artifact, AssetCatalog(), cas, tmp_path)
        assert backend.calls == []
        # The real constant is still what production code enforces by default.
        assert MAX_BUNDLE_BYTES > 16

    def test_rejects_too_many_entries_against_max_bundle_entries(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        monkeypatch.setattr(ai, "MAX_BUNDLE_ENTRIES", 2)
        artifact = _artifact_bytes([{}, {}, {}])  # 3 > patched cap of 2
        with pytest.raises(IngressError, match="MAX_BUNDLE_ENTRIES"):
            import_artifact(artifact, AssetCatalog(), cas, tmp_path)
        assert backend.calls == []
        assert MAX_BUNDLE_ENTRIES > 2

    def test_rejects_entry_missing_asset_id(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry()
        del entry["asset_id"]
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_entry_hash_mismatch(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(content_hash_value=content_hash(b"not-the-payload"))
        with pytest.raises(IngressError, match="does not match"):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()

    def test_rejects_entry_path_escaping_root(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(path="../../escape.pixproj")
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_entry_tag_cap_violation_against_constant(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(tags=[f"t{i}" for i in range(MAX_TAGS_PER_ASSET + 1)])
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_entry_tag_byte_cap_violation_against_constant(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(tags=["x" * (MAX_TAG_BYTES + 1)])
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_non_catalog(self, tmp_path: Path) -> None:
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([]), "not-a-catalog", _cas(), tmp_path)  # type: ignore[arg-type]

    def test_rejects_non_cas(self, tmp_path: Path) -> None:
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([]), AssetCatalog(), "not-a-cas", tmp_path)  # type: ignore[arg-type]

    def test_rejects_entry_kind_not_a_string(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(kind=123)  # type: ignore[arg-type]
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_rejects_entry_kind_unknown_value(self, tmp_path: Path) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        entry = _artifact_entry(kind="not-a-real-kind")
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([entry]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []

    def test_parse_artifact_entry_payload_not_canonical_encodable_raises(self) -> None:
        """A defensive branch unreachable through the public JSON-parse path
        (any payload arriving via ``json.loads`` is already JSON-serialisable)
        — exercised directly against the private parser to prove the guard
        exists, white-box, rather than left silently untested."""
        entry: Dict[str, Any] = {
            "asset_id": "e1",
            "name": "Entry",
            "kind": "sprite",
            "content_hash": "0" * 64,
            "tags": [],
            "metadata": {},
            "path": None,
            "payload": {1, 2, 3},  # a set is not JSON-serialisable
        }
        with pytest.raises(IngressError):
            _parse_artifact_entry(entry, Path("."))


# --------------------------------------------------------------------------- #
# import_artifact — atomicity (validate-all-first, then write, commit once)   #
# --------------------------------------------------------------------------- #


class TestImportArtifactAtomicity:
    def test_second_entry_invalid_rejects_whole_artifact_first_entry_not_written(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        good = _artifact_entry(asset_id="good", payload={"a": 1})
        bad = _artifact_entry(
            asset_id="bad", content_hash_value=content_hash(b"tampered")
        )
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([good, bad]), AssetCatalog(), cas, tmp_path)
        # Step 1 validates every entry before any write — nothing written.
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()

    def test_put_failure_on_second_entry_commits_nothing_first_blob_tolerated(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        e1 = _artifact_entry(asset_id="e1", payload={"a": 1})
        e2 = _artifact_entry(asset_id="e2", payload={"a": 2})

        real_put = ContentAddressableStore.put
        call_count = {"n": 0}

        def flaky_put(self, blob):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise CasError("injected mid-write failure")
            return real_put(self, blob)

        monkeypatch.setattr(ContentAddressableStore, "put", flaky_put)
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([e1, e2]), AssetCatalog(), cas, tmp_path)

        # Guaranteed invariant: no catalog was ever committed.
        with pytest.raises(AssetCatalogError):
            load_catalog(tmp_path)
        # Tolerated state: the first blob may be present (not asserted absent).
        assert backend.put_count == 1

    def test_commit_failure_after_all_blobs_written_no_catalog_entry_tolerated_blobs(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        e1 = _artifact_entry(asset_id="e1", payload={"a": 1})
        e2 = _artifact_entry(asset_id="e2", payload={"a": 2})

        def boom(new_catalog, root):
            raise AssetCatalogError("injected commit failure")

        monkeypatch.setattr(ai, "save_catalog", boom)
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([e1, e2]), AssetCatalog(), cas, tmp_path)

        with pytest.raises(AssetCatalogError):
            load_catalog(tmp_path)
        assert backend.put_count == 2  # both tolerated, both present

        monkeypatch.undo()
        catalog, descriptors = import_artifact(
            _artifact_bytes([e1, e2]), AssetCatalog(), cas, tmp_path
        )
        assert {d.asset_id for d in descriptors} == {"e1", "e2"}
        assert backend.put_count == 2  # dedup: no third/fourth blob on retry
        _assert_every_entry_has_bytes(catalog, cas)

    def test_dedup_within_one_artifact_identical_payload_two_entries_one_blob(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        e1 = _artifact_entry(asset_id="e1", payload={"same": True})
        e2 = _artifact_entry(asset_id="e2", payload={"same": True})
        catalog, descriptors = import_artifact(
            _artifact_bytes([e1, e2]), AssetCatalog(), cas, tmp_path
        )
        assert len(descriptors) == 2
        assert descriptors[0].content_hash == descriptors[1].content_hash
        assert backend.put_count == 1
        _assert_every_entry_has_bytes(catalog, cas)

    def test_duplicate_asset_id_within_artifact_rejects_whole_artifact(
        self, tmp_path: Path
    ) -> None:
        backend = _SpyBackend()
        cas = _cas(backend)
        e1 = _artifact_entry(asset_id="dup", payload={"a": 1})
        e2 = _artifact_entry(asset_id="dup", payload={"a": 2})
        with pytest.raises(IngressError):
            import_artifact(_artifact_bytes([e1, e2]), AssetCatalog(), cas, tmp_path)
        assert backend.calls == []
        assert not (tmp_path / "catalog.json").exists()


# --------------------------------------------------------------------------- #
# export_subset                                                               #
# --------------------------------------------------------------------------- #


class TestExportSubset:
    def test_rejects_non_catalog(self) -> None:
        with pytest.raises(IngressError):
            export_subset([], "not-a-catalog", _cas())  # type: ignore[arg-type]

    def test_rejects_non_cas(self) -> None:
        with pytest.raises(IngressError):
            export_subset([], AssetCatalog(), "not-a-cas")  # type: ignore[arg-type]

    def test_rejects_asset_ids_given_as_a_single_string(self) -> None:
        with pytest.raises(IngressError):
            export_subset("abc", AssetCatalog(), _cas())  # type: ignore[arg-type]

    def test_rejects_non_iterable_asset_ids(self) -> None:
        with pytest.raises(IngressError):
            export_subset(123, AssetCatalog(), _cas())  # type: ignore[arg-type]

    def test_missing_blob_for_a_catalogued_entry_raises_ingress_error(self) -> None:
        """A descriptor whose blob was never (or is no longer) in the CAS —
        the corrupted-store case ``export_subset`` must still refuse cleanly."""
        cas = _cas()
        descriptor = AssetDescriptor(
            asset_id="a",
            kind=AssetKind.SPRITE,
            name="A",
            content_hash=content_hash(b"never-stored"),
        )
        catalog = AssetCatalog().add(descriptor)
        with pytest.raises(IngressError):
            export_subset(["a"], catalog, cas)

    def test_non_json_stored_payload_raises_ingress_error(self) -> None:
        """A blob whose bytes hash-verify but do not decode as JSON — proves
        the payload-decode guard, not just the hash-verify guard."""
        cas = _cas()
        raw = b"not-json-bytes"
        digest = cas.put(raw)
        descriptor = AssetDescriptor(
            asset_id="a", kind=AssetKind.SPRITE, name="A", content_hash=digest
        )
        catalog = AssetCatalog().add(descriptor)
        with pytest.raises(IngressError):
            export_subset(["a"], catalog, cas)

    def test_rejects_missing_id_no_partial_artifact(self, tmp_path: Path) -> None:
        cas = _cas()
        catalog, descriptor, _ = register(
            _doc(), AssetCatalog(), cas, tmp_path, name="A", kind=AssetKind.SPRITE
        )
        with pytest.raises(IngressError):
            export_subset([descriptor.asset_id, "missing-id"], catalog, cas)

    def test_export_then_import_round_trip_into_empty_library_same_hashes(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        source_cas = _cas()
        doc1 = _doc(2, 2)
        doc1.frames[0].layers[0].buffer.set_pixel(0, 0, (1, 2, 3, 255))
        doc2 = _doc(3, 3)
        catalog, d1, _ = register(
            doc1,
            AssetCatalog(),
            source_cas,
            tmp_path,
            name="Hero",
            kind=AssetKind.SPRITE,
            tags=["hero"],
            metadata={"k": "v"},
            path="assets/hero.pixproj",
        )
        catalog, d2, _ = register(
            doc2,
            catalog,
            source_cas,
            tmp_path,
            name="Tiles",
            kind=AssetKind.TILESET,
        )

        artifact = export_subset([d1.asset_id, d2.asset_id], catalog, source_cas)

        # A second, disjoint scratch tree (an "empty library") — pytest's own
        # tmp_path_factory, deleted with the rest of the test session's tmp
        # tree, never a hardcoded path.
        dest_root = tmp_path_factory.mktemp("ingress-dest")
        dest_cas = _cas()
        new_catalog, imported = import_artifact(
            artifact, AssetCatalog(), dest_cas, dest_root
        )
        imported_by_id = {d.asset_id: d for d in imported}
        assert imported_by_id[d1.asset_id].content_hash == d1.content_hash
        assert imported_by_id[d2.asset_id].content_hash == d2.content_hash
        assert imported_by_id[d1.asset_id].tags == d1.tags
        assert dict(imported_by_id[d1.asset_id].metadata) == dict(d1.metadata)
        # The advisory path is dropped — relocatable, self-contained artifact.
        assert imported_by_id[d1.asset_id].path is None
        _assert_every_entry_has_bytes(new_catalog, dest_cas)

    def test_export_then_import_round_trip_preserves_reference_key(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """An artifact written by ``export_subset``
        carries the ``reference_key`` and ``import_artifact`` restores it
        exactly — the assertion that keeps a cross-machine share graph-
        reachable (SC-P11-UI-016-2's "identical content hashes" promise
        would be green over a dead feature otherwise, per the module docstring
        note at ``export_subset``'s ``reference_key`` field)."""
        source_cas = _cas()
        buf = PixelBuffer(4, 4, ColorMode.RGBA, fill=(255, 0, 0, 255))
        doc = Document.from_buffer(buf, name="hero")
        catalog, descriptor, _ = register(
            doc,
            AssetCatalog(),
            source_cas,
            tmp_path,
            name="Hero",
            kind=AssetKind.SPRITE,
        )
        assert descriptor.reference_key != ""  # sanity: a real key to lose

        artifact = export_subset([descriptor.asset_id], catalog, source_cas)

        dest_root = tmp_path_factory.mktemp("ingress-dest-refkey")
        dest_cas = _cas()
        _, imported = import_artifact(artifact, AssetCatalog(), dest_cas, dest_root)
        assert imported[0].reference_key == descriptor.reference_key

    def test_import_pre_reference_key_artifact_entry_parses_as_empty_no_edge(
        self, tmp_path: Path
    ) -> None:
        """A pre-``reference_key`` artifact/sidecar
        imports with the key as ``""`` and produces no edge (backward-compat
        read path, no schema bump) — the entry carries no
        ``"reference_key"`` key at all, the exact shape an artifact exported
        before the fix would have."""
        entry = _artifact_entry(asset_id="legacy", payload={"a": 1})
        assert "reference_key" not in entry  # the pre-fix artifact shape
        catalog, imported = import_artifact(
            _artifact_bytes([entry]), AssetCatalog(), _cas(), tmp_path
        )
        assert imported[0].reference_key == ""
        # No edge is derivable from an unknown key — matches edges_for's own
        # "unknown never matches" guard (ruling P11-R8); asserted here at the
        # boundary that produces the "" in the first place.
        assert catalog.get("legacy").reference_key == ""


# --------------------------------------------------------------------------- #
# Hypothesis property tests — bounded, deterministic (derandomize=True)       #
# --------------------------------------------------------------------------- #


@settings(
    max_examples=25,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(garbage=st.binary(min_size=0, max_size=64))
def test_import_artifact_random_bytes_never_write_anything(
    garbage: bytes, tmp_path: Path
) -> None:
    """No adversarial byte string ever reaches step 2 (write) — every one is
    rejected purely at step 1, before any blob or catalog write. The root is
    never touched on this path, so the function-scoped ``tmp_path`` fixture
    (shared across the generated examples) is safe to reuse here."""
    backend = _SpyBackend()
    cas = _cas(backend)
    with pytest.raises(IngressError):
        import_artifact(garbage, AssetCatalog(), cas, tmp_path)
    assert backend.calls == []


@settings(max_examples=15, deadline=None, derandomize=True)
@given(
    width=st.integers(min_value=1, max_value=4),
    height=st.integers(min_value=1, max_value=4),
)
def test_canonical_bytes_deterministic_across_generated_sizes(
    width: int, height: int
) -> None:
    doc = _doc(width, height)
    assert canonical_bytes(doc) == canonical_bytes(doc)


def test_register_tag_count_boundary_property(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Property: register accepts a tag count iff it is <= MAX_TAGS_PER_ASSET
    (the constant, never a literal boundary), each time in a fresh scratch
    tree from pytest's own tmp_path_factory, deleted with the test session's
    tmp tree."""

    @settings(max_examples=15, deadline=None, derandomize=True)
    @given(count=st.integers(min_value=0, max_value=MAX_TAGS_PER_ASSET + 10))
    def check(count: int) -> None:
        root = tmp_path_factory.mktemp("ingress-prop")
        tags = [f"t{i}" for i in range(count)]
        cas = _cas()
        if count <= MAX_TAGS_PER_ASSET:
            _, descriptor, _ = register(
                _doc(),
                AssetCatalog(),
                cas,
                root,
                name="A",
                kind=AssetKind.SPRITE,
                tags=tags,
            )
            assert len(descriptor.tags) == count
        else:
            with pytest.raises(IngressError):
                register(
                    _doc(),
                    AssetCatalog(),
                    cas,
                    root,
                    name="A",
                    kind=AssetKind.SPRITE,
                    tags=tags,
                )

    check()
