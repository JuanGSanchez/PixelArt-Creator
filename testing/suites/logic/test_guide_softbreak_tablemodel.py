"""The table model and idempotence of pixelart_creator.logic.guide_softbreak.

Logic layer, no Qt: every expected value below is a LITERAL written from the
architect's decision (measured against Qt 6.11.1 and re-measured for this file), never
computed from the module, so the module cannot agree with itself here.

* ``TestRegressionDelimiterShapedLine`` -- the defect where the transform was not
  idempotent on a delimiter-shaped line that the same pass rewrote, as a strict,
  permanent regression case.
* ``TestTableRows`` -- one case per row of the table model (sixteen rows): the exact
  output, the exact ``breaks`` set, a second pass that is a no-op, the same in CRLF,
  and -- from Qt's own table grids, written here as literals -- that no line Qt puts
  in a table was joined to its neighbour.
* ``TestQtTableModel`` -- where a table starts and what ends one, one
  behaviour per test, with the control beside each.
* ``test_p2t_*`` -- the idempotence property (table-idempotence): idempotence over
  table-shaped pages, under the repository's ``ci`` profile, and its positive control:
  the same property against a copy of the module with the post-delimiter guard removed
  (M-DG) must FAIL.

The module under test can be a broken copy (``SOFTBREAK_MUTANT_FILE``): the mutants
M-DG, M-ST and M-EN of ``_softbreak_mutants.py`` are killed by this file.
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ._softbreak_support import REPO_ROOT, load_softbreak

if TYPE_CHECKING:
    from pixelart_creator.logic.guide_softbreak import SoftBreakClause

sb = load_softbreak()

ZWSP = "​"

U = sb.SoftBreakClause.UNDECIDED
Z = sb.SoftBreakClause.ZERO_WIDTH_SPACE
W = sb.SoftBreakClause.WIDE_PAIR
SP = sb.SoftBreakClause.SPACE

Breaks = Sequence[Tuple[int, "SoftBreakClause"]]


def page_of(lines: Sequence[str], ending: str = "\n") -> str:
    """The page that ``lines`` make: each line, then one line ending."""
    return ending.join(lines) + ending


def run(lines: Sequence[str], language: str = "ja", ending: str = "\n"):
    """``(page, result)`` of the rule over ``lines``."""
    page = page_of(lines, ending)
    return page, sb.apply_soft_break_rule(page, language)


def summary(result) -> List[Tuple[int, "SoftBreakClause"]]:
    """``(line, clause)`` for every examined break, in order."""
    return [(b.line, b.clause) for b in result.breaks]


def assert_second_pass_is_a_no_op(markdown: str, language: str) -> None:
    """A second pass returns the output unchanged and removes no break."""
    again = sb.apply_soft_break_rule(markdown, language)
    assert (
        again.markdown == markdown
    ), f"not idempotent ({language}): once {markdown!r}, twice {again.markdown!r}"
    assert not any(b.removed for b in again.breaks), (
        f"the second pass removed a break ({language}): "
        f"{[(b.line, b.clause) for b in again.breaks if b.removed]}"
    )


# ===========================================================================
# 1. The delimiter-shaped-line defect, a permanent regression case
# ===========================================================================

#: (id, lines, language). Every one is kept byte for byte with all three breaks
#: UNDECIDED.
DELIMITER_LINE_PAGES = [
    ("delimiter-line-ja", ["日", "本", "|-|-|", ZWSP + "語"], "ja"),
    ("delimiter-line-en", ["日", "本", "|-|-|", ZWSP + "語"], "en"),
    ("delimiter-line-zh_CN", ["日", "本", "|-|-|", ZWSP + "語"], "zh_CN"),
    ("delimiter-line-ko", ["日", "本", "|-|-|", ZWSP + "語"], "ko"),
    ("delimiter-line-colons", ["日", "本", ":-|-:", ZWSP + "語"], "ja"),
    (
        "delimiter-line-in-a-block-quote",
        ["> 日", "> 本", "> |-|-|", "> " + ZWSP + "語"],
        "ja",
    ),
    # The shape Hypothesis shrank to by the property run, in ja and en.
    ("shrunk-ja", ["[x](日", "本>", "|-|-|", "[" + ZWSP + "本](/x)"], "ja"),
    ("shrunk-en", ["[x](日", "本>", "|-|-|", "[" + ZWSP + "本](/x)"], "en"),
]


class TestRegressionDelimiterShapedLine:
    """Found by the property run and fixed by the post-delimiter guard.

    The first pass kept ``日``/``本`` because ``|-|-|`` is delimiter-shaped, then removed
    the break after that line (clause 1, U+200B), so the line stopped being
    delimiter-shaped and a second pass removed the break the first had kept. These cases
    are strict: the source is kept byte for byte, the three breaks are UNDECIDED, and a
    second pass is a no-op. Neither wrong output of the module as built is accepted.
    """

    @pytest.mark.parametrize(
        "lines, language",
        [(l, g) for _, l, g in DELIMITER_LINE_PAGES],
        ids=[i for i, _, _ in DELIMITER_LINE_PAGES],
    )
    def test_the_source_is_kept_byte_for_byte_with_three_undecided_breaks(
        self, lines, language
    ):
        page, result = run(lines, language)
        assert result.markdown == page
        assert summary(result) == [(1, U), (2, U), (3, U)]
        assert not any(b.removed for b in result.breaks)

    @pytest.mark.parametrize(
        "lines, language",
        [(l, g) for _, l, g in DELIMITER_LINE_PAGES],
        ids=[i for i, _, _ in DELIMITER_LINE_PAGES],
    )
    def test_a_second_pass_is_a_no_op(self, lines, language):
        _, result = run(lines, language)
        assert_second_pass_is_a_no_op(result.markdown, language)

    def test_neither_wrong_output_is_produced(self):
        lines = ["日", "本", "|-|-|", ZWSP + "語"]
        page, result = run(lines)
        # What the module as built produced on the first pass (the break after the
        # delimiter-shaped line removed), and what its second pass then made of it.
        built_once = "日\n本\n|-|-|" + ZWSP + "語\n"
        built_twice = "日本\n|-|-|" + ZWSP + "語\n"
        # The intent (both removable breaks removed) is rejected (a second pass would
        # change it), and removing only the first break would make a table in Qt.
        only_break_one = "日本\n|-|-|\n" + ZWSP + "語\n"
        assert result.markdown not in (built_once, built_twice, only_break_one)
        assert result.markdown == page

    def test_the_same_page_in_crlf_is_kept_too(self):
        page, result = run(["日", "本", "|-|-|", ZWSP + "語"], "ja", "\r\n")
        assert result.markdown == page
        assert summary(result) == [(1, U), (2, U), (3, U)]
        assert_second_pass_is_a_no_op(result.markdown, "ja")

    def test_post_delimiter_guard_alone_keeps_the_break_after_a_delimiter_shaped_line(
        self,
    ):
        # No wide character: break 1 is a clause 5 space, break 2 is UNDECIDED (it sits
        # above a delimiter-shaped line), and the third is kept only by the
        # post-delimiter guard (clause 1 would remove it). M-DG drops exactly this.
        for language in ("en", "ja"):
            page, result = run(["x", "y", "|-|-|", ZWSP + "語"], language)
            assert result.markdown == page
            assert summary(result) == [(1, SP), (2, U), (3, U)]

    def test_control_a_delimiter_row_that_opens_a_paragraph_is_plain_text(self):
        # The row opens the paragraph, so it is neither a table nor marked: clause 1
        # still removes the break after it, in one pass, and the pass is idempotent.
        for language in ("ja", "en"):
            page, result = run(["|-|-|", ZWSP + "語"], language)
            assert result.markdown == "|-|-|" + ZWSP + "語\n"
            assert summary(result) == [(1, Z)]
            assert_second_pass_is_a_no_op(result.markdown, language)

    def test_control_a_plain_pair_is_still_joined(self):
        page, result = run(["日", "本", "語"])
        assert result.markdown == "日本語\n"
        assert summary(result) == [(1, W), (2, W)]
        assert_second_pass_is_a_no_op(result.markdown, "ja")


# ===========================================================================
# 2. The sixteen rows of the table model
# ===========================================================================

#: Each row: (id, source lines, expected lines or None for "the source", breaks, the
#: Qt table grid of the source as measured (rows of cell texts, [] for "no table")).
#: The grid is the oracle's reading (measured against Qt, re-measured under
#: PySide6 6.11.1); the transformed source never changes it.
Row = Tuple[
    str, Sequence[str], Optional[Sequence[str]], Breaks, Sequence[Sequence[str]]
]

ROWS: List[Row] = [
    (
        "delimiter-line-then-zwsp-row",
        ["日", "本", "|-|-|", ZWSP + "語"],
        None,
        [(1, U), (2, U), (3, U)],
        [],
    ),
    (
        "table-header-then-delimiter-line-then-zwsp-row",
        ["a|日", "本|", "|-|-|", ZWSP + "語"],
        None,
        [(1, U), (2, U), (3, U)],
        [],
    ),
    (
        "table-header-then-delimiter-line",
        ["a|日", "本|", "|-|-|"],
        None,
        [(1, U), (2, U)],
        [],
    ),
    (
        "header-of-three-cells-then-zwsp-row",
        ["a|b|c", "|-|-|", ZWSP + "語"],
        None,
        [],
        [["a", "b"], [ZWSP + "語", ""]],
    ),
    (
        "header-of-three-cells-then-two-rows",
        ["a|b|c", "|-|-|", "日", "本"],
        None,
        [],
        [["a", "b"], ["日", ""], ["本", ""]],
    ),
    (
        "one-line-header-then-two-rows",
        ["日", "|-|-|", "日", "本"],
        None,
        [],
        [["日", ""], ["日", ""], ["本", ""]],
    ),
    (
        "header-candidate-is-a-second-line",
        ["日", "本|", "|-|"],
        None,
        [(1, U), (2, U)],
        [],
    ),
    (
        "header-candidate-is-a-third-line",
        ["日", "a|b", "|-|-|", "日", "本"],
        ["日", "a|b", "|-|-|", "日本"],
        [(1, SP), (2, U), (3, SP), (4, W)],
        [],
    ),
    (
        "in-a-block-quote",
        ["> 日", "> 本|", "> |-|"],
        None,
        [(1, U), (2, U)],
        [],
    ),
    (
        "an-atx-heading-is-a-body-row",
        ["a|b", "|-|-|", "# h", "日", "本"],
        None,
        [],
        [["a", "b"], ["# h", ""], ["日", ""], ["本", ""]],
    ),
    (
        "a-fence-is-a-body-row",
        ["a|b", "|-|-|", "```", "日", "本", "", "日", "本"],
        ["a|b", "|-|-|", "```", "日", "本", "", "日本"],
        [(7, W)],
        [["a", "b"], ["```", ""], ["日", ""], ["本", ""]],
    ),
    (
        "an-indented-line-ends-the-table",
        ["a|b", "|-|-|", "    code", "日", "本"],
        ["a|b", "|-|-|", "    code", "日本"],
        [(4, W)],
        [["a", "b"]],
    ),
    (
        "a-definition-line-counts-as-the-first-line",
        ["[a]: /x", "b|c", "|-|-|", "日", "本"],
        ["[a]: /x", "b|c", "|-|-|", "日本"],
        [(2, U), (3, SP), (4, W)],
        [],
    ),
    (
        "control-table-blank-paragraph",
        ["a|b", "|-|-|", "日", "本", "", "日", "本"],
        ["a|b", "|-|-|", "日", "本", "", "日本"],
        [(6, W)],
        [["a", "b"], ["日", ""], ["本", ""]],
    ),
    (
        "control-a-thematic-break-ends-a-table",
        ["a|b", "|-|-|", "***", "日", "本"],
        ["a|b", "|-|-|", "***", "日本"],
        [(4, W)],
        [["a", "b"]],
    ),
    (
        "control-a-plain-pair",
        ["日", "本"],
        ["日本"],
        [(1, W)],
        [],
    ),
]

ROW_IDS = [row[0] for row in ROWS]


class TestTableRows:
    """One named case per row of the table model, in LF and CRLF."""

    @pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
    def test_the_exact_output_and_the_exact_breaks(self, row):
        _, lines, wanted, breaks, _grid = row
        page, result = run(lines)
        expected = page if wanted is None else page_of(wanted)
        assert result.markdown == expected
        assert summary(result) == list(breaks)

    @pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
    def test_the_same_page_in_crlf_decides_the_same(self, row):
        _, lines, wanted, breaks, _grid = row
        page, result = run(lines, "ja", "\r\n")
        expected = page if wanted is None else page_of(wanted, "\r\n")
        assert result.markdown == expected
        assert summary(result) == list(breaks)

    @pytest.mark.parametrize("row", ROWS, ids=ROW_IDS)
    def test_a_second_pass_is_a_no_op(self, row):
        _, lines, _wanted, _breaks, _grid = row
        _, result = run(lines)
        assert_second_pass_is_a_no_op(result.markdown, "ja")

    @pytest.mark.parametrize(
        "row", [r for r in ROWS if r[4]], ids=[r[0] for r in ROWS if r[4]]
    )
    def test_no_line_qt_puts_in_a_table_was_joined(self, row):
        # The Qt grid is the oracle's reading of the SOURCE. A table holds the header,
        # the delimiter row and one line per body row: len(grid) + 1 lines, from the
        # first line. Each body row's first cell is the line itself. The output must
        # keep all of them as lines of their own, untouched.
        _, lines, _wanted, _breaks, grid = row
        table_lines = list(lines[: len(grid) + 1])
        for index, cells in enumerate(grid[1:], start=2):
            assert (
                table_lines[index] == cells[0]
            ), f"the literal grid disagrees with the source at line {index + 1}"
        _, result = run(lines)
        assert result.markdown.split("\n")[: len(table_lines)] == table_lines

    @pytest.mark.parametrize(
        "row", [r for r in ROWS if not r[4]], ids=[r[0] for r in ROWS if not r[4]]
    )
    def test_where_qt_shows_no_table_the_breaks_are_examined(self, row):
        # Qt reads these as one paragraph, so the scanner must examine the line ending
        # of the paragraph (it does not skip them as table rows), and a delimiter-shaped
        # line must never be joined onto its neighbour.
        _, lines, _wanted, breaks, _grid = row
        _, result = run(lines)
        assert breaks and summary(result) == list(breaks)
        kept = result.markdown.split("\n")
        for text in lines:
            if "|" in text and not text.lstrip("> ").strip("|-:"):
                assert text in kept, f"the delimiter-shaped line {text!r} was changed"


# ===========================================================================
# 3. Where a table starts and what ends one, one behaviour per test
# ===========================================================================


def expect(
    lines: Sequence[str], breaks: Breaks, wanted: Optional[Sequence[str]] = None
):
    """Assert the exact output and breaks of ``lines`` in ``ja``, and idempotence."""
    page, result = run(lines)
    assert summary(result) == list(breaks)
    assert result.markdown == (page if wanted is None else page_of(wanted))
    assert_second_pass_is_a_no_op(result.markdown, "ja")


class TestQtTableModel:
    """Qt (md4c) starts a table below a paragraph's FIRST line and ends it on 5
    shapes."""

    def test_the_header_cell_count_is_not_compared(self):
        # Qt: ``a|b|c`` over ``|-|-|`` is a table with 2 columns.
        expect(["a|b|c", "|-|-|", "日", "本"], [])

    def test_a_one_line_paragraph_without_a_pipe_is_a_header(self):
        expect(["日", "|-|-|", "日", "本"], [])

    def test_a_table_starts_only_under_the_first_line_of_a_paragraph(self):
        # Two lines before the delimiter row: a paragraph, so every break is examined.
        expect(
            ["日", "a|b", "|-|-|", "日", "本"],
            [(1, SP), (2, U), (3, SP), (4, W)],
            ["日", "a|b", "|-|-|", "日本"],
        )

    def test_control_a_one_line_paragraph_with_a_pipe_is_a_header(self):
        expect(["a|b", "|-|-|", "日", "本"], [])

    def test_the_first_line_of_a_paragraph_after_a_blank_line_is_a_header(self):
        # Qt: ``x`` blank ``本`` ``|-|`` is a table (the blank line starts a new
        # paragraph).
        expect(["x", "", "本", "|-|", "日", "本"], [])

    def test_a_link_reference_definition_counts_as_the_first_line(self):
        expect(
            ["[a]: /x", "b|c", "|-|-|", "日", "本"],
            [(2, U), (3, SP), (4, W)],
            ["[a]: /x", "b|c", "|-|-|", "日本"],
        )

    def test_control_after_a_blank_line_a_definition_does_not_count(self):
        expect(["[a]: /x", "", "b|c", "|-|-|", "日", "本"], [])

    def test_a_delimiter_row_in_a_longer_quote_paragraph_is_not_a_table(self):
        expect(
            ["> 日", "> a|b", "> |-|-|", "> 日", "> 本"],
            [(1, SP), (2, U), (3, SP), (4, W)],
            ["> 日", "> a|b", "> |-|-|", "> 日本"],
        )

    def test_a_delimiter_row_in_a_longer_list_paragraph_is_not_a_table(self):
        expect(
            ["- 日", "  a|b", "  |-|-|", "  日", "  本"],
            [(1, SP), (2, U), (3, SP), (4, W)],
            ["- 日", "  a|b", "  |-|-|", "  日本"],
        )

    # -- what ends a table ------------------------------------------

    @pytest.mark.parametrize(
        "row_text",
        ["# h", "## h", "```", "~~~", "<div>", "<!-- c -->", "===", "  日"],
    )
    def test_these_lines_are_body_rows_and_the_table_runs_on(self, row_text):
        # Qt: each is one more row; the rows below it are rows too, so no break is
        # examined and nothing is joined.
        expect(["a|b", "|-|-|", row_text, "日", "本"], [])

    @pytest.mark.parametrize(
        "ender, breaks",
        [
            ("", [(4, W)]),
            ("***", [(4, W)]),
            ("---", [(4, W)]),
            ("   ***", [(4, W)]),
            ("-", [(4, W)]),
            ("- x", [(3, SP), (4, W)]),
            ("+ x", [(3, SP), (4, W)]),
            ("1. x", [(3, SP), (4, W)]),
            ("2. x", [(3, SP), (4, W)]),
            ("> q", [(3, SP), (4, W)]),
        ],
    )
    def test_these_lines_end_the_table_and_the_pair_after_them_is_joined(
        self, ender, breaks
    ):
        # Qt: a blank line, a thematic break, any list-item start (an empty one too) and
        # a block-quote start end the table (grid [[a, b]] only); the pair is then text.
        expect(
            ["a|b", "|-|-|", ender, "日", "本"],
            breaks,
            ["a|b", "|-|-|", ender, "日本"],
        )

    def test_four_columns_of_indent_end_the_table(self):
        expect(
            ["a|b", "|-|-|", "    code", "日", "本"],
            [(4, W)],
            ["a|b", "|-|-|", "    code", "日本"],
        )

    def test_a_blank_line_ends_the_table(self):
        expect(
            ["a|b", "|-|-|", "日", "本", "", "日", "本"],
            [(6, W)],
            ["a|b", "|-|-|", "日", "本", "", "日本"],
        )

    def test_a_thematic_break_ends_the_table(self):
        for rule in ("***", "---", "   ***"):
            expect(
                ["a|b", "|-|-|", rule, "日", "本"],
                [(4, W)],
                ["a|b", "|-|-|", rule, "日本"],
            )

    def test_a_block_quote_start_ends_the_table_and_its_lines_are_the_quotes(self):
        expect(["a|b", "|-|-|", "> 日", "> 本"], [(3, W)], ["a|b", "|-|-|", "> 日本"])

    def test_a_line_outside_the_tables_container_closes_it(self):
        # Qt: the quote's table holds the quoted row only; the unprefixed line after it
        # is a paragraph, and its pair is joined.
        expect(
            ["> a|b", "> |-|-|", "> 日", "日", "本"],
            [(4, W)],
            ["> a|b", "> |-|-|", "> 日", "日本"],
        )


# ===========================================================================
# 4. table-idempotence: idempotence over table-shaped pages
# ===========================================================================

#: The pool of lines: wide, U+200B-led, delimiter-shaped, header-shaped, block starts.
P2T_POOL = [
    "日",
    "本",
    "語",
    "日本",
    "日 本",
    ZWSP + "語",
    "日" + ZWSP,
    "x",
    "x y",
    "|-|-|",
    "|---|---|",
    ":-|-:",
    "| --- |",
    "a|b",
    "a|日",
    "本|",
    "a|b|c",
    "| a | b |",
    "# h",
    "```",
    "~~~",
    "    code",
    "***",
    "---",
    "===",
    "- x",
    "1. x",
    "> q",
    "<div>",
    "[a]: /x",
    "",
]
P2T_PREFIXES = ("none", "quote", "item", "indent")
P2T_ENDINGS = ("\n", "\r\n")
P2T_LANGUAGES = ("ja", "zh_CN", "en", "ko")
#: Examples per run under the ci profile (derandomized): enough for the control to fail.
P2T_EXAMPLES = 1500


def prefixed(lines: Sequence[str], prefix: str) -> List[str]:
    """Put the container prefix on every line (an item: its marker, then its indent)."""
    if prefix == "none":
        return list(lines)
    if prefix == "quote":
        return ["> " + line for line in lines]
    if prefix == "item":
        return [("- " if i == 0 else "  ") + line for i, line in enumerate(lines)]
    return ["   " + line for line in lines]


#: The lines of a table-shaped skeleton: what comes above a delimiter-shaped line
#: (wide, header-shaped), the delimiter-shaped line itself, and what comes below it.
#: A repeated entry weights the draw: the defect's shape (two wide lines, a
#: delimiter-shaped line, a U+200B-led line) must turn up often enough for the
#: positive control to fail under the ci profile whatever the seed.
P2T_HEADS = [
    "日",
    "日",
    "本",
    "本",
    "語",
    "日本",
    "x",
    "a|b",
    "a|日",
    "本|",
    "a|b|c",
    "[a]: /x",
]
P2T_DELIMITERS = ["|-|-|", "|---|---|", ":-|-:", "| --- |"]
P2T_TAILS = [
    ZWSP + "語",
    ZWSP + "語",
    ZWSP + "語",
    "日",
    "本",
    "# h",
    "```",
    "    code",
    "***",
    "---",
    "===",
    "- x",
    "> q",
    "<div>",
    "a|b",
    "",
]


@st.composite
def p2t_lines(draw):
    """2 to 10 lines drawn from the pool: a skeleton (twice as likely) or free."""
    free = st.lists(st.sampled_from(P2T_POOL), min_size=2, max_size=10)
    skeleton = st.builds(
        lambda head, delimiter, tail: head + [delimiter] + tail,
        st.lists(st.sampled_from(P2T_HEADS), min_size=1, max_size=3),
        st.sampled_from(P2T_DELIMITERS),
        st.lists(st.sampled_from(P2T_TAILS), min_size=0, max_size=3),
    )
    return draw(st.one_of(skeleton, skeleton, free))


@st.composite
def p2t_pages(draw):
    """A page of table-shaped lines, with a container prefix and a line ending."""
    lines = draw(p2t_lines())
    prefix = draw(st.sampled_from(P2T_PREFIXES))
    ending = draw(st.sampled_from(P2T_ENDINGS))
    final = draw(st.booleans())
    page = ending.join(prefixed(lines, prefix))
    return page + (ending if final else "")


def p2t_holds(module, page: str, language: str) -> None:
    """The property, for ``module``: the second pass is a no-op (raises
    AssertionError)."""
    once = module.apply_soft_break_rule(page, language)
    twice = module.apply_soft_break_rule(once.markdown, language)
    assert twice.markdown == once.markdown, (
        f"not idempotent ({language}): "
        f"{page!r} -> {once.markdown!r} -> {twice.markdown!r}"
    )
    assert not any(b.removed for b in twice.breaks)


@settings(max_examples=P2T_EXAMPLES)
@given(p2t_pages(), st.sampled_from(P2T_LANGUAGES))
def test_p2t_the_transform_is_idempotent_over_table_shaped_pages(page, language):
    p2t_holds(sb, page, language)


#: The anchor of the post-delimiter guard in the module (the post-``decide`` guard),
#: and what removes it.
GUARD_ANCHOR = "        elif (\n            paragraph[k].delimiter_like\n"
GUARD_REMOVED = "        elif (\n            False\n"
MODULE_FILE = REPO_ROOT / "pixelart_creator" / "logic" / "guide_softbreak.py"


def load_copy(name: str, *, without_guard: bool) -> types.ModuleType:
    """A copy of the REPOSITORY'S module under its own name, the post-delimiter guard
    removed (M-DG) or not.

    Independent of ``SOFTBREAK_MUTANT_FILE``: the control must hold whatever the
    suite is pointed at. It is registered in ``sys.modules`` while it runs
    (dataclasses read it).
    """
    source = MODULE_FILE.read_bytes().decode("utf-8")
    if without_guard:
        assert (
            source.count(GUARD_ANCHOR) == 1
        ), "the post-delimiter guard's anchor is not in the module once"
        source = source.replace(GUARD_ANCHOR, GUARD_REMOVED)
    module = types.ModuleType(name)
    module.__file__ = str(MODULE_FILE)
    sys.modules[name] = module
    try:
        exec(compile(source, str(MODULE_FILE), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


@pytest.fixture(scope="module")
def module_without_guard():
    module = load_copy("_softbreak_without_guard", without_guard=True)
    yield module
    sys.modules.pop(module.__name__, None)


@pytest.fixture(scope="module")
def module_with_guard():
    module = load_copy("_softbreak_with_guard", without_guard=False)
    yield module
    sys.modules.pop(module.__name__, None)


class TestP2TPositiveControl:
    """table-idempotence must be able to fail: against M-DG it does."""

    def test_the_delimiter_line_page_is_not_idempotent_without_guard(
        self, module_without_guard
    ):
        page = page_of(["日", "本", "|-|-|", ZWSP + "語"])
        with pytest.raises(AssertionError, match="not idempotent"):
            p2t_holds(module_without_guard, page, "ja")

    def test_the_property_finds_a_counterexample_without_guard(
        self, module_without_guard
    ):
        # The same strategy and settings as the real property, derandomized by the
        # repository's ci profile: it must reach a failing page.
        @settings(max_examples=P2T_EXAMPLES)
        @given(p2t_pages(), st.sampled_from(P2T_LANGUAGES))
        def property_on_the_copy(page, language):
            p2t_holds(module_without_guard, page, language)

        with pytest.raises(AssertionError, match="not idempotent"):
            property_on_the_copy()

    def test_the_same_property_holds_on_the_unpatched_copy(self, module_with_guard):
        # The control is the module minus ONE guard: the unpatched copy passes the page
        # that the patched one fails.
        page = page_of(["日", "本", "|-|-|", ZWSP + "語"])
        p2t_holds(module_with_guard, page, "ja")

    def test_the_copy_differs_from_the_module_only_where_the_guard_acts(
        self, module_with_guard, module_without_guard
    ):
        for lines in (["日", "本"], ["a|b", "|-|-|", "日", "本"], ["x", "y", "z"]):
            page = page_of(lines)
            assert (
                module_without_guard.apply_soft_break_rule(page, "ja").markdown
                == module_with_guard.apply_soft_break_rule(page, "ja").markdown
            )
