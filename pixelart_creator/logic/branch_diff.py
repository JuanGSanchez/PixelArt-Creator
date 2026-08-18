"""Pre-merge branch divergence + op-log supervision (zero Qt, S11).

Phase 10 slice ``phase-10-branch-diff`` (plan §3, §4). Two pure, read-only
derivations over the shipped git-like branching model
(:mod:`pixelart_creator.logic.realtime_apply`):

* :func:`derive_divergence` (``REQ-P10-LOGIC-008``) — what a source branch's
  op-log would add to its merge target, presented two ways: an op-level tier
  (every diverging operation, grouped by class and by target) and a
  region-level tier (the raster changes as buffer-space rectangles, via
  :func:`~pixelart_creator.logic.realtime_apply.regions_for_ops` — the **same**
  tile->rect mapping the real-time apply path uses, not a copy of it).
* :func:`supervise` (``REQ-P10-LOGIC-009``) — materialises a branch's op-log
  (``converge(base, ops)``, the shipped algorithm, unchanged) and compares it
  against a **caller-supplied live document** (plan §3.2: ``Branch.document()``
  *is* that same materialisation, so a one-argument form could never disagree
  with itself). Reports, never repairs: ``unaccounted`` is a value, never an
  exception, and names the differing frames, layers, attributes, metadata keys
  and raster tiles.

Neither derivation mutates its arguments, and neither changes the merge
algorithm (``logic/convergence.converge`` / ``logic/realtime_apply.merge`` are
not imported for their side effects, only called read-only). Numeric bounds
come from :mod:`pixelart_creator.logic.constants` (S12); ``CRDT_TILE_SIZE_PX``
is read at every raster comparison, never inlined.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Type

import numpy as np

from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import (
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    Operation,
    RasterOp,
)
from pixelart_creator.logic.document import (
    Document,
    Frame,
    Layer,
    LayerGroup,
    LayerNode,
)
from pixelart_creator.logic.realtime_apply import (
    Branch,
    DirtyRegion,
    RealtimeError,
    regions_for_ops,
)

__all__ = [
    "OpEntry",
    "BranchDivergence",
    "SupervisionResult",
    "derive_divergence",
    "supervise",
]

#: Total order over op classes for :class:`BranchDivergence` op-tier sorting —
#: the declaration order of the convergence ``Operation`` union
#: (``convergence.py:228``).
_CLASS_RANK: Dict[Type[Operation], int] = {
    MetadataOp: 0,
    LayerAttrOp: 1,
    LayerOrderOp: 2,
    RasterOp: 3,
}

#: Human-readable class name per op type, for Tier-1 grouping/display.
_CLASS_NAME: Dict[Type[Operation], str] = {
    MetadataOp: "metadata",
    LayerAttrOp: "layer_attr",
    LayerOrderOp: "layer_order",
    RasterOp: "raster",
}

#: The mutable node attributes compared by :func:`supervise` (a superset of
#: ``convergence.LAYER_ATTRS``: ``blend_mode`` is included because supervision
#: must be able to catch *any* unrecorded change, ``SC-L009-4``, even one the
#: convergence model has no op class for — plan risk R-1).
_COMPARED_ATTRS: Tuple[str, ...] = (
    "name",
    "opacity",
    "visible",
    "locked",
    "blend_mode",
)


def _op_target(op: Operation) -> Tuple[object, ...]:
    """Return the target tuple an op is grouped/sorted by (Tier 1)."""
    if isinstance(op, MetadataOp):
        return (op.key,)
    if isinstance(op, LayerAttrOp):
        return (op.frame_index, op.layer_id, op.attr)
    if isinstance(op, LayerOrderOp):
        return (op.frame_index,)
    if isinstance(op, RasterOp):
        return (op.frame_index, op.layer_id, op.tile_x, op.tile_y)
    raise RealtimeError(f"unknown operation type: {op!r}")  # pragma: no cover


@dataclass(frozen=True)
class OpEntry:
    """One Tier-1 divergence row: one diverging operation, rendered for display.

    Attributes:
        op: The diverging :mod:`~pixelart_creator.logic.convergence` operation.
        op_class: Its class name (``"metadata"``, ``"layer_attr"``,
            ``"layer_order"`` or ``"raster"``).
        target: The op's target, rendered as a tuple for grouping/sorting.
        region: The buffer-space rectangle this op touches, or ``None`` for a
            non-raster op (task T11: "non-raster ops produce no region").
    """

    op: Operation
    op_class: str
    target: Tuple[object, ...]
    region: Optional[DirtyRegion]


@dataclass(frozen=True)
class BranchDivergence:
    """The two-tier pre-merge divergence of a source branch against a target.

    ``is_empty`` is a first-class result (``SC-L008-5``): a source identical to
    its target reports both tiers empty rather than raising.

    Attributes:
        ops: Every diverging operation, ordered by ``(class rank, target)``
            (a deterministic total order, ``SC-L008-4``).
        regions: The raster rectangles the diverging ``RasterOp`` s touch,
            ordered ``(frame_index, layer_id, y, x)``
            (:func:`~pixelart_creator.logic.realtime_apply.regions_for_ops`).
        total: ``len(ops)`` — the same number the post-merge summary reports.
        distinct_targets: The count of distinct ``target`` tuples across
            ``ops``.
        is_empty: Whether there is no divergence at all.
    """

    ops: Tuple[OpEntry, ...]
    regions: Tuple[DirtyRegion, ...]
    total: int
    distinct_targets: int
    is_empty: bool


@dataclass(frozen=True)
class SupervisionResult:
    """The ``REQ-P10-LOGIC-009`` verdict: does the op-log explain the live document?

    ``accounted`` is ``True`` when the branch's materialised op-log
    (``converge(base, ops)``) matches the caller-supplied live document
    exactly. When it is ``False``, the remaining fields locate every
    difference found — a *value*, never an exception (``SC-L009-2``,
    ``SC-L009-4``).

    Attributes:
        accounted: Whether the op-log fully explains the live document.
        frames: Frame indices present in one document but not the other
            (a frame-count mismatch).
        layers: ``(frame_index, layer_id)`` pairs whose structural presence or
            top-level position differs.
        attrs: ``(frame_index, layer_id, attr)`` triples whose value differs
            (``attr`` is one of the compared node attributes).
        metadata_keys: ``Document.metadata`` keys whose value differs.
        tiles: ``(frame_index, layer_id, tile_x, tile_y)`` tuples whose raster
            content differs, at ``CRDT_TILE_SIZE_PX`` granularity.
    """

    accounted: bool
    frames: Tuple[int, ...]
    layers: Tuple[Tuple[int, int], ...]
    attrs: Tuple[Tuple[int, int, str], ...]
    metadata_keys: Tuple[str, ...]
    tiles: Tuple[Tuple[int, int, int, int], ...]


def derive_divergence(source: Branch, target: Branch) -> BranchDivergence:
    """Derive the two-tier pre-merge divergence of ``source`` against ``target``.

    The divergence is what ``source``'s op-log carries that ``target``'s does
    not (multiset difference over the op-logs — exactly what a merge of
    ``source`` into ``target`` would add). Deterministic regardless of the
    op-logs' internal order (``SC-L008-4``): ties are broken by the fixed
    ``(class rank, target)`` order, never by list position.

    Args:
        source: The branch being compared (typically the feature branch).
        target: The merge target (typically the mainline).

    Returns:
        The two-tier :class:`BranchDivergence`; ``is_empty`` when there is
        none (``SC-L008-5``).

    Raises:
        RealtimeError: If ``source`` or ``target`` is not a :class:`Branch`.
    """
    if not isinstance(source, Branch) or not isinstance(target, Branch):
        raise RealtimeError("derive_divergence requires two Branch objects")

    remaining = Counter(target.ops)
    diverging: List[Operation] = []
    for op in source.ops:
        if remaining.get(op, 0) > 0:
            remaining[op] -= 1
        else:
            diverging.append(op)

    def _sort_key(op: Operation) -> Tuple[int, Tuple[object, ...]]:
        return (_CLASS_RANK[type(op)], _op_target(op))

    diverging.sort(key=_sort_key)

    raster_ops = tuple(op for op in diverging if isinstance(op, RasterOp))
    regions = regions_for_ops(raster_ops)
    region_by_tile = {
        (
            r.frame_index,
            r.layer_id,
            r.x // CRDT_TILE_SIZE_PX,
            r.y // CRDT_TILE_SIZE_PX,
        ): r
        for r in regions
    }

    entries = tuple(
        OpEntry(
            op=op,
            op_class=_CLASS_NAME[type(op)],
            target=_op_target(op),
            region=(
                region_by_tile.get((op.frame_index, op.layer_id, op.tile_x, op.tile_y))
                if isinstance(op, RasterOp)
                else None
            ),
        )
        for op in diverging
    )
    distinct_targets = len({entry.target for entry in entries})
    return BranchDivergence(
        ops=entries,
        regions=regions,
        total=len(entries),
        distinct_targets=distinct_targets,
        is_empty=len(entries) == 0,
    )


def _walk(nodes: Sequence[LayerNode]) -> Dict[int, LayerNode]:
    """Flatten a frame's node tree into ``{layer_id: node}`` (depth-first)."""
    out: Dict[int, LayerNode] = {}
    for node in nodes:
        out[node.layer_id] = node
        if isinstance(node, LayerGroup):
            out.update(_walk(node.children))
    return out


def _tiles_for_layer(node: Layer) -> "Sequence[Tuple[int, int]]":
    """Every ``(tile_x, tile_y)`` covering ``node``'s buffer, tile-partitioned."""
    height, width = node.buffer.data.shape[0], node.buffer.data.shape[1]
    n_tx = (width + CRDT_TILE_SIZE_PX - 1) // CRDT_TILE_SIZE_PX
    n_ty = (height + CRDT_TILE_SIZE_PX - 1) // CRDT_TILE_SIZE_PX
    return [(tx, ty) for ty in range(n_ty) for tx in range(n_tx)]


def _compare_frame(
    frame_index: int,
    materialised: Frame,
    live: Frame,
    layers: List[Tuple[int, int]],
    attrs: List[Tuple[int, int, str]],
    tiles: List[Tuple[int, int, int, int]],
) -> None:
    """Compare one frame pair, appending located differences to the out-lists."""
    order_a = tuple(n.layer_id for n in materialised.layers)
    order_b = tuple(n.layer_id for n in live.layers)
    if order_a != order_b:
        for lid in set(order_a) ^ set(order_b):
            layers.append((frame_index, lid))

    nodes_a = _walk(materialised.layers)
    nodes_b = _walk(live.layers)
    for lid in sorted(set(nodes_a) ^ set(nodes_b)):
        if (frame_index, lid) not in layers:
            layers.append((frame_index, lid))
    for lid in sorted(set(nodes_a) & set(nodes_b)):
        node_a = nodes_a[lid]
        node_b = nodes_b[lid]
        for attr in _COMPARED_ATTRS:
            if getattr(node_a, attr, None) != getattr(node_b, attr, None):
                attrs.append((frame_index, lid, attr))
        if isinstance(node_a, Layer) and isinstance(node_b, Layer):
            for tile_x, tile_y in _tiles_for_layer(node_a):
                x0, y0 = tile_x * CRDT_TILE_SIZE_PX, tile_y * CRDT_TILE_SIZE_PX
                arr_a = node_a.buffer.data
                arr_b = node_b.buffer.data
                block_a = arr_a[
                    y0 : y0 + CRDT_TILE_SIZE_PX, x0 : x0 + CRDT_TILE_SIZE_PX
                ]
                block_b = arr_b[
                    y0 : y0 + CRDT_TILE_SIZE_PX, x0 : x0 + CRDT_TILE_SIZE_PX
                ]
                if block_a.shape != block_b.shape or not np.array_equal(
                    block_a, block_b
                ):
                    tiles.append((frame_index, lid, tile_x, tile_y))


def supervise(branch: Branch, live: Document) -> SupervisionResult:
    """Materialise ``branch``'s op-log and compare it against ``live`` (LOGIC-009).

    Runs the shipped, unchanged
    :meth:`~pixelart_creator.logic.realtime_apply.Branch.document` (``converge``)
    and compares the result to the **caller-supplied** ``live`` document — the
    one the user is actually editing (plan §3.2), never the branch's own
    materialisation compared to itself, which could never disagree. Reports
    (never repairs): every difference located is returned as data.

    Args:
        branch: The branch whose op-log is supervised.
        live: The live document to compare against (supplied by ``ui/``).

    Returns:
        A :class:`SupervisionResult`; ``accounted`` is ``True`` iff every
        field is empty.

    Raises:
        RealtimeError: If ``branch`` is not a :class:`Branch` or ``live`` is
            not a :class:`Document`.
    """
    if not isinstance(branch, Branch):
        raise RealtimeError(f"branch must be a Branch, got {branch!r}")
    if not isinstance(live, Document):
        raise RealtimeError(f"live must be a Document, got {live!r}")

    materialised = branch.document()

    metadata_keys = tuple(
        sorted(
            k
            for k in set(materialised.metadata) | set(live.metadata)
            if materialised.metadata.get(k) != live.metadata.get(k)
        )
    )

    frames: List[int] = []
    layers: List[Tuple[int, int]] = []
    attrs: List[Tuple[int, int, str]] = []
    tiles: List[Tuple[int, int, int, int]] = []

    common = min(len(materialised.frames), len(live.frames))
    for i in range(common):
        _compare_frame(i, materialised.frames[i], live.frames[i], layers, attrs, tiles)
    for i in range(common, max(len(materialised.frames), len(live.frames))):
        frames.append(i)

    layers.sort()
    attrs.sort()
    tiles.sort()

    accounted = not (frames or layers or attrs or metadata_keys or tiles)
    return SupervisionResult(
        accounted=accounted,
        frames=tuple(sorted(frames)),
        layers=tuple(layers),
        attrs=tuple(attrs),
        metadata_keys=metadata_keys,
        tiles=tuple(tiles),
    )
