"""Edit-trace vocabulary — what a reversible command changed (zero Qt, S11).

Phase 10 slice ``phase-10-branch-diff`` (plan §3, §3.1; ``REQ-P10-UI-025``). A
:class:`~pixelart_creator.logic.history.Command` already knows its own before and
after state (that is what makes it reversible); an :class:`EditTrace` is the pure,
declarative shape a command uses to *describe* that change so the branching
session can mint a :mod:`pixelart_creator.logic.convergence` ``Operation`` from it.

This module is a **stdlib-only leaf, by construction**: it imports nothing from
``pixelart_creator`` and nothing third-party (not even ``typing`` extras beyond the
standard library). It carries **no logical clock and no site id** — those are
owned by the session (``ui/branching_panel.py::Branching_Session``), which is the
only object with the authority to stamp an edit for convergence ordering. Giving a
trace a clock/site id here would let a `logic/history.py` command look enough like
an ``Operation`` to invite importing :mod:`pixelart_creator.logic.convergence`
straight from :mod:`pixelart_creator.logic.history`, which would close the cycle
``history -> convergence -> document -> history`` (plan §3.1, proven not asserted).
Keeping this module a leaf is what keeps that edge out.

Each variant mirrors one of the four convergence ``Operation`` classes
(``logic/convergence.py``): :class:`MetadataTrace` <-> ``MetadataOp``,
:class:`LayerAttrTrace` <-> ``LayerAttrOp``, :class:`LayerOrderTrace` <->
``LayerOrderOp``, :class:`RasterTrace` <-> ``RasterOp``. A raster trace never
carries pixel bytes — the tile content is read from the *live* buffer at minting
time by ``convergence.make_raster_op``, so the trace stays a light, Qt-free
descriptor of *where*, never a copy of *what*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple, Union

__all__ = [
    "MetadataTrace",
    "LayerAttrTrace",
    "LayerOrderTrace",
    "RasterTrace",
    "EditTrace",
]

#: A structured layer-attribute value. Duplicated from
#: ``logic/convergence.LayerAttrValue`` rather than imported — this module is a
#: stdlib-only leaf (module docstring) and must not import ``logic/convergence``.
LayerAttrValue = Union[str, float, bool, int]


@dataclass(frozen=True)
class MetadataTrace:
    """A change to one ``Document.metadata`` key (mirrors ``convergence.MetadataOp``).

    Attributes:
        key: The metadata key written.
        value: The new value (a ``str`` — ``Document.metadata`` is ``Dict[str,
            str]``).
    """

    key: str
    value: str


@dataclass(frozen=True)
class LayerAttrTrace:
    """A change to one layer/group attribute (mirrors ``convergence.LayerAttrOp``).

    Attributes:
        frame_index: The frame the target node lives in.
        layer_id: The stable id of the target node.
        attr: The attribute name (one of ``convergence.LAYER_ATTRS``).
        value: The new attribute value.
    """

    frame_index: int
    layer_id: int
    attr: str
    value: LayerAttrValue


@dataclass(frozen=True)
class LayerOrderTrace:
    """A change to a frame's top-level layer order (mirrors ``LayerOrderOp``).

    Attributes:
        frame_index: The frame whose top-level order changed.
        order: The resulting top-level order, as ``layer_id`` s.
    """

    frame_index: int
    order: Tuple[int, ...]


@dataclass(frozen=True)
class RasterTrace:
    """One touched raster tile (mirrors ``convergence.RasterOp``).

    No pixel bytes travel in the trace: the tile content is read from the live
    buffer at op-minting time (``convergence.make_raster_op``), so a
    :class:`RasterTrace` only ever names *where* a tile changed.

    Attributes:
        frame_index: The frame the target layer lives in.
        layer_id: The stable id of the target leaf layer.
        tile_x: The tile column index (buffer-pixel ``x`` // ``CRDT_TILE_SIZE_PX``).
        tile_y: The tile row index (buffer-pixel ``y`` // ``CRDT_TILE_SIZE_PX``).
    """

    frame_index: int
    layer_id: int
    tile_x: int
    tile_y: int


#: The union of the four trace variants a reversible command may report.
EditTrace = Union[MetadataTrace, LayerAttrTrace, LayerOrderTrace, RasterTrace]
