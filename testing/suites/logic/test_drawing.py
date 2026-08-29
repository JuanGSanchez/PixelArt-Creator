"""Tests for pixelart_creator.logic.drawing."""

from __future__ import annotations

from pixelart_creator.logic import drawing
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def _new(w=8, h=8, fill=(0, 0, 0, 0)):
    return PixelBuffer(w, h, fill=fill)


def test_pencil_in_and_out_of_bounds():
    buf = _new(2, 2)
    assert drawing.pencil(buf, 0, 0, RED) == [(0, 0)]
    assert buf.get_pixel(0, 0) == RED
    assert drawing.pencil(buf, 9, 9, RED) == []


def test_pick_color():
    buf = _new(2, 2, fill=RED)
    assert drawing.pick_color(buf, 1, 1) == RED


def test_line_horizontal_and_diagonal():
    buf = _new()
    coords = drawing.line(buf, 0, 0, 3, 0, RED)
    assert coords == [(0, 0), (1, 0), (2, 0), (3, 0)]
    diag = drawing.line(buf, 0, 0, 3, 3, GREEN)
    assert (2, 2) in diag and buf.get_pixel(3, 3) == GREEN


def test_line_single_point():
    buf = _new()
    assert drawing.line(buf, 2, 2, 2, 2, RED) == [(2, 2)]


def test_line_vertical():
    buf = _new()
    coords = drawing.line(buf, 1, 0, 1, 3, RED)
    assert coords == [(1, 0), (1, 1), (1, 2), (1, 3)]


def test_line_steep():
    buf = _new()
    coords = drawing.line(buf, 0, 0, 1, 4, RED)
    assert (0, 0) in coords and (1, 4) in coords
    assert len(coords) == 5


def test_line_clips_out_of_bounds_endpoints():
    buf = _new(4, 4)
    coords = drawing.line(buf, -2, 0, 2, 0, RED)
    # negative x coords are skipped, positives painted
    assert (0, 0) in coords and (-1, 0) not in coords


def test_rectangle_outline_perimeter_only():
    buf = _new()
    coords = drawing.rectangle(buf, 1, 1, 3, 3, RED)
    assert (1, 1) in coords and (3, 3) in coords
    assert (2, 2) not in coords  # centre not on outline
    assert buf.get_pixel(2, 2) == (0, 0, 0, 0)


def test_rectangle_filled():
    buf = _new()
    coords = drawing.rectangle(buf, 1, 1, 3, 3, RED, filled=True)
    assert (2, 2) in coords
    assert len(coords) == 9


def test_rectangle_normalises_swapped_corners():
    buf = _new()
    a = drawing.rectangle(buf.copy(), 3, 3, 1, 1, RED)
    b = drawing.rectangle(buf.copy(), 1, 1, 3, 3, RED)
    assert set(a) == set(b)


def test_ellipse_outline_and_fill():
    buf = _new(16, 16)
    outline = drawing.ellipse(buf, 2, 2, 12, 8, RED)
    assert outline  # non-empty
    filled_buf = _new(16, 16)
    filled = drawing.ellipse(filled_buf, 2, 2, 12, 8, RED, filled=True)
    assert len(filled) > len(outline)


def test_ellipse_various_aspect_ratios_stay_in_bounds():
    for x0, y0, x1, y1 in [(0, 0, 15, 15), (0, 0, 15, 5), (0, 0, 5, 15), (0, 0, 9, 9)]:
        buf = _new(16, 16)
        coords = drawing.ellipse(buf, x0, y0, x1, y1, RED)
        assert coords
        for cx, cy in coords:
            assert buf.in_bounds(cx, cy)


def test_ellipse_degenerate_becomes_line():
    buf = _new()
    coords = drawing.ellipse(buf, 0, 0, 5, 0, RED)
    assert (0, 0) in coords and (5, 0) in coords


def test_flood_fill_contiguous_region():
    buf = _new(4, 4, fill=RED)
    buf.fill_rect(0, 0, 2, 4, BLUE)  # left half blue
    coords = drawing.flood_fill(buf, 0, 0, GREEN)
    assert len(coords) == 8  # 2x4 region
    assert buf.get_pixel(0, 0) == GREEN
    assert buf.get_pixel(2, 0) == RED  # right half untouched


def test_flood_fill_noop_when_same_color():
    buf = _new(3, 3, fill=RED)
    assert drawing.flood_fill(buf, 0, 0, RED) == []


def test_flood_fill_out_of_bounds_seed():
    buf = _new(2, 2)
    assert drawing.flood_fill(buf, 5, 5, RED) == []


def test_flood_fill_indexed():
    buf = PixelBuffer(3, 3, ColorMode.INDEXED, fill=1)
    coords = drawing.flood_fill(buf, 1, 1, 2)
    assert len(coords) == 9
    assert buf.get_pixel(0, 0) == 2


def test_flood_fill_tolerance_rgba():
    buf = _new(3, 1, fill=(100, 100, 100, 255))
    buf.set_pixel(1, 0, (105, 100, 100, 255))  # near-match
    buf.set_pixel(2, 0, (255, 0, 0, 255))  # far
    coords = drawing.flood_fill(buf, 0, 0, GREEN, tolerance=10)
    assert (1, 0) in coords and (2, 0) not in coords


def test_matches_type_mismatch_returns_false():
    assert drawing._matches(1, (1, 2, 3, 4), 0) is False
