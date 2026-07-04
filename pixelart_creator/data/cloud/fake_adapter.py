"""Local-filesystem / in-memory fake cloud adapter — the CI contract (zero Qt, S11).

Phase-10 Slice A (ADR-0026 §2/§4; spec REQ-P10-DATA-002/-003/-004/-005). A fully
functional adapter that implements the **whole**
:class:`~pixelart_creator.data.cloud.port.CloudPort`
with **no network and no credentials**, so the entire Slice-A contract — ``.pixproj``
round-trip, ordered version history, crash-safe autosave/recovery, defensive load,
provider isolation — is exercised deterministically in CI (Article IV). It is the
fixed Slice-A deliverable; real Drive/OneDrive/Dropbox adapters (out of Slice A) will
implement the same port later, credential-gated.

Two modes:

* **In-memory** (``root=None``): state lives in dicts — fast, deterministic, ideal
  for round-trip / version-history tests. Does not survive a process restart.
* **Filesystem-backed** (``root=<dir>``): versions + the recovery sidecar persist
  under ``root`` via an **atomic temp-write + fsync + os.replace** (Windows-safe,
  ADR-0026 §4); a *new* adapter instance over the same ``root`` therefore observes
  state written before an "unclean restart" — the recovery-survives-restart contract
  (REQ-P10-DATA-004). The recovery slot is stored **separately** from version blobs,
  so restoring it never clobbers the last explicit version.

The ``.pixproj`` bytes are transported as-is (PIO-1, no new format). Version
``created_marker`` values are a deterministic monotonic counter (never a wall-clock
read), keeping the adapter reproducible.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from pixelart_creator.data.cloud.port import (
    CloudCapabilities,
    CloudDataError,
    CloudError,
    CloudPort,
)
from pixelart_creator.logic.constants import MAX_CLOUD_PROJECT_BYTES, MAX_CLOUD_VERSIONS
from pixelart_creator.logic.version_history import (
    CloudVersion,
    VersionHistory,
    VersionHistoryError,
)

__all__ = ["FakeCloudAdapter"]

_INDEX_NAME = "versions.json"
_RECOVERY_NAME = "recovery.blob"
_BLOB_SUFFIX = ".blob"


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (temp + fsync + os.replace).

    An interrupted write never corrupts the last good file (ADR-0026 §4;
    ``os.replace`` is a cross-platform atomic rename, Windows-safe).
    """
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _require_bytes(blob: object) -> bytes:
    if not isinstance(blob, (bytes, bytearray)):
        raise CloudError(f"blob must be bytes, got {type(blob).__name__}")
    return bytes(blob)


def _check_size(blob: bytes) -> None:
    if len(blob) > MAX_CLOUD_PROJECT_BYTES:
        raise CloudDataError(
            f"blob {len(blob)} bytes exceeds MAX_CLOUD_PROJECT_BYTES "
            f"({MAX_CLOUD_PROJECT_BYTES})"
        )


def _require_project_id(project_id: object) -> str:
    if not isinstance(project_id, str) or not project_id:
        raise CloudError(f"project_id must be a non-empty str, got {project_id!r}")
    # Guard against path traversal in the filesystem-backed mode.
    if "/" in project_id or "\\" in project_id or project_id in (".", ".."):
        raise CloudError(f"project_id must not contain path separators: {project_id!r}")
    return project_id


class _ProjectState:
    """In-memory state for one project: ordered history + blobs + recovery."""

    def __init__(self) -> None:
        self.history: VersionHistory = VersionHistory()
        self.blobs: Dict[str, bytes] = {}
        self.recovery: Optional[bytes] = None
        self.next_marker: int = 0


class FakeCloudAdapter(CloudPort):
    """A deterministic local/in-memory :class:`CloudPort` (no network/credentials)."""

    def __init__(
        self,
        root: Optional[Union[str, Path]] = None,
        *,
        connected: bool = True,
    ) -> None:
        """Create an adapter.

        Args:
            root: If given, a directory the adapter persists to (state survives a
                new-instance "restart"). If ``None``, state is purely in-memory.
            connected: The provider-agnostic connected flag reported by
                :meth:`is_connected` (the fake adapter needs no real auth).
        """
        self._root: Optional[Path] = Path(root) if root is not None else None
        self._connected = bool(connected)
        self._projects: Dict[str, _ProjectState] = {}
        if self._root is not None:
            self._root.mkdir(parents=True, exist_ok=True)
            self._load_all()

    # -- persistence ------------------------------------------------------- #

    def _project_dir(self, project_id: str) -> Path:
        assert self._root is not None
        return self._root / project_id

    def _load_all(self) -> None:
        assert self._root is not None
        for child in sorted(self._root.iterdir()):
            if child.is_dir():
                self._load_project(child.name)

    def _load_project(self, project_id: str) -> None:
        assert self._root is not None
        pdir = self._project_dir(project_id)
        state = _ProjectState()
        index_path = pdir / _INDEX_NAME
        if index_path.exists():
            raw = json.loads(index_path.read_text(encoding="utf-8"))
            versions = []
            max_marker = -1
            for entry in raw.get("versions", []):
                version = CloudVersion(
                    version_id=entry["version_id"],
                    ordinal=entry["ordinal"],
                    created_marker=entry["created_marker"],
                    size_bytes=entry["size_bytes"],
                    is_pinned=entry.get("is_pinned", False),
                    parent_version_id=entry.get("parent_version_id"),
                    remote_revision_id=entry.get("remote_revision_id"),
                )
                versions.append(version)
                max_marker = max(max_marker, version.created_marker)
                blob_path = pdir / f"{version.ordinal}{_BLOB_SUFFIX}"
                state.blobs[version.version_id] = blob_path.read_bytes()
            state.history = VersionHistory(versions=tuple(versions))
            state.next_marker = max_marker + 1
        recovery_path = pdir / _RECOVERY_NAME
        if recovery_path.exists():
            state.recovery = recovery_path.read_bytes()
        self._projects[project_id] = state

    def _persist_index(self, project_id: str, state: _ProjectState) -> None:
        if self._root is None:
            return
        pdir = self._project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        payload = {
            "versions": [
                {
                    "version_id": v.version_id,
                    "ordinal": v.ordinal,
                    "created_marker": v.created_marker,
                    "size_bytes": v.size_bytes,
                    "is_pinned": v.is_pinned,
                    "parent_version_id": v.parent_version_id,
                    "remote_revision_id": v.remote_revision_id,
                }
                for v in state.history.versions
            ]
        }
        _atomic_write(pdir / _INDEX_NAME, json.dumps(payload).encode("utf-8"))

    def _persist_blob(self, project_id: str, ordinal: int, blob: bytes) -> None:
        # Blob files are named by ordinal (an int, always filename-safe) — never by
        # version_id, which may contain characters invalid in a filename (e.g. ':'
        # on Windows). The index maps version_id -> ordinal.
        if self._root is None:
            return
        pdir = self._project_dir(project_id)
        pdir.mkdir(parents=True, exist_ok=True)
        _atomic_write(pdir / f"{ordinal}{_BLOB_SUFFIX}", blob)

    # -- helpers ----------------------------------------------------------- #

    def _state(self, project_id: str) -> _ProjectState:
        state = self._projects.get(project_id)
        if state is None:
            raise CloudError(f"unknown project {project_id!r}")
        return state

    # -- CloudPort verbs --------------------------------------------------- #

    def put(
        self,
        project_id: str,
        blob: bytes,
        *,
        parent_version: Optional[str] = None,
    ) -> CloudVersion:
        """Append a new version; enforce size, concurrency, and history caps."""
        project_id = _require_project_id(project_id)
        data = _require_bytes(blob)
        _check_size(data)
        state = self._projects.setdefault(project_id, _ProjectState())

        if parent_version is not None:
            current = (
                state.history.versions[-1].version_id
                if state.history.versions
                else None
            )
            if parent_version != current:
                raise CloudError(
                    f"optimistic-concurrency conflict: parent_version "
                    f"{parent_version!r} is not the current latest {current!r}"
                )

        ordinal = (
            state.history.versions[-1].ordinal + 1 if state.history.versions else 0
        )
        marker = state.next_marker
        version_id = f"{project_id}:{ordinal}"
        parent_id = (
            state.history.versions[-1].version_id if state.history.versions else None
        )
        version = CloudVersion(
            version_id=version_id,
            ordinal=ordinal,
            created_marker=marker,
            size_bytes=len(data),
            parent_version_id=parent_id,
        )
        try:
            new_history = state.history.append(version)
        except VersionHistoryError as exc:
            raise CloudError(str(exc)) from exc

        state.history = new_history
        state.blobs[version_id] = data
        state.next_marker = marker + 1
        self._persist_blob(project_id, ordinal, data)
        self._persist_index(project_id, state)
        return version

    def get(self, project_id: str, version_id: str) -> bytes:
        """Return a version's stored ``.pixproj`` bytes (size-checked, untrusted)."""
        project_id = _require_project_id(project_id)
        state = self._state(project_id)
        blob = state.blobs.get(version_id)
        if blob is None:
            raise CloudError(
                f"unknown version {version_id!r} for project {project_id!r}"
            )
        _check_size(blob)
        return blob

    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]:
        """Return the ordered version history (empty tuple for an unknown project)."""
        project_id = _require_project_id(project_id)
        state = self._projects.get(project_id)
        return state.history.versions if state is not None else ()

    def latest(self, project_id: str) -> CloudVersion:
        """Return the most recent version (``CloudError`` if none)."""
        project_id = _require_project_id(project_id)
        state = self._state(project_id)
        try:
            return state.history.latest()
        except VersionHistoryError as exc:
            raise CloudError(str(exc)) from exc

    def delete(self, project_id: str) -> None:
        """Delete a project's versions + recovery slot (``CloudError`` if unknown)."""
        project_id = _require_project_id(project_id)
        if project_id not in self._projects:
            raise CloudError(f"unknown project {project_id!r}")
        del self._projects[project_id]
        if self._root is not None:
            pdir = self._project_dir(project_id)
            if pdir.exists():
                for child in sorted(pdir.iterdir()):
                    child.unlink()
                pdir.rmdir()

    def put_recovery(self, project_id: str, blob: bytes) -> None:
        """Store the recovery-slot blob atomically (distinct from version history)."""
        project_id = _require_project_id(project_id)
        data = _require_bytes(blob)
        _check_size(data)
        state = self._projects.setdefault(project_id, _ProjectState())
        state.recovery = data
        if self._root is not None:
            pdir = self._project_dir(project_id)
            pdir.mkdir(parents=True, exist_ok=True)
            _atomic_write(pdir / _RECOVERY_NAME, data)

    def get_recovery(self, project_id: str) -> Optional[bytes]:
        """Return the recovery-slot bytes, or ``None`` if none exists."""
        project_id = _require_project_id(project_id)
        state = self._projects.get(project_id)
        if state is None or state.recovery is None:
            return None
        _check_size(state.recovery)
        return state.recovery

    def capabilities(self) -> CloudCapabilities:
        """Return the fake adapter's deterministic, full-featured capability set."""
        return CloudCapabilities(
            supports_named_revisions=True,
            supports_revision_delete=True,
            max_versions_per_call=MAX_CLOUD_VERSIONS,
            change_feed_scope="project",
            supports_optimistic_concurrency=True,
        )

    def is_connected(self) -> bool:
        """Return the provider-agnostic connected flag (no token involved)."""
        return self._connected
