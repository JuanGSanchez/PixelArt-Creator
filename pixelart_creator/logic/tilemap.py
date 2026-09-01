# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tilemap model — layered, chunked-sparse, infinite grid of linked instances.

Zero Qt (S11). A :class:`Tilemap` is an ordered stack of :class:`TilemapLayer`
plus the referenced :class:`~pixelart_creator.logic.tileset.Tileset` list under a
Tiled-style global gid space. Each layer is an **unbounded, sparse** grid of
cells stored as ``TILEMAP_CHUNK_SIZE`` x ``TILEMAP_CHUNK_SIZE`` dense numpy
``uint32`` chunks keyed by chunk-origin; only non-empty chunks are held, arbitrary
(incl. negative) coordinates are addressable, and reading an unset cell yields
``0`` (Tiled empty semantics). Coordinate magnitude is guarded by
``MAX_TILEMAP_COORD`` (REQ-P6-LOGIC-009).

A cell is a **32-bit GID** (a *linked instance*, never pixels, REQ-P6-LOGIC-005):
the low 28 bits are the global tile id (``0`` = empty) and the top nibble carries
the flip/rotate flags. These masks are the **canonical cell bit layout** —
module-local intrinsic constants matching Tiled 1.12.2 exactly for a 1:1 lossless
map (ADR-0001 exemption / ADR-0015, the ``blend.py`` precedent). They live in
``logic/`` so ``data/tiled_io.py`` imports them **downward** (``data -> logic``);
a forbidden ``logic -> data`` edge never appears.

Auto-tiling (ADR-0013): a layer may carry an
:class:`~pixelart_creator.logic.autotile.AutotileRuleset`. Then the layer stores
the **logical** placement separately from the derived **display** gid; a
stamp/erase/fill records the logical change, re-resolves the affected cells' 8
neighbours' display gids, and the enclosing reversible command captures the prior
display gids so undo restores the whole affected region (REQ-P6-LOGIC-011).

Rendering (REQ-P6-LOGIC-013) resolves each visible cell's instance to source-tile
pixels (flip applied), blits via ``PixelBuffer.blit`` (PB-1), and flattens the
visible layer stack via ``blend.composite_stack`` (CO-4), non-destructively. This
module never imports ``document`` or Qt (PL6-D3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import autotile as _autotile
from pixelart_creator.logic.autotile import AutotileRuleset
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.constants import (
    DEFAULT_TILE_HEIGHT,
    DEFAULT_TILE_WIDTH,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_TILEMAP_COORD,
    MAX_TILEMAP_LAYERS,
    TILEMAP_CHUNK_SIZE,
)
from pixelart_creator.logic.history import Command, FunctionCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tileset import Tileset

__all__ = [
    "FLIPPED_HORIZONTALLY_FLAG",
    "FLIPPED_VERTICALLY_FLAG",
    "FLIPPED_DIAGONALLY_FLAG",
    "ROTATED_HEXAGONAL_120_FLAG",
    "GID_MASK",
    "TilemapError",
    "TileInstance",
    "TilemapLayer",
    "Tilemap",
]

# --- canonical uint32 cell bit layout (module-local intrinsic, Tiled 1.12.2) --
# ADR-0015: deliberately matching Tiled for a 1:1 lossless map (ADR-0001
# exemption, the blend.py formula-constant precedent). Placed in logic/ so
# data/tiled_io.py imports them downward (no logic -> data edge).
FLIPPED_HORIZONTALLY_FLAG = 0x80000000
FLIPPED_VERTICALLY_FLAG = 0x40000000
FLIPPED_DIAGONALLY_FLAG = 0x20000000
ROTATED_HEXAGONAL_120_FLAG = 0x10000000
GID_MASK = 0x0FFFFFFF  # low 28 bits = global tile id (0 = empty)

#: numpy dtype of a stored cell (top-nibble flags representable, research OD-8).
_CELL_DTYPE = np.uint32


class TilemapError(ValueError):
    """Raised on invalid tilemap geometry, layer/coord/gid, or an unknown gid."""


@dataclass(frozen=True)
class TileInstance:
    """A read-only view of a cell's 32-bit GID (base id + flip flags)."""

    gid: int

    @property
    def base_gid(self) -> int:
        """The global tile id with the flag nibble stripped (``0`` = empty)."""
        return self.gid & GID_MASK

    @property
    def flip_h(self) -> bool:
        """Whether the horizontal-flip flag is set."""
        return bool(self.gid & FLIPPED_HORIZONTALLY_FLAG)

    @property
    def flip_v(self) -> bool:
        """Whether the vertical-flip flag is set."""
        return bool(self.gid & FLIPPED_VERTICALLY_FLAG)

    @property
    def flip_d(self) -> bool:
        """Whether the (anti-)diagonal-flip flag is set (round-trip preserved)."""
        return bool(self.gid & FLIPPED_DIAGONALLY_FLAG)


def _check_coord(x: int, y: int) -> None:
    for name, value in (("x", x), ("y", y)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise TilemapError(f"{name} must be an int, got {value!r}")
        if abs(value) > MAX_TILEMAP_COORD:
            raise TilemapError(
                f"{name} {value} exceeds MAX_TILEMAP_COORD ({MAX_TILEMAP_COORD})"
            )


def _chunk_key(x: int, y: int) -> Tuple[int, int]:
    """Return the chunk-origin key ``(cx, cy)`` owning cell ``(x, y)``."""
    return (x // TILEMAP_CHUNK_SIZE, y // TILEMAP_CHUNK_SIZE)


def _local_index(x: int, y: int) -> Tuple[int, int]:
    """Return the ``(row, col)`` index of cell ``(x, y)`` inside its chunk."""
    return (y % TILEMAP_CHUNK_SIZE, x % TILEMAP_CHUNK_SIZE)


class _ChunkGrid:
    """A chunked-sparse ``uint32`` cell store keyed by chunk-origin.

    Only non-empty chunks are held; a chunk that becomes all-zero is dropped so
    an emptied region costs nothing (REQ-P6-LOGIC-009). Not part of the public
    contract — an internal store shared by a layer's display and logical planes.
    """

    __slots__ = ("_chunks",)

    def __init__(self) -> None:
        self._chunks: Dict[Tuple[int, int], npt.NDArray[np.uint32]] = {}

    def get(self, x: int, y: int) -> int:
        chunk = self._chunks.get(_chunk_key(x, y))
        if chunk is None:
            return 0
        row, col = _local_index(x, y)
        return int(chunk[row, col])

    def set(self, x: int, y: int, value: int) -> None:
        key = _chunk_key(x, y)
        row, col = _local_index(x, y)
        chunk = self._chunks.get(key)
        if value == 0:
            if chunk is None:
                return
            chunk[row, col] = 0
            if not chunk.any():
                del self._chunks[key]
            return
        if chunk is None:
            chunk = np.zeros(
                (TILEMAP_CHUNK_SIZE, TILEMAP_CHUNK_SIZE), dtype=_CELL_DTYPE
            )
            self._chunks[key] = chunk
        chunk[row, col] = value

    def cells(self) -> Iterator[Tuple[int, int, int]]:
        """Yield ``(x, y, value)`` for every non-zero cell, in chunk order."""
        for (cx, cy), chunk in sorted(self._chunks.items()):
            nz = np.argwhere(chunk != 0)
            for row, col in nz:
                x = cx * TILEMAP_CHUNK_SIZE + int(col)
                y = cy * TILEMAP_CHUNK_SIZE + int(row)
                yield x, y, int(chunk[row, col])

    def chunk_items(
        self,
    ) -> Iterator[Tuple[Tuple[int, int], npt.NDArray[np.uint32]]]:
        """Yield ``((cx, cy), chunk)`` for every stored chunk, in chunk order."""
        yield from sorted(self._chunks.items())

    def region(
        self, col0: int, row0: int, n_cols: int, n_rows: int
    ) -> npt.NDArray[np.uint32]:
        """Return a dense ``(n_rows, n_cols)`` gid array over a cell rectangle.

        Gathers the requested cell window (in *cell* coordinates, top-left
        ``(col0, row0)``) directly from the intersecting chunks by numpy slice
        copies — never a per-cell Python read — so a render pass is O(visible
        chunks), not O(cells). Cells with no stored chunk read ``0`` (Tiled empty
        semantics). Chunk coordinates use floor division so negative windows are
        handled identically to :func:`_chunk_key`.
        """
        out = np.zeros((n_rows, n_cols), dtype=_CELL_DTYPE)
        cs = TILEMAP_CHUNK_SIZE
        col1 = col0 + n_cols  # exclusive
        row1 = row0 + n_rows
        cx_start = col0 // cs
        cx_end = (col1 - 1) // cs
        cy_start = row0 // cs
        cy_end = (row1 - 1) // cs
        for cy in range(cy_start, cy_end + 1):
            chunk_row0 = cy * cs
            for cx in range(cx_start, cx_end + 1):
                chunk = self._chunks.get((cx, cy))
                if chunk is None:
                    continue
                chunk_col0 = cx * cs
                gc0 = max(col0, chunk_col0)
                gc1 = min(col1, chunk_col0 + cs)
                gr0 = max(row0, chunk_row0)
                gr1 = min(row1, chunk_row0 + cs)
                if gc0 >= gc1 or gr0 >= gr1:
                    continue
                out[gr0 - row0 : gr1 - row0, gc0 - col0 : gc1 - col0] = chunk[
                    gr0 - chunk_row0 : gr1 - chunk_row0,
                    gc0 - chunk_col0 : gc1 - chunk_col0,
                ]
        return out

    def is_empty(self) -> bool:
        return not self._chunks


class TilemapLayer:
    """One tilemap layer: a chunked-sparse cell grid + render state.

    ``visible`` / ``opacity`` are render state; ``autotile`` (an
    :class:`AutotileRuleset` or ``None``) selects literal vs auto-tiled placement.
    When ``autotile`` is set the layer keeps the **logical** placement plane
    separate from the derived **display** plane (ADR-0013); when ``None`` the two
    coincide and only the display plane is used. ``get`` / :meth:`cells` report the
    **display** plane (what renders).
    """

    __slots__ = ("name", "visible", "_opacity", "autotile", "_display", "_logical")

    def __init__(
        self,
        name: str = "Layer",
        *,
        visible: bool = True,
        opacity: float = 1.0,
        autotile: Optional[AutotileRuleset] = None,
    ) -> None:
        """Initialise an empty layer with render state and optional auto-tiling."""
        if not isinstance(name, str):
            raise TilemapError(f"layer name must be a string, got {name!r}")
        self.name = name
        self.visible = bool(visible)
        self._opacity = 1.0
        self.opacity = opacity  # validates via setter
        if autotile is not None and not isinstance(autotile, AutotileRuleset):
            raise TilemapError(
                f"autotile must be an AutotileRuleset or None, got {autotile!r}"
            )
        self.autotile = autotile
        self._display = _ChunkGrid()
        self._logical = _ChunkGrid()

    @property
    def opacity(self) -> float:
        """Layer opacity in ``0.0..1.0``."""
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TilemapError(f"opacity must be a number, got {value!r}")
        if not 0.0 <= float(value) <= 1.0:
            raise TilemapError(f"opacity {value} out of range 0.0..1.0")
        self._opacity = float(value)

    def get(self, x: int, y: int) -> int:
        """Return the **display** gid at ``(x, y)`` (``0`` for an unset cell)."""
        _check_coord(x, y)
        return self._display.get(x, y)

    def get_logical(self, x: int, y: int) -> int:
        """Return the **logical** placement gid at ``(x, y)`` (auto-tile plane).

        For a non-auto-tile layer the logical plane mirrors the display plane.
        """
        _check_coord(x, y)
        if self.autotile is None:
            return self._display.get(x, y)
        return self._logical.get(x, y)

    def instance(self, x: int, y: int) -> TileInstance:
        """Return the :class:`TileInstance` view of the display cell at ``(x, y)``."""
        return TileInstance(self.get(x, y))

    def cells(self) -> Iterator[Tuple[int, int, int]]:
        """Yield ``(x, y, gid>0)`` for every non-empty **display** cell."""
        return self._display.cells()

    def _display_chunk_items(
        self,
    ) -> Iterator[Tuple[Tuple[int, int], npt.NDArray[np.uint32]]]:
        return self._display.chunk_items()

    def _logical_chunk_items(
        self,
    ) -> Iterator[Tuple[Tuple[int, int], npt.NDArray[np.uint32]]]:
        return self._logical.chunk_items()


def _apply_flip(
    data: npt.NDArray[np.uint8], flip_h: bool, flip_v: bool, flip_d: bool
) -> npt.NDArray[np.uint8]:
    """Apply Tiled's transform order to a tile pixel array (diagonal -> H -> V).

    ``data`` is an ``(h, w, C)`` array. The diagonal flip is an x/y-axis swap
    (transpose of the first two axes); horizontal is a left-right mirror; vertical
    is a top-bottom mirror (research §2.6).
    """
    out = data
    if flip_d:
        out = np.swapaxes(out, 0, 1)
    if flip_h:
        out = out[:, ::-1]
    if flip_v:
        out = out[::-1, :]
    return np.ascontiguousarray(out)


class _RegionLayerNode:
    """A minimal :class:`~pixelart_creator.logic.blend.CompositeNode` for render.

    Wraps a region-sized RGBA buffer as a NORMAL-blend leaf so
    ``blend.composite_stack`` (CO-4) can flatten the layer stack without any
    ``document`` import (duck-typed protocol, mirroring ``blend._flatten_group``).
    """

    __slots__ = ("_buffer", "opacity", "visible", "blend_mode", "mask")

    def __init__(self, buffer: PixelBuffer, opacity: float) -> None:
        from pixelart_creator.logic.blend import BlendMode

        self._buffer = buffer
        self.opacity = opacity
        self.visible = True
        self.blend_mode = BlendMode.NORMAL
        self.mask: Optional[PixelBuffer] = None

    def effective_buffer(self) -> PixelBuffer:
        return self._buffer


class Tilemap:
    """An ordered stack of layers over a global gid space (linked instances)."""

    __slots__ = (
        "name",
        "infinite",
        "_tile_width",
        "_tile_height",
        "tilesets",
        "layers",
        "tiled_passthrough",
        "_chunk_versions",
    )

    def __init__(
        self,
        *,
        name: str = "Tilemap",
        infinite: bool = True,
        tile_width: int = DEFAULT_TILE_WIDTH,
        tile_height: int = DEFAULT_TILE_HEIGHT,
    ) -> None:
        """Create an empty tilemap with a tile geometry and infinite flag.

        Raises:
            TilemapError: On a non-positive tile dimension or a non-string name.
        """
        if not isinstance(name, str):
            raise TilemapError(f"name must be a string, got {name!r}")
        for label, value in (("tile_width", tile_width), ("tile_height", tile_height)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise TilemapError(f"{label} must be a positive int, got {value!r}")
        self.name = name
        self.infinite = bool(infinite)
        self._tile_width = tile_width
        self._tile_height = tile_height
        self.tilesets: List[Tileset] = []
        self.layers: List[TilemapLayer] = []
        #: Opaque verbatim carrier of Tiled fields the model does not itself model
        #: (properties/wangsets/object layers/counters/unknown keys) so
        #: ``data/tiled_io`` can round-trip losslessly (ADR-0014). Plain JSON-able
        #: data only; NOT serialised into ``.pixproj`` (project_io lists fields).
        self.tiled_passthrough: Dict[str, Any] = {}
        #: Per-chunk mutation counters keyed by chunk-origin ``(cx, cy)``,
        #: aggregated across *all* layers. Bumped by every reversible cell edit
        #: (stamp/erase/fill and each auto-tile neighbour re-resolution) that
        #: touches the chunk, on both apply and undo. The UI keys a per-chunk
        #: QPixmap cache by ``(chunk coord, version)`` (AGT-05 D1); an unseen key
        #: reads ``0``. O(1), zero Qt.
        self._chunk_versions: Dict[Tuple[int, int], int] = {}

    # -- per-chunk cache-invalidation version (AGT-05 D1) -----------------

    def chunk_version(self, cx: int, cy: int) -> int:
        """Return the mutation counter for chunk-origin ``(cx, cy)`` (O(1)).

        Monotonically non-decreasing; bumped whenever a reversible cell edit
        (stamp/erase/fill, incl. every auto-tile neighbour re-resolution) touches
        any layer's cell inside that chunk — on **both** apply and undo. The UI
        keys a per-chunk pixmap cache by ``(cx, cy, chunk_version(cx, cy))`` and
        invalidates only dirtied chunks; an all-empty/unseen chunk reads ``0``.

        Coarser mutations that are NOT per-chunk and must invalidate the whole UI
        cache separately: layer add/remove/reorder/visibility, tileset attach, and
        a tileset source-tile edit (``Tileset.make_edit_tile_command``) — these are
        map-wide and outside this per-chunk counter's scope.

        Note:
            The chunk coordinate is the *tilemap-cell* chunk origin
            (``cell // TILEMAP_CHUNK_SIZE``), i.e. a chunk spans
            ``TILEMAP_CHUNK_SIZE`` cells (= ``TILEMAP_CHUNK_SIZE * tile_width``
            pixels) per axis.
        """
        return self._chunk_versions.get((int(cx), int(cy)), 0)

    def _bump_chunks(self, cells: Iterator[Tuple[int, int]]) -> None:
        """Increment the version of every chunk owning a cell in ``cells``."""
        keys = {_chunk_key(x, y) for x, y in cells}
        versions = self._chunk_versions
        for key in keys:
            versions[key] = versions.get(key, 0) + 1

    @property
    def tile_width(self) -> int:
        """Tile width in pixels."""
        return self._tile_width

    @property
    def tile_height(self) -> int:
        """Tile height in pixels."""
        return self._tile_height

    # -- gid resolution ---------------------------------------------------

    def resolve(self, gid: int) -> Tuple[Tileset, int]:
        """Resolve a gid to ``(tileset, local_id)`` (flags stripped).

        Picks the tileset with the largest ``first_gid <= (gid & GID_MASK)`` that
        also contains the base id (research Topic 3). REQ-P6-LOGIC-005/-013.

        Raises:
            TilemapError: If the base id is empty (``0``) or is owned by no
                referenced tileset.
        """
        if not isinstance(gid, int) or isinstance(gid, bool):
            raise TilemapError(f"gid must be an int, got {gid!r}")
        base = gid & GID_MASK
        if base == 0:
            raise TilemapError("cannot resolve the empty gid (0)")
        best: Optional[Tileset] = None
        for tileset in self.tilesets:
            if tileset.first_gid <= base and tileset.contains_gid(base):
                if best is None or tileset.first_gid > best.first_gid:
                    best = tileset
        if best is None:
            raise TilemapError(f"gid {base} is not in any referenced tileset")
        return best, best.local_id_for_gid(base)

    # -- internal guards --------------------------------------------------

    def _check_layer(self, layer_index: int) -> TilemapLayer:
        if not isinstance(layer_index, int) or isinstance(layer_index, bool):
            raise TilemapError(f"layer_index must be an int, got {layer_index!r}")
        if not 0 <= layer_index < len(self.layers):
            raise TilemapError(f"layer index {layer_index} out of range")
        return self.layers[layer_index]

    def _validate_stampable(self, gid: int) -> None:
        """Validate a stamp gid: empty is allowed; a base id must be known."""
        if not isinstance(gid, int) or isinstance(gid, bool):
            raise TilemapError(f"gid must be an int, got {gid!r}")
        base = gid & GID_MASK
        if base != 0:
            self.resolve(gid)  # raises TilemapError on an unknown base id

    # -- auto-tile display resolution -------------------------------------

    def _occupied(self, layer: TilemapLayer, x: int, y: int) -> bool:
        """Whether the logical cell at ``(x, y)`` is occupied (auto-tile)."""
        return layer.get_logical(x, y) != 0

    def _resolved_display_gid(self, layer: TilemapLayer, x: int, y: int) -> int:
        """Compute the display gid for a logical auto-tile cell from neighbours."""
        assert layer.autotile is not None
        if layer.get_logical(x, y) == 0:
            return 0
        mask = _autotile.mask_from_neighbours(
            self._occupied(layer, x - 1, y - 1),
            self._occupied(layer, x, y - 1),
            self._occupied(layer, x + 1, y - 1),
            self._occupied(layer, x - 1, y),
            self._occupied(layer, x + 1, y),
            self._occupied(layer, x - 1, y + 1),
            self._occupied(layer, x, y + 1),
            self._occupied(layer, x + 1, y + 1),
        )
        return _autotile.resolve_display_gid(layer.autotile, mask)

    def _autotile_command(
        self,
        layer: TilemapLayer,
        changes: List[Tuple[int, int, int]],
        label: str,
    ) -> Command:
        """Build a reversible auto-tile op from logical ``(x, y, logical_gid)`` changes.

        Applies the logical changes, then re-resolves the display gid of every
        changed cell *and* its 8 neighbours (the affected set), capturing the
        prior logical + display gids of that whole set so undo restores it exactly
        (REQ-P6-LOGIC-011). ``logical_gid`` must be ``0`` (erase) or the ruleset's
        terrain gid.
        """
        assert layer.autotile is not None
        terrain = layer.autotile.terrain_gid
        for _x, _y, logical_gid in changes:
            if logical_gid not in (0, terrain):
                raise TilemapError(
                    f"auto-tile placement gid {logical_gid} must be 0 or the "
                    f"ruleset terrain gid {terrain}"
                )
        # Affected set = changed cells plus their 8 neighbours (display re-resolve).
        affected = set()
        for x, y, _g in changes:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    affected.add((x + dx, y + dy))
        affected_cells = sorted(affected)
        prior_logical = {(x, y): layer._logical.get(x, y) for x, y in affected_cells}
        prior_display = {(x, y): layer._display.get(x, y) for x, y in affected_cells}
        new_logical = dict(prior_logical)
        for x, y, logical_gid in changes:
            new_logical[(x, y)] = logical_gid

        def _apply(logical_state: Dict[Tuple[int, int], int]) -> None:
            for (x, y), gid in logical_state.items():
                layer._logical.set(x, y, gid)
            for x, y in affected_cells:
                layer._display.set(x, y, self._resolved_display_gid(layer, x, y))

        def _do() -> None:
            _apply(new_logical)
            self._bump_chunks(iter(affected_cells))

        def _undo() -> None:
            for (x, y), gid in prior_logical.items():
                layer._logical.set(x, y, gid)
            for (x, y), gid in prior_display.items():
                layer._display.set(x, y, gid)
            self._bump_chunks(iter(affected_cells))

        return FunctionCommand(_do, _undo, label=label)

    # -- reversible cell ops (return an UNAPPLIED history.Command) --------

    def make_stamp_command(self, layer_index: int, x: int, y: int, gid: int) -> Command:
        """Build a command placing a linked instance at ``(x, y)`` (REQ-P6-LOGIC-007).

        On a literal layer the cell is set to ``gid`` (base id + flip flags);
        undo restores the prior cell. On an auto-tile layer ``gid`` records the
        logical terrain placement and the display gids of the cell and its
        re-resolved neighbours are captured for undo (REQ-P6-LOGIC-011).

        Raises:
            TilemapError: On a bad layer/coord or an unknown base gid.
        """
        layer = self._check_layer(layer_index)
        _check_coord(x, y)
        self._validate_stampable(gid)
        if layer.autotile is not None:
            return self._autotile_command(layer, [(x, y, gid & GID_MASK)], "stamp")
        old = layer._display.get(x, y)
        chunk = _chunk_key(x, y)

        def _do() -> None:
            layer._display.set(x, y, gid)
            self._chunk_versions[chunk] = self._chunk_versions.get(chunk, 0) + 1

        def _undo() -> None:
            layer._display.set(x, y, old)
            self._chunk_versions[chunk] = self._chunk_versions.get(chunk, 0) + 1

        return FunctionCommand(_do, _undo, label="stamp")

    def make_erase_command(self, layer_index: int, x: int, y: int) -> Command:
        """Build a command clearing the cell at ``(x, y)`` (REQ-P6-LOGIC-007).

        Undo restores the prior instance (id + orientation). On an auto-tile layer
        the erased cell's neighbours are re-resolved and restored on undo.
        """
        layer = self._check_layer(layer_index)
        _check_coord(x, y)
        if layer.autotile is not None:
            return self._autotile_command(layer, [(x, y, 0)], "erase")
        old = layer._display.get(x, y)
        chunk = _chunk_key(x, y)

        def _do() -> None:
            layer._display.set(x, y, 0)
            self._chunk_versions[chunk] = self._chunk_versions.get(chunk, 0) + 1

        def _undo() -> None:
            layer._display.set(x, y, old)
            self._chunk_versions[chunk] = self._chunk_versions.get(chunk, 0) + 1

        return FunctionCommand(_do, _undo, label="erase")

    def make_fill_rect_command(
        self, layer_index: int, x: int, y: int, w: int, h: int, gid: int
    ) -> Command:
        """Build a command filling a ``w`` x ``h`` cell rectangle with ``gid``.

        One reversible op (REQ-P6-LOGIC-007). Undo restores every prior cell in
        the rectangle. On an auto-tile layer the whole rectangle is placed
        logically and the rectangle + its border are re-resolved/restored.

        Raises:
            TilemapError: On a bad layer/coord, a non-positive size, or an unknown
                base gid.
        """
        layer = self._check_layer(layer_index)
        _check_coord(x, y)
        _check_coord(x + w - 1, y + h - 1)
        if not isinstance(w, int) or isinstance(w, bool) or w <= 0:
            raise TilemapError(f"width must be a positive int, got {w!r}")
        if not isinstance(h, int) or isinstance(h, bool) or h <= 0:
            raise TilemapError(f"height must be a positive int, got {h!r}")
        self._validate_stampable(gid)
        cells = [(cx, cy) for cy in range(y, y + h) for cx in range(x, x + w)]
        if layer.autotile is not None:
            base = gid & GID_MASK
            changes = [(cx, cy, base) for cx, cy in cells]
            return self._autotile_command(layer, changes, "fill rectangle")
        prior = {(cx, cy): layer._display.get(cx, cy) for cx, cy in cells}
        chunks = {_chunk_key(cx, cy) for cx, cy in cells}

        def _bump() -> None:
            for key in chunks:
                self._chunk_versions[key] = self._chunk_versions.get(key, 0) + 1

        def _do() -> None:
            for cx, cy in cells:
                layer._display.set(cx, cy, gid)
            _bump()

        def _undo() -> None:
            for (cx, cy), old in prior.items():
                layer._display.set(cx, cy, old)
            _bump()

        return FunctionCommand(_do, _undo, label="fill rectangle")

    # -- reversible layer ops ---------------------------------------------

    def make_add_layer_command(
        self, *, name: str = "Layer", at: Optional[int] = None
    ) -> Command:
        """Build a command inserting a new empty layer (REQ-P6-LOGIC-008).

        ``at`` is the insertion index (append when ``None``). Undo removes exactly
        the inserted layer.

        Raises:
            TilemapError: If the map is at :data:`MAX_TILEMAP_LAYERS` or ``at`` is
                out of the valid insertion range.
        """
        if len(self.layers) >= MAX_TILEMAP_LAYERS:
            raise TilemapError(
                f"tilemap already at MAX_TILEMAP_LAYERS ({MAX_TILEMAP_LAYERS})"
            )
        index = len(self.layers) if at is None else at
        if not isinstance(index, int) or isinstance(index, bool):
            raise TilemapError(f"at must be an int or None, got {at!r}")
        if not 0 <= index <= len(self.layers):
            raise TilemapError(f"insertion index {index} out of range")
        layer = TilemapLayer(name)

        def _do() -> None:
            self.layers.insert(index, layer)

        def _undo() -> None:
            self.layers.remove(layer)

        return FunctionCommand(_do, _undo, label="add layer")

    def make_remove_layer_command(self, layer_index: int) -> Command:
        """Build a command removing a layer, restorable at its exact position."""
        layer = self._check_layer(layer_index)

        def _do() -> None:
            self.layers.remove(layer)

        def _undo() -> None:
            self.layers.insert(layer_index, layer)

        return FunctionCommand(_do, _undo, label="remove layer")

    def make_move_layer_command(self, from_index: int, to_index: int) -> Command:
        """Build a command reordering a layer (z-order). Undo restores the order."""
        self._check_layer(from_index)
        if not isinstance(to_index, int) or isinstance(to_index, bool):
            raise TilemapError(f"to_index must be an int, got {to_index!r}")
        if not 0 <= to_index < len(self.layers):
            raise TilemapError(f"to_index {to_index} out of range")
        layer = self.layers[from_index]

        def _do() -> None:
            self.layers.pop(from_index)
            self.layers.insert(to_index, layer)

        def _undo() -> None:
            self.layers.pop(to_index)
            self.layers.insert(from_index, layer)

        return FunctionCommand(_do, _undo, label="move layer")

    def make_set_layer_visibility_command(
        self, layer_index: int, visible: bool
    ) -> Command:
        """Build a command toggling a layer's visibility (REQ-P6-LOGIC-008)."""
        layer = self._check_layer(layer_index)
        old = layer.visible
        new = bool(visible)

        def _do() -> None:
            layer.visible = new

        def _undo() -> None:
            layer.visible = old

        return FunctionCommand(_do, _undo, label="set layer visibility")

    def make_attach_tileset_command(self, tileset: Tileset) -> Command:
        """Build a command attaching a tileset to the map's gid space.

        Raises:
            TilemapError: If ``tileset`` is not a :class:`Tileset`.
        """
        if not isinstance(tileset, Tileset):
            raise TilemapError(f"tileset must be a Tileset, got {tileset!r}")

        def _do() -> None:
            self.tilesets.append(tileset)

        def _undo() -> None:
            self.tilesets.remove(tileset)

        return FunctionCommand(_do, _undo, label="attach tileset")

    # -- render -----------------------------------------------------------

    def _transform_gid(self, gid: int) -> npt.NDArray[np.uint8]:
        """Resolve a nonzero gid to its flip-applied ``(h, w, 4)`` tile pixels.

        Reads the tile's sub-rectangle directly from the *current* tileset source
        array (the same pixels :meth:`Tileset.tile_pixels` would copy, PB-1 live
        linking) and applies the flip transform. Read-only over the source —
        :func:`_apply_flip` returns a fresh contiguous copy — so rendering stays
        non-destructive while avoiding a per-tile :class:`PixelBuffer` allocation.

        Raises:
            TilemapError: On an unknown gid or a non-RGBA tileset source.
        """
        tileset, local_id = self.resolve(gid)
        if tileset.mode is not ColorMode.RGBA:
            raise TilemapError(
                "render_region requires RGBA tileset sources, got "
                f"{tileset.mode.value}"
            )
        region = tileset.region_of(local_id)
        arr = tileset.source.data[
            region.y : region.y + region.height,
            region.x : region.x + region.width,
        ]
        instance = TileInstance(gid)
        return _apply_flip(arr, instance.flip_h, instance.flip_v, instance.flip_d)

    def _render_layer_region(
        self, layer: TilemapLayer, x: int, y: int, w: int, h: int
    ) -> PixelBuffer:
        """Render a single layer over a pixel region into an RGBA buffer.

        Vectorised, O(unique gids + visible chunks) — never O(cells) in Python.
        Gathers the intersecting cell window from the chunk store in one numpy
        pass (:meth:`_ChunkGrid.region`), resolves each *distinct* gid once (a
        stripped-flag atlas lookup + one flip transform), scatters those tile
        pixels across all cells that carry the gid, and assembles the full cell
        window as ``(rows*th, cols*tw, 4)`` before cropping to the requested
        pixel region. Within a layer the fixed-size, grid-aligned tiles never
        overlap, so a scatter-then-crop is byte-identical to the previous
        per-cell alpha-blit over a transparent buffer (RGB is forced to ``0``
        where alpha is ``0``, matching that blit). A tileset whose tile size
        differs from the tilemap's (tiles could overlap / change shape under a
        diagonal flip) falls back to the exact per-cell blit path (:meth:
        `_blit_layer_region`).
        """
        tw, th = self._tile_width, self._tile_height
        first_col = x // tw
        last_col = (x + w - 1) // tw
        first_row = y // th
        last_row = (y + h - 1) // th
        n_cols = last_col - first_col + 1
        n_rows = last_row - first_row + 1

        gid_grid = layer._display.region(first_col, first_row, n_cols, n_rows)
        out = PixelBuffer(w, h, ColorMode.RGBA)
        if not gid_grid.any():
            return out

        transformed: Dict[int, npt.NDArray[np.uint8]] = {}
        uniform = True
        for raw in np.unique(gid_grid):
            gid = int(raw)
            if gid == 0:
                continue
            flipped = self._transform_gid(gid)
            transformed[gid] = flipped
            if flipped.shape[0] != th or flipped.shape[1] != tw:
                uniform = False

        if not uniform:
            return self._blit_layer_region(
                gid_grid, first_col, first_row, x, y, w, h, transformed
            )

        tile_stack = np.zeros((n_rows, n_cols, th, tw, 4), dtype=np.uint8)
        for gid, flipped in transformed.items():
            rows, cols = np.nonzero(gid_grid == gid)
            tile_stack[rows, cols] = flipped
        # (R, C, th, tw, 4) -> (R, th, C, tw, 4) -> (R*th, C*tw, 4).
        layer_full = tile_stack.transpose(0, 2, 1, 3, 4).reshape(
            n_rows * th, n_cols * tw, 4
        )
        ox = x - first_col * tw
        oy = y - first_row * th
        out.data[:, :] = layer_full[oy : oy + h, ox : ox + w]
        transparent = out.data[:, :, 3] == 0
        out.data[transparent, :3] = 0  # match blit-over-transparent RGB clearing
        return out

    def _blit_layer_region(
        self,
        gid_grid: npt.NDArray[np.uint32],
        first_col: int,
        first_row: int,
        x: int,
        y: int,
        w: int,
        h: int,
        transformed: Dict[int, npt.NDArray[np.uint8]],
    ) -> PixelBuffer:
        """Per-cell alpha-blit fallback for non-uniform tile sizes.

        Preserves the exact prior placement/overlap semantics (row-major blit
        order, ``blend=True``) for the rare case where a tileset's tile size
        differs from the tilemap's tile geometry.
        """
        out = PixelBuffer(w, h, ColorMode.RGBA)
        tw, th = self._tile_width, self._tile_height
        n_rows, n_cols = gid_grid.shape
        for r in range(n_rows):
            row = gid_grid[r]
            cy = first_row + r
            for c in range(n_cols):
                gid = int(row[c])
                if gid == 0:
                    continue
                flipped = transformed[gid]
                placed = PixelBuffer(flipped.shape[1], flipped.shape[0], ColorMode.RGBA)
                placed.data[:, :] = flipped
                cx = first_col + c
                out.blit(placed, cx * tw - x, cy * th - y, blend=True)
        return out

    def render_region(self, x: int, y: int, w: int, h: int) -> PixelBuffer:
        """Render the composited visible layer stack over a pixel region (PB-1/CO-4).

        Resolves only the cells intersecting the ``(x, y, w, h)`` **pixel** region
        (the viewport-culling seam AGT-10 plugs into, DEP-3), applies each
        instance's flip vectorised over the chunk (:meth:`_render_layer_region`),
        and flattens the visible layer stack via ``blend.composite_stack`` (CO-4).
        Non-destructive: the tileset source buffers and the cell data are
        byte-for-byte unchanged (REQ-P6-LOGIC-013).

        A single visible layer at full opacity short-circuits the compositor: its
        rendered region already equals its own ``NORMAL`` composite over a
        transparent backdrop (RGB is cleared where alpha is ``0``), so returning
        it is byte-identical to ``composite_stack`` while skipping the float64
        ``blend_over`` pass (the dominant per-frame cost). Two or more visible
        layers — or any layer with ``opacity < 1.0`` — go through
        ``composite_stack`` unchanged, keeping ``NORMAL`` bit-exact.

        Raises:
            TilemapError: On a non-positive / out-of-bounds region size, an unknown
                gid, or a non-RGBA tileset source.
        """
        for label, value in (("w", w), ("h", h)):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise TilemapError(f"{label} must be a positive int, got {value!r}")
        if w > MAX_CANVAS_WIDTH or h > MAX_CANVAS_HEIGHT:
            raise TilemapError(
                f"render region {w}x{h} exceeds canvas bounds "
                f"{MAX_CANVAS_WIDTH}x{MAX_CANVAS_HEIGHT}"
            )
        _check_coord(x, y)
        visible = [layer for layer in self.layers if layer.visible]
        if len(visible) == 1 and visible[0].opacity == 1.0:
            return self._render_layer_region(visible[0], x, y, w, h)
        nodes: List[_RegionLayerNode] = []
        for layer in visible:
            region_buffer = self._render_layer_region(layer, x, y, w, h)
            nodes.append(_RegionLayerNode(region_buffer, layer.opacity))
        return composite_stack(nodes, w, h)

    def __repr__(self) -> str:
        """Return a debug representation of the tilemap."""
        return (
            f"Tilemap({self.name!r}, {len(self.layers)} layers, "
            f"{len(self.tilesets)} tilesets, infinite={self.infinite})"
        )
