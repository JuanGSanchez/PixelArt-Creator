"""Unit tests for :mod:`pixelart_creator.data.asset_storage` (S11, no Qt).

Covers the provider-agnostic :class:`BlobBackend` port and the offline
:class:`LocalBlobBackend` (ADR-0032; REQ-P11-DATA-006): in-memory + filesystem
put/get/has, write-once dedup, malformed-key rejection (Article VII path-traversal
defence — a hex-only key can never escape ``root``), and non-bytes / missing-blob /
I/O error paths.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.asset_storage import (
    AssetStorageError,
    BlobBackend,
    LocalBlobBackend,
)
from pixelart_creator.logic.content_hash import content_hash

VALID_KEY = content_hash(b"payload")
BAD_KEY = "not-a-valid-hash"


# --------------------------------------------------------------------------- #
# The port (ABC)                                                               #
# --------------------------------------------------------------------------- #


def test_blob_backend_is_abstract() -> None:
    with pytest.raises(TypeError):
        BlobBackend()  # type: ignore[abstract]


class _SuperCaller(BlobBackend):
    """A concrete backend that defers to the ABC's (no-op) method bodies."""

    def put_blob(self, content_hash: str, blob: bytes) -> None:
        return super().put_blob(content_hash, blob)

    def get_blob(self, content_hash: str) -> bytes:
        return super().get_blob(content_hash)  # type: ignore[return-value]

    def has_blob(self, content_hash: str) -> bool:
        return super().has_blob(content_hash)  # type: ignore[return-value]


def test_abstract_method_bodies_are_noops() -> None:
    backend = _SuperCaller()
    assert backend.put_blob(VALID_KEY, b"x") is None
    assert backend.get_blob(VALID_KEY) is None
    assert backend.has_blob(VALID_KEY) is None


# --------------------------------------------------------------------------- #
# LocalBlobBackend — in-memory (default)                                       #
# --------------------------------------------------------------------------- #


def test_memory_put_get_has_roundtrip() -> None:
    backend = LocalBlobBackend()
    assert backend.has_blob(VALID_KEY) is False
    backend.put_blob(VALID_KEY, b"payload")
    assert backend.has_blob(VALID_KEY) is True
    assert backend.get_blob(VALID_KEY) == b"payload"


def test_memory_put_accepts_bytearray() -> None:
    backend = LocalBlobBackend()
    backend.put_blob(VALID_KEY, bytearray(b"payload"))
    assert backend.get_blob(VALID_KEY) == b"payload"


def test_memory_put_is_write_once_dedup() -> None:
    backend = LocalBlobBackend()
    backend.put_blob(VALID_KEY, b"first")
    backend.put_blob(VALID_KEY, b"second")  # setdefault -> no overwrite
    assert backend.get_blob(VALID_KEY) == b"first"


def test_memory_get_missing_raises() -> None:
    with pytest.raises(AssetStorageError):
        LocalBlobBackend().get_blob(VALID_KEY)


def test_memory_rejects_bad_key_on_every_verb() -> None:
    backend = LocalBlobBackend()
    with pytest.raises(AssetStorageError):
        backend.put_blob(BAD_KEY, b"x")
    with pytest.raises(AssetStorageError):
        backend.get_blob(BAD_KEY)
    with pytest.raises(AssetStorageError):
        backend.has_blob(BAD_KEY)


def test_memory_put_rejects_non_bytes() -> None:
    with pytest.raises(AssetStorageError):
        LocalBlobBackend().put_blob(VALID_KEY, "not-bytes")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# LocalBlobBackend — filesystem-backed                                         #
# --------------------------------------------------------------------------- #


def test_fs_put_get_has_roundtrip(tmp_path) -> None:
    backend = LocalBlobBackend(root=tmp_path)
    assert backend.has_blob(VALID_KEY) is False
    backend.put_blob(VALID_KEY, b"payload")
    assert backend.has_blob(VALID_KEY) is True
    assert backend.get_blob(VALID_KEY) == b"payload"
    # a file named by the hex key was written under root (never escaping it)
    assert (tmp_path / f"{VALID_KEY}.blob").is_file()


def test_fs_put_is_write_once(tmp_path) -> None:
    backend = LocalBlobBackend(root=tmp_path)
    backend.put_blob(VALID_KEY, b"first")
    backend.put_blob(VALID_KEY, b"second")  # target.exists() -> early return
    assert backend.get_blob(VALID_KEY) == b"first"


def test_fs_get_missing_raises(tmp_path) -> None:
    with pytest.raises(AssetStorageError):
        LocalBlobBackend(root=tmp_path).get_blob(VALID_KEY)


def test_fs_put_wraps_os_error(tmp_path) -> None:
    # A regular file where a directory is expected -> mkdir raises OSError,
    # which the backend re-raises as AssetStorageError.
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"x")
    backend = LocalBlobBackend(root=blocker / "under-a-file")
    with pytest.raises(AssetStorageError):
        backend.put_blob(VALID_KEY, b"payload")
