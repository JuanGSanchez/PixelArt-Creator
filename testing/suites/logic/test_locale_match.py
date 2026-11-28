"""Tests for ``pixelart_creator.logic.locale_match`` (Qt-free).

Covers ``REQ-L10N-UI-002``: the system's preferred languages are walked in their
own order and the first entry that maps to a shipped language is installed;
English when none does. Every row of the requirement's table is one parametrized
case. A Traditional-script entry is *skipped* in the walk, never a stop: the
user's ruling of 2026-10-24 on that requirement.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import locale_match

SHIPPED = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

# The Traditional-script rows of the requirement's table.
TRADITIONAL_ROWS = ("zh_TW", "zh-HK", "zh_MO", "zh-Hant", "zh-Hant-TW")

# (system entry, installed language): one case per row of the table.
TABLE_ROWS = (
    ("fr", "fr"),
    ("fr_FR", "fr"),
    ("fr-CA", "fr"),
    ("fr_BE", "fr"),
    ("fr_CH", "fr"),
    ("de", "de"),
    ("de_DE", "de"),
    ("de-AT", "de"),
    ("de_CH", "de"),
    ("ru", "ru"),
    ("ru_RU", "ru"),
    ("zh", "zh_CN"),
    ("zh_CN", "zh_CN"),
    ("zh-Hans", "zh_CN"),
    ("zh-Hans-CN", "zh_CN"),
    ("zh_SG", "zh_CN"),
    ("zh_TW", "en"),
    ("zh-HK", "en"),
    ("zh_MO", "en"),
    ("zh-Hant", "en"),
    ("zh-Hant-TW", "en"),
    ("ko", "ko"),
    ("ko_KR", "ko"),
    ("ja", "ja"),
    ("ja_JP", "ja"),
    ("es", "es"),
    ("es_ES", "es"),
    ("es-MX", "es"),
    ("pt_BR", "en"),
    ("sv", "en"),
)


class TestTableRows:
    """Every row of the requirement's table maps to its installed language."""

    @pytest.mark.parametrize(("entry", "expected"), TABLE_ROWS)
    def test_row_maps_to_installed_language(self, entry, expected):
        """Map a single system entry to the language the table names."""
        assert locale_match.match_ui_language([entry], SHIPPED) == expected

    @pytest.mark.parametrize("entry", ["en", "en_US", "en-GB"])
    def test_english_entry_installs_english(self, entry):
        """Install English for an English entry."""
        assert locale_match.match_ui_language([entry], SHIPPED) == "en"


class TestWalk:
    """The list is walked in its own order; the first mapping entry wins."""

    def test_first_mapping_entry_wins(self):
        """Prefer the earlier of two entries that both map."""
        assert locale_match.match_ui_language(["ja_JP", "fr_FR"], SHIPPED) == "ja"

    def test_unshipped_entry_is_skipped(self):
        """Skip an entry that maps to nothing shipped and use the next one."""
        assert locale_match.match_ui_language(["pt_BR", "fr_FR"], SHIPPED) == "fr"

    def test_empty_list_installs_english(self):
        """Install English when the system list is empty."""
        assert locale_match.match_ui_language([], SHIPPED) == "en"

    def test_no_entry_maps_installs_english(self):
        """Install English when no entry maps."""
        assert locale_match.match_ui_language(["pt_BR", "sv"], SHIPPED) == "en"

    def test_accepts_any_sequence_type(self):
        """Accept a tuple as the preferred list."""
        assert locale_match.match_ui_language(("de_DE",), SHIPPED) == "de"

    def test_does_not_mutate_inputs(self):
        """Leave the preferred list and the available set untouched."""
        preferred = ["zh_TW", "fr_FR"]
        available = set(SHIPPED)
        locale_match.match_ui_language(preferred, available)
        assert preferred == ["zh_TW", "fr_FR"]
        assert available == set(SHIPPED)


class TestTraditionalScriptIsSkippedNeverAStop:
    """A Traditional-script entry is skipped; the walk goes on.

    Under the user's ruling of 2026-10-24 on the preferred-language requirement,
    Chinese written in Traditional script maps to nothing shipped, so it is passed
    over exactly like any other unshipped language. It does not end the walk.
    """

    @pytest.mark.parametrize("entry", TRADITIONAL_ROWS)
    def test_traditional_row_then_french_installs_french(self, entry):
        """Skip each Traditional row of the table and install the French after it."""
        assert locale_match.match_ui_language([entry, "fr_FR"], SHIPPED) == "fr"

    def test_traditional_hant_hk_then_japanese_installs_japanese(self):
        """Skip a script-and-territory Traditional entry and reach Japanese."""
        assert locale_match.match_ui_language(["zh-Hant-HK", "ja_JP"], SHIPPED) == "ja"

    def test_traditional_alone_installs_english(self):
        """Install English when the only entry is Traditional."""
        assert locale_match.match_ui_language(["zh_TW"], SHIPPED) == "en"

    def test_traditional_then_unshipped_installs_english(self):
        """Install English when a Traditional entry is followed by nothing shipped."""
        assert locale_match.match_ui_language(["zh_TW", "pt_BR"], SHIPPED) == "en"

    def test_explicit_simplified_script_wins_over_traditional_territory(self):
        """Read an explicit Simplified script as Simplified despite the territory."""
        assert locale_match.match_ui_language(["zh-Hans-TW"], SHIPPED) == "zh_CN"

    def test_traditional_script_with_simplified_territory_is_skipped(self):
        """Skip a Traditional script even when the territory is mainland China."""
        assert locale_match.match_ui_language(["zh-Hant-CN", "ko"], SHIPPED) == "ko"


class TestTraditionalScriptScenarioRows:
    """SC-L10N-UI-002-3: the six rows of the Traditional-script scenario.

    Each row is a two-entry preferred list. The Traditional-script first entry is
    skipped like an unshipped language and the second entry decides, which the user
    confirmed on 2026-10-24: a later Simplified entry is installed, and a
    Traditional script decides over a mainland territory.
    """

    @pytest.mark.parametrize(
        ("first", "second", "installed"),
        [
            ("zh_TW", "fr_FR", "fr"),
            ("zh-Hant", "ja_JP", "ja"),
            ("zh-HK", "de_DE", "de"),
            ("zh_MO", "pt_BR", "en"),
            ("zh-Hant-TW", "zh_CN", "zh_CN"),
            ("zh-Hant-CN", "ko", "ko"),
        ],
    )
    def test_traditional_entry_is_skipped_and_the_second_decides(
        self, first, second, installed
    ):
        """Install the language of the second entry after a skipped first one."""
        assert locale_match.match_ui_language([first, second], SHIPPED) == installed


class TestNormalisation:
    """Separators, case, encoding and modifier suffixes do not matter."""

    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ("FR_fr", "fr"),
            ("De-DE", "de"),
            ("ZH_cn", "zh_CN"),
            ("ZH-HANS-CN", "zh_CN"),
            ("ja_JP.UTF-8", "ja"),
            ("de_DE@euro", "de"),
            ("ko_KR.eucKR@x", "ko"),
            ("  fr_FR  ", "fr"),
            ("zh_TW.UTF-8", "en"),
        ],
    )
    def test_entry_is_normalised(self, entry, expected):
        """Ignore case, padding, encoding and modifier in an entry."""
        assert locale_match.match_ui_language([entry], SHIPPED) == expected

    @pytest.mark.parametrize("entry", ["", "   ", "-", "_", ".UTF-8", "@euro"])
    def test_blank_entry_maps_to_nothing(self, entry):
        """Skip an entry with no language subtag and use the next one."""
        assert locale_match.match_ui_language([entry, "ru"], SHIPPED) == "ru"

    def test_returns_the_available_codes_spelling(self):
        """Return the code as the catalogues spell it, not lower-cased."""
        assert locale_match.match_ui_language(["zh-Hans"], ["en", "zh_CN"]) == "zh_CN"


class TestAvailableCodes:
    """Only a language that really ships can be installed."""

    def test_language_not_available_installs_english(self):
        """Fall back to English when the matched language does not ship."""
        assert locale_match.match_ui_language(["fr_FR"], ["en", "es"]) == "en"

    def test_simplified_chinese_not_available_is_skipped(self):
        """Skip Chinese when the Simplified catalogue is absent."""
        assert locale_match.match_ui_language(["zh_CN", "de"], ["en", "de"]) == "de"

    def test_language_territory_code_matches_exactly(self):
        """Match a shipped language-and-territory code before the bare language."""
        available = ["en", "pt", "pt_BR"]
        assert locale_match.match_ui_language(["pt-BR"], available) == "pt_BR"

    def test_territory_falls_back_to_bare_language(self):
        """Fall back to the bare language when the territory code is not shipped."""
        assert locale_match.match_ui_language(["pt_PT"], ["en", "pt"]) == "pt"

    def test_accepts_any_collection_type(self):
        """Accept a frozenset as the available codes."""
        assert locale_match.match_ui_language(["ko"], frozenset(SHIPPED)) == "ko"


_CANONICAL_ENTRIES = (
    ("fr", "FR"),
    ("de", "AT"),
    ("ru",),
    ("zh",),
    ("zh", "CN"),
    ("zh", "Hans"),
    ("zh", "Hans", "CN"),
    ("zh", "SG"),
    ("zh", "TW"),
    ("zh", "HK"),
    ("zh", "MO"),
    ("zh", "Hant"),
    ("zh", "Hant", "TW"),
    ("ko", "KR"),
    ("ja", "JP"),
    ("es", "MX"),
    ("pt", "BR"),
)


@st.composite
def _spelling(draw):
    """Draw a canonical subtag tuple and one arbitrary spelling of it."""
    parts = draw(st.sampled_from(_CANONICAL_ENTRIES))
    text = ""
    for index, part in enumerate(parts):
        if index:
            text += draw(st.sampled_from(["-", "_"]))
        flips = draw(st.lists(st.booleans(), min_size=len(part), max_size=len(part)))
        text += "".join(
            char.upper() if flip else char.lower() for char, flip in zip(part, flips)
        )
    return parts, text


class TestSeparatorAndCaseInvariance:
    """Hyphen versus underscore and letter case never change the answer."""

    @given(_spelling())
    def test_any_spelling_matches_the_canonical_spelling(self, drawn):
        """Return the same code for every separator and case spelling of an entry."""
        parts, text = drawn
        canonical = "_".join(parts)
        assert locale_match.match_ui_language(
            [text], SHIPPED
        ) == locale_match.match_ui_language([canonical], SHIPPED)

    @given(_spelling(), st.lists(st.sampled_from(["fr", "pt_BR"]), max_size=2))
    def test_skip_or_choose_decision_is_independent_of_spelling(self, drawn, tail):
        """Keep the skip-or-stop decision of an entry independent of its spelling."""
        parts, text = drawn
        canonical = "_".join(parts)
        assert locale_match.match_ui_language(
            [text, *tail], SHIPPED
        ) == locale_match.match_ui_language([canonical, *tail], SHIPPED)

    @given(_spelling())
    def test_result_is_always_shipped(self, drawn):
        """Return only a shipped code, whatever the spelling."""
        _, text = drawn
        assert locale_match.match_ui_language([text], SHIPPED) in SHIPPED


# --- formatting_locale_name: numbers follow the interface language ----------------

# Every entry of the table above, with the shipped language it SELECTS (not the
# fallback it ends on): the rows that end on English only because nothing shipped
# matched (zh_TW, zh-HK, zh_MO, zh-Hant, zh-Hant-TW, pt_BR, sv) select nothing.
_NOT_SELECTING = frozenset(
    entry for entry, installed in TABLE_ROWS if installed == "en"
)
_SELECTS = {
    entry: (None if entry in _NOT_SELECTING else installed)
    for entry, installed in TABLE_ROWS
} | {"en": "en", "en_US": "en", "en-GB": "en"}


class TestFormattingLocaleNameScenarioRows:
    """The seven rows of the decision on the formatting locale."""

    @pytest.mark.parametrize(
        ("system", "language", "formatting"),
        [
            ("es_ES", "es", "es_ES"),
            ("es_ES", "fr", "fr"),
            ("es_ES", "en", "en"),
            ("en_GB", "en", "en_GB"),
            ("fr_CA", "fr", "fr_CA"),
            ("zh_TW", "zh_CN", "zh_CN"),
            ("ja_JP", "ko", "ko"),
        ],
    )
    def test_row_gives_the_formatting_locale_the_scenario_names(
        self, system, language, formatting
    ):
        """Choose the system's own locale or the language, as each row says."""
        chosen = locale_match.formatting_locale_name(system, language, SHIPPED)
        assert chosen == formatting


class TestFormattingLocaleNameControl:
    """A fallback is not a match: ``pt_BR`` is in none of the eight languages."""

    @pytest.mark.parametrize("language", SHIPPED)
    def test_pt_br_system_gives_each_language_itself(self, language):
        """Give the interface language, never ``pt_BR``, for every shipped language."""
        assert (
            locale_match.formatting_locale_name("pt_BR", language, SHIPPED) == language
        )

    def test_pt_br_with_english_gives_en_not_the_system_name(self):
        """Do not take English as a match for ``pt_BR`` because the walk falls to it."""
        assert locale_match.formatting_locale_name("pt_BR", "en", SHIPPED) == "en"

    @pytest.mark.parametrize("system", ["sv", "sv_SE", "it_IT", "zh_TW", "zh-Hant"])
    def test_system_in_no_shipped_language_gives_english_when_english_is_active(
        self, system
    ):
        """Give ``en`` for a system locale that maps to nothing shipped."""
        assert locale_match.formatting_locale_name(system, "en", SHIPPED) == "en"

    def test_traditional_script_system_with_simplified_chosen_gives_zh_cn(self):
        """Give ``zh_CN`` for a Traditional system, never the Traditional name."""
        chosen = locale_match.formatting_locale_name("zh-Hant-TW", "zh_CN", SHIPPED)
        assert chosen == "zh_CN"


class TestFormattingLocaleNameKeepsTheSystemName:
    """The system's name comes back exactly as given when it is in the language."""

    @pytest.mark.parametrize(
        ("system", "language"),
        [
            ("es-MX", "es"),
            ("fr_BE", "fr"),
            ("de_AT", "de"),
            ("en_US", "en"),
            ("ru_RU", "ru"),
            ("ko_KR", "ko"),
            ("ja_JP", "ja"),
            ("zh_SG", "zh_CN"),
            ("zh-Hans-CN", "zh_CN"),
            ("zh_CN", "zh_CN"),
        ],
    )
    def test_system_in_the_language_is_kept(self, system, language):
        """Keep the system locale's own name for a system in the active language."""
        assert locale_match.formatting_locale_name(system, language, SHIPPED) == system

    @pytest.mark.parametrize("system", ["FR_ca", "fr_CA.UTF-8", "  fr_FR  ", "fr-CA@x"])
    def test_system_name_is_returned_unnormalised(self, system):
        """Return the spelling the system gave, not a lower-cased or trimmed copy."""
        assert locale_match.formatting_locale_name(system, "fr", SHIPPED) == system

    @pytest.mark.parametrize("system", ["fr_FR", "de_DE", "ru_RU", "ja_JP", "ko_KR"])
    def test_other_language_active_gives_that_language(self, system):
        """Give the interface language when the system speaks another one."""
        assert locale_match.formatting_locale_name(system, "es", SHIPPED) == "es"


class TestFormattingLocaleNameAvailableCodes:
    """The mapping uses the catalogues that ship, as the startup match does."""

    def test_system_language_that_does_not_ship_is_not_a_match(self):
        """Give the language, not ``fr_CA``, when the French catalogue is absent."""
        chosen = locale_match.formatting_locale_name("fr_CA", "fr", ["en", "es"])
        assert chosen == "fr"

    def test_accepts_any_collection_type(self):
        """Accept a frozenset as the available codes."""
        chosen = locale_match.formatting_locale_name("de_AT", "de", frozenset(SHIPPED))
        assert chosen == "de_AT"

    def test_does_not_mutate_the_available_codes(self):
        """Leave the available set untouched."""
        available = set(SHIPPED)
        locale_match.formatting_locale_name("fr_CA", "fr", available)
        assert available == set(SHIPPED)

    def test_territory_code_that_ships_matches_exactly(self):
        """Keep ``pt_BR`` when ``pt_BR`` is itself the active shipped language."""
        chosen = locale_match.formatting_locale_name("pt-BR", "pt_BR", ["en", "pt_BR"])
        assert chosen == "pt-BR"


class TestFormattingLocaleNameProperties:
    """Invariants of the choice over every table entry and every language."""

    @pytest.mark.parametrize("language", SHIPPED)
    @pytest.mark.parametrize("system", sorted(_SELECTS))
    def test_choice_follows_the_table(self, system, language):
        """Keep the system name exactly when the table says it selects the language."""
        expected = system if _SELECTS[system] == language else language
        chosen = locale_match.formatting_locale_name(system, language, SHIPPED)
        assert chosen == expected

    @given(_spelling(), st.sampled_from(SHIPPED))
    def test_chosen_name_is_one_of_the_two_candidates(self, drawn, language):
        """Return the system name or the language, and nothing else."""
        _, text = drawn
        chosen = locale_match.formatting_locale_name(text, language, SHIPPED)
        assert chosen in (text, language)

    @given(_spelling(), st.sampled_from(SHIPPED))
    def test_any_spelling_decides_as_the_canonical_spelling_does(self, drawn, language):
        """Decide keep-or-replace alike for every separator and case spelling."""
        parts, text = drawn
        canonical = "_".join(parts)
        kept_text = locale_match.formatting_locale_name(text, language, SHIPPED) == text
        kept_canonical = (
            locale_match.formatting_locale_name(canonical, language, SHIPPED)
            == canonical
        )
        assert kept_text == kept_canonical

    @given(st.sampled_from(sorted(_SELECTS)), st.sampled_from(SHIPPED))
    def test_a_kept_name_selects_the_language_and_a_replaced_one_does_not(
        self, system, language
    ):
        """Keep the system name only for a system that selects the language."""
        chosen = locale_match.formatting_locale_name(system, language, SHIPPED)
        if chosen == system and system != language:
            assert _SELECTS[system] == language
        elif chosen == language and system != language:
            assert _SELECTS[system] != language
