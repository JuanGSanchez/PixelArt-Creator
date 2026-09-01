# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Indexed-colour palette model (zero Qt, S11).

A :class:`Palette` is an ordered list of RGBA colours addressed by index. It
backs *indexed* :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` mode
(Phase 1) and is the foundation the Phase 3 colour/palette system extends
(ramps, cycling, constraints, extraction). Kept intentionally small here.
"""

from __future__ import annotations

from typing import Iterable, Iterator, List, Optional

from pixelart_creator.logic.color import RGBA, distance_sq, is_rgba, rgba
from pixelart_creator.logic.constants import MAX_PALETTE_SIZE

#: Maximum entries in an indexed palette (8-bit index space). Re-exported from
#: :mod:`pixelart_creator.logic.constants` (single source, S12) for callers that
#: import it from here (e.g. ``data.project_io``).
__all__ = ["MAX_PALETTE_SIZE", "PaletteError", "Palette"]


class PaletteError(ValueError):
    """Raised on an invalid palette index or operation."""


class Palette:
    """An ordered, index-addressable collection of RGBA colours."""

    __slots__ = ("_colors",)

    def __init__(self, colors: Optional[Iterable[RGBA]] = None) -> None:
        """Create a palette from ``colors`` (empty if omitted)."""
        self._colors: List[RGBA] = []
        if colors is not None:
            for c in colors:
                self.append(c)

    def __len__(self) -> int:
        """Return the number of colours in the palette."""
        return len(self._colors)

    def __iter__(self) -> Iterator[RGBA]:
        """Iterate over the palette colours in order."""
        return iter(self._colors)

    def __eq__(self, other: object) -> bool:
        """Return whether ``other`` is a palette with identical ordered colours."""
        if not isinstance(other, Palette):
            return NotImplemented
        return self._colors == other._colors

    def __repr__(self) -> str:
        """Return the ``eval``-friendly representation of the palette."""
        return f"Palette({self._colors!r})"

    def _check_index(self, index: int) -> int:
        if not isinstance(index, int) or isinstance(index, bool):
            raise PaletteError(f"palette index must be an int, got {index!r}")
        if index < 0 or index >= len(self._colors):
            raise PaletteError(
                f"palette index {index} out of range 0..{len(self._colors) - 1}"
            )
        return index

    def get(self, index: int) -> RGBA:
        """Return the colour at ``index``."""
        return self._colors[self._check_index(index)]

    def set(self, index: int, color: RGBA) -> None:
        """Replace the colour at ``index``."""
        self._colors[self._check_index(index)] = rgba(*color)

    def append(self, color: RGBA) -> int:
        """Append ``color`` and return its new index."""
        if not is_rgba(color):
            raise PaletteError(f"not an RGBA colour: {color!r}")
        if len(self._colors) >= MAX_PALETTE_SIZE:
            raise PaletteError(f"palette is full ({MAX_PALETTE_SIZE} colours)")
        self._colors.append(rgba(*color))
        return len(self._colors) - 1

    def remove_at(self, index: int) -> RGBA:
        """Remove and return the colour at ``index`` (shifts later indices down)."""
        return self._colors.pop(self._check_index(index))

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder: move the colour at ``from_index`` to ``to_index``."""
        self._check_index(from_index)
        if not isinstance(to_index, int) or isinstance(to_index, bool):
            raise PaletteError(f"target index must be an int, got {to_index!r}")
        if to_index < 0 or to_index >= len(self._colors):
            raise PaletteError(f"target index {to_index} out of range")
        color = self._colors.pop(from_index)
        self._colors.insert(to_index, color)

    def index_of(self, color: RGBA) -> Optional[int]:
        """Return the first index holding ``color`` exactly, or ``None``."""
        target = rgba(*color)
        for i, c in enumerate(self._colors):
            if c == target:
                return i
        return None

    def nearest_index(self, color: RGBA) -> int:
        """Return the index of the closest colour by squared RGBA distance.

        Ties resolve to the lower index (deterministic, P2).

        Raises:
            PaletteError: If the palette is empty.
        """
        if not self._colors:
            raise PaletteError("cannot match against an empty palette")
        target = rgba(*color)
        best_index = 0
        best_dist = distance_sq(target, self._colors[0])
        for i in range(1, len(self._colors)):
            dist = distance_sq(target, self._colors[i])
            if dist < best_dist:
                best_dist, best_index = dist, i
        return best_index

    def replace(self, colors: Iterable[RGBA]) -> None:
        """Replace all colours in place with ``colors`` (bounds-checked).

        Mutates *this* palette object rather than rebinding a new one, so the
        scene / palette panel / editor references stay valid — the pattern the
        drag-drop palette load relies on for a reversible ``apply ∘ undo =
        identity`` step (plan §6, REQ-DDI-UI-005). Validation is done up front on
        a staged list, so an invalid colour or an oversized palette raises
        **before** any mutation: on failure this palette is left untouched
        (atomic replace).

        Args:
            colors: The new colours, in order.

        Raises:
            PaletteError: If any colour is not a valid RGBA tuple, or the new
                length exceeds ``MAX_PALETTE_SIZE``.
        """
        staged: List[RGBA] = []
        for c in colors:
            if not is_rgba(c):
                raise PaletteError(f"not an RGBA colour: {c!r}")
            staged.append(rgba(*c))
        if len(staged) > MAX_PALETTE_SIZE:
            raise PaletteError(
                f"palette has {len(staged)} colours, exceeds {MAX_PALETTE_SIZE}"
            )
        self._colors[:] = staged

    def colors(self) -> List[RGBA]:
        """Return a shallow copy of the colour list."""
        return list(self._colors)

    def copy(self) -> "Palette":
        """Return an independent copy of this palette."""
        return Palette(self._colors)
