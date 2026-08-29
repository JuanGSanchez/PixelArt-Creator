"""Regression: ``.pixproj`` round-trip of a mode-CONVERTED document (ADR-0008).

Closes the latent persistence-corruption bug from ADR-0008 §Context (bug 2):
before the fix, convert-to-indexed swapped a layer buffer to indexed but left
``Document.mode = RGBA``, so :func:`project_io.serialize` wrote
``canvas.mode = "rgba"`` above indexed bytes; on reload the indexed bytes were
mis-decoded as RGBA → :class:`ProjectIOError` (wrong payload size) or silent
corruption. With ADR-0008 the conversion command flips ``Document.mode``
atomically with the buffers, so a converted document persists and reloads
consistently.

These tests convert in memory, SAVE, LOAD, and assert the reloaded document is
in the expected mode with a correctly-decoded buffer — no ``ProjectIOError``, no
corruption. Maps to DATA-001..005 (v2 round-trip) + ADR-0008 D1/D3.
"""

from __future__ import annotations

import numpy as np

from pixelart_creator.data import project_io as pio
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)

PAL = Palette([RED, GREEN, BLUE, BLACK, WHITE])


def _single_layer_rgba_doc() -> Document:
    doc = Document(2, 2, palette=PAL)
    buf = doc.frames[0].layers[0].buffer
    for x, y, color in [(0, 0, RED), (1, 0, GREEN), (0, 1, BLUE), (1, 1, WHITE)]:
        buf.set_pixel(x, y, color)
    return doc


def _multilayer_rgba_doc() -> Document:
    doc = Document(3, 3, palette=PAL)
    doc.frames[0].layers[0].buffer.fill(BLUE)
    top = doc.add_layer("Top")
    top.buffer.set_pixel(0, 0, RED)
    top.buffer.set_pixel(2, 2, GREEN)
    return doc


# --------------------------------------------------------------------------- #
# The KEY regression: convert-to-indexed then round-trip.                      #
# --------------------------------------------------------------------------- #


def test_converted_to_indexed_doc_round_trips_without_corruption(tmp_path):
    doc = _single_layer_rgba_doc()
    doc.make_convert_to_indexed_command(PAL).execute()
    assert doc.mode is ColorMode.INDEXED
    expected_bytes = doc.frames[0].layers[0].buffer.data.copy()

    # The serialised header must now agree with the indexed buffers (the bug was
    # canvas.mode == "rgba" above indexed bytes).
    payload = pio.serialize(doc)
    assert payload["canvas"]["mode"] == "indexed"

    path = pio.save_project(doc, tmp_path / "converted")
    loaded = pio.load_project(path)  # must NOT raise ProjectIOError

    assert loaded.mode is ColorMode.INDEXED
    assert len(loaded.frames[0].layers) == 1
    layer = loaded.frames[0].layers[0]
    assert layer.buffer.mode is ColorMode.INDEXED
    assert np.array_equal(layer.buffer.data, expected_bytes)


def test_converted_multilayer_to_indexed_round_trips(tmp_path):
    doc = _multilayer_rgba_doc()
    doc.make_convert_to_indexed_command(PAL).execute()
    assert doc.mode is ColorMode.INDEXED
    expected_bytes = doc.frames[0].layers[0].buffer.data.copy()

    path = pio.save_project(doc, tmp_path / "converted_multi")
    loaded = pio.load_project(path)

    assert loaded.mode is ColorMode.INDEXED
    # Flatten-then-index collapses the tree to a single indexed layer (D2/D4).
    assert len(loaded.frames[0].layers) == 1
    assert len(iter_layers(loaded.frames[0].layers)) == 1
    layer = loaded.frames[0].layers[0]
    assert layer.buffer.mode is ColorMode.INDEXED
    assert np.array_equal(layer.buffer.data, expected_bytes)


def test_converted_to_rgba_doc_round_trips(tmp_path):
    # A born-indexed document converted to RGBA must persist as RGBA.
    doc = Document(2, 2, mode=ColorMode.INDEXED, palette=PAL)
    doc.frames[0].layers[0].buffer.data[:, :] = np.array([[0, 1], [2, 3]], np.uint8)
    doc.make_convert_to_rgba_command(PAL).execute()
    assert doc.mode is ColorMode.RGBA
    expected_bytes = doc.frames[0].layers[0].buffer.data.copy()

    payload = pio.serialize(doc)
    assert payload["canvas"]["mode"] == "rgba"

    path = pio.save_project(doc, tmp_path / "to_rgba")
    loaded = pio.load_project(path)

    assert loaded.mode is ColorMode.RGBA
    layer = loaded.frames[0].layers[0]
    assert layer.buffer.mode is ColorMode.RGBA
    assert np.array_equal(layer.buffer.data, expected_bytes)


def test_convert_index_save_reload_equals_direct_index(tmp_path):
    # The reloaded indexed buffer must equal indexing the original RGBA buffer
    # directly — end-to-end proof the decode used the correct (indexed) mode.
    doc = _single_layer_rgba_doc()
    from pixelart_creator.logic import palette_ops

    direct = palette_ops.to_indexed(doc.frames[0].layers[0].buffer, PAL)

    doc.make_convert_to_indexed_command(PAL).execute()
    path = pio.save_project(doc, tmp_path / "roundtrip")
    loaded = pio.load_project(path)

    assert isinstance(loaded.frames[0].layers[0].buffer, PixelBuffer)
    assert loaded.frames[0].layers[0].buffer == direct
