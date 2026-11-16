"""The join's regression proof for pixelart_creator.logic.guide_softbreak.

Logic layer, no Qt: every expected value below is a LITERAL, written from the
architect's decision and measured against Qt, never computed from the module, so the
module cannot agree with itself here.

One named case per row of the joiner table and per guard:

* *joined with the comment* ``<!---->`` (the pairs the joiner is proven for);
* *joined plainly* (the measured non-triggers: the joiner must NOT appear);
* *kept, UNDECIDED, source byte for byte* (what the joiner cannot be proven safe for);
* the paragraph-wide preservation check (an ordinary break beside the bad one is kept too);
* the permissive-link and header-candidate guards, per break (the ordinary break beside
  them is still removed).

The module under test can be a broken copy (``SOFTBREAK_MUTANT_FILE``): the mutants
M-J, M-P, M-A and M-T of ``_softbreak_mutants.py`` are killed by this file.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import pytest

from ._softbreak_support import load_softbreak

sb = load_softbreak()

JOINER = "<!---->"
ZWSP = "​"
BACKSLASH = chr(92)

U = sb.SoftBreakClause.UNDECIDED
Z = sb.SoftBreakClause.ZERO_WIDTH_SPACE
W = sb.SoftBreakClause.WIDE_PAIR
SP = sb.SoftBreakClause.SPACE

Row = Tuple[str, Sequence[str], str, Sequence[Tuple[int, "sb.SoftBreakClause"]]]


def page_of(lines: Sequence[str], ending: str = "\n") -> str:
    """The page that ``lines`` make: each line, then one line ending."""
    return ending.join(lines) + ending


def run(lines: Sequence[str], language: str = "ja", ending: str = "\n"):
    """``(page, result)`` of the rule over ``lines``."""
    page = page_of(lines, ending)
    return page, sb.apply_soft_break_rule(page, language)


def summary(result) -> List[Tuple[int, "sb.SoftBreakClause"]]:
    """``(line, clause)`` for every examined break, in order."""
    return [(b.line, b.clause) for b in result.breaks]


# ---------------------------------------------------------------------------
# The joiner rows. Each: (row name, source lines, the exact output, the breaks).
# ---------------------------------------------------------------------------

#: The emphasis characters, unchanged (the positive controls of the joiner table).
EMPHASIS_ROWS: List[Row] = [
    (
        "bold-flanking",
        ["**移動。**", "を選ぶ"],
        "**移動。**" + JOINER + "を選ぶ\n",
        [(1, W)],
    ),
    ("strike", ["~~日~~", "本"], "~~日~~" + JOINER + "本\n", [(1, W)]),
    (
        "emphasis-inside-link-text",
        ["[*日*", "*本*](/x)"],
        "[*日*" + JOINER + "*本*](/x)\n",
        [(1, W)],
    ),
    (
        "underline",
        ["_移動。_", "を選ぶ"],
        "_移動。_" + JOINER + "を選ぶ\n",
        [(1, W)],
    ),
    (
        "double-underline",
        ["__移動。__", "を選ぶ"],
        "__移動。__" + JOINER + "を選ぶ\n",
        [(1, W)],
    ),
    ("underline-both-sides", ["_日_", "_本_"], "_日_" + JOINER + "_本_\n", [(1, W)]),
]

#: The pairs beside backticks and brackets. Joined with the comment, so the intent survives.
PAIR_ROWS: List[Row] = [
    ("backtick-both", ["`日`", "`本`"], "`日`" + JOINER + "`本`\n", [(1, W)]),
    ("double-runs", ["``日``", "``本``"], "``日``" + JOINER + "``本``\n", [(1, W)]),
    ("unequal-runs", ["`日`", "``本``"], "`日`" + JOINER + "``本``\n", [(1, W)]),
    (
        "literal-backtick-then-span",
        ["日`", "``" + ZWSP + "本``"],
        "日`" + JOINER + "``" + ZWSP + "本``\n",
        [(1, Z)],
    ),
    (
        "bracket-bracket",
        ["[日]", "[本]", "", "[日]: /a", "[本]: /b"],
        "[日]" + JOINER + "[本]\n\n[日]: /a\n[本]: /b\n",
        [(1, W)],
    ),
    (
        "bracket-paren",
        ["[日" + ZWSP + "]", "(本)", "", "[日" + ZWSP + "]: /a"],
        "[日" + ZWSP + "]" + JOINER + "(本)\n\n[日" + ZWSP + "]: /a\n",
        [(1, Z)],
    ),
    (
        "bracket-colon",
        ["[日" + ZWSP + "]", ": /x", "", "[日" + ZWSP + "]: /a"],
        "[日" + ZWSP + "]" + JOINER + ": /x\n\n[日" + ZWSP + "]: /a\n",
        [(1, Z)],
    ),
    (
        "bang-bracket",
        ["日!", "[" + ZWSP + "本](/x)"],
        "日!" + JOINER + "[" + ZWSP + "本](/x)\n",
        [(1, Z)],
    ),
]

#: The measured non-triggers: joined plainly.
PLAIN_ROWS: List[Row] = [
    ("plain-control", ["日", "本"], "日本\n", [(1, W)]),
    ("backtick-left-only", ["`日`", "本"], "`日`本\n", [(1, W)]),
    ("backtick-right-only", ["日", "`本`"], "日`本`\n", [(1, W)]),
    (
        "paren-then-bracket",
        ["[日](/a)", "[本](/b)"],
        "[日](/a)[本](/b)\n",
        [(1, W)],
    ),
    (
        "even-backslash-run",
        ["日" + BACKSLASH * 2, ZWSP + "本"],
        "日" + BACKSLASH * 2 + ZWSP + "本\n",
        [(1, Z)],
    ),
    ("ampersand", ["日&", ZWSP + "amp;"], "日&" + ZWSP + "amp;\n", [(1, Z)]),
    ("angle-bracket", ["日<", ZWSP + "b>本"], "日<" + ZWSP + "b>本\n", [(1, Z)]),
]

#: What the joiner cannot be proven safe for, and the guards for it.
#: ``kept``: the source comes back byte for byte and every break is UNDECIDED.
PRESERVATION_ROWS: List[Row] = [
    ("inline-destination", ["[x](日", "本)"], "[x](日\n本)\n", [(1, U)]),
    ("uri-autolink", ["<http://日", "本>"], "<http://日\n本>\n", [(1, U)]),
    (
        "raw-html-unquoted-attribute",
        ["<a href=日", "本>x"],
        "<a href=日\n本>x\n",
        [(1, U)],
    ),
    (
        "label-gains-a-definition",
        ["[日", "本]", "", "[日本]: /x"],
        "[日\n本]\n\n[日本]: /x\n",
        [(1, U)],
    ),
    (
        "label-loses-its-definition",
        ["[日", "本]", "", "[日 本]: /x"],
        "[日\n本]\n\n[日 本]: /x\n",
        [(1, U)],
    ),
]

#: The permissive-link guard: the seven permissive-link rows and the three permissive URLs that end in a
#: wide character (the space-free run at the break holds ``://``, ``www.`` or ``@``).
PERMISSIVE_LINK_ROWS: List[Row] = [
    (
        "url-then-ideographic-stop",
        ["https://example.com/a", "。"],
        "https://example.com/a\n。\n",
        [(1, U)],
    ),
    (
        "www-then-comma",
        ["www.example.com", "、日"],
        "www.example.com\n、日\n",
        [(1, U)],
    ),
    ("email-then-stop", ["a@example.com", "。"], "a@example.com\n。\n", [(1, U)]),
    (
        "stop-then-url",
        ["日。", "https://example.com"],
        "日。\nhttps://example.com\n",
        [(1, U)],
    ),
    (
        "stop-then-www",
        ["日。", "www.example.com"],
        "日。\nwww.example.com\n",
        [(1, U)],
    ),
    (
        "stop-then-email",
        ["日。", "a@example.com"],
        "日。\na@example.com\n",
        [(1, U)],
    ),
    (
        "url-ending-in-a-digit",
        ["https://example.com/1", "。"],
        "https://example.com/1\n。\n",
        [(1, U)],
    ),
    (
        "url-ending-wide",
        ["https://example.com/日", "本"],
        "https://example.com/日\n本\n",
        [(1, U)],
    ),
    (
        "www-ending-wide",
        ["www.example.com/日", "本"],
        "www.example.com/日\n本\n",
        [(1, U)],
    ),
    (
        "url-ending-wide-then-wide",
        ["https://example.com/日", "本"],
        "https://example.com/日\n本\n",
        [(1, U)],
    ),
]

#: The header-candidate guard: the break above a delimiter row's header candidate. Both breaks are kept.
HEADER_CANDIDATE_ROWS: List[Row] = [
    (
        "delimiter-row-header-candidate",
        ["a|日", "本|", "|-|-|"],
        "a|日\n本|\n|-|-|\n",
        [(1, U), (2, U)],
    ),
]


def ids(rows: Sequence[Row]) -> List[str]:
    """The pytest ids of a table of rows: the row names."""
    return [row[0] for row in rows]


JOINED_ROWS = EMPHASIS_ROWS + PAIR_ROWS


class TestJoinedWithTheComment:
    """Where the comment joiner is proven, it is placed, once."""

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"), JOINED_ROWS, ids=ids(JOINED_ROWS)
    )
    def test_the_break_is_removed_with_the_joiner(self, name, lines, expected, breaks):
        page, result = run(lines)
        assert result.markdown == expected
        assert summary(result) == list(breaks)
        assert result.markdown.count(JOINER) == 1

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"), JOINED_ROWS, ids=ids(JOINED_ROWS)
    )
    def test_only_the_line_ending_and_its_spaces_went_and_one_joiner_came(
        self, name, lines, expected, breaks
    ):
        page, result = run(lines)
        assert result.markdown.replace(JOINER, "").count("\n") == page.count("\n") - 1
        assert result.markdown.replace(JOINER, "") == page.replace("\n", "", 1)

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"), JOINED_ROWS, ids=ids(JOINED_ROWS)
    )
    def test_a_second_pass_changes_nothing(self, name, lines, expected, breaks):
        first = sb.apply_soft_break_rule(page_of(lines), "ja")
        assert sb.apply_soft_break_rule(first.markdown, "ja").markdown == first.markdown

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"), PAIR_ROWS, ids=ids(PAIR_ROWS)
    )
    def test_the_same_pair_is_joined_in_every_line_ending(
        self, name, lines, expected, breaks
    ):
        for ending in ("\r\n", "\r"):
            page, result = run(lines, ending=ending)
            assert result.markdown == expected.replace("\n", ending)
            assert summary(result) == list(breaks)


class TestRegressionTwoCodeSpans:
    """Found by the first run: two code spans must stay two code spans.

    The expected joined source is exact: the join is neither the plain
    ``\\`日\\`\\`本\\``` (Qt shows one span, ``日``本``) nor the kept source.
    """

    def test_two_code_spans_across_a_removed_break_are_joined_with_the_comment(self):
        page, result = run(["`日`", "`本`"])
        assert result.markdown == "`日`" + JOINER + "`本`\n"
        assert result.markdown != "`日``本`\n"
        assert summary(result) == [(1, W)]

    def test_the_plain_join_of_the_two_spans_is_not_what_is_produced(self):
        page, result = run(["`日`", "`本`"])
        assert "`日``本`" not in result.markdown
        assert result.markdown != page


class TestRegressionTwoReferenceLinks:
    """Found by the first run: two reference links must stay two links.

    ``[日][本]`` is one FULL reference link to ``/b`` in Qt, and 本 is lost.
    """

    LINES = ["[日]", "[本]", "", "[日]: /a", "[本]: /b"]

    def test_two_reference_links_across_a_removed_break_are_joined_with_the_comment(
        self,
    ):
        page, result = run(self.LINES)
        assert result.markdown == "[日]" + JOINER + "[本]\n\n[日]: /a\n[本]: /b\n"
        assert summary(result) == [(1, W)]

    def test_the_plain_join_is_not_what_is_produced(self):
        page, result = run(self.LINES)
        assert "[日][本]" not in result.markdown
        assert result.markdown != page


class TestJoinedPlainly:
    """The measured non-triggers: no joiner where none is needed."""

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"), PLAIN_ROWS, ids=ids(PLAIN_ROWS)
    )
    def test_the_break_is_removed_and_no_joiner_is_left(
        self, name, lines, expected, breaks
    ):
        page, result = run(lines)
        assert result.markdown == expected
        assert summary(result) == list(breaks)
        assert JOINER not in result.markdown

    def test_a_backtick_on_one_side_is_not_a_trigger_in_either_direction(self):
        assert JOINER not in run(["`日`", "本"])[1].markdown
        assert JOINER not in run(["日", "`本`"])[1].markdown

    def test_paren_then_bracket_is_not_a_trigger(self):
        assert JOINER not in run(["[日](/a)", "[本](/b)"])[1].markdown


class TestKeptByThePreservationCheck:
    """Syntax that forms AWAY from the join keeps the break, byte for byte."""

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"),
        PRESERVATION_ROWS,
        ids=ids(PRESERVATION_ROWS),
    )
    def test_the_source_is_returned_byte_for_byte(self, name, lines, expected, breaks):
        page, result = run(lines)
        assert result.markdown == expected == page
        assert summary(result) == list(breaks)
        assert not any(b.removed for b in result.breaks)

    def test_the_kept_break_reports_the_real_characters_beside_it(self):
        page, result = run(["[x](日", "本)"])
        assert (result.breaks[0].before, result.breaks[0].after) == ("日", "本")
        assert result.breaks[0].clause is U

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"),
        PRESERVATION_ROWS,
        ids=ids(PRESERVATION_ROWS),
    )
    def test_a_kept_break_gets_no_joiner(self, name, lines, expected, breaks):
        assert JOINER not in run(lines)[1].markdown

    # A paragraph with one ordinary break (日 / 本) before the bad one. The
    # preservation check is PARAGRAPH-WIDE: the ordinary break is kept as well.
    # The URI autolink row is not here: its ``://`` makes the permissive-link guard keep
    # that one break by itself, so it cannot tell the two guards apart (M-P does not
    # need it).
    WIDE = {
        "inline-destination": ["日", "本 [x](日", "本)"],
        "raw-html-unquoted-attribute": ["日", "本 <a href=日", "本>x"],
        "label-gains-a-definition": ["日", "本 [日", "本]", "", "[日本]: /x"],
        "label-loses-its-definition": ["日", "本 [日", "本]", "", "[日 本]: /x"],
    }

    @pytest.mark.parametrize("name", sorted(WIDE))
    def test_the_other_removable_breaks_of_the_paragraph_are_kept_too(self, name):
        lines = self.WIDE[name]
        page, result = run(lines)
        assert result.markdown == page
        assert [b.clause for b in result.breaks][:2] == [U, U]
        assert not any(b.removed for b in result.breaks)

    def test_the_control_without_the_bad_break_removes_the_ordinary_one(self):
        # Positive control for the test above: that paragraph's ordinary break is
        # removable, so keeping it is the paragraph-wide rule and not a coincidence.
        page, result = run(["日", "本 語"])
        assert result.markdown == "日本 語\n"
        assert summary(result) == [(1, W)]

    def test_a_break_in_another_paragraph_is_not_kept(self):
        lines = ["[x](日", "本)", "", "日", "本"]
        page, result = run(lines)
        assert result.markdown == "[x](日\n本)\n\n日本\n"
        assert summary(result) == [(1, U), (4, W)]

    def test_the_kept_paragraph_is_returned_byte_for_byte_beside_a_removed_one(self):
        lines = ["日", "本", "", "[x](日", "本)", "", "語", "本"]
        page, result = run(lines)
        assert result.markdown == "日本\n\n[x](日\n本)\n\n語本\n"


class TestKeptBecauseOfAPermissiveLink:
    """A clause that would remove is UNDECIDED beside ``://``, ``www.`` or ``@``."""

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"),
        PERMISSIVE_LINK_ROWS,
        ids=ids(PERMISSIVE_LINK_ROWS),
    )
    def test_the_source_is_returned_byte_for_byte(self, name, lines, expected, breaks):
        page, result = run(lines)
        assert result.markdown == expected == page
        assert summary(result) == list(breaks)
        assert JOINER not in result.markdown

    @pytest.mark.parametrize(
        "token_line",
        [
            "https://example.com/日",
            "HTTPS://EXAMPLE.COM/日",
            "WWW.example.com/日",
            "Www.a.b/日",
            "a@b/日",
        ],
    )
    def test_the_token_is_matched_in_any_case_before_the_break(self, token_line):
        page, result = run([token_line, "本"])
        assert result.markdown == page
        assert summary(result) == [(1, U)]

    @pytest.mark.parametrize(
        "token_line", ["本https://x.y", "本www.x.y", "本a@b", "本WWW.X.Y"]
    )
    def test_the_token_is_matched_after_the_break_as_well(self, token_line):
        page, result = run(["日", token_line])
        assert result.markdown == page
        assert summary(result) == [(1, U)]

    def test_the_run_is_the_space_free_run_at_the_break(self):
        # The address is a different space-separated word: the run at the break is 日.
        page, result = run(["see https://x.com 日", "本"])
        assert result.markdown == "see https://x.com 日本\n"
        assert summary(result) == [(1, W)]
        page, result = run(["日", "本 https://x.com see"])
        assert result.markdown == "日本 https://x.com see\n"

    def test_a_tab_also_ends_the_run(self):
        page, result = run(["https://x.com\t日", "本"])
        assert result.markdown == "https://x.com\t日本\n"

    def test_the_guard_is_consulted_only_where_a_clause_would_remove(self):
        # Clause 5 (two Latin letters) keeps the space already: not UNDECIDED.
        page, result = run(["https://example.com/a", "b"])
        assert result.markdown == page
        assert summary(result) == [(1, SP)]

    def test_the_guard_is_per_break_the_ordinary_break_is_still_removed(self):
        page, result = run(["日", "本", "https://example.com/a", "。"])
        assert result.markdown == "日本\nhttps://example.com/a\n。\n"
        assert summary(result) == [(1, W), (2, SP), (3, U)]

    def test_an_address_in_one_paragraph_does_not_keep_the_next_paragraphs_breaks(self):
        page, result = run(["https://example.com/a", "。", "", "日", "本"])
        assert result.markdown == "https://example.com/a\n。\n\n日本\n"
        assert summary(result) == [(1, U), (4, W)]

    def test_a_break_whose_neighbour_runs_hold_no_token_is_removed(self):
        page, result = run(["example.com/日", "本"])
        assert result.markdown == "example.com/日本\n"


class TestKeptBecauseOfAHeaderCandidate:
    """The break above a delimiter-shaped line's header candidate."""

    @pytest.mark.parametrize(
        ("name", "lines", "expected", "breaks"),
        HEADER_CANDIDATE_ROWS,
        ids=ids(HEADER_CANDIDATE_ROWS),
    )
    def test_both_breaks_are_kept_byte_for_byte(self, name, lines, expected, breaks):
        page, result = run(lines)
        assert result.markdown == expected == page
        assert summary(result) == list(breaks)

    def test_the_break_above_the_header_candidate_line_is_kept(self):
        page, result = run(["日", "本", "|-|-|"])
        assert result.markdown == page
        assert summary(result) == [(1, U), (2, U)]

    def test_a_break_three_lines_above_a_delimiter_row_is_not_kept(self):
        # Only the break above the header candidate (本 / 語) and the one before the
        # delimiter row itself are kept; the break above them is still removed.
        page, result = run(["日", "本", "語", "|-|-|"])
        assert result.markdown == "日本\n語\n|-|-|\n"
        assert summary(result) == [(1, W), (2, U), (3, U)]

    def test_without_a_delimiter_row_the_same_lines_are_joined(self):
        page, result = run(["日", "本", "語"])
        assert result.markdown == "日本語\n"
        assert summary(result) == [(1, W), (2, W)]

    def test_a_pipe_row_without_a_delimiter_row_is_not_a_header_candidate(self):
        page, result = run(["a|日", "本|"])
        assert result.markdown == "a|日本|\n"


class TestTheJoinerIsJudgedOnSourceCharacters:
    """L and R are the source characters, after the container prefix."""

    def test_a_block_quote_prefix_is_not_the_right_hand_character(self):
        page, result = run(["> `日`", "> `本`"])
        assert result.markdown == "> `日`" + JOINER + "`本`\n"

    def test_a_list_continuation_indent_is_not_the_right_hand_character(self):
        page, result = run(["- `日`", "  `本`"])
        assert result.markdown == "- `日`" + JOINER + "`本`\n"

    def test_trailing_and_leading_spaces_and_tabs_are_not_characters(self):
        page, result = run(["`日` \t", " \t `本`"])
        assert result.markdown == "`日`" + JOINER + "`本`\n"

    def test_a_pair_with_both_a_trigger_pair_and_an_emphasis_character_gets_one_joiner(
        self,
    ):
        page, result = run(["*`日`*", "`本`"])
        assert result.markdown.count(JOINER) == 1

    def test_three_lines_place_a_joiner_at_each_trigger_and_none_elsewhere(self):
        page, result = run(["`日`", "`本`", "語"])
        assert result.markdown == "`日`" + JOINER + "`本`語\n"
        page, result = run(["日", "`本`", "`語`"])
        assert result.markdown == "日`本`" + JOINER + "`語`\n"

    def test_the_pair_is_ordered_a_closing_bracket_after_a_paren_is_not_a_trigger(self):
        # (c) is ] then (, [ or : ; the mirror, ( then ], joins plainly.
        page, result = run(["日(", ZWSP + "]本"])
        assert JOINER not in result.markdown

    def test_the_pair_is_ordered_a_bracket_before_a_bang_is_not_a_trigger(self):
        # (d) is ! then [ ; the mirror, [ then !, joins plainly.
        page, result = run(["[日" + ZWSP + "[", "!本"])
        assert JOINER not in result.markdown


class TestTheJoinerIsNotLanguageScoped:
    """Clauses 1 and 2 remove in every language, so the joiner goes with them."""

    @pytest.mark.parametrize(
        "language", ["en", "es", "fr", "de", "ru", "ko", "ja", "zh_CN"]
    )
    def test_a_wide_pair_is_joined_with_the_comment_in_every_language(self, language):
        page, result = run(["`日`", "`本`"], language=language)
        assert result.markdown == "`日`" + JOINER + "`本`\n"

    @pytest.mark.parametrize("language", ["en", "ko", "ja"])
    def test_clause_one_joins_in_every_language(self, language):
        page, result = run(["日!", "[" + ZWSP + "本](/x)"], language=language)
        assert result.markdown == "日!" + JOINER + "[" + ZWSP + "本](/x)\n"

    @pytest.mark.parametrize("language", ["en", "es", "ko"])
    def test_no_guard_changes_a_break_that_no_clause_removes(self, language):
        # 。 beside a Latin letter is clause 4 (ja and zh_CN only): outside them the
        # break is kept as a space, whatever the permissive-link guard would say about the address.
        page, result = run(["https://example.com/a", "。"], language=language)
        assert result.markdown == page
        assert [b.removed for b in result.breaks] == [False]
        assert [b.clause is U for b in result.breaks] == [False]
