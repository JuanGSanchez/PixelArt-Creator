# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Per-colour / per-index usage analytics (read-only, vectorised, zero Qt, S11).

Computes how often each colour or palette index is used across a buffer or a
whole :class:`~pixelart_creator.logic.document.Document`. Read-only (no mutation),
deterministic, and **vectorised** over the pixel buffer (NumPy, F7) — never a
per-pixel Python loop, so it holds the frame budget over the 8K buffer (NFR-9).
REQ-P3-LOGIC-012 (SC-L012-1..4).
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional, Tuple

import numpy as np

from pixelart_creator.logic._rgba_unique import unique_rgba_counts
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = [
    "color_usage_counts",
    "index_usage_counts",
    "document_usage_counts",
]


class PaletteAnalyticsError(ValueError):
    """Raised when analytics is asked for the wrong buffer mode."""


def color_usage_counts(buffer: PixelBuffer) -> List[Tuple[RGBA, int]]:
    """Return ``(colour, count)`` pairs for an RGBA buffer, most-used first.

    Counts sum to the total pixel count (SC-L012-1); ties order by the colour
    tuple ascending (deterministic, SC-L012-4). Vectorised via ``np.unique``.

    Raises:
        PaletteAnalyticsError: If ``buffer`` is not RGBA.
    """
    if buffer.mode is not ColorMode.RGBA:
        raise PaletteAnalyticsError("color_usage_counts requires an RGBA buffer")
    pixels = buffer.data.reshape(-1, 4)
    unique, counts = unique_rgba_counts(pixels)
    pairs = [
        ((int(c[0]), int(c[1]), int(c[2]), int(c[3])), int(n))
        for c, n in zip(unique, counts)
    ]
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return pairs


def index_usage_counts(buffer: PixelBuffer, palette: Palette) -> List[Tuple[int, int]]:
    """Return ``(index, count)`` pairs for an indexed buffer, most-used first.

    Every palette index appears; an unused index reports ``0`` (SC-L012-2). Ties
    order by index ascending (SC-L012-4). Vectorised via ``np.bincount``.

    Raises:
        PaletteAnalyticsError: If ``buffer`` is not indexed.
    """
    if buffer.mode is not ColorMode.INDEXED:
        raise PaletteAnalyticsError("index_usage_counts requires an indexed buffer")
    flat = buffer.data.reshape(-1).astype(np.int64)
    span = max(len(palette), int(flat.max()) + 1 if flat.size else 0)
    counts = np.bincount(flat, minlength=span)
    pairs = [(i, int(counts[i])) for i in range(span)]
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return pairs


def document_usage_counts(
    document: Document, palette: Optional[Palette] = None
) -> List[Tuple[object, int]]:
    """Aggregate usage counts across every layer of every frame of ``document``.

    For an RGBA document the keys are colours; for an indexed document they are
    palette indices (``palette`` defaults to ``document.palette``). Read-only and
    deterministic (SC-L012-4).
    """
    if document.mode is ColorMode.RGBA:
        colour_totals: Counter[RGBA] = Counter()
        for frame in document.frames:
            for layer in iter_layers(frame.layers):
                for colour, count in color_usage_counts(layer.buffer):
                    colour_totals[colour] += count
        colour_sorted = sorted(
            colour_totals.items(), key=lambda item: (-item[1], item[0])
        )
        return [(colour, count) for colour, count in colour_sorted]

    active_palette = palette if palette is not None else document.palette
    index_totals: Counter[int] = Counter()
    for frame in document.frames:
        for layer in iter_layers(frame.layers):
            for index, count in index_usage_counts(layer.buffer, active_palette):
                index_totals[index] += count
    index_sorted = sorted(index_totals.items(), key=lambda item: (-item[1], item[0]))
    return [(index, count) for index, count in index_sorted]
