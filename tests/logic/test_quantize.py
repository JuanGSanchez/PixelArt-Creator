"""Tests for pixelart_creator.logic.quantize (constraint + median-cut + k-means).

Covers REQ-P3-LOGIC-009 / -010 / -011 and the reversible builder (-017):

* ``constrain_to_palette`` output ⊆ the target palette for distance_sq **and**
  the opt-in ciede2000 metric (SC-L009-1/-2/-3/-4), incl. NES / Game Boy;
* ``median_cut`` and ``kmeans`` return ≤N colours (SC-L010-1, SC-L011-1),
  deterministically; k-means is reproducible with ``KMEANS_SEED`` (run twice →
  identical, SC-L011-2); N defaults to ``PALETTE_EXTRACT_DEFAULT_N`` (SC-L010-2);
  a ≤N-colour image returns exactly those colours (SC-L010-3);
* ``make_constraint_command`` is reversible (SC-L017-1).

Hypothesis: extraction ≤N for arbitrary bounded buffers.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants, history
from pixelart_creator.logic.hardware_palette import game_boy_palette, nes_palette
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import (
    QuantizeError,
    constrain_to_palette,
    kmeans,
    make_constraint_command,
    median_cut,
)
from pixelart_creator.logic.selection import rect_mask

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
RED = (255, 0, 0, 255)


def _random_buffer(w=24, h=24, seed=1):
    rng = np.random.default_rng(seed)
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.data[:, :, :3] = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    buf.data[:, :, 3] = 255
    return buf


def _colours_in(buffer):
    return {tuple(int(v) for v in px) for px in buffer.data.reshape(-1, 4)}


def _palette_set(palette):
    return {tuple(c) for c in palette.colors()}


# -- constrain_to_palette (SC-L009) -------------------------------------------


def test_constrain_output_subset_of_nes():
    # SC-L009-1 (acceptance-critical): output ⊆ NES palette.
    nes = nes_palette()
    out = constrain_to_palette(_random_buffer(), nes)
    assert _colours_in(out).issubset(_palette_set(nes))


def test_constrain_output_subset_of_game_boy():
    # SC-L009-2.
    gb = game_boy_palette()
    out = constrain_to_palette(_random_buffer(), gb)
    assert _colours_in(out).issubset(_palette_set(gb))


def test_constrain_ciede2000_metric_still_subset():
    # SC-L009-4: the ΔE00 metric is selectable and still yields a ⊆ result.
    gb = game_boy_palette()
    out = constrain_to_palette(_random_buffer(12, 12), gb, metric="ciede2000")
    assert _colours_in(out).issubset(_palette_set(gb))


def test_constrain_maps_to_nearest_and_deterministic():
    # SC-L009-3.
    pal = Palette([BLACK, WHITE])
    buf = PixelBuffer(2, 1, ColorMode.RGBA)
    buf.set_pixel(0, 0, (10, 10, 10, 255))
    buf.set_pixel(1, 0, (240, 240, 240, 255))
    out = constrain_to_palette(buf, pal)
    assert out.get_pixel(0, 0) == BLACK
    assert out.get_pixel(1, 0) == WHITE
    assert np.array_equal(out.data, constrain_to_palette(buf, pal).data)


def test_constrain_requires_rgba():
    with pytest.raises(QuantizeError):
        constrain_to_palette(PixelBuffer(4, 4, ColorMode.INDEXED), nes_palette())


def test_constrain_empty_palette_raises():
    with pytest.raises(PaletteError):
        constrain_to_palette(_random_buffer(4, 4), Palette())


def test_constrain_bad_metric_raises():
    with pytest.raises(QuantizeError):
        constrain_to_palette(_random_buffer(4, 4), game_boy_palette(), metric="lab99")


# -- median_cut (SC-L010) -----------------------------------------------------


def test_median_cut_at_most_n():
    # SC-L010-1 (acceptance-critical).
    pal = median_cut(_random_buffer(), n=8)
    assert len(pal) <= 8


def test_median_cut_default_n_is_constant():
    # SC-L010-2.
    assert constants.PALETTE_EXTRACT_DEFAULT_N == 16
    pal = median_cut(_random_buffer())
    assert len(pal) <= constants.PALETTE_EXTRACT_DEFAULT_N


def test_median_cut_few_colours_returns_exactly_those():
    # SC-L010-3: ≤N distinct colours returns exactly those colours.
    buf = PixelBuffer(4, 4, ColorMode.RGBA)
    buf.fill(RED)
    buf.set_pixel(0, 0, BLACK)
    buf.set_pixel(1, 1, WHITE)
    pal = median_cut(buf, n=8)
    assert _palette_set(pal) == {RED, BLACK, WHITE}


def test_median_cut_deterministic():
    # SC-L010-4.
    assert (
        median_cut(_random_buffer(), n=8).colors()
        == median_cut(_random_buffer(), n=8).colors()
    )


@pytest.mark.parametrize("bad", [0, -1, True, "x"])
def test_median_cut_bad_n_raises(bad):
    with pytest.raises(QuantizeError):
        median_cut(_random_buffer(4, 4), n=bad)  # type: ignore[arg-type]


def test_median_cut_requires_rgba():
    with pytest.raises(QuantizeError):
        median_cut(PixelBuffer(4, 4, ColorMode.INDEXED))


# -- kmeans (SC-L011) ---------------------------------------------------------


def test_kmeans_at_most_n():
    # SC-L011-1 (acceptance-critical).
    pal = kmeans(_random_buffer(), n=6)
    assert len(pal) <= 6


def test_kmeans_deterministic_with_seed():
    # SC-L011-2: identical input+N+seed reproduces identical output (run twice).
    first = kmeans(_random_buffer(), n=6, seed=constants.KMEANS_SEED)
    second = kmeans(_random_buffer(), n=6, seed=constants.KMEANS_SEED)
    assert first.colors() == second.colors()


def test_kmeans_returns_palette():
    # SC-L011-3.
    assert isinstance(kmeans(_random_buffer(), n=4), Palette)


def test_kmeans_few_colours_shortcut():
    # unique colours ≤ n -> returns those directly (branch coverage).
    buf = PixelBuffer(4, 4, ColorMode.RGBA)
    buf.fill(RED)
    buf.set_pixel(0, 0, BLACK)
    pal = kmeans(buf, n=8)
    assert _palette_set(pal) == {RED, BLACK}


@pytest.mark.parametrize("bad", [0, -1, True])
def test_kmeans_bad_n_raises(bad):
    with pytest.raises(QuantizeError):
        kmeans(_random_buffer(4, 4), n=bad)  # type: ignore[arg-type]


def test_kmeans_requires_rgba():
    with pytest.raises(QuantizeError):
        kmeans(PixelBuffer(4, 4, ColorMode.INDEXED))


# -- make_constraint_command (SC-L017-1) --------------------------------------


def test_make_constraint_command_reversible():
    buf = _random_buffer(8, 8)
    before = buf.copy()
    cmd = make_constraint_command(buf, game_boy_palette(), target=None)
    assert isinstance(cmd, history.Command)
    cmd.execute()
    assert _colours_in(buf).issubset(_palette_set(game_boy_palette()))
    cmd.undo()
    assert buf == before


def test_make_constraint_command_respects_mask():
    buf = _random_buffer(8, 8)
    before = buf.copy()
    mask = rect_mask(8, 8, 0, 0, 3, 3)
    cmd = make_constraint_command(buf, game_boy_palette(), mask=mask, target=None)
    cmd.execute()
    assert buf.get_pixel(7, 7) == before.get_pixel(7, 7)


def test_make_constraint_command_ciede2000_metric():
    buf = _random_buffer(6, 6)
    cmd = make_constraint_command(
        buf, game_boy_palette(), metric="ciede2000", target=None
    )
    cmd.execute()
    assert _colours_in(buf).issubset(_palette_set(game_boy_palette()))


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255),
    n=st.integers(1, 16),
)
def test_extraction_at_most_n_property(r, g, b, n):
    buf = PixelBuffer(6, 6, ColorMode.RGBA)
    rng = np.random.default_rng(int(r) * 1000 + int(g) * 10 + int(b))
    buf.data[:, :, :3] = rng.integers(0, 256, size=(6, 6, 3), dtype=np.uint8)
    buf.data[:, :, 3] = 255
    assert len(median_cut(buf, n=n)) <= n
    assert len(kmeans(buf, n=n)) <= n
