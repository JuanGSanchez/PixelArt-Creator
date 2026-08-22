"""Unit tests for ``pixelart_creator.data.asset_revision_store`` (S11, no Qt).

Covers the append-only, content-addressable revision store (ADR-0030 §6;
REQ-P11-DATA-004): recording a revision appends an immutable content-hash-keyed
descriptor and stores the bytes once in the CAS; re-recording bytes whose hash equals
the current head is a dedup no-op (no new revision AND no new CAS blob); ``fetch`` is
content-hash-verified and a tampered blob is rejected; the store is append-only (no
in-place mutate/delete path and earlier revisions survive later records); and the module
routes revisions through the CAS only — it imports no CRDT/cloud code. T11-3-07.
"""

from __future__ import annotations

import ast

import pytest

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_revision_store import (
    AssetRevisionStore,
    AssetRevisionStoreError,
)
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.logic.asset_version import AssetRevision, AssetVersionHistory
from pixelart_creator.logic.content_hash import content_hash


def _store_over_backend() -> tuple[AssetRevisionStore, LocalBlobBackend]:
    """Return a revision store over an inspectable in-memory CAS backend."""
    backend = LocalBlobBackend()
    store = AssetRevisionStore(ContentAddressableStore(backend=backend))
    return store, backend


# --------------------------------------------------------------------------- #
# Construction                                                                 #
# --------------------------------------------------------------------------- #


def test_default_cas_is_in_memory() -> None:
    store = AssetRevisionStore()
    r = store.record("a", b"bytes", created_marker=0)
    assert store.fetch("a", r.content_hash) == b"bytes"


def test_rejects_non_cas() -> None:
    with pytest.raises(AssetRevisionStoreError):
        AssetRevisionStore(cas="not-a-cas")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# record — appends an immutable, content-hash-keyed descriptor                 #
# --------------------------------------------------------------------------- #


def test_record_appends_content_hash_keyed_descriptor() -> None:
    store, backend = _store_over_backend()
    r = store.record("sprite", b"v1", created_marker=0, author="alice")
    assert isinstance(r, AssetRevision)
    assert r.asset_id == "sprite"
    assert r.content_hash == content_hash(b"v1")
    assert r.parent_hash is None  # first revision is a root
    assert r.author == "alice"
    # The bytes are stored exactly once in the content-addressable store.
    assert len(backend._memory) == 1
    assert store.head("sprite") is r


def test_second_distinct_revision_links_to_prior_head() -> None:
    store, backend = _store_over_backend()
    r1 = store.record("s", b"v1", created_marker=0)
    r2 = store.record("s", b"v2", created_marker=1)
    assert r2.parent_hash == r1.content_hash  # DAG parent link
    history = store.history("s")
    assert [r.content_hash for r in history.revisions] == [
        r1.content_hash,
        r2.content_hash,
    ]
    assert len(backend._memory) == 2  # two distinct blobs


def test_record_rejects_invalid_asset_id() -> None:
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.record("", b"v1", created_marker=0)


def test_record_rejects_non_bytes_blob() -> None:
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.record("s", "not-bytes", created_marker=0)  # type: ignore[arg-type]


def test_record_wraps_cas_error(monkeypatch) -> None:
    # An oversized blob trips the CAS cap -> wrapped as AssetRevisionStoreError.
    from pixelart_creator.data import asset_cas

    monkeypatch.setattr(asset_cas, "MAX_BLOB_BYTES", 4)
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.record("s", b"x" * 5, created_marker=0)


# --------------------------------------------------------------------------- #
# Dedup no-op — identical bytes create no new revision / no new blob           #
# --------------------------------------------------------------------------- #


def test_recording_identical_head_bytes_is_dedup_noop() -> None:
    store, backend = _store_over_backend()
    r1 = store.record("s", b"same", created_marker=0)
    r2 = store.record("s", b"same", created_marker=1)  # identical bytes -> no-op
    # No new revision.
    assert r2 is r1
    assert len(store.history("s").revisions) == 1
    # No duplicate blob.
    assert len(backend._memory) == 1


def test_reintroducing_old_bytes_after_change_is_a_new_revision() -> None:
    # Dedup is only against the CURRENT head: re-recording earlier bytes after the head
    # moved on is a genuine new revision (append-only), sharing the deduped blob.
    store, backend = _store_over_backend()
    store.record("s", b"v1", created_marker=0)
    store.record("s", b"v2", created_marker=1)
    r3 = store.record("s", b"v1", created_marker=2)  # v1 != current head (v2)
    assert r3.content_hash == content_hash(b"v1")
    assert len(store.history("s").revisions) == 3
    # v1's blob is shared (dedup) -> still only two distinct blobs.
    assert len(backend._memory) == 2


# --------------------------------------------------------------------------- #
# fetch — content-hash verified; tampered blob rejected                        #
# --------------------------------------------------------------------------- #


def test_fetch_returns_recorded_bytes() -> None:
    store, _ = _store_over_backend()
    r = store.record("s", b"payload", created_marker=0)
    assert store.fetch("s", r.content_hash) == b"payload"


def test_fetch_unknown_asset_raises() -> None:
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.fetch("ghost", content_hash(b"payload"))


def test_fetch_unknown_revision_raises() -> None:
    store, _ = _store_over_backend()
    store.record("s", b"payload", created_marker=0)
    with pytest.raises(AssetRevisionStoreError):
        store.fetch("s", content_hash(b"never-recorded"))


def test_fetch_rejects_tampered_blob() -> None:
    store, backend = _store_over_backend()
    r = store.record("s", b"honest", created_marker=0)
    # Corrupt the backing bytes under the recorded key (tamper/corruption).
    backend._memory[r.content_hash] = b"tampered-content"
    with pytest.raises(AssetRevisionStoreError):
        store.fetch("s", r.content_hash)


# --------------------------------------------------------------------------- #
# history / head                                                               #
# --------------------------------------------------------------------------- #


def test_history_of_unknown_asset_is_empty() -> None:
    store, _ = _store_over_backend()
    assert store.history("ghost") == AssetVersionHistory()


def test_head_of_unknown_asset_raises() -> None:
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.head("ghost")


# --------------------------------------------------------------------------- #
# Append-only — no in-place mutate/delete; earlier revisions survive           #
# --------------------------------------------------------------------------- #


def test_store_exposes_no_mutate_or_delete_path() -> None:
    store = AssetRevisionStore()
    for forbidden in ("delete", "remove", "mutate", "update", "pop", "clear"):
        assert not hasattr(store, forbidden)


def test_earlier_revision_survives_and_stays_fetchable() -> None:
    store, _ = _store_over_backend()
    r1 = store.record("s", b"v1", created_marker=0)
    store.record("s", b"v2", created_marker=1)
    # The earlier revision is retained (append-only, never rewritten) and fetchable.
    assert store.history("s").by_hash(r1.content_hash) == r1
    assert store.fetch("s", r1.content_hash) == b"v1"


# --------------------------------------------------------------------------- #
# No CRDT / no cloud dependency (import-graph scan of the module source)       #
# --------------------------------------------------------------------------- #


def _imported_names(module) -> list[str]:
    with open(module.__file__, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_module_imports_no_crdt_no_cloud_no_qt() -> None:
    from pixelart_creator.data import asset_revision_store

    for name in _imported_names(asset_revision_store):
        lowered = name.lower()
        parts = lowered.split(".")
        # Revisions are stored in the CAS only — never through the collab CRDT/cloud.
        assert "crdt" not in parts
        assert "cloud" not in parts
        assert not lowered.startswith(("pyside", "pyqt"))
        assert "qt" not in parts


# --------------------------------------------------------------------------- #
# Durability — bind_root (T40; SC-P11-INGRESS-E2E-1's restart clause, unit    #
# level; REQ-P11-DATA-008's revision half)                                    #
# --------------------------------------------------------------------------- #


def test_bind_root_of_empty_root_adopts_nothing(tmp_path) -> None:
    store, _ = _store_over_backend()
    before = sorted(p.name for p in tmp_path.iterdir())
    assert before == []
    store.bind_root(tmp_path)
    assert store.history("anything") == AssetVersionHistory()
    after = sorted(p.name for p in tmp_path.iterdir())
    assert after == []


def test_bind_root_rejects_malformed_index(tmp_path) -> None:
    (tmp_path / "revisions.json").write_text("not json{{{", encoding="utf-8")
    store, _ = _store_over_backend()
    with pytest.raises(AssetRevisionStoreError):
        store.bind_root(tmp_path)


def test_record_after_bind_root_persists_to_disk(tmp_path) -> None:
    store, _ = _store_over_backend()
    store.bind_root(tmp_path)
    store.record("sprite", b"v1", created_marker=0)
    assert (tmp_path / "revisions.json").exists()
    assert (tmp_path / "revisions" / "sprite.json").exists()


def test_second_store_bound_to_same_root_sees_recorded_revisions(tmp_path) -> None:
    writer, _ = _store_over_backend()
    writer.bind_root(tmp_path)
    r1 = writer.record("sprite", b"v1", created_marker=0)
    writer.record("sprite", b"v2", created_marker=1)

    reader, _ = _store_over_backend()
    reader.bind_root(tmp_path)
    history = reader.history("sprite")
    assert [r.content_hash for r in history.revisions] == [
        r1.content_hash,
        content_hash(b"v2"),
    ]


def test_unbound_store_persists_nothing(tmp_path, monkeypatch) -> None:
    from pixelart_creator.data import asset_revision_store as module

    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "write_history",
        lambda *a, **k: calls.append("write_history"),
    )
    monkeypatch.setattr(
        module,
        "write_index",
        lambda *a, **k: calls.append("write_index"),
    )
    store, _ = _store_over_backend()  # never bound
    store.record("sprite", b"v1", created_marker=0)
    assert calls == []


def test_dedup_rerecord_after_bind_root_writes_nothing_new(
    tmp_path, monkeypatch
) -> None:
    from pixelart_creator.data import asset_revision_store as module

    store, _ = _store_over_backend()
    store.bind_root(tmp_path)
    store.record("sprite", b"same", created_marker=0)

    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "write_history",
        lambda *a, **k: calls.append("write_history"),
    )
    monkeypatch.setattr(
        module,
        "write_index",
        lambda *a, **k: calls.append("write_index"),
    )
    # Identical bytes against the current head is a dedup no-op: the store never
    # reaches the persistence calls at all.
    store.record("sprite", b"same", created_marker=1)
    assert calls == []


def test_write_failure_leaves_history_unchanged_and_wraps_as_store_error(
    tmp_path, monkeypatch
) -> None:
    from pixelart_creator.data import asset_revision_store as module
    from pixelart_creator.data.asset_revision_io import AssetRevisionIOError

    store, _ = _store_over_backend()
    store.bind_root(tmp_path)
    store.record("sprite", b"v1", created_marker=0)
    before = store.history("sprite")

    def _raise(*_args, **_kwargs):
        raise AssetRevisionIOError("simulated disk failure")

    monkeypatch.setattr(module, "write_history", _raise)

    with pytest.raises(AssetRevisionStoreError) as excinfo:
        store.record("sprite", b"v2", created_marker=1)

    # Never the raw serialiser error — the two Qt slots that call record() catch
    # only AssetRevisionStoreError, so a leaked AssetRevisionIOError would crash
    # unhandled inside a slot.
    assert not isinstance(excinfo.value, AssetRevisionIOError)
    assert store.history("sprite") == before


def test_write_index_failure_also_leaves_history_unchanged(
    tmp_path, monkeypatch
) -> None:
    from pixelart_creator.data import asset_revision_store as module
    from pixelart_creator.data.asset_revision_io import AssetRevisionIOError

    store, _ = _store_over_backend()
    store.bind_root(tmp_path)
    store.record("sprite", b"v1", created_marker=0)
    before = store.history("sprite")

    def _raise(*_args, **_kwargs):
        raise AssetRevisionIOError("simulated index write failure")

    monkeypatch.setattr(module, "write_index", _raise)

    with pytest.raises(AssetRevisionStoreError) as excinfo:
        store.record("sprite", b"v2", created_marker=1)

    assert not isinstance(excinfo.value, AssetRevisionIOError)
    assert store.history("sprite") == before
