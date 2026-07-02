"""Tests for pixelart_creator.logic.palette_analytics (usage counts).

Covers REQ-P3-LOGIC-012 (SC-L012-1..4): per-colour counts sum to the total pixel
count, an unused index reports 0, counts are computed for both RGBA and indexed
buffers, and the result is deterministically ordered by (-count, key).
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_analytics import (
    PaletteAnalyticsError,
    color_usage_counts,
    document_usage_counts,
    index_usage_counts,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
RED = (255, 0, 0, 255)


def test_color_usage_counts_sum_to_total():
    # SC-L012-1.
    buf = PixelBuffer(4, 4, ColorMode.RGBA)  # 16 px, all transparent black
    buf.set_pixel(0, 0, RED)
    buf.set_pixel(1, 0, RED)
    counts = color_usage_counts(buf)
    assert sum(n for _, n in counts) == 16
    as_dict = dict(counts)
    assert as_dict[RED] == 2
    assert as_dict[(0, 0, 0, 0)] == 14


def test_color_usage_counts_ordered_by_count_then_colour():
    # SC-L012-4: most-used first; ties by colour tuple ascending.
    buf = PixelBuffer(3, 1, ColorMode.RGBA)
    buf.set_pixel(0, 0, WHITE)
    buf.set_pixel(1, 0, RED)
    buf.set_pixel(2, 0, RED)
    counts = color_usage_counts(buf)
    assert counts[0] == (RED, 2)
    # deterministic order for equal counts
    assert counts == color_usage_counts(buf)


def test_color_usage_counts_requires_rgba():
    with pytest.raises(PaletteAnalyticsError):
        color_usage_counts(PixelBuffer(4, 4, ColorMode.INDEXED))


def test_index_usage_counts_unused_reports_zero():
    # SC-L012-2: every palette index appears; unused -> 0.
    pal = Palette([BLACK, WHITE, RED])
    buf = PixelBuffer(2, 2, ColorMode.INDEXED)
    buf.fill(0)
    buf.set_pixel(0, 0, 1)  # index 1 used once
    counts = dict(index_usage_counts(buf, pal))
    assert counts[0] == 3
    assert counts[1] == 1
    assert counts[2] == 0  # unused


def test_index_usage_counts_ordered():
    # SC-L012-4.
    pal = Palette([BLACK, WHITE])
    buf = PixelBuffer(2, 2, ColorMode.INDEXED)
    buf.data[:, :] = np.array([[0, 1], [1, 1]], dtype=np.uint8)
    counts = index_usage_counts(buf, pal)
    assert counts[0] == (1, 3)
    assert counts[1] == (0, 1)


def test_index_usage_counts_requires_indexed():
    with pytest.raises(PaletteAnalyticsError):
        index_usage_counts(PixelBuffer(4, 4, ColorMode.RGBA), Palette([BLACK]))


def test_document_usage_counts_rgba_aggregates_layers():
    # SC-L012-3: works on a whole RGBA document, aggregating frames/layers.
    doc = Document(2, 2, mode=ColorMode.RGBA)
    doc.frames[0].layers[0].buffer.fill(RED)
    layer2 = doc.add_layer("L2")
    layer2.buffer.fill(WHITE)
    counts = dict(document_usage_counts(doc))
    assert counts[RED] == 4
    assert counts[WHITE] == 4


def test_document_usage_counts_indexed():
    # SC-L012-3 indexed branch.
    pal = Palette([BLACK, WHITE])
    doc = Document(2, 2, mode=ColorMode.INDEXED, palette=pal)
    doc.frames[0].layers[0].buffer.fill(1)
    counts = dict(document_usage_counts(doc))
    assert counts[1] == 4
    assert counts[0] == 0


def test_document_usage_counts_indexed_explicit_palette():
    pal = Palette([BLACK, WHITE, RED])
    doc = Document(2, 2, mode=ColorMode.INDEXED)
    doc.frames[0].layers[0].buffer.fill(0)
    counts = dict(document_usage_counts(doc, palette=pal))
    assert counts[0] == 4
    assert counts[2] == 0


def test_document_usage_counts_walks_leaves_through_groups():
    # Regression (Phase-4): analytics now flatten group subtrees via iter_layers,
    # so a layer nested inside a LayerGroup is counted like a top-level layer.
    from pixelart_creator.logic.document import Layer, LayerGroup

    doc = Document(2, 2, mode=ColorMode.RGBA)
    doc.frames[0].layers[0].buffer.fill(RED)  # top-level: 4 px RED
    inner = Layer(PixelBuffer(2, 2, ColorMode.RGBA), "inner")
    inner.buffer.fill(WHITE)  # nested: 4 px WHITE
    doc.frames[0].layers.append(LayerGroup("G", [inner]))
    counts = dict(document_usage_counts(doc))
    assert counts[RED] == 4
    assert counts[WHITE] == 4  # the grouped leaf is counted, not skipped
