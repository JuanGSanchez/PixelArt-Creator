"""Isometric & perspective grid geometry — pure, invertible, zero Qt (S11).

The "tested geometry logic" the ROADMAP names (Phase-9 §2): every transform / snap
here is a **pure, deterministic** closed-form function of its inputs — no Qt, no
wall-clock, no randomness, no locale — so the SAME function the ``ui/`` overlays
call is the one unit- and property-tested without any GUI (ADR-0023; Article I).

Isometric (ADR-0023 §1, research §1): a **2:1 dimetric** (``DEFAULT_ISO_GRID_RATIO``)
**diamond** layout with an invertible world<->screen transform and snap-to-nearest
lattice vertex (round-half-up tie-break). Perspective (ADR-0023 §2, research §2):
1-/2-/3-point vanishing-point config, a deterministic guide-line fan for display,
and a **direction-lock-to-VP** snap (nearest vanishing line within tolerance, else
none; lowest-index tie-break).

Constants (bounds/defaults) come from :mod:`pixelart_creator.logic.constants`
(S12); no numeric is inlined. ``GridError`` (a ``ValueError``, the Phase-1
convention) reports every out-of-bounds / degenerate input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

from pixelart_creator.logic.constants import (
    DEFAULT_ISO_GRID_RATIO,
    MAX_GRID_SPACING,
    MAX_PERSPECTIVE_VANISHING_POINTS,
    MIN_GRID_SPACING,
)

__all__ = [
    "GridError",
    "IsoGridConfig",
    "iso_world_to_screen",
    "iso_screen_to_world",
    "iso_snap_vertex",
    "iso_snap_cell",
    "VanishingPoint",
    "PerspectiveConfig",
    "GuideLine",
    "perspective_guide_lines",
    "perspective_snap",
]


class GridError(ValueError):
    """Raised on an invalid grid configuration or a degenerate geometry input."""


# --------------------------------------------------------------------------- #
# Isometric grid (2:1 dimetric default, diamond layout)                       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IsoGridConfig:
    """An isometric-grid configuration (immutable, validated at construction).

    Attributes:
        origin: ``(ox, oy)`` — the screen anchor of cell ``(0, 0)`` (doc/scene
            space). The transform is origin-parametric; the ``-w`` top-corner blit
            offset is a *render* concern kept out of the geometry (ADR-0023 §1).
        tile_width: Full tile width ``W`` in px. Clamped to
            ``[MIN_GRID_SPACING, MAX_GRID_SPACING]``; out of that range ->
            :class:`GridError`.
        ratio: Tile aspect ``W:H``. ``2.0`` (default) is 2:1 dimetric; true-iso
            (~1.732) is configurable. Must be finite and ``> 0``.
    """

    origin: Tuple[float, float] = (0.0, 0.0)
    tile_width: int = MIN_GRID_SPACING
    ratio: float = DEFAULT_ISO_GRID_RATIO

    def __post_init__(self) -> None:
        """Validate the origin, tile width and ratio (ADR-0023 §1; LOGIC-008/011)."""
        ox, oy = _require_point(self.origin, "origin")
        object.__setattr__(self, "origin", (ox, oy))
        if isinstance(self.tile_width, bool) or not isinstance(self.tile_width, int):
            raise GridError(f"tile_width must be an int, got {self.tile_width!r}")
        if not MIN_GRID_SPACING <= self.tile_width <= MAX_GRID_SPACING:
            raise GridError(
                f"tile_width {self.tile_width} outside "
                f"[{MIN_GRID_SPACING}, {MAX_GRID_SPACING}]"
            )
        if isinstance(self.ratio, bool) or not isinstance(self.ratio, (int, float)):
            raise GridError(f"ratio must be a number, got {self.ratio!r}")
        if not math.isfinite(self.ratio) or self.ratio <= 0.0:
            raise GridError(f"ratio must be finite and > 0, got {self.ratio}")

    @property
    def half_width(self) -> float:
        """Half tile width ``w = W / 2`` (px)."""
        return self.tile_width / 2.0

    @property
    def half_height(self) -> float:
        """Half tile height ``h = w / ratio`` (px); 2:1 => ``h = W / 4``."""
        return self.half_width / float(self.ratio)


def iso_world_to_screen(
    i: float, j: float, config: IsoGridConfig
) -> Tuple[float, float]:
    """World cell ``(i, j)`` -> screen ``(sx, sy)`` in the diamond layout.

    ``sx = (i - j)*w + ox``, ``sy = (i + j)*h + oy`` (``w`` = half-width,
    ``h`` = half-height). Pure and exact; round-trips with
    :func:`iso_screen_to_world` on lattice points (REQ-P9-LOGIC-001; SC-L001-1).
    """
    _require_number(i, "i")
    _require_number(j, "j")
    w = config.half_width
    h = config.half_height
    ox, oy = config.origin
    sx = (i - j) * w + ox
    sy = (i + j) * h + oy
    return (sx, sy)


def iso_screen_to_world(
    sx: float, sy: float, config: IsoGridConfig
) -> Tuple[float, float]:
    """Screen ``(sx, sy)`` -> continuous world ``(i, j)`` (inverse transform).

    ``i = sx'/(2w) + sy'/(2h)``, ``j = sy'/(2h) - sx'/(2w)`` with
    ``sx' = sx - ox``, ``sy' = sy - oy``. Exact inverse of
    :func:`iso_world_to_screen` (REQ-P9-LOGIC-001; SC-L001-1).
    """
    _require_number(sx, "sx")
    _require_number(sy, "sy")
    w = config.half_width
    h = config.half_height
    ox, oy = config.origin
    sxp = sx - ox
    syp = sy - oy
    i = sxp / (2.0 * w) + syp / (2.0 * h)
    j = syp / (2.0 * h) - sxp / (2.0 * w)
    return (i, j)


def _round_half_up(value: float) -> int:
    """Round to the nearest int with a deterministic round-half-up tie-break.

    ``floor(value + 0.5)`` (ADR-0023 §1): a coordinate exactly between two
    lattice points always resolves upward, so snap is reproducible
    (REQ-P9-LOGIC-009).
    """
    return math.floor(value + 0.5)


def iso_snap_vertex(sx: float, sy: float, config: IsoGridConfig) -> Tuple[float, float]:
    """Snap a screen point to the nearest lattice **vertex** (grid corner).

    Converts to continuous ``(i, j)``, rounds each axis half-up (deterministic
    tie-break), and reprojects. Idempotent on already-snapped points; the model
    for line/guide drawing (REQ-P9-LOGIC-002/-009; SC-L002-1).
    """
    i, j = iso_screen_to_world(sx, sy, config)
    return iso_world_to_screen(_round_half_up(i), _round_half_up(j), config)


def iso_snap_cell(sx: float, sy: float, config: IsoGridConfig) -> Tuple[int, int]:
    """Snap a screen point to the ``(i, j)`` **cell** it lies inside (``floor``).

    The tile-placement companion to :func:`iso_snap_vertex` (research §1.5); the
    phase's snap *contract* is nearest-vertex, this is offered for tile authoring.
    """
    i, j = iso_screen_to_world(sx, sy, config)
    return (math.floor(i), math.floor(j))


# --------------------------------------------------------------------------- #
# Perspective grid (1-/2-/3-point, direction-lock-to-VP snap)                 #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class VanishingPoint:
    """A vanishing point: a finite position, or a pseudo-VP at infinity.

    Attributes:
        position: The finite VP ``(vx, vy)``; ``None`` => a pseudo-VP at infinity
            (an axis-lock family) carrying a fixed unit ``direction`` instead.
        direction: Unit direction for a pseudo-VP (required iff ``position`` is
            ``None``; normalised at construction). Ignored for a finite VP.
    """

    position: Optional[Tuple[float, float]] = None
    direction: Optional[Tuple[float, float]] = None

    def __post_init__(self) -> None:
        """Validate the position/direction pair and normalise a pseudo-VP dir."""
        if self.position is None and self.direction is None:
            raise GridError("a vanishing point needs a position or a direction")
        if self.position is not None:
            px, py = _require_point(self.position, "position")
            object.__setattr__(self, "position", (px, py))
        if self.direction is not None:
            dx, dy = _require_point(self.direction, "direction")
            norm = math.hypot(dx, dy)
            if norm == 0.0:
                raise GridError("vanishing-point direction must be non-zero")
            object.__setattr__(self, "direction", (dx / norm, dy / norm))


@dataclass(frozen=True)
class PerspectiveConfig:
    """A perspective configuration (immutable, validated at construction).

    Attributes:
        mode: ``1``, ``2`` or ``3`` (point count); ``<= MAX_PERSPECTIVE_VANISHING_
            POINTS``.
        vanishing_points: The active vanishing points (finite or pseudo). Count
            must be ``>= 1`` and ``<= MAX_PERSPECTIVE_VANISHING_POINTS``.
        horizon_y: The horizon line's screen ``y`` (render aid).
    """

    mode: int
    vanishing_points: Tuple[VanishingPoint, ...] = field(default_factory=tuple)
    horizon_y: float = 0.0

    def __post_init__(self) -> None:
        """Validate the mode, VP count and horizon (ADR-0023 §2; LOGIC-003/011)."""
        if isinstance(self.mode, bool) or not isinstance(self.mode, int):
            raise GridError(f"mode must be an int, got {self.mode!r}")
        if not 1 <= self.mode <= MAX_PERSPECTIVE_VANISHING_POINTS:
            raise GridError(
                f"mode {self.mode} outside 1..{MAX_PERSPECTIVE_VANISHING_POINTS}"
            )
        vps = tuple(self.vanishing_points)
        object.__setattr__(self, "vanishing_points", vps)
        if not vps:
            raise GridError("a perspective config needs at least one vanishing point")
        if len(vps) > MAX_PERSPECTIVE_VANISHING_POINTS:
            raise GridError(
                f"{len(vps)} vanishing points exceeds "
                f"MAX_PERSPECTIVE_VANISHING_POINTS ({MAX_PERSPECTIVE_VANISHING_POINTS})"
            )
        for vp in vps:
            if not isinstance(vp, VanishingPoint):
                raise GridError(f"expected a VanishingPoint, got {vp!r}")
        _require_number(self.horizon_y, "horizon_y")


@dataclass(frozen=True)
class GuideLine:
    """A perspective guide segment (render aid), from ``p0`` to ``p1``."""

    p0: Tuple[float, float]
    p1: Tuple[float, float]


def perspective_guide_lines(
    config: PerspectiveConfig,
    samples: int,
    *,
    edge_start: Tuple[float, float],
    edge_end: Tuple[float, float],
) -> Tuple[GuideLine, ...]:
    """Deterministic fan of guide segments from a reference edge toward each VP.

    Evenly samples ``samples`` points on the segment ``edge_start -> edge_end``
    (inclusive) and, per vanishing point, emits one segment from each sample point
    toward the VP: for a finite VP the segment ends at the VP; for a pseudo-VP the
    segment extends one tile of unit direction from the sample point. A pure,
    deterministic function of the config + edge (render aid only, **not** the snap
    primitive) (REQ-P9-LOGIC-003; SC-L003-1).

    Raises:
        GridError: If ``samples < 1`` or the edge points are malformed.
    """
    if isinstance(samples, bool) or not isinstance(samples, int):
        raise GridError(f"samples must be an int, got {samples!r}")
    if samples < 1:
        raise GridError(f"samples must be >= 1, got {samples}")
    ax, ay = _require_point(edge_start, "edge_start")
    bx, by = _require_point(edge_end, "edge_end")
    lines: list[GuideLine] = []
    denom = float(samples - 1) if samples > 1 else 1.0
    for vp in config.vanishing_points:
        for k in range(samples):
            t = (k / denom) if samples > 1 else 0.0
            px = ax + (bx - ax) * t
            py = ay + (by - ay) * t
            if vp.position is not None:
                end = vp.position
            else:
                dx, dy = vp.direction  # type: ignore[misc]
                # Extend one sample-edge length along the fixed unit direction.
                span = math.hypot(bx - ax, by - ay) or 1.0
                end = (px + dx * span, py + dy * span)
            lines.append(GuideLine((px, py), end))
    return tuple(lines)


def perspective_snap(
    sx: float,
    sy: float,
    anchor: Tuple[float, float],
    config: PerspectiveConfig,
    tolerance: float,
) -> Optional[Tuple[float, float]]:
    """Direction-lock a cursor to the nearest vanishing line within tolerance.

    For each VP: ``d = normalize(V - anchor)`` (finite) or the pseudo-VP's fixed
    unit ``d``; ``t = dot(C - anchor, d)``; ``proj = anchor + t*d``;
    ``err = ||(C - anchor) - t*d||``. Returns the ``proj`` of the VP with the
    smallest ``err`` **iff** that ``err <= tolerance`` (document px), else ``None``
    (no snap beyond tolerance). Tie-break: on equal ``err`` the **lowest VP index**
    wins. A degenerate VP (``anchor == V``) is skipped. Pure and deterministic
    (REQ-P9-LOGIC-004/-009; SC-L004-1; ADR-0023 §2).

    Raises:
        GridError: If ``anchor`` is malformed or ``tolerance`` is negative /
            non-finite.
    """
    cx = _require_number(sx, "sx")
    cy = _require_number(sy, "sy")
    ax, ay = _require_point(anchor, "anchor")
    _require_number(tolerance, "tolerance")
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise GridError(f"tolerance must be finite and >= 0, got {tolerance}")

    rel_x = cx - ax
    rel_y = cy - ay
    best_err: Optional[float] = None
    best_proj: Optional[Tuple[float, float]] = None
    for vp in config.vanishing_points:
        if vp.position is not None:
            vx, vy = vp.position
            dx = vx - ax
            dy = vy - ay
            norm = math.hypot(dx, dy)
            if norm == 0.0:  # degenerate: anchor on the VP
                continue
            dx /= norm
            dy /= norm
        else:
            dx, dy = vp.direction  # type: ignore[misc]
        t = rel_x * dx + rel_y * dy
        proj = (ax + t * dx, ay + t * dy)
        perp_x = rel_x - t * dx
        perp_y = rel_y - t * dy
        err = math.hypot(perp_x, perp_y)
        # Strict `<` keeps the lowest-index VP on an exact tie (deterministic).
        if best_err is None or err < best_err:
            best_err = err
            best_proj = proj
    if best_err is None or best_err > tolerance:
        return None
    return best_proj


# --------------------------------------------------------------------------- #
# Shared validation helpers                                                   #
# --------------------------------------------------------------------------- #


def _require_number(value: object, name: str) -> float:
    """Return ``value`` as a finite float, else raise :class:`GridError`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GridError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise GridError(f"{name} must be finite, got {value}")
    return float(value)


def _require_point(value: object, name: str) -> Tuple[float, float]:
    """Return ``value`` as a finite ``(x, y)`` float pair, else raise."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise GridError(f"{name} must be an (x, y) pair, got {value!r}")
    x = _require_number(value[0], f"{name}[0]")
    y = _require_number(value[1], f"{name}[1]")
    return (x, y)
