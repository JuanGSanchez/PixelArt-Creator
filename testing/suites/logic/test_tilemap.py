"""Tests for pixelart_creator.logic.tilemap (REQ-P6-LOGIC-005..013).

Covers the canonical uint32 GID cell layout + flag round-trip (SC-L005), linked
instances and source-tile propagation (SC-L006), reversible stamp/erase/fill and
layer ops (SC-L007/-008), infinite-sparse addressing (SC-L009), deterministic +
reversible auto-tiling (SC-L010/-011), all-mutations-do/undo (SC-L012), and the
non-destructive resolve+composite render (SC-L013). Zero Qt; deterministic.
Includes the GID flag-nibble round-trip and auto-tile apply-undo identity
Hypothesis properties.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    FLIPPED_DIAGONALLY_FLAG,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    GID_MASK,
    ROTATED_HEXAGONAL_120_FLAG,
    TileInstance,
    Tilemap,
    TilemapError,
    TilemapLayer,
    _apply_flip,
)
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)


def _two_tile_source() -> PixelBuffer:
    """A 32x16 RGBA source: tile 0 red, tile 1 blue."""
    src = PixelBuffer(32, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, RED)
    src.fill_rect(16, 0, 16, 16, BLUE)
    return src


def _map_with_tileset(**ts_kwargs) -> tuple[Tilemap, Tileset]:
    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16, **ts_kwargs)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    return tm, ts


def _valid_ruleset(terrain: int = 1) -> AutotileRuleset:
    return AutotileRuleset(terrain, list(range(1, 1 + BLOB_TILE_COUNT)))


# --------------------------------------------------------------------------- #
# Canonical GID cell layout + TileInstance                                    #
# --------------------------------------------------------------------------- #


def test_gid_masks_match_tiled_1_12_2():
    assert FLIPPED_HORIZONTALLY_FLAG == 0x80000000
    assert FLIPPED_VERTICALLY_FLAG == 0x40000000
    assert FLIPPED_DIAGONALLY_FLAG == 0x20000000
    assert ROTATED_HEXAGONAL_120_FLAG == 0x10000000
    assert GID_MASK == 0x0FFFFFFF


def test_sc_l005_1_tile_instance_reports_base_id_and_flips():
    gid = 5 | FLIPPED_HORIZONTALLY_FLAG | FLIPPED_DIAGONALLY_FLAG
    inst = TileInstance(gid)
    assert inst.base_gid == 5
    assert inst.flip_h is True
    assert inst.flip_v is False
    assert inst.flip_d is True
    assert TileInstance(0).base_gid == 0  # empty (Tiled gid 0)


# --------------------------------------------------------------------------- #
# TilemapLayer + Tilemap construction/validation                              #
# --------------------------------------------------------------------------- #


def test_layer_state_and_opacity_validation():
    layer = TilemapLayer("Ground", visible=False, opacity=0.5)
    assert layer.name == "Ground" and layer.visible is False and layer.opacity == 0.5
    layer.opacity = 1.0
    assert layer.opacity == 1.0
    for bad in (-0.1, 1.1, "x", True):
        with pytest.raises(TilemapError):
            layer.opacity = bad


@pytest.mark.parametrize("bad", [123, None])
def test_layer_rejects_non_string_name(bad):
    with pytest.raises(TilemapError):
        TilemapLayer(bad)


def test_layer_rejects_bad_autotile():
    with pytest.raises(TilemapError):
        TilemapLayer("L", autotile=object())


def test_tilemap_construction_validation():
    with pytest.raises(TilemapError):
        Tilemap(name=123)
    with pytest.raises(TilemapError):
        Tilemap(tile_width=0)
    with pytest.raises(TilemapError):
        Tilemap(tile_height=True)


# --------------------------------------------------------------------------- #
# resolve — global gid space                                                  #
# --------------------------------------------------------------------------- #


def test_resolve_picks_owning_tileset():
    tm, ts = _map_with_tileset(first_gid=1)
    ts2 = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=5)
    tm.tilesets.append(ts2)
    assert tm.resolve(2) == (ts, 1)
    assert tm.resolve(6) == (ts2, 1)


def test_resolve_strips_flags_before_lookup():
    tm, ts = _map_with_tileset(first_gid=1)
    gid = 2 | FLIPPED_HORIZONTALLY_FLAG | FLIPPED_DIAGONALLY_FLAG
    assert tm.resolve(gid) == (ts, 1)


@pytest.mark.parametrize("bad", [0, True, "x"])
def test_resolve_rejects_empty_or_non_int(bad):
    tm, _ = _map_with_tileset()
    with pytest.raises(TilemapError):
        tm.resolve(bad)


def test_resolve_unknown_gid_raises():
    tm, _ = _map_with_tileset()
    with pytest.raises(TilemapError):
        tm.resolve(9999)


# --------------------------------------------------------------------------- #
# SC-L007 — reversible stamp / erase / fill                                   #
# --------------------------------------------------------------------------- #


def test_sc_l007_1_stamp_is_reversible_and_stores_gid_plus_flip():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    gid = 2 | FLIPPED_HORIZONTALLY_FLAG
    cmd = tm.make_stamp_command(0, 2, 3, gid)
    cmd.execute()
    assert tm.layers[0].get(2, 3) == gid
    inst = tm.layers[0].instance(2, 3)
    assert inst.base_gid == 2 and inst.flip_h is True
    cmd.undo()
    assert tm.layers[0].get(2, 3) == 0


def test_sc_l007_1_erase_and_fill_reversible():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1).execute()

    erase = tm.make_erase_command(0, 0, 0)
    erase.execute()
    assert tm.layers[0].get(0, 0) == 0
    erase.undo()
    assert tm.layers[0].get(0, 0) == 1

    fill = tm.make_fill_rect_command(0, 1, 1, 2, 2, 2)
    fill.execute()
    assert [tm.layers[0].get(x, y) for y in (1, 2) for x in (1, 2)] == [2, 2, 2, 2]
    fill.undo()
    assert all(tm.layers[0].get(x, y) == 0 for y in (1, 2) for x in (1, 2))


def test_sc_l007_2_stamp_unknown_gid_rejected():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    with pytest.raises(TilemapError):
        tm.make_stamp_command(0, 0, 0, 9999)


def test_empty_gid_stamp_allowed_and_clears():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 0).execute()  # base 0 = empty, no resolve
    assert tm.layers[0].get(0, 0) == 0


def test_fill_rejects_bad_size_and_layer():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    with pytest.raises(TilemapError):
        tm.make_fill_rect_command(0, 0, 0, 0, 2, 1)
    with pytest.raises(TilemapError):
        tm.make_fill_rect_command(0, 0, 0, 2, -1, 1)
    with pytest.raises(TilemapError):
        tm.make_stamp_command(5, 0, 0, 1)  # bad layer index


def test_coord_out_of_range_rejected():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    with pytest.raises(TilemapError):
        tm.make_stamp_command(0, constants.MAX_TILEMAP_COORD + 1, 0, 1)
    with pytest.raises(TilemapError):
        tm.layers[0].get(constants.MAX_TILEMAP_COORD + 1, 0)


# --------------------------------------------------------------------------- #
# SC-L009 — infinite / sparse addressing                                      #
# --------------------------------------------------------------------------- #


def test_sc_l009_1_arbitrary_negative_coords_sparse():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, -1000, 5000, 1).execute()
    assert tm.layers[0].get(-1000, 5000) == 1
    assert tm.layers[0].get(0, 0) == 0  # unset reads empty
    # Erasing the only cell drops the chunk (empty region costs nothing).
    tm.make_erase_command(0, -1000, 5000).execute()
    assert list(tm.layers[0].cells()) == []


# --------------------------------------------------------------------------- #
# SC-L008 — reversible layer ops                                              #
# --------------------------------------------------------------------------- #


def test_sc_l008_1_layer_add_remove_reorder_visibility_reversible():
    tm, _ = _map_with_tileset()
    add_a = tm.make_add_layer_command(name="A")
    add_a.execute()
    add_b = tm.make_add_layer_command(name="B")
    add_b.execute()
    assert [layer.name for layer in tm.layers] == ["A", "B"]

    move = tm.make_move_layer_command(0, 1)
    move.execute()
    assert [layer.name for layer in tm.layers] == ["B", "A"]
    move.undo()
    assert [layer.name for layer in tm.layers] == ["A", "B"]

    vis = tm.make_set_layer_visibility_command(0, False)
    vis.execute()
    assert tm.layers[0].visible is False
    vis.undo()
    assert tm.layers[0].visible is True

    remove = tm.make_remove_layer_command(0)
    remove.execute()
    assert [layer.name for layer in tm.layers] == ["B"]
    remove.undo()
    assert [layer.name for layer in tm.layers] == ["A", "B"]


def test_add_layer_at_index():
    tm, _ = _map_with_tileset()
    tm.make_add_layer_command(name="A").execute()
    cmd = tm.make_add_layer_command(name="mid", at=0)
    cmd.execute()
    assert [layer.name for layer in tm.layers] == ["mid", "A"]
    cmd.undo()
    assert [layer.name for layer in tm.layers] == ["A"]


def test_add_layer_over_max_raises(monkeypatch):
    tm, _ = _map_with_tileset()
    # Fill to the cap without allocating 256 real layers by shrinking the bound.
    monkeypatch.setattr("pixelart_creator.logic.tilemap.MAX_TILEMAP_LAYERS", 1)
    tm.make_add_layer_command().execute()
    with pytest.raises(TilemapError):
        tm.make_add_layer_command()


def test_add_layer_bad_index_and_move_out_of_range():
    tm, _ = _map_with_tileset()
    tm.make_add_layer_command().execute()
    with pytest.raises(TilemapError):
        tm.make_add_layer_command(at=99)
    with pytest.raises(TilemapError):
        tm.make_move_layer_command(0, 99)


def test_attach_tileset_command_reversible():
    tm = Tilemap(tile_width=16, tile_height=16)
    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16)
    cmd = tm.make_attach_tileset_command(ts)
    cmd.execute()
    assert tm.tilesets == [ts]
    cmd.undo()
    assert tm.tilesets == []
    with pytest.raises(TilemapError):
        tm.make_attach_tileset_command(object())


# --------------------------------------------------------------------------- #
# SC-L010 / SC-L011 — auto-tiling determinism + reversibility                 #
# --------------------------------------------------------------------------- #


def test_sc_l010_1_autotile_deterministic_and_neighbour_dependent():
    tm, _ = _map_with_tileset()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers.append(layer)
    tm.make_stamp_command(0, 5, 5, 1).execute()
    display_solo = layer.get(5, 5)
    # Deterministic: an identical placement resolves to the same display gid.
    tm2, _ = _map_with_tileset()
    layer2 = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm2.layers.append(layer2)
    tm2.make_stamp_command(0, 5, 5, 1).execute()
    assert layer2.get(5, 5) == display_solo
    # Adding an edge-adjacent neighbour changes the resolved display gid.
    tm.make_stamp_command(0, 6, 5, 1).execute()
    assert layer.get(5, 5) != display_solo


def test_autotile_logical_placement_gid_must_be_terrain_or_empty():
    tm, _ = _map_with_tileset()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(terrain=1))
    tm.layers.append(layer)
    # gid 2 (resolvable) is not the terrain gid -> rejected at command build.
    with pytest.raises(TilemapError):
        tm.make_stamp_command(0, 0, 0, 2)


def test_sc_l011_1_autotile_stamp_undo_restores_logical_and_display():
    tm, _ = _map_with_tileset()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers.append(layer)
    tm.make_stamp_command(0, 5, 5, 1).execute()  # a pre-existing neighbour context
    before_logical = {
        (x, y): layer.get_logical(x, y) for x in range(3, 9) for y in range(3, 9)
    }
    before_display = {(x, y): layer.get(x, y) for x in range(3, 9) for y in range(3, 9)}
    cmd = tm.make_stamp_command(0, 6, 5, 1)
    cmd.execute()
    assert layer.get_logical(6, 5) == 1
    cmd.undo()
    after_logical = {
        (x, y): layer.get_logical(x, y) for x in range(3, 9) for y in range(3, 9)
    }
    after_display = {(x, y): layer.get(x, y) for x in range(3, 9) for y in range(3, 9)}
    assert after_logical == before_logical
    assert after_display == before_display


def test_get_logical_mirrors_display_on_literal_layer():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 1, 1, 2).execute()
    assert tm.layers[0].get_logical(1, 1) == 2


# --------------------------------------------------------------------------- #
# _apply_flip — transform order diag -> H -> V                                #
# --------------------------------------------------------------------------- #


def test_apply_flip_order_is_diag_then_h_then_v():
    data = np.array([[[0], [1]], [[2], [3]]], dtype=np.uint8)  # (2,2,1): a b / c d
    # diag (swapaxes) then H: [[a,c],[b,d]] -> [[c,a],[d,b]]
    out = _apply_flip(data, flip_h=True, flip_v=False, flip_d=True)
    assert out[:, :, 0].tolist() == [[2, 0], [3, 1]]
    # identity
    same = _apply_flip(data, flip_h=False, flip_v=False, flip_d=False)
    assert np.array_equal(same, data)
    # vertical only
    v = _apply_flip(data, flip_h=False, flip_v=True, flip_d=False)
    assert v[:, :, 0].tolist() == [[2, 3], [0, 1]]


# --------------------------------------------------------------------------- #
# SC-L013 — render resolves instances + composites, non-destructively         #
# --------------------------------------------------------------------------- #


def test_sc_l013_1_render_resolves_instances_and_composites():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("bg"))
    tm.make_stamp_command(0, 0, 0, 1).execute()  # red tile
    tm.make_stamp_command(0, 1, 0, 2).execute()  # blue tile
    out = tm.render_region(0, 0, 32, 16)
    assert out.width == 32 and out.height == 16
    assert out.get_pixel(0, 0) == RED
    assert out.get_pixel(16, 0) == BLUE


def test_render_applies_flip_orientation():
    # A tile whose left half is red, right half green; a H-flip swaps them.
    src = PixelBuffer(16, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 8, 16, RED)
    src.fill_rect(8, 0, 8, 16, GREEN)
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1 | FLIPPED_HORIZONTALLY_FLAG).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(0, 0) == GREEN  # right half is now on the left
    assert out.get_pixel(15, 0) == RED


def test_render_is_non_destructive():
    tm, ts = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    source_before = ts.source.data.copy()
    cell_before = tm.layers[0].get(0, 0)
    tm.render_region(0, 0, 16, 16)
    assert np.array_equal(ts.source.data, source_before)
    assert tm.layers[0].get(0, 0) == cell_before


def test_render_hidden_layer_skipped():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L", visible=False))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    out = tm.render_region(0, 0, 16, 16)
    assert out.get_pixel(0, 0) == (0, 0, 0, 0)  # nothing composited


def test_render_indexed_source_rejected():
    src = PixelBuffer(32, 16, ColorMode.INDEXED)
    ts = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    with pytest.raises(TilemapError):
        tm.render_region(0, 0, 16, 16)


def test_render_region_size_validation():
    tm, _ = _map_with_tileset()
    with pytest.raises(TilemapError):
        tm.render_region(0, 0, 0, 16)
    with pytest.raises(TilemapError):
        tm.render_region(0, 0, constants.MAX_CANVAS_WIDTH + 1, 16)


def test_repr_reports_counts():
    tm, _ = _map_with_tileset()
    tm.layers.append(TilemapLayer("L"))
    assert "1 layers" in repr(tm) and "1 tilesets" in repr(tm)


# --------------------------------------------------------------------------- #
# Property — GID flag-nibble round-trip                                       #
# --------------------------------------------------------------------------- #


@given(
    local_id=st.integers(min_value=0, max_value=GID_MASK),
    flip_h=st.booleans(),
    flip_v=st.booleans(),
    flip_d=st.booleans(),
    hexrot=st.booleans(),
)
def test_property_gid_flag_roundtrip(local_id, flip_h, flip_v, flip_d, hexrot):
    gid = local_id
    if flip_h:
        gid |= FLIPPED_HORIZONTALLY_FLAG
    if flip_v:
        gid |= FLIPPED_VERTICALLY_FLAG
    if flip_d:
        gid |= FLIPPED_DIAGONALLY_FLAG
    if hexrot:
        gid |= ROTATED_HEXAGONAL_120_FLAG
    inst = TileInstance(gid)
    assert inst.base_gid == local_id
    assert inst.flip_h == flip_h
    assert inst.flip_v == flip_v
    assert inst.flip_d == flip_d
    # A cell store preserves the full 32-bit gid verbatim (incl. hex-rot bit).
    tm = Tilemap(tile_width=16, tile_height=16)
    layer = TilemapLayer("L")
    layer._display.set(3, 4, gid)
    assert layer.get(3, 4) == gid


# --------------------------------------------------------------------------- #
# Property — auto-tile apply o undo == identity                               #
# --------------------------------------------------------------------------- #


@given(
    ops=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=4),
            st.integers(min_value=0, max_value=4),
            st.sampled_from([0, 1]),  # erase (0) or stamp terrain (1)
        ),
        min_size=1,
        max_size=8,
    )
)
def test_property_autotile_command_apply_undo_identity(ops):
    tm, _ = _map_with_tileset()
    layer = TilemapLayer("auto", autotile=_valid_ruleset(1))
    tm.layers.append(layer)

    def snapshot():
        cells = range(-1, 6)
        return (
            {(x, y): layer.get_logical(x, y) for x in cells for y in cells},
            {(x, y): layer.get(x, y) for x in cells for y in cells},
        )

    for x, y, kind in ops:
        before = snapshot()
        cmd = (
            tm.make_stamp_command(0, x, y, 1)
            if kind == 1
            else tm.make_erase_command(0, x, y)
        )
        cmd.execute()
        cmd.undo()
        # apply o undo restores logical AND display planes (incl. 8 neighbours).
        assert snapshot() == before
        cmd.execute()  # keep the change to build a non-trivial neighbourhood
