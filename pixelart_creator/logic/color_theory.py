"""Colour-theory maths: HSV/HSL conversion, harmonies, and ramps (zero Qt, S11).

Pure tuple maths over the Phase-1 :data:`~pixelart_creator.logic.color.RGBA`
type — the geometric substrate the colour-hub wheel and every hue-rotation
harmony need. Conversions and harmonies are **not** built on ``QColor`` (CL-2);
Qt lives in ``ui/`` only. All maths are deterministic and side-effect-free.

Grounding: harmony hue rotations and the tint/shade/tone HSV formulas are taken
from ``docs/research-phase3-colour.md`` Topic 1 (F9). The harmony *angles* are
tuning scalars in :mod:`~pixelart_creator.logic.constants` (Article II); the
tint/shade/tone formulas are intrinsic to the HSV geometry and stay local here
(ADR-0001). REQ-P3-LOGIC-001, -002, -003.
"""

from __future__ import annotations

import colorsys
from typing import List, Tuple

from pixelart_creator.logic.color import CHANNEL_MAX, RGBA, is_rgba, rgba
from pixelart_creator.logic.constants import (
    HARMONY_ANALOGOUS_DEG,
    HARMONY_COMPLEMENTARY_DEG,
    HARMONY_SPLIT_COMPLEMENTARY_DEG,
    HARMONY_TRIADIC_DEG,
    RAMP_STEP_COUNT,
)

__all__ = [
    "ColorTheoryError",
    "rgba_to_hsv",
    "hsv_to_rgba",
    "rgba_to_hsl",
    "hsl_to_rgba",
    "complementary",
    "analogous",
    "triadic",
    "split_complementary",
    "harmony",
    "shade_ramp",
    "tint_ramp",
    "tone_ramp",
]

#: A hue-saturation-value tuple plus alpha: ``(h∈[0,360), s∈[0,1], v∈[0,1], a)``.
HSVA = Tuple[float, float, float, int]
#: A hue-saturation-lightness tuple plus alpha: ``(h∈[0,360), s∈[0,1], l∈[0,1], a)``.
HSLA = Tuple[float, float, float, int]

#: Valid harmony scheme names accepted by :func:`harmony`.
_SCHEMES = ("complementary", "analogous", "triadic", "split")


class ColorTheoryError(ValueError):
    """Raised when a colour or scheme argument is malformed."""


def _check_unit(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ColorTheoryError(f"{name} must be a number, got {value!r}")
    if value < 0.0 or value > 1.0:
        raise ColorTheoryError(f"{name} {value} out of range 0.0..1.0")
    return float(value)


def _check_hue(value: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ColorTheoryError(f"hue must be a number, got {value!r}")
    return float(value) % 360.0


def _channel_from_unit(value: float) -> int:
    return max(0, min(CHANNEL_MAX, int(round(value * CHANNEL_MAX))))


# -- conversions ---------------------------------------------------------------


def rgba_to_hsv(color: RGBA) -> HSVA:
    """Convert an RGBA tuple to ``(hue°, saturation, value, alpha)``.

    Hue is in ``[0, 360)`` degrees; saturation and value in ``[0, 1]``; alpha is
    the unchanged ``0..255`` integer. Primaries map to red=0°, green=120°,
    blue=240° (SC-L001-2). Alpha is preserved (SC-L001-3).

    Raises:
        ColorTheoryError: If ``color`` is not a well-formed RGBA tuple.
    """
    if not is_rgba(color):
        raise ColorTheoryError(f"not an RGBA colour: {color!r}")
    r, g, b, a = color
    h, s, v = colorsys.rgb_to_hsv(r / CHANNEL_MAX, g / CHANNEL_MAX, b / CHANNEL_MAX)
    return (h * 360.0, s, v, a)


def hsv_to_rgba(h: float, s: float, v: float, a: int = CHANNEL_MAX) -> RGBA:
    """Convert ``(hue°, saturation, value, alpha)`` back to an RGBA tuple.

    Hue wraps modulo 360°; saturation/value must lie in ``[0, 1]``. RGB→HSV→RGB
    round-trips a representable colour exactly (CL-1, SC-L001-1).

    Raises:
        ColorTheoryError: If any component is out of range.
    """
    hue = _check_hue(h) / 360.0
    sat = _check_unit("saturation", s)
    val = _check_unit("value", v)
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return rgba(
        _channel_from_unit(r),
        _channel_from_unit(g),
        _channel_from_unit(b),
        a,
    )


def rgba_to_hsl(color: RGBA) -> HSLA:
    """Convert an RGBA tuple to ``(hue°, saturation, lightness, alpha)``.

    Raises:
        ColorTheoryError: If ``color`` is not a well-formed RGBA tuple.
    """
    if not is_rgba(color):
        raise ColorTheoryError(f"not an RGBA colour: {color!r}")
    r, g, b, a = color
    # colorsys returns (h, l, s); reorder to (h, s, l).
    h, ligtness, s = colorsys.rgb_to_hls(
        r / CHANNEL_MAX, g / CHANNEL_MAX, b / CHANNEL_MAX
    )
    return (h * 360.0, s, ligtness, a)


def hsl_to_rgba(h: float, s: float, lightness: float, a: int = CHANNEL_MAX) -> RGBA:
    """Convert ``(hue°, saturation, lightness, alpha)`` back to an RGBA tuple.

    Raises:
        ColorTheoryError: If any component is out of range.
    """
    hue = _check_hue(h) / 360.0
    sat = _check_unit("saturation", s)
    light = _check_unit("lightness", lightness)
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return rgba(
        _channel_from_unit(r),
        _channel_from_unit(g),
        _channel_from_unit(b),
        a,
    )


# -- harmonies (hue rotation; S/V preserved, hue mod 360, alpha preserved) -----


def _rotate_hue(color: RGBA, delta: float) -> RGBA:
    h, s, v, a = rgba_to_hsv(color)
    return hsv_to_rgba(h + delta, s, v, a)


def complementary(color: RGBA) -> RGBA:
    """Return the complementary colour (hue + ``HARMONY_COMPLEMENTARY_DEG``)."""
    return _rotate_hue(color, HARMONY_COMPLEMENTARY_DEG)


def analogous(color: RGBA) -> Tuple[RGBA, RGBA]:
    """Return the two analogous neighbours (hue ± ``HARMONY_ANALOGOUS_DEG``)."""
    return (
        _rotate_hue(color, -HARMONY_ANALOGOUS_DEG),
        _rotate_hue(color, HARMONY_ANALOGOUS_DEG),
    )


def triadic(color: RGBA) -> Tuple[RGBA, RGBA]:
    """Return the two triadic colours (hue ± ``HARMONY_TRIADIC_DEG``)."""
    return (
        _rotate_hue(color, HARMONY_TRIADIC_DEG),
        _rotate_hue(color, -HARMONY_TRIADIC_DEG),
    )


def split_complementary(color: RGBA) -> Tuple[RGBA, RGBA]:
    """Return the split-complementary pair (hue ± ``HARMONY_SPLIT_COMPLEMENTARY_DEG``).

    These are the two neighbours of the complement (±30° from 180°).
    """
    return (
        _rotate_hue(color, HARMONY_SPLIT_COMPLEMENTARY_DEG),
        _rotate_hue(color, -HARMONY_SPLIT_COMPLEMENTARY_DEG),
    )


def harmony(color: RGBA, scheme: str) -> List[RGBA]:
    """Return the harmony set for ``scheme`` (excluding the base colour).

    Args:
        color: The base RGBA colour.
        scheme: One of ``'complementary'``, ``'analogous'``, ``'triadic'``,
            ``'split'``.

    Returns:
        A deterministic list of the harmony colours (SC-L002-6).

    Raises:
        ColorTheoryError: If ``scheme`` is not recognised.
    """
    if scheme == "complementary":
        return [complementary(color)]
    if scheme == "analogous":
        return list(analogous(color))
    if scheme == "triadic":
        return list(triadic(color))
    if scheme == "split":
        return list(split_complementary(color))
    raise ColorTheoryError(
        f"unknown harmony scheme {scheme!r}; expected one of {_SCHEMES}"
    )


# -- ramps (RAMP_STEP_COUNT steps, include the base, monotonic, deterministic) --


def _check_steps(steps: int) -> int:
    if not isinstance(steps, int) or isinstance(steps, bool):
        raise ColorTheoryError(f"steps must be an int, got {steps!r}")
    if steps < 2:
        raise ColorTheoryError(f"steps must be >= 2, got {steps}")
    return steps


def shade_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]:
    """Return a shade ramp of ``steps`` colours toward black (value decreasing).

    The first entry is the base colour; value scales by ``(1 - t)`` for
    ``t = k / (steps - 1)`` (research F9 Topic 1.2). Hue and saturation are held
    constant; alpha is preserved. Value decreases monotonically (SC-L003-1).
    """
    _check_steps(steps)
    h, s, v, a = rgba_to_hsv(color)
    out: List[RGBA] = []
    for k in range(steps):
        t = k / (steps - 1)
        out.append(hsv_to_rgba(h, s, v * (1.0 - t), a))
    return out


def tint_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]:
    """Return a tint ramp of ``steps`` colours toward white.

    The first entry is the base colour; value rises to white
    (``V + (1 - V)·t``) while saturation drops (``S·(1 - t)``) (research F9
    Topic 1.2). Hue and alpha are preserved (SC-L003-2).
    """
    _check_steps(steps)
    h, s, v, a = rgba_to_hsv(color)
    out: List[RGBA] = []
    for k in range(steps):
        t = k / (steps - 1)
        out.append(hsv_to_rgba(h, s * (1.0 - t), v + (1.0 - v) * t, a))
    return out


def tone_ramp(color: RGBA, steps: int = RAMP_STEP_COUNT) -> List[RGBA]:
    """Return a tone ramp of ``steps`` colours toward grey (saturation decreasing).

    The first entry is the base colour; saturation scales by ``(1 - t)`` at
    constant value (research F9 Topic 1.2). Hue and alpha are preserved
    (SC-L003-3).
    """
    _check_steps(steps)
    h, s, v, a = rgba_to_hsv(color)
    out: List[RGBA] = []
    for k in range(steps):
        t = k / (steps - 1)
        out.append(hsv_to_rgba(h, s * (1.0 - t), v, a))
    return out
