"""Tests for pixelart_creator.logic.pixel_buffer."""

from __future__ import annotations

import numpy as np
import pytest

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
