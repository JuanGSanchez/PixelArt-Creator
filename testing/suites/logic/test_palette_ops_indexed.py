"""Tests for the pure indexed-mode converters in ``logic.palette_ops`` (no Qt).

Covers the RGBA<->indexed *pure* functions AGT-03 kept (REQ-P3-UI-014 logic
support). The reversible **mode-conversion commands** moved up to
:class:`~pixelart_creator.logic.document.Document` (ADR-0008 D3/D6 — the
buffer-level ``make_to_indexed_command`` / ``make_to_rgba_command`` and the
``SupportsBuffer`` protocol were retired); those commands are covered by
``testing/suites/logic/test_document_convert.py``. This module keeps the pure-function
coverage the commands delegate to:

* :func:`to_indexed` snaps each pixel to its nearest palette index — by squared
  RGBA distance (default, matching :meth:`Palette.nearest_index`, ties -> lower
  index) and by perceptual ΔE00 (``metric="ciede2000"``);
* :func:`to_rgba` is the palette-lookup inverse;
* the pair is lossy-to-the-palette: ``to_rgba(to_indexed(rgba, pal), pal)`` has a
  colour set ⊆ ``pal`` and is idempotent on an already-quantised buffer;
* :class:`IndexedModeError` / :class:`PaletteError` on invalid input;
* determinism (P2).

Hypothesis: round-trip colour-containment and nearest-index equivalence on
generated RGBA buffers + palettes, deterministic under the ``ci`` profile
(conftest).
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import perceptual
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.palette_ops import (
    IndexedModeError,
    to_indexed,
    to_rgba,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)


def _rgba_buffer(rows: Sequence[Sequence[RGBA]]) -> PixelBuffer:
    """Build an RGBA buffer from a 2-D grid of RGBA tuples."""
    height = len(rows)
    width = len(rows[0])
    buf = PixelBuffer(width, height, ColorMode.RGBA)
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            buf.set_pixel(x, y, color)
    return buf


def _indexed_buffer(rows: Sequence[Sequence[int]]) -> PixelBuffer:
    arr = np.array(rows, dtype=np.uint8)
    h, w = arr.shape
    buf = PixelBuffer(w, h, ColorMode.INDEXED)
    buf.data[:, :] = arr
    return buf


# -- to_indexed: nearest-index mapping (default distance_sq) ------------------


def test_to_indexed_maps_each_pixel_to_nearest_index():
    # Exact palette colours must map to their own index.
    pal = Palette([RED, GREEN, BLUE])
    buf = _rgba_buffer([[RED, GREEN], [BLUE, RED]])
    out = to_indexed(buf, pal)
    assert out.mode is ColorMode.INDEXED
    assert out.data.tolist() == [[0, 1], [2, 0]]


def test_to_indexed_snaps_off_palette_colour_to_nearest():
    pal = Palette([BLACK, WHITE])
    # (200,200,200) is nearer white; (50,50,50) is nearer black.
    buf = _rgba_buffer([[(200, 200, 200, 255), (50, 50, 50, 255)]])
    out = to_indexed(buf, pal)
    assert out.data.tolist() == [[1, 0]]


def test_to_indexed_matches_palette_nearest_index_per_pixel():
    # Every produced index must equal Palette.nearest_index for that pixel.
    pal = Palette([BLACK, RED, GREEN, BLUE, WHITE])
    colors = [
        (10, 20, 30, 255),
        (250, 5, 5, 255),
        (5, 240, 10, 128),
        (30, 40, 250, 255),
        (240, 240, 240, 255),
        (120, 120, 120, 200),
    ]
    buf = _rgba_buffer([colors[:3], colors[3:]])
    out = to_indexed(buf, pal)
    for y in range(buf.height):
        for x in range(buf.width):
            expected = pal.nearest_index(buf.get_pixel(x, y))
            assert out.get_pixel(x, y) == expected


def test_to_indexed_ties_resolve_to_lower_index():
    # (5,0,0) is equidistant (25) from index 0 and index 1 -> lower index 0.
    pal = Palette([(0, 0, 0, 255), (10, 0, 0, 255)])
    buf = _rgba_buffer([[(5, 0, 0, 255)]])
    out = to_indexed(buf, pal)
    assert out.data.tolist() == [[0]]
    # Sanity: Palette.nearest_index resolves the same tie identically.
    assert pal.nearest_index((5, 0, 0, 255)) == 0


def test_to_indexed_distance_includes_alpha():
    # Two palette colours identical in RGB but differing in alpha; the pixel's
    # alpha decides the nearest match (distance_sq spans all four channels).
    pal = Palette([(10, 10, 10, 0), (10, 10, 10, 255)])
    buf = _rgba_buffer([[(10, 10, 10, 240), (10, 10, 10, 10)]])
    out = to_indexed(buf, pal)
    assert out.data.tolist() == [[1, 0]]


def test_to_indexed_ciede2000_path_matches_perceptual():
    pal = Palette([BLACK, RED, GREEN, BLUE, WHITE])
    colors = [
        (12, 200, 30, 255),
        (240, 10, 10, 255),
        (5, 5, 5, 255),
        (250, 250, 250, 255),
    ]
    buf = _rgba_buffer([colors[:2], colors[2:]])
    out = to_indexed(buf, pal, metric="ciede2000")
    for y in range(buf.height):
        for x in range(buf.width):
            expected = perceptual.nearest_index_perceptual(pal, buf.get_pixel(x, y))
            assert out.get_pixel(x, y) == expected


# -- to_rgba: palette lookup --------------------------------------------------


def test_to_rgba_reproduces_palette_colours_by_index():
    pal = Palette([RED, GREEN, BLUE])
    buf = _indexed_buffer([[0, 1], [2, 0]])
    out = to_rgba(buf, pal)
    assert out.mode is ColorMode.RGBA
    assert out.get_pixel(0, 0) == RED
    assert out.get_pixel(1, 0) == GREEN
    assert out.get_pixel(0, 1) == BLUE
    assert out.get_pixel(1, 1) == RED


# -- round-trip / idempotence -------------------------------------------------


def test_round_trip_colours_subset_of_palette():
    pal = Palette([BLACK, RED, GREEN, BLUE, WHITE])
    buf = _rgba_buffer(
        [
            [(9, 200, 15, 255), (250, 3, 4, 255)],
            [(5, 5, 5, 255), (30, 20, 240, 255)],
        ]
    )
    restored = to_rgba(to_indexed(buf, pal), pal)
    palette_set = {tuple(c) for c in pal.colors()}
    for y in range(restored.height):
        for x in range(restored.width):
            assert restored.get_pixel(x, y) in palette_set


def test_round_trip_idempotent_on_quantised_buffer():
    # A buffer already made of palette colours survives a round-trip unchanged.
    pal = Palette([RED, GREEN, BLUE])
    quantised = _rgba_buffer([[RED, GREEN], [BLUE, RED]])
    once = to_rgba(to_indexed(quantised, pal), pal)
    twice = to_rgba(to_indexed(once, pal), pal)
    assert once == quantised
    assert twice == once


# -- invalid input ------------------------------------------------------------


def test_to_indexed_requires_rgba_buffer():
    with pytest.raises(IndexedModeError):
        to_indexed(PixelBuffer(2, 2, ColorMode.INDEXED), Palette([RED]))


def test_to_indexed_unknown_metric_raises():
    with pytest.raises(IndexedModeError):
        to_indexed(PixelBuffer(2, 2, ColorMode.RGBA), Palette([RED]), metric="nope")


def test_to_indexed_empty_palette_raises():
    with pytest.raises(PaletteError):
        to_indexed(PixelBuffer(2, 2, ColorMode.RGBA), Palette([]))


def test_to_rgba_requires_indexed_buffer():
    with pytest.raises(IndexedModeError):
        to_rgba(PixelBuffer(2, 2, ColorMode.RGBA), Palette([RED]))


def test_to_rgba_empty_palette_raises():
    with pytest.raises(PaletteError):
        to_rgba(PixelBuffer(2, 2, ColorMode.INDEXED), Palette([]))


def test_to_rgba_index_out_of_palette_range_raises():
    pal = Palette([RED, GREEN])  # valid indices 0..1
    buf = _indexed_buffer([[0, 2]])  # references index 2
    with pytest.raises(PaletteError):
        to_rgba(buf, pal)


# -- determinism (P2) ---------------------------------------------------------


def test_to_indexed_deterministic():
    pal = Palette([BLACK, RED, GREEN, BLUE, WHITE])
    buf = _rgba_buffer([[(9, 200, 15, 255), (250, 3, 4, 255)]])
    a = to_indexed(buf, pal)
    b = to_indexed(buf, pal)
    assert np.array_equal(a.data, b.data)


def test_to_rgba_deterministic():
    pal = Palette([RED, GREEN, BLUE])
    buf = _indexed_buffer([[0, 1], [2, 0]])
    assert to_rgba(buf, pal) == to_rgba(buf, pal)


# -- Hypothesis property tests ------------------------------------------------

_channel = st.integers(min_value=0, max_value=255)
_colour = st.tuples(_channel, _channel, _channel, _channel)


@st.composite
def _palette_and_pixels(draw):
    n_colours = draw(st.integers(min_value=1, max_value=6))
    colours: List[RGBA] = draw(
        st.lists(_colour, min_size=n_colours, max_size=n_colours)
    )
    width = draw(st.integers(min_value=1, max_value=4))
    height = draw(st.integers(min_value=1, max_value=4))
    pixels = draw(
        st.lists(
            st.lists(_colour, min_size=width, max_size=width),
            min_size=height,
            max_size=height,
        )
    )
    return colours, pixels


@given(_palette_and_pixels())
def test_property_round_trip_colours_subset_of_palette(data):
    colours, pixels = data
    pal = Palette(colours)
    buf = _rgba_buffer(pixels)
    restored = to_rgba(to_indexed(buf, pal), pal)
    palette_set = {tuple(c) for c in pal.colors()}
    for y in range(restored.height):
        for x in range(restored.width):
            assert restored.get_pixel(x, y) in palette_set


@given(_palette_and_pixels())
def test_property_to_indexed_matches_nearest_index(data):
    colours, pixels = data
    pal = Palette(colours)
    buf = _rgba_buffer(pixels)
    out = to_indexed(buf, pal)
    for y in range(buf.height):
        for x in range(buf.width):
            assert out.get_pixel(x, y) == pal.nearest_index(buf.get_pixel(x, y))
