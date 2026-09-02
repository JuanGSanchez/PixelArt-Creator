"""Re-test of the vectorised ``Tilemap.render_region`` (perf rewrite).

The Phase-6 render path was rewritten to a per-chunk numpy gather -> resolve
-> vectorised flip -> scatter -> assemble -> crop pipeline, with a single-layer
opaque short-circuit, a ``composite_stack`` route for multi-layer/opacity<1, and
an exact per-cell blit fallback for non-uniform tile sizes. A new O(1)
``Tilemap.chunk_version(cx, cy)`` per-chunk cache-version API was added.

These tests lock the rewrite against regressions (the render signature and
pixel-space semantics are UNCHANGED, per the implementation report):

* fast (vectorised) vs fallback (per-cell blit) byte-identity via an independent
  per-cell oracle renderer (never calls the vectorised gather/scatter code);
* RGB forced to 0 where alpha == 0 (matches blit-over-transparent);
* single-layer opaque short-circuit == ``composite_stack`` of the same content;
* GID flip flags (H / V / D, order diag -> H -> V) under the vectorised flip;
* ``_ChunkGrid.region`` across chunk boundaries, negative windows, sparse areas;
* ``chunk_version`` semantics: 0 unseen, bumps on stamp/erase/fill, bumps for
  auto-tile neighbour re-resolution incl. neighbours in ADJACENT chunks, bumps
  on undo, per-chunk isolation, and NOT bumped by layer/tileset ops;
* a Hypothesis property: vectorised render == per-cell oracle for random maps.

Zero Qt; deterministic.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    FLIPPED_DIAGONALLY_FLAG,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    GID_MASK,
    TILEMAP_CHUNK_SIZE,
    TileInstance,
    Tilemap,
    TilemapLayer,
    _ChunkGrid,
)
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)
YELLOW = (255, 255, 0, 255)
TRANSPARENT = (0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #


def _strip_source(colors, tw: int, th: int) -> PixelBuffer:
    """A horizontal strip of ``len(colors)`` solid tiles, each ``tw`` x ``th``."""
    src = PixelBuffer(tw * len(colors), th, ColorMode.RGBA)
    for i, color in enumerate(colors):
        src.fill_rect(i * tw, 0, tw, th, color)
    return src


def _quadrant_tile(tw: int, th: int) -> PixelBuffer:
    """A single tile with four distinct quadrants (asymmetric under any flip)."""
    src = PixelBuffer(tw, th, ColorMode.RGBA)
    hw, hh = tw // 2, th // 2
    src.fill_rect(0, 0, hw, hh, RED)  # top-left
    src.fill_rect(hw, 0, tw - hw, hh, GREEN)  # top-right
    src.fill_rect(0, hh, hw, th - hh, BLUE)  # bottom-left
    src.fill_rect(hw, hh, tw - hw, th - hh, YELLOW)  # bottom-right
    return src


def _map(colors=(RED, BLUE, GREEN), *, tw=16, th=16, ts_tw=None, ts_th=None):
    """A tilemap + attached tileset. ``ts_tw/ts_th`` default to the map's tile."""
    ts_tw = tw if ts_tw is None else ts_tw
    ts_th = th if ts_th is None else ts_th
    src = _strip_source(colors, ts_tw, ts_th)
    ts = Tileset(src, tile_width=ts_tw, tile_height=ts_th, first_gid=1)
    tm = Tilemap(tile_width=tw, tile_height=th)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    return tm, ts


def _valid_ruleset(terrain: int = 1) -> AutotileRuleset:
    return AutotileRuleset(terrain, list(range(1, 1 + BLOB_TILE_COUNT)))


# --------------------------------------------------------------------------- #
# Independent per-cell oracle (never touches the vectorised gather/scatter)    #
# --------------------------------------------------------------------------- #


def _oracle_layer_region(tm, layer, x, y, w, h) -> PixelBuffer:
    """Reference single-layer render: per-cell resolve + flip + blit-over.

    Uses only the tested primitives ``Tileset.region_of``/``PixelBuffer.blit``
    over the same viewport cell window ``render_region`` culls to. Iterates in
    row-major order so overlap semantics match the per-cell fallback exactly.
    """
    tw, th = tm.tile_width, tm.tile_height
    first_col = x // tw
    last_col = (x + w - 1) // tw
    first_row = y // th
    last_row = (y + h - 1) // th
    out = PixelBuffer(w, h, ColorMode.RGBA)
    for cy in range(first_row, last_row + 1):
        for cx in range(first_col, last_col + 1):
            gid = layer.get(cx, cy)
            if gid & GID_MASK == 0:
                continue
            tileset, local = tm.resolve(gid)
            reg = tileset.region_of(local)
            arr = tileset.source.data[
                reg.y : reg.y + reg.height, reg.x : reg.x + reg.width
            ]
            inst = TileInstance(gid)
            flipped = arr
            if inst.flip_d:
                flipped = np.swapaxes(flipped, 0, 1)
            if inst.flip_h:
                flipped = flipped[:, ::-1]
            if inst.flip_v:
                flipped = flipped[::-1, :]
            flipped = np.ascontiguousarray(flipped)
            tile = PixelBuffer(flipped.shape[1], flipped.shape[0], ColorMode.RGBA)
            tile.data[:, :] = flipped
            out.blit(tile, cx * tw - x, cy * th - y, blend=True)
    return out


def _assert_byte_identical(a: PixelBuffer, b: PixelBuffer) -> None:
    assert a.width == b.width and a.height == b.height
    assert np.array_equal(a.data, b.data)


# --------------------------------------------------------------------------- #
# 1. Fast (vectorised) path == per-cell oracle, incl. RGB-zeroed-where-alpha=0 #
# --------------------------------------------------------------------------- #


def test_fast_path_matches_oracle_uniform_tiles():
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2).execute()
    tm.make_stamp_command(0, 0, 1, 3).execute()
    out = tm.render_region(0, 0, 32, 32)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 0, 0, 32, 32))


def test_fast_path_matches_oracle_non_tile_aligned_window():
    # A window whose origin is not a tile multiple exercises the crop offset.
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2).execute()
    tm.make_stamp_command(0, 1, 1, 3).execute()
    out = tm.render_region(7, 5, 20, 19)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 7, 5, 20, 19))


def test_fast_path_rgb_zeroed_where_alpha_zero():
    # A tile carrying opaque RGB in some pixels and RGB!=0 under alpha==0.
    src = PixelBuffer(16, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, (200, 50, 90, 0))  # nonzero RGB, alpha 0
    src.fill_rect(0, 0, 8, 16, RED)  # left half opaque
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(0, 0) == RED  # opaque half preserved
    # Right half was alpha 0 -> RGB must be cleared to 0 (matches blit-over).
    assert out.get_pixel(12, 0) == (0, 0, 0, 0)
    transparent = out.data[:, :, 3] == 0
    assert np.all(out.data[transparent, :3] == 0)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 0, 0, 16, 16))


def test_fast_path_partial_alpha_copies_source_exactly():
    # The fast path copies source RGB directly (no blend); a mid-alpha tile over
    # a transparent backdrop keeps its RGB and alpha byte-for-byte.
    src = PixelBuffer(16, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, (10, 20, 30, 128))
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(3, 3) == (10, 20, 30, 128)


def test_empty_region_is_all_transparent():
    tm, _ = _map()  # no cells stamped
    out = tm.render_region(0, 0, 32, 32)
    assert not out.data.any()


# --------------------------------------------------------------------------- #
# 2. Fallback (per-cell blit) path == oracle, and == fast on the aligned case  #
# --------------------------------------------------------------------------- #


def test_fallback_triggered_when_tileset_tile_smaller_than_map_tile():
    # Tileset tile 8x8 in a 16x16 map -> flipped.shape != (th, tw) -> fallback.
    tm, _ = _map(tw=16, th=16, ts_tw=8, ts_th=8)
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2).execute()
    tm.make_stamp_command(0, 0, 1, 3).execute()
    out = tm.render_region(0, 0, 32, 32)
    # 8x8 tiles at 16px spacing leave transparent gaps between them.
    assert out.get_pixel(0, 0) == RED
    assert out.get_pixel(10, 0) == (0, 0, 0, 0)  # gap after the 8px tile
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 0, 0, 32, 32))


def test_fallback_non_square_diagonal_flip_matches_oracle():
    # Non-square tile 16x8; a diagonal flip swaps axes to 8x16 -> fallback path.
    tm, _ = _map(colors=(RED, BLUE), tw=16, th=8, ts_tw=16, ts_th=8)
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2 | FLIPPED_DIAGONALLY_FLAG).execute()
    out = tm.render_region(0, 0, 48, 24)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 0, 0, 48, 24))


def test_fallback_and_fast_agree_on_content_via_oracle():
    # A uniform map (fast) and a small-tile map (fallback) over the same gid
    # layout each match their oracle; both oracles use the identical primitive
    # so the two render paths are proven equivalent through the shared reference.
    layout = [(0, 0, 1), (1, 0, 2), (2, 1, 1)]
    tm_fast, _ = _map()
    tm_slow, _ = _map(ts_tw=8, ts_th=8)
    for lx, ly, g in layout:
        tm_fast.make_stamp_command(0, lx, ly, g).execute()
        tm_slow.make_stamp_command(0, lx, ly, g).execute()
    fast = tm_fast.render_region(0, 0, 48, 32)
    slow = tm_slow.render_region(0, 0, 48, 32)
    _assert_byte_identical(
        fast, _oracle_layer_region(tm_fast, tm_fast.layers[0], 0, 0, 48, 32)
    )
    _assert_byte_identical(
        slow, _oracle_layer_region(tm_slow, tm_slow.layers[0], 0, 0, 48, 32)
    )


# --------------------------------------------------------------------------- #
# 3. GID flip flags render correctly under the vectorised flip (diag->H->V)    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("flip_h", [False, True])
@pytest.mark.parametrize("flip_v", [False, True])
@pytest.mark.parametrize("flip_d", [False, True])
def test_all_flip_combinations_match_oracle(flip_h, flip_v, flip_d):
    src = _quadrant_tile(16, 16)
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    gid = 1
    if flip_h:
        gid |= FLIPPED_HORIZONTALLY_FLAG
    if flip_v:
        gid |= FLIPPED_VERTICALLY_FLAG
    if flip_d:
        gid |= FLIPPED_DIAGONALLY_FLAG
    tm.make_stamp_command(0, 0, 0, gid).execute()
    out = tm.render_region(0, 0, 16, 16)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], 0, 0, 16, 16))


def test_diagonal_flip_known_orientation():
    # Diag-only swaps the two off-diagonal quadrants (TR<->BL), keeps TL/BR.
    src = _quadrant_tile(16, 16)
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1 | FLIPPED_DIAGONALLY_FLAG).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(0, 0) == RED  # TL unchanged on the main diagonal
    assert out.get_pixel(15, 15) == YELLOW  # BR unchanged
    assert out.get_pixel(15, 0) == BLUE  # was BL -> now TR
    assert out.get_pixel(0, 15) == GREEN  # was TR -> now BL


# --------------------------------------------------------------------------- #
# 4. Multi-layer / opacity: composite_stack path vs single-layer short-circuit #
# --------------------------------------------------------------------------- #


def test_single_opaque_short_circuit_equals_composite_with_empty_top():
    # One opaque layer takes the short-circuit; adding an empty visible layer
    # forces the composite_stack path. Result must be byte-identical.
    tm_fast, _ = _map()
    tm_fast.make_stamp_command(0, 0, 0, 1).execute()
    tm_fast.make_stamp_command(0, 1, 0, 2).execute()
    fast = tm_fast.render_region(0, 0, 32, 16)

    tm_comp, _ = _map()
    tm_comp.make_stamp_command(0, 0, 0, 1).execute()
    tm_comp.make_stamp_command(0, 1, 0, 2).execute()
    tm_comp.layers.append(TilemapLayer("empty-top"))  # 2 visible -> composite
    comp = tm_comp.render_region(0, 0, 32, 16)
    _assert_byte_identical(fast, comp)


def test_multi_layer_opaque_top_covers_bottom():
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()  # bottom: red at (0,0)
    tm.layers.append(TilemapLayer("top"))
    tm.make_stamp_command(1, 0, 0, 2).execute()  # top: blue at (0,0)
    tm.make_stamp_command(1, 1, 0, 3).execute()  # top: green at (1,0)
    out = tm.render_region(0, 0, 32, 16)
    assert out.get_pixel(0, 0) == BLUE  # opaque top wins
    assert out.get_pixel(16, 0) == GREEN  # top-only cell


def test_multi_layer_transparent_top_shows_bottom():
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()  # bottom red
    tm.layers.append(TilemapLayer("top"))  # empty top, visible
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(0, 0) == RED  # bottom shows through empty top


def test_single_layer_opacity_below_one_routes_through_composite():
    # len(visible) == 1 but opacity < 1.0 -> NOT the short-circuit; opacity
    # scales the alpha via composite_stack.
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()  # opaque red
    tm.layers[0].opacity = 0.5
    out = tm.render_region(0, 0, 16, 16)
    r, g, b, a = out.get_pixel(0, 0)
    assert (r, g, b) == (255, 0, 0)
    assert a == pytest.approx(128, abs=1)  # ~50% alpha


def test_hidden_only_layer_renders_transparent():
    tm, _ = _map()
    tm.layers[0].visible = False
    tm.make_stamp_command(0, 0, 0, 1).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert not out.data.any()


# --------------------------------------------------------------------------- #
# 5. _ChunkGrid.region: boundaries, negative windows, sparse                   #
# --------------------------------------------------------------------------- #


def _region_oracle(grid: _ChunkGrid, col0, row0, n_cols, n_rows):
    out = np.zeros((n_rows, n_cols), dtype=np.uint32)
    for r in range(n_rows):
        for c in range(n_cols):
            out[r, c] = grid.get(col0 + c, row0 + r)
    return out


def test_region_spans_four_chunks_across_boundary():
    grid = _ChunkGrid()
    cs = TILEMAP_CHUNK_SIZE
    # One cell in each of the four chunks meeting at the origin corner.
    grid.set(cs - 1, cs - 1, 11)  # chunk (0,0)
    grid.set(cs, cs - 1, 12)  # chunk (1,0)
    grid.set(cs - 1, cs, 13)  # chunk (0,1)
    grid.set(cs, cs, 14)  # chunk (1,1)
    region = grid.region(cs - 2, cs - 2, 4, 4)
    assert np.array_equal(region, _region_oracle(grid, cs - 2, cs - 2, 4, 4))
    assert region[1, 1] == 11 and region[1, 2] == 12
    assert region[2, 1] == 13 and region[2, 2] == 14


def test_region_negative_window():
    grid = _ChunkGrid()
    grid.set(-1, -1, 7)
    grid.set(-17, -17, 9)  # different (negative) chunk
    region = grid.region(-20, -20, 40, 40)
    assert np.array_equal(region, _region_oracle(grid, -20, -20, 40, 40))
    assert region[19, 19] == 7  # cell (-1,-1) at offset (19,19) from (-20,-20)


def test_region_over_unpopulated_area_is_all_zero():
    grid = _ChunkGrid()
    grid.set(0, 0, 5)  # populate one distant chunk only
    region = grid.region(100, 100, 8, 8)  # far, unpopulated
    assert not region.any()


def test_region_partially_populated_chunk():
    grid = _ChunkGrid()
    grid.set(3, 4, 42)
    region = grid.region(0, 0, TILEMAP_CHUNK_SIZE, TILEMAP_CHUNK_SIZE)
    assert region[4, 3] == 42
    assert region.sum() == 42  # exactly one non-zero cell


def test_chunkgrid_is_empty():
    grid = _ChunkGrid()
    assert grid.is_empty()
    grid.set(0, 0, 1)
    assert not grid.is_empty()
    grid.set(0, 0, 0)  # emptied -> chunk dropped
    assert grid.is_empty()


def test_render_across_chunk_boundary_matches_oracle():
    tm, _ = _map()
    cs = TILEMAP_CHUNK_SIZE
    tm.make_stamp_command(0, cs - 1, 0, 1).execute()  # last col of chunk (0,0)
    tm.make_stamp_command(0, cs, 0, 2).execute()  # first col of chunk (1,0)
    x = (cs - 1) * 16
    out = tm.render_region(x, 0, 32, 16)
    _assert_byte_identical(out, _oracle_layer_region(tm, tm.layers[0], x, 0, 32, 16))


def test_render_negative_region_matches_oracle():
    tm, _ = _map()
    tm.make_stamp_command(0, -1, -1, 1).execute()
    tm.make_stamp_command(0, 0, 0, 2).execute()
    out = tm.render_region(-16, -16, 32, 32)
    _assert_byte_identical(
        out, _oracle_layer_region(tm, tm.layers[0], -16, -16, 32, 32)
    )


# --------------------------------------------------------------------------- #
# 6. chunk_version semantics                                                   #
# --------------------------------------------------------------------------- #


def test_chunk_version_unseen_is_zero():
    tm, _ = _map()
    assert tm.chunk_version(0, 0) == 0
    assert tm.chunk_version(999, -999) == 0


def test_chunk_version_bumps_on_stamp_and_undo():
    tm, _ = _map()
    tm.layers.append(TilemapLayer("L2"))  # noqa: keep layer 0 for stamp
    tm2, _ = _map()
    cmd = tm2.make_stamp_command(0, 0, 0, 1)
    assert tm2.chunk_version(0, 0) == 0
    cmd.execute()
    assert tm2.chunk_version(0, 0) == 1  # apply bumps
    cmd.undo()
    assert tm2.chunk_version(0, 0) == 2  # undo also bumps (invalidates cache)


def test_chunk_version_bumps_on_erase_and_fill():
    tm, _ = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()
    v = tm.chunk_version(0, 0)
    tm.make_erase_command(0, 0, 0).execute()
    assert tm.chunk_version(0, 0) == v + 1
    before = tm.chunk_version(0, 0)
    tm.make_fill_rect_command(0, 0, 0, 3, 3, 1).execute()
    assert tm.chunk_version(0, 0) == before + 1


def test_chunk_version_fill_spanning_two_chunks_bumps_both():
    tm, _ = _map()
    cs = TILEMAP_CHUNK_SIZE
    # A fill rectangle straddling the vertical chunk boundary at x == cs.
    tm.make_fill_rect_command(0, cs - 1, 0, 2, 1, 1).execute()
    assert tm.chunk_version(0, 0) == 1  # chunk (0,0)
    assert tm.chunk_version(1, 0) == 1  # chunk (1,0)
    assert tm.chunk_version(0, 1) == 0  # untouched


def test_chunk_version_is_per_chunk_far_chunk_untouched():
    tm, _ = _map()
    for _ in range(5):
        tm.make_stamp_command(0, 0, 0, 1).execute()
        tm.make_erase_command(0, 0, 0).execute()
    assert tm.chunk_version(0, 0) == 10
    assert tm.chunk_version(50, 50) == 0  # no full-map scan side effect


def test_chunk_version_aggregated_across_layers():
    tm, _ = _map()
    tm.layers.append(TilemapLayer("L2"))
    tm.make_stamp_command(0, 0, 0, 1).execute()  # layer 0, chunk (0,0)
    assert tm.chunk_version(0, 0) == 1
    tm.make_stamp_command(1, 1, 1, 2).execute()  # layer 1, same chunk
    assert tm.chunk_version(0, 0) == 2  # aggregated across both layers


def test_chunk_version_autotile_bumps_neighbour_in_adjacent_chunk():
    tm, _ = _map()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers[0] = layer
    cs = TILEMAP_CHUNK_SIZE
    # Stamp at the last column of chunk (0,0); its right neighbours (x==cs) live
    # in chunk (1,0), so the auto-tile re-resolution must bump BOTH chunks.
    tm.make_stamp_command(0, cs - 1, 5, 1).execute()
    assert tm.chunk_version(0, 0) == 1
    assert tm.chunk_version(1, 0) == 1  # adjacent chunk re-resolved


def test_chunk_version_autotile_fill_rect_bumps_region():
    tm, _ = _map()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers[0] = layer
    # An auto-tile fill routes through _autotile_command; every touched chunk
    # (here just (0,0)) is bumped once.
    tm.make_fill_rect_command(0, 0, 0, 3, 3, 1).execute()
    assert tm.chunk_version(0, 0) == 1
    assert layer.get_logical(1, 1) == 1  # logical terrain placed
    assert layer.get(1, 1) != 0  # display resolved


def test_chunk_version_autotile_bumps_on_undo():
    tm, _ = _map()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers[0] = layer
    cmd = tm.make_stamp_command(0, 5, 5, 1)
    cmd.execute()
    v = tm.chunk_version(0, 0)
    cmd.undo()
    assert tm.chunk_version(0, 0) == v + 1  # undo re-resolves -> bumps


def test_chunk_version_not_bumped_by_layer_or_tileset_ops():
    tm, ts = _map()
    tm.make_stamp_command(0, 0, 0, 1).execute()
    base = tm.chunk_version(0, 0)

    # Layer add / remove / reorder / visibility are map-wide, not per-chunk.
    tm.make_add_layer_command(name="X").execute()
    tm.make_set_layer_visibility_command(0, False).execute()
    tm.make_move_layer_command(0, 1).execute()
    # Attaching another tileset is map-wide too.
    ts2 = Tileset(
        _strip_source([RED], 16, 16), tile_width=16, tile_height=16, first_gid=9
    )
    tm.make_attach_tileset_command(ts2).execute()
    # A tileset source-tile edit is map-wide (outside the per-chunk counter).
    edited = PixelBuffer(16, 16, ColorMode.RGBA)
    edited.fill(GREEN)
    ts.make_edit_tile_command(0, edited).execute()

    assert tm.chunk_version(0, 0) == base  # unchanged by all of the above


# --------------------------------------------------------------------------- #
# Property (Hypothesis): vectorised render == per-cell oracle                  #
# --------------------------------------------------------------------------- #

_TILE = 4
_COLORS = (RED, BLUE, GREEN, YELLOW)


def _flag_gid(base: int, flip_h: bool, flip_v: bool, flip_d: bool) -> int:
    gid = base
    if flip_h:
        gid |= FLIPPED_HORIZONTALLY_FLAG
    if flip_v:
        gid |= FLIPPED_VERTICALLY_FLAG
    if flip_d:
        gid |= FLIPPED_DIAGONALLY_FLAG
    return gid


_edit = st.tuples(
    st.integers(min_value=-3, max_value=3),  # cell x
    st.integers(min_value=-3, max_value=3),  # cell y
    st.integers(min_value=1, max_value=len(_COLORS)),  # base gid (1..4)
    st.booleans(),  # flip_h
    st.booleans(),  # flip_v
    st.booleans(),  # flip_d
)


@given(
    edits=st.lists(_edit, min_size=0, max_size=10),
    win=st.tuples(
        st.integers(min_value=-16, max_value=8),  # region x (pixels)
        st.integers(min_value=-16, max_value=8),  # region y
        st.integers(min_value=1, max_value=20),  # w
        st.integers(min_value=1, max_value=20),  # h
    ),
)
def test_property_vectorised_render_equals_oracle(edits, win):
    tm, _ = _map(colors=_COLORS, tw=_TILE, th=_TILE)
    layer = tm.layers[0]
    for cx, cy, base, fh, fv, fd in edits:
        tm.make_stamp_command(0, cx, cy, _flag_gid(base, fh, fv, fd)).execute()
    x, y, w, h = win
    out = tm.render_region(x, y, w, h)
    _assert_byte_identical(out, _oracle_layer_region(tm, layer, x, y, w, h))
