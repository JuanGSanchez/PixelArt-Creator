"""Tests for the floating-selection logic (REQ-P2-LOGIC-030..036, ADR-0009).

Slice F-A LOGIC: :class:`FloatMode`, :class:`FloatingSelection`,
:func:`lift_selection`, :func:`composite_preview`, :func:`copy_selection`,
:func:`commit_floating` in ``pixelart_creator.logic.selection`` (MOVE reuses
the shipped :func:`move_selection`).

One test per acceptance criterion (SC-L030..036 / FA-T1..T7), plus Hypothesis
invariants for the non-destructive (NFR-3) and reversibility (NFR-4) properties.
Zero Qt; deterministic and portable (NFR-1/-2).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from pixelart_creator.logic import history
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import (
    FloatingSelection,
    FloatMode,
    SelectionError,
    commit_floating,
    composite_preview,
    copy_selection,
    lasso_mask,
    lift_selection,
    move_selection,
    rect_mask,
    wand_mask,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def _block_buffer(w: int = 6, h: int = 6) -> PixelBuffer:
    """A ``w`` x ``h`` transparent RGBA buffer with a 2x2 RED block at (1,1)."""
    buf = PixelBuffer(w, h, fill=TRANSPARENT)
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        buf.set_pixel(x, y, RED)
    return buf


def _block_mask(w: int = 6, h: int = 6) -> "object":
    """The rectangle mask covering the (1,1)-(2,2) block of :func:`_block_buffer`."""
    return rect_mask(w, h, 1, 1, 2, 2)


# --- FA-T1 / SC-L030: floating-selection model / lift ---------------------


def test_sc_l030_1_lift_captures_colours_source_unchanged():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    # The source buffer is byte-for-byte unchanged (non-destructive lift).
    assert buf == before
    # The float holds the masked colours as an independent tight-bbox snapshot.
    assert floating.width == 2 and floating.height == 2
    preview = composite_preview(floating, buf)  # offset (0,0)
    assert preview == before  # identity float reproduces the source


def test_sc_l030_2_float_records_mode_and_zero_offset():
    floating = lift_selection(_block_buffer(), _block_mask(), FloatMode.COPY)
    assert floating.mode is FloatMode.COPY
    assert floating.offset == (0, 0)
    # Floated bbox equals the mask bbox at offset (0,0); origin bbox via mask().
    assert floating.bounds() == (1, 1, 2, 2)
    assert floating.mask().bounds() == (1, 1, 2, 2)


def test_sc_l030_3_empty_mask_raises_selection_error_not_sentinel():
    buf = _block_buffer()
    empty = rect_mask(6, 6, 10, 10, 20, 20)  # fully out of bounds -> empty
    assert empty.is_empty
    with pytest.raises(SelectionError):
        lift_selection(buf, empty, FloatMode.MOVE)


def test_sc_l030_4_dimension_mismatch_raises_selection_error():
    buf = _block_buffer(6, 6)
    with pytest.raises(SelectionError):
        lift_selection(buf, rect_mask(8, 8, 0, 0, 1, 1), FloatMode.MOVE)


def test_sc_l030_5_non_floatmode_raises_selection_error():
    buf = _block_buffer()
    with pytest.raises(SelectionError):
        lift_selection(buf, _block_mask(), "move")  # type: ignore[arg-type]


def test_floating_selection_set_offset_validates_ints():
    floating = lift_selection(_block_buffer(), _block_mask(), FloatMode.MOVE)
    floating.set_offset(3, -2)
    assert floating.offset == (3, -2)
    assert floating.bounds() == (1 + 3, 1 - 2, 2 + 3, 2 - 2)
    with pytest.raises(SelectionError):
        floating.set_offset(1.5, 0)  # type: ignore[arg-type]
    with pytest.raises(SelectionError):
        floating.set_offset(True, 0)  # type: ignore[arg-type]


def test_floating_selection_direct_construction_normalises_offset():
    # FloatingSelection is constructed by lift_selection in normal code; direct
    # construction coerces the offset to ints (defensive path).
    mask = _block_mask()
    colors = PixelBuffer(2, 2, fill=RED)
    fs = FloatingSelection(mask, FloatMode.COPY, colors, (1, 1, 2, 2), offset=(2, 3))
    assert fs.offset == (2, 3)
    assert fs.width == 2 and fs.height == 2
    # mask() returns an independent copy.
    assert fs.mask() == mask
    assert fs.mask() is not mask


# --- FA-T2 / SC-L031: non-destructive preview composite -------------------


def test_sc_l031_1_move_preview_vacates_origin_and_stamps_offset():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(2, 1)
    preview = composite_preview(floating, buf)
    # Origin mask pixels read vacated (transparent).
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert preview.get_pixel(x, y) == TRANSPARENT
    # Floated colours land at (x+2, y+1).
    for x, y in ((3, 2), (4, 2), (3, 3), (4, 3)):
        assert preview.get_pixel(x, y) == RED
    # The base buffer is NOT mutated.
    assert buf == before


def test_sc_l031_2_copy_preview_keeps_origin_and_adds_offset():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
    floating.set_offset(2, 1)
    preview = composite_preview(floating, buf)
    # Origin intact (COPY does not vacate).
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert preview.get_pixel(x, y) == RED
    # Floated copy also present at the offset.
    for x, y in ((3, 2), (4, 2), (3, 3), (4, 3)):
        assert preview.get_pixel(x, y) == RED
    assert buf == before


def test_sc_l031_3_preview_is_deterministic():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(1, 2)
    first = composite_preview(floating, buf)
    second = composite_preview(floating, buf)
    assert first == second


def test_sc_l031_4_off_canvas_offset_clips_preview():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    # Drag partly off the right/bottom edge: dest block (5,5)-(6,6); only (5,5)
    # is in bounds.
    floating.set_offset(4, 4)
    preview = composite_preview(floating, buf)
    assert preview.get_pixel(5, 5) == RED  # in-bounds corner stamped
    # Origin still vacated.
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert preview.get_pixel(x, y) == TRANSPARENT
    # Fully off-canvas: nothing stamped, origin still vacated (no stamp branch).
    floating.set_offset(10, 10)
    fully = composite_preview(floating, buf)
    assert not np.any(fully.data[:, :, :] != 0)  # all transparent


def test_sc_l031_region_return_is_region_sized_and_matches_full_slice():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(2, 1)
    full = composite_preview(floating, buf)
    # Region covering the destination block (scene (3,2), size 2x2).
    region = composite_preview(floating, buf, region=(3, 2, 2, 2))
    # Region-sized, NOT full-canvas.
    assert region.width == 2 and region.height == 2
    assert region.data.shape == (2, 2, 4)
    # Element (i, j) == scene pixel (3+j, 2+i) == the full-preview slice.
    assert np.array_equal(region.data, full.data[2:4, 3:5])
    # A region containing only the (vacated) origin equals the vacated slice.
    origin_region = composite_preview(floating, buf, region=(1, 1, 2, 2))
    assert np.array_equal(origin_region.data, full.data[1:3, 1:3])
    # A region touching neither origin nor float equals the untouched base slice.
    clear_region = composite_preview(floating, buf, region=(0, 4, 2, 2))
    assert np.array_equal(clear_region.data, buf.data[4:6, 0:2])


@pytest.mark.parametrize(
    "region",
    [
        (0, 0, 0, 2),  # w < 1
        (0, 0, 2, 0),  # h < 1
        (-1, 0, 2, 2),  # x < 0
        (0, -1, 2, 2),  # y < 0
        (5, 0, 2, 2),  # x + w > width
        (0, 5, 2, 2),  # y + h > height
    ],
)
def test_sc_l031_region_out_of_bounds_or_degenerate_raises(region):
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    with pytest.raises(SelectionError):
        composite_preview(floating, buf, region=region)


def test_sc_l031_region_non_int_component_raises():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    bad_region = (0, 0, 2.0, 2)
    with pytest.raises(SelectionError):
        composite_preview(floating, buf, region=bad_region)  # type: ignore[arg-type]


def test_sc_l031_preview_base_dimension_mismatch_raises():
    floating = lift_selection(_block_buffer(6, 6), _block_mask(6, 6), FloatMode.MOVE)
    other_base = PixelBuffer(8, 8, fill=TRANSPARENT)
    with pytest.raises(SelectionError):
        composite_preview(floating, other_base)


# --- FA-T3 / SC-L032: MOVE commit -----------------------------------------


def test_sc_l032_1_move_commit_vacates_origin_and_stamps():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(2, 1)
    cmd = commit_floating(buf, floating)
    cmd.execute()
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert buf.get_pixel(x, y) == TRANSPARENT
    for x, y in ((3, 2), (4, 2), (3, 3), (4, 3)):
        assert buf.get_pixel(x, y) == RED


def test_sc_l032_2_move_commit_reversible_apply_undo_identity():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(1, 2)
    cmd = commit_floating(buf, floating)
    cmd.execute()
    assert buf != before  # something moved
    cmd.undo()
    assert buf == before  # apply then undo = identity


def test_sc_l032_3_move_commit_is_exactly_one_pixeledit():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(2, 1)
    cmd = commit_floating(buf, floating)
    assert isinstance(cmd, history.PixelEdit)


def test_sc_l032_4_zero_offset_move_commit_is_noop():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)  # offset (0,0)
    cmd = commit_floating(buf, floating)
    assert len(cmd) == 0  # CL-F8: no spurious undo step
    cmd.execute()
    assert buf == before


def test_sc_l032_5_indexed_move_vacates_index_zero():
    buf = PixelBuffer(4, 4, ColorMode.INDEXED, fill=0)
    buf.set_pixel(0, 0, 7)
    buf.set_pixel(1, 0, 7)
    mask = rect_mask(4, 4, 0, 0, 1, 0)
    floating = lift_selection(buf, mask, FloatMode.MOVE)
    floating.set_offset(0, 2)
    commit_floating(buf, floating).execute()
    assert buf.get_pixel(0, 0) == 0  # vacated to index 0 (CL-F2)
    assert buf.get_pixel(1, 0) == 0
    assert buf.get_pixel(0, 2) == 7
    assert buf.get_pixel(1, 2) == 7


def test_sc_l032_move_commit_equals_move_selection_regression():
    # FA-7 invariant: commit_floating(MOVE) reuses move_selection verbatim, so
    # the two produce byte-identical results on equal buffers.
    buf1 = _block_buffer()
    buf2 = buf1.copy()
    mask = _block_mask()
    floating = lift_selection(buf1, mask, FloatMode.MOVE)
    floating.set_offset(2, 1)
    commit_floating(buf1, floating).execute()
    move_selection(buf2, mask, 2, 1).execute()
    assert buf1 == buf2


# --- FA-T4 / SC-L033: COPY commit -----------------------------------------


def test_sc_l033_1_copy_commit_stamps_dest_keeps_origin():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
    floating.set_offset(2, 1)
    commit_floating(buf, floating).execute()
    # Origin intact.
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert buf.get_pixel(x, y) == RED
    # Copy stamped at the destination.
    for x, y in ((3, 2), (4, 2), (3, 3), (4, 3)):
        assert buf.get_pixel(x, y) == RED


def test_sc_l033_2_copy_commit_reversible():
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
    floating.set_offset(3, 1)
    cmd = commit_floating(buf, floating)
    cmd.execute()
    assert buf != before
    cmd.undo()
    assert buf == before


def test_sc_l033_3_copy_commit_is_exactly_one_command():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
    floating.set_offset(2, 1)
    cmd = commit_floating(buf, floating)
    assert isinstance(cmd, history.PixelEdit)


def test_sc_l033_4_copy_keeps_origin_in_indexed_mode():
    buf = PixelBuffer(4, 4, ColorMode.INDEXED, fill=0)
    buf.set_pixel(0, 0, 7)
    mask = rect_mask(4, 4, 0, 0, 0, 0)
    floating = lift_selection(buf, mask, FloatMode.COPY)
    floating.set_offset(2, 0)
    commit_floating(buf, floating).execute()
    assert buf.get_pixel(0, 0) == 7  # origin kept (CL-F7)
    assert buf.get_pixel(2, 0) == 7  # copy stamped


def test_sc_l033_copy_introduces_no_new_colours():
    # NFR-5: the committed output colour set is a subset of the source colours.
    buf = _block_buffer()
    source_colours = {
        buf.get_pixel(x, y) for y in range(buf.height) for x in range(buf.width)
    }
    floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
    floating.set_offset(2, 1)
    commit_floating(buf, floating).execute()
    after_colours = {
        buf.get_pixel(x, y) for y in range(buf.height) for x in range(buf.width)
    }
    assert after_colours <= source_colours


def test_copy_selection_zero_offset_is_noop():
    buf = _block_buffer()
    before = buf.copy()
    cmd = copy_selection(buf, _block_mask(), 0, 0)
    assert len(cmd) == 0
    cmd.execute()
    assert buf == before


def test_copy_selection_validates_arguments():
    buf = _block_buffer()
    with pytest.raises(SelectionError):
        copy_selection(buf, rect_mask(8, 8, 0, 0, 1, 1), 1, 1)  # dim mismatch
    with pytest.raises(SelectionError):
        copy_selection(buf, _block_mask(), 1.5, 0)  # type: ignore[arg-type]
    with pytest.raises(SelectionError):
        copy_selection(buf, _block_mask(), True, 0)  # type: ignore[arg-type]


# --- FA-T5 / SC-L034: cancel is a non-destructive no-op -------------------


def test_sc_l034_1_cancel_discards_float_buffer_unchanged():
    # There is no logic-side cancel function: the non-destructive invariant means
    # lifting and then discarding the float (never committing) leaves the buffer
    # byte-for-byte unchanged and produces NO command.
    buf = _block_buffer()
    before = buf.copy()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(3, 2)
    _ = composite_preview(floating, buf)  # dragged around; buffer untouched
    # Discard the float (do nothing else). No command was ever produced.
    assert buf == before


# --- FA-T6 / SC-L035: off-canvas clipping at commit -----------------------


def test_sc_l035_1_off_canvas_pixels_discarded_on_commit_not_wrapped():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(4, 4)  # dest (5,5)-(6,6): only (5,5) in bounds
    commit_floating(buf, floating).execute()
    assert buf.get_pixel(5, 5) == RED
    # Off-canvas destinations dropped, never wrapped to (0,0)/(0,*)/(*, 0).
    assert buf.get_pixel(0, 0) == TRANSPARENT
    # Origin fully vacated.
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert buf.get_pixel(x, y) == TRANSPARENT


def test_sc_l035_2_move_fully_off_canvas_still_vacates_whole_origin():
    buf = _block_buffer()
    floating = lift_selection(buf, _block_mask(), FloatMode.MOVE)
    floating.set_offset(20, 20)  # entirely off-canvas
    commit_floating(buf, floating).execute()
    # Whole in-bounds origin vacated; no stamp anywhere (would-be dest off-canvas).
    assert not np.any(buf.data[:, :, :] != 0)


def test_sc_l035_3_off_canvas_clipping_is_deterministic():
    def _commit_result() -> PixelBuffer:
        buf = _block_buffer()
        floating = lift_selection(buf, _block_mask(), FloatMode.COPY)
        floating.set_offset(5, 3)
        commit_floating(buf, floating).execute()
        return buf

    assert _commit_result() == _commit_result()


# --- FA-T7 / SC-L036: single-buffer / mask-source contract ----------------


def test_sc_l036_1_lift_from_rect_lasso_wand_masks():
    # The float lifts from any shipped mask builder (CL-F4).
    buf = _block_buffer()
    rect = rect_mask(6, 6, 1, 1, 2, 2)
    lasso = lasso_mask(6, 6, [(1, 1), (2, 1), (2, 2), (1, 2)])
    wand = wand_mask(buf, 1, 1)  # contiguous RED block
    for mask in (rect, lasso, wand):
        assert not mask.is_empty
        floating = lift_selection(buf, mask, FloatMode.MOVE)
        assert floating.mask() == mask


def test_sc_l036_2_dimension_mismatch_raises_selection_error():
    buf = _block_buffer(6, 6)
    with pytest.raises(SelectionError):
        lift_selection(buf, rect_mask(4, 4, 0, 0, 1, 1), FloatMode.COPY)


# --- Hypothesis invariants (NFR-2 / NFR-3 / NFR-4) ------------------------

_W = _H = 5
_flat = st.lists(st.integers(0, 255), min_size=_W * _H * 4, max_size=_W * _H * 4)
_corner = st.integers(min_value=0, max_value=_W - 1)
_offset = st.integers(min_value=-(_W + 1), max_value=_W + 1)
_mode = st.sampled_from([FloatMode.MOVE, FloatMode.COPY])


def _buffer_from_flat(flat: list[int]) -> PixelBuffer:
    arr = np.array(flat, dtype=np.uint8).reshape((_H, _W, 4))
    buf = PixelBuffer(_W, _H)
    buf.data[:, :] = arr
    return buf


@given(
    flat=_flat,
    x0=_corner,
    y0=_corner,
    x1=_corner,
    y1=_corner,
    dx=_offset,
    dy=_offset,
    mode=_mode,
)
def test_property_lift_and_preview_are_non_destructive(
    flat, x0, y0, x1, y1, dx, dy, mode
):
    buf = _buffer_from_flat(flat)
    before = buf.copy()
    mask = rect_mask(_W, _H, x0, y0, x1, y1)  # in-bounds corners -> non-empty
    floating = lift_selection(buf, mask, mode)
    assert buf == before  # lift never mutates the source (NFR-3)
    floating.set_offset(dx, dy)
    _ = composite_preview(floating, buf)
    assert buf == before  # preview never mutates the base (NFR-3)


@given(
    flat=_flat,
    x0=_corner,
    y0=_corner,
    x1=_corner,
    y1=_corner,
    dx=_offset,
    dy=_offset,
    mode=_mode,
)
def test_property_commit_apply_undo_is_identity(flat, x0, y0, x1, y1, dx, dy, mode):
    buf = _buffer_from_flat(flat)
    mask = rect_mask(_W, _H, x0, y0, x1, y1)
    floating = lift_selection(buf, mask, mode)
    floating.set_offset(dx, dy)
    cmd = commit_floating(buf, floating)
    before = buf.copy()
    cmd.execute()
    cmd.undo()
    assert buf == before  # apply then undo = identity (NFR-4)


@st.composite
def _regions(draw):
    rx = draw(st.integers(0, _W - 1))
    ry = draw(st.integers(0, _H - 1))
    rw = draw(st.integers(1, _W - rx))
    rh = draw(st.integers(1, _H - ry))
    return (rx, ry, rw, rh)


@given(
    flat=_flat,
    x0=_corner,
    y0=_corner,
    x1=_corner,
    y1=_corner,
    dx=_offset,
    dy=_offset,
    mode=_mode,
    region=_regions(),
)
def test_property_region_preview_equals_full_slice(
    flat, x0, y0, x1, y1, dx, dy, mode, region
):
    buf = _buffer_from_flat(flat)
    mask = rect_mask(_W, _H, x0, y0, x1, y1)
    floating = lift_selection(buf, mask, mode)
    floating.set_offset(dx, dy)
    rx, ry, rw, rh = region
    assume(rx + rw <= _W and ry + rh <= _H)
    full = composite_preview(floating, buf)
    part = composite_preview(floating, buf, region=region)
    assert part.data.shape == (rh, rw, 4)
    assert np.array_equal(part.data, full.data[ry : ry + rh, rx : rx + rw])
