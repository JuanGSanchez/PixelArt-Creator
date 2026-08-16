"""Perceptual colour difference: sRGB→Lab + CIEDE2000 (ΔE00) (zero Qt, S11).

Implements the CIEDE2000 perceptual colour-difference metric and a perceptual
nearest-palette match layered *on top of* the Phase-1 ``distance_sq`` baseline —
an opt-in upgrade path, not a replacement (CL-10, PL-D6). Pure, deterministic,
Qt-free.

Grounding: the sRGB→XYZ(D65)→L*a*b* pipeline and the full ΔE00 equation
(pins recorded in docs/adr/0003-hardware-palette-data-placement.md and
docs/adr/0001-s12-governs-tuning-not-intrinsic-constants.md; original research
record lives outside this repository), Topic 2 (Sharma, Wu & Dalal 2005; the
Wikipedia Color-difference article mirrors the same formulation). The D65 white
point, sRGB linearisation coefficients, XYZ matrix, and the ΔE00 "magic" terms
(0.17/0.24/0.32/0.20, 25⁷, 6°/30°/275°/25°/63°) are intrinsic to the CIELAB /
CIEDE2000 standards, so they stay **local** to this module (ADR-0001); only the
parametric weights ``CIEDE2000_KL/KC/KH`` are tuning scalars in
:mod:`~pixelart_creator.logic.constants`. REQ-P3-LOGIC-004, -005.

The implementation MUST be validated against Sharma et al.'s supplementary
test-data pairs within a documented tolerance (AGT-04, plan §7) before ship.
"""

from __future__ import annotations

import math
from typing import Tuple

from pixelart_creator.logic.color import CHANNEL_MAX, RGBA, is_rgba
from pixelart_creator.logic.constants import CIEDE2000_KC, CIEDE2000_KH, CIEDE2000_KL
from pixelart_creator.logic.palette import Palette, PaletteError

__all__ = ["rgba_to_lab", "delta_e_2000", "nearest_index_perceptual"]

# -- intrinsic CIELAB / sRGB constants (standard-fixed, local per ADR-0001) ----
_D65_XN = 95.047
_D65_YN = 100.0
_D65_ZN = 108.883
_SRGB_LINEAR_THRESHOLD = 0.04045
_SRGB_LINEAR_DIVISOR = 12.92
_SRGB_GAMMA_OFFSET = 0.055
_SRGB_GAMMA_DIVISOR = 1.055
_SRGB_GAMMA_EXPONENT = 2.4
_LAB_EPSILON = (6.0 / 29.0) ** 3
_POW_25_7 = 25.0**7


def _linearise(channel: float) -> float:
    """Linearise one gamma-encoded sRGB channel in ``[0, 1]``."""
    if channel <= _SRGB_LINEAR_THRESHOLD:
        return channel / _SRGB_LINEAR_DIVISOR
    return (
        (channel + _SRGB_GAMMA_OFFSET) / _SRGB_GAMMA_DIVISOR
    ) ** _SRGB_GAMMA_EXPONENT


def _lab_f(t: float) -> float:
    if t > _LAB_EPSILON:
        return t ** (1.0 / 3.0)
    return (1.0 / 3.0) * (29.0 / 6.0) ** 2 * t + 4.0 / 29.0


def rgba_to_lab(color: RGBA) -> Tuple[float, float, float]:
    """Convert an RGBA colour to CIELAB ``(L*, a*, b*)`` via sRGB→XYZ(D65)→Lab.

    Alpha is ignored (Lab is an opaque-colour space). Deterministic.

    Raises:
        PaletteError: never; malformed input raises ``ValueError`` via the
            colour check below.
    """
    if not is_rgba(color):
        raise ValueError(f"not an RGBA colour: {color!r}")
    r, g, b, _a = color
    rl = _linearise(r / CHANNEL_MAX)
    gl = _linearise(g / CHANNEL_MAX)
    bl = _linearise(b / CHANNEL_MAX)
    # Linear RGB → XYZ (sRGB / D65 matrix), scaled to the 0..100 range.
    x = (0.4124 * rl + 0.3576 * gl + 0.1805 * bl) * 100.0
    y = (0.2126 * rl + 0.7152 * gl + 0.0722 * bl) * 100.0
    z = (0.0193 * rl + 0.1192 * gl + 0.9505 * bl) * 100.0
    fx = _lab_f(x / _D65_XN)
    fy = _lab_f(y / _D65_YN)
    fz = _lab_f(z / _D65_ZN)
    lstar = 116.0 * fy - 16.0
    astar = 500.0 * (fx - fy)
    bstar = 200.0 * (fy - fz)
    return (lstar, astar, bstar)


def _delta_e_2000_lab(
    lab1: Tuple[float, float, float],
    lab2: Tuple[float, float, float],
    kl: float,
    kc: float,
    kh: float,
) -> float:
    """ΔE00 between two CIELAB samples (Sharma et al. 2005 formulation)."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    # Step 1 — chroma and the G adjustment.
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    g = 0.5 * (1.0 - math.sqrt(c_bar**7 / (c_bar**7 + _POW_25_7)))
    a1p = (1.0 + g) * a1
    a2p = (1.0 + g) * a2
    c1p = math.hypot(a1p, b1)
    c2p = math.hypot(a2p, b2)

    def _hue(ap: float, bp: float) -> float:
        if ap == 0.0 and bp == 0.0:
            return 0.0
        angle = math.degrees(math.atan2(bp, ap))
        return angle + 360.0 if angle < 0.0 else angle

    h1p = _hue(a1p, b1)
    h2p = _hue(a2p, b2)

    # Step 2 — differences.
    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0.0:
        dhp = 0.0
    else:
        diff = h2p - h1p
        if abs(diff) <= 180.0:
            dhp = diff
        elif diff > 180.0:
            dhp = diff - 360.0
        else:
            dhp = diff + 360.0
    dbig_hp = 2.0 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2.0)

    # Step 3 — weighting means and functions.
    lbar = (l1 + l2) / 2.0
    cbar = (c1p + c2p) / 2.0
    if c1p * c2p == 0.0:
        hbar = h1p + h2p
    elif abs(h1p - h2p) <= 180.0:
        hbar = (h1p + h2p) / 2.0
    elif h1p + h2p < 360.0:
        hbar = (h1p + h2p + 360.0) / 2.0
    else:
        hbar = (h1p + h2p - 360.0) / 2.0

    t = (
        1.0
        - 0.17 * math.cos(math.radians(hbar - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * hbar))
        + 0.32 * math.cos(math.radians(3.0 * hbar + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * hbar - 63.0))
    )
    dtheta = 30.0 * math.exp(-(((hbar - 275.0) / 25.0) ** 2))
    rc = 2.0 * math.sqrt(cbar**7 / (cbar**7 + _POW_25_7))
    sl = 1.0 + (0.015 * (lbar - 50.0) ** 2) / math.sqrt(20.0 + (lbar - 50.0) ** 2)
    sc = 1.0 + 0.045 * cbar
    sh = 1.0 + 0.015 * cbar * t
    rt = -math.sin(math.radians(2.0 * dtheta)) * rc

    # Step 4 — final combination.
    term_l = dlp / (kl * sl)
    term_c = dcp / (kc * sc)
    term_h = dbig_hp / (kh * sh)
    return math.sqrt(term_l**2 + term_c**2 + term_h**2 + rt * term_c * term_h)


def delta_e_2000(
    a: RGBA,
    b: RGBA,
    *,
    kl: float = CIEDE2000_KL,
    kc: float = CIEDE2000_KC,
    kh: float = CIEDE2000_KH,
) -> float:
    """Return the CIEDE2000 (ΔE00) perceptual difference between two RGBA colours.

    Colours are converted sRGB→Lab (alpha ignored) then compared by the full
    ΔE00 equation. The metric is symmetric (SC-L004-3) and ``ΔE00(x, x) == 0``
    (SC-L004-2). The parametric weights default to the ``constants.py`` values
    (=1.0, SC-L004-4).

    Raises:
        ValueError: If either colour is malformed.
    """
    return _delta_e_2000_lab(rgba_to_lab(a), rgba_to_lab(b), kl, kc, kh)


def nearest_index_perceptual(palette: Palette, color: RGBA) -> int:
    """Return the palette index perceptually closest to ``color`` by ΔE00.

    An opt-in perceptual upgrade over :meth:`Palette.nearest_index` /
    ``color.distance_sq`` (which remain the retained fast default, CL-10). Ties
    resolve to the lower index (deterministic, P2, SC-L005-3).

    Raises:
        PaletteError: If the palette is empty (SC-L005-4).
    """
    colors = palette.colors()
    if not colors:
        raise PaletteError("cannot match against an empty palette")
    target_lab = rgba_to_lab(color)
    best_index = 0
    best_dist = _delta_e_2000_lab(
        target_lab, rgba_to_lab(colors[0]), CIEDE2000_KL, CIEDE2000_KC, CIEDE2000_KH
    )
    for i in range(1, len(colors)):
        dist = _delta_e_2000_lab(
            target_lab,
            rgba_to_lab(colors[i]),
            CIEDE2000_KL,
            CIEDE2000_KC,
            CIEDE2000_KH,
        )
        if dist < best_dist:
            best_dist, best_index = dist, i
    return best_index
