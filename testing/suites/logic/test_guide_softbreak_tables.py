"""Tests for the Unicode tables of the soft-line-break rule.

``pixelart_creator.logic.constants`` declares three inclusive range tables at
UCD 15.1.0, because ``unicodedata`` carries neither the Script nor the Emoji
property: ``GUIDE_HANGUL_SCRIPT_RANGES``, ``GUIDE_LATIN_SCRIPT_RANGES`` and
``GUIDE_EMOJI_RANGES`` (none of them is in ``unicodedata``). This module proves them:

* shape: sorted, disjoint, inside the code space, every code point assigned;
* Hangul and Latin against ``fontTools.unicodedata``, the independent oracle,
  at the equal Unicode version, printing what was read;
* the interpreter named by ``.python-version`` carries the tables' version, so
  CI can never skip the cross-check;
* the Emoji property: 1,424 elements, members, non-members and range-edge
  samples written as literal characters.

The Emoji tests fail clearly, with the reason, if the table is missing.
"""

from __future__ import annotations

import bisect
import hashlib
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, FrozenSet, Sequence, Tuple

import fontTools
import pytest
from fontTools import unicodedata as ft_unicodedata
from fontTools.unicodedata import Scripts as ft_scripts

from pixelart_creator.logic import constants as C

from ._softbreak_support import REPO_ROOT, load_softbreak

sb = load_softbreak()  # the module under test must import: the tables serve it

MAX_CODE_POINT = 0x10FFFF
EXPECTED_TABLES_VERSION = "15.1.0"
EMOJI_TOTAL = 1424  # "# Total elements: 1424" of the Emoji block, emoji-data.txt 15.1.0
EMOJI_RANGE_COUNT = 151  # the coalesced ranges of those 1,424 code points
#: SHA-256 of the table written as ``FIRST-LAST`` hex lines (upper case, one per range,
#: each ending in a line feed). Measured from the table that was generated from
#: emoji-data.txt 15.1.0 (file SHA-256 d7aef489...5cc1) and found equal, as a set of
#: code points, to that file's ``Emoji`` property by an independent parse. A deliberate
#: regeneration changes this value; an accidental edit that keeps the total no longer
#: passes unseen.
EMOJI_TABLE_DIGEST = "1783589a07b08879382e29b964c0350e120a11cc5d04f99c3ace59127421f175"
HANGUL_TOTAL = 11739  # "# Total code points: 11739", Scripts.txt 15.1.0
LATIN_TOTAL = 1481  # "# Total code points: 1481", Scripts.txt 15.1.0

#: Differences between a table and fontTools that are accepted, with the UCD
#: reason. EMPTY when last measured (fontTools 4.63.0, Scripts-17.0.0, 0
#: differences). Adding an entry needs an architect's decision with the UCD reason,
#: never a quiet edit.
ALLOW_LIST: Dict[str, FrozenSet[int]] = {"hangul": frozenset(), "latin": frozenset()}

TABLE_NAMES = {
    "hangul": "GUIDE_HANGUL_SCRIPT_RANGES",
    "latin": "GUIDE_LATIN_SCRIPT_RANGES",
    "emoji": "GUIDE_EMOJI_RANGES",
}

EMOJI_MISSING = (
    "the Emoji table is not delivered: GUIDE_EMOJI_RANGES is missing or empty in "
    "logic/constants.py, so the Emoji property cannot be proven"
)


def table(name: str) -> Tuple[Tuple[int, int], ...]:
    """Return the named table; the Emoji table fails clearly until it is supplied."""
    ranges = getattr(C, TABLE_NAMES[name], None)
    if name == "emoji" and not ranges:
        pytest.fail(EMOJI_MISSING, pytrace=False)
    assert ranges is not None, f"constants.{TABLE_NAMES[name]} is missing"
    return ranges


def expand(ranges: Sequence[Tuple[int, int]]) -> FrozenSet[int]:
    """All code points of inclusive ``(first, last)`` ranges."""
    points = set()
    for first, last in ranges:
        points.update(range(first, last + 1))
    return frozenset(points)


def contains(ranges: Sequence[Tuple[int, int]], char: str) -> bool:
    """Membership by ``bisect`` over the range starts (the test's own lookup)."""
    code = ord(char)
    starts = [first for first, _last in ranges]
    index = bisect.bisect_right(starts, code) - 1
    return index >= 0 and ranges[index][0] <= code <= ranges[index][1]


@lru_cache(maxsize=1)
def assigned_code_points() -> FrozenSet[int]:
    """Every code point the running interpreter's database assigns (category not Cn)."""
    return frozenset(
        cp for cp in range(MAX_CODE_POINT + 1) if unicodedata.category(chr(cp)) != "Cn"
    )


@lru_cache(maxsize=1)
def oracle_points() -> Dict[str, FrozenSet[int]]:
    """Hangul and Latin from fontTools over the assigned code points."""
    assigned = assigned_code_points()
    hangul = set()
    latin = set()
    for cp in assigned:
        script = ft_unicodedata.script(chr(cp))
        if script == "Hang":
            hangul.add(cp)
        elif script == "Latn":
            latin.add(cp)
    return {"hangul": frozenset(hangul), "latin": frozenset(latin)}


def scripts_header() -> str:
    """The ``Scripts-*.txt`` header line of fontTools' own copy."""
    for line in Path(str(ft_scripts.__file__)).read_text(encoding="utf-8").splitlines():
        if line.startswith("# Scripts-"):
            return line
    return "(no Scripts header found)"


def python_version_pin() -> str:
    """The interpreter version ``.python-version`` declares (CI reads the same file)."""
    return (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()


def running_version() -> str:
    """The running interpreter as ``major.minor.micro``."""
    return ".".join(str(part) for part in sys.version_info[:3])


# ---------------------------------------------------------------------------
# The version constant and the shape of every table
# ---------------------------------------------------------------------------


def test_the_tables_version_constant_is_unicode_15_1_0():
    assert C.GUIDE_UCD_TABLES_VERSION == EXPECTED_TABLES_VERSION


def test_the_font_coverage_hangul_constant_is_a_different_thing():
    # HANGUL_RANGES is the Hangul Syllables block for font coverage. Script=Hangul
    # also holds the conjoining and compatibility jamo and the half-width forms.
    assert tuple(C.HANGUL_RANGES) == ((0xAC00, 0xD7A3),)
    script_table = table("hangul")
    assert tuple(script_table) != tuple(C.HANGUL_RANGES)
    for char in ("ᄀ", "ㄱ", "ﾡ"):
        assert contains(script_table, char)
        assert not any(first <= ord(char) <= last for first, last in C.HANGUL_RANGES)


@pytest.mark.parametrize("name", ["hangul", "latin", "emoji"])
class TestTableShape:
    def test_it_is_a_tuple_of_integer_pairs(self, name):
        ranges = table(name)
        assert isinstance(ranges, tuple) and ranges
        for item in ranges:
            assert isinstance(item, tuple) and len(item) == 2
            assert all(isinstance(value, int) for value in item)

    def test_each_range_is_inside_the_code_space_and_not_reversed(self, name):
        for first, last in table(name):
            assert 0 <= first <= last <= MAX_CODE_POINT, (hex(first), hex(last))

    def test_ranges_are_sorted_and_disjoint(self, name):
        ranges = table(name)
        for (_a_first, a_last), (b_first, _b_last) in zip(ranges, ranges[1:]):
            assert b_first > a_last, f"{hex(a_last)} is not below {hex(b_first)}"

    def test_every_listed_code_point_is_assigned_in_the_running_interpreter(self, name):
        listed = expand(table(name))
        unassigned = sorted(listed - assigned_code_points())
        assert not unassigned, (
            f"{name}: {len(unassigned)} listed code points are unassigned (Cn) at "
            f"unidata {unicodedata.unidata_version}: {[hex(c) for c in unassigned[:10]]}. "
            f"The tables are newer than the runtime."
        )


# ---------------------------------------------------------------------------
# Hangul and Latin against fontTools
# ---------------------------------------------------------------------------


def versions_line() -> str:
    return (
        f"interpreter {sys.version.split()[0]}, unicodedata.unidata_version "
        f"{unicodedata.unidata_version}, fontTools {fontTools.version}, "
        f"fontTools Scripts header '{scripts_header()}', tables {C.GUIDE_UCD_TABLES_VERSION}"
    )


class TestFontToolsCrossCheck:
    def test_it_prints_what_it_read(self, capsys):
        with capsys.disabled():
            print(f"[softbreak][FONTTOOLS] {versions_line()}")
        assert unicodedata.unidata_version
        assert scripts_header().startswith("# Scripts-")

    @pytest.mark.parametrize("name", ["hangul", "latin"])
    def test_table_equals_fonttools_script_over_every_assigned_code_point(
        self, name, capsys
    ):
        if unicodedata.unidata_version != C.GUIDE_UCD_TABLES_VERSION:
            if running_version() == python_version_pin():
                pytest.fail(
                    "the .python-version interpreter must carry the tables' Unicode version: "
                    + versions_line(),
                    pytrace=False,
                )
            pytest.skip(
                "unidata_version differs from the tables' version, so the cross-check does not "
                "stand for CI: " + versions_line()
            )
        listed = expand(table(name)) - ALLOW_LIST[name]
        oracle = oracle_points()[name] - ALLOW_LIST[name]
        missing = sorted(oracle - listed)
        extra = sorted(listed - oracle)
        with capsys.disabled():
            print(
                f"[softbreak][FONTTOOLS] {name}: table {len(listed)}, oracle {len(oracle)}, "
                f"table-only {len(extra)}, oracle-only {len(missing)}; {versions_line()}"
            )
        assert (
            not extra
        ), f"{name}: in the table, not in fontTools: {[hex(c) for c in extra[:20]]}"
        assert (
            not missing
        ), f"{name}: in fontTools, not in the table: {[hex(c) for c in missing[:20]]}"

    def test_the_allow_list_is_empty(self):
        assert all(not entries for entries in ALLOW_LIST.values())


class TestPinnedInterpreter:
    def test_python_version_file_names_a_full_version(self):
        pin = python_version_pin()
        assert len(pin.split(".")) == 3 and all(
            part.isdigit() for part in pin.split(".")
        ), pin

    def test_the_pinned_interpreter_carries_unicode_15_1_0(self, capsys):
        pin = python_version_pin()
        if running_version() != pin:
            pytest.skip(
                f"running {running_version()}, .python-version names {pin}: the pinned-interpreter "
                f"assertion is not exercised here ({versions_line()})"
            )
        with capsys.disabled():
            print(
                f"[softbreak][PIN] {running_version()} == .python-version; {versions_line()}"
            )
        assert unicodedata.unidata_version == "15.1.0"
        assert unicodedata.unidata_version == C.GUIDE_UCD_TABLES_VERSION


# ---------------------------------------------------------------------------
# Hangul and Latin: totals and literal samples (independent of fontTools)
# ---------------------------------------------------------------------------


def test_hangul_table_holds_the_stated_total():
    assert len(expand(table("hangul"))) == HANGUL_TOTAL


def test_latin_table_holds_the_stated_total():
    assert len(expand(table("latin"))) == LATIN_TOTAL


@pytest.mark.parametrize(
    "char",
    ["가", "힣", "ᄀ", "ᇿ", "ㄱ", "ㅎ", "ﾠ", "ￜ", "〮", "ꥠ", "ퟻ"],
)
def test_hangul_members(char):
    assert contains(table("hangul"), char), hex(ord(char))


@pytest.mark.parametrize(
    "char",
    ["日", "A", "あ", "　", "​", "꯿", "퟼", "ჿ", "ሀ", "﾿", "￝"],
)
def test_hangul_non_members(char):
    assert not contains(table("hangul"), char), hex(ord(char))


@pytest.mark.parametrize(
    "char",
    ["A", "Z", "a", "z", "é", "ª", "º", "ǅ", "K", "Ⅳ", "Ａ", "ｚ", "ĳ", "Ꟊ", "ﬆ"],
)
def test_latin_members(char):
    assert contains(table("latin"), char), hex(ord(char))


@pytest.mark.parametrize(
    "char",
    ["0", "日", "한", "α", "Ж", "@", "[", "`", "{", "×", "÷", "　"],
)
def test_latin_non_members(char):
    assert not contains(table("latin"), char), hex(ord(char))


def test_the_fifteen_one_latin_edge_before_the_sixteen_additions():
    # 16.0.0 widened two ranges (U+A7CB..A7CD, U+A7DA..A7DC); the 15.1.0 table does not hold them.
    assert not contains(table("latin"), "Ɤ")
    assert not contains(table("latin"), "Ƛ")
    assert contains(table("latin"), "ꟊ")
    assert contains(table("latin"), "ꟙ")


# ---------------------------------------------------------------------------
# The Emoji property (fails clearly if the table is missing)
# ---------------------------------------------------------------------------


class TestEmojiTable:
    def test_the_table_has_been_supplied(self):
        assert table("emoji")

    def test_the_table_is_pinned_by_range_count_and_content_digest(self):
        ranges = table("emoji")
        assert len(ranges) == EMOJI_RANGE_COUNT
        text = "".join(f"{first:X}-{last:X}\n" for first, last in ranges)
        assert hashlib.sha256(text.encode("ascii")).hexdigest() == EMOJI_TABLE_DIGEST

    def test_one_code_point_swapped_for_another_changes_the_digest(self):
        # The pin must be able to fail: same size, different content, different digest.
        ranges = list(table("emoji"))
        first, last = ranges[0]
        assert first == last, "the first range is a single code point (U+0023)"
        ranges[0] = (first + 1, last + 1)  # same total, one member swapped
        text = "".join(f"{a:X}-{b:X}\n" for a, b in ranges)
        assert sum(b - a + 1 for a, b in ranges) == EMOJI_TOTAL
        assert hashlib.sha256(text.encode("ascii")).hexdigest() != EMOJI_TABLE_DIGEST

    def test_it_holds_the_stated_total_of_1424(self):
        total = sum(last - first + 1 for first, last in table("emoji"))
        assert total == EMOJI_TOTAL
        assert len(expand(table("emoji"))) == EMOJI_TOTAL

    @pytest.mark.parametrize("char", ["\U0001f600", "©", "0", "#", "*", "™", "‼", "®"])
    def test_members(self, char):
        assert contains(table("emoji"), char), hex(ord(char))

    @pytest.mark.parametrize("char", ["A", "日", "a", "z", " ", "　", "한", "$", "​"])
    def test_non_members(self, char):
        assert not contains(table("emoji"), char), hex(ord(char))

    def test_the_table_holds_the_whole_property_not_only_width_w_and_n(self):
        # the W/N restriction is applied in decide, not baked into the table
        ranges = table("emoji")
        widths = {unicodedata.east_asian_width(chr(cp)) for cp in expand(ranges)}
        assert {"W", "N", "Na", "A"} <= widths, widths

    # Range-edge samples, written as literal characters: first, last, first-1, last+1.
    # The ranges are the single-line members of the Emoji property
    # as listed in the Unicode data file emoji-data.txt.
    # Eight ranges: 0023, 002A, 0030..0039, 00A9, 00AE, 203C, 2049, 2122.
    EDGES = [
        ("0023", "#", "#", '"', "$"),
        ("002A", "*", "*", ")", "+"),
        ("0030..0039", "0", "9", "/", ":"),
        ("00A9", "©", "©", "¨", "ª"),
        ("00AE", "®", "®", "­", "¯"),
        ("203C", "‼", "‼", "※", "‽"),
        ("2049", "⁉", "⁉", "⁈", "⁊"),
        ("2122", "™", "™", "℡", "℣"),
    ]

    @pytest.mark.parametrize(
        ("line", "first", "last", "before_first", "after_last"),
        EDGES,
        ids=[edge[0] for edge in EDGES],
    )
    def test_range_edges(self, line, first, last, before_first, after_last):
        ranges = table("emoji")
        assert contains(ranges, first), f"{line}: first"
        assert contains(ranges, last), f"{line}: last"
        assert not contains(ranges, before_first), f"{line}: first-1"
        assert not contains(ranges, after_last), f"{line}: last+1"

    def test_at_least_eight_ranges_are_sampled(self):
        assert len(self.EDGES) >= 8

    def test_the_edge_characters_are_the_ones_the_lines_name(self):
        for line, first, last, before_first, after_last in self.EDGES:
            low, _, high = line.partition("..")
            assert ord(first) == int(low, 16)
            assert ord(last) == int(high or low, 16)
            assert ord(before_first) == ord(first) - 1
            assert ord(after_last) == ord(last) + 1
