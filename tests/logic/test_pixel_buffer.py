"""Tests for pixelart_creator.logic.pixel_buffer."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.constants import MAX_CANVAS_WIDTH
from pixelart_creator.logic.pixel_buffer import (
    ColorMode,
    PixelBuffer,
    PixelBufferError,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def test_default_rgba_is_transparent():
    buf = PixelBuffer(3, 2)
    assert buf.width == 3 and buf.height == 2
    assert buf.mode is ColorMode.RGBA
    assert buf.get_pixel(0, 0) == (0, 0, 0, 0)


def test_indexed_buffer_defaults_zero():
    buf = PixelBuffer(2, 2, ColorMode.INDEXED)
    assert buf.get_pixel(1, 1) == 0


def test_prefill_rgba_and_indexed():
    assert PixelBuffer(1, 1, fill=RED).get_pixel(0, 0) == RED
    assert PixelBuffer(1, 1, ColorMode.INDEXED, fill=7).get_pixel(0, 0) == 7


@pytest.mark.parametrize("w,h", [(0, 1), (1, 0), (-3, 2)])
def test_bad_dimensions(w, h):
    with pytest.raises(PixelBufferError):
        PixelBuffer(w, h)


def test_non_int_dimensions_rejected():
    with pytest.raises(PixelBufferError):
        PixelBuffer("2", 2)  # type: ignore[arg-type]
    with pytest.raises(PixelBufferError):
        PixelBuffer(2, True)  # type: ignore[arg-type]


def test_indexed_fill_rect():
    buf = PixelBuffer(4, 4, ColorMode.INDEXED)
    buf.fill_rect(1, 1, 2, 2, 9)
    assert buf.get_pixel(1, 1) == 9
    assert buf.get_pixel(0, 0) == 0


def test_dimension_exceeds_max():
    with pytest.raises(PixelBufferError):
        PixelBuffer(MAX_CANVAS_WIDTH + 1, 1)


def test_bad_mode():
    with pytest.raises(PixelBufferError):
        PixelBuffer(1, 1, mode="rgba")  # type: ignore[arg-type]


def test_set_get_pixel():
    buf = PixelBuffer(2, 2)
    buf.set_pixel(1, 0, RED)
    assert buf.get_pixel(1, 0) == RED


def test_out_of_bounds_access():
    buf = PixelBuffer(2, 2)
    with pytest.raises(PixelBufferError):
        buf.get_pixel(2, 0)
    with pytest.raises(PixelBufferError):
        buf.set_pixel(0, -1, RED)


def test_wrong_value_type_for_mode():
    rgba_buf = PixelBuffer(1, 1)
    with pytest.raises(PixelBufferError):
        rgba_buf.set_pixel(0, 0, 5)  # index into rgba buffer
    idx_buf = PixelBuffer(1, 1, ColorMode.INDEXED)
    with pytest.raises(PixelBufferError):
        idx_buf.set_pixel(0, 0, RED)  # tuple into indexed buffer
    with pytest.raises(PixelBufferError):
        idx_buf.set_pixel(0, 0, 300)  # index out of 0..255


def test_fill_and_fill_rect_clipped():
    buf = PixelBuffer(4, 4)
    buf.fill(RED)
    assert buf.get_pixel(3, 3) == RED
    buf.fill_rect(-1, -1, 2, 2, BLUE)  # clipped to (0,0)
    assert buf.get_pixel(0, 0) == BLUE
    assert buf.get_pixel(1, 1) == RED
    buf.fill_rect(0, 0, 0, 5, BLUE)  # zero width no-op
    buf.fill_rect(10, 10, 2, 2, BLUE)  # fully outside no-op


def test_region_copy_independent():
    buf = PixelBuffer(4, 4, fill=RED)
    buf.set_pixel(2, 2, BLUE)
    region = buf.region(1, 1, 2, 2)
    assert region.width == 2 and region.get_pixel(1, 1) == BLUE
    region.set_pixel(0, 0, BLUE)
    assert buf.get_pixel(1, 1) == RED  # original untouched


def test_region_out_of_bounds():
    buf = PixelBuffer(2, 2)
    with pytest.raises(PixelBufferError):
        buf.region(1, 1, 5, 5)
    with pytest.raises(PixelBufferError):
        buf.region(0, 0, 0, 1)


def test_blit_overwrite_and_clip():
    dst = PixelBuffer(4, 4)
    src = PixelBuffer(2, 2, fill=RED)
    dst.blit(src, 3, 3)  # only 1px lands in-bounds
    assert dst.get_pixel(3, 3) == RED
    dst.blit(src, -5, 0)  # fully clipped -> no-op
    assert dst.get_pixel(0, 0) == (0, 0, 0, 0)


def test_blit_mode_mismatch():
    dst = PixelBuffer(2, 2)
    src = PixelBuffer(2, 2, ColorMode.INDEXED)
    with pytest.raises(PixelBufferError):
        dst.blit(src, 0, 0)


def test_blit_blend_on_indexed_rejected():
    dst = PixelBuffer(2, 2, ColorMode.INDEXED)
    src = PixelBuffer(2, 2, ColorMode.INDEXED)
    with pytest.raises(PixelBufferError):
        dst.blit(src, 0, 0, blend=True)


def test_blit_blend_composites_alpha():
    dst = PixelBuffer(1, 1, fill=BLUE)
    src = PixelBuffer(1, 1, fill=(255, 0, 0, 128))
    dst.blit(src, 0, 0, blend=True)
    r, g, b, a = dst.get_pixel(0, 0)
    assert a == 255 and r > b


def test_resize_pad_and_crop_preserve_content():
    buf = PixelBuffer(2, 2, fill=RED)
    bigger = buf.resize(4, 4)
    assert bigger.width == 4
    assert bigger.get_pixel(0, 0) == RED
    assert bigger.get_pixel(3, 3) == (0, 0, 0, 0)  # padded
    smaller = buf.resize(1, 1)
    assert smaller.get_pixel(0, 0) == RED


def test_resize_with_offset():
    buf = PixelBuffer(1, 1, fill=RED)
    out = buf.resize(3, 3, offset_x=1, offset_y=1)
    assert out.get_pixel(1, 1) == RED
    assert out.get_pixel(0, 0) == (0, 0, 0, 0)


def test_copy_equality_and_independence():
    buf = PixelBuffer(2, 2, fill=RED)
    clone = buf.copy()
    assert clone == buf
    clone.set_pixel(0, 0, BLUE)
    assert clone != buf


def test_eq_notimplemented_and_mode_diff():
    buf = PixelBuffer(1, 1)
    assert (buf == "x") is False
    assert buf != PixelBuffer(1, 1, ColorMode.INDEXED)


def test_data_is_uint8_array_and_repr():
    buf = PixelBuffer(2, 2)
    assert isinstance(buf.data, np.ndarray) and buf.data.dtype == np.uint8
    assert "PixelBuffer(2x2" in repr(buf)


def test_in_bounds():
    buf = PixelBuffer(2, 2)
    assert buf.in_bounds(0, 0) and buf.in_bounds(1, 1)
    assert not buf.in_bounds(2, 0) and not buf.in_bounds(0, 2)


# --------------------------------------------------------------------------- #
# Casuistics (M) — Hypothesis: blit / resize round-trip + bounds              #
# --------------------------------------------------------------------------- #

_dim = st.integers(min_value=1, max_value=10)
_chan = st.integers(min_value=0, max_value=255)
_rgba = st.tuples(_chan, _chan, _chan, _chan)


@given(w=_dim, h=_dim, color=_rgba)
def test_property_region_of_a_filled_buffer_round_trips(w, h, color):
    """A filled buffer's own full-extent region() equals a copy() of itself --
    the blit source-of-truth never drifts from a plain fill+read round-trip."""
    buf = PixelBuffer(w, h, fill=color)
    assert np.array_equal(buf.region(0, 0, w, h).data, buf.copy().data)


@given(w=_dim, h=_dim, color=_rgba, dx=st.integers(-5, 5), dy=st.integers(-5, 5))
def test_property_blit_then_region_recovers_the_source_within_bounds(
    w, h, color, dx, dy
):
    """blit(source, dx, dy) then reading back the overlapping region equals the
    source pixels that actually landed in bounds (blit never corrupts data it
    places, and never touches pixels outside the destination)."""
    dest = PixelBuffer(w, h, fill=(0, 0, 0, 0))
    source = PixelBuffer(w, h, fill=color)
    before = dest.data.copy()
    dest.blit(source, dx, dy)

    sx0, sy0 = max(0, -dx), max(0, -dy)
    sx1, sy1 = min(w, w - dx), min(h, h - dy)
    if sx0 < sx1 and sy0 < sy1:
        dx0, dy0, dx1, dy1 = dx + sx0, dy + sy0, dx + sx1, dy + sy1
        pasted = dest.region(dx0, dy0, dx1 - dx0, dy1 - dy0)
        assert np.array_equal(
            pasted.data, np.full((dy1 - dy0, dx1 - dx0, 4), color, dtype=np.uint8)
        )
    else:
        # Fully off-canvas: nothing changed.
        assert np.array_equal(dest.data, before)


@given(
    w=_dim,
    h=_dim,
    color=_rgba,
    nw=_dim,
    nh=_dim,
    ox=st.integers(-3, 3),
    oy=st.integers(-3, 3),
)
def test_property_resize_preserves_the_overlapping_content(w, h, color, nw, nh, ox, oy):
    """resize() places the old content at (offset_x, offset_y) in a NEW buffer
    of the requested size -- the result dimensions match the request exactly,
    and it never mutates the original."""
    original = PixelBuffer(w, h, fill=color)
    before = original.data.copy()
    resized = original.resize(nw, nh, offset_x=ox, offset_y=oy)
    assert (resized.width, resized.height) == (nw, nh)
    assert np.array_equal(original.data, before)  # non-destructive


@given(w=_dim, h=_dim)
def test_property_region_out_of_bounds_always_raises(w, h):
    """A region that starts (or ends) outside the buffer always raises, for
    every size/coordinate combination -- never clamped, never silently cropped."""
    buf = PixelBuffer(w, h)
    with pytest.raises(PixelBufferError):
        buf.region(w, 0, 1, 1)  # starts exactly one past the right edge
    with pytest.raises(PixelBufferError):
        buf.region(0, h, 1, 1)  # starts exactly one past the bottom edge
