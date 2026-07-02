"""Tests for the Document-level colour-mode conversion commands (ADR-0008, no Qt).

Colour mode is document-wide with a single authority: :attr:`Document.mode`
(ADR-0008 D1). The reversible whole-document conversions
:meth:`Document.make_convert_to_indexed_command` /
:meth:`Document.make_convert_to_rgba_command` (D3/D4) flip every layer buffer
**and** ``Document.mode`` together in one :class:`history.FunctionCommand`, so no
consumer ever observes a mixed-mode state. This module verifies:

* execute flips ``Document.mode`` to INDEXED / RGBA;
* the D2 invariant after convert-to-indexed — exactly ONE indexed layer per
  frame, every buffer's mode == ``Document.mode`` (no mixed mode);
* ``apply ∘ undo = identity`` (REQ-P3-LOGIC-017), including the **wholesale
  list-swap** undo restoring a FULL multi-layer RGBA tree (groups/masks/opacity/
  blend/references) — same node identities and order — with the originals never
  mutated;
* single-layer convert in both directions;
* D4 flatten-then-index: the resulting single indexed layer equals
  ``to_indexed(composite_stack(original stack), palette)``;
* the eager build-time guards (wrong direction / empty palette / bad metric).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pytest

from pixelart_creator.logic import history, palette_ops
from pixelart_creator.logic.blend import BlendMode, composite_stack
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.document import (
    Document,
    DocumentError,
    Layer,
    LayerGroup,
    iter_layers,
)
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.palette_ops import IndexedModeError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)

PAL = Palette([RED, GREEN, BLUE, BLACK, WHITE])


def _fill_rgba(buffer: PixelBuffer, rows: Sequence[Sequence[RGBA]]) -> None:
    for y, row in enumerate(rows):
        for x, color in enumerate(row):
            buffer.set_pixel(x, y, color)


def _single_layer_rgba_doc() -> Document:
    """A 2x2 single-layer RGBA document whose pixels are exact palette colours."""
    doc = Document(2, 2, palette=PAL)
    _fill_rgba(doc.frames[0].layers[0].buffer, [[RED, GREEN], [BLUE, RED]])
    return doc


def _indexed_doc() -> Document:
    """A 2x2 single-layer INDEXED document with indices into PAL."""
    doc = Document(2, 2, mode=ColorMode.INDEXED, palette=PAL)
    doc.frames[0].layers[0].buffer.data[:, :] = np.array(
        [[0, 1], [2, 3]], dtype=np.uint8
    )
    return doc


def _multilayer_rgba_doc() -> Document:
    """A 3x3 multi-layer RGBA document (opaque top over a solid background)."""
    doc = Document(3, 3, palette=PAL)
    base = doc.frames[0].layers[0]
    base.buffer.fill(BLUE)
    top = doc.add_layer("Top")
    # Two opaque red pixels on the top layer; the rest transparent (composites
    # through to the blue background).
    top.buffer.set_pixel(0, 0, RED)
    top.buffer.set_pixel(2, 2, GREEN)
    return doc


# -- convert-to-indexed: mode flip + returned unapplied -----------------------


def test_convert_to_indexed_returned_unapplied_then_flips_mode():
    doc = _single_layer_rgba_doc()
    cmd = doc.make_convert_to_indexed_command(PAL)
    assert isinstance(cmd, history.Command)
    # Returned UNAPPLIED — nothing changed yet.
    assert doc.mode is ColorMode.RGBA
    assert doc.frames[0].layers[0].buffer.mode is ColorMode.RGBA
    cmd.execute()
    assert doc.mode is ColorMode.INDEXED


def test_convert_to_indexed_single_layer_indexes_in_place():
    doc = _single_layer_rgba_doc()
    expected = palette_ops.to_indexed(doc.frames[0].layers[0].buffer, PAL)
    doc.make_convert_to_indexed_command(PAL).execute()
    layer = doc.frames[0].layers[0]
    assert layer.buffer.mode is ColorMode.INDEXED
    assert layer.buffer == expected
    # Single-leaf frame keeps the source layer's name.
    assert layer.name == "Background"


def test_convert_to_indexed_preserves_metric_kwarg():
    doc = _single_layer_rgba_doc()
    expected = palette_ops.to_indexed(
        doc.frames[0].layers[0].buffer, PAL, metric="ciede2000"
    )
    doc.make_convert_to_indexed_command(PAL, metric="ciede2000").execute()
    assert doc.frames[0].layers[0].buffer == expected


# -- convert-to-indexed: the D2 invariant -------------------------------------


def test_convert_to_indexed_invariant_one_indexed_layer_per_frame():
    doc = _multilayer_rgba_doc()
    doc.add_frame()  # a second frame, also multi-...: actually one layer here
    doc.frames[1].layers[0].buffer.fill(WHITE)
    doc.make_convert_to_indexed_command(PAL).execute()

    assert doc.mode is ColorMode.INDEXED
    for frame in doc.frames:
        # Exactly ONE layer per frame, and it is a leaf Layer.
        assert len(frame.layers) == 1
        assert isinstance(frame.layers[0], Layer)
        # No mixed mode: every buffer agrees with Document.mode.
        for leaf in iter_layers(frame.layers):
            assert leaf.buffer.mode is ColorMode.INDEXED
            assert leaf.buffer.mode is doc.mode


# -- convert-to-indexed: D4 flatten-then-index matches the compositor ---------


def test_convert_to_indexed_multilayer_flatten_matches_compositor():
    doc = _multilayer_rgba_doc()
    nodes = list(doc.frames[0].layers)
    # The wholesale-swap semantics mean the resulting single indexed layer must
    # equal indexing the compositor's flatten of the ORIGINAL stack (D4).
    flat = composite_stack(nodes, doc.width, doc.height)
    expected = palette_ops.to_indexed(flat, PAL)

    doc.make_convert_to_indexed_command(PAL).execute()
    assert len(doc.frames[0].layers) == 1
    result = doc.frames[0].layers[0]
    assert result.buffer.mode is ColorMode.INDEXED
    assert result.buffer == expected
    # New layer takes the topmost node's name (nodes[-1]).
    assert result.name == "Top"


# -- convert-to-indexed: apply∘undo == identity (single layer) ----------------


def test_convert_to_indexed_undo_restores_single_layer_exactly():
    doc = _single_layer_rgba_doc()
    original_list = doc.frames[0].layers
    original_layer = original_list[0]
    original_bytes = original_layer.buffer.data.copy()

    cmd = doc.make_convert_to_indexed_command(PAL)
    cmd.execute()
    cmd.undo()

    assert doc.mode is ColorMode.RGBA
    # Same list object and same node identity restored (no deep copy).
    assert doc.frames[0].layers is original_list
    assert doc.frames[0].layers[0] is original_layer
    assert original_layer.buffer.mode is ColorMode.RGBA
    assert np.array_equal(original_layer.buffer.data, original_bytes)


# -- convert-to-indexed: FULL multi-layer tree restore on undo ----------------


def _rich_multilayer_doc() -> Document:
    """A multi-layer RGBA doc with a group, mask, opacity, blend and a reference."""
    doc = Document(3, 3, palette=PAL)
    base = doc.frames[0].layers[0]
    base.buffer.fill(BLUE)
    base.opacity = 0.5
    base.blend_mode = BlendMode.MULTIPLY
    base.reference = True

    mid = Layer(PixelBuffer(3, 3, ColorMode.RGBA), "Mid")
    mid.buffer.set_pixel(1, 1, RED)
    mask = PixelBuffer(3, 3, ColorMode.RGBA)
    mask.set_pixel(0, 0, (0, 0, 0, 255))
    mid.mask = mask

    inner = Layer(PixelBuffer(3, 3, ColorMode.RGBA), "Inner")
    inner.buffer.set_pixel(2, 0, GREEN)
    group = LayerGroup("G", [inner], opacity=0.75, blend_mode=BlendMode.SCREEN)

    doc.frames[0].layers.append(mid)
    doc.frames[0].layers.append(group)
    return doc


def test_convert_to_indexed_undo_restores_full_multilayer_tree():
    doc = _rich_multilayer_doc()
    frame = doc.frames[0]
    original_list = frame.layers
    original_nodes = list(frame.layers)
    # Snapshot the exact prior state of every leaf buffer (identity + bytes).
    leaf_snapshots = [
        (leaf, leaf.buffer.data.copy()) for leaf in iter_layers(original_nodes)
    ]

    cmd = doc.make_convert_to_indexed_command(PAL)
    cmd.execute()

    # While applied: single indexed layer, and the ORIGINAL nodes are untouched
    # (execute swaps lists wholesale, never mutates the original tree).
    assert doc.mode is ColorMode.INDEXED
    assert len(frame.layers) == 1
    for leaf, snap in leaf_snapshots:
        assert leaf.buffer.mode is ColorMode.RGBA
        assert np.array_equal(leaf.buffer.data, snap)

    cmd.undo()

    # Full tree restored: same list object, same node identities and order.
    assert doc.mode is ColorMode.RGBA
    assert frame.layers is original_list
    assert list(frame.layers) == original_nodes
    assert frame.layers[0] is original_nodes[0]
    restored_group = frame.layers[2]
    assert isinstance(restored_group, LayerGroup)
    assert restored_group.children[0] is original_nodes[2].children[0]
    # Attributes / bytes intact.
    assert frame.layers[0].opacity == 0.5
    assert frame.layers[0].blend_mode is BlendMode.MULTIPLY
    assert frame.layers[0].reference is True
    assert frame.layers[1].mask is not None
    for leaf, snap in leaf_snapshots:
        assert np.array_equal(leaf.buffer.data, snap)


def test_convert_to_indexed_redo_after_undo_reapplies():
    doc = _single_layer_rgba_doc()
    cmd = doc.make_convert_to_indexed_command(PAL)
    cmd.execute()
    applied = doc.frames[0].layers[0]
    cmd.undo()
    cmd.execute()
    # Redo restores the applied single indexed layer (same rebuilt object).
    assert doc.mode is ColorMode.INDEXED
    assert doc.frames[0].layers[0] is applied


# -- convert-to-indexed: guards -----------------------------------------------


def test_convert_to_indexed_on_indexed_doc_raises():
    doc = _indexed_doc()
    with pytest.raises(DocumentError):
        doc.make_convert_to_indexed_command(PAL)


def test_convert_to_indexed_empty_palette_raises_at_build():
    doc = _single_layer_rgba_doc()
    with pytest.raises(PaletteError):
        doc.make_convert_to_indexed_command(Palette([]))


def test_convert_to_indexed_bad_metric_raises_at_build():
    doc = _single_layer_rgba_doc()
    with pytest.raises(IndexedModeError):
        doc.make_convert_to_indexed_command(PAL, metric="nope")


# -- convert-to-rgba: mode flip + correctness ---------------------------------


def test_convert_to_rgba_returned_unapplied_then_flips_mode():
    doc = _indexed_doc()
    cmd = doc.make_convert_to_rgba_command(PAL)
    assert isinstance(cmd, history.Command)
    assert doc.mode is ColorMode.INDEXED
    cmd.execute()
    assert doc.mode is ColorMode.RGBA


def test_convert_to_rgba_reproduces_palette_lookup():
    doc = _indexed_doc()
    expected = palette_ops.to_rgba(doc.frames[0].layers[0].buffer, PAL)
    doc.make_convert_to_rgba_command(PAL).execute()
    layer = doc.frames[0].layers[0]
    assert layer.buffer.mode is ColorMode.RGBA
    assert layer.buffer == expected
    assert layer.name == "Background"


def test_convert_to_rgba_undo_restores_indexed_exactly():
    doc = _indexed_doc()
    original_list = doc.frames[0].layers
    original_layer = original_list[0]
    original_bytes = original_layer.buffer.data.copy()

    cmd = doc.make_convert_to_rgba_command(PAL)
    cmd.execute()
    cmd.undo()

    assert doc.mode is ColorMode.INDEXED
    assert doc.frames[0].layers is original_list
    assert doc.frames[0].layers[0] is original_layer
    assert original_layer.buffer.mode is ColorMode.INDEXED
    assert np.array_equal(original_layer.buffer.data, original_bytes)


def test_convert_to_rgba_on_rgba_doc_raises():
    doc = _single_layer_rgba_doc()
    with pytest.raises(DocumentError):
        doc.make_convert_to_rgba_command(PAL)


# -- single-layer convert both directions in sequence -------------------------


def test_convert_round_trip_indexed_then_rgba_is_palette_quantised():
    # RGBA (exact palette colours) -> INDEXED -> RGBA reproduces the quantised
    # image (colour set ⊆ palette); here the source is already quantised so the
    # RGBA result equals the original bytes.
    doc = _single_layer_rgba_doc()
    original_bytes = doc.frames[0].layers[0].buffer.data.copy()

    doc.make_convert_to_indexed_command(PAL).execute()
    assert doc.mode is ColorMode.INDEXED

    doc.make_convert_to_rgba_command(PAL).execute()
    assert doc.mode is ColorMode.RGBA
    assert np.array_equal(doc.frames[0].layers[0].buffer.data, original_bytes)
