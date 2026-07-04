"""Unit + property tests for :mod:`pixelart_creator.data.asset_cas` (S11, no Qt).

Covers the content-addressable store (ADR-0030 §4; REQ-P11-DATA-004/-005): DEDUP
(same content stored once — a Hypothesis property over byte blobs), content-hash
VERIFICATION on fetch (a tampered blob is rejected), invalid-key rejection, and the
``MAX_BLOB_BYTES`` boundary enforced from ``logic/constants`` (not a literal). T11-1-10.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data import asset_cas
from pixelart_creator.data.asset_cas import CasError, ContentAddressableStore
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.logic.constants import MAX_BLOB_BYTES
from pixelart_creator.logic.content_hash import content_hash

# --------------------------------------------------------------------------- #
# Construction                                                                 #
# --------------------------------------------------------------------------- #


def test_default_backend_is_local() -> None:
    store = ContentAddressableStore()
    digest = store.put(b"hello")
    assert store.get(digest) == b"hello"


def test_rejects_non_backend() -> None:
    with pytest.raises(CasError):
        ContentAddressableStore(backend="not-a-backend")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# put / get round-trip + verification                                          #
# --------------------------------------------------------------------------- #


def test_put_returns_content_hash_and_get_verifies() -> None:
    store = ContentAddressableStore()
    blob = b"sprite-bytes"
    digest = store.put(blob)
    assert digest == content_hash(blob)
    assert store.get(digest) == blob
    assert store.has(digest) is True


def test_put_rejects_non_bytes() -> None:
    with pytest.raises(CasError):
        ContentAddressableStore().put("not-bytes")  # type: ignore[arg-type]


def test_get_rejects_invalid_key() -> None:
    with pytest.raises(CasError):
        ContentAddressableStore().get("not-a-hash")


def test_get_missing_blob_raises() -> None:
    store = ContentAddressableStore()
    with pytest.raises(CasError):
        store.get(content_hash(b"never-stored"))


def test_has_returns_false_for_invalid_or_absent_key() -> None:
    store = ContentAddressableStore()
    assert store.has("not-a-hash") is False
    assert store.has(content_hash(b"absent")) is False


# --------------------------------------------------------------------------- #
# DEDUP — same content stored once                                             #
# --------------------------------------------------------------------------- #


def test_second_put_of_same_content_is_dedup_noop() -> None:
    backend = LocalBlobBackend()
    store = ContentAddressableStore(backend=backend)
    d1 = store.put(b"same")
    d2 = store.put(b"same")
    assert d1 == d2
    # exactly one blob is resident in the backend (dedup no-op)
    assert len(backend._memory) == 1


@given(st.binary(max_size=512), st.binary(max_size=512))
def test_dedup_property(a: bytes, b: bytes) -> None:
    backend = LocalBlobBackend()
    store = ContentAddressableStore(backend=backend)
    store.put(a)
    store.put(a)  # re-put identical -> no duplicate
    store.put(b)
    # distinct contents -> distinct blobs; identical contents share one blob
    expected = 1 if a == b else 2
    assert len(backend._memory) == expected
    assert store.get(store.put(a)) == a


# --------------------------------------------------------------------------- #
# VERIFICATION — tampered blob rejected on fetch                               #
# --------------------------------------------------------------------------- #


def test_tampered_blob_is_rejected_on_get() -> None:
    backend = LocalBlobBackend()
    store = ContentAddressableStore(backend=backend)
    digest = store.put(b"honest")
    # Corrupt the backing bytes under the same key (tamper/corruption).
    backend._memory[digest] = b"tampered-content"
    with pytest.raises(CasError):
        store.get(digest)


# --------------------------------------------------------------------------- #
# MAX_BLOB_BYTES boundary — enforced from the named constant                   #
# --------------------------------------------------------------------------- #


def test_max_blob_bytes_is_the_named_constant() -> None:
    assert asset_cas.MAX_BLOB_BYTES == MAX_BLOB_BYTES


def test_put_at_boundary_accepted_over_boundary_rejected(monkeypatch) -> None:
    monkeypatch.setattr(asset_cas, "MAX_BLOB_BYTES", 8)
    store = ContentAddressableStore()
    # exactly at the cap is accepted
    digest = store.put(b"x" * 8)
    assert store.get(digest) == b"x" * 8
    # one byte over the cap is rejected
    with pytest.raises(CasError):
        store.put(b"x" * 9)


def test_get_rejects_oversized_fetched_blob(monkeypatch) -> None:
    store = ContentAddressableStore()
    digest = store.put(b"x" * 20)
    # Shrink the cap below the stored size -> fetch guard rejects before verify.
    monkeypatch.setattr(asset_cas, "MAX_BLOB_BYTES", 5)
    with pytest.raises(CasError):
        store.get(digest)
