"""Nifen Art build: source lint, deterministic TTF build, byte-identity check.

Build-time only; requires fontTools (4.63.0 is the version the committed
fonts were built and proved with). Writes NifenArt-Regular.ttf and
NifenArt-Bold.ttf from the text-grid sources. Run from the repository root:

    python scripts/font/build_nifen_art.py --lint
    python scripts/font/build_nifen_art.py --build
    python scripts/font/build_nifen_art.py --check
    python scripts/font/build_nifen_art.py --verify-freeze

Defaults are repository-relative: sources in fonts-src/nifen-art, built fonts
in pixelart_creator/fonts (the --check comparison target as well).

--face nifen-art-cjk does the same for the second face: three families (Japanese
Han forms, Simplified Han forms, Hangul), Regular and Bold, six fonts from the
sources in fonts-src/nifen-art-cjk. Its Bold is its Regular, pixel for pixel. The
face lints a declared R05 exemption list, holds its character map to Han and
Hangul, and requires every glyph to be drawn or a recipe of drawn glyphs. A face
with no glyph record yet lints clean (the glyph rules examine nothing) and has no
font to build or check. The lint of either face runs the donor gate: one donor
(the hiragana), none for the CJK face.

--verify-freeze, and --check, compare the existing face with its freeze manifest
(fonts-src/nifen-art-cjk/existing-face.sha256), which is never regenerated.

Every command exits non-zero on any violation, on any mismatch, or when it
examined nothing.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_SRC = os.path.join(REPO, "fonts-src", "nifen-art")
DEFAULT_OUT = os.path.join(REPO, "pixelart_creator", "fonts")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from nifen_src import (  # noqa: E402
    CJK_SETS,
    CjkFont,
    Font,
    SourceError,
    bbox,
    cjk_key,
    cjk_key_text,
    components,
    contours,
    counters,
    fill_from_contours,
    lost_counters,
    make_console_safe,
    parse_cjk_sources,
    parse_cp,
    parse_sources,
)

WEIGHTS = ("regular", "bold")
FILE_NAMES = {"regular": "NifenArt-Regular.ttf", "bold": "NifenArt-Bold.ttf"}

# The Reserved Font Name declaration. It ends the typeface's own copyright line, in the
# licence file and in name ID 0 of every built font, and never sits on the line of a
# work this font includes. The wording is fixed here, apart from the metrics, so a
# metrics edit cannot make the checks agree with a changed clause.
RFN_CLAUSE = 'with Reserved Font Name "Nifen Art".'
RFN_PHRASE = "Reserved Font Name"

WORD_START = "(?<![A-Za-z0-9_])"
WORD_END = "(?![A-Za-z0-9_])"

# Patterns for the public-safe scan. Written in pieces so this file does not
# match its own rules.
UNSAFE = [
    ("authoring-tool name", re.compile("cl" + "aude", re.I)),
    ("vendor name", re.compile("anthr" + "opic", re.I)),
    ("authorship token", re.compile(WORD_START + "A" + "I" + WORD_END)),
    ("orchestration id", re.compile(WORD_START + "AG" + "T-?[0-9]", re.I)),
    ("workflow id", re.compile(WORD_START + "O" + "F[0-9]")),
    ("slug", re.compile("pixelart-style-" + "refresh")),
    ("requirement id", re.compile(r"\b(REC|RR|AR)-\d")),
    ("question id", re.compile(r"\bQ-\d")),
    ("drive path", re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")),
    ("design folder", re.compile("design-" + "docs")),
    ("profile name", re.compile("Us" + "uario")),
    ("home path", re.compile("/Us" + "ers/|/ho" + "me/")),
    ("orchestration term", re.compile(r"\bag" + r"ents?\b", re.I)),
    ("workflow term", re.compile(WORD_START + "j" + "ob" + WORD_END, re.I)),
]


# --------------------------------------------------------------------------
# The two faces and the donor record
# --------------------------------------------------------------------------

FACE_EXISTING = "nifen-art"
FACE_CJK = "nifen-art-cjk"
DEFAULT_CJK_SRC = os.path.join(REPO, "fonts-src", "nifen-art-cjk")
DEFAULT_NOTICE = os.path.join(REPO, "NOTICE")

# The donor record that the donor gate holds the sources to. It is fixed here, apart
# from the metrics, so that an edit of the metrics cannot make the gate agree with a
# changed donor: one donor, one version, and the code points it supplied.
DONOR_NAME = "Ark Pixel Font"
DONOR_VERSION = "2026.09.25"
DONOR_LICENCE = "SIL Open Font License, Version 1.1"
DONOR_HOLDER = "TakWolf"
DONOR_FILES = ("hiragana-ark-pixel.txt",)
DONOR_DERIVED_FILES = ("hiragana-ark-pixel.txt", "bold-overlays-ark-pixel.txt")
DONOR_KEYS = (
    "donor_files",
    "donor_derived_files",
    "donor_name",
    "donor_version",
    "donor_licence",
)
DONOR_SPANS = ((0x3041, 0x3096), (0x309D, 0x309F))
OWN_HOLDERS = ("JuanGSanchez", "Juan Garcia Sanchez")
# Fonts that the project looked at and did not use. Naming one in a source, a licence
# file, a change log or a name table is read as crediting a second donor.
OTHER_FONTS = (
    "Galmuri",
    "x12y12pxMaruMinyaHangul",
    "Fusion Pixel",
    "Misaki",
    "Unifont",
)

# A copyright statement (the holder is the text after the year, up to a bracket or a
# semicolon), and a sentence that credits the source of a drawing. A negated sentence
# about "another font" is a statement of originality, not a credit.
HOLDER_RE = re.compile(
    r"copyright\s*(?:\(c\)|\u00a9)?\s*(?:19|20)\d\d(?:\s*[-,]\s*(?:19|20)\d\d)*"
    r"\s*,?\s*([^(;]*)",
    re.I,
)
HOLDER_END_RE = re.compile(r"\s*(?:[(;]|\.(?:\s|$))")
DONOR_RE = re.compile(r"ark[\s_-]*pixel|tak[\s_-]*wolf", re.I)
CREDIT_RE = re.compile(
    r"\b(?:adapted|derived|taken|copied|traced|borrowed|redrawn)"
    r"(?:\s+\w+){0,3}?\s+from\b",
    re.I,
)
NEGATION_RE = re.compile(r"\b(?:no|not|never|nothing|none|neither|nor|without)\b", re.I)
GENERIC_SOURCE_RE = re.compile(
    r"\bfrom\s+(?:another|any|other|a|an)\s+(?:\w+\s+){0,2}fonts?\b", re.I
)
STRUCTURED_CREDIT_RE = re.compile(
    r"code points\s+\w+\s+from\s+(.+?),\s*version\b", re.I
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MANIFEST_LINE_RE = re.compile(r"^[0-9a-f]{64}\s+\S+\s*$", re.M)


@dataclass
class Gate:
    """Where the donor gate reads what the existing face's sources do not hold: the CJK
    sources, the product's notice file and the built fonts (when they are to be read).
    """

    cjk_dir: str
    notice: str
    out_dir: str
    ttfs: bool = True


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def mint(m, key):
    return int(m[key])


def epoch_1904(iso: str) -> int:
    dt = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )
    base = datetime.datetime(1904, 1, 1, tzinfo=datetime.timezone.utc)
    return int((dt - base).total_seconds())


def rng(text):
    a, b = text.split("..")
    return int(a), int(b)


# The capitals whose body must measure exactly cap_px rows (R02): Latin, Greek
# and Cyrillic uppercase letters, found by their Unicode names. Nothing else is
# in the set: not the digits, not the symbols, not the small capitals.
CAPITAL_NAME_PREFIXES = (
    "LATIN CAPITAL LETTER ",
    "GREEK CAPITAL LETTER ",
    "CYRILLIC CAPITAL LETTER ",
)


def is_capital_letter(cp):
    """True for a Latin, Greek or Cyrillic uppercase letter."""
    ch = chr(cp)
    return unicodedata.category(ch) == "Lu" and unicodedata.name(ch, "").startswith(
        CAPITAL_NAME_PREFIXES
    )


def has_canonical_mark(cp):
    """True when the codepoint canonically decomposes into a letter and marks."""
    dec = unicodedata.decomposition(chr(cp))
    return bool(dec) and not dec.startswith("<")


# --------------------------------------------------------------------------
# Lint
# --------------------------------------------------------------------------


class Report:
    def __init__(self):
        self.rules = []  # (code, title, examined, [violations], [info])
        # Rules that may examine nothing without failing: the glyph rules of a face
        # that has no glyph record yet.
        self.zero_ok = set()

    def add(self, code, title, examined, violations, info=None):
        self.rules.append((code, title, examined, list(violations), list(info or [])))

    def print(self):
        total_v = 0
        for code, title, examined, viol, info in self.rules:
            print(
                "%-4s %-52s examined %5d  violations %3d"
                % (code, title, examined, len(viol))
            )
            for v in viol[:25]:
                print("       VIOLATION", v)
            if len(viol) > 25:
                print("       ... %d more" % (len(viol) - 25))
            for i in info:
                print("       info", i)
            total_v += len(viol)
        return total_v

    def failed(self):
        if any(v for _c, _t, _e, v, _i in self.rules):
            return True
        if any(e == 0 and c not in self.zero_ok for c, _t, e, _v, _i in self.rules):
            return True
        return False


def is_cell(font: Font, cp):
    """True for full-width cell glyphs, following aliases and recipe bases."""
    s = font.srcs
    if cp in s.glyphs:
        return s.glyphs[cp].has_flag("cell")
    if cp in font.alias_by_cp:
        return is_cell(font, font.alias_by_cp[cp].source_cp)
    if cp in font.recipe_by_cp:
        r = font.recipe_by_cp[cp]
        return is_cell(font, parse_cp(r.args[0], "%s:%d" % (r.path, r.line)))
    return False


def has_flag(font: Font, cp, name):
    """True when the drawing a codepoint resolves to (via aliases) carries a flag."""
    s = font.srcs
    if cp in s.glyphs:
        return s.glyphs[cp].has_flag(name)
    if cp in font.alias_by_cp:
        return has_flag(font, font.alias_by_cp[cp].source_cp, name)
    return False


def allowance(font: Font, cp, seen=()):
    """Declared isolated-pixel allowance for a codepoint (drawn dots plus parts)."""
    s = font.srcs
    if cp in s.glyphs:
        return int(s.glyphs[cp].attrs.get("dots", "0"))
    if cp in font.alias_by_cp:
        return allowance(font, font.alias_by_cp[cp].source_cp)
    if cp in font.recipe_by_cp:
        r = font.recipe_by_cp[cp]
        where = "%s:%d" % (r.path, r.line)
        if r.op == "mark":
            mk = s.marks[r.args[1]]
            return allowance(font, parse_cp(r.args[0], where)) + int(
                mk.attrs.get("dots", "0")
            )
        if r.op in ("overlay", "cat"):
            return allowance(font, parse_cp(r.args[0], where)) + allowance(
                font, parse_cp(r.args[1], where)
            )
        return allowance(font, parse_cp(r.args[0], where))
    return 0


def lint(srcs, font: Font, script_files, src_dir, fonts_dir=None, gate=None):
    rep = Report()
    if fonts_dir is None:
        fonts_dir = DEFAULT_OUT
    m = srcs.metrics
    U = mint(m, "units_per_px")
    cps = font.codepoints()
    notdef = srcs.glyphs.get(".notdef")
    em_bot, em_top = mint(m, "em_bottom_px"), mint(m, "em_top_px")
    cell_adv = mint(m, "cell_adv_px")
    kx_r = rng(m["cell_ink_x_regular"])
    kx_b = rng(m["cell_ink_x_bold"])
    ky = rng(m["cell_ink_rows"])
    cap_px = mint(m, "cap_px")
    allowed_tops = {mint(m, "x_px"), cap_px, mint(m, "asc_px")}

    # R01 bounds ---------------------------------------------------------------
    v, n = [], 0
    for cp in cps:
        for w in WEIGHTS:
            b = font.bmp(cp, w)
            n += 1
            bb = bbox(b.px)
            if bb is None:
                continue
            full = is_cell(font, cp)
            if bb[1] < em_bot or bb[3] > em_top - 1:
                v.append(
                    "U+%04X %s ink rows %d..%d outside em box %d..%d"
                    % (cp, w, bb[1], bb[3], em_bot, em_top - 1)
                )
            if bb[0] < 0 or bb[2] > b.adv - 1:
                v.append(
                    "U+%04X %s ink columns %d..%d outside advance %d"
                    % (cp, w, bb[0], bb[2], b.adv)
                )
            if full:
                lo, hi = kx_r if w == "regular" else kx_b
                if bb[0] < lo or bb[2] > hi:
                    v.append(
                        "U+%04X %s kana ink columns %d..%d outside cell columns %d..%d"
                        % (cp, w, bb[0], bb[2], lo, hi)
                    )
                if bb[1] < ky[0] or bb[3] > ky[1]:
                    v.append(
                        "U+%04X %s kana ink rows %d..%d outside cell rows %d..%d"
                        % (cp, w, bb[1], bb[3], ky[0], ky[1])
                    )
    rep.add("R01", "glyph within the em box and the advance", n, v)

    # R02 baseline and heights --------------------------------------------------
    v, n = [], 0
    for cp, rec in sorted((k, r) for k, r in srcs.glyphs.items() if isinstance(k, int)):
        ext = rec.attrs.get("ext")
        if ext is None:
            v.append("U+%04X has no ext= declaration" % cp)
            continue
        n += 1
        if ext == "free":
            # A drawn capital may declare a free extent only when it is an
            # accented form drawn with its mark (the diaeresis on I). Its body
            # is still a cap-height capital: the row between the capital and
            # the accent zone is empty, the cap-height row carries ink, and the
            # body stands on the baseline or a descender.
            if is_capital_letter(cp):
                px = rec.pixels()
                bb = bbox(px)
                if not has_canonical_mark(cp):
                    v.append(
                        "U+%04X capital declares ext=free but is not an accented "
                        "form: its body must measure %d rows" % (cp, cap_px)
                    )
                elif bb is None or bb[1] not in (0, -1, -2):
                    v.append("U+%04X accented capital is off the baseline" % cp)
                elif any(y == cap_px for _, y in px) or not any(
                    y == cap_px - 1 for _, y in px
                ):
                    v.append(
                        "U+%04X accented capital body is not %d rows (row %d must "
                        "be empty, row %d inked)" % (cp, cap_px, cap_px, cap_px - 1)
                    )
            continue
        lo, hi = rng(ext)
        px = rec.pixels()
        bb = bbox(px)
        if bb is None or bb[1] != lo or bb[3] + 1 != hi:
            v.append(
                "U+%04X grid extent %s but ext=%s"
                % (cp, None if bb is None else "%d..%d" % (bb[1], bb[3] + 1), ext)
            )
        if hi not in allowed_tops:
            v.append("U+%04X ext top %d is not x/cap/ascender height" % (cp, hi))
        if is_capital_letter(cp) and hi != cap_px:
            v.append(
                "U+%04X capital ext top %d: a capital measures exactly %d rows "
                "above the baseline" % (cp, hi, cap_px)
            )
        if lo not in (0, -1, -2):
            v.append("U+%04X ext bottom %d is not baseline or descender" % (cp, lo))
    if notdef is not None:
        n += 1
    rep.add("R02", "baseline row and declared heights (drawn glyphs)", n, v)

    # R03 advance policy -----------------------------------------------------------
    v, n = [], 0
    bold_shift = mint(m, "bold_shift_px")
    narrow_cps = {parse_cp(t) for t in m.get("narrow_space_cps", "").split()}
    wide_cps = {parse_cp(t) for t in m.get("wide_space_cps", "").split()}
    for cp in cps:
        rb, bb_ = font.bmp(cp, "regular"), font.bmp(cp, "bold")
        n += 1
        full = is_cell(font, cp)
        tab = has_flag(font, cp, "tab")
        if not rb.px:  # space and its aliases carry no ink
            if (
                cp in wide_cps
            ):  # the ideographic space: one full-width cell in both weights
                want_blank = mint(m, "wide_space_adv_px")
                if rb.adv != want_blank:
                    v.append("U+%04X blank advance %d != %d" % (cp, rb.adv, want_blank))
                if bb_.adv != want_blank:
                    v.append(
                        "U+%04X blank Bold advance %d != %d (a full-width cell keeps "
                        "its width)" % (cp, bb_.adv, want_blank)
                    )
                if not full:
                    v.append("U+%04X is declared wide but is not a cell glyph" % cp)
                continue
            want_blank = (
                mint(m, "narrow_space_adv_px")
                if cp in narrow_cps
                else mint(m, "space_adv_px")
            )
            if rb.adv != want_blank:
                v.append("U+%04X blank advance %d != %d" % (cp, rb.adv, want_blank))
            if bb_.adv != rb.adv + bold_shift:
                v.append(
                    "U+%04X blank Bold advance %d != Regular + %d"
                    % (cp, bb_.adv, bold_shift)
                )
            continue
        if full:
            if rb.adv != cell_adv or bb_.adv != cell_adv:
                v.append(
                    "U+%04X full-width advance %d/%d != %d"
                    % (cp, rb.adv, bb_.adv, cell_adv)
                )
            continue
        ink = bbox(rb.px)
        if not tab and ink[0] != 0:
            v.append("U+%04X Regular left sidebearing %d != 0" % (cp, ink[0]))
        rsb = rb.adv - 1 - ink[2]
        if not tab and cp in srcs.glyphs and rb.adv != ink[2] + 2:
            v.append(
                "U+%04X Regular advance %d != rightmost column %d + 2"
                % (cp, rb.adv, ink[2])
            )
        if rsb < 1:
            v.append("U+%04X Regular right sidebearing %d < 1" % (cp, rsb))
        want = rb.adv + bold_shift
        if bb_.adv != want:
            v.append(
                "U+%04X Bold advance %d != Regular %d + %d"
                % (cp, bb_.adv, rb.adv, want - rb.adv)
            )
        brsb = bb_.adv - 1 - bbox(bb_.px)[2]
        if brsb < 1:
            v.append("U+%04X Bold right sidebearing %d < 1" % (cp, brsb))
    rep.add("R03", "advance consistent with the proportional / cell policy", n, v)

    # R04 orphan pixels --------------------------------------------------------------
    v, n, declared = [], 0, 0
    for cp in cps:
        a = allowance(font, cp)
        declared += a
        for w in WEIGHTS:
            n += 1
            px = font.bmp(cp, w).px
            lone = [c for c in components(px) if len(c) == 1]
            if len(lone) > a:
                v.append(
                    "U+%04X %s has %d single-pixel components, %d declared"
                    % (cp, w, len(lone), a)
                )
    rep.add(
        "R04",
        "orphan pixels (single-pixel components vs dots=)",
        n,
        v,
        ["deliberate isolated pixels declared across the set: %d" % declared],
    )

    # R05 stems ------------------------------------------------------------------------
    v, n = [], 0
    for cp in cps:
        solid = cp in srcs.glyphs and srcs.glyphs[cp].has_flag("solid")
        for w in WEIGHTS:
            n += 1
            px = font.bmp(cp, w).px
            if solid:
                continue
            if w == "regular":
                for x, y in sorted(px):
                    if (x + 1, y) in px and (x, y + 1) in px and (x + 1, y + 1) in px:
                        v.append(
                            "U+%04X Regular has a 2x2 block at (%d,%d): stem wider "
                            "than 1 px" % (cp, x, y)
                        )
                        break
            else:
                for x, y in sorted(px):
                    if (x - 1, y) not in px and (x + 1, y) not in px:
                        v.append(
                            "U+%04X Bold has a 1 px wide run at (%d,%d)" % (cp, x, y)
                        )
                        break
    rep.add("R05", "stem width: Regular 1 px (no 2x2), Bold >= 2 px", n, v)

    # R06 recipes and aliases resolvable, parts not merged -----------------------------
    v, n = [], 0
    for a in srcs.aliases:
        n += 1
        for w in WEIGHTS:
            try:
                font.bmp(a.source_cp, w)
            except SourceError as exc:
                v.append("alias U+%04X -> U+%04X: %s" % (a.target_cp, a.source_cp, exc))
    trim_stats = {"regular": [], "bold": []}
    cut_used = []
    for r in srcs.recipes:
        n += 1
        if r.target_cp in srcs.glyphs:
            # an override: the drawn grid wins and R07 lists it; the composition
            # is not what ships
            continue
        for w in WEIGHTS:
            try:
                res = font.bmp(r.target_cp, w)
            except SourceError as exc:
                v.append("recipe U+%04X: %s" % (r.target_cp, exc))
                continue
            if w == "bold" and r.target_cp in srcs.bold_glyphs:
                # a drawn Bold grid replaces the composition; R08 checks what it
                # restores
                continue
            parts = font.recipe_components(r, w)
            if r.op == "overlay" and "trim" in r.opts and parts:
                full = font.bmp(parse_cp(r.args[0], "%s:%d" % (r.path, r.line)), w).px
                removed = len(full) - len(parts[0])
                trim_stats[w].append(removed)
                delta = abs(len(components(parts[0])) - len(components(full)))
                allowed = int(r.opts.get("cut", "0"))
                if delta > allowed:
                    v.append(
                        "U+%04X %s: trim changes the part count of the base (%d -> "
                        "%d, cut=%d declared): draw the glyph instead"
                        % (
                            r.target_cp,
                            w,
                            len(components(full)),
                            len(components(parts[0])),
                            allowed,
                        )
                    )
                elif delta:
                    cut_used.append((r.target_cp, w, delta))
                if removed > mint(m, "trim_max_px"):
                    v.append(
                        "U+%04X %s: trim removes %d pixels of the base (limit %d)"
                        % (r.target_cp, w, removed, mint(m, "trim_max_px"))
                    )
            if parts:
                joined = "join" in r.opts
                want = (
                    len(components(parts[0]))
                    if joined
                    else sum(len(components(p)) for p in parts)
                )
                got = len(components(res.px))
                if want != got:
                    if joined:
                        v.append(
                            "U+%04X %s: join= mark must touch the base (expected %d "
                            "components, composed glyph has %d)"
                            % (r.target_cp, w, want, got)
                        )
                    else:
                        v.append(
                            "U+%04X %s: parts have %d components, composed glyph has "
                            "%d (mark touches base)" % (r.target_cp, w, want, got)
                        )
    joined_n = sum(1 for r in srcs.recipes if "join" in r.opts)
    trim_info = []
    for w in WEIGHTS:
        if trim_stats[w]:
            trim_info.append(
                "trimmed-base recipes (trim=): %d, pixels removed from the base in "
                "%s: min %d, max %d, mean %.1f"
                % (
                    len(trim_stats[w]),
                    w,
                    min(trim_stats[w]),
                    max(trim_stats[w]),
                    sum(trim_stats[w]) / len(trim_stats[w]),
                )
            )
    declared_cut = sorted(
        r.target_cp
        for r in srcs.recipes
        if int(r.opts.get("cut", "0")) > 0 and r.target_cp not in srcs.glyphs
    )
    used_cut = {c for c, _w, _d in cut_used}
    for c in declared_cut:
        if c not in used_cut:
            v.append(
                "U+%04X declares cut= but the trim leaves the part count of the base "
                "unchanged: remove the declaration" % c
            )
    trim_info.append(
        "recipes with a declared cut (the mark replaces or splits a stroke of the "
        "base, cut=): %d: %s"
        % (len(declared_cut), " ".join("U+%04X" % c for c in declared_cut) or "none")
    )
    rep.add(
        "R06",
        "every alias/recipe resolves; composed parts do not touch",
        n,
        v,
        ["recipes with a declared joining mark (join=): %d" % joined_n] + trim_info,
    )

    # R07 duplicates -------------------------------------------------------------------
    v = list(srcs.duplicates)
    seen = {}
    for a in srcs.aliases:
        if a.target_cp in seen:
            v.append("U+%04X defined twice (alias)" % a.target_cp)
        seen[a.target_cp] = "alias"
        if a.target_cp in srcs.glyphs:
            v.append("U+%04X is both drawn and aliased" % a.target_cp)
    rec_seen = set()
    for r in srcs.recipes:
        if r.target_cp in rec_seen:
            v.append("U+%04X has two recipes" % r.target_cp)
        rec_seen.add(r.target_cp)
        if r.target_cp in seen:
            v.append("U+%04X is both aliased and composed" % r.target_cp)
    overrides = [cp for cp in rec_seen if cp in srcs.glyphs]
    rep.add(
        "R07",
        "no duplicate codepoint",
        len(cps) + len(srcs.marks),
        v,
        [
            "overrides (drawn grid replaces a recipe): %s"
            % (", ".join("U+%04X" % c for c in sorted(overrides)) or "none")
        ],
    )

    # R08 Bold comparison --------------------------------------------------------------
    v, n, flagged, restored = [], 0, [], []
    overlays_glyph = set(srcs.bold_glyphs)
    overlays_mark = set(srcs.bold_marks)

    def sig(px):
        return (counters(px), len(components(px)))

    def derived_sig(px_regular):
        from nifen_src import embolden

        return sig(embolden(px_regular, bold_shift))

    def derived_lost(px_regular):
        """Counters of a drawn Regular that the plain derivation fills in."""
        from nifen_src import embolden

        return lost_counters(px_regular, embolden(px_regular, bold_shift))

    def runs_per_row(px):
        rows = {}
        for x, y in px:
            rows.setdefault(y, []).append(x)
        out = {}
        for y, xs in rows.items():
            xs.sort()
            out[y] = 1 + sum(1 for a, b in zip(xs, xs[1:]) if b != a + 1)
        return out

    def gap_closes(px_regular):
        """The plain derivation merges ink runs in a row (a one-pixel gap closes)."""
        from nifen_src import embolden

        r0, r1 = runs_per_row(px_regular), runs_per_row(
            embolden(px_regular, bold_shift)
        )
        return any(r1.get(y, 0) < r0[y] for y in r0)

    def needs_overlay(cp, reg, bold):
        """The plain derivation of a drawn glyph changes its counters or parts."""
        if sig(bold) != sig(reg):
            return True
        return cp in srcs.glyphs and derived_lost(reg) > 0

    for cp in cps:
        n += 1
        reg = font.bmp(cp, "regular").px
        bold = font.bmp(cp, "bold").px
        sr = sig(reg)
        if cp in overlays_glyph:
            if sig(bold) != sr:
                v.append(
                    "U+%04X Bold overlay does not restore counters/parts: Regular "
                    "%s, overlay %s" % (cp, sr, sig(bold))
                )
            # was it needed? compare with the pure derivation (for a composed glyph: the
            # composition of the
            # Bold parts, without the overlay of the glyph itself)
            if cp in srcs.glyphs or cp not in font.recipe_by_cp:
                plain_sig = derived_sig(reg)
            else:
                plain_sig = sig(font._recipe(font.recipe_by_cp[cp], "bold", (cp,)).px)
            if plain_sig == sr and not (
                cp in srcs.glyphs and (derived_lost(reg) > 0 or gap_closes(reg))
            ):
                v.append(
                    "U+%04X has a Bold overlay but the derived Bold was not flagged"
                    % cp
                )
            restored.append(cp)
        else:
            if sig(bold) != sr:
                v.append(
                    "U+%04X derived Bold changes (counters, parts) %s -> %s: needs a "
                    "correction overlay" % (cp, sr, sig(bold))
                )
                flagged.append(cp)
            elif cp in srcs.glyphs and derived_lost(reg) > 0:
                v.append(
                    "U+%04X derived Bold fills in %d Regular counter(s) although the "
                    "count agrees: needs a correction overlay" % (cp, derived_lost(reg))
                )
                flagged.append(cp)
    mark_info = []
    for name in sorted(srcs.marks):
        n += 1
        mk = srcs.marks[name]
        reg = mk.pixels()
        sr = sig(reg)
        mpx, _a, _w = font.mark_bmp(name, "bold")
        if name in overlays_mark:
            if sig(mpx) != sr:
                v.append("mark %s Bold overlay does not restore counters/parts" % name)
            if derived_sig(reg) == sr:
                v.append(
                    "mark %s has a Bold overlay but the derived Bold was not flagged"
                    % name
                )
            mark_info.append(name)
        elif sig(mpx) != sr:
            v.append(
                "mark %s derived Bold changes %s -> %s: needs a correction overlay"
                % (name, sr, sig(mpx))
            )
    for name in overlays_mark:
        if name not in srcs.marks:
            v.append("Bold overlay for unknown mark %s" % name)
    for cp in overlays_glyph:
        if cp not in font.codepoints():
            v.append("Bold overlay for undefined U+%04X" % cp)
    detail = []
    for cp in sorted(restored):
        reg = font.bmp(cp, "regular").px
        if cp in srcs.glyphs or cp not in font.recipe_by_cp:
            plain_sig = derived_sig(reg)
        else:
            plain_sig = sig(font._recipe(font.recipe_by_cp[cp], "bold", (cp,)).px)
        detail.append(
            "U+%04X flagged: Regular (counters, parts) %s, plain derivation %s with "
            "%d counter(s) filled in, drawn overlay %s"
            % (
                cp,
                sig(reg),
                plain_sig,
                derived_lost(reg) if cp in srcs.glyphs else 0,
                sig(font.bmp(cp, "bold").px),
            )
        )
    for name in sorted(mark_info):
        reg = srcs.marks[name].pixels()
        detail.append(
            "mark %s flagged: Regular %s, plain derivation %s, drawn overlay %s"
            % (name, sig(reg), derived_sig(reg), sig(font.mark_bmp(name, "bold")[0]))
        )
    # information only (not a gate): drawn glyphs whose plain Bold derivation merges
    # ink runs inside a row (a one-pixel gap closes). Counter and part counts cannot
    # see this; it is the measured worklist for the Bold correction pass.
    from nifen_src import embolden as _emb

    merged = []
    for cp in cps:
        if (
            cp not in srcs.glyphs
            or cp in overlays_glyph
            or srcs.glyphs[cp].has_flag("solid")
        ):
            continue
        reg = font.bmp(cp, "regular").px
        r0, r1 = runs_per_row(reg), runs_per_row(_emb(reg, bold_shift))
        closed = sum(1 for y in r0 if r1.get(y, 0) < r0[y])
        if closed:
            merged.append((cp, closed))
    merge_info = (
        "Bold gap-closure worklist (information, not a gate): %d drawn glyphs close "
        "a one-pixel gap in at least one row: %s"
        % (len(merged), " ".join("U+%04X(%d)" % (c, n) for c, n in merged))
    )
    clean = len(cps) - len(restored)
    rep.add(
        "R08",
        "Bold counter / part comparison (flagged need overlays)",
        n,
        v,
        [
            "Bold derived cleanly: %d of %d codepoints; flagged and corrected by a "
            "drawn overlay: %d" % (clean, len(cps), len(restored)),
            "Bold overlays present: glyphs %s; marks %s"
            % (
                ", ".join("U+%04X" % c for c in sorted(restored)) or "none",
                ", ".join(mark_info) or "none",
            ),
            merge_info,
        ]
        + detail,
    )

    # R09 public-safe scan
    # -------------------------------------------------------------------------------
    v, n = [], 0
    targets = []
    for name in srcs.files + ["metrics.txt"]:
        targets.append(os.path.join(src_dir, name))
    targets += script_files
    for path in sorted(targets):
        n += 1
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
        for ln, line in enumerate(text.split("\n"), 1):
            for label, pat in UNSAFE:
                if pat.search(line):
                    v.append("%s:%d contains %s" % (os.path.basename(path), ln, label))
    rep.add("R09", "public-safe scan of sources and scripts", n, v)

    # R10 outline fidelity -------------------------------------------------------------
    v, n = [], 0
    for cp in cps:
        for w in WEIGHTS:
            n += 1
            px = font.bmp(cp, w).px
            loops = contours(px)
            if fill_from_contours(loops) != px:
                v.append("U+%04X %s outline does not reproduce the pixels" % (cp, w))
    rep.add("R10", "outline reproduces the pixel grid exactly", n, v)

    # R11 contract constants -----------------------------------------------------------
    v, n = [], 0
    for key, want in (("em_px", 12), ("units_per_px", 128), ("units_per_em", 1536)):
        n += 1
        if mint(m, key) != want:
            v.append("%s is %s, expected %d" % (key, m[key], want))
    n += 1
    if mint(m, "units_per_em") != mint(m, "em_px") * U:
        v.append("units_per_em is not em_px * units_per_px")
    n += 1
    if mint(m, "line_ascent_px") < em_top or mint(m, "line_descent_px") < -em_bot:
        v.append("line box does not contain the em box")
    rep.add("R11", "grid contract constants", n, v)

    # R12 small kana placement ---------------------------------------------------------
    # Every small kana sits on the bottom row of the cell and is at most
    # small_kana_max_rows tall. Hiragana small kana are centred in the cell (the
    # horizontal-writing convention of Japanese typesetting: horizontally centred,
    # below the vertical centre); the katakana small kana keep their earlier left-hand
    # placement.
    v, n = [], 0
    small = [parse_cp(t) for t in m.get("small_kana_cps", "").split()]
    left = {parse_cp(t) for t in m.get("small_kana_left_cps", "").split()}
    centred = {parse_cp(t) for t in m.get("small_kana_centred_cps", "").split()}
    sb, smax = mint(m, "small_kana_bottom_row"), mint(m, "small_kana_max_rows")
    sxr, sxb = rng(m["small_kana_ink_x_regular"]), rng(m["small_kana_ink_x_bold"])
    c2 = mint(m, "small_kana_centre_x2")
    c2tol = mint(m, "small_kana_centre_tol_x2")
    c2bold = mint(m, "small_kana_bold_extra_x2")
    cmax = mint(m, "small_kana_centred_max_cols")
    heights, widths = [], []
    for cp in small:
        if cp not in left and cp not in centred:
            n += 1
            v.append("U+%04X is a small kana with no declared placement class" % cp)
        if cp in left and cp in centred:
            n += 1
            v.append("U+%04X is declared both left-placed and centred" % cp)
        for w in WEIGHTS:
            n += 1
            bb = bbox(font.bmp(cp, w).px)
            lo, hi = sxr if w == "regular" else sxb
            if bb is None:
                v.append("U+%04X %s small kana has no ink" % (cp, w))
                continue
            heights.append(bb[3] - bb[1] + 1)
            if bb[1] != sb:
                v.append(
                    "U+%04X %s small kana bottom row %d != %d (small kana sit on the "
                    "bottom of the cell)" % (cp, w, bb[1], sb)
                )
            if bb[3] - bb[1] + 1 > smax:
                v.append(
                    "U+%04X %s small kana is %d rows tall, more than %d"
                    % (cp, w, bb[3] - bb[1] + 1, smax)
                )
            if cp in left and (bb[0] < lo or bb[2] > hi):
                v.append(
                    "U+%04X %s small kana ink columns %d..%d outside %d..%d (these "
                    "small kana sit to the left)" % (cp, w, bb[0], bb[2], lo, hi)
                )
            if cp in centred:
                width = bb[2] - bb[0] + 1
                widths.append(width)
                mid2 = bb[0] + bb[2] + 1
                want = c2 + (c2bold if w == "bold" else 0)
                if abs(mid2 - want) > c2tol:
                    v.append(
                        "U+%04X %s small kana is not centred: ink columns %d..%d, "
                        "twice the centre %d, expected %d +-%d"
                        % (cp, w, bb[0], bb[2], mid2, want, c2tol)
                    )
                if width > cmax + (1 if w == "bold" else 0):
                    v.append(
                        "U+%04X %s small kana is %d columns wide, more than %d"
                        % (cp, w, width, cmax + (1 if w == "bold" else 0))
                    )
    rep.add(
        "R12",
        "small kana: bottom row, height and horizontal placement",
        n,
        v,
        (
            [
                "small kana heights in rows: min %d, max %d"
                % (min(heights), max(heights))
            ]
            if heights
            else []
        )
        + (
            [
                "centred small kana widths in columns (both weights): min %d, max %d"
                % (min(widths), max(widths))
            ]
            if widths
            else []
        ),
    )

    # R13 voicing mark clearance -------------------------------------------------------
    # In every voiced or semi-voiced kana, in each weight, the mark is whole inside
    # the glyph and no pixel of the base is within one pixel of it (so the mark never
    # touches the base). This covers composed and hand-drawn glyphs alike.
    v, n = [], 0
    mark_cps = {parse_cp(t) for t in m.get("voicing_mark_cps", "").split()}
    voiced = []
    for r in srcs.recipes:
        if r.op != "overlay" or len(r.args) < 2:
            continue
        mk = parse_cp(r.args[1], "%s:%d" % (r.path, r.line))
        if mk in mark_cps:
            voiced.append((r.target_cp, mk))
    gaps = []
    for cp, mk in sorted(voiced):
        for w in WEIGHTS:
            n += 1
            glyph = font.bmp(cp, w).px
            mark = font.bmp(mk, w).px
            if not mark <= glyph:
                v.append(
                    "U+%04X %s: the voicing mark U+%04X is not whole inside the glyph"
                    % (cp, w, mk)
                )
                continue
            base = glyph - mark
            halo = {
                (x + dx, y + dy)
                for (x, y) in mark
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
            }
            touching = sorted(base & halo)
            if touching:
                v.append(
                    "U+%04X %s: %d pixel(s) of the base are within one pixel of the "
                    "voicing mark, first at %s" % (cp, w, len(touching), touching[0])
                )
            elif base:
                d = min(
                    max(abs(x - a), abs(y - b)) for (x, y) in base for (a, b) in mark
                )
                gaps.append(d)
    rep.add(
        "R13",
        "voicing mark whole and clear of the base (one pixel)",
        n,
        v,
        (
            [
                "voiced and semi-voiced kana: %d, smallest clearance between mark "
                "and base %d pixel steps (both weights)" % (len(voiced), min(gaps))
            ]
            if gaps
            else []
        ),
    )

    # R14 provenance of merged letterforms and the donor gate ------------------------
    n, v, donor_cps = provenance_checks(srcs, font, src_dir, fonts_dir)
    info = (
        [
            "code points taken from the donor: %d: %s"
            % (len(donor_cps), spans(donor_cps))
        ]
        if donor_cps
        else []
    )
    if gate is not None:
        gate_n, gate_v, gate_info = donor_gate(srcs, src_dir, fonts_dir, gate)
        n, v, info = n + gate_n, v + gate_v, info + gate_info
    rep.add(
        "R14",
        "provenance of merged letterforms (donor files and licence files)",
        n,
        v,
        info,
    )
    return rep


def spans(cps):
    out, cps = [], sorted(set(cps))
    i = 0
    while i < len(cps):
        j = i
        while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1:
            j += 1
        out.append("U+%04X" % cps[i] if i == j else "U+%04X-U+%04X" % (cps[i], cps[j]))
        i = j + 1
    return ", ".join(out)


def provenance_checks(srcs, font: Font, src_dir, fonts_dir):
    """Provenance of merged letterforms (rule R14): the donor files, the licence
    file and the change log beside the fonts, and the Reserved Font Name clause.
    Returns (examined, violations, donor code points)."""
    m = srcs.metrics
    # Provenance of merged letterforms ---------------------------------------------
    # Letterforms adapted from another font under its open licence live in their own
    # source files (metrics: donor_files, the files that draw donor code points).
    # Every source file derived from the donor, drawing files and correction files
    # alike, is listed in metrics donor_derived_files; the header of each carries the
    # donor's name, version, licence and copyright line, and a file that mentions the
    # donor and is not listed is a violation, so no file can be left unchecked by being
    # left undeclared. The licence file and the change log shipped beside the fonts
    # carry the copyright line, and the change log names exactly the code points taken
    # from the donor in one sentence of the form
    # "Code points adapted from <donor>, version <version>: <ranges>".
    v, n = [], 0
    donors = m.get("donor_files", "").split()
    derived = m.get("donor_derived_files", "").split()
    prior = [
        m[k] for k in sorted(m) if k.startswith("copyright_prior_line") and m[k].strip()
    ]
    dname = m.get("donor_name", "")
    dver = m.get("donor_version", "")
    dlic = m.get("donor_licence", "")
    n += 1
    if bool(donors) != bool(prior):
        v.append("donor_files and copyright_prior_line must be declared together")
    if bool(derived) != bool(donors):
        v.append("donor_derived_files and donor_files must be declared together")
    for name in donors:
        if name not in derived:
            v.append("donor file %s is not listed in donor_derived_files" % name)
    for need_key, need in (("donor_name", dname), ("donor_version", dver)):
        if (donors or derived) and not need:
            v.append("%s is not declared" % need_key)
    # The header is the comment block before the first record of the file. A trailing
    # full stop of a copyright line is punctuation of the donor's own sentence, not part
    # of the notice, so a header may continue the line with a semicolon or a bracket.
    for name in derived:
        n += 1
        if name not in srcs.files:
            v.append("donor-derived file %s is not among the sources" % name)
            continue
        with open(os.path.join(src_dir, name), "rb") as fh:
            text = fh.read().decode("utf-8")
        header = []
        for line in text.split("\n"):
            line = line.rstrip("\r")
            if line.strip() and not (line.startswith("# ") or line.strip() == "#"):
                break
            header.append(line)
        head = "\n".join(header)
        for label, need in [("name", dname), ("version", dver), ("licence", dlic)] + [
            ("copyright line", p.rstrip(".")) for p in prior
        ]:
            if need and need not in head:
                v.append("%s: the header does not state the donor %s" % (name, label))
    # A file that speaks of the donor must be declared. Every other source file is read
    # whole (comments wrapped across lines and notes after a record included).
    donor_key = " ".join(dname.lower().split())
    if donor_key:
        for name in srcs.files:
            if name in derived:
                continue
            n += 1
            with open(os.path.join(src_dir, name), "rb") as fh:
                flat = " ".join(
                    fh.read().decode("utf-8").replace("#", " ").lower().split()
                )
            if donor_key in flat:
                v.append(
                    "%s mentions the donor (%s) but is not listed in "
                    "donor_derived_files" % (name, dname)
                )
    donor_cps = []
    for name in donors:
        if name not in srcs.files:
            v.append("donor file %s is not among the sources" % name)
            continue
        n += 1
        recs = [r for r in srcs.glyphs.values() if r.path == name]
        n += len(recs)
        for r in recs:
            if not isinstance(r.key, int):
                v.append("%s:%d: a donor file draws only code points" % (name, r.line))
                continue
            donor_cps.append(r.key)
            if r.key in font.recipe_by_cp:
                v.append("U+%04X is both a donor drawing and a recipe" % r.key)

    if donor_cps:
        needs = {
            "OFL.txt": list(prior),
            "FONTLOG.txt": list(prior)
            + [
                "Code points adapted from %s, version %s: %s"
                % (dname, dver, spans(donor_cps))
            ],
        }
        for fname in sorted(needs):
            n += 1
            path = os.path.join(fonts_dir, fname)
            if not os.path.exists(path):
                v.append("%s is not beside the fonts" % fname)
                continue
            with open(path, "rb") as fh:
                text = " ".join(fh.read().decode("utf-8").split())
            for need in needs[fname]:
                if " ".join(need.split()) not in text:
                    v.append("%s does not state %r" % (fname, need))
    # The Reserved Font Name clause ends the typeface's own line of OFL.txt (line 2
    # with one prior line) and is not attached to a prior line.
    n += 1
    if m.get("copyright_rfn_clause") != RFN_CLAUSE:
        v.append(
            "metrics copyright_rfn_clause is %r, not %r"
            % (m.get("copyright_rfn_clause"), RFN_CLAUSE)
        )
    ofl_path = os.path.join(fonts_dir, "OFL.txt")
    if os.path.exists(ofl_path):
        with open(ofl_path, "rb") as fh:
            ofl_lines = fh.read().decode("utf-8").splitlines()
        own_prefix = "Copyright (c) %s, %s" % (
            m["copyright_year"],
            m["copyright_holder"],
        )
        own_at = [i for i, ln in enumerate(ofl_lines) if ln.startswith(own_prefix)]
        if not own_at:
            v.append("OFL.txt has no line starting %r" % own_prefix)
        else:
            if not ofl_lines[own_at[0]].rstrip().endswith(RFN_CLAUSE):
                v.append(
                    "OFL.txt line %d (the typeface's own copyright line) does not "
                    "end with %r" % (own_at[0] + 1, RFN_CLAUSE)
                )
            if own_at[0] != len(prior):
                v.append(
                    "OFL.txt line %d is the typeface's own copyright line; it must "
                    "follow the %d prior line(s) directly" % (own_at[0] + 1, len(prior))
                )
        for i, ln in enumerate(ofl_lines):
            if any(p in ln for p in prior) and RFN_PHRASE in ln:
                v.append(
                    "OFL.txt line %d (a prior copyright line) carries %r; the "
                    "clause belongs to the typeface's own line only"
                    % (i + 1, RFN_PHRASE)
                )
    elif not donor_cps:
        v.append("OFL.txt is not beside the fonts")
    return n, v, donor_cps


# --------------------------------------------------------------------------
# The donor gate
# --------------------------------------------------------------------------
# The font has exactly one donor: the Ark Pixel Font hiragana (the 89 code points of
# DONOR_SPANS). The gate fails when any other donor is declared or credited, when a
# donor-derived code point lies outside those 89, or when the CJK face declares a donor
# of any kind. It reads every file of the scan list, prints the list with the status of
# each entry, and treats a missing entry as a violation, never as a file to skip.


def walk_files(base):
    """Every file below base, as sorted relative paths with forward slashes."""
    names = []
    for root, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(root, name), base)
            names.append(rel.replace(os.sep, "/"))
    return sorted(names)


def holder_ok(holder, allowed):
    """True when a copyright holder text starts with the allowed holder's name."""
    return re.match(re.escape(allowed) + r"(?![A-Za-z0-9])", holder, re.I) is not None


def credit_findings(label, text, cjk_scope, prose, donors):
    """What one text credits. Every copyright holder must be a declared one (the donor's
    only outside the CJK face); the CJK face names no donor at all; no other font is
    named; and, in a licence file, a change log, the notice file or a name record
    (prose), a sentence that says a drawing was adapted, copied, traced or derived from
    something must name the donor, unless it states that nothing was taken from another
    font. Names found as donors are added to the set donors."""
    out = []
    flat = " ".join(text.replace("#", " ").split())
    allowed = OWN_HOLDERS if cjk_scope else OWN_HOLDERS + (DONOR_HOLDER,)
    for mt in HOLDER_RE.finditer(flat):
        holder = HOLDER_END_RE.split(mt.group(1).strip(), 1)[0].rstrip(" .,;:")
        if holder_ok(holder, DONOR_HOLDER):
            donors.add(DONOR_NAME)
        elif not any(holder_ok(holder, a) for a in allowed):
            donors.add(holder[:40])
        if not any(holder_ok(holder, a) for a in allowed):
            out.append(
                "%s: a copyright line credits %r, who is not a declared holder%s"
                % (label, holder[:40], " of the CJK face" if cjk_scope else "")
            )
    if cjk_scope and DONOR_RE.search(flat):
        out.append("%s: names the donor; the CJK face declares no donor" % label)
    low = flat.lower()
    for name in OTHER_FONTS:
        if name.lower() in low:
            donors.add(name)
            out.append("%s: names another font (%s) as a donor" % (label, name))
    for mt in STRUCTURED_CREDIT_RE.finditer(flat):
        donors.add(mt.group(1).strip()[:40])
    if prose:
        for sentence in SENTENCE_SPLIT_RE.split(flat):
            mt = CREDIT_RE.search(sentence)
            if mt is None:
                continue
            if not cjk_scope and DONOR_NAME.lower() in sentence.lower():
                continue
            if NEGATION_RE.search(sentence[: mt.start()]) and GENERIC_SOURCE_RE.search(
                sentence[mt.start() :]
            ):
                continue
            out.append(
                "%s: a credit sentence names no declared donor: %r"
                % (label, sentence[:70])
            )
    return out


def cjk_file_name(face, set_key, weight):
    return "%s-%s.ttf" % (
        face["postscript_" + set_key],
        "Bold" if weight == "bold" else "Regular",
    )


def cjk_name_table(m, face, set_key, weight):
    """The name records of one CJK font. Only the Nifen Art copyright line: this face
    declares no donor, so no prior copyright line comes before it."""
    style = "Bold" if weight == "bold" else "Regular"
    family = face["family_" + set_key]
    return {
        0: "Copyright (c) %s, %s (%s), %s"
        % (
            m["copyright_year"],
            m["copyright_holder"],
            m["copyright_url"],
            m["copyright_rfn_clause"],
        ),
        1: family,
        2: style,
        3: "%s %s;%s" % (family, style, face["font_revision"]),
        4: "%s %s" % (family, style),
        5: face["version_string"],
        6: "%s-%s" % (face["postscript_" + set_key], style),
        9: m["designer"],
        13: m["license_description"],
        14: m["license_url"],
    }


def donor_gate(srcs, src_dir, fonts_dir, gate):
    """The donor gate. Returns (examined, violations, info lines)."""
    m = srcs.metrics
    v, scan, donors = [], [], set()
    n = 0

    def read(path, label):
        try:
            with open(path, "rb") as fh:
                return fh.read().decode("utf-8")
        except FileNotFoundError:
            v.append("%s is missing: a scanned file is never skipped" % label)
            scan.append((label, "MISSING"))
        except UnicodeDecodeError:
            v.append("%s is not UTF-8 text" % label)
            scan.append((label, "UNREADABLE"))
        return None

    # 1. The donor record in the metadata: one donor, as fixed above.
    n += 1
    for key in sorted(m):
        if key.startswith("donor") and key not in DONOR_KEYS:
            v.append("metrics.txt declares %s: a second donor is refused" % key)
        if key.startswith("copyright_prior_line") and key != "copyright_prior_line_1":
            v.append(
                "metrics.txt declares %s: only the one donor's copyright line is "
                "accepted" % key
            )
    if m.get("donor_name"):
        donors.add(m["donor_name"])
    for key, want in (
        ("donor_name", DONOR_NAME),
        ("donor_version", DONOR_VERSION),
        ("donor_licence", DONOR_LICENCE),
    ):
        if m.get(key) != want:
            v.append("metrics.txt %s is %r, expected %r" % (key, m.get(key), want))
    if m.get("donor_files", "").split() != list(DONOR_FILES):
        v.append(
            "metrics.txt donor_files is %r, exactly %s is accepted"
            % (m.get("donor_files", ""), " ".join(DONOR_FILES))
        )
    listed = m.get("donor_derived_files", "").split()
    for name in listed:
        if name not in DONOR_DERIVED_FILES:
            v.append(
                "%s is listed as a donor-derived file: a third one is refused "
                "(exactly %s are accepted)" % (name, " and ".join(DONOR_DERIVED_FILES))
            )
    for name in DONOR_DERIVED_FILES:
        if name not in listed:
            v.append("%s is not listed in donor_derived_files" % name)
    if DONOR_HOLDER not in m.get("copyright_prior_line_1", ""):
        v.append("metrics.txt copyright_prior_line_1 does not name %s" % DONOR_HOLDER)

    # 2. The donor-derived code points are exactly the 89 hiragana.
    expected = {cp for lo, hi in DONOR_SPANS for cp in range(lo, hi + 1)}
    derived_files = set(listed) | set(DONOR_DERIVED_FILES)
    donor_cps = set()
    for rec in list(srcs.glyphs.values()) + list(srcs.bold_glyphs.values()):
        if rec.path in derived_files and isinstance(rec.key, int):
            n += 1
            donor_cps.add(rec.key)
            if rec.key not in expected:
                v.append(
                    "U+%04X is donor-derived (%s:%d) but lies outside the 89 hiragana "
                    "%s" % (rec.key, rec.path, rec.line, spans(sorted(expected)))
                )
    gone = sorted(expected - donor_cps)
    if gone:
        v.append(
            "the donor-derived code points are not the 89 hiragana: %d missing, "
            "first U+%04X" % (len(gone), gone[0])
        )

    # 3. The scan list: sources of both faces, licence files, change logs, notice file.
    def scan_tree(display, base, cjk_scope):
        nonlocal n
        if not os.path.isdir(base):
            v.append("%s is missing: a scanned folder is never skipped" % display)
            scan.append((display + "/**", "MISSING"))
            return
        names = walk_files(base)
        if not names:
            v.append("%s holds no file: nothing was scanned" % display)
        for rel in names:
            label = display + "/" + rel
            text = read(os.path.join(base, *rel.split("/")), label)
            if text is None:
                continue
            n += 1
            scan.append((label, "examined"))
            if cjk_scope:
                if DONOR_RE.search(rel):
                    v.append("%s: a file of the CJK face named for the donor" % label)
                if rel in DONOR_DERIVED_FILES or rel in listed:
                    v.append("%s: a donor-derived file under the CJK face" % label)
                text = MANIFEST_LINE_RE.sub("", text)
            v.extend(credit_findings(label, text, cjk_scope, False, donors))

    scan_tree("fonts-src/nifen-art", src_dir, False)
    scan_tree("fonts-src/nifen-art-cjk", gate.cjk_dir, True)
    for fname, cjk_scope in (
        ("OFL.txt", False),
        ("FONTLOG.txt", False),
        ("FONTLOG-CJK.txt", True),
    ):
        label = "pixelart_creator/fonts/" + fname
        text = read(os.path.join(fonts_dir, fname), label)
        if text is not None:
            n += 1
            scan.append((label, "examined"))
            v.extend(credit_findings(label, text, cjk_scope, True, donors))
    text = read(gate.notice, "NOTICE")
    if text is not None:
        n += 1
        scan.append(("NOTICE", "examined"))
        v.extend(credit_findings("NOTICE", text, False, True, donors))

    # 4. The name tables of all eight fonts.
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        TTFont = None
        v.append("fontTools cannot be imported: the name tables cannot be examined")

    def scan_names(label, texts, cjk_scope):
        """Examine the name records of one font; one more entry examined."""
        nonlocal n
        n += 1
        for nid, text in texts:
            v.extend(
                credit_findings(
                    "%s name ID %d" % (label, nid), text, cjk_scope, True, donors
                )
            )

    def disk_names(path):
        with TTFont(path) as font:
            return sorted((rec.nameID, rec.toUnicode()) for rec in font["name"].names)

    if gate.ttfs and TTFont is not None:
        for w in WEIGHTS:
            fname = FILE_NAMES[w]
            label = "pixelart_creator/fonts/" + fname
            path = os.path.join(gate.out_dir, fname)
            if not os.path.exists(path):
                v.append("%s is missing: a scanned font is never skipped" % label)
                scan.append((label, "MISSING"))
                continue
            texts = disk_names(path)
            scan_names(label, texts, False)
            scan.append((label, "examined (name table, %d records)" % len(texts)))
    elif not gate.ttfs:
        for w in WEIGHTS:
            label = "pixelart_creator/fonts/" + FILE_NAMES[w]
            scan.append((label, "read after this run builds it"))
    face, counts = None, {}
    try:
        cjk = parse_cjk_sources(gate.cjk_dir)
        face = cjk.face
        counts = {s: len(CjkFont(cjk).codepoints(s)) for s in CJK_SETS}
    except (SourceError, OSError) as exc:
        v.append("the CJK sources cannot be read: %s" % exc)
    if face is not None:
        for s in CJK_SETS:
            for w in WEIGHTS:
                try:
                    fname = cjk_file_name(face, s, w)
                    names = cjk_name_table(m, face, s, w)
                except KeyError as exc:
                    v.append("face.txt lacks %s" % exc)
                    continue
                label = "pixelart_creator/fonts/" + fname
                # The records the build writes are examined from the sources, so the
                # name tables of fonts that do not exist yet are still gated.
                scan_names(label + " (from the sources)", sorted(names.items()), True)
                status = "examined from the sources"
                path = os.path.join(gate.out_dir, fname)
                if not gate.ttfs or TTFont is None:
                    pass
                elif os.path.exists(path):
                    texts = disk_names(path)
                    scan_names(label, texts, True)
                    status += "; built, name table examined (%d records)" % len(texts)
                elif counts[s] > 0:
                    v.append(
                        "%s is missing: the %s set has %d glyph records"
                        % (label, s, counts[s])
                    )
                    status = "MISSING"
                else:
                    status += "; not built, the %s set has no glyph record yet" % s
                scan.append((label, status))

    if len(donors) != 1:
        v.append(
            "%d donors are declared (%s); exactly one is accepted"
            % (len(donors), ", ".join(sorted(donors)) or "none")
        )
    info = [
        "donors declared: %d (%s)" % (len(donors), ", ".join(sorted(donors)) or "none"),
        "donor-derived code points: %d (%s)" % (len(donor_cps), spans(donor_cps)),
        "donor-derived source files: %d (%s)" % (len(listed), " ".join(listed)),
        "donor gate scan list: %d entries" % len(scan),
    ]
    info += ["  %s: %s" % (label, status) for label, status in scan]
    return n, v, info


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def glyph_name(cp):
    return ".notdef" if cp is None else "uni%04X" % cp


def build_font(srcs, font: Font, weight: str, out_path: str):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    m = srcs.metrics
    U = mint(m, "units_per_px")
    cps = font.codepoints()
    order = [".notdef"] + [glyph_name(cp) for cp in cps]
    glyphs, metrics_ = {}, {}

    def make(px, adv):
        pen = TTGlyphPen(None)
        loops = contours(px)
        xmin = None
        for loop in loops:
            pts = [(x * U, y * U) for x, y in loop]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
        bb = bbox(px)
        xmin = 0 if bb is None else bb[0] * U
        return pen.glyph(), (adv * U, xmin)

    nd = srcs.glyphs[".notdef"]
    npx = nd.pixels()
    nadv = nd.attr_int("adv")
    if weight == "bold":
        from nifen_src import embolden

        npx = embolden(npx, mint(m, "bold_shift_px"))
        nadv += mint(m, "bold_shift_px")
    glyphs[".notdef"], metrics_[".notdef"] = make(npx, nadv)
    cmap = {}
    for cp in cps:
        b = font.bmp(cp, weight)
        name = glyph_name(cp)
        glyphs[name], metrics_[name] = make(b.px, b.adv)
        cmap[cp] = name

    bold = weight == "bold"
    style = "Bold" if bold else "Regular"
    created = epoch_1904(m["created_utc"])
    modified = epoch_1904(m["modified_utc"])
    family = m["family"]
    ps = "NifenArt-" + style
    asc, desc = mint(m, "line_ascent_px") * U, mint(m, "line_descent_px") * U

    fb = FontBuilder(mint(m, "units_per_em"), isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics_)
    fb.setupHorizontalHeader(
        ascent=asc, descent=-desc, lineGap=mint(m, "line_gap_px") * U
    )
    fb.setupHead(
        unitsPerEm=mint(m, "units_per_em"),
        fontRevision=float(m["font_revision"]),
        created=created,
        modified=modified,
        flags=0x0009,
        lowestRecPPEM=mint(m, "em_px"),
        macStyle=1 if bold else 0,
        glyphDataFormat=0,
    )
    year, holder = m["copyright_year"], m["copyright_holder"]
    # Copyright lines of works this font includes (one line each, kept as their authors
    # wrote them) come first; the Reserved Font Name clause follows the last
    # copyright line.
    prior = [
        m[k] for k in sorted(m) if k.startswith("copyright_prior_line") and m[k].strip()
    ]
    names = {
        0: " ".join(
            prior
            + [
                "Copyright (c) %s, %s (%s), %s"
                % (year, holder, m["copyright_url"], m["copyright_rfn_clause"])
            ]
        ),
        1: family,
        2: style,
        3: "%s %s;%s" % (family, style, m["font_revision"]),
        4: "%s %s" % (family, style),
        5: m["version_string"],
        6: ps,
        9: m["designer"],
        13: m["license_description"],
        14: m["license_url"],
    }
    fb.setupNameTable(names)
    fb.setupOS2(
        version=4,
        usWeightClass=700 if bold else 400,
        usWidthClass=5,
        fsType=0,
        achVendID=m["vendor_id"],
        fsSelection=(0x20 if bold else 0x40) | 0x80,
        sTypoAscender=asc,
        sTypoDescender=-desc,
        sTypoLineGap=mint(m, "line_gap_px") * U,
        usWinAscent=asc,
        usWinDescent=desc,
        sxHeight=mint(m, "x_px") * U,
        sCapHeight=mint(m, "cap_px") * U,
        usDefaultChar=0,
        usBreakChar=32,
        ySubscriptXSize=7 * U,
        ySubscriptYSize=7 * U,
        ySubscriptXOffset=0,
        ySubscriptYOffset=1 * U,
        ySuperscriptXSize=7 * U,
        ySuperscriptYSize=7 * U,
        ySuperscriptXOffset=0,
        ySuperscriptYOffset=4 * U,
        yStrikeoutSize=U,
        yStrikeoutPosition=3 * U,
    )
    fb.setupPost(underlinePosition=-2 * U, underlineThickness=U)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fb.save(out_path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def build_all(srcs, font, out_dir):
    paths = {}
    for w in WEIGHTS:
        p = os.path.join(out_dir, FILE_NAMES[w])
        build_font(srcs, font, w, p)
        paths[w] = p
    return paths


def name_table_scan(paths):
    """Public-safe scan of every built name record (both weights)."""
    from fontTools.ttLib import TTFont

    v, n = [], 0
    for w, p in sorted(paths.items()):
        f = TTFont(p)
        for rec in f["name"].names:
            n += 1
            text = rec.toUnicode()
            for label, pat in UNSAFE:
                if pat.search(text):
                    v.append("%s name ID %d contains %s" % (w, rec.nameID, label))
    return n, v


def name0_records(path):
    """Every name ID 0 record of one built font, as (platform, encoding, text)."""
    from fontTools.ttLib import TTFont

    with TTFont(path) as f:
        return [
            (rec.platformID, rec.platEncID, rec.toUnicode())
            for rec in f["name"].names
            if rec.nameID == 0
        ]


def name0_scan(paths, srcs, prior=None):
    """The copyright record (name ID 0) of every built font states each prior copyright
    line of the metrics, before the typeface's line (first record); and, at EVERY
    platform record, the typeface's own line ends with the Reserved Font Name clause
    and the clause is not attached to a prior line. A font with no name ID 0 record is
    a violation. The clause check of a weight runs once the prior lines are in order,
    so each weight reports its first defect. The CJK face passes prior=[]: its record
    holds the typeface's own line only."""
    from fontTools.ttLib import TTFont

    m = srcs.metrics
    if prior is None:
        prior = [
            m[k]
            for k in sorted(m)
            if k.startswith("copyright_prior_line") and m[k].strip()
        ]
    v = []
    for w, p in sorted(paths.items()):
        rec = TTFont(p)["name"].getDebugName(0) or ""
        own = rec.find(
            "Copyright (c) %s, %s" % (m["copyright_year"], m["copyright_holder"])
        )
        bad = False
        for line in prior:
            at = rec.find(line)
            if at < 0 or (own >= 0 and at > own):
                bad = True
                v.append(
                    "%s name ID 0 does not state %r before the typeface's line"
                    % (w, line)
                )
        if bad:
            continue
        records = name0_records(p)
        if not records:
            v.append("%s has no name ID 0 record" % w)
        for plat, enc, text in records:
            where = "%s name ID 0 (platform %d/%d)" % (w, plat, enc)
            if not text.rstrip().endswith(RFN_CLAUSE):
                v.append(
                    "%s: the typeface's own line does not end with %r"
                    % (where, RFN_CLAUSE)
                )
            at = text.find(
                "Copyright (c) %s, %s" % (m["copyright_year"], m["copyright_holder"])
            )
            if at < 0 or RFN_PHRASE in text[: max(at, 0)]:
                v.append(
                    "%s: %r is attached to a prior copyright line, or the "
                    "typeface's own line is absent" % (where, RFN_PHRASE)
                )
    return v


# --------------------------------------------------------------------------
# The CJK face: lint
# --------------------------------------------------------------------------
# Three families (Japanese Han forms, Simplified Han forms, Hangul), Regular and Bold,
# one drawing per glyph for both weights. The rules below are the ones of the existing
# face that apply to full-width glyphs, with these differences: R05 takes a declared,
# reasoned and counted exemption list; R08 is the identity of the two weights; R14 is
# the donor gate; R15 holds the character map to Han and Hangul; R16 holds every glyph
# to a provenance of its own drawing. The rules R02, R03, R12 and R13 describe Latin
# heights, proportional advances and kana, and have no counterpart here.

FACE_REQUIRED = (
    "face",
    "version_string",
    "font_revision",
    "created_utc",
    "modified_utc",
    "exemptions",
    "notdef_box_x",
    "notdef_box_rows",
) + tuple(
    "%s_%s" % (kind, s)
    for kind in ("family", "postscript", "records")
    for s in CJK_SETS
)
# Keys that belong to the grid contract: read from the existing face's metrics.txt,
# never restated in face.txt.
GRID_KEYS = (
    "em_px",
    "units_per_px",
    "units_per_em",
    "cell_adv_px",
    "cell_ink_x_regular",
    "cell_ink_x_bold",
    "cell_ink_rows",
    "line_ascent_px",
    "line_descent_px",
    "line_gap_px",
    "cap_px",
    "x_px",
    "asc_px",
    "desc_px",
    "em_top_px",
    "em_bottom_px",
)
CJK_ATTRS = ("set", "src", "same-as", "top", "x", "dots", "solid", "at", "reason")
# Attribute names that would record where a drawing came from. A CJK record names its
# provenance in src= only, and the only values accepted are drawn and recipe.
SOURCE_ATTRS = (
    "copied",
    "copied-from",
    "copied_from",
    "from",
    "font",
    "donor",
    "adapted-from",
    "traced-from",
    "source",
    "source-font",
    "ref",
)
FREEZE_NAME = "existing-face.sha256"


def han_hangul_ranges():
    """The Han and Hangul code point ranges, read from logic/constants.py (the one
    source) without importing the package."""
    rel = "pixelart_creator/logic/constants.py"
    path = os.path.join(REPO, *rel.split("/"))
    spec = importlib.util.spec_from_file_location("_nifen_script_constants", path)
    if spec is None or spec.loader is None or not os.path.isfile(path):
        raise SourceError("%s cannot be loaded: the ranges are imported from it" % rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        return tuple(module.HAN_RANGES), tuple(module.HANGUL_RANGES)
    except AttributeError as exc:
        raise SourceError("%s lacks %s" % (rel, exc))


def in_ranges(cp, ranges):
    return any(lo <= cp <= hi for lo, hi in ranges)


def cjk_weight_pixels(cfont, key, set_key, weight):
    """The bitmap of a CJK glyph in a weight. Bold is Regular, pixel for pixel."""
    return cfont.pixels(key, set_key, "regular")


def cjk_notdef(m, face):
    """The missing-glyph box: a one-pixel frame in the declared columns and rows."""
    a, b = rng(face["notdef_box_x"])
    lo, hi = rng(face["notdef_box_rows"])
    return frozenset(
        (x, y)
        for x in range(a, b + 1)
        for y in range(lo, hi + 1)
        if x in (a, b) or y in (lo, hi)
    )


def first_block(px):
    """The first 2x2 block of lit pixels, as its lowest-leftmost pixel, or None."""
    for x, y in sorted(px):
        if (x + 1, y) in px and (x, y + 1) in px and (x + 1, y + 1) in px:
            return (x, y)
    return None


def dots_of(rec):
    try:
        return int(rec.attrs.get("dots", "0"))
    except ValueError:
        return 0


def cjk_allowance(cjk, key, set_key, seen=()):
    """Declared isolated-pixel allowance of a glyph (its own dots plus its parts')."""
    ident = (key, set_key)
    rec = cjk.glyphs.get(ident)
    if rec is None or ident in seen:
        return 0
    seen = seen + (ident,)
    same = rec.attrs.get("same-as")
    if same:
        return cjk_allowance(cjk, key, same, seen)
    src = rec.attrs.get("src", "")
    total = dots_of(rec)
    if src.startswith("recipe:"):
        for tok in src[len("recipe:") :].split(","):
            try:
                part = cjk_key(tok, "")
            except SourceError:
                continue
            total += cjk_allowance(cjk, part, set_key, seen)
    return total


def order_key(ident):
    """Sort key: set order, then code points before parts, then the key."""
    key, s = ident
    rank = CJK_SETS.index(s) if s in CJK_SETS else len(CJK_SETS)
    if isinstance(key, int):
        return (rank, 0, key, "")
    return (rank, 1, 0, str(key))


def lint_cjk(srcs, font, cjk, cfont, script_files, src_dir, cjk_dir, fonts_dir, gate):
    """Lint of the CJK face. Returns the report. A face with no glyph record yet is a
    scaffold: the rules that examine glyphs report 0 examined and do not fail on that
    alone (they fail as soon as a record exists and the rule reaches none of it)."""
    rep = Report()
    m = srcs.metrics
    face = cjk.face
    kx = rng(m["cell_ink_x_regular"])
    ky = rng(m["cell_ink_rows"])
    em_bot, em_top = mint(m, "em_bottom_px"), mint(m, "em_top_px")
    idents = sorted(cjk.glyphs, key=order_key)
    cp_idents = [i for i in idents if isinstance(i[0], int)]
    if not idents:
        rep.zero_ok.update(
            ("R01", "R04", "R05", "R06", "R07", "R08", "R10", "R15", "R16")
        )

    # Resolve every record once. A record that does not resolve is reported by R06 and
    # left out of the rules that need its bitmap.
    pixels, unresolved = {}, {}
    for ident in idents:
        try:
            pixels[ident] = cjk_weight_pixels(cfont, ident[0], ident[1], "regular")
        except (SourceError, ValueError) as exc:
            unresolved[ident] = str(exc)

    def tag(ident):
        return "%s set=%s" % (cjk_key_text(ident[0]), ident[1])

    # R01 bounds ---------------------------------------------------------------------
    v, n = [], 0
    for ident in cp_idents:
        if ident not in pixels:
            continue
        for w in WEIGHTS:
            n += 1
            bb = bbox(cjk_weight_pixels(cfont, ident[0], ident[1], w))
            if bb is None:
                v.append("%s %s has no ink" % (tag(ident), w))
                continue
            if bb[1] < em_bot or bb[3] > em_top - 1:
                v.append(
                    "%s %s ink rows %d..%d outside em box %d..%d"
                    % (tag(ident), w, bb[1], bb[3], em_bot, em_top - 1)
                )
            if bb[0] < kx[0] or bb[2] > kx[1]:
                v.append(
                    "%s %s ink columns %d..%d outside cell columns %d..%d"
                    % (tag(ident), w, bb[0], bb[2], kx[0], kx[1])
                )
            if bb[1] < ky[0] or bb[3] > ky[1]:
                v.append(
                    "%s %s ink rows %d..%d outside cell rows %d..%d"
                    % (tag(ident), w, bb[1], bb[3], ky[0], ky[1])
                )
    rep.add("R01", "glyph within the em box and the cell", n, v)

    # R04 orphan pixels --------------------------------------------------------------
    v, n, declared = [], 0, 0
    for ident in cp_idents:
        if ident not in pixels:
            continue
        allow = cjk_allowance(cjk, ident[0], ident[1])
        declared += allow
        for w in WEIGHTS:
            n += 1
            px = cjk_weight_pixels(cfont, ident[0], ident[1], w)
            lone = [c for c in components(px) if len(c) == 1]
            if len(lone) > allow:
                v.append(
                    "%s %s has %d single-pixel components, %d declared"
                    % (tag(ident), w, len(lone), allow)
                )
    rep.add(
        "R04",
        "orphan pixels (single-pixel components vs dots=)",
        n,
        v,
        ["deliberate isolated pixels declared across the set: %d" % declared],
    )

    # R05 stems: Regular 1 px, with the declared exemptions ----------------------------
    # A Regular glyph may hold a 2x2 block only if it is declared with a reason: on the
    # list r05-exemptions.txt, or flagged solid in its own record. The lint prints the
    # number of exempted glyphs and the name of each.
    v, n = [], 0
    valid = {}
    first_line = {}
    for e in cjk.exemptions:
        s_attr = e.attrs.get("set", "")
        ident = (e.cp, s_attr)
        entry = "exemption entry U+%04X set=%s (%s:%d)" % (
            e.cp,
            s_attr or "?",
            e.path,
            e.line,
        )
        rec = cjk.glyphs.get(ident)
        problem = None
        if s_attr not in CJK_SETS:
            problem = "names no set (jp, sc or kr)"
        elif e.reason is None or not e.reason.strip():
            problem = "gives no reason"
        elif ident in first_line:
            problem = "repeats the entry of line %d" % first_line[ident]
        elif rec is None:
            problem = "names a glyph that has no record in the set"
        elif rec.attrs.get("same-as"):
            problem = (
                "names a glyph that shares another set's drawing: declare it there"
            )
        elif rec.has_flag("solid"):
            problem = "is also flagged solid in its record: declare it once"
        first_line.setdefault(ident, e.line)
        if problem:
            v.append("%s %s" % (entry, problem))
        else:
            valid[ident] = (e.reason.strip(), "list")
    for ident in cp_idents:
        rec = cjk.glyphs[ident]
        if not rec.has_flag("solid"):
            continue
        reason = rec.attrs.get("reason", "").strip()
        if not reason:
            v.append("%s is flagged solid with no reason" % tag(ident))
        elif rec.attrs.get("same-as"):
            v.append(
                "%s is flagged solid but shares another set's drawing" % tag(ident)
            )
        else:
            valid[ident] = (reason, "solid")
    for ident in cp_idents:
        if ident not in pixels:
            continue
        n += 1
        if cjk.glyphs[ident].attrs.get("same-as"):
            continue  # the owning set's record carries the declaration
        block = first_block(pixels[ident])
        if block is not None and ident not in valid:
            v.append(
                "%s Regular has a 2x2 block at (%d,%d): stem wider than 1 px, and the "
                "glyph is not declared" % ((tag(ident),) + block)
            )
        if block is None and ident in valid:
            v.append(
                "%s is declared exempt (%s) but holds no 2x2 block: remove the "
                "declaration" % (tag(ident), valid[ident][1])
            )
    shown = sorted(valid, key=order_key)
    rep.add(
        "R05",
        "stem width: Regular 1 px (no 2x2), declared exemptions",
        n,
        v,
        ["exempted glyphs: %d%s" % (len(shown), "" if shown else " (none)")]
        + ["exempt %s [%s]: %s" % (tag(i), valid[i][1], valid[i][0]) for i in shown],
    )

    # R06 same-as and recipes resolve ------------------------------------------------
    v, n, used = [], 0, set()
    for ident in idents:
        n += 1
        rec = cjk.glyphs[ident]
        if ident in unresolved:
            v.append("%s: %s" % (tag(ident), unresolved[ident]))
            continue
        same = rec.attrs.get("same-as")
        if same:
            other = cjk.glyphs.get((ident[0], same))
            if ident[1] == "kr" or same == "kr":
                v.append(
                    "%s: a Hangul glyph never shares a drawing (same-as=%s)"
                    % (tag(ident), same)
                )
            elif other is None:
                v.append(
                    "%s: same-as=%s but that set has no such record"
                    % (tag(ident), same)
                )
            elif other.attrs.get("same-as"):
                v.append(
                    "%s: same-as=%s names a record that is itself shared"
                    % (tag(ident), same)
                )
        src = rec.attrs.get("src", "")
        if src.startswith("recipe:"):
            for tok in src[len("recipe:") :].split(","):
                try:
                    used.add((cjk_key(tok, ""), ident[1]))
                except SourceError:
                    pass
    rep.add(
        "R06",
        "every same-as and recipe resolves to drawn glyphs of the face",
        n,
        v,
        [
            "parts (drawings used by recipes, not characters): %d; unused: %d"
            % (
                sum(1 for i in idents if not isinstance(i[0], int)),
                sum(1 for i in idents if not isinstance(i[0], int) and i not in used),
            )
        ],
    )

    # R07 duplicates and placement ---------------------------------------------------
    v = list(cjk.duplicates)
    for ident in idents:
        rec = cjk.glyphs[ident]
        if ident[1] not in CJK_SETS:
            v.append(
                "%s:%d: %s has no valid set= (jp, sc or kr)"
                % (rec.path, rec.line, cjk_key_text(ident[0]))
            )
        elif rec.path != cjk.set_files[ident[1]]:
            v.append(
                "%s:%d: %s is a record of set %s but sits in %s"
                % (rec.path, rec.line, cjk_key_text(ident[0]), ident[1], rec.path)
            )
    rep.add(
        "R07", "no duplicate record, every record in its set's file", len(idents), v
    )

    # R08 Bold is Regular ------------------------------------------------------------
    v, n = [], 0
    for ident in cp_idents:
        if ident not in pixels:
            continue
        n += 1
        if cjk_weight_pixels(cfont, ident[0], ident[1], "regular") != cjk_weight_pixels(
            cfont, ident[0], ident[1], "bold"
        ):
            v.append("%s: the Bold glyph is not the Regular glyph" % tag(ident))
    for where in cjk.refused:
        v.append(
            "%s: refused, because Bold is Regular and has no drawing of its own" % where
        )
    rep.add(
        "R08",
        "Bold is Regular, pixel for pixel (pairs compared)",
        n,
        v,
        ["glyph pairs compared: %d" % n],
    )

    # R09 public-safe scan -----------------------------------------------------------
    v, n = [], 0
    targets = [os.path.join(cjk_dir, "face.txt")]
    targets += [os.path.join(cjk_dir, name) for name in cjk.files]
    log = os.path.join(fonts_dir, "FONTLOG-CJK.txt")
    if os.path.exists(log):
        targets.append(log)
    targets += script_files
    for path in sorted(targets):
        n += 1
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
        for ln, line in enumerate(text.split("\n"), 1):
            for label, pat in UNSAFE:
                if pat.search(line):
                    v.append("%s:%d contains %s" % (os.path.basename(path), ln, label))
    rep.add("R09", "public-safe scan of sources and scripts", n, v)

    # R10 outline fidelity -----------------------------------------------------------
    v, n = [], 0
    for ident in cp_idents:
        if ident not in pixels:
            continue
        for w in WEIGHTS:
            n += 1
            px = cjk_weight_pixels(cfont, ident[0], ident[1], w)
            if fill_from_contours(contours(px)) != px:
                v.append(
                    "%s %s outline does not reproduce the pixels" % (tag(ident), w)
                )
    rep.add("R10", "outline reproduces the pixel grid exactly", n, v)

    # R11 contract constants and the face record -------------------------------------
    v, n = [], 0
    U = mint(m, "units_per_px")
    for key, want in (("em_px", 12), ("units_per_px", 128), ("units_per_em", 1536)):
        n += 1
        if mint(m, key) != want:
            v.append("%s is %s, expected %d" % (key, m[key], want))
    n += 1
    if mint(m, "units_per_em") != mint(m, "em_px") * U:
        v.append("units_per_em is not em_px * units_per_px")
    n += 1
    if mint(m, "line_ascent_px") < em_top or mint(m, "line_descent_px") < -em_bot:
        v.append("line box does not contain the em box")
    for key in FACE_REQUIRED:
        n += 1
        if not face.get(key, "").strip():
            v.append("face.txt does not declare %s" % key)
    for key in sorted(face):
        n += 1
        if key in GRID_KEYS:
            v.append(
                "face.txt restates the grid key %s: it is read from metrics.txt" % key
            )
        if key.startswith("donor") or key.startswith("copyright_prior"):
            v.append("face.txt declares %s: the CJK face declares no donor" % key)
    for kind in ("family", "postscript", "records"):
        n += 1
        values = [face.get("%s_%s" % (kind, s), "") for s in CJK_SETS]
        if len(set(values)) != len(values):
            v.append("face.txt gives two sets the same %s" % kind)
    try:
        notdef = cjk_notdef(m, face)
        bb = bbox(notdef)
        n += 1
        if (
            bb is None
            or bb[0] < kx[0]
            or bb[2] > kx[1]
            or bb[1] < ky[0]
            or bb[3] > ky[1]
        ):
            v.append("the missing-glyph box lies outside the cell")
    except (KeyError, ValueError):
        v.append("face.txt notdef_box_x / notdef_box_rows are not column ranges")
    rep.add("R11", "grid contract constants and the face record", n, v)

    # R14 the donor gate -------------------------------------------------------------
    n, v, donor_cps = provenance_checks(srcs, font, src_dir, fonts_dir)
    info = (
        [
            "code points taken from the donor: %d: %s"
            % (len(donor_cps), spans(donor_cps))
        ]
        if donor_cps
        else []
    )
    gate_n, gate_v, gate_info = donor_gate(srcs, src_dir, fonts_dir, gate)
    rep.add(
        "R14",
        "provenance of merged letterforms and the donor gate",
        n + gate_n,
        v + gate_v,
        info + gate_info,
    )

    # R15 the character map holds Han and Hangul only --------------------------------
    v, n = [], 0
    han, hangul = han_hangul_ranges()
    allowed = {"jp": han, "sc": han, "kr": hangul}
    for ident in cp_idents:
        n += 1
        cp, s = ident
        if s not in allowed:
            continue
        if in_ranges(cp, allowed[s]):
            continue
        if in_ranges(cp, han) or in_ranges(cp, hangul):
            kind = "Han" if in_ranges(cp, han) else "Hangul"
            v.append(
                "U+%04X set=%s is %s: the %s set holds %s only"
                % (cp, s, kind, s, "Hangul" if s == "kr" else "Han")
            )
        else:
            v.append(
                "U+%04X set=%s is neither Han nor Hangul: the CJK character map "
                "holds Han and Hangul only, a space included" % (cp, s)
            )
    disk = 0
    for s in CJK_SETS:
        for w in WEIGHTS:
            try:
                path = os.path.join(gate.out_dir, cjk_file_name(face, s, w))
            except KeyError:
                continue
            if not (gate.ttfs and os.path.exists(path)):
                continue
            from fontTools.ttLib import TTFont

            disk += 1
            with TTFont(path) as built:
                for cp in sorted(built.getBestCmap()):
                    n += 1
                    if not in_ranges(cp, allowed[s]):
                        v.append(
                            "%s: U+%04X is in the character map but is not %s"
                            % (
                                os.path.basename(path),
                                cp,
                                "Hangul" if s == "kr" else "Han",
                            )
                        )
    rep.add(
        "R15",
        "character map holds Han and Hangul only",
        n,
        v,
        ["built CJK fonts whose character map was read: %d" % disk],
    )

    # R16 provenance of every glyph --------------------------------------------------
    v, n = [], 0
    for ident in idents:
        n += 1
        rec = cjk.glyphs[ident]
        t = tag(ident)
        for name, value in sorted(rec.attrs.items()):
            if name in CJK_ATTRS:
                continue
            if name in SOURCE_ATTRS:
                v.append(
                    "%s: %s=%s records a font as the source of the drawing: a glyph "
                    "copied from any font is refused" % (t, name, value)
                )
            else:
                v.append("%s: the attribute %s is not part of a CJK record" % (t, name))
        src = rec.attrs.get("src")
        same = rec.attrs.get("same-as")
        has_rows = any("#" in row for row in rec.rows)
        if src is None:
            v.append("%s: no src= (every glyph names its provenance)" % t)
        elif src == "drawn":
            if not has_rows and not same:
                v.append("%s: src=drawn but the record draws nothing" % t)
        elif src.startswith("recipe:"):
            if not [tok for tok in src[len("recipe:") :].split(",") if tok]:
                v.append("%s: src=recipe: names no glyph" % t)
            if has_rows:
                v.append("%s: a recipe has no rows of its own" % t)
            if same:
                v.append("%s: a recipe cannot also be same-as" % t)
        else:
            kind, _sep, rest = src.partition(":")
            if rest:
                v.append(
                    "%s: provenance src=%s names another font (%s) as the source of "
                    "the drawing: a glyph copied from any font is refused"
                    % (t, src, rest)
                )
            else:
                v.append("%s: provenance src=%s is not drawn or recipe" % (t, src))
        if same and has_rows:
            v.append("%s: a same-as record has no rows of its own" % t)
        if same and src not in (None, "drawn"):
            v.append("%s: same-as needs src=drawn" % t)
        if not isinstance(ident[0], int) and (src != "drawn" or same):
            v.append("%s: a part is a drawing of its own (src=drawn, no same-as)" % t)
    rep.add("R16", "provenance: every glyph is drawn or a recipe of drawn glyphs", n, v)
    return rep


# --------------------------------------------------------------------------
# The CJK face: build and checks of the built fonts
# --------------------------------------------------------------------------


def cjk_glyph_name(cp):
    return "uni%04X" % cp if cp <= 0xFFFF else "u%05X" % cp


def build_cjk_font(srcs, cjk, cfont, set_key, weight, out_path):
    """One font of the CJK face. Both weights are the same drawing, so the two files of
    a family differ in their name records and style flags only."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    m, face = srcs.metrics, cjk.face
    U = mint(m, "units_per_px")
    adv = mint(m, "cell_adv_px")
    cps = cfont.codepoints(set_key)
    order = [".notdef"] + [cjk_glyph_name(cp) for cp in cps]
    glyphs, metrics_ = {}, {}

    def make(px):
        pen = TTGlyphPen(None)
        for loop in contours(px):
            pts = [(x * U, y * U) for x, y in loop]
            pen.moveTo(pts[0])
            for p in pts[1:]:
                pen.lineTo(p)
            pen.closePath()
        bb = bbox(px)
        return pen.glyph(), (adv * U, 0 if bb is None else bb[0] * U)

    glyphs[".notdef"], metrics_[".notdef"] = make(cjk_notdef(m, face))
    cmap = {}
    for cp in cps:
        name = cjk_glyph_name(cp)
        glyphs[name], metrics_[name] = make(
            cjk_weight_pixels(cfont, cp, set_key, weight)
        )
        cmap[cp] = name

    bold = weight == "bold"
    asc, desc = mint(m, "line_ascent_px") * U, mint(m, "line_descent_px") * U
    fb = FontBuilder(mint(m, "units_per_em"), isTTF=True)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics_)
    fb.setupHorizontalHeader(
        ascent=asc, descent=-desc, lineGap=mint(m, "line_gap_px") * U
    )
    fb.setupHead(
        unitsPerEm=mint(m, "units_per_em"),
        fontRevision=float(face["font_revision"]),
        created=epoch_1904(face["created_utc"]),
        modified=epoch_1904(face["modified_utc"]),
        flags=0x0009,
        lowestRecPPEM=mint(m, "em_px"),
        macStyle=1 if bold else 0,
        glyphDataFormat=0,
    )
    fb.setupNameTable(cjk_name_table(m, face, set_key, weight))
    fb.setupOS2(
        version=4,
        usWeightClass=700 if bold else 400,
        usWidthClass=5,
        fsType=0,
        achVendID=m["vendor_id"],
        fsSelection=(0x20 if bold else 0x40) | 0x80,
        sTypoAscender=asc,
        sTypoDescender=-desc,
        sTypoLineGap=mint(m, "line_gap_px") * U,
        usWinAscent=asc,
        usWinDescent=desc,
        sxHeight=mint(m, "x_px") * U,
        sCapHeight=mint(m, "cap_px") * U,
        usDefaultChar=0,
        usBreakChar=32,
        ySubscriptXSize=7 * U,
        ySubscriptYSize=7 * U,
        ySubscriptXOffset=0,
        ySubscriptYOffset=1 * U,
        ySuperscriptXSize=7 * U,
        ySuperscriptYSize=7 * U,
        ySuperscriptXOffset=0,
        ySuperscriptYOffset=4 * U,
        yStrikeoutSize=U,
        yStrikeoutPosition=3 * U,
    )
    fb.setupPost(underlinePosition=-2 * U, underlineThickness=U)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fb.save(out_path)


def build_cjk_all(srcs, cjk, cfont, out_dir):
    """Every font of every set that has a glyph record, as {(set, weight): path}."""
    paths = {}
    for s in CJK_SETS:
        if not cfont.codepoints(s):
            continue
        for w in WEIGHTS:
            p = os.path.join(out_dir, cjk_file_name(cjk.face, s, w))
            build_cjk_font(srcs, cjk, cfont, s, w, p)
            paths[(s, w)] = p
    return paths


def flat_labels(paths):
    """{(set, weight): path} as {"jp-regular": path} for the name scans."""
    return {"%s-%s" % key: p for key, p in sorted(paths.items())}


def bold_identity(paths):
    """Compare the Regular and Bold file of every set: same glyph order, same character
    map, and for every glyph the same outline and the same advance. Returns
    (glyph pairs compared, violations)."""
    from fontTools.ttLib import TTFont

    v, pairs = [], 0
    for s in CJK_SETS:
        if (s, "regular") not in paths or (s, "bold") not in paths:
            continue
        with TTFont(paths[(s, "regular")]) as fr, TTFont(paths[(s, "bold")]) as fb:
            order = fr.getGlyphOrder()
            where = os.path.basename(paths[(s, "bold")])
            if order != fb.getGlyphOrder():
                v.append("%s: the glyph order differs from Regular" % where)
                continue
            if fr.getBestCmap() != fb.getBestCmap():
                v.append("%s: the character map differs from Regular" % where)
            gr, gb = fr["glyf"], fb["glyf"]
            for name in order:
                pairs += 1
                cr, cb = gr[name].getCoordinates(gr), gb[name].getCoordinates(gb)
                same = (
                    list(cr[0]) == list(cb[0])
                    and list(cr[1]) == list(cb[1])
                    and list(cr[2]) == list(cb[2])
                    and fr["hmtx"][name] == fb["hmtx"][name]
                )
                if not same:
                    v.append(
                        "%s: glyph %s is not the Regular glyph, pixel for pixel"
                        % (where, name)
                    )
    return pairs, v


# --------------------------------------------------------------------------
# The freeze manifest of the existing face
# --------------------------------------------------------------------------


def freeze_verify(root, manifest):
    """Compare the existing face with its manifest: every listed file present and equal,
    and no file under fonts-src/nifen-art that the manifest does not list. Returns
    (files compared, violations, info lines)."""
    v, info, listed = [], [], {}
    if not os.path.isfile(manifest):
        v.append("the freeze manifest %s is missing" % os.path.basename(manifest))
        return 0, v, info
    with open(manifest, "rb") as fh:
        text = fh.read().decode("utf-8")
    for number, line in enumerate(text.split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        digest, sep, rel = line.partition("  ")
        if not sep or not re.fullmatch(r"[0-9a-f]{64}", digest) or not rel.strip():
            v.append(
                "%s:%d is not '<sha256>  <path>'" % (os.path.basename(manifest), number)
            )
            continue
        if rel in listed:
            v.append("%s is listed twice" % rel)
        listed[rel] = digest
    n = same = 0
    for rel, digest in sorted(listed.items()):
        path = os.path.join(root, *rel.split("/"))
        if not os.path.isfile(path):
            v.append("%s is listed but missing" % rel)
            continue
        n += 1
        if sha256(path) == digest:
            same += 1
        else:
            v.append("%s differs from the manifest" % rel)
    base = os.path.join(root, "fonts-src", "nifen-art")
    extra = 0
    if os.path.isdir(base):
        for rel in walk_files(base):
            key = "fonts-src/nifen-art/" + rel
            if key not in listed:
                extra += 1
                v.append(
                    "%s is not in the manifest: a file was added to the frozen face"
                    % key
                )
    else:
        v.append("fonts-src/nifen-art is missing")
    if n == 0:
        v.append("the manifest lists no file that exists: nothing was compared")
    info.append(
        "existing face frozen: %d files compared, %d identical, %d missing or "
        "changed, %d not listed" % (n, same, len(listed) - same, extra)
    )
    return n, v, info


def print_freeze(args):
    """Run the freeze comparison and print it. Returns True when it is clean."""
    root = getattr(args, "root", REPO)
    manifest = os.path.join(getattr(args, "cjk_src", DEFAULT_CJK_SRC), FREEZE_NAME)
    n, v, info = freeze_verify(root, manifest)
    for line in info:
        print(line)
    for x in v:
        print("  VIOLATION", x)
    print("freeze check: %d files compared, %d violations" % (n, len(v)))
    return not v and n > 0


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def script_list():
    out = []
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py"):
            out.append(os.path.join(HERE, name))
    return out


def existing_gate(args, ttfs):
    """The donor gate's inputs beyond the existing face's own sources."""
    return Gate(
        getattr(args, "cjk_src", DEFAULT_CJK_SRC),
        getattr(args, "notice", DEFAULT_NOTICE),
        getattr(args, "out", DEFAULT_OUT),
        ttfs,
    )


def built_name_findings(paths, cjk_scope):
    """The donor gate's reading of the name records of fonts this run just built."""
    from fontTools.ttLib import TTFont

    donors, out = set(), []
    for label, path in sorted(paths.items()):
        with TTFont(path) as font:
            for rec in font["name"].names:
                out.extend(
                    credit_findings(
                        "%s name ID %d" % (label, rec.nameID),
                        rec.toUnicode(),
                        cjk_scope,
                        True,
                        donors,
                    )
                )
    return out


def cmd_lint(args):
    if getattr(args, "face", FACE_EXISTING) == FACE_CJK:
        return cmd_lint_cjk(args)
    srcs = parse_sources(args.src)
    font = Font(srcs)
    rep = lint(
        srcs,
        font,
        script_list(),
        args.src,
        getattr(args, "licence_dir", DEFAULT_OUT),
        existing_gate(args, True),
    )
    total = rep.print()
    cps = font.codepoints()
    kinds = {}
    for cp in cps:
        kinds[font.classify(cp)] = kinds.get(font.classify(cp), 0) + 1
    print(
        "glyphs: %d codepoints x 2 weights = %d examined; classes %s"
        % (len(cps), len(cps) * 2, kinds)
    )
    print("lint violations: %d" % total)
    return 1 if rep.failed() else 0


def cmd_lint_cjk(args):
    srcs = parse_sources(args.src)
    font = Font(srcs)
    cjk_src = getattr(args, "cjk_src", DEFAULT_CJK_SRC)
    cjk = parse_cjk_sources(cjk_src)
    cfont = CjkFont(cjk)
    rep = lint_cjk(
        srcs,
        font,
        cjk,
        cfont,
        script_list(),
        args.src,
        cjk_src,
        getattr(args, "licence_dir", DEFAULT_OUT),
        existing_gate(args, True),
    )
    total = rep.print()
    counts = {s: len(cfont.codepoints(s)) for s in CJK_SETS}
    cps = sum(counts.values())
    print(
        "CJK glyphs: %d codepoints x 2 weights = %d examined; sets %s; records %d"
        % (cps, cps * 2, counts, len(cjk.glyphs))
    )
    if not cjk.glyphs:
        print(
            "CJK glyph records: 0. Nothing is drawn yet, so the glyph rules examined "
            "nothing; that does not fail the lint while no record exists."
        )
    print("lint violations: %d" % total)
    return 1 if rep.failed() else 0


def cmd_build(args):
    if getattr(args, "face", FACE_EXISTING) == FACE_CJK:
        return cmd_build_cjk(args)
    srcs = parse_sources(args.src)
    font = Font(srcs)
    rep = lint(
        srcs,
        font,
        script_list(),
        args.src,
        getattr(args, "licence_dir", DEFAULT_OUT),
        existing_gate(args, False),
    )
    if rep.failed():
        rep.print()
        print("build refused: lint failed")
        return 1
    paths = build_all(srcs, font, args.out)
    n, v = name_table_scan(paths)
    v = v + name0_scan(paths, srcs) + built_name_findings(paths, False)
    print("name records scanned: %d, public-safe violations: %d" % (n, len(v)))
    print(
        "name ID 0 records checked for the clause %r: %d"
        % (RFN_CLAUSE, sum(len(name0_records(p)) for p in paths.values()))
    )
    for x in v:
        print("  VIOLATION", x)
    for w in WEIGHTS:
        print(
            "built %s  %d bytes  sha256 %s"
            % (os.path.basename(paths[w]), os.path.getsize(paths[w]), sha256(paths[w]))
        )
    return 1 if v or n == 0 else 0


def cmd_build_cjk(args):
    srcs = parse_sources(args.src)
    font = Font(srcs)
    cjk_src = getattr(args, "cjk_src", DEFAULT_CJK_SRC)
    cjk = parse_cjk_sources(cjk_src)
    cfont = CjkFont(cjk)
    rep = lint_cjk(
        srcs,
        font,
        cjk,
        cfont,
        script_list(),
        args.src,
        cjk_src,
        getattr(args, "licence_dir", DEFAULT_OUT),
        existing_gate(args, False),
    )
    if rep.failed():
        rep.print()
        print("build refused: lint failed")
        return 1
    if not any(cfont.codepoints(s) for s in CJK_SETS):
        print("build refused: the CJK face has no glyph record: nothing to build")
        return 1
    paths = build_cjk_all(srcs, cjk, cfont, args.out)
    flat = flat_labels(paths)
    n, v = name_table_scan(flat)
    v = v + name0_scan(flat, srcs, prior=[]) + built_name_findings(flat, True)
    pairs, bv = bold_identity(paths)
    v = v + bv
    print("name records scanned: %d, public-safe violations: %d" % (n, len(v)))
    print(
        "name ID 0 records checked for the clause %r: %d"
        % (RFN_CLAUSE, sum(len(name0_records(p)) for p in flat.values()))
    )
    print("Bold == Regular: %d glyph pairs compared, %d differ" % (pairs, len(bv)))
    for x in v:
        print("  VIOLATION", x)
    for key in sorted(paths):
        print(
            "built %s  %d bytes  sha256 %s"
            % (
                os.path.basename(paths[key]),
                os.path.getsize(paths[key]),
                sha256(paths[key]),
            )
        )
    return 1 if v or n == 0 or pairs == 0 else 0


def cmd_check(args):
    if getattr(args, "face", FACE_EXISTING) == FACE_CJK:
        return cmd_check_cjk(args)
    srcs = parse_sources(args.src)
    font = Font(srcs)
    if args.tmp:
        os.makedirs(args.tmp, exist_ok=True)
    ok = True
    examined = 0
    with (
        tempfile.TemporaryDirectory(dir=args.tmp) as t1,
        tempfile.TemporaryDirectory(dir=args.tmp) as t2,
    ):
        p1 = build_all(srcs, font, t1)
        srcs2 = parse_sources(args.src)
        p2 = build_all(srcs2, Font(srcs2), t2)
        for w in WEIGHTS:
            a, b = sha256(p1[w]), sha256(p2[w])
            committed = os.path.join(args.out, FILE_NAMES[w])
            c = sha256(committed) if os.path.exists(committed) else "(missing)"
            examined += 1
            same = a == b == c
            ok = ok and same
            print("%-20s build1 %s" % (FILE_NAMES[w], a))
            print("%-20s build2 %s" % ("", b))
            print(
                "%-20s disk   %s   %s" % ("", c, "IDENTICAL" if same else "DIFFERENT")
            )
    print(
        "--check: %d/%d weights byte-identical (two fresh rebuilds and the files on "
        "disk)" % (examined if ok else 0, examined)
    )
    frozen = print_freeze(args)
    return 0 if ok and examined and frozen else 1


def cmd_check_cjk(args):
    srcs = parse_sources(args.src)
    cjk_src = getattr(args, "cjk_src", DEFAULT_CJK_SRC)
    cjk = parse_cjk_sources(cjk_src)
    cfont = CjkFont(cjk)
    tmp = getattr(args, "tmp", None)
    if tmp:
        os.makedirs(tmp, exist_ok=True)
    ok, examined = True, 0
    on_disk = {}
    if not any(cfont.codepoints(s) for s in CJK_SETS):
        print(
            "--check: the CJK face has no glyph record: no font to rebuild or compare"
        )
        ok = False
    else:
        with (
            tempfile.TemporaryDirectory(dir=tmp) as t1,
            tempfile.TemporaryDirectory(dir=tmp) as t2,
        ):
            p1 = build_cjk_all(srcs, cjk, cfont, t1)
            srcs2 = parse_sources(args.src)
            cjk2 = parse_cjk_sources(cjk_src)
            p2 = build_cjk_all(srcs2, cjk2, CjkFont(cjk2), t2)
            for key in sorted(p1):
                name = os.path.basename(p1[key])
                a, b = sha256(p1[key]), sha256(p2[key])
                committed = os.path.join(args.out, name)
                c = sha256(committed) if os.path.exists(committed) else "(missing)"
                if c != "(missing)":
                    on_disk[key] = committed
                examined += 1
                same = a == b == c
                ok = ok and same
                print("%-24s build1 %s" % (name, a))
                print("%-24s build2 %s" % ("", b))
                print(
                    "%-24s disk   %s   %s"
                    % ("", c, "IDENTICAL" if same else "DIFFERENT")
                )
        print(
            "--check: %d/%d CJK files byte-identical (two fresh rebuilds and the files "
            "on disk)" % (examined if ok else 0, examined)
        )
        pairs, bv = bold_identity(on_disk)
        for x in bv:
            print("  VIOLATION", x)
        print("Bold == Regular: %d glyph pairs compared, %d differ" % (pairs, len(bv)))
        ok = ok and not bv and pairs > 0
    frozen = print_freeze(args)
    return 0 if ok and frozen and examined else 1


def cmd_verify_freeze(args):
    return 0 if print_freeze(args) else 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--face",
        choices=(FACE_EXISTING, FACE_CJK),
        default=FACE_EXISTING,
        help="which face to lint, build or check (default: nifen-art)",
    )
    ap.add_argument(
        "--src",
        default=DEFAULT_SRC,
        help="glyph sources folder of the existing face; the CJK face reads its grid "
        "and donor facts from the metrics.txt in it (default: fonts-src/nifen-art)",
    )
    ap.add_argument(
        "--cjk-src",
        default=DEFAULT_CJK_SRC,
        help="glyph sources folder of the CJK face (default: fonts-src/nifen-art-cjk)",
    )
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="built fonts folder (default: pixelart_creator/fonts)",
    )
    ap.add_argument(
        "--licence-dir",
        default=DEFAULT_OUT,
        help="folder with OFL.txt, FONTLOG.txt and FONTLOG-CJK.txt that the provenance "
        "rule and the donor gate read (default: pixelart_creator/fonts)",
    )
    ap.add_argument(
        "--notice",
        default=DEFAULT_NOTICE,
        help="the product's notice file, scanned by the donor gate (default: NOTICE)",
    )
    ap.add_argument(
        "--root",
        default=REPO,
        help="repository root that the freeze manifest's paths are relative to",
    )
    ap.add_argument(
        "--tmp",
        default=None,
        help="scratch folder for --check (default: the system temporary folder)",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--lint", action="store_true")
    g.add_argument("--build", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument(
        "--verify-freeze",
        action="store_true",
        help="compare the existing face with its freeze manifest",
    )
    args = ap.parse_args()
    make_console_safe()
    try:
        if args.lint:
            return cmd_lint(args)
        if args.build:
            return cmd_build(args)
        if args.verify_freeze:
            return cmd_verify_freeze(args)
        return cmd_check(args)
    except SourceError as exc:
        print("source error:", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
