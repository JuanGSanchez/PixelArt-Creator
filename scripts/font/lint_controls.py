"""Injected-defect controls for the source lint.

Each control copies the glyph sources, applies one edit that breaks a rule,
runs the lint on the copy and requires a non-zero exit and the expected rule
flagged. A lint that cannot fail proves nothing; this shows that it can.

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


def run(name, edits, expect_rule, expect_text=None):
    d = tempfile.mkdtemp(dir=SCRATCH)
    try:
        dst = os.path.join(d, "src")
        shutil.copytree(SOURCES, dst)
        for fname, old, new in edits:
            path = os.path.join(dst, fname)
            text = open(path, "rb").read().decode("utf-8")
            if old not in text:
                # the edit targets a record that is not in the sources
                print("%-44s skipped (record not in the sources)" % name)
                return None
            open(path, "wb").write(text.replace(old, new, 1).encode("utf-8"))
        r = subprocess.run(
            [PY, os.path.join(HERE, "build_nifen_art.py"), "--lint", "--src", dst],
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
                "hiragana.txt",
                "glyph U+3044 adv=12 x=1 cell=full ext=free top=10",
                "glyph U+3044 adv=12 x=4 cell=full ext=free top=10",
            )
        ],
        "R01",
        "U+3044",
    ),
    (
        "orphan pixel in hiragana i",
        [
            (
                "hiragana.txt",
                "glyph U+3044 adv=12 x=1 cell=full ext=free top=10\n.#........\n"
                ".#........",
                "glyph U+3044 adv=12 x=1 cell=full ext=free top=10\n.#.......#\n"
                ".#........",
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
        "voiced mark touches its base (trim removed from zu)",
        [
            (
                "recipes-b6.txt",
                "recipe U+305A = overlay U+3059 U+309B trim=1",
                "recipe U+305A = overlay U+3059 U+309B",
            )
        ],
        "R06",
        "U+305A",
    ),
    (
        "trim cut undeclared (gi loses cut=1)",
        [
            (
                "recipes-b6.txt",
                "recipe U+304E = overlay U+304D U+309B trim=1 cut=1",
                "recipe U+304E = overlay U+304D U+309B trim=1",
            )
        ],
        "R06",
        "U+304E",
    ),
    (
        "cut declared but not needed (gu)",
        [
            (
                "recipes-b6.txt",
                "recipe U+3050 = overlay U+304F U+309B trim=1",
                "recipe U+3050 = overlay U+304F U+309B trim=1 cut=1",
            )
        ],
        "R06",
        "U+3050 declares cut",
    ),
    (
        "trim limit exceeded (limit 2 pixels)",
        [("metrics.txt", "trim_max_px = 20", "trim_max_px = 2")],
        "R06",
        "trim removes",
    ),
    (
        "Bold overlay of small hiragana i removed",
        [("bold-overlays-b6.txt", "bold U+3043 ", "bold U+3042 ")],
        "R08",
        "U+3043 derived Bold",
    ),
    (
        "Bold overlay of the hand-drawn pu removed",
        [("bold-overlays-b6.txt", "bold U+3077 ", "bold U+3076 ")],
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
                "hiragana.txt",
                "glyph U+3083 adv=12 x=1 cell=full ext=free top=7",
                "glyph U+3083 adv=12 x=1 cell=full ext=free top=8",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small ya moved to the right half of the cell",
        [
            (
                "hiragana.txt",
                "glyph U+3083 adv=12 x=1 cell=full ext=free top=7",
                "glyph U+3083 adv=12 x=3 cell=full ext=free top=7",
            )
        ],
        "R12",
        "U+3083",
    ),
    (
        "small a moved one pixel off the centre of the cell",
        [
            (
                "hiragana.txt",
                "glyph U+3041 adv=12 x=1 cell=full ext=free top=7",
                "glyph U+3041 adv=12 x=0 cell=full ext=free top=7",
            )
        ],
        "R12",
        "U+3041 regular small kana is not centred",
    ),
    (
        "base of a hand-drawn voiced kana touches the mark (za)",
        [
            (
                "kana-voiced.txt",
                "....#..#.#\n....#..#.#\n...#......",
                "....#..#.#\n....#..#.#\n...#..#...",
            )
        ],
        "R13",
        "U+3056 regular: 1 pixel",
    ),
    (
        "mark pixel missing from a hand-drawn semi-voiced kana (pu)",
        [
            (
                "kana-voiced.txt",
                "...#...##.\n....#.#..#",
                "...#...#..\n....#.#..#",
            )
        ],
        "R13",
        "U+3077 regular: the voicing mark",
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
