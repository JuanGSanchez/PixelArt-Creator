# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Role-indexed pixel-art templates: parse, 9-slice compose, colour (zero Qt, S11).

The pure half of the runtime-generated pixel chrome (ADR-0069 decision 1). A
template cell holds a *role index* -- one symbol character -- never a colour; a
per-template legend maps each symbol to a role key (``_`` is transparent). This
module

* parses a grid of symbols (:func:`parse_grid`),
* composes a 9-slice template to a target size with Qt ``border-image``
  ``repeat`` semantics (:func:`compose`): corners unchanged, edges and centre
  tiled,
* resolves roles to RGBA at an integer scale with binary alpha and nearest
  replication only (:func:`render`), and
* derives which roles a keyboard-focus ring touches (:func:`focus_touch_roles`),
  so the gated focus-contrast pairs are *measured from the art* instead of
  declared (ADR-0070 decision 5).

Writing the PNG files and the stylesheet are ``ui/`` concerns; nothing here
touches Qt, the file system or the clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from pixelart_creator.logic.contrast import ContrastError, parse_color
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelBufferError

__all__ = [
    "ThemeArtError",
    "TRANSPARENT_SYMBOL",
    "FOCUS_ROLE",
    "KIND_NINE_SLICE",
    "KIND_SPRITE",
    "KIND_OVERLAY",
    "KIND_ORNAMENT",
    "KIND_PATTERN",
    "TEMPLATE_KINDS",
    "DEFAULT_FOCUS_GROUNDS",
    "Slices",
    "RoleGrid",
    "Template",
    "TemplateSet",
    "parse_grid",
    "compose",
    "render",
    "focus_touch_roles",
]

#: The symbol every legend reserves for a transparent cell.
TRANSPARENT_SYMBOL: str = "_"
#: The role key the keyboard-focus ring is drawn in.
FOCUS_ROLE: str = "focus"

KIND_NINE_SLICE = "nine-slice"
KIND_SPRITE = "sprite"
KIND_OVERLAY = "overlay"
KIND_ORNAMENT = "ornament"
KIND_PATTERN = "pattern"
#: Every template kind the loader accepts.
TEMPLATE_KINDS: Tuple[str, ...] = (
    KIND_NINE_SLICE,
    KIND_SPRITE,
    KIND_OVERLAY,
    KIND_ORNAMENT,
    KIND_PATTERN,
)

#: Role keys of the two grounds a focused control can stand on (a window
#: background and a list/field fill).
DEFAULT_FOCUS_GROUNDS: Tuple[str, ...] = ("background", "surface")

# Structural, not tuning (ADR-0001): the probe scene is the control at a
# multiple of its native size on a ground that shows one art pixel all round.
_PROBE_SPAN_FACTOR = 2
_GROUND_MARGIN = 1
_MIN_SCALE = 1
_OPAQUE_ALPHA = 255
_TRANSPARENT_RGBA = (0, 0, 0, 0)
_NEIGHBOURS = ((1, 0), (0, 1))


class ThemeArtError(ValueError):
    """Raised on a malformed grid, template, size, scale or role map."""


@dataclass(frozen=True)
class Slices:
    """9-slice insets in art pixels (Qt ``border-image`` slice widths)."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        """Reject negative or non-integer insets."""
        for name in ("left", "top", "right", "bottom"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ThemeArtError(f"slice {name} must be an int >= 0, got {value!r}")

    @classmethod
    def from_css(cls, values: Sequence[int]) -> "Slices":
        """Build from four values in CSS order ``top, right, bottom, left``."""
        if len(values) != len(("top", "right", "bottom", "left")):
            raise ThemeArtError(f"slices need 4 values (t, r, b, l), got {values!r}")
        top, right, bottom, left = values
        return cls(left=left, top=top, right=right, bottom=bottom)

    @property
    def is_zero(self) -> bool:
        """``True`` when the template is not sliced at all (a sprite or tile)."""
        return not (self.left or self.top or self.right or self.bottom)


@dataclass(frozen=True)
class RoleGrid:
    """A rectangle of role-index symbols plus the legend that names the roles.

    Attributes:
        rows: Equal-length strings, one symbol per cell.
        legend: ``(symbol, role key or None)`` pairs; ``None`` is transparent.
    """

    rows: Tuple[str, ...]
    legend: Tuple[Tuple[str, Optional[str]], ...] = field(default=())

    @property
    def width(self) -> int:
        """Cells per row."""
        return len(self.rows[0])

    @property
    def height(self) -> int:
        """Number of rows."""
        return len(self.rows)

    def role_of(self, symbol: str) -> Optional[str]:
        """Return the role key of ``symbol`` (``None`` = transparent).

        Raises:
            ThemeArtError: If the symbol is not in the legend.
        """
        if symbol == TRANSPARENT_SYMBOL:
            return None
        for sym, role in self.legend:
            if sym == symbol:
                return role
        raise ThemeArtError(f"symbol {symbol!r} is not in the legend")

    def roles(self) -> Tuple[str, ...]:
        """Return the sorted role keys the legend names (transparent excluded)."""
        return tuple(sorted({r for _, r in self.legend if r is not None}))


@dataclass(frozen=True)
class Template:
    """One named template: a grid, its 9-slice insets and its kind.

    Attributes:
        name: Template name (``panel``, ``focus_ring`` ...).
        grid: The role grid.
        slices: 9-slice insets (all zero for sprites and tiles).
        kind: One of :data:`TEMPLATE_KINDS`.
        qss_hint: Free text naming the widgets that use it (documentation).
    """

    name: str
    grid: RoleGrid
    slices: Slices
    kind: str = KIND_NINE_SLICE
    qss_hint: str = ""

    def __post_init__(self) -> None:
        """Validate the kind and that the insets fit inside the grid."""
        if self.kind not in TEMPLATE_KINDS:
            raise ThemeArtError(f"{self.name}: unknown template kind {self.kind!r}")
        s, g = self.slices, self.grid
        if s.left + s.right > g.width or s.top + s.bottom > g.height:
            raise ThemeArtError(
                f"{self.name}: slices {s} exceed the {g.width}x{g.height} grid"
            )


@dataclass(frozen=True)
class TemplateSet:
    """Every template of one style plus the focus-ring assignment.

    Attributes:
        style: The style id.
        templates: Template name to :class:`Template`.
        focus_rings: Framed-control template name to the ring template that
            is overlaid on it when focused.
        pattern: The seamless pattern tile.
    """

    style: str
    templates: Mapping[str, Template]
    focus_rings: Mapping[str, str]
    pattern: Template

    def get(self, name: str) -> Template:
        """Return the template ``name``.

        Raises:
            ThemeArtError: If the set has no such template.
        """
        try:
            return self.templates[name]
        except KeyError:
            raise ThemeArtError(f"{self.style}: no template {name!r}") from None


def parse_grid(
    text: str, legend: Optional[Mapping[str, Optional[str]]] = None
) -> RoleGrid:
    """Parse a grid of one-character symbols, one row per line.

    Trailing blank lines are ignored; whitespace inside a row is an error (it
    would be a symbol nobody can see).

    Args:
        text: The grid text.
        legend: Optional symbol to role-key map (``None`` value = transparent).
            When given, every symbol in the grid must be in it (or be ``_``).

    Raises:
        ThemeArtError: If the grid is empty, ragged, contains whitespace, or
            uses a symbol the legend lacks.
    """
    rows = [line.rstrip("\r") for line in text.split("\n")]
    while rows and not rows[-1].strip():
        rows.pop()
    if not rows:
        raise ThemeArtError("grid is empty")
    width = len(rows[0])
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ThemeArtError(f"ragged row {y}: {len(row)} cells, expected {width}")
        if not row or any(ch.isspace() for ch in row):
            raise ThemeArtError(f"row {y} is empty or contains whitespace")
    pairs: Tuple[Tuple[str, Optional[str]], ...] = ()
    if legend is not None:
        used = {ch for row in rows for ch in row} - {TRANSPARENT_SYMBOL}
        missing = sorted(used - set(legend))
        if missing:
            raise ThemeArtError(f"symbols {missing} are not in the legend")
        pairs = tuple(sorted(legend.items()))
    return RoleGrid(rows=tuple(rows), legend=pairs)


def compose(template: Template, w: int, h: int) -> RoleGrid:
    """Compose a 9-slice template to ``w`` x ``h`` cells.

    Corners are copied unchanged; the edges and the centre are tiled (Qt
    ``border-image`` ``repeat repeat``). A template with no middle in an axis
    can only be composed at its native size on that axis.

    Raises:
        ThemeArtError: If the target is smaller than the two insets together,
            or the axis has no middle to repeat.
    """
    g, s = template.grid, template.slices
    for axis, target, native, before, after in (
        ("width", w, g.width, s.left, s.right),
        ("height", h, g.height, s.top, s.bottom),
    ):
        if not isinstance(target, int) or isinstance(target, bool):
            raise ThemeArtError(f"{template.name}: {axis} must be an int")
        if target < before + after:
            raise ThemeArtError(
                f"{template.name}: {axis} {target} < slices {before}+{after}"
            )
        if native - before - after == 0 and target != native:
            raise ThemeArtError(
                f"{template.name}: no middle to repeat on {axis}; "
                f"only the native {native} is possible"
            )
    mw = g.width - s.left - s.right
    mh = g.height - s.top - s.bottom
    out: List[str] = []
    for y in range(h):
        if y < s.top:
            sy = y
        elif y >= h - s.bottom:
            sy = g.height - (h - y)
        else:
            sy = s.top + (y - s.top) % mh
        row = g.rows[sy]
        chars: List[str] = []
        for x in range(w):
            if x < s.left:
                sx = x
            elif x >= w - s.right:
                sx = g.width - (w - x)
            else:
                sx = s.left + (x - s.left) % mw
            chars.append(row[sx])
        out.append("".join(chars))
    return RoleGrid(rows=tuple(out), legend=g.legend)


def _role_rgba(role: str, role_map: Mapping[str, str]) -> Tuple[int, int, int, int]:
    try:
        value = role_map[role]
    except KeyError:
        raise ThemeArtError(f"role {role!r} is not in the role map") from None
    try:
        r, g, b, a = parse_color(value)
    except ContrastError as exc:
        raise ThemeArtError(f"role {role!r}: {exc}") from exc
    if a != _OPAQUE_ALPHA:
        raise ThemeArtError(
            f"role {role!r} is translucent ({value!r}); art alpha is binary"
        )
    return (r, g, b, a)


def render(grid: RoleGrid, role_map: Mapping[str, str], scale: int) -> PixelBuffer:
    """Colour ``grid`` from ``role_map`` at an integer ``scale``.

    Each cell becomes a ``scale`` x ``scale`` block (nearest replication, no
    smoothing). Alpha is binary: ``_`` cells are fully transparent, every
    other cell is fully opaque.

    Raises:
        ThemeArtError: On a bad scale, a role missing from ``role_map``, a
            translucent role colour, a symbol missing from the grid's legend,
            or a result too large for a pixel buffer.
    """
    if not isinstance(scale, int) or isinstance(scale, bool) or scale < _MIN_SCALE:
        raise ThemeArtError(f"scale must be an int >= {_MIN_SCALE}, got {scale!r}")
    colours: Dict[str, Tuple[int, int, int, int]] = {}
    for symbol in {ch for row in grid.rows for ch in row}:
        role = grid.role_of(symbol)
        colours[symbol] = (
            _TRANSPARENT_RGBA if role is None else _role_rgba(role, role_map)
        )
    cells = np.zeros((grid.height, grid.width, len(_TRANSPARENT_RGBA)), np.uint8)
    for y, row in enumerate(grid.rows):
        for x, symbol in enumerate(row):
            cells[y, x] = colours[symbol]
    try:
        buf = PixelBuffer(grid.width * scale, grid.height * scale)
    except PixelBufferError as exc:
        raise ThemeArtError(f"rendered size is not allowed: {exc}") from exc
    buf.data[:, :] = np.repeat(np.repeat(cells, scale, axis=0), scale, axis=1)
    return buf


def _probe_size(template: Template) -> Tuple[int, int]:
    g = template.grid
    if template.slices.is_zero:
        return (g.width, g.height)
    return (g.width * _PROBE_SPAN_FACTOR, g.height * _PROBE_SPAN_FACTOR)


def focus_touch_roles(
    template_set: TemplateSet,
    grounds: Sequence[str] = DEFAULT_FOCUS_GROUNDS,
) -> Dict[str, int]:
    """Derive which roles the focus ring touches.

    For every framed control in ``template_set.focus_rings``, on every ground,
    the control and its ring overlay are composed at the same rectangle (the
    overlay is a child painted over the control's frame), the ground showing
    one art pixel all round. Each 4-neighbour pair made of a
    :data:`FOCUS_ROLE` cell and a cell of another role is counted under the
    other role.

    Returns:
        ``{role key: number of touching pairs}``, sorted by role; every key
        becomes a gated ``focus`` contrast pair (3:1).

    Raises:
        ThemeArtError: If a named control or ring template is missing, or the
            set assigns no ring at all (an empty derivation must not pass).
    """
    if not template_set.focus_rings:
        raise ThemeArtError(f"{template_set.style}: no focus ring assignments")
    if not grounds:
        raise ThemeArtError("no grounds to probe")
    counts: Dict[str, int] = {}
    for control_name in sorted(template_set.focus_rings):
        control = template_set.get(control_name)
        ring = template_set.get(template_set.focus_rings[control_name])
        w, h = _probe_size(control)
        framed = compose(control, w, h)
        overlay = compose(ring, w, h)
        for ground in grounds:
            side_x, side_y = w + 2 * _GROUND_MARGIN, h + 2 * _GROUND_MARGIN
            canvas: List[List[Optional[str]]] = [
                [ground] * side_x for _ in range(side_y)
            ]
            for layer in (framed, overlay):
                for y, row in enumerate(layer.rows):
                    for x, symbol in enumerate(row):
                        role = layer.role_of(symbol)
                        if role is not None:
                            canvas[y + _GROUND_MARGIN][x + _GROUND_MARGIN] = role
            for y in range(side_y):
                for x in range(side_x):
                    for dx, dy in _NEIGHBOURS:
                        nx, ny = x + dx, y + dy
                        if nx >= side_x or ny >= side_y:
                            continue
                        a, b = canvas[y][x], canvas[ny][nx]
                        if (a == FOCUS_ROLE) == (b == FOCUS_ROLE):
                            continue
                        other = b if a == FOCUS_ROLE else a
                        if other is not None:
                            counts[other] = counts.get(other, 0) + 1
    return dict(sorted(counts.items()))
