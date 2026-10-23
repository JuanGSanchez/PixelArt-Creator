"""Nifen Art build: source lint, deterministic TTF build, byte-identity check.

Build-time only; requires fontTools (4.63.0 is the version the committed
fonts were built and proved with). Writes NifenArt-Regular.ttf and
NifenArt-Bold.ttf from the text-grid sources. Run from the repository root:

    python scripts/font/build_nifen_art.py --lint
    python scripts/font/build_nifen_art.py --build
    python scripts/font/build_nifen_art.py --check

Defaults are repository-relative: sources in fonts-src/nifen-art, built fonts
in pixelart_creator/fonts (the --check comparison target as well).

Every command exits non-zero on any violation, on any mismatch, or when it
examined nothing.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import re
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_SRC = os.path.join(REPO, "fonts-src", "nifen-art")
DEFAULT_OUT = os.path.join(REPO, "pixelart_creator", "fonts")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from nifen_src import (  # noqa: E402
    Font,
    SourceError,
    bbox,
    components,
    contours,
    counters,
    fill_from_contours,
    lost_counters,
    make_console_safe,
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
        if any(e == 0 for _c, _t, e, _v, _i in self.rules):
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


def lint(srcs, font: Font, script_files, src_dir, fonts_dir=None):
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

    # R14 provenance of merged letterforms ---------------------------------------------
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

    def spans(cps):
        out, cps = [], sorted(set(cps))
        i = 0
        while i < len(cps):
            j = i
            while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1:
                j += 1
            out.append(
                "U+%04X" % cps[i] if i == j else "U+%04X-U+%04X" % (cps[i], cps[j])
            )
            i = j + 1
        return ", ".join(out)

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
    rep.add(
        "R14",
        "provenance of merged letterforms (donor files and licence files)",
        n,
        v,
        (
            [
                "code points taken from the donor: %d: %s"
                % (len(donor_cps), spans(donor_cps))
            ]
            if donor_cps
            else []
        ),
    )
    return rep


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


def name0_scan(paths, srcs):
    """The copyright record (name ID 0) of every built font states each prior copyright
    line of the metrics, before the typeface's line (first record); and, at EVERY
    platform record, the typeface's own line ends with the Reserved Font Name clause
    and the clause is not attached to a prior line. A font with no name ID 0 record is
    a violation. The clause check of a weight runs once the prior lines are in order,
    so each weight reports its first defect."""
    from fontTools.ttLib import TTFont

    m = srcs.metrics
    prior = [
        m[k] for k in sorted(m) if k.startswith("copyright_prior_line") and m[k].strip()
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
# Commands
# --------------------------------------------------------------------------


def script_list():
    out = []
    for name in sorted(os.listdir(HERE)):
        if name.endswith(".py"):
            out.append(os.path.join(HERE, name))
    return out


def cmd_lint(args):
    srcs = parse_sources(args.src)
    font = Font(srcs)
    rep = lint(
        srcs, font, script_list(), args.src, getattr(args, "licence_dir", DEFAULT_OUT)
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


def cmd_build(args):
    srcs = parse_sources(args.src)
    font = Font(srcs)
    rep = lint(
        srcs, font, script_list(), args.src, getattr(args, "licence_dir", DEFAULT_OUT)
    )
    if rep.failed():
        rep.print()
        print("build refused: lint failed")
        return 1
    paths = build_all(srcs, font, args.out)
    n, v = name_table_scan(paths)
    v = v + name0_scan(paths, srcs)
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


def cmd_check(args):
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
    return 0 if ok and examined else 1


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--src",
        default=DEFAULT_SRC,
        help="glyph sources folder (default: fonts-src/nifen-art)",
    )
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="built fonts folder (default: pixelart_creator/fonts)",
    )
    ap.add_argument(
        "--licence-dir",
        default=DEFAULT_OUT,
        help="folder with OFL.txt and FONTLOG.txt that the provenance rule reads "
        "(default: pixelart_creator/fonts)",
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
    args = ap.parse_args()
    make_console_safe()
    try:
        if args.lint:
            return cmd_lint(args)
        if args.build:
            return cmd_build(args)
        return cmd_check(args)
    except SourceError as exc:
        print("source error:", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
