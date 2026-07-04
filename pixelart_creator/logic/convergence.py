"""Deterministic HYBRID convergence model for a ``.pixproj`` (zero Qt, S11).

Phase-10 Slice B (ADR-0028 §1/§2/§3; spec REQ-P10-LOGIC-006, CL-B5). Concurrent edits
to a :class:`~pixelart_creator.logic.document.Document` converge **deterministically**
via a **hybrid** model, split by data kind:

* **Structured metadata** (document metadata, layer names/attributes, top-level layer
  order per frame) converges through a **sequence/tree CRDT** — ``pycrdt`` (the Python
  bindings to ``y-crdt``/``yrs``, the Rust port of Yjs). The converged structured state
  is materialised into an opaque, transportable CRDT update blob (the per-project
  **sidecar** state, BF-4 — never embedded in the ``.pixproj``).
* **Raster pixel buffers** converge through **per-tile / per-region last-writer-wins
  (LWW)**: the canvas is partitioned into ``CRDT_TILE_SIZE_PX`` tiles; each tile is an
  LWW-Register keyed by ``(logical_clock, site_id)``. Concurrent edits to *different*
  tiles both survive; concurrent edits to the *same* tile resolve by the
  ``(logical_clock, site_id)`` tiebreak. Tile partitioning (not per-pixel CRDT
  metadata) makes the model **8K-scalable**.

**Determinism contract (REQ-P10-LOGIC-006, SC-L006-1):** :func:`converge` is a pure
function of ``(base, ops)`` — it reads no wall-clock, no randomness, no locale. Given
the same set of operations, applying them in **any (permuted) order** yields a
**byte-identical** ``Document`` (strong eventual consistency): the structured winners
are resolved by a total ``(logical_clock, site_id)`` order (sort-stable, so input order
is irrelevant), pycrdt merges commutatively, and the raster LWW picks the same winner
per tile regardless of order.

The :class:`Operation` vocabulary (module-local frozen dataclasses, ADR-0001) is the
unit both this Slice-B batch model and the Slice-C real-time apply layer
(``logic/realtime_apply.py``) reconcile over the shipped ``Document`` (DOC-1) — the
reconciliation of the shipped ``logic/history.py`` command stream (HIS-1). Numeric
bounds come from :mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from pycrdt import Doc, Map

from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.document import (
    Document,
    Frame,
    Layer,
    LayerGroup,
    LayerNode,
)
from pixelart_creator.logic.pixel_buffer import ColorMode

__all__ = [
    "ConvergenceError",
    "MetadataOp",
    "LayerAttrOp",
    "LayerOrderOp",
    "RasterOp",
    "Operation",
    "LAYER_ATTRS",
    "converge",
    "apply_operations",
    "make_raster_op",
    "structured_sidecar",
]


class ConvergenceError(ValueError):
    """Raised on an ill-formed operation or an operation that cannot be applied."""


#: The convergeable per-node structured attributes (deterministic LWW registers).
#: Kept module-local (enumerated vocabulary, ADR-0001).
LAYER_ATTRS = frozenset({"name", "opacity", "visible", "locked"})

#: A structured layer-attribute value (per :data:`LAYER_ATTRS`).
LayerAttrValue = Union[str, float, bool, int]

#: A value stored in the structured CRDT map (attributes + a layer-order list).
_StructuredValue = Union[str, float, bool, int, List[int]]

#: A deterministic total-order key for LWW resolution: higher wins.
_OrderKey = Tuple[int, int]


def _require_nonneg_int(value: object, name: str) -> int:
    """Return ``value`` as a non-negative int, or raise :class:`ConvergenceError`."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConvergenceError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise ConvergenceError(f"{name} must be >= 0, got {value}")
    return value


@dataclass(frozen=True)
class MetadataOp:
    """Set a ``Document.metadata`` key — a structured LWW register (str value)."""

    key: str
    value: str
    logical_clock: int
    site_id: int

    def __post_init__(self) -> None:
        """Validate the key/value types and the ordering stamp."""
        if not isinstance(self.key, str) or not self.key:
            raise ConvergenceError(
                f"metadata key must be a non-empty str, {self.key!r}"
            )
        if not isinstance(self.value, str):
            raise ConvergenceError(f"metadata value must be a str, got {self.value!r}")
        _require_nonneg_int(self.logical_clock, "logical_clock")
        _require_nonneg_int(self.site_id, "site_id")


@dataclass(frozen=True)
class LayerAttrOp:
    """Set a layer/group attribute (:data:`LAYER_ATTRS`) — a structured LWW register.

    Targets the node with stable ``layer_id`` in ``frame_index``. Concurrent writes to
    the same ``(frame_index, layer_id, attr)`` resolve by ``(logical_clock, site_id)``.
    """

    frame_index: int
    layer_id: int
    attr: str
    value: LayerAttrValue
    logical_clock: int
    site_id: int

    def __post_init__(self) -> None:
        """Validate the target, the attribute name, and the ordering stamp."""
        _require_nonneg_int(self.frame_index, "frame_index")
        if isinstance(self.layer_id, bool) or not isinstance(self.layer_id, int):
            raise ConvergenceError(f"layer_id must be an int, got {self.layer_id!r}")
        if self.layer_id <= 0:
            raise ConvergenceError(f"layer_id must be positive, got {self.layer_id}")
        if self.attr not in LAYER_ATTRS:
            raise ConvergenceError(
                f"attr {self.attr!r} is not one of {sorted(LAYER_ATTRS)}"
            )
        _require_nonneg_int(self.logical_clock, "logical_clock")
        _require_nonneg_int(self.site_id, "site_id")


@dataclass(frozen=True)
class LayerOrderOp:
    """Set the top-level layer order of a frame — the sequence-CRDT ordering register.

    ``order`` is a tuple of top-level node ``layer_id`` s in the desired z-order.
    Concurrent reorders converge deterministically via the ``(logical_clock, site_id)``
    tiebreak (the sequence-CRDT commutativity contract for ordering).
    """

    frame_index: int
    order: Tuple[int, ...]
    logical_clock: int
    site_id: int

    def __post_init__(self) -> None:
        """Validate the frame index, the order tuple, and the ordering stamp."""
        _require_nonneg_int(self.frame_index, "frame_index")
        if not isinstance(self.order, tuple):
            raise ConvergenceError(f"order must be a tuple, got {self.order!r}")
        for lid in self.order:
            if isinstance(lid, bool) or not isinstance(lid, int) or lid <= 0:
                raise ConvergenceError(
                    f"order layer_id must be a positive int, {lid!r}"
                )
        if len(set(self.order)) != len(self.order):
            raise ConvergenceError(f"order has duplicate layer_ids: {self.order}")
        _require_nonneg_int(self.logical_clock, "logical_clock")
        _require_nonneg_int(self.site_id, "site_id")


@dataclass(frozen=True)
class RasterOp:
    """A raster edit to one tile of a layer buffer — an LWW-Register (ADR-0028 §2).

    ``pixels`` is the raw ``uint8`` bytes of the ``tile_height`` x ``tile_width`` tile
    at tile index ``(tile_x, tile_y)`` (edge tiles are smaller than
    ``CRDT_TILE_SIZE_PX``). Concurrent edits to the same
    ``(frame_index, layer_id, tile_x, tile_y)`` resolve by ``(logical_clock, site_id)``;
    different tiles both survive. Build one with :func:`make_raster_op`.
    """

    frame_index: int
    layer_id: int
    tile_x: int
    tile_y: int
    pixels: bytes
    tile_width: int
    tile_height: int
    logical_clock: int
    site_id: int

    def __post_init__(self) -> None:
        """Validate tile geometry, payload size, and the ordering stamp."""
        _require_nonneg_int(self.frame_index, "frame_index")
        if isinstance(self.layer_id, bool) or not isinstance(self.layer_id, int):
            raise ConvergenceError(f"layer_id must be an int, got {self.layer_id!r}")
        if self.layer_id <= 0:
            raise ConvergenceError(f"layer_id must be positive, got {self.layer_id}")
        _require_nonneg_int(self.tile_x, "tile_x")
        _require_nonneg_int(self.tile_y, "tile_y")
        if self.tile_width <= 0 or self.tile_width > CRDT_TILE_SIZE_PX:
            raise ConvergenceError(
                f"tile_width must be in 1..{CRDT_TILE_SIZE_PX}, got {self.tile_width}"
            )
        if self.tile_height <= 0 or self.tile_height > CRDT_TILE_SIZE_PX:
            raise ConvergenceError(
                f"tile_height must be in 1..{CRDT_TILE_SIZE_PX}, got {self.tile_height}"
            )
        if not isinstance(self.pixels, (bytes, bytearray)):
            raise ConvergenceError(f"pixels must be bytes, got {self.pixels!r}")
        cells = self.tile_width * self.tile_height
        if len(self.pixels) not in (cells, cells * 4):
            raise ConvergenceError(
                f"pixels length {len(self.pixels)} matches neither indexed "
                f"({cells}) nor RGBA ({cells * 4}) for a "
                f"{self.tile_width}x{self.tile_height} tile"
            )
        _require_nonneg_int(self.logical_clock, "logical_clock")
        _require_nonneg_int(self.site_id, "site_id")


#: A single convergence operation.
Operation = Union[MetadataOp, LayerAttrOp, LayerOrderOp, RasterOp]


def make_raster_op(
    buffer: np.ndarray,
    *,
    frame_index: int,
    layer_id: int,
    tile_x: int,
    tile_y: int,
    logical_clock: int,
    site_id: int,
) -> RasterOp:
    """Extract the ``(tile_x, tile_y)`` tile of a buffer array into a :class:`RasterOp`.

    ``buffer`` is a layer's backing ``uint8`` NumPy array — shape ``(H, W, 4)`` (RGBA)
    or ``(H, W)`` (indexed), i.e. ``layer.buffer.data``. The tile is
    ``CRDT_TILE_SIZE_PX``-partitioned; the edge tile is clipped to the buffer bounds.

    Raises:
        ConvergenceError: If the tile lies fully outside the buffer, or the array is
            not a 2-D indexed / 3-D RGBA ``uint8`` array.
    """
    arr = np.asarray(buffer)
    if arr.dtype != np.uint8 or arr.ndim not in (2, 3):
        raise ConvergenceError("buffer must be a uint8 (H,W) or (H,W,4) array")
    height = int(arr.shape[0])
    width = int(arr.shape[1])
    x0 = tile_x * CRDT_TILE_SIZE_PX
    y0 = tile_y * CRDT_TILE_SIZE_PX
    if x0 >= width or y0 >= height:
        raise ConvergenceError(f"tile ({tile_x}, {tile_y}) is outside the buffer")
    tw = min(CRDT_TILE_SIZE_PX, width - x0)
    th = min(CRDT_TILE_SIZE_PX, height - y0)
    tile = np.ascontiguousarray(arr[y0 : y0 + th, x0 : x0 + tw])
    return RasterOp(
        frame_index=frame_index,
        layer_id=layer_id,
        tile_x=tile_x,
        tile_y=tile_y,
        pixels=tile.tobytes(),
        tile_width=tw,
        tile_height=th,
        logical_clock=logical_clock,
        site_id=site_id,
    )


def _find_node(frame: Frame, layer_id: int) -> Optional[LayerNode]:
    """Return the node with stable ``layer_id`` in a frame tree, or ``None``."""

    def _walk(nodes: Sequence[LayerNode]) -> Optional[LayerNode]:
        for node in nodes:
            if node.layer_id == layer_id:
                return node
            if isinstance(node, LayerGroup):
                found = _walk(node.children)
                if found is not None:
                    return found
        return None

    return _walk(frame.layers)


def _resolve_structured_winners(
    ops: Sequence[Operation],
) -> Dict[str, _StructuredValue]:
    """Resolve structured LWW registers into a flat, deterministic winner map.

    Keys are composite strings (``"meta:<k>"``, ``"attr:<frame>:<lid>:<attr>"``,
    ``"order:<frame>"``); each maps to the value of the op with the highest
    ``(logical_clock, site_id)`` for that key. Order-independent: the input is scanned
    once and a strictly-greater key replaces the incumbent, so any permutation yields
    the same winners.
    """
    winners: Dict[str, _StructuredValue] = {}
    stamps: Dict[str, _OrderKey] = {}

    def _offer(key: str, value: _StructuredValue, stamp: _OrderKey) -> None:
        current = stamps.get(key)
        if current is None or stamp > current:
            winners[key] = value
            stamps[key] = stamp

    for op in ops:
        if isinstance(op, MetadataOp):
            _offer(f"meta:{op.key}", op.value, (op.logical_clock, op.site_id))
        elif isinstance(op, LayerAttrOp):
            _offer(
                f"attr:{op.frame_index}:{op.layer_id}:{op.attr}",
                op.value,
                (op.logical_clock, op.site_id),
            )
        elif isinstance(op, LayerOrderOp):
            _offer(
                f"order:{op.frame_index}",
                list(op.order),  # stored as a plain list value in the CRDT map
                (op.logical_clock, op.site_id),
            )
    return winners


def structured_sidecar(ops: Sequence[Operation]) -> bytes:
    """Encode the converged structured state into an opaque pycrdt update (BF-4).

    Resolves the structured LWW winners deterministically, writes them into a
    ``pycrdt`` document (the sequence/tree CRDT), and returns its encoded update — the
    per-project **sidecar** collaboration state (never embedded in the ``.pixproj``).
    The returned bytes are an opaque CRDT blob; :func:`converge` re-decodes them to
    materialise the structured metadata. A fixed ``client_id`` keeps the encoding
    reproducible.
    """
    winners = _resolve_structured_winners(ops)
    doc: Doc = Doc(client_id=0)
    doc["structured"] = Map()
    struct: Map = doc["structured"]
    with doc.transaction():
        for key in sorted(winners):
            struct[key] = winners[key]
    return bytes(doc.get_update())


def _decode_structured(blob: bytes) -> Dict[str, object]:
    """Decode a :func:`structured_sidecar` blob back into a plain winner mapping."""
    doc: Doc = Doc(client_id=0)
    doc["structured"] = Map()
    doc.apply_update(blob)
    struct: Map = doc["structured"]
    return {key: struct[key] for key in struct.keys()}


def _apply_layer_attr(node: LayerNode, attr: str, value: object) -> None:
    """Apply a converged structured attribute to a node (validated by the setter)."""
    if attr == "name":
        node.name = str(value)
    elif attr == "opacity":
        node.opacity = float(value)  # type: ignore[arg-type]
    elif attr == "visible":
        node.visible = bool(value)
    elif attr == "locked":
        node.locked = bool(value)
    else:  # pragma: no cover - guarded at op construction (LAYER_ATTRS)
        raise ConvergenceError(f"unknown layer attribute {attr!r}")


def _reorder_top_level(frame: Frame, order: Sequence[int]) -> None:
    """Reorder ``frame.layers`` (top level) to match ``order`` (by ``layer_id``).

    Nodes named in ``order`` come first in that order; any top-level node not named
    keeps its relative position, appended after — a deterministic, total reordering.
    """
    by_id: Dict[int, LayerNode] = {n.layer_id: n for n in frame.layers}
    new_layers: List[LayerNode] = []
    placed: set[int] = set()
    for lid in order:
        node = by_id.get(int(lid))
        if node is not None and node.layer_id not in placed:
            new_layers.append(node)
            placed.add(node.layer_id)
    for node in frame.layers:
        if node.layer_id not in placed:
            new_layers.append(node)
            placed.add(node.layer_id)
    frame.layers = new_layers


def _apply_structured(result: Document, blob: bytes) -> None:
    """Materialise the decoded structured winners onto ``result`` (deterministic)."""
    decoded = _decode_structured(blob)
    # metadata first, then attrs, then order — deterministic key sort within each kind.
    meta_written = False
    for key in sorted(decoded):
        value = decoded[key]
        if key.startswith("meta:"):
            result.metadata[key[len("meta:") :]] = str(value)
            meta_written = True
    if meta_written:
        # Canonicalise the metadata key order (sorted) so the serialised ``.pixproj``
        # is byte-identical no matter how the ops were chunked across apply calls. The
        # batch :func:`converge` inserts every winning key in one sorted pass, but the
        # Slice-C realtime path (:mod:`realtime_apply`) folds patches one at a time,
        # appending new keys in arrival order; re-sorting the whole dict here (subset-
        # invariant and idempotent) makes the incremental path converge byte-identically
        # to the batch path (byte-level SEC, not just logical-state convergence).
        result.metadata = {k: result.metadata[k] for k in sorted(result.metadata)}
    for key in sorted(decoded):
        if not key.startswith("attr:"):
            continue
        _, frame_s, lid_s, attr = key.split(":", 3)
        frame_index = int(frame_s)
        if not 0 <= frame_index < len(result.frames):
            continue
        node = _find_node(result.frames[frame_index], int(lid_s))
        if node is not None:
            _apply_layer_attr(node, attr, decoded[key])
    for key in sorted(decoded):
        if not key.startswith("order:"):
            continue
        frame_index = int(key[len("order:") :])
        if not 0 <= frame_index < len(result.frames):
            continue
        raw_order = decoded[key]
        if isinstance(raw_order, (list, tuple)):
            _reorder_top_level(
                result.frames[frame_index], [int(round(float(v))) for v in raw_order]
            )


def _apply_raster(result: Document, ops: Sequence[RasterOp]) -> None:
    """Apply the winning tile per ``(frame, layer, tile)`` by the LWW tiebreak."""
    # Winner per tile: highest (logical_clock, site_id); final content bytes as a
    # total-order tiebreak so an exact stamp collision is still deterministic.
    winners: Dict[Tuple[int, int, int, int], RasterOp] = {}
    for op in ops:
        tile_key = (op.frame_index, op.layer_id, op.tile_x, op.tile_y)
        incumbent = winners.get(tile_key)
        if incumbent is None or (
            (op.logical_clock, op.site_id, op.pixels)
            > (incumbent.logical_clock, incumbent.site_id, incumbent.pixels)
        ):
            winners[tile_key] = op

    for tile_key in sorted(winners):
        op = winners[tile_key]
        if not 0 <= op.frame_index < len(result.frames):
            raise ConvergenceError(f"raster op frame {op.frame_index} out of range")
        node = _find_node(result.frames[op.frame_index], op.layer_id)
        if not isinstance(node, Layer):
            raise ConvergenceError(
                f"raster op targets layer_id {op.layer_id}, "
                f"which is not a paintable leaf layer"
            )
        arr = node.buffer.data
        x0 = op.tile_x * CRDT_TILE_SIZE_PX
        y0 = op.tile_y * CRDT_TILE_SIZE_PX
        if x0 + op.tile_width > arr.shape[1] or y0 + op.tile_height > arr.shape[0]:
            raise ConvergenceError(
                f"raster tile ({op.tile_x}, {op.tile_y}) exceeds the layer buffer"
            )
        channels = 4 if node.buffer.mode is ColorMode.RGBA else 1
        expected = op.tile_width * op.tile_height * channels
        if len(op.pixels) != expected:
            raise ConvergenceError(
                f"raster tile payload {len(op.pixels)} bytes does not match the "
                f"{node.buffer.mode.value} layer ({expected} expected)"
            )
        flat = np.frombuffer(op.pixels, dtype=np.uint8)
        tile: np.ndarray
        if channels == 4:
            tile = flat.reshape(op.tile_height, op.tile_width, 4)
        else:
            tile = flat.reshape(op.tile_height, op.tile_width)
        arr[y0 : y0 + op.tile_height, x0 : x0 + op.tile_width] = tile


def apply_operations(document: Document, ops: Sequence[Operation]) -> None:
    """Apply a set of operations onto ``document`` **in place** (no deep copy).

    This is the deterministic core :func:`converge` runs after cloning ``base``,
    exposed as a public seam so the Slice-C real-time apply layer
    (:mod:`pixelart_creator.logic.realtime_apply`) can fold an inbound patch onto
    the **live** ``Document`` without the (8K-scale, ~126 MB) deep copy — Article VI
    per-frame re-entry (ADR-0027 §7). Only the tiles/nodes named in ``ops`` are
    touched (the hybrid model is dirty-region-scoped by construction), so a single
    remote-patch apply is bounded by the size of the patch, not the canvas.

    The winner resolution is identical to :func:`converge`: structured LWW registers
    resolve by the total ``(logical_clock, site_id)`` order, and each raster tile
    resolves to the same winner regardless of order — so applying a batch here is
    order-independent (strong eventual consistency).

    Args:
        document: The document to mutate in place (must be a ``Document``).
        ops: The operations to apply (any order).

    Raises:
        ConvergenceError: If ``document`` is not a ``Document`` or an op cannot be
            applied (e.g. a raster op targets a missing / non-leaf layer).
    """
    if not isinstance(document, Document):
        raise ConvergenceError(f"document must be a Document, got {document!r}")

    raster_ops: List[RasterOp] = []
    structured_ops: List[Operation] = []
    for op in ops:
        if isinstance(op, RasterOp):
            raster_ops.append(op)
        elif isinstance(op, (MetadataOp, LayerAttrOp, LayerOrderOp)):
            structured_ops.append(op)
        else:
            raise ConvergenceError(f"unknown operation type: {op!r}")

    _apply_structured(document, structured_sidecar(structured_ops))
    _apply_raster(document, raster_ops)


def converge(base: Document, ops: Sequence[Operation], *, site_id: int) -> Document:
    """Converge a set of concurrent operations onto ``base`` deterministically.

    Applies the hybrid model (ADR-0028): structured metadata (document metadata, layer
    attributes, top-level order) converges through the ``pycrdt`` sequence/tree CRDT;
    raster tiles converge through per-tile ``(logical_clock, site_id)`` last-writer-wins
    (``CRDT_TILE_SIZE_PX`` partition). The result is a **new** ``Document`` (``base`` is
    never mutated).

    **Determinism (REQ-P10-LOGIC-006):** the returned ``Document`` is byte-identical for
    any permutation of ``ops`` — structured winners are resolved by a total
    ``(logical_clock, site_id)`` order, pycrdt merges commutatively, and each tile
    resolves to the same winner regardless of order. No wall-clock, randomness, or
    locale is read.

    Args:
        base: The starting document (deep-copied; not mutated).
        ops: The concurrent operations to converge (any order).
        site_id: The local replica id requesting convergence (a non-negative int). It
            identifies the caller and does **not** affect the converged result — the
            outcome is a pure function of ``(base, ops)`` (strong eventual consistency).

    Returns:
        A new, converged :class:`Document`.

    Raises:
        ConvergenceError: If ``base`` is not a ``Document``, ``site_id`` is invalid, or
            an op cannot be applied to the converged structure (e.g. a raster op targets
            a missing / non-leaf layer).
    """
    if not isinstance(base, Document):
        raise ConvergenceError(f"base must be a Document, got {base!r}")
    _require_nonneg_int(site_id, "site_id")

    result: Document = copy.deepcopy(base)
    apply_operations(result, ops)
    return result
