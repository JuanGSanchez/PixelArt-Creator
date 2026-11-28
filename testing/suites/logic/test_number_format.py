"""Tests for ``pixelart_creator.logic.number_format`` (Qt-free).

Covers the rule for numbers and sizes in the interface language: in the French
and Russian interface a data size carries exactly one U+00A0 between the figure
and the unit, whatever separator Qt's locale data gave (U+0020, U+00A0 or
U+202F); in the other six languages Qt's own output stands. A decimal the app
writes into a translated message follows the formatting locale's decimal
separator without changing the message's own ``{n:.Nf}`` field.

Expected values come from the requirement and its scenarios, never from the
module's output. The code points are written out here on purpose, so a wrong
constant in the module cannot agree with its own test.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.number_format import LocaleDecimal, with_unit_space

NBSP = " "
SPACE = " "
NARROW_NBSP = " "

# The eight interface languages the product ships.
LANGUAGES = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")
# The two that carry the no-break space (the requirement on a number and its unit).
NBSP_LANGUAGES = ("fr", "ru")
OTHER_LANGUAGES = tuple(code for code in LANGUAGES if code not in NBSP_LANGUAGES)
# The three separators the scenario on leaked system formats says Qt might give.
SEPARATORS = (SPACE, NBSP, NARROW_NBSP)


class TestWithUnitSpaceFrenchAndRussian:
    """In fr and ru the one separator between the figure and the unit is U+00A0."""

    @pytest.mark.parametrize("language", NBSP_LANGUAGES)
    @pytest.mark.parametrize("separator", SEPARATORS)
    def test_any_qt_separator_becomes_no_break_space(self, language, separator):
        """Replace U+0020, U+00A0 and U+202F alike with one U+00A0."""
        assert with_unit_space(f"506,25{separator}MiB", language) == f"506,25{NBSP}MiB"

    def test_measured_french_case_gives_figure_nbsp_mio(self):
        """Turn Qt's measured U+0020 French size into 506,25, U+00A0, Mio."""
        assert with_unit_space("506,25 Mio", "fr") == "506,25" + NBSP + "Mio"

    def test_measured_french_case_has_no_plain_space_left(self):
        """Leave no U+0020 between the figure and the unit of the French size."""
        assert SPACE not in with_unit_space("506,25 Mio", "fr")

    def test_russian_latin_unit_gets_the_no_break_space(self):
        """Keep Qt's Latin MiB under Russian and join it to the figure with U+00A0."""
        assert with_unit_space("506,25 MiB", "ru") == "506,25" + NBSP + "MiB"

    def test_separator_already_no_break_space_stays(self):
        """Leave a U+00A0 separator as the one U+00A0."""
        assert with_unit_space("1,5" + NBSP + "Go", "fr") == "1,5" + NBSP + "Go"

    def test_integer_figure_is_joined_too(self):
        """Join a figure without a decimal part to its unit."""
        assert with_unit_space("512 Ko", "fr") == "512" + NBSP + "Ko"

    def test_only_the_separator_after_the_last_digit_changes(self):
        """Leave every other space of the text as it was."""
        assert with_unit_space("2 x 4 Mio", "fr") == "2 x 4" + NBSP + "Mio"

    def test_text_around_the_size_is_untouched(self):
        """Keep the sentence around the size as it was."""
        text = "Cette opération coûtera 506,25 Mio de données."
        expected = "Cette opération coûtera 506,25" + NBSP + "Mio de données."
        assert with_unit_space(text, "fr") == expected


class TestWithUnitSpaceOtherLanguages:
    """In the other six languages Qt's own output stands."""

    @pytest.mark.parametrize("language", OTHER_LANGUAGES)
    @pytest.mark.parametrize("separator", SEPARATORS)
    def test_text_comes_back_unchanged(self, language, separator):
        """Return the text exactly as given for each language outside fr and ru."""
        text = f"506.25{separator}MiB"
        assert with_unit_space(text, language) == text

    def test_german_keeps_its_plain_space(self):
        """Keep the U+0020 of a German size: only fr and ru are rewritten."""
        assert with_unit_space("506,25 MiB", "de") == "506,25 MiB"

    @pytest.mark.parametrize("language", ("ja", "zh_CN"))
    def test_japanese_and_chinese_stay_without_a_space(self, language):
        """Leave a size with no separator as it is in Japanese and Chinese."""
        assert with_unit_space("506.25MiB", language) == "506.25MiB"

    def test_the_eight_languages_are_all_examined(self):
        """Examine eight languages, as the scenario prints."""
        assert len(set(LANGUAGES)) == 8

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_only_fr_and_ru_change_a_qt_size(self, language):
        """Change the Qt-style size of exactly the two languages the rule names."""
        text = "506,25 MiB"
        changed = with_unit_space(text, language) != text
        assert changed == (language in NBSP_LANGUAGES)

    @pytest.mark.parametrize("language", ("", "FR", "xx", "fr-FR"))
    def test_unlisted_language_code_is_left_alone(self, language):
        """Return the text unchanged for a code that is not one of the eight."""
        assert with_unit_space("506,25 Mio", language) == "506,25 Mio"


class TestWithUnitSpaceNoSeparator:
    """With no separator between a figure and a unit the text is unchanged."""

    @pytest.mark.parametrize("language", NBSP_LANGUAGES)
    @pytest.mark.parametrize(
        "text",
        ["", "Mio", " Mio", "506,25", "506,25Mio", "Mio 506"],
        ids=[
            "empty",
            "no-digit",
            "no-digit-lead-space",
            "figure-only",
            "joined",
            "unit-first",
        ],
    )
    def test_text_comes_back_unchanged(self, language, text):
        """Return a text with no figure-space-unit shape as given."""
        assert with_unit_space(text, language) == text

    @pytest.mark.parametrize("language", NBSP_LANGUAGES)
    def test_digit_free_text_with_spaces_is_unchanged(self, language):
        """Leave every space of a text that holds no digit."""
        assert with_unit_space("pas de taille ici", language) == "pas de taille ici"


class TestWithUnitSpaceProperties:
    """Invariants of the rule over generated texts."""

    _text = st.text(
        alphabet=st.sampled_from(
            list("0123456789,.abMio-x") + [SPACE, NBSP, NARROW_NBSP]
        ),
        max_size=24,
    )
    _language = st.sampled_from(LANGUAGES + ("", "FR", "xx"))

    @given(_text, _language)
    def test_changes_at_most_one_character(self, text, language):
        """Keep the length and differ from the input in at most one position."""
        result = with_unit_space(text, language)
        assert len(result) == len(text)
        assert sum(a != b for a, b in zip(result, text)) <= 1

    @given(_text, st.sampled_from(OTHER_LANGUAGES + ("", "FR", "xx")))
    def test_never_changes_outside_fr_and_ru(self, text, language):
        """Return the input for any language other than fr and ru."""
        assert with_unit_space(text, language) == text

    @given(_text, st.sampled_from(NBSP_LANGUAGES))
    def test_a_changed_character_becomes_no_break_space_from_a_known_separator(
        self, text, language
    ):
        """Write only U+00A0, and only over U+0020 or U+202F."""
        result = with_unit_space(text, language)
        for before, after in zip(text, result):
            if before != after:
                assert after == NBSP
                assert before in (SPACE, NARROW_NBSP)

    @given(_text, _language)
    def test_second_application_changes_nothing(self, text, language):
        """Apply twice and get what one application gives."""
        once = with_unit_space(text, language)
        assert with_unit_space(once, language) == once

    @given(
        st.integers(min_value=0, max_value=10**9),
        st.sampled_from(SEPARATORS),
        st.sampled_from(["B", "Ko", "Mio", "MiB", "Go"]),
        st.sampled_from(NBSP_LANGUAGES),
    )
    def test_figure_separator_unit_is_joined_by_one_no_break_space(
        self, figure, separator, unit, language
    ):
        """Give figure, U+00A0, unit for every figure, separator and unit."""
        assert (
            with_unit_space(f"{figure}{separator}{unit}", language)
            == f"{figure}{NBSP}{unit}"
        )


class TestLocaleDecimalRendering:
    """A fixed-point rendering with the locale's decimal separator."""

    def test_comma_replaces_the_point(self):
        """Render 1.5 with two decimals and a comma as 1,50."""
        assert format(LocaleDecimal(1.5, ","), ".2f") == "1,50"

    def test_scale_of_the_real_size_preview_under_french(self):
        """Render a scale of 1.5 with a comma."""
        assert f"{LocaleDecimal(1.5, ','):.2f}" == "1,50"

    def test_point_keeps_the_english_rendering(self):
        """Render with a point as the point stands."""
        assert format(LocaleDecimal(1.5, "."), ".2f") == "1.50"

    def test_translated_message_keeps_its_own_field(self):
        """Fill a message's own {0:.2f} field with the locale's separator."""
        assert "Echelle {0:.2f}x".format(LocaleDecimal(2.25, ",")) == "Echelle 2,25x"

    def test_negative_value_keeps_its_sign(self):
        """Keep the minus sign in front of a negative figure."""
        assert format(LocaleDecimal(-0.5, ","), ".2f") == "-0,50"

    def test_no_digit_grouping_is_added(self):
        """Add no thousands separator to a large figure."""
        assert format(LocaleDecimal(1234567.891, ","), ".2f") == "1234567,89"

    def test_zero_decimals_has_no_separator(self):
        """Render a whole figure with no separator when no decimal is asked for."""
        assert format(LocaleDecimal(3.0, ","), ".0f") == "3"

    def test_rounds_as_fixed_point_formatting_rounds(self):
        """Round 2.675 as the fixed-point format of the float does: 2,67."""
        assert format(LocaleDecimal(2.675, ","), ".2f") == "2,67"

    def test_arabic_decimal_separator_is_accepted(self):
        """Use the Arabic decimal separator U+066B when the locale gives it."""
        assert format(LocaleDecimal(1.5, "٫"), ".1f") == "1٫5"

    @pytest.mark.parametrize("text", ["nan", "inf", "-inf"])
    def test_non_finite_values_render_as_python_renders_them(self, text):
        """Leave nan and the infinities without a separator to replace."""
        assert format(LocaleDecimal(float(text), ","), ".2f") == text

    def test_value_and_separator_are_kept_as_given(self):
        """Hold the two constructor arguments as value and decimal_point."""
        number = LocaleDecimal(1.5, ",")
        assert (number.value, number.decimal_point) == (1.5, ",")


class TestLocaleDecimalUnsupportedSpec:
    """A spec other than ``.Nf`` raises ``ValueError``, with no fallback."""

    @pytest.mark.parametrize(
        "spec",
        [
            "",
            "f",
            ".2",
            ".2e",
            ".2g",
            ".2%",
            "d",
            "s",
            "10.2f",
            ">8.2f",
            "+.2f",
            ",.2f",
            ".f",
            ".-1f",
        ],
    )
    def test_spec_is_refused(self, spec):
        """Refuse each spec that is not a fixed-point precision."""
        with pytest.raises(ValueError):
            format(LocaleDecimal(1.5, ","), spec)

    def test_f_string_with_no_spec_is_refused(self):
        """Refuse a bare ``{value}`` with no spec rather than print a default."""
        with pytest.raises(ValueError):
            f"{LocaleDecimal(1.5, ',')}"

    def test_unsupported_spec_is_refused_with_a_point_too(self):
        """Refuse an unsupported spec when the separator is the point as well."""
        with pytest.raises(ValueError):
            format(LocaleDecimal(1.5, "."), ".2e")


class TestLocaleDecimalProperties:
    """Invariants of the rendering over generated values."""

    _finite = st.floats(allow_nan=False, allow_infinity=False, width=64)
    _any = st.floats(width=64)
    _digits = st.integers(min_value=0, max_value=12)
    _separator = st.sampled_from([",", "٫"])

    @given(_any, _digits)
    def test_point_separator_equals_plain_format(self, value, digits):
        """Equal the plain fixed-point format when the separator is the point."""
        spec = f".{digits}f"
        assert format(LocaleDecimal(value, "."), spec) == format(value, spec)

    @given(_finite, _digits, _separator)
    def test_format_then_parse_round_trips(self, value, digits, separator):
        """Parse the rendering back, by undoing the separator, to the plain value."""
        spec = f".{digits}f"
        rendered = format(LocaleDecimal(value, separator), spec)
        parsed = float(rendered.replace(separator, "."))
        expected = float(format(value, spec))
        assert parsed == expected or (math.isnan(parsed) and math.isnan(expected))

    @given(_finite, st.integers(min_value=1, max_value=12), _separator)
    def test_separator_appears_once_and_no_point_remains(
        self, value, digits, separator
    ):
        """Show the locale's separator once and the ASCII point not at all."""
        rendered = format(LocaleDecimal(value, separator), f".{digits}f")
        assert rendered.count(separator) == 1
        assert "." not in rendered

    @given(_finite, _digits, _separator)
    def test_digits_are_those_of_the_plain_format(self, value, digits, separator):
        """Change nothing but the separator character."""
        spec = f".{digits}f"
        plain = format(value, spec)
        rendered = format(LocaleDecimal(value, separator), spec)
        assert rendered.replace(separator, ".") == plain
