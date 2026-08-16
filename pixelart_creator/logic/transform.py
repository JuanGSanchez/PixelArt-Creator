"""Buffer transforms: flip / rotate-90 / scale-NN (zero Qt, S11).

Pure transforms return a new :class:`PixelBuffer`; flip and rotate-90 are pure
pixel permutations (no new colours), scale uses nearest-neighbour only (output
colour set is a subset of the input, R2). Each is available whole-buffer or
selection-aware via :func:`make_transform_command`, which returns a reversible
``history`` command (``FunctionCommand`` for dimension-changing whole-buffer
transforms, ``PixelEdit`` otherwise). REQ-P2-LOGIC-007..010.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Protocol

import numpy as np

from pixelart_creator.logic import history
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.constants import SCALE_MAX_FACTOR, SCALE_MIN_FACTOR
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue
from pixelart_creator.logic.selection import SelectionMask


class TransformError(ValueError):
    """Raised on an invalid transform target or scale factor."""


class BufferHolder(Protocol):
    """A mutable holder of a :class:`PixelBuffer` (e.g. a document ``Layer``).

    ``make_transform_command`` swaps this attribute for dimension-changing
    transforms; the Qt undo bridge (``ui/commands.py``) supplies the concrete
    holder.
    """

    buffer: PixelBuffer


def _from_array(mode: ColorMode, arr: np.ndarray) -> PixelBuffer:
    """Wrap a NumPy array back into a :class:`PixelBuffer` of ``mode``.

    The first two axes are ``(height, width)`` in both RGBA ``(H, W, 4)`` and
    indexed ``(H, W)`` layouts.
    """
    height, width = int(arr.shape[0]), int(arr.shape[1])
    out = PixelBuffer(width, height, mode)
    out.data[:, :] = np.ascontiguousarray(arr)
    return out


# -- pure transforms (whole buffer) --------------------------------------


def flip_horizontal(buffer: PixelBuffer) -> PixelBuffer:
    """Mirror the buffer left-to-right (columns reversed). No new colours."""
    return _from_array(buffer.mode, np.fliplr(buffer.data))


def flip_vertical(buffer: PixelBuffer) -> PixelBuffer:
    """Mirror the buffer top-to-bottom (rows reversed). No new colours."""
    return _from_array(buffer.mode, np.flipud(buffer.data))


def rotate_90_cw(buffer: PixelBuffer) -> PixelBuffer:
    """Rotate the buffer 90 degrees clockwise (W/H swap, CL-8). No new colours."""
    return _from_array(buffer.mode, np.rot90(buffer.data, k=-1))


def rotate_90_ccw(buffer: PixelBuffer) -> PixelBuffer:
    """Rotate 90 degrees counter-clockwise (W/H swap, CL-8). No new colours."""
    return _from_array(buffer.mode, np.rot90(buffer.data, k=1))


def scale_nearest(buffer: PixelBuffer, new_width: int, new_height: int) -> PixelBuffer:
    """Resample to ``new_width`` x ``new_height`` with nearest-neighbour only.

    No colour absent from the source is ever produced (R2). Target coordinates
    map back to a source pixel by floor.

    Raises:
        TransformError: If a target dimension is a non-positive int, or the
            implied scale factor falls outside ``SCALE_MIN_FACTOR`` /
            ``SCALE_MAX_FACTOR``.
    """
    for name, value in (("new_width", new_width), ("new_height", new_height)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TransformError(f"{name} must be an int, got {value!r}")
        if value <= 0:
            raise TransformError(f"{name} must be positive, got {value}")
    fx = new_width / buffer.width
    fy = new_height / buffer.height
    for axis, factor in (("x", fx), ("y", fy)):
        if factor < SCALE_MIN_FACTOR or factor > SCALE_MAX_FACTOR:
            raise TransformError(
                f"scale factor {factor:g} on {axis} outside "
                f"[{SCALE_MIN_FACTOR}, {SCALE_MAX_FACTOR}]"
            )
    src_xs = (np.arange(new_width) * buffer.width) // new_width
    src_ys = (np.arange(new_height) * buffer.height) // new_height
    sampled = buffer.data[src_ys.reshape(-1, 1), src_xs.reshape(1, -1)]
    return _from_array(buffer.mode, sampled)


# -- reversible builders --------------------------------------------------


def _diff_changes(before: PixelBuffer, after: PixelBuffer) -> List[history.PixelChange]:
    """Per-pixel ``(x, y, old, new)`` diff of two same-dimension buffers."""
    if before.mode is ColorMode.RGBA:
        differ = np.any(before.data != after.data, axis=-1)
    else:
        differ = before.data != after.data
    changes: List[history.PixelChange] = []
    ys, xs = np.nonzero(differ)
    for x, y in zip(xs.tolist(), ys.tolist()):
        changes.append((x, y, before.get_pixel(x, y), after.get_pixel(x, y)))
    return changes


def _masked_transform_changes(
    buffer: PixelBuffer,
    transform: Callable[[PixelBuffer], PixelBuffer],
    mask: SelectionMask,
) -> List[history.PixelChange]:
    """Compute the changes for a transform constrained to a selection (masked only).

    The transform is applied to the mask's bounding-box sub-buffer; the result is
    written back only at originally-selected coordinates (unmasked pixels are
    untouched, SC-L010-1). Dimension-changing transforms are anchored at the
    bounding-box top-left; uncovered masked pixels take the vacated fill.
    """
    if mask.width != buffer.width or mask.height != buffer.height:
        raise TransformError("mask dimensions must match the buffer")
    box = mask.bounds()
    if box is None:
        return []
    x0, y0, x1, y1 = box
    sub = buffer.region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
    result = transform(sub)
    fill: PixelValue = TRANSPARENT if buffer.mode is ColorMode.RGBA else 0

    changes: List[history.PixelChange] = []
    mask_data = mask.data()
    for gy in range(y0, y1 + 1):
        for gx in range(x0, x1 + 1):
            if not mask_data[gy, gx]:
                continue
            lx, ly = gx - x0, gy - y0
            if result.in_bounds(lx, ly):
                new = result.get_pixel(lx, ly)
            else:
                new = fill
            old = buffer.get_pixel(gx, gy)
            if old != new:
                changes.append((gx, gy, old, new))
    return changes


def make_transform_command(
    holder: BufferHolder,
    transform: Callable[[PixelBuffer], PixelBuffer],
    mask: Optional[SelectionMask] = None,
) -> history.Command:
    """Build a reversible command applying ``transform`` to ``holder.buffer``.

    * With a ``mask``: the transform touches only masked pixels (re-stamped);
      returns a :class:`history.PixelEdit`.
    * Whole-buffer, dimension-changing (rotate-90 of a non-square buffer, scale):
      returns a :class:`history.FunctionCommand` that swaps ``holder.buffer``.
    * Whole-buffer, same-dimension (flip, square rotate-90): returns a
      :class:`history.PixelEdit` of the changed pixels.

    The command is returned **unapplied** (push it with ``execute=True``);
    ``apply then undo`` restores the buffer exactly (SC-L010-3).
    """
    buffer = holder.buffer
    if mask is not None:
        changes = _masked_transform_changes(buffer, transform, mask)
        return history.PixelEdit(buffer, changes, label="transform selection")

    result = transform(buffer)
    if result.width != buffer.width or result.height != buffer.height:
        prior = buffer

        def _do() -> None:
            holder.buffer = result

        def _undo() -> None:
            holder.buffer = prior

        return history.FunctionCommand(_do, _undo, label="transform")

    return history.PixelEdit(buffer, _diff_changes(buffer, result), label="transform")
