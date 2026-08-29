"""Tests for pixelart_creator.logic.dither (Bayer + Floyd–Steinberg).

Covers REQ-P3-LOGIC-006 / -007 and the reversible builder (REQ-P3-LOGIC-017):

* palette containment — the output colour set is a subset of the target palette
  (SC-L006-1, SC-L007-1) for both algorithms and Bayer sizes 2/4/8;
* the Bayer matrix defaults to ``BAYER_MATRIX_SIZE`` (SC-L006-2);
* determinism (SC-L006-3, SC-L007-3);
* ``make_dither_command`` yields a reversible command (apply∘undo = identity),
  honours a mask, and raises on a bad mode / empty palette.

Hypothesis: dither output ⊆ palette for arbitrary bounded pixel data.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants, history
from pixelart_creator.logic.dither import (
    DitherError,
    floyd_steinberg,
    make_dither_command,
    ordered_dither,
)
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import rect_mask

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
RED = (255, 0, 0, 255)
BW = Palette([BLACK, WHITE])


def _buffer_from_rows(rows):
    """Build an RGBA PixelBuffer from a nested list of RGBA tuples."""
    arr = np.array(rows, dtype=np.uint8)
    h, w = arr.shape[0], arr.shape[1]
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.data[:, :] = arr
    return buf


def _gradient_buffer(w=16, h=16):
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    for y in range(h):
        for x in range(w):
            g = int(255 * (x + y) / (w + h - 2))
            buf.set_pixel(x, y, (g, g, g, 255))
    return buf


def _colours_in(buffer):
    return {tuple(int(v) for v in px) for px in buffer.data.reshape(-1, 4)}


def _palette_set(palette):
    return {tuple(c) for c in palette.colors()}


# -- ordered / Bayer ----------------------------------------------------------


@pytest.mark.parametrize("size", [2, 4, 8])
def test_ordered_dither_output_subset_of_palette(size):
    # SC-L006-1: output ⊆ palette for Bayer 2/4/8.
    out = ordered_dither(_gradient_buffer(), BW, matrix_size=size)
    assert _colours_in(out).issubset(_palette_set(BW))


def test_ordered_dither_default_matrix_size_is_constant():
    # SC-L006-2: default matrix size is BAYER_MATRIX_SIZE (=4).
    assert constants.BAYER_MATRIX_SIZE == 4
    out_default = ordered_dither(_gradient_buffer(), BW)
    out_explicit = ordered_dither(_gradient_buffer(), BW, matrix_size=4)
    assert np.array_equal(out_default.data, out_explicit.data)


def test_ordered_dither_deterministic():
    # SC-L006-3.
    a = ordered_dither(_gradient_buffer(), BW)
    b = ordered_dither(_gradient_buffer(), BW)
    assert np.array_equal(a.data, b.data)


@pytest.mark.parametrize("bad", [3, 0, -4, True, "x"])
def test_ordered_dither_rejects_bad_matrix_size(bad):
    with pytest.raises(DitherError):
        ordered_dither(
            _gradient_buffer(4, 4), BW, matrix_size=bad  # type: ignore[arg-type]
        )


def test_ordered_dither_requires_rgba():
    idx = PixelBuffer(4, 4, ColorMode.INDEXED)
    with pytest.raises(DitherError):
        ordered_dither(idx, BW)


def test_ordered_dither_empty_palette_raises():
    with pytest.raises(PaletteError):
        ordered_dither(_gradient_buffer(4, 4), Palette())


# -- Floyd–Steinberg ----------------------------------------------------------


def test_floyd_steinberg_output_subset_of_palette():
    # SC-L007-1: output ⊆ palette.
    out = floyd_steinberg(_gradient_buffer(), BW)
    assert _colours_in(out).issubset(_palette_set(BW))


def test_floyd_steinberg_deterministic():
    # SC-L007-3.
    a = floyd_steinberg(_gradient_buffer(), BW)
    b = floyd_steinberg(_gradient_buffer(), BW)
    assert np.array_equal(a.data, b.data)


def test_floyd_steinberg_diffuses_error_to_neighbours():
    # SC-L007-2: a single mid-grey pixel forces its neighbours off-grey via the
    # 7/16 (right) and 3/16,5/16,1/16 (below) diffusion, so not every pixel maps
    # to the same palette colour.
    buf = PixelBuffer(3, 3, ColorMode.RGBA)
    buf.fill((128, 128, 128, 255))
    out = floyd_steinberg(buf, BW)
    colours = _colours_in(out)
    assert colours.issubset(_palette_set(BW))
    assert colours == {BLACK, WHITE}  # error diffusion produced both


def test_floyd_steinberg_requires_rgba():
    idx = PixelBuffer(4, 4, ColorMode.INDEXED)
    with pytest.raises(DitherError):
        floyd_steinberg(idx, BW)


def test_floyd_steinberg_empty_palette_raises():
    with pytest.raises(PaletteError):
        floyd_steinberg(_gradient_buffer(4, 4), Palette())


# -- make_dither_command (reversibility, REQ-P3-LOGIC-017) --------------------


@pytest.mark.parametrize("mode", ["ordered", "floyd_steinberg"])
def test_make_dither_command_reversible(mode):
    # SC-L017-1: apply ∘ undo = identity.
    buf = _gradient_buffer(8, 8)
    before = buf.copy()
    cmd = make_dither_command(buf, BW, mode, target=None)
    assert isinstance(cmd, history.Command)
    cmd.execute()
    assert _colours_in(buf).issubset(_palette_set(BW))
    cmd.undo()
    assert buf == before


def test_make_dither_command_respects_mask():
    buf = _gradient_buffer(8, 8)
    before = buf.copy()
    mask = rect_mask(8, 8, 0, 0, 3, 3)
    cmd = make_dither_command(buf, BW, "ordered", mask=mask, target=None)
    cmd.execute()
    # Unmasked region is unchanged; masked region is snapped to the palette.
    assert buf.get_pixel(7, 7) == before.get_pixel(7, 7)
    for y in range(4):
        for x in range(4):
            assert tuple(buf.get_pixel(x, y)) in _palette_set(BW)


def test_make_dither_command_bad_mode_raises():
    with pytest.raises(DitherError):
        make_dither_command(_gradient_buffer(4, 4), BW, "nope", target=None)


def test_make_dither_command_empty_palette_raises():
    with pytest.raises(PaletteError):
        make_dither_command(_gradient_buffer(4, 4), Palette(), "ordered", target=None)


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255),
)
def test_dither_containment_property(r, g, b):
    buf = PixelBuffer(4, 4, ColorMode.RGBA)
    buf.fill((r, g, b, 255))
    pal = Palette([BLACK, WHITE, RED])
    assert _colours_in(ordered_dither(buf, pal)).issubset(_palette_set(pal))
    assert _colours_in(floyd_steinberg(buf, pal)).issubset(_palette_set(pal))
