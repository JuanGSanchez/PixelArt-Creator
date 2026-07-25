"""RotSprite clean arbitrary-angle rotation (zero Qt, S11).

Implements the grounded four-stage RotSprite pipeline (research Topic 1) with the
four ADR-0002 pins: an ``ROTSPRITE_UPSCALE_FACTOR`` x similarity-based Scale2x
upscale (similarity via ``distance_sq <= ROTSPRITE_SIMILARITY_THRESHOLD``, not
equality) -> per-pixel offset search minimising neighbour SSD (lexicographic
tie-break) -> simultaneous nearest-neighbour rotate + downscale -> single-pixel
detail restore. Every stage only ever *copies* existing pixels, so the output
introduces no interpolated colours (R2). Vectorised with NumPy; deterministic for
a fixed ``(buffer, angle)``. REQ-P2-LOGIC-013.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional, Protocol, Tuple, Union

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history
from pixelart_creator.logic.color import RGBA, TRANSPARENT
from pixelart_creator.logic.constants import (
    ROTSPRITE_SIMILARITY_THRESHOLD,
    ROTSPRITE_UPSCALE_FACTOR,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue

if TYPE_CHECKING:  # annotation-only; masks are duck-typed at runtime (no cycle)
    from pixelart_creator.logic.selection import SelectionMask

_FULL_TURN_DEGREES = 360


class BufferHolder(Protocol):
    """A mutable holder of a :class:`PixelBuffer` (e.g. a document ``Layer``)."""

    buffer: PixelBuffer


# -- Scale2x similarity upscale ------------------------------------------


def _neighbours(
    img: npt.NDArray[np.uint8],
) -> Tuple[
    npt.NDArray[np.uint8],
    npt.NDArray[np.uint8],
    npt.NDArray[np.uint8],
    npt.NDArray[np.uint8],
]:
    """Return edge-clamped (up, down, left, right) neighbour arrays of ``img``."""
    up = np.empty_like(img)
    up[1:] = img[:-1]
    up[0] = img[0]
    down = np.empty_like(img)
    down[:-1] = img[1:]
    down[-1] = img[-1]
    left = np.empty_like(img)
    left[:, 1:] = img[:, :-1]
    left[:, 0] = img[:, 0]
    right = np.empty_like(img)
    right[:, :-1] = img[:, 1:]
    right[:, -1] = img[:, -1]
    return up, down, left, right


def _similar(
    a: npt.NDArray[np.uint8],
    b: npt.NDArray[np.uint8],
    is_rgba: bool,
    threshold: int,
) -> npt.NDArray[np.bool_]:
    """Similarity test: squared-RGBA distance <= threshold, or exact if indexed.

    Uses the same metric as ``color.distance_sq`` (vectorised over the array).
    """
    if is_rgba:
        diff = a.astype(np.int32) - b.astype(np.int32)
        result: npt.NDArray[np.bool_] = (diff * diff).sum(axis=-1) <= threshold
        return result
    return a == b


def _pick(
    cond: npt.NDArray[np.bool_],
    chosen: npt.NDArray[np.uint8],
    fallback: npt.NDArray[np.uint8],
    is_rgba: bool,
) -> npt.NDArray[np.uint8]:
    """Vectorised ``cond ? chosen : fallback`` handling the RGBA channel axis."""
    if is_rgba:
        return np.where(cond[..., None], chosen, fallback)
    return np.where(cond, chosen, fallback)


def _scale2x_similar(
    img: npt.NDArray[np.uint8], is_rgba: bool, threshold: int
) -> npt.NDArray[np.uint8]:
    """One similarity-based Scale2x pass (copy-only; no new colours)."""
    b, h_, d, f = _neighbours(img)  # up, down, left, right
    sim_db = _similar(d, b, is_rgba, threshold)
    sim_bf = _similar(b, f, is_rgba, threshold)
    sim_dh = _similar(d, h_, is_rgba, threshold)
    sim_hf = _similar(h_, f, is_rgba, threshold)

    e = img
    e0 = _pick(sim_db & ~sim_bf & ~sim_dh, d, e, is_rgba)
    e1 = _pick(sim_bf & ~sim_db & ~sim_hf, f, e, is_rgba)
    e2 = _pick(sim_dh & ~sim_db & ~sim_hf, d, e, is_rgba)
    e3 = _pick(sim_hf & ~sim_dh & ~sim_bf, f, e, is_rgba)

    height, width = img.shape[0], img.shape[1]
    if is_rgba:
        out = np.empty((height * 2, width * 2, img.shape[2]), dtype=np.uint8)
    else:
        out = np.empty((height * 2, width * 2), dtype=np.uint8)
    out[0::2, 0::2] = e0
    out[0::2, 1::2] = e1
    out[1::2, 0::2] = e2
    out[1::2, 1::2] = e3
    return out


def _upscale(
    img: npt.NDArray[np.uint8], is_rgba: bool, threshold: int, factor: int
) -> npt.NDArray[np.uint8]:
    """Upscale by ``factor`` (a power of two) via repeated similarity-Scale2x."""
    out = img
    scale = 1
    while scale < factor:
        out = _scale2x_similar(out, is_rgba, threshold)
        scale *= 2
    return out


# -- offset search --------------------------------------------------------


def _neighbour_ssd(samp: npt.NDArray[np.uint8]) -> int:
    """Sum of squared differences between adjacent interior samples."""
    a = samp.astype(np.int64)
    total = 0
    if a.shape[1] >= 2:
        dh = a[:, 1:] - a[:, :-1]
        total += int((dh * dh).sum())
    if a.shape[0] >= 2:
        dv = a[1:, :] - a[:-1, :]
        total += int((dv * dv).sum())
    return total


def _offset_search(big: npt.NDArray[np.uint8], factor: int) -> Tuple[int, int]:
    """Pick the downscale-lattice offset minimising neighbour SSD (ADR-0002 #3).

    Scans offsets ``(dx, dy)`` over ``0..factor-1`` (dx outer, dy inner, both
    ascending, from ``(0, 0)``) and keeps the first minimum, so ties resolve to
    the lexicographically smallest ``(dx, dy)``.
    """
    best: Tuple[int, int] = (0, 0)
    best_cost: Optional[int] = None
    for dx in range(factor):
        for dy in range(factor):
            cost = _neighbour_ssd(big[dy::factor, dx::factor])
            if best_cost is None or cost < best_cost:
                best_cost = cost
                best = (dx, dy)
    return best


# -- rotate + downscale + detail restore ---------------------------------


def _sample_grid(
    angle_degrees: float, pivot: Tuple[float, float], out_w: int, out_h: int
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Inverse-rotated source coordinates for every output pixel (about pivot)."""
    cx, cy = pivot
    rad = math.radians(angle_degrees)
    cos_t = math.cos(rad)
    sin_t = math.sin(rad)
    oy, ox = np.mgrid[0:out_h, 0:out_w]
    rel_x = ox - cx
    rel_y = oy - cy
    src_x = cx + cos_t * rel_x + sin_t * rel_y
    src_y = cy - sin_t * rel_x + cos_t * rel_y
    return src_x, src_y


def _rotate_downscale(
    big: npt.NDArray[np.uint8],
    angle_degrees: float,
    pivot: Tuple[float, float],
    factor: int,
    offset: Tuple[int, int],
    fill_arr: npt.NDArray[np.uint8],
    is_rgba: bool,
    out_w: int,
    out_h: int,
) -> npt.NDArray[np.uint8]:
    """Simultaneous nearest-neighbour rotate + downscale of the upscaled image."""
    src_x, src_y = _sample_grid(angle_degrees, pivot, out_w, out_h)
    off_x, off_y = offset
    big_x = np.floor(src_x * factor + 0.5).astype(np.int64) + off_x
    big_y = np.floor(src_y * factor + 0.5).astype(np.int64) + off_y
    big_h, big_w = big.shape[0], big.shape[1]
    valid = (big_x >= 0) & (big_x < big_w) & (big_y >= 0) & (big_y < big_h)
    if is_rgba:
        out = np.empty((out_h, out_w, big.shape[2]), dtype=np.uint8)
    else:
        out = np.empty((out_h, out_w), dtype=np.uint8)
    out[...] = fill_arr
    out[valid] = big[big_y[valid], big_x[valid]]
    return out


def _nn_rotate(
    img: npt.NDArray[np.uint8],
    angle_degrees: float,
    pivot: Tuple[float, float],
    fill_arr: npt.NDArray[np.uint8],
    is_rgba: bool,
) -> npt.NDArray[np.uint8]:
    """Plain nearest-neighbour rotate of the original image (detail reference)."""
    out_h, out_w = img.shape[0], img.shape[1]
    src_x, src_y = _sample_grid(angle_degrees, pivot, out_w, out_h)
    s_x = np.floor(src_x + 0.5).astype(np.int64)
    s_y = np.floor(src_y + 0.5).astype(np.int64)
    valid = (s_x >= 0) & (s_x < out_w) & (s_y >= 0) & (s_y < out_h)
    out = np.empty_like(img)
    out[...] = fill_arr
    out[valid] = img[s_y[valid], s_x[valid]]
    return out


def _equal(
    a: npt.NDArray[np.uint8], b: npt.NDArray[np.uint8], is_rgba: bool
) -> npt.NDArray[np.bool_]:
    """Per-pixel equality (all channels for RGBA)."""
    if is_rgba:
        result: npt.NDArray[np.bool_] = np.all(a == b, axis=-1)
        return result
    return a == b


def _detail_restore(
    res: npt.NDArray[np.uint8], src_nn: npt.NDArray[np.uint8], is_rgba: bool
) -> npt.NDArray[np.uint8]:
    """Restore 1-px features smeared away by the rotation (copy-only).

    Where a result pixel sits in a uniform neighbourhood (>=3 of its 4 edge-clamped
    neighbours mutually equal) yet differs from the plain NN-rotated source, the
    source value is copied back (research Topic 1 step 5).
    """
    neigh = _neighbours(res)
    uniform = np.zeros(res.shape[:2], dtype=bool)
    for i in range(4):
        count = np.zeros(res.shape[:2], dtype=np.int32)
        for j in range(4):
            count += _equal(neigh[i], neigh[j], is_rgba).astype(np.int32)
        uniform |= count >= 3
    restore = uniform & ~_equal(res, src_nn, is_rgba)
    out = res.copy()
    out[restore] = src_nn[restore]
    return out


# -- public API -----------------------------------------------------------


def rotsprite(
    buffer: PixelBuffer,
    angle_degrees: float,
    *,
    pivot: Optional[Tuple[float, float]] = None,
    fill: Optional[Union[RGBA, int]] = None,
) -> PixelBuffer:
    """Rotate ``buffer`` by ``angle_degrees`` with the RotSprite pipeline.

    Args:
        buffer: The source buffer (RGBA or indexed).
        angle_degrees: Rotation angle; ``0`` / ``360`` (any multiple) returns an
            equal copy.
        pivot: Rotation centre in buffer coordinates; defaults to the grid centre
            ``((W-1)/2, (H-1)/2)`` (ADR-0002 #2).
        fill: Value for uncovered (out-of-bounds) destination pixels; defaults to
            transparent RGBA ``(0, 0, 0, 0)`` / index ``0`` (ADR-0002 #4).

    Returns:
        A new ``W`` x ``H`` :class:`PixelBuffer`. Copy-only pipeline, so the output
        colour set is a subset of the input colours together with ``fill``
        (R2). Deterministic for a fixed ``(buffer, angle_degrees)``.
    """
    if angle_degrees % _FULL_TURN_DEGREES == 0:
        return buffer.copy()

    is_rgba = buffer.mode is ColorMode.RGBA
    width, height = buffer.width, buffer.height
    if pivot is None:
        pivot = ((width - 1) / 2.0, (height - 1) / 2.0)

    fill_value: PixelValue
    if fill is None:
        fill_value = TRANSPARENT if is_rgba else 0
    else:
        fill_value = fill
    # 0-d array for an index, shape-(4,) array for RGBA; both broadcast on
    # ``out[...] = fill_arr`` and satisfy the NDArray helper signatures.
    fill_arr: npt.NDArray[np.uint8] = np.asarray(fill_value, dtype=np.uint8)

    img = buffer.data.copy()
    factor = ROTSPRITE_UPSCALE_FACTOR
    threshold = ROTSPRITE_SIMILARITY_THRESHOLD

    big = _upscale(img, is_rgba, threshold, factor)
    offset = _offset_search(big, factor)
    res = _rotate_downscale(
        big, angle_degrees, pivot, factor, offset, fill_arr, is_rgba, width, height
    )
    src_nn = _nn_rotate(img, angle_degrees, pivot, fill_arr, is_rgba)
    res = _detail_restore(res, src_nn, is_rgba)

    out = PixelBuffer(width, height, buffer.mode)
    out.data[:, :] = res
    return out


def make_rotsprite_command(
    holder: BufferHolder,
    angle_degrees: float,
    mask: Optional["SelectionMask"] = None,
) -> history.Command:
    """Build a reversible RotSprite command over ``holder.buffer``.

    Whole-buffer rotation returns a :class:`history.FunctionCommand` that swaps
    ``holder.buffer`` (near-total rewrite). A selection variant rotates only the
    masked region and returns a :class:`history.PixelEdit` touching solely the
    masked pixels. Returned **unapplied** (push with ``execute=True``);
    ``apply then undo`` restores the buffer exactly.
    """
    buffer = holder.buffer
    if mask is not None:
        if mask.width != buffer.width or mask.height != buffer.height:
            raise ValueError("mask dimensions must match the buffer")
        box = mask.bounds()
        if box is None:
            return history.PixelEdit(buffer, [], label="rotate selection")
        x0, y0, x1, y1 = box
        sub = buffer.region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        rotated = rotsprite(sub, angle_degrees)
        mask_data = mask.data()
        changes: list[history.PixelChange] = []
        for gy in range(y0, y1 + 1):
            for gx in range(x0, x1 + 1):
                if not mask_data[gy, gx]:
                    continue
                new = rotated.get_pixel(gx - x0, gy - y0)
                old = buffer.get_pixel(gx, gy)
                if old != new:
                    changes.append((gx, gy, old, new))
        return history.PixelEdit(buffer, changes, label="rotate selection")

    rotated = rotsprite(buffer, angle_degrees)
    prior = buffer

    def _do() -> None:
        holder.buffer = rotated

    def _undo() -> None:
        holder.buffer = prior

    return history.FunctionCommand(_do, _undo, label="rotate")
