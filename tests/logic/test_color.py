"""Tests for pixelart_creator.logic.color."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import color


def test_rgba_defaults_opaque():
    assert color.rgba(1, 2, 3) == (1, 2, 3, 255)


@pytest.mark.parametrize("bad", [-1, 256, 1000])
def test_rgba_out_of_range_rejected(bad):
    with pytest.raises(color.ColorError):
        color.rgba(bad, 0, 0)


def test_rgba_rejects_non_int_and_bool():
    with pytest.raises(color.ColorError):
        color.rgba(1.5, 0, 0)  # type: ignore[arg-type]
    with pytest.raises(color.ColorError):
        color.rgba(True, 0, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value,expected",
    [
        ((1, 2, 3, 4), True),
        ((1, 2, 3), False),
        ((1, 2, 3, 300), False),
        ((1, 2, 3, True), False),
        ("nope", False),
        ([1, 2, 3, 4], False),
    ],
)
def test_is_rgba(value, expected):
    assert color.is_rgba(value) is expected


def test_hex_roundtrip_with_and_without_alpha():
    assert color.to_hex((255, 0, 128, 255)) == "#FF0080FF"
    assert color.to_hex((255, 0, 128, 255), with_alpha=False) == "#FF0080"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("#f00", (255, 0, 0, 255)),
        ("0F0", (0, 255, 0, 255)),
        ("#0000FF", (0, 0, 255, 255)),
        ("#01020304", (1, 2, 3, 4)),
    ],
)
def test_from_hex_variants(text, expected):
    assert color.from_hex(text) == expected


@pytest.mark.parametrize("bad", ["#12", "#12345", "wxyz", "#GGGGGG", 123])
def test_from_hex_invalid(bad):
    with pytest.raises(color.ColorError):
        color.from_hex(bad)  # type: ignore[arg-type]


def test_blend_over_opaque_source_returns_source():
    assert color.blend_over((10, 20, 30, 255), (0, 0, 0, 255)) == (10, 20, 30, 255)


def test_blend_over_transparent_source_returns_dest():
    assert color.blend_over((10, 20, 30, 0), (5, 6, 7, 200)) == (5, 6, 7, 200)


def test_blend_over_half_alpha_on_opaque():
    out = color.blend_over((255, 0, 0, 128), (0, 0, 255, 255))
    assert out[3] == 255
    assert out[0] > out[2]  # red dominates but blue remains


def test_blend_over_transparent_source_returns_dest_even_if_dest_transparent():
    # source-over with a fully transparent source returns the destination as-is.
    assert color.blend_over((10, 10, 10, 0), (20, 20, 20, 0)) == (20, 20, 20, 0)


def test_distance_sq_zero_and_symmetric():
    assert color.distance_sq(color.BLACK, color.BLACK) == 0
    a, b = (0, 0, 0, 255), (0, 0, 255, 255)
    assert color.distance_sq(a, b) == color.distance_sq(b, a) == 255**2


@given(
    st.integers(0, 255),
    st.integers(0, 255),
    st.integers(0, 255),
    st.integers(0, 255),
)
def test_hex_roundtrip_property(r, g, b, a):
    assert color.from_hex(color.to_hex((r, g, b, a))) == (r, g, b, a)
