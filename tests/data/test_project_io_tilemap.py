"""Native .pixproj v4 persistence of tilesets + tilemaps (REQ-P6-DATA-004).

FORMAT_VERSION is bumped 3->4 (ADR-0016) and the document's ``tilesets`` /
``tilemaps`` collections round-trip identically — including a literal layer, an
auto-tile layer's logical AND display planes, and its ruleset (SC-D004). v1/v2/v3
projects (no tileset/tilemap fields) still load with empty collections
(back-compat). Defensive parse rejects malformed collections. Zero Qt.
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.logic import constants
from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    FLIPPED_HORIZONTALLY_FLAG,
    Tilemap,
    TilemapLayer,
)
from pixelart_creator.logic.tileset import Tileset

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _two_tile_source() -> PixelBuffer:
    src = PixelBuffer(32, 16, ColorMode.RGBA)
    src.fill_rect(0, 0, 16, 16, RED)
    src.fill_rect(16, 0, 16, 16, BLUE)
    return src


def _ruleset() -> AutotileRuleset:
    return AutotileRuleset(1, list(range(1, 1 + BLOB_TILE_COUNT)))


def _document_with_tilemap() -> Document:
    doc = Document(8, 8)
    ts = Tileset(_two_tile_source(), tile_width=16, tile_height=16, first_gid=1)
    doc.tilesets.append(ts)
    tm = Tilemap(name="World", tile_width=16, tile_height=16)
    tm.tilesets.append(ts)
    # Literal layer.
    tm.layers.append(TilemapLayer("ground", opacity=0.75))
    tm.make_stamp_command(0, 0, 0, 1).execute()
    tm.make_stamp_command(0, 1, 0, 2 | FLIPPED_HORIZONTALLY_FLAG).execute()
    # Auto-tile layer (logical + derived display planes).
    tm.layers.append(TilemapLayer("auto", autotile=_ruleset()))
    tm.make_stamp_command(1, 5, 5, 1).execute()
    tm.make_stamp_command(1, 6, 5, 1).execute()
    doc.tilemaps.append(tm)
    return doc


# --------------------------------------------------------------------------- #
# Version bump                                                                 #
# --------------------------------------------------------------------------- #


def test_format_version_is_4():
    assert pio.FORMAT_VERSION == 4
    assert pio._SUPPORTED_VERSIONS == (1, 2, 3, 4)


# --------------------------------------------------------------------------- #
# SC-D004 — v4 save -> load round-trip identity                               #
# --------------------------------------------------------------------------- #


def test_sc_d004_1_tilesets_and_tilemaps_roundtrip(tmp_path):
    doc = _document_with_tilemap()
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "proj"))

    # Tilesets.
    assert len(loaded.tilesets) == 1
    lts = loaded.tilesets[0]
    assert (lts.first_gid, lts.tile_count) == (1, 2)
    assert np.array_equal(lts.source.data, doc.tilesets[0].source.data)

    # Tilemap geometry + layer stack.
    assert len(loaded.tilemaps) == 1
    ltm = loaded.tilemaps[0]
    assert ltm.name == "World"
    assert [layer.name for layer in ltm.layers] == ["ground", "auto"]

    # Literal layer display cells restored (id + flip).
    assert sorted(ltm.layers[0].cells()) == sorted(doc.tilemaps[0].layers[0].cells())
    assert ltm.layers[0].opacity == 0.75

    # Auto-tile layer: ruleset + logical AND display planes restored.
    auto = ltm.layers[1]
    assert auto.autotile is not None
    assert auto.autotile.terrain_gid == 1
    assert auto.autotile.frame_gids == tuple(range(1, 1 + BLOB_TILE_COUNT))
    src_auto = doc.tilemaps[0].layers[1]
    box = range(3, 9)
    assert {(x, y): auto.get_logical(x, y) for x in box for y in box} == {
        (x, y): src_auto.get_logical(x, y) for x in box for y in box
    }
    assert sorted(auto.cells()) == sorted(src_auto.cells())


def test_tilemap_references_tileset_by_document_index(tmp_path):
    # The tilemap's tileset is the same object attached to the document.
    doc = _document_with_tilemap()
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "p"))
    assert loaded.tilemaps[0].tilesets[0] is loaded.tilesets[0]


# --------------------------------------------------------------------------- #
# Deviation 5 — unattached tileset reference is rejected on serialise         #
# --------------------------------------------------------------------------- #


def test_serialise_rejects_tilemap_with_unattached_tileset():
    doc = Document(8, 8)
    tm = Tilemap(tile_width=16, tile_height=16)
    tm.tilesets.append(Tileset(_two_tile_source(), tile_width=16, tile_height=16))
    doc.tilemaps.append(tm)  # tileset NOT in doc.tilesets
    with pytest.raises(pio.ProjectIOError):
        pio.serialize(doc)


# --------------------------------------------------------------------------- #
# Back-compat — v1/v2/v3 load with empty collections                          #
# --------------------------------------------------------------------------- #


def test_v3_payload_without_collections_loads_empty():
    payload = pio.serialize(Document(4, 4))
    del payload["tilesets"]
    del payload["tilemaps"]
    payload["version"] = 3
    loaded = pio.deserialize(payload)
    assert loaded.tilesets == []
    assert loaded.tilemaps == []


# --------------------------------------------------------------------------- #
# Defensive parse                                                             #
# --------------------------------------------------------------------------- #


def _payload() -> dict:
    return pio.serialize(_document_with_tilemap())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["tilesets"][0].update(mode="bogus"),
        lambda p: p["tilesets"][0].update(source_width=10_000_000),
        lambda p: p["tilesets"][0].update(first_gid=0),
        lambda p: p["tilesets"][0].update(tile_width=0),
        lambda p: p["tilesets"][0].update(margin=-1),
        lambda p: p["tilemaps"][0].update(tilesets=[5]),
        lambda p: p["tilemaps"][0].update(tile_width=0),
        lambda p: p["tilemaps"][0]["layers"][1]["autotile"].update(frame_gids=[1]),
        lambda p: p.update(tilesets="notalist"),
        lambda p: p.update(tilemaps="notalist"),
    ],
)
def test_deserialize_rejects_malformed_collections(mutate):
    payload = _payload()
    mutate(payload)
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_deserialize_rejects_too_many_layers():
    payload = _payload()
    payload["tilemaps"][0]["layers"] = [{"name": "L", "display_chunks": []}] * (
        constants.MAX_TILEMAP_LAYERS + 1
    )
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)
