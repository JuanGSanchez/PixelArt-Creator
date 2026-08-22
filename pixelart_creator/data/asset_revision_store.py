"""Append-only, content-addressable asset-revision store — zero Qt (S11; ADR-0030 §6).

Record and retrieve an asset's revisions (REQ-P11-DATA-004). The store composes two
shipped primitives — the pure
:class:`~pixelart_creator.logic.asset_version.AssetVersionHistory` model (immutable,
ordered, content-hash-addressed DAG) and the
:class:`~pixelart_creator.data.asset_cas.ContentAddressableStore` (write-once, dedup,
hash-verified) — and adds the append-only recording semantics:

* :meth:`~AssetRevisionStore.record` stores the revision's bytes **once** in the CAS
  (dedup: two revisions with identical canonical bytes share one blob) and appends an
  immutable :class:`~pixelart_creator.logic.asset_version.AssetRevision` descriptor
  keyed by its ``content_hash``. Re-recording bytes whose hash equals the **current
  head** is a **dedup no-op** — no new revision, no new blob (the acceptance
  change-detector, ADR-0030 §6).
* :meth:`~AssetRevisionStore.fetch` returns a recorded revision's
  **content-hash-verified** bytes (via the CAS's recompute-and-compare) — a blob whose
  content hash no longer matches its record is rejected with
  :class:`AssetRevisionStoreError` (tamper defence).
* The store is **append-only**: it never mutates or deletes a revision in place; each
  :meth:`record` yields a *new* :class:`AssetVersionHistory` value for the asset.

Asset revisions are stored in this content-addressable store **only** — they never
route through the Phase-10 live-collaboration CRDT (this module imports no CRDT/cloud
code, so ``check_layering`` confirms it is Qt-free ``data/`` outside the collab path).
Zero Qt; the whole store is CI-testable headless with no network/credentials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Union

from pixelart_creator.data.asset_cas import CasError, ContentAddressableStore
from pixelart_creator.data.asset_revision_io import (
    AssetRevisionIOError,
    load_histories,
    write_history,
    write_index,
)
from pixelart_creator.logic.asset_version import (
    AssetRevision,
    AssetVersionError,
    AssetVersionHistory,
)
from pixelart_creator.logic.content_hash import content_hash

__all__ = [
    "AssetRevisionStoreError",
    "AssetRevisionStore",
]


class AssetRevisionStoreError(ValueError):
    """Raised on an invalid revision record, an unknown asset/revision, or tamper."""


class AssetRevisionStore:
    """An append-only, content-addressable revision store over a CAS + version model."""

    def __init__(self, cas: Optional[ContentAddressableStore] = None) -> None:
        """Create a store over ``cas``, defaulting to a fresh in-memory CAS.

        Args:
            cas: The content-addressable store the revision bytes are written to /
                fetched from. When omitted, an in-memory
                :class:`ContentAddressableStore` (local backend) is used.

        Raises:
            AssetRevisionStoreError: If ``cas`` is not a
                :class:`ContentAddressableStore`.
        """
        if cas is None:
            cas = ContentAddressableStore()
        if not isinstance(cas, ContentAddressableStore):
            raise AssetRevisionStoreError(
                f"cas must be a ContentAddressableStore, got {cas!r}"
            )
        self._cas = cas
        self._histories: Dict[str, AssetVersionHistory] = {}
        self._root: Optional[Path] = None

    def bind_root(self, root: Union[str, Path]) -> None:
        """Bind this store to ``root`` and adopt any revision histories found there.

        Loads ``root``'s revision index/sidecars via
        :func:`~pixelart_creator.data.asset_revision_io.load_histories` and adopts
        the result into this store's in-memory histories, replacing whatever was
        held before the call. An absent index loads as an empty mapping — this
        method performs **no** ``mkdir`` and creates nothing on disk (``root`` is
        already resolved by the caller; this method neither resolves a root nor
        names a backend, ADR-0051).

        Once bound, :meth:`record` persists every recorded revision under ``root``
        (T40's durable half of ``REQ-P11-DATA-008``).

        Args:
            root: The already-resolved project root revisions are persisted under.

        Raises:
            AssetRevisionStoreError: If the index or a sidecar under ``root`` is
                malformed.
        """
        root_path = Path(root)
        try:
            histories = load_histories(root_path)
        except AssetRevisionIOError as exc:
            raise AssetRevisionStoreError(
                f"cannot bind revision store to {str(root_path)!r}: {exc}"
            ) from exc
        self._root = root_path
        self._histories = dict(histories)

    def _require_asset_id(self, asset_id: object) -> str:
        if not isinstance(asset_id, str) or not asset_id:
            raise AssetRevisionStoreError(
                f"asset_id must be a non-empty str, got {asset_id!r}"
            )
        return asset_id

    def record(
        self,
        asset_id: str,
        blob: bytes,
        *,
        created_marker: int,
        author: Optional[str] = None,
    ) -> AssetRevision:
        """Record a revision of ``asset_id`` from ``blob``; return its descriptor.

        Stores ``blob`` once in the CAS (dedup by content hash) and appends an immutable
        revision descriptor whose ``parent_hash`` is the prior head's content hash (or
        ``None`` for the first revision). **Re-recording bytes whose content hash equals
        the current head is a dedup no-op** — the existing head is returned unchanged,
        no new revision or blob is created (REQ-P11-DATA-004).

        Args:
            asset_id: The asset the revision belongs to (non-empty str).
            blob: The revision's canonical bytes (``<= MAX_BLOB_BYTES``).
            created_marker: An opaque monotonic ordering marker supplied by the caller.
            author: An optional author label.

        Returns:
            The recorded revision (or, on a dedup no-op, the existing head)
            :class:`AssetRevision`.

        Raises:
            AssetRevisionStoreError: If ``asset_id`` is invalid, ``blob`` is not bytes,
                exceeds the CAS blob cap, or the appended revision breaks a
                version-model invariant.
        """
        asset_id = self._require_asset_id(asset_id)
        if not isinstance(blob, (bytes, bytearray)):
            raise AssetRevisionStoreError(
                f"blob must be bytes, got {type(blob).__name__}"
            )
        payload = bytes(blob)
        digest = content_hash(payload)
        history = self._histories.get(asset_id, AssetVersionHistory())

        # Dedup against the current head: identical bytes create no new revision/blob.
        if not history.is_empty() and history.is_unchanged(digest):
            return history.head()

        parent_hash = history.head().content_hash if not history.is_empty() else None
        try:
            stored_digest = self._cas.put(payload)
        except CasError as exc:
            raise AssetRevisionStoreError(
                f"cannot store revision bytes for {asset_id!r}: {exc}"
            ) from exc
        try:
            revision = AssetRevision(
                asset_id=asset_id,
                content_hash=stored_digest,
                created_marker=created_marker,
                parent_hash=parent_hash,
                author=author,
            )
            updated = history.append(revision)
        except AssetVersionError as exc:
            raise AssetRevisionStoreError(
                f"cannot record revision for {asset_id!r}: {exc}"
            ) from exc

        if self._root is not None:
            try:
                write_history(self._root, asset_id, updated)
                write_index(self._root, sorted(set(self._histories) | {asset_id}))
            except AssetRevisionIOError as exc:
                raise AssetRevisionStoreError(
                    f"cannot persist revision for {asset_id!r}: {exc}"
                ) from exc

        self._histories[asset_id] = updated
        return revision

    def history(self, asset_id: str) -> AssetVersionHistory:
        """Return the asset's immutable revision history — empty when unknown."""
        asset_id = self._require_asset_id(asset_id)
        return self._histories.get(asset_id, AssetVersionHistory())

    def head(self, asset_id: str) -> AssetRevision:
        """Return the asset's most recent revision.

        Raises:
            AssetRevisionStoreError: If the asset has no recorded revisions.
        """
        asset_id = self._require_asset_id(asset_id)
        history = self._histories.get(asset_id, AssetVersionHistory())
        if history.is_empty():
            raise AssetRevisionStoreError(f"asset {asset_id!r} has no revisions")
        return history.head()

    def fetch(self, asset_id: str, content_hash_key: str) -> bytes:
        """Return the content-hash-verified bytes of a recorded revision.

        Args:
            asset_id: The asset whose revision is fetched.
            content_hash_key: The ``content_hash`` of the recorded revision to fetch.

        Returns:
            The revision's bytes, verified: their recomputed hash equals the recorded
            hash (the CAS rejects a mismatch — tamper defence).

        Raises:
            AssetRevisionStoreError: If the asset/revision is unknown, or the fetched
                bytes do not verify against the recorded content hash.
        """
        asset_id = self._require_asset_id(asset_id)
        history = self._histories.get(asset_id, AssetVersionHistory())
        try:
            history.by_hash(content_hash_key)
        except AssetVersionError as exc:
            raise AssetRevisionStoreError(
                f"asset {asset_id!r} has no revision {content_hash_key!r}: {exc}"
            ) from exc
        try:
            return self._cas.get(content_hash_key)
        except CasError as exc:
            raise AssetRevisionStoreError(
                f"cannot fetch revision {content_hash_key!r} of {asset_id!r}: {exc}"
            ) from exc
