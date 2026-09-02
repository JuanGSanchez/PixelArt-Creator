"""Phase-6 chunk pixmap cache + off-thread warm-worker unit tests.

pytest-qt, headless, both themes (autouse fixture). Exercises the LRU cache the
tilemap canvas keys by ``(cx, cy, chunk_version)`` (version-validated hit/miss,
eviction under the MiB budget, discard/clear) and the off-GUI-thread warm worker /
carrier (``TilemapChunkWarmRunnable`` emits a rendered ``PixelBuffer`` through the
``TilemapChunkWarmSignals`` carrier; a set cancel event is an early exit). These are
the pieces behind REQ-P6-UI-014's incremental render (measured to hold the 16 ms
budget); this module proves their behaviour deterministically.
"""

from __future__ import annotations

import threading

import pytest
from PySide6.QtGui import QPixmap

from pixelart_creator.logic.constants import TILEMAP_CHUNK_SIZE
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.ui.tilemap_chunk_cache import (
    ChunkPixmapCache,
    TilemapChunkWarmRunnable,
    TilemapChunkWarmSignals,
)


def _pixmap(edge: int = 8) -> QPixmap:
    pm = QPixmap(edge, edge)
    pm.fill()
    return pm


def test_cache_hit_only_on_matching_version(qtbot):
    """A stored chunk is a hit only when the requested version matches (D1)."""
    cache = ChunkPixmapCache(1_000_000)
    pm = _pixmap()
    cache.put(0, 0, version=3, pixmap=pm, nbytes=256)
    assert cache.get(0, 0, 3) is not None  # version match -> hit
    assert cache.get(0, 0, 4) is None  # stale version -> miss (dirtied chunk)
    assert cache.get(9, 9, 3) is None  # absent chunk -> miss
    assert cache.resident_chunks == 1
    assert cache.resident_bytes == 256


def test_cache_discard_and_clear(qtbot):
    """discard drops one chunk; clear empties the whole cache."""
    cache = ChunkPixmapCache(1_000_000)
    cache.put(0, 0, 1, _pixmap(), 128)
    cache.put(1, 0, 1, _pixmap(), 128)
    cache.discard(0, 0)
    assert cache.get(0, 0, 1) is None
    assert cache.resident_chunks == 1
    cache.discard(5, 5)  # absent -> no-op
    cache.clear()
    assert cache.resident_chunks == 0
    assert cache.resident_bytes == 0


def test_cache_evicts_lru_under_byte_budget(qtbot):
    """Over-budget puts evict LRU-first but always keep >= 1 entry."""
    cache = ChunkPixmapCache(1000)
    for i in range(6):
        cache.put(i, 0, 1, _pixmap(), 400)  # 6 * 400 = 2400 >> 1000
    assert cache.resident_bytes <= 1000 or cache.resident_chunks == 1
    assert cache.resident_chunks >= 1  # never evicts the last entry
    # The most-recently-put chunk survives (MRU); the earliest is gone (LRU).
    assert cache.get(5, 0, 1) is not None
    assert cache.get(0, 0, 1) is None


def test_cache_put_replaces_same_key_bytes(qtbot):
    """Re-putting a key updates version + adjusts the byte total (no double count)."""
    cache = ChunkPixmapCache(1_000_000)
    cache.put(2, 2, 1, _pixmap(), 500)
    cache.put(2, 2, 2, _pixmap(), 300)  # replace same key
    assert cache.resident_chunks == 1
    assert cache.resident_bytes == 300
    assert cache.get(2, 2, 2) is not None


def test_cache_rejects_non_positive_budget():
    """A non-positive byte budget is rejected (defensive)."""
    with pytest.raises(ValueError):
        ChunkPixmapCache(0)


def test_warm_runnable_emits_rendered_buffer(qtbot, make_tilemap_setup):
    """The off-thread worker renders a chunk and emits it through the carrier (D4)."""
    tileset, tilemap = make_tilemap_setup()
    tilemap.make_stamp_command(0, 0, 0, tileset.first_gid).execute()

    signals = TilemapChunkWarmSignals()
    received = []
    signals.chunkReady.connect(lambda *args: received.append(args))
    cancel = threading.Event()
    chunk_px = TILEMAP_CHUNK_SIZE * tilemap.tile_width
    runnable = TilemapChunkWarmRunnable(
        7,
        tilemap,
        0,
        0,
        tilemap.chunk_version(0, 0),
        0,
        0,
        chunk_px,
        chunk_px,
        cancel,
        signals,
    )
    runnable.run()  # synchronous on this thread -> direct emit
    assert len(received) == 1
    token, cx, cy, version, buffer = received[0]
    assert token == 7 and (cx, cy) == (0, 0)
    assert isinstance(buffer, PixelBuffer)


def test_warm_runnable_early_exits_when_cancelled(qtbot, make_tilemap_setup):
    """A set cancel event is a best-effort early exit — nothing is emitted."""
    tileset, tilemap = make_tilemap_setup()
    tilemap.make_stamp_command(0, 0, 0, tileset.first_gid).execute()
    signals = TilemapChunkWarmSignals()
    received = []
    signals.chunkReady.connect(lambda *args: received.append(args))
    cancel = threading.Event()
    cancel.set()  # cancelled before it runs
    chunk_px = TILEMAP_CHUNK_SIZE * tilemap.tile_width
    runnable = TilemapChunkWarmRunnable(
        1, tilemap, 0, 0, 1, 0, 0, chunk_px, chunk_px, cancel, signals
    )
    runnable.run()
    assert received == []
