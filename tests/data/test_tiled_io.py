"""Tests for pixelart_creator.data.tiled_io (REQ-P6-DATA-001..003, ADR-0014).

Tiled 1.12.2 JSON export + lossless import: a valid Tiled map object (SC-D001),
export->import round-trip identity across CSV and base64 none/gzip/zlib
(SC-D002), unknown-field verbatim passthrough, and the defensive load that
rejects zstd, external .tsx, non-orthogonal orientation and out-of-range gids
(SC-D003). Zero Qt; deterministic. Includes a Hypothesis round-trip property.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.tiled_io import (
    export_tilemap,
    import_tilemap,
    read_tiled_json,
    write_tiled_json,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    FLIPPED_DIAGONALLY_FLAG,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    Tilemap,
    TilemapLayer,
)
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)

_ENCODINGS = [("csv", None), ("base64", None), ("base64", "gzip"), ("base64", "zlib")]


def _two_tile_source() -> PixelBuffer:
    src = PixelBuffer(32, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, RED)
    src.fill_rect(16, 0, 16, 16, BLUE)
    return src


def _build_tilemap(infinite: bool = True) -> Tilemap:
    ts1 = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=1)
    ts2 = Tileset(
        PixelBuffer(16, 16, ColorMode.RGBA), tile_width=16, tile_height=16, first_gid=3
    )
    tm = Tilemap(name="M", infinite=infinite, tile_width=16, tile_height=16)
    tm.tilesets.extend([ts1, ts2])
    tm.layers.append(TilemapLayer("ground"))
    tm.layers.append(TilemapLayer("decor", visible=False, opacity=0.5))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2 | FLIPPED_HORIZONTALLY_FLAG).execute()
    tm.make_stamp_command(0, 2, 1, 2 | FLIPPED_DIAGONALLY_FLAG).execute()
    tm.make_stamp_command(1, 3, 4, 3 | FLIPPED_VERTICALLY_FLAG).execute()
    return tm


def _cells(tm: Tilemap):
    return [sorted(layer.cells()) for layer in tm.layers]


def _meta(tm: Tilemap):
    return [(layer.name, layer.visible, layer.opacity) for layer in tm.layers]


def _tsmap(tm: Tilemap):
    return [(t.first_gid, t.tile_count, t.name) for t in tm.tilesets]


def _minimal_map() -> dict:
    return {
        "type": "map",
        "version": "1.10",
        "tiledversion": "1.12.2",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "infinite": False,
        "tilewidth": 16,
        "tileheight": 16,
        "width": 2,
        "height": 1,
        "tilesets": [
            {
                "firstgid": 1,
                "name": "ts",
                "tilewidth": 16,
                "tileheight": 16,
                "imagewidth": 32,
                "imageheight": 16,
                "margin": 0,
                "spacing": 0,
            }
        ],
        "layers": [
            {
                "type": "tilelayer",
                "id": 1,
                "name": "L",
                "width": 2,
                "height": 1,
                "x": 0,
                "y": 0,
                "opacity": 1.0,
                "visible": True,
                "encoding": "csv",
                "data": [1, 2],
            }
        ],
        "nextlayerid": 2,
        "nextobjectid": 1,
    }


# --------------------------------------------------------------------------- #
# SC-D001 — valid Tiled map export                                            #
# --------------------------------------------------------------------------- #


def test_sc_d001_1_export_is_a_valid_tiled_map():
    data = export_tilemap(_build_tilemap())
    assert data["type"] == "map"
    assert data["orientation"] == "orthogonal"
    assert data["renderorder"] == "right-down"
    assert data["infinite"] is True
    assert data["tilewidth"] == 16 and data["tileheight"] == 16
    assert data["tilesets"][0]["firstgid"] == 1
    assert data["tilesets"][1]["firstgid"] == 3
    assert len(data["layers"]) == 2
    assert data["layers"][0]["type"] == "tilelayer"


def test_export_fixed_map_uses_dense_data_block():
    data = export_tilemap(_build_tilemap(infinite=False))
    layer = data["layers"][0]
    assert "data" in layer and "chunks" not in layer


@pytest.mark.parametrize(
    "encoding,compression",
    [("zip", None), ("csv", "gzip"), ("base64", "zstd"), ("base64", "lz4")],
)
def test_export_rejects_bad_encoding_or_compression(encoding, compression):
    with pytest.raises(ProjectIOError):
        export_tilemap(_build_tilemap(), encoding=encoding, compression=compression)


def test_export_rejects_non_tilemap():
    with pytest.raises(ProjectIOError):
        export_tilemap(object())


# --------------------------------------------------------------------------- #
# SC-D002 — lossless round-trip identity                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("encoding,compression", _ENCODINGS)
def test_sc_d002_1_roundtrip_identity_infinite(encoding, compression):
    tm = _build_tilemap(infinite=True)
    data = export_tilemap(tm, encoding=encoding, compression=compression)
    back = import_tilemap(data)
    assert _cells(back) == _cells(tm)
    assert _meta(back) == _meta(tm)
    assert _tsmap(back) == _tsmap(tm)
    assert back.tile_width == tm.tile_width and back.infinite == tm.infinite


@pytest.mark.parametrize("encoding,compression", _ENCODINGS)
def test_roundtrip_identity_fixed(encoding, compression):
    tm = _build_tilemap(infinite=False)
    back = import_tilemap(
        export_tilemap(tm, encoding=encoding, compression=compression)
    )
    assert _cells(back) == _cells(tm)
    assert _meta(back) == _meta(tm)


def test_flip_flags_survive_roundtrip():
    tm = _build_tilemap()
    back = import_tilemap(export_tilemap(tm))
    # The diagonally-flipped cell keeps its full flag nibble.
    inst = back.layers[0].instance(2, 1)
    assert inst.base_gid == 2 and inst.flip_d is True


def test_write_and_read_roundtrip(tmp_path):
    tm = _build_tilemap()
    path = write_tiled_json(
        tmp_path / "map.json", tm, encoding="base64", compression="zlib"
    )
    back = read_tiled_json(path)
    assert _cells(back) == _cells(tm)


# --------------------------------------------------------------------------- #
# C-03 — negative-coordinate cells on a non-infinite map raise ProjectIOError  #
# --------------------------------------------------------------------------- #
# Regression test for C-03 — proven by reversion in the commit pass


def test_export_fixed_map_negative_cell_raises_naming_the_cell():
    """A non-infinite map with a cell at (-1, 0) raises ProjectIOError naming it.

    Before the fix a negative coordinate silently wrapped/aliased into the
    dense grid via numpy negative indexing instead of being rejected.
    """
    tm = Tilemap(name="M", infinite=False, tile_width=16, tile_height=16)
    ts = Tileset(
        PixelBuffer(16, 16, ColorMode.RGBA), tile_width=16, tile_height=16, first_gid=1
    )
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("ground"))
    tm.make_stamp_command(0, -1, 0, 1).execute()
    with pytest.raises(ProjectIOError, match=r"\(-1, 0\)"):
        export_tilemap(tm)


def test_export_infinite_map_negative_cell_still_roundtrips():
    """T-06: the same negative-coordinate cell on an INFINITE map round-trips.

    Infinite maps store per-chunk data (chunk coordinates may be negative), so
    the bound check that rejects fixed maps must not reject infinite ones.
    """
    tm = Tilemap(name="M", infinite=True, tile_width=16, tile_height=16)
    ts = Tileset(
        PixelBuffer(16, 16, ColorMode.RGBA), tile_width=16, tile_height=16, first_gid=1
    )
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("ground"))
    tm.make_stamp_command(0, -1, 0, 1).execute()
    back = import_tilemap(export_tilemap(tm))
    assert _cells(back) == _cells(tm)


# --------------------------------------------------------------------------- #
# Unknown-field verbatim passthrough                                          #
# --------------------------------------------------------------------------- #


def test_unknown_fields_preserved_verbatim():
    raw = export_tilemap(_build_tilemap())
    raw["customTopKey"] = {"foo": 1}
    raw["tilesets"][0]["customTilesetKey"] = "keep-me"
    raw["layers"].append(
        {"type": "objectgroup", "id": 99, "name": "objs", "objects": []}
    )
    imported = import_tilemap(raw)
    assert imported.tiled_passthrough["map_extra"]["customTopKey"] == {"foo": 1}
    re = export_tilemap(imported)
    assert re["customTopKey"] == {"foo": 1}
    assert re["tilesets"][0]["customTilesetKey"] == "keep-me"
    assert any(layer.get("type") == "objectgroup" for layer in re["layers"])


# --------------------------------------------------------------------------- #
# SC-D003 — defensive load                                                    #
# --------------------------------------------------------------------------- #


def test_import_rejects_non_orthogonal_orientation():
    data = _minimal_map()
    data["orientation"] = "isometric"
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_out_of_range_gid():
    data = _minimal_map()
    data["layers"][0]["data"] = [1, 99]  # gid 99 belongs to no tileset
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_zstd_compression():
    data = _minimal_map()
    data["layers"][0]["encoding"] = "base64"
    data["layers"][0]["compression"] = "zstd"
    data["layers"][0]["data"] = "AAAAAA=="
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_external_tsx():
    data = _minimal_map()
    data["tilesets"][0] = {"firstgid": 1, "source": "world.tsx"}
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_unknown_external_extension():
    data = _minimal_map()
    data["tilesets"][0] = {"firstgid": 1, "source": "world.png"}
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_oversized_tileset_image():
    data = _minimal_map()
    data["tilesets"][0]["imagewidth"] = 10_000_000
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_bad_tile_dimension():
    data = _minimal_map()
    data["tilewidth"] = 0
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_bad_opacity():
    data = _minimal_map()
    data["layers"][0]["opacity"] = 2.0
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_wrong_csv_length():
    data = _minimal_map()
    data["layers"][0]["data"] = [1]  # declared 2x1 but only one gid
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_import_rejects_non_dict():
    with pytest.raises(ProjectIOError):
        import_tilemap([1, 2, 3])


def test_external_tsj_without_base_dir_rejected():
    data = _minimal_map()
    data["tilesets"][0] = {"firstgid": 1, "source": "tiles.tsj"}
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


def test_external_tsj_resolved_relative_to_map(tmp_path):
    tsj = {
        "name": "ext",
        "tilewidth": 16,
        "tileheight": 16,
        "imagewidth": 32,
        "imageheight": 16,
        "margin": 0,
        "spacing": 0,
    }
    (tmp_path / "tiles.tsj").write_text(json.dumps(tsj), encoding="utf-8")
    data = _minimal_map()
    data["tilesets"][0] = {"firstgid": 1, "source": "tiles.tsj"}
    (tmp_path / "map.json").write_text(json.dumps(data), encoding="utf-8")
    tm = read_tiled_json(tmp_path / "map.json")
    assert tm.tilesets[0].tile_count == 2


def test_read_tiled_json_malformed_file_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(ProjectIOError):
        read_tiled_json(bad)


def test_read_tiled_json_missing_file_raises(tmp_path):
    with pytest.raises(ProjectIOError):
        read_tiled_json(tmp_path / "nope.json")


def test_import_rejects_corrupt_base64():
    data = _minimal_map()
    data["layers"][0]["encoding"] = "base64"
    data["layers"][0]["data"] = "!!!not-base64!!!"
    with pytest.raises(ProjectIOError):
        import_tilemap(data)


# --------------------------------------------------------------------------- #
# Property — round-trip identity for arbitrary small maps                     #
# --------------------------------------------------------------------------- #

_FLAGS = [
    0,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    FLIPPED_DIAGONALLY_FLAG,
]


@given(
    placements=st.lists(
        st.tuples(
            st.integers(min_value=-4, max_value=4),
            st.integers(min_value=-4, max_value=4),
            st.integers(min_value=1, max_value=2),
            st.sampled_from(_FLAGS),
        ),
        max_size=10,
    ),
    enc=st.sampled_from(_ENCODINGS),
)
def test_property_roundtrip_identity(placements, enc):
    encoding, compression = enc
    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=1)
    tm = Tilemap(infinite=True, tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    tm.layers.append(TilemapLayer("L"))
    for x, y, base, flag in placements:
        tm.make_stamp_command(0, x, y, base | flag).execute()
    back = import_tilemap(
        export_tilemap(tm, encoding=encoding, compression=compression)
    )
    assert _cells(back) == _cells(tm)
