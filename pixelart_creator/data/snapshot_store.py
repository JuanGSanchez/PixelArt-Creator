# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Document <-> content-addressed snapshot store (zero Qt, S11).

The shared, single persisted-history payload for the whole product
(ADR-0052): a timelapse frame's own recorded state (D-12, phase-9) and a
mode-toggle undo checkpoint (phase-6) are both, at bottom, one
:class:`~pixelart_creator.logic.document.Document` at a moment in time. Rather
than invent a second encoding, this module reuses the **public**
``data/project_io.serialize`` / ``deserialize`` entry points — which already
cover every persisted field, defensively, ``eval``-free, zlib+base64-compressed
(plan §2) — and hoists the already-encoded pixel/array blob strings its output
contains into a **content-addressed** ``{sha256hex: blob}`` table, shared across
every snapshot built this way.

Consecutive edits typically change one layer's buffer; every *other* buffer's
encoded blob string is byte-identical across snapshots, so it hashes to the
same key and is stored once. That is the copy-on-write benefit at *buffer*
granularity — the granularity this product actually has
(:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` is a flat NumPy
array, not tiled).

``data/project_io.py`` is **not modified** — not one line (plan §2): extracting
a shared codec was considered and dropped, since it would touch an 802-line,
5-format-version module for zero gain and would invert the natural
``snapshot_store -> project_io`` dependency into a cycle.

:data:`BLOB_KEYS` is the whole of the "which keys hold blob strings" knowledge
this module needs, enumerated from ``project_io``'s serialisers
(``_serialise_buffer`` emits ``{"mode", "data"}``; ``_serialise_tileset`` emits
``"source"``; ``_encode_u32``-encoded tilemap chunks are emitted under
``"data"`` too). It is deliberately **not** exhaustively verified against every
serialiser body (plan §3.1) — the drift guard (``tests/data/test_snapshot_store.py``,
AGT-04, T12) is what makes a future ``project_io`` addition at an unlisted key
cheap to catch, rather than a silently un-deduplicated (and therefore oversized)
payload.

Layering: ``data -> data`` (``project_io``) and ``data -> logic``
(``content_hash``, ``document`` for typing). Never ``logic -> data`` — a
snapshot reaches ``logic`` only as a :class:`Document`, never as bytes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Tuple

from pixelart_creator.data import project_io
from pixelart_creator.logic.content_hash import content_hash

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    from pixelart_creator.logic.document import Document

__all__ = [
    "SnapshotStoreError",
    "BLOB_KEYS",
    "snapshot_of",
    "document_of",
]

#: The ``project_io.serialize()`` output dict keys whose string value is an
#: already-encoded ``base64(zlib(raw))`` blob (never a value to recurse into
#: for further blob keys): layer/mask buffers and tileset source images
#: (``project_io._serialise_buffer`` / ``_encode_buffer``, keyed ``"data"`` on
#: a layer node and on a mask object, ``"source"`` on a tileset) and encoded
#: tilemap display/logical chunk cells (``project_io._encode_u32``, keyed
#: ``"data"`` on each chunk entry). No other key in the serialised shape holds
#: a blob string (plan §3.1).
BLOB_KEYS: FrozenSet[str] = frozenset({"data", "source"})


class SnapshotStoreError(ValueError):
    """Raised when a document cannot be snapshotted or a blob is missing."""


def _hash_blob(blob: str) -> str:
    """Return the content-hash key for an encoded blob string."""
    if not isinstance(blob, str):
        raise SnapshotStoreError(f"blob value must be a str, got {blob!r}")
    return content_hash(blob.encode("ascii"))


def _hoist(node: Any, blobs: Dict[str, str]) -> Any:
    """Recursively replace every ``BLOB_KEYS`` string value with its hash key.

    Every hoisted blob is recorded into ``blobs`` (mutated in place); a blob
    already present under the same hash is left as-is (shared / deduplicated).
    """
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for key, value in node.items():
            if key in BLOB_KEYS and isinstance(value, str):
                digest = _hash_blob(value)
                blobs[digest] = value
                out[key] = digest
            else:
                out[key] = _hoist(value, blobs)
        return out
    if isinstance(node, list):
        return [_hoist(item, blobs) for item in node]
    return node


def _inline(node: Any, blobs: Dict[str, str]) -> Any:
    """Recursively replace every ``BLOB_KEYS`` hash-key value with its blob.

    Raises:
        SnapshotStoreError: If a referenced hash key has no entry in ``blobs``.
    """
    if isinstance(node, dict):
        out: Dict[str, Any] = {}
        for key, value in node.items():
            if key in BLOB_KEYS and isinstance(value, str):
                if value not in blobs:
                    raise SnapshotStoreError(
                        f"missing blob {value!r} referenced at key {key!r}"
                    )
                out[key] = blobs[value]
            else:
                out[key] = _inline(value, blobs)
        return out
    if isinstance(node, list):
        return [_inline(item, blobs) for item in node]
    return node


def snapshot_of(document: "Document") -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Snapshot ``document`` as a ``(snapshot, blobs)`` pair.

    Calls the **public** :func:`pixelart_creator.data.project_io.serialize`
    and hoists every value at a :data:`BLOB_KEYS` key into a
    ``{content_hash(blob): blob}`` table. ``snapshot`` is the same shape
    ``project_io.serialize`` returns, with every blob string replaced by its
    hash key; ``blobs`` holds only the blobs *this* snapshot references —
    callers building a multi-snapshot table (e.g. one per timelapse frame)
    merge successive ``blobs`` dicts, which is exactly how sharing happens: an
    unchanged buffer hashes to the same key every time and is therefore stored
    once regardless of how many snapshots reference it.

    Args:
        document: The document to snapshot.

    Returns:
        A ``(snapshot, blobs)`` pair.
    """
    serialised = project_io.serialize(document)
    blobs: Dict[str, str] = {}
    snapshot = _hoist(serialised, blobs)
    return snapshot, blobs


def document_of(snapshot: Dict[str, Any], blobs: Dict[str, str]) -> "Document":
    """Reconstruct a :class:`Document` from a ``(snapshot, blobs)`` pair.

    Re-inlines every :data:`BLOB_KEYS` hash-key reference in ``snapshot`` from
    ``blobs`` and calls the **public**
    :func:`pixelart_creator.data.project_io.deserialize`.

    Args:
        snapshot: A snapshot as returned by :func:`snapshot_of` (or loaded from
            a schema-2 ``.pixtimelapse`` snapshot table).
        blobs: The blob table the snapshot's hash-key references resolve
            against — typically the merged table of every snapshot sharing this
            document's history, not just this one snapshot's own.

    Raises:
        SnapshotStoreError: If ``snapshot`` references a blob absent from
            ``blobs``.
        project_io.ProjectIOError: If the re-inlined payload is otherwise
            malformed (propagated from ``project_io.deserialize``, Article VII).
    """
    inlined = _inline(snapshot, blobs)
    return project_io.deserialize(inlined)
