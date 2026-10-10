"""Tests for ``pixelart_creator.logic.contrast`` (REQ-VI-UI-003, REQ-VI-UI-004).

Qt-free. Expected values are WCAG facts taken from outside the module
(white/black = 21:1, ``#767676`` on white = 4.54:1, ``#777777`` on white =
4.48:1, ``#0000ff`` on white = 8.59:1) so a mutated formula cannot agree with
itself. The eight-digit colour convention is ``#AARRGGBB`` (alpha first), as Qt
reads it.
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import contrast
from pixelart_creator.logic.contrast import (
    COMPONENT_MIN_RATIO,
    FOCUS_MIN_RATIO,
    TEXT_MIN_RATIO,
    ContrastError,
    ContrastPair,
    PairKind,
    composite,
    contrast_ratio,
    floor_for,
    is_valid_color,
    meets_floor,
    parse_color,
    relative_luminance,
)

_CHANNEL = st.integers(min_value=0, max_value=255)
_OPAQUE = st.builds(
    lambda r, g, b: f"#{r:02x}{g:02x}{b:02x}", _CHANNEL, _CHANNEL, _CHANNEL
)
_TRANSLUCENT = st.builds(
    lambda a, r, g, b: f"#{a:02x}{r:02x}{g:02x}{b:02x}",
    _CHANNEL,
    _CHANNEL,
    _CHANNEL,
    _CHANNEL,
)


class TestFloors:
    """The WCAG floors are fixed values (intrinsic, ADR-0001)."""

    def test_text_floor_is_4_5(self):
        assert TEXT_MIN_RATIO == 4.5

    def test_component_floor_is_3(self):
        assert COMPONENT_MIN_RATIO == 3.0

    def test_focus_floor_is_3(self):
        assert FOCUS_MIN_RATIO == 3.0

    def test_floor_for_each_gated_kind(self):
        assert floor_for(PairKind.TEXT) == 4.5
        assert floor_for(PairKind.COMPONENT) == 3.0
        assert floor_for(PairKind.FOCUS) == 3.0

    def test_floor_for_info_is_none(self):
        assert floor_for(PairKind.INFO) is None

    def test_pair_kind_values_are_the_file_spellings(self):
        assert [k.value for k in PairKind] == ["text", "component", "focus", "info"]


class TestMeetsFloor:
    @pytest.mark.parametrize(
        "kind,floor",
        [
            (PairKind.TEXT, 4.5),
            (PairKind.COMPONENT, 3.0),
            (PairKind.FOCUS, 3.0),
        ],
    )
    def test_exactly_at_floor_passes(self, kind, floor):
        assert meets_floor(kind, floor) is True

    @pytest.mark.parametrize(
        "kind,floor",
        [
            (PairKind.TEXT, 4.5),
            (PairKind.COMPONENT, 3.0),
            (PairKind.FOCUS, 3.0),
        ],
    )
    def test_just_below_floor_fails(self, kind, floor):
        assert meets_floor(kind, floor - 0.001) is False

    def test_text_needs_more_than_component(self):
        assert meets_floor(PairKind.COMPONENT, 4.0) is True
        assert meets_floor(PairKind.TEXT, 4.0) is False

    def test_info_always_passes_even_at_one(self):
        assert meets_floor(PairKind.INFO, 1.0) is True


class TestContrastPair:
    def test_defaults(self):
        pair = ContrastPair(fg="text", bg="background", kind=PairKind.TEXT)
        assert pair.over is None
        assert pair.note == ""

    def test_is_frozen(self):
        pair = ContrastPair(fg="a", bg="b", kind=PairKind.INFO)
        with pytest.raises(dataclasses.FrozenInstanceError):
            pair.fg = "c"


class TestIsValidColor:
    @pytest.mark.parametrize("value", ["#000000", "#FFFFFF", "#aBcDeF", "#80ffffff"])
    def test_accepts_six_and_eight_digits(self, value):
        assert is_valid_color(value) is True

    @pytest.mark.parametrize(
        "value",
        ["", "#", "000000", "#00000", "#0000000", "#000000000", "#gggggg", "#12 456"],
    )
    def test_rejects_malformed_text(self, value):
        assert is_valid_color(value) is False

    @pytest.mark.parametrize("value", [None, 0, 0xFFFFFF, b"#000000", ["#000000"]])
    def test_rejects_non_strings_without_raising(self, value):
        assert is_valid_color(value) is False

    def test_rejects_trailing_newline(self):
        # ``$`` alone would accept "#000000\n"; the colour must be exact.
        assert is_valid_color("#000000\n") is False


class TestParseColor:
    def test_six_digits_are_opaque(self):
        assert parse_color("#102030") == (0x10, 0x20, 0x30, 255)

    def test_eight_digits_put_alpha_first(self):
        # QColor("#78787890") is alpha 0x78, not 0x90.
        assert parse_color("#78787890") == (0x78, 0x78, 0x90, 0x78)

    def test_alpha_first_with_distinct_channels(self):
        assert parse_color("#01020304") == (2, 3, 4, 1)

    def test_case_insensitive(self):
        assert parse_color("#ABCDEF") == parse_color("#abcdef")

    def test_boundary_channels(self):
        assert parse_color("#000000") == (0, 0, 0, 255)
        assert parse_color("#ffffff") == (255, 255, 255, 255)
        assert parse_color("#00000000") == (0, 0, 0, 0)
        assert parse_color("#ffffffff") == (255, 255, 255, 255)

    @pytest.mark.parametrize("value", ["", "fff", "#fff", "#12345", "#zzzzzz", "x"])
    def test_malformed_raises_contrast_error(self, value):
        with pytest.raises(ContrastError):
            parse_color(value)

    def test_error_message_names_the_value(self):
        with pytest.raises(ContrastError, match="nope"):
            parse_color("nope")

    def test_trailing_newline_raises_contrast_error_not_a_bare_value_error(self):
        # Regression: the pattern ends in ``$``, which matches before a
        # final newline, so is_valid_color accepts "#000000<LF>" and parse_color
        # then dies in int("<LF>", 16) with a plain ValueError.
        with pytest.raises(ContrastError):
            parse_color("#000000\n")

    def test_contrast_error_is_a_value_error(self):
        assert issubclass(ContrastError, ValueError)

    @given(_CHANNEL, _CHANNEL, _CHANNEL, _CHANNEL)
    def test_round_trips_the_eight_digit_form(self, a, r, g, b):
        assert parse_color(f"#{a:02X}{r:02X}{g:02X}{b:02X}") == (r, g, b, a)


class TestRelativeLuminance:
    def test_white_is_one(self):
        assert relative_luminance("#ffffff") == pytest.approx(1.0)

    def test_black_is_zero(self):
        assert relative_luminance("#000000") == 0.0

    def test_pure_channels_use_the_wcag_weights(self):
        assert relative_luminance("#ff0000") == pytest.approx(0.2126)
        assert relative_luminance("#00ff00") == pytest.approx(0.7152)
        assert relative_luminance("#0000ff") == pytest.approx(0.0722)

    def test_linear_segment_below_the_knee(self):
        # 10/255 = 0.0392 <= 0.04045 -> c / 12.92 on every channel.
        assert relative_luminance("#0a0a0a") == pytest.approx((10 / 255) / 12.92)

    def test_power_segment_above_the_knee(self):
        c = 11 / 255
        expected = ((c + 0.055) / 1.055) ** 2.4
        assert relative_luminance("#0b0b0b") == pytest.approx(expected)

    def test_curve_is_continuous_across_the_knee(self):
        low, high = relative_luminance("#0a0a0a"), relative_luminance("#0b0b0b")
        assert 0 < high - low < 0.001

    def test_mid_grey(self):
        assert relative_luminance("#808080") == pytest.approx(0.2158, abs=1e-4)

    def test_translucent_colour_is_refused(self):
        with pytest.raises(ContrastError, match="translucent"):
            relative_luminance("#80ffffff")

    def test_malformed_colour_is_refused(self):
        with pytest.raises(ContrastError):
            relative_luminance("red")

    def test_fully_opaque_eight_digit_is_accepted(self):
        assert relative_luminance("#ffffffff") == pytest.approx(1.0)

    @given(_OPAQUE)
    def test_stays_within_unit_interval(self, colour):
        assert 0.0 <= relative_luminance(colour) <= 1.0


class TestComposite:
    def test_opaque_foreground_wins(self):
        assert composite("#123456", "#ffffff") == "#123456"

    def test_zero_alpha_shows_the_background(self):
        assert composite("#00ff0000", "#102030") == "#102030"

    def test_alpha_is_the_first_pair_of_digits(self):
        # 0x80 alpha black over white: ~50% grey. Read last-pair-as-alpha and
        # this would be an almost-opaque (alpha 0x00) or wrong colour.
        assert composite("#80000000", "#ffffff") == "#7f7f7f"

    def test_documented_example(self):
        # alpha 0x78, rgb (0x78, 0x78, 0x90) over white.
        assert composite("#78787890", "#ffffff") == "#bfbfcb"

    def test_rounds_half_up_not_down(self):
        # 200 * 200/255 = 156.86 -> 157 (truncation would give 156).
        assert composite("#c8c80000", "#000000") == "#9d0000"

    def test_result_is_lower_case_hash_six_digits(self):
        out = composite("#80ABCDEF", "#FFFFFF")
        assert out == out.lower() and len(out) == 7 and out.startswith("#")

    def test_translucent_background_is_refused(self):
        with pytest.raises(ContrastError, match="translucent"):
            composite("#ff0000", "#80ffffff")

    def test_malformed_foreground_is_refused(self):
        with pytest.raises(ContrastError):
            composite("red", "#ffffff")

    def test_malformed_background_is_refused(self):
        with pytest.raises(ContrastError):
            composite("#ffffff", "white")

    @given(_OPAQUE, _OPAQUE)
    def test_opaque_foreground_is_identity(self, fg, bg):
        assert composite(fg, bg) == fg

    @given(_OPAQUE, _OPAQUE)
    def test_zero_alpha_foreground_is_the_background(self, fg, bg):
        assert composite("#00" + fg[1:], bg) == bg

    @given(_TRANSLUCENT, _OPAQUE)
    def test_each_channel_lies_between_foreground_and_background(self, fg, bg):
        r, g, b, _ = parse_color(fg)
        out = parse_color(composite(fg, bg))
        under = parse_color(bg)
        for got, top, low in zip(out[:3], (r, g, b), under[:3]):
            assert min(top, low) <= got <= max(top, low)


class TestContrastRatio:
    def test_white_on_black_is_21(self):
        assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0)

    def test_black_on_white_is_21(self):
        assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)

    def test_identical_colours_are_one(self):
        assert contrast_ratio("#336699", "#336699") == pytest.approx(1.0)

    def test_known_value_just_passing_grey(self):
        assert contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)

    def test_known_value_just_failing_grey(self):
        assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)

    def test_known_value_pure_blue_on_white(self):
        assert contrast_ratio("#0000ff", "#ffffff") == pytest.approx(8.59, abs=0.01)

    def test_the_two_greys_straddle_the_text_floor(self):
        assert meets_floor(PairKind.TEXT, contrast_ratio("#767676", "#ffffff"))
        assert not meets_floor(PairKind.TEXT, contrast_ratio("#777777", "#ffffff"))

    def test_ratio_is_returned_unrounded(self):
        ratio = contrast_ratio("#767676", "#ffffff")
        assert ratio != round(ratio, 2)

    def test_translucent_foreground_is_composited_over_background(self):
        assert contrast_ratio("#80000000", "#ffffff") == pytest.approx(
            contrast_ratio("#7f7f7f", "#ffffff")
        )

    def test_translucent_foreground_zero_alpha_is_one(self):
        assert contrast_ratio("#00000000", "#336699") == pytest.approx(1.0)

    def test_translucent_background_without_over_is_refused(self):
        with pytest.raises(ContrastError, match="over"):
            contrast_ratio("#000000", "#80ffffff")

    def test_translucent_background_is_composited_over_over(self):
        expected = contrast_ratio("#000000", composite("#80ffffff", "#000000"))
        assert contrast_ratio("#000000", "#80ffffff", over="#000000") == (
            pytest.approx(expected)
        )

    def test_over_changes_the_result(self):
        on_black = contrast_ratio("#ffffff", "#80808080", over="#000000")
        on_white = contrast_ratio("#ffffff", "#80808080", over="#ffffff")
        assert on_black != pytest.approx(on_white)

    def test_over_is_ignored_for_an_opaque_background(self):
        assert contrast_ratio("#000000", "#ffffff", over="#ff0000") == pytest.approx(
            21.0
        )

    def test_translucent_over_is_refused(self):
        with pytest.raises(ContrastError, match="translucent"):
            contrast_ratio("#000000", "#80ffffff", over="#80000000")

    def test_translucent_foreground_on_composited_background(self):
        bg = composite("#80ffffff", "#000000")
        expected = contrast_ratio(composite("#80ff0000", bg), bg)
        got = contrast_ratio("#80ff0000", "#80ffffff", over="#000000")
        assert got == pytest.approx(expected)

    @pytest.mark.parametrize("fg,bg", [("x", "#ffffff"), ("#ffffff", "x")])
    def test_malformed_operand_is_refused(self, fg, bg):
        with pytest.raises(ContrastError):
            contrast_ratio(fg, bg)

    @given(_OPAQUE, _OPAQUE)
    def test_is_symmetric(self, a, b):
        assert contrast_ratio(a, b) == pytest.approx(contrast_ratio(b, a))

    @given(_OPAQUE, _OPAQUE)
    def test_lies_between_1_and_21(self, a, b):
        assert 1.0 <= contrast_ratio(a, b) <= 21.0 + 1e-9

    @given(_OPAQUE)
    def test_a_colour_against_itself_is_one(self, a):
        assert contrast_ratio(a, a) == pytest.approx(1.0)

    @given(_OPAQUE)
    def test_black_and_white_bound_every_colour(self, a):
        # No colour is further from white than black is, nor further from
        # black than white is.
        assert contrast_ratio(a, "#ffffff") <= contrast_ratio("#000000", "#ffffff")
        assert contrast_ratio(a, "#000000") <= contrast_ratio("#ffffff", "#000000")

    @given(_TRANSLUCENT, _OPAQUE)
    def test_translucent_foreground_equals_its_composite(self, fg, bg):
        assert contrast_ratio(fg, bg) == pytest.approx(
            contrast_ratio(composite(fg, bg), bg)
        )


def test_public_surface_is_exported():
    assert set(contrast.__all__) >= {
        "ContrastError",
        "PairKind",
        "ContrastPair",
        "parse_color",
        "is_valid_color",
        "relative_luminance",
        "composite",
        "contrast_ratio",
        "floor_for",
        "meets_floor",
    }
