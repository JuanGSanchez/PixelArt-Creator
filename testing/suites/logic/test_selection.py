"""Tests for pixelart_creator.logic.selection (REQ-P2-LOGIC-001..006, 010).

One test per SC-L001..006 behaviour, plus Hypothesis invariants (mask bounds
within canvas; invert-invert = identity). Zero Qt; deterministic and portable.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic import selection
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import (
    SelectionError,
    SelectionMask,
    apply_masked,
    extract_masked,
    lasso_mask,
    move_selection,
    rect_mask,
    wand_mask,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def _buf(w: int = 4, h: int = 4, fill=TRANSPARENT) -> PixelBuffer:
    return PixelBuffer(w, h, fill=fill)


# --- SC-L001: mask model --------------------------------------------------


def test_sc_l001_1_empty_mask_reports_empty_and_no_bounds():
    mask = SelectionMask(4, 4)
    assert mask.is_empty is True
    assert mask.bounds() is None
    assert mask.count() == 0
    assert mask.is_selected(1, 1) is False
    # out-of-bounds coordinates report False rather than raising.
    assert mask.is_selected(-1, 0) is False
    assert mask.is_selected(0, 99) is False


def test_sc_l001_2_mask_reports_selected_pixels_and_tight_bounds():
    mask = rect_mask(4, 4, 1, 1, 1, 1).combine(
        rect_mask(4, 4, 2, 3, 2, 3), selection.COMBINE_ADD
    )
    assert mask.is_selected(1, 1) is True
    assert mask.is_selected(2, 3) is True
    assert mask.is_selected(0, 0) is False
    assert mask.bounds() == (1, 1, 2, 3)


def test_sc_l001_3_copy_is_equal_but_independent():
    original = rect_mask(4, 4, 0, 0, 1, 1)
    clone = original.copy()
    assert clone == original
    # mutate the clone via a combine that returns a new mask; original stays.
    clone2 = clone.combine(rect_mask(4, 4, 3, 3, 3, 3), selection.COMBINE_ADD)
    assert clone2 != original
    assert original == rect_mask(4, 4, 0, 0, 1, 1)


def test_sc_l001_4_bad_dimensions_raise_selection_error():
    with pytest.raises(SelectionError):
        SelectionMask(0, 4)
    with pytest.raises(SelectionError):
        SelectionMask(4, -1)
    with pytest.raises(SelectionError):
        SelectionMask(4, 4.0)  # type: ignore[arg-type]
    with pytest.raises(SelectionError):
        SelectionMask(True, 4)  # type: ignore[arg-type]


def test_mask_dunders_and_data():
    mask = rect_mask(4, 4, 0, 0, 1, 1)
    assert mask.width == 4 and mask.height == 4
    assert (mask == 5) is False  # __eq__ returns NotImplemented -> False
    assert mask.__hash__() is None  # mutable value type; unhashable
    assert "SelectionMask(4x4" in repr(mask)
    data = mask.data()
    data[0, 0] = False  # a copy — must not affect the mask
    assert mask.is_selected(0, 0) is True


# --- SC-L002: rectangle selection ----------------------------------------


def test_sc_l002_1_rectangle_marks_only_the_rectangle():
    mask = rect_mask(4, 4, 1, 1, 2, 2)
    assert mask.count() == 4
    for x, y in ((1, 1), (2, 1), (1, 2), (2, 2)):
        assert mask.is_selected(x, y)
    assert not mask.is_selected(0, 0)


def test_sc_l002_2_swapped_corners_normalise_to_same_mask():
    assert rect_mask(4, 4, 2, 2, 1, 1) == rect_mask(4, 4, 1, 1, 2, 2)


def test_sc_l002_3_out_of_bounds_rectangle_is_clipped():
    mask = rect_mask(4, 4, 2, 2, 10, 10)
    assert mask.bounds() == (2, 2, 3, 3)
    assert not mask.is_selected(0, 0)


def test_sc_l002_4_fully_out_of_bounds_rectangle_is_empty():
    assert rect_mask(4, 4, 10, 10, 20, 20).is_empty
    assert rect_mask(4, 4, -5, -5, -2, -2).is_empty


# --- SC-L003: lasso selection --------------------------------------------


def test_sc_l003_1_closed_triangle_fills_interior_even_odd():
    mask = lasso_mask(8, 8, [(1, 1), (6, 1), (1, 6)])
    # A corner well inside the triangle is selected.
    assert mask.is_selected(2, 2)
    # A point clearly outside the hypotenuse is not.
    assert not mask.is_selected(6, 6)
    # Boundary vertices are traced.
    assert mask.is_selected(1, 1) and mask.is_selected(6, 1)


def test_sc_l003_2_path_auto_closes_last_to_first():
    # Omitting the closing edge still yields a closed, filled polygon.
    open_path = [(1, 1), (6, 1), (6, 6), (1, 6)]
    mask = lasso_mask(8, 8, open_path)
    assert mask.is_selected(3, 3)  # interior filled
    assert mask.is_selected(1, 6) and mask.is_selected(1, 1)  # closing edge traced


def test_sc_l003_3_degenerate_path_selects_at_most_traced_pixels():
    empty = lasso_mask(8, 8, [])
    assert empty.is_empty
    two = lasso_mask(8, 8, [(1, 1), (4, 1)])
    # A 2-point path traces the line, no interior fill.
    assert two.is_selected(1, 1) and two.is_selected(4, 1)
    assert not two.is_selected(2, 5)
    single = lasso_mask(8, 8, [(2, 2)])
    assert single.is_selected(2, 2) and single.count() == 1


def test_sc_l003_4_lasso_is_deterministic_for_identical_vertices():
    verts = [(0, 0), (5, 0), (5, 5), (0, 5)]
    assert lasso_mask(8, 8, verts) == lasso_mask(8, 8, verts)


def test_lasso_clips_vertices_to_bounds():
    mask = lasso_mask(4, 4, [(-3, -3), (10, -3), (10, 10), (-3, 10)])
    # A polygon larger than the buffer fills the whole (clipped) buffer.
    assert mask.count() == 16


# --- SC-L004: magic-wand selection ---------------------------------------


def test_sc_l004_1_wand_selects_only_contiguous_same_colour_region():
    buf = _buf(6, 1, fill=RED)
    buf.set_pixel(3, 0, GREEN)  # split the row into two red runs
    buf.set_pixel(4, 0, RED)
    buf.set_pixel(5, 0, RED)
    mask = wand_mask(buf, 0, 0)
    assert mask.is_selected(0, 0) and mask.is_selected(2, 0)
    assert not mask.is_selected(4, 0)  # separated red block excluded


def test_sc_l004_2_tolerance_includes_near_colours_excludes_far():
    near = (250, 0, 0, 255)  # distance_sq to RED = 25
    far = (0, 0, 255, 255)
    buf = _buf(3, 1, fill=RED)
    buf.set_pixel(1, 0, near)
    buf.set_pixel(2, 0, far)
    # tolerance 6 -> 6*6 = 36 >= 25 includes near, excludes far.
    mask = wand_mask(buf, 0, 0, tolerance=6)
    assert mask.is_selected(1, 0)
    assert not mask.is_selected(2, 0)
    # exact (tolerance 0) excludes the near colour too.
    assert not wand_mask(buf, 0, 0, tolerance=0).is_selected(1, 0)


def test_sc_l004_3_indexed_matches_exactly_tolerance_ignored():
    buf = PixelBuffer(3, 1, ColorMode.INDEXED, fill=5)
    buf.set_pixel(1, 0, 6)
    buf.set_pixel(2, 0, 5)
    mask = wand_mask(buf, 0, 0, tolerance=100)
    assert mask.is_selected(0, 0)
    assert not mask.is_selected(1, 0)  # exact match only, tolerance ignored


def test_sc_l004_4_out_of_bounds_seed_yields_empty_mask():
    buf = _buf(4, 4, fill=RED)
    assert wand_mask(buf, -1, 0).is_empty
    assert wand_mask(buf, 4, 4).is_empty


# --- SC-L005: selection operations ---------------------------------------


def test_sc_l005_1_invert_complements_within_bounds():
    mask = rect_mask(4, 4, 0, 0, 1, 3)
    inv = mask.invert()
    assert inv.is_selected(2, 0) and not inv.is_selected(0, 0)
    assert inv.count() == 16 - mask.count()


def test_sc_l005_2_clear_deselect_yields_empty_mask():
    assert rect_mask(4, 4, 0, 0, 3, 3).cleared().is_empty


def test_sc_l005_3_translate_shifts_and_clips_off_buffer():
    mask = rect_mask(4, 4, 0, 0, 1, 1)
    shifted = mask.translate(1, 1)
    assert shifted.is_selected(1, 1) and not shifted.is_selected(0, 0)
    # translate off the right/bottom clips away the vanished pixels.
    off = mask.translate(3, 3)
    assert off.count() == 1 and off.is_selected(3, 3)
    # negative translate clips on the near edges.
    neg = mask.translate(-1, -1)
    assert neg.count() == 1 and neg.is_selected(0, 0)


def test_sc_l005_4_combine_add_subtract_replace():
    a = rect_mask(4, 4, 0, 0, 1, 1)
    b = rect_mask(4, 4, 1, 1, 2, 2)
    added = a.combine(b, selection.COMBINE_ADD)
    assert added.count() == 4 + 4 - 1  # overlap at (1,1)
    subbed = a.combine(b, selection.COMBINE_SUBTRACT)
    assert subbed.count() == 3 and not subbed.is_selected(1, 1)
    replaced = a.combine(b, selection.COMBINE_REPLACE)
    assert replaced == b


def test_combine_errors_on_bad_mode_and_mismatched_dims():
    a = rect_mask(4, 4, 0, 0, 1, 1)
    with pytest.raises(SelectionError):
        a.combine(a, "xor")
    with pytest.raises(SelectionError):
        a.combine(rect_mask(8, 8, 0, 0, 1, 1), selection.COMBINE_ADD)


def test_sc_l005_5_move_lifts_pixels_and_restamps_at_offset():
    buf = _buf(4, 4, fill=TRANSPARENT)
    buf.set_pixel(0, 0, RED)
    buf.set_pixel(1, 0, RED)
    mask = rect_mask(4, 4, 0, 0, 1, 0)
    cmd = move_selection(buf, mask, 2, 1, target=None)
    cmd.execute()
    # vacated source is transparent, pixels re-stamped at +(2,1).
    assert buf.get_pixel(0, 0) == TRANSPARENT
    assert buf.get_pixel(1, 0) == TRANSPARENT
    assert buf.get_pixel(2, 1) == RED
    assert buf.get_pixel(3, 1) == RED


def test_sc_l005_5_move_indexed_vacates_index_zero():
    buf = PixelBuffer(4, 1, ColorMode.INDEXED, fill=0)
    buf.set_pixel(0, 0, 7)
    mask = rect_mask(4, 1, 0, 0, 0, 0)
    move_selection(buf, mask, 1, 0, target=None).execute()
    assert buf.get_pixel(0, 0) == 0
    assert buf.get_pixel(1, 0) == 7


def test_sc_l005_6_move_then_undo_restores_buffer_exactly():
    buf = _buf(5, 5, fill=TRANSPARENT)
    buf.set_pixel(1, 1, RED)
    buf.set_pixel(2, 1, GREEN)
    before = buf.copy()
    mask = rect_mask(5, 5, 1, 1, 2, 1)
    cmd = move_selection(buf, mask, 1, 2, target=None)
    cmd.execute()
    assert buf != before  # something moved
    cmd.undo()
    assert buf == before  # apply-then-undo = identity


def test_move_selection_argument_validation():
    buf = _buf(4, 4)
    good_mask = rect_mask(4, 4, 0, 0, 1, 1)
    with pytest.raises(SelectionError):
        move_selection(buf, rect_mask(8, 8, 0, 0, 1, 1), 1, 1, target=None)
    with pytest.raises(SelectionError):
        move_selection(buf, good_mask, 1.5, 1, target=None)  # type: ignore[arg-type]
    with pytest.raises(SelectionError):
        move_selection(buf, good_mask, True, 1, target=None)  # type: ignore[arg-type]


# --- SC-L006: mask-constrained editing -----------------------------------


def test_sc_l006_1_fill_constrained_to_mask_writes_only_masked_pixels():
    buf = _buf(4, 4, fill=TRANSPARENT)
    mask = rect_mask(4, 4, 0, 0, 1, 1)

    def paint(scratch: PixelBuffer) -> List[Tuple[int, int]]:
        return [(x, y) for y in range(4) for x in range(4) if _set(scratch, x, y)]

    def _set(scratch: PixelBuffer, x: int, y: int) -> bool:
        scratch.set_pixel(x, y, RED)
        return True

    changed = apply_masked(buf, paint, mask)
    assert set(changed) == {(0, 0), (1, 0), (0, 1), (1, 1)}
    assert buf.get_pixel(3, 3) == TRANSPARENT  # outside the mask, untouched


def test_sc_l006_2_no_active_mask_edits_whole_buffer():
    buf = _buf(3, 3, fill=TRANSPARENT)

    def paint(scratch: PixelBuffer) -> List[Tuple[int, int]]:
        coords = []
        for y in range(3):
            for x in range(3):
                scratch.set_pixel(x, y, BLUE)
                coords.append((x, y))
        return coords

    changed = apply_masked(buf, paint, None)
    assert len(changed) == 9
    assert buf.get_pixel(2, 2) == BLUE


def test_sc_l006_3_helper_returns_exactly_changed_coords():
    # An operation that reports a coord whose value does not change, and a
    # duplicate coord, must not appear in the returned change list.
    buf = _buf(3, 3, fill=RED)

    def paint(scratch: PixelBuffer) -> List[Tuple[int, int]]:
        scratch.set_pixel(0, 0, GREEN)  # real change
        scratch.set_pixel(1, 1, RED)  # no-op (already red)
        return [(0, 0), (0, 0), (1, 1)]  # duplicate + no-op

    changed = apply_masked(buf, paint, None)
    assert changed == [(0, 0)]


def test_apply_masked_dedup_and_unselected_skipped_with_mask():
    buf = _buf(3, 3, fill=RED)
    mask = rect_mask(3, 3, 0, 0, 0, 0)  # only (0,0)

    def paint(scratch: PixelBuffer) -> List[Tuple[int, int]]:
        scratch.set_pixel(0, 0, GREEN)
        scratch.set_pixel(2, 2, BLUE)  # outside the mask
        return [(0, 0), (0, 0), (2, 2)]

    changed = apply_masked(buf, paint, mask)
    assert changed == [(0, 0)]
    assert buf.get_pixel(2, 2) == RED  # unselected pixel untouched


# --- Hypothesis invariants -----------------------------------------------

_coord = st.integers(min_value=-2, max_value=6)


@settings(max_examples=100, derandomize=True)
@given(x0=_coord, y0=_coord, x1=_coord, y1=_coord)
def test_property_rect_mask_bounds_within_canvas(x0, y0, x1, y1):
    mask = rect_mask(5, 5, x0, y0, x1, y1)
    box = mask.bounds()
    if box is not None:
        bx0, by0, bx1, by1 = box
        assert 0 <= bx0 <= bx1 < 5
        assert 0 <= by0 <= by1 < 5


@settings(max_examples=100, derandomize=True)
@given(x0=_coord, y0=_coord, x1=_coord, y1=_coord)
def test_property_invert_invert_is_identity(x0, y0, x1, y1):
    mask = rect_mask(5, 5, x0, y0, x1, y1)
    assert mask.invert().invert() == mask


@settings(max_examples=100, derandomize=True)
@given(
    verts=st.lists(
        st.tuples(st.integers(0, 7), st.integers(0, 7)), min_size=0, max_size=8
    )
)
def test_property_lasso_mask_stays_in_bounds(verts):
    mask = lasso_mask(8, 8, verts)
    assert mask.data().shape == (8, 8)
    ys, xs = np.nonzero(mask.data())
    if xs.size:
        assert xs.max() < 8 and ys.max() < 8


# --- extract_masked (SC-P11-UI-013-1 payload clause, unit level) ----------


def _unique_pixel_buf(w: int, h: int) -> PixelBuffer:
    """A buffer where every pixel's colour encodes its own (x, y) coordinate.

    Lets a test tell "the selected pixel equals the source pixel at its own
    coordinate" apart from "the selected pixel equals some other pixel that
    happens to share its colour" (a uniform fill cannot make that distinction).
    """
    buf = PixelBuffer(w, h, fill=TRANSPARENT)
    for y in range(h):
        for x in range(w):
            buf.set_pixel(x, y, (10 + x * 10, 10 + y * 10, 100, 255))
    return buf


def _expected_region(buf: PixelBuffer, mask: SelectionMask) -> PixelBuffer:
    """The shipped no-regression comparator: ``region`` over the mask's own bounds."""
    x0, y0, x1, y1 = mask.bounds()
    return buf.region(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


class TestExtractMasked:
    def test_lasso_mask_exact_extraction(self):
        buf = _unique_pixel_buf(8, 8)
        # A triangle lasso: its bounding box strictly contains unselected corners.
        mask = lasso_mask(8, 8, [(1, 1), (6, 1), (1, 6)])
        assert mask.bounds() is not None
        x0, y0, x1, y1 = mask.bounds()

        out = extract_masked(buf, mask)

        assert out.width == x1 - x0 + 1
        assert out.height == y1 - y0 + 1
        sub_mask = mask.data()[y0 : y1 + 1, x0 : x1 + 1]
        selected_any = False
        unselected_any = False
        for oy in range(out.height):
            for ox in range(out.width):
                sx, sy = x0 + ox, y0 + oy
                if sub_mask[oy, ox]:
                    selected_any = True
                    assert out.get_pixel(ox, oy) == buf.get_pixel(sx, sy)
                else:
                    unselected_any = True
                    assert out.get_pixel(ox, oy) == TRANSPARENT
        # Both halves of the property must actually be exercised, or the
        # assertions above would pass vacuously.
        assert selected_any and unselected_any

    def test_wand_mask_exact_extraction(self):
        buf = PixelBuffer(6, 6, fill=(0, 0, 0, 255))
        # A plus-shaped contiguous region distinct from the background.
        plus = [(2, 1), (2, 2), (1, 2), (2, 2), (3, 2), (2, 3)]
        for x, y in plus:
            buf.set_pixel(x, y, (200, 50, 50, 255))

        mask = wand_mask(buf, 2, 2, tolerance=0)
        assert mask.bounds() is not None
        x0, y0, x1, y1 = mask.bounds()

        out = extract_masked(buf, mask)

        assert out.width == x1 - x0 + 1
        assert out.height == y1 - y0 + 1
        sub_mask = mask.data()[y0 : y1 + 1, x0 : x1 + 1]
        selected_any = False
        unselected_any = False
        for oy in range(out.height):
            for ox in range(out.width):
                sx, sy = x0 + ox, y0 + oy
                if sub_mask[oy, ox]:
                    selected_any = True
                    assert out.get_pixel(ox, oy) == buf.get_pixel(sx, sy)
                else:
                    unselected_any = True
                    assert out.get_pixel(ox, oy) == TRANSPARENT
        assert selected_any and unselected_any

    def test_rectangular_mask_matches_shipped_region_no_regression(self):
        buf = _unique_pixel_buf(6, 6)
        mask = rect_mask(6, 6, 1, 2, 4, 5)

        out = extract_masked(buf, mask)
        expected = _expected_region(buf, mask)

        assert out == expected

    def test_purity_buffer_and_mask_unchanged(self):
        buf = _unique_pixel_buf(5, 5)
        mask = lasso_mask(5, 5, [(0, 0), (4, 0), (4, 4), (0, 4)])

        buf_before = buf.data.copy()
        mask_before = mask.data().copy()

        extract_masked(buf, mask)

        assert np.array_equal(buf.data, buf_before)
        assert np.array_equal(mask.data(), mask_before)

    def test_raises_selection_error_on_dimension_mismatch(self):
        buf = _unique_pixel_buf(4, 4)
        mismatched_mask = rect_mask(5, 5, 0, 0, 1, 1)

        with pytest.raises(SelectionError):
            extract_masked(buf, mismatched_mask)

    def test_raises_selection_error_on_empty_mask(self):
        buf = _unique_pixel_buf(4, 4)
        empty_mask = SelectionMask(4, 4)

        with pytest.raises(SelectionError):
            extract_masked(buf, empty_mask)
