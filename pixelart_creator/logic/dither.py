# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Ordered (Bayer) + Floyd–Steinberg dithering onto a palette (zero Qt, S11).

Both routines map a source RGBA buffer onto a **target palette**: the output's
colour set is a strict subset of the palette (a mapping, not a blend) —
acceptance-critical (SC-L006-1, SC-L007-1). :func:`make_dither_command` captures
an application as a reversible :class:`~pixelart_creator.logic.history.PixelEdit`
so ``ui/commands.py`` can wrap it as one ``QUndoCommand`` (REQ-P3-LOGIC-017).

Grounding: the Bayer recurrence and matrices, and the Floyd–Steinberg 7/3/5/1÷16
weights (pins recorded in the docs/adr/0003-hardware-palette-data-placement.md
family of ADRs; original research record lives outside this repository), Topic
5 (F9). Those matrix values and coefficients are intrinsic to the algorithms, so
they stay **local** here (ADR-0001); only ``BAYER_MATRIX_SIZE`` (which size) is a
tuning scalar in :mod:`~pixelart_creator.logic.constants`. REQ-P3-LOGIC-006, -007.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history
from pixelart_creator.logic.color import CHANNEL_MAX
from pixelart_creator.logic.constants import BAYER_MATRIX_SIZE
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import SelectionMask

__all__ = ["DitherError", "ordered_dither", "floyd_steinberg", "make_dither_command"]

_MODES = ("ordered", "floyd_steinberg")

# Floyd–Steinberg forward-diffusion weights (intrinsic, research Topic 5.2).
_FS_RIGHT = 7.0 / 16.0
_FS_BELOW_LEFT = 3.0 / 16.0
_FS_BELOW = 5.0 / 16.0
_FS_BELOW_RIGHT = 1.0 / 16.0


class DitherError(ValueError):
    """Raised on an invalid dither mode or matrix size."""


def _require_rgba(source: PixelBuffer) -> None:
    if source.mode is not ColorMode.RGBA:
        raise DitherError("dithering requires an RGBA source buffer")


def _palette_array(palette: Palette) -> npt.NDArray[np.int16]:
    colors = palette.colors()
    if not colors:
        raise PaletteError("cannot dither against an empty palette")
    return np.asarray(colors, dtype=np.int16)


def _bayer_matrix(size: int) -> npt.NDArray[np.float64]:
    """Return an ``size``x``size`` Bayer threshold map normalised to ``[0, 1)``.

    Built by the van der Corput / Bayer recurrence (research Topic 5.1); ``size``
    must be a power of two.

    Raises:
        DitherError: If ``size`` is not a positive power of two.
    """
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise DitherError(f"matrix size must be a positive int, got {size!r}")
    if size & (size - 1) != 0:
        raise DitherError(f"matrix size must be a power of two, got {size}")
    matrix = np.zeros((1, 1), dtype=np.float64)
    n = 1
    while n < size:
        ones = np.ones((n, n), dtype=np.float64)
        matrix = np.block(
            [
                [4.0 * matrix, 4.0 * matrix + 2.0 * ones],
                [4.0 * matrix + 3.0 * ones, 4.0 * matrix + 1.0 * ones],
            ]
        )
        n *= 2
    return matrix / (size * size)


def _nearest_indices(
    pixels: npt.NDArray[np.floating], pal: npt.NDArray[np.int16]
) -> npt.NDArray[np.intp]:
    """Return the nearest palette index (squared RGBA distance) per pixel.

    ``pixels`` is ``(..., 4)`` float; ties resolve to the lower index (P2).
    """
    flat = pixels.reshape(-1, 4)
    best = np.zeros(flat.shape[0], dtype=np.intp)
    best_dist = np.full(flat.shape[0], np.inf, dtype=np.float64)
    for i in range(pal.shape[0]):
        diff = flat - pal[i].astype(np.float64)
        dist = np.einsum("ij,ij->i", diff, diff)
        closer = dist < best_dist
        best_dist = np.where(closer, dist, best_dist)
        best = np.where(closer, i, best)
    return best.reshape(pixels.shape[:-1])


def ordered_dither(
    source: PixelBuffer, palette: Palette, *, matrix_size: int = BAYER_MATRIX_SIZE
) -> PixelBuffer:
    """Return a copy of ``source`` ordered-dithered onto ``palette``.

    Each pixel is offset by ``amplitude·(threshold - 0.5)`` from the tiled Bayer
    map, then snapped to its nearest palette colour. The output colour set is a
    subset of ``palette`` (SC-L006-1); deterministic for fixed
    input+palette+matrix (SC-L006-3).

    Raises:
        DitherError: If ``source`` is not RGBA or ``matrix_size`` is invalid.
        PaletteError: If ``palette`` is empty.
    """
    _require_rgba(source)
    pal = _palette_array(palette)
    matrix = _bayer_matrix(matrix_size)

    h, w = source.height, source.width
    data = source.data.astype(np.float64)
    tiled = np.tile(
        matrix,
        ((h + matrix_size - 1) // matrix_size, (w + matrix_size - 1) // matrix_size),
    )[:h, :w]
    # Amplitude ≈ one palette step (intrinsic dither spread, research Topic 5.1).
    amplitude = CHANNEL_MAX / float(pal.shape[0])
    offset = (amplitude * (tiled - 0.5))[:, :, np.newaxis]
    adjusted = data + offset
    indices = _nearest_indices(adjusted, pal)

    out = PixelBuffer(w, h, ColorMode.RGBA)
    out.data[:, :] = pal[indices].astype(np.uint8)
    return out


def floyd_steinberg(source: PixelBuffer, palette: Palette) -> PixelBuffer:
    """Return a copy of ``source`` Floyd–Steinberg-dithered onto ``palette``.

    Forward error diffusion with the 7/16, 3/16, 5/16, 1/16 weights (research
    Topic 5.2). The output colour set is a subset of ``palette`` (SC-L007-1);
    deterministic for fixed input+palette (SC-L007-3).

    Raises:
        DitherError: If ``source`` is not RGBA.
        PaletteError: If ``palette`` is empty.
    """
    _require_rgba(source)
    pal = _palette_array(palette)
    pal_f = pal.astype(np.float64)

    h, w = source.height, source.width
    work = source.data.astype(np.float64)
    out = PixelBuffer(w, h, ColorMode.RGBA)
    result = out.data

    for y in range(h):
        for x in range(w):
            old = work[y, x]
            diff = pal_f - old
            idx = int(np.argmin(np.einsum("ij,ij->i", diff, diff)))
            new = pal_f[idx]
            result[y, x] = pal[idx].astype(np.uint8)
            error = old - new
            if x + 1 < w:
                work[y, x + 1] += error * _FS_RIGHT
            if y + 1 < h:
                if x - 1 >= 0:
                    work[y + 1, x - 1] += error * _FS_BELOW_LEFT
                work[y + 1, x] += error * _FS_BELOW
                if x + 1 < w:
                    work[y + 1, x + 1] += error * _FS_BELOW_RIGHT
    return out


def make_dither_command(
    buffer: PixelBuffer,
    palette: Palette,
    mode: str,
    mask: Optional[SelectionMask] = None,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Build a reversible command dithering ``buffer`` onto ``palette``.

    Args:
        buffer: The RGBA buffer to dither in place (the command is returned
            **unapplied**; push it with ``execute=True``).
        palette: The target palette (output ⊆ palette).
        mode: ``'ordered'`` or ``'floyd_steinberg'``.
        mask: If given, only masked pixels change; others are untouched.
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2); passed straight through to
            :class:`history.PixelEdit`.

    Returns:
        A :class:`history.PixelEdit` whose undo restores the prior pixels exactly
        (``apply ∘ undo = identity``, SC-L017-1).

    Raises:
        DitherError: If ``mode`` is not recognised.
        PaletteError: If ``palette`` is empty.
    """
    if mode == "ordered":
        dithered = ordered_dither(buffer, palette)
    elif mode == "floyd_steinberg":
        dithered = floyd_steinberg(buffer, palette)
    else:
        raise DitherError(f"unknown dither mode {mode!r}; expected one of {_MODES}")

    changes: List[history.PixelChange] = []
    for y in range(buffer.height):
        for x in range(buffer.width):
            if mask is not None and not mask.is_selected(x, y):
                continue
            old = buffer.get_pixel(x, y)
            new = dithered.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
    return history.PixelEdit(buffer, changes, label=f"dither ({mode})", target=target)
