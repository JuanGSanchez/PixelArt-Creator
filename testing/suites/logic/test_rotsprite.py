"""Tests for pixelart_creator.logic.rotsprite (REQ-P2-LOGIC-013).

One test per SC-L013 behaviour. The acceptance-critical invariant SC-L013-1 is
that the output colour set is a subset of the input colours together with the
transparent fill (0,0,0,0) (ADR-0002: the pipeline is copy-only). Plus
determinism, 0/360 identity, transparent-stays-transparent, and the upscale
factor sourced from constants.py. Small buffers keep the x8 upscale fast.
Zero Qt; deterministic and portable.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.color import TRANSPARENT
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.rotsprite import (
    _offset_search,
    _upscale,
    make_rotsprite_command,
    rotsprite,
)
from pixelart_creator.logic.selection import rect_mask

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


class _Holder:
    def __init__(self, buffer: PixelBuffer) -> None:
        self.buffer = buffer


def _sprite(w: int = 6, h: int = 6) -> PixelBuffer:
    """A small multi-colour RGBA sprite on a transparent field."""
    buf = PixelBuffer(w, h, fill=TRANSPARENT)
    buf.fill_rect(1, 1, w - 2, h - 2, RED)
    buf.set_pixel(2, 2, GREEN)
    buf.set_pixel(w - 3, h - 3, BLUE)
    return buf


def _rgba_colour_set(buf: PixelBuffer):
    return {tuple(px) for px in buf.data.reshape(-1, 4).tolist()}


# --- SC-L013-1: NO NEW COLOURS (acceptance-critical) ----------------------


def test_sc_l013_1_no_new_colours_rgba():
    buf = _sprite(6, 6)
    out = rotsprite(buf, 37.0)
    allowed = _rgba_colour_set(buf) | {TRANSPARENT}
    assert _rgba_colour_set(out).issubset(allowed)


def test_sc_l013_1_no_new_colours_indexed():
    buf = PixelBuffer(6, 6, ColorMode.INDEXED, fill=0)
    buf.fill_rect(1, 1, 4, 4, 3)
    buf.set_pixel(2, 2, 7)
    out = rotsprite(buf, 25.0)
    allowed = set(buf.data.reshape(-1).tolist()) | {0}
    assert set(out.data.reshape(-1).tolist()).issubset(allowed)


# --- SC-L013-2: 0 / 360 identity ------------------------------------------


def test_sc_l013_2_zero_and_360_return_equal_buffer():
    buf = _sprite(6, 6)
    assert rotsprite(buf, 0) == buf
    assert rotsprite(buf, 360) == buf
    assert rotsprite(buf, 720) == buf


def test_sc_l013_2_zero_returns_independent_copy():
    buf = _sprite(4, 4)
    out = rotsprite(buf, 0)
    out.set_pixel(0, 0, GREEN)
    assert buf.get_pixel(0, 0) != GREEN  # a copy, not the same array


# --- SC-L013-3: transparent stays transparent -----------------------------


def test_sc_l013_3_fully_transparent_stays_transparent():
    buf = PixelBuffer(6, 6, fill=TRANSPARENT)
    out = rotsprite(buf, 45.0)
    assert _rgba_colour_set(out) == {TRANSPARENT}


# --- SC-L013-4: determinism -----------------------------------------------


def test_sc_l013_4_deterministic_for_fixed_input_and_angle():
    buf = _sprite(6, 6)
    first = rotsprite(buf, 30.0)
    second = rotsprite(buf, 30.0)
    assert np.array_equal(first.data, second.data)


# --- SC-L013-5: upscale factor from constants -----------------------------


def test_sc_l013_5_upscale_factor_from_constants():
    assert constants.ROTSPRITE_UPSCALE_FACTOR == 8
    # the internal upscale scales dimensions by exactly the factor.
    img = _sprite(4, 4).data
    big = _upscale(
        img,
        True,
        constants.ROTSPRITE_SIMILARITY_THRESHOLD,
        constants.ROTSPRITE_UPSCALE_FACTOR,
    )
    assert big.shape[0] == 4 * constants.ROTSPRITE_UPSCALE_FACTOR
    assert big.shape[1] == 4 * constants.ROTSPRITE_UPSCALE_FACTOR


# --- The three unasserted ADR-0002 RotSprite pins ---------------------------


def test_rotsprite_similarity_threshold_is_100_by_identity():
    # ADR-0002: the shipped ROTSPRITE_SIMILARITY_THRESHOLD is pinned at 100.
    assert constants.ROTSPRITE_SIMILARITY_THRESHOLD == 100


def test_rotsprite_default_pivot_equals_explicit_grid_centre():
    # ADR-0002 #2: pivot=None defaults to exactly ((W-1)/2, (H-1)/2).
    buf = _sprite(6, 4)
    w, h = buf.width, buf.height
    default = rotsprite(buf, 40.0)
    explicit = rotsprite(buf, 40.0, pivot=((w - 1) / 2.0, (h - 1) / 2.0))
    assert default == explicit


def test_offset_search_lexicographic_minimum_on_a_constructed_tie():
    # ADR-0002 #3: _offset_search resolves a tie to the lexicographically
    # smallest (dx, dy). Constructed so offsets (0,0) AND (1,1) both cost 0
    # (the tie), while (0,1) and (1,0) cost strictly more -- proving the first
    # (lexicographically smallest) minimum is kept, not overwritten by the
    # later-found equal-cost (1,1).
    big = np.array(
        [
            [10, 99, 10, 1],
            [50, 20, 5, 20],
            [10, 99, 10, 1],
            [50, 20, 5, 20],
        ],
        dtype=np.uint8,
    )
    assert _offset_search(big, factor=2) == (0, 0)


# --- output geometry / options --------------------------------------------


def test_output_keeps_source_dimensions():
    buf = _sprite(6, 5)
    out = rotsprite(buf, 15.0)
    assert out.width == 6 and out.height == 5


def test_custom_fill_used_for_uncovered_pixels():
    buf = _sprite(6, 6)
    out = rotsprite(buf, 30.0, fill=BLUE)
    # corners rotate out of frame -> filled with the custom colour.
    allowed = _rgba_colour_set(buf) | {BLUE}
    assert _rgba_colour_set(out).issubset(allowed)
    assert out.get_pixel(0, 0) == BLUE


def test_custom_pivot_is_accepted():
    buf = _sprite(6, 6)
    out = rotsprite(buf, 20.0, pivot=(0.0, 0.0))
    assert out.width == 6 and out.height == 6


# --- make_rotsprite_command -----------------------------------------------


def test_command_whole_buffer_is_reversible():
    buf = _sprite(6, 6)
    before = buf.copy()
    holder = _Holder(buf)
    cmd = make_rotsprite_command(holder, 33.0, target=None)
    cmd.execute()
    assert holder.buffer != before
    cmd.undo()
    assert holder.buffer == before


def test_command_selection_touches_only_masked_pixels_and_reverts():
    buf = _sprite(8, 8)
    before = buf.copy()
    mask = rect_mask(8, 8, 2, 2, 5, 5)
    holder = _Holder(buf)
    cmd = make_rotsprite_command(holder, 30.0, mask, target=None)
    cmd.execute()
    # pixels outside the mask are unchanged.
    for y in range(8):
        for x in range(8):
            if not (2 <= x <= 5 and 2 <= y <= 5):
                assert buf.get_pixel(x, y) == before.get_pixel(x, y)
    cmd.undo()
    assert buf == before


def test_command_selection_dim_mismatch_raises():
    buf = _sprite(6, 6)
    holder = _Holder(buf)
    with pytest.raises(ValueError):
        make_rotsprite_command(holder, 30.0, rect_mask(8, 8, 0, 0, 1, 1), target=None)


def test_command_empty_selection_is_noop():
    buf = _sprite(6, 6)
    before = buf.copy()
    empty = rect_mask(6, 6, 10, 10, 20, 20)
    holder = _Holder(buf)
    cmd = make_rotsprite_command(holder, 30.0, empty, target=None)
    cmd.execute()
    assert buf == before


# --- Hypothesis: no-new-colours over angles + sprites ---------------------

_angle = st.floats(
    min_value=0.0, max_value=360.0, allow_nan=False, allow_infinity=False
)


@settings(max_examples=30, deadline=None, derandomize=True)
@given(angle=_angle)
def test_property_no_new_colours_over_angles(angle):
    buf = _sprite(6, 6)
    out = rotsprite(buf, angle)
    allowed = _rgba_colour_set(buf) | {TRANSPARENT}
    assert _rgba_colour_set(out).issubset(allowed)


@settings(max_examples=20, deadline=None, derandomize=True)
@given(
    data=st.data(),
    angle=_angle,
)
def test_property_random_sprite_no_new_colours(data, angle):
    buf = PixelBuffer(5, 5, fill=TRANSPARENT)
    chan = st.integers(0, 255)
    for y in range(5):
        for x in range(5):
            buf.set_pixel(
                x,
                y,
                (
                    data.draw(chan),
                    data.draw(chan),
                    data.draw(chan),
                    data.draw(chan),
                ),
            )
    out = rotsprite(buf, angle)
    allowed = _rgba_colour_set(buf) | {TRANSPARENT}
    assert _rgba_colour_set(out).issubset(allowed)
