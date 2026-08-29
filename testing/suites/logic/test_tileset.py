"""Tests for pixelart_creator.logic.tileset (REQ-P6-LOGIC-001..004, -014).

A Tileset slices a source PixelBuffer into a deterministic row-major grid of
tiles (SC-L001..SC-L003), derives each tile's pixels from the *current* source
via PixelBuffer.region so a source-tile edit is seen by every reader
(SC-L002/SC-L004), and enforces the constants-sourced bounds (SC-L014). Zero Qt;
deterministic. Includes a Hypothesis slicing-invariant property.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import TileRegion, Tileset, TilesetError

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _source(w: int = 64, h: int = 32, mode: ColorMode = ColorMode.RGBA) -> PixelBuffer:
    return PixelBuffer(w, h, mode)


# --------------------------------------------------------------------------- #
# SC-L001 — deterministic slice grid + invalid params                         #
# --------------------------------------------------------------------------- #


def test_sc_l001_1_slices_into_deterministic_grid():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16)
    assert (ts.columns, ts.rows, ts.tile_count) == (4, 2, 8)
    # Re-slicing the identical inputs yields the identical grid.
    again = Tileset(_source(64, 32), tile_width=16, tile_height=16)
    assert [ts.region_of(i) for i in range(ts.tile_count)] == [
        again.region_of(i) for i in range(again.tile_count)
    ]


def test_slice_honours_margin_and_spacing():
    # 2 tiles of 16 with margin 2, spacing 4: 2 + 16 + 4 + 16 = 38 <= 40 fits 2.
    ts = Tileset(_source(40, 40), tile_width=16, tile_height=16, margin=2, spacing=4)
    assert ts.columns == 2 and ts.rows == 2
    assert ts.region_of(0) == TileRegion(2, 2, 16, 16)
    assert ts.region_of(1) == TileRegion(22, 2, 16, 16)  # 2 + 16 + 4
    assert ts.region_of(2) == TileRegion(2, 22, 16, 16)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tile_width": 0},
        {"tile_width": -1},
        {"tile_height": 0},
        {"tile_width": constants.MAX_TILE_DIMENSION + 1},
        {"tile_width": True},
        {"margin": -1},
        {"spacing": -1},
        {"first_gid": 0},
        {"first_gid": True},
    ],
)
def test_sc_l001_2_invalid_slicing_params_rejected(kwargs):
    with pytest.raises(TilesetError):
        Tileset(_source(), **kwargs)


def test_non_pixelbuffer_source_rejected():
    with pytest.raises(TilesetError):
        Tileset(object())  # type: ignore[arg-type]


def test_non_string_name_rejected():
    with pytest.raises(TilesetError):
        Tileset(_source(), name=123)  # type: ignore[arg-type]


def test_sc_l014_1_tile_count_over_max_is_rejected():
    # 257x257 at 1px tiles = 66049 tiles > MAX_TILESET_TILES (65536).
    assert 257 * 257 > constants.MAX_TILESET_TILES
    with pytest.raises(TilesetError):
        Tileset(_source(257, 257), tile_width=1, tile_height=1)


def test_sc_l014_2_defaults_from_constants_distinct_from_tile_size():
    ts = Tileset(_source())
    assert ts.tile_width == constants.DEFAULT_TILE_WIDTH == 16
    assert ts.tile_height == constants.DEFAULT_TILE_HEIGHT == 16
    assert ts.margin == constants.DEFAULT_TILE_MARGIN == 0
    assert ts.spacing == constants.DEFAULT_TILE_SPACING == 0
    # The tileset tile dimension is NOT the viewport-cull TILE_SIZE (64) (BF-2).
    assert ts.tile_width != constants.TILE_SIZE


# --------------------------------------------------------------------------- #
# SC-L002 / SC-L003 — id <-> region + pixel derivation                        #
# --------------------------------------------------------------------------- #


def test_sc_l003_1_ids_are_row_major_and_region_is_total():
    ts = Tileset(_source(48, 32), tile_width=16, tile_height=16)  # 3x2 = 6
    # Row-major left-to-right, top-to-bottom.
    assert ts.region_of(0) == TileRegion(0, 0, 16, 16)
    assert ts.region_of(1) == TileRegion(16, 0, 16, 16)
    assert ts.region_of(2) == TileRegion(32, 0, 16, 16)
    assert ts.region_of(3) == TileRegion(0, 16, 16, 16)
    # Total + repeatable over the valid range.
    assert [ts.region_of(i) for i in range(6)] == [ts.region_of(i) for i in range(6)]


@pytest.mark.parametrize("bad", [-1, 8, 100, True, 1.5])
def test_region_of_rejects_out_of_range_id(bad):
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16)  # 8 tiles
    with pytest.raises(TilesetError):
        ts.region_of(bad)


def test_sc_l002_1_tile_pixels_derive_from_source_region_and_inherit_mode():
    src = _source(64, 32)
    src.set_pixel(16, 0, RED)  # top-left pixel of tile id 1
    ts = Tileset(src, tile_width=16, tile_height=16)
    tile = ts.tile_pixels(1)
    assert tile.width == 16 and tile.height == 16
    assert tile.mode is ColorMode.RGBA
    # Equals PixelBuffer.region of that id's rectangle.
    region = src.region(16, 0, 16, 16)
    assert np.array_equal(tile.data, region.data)
    assert tile.get_pixel(0, 0) == RED


def test_tile_pixels_inherit_indexed_mode():
    ts = Tileset(_source(32, 16, ColorMode.INDEXED), tile_width=16, tile_height=16)
    assert ts.mode is ColorMode.INDEXED
    assert ts.tile_pixels(0).mode is ColorMode.INDEXED


# --------------------------------------------------------------------------- #
# SC-L003-2 — global gid space                                                #
# --------------------------------------------------------------------------- #


def test_global_gid_space_first_gid_offset():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16, first_gid=5)  # 8 tiles
    assert ts.first_gid == 5
    assert ts.contains_gid(5) and ts.contains_gid(12)
    assert not ts.contains_gid(4) and not ts.contains_gid(13)
    assert ts.local_id_for_gid(5) == 0
    assert ts.local_id_for_gid(12) == 7


def test_contains_gid_rejects_non_int_gracefully():
    ts = Tileset(_source(), first_gid=1)
    assert ts.contains_gid(True) is False
    assert ts.contains_gid("x") is False  # type: ignore[arg-type]


def test_local_id_for_foreign_gid_raises():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16, first_gid=1)
    with pytest.raises(TilesetError):
        ts.local_id_for_gid(9999)


def test_repr_reports_geometry():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16, name="Grass")
    text = repr(ts)
    assert "Grass" in text and "4x2" in text


# --------------------------------------------------------------------------- #
# SC-L004 — reversible source-tile edit, seen by all readers                  #
# --------------------------------------------------------------------------- #


def test_sc_l004_1_edit_tile_is_reversible_and_seen_by_all_readers():
    src = _source(64, 32, ColorMode.RGBA)
    src.fill(RED)
    ts = Tileset(src, tile_width=16, tile_height=16)
    before = ts.tile_pixels(2).get_pixel(0, 0)
    assert before == RED

    edited = PixelBuffer(16, 16, ColorMode.RGBA, fill=BLUE)
    cmd = ts.make_edit_tile_command(2, edited)
    cmd.execute()
    # Every reader of tile id 2 now sees blue (derived from the live source).
    assert ts.tile_pixels(2).get_pixel(0, 0) == BLUE
    assert ts.tile_pixels(2).get_pixel(15, 15) == BLUE

    cmd.undo()
    assert ts.tile_pixels(2).get_pixel(0, 0) == RED


def test_edit_tile_rejects_wrong_geometry_and_mode():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16)
    with pytest.raises(TilesetError):
        ts.make_edit_tile_command(0, PixelBuffer(8, 8, ColorMode.RGBA))
    with pytest.raises(TilesetError):
        ts.make_edit_tile_command(0, PixelBuffer(16, 16, ColorMode.INDEXED))
    with pytest.raises(TilesetError):
        ts.make_edit_tile_command(0, object())  # type: ignore[arg-type]


def test_reslice_command_is_reversible():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16)  # 8 tiles
    cmd = ts.make_reslice_command(tile_width=32, tile_height=32, margin=0, spacing=0)
    cmd.execute()
    assert (ts.tile_width, ts.tile_height) == (32, 32)
    assert (ts.columns, ts.rows) == (2, 1)
    cmd.undo()
    assert (ts.tile_width, ts.tile_height) == (16, 16)
    assert ts.tile_count == 8


def test_reslice_command_rejects_invalid_params():
    ts = Tileset(_source(64, 32), tile_width=16, tile_height=16)
    with pytest.raises(TilesetError):
        ts.make_reslice_command(tile_width=0, tile_height=16, margin=0, spacing=0)


# --------------------------------------------------------------------------- #
# Property — slicing determinism / row-major invariants                        #
# --------------------------------------------------------------------------- #


@given(
    width=st.integers(min_value=1, max_value=128),
    height=st.integers(min_value=1, max_value=128),
    tile=st.integers(min_value=1, max_value=32),
    margin=st.integers(min_value=0, max_value=8),
    spacing=st.integers(min_value=0, max_value=8),
)
def test_property_slice_grid_matches_independent_formula(
    width, height, tile, margin, spacing
):
    ts = Tileset(
        PixelBuffer(width, height),
        tile_width=tile,
        tile_height=tile,
        margin=margin,
        spacing=spacing,
    )

    def count(extent: int) -> int:
        usable = extent - margin + spacing
        return max(0, usable // (tile + spacing)) if usable > 0 else 0

    assert ts.columns == count(width)
    assert ts.rows == count(height)
    # Every valid id maps to an in-bounds, non-negative region, repeatably.
    for i in range(ts.tile_count):
        r = ts.region_of(i)
        assert r.x >= 0 and r.y >= 0
        assert r.x + r.width <= width and r.y + r.height <= height
        assert ts.region_of(i) == r
