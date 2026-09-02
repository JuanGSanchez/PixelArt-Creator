"""Tests for pixelart_creator.data.snapshot_store — Document <-> content-addressed
snapshot (REQ-P9-DATA-004 store half; plan §3.1).

Covers: a round trip over a "maximal" document (multiple layers, a mask, a
tileset, a tilemap with a literal and an auto-tile layer) yields an equal
Document; blobs are shared between two snapshots differing in one buffer; a
missing blob raises SnapshotStoreError; and a DRIFT GUARD that fails if any
string value above a stated length sits at a key outside BLOB_KEYS in
``project_io.serialize``'s own output -- so a future ``project_io`` addition
is caught by a red test rather than by a silently un-deduplicated payload
(plan §3.1, done-when). Zero Qt.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from pixelart_creator.data import project_io
from pixelart_creator.data.snapshot_store import (
    BLOB_KEYS,
    SnapshotStoreError,
    document_of,
    snapshot_of,
)
from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)

#: The drift guard's stated threshold (plan §3.1): a base64(zlib(...))-encoded
#: buffer blob is always far longer than this for any non-trivial buffer, and
#: no non-blob field in the serialised shape (names, ids, mode strings, the
#: fingerprint-free structure) is expected to reach it.
_DRIFT_GUARD_MIN_BLOB_LEN = 64


def _two_tile_source() -> PixelBuffer:
    src = PixelBuffer(32, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, RED)
    src.fill_rect(16, 0, 16, 16, BLUE)
    return src


def _ruleset() -> AutotileRuleset:
    return AutotileRuleset(1, list(range(1, 1 + BLOB_TILE_COUNT)))


def _maximal_document() -> Document:
    """A document exercising every project_io serialiser branch this module
    knows about: multiple layers, a group, a mask, a tileset and a tilemap
    with both a literal and an auto-tile layer (mirrors
    testing/suites/data/test_project_io_v2.py::_rich_document and
    testing/suites/data/test_project_io_tilemap.py::_document_with_tilemap)."""
    doc = Document(
        8, 8, palette=Palette([RED, BLUE, GREEN]), metadata={"author": "test-fixture"}
    )
    base = doc.frames[0].layers[0]
    base.buffer.set_pixel(1, 1, RED)
    mask = PixelBuffer(8, 8)
    mask.set_pixel(0, 0, (10, 20, 30, 200))
    base.mask = mask

    inner = Layer(PixelBuffer(8, 8), "inner")
    inner.buffer.set_pixel(2, 2, BLUE)
    group = LayerGroup("G", [inner])
    doc.frames[0].layers.append(group)

    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=1)
    doc.tilesets.append(ts)
    tm = Tilemap(name="World", tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("ground", opacity=0.75))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.layers.append(TilemapLayer("auto", autotile=_ruleset()))
    tm.make_stamp_command(1, 5, 5, 1).execute()
    doc.tilemaps.append(tm)

    doc.add_frame(duration_ms=250)
    return doc


def _one_pixel_document(value) -> Document:
    doc = Document(4, 4, palette=Palette([RED]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, value)
    return doc


# --------------------------------------------------------------------------- #
# Round trip over a maximal document                                          #
# --------------------------------------------------------------------------- #


def test_round_trip_maximal_document_yields_equal_document():
    doc = _maximal_document()
    snapshot, blobs = snapshot_of(doc)
    restored = document_of(snapshot, blobs)

    assert restored.width == doc.width
    assert restored.height == doc.height
    assert restored.mode is doc.mode
    assert restored.palette.colors() == doc.palette.colors()
    assert restored.metadata == doc.metadata
    assert len(restored.frames) == len(doc.frames) == 2
    assert restored.frames[1].duration_ms == 250

    restored_base = restored.frames[0].layers[0]
    assert restored_base.buffer.get_pixel(1, 1) == RED
    assert restored_base.mask is not None
    assert restored_base.mask.get_pixel(0, 0) == (10, 20, 30, 200)

    restored_group = restored.frames[0].layers[1]
    assert isinstance(restored_group, LayerGroup)
    assert restored_group.name == "G"
    assert restored_group.children[0].buffer.get_pixel(2, 2) == BLUE

    assert len(restored.tilesets) == 1
    assert restored.tilesets[0].tile_width == 16
    assert len(restored.tilemaps) == 1
    assert restored.tilemaps[0].name == "World"
    assert len(restored.tilemaps[0].layers) == 2
    assert restored.tilemaps[0].layers[1].autotile is not None


def test_round_trip_preserves_indexed_mode():
    doc = Document(3, 3, mode=ColorMode.INDEXED, palette=Palette([RED]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, 5)
    snapshot, blobs = snapshot_of(doc)
    restored = document_of(snapshot, blobs)
    assert restored.mode is ColorMode.INDEXED
    assert restored.frames[0].layers[0].buffer.get_pixel(0, 0) == 5


# --------------------------------------------------------------------------- #
# Blob sharing across snapshots                                               #
# --------------------------------------------------------------------------- #


def test_blobs_shared_between_snapshots_differing_in_one_buffer():
    doc_a = _maximal_document()
    doc_b = _maximal_document()
    # One buffer changes; every other blob (the group's inner layer, the
    # mask, the tileset source, the tilemap chunk data) stays byte-identical.
    doc_b.frames[0].layers[0].buffer.set_pixel(3, 3, GREEN)

    snap_a, blobs_a = snapshot_of(doc_a)
    snap_b, blobs_b = snapshot_of(doc_b)

    merged: Dict[str, str] = dict(blobs_a)
    merged.update(blobs_b)

    # Sharing: every blob key common to both tables maps to the identical
    # encoded string (same content -> same hash -> stored once).
    shared_keys = set(blobs_a) & set(blobs_b)
    assert shared_keys, "expected at least one shared (unchanged) blob"
    for key in shared_keys:
        assert blobs_a[key] == blobs_b[key]

    # The two snapshots differ (the changed layer's blob key differs)...
    assert snap_a != snap_b
    # ...but restoring each from the *merged* table still round-trips
    # correctly -- proving the sharing is genuine, not accidental overlap.
    restored_a = document_of(snap_a, merged)
    restored_b = document_of(snap_b, merged)
    assert restored_a.frames[0].layers[0].buffer.get_pixel(3, 3) == (0, 0, 0, 0)
    assert restored_b.frames[0].layers[0].buffer.get_pixel(3, 3) == GREEN
    # The pixel both share (1,1) round-trips identically for each.
    assert restored_a.frames[0].layers[0].buffer.get_pixel(1, 1) == RED
    assert restored_b.frames[0].layers[0].buffer.get_pixel(1, 1) == RED
    # An unrelated, unchanged pixel round-trips identically off the shared blob.
    assert restored_a.frames[0].layers[1].children[0].buffer.get_pixel(2, 2) == BLUE
    assert restored_b.frames[0].layers[1].children[0].buffer.get_pixel(2, 2) == BLUE


def test_identical_documents_hash_to_the_same_blob_table():
    # Two independently-built but pixel-identical documents produce byte-
    # identical blob tables -- the content-addressing is deterministic.
    _, blobs_a = snapshot_of(_one_pixel_document(RED))
    _, blobs_b = snapshot_of(_one_pixel_document(RED))
    assert blobs_a == blobs_b


# --------------------------------------------------------------------------- #
# Missing blob                                                                 #
# --------------------------------------------------------------------------- #


def test_document_of_raises_on_missing_blob():
    doc = _one_pixel_document(RED)
    snapshot, blobs = snapshot_of(doc)
    assert blobs, "expected at least one blob for a non-empty buffer"
    incomplete = {}  # every referenced key is now missing
    with pytest.raises(SnapshotStoreError):
        document_of(snapshot, incomplete)


def test_document_of_raises_naming_the_missing_key():
    doc = _one_pixel_document(RED)
    snapshot, blobs = snapshot_of(doc)
    victim_key = next(iter(blobs))
    partial = {k: v for k, v in blobs.items() if k != victim_key}
    with pytest.raises(SnapshotStoreError, match=victim_key):
        document_of(snapshot, partial)


# --------------------------------------------------------------------------- #
# The BLOB_KEYS drift guard (plan §3.1, done-when)                           #
# --------------------------------------------------------------------------- #


def _walk_string_values(node: Any) -> List[Any]:
    """Yield every ``(key, value)`` pair in ``node`` where ``value`` is a str,
    recursively over dicts/lists -- the same shape ``_hoist``/``_inline`` walk."""
    found: List[Any] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str):
                found.append((key, value))
            else:
                found.extend(_walk_string_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_string_values(item))
    return found


def test_blob_keys_drift_guard_over_maximal_document():
    """Fails red if project_io.serialize ever emits a long string value at a
    key outside BLOB_KEYS -- e.g. a future serialiser adding a new encoded
    array field. This is the guard the plan names, not a hand-enumerated
    pin: it inspects project_io's OWN output, not a literal list."""
    serialised = project_io.serialize(_maximal_document())
    offenders = [
        (key, len(value))
        for key, value in _walk_string_values(serialised)
        if len(value) > _DRIFT_GUARD_MIN_BLOB_LEN and key not in BLOB_KEYS
    ]
    assert offenders == [], (
        "long string value(s) found outside BLOB_KEYS -- BLOB_KEYS has drifted "
        f"from project_io.serialize's actual output: {offenders}"
    )


def test_blob_keys_drift_guard_catches_an_injected_unlisted_key():
    """Proves the guard actually catches drift (not just that it passes today):
    injecting a long string at a key BLOB_KEYS does not know about must fail
    the same assertion the guard makes."""
    serialised = project_io.serialize(_maximal_document())
    serialised["frames"][0]["layers"][0]["totally_new_blob_field"] = "x" * 100
    offenders = [
        (key, len(value))
        for key, value in _walk_string_values(serialised)
        if len(value) > _DRIFT_GUARD_MIN_BLOB_LEN and key not in BLOB_KEYS
    ]
    assert offenders != []
    assert offenders[0][0] == "totally_new_blob_field"


def test_snapshot_of_hoists_every_blob_key_actually_present():
    """Every BLOB_KEYS-keyed string in project_io's own output is hoisted --
    none is left inline in the snapshot."""
    serialised = project_io.serialize(_maximal_document())
    blob_bearing = [
        (key, value)
        for key, value in _walk_string_values(serialised)
        if key in BLOB_KEYS
    ]
    assert blob_bearing, "fixture must exercise at least one BLOB_KEYS field"

    snapshot, blobs = snapshot_of(_maximal_document())
    remaining = [
        (key, value) for key, value in _walk_string_values(snapshot) if key in BLOB_KEYS
    ]
    assert remaining, "expected hoisted BLOB_KEYS references in the snapshot"
    for key, value in remaining:
        # Each BLOB_KEYS-keyed value in the snapshot is a hash-key reference
        # (present in blobs), never the long raw blob string itself.
        assert (
            value in blobs
        ), f"hoisted reference at {key!r} not present in blobs table"
        assert (
            len(value) == 64
        ), f"value at {key!r} is not a 64-char sha256 hex hash key: {value!r}"
