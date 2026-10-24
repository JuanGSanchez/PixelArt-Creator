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
#     no-u202f   No U+202F (narrow no-break space) in any scanned file. Both
#                 surfaces, every language.
#     ellipsis    Catalogue only: a finished translation holds as many U+2026
#                 as its source message, no space before one, and no run of
#                 three periods unless its source has one.
#     ko-no-han   Korean: no Han character outside the eight language
#                 self-names. Both surfaces.
#     zh-fullwidth  Simplified Chinese catalogue only: no U+FF1A, U+FF01,
#                 U+FF1F, U+FF08, U+FF09 in a finished translation. The
#                 Chinese guide pages take those marks full-width and are
#                 never scanned for them (reported as excluded).
#   Registers (address forms) and the judgments that stay with a reviewer (the
#   French quotation style as a whole, spacing inside Russian « ») are not
#   decided here.
# FLAVOUR: standalone
# LOCATION: scripts/check_l10n_typography.py
# INVOKED BY: the localisation role, as an acceptance gate on every catalogue
#   or guide-topic translation batch; and by CI over the committed catalogues
#   and guide trees.
# RUNTIME: Python 3.12+ (CPython; stdlib only). The catalogue reader is the one
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
import importlib.util
import json
import os
import re
import sys

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


class Tally:
    """Per (rule, surface, language) examined counts and findings."""

    def __init__(self) -> None:
        """Start empty."""
        self.units: dict = {}
        self.excluded: list = []

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
    for offset in [i for i, c in enumerate(raw) if c == NARROW_NBSP]:
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


def scan_guide_page(path: str, rel: str, language: str, tally: Tally, endonyms):
    """Apply the guide rules to one page."""
    lang = primary(language)
    text = _read_bytes(path)
    unit = tally.unit("no-u202f", "guide", language)
    unit["files"] += 1
    unit["examined"] += 1
    for offset in [i for i, c in enumerate(text) if c == NARROW_NBSP]:
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
                        scan_guide_page(path, rel, language, tally, endonyms)
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
    return report


def print_report(report: dict, out) -> None:
    """Print a report as text."""
    for note in report["skipped"]:
        print(f"skipped: {note}", file=out)
    for note in report["excluded"]:
        print(f"excluded: {note}", file=out)
    if any(row["rule"] == "fr-num-unit" for row in report["rules"]):
        labels = ", ".join(label for label, _pattern in UNITS)
        print(f"fr-num-unit units ({len(UNITS)}): {labels}", file=out)
    for row in report["rules"]:
        unit = "item(s)"
        if row["rule"] == "no-u202f" and row["surface"] != "worklist":
            unit = "file(s)"
        if row["rule"] == "fr-num-unit":
            unit = "page(s)" if row["surface"] == "guide" else "entr(ies)"
        parts = ", ".join(f"{k} {v}" for k, v in row["sub_counts"].items())
        split = f" ({parts})" if row["rule"] == "fr-nbsp" and parts else ""
        if row["rule"] == "fr-num-unit" and parts:
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
