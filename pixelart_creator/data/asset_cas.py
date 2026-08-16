"""Content-addressable store (CAS) over a blob backend — zero Qt (S11; ADR-0030 §4).

Store asset bytes **once**, keyed by their content hash (the Git-blob / IPFS-CID model,
Researcher §4.1; REQ-P11-DATA-004/-005). :class:`ContentAddressableStore` composes a
:class:`~pixelart_creator.data.asset_storage.BlobBackend` (the local default when none
is
given) and adds the integrity layer the dumb backend lacks:

* :meth:`~ContentAddressableStore.put` computes the content hash, rejects a blob larger
  than :data:`~pixelart_creator.logic.constants.MAX_BLOB_BYTES` (Article VII), and
  stores
  the bytes only if the hash is new — **writing an existing hash is a dedup no-op** (the
  reference-not-copy foundation: two projects referencing the same content share one
  blob).
* :meth:`~ContentAddressableStore.get` fetches by hash and **content-hash-verifies** the
  bytes (recompute + compare); a mismatch is rejected with :class:`CasError`
  (tamper/corruption defence, Researcher §5), on both the local and the shared backend.

Because the store is backend-agnostic, it runs unchanged against the offline
:class:`LocalBlobBackend` or an optional Phase-10-shared backend (ADR-0032). Zero Qt;
the whole store is CI-testable headless with no network/credentials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pixelart_creator.data.asset_storage import (
    AssetStorageError,
    BlobBackend,
    LocalBlobBackend,
    default_asset_root,
)
from pixelart_creator.logic.constants import MAX_BLOB_BYTES
from pixelart_creator.logic.content_hash import content_hash, is_valid_hash

__all__ = [
    "CasError",
    "ContentAddressableStore",
    "default_content_store",
]


class CasError(ValueError):
    """Raised on an oversized blob, a missing blob, or a content-hash mismatch."""


class ContentAddressableStore:
    """A write-once, content-hash-verified blob store over a :class:`BlobBackend`."""

    def __init__(self, backend: Optional[BlobBackend] = None) -> None:
        """Create a store over ``backend``, defaulting to an in-memory backend.

        When ``backend`` is omitted, an in-memory :class:`LocalBlobBackend` is used.

        Raises:
            CasError: If ``backend`` is not a :class:`BlobBackend`.
        """
        if backend is None:
            backend = LocalBlobBackend()
        if not isinstance(backend, BlobBackend):
            raise CasError(f"backend must be a BlobBackend, got {backend!r}")
        self._backend = backend

    def put(self, blob: bytes) -> str:
        """Store ``blob`` and return its content hash (existing hash = dedup no-op).

        Args:
            blob: The canonical asset bytes to store; ``<= MAX_BLOB_BYTES``.

        Returns:
            The content hash the bytes are addressed by.

        Raises:
            CasError: If ``blob`` is not bytes or exceeds :data:`MAX_BLOB_BYTES`.
        """
        if not isinstance(blob, (bytes, bytearray)):
            raise CasError(f"blob must be bytes, got {type(blob).__name__}")
        if len(blob) > MAX_BLOB_BYTES:
            raise CasError(
                f"blob is {len(blob)} bytes, exceeds MAX_BLOB_BYTES ({MAX_BLOB_BYTES})"
            )
        payload = bytes(blob)
        digest = content_hash(payload)
        if not self._backend.has_blob(digest):
            self._backend.put_blob(digest, payload)
        return digest

    def get(self, content_hash_key: str) -> bytes:
        """Return the bytes for ``content_hash_key``, content-hash-verified.

        Args:
            content_hash_key: The content hash to fetch.

        Returns:
            The stored bytes (verified: their recomputed hash equals the key).

        Raises:
            CasError: If the key is malformed, absent, exceeds :data:`MAX_BLOB_BYTES`,
                or the fetched bytes do not hash to the requested key (tamper defence).
        """
        if not is_valid_hash(content_hash_key):
            raise CasError(
                f"content hash must be a valid hex hash, got {content_hash_key!r}"
            )
        try:
            blob = self._backend.get_blob(content_hash_key)
        except AssetStorageError as exc:
            raise CasError(f"no blob for {content_hash_key!r}: {exc}") from exc
        if len(blob) > MAX_BLOB_BYTES:
            raise CasError(
                f"fetched blob is {len(blob)} bytes, exceeds MAX_BLOB_BYTES "
                f"({MAX_BLOB_BYTES})"
            )
        actual = content_hash(blob)
        if actual != content_hash_key:
            raise CasError(
                f"content-hash mismatch: requested {content_hash_key!r}, got {actual!r}"
            )
        return blob

    def has(self, content_hash_key: str) -> bool:
        """Return whether a blob is stored under ``content_hash_key`` (never raises).

        A malformed key is treated as absent (returns ``False``) rather than raising.
        """
        if not is_valid_hash(content_hash_key):
            return False
        return self._backend.has_blob(content_hash_key)


def default_content_store(root: Optional[Path] = None) -> ContentAddressableStore:
    """Return the app's default, DURABLE asset store (D-26 / CF-119).

    ``ContentAddressableStore()`` (the bare constructor) keeps defaulting to an
    in-memory backend on purpose — many headless tests and transient-session
    callers rely on that ephemeral, disk-free construction, and changing it would
    make every such caller write real files to the host filesystem as a side
    effect (never acceptable for a test run). This factory is the SEPARATE,
    explicit "app default": a filesystem-backed store, so an asset put through it
    survives a restart instead of ending with the session.

    Args:
        root: The filesystem root the store's :class:`LocalBlobBackend` is
            rooted at. When omitted (``None``), defaults to
            :func:`~pixelart_creator.data.asset_storage.default_asset_root` —
            today's behaviour is unchanged. Pass an explicit root to build the
            store over a different location (e.g. a ``ui``-resolved
            ``QStandardPaths`` directory injected as a :class:`pathlib.Path`,
            per the D-26 placement ruling: this factory computes nothing Qt and
            performs no ``mkdir`` itself — directory creation stays deferred to
            :meth:`~pixelart_creator.data.asset_storage.LocalBlobBackend.put_blob`,
            on first write).

    Production wiring (construction-time, ui-side — REQ-P11-DATA-006/-007):
    ``ui/main_window.py`` should construct its asset store via this factory,
    passing a ``QStandardPaths``-resolved root (the Favourites precedent,
    ADR-0004) instead of the bare ``ContentAddressableStore()`` it uses today —
    never by composing ``ContentAddressableStore(LocalBlobBackend(path))``
    directly in ``ui/``.
    """
    resolved_root = root if root is not None else default_asset_root()
    return ContentAddressableStore(LocalBlobBackend(resolved_root))
