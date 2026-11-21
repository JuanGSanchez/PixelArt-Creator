"""Scan for font files that are not Nifen Art's own, and for scripts that name one.

Standard library only:

    python scripts/font/check_foreign_fonts.py --tree <folder> [--tree <folder> ...] \\
        --scripts <folder> [--scripts <folder> ...] [--scripts-skip <name> ...]
    python scripts/font/check_foreign_fonts.py --controls [--sample-font <file>]

Two scans, each over what it is given:

  - every file of every --tree folder is recognised by its content, never by its name
    (a TrueType or OpenType font, a font collection, a WOFF file), and a font is allowed
    only when it is a TrueType file named as Nifen Art's built files are named and its
    name table gives a Nifen Art family. A font under any other name, in any other
    format, or with any other family is refused and named;
  - every script (.py, .sh, .bash, .cmd, .bat, .ps1, .js, .mjs, .cjs) under every
    --scripts folder is searched, line by line, for the reference typefaces' file names,
    for the font collection extension, for any font file name whose name is not a Nifen
    Art one, and for a path into the folder of reference images; a hit is named with its
    file and line. A font file name that starts with a placeholder (a format field) is
    built at run time and cannot be judged: it is listed apart, and fails nothing.

The numbers of files and scripts examined are printed and each must be non-zero.
The search words are written in pieces, so that this file does not itself name what it
looks for. Exit codes: 0 nothing foreign found, 1 something found or nothing examined,
2 an input could not be read.

--controls plants each fault in memory (a copy of one of Nifen Art's own built files,
with its family name altered, or under another name, and headers of other formats;
scripts that open or name a font) and requires the scan to catch it. The sample is one
of the product's own fonts, found at the default path under the repository root or
given with --sample-font; no reference file is ever used.
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

sys.dont_write_bytecode = True


def pieces(*parts: str) -> str:
    return "".join(parts)


OWN_FILE_PREFIX = "NifenArt"
OWN_FAMILY_PREFIX = "Nifen Art"
OWN_FILE_END = pieces(".tt", "f")
SAMPLE_REL = ("pixelart_creator", "fonts", "NifenArt-Regular.ttf")

# What the scripts are searched for: the reference typefaces' file names (the stems of
# their files), the name of the folder that holds the reference font files, then the
# other patterns. Each is a regular expression, case-insensitive. The earlier stems
# stay: they name font files outside Nifen Art's.
REFERENCE_STEMS = (
    pieces("YuGoth", "M"),
    pieces("ms", "yh"),
    pieces("Source", "HanSans-Regular"),
    pieces("Source", "HanSansSC-Regular"),
    pieces("reference", "-fonts"),
)
SCRIPT_EXTENSIONS = (
    ".py",
    ".sh",
    ".bash",
    ".cmd",
    ".bat",
    ".ps1",
    ".js",
    ".mjs",
    ".cjs",
)
SEPARATOR_CLASS = pieces("[/", chr(92), chr(92), "]")
FONT_NAME_RE = re.compile(
    r"[%{}A-Za-z0-9_\-]+\.(?:ttf|otf|woff2?|pfb|pfa|dfont|fon|ttc|otc)\b",
    re.IGNORECASE,
)
# A name that starts with a placeholder is built at run time; the scan cannot judge it
# and lists it apart, failing nothing.
PLACEHOLDER_STARTS = ("%", "{")
COLLECTION_RE = re.compile(r"\.(?:tt|ot)c\b", re.IGNORECASE)
FOLDER_RE = re.compile(
    r"(?<![A-Za-z0-9_])" + pieces("comp", "are") + SEPARATOR_CLASS, re.IGNORECASE
)
STEM_RES = tuple((s, re.compile(re.escape(s), re.IGNORECASE)) for s in REFERENCE_STEMS)

HEAD_BYTES = 1100
MAX_TABLES = 64
TRUETYPE_TAGS = (b"\x00\x01\x00\x00", b"true")
OPENTYPE_TAGS = (b"OTTO", b"typ1")


class Entry(NamedTuple):
    """A file as the scan sees it: its name, its size and a way to read it."""

    rel: str
    size: int
    read: Callable[[Optional[int]], bytes]


class Scan(NamedTuple):
    files: int
    scripts: int
    fonts: int
    allowed: int
    refused: List[str]
    hits: List[str]
    templates: List[str]


def memory_entry(rel: str, data: bytes) -> Entry:
    return Entry(rel, len(data), lambda n: data if n is None else data[:n])


def disk_entry(rel: str, full: str) -> Entry:
    def read(n: Optional[int]) -> bytes:
        with open(full, "rb") as fh:
            return fh.read() if n is None else fh.read(n)

    return Entry(rel, os.path.getsize(full), read)


def walk(root: str, seen: Dict[str, bool], skip: Sequence[str] = ()) -> List[Entry]:
    """Every regular file under root, once, in a fixed order."""
    out: List[Entry] = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for name in sorted(names):
            full = os.path.join(folder, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            real = os.path.realpath(full)
            if real in seen:
                continue
            seen[real] = True
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out.append(disk_entry(rel, full))
    return out


def classify(head: bytes, size: int) -> Optional[str]:
    """The font format of a file's first bytes, or None when it is not a font."""
    tag = head[:4]
    if tag == b"ttcf":
        if len(head) < 12:
            return None
        major, _minor, count = struct.unpack(">HHI", head[4:12])
        if major in (1, 2) and 1 <= count <= MAX_TABLES and 12 + 4 * count <= size:
            return "collection"
        return None
    if tag in TRUETYPE_TAGS + OPENTYPE_TAGS:
        if len(head) < 12:
            return None
        (num,) = struct.unpack(">H", head[4:6])
        end = 12 + 16 * num
        if not 1 <= num <= MAX_TABLES or end > size or len(head) < end:
            return None
        for i in range(num):
            name, _sum, offset, length = struct.unpack(
                ">4sIII", head[12 + 16 * i : 28 + 16 * i]
            )
            if not all(32 <= b < 127 for b in name) or offset + length > size:
                return None
        return "truetype" if tag in TRUETYPE_TAGS else "opentype"
    if tag in (b"wOFF", b"wOF2"):
        if len(head) >= 12 and size >= 44:
            (length,) = struct.unpack(">I", head[8:12])
            if length == size:
                return "woff" if tag == b"wOFF" else "woff2"
    return None


def family_names(data: bytes) -> List[str]:
    """The family names (name IDs 1 and 16) of a TrueType or OpenType file."""
    try:
        (num,) = struct.unpack(">H", data[4:6])
        for i in range(num):
            tag, _sum, offset, length = struct.unpack(
                ">4sIII", data[12 + 16 * i : 28 + 16 * i]
            )
            if tag != b"name":
                continue
            table = data[offset : offset + length]
            _fmt, count, string_offset = struct.unpack(">HHH", table[:6])
            names: List[str] = []
            for j in range(count):
                platform, _enc, _lang, name_id, size, off = struct.unpack(
                    ">6H", table[6 + 12 * j : 18 + 12 * j]
                )
                if name_id not in (1, 16):
                    continue
                raw = table[string_offset + off : string_offset + off + size]
                names.append(
                    raw.decode("utf-16-be" if platform in (0, 3) else "latin-1")
                )
            return names
    except struct.error, UnicodeDecodeError:
        return []
    return []


def refusal(entry: Entry, kind: str) -> Optional[str]:
    """Why a font file is not Nifen Art's own, or None when it is."""
    if kind != "truetype":
        return "a %s file; Nifen Art's built files are TrueType files" % kind
    base = entry.rel.rsplit("/", 1)[-1]
    if not (base.startswith(OWN_FILE_PREFIX) and base.endswith(OWN_FILE_END)):
        return "a TrueType font named %s, which is not a Nifen Art file name" % base
    names = family_names(entry.read(None))
    if not names or not all(n.startswith(OWN_FAMILY_PREFIX) for n in names):
        return "a TrueType font whose family is %s, not Nifen Art" % (
            ", ".join(repr(n) for n in names) or "unreadable"
        )
    return None


def scan_script(entry: Entry) -> Tuple[List[str], List[str]]:
    """The hits of one script, and the names it builds at run time."""
    text = entry.read(None).decode("utf-8", "replace")
    hits: List[str] = []
    templates: List[str] = []
    for n, line in enumerate(text.split("\n"), 1):
        found: List[str] = []
        for stem, rx in STEM_RES:
            if rx.search(line):
                found.append("the reference file name %s" % stem)
        for m in FONT_NAME_RE.finditer(line):
            token = m.group(0)
            if token.startswith(PLACEHOLDER_STARTS):
                templates.append("%s:%d: %s" % (entry.rel, n, token))
            elif not token.startswith(OWN_FILE_PREFIX):
                found.append("the font file %s" % token)
        if COLLECTION_RE.search(line):
            found.append("a font collection extension")
        if FOLDER_RE.search(line):
            found.append("a path into the folder of reference images")
        for what in found:
            hits.append("%s:%d: names %s" % (entry.rel, n, what))
    return hits, templates


def scan(trees: Sequence[Entry], scripts: Sequence[Entry]) -> Scan:
    refused: List[str] = []
    fonts = allowed = 0
    for entry in trees:
        kind = classify(entry.read(HEAD_BYTES), entry.size)
        if kind is None:
            continue
        fonts += 1
        why = refusal(entry, kind)
        if why is None:
            allowed += 1
        else:
            refused.append("%s: %s" % (entry.rel, why))
    hits: List[str] = []
    templates: List[str] = []
    examined = 0
    for entry in scripts:
        if not entry.rel.lower().endswith(SCRIPT_EXTENSIONS):
            continue
        examined += 1
        found, built = scan_script(entry)
        hits.extend(found)
        templates.extend(built)
    return Scan(len(trees), examined, fonts, allowed, refused, hits, templates)


def report(result: Scan) -> Tuple[int, List[str]]:
    out = [
        "files examined by content: %d" % result.files,
        "font files found: %d (Nifen Art's own %d, refused %d)"
        % (result.fonts, result.allowed, len(result.refused)),
    ]
    out.extend("  refused: " + line for line in result.refused)
    out.append("scripts examined: %d" % result.scripts)
    out.append("script hits: %d" % len(result.hits))
    out.extend("  hit: " + line for line in result.hits)
    out.append(
        "names built at run time, not judged: %d (information)" % len(result.templates)
    )
    out.extend("  built: " + line for line in result.templates)
    failed = bool(result.refused or result.hits)
    if result.files == 0:
        out.append("FAILED: examined: 0 files")
        failed = True
    if result.scripts == 0:
        out.append("FAILED: examined: 0 scripts")
        failed = True
    return (1 if failed else 0), out


def controls(sample_path: str) -> int:
    try:
        with open(sample_path, "rb") as fh:
            sample = fh.read()
    except OSError as exc:
        sys.stdout.write("could not read the sample font: %s\n" % exc)
        return 2
    kind = classify(sample[:HEAD_BYTES], len(sample))
    own_ok = (
        kind is not None and refusal(memory_entry(SAMPLE_REL[-1], sample), kind) is None
    )
    renamed = sample.replace(
        OWN_FAMILY_PREFIX.encode("utf-16-be"), "Nofen Art".encode("utf-16-be")
    ).replace(OWN_FAMILY_PREFIX.encode("latin-1"), b"Nofen Art")
    results: List[Tuple[str, bool, str]] = []

    def record(label: str, ok: bool, what: str) -> None:
        results.append((label, ok, what))

    own_name = "pixelart_creator/fonts/" + SAMPLE_REL[-1]
    clean_files = [
        memory_entry(own_name, sample),
        memory_entry("docs/readme.txt", b"text\n"),
        memory_entry("art/icon.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40),
    ]
    clean_scripts = [
        memory_entry("scripts/font/ok.py", b"path = 'NifenArt-Regular.ttf'\n")
    ]

    def run(
        extra_files: Sequence[Entry] = (),
        extra_scripts: Sequence[Entry] = (),
        files: Optional[Sequence[Entry]] = None,
        scripts: Optional[Sequence[Entry]] = None,
    ) -> Tuple[int, str, Scan]:
        result = scan(
            list(clean_files if files is None else files) + list(extra_files),
            list(clean_scripts if scripts is None else scripts) + list(extra_scripts),
        )
        code, lines = report(result)
        return code, "\n".join(lines), result

    code, text, result = run()
    record(
        "base",
        own_ok and code == 0 and result.allowed == 1 and result.scripts == 1,
        "a clean fixture holding one Nifen Art font exits 0 "
        "(exit %d, fonts %d, allowed %d, scripts %d)"
        % (code, result.fonts, result.allowed, result.scripts),
    )
    planted = "fonts-src/nifen-art-cjk/NifenArtCJKJP-Regular.ttf"
    code, text, result = run(extra_files=[memory_entry(planted, renamed)])
    record(
        "f1",
        renamed != sample and code != 0 and planted in text and "family" in text,
        "a copy of a product font with another family, under a Nifen Art file "
        "name: exit %d, names %s" % (code, planted),
    )
    planted = "fonts-src/nifen-art-cjk/notes.txt"
    code, text, result = run(extra_files=[memory_entry(planted, sample)])
    record(
        "f2",
        code != 0 and planted in text and "not a Nifen Art file name" in text,
        "a copy of a product font under a text file's name: exit %d, "
        "names %s (found by content)" % (code, planted),
    )
    planted = "fonts-src/nifen-art-cjk/data.bin"
    ttc = b"ttcf" + struct.pack(">HHI", 1, 0, 1) + struct.pack(">I", 16) + b"\x00" * 48
    code, text, result = run(extra_files=[memory_entry(planted, ttc)])
    record(
        "f3",
        code != 0 and planted in text and "collection" in text,
        "a font collection under a data file's name: exit %d, names %s"
        % (code, planted),
    )
    planted = "web/asset.dat"
    woff = b"wOFF" + b"\x00\x01\x00\x00" + struct.pack(">I", 60) + b"\x00" * 48
    code, text, result = run(extra_files=[memory_entry(planted, woff)])
    record(
        "f4",
        code != 0 and planted in text and "woff" in text,
        "a WOFF file under a data file's name: exit %d, names %s" % (code, planted),
    )
    planted = "fonts-src/nifen-art-cjk/data.dat"
    otto = b"OTTO" + sample[4:]
    code, text, result = run(extra_files=[memory_entry(planted, otto)])
    record(
        "f5",
        otto != sample
        and otto[4:] == sample[4:]
        and code != 0
        and planted in text
        and "opentype" in text,
        "a copy of a product font with its first four bytes replaced by OTTO, under "
        "a data file's name: exit %d, names %s (found by content)" % (code, planted),
    )
    planted = "scripts/font/planted.py"
    opener = (
        "data = open('Sample" + "Face" + "." + "tt" + "f', 'rb').read()\n"
    ).encode()
    code, text, result = run(extra_scripts=[memory_entry(planted, opener)])
    record(
        "s1",
        code != 0 and planted + ":1" in text and "SampleFace" in text,
        "a script that opens a font file that is not Nifen Art's: "
        "exit %d, names %s line 1" % (code, planted),
    )
    stem = REFERENCE_STEMS[0]
    code, text, result = run(
        extra_scripts=[memory_entry(planted, ("# source: " + stem + "\n").encode())]
    )
    record(
        "s2",
        code != 0 and planted + ":1" in text and stem in text,
        "a script that names a reference font file: exit %d, names %s" % (code, stem),
    )
    for label, index, what in (
        ("s6", 2, "the reference file name of the Japanese form"),
        ("s7", 3, "the reference file name of the Simplified form"),
        ("s8", 4, "the folder that holds the reference font files"),
    ):
        stem = REFERENCE_STEMS[index]
        code, text, result = run(
            extra_scripts=[memory_entry(planted, ("# source: " + stem + "\n").encode())]
        )
        record(
            label,
            code != 0 and planted + ":1" in text and stem in text,
            "a script that names %s: exit %d, names %s" % (what, code, stem),
        )
    code, text, result = run(
        extra_scripts=[memory_entry(planted, ("x = 'a" + "." + "tt" + "c'\n").encode())]
    )
    record(
        "s3",
        code != 0 and planted + ":1" in text and "collection" in text,
        "a script that names the font collection extension: exit %d" % code,
    )
    folder = ("p = 'work/glyphs/" + "comp" + "are" + "/x'\n").encode()
    code, text, result = run(extra_scripts=[memory_entry(planted, folder)])
    record(
        "s4",
        code != 0 and planted + ":1" in text and "reference images" in text,
        "a script that names the folder of reference images: exit %d" % code,
    )
    built = ("name = '%s" + "-" + "%s" + "." + "tt" + "f' % (a, b)\n").encode()
    code, text, result = run(extra_scripts=[memory_entry(planted, built)])
    record(
        "s5",
        code == 0 and len(result.templates) == 1 and not result.hits,
        "a font name built at run time is listed apart and fails nothing: exit %d, "
        "%d listed" % (code, len(result.templates)),
    )
    code, text, result = run(files=[], scripts=[])
    record(
        "empty",
        code != 0 and "examined: 0 files" in text and "examined: 0 scripts" in text,
        "nothing to examine: exit %d, both examined counts are 0 and fail" % code,
    )
    for label, ok, what in results:
        sys.stdout.write(
            "control %-6s %s: %s\n"
            % (
                label,
                (
                    ("passes" if label in ("base", "s5") else "killed")
                    if ok
                    else "NOT KILLED"
                ),
                what,
            )
        )
    bad = [label for label, ok, _ in results if not ok]
    sys.stdout.write(
        "controls: %d run, %d killed, %d not killed\n"
        % (len(results), len(results) - len(bad), len(bad))
    )
    return 0 if not bad else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    ap.add_argument(
        "--tree", action="append", default=[], help="a folder to scan by content"
    )
    ap.add_argument(
        "--scripts", action="append", default=[], help="a folder of scripts"
    )
    ap.add_argument(
        "--scripts-skip", action="append", default=[], help="a folder name to skip"
    )
    ap.add_argument("--controls", action="store_true", help="run the planted controls")
    ap.add_argument("--sample-font", default=os.path.join(root, *SAMPLE_REL))
    args = ap.parse_args(argv)
    if args.controls:
        return controls(args.sample_font)
    if not args.tree or not args.scripts:
        sys.stdout.write("usage: --tree and --scripts are required\n")
        return 2
    try:
        seen: Dict[str, bool] = {}
        trees: List[Entry] = []
        for folder in args.tree:
            trees.extend(walk(folder, seen))
        seen_scripts: Dict[str, bool] = {}
        scripts: List[Entry] = []
        for folder in args.scripts:
            scripts.extend(walk(folder, seen_scripts, args.scripts_skip))
        code, lines = report(scan(trees, scripts))
    except OSError as exc:
        sys.stdout.write("could not read an input: %s\n" % exc)
        return 2
    for line in lines:
        sys.stdout.write(line + "\n")
    sys.stdout.write("exit %d\n" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
