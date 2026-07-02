"""Selection mask model, builders, ops, and mask-constrained editing (zero Qt).

:class:`SelectionMask` is a boolean region over a buffer's ``(width, height)`` —
a NumPy ``bool`` array of shape ``(H, W)``, origin top-left. Builders construct a
mask from a rectangle, a freehand lasso (even-odd scanline fill, auto-closed), or
a magic-wand (contiguous colour, reusing ``drawing.flood_fill`` +
``color.distance_sq``). Ops (invert / clear / translate / combine) return new
masks. :func:`apply_masked` constrains any edit to selected pixels;
:func:`move_selection` is the reversible floating cut-move. Zero Qt (S11);
REQ-P2-LOGIC-001..006, 010.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.constants import MAGIC_WAND_DEFAULT_TOLERANCE
from pixelart_creator.logic.drawing import flood_fill
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue

Coord = Tuple[int, int]

#: Selection combine modes for :meth:`SelectionMask.combine`.
COMBINE_REPLACE = "replace"
COMBINE_ADD = "add"
COMBINE_SUBTRACT = "subtract"
_COMBINE_MODES = (COMBINE_REPLACE, COMBINE_ADD, COMBINE_SUBTRACT)


class SelectionError(ValueError):
    """Raised on invalid selection dimensions, arguments, or operations."""


def _check_dims(width: int, height: int) -> None:
    for name, value in (("width", width), ("height", height)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise SelectionError(f"{name} must be an int, got {value!r}")
        if value <= 0:
            raise SelectionError(f"{name} must be positive, got {value}")


class SelectionMask:
    """A boolean region over a buffer's dimensions (origin top-left)."""

    __slots__ = ("_data",)

    def __init__(self, width: int, height: int) -> None:
        """Create an empty mask sized ``width`` x ``height``.

        Raises:
            SelectionError: If either dimension is not a positive int.
        """
        _check_dims(width, height)
        self._data: npt.NDArray[np.bool_] = np.zeros((height, width), dtype=bool)

    # -- geometry ---------------------------------------------------------

    @property
    def width(self) -> int:
        """Mask width in pixels."""
        return int(self._data.shape[1])

    @property
    def height(self) -> int:
        """Mask height in pixels."""
        return int(self._data.shape[0])

    @property
    def is_empty(self) -> bool:
        """Whether nothing is selected."""
        return not bool(self._data.any())

    def is_selected(self, x: int, y: int) -> bool:
        """Whether ``(x, y)`` is selected; out-of-bounds returns ``False``."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return bool(self._data[y, x])

    def count(self) -> int:
        """Number of selected pixels."""
        return int(self._data.sum())

    def bounds(self) -> Optional[Tuple[int, int, int, int]]:
        """Tight inclusive bounding box ``(x0, y0, x1, y1)``, or ``None`` if empty."""
        if self.is_empty:
            return None
        ys, xs = np.nonzero(self._data)
        return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

    def data(self) -> npt.NDArray[np.bool_]:
        """Return an independent ``(H, W)`` bool copy of the mask."""
        return self._data.copy()

    def copy(self) -> "SelectionMask":
        """Return an independent copy of this mask."""
        out = SelectionMask(self.width, self.height)
        out._data[:, :] = self._data
        return out

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SelectionMask):
            return NotImplemented
        return np.array_equal(self._data, other._data)

    def __hash__(self) -> None:  # type: ignore[override]
        return None  # mutable value type; not hashable

    def __repr__(self) -> str:
        return f"SelectionMask({self.width}x{self.height}, {self.count()} selected)"

    # -- ops (return new masks) ------------------------------------------

    def invert(self) -> "SelectionMask":
        """Return the complement of this mask within the buffer bounds."""
        out = SelectionMask(self.width, self.height)
        out._data[:, :] = ~self._data
        return out

    def cleared(self) -> "SelectionMask":
        """Return an empty mask of the same size (deselect / clear)."""
        return SelectionMask(self.width, self.height)

    def translate(self, dx: int, dy: int) -> "SelectionMask":
        """Return a copy shifted by ``(dx, dy)``, clipping off-buffer selection."""
        out = SelectionMask(self.width, self.height)
        h, w = self.height, self.width
        sx0 = max(0, -dx)
        sy0 = max(0, -dy)
        sx1 = min(w, w - dx)
        sy1 = min(h, h - dy)
        if sx0 < sx1 and sy0 < sy1:
            out._data[sy0 + dy : sy1 + dy, sx0 + dx : sx1 + dx] = self._data[
                sy0:sy1, sx0:sx1
            ]
        return out

    def combine(self, other: "SelectionMask", mode: str) -> "SelectionMask":
        """Combine with ``other`` using ``'replace'`` / ``'add'`` / ``'subtract'``.

        Raises:
            SelectionError: On mismatched dimensions or an unknown mode.
        """
        if mode not in _COMBINE_MODES:
            raise SelectionError(
                f"combine mode must be one of {_COMBINE_MODES}, got {mode!r}"
            )
        if other.width != self.width or other.height != self.height:
            raise SelectionError("combine requires masks of equal dimensions")
        out = SelectionMask(self.width, self.height)
        if mode == COMBINE_REPLACE:
            out._data[:, :] = other._data
        elif mode == COMBINE_ADD:
            out._data[:, :] = self._data | other._data
        else:  # COMBINE_SUBTRACT
            out._data[:, :] = self._data & ~other._data
        return out


# -- builders -------------------------------------------------------------


def rect_mask(
    width: int, height: int, x0: int, y0: int, x1: int, y1: int
) -> SelectionMask:
    """Build a rectangle selection from two opposite corners.

    Swapped corners are normalised (``drawing.rectangle`` convention) and the
    rectangle is clipped to the buffer. A zero/negative rectangle yields an empty
    mask.
    """
    mask = SelectionMask(width, height)
    lx, rx = (x0, x1) if x0 <= x1 else (x1, x0)
    ty, by = (y0, y1) if y0 <= y1 else (y1, y0)
    cx0 = max(0, lx)
    cy0 = max(0, ty)
    cx1 = min(width - 1, rx)
    cy1 = min(height - 1, by)
    if cx0 <= cx1 and cy0 <= cy1:
        mask._data[cy0 : cy1 + 1, cx0 : cx1 + 1] = True
    return mask


def _trace_line(x0: int, y0: int, x1: int, y1: int) -> List[Coord]:
    """Bresenham integer line as a coordinate list (pure, unclipped)."""
    coords: List[Coord] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = x0, y0
    while True:
        coords.append((cx, cy))
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sx
        if e2 <= dx:
            err += dx
            cy += sy
    return coords


def lasso_mask(
    width: int, height: int, vertices: Sequence[Tuple[int, int]]
) -> SelectionMask:
    """Build a freehand-lasso selection from polygon vertices.

    The path is auto-closed (last -> first vertex); the interior is filled by the
    even-odd (scanline) rule and the traced boundary is included. A degenerate
    path (< 3 distinct points) yields at most the traced pixels. Points are
    clipped to the buffer. Deterministic.
    """
    mask = SelectionMask(width, height)
    pts = [(int(px), int(py)) for px, py in vertices]
    if not pts:
        return mask

    distinct = list(dict.fromkeys(pts))

    def _mark(cx: int, cy: int) -> None:
        if 0 <= cx < width and 0 <= cy < height:
            mask._data[cy, cx] = True

    # Trace the closed boundary (also handles the degenerate < 3 distinct case).
    closed = pts + [pts[0]]
    for (ax, ay), (bx, by) in zip(closed, closed[1:]):
        for cx, cy in _trace_line(ax, ay, bx, by):
            _mark(cx, cy)

    if len(distinct) < 3:
        return mask

    # Even-odd scanline fill of the polygon interior.
    poly = distinct
    n = len(poly)
    y_min = max(0, min(p[1] for p in poly))
    y_max = min(height - 1, max(p[1] for p in poly))
    for y in range(y_min, y_max + 1):
        nodes: List[float] = []
        j = n - 1
        for i in range(n):
            yi = poly[i][1]
            yj = poly[j][1]
            if (yi <= y < yj) or (yj <= y < yi):
                t = (y - yi) / (yj - yi)
                nodes.append(poly[i][0] + t * (poly[j][0] - poly[i][0]))
            j = i
        nodes.sort()
        for k in range(0, len(nodes) - 1, 2):
            xa = int(np.ceil(nodes[k]))
            xb = int(np.floor(nodes[k + 1]))
            for x in range(max(0, xa), min(width - 1, xb) + 1):
                _mark(x, y)
    return mask


def _distinct_value(buffer: PixelBuffer, seed: PixelValue) -> PixelValue:
    """Return a value guaranteed to differ from ``seed`` in the buffer's mode."""
    if buffer.mode is ColorMode.RGBA:
        r, g, b, a = seed  # type: ignore[misc]
        return (255 - r, 255 - g, 255 - b, 255 - a)
    return 0 if seed != 0 else 1


def wand_mask(
    buffer: PixelBuffer,
    x: int,
    y: int,
    *,
    tolerance: int = MAGIC_WAND_DEFAULT_TOLERANCE,
) -> SelectionMask:
    """Build a magic-wand selection: the contiguous colour region at the seed.

    Reuses ``drawing.flood_fill`` contiguity + ``color.distance_sq`` semantics on
    a scratch copy (RGBA tolerance via squared distance; INDEXED exact match,
    tolerance ignored — CL-16). An out-of-bounds seed yields an empty mask.
    """
    mask = SelectionMask(buffer.width, buffer.height)
    if not buffer.in_bounds(x, y):
        return mask
    scratch = buffer.copy()
    seed = scratch.get_pixel(x, y)
    replacement = _distinct_value(scratch, seed)
    for cx, cy in flood_fill(scratch, x, y, replacement, tolerance=tolerance):
        mask._data[cy, cx] = True
    return mask


# -- mask-constrained editing + floating move -----------------------------


def apply_masked(
    buffer: PixelBuffer,
    operation: Callable[[PixelBuffer], List[Tuple[int, int]]],
    mask: Optional[SelectionMask],
) -> List[Tuple[int, int]]:
    """Apply an edit ``operation`` to ``buffer`` only inside ``mask``.

    ``operation`` runs on a scratch copy and returns the coordinates it changed
    (the ``logic/drawing.py`` contract). Only coordinates inside ``mask`` (and
    whose value actually changes) are written back to ``buffer``; pixels outside
    the mask are never touched. With ``mask`` None the operation covers the whole
    buffer (CL-5). Returns exactly the coordinates changed, so the caller can
    build a reversible record (e.g. via ``history.record_edit``).
    """
    if mask is None:
        scratch = buffer.copy()
        changed: List[Tuple[int, int]] = []
        seen: set[Coord] = set()
        for cx, cy in operation(scratch):
            if (cx, cy) in seen:
                continue
            seen.add((cx, cy))
            new = scratch.get_pixel(cx, cy)
            if buffer.get_pixel(cx, cy) != new:
                buffer.set_pixel(cx, cy, new)
                changed.append((cx, cy))
        return changed

    scratch = buffer.copy()
    changed = []
    seen = set()
    for cx, cy in operation(scratch):
        if (cx, cy) in seen or not mask.is_selected(cx, cy):
            continue
        seen.add((cx, cy))
        new = scratch.get_pixel(cx, cy)
        if buffer.get_pixel(cx, cy) != new:
            buffer.set_pixel(cx, cy, new)
            changed.append((cx, cy))
    return changed


def move_selection(
    buffer: PixelBuffer, mask: SelectionMask, dx: int, dy: int
) -> history.Command:
    """Lift the masked pixels and re-stamp them at ``(dx, dy)`` (floating cut).

    The vacated area is filled transparent (RGBA) / index 0 (indexed) — CL-6 — and
    the lifted pixels are re-stamped at the offset (clipped to bounds). Returns an
    unapplied reversible :class:`history.PixelEdit` (push with ``execute=True``);
    ``apply then undo`` restores the buffer exactly.

    Raises:
        SelectionError: On a dimension mismatch or non-int offsets.
    """
    if mask.width != buffer.width or mask.height != buffer.height:
        raise SelectionError("mask dimensions must match the buffer")
    for name, value in (("dx", dx), ("dy", dy)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise SelectionError(f"{name} must be an int, got {value!r}")

    fill: PixelValue = TRANSPARENT if buffer.mode is ColorMode.RGBA else 0
    selected = [(int(cx), int(cy)) for cy, cx in zip(*np.nonzero(mask.data()))]
    source = {(cx, cy): buffer.get_pixel(cx, cy) for cx, cy in selected}

    new_values: dict[Coord, PixelValue] = {}
    for cx, cy in selected:
        new_values[(cx, cy)] = fill
    for cx, cy in selected:
        tx, ty = cx + dx, cy + dy
        if buffer.in_bounds(tx, ty):
            new_values[(tx, ty)] = source[(cx, cy)]

    changes: List[history.PixelChange] = []
    for (cx, cy), new in new_values.items():
        old = buffer.get_pixel(cx, cy)
        if old != new:
            changes.append((cx, cy, old, new))
    return history.PixelEdit(buffer, changes, label="move selection")


__all__ = [
    "SelectionError",
    "SelectionMask",
    "COMBINE_REPLACE",
    "COMBINE_ADD",
    "COMBINE_SUBTRACT",
    "rect_mask",
    "lasso_mask",
    "wand_mask",
    "apply_masked",
    "move_selection",
]
