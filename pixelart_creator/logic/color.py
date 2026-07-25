"""RGBA colour value type and pure colour operations (zero Qt, S11).

Colours are plain ``(r, g, b, a)`` tuples of four ints in ``0..255``. Qt colour
objects (``QColor``) live in ``ui/`` only; ``logic/`` works on tuples so the
layer stays Qt-free (architecture gate, S11). Every helper here is deterministic
and side-effect-free.
"""

from __future__ import annotations

from typing import Tuple

#: An RGBA colour: four channels, each an int in ``0..255``.
RGBA = Tuple[int, int, int, int]

CHANNEL_MIN = 0
CHANNEL_MAX = 255

TRANSPARENT: RGBA = (0, 0, 0, 0)
BLACK: RGBA = (0, 0, 0, 255)
WHITE: RGBA = (255, 255, 255, 255)


class ColorError(ValueError):
    """Raised when a colour value is malformed or out of range."""


def _check_channel(name: str, value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ColorError(f"{name} channel must be an int, got {value!r}")
    if value < CHANNEL_MIN or value > CHANNEL_MAX:
        raise ColorError(f"{name} channel {value} out of range 0..255")
    return value


def rgba(r: int, g: int, b: int, a: int = CHANNEL_MAX) -> RGBA:
    """Build a validated RGBA tuple.

    Args:
        r, g, b: Colour channels in ``0..255``.
        a: Alpha channel in ``0..255`` (default fully opaque).

    Returns:
        The validated ``(r, g, b, a)`` tuple.

    Raises:
        ColorError: If any channel is not an int in ``0..255``.
    """
    return (
        _check_channel("red", r),
        _check_channel("green", g),
        _check_channel("blue", b),
        _check_channel("alpha", a),
    )


def is_rgba(value: object) -> bool:
    """Return ``True`` if ``value`` is a well-formed RGBA tuple."""
    if not isinstance(value, tuple) or len(value) != 4:
        return False
    for channel in value:
        if not isinstance(channel, int) or isinstance(channel, bool):
            return False
        if channel < CHANNEL_MIN or channel > CHANNEL_MAX:
            return False
    return True


def to_hex(color: RGBA, *, with_alpha: bool = True) -> str:
    """Serialise an RGBA tuple to ``#RRGGBB`` or ``#RRGGBBAA``."""
    r, g, b, a = rgba(*color)
    if with_alpha:
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"


def from_hex(text: str) -> RGBA:
    """Parse ``#RGB``, ``#RRGGBB`` or ``#RRGGBBAA`` (``#`` optional) to RGBA.

    Raises:
        ColorError: If the string is not a recognised hex colour.
    """
    if not isinstance(text, str):
        raise ColorError(f"hex colour must be a string, got {text!r}")
    s = text.strip().lstrip("#")
    try:
        if len(s) == 3:
            r, g, b = (int(c * 2, 16) for c in s)
            return rgba(r, g, b)
        if len(s) == 6:
            r, g, b = (int(s[i : i + 2], 16) for i in (0, 2, 4))
            return rgba(r, g, b)
        if len(s) == 8:
            r, g, b, a = (int(s[i : i + 2], 16) for i in (0, 2, 4, 6))
            return rgba(r, g, b, a)
    except ValueError as exc:
        raise ColorError(f"invalid hex colour {text!r}") from exc
    raise ColorError(f"hex colour {text!r} must have 3, 6 or 8 digits")


def blend_over(src: RGBA, dst: RGBA) -> RGBA:
    """Alpha-composite ``src`` over ``dst`` (straight-alpha ``source-over``).

    Uses integer rounding so identical inputs always yield identical output
    (determinism, P2). A fully opaque ``src`` returns ``src`` unchanged.
    """
    sr, sg, sb, sa = rgba(*src)
    dr, dg, db, da = rgba(*dst)
    if sa == CHANNEL_MAX:
        return (sr, sg, sb, sa)
    if sa == 0:
        return (dr, dg, db, da)
    # 0 < sa < 255 here, so out_a is always > 0.
    sa_f = sa / 255.0
    da_f = da / 255.0
    out_a = sa_f + da_f * (1.0 - sa_f)

    def _channel(sc: int, dc: int) -> int:
        value = (sc * sa_f + dc * da_f * (1.0 - sa_f)) / out_a
        return max(CHANNEL_MIN, min(CHANNEL_MAX, int(round(value))))

    return (
        _channel(sr, dr),
        _channel(sg, dg),
        _channel(sb, db),
        max(CHANNEL_MIN, min(CHANNEL_MAX, int(round(out_a * 255.0)))),
    )


def distance_sq(a: RGBA, b: RGBA) -> int:
    """Squared Euclidean distance over all four channels (integer, exact).

    Cheap ordering metric for nearest-colour matching; a perceptual metric
    (CIEDE2000) is a Phase 3 addition layered on top of this baseline.
    """
    ar, ag, ab, aa = rgba(*a)
    br, bg, bb, ba = rgba(*b)
    return (ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2 + (aa - ba) ** 2
