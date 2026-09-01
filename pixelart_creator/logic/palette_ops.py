# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Colour cycling, palette swap/remap, and indexed-mode conversion (zero Qt, S11).

* :func:`cycle_palette` rotates the colours within a palette index range — the
  pure per-step transform behind the colour-cycling preview (the animation *rate*
  is a UI concern). Cycling by the range length is the identity (SC-L013-2).
* :func:`swap_indices` / :func:`remap_colors` remap an indexed / RGBA buffer
  through a caller-supplied mapping.
* :func:`to_indexed` / :func:`to_rgba` convert a buffer between RGBA and indexed
  storage against a :class:`~pixelart_creator.logic.palette.Palette` — the logic
  half of the indexed-mode workflow (REQ-P3-UI-014). The pairing is **lossy to
  the palette**: ``to_rgba(to_indexed(rgba, pal), pal)`` reproduces the
  *palette-quantised* image (its colour set ⊆ ``pal``), never the original RGBA,
  because :func:`to_indexed` snaps each pixel to its nearest palette colour.
* :func:`make_cycle_command` / :func:`make_swap_command` capture an application as
  a reversible :class:`~pixelart_creator.logic.history.PixelEdit`, returned
  **unapplied** so ``ui/commands.py`` wraps each as one ``QUndoCommand``
  (REQ-P3-LOGIC-017; ``apply ∘ undo = identity``). Whole-document RGBA↔indexed
  *mode* conversion is **not** here: because colour mode is document-wide and must
  flip ``Document.mode`` atomically with the buffers (ADR-0008), it lives in
  :meth:`pixelart_creator.logic.document.Document.make_convert_to_indexed_command`
  / :meth:`~pixelart_creator.logic.document.Document.make_convert_to_rgba_command`,
  which call the pure :func:`to_indexed` / :func:`to_rgba` functions below.

REQ-P3-LOGIC-013, -014; REQ-P3-UI-014 (logic support).
"""

from __future__ import annotations

from typing import List, Mapping, Optional

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history, perceptual
from pixelart_creator.logic._rgba_unique import unique_rgba_inverse
from pixelart_creator.logic.color import RGBA, is_rgba, rgba
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import SelectionMask

__all__ = [
    "IndexedModeError",
    "cycle_palette",
    "swap_indices",
    "remap_colors",
    "to_indexed",
    "to_rgba",
    "make_cycle_command",
    "make_swap_command",
]

_INDEX_MIN = 0
_INDEX_MAX = 255
_INDEX_METRICS = ("distance_sq", "ciede2000")


class IndexedModeError(ValueError):
    """Raised on an invalid buffer mode or metric for indexed-mode conversion."""


def _check_range(palette: Palette, start: int, end: int) -> int:
    n = len(palette)
    for name, value in (("start", start), ("end", end)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise PaletteError(f"{name} must be an int, got {value!r}")
    if not (0 <= start <= end < n):
        raise PaletteError(f"cycle range [{start}, {end}] out of bounds 0..{n - 1}")
    return end - start + 1


def cycle_palette(palette: Palette, start: int, end: int, step: int) -> Palette:
    """Return a new palette with colours in ``[start, end]`` rotated by ``step``.

    Colours outside the range are unchanged. A positive ``step`` rotates forward;
    cycling by ``len(range)`` returns the original (SC-L013-2), and forward then
    backward by the same ``step`` is the identity (SC-L013-3). Deterministic.

    Raises:
        PaletteError: If the range is out of bounds (SC-L013-4).
    """
    length = _check_range(palette, start, end)
    if not isinstance(step, int) or isinstance(step, bool):
        raise PaletteError(f"step must be an int, got {step!r}")
    colors = palette.colors()
    segment = colors[start : end + 1]
    k = step % length
    rotated = segment[-k:] + segment[:-k] if k else segment
    colors[start : end + 1] = rotated
    return Palette(colors)


def _check_index(value: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise PaletteError(f"{label} must be an int, got {value!r}")
    if not (_INDEX_MIN <= value <= _INDEX_MAX):
        raise PaletteError(f"{label} {value} out of range {_INDEX_MIN}..{_INDEX_MAX}")
    return value


def swap_indices(buffer: PixelBuffer, mapping: Mapping[int, int]) -> PixelBuffer:
    """Return a copy of an indexed ``buffer`` with indices remapped.

    Each pixel index present in ``mapping`` becomes its mapped value; others are
    unchanged. Deterministic (SC-L014-4).

    Raises:
        PaletteError: If ``buffer`` is not indexed, or a key/value is out of the
            ``0..255`` index space (SC-L014-3).
    """
    if buffer.mode is not ColorMode.INDEXED:
        raise PaletteError("swap_indices requires an indexed buffer")
    for src, dst in mapping.items():
        _check_index(src, "source index")
        _check_index(dst, "target index")
    out = buffer.copy()
    data = out.data
    result = data.copy()
    for src, dst in mapping.items():
        result[data == src] = dst
    out.data[:, :] = result
    return out


def remap_colors(buffer: PixelBuffer, mapping: Mapping[RGBA, RGBA]) -> PixelBuffer:
    """Return a copy of an RGBA ``buffer`` with colours remapped (CL-14).

    Each pixel whose colour is a key of ``mapping`` becomes the mapped colour;
    others are unchanged. Deterministic.

    Raises:
        PaletteError: If ``buffer`` is not RGBA, or a key/value is not RGBA.
    """
    if buffer.mode is not ColorMode.RGBA:
        raise PaletteError("remap_colors requires an RGBA buffer")
    out = buffer.copy()
    data = out.data
    source = data.copy()
    for src, dst in mapping.items():
        if not is_rgba(src) or not is_rgba(dst):
            raise PaletteError(f"mapping entry must be RGBA→RGBA: {src!r}->{dst!r}")
        match = np.all(source == np.asarray(rgba(*src), dtype=np.uint8), axis=-1)
        data[match] = rgba(*dst)
    return out


def _index_changes(
    buffer: PixelBuffer,
    mapping: Mapping[int, int],
    mask: Optional[SelectionMask],
) -> List[history.PixelChange]:
    remapped = swap_indices(buffer, mapping)
    changes: List[history.PixelChange] = []
    for y in range(buffer.height):
        for x in range(buffer.width):
            if mask is not None and not mask.is_selected(x, y):
                continue
            old = buffer.get_pixel(x, y)
            new = remapped.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
    return changes


def make_cycle_command(
    buffer: PixelBuffer,
    start: int,
    end: int,
    step: int,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Commit a colour-cycle preview on an indexed ``buffer`` as one command.

    Bakes the rotation of index range ``[start, end]`` by ``step`` into the
    buffer's indices (a reversible :class:`history.PixelEdit`, returned
    **unapplied**). Undo restores the pre-cycle buffer exactly.

    Args:
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2, task T27); passed straight through to
            :class:`history.PixelEdit`.

    Raises:
        PaletteError: If ``buffer`` is not indexed or the range is invalid.
    """
    if buffer.mode is not ColorMode.INDEXED:
        raise PaletteError("make_cycle_command requires an indexed buffer")
    if end < start:
        raise PaletteError(f"cycle range [{start}, {end}] is empty")
    for name, value in (("start", start), ("end", end)):
        _check_index(value, name)
    if not isinstance(step, int) or isinstance(step, bool):
        raise PaletteError(f"step must be an int, got {step!r}")
    length = end - start + 1
    k = step % length
    mapping = {start + j: start + ((j + k) % length) for j in range(length)}
    changes = _index_changes(buffer, mapping, None)
    return history.PixelEdit(buffer, changes, label="colour cycle", target=target)


def make_swap_command(
    buffer: PixelBuffer,
    mapping: Mapping[int, int],
    mask: Optional[SelectionMask] = None,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Build a reversible command remapping ``buffer`` indices through ``mapping``.

    Returns a :class:`history.PixelEdit` (returned **unapplied**); its undo
    restores the original buffer exactly (the inverse remap, SC-L014-2). With a
    ``mask`` only masked pixels change.

    Args:
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2, task T27); passed straight through to
            :class:`history.PixelEdit`.

    Raises:
        PaletteError: If ``buffer`` is not indexed or an index is out of range.
    """
    changes = _index_changes(buffer, mapping, mask)
    return history.PixelEdit(buffer, changes, label="palette swap", target=target)


# -- indexed-mode conversion (REQ-P3-UI-014 logic support) --------------------


def _nearest_index_map(
    unique: npt.NDArray[np.int64], pal: npt.NDArray[np.int64]
) -> npt.NDArray[np.intp]:
    """Return the nearest-palette index (squared RGBA distance) per unique colour.

    Vectorised over the palette (F7). Ties resolve to the lower index — a strict
    ``<`` keeps the first minimum — matching :meth:`Palette.nearest_index`
    (deterministic, P2).
    """
    best = np.zeros(unique.shape[0], dtype=np.intp)
    best_dist = np.full(unique.shape[0], np.inf, dtype=np.float64)
    for i in range(pal.shape[0]):
        diff = (unique - pal[i]).astype(np.float64)
        dist = np.einsum("ij,ij->i", diff, diff)
        closer = dist < best_dist
        best_dist = np.where(closer, dist, best_dist)
        best = np.where(closer, i, best)
    return best


def to_indexed(
    buffer: PixelBuffer, palette: Palette, *, metric: str = "distance_sq"
) -> PixelBuffer:
    """Return an INDEXED copy of an RGBA ``buffer`` mapped onto ``palette``.

    Each pixel becomes the index of its nearest palette colour — by squared RGBA
    distance (``'distance_sq'``, the fast default matching
    :meth:`Palette.nearest_index`) or perceptual ΔE00 (``'ciede2000'``, opt-in,
    delegating to :mod:`~pixelart_creator.logic.perceptual`, CL-10/CL-11). Ties
    resolve to the lower index (deterministic, P2). Vectorised over the buffer's
    unique colours (F7).

    This is the RGBA→indexed half of the indexed-mode workflow (REQ-P3-UI-014);
    :func:`to_rgba` is its palette-lookup inverse. The pairing is **lossy to the
    palette**: ``to_rgba(to_indexed(rgba, pal), pal)`` reproduces the
    palette-quantised image (colour set ⊆ ``pal``), not the original RGBA (see
    the module docstring). Because ``palette`` holds at most ``MAX_PALETTE_SIZE``
    (256) colours, the resulting indices always fit ``uint8``.

    Raises:
        IndexedModeError: If ``buffer`` is not RGBA or ``metric`` is unknown.
        PaletteError: If ``palette`` is empty.
    """
    if buffer.mode is not ColorMode.RGBA:
        raise IndexedModeError("to_indexed requires an RGBA source buffer")
    if metric not in _INDEX_METRICS:
        raise IndexedModeError(
            f"unknown metric {metric!r}; expected one of {_INDEX_METRICS}"
        )
    colors = palette.colors()
    if not colors:
        raise PaletteError("cannot index against an empty palette")

    unique, inverse = unique_rgba_inverse(buffer.data.reshape(-1, 4))
    if metric == "distance_sq":
        uniq_idx = _nearest_index_map(
            unique.astype(np.int64), np.asarray(colors, dtype=np.int64)
        )
    else:
        uniq_idx = np.array(
            [
                perceptual.nearest_index_perceptual(
                    palette, (int(c[0]), int(c[1]), int(c[2]), int(c[3]))
                )
                for c in unique
            ],
            dtype=np.intp,
        )
    indices = uniq_idx[inverse.reshape(-1)]
    out = PixelBuffer(buffer.width, buffer.height, ColorMode.INDEXED)
    out.data[:, :] = indices.reshape(buffer.height, buffer.width).astype(np.uint8)
    return out


def to_rgba(buffer: PixelBuffer, palette: Palette) -> PixelBuffer:
    """Return an RGBA copy of an INDEXED ``buffer`` by ``palette`` lookup.

    Each palette index is replaced by its RGBA colour — the inverse of
    :func:`to_indexed` (REQ-P3-UI-014). Deterministic; vectorised (F7).

    Raises:
        IndexedModeError: If ``buffer`` is not indexed.
        PaletteError: If ``palette`` is empty or the buffer references an index
            beyond the palette's range.
    """
    if buffer.mode is not ColorMode.INDEXED:
        raise IndexedModeError("to_rgba requires an indexed source buffer")
    colors = palette.colors()
    if not colors:
        raise PaletteError("cannot look up against an empty palette")
    indices = buffer.data
    max_index = int(indices.max()) if indices.size else 0
    if max_index >= len(colors):
        raise PaletteError(
            f"buffer references index {max_index} but palette has "
            f"{len(colors)} colour(s)"
        )
    pal = np.asarray(colors, dtype=np.uint8)
    out = PixelBuffer(buffer.width, buffer.height, ColorMode.RGBA)
    out.data[:, :] = pal[indices]
    return out
