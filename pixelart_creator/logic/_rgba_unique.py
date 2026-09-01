# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Fast deterministic unique-RGBA reduction over a pixel buffer (zero Qt, S11).

The naive way to find the distinct colours of an ``(N, 4)`` RGBA buffer is
``np.unique(pixels, axis=0, ...)``, but ``axis=0`` runs an ``O(N log N)``
four-column *lexsort* over every pixel row — so a blank 8K document (≈33M rows)
pays ~50 s regardless of how few colours it actually contains (F7 hotspot).

This module packs each contiguous ``(R, G, B, A)`` uint8 row into a single
``uint32`` scalar and runs a plain 1-D ``np.unique`` (a single-key sort instead
of a four-key lexsort), then unpacks the small ``K`` distinct values back to
``(K, 4)`` uint8. The result is *semantically identical* to the ``axis=0`` call.

Order contract (SC-L012-4, byte-for-byte identical output): the ``uint32`` view
reorders bytes on a little-endian host (``R,G,B,A`` is stored as ``A,B,G,R``), so
the ``uint32`` sort order is **not** the required ``(R, G, B, A)`` lexicographic
order. After the reduction (small ``K``) the distinct rows — and any paired
counts / inverse mapping — are re-sorted lexicographically by ``(R, G, B, A)`` so
the observable output matches the previous ``np.unique(..., axis=0)`` exactly, on
any byte order.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import numpy.typing as npt

__all__ = [
    "unique_rgba_counts",
    "unique_rgba_inverse",
]

_RGBA_CHANNELS = 4


def _as_rgba_rows(pixels: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint8]:
    """Return ``pixels`` as a C-contiguous ``(N, 4)`` uint8 array.

    Raises:
        ValueError: If ``pixels`` is not an ``(N, 4)`` uint8 array.
    """
    if (
        pixels.dtype != np.uint8
        or pixels.ndim != 2
        or pixels.shape[1] != _RGBA_CHANNELS
    ):
        raise ValueError(
            "unique-RGBA reduction requires an (N, 4) uint8 array, got "
            f"dtype={pixels.dtype} shape={pixels.shape}"
        )
    return np.ascontiguousarray(pixels)


def _lex_order(rows: npt.NDArray[np.uint8]) -> npt.NDArray[np.intp]:
    """Return the index order sorting ``rows`` lexicographically by (R, G, B, A).

    ``np.lexsort`` treats its **last** key as primary, so the channels are passed
    A, B, G, R to yield R-primary, then G, then B, then A ascending.
    """
    return np.lexsort((rows[:, 3], rows[:, 2], rows[:, 1], rows[:, 0]))


def _packed_keys(pixels: npt.NDArray[np.uint8]) -> npt.NDArray[np.uint32]:
    """Pack each C-contiguous ``(R, G, B, A)`` uint8 row into one ``uint32``."""
    rows = _as_rgba_rows(pixels)
    return rows.view(np.uint32).reshape(-1)


def _rows_and_order(
    uniq_keys: npt.NDArray[np.uint32],
) -> Tuple[npt.NDArray[np.uint8], npt.NDArray[np.intp]]:
    """Unpack ``uniq_keys`` to ``(K, 4)`` uint8 rows and their (R, G, B, A) order."""
    unique_rows = uniq_keys.view(np.uint8).reshape(-1, _RGBA_CHANNELS)
    return unique_rows, _lex_order(unique_rows)


def unique_rgba_counts(
    pixels: npt.NDArray[np.uint8],
) -> Tuple[npt.NDArray[np.uint8], npt.NDArray[np.intp]]:
    """Return ``(unique_rows, counts)`` for an ``(N, 4)`` uint8 buffer.

    Semantically identical to ``np.unique(pixels, axis=0, return_counts=True)``:
    ``unique_rows`` is the distinct colours ascending as ``(R, G, B, A)`` tuples
    and ``counts[i]`` is the occurrence count of ``unique_rows[i]``.

    Raises:
        ValueError: If ``pixels`` is not an ``(N, 4)`` uint8 array.
    """
    uniq_keys, counts = np.unique(_packed_keys(pixels), return_counts=True)
    unique_rows, order = _rows_and_order(uniq_keys)
    return unique_rows[order], np.asarray(counts)[order]


def unique_rgba_inverse(
    pixels: npt.NDArray[np.uint8],
) -> Tuple[npt.NDArray[np.uint8], npt.NDArray[np.intp]]:
    """Return ``(unique_rows, inverse)`` for an ``(N, 4)`` uint8 buffer.

    Semantically identical to ``np.unique(pixels, axis=0, return_inverse=True)``:
    ``unique_rows`` is the distinct colours ascending as ``(R, G, B, A)`` tuples
    and ``unique_rows[inverse]`` reconstructs the original row sequence.

    Raises:
        ValueError: If ``pixels`` is not an ``(N, 4)`` uint8 array.
    """
    uniq_keys, raw_inverse = np.unique(_packed_keys(pixels), return_inverse=True)
    unique_rows, order = _rows_and_order(uniq_keys)
    # Remap each pixel's old (uint32-sort) index to its new (R, G, B, A) index.
    rank = np.empty(order.shape[0], dtype=np.intp)
    rank[order] = np.arange(order.shape[0], dtype=np.intp)
    inverse = rank[np.asarray(raw_inverse).reshape(-1)]
    return unique_rows[order], inverse
