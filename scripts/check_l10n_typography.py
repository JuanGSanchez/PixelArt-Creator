#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_l10n_typography  (standalone script — PixelArt Creator)
# =============================================================================
# PURPOSE: Enforce the mechanically decidable typography rules of
#   REQ-L10N-DATA-004 on two surfaces: the translation catalogues (``.ts``) and
#   the user-guide page trees (``.md``). One rule table, one count per rule:
#     fr-nbsp     French: a ``? ! ; :`` that follows a word is preceded by
#                 U+00A0 (not by no space, not by an ordinary space), and the
#                 inside of a quotation is spaced the same way: exactly one
#                 U+00A0 after ``«`` and before ``»`` when text follows or
#                 precedes on the same line. Both surfaces. One rule, two
#                 sub-counts (marks, guillemet sides) that add up to the
#                 examined count, so a French batch with no quotation is not
#                 blind.
#     fr-num-unit  French, catalogue, worklist and guide: a number (digits, a
#                 ``%n`` / ``%1``..``%9`` placeholder or a ``{name}`` / ``{0:.0f}``
#                 format field) followed by a space and then a unit from the
#                 explicit list ``UNITS`` below must be joined to it by exactly
#                 one U+00A0 (fr.md 5.1, 5.4): an ordinary U+0020 or a U+202F is
#                 a finding. Examined = fr entries (catalogue messages,
#                 worklist entries) or fr guide pages scanned, so a French batch
#                 with no unit is not blind; the number+unit pairs found (U+00A0
#                 ones included) are a sub-count with no zero-failure. The unit
#                 list and its count are printed with the rule. Count nouns
#                 (``%n images``, ``%n points``) are not units; only
#                 ``images par seconde`` is.
#     ru-no-straight-quote  Russian: no U+0022 in prose, where the language
#                 takes « » (markup attributes, code spans and link targets
#                 are not prose). Both surfaces.
#     no-u202f   No U+202F (narrow no-break space) in any scanned file, in
#                 any spelling: the character itself or a numeric character
#                 reference (&#x202f;, &#8239;). Both surfaces, every language.
#     ellipsis    Catalogue only: a finished translation holds as many U+2026
#                 as its source message, no space before one, and no run of
#                 three periods unless its source has one.
#     ko-no-han   Korean: no Han character outside the eight language
#                 self-names. Both surfaces.
#     zh-fullwidth  Simplified Chinese catalogue only: no U+FF1A, U+FF01,
#                 U+FF1F, U+FF08, U+FF09 in a finished translation. The
#                 Chinese guide pages take those marks full-width and are
#                 never scanned for them (reported as excluded).
#   zh-space-han-latin  Simplified Chinese GUIDE PAGES only (never ``ja`` pages,
#                 never catalogue messages): rule (a), exactly one U+0020 between
#                 a Han character and an adjacent Latin letter or decimal digit,
#                 in either order; full-width Latin letters and digits count.
#     zh-space-mark-latin  rule (b), exactly one U+0020 between a full-width
#                 punctuation mark (category P, width F or W, plus U+201C and
#                 U+201D) and an adjacent Latin letter or digit, and between such a
#                 mark and a number's symbol (a listed trailing symbol after a
#                 number, a listed opening symbol before one). Two sub-counts:
#                 mark edges, symbol edges.
#     zh-num-unit-closed  rule (c), a number and a Latin unit from the explicit
#                 list ZH_NUM_UNITS (printed) written closed: no space character
#                 of any kind, and no soft line break the guide shows as a space,
#                 between them. Sub-count: pairs.
#     zh-space-symbol  rule (d), exactly one U+0020 between a number's listed
#                 trailing symbol (ZH_TRAILING_SYMBOLS, printed) and a following Han
#                 character, and between Han and a listed opening symbol
#                 (ZH_OPENING_SYMBOLS, printed) before a number. Sub-counts:
#                 trailing-symbol edges, opening-symbol edges.
#                 The four rules read the SHOWN text: markup is not a character, a
#                 code span's first and last characters are, its inside, a link
#                 destination and an image path are not examined. A soft line
#                 break counts as the one space where the guide shows it as one;
#                 where the guide hides it (REQ-L10N-UI-014) at an edge that takes
#                 a space, the break is a finding that names it. Which breaks exist
#                 and which are hidden is decided by logic/guide_softbreak.py of the
#                 product, loaded by file path (stdlib only); East Asian Width
#                 comes from the running interpreter's unicodedata. Each rule
#                 examines pages (one per page) and prints its edges or pairs as a
#                 sub-count that may be 0; with no zh_CN page every one of the four
#                 exits 1 and says "nothing examined".
#                 A VERBATIM QUOTATION of an interface message is exempt from all four
#                 (REQ-L10N-DATA-004, round 21, Q-61): a run of the shown text equal
#                 to the whole finished translation of one message of the zh_CN
#                 catalogue (read from --catalogues, else the product default).
#                 Each placeholder (%1..%99, %n, %L1.., {field}) matches the
#                 shortest non-empty run; an access-key & is not a character and
#                 the suffix " (&X)" may stand or be left out; a message with no
#                 letter or Han character outside its placeholders quotes no
#                 wording and exempts nothing. Only the inside is exempt: an edge
#                 between the quotation and the page's own text beside it is judged,
#                 and edges inside are counted but not judged. A quotation is
#                 counted only when it exempted at least one edge or pair. The
#                 report prints the number of quotations exempted and, for each,
#                 its page, line and the message's source text (JSON:
#                 ``zh_quotations`` and ``quotations_exempted`` on each of the four
#                 rows), so that no exemption is silent.
#   Registers (address forms) and the judgments that stay with a reviewer (the
#   French quotation style as a whole, spacing inside Russian « ») are not
#   decided here.
# FLAVOUR: standalone
# LOCATION: scripts/check_l10n_typography.py
# INVOKED BY: the localisation role, as an acceptance gate on every catalogue
#   or guide-topic translation batch; and by CI over the committed catalogues
#   and guide trees.
# RUNTIME: Python 3.12+ (CPython; stdlib only; the zh_CN rules read the product's
#   logic/guide_softbreak.py by file path and print the Unicode versions they
#   used). The catalogue reader is the one
#   in the sibling ``check_catalogues.py``, loaded from this script's folder;
#   the language self-names are read from ``logic/language_names.py`` of the
#   product root, by file path, so the list is defined once.
# ENTRYPOINT: python scripts/check_l10n_typography.py [--root DIR]
#   [--catalogues DIR] [--guide-root DIR] [--surface catalogue|guide|both]
#   [--languages a,b] [--json]
#   python scripts/check_l10n_typography.py --worklist FILE [--root DIR] [--json]
# INPUTS:
#   --worklist    a translation worklist (JSON) instead of the folders: the
#                 catalogue rules run over its entries with every form filled,
#                 under the surface name ``worklist``, in the language the
#                 worklist names. The report gives the examined count beside
#                 the worklist's entry count and its unfilled count. It cannot
#                 be combined with --catalogues, --guide-root or --surface.
#   --root        product root (default: the parent of this script's folder).
#   --catalogues  folder holding ``pixelart_<code>.ts`` (default
#                 ``pixelart_creator/i18n`` under the root).
#   --guide-root  folder holding one sub-folder of ``.md`` pages per language
#                 (default ``pixelart_creator/userguide_content/content``).
#   --surface     which surface to scan (default both). A default folder that
#                 does not exist is reported and skipped; one named on the
#                 command line that does not exist is an error.
#   --languages   comma-separated language codes to keep (default all found).
# OUTPUTS: one line per (rule, surface, language) with the number examined and
#   the findings, then a total; with ``--json`` one JSON document on stdout.
# EXIT CODES: 0 clean; 1 a finding, or a rule that applied examined nothing,
#   or nothing at all was examined; 2 an input is missing or unreadable.
# DETERMINISM NOTE: pure function of the files read; files in sorted order.
# =============================================================================
"""Check the mechanically decidable typography rules of the translations."""

import argparse
import bisect
import importlib.util
import json
import os
import re
import sys
import unicodedata
from typing import Any, NamedTuple

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2

NBSP = " "
NARROW_NBSP = " "
ELLIPSIS = "…"
ZH_FULLWIDTH = "：！？（）"
OPENING = "«"
CLOSING = "»"
STRAIGHT = '"'
# Units that take U+00A0 after a number (fr-num-unit): (label, regex source).
# Symbols carry no word boundary of their own; words must end at a non-word.
UNITS = (
    ("px", r"px"),
    ("ms", r"ms"),
    ("mm", r"mm"),
    ("cm", r"cm"),
    ("PPI", r"PPI"),
    ("%", r"%"),
    ("\u00b0", r"\u00b0"),
    ("octet/octets/octet(s)", r"octets?(?:\(s\))?"),
    ("Ko", r"Ko"),
    ("Mo", r"Mo"),
    ("Go", r"Go"),
    ("milliseconde/millisecondes/milliseconde(s)", r"millisecondes?(?:\(s\))?"),
    ("seconde/secondes/seconde(s)", r"secondes?(?:\(s\))?"),
    ("image(s) par seconde", r"images?(?:\(s\))? par seconde"),
)
_UNIT_ALTERNATIVES = "|".join(pattern for _label, pattern in UNITS)
NUM_UNIT = re.compile(
    r"(?P<num>(?<![\w%{.,])\d+(?:[.,]\d+)*|%L?(?:n|[1-9])|\{[^{}\n]*\})"
    r"(?P<gap>[ " + NBSP + NARROW_NBSP + r"]+)"
    r"(?P<unit>(?:" + _UNIT_ALTERNATIVES + r")(?![\w]))"
)
SURFACES = ("catalogue", "guide")
SHOWN = 20

# Characters after a mark that still count as the end of its word group.
CLOSERS = frozenset(")]}»”’\"'")
# Characters before a mark that make it follow a word.
WORD_ENDERS = frozenset(")»”’\"'" + ELLIPSIS)
MARKS = re.compile(r"[?!;:]+")
THREE_PERIODS = re.compile(r"\.{3,}")
SPACE_BEFORE_ELLIPSIS = re.compile("[ \t" + NBSP + NARROW_NBSP + "]" + ELLIPSIS)
HAN = re.compile("[⺀-⿟㐀-䶿一-鿿豈-﫿\U00020000-\U0003134f]")
MD_BLOCKS = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.DOTALL | re.MULTILINE),
    re.compile(r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t:-]*)*$", re.MULTILINE),
)
MD_FILLED = (
    re.compile(r"`[^`\n]*`"),
    re.compile(r"\]\([^)\n]*\)"),
    re.compile(r"<(?:https?|mailto):[^>\n]*>"),
    re.compile(r"https?://[^\s)>\]]*"),
)
MD_DROPPED = (
    re.compile(r"</?[A-Za-z][^<>\n]*>"),
    re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#[xX][0-9A-Fa-f]+);"),
)


class TypographyError(Exception):
    """Raised when an input cannot be found or read."""


def _sibling(name: str, path: str):
    """Load a Python file by path and register it under ``name``."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None or not os.path.isfile(path):
        raise TypographyError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def _catalogue_reader():
    """Return the sibling catalogue reader module."""
    here = os.path.dirname(os.path.abspath(__file__))
    return _sibling("check_catalogues", os.path.join(here, "check_catalogues.py"))


def load_endonyms(root: str) -> tuple:
    """Return the language self-names defined once in the product."""
    path = os.path.join(root, "pixelart_creator", "logic", "language_names.py")
    module = _sibling("pixelart_language_names", path)
    return tuple(sorted(set(module.ENDONYMS.values()), key=len, reverse=True))


def primary(language: str) -> str:
    """Return the primary subtag of a language code (``zh_CN`` -> ``zh``)."""
    return re.split(r"[_-]", language)[0] if language else ""


def _blank(match) -> str:
    """Return a stand-in of the same line structure, with word characters."""
    return "".join("\n" if ch == "\n" else "_" for ch in match.group())


def _vanish(match) -> str:
    """Return only the line breaks of a match."""
    return "".join(ch for ch in match.group() if ch == "\n")


def markdown_prose(text: str) -> str:
    """Return a page with non-prose spans neutralised, line numbers kept.

    HTML comments, fenced blocks and table separator rows are removed; inline
    code, link targets and bare addresses become word characters; markup tags
    and entities are removed.
    """
    for pattern in MD_BLOCKS:
        text = pattern.sub(_vanish, text)
    for pattern in MD_FILLED:
        text = pattern.sub(_blank, text)
    for pattern in MD_DROPPED:
        text = pattern.sub(_vanish, text)
    return text


def markup_free(text: str, catalogues) -> str:
    """Return a catalogue string without entities and markup tags."""
    return catalogues.TAG.sub("", catalogues.ENTITY.sub("", text))


def nbsp_problems(text: str) -> tuple:
    """Return ``(examined, [(offset, detail)])`` for the French spacing rule.

    A run of ``? ! ; :`` is examined when it follows a word (a letter, a digit
    or a closing mark) or a space, and ends a word group (end of text, a space
    or a closing mark follows). Addresses, times and entities therefore pass
    untouched. It must be preceded by exactly one U+00A0.
    """
    examined = 0
    problems = []
    for match in MARKS.finditer(text):
        start, end = match.span()
        if start == 0 or text[start - 1] == "\n":
            continue
        after = text[end : end + 1]
        if after and not (after.isspace() or after in CLOSERS):
            continue
        before = text[start - 1]
        if before == NBSP:
            examined += 1
        elif before.isspace():
            if start == 1 or text[start - 2] == "\n":
                continue
            examined += 1
            shown = "U+202F" if before == NARROW_NBSP else "an ordinary space"
            problems.append((start, f"{match.group()!r} is preceded by {shown}"))
        elif before.isalnum() or before == "_" or before in WORD_ENDERS:
            examined += 1
            problems.append((start, f"{match.group()!r} has no space before it"))
    return examined, problems


def _space_name(char: str) -> str:
    """Name a space character for a finding."""
    if char == NARROW_NBSP:
        return "U+202F"
    if char == " ":
        return "an ordinary space"
    return f"U+{ord(char):04X}"


def _inner_space(side: str, glyph: str, space: str, rest: str) -> str:
    """Return the problem of the space on the inner side of a guillemet.

    ``space`` is the character next to the guillemet and ``rest`` the text
    beyond it on the same line, on the side away from the guillemet.
    """
    if space == NBSP:
        if rest and rest[0].isspace():
            return f"{glyph} {side} has more than one space"
        return ""
    if space.isspace():
        return f"{glyph} {side} is {_space_name(space)} (needs one U+00A0)"
    return f"{glyph} {side} has no space (needs one U+00A0)"


def guillemet_problems(text: str) -> tuple:
    """Return ``(examined, [(offset, detail)])`` for the inside of « ».

    Each guillemet side is examined when text follows ``«`` (or precedes ``»``)
    on the same line; a ``«`` ending a line and a ``»`` starting one are not.
    The adjacent character must be exactly one U+00A0.
    """
    examined = 0
    problems = []
    for offset, char in enumerate(text):
        if char == OPENING:
            rest = text[offset + 1 :].split("\n", 1)[0]
            if not rest.strip():
                continue
            examined += 1
            detail = _inner_space("after", OPENING, rest[0], rest[1:])
        elif char == CLOSING:
            head = text[:offset].rsplit("\n", 1)[-1]
            if not head.strip():
                continue
            examined += 1
            detail = _inner_space("before", CLOSING, head[-1], head[-2::-1])
        else:
            continue
        if detail:
            problems.append((offset, detail))
    return examined, problems


def num_unit_problems(text: str) -> tuple:
    """Return ``(examined, [(offset, detail)])`` for the French number+unit rule.

    A pair is a number or numeric placeholder, a run of space characters and a
    unit from ``UNITS``. The run must be exactly one U+00A0.
    """
    examined = 0
    problems = []
    for match in NUM_UNIT.finditer(text):
        examined += 1
        gap = match.group("gap")
        if gap == NBSP:
            continue
        if len(gap) > 1:
            shown = "more than one space character"
        else:
            shown = _space_name(gap)
        problems.append(
            (
                match.start("gap"),
                f"{match.group('num')} {match.group('unit')}: "
                f"{shown} between number and unit (needs one U+00A0)",
            )
        )
    return examined, problems


def french_problems(text: str) -> tuple:
    """Return ``(marks, guillemet_sides, [(offset, detail)])`` for ``fr-nbsp``."""
    marks, mark_problems = nbsp_problems(text)
    sides, side_problems = guillemet_problems(text)
    return marks, sides, sorted(mark_problems + side_problems)


def straight_quote_problems(text: str) -> list:
    """Return ``[(offset, detail)]`` for U+0022 in Russian prose."""
    return [
        (offset, "U+0022 used as a quotation mark (Russian takes « »)")
        for offset, char in enumerate(text)
        if char == STRAIGHT
    ]


def ellipsis_problems(source: str, form: str) -> list:
    """Return the ellipsis problems of one translated form against its source."""
    problems = []
    wanted, found = source.count(ELLIPSIS), form.count(ELLIPSIS)
    if wanted != found:
        problems.append(f"{found} U+2026 where the source has {wanted}")
    if SPACE_BEFORE_ELLIPSIS.search(form):
        problems.append("a space before U+2026")
    if THREE_PERIODS.search(form) and not THREE_PERIODS.search(source):
        problems.append("three periods where the source has none")
    return problems


def han_problems(text: str, endonyms) -> tuple:
    """Return ``(examined, [(offset, detail)])`` for the Korean Han rule."""
    for name in endonyms:
        text = text.replace(name, "\u0000" * len(name))
    found = [(m.start(), m.group()) for m in HAN.finditer(text)]
    return 1, [(o, f"Han character U+{ord(c):04X} {c}") for o, c in found]


def fullwidth_problems(text: str) -> tuple:
    """Return ``(examined, [(offset, detail)])`` for the Chinese catalogue rule."""
    found = [(i, c) for i, c in enumerate(text) if c in ZH_FULLWIDTH]
    return 1, [(i, f"full-width mark U+{ord(c):04X} {c}") for i, c in found]


# -----------------------------------------------------------------------------
# Simplified Chinese guide pages: the half-width space rules (a) to (d).
# -----------------------------------------------------------------------------
ZH_LANGUAGE = "zh_CN"
# The explicit lists of the rules, printed with them (spec: REQ-L10N-DATA-004,
# rules (c) and (d) and the sentences about a number's symbol).
ZH_NUM_UNITS = ("px",)
ZH_TRAILING_SYMBOLS = ("%", "\u00b0")
ZH_OPENING_SYMBOLS = ("\u00b1",)
# One row per rule: (rule name, sub-counts it prints beside its page count).
ZH_RULES = (
    ("zh-space-han-latin", ("edges",)),
    ("zh-space-mark-latin", ("mark edges", "symbol edges")),
    ("zh-num-unit-closed", ("pairs",)),
    ("zh-space-symbol", ("trailing-symbol edges", "opening-symbol edges")),
)
ZH_RULE_NAMES = tuple(name for name, _parts in ZH_RULES)
# The verbatim-quotation exemption (Q-61): a message's placeholders (``%1``..``%99``,
# ``%n``, ``%L1``.., a ``{field}``), its access-key suffix and its access-key ``&``.
ZH_PLACEHOLDER = re.compile(r"%L?(?:n|[1-9][0-9]?)|\{[^{}\n]*\}")
ZH_SUFFIX = re.compile(r" \(&[A-Za-z0-9]\)\Z")
ZH_ACCESS_KEY = re.compile(r"&(.?)", re.DOTALL)
ZH_ANY_RUN = r"[^\ufffc]+?"
ZH_QUOTES = "\u201c\u201d"
ZH_SPACE = " "
OBJECT_MARK = "\ufffc"
# Script=Han, Unicode 16.0.0 (Scripts.txt). Script is not in ``unicodedata``.
HAN_SCRIPT_RANGES = (
    (0x2E80, 0x2E99),
    (0x2E9B, 0x2EF3),
    (0x2F00, 0x2FD5),
    (0x3005, 0x3005),
    (0x3007, 0x3007),
    (0x3021, 0x3029),
    (0x3038, 0x303B),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFA6D),
    (0xFA70, 0xFAD9),
    (0x16FE2, 0x16FE3),
    (0x16FF0, 0x16FF1),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B739),
    (0x2B740, 0x2B81D),
    (0x2B820, 0x2CEA1),
    (0x2CEB0, 0x2EBE0),
    (0x2EBF0, 0x2EE5D),
    (0x2F800, 0x2FA1D),
    (0x30000, 0x3134A),
    (0x31350, 0x323AF),
)
_HAN_STARTS = [first for first, _last in HAN_SCRIPT_RANGES]
SOFTBREAK_MODULE = "pixelart_guide_softbreak"
_LINE_END = re.compile(r"\r\n|\r|\n")
_BLOCK_PREFIX = re.compile(r"^[ \t]*(?:>[ \t]?)*[ \t]*")
_BLOCK_MARKER = re.compile(r"^(?:#{1,6}|[-+*]|[0-9]{1,9}[.)])(?:[ \t]+|$)")
_DEFINITION = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]")
_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_IMAGE = re.compile(r"!\[[^\[\]\n]*\](?:\((?:[^()\n]|\([^()\n]*\))*\)|\[[^\]\n]*\])")
_LINK_TAIL = re.compile(r"\](?:\((?:[^()\n]|\([^()\n]*\))*\)|\[[^\]\n]*\])")
_RUN = re.compile(r"\*+|_+|~+")


class Cell(NamedTuple):
    """One shown character (or break) of a guide paragraph."""

    char: str
    kind: str  # text, space, soft, hidden, opaque or stop
    line: int
    span: int
    soft: Any = None


def zh_han(char: str) -> bool:
    """Return True for a character of Script Han."""
    code = ord(char)
    index = bisect.bisect_right(_HAN_STARTS, code) - 1
    return index >= 0 and code <= HAN_SCRIPT_RANGES[index][1]


def zh_digit(char: str) -> bool:
    """Return True for a decimal digit (category Nd), full-width forms included."""
    return unicodedata.category(char) == "Nd"


def zh_mark(char: str) -> bool:
    """Return True for a full-width punctuation mark of the rules' terms.

    A character of category P whose East Asian Width is F or W, plus U+201C and
    U+201D (width A, named by the reference and by clause 4 of the soft-break
    rule). Width comes from the running interpreter's ``unicodedata``.
    """
    if char in ZH_QUOTES:
        return True
    return unicodedata.category(char).startswith("P") and (
        unicodedata.east_asian_width(char) in "FW"
    )


def _guard(masked: list, start: int, end: int) -> None:
    """Hide ``masked[start:end]`` from the later patterns."""
    for pos in range(start, end):
        if masked[pos] != "\n":
            masked[pos] = "\0"


def _mark_range(kinds: list, start: int, end: int, kind: str) -> None:
    """Set the kind of ``kinds[start:end]``, never touching a line ending."""
    for pos in range(start, end):
        if kinds[pos] != "N":
            kinds[pos] = kind


def _code_spans(text: str, kinds: list, spans: list, masked: list) -> None:
    """Mark the code spans of a paragraph (CommonMark 6.1, one-line subset)."""
    size, pos, count = len(text), 0, 0
    while pos < size:
        if text[pos] != "`":
            pos += 1
            continue
        run_end = pos
        while run_end < size and text[run_end] == "`":
            run_end += 1
        width = run_end - pos
        scan, found = run_end, None
        while scan < size:
            if text[scan] != "`":
                scan += 1
                continue
            stop = scan
            while stop < size and text[stop] == "`":
                stop += 1
            if stop - scan == width:
                found = (scan, stop)
                break
            scan = stop
        if found is None:
            pos = run_end
            continue
        count += 1
        first, last = run_end, found[0]
        inner = text[first:last]
        if inner.strip(" ") and inner.startswith(" ") and inner.endswith(" "):
            first, last = first + 1, last - 1
        _mark_range(kinds, pos, found[1], "M")
        if first >= last:
            _mark_range(kinds, run_end, found[0], "M")
        for at in range(first, last):
            if kinds[at] != "N":
                kinds[at] = "T"
                spans[at] = count
        _guard(masked, pos, found[1])
        pos = found[1]


def _opaque(kinds: list, masked: list, start: int, end: int, kind: str = "O") -> None:
    """Replace ``[start:end]`` by one opaque cell (the rest becomes markup)."""
    _mark_range(kinds, start, end, "M")
    if kinds[start] != "N":
        kinds[start] = kind
    _guard(masked, start, end)


def _inline_kinds(text: str) -> tuple:
    """Return ``(kinds, spans)`` for a paragraph's text.

    Kinds: ``T`` shown text, ``M`` markup (shown as nothing), ``O`` an opaque
    thing (image, entity, address) that is one character the rules never
    examine, ``B`` a hard stop (``<br>``), ``N`` a line ending. ``spans`` holds
    the code span a character stands in (0 outside). The inside of a code span
    and link destinations are text for neighbours only at their edges.
    """
    kinds = ["N" if ch == "\n" else "T" for ch in text]
    spans = [0] * len(text)
    masked = list(text)
    _code_spans(text, kinds, spans, masked)
    for match in _ESCAPE.finditer("".join(masked)):
        _mark_range(kinds, match.start(), match.start() + 1, "M")
        _guard(masked, match.start(), match.end())
    for pattern in (_IMAGE, MD_FILLED[2], MD_FILLED[3], MD_DROPPED[1]):
        for match in pattern.finditer("".join(masked)):
            _opaque(kinds, masked, match.start(), match.end())
    for match in MD_DROPPED[0].finditer("".join(masked)):
        stop = match.group().lower().startswith(("<br", "</br"))
        _mark_range(kinds, match.start(), match.end(), "M")
        if stop:
            kinds[match.start()] = "B"
        _guard(masked, match.start(), match.end())
    _links(kinds, masked)
    _emphasis(kinds, masked)
    return kinds, spans


def _links(kinds: list, masked: list) -> None:
    """Mark the brackets and destinations of inline and reference links."""
    for match in _LINK_TAIL.finditer("".join(masked)):
        flat = "".join(masked)
        opener = flat.rfind("[", 0, match.start())
        if opener < 0 or "]" in flat[opener : match.start()]:
            continue
        for first, last in ((opener, opener + 1), match.span()):
            _mark_range(kinds, first, last, "M")
            _guard(masked, first, last)


def _emphasis(kinds: list, masked: list) -> None:
    """Mark the ``*``, ``_`` and ``~`` runs that pair up as emphasis."""
    flat = "".join(masked)

    def side(pos: int) -> str:
        """Return the character at ``pos`` or a space beyond the text."""
        return flat[pos] if 0 <= pos < len(flat) else " "

    stack: list = []
    for match in _RUN.finditer(flat):
        start, end = match.span()
        char = flat[start]
        before, after = side(start - 1), side(end)
        opens = not after.isspace()
        closes = not before.isspace()
        if char == "_" and before.isalnum() and after.isalnum():
            opens = closes = False
        left = start
        while closes and left < end:
            depth = next(
                (d for d in range(len(stack) - 1, -1, -1) if stack[d][2] == char),
                None,
            )
            if depth is None:
                break
            entry = stack[depth]
            used = min(entry[1] - entry[0], end - left)
            _mark_range(kinds, entry[1] - used, entry[1], "M")
            _mark_range(kinds, left, left + used, "M")
            _guard(masked, entry[1] - used, entry[1])
            _guard(masked, left, left + used)
            left += used
            entry[1] -= used
            del stack[depth + (1 if entry[1] > entry[0] else 0) :]
        if opens and left < end:
            stack.append([left, end, char])


def _zh_lines(text: str, by_line: dict) -> list:
    """Return the paragraphs of a page as ``[(line number, shown source)]``.

    Two lines share a paragraph only where the soft-break module reports a soft
    line break between them. Container prefixes and the first line's block marker
    are not text.
    """
    rows = _LINE_END.split(text)
    paragraphs = []
    number = 1
    while number <= len(rows):
        paragraph: list = []
        while True:
            raw = rows[number - 1].rstrip(" \t")
            body = _BLOCK_PREFIX.sub("", raw, count=1)
            if not paragraph:
                while _BLOCK_MARKER.match(body):
                    body = _BLOCK_PREFIX.sub("", _BLOCK_MARKER.sub("", body, 1), 1)
            if _DEFINITION.match(raw):
                body = ""
            paragraph.append((number, body))
            more = number in by_line and number < len(rows)
            number += 1
            if not more:
                break
        paragraphs.append(paragraph)
    return paragraphs


def zh_cells(paragraph: list, by_line: dict) -> list:
    """Return the shown cells of one paragraph.

    A soft line break is a ``soft`` cell (shown as one space) where the guide keeps
    it, and a ``hidden`` cell (shown as nothing) where the soft-break rule of
    ``REQ-L10N-UI-014`` removes it. The module decides; this reader only places it.
    """
    text = "\n".join(body for _number, body in paragraph)
    kinds, spans = _inline_kinds(text)
    cells = []
    row = 0
    for pos, char in enumerate(text):
        kind = kinds[pos]
        number = paragraph[row][0]
        if kind == "N":
            soft = by_line.get(number)
            hidden = soft is not None and soft.removed
            cells.append(
                Cell(
                    "" if hidden else ZH_SPACE,
                    "hidden" if hidden else "soft",
                    number,
                    0,
                    soft,
                )
            )
            row += 1
        elif kind == "O":
            cells.append(Cell(OBJECT_MARK, "opaque", number, 0))
        elif kind == "B":
            cells.append(Cell(OBJECT_MARK, "stop", number, 0))
        elif kind == "T":
            shown = "space" if char in "\t\u00a0\u3000 " else "text"
            if shown == "text" and unicodedata.category(char) == "Zs":
                shown = "space"
            cells.append(Cell(char, shown, number, spans[pos]))
    return cells


def _zh_name(cell: Cell) -> str:
    """Name a cell for a finding."""
    if cell.kind in ("opaque", "stop"):
        return "an image, entity or address"
    if cell.char.isascii() and cell.char.isprintable():
        return cell.char
    return f"{cell.char} (U+{ord(cell.char):04X})"


def _zh_space_name(cell: Cell) -> str:
    """Name the one space cell of a gap for a finding."""
    if cell.kind == "soft":
        return "a soft line break the guide shows as a space"
    if cell.kind == "hidden":
        clause = cell.soft.clause.value if cell.soft is not None else "?"
        return f"a soft line break the guide hides ({clause})"
    return f"U+{ord(cell.char):04X}"


def _gap_problem(gap: list) -> str:
    """Return what is wrong with the gap at an edge that takes one U+0020."""
    if not gap:
        return "nothing stands between them"
    if len(gap) > 1:
        names = ", ".join(_zh_space_name(cell) for cell in gap)
        return f"more than one space character ({names})"
    cell = gap[0]
    if cell.kind == "soft" or cell.char == ZH_SPACE:
        return ""
    if cell.kind == "hidden":
        return f"{_zh_space_name(cell)} stands between them and shows nothing"
    return f"{_zh_space_name(cell)} stands between them"


class ZhQuote(NamedTuple):
    """One finished ``zh_CN`` message, compiled to be found in shown text."""

    source: str
    pattern: Any
    probe: str
    weight: int


def _screen_texts(form: str, catalogues) -> tuple:
    """Return ``(texts, wording)``: the forms of a message as the screen shows it.

    Markup is not a character and an access-key ``&`` is not one either
    (``&&`` is a literal ampersand). The appended access-key suffix `` (&X)``
    may stand in the quotation or be left out, so both texts are returned; the
    wording test is made without the suffix, whose letter is not wording.
    """
    text = markup_free(form, catalogues)
    bare = ZH_SUFFIX.sub("", text)
    texts = []
    for each in (text, bare):
        shown = ZH_ACCESS_KEY.sub(r"\1", each)
        if shown and shown not in texts:
            texts.append(shown)
    outside = ZH_PLACEHOLDER.sub("", ZH_ACCESS_KEY.sub(r"\1", bare))
    return texts, any(char.isalpha() for char in outside)


def zh_quote_messages(catalogue, catalogues) -> tuple:
    """Return ``(quotes, finished)`` for the exemption of a verbatim quotation.

    ``finished`` counts the finished messages read; ``quotes`` holds the ones that
    can be quoted: a message whose text outside its placeholders holds no letter
    and no Han character quotes no wording and exempts nothing. Each placeholder
    matches the shortest non-empty run of shown text, never an image or a
    ``<br>``.
    """
    quotes: list = []
    finished = 0
    for message in catalogue.live_messages():
        if message.kind == "unfinished" or not message.forms:
            continue
        if not all(message.forms):
            continue
        finished += 1
        for form in message.forms:
            texts, wording = _screen_texts(form, catalogues)
            if not wording:
                continue
            for text in texts:
                pieces = ZH_PLACEHOLDER.split(text)
                pattern = re.compile(ZH_ANY_RUN.join(re.escape(p) for p in pieces))
                probe = max(pieces, key=len)
                if probe:
                    quotes.append(ZhQuote(message.source, pattern, probe, len(text)))
    return tuple(quotes), finished


def _zh_shown(cells: list) -> tuple:
    """Return the shown text of a paragraph and the cell each character comes from."""
    chars, owners = [], []
    for index, cell in enumerate(cells):
        if cell.kind != "hidden":
            chars.append(cell.char)
            owners.append(index)
    return "".join(chars), owners


def zh_quotations(cells: list, quotes: tuple) -> list:
    """Return ``[(first cell, last cell, source)]`` of the verbatim quotations.

    A verbatim quotation is a run of the shown text equal to the whole finished
    translation of one message (``REQ-L10N-DATA-004``, Q-61). Every such run is
    returned, because an edge inside any of them is exempt. Where runs overlap
    the precedence (more of the message's own text, then the shorter, then the
    earlier) decides only the ORDER: the runs it keeps, which never overlap,
    come first, then the overlapped ones in the same precedence. The first run
    holding an edge is the one listed for it, never whether the edge is exempt.
    """
    shown, owners = _zh_shown(cells)
    if not quotes or not shown:
        return []
    best: dict = {}
    for number, quote in enumerate(quotes):
        if quote.probe not in shown:
            continue
        for start in range(len(shown)):
            hit = quote.pattern.match(shown, start)
            if hit and hit.end() > start:
                key = (number, hit.end())
                best[key] = max(best.get(key, start), start)
    runs = sorted(
        (-quotes[number].weight, end - start, start, end, number)
        for (number, end), start in best.items()
    )
    kept: list = []
    overlapped: list = []
    for _weight, _width, start, end, number in runs:
        if all(end <= first or start >= last for first, last, _n in kept):
            kept.append((start, end, number))
        else:
            overlapped.append((start, end, number))
    return [
        (owners[start], owners[end - 1], quotes[number].source)
        for start, end, number in (*kept, *overlapped)
    ]


class ZhPage:
    """The edges of one paragraph, counted and judged."""

    def __init__(self, latin_ranges: tuple, quotes: tuple = ()) -> None:
        """Keep the Script Latin table and the quotable messages."""
        self.latin = latin_ranges
        self.quotes = quotes
        self.quoted: list = []
        self.runs: list = []
        self.used: set = set()
        self.quote = -1
        self.starts = [first for first, _last in latin_ranges]
        self.counts = {
            "edges": 0,
            "mark edges": 0,
            "symbol edges": 0,
            "pairs": 0,
            "trailing-symbol edges": 0,
            "opening-symbol edges": 0,
        }
        self.found: list = []

    def latin_letter(self, char: str) -> bool:
        """Return True for a letter (category L) of Script Latin."""
        if not unicodedata.category(char).startswith("L"):
            return False
        code = ord(char)
        index = bisect.bisect_right(self.starts, code) - 1
        return index >= 0 and code <= self.latin[index][1]

    def latin_or_digit(self, char: str) -> bool:
        """Return True for a Latin letter or a decimal digit."""
        return self.latin_letter(char) or zh_digit(char)

    def add(self, rule: str, line: int, detail: str) -> None:
        """Record one finding."""
        self.found.append((rule, line, detail))

    def judge(self, rule: str, count: str, left: Cell, right: Cell, gap: list) -> None:
        """Count an edge that takes one U+0020 and record a finding if it fails.

        An edge inside a verbatim quotation is counted but not judged.
        """
        self.counts[count] += 1
        if self.quote >= 0:
            self.used.add(self.quote)
            return
        problem = _gap_problem(gap)
        if not problem:
            return
        hidden = [cell for cell in gap if cell.kind == "hidden"]
        line = hidden[0].line if hidden else left.line
        self.add(
            rule,
            line,
            f"between {_zh_name(left)} and {_zh_name(right)}: {problem} "
            "(needs one U+0020)",
        )

    def inside(self, first: int, last: int) -> int:
        """Return the quotation holding cells ``first``..``last``, or -1."""
        for number, (a, b) in enumerate(self.runs):
            if a <= first and last <= b:
                return number
        return -1

    def edges(self, cells: list) -> None:
        """Count and judge every edge of rules (a), (b) and (d) in a paragraph.

        An edge with both sides inside one verbatim quotation is counted but not
        judged; an edge between a quotation and the page's own text is judged. A
        quotation is reported only when it exempted at least one edge or pair.
        """
        found = zh_quotations(cells, self.quotes)
        self.runs = [(first, last) for first, last, _source in found]
        self.used = set()
        keep = [i for i, c in enumerate(cells) if c.kind in ("text", "opaque", "stop")]

        def text(index: int) -> str:
            """Return the character of a content cell, or "" for a non-text one."""
            cell = cells[keep[index]]
            return cell.char if cell.kind == "text" else ""

        def joined(index: int) -> bool:
            """Return True when content cell ``index`` touches the next one."""
            return keep[index + 1] == keep[index] + 1

        def trailing(index: int) -> bool:
            """Return True for a listed symbol that closes a number."""
            return (
                text(index) in ZH_TRAILING_SYMBOLS
                and index > 0
                and joined(index - 1)
                and zh_digit(text(index - 1) or "x")
            )

        def opening(index: int) -> bool:
            """Return True for a listed symbol that opens a number."""
            return (
                text(index) in ZH_OPENING_SYMBOLS
                and index + 1 < len(keep)
                and joined(index)
                and zh_digit(text(index + 1) or "x")
            )

        for index in range(len(keep) - 1):
            left, right = cells[keep[index]], cells[keep[index + 1]]
            if left.span and left.span == right.span:
                continue
            self.quote = self.inside(keep[index], keep[index + 1])
            gap = cells[keep[index] + 1 : keep[index + 1]]
            one, two = text(index), text(index + 1)
            if not one or not two:
                continue
            if (zh_han(one) and self.latin_or_digit(two)) or (
                self.latin_or_digit(one) and zh_han(two)
            ):
                self.judge("zh-space-han-latin", "edges", left, right, gap)
            elif (zh_mark(one) and self.latin_or_digit(two)) or (
                self.latin_or_digit(one) and zh_mark(two)
            ):
                self.judge("zh-space-mark-latin", "mark edges", left, right, gap)
            elif (trailing(index) and zh_mark(two)) or (
                opening(index + 1) and zh_mark(one)
            ):
                self.judge("zh-space-mark-latin", "symbol edges", left, right, gap)
            elif trailing(index) and zh_han(two):
                self.judge("zh-space-symbol", "trailing-symbol edges", left, right, gap)
            elif zh_han(one) and opening(index + 1):
                self.judge("zh-space-symbol", "opening-symbol edges", left, right, gap)
        self.quote = -1
        self.pairs(cells, keep)
        for number in sorted(self.used, key=lambda i: (found[i][0], i)):
            self.quoted.append((cells[found[number][0]].line, found[number][2]))

    def pairs(self, cells: list, keep: list) -> None:
        """Count and judge the number+unit pairs of rule (c)."""
        size = len(keep)

        def char(index: int) -> str:
            """Return the character of content cell ``index`` ("" when not text)."""
            cell = cells[keep[index]]
            return cell.char if cell.kind == "text" else ""

        def joined(index: int) -> bool:
            """Return True when content cell ``index`` touches the next one."""
            return keep[index + 1] == keep[index] + 1

        index = 0
        while index < size:
            if not (char(index) and zh_digit(char(index))):
                index += 1
                continue
            start = end = index
            while end + 1 < size and joined(end):
                nxt = char(end + 1)
                if nxt and zh_digit(nxt):
                    end += 1
                elif (
                    nxt in (".", ",")
                    and end + 2 < size
                    and joined(end + 1)
                    and zh_digit(char(end + 2) or "x")
                ):
                    end += 2
                else:
                    break
            index = end + 1
            before = char(start - 1) if start > 0 and joined(start - 1) else ""
            if before and (self.latin_or_digit(before) or before in "_%{.,"):
                continue
            unit = end + 1
            word = ""
            stop = unit
            while stop < size and (stop == unit or joined(stop - 1)):
                here = char(stop)
                if not here or not self.latin_or_digit(here):
                    break
                word += here
                stop += 1
            if word not in ZH_NUM_UNITS:
                continue
            members = [
                cells[keep[i]] for i in (*range(start, end + 1), *range(unit, stop))
            ]
            owners = {cell.span for cell in members}
            if len(owners) == 1 and 0 not in owners:
                continue
            self.counts["pairs"] += 1
            quote = self.inside(keep[start], keep[stop - 1])
            if quote >= 0:
                self.used.add(quote)
                continue
            gap = cells[keep[end] + 1 : keep[unit]]
            if not gap:
                continue
            number = "".join(cells[keep[i]].char for i in range(start, end + 1))
            shown = "".join("⏎" if c.kind == "soft" else c.char for c in gap)
            names = ", ".join(_zh_space_name(cell) for cell in gap)
            self.add(
                "zh-num-unit-closed",
                gap[0].line,
                f"pair '{number}{shown}{word}': {names} between number and unit "
                "(written closed, no space of any kind)",
            )


def _softbreak_module(root: str) -> Any:
    """Load ``logic/guide_softbreak.py`` by path, from ``root`` or this product."""
    own = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tried = []
    for base in dict.fromkeys(b for b in (root, own) if b):
        path = os.path.join(base, "pixelart_creator", "logic", "guide_softbreak.py")
        tried.append(path)
        if not os.path.isfile(path):
            continue
        added = base not in sys.path
        if added:
            sys.path.insert(0, base)
        try:
            return _sibling(SOFTBREAK_MODULE, path)
        except (ImportError, RuntimeError) as exc:
            raise TypographyError(f"cannot load {path}: {exc}") from exc
        finally:
            if added:
                sys.path.remove(base)
    raise TypographyError("cannot find logic/guide_softbreak.py: " + ", ".join(tried))


def zh_page_problems(text: str, root: str = "") -> tuple:
    """Return ``(counts, findings, info)`` for one Simplified Chinese guide page.

    ``findings`` is ``[(rule, line, detail)]`` in page order. The shown text is
    read as ``REQ-L10N-UI-014`` reads it: the soft-break module of the product,
    called by module path, says which line endings are shown as a space and which
    as nothing. No message is known here, so no quotation is exempt.
    """
    return zh_page_scan(text, root)[:3]


def zh_page_scan(text: str, root: str = "", quotes: tuple = ()) -> tuple:
    """Return ``(counts, findings, info, quoted)`` for one ``zh_CN`` guide page.

    As ``zh_page_problems``, with the verbatim quotations of ``quotes`` (see
    ``zh_quote_messages``) exempt; ``quoted`` is ``[(line, source)]``.
    """
    module = _softbreak_module(root)
    prose = text
    for pattern in MD_BLOCKS:
        prose = pattern.sub(_vanish, prose)
    by_line = {
        b.line: b for b in module.apply_soft_break_rule(text, ZH_LANGUAGE).breaks
    }
    page = ZhPage(module.GUIDE_LATIN_SCRIPT_RANGES, quotes)
    for paragraph in _zh_lines(prose, by_line):
        page.edges(zh_cells(paragraph, by_line))
    info = {
        "unicodedata": unicodedata.unidata_version,
        "softbreak_tables": module.GUIDE_UCD_TABLES_VERSION,
    }
    found = sorted(page.found, key=lambda item: item[1])
    return page.counts, found, info, page.quoted


def declare_zh_units(tally: "Tally") -> None:
    """Open the four rule units of a guide run, so that a missing tree is seen."""
    for rule, parts in ZH_RULES:
        unit = tally.unit(rule, "guide", ZH_LANGUAGE)
        for part in parts:
            unit["sub"].setdefault(part, 0)


def load_zh_quotes(tally: "Tally", folder: str, catalogues) -> None:
    """Read the ``zh_CN`` catalogue's finished messages for the quotation exemption.

    The catalogue is optional: with none in ``folder`` nothing is exempt, and the
    report names the path it tried and "0 finished message(s) read". The file,
    the finished messages read and the ones that can be quoted are kept for the
    report, so that the exemption is never silent.
    """
    path = ""
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            candidate = os.path.join(folder, name)
            if (
                name.startswith("pixelart_")
                and name.endswith(".ts")
                and catalogues.file_code(candidate) == ZH_LANGUAGE
            ):
                path = candidate
                break
    tried = os.path.join(folder, f"pixelart_{ZH_LANGUAGE}.ts")
    tally.zh_catalogue = {"file": path, "tried": tried, "finished": 0, "quotable": 0}
    if not path:
        return
    quotes, finished = zh_quote_messages(catalogues.load_catalogue(path), catalogues)
    tally.zh_quotes = quotes
    tally.zh_catalogue.update(finished=finished, quotable=len(quotes))


def scan_zh_page(text: str, rel: str, tally: "Tally", root: str = "") -> None:
    """Apply rules (a) to (d) to one ``zh_CN`` guide page."""
    counts, found, info, quoted = zh_page_scan(text, root, tally.zh_quotes)
    tally.zh_info = info
    for line, source in quoted:
        tally.zh_exempted.append({"page": rel, "line": line, "source": source})
    for rule, parts in ZH_RULES:
        unit = tally.unit(rule, "guide", ZH_LANGUAGE)
        unit["files"] += 1
        unit["examined"] += 1
        for part in parts:
            unit["sub"][part] = unit["sub"].get(part, 0) + counts[part]
    for rule, line, detail in found:
        tally.add(tally.unit(rule, "guide", ZH_LANGUAGE), f"{rel}:{line}", detail)


class Tally:
    """Per (rule, surface, language) examined counts and findings."""

    def __init__(self) -> None:
        """Start empty."""
        self.units: dict = {}
        self.excluded: list = []
        self.zh_info: dict = {}
        self.zh_quotes: tuple = ()
        self.zh_catalogue: dict = {}
        self.zh_exempted: list = []

    def unit(self, rule: str, surface: str, language: str) -> dict:
        """Return the record of one unit, creating it as applicable."""
        key = (rule, surface, language)
        if key not in self.units:
            self.units[key] = {"examined": 0, "files": 0, "findings": [], "sub": {}}
        return self.units[key]

    def credit(self, unit: dict, part: str, count: int) -> None:
        """Add examined sites to a unit, remembering which kind they were."""
        unit["examined"] += count
        unit["sub"][part] = unit["sub"].get(part, 0) + count

    def add(self, unit: dict, where: str, detail: str) -> None:
        """Record one finding."""
        unit["findings"].append({"where": where, "detail": detail})


def _read_bytes(path: str) -> str:
    """Read a file in binary and decode it as UTF-8."""
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TypographyError(f"{path}: {exc}") from exc


def _line_of(text: str, offset: int) -> int:
    """Return the 1-based line of an offset."""
    return text.count("\n", 0, offset) + 1


# U+202F written as a numeric character reference (decimal or hexadecimal,
# leading zeros allowed, the semicolon required as in HTML and CommonMark). The
# character itself is found by the callers' own scan. HTML5 has no named
# reference for it (measured on html.entities.html5), so none is listed.
NARROW_NBSP_REFERENCE = re.compile(r"&#(?:[xX]0*202[fF]|0*8239);")


def narrow_nbsp_references(text: str) -> list:
    """Return the offset of every U+202F written as a character reference."""
    return [match.start() for match in NARROW_NBSP_REFERENCE.finditer(text)]


def _clip(text: str, width: int = 60) -> str:
    """Shorten a string for one-line display."""
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 3] + "..."


def catalogue_units(tally: Tally, surface: str, language: str) -> dict:
    """Return the rule units that apply to a catalogue language (0 if none)."""
    lang = primary(language)

    def unit(rule: str, wanted: str):
        """Return the unit when the language is the rule's own."""
        return tally.unit(rule, surface, language) if lang == wanted else 0

    return {
        "ellipsis": tally.unit("ellipsis", surface, language),
        "fr-nbsp": unit("fr-nbsp", "fr"),
        "fr-num-unit": unit("fr-num-unit", "fr"),
        "ru-no-straight-quote": unit("ru-no-straight-quote", "ru"),
        "ko-no-han": unit("ko-no-han", "ko"),
        "zh-fullwidth": unit("zh-fullwidth", "zh"),
    }


def apply_message_rules(
    source: str, forms, where: str, units: dict, tally: Tally, endonyms, catalogues
) -> None:
    """Apply every catalogue rule that has a unit to one finished message."""
    units["ellipsis"]["examined"] += 1
    for form in forms:
        for detail in ellipsis_problems(source, form):
            tally.add(units["ellipsis"], where, detail)
    target = units["fr-nbsp"]
    if target:
        for form in forms:
            marks, sides, problems = french_problems(markup_free(form, catalogues))
            tally.credit(target, "marks", marks)
            tally.credit(target, "guillemet sides", sides)
            for _offset, detail in problems:
                tally.add(target, where, detail)
    target = units["fr-num-unit"]
    if target:
        target["examined"] += 1
        for form in forms:
            pairs, problems = num_unit_problems(markup_free(form, catalogues))
            target["sub"]["pairs"] = target["sub"].get("pairs", 0) + pairs
            for _offset, detail in problems:
                tally.add(target, where, detail)
    target = units["ru-no-straight-quote"]
    if target:
        tally.credit(target, "messages", 1)
        for form in forms:
            for _offset, detail in straight_quote_problems(
                markup_free(form, catalogues)
            ):
                tally.add(target, where, detail)
    for rule, check in (
        ("ko-no-han", lambda t: han_problems(t, endonyms)),
        ("zh-fullwidth", fullwidth_problems),
    ):
        target = units[rule]
        if not target:
            continue
        tally.credit(target, "messages", 1)
        for form in forms:
            for _offset, detail in check(form)[1]:
                tally.add(target, where, detail)


def scan_catalogue(path: str, tally: Tally, endonyms, catalogues) -> str:
    """Apply the catalogue rules to one ``.ts`` file; return its language."""
    catalogue = catalogues.load_catalogue(path)
    language = catalogue.language or catalogues.file_code(path) or ""
    name = os.path.basename(path)
    unit = tally.unit("no-u202f", "catalogue", language)
    unit["files"] += 1
    unit["examined"] += 1
    raw = _read_bytes(path)
    spelled = [i for i, c in enumerate(raw) if c == NARROW_NBSP]
    for offset in sorted(spelled + narrow_nbsp_references(raw)):
        tally.add(unit, f"{name}:{_line_of(raw, offset)}", "U+202F")
    if catalogue.identity:
        return language
    units = catalogue_units(tally, "catalogue", language)
    for message in catalogue.live_messages():
        forms = message.forms
        if message.kind == "unfinished" or not forms or not all(forms):
            continue
        where = f"{name} [{message.context}] {_clip(message.source)}"
        apply_message_rules(
            message.source, forms, where, units, tally, endonyms, catalogues
        )
    return language


def load_worklist(path: str) -> dict:
    """Read a translation worklist (JSON object with an entries list)."""
    try:
        document = json.loads(_read_bytes(path))
    except ValueError as exc:
        raise TypographyError(f"{path}: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("entries"), list):
        raise TypographyError(f"{path}: not a worklist (no entries list)")
    if not isinstance(document.get("language"), str) or not document["language"]:
        raise TypographyError(f"{path}: the worklist names no language")
    return document


def scan_worklist(path: str, tally: Tally, endonyms, catalogues) -> dict:
    """Apply the catalogue rules to a worklist's filled entries."""
    document = load_worklist(path)
    language = document["language"]
    name = os.path.basename(path)
    units = catalogue_units(tally, "worklist", language)
    stray = tally.unit("no-u202f", "worklist", language)
    stray["files"] += 1
    filled = 0
    for number, entry in enumerate(document["entries"], start=1):
        forms = entry.get("translation") if isinstance(entry, dict) else None
        if (
            not isinstance(forms, list)
            or not forms
            or not all(isinstance(f, str) and f for f in forms)
        ):
            continue
        filled += 1
        source = str(entry.get("source") or "")
        where = f"{name} entry {number} [{entry.get('context')}] {_clip(source)}"
        stray["examined"] += 1
        for form in forms:
            if NARROW_NBSP in form:
                tally.add(stray, where, "U+202F")
        apply_message_rules(source, forms, where, units, tally, endonyms, catalogues)
    total = len(document["entries"])
    return {
        "file": path,
        "language": language,
        "entries": total,
        "filled": filled,
        "unfilled": total - filled,
    }


def scan_guide_page(
    path: str, rel: str, language: str, tally: Tally, endonyms, root: str = ""
):
    """Apply the guide rules to one page."""
    lang = primary(language)
    text = _read_bytes(path)
    unit = tally.unit("no-u202f", "guide", language)
    unit["files"] += 1
    unit["examined"] += 1
    spelled = [i for i, c in enumerate(text) if c == NARROW_NBSP]
    for offset in sorted(spelled + narrow_nbsp_references(text)):
        tally.add(unit, f"{rel}:{_line_of(text, offset)}", "U+202F")
    if lang == "fr":
        unit = tally.unit("fr-nbsp", "guide", language)
        unit["files"] += 1
        prose = markdown_prose(text)
        marks, sides, problems = french_problems(prose)
        tally.credit(unit, "marks", marks)
        tally.credit(unit, "guillemet sides", sides)
        for offset, detail in problems:
            tally.add(unit, f"{rel}:{_line_of(prose, offset)}", detail)
        unit = tally.unit("fr-num-unit", "guide", language)
        unit["files"] += 1
        unit["examined"] += 1
        pairs, problems = num_unit_problems(prose)
        unit["sub"]["pairs"] = unit["sub"].get("pairs", 0) + pairs
        for offset, detail in problems:
            tally.add(unit, f"{rel}:{_line_of(prose, offset)}", detail)
    if lang == "ru":
        unit = tally.unit("ru-no-straight-quote", "guide", language)
        unit["files"] += 1
        prose = markdown_prose(text)
        tally.credit(unit, "pages", 1)
        for offset, detail in straight_quote_problems(prose):
            tally.add(unit, f"{rel}:{_line_of(prose, offset)}", detail)
    if lang == "ko":
        unit = tally.unit("ko-no-han", "guide", language)
        unit["files"] += 1
        count, problems = han_problems(text, endonyms)
        unit["examined"] += count
        for offset, detail in problems:
            tally.add(unit, f"{rel}:{_line_of(text, offset)}", detail)
    if language == ZH_LANGUAGE:
        scan_zh_page(text, rel, tally, root)


def _wanted(language: str, keep) -> bool:
    """Return True when the language passes the ``--languages`` filter."""
    return keep is None or language in keep


def run(args) -> dict:
    """Scan the requested surfaces and return the report."""
    root = os.path.abspath(args.root)
    catalogues = _catalogue_reader()
    endonyms = load_endonyms(root)
    keep = set(args.languages.split(",")) if args.languages else None
    tally = Tally()
    surfaces_run = []
    skipped: list[str] = []
    if args.worklist:
        if args.surface or args.catalogues or args.guide_root:
            raise TypographyError(
                "--worklist cannot be combined with --surface, --catalogues "
                "or --guide-root"
            )
        info = scan_worklist(args.worklist, tally, endonyms, catalogues)
        if keep is not None and info["language"] not in keep:
            raise TypographyError(
                f"--languages excludes the worklist's language {info['language']!r}"
            )
        report = _report(tally, ["worklist"], skipped)
        report["worklist"] = info
        return report
    args.surface = args.surface or "both"
    folder = args.catalogues or os.path.join(root, "pixelart_creator", "i18n")
    guide_root = args.guide_root or os.path.join(
        root, "pixelart_creator", "userguide_content", "content"
    )
    if args.surface in ("catalogue", "both"):
        if os.path.isdir(folder):
            surfaces_run.append("catalogue")
            names = sorted(
                n
                for n in os.listdir(folder)
                if n.startswith("pixelart_") and n.endswith(".ts")
            )
            for name in names:
                path = os.path.join(folder, name)
                code = catalogues.file_code(path) or ""
                if _wanted(code, keep):
                    scan_catalogue(path, tally, endonyms, catalogues)
        elif args.catalogues:
            raise TypographyError(f"{folder}: not a folder")
        else:
            skipped.append(f"catalogue surface: {folder} does not exist")
    if args.surface in ("guide", "both"):
        if os.path.isdir(guide_root):
            surfaces_run.append("guide")
            if _wanted(ZH_LANGUAGE, keep):
                declare_zh_units(tally)
                load_zh_quotes(tally, folder, catalogues)
            for language in sorted(os.listdir(guide_root)):
                tree = os.path.join(guide_root, language)
                if not os.path.isdir(tree) or not _wanted(language, keep):
                    continue
                if primary(language) == "zh":
                    tally.excluded.append(
                        f"zh-fullwidth [guide] {language}: not scanned by design"
                    )
                scanned = False
                for folder_, _dirs, files in sorted(os.walk(tree)):
                    for name in sorted(f for f in files if f.endswith(".md")):
                        path = os.path.join(folder_, name)
                        rel = os.path.relpath(path, guide_root).replace(os.sep, "/")
                        scan_guide_page(path, rel, language, tally, endonyms, root)
                        scanned = True
                if not scanned:
                    tally.unit("no-u202f", "guide", language)
        elif args.guide_root:
            raise TypographyError(f"{guide_root}: not a folder")
        else:
            skipped.append(f"guide surface: {guide_root} does not exist")
    return _report(tally, surfaces_run, skipped)


def _report(tally: Tally, surfaces_run: list, skipped: list) -> dict:
    """Build the report and the exit code from the tally."""
    rows = []
    blind = 0
    for (rule, surface, language), unit in sorted(tally.units.items()):
        empty = unit["examined"] == 0
        blind += 1 if empty else 0
        rows.append(
            {
                "rule": rule,
                "surface": surface,
                "language": language,
                "examined": unit["examined"],
                "sub_counts": dict(sorted(unit["sub"].items())),
                "files": unit["files"],
                "nothing_examined": empty,
                "findings": unit["findings"],
            }
        )
    total = sum(len(r["findings"]) for r in rows)
    examined = sum(r["examined"] for r in rows)
    code = EXIT_FINDINGS if total or blind or examined == 0 else EXIT_OK
    report = {
        "surfaces": surfaces_run,
        "skipped": skipped,
        "excluded": tally.excluded,
        "rules": rows,
        "examined_total": examined,
        "findings_total": total,
        "rules_examining_nothing": blind,
        "exit": code,
    }
    if any(r["rule"] == "fr-num-unit" for r in rows):
        report["fr_num_unit_units"] = [label for label, _pattern in UNITS]
    if any(r["rule"] in ZH_RULE_NAMES for r in rows):
        report["zh_num_unit_units"] = list(ZH_NUM_UNITS)
        report["zh_trailing_symbols"] = list(ZH_TRAILING_SYMBOLS)
        report["zh_opening_symbols"] = list(ZH_OPENING_SYMBOLS)
        for row in rows:
            if row["rule"] in ZH_RULE_NAMES:
                row["quotations_exempted"] = len(tally.zh_exempted)
        report["zh_quotations"] = {
            "catalogue": os.path.basename(tally.zh_catalogue.get("file", "")),
            "tried": tally.zh_catalogue.get("tried", ""),
            "finished_messages": tally.zh_catalogue.get("finished", 0),
            "quotable_messages": tally.zh_catalogue.get("quotable", 0),
            "exempted": len(tally.zh_exempted),
            "items": tally.zh_exempted,
        }
        if tally.zh_info:
            report["zh_unicode"] = tally.zh_info
    return report


def print_zh_lists(report: dict, out) -> None:
    """Print the explicit lists and the Unicode versions of the zh_CN rules."""
    units = ", ".join(report["zh_num_unit_units"])
    print(f"zh-num-unit-closed units ({len(ZH_NUM_UNITS)}): {units}", file=out)
    both = "zh-space-symbol, zh-space-mark-latin"
    trailing = ", ".join(report["zh_trailing_symbols"])
    opening = ", ".join(report["zh_opening_symbols"])
    print(f"{both} trailing symbols ({len(ZH_TRAILING_SYMBOLS)}): {trailing}", file=out)
    print(f"{both} opening symbols ({len(ZH_OPENING_SYMBOLS)}): {opening}", file=out)
    info = report.get("zh_unicode")
    if info:
        print(
            f"zh unicode data: unicodedata {info['unicodedata']}, soft-break "
            f"tables {info['softbreak_tables']}",
            file=out,
        )
    quoted = report.get("zh_quotations")
    if quoted:
        where = quoted["catalogue"] or "no zh_CN catalogue read"
        if not quoted["catalogue"]:
            where = f"{where} (tried {quoted['tried']})"
        print(
            f"zh quotations exempted from all four rules ({quoted['exempted']}), "
            f"{where}: {quoted['finished_messages']} finished message(s) read, "
            f"{quoted['quotable_messages']} quotable",
            file=out,
        )
        for item in quoted["items"]:
            source = " ".join(item["source"].split())
            print(f"  {item['page']}:{item['line']}: {source}", file=out)


def print_report(report: dict, out) -> None:
    """Print a report as text."""
    for note in report["skipped"]:
        print(f"skipped: {note}", file=out)
    for note in report["excluded"]:
        print(f"excluded: {note}", file=out)
    if any(row["rule"] == "fr-num-unit" for row in report["rules"]):
        labels = ", ".join(label for label, _pattern in UNITS)
        print(f"fr-num-unit units ({len(UNITS)}): {labels}", file=out)
    if any(row["rule"] in ZH_RULE_NAMES for row in report["rules"]):
        print_zh_lists(report, out)
    for row in report["rules"]:
        unit = "item(s)"
        if row["rule"] == "no-u202f" and row["surface"] != "worklist":
            unit = "file(s)"
        if row["rule"] == "fr-num-unit":
            unit = "page(s)" if row["surface"] == "guide" else "entr(ies)"
        if row["rule"] in ZH_RULE_NAMES:
            unit = "page(s)"
        parts = ", ".join(f"{k} {v}" for k, v in row["sub_counts"].items())
        split = f" ({parts})" if row["rule"] == "fr-nbsp" and parts else ""
        if row["rule"] in ("fr-num-unit", *ZH_RULE_NAMES) and parts:
            split = f" ({parts})"
        print(
            f"{row['rule']} [{row['surface']}] {row['language']}: examined "
            f"{row['examined']} {unit}{split}, {len(row['findings'])} finding(s)",
            file=out,
        )
        if row["nothing_examined"]:
            print("  nothing examined", file=out)
        for finding in row["findings"][:SHOWN]:
            print(f"  {finding['where']}: {finding['detail']}", file=out)
        extra = len(row["findings"]) - SHOWN
        if extra > 0:
            print(f"  ... and {extra} more", file=out)
    info = report.get("worklist")
    if info:
        print(
            f"worklist {os.path.basename(info['file'])} [{info['language']}]: "
            f"{info['entries']} entr(ies), {info['filled']} filled and "
            f"examined, {info['unfilled']} unfilled",
            file=out,
        )
    print(
        f"examined {report['examined_total']} in {len(report['rules'])} "
        f"rule unit(s), {report['findings_total']} finding(s)",
        file=out,
    )
    if report["examined_total"] == 0 or not report["rules"]:
        print("nothing examined", file=out)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    here = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument("--root", default=os.path.dirname(here))
    parser.add_argument("--catalogues", help="folder of pixelart_<code>.ts files")
    parser.add_argument("--guide-root", help="folder of per-language page trees")
    parser.add_argument("--surface", choices=("catalogue", "guide", "both"))
    parser.add_argument("--worklist", help="a translation worklist (JSON) to check")
    parser.add_argument("--languages", help="comma-separated codes to keep")
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv=None) -> int:
    """Run the check and return the process exit code."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = run(args)
    except (TypographyError, _catalogue_error()) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print_report(report, sys.stdout)
    return report["exit"]


def _catalogue_error():
    """Return the sibling reader's error class (or one nothing raises)."""
    module = sys.modules.get("check_catalogues")
    return getattr(module, "CatalogueError", TypographyError)


if __name__ == "__main__":
    sys.exit(main())
