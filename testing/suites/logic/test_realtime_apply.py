"""Tests for pixelart_creator.logic.realtime_apply (Phase-10 Slice C, no Qt).

Covers REQ-P10-LOGIC-007: the real-time CRDT apply layer + git-like branching over the
shipped hybrid convergence model.

Three behaviours are proven hard:

* **In-place apply.** :func:`apply_remote` mutates the *live* ``Document`` (the same
  object + the same layer-buffer ``ndarray`` are returned), never a full-document deep
  copy — the Article VI per-frame contract (ADR-0027 §7).
* **Out-of-order convergence (strong eventual consistency).** With a shared
  :class:`RealtimeState`, applying a set of updates in *any* delivery order converges to
  the SAME ``Document`` as the batch :func:`~pixelart_creator.logic.convergence.converge`
  of the same ops — verified with Hypothesis over permuted single-op streams (mirroring
  the Slice-B determinism property through the realtime path) and by concrete stale-drop
  cases.
* **Branching.** ``branch`` -> ``record`` -> ``merge`` is deterministic, conflict-free,
  order-independent, and the op-log is preserved so history is reconstructable.

Also exercises the op-codec (``encode_update`` / ``decode_update``), ``dirty_regions``,
and the Article VII untrusted-input surface (oversized / malformed / over-op-cap /
bad-base64 blobs rejected without ``eval``/``exec``).
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.data.cloud.port import serialize_project
from pixelart_creator.logic.cloud_validation import CloudValidationError
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX, MAX_CRDT_UPDATE_BYTES
from pixelart_creator.logic.convergence import (
    LAYER_ATTRS,
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    RasterOp,
    converge,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.logic.realtime_apply import (
    Branch,
    DirtyRegion,
    RealtimeError,
    RealtimeState,
    apply_remote,
    branch,
    decode_update,
    dirty_regions,
    encode_update,
    merge,
)

TILE = CRDT_TILE_SIZE_PX


def _doc(width=2 * TILE, height=TILE, mode=ColorMode.RGBA):
    """A 3-top-level-layer document; layer_ids == [1, 2, 3], all paintable leaves."""
    d = Document(width, height, mode=mode)
    d.add_layer("L2")
    d.add_layer("L3")
    return d


def _ser(doc):
    return serialize_project(doc)


def _layer_ids(doc):
    return [n.layer_id for n in doc.frames[0].layers]


def _solid_tile(value, width=TILE, height=TILE, channels=4):
    return bytes([value]) * (width * height * channels)


# --------------------------------------------------------------------------- #
# Op-codec round-trip + Article VII rejection surface.
# --------------------------------------------------------------------------- #


def test_encode_decode_round_trips_every_op_kind():
    ops = (
        MetadataOp("title", "Hello", 3, 0),
        LayerAttrOp(0, 2, "opacity", 0.5, 4, 1),
        LayerOrderOp(0, (3, 2, 1), 5, 2),
        RasterOp(0, 1, 0, 0, _solid_tile(0x40), TILE, TILE, 7, 1),
    )
    blob = encode_update(ops)
    assert isinstance(blob, bytes)
    assert decode_update(blob) == ops


def test_encode_update_is_deterministic():
    ops = (MetadataOp("a", "1", 1, 0), MetadataOp("b", "2", 2, 0))
    assert encode_update(ops) == encode_update(ops)


def test_encode_update_rejects_over_op_cap():
    ops = [MetadataOp("k", str(i), i, 0) for i in range(4097)]
    with pytest.raises(RealtimeError):
        encode_update(ops)


def test_encode_update_rejects_unknown_operation():
    with pytest.raises(RealtimeError):
        encode_update([object()])  # type: ignore[list-item]


def test_decode_update_rejects_oversized_blob():
    with pytest.raises(CloudValidationError):
        decode_update(b"x" * (MAX_CRDT_UPDATE_BYTES + 1))


def test_decode_update_rejects_empty_blob():
    with pytest.raises(CloudValidationError):
        decode_update(b"")


def test_decode_update_rejects_non_bytes():
    with pytest.raises(CloudValidationError):
        decode_update("not bytes")  # type: ignore[arg-type]


def test_decode_update_rejects_invalid_utf8_json():
    with pytest.raises(RealtimeError):
        decode_update(b"\xff\xfe not json")


def test_decode_update_rejects_non_object_payload():
    with pytest.raises(RealtimeError):
        decode_update(b"[1, 2, 3]")


def test_decode_update_rejects_wrong_version():
    with pytest.raises(RealtimeError):
        decode_update(json.dumps({"v": 999, "ops": []}).encode("utf-8"))


def test_decode_update_rejects_ops_not_a_list():
    with pytest.raises(RealtimeError):
        decode_update(json.dumps({"v": 1, "ops": "nope"}).encode("utf-8"))


def test_decode_update_rejects_over_op_cap_in_payload():
    payload = {"v": 1, "ops": [{"t": "meta", "key": "k", "value": "v", "c": 0, "s": 0}]}
    payload["ops"] = payload["ops"] * 4097
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_rejects_non_mapping_op():
    with pytest.raises(RealtimeError):
        decode_update(json.dumps({"v": 1, "ops": [123]}).encode("utf-8"))


def test_decode_update_rejects_op_missing_field():
    payload = {"v": 1, "ops": [{"t": "meta", "key": "k"}]}  # missing value/c/s
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_rejects_unknown_op_kind():
    payload = {"v": 1, "ops": [{"t": "bogus"}]}
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_rejects_order_op_with_non_list_order():
    payload = {
        "v": 1,
        "ops": [{"t": "order", "frame": 0, "order": "x", "c": 1, "s": 0}],
    }
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_rejects_raster_px_not_str():
    payload = {
        "v": 1,
        "ops": [
            {
                "t": "raster",
                "frame": 0,
                "layer": 1,
                "tx": 0,
                "ty": 0,
                "tw": 1,
                "th": 1,
                "px": 123,
                "c": 1,
                "s": 0,
            }
        ],
    }
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_rejects_raster_bad_base64():
    payload = {
        "v": 1,
        "ops": [
            {
                "t": "raster",
                "frame": 0,
                "layer": 1,
                "tx": 0,
                "ty": 0,
                "tw": 1,
                "th": 1,
                "px": "!!!not-base64!!!",
                "c": 1,
                "s": 0,
            }
        ],
    }
    with pytest.raises(RealtimeError):
        decode_update(json.dumps(payload).encode("utf-8"))


def test_decode_update_treats_dangerous_strings_as_inert_data_no_eval():
    # A hostile key that would be dangerous if eval'd is carried as plain data.
    payload = {
        "v": 1,
        "ops": [{"t": "meta", "key": "__import__", "value": "os", "c": 1, "s": 0}],
    }
    ops = decode_update(json.dumps(payload).encode("utf-8"))
    assert ops[0].key == "__import__"
    assert ops[0].value == "os"


# --------------------------------------------------------------------------- #
# dirty_regions.
# --------------------------------------------------------------------------- #


def test_dirty_regions_maps_raster_ops_to_tile_rects():
    blob = encode_update(
        [
            RasterOp(0, 1, 1, 0, _solid_tile(9), TILE, TILE, 1, 0),
            RasterOp(0, 1, 0, 0, _solid_tile(8), TILE, TILE, 1, 0),
        ]
    )
    regions = dirty_regions(blob)
    assert regions == (
        DirtyRegion(0, 1, 0, 0, TILE, TILE),  # sorted: (0,0) before (64,0)
        DirtyRegion(0, 1, TILE, 0, TILE, TILE),
    )


def test_dirty_regions_empty_for_structured_only_update():
    blob = encode_update([MetadataOp("k", "v", 1, 0)])
    assert dirty_regions(blob) == ()


def test_dirty_regions_validates_the_blob():
    with pytest.raises(CloudValidationError):
        dirty_regions(b"")


# --------------------------------------------------------------------------- #
# apply_remote — in-place, validation, one-shot batch.
# --------------------------------------------------------------------------- #


def test_apply_remote_mutates_in_place_and_returns_same_document():
    doc = _doc()
    buffer_before = doc.frames[0].layers[0].buffer.data
    blob = encode_update(
        [
            MetadataOp("title", "live", 1, 0),
            RasterOp(0, 1, 0, 0, _solid_tile(200), TILE, TILE, 2, 0),
        ]
    )
    result = apply_remote(doc, blob, site_id=0)
    assert result is doc  # same object — no full-document deep copy
    # The layer buffer ndarray object is mutated in place, not replaced.
    assert doc.frames[0].layers[0].buffer.data is buffer_before
    assert doc.metadata["title"] == "live"
    assert np.all(buffer_before[0:TILE, 0:TILE] == 200)


def test_apply_remote_matches_batch_converge_for_the_same_ops():
    base = _doc()
    ops = [
        MetadataOp("title", "sprite", 3, 1),
        LayerAttrOp(0, 2, "opacity", 0.25, 2, 0),
        RasterOp(0, 1, 0, 0, _solid_tile(0x30), TILE, TILE, 7, 1),
    ]
    batch = converge(base, ops, site_id=1)

    live = _doc()
    apply_remote(live, encode_update(ops), site_id=1)
    assert _ser(live) == _ser(batch)


def test_apply_remote_one_shot_resolves_winners_within_a_single_blob():
    doc = _doc()
    blob = encode_update(
        [
            MetadataOp("k", "low", 1, 0),
            MetadataOp("k", "win", 9, 0),
        ]
    )
    apply_remote(doc, blob, site_id=0)
    assert doc.metadata["k"] == "win"


def test_apply_remote_rejects_non_document():
    with pytest.raises(RealtimeError):
        apply_remote("nope", encode_update([MetadataOp("k", "v", 1, 0)]), site_id=0)


@pytest.mark.parametrize("bad_site", [True, -1, "0", 1.0])
def test_apply_remote_rejects_bad_site_id(bad_site):
    with pytest.raises(RealtimeError):
        apply_remote(
            _doc(), encode_update([MetadataOp("k", "v", 1, 0)]), site_id=bad_site
        )


def test_apply_remote_wraps_unapplyable_op_as_realtime_error():
    doc = _doc()
    # Raster op targeting a non-existent layer -> ConvergenceError -> RealtimeError.
    blob = encode_update([RasterOp(0, 999, 0, 0, _solid_tile(1), TILE, TILE, 1, 0)])
    with pytest.raises(RealtimeError):
        apply_remote(doc, blob, site_id=0)


# --------------------------------------------------------------------------- #
# RealtimeState — out-of-order / stale-drop convergence.
# --------------------------------------------------------------------------- #


def test_realtime_state_drops_stale_ops():
    state = RealtimeState()
    fresh_first = state.accept([MetadataOp("k", "new", 5, 0)])
    assert len(fresh_first) == 1
    fresh_stale = state.accept([MetadataOp("k", "old", 3, 0)])
    assert fresh_stale == ()  # strictly-older stamp dropped


def test_realtime_state_accepts_strictly_newer_op():
    state = RealtimeState()
    state.accept([MetadataOp("k", "v", 3, 0)])
    assert len(state.accept([MetadataOp("k", "v2", 4, 0)])) == 1


def test_realtime_state_resolves_the_winner_within_one_batch():
    state = RealtimeState()
    winners = state.accept([MetadataOp("k", "lo", 1, 0), MetadataOp("k", "hi", 9, 0)])
    assert len(winners) == 1
    assert winners[0].value == "hi"


def test_realtime_state_within_batch_loser_is_ignored():
    # Highest-stamp op offered FIRST; the later, lower-stamp op for the same register
    # must be dropped (exercises the not-strictly-greater branch in accept()).
    state = RealtimeState()
    winners = state.accept([MetadataOp("k", "hi", 9, 0), MetadataOp("k", "lo", 1, 0)])
    assert len(winners) == 1
    assert winners[0].value == "hi"


def test_realtime_state_rejects_unknown_operation_type():
    with pytest.raises(RealtimeError):
        RealtimeState().accept([object()])  # type: ignore[list-item]


def test_apply_remote_out_of_order_delivery_newer_then_older_keeps_newer():
    doc = _doc()
    state = RealtimeState()
    apply_remote(
        doc, encode_update([MetadataOp("k", "newer", 5, 0)]), site_id=0, state=state
    )
    apply_remote(
        doc, encode_update([MetadataOp("k", "older", 2, 0)]), site_id=0, state=state
    )
    assert doc.metadata["k"] == "newer"  # stale patch never clobbered the newer edit


# --------------------------------------------------------------------------- #
# Determinism property: permuted streaming apply == batch converge.
# --------------------------------------------------------------------------- #

_STRAT_DOC = _doc(width=2 * TILE, height=TILE)
_STRAT_IDS = _layer_ids(_STRAT_DOC)  # [1, 2, 3]
_STRAT_TILES = ((0, 0), (1, 0))


@st.composite
def _mixed_op_sets(draw):
    """A mixed op set from up to 5 sites (structured ops get UNIQUE stamps).

    Mirrors the Slice-B convergence strategy: structured registers receive globally
    unique ``(logical_clock, site_id)`` stamps (no equal-stamp structured collisions),
    and layer-order ops always name the FULL id set, so incremental in-place reordering
    composes to the same result as a batch converge. Raster ops commute unconditionally
    (their LWW total order includes the content bytes).
    """
    kinds = draw(
        st.lists(
            st.sampled_from(["meta", "attr", "order", "raster"]),
            min_size=0,
            max_size=12,
        )
    )
    n_struct = sum(1 for k in kinds if k != "raster")
    stamps = draw(
        st.lists(
            st.tuples(st.integers(0, 50), st.integers(0, 4)),
            unique=True,
            min_size=n_struct,
            max_size=n_struct,
        )
    )
    ops = []
    si = 0
    for kind in kinds:
        if kind == "raster":
            clk = draw(st.integers(0, 50))
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
        else:
            order = tuple(draw(st.permutations(_STRAT_IDS)))
            ops.append(LayerOrderOp(0, order, clk, site))
    return ops


def _semantic(doc):
    """A delivery-order-independent fingerprint of a document's converged state.

    Captures exactly what strong eventual consistency guarantees for the realtime path:
    the metadata mapping (as a sorted item list — the *content*, not the dict insertion
    order), and, per frame, the top-level layer z-order plus every leaf layer's
    convergeable attributes and raw buffer bytes. (See the module note: the streaming
    apply converges the logical Document identically; only the ``.pixproj`` byte-serial
    insertion order of newly-added metadata keys is arrival-ordered, unlike the sorting
    batch ``converge`` — a serialisation caveat, not a state divergence.)
    """
    frames = []
    for frame in doc.frames:
        order = [n.layer_id for n in frame.layers]
        leaves = []

        def _walk(nodes):
            for node in nodes:
                children = getattr(node, "children", None)
                if children is not None:
                    _walk(children)
                else:
                    leaves.append(
                        (
                            node.layer_id,
                            node.name,
                            round(float(node.opacity), 6),
                            bool(node.visible),
                            bool(node.locked),
                            node.buffer.data.tobytes(),
                        )
                    )

        _walk(frame.layers)
        frames.append((tuple(order), tuple(sorted(leaves))))
    return (tuple(sorted(doc.metadata.items())), tuple(frames))


@settings(max_examples=120)
@given(ops=_mixed_op_sets(), data=st.data())
def test_permuted_streaming_apply_converges_to_batch_result(ops, data):
    """Any delivery order of single-op updates, folded through a shared RealtimeState,
    converges to the SAME logical Document as the batch converge of the whole op set."""
    base = _doc(width=2 * TILE, height=TILE)
    expected = _semantic(converge(base, list(ops), site_id=1))

    permuted = data.draw(st.permutations(ops))
    live = _doc(width=2 * TILE, height=TILE)
    state = RealtimeState()
    for op in permuted:
        apply_remote(live, encode_update([op]), site_id=2, state=state)

    assert _semantic(live) == expected


@settings(max_examples=80)
@given(ops=_mixed_op_sets(), data=st.data())
def test_two_replicas_receiving_different_orders_converge(ops, data):
    """Two replicas fed the SAME ops in DIFFERENT delivery orders converge (SEC)."""
    order_a = data.draw(st.permutations(ops))
    order_b = data.draw(st.permutations(ops))

    replica_a = _doc(width=2 * TILE, height=TILE)
    state_a = RealtimeState()
    for op in order_a:
        apply_remote(replica_a, encode_update([op]), site_id=1, state=state_a)

    replica_b = _doc(width=2 * TILE, height=TILE)
    state_b = RealtimeState()
    for op in order_b:
        apply_remote(replica_b, encode_update([op]), site_id=2, state=state_b)

    assert _semantic(replica_a) == _semantic(replica_b)


# --------------------------------------------------------------------------- #
# Regression: metadata-key canonicalisation -> RAW .pixproj byte identity.     #
# Fix — convergence._apply_structured re-sorts Document.metadata to           #
# canonical (sorted) key order on EVERY fold, so the realtime one-op-at-a-time  #
# path serialises BYTE-IDENTICAL to the sorting batch converge no matter what   #
# order newly-inserted keys arrive in. This LOCKS byte-level SEC (not just the  #
# _semantic sorted-items fingerprint) for the metadata-key case.                #
# --------------------------------------------------------------------------- #


@st.composite
def _metadata_op_sets(draw):
    """A set of MetadataOps with DISTINCT keys + globally-unique stamps.

    Distinct keys => every op is the lone winner for its register, so all ops
    survive under any delivery order (no LWW drops); the ONLY variable left is the
    byte-serial insertion order of the metadata dict — exactly what the
    canonical-sort fix pins down. Keys are drawn from a wide pool so their arrival
    order is almost never already sorted, exercising the re-sort on the incremental
    realtime path (which appends new keys in arrival order before the canonicalise).
    """
    n = draw(st.integers(min_value=2, max_value=8))
    keys = draw(
        st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz_0123456789",
                min_size=1,
                max_size=6,
            ),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    stamps = draw(
        st.lists(
            st.tuples(st.integers(0, 50), st.integers(0, 4)),
            unique=True,
            min_size=n,
            max_size=n,
        )
    )
    values = draw(st.lists(st.text(max_size=10), min_size=n, max_size=n))
    return [MetadataOp(k, v, c, s) for k, v, (c, s) in zip(keys, values, stamps)]


def _apply_stream(ops, *, site_id):
    """Fold single-op updates through a fresh RealtimeState onto a live document."""
    live = _doc(width=2 * TILE, height=TILE)
    state = RealtimeState()
    for op in ops:
        apply_remote(live, encode_update([op]), site_id=site_id, state=state)
    return live


@settings(max_examples=120)
@given(ops=_metadata_op_sets(), data=st.data())
def test_metadata_keys_converge_byte_identical_regardless_of_arrival_order(ops, data):
    """Regression: metadata keys arriving in NON-sorted order serialise to a
    BYTE-IDENTICAL ``.pixproj`` through the realtime apply path.

    ``serialize_project(forward) == serialize_project(reversed) ==
    serialize_project(batch converge)`` — a RAW ``.pixproj`` byte comparison
    (stronger than the ``_semantic`` sorted-items fingerprint), plus an arbitrary
    Hypothesis-drawn delivery permutation, and a check that the metadata dict itself
    serialises in canonical (sorted) key order.
    """
    base = _doc(width=2 * TILE, height=TILE)
    batch_bytes = _ser(converge(base, list(ops), site_id=1))

    forward = _apply_stream(ops, site_id=2)
    reverse = _apply_stream(list(reversed(ops)), site_id=3)
    permuted = _apply_stream(data.draw(st.permutations(ops)), site_id=4)

    forward_bytes = _ser(forward)

    # RAW .pixproj byte identity across forward / reversed / permuted / batch.
    assert forward_bytes == batch_bytes
    assert _ser(reverse) == batch_bytes
    assert _ser(permuted) == batch_bytes

    # The metadata dict itself is canonically sorted (byte-level SEC precondition).
    assert list(forward.metadata.keys()) == sorted(forward.metadata.keys())
    # Every winning key/value round-trips (distinct keys => all ops survive).
    for op in ops:
        assert forward.metadata[op.key] == op.value


def test_realtime_metadata_non_sorted_arrival_is_byte_identical_concrete():
    """Concrete regression: keys delivered in reverse-alphabetical order still
    serialise byte-identically to the sorting batch converge, and canonically sorted.
    """
    base = _doc(width=2 * TILE, height=TILE)
    # Deliberately NON-sorted arrival order ("zeta" before "alpha").
    ops = [
        MetadataOp("zeta", "z", 1, 0),
        MetadataOp("mid", "m", 2, 0),
        MetadataOp("alpha", "a", 3, 0),
    ]
    batch_bytes = _ser(converge(base, list(ops), site_id=1))
    live = _apply_stream(ops, site_id=2)
    assert _ser(live) == batch_bytes
    assert list(live.metadata.keys()) == ["alpha", "mid", "zeta"]


# --------------------------------------------------------------------------- #
# Branching.
# --------------------------------------------------------------------------- #


def test_branch_rejects_non_document():
    with pytest.raises(RealtimeError):
        branch("not a document")


@pytest.mark.parametrize("bad_site", [True, -1])
def test_branch_rejects_bad_site_id(bad_site):
    with pytest.raises(RealtimeError):
        branch(_doc(), site_id=bad_site)


def test_branch_forks_an_independent_snapshot():
    doc = _doc()
    b = branch(doc, site_id=1)
    assert isinstance(b, Branch)
    assert b.base is not doc
    # Mutating the original does not touch the fork's base.
    doc.metadata["k"] = "changed"
    assert "k" not in b.base.metadata


def test_branch_record_preserves_history():
    b = branch(_doc(), site_id=1)
    ops1 = [MetadataOp("a", "1", 1, 1)]
    ops2 = [MetadataOp("b", "2", 2, 1)]
    b.record(ops1)
    b.record(ops2)
    assert list(b.ops) == ops1 + ops2  # ordered op-log reconstructable


def test_branch_record_rejects_over_op_cap():
    b = branch(_doc(), site_id=1)
    with pytest.raises(RealtimeError):
        b.record([MetadataOp("k", str(i), i, 1) for i in range(4097)])


def test_branch_document_materialises_converge():
    b = branch(_doc(), site_id=1)
    b.record([MetadataOp("title", "on-branch", 1, 1)])
    assert b.document().metadata["title"] == "on-branch"


def test_fork_diverge_merge_is_conflict_free():
    base = _doc()
    mainline = branch(base, site_id=0)
    feature = branch(base, site_id=1)
    # Divergent edits to different registers both survive the merge.
    mainline.record([MetadataOp("title", "main", 1, 0)])
    feature.record([LayerAttrOp(0, 2, "opacity", 0.5, 1, 1)])
    merged = merge(mainline, feature)
    assert merged.metadata["title"] == "main"
    by_id = {n.layer_id: n for n in merged.frames[0].layers}
    assert by_id[2].opacity == pytest.approx(0.5)


def test_merge_is_order_independent():
    base = _doc()
    b1 = branch(base, site_id=0)
    b2 = branch(base, site_id=1)
    b1.record([MetadataOp("k", "from-b1", 4, 0)])
    b2.record([MetadataOp("k", "from-b2", 7, 1)])  # higher stamp wins either way
    # merge anchors on mainline.base; both branches share the same base, so the union
    # of op-logs converges identically regardless of which branch is named first.
    assert _ser(merge(b1, b2)) == _ser(merge(b2, b1))
    assert merge(b1, b2).metadata["k"] == "from-b2"


def test_concurrent_same_register_branches_converge_by_tiebreak():
    base = _doc()
    b1 = branch(base, site_id=0)
    b2 = branch(base, site_id=0)
    b1.record([MetadataOp("k", "lo", 3, 0)])
    b2.record([MetadataOp("k", "hi", 8, 0)])
    assert merge(b1, b2).metadata["k"] == "hi"


def test_merge_requires_two_branches():
    b = branch(_doc(), site_id=0)
    with pytest.raises(RealtimeError):
        merge(b, "not a branch")  # type: ignore[arg-type]
    with pytest.raises(RealtimeError):
        merge("not a branch", b)  # type: ignore[arg-type]
