# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Chunk-aligned pixmap cache + off-GUI-thread cold warm for the tilemap (D1/D4).

The tilemap canvas renders through the frozen, Qt-free
:meth:`~pixelart_creator.logic.tilemap.Tilemap.render_region` seam. Re-running it
for the whole exposed viewport every frame is over the 16 ms budget on a large /
cold map (measured: full 8K viewport cold ~307 ms, and the original S1/S4 froze for
seconds). This module supplies the two pieces the scene assembles into a
budget-hitting incremental render:

* :class:`ChunkPixmapCache` — a **bounded LRU** of one rendered ``QPixmap`` per
  ``TILEMAP_CHUNK_SIZE`` chunk, keyed by ``(cx, cy)`` and *validated* by the
  logic layer's O(1) :meth:`Tilemap.chunk_version` (D1). A ``get`` whose stored
  version no longer matches the current chunk version is a **miss**, so a dirtied
  chunk transparently re-renders while every untouched chunk re-blits (D2/D3). The
  cache holds at most one version per chunk, so a stale version is dropped the
  instant its chunk is re-rendered; total bytes are capped in MiB (mirroring
  :mod:`~pixelart_creator.ui.frame_cache`'s discipline) so an infinite / fully
  filled map stays bounded — only the DERIVED pixmaps are culled, never the
  resident tileset pixel data (Article VI §3).

* :class:`TilemapChunkWarmSignals` / :class:`TilemapChunkWarmRunnable` — the
  off-GUI-thread cold-warm carrier + worker (D4), mirroring
  :mod:`~pixelart_creator.ui.composite_warmer` exactly. The worker calls the
  **Qt-free** ``render_region`` for one chunk's pixel rect on a scene-owned
  :class:`~PySide6.QtCore.QThreadPool` (never the global pool) and hands the
  resulting :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` back through
  a GUI-thread-affine **queued** signal; the scene converts it to a ``QPixmap``
  and caches it only inside its GUI-thread slot (no cross-thread QPixmap / QImage
  construction). A shared :class:`threading.Event` gives a best-effort early exit
  and a monotonic ``token`` validated by the scene drops any superseded result.

Qt lives only here in ``ui/`` (S11); the domain render maths stay in ``logic/``.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtGui import QPixmap

from pixelart_creator.logic.tilemap import Tilemap, TilemapError

#: Cache key: the tilemap-cell chunk origin ``(cx, cy)`` (``cell //
#: TILEMAP_CHUNK_SIZE``), the same coordinate :meth:`Tilemap.chunk_version` takes.
ChunkKey = Tuple[int, int]


class ChunkPixmapCache:
    """Bounded-MiB LRU of rendered chunk pixmaps, version-validated (D1/D2/D3)."""

    def __init__(self, memory_budget_bytes: int) -> None:
        """Bound the cache to ``memory_budget_bytes`` of rendered chunk pixmaps.

        Raises:
            ValueError: If ``memory_budget_bytes`` is not positive.
        """
        if memory_budget_bytes <= 0:
            raise ValueError("memory_budget_bytes must be positive")
        self._budget = int(memory_budget_bytes)
        # (cx, cy) -> (version, pixmap, nbytes); LRU order = insertion/touch order.
        self._entries: "OrderedDict[ChunkKey, Tuple[int, QPixmap, int]]" = OrderedDict()
        self._bytes = 0

    def get(self, cx: int, cy: int, version: int) -> Optional[QPixmap]:
        """Return the cached pixmap for chunk ``(cx, cy)`` iff its version matches.

        A stored entry whose version differs from ``version`` (the chunk was
        dirtied since it was rendered) is treated as a **miss** so the caller
        re-renders; the stale entry is overwritten on the next :meth:`put`.
        """
        entry = self._entries.get((cx, cy))
        if entry is None or entry[0] != version:
            return None
        self._entries.move_to_end((cx, cy))
        return entry[1]

    def put(self, cx: int, cy: int, version: int, pixmap: QPixmap, nbytes: int) -> None:
        """Store ``pixmap`` for chunk ``(cx, cy)`` at ``version`` as MRU (evict LRU)."""
        key = (cx, cy)
        existing = self._entries.get(key)
        if existing is not None:
            self._bytes -= existing[2]
        self._entries[key] = (int(version), pixmap, int(nbytes))
        self._entries.move_to_end(key)
        self._bytes += int(nbytes)
        self._evict()

    def discard(self, cx: int, cy: int) -> None:
        """Drop chunk ``(cx, cy)`` if resident (a no-op otherwise)."""
        entry = self._entries.pop((cx, cy), None)
        if entry is not None:
            self._bytes -= entry[2]

    def clear(self) -> None:
        """Drop every cached chunk pixmap (whole-cache invalidation)."""
        self._entries.clear()
        self._bytes = 0

    @property
    def resident_chunks(self) -> int:
        """Number of chunk pixmaps currently held (for tests / diagnostics)."""
        return len(self._entries)

    @property
    def resident_bytes(self) -> int:
        """Total bytes currently held by cached chunk pixmaps (for tests)."""
        return self._bytes

    def _evict(self) -> None:
        """Evict LRU-first until the byte budget is honoured (keep >= 1 entry)."""
        for key in list(self._entries.keys()):  # LRU -> MRU order
            if self._bytes <= self._budget or len(self._entries) <= 1:
                break
            _version, _pixmap, nbytes = self._entries.pop(key)
            self._bytes -= nbytes


class TilemapChunkWarmSignals(QObject):
    """GUI-thread-affine carrier for the worker's ``chunkReady`` signal (D4)."""

    #: ``(token, cx, cy, version, PixelBuffer)`` — a warmed chunk region, delivered
    #: queued to the GUI thread. The buffer is a fresh worker-allocated object; the
    #: scene converts it to a ``QPixmap`` and takes ownership only in its slot.
    chunkReady = Signal(int, int, int, int, object)


class TilemapChunkWarmRunnable(QRunnable):
    """Render one chunk's pixel region off the GUI thread via ``render_region`` (D4)."""

    def __init__(
        self,
        token: int,
        tilemap: Tilemap,
        cx: int,
        cy: int,
        version: int,
        px: int,
        py: int,
        pw: int,
        ph: int,
        cancel: threading.Event,
        signals: TilemapChunkWarmSignals,
    ) -> None:
        """Capture the job: ``token``, chunk ``(cx, cy)`` + its pixel rect + version.

        ``cancel`` is the scene's shared cancellation event (checked before and
        after the render); ``signals`` is the GUI-thread carrier the result is
        emitted through. ``render_region`` is the frozen, Qt-free logic seam and is
        read-only over the tilemap; the scene cancels in-flight warms on an edit and
        validates the ``token`` so a stale/torn read is never cached.
        """
        super().__init__()
        self._token = int(token)
        self._tilemap = tilemap
        self._cx = int(cx)
        self._cy = int(cy)
        self._version = int(version)
        self._px = int(px)
        self._py = int(py)
        self._pw = int(pw)
        self._ph = int(ph)
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Render the chunk region off-thread and emit it (unless cancelled)."""
        if self._cancel.is_set():
            return
        try:
            buffer = self._tilemap.render_region(self._px, self._py, self._pw, self._ph)
        except TilemapError:
            # A bad/unknown cell must never crash the worker; the chunk stays as the
            # checker placeholder and re-warms if its version changes.
            return
        if self._cancel.is_set():
            return
        # render_region returns a freshly allocated PixelBuffer sharing no memory
        # with the tileset sources, so it is safe to hand across the queued
        # connection to the GUI thread as-is (no extra copy).
        self._signals.chunkReady.emit(
            self._token, self._cx, self._cy, self._version, buffer
        )


#: In-flight bookkeeping: chunk key -> the version being warmed (dedupe dispatch).
InflightMap = Dict[ChunkKey, int]
