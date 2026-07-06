"""Optional Phase-10 cloud-backed blob backend — local-first, zero Qt (S11; ADR-0032).

The local-first / cloud-optional storage substrate (REQ-P11-DATA-006 / CL-3).
:class:`SharedBlobBackend` implements the SAME provider-agnostic
:class:`~pixelart_creator.data.asset_storage.BlobBackend` port as
:class:`~pixelart_creator.data.asset_storage.LocalBlobBackend`, so the
:class:`~pixelart_creator.data.asset_cas.ContentAddressableStore`, catalog store, and
revision store above it are **unchanged** whether the backend is local or shared — they
never learn a provider is involved.

It composes a local backend (the offline default) with an **optional** Phase-10
``data/cloud/`` :class:`~pixelart_creator.data.cloud.port.CloudPort` as the shared
backing. The cloud backing is engaged **only when a provider is connected**
(``CloudPort.is_connected()``) — otherwise the backend is purely local, so the library
works fully offline (the acceptance "works fully offline" scenario). This is the
**only** Phase-11 module that touches ``data/cloud/``; **no provider SDK type,
credential type, or provider name appears in its signatures or above the port** — it
depends solely on the provider-agnostic ``CloudPort`` (ADR-0032 §1).

Every blob fetched from the shared backing is **content-hash-verified** (recompute +
compare) before it is returned — a cloud blob whose bytes do not hash to the requested
key is rejected with :class:`~pixelart_creator.data.asset_storage.AssetStorageError`
(cloud is untrusted input, Article VII; the acceptance "cloud-fetched blobs are
content-hash verified" scenario). Blobs are addressed content-first, so a fetched cloud
blob is also cached into the local backend (write-once) to keep subsequent reads
offline. Zero Qt; CI-testable headless against the shipped fake cloud adapter (no
network/credentials).
"""

from __future__ import annotations

from typing import Optional

from pixelart_creator.data.asset_storage import (
    AssetStorageError,
    BlobBackend,
    LocalBlobBackend,
)
from pixelart_creator.data.cloud.port import CloudError, CloudPort
from pixelart_creator.logic.content_hash import content_hash as compute_content_hash
from pixelart_creator.logic.content_hash import is_valid_hash

__all__ = [
    "SharedBlobBackend",
]


class SharedBlobBackend(BlobBackend):
    """A :class:`BlobBackend` over a local store plus optional shared cloud storage."""

    def __init__(
        self,
        port: Optional[CloudPort] = None,
        *,
        local: Optional[BlobBackend] = None,
    ) -> None:
        """Create the backend over an optional cloud ``port`` and a ``local`` store.

        Args:
            port: The optional provider-agnostic
                :class:`~pixelart_creator.data.cloud.port.CloudPort` used as shared
                backing. The cloud path is engaged only while ``port.is_connected()``;
                when ``port`` is ``None`` or disconnected, the backend is purely local.
            local: The local backend (the offline default). When omitted, an in-memory
                :class:`LocalBlobBackend` is used.

        Raises:
            AssetStorageError: If ``local`` is not a :class:`BlobBackend` or ``port`` is
                not a :class:`CloudPort`.
        """
        if local is None:
            local = LocalBlobBackend()
        if not isinstance(local, BlobBackend):
            raise AssetStorageError(f"local must be a BlobBackend, got {local!r}")
        if port is not None and not isinstance(port, CloudPort):
            raise AssetStorageError(f"port must be a CloudPort or None, got {port!r}")
        self._local = local
        self._port = port

    def _require_valid_key(self, content_hash: str) -> None:
        """Raise :class:`AssetStorageError` unless ``content_hash`` is a valid key."""
        if not is_valid_hash(content_hash):
            raise AssetStorageError(
                f"content_hash must be a valid hex hash key, got {content_hash!r}"
            )

    def _cloud_active(self) -> bool:
        """Return whether a connected cloud provider backs this backend."""
        return self._port is not None and self._port.is_connected()

    def _cloud_has(self, content_hash: str) -> bool:
        """Return whether the shared backing already holds ``content_hash``."""
        assert self._port is not None
        return bool(self._port.list_versions(content_hash))

    def _cloud_get(self, content_hash: str) -> bytes:
        """Fetch + content-hash-verify a blob from the shared backing.

        Raises:
            AssetStorageError: If the shared backing has no such blob, or the fetched
                bytes do not hash to ``content_hash`` (tamper defence).
        """
        assert self._port is not None
        versions = self._port.list_versions(content_hash)
        if not versions:
            raise AssetStorageError(f"no shared blob for {content_hash!r}")
        # Blobs are content-addressed and written write-once, so the history holds a
        # single version; fetch the latest defensively either way.
        version = versions[-1]
        try:
            blob = self._port.get(content_hash, version.version_id)
        except CloudError as exc:
            raise AssetStorageError(
                f"cannot fetch shared blob {content_hash!r}: {exc}"
            ) from exc
        actual = compute_content_hash(blob)
        if actual != content_hash:
            raise AssetStorageError(
                f"shared blob content-hash mismatch: requested {content_hash!r}, "
                f"got {actual!r}"
            )
        return blob

    def put_blob(self, content_hash: str, blob: bytes) -> None:
        """Store ``blob`` under ``content_hash`` (write-once; existing key = no-op).

        Always writes to the local backend; when a provider is connected, also backs the
        write to the shared storage (write-once — an existing shared blob is not
        re-uploaded).
        """
        self._require_valid_key(content_hash)
        if not isinstance(blob, (bytes, bytearray)):
            raise AssetStorageError(f"blob must be bytes, got {type(blob).__name__}")
        payload = bytes(blob)
        self._local.put_blob(content_hash, payload)
        if self._cloud_active() and not self._cloud_has(content_hash):
            try:
                self._port.put(content_hash, payload)  # type: ignore[union-attr]
            except CloudError as exc:
                raise AssetStorageError(
                    f"cannot back up shared blob {content_hash!r}: {exc}"
                ) from exc

    def get_blob(self, content_hash: str) -> bytes:
        """Return the bytes stored under ``content_hash`` (local first, then shared).

        A blob served from the shared backing is content-hash-verified and cached to the
        local backend so subsequent reads stay offline.

        Raises:
            AssetStorageError: If neither the local backend nor the connected shared
                backing holds the blob, or a shared blob fails hash verification.
        """
        self._require_valid_key(content_hash)
        if self._local.has_blob(content_hash):
            return self._local.get_blob(content_hash)
        if self._cloud_active():
            blob = self._cloud_get(content_hash)
            self._local.put_blob(content_hash, blob)
            return blob
        raise AssetStorageError(f"no blob for {content_hash!r}")

    def has_blob(self, content_hash: str) -> bool:
        """Return whether the local backend or the connected shared backing holds it."""
        self._require_valid_key(content_hash)
        if self._local.has_blob(content_hash):
            return True
        if self._cloud_active():
            return self._cloud_has(content_hash)
        return False
