# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Guides & rulers geometry — pure snap + tick computation, zero Qt (S11).

Document-coordinate guides (the Photoshop/Aseprite model, ADR-0023 §3): a guide is
one scalar in doc space + an orientation. Snap tolerance is expressed in *screen*
px and converted to doc space via ``screen_tolerance_to_doc`` so perceived
"stickiness" is constant at every zoom. Ruler ticks use a **nice-number**
``{1, 2, 5}·10ⁿ`` ladder with **locale-independent** integer labels. Every function
is a pure, deterministic function of its inputs — no Qt, no wall-clock, no locale
formatting — the same math the ``ui/`` overlay calls and the test suite
unit-tests (Article I; REQ-P9-LOGIC-005/-006/-009).

Constants come from :mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from pixelart_creator.logic.constants import MAX_GUIDES

__all__ = [
    "GuideError",
    "GuideOrientation",
    "Guide",
    "screen_tolerance_to_doc",
    "snap_axis",
    "snap_guides",
    "RulerTick",
    "ruler_ticks",
    "coordinate_readout",
]

#: Nice-number step mantissas — the ``{1, 2, 5}`` ladder (research §3.1). The
#: values are algorithm-intrinsic to the tick computation (ADR-0001), module-local.
_NICE_MANTISSAS: Tuple[int, ...] = (1, 2, 5)

#: Minimum on-screen spacing (px) between two major ruler labels before the ladder
#: steps up. Intrinsic to the tick algorithm (ADR-0001), module-local.
_MIN_LABEL_SPACING_PX: float = 50.0


class GuideError(ValueError):
    """Raised on an invalid guide set or guide-geometry input."""


class GuideOrientation(enum.Enum):
    """Guide orientation — a module-local enumerated vocabulary (ADR-0001/BF-2).

    ``HORIZONTAL`` guides are a doc ``y``; ``VERTICAL`` guides are a doc ``x``.
    """

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class Guide:
    """A single document-coordinate guide.

    Attributes:
        orientation: :class:`GuideOrientation` — the axis the guide constrains.
        position: The doc coordinate (``x`` for ``VERTICAL``, ``y`` for
            ``HORIZONTAL``). Must be finite.
    """

    orientation: GuideOrientation
    position: float

    def __post_init__(self) -> None:
        """Validate the orientation and position."""
        if not isinstance(self.orientation, GuideOrientation):
            raise GuideError(
                f"orientation must be a GuideOrientation, got {self.orientation!r}"
            )
        if isinstance(self.position, bool) or not isinstance(
            self.position, (int, float)
        ):
            raise GuideError(f"position must be a number, got {self.position!r}")
        if not math.isfinite(self.position):
            raise GuideError(f"position must be finite, got {self.position}")
        object.__setattr__(self, "position", float(self.position))


def screen_tolerance_to_doc(tolerance_px: float, zoom: float) -> float:
    """Convert a screen-px snap tolerance to document space: ``tol_px / zoom``.

    Keeps perceived stickiness constant at every zoom level (ADR-0023 §3, research
    §3.3). Pure (REQ-P9-LOGIC-005).

    Raises:
        GuideError: If ``tolerance_px`` is negative / non-finite or ``zoom`` is
            not finite and ``> 0``.
    """
    _require_number(tolerance_px, "tolerance_px")
    _require_number(zoom, "zoom")
    if tolerance_px < 0.0:
        raise GuideError(f"tolerance_px must be >= 0, got {tolerance_px}")
    if zoom <= 0.0:
        raise GuideError(f"zoom must be > 0, got {zoom}")
    return tolerance_px / zoom


def snap_axis(value: float, positions: Sequence[float], tolerance_doc: float) -> float:
    """Snap ``value`` to the nearest ``positions`` entry within ``tolerance_doc``.

    Candidates are considered in **ascending position**; on equal distance the
    **lowest position** wins (deterministic tie-break, REQ-P9-LOGIC-009). Returns
    ``value`` unchanged if none is within tolerance. Pure.
    """
    best: Optional[float] = None
    best_d: Optional[float] = None
    for pos in sorted(positions):
        d = abs(value - pos)
        # Ascending order + strict `<` keeps the lowest position on an equal tie.
        if d <= tolerance_doc and (best_d is None or d < best_d):
            best = pos
            best_d = d
    return value if best is None else best


def snap_guides(
    x: float,
    y: float,
    guides: Sequence[Guide],
    tolerance_doc: float,
) -> Tuple[float, float]:
    """Snap ``(x, y)`` per-axis to the nearest guide within ``tolerance_doc``.

    ``VERTICAL`` guides snap ``x``; ``HORIZONTAL`` guides snap ``y`` — independently
    (research §3.2). Each axis is unchanged if no guide is within tolerance; the
    ascending-position / lowest-on-tie rule of :func:`snap_axis` applies. Pure and
    deterministic (REQ-P9-LOGIC-005/-009; SC-L005-1).

    Raises:
        GuideError: If ``> MAX_GUIDES`` guides are supplied, an entry is not a
            :class:`Guide`, the coordinates are malformed, or ``tolerance_doc`` is
            negative / non-finite.
    """
    _require_number(x, "x")
    _require_number(y, "y")
    _require_number(tolerance_doc, "tolerance_doc")
    if tolerance_doc < 0.0:
        raise GuideError(f"tolerance_doc must be >= 0, got {tolerance_doc}")
    if len(guides) > MAX_GUIDES:
        raise GuideError(f"{len(guides)} guides exceeds MAX_GUIDES ({MAX_GUIDES})")
    verticals: list[float] = []
    horizontals: list[float] = []
    for guide in guides:
        if not isinstance(guide, Guide):
            raise GuideError(f"expected a Guide, got {guide!r}")
        if guide.orientation is GuideOrientation.VERTICAL:
            verticals.append(guide.position)
        else:
            horizontals.append(guide.position)
    return (
        snap_axis(x, verticals, tolerance_doc),
        snap_axis(y, horizontals, tolerance_doc),
    )


@dataclass(frozen=True)
class RulerTick:
    """One ruler tick.

    Attributes:
        position: The doc coordinate of the tick.
        label: A locale-independent integer string (major ticks only; ``""`` on a
            minor tick).
        major: Whether this is a labelled major tick.
    """

    position: float
    label: str
    major: bool


def _nice_step(min_doc_step: float) -> float:
    """Smallest ``{1, 2, 5}·10ⁿ`` step that is ``>= min_doc_step``.

    A pure, deterministic ladder (research §3.1); ``min_doc_step <= 0`` -> ``1``.
    """
    if min_doc_step <= 0.0:
        return 1.0
    exponent = math.floor(math.log10(min_doc_step))
    for _ in range(3):  # advance at most one decade past the mantissa list
        base = 10.0**exponent
        for mantissa in _NICE_MANTISSAS:
            step = mantissa * base
            if step >= min_doc_step:
                return step
        exponent += 1
    return 10.0**exponent


def ruler_ticks(
    doc_length: float,
    zoom: float,
    offset: float,
    *,
    axis_pixels: int,
) -> Tuple[RulerTick, ...]:
    """Nice-number ruler ticks over one axis — pure of the view parameters.

    Chooses the smallest ``{1, 2, 5}·10ⁿ`` doc step whose on-screen size
    (``step * zoom``) is ``>= _MIN_LABEL_SPACING_PX``, then emits a major, labelled
    tick at every multiple of that step across the visible ``axis_pixels`` window
    (``offset`` = the doc coordinate at screen 0). Labels are **locale-independent**
    integer strings (no thousands separators). Deterministic (REQ-P9-LOGIC-006/-009;
    SC-L006-1).

    Raises:
        GuideError: If ``zoom`` is not ``> 0`` / finite, ``axis_pixels`` is not a
            positive int, or ``doc_length`` / ``offset`` is non-finite.
    """
    _require_number(doc_length, "doc_length")
    _require_number(zoom, "zoom")
    _require_number(offset, "offset")
    if zoom <= 0.0:
        raise GuideError(f"zoom must be > 0, got {zoom}")
    if isinstance(axis_pixels, bool) or not isinstance(axis_pixels, int):
        raise GuideError(f"axis_pixels must be an int, got {axis_pixels!r}")
    if axis_pixels < 1:
        raise GuideError(f"axis_pixels must be >= 1, got {axis_pixels}")

    min_doc_step = _MIN_LABEL_SPACING_PX / zoom
    step = _nice_step(min_doc_step)
    # Visible doc window: [offset, offset + axis_pixels / zoom].
    doc_span = axis_pixels / zoom
    start_doc = offset
    end_doc = offset + doc_span
    first_index = math.ceil(start_doc / step)
    last_index = math.floor(end_doc / step)
    ticks: list[RulerTick] = []
    for k in range(first_index, last_index + 1):
        pos = k * step
        # Integer label when the step lands on whole doc units; else trimmed float.
        label = _format_tick_label(pos)
        ticks.append(RulerTick(position=float(pos), label=label, major=True))
    return tuple(ticks)


def _format_tick_label(position: float) -> str:
    """Locale-independent tick label: an integer string when whole, else trimmed.

    No locale formatting / thousands separators (REQ-P9-LOGIC-009).
    """
    rounded = round(position)
    if math.isclose(position, rounded, abs_tol=1e-9):
        return str(int(rounded))
    # Trim trailing zeros from a fixed-point representation (locale-independent).
    text = f"{position:.6f}".rstrip("0").rstrip(".")
    return text


def coordinate_readout(
    sx: float,
    sy: float,
    zoom: float,
    offset: Tuple[float, float],
) -> Tuple[int, int]:
    """Screen ``(sx, sy)`` -> integer document ``(x, y)`` readout.

    ``doc = offset + screen / zoom``, floored to an integer doc coordinate.
    Deterministic (REQ-P9-LOGIC-006).

    Raises:
        GuideError: If ``zoom`` is not ``> 0`` / finite, or a coordinate / offset
            is malformed.
    """
    _require_number(sx, "sx")
    _require_number(sy, "sy")
    _require_number(zoom, "zoom")
    if zoom <= 0.0:
        raise GuideError(f"zoom must be > 0, got {zoom}")
    ox, oy = _require_point(offset, "offset")
    return (math.floor(ox + sx / zoom), math.floor(oy + sy / zoom))


# --------------------------------------------------------------------------- #
# Shared validation helpers                                                   #
# --------------------------------------------------------------------------- #


def _require_number(value: object, name: str) -> float:
    """Return ``value`` as a finite float, else raise :class:`GuideError`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GuideError(f"{name} must be a number, got {value!r}")
    if not math.isfinite(value):
        raise GuideError(f"{name} must be finite, got {value}")
    return float(value)


def _require_point(value: object, name: str) -> Tuple[float, float]:
    """Return ``value`` as a finite ``(x, y)`` float pair, else raise."""
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise GuideError(f"{name} must be an (x, y) pair, got {value!r}")
    x = _require_number(value[0], f"{name}[0]")
    y = _require_number(value[1], f"{name}[1]")
    return (x, y)
