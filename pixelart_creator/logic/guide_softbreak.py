# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Soft line breaks in guide pages — which are not shown as a space (zero Qt, S11).

A guide page's source is Markdown wrapped across lines, and the
guide window shows each *soft line break* inside a paragraph as one space. For
Chinese and Japanese text that space is wrong. This module decides, for every soft
line break of a page, whether it is shown, and removes the ones that are not. It is
pure: it takes the page text and the page's language (the guide folder the page came
from) and returns text. It does no I/O and imports no Qt.

The decision (:func:`decide`) is the spec's five ordered clauses, judged on the two
*visible* characters on either side of the break:

1. U+200B on either side: not shown (the U+200B stays);
2. both sides East Asian Width F, W or H and neither Hangul: not shown;
3. in a ``ja`` or ``zh_CN`` page, one side punctuation or a symbol of width A and the
   other F, W or H and not Hangul: not shown;
4. in a ``ja`` or ``zh_CN`` page, one side a mark that the page's language lists
   (:data:`~pixelart_creator.logic.constants.GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS`) and
   the other a Latin letter or a decimal digit: not shown;
5. otherwise: shown as one space.

An Emoji character of width W or N counts as A in clauses 2 and 3.

Finding the breaks (:func:`apply_soft_break_rule`) is a CommonMark 0.31.2 subset, plus
GitHub tables (as Qt reads them) and strikethrough: a block pass (containers,
paragraphs, lazy continuation, fences, HTML blocks, headings, tables) and an inline
pass per paragraph (escapes, code spans, raw HTML, autolinks, links and images,
emphasis). A break that the scanner cannot classify with certainty is **kept** and
reported ``UNDECIDED``. Entity and numeric references are recognised and **never
decoded** (Qt decodes only some of them). A removed break joins the two lines with an
empty HTML comment (:data:`SOFT_BREAK_JOINER`) only where syntax would otherwise form
at the join: ``*``, ``_`` or ``~`` on either side, two backticks, ``]`` before ``(``,
``[`` or ``:``, and ``!`` before ``[`` (a joiner, below). Three guards keep the
break (``UNDECIDED``) where a join can change what the page means away from the join:
a paragraph whose inline pass, re-run over the joined text, changes the kind of any
character; a run beside the break holding ``://``, ``www.`` or ``@``, the
shape of a permissive link; and a delimiter-shaped line, on both sides: the
break above a table's delimiter row and the break after such a line, so that a
join never changes the shape that those guards read.

The table model is Qt's (md4c), not GitHub's. A table
starts only when a delimiter row follows a paragraph of exactly one line, and no
cell count is compared. A table ends only at a blank line, a line indented by four
or more columns, a thematic break, a list item or a block quote; any other line,
a heading, a fence or an HTML block included, is a body row. Imports are standard
library only.

The East Asian Width, the general category and ``Nd`` come from ``unicodedata``.
Script Hangul, Script Latin and Emoji are range tables in
:mod:`pixelart_creator.logic.constants` (UCD 16.0.0, the version of the
interpreter's ``unicodedata``; emoji-data.txt SHA-256
``f1365a5173eee18e1f98b240cdc492e84a25f1ce7e0c9d1094eb29c41a22696a``).
Importing this module fails loudly (:class:`SoftBreakTableError`) while the Emoji
table is missing.
"""

from __future__ import annotations

import bisect
import enum
import re
import string
import unicodedata
from dataclasses import dataclass, field

from pixelart_creator.logic.constants import (
    GUIDE_EMOJI_RANGES,
    GUIDE_EMOJI_TOTAL_ELEMENTS,
    GUIDE_HANGUL_SCRIPT_RANGES,
    GUIDE_LATIN_SCRIPT_RANGES,
    GUIDE_MD_CODE_INDENT,
    GUIDE_MD_EMPHASIS_MODULUS,
    GUIDE_MD_ESCAPE_LENGTH,
    GUIDE_MD_HARD_BREAK_SPACES,
    GUIDE_MD_MAX_ATX_LEVEL,
    GUIDE_MD_MAX_DECIMAL_REF_DIGITS,
    GUIDE_MD_MAX_ENTITY_NAME,
    GUIDE_MD_MAX_HEX_REF_DIGITS,
    GUIDE_MD_MAX_INDENT,
    GUIDE_MD_MAX_LABEL_CHARS,
    GUIDE_MD_MAX_ORDERED_DIGITS,
    GUIDE_MD_MAX_PAREN_DEPTH,
    GUIDE_MD_MAX_STRIKE_RUN,
    GUIDE_MD_MIN_FENCE,
    GUIDE_MD_MIN_THEMATIC,
    GUIDE_MD_STRONG_RUN,
    GUIDE_MD_TAB_STOP,
    GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS,
    GUIDE_SOFTBREAK_ZERO_WIDTH_SPACE,
    GUIDE_UCD_TABLES_VERSION,
)

__all__ = [
    "SoftBreakClause",
    "SoftBreak",
    "SoftBreakResult",
    "SoftBreakTableError",
    "decide",
    "apply_soft_break_rule",
    "CLAUSE3_LANGUAGES",
    "CLAUSE4_LANGUAGES",
    "SOFT_BREAK_JOINER",
]


class SoftBreakTableError(RuntimeError):
    """A Unicode range table that the rule needs is missing or incomplete."""


#: Page codes for which clause 3 applies. Kept apart from :data:`CLAUSE4_LANGUAGES`
#: so that a ruling that separates the two clauses is a data edit.
CLAUSE3_LANGUAGES: frozenset[str] = frozenset({"ja", "zh_CN"})

#: Page codes for which clause 4 applies: the languages that have a list of marks in
#: :data:`~pixelart_creator.logic.constants.GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS`.
CLAUSE4_LANGUAGES: frozenset[str] = frozenset(GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS)

#: What a removed break leaves between the two lines where syntax would form at the
#: join (the pairs of :data:`_JOINER_PAIRS`): an empty HTML comment. It shows
#: nothing, and as punctuation it restores the flanking that the line ending gave a
#: delimiter run.
SOFT_BREAK_JOINER = "<!---->"

_EMPHASIS_CHARS = "*_~"
# The pairs (L, R) beside a removed break that form syntax at the join (two
# backticks, ``]`` before ``(``, ``[`` or ``:``, ``!`` before ``[``); an emphasis
# character on either side is _EMPHASIS_CHARS.
_JOINER_PAIRS = frozenset({("`", "`"), ("]", "("), ("]", "["), ("]", ":"), ("!", "[")})
# What marks a run as the shape of a permissive link.
_LINK_SHAPE_TOKENS = ("://", "www.", "@")
_RUN_BREAK = re.compile(r"[ \t]")
_SPACE_TAB = " \t"
_ASCII_PUNCT = frozenset(string.punctuation)
_WIDE = frozenset({"F", "W", "H"})
_EMOJI_AS_AMBIGUOUS = frozenset({"W", "N"})
_NEWLINE = "\n"
_LINK_OPEN = "["
_IMAGE_OPEN = "!["


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


class SoftBreakClause(enum.Enum):
    """The clause of the soft-break rule that decided a soft line break."""

    ZERO_WIDTH_SPACE = "clause 1"
    WIDE_PAIR = "clause 2"
    AMBIGUOUS_PUNCTUATION = "clause 3"
    IDEOGRAPHIC_COMMA_OR_STOP = "clause 4"
    SPACE = "clause 5"
    UNDECIDED = "undecided"

    @property
    def removes(self) -> bool:
        """Whether this outcome removes the break (clauses 1 to 4)."""
        return self not in (SoftBreakClause.SPACE, SoftBreakClause.UNDECIDED)


@dataclass(frozen=True)
class SoftBreak:
    """One soft line break that was examined.

    Attributes:
        line: 1-based line of the original source that ends at the break.
        before: The visible character before the break ("" when undecided).
        after: The visible character after the break ("" when undecided).
        clause: The clause that decided it.
    """

    line: int
    before: str
    after: str
    clause: SoftBreakClause

    @property
    def removed(self) -> bool:
        """Whether the rule removed this break."""
        return self.clause.removes


@dataclass(frozen=True)
class SoftBreakResult:
    """The page after the rule, and every soft break that was examined.

    Attributes:
        markdown: The transformed source (byte for byte the input when no break is
            removed).
        breaks: Every candidate, removed or kept, in document order.
    """

    markdown: str
    breaks: tuple[SoftBreak, ...]


def _starts(ranges: tuple[tuple[int, int], ...]) -> list[int]:
    """Return the first code point of each range, for :mod:`bisect`."""
    return [first for first, _ in ranges]


_HANGUL_STARTS = _starts(GUIDE_HANGUL_SCRIPT_RANGES)
_LATIN_STARTS = _starts(GUIDE_LATIN_SCRIPT_RANGES)
_EMOJI_STARTS = _starts(GUIDE_EMOJI_RANGES)


def _check_emoji_table() -> None:
    """Fail loudly unless the Emoji table is the whole property."""
    size = sum(last - first + 1 for first, last in GUIDE_EMOJI_RANGES)
    if size != GUIDE_EMOJI_TOTAL_ELEMENTS:
        raise SoftBreakTableError(
            f"GUIDE_EMOJI_RANGES holds {size} code points, not the "
            f"{GUIDE_EMOJI_TOTAL_ELEMENTS} of the Emoji property at UCD "
            f"{GUIDE_UCD_TABLES_VERSION}: the "
            "table is incomplete or was edited: regenerate it from emoji-data.txt"
        )


_check_emoji_table()


def _in_ranges(ranges: tuple[tuple[int, int], ...], starts: list[int], ch: str) -> bool:
    """Return whether ``ch`` lies in one of the sorted, disjoint ``ranges``."""
    code = ord(ch)
    index = bisect.bisect_right(starts, code) - 1
    return index >= 0 and code <= ranges[index][1]


def _is_hangul(ch: str) -> bool:
    """Return whether ``ch`` has Script=Hangul."""
    return _in_ranges(GUIDE_HANGUL_SCRIPT_RANGES, _HANGUL_STARTS, ch)


def _is_latin_letter(ch: str) -> bool:
    """Return whether ``ch`` is a letter (category L) of Script=Latin."""
    return unicodedata.category(ch).startswith("L") and _in_ranges(
        GUIDE_LATIN_SCRIPT_RANGES, _LATIN_STARTS, ch
    )


def _is_emoji(ch: str) -> bool:
    """Return whether ``ch`` has the Emoji property."""
    return _in_ranges(GUIDE_EMOJI_RANGES, _EMOJI_STARTS, ch)


def _width(ch: str) -> str:
    """Return ``ch``'s East Asian Width, with the emoji rule applied.

    An Emoji of width W or N counts as A (the rule's "Emoji" note). Na is not N,
    so the digits, ``#`` and ``*`` are not affected.
    """
    width = unicodedata.east_asian_width(ch)
    if width in _EMOJI_AS_AMBIGUOUS and _is_emoji(ch):
        return "A"
    return width


def _is_wide(ch: str) -> bool:
    """Return whether ``ch`` is F, W or H and not Hangul (the emoji rule applied)."""
    return _width(ch) in _WIDE and not _is_hangul(ch)


def _is_ambiguous_mark(ch: str) -> bool:
    """Return whether ``ch`` is punctuation or a symbol (P, S) of width A."""
    return unicodedata.category(ch)[0] in "PS" and _width(ch) == "A"


def _is_latin_or_digit(ch: str) -> bool:
    """Return whether ``ch`` is a Latin letter or a decimal digit (Nd)."""
    return _is_latin_letter(ch) or unicodedata.category(ch) == "Nd"


def _is_ideographic_mark(ch: str, language: str) -> bool:
    """Return whether ``ch`` is a clause-4 mark of the page's ``language``."""
    return ord(ch) in GUIDE_SOFTBREAK_IDEOGRAPHIC_MARKS.get(language, ())


def decide(before: str, after: str, language: str) -> SoftBreakClause:
    """Decide a soft line break from the characters on either side.

    The clauses are tried in the spec's order and the first that applies decides.

    Args:
        before: The visible character before the break (one character).
        after: The visible character after the break (one character).
        language: The page's language, the guide folder it came from (``"ja"``,
            ``"zh_CN"``, ``"en"`` ...).

    Returns:
        The deciding clause. :attr:`SoftBreakClause.SPACE` and
        :attr:`SoftBreakClause.UNDECIDED` keep the break; the others remove it.
        ``UNDECIDED`` is returned only when an argument is not one character.
    """
    if len(before) != 1 or len(after) != 1:
        return SoftBreakClause.UNDECIDED
    pair = (before, after)
    zero_width = chr(GUIDE_SOFTBREAK_ZERO_WIDTH_SPACE)
    if zero_width in pair:
        return SoftBreakClause.ZERO_WIDTH_SPACE
    if _is_wide(before) and _is_wide(after):
        return SoftBreakClause.WIDE_PAIR
    if language in CLAUSE3_LANGUAGES and (
        (_is_ambiguous_mark(before) and _is_wide(after))
        or (_is_ambiguous_mark(after) and _is_wide(before))
    ):
        return SoftBreakClause.AMBIGUOUS_PUNCTUATION
    if language in CLAUSE4_LANGUAGES and (
        (_is_ideographic_mark(before, language) and _is_latin_or_digit(after))
        or (_is_ideographic_mark(after, language) and _is_latin_or_digit(before))
    ):
        return SoftBreakClause.IDEOGRAPHIC_COMMA_OR_STOP
    return SoftBreakClause.SPACE


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    """A source line without its ending, with its offset in the source."""

    text: str
    offset: int


_LINE_ENDING = re.compile(r"\r\n|\r|\n")


def _split_lines(source: str) -> list[_Line]:
    """Split ``source`` at LF, CR and CRLF (CommonMark §2.1), keeping offsets."""
    lines: list[_Line] = []
    start = 0
    for match in _LINE_ENDING.finditer(source):
        lines.append(_Line(source[start : match.start()], start))
        start = match.end()
    lines.append(_Line(source[start:], start))
    return lines


# ---------------------------------------------------------------------------
# Block pass
# ---------------------------------------------------------------------------

_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|center|col|"
    "colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|"
    "form|frame|frameset|h1|h2|h3|h4|h5|h6|head|header|hr|html|iframe|legend|li|"
    "link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|"
    "summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul"
)
_ATTRIBUTE = (
    r"(?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:\s*=\s*(?:[^\s\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)"
)
_OPEN_TAG = rf"<[A-Za-z][A-Za-z0-9-]*{_ATTRIBUTE}*\s*/?>"
_CLOSE_TAG = r"</[A-Za-z][A-Za-z0-9-]*\s*>"

#: (start, end, may interrupt a paragraph): CommonMark §4.6, conditions 1 to 7.
_HTML_BLOCKS: tuple[tuple[re.Pattern[str], re.Pattern[str] | None, bool], ...] = (
    (
        re.compile(r"<(?:script|pre|style|textarea)(?:[ \t>]|$)", re.IGNORECASE),
        re.compile(r"</(?:script|pre|style|textarea)>", re.IGNORECASE),
        True,
    ),
    (re.compile(r"<!--"), re.compile(r"-->"), True),
    (re.compile(r"<\?"), re.compile(r"\?>"), True),
    (re.compile(r"<![A-Za-z]"), re.compile(r">"), True),
    (re.compile(r"<!\[CDATA\["), re.compile(r"\]\]>"), True),
    (
        re.compile(rf"</?(?:{_BLOCK_TAGS})(?:[ \t]|/?>|$)", re.IGNORECASE),
        None,
        True,
    ),
    (re.compile(rf"(?:{_OPEN_TAG}|{_CLOSE_TAG})[ \t]*$"), None, False),
)

_ATX = re.compile(rf"#{{1,{GUIDE_MD_MAX_ATX_LEVEL}}}(?:[ \t]|$)")
_FENCE_OPEN = re.compile(rf"(`{{{GUIDE_MD_MIN_FENCE},}}|~{{{GUIDE_MD_MIN_FENCE},}})")
_THEMATIC = re.compile(rf"([-*_])(?:[ \t]*\1){{{GUIDE_MD_MIN_THEMATIC - 1},}}[ \t]*$")
_SETEXT = re.compile(r"(?:=+|-+)[ \t]*$")
_BULLET = re.compile(r"([-+*])(?:[ \t]|$)")
_ORDERED = re.compile(rf"(\d{{1,{GUIDE_MD_MAX_ORDERED_DIGITS}}})([.)])(?:[ \t]|$)")
_DELIMITER_CELL = re.compile(r"[ \t]*:?-+:?[ \t]*$")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


class _Leaf(enum.Enum):
    """The open leaf block."""

    PARAGRAPH = enum.auto()
    FENCE = enum.auto()
    HTML = enum.auto()
    INDENTED_CODE = enum.auto()
    TABLE = enum.auto()


_RAW_LEAVES = frozenset({_Leaf.FENCE, _Leaf.HTML, _Leaf.INDENTED_CODE})


@dataclass
class _Container:
    """An open block quote or list item."""

    is_quote: bool
    indent: int = 0
    has_content: bool = False


@dataclass
class _ParaLine:
    """One line of a paragraph."""

    index: int
    start: int
    tabby: bool
    delimiter_like: bool


@dataclass
class _OpenLeaf:
    """The open leaf block and what it needs to know."""

    kind: _Leaf
    lines: list[_ParaLine] = field(default_factory=list)
    fence_char: str = ""
    fence_length: int = 0
    html_end: re.Pattern[str] | None = None


class _Cursor:
    """A position in a line, with a column count that expands tabs (CommonMark §2.2)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.col = 0
        self.partial_tab = False

    def peek(self) -> tuple[int, int]:
        """Return ``(pos, col)`` of the next character that is not a space or tab."""
        pos, col = self.pos, self.col
        while pos < len(self.text) and self.text[pos] in _SPACE_TAB:
            col += self._width(self.text[pos], col)
            pos += 1
        return pos, col

    @staticmethod
    def _width(ch: str, col: int) -> int:
        """Return the columns that ``ch`` takes at column ``col``."""
        return GUIDE_MD_TAB_STOP - col % GUIDE_MD_TAB_STOP if ch == "\t" else 1

    def advance_columns(self, count: int) -> None:
        """Move forward by ``count`` columns; a tab cut in two is remembered."""
        while count > 0 and self.pos < len(self.text):
            width = self._width(self.text[self.pos], self.col)
            if width > count:
                self.col += count
                self.partial_tab = True
                return
            self.col += width
            self.pos += 1
            count -= width

    def set(self, pos: int, col: int) -> None:
        """Place the cursor."""
        self.pos, self.col = pos, col


def _split_cells(row: str) -> list[str]:
    """Split a table row at its unescaped pipes, dropping an outer pipe each end."""
    body = row.strip(_SPACE_TAB)
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return _UNESCAPED_PIPE.split(body)


def _delimiter_cells(row: str) -> int | None:
    """Return the cell count when ``row`` is a GitHub table delimiter row."""
    if "|" not in row:
        return None
    cells = _split_cells(row)
    if all(_DELIMITER_CELL.match(cell) for cell in cells):
        return len(cells)
    return None


def _normalise_label(label: str) -> str:
    """Normalise a link label for matching (CommonMark §4.7)."""
    return " ".join(label.split()).casefold()


class _BlockPass:
    """The block pass: finds the paragraphs and the link reference definitions."""

    def __init__(self, lines: list[_Line]) -> None:
        self.lines = lines
        self.stack: list[_Container] = []
        self.leaf: _OpenLeaf | None = None
        self.paragraphs: list[list[_ParaLine]] = []
        self.definitions: set[str] = set()
        self._matched = 0
        self._delimiter_like = False

    # -- driver ------------------------------------------------------------

    def run(self) -> None:
        """Process every line, then close what is open."""
        for index, line in enumerate(self.lines):
            self._line(index, line.text)
        self._close_leaf()

    @property
    def _all_matched(self) -> bool:
        return self._matched == len(self.stack)

    def _line(self, index: int, text: str) -> None:
        """Process one line."""
        cur = _Cursor(text)
        self._delimiter_like = False
        self._matched = self._match_containers(cur)
        leaf = self.leaf
        if leaf is not None and leaf.kind in _RAW_LEAVES:
            if self._all_matched and self._raw_continues(leaf, cur):
                return
            self.leaf = None
        while True:
            npos, ncol = cur.peek()
            if npos >= len(text):
                self._blank_line()
                return
            indent = ncol - cur.col
            in_paragraph = self._paragraph_is_open()
            if indent >= GUIDE_MD_CODE_INDENT:
                if in_paragraph:
                    break
                self._open_block()
                self.leaf = _OpenLeaf(_Leaf.INDENTED_CODE)
                self._mark_content(whole_stack=True)
                return
            outcome = self._block_start(cur, npos, ncol, text[npos:], index)
            if outcome == "leaf":
                return
            if outcome == "none":
                break
        self._text_line(index, text, cur)

    def _kind_is(self, kind: _Leaf) -> bool:
        return self.leaf is not None and self.leaf.kind is kind

    def _paragraph_is_open(self) -> bool:
        return self._kind_is(_Leaf.PARAGRAPH)

    def _para_in_matched(self) -> bool:
        """Return whether the open paragraph is in the matched innermost container."""
        return self._paragraph_is_open() and self._all_matched

    # -- containers --------------------------------------------------------

    def _match_containers(self, cur: _Cursor) -> int:
        """Match the open containers against the line; return how many matched."""
        text = cur.text
        matched = 0
        for container in self.stack:
            npos, ncol = cur.peek()
            blank = npos >= len(text)
            if container.is_quote:
                if blank or ncol - cur.col > GUIDE_MD_MAX_INDENT or text[npos] != ">":
                    break
                cur.set(npos + 1, ncol + 1)
                if cur.pos < len(text) and text[cur.pos] in _SPACE_TAB:
                    cur.advance_columns(1)
            elif blank:
                if not container.has_content:
                    break
            elif ncol - cur.col >= container.indent:
                cur.advance_columns(container.indent)
            else:
                break
            matched += 1
        return matched

    def _open_block(self) -> None:
        """Close the open leaf and the unmatched containers: a new block starts."""
        self._close_leaf()
        del self.stack[self._matched :]

    def _mark_content(self, *, whole_stack: bool) -> None:
        """Record that the containers now hold a block (an item is then not empty)."""
        containers = self.stack if whole_stack else self.stack[:-1]
        for container in containers:
            container.has_content = True

    # -- leaves ------------------------------------------------------------

    def _close_leaf(self) -> None:
        """Close the open leaf; a paragraph is kept for the inline pass."""
        leaf = self.leaf
        self.leaf = None
        if leaf is not None and leaf.kind is _Leaf.PARAGRAPH:
            self._finish_paragraph(leaf.lines)

    def _raw_continues(self, leaf: _OpenLeaf, cur: _Cursor) -> bool:
        """Return whether the raw leaf takes this line (closing it when it ends)."""
        text = cur.text
        npos, ncol = cur.peek()
        blank = npos >= len(text)
        indent = ncol - cur.col
        if leaf.kind is _Leaf.INDENTED_CODE:
            return blank or indent >= GUIDE_MD_CODE_INDENT
        if leaf.kind is _Leaf.HTML:
            if leaf.html_end is None:
                return not blank
            if leaf.html_end.search(text[cur.pos :]):
                self.leaf = None
            return True
        if indent <= GUIDE_MD_MAX_INDENT:
            closing = text[npos:].rstrip(_SPACE_TAB)
            if len(closing) >= leaf.fence_length and closing == leaf.fence_char * len(
                closing
            ):
                self.leaf = None
        return True

    def _blank_line(self) -> None:
        """Close a paragraph, a table and the unmatched containers at a blank line."""
        if self.leaf is not None:
            self._close_leaf()
        del self.stack[self._matched :]

    def _text_line(self, index: int, text: str, cur: _Cursor) -> None:
        """Take a line of text: continue the paragraph or start a new one."""
        npos, _ = cur.peek()
        # A tab in the container prefix cannot be removed with certainty; a tab in
        # the paragraph's own leading whitespace can (it is stripped whole).
        tabby = "\t" in text[: cur.pos] or cur.partial_tab
        paragraph_line = _ParaLine(index, npos, tabby, self._delimiter_like)
        leaf = self.leaf
        if leaf is not None and leaf.kind is _Leaf.PARAGRAPH:
            leaf.lines.append(paragraph_line)
            return
        if leaf is not None and leaf.kind is _Leaf.TABLE and self._all_matched:
            return
        self._open_block()
        self.leaf = _OpenLeaf(_Leaf.PARAGRAPH, [paragraph_line])
        self._mark_content(whole_stack=True)

    # -- block starts ------------------------------------------------------

    def _block_start(
        self, cur: _Cursor, npos: int, ncol: int, rest: str, index: int
    ) -> str:
        """Try the block starts in CommonMark's order.

        Returns:
            ``"container"`` after opening a quote or item (keep scanning),
            ``"leaf"`` when the line is consumed, ``"none"`` when no block starts.
        """
        text = cur.text
        if rest.startswith(">"):
            self._open_block()
            self._mark_content(whole_stack=True)
            self.stack.append(_Container(is_quote=True, has_content=True))
            cur.set(npos + 1, ncol + 1)
            if cur.pos < len(text) and text[cur.pos] in _SPACE_TAB:
                cur.advance_columns(1)
            self._matched = len(self.stack)
            return "container"
        # A table is ended by only a few lines; a heading, a fence or an HTML
        # block start under it is one more body row, as in Qt.
        in_table = self._kind_is(_Leaf.TABLE) and self._all_matched
        if not in_table:
            if _ATX.match(rest):
                self._single_line_block()
                return "leaf"
            if self._fence_start(rest):
                return "leaf"
            if self._html_start(rest):
                return "leaf"
        if self._para_in_matched() and _SETEXT.match(rest):
            self.leaf = None
            return "leaf"
        if self._table_start(rest):
            return "leaf"
        if _THEMATIC.match(rest):
            self._single_line_block()
            return "leaf"
        if self._item_start(cur, npos, ncol, rest):
            return "container"
        return "none"

    def _single_line_block(self) -> None:
        """Take a heading or a thematic break: it closes what is open, holds no text."""
        self._open_block()
        self._mark_content(whole_stack=True)

    def _fence_start(self, rest: str) -> bool:
        """Open a fenced code block when the line is a code fence."""
        match = _FENCE_OPEN.match(rest)
        if match is None:
            return False
        fence = match.group(1)
        if fence[0] == "`" and "`" in rest[len(fence) :]:
            return False
        self._open_block()
        self.leaf = _OpenLeaf(_Leaf.FENCE, fence_char=fence[0], fence_length=len(fence))
        self._mark_content(whole_stack=True)
        return True

    def _html_start(self, rest: str) -> bool:
        """Open an HTML block when the line starts one (CommonMark §4.6)."""
        if not rest.startswith("<"):
            return False
        for start, end, interrupts in _HTML_BLOCKS:
            if not start.match(rest):
                continue
            if self._para_in_matched() and not interrupts:
                continue
            self._open_block()
            self._mark_content(whole_stack=True)
            if end is None or not end.search(rest):
                self.leaf = _OpenLeaf(_Leaf.HTML, html_end=end)
            return True
        return False

    def _table_start(self, rest: str) -> bool:
        """Open a table when ``rest`` is a delimiter row under a one-line paragraph.

        Qt's rule: the paragraph's only line is the header and
        no cell count is compared. Under a longer paragraph the row is paragraph text,
        marked delimiter-shaped for the guards.
        """
        leaf = self.leaf
        if (
            leaf is None
            or _delimiter_cells(rest) is None
            or not self._para_in_matched()
        ):
            return False
        if len(leaf.lines) != 1:
            self._delimiter_like = True
            return False
        self.leaf = _OpenLeaf(_Leaf.TABLE)
        return True

    def _item_start(self, cur: _Cursor, npos: int, ncol: int, rest: str) -> bool:
        """Open a list item when the line starts one (CommonMark §5.2)."""
        bullet = _BULLET.match(rest)
        ordered = None if bullet else _ORDERED.match(rest)
        marker = bullet or ordered
        if marker is None:
            return False
        marker_width = len(marker.group(0).rstrip(_SPACE_TAB))
        blank_after = not rest[marker_width:].strip(_SPACE_TAB)
        if self._para_in_matched() and (
            blank_after or (ordered is not None and int(ordered.group(1)) != 1)
        ):
            return False
        marker_end_col = ncol + marker_width
        spaces = _Cursor(cur.text)
        spaces.set(npos + marker_width, marker_end_col)
        gap = spaces.peek()[1] - marker_end_col
        if blank_after or gap > GUIDE_MD_CODE_INDENT:
            gap = 1
        self._open_block()
        self._mark_content(whole_stack=True)
        self.stack.append(
            _Container(
                is_quote=False,
                indent=(ncol - cur.col) + marker_width + gap,
                has_content=not blank_after,
            )
        )
        cur.advance_columns((ncol - cur.col) + marker_width + gap)
        self._matched = len(self.stack)
        return True

    # -- paragraphs --------------------------------------------------------

    def _finish_paragraph(self, lines: list[_ParaLine]) -> None:
        """Keep a finished paragraph, without its leading link reference definitions."""
        raw = [
            self.lines[line.index].text[line.start :].rstrip(_SPACE_TAB)
            for line in lines
        ]
        joined = _NEWLINE.join(raw)
        pos = 0
        last_end: int | None = None
        while True:
            parsed = _parse_definition(joined, pos)
            if parsed is None:
                break
            label, last_end = parsed
            self.definitions.add(label)
            pos = last_end + 1
        if last_end is not None:
            lines = lines[joined.count(_NEWLINE, 0, last_end) + 1 :]
        if lines:
            self.paragraphs.append(lines)


# -- link syntax shared by the block pass (definitions) and the inline pass --------


def _skip_whitespace(text: str, pos: int) -> int:
    """Skip spaces, tabs and at most one line ending (CommonMark §6.3)."""
    while pos < len(text) and text[pos] in _SPACE_TAB:
        pos += 1
    if pos < len(text) and text[pos] == _NEWLINE:
        pos += 1
        while pos < len(text) and text[pos] in _SPACE_TAB:
            pos += 1
    return pos


def _parse_destination(text: str, pos: int) -> int | None:
    """Return the end of a link destination at ``pos``, or ``None``."""
    size = len(text)
    if pos < size and text[pos] == "<":
        i = pos + 1
        while i < size:
            ch = text[i]
            if ch == "\\" and i + 1 < size and text[i + 1] in _ASCII_PUNCT:
                i += GUIDE_MD_ESCAPE_LENGTH
                continue
            if ch in "\n<":
                return None
            if ch == ">":
                return i + 1
            i += 1
        return None
    depth = 0
    i = pos
    while i < size:
        ch = text[i]
        if ch == "\\" and i + 1 < size and text[i + 1] in _ASCII_PUNCT:
            i += GUIDE_MD_ESCAPE_LENGTH
            continue
        if ch.isspace() or unicodedata.category(ch) == "Cc":
            break
        if ch == "(":
            depth += 1
            if depth > GUIDE_MD_MAX_PAREN_DEPTH:
                return None
        elif ch == ")":
            if depth == 0:
                break
            depth -= 1
        i += 1
    return i if depth == 0 else None


def _parse_title(text: str, pos: int) -> int | None:
    """Return the end of a link title at ``pos``, or ``None``."""
    if pos >= len(text) or text[pos] not in "\"'(":
        return None
    closer = ")" if text[pos] == "(" else text[pos]
    i = pos + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in _ASCII_PUNCT:
            i += GUIDE_MD_ESCAPE_LENGTH
            continue
        if ch == closer:
            return i + 1
        if ch == "(" and closer == ")":
            return None
        i += 1
    return None


def _parse_label(text: str, pos: int) -> int | None:
    """Return the index after the ``]`` of a link label that starts at ``pos``."""
    if pos >= len(text) or text[pos] != "[":
        return None
    i = pos + 1
    while i < len(text) and i - pos <= GUIDE_MD_MAX_LABEL_CHARS:
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in _ASCII_PUNCT:
            i += GUIDE_MD_ESCAPE_LENGTH
            continue
        if ch == "[":
            return None
        if ch == "]":
            return i + 1
        i += 1
    return None


def _parse_definition(text: str, pos: int) -> tuple[str, int] | None:
    """Parse a link reference definition at ``pos``.

    Returns:
        ``(normalised label, index of the end of the definition's last line)`` or
        ``None``.
    """
    end = _parse_label(text, pos)
    if end is None or end >= len(text) or text[end] != ":":
        return None
    label = _normalise_label(text[pos + 1 : end - 1])
    if not label:
        return None
    start = _skip_whitespace(text, end + 1)
    dest_end = _parse_destination(text, start)
    if dest_end is None or dest_end == start:
        return None
    line_end = _line_end(text, dest_end)
    title_start = _skip_whitespace(text, dest_end)
    if title_start > dest_end:
        title_end = _parse_title(text, title_start)
        if title_end is not None:
            title_line_end = _line_end(text, title_end)
            if not text[title_end:title_line_end].strip(_SPACE_TAB):
                return label, title_line_end
    if text[dest_end:line_end].strip(_SPACE_TAB):
        return None
    return label, line_end


def _line_end(text: str, pos: int) -> int:
    """Return the index of the line ending at or after ``pos`` (or the end)."""
    found = text.find(_NEWLINE, pos)
    return len(text) if found < 0 else found


# ---------------------------------------------------------------------------
# Inline pass
# ---------------------------------------------------------------------------


class _Kind(enum.Enum):
    """What a character of a paragraph's text is, for finding its neighbours."""

    VISIBLE = enum.auto()
    MARKUP = enum.auto()  # shown as nothing; skipped when looking for a neighbour
    OPAQUE = enum.auto()  # a reference, a tag, an image: not classified
    LINE_ENDING = enum.auto()
    EXCLUDED = enum.auto()  # a line ending inside a code span, a tag or a destination


_ENTITY = re.compile(
    rf"&(?:[A-Za-z][A-Za-z0-9]{{1,{GUIDE_MD_MAX_ENTITY_NAME - 1}}}"
    rf"|#[0-9]{{1,{GUIDE_MD_MAX_DECIMAL_REF_DIGITS}}}"
    rf"|#[xX][0-9a-fA-F]{{1,{GUIDE_MD_MAX_HEX_REF_DIGITS}}});"
)
_AUTOLINK = re.compile(r"<(?:[A-Za-z][A-Za-z0-9+.-]+:[^\s<>]*|[^\s<>@]+@[^\s<>@]+)>")
_RAW_HTML = re.compile(
    rf"<!--(?:-?>|.*?-->)|<\?.*?\?>|<![A-Za-z][^>]*>|<!\[CDATA\[.*?\]\]>"
    rf"|{_OPEN_TAG}|{_CLOSE_TAG}",
    re.DOTALL,
)


@dataclass
class _Delimiter:
    """A run of ``*``, ``_`` or ``~`` that may open or close emphasis."""

    pos: int
    char: str
    original: int
    count: int
    can_open: bool
    can_close: bool


@dataclass
class _Bracket:
    """An open ``[`` or ``![``."""

    pos: int
    is_image: bool
    delimiter_start: int
    active: bool = True


def _is_whitespace(ch: str | None) -> bool:
    """Return whether ``ch`` is Unicode whitespace; the text edges count as such."""
    return ch is None or ch in "\t\n\f\r" or unicodedata.category(ch) == "Zs"


def _is_punctuation(ch: str | None) -> bool:
    """Return whether ``ch`` is Unicode punctuation or a symbol (CommonMark 0.31)."""
    return ch is not None and unicodedata.category(ch)[0] in "PS"


class _InlinePass:
    """Classifies every character of one paragraph's text."""

    def __init__(self, text: str, definitions: set[str]) -> None:
        self.text = text
        self.definitions = definitions
        self.kinds = [_Kind.VISIBLE] * len(text)
        self.delimiters: list[_Delimiter] = []
        self.brackets: list[_Bracket] = []

    def run(self) -> list[_Kind]:
        """Scan the text and return a kind for each character."""
        text, size, i = self.text, len(self.text), 0
        while i < size:
            ch = text[i]
            if ch == _NEWLINE:
                self.kinds[i] = _Kind.LINE_ENDING
                i += 1
            elif ch == "\\":
                i = self._backslash(i)
            elif ch == "`":
                i = self._code_span(i)
            elif ch == "&":
                i = self._reference(i)
            elif ch == "<":
                i = self._angle(i)
            elif ch in _EMPHASIS_CHARS:
                i = self._delimiter_run(i)
            elif text.startswith((_LINK_OPEN, _IMAGE_OPEN), i):
                i = self._open_bracket(i)
            elif ch == "]":
                i = self._close_bracket(i)
            else:
                i += 1
        self._process_emphasis(0)
        return self.kinds

    def _mark(self, start: int, end: int, kind: _Kind) -> None:
        """Mark ``text[start:end]``; a line ending inside becomes ``EXCLUDED``."""
        for j in range(start, end):
            self.kinds[j] = _Kind.EXCLUDED if self.text[j] == _NEWLINE else kind

    def _backslash(self, i: int) -> int:
        if i + 1 < len(self.text) and self.text[i + 1] in _ASCII_PUNCT:
            self.kinds[i] = _Kind.MARKUP
            return i + GUIDE_MD_ESCAPE_LENGTH
        return i + 1

    def _code_span(self, i: int) -> int:
        text = self.text
        run_end = i
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        length = run_end - i
        j = run_end
        while j < len(text):
            if text[j] != "`":
                j += 1
                continue
            close_end = j
            while close_end < len(text) and text[close_end] == "`":
                close_end += 1
            if close_end - j == length:
                self._finish_code_span(i, run_end, j, close_end)
                return close_end
            j = close_end
        return run_end

    def _finish_code_span(self, open_at: int, start: int, stop: int, end: int) -> None:
        """Mark a code span: its content is visible, its line endings excluded."""
        content = self.text[start:stop].replace(_NEWLINE, " ")
        lo, hi = start, stop
        if content.strip(" ") and content[0] == " " and content[-1] == " ":
            lo, hi = start + 1, stop - 1
        self._mark(open_at, start, _Kind.MARKUP)
        self._mark(stop, end, _Kind.MARKUP)
        for j in range(start, stop):
            if self.text[j] == _NEWLINE:
                self.kinds[j] = _Kind.EXCLUDED
            elif lo <= j < hi:
                self.kinds[j] = _Kind.VISIBLE
            else:
                self.kinds[j] = _Kind.MARKUP
        if lo >= hi:
            self._mark(start, stop, _Kind.OPAQUE)

    def _reference(self, i: int) -> int:
        match = _ENTITY.match(self.text, i)
        if match is None:
            return i + 1
        self._mark(i, match.end(), _Kind.OPAQUE)
        return match.end()

    def _angle(self, i: int) -> int:
        match = _AUTOLINK.match(self.text, i) or _RAW_HTML.match(self.text, i)
        if match is None:
            return i + 1
        self._mark(i, match.end(), _Kind.OPAQUE)
        return match.end()

    def _delimiter_run(self, i: int) -> int:
        text = self.text
        char = text[i]
        end = i
        while end < len(text) and text[end] == char:
            end += 1
        count = end - i
        if char == "~" and count > GUIDE_MD_MAX_STRIKE_RUN:
            return end
        before = text[i - 1] if i > 0 else None
        after = text[end] if end < len(text) else None
        left = not _is_whitespace(after) and (
            not _is_punctuation(after)
            or _is_whitespace(before)
            or _is_punctuation(before)
        )
        right = not _is_whitespace(before) and (
            not _is_punctuation(before)
            or _is_whitespace(after)
            or _is_punctuation(after)
        )
        if char == "_":
            can_open = left and (not right or _is_punctuation(before))
            can_close = right and (not left or _is_punctuation(after))
        else:
            can_open, can_close = left, right
        self.delimiters.append(_Delimiter(i, char, count, count, can_open, can_close))
        return end

    def _process_emphasis(self, start: int) -> None:
        """Match delimiter runs from ``start`` (CommonMark §6.2, appendix)."""
        index = start
        while index < len(self.delimiters):
            closer = self.delimiters[index]
            if not closer.can_close or closer.count == 0:
                index += 1
                continue
            opener_at = self._find_opener(index, start)
            if opener_at is None:
                index += 1
                continue
            opener = self.delimiters[opener_at]
            if closer.char == "~":
                used = closer.count
            else:
                used = (
                    GUIDE_MD_STRONG_RUN
                    if opener.count >= GUIDE_MD_STRONG_RUN
                    and closer.count >= GUIDE_MD_STRONG_RUN
                    else 1
                )
            first = opener.pos + opener.count - used
            self._mark(first, first + used, _Kind.MARKUP)
            second = closer.pos + closer.original - closer.count
            self._mark(second, second + used, _Kind.MARKUP)
            opener.count -= used
            closer.count -= used
            for between in self.delimiters[opener_at + 1 : index]:
                between.count = 0
            if closer.count == 0:
                index += 1

    def _find_opener(self, index: int, start: int) -> int | None:
        """Return the delimiter that the closer at ``index`` matches, if any."""
        closer = self.delimiters[index]
        for j in range(index - 1, start - 1, -1):
            opener = self.delimiters[j]
            if opener.char != closer.char or not opener.can_open or opener.count == 0:
                continue
            if closer.char == "~":
                if opener.original == closer.original:
                    return j
                continue
            both = closer.can_open or opener.can_close
            total = opener.original + closer.original
            if (
                both
                and total % GUIDE_MD_EMPHASIS_MODULUS == 0
                and not (
                    opener.original % GUIDE_MD_EMPHASIS_MODULUS == 0
                    and closer.original % GUIDE_MD_EMPHASIS_MODULUS == 0
                )
            ):
                continue
            return j
        return None

    def _open_bracket(self, i: int) -> int:
        is_image = self.text.startswith(_IMAGE_OPEN, i)
        self.brackets.append(_Bracket(i, is_image, len(self.delimiters)))
        return i + len(_IMAGE_OPEN if is_image else _LINK_OPEN)

    def _close_bracket(self, i: int) -> int:
        if not self.brackets:
            return i + 1
        opener = self.brackets[-1]
        if not opener.active:
            self.brackets.pop()
            return i + 1
        end = self._link_end(i, opener)
        if end is None:
            self.brackets.pop()
            return i + 1
        self._process_emphasis(opener.delimiter_start)
        del self.delimiters[opener.delimiter_start :]
        if opener.is_image:
            self._mark(opener.pos, end, _Kind.OPAQUE)
        else:
            self._mark(opener.pos, opener.pos + len(_LINK_OPEN), _Kind.MARKUP)
            self._mark(i, end, _Kind.MARKUP)
            for earlier in self.brackets[:-1]:
                if not earlier.is_image:
                    earlier.active = False
        self.brackets.pop()
        return end

    def _link_end(self, i: int, opener: _Bracket) -> int | None:
        """Return the end of the link or image that the ``]`` at ``i`` closes."""
        text = self.text
        content_start = opener.pos + len(_IMAGE_OPEN if opener.is_image else _LINK_OPEN)
        after = i + 1
        if after < len(text) and text[after] == "(":
            inline = self._inline_destination(after + 1)
            if inline is not None:
                return inline
        if after < len(text) and text[after] == "[":
            label_end = _parse_label(text, after)
            if label_end is not None:
                label = text[after + 1 : label_end - 1] or text[content_start:i]
                if _normalise_label(label) in self.definitions:
                    return label_end
        if _normalise_label(text[content_start:i]) in self.definitions:
            return after
        return None

    def _inline_destination(self, pos: int) -> int | None:
        """Parse ``dest "title")`` after the ``(`` of an inline link."""
        text = self.text
        start = _skip_whitespace(text, pos)
        dest_end = _parse_destination(text, start)
        if dest_end is None:
            return None
        after = _skip_whitespace(text, dest_end)
        if after > dest_end:
            title_end = _parse_title(text, after)
            if title_end is not None:
                after = _skip_whitespace(text, title_end)
        if after < len(text) and text[after] == ")":
            return after + 1
        return None


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Edit:
    """Replace ``source[start:end]`` (a removed break) with ``text``."""

    start: int
    end: int
    text: str


def _is_hard_break(raw: str) -> bool:
    """Return whether a line (with its trailing spaces) ends in a hard line break."""
    spaces = len(raw) - len(raw.rstrip(" "))
    if spaces >= GUIDE_MD_HARD_BREAK_SPACES:
        return True
    backslashes = len(raw) - len(raw.rstrip("\\"))
    return backslashes % GUIDE_MD_ESCAPE_LENGTH == 1


def _neighbour(kinds: list[_Kind], text: str, start: int, step: int) -> str | None:
    """Return the nearest visible character from ``start`` going ``step``."""
    j = start
    while 0 <= j < len(text) and kinds[j] is _Kind.MARKUP:
        j += step
    if 0 <= j < len(text) and kinds[j] is _Kind.VISIBLE:
        return text[j]
    return None


def _forms_link_shape(before_raw: str, after_raw: str) -> bool:
    """Return whether a run beside a break has the shape of a permissive link.

    The run is the characters other than space, tab and line endings that end at
    the break (``before_raw``) or start after it (``after_raw``). Qt links bare
    addresses; the scanner does not model that, so the shape alone keeps the break
    (the link-shape guard).
    """
    trimmed = before_raw.rstrip(_SPACE_TAB)
    run_before = _RUN_BREAK.split(trimmed)[-1]
    run_after = _RUN_BREAK.split(after_raw, 1)[0]
    return any(
        token in run.lower()
        for run in (run_before, run_after)
        for token in _LINK_SHAPE_TOKENS
    )


@dataclass(frozen=True)
class _Candidate:
    """A soft break that a clause would remove, before the paragraph-wide check."""

    index: int  # index k of the paragraph line that ends at the break
    newline_at: int  # offset of the break's line ending in the paragraph text
    soft_break: SoftBreak


def _keeps_parse(
    text: str, kinds: list[_Kind], definitions: set[str], cuts: dict[int, str]
) -> bool:
    """Return whether joining at ``cuts`` leaves every other character's kind alone.

    ``cuts`` maps the offset of each removed line ending to what replaces it. The
    inline pass runs once more over the joined text; a character
    that was visible, markup or opaque must still be so.
    """
    pieces: list[str] = []
    survivors: list[tuple[int, int]] = []
    size = 0
    for i, ch in enumerate(text):
        if i in cuts:
            pieces.append(cuts[i])
            size += len(cuts[i])
        else:
            pieces.append(ch)
            survivors.append((i, size))
            size += 1
    joined = _InlinePass("".join(pieces), definitions).run()
    return all(joined[after] is kinds[before] for before, after in survivors)


def _examine_paragraph(
    source: str,
    lines: list[_Line],
    paragraph: list[_ParaLine],
    definitions: set[str],
    language: str,
    breaks: list[SoftBreak],
    edits: list[_Edit],
) -> None:
    """Find, decide and record the soft breaks of one paragraph."""
    raws = [lines[p.index].text[p.start :] for p in paragraph]
    text = _NEWLINE.join(raw.rstrip(_SPACE_TAB) for raw in raws)
    kinds = _InlinePass(text, definitions).run()
    position = 0
    found: list[SoftBreak | _Candidate] = []
    for k in range(len(paragraph) - 1):
        position += len(raws[k].rstrip(_SPACE_TAB))
        newline_at = position
        position += 1
        if _is_hard_break(raws[k]) or kinds[newline_at] is _Kind.EXCLUDED:
            continue
        line_number = paragraph[k].index + 1
        before = _neighbour(kinds, text, newline_at - 1, -1)
        after = _neighbour(kinds, text, newline_at + 1, 1)
        following = paragraph[k + 1]
        if (
            before is None
            or after is None
            or following.tabby
            or following.delimiter_like
        ):
            found.append(
                SoftBreak(
                    line_number, before or "", after or "", SoftBreakClause.UNDECIDED
                )
            )
            continue
        clause = decide(before, after, language)
        if not clause.removes:
            found.append(SoftBreak(line_number, before, after, clause))
        elif (
            paragraph[k].delimiter_like
            or (k + 2 < len(paragraph) and paragraph[k + 2].delimiter_like)
            or _forms_link_shape(raws[k], raws[k + 1])
        ):
            found.append(
                SoftBreak(line_number, before, after, SoftBreakClause.UNDECIDED)
            )
        else:
            found.append(
                _Candidate(k, newline_at, SoftBreak(line_number, before, after, clause))
            )
    candidates = [item for item in found if isinstance(item, _Candidate)]
    if candidates:
        cuts = {
            c.newline_at: _joiner_for(source, lines, paragraph, c.index)
            for c in candidates
        }
        if not _keeps_parse(text, kinds, definitions, cuts):
            candidates = []
    kept = {id(c) for c in candidates}
    for item in found:
        if isinstance(item, SoftBreak):
            breaks.append(item)
        elif id(item) in kept:
            breaks.append(item.soft_break)
            edits.append(_edit_for(source, lines, paragraph, item.index))
        else:
            old = item.soft_break
            breaks.append(
                SoftBreak(old.line, old.before, old.after, SoftBreakClause.UNDECIDED)
            )


def _joiner_for(
    source: str, lines: list[_Line], paragraph: list[_ParaLine], k: int
) -> str:
    """Return what replaces the removed break after paragraph line ``k``.

    The joiner goes between the source character before the break (L) and the first
    one after it (R) when one of the pairs of :data:`_JOINER_PAIRS` holds: an emphasis
    character on either side, two backticks, ``]`` before ``(``, ``[`` or ``:``, or
    ``!`` before ``[``. Otherwise nothing is left.
    """
    this, following = lines[paragraph[k].index], lines[paragraph[k + 1].index]
    start = this.offset + len(this.text.rstrip(_SPACE_TAB))
    end = following.offset + paragraph[k + 1].start
    left, right = source[start - 1], source[end]
    if left in _EMPHASIS_CHARS or right in _EMPHASIS_CHARS:
        return SOFT_BREAK_JOINER
    return SOFT_BREAK_JOINER if (left, right) in _JOINER_PAIRS else ""


def _edit_for(
    source: str, lines: list[_Line], paragraph: list[_ParaLine], k: int
) -> _Edit:
    """Return the edit that removes the break after paragraph line ``k``."""
    this, following = lines[paragraph[k].index], lines[paragraph[k + 1].index]
    start = this.offset + len(this.text.rstrip(_SPACE_TAB))
    end = following.offset + paragraph[k + 1].start
    return _Edit(start, end, _joiner_for(source, lines, paragraph, k))


def apply_soft_break_rule(markdown: str, language: str) -> SoftBreakResult:
    """Remove the soft line breaks of ``markdown`` that are not shown as a space.

    Pure, linear in the length of the page, and raising nothing for any ``str``. A
    page in which no break is removed is returned byte for byte.

    The transform is idempotent: for every ``str`` ``x`` and
    every language ``L``, applying it to its own output returns that output
    unchanged, and the second pass removes no break. The ``breaks`` that the second
    pass reports are not part of the property: line numbers move, and a kept break's
    label may change from clause 5 to ``UNDECIDED``, never the other way.

    Args:
        markdown: A guide page's Markdown source.
        language: The page's language: the guide folder it came from (see
            :func:`pixelart_creator.logic.guide_model.content_ref_locale`).

    Returns:
        The transformed source and every candidate break that was examined.
    """
    lines = _split_lines(markdown)
    block = _BlockPass(lines)
    block.run()
    breaks: list[SoftBreak] = []
    edits: list[_Edit] = []
    for paragraph in block.paragraphs:
        _examine_paragraph(
            markdown, lines, paragraph, block.definitions, language, breaks, edits
        )
    if not edits:
        return SoftBreakResult(markdown, tuple(breaks))
    pieces: list[str] = []
    cursor = 0
    for edit in edits:
        pieces.append(markdown[cursor : edit.start])
        pieces.append(edit.text)
        cursor = edit.end
    pieces.append(markdown[cursor:])
    return SoftBreakResult("".join(pieces), tuple(breaks))
