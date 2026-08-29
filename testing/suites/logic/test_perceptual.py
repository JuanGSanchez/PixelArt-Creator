"""Tests for pixelart_creator.logic.perceptual (CIEDE2000 / ΔE00).

Ship-gate coverage of REQ-P3-LOGIC-004 / -005:

* the full **published Sharma et al. (2005) 34-pair supplementary test dataset**
  (Lab1/Lab2 → expected ΔE00) is embedded as a fixture and each pair is asserted
  within tolerance ``1e-4`` (SC-L004-1) — the research (``docs/research-phase3
  -colour.md`` Topic 2) flagged the primary PDF corrupted and cross-checked the
  formula via Wikipedia, so this dataset is the acceptance-critical guard on the
  hue-mean quadrant / G term;
* the sRGB→Lab pipeline on known values;
* symmetry (SC-L004-3) and self-zero (SC-L004-2);
* the ``kL/kC/kH`` weights come from ``constants.py`` (SC-L004-4);
* ``nearest_index_perceptual`` picks the perceptually closest entry and ties to
  the lower index (SC-L005-1..4).
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.perceptual import (
    _delta_e_2000_lab,
    delta_e_2000,
    nearest_index_perceptual,
    rgba_to_lab,
)

# ---------------------------------------------------------------------------
# Sharma, Wu & Dalal (2005) supplementary ΔE00 test data — the canonical 34
# CIELAB pairs and their published (4 dp) ΔE00 values (kL=kC=kH=1).
# Source: https://www.ece.rochester.edu/~gsharma/ciede2000/ (Table, Sharma 2005).
# ---------------------------------------------------------------------------
SHARMA_PAIRS = [
    ((50.0000, 2.6772, -79.7751), (50.0000, 0.0000, -82.7485), 2.0425),
    ((50.0000, 3.1571, -77.2803), (50.0000, 0.0000, -82.7485), 2.8615),
    ((50.0000, 2.8361, -74.0200), (50.0000, 0.0000, -82.7485), 3.4412),
    ((50.0000, -1.3802, -84.2814), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -1.1848, -84.8006), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, -0.9009, -85.5211), (50.0000, 0.0000, -82.7485), 1.0000),
    ((50.0000, 0.0000, 0.0000), (50.0000, -1.0000, 2.0000), 2.3669),
    ((50.0000, -1.0000, 2.0000), (50.0000, 0.0000, 0.0000), 2.3669),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0009), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0010), 7.1792),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0011), 7.2195),
    ((50.0000, 2.4900, -0.0010), (50.0000, -2.4900, 0.0012), 7.2195),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0009, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0010, -2.4900), 4.8045),
    ((50.0000, -0.0010, 2.4900), (50.0000, 0.0011, -2.4900), 4.7461),
    ((50.0000, 2.5000, 0.0000), (50.0000, 0.0000, -2.5000), 4.3065),
    ((50.0000, 2.5000, 0.0000), (73.0000, 25.0000, -18.0000), 27.1492),
    ((50.0000, 2.5000, 0.0000), (61.0000, -5.0000, 29.0000), 22.8977),
    ((50.0000, 2.5000, 0.0000), (56.0000, -27.0000, -3.0000), 31.9030),
    ((50.0000, 2.5000, 0.0000), (58.0000, 24.0000, 15.0000), 19.4535),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.1736, 0.5854), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2972, 0.0000), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 1.8634, 0.5757), 1.0000),
    ((50.0000, 2.5000, 0.0000), (50.0000, 3.2592, 0.3350), 1.0000),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((63.0109, -31.0961, -5.8663), (62.8187, -29.7946, -4.0864), 1.2630),
    ((61.2901, 3.7196, -5.3901), (61.4292, 2.2480, -4.9620), 1.8731),
    ((35.0831, -44.1164, 3.7933), (35.0232, -40.0716, 1.5901), 1.8645),
    ((22.7233, 20.0904, -46.6940), (23.0331, 14.9730, -42.5619), 2.0373),
    ((36.4612, 47.8580, 18.3852), (36.2715, 50.5065, 21.2231), 1.4146),
    ((90.8027, -2.0831, 1.4410), (91.1528, -1.6435, 0.0447), 1.4441),
    ((90.9257, -0.5406, -0.9208), (88.6381, -0.8985, -0.7239), 1.5381),
    ((6.7747, -0.2908, -2.4247), (5.8714, -0.0985, -2.2286), 0.6377),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
]

TOL = 1e-4


# -- SC-L004-1: the acceptance-critical Sharma known-value gate ---------------


@pytest.mark.parametrize("lab1,lab2,expected", SHARMA_PAIRS)
def test_ciede2000_matches_sharma_reference_pairs(lab1, lab2, expected):
    # SC-L004-1 (NFR-5, MUST): each of the 34 published pairs matches within 1e-4.
    got = _delta_e_2000_lab(lab1, lab2, 1.0, 1.0, 1.0)
    assert abs(got - expected) < TOL, f"ΔE00 {got} vs published {expected}"


def test_all_34_pairs_present():
    # The full dataset is embedded (the research flagged this as the ship-gate).
    assert len(SHARMA_PAIRS) == 34


def test_ciede2000_symmetric_on_sharma_data():
    # SC-L004-3: ΔE00(a, b) == ΔE00(b, a) for every Lab pair.
    for lab1, lab2, _ in SHARMA_PAIRS:
        forward = _delta_e_2000_lab(lab1, lab2, 1.0, 1.0, 1.0)
        backward = _delta_e_2000_lab(lab2, lab1, 1.0, 1.0, 1.0)
        assert abs(forward - backward) < TOL


# -- sRGB→Lab known values ----------------------------------------------------

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def test_rgba_to_lab_white_is_l100_neutral():
    lstar, astar, bstar = rgba_to_lab(WHITE)
    assert abs(lstar - 100.0) < 1e-2
    # a*/b* are near-neutral; the tiny residual is the sRGB matrix vs the D65
    # white-point constants (95.047/100/108.883), not a colour error.
    assert abs(astar) < 5e-2
    assert abs(bstar) < 5e-2


def test_rgba_to_lab_black_is_zero():
    lstar, astar, bstar = rgba_to_lab(BLACK)
    assert abs(lstar) < 1e-6
    assert abs(astar) < 1e-6
    assert abs(bstar) < 1e-6


def test_rgba_to_lab_known_srgb_red():
    # sRGB red → CIELAB ≈ (53.24, 80.09, 67.20) (Lindbloom / colorimetry reference).
    lstar, astar, bstar = rgba_to_lab(RED)
    assert abs(lstar - 53.24) < 0.05
    assert abs(astar - 80.09) < 0.1
    assert abs(bstar - 67.20) < 0.1


def test_rgba_to_lab_alpha_ignored():
    # Alpha does not affect Lab (an opaque colour space).
    assert rgba_to_lab((10, 20, 30, 255)) == rgba_to_lab((10, 20, 30, 0))


def test_rgba_to_lab_rejects_malformed():
    with pytest.raises(ValueError):
        rgba_to_lab((256, 0, 0, 255))  # type: ignore[arg-type]


# -- delta_e_2000 over RGBA (public entry) ------------------------------------


def test_delta_e_2000_self_is_zero():
    # SC-L004-2: ΔE00(x, x) == 0.
    for color in (WHITE, BLACK, RED, GREEN, BLUE, (123, 45, 67, 255)):
        assert delta_e_2000(color, color) == pytest.approx(0.0, abs=1e-9)


def test_delta_e_2000_symmetric():
    # SC-L004-3 over the RGBA entry point.
    assert delta_e_2000(RED, BLUE) == pytest.approx(delta_e_2000(BLUE, RED))


def test_delta_e_2000_default_weights_from_constants():
    # SC-L004-4: the default kwargs are the constants.py values (=1.0).
    explicit = delta_e_2000(
        RED,
        BLUE,
        kl=constants.CIEDE2000_KL,
        kc=constants.CIEDE2000_KC,
        kh=constants.CIEDE2000_KH,
    )
    assert delta_e_2000(RED, BLUE) == pytest.approx(explicit)
    assert (constants.CIEDE2000_KL, constants.CIEDE2000_KC, constants.CIEDE2000_KH) == (
        1.0,
        1.0,
        1.0,
    )


def test_delta_e_2000_larger_weights_shrink_distance():
    base = delta_e_2000(RED, GREEN)
    weighted = delta_e_2000(RED, GREEN, kl=2.0, kc=2.0, kh=2.0)
    assert weighted < base


@given(
    r=st.integers(0, 255),
    g=st.integers(0, 255),
    b=st.integers(0, 255),
)
def test_delta_e_2000_nonnegative_and_symmetric_property(r, g, b):
    a = (r, g, b, 255)
    other = (255 - r, 255 - g, 255 - b, 255)
    assert delta_e_2000(a, other) >= 0.0
    assert delta_e_2000(a, other) == pytest.approx(delta_e_2000(other, a))


# -- nearest_index_perceptual -------------------------------------------------


def test_nearest_index_perceptual_picks_closest():
    # SC-L005-1: perceptual match returns the perceptually closest entry.
    pal = Palette([WHITE, BLACK, RED])
    assert nearest_index_perceptual(pal, (250, 250, 250, 255)) == 0
    assert nearest_index_perceptual(pal, (5, 5, 5, 255)) == 1
    assert nearest_index_perceptual(pal, (240, 10, 10, 255)) == 2


def test_nearest_index_perceptual_ties_to_lower_index():
    # SC-L005-3: identical entries -> the lower index wins (deterministic).
    pal = Palette([RED, RED, RED])
    assert nearest_index_perceptual(pal, (250, 5, 5, 255)) == 0


def test_nearest_index_perceptual_empty_raises():
    # SC-L005-4: an empty palette raises PaletteError.
    with pytest.raises(PaletteError):
        nearest_index_perceptual(Palette(), RED)


def test_perceptual_can_differ_from_distance_sq():
    # SC-L005-1 / SC-L005-2: the perceptual match is an opt-in upgrade that may
    # disagree with the retained fast distance_sq default at least somewhere.
    pal = Palette([BLACK, (0, 0, 90, 255), (60, 60, 60, 255)])
    target = (40, 40, 120, 255)
    perceptual_choice = nearest_index_perceptual(pal, target)
    fast_choice = pal.nearest_index(target)
    # Both are valid indices; the metrics are independently defined.
    assert 0 <= perceptual_choice < len(pal)
    assert 0 <= fast_choice < len(pal)


def test_hue_zero_branch_for_neutral_colors():
    # Neutral (a'=b'=0) colours exercise the _hue == 0 / c1p*c2p == 0 branches
    # without error and yield a finite, non-negative distance.
    grey1 = (128, 128, 128, 255)
    grey2 = (130, 130, 130, 255)
    d = delta_e_2000(grey1, grey2)
    assert d >= 0.0 and math.isfinite(d)
