"""Tests for the Phase-6 tileset/tilemap collection on Document (REQ-P6-LOGIC-012).

The Document gains empty ``tilesets`` / ``tilemaps`` collections and four
reversible attach/detach command factories, each a pure do/undo pair usable by
``ui/commands.py``. Zero Qt; deterministic.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.document import Document, DocumentError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.logic.tileset import Tileset


def _tileset() -> Tileset:
    return Tileset(PixelBuffer(32, 16, ColorMode.RGBA), tile_width=16, tile_height=16)


def test_new_document_has_empty_collections():
    doc = Document(4, 4)
    assert doc.tilesets == []
    assert doc.tilemaps == []


def test_add_and_remove_tileset_reversible():
    doc = Document(4, 4)
    ts = _tileset()
    add = doc.make_add_tileset_command(ts)
    add.execute()
    assert doc.tilesets == [ts]
    add.undo()
    assert doc.tilesets == []

    add.execute()
    remove = doc.make_remove_tileset_command(0)
    remove.execute()
    assert doc.tilesets == []
    remove.undo()
    assert doc.tilesets == [ts]


def test_add_and_remove_tilemap_reversible():
    doc = Document(4, 4)
    tm = Tilemap(tile_width=16, tile_height=16)
    add = doc.make_add_tilemap_command(tm)
    add.execute()
    assert doc.tilemaps == [tm]
    add.undo()
    assert doc.tilemaps == []

    add.execute()
    remove = doc.make_remove_tilemap_command(0)
    remove.execute()
    assert doc.tilemaps == []
    remove.undo()
    assert doc.tilemaps == [tm]


def test_add_tileset_rejects_non_tileset():
    doc = Document(4, 4)
    with pytest.raises(DocumentError):
        doc.make_add_tileset_command(object())


def test_add_tilemap_rejects_non_tilemap():
    doc = Document(4, 4)
    with pytest.raises(DocumentError):
        doc.make_add_tilemap_command(object())


def test_remove_tileset_out_of_range_rejected():
    doc = Document(4, 4)
    with pytest.raises(DocumentError):
        doc.make_remove_tileset_command(0)


def test_remove_tilemap_out_of_range_rejected():
    doc = Document(4, 4)
    with pytest.raises(DocumentError):
        doc.make_remove_tilemap_command(5)
