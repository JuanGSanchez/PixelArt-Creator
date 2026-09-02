"""Tests for pixelart_creator.logic.document."""

from __future__ import annotations

import pytest

from pixelart_creator.logic import constants
from pixelart_creator.logic.document import (
    DEFAULT_FRAME_DURATION_MS,
    Document,
    DocumentError,
    Frame,
    Layer,
)
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)


def test_default_frame_duration_is_single_sourced_from_constants():
    # Regression (S12): document re-exports the constant; constants.py is the
    # sole source of truth. No magic 100 inlined in document.py.
    assert DEFAULT_FRAME_DURATION_MS == constants.DEFAULT_FRAME_DURATION_MS
    assert constants.DEFAULT_FRAME_DURATION_MS == 100


def test_new_document_has_one_frame_one_layer():
    doc = Document(16, 16)
    assert doc.width == 16 and doc.height == 16
    assert len(doc.frames) == 1
    assert len(doc.frames[0].layers) == 1
    assert doc.frames[0].layers[0].name == "Background"


def test_document_accepts_palette_and_metadata():
    pal = Palette([RED])
    doc = Document(4, 4, mode=ColorMode.INDEXED, palette=pal, metadata={"author": "x"})
    assert doc.mode is ColorMode.INDEXED
    assert doc.palette == pal
    assert doc.metadata["author"] == "x"


def test_document_ppi_defaults_to_constant():
    # REQ-P9-LOGIC-007 / BF-3 (ADR-0025 §1): default ppi is the named constant.
    doc = Document(4, 4)
    assert doc.ppi == constants.DEFAULT_DOCUMENT_PPI
    assert constants.DEFAULT_DOCUMENT_PPI == 72.0
    assert isinstance(doc.ppi, float)


def test_document_ppi_threaded_through_construction():
    doc = Document(4, 4, ppi=300)
    assert doc.ppi == 300.0
    assert isinstance(doc.ppi, float)


@pytest.mark.parametrize(
    "bad", [0, -1, 0.0, -72.5, float("nan"), float("inf"), "x", True]
)
def test_document_ppi_rejects_non_positive_or_invalid(bad):
    with pytest.raises(DocumentError):
        Document(4, 4, ppi=bad)  # type: ignore[arg-type]


def test_document_from_buffer_carries_ppi():
    buf = PixelBuffer(3, 2)
    doc = Document.from_buffer(buf, ppi=150.0)
    assert doc.ppi == 150.0
    # And defaults to the constant when omitted.
    assert Document.from_buffer(PixelBuffer(2, 2)).ppi == constants.DEFAULT_DOCUMENT_PPI


def test_layer_opacity_validation():
    layer = Layer(PixelBuffer(2, 2))
    layer.opacity = 0.5
    assert layer.opacity == 0.5
    with pytest.raises(DocumentError):
        layer.opacity = 1.5
    with pytest.raises(DocumentError):
        Layer(PixelBuffer(2, 2), opacity="x")  # type: ignore[arg-type]


def test_layer_repr():
    assert "Layer" in repr(Layer(PixelBuffer(1, 1), "L"))


def test_frame_duration_validation_and_repr():
    with pytest.raises(DocumentError):
        Frame(duration_ms=0)
    assert "Frame(" in repr(Frame())


def test_add_and_remove_layer():
    doc = Document(8, 8)
    layer = doc.add_layer("Ink")
    assert layer.name == "Ink"
    assert len(doc.frames[0].layers) == 2
    removed = doc.remove_layer(1)
    assert removed is layer
    assert len(doc.frames[0].layers) == 1


def test_remove_last_layer_refused():
    doc = Document(8, 8)
    with pytest.raises(DocumentError):
        doc.remove_layer(0)


def test_remove_layer_bad_index():
    doc = Document(8, 8)
    doc.add_layer()
    with pytest.raises(DocumentError):
        doc.remove_layer(9)


def test_move_layer_reorders():
    doc = Document(8, 8)
    top = doc.add_layer("Top")
    doc.move_layer(1, 0)
    assert doc.frames[0].layers[0] is top


def test_move_layer_bad_index():
    doc = Document(8, 8)
    with pytest.raises(DocumentError):
        doc.move_layer(0, 5)


def test_add_and_remove_frame():
    doc = Document(8, 8)
    doc.add_frame(duration_ms=200)
    assert len(doc.frames) == 2
    assert doc.frames[1].duration_ms == 200
    doc.remove_frame(1)
    assert len(doc.frames) == 1


def test_remove_last_frame_refused():
    doc = Document(8, 8)
    with pytest.raises(DocumentError):
        doc.remove_frame(0)


def test_bad_frame_index():
    doc = Document(8, 8)
    with pytest.raises(DocumentError):
        doc.add_layer(frame_index=3)


def test_resize_canvas_all_buffers():
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, RED)
    doc.add_layer()
    doc.resize_canvas(8, 8)
    assert doc.width == 8 and doc.height == 8
    for frame in doc.frames:
        for layer in frame.layers:
            assert layer.buffer.width == 8 and layer.buffer.height == 8
    assert doc.frames[0].layers[0].buffer.get_pixel(0, 0) == RED


def test_document_repr():
    assert "Document(8x8" in repr(Document(8, 8))
