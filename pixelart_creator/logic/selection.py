# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Selection mask model, builders, ops, and mask-constrained editing (zero Qt).

:class:`SelectionMask` is a boolean region over a buffer's ``(width, height)`` —
a NumPy ``bool`` array of shape ``(H, W)``, origin top-left. Builders construct a
mask from a rectangle, a freehand lasso (even-odd scanline fill, auto-closed), or
a magic-wand (contiguous colour, reusing ``drawing.flood_fill`` +
``color.distance_sq``). Ops (invert / clear / translate / combine) return new
masks. :func:`apply_masked` constrains any edit to selected pixels;
:func:`move_selection` is the reversible floating cut-move. Zero Qt (S11);
REQ-P2-LOGIC-001..006, 010.

The **floating-selection** model (REQ-P2-LOGIC-030..036, ADR-0009) layers a
*non-destructive* move/copy on top of that: :func:`lift_selection` captures the
masked colours into a :class:`FloatingSelection` snapshot **without mutating the
source**; :func:`composite_preview` renders a region-scoped, non-destructive
preview (base never written); :func:`commit_floating` turns the float into one
reversible :class:`history.Command` — MOVE reuses :func:`move_selection`
verbatim, COPY uses the sibling :func:`copy_selection` (stamp without vacate).
Because the base is never written during the float, cancel is a pure no-op and
the lift-time snapshot equals the value read at commit time (ADR-0009 D2).
"""

from __future__ import annotations

import enum
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.constants import MAGIC_WAND_DEFAULT_TOLERANCE
from pixelart_creator.logic.drawing import flood_fill
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue

Coord = Tuple[int, int]

#: Selection combine modes for :meth:`SelectionMask.combine`.
COMBINE_REPLACE = "replace"
COMBINE_ADD = "add"
COMBINE_SUBTRACT = "subtract"
_COMBINE_MODES = (COMBINE_REPLACE, COMBINE_ADD, COMBINE_SUBTRACT)


class FloatMode(enum.Enum):
    """Whether a floating selection MOVES its origin or leaves a COPY behind.

    Module-local (like :class:`~pixelart_creator.logic.pixel_buffer.ColorMode`);
    it is an enum, not a numeric tuning value, so it carries no ``constants.py``
    entry (NFR-6). MOVE vacates the origin on commit; COPY keeps it intact.
    """

    MOVE = "move"
    COPY = "copy"


class SelectionError(ValueError):
    """Raised on invalid selection dimensions, arguments, or operations."""


def _require_int(name: str, value: object) -> int:
    """Return ``value`` as an int, or raise :class:`SelectionError`.

    Booleans are rejected (``bool`` is an ``int`` subclass but never a valid
    coordinate/offset).
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise SelectionError(f"{name} must be an int, got {value!r}")
    return value


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
        """Return the number of selected pixels."""
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
        """Return True if `other` is a SelectionMask with the same selected pixels."""
        if not isinstance(other, SelectionMask):
            return NotImplemented
        return np.array_equal(self._data, other._data)

    def __hash__(self) -> None:  # type: ignore[override]
        """Return None: SelectionMask is a mutable value type and is not hashable."""
        return None  # mutable value type; not hashable

    def __repr__(self) -> str:
        """Return a repr showing dimensions and the current selected-pixel count."""
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
    buffer: PixelBuffer,
    mask: SelectionMask,
    dx: int,
    dy: int,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Lift the masked pixels and re-stamp them at ``(dx, dy)`` (floating cut).

    The vacated area is filled transparent (RGBA) / index 0 (indexed) — CL-6 — and
    the lifted pixels are re-stamped at the offset (clipped to bounds). Returns an
    unapplied reversible :class:`history.PixelEdit` (push with ``execute=True``);
    ``apply then undo`` restores the buffer exactly.

    Args:
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2, task T27); passed straight through to
            :class:`history.PixelEdit`.

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
    return history.PixelEdit(buffer, changes, label="move selection", target=target)


# -- floating selection (non-destructive move / copy) ---------------------
# REQ-P2-LOGIC-030..036; ADR-0009 (lifted-snapshot preview, region-scoped
# composite, commit re-reads the live buffer). MOVE reuses ``move_selection``
# verbatim (D2 snapshot == commit-read invariant); COPY is the sibling
# ``copy_selection`` builder. Zero Qt.


class FloatingSelection:
    """A non-destructive floating move/copy: lifted colours + mask + offset.

    Created by :func:`lift_selection`, never constructed directly by the UI. It
    holds an **immutable snapshot** of the lifted pixel colours (stored as the
    tight mask-bounding-box sub-buffer — *never* a full-canvas copy, per
    ADR-0009 D3 / plan §4.3), the source :class:`SelectionMask`, a
    :class:`FloatMode`, and a **live** integer offset ``(dx, dy)`` that the drag
    interaction updates via :meth:`set_offset`. Constructing a float does not
    mutate the source buffer (REQ-P2-LOGIC-030); the buffer changes only at
    commit (:func:`commit_floating`).
    """

    __slots__ = ("_mask", "_mode", "_colors", "_bbox", "_offset")

    def __init__(
        self,
        mask: SelectionMask,
        mode: FloatMode,
        colors: PixelBuffer,
        bbox: Tuple[int, int, int, int],
        offset: Tuple[int, int] = (0, 0),
    ) -> None:
        """Store the lifted state. Use :func:`lift_selection` in normal code."""
        self._mask = mask
        self._mode = mode
        self._colors = colors
        self._bbox = bbox
        self._offset = (int(offset[0]), int(offset[1]))

    # -- properties -------------------------------------------------------

    @property
    def mode(self) -> FloatMode:
        """The :class:`FloatMode` (MOVE vacates the origin, COPY keeps it)."""
        return self._mode

    @property
    def offset(self) -> Tuple[int, int]:
        """The current live integer offset ``(dx, dy)`` (initially ``(0, 0)``)."""
        return self._offset

    @property
    def width(self) -> int:
        """Width of the floating content's bounding box (constant across drags)."""
        return self._colors.width

    @property
    def height(self) -> int:
        """Height of the floating content's bounding box (constant across drags)."""
        return self._colors.height

    # -- accessors --------------------------------------------------------

    def mask(self) -> SelectionMask:
        """Return an independent copy of the source selection mask.

        Full-buffer-sized (origin top-left), suitable for handing straight to
        :func:`move_selection` / :func:`copy_selection` at commit.
        """
        return self._mask.copy()

    def bounds(self) -> Tuple[int, int, int, int]:
        """Return the floated bounding box ``(x0, y0, x1, y1)`` in scene coords.

        This is the lift bounding box shifted by the live offset — i.e. the
        destination rectangle the preview occupies now. The origin (pre-move)
        bounding box is this shifted back by ``-offset`` (or ``mask().bounds()``).
        Never ``None`` (a float never has an empty mask — see
        :func:`lift_selection`).
        """
        x0, y0, x1, y1 = self._bbox
        dx, dy = self._offset
        return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)

    def set_offset(self, dx: int, dy: int) -> None:
        """Update the live offset ``(dx, dy)`` (integer pixel units).

        Raises:
            SelectionError: If either component is not an int.
        """
        self._offset = (_require_int("dx", dx), _require_int("dy", dy))


def lift_selection(
    buffer: PixelBuffer, mask: SelectionMask, mode: FloatMode
) -> FloatingSelection:
    """Lift the masked colours of ``buffer`` into a :class:`FloatingSelection`.

    Snapshots the masked pixels' colours (the tight mask-bbox sub-buffer)
    **without mutating** ``buffer`` (REQ-P2-LOGIC-030) and pairs them with a copy
    of ``mask`` and the given :class:`FloatMode`, at offset ``(0, 0)``.

    Raises:
        SelectionError: If ``mode`` is not a :class:`FloatMode`, ``mask``
            dimensions differ from ``buffer`` (REQ-P2-LOGIC-036), or ``mask`` is
            empty (ADR-0009 D5 — a lift on an empty mask is a programming error,
            not a control-flow path; no sentinel is returned).
    """
    if not isinstance(mode, FloatMode):
        raise SelectionError(f"mode must be a FloatMode, got {mode!r}")
    if mask.width != buffer.width or mask.height != buffer.height:
        raise SelectionError("mask dimensions must match the buffer")
    box = mask.bounds()
    if box is None:
        raise SelectionError("cannot lift an empty selection")
    x0, y0, x1, y1 = box
    colors = buffer.region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    return FloatingSelection(mask.copy(), mode, colors, box, offset=(0, 0))


def extract_masked(buffer: PixelBuffer, mask: SelectionMask) -> PixelBuffer:
    """Extract the mask-exact selected region of ``buffer`` (ruling P11-R10).

    Returns the tight :meth:`SelectionMask.bounds` region of ``buffer``, with
    every pixel the mask does **not** select set to
    :data:`~pixelart_creator.logic.color.TRANSPARENT` (RGBA) / index ``0``
    (indexed) — the same vacate-fill convention :func:`move_selection` and
    :func:`composite_preview` already use. Unlike :func:`lift_selection`
    (which pairs a bbox crop with the mask for later application),
    this returns the masked colours **already applied**: a single buffer whose
    non-selected pixels carry no content, which is what
    ``REQ-P11-UI-013``'s *"only the selected region's content as the
    payload"* requires for a non-rectangular (lasso/wand) selection.

    For a **rectangular** mask this is byte-identical to
    ``buffer.region(*mask.bounds())`` — every pixel inside the bounding box is
    selected, so nothing is cleared.

    Neither ``buffer`` nor ``mask`` is mutated.

    Raises:
        SelectionError: If ``mask`` dimensions differ from ``buffer``, or
            ``mask`` is empty (ADR-0009 D5 — the same boundary
            :func:`lift_selection` states: a programming error, not a
            control-flow path).
    """
    if mask.width != buffer.width or mask.height != buffer.height:
        raise SelectionError("mask dimensions must match the buffer")
    box = mask.bounds()
    if box is None:
        raise SelectionError("cannot extract an empty selection")
    x0, y0, x1, y1 = box
    out = buffer.region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    fill: PixelValue = TRANSPARENT if buffer.mode is ColorMode.RGBA else 0
    sub_mask = mask.data()[y0 : y1 + 1, x0 : x1 + 1]
    unselected = ~sub_mask
    if unselected.any():
        out.data[unselected] = fill
    return out


def _validate_region(
    base: PixelBuffer, region: Tuple[int, int, int, int]
) -> Tuple[int, int, int, int]:
    """Validate a scene-space ``(x, y, w, h)`` region lies fully within ``base``.

    Mirrors the ADR-0007 ``composite_stack`` rule: validate, never clamp
    (P2 determinism).

    Raises:
        SelectionError: If a component is not an int, the size is degenerate
            (``w < 1`` / ``h < 1``), or the region is out of bounds.
    """
    rx = _require_int("region x", region[0])
    ry = _require_int("region y", region[1])
    rw = _require_int("region w", region[2])
    rh = _require_int("region h", region[3])
    if rw < 1 or rh < 1:
        raise SelectionError(f"region size must be positive, got {rw}x{rh}")
    if rx < 0 or ry < 0 or rx + rw > base.width or ry + rh > base.height:
        raise SelectionError(
            f"region ({rx},{ry},{rw},{rh}) exceeds buffer bounds "
            f"{base.width}x{base.height}"
        )
    return rx, ry, rw, rh


def composite_preview(
    floating: FloatingSelection,
    base: PixelBuffer,
    *,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> PixelBuffer:
    """Render a NON-destructive preview of ``floating`` over ``base``.

    Returns a **new** buffer; ``base`` is never mutated (REQ-P2-LOGIC-031). For
    :attr:`FloatMode.MOVE` the origin (source-mask pixels) reads **vacated**
    (``color.TRANSPARENT`` RGBA / index ``0`` indexed, CL-F2); for
    :attr:`FloatMode.COPY` the origin stays intact. The floated colours are
    stamped at the current offset, clipped to the returned rectangle
    (REQ-P2-LOGIC-035). Deterministic (NFR-2).

    Args:
        floating: The active float (its :attr:`FloatingSelection.offset` is used).
        base: The buffer to preview over (must match the float's mask
            dimensions). Never written.
        region: ``None`` → a full-size copy of ``base`` (reference / test path).
            ``(x, y, w, h)`` → a **region-sized** ``(h, w[, 4])`` buffer with
            implied scene origin ``(x, y)``; element ``(i, j)`` is scene pixel
            ``(x + j, y + i)``. Allocates only the region — **no full-canvas
            allocation** (ADR-0009 D3 / ADR-0007). The UI drag path MUST pass a
            bounded ``region`` so a per-frame preview costs its dirty rect.

    Raises:
        SelectionError: If ``base`` dimensions differ from the float's mask, or
            ``region`` is degenerate / out of bounds (validated, never clamped).
    """
    if floating._mask.width != base.width or floating._mask.height != base.height:
        raise SelectionError("mask dimensions must match the base buffer")

    if region is None:
        rx, ry, rw, rh = 0, 0, base.width, base.height
        out = base.copy()
    else:
        rx, ry, rw, rh = _validate_region(base, region)
        out = base.region(rx, ry, rw, rh)

    out_data = out.data
    mask_data = floating._mask._data  # same-module read; no full-canvas copy
    fill: PixelValue = TRANSPARENT if base.mode is ColorMode.RGBA else 0

    # MOVE: vacate the origin pixels that fall inside the returned region.
    if floating._mode is FloatMode.MOVE:
        origin_sub = mask_data[ry : ry + rh, rx : rx + rw]
        if origin_sub.any():
            out_data[origin_sub] = fill

    # Both modes: stamp the floated colours at the offset, clipped to the region.
    x0, y0, x1, y1 = floating._bbox
    dx, dy = floating._offset
    dest_x0, dest_y0 = x0 + dx, y0 + dy
    fw, fh = floating._colors.width, floating._colors.height

    ix0 = max(dest_x0, rx)
    iy0 = max(dest_y0, ry)
    ix1 = min(dest_x0 + fw, rx + rw)
    iy1 = min(dest_y0 + fh, ry + rh)
    if ix0 < ix1 and iy0 < iy1:
        # Source (mask-bbox) window and destination (region-local) window.
        sx0, sy0 = ix0 - dest_x0, iy0 - dest_y0
        sx1, sy1 = ix1 - dest_x0, iy1 - dest_y0
        ox0, oy0 = ix0 - rx, iy0 - ry
        ox1, oy1 = ix1 - rx, iy1 - ry
        bbox_mask = mask_data[y0 : y1 + 1, x0 : x1 + 1]
        sub_mask = bbox_mask[sy0:sy1, sx0:sx1]
        src = floating._colors.data[sy0:sy1, sx0:sx1]
        dst = out_data[oy0:oy1, ox0:ox1]
        dst[sub_mask] = src[sub_mask]
    return out


def copy_selection(
    buffer: PixelBuffer,
    mask: SelectionMask,
    dx: int,
    dy: int,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Stamp the masked pixels at ``(dx, dy)`` **without** vacating the origin.

    The sibling of :func:`move_selection` for :attr:`FloatMode.COPY`: it copies
    the masked colours to ``(x + dx, y + dy)`` (clipped to bounds,
    REQ-P2-LOGIC-035) and leaves the origin pixels unchanged (CL-F7). Returns an
    unapplied reversible :class:`history.PixelEdit` (push with ``execute=True``);
    ``apply then undo`` restores the buffer exactly. A zero offset produces an
    empty (identity / no-op) command (CL-F8).

    Args:
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2, task T27); passed straight through to
            :class:`history.PixelEdit`.

    Raises:
        SelectionError: On a dimension mismatch or non-int offsets.
    """
    if mask.width != buffer.width or mask.height != buffer.height:
        raise SelectionError("mask dimensions must match the buffer")
    _require_int("dx", dx)
    _require_int("dy", dy)

    selected = [(int(cx), int(cy)) for cy, cx in zip(*np.nonzero(mask.data()))]

    changes: List[history.PixelChange] = []
    for cx, cy in selected:
        tx, ty = cx + dx, cy + dy
        if not buffer.in_bounds(tx, ty):
            continue
        new = buffer.get_pixel(cx, cy)
        old = buffer.get_pixel(tx, ty)
        if old != new:
            changes.append((tx, ty, old, new))
    return history.PixelEdit(buffer, changes, label="copy selection", target=target)


def commit_floating(
    buffer: PixelBuffer,
    floating: FloatingSelection,
    *,
    target: Optional[EditTarget],
) -> history.Command:
    """Turn a floating selection into ONE reversible commit command.

    Dispatches on :attr:`FloatingSelection.mode` at the float's current offset:
    MOVE reuses the shipped :func:`move_selection` **verbatim** (vacate + stamp);
    COPY uses :func:`copy_selection` (stamp only). This is sound because the base
    was never written during the float, so the colours read here equal the lifted
    snapshot (ADR-0009 D2). Returns the command **unapplied** (push with
    ``execute=True``); ``apply then undo = identity``. A zero-offset commit is an
    identity / no-op command (CL-F8).

    Args:
        target: Where this edit landed, or ``None`` if unknown — **required,
            no default** (plan §8.2, task T27); passed straight through to
            :func:`move_selection` / :func:`copy_selection`.

    Raises:
        SelectionError: On a dimension mismatch (propagated from the builder).
    """
    dx, dy = floating.offset
    mask = floating.mask()
    if floating.mode is FloatMode.MOVE:
        return move_selection(buffer, mask, dx, dy, target=target)
    return copy_selection(buffer, mask, dx, dy, target=target)


def destination_is_empty(floating: FloatingSelection, base: PixelBuffer) -> bool:
    """Report whether committing ``floating`` onto ``base`` would overwrite content.

    Pure, read-only and total (REQ-P2-LOGIC-037, Q-19 ruling): mutates neither
    ``floating`` nor ``base``, and never raises for a degenerate destination — an
    empty mask, a fully off-canvas offset, or a zero-offset (identity) commit are
    all simply **empty**, matching :func:`move_selection` /
    :func:`copy_selection`'s own no-op convention (CL-F8).

    "Empty" is the ruling's definition, taken verbatim: the destination is empty
    only when **no content exists there**; any existing content makes it not
    empty (no threshold, no percentage, no tolerance). A pixel carries content
    when, on the **active layer** (``base``), it is **not fully transparent** —
    alpha ``!= 0`` in :attr:`~pixelart_creator.logic.pixel_buffer.ColorMode.RGBA`,
    palette index ``!= 0`` in
    :attr:`~pixelart_creator.logic.pixel_buffer.ColorMode.INDEXED` (the same
    vacate-fill convention :func:`move_selection` uses). The destination is the
    float's mask translated by its current offset and clipped to ``base``'s
    bounds (REQ-P2-LOGIC-035) — only pixels the mask actually covers are
    considered, never the bounding box.

    For :attr:`FloatMode.MOVE`, a destination pixel that coincides with an
    origin (pre-offset) mask pixel is excluded from the check: the commit
    vacates every origin pixel before it stamps, so whatever was there is
    replaced by the float's own write regardless of its prior content, and is
    never "existing content" the user could lose (SC-L037-4). This is *not*
    applied to :attr:`FloatMode.COPY`, whose origin is left intact and is judged
    at its destination only, exactly as the ruling states.

    Args:
        floating: The active float; its live :attr:`FloatingSelection.offset`
            and mask are used.
        base: The buffer the float would commit onto. Never written.

    Raises:
        SelectionError: If ``base`` dimensions differ from the float's mask.
    """
    if floating._mask.width != base.width or floating._mask.height != base.height:
        raise SelectionError("mask dimensions must match the base buffer")

    dx, dy = floating.offset
    if dx == 0 and dy == 0:
        return True

    mask_data = floating._mask._data  # same-module read; no full-canvas copy
    ys, xs = np.nonzero(mask_data)
    if ys.size == 0:
        return True

    dest_x = xs + dx
    dest_y = ys + dy
    in_bounds = (
        (dest_x >= 0) & (dest_x < base.width) & (dest_y >= 0) & (dest_y < base.height)
    )
    dest_x = dest_x[in_bounds]
    dest_y = dest_y[in_bounds]
    if dest_x.size == 0:
        return True

    if floating.mode is FloatMode.MOVE:
        supplied_by_float = mask_data[dest_y, dest_x]
        keep = ~supplied_by_float
        dest_x = dest_x[keep]
        dest_y = dest_y[keep]
        if dest_x.size == 0:
            return True

    if base.mode is ColorMode.RGBA:
        content = base.data[dest_y, dest_x, 3] != 0
    else:
        content = base.data[dest_y, dest_x] != 0
    return not bool(content.any())


__all__ = [
    "SelectionError",
    "SelectionMask",
    "FloatMode",
    "FloatingSelection",
    "COMBINE_REPLACE",
    "COMBINE_ADD",
    "COMBINE_SUBTRACT",
    "rect_mask",
    "lasso_mask",
    "wand_mask",
    "apply_masked",
    "move_selection",
    "extract_masked",
    "lift_selection",
    "composite_preview",
    "copy_selection",
    "commit_floating",
    "destination_is_empty",
]
