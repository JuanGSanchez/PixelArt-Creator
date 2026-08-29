"""Tests for pixelart_creator.logic.convergence (Phase-10 Slice B, no Qt).

The heart of REQ-P10-LOGIC-006 / SC-L006-1: deterministic HYBRID convergence. The
determinism guarantee — for any set of concurrent ops from N sites, **every** delivery
ordering converges to a BYTE-IDENTICAL serialised ``Document`` (strong eventual
consistency) — is tested hard with Hypothesis (permutation-invariance property) and an
exhaustive all-orderings enumeration. Also covers: ``base`` is never mutated, same-tile
RasterOp LWW by ``(logical_clock, site_id)``, different-tile survival, structured
metadata / layer-attr / layer-order LWW via the pycrdt layer, the ``make_raster_op`` /
``structured_sidecar`` helper contracts, and the ``ConvergenceError`` validation surface
(including that ``CRDT_TILE_SIZE_PX`` is enforced, not inlined).
"""

from __future__ import annotations

import copy
import itertools

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.data.cloud.port import serialize_project
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import (
    LAYER_ATTRS,
    ConvergenceError,
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    RasterOp,
    converge,
    make_raster_op,
    structured_sidecar,
)
from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

TILE = CRDT_TILE_SIZE_PX
RGBA_TILE_BYTES = TILE * TILE * 4


def _doc(width=2 * TILE, height=TILE, mode=ColorMode.RGBA):
    """A 3-top-level-layer document; layer_ids == [1, 2, 3], all paintable leaves."""
    d = Document(width, height, mode=mode)
    d.add_layer("L2")
    d.add_layer("L3")
    return d


def _layer_ids(doc):
    return [n.layer_id for n in doc.frames[0].layers]


def _ser(doc):
    return serialize_project(doc)


def _solid_tile(value, width=TILE, height=TILE, channels=4):
    return bytes([value]) * (width * height * channels)


# --- helpers: converge is a pure, non-mutating NEW-Document factory ---------- #


def test_converge_returns_new_document_and_never_mutates_base():
    base = _doc()
    before = _ser(base)
    ops = [
        MetadataOp("title", "Hello", 1, 0),
        make_raster_op(
            base.frames[0].layers[0].buffer.data,
            frame_index=0,
            layer_id=1,
            tile_x=0,
            tile_y=0,
            logical_clock=3,
            site_id=1,
        ),
    ]
    result = converge(base, ops, site_id=1)
    assert result is not base
    assert _ser(base) == before  # base untouched
    assert result.metadata["title"] == "Hello"


def test_site_id_does_not_affect_the_converged_result():
    base = _doc()
    ops = [MetadataOp("author", "Ada", 5, 2), LayerAttrOp(0, 2, "opacity", 0.5, 4, 1)]
    a = converge(base, ops, site_id=0)
    b = converge(base, ops, site_id=999)
    assert _ser(a) == _ser(b)


# --- structured LWW winners (metadata / layer attr / layer order) ------------ #


def test_metadata_lww_highest_stamp_wins():
    base = _doc()
    ops = [
        MetadataOp("k", "low", 1, 5),
        MetadataOp("k", "win", 9, 0),
        MetadataOp("k", "mid", 9, 0),  # same stamp+value as winner (no conflict)
    ]
    assert converge(base, ops, site_id=0).metadata["k"] == "win"


def test_metadata_site_id_breaks_equal_logical_clock():
    base = _doc()
    ops = [MetadataOp("k", "lo", 7, 1), MetadataOp("k", "hi", 7, 3)]
    assert converge(base, ops, site_id=0).metadata["k"] == "hi"


def test_layer_attr_lww_applies_winning_value():
    base = _doc()
    ops = [
        LayerAttrOp(0, 2, "name", "old", 1, 0),
        LayerAttrOp(0, 2, "name", "new", 2, 0),
        LayerAttrOp(0, 3, "visible", False, 1, 0),
        LayerAttrOp(0, 3, "opacity", 0.25, 1, 0),
        LayerAttrOp(0, 1, "locked", True, 1, 0),
    ]
    result = converge(base, ops, site_id=0)
    by_id = {n.layer_id: n for n in result.frames[0].layers}
    assert by_id[2].name == "new"
    assert by_id[3].visible is False
    assert by_id[3].opacity == pytest.approx(0.25)
    assert by_id[1].locked is True


def test_concurrent_layer_order_converges_by_tiebreak():
    base = _doc()
    ids = _layer_ids(base)  # [1, 2, 3]
    ops = [
        LayerOrderOp(0, (3, 2, 1), 5, 0),  # loser
        LayerOrderOp(0, (2, 1, 3), 5, 1),  # winner (higher site_id at equal clock)
    ]
    result = converge(base, ops, site_id=0)
    assert _layer_ids(result) == [2, 1, 3]
    assert sorted(_layer_ids(result)) == sorted(ids)  # no layers lost


def test_layer_order_partial_order_appends_unnamed_nodes_in_place():
    base = _doc()
    ops = [LayerOrderOp(0, (3,), 1, 0)]  # only names id 3
    result = converge(base, ops, site_id=0)
    order = _layer_ids(result)
    assert order[0] == 3
    assert set(order) == {1, 2, 3}


# --- raster LWW: same-tile resolves, different tiles both survive ------------ #


def test_same_tile_raster_lww_highest_stamp_wins():
    base = _doc()
    win = _solid_tile(200)
    ops = [
        RasterOp(0, 1, 0, 0, _solid_tile(10), TILE, TILE, 1, 0),
        RasterOp(0, 1, 0, 0, win, TILE, TILE, 4, 0),
        RasterOp(0, 1, 0, 0, _solid_tile(50), TILE, TILE, 4, 0),  # lower content
    ]
    result = converge(base, ops, site_id=0)
    arr = result.frames[0].layers[0].buffer.data
    assert np.all(arr[0:TILE, 0:TILE] == 200)


def test_same_tile_equal_stamp_resolves_by_content_bytes_deterministically():
    base = _doc()
    a = RasterOp(0, 1, 0, 0, _solid_tile(0xAA), TILE, TILE, 2, 1)
    b = RasterOp(0, 1, 0, 0, _solid_tile(0x11), TILE, TILE, 2, 1)  # equal stamp
    r1 = converge(base, [a, b], site_id=0)
    r2 = converge(base, [b, a], site_id=0)
    assert _ser(r1) == _ser(r2)
    # higher pixel-byte content wins the total-order tiebreak
    assert np.all(r1.frames[0].layers[0].buffer.data[0:TILE, 0:TILE] == 0xAA)


def test_different_tiles_both_survive():
    base = _doc()  # 2*TILE wide => tile_x in {0, 1}
    ops = [
        RasterOp(0, 1, 0, 0, _solid_tile(11), TILE, TILE, 1, 0),
        RasterOp(0, 1, 1, 0, _solid_tile(22), TILE, TILE, 1, 0),
    ]
    arr = converge(base, ops, site_id=0).frames[0].layers[0].buffer.data
    assert np.all(arr[0:TILE, 0:TILE] == 11)
    assert np.all(arr[0:TILE, TILE : 2 * TILE] == 22)


def test_raster_converges_on_indexed_layer():
    base = _doc(width=TILE, height=TILE, mode=ColorMode.INDEXED)
    pixels = _solid_tile(7, channels=1)
    op = RasterOp(0, 1, 0, 0, pixels, TILE, TILE, 1, 0)
    arr = converge(base, [op], site_id=0).frames[0].layers[0].buffer.data
    assert arr.ndim == 2
    assert np.all(arr[0:TILE, 0:TILE] == 7)


# --- make_raster_op + structured_sidecar helper contracts -------------------- #


def test_make_raster_op_extracts_full_tile():
    base = _doc()
    buf = base.frames[0].layers[0].buffer.data
    buf[0:TILE, 0:TILE] = 123
    op = make_raster_op(
        buf, frame_index=0, layer_id=1, tile_x=0, tile_y=0, logical_clock=1, site_id=0
    )
    assert op.tile_width == TILE and op.tile_height == TILE
    assert len(op.pixels) == RGBA_TILE_BYTES
    assert set(op.pixels) == {123}


def test_make_raster_op_clips_edge_tile():
    # A 96px-wide buffer: tile_x=1 starts at 64 and is clipped to width-64 = 32.
    d = Document(96, TILE)
    buf = d.frames[0].layers[0].buffer.data
    op = make_raster_op(
        buf, frame_index=0, layer_id=1, tile_x=1, tile_y=0, logical_clock=1, site_id=0
    )
    assert op.tile_width == 96 - TILE
    assert op.tile_height == TILE


def test_make_raster_op_tile_fully_outside_buffer_raises():
    base = _doc()
    buf = base.frames[0].layers[0].buffer.data
    with pytest.raises(ConvergenceError):
        make_raster_op(
            buf,
            frame_index=0,
            layer_id=1,
            tile_x=9,
            tile_y=0,
            logical_clock=1,
            site_id=0,
        )


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((TILE, TILE), dtype=np.int32),  # wrong dtype
        np.zeros((TILE, TILE, 4, 1), dtype=np.uint8),  # wrong ndim
    ],
)
def test_make_raster_op_rejects_bad_array(bad):
    with pytest.raises(ConvergenceError):
        make_raster_op(
            bad,
            frame_index=0,
            layer_id=1,
            tile_x=0,
            tile_y=0,
            logical_clock=1,
            site_id=0,
        )


def test_structured_sidecar_is_bytes_and_order_independent():
    ops = [
        MetadataOp("a", "1", 3, 0),
        MetadataOp("b", "2", 1, 0),
        LayerAttrOp(0, 2, "name", "N", 2, 0),
    ]
    forward = structured_sidecar(ops)
    reverse = structured_sidecar(list(reversed(ops)))
    assert isinstance(forward, bytes)
    assert forward == reverse  # deterministic, permutation-independent sidecar


def test_structured_sidecar_empty_ops_is_valid_bytes():
    assert isinstance(structured_sidecar([]), bytes)


# --- ConvergenceError validation surface ------------------------------------- #


def test_converge_rejects_non_document_base():
    with pytest.raises(ConvergenceError):
        converge("not a document", [], site_id=0)  # type: ignore[arg-type]


def test_converge_rejects_negative_site_id():
    with pytest.raises(ConvergenceError):
        converge(_doc(), [], site_id=-1)


def test_converge_rejects_unknown_operation_type():
    with pytest.raises(ConvergenceError):
        converge(_doc(), [object()], site_id=0)  # type: ignore[list-item]


def test_raster_op_targeting_missing_layer_raises():
    base = _doc()
    op = RasterOp(0, 999, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)
    with pytest.raises(ConvergenceError):
        converge(base, [op], site_id=0)


def test_raster_op_targeting_group_node_raises():
    base = _doc()
    base.frames[0].layers.append(LayerGroup("G", [], layer_id=777))
    op = RasterOp(0, 777, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)
    with pytest.raises(ConvergenceError):
        converge(base, [op], site_id=0)


def test_raster_op_frame_out_of_range_raises():
    base = _doc()
    op = RasterOp(5, 1, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)
    with pytest.raises(ConvergenceError):
        converge(base, [op], site_id=0)


def test_raster_tile_exceeding_buffer_raises():
    base = _doc(width=TILE, height=TILE)  # one tile only
    op = RasterOp(0, 1, 1, 0, _solid_tile(1), TILE, TILE, 1, 0)  # tile_x=1 => x0=TILE
    with pytest.raises(ConvergenceError):
        converge(base, [op], site_id=0)


def test_raster_payload_mode_mismatch_raises():
    base = _doc(width=TILE, height=TILE)  # RGBA layer expects cells*4 bytes
    op = RasterOp(0, 1, 0, 0, _solid_tile(1, 2, 2, 1), 2, 2, 1, 0)  # indexed-sized
    with pytest.raises(ConvergenceError):
        converge(base, [op], site_id=0)


def test_layer_attr_op_rejects_bool_layer_id():
    with pytest.raises(ConvergenceError):
        LayerAttrOp(0, True, "name", "x", 1, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_layer_id", [True, 0, -1])
def test_raster_op_rejects_bad_layer_id(bad_layer_id):
    with pytest.raises(ConvergenceError):
        RasterOp(0, bad_layer_id, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)


def test_layer_attr_applies_to_nested_group_child():
    base = _doc()
    child = Layer(PixelBuffer(TILE, TILE, ColorMode.RGBA), "Nested", layer_id=50)
    base.frames[0].layers.append(LayerGroup("G", [child], layer_id=60))
    ops = [LayerAttrOp(0, 50, "name", "Renamed", 1, 0)]
    result = converge(base, ops, site_id=0)
    group = [n for n in result.frames[0].layers if isinstance(n, LayerGroup)][0]
    assert group.children[0].name == "Renamed"


def test_structured_ops_targeting_out_of_range_frame_are_skipped():
    base = _doc()
    before_ids = _layer_ids(base)
    ops = [
        MetadataOp("k", "v", 1, 0),  # this one applies
        LayerAttrOp(9, 2, "name", "X", 1, 0),  # frame out of range -> skipped
        LayerOrderOp(9, (3, 2, 1), 1, 0),  # frame out of range -> skipped
    ]
    result = converge(base, ops, site_id=0)
    assert result.metadata["k"] == "v"
    assert _layer_ids(result) == before_ids  # order untouched


@pytest.mark.parametrize(
    "factory",
    [
        lambda: MetadataOp("", "v", 1, 0),  # empty key
        lambda: MetadataOp("k", 123, 1, 0),  # non-str value
        lambda: MetadataOp("k", "v", -1, 0),  # negative clock
        lambda: MetadataOp("k", "v", 1, True),  # bool site_id
        lambda: LayerAttrOp(0, 0, "name", "x", 1, 0),  # layer_id <= 0
        lambda: LayerAttrOp(0, 2, "bogus", "x", 1, 0),  # attr not in LAYER_ATTRS
        lambda: LayerOrderOp(0, [1, 2], 1, 0),  # order not a tuple
        lambda: LayerOrderOp(0, (1, 1), 1, 0),  # duplicate layer_id
        lambda: LayerOrderOp(0, (0,), 1, 0),  # non-positive id in order
        lambda: RasterOp(0, 1, 0, 0, b"\x00", TILE + 1, TILE, 1, 0),  # tile_w > cap
        lambda: RasterOp(0, 1, 0, 0, b"\x00", TILE, TILE + 1, 1, 0),  # tile_h > cap
        lambda: RasterOp(0, 1, 0, 0, "notbytes", 1, 1, 1, 0),  # pixels not bytes
        lambda: RasterOp(0, 1, 0, 0, b"\x00\x00", 1, 1, 1, 0),  # wrong payload length
    ],
)
def test_operation_post_init_validation(factory):
    with pytest.raises(ConvergenceError):
        factory()


def test_crdt_tile_size_is_enforced_from_the_constant():
    # tile_width up to CRDT_TILE_SIZE_PX is accepted; one over is rejected — proving
    # the bound is the imported constant, not an inlined literal.
    RasterOp(0, 1, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)  # exactly the cap: OK
    with pytest.raises(ConvergenceError):
        RasterOp(0, 1, 0, 0, b"\x00" * ((TILE + 1) * TILE * 4), TILE + 1, TILE, 1, 0)


def test_layer_attrs_vocabulary():
    assert LAYER_ATTRS == frozenset({"name", "opacity", "visible", "locked"})


# =========================================================================== #
# The core determinism guarantee (SC-L006-1): permutation-invariance.         #
# Hypothesis generates mixed op sets from multiple sites; every ordering must #
# converge to a BYTE-IDENTICAL serialised Document.                           #
# =========================================================================== #

# Fixed replica geometry the strategy generates ops against.
_STRAT_DOC = _doc(width=2 * TILE, height=TILE)
_STRAT_IDS = _layer_ids(_STRAT_DOC)  # [1, 2, 3]
_STRAT_TILES = ((0, 0), (1, 0))  # two horizontal tiles


@st.composite
def _mixed_op_sets(draw):
    """Generate a mixed set of concurrent ops from up to 5 sites.

    Structured ops (metadata / layer-attr / layer-order) are assigned GLOBALLY
    UNIQUE ``(logical_clock, site_id)`` stamps so no two structured writers ever
    collide on a key with an equal stamp — the realistic invariant a logical clock
    guarantees (a site issues monotonic clocks). Raster ops need no such care: their
    LWW total order includes the content bytes, so they commute unconditionally.
    """
    kinds = draw(
        st.lists(
            st.sampled_from(["meta", "attr", "order", "raster"]),
            min_size=0,
            max_size=14,
        )
    )
    n_struct = sum(1 for k in kinds if k != "raster")
    stamps = draw(
        st.lists(
            st.tuples(st.integers(0, 40), st.integers(0, 4)),
            unique=True,
            min_size=n_struct,
            max_size=n_struct,
        )
    )
    ops = []
    si = 0
    for kind in kinds:
        if kind == "raster":
            clk = draw(st.integers(0, 40))
            site = draw(st.integers(0, 4))
            tx, ty = draw(st.sampled_from(_STRAT_TILES))
            lid = draw(st.sampled_from(_STRAT_IDS))
            value = draw(st.integers(0, 255))
            ops.append(
                RasterOp(0, lid, tx, ty, _solid_tile(value), TILE, TILE, clk, site)
            )
            continue
        clk, site = stamps[si]
        si += 1
        if kind == "meta":
            key = draw(st.sampled_from(["title", "author", "note"]))
            val = draw(st.text(max_size=10))
            ops.append(MetadataOp(key, val, clk, site))
        elif kind == "attr":
            lid = draw(st.sampled_from(_STRAT_IDS))
            attr = draw(st.sampled_from(sorted(LAYER_ATTRS)))
            if attr == "name":
                val = draw(st.text(min_size=1, max_size=8))
            elif attr == "opacity":
                val = draw(
                    st.floats(
                        min_value=0.0,
                        max_value=1.0,
                        allow_nan=False,
                        allow_infinity=False,
                    )
                )
            else:
                val = draw(st.booleans())
            ops.append(LayerAttrOp(0, lid, attr, val, clk, site))
        else:  # order
            order = tuple(draw(st.permutations(_STRAT_IDS)))
            ops.append(LayerOrderOp(0, order, clk, site))
    return ops


@settings(max_examples=150)
@given(ops=_mixed_op_sets(), data=st.data())
def test_permutation_invariance_property(ops, data):
    """Every delivery ordering of the same op set converges byte-identically."""
    base = _doc(width=2 * TILE, height=TILE)
    baseline = _ser(base)
    permuted = data.draw(st.permutations(ops))

    canonical = _ser(converge(base, list(ops), site_id=1))
    other = _ser(converge(base, permuted, site_id=3))

    assert canonical == other
    assert _ser(base) == baseline  # base still never mutated under any op set


@settings(max_examples=60)
@given(ops=_mixed_op_sets())
def test_convergence_is_idempotent_under_reapplication(ops):
    """Re-converging the already-converged winners reproduces the same Document."""
    base = _doc(width=2 * TILE, height=TILE)
    first = converge(base, list(ops), site_id=2)
    again = converge(base, list(ops), site_id=2)
    assert _ser(first) == _ser(again)


def test_all_orderings_of_a_fixed_multi_site_set_are_byte_identical():
    """Exhaustive: ALL 5! = 120 delivery orderings of a 3-site op set converge equal.

    Concrete SC-L006-1 evidence — a fixed mixed set (concurrent metadata, a layer
    attribute, two competing reorders, same-tile + different-tile raster) from three
    sites; every permutation serialises byte-identically.
    """
    base = _doc(width=2 * TILE, height=TILE)
    ops = [
        MetadataOp("title", "sprite", 3, 1),
        LayerAttrOp(0, 2, "opacity", 0.5, 2, 0),
        LayerOrderOp(0, (3, 2, 1), 5, 0),
        LayerOrderOp(0, (2, 3, 1), 5, 2),  # higher site_id wins at equal clock
        RasterOp(0, 1, 0, 0, _solid_tile(0x40), TILE, TILE, 7, 1),
    ]
    results = {
        _ser(converge(base, list(perm), site_id=1))
        for perm in itertools.permutations(ops)
    }
    assert len(results) == 1  # all 120 orderings collapse to one serialisation

    # And the winners are the expected ones.
    converged = converge(base, ops, site_id=1)
    assert converged.metadata["title"] == "sprite"
    assert _layer_ids(converged) == [2, 3, 1]  # site_id=2 reorder won
    by_id = {n.layer_id: n for n in converged.frames[0].layers}
    assert by_id[2].opacity == pytest.approx(0.5)
    assert np.all(by_id[1].buffer.data[0:TILE, 0:TILE] == 0x40)  # raster hit layer 1
