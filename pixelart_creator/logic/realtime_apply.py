"""Real-time CRDT apply layer + git-like art branching (zero Qt, S11).

Phase-10 Slice C (ADR-0028 §1/§3, ADR-0027 §7; spec REQ-P10-LOGIC-007). Two capabilities
over the shipped hybrid convergence model (:mod:`pixelart_creator.logic.convergence`):

1. **Real-time apply (REQ-P10-LOGIC-007).** :func:`apply_remote` folds an inbound,
   untrusted CRDT-update blob onto the **live** ``Document`` deterministically. It is
   built for **Article VI per-frame re-entry** (ADR-0027 §7, the AGT-10 FLAG-PERFRAME
   obligation): unlike the batch :func:`~pixelart_creator.logic.convergence.converge`
   (which deep-copies ``base`` — ~126 MB at 8K), it mutates the passed document **in
   place** via the dirty-region-scoped
   :func:`~pixelart_creator.logic.convergence.apply_operations`, so a single patch apply
   costs the size of the *patch*, not the canvas. :func:`dirty_regions` reports exactly
   which raster tiles a patch touches so AGT-10's overlay/redraw path can coalesce and
   redraw only those rects. A :class:`RealtimeState` carries the per-register LWW clocks
   across a stream so **out-of-order delivery still converges** (strong eventual
   consistency): a stale patch (older ``(logical_clock, site_id)`` than what is already
   applied) is dropped, never clobbering a newer edit.

2. **Git-like branching (REQ-P10-LOGIC-007).** :func:`branch` forks a document (clone +
   an empty ordered op-log); each fork records local edits; :func:`merge` converges the
   union of two forks' logs onto their shared base — **conflict-free**, no manual
   resolution (the CRDT/LWW merges), deterministic, and with the op-log preserved so the
   branch history is reconstructable (ADR-0028 §3).

The update blob is the op-codec output (:func:`encode_update` / :func:`decode_update`):
a versioned JSON envelope of the :class:`~pixelart_creator.logic.convergence.Operation`
vocabulary, raster pixels base64-encoded. It is **never** ``eval``/``exec``'d and is
size-capped (``validate_crdt_update``, ``MAX_CRDT_UPDATE_BYTES``) before decode
(Article VII). Numeric bounds come from
:mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

import base64
import copy
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from pixelart_creator.logic.cloud_validation import validate_crdt_update
from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
from pixelart_creator.logic.convergence import (
    LayerAttrOp,
    LayerOrderOp,
    MetadataOp,
    Operation,
    RasterOp,
    apply_operations,
    converge,
)
from pixelart_creator.logic.document import Document

__all__ = [
    "RealtimeError",
    "DirtyRegion",
    "RealtimeState",
    "Branch",
    "encode_update",
    "decode_update",
    "apply_remote",
    "dirty_regions",
    "regions_for_ops",
    "branch",
    "merge",
]

#: Wire-format version of a CRDT-update blob (the op-codec envelope).
_UPDATE_VERSION = 1

#: Defensive cap on the number of operations one update blob may carry — guards a
#: hostile blob with a pathological op count (Article VII). The whole blob is already
#: bounded by ``MAX_CRDT_UPDATE_BYTES``; this bounds the decoded op list. Intrinsic to
#: the codec, so module-local (not a tuning value).
_MAX_OPS_PER_UPDATE = 4096


class RealtimeError(ValueError):
    """Raised on an ill-formed real-time update, branch, or merge (Phase-1 convention).

    A subclass of ``ValueError``; a caller catches it and surfaces / rejects the
    real-time patch or branch operation without crashing (Article VII).
    """


@dataclass(frozen=True)
class DirtyRegion:
    """A raster rectangle a remote patch touches — the dirty-rect redraw unit (F4/F7).

    Given to AGT-10's per-frame overlay/redraw path so only the changed pixels are
    repainted after a remote apply (Article VI, ADR-0027 §7). Coordinates are in the
    target layer's buffer space (pixels).

    Attributes:
        frame_index: The frame the edited layer lives in.
        layer_id: The stable id of the edited leaf layer.
        x, y: Top-left of the touched tile in buffer pixels.
        width, height: Tile size in pixels (edge tiles are smaller than
            ``CRDT_TILE_SIZE_PX``).
    """

    frame_index: int
    layer_id: int
    x: int
    y: int
    width: int
    height: int


# --------------------------------------------------------------------------- #
# Operation codec (blob <-> ops). Deterministic, eval-free.
# --------------------------------------------------------------------------- #


def _encode_op(op: Operation) -> Dict[str, object]:
    """Encode one operation to a JSON-safe dict (raster pixels base64-encoded)."""
    if isinstance(op, MetadataOp):
        return {
            "t": "meta",
            "key": op.key,
            "value": op.value,
            "c": op.logical_clock,
            "s": op.site_id,
        }
    if isinstance(op, LayerAttrOp):
        return {
            "t": "attr",
            "frame": op.frame_index,
            "layer": op.layer_id,
            "attr": op.attr,
            "value": op.value,
            "c": op.logical_clock,
            "s": op.site_id,
        }
    if isinstance(op, LayerOrderOp):
        return {
            "t": "order",
            "frame": op.frame_index,
            "order": list(op.order),
            "c": op.logical_clock,
            "s": op.site_id,
        }
    if isinstance(op, RasterOp):
        return {
            "t": "raster",
            "frame": op.frame_index,
            "layer": op.layer_id,
            "tx": op.tile_x,
            "ty": op.tile_y,
            "tw": op.tile_width,
            "th": op.tile_height,
            "px": base64.b64encode(op.pixels).decode("ascii"),
            "c": op.logical_clock,
            "s": op.site_id,
        }
    raise RealtimeError(f"cannot encode unknown operation {op!r}")


def _decode_op(item: object) -> Operation:
    """Decode one JSON dict back into an ``Operation`` (validated at construction)."""
    if not isinstance(item, dict):
        raise RealtimeError(f"operation must be a mapping, got {item!r}")
    kind = item.get("t")
    try:
        if kind == "meta":
            return MetadataOp(
                key=item["key"],
                value=item["value"],
                logical_clock=item["c"],
                site_id=item["s"],
            )
        if kind == "attr":
            return LayerAttrOp(
                frame_index=item["frame"],
                layer_id=item["layer"],
                attr=item["attr"],
                value=item["value"],
                logical_clock=item["c"],
                site_id=item["s"],
            )
        if kind == "order":
            order = item["order"]
            if not isinstance(order, list):
                raise RealtimeError("order op 'order' must be a list")
            return LayerOrderOp(
                frame_index=item["frame"],
                order=tuple(order),
                logical_clock=item["c"],
                site_id=item["s"],
            )
        if kind == "raster":
            body = item["px"]
            if not isinstance(body, str):
                raise RealtimeError("raster op 'px' must be a base64 str")
            pixels = base64.b64decode(body, validate=True)
            return RasterOp(
                frame_index=item["frame"],
                layer_id=item["layer"],
                tile_x=item["tx"],
                tile_y=item["ty"],
                pixels=pixels,
                tile_width=item["tw"],
                tile_height=item["th"],
                logical_clock=item["c"],
                site_id=item["s"],
            )
    except KeyError as exc:
        raise RealtimeError(f"operation missing field {exc}") from exc
    except (ValueError, TypeError) as exc:
        # ConvergenceError (a ValueError) from a dataclass __post_init__ / bad base64.
        raise RealtimeError(f"invalid operation payload: {exc}") from exc
    raise RealtimeError(f"unknown operation kind {kind!r}")


def encode_update(ops: Sequence[Operation]) -> bytes:
    """Encode a sequence of operations into a transportable CRDT-update blob.

    The blob is the unit the transport carries and the backend persists/relays. It is
    canonical JSON (deterministic key order); raster pixels are base64-encoded so the
    envelope stays valid UTF-8/JSON. The result should be wrapped by the transport
    (``sync_protocol.encode_update``) and is bounded by ``MAX_CRDT_UPDATE_BYTES`` at the
    trust boundary.

    Raises:
        RealtimeError: If ``ops`` exceeds the per-update op cap or an op is unknown.
    """
    if len(ops) > _MAX_OPS_PER_UPDATE:
        raise RealtimeError(f"update has {len(ops)} ops, exceeds {_MAX_OPS_PER_UPDATE}")
    payload = {"v": _UPDATE_VERSION, "ops": [_encode_op(op) for op in ops]}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_update(blob: bytes) -> Tuple[Operation, ...]:
    """Decode an untrusted CRDT-update blob into a tuple of operations.

    The untrusted-input defence (Article VII): ``blob`` is size-capped
    (``validate_crdt_update``, ``MAX_CRDT_UPDATE_BYTES``) **before** JSON decode; the
    payload is JSON-parsed (never ``eval``/``exec``), the op count is bounded, and every
    op is reconstructed through its validating dataclass constructor.

    Raises:
        RealtimeError: If the blob is malformed, wrong-version, over the op cap, or
            carries an ill-formed operation.
        CloudValidationError: If the blob is not bytes, empty, or oversized.
    """
    checked = validate_crdt_update(blob)
    try:
        payload = json.loads(bytes(checked).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RealtimeError(f"update blob is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RealtimeError("update blob must decode to a JSON object")
    if payload.get("v") != _UPDATE_VERSION:
        raise RealtimeError(f"unsupported update version {payload.get('v')!r}")
    items = payload.get("ops")
    if not isinstance(items, list):
        raise RealtimeError("update blob 'ops' must be a list")
    if len(items) > _MAX_OPS_PER_UPDATE:
        raise RealtimeError(
            f"update has {len(items)} ops, exceeds {_MAX_OPS_PER_UPDATE}"
        )
    return tuple(_decode_op(item) for item in items)


# --------------------------------------------------------------------------- #
# LWW clock tracking for out-of-order streaming apply.
# --------------------------------------------------------------------------- #


def _register_key(op: Operation) -> str:
    """Return the LWW-register key an op writes (structured register or raster tile)."""
    if isinstance(op, MetadataOp):
        return f"meta:{op.key}"
    if isinstance(op, LayerAttrOp):
        return f"attr:{op.frame_index}:{op.layer_id}:{op.attr}"
    if isinstance(op, LayerOrderOp):
        return f"order:{op.frame_index}"
    if isinstance(op, RasterOp):
        return f"raster:{op.frame_index}:{op.layer_id}:{op.tile_x}:{op.tile_y}"
    raise RealtimeError(f"unknown operation type: {op!r}")


def _stamp(op: Operation) -> Tuple[int, int, bytes]:
    """Return a total-order stamp mirroring convergence: clock, site, tiebreak."""
    pixels = op.pixels if isinstance(op, RasterOp) else b""
    return (op.logical_clock, op.site_id, pixels)


@dataclass
class RealtimeState:
    """Per-register LWW clocks for order-independent streaming apply (LOGIC-007).

    Holds, per LWW register (structured register key or raster tile key), the stamp of
    the newest operation applied so far. :meth:`accept` filters an incoming op set down
    to the strictly-newer ops (updating the clocks), so applying updates in **any**
    arrival order converges to the same document — a stale/duplicate patch is dropped,
    never overwriting a newer edit (strong eventual consistency). Pass one instance
    across a real-time session; omit it for a one-shot batch apply.
    """

    _stamps: Dict[str, Tuple[int, int, bytes]] = field(default_factory=dict)

    def accept(self, ops: Sequence[Operation]) -> Tuple[Operation, ...]:
        """Return the ops that win against the recorded clocks; record their stamps.

        Among ``ops`` themselves the winner per register is the highest stamp (matching
        :func:`~pixelart_creator.logic.convergence.converge`); an op that is not
        strictly newer than the already-applied stamp for its register is dropped.
        """
        winners: Dict[str, Operation] = {}
        winner_stamps: Dict[str, Tuple[int, int, bytes]] = {}
        for op in ops:
            key = _register_key(op)
            stamp = _stamp(op)
            applied = self._stamps.get(key)
            if applied is not None and stamp <= applied:
                continue
            current = winner_stamps.get(key)
            if current is None or stamp > current:
                winners[key] = op
                winner_stamps[key] = stamp
        for key, stamp in winner_stamps.items():
            self._stamps[key] = stamp
        # Deterministic order (does not affect the converged result).
        return tuple(winners[key] for key in sorted(winners))


# --------------------------------------------------------------------------- #
# Real-time apply.
# --------------------------------------------------------------------------- #


def regions_for_ops(ops: Sequence[Operation]) -> Tuple[DirtyRegion, ...]:
    """Map raster operations to their buffer-space rectangles (dirty-rect redraw).

    Pure over an already-decoded op sequence — the tile-index -> pixel-rect
    mapping and its sort order live here **once** (plan §2: "two homes for one
    format is a drift surface"), so both the real-time apply path
    (:func:`dirty_regions`, via :func:`decode_update`) and the Phase-10 branch
    diff's region tier (``logic/branch_diff.py``) read the *same* function
    rather than a copy of it. Non-raster ops (metadata/attr/order) contribute no
    region. Deterministic: sorted ``(frame_index, layer_id, y, x)``.
    """
    regions: List[DirtyRegion] = []
    for op in ops:
        if isinstance(op, RasterOp):
            regions.append(
                DirtyRegion(
                    frame_index=op.frame_index,
                    layer_id=op.layer_id,
                    x=op.tile_x * CRDT_TILE_SIZE_PX,
                    y=op.tile_y * CRDT_TILE_SIZE_PX,
                    width=op.tile_width,
                    height=op.tile_height,
                )
            )
    regions.sort(key=lambda r: (r.frame_index, r.layer_id, r.y, r.x))
    return tuple(regions)


def dirty_regions(update: bytes) -> Tuple[DirtyRegion, ...]:
    """Return the raster rectangles a remote ``update`` touches (for dirty-rect redraw).

    Decodes + validates the blob (Article VII) and delegates the tile->rect
    mapping to :func:`regions_for_ops` — **no** round trip through
    :func:`encode_update` (that would re-impose the ``_MAX_OPS_PER_UPDATE`` cap
    on a path that does not need it). Structured-only updates touch no raster
    and yield an empty tuple. Deterministic (sorted).

    Raises:
        RealtimeError / CloudValidationError: If the blob is malformed or oversized.
    """
    return regions_for_ops(decode_update(update))


def apply_remote(
    document: Document,
    update: bytes,
    *,
    site_id: int,
    state: Optional[RealtimeState] = None,
) -> Document:
    """Apply an untrusted remote CRDT-update blob onto ``document`` **in place**.

    Validates (``validate_crdt_update`` size cap), decodes (``decode_update``, never
    ``eval``/``exec``), filters to the fresh (strictly-newer) ops via ``state``, and
    folds them onto the live ``document`` through the dirty-region-scoped
    :func:`~pixelart_creator.logic.convergence.apply_operations` — **no** deep copy,
    so a single patch apply is bounded by the patch, not the 8K canvas (Article VI
    re-entry, ADR-0027 §7; AGT-10 FLAG-PERFRAME profiles exactly this call).

    Determinism (REQ-P10-LOGIC-007): with a shared ``state`` across a session,
    applying a given set of updates in **any** order converges to the same document —
    per-register LWW resolves the winner by ``(logical_clock, site_id)`` regardless of
    order (strong eventual consistency). Use :func:`dirty_regions` on the same blob to
    learn which rects to repaint.

    Args:
        document: The live document to mutate in place.
        update: The untrusted CRDT-update blob (from the transport).
        site_id: The local replica id (non-negative). Identifies the caller; it does not
            affect the converged result.
        state: The session's :class:`RealtimeState` for out-of-order convergence. When
            ``None`` a fresh one is used (resolves the winners within this single blob,
            equivalent to a one-shot batch apply).

    Returns:
        The same ``document`` object, mutated in place (returned for convenience).

    Raises:
        RealtimeError: If ``document`` is not a ``Document``, ``site_id`` is invalid, or
            the blob / an op is malformed.
        CloudValidationError: If the blob is not bytes, empty, or oversized.
    """
    if not isinstance(document, Document):
        raise RealtimeError(f"document must be a Document, got {document!r}")
    if isinstance(site_id, bool) or not isinstance(site_id, int) or site_id < 0:
        raise RealtimeError(f"site_id must be a non-negative int, got {site_id!r}")
    ops = decode_update(update)
    fresh = (state or RealtimeState()).accept(ops)
    try:
        apply_operations(document, fresh)
    except ValueError as exc:  # ConvergenceError (bad target layer, etc.)
        raise RealtimeError(f"cannot apply remote update: {exc}") from exc
    return document


# --------------------------------------------------------------------------- #
# Git-like branching.
# --------------------------------------------------------------------------- #


@dataclass
class Branch:
    """A forked line of edits over a shared base document (git-like, ADR-0028 §3).

    A branch is a clone of the base document plus an **ordered op-log** of the edits
    made since the fork. Two branches forked from the same base merge back
    conflict-free via :func:`merge` (the CRDT/LWW converges the union of their logs);
    the op-log makes the history reconstructable. Create one with :func:`branch`.

    Attributes:
        base: The document snapshot at fork time (owned by this branch; not mutated).
        site_id: The replica id attributed to this branch's local edits.
        ops: The ordered edits recorded on this branch since the fork.
    """

    base: Document
    site_id: int
    ops: Tuple[Operation, ...] = ()

    def record(self, ops: Sequence[Operation]) -> None:
        """Append local edits to this branch's op-log (does not materialise yet).

        Raises:
            RealtimeError: If the accumulated op-log exceeds the per-update op cap.
        """
        combined = self.ops + tuple(ops)
        if len(combined) > _MAX_OPS_PER_UPDATE:
            raise RealtimeError(
                f"branch op-log has {len(combined)} ops, exceeds {_MAX_OPS_PER_UPDATE}"
            )
        self.ops = combined

    def document(self) -> Document:
        """Materialise this branch's current document = converge(base, ops)."""
        return converge(self.base, self.ops, site_id=self.site_id)


def branch(document: Document, *, site_id: int = 0) -> Branch:
    """Fork ``document`` into a new :class:`Branch` (clone + empty op-log).

    Equivalent to ``git branch``: the returned branch owns a deep copy of ``document``
    so subsequent edits to either are independent. Fork mainline and feature from the
    **same** document to get a shared base, edit each via
    :meth:`Branch.record`, then :func:`merge` them.

    Args:
        document: The document to fork.
        site_id: The replica id attributed to this branch's edits (non-negative).

    Raises:
        RealtimeError: If ``document`` is not a ``Document`` or ``site_id`` is invalid.
    """
    if not isinstance(document, Document):
        raise RealtimeError(f"document must be a Document, got {document!r}")
    if isinstance(site_id, bool) or not isinstance(site_id, int) or site_id < 0:
        raise RealtimeError(f"site_id must be a non-negative int, got {site_id!r}")
    return Branch(base=copy.deepcopy(document), site_id=site_id, ops=())


def merge(mainline: Branch, other: Branch) -> Document:
    """Merge two branches conflict-free into a new converged document (git-like).

    Converges the **union** of both branches' op-logs onto their shared base via the
    hybrid CRDT/LWW model — no manual conflict resolution (the CRDT merges), and the
    result is deterministic and independent of which branch is named first (``converge``
    is order-independent). The branches must have been forked from the same base
    document (``branch(doc)`` twice or fork then re-fork); that is the merge base.

    Args:
        mainline: The branch whose base + site_id anchor the merge.
        other: The branch to merge in.

    Returns:
        A new, converged :class:`Document` (neither branch is mutated).

    Raises:
        RealtimeError: If either argument is not a :class:`Branch`.
    """
    if not isinstance(mainline, Branch) or not isinstance(other, Branch):
        raise RealtimeError("merge requires two Branch objects")
    combined: Tuple[Operation, ...] = tuple(mainline.ops) + tuple(other.ops)
    return converge(mainline.base, combined, site_id=mainline.site_id)
