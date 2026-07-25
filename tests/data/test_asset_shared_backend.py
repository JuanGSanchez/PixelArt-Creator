"""Unit tests for ``pixelart_creator.data.asset_shared_backend`` (S11, no Qt).

Covers the local-first / cloud-optional storage substrate (ADR-0032; REQ-P11-DATA-006):
the backend works fully offline against a local store when no provider is connected; a
CONNECTED provider transparently backs the same ``put``/``get``/``has`` operations
through the SAME ``BlobBackend`` port (exercised against the shipped FAKE Phase-10 cloud
adapter — no network, no credentials); a cloud-fetched blob is content-hash verified and
a mismatch is rejected; and the write path is write-once. Provider isolation ("no
provider type above the port") is not asserted by importing a provider here — it is
backed by ``check_layering --root pixelart_creator`` exit 0 and by this test depending
only on the provider-agnostic port. T11-3-07.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.asset_shared_backend import SharedBlobBackend
from pixelart_creator.data.asset_storage import AssetStorageError, LocalBlobBackend
from pixelart_creator.data.cloud.fake_adapter import FakeCloudAdapter
from pixelart_creator.data.cloud.port import CloudError
from pixelart_creator.logic.content_hash import content_hash

# --------------------------------------------------------------------------- #
# Construction / validation                                                    #
# --------------------------------------------------------------------------- #


def test_rejects_non_backend_local() -> None:
    with pytest.raises(AssetStorageError):
        SharedBlobBackend(local="not-a-backend")  # type: ignore[arg-type]


def test_rejects_non_port() -> None:
    with pytest.raises(AssetStorageError):
        SharedBlobBackend(port="not-a-port")  # type: ignore[arg-type]


def test_rejects_invalid_key_on_every_verb() -> None:
    backend = SharedBlobBackend()
    with pytest.raises(AssetStorageError):
        backend.get_blob("not-a-hash")
    with pytest.raises(AssetStorageError):
        backend.has_blob("not-a-hash")
    with pytest.raises(AssetStorageError):
        backend.put_blob("not-a-hash", b"x")


def test_put_rejects_non_bytes() -> None:
    backend = SharedBlobBackend()
    with pytest.raises(AssetStorageError):
        backend.put_blob(content_hash(b"x"), "not-bytes")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Offline default — purely local when no provider is connected                 #
# --------------------------------------------------------------------------- #


def test_works_fully_offline_with_no_port() -> None:
    backend = SharedBlobBackend()  # port=None -> purely local
    blob = b"offline-bytes"
    digest = content_hash(blob)
    backend.put_blob(digest, blob)
    assert backend.has_blob(digest) is True
    assert backend.get_blob(digest) == blob


def test_offline_missing_blob_is_not_found() -> None:
    backend = SharedBlobBackend()
    absent = content_hash(b"absent")
    assert backend.has_blob(absent) is False
    with pytest.raises(AssetStorageError):
        backend.get_blob(absent)


def test_disconnected_provider_is_not_consulted() -> None:
    # A blob present ONLY in a disconnected cloud is invisible: the backend is local.
    adapter = FakeCloudAdapter(connected=False)
    blob = b"cloud-only"
    digest = content_hash(blob)
    adapter.put(digest, blob)  # sits in the (disconnected) cloud
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    assert backend.has_blob(digest) is False
    with pytest.raises(AssetStorageError):
        backend.get_blob(digest)


# --------------------------------------------------------------------------- #
# Connected provider transparently backs the same operations                   #
# --------------------------------------------------------------------------- #


def test_connected_provider_serves_get_transparently_and_caches() -> None:
    adapter = FakeCloudAdapter(connected=True)
    blob = b"shared-bytes"
    digest = content_hash(blob)
    adapter.put(digest, blob)  # the blob lives only in the shared backing
    local = LocalBlobBackend()
    backend = SharedBlobBackend(port=adapter, local=local)

    assert local.has_blob(digest) is False  # not local yet
    assert backend.has_blob(digest) is True  # visible via the connected provider
    # Served transparently through the same port and cached locally for offline reads.
    assert backend.get_blob(digest) == blob
    assert local.has_blob(digest) is True


def test_put_backs_up_to_connected_provider_write_once() -> None:
    adapter = FakeCloudAdapter(connected=True)
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    blob = b"to-share"
    digest = content_hash(blob)

    backend.put_blob(digest, blob)
    assert len(adapter.list_versions(digest)) == 1  # backed to the shared store
    # Write-once: re-putting an existing shared blob is not re-uploaded.
    backend.put_blob(digest, blob)
    assert len(adapter.list_versions(digest)) == 1


def test_has_blob_false_when_connected_but_absent() -> None:
    adapter = FakeCloudAdapter(connected=True)
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    assert backend.has_blob(content_hash(b"nowhere")) is False


# --------------------------------------------------------------------------- #
# Cloud-fetched blob is content-hash verified                                  #
# --------------------------------------------------------------------------- #


def test_cloud_fetched_blob_hash_mismatch_is_rejected() -> None:
    adapter = FakeCloudAdapter(connected=True)
    blob = b"honest"
    digest = content_hash(blob)
    # Store bytes under the digest key that do NOT hash to it (tamper / corruption).
    adapter.put(digest, b"tampered-bytes")
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    with pytest.raises(AssetStorageError):
        backend.get_blob(digest)


def test_get_raises_when_neither_local_nor_shared_has_blob() -> None:
    adapter = FakeCloudAdapter(connected=True)
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    with pytest.raises(AssetStorageError):
        backend.get_blob(content_hash(b"nowhere"))


# --------------------------------------------------------------------------- #
# Cloud transport errors are wrapped as AssetStorageError (defensive)          #
# --------------------------------------------------------------------------- #


class _GetFailsAdapter(FakeCloudAdapter):
    def get(self, project_id, version_id):  # noqa: D102 - test double
        raise CloudError("transport boom")


class _PutFailsAdapter(FakeCloudAdapter):
    def put(self, project_id, blob, *, parent_version=None):  # noqa: D102 - test double
        raise CloudError("transport boom")


def test_get_wraps_cloud_transport_error() -> None:
    adapter = _GetFailsAdapter(connected=True)
    blob = b"shared"
    digest = content_hash(blob)
    # Populate the version history directly so list_versions is non-empty, then the
    # overridden get() raises CloudError -> wrapped.
    FakeCloudAdapter.put(adapter, digest, blob)
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    with pytest.raises(AssetStorageError):
        backend.get_blob(digest)


def test_put_wraps_cloud_transport_error() -> None:
    adapter = _PutFailsAdapter(connected=True)
    backend = SharedBlobBackend(port=adapter, local=LocalBlobBackend())
    blob = b"share-me"
    digest = content_hash(blob)
    with pytest.raises(AssetStorageError):
        backend.put_blob(digest, blob)
