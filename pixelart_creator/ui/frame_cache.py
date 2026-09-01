# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""LRU-bounded per-frame composite cache (D3, F7-safe).

``FrameCompositeCache`` bounds the **derived** per-frame flattened composites by a
memory budget so a long animation cannot grow the cache to ~1 GB (the previous
``MAX_FRAMES``-bounded dict held ~126 MB per 8K frame). It caches **only** the
flattened composite :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`
objects the :class:`~pixelart_creator.ui.canvas_scene.CanvasScene` produces — the
**source** layer buffers are never stored here and are never culled (Article VI
§3, F7): culling is applied to the derived render products only.

The eviction policy is classic LRU with two safeguards:

* the **active** frame is *pinned* (its buffer is the scene's live display target
  and every edit writes into it, so it must never be evicted), and
* a small ``min_resident`` floor keeps at least a working set resident even under
  a tight budget, so a scrub/playback step to a neighbouring frame stays a blit.

Get/put are O(1) (an :class:`~collections.OrderedDict` move-to-end), so the
interactive cache-**hit** scrub/playback path is unchanged (a dict lookup + LRU
touch); the compositor is only ever invoked on a genuine miss.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from pixelart_creator.logic.pixel_buffer import PixelBuffer


class FrameCompositeCache:
    """Memory-budgeted LRU cache of derived per-frame composites (D3)."""

    def __init__(self, memory_budget_bytes: int, min_resident: int = 2) -> None:
        """Bound the cache to ``memory_budget_bytes`` of derived composites.

        ``min_resident`` (>= 1) frames are always kept even when that exceeds the
        byte budget, so a step to an adjacent frame stays a cache hit. The active
        frame is additionally protected by :meth:`pin`.

        Raises:
            ValueError: If ``memory_budget_bytes`` is not positive.
        """
        if memory_budget_bytes <= 0:
            raise ValueError("memory_budget_bytes must be positive")
        self._budget = int(memory_budget_bytes)
        self._min_resident = max(1, int(min_resident))
        self._entries: "OrderedDict[int, PixelBuffer]" = OrderedDict()
        self._bytes = 0
        self._pinned: Optional[int] = None

    def __contains__(self, index: int) -> bool:
        """Return whether frame ``index`` is resident (no LRU touch)."""
        return index in self._entries

    def contains(self, index: int) -> bool:
        """Return whether frame ``index`` is resident (no LRU touch)."""
        return index in self._entries

    def get(self, index: int) -> Optional[PixelBuffer]:
        """Return frame ``index``'s composite as MRU, or ``None`` if not resident."""
        buffer = self._entries.get(index)
        if buffer is not None:
            self._entries.move_to_end(index)
        return buffer

    def put(self, index: int, buffer: PixelBuffer) -> None:
        """Store ``buffer`` for frame ``index`` as MRU, evicting LRU past budget."""
        existing = self._entries.get(index)
        if existing is not None:
            self._bytes -= existing.data.nbytes
            self._entries.move_to_end(index)
        self._entries[index] = buffer
        self._bytes += buffer.data.nbytes
        self._evict()

    def pin(self, index: int) -> None:
        """Protect frame ``index`` from eviction (the active display buffer)."""
        self._pinned = index
        if index in self._entries:
            self._entries.move_to_end(index)

    def discard(self, index: int) -> None:
        """Drop frame ``index`` if resident (a no-op otherwise)."""
        buffer = self._entries.pop(index, None)
        if buffer is not None:
            self._bytes -= buffer.data.nbytes

    def clear(self) -> None:
        """Drop every cached composite (the caller re-registers the pin target)."""
        self._entries.clear()
        self._bytes = 0

    @property
    def resident_frames(self) -> int:
        """Number of frames currently held (for tests / diagnostics)."""
        return len(self._entries)

    @property
    def resident_bytes(self) -> int:
        """Total bytes currently held by derived composites (for tests)."""
        return self._bytes

    def _evict(self) -> None:
        """Evict LRU-first past budget, never the pinned frame nor below floor."""
        for index in list(self._entries.keys()):  # LRU -> MRU order
            if self._bytes <= self._budget:
                break
            if len(self._entries) <= self._min_resident:
                break
            if index == self._pinned:
                continue
            buffer = self._entries.pop(index)
            self._bytes -= buffer.data.nbytes
