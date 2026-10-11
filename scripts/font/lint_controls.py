"""Injected-defect controls for the source lint.

Each control copies the glyph sources, applies one edit that breaks a rule,
runs the lint on the copy and requires a non-zero exit and the expected rule
flagged. A lint that cannot fail proves nothing; this shows that it can.

A control whose expected rule is NAME0 exercises the build's name ID 0 check instead:
the copy is built in process (Regular only), the listed damage is done to name ID 0 of
the built file (an edit whose file is "name ID 0" or "name ID 0 (Macintosh)"; any other
file is a source edit made before the build), and the check must report the expected
text. The undamaged build must be clean first, so a quiet check cannot pass.

    python scripts/font/lint_controls.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
PY = sys.executable
REPO = os.path.dirname(os.path.dirname(HERE))
SOURCES = os.path.join(REPO, "fonts-src", "nifen-art")
FONTS = os.path.join(REPO, "pixelart_creator", "fonts")
SCRATCH = tempfile.gettempdir()


def show_child_output(r, tail=12):
    """Print what the lint child said when a control is not caught (never silent)."""
    err = r.stderr.strip()
    print("    child exit code: %d" % r.returncode)
    print("    child stderr: %s" % ("" if err else "(empty)"))
    for ln in err.splitlines():
        print("      | " + ln.encode("ascii", "backslashreplace").decode("ascii"))
    lines = r.stdout.rstrip().splitlines()
    print(
        "    child stdout, last %d of %d lines:" % (min(tail, len(lines)), len(lines))
    )
    for ln in lines[-tail:]:
        print("      | " + ln.encode("ascii", "backslashreplace").decode("ascii"))


_PRISTINE = []


def pristine_findings(build):
    """What the name ID 0 check says about the untouched sources, built once per run."""
    if not _PRISTINE:
        d = tempfile.mkdtemp(dir=SCRATCH)
        try:
            srcs = build.parse_sources(SOURCES)
            p = os.path.join(d, "NifenArt-Regular.ttf")
            build.build_font(srcs, build.Font(srcs), "regular", p)
            _PRISTINE.append(build.name0_scan({"regular": p}, srcs))
        finally:
            shutil.rmtree(d, ignore_errors=True)
    return _PRISTINE[0]


def run_name0(name, edits, expect_text):
    """Build a copy, damage name ID 0, require the build's check to report it."""
    sys.path.insert(0, HERE)
    import build_nifen_art as build
    from fontTools.ttLib import TTFont

    d = tempfile.mkdtemp(dir=SCRATCH)
    try:
        dst = os.path.join(d, "src")
        shutil.copytree(SOURCES, dst)
        damage = []
        for fname, old, new in edits:
            if fname.startswith("name ID 0"):
                damage.append((fname, old, new))
                continue
            path = os.path.join(dst, fname)
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                print("%-44s skipped (record not in the sources)" % name)
                return None
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        srcs = build.parse_sources(dst)
        out = os.path.join(d, "out")
        paths = {"regular": os.path.join(out, "NifenArt-Regular.ttf")}
        build.build_font(srcs, build.Font(srcs), "regular", paths["regular"])
        clean = pristine_findings(build)
        if clean:
            print("%-44s the undamaged build is not clean: %s" % (name, clean))
            return False
        with TTFont(paths["regular"]) as font:
            hit_records = 0
            for rec in list(font["name"].names):
                if rec.nameID != 0:
                    continue
                text = rec.toUnicode()
                for fname, old, new in damage:
                    if fname.endswith("(Macintosh)") and rec.platformID != 1:
                        continue
                    if old not in text:
                        print("%-44s skipped (text not in name ID 0)" % name)
                        return None
                    text = text.replace(old, new, 1)
                if text != rec.toUnicode():
                    hit_records += 1
                    font["name"].setName(
                        text, 0, rec.platformID, rec.platEncID, rec.langID
                    )
            font.save(paths["regular"])
        found = build.name0_scan(paths, srcs)
        hit = [ln for ln in found if expect_text in ln]
        print(
            "%-44s %d violation(s) over %d damaged record(s), %r reported: %s"
            % (name, len(found), hit_records, expect_text, "YES" if hit else "NO")
        )
        if not hit:
            for ln in found:
                print(
                    "      | " + ln.encode("ascii", "backslashreplace").decode("ascii")
                )
        return bool(hit)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run(name, edits, expect_rule, expect_text=None, licence_edits=()):
    if expect_rule == "NAME0":
        return run_name0(name, edits, expect_text)
    d = tempfile.mkdtemp(dir=SCRATCH)
    try:
        dst = os.path.join(d, "src")
        shutil.copytree(SOURCES, dst)
        fonts = os.path.join(d, "fonts")
        os.makedirs(fonts)
        for fname in ("OFL.txt", "FONTLOG.txt"):
            shutil.copy(os.path.join(FONTS, fname), os.path.join(fonts, fname))
        for fname, old, new in licence_edits:
            path = os.path.join(fonts, fname)
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                print("%-44s skipped (text not in the licence files)" % name)
                return None
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        for fname, old, new in edits:
            path = os.path.join(dst, fname)
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                # the edit targets a record that is not in the sources
                print("%-44s skipped (record not in the sources)" % name)
                return None
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        r = subprocess.run(
            [
                PY,
                os.path.join(HERE, "build_nifen_art.py"),
                "--lint",
                "--src",
                dst,
                "--licence-dir",
                fonts,
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=dict(
                os.environ,
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONIOENCODING="utf-8",
                PYTHONUTF8="1",
            ),
        )
        hit = [
            ln
            for ln in r.stdout.split("\n")
            if ln.startswith(expect_rule) and "violations   0" not in ln
        ]
        if expect_text is not None:
            hit = [
                ln
                for ln in r.stdout.split(chr(10))
                if expect_text in ln and "VIOLATION" in ln
            ]
        if expect_rule == "source error":
            hit = [ln for ln in r.stdout.split("\n") if ln.startswith("source error")]
        print(
            "%-44s exit %d  expected rule %s flagged: %s"
            % (name, r.returncode, expect_rule, "YES" if hit else "NO")
        )
        caught = r.returncode != 0 and bool(hit)
        if not caught or r.stderr.strip():
            show_child_output(r)
        return caught
    finally:
        shutil.rmtree(d, ignore_errors=True)


CONTROLS = [
    (
        "2x2 block in Regular H",
        [
            (
                "latin-basic.txt",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n##..#\n#####",
            )
        ],
        "R05",
    ),
    (
        "orphan pixel added to o",
        [
            (
                "latin-basic.txt",
                "glyph U+006F adv=6 top=5 ext=0..5\n.###.",
                "glyph U+006F adv=6 top=7 ext=0..7\n#....\n.....\n.###.",
            )
        ],
        "R04",
    ),
    (
        "Bold overlay for Omega removed",
        [("bold-overlays.txt", "bold U+03A9", "bold U+03A8")],
        "R08",
    ),
    (
        "wrong advance on A",
        [("latin-basic.txt", "glyph U+0041 adv=6", "glyph U+0041 adv=7")],
        "R03",
    ),
    (
        "height wrong (H lacks a row)",
        [
            (
                "latin-basic.txt",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####",
                "glyph U+0048 adv=6 top=6 ext=0..7\n#...#\n#...#\n#...#\n#####",
            )
        ],
        "R02",
    ),
    (
        "capital X drawn 8 rows (ascender height, not cap height)",
        [
            (
                "latin-basic.txt",
                "glyph U+0058 adv=6 top=7 ext=0..7\n#...#\n#...#\n.#.#.",
                "glyph U+0058 adv=6 top=8 ext=0..8\n#...#\n#...#\n#...#\n.#.#.",
            )
        ],
        "R02",
        "U+0058 capital ext top 8",
    ),
    (
        "capital drawn with a free extent but not an accented form",
        [
            (
                "latin-basic.txt",
                "glyph U+0058 adv=6 top=7 ext=0..7",
                "glyph U+0058 adv=6 top=7 ext=free",
            )
        ],
        "R02",
        "U+0058 capital declares ext=free",
    ),
    (
        "accented capital I diaeresis drawn 8 rows (gap row filled)",
        [
            (
                "latin1.txt",
                "glyph U+00CF adv=5 top=9 ext=free dots=2 tab\n#.#\n...\n###\n.#.",
                "glyph U+00CF adv=5 top=9 ext=free dots=2 tab\n#.#\n###\n.#.\n.#.",
            )
        ],
        "R02",
        "U+00CF accented capital body",
    ),
    (
        "forbidden token in a comment",
        [("greek.txt", "# Greek block.", "# Greek block, drawn by an A" + "I model.")],
        "R09",
    ),
    (
        "duplicate codepoint",
        [("symbols.txt", "glyph U+00D7 adv=6", "glyph U+0041 adv=6")],
        "R07",
    ),
    (
        "recipe base missing",
        [("recipes.txt", "recipe U+00E1 = mark U+0061", "recipe U+00E1 = mark U+E000")],
        "source error",
    ),
    (
        "ink outside the em box",
        [
            (
                "latin-basic.txt",
                "glyph U+0045 adv=6 top=7 ext=0..7",
                "glyph U+0045 adv=6 top=12 ext=0..7",
            )
        ],
        "R01",
    ),
    (
        "Bold overlay of @ removed (eye fills in)",
        [
            (
                "bold-overlays.txt",
                "bold U+0040",
                "bold U+0024 adv=7 top=7 ext=free\n..#..\n\nbold U+3042",
            )
        ],
        "R08",
    ),
    (
        "joined mark no longer touches (cedilla lowered)",
        [
            (
                "recipes.txt",
                "recipe U+00C7 = mark U+0043 cedilla join=1",
                "recipe U+00C7 = mark U+0043 cedilla join=1 rise=-1",
            )
        ],
        "R06",
    ),
    (
        "accent sunk into its letter (acute rise=-2)",
        [
            (
                "recipes.txt",
                "recipe U+00E1 = mark U+0061 acute.low",
                "recipe U+00E1 = mark U+0061 acute.low rise=-2",
            )
        ],
        "R06",
    ),
    (
        "space (and its alias) with the wrong width",
        [("latin-basic.txt", "glyph U+0020 adv=3", "glyph U+0020 adv=4")],
        "R03",
        "U+00A0 blank advance",
    ),
    (
        "ogonek no longer touches its letter (align removed)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0104 = mark U+0041 ogonek align=right join=1",
                "recipe U+0104 = mark U+0041 ogonek join=1",
            )
        ],
        "R06",
    ),
    (
        "ligature Bold parts fuse (gap removed from IJ)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0132 = cat U+0049 U+004A gap=1",
                "recipe U+0132 = cat U+0049 U+004A",
            )
        ],
        "R08",
    ),
    (
        "macron sunk into its capital (rise=-3)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+0100 = mark U+0041 macron.cap",
                "recipe U+0100 = mark U+0041 macron.cap rise=-3",
            )
        ],
        "R06",
    ),
    (
        "declared join but the acute floats (l acute dx=3)",
        [
            (
                "recipes-ext-a.txt",
                "recipe U+013A = mark U+006C acute.low rise=2 dx=1 join=1",
                "recipe U+013A = mark U+006C acute.low rise=2 dx=3 join=1",
            )
        ],
        "R06",
    ),
    (
        "Bold overlay of U ring removed (cup closes)",
        [("bold-overlays.txt", "bold U+016E", "bold U+0176")],
        "R08",
        "U+016E derived Bold",
    ),
    (
        "tick moved against the stem (l tick, Bold fuses)",
        [
            (
                "latin-ext-a.txt",
                "glyph U+013E adv=5 top=8 ext=0..8\n#..#\n#..#",
                "glyph U+013E adv=4 top=8 ext=0..8\n#.#.\n#.#.",
            )
        ],
        "R08",
        "U+013E derived Bold",
    ),
    (
        "wrong advance on L with stroke",
        [("latin-ext-a.txt", "glyph U+0141 adv=6", "glyph U+0141 adv=7")],
        "R03",
    ),
    (
        "solid flag removed from the black circle (2x2 blocks)",
        [
            (
                "symbols.txt",
                "glyph U+25CF adv=7 top=6 ext=free solid",
                "glyph U+25CF adv=7 top=6 ext=free",
            )
        ],
        "R05",
    ),
    (
        "orphan pixel in the euro sign",
        [("symbols.txt", "###...\n.#....\n###...", "###...\n.#...#\n###...")],
        "R04",
    ),
    (
        "black star with the wrong advance",
        [("symbols.txt", "glyph U+2605 adv=8", "glyph U+2605 adv=7")],
        "R03",
    ),
    (
        "alias to a code point with no drawing",
        [("aliases.txt", "alias U+2212 = U+2013", "alias U+2212 = U+E000")],
        "source error",
    ),
    (
        "double acute too narrow (Bold strokes touch)",
        [
            (
                "marks.txt",
                "mark doubleacute.low attach=2 top=8\n.#...#\n#...#.",
                "mark doubleacute.low attach=2 top=8\n.#..#\n#..#.",
            )
        ],
        "R08",
        "mark doubleacute.low derived Bold",
    ),
    (
        "comma below on K loses its Bold overlay",
        [("bold-overlays.txt", "bold U+0136", "bold U+0176")],
        "R08",
        "U+0136 derived Bold",
    ),
    (
        "thin space with the wrong advance",
        [("latin-basic.txt", "glyph U+2009 adv=2", "glyph U+2009 adv=3")],
        "R03",
        "U+2009 blank advance",
    ),
    (
        "Djerv leg shortened (Bold closes the counter)",
        [
            (
                "cyrillic.txt",
                "glyph U+0402 adv=6 top=7 ext=-2..7\n#####\n.#...\n.#...\n.###.\n"
                ".#..#\n.#..#\n.#..#\n....#\n...#.",
                "glyph U+0402 adv=6 top=7 ext=-1..7\n#####\n.#...\n.#...\n.###.\n"
                ".#..#\n.#..#\n.#..#\n...#.",
            )
        ],
        "R08",
        "U+0402 derived Bold",
    ),
    (
        "alias of the middle dot loses the tab flag",
        [
            (
                "latin1.txt",
                "glyph U+00B7 adv=3 top=4 ext=free dots=1 tab",
                "glyph U+00B7 adv=3 top=4 ext=free dots=1",
            )
        ],
        "R03",
        "U+0387 Regular left sidebearing",
    ),
    (
        "numero sign parts fuse in Bold (gap removed)",
        [
            (
                "recipes-b5.txt",
                "recipe U+2116 = cat U+004E U+00BA gap=1",
                "recipe U+2116 = cat U+004E U+00BA",
            )
        ],
        "R08",
        "U+2116 derived Bold",
    ),
    (
        "orphan pixel in Greek capital Gamma",
        [
            (
                "greek.txt",
                "glyph U+0393 adv=6 top=7 ext=0..7\n#####\n#....\n#....",
                "glyph U+0393 adv=6 top=7 ext=0..7\n#####\n#....\n#..#.",
            )
        ],
        "R04",
    ),
    (
        "ideographic space with the wrong advance",
        [
            (
                "cjk-fullwidth.txt",
                "glyph U+3000 adv=12 top=0 x=0",
                "glyph U+3000 adv=11 top=0 x=0",
            )
        ],
        "R03",
        "U+3000 blank advance",
    ),
    (
        "hiragana i shifted out of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9",
                "glyph U+3044 adv=12 x=4 cell=full ext=free top=9",
            )
        ],
        "R01",
        "U+3044",
    ),
    (
        "hiragana i drawn 12 columns wide (the cell takes 11)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n"
                "#.......#..\n#.......#..\n#........#.\n#........#.\n#........#.\n"
                "#.........#\n",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n"
                "#.......#...\n#.......#...\n#........#..\n#........#..\n#........#..\n"
                "#.........##\n",
            )
        ],
        "R01",
        "U+3044 regular kana ink columns 0..11",
    ),
    (
        "katakana e shifted two columns right (ink to column 12)",
        [
            (
                "katakana.txt",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8",
                "glyph U+30A8 adv=12 x=3 cell=full ext=free top=8",
            )
        ],
        "R01",
        "U+30A8 regular kana ink columns",
    ),
    (
        "half-width H with its advance cut to 4 (ink past the advance)",
        [("latin-basic.txt", "glyph U+0048 adv=6", "glyph U+0048 adv=4")],
        "R01",
        "U+0048 regular ink columns",
    ),
    (
        "orphan pixel in hiragana i",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n#.......#..\n"
                "#.......#..",
                "glyph U+3044 adv=12 x=0 cell=full ext=free top=9\n#.......#.#\n"
                "#.......#..",
            )
        ],
        "R04",
        "U+3044",
    ),
    (
        "2x2 block in katakana e",
        [
            (
                "katakana.txt",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8\n..######..\n"
                ".....#....\n.....#....\n",
                "glyph U+30A8 adv=12 x=1 cell=full ext=free top=8\n..######..\n"
                "....##....\n....##....\n",
            )
        ],
        "R05",
        "U+30A8",
    ),
    (
        "voiced mark touches its base (trim removed from ZE)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30BC = overlay U+30BB U+309B trim=1",
                "recipe U+30BC = overlay U+30BB U+309B",
            )
        ],
        "R06",
        "U+30BC",
    ),
    (
        "trim cut undeclared (GU loses cut=1)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30B0 = overlay U+30AF U+309B trim=1 cut=1",
                "recipe U+30B0 = overlay U+30AF U+309B trim=1",
            )
        ],
        "R06",
        "U+30B0",
    ),
    (
        "cut declared but not needed (GE)",
        [
            (
                "recipes-b6.txt",
                "recipe U+30B2 = overlay U+30B1 U+309B trim=1",
                "recipe U+30B2 = overlay U+30B1 U+309B trim=1 cut=1",
            )
        ],
        "R06",
        "U+30B2 declares cut",
    ),
    (
        "trim limit exceeded (limit 2 pixels)",
        [("metrics.txt", "trim_max_px = 20", "trim_max_px = 2")],
        "R06",
        "trim removes",
    ),
    (
        "Bold overlay of small hiragana a removed",
        [("bold-overlays-ark-pixel.txt", "bold U+3041 ", "bold U+3042 ")],
        "R08",
        "U+3041 derived Bold",
    ),
    (
        "Bold overlay of the voiced kana pu removed",
        [("bold-overlays-ark-pixel.txt", "bold U+3077 ", "bold U+3076 ")],
        "R08",
        "U+3077 derived Bold",
    ),
    (
        "alias of the full-width tilde to nothing",
        [("aliases.txt", "alias U+FF5E = U+301C", "alias U+FF5E = U+E000")],
        "source error",
    ),
    (
        "small ya floats above the bottom row",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=9",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small ya moved to the right half of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3083 adv=12 x=3 cell=full ext=free top=8",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small a moved two pixels off the centre of the cell",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3041 adv=12 x=2 cell=full ext=free top=8",
            )
        ],
        "R12",
        "U+3041 regular small kana is not centred",
    ),
    (
        "small a drawn 10 rows tall (the limit is 9)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=9\n....#......\n",
            )
        ],
        "R12",
        "U+3041 regular small kana is 10 rows tall",
    ),
    (
        "small a drawn 10 columns wide (the limit is 9)",
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n"
                "....#......\n..#######..\n",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=8\n"
                "....#......\n..#########\n",
            )
        ],
        "R12",
        "U+3041 regular small kana is 10 columns wide",
    ),
    (
        "base of a composed voiced katakana touches the mark (GA)",
        [
            (
                "kana.txt",
                "glyph U+30AB adv=12 top=8 x=1 cell=full ext=free"
                "\n...#......\n.########.",
                "glyph U+30AB adv=12 top=8 x=1 cell=full ext=free"
                "\n...#....#.\n.########.",
            )
        ],
        "R13",
        "U+30AC regular: 1 pixel",
    ),
    (
        "donor copyright line missing from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "# Copyright (c) 2021, TakWolf (https://takwolf.com).\n",
                "",
            )
        ],
        "R14",
        "header does not state the donor copyright line",
    ),
    (
        "donor name removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "adapted from Ark Pixel Font, 12 px,",
                "adapted from a donor font, 12 px,",
            ),
            (
                "hiragana-ark-pixel.txt",
                "# Ark Pixel Font is licensed",
                "# The donor font is licensed",
            ),
        ],
        "R14",
        "header does not state the donor name",
    ),
    (
        "donor version removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "version 2026.09.25 (https",
                "version (https",
            )
        ],
        "R14",
        "header does not state the donor version",
    ),
    (
        "donor version altered in the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "version 2026.09.25 (https",
                "version 2026.09.24 (https",
            )
        ],
        "R14",
        "header does not state the donor version",
    ),
    (
        "donor licence removed from the header of the donor file",
        [
            (
                "hiragana-ark-pixel.txt",
                "licensed under the SIL Open Font License, Version 1.1 and declares",
                "licensed under an open licence and declares",
            )
        ],
        "R14",
        "header does not state the donor licence",
    ),
    (
        "donor name removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "adapted from Ark Pixel Font 12 px",
                "adapted from a donor font 12 px",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor name",
    ),
    (
        "donor version removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "version 2026.09.25; https",
                "version; https",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor version",
    ),
    (
        "donor version altered in the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "version 2026.09.25; https",
                "version 2026.09.24; https",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor version",
    ),
    (
        "donor licence removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "SIL Open Font License, Version 1.1,",
                "an open licence,",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor licence",
    ),
    (
        "donor copyright line removed from the header of the Bold correction file",
        [
            (
                "bold-overlays-ark-pixel.txt",
                "Copyright (c) 2021, TakWolf (https://takwolf.com); ",
                "",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt: the header does not state the donor copyright",
    ),
    (
        "Bold correction file left out of the derived-file list",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = hiragana-ark-pixel.txt",
            )
        ],
        "R14",
        "bold-overlays-ark-pixel.txt mentions the donor (Ark Pixel Font) but is not",
    ),
    (
        "an unlisted source file that mentions the donor",
        [
            (
                "cyrillic.txt",
                "# Cyrillic block. ",
                "# Cyrillic block, a few shapes after Ark Pixel Font. ",
            )
        ],
        "R14",
        "cyrillic.txt mentions the donor (Ark Pixel Font) but is not listed",
    ),
    (
        "an unlisted source file that mentions the donor across a line break",
        [
            (
                "cyrillic.txt",
                "# Cyrillic block. ",
                "# Cyrillic block, a few shapes after Ark Pixel\n# font. ",
            )
        ],
        "R14",
        "cyrillic.txt mentions the donor (Ark Pixel Font) but is not listed",
    ),
    (
        "glyph donor file left out of the derived-file list",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = bold-overlays-ark-pixel.txt",
            )
        ],
        "R14",
        "donor file hiragana-ark-pixel.txt is not listed in donor_derived_files",
    ),
    (
        "derived file named in the metrics is not among the sources",
        [
            (
                "metrics.txt",
                "donor_derived_files = hiragana-ark-pixel.txt "
                "bold-overlays-ark-pixel.txt",
                "donor_derived_files = hiragana-ark-pixel.txt bold-overlays-ark.txt",
            )
        ],
        "R14",
        "donor-derived file bold-overlays-ark.txt is not among the sources",
    ),
    (
        "donor file named in the metrics is not among the sources",
        [
            (
                "metrics.txt",
                "donor_files = hiragana-ark-pixel.txt",
                "donor_files = hiragana-ark.txt",
            )
        ],
        "R14",
        "is not among the sources",
    ),
    (
        "prior copyright line removed from the metrics (name ID 0 would lose it)",
        [
            (
                "metrics.txt",
                "copyright_prior_line_1 = Copyright (c) 2021, TakWolf "
                "(https://takwolf.com).",
                "copyright_prior_line_1 =",
            )
        ],
        "R14",
        "declared together",
    ),
    (
        "a donor letter also composed by a recipe",
        [
            (
                "recipes.txt",
                "recipe U+30AC = overlay U+30AB U+309B ",
                "recipe U+3042 = overlay U+3044 U+309B trim=1"
                "\nrecipe U+30AC = overlay U+30AB U+309B ",
            )
        ],
        "R14",
        "U+3042 is both a donor drawing and a recipe",
    ),
    (
        "donor copyright line missing from the licence file",
        [],
        "R14",
        "OFL.txt does not state",
        [("OFL.txt", "Copyright (c) 2021, TakWolf (https://takwolf.com).\n", "")],
    ),
    (
        "donor code points not named in the change log",
        [],
        "R14",
        "FONTLOG.txt does not state",
        [("FONTLOG.txt", "Code points adapted from", "Code points taken from")],
    ),
    (
        "gap overlay of r wider than the Bold box",
        [
            (
                "bold-overlays-b7.txt",
                "##.##\n###..\n##...\n##...\n##...",
                "##.###\n###...\n##....\n##....\n##....",
            )
        ],
        "R03",
        "U+0072 Bold right sidebearing",
    ),
    (
        "gap overlay of m with a one-pixel run",
        [("bold-overlays-b7.txt", "##.##.##\n########", "##.##.#.\n########")],
        "R05",
        "U+006D",
    ),
    (
        "gap overlay of Cyrillic Ya loses its leg join",
        [
            (
                "bold-overlays-b7.txt",
                ".#####\n.##.##\n##..##\n##..##\n\n# Cyrillic ya (lowercase)",
                ".#####\n......\n##..##\n##..##\n\n# Cyrillic ya (lowercase)",
            )
        ],
        "R08",
        "U+042F",
    ),
    (
        "needless Bold overlay on H",
        [
            (
                "bold-overlays.txt",
                "bold U+0023",
                "bold U+0048 adv=7 top=7 ext=free\n##..##\n##..##\n##..##\n######\n"
                "##..##\n##..##\n##..##\n\nbold U+0023",
            )
        ],
        "R08",
    ),
    (
        "licence file: clause missing from the typeface's line",
        [],
        "R14",
        "does not end with",
        [("OFL.txt", ' with Reserved Font Name "Nifen Art".', "")],
    ),
    (
        "licence file: clause altered on the typeface's line",
        [],
        "R14",
        "does not end with",
        [("OFL.txt", 'Reserved Font Name "Nifen Art".', 'Reserved Font Name "Nifen".')],
    ),
    (
        "licence file: clause moved to the donor line",
        [],
        "R14",
        "carries 'Reserved Font Name'",
        [
            ("OFL.txt", ' with Reserved Font Name "Nifen Art".', ""),
            (
                "OFL.txt",
                "(https://takwolf.com).\n",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".\n',
            ),
        ],
    ),
    (
        "licence file: clause also on the donor line",
        [],
        "R14",
        "carries 'Reserved Font Name'",
        [
            (
                "OFL.txt",
                "(https://takwolf.com).\n",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".\n',
            )
        ],
    ),
    (
        "metrics clause reworded (the lint refuses it)",
        [
            (
                "metrics.txt",
                'copyright_rfn_clause = with Reserved Font Name "Nifen Art".',
                "copyright_rfn_clause = with no declaration.",
            )
        ],
        "R14",
        "copyright_rfn_clause is",
    ),
    (
        "name ID 0: clause missing from the typeface's line",
        [("name ID 0", ' with Reserved Font Name "Nifen Art".', "")],
        "NAME0",
        "does not end with",
    ),
    (
        "name ID 0: clause altered on the typeface's line",
        [
            (
                "name ID 0",
                'Reserved Font Name "Nifen Art".',
                'Reserved Font Name "Nifen".',
            )
        ],
        "NAME0",
        "does not end with",
    ),
    (
        "name ID 0: clause moved to the donor line",
        [
            ("name ID 0", ' with Reserved Font Name "Nifen Art".', ""),
            (
                "name ID 0",
                "(https://takwolf.com).",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".',
            ),
        ],
        "NAME0",
        "is attached to a prior copyright line",
    ),
    (
        "name ID 0: clause also on the donor line",
        [
            (
                "name ID 0",
                "(https://takwolf.com).",
                '(https://takwolf.com). with Reserved Font Name "Nifen Art".',
            )
        ],
        "NAME0",
        "is attached to a prior copyright line",
    ),
    (
        "name ID 0: clause missing at the Macintosh record only",
        [("name ID 0 (Macintosh)", ' with Reserved Font Name "Nifen Art".', "")],
        "NAME0",
        "does not end with",
    ),
    (
        "metrics clause reworded (the built name ID 0 follows it)",
        [
            (
                "metrics.txt",
                'copyright_rfn_clause = with Reserved Font Name "Nifen Art".',
                "copyright_rfn_clause = with no declaration.",
            )
        ],
        "NAME0",
        "does not end with",
    ),
]


def main():
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
    ok = True
    n = skipped = 0
    for ctl in CONTROLS:
        res = run(*ctl)
        if res is None:
            skipped += 1
            continue
        n += 1
        ok &= res
    print("controls run: %d   skipped (record not in the sources): %d" % (n, skipped))
    print("ALL CONTROLS CAUGHT" if ok else "SOME CONTROL MISSED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
