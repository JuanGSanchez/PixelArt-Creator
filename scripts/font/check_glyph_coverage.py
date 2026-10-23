"""Nifen Art glyph coverage checker.

Compares a declared character set (and optionally the characters found in
translation catalogues and specimen strings) with the cmap of both built
fonts. Prints the examined count, the missing list and per-block totals;
exits non-zero on any missing gated character, on an unreadable font, or when
nothing was examined.

    python scripts/font/check_glyph_coverage.py [--declared <file>] \
        [--font <ttf> ...] [--strings <file>] [--catalogue <ts> ...] \
        [--py-dir <folder> ...] [--text-dir <folder> ...] [--gate-catalogues] \
        [--table U+LO..U+HI ...]

Run from the repository root. Without arguments the declared set is
fonts-src/nifen-art/coverage/declared-set.txt, the fonts are the two built
files in pixelart_creator/fonts, the probe text is
fonts-src/nifen-art/coverage/probe-text.txt and the catalogues are the two
shipped .ts files; the string-literal, content-text and table scans are only
made when named.

Catalogue characters are reported as information unless --gate-catalogues is
given. --py-dir (repeatable) adds the
non-ASCII characters found in string literals of every .py file below the folder
(the interface code outside the catalogues). --text-dir (repeatable) adds every
non-ASCII character of every .md and .json file below the folder (the content
shown to the reader, such as the user guide). Both are gated together with the
catalogues.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tokenize
import unicodedata
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

BLOCKS = [
    ("Basic Latin", 0x0020, 0x007F),
    ("Latin-1 Supplement", 0x0080, 0x00FF),
    ("Latin Extended-A", 0x0100, 0x017F),
    ("Latin Extended-B", 0x0180, 0x024F),
    ("General Punctuation", 0x2000, 0x206F),
    ("Greek and Coptic", 0x0370, 0x03FF),
    ("Cyrillic", 0x0400, 0x04FF),
    ("Arrows", 0x2190, 0x21FF),
    ("Geometric Shapes", 0x25A0, 0x25FF),
    ("Dingbats", 0x2700, 0x27BF),
    ("CJK Symbols and Punctuation", 0x3000, 0x303F),
    ("Hiragana", 0x3040, 0x309F),
    ("Katakana", 0x30A0, 0x30FF),
    ("CJK Unified Ideographs", 0x4E00, 0x9FFF),
    ("Halfwidth and Fullwidth Forms", 0xFF00, 0xFFEF),
]


def block_of(cp: int) -> str:
    for name, lo, hi in BLOCKS:
        if lo <= cp <= hi:
            return name
    return "Other"


def read_declared(path: str):
    chars = []
    with open(path, "rb") as fh:
        for raw in fh.read().decode("utf-8").split("\n"):
            if not raw or raw.startswith("# "):
                continue
            if ": " not in raw:
                raise SystemExit("bad line in %s: %r" % (path, raw))
            _label, rest = raw.split(": ", 1)
            chars.extend(rest)
    return chars


def read_strings(path: str):
    out = []
    with open(path, "rb") as fh:
        for raw in fh.read().decode("utf-8").split("\n"):
            if raw and not raw.startswith("# "):
                out.extend(raw)
    return out


def read_catalogue(path: str):
    tree = ET.parse(path)
    out = []
    for elem in tree.iter():
        if (
            elem.tag in ("source", "translation", "comment", "extracomment")
            and elem.text
        ):
            out.extend(elem.text)
    return out


def read_py_literals(folder: str):
    """Non-ASCII characters inside string literals of every .py file below folder."""
    out = []
    files = 0
    for root, _dirs, names in sorted(os.walk(folder)):
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            files += 1
            with open(os.path.join(root, name), "rb") as fh:
                text = fh.read().decode("utf-8")
            for tok in tokenize.generate_tokens(io.StringIO(text).readline):
                if tok.type == tokenize.STRING or tok.type == getattr(
                    tokenize, "FSTRING_MIDDLE", -1
                ):
                    out.extend(ch for ch in tok.string if ord(ch) > 127)
    return out, files


def read_text_files(folder: str):
    """Non-ASCII characters of every .md and .json file below folder."""
    out = []
    files = 0
    for root, _dirs, names in sorted(os.walk(folder)):
        for name in sorted(names):
            if not (name.endswith(".md") or name.endswith(".json")):
                continue
            files += 1
            with open(os.path.join(root, name), "rb") as fh:
                text = fh.read().decode("utf-8")
            out.extend(ch for ch in text if ord(ch) > 127)
    return out, files


def cmap_of(path: str):
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    return set(font.getBestCmap().keys())


def describe(cp: int) -> str:
    try:
        name = unicodedata.name(chr(cp))
    except ValueError:
        name = "?"
    return "U+%04X %s" % (cp, name)


def report_set(label, chars, cmaps, gate):
    """Print the coverage of a character list against each font; return failures."""
    uniq = sorted(set(ord(c) for c in chars if c not in "\n\r\t"))
    if not uniq:
        print("%s: nothing examined" % label)
        return 1
    fails = 0
    for fname, cmap in cmaps:
        missing = [cp for cp in uniq if cp not in cmap]
        by_block = {}
        for cp in uniq:
            b = by_block.setdefault(block_of(cp), [0, 0])
            b[0] += 1
            if cp not in cmap:
                b[1] += 1
        print(
            "%s | %s: examined %d unique characters, missing %d"
            % (label, fname, len(uniq), len(missing))
        )
        for b, (n, miss) in sorted(by_block.items()):
            print("    %-30s examined %4d  missing %4d" % (b, n, miss))
        if missing:
            shown = missing[:40]
            print(
                "    missing: "
                + ", ".join(describe(cp) for cp in shown)
                + (" ..." if len(missing) > 40 else "")
            )
        if gate and missing:
            fails += 1
    return fails


def report_table(spec, cmaps):
    """A whole Unicode range, taken from the Unicode character database rather
    than from a list of characters: every assigned code point in LO..HI must be
    in each font. Returns the number of failures.
    """
    lo_s, hi_s = spec.split("..")
    lo, hi = int(lo_s.replace("U+", ""), 16), int(hi_s.replace("U+", ""), 16)
    assigned = [cp for cp in range(lo, hi + 1) if unicodedata.category(chr(cp)) != "Cn"]
    if not assigned:
        print("table %s: no assigned code point in the range, nothing examined" % spec)
        return 1
    fails = 0
    for fname, cmap in cmaps:
        missing = [cp for cp in assigned if cp not in cmap]
        print(
            "table U+%04X..U+%04X | %s: assigned %d of %d code points, missing %d%s"
            % (
                lo,
                hi,
                fname,
                len(assigned),
                hi - lo + 1,
                len(missing),
                (
                    (": " + ", ".join(describe(cp) for cp in missing[:20]))
                    if missing
                    else ""
                ),
            )
        )
        fails += 1 if missing else 0
    return fails


def report_block_gaps(cmaps):
    """Information only: assigned code points of the Japanese blocks that the
    fonts do not carry."""
    for name, lo, hi in BLOCKS:
        if name not in ("CJK Symbols and Punctuation", "Hiragana", "Katakana"):
            continue
        for fname, cmap in cmaps[:1]:
            absent = [
                cp
                for cp in range(lo, hi + 1)
                if unicodedata.category(chr(cp)) != "Cn" and cp not in cmap
            ]
            print(
                "info: %s: assigned code points not in the font: %d%s"
                % (
                    name,
                    len(absent),
                    (": " + ", ".join("U+%04X" % c for c in absent)) if absent else "",
                )
            )


HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_DECLARED = os.path.join(
    REPO, "fonts-src", "nifen-art", "coverage", "declared-set.txt"
)
DEFAULT_STRINGS = os.path.join(
    REPO, "fonts-src", "nifen-art", "coverage", "probe-text.txt"
)
DEFAULT_FONTS = [
    os.path.join(REPO, "pixelart_creator", "fonts", "NifenArt-Regular.ttf"),
    os.path.join(REPO, "pixelart_creator", "fonts", "NifenArt-Bold.ttf"),
]
DEFAULT_CATALOGUES = [
    os.path.join(REPO, "pixelart_creator", "i18n", "pixelart_en.ts"),
    os.path.join(REPO, "pixelart_creator", "i18n", "pixelart_es.ts"),
]


def make_console_safe():
    """Keep every later print() from dying on a legacy console code page.

    A character the stream cannot encode prints as a backslash escape instead of
    raising. The checker stays standalone, so this does not import the build's
    library.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--declared", default=DEFAULT_DECLARED)
    ap.add_argument("--font", action="append")
    ap.add_argument("--strings", default=DEFAULT_STRINGS)
    ap.add_argument("--catalogue", action="append", default=None)
    ap.add_argument("--py-dir", action="append", default=[])
    ap.add_argument("--text-dir", action="append", default=[])
    ap.add_argument("--gate-catalogues", action="store_true")
    ap.add_argument(
        "--table",
        action="append",
        default=[],
        help="U+LO..U+HI: a whole Unicode range, gated",
    )
    args = ap.parse_args()
    make_console_safe()
    if not args.font:
        args.font = list(DEFAULT_FONTS)
    if args.catalogue is None:
        args.catalogue = list(DEFAULT_CATALOGUES)

    cmaps = []
    for p in args.font:
        try:
            cmaps.append((p.replace("\\", "/").rsplit("/", 1)[-1], cmap_of(p)))
        except Exception as exc:  # noqa: BLE001 - report any unreadable font
            print("cannot read %s: %s" % (p, exc))
            return 2
    declared = read_declared(args.declared)
    fails = report_set("declared set", declared, cmaps, True)
    declared_set = set(ord(c) for c in declared)
    for fname, cmap in cmaps:
        extra = sorted(cp for cp in cmap if cp not in declared_set)
        print(
            "%s: font glyphs not in the declared set: %d %s"
            % (fname, len(extra), ", ".join("U+%04X" % c for c in extra))
        )
        fails += 1 if extra else 0
    if args.strings:
        fails += report_set("specimen strings", read_strings(args.strings), cmaps, True)
    if args.catalogue:
        chars = []
        for c in args.catalogue:
            chars.extend(read_catalogue(c))
        fails += report_set(
            "catalogues (%d files)" % len(args.catalogue),
            chars,
            cmaps,
            args.gate_catalogues,
        )
    for folder in args.py_dir:
        chars, nfiles = read_py_literals(folder)
        tag = os.path.basename(os.path.normpath(folder))
        fails += report_set(
            "python string literals of %s (%d files, non-ASCII only)" % (tag, nfiles),
            chars,
            cmaps,
            args.gate_catalogues,
        )
    for folder in args.text_dir:
        chars, nfiles = read_text_files(folder)
        tag = os.path.basename(os.path.normpath(folder))
        fails += report_set(
            "content text of %s (%d .md/.json files, non-ASCII only)" % (tag, nfiles),
            chars,
            cmaps,
            args.gate_catalogues,
        )
    for spec in args.table:
        fails += report_table(spec, cmaps)
    if args.table:
        report_block_gaps(cmaps)
    print("coverage failures: %d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
