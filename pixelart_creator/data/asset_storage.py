# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Content-addressable blob storage port + local backend — zero Qt (S11; ADR-0032).

The local-vs-cloud seam (REQ-P11-DATA-006 / CL-3). :class:`BlobBackend` is the single
**provider-agnostic** port — the minimal content-addressable verb set keyed by a
``content_hash``: :meth:`~BlobBackend.put_blob` (write-once / dedup),
:meth:`~BlobBackend.get_blob`, :meth:`~BlobBackend.has_blob`. **No provider SDK type,
credential/token type, HTTP/network type, or ``data/cloud/`` type appears in these
signatures** (the Phase-10 provider-isolation invariant extended to assets, ADR-0032
§1);
the :class:`~pixelart_creator.data.asset_cas.ContentAddressableStore`, catalog store and
revision store all sit *above* this port, unchanged whether the backend is local or
shared.

:class:`LocalBlobBackend` is the **offline default** (ADR-0032 §2): an in-memory store,
or — when a ``root`` directory is given — a local-filesystem store that writes each blob
once to a file named by its ``content_hash``. It requires no cloud, no network, no
credentials, so Slice 1 ships and CI-tests fully headless. The optional
``SharedBlobBackend`` (Slice 3) implements the *same* port over Phase-10 shared storage.

:func:`default_asset_root` is the data layer's stdlib-only (no Qt) durable-by-default
location for the filesystem-mode backend (D-26 / CF-119): a bare ``LocalBlobBackend()``
still defaults to in-memory (unchanged — many existing tests and callers rely on that
ephemeral, disk-free construction), but a **production** construction should pass
``LocalBlobBackend(default_asset_root())`` (or a UI-resolved, platform-conventional
path — e.g. ``QStandardPaths``, the :mod:`pixelart_creator.ui.main_window` Favourites
precedent, ADR-0004) so the asset library survives a restart instead of the session
ending its blobs.

The backend is a dumb keyed store: it does **not** hash or verify (that is the CAS's
job,
ADR-0030 §4). It *does* defend its filesystem: a ``content_hash`` used as a filename is
validated to be a well-formed hash (a lowercase hex token — no separators, no ``..``),
so
a malformed key can never escape ``root`` (Article VII path-traversal defence). Zero Qt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Union

from pixelart_creator.logic.content_hash import is_valid_hash

__all__ = [
    "AssetStorageError",
    "BlobBackend",
    "LocalBlobBackend",
    "default_asset_root",
]

#: The filename suffix a filesystem-backed blob is stored under.
_BLOB_SUFFIX = ".blob"

#: The per-user application directory name under the home directory (stdlib-only,
#: no Qt), used only by :func:`default_asset_root` — mirrors the app-config
#: directory name the UI layer already falls back to (``main_window.py``'s
#: Favourites path, ADR-0004) when a platform ``QStandardPaths`` location is
#: unavailable.
_APP_DIR_NAME = ".pixelart_creator"

#: The asset-blob subdirectory name under :data:`_APP_DIR_NAME`.
_ASSET_DIR_NAME = "assets"


class AssetStorageError(ValueError):
    """Raised when a blob cannot be stored/fetched (missing key / bad key / I/O)."""


def default_asset_root() -> Path:
    """Return the data layer's default on-disk root for :class:`LocalBlobBackend`.

    A stdlib-only (zero Qt, S11), stable, per-user location —
    ``~/.pixelart_creator/assets`` — so a production caller can select durable,
    filesystem-mode asset storage (D-26 / CF-119) with no path logic of its own:
    ``LocalBlobBackend(default_asset_root())``. This function only *computes* the
    path; it never creates the directory or touches the filesystem (creation is
    deferred to :meth:`LocalBlobBackend.put_blob`, on first write).

    Neither :class:`LocalBlobBackend`'s nor
    :class:`~pixelart_creator.data.asset_cas.ContentAddressableStore`'s own bare
    constructor calls this automatically — both keep defaulting to the in-memory
    backend, so existing headless tests and any transient-session caller are
    unaffected. A caller that wants the durable default must pass it explicitly.
    """
    return Path.home() / _APP_DIR_NAME / _ASSET_DIR_NAME


def _require_valid_key(content_hash: str) -> None:
    """Raise :class:`AssetStorageError` unless ``content_hash`` is a valid hash key.

    A valid key is a lowercase hex content-hash string (Article VII): this rejects a
    type/format error early and guarantees the key is a safe filename component (no path
    separators, no ``..``, no absolute-path escape) for the filesystem backend.
    """
    if not is_valid_hash(content_hash):
        raise AssetStorageError(
            f"content_hash must be a valid hex hash key, got {content_hash!r}"
        )


class BlobBackend(ABC):
    """A provider-agnostic content-addressable blob store (no provider type leaks).

    Implementations map a ``content_hash`` key to a ``bytes`` payload. Writes are
    write-once / idempotent (dedup), so re-``put``-ing an existing hash is a no-op.
    """

    @abstractmethod
    def put_blob(self, content_hash: str, blob: bytes) -> None:
        """Store ``blob`` under ``content_hash`` (write-once; existing key = no-op)."""

    @abstractmethod
    def get_blob(self, content_hash: str) -> bytes:
        """Return the bytes stored under ``content_hash``.

        Raises:
            AssetStorageError: If ``content_hash`` is malformed or absent.
        """

    @abstractmethod
    def has_blob(self, content_hash: str) -> bool:
        """Return whether a blob is stored under ``content_hash``."""


class LocalBlobBackend(BlobBackend):
    """The offline default backend: in-memory, or local-FS when ``root`` is set.

    With no ``root`` (the default), blobs live in an in-memory dict — ideal for tests
    and
    transient sessions. With a ``root`` directory, each blob is written once to
    ``root/<content_hash>.blob`` (created on demand); the hex-only key guarantees the
    file stays within ``root`` (Article VII).
    """

    def __init__(self, root: Optional[Union[str, Path]] = None) -> None:
        """Create an in-memory backend, or a filesystem backend rooted at ``root``."""
        self._root: Optional[Path] = Path(root) if root is not None else None
        self._memory: Dict[str, bytes] = {}

    def _path_for(self, content_hash: str) -> Path:
        """Return the filesystem path for ``content_hash`` (root guaranteed set)."""
        assert self._root is not None
        return self._root / f"{content_hash}{_BLOB_SUFFIX}"

    def put_blob(self, content_hash: str, blob: bytes) -> None:
        """Store ``blob`` under ``content_hash`` (write-once; existing key = no-op)."""
        _require_valid_key(content_hash)
        if not isinstance(blob, (bytes, bytearray)):
            raise AssetStorageError(f"blob must be bytes, got {type(blob).__name__}")
        payload = bytes(blob)
        if self._root is None:
            self._memory.setdefault(content_hash, payload)
            return
        target = self._path_for(content_hash)
        if target.exists():
            return
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        except OSError as exc:
            raise AssetStorageError(
                f"cannot write blob {content_hash!r}: {exc}"
            ) from exc

    def get_blob(self, content_hash: str) -> bytes:
        """Return the bytes stored under ``content_hash`` (raises if absent)."""
        _require_valid_key(content_hash)
        if self._root is None:
            try:
                return self._memory[content_hash]
            except KeyError:
                raise AssetStorageError(f"no blob for {content_hash!r}") from None
        target = self._path_for(content_hash)
        try:
            return target.read_bytes()
        except OSError as exc:
            raise AssetStorageError(f"no blob for {content_hash!r}: {exc}") from exc

    def has_blob(self, content_hash: str) -> bool:
        """Return whether a blob is stored under ``content_hash``."""
        _require_valid_key(content_hash)
        if self._root is None:
            return content_hash in self._memory
        return self._path_for(content_hash).exists()
