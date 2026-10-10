# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""WCAG 2.x contrast maths for theme role colours (zero Qt, S11).

One implementation serves the theme, the tests and the contrast check script
(ADR-0070 decision 4). It is a pure function of its hex inputs: no clock, no
randomness, no I/O.

Colour syntax. A colour is ``#RRGGBB`` (opaque) or ``#AARRGGBB`` -- **alpha
first**, which is how Qt reads an eight-digit value (``QColor("#78787890")`` is
alpha ``0x78``, not ``0x90``). The convention is fixed here and nowhere else is
it re-decided; an alpha-bearing colour has no luminance of its own, so it is
first composited over an opaque colour (:func:`composite`) before it is measured.

Formula (WCAG 2.2, "relative luminance" and "contrast ratio"): sRGB channels are
linearised, weighted ``0.2126 / 0.7152 / 0.0722`` and the ratio is
``(L_lighter + 0.05) / (L_darker + 0.05)``. The ratio is returned unrounded; it
agrees with the private helper the accessibility tests used before this module
existed.

The floors (4.5 text, 3.0 components and focus) are fixed by WCAG, so under
ADR-0001 they are intrinsic and live here, next to the formula, not in
``logic/constants.py``.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

__all__ = [
    "ContrastError",
    "PairKind",
    "ContrastPair",
    "TEXT_MIN_RATIO",
    "COMPONENT_MIN_RATIO",
    "FOCUS_MIN_RATIO",
    "parse_color",
    "is_valid_color",
    "relative_luminance",
    "composite",
    "contrast_ratio",
    "floor_for",
    "meets_floor",
]

#: WCAG 2.x minimum contrast for text (AA, normal size) -- WCAG-intrinsic.
TEXT_MIN_RATIO: float = 4.5
#: WCAG 2.x minimum contrast for user-interface components -- WCAG-intrinsic.
COMPONENT_MIN_RATIO: float = 3.0
#: Minimum contrast of a keyboard-focus indicator -- WCAG-intrinsic (same 3:1).
FOCUS_MIN_RATIO: float = 3.0

# Format-intrinsic: hex digit counts, channel range, and the sRGB / WCAG
# coefficients (ADR-0001: not tuning values).
_OPAQUE_DIGITS = 6
_ALPHA_DIGITS = 8
_CHANNEL_MAX = 255
_HEX_RADIX = 16
_COLOR_PATTERN = re.compile(r"#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})")
_SRGB_KNEE = 0.04045
_SRGB_LINEAR_DIVISOR = 12.92
_SRGB_OFFSET = 0.055
_SRGB_SCALE = 1.055
_SRGB_GAMMA = 2.4
_LUMA_RED = 0.2126
_LUMA_GREEN = 0.7152
_LUMA_BLUE = 0.0722
_RATIO_OFFSET = 0.05
_ROUND_HALF = 0.5

#: ``(red, green, blue, alpha)``, each ``0..255``.
Rgba = Tuple[int, int, int, int]
#: ``(red, green, blue)``, each ``0..255``.
Rgb = Tuple[int, int, int]


class ContrastError(ValueError):
    """Raised on a malformed colour or an unmeasurable (translucent) operand."""


class PairKind(enum.Enum):
    """How a declared foreground/background pair is judged."""

    TEXT = "text"
    COMPONENT = "component"
    FOCUS = "focus"
    INFO = "info"


_FLOORS: Dict[PairKind, float] = {
    PairKind.TEXT: TEXT_MIN_RATIO,
    PairKind.COMPONENT: COMPONENT_MIN_RATIO,
    PairKind.FOCUS: FOCUS_MIN_RATIO,
}


@dataclass(frozen=True)
class ContrastPair:
    """One declared pair of role names to be measured.

    Attributes:
        fg: Foreground role key.
        bg: Background role key.
        kind: How the pair is judged (:class:`PairKind`).
        over: Optional role key a translucent ``bg`` is composited over.
        note: Free-text reason, reported with the measurement.
    """

    fg: str
    bg: str
    kind: PairKind
    over: Optional[str] = None
    note: str = ""


def is_valid_color(value: str) -> bool:
    """Return ``True`` if ``value`` is ``#RRGGBB`` or ``#AARRGGBB``."""
    return isinstance(value, str) and _COLOR_PATTERN.fullmatch(value) is not None


def parse_color(value: str) -> Rgba:
    """Parse ``#RRGGBB`` or ``#AARRGGBB`` (alpha first) into ``(r, g, b, a)``.

    Args:
        value: The colour text, case-insensitive.

    Returns:
        The channels, each ``0..255``; alpha is ``255`` for a six-digit colour.

    Raises:
        ContrastError: If ``value`` is not one of the two accepted forms.
    """
    if not is_valid_color(value):
        raise ContrastError(
            f"colour {value!r} is not #RRGGBB or #AARRGGBB (alpha first)"
        )
    digits = value[1:]
    channels = [int(digits[i : i + 2], _HEX_RADIX) for i in range(0, len(digits), 2)]
    if len(digits) == _OPAQUE_DIGITS:
        r, g, b = channels
        return (r, g, b, _CHANNEL_MAX)
    a, r, g, b = channels
    return (r, g, b, a)


def _linearise(channel: int) -> float:
    c = channel / _CHANNEL_MAX
    if c <= _SRGB_KNEE:
        return c / _SRGB_LINEAR_DIVISOR
    return float(((c + _SRGB_OFFSET) / _SRGB_SCALE) ** _SRGB_GAMMA)


def _luminance(rgb: Rgb) -> float:
    r, g, b = rgb
    return (
        _LUMA_RED * _linearise(r)
        + _LUMA_GREEN * _linearise(g)
        + (_LUMA_BLUE * _linearise(b))
    )


def _opaque(value: str, what: str) -> Rgb:
    r, g, b, a = parse_color(value)
    if a != _CHANNEL_MAX:
        raise ContrastError(
            f"{what} {value!r} is translucent; composite it over an opaque "
            f"colour before measuring"
        )
    return (r, g, b)


def relative_luminance(color: str) -> float:
    """Return the WCAG relative luminance (``0.0``..``1.0``) of an opaque colour.

    Raises:
        ContrastError: If ``color`` is malformed or carries alpha.
    """
    return _luminance(_opaque(color, "colour"))


def _composite_rgb(fg: Rgba, under: Rgb) -> Rgb:
    r, g, b, a = fg
    k = a / _CHANNEL_MAX
    return (
        int(k * r + (1.0 - k) * under[0] + _ROUND_HALF),
        int(k * g + (1.0 - k) * under[1] + _ROUND_HALF),
        int(k * b + (1.0 - k) * under[2] + _ROUND_HALF),
    )


def composite(fg: str, bg: str) -> str:
    """Composite ``fg`` (may carry alpha) over the opaque ``bg``.

    Returns:
        The resulting opaque colour as ``#rrggbb`` (lower case), rounded to
        8-bit precision half-up.

    Raises:
        ContrastError: If either colour is malformed or ``bg`` is translucent.
    """
    under = _opaque(bg, "background")
    r, g, b = _composite_rgb(parse_color(fg), under)
    return f"#{r:02x}{g:02x}{b:02x}"


def contrast_ratio(fg: str, bg: str, over: Optional[str] = None) -> float:
    """Return the WCAG contrast ratio of ``fg`` on ``bg`` (unrounded, ``>= 1``).

    A translucent ``fg`` is composited over the (resolved) ``bg``. A translucent
    ``bg`` is first composited over ``over``; without ``over`` it cannot be
    measured and is refused (never silently dropped).

    Args:
        fg: Foreground colour.
        bg: Background colour.
        over: Opaque colour a translucent ``bg`` sits on, if any.

    Raises:
        ContrastError: On a malformed colour, a translucent ``bg`` with no
            ``over``, or a translucent ``over``.
    """
    bg_r, bg_g, bg_b, bg_a = parse_color(bg)
    if bg_a != _CHANNEL_MAX:
        if over is None:
            raise ContrastError(
                f"background {bg!r} is translucent and no 'over' colour was given"
            )
        bg_rgb = _composite_rgb((bg_r, bg_g, bg_b, bg_a), _opaque(over, "over"))
    else:
        bg_rgb = (bg_r, bg_g, bg_b)
    fg_rgb = _composite_rgb(parse_color(fg), bg_rgb)
    la, lb = _luminance(fg_rgb), _luminance(bg_rgb)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + _RATIO_OFFSET) / (darker + _RATIO_OFFSET)


def floor_for(kind: PairKind) -> Optional[float]:
    """Return the WCAG floor gating ``kind``, or ``None`` for ``INFO``."""
    return _FLOORS.get(kind)


def meets_floor(kind: PairKind, ratio: float) -> bool:
    """Return ``True`` if ``ratio`` satisfies ``kind``'s floor.

    ``INFO`` pairs are reported only and therefore always return ``True``.
    """
    floor = floor_for(kind)
    return True if floor is None else ratio >= floor
