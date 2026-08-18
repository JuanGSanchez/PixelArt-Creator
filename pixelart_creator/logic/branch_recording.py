"""Edit traces + a live document + a session stamp -> convergence ``Operation`` s.

Phase 10 slice ``phase-10-branch-diff`` (plan §3, step 4; ``REQ-P10-UI-025``). The
one seam that turns what a reversible :class:`~pixelart_creator.logic.history.Command`
describes (an :class:`~pixelart_creator.logic.edit_trace.EditTrace`) into what the
branch op-log actually stores (a :mod:`pixelart_creator.logic.convergence`
``Operation``). The **session** — never this module, never the command — owns the
logical clock and the site id (plan §3.1); this module only maps.

Two entry points:

* :func:`ops_for_traces` — the forward direction. Reads whatever live state an op
  needs at minting time (a metadata/attr/order trace already carries its own new
  value; a raster trace carries none, so its tile bytes are read from ``live``'s
  buffer by :func:`~pixelart_creator.logic.convergence.make_raster_op`).
* :func:`inverse_traces` — the undo direction (plan §3.3: *append the inverse,
  never pop the log*). Given the **same forward traces** a command reported, and
  the **live document as it stands after the command's own** :meth:`Command.undo`
  **has already run**, returns the traces that describe reverting to the prior
  state — read straight off ``live`` at call time, since ``live`` already holds
  that prior state by the time this is called (the caller's ordering, plan §3.3,
  ``ui/commands.py`` fires the callback with ``inverse=True`` *after* ``undo()``).
  Feeding the inverse traces back through :func:`ops_for_traces` with the same
  (now-reverted) ``live`` document is what makes a raster undo carry the prior
  tile bytes without this module ever needing to snapshot them itself.

Pure, Qt-free (S11); every numeric bound comes from
:mod:`pixelart_creator.logic.constants` (S12, via the constants the ops
themselves validate against).
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from pixelart_creator.logic.convergence import (
    LAYER_ATTRS,
    ConvergenceError,
    Operation,
    make_layer_attr_op,
    make_layer_order_op,
    make_metadata_op,
    make_raster_op,
)
from pixelart_creator.logic.document import (
    Document,
    Frame,
    Layer,
    LayerGroup,
    LayerNode,
)
from pixelart_creator.logic.edit_trace import (
    EditTrace,
    LayerAttrTrace,
    LayerOrderTrace,
    MetadataTrace,
    RasterTrace,
)

__all__ = ["BranchRecordingError", "ops_for_traces", "inverse_traces"]


class BranchRecordingError(ValueError):
    """Raised when a trace cannot be mapped against the supplied live document."""


def _check_frame(live: Document, frame_index: int) -> Frame:
    """Return ``live.frames[frame_index]``, or raise :class:`BranchRecordingError`."""
    if not 0 <= frame_index < len(live.frames):
        raise BranchRecordingError(f"frame index {frame_index} out of range")
    return live.frames[frame_index]


def _find_node(frame: Frame, layer_id: int) -> LayerNode:
    """Return the node with stable ``layer_id`` in ``frame``'s tree, depth-first."""

    def _walk(nodes: Sequence[LayerNode]) -> Optional[LayerNode]:
        for node in nodes:
            if node.layer_id == layer_id:
                return node
            if isinstance(node, LayerGroup):
                found = _walk(node.children)
                if found is not None:
                    return found
        return None

    node = _walk(frame.layers)
    if node is None:
        raise BranchRecordingError(f"layer_id {layer_id} not found in frame")
    return node


def _op_for_trace(
    trace: EditTrace, live: Document, *, logical_clock: int, site_id: int
) -> Operation:
    """Map one :class:`EditTrace` to its convergence ``Operation`` against ``live``."""
    if isinstance(trace, MetadataTrace):
        return make_metadata_op(
            trace.key, trace.value, logical_clock=logical_clock, site_id=site_id
        )
    if isinstance(trace, LayerAttrTrace):
        return make_layer_attr_op(
            frame_index=trace.frame_index,
            layer_id=trace.layer_id,
            attr=trace.attr,
            value=trace.value,
            logical_clock=logical_clock,
            site_id=site_id,
        )
    if isinstance(trace, LayerOrderTrace):
        return make_layer_order_op(
            trace.frame_index,
            trace.order,
            logical_clock=logical_clock,
            site_id=site_id,
        )
    if isinstance(trace, RasterTrace):
        frame = _check_frame(live, trace.frame_index)
        node = _find_node(frame, trace.layer_id)
        if not isinstance(node, Layer):
            raise BranchRecordingError(
                f"raster trace targets layer_id {trace.layer_id}, "
                f"which is not a paintable leaf layer"
            )
        try:
            return make_raster_op(
                node.buffer.data,
                frame_index=trace.frame_index,
                layer_id=trace.layer_id,
                tile_x=trace.tile_x,
                tile_y=trace.tile_y,
                logical_clock=logical_clock,
                site_id=site_id,
            )
        except ConvergenceError as exc:
            raise BranchRecordingError(f"cannot mint raster op: {exc}") from exc
    raise BranchRecordingError(f"unknown edit trace type: {trace!r}")


def ops_for_traces(
    traces: Sequence[EditTrace],
    live: Document,
    *,
    site_id: int,
    logical_clock: int,
) -> Tuple[Operation, ...]:
    """Mint the convergence ``Operation`` s ``traces`` describe against ``live``.

    The session supplies the stamp (plan §3.1: the trace carries neither a clock
    nor a site id, so a logic ``Command`` never pretends to mint one). A raster
    trace's pixel bytes are read from ``live`` at call time; the other three
    classes carry their own value already.

    Args:
        traces: The traces a command's :meth:`~pixelart_creator.logic.history.
            Command.edit_trace` reported.
        live: The document to read raster tile bytes / validate targets against.
        site_id: The recording session's replica id (stamped onto every op).
        logical_clock: The recording session's logical clock (stamped onto every
            op).

    Raises:
        BranchRecordingError: If ``live`` is not a :class:`Document`, a target
            frame/layer does not exist, or a raster trace targets a non-leaf
            node.
    """
    if not isinstance(live, Document):
        raise BranchRecordingError(f"live must be a Document, got {live!r}")
    return tuple(
        _op_for_trace(trace, live, logical_clock=logical_clock, site_id=site_id)
        for trace in traces
    )


def _inverse_for_trace(trace: EditTrace, live: Document) -> EditTrace:
    """Return the inverse of one forward ``trace``, read off ``live`` (post-undo)."""
    if isinstance(trace, MetadataTrace):
        prior = live.metadata.get(trace.key, "")
        return MetadataTrace(key=trace.key, value=prior)
    if isinstance(trace, LayerAttrTrace):
        if trace.attr not in LAYER_ATTRS:
            raise BranchRecordingError(f"attr {trace.attr!r} is not a known layer attr")
        frame = _check_frame(live, trace.frame_index)
        node = _find_node(frame, trace.layer_id)
        prior_value = getattr(node, trace.attr)
        return LayerAttrTrace(
            frame_index=trace.frame_index,
            layer_id=trace.layer_id,
            attr=trace.attr,
            value=prior_value,
        )
    if isinstance(trace, LayerOrderTrace):
        frame = _check_frame(live, trace.frame_index)
        prior_order: Tuple[int, ...] = tuple(node.layer_id for node in frame.layers)
        return LayerOrderTrace(frame_index=trace.frame_index, order=prior_order)
    if isinstance(trace, RasterTrace):
        # No baked-in value to invert: the prior tile bytes are read from
        # ``live`` (already reverted) by :func:`ops_for_traces` at mint time,
        # so the same tile coordinates are the correct inverse trace.
        return trace
    raise BranchRecordingError(f"unknown edit trace type: {trace!r}")


def inverse_traces(
    traces: Sequence[EditTrace], live: Document
) -> Tuple[EditTrace, ...]:
    """Return the well-defined inverse of each of ``traces``, read off ``live``.

    Call this **after** the originating command's own :meth:`~pixelart_creator.
    logic.history.Command.undo` has already run, so ``live`` holds the prior
    (reverted) state — the value each inverse trace reports (plan §3.3: prior
    metadata value, prior attribute value, prior top-level order, prior tile
    bytes) is read straight off it. A raster trace's inverse is itself
    (unchanged tile coordinates); feeding it back through :func:`ops_for_traces`
    against the same reverted ``live`` is what recovers the prior pixel bytes.

    Raises:
        BranchRecordingError: If ``live`` is not a :class:`Document` or a target
            frame/layer named by a trace does not exist in it.
    """
    if not isinstance(live, Document):
        raise BranchRecordingError(f"live must be a Document, got {live!r}")
    return tuple(_inverse_for_trace(trace, live) for trace in traces)
