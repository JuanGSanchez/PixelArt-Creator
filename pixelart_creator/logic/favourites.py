"""Persisted Favourites colour model — ordered, de-duplicated (zero Qt, S11).

The Qt-free model backing the colour-hub Favourites list: an ordered,
de-duplicated list of favourite :data:`~pixelart_creator.logic.color.RGBA`
colours with add / remove / reorder and a JSON-serialisable form
(:meth:`Favourites.to_serializable` / :meth:`Favourites.from_serializable`). The
UI/data layer persists it (``data/favourites_io.py``, ADR-0004). A soft cap
(``FAVOURITES_MAX``) bounds the list defensively (Article VII). REQ-P3-LOGIC-015.
"""

from __future__ import annotations

from typing import Iterable, Iterator, List, Optional

from pixelart_creator.logic.color import RGBA, from_hex, is_rgba, rgba, to_hex
from pixelart_creator.logic.constants import FAVOURITES_MAX

__all__ = ["FavouritesError", "Favourites"]


class FavouritesError(ValueError):
    """Raised on a malformed colour, over-cap add, or bad serialised data."""


class Favourites:
    """An ordered, de-duplicated list of favourite RGBA colours."""

    __slots__ = ("_colors", "_max_size")

    def __init__(
        self, colors: Optional[Iterable[RGBA]] = None, *, max_size: int = FAVOURITES_MAX
    ) -> None:
        """Create a Favourites list, optionally seeded with ``colors``.

        Raises:
            FavouritesError: If ``max_size`` is not a positive int, a seed colour
                is malformed, or the seed exceeds ``max_size``.
        """
        if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size <= 0:
            raise FavouritesError(f"max_size must be a positive int, got {max_size!r}")
        self._max_size = max_size
        self._colors: List[RGBA] = []
        if colors is not None:
            for c in colors:
                self.add(c)

    def add(self, color: RGBA) -> None:
        """Append ``color`` if absent; a no-op if already present (de-dup).

        Raises:
            FavouritesError: If ``color`` is malformed, or adding a new colour
                would exceed ``max_size``.
        """
        if not is_rgba(color):
            raise FavouritesError(f"not an RGBA colour: {color!r}")
        normalised = rgba(*color)
        if normalised in self._colors:
            return
        if len(self._colors) >= self._max_size:
            raise FavouritesError(f"favourites is full ({self._max_size} colours)")
        self._colors.append(normalised)

    def remove(self, color: RGBA) -> None:
        """Remove ``color``.

        Raises:
            FavouritesError: If ``color`` is malformed or not present.
        """
        if not is_rgba(color):
            raise FavouritesError(f"not an RGBA colour: {color!r}")
        normalised = rgba(*color)
        try:
            self._colors.remove(normalised)
        except ValueError as exc:
            raise FavouritesError(f"colour not in favourites: {color!r}") from exc

    def move(self, from_index: int, to_index: int) -> None:
        """Reorder: move the favourite at ``from_index`` to ``to_index``.

        Raises:
            FavouritesError: If either index is out of range.
        """
        n = len(self._colors)
        for name, value in (("from_index", from_index), ("to_index", to_index)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise FavouritesError(f"{name} must be an int, got {value!r}")
            if not (0 <= value < n):
                raise FavouritesError(f"{name} {value} out of range 0..{n - 1}")
        color = self._colors.pop(from_index)
        self._colors.insert(to_index, color)

    def colors(self) -> List[RGBA]:
        """Return a shallow copy of the favourites in order."""
        return list(self._colors)

    def __contains__(self, color: object) -> bool:
        """Return True if `color` is a valid RGBA tuple already in the favourites."""
        return is_rgba(color) and rgba(*color) in self._colors  # type: ignore[misc]

    def __len__(self) -> int:
        """Return the number of favourite colours."""
        return len(self._colors)

    def __iter__(self) -> Iterator[RGBA]:
        """Iterate the favourite colours in order."""
        return iter(self._colors)

    def __eq__(self, other: object) -> bool:
        """Return True if `other` is a Favourites with the same colours, same order."""
        if not isinstance(other, Favourites):
            return NotImplemented
        return self._colors == other._colors

    def __repr__(self) -> str:
        """Return an eval-able repr showing the underlying colour list."""
        return f"Favourites({self._colors!r})"

    def to_serializable(self) -> List[str]:
        """Return the favourites as a list of ``#RRGGBBAA`` hex strings (JSON-safe)."""
        return [to_hex(c) for c in self._colors]

    @classmethod
    def from_serializable(cls, data: object) -> "Favourites":
        """Rebuild a Favourites list from :meth:`to_serializable` output.

        Raises:
            FavouritesError: If ``data`` is not a list of valid hex colour strings
                (SC-L015-4).
        """
        if not isinstance(data, list):
            raise FavouritesError(f"expected a list of hex colours, got {data!r}")
        colors: List[RGBA] = []
        for entry in data:
            if not isinstance(entry, str):
                raise FavouritesError(f"favourite must be a hex string, got {entry!r}")
            try:
                colors.append(from_hex(entry))
            except ValueError as exc:
                raise FavouritesError(f"invalid favourite colour {entry!r}") from exc
        return cls(colors)
