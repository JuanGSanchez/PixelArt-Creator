"""Tests for pixelart_creator.logic.color_theory (HSV/HSL, harmonies, ramps).

Covers REQ-P3-LOGIC-001 (SC-L001-1..5), -002 (SC-L002-1..6), -003 (SC-L003-1..4):

* RGB↔HSV round-trip identity, known primaries, alpha preservation, malformed
  input;
* harmony **angle correctness** (complementary +180, analogous ±30, triadic
  ±120, split-complementary ±150), hue wrap mod 360, determinism;
* shade/tint/tone ramps of ``RAMP_STEP_COUNT`` steps, monotonic, include the
  base, deterministic.

Hypothesis properties: RGB→HSV→RGB identity, harmony hue-wrap, ramp determinism.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.color_theory import (
    ColorTheoryError,
    analogous,
    complementary,
    harmony,
    hsl_to_rgba,
    hsv_to_rgba,
    rgba_to_hsl,
    rgba_to_hsv,
    shade_ramp,
    split_complementary,
    tint_ramp,
    tone_ramp,
    triadic,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
MID = (200, 120, 40, 200)

rgb_channels = st.integers(min_value=0, max_value=255)
alpha = st.integers(min_value=0, max_value=255)


# -- SC-L001: conversion ------------------------------------------------------


def test_known_primaries_hue():
    # SC-L001-2: red=0°, green=120°, blue=240°.
    assert rgba_to_hsv(RED)[0] == pytest.approx(0.0)
    assert rgba_to_hsv(GREEN)[0] == pytest.approx(120.0)
    assert rgba_to_hsv(BLUE)[0] == pytest.approx(240.0)


def test_alpha_preserved_through_hsv():
    # SC-L001-3.
    assert rgba_to_hsv((10, 20, 30, 77))[3] == 77
    assert hsv_to_rgba(200.0, 0.5, 0.5, 42)[3] == 42


def test_hsl_round_trips():
    # SC-L001-4: HSL is provided and round-trips within rounding.
    h, s, ligt, a = rgba_to_hsl(MID)
    back = hsl_to_rgba(h, s, ligt, a)
    for channel, expected in zip(back, MID):
        assert abs(channel - expected) <= 1


def test_hsl_alpha_preserved():
    assert rgba_to_hsl((1, 2, 3, 99))[3] == 99


@pytest.mark.parametrize("bad", [(256, 0, 0, 255), (0, 0, 0), "x", (1, 2, 3, 4, 5)])
def test_rgba_to_hsv_rejects_malformed(bad):
    # SC-L001-5.
    with pytest.raises(ColorTheoryError):
        rgba_to_hsv(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [(256, 0, 0, 255), (0, 0, 0)])
def test_rgba_to_hsl_rejects_malformed(bad):
    with pytest.raises(ColorTheoryError):
        rgba_to_hsl(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_s", [-0.1, 1.1, True, "x"])
def test_hsv_to_rgba_rejects_bad_saturation(bad_s):
    with pytest.raises(ColorTheoryError):
        hsv_to_rgba(0.0, bad_s, 0.5)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_v", [-0.1, 1.1])
def test_hsv_to_rgba_rejects_bad_value(bad_v):
    with pytest.raises(ColorTheoryError):
        hsv_to_rgba(0.0, 0.5, bad_v)


def test_hsv_to_rgba_rejects_bad_hue_type():
    with pytest.raises(ColorTheoryError):
        hsv_to_rgba(True, 0.5, 0.5)  # type: ignore[arg-type]


def test_hsl_to_rgba_rejects_bad_lightness():
    with pytest.raises(ColorTheoryError):
        hsl_to_rgba(0.0, 0.5, 2.0)


@given(r=rgb_channels, g=rgb_channels, b=rgb_channels, a=alpha)
def test_rgb_hsv_round_trip_identity(r, g, b, a):
    # SC-L001-1 (CL-1): RGB→HSV→RGB is the identity for a representable colour.
    color = (r, g, b, a)
    h, s, v, alpha_out = rgba_to_hsv(color)
    back = hsv_to_rgba(h, s, v, alpha_out)
    assert back == color


# -- SC-L002: harmonies -------------------------------------------------------


def _hue(color):
    return rgba_to_hsv(color)[0]


def test_complementary_angle():
    # SC-L002-1: hue rotates by exactly +180° (S/V preserved).
    base = (200, 120, 40, 255)
    bh, bs, bv, _ = rgba_to_hsv(base)
    comp = complementary(base)
    ch, cs, cv, _ = rgba_to_hsv(comp)
    assert ch == pytest.approx(
        (bh + constants.HARMONY_COMPLEMENTARY_DEG) % 360.0, abs=1.0
    )
    assert cs == pytest.approx(bs, abs=0.01)
    assert cv == pytest.approx(bv, abs=0.01)


def test_analogous_angles():
    # SC-L002-2: hue ±30°.
    base = (200, 120, 40, 255)
    bh = _hue(base)
    lo, hi = analogous(base)
    assert _hue(lo) == pytest.approx(
        (bh - constants.HARMONY_ANALOGOUS_DEG) % 360.0, abs=1.0
    )
    assert _hue(hi) == pytest.approx(
        (bh + constants.HARMONY_ANALOGOUS_DEG) % 360.0, abs=1.0
    )


def test_triadic_angles():
    # SC-L002-3: hue ±120°.
    base = (200, 120, 40, 255)
    bh = _hue(base)
    a, b = triadic(base)
    assert _hue(a) == pytest.approx(
        (bh + constants.HARMONY_TRIADIC_DEG) % 360.0, abs=1.0
    )
    assert _hue(b) == pytest.approx(
        (bh - constants.HARMONY_TRIADIC_DEG) % 360.0, abs=1.0
    )


def test_split_complementary_angles():
    # SC-L002-4: hue ±150°.
    base = (200, 120, 40, 255)
    bh = _hue(base)
    a, b = split_complementary(base)
    assert _hue(a) == pytest.approx(
        (bh + constants.HARMONY_SPLIT_COMPLEMENTARY_DEG) % 360.0, abs=1.0
    )
    assert _hue(b) == pytest.approx(
        (bh - constants.HARMONY_SPLIT_COMPLEMENTARY_DEG) % 360.0, abs=1.0
    )


def test_hue_wraps_mod_360():
    # SC-L002-5: base 300° complementary = 120°.
    base = hsv_to_rgba(300.0, 1.0, 1.0)
    assert _hue(complementary(base)) == pytest.approx(120.0, abs=1.0)


def test_harmony_dispatch_and_determinism():
    # SC-L002-6: deterministic; the dispatcher covers every scheme.
    base = (123, 200, 50, 255)
    assert harmony(base, "complementary") == [complementary(base)]
    assert harmony(base, "analogous") == list(analogous(base))
    assert harmony(base, "triadic") == list(triadic(base))
    assert harmony(base, "split") == list(split_complementary(base))
    assert harmony(base, "triadic") == harmony(base, "triadic")


def test_harmony_unknown_scheme_raises():
    with pytest.raises(ColorTheoryError):
        harmony(RED, "tetradic")


def test_complementary_preserves_alpha():
    assert complementary((200, 120, 40, 128))[3] == 128


@given(h=st.floats(min_value=-1080.0, max_value=1080.0), a=alpha)
def test_complementary_hue_wrap_property(h, a):
    base = hsv_to_rgba(h % 360.0, 0.8, 0.8, a)
    comp = complementary(base)
    expected = (_hue(base) + 180.0) % 360.0
    got = _hue(comp)
    diff = min((got - expected) % 360.0, (expected - got) % 360.0)
    assert diff < 2.0


# -- SC-L003: ramps -----------------------------------------------------------


def test_shade_ramp_length_and_base():
    # SC-L003-1 / SC-L003-4: RAMP_STEP_COUNT steps, first entry is the base.
    ramp = shade_ramp(MID)
    assert len(ramp) == constants.RAMP_STEP_COUNT
    assert ramp[0] == MID


def test_shade_ramp_value_decreases_monotonically():
    ramp = shade_ramp((200, 120, 40, 255))
    values = [rgba_to_hsv(c)[2] for c in ramp]
    assert values == sorted(values, reverse=True)
    assert ramp[-1] == (0, 0, 0, 255)  # toward black


def test_tint_ramp_trends_to_white():
    # SC-L003-2.
    ramp = tint_ramp((200, 120, 40, 255))
    assert ramp[0] == (200, 120, 40, 255)
    values = [rgba_to_hsv(c)[2] for c in ramp]
    sats = [rgba_to_hsv(c)[1] for c in ramp]
    assert values == sorted(values)  # value rises toward white
    assert sats == sorted(sats, reverse=True)  # saturation falls
    assert ramp[-1] == (255, 255, 255, 255)


def test_tone_ramp_desaturates():
    # SC-L003-3: saturation decreases toward grey; value held.
    base = (200, 120, 40, 255)
    ramp = tone_ramp(base)
    assert ramp[0] == base
    sats = [rgba_to_hsv(c)[1] for c in ramp]
    assert sats == sorted(sats, reverse=True)
    assert rgba_to_hsv(ramp[-1])[1] == pytest.approx(0.0, abs=0.01)


def test_ramps_preserve_alpha():
    for ramp_fn in (shade_ramp, tint_ramp, tone_ramp):
        for color in ramp_fn((200, 120, 40, 111)):
            assert color[3] == 111


def test_ramps_deterministic():
    # SC-L003-4.
    assert shade_ramp(MID) == shade_ramp(MID)
    assert tint_ramp(MID) == tint_ramp(MID)
    assert tone_ramp(MID) == tone_ramp(MID)


@pytest.mark.parametrize("bad", [1, 0, -3, True, "x", 2.0])
def test_ramp_rejects_bad_step_count(bad):
    with pytest.raises(ColorTheoryError):
        shade_ramp(MID, steps=bad)  # type: ignore[arg-type]


def test_ramp_custom_step_count():
    assert len(tint_ramp(MID, steps=8)) == 8
