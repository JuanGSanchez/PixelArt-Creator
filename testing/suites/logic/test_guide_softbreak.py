"""Tests for pixelart_creator.logic.guide_softbreak.

Logic layer, no Qt. Written against the module's documented interface and the
scenario rows of the soft-line-break requirement; every case follows from that
requirement and its clause list.

Layout of the module:

* the public surface and the import discipline of the module under test;
* ``decide`` against the reference oracle, clause by clause;
* one case per scenario row, named by its scenario id and row;
* one case per CommonMark construct of the scanner;
* line endings, the joiner, the fail-safe and the invariants P1 to P6;
* ``content_ref_locale``;
* the tracked trees (non-CJK and CJK), the floors, the guard and its planted control.

The module under test can be replaced by a broken copy through the environment
variable ``SOFTBREAK_MUTANT_FILE`` (see ``_softbreak_mutants.py``).
"""

from __future__ import annotations

import ast
import dataclasses
import re
import sys
import time
import unicodedata
from typing import Callable, Dict, List, Sequence, Tuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic import constants as C
from pixelart_creator.logic import guide_model

from ._softbreak_support import (
    ALL_LOCALES,
    CJ_LOCALES,
    EMOJI_ORACLE,
    NON_CJK_LOCALES,
    REPO_ROOT,
    TREE_REL,
    ZWSP,
    GitListingError,
    git_tracked_pages,
    guard_problems,
    is_hangul,
    load_softbreak,
    make_planted_repo,
    make_scratch,
    module_source_path,
    oracle_clause,
    read_page,
    remove_scratch,
    tracked_trees,
    untracked_present,
)

sb = load_softbreak()

# ---------------------------------------------------------------------------
# The floors. One line per tree that arrives is added in the commit that brings the
# tree.
# ---------------------------------------------------------------------------
REQUIRED_NON_CJK_TREES: Tuple[str, ...] = ("en", "es", "ko")
REQUIRED_CJ_TREES: Tuple[str, ...] = ()

CJK_TREES_SKIP_REASON = (
    "shipped-tree half: no tracked ja or zh_CN tree (REQUIRED_CJ_TREES = ())"
)

#: The clause numbers of the spec, mapped to the enum members. 0 is UNDECIDED.
CL = {
    1: sb.SoftBreakClause.ZERO_WIDTH_SPACE,
    2: sb.SoftBreakClause.WIDE_PAIR,
    3: sb.SoftBreakClause.AMBIGUOUS_PUNCTUATION,
    4: sb.SoftBreakClause.IDEOGRAPHIC_COMMA_OR_STOP,
    5: sb.SoftBreakClause.SPACE,
    0: sb.SoftBreakClause.UNDECIDED,
}
NUMBER_OF = {member: number for number, member in CL.items()}

JOINER = "<!---->"
BACKSLASH = chr(92)
#: The Emoji property's size at UCD 15.1.0 (Unicode 15.1.0): what the import guard checks.
EMOJI_TOTAL = 1424
EMOJI_MISSING = (
    "the Emoji table is not delivered: GUIDE_EMOJI_RANGES is missing or empty in "
    "logic/constants.py, so the emoji clause cannot be proven"
)


def require_emoji_table() -> None:
    """Fail clearly, with the reason, until the Emoji table has been supplied."""
    table = getattr(C, "GUIDE_EMOJI_RANGES", None)
    if not table:
        pytest.fail(EMOJI_MISSING, pytrace=False)


def number(result_break) -> int:
    """The spec's clause number (0 = undecided) of one examined break."""
    return NUMBER_OF[result_break.clause]


def summary(result) -> List[Tuple[int, int]]:
    """``(line, clause number)`` for every examined break, in order."""
    return [(b.line, number(b)) for b in result.breaks]


def join_after(lines: Sequence[str], removed: Sequence[int], ending: str = "\n") -> str:
    """Join ``lines`` with ``ending``; the endings after the 1-based ``removed`` go.

    Only for lines that carry no container prefix and no joiner: it is the
    expected value of a plain-text case, computed from the construction.
    """
    out = []
    for index, line in enumerate(lines, start=1):
        out.append(line)
        out.append("" if index in removed else ending)
    return "".join(out)


# ===========================================================================
# 1. The public surface and the import discipline
# ===========================================================================


class TestPublicSurface:
    """The public interface contract and the module's import list."""

    def test_the_names_the_contract_fixes_exist(self):
        for name in (
            "SoftBreakClause",
            "decide",
            "SoftBreak",
            "SoftBreakResult",
            "apply_soft_break_rule",
            "CLAUSE3_LANGUAGES",
            "CLAUSE4_LANGUAGES",
            "SOFT_BREAK_JOINER",
        ):
            assert hasattr(sb, name), name

    def test_clause_members_and_labels(self):
        members = {m.name: m.value for m in sb.SoftBreakClause}
        assert members == {
            "ZERO_WIDTH_SPACE": "clause 1",
            "WIDE_PAIR": "clause 2",
            "AMBIGUOUS_PUNCTUATION": "clause 3",
            "IDEOGRAPHIC_COMMA_OR_STOP": "clause 4",
            "SPACE": "clause 5",
            "UNDECIDED": "undecided",
        }

    def test_the_two_language_sets_are_ja_and_zh_cn_and_apart(self):
        assert set(sb.CLAUSE3_LANGUAGES) == {"ja", "zh_CN"}
        assert set(sb.CLAUSE4_LANGUAGES) == {"ja", "zh_CN"}

    def test_the_joiner_is_an_empty_html_comment(self):
        assert sb.SOFT_BREAK_JOINER == JOINER

    def test_a_soft_break_and_a_result_are_frozen_dataclasses(self):
        item = sb.SoftBreak(
            line=1, before="a", after="b", clause=sb.SoftBreakClause.SPACE
        )
        assert dataclasses.is_dataclass(item)
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.line = 2  # type: ignore[misc]
        result = sb.SoftBreakResult(markdown="x", breaks=(item,))
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.markdown = "y"  # type: ignore[misc]
        assert result.breaks == (item,)

    @pytest.mark.parametrize("clause_number", [1, 2, 3, 4, 5, 0])
    def test_removed_is_true_exactly_for_clauses_one_to_four(self, clause_number):
        item = sb.SoftBreak(line=1, before="a", after="b", clause=CL[clause_number])
        assert item.removed is (clause_number in (1, 2, 3, 4))

    def test_the_result_holds_a_tuple_of_soft_breaks(self):
        result = sb.apply_soft_break_rule("日本\n語\n", "ja")
        assert isinstance(result, sb.SoftBreakResult)
        assert isinstance(result.breaks, tuple)
        assert all(isinstance(b, sb.SoftBreak) for b in result.breaks)
        assert isinstance(result.markdown, str)


class TestImportDiscipline:
    """The module imports only the stdlib and the constants ."""

    @staticmethod
    def _imports() -> List[str]:
        tree = ast.parse(module_source_path(sb).read_text(encoding="utf-8"))
        found: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    base = "." * node.level + base
                found.append(base)
                found.extend(f"{base}.{alias.name}" for alias in node.names)
        return found

    def test_only_the_standard_library_and_the_constants_are_imported(self):
        allowed_roots = set(sys.stdlib_module_names) | {"pixelart_creator"}
        for name in self._imports():
            root = name.split(".")[0]
            assert (
                root in allowed_roots
            ), f"{name} is not the stdlib or pixelart_creator"
            if root == "pixelart_creator":
                assert name.startswith("pixelart_creator.logic"), name

    def test_no_qt_no_ui_no_data_layer_is_imported(self):
        for name in self._imports():
            assert not name.startswith("PySide6"), name
            assert not name.startswith("pixelart_creator.ui"), name
            assert not name.startswith("pixelart_creator.data"), name

    def test_html_is_not_imported_because_references_are_not_decoded(self):
        for name in self._imports():
            assert name.split(".")[0] != "html", name

    def test_the_bare_str_strip_family_does_not_occur(self):
        source = module_source_path(sb).read_text(encoding="utf-8")
        assert not re.search(r"\.(?:l|r)?strip\(\s*\)", source), (
            "str.strip() with no argument also strips U+3000 and U+00A0 "
            "(see the module docstring): only U+0020 and U+0009 may be stripped"
        )

    def test_the_font_coverage_hangul_block_is_not_used_by_the_rule(self):
        source = module_source_path(sb).read_text(encoding="utf-8")
        assert not re.search(r"\bHANGUL_RANGES\b", source)


# ===========================================================================
# 2. decide(): the clauses, in order
# ===========================================================================


def d(before: str, after: str, language: str):
    return sb.decide(before, after, language)


class TestDecideClauseOne:
    """Clause 1: U+200B on either side, any language, before every other clause."""

    @pytest.mark.parametrize("language", ALL_LOCALES)
    def test_zwsp_before_removes_in_every_language(self, language):
        assert d(ZWSP, "a", language) is CL[1]

    @pytest.mark.parametrize("language", ALL_LOCALES)
    def test_zwsp_after_removes_in_every_language(self, language):
        assert d("a", ZWSP, language) is CL[1]

    def test_clause_one_precedes_clause_two(self):
        assert d("日", ZWSP, "ja") is CL[1]
        assert d(ZWSP, "本", "ja") is CL[1]

    def test_zwsp_beside_hangul_still_removes(self):
        assert d("레", ZWSP, "ko") is CL[1]
        assert d(ZWSP, "선", "ja") is CL[1]

    def test_zwsp_on_both_sides(self):
        assert d(ZWSP, ZWSP, "en") is CL[1]


class TestDecideClauseTwo:
    """Clause 2: both sides F, W or H, and neither Hangul. No language named."""

    @pytest.mark.parametrize("language", ALL_LOCALES)
    def test_two_han_characters_in_any_language(self, language):
        assert d("日", "本", language) is CL[2]

    def test_wide_kana_and_fullwidth_punctuation(self):
        assert d("ル", "を", "ja") is CL[2]
        assert d("、", "編", "ja") is CL[2]
        assert d("，", "然", "zh_CN") is CL[2]
        assert d("で", "「", "ja") is CL[2]

    def test_halfwidth_h_counts_as_wide(self):
        assert unicodedata.east_asian_width("ｱ") == "H"
        assert d("ｱ", "日", "ja") is CL[2]
        assert d("日", "ｱ", "ja") is CL[2]
        assert d("､", "日", "ja") is CL[2]
        assert d("｡", "日", "ja") is CL[2]

    def test_fullwidth_latin_is_f_and_joins_with_the_ideographic_marks(self):
        assert d("Ａ", "、", "ja") is CL[2]
        assert d("。", "１", "zh_CN") is CL[2]

    def test_ideographic_space_is_f_and_takes_part(self):
        assert d("　", "語", "ja") is CL[2]
        assert d("本", "　", "ja") is CL[2]

    @pytest.mark.parametrize(
        "hangul",
        ["한", "ᄀ", "ㄱ", "ﾡ", "ꥠ", "ힰ"],
        ids=[
            "syllable",
            "jamo-u1100",
            "compat-jamo",
            "halfwidth-hangul",
            "jamo-a960",
            "jamo-d7b0",
        ],
    )
    def test_any_script_hangul_character_on_either_side_blocks_clause_two(self, hangul):
        assert is_hangul(hangul)
        assert d(hangul, "日", "ja") is CL[5]
        assert d("日", hangul, "ja") is CL[5]
        assert d(hangul, hangul, "ko") is CL[5]

    def test_narrow_and_neutral_never_qualify(self):
        assert d("日", "a", "ja") is CL[5]
        assert d("a", "日", "ja") is CL[5]
        assert d("Ж", "日", "ru") is CL[5]


class TestDecideClauseThree:
    """Clause 3: A-width punctuation or symbol beside F/W/H, in ja and zh_CN only."""

    @pytest.mark.parametrize("mark", list("“”‘’…—·※→×°±§"))
    @pytest.mark.parametrize("language", ["ja", "zh_CN"])
    def test_ambiguous_mark_beside_a_wide_character(self, mark, language):
        assert unicodedata.east_asian_width(mark) == "A"
        assert unicodedata.category(mark)[0] in "PS"
        assert d(mark, "日", language) is CL[3]
        assert d("日", mark, language) is CL[3]

    @pytest.mark.parametrize("mark", list("“—…→"))
    @pytest.mark.parametrize("language", ["en", "es", "fr", "de", "ru", "ko"])
    def test_other_languages_keep_the_space(self, mark, language):
        assert d(mark, "日", language) is CL[5]
        assert d("日", mark, language) is CL[5]

    def test_halfwidth_is_the_other_side_too(self):
        assert d("“", "ｱ", "ja") is CL[3]

    def test_the_other_side_must_not_be_hangul(self):
        assert d("“", "한", "ja") is CL[5]
        assert d("한", "”", "zh_CN") is CL[5]
        assert d("—", "ﾡ", "ja") is CL[5]

    def test_the_other_side_must_be_wide(self):
        assert d("“", "C", "zh_CN") is CL[5]
        assert d("—", "C", "ja") is CL[5]
        assert d("C", "”", "ja") is CL[5]

    def test_ambiguous_letters_and_numbers_are_not_punctuation_or_symbols(self):
        # α is A and a letter, Ⅳ is A and Nl, ² is A and No: none is P or S.
        for char in ("α", "Ⅳ", "²"):
            assert unicodedata.east_asian_width(char) == "A"
            assert d(char, "日", "ja") is CL[5], char

    def test_a_plain_ascii_mark_is_narrow_not_ambiguous(self):
        assert d("!", "日", "ja") is CL[5]
        assert d("-", "日", "ja") is CL[5]

    def test_clause_two_is_tried_before_clause_three(self):
        # 、 is W, so a pair with a wide character is clause 2 even in ja.
        assert d("、", "日", "ja") is CL[2]


class TestDecideClauseFour:
    """Clause 4: U+3001 or U+3002 beside a Latin letter or Nd, ja and zh_CN only."""

    @pytest.mark.parametrize("mark", ["、", "。"])
    @pytest.mark.parametrize("language", ["ja", "zh_CN"])
    @pytest.mark.parametrize(
        "other", ["P", "a", "é", "Z", "K", "ª", "ǅ", "0", "4", "٣"]
    )
    def test_mark_beside_latin_letter_or_digit_in_either_order(
        self, mark, language, other
    ):
        assert d(mark, other, language) is CL[4]
        assert d(other, mark, language) is CL[4]

    @pytest.mark.parametrize("language", ["en", "es", "fr", "de", "ru", "ko"])
    def test_not_applied_outside_chinese_and_japanese_pages(self, language):
        assert d("、", "E", language) is CL[5]
        assert d("G", "。", language) is CL[5]

    @pytest.mark.parametrize("near_miss", ["，", "､", "｡", "．", "：", "；"])
    def test_other_marks_are_not_covered(self, near_miss):
        assert d(near_miss, "E", "ja") is CL[5]
        assert d("4", near_miss, "zh_CN") is CL[5]

    def test_the_latin_letter_is_a_letter_and_not_any_latin_script_character(self):
        # Ⅳ (U+2163) is Script=Latin but its category is Nl, not L.
        assert d("。", "Ⅳ", "ja") is CL[5]

    def test_only_decimal_digits_count(self):
        assert d("。", "²", "ja") is CL[5]  # No
        assert d("。", "½", "ja") is CL[5]  # No

    def test_non_latin_letters_do_not_count(self):
        assert d("。", "α", "ja") is CL[5]  # Greek
        assert d("。", "Ж", "zh_CN") is CL[5]  # Cyrillic

    def test_the_marks_come_from_the_constant(self):
        assert tuple(C.GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS) == (0x3001, 0x3002)


class TestDecideClauseFive:
    """Clause 5 and the language switch."""

    @pytest.mark.parametrize("language", ALL_LOCALES)
    def test_two_latin_letters(self, language):
        assert d("o", "w", language) is CL[5]

    @pytest.mark.parametrize("language", ["xx", "", "JA", "zh_TW", "ja_JP", "zh-CN"])
    def test_an_unknown_language_gets_only_the_language_free_clauses(self, language):
        assert d("“", "日", language) is CL[5]
        assert d("、", "E", language) is CL[5]
        assert d("日", "本", language) is CL[2]
        assert d(ZWSP, "x", language) is CL[1]

    def test_decide_returns_enum_members_only(self):
        for pair in (("a", "b"), ("日", "本"), (ZWSP, "a"), ("“", "日"), ("、", "A")):
            assert isinstance(d(pair[0], pair[1], "ja"), sb.SoftBreakClause)

    def test_decide_never_returns_undecided_for_two_single_characters(self):
        assert d("a", "b", "en") is not CL[0]


class TestDecideEmojiRule:
    """Emoji of width W or N count as A in clauses 2 and 3 (needs the Emoji table)."""

    def test_the_emoji_table_has_been_supplied(self):
        require_emoji_table()

    def test_a_wide_emoji_beside_a_wide_character_is_clause_three_not_two(self):
        require_emoji_table()
        assert unicodedata.east_asian_width("\U0001f600") == "W"
        assert d("\U0001f600", "次", "ja") is CL[3]
        assert d("完", "\U0001f600", "zh_CN") is CL[3]

    def test_the_emoji_rule_is_not_language_free_in_clause_three(self):
        require_emoji_table()
        assert d("\U0001f600", "次", "en") is CL[5]
        assert d("完", "\U0001f600", "ko") is CL[5]

    def test_a_neutral_emoji_beside_a_wide_character(self):
        require_emoji_table()
        for char in ("©", "™", "‼", "☀", "❤"):
            assert unicodedata.east_asian_width(char) in ("N", "A"), char
            assert d(char, "山", "ja") is CL[3], char

    def test_two_emoji_are_both_ambiguous_so_neither_clause_applies(self):
        require_emoji_table()
        assert d("\U0001f600", "\U0001f600", "ja") is CL[5]
        assert d("\U0001f600", "✨", "zh_CN") is CL[5]

    def test_narrow_emoji_property_characters_are_not_affected(self):
        require_emoji_table()
        # #, * and 0 have Emoji=Yes and width Na, not N: unaffected.
        for char in ("#", "*", "0"):
            assert unicodedata.east_asian_width(char) == "Na"
            assert d(char, "日", "ja") is CL[5], char
            assert d("日", char, "zh_CN") is CL[5], char

    def test_emoji_status_is_judged_on_the_character_not_a_neighbour(self):
        require_emoji_table()
        assert d("日", "本", "ja") is CL[2]


# ===========================================================================
# 3. The reference oracle (property P5) and the other properties
# ===========================================================================

HAN = "日本語图层面板選択範囲移動"
KANA = "ひらがなカタカナファイルをのー"
HALFWIDTH_KANA = "ｱｲｳｶ"
FULLWIDTH = "、。「」（），．：Ａａ１"
HANGUL = "한국어레이어" + "ᄀᆨ" + "ㄱㅏ" + "ﾡﾢ" + "ꥠힰ"
LATIN = "AbZé" + "ǅ" + "ª" + "K" + "Ⅳ" + "ĳ"
DIGITS = "059" + "٣" + "²" + "½"
OTHER_LETTERS = "αΩжЖ"
AMBIG_MARKS = "“”‘’…—·※→×°±§"
NEAR_MISS_MARKS = "，､｡．：；"
IDEOGRAPHIC = "、。"
ASCII_PUNCT = ".,;:!?()-+/=<>|~"
SPACES = "　 "
EMOJI_CHARS = "\U0001f600\U0001f601\U0001f389\U0001f680✨⭐⌚☀❤ℹ©®™‼⁉#*0123456789"
NON_EMOJI_CHARS = (
    HAN + KANA + HALFWIDTH_KANA + FULLWIDTH + HANGUL + LATIN + OTHER_LETTERS
)
NON_EMOJI_CHARS += (
    AMBIG_MARKS + NEAR_MISS_MARKS + IDEOGRAPHIC + ASCII_PUNCT + SPACES + ZWSP
)
NON_EMOJI_CHARS += "٣²½"

LANGUAGES = st.sampled_from(list(ALL_LOCALES))
CHAR_NON_EMOJI = st.sampled_from(sorted(set(NON_EMOJI_CHARS)))
CHAR_ANY = st.sampled_from(sorted(set(NON_EMOJI_CHARS + EMOJI_CHARS)))


class TestOracleSanity:
    """The oracle itself is checked on the spec's own pairs, before it judges anything."""

    @pytest.mark.parametrize(
        ("before", "after", "language", "clause"),
        [
            ("日", "本", "en", 2),
            ("한", "국", "ko", 5),
            ("“", "日", "ja", 3),
            ("“", "日", "en", 5),
            ("、", "P", "ja", 4),
            ("、", "P", "ko", 5),
            (ZWSP, "a", "ru", 1),
            ("©", "山", "ja", 3),
            ("\U0001f600", "\U0001f600", "ja", 5),
        ],
    )
    def test_oracle_matches_the_spec(self, before, after, language, clause):
        assert oracle_clause(before, after, language) == clause

    def test_every_oracle_emoji_character_has_a_known_width(self):
        for char in EMOJI_ORACLE:
            assert unicodedata.east_asian_width(char) in ("W", "N", "A", "Na"), char


@given(CHAR_NON_EMOJI, CHAR_NON_EMOJI, LANGUAGES)
def test_p5_decide_agrees_with_the_oracle_without_emoji(before, after, language):
    expected = CL[oracle_clause(before, after, language)]
    assert sb.decide(before, after, language) is expected


@given(CHAR_ANY, CHAR_ANY, LANGUAGES)
def test_p5_decide_agrees_with_the_oracle_with_emoji(before, after, language):
    require_emoji_table()
    expected = CL[oracle_clause(before, after, language)]
    assert sb.decide(before, after, language) is expected


@given(CHAR_ANY, CHAR_ANY, LANGUAGES)
def test_p4_a_hangul_character_is_removed_only_by_clause_one(before, after, language):
    if is_hangul(before) or is_hangul(after):
        assert sb.decide(before, after, language) in (CL[1], CL[5])


@given(
    st.lists(st.sampled_from(sorted(set(HANGUL))), min_size=1, max_size=3),
    st.sampled_from(sorted(set(HAN + KANA + AMBIG_MARKS + IDEOGRAPHIC + "aZ5"))),
    LANGUAGES,
    st.booleans(),
)
def test_p4_on_pages_a_removed_break_beside_hangul_is_clause_one(
    hangul, other, language, hangul_first
):
    left, right = ("".join(hangul), other) if hangul_first else (other, "".join(hangul))
    page = f"{left}\n{right}\n"
    result = sb.apply_soft_break_rule(page, language)
    for item in result.breaks:
        if (is_hangul(item.before) or is_hangul(item.after)) and item.removed:
            assert item.clause is CL[1]


# ===========================================================================
# 4. One case per scenario row, named by scenario id and row
# ===========================================================================

# (language, source, expected source, visible character before, visible after)
ADJACENT_CJK_ROWS = [
    ("ja", "日本\n語", "日本語", "本", "語"),
    ("ja", "ファイル\nを開く", "ファイルを開く", "ル", "を"),
    ("ja", "表示、\n編集", "表示、編集", "、", "編"),
    ("ja", "選択範囲を\n**移動**します", "選択範囲を<!---->**移動**します", "を", "移"),
    (
        "ja",
        "[レイヤー](layers.md)\nを選びます",
        "[レイヤー](layers.md)を選びます",
        "ー",
        "を",
    ),
    ("ja", "日本 \n語", "日本語", "本", "語"),
    ("zh_CN", "图层\n面板", "图层面板", "层", "面"),
    ("zh_CN", "选择，\n然后", "选择，然后", "，", "然"),
    (
        "ja",
        "> 1 回のドロップで\n> 種類を混ぜる",
        "> 1 回のドロップで種類を混ぜる",
        "で",
        "種",
    ),
    ("ja", "1. 選択範囲を\n   持ち上げます", "1. 選択範囲を持ち上げます", "を", "持"),
]

# Every row keeps its break: the source comes back byte for byte (clause 5).
OTHER_BREAKS_ROWS = [
    ("en", "Hello\nworld", "o", "w"),
    ("ru", "Слой\nвыбран", "й", "в"),
    ("ko", "레이어를\n선택합니다", "를", "선"),
    ("ja", "ストレートアルファの\nsource-over", "の", "s"),
    ("ja", "**Delete**\nは同じ", "e", "は"),
    ("ja", "バージョンを\n1 行", "を", "1"),
    ("en", "Click “Save”\nand close", "”", "a"),
    ("en", "日本 —\n語", "—", "語"),
    ("ja", "選択 —\nCtrl キー", "—", "C"),
    ("ja", "韓国語 “\n한국어”", "“", "한"),
    ("zh_CN", "使用“\nCtrl”键", "“", "C"),
    ("ko", "끝。\nCtrl 키", "。", "C"),
    ("en", "表示、\nEdit", "、", "E"),
    ("zh_CN", "选择，\nCtrl 键", "，", "C"),
    ("ja", "表示､\nEdit", "､", "E"),
]

ZERO_WIDTH_SPACE_ROWS = [
    ("en", "word​\nbreak", "word​break", "​", "b"),
    ("en", "word\n​break", "word​break", "d", "​"),
    ("en", "word​ \nbreak", "word​break", "​", "b"),
    ("ko", "레이어를​\n선택합니다", "레이어를​선택합니다", "​", "선"),
    ("ja", "日本​\n語", "日本​語", "​", "語"),
]

AMBIGUOUS_PUNCTUATION_ROWS = [
    ("zh_CN", "选择\n“文件”菜单", "选择“文件”菜单", "择", "“"),
    ("zh_CN", "打开“文件”\n菜单", "打开“文件”菜单", "”", "菜"),
    ("zh_CN", "正在保存…\n完成后", "正在保存…完成后", "…", "完"),
    (
        "ja",
        "**ありません** —\n現在のドキュメント",
        "**ありません** —現在のドキュメント",
        "—",
        "現",
    ),
    ("ja", "「保存」→\n「閉じる」", "「保存」→「閉じる」", "→", "「"),
    ("ja", "下記※\n参照", "下記※参照", "※", "参"),
]

IDEOGRAPHIC_PUNCTUATION_ROWS = [
    (
        "ja",
        "**パースグリッド**、\nPureRef 風の",
        "**パースグリッド**、PureRef 風の",
        "、",
        "P",
    ),
    (
        "ja",
        "載せています。\n**Ctrl+Shift+E** は",
        "載せています。<!---->**Ctrl+Shift+E** は",
        "。",
        "C",
    ),
    ("ja", "設定でき、\n4 つのモード", "設定でき、4 つのモード", "、", "4"),
    ("ja", "対象は PNG\n、GIF です", "対象は PNG、GIF です", "G", "、"),
    ("zh_CN", "支持 PNG、\nGIF 和", "支持 PNG、GIF 和", "、", "G"),
    ("zh_CN", "完成。\nPixelArt Creator 会", "完成。PixelArt Creator 会", "。", "P"),
    ("zh_CN", "版本 2\n。", "版本 2。", "2", "。"),
]

# (language, source, expected source or None = unchanged, before, after, clause number)
EMOJI_WIDTH_ROWS = [
    ("ja", "完了\U0001f600\n次へ", "完了\U0001f600次へ", "\U0001f600", "次", 3),
    ("ja", "著作権 ©\n山田", "著作権 ©山田", "©", "山", 3),
    ("en", "完了\U0001f600\n次へ", None, "\U0001f600", "次", 5),
    ("ja", "\U0001f600\n\U0001f600", None, "\U0001f600", "\U0001f600", 5),
]


def _ids(prefix: str, rows: Sequence) -> List[str]:
    return [f"{prefix}-row-{index:02d}" for index in range(1, len(rows) + 1)]


def _expect_row(language, source, expected, before, after, clause_number):
    result = sb.apply_soft_break_rule(source, language)
    assert result.markdown == (source if expected is None else expected)
    assert len(result.breaks) == 1
    item = result.breaks[0]
    assert (item.line, item.before, item.after) == (1, before, after)
    assert number(item) == clause_number
    # the premise of the row, recomputed from the Unicode database and the spec
    assert oracle_clause(before, after, language) == clause_number
    assert sb.decide(before, after, language) is CL[clause_number]
    assert item.removed is (clause_number <= 4)


class TestAdjacentCjk:
    """A break between two Chinese or Japanese characters shows nothing."""

    @pytest.mark.parametrize(
        ("language", "source", "expected", "before", "after"),
        ADJACENT_CJK_ROWS,
        ids=_ids("adjacent-cjk", ADJACENT_CJK_ROWS),
    )
    def test_row(self, language, source, expected, before, after):
        _expect_row(language, source, expected, before, after, 2)


class TestOtherBreaks:
    """Every other soft line break is shown as one space."""

    @pytest.mark.parametrize(
        ("language", "source", "before", "after"),
        OTHER_BREAKS_ROWS,
        ids=_ids("other-breaks", OTHER_BREAKS_ROWS),
    )
    def test_row(self, language, source, before, after):
        _expect_row(language, source, None, before, after, 5)


class TestVerbatim:
    """Code, hard breaks and paragraph breaks come back byte-identical."""

    CONSTRUCTS = {
        "row-1-code-span-with-a-line-ending": "`日本\n語`\n",
        "row-2-fenced-code-block": "```\n日本\n語\n```\n",
        "row-3-indented-code-block": "    日本\n    語\n",
        "row-4-two-space-hard-break": "日本  \n語\n",
        "row-5-backslash-hard-break": "日本\\\n語\n",
        "row-6-paragraph-break": "日本\n\n語\n",
        "row-7-typed-space-on-one-line": "日本 語\n",
    }

    @pytest.mark.parametrize("page", list(CONSTRUCTS.values()), ids=list(CONSTRUCTS))
    def test_row(self, page):
        result = sb.apply_soft_break_rule(page, "ja")
        assert result.markdown == page
        assert not [b for b in result.breaks if b.removed]

    @pytest.mark.parametrize("page", list(CONSTRUCTS.values()), ids=list(CONSTRUCTS))
    def test_the_row_is_the_same_in_the_other_languages(self, page):
        for language in ("zh_CN", "ko", "en"):
            result = sb.apply_soft_break_rule(page, language)
            assert result.markdown == page, language


class TestZeroWidthSpace:
    """A break beside U+200B is not shown, and the U+200B stays."""

    @pytest.mark.parametrize(
        ("language", "source", "expected", "before", "after"),
        ZERO_WIDTH_SPACE_ROWS,
        ids=_ids("zero-width-space", ZERO_WIDTH_SPACE_ROWS),
    )
    def test_row(self, language, source, expected, before, after):
        _expect_row(language, source, expected, before, after, 1)
        assert ZWSP in sb.apply_soft_break_rule(source, language).markdown


class TestAmbiguousPunctuation:
    """Ambiguous-width punctuation beside a Chinese or Japanese character."""

    @pytest.mark.parametrize(
        ("language", "source", "expected", "before", "after"),
        AMBIGUOUS_PUNCTUATION_ROWS,
        ids=_ids("ambiguous-punctuation", AMBIGUOUS_PUNCTUATION_ROWS),
    )
    def test_row(self, language, source, expected, before, after):
        _expect_row(language, source, expected, before, after, 3)


class TestIdeographicPunctuation:
    """U+3001 or U+3002 beside a Latin letter or a digit."""

    @pytest.mark.parametrize(
        ("language", "source", "expected", "before", "after"),
        IDEOGRAPHIC_PUNCTUATION_ROWS,
        ids=_ids("ideographic-punctuation", IDEOGRAPHIC_PUNCTUATION_ROWS),
    )
    def test_row(self, language, source, expected, before, after):
        _expect_row(language, source, expected, before, after, 4)


class TestEmojiWidth:
    """An emoji counts as ambiguous width (needs the Emoji table)."""

    @pytest.mark.parametrize(
        ("language", "source", "expected", "before", "after", "clause_number"),
        EMOJI_WIDTH_ROWS,
        ids=_ids("emoji-width", EMOJI_WIDTH_ROWS),
    )
    def test_row(self, language, source, expected, before, after, clause_number):
        require_emoji_table()
        _expect_row(language, source, expected, before, after, clause_number)


# ===========================================================================
# 5. One case per construct of the scanner
# ===========================================================================


def run_ja(
    lines: Sequence[str], ending: str = "\n"
) -> Tuple[str, "sb.SoftBreakResult"]:
    page = ending.join(lines) + ending
    return page, sb.apply_soft_break_rule(page, "ja")


def expect_plain(
    lines: Sequence[str], expected: Sequence[Tuple[int, int]], markdown=None
):
    """Assert the exact break set and the transformed source of a plain-text page."""
    page, result = run_ja(lines)
    assert summary(result) == list(expected)
    removed = {line for line, clause in expected if 1 <= clause <= 4}
    wanted = join_after(lines, removed) if markdown is None else markdown
    assert result.markdown == wanted


class TestConstructHeadingsAndRules:
    def test_setext_heading_of_one_line_equals_underline(self):
        expect_plain(["日本", "===", "語", "本"], [(3, 2)])

    def test_setext_heading_of_one_line_dash_underline(self):
        expect_plain(["日本", "---", "語", "本"], [(3, 2)])

    def test_setext_heading_of_two_lines_has_no_candidate(self):
        expect_plain(["日本", "語", "===", "本", "語"], [(4, 2)])

    def test_setext_heading_of_two_lines_dash_underline(self):
        expect_plain(["日本", "語", "---", "本", "語"], [(4, 2)])

    @pytest.mark.parametrize("rule", ["***", "___", "- - -", "* * *", "_ _ _"])
    def test_thematic_break_interrupts_a_paragraph(self, rule):
        expect_plain(["日本", rule, "語", "本"], [(3, 2)])

    def test_atx_heading_interrupts_a_paragraph(self):
        expect_plain(["日本", "語", "# 見出し", "本", "語"], [(1, 2), (4, 2)])

    def test_atx_heading_text_is_not_judged(self):
        expect_plain(["# 日本", "語", "本"], [(2, 2)])


# (name, start line, inner lines, end line or None for "ends at a blank line")
HTML_CONDITIONS = {
    1: ("<pre>", ["日本", "語"], "</pre>"),
    2: ("<!-- note", ["日本", "語"], "-->"),
    3: ("<?php", ["日本", "語"], "?>"),
    4: ("<!ELEMENT x", ["日本", "語"], "end>"),
    5: ("<![CDATA[", ["日本", "語"], "]]>"),
    6: ("<div>", ["日本", "語"], None),
    7: ("<custom-tag>", ["日本", "語"], None),
}


class TestConstructHtmlBlocks:
    """HTML blocks of start conditions 1 to 7 (CommonMark 0.31.2 section 4.6)."""

    @pytest.mark.parametrize("condition", [1, 2, 3, 4, 5, 6])
    def test_interrupts_a_paragraph(self, condition):
        start, inner, end = HTML_CONDITIONS[condition]
        lines = ["日本", "語", start, *inner]
        if end is not None:
            lines.append(end)
        tail = ["", "本", "語"] if end is None else ["本", "語"]
        lines += tail
        # the paragraph before the block has one break (line 1); the paragraph after has one
        after_line = len(lines) - 1
        expect_plain(lines, [(1, 2), (after_line, 2)])

    @pytest.mark.parametrize("condition", [1, 2, 3, 4, 5, 6, 7])
    def test_starts_after_a_blank_line(self, condition):
        start, inner, end = HTML_CONDITIONS[condition]
        lines = ["本", "", start, *inner]
        if end is not None:
            lines.append(end)
        tail = ["", "本", "語"] if end is None else ["本", "語"]
        lines += tail
        after_line = len(lines) - 1
        expect_plain(lines, [(after_line, 2)])

    def test_condition_seven_does_not_interrupt_a_paragraph(self):
        page, result = run_ja(["日本", "<custom-tag>", "語"])
        assert result.markdown == page
        assert [b.line for b in result.breaks] == [1, 2]
        assert not [b for b in result.breaks if b.removed]

    def test_condition_seven_tag_that_is_followed_by_text_is_inline(self):
        page, result = run_ja(["日本", "<custom-tag>語"])
        assert result.markdown == page
        assert [b.line for b in result.breaks] == [1]


class TestConstructLinkReferenceDefinition:
    def test_definition_with_a_title_of_several_lines_is_not_text(self):
        lines = ['[foo]: /url "日本', '語"', "", "日本", "語"]
        expect_plain(lines, [(4, 2)])

    def test_definition_without_a_title_is_not_text(self):
        lines = ["[foo]: /url", "日本", "語"]
        expect_plain(lines, [(2, 2)])

    def test_definition_with_the_destination_on_the_next_line(self):
        lines = ["[foo]:", "/url", "日本", "語"]
        expect_plain(lines, [(3, 2)])


class TestConstructContainers:
    def test_lazy_continuation_in_a_block_quote(self):
        page, result = run_ja(["> 日本", "語", "本"])
        assert summary(result) == [(1, 2), (2, 2)]
        assert result.markdown == "> 日本語本\n"

    def test_lazy_continuation_in_a_list_item(self):
        page, result = run_ja(["- 日本", "語", "本"])
        assert summary(result) == [(1, 2), (2, 2)]
        assert result.markdown == "- 日本語本\n"

    def test_nested_quotes_with_the_same_depth(self):
        page, result = run_ja([">> 日本", ">> 語"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == ">> 日本語\n"

    def test_depth_falling_is_a_lazy_continuation(self):
        page, result = run_ja([">> 日本", "> 語"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == ">> 日本語\n"

    def test_depth_rising_starts_a_nested_quote_and_interrupts(self):
        page, result = run_ja(["> 日本", ">> 語"])
        assert summary(result) == []
        assert result.markdown == page

    def test_three_deep_quote_loses_every_marker_of_the_joined_line(self):
        page, result = run_ja([">>> 日本", ">>> 語"])
        assert result.markdown == ">>> 日本語\n"

    def test_ordered_item_starting_at_two_does_not_interrupt(self):
        expect_plain(
            ["日本", "2. 語", "本"], [(1, 5), (2, 2)], markdown="日本\n2. 語本\n"
        )

    def test_ordered_item_starting_at_one_interrupts(self):
        expect_plain(["日本", "1. 語", "本"], [(2, 2)], markdown="日本\n1. 語本\n")

    def test_ordered_item_with_a_parenthesis(self):
        expect_plain(["日本", "1) 語", "本"], [(2, 2)], markdown="日本\n1) 語本\n")

    def test_empty_bullet_does_not_interrupt(self):
        expect_plain(["日本", "+", "語"], [(1, 5), (2, 5)])

    def test_an_empty_item_ends_at_a_blank_line_and_the_text_after_it_is_a_paragraph(
        self,
    ):
        # "-" with nothing after it, a blank line, then an indented paragraph: the
        # item has no content, so the blank line closes it and the two lines below
        # are an ordinary paragraph (CommonMark 0.31.2 list items).
        page, result = run_ja(["-", "", "  日", "  本"])
        assert summary(result) == [(3, 2)]
        assert result.markdown == "-\n\n  日本\n"

    def test_the_same_lines_after_an_item_with_content_belong_to_the_item(self):
        page, result = run_ja(["- a", "", "  日", "  本"])
        assert summary(result) == [(3, 2)]
        assert result.markdown == "- a\n\n  日本\n"

    def test_non_empty_bullet_interrupts(self):
        expect_plain(["日本", "- 語", "本"], [(2, 2)], markdown="日本\n- 語本\n")

    def test_list_item_continuation_loses_its_indentation_when_joined(self):
        page, result = run_ja(["- 日本", "  語"])
        assert result.markdown == "- 日本語\n"

    def test_ordered_list_continuation_indentation_is_the_content_column(self):
        page, result = run_ja(["10. 日本", "    語"])
        assert result.markdown == "10. 日本語\n"

    def test_nested_list_item_joins_under_both_indents(self):
        page, result = run_ja(["- 外", "  - 日本", "    語"])
        assert result.markdown == "- 外\n  - 日本語\n"

    def test_quote_in_a_list_item(self):
        page, result = run_ja(["- > 日本", "  > 語"])
        assert result.markdown == "- > 日本語\n"

    def test_indented_code_under_a_list_item_at_the_content_column(self):
        # content column 2, so six spaces is four beyond it: indented code.
        expect_plain(["- 日本", "", "      日本", "      語"], [])

    def test_one_column_short_of_indented_code_is_a_paragraph(self):
        page, result = run_ja(["- 日本", "", "     日本", "     語"])
        assert summary(result) == [(3, 2)]
        assert result.markdown == "- 日本\n\n     日本語\n"

    def test_an_indented_line_after_a_paragraph_line_continues_it(self):
        page, result = run_ja(["日本", "    語"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == "日本語\n"

    def test_indented_code_after_a_blank_line_is_code(self):
        expect_plain(["日本", "", "    日本", "    語"], [])

    def test_a_block_quote_interrupts_a_paragraph(self):
        page, result = run_ja(["日本", "語", "> 本", "> 語"])
        assert summary(result) == [(1, 2), (3, 2)]
        assert result.markdown == "日本語\n> 本語\n"

    def test_a_fence_interrupts_a_paragraph(self):
        expect_plain(
            ["日本", "語", "```", "日本", "語", "```", "本", "語"], [(1, 2), (7, 2)]
        )

    def test_a_tilde_fence_interrupts_a_paragraph(self):
        expect_plain(
            ["日本", "語", "~~~", "日本", "語", "~~~", "本", "語"], [(1, 2), (7, 2)]
        )

    def test_a_longer_fence_is_not_closed_by_a_shorter_one(self):
        expect_plain(["````", "日本", "```", "語", "````", "本", "語"], [(6, 2)])

    def test_an_unclosed_fence_runs_to_the_end(self):
        expect_plain(["日本", "語", "```", "日本", "語"], [(1, 2)])


class TestConstructTables:
    # Re-expected from Qt, not weakened. Qt (md4c,
    # PySide6 6.11.1) starts a table only under a paragraph's FIRST line, so it reads both
    # pages below as ONE paragraph (blocks=1, tables=0; plain text
    # ``日本 | a | b | | --- | --- | | 本 | 語 |``). The transformed source stays as it was
    # asserted; the ``breaks`` set grows by the breaks Qt shows inside the paragraph.
    def test_a_table_header_directly_after_a_paragraph_line_is_never_joined(self):
        lines = ["日本", "| a | b |", "| --- | --- |", "| 本 | 語 |"]
        old_breaks: List[Tuple[int, int]] = (
            []
        )  # the earlier expectation, kept as a subset
        expect_plain(lines, [(1, 5), (2, 0), (3, 5)])
        page, result = run_ja(lines)
        assert set(old_breaks) <= set(summary(result))
        assert result.markdown == page  # the old claim: no line ending is removed
        assert not any(b.removed for b in result.breaks)
        assert len(result.breaks) == len(lines) - 1  # every line ending is examined
        again = sb.apply_soft_break_rule(result.markdown, "ja")  # idempotence
        assert again.markdown == result.markdown
        assert not any(b.removed for b in again.breaks)
        # control: with the header FIRST the same rows are a Qt table, and none is examined
        assert summary(run_ja(lines[1:])[1]) == []

    def test_a_table_after_a_two_line_paragraph_keeps_the_paragraph_break_only(self):
        lines = ["日本", "語", "| a | b |", "| --- | --- |", "| 本 | 語 |"]
        old_breaks = [(1, 2)]  # the earlier expectation, kept as a subset
        expect_plain(lines, [(1, 2), (2, 5), (3, 0), (4, 5)])
        page, result = run_ja(lines)
        assert set(old_breaks) <= set(summary(result))
        assert result.markdown == "日本語\n| a | b |\n| --- | --- |\n| 本 | 語 |\n"
        assert [b.line for b in result.breaks if b.removed] == [
            1
        ]  # the paragraph break only
        assert (
            len(result.breaks) == len(lines) - 1
        )  # one paragraph: every ending examined
        again = sb.apply_soft_break_rule(result.markdown, "ja")  # idempotence
        assert again.markdown == result.markdown
        assert not any(b.removed for b in again.breaks)
        # control: after a blank line the header is the paragraph's first line, so a table
        blank = ["日本", "語", "", "| a | b |", "| --- | --- |", "| 本 | 語 |"]
        assert summary(run_ja(blank)[1]) == [(1, 2)]

    def test_a_pipe_less_row_belongs_to_the_table(self):
        lines = ["| a | b |", "| --- | --- |", "| 本 | 語 |", "日本", "語"]
        expect_plain(lines, [])

    def test_a_table_ends_at_a_blank_line(self):
        lines = ["| a | b |", "| --- | --- |", "| 本 | 語 |", "", "日本", "語"]
        expect_plain(lines, [(5, 2)])

    def test_a_table_inside_a_block_quote(self):
        lines = ["> | a | b |", "> | --- | --- |", "> | 本 | 語 |"]
        expect_plain(lines, [])

    def test_a_delimiter_row_shape_is_not_a_table_without_a_header(self):
        # a lone delimiter-shaped line after text is a setext underline or text
        page, result = run_ja(["日本", "| --- | --- |"])
        assert result.markdown == page


class TestConstructHardBreaksAndBackslashes:
    def test_two_spaces_before_the_line_ending_is_a_hard_break(self):
        expect_plain(["日本  ", "語"], [])

    def test_three_spaces_is_a_hard_break(self):
        expect_plain(["日本   ", "語"], [])

    def test_one_space_is_not_a_hard_break(self):
        page, result = run_ja(["日本 ", "語"])
        assert result.markdown == "日本語\n"

    def test_a_tab_is_not_a_hard_break(self):
        page, result = run_ja(["日本\t", "語"])
        assert result.markdown == "日本語\n"

    def test_a_single_backslash_is_a_hard_break(self):
        expect_plain(["日本\\", "語"], [])

    def test_an_odd_run_of_backslashes_is_a_hard_break(self):
        expect_plain(["日本\\\\\\", "語"], [])
        expect_plain(["日本\\\\\\\\\\", "語"], [])

    def test_an_even_run_of_backslashes_is_an_escaped_backslash_and_the_break_stays_soft(
        self,
    ):
        page, result = run_ja(["日本\\\\", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "\\"
        assert result.markdown == page

    def test_four_backslashes_are_two_escaped_backslashes(self):
        page, result = run_ja(["日本\\\\\\\\", "語"])
        assert summary(result) == [(1, 5)]
        assert result.markdown == page

    def test_a_backslash_in_the_middle_of_a_line_is_text(self):
        page, result = run_ja(["日\\本", "語"])
        assert summary(result) == [(1, 2)]


class TestConstructInline:
    def test_a_line_ending_inside_a_code_span_is_not_a_candidate(self):
        expect_plain(["`日本", "語`"], [])
        expect_plain(["日本 `a", "b` 語"], [])

    def test_a_code_span_across_three_lines(self):
        expect_plain(["`日本", "語", "本`", "語"], [(3, 2)])

    def test_a_code_span_neighbour_is_its_last_or_first_character(self):
        page, result = run_ja(["`日本`", "語"])
        assert summary(result) == [(1, 2)]
        assert (result.breaks[0].before, result.breaks[0].after) == ("本", "語")
        assert result.markdown == "`日本`語\n"
        page, result = run_ja(["日本", "`語`"])
        assert (result.breaks[0].before, result.breaks[0].after) == ("本", "語")
        assert result.markdown == "日本`語`\n"

    def test_a_double_backtick_span_contains_a_single_backtick(self):
        expect_plain(["``日`本", "語``", "本"], [(2, 2)])

    def test_an_unmatched_backtick_is_text(self):
        expect_plain(["日`本", "語"], [(1, 2)])

    def test_a_line_ending_in_a_link_destination_or_title_is_not_a_candidate(self):
        expect_plain(["[日本](a.md", '"語")'], [])

    def test_a_break_inside_link_text_is_a_candidate(self):
        page, result = run_ja(["[日本", "語](a.md)"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == "[日本語](a.md)\n"

    def test_a_line_ending_inside_a_raw_html_tag_is_not_a_candidate(self):
        page, result = run_ja(["日本 <span", 'class="x">語</span>'])
        assert not [b for b in result.breaks if b.removed]
        assert result.markdown == page

    def test_an_html_comment_in_the_text_is_markup(self):
        page, result = run_ja(["日本<!-- c -->", "語"])
        assert len(result.breaks) == 1
        assert result.markdown == page or result.breaks[0].removed

    def test_a_break_beside_an_emphasis_run_judges_the_visible_character(self):
        page, result = run_ja(["日本**語**", "本"])
        assert (result.breaks[0].before, result.breaks[0].after) == ("語", "本")

    def test_a_literal_asterisk_run_is_visible_text(self):
        page, result = run_ja(["日本 *", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "*"

    def test_inline_text_spaces_are_never_removed(self):
        page, result = run_ja(["日本 語", "本 語"])
        assert result.markdown == "日本 語本 語\n"


class TestConstructEntityReferencesAreUndecided:
    """Entity and numeric references are recognised, never decoded (mutant M4)."""

    @pytest.mark.parametrize(
        "reference", ["&amp;", "&Abreve;", "&#32;", "&#x20;", "&nbsp;"]
    )
    def test_a_reference_before_the_break(self, reference):
        page, result = run_ja([f"日本{reference}", "語"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    @pytest.mark.parametrize(
        "reference", ["&amp;", "&Abreve;", "&#32;", "&#x20;", "&nbsp;"]
    )
    def test_a_reference_after_the_break(self, reference):
        page, result = run_ja(["日本", f"{reference}語"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_a_lone_ampersand_is_not_a_reference(self):
        page, result = run_ja(["日本&", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "&"

    def test_an_ampersand_without_a_semicolon_is_not_a_reference(self):
        page, result = run_ja(["日本&amp", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "p"

    def test_a_reference_in_the_middle_of_a_line_does_not_matter(self):
        page, result = run_ja(["日本&amp;語", "本"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == "日本&amp;語本\n"

    def test_html_is_never_consulted_for_a_name_qt_does_not_decode(self):
        page, result = run_ja(["日本&Abreve;", "語"])
        assert result.breaks[0].clause is CL[0]
        assert not result.breaks[0].removed


class TestFailSafeIsUndecided:
    """A candidate the scanner cannot classify is kept and counted."""

    def test_an_image_after_the_break(self):
        page, result = run_ja(["日本", "![ロゴ](logo.png)"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_an_image_before_the_break(self):
        page, result = run_ja(["![ロゴ](logo.png)", "日本"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_a_raw_html_tag_after_the_break(self):
        page, result = run_ja(["日本", "<b>語</b>"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_a_raw_html_tag_before_the_break(self):
        page, result = run_ja(["<b>日本</b>", "語"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_a_tab_inside_a_container_prefix(self):
        page, result = run_ja([">\t日本", ">\t語"])
        assert summary(result) == [(1, 0)]
        assert result.markdown == page

    def test_an_undecided_break_is_not_removed(self):
        item = sb.SoftBreak(line=1, before="", after="", clause=CL[0])
        assert item.removed is False

    def test_an_undecided_break_keeps_the_other_breaks_working(self):
        page, result = run_ja(["日本", "![x](y.png)", "", "日本", "語"])
        assert summary(result) == [(1, 0), (4, 2)]
        assert result.markdown == "日本\n![x](y.png)\n\n日本語\n"


class TestConstructLinksAndDefinitions:
    """Link syntax, in the inline pass and in link reference definitions (CommonMark 6.3, 4.7)."""

    def test_an_angle_bracket_destination_is_a_link(self):
        page, result = run_ja(["[日本](<a b.md>)", "語"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == "[日本](<a b.md>)語\n"

    def test_an_angle_bracket_destination_may_hold_an_escaped_bracket(self):
        page, result = run_ja(["[日本](<a\\>b.md>)", "語"])
        assert summary(result) == [(1, 2)]

    def test_an_angle_bracket_destination_that_holds_a_bracket_is_not_a_link(self):
        page, result = run_ja(["[日本](<a<b>)", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == ")"

    def test_a_destination_with_balanced_parentheses_is_a_link(self):
        page, result = run_ja(["[日本](a(b)c)", "語"])
        assert summary(result) == [(1, 2)]

    def test_a_destination_with_unbalanced_parentheses_is_not_a_link(self):
        page, result = run_ja(["[日本](a(b", "語"])
        assert summary(result) == [(1, 5)]

    def test_a_destination_with_an_escaped_parenthesis_is_a_link(self):
        page, result = run_ja(["[日本](a\\)b)", "語"])
        assert summary(result) == [(1, 2)]

    @pytest.mark.parametrize(
        "title",
        ['"t"', "'t'", "(t)", '"t\\"x"'],
        ids=["double", "single", "paren", "escaped-quote"],
    )
    def test_a_title_in_any_of_its_three_forms_belongs_to_the_link(self, title):
        page, result = run_ja([f"[日本](a.md {title})", "語"])
        assert summary(result) == [(1, 2)]
        assert result.markdown == f"[日本](a.md {title})語\n"

    def test_a_parenthesis_title_that_holds_a_parenthesis_is_not_a_title(self):
        page, result = run_ja(["[日本](a.md (t(x)))", "語"])
        assert summary(result) == [(1, 5)]

    def test_an_unterminated_title_makes_the_text_literal(self):
        page, result = run_ja(['[日本](a.md "t)', "語"])
        assert summary(result) == [(1, 5)]

    def test_a_stray_closing_bracket_is_visible_text(self):
        page, result = run_ja(["日本]", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "]"

    def test_a_link_inside_a_link_leaves_the_outer_brackets_literal(self):
        page, result = run_ja(["[日本 [語](a.md) 本](b.md)", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == ")"

    def test_an_image_inside_a_link_does_not_deactivate_it(self):
        page, result = run_ja(["[![x](y.png) 日本](a.md)", "語"])
        assert summary(result) == [(1, 2)]

    @pytest.mark.parametrize(
        ("use", "label"),
        [("[日本][ref]", "ref"), ("[日本][]", "日本"), ("[日本]", "日本")],
        ids=["full-reference", "collapsed-reference", "shortcut-reference"],
    )
    def test_a_reference_link_is_a_link_only_when_its_label_is_defined(
        self, use, label
    ):
        page, result = run_ja([use, "語", "", f"[{label}]: /url"])
        assert [(b.line, b.before, b.after) for b in result.breaks] == [(1, "本", "語")]
        undefined = sb.apply_soft_break_rule("\n".join([use, "語"]) + "\n", "ja")
        assert undefined.breaks[0].before == "]"
        assert undefined.breaks[0].clause is CL[5]

    def test_a_definition_after_the_paragraph_that_uses_it_still_counts(self):
        page, result = run_ja(["[日本][Ref]", "語", "", "[REF]: /url"])
        assert result.breaks[0].before == "本"

    def test_a_definition_with_the_destination_on_the_next_line_takes_it(self):
        page, result = run_ja(["[foo]:", "日本", "語"])
        assert result.breaks == ()
        assert result.markdown == page

    def test_a_definition_with_an_angle_bracket_destination(self):
        page, result = run_ja(["[foo]: <a b>", "日本", "語"])
        assert summary(result) == [(2, 2)]

    def test_a_definition_with_a_title_on_an_indented_next_line(self):
        page, result = run_ja(["[foo]: /url", '  "title"', "日本", "語"])
        assert summary(result) == [(3, 2)]

    def test_an_empty_label_is_not_a_definition(self):
        page, result = run_ja(["[]: /url", "日本"])
        assert summary(result) == [(1, 5)]

    def test_a_label_with_a_bracket_inside_is_not_a_definition(self):
        page, result = run_ja(["[a[b]: /url", "日本"])
        assert summary(result) == [(1, 5)]

    def test_a_label_may_hold_an_escaped_bracket(self):
        page, result = run_ja(["[a\\]b]: /url", "日本", "語"])
        assert summary(result) == [(2, 2)]

    def test_a_definition_followed_by_text_on_its_line_is_a_paragraph(self):
        page, result = run_ja(["[foo]: /url bar", "日本", "語"])
        assert summary(result) == [(1, 5), (2, 2)]

    def test_a_definition_with_a_destination_and_a_bad_title_line_is_the_destination_only(
        self,
    ):
        page, result = run_ja(["[foo]: /url", '"t" x', "日本"])
        assert summary(result) == [(2, 5)]

    def test_an_angle_bracket_destination_that_is_never_closed(self):
        page, result = run_ja(["語", "[日本](<a"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].after == "["

    def test_a_destination_nested_deeper_than_the_limit_is_not_a_link(self):
        depth = C.GUIDE_MD_MAX_PAREN_DEPTH + 1
        page, result = run_ja(["[日本](" + "(" * depth + ")" * depth + ")", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == ")"

    def test_a_definition_with_a_bad_angle_bracket_destination_is_a_paragraph(self):
        page, result = run_ja(["[foo]: <a<b>", "日本"])
        assert len(result.breaks) == 1
        assert not result.breaks[0].removed

    def test_a_reference_label_that_is_never_closed_is_literal(self):
        page, result = run_ja(["[日本][ref", "語"])
        assert summary(result) == [(1, 5)]

    def test_a_link_inside_an_image_leaves_the_image_brackets_alone(self):
        page, result = run_ja(["![日本 [語](a.md) 本](b.png)", "語"])
        assert len(result.breaks) == 1
        assert not result.breaks[0].removed

    def test_a_definition_title_followed_by_text_on_its_line_is_a_paragraph(self):
        page, result = run_ja(['[foo]: /url "t" x', "日本"])
        assert summary(result) == [(1, 5)]


class TestConstructCodeSpansAndDelimiters:
    def test_a_code_span_with_a_space_each_side_loses_one_of_each(self):
        page, result = run_ja(["`` 日本 ``", "語"])
        assert summary(result) == [(1, 2)]
        assert result.breaks[0].before == "本"

    def test_a_strikethrough_run_that_does_not_match_stays_literal(self):
        page, result = run_ja(["~日本~~", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "~"

    def test_a_strikethrough_run_of_three_is_not_strikethrough(self):
        page, result = run_ja(["日本~~~本~~~", "語"])
        assert result.breaks[0].before == "~"

    def test_unmatched_underscores_are_visible(self):
        page, result = run_ja(["日本_", "語"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == "_"

    def test_intraword_underscores_do_not_emphasise(self):
        page, result = run_ja(["foo_bar_", "語"])
        assert result.breaks[0].before == "_"


class TestDecideArguments:
    """``decide`` is for two single characters; anything else is undecided."""

    @pytest.mark.parametrize(
        ("before", "after"), [("", "a"), ("a", ""), ("ab", "c"), ("a", "bc"), ("", "")]
    )
    def test_not_two_single_characters_is_undecided(self, before, after):
        assert d(before, after, "ja") is CL[0]


class TestEmojiTableGuard:
    """The module refuses to import without the whole Emoji table (fail loudly)."""

    @staticmethod
    def _exec_probe(monkeypatch, name):
        import importlib.util

        spec = importlib.util.spec_from_file_location(name, module_source_path(sb))
        assert spec is not None and spec.loader is not None
        probe = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, probe)
        spec.loader.exec_module(probe)

    def test_an_empty_table_refuses_to_import(self, monkeypatch):
        monkeypatch.setattr(C, "GUIDE_EMOJI_TOTAL_ELEMENTS", EMOJI_TOTAL)
        monkeypatch.setattr(C, "GUIDE_EMOJI_RANGES", ())
        with pytest.raises(RuntimeError, match="incomplete or was edited"):
            self._exec_probe(monkeypatch, "softbreak_guard_probe_empty")

    def test_a_partial_table_refuses_to_import(self, monkeypatch):
        monkeypatch.setattr(C, "GUIDE_EMOJI_TOTAL_ELEMENTS", EMOJI_TOTAL)
        monkeypatch.setattr(C, "GUIDE_EMOJI_RANGES", ((0x1F600, 0x1F64F),))
        with pytest.raises(RuntimeError, match="1424"):
            self._exec_probe(monkeypatch, "softbreak_guard_probe_partial")


# Two defects were found by this suite's first runs and are now STRICT regression cases:
# two code spans and two reference links (``TestRegressionTwoCodeSpans`` and
# ``TestRegressionTwoReferenceLinks`` in ``test_guide_softbreak_join.py``): the exact
# joined source is asserted, and neither the plain join nor the kept source is accepted.


# A third defect (the transform was not idempotent on a delimiter-shaped line that the
# same pass rewrote) was found by the property run and is now a STRICT regression case,
# ``TestRegressionDelimiterShapedLine`` in ``test_guide_softbreak_tablemodel.py``: the
# source is kept byte for byte, the three breaks are UNDECIDED, and a second pass is a
# no-op.


def page_of_lines(lines):
    """The page of ``lines``, each followed by one line feed."""
    return "\n".join(lines) + "\n"


def join_with_joiner(lines):
    """Two lines joined by the joiner and a final line ending."""
    return JOINER.join(lines) + "\n"


# ===========================================================================
# 6. The join: spaces, tabs, U+3000, line endings, the joiner
# ===========================================================================


class TestJoin:
    def test_only_u0020_and_u0009_belong_to_the_break(self):
        page, result = run_ja(["日本 \t ", "\t  語"])
        assert result.markdown == "日本語\n"

    def test_trailing_ideographic_space_is_a_character_not_a_break_space(self):
        page, result = run_ja(["日本　", "語"])
        assert summary(result) == [(1, 2)]
        assert result.breaks[0].before == "　"
        assert result.markdown == "日本　語\n"

    def test_leading_ideographic_space_is_a_character_not_a_break_space(self):
        page, result = run_ja(["日本", "　語"])
        assert result.breaks[0].after == "　"
        assert result.markdown == "日本　語\n"

    def test_no_break_space_is_a_character(self):
        page, result = run_ja(["Hello ", "world"])
        assert summary(result) == [(1, 5)]
        assert result.breaks[0].before == " "
        assert result.markdown == page

    def test_a_kept_break_is_returned_byte_for_byte_with_its_spaces(self):
        page = "Hello \t \n\t  world\n"
        result = sb.apply_soft_break_rule(page, "en")
        assert result.markdown == page

    def test_a_page_with_no_removal_is_returned_byte_for_byte(self):
        page = (
            "# Title\n\nHello\nworld\n\n- a\n  b\n\n| a | b |\n| - | - |\n| 1 | 2 |\n"
        )
        assert sb.apply_soft_break_rule(page, "en").markdown == page

    def test_the_last_line_ending_is_never_a_candidate(self):
        page, result = run_ja(["日本"])
        assert result.breaks == ()
        assert result.markdown == page

    def test_a_page_without_a_final_line_ending(self):
        result = sb.apply_soft_break_rule("日本\n語", "ja")
        assert result.markdown == "日本語"

    def test_empty_and_blank_pages(self):
        assert sb.apply_soft_break_rule("", "ja").markdown == ""
        assert sb.apply_soft_break_rule("", "ja").breaks == ()
        assert sb.apply_soft_break_rule("\n\n", "ja").markdown == "\n\n"
        assert sb.apply_soft_break_rule("   \n", "ja").markdown == "   \n"

    def test_reported_line_numbers_refer_to_the_original_source(self):
        page, result = run_ja(["日本", "語", "本", "", "# H", "日本", "語"])
        assert summary(result) == [(1, 2), (2, 2), (6, 2)]
        assert result.markdown == "日本語本\n\n# H\n日本語\n"

    def test_three_lines_join_to_one(self):
        page, result = run_ja(["日本", "語", "本"])
        assert result.markdown == "日本語本\n"

    def test_a_kept_break_between_two_removed_ones(self):
        page, result = run_ja(["日本", "語", "Hello", "world", "本", "語"])
        assert summary(result) == [(1, 2), (2, 5), (3, 5), (4, 5), (5, 2)]
        assert result.markdown == "日本語\nHello\nworld\n本語\n"

    def test_clause_one_keeps_the_zero_width_space(self):
        page, result = run_ja(["日本" + ZWSP, "語"])
        assert result.markdown == "日本" + ZWSP + "語\n"


class TestJoiner:
    """The joiner appears only beside *, _ or ~, and keeps the emphasis."""

    @pytest.mark.parametrize(
        ("lines", "expected"),
        [
            (["**移動。**", "を選ぶ"], "**移動。**<!---->を選ぶ\n"),
            (["を選ぶ", "**移動。**"], "を選ぶ<!---->**移動。**\n"),
            (["_日本_", "語"], "_日本_<!---->語\n"),
            (["日本", "_語_"], "日本<!---->_語_\n"),
            (["~~日本~~", "語"], "~~日本~~<!---->語\n"),
            (["日本", "~~語~~"], "日本<!---->~~語~~\n"),
            (["*日本*", "語"], "*日本*<!---->語\n"),
            (["**日本** ", "語"], "**日本**<!---->語\n"),
            (["日本", "  **語**"], "日本<!---->**語**\n"),
        ],
    )
    def test_the_joiner_goes_beside_a_delimiter(self, lines, expected):
        page, result = run_ja(lines)
        assert result.markdown == expected

    def test_a_delimiter_on_both_sides_gets_one_joiner(self):
        page, result = run_ja(["**日本**", "**語**"])
        assert result.markdown == "**日本**<!---->**語**\n"
        assert result.markdown.count(JOINER) == 1

    def test_the_flanking_regression_case_keeps_the_closing_run_right_flanking(self):
        # Joined plainly, **移動。**を選ぶ shows literal ** (research: measured on Qt).
        page, result = run_ja(["**移動。**", "を選ぶ"])
        assert "**移動。**を選ぶ" not in result.markdown
        assert result.markdown.count(JOINER) == 1

    def test_no_joiner_without_a_delimiter(self):
        page, result = run_ja(["日本", "語", "本"])
        assert JOINER not in result.markdown

    def test_no_joiner_beside_a_link_or_a_code_span(self):
        page, result = run_ja(["[レイヤー](a.md)", "を選ぶ"])
        assert JOINER not in result.markdown
        page, result = run_ja(["`日本`", "語"])
        assert JOINER not in result.markdown

    def test_no_joiner_when_the_break_is_kept(self):
        page, result = run_ja(["**Delete**", "は同じ"])
        assert result.markdown == page

    def test_a_joiner_is_idempotent_on_a_second_pass(self):
        first = sb.apply_soft_break_rule("**移動。**\nを選ぶ\n", "ja")
        second = sb.apply_soft_break_rule(first.markdown, "ja")
        assert second.markdown == first.markdown


class TestLineEndings:
    """LF, CR and CRLF are line endings; a removed break takes the whole ending."""

    PAGE_LINES = [
        "# 見出し",
        "",
        "日本",
        "語",
        "",
        "Hello",
        "world",
        "",
        "```",
        "日本",
        "語",
        "```",
        "",
        "日本  ",
        "語",
        "",
        "> 引用",
        "> 語",
        "",
        "- 項目",
        "  語",
        "",
    ]

    @pytest.mark.parametrize("ending", ["\r\n", "\r"])
    def test_the_decisions_and_the_text_are_the_same_as_in_lf(self, ending):
        lf = sb.apply_soft_break_rule("\n".join(self.PAGE_LINES), "ja")
        other = sb.apply_soft_break_rule(ending.join(self.PAGE_LINES), "ja")
        assert summary(other) == summary(lf)
        assert [(b.before, b.after) for b in other.breaks] == [
            (b.before, b.after) for b in lf.breaks
        ]
        assert other.markdown == lf.markdown.replace("\n", ending)

    def test_a_removed_break_removes_the_whole_crlf(self):
        result = sb.apply_soft_break_rule("日本\r\n語\r\n", "ja")
        assert result.markdown == "日本語\r\n"
        assert "\n" not in result.markdown.replace("\r\n", "")

    def test_a_removed_break_removes_a_lone_cr(self):
        result = sb.apply_soft_break_rule("日本\r語\r", "ja")
        assert result.markdown == "日本語\r"

    def test_a_kept_break_keeps_its_ending_byte_for_byte(self):
        for ending in ("\n", "\r\n", "\r"):
            page = f"Hello{ending}world{ending}"
            assert sb.apply_soft_break_rule(page, "ja").markdown == page

    def test_mixed_endings_in_one_page(self):
        page = "日本\r\n語\nHello\rworld\r\n本\r語\n"
        result = sb.apply_soft_break_rule(page, "ja")
        assert result.markdown == "日本語\nHello\rworld\r\n本語\n"
        assert summary(result) == [(1, 2), (2, 5), (3, 5), (4, 5), (5, 2)]

    def test_a_blank_line_made_of_crlf_is_a_paragraph_break(self):
        page = "日本\r\n\r\n語\r\n"
        assert sb.apply_soft_break_rule(page, "ja").markdown == page

    def test_a_hard_break_before_crlf(self):
        page = "日本  \r\n語\r\n"
        assert sb.apply_soft_break_rule(page, "ja").markdown == page

    def test_a_backslash_hard_break_before_crlf(self):
        page = "日本\\\r\n語\r\n"
        assert sb.apply_soft_break_rule(page, "ja").markdown == page


class TestRobustness:
    """The module raises nothing for any str and has no I/O."""

    @given(st.text(max_size=400), LANGUAGES)
    def test_any_text_returns_a_result(self, text, language):
        result = sb.apply_soft_break_rule(text, language)
        assert isinstance(result.markdown, str)
        assert isinstance(result.breaks, tuple)

    @given(
        st.text(alphabet="`*_~[]()<>!&;#\\\n\r\t |-=:.日本語한A1​　", max_size=200),
        LANGUAGES,
    )
    def test_any_structural_text_returns_a_result(self, text, language):
        result = sb.apply_soft_break_rule(text, language)
        assert isinstance(result.markdown, str)
        for item in result.breaks:
            assert item.line >= 1
            assert isinstance(item.clause, sb.SoftBreakClause)

    @given(st.text(max_size=300), LANGUAGES)
    def test_a_page_with_no_removed_break_is_returned_unchanged(self, text, language):
        result = sb.apply_soft_break_rule(text, language)
        if not any(b.removed for b in result.breaks):
            assert result.markdown == text


# ===========================================================================
# 7. Properties P1 to P3 and P6 over generated pages
# ===========================================================================

FRAGMENTS = [
    "日本",
    "語",
    "ファイル",
    "を開く",
    "图层",
    "Hello",
    "world",
    "選択",
    "한국어",
    "レイヤー",
    "**移動**",
    "_強調_",
    "~~消す~~",
    "`code`",
    "[リンク](a.md)",
    "、",
    "。",
    "“",
    "”",
    "…",
    "​",
    "1",
    "A",
    " ",
    "  ",
    "\t",
    "　",
    "- 項目",
    "> 引用",
    "1. 順",
    "2. 順",
    "# 見出し",
    "```",
    "~~~",
    "| a | b |",
    "| - | - |",
    "    code",
    "",
    "日本  ",
    "語\\",
    "&amp;",
    "![x](y.png)",
    "<b>",
    "***",
    "===",
    "---",
    "[ref]: /url",
    "+",
    "<!-- c -->",
    # The shapes the joiner and the three guards are about
    "[x](日",
    "本)",
    "<http://日",
    "本>",
    "<a href=日",
    "https://example.com/a",
    "www.example.com",
    "a@example.com",
    "|-|-|",
    "a|日",
    "[日]",
    "[本]",
    "[日]: /a",
    "[本]: /b",
    "[日本]: /x",
    "[日 本]: /x",
    "``本``",
    "!",
    "]",
    "(",
    ":",
]


@st.composite
def pages(draw):
    count = draw(st.integers(min_value=1, max_value=12))
    lines = []
    for _ in range(count):
        parts = draw(st.lists(st.sampled_from(FRAGMENTS), min_size=0, max_size=3))
        lines.append(draw(st.sampled_from(["", " ", "  "])) + "".join(parts))
    ending = draw(st.sampled_from(["\n", "\n", "\n", "\r\n", "\r"]))
    tail = draw(st.sampled_from(["", ending]))
    return ending.join(lines) + tail


def _subsequence_deleted(source: str, produced: str) -> Tuple[bool, str]:
    """Is ``produced`` a subsequence of ``source``? Also return the deleted characters."""
    deleted = []
    index = 0
    for char in source:
        if index < len(produced) and produced[index] == char:
            index += 1
        else:
            deleted.append(char)
    return index == len(produced), "".join(deleted)


@settings(max_examples=300)
@given(pages(), LANGUAGES)
def test_p1_only_whitespace_line_endings_and_container_prefix_are_deleted(
    page, language
):
    result = sb.apply_soft_break_rule(page, language)
    assert JOINER not in page
    produced = result.markdown.replace(JOINER, "")
    ok, deleted = _subsequence_deleted(page, produced)
    assert (
        ok
    ), "the output is not the input with characters deleted and the joiner inserted"
    assert set(deleted) <= set(
        " \t\n\r>"
    ), f"deleted {set(deleted) - set(' \t\n\r>')!r}"
    # the joiner is the only insertion, and at most one per removed break
    assert result.markdown.count(JOINER) <= sum(1 for b in result.breaks if b.removed)


#: The joiner pairs beside backticks and brackets, written here as literals and not read from the module.
TRIGGER_PAIRS = {("`", "`"), ("]", "("), ("]", "["), ("]", ":"), ("!", "[")}


def joiner_contexts(text: str) -> List[Tuple[str, str]]:
    """``(left, right)`` characters around every joiner of ``text``."""
    found = []
    start = text.find(JOINER)
    while start != -1:
        before = text[start - 1] if start else ""
        end = start + len(JOINER)
        after = text[end] if end < len(text) else ""
        found.append((before, after))
        start = text.find(JOINER, end)
    return found


@settings(max_examples=400)
@given(pages(), LANGUAGES)
def test_p1_a_joiner_sits_only_where_the_pair_rules_put_it(page, language):
    """The joiner is the only insertion, and only beside *, _, ~ or a trigger pair."""
    assert JOINER not in page
    result = sb.apply_soft_break_rule(page, language)
    for left, right in joiner_contexts(result.markdown):
        assert (
            left in "*_~" or right in "*_~" or (left, right) in TRIGGER_PAIRS
        ), f"a joiner between {left!r} and {right!r}"


@settings(max_examples=300)
@given(pages(), LANGUAGES)
def test_p1_each_removed_break_removes_exactly_one_line_ending(page, language):
    result = sb.apply_soft_break_rule(page, language)
    removed = sum(1 for b in result.breaks if b.removed)
    endings_in = len(re.findall(r"\r\n|\r|\n", page))
    endings_out = len(re.findall(r"\r\n|\r|\n", result.markdown))
    assert endings_in - endings_out == removed


@settings(max_examples=300)
@given(pages(), LANGUAGES)
def test_p2_the_transform_is_idempotent(page, language):
    once = sb.apply_soft_break_rule(page, language)
    twice = sb.apply_soft_break_rule(once.markdown, language)
    assert twice.markdown == once.markdown


#: Lines of the shapes the guards keep, and of the pairs the joiner joins.
JOINER_GUARD_LINES = [
    "[x](日",
    "本)",
    "<http://日",
    "本>",
    "<a href=日",
    "本>x",
    "[日",
    "本]",
    "[日本]: /x",
    "[日 本]: /x",
    "https://example.com/a",
    "www.example.com",
    "a@example.com",
    "。",
    "、日",
    "日。",
    "a|日",
    "本|",
    "|-|-|",
    "`日`",
    "`本`",
    "``本``",
    "[日]",
    "[本]",
    "[日]: /a",
    "[本]: /b",
    "日",
    "本",
    "*日*",
    "_本_",
    "日!",
    "[" + ZWSP + "本](/x)",
    ZWSP + "本",
    "日" + ZWSP,
]


@st.composite
def joiner_guard_pages(draw):
    lines = draw(
        st.lists(st.sampled_from(JOINER_GUARD_LINES + [""]), min_size=1, max_size=9)
    )
    return "\n".join(lines) + "\n"


@settings(max_examples=500)
@given(joiner_guard_pages(), LANGUAGES)
def test_p2_the_transform_is_idempotent_over_pages_the_guards_keep_in_part(
    page, language
):
    once = sb.apply_soft_break_rule(page, language)
    twice = sb.apply_soft_break_rule(once.markdown, language)
    assert twice.markdown == once.markdown
    assert not any(b.removed for b in twice.breaks)


@settings(max_examples=500)
@given(joiner_guard_pages(), LANGUAGES)
def test_p1_joiner_guard_pages_delete_only_whitespace_and_line_endings(page, language):
    result = sb.apply_soft_break_rule(page, language)
    produced = result.markdown.replace(JOINER, "")
    ok, deleted = _subsequence_deleted(page, produced)
    assert ok
    assert set(deleted) <= set(" \t\n\r>")
    for left, right in joiner_contexts(result.markdown):
        assert left in "*_~" or right in "*_~" or (left, right) in TRIGGER_PAIRS


@settings(max_examples=300)
@given(pages())
def test_p3_the_breaks_removed_in_english_are_removed_in_japanese(page):
    english = sb.apply_soft_break_rule(page, "en")
    japanese = sb.apply_soft_break_rule(page, "ja")
    assert [b.line for b in english.breaks] == [b.line for b in japanese.breaks]
    removed_en = {b.line for b in english.breaks if b.removed}
    removed_ja = {b.line for b in japanese.breaks if b.removed}
    assert removed_en <= removed_ja


@settings(max_examples=200)
@given(pages())
def test_p3_korean_and_english_remove_the_same_breaks(page):
    korean = sb.apply_soft_break_rule(page, "ko")
    english = sb.apply_soft_break_rule(page, "en")
    assert korean.markdown == english.markdown


@settings(max_examples=300)
@given(pages(), LANGUAGES)
def test_p4_no_hangul_break_is_removed_by_a_clause_other_than_one(page, language):
    result = sb.apply_soft_break_rule(page, language)
    for item in result.breaks:
        if item.removed and (is_hangul(item.before) or is_hangul(item.after)):
            assert item.clause is CL[1]


@settings(max_examples=300)
@given(pages(), LANGUAGES)
def test_every_examined_break_agrees_with_decide_and_the_oracle(page, language):
    result = sb.apply_soft_break_rule(page, language)
    for item in result.breaks:
        if item.clause is CL[0]:
            continue
        if any(
            c in EMOJI_ORACLE and not c.isascii() for c in (item.before, item.after)
        ):
            continue
        assert item.clause is sb.decide(item.before, item.after, language)
        assert number(item) == oracle_clause(item.before, item.after, language)


# --- P6: documents generated from a grammar know where their breaks are --------

WORDS = [
    "日本",
    "語",
    "ファイル",
    "を開く",
    "图层",
    "Hello",
    "world",
    "選択",
    "한국어",
    "123",
]


@st.composite
def text_line(draw):
    words = draw(st.lists(st.sampled_from(WORDS), min_size=1, max_size=3))
    line = draw(st.sampled_from(["", " "])).join(words)
    wrap = draw(st.sampled_from(["", "", "**", "_", "~~", "[]", "`", "ref", "url"]))
    if wrap == "[]":
        return f"[{line}](p.md)"
    if wrap == "ref":
        return draw(st.sampled_from(["[日]", "[本]"]))
    if wrap == "url":
        return "https://example.com/" + line.replace(" ", "")
    return f"{wrap}{line}{wrap}"


@st.composite
def block(draw):
    """Return ``(lines, candidate offsets)``: offsets are 0-based line indexes with a candidate."""
    kind = draw(
        st.sampled_from(
            [
                "paragraph",
                "list",
                "ordered",
                "quote",
                "codespan",
                "fence",
                "indented",
                "hard",
                "table",
                "heading",
            ]
        )
    )
    count = draw(st.integers(min_value=1, max_value=4))
    body = [draw(text_line()) for _ in range(count)]
    if kind == "paragraph":
        return body, list(range(count - 1))
    if kind == "list":
        lines = ["- " + body[0]] + ["  " + t for t in body[1:]]
        return lines, list(range(count - 1))
    if kind == "ordered":
        lines = ["1. " + body[0]] + ["   " + t for t in body[1:]]
        return lines, list(range(count - 1))
    if kind == "quote":
        return ["> " + t for t in body], list(range(count - 1))
    if kind == "codespan":
        # lines: body, "`a", "b`", body: the break inside the span is not a candidate
        lines = body + ["前 `日本", "語` 後"] + [draw(text_line())]
        return lines, list(range(len(body))) + [len(body) + 1]
    if kind == "fence":
        return ["```"] + body + ["```"], []
    if kind == "indented":
        # eight spaces: code even directly after a list item (content column 2 or 3)
        return [" " * 8 + t for t in body], []
    if kind == "hard":
        marks = [draw(st.sampled_from(["  ", "\\", ""])) for _ in range(count)]
        lines = [t + m for t, m in zip(body, marks)]
        return lines, [i for i in range(count - 1) if marks[i] == ""]
    if kind == "table":
        return ["| a | b |", "| --- | --- |", "| 日本 | 語 |"], []
    return ["# " + body[0]], []


@st.composite
def grammar_page(draw):
    blocks = draw(st.lists(block(), min_size=1, max_size=5))
    lines: List[str] = []
    expected: List[int] = []
    for index, (block_lines, offsets) in enumerate(blocks):
        if index:
            lines.append("")
        start = len(lines)
        expected.extend(start + offset + 1 for offset in offsets)
        lines.extend(block_lines)
    # the reference links of the "ref" lines are always defined, after the blocks
    lines.extend(["", "[日]: /a", "[本]: /b"])
    return "\n".join(lines) + "\n", expected


@settings(max_examples=300)
@given(grammar_page(), st.sampled_from(["ja", "zh_CN", "en", "ko"]))
def test_p6_generated_documents_have_exactly_the_constructed_breaks(
    generated, language
):
    page, expected = generated
    result = sb.apply_soft_break_rule(page, language)
    assert [b.line for b in result.breaks] == expected
    if "://" not in page:
        # only a bare URL can make the permissive-link guard keep a break in this grammar
        assert not [b for b in result.breaks if b.clause is CL[0]]


# ===========================================================================
# 8. content_ref_locale (guide_model)
# ===========================================================================

REF_SEGMENT = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs", "Cc"), blacklist_characters="/\\"
    ),
    min_size=1,
    max_size=8,
).filter(lambda s: s.strip() != "")


class TestContentRefLocale:
    def test_the_function_is_in_guide_model(self):
        assert callable(guide_model.content_ref_locale)

    @pytest.mark.parametrize("locale", ALL_LOCALES)
    def test_flat_stem_round_trip(self, locale):
        path = guide_model.content_ref_path("layers", locale)
        assert guide_model.content_ref_locale(path) == locale

    def test_nested_stem_round_trip(self):
        path = guide_model.content_ref_path("reference/layers", "zh_CN")
        assert guide_model.content_ref_locale(path) == "zh_CN"

    @given(
        st.lists(REF_SEGMENT, min_size=1, max_size=3).map("/".join),
        st.sampled_from(list(ALL_LOCALES)),
    )
    def test_property_inverse_of_content_ref_path(self, ref, locale):
        assert (
            guide_model.content_ref_locale(guide_model.content_ref_path(ref, locale))
            == locale
        )

    @given(st.lists(REF_SEGMENT, min_size=1, max_size=3).map("/".join), REF_SEGMENT)
    def test_property_inverse_for_any_locale_segment(self, ref, locale):
        assert (
            guide_model.content_ref_locale(guide_model.content_ref_path(ref, locale))
            == locale
        )

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "content",
            "content/",
            "content/ja",
            "content/ja/",
            "content/ja/.md",
            "content//layers.md",
            "content/ja//layers.md",
            "content/ja/layers",
            "content/ja/layers.txt",
            "content/ja/layers.md/",
            "/content/ja/layers.md",
            "other/ja/layers.md",
            "Content/ja/layers.md",
            "ja/layers.md",
            "layers.md",
            "content" + BACKSLASH + "ja" + BACKSLASH + "layers.md",
            "  ",
        ],
    )
    def test_every_other_shape_raises(self, bad):
        with pytest.raises(guide_model.GuideModelError):
            guide_model.content_ref_locale(bad)

    @pytest.mark.parametrize("bad", [None, 3, b"content/ja/x.md", ["content/ja/x.md"]])
    def test_a_non_string_raises(self, bad):
        with pytest.raises(guide_model.GuideModelError):
            guide_model.content_ref_locale(bad)  # type: ignore[arg-type]


# ===========================================================================
# 9. The tracked trees: discovery, the floors, the guard, the planted control
# ===========================================================================


@pytest.fixture
def scratch(tmp_path_factory):
    """A private folder under the configured temp root, removed after the test."""
    folder = make_scratch(tmp_path_factory.mktemp("softbreak-fallback"))
    try:
        yield folder
    finally:
        remove_scratch(folder)


def judged_trees() -> Dict[str, List[str]]:
    """The tracked trees of the product repository, or a clear failure."""
    try:
        return tracked_trees(REPO_ROOT)
    except GitListingError as error:
        pytest.fail(str(error), pytrace=False)
        raise  # unreachable


class TestTrackedTreeDiscovery:
    """Shipped means git-tracked; an untracked tree is not judged."""

    def test_the_guard_passes_on_the_real_repository(self):
        tracked = judged_trees()
        problems = guard_problems(tracked, REQUIRED_NON_CJK_TREES, REQUIRED_CJ_TREES)
        assert not problems, "\n".join(problems)

    def test_untracked_trees_are_printed_as_not_judged(self, capsys):
        tracked = judged_trees()
        with capsys.disabled():
            for locale in untracked_present(REPO_ROOT, tracked):
                print(f"[softbreak] {locale}: present, untracked, not judged")
            for locale in ALL_LOCALES:
                print(f"[softbreak] {locale}: {len(tracked[locale])} tracked pages")

    def test_the_required_floors_name_only_locales_of_their_family(self):
        assert set(REQUIRED_NON_CJK_TREES) <= set(NON_CJK_LOCALES)
        assert set(REQUIRED_CJ_TREES) <= set(CJ_LOCALES)

    def test_the_non_cjk_floor_is_never_empty(self):
        assert REQUIRED_NON_CJK_TREES

    def test_git_that_cannot_list_fails_with_a_message_and_never_passes(self, scratch):
        not_a_repo = scratch / "plain"
        not_a_repo.mkdir()
        env = {
            "GIT_CEILING_DIRECTORIES": str(scratch),
            "GIT_DIR": str(scratch / "no-such.git"),
        }
        with pytest.raises(
            GitListingError, match="cannot list the git-tracked guide pages"
        ):
            git_tracked_pages(not_a_repo, "ja", env=env)

    def test_a_missing_git_executable_fails_with_a_message(self, scratch):
        with pytest.raises(GitListingError, match="git could not run"):
            git_tracked_pages(scratch, "ja", git="git-that-does-not-exist")


class TestGuardLogic:
    """The pure guard, on constructed inputs (no repository)."""

    def tracked(self, **trees):
        base = {loc: [] for loc in ALL_LOCALES}
        base.update({loc: [f"{loc}/a.md"] for loc in trees})
        return base

    def test_a_tracked_tree_without_its_line_fails_and_names_the_locale(self):
        problems = guard_problems(self.tracked(en=1, ja=1), ("en",), ())
        assert any(p.startswith("ja:") for p in problems)

    def test_a_line_without_a_tracked_tree_fails_and_names_the_locale(self):
        problems = guard_problems(self.tracked(en=1), ("en", "fr"), ())
        assert any(p.startswith("fr:") for p in problems)

    def test_a_matching_state_passes(self):
        assert not guard_problems(self.tracked(en=1, ja=1), ("en",), ("ja",))

    def test_a_locale_in_the_wrong_family_tuple_fails(self):
        assert guard_problems(self.tracked(ja=1), (), ("ja", "ko"))
        assert guard_problems(self.tracked(en=1), ("en", "ja"), ())

    def test_an_empty_tracked_tree_does_not_count_as_tracked(self):
        assert not guard_problems({loc: [] for loc in ALL_LOCALES}, (), ())

    def test_a_locale_that_exists_in_neither_family_fails(self):
        assert guard_problems(self.tracked(), ("xx",), ())
        assert guard_problems(self.tracked(), (), ("xx",))


class TestPlantedTreeControl:
    """A temporary repository with ja committed and zh_CN untracked ."""

    @pytest.fixture
    def planted(self, scratch):
        root, env = make_planted_repo(scratch)
        return root, env

    def test_discovery_returns_ja_only(self, planted):
        root, env = planted
        found = {
            loc: pages for loc, pages in tracked_trees(root, env=env).items() if pages
        }
        assert list(found) == ["ja"]
        assert found["ja"] == [f"{TREE_REL}/ja/a.md"]

    def test_the_untracked_tree_is_reported_as_not_judged(self, planted):
        root, env = planted
        tracked = tracked_trees(root, env=env)
        assert untracked_present(root, tracked) == ["zh_CN"]

    def test_guard_fails_for_the_empty_tuple_and_names_ja(self, planted):
        root, env = planted
        problems = guard_problems(tracked_trees(root, env=env), (), ())
        assert problems and all(p.startswith("ja:") for p in problems)

    def test_guard_passes_for_ja_alone(self, planted):
        root, env = planted
        assert not guard_problems(tracked_trees(root, env=env), (), ("ja",))

    def test_guard_fails_for_ja_and_zh_cn_and_names_zh_cn(self, planted):
        root, env = planted
        problems = guard_problems(tracked_trees(root, env=env), (), ("ja", "zh_CN"))
        assert problems and all(p.startswith("zh_CN:") for p in problems)

    def test_the_control_repository_is_gone_after_the_test(self, scratch):
        root, _env = make_planted_repo(scratch)
        assert root.exists()
        remove_scratch(scratch)
        assert not scratch.exists()
        scratch.mkdir()  # the fixture's own teardown removes it again


# --- the non-CJK trees ------------------------------------------------


def non_cjk_text_violations(name: str, text: str, locale: str) -> List[str]:
    """Breaks removed on a non-CJK page that do not have U+200B on one side."""
    out = []
    for item in sb.apply_soft_break_rule(text, locale).breaks:
        if item.removed and ZWSP not in (item.before, item.after):
            out.append(
                f"{name}:{item.line}: {item.clause.value} removed a break with no U+200B beside it"
            )
    return out


def non_cjk_findings(trees: Dict[str, List[str]]) -> Tuple[List[str], Dict[str, dict]]:
    """Run the rule over the listed non-CJK trees; return violations and statistics."""
    violations: List[str] = []
    stats: Dict[str, dict] = {}
    for locale, pages in trees.items():
        entry = {
            "pages": 0,
            "removed": 0,
            "identical": 0,
            "hangul_hangul": 0,
            "candidates": 0,
            "per_page": [],
        }
        for relative in pages:
            text = read_page(REPO_ROOT, relative)
            result = sb.apply_soft_break_rule(text, locale)
            entry["pages"] += 1
            entry["candidates"] += len(result.breaks)
            entry["identical"] += result.markdown == text
            entry["per_page"].append(
                (relative, result.markdown == text, len(result.breaks))
            )
            violations.extend(non_cjk_text_violations(relative, text, locale))
            for item in result.breaks:
                if is_hangul(item.before) and is_hangul(item.after):
                    entry["hangul_hangul"] += 1
                if item.removed:
                    entry["removed"] += 1
        stats[locale] = entry
    return violations, stats


class TestNonCjkTrees:
    """Non-CJK trees change only beside U+200B (source-level half)."""

    def listed(self) -> Dict[str, List[str]]:
        tracked = judged_trees()
        locales = sorted(
            set(REQUIRED_NON_CJK_TREES)
            | {loc for loc in NON_CJK_LOCALES if tracked[loc]}
        )
        return {loc: tracked[loc] for loc in locales}

    def test_every_removed_break_has_u200b_on_one_side(self, capsys):
        trees = self.listed()
        violations, stats = non_cjk_findings(trees)
        with capsys.disabled():
            for locale, entry in stats.items():
                for relative, identical, examined in entry["per_page"]:
                    print(
                        f"[softbreak][non-CJK] {relative}: byte-identical {identical}, "
                        f"candidates {examined}"
                    )
                print(
                    f"[softbreak][non-CJK] {locale}: pages {entry['pages']}, candidates "
                    f"{entry['candidates']}, removed {entry['removed']}, byte-identical "
                    f"{entry['identical']}/{entry['pages']}, Hangul-Hangul {entry['hangul_hangul']}"
                )
        assert not violations, "\n".join(violations)

    def test_pages_per_language_are_non_zero_for_each_listed_tree(self):
        _violations, stats = non_cjk_findings(self.listed())
        assert set(REQUIRED_NON_CJK_TREES) <= set(stats)
        for locale, entry in stats.items():
            assert entry["pages"] > 0, f"{locale}: no tracked page was examined"

    def test_korean_hangul_hangul_candidates_are_examined_and_non_zero(self):
        trees = self.listed()
        assert "ko" in trees, "ko is in REQUIRED_NON_CJK_TREES"
        _violations, stats = non_cjk_findings({"ko": trees["ko"]})
        assert stats["ko"]["hangul_hangul"] > 0

    def test_a_planted_non_cjk_removal_without_u200b_is_reported(self):
        # control of the check itself: a Han pair on an es page is clause 2, no U+200B
        found = non_cjk_text_violations("planted-es.md", "日本\n語\n", "es")
        assert found == [
            "planted-es.md:1: clause 2 removed a break with no U+200B beside it"
        ]

    def test_a_removal_beside_u200b_on_a_non_cjk_page_meets_the_spec(self):
        assert non_cjk_text_violations("es.md", "word​\nbreak\n", "es") == []


# --- the CJK trees, the planted pages ---------------------------------


def cjk_tree_check(
    name: str,
    markdown: str,
    language: str,
    apply_fn: Callable[[str, str], "sb.SoftBreakResult"],
) -> Tuple[List[str], Dict[str, int]]:
    """Return the violations of the CJK-tree check for one page, and the candidates per clause.

    A violation is a break that the spec's clauses 1 to 4 remove (judged by the
    oracle, which is independent of the module) and that is still a line ending
    in the page ``apply_fn`` produced, or a break the scanner left UNDECIDED.
    """
    counts = {
        "clause 1": 0,
        "clause 2": 0,
        "clause 3": 0,
        "clause 4": 0,
        "clause 5": 0,
        "undecided": 0,
    }
    for item in sb.apply_soft_break_rule(markdown, language).breaks:
        counts[item.clause.value] += 1
    produced = apply_fn(markdown, language).markdown
    violations: List[str] = []
    for item in sb.apply_soft_break_rule(produced, language).breaks:
        if item.clause is CL[0]:
            violations.append(f"{name}: line {item.line}: undecided")
            continue
        wanted = oracle_clause(item.before, item.after, language)
        if wanted <= 4:
            violations.append(
                f"{name}: line {item.line}: clause {wanted} break is shown as a space"
            )
    return violations, counts


def bypass(markdown: str, _language: str) -> "sb.SoftBreakResult":
    """The rule bypassed: the page unchanged."""
    return sb.SoftBreakResult(markdown=markdown, breaks=())


PLANTED = {
    "planted-clause-2": ("ja", "日本\n語\n", 2),
    "planted-clause-3": ("ja", "ファイル\n“開く”\n", 3),
    "planted-clause-4": ("zh_CN", "支持 PNG、\nGIF 和\n", 4),
}


class TestCjkTrees:
    """No shipped Chinese or Japanese page keeps a removable break."""

    @pytest.mark.parametrize(
        ("name", "language", "page", "clause_number"),
        [(k, *v) for k, v in PLANTED.items()],
    )
    def test_planted_page_fails_the_check_when_the_rule_is_bypassed(
        self, name, language, page, clause_number
    ):
        violations, counts = cjk_tree_check(name, page, language, bypass)
        assert violations, f"{name}: the check did not fail on a break shown as a space"
        assert all(name in v for v in violations)
        assert (
            f"line 1: clause {clause_number} break is shown as a space" in violations[0]
        )

    @pytest.mark.parametrize(
        ("name", "language", "page", "clause_number"),
        [(k, *v) for k, v in PLANTED.items()],
    )
    def test_planted_page_passes_with_the_real_rule(
        self, name, language, page, clause_number
    ):
        violations, counts = cjk_tree_check(
            name, page, language, sb.apply_soft_break_rule
        )
        assert violations == []
        assert counts[f"clause {clause_number}"] == 1
        assert counts["undecided"] == 0

    def test_the_check_names_the_page_the_line_and_the_clause(self):
        page = "Hello\nworld\n\n日本\n語\n"
        violations, _ = cjk_tree_check("a/b.md", page, "ja", bypass)
        assert violations == ["a/b.md: line 4: clause 2 break is shown as a space"]

    def test_the_check_reports_an_undecided_candidate(self):
        violations, counts = cjk_tree_check(
            "u.md", "日本&amp;\n語\n", "ja", sb.apply_soft_break_rule
        )
        assert violations == ["u.md: line 1: undecided"]
        assert counts["undecided"] == 1

    def test_shipped_tree_half(self, capsys):
        tracked = judged_trees()
        trees = sorted(
            set(REQUIRED_CJ_TREES) | {loc for loc in CJ_LOCALES if tracked[loc]}
        )
        if not trees:
            pytest.skip(CJK_TREES_SKIP_REASON)
        total = {"clause 1": 0, "clause 2": 0, "clause 3": 0, "clause 4": 0}
        violations: List[str] = []
        for locale in trees:
            assert tracked[locale], f"{locale}: no tracked page was examined"
            for relative in tracked[locale]:
                text = read_page(REPO_ROOT, relative)
                found, counts = cjk_tree_check(
                    relative, text, locale, sb.apply_soft_break_rule
                )
                violations.extend(found)
                for key in total:
                    total[key] += counts[key]
        with capsys.disabled():
            print(f"[softbreak][CJK] candidates per clause: {total}")
        assert sum(total.values()) > 0
        assert not violations, "\n".join(violations)


# --- timing, printed and never asserted ---------------------------------------


class TestTimingReport:
    """The time of the rule on the largest shipped page and at the size cap."""

    def test_timing_is_printed_not_asserted(self, capsys):
        tracked = judged_trees()
        largest = max(
            (relative for pages in tracked.values() for relative in pages),
            key=lambda relative: (REPO_ROOT / relative).stat().st_size,
            default=None,
        )
        assert largest is not None, "no tracked guide page"
        text = read_page(REPO_ROOT, largest)
        started = time.perf_counter()
        result = sb.apply_soft_break_rule(text, "ja")
        elapsed = time.perf_counter() - started
        with capsys.disabled():
            print(
                f"[softbreak][TIMING] largest tracked page {largest}: {len(text.encode('utf-8'))} bytes, "
                f"{len(result.breaks)} candidates, {elapsed * 1000:.2f} ms (ja)"
            )
        named = f"{TREE_REL}/es/collaboration.md"
        if named in tracked["es"]:
            text = read_page(REPO_ROOT, named)
            started = time.perf_counter()
            result = sb.apply_soft_break_rule(text, "es")
            elapsed = time.perf_counter() - started
            with capsys.disabled():
                print(
                    f"[softbreak][TIMING] {named}: {len(text.encode('utf-8'))} bytes, "
                    f"{len(result.breaks)} candidates, {elapsed * 1000:.2f} ms (es)"
                )

    def test_synthetic_page_at_the_content_size_cap(self, capsys):
        cap = C.GUIDE_MAX_CONTENT_BYTES
        unit = "選択範囲を\n**移動**します。\nPNG、\nGIF と 日本\n語 の `code\nspan` です。\n\n"
        text = unit * (cap // len(unit.encode("utf-8")) + 1)
        text = text.encode("utf-8")[:cap].decode("utf-8", "ignore")
        started = time.perf_counter()
        result = sb.apply_soft_break_rule(text, "ja")
        elapsed = time.perf_counter() - started
        with capsys.disabled():
            print(
                f"[softbreak][TIMING] synthetic page at GUIDE_MAX_CONTENT_BYTES ({len(text.encode('utf-8'))} "
                f"bytes), {len(result.breaks)} candidates, {elapsed * 1000:.2f} ms (ja)"
            )
        assert isinstance(result.markdown, str)
        assert len(result.breaks) > 0
