# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The timeline grid's model: a pure frames x layer-track table (zero Qt, S11).

Implements ``REQ-P5-LOGIC-015``: given a document and its active frame, derive
the ordered list of **layer tracks** and, for every ``(frame, track)`` pair,
either the node occupying that cell or the fact that it is **empty**. A track
is identified by the shipped stable cross-frame ``Layer.layer_id``
(``logic/document.py`` — two frames share a track exactly when they carry
nodes with the same id, which is exactly what
``Document.make_duplicate_frame_command`` preserves). Group nodes are tracks
too, in tree order (CL-P5G-2).

The computation mutates nothing — not the document, not a frame, not a node —
reads no Qt type, and stays inside the shipped ``MAX_FRAMES`` /
``MAX_LAYERS_PER_FRAME`` without introducing any new bound or constant
(``ui/timeline_grid_view.py`` is the ``QTableView`` + ``QAbstractTableModel``
that renders this table — not this module's concern).
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple, Union

from pixelart_creator.logic.document import Document, LayerGroup, LayerNode

__all__ = [
    "TrackTableError",
    "EmptyCell",
    "EMPTY_CELL",
    "Cell",
    "TrackRow",
    "TrackTable",
    "track_table",
]


class TrackTableError(ValueError):
    """Raised when ``track_table`` is asked to derive an invalid table."""


class EmptyCell:
    """Sentinel: a ``(frame, track)`` cell that carries no node.

    A first-class value (CL-P5G-2 / ``REQ-P5-LOGIC-015``) — never ``None``
    read as an error, and never a silently substituted blank layer. Compares
    equal only to itself; use the module-level singleton :data:`EMPTY_CELL`,
    never construct a second instance.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a stable debug representation."""
        return "EMPTY_CELL"


#: The single, shared "this cell has no node" marker. Use ``is EMPTY_CELL`` to
#: test for it, never equality against a fresh ``EmptyCell()``.
EMPTY_CELL = EmptyCell()

#: A track's occupant in one frame: the node it holds, or :data:`EMPTY_CELL`.
Cell = Union[LayerNode, EmptyCell]


class TrackRow(NamedTuple):
    """One layer track: its stable id, display label, and one cell per frame."""

    layer_id: int
    label: str
    #: One entry per document frame, in frame order; ``cells[i]`` is this
    #: track's occupant (or :data:`EMPTY_CELL`) in ``document.frames[i]``.
    cells: Tuple[Cell, ...]


class TrackTable(NamedTuple):
    """The grid's whole model: every track, in the spec's deterministic order."""

    rows: Tuple[TrackRow, ...]


def _dfs_nodes(nodes: Sequence["LayerNode"]) -> List["LayerNode"]:
    """Pre-order depth-first list of every node in ``nodes`` — groups included.

    Matches the layer panel's own tree order: a group appears before its
    children, and both a group and each of its children are separate rows
    (CL-P5G-2).
    """
    out: List["LayerNode"] = []
    for node in nodes:
        out.append(node)
        if isinstance(node, LayerGroup):
            out.extend(_dfs_nodes(node.children))
    return out


def _find_by_id(nodes: Sequence["LayerNode"], layer_id: int) -> Optional["LayerNode"]:
    """Depth-first search for the node whose ``layer_id`` matches, or ``None``."""
    for node in nodes:
        if node.layer_id == layer_id:
            return node
        if isinstance(node, LayerGroup):
            found = _find_by_id(node.children, layer_id)
            if found is not None:
                return found
    return None


def track_table(document: Document, *, active_frame: int) -> TrackTable:
    """Derive the frames x layer-track table for ``document`` (REQ-P5-LOGIC-015).

    Row order is deterministic and matches the spec exactly: tracks present in
    ``active_frame`` come first, in that frame's own tree order (a group then
    its children, depth-first); tracks absent from the active frame follow,
    ordered by the index of the earliest frame that carries them and then by
    that frame's own tree order. The same ``document`` and ``active_frame``
    always yield the same table (pure, deterministic).

    Args:
        document: The document to derive the table from. Not mutated.
        active_frame: The index of the currently active frame; determines
            which tracks are listed first and whose stack order they follow.

    Returns:
        The ordered :class:`TrackTable`.

    Raises:
        TrackTableError: If ``active_frame`` is not a valid frame index.
    """
    frame_count = len(document.frames)
    if not isinstance(active_frame, int) or isinstance(active_frame, bool):
        raise TrackTableError(f"active_frame must be an int, got {active_frame!r}")
    if not 0 <= active_frame < frame_count:
        raise TrackTableError(f"active_frame {active_frame} out of range")

    active_nodes = _dfs_nodes(document.frames[active_frame].layers)
    ordered_ids: List[int] = [node.layer_id for node in active_nodes]
    seen = set(ordered_ids)
    labels: Dict[int, str] = {node.layer_id: node.name for node in active_nodes}

    # Absent tracks: order key is (earliest carrying frame index, that
    # frame's own tree position) — first-seen wins, so later frames carrying
    # the same id do not reorder it.
    absent_order: Dict[int, Tuple[int, int]] = {}
    for frame_index, frame in enumerate(document.frames):
        if frame_index == active_frame:
            continue
        for position, node in enumerate(_dfs_nodes(frame.layers)):
            layer_id = node.layer_id
            if layer_id in seen or layer_id in absent_order:
                continue
            absent_order[layer_id] = (frame_index, position)
            labels.setdefault(layer_id, node.name)

    ordered_ids.extend(sorted(absent_order, key=lambda lid: absent_order[lid]))

    rows: List[TrackRow] = []
    for layer_id in ordered_ids:
        cells: List[Cell] = []
        for frame in document.frames:
            occupant = _find_by_id(frame.layers, layer_id)
            cells.append(occupant if occupant is not None else EMPTY_CELL)
        rows.append(
            TrackRow(layer_id=layer_id, label=labels[layer_id], cells=tuple(cells))
        )
    return TrackTable(rows=tuple(rows))
