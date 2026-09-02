"""Tests for pixelart_creator.data.cloud.fake_adapter (Phase-10 Slice A, no Qt).

The fake adapter is the CI-tested implementation of the whole ``CloudPort``
(REQ-P10-DATA-002/-003/-004/-005). Covers the full verb set, optimistic
concurrency, the ``MAX_CLOUD_PROJECT_BYTES`` + ``MAX_CLOUD_VERSIONS`` bounds
(boundary + over), the crash-safe recovery slot and the restart-recovery recipe
from the implementation report §7, and a regression test for the Windows blob-filename bug
(blobs keyed by ordinal, never by a ``version_id`` containing ``:``).
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.cloud import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
    FakeCloudAdapter,
)
from pixelart_creator.data.cloud import fake_adapter as fa
from pixelart_creator.logic.constants import MAX_CLOUD_VERSIONS

PID = "myproject"


# --- put / get / list / latest ---------------------------------------------- #


def test_put_get_round_trip():
    a = FakeCloudAdapter()
    v = a.put(PID, b"blob-0")
    assert v.ordinal == 0
    assert a.get(PID, v.version_id) == b"blob-0"


def test_put_appends_ordered_versions_with_envelope():
    a = FakeCloudAdapter()
    v0 = a.put(PID, b"v0")
    v1 = a.put(PID, b"v1")
    versions = a.list_versions(PID)
    assert [v.ordinal for v in versions] == [0, 1]
    # Deterministic monotonic markers (no wall-clock).
    assert [v.created_marker for v in versions] == [0, 1]
    # Version envelope: parent chain points at the prior version.
    assert v0.parent_version_id is None
    assert v1.parent_version_id == v0.version_id
    assert a.latest(PID).version_id == v1.version_id


def test_get_unknown_version_raises():
    a = FakeCloudAdapter()
    a.put(PID, b"v0")
    with pytest.raises(CloudError):
        a.get(PID, "myproject:999")


def test_list_versions_unknown_project_is_empty():
    a = FakeCloudAdapter()
    assert a.list_versions("nope") == ()


def test_latest_unknown_project_raises():
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.latest("nope")


def test_get_unknown_project_raises():
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.get("nope", "x:0")


# --- delete ----------------------------------------------------------------- #


def test_delete_removes_project(tmp_path):
    a = FakeCloudAdapter(tmp_path)
    a.put(PID, b"v0")
    a.put_recovery(PID, b"rec")
    a.delete(PID)
    assert a.list_versions(PID) == ()
    assert not (tmp_path / PID).exists()


def test_delete_unknown_project_raises():
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.delete("nope")


# --- optimistic concurrency ------------------------------------------------- #


def test_parent_version_none_always_appends():
    a = FakeCloudAdapter()
    a.put(PID, b"v0")
    a.put(PID, b"v1", parent_version=None)  # no guard -> appends
    assert len(a.list_versions(PID)) == 2


def test_parent_version_current_latest_appends():
    a = FakeCloudAdapter()
    v0 = a.put(PID, b"v0")
    a.put(PID, b"v1", parent_version=v0.version_id)
    assert len(a.list_versions(PID)) == 2


def test_stale_parent_version_conflicts():
    a = FakeCloudAdapter()
    v0 = a.put(PID, b"v0")
    a.put(PID, b"v1", parent_version=v0.version_id)
    # v0 is no longer the latest -> conflict.
    with pytest.raises(CloudError):
        a.put(PID, b"v2", parent_version=v0.version_id)


def test_parent_version_on_empty_history_conflicts():
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.put(PID, b"v0", parent_version="something")


# --- input guards ----------------------------------------------------------- #


# Built at runtime (never a literal) so the path-portability check does not flag
# the deliberate backslash-separator test input.
_BACKSLASH_ID = "a" + chr(92) + "b"


@pytest.mark.parametrize("bad", ["", "a/b", _BACKSLASH_ID, ".", ".."])
def test_project_id_guard(bad):
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.put(bad, b"x")


def test_put_non_bytes_raises():
    a = FakeCloudAdapter()
    with pytest.raises(CloudError):
        a.put(PID, "not-bytes")  # type: ignore[arg-type]


def test_put_accepts_bytearray():
    a = FakeCloudAdapter()
    v = a.put(PID, bytearray(b"data"))
    assert a.get(PID, v.version_id) == b"data"


# --- size cap (MAX_CLOUD_PROJECT_BYTES) boundary + over --------------------- #


def test_put_at_size_cap_ok_over_raises(monkeypatch):
    monkeypatch.setattr(fa, "MAX_CLOUD_PROJECT_BYTES", 8)
    a = FakeCloudAdapter()
    a.put(PID, b"x" * 8)  # exactly at the cap is allowed
    with pytest.raises(CloudDataError):
        a.put(PID, b"x" * 9)


def test_put_recovery_over_cap_raises(monkeypatch):
    monkeypatch.setattr(fa, "MAX_CLOUD_PROJECT_BYTES", 4)
    a = FakeCloudAdapter()
    with pytest.raises(CloudDataError):
        a.put_recovery(PID, b"toolong")


# --- version cap (MAX_CLOUD_VERSIONS) --------------------------------------- #


def test_version_cap_over_limit_raises(monkeypatch):
    # Shrink the cap in the version-history module (where append enforces it) to
    # avoid 100 puts; the adapter re-raises VersionHistoryError as CloudError.
    from pixelart_creator.logic import version_history as vh

    monkeypatch.setattr(vh, "MAX_CLOUD_VERSIONS", 2)
    a = FakeCloudAdapter()
    a.put(PID, b"v0")
    a.put(PID, b"v1")
    with pytest.raises(CloudError):
        a.put(PID, b"v2")


# --- capabilities / is_connected -------------------------------------------- #


def test_capabilities_full_featured():
    caps = FakeCloudAdapter().capabilities()
    assert isinstance(caps, CloudCapabilities)
    assert caps.supports_named_revisions is True
    assert caps.supports_revision_delete is True
    assert caps.max_versions_per_call == MAX_CLOUD_VERSIONS
    assert caps.change_feed_scope == "project"
    assert caps.supports_optimistic_concurrency is True


def test_is_connected_reflects_flag():
    assert FakeCloudAdapter(connected=True).is_connected() is True
    assert FakeCloudAdapter(connected=False).is_connected() is False


# --- recovery slot: distinct from history, crash-safe ----------------------- #


def test_recovery_slot_round_trip_in_memory():
    a = FakeCloudAdapter()
    assert a.get_recovery(PID) is None
    a.put_recovery(PID, b"recovery-bytes")
    assert a.get_recovery(PID) == b"recovery-bytes"


def test_recovery_does_not_clobber_latest_version():
    a = FakeCloudAdapter()
    v0 = a.put(PID, b"explicit-save")
    a.put_recovery(PID, b"unsaved-work")
    # Recovery is stored separately; the last explicit version is untouched.
    assert a.latest(PID).version_id == v0.version_id
    assert a.get(PID, v0.version_id) == b"explicit-save"
    assert a.get_recovery(PID) == b"unsaved-work"


def test_get_recovery_unknown_project_is_none():
    a = FakeCloudAdapter()
    assert a.get_recovery("nope") is None


def test_latest_on_recovery_only_project_raises():
    # A project that exists (recovery written) but has no explicit version:
    # latest() surfaces the empty-history VersionHistoryError as a CloudError.
    a = FakeCloudAdapter()
    a.put_recovery(PID, b"rec")
    with pytest.raises(CloudError):
        a.latest(PID)


def test_delete_in_memory_project():
    # root=None branch of delete (no filesystem cleanup path taken).
    a = FakeCloudAdapter()
    a.put(PID, b"v0")
    a.delete(PID)
    assert a.list_versions(PID) == ()


def test_restart_recovers_recovery_only_project(tmp_path):
    # Filesystem project with a recovery sidecar but no versions.json index:
    # the load path finds recovery and no history.
    first = FakeCloudAdapter(tmp_path)
    first.put_recovery(PID, b"only-recovery")
    restarted = FakeCloudAdapter(tmp_path)
    assert restarted.get_recovery(PID) == b"only-recovery"
    assert restarted.list_versions(PID) == ()


def test_load_ignores_stray_files_at_root(tmp_path):
    # A non-directory entry at the adapter root is skipped by the loader.
    (tmp_path / "stray.txt").write_text("ignore me", encoding="utf-8")
    a = FakeCloudAdapter(tmp_path)
    assert a.list_versions("stray.txt") == ()


# --- restart-recovery recipe (implementation report §7) --------------------- #


def test_recovery_survives_unclean_restart(tmp_path):
    # Filesystem-backed: put a recovery, then construct a NEW adapter over the
    # same root (a simulated unclean restart) and assert the recovery is
    # discovered and the last explicit version is unchanged (no clobber).
    first = FakeCloudAdapter(tmp_path)
    v0 = first.put(PID, b"explicit-v0")
    first.put_recovery(PID, b"unsaved-recovery")

    restarted = FakeCloudAdapter(tmp_path)
    assert restarted.get_recovery(PID) == b"unsaved-recovery"
    assert restarted.latest(PID).version_id == v0.version_id
    assert restarted.get(PID, v0.version_id) == b"explicit-v0"


def test_versions_survive_restart_ordered(tmp_path):
    first = FakeCloudAdapter(tmp_path)
    first.put(PID, b"v0")
    first.put(PID, b"v1")
    first.put(PID, b"v2")

    restarted = FakeCloudAdapter(tmp_path)
    versions = restarted.list_versions(PID)
    assert [v.ordinal for v in versions] == [0, 1, 2]
    # Next put continues the monotonic marker/ordinal sequence.
    v3 = restarted.put(PID, b"v3")
    assert v3.ordinal == 3
    assert v3.created_marker == 3


def test_in_memory_mode_does_not_persist(tmp_path):
    # root=None never touches the filesystem; nothing survives a "restart".
    a = FakeCloudAdapter()
    a.put(PID, b"v0")
    fresh = FakeCloudAdapter()
    assert fresh.list_versions(PID) == ()


# --- regression: Windows blob-filename bug ---------------------------------- #


def test_regression_blob_keyed_by_ordinal_not_version_id(tmp_path):
    """Blobs are stored under ``<ordinal>.blob`` on disk, never under a filename
    derived from ``version_id`` — which is ``"{project_id}:{ordinal}"`` and whose
    ``:`` is an INVALID filename character on Windows (the underlying fix).
    """
    a = FakeCloudAdapter(tmp_path)
    v0 = a.put(PID, b"v0")
    v1 = a.put(PID, b"v1")

    # The version_id contains the Windows-invalid ':' separator ...
    assert ":" in v0.version_id
    pdir = tmp_path / PID
    # ... yet the on-disk blob files are named by ordinal (always filename-safe).
    assert (pdir / "0.blob").exists()
    assert (pdir / "1.blob").exists()
    # No file is named after a ':'-bearing version_id (would be illegal on NTFS).
    on_disk = {p.name for p in pdir.iterdir()}
    assert not any(":" in name for name in on_disk)
    # And the ordinal-keyed blobs remain retrievable by version_id via the index.
    assert a.get(PID, v0.version_id) == b"v0"
    assert a.get(PID, v1.version_id) == b"v1"
