"""Tests for pixelart_creator.logic.transform (REQ-P2-LOGIC-007..010).

One test per SC-L007..010 behaviour, plus Hypothesis invariants:
flip-flip = identity, rotate90 x4 = identity, no-new-colours, reversibility.
Zero Qt; deterministic and portable.
"""

from __future__ import annotations

import tracemalloc

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.logic.transform import (
    TransformError,
    flip_horizontal,
    flip_vertical,
    make_transform_command,
    rotate_90_ccw,
    rotate_90_cw,
    scale_nearest,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)


class _Holder:
    """Minimal BufferHolder for make_transform_command tests."""

    def __init__(self, buffer: PixelBuffer) -> None:
        self.buffer = buffer


def _distinct_buffer(w: int = 3, h: int = 2) -> PixelBuffer:
    """A buffer where every pixel has a unique colour (so permutations show)."""
    buf = PixelBuffer(w, h)
    for y in range(h):
        for x in range(w):
            buf.set_pixel(x, y, (x * 10, y * 10, 50, 255))
    return buf


def _colour_set(buf: PixelBuffer):
    if buf.mode is ColorMode.RGBA:
        return {tuple(px) for px in buf.data.reshape(-1, 4).tolist()}
    return set(buf.data.reshape(-1).tolist())


# --- SC-L007: flip --------------------------------------------------------


def test_sc_l007_1_flip_horizontal_mirrors_columns():
    buf = _distinct_buffer(3, 2)
    out = flip_horizontal(buf)
    assert out.get_pixel(0, 0) == buf.get_pixel(2, 0)
    assert out.get_pixel(2, 1) == buf.get_pixel(0, 1)


def test_sc_l007_1_flip_vertical_mirrors_rows():
    buf = _distinct_buffer(3, 2)
    out = flip_vertical(buf)
    assert out.get_pixel(0, 0) == buf.get_pixel(0, 1)
    assert out.get_pixel(2, 1) == buf.get_pixel(2, 0)


def test_sc_l007_2_flip_introduces_no_new_colours():
    buf = _distinct_buffer(4, 4)
    assert _colour_set(flip_horizontal(buf)) == _colour_set(buf)
    assert _colour_set(flip_vertical(buf)) == _colour_set(buf)


def test_sc_l007_3_flipping_twice_restores_the_buffer():
    buf = _distinct_buffer(5, 3)
    assert flip_horizontal(flip_horizontal(buf)) == buf
    assert flip_vertical(flip_vertical(buf)) == buf


# --- SC-L008: rotate 90 ---------------------------------------------------


def test_sc_l008_1_rotate_cw_on_known_2x3_buffer():
    # 2 wide x 3 tall, labelled by colour; CW should map top-left to top-right.
    buf = _distinct_buffer(2, 3)
    out = rotate_90_cw(buf)
    assert out.width == 3 and out.height == 2
    # top-left of source (0,0) rotates to the top-right column of the result.
    assert out.get_pixel(out.width - 1, 0) == buf.get_pixel(0, 0)


def test_sc_l008_2_non_square_swaps_width_and_height():
    buf = _distinct_buffer(5, 2)
    assert (rotate_90_cw(buf).width, rotate_90_cw(buf).height) == (2, 5)
    assert (rotate_90_ccw(buf).width, rotate_90_ccw(buf).height) == (2, 5)


def test_sc_l008_3_four_cw_and_cw_then_ccw_are_identity():
    buf = _distinct_buffer(4, 3)
    r = rotate_90_cw(rotate_90_cw(rotate_90_cw(rotate_90_cw(buf))))
    assert r == buf
    assert rotate_90_ccw(rotate_90_cw(buf)) == buf


def test_sc_l008_4_rotate_introduces_no_new_colours():
    buf = _distinct_buffer(4, 3)
    assert _colour_set(rotate_90_cw(buf)) == _colour_set(buf)
    assert _colour_set(rotate_90_ccw(buf)) == _colour_set(buf)


# --- SC-L009: scale nearest-neighbour -------------------------------------


def test_sc_l009_1_scale_2x_doubles_and_maps_each_pixel_to_2x2_block():
    buf = _distinct_buffer(2, 2)
    out = scale_nearest(buf, 4, 4)
    assert out.width == 4 and out.height == 4
    for y in range(2):
        for x in range(2):
            src = buf.get_pixel(x, y)
            for dy in (0, 1):
                for dx in (0, 1):
                    assert out.get_pixel(x * 2 + dx, y * 2 + dy) == src


def test_sc_l009_2_scale_introduces_no_new_colours():
    buf = _distinct_buffer(3, 3)
    up = scale_nearest(buf, 7, 5)
    assert _colour_set(up).issubset(_colour_set(buf))


def test_sc_l009_3_non_integer_factor_is_deterministic():
    buf = _distinct_buffer(4, 4)
    a = scale_nearest(buf, 7, 3)
    b = scale_nearest(buf, 7, 3)
    assert a == b
    assert _colour_set(a).issubset(_colour_set(buf))


def test_sc_l009_4_non_positive_target_raises():
    buf = _distinct_buffer(4, 4)
    with pytest.raises(TransformError):
        scale_nearest(buf, 0, 4)
    with pytest.raises(TransformError):
        scale_nearest(buf, 4, -1)
    with pytest.raises(TransformError):
        scale_nearest(buf, 4.0, 4)  # type: ignore[arg-type]
    with pytest.raises(TransformError):
        scale_nearest(buf, True, 4)  # type: ignore[arg-type]


def test_sc_l009_5_scale_down_stays_within_source_palette():
    buf = _distinct_buffer(8, 8)
    down = scale_nearest(buf, 3, 3)
    assert _colour_set(down).issubset(_colour_set(buf))


# --- REQ-CSD-LOGIC-001/002: the scale target is bounded by resulting
# dimension, not by the old ratio-factor guard (canvas-scale-defects
# spec.md). The old test_scale_factor_out_of_bounds_raises
# asserted the DELETED SCALE_MIN_FACTOR/SCALE_MAX_FACTOR ratio guard: both
# of its bodies (200x1 -> 1x1, factor 0.005; 1x1 -> 65x1, factor 65.0) are
# now within [1, MAX_CANVAS_WIDTH/HEIGHT] and must NOT raise. It is
# replaced below by the per-scenario class table this module specifies.


class TestScDimensionClamp:
    """SC-CSD-L001-*: the scale target is bounded by resulting dimension.

    DEFECT (L001-1..4): fails against the unfixed code, which still enforces
    the deleted SCALE_MIN_FACTOR/SCALE_MAX_FACTOR ratio guard.
    GUARD (L001-5): passes today (the positive-int check predates this
    batch) and must keep passing -- no pre-fix failure is manufactured for it.
    """

    def test_sc_l001_1_ceiling_reachable_from_default_document(self):
        # DEFECT: implied factors 120.0 x / 67.5 y both exceed the old 64.0
        # ratio cap; the fixed code accepts any in-bounds resulting dimension.
        buf = PixelBuffer(64, 64)
        out = scale_nearest(buf, 7680, 4320)
        assert out.width == 7680 and out.height == 4320

    def test_sc_l001_2_one_pixel_past_ceiling_names_the_limit(self):
        # DEFECT: pre-fix this also raised, but with the ratio-factor
        # message, not one naming the 7680 dimension ceiling.
        buf = PixelBuffer(64, 64)
        with pytest.raises(TransformError) as excinfo:
            scale_nearest(buf, 7681, 4320)
        assert "7680" in str(excinfo.value)

    def test_sc_l001_3_large_downscale_is_reachable(self):
        # DEFECT: implied factor 0.00833 is below the old SCALE_MIN_FACTOR
        # of 0.01 and was refused pre-fix.
        buf = PixelBuffer(7680, 4320)
        out = scale_nearest(buf, 64, 36)
        assert out.width == 64 and out.height == 36

    def test_sc_l001_4_downscale_to_single_pixel_is_reachable(self):
        # DEFECT: pre-fix the implied factor is far below SCALE_MIN_FACTOR.
        buf = PixelBuffer(7680, 4320)
        out = scale_nearest(buf, 1, 1)
        assert out.width == 1 and out.height == 1

    def test_sc_l001_5_zero_target_still_refused(self):
        # GUARD: the positive-int check already passes today; do not prove
        # a prior failure for this row.
        buf = PixelBuffer(64, 64)
        with pytest.raises(TransformError):
            scale_nearest(buf, 0, 64)


def test_sc_l002_1_oversized_target_raises_before_allocation():
    # DEFECT: under the deleted ratio guard the implied factor is exactly
    # 64.0 (32768 / 512), which passed, so a 4 GiB array was attempted. The
    # fixed clamp on resulting dimension must refuse BEFORE any array of
    # that size is allocated -- proven here by a tracemalloc peak far below
    # the would-be 4 GiB allocation, and by the absence of MemoryError.
    buf = PixelBuffer(512, 512)
    assert buf.data.nbytes == 1_048_576
    tracemalloc.start()
    try:
        with pytest.raises(TransformError) as excinfo:
            scale_nearest(buf, 32768, 32768)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    message = str(excinfo.value)
    assert str(MAX_CANVAS_WIDTH) in message
    assert peak < 4_194_304
    assert not isinstance(excinfo.value, MemoryError)


# --- SC-L010: transform target buffer-or-selection ------------------------


def test_sc_l010_1_selection_transform_changes_only_masked_pixels():
    buf = _distinct_buffer(4, 4)
    before = buf.copy()
    # select the 2x2 top-left region and flip it horizontally in place.
    mask = rect_mask(4, 4, 0, 0, 1, 1)
    holder = _Holder(buf)
    cmd = make_transform_command(holder, flip_horizontal, mask, target=None)
    cmd.execute()
    # pixels outside the selection are untouched.
    for y in range(4):
        for x in range(4):
            if not (x <= 1 and y <= 1):
                assert buf.get_pixel(x, y) == before.get_pixel(x, y)
    # inside: columns swapped within the 2x2 box.
    assert buf.get_pixel(0, 0) == before.get_pixel(1, 0)


def test_sc_l010_2_whole_buffer_transform_changes_every_pixel():
    buf = _distinct_buffer(3, 3)
    before = buf.copy()
    holder = _Holder(buf)
    make_transform_command(holder, flip_horizontal, target=None).execute()
    assert holder.buffer == flip_horizontal(before)


def test_sc_l010_2_dim_changing_whole_buffer_uses_function_command():
    buf = _distinct_buffer(5, 2)  # non-square -> rotate swaps dims
    holder = _Holder(buf)
    cmd = make_transform_command(holder, rotate_90_cw, target=None)
    cmd.execute()
    assert holder.buffer.width == 2 and holder.buffer.height == 5


def test_sc_l010_3_selection_transform_then_undo_restores_buffer():
    buf = _distinct_buffer(4, 4)
    before = buf.copy()
    mask = rect_mask(4, 4, 1, 1, 3, 3)
    holder = _Holder(buf)
    cmd = make_transform_command(holder, rotate_90_cw, mask, target=None)
    cmd.execute()
    cmd.undo()
    assert buf == before


def test_dim_changing_command_undo_restores_buffer():
    buf = _distinct_buffer(5, 2)
    before = buf.copy()
    holder = _Holder(buf)
    cmd = make_transform_command(holder, rotate_90_cw, target=None)
    cmd.execute()
    cmd.undo()
    assert holder.buffer == before


def test_masked_transform_with_empty_mask_is_noop():
    buf = _distinct_buffer(4, 4)
    before = buf.copy()
    empty = rect_mask(4, 4, 10, 10, 20, 20)  # empty
    holder = _Holder(buf)
    make_transform_command(holder, flip_horizontal, empty, target=None).execute()
    assert buf == before


def test_masked_transform_dim_mismatch_raises():
    buf = _distinct_buffer(4, 4)
    holder = _Holder(buf)
    with pytest.raises(TransformError):
        make_transform_command(
            holder, flip_horizontal, rect_mask(8, 8, 0, 0, 1, 1), target=None
        )


def test_masked_transform_uncovered_pixel_takes_fill():
    # Rotate a wide 3x1 selection region: the rotated result is 1x3, so the
    # extra selected columns have no source and take the transparent fill.
    buf = PixelBuffer(4, 4)
    for x in range(3):
        buf.set_pixel(x, 0, (10 * (x + 1), 0, 0, 255))
    mask = rect_mask(4, 4, 0, 0, 2, 0)  # a 3-wide, 1-tall selection
    holder = _Holder(buf)
    cmd = make_transform_command(holder, rotate_90_cw, mask, target=None)
    cmd.execute()
    # some selected cells become transparent fill (rotated region is taller).
    fill_seen = any(buf.get_pixel(x, 0) == (0, 0, 0, 0) for x in range(3))
    assert fill_seen
    cmd.undo()
    for x in range(3):
        assert buf.get_pixel(x, 0) == (10 * (x + 1), 0, 0, 255)


def test_indexed_flip_diff_path():
    buf = PixelBuffer(3, 1, ColorMode.INDEXED)
    buf.set_pixel(0, 0, 1)
    buf.set_pixel(2, 0, 3)
    before = buf.copy()
    holder = _Holder(buf)
    cmd = make_transform_command(holder, flip_horizontal, target=None)
    cmd.execute()
    assert buf.get_pixel(0, 0) == 3 and buf.get_pixel(2, 0) == 1
    cmd.undo()
    assert buf == before


# --- Hypothesis invariants ------------------------------------------------

_dim = st.integers(min_value=1, max_value=6)
_chan = st.integers(min_value=0, max_value=255)


def _random_buffer(draw, w, h):
    buf = PixelBuffer(w, h)
    for y in range(h):
        for x in range(w):
            buf.set_pixel(x, y, (draw(_chan), draw(_chan), draw(_chan), draw(_chan)))
    return buf


@settings(max_examples=60, derandomize=True)
@given(data=st.data(), w=_dim, h=_dim)
def test_property_flip_flip_identity(data, w, h):
    buf = _random_buffer(data.draw, w, h)
    assert flip_horizontal(flip_horizontal(buf)) == buf
    assert flip_vertical(flip_vertical(buf)) == buf


@settings(max_examples=60, derandomize=True)
@given(data=st.data(), w=_dim, h=_dim)
def test_property_rotate90_four_times_identity(data, w, h):
    buf = _random_buffer(data.draw, w, h)
    out = buf
    for _ in range(4):
        out = rotate_90_cw(out)
    assert out == buf


@settings(max_examples=60, derandomize=True)
@given(data=st.data(), w=_dim, h=_dim, nw=_dim, nh=_dim)
def test_property_scale_no_new_colours(data, w, h, nw, nh):
    buf = _random_buffer(data.draw, w, h)
    out = scale_nearest(buf, nw, nh)
    out_cols = {tuple(px) for px in out.data.reshape(-1, 4).tolist()}
    src_cols = {tuple(px) for px in buf.data.reshape(-1, 4).tolist()}
    assert out_cols.issubset(src_cols)


@settings(max_examples=40, derandomize=True)
@given(data=st.data(), w=_dim, h=_dim)
def test_property_whole_buffer_transform_reversible(data, w, h):
    buf = _random_buffer(data.draw, w, h)
    before = buf.copy()
    holder = _Holder(buf)
    for tfm in (flip_horizontal, flip_vertical, rotate_90_cw):
        holder.buffer = before.copy()
        snapshot = holder.buffer.copy()
        cmd = make_transform_command(holder, tfm, target=None)
        cmd.execute()
        cmd.undo()
        assert holder.buffer == snapshot
