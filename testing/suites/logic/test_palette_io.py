"""Tests for pixelart_creator.logic.palette_io (encode/decode gpl/pal/hex).

Covers REQ-P3-LOGIC-016 (SC-L016-1..3): encode∘decode round-trips a palette for
each format, malformed input is rejected defensively (no eval/exec), encode is
deterministic, and the alpha behaviour is explicit — gpl/pal drop alpha while
hex preserves it.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette
from pixelart_creator.logic.palette_io import PaletteIOError, decode, encode

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSLUCENT = (10, 20, 30, 128)


@pytest.mark.parametrize("fmt", ["gpl", "pal", "hex"])
def test_encode_decode_round_trip_opaque(fmt):
    # SC-L016-1: encode∘decode round-trips opaque colours for every format.
    pal = Palette([RED, GREEN, BLUE])
    text = encode(pal, fmt)
    assert decode(text, fmt) == pal


def test_hex_preserves_alpha():
    # hex carries #RRGGBBAA -> alpha survives the round-trip.
    pal = Palette([TRANSLUCENT])
    restored = decode(encode(pal, "hex"), "hex")
    assert restored.colors() == [TRANSLUCENT]


@pytest.mark.parametrize("fmt", ["gpl", "pal"])
def test_gpl_pal_drop_alpha(fmt):
    # gpl / pal are RGB-only; alpha is dropped (forced opaque on decode).
    pal = Palette([TRANSLUCENT])
    restored = decode(encode(pal, fmt), fmt)
    assert restored.colors() == [(10, 20, 30, 255)]


def test_encode_deterministic():
    # SC-L016-3.
    pal = Palette([RED, GREEN])
    assert encode(pal, "gpl") == encode(pal, "gpl")
    assert encode(pal, "hex") == encode(pal, "hex")


def test_encode_headers_present():
    pal = Palette([RED])
    assert encode(pal, "gpl").startswith("GIMP Palette")
    assert encode(pal, "pal").startswith("JASC-PAL")


def test_unknown_format_raises_on_encode_and_decode():
    with pytest.raises(PaletteIOError):
        encode(Palette([RED]), "aco")
    with pytest.raises(PaletteIOError):
        decode("x", "aco")


# -- defensive parsing (SC-L016-2) --------------------------------------------


def test_decode_non_string_rejected():
    with pytest.raises(PaletteIOError):
        decode(1234, "hex")  # type: ignore[arg-type]


def test_decode_hex_invalid_colour_rejected():
    with pytest.raises(PaletteIOError):
        decode("#ZZZZZZ", "hex")


def test_decode_gpl_missing_header_rejected():
    with pytest.raises(PaletteIOError):
        decode("255 0 0", "gpl")


def test_decode_gpl_bad_channel_rejected():
    with pytest.raises(PaletteIOError):
        decode("GIMP Palette\n300 0 0", "gpl")
    with pytest.raises(PaletteIOError):
        decode("GIMP Palette\nfoo bar baz", "gpl")


def test_decode_pal_missing_header_rejected():
    with pytest.raises(PaletteIOError):
        decode("255 0 0\n0 255 0", "pal")


def test_decode_pal_bad_version_rejected():
    with pytest.raises(PaletteIOError):
        decode("JASC-PAL\n0200\n1\n255 0 0", "pal")


def test_decode_pal_bad_count_rejected():
    with pytest.raises(PaletteIOError):
        decode("JASC-PAL\n0100\nfoo\n255 0 0", "pal")


def test_decode_pal_negative_count_rejected():
    with pytest.raises(PaletteIOError):
        decode("JASC-PAL\n0100\n-1", "pal")


def test_decode_pal_short_body_rejected():
    with pytest.raises(PaletteIOError):
        decode("JASC-PAL\n0100\n3\n255 0 0", "pal")


def test_decode_gpl_skips_comments_and_metadata():
    text = "GIMP Palette\nName: Foo\nColumns: 4\n# a comment\n\n255 0 0\n0 255 0"
    pal = decode(text, "gpl")
    assert pal.colors() == [RED, GREEN]


def test_decode_hex_skips_blank_and_bare_comment_lines():
    # Per the module contract, a bare "#" comment and blank lines are skipped.
    text = "\n#\n#FF0000\n\n#00FF00\n"
    pal = decode(text, "hex")
    assert pal.colors() == [(255, 0, 0, 255), (0, 255, 0, 255)]


def test_decode_rejects_oversized_palette():
    text = "\n".join("#000000" for _ in range(MAX_PALETTE_SIZE + 1))
    with pytest.raises(PaletteIOError):
        decode(text, "hex")


def test_encode_empty_palette():
    assert decode(encode(Palette(), "hex"), "hex") == Palette()
