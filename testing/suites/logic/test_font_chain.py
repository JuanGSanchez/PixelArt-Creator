# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tests for pixelart_creator.logic.font_chain (REQ-L10N-UI-012, no Qt).

Covers the family-list rule table (both values of ``primary_holds_cjk``), the
precedence invariant as a property, the endonym labels' own-form chains
(SC-L10N-UI-011-4 and SC-L10N-UI-012-2 at chain level) and the chain-tag
registry that keeps two lists with one first family apart in Qt's font cache.

Each invariant is paired with a deliberately broken copy (a "control") that must
fail it, so a check that cannot see the defect cannot pass unnoticed.
"""

from __future__ import annotations

import itertools
import string
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pixelart_creator.logic.font_chain as font_chain
import pixelart_creator.logic.language_names as language_names
from pixelart_creator.logic.font_chain import (
    CJK_HANGUL_FAMILY,
    CJK_JP_FAMILY,
    CJK_SC_FAMILY,
    NIFEN_ART_FAMILY,
    ChainTagRegistry,
    ChainTagsExhausted,
    family_chain,
    label_chain,
)

Chain = tuple[str, ...]

UI_LANGUAGES = tuple(language_names.ENDONYMS)
SYSTEM_LANGUAGES = (
    "",
    "_",
    "en",
    "en_US",
    "es",
    "fr_FR",
    "de-DE",
    "ru",
    "ja",
    "ja_JP",
    "ja-JP",
    "JA_jp",
    " ja ",
    "zh_CN",
    "zh-CN",
    "zh_TW",
    "zh-Hant",
    "ko",
    "ko_KR",
    "jaa",
)
PLATFORM_FAMILIES = ("Segoe UI", "Malgun Gothic")
# Nifen mode plus two distinct platform families standing in for two per-class fonts.
ROLE_PRIMARIES = (NIFEN_ART_FAMILY, *PLATFORM_FAMILIES)
HOLDS = (False, True)
CJK_NAMES = frozenset(
    name.casefold() for name in (CJK_SC_FAMILY, CJK_JP_FAMILY, CJK_HANGUL_FAMILY)
)
TAG_CAPACITY = 3


def _oracle_han(ui_language: str, system_language: str) -> str:
    """The Han family the rule table names, written out independently."""
    if ui_language == "ja":
        return CJK_JP_FAMILY
    if ui_language == "zh_CN":
        return CJK_SC_FAMILY
    subtag = system_language.strip().lower().replace("-", "_").split("_")[0]
    return CJK_JP_FAMILY if subtag == "ja" else CJK_SC_FAMILY


def _oracle_chain(
    primary: str, ui_language: str, system_language: str, holds: bool
) -> Chain:
    han = _oracle_han(ui_language, system_language)
    raw = (
        (han, CJK_HANGUL_FAMILY, primary, NIFEN_ART_FAMILY)
        if holds
        else (primary, NIFEN_ART_FAMILY, han, CJK_HANGUL_FAMILY)
    )
    seen: set[str] = set()
    out: list[str] = []
    for name in raw:
        if name.casefold() not in seen:
            seen.add(name.casefold())
            out.append(name)
    return tuple(out)


def _index(chain: Sequence[str], family: str) -> int:
    return [name.casefold() for name in chain].index(family.casefold())


def assert_precedence(chain: Sequence[str], primary: str, holds: bool) -> None:
    """No family declared CJK-holding precedes the CJK families in ``chain``."""
    han_index = min(
        _index(chain, name)
        for name in (CJK_SC_FAMILY, CJK_JP_FAMILY)
        if name.casefold() in [c.casefold() for c in chain]
    )
    hangul_index = _index(chain, CJK_HANGUL_FAMILY)
    if holds:
        primary_index = _index(chain, primary)
        assert (
            primary_index > han_index
        ), f"CJK-holding primary {primary!r} precedes the Han family in {chain}"
        assert (
            primary_index > hangul_index
        ), f"CJK-holding primary {primary!r} precedes the Hangul family in {chain}"


def all_chains() -> list[tuple[Chain, str, bool]]:
    """Every list ``family_chain`` and ``label_chain`` can produce, with its inputs."""
    found: list[tuple[Chain, str, bool]] = []
    for primary, holds in itertools.product(ROLE_PRIMARIES, HOLDS):
        for ui, system in itertools.product(UI_LANGUAGES, SYSTEM_LANGUAGES):
            found.append((family_chain(primary, ui, system, holds), primary, holds))
        for label in UI_LANGUAGES:
            found.append((label_chain(primary, label, holds), primary, holds))
    return found


# --------------------------------------------------------------------------- #
# The rule table
# --------------------------------------------------------------------------- #


class TestFamilyChainRows:
    """Every row of the chain table, false and true column, Nifen mode included."""

    @pytest.mark.parametrize(
        ("ui", "system", "han"),
        [
            ("ja", "en", CJK_JP_FAMILY),
            ("ja", "zh_CN", CJK_JP_FAMILY),
            ("zh_CN", "ja_JP", CJK_SC_FAMILY),
            ("zh_CN", "en", CJK_SC_FAMILY),
            ("en", "ja", CJK_JP_FAMILY),
            ("fr", "ja_JP", CJK_JP_FAMILY),
            ("ko", "ja-JP", CJK_JP_FAMILY),
            ("ko", "zh_CN", CJK_SC_FAMILY),
            ("de", "en_US", CJK_SC_FAMILY),
            ("ru", "", CJK_SC_FAMILY),
            ("es", "ko_KR", CJK_SC_FAMILY),
        ],
    )
    def test_han_form_follows_the_rule(self, ui: str, system: str, han: str) -> None:
        platform = "Segoe UI"
        assert family_chain(platform, ui, system, False) == (
            platform,
            NIFEN_ART_FAMILY,
            han,
            CJK_HANGUL_FAMILY,
        )
        assert family_chain(platform, ui, system, True) == (
            han,
            CJK_HANGUL_FAMILY,
            platform,
            NIFEN_ART_FAMILY,
        )

    def test_platform_primary_false_column_is_platform_first(self) -> None:
        assert family_chain("Segoe UI", "en", "en", False) == (
            "Segoe UI",
            "Nifen Art",
            "Nifen Art CJK SC",
            "Nifen Art CJK KR",
        )

    def test_platform_primary_true_column_is_cjk_first(self) -> None:
        assert family_chain("Malgun Gothic", "ja", "ja", True) == (
            "Nifen Art CJK JP",
            "Nifen Art CJK KR",
            "Malgun Gothic",
            "Nifen Art",
        )

    def test_nifen_mode_false_lists_nifen_art_once(self) -> None:
        assert family_chain(NIFEN_ART_FAMILY, "zh_CN", "en", False) == (
            "Nifen Art",
            "Nifen Art CJK SC",
            "Nifen Art CJK KR",
        )
        assert family_chain(NIFEN_ART_FAMILY, "ja", "en", False) == (
            "Nifen Art",
            "Nifen Art CJK JP",
            "Nifen Art CJK KR",
        )

    def test_nifen_mode_true_lists_nifen_art_once(self) -> None:
        assert family_chain(NIFEN_ART_FAMILY, "zh_CN", "en", True) == (
            "Nifen Art CJK SC",
            "Nifen Art CJK KR",
            "Nifen Art",
        )

    def test_primary_repeat_is_dropped_case_insensitively(self) -> None:
        assert family_chain("nifen art", "en", "en", False) == (
            "nifen art",
            "Nifen Art CJK SC",
            "Nifen Art CJK KR",
        )
        assert family_chain("NIFEN ART", "en", "en", True) == (
            "Nifen Art CJK SC",
            "Nifen Art CJK KR",
            "NIFEN ART",
        )

    @pytest.mark.parametrize("primary", ROLE_PRIMARIES)
    @pytest.mark.parametrize("holds", HOLDS)
    def test_every_row_matches_the_independent_oracle(
        self, primary: str, holds: bool
    ) -> None:
        for ui, system in itertools.product(UI_LANGUAGES, SYSTEM_LANGUAGES):
            assert family_chain(primary, ui, system, holds) == _oracle_chain(
                primary, ui, system, holds
            ), (primary, ui, system, holds)

    @pytest.mark.parametrize("system", ["", "_", "-", "   "])
    def test_blank_system_language_gives_simplified(self, system: str) -> None:
        assert family_chain("Segoe UI", "en", system, False)[2] == CJK_SC_FAMILY

    @pytest.mark.parametrize("system", ["ja", "ja_JP", "ja-JP", "JA_jp", " ja "])
    def test_japanese_system_tag_spellings_give_japanese(self, system: str) -> None:
        assert family_chain("Segoe UI", "en", system, False)[2] == CJK_JP_FAMILY

    def test_primary_subtag_must_be_exactly_ja(self) -> None:
        assert family_chain("Segoe UI", "en", "jaa", False)[2] == CJK_SC_FAMILY

    def test_ui_language_wins_over_system_language(self) -> None:
        assert family_chain("X", "zh_CN", "ja_JP", False)[2] == CJK_SC_FAMILY
        assert family_chain("X", "ja", "zh_CN", False)[2] == CJK_JP_FAMILY

    def test_hangul_family_is_always_present_after_the_han_family(self) -> None:
        for chain, _primary, _holds in all_chains():
            lowered = [name.casefold() for name in chain]
            assert lowered.count(CJK_HANGUL_FAMILY.casefold()) == 1
            han = [
                n
                for n in lowered
                if n in (CJK_SC_FAMILY.casefold(), CJK_JP_FAMILY.casefold())
            ]
            assert len(han) == 1
            assert lowered.index(han[0]) < lowered.index(CJK_HANGUL_FAMILY.casefold())

    def test_inactive_form_family_is_never_in_the_chain(self) -> None:
        """SC-L10N-UI-011-4 at chain level: no borrowing of the other form set."""
        for chain, _primary, _holds in all_chains():
            assert not ({CJK_SC_FAMILY, CJK_JP_FAMILY} <= set(chain))
        for primary, holds, system in itertools.product(
            ROLE_PRIMARIES, HOLDS, SYSTEM_LANGUAGES
        ):
            assert CJK_JP_FAMILY not in family_chain(primary, "zh_CN", system, holds)
            assert CJK_SC_FAMILY not in family_chain(primary, "ja", system, holds)

    def test_chain_is_a_tuple(self) -> None:
        assert isinstance(family_chain("X", "en", "en", False), tuple)


class TestFamilyChainErrors:
    @pytest.mark.parametrize("primary", ["", "   ", "\t\n"])
    def test_blank_role_primary_raises_value_error(self, primary: str) -> None:
        with pytest.raises(ValueError, match="role_primary"):
            family_chain(primary, "en", "en", False)

    @pytest.mark.parametrize("ui", ["xx", "", "ja_JP", "EN", "zh"])
    def test_unshipped_ui_language_raises_unknown_language(self, ui: str) -> None:
        with pytest.raises(language_names.UnknownLanguageError):
            family_chain("Segoe UI", ui, "en", False)

    def test_label_chain_unshipped_language_raises(self) -> None:
        with pytest.raises(language_names.UnknownLanguageError):
            label_chain("Segoe UI", "tlh", False)

    def test_label_chain_blank_primary_raises(self) -> None:
        with pytest.raises(ValueError, match="role_primary"):
            label_chain("", "ja", True)


# --------------------------------------------------------------------------- #
# The precedence invariant
# --------------------------------------------------------------------------- #

_PRIMARY_NAMES = st.text(
    alphabet=string.ascii_letters + string.digits + " -", min_size=1, max_size=20
).filter(lambda s: bool(s.strip()) and s.casefold() not in CJK_NAMES)
_SYSTEM_TAGS = st.text(alphabet=string.ascii_letters + "_- ", max_size=12)


def _platform_first_copy(primary: str, ui: str, system: str, holds: bool) -> Chain:
    """Broken copy: the platform-first order whatever the primary holds."""
    del holds
    return family_chain(primary, ui, system, False)


class TestPrecedenceInvariant:
    @given(
        primary=_PRIMARY_NAMES,
        ui=st.sampled_from(UI_LANGUAGES),
        system=_SYSTEM_TAGS,
        holds=st.booleans(),
    )
    def test_no_cjk_holding_family_precedes_the_cjk_families(
        self, primary: str, ui: str, system: str, holds: bool
    ) -> None:
        chain = family_chain(primary, ui, system, holds)
        assert_precedence(chain, primary, holds)
        # The only other family that may stand ahead of a CJK family is Nifen Art.
        first_cjk = min(
            i for i, name in enumerate(chain) if name.casefold() in CJK_NAMES
        )
        for name in chain[:first_cjk]:
            assert name == primary or name == NIFEN_ART_FAMILY
        assert len({n.casefold() for n in chain}) == len(chain)

    def test_holds_true_puts_primary_after_both_cjk_families_for_every_chain(
        self,
    ) -> None:
        for primary, ui, system in itertools.product(
            ROLE_PRIMARIES, UI_LANGUAGES, SYSTEM_LANGUAGES
        ):
            assert_precedence(family_chain(primary, ui, system, True), primary, True)

    def test_label_chain_obeys_the_invariant_for_every_label(self) -> None:
        for primary, label in itertools.product(ROLE_PRIMARIES, UI_LANGUAGES):
            assert_precedence(label_chain(primary, label, True), primary, True)

    def test_control_platform_first_copy_fails_the_invariant(self) -> None:
        """The broken order must trip the same assertion the real one passes."""
        for primary, ui, system in itertools.product(
            PLATFORM_FAMILIES, UI_LANGUAGES, SYSTEM_LANGUAGES
        ):
            with pytest.raises(AssertionError, match="precedes the Han family"):
                assert_precedence(
                    _platform_first_copy(primary, ui, system, True), primary, True
                )

    def test_control_checker_accepts_the_false_column_when_not_holding(self) -> None:
        chain = _platform_first_copy("Segoe UI", "en", "en", False)
        assert_precedence(chain, "Segoe UI", False)


# --------------------------------------------------------------------------- #
# Labels (SC-L10N-UI-011-4, SC-L10N-UI-012-2 at chain level)
# --------------------------------------------------------------------------- #

ACTIVE_LANGUAGES_012_2 = ("en", "es", "fr", "de", "ru", "zh_CN", "ko")


def _han_count(text: str) -> int:
    return sum(
        1 for ch in text if unicodedata.name(ch, "").startswith("CJK UNIFIED IDEOGRAPH")
    )


class TestLabelChain:
    @pytest.mark.parametrize("primary", ROLE_PRIMARIES)
    @pytest.mark.parametrize("holds", HOLDS)
    @pytest.mark.parametrize("label", UI_LANGUAGES)
    def test_equals_family_chain_with_label_language_as_both_languages(
        self, primary: str, holds: bool, label: str
    ) -> None:
        assert label_chain(primary, label, holds) == family_chain(
            primary, label, label, holds
        )

    @pytest.mark.parametrize("holds", HOLDS)
    def test_zh_cn_label_holds_simplified_and_never_japanese(self, holds: bool) -> None:
        for primary in ROLE_PRIMARIES:
            chain = label_chain(primary, "zh_CN", holds)
            assert CJK_SC_FAMILY in chain
            assert CJK_JP_FAMILY not in chain

    @pytest.mark.parametrize("holds", HOLDS)
    def test_ja_label_holds_japanese_and_never_simplified(self, holds: bool) -> None:
        for primary in ROLE_PRIMARIES:
            chain = label_chain(primary, "ja", holds)
            assert CJK_JP_FAMILY in chain
            assert CJK_SC_FAMILY not in chain

    @pytest.mark.parametrize("active", ACTIVE_LANGUAGES_012_2 + ("ja",))
    @pytest.mark.parametrize("holds", HOLDS)
    def test_sc_l10n_ui_012_2_each_label_keeps_its_own_forms(
        self, active: str, holds: bool
    ) -> None:
        """SC-L10N-UI-012-2 at chain level, one case per scenario Example.

        Whatever language is active (and whatever the system language is), the
        label "简体中文" carries the Simplified family and "日本語" the Japanese one.
        """
        sc_label_language = _language_of("简体中文")
        jp_label_language = _language_of("日本語")
        for system in SYSTEM_LANGUAGES:
            for primary in ROLE_PRIMARIES:
                # The active language's own role chain follows the rule table...
                role_chain = family_chain(primary, active, system, holds)
                assert _oracle_han(active, system) in role_chain
                # ...while a label chain never follows the active language.
                sc_chain = label_chain(primary, sc_label_language, holds)
                jp_chain = label_chain(primary, jp_label_language, holds)
                assert CJK_SC_FAMILY in sc_chain and CJK_JP_FAMILY not in sc_chain
                assert CJK_JP_FAMILY in jp_chain and CJK_SC_FAMILY not in jp_chain
                assert (sc_chain, jp_chain) == (
                    label_chain(primary, "zh_CN", holds),
                    label_chain(primary, "ja", holds),
                )

    def test_sc_l10n_ui_012_2_examines_seven_han_characters(self) -> None:
        count = _han_count("简体中文") + _han_count("日本語")
        print(f"SC-L10N-UI-012-2 Han characters examined: {count}")
        assert count == 7

    def test_the_two_han_labels_differ_only_in_the_form_family(self) -> None:
        for primary, holds in itertools.product(ROLE_PRIMARIES, HOLDS):
            sc = label_chain(primary, "zh_CN", holds)
            jp = label_chain(primary, "ja", holds)
            swapped = tuple(CJK_JP_FAMILY if n == CJK_SC_FAMILY else n for n in sc)
            assert swapped == jp

    def test_the_other_six_labels_use_the_default_simplified_slot(self) -> None:
        for label in ("en", "es", "fr", "de", "ru", "ko"):
            assert CJK_SC_FAMILY in label_chain("Segoe UI", label, False)
            assert CJK_JP_FAMILY not in label_chain("Segoe UI", label, False)


def _language_of(endonym: str) -> str:
    matches = [
        code for code, name in language_names.ENDONYMS.items() if name == endonym
    ]
    assert len(matches) == 1
    return matches[0]


# --------------------------------------------------------------------------- #
# The chain tag registry
# --------------------------------------------------------------------------- #


class TestRegistryConstruction:
    def test_negative_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            ChainTagRegistry(-1)

    def test_zero_capacity_is_allowed(self) -> None:
        registry = ChainTagRegistry(0)
        assert registry.tag_for(["A"]) is None
        with pytest.raises(ChainTagsExhausted):
            registry.tag_for(["A", "B"])


class TestRegistryTags:
    def test_first_list_gets_tag_one_then_two(self) -> None:
        registry = ChainTagRegistry(3)
        assert registry.tag_for(["A", "B"]) == 1
        assert registry.tag_for(["A", "C"]) == 2

    def test_same_list_gets_same_tag(self) -> None:
        registry = ChainTagRegistry(3)
        first = registry.tag_for(["A", "B", "C"])
        registry.tag_for(["A", "D"])
        assert registry.tag_for(("A", "B", "C")) == first

    def test_case_variants_of_a_name_share_the_tag(self) -> None:
        registry = ChainTagRegistry(3)
        first = registry.tag_for(["Nifen Art", "Nifen Art CJK SC"])
        assert registry.tag_for(["NIFEN ART", "nifen art cjk sc"]) == first
        assert registry.tag_for(["nifen art", "Nifen Art CJK sc"]) == first

    def test_different_lists_behind_one_first_family_differ(self) -> None:
        registry = ChainTagRegistry(3)
        tags = {
            registry.tag_for(["A", "B"]),
            registry.tag_for(["A", "C"]),
            registry.tag_for(["A", "B", "C"]),
        }
        assert tags == {1, 2, 3}

    def test_equal_length_tails_get_different_tags(self) -> None:
        registry = ChainTagRegistry(3)
        assert registry.tag_for(["A", "SC", "KR"]) != registry.tag_for(
            ["A", "JP", "KR"]
        )

    def test_different_length_lists_get_different_tags(self) -> None:
        registry = ChainTagRegistry(3)
        assert registry.tag_for(["A", "B"]) != registry.tag_for(["A", "B", "C"])

    def test_first_families_are_allocated_independently(self) -> None:
        registry = ChainTagRegistry(2)
        assert registry.tag_for(["A", "x"]) == 1
        assert registry.tag_for(["A", "y"]) == 2
        assert registry.tag_for(["B", "x"]) == 1
        assert registry.tag_for(["b", "y"]) == 2

    def test_tags_stay_inside_one_to_capacity(self) -> None:
        registry = ChainTagRegistry(5)
        tags = [registry.tag_for(["A", str(i)]) for i in range(5)]
        assert tags == [1, 2, 3, 4, 5]

    def test_list_order_matters(self) -> None:
        registry = ChainTagRegistry(3)
        assert registry.tag_for(["A", "B", "C"]) != registry.tag_for(["A", "C", "B"])


class TestRegistryOneFamilyRule:
    def test_one_family_list_gets_none(self) -> None:
        assert ChainTagRegistry(3).tag_for(["Nifen Art"]) is None

    def test_case_variants_and_tuples_of_one_family_get_none(self) -> None:
        registry = ChainTagRegistry(3)
        for spelling in (["Nifen Art"], ["nifen art"], ("NIFEN ART",)):
            assert registry.tag_for(spelling) is None

    def test_one_family_list_behind_a_first_family_that_has_chains_gets_none(
        self,
    ) -> None:
        registry = ChainTagRegistry(3)
        chain_tag = registry.tag_for(["Nifen Art", "Nifen Art CJK SC"])
        assert registry.tag_for(["Nifen Art"]) is None
        assert chain_tag == 1

    def test_one_family_lists_spend_no_capacity(self) -> None:
        registry = ChainTagRegistry(1)
        for name in ("A", "a", "B", "C", "A"):
            assert registry.tag_for([name]) is None
        assert registry.tag_for(["A", "x"]) == 1  # not exhausted by the above

    def test_one_family_list_never_shares_a_tag_with_a_chain(self) -> None:
        registry = ChainTagRegistry(3)
        chain_tag = registry.tag_for(["A", "B"])
        assert registry.tag_for(["A"]) != chain_tag

    @given(
        names=st.lists(
            st.sampled_from(["A", "a", "B", "Nifen Art", "nifen art"]),
            min_size=2,
            max_size=6,
        )
    )
    def test_property_two_or_more_families_are_never_none(
        self, names: list[str]
    ) -> None:
        registry = ChainTagRegistry(len(names) + 1)
        assert registry.tag_for(names) is not None

    def test_tail_length_is_not_used(self) -> None:
        registry = ChainTagRegistry(3)
        # A two-family list has a one-name tail and is still tagged; a longer
        # tail does not get a different class of tag from it.
        short = registry.tag_for(["A", "x"])
        long_ = registry.tag_for(["A", "x", "y", "z"])
        assert short is not None and long_ is not None
        assert short != long_


class TestRegistryExhaustion:
    def test_capacity_plus_one_raises_naming_the_family(self) -> None:
        registry = ChainTagRegistry(2)
        registry.tag_for(["Nifen Art", "a"])
        registry.tag_for(["Nifen Art", "b"])
        with pytest.raises(ChainTagsExhausted) as caught:
            registry.tag_for(["Nifen Art", "c"])
        assert caught.value.family == "Nifen Art"
        assert caught.value.capacity == 2
        assert "'Nifen Art'" in str(caught.value)
        assert "2" in str(caught.value)

    def test_exhaustion_is_a_runtime_error(self) -> None:
        assert issubclass(ChainTagsExhausted, RuntimeError)

    def test_known_lists_keep_their_tags_after_exhaustion(self) -> None:
        registry = ChainTagRegistry(1)
        assert registry.tag_for(["A", "x"]) == 1
        with pytest.raises(ChainTagsExhausted):
            registry.tag_for(["A", "y"])
        assert registry.tag_for(["a", "X"]) == 1
        with pytest.raises(ChainTagsExhausted):  # still refused, nothing was stored
            registry.tag_for(["A", "y"])

    def test_other_first_families_are_not_affected(self) -> None:
        registry = ChainTagRegistry(1)
        registry.tag_for(["A", "x"])
        with pytest.raises(ChainTagsExhausted):
            registry.tag_for(["A", "y"])
        assert registry.tag_for(["B", "y"]) == 1

    def test_one_family_list_is_fine_when_the_family_is_exhausted(self) -> None:
        registry = ChainTagRegistry(1)
        registry.tag_for(["A", "x"])
        assert registry.tag_for(["A"]) is None


class TestRegistryInputErrors:
    @pytest.mark.parametrize("empty", [[], ()])
    def test_empty_list_raises_value_error(self, empty: Sequence[str]) -> None:
        with pytest.raises(ValueError, match="empty"):
            ChainTagRegistry(3).tag_for(empty)

    @pytest.mark.parametrize("text", ["Nifen Art", "", "ab"])
    def test_a_bare_string_raises_type_error(self, text: str) -> None:
        with pytest.raises(TypeError):
            ChainTagRegistry(3).tag_for(text)


_REGISTRY_NAMES = st.sampled_from(["A", "a", "B", "C", "Nifen Art", "NIFEN ART", "x"])
_REGISTRY_LISTS = st.lists(
    st.lists(_REGISTRY_NAMES, min_size=1, max_size=4), min_size=1, max_size=12
)


class TestRegistryProperties:
    @given(lists=_REGISTRY_LISTS)
    def test_stable_injective_per_first_family_and_in_range(
        self, lists: list[list[str]]
    ) -> None:
        capacity = len(lists)
        registry = ChainTagRegistry(capacity)
        seen: dict[tuple[str, ...], int | None] = {}
        for names in lists + lists:  # second pass checks stability
            tag = registry.tag_for(names)
            key = tuple(n.casefold() for n in names)
            if key in seen:
                assert tag == seen[key]
            seen[key] = tag
            if len(names) == 1:
                assert tag is None
            else:
                assert tag is not None and 1 <= tag <= capacity
        by_first: dict[str, dict[int, tuple[str, ...]]] = defaultdict(dict)
        for key, tag in seen.items():
            if tag is None:
                continue
            owner = by_first[key[0]].setdefault(tag, key)
            assert owner == key, f"{owner} and {key} share tag {tag}"


# --------------------------------------------------------------------------- #
# Injectivity over the real chain set, with controls
# --------------------------------------------------------------------------- #


class _FirstFamilyOnlyRegistry:
    """Broken copy: keys on the first family only (Qt's measured cache behaviour)."""

    def __init__(self, capacity: int) -> None:
        self._tags: dict[str, int] = {}

    def tag_for(self, families: Sequence[str]) -> int | None:
        if len(families) == 1:
            return None
        return self._tags.setdefault(families[0].casefold(), len(self._tags) + 1)


class _TagsOneFamilyListsRegistry(ChainTagRegistry):
    """Broken copy: gives one-family lists a tag and spends capacity on them."""

    def tag_for(self, families: Sequence[str]) -> int | None:
        if len(families) == 1:
            first = families[0].casefold()
            table = self._by_first.setdefault(first, {})
            key = (first,)
            if key not in table:
                table[key] = len(table) + 1
            return table[key]
        return super().tag_for(families)


class _TailLengthRegistry:
    """Broken copy: the tag is the tail length."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity

    def tag_for(self, families: Sequence[str]) -> int | None:
        return len(families) - 1 or None


class _FirstListUntaggedRegistry:
    """Broken copy: leaves the first list behind each first family untagged."""

    def __init__(self, capacity: int) -> None:
        self._inner = ChainTagRegistry(capacity)
        self._seen: dict[str, tuple[str, ...]] = {}

    def tag_for(self, families: Sequence[str]) -> int | None:
        first = families[0].casefold()
        key = tuple(f.casefold() for f in families)
        if self._seen.setdefault(first, key) == key:
            return None
        return self._inner.tag_for(families)


class Tagger(Protocol):
    """Anything that hands out chain tags, real or a broken copy."""

    def tag_for(self, families: Sequence[str]) -> int | None: ...


def _distinct_lists() -> list[Chain]:
    unique: dict[tuple[str, ...], Chain] = {}
    for chain, _primary, _holds in all_chains():
        unique.setdefault(tuple(n.casefold() for n in chain), chain)
    return list(unique.values())


def injectivity_violations(
    registry: Tagger, chains: Sequence[Chain]
) -> list[tuple[Chain, Chain]]:
    """Pairs that break "equal lists share a tag, different lists behind one first
    family never do"."""
    tag_for = registry.tag_for
    tagged = [(chain, tag_for(chain)) for chain in chains]
    bad: list[tuple[Chain, Chain]] = []
    for (a, tag_a), (b, tag_b) in itertools.combinations(tagged, 2):
        same_list = [n.casefold() for n in a] == [n.casefold() for n in b]
        same_first = a[0].casefold() == b[0].casefold()
        if same_list and tag_a != tag_b:
            bad.append((a, b))
        elif same_first and not same_list and tag_a == tag_b:
            bad.append((a, b))
    return bad


def untagged_chain_violations(registry: Tagger, chains: Sequence[Chain]) -> list[Chain]:
    """Lists of two or more families that were given no tag."""
    return [c for c in chains if len(c) >= 2 and registry.tag_for(c) is None]


def one_family_violations(registry: Tagger, lists: Sequence[Chain]) -> list[Chain]:
    """One-family lists that were given a tag, or share one with a chain."""
    return [c for c in lists if len(c) == 1 and registry.tag_for(c) is not None]


def _is_nifen_mode(chain: Chain) -> bool:
    return chain[0] == NIFEN_ART_FAMILY or NIFEN_ART_FAMILY in chain[:3]


class TestRealChainSet:
    def test_every_produced_list_is_tagged_injectively(self) -> None:
        chains = _distinct_lists()
        registry = ChainTagRegistry(TAG_CAPACITY)
        assert injectivity_violations(registry, chains) == []

    def test_largest_number_of_lists_behind_one_first_family_is_printed_and_bounded(
        self,
    ) -> None:
        behind: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for chain in _distinct_lists():
            behind[chain[0].casefold()].add(tuple(n.casefold() for n in chain))
        largest = max(len(lists) for lists in behind.values())
        print(
            "largest number of lists behind one first family:",
            largest,
            {family: len(lists) for family, lists in sorted(behind.items())},
        )
        assert largest <= TAG_CAPACITY

    def test_no_chain_gets_none_and_one_family_lists_do(self) -> None:
        registry = ChainTagRegistry(TAG_CAPACITY)
        chains = _distinct_lists()
        alone = [(primary,) for primary in ROLE_PRIMARIES]
        assert untagged_chain_violations(registry, chains) == []
        assert one_family_violations(registry, alone) == []
        for chain in chains:
            assert len(chain) >= 2
            assert registry.tag_for(chain) is not None
            assert registry.tag_for((chain[0],)) is None

    def test_a_one_family_list_and_a_chain_never_share_a_tag(self) -> None:
        registry = ChainTagRegistry(TAG_CAPACITY)
        for chain in _distinct_lists():
            assert registry.tag_for(chain) != registry.tag_for((chain[0],))

    def test_the_two_nifen_mode_han_chains_get_different_tags(self) -> None:
        registry = ChainTagRegistry(TAG_CAPACITY)
        sc = registry.tag_for(family_chain(NIFEN_ART_FAMILY, "zh_CN", "en", False))
        jp = registry.tag_for(family_chain(NIFEN_ART_FAMILY, "ja", "en", False))
        assert sc != jp

    def test_the_two_platform_han_chains_get_different_tags(self) -> None:
        registry = ChainTagRegistry(TAG_CAPACITY)
        sc = registry.tag_for(family_chain("Segoe UI", "zh_CN", "en", False))
        jp = registry.tag_for(family_chain("Segoe UI", "ja", "en", False))
        assert sc != jp

    def test_two_cjk_holding_platform_families_get_different_tags(self) -> None:
        registry = ChainTagRegistry(TAG_CAPACITY)
        one = registry.tag_for(family_chain("Segoe UI", "ja", "ja", True))
        other = registry.tag_for(family_chain("Malgun Gothic", "ja", "ja", True))
        assert one != other


class TestControls:
    def test_control_first_family_only_registry_fails_injectivity(self) -> None:
        broken = _FirstFamilyOnlyRegistry(TAG_CAPACITY)
        violations = injectivity_violations(broken, _distinct_lists())
        assert violations, "the broken registry must be caught"
        nifen_sc = family_chain(NIFEN_ART_FAMILY, "zh_CN", "en", False)
        nifen_jp = family_chain(NIFEN_ART_FAMILY, "ja", "en", False)
        assert (nifen_sc, nifen_jp) in violations or (nifen_jp, nifen_sc) in violations
        a, b = violations[0]
        print(f"first-family-only registry fails on the pair {a} / {b}")

    def test_control_first_family_only_registry_names_the_nifen_pair(self) -> None:
        pair = [
            (a, b)
            for a, b in injectivity_violations(
                _FirstFamilyOnlyRegistry(TAG_CAPACITY), _distinct_lists()
            )
            if a[0] == NIFEN_ART_FAMILY and CJK_SC_FAMILY in a and CJK_JP_FAMILY in b
        ]
        assert pair
        print("named failing pair:", pair[0])

    def test_control_real_registry_passes_the_same_check(self) -> None:
        assert (
            injectivity_violations(ChainTagRegistry(TAG_CAPACITY), _distinct_lists())
            == []
        )

    def test_control_tail_length_registry_fails_injectivity(self) -> None:
        violations = injectivity_violations(
            _TailLengthRegistry(TAG_CAPACITY), _distinct_lists()
        )
        assert violations
        print("tail-length registry fails on the pair", violations[0])

    def test_control_registry_tagging_one_family_lists_fails_the_one_family_rule(
        self,
    ) -> None:
        broken = _TagsOneFamilyListsRegistry(TAG_CAPACITY)
        alone = [(primary,) for primary in ROLE_PRIMARIES]
        assert one_family_violations(broken, alone) == alone
        # and it spends capacity: a first family is exhausted sooner than it should be
        exhausting = _TagsOneFamilyListsRegistry(1)
        exhausting.tag_for(["A"])
        with pytest.raises(ChainTagsExhausted):
            exhausting.tag_for(["A", "x"])
        assert one_family_violations(ChainTagRegistry(TAG_CAPACITY), alone) == []

    def test_control_first_list_untagged_registry_fails_the_no_none_rule(
        self,
    ) -> None:
        broken = _FirstListUntaggedRegistry(TAG_CAPACITY)
        violations = untagged_chain_violations(broken, _distinct_lists())
        assert violations
        assert any(chain[0] == NIFEN_ART_FAMILY for chain in violations)
        print("first-list-untagged registry leaves untagged:", violations[0])
        assert any(_is_nifen_mode(chain) for chain in violations)
        assert (
            untagged_chain_violations(ChainTagRegistry(TAG_CAPACITY), _distinct_lists())
            == []
        )


def test_constants_name_the_bundled_families() -> None:
    assert NIFEN_ART_FAMILY == "Nifen Art"
    assert {CJK_SC_FAMILY, CJK_JP_FAMILY, CJK_HANGUL_FAMILY} == {
        "Nifen Art CJK SC",
        "Nifen Art CJK JP",
        "Nifen Art CJK KR",
    }
    assert set(font_chain.__all__) >= {
        "family_chain",
        "label_chain",
        "ChainTagRegistry",
    }
