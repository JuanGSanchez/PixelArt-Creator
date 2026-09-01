# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tileset model — slice a source image into indexed tiles (zero Qt, S11).

A :class:`Tileset` references a source
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` and slices it into a
deterministic row-major grid of fixed-size tiles honouring
``margin`` (border before the first tile) and ``spacing`` (gap between tiles) —
the Tiled slicing formula (research §2.2). A tile is defined only by its
``(tileset, local_id) -> source-region`` mapping (PB-1): reading a tile derives
its pixels from the *current* source via :meth:`PixelBuffer.region`, so the
tileset stores **no** detached pixel copy and a source-tile edit is seen by every
reader (the linking mechanism behind REQ-P6-LOGIC-004/-006). Tiles inherit the
source's :class:`~pixelart_creator.logic.pixel_buffer.ColorMode` (CM-1).

Multiple tilesets compose into a Tiled-style **global gid space** via a
per-tileset ``first_gid`` offset (research Topic 3): ``local_id = gid - first_gid``.
Every mutating op is a reversible :class:`~pixelart_creator.logic.history.Command`
(HIS-1) so ``ui/commands.py`` wraps it as one ``QUndoCommand`` (ADR-0015). This
module imports only ``pixel_buffer``/``history``/``constants`` — never
``document`` or Qt (PL6-D3).
"""

from __future__ import annotations

from dataclasses import dataclass

from pixelart_creator.logic.constants import (
    DEFAULT_TILE_HEIGHT,
    DEFAULT_TILE_MARGIN,
    DEFAULT_TILE_SPACING,
    DEFAULT_TILE_WIDTH,
    MAX_TILE_DIMENSION,
    MAX_TILESET_TILES,
)
from pixelart_creator.logic.history import Command, FunctionCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = ["TilesetError", "TileRegion", "Tileset"]


class TilesetError(ValueError):
    """Raised on invalid slicing parameters, tile ids, or edit geometry."""


@dataclass(frozen=True)
class TileRegion:
    """A tile's source sub-rectangle in pixels: ``(x, y, width, height)``."""

    x: int
    y: int
    width: int
    height: int


def _check_positive_dim(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TilesetError(f"{name} must be an int, got {value!r}")
    if value <= 0:
        raise TilesetError(f"{name} must be positive, got {value}")
    if value > MAX_TILE_DIMENSION:
        raise TilesetError(
            f"{name} {value} exceeds MAX_TILE_DIMENSION ({MAX_TILE_DIMENSION})"
        )
    return value


def _check_non_negative(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TilesetError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise TilesetError(f"{name} must be non-negative, got {value}")
    return value


def _grid_count(extent: int, tile: int, margin: int, spacing: int) -> int:
    """Return how many tiles fit along one axis (Tiled formula; 0 if none fit).

    ``n`` tiles occupy ``margin + n*tile + (n-1)*spacing`` px, so
    ``n = (extent - margin + spacing) // (tile + spacing)`` (research §2.2),
    clamped at 0 when the first tile does not fit.
    """
    usable = extent - margin + spacing
    if usable <= 0:
        return 0
    return max(0, usable // (tile + spacing))


class Tileset:
    """A source image sliced into a deterministic grid of indexed tiles."""

    __slots__ = (
        "_source",
        "_tile_width",
        "_tile_height",
        "_margin",
        "_spacing",
        "name",
        "_first_gid",
    )

    def __init__(
        self,
        source: PixelBuffer,
        *,
        tile_width: int = DEFAULT_TILE_WIDTH,
        tile_height: int = DEFAULT_TILE_HEIGHT,
        margin: int = DEFAULT_TILE_MARGIN,
        spacing: int = DEFAULT_TILE_SPACING,
        name: str = "Tileset",
        first_gid: int = 1,
    ) -> None:
        """Slice ``source`` deterministically into an indexed tile grid.

        Args:
            source: The backing :class:`PixelBuffer` (tiles are its regions).
            tile_width, tile_height: Tile size, px (``1..MAX_TILE_DIMENSION``).
            margin: Border offset before the first tile, px (``>= 0``).
            spacing: Gap between adjacent tiles, px (``>= 0``).
            name: Human-readable tileset name.
            first_gid: This tileset's first global tile id (``>= 1``; Tiled's
                first tileset is ``1``).

        Raises:
            TilesetError: On a non-:class:`PixelBuffer` source, invalid slicing
                parameters, a tile count over :data:`MAX_TILESET_TILES`, or an
                invalid ``first_gid``.
        """
        if not isinstance(source, PixelBuffer):
            raise TilesetError(f"source must be a PixelBuffer, got {source!r}")
        self._source = source
        self._tile_width = _check_positive_dim("tile_width", tile_width)
        self._tile_height = _check_positive_dim("tile_height", tile_height)
        self._margin = _check_non_negative("margin", margin)
        self._spacing = _check_non_negative("spacing", spacing)
        if not isinstance(name, str):
            raise TilesetError(f"name must be a string, got {name!r}")
        self.name = name
        self._set_first_gid(first_gid)
        # Validate the resulting tile count against the defensive bound.
        _ = self._validated_count(
            self._tile_width, self._tile_height, self._margin, self._spacing
        )

    # -- internal validation ---------------------------------------------

    def _set_first_gid(self, first_gid: int) -> None:
        if not isinstance(first_gid, int) or isinstance(first_gid, bool):
            raise TilesetError(f"first_gid must be an int, got {first_gid!r}")
        if first_gid < 1:
            raise TilesetError(f"first_gid must be >= 1, got {first_gid}")
        self._first_gid = first_gid

    def _validated_count(
        self, tile_width: int, tile_height: int, margin: int, spacing: int
    ) -> int:
        columns = _grid_count(self._source.width, tile_width, margin, spacing)
        rows = _grid_count(self._source.height, tile_height, margin, spacing)
        count = columns * rows
        if count > MAX_TILESET_TILES:
            raise TilesetError(
                f"tile count {count} exceeds MAX_TILESET_TILES "
                f"({MAX_TILESET_TILES})"
            )
        return count

    # -- geometry ---------------------------------------------------------

    @property
    def source(self) -> PixelBuffer:
        """The backing source :class:`PixelBuffer` (tiles are its regions)."""
        return self._source

    @property
    def tile_width(self) -> int:
        """Tile width in pixels."""
        return self._tile_width

    @property
    def tile_height(self) -> int:
        """Tile height in pixels."""
        return self._tile_height

    @property
    def margin(self) -> int:
        """Border offset before the first tile, px."""
        return self._margin

    @property
    def spacing(self) -> int:
        """Gap between adjacent tiles, px."""
        return self._spacing

    @property
    def columns(self) -> int:
        """Number of tile columns produced by the current slicing."""
        return _grid_count(
            self._source.width, self._tile_width, self._margin, self._spacing
        )

    @property
    def rows(self) -> int:
        """Number of tile rows produced by the current slicing."""
        return _grid_count(
            self._source.height, self._tile_height, self._margin, self._spacing
        )

    @property
    def tile_count(self) -> int:
        """Total number of tiles (``columns * rows``)."""
        return self.columns * self.rows

    @property
    def mode(self) -> ColorMode:
        """Storage mode of the tiles — inherited from the source (CM-1)."""
        return self._source.mode

    @property
    def first_gid(self) -> int:
        """This tileset's first global tile id (Tiled first-gid offset)."""
        return self._first_gid

    # -- id <-> region ----------------------------------------------------

    def _check_local_id(self, local_id: int) -> None:
        if not isinstance(local_id, int) or isinstance(local_id, bool):
            raise TilesetError(f"local_id must be an int, got {local_id!r}")
        if not 0 <= local_id < self.tile_count:
            raise TilesetError(
                f"local_id {local_id} out of range 0..{self.tile_count - 1}"
            )

    def region_of(self, local_id: int) -> TileRegion:
        """Return the source sub-rectangle for ``local_id`` (pure, total).

        Ids are assigned row-major (left-to-right, top-to-bottom). The mapping is
        a pure total function over ``0..tile_count-1`` and identical on repeat
        (P2, REQ-P6-LOGIC-003).

        Raises:
            TilesetError: If ``local_id`` is out of the valid range.
        """
        self._check_local_id(local_id)
        columns = self.columns
        col = local_id % columns
        row = local_id // columns
        px = self._margin + col * (self._tile_width + self._spacing)
        py = self._margin + row * (self._tile_height + self._spacing)
        return TileRegion(px, py, self._tile_width, self._tile_height)

    def tile_pixels(self, local_id: int) -> PixelBuffer:
        """Return a tile's pixels, derived from the *current* source (PB-1).

        Reads the tile's region from the live source buffer via
        :meth:`PixelBuffer.region`; no detached copy is stored, so a source-tile
        edit (:meth:`make_edit_tile_command`) is seen by every reader
        (REQ-P6-LOGIC-002/-004/-006).

        Raises:
            TilesetError: If ``local_id`` is out of range.
        """
        region = self.region_of(local_id)
        return self._source.region(region.x, region.y, region.width, region.height)

    # -- global gid space -------------------------------------------------

    def contains_gid(self, gid: int) -> bool:
        """Return ``True`` if ``gid`` (base, flags stripped) belongs to this set.

        A gid belongs when ``first_gid <= gid < first_gid + tile_count``.
        """
        if not isinstance(gid, int) or isinstance(gid, bool):
            return False
        return self._first_gid <= gid < self._first_gid + self.tile_count

    def local_id_for_gid(self, gid: int) -> int:
        """Return ``gid - first_gid`` for a gid this tileset owns.

        Raises:
            TilesetError: If ``gid`` is not owned by this tileset.
        """
        if not self.contains_gid(gid):
            raise TilesetError(f"gid {gid!r} is not in this tileset")
        return gid - self._first_gid

    # -- reversible ops (return an UNAPPLIED history.Command) -------------

    def make_edit_tile_command(self, local_id: int, edited: PixelBuffer) -> Command:
        """Build a command overwriting a tile's source sub-rectangle (HIS-1).

        Writes ``edited`` (a ``tile_width x tile_height`` buffer of the tileset's
        mode) into the source rectangle for ``local_id``, so every reader of that
        id sees the change (REQ-P6-LOGIC-004/-006). Undo restores the prior source
        pixels exactly. Returned **unapplied** for ``ui/commands.py`` to wrap as
        one ``QUndoCommand``.

        Raises:
            TilesetError: If ``local_id`` is out of range or ``edited`` has the
                wrong mode or geometry.
        """
        region = self.region_of(local_id)
        if not isinstance(edited, PixelBuffer):
            raise TilesetError(f"edited must be a PixelBuffer, got {edited!r}")
        if edited.mode is not self._source.mode:
            raise TilesetError(
                f"edited mode {edited.mode.value} must match source "
                f"{self._source.mode.value}"
            )
        if edited.width != region.width or edited.height != region.height:
            raise TilesetError(
                f"edited geometry {edited.width}x{edited.height} must match tile "
                f"{region.width}x{region.height}"
            )
        before = self._source.region(region.x, region.y, region.width, region.height)
        after = edited.copy()
        source = self._source

        def _do() -> None:
            source.blit(after, region.x, region.y)

        def _undo() -> None:
            source.blit(before, region.x, region.y)

        return FunctionCommand(_do, _undo, label="edit tile")

    def make_reslice_command(
        self,
        *,
        tile_width: int,
        tile_height: int,
        margin: int,
        spacing: int,
    ) -> Command:
        """Build a command reconfiguring the slicing reversibly (REQ-P6-UI-002).

        Validates the new geometry (bounds + resulting tile count) at build time;
        undo restores the exact prior slicing configuration.

        Raises:
            TilesetError: On invalid parameters or a tile count over
                :data:`MAX_TILESET_TILES`.
        """
        new_tw = _check_positive_dim("tile_width", tile_width)
        new_th = _check_positive_dim("tile_height", tile_height)
        new_margin = _check_non_negative("margin", margin)
        new_spacing = _check_non_negative("spacing", spacing)
        self._validated_count(new_tw, new_th, new_margin, new_spacing)
        old = (self._tile_width, self._tile_height, self._margin, self._spacing)

        def _do() -> None:
            self._tile_width = new_tw
            self._tile_height = new_th
            self._margin = new_margin
            self._spacing = new_spacing

        def _undo() -> None:
            (
                self._tile_width,
                self._tile_height,
                self._margin,
                self._spacing,
            ) = old

        return FunctionCommand(_do, _undo, label="reslice tileset")

    def __repr__(self) -> str:
        """Return a debug representation of the tileset geometry."""
        return (
            f"Tileset({self.name!r}, {self.columns}x{self.rows} tiles, "
            f"{self._tile_width}x{self._tile_height}px, first_gid={self._first_gid})"
        )
