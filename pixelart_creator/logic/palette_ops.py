"""Colour cycling + palette swap/remap, reversible (zero Qt, S11).

* :func:`cycle_palette` rotates the colours within a palette index range — the
  pure per-step transform behind the colour-cycling preview (the animation *rate*
  is a UI concern). Cycling by the range length is the identity (SC-L013-2).
* :func:`swap_indices` / :func:`remap_colors` remap an indexed / RGBA buffer
  through a caller-supplied mapping.
* :func:`make_cycle_command` / :func:`make_swap_command` capture an application as
  a reversible :class:`~pixelart_creator.logic.history.PixelEdit` so
  ``ui/commands.py`` wraps it as one ``QUndoCommand`` (REQ-P3-LOGIC-017); the
  inverse remap restores the original exactly (SC-L014-2).

REQ-P3-LOGIC-013, -014.
"""

from __future__ import annotations

from typing import List, Mapping, Optional

import numpy as np

from pixelart_creator.logic import history
from pixelart_creator.logic.color import RGBA, is_rgba, rgba
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import SelectionMask

__all__ = [
    "cycle_palette",
    "swap_indices",
    "remap_colors",
    "make_cycle_command",
    "make_swap_command",
]

_INDEX_MIN = 0
_INDEX_MAX = 255


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
    buffer: PixelBuffer, start: int, end: int, step: int
) -> history.Command:
    """Commit a colour-cycle preview on an indexed ``buffer`` as one command.

    Bakes the rotation of index range ``[start, end]`` by ``step`` into the
    buffer's indices (a reversible :class:`history.PixelEdit`, returned
    **unapplied**). Undo restores the pre-cycle buffer exactly.

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
    return history.PixelEdit(buffer, changes, label="colour cycle")


def make_swap_command(
    buffer: PixelBuffer,
    mapping: Mapping[int, int],
    mask: Optional[SelectionMask] = None,
) -> history.Command:
    """Build a reversible command remapping ``buffer`` indices through ``mapping``.

    Returns a :class:`history.PixelEdit` (returned **unapplied**); its undo
    restores the original buffer exactly (the inverse remap, SC-L014-2). With a
    ``mask`` only masked pixels change.

    Raises:
        PaletteError: If ``buffer`` is not indexed or an index is out of range.
    """
    changes = _index_changes(buffer, mapping, mask)
    return history.PixelEdit(buffer, changes, label="palette swap")
