"""Tests for pixelart_creator.logic.document.Document.from_buffer.

Covers the image-import factory (REQ-P7-DATA-002 / REQ-P7-UI-003, plan §5): a
decoded RGBA PixelBuffer becomes a single-frame, single-layer Document sized to
the buffer, seeding the background layer by *identity* (not a copy) so ui/ never
reaches into the layer tree. Maps to Gherkin SC-D002-1 (RGBA buffer -> document
of the image's size) and the contract that a non-RGBA / non-buffer input is
rejected with a DocumentError (defensive, Article VII).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.document import Document, DocumentError, iter_layers
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)


# --------------------------------------------------------------------------- #
# construction (SC-D002-1)                                                    #
# --------------------------------------------------------------------------- #


def test_from_buffer_dimensions_and_mode_match_buffer():
    buffer = PixelBuffer(24, 16, ColorMode.RGBA)
    doc = Document.from_buffer(buffer)
    assert (doc.width, doc.height) == (24, 16)
    assert doc.mode is ColorMode.RGBA


def test_from_buffer_has_single_frame_single_layer():
    doc = Document.from_buffer(PixelBuffer(8, 8, ColorMode.RGBA))
    assert len(doc.frames) == 1
    assert len(doc.frames[0].layers) == 1
    assert len(iter_layers(doc.frames[0].layers)) == 1


def test_from_buffer_seeds_layer_by_identity_not_copy():
    # The background layer's buffer IS the passed buffer (no defensive copy).
    buffer = PixelBuffer(4, 4, ColorMode.RGBA, fill=RED)
    doc = Document.from_buffer(buffer)
    assert doc.frames[0].layers[0].buffer is buffer


def test_from_buffer_default_layer_name():
    doc = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA))
    assert doc.frames[0].layers[0].name == "Imported"


def test_from_buffer_custom_layer_name():
    doc = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA), name="Sprite")
    assert doc.frames[0].layers[0].name == "Sprite"


def test_from_buffer_default_palette_is_empty():
    doc = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA))
    assert isinstance(doc.palette, Palette)
    assert len(doc.palette) == 0


def test_from_buffer_uses_supplied_palette():
    palette = Palette([RED])
    doc = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA), palette=palette)
    assert doc.palette is palette


def test_from_buffer_preserves_pixel_data():
    buffer = PixelBuffer(3, 2, ColorMode.RGBA, fill=RED)
    doc = Document.from_buffer(buffer)
    assert doc.frames[0].layers[0].buffer.get_pixel(0, 0) == RED
    assert doc.frames[0].layers[0].buffer.get_pixel(2, 1) == RED


@pytest.mark.parametrize("w, h", [(1, 1), (100, 1), (1, 100), (64, 48)])
def test_from_buffer_various_dimensions(w, h):
    doc = Document.from_buffer(PixelBuffer(w, h, ColorMode.RGBA))
    assert (doc.width, doc.height) == (w, h)


# --------------------------------------------------------------------------- #
# defensive rejection (Article VII)                                           #
# --------------------------------------------------------------------------- #


def test_from_buffer_rejects_indexed_buffer():
    indexed = PixelBuffer(4, 4, ColorMode.INDEXED)
    with pytest.raises(DocumentError):
        Document.from_buffer(indexed)


@pytest.mark.parametrize("bad", [None, "not a buffer", 42, object(), (4, 4)])
def test_from_buffer_rejects_non_pixelbuffer(bad):
    with pytest.raises(DocumentError):
        Document.from_buffer(bad)


def test_from_buffer_result_is_an_editable_document():
    # The produced document behaves like any other (can add a layer).
    doc = Document.from_buffer(PixelBuffer(4, 4, ColorMode.RGBA))
    doc.add_layer("Second")
    assert doc.layer_count() == 2
