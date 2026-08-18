"""Tests for pixelart_creator.logic.tiled (REQ-P2-LOGIC-014).

One test per SC-L014 behaviour, plus Hypothesis invariants (wrap is the modulo
identity; a wrapped edit then undo restores the buffer). Zero Qt; deterministic.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic.constants import TILED_PREVIEW_REPEAT
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tiled import make_tiled_command, preview_tiling, wrap

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)


def _buf(w: int = 4, h: int = 4) -> PixelBuffer:
    buf = PixelBuffer(w, h)
    # give each tile a recognisable corner pixel.
    buf.set_pixel(0, 0, GREEN)
    return buf


# --- SC-L014-1 / -2: torus wrap -------------------------------------------


def test_sc_l014_1_coordinate_past_edge_wraps_modulo():
    assert wrap(5, 6, 4, 4) == (1, 2)
    assert wrap(4, 4, 4, 4) == (0, 0)


def test_sc_l014_2_negative_coordinate_wraps_to_opposite_edge():
    assert wrap(-1, -1, 4, 4) == (3, 3)
    assert wrap(-5, -8, 4, 4) == (3, 0)


def test_wrap_in_range_is_identity():
    assert wrap(2, 3, 4, 4) == (2, 3)


def test_wrap_nonpositive_dimensions_raise():
    with pytest.raises(ValueError):
        wrap(1, 1, 0, 4)
    with pytest.raises(ValueError):
        wrap(1, 1, 4, -2)


# --- SC-L014-3: preview tiling --------------------------------------------


def test_sc_l014_3_preview_tiling_default_is_3x3():
    buf = _buf(4, 4)
    out = preview_tiling(buf)
    assert out.width == 4 * TILED_PREVIEW_REPEAT
    assert out.height == 4 * TILED_PREVIEW_REPEAT
    # every tile's (0,0) corner carries the marker colour.
    for row in range(TILED_PREVIEW_REPEAT):
        for col in range(TILED_PREVIEW_REPEAT):
            assert out.get_pixel(col * 4, row * 4) == GREEN


def test_preview_tiling_custom_repeat():
    buf = _buf(3, 2)
    out = preview_tiling(buf, repeat=2)
    assert out.width == 6 and out.height == 4


def test_preview_tiling_invalid_repeat_raises():
    buf = _buf(4, 4)
    with pytest.raises(ValueError):
        preview_tiling(buf, repeat=0)
    with pytest.raises(ValueError):
        preview_tiling(buf, repeat=True)  # type: ignore[arg-type]


def test_preview_tiling_indexed_mode():
    buf = PixelBuffer(2, 2, ColorMode.INDEXED, fill=4)
    out = preview_tiling(buf, repeat=2)
    assert out.mode is ColorMode.INDEXED
    assert out.get_pixel(3, 3) == 4


# --- SC-L014-4: reversible wrapped edit -----------------------------------


def test_wrapped_edit_paints_wrapped_pixels():
    buf = PixelBuffer(4, 4)
    cmd = make_tiled_command(buf, lambda: ([(5, 6), (-1, -1)], RED), target=None)
    cmd.execute()
    assert buf.get_pixel(1, 2) == RED  # (5,6) wrapped
    assert buf.get_pixel(3, 3) == RED  # (-1,-1) wrapped


def test_sc_l014_4_wrapped_edit_then_undo_restores_buffer():
    buf = PixelBuffer(4, 4)
    before = buf.copy()
    cmd = make_tiled_command(buf, lambda: ([(4, 0), (0, 5), (7, 7)], RED), target=None)
    cmd.execute()
    assert buf != before
    cmd.undo()
    assert buf == before


def test_wrapped_edit_dedups_coincident_wrapped_coords():
    buf = PixelBuffer(4, 4)
    # (0,0) and (4,4) both wrap to (0,0); only one change is recorded.
    cmd = make_tiled_command(buf, lambda: ([(0, 0), (4, 4)], RED), target=None)
    cmd.execute()
    assert len(cmd) == 1


def test_wrapped_edit_noop_when_value_unchanged():
    buf = PixelBuffer(4, 4, fill=RED)
    cmd = make_tiled_command(buf, lambda: ([(0, 0), (5, 5)], RED), target=None)
    cmd.execute()
    assert len(cmd) == 0


def test_wrapped_edit_indexed():
    buf = PixelBuffer(4, 4, ColorMode.INDEXED, fill=0)
    before = buf.copy()
    cmd = make_tiled_command(buf, lambda: ([(5, 5)], 9), target=None)
    cmd.execute()
    assert buf.get_pixel(1, 1) == 9
    cmd.undo()
    assert buf == before


# --- Hypothesis invariants ------------------------------------------------

_coord = st.integers(min_value=-50, max_value=50)
_dim = st.integers(min_value=1, max_value=16)


@settings(max_examples=200, derandomize=True)
@given(x=_coord, y=_coord, w=_dim, h=_dim)
def test_property_wrap_is_modulo_identity(x, y, w, h):
    wx, wy = wrap(x, y, w, h)
    assert 0 <= wx < w and 0 <= wy < h
    assert wx == x % w and wy == y % h


@settings(max_examples=100, derandomize=True)
@given(
    coords=st.lists(st.tuples(_coord, _coord), min_size=0, max_size=10),
    w=st.integers(2, 8),
    h=st.integers(2, 8),
)
def test_property_wrapped_edit_reversible(coords, w, h):
    buf = PixelBuffer(w, h)
    before = buf.copy()
    cmd = make_tiled_command(buf, lambda: (coords, RED), target=None)
    cmd.execute()
    cmd.undo()
    assert buf == before
