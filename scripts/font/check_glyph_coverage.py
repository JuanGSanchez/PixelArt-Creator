"""Nifen Art glyph coverage checker.

Compares a declared character set (and optionally the characters found in
translation catalogues, interface code and guide content) with the cmap of the
built fonts of both faces, and prints the examined count, the missing list and
per-block totals. It exits non-zero on any missing gated character, on an
unreadable font, and when nothing was examined.

    python scripts/font/check_glyph_coverage.py [--declared <file>] \
        [--font <ttf> ...] [--strings <file>] [--catalogue <ts> ...] \
        [--catalogue-dir <folder>] [--py-dir <folder> ...] \
        [--text-dir <folder> ...] [--endonyms] [--gate-catalogues] \
        [--measured-set [<file>]] [--table U+LO..U+HI ...]
    python scripts/font/check_glyph_coverage.py --batch <worklist.json | page.md |
        folder> ... [--language <code>]

Run from the repository root. Without arguments the declared set is
fonts-src/nifen-art/coverage/declared-set.txt, the fonts are the two built
files of the existing face in pixelart_creator/fonts (plus the CJK files that
exist there), the probe text is fonts-src/nifen-art/coverage/probe-text.txt and
the catalogues are every pixelart_*.ts found in pixelart_creator/i18n (none
found fails). The string-literal, content-text, endonym, measured-set and table
scans are only made when named.

Two faces. The existing face (NifenArt-Regular.ttf, NifenArt-Bold.ttf) holds
neither a Han nor a Hangul character, asserted and printed per weight on every
run. The CJK face is three families, each in Regular and Bold:
NifenArtCJKJP-*.ttf (Japanese Han forms), NifenArtCJKSC-*.ttf (Simplified Han
forms) and NifenArtCJKKR-*.ttf (Hangul). The declared set, the probe text and the
"font glyphs not in the declared set" rule are existing-face checks.

Routing. Every character of a catalogue, python literal, content text or endonym
scan is sent to the face that must draw it, with the Han and Hangul definitions
(the ranges) imported from pixelart_creator/logic/constants.py:

* a Hangul syllable goes to the KR face;
* the Han of an endonym goes to its own language's form set only (the endonym of
  zh_CN to SC, of ja to JP); the endonyms are imported from
  pixelart_creator/logic/language_names.py;
* Han in ja text (its catalogue file or guide tree) goes to the JP set, and Han in
  zh_CN text to the SC set;
* any other Han goes to both form sets: the text of every other language, and
  python literals that are not an endonym;
* everything else goes to the existing face.

Each face prints its own line per weight, "<label> | <font>: examined N unique
characters, missing M", and each scan prints its routed counts, which must add up
to the examined total. A CJK font that is not given (or whose file does not exist
at the default path) holds nothing: the characters routed to it are missing.

Escapes. A character written as an escape is read as the character: python
literals are parsed as syntax trees (so "\\u7b80" and "\\N{...}" are seen), .json
files are parsed as JSON, .md files have their character references decoded and
catalogues are parsed as XML. A file that cannot be parsed or decoded is a
failure, never skipped. A character built at run time (chr(0x7B80)) cannot be seen
by any static scan.

Catalogue characters are reported as information unless --gate-catalogues is
given. --py-dir (repeatable) adds the non-ASCII characters found in string
literals of every .py file below the folder. --text-dir (repeatable) adds every
non-ASCII character of every .md and .json file below the folder (the content
shown to the reader, such as the user guide). --endonyms adds the language
self-names. All are gated together with the catalogues.

Batch mode (--batch, alone): reads a batch (a worklist's translations, guide
pages), routes every character of it as above and judges each destination against
its own font, with the segment key of every missing character. Every examined
character lands in exactly one named destination (existing face, KR, JP only, SC
only, JP and SC); a character that lands in none is a routing error, and the
destination counts must add up to the examined total. It prints, per CJK face and
per weight, "<label> | <font>: examined N unique characters, missing M" (N is the
number routed to that face, 0 stated as such), and fails when any routed character
is missing from its face, as the other modes do: a Hangul syllable of a batch is
missing until the KR face draws it. A CJK font that is not given holds nothing.
Zero characters examined fails.
"""

from __future__ import annotations

import argparse
import ast
import html
import importlib.util
import json
import os
import re
import sys
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
    ("CJK Unified Ideographs Extension A", 0x3400, 0x4DBF),
    ("CJK Unified Ideographs", 0x4E00, 0x9FFF),
    ("Hangul Syllables", 0xAC00, 0xD7AF),
    ("CJK Compatibility Ideographs", 0xF900, 0xFAFF),
    ("Halfwidth and Fullwidth Forms", 0xFF00, 0xFFEF),
    ("CJK Ideographs Extensions B to H", 0x20000, 0x323AF),
]

#: The three CJK families: set key -> file stem. Each is built in Regular and Bold.
CJK_STEMS = {"jp": "NifenArtCJKJP", "sc": "NifenArtCJKSC", "kr": "NifenArtCJKKR"}
CJK_FACES = ("jp", "sc", "kr")
WEIGHTS = ("Regular", "Bold")
CJK_FILE = re.compile(r"^NifenArtCJK(JP|SC|KR)-(Regular|Bold)\.ttf$")

#: The five destinations a character can have, by the exact set of faces that must
#: draw it; the names are the keys of ``Collector.partition``.
DESTINATIONS = {
    frozenset({"existing"}): "existing",
    frozenset({"kr"}): "kr",
    frozenset({"jp"}): "jp",
    frozenset({"sc"}): "sc",
    frozenset({"jp", "sc"}): "jp+sc",
}

#: The Han form set of a language whose text is drawn in one (Japanese, Simplified).
FORM_OF_LANGUAGE = {"ja": "jp", "zh_CN": "sc"}

#: Language codes of the shipped catalogues, used only when the endonym table
#: cannot be read (the table's keys are the source otherwise).
FALLBACK_LANGUAGES = ("en", "es", "fr", "de", "ru", "zh_CN", "ja", "ko")

CATALOGUE_TAGS = ("source", "translation", "comment", "extracomment", "numerusform")
CATALOGUE_FILE = re.compile(r"^pixelart_(.+)\.ts$")


class ToolError(Exception):
    """A problem with an input the checker cannot go on without."""


def block_of(cp: int) -> str:
    for name, lo, hi in BLOCKS:
        if lo <= cp <= hi:
            return name
    return "Other"


def safe(text) -> str:
    """Text as ASCII, so a report reads the same under any console code page."""
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def describe(cp: int) -> str:
    try:
        name = unicodedata.name(chr(cp))
    except ValueError:
        name = "?"
    return "U+%04X %s" % (cp, name)


def posix_rel(path: str, start: str) -> str:
    return os.path.relpath(path, start).replace(os.sep, "/")


# --------------------------------------------------------------------------
# The two definitions and the endonyms, imported from the product package
# --------------------------------------------------------------------------


def _load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None or not os.path.isfile(path):
        raise ToolError("cannot load %s" % safe(path))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - name the file, whatever went wrong
        raise ToolError("cannot load %s: %s" % (safe(path), safe(exc))) from exc
    return module


class Ranges:
    """The Han and Hangul definitions (inclusive code point ranges)."""

    def __init__(self, han, hangul):
        self.han = tuple((int(a), int(b)) for a, b in han)
        self.hangul = tuple((int(a), int(b)) for a, b in hangul)

    def kind(self, cp: int) -> str:
        for lo, hi in self.han:
            if lo <= cp <= hi:
                return "han"
        for lo, hi in self.hangul:
            if lo <= cp <= hi:
                return "hangul"
        return "other"


def load_ranges(path: str) -> Ranges:
    module = _load_module("nifen_cov_constants", path)
    try:
        return Ranges(module.HAN_RANGES, module.HANGUL_RANGES)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ToolError(
            "%s does not define HAN_RANGES and HANGUL_RANGES: %s"
            % (safe(path), safe(exc))
        ) from exc


def load_endonyms(path: str):
    """Language code -> its own name, or None when the module is not there."""
    if not os.path.isfile(path):
        return None
    module = _load_module("nifen_cov_language_names", path)
    try:
        table = dict(module.ENDONYMS)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ToolError(
            "%s does not define ENDONYMS: %s" % (safe(path), safe(exc))
        ) from exc
    return table


def form_set_of(lang):
    if lang is None:
        return None
    if lang in FORM_OF_LANGUAGE:
        return FORM_OF_LANGUAGE[lang]
    return FORM_OF_LANGUAGE.get(lang.split("_")[0])


def route(ch: str, ranges: Ranges, lang, endonym_lang):
    """The set of faces that must draw ``ch`` seen in ``lang`` text.

    ``endonym_lang`` is the language whose self-name the character came from, or
    None. Destinations are "existing", "kr", "jp" and "sc".
    """
    kind = ranges.kind(ord(ch))
    if kind == "hangul":
        return {"kr"}
    if kind == "han":
        own = form_set_of(endonym_lang if endonym_lang else lang)
        if own:
            return {own}
        return {"jp", "sc"}
    return {"existing"}


# --------------------------------------------------------------------------
# What was read: characters, the faces they route to, where they were seen
# --------------------------------------------------------------------------


class Collector:
    """Unique characters of one scan with their destinations and first places."""

    def __init__(self, ranges: Ranges):
        self.ranges = ranges
        self.chars = {}  # ch -> {"dest": set, "keys": list, "langs": set}
        self.occurrences = 0

    def add(self, text, lang, endonym_lang, key):
        for ch in set(text):
            if ch in "\n\r\t":
                continue
            info = self.chars.get(ch)
            if info is None:
                info = {"dest": set(), "keys": [], "langs": set()}
                self.chars[ch] = info
            info["dest"] |= route(ch, self.ranges, lang, endonym_lang)
            if lang:
                info["langs"].add(lang)
            if len(info["keys"]) < 3 and key not in info["keys"]:
                info["keys"].append(key)
        self.occurrences += len(text)

    def merge(self, other: "Collector"):
        for ch, src in other.chars.items():
            info = self.chars.setdefault(
                ch, {"dest": set(), "keys": [], "langs": set()}
            )
            info["dest"] |= src["dest"]
            info["langs"] |= src["langs"]
            for key in src["keys"]:
                if len(info["keys"]) < 3 and key not in info["keys"]:
                    info["keys"].append(key)
        self.occurrences += other.occurrences

    def routed(self, face: str):
        return sorted(ord(ch) for ch, i in self.chars.items() if face in i["dest"])

    def partition(self):
        """Characters by exact destination set; the parts add up to the total.

        The partition is strict: a character whose destination is none of the five
        named ones (an empty set, or a mix such as the existing face and JP) is in
        no part, so the parts then add up to less than the total. A Han seen in
        two roles (the endonym of one language, other text of another) is the union
        of its two form sets, which is the named JP-and-SC destination.
        """
        parts = {name: 0 for name in DESTINATIONS.values()}
        for info in self.chars.values():
            name = DESTINATIONS.get(frozenset(info["dest"]))
            if name is not None:
                parts[name] += 1
        return parts

    def unrouted(self):
        """Code points whose destination is none of the five named ones."""
        return sorted(
            ord(ch)
            for ch, info in self.chars.items()
            if frozenset(info["dest"]) not in DESTINATIONS
        )

    def annotation(self, ch: str) -> str:
        info = self.chars[ch]
        langs = ",".join(sorted(info["langs"]))
        where = "; ".join(safe(k) for k in info["keys"][:2])
        return ("%s: %s" % (langs, where)) if langs else where


def known_languages(endonyms):
    return tuple(endonyms) if endonyms else FALLBACK_LANGUAGES


def normalise_language(code, known):
    if not code:
        return None
    if code in known:
        return code
    head = code.split("_")[0]
    return head if head in known else None


def catalogue_language(path: str, root, known):
    found = CATALOGUE_FILE.match(os.path.basename(path))
    lang = normalise_language(found.group(1), known) if found else None
    if lang is None:
        lang = normalise_language(root.get("language"), known)
    return lang


def read_catalogue(path: str, coll: Collector, known):
    """Read one .ts file into ``coll``; return (language, unique characters)."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ToolError("cannot read %s: %s" % (safe(path), safe(exc))) from exc
    lang = catalogue_language(path, root, known)
    mine = Collector(coll.ranges)
    name = os.path.basename(path)
    for ctx in root.iter("context"):
        key = "%s[%s]" % (name, ctx.findtext("name") or "")
        for elem in ctx.iter():
            if elem.tag in CATALOGUE_TAGS and elem.text:
                mine.add(elem.text, lang, None, key)
    coll.merge(mine)
    return lang, len(mine.chars)


def discover_catalogues(folder: str):
    if not os.path.isdir(folder):
        return []
    return [
        os.path.join(folder, n)
        for n in sorted(os.listdir(folder))
        if CATALOGUE_FILE.match(n)
    ]


def language_of_path(rel: str, folder: str, known):
    """The language a file belongs to: the first folder name that is a code."""
    parts = [os.path.basename(os.path.normpath(folder))] + rel.split("/")[:-1]
    for part in parts:
        if part in known:
            return part
    return None


def _json_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _json_strings(k)
            yield from _json_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _json_strings(v)


def _non_ascii(text: str) -> str:
    return "".join(ch for ch in text if ord(ch) > 127)


def read_md_text(data: bytes, lang, key, coll: Collector):
    """Non-ASCII characters of a page, character references decoded, per line."""
    text = html.unescape(data.decode("utf-8"))
    for number, line in enumerate(text.split("\n"), 1):
        na = _non_ascii(line)
        if na:
            coll.add(na, lang, None, "%s:%d" % (key, number))


def read_json_text(data: bytes, lang, key, coll: Collector):
    """Non-ASCII characters of every string (keys included) of a JSON document."""
    document = json.loads(data.decode("utf-8"))
    for text in _json_strings(document):
        na = _non_ascii(text)
        if na:
            coll.add(na, lang, None, key)


def read_text_files(folder: str, coll: Collector, known):
    """Non-ASCII characters of every .md and .json file below folder.

    Returns (files read, problems). A file that cannot be decoded or parsed is a
    problem, not a skip.
    """
    files = 0
    problems = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(names):
            if not (name.endswith(".md") or name.endswith(".json")):
                continue
            files += 1
            path = os.path.join(root, name)
            rel = posix_rel(path, folder)
            lang = language_of_path(rel, folder, known)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
                if name.endswith(".md"):
                    read_md_text(data, lang, rel, coll)
                else:
                    read_json_text(data, lang, rel, coll)
            except (OSError, ValueError) as exc:
                problems.append("cannot read %s: %s" % (safe(rel), safe(exc)))
    return files, problems


def read_py_literals(folder: str, coll: Collector, endonym_texts):
    """Non-ASCII characters inside string literals of every .py file below folder.

    The files are parsed, so an escape ("\\u7b80", "\\N{...}") is read as the
    character it spells. A literal that is exactly an endonym is routed as that
    language's endonym. Returns (files read, problems).
    """
    files = 0
    problems = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            files += 1
            path = os.path.join(root, name)
            rel = posix_rel(path, folder)
            try:
                with open(path, "rb") as fh:
                    tree = ast.parse(fh.read(), filename=name)
            except (OSError, SyntaxError, ValueError) as exc:
                problems.append("cannot read %s: %s" % (safe(rel), safe(exc)))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    na = _non_ascii(node.value)
                    if na:
                        coll.add(
                            na,
                            None,
                            endonym_texts.get(node.value),
                            "%s:%d" % (rel, node.lineno),
                        )
    return files, problems


def read_endonyms(endonyms, coll: Collector):
    for lang in sorted(endonyms):
        coll.add(endonyms[lang], None, lang, "endonym %s" % lang)


# --------------------------------------------------------------------------
# Plain (single-face) readers: the declared set and the probe text
# --------------------------------------------------------------------------


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


def read_measured_set(path: str):
    """The measured set file: {"jp": set, "sc": set, "kr": set} of code points."""
    sets = {}
    with open(path, "rb") as fh:
        for raw in fh.read().decode("utf-8").split("\n"):
            if not raw or raw.startswith("#"):
                continue
            label, sep, rest = raw.partition(":")
            if not sep or label not in CJK_STEMS:
                raise ToolError("bad line in %s: %s" % (safe(path), safe(repr(raw))))
            if rest.startswith(" "):
                rest = rest[1:]
            sets[label] = set(ord(c) for c in rest)
    for label in CJK_STEMS:
        if label not in sets:
            raise ToolError("%s has no %s line" % (safe(path), label))
    return sets


def cmap_of(path: str):
    from fontTools.ttLib import TTFont

    font = TTFont(path)
    return set(font.getBestCmap().keys())


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------


def emit_line(label, fname, uniq, cmap, gate, notes=None, annotate=None):
    """Print one "<label> | <font>" line with its block rows; return 1 if it fails.

    ``cmap`` None means the font is not there: every character is missing.
    """
    have = cmap if cmap is not None else set()
    missing = [cp for cp in uniq if cp not in have]
    by_block = {}
    for cp in uniq:
        b = by_block.setdefault(block_of(cp), [0, 0])
        b[0] += 1
        if cp not in have:
            b[1] += 1
    print(
        "%s | %s: examined %d unique characters, missing %d"
        % (label, fname, len(uniq), len(missing))
    )
    for line in notes or ():
        print("    " + line)
    for b, (n, miss) in sorted(by_block.items()):
        print("    %-30s examined %4d  missing %4d" % (b, n, miss))
    if missing:
        shown = missing[:40]
        print(
            "    missing: "
            + ", ".join(
                describe(cp)
                + (" (%s)" % annotate(cp) if annotate and annotate(cp) else "")
                for cp in shown
            )
            + (" ..." if len(missing) > 40 else "")
        )
    return 1 if (gate and missing) else 0


def report_set(label, chars, cmaps, gate):
    """Print the coverage of a character list against each font; return failures."""
    uniq = sorted(set(ord(c) for c in chars if c not in "\n\r\t"))
    if not uniq:
        print("%s: nothing examined" % label)
        return 1
    fails = 0
    for fname, cmap in cmaps:
        fails += emit_line(label, fname, uniq, cmap, gate)
    return fails


class Faces:
    """The fonts a run judges: the existing face and the six CJK files."""

    def __init__(self, existing, cjk):
        self.existing = existing  # [(file name, cmap)]
        self.cjk = cjk  # {file name: cmap}

    def cjk_slots(self):
        for face in CJK_FACES:
            for weight in WEIGHTS:
                name = "%s-%s.ttf" % (CJK_STEMS[face], weight)
                yield face, name, self.cjk.get(name)


def report_routed(label, coll: Collector, faces: Faces, gate):
    """Print one scan against both faces; return failures.

    Each character is judged by the face(s) it is routed to. The routed counts are
    printed and must add up to the examined total.
    """
    total = len(coll.chars)
    if total == 0:
        print("%s: nothing examined" % label)
        return 1
    fails = 0
    parts = coll.partition()
    summed = sum(parts.values())
    print(
        "%s: examined %d unique characters, routed: existing face %d, KR %d, "
        "JP only %d, SC only %d, JP and SC %d (sum %d)"
        % (
            label,
            total,
            parts["existing"],
            parts["kr"],
            parts["jp"],
            parts["sc"],
            parts["jp+sc"],
            summed,
        )
    )
    if summed != total:
        print("    routing error: routed counts sum to %d, not %d" % (summed, total))
        for cp in coll.unrouted()[:40]:
            print("    unrouted: %s" % describe(cp))
        fails += 1

    def annotate(cp):
        return coll.annotation(chr(cp))

    uniq = coll.routed("existing")
    for fname, cmap in faces.existing:
        notes = None if uniq else ["nothing routed to the existing face"]
        fails += emit_line(label, fname, uniq, cmap, gate, notes, annotate)
    for face, fname, cmap in faces.cjk_slots():
        uniq = coll.routed(face)
        notes = []
        if not uniq:
            notes.append("nothing routed to the %s face" % face.upper())
        elif cmap is None:
            notes.append("font not provided: every routed character counts as missing")
        fails += emit_line(label, fname, uniq, cmap, gate, notes, annotate)
    return fails


def report_existing_face_clean(faces: Faces, ranges: Ranges):
    """The existing face holds no Han and no Hangul character, per weight."""
    fails = 0
    for fname, cmap in faces.existing:
        han = sorted(cp for cp in cmap if ranges.kind(cp) == "han")
        hangul = sorted(cp for cp in cmap if ranges.kind(cp) == "hangul")
        print(
            "%s: Han %d, Hangul %d of %d code points%s"
            % (
                fname,
                len(han),
                len(hangul),
                len(cmap),
                (
                    ": " + ", ".join(describe(cp) for cp in (han + hangul)[:20])
                    if han or hangul
                    else ""
                ),
            )
        )
        if han or hangul or not cmap:
            fails += 1
    return fails


def report_measured(path: str, faces: Faces):
    """Each CJK file against the measured set; the glyphs it holds beyond it."""
    sets = read_measured_set(path)
    fails = 0
    for face, fname, cmap in faces.cjk_slots():
        uniq = sorted(sets[face])
        if not uniq:
            print("measured set | %s: examined 0 unique characters, missing 0" % fname)
            continue
        notes = (
            ["font not provided: every measured character counts as missing"]
            if cmap is None
            else None
        )
        fails += emit_line("measured set", fname, uniq, cmap, True, notes)
        if cmap is None:
            print("%s: glyphs outside the measured set: not counted (no font)" % fname)
        else:
            extra = sorted(cp for cp in cmap if cp not in sets[face])
            print(
                "%s: glyphs outside the measured set: %d%s"
                % (
                    fname,
                    len(extra),
                    (
                        (": " + ", ".join(describe(cp) for cp in extra[:20]))
                        if extra
                        else ""
                    ),
                )
            )
    if not any(sets.values()):
        print("measured set: nothing examined")
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


# --------------------------------------------------------------------------
# Batch mode
# --------------------------------------------------------------------------


def _batch_files(path: str):
    if os.path.isfile(path):
        return [path], os.path.dirname(path) or "."
    out = []
    for root, dirs, names in os.walk(path):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(".md") or name.endswith(".json"):
                out.append(os.path.join(root, name))
    return out, path


def read_batch(path: str, coll: Collector, known, default_lang):
    """Read a worklist, a guide page or a folder of them into ``coll``.

    A worklist is a JSON object with an ``entries`` list; its translations are the
    batch's text, keyed "entry N [context]". Returns (files read, problems, the
    language found or None).
    """
    files, base = _batch_files(path)
    problems = []
    found = None
    if not files:
        problems.append("no .md or .json file at %s" % safe(path))
    for item in files:
        rel = posix_rel(item, base)
        try:
            with open(item, "rb") as fh:
                data = fh.read()
            lang = default_lang or language_of_path(rel, base, known)
            if item.endswith(".md"):
                read_md_text(data, lang, rel, coll)
                found = found or lang
                continue
            document = json.loads(data.decode("utf-8"))
            if isinstance(document, dict) and isinstance(document.get("entries"), list):
                lang = (
                    normalise_language(document.get("language"), known)
                    or default_lang
                    or lang
                )
                found = found or lang
                for number, entry in enumerate(document["entries"], 1):
                    forms = (
                        entry.get("translation") if isinstance(entry, dict) else None
                    )
                    if isinstance(forms, str):
                        forms = [forms]
                    key = "entry %d [%s]" % (
                        number,
                        entry.get("context", "") if isinstance(entry, dict) else "",
                    )
                    for form in forms or ():
                        if isinstance(form, str):
                            coll.add(form, lang, None, rel + " " + key)
            else:
                found = found or lang
                read_json_text(data, lang, rel, coll)
        except (OSError, ValueError, AttributeError) as exc:
            problems.append("cannot read %s: %s" % (safe(rel), safe(exc)))
    return len(files), problems, found


def _batch_font_line(label, fname, uniq, cmap, coll: Collector, notes=()):
    """One "<label> | <font>" line of a batch with the segment of each miss.

    ``uniq`` is the code points routed to this font; ``cmap`` None means the font is
    not there, so every one of them is missing. Returns 1 when any is missing.
    """
    have = cmap if cmap is not None else set()
    missing = [cp for cp in uniq if cp not in have]
    print(
        "%s | %s: examined %d unique characters, missing %d"
        % (label, fname, len(uniq), len(missing))
    )
    for line in notes:
        print("    " + line)
    for cp in missing[:40]:
        keys = coll.chars[chr(cp)]["keys"]
        print(
            "    missing: %s - segment: %s"
            % (describe(cp), "; ".join(safe(k) for k in keys))
        )
    if len(missing) > 40:
        print("    missing: ...")
    return 1 if missing else 0


def report_batch(name, nfiles, coll: Collector, faces: Faces, lang):
    """A batch's characters, each judged by the face(s) that must draw it.

    The existing face judges what is routed to it, and each CJK file judges the
    Hangul or Han routed to its family, in both weights, as every other mode does.
    The destinations are strict (see ``Collector.partition``) and their counts must
    add up to the examined total.
    """
    total = len(coll.chars)
    label = "batch %s (%d files)" % (name, nfiles)
    if total == 0:
        print("%s: nothing examined" % label)
        return 1
    fails = 0
    parts = coll.partition()
    judged = coll.routed("existing")
    han = parts["jp"] + parts["sc"] + parts["jp+sc"]
    hangul = parts["kr"]
    summed = len(judged) + han + hangul
    by_dest = sum(parts.values())
    print(
        "%s: examined %d unique characters, routed: existing face %d, Han %d, "
        "Hangul %d (sum %d)" % (label, total, len(judged), han, hangul, summed)
    )
    print(
        "    routed by destination: existing face %d, KR %d, JP only %d, SC only %d, "
        "JP and SC %d (sum %d)"
        % (
            parts["existing"],
            parts["kr"],
            parts["jp"],
            parts["sc"],
            parts["jp+sc"],
            by_dest,
        )
    )
    if lang:
        print("    language of the batch: %s" % lang)
    for counted in sorted({summed, by_dest}):
        if counted != total:
            print(
                "    routing error: routed counts sum to %d, not %d" % (counted, total)
            )
    if summed != total or by_dest != total:
        for cp in coll.unrouted()[:40]:
            print("    unrouted: %s" % describe(cp))
        fails += 1
    for fname, cmap in faces.existing:
        notes = [] if judged else ["nothing routed to the existing face"]
        fails += _batch_font_line(label, fname, judged, cmap, coll, notes)
    for face, fname, cmap in faces.cjk_slots():
        uniq = coll.routed(face)
        notes = []
        if not uniq:
            notes.append("nothing routed to the %s face" % face.upper())
        elif cmap is None:
            notes.append("font not provided: every routed character counts as missing")
        fails += _batch_font_line(label, fname, uniq, cmap, coll, notes)
    return fails


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FONT_DIR = os.path.join(REPO, "pixelart_creator", "fonts")
DEFAULT_DECLARED = os.path.join(
    REPO, "fonts-src", "nifen-art", "coverage", "declared-set.txt"
)
DEFAULT_STRINGS = os.path.join(
    REPO, "fonts-src", "nifen-art", "coverage", "probe-text.txt"
)
DEFAULT_MEASURED = os.path.join(
    REPO, "fonts-src", "nifen-art-cjk", "coverage", "measured-set.txt"
)
DEFAULT_EXISTING_FONTS = [
    os.path.join(FONT_DIR, "NifenArt-Regular.ttf"),
    os.path.join(FONT_DIR, "NifenArt-Bold.ttf"),
]
DEFAULT_CATALOGUE_DIR = os.path.join(REPO, "pixelart_creator", "i18n")
DEFAULT_CONSTANTS = os.path.join(REPO, "pixelart_creator", "logic", "constants.py")
DEFAULT_LANGUAGE_NAMES = os.path.join(
    REPO, "pixelart_creator", "logic", "language_names.py"
)


def default_fonts():
    """The existing face, plus the CJK files that are there."""
    fonts = list(DEFAULT_EXISTING_FONTS)
    for face in CJK_FACES:
        for weight in WEIGHTS:
            path = os.path.join(FONT_DIR, "%s-%s.ttf" % (CJK_STEMS[face], weight))
            if os.path.isfile(path):
                fonts.append(path)
    return fonts


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


def build_parser():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--declared", default=DEFAULT_DECLARED)
    ap.add_argument("--font", action="append")
    ap.add_argument("--strings", default=DEFAULT_STRINGS)
    ap.add_argument("--catalogue", action="append", default=None)
    ap.add_argument(
        "--catalogue-dir",
        default=DEFAULT_CATALOGUE_DIR,
        help="folder searched for pixelart_*.ts when no --catalogue is named",
    )
    ap.add_argument("--py-dir", action="append", default=[])
    ap.add_argument("--text-dir", action="append", default=[])
    ap.add_argument(
        "--endonyms", action="store_true", help="judge the language self-names"
    )
    ap.add_argument("--gate-catalogues", action="store_true")
    ap.add_argument(
        "--measured-set",
        nargs="?",
        const=DEFAULT_MEASURED,
        default=None,
        help="judge the CJK files against the measured set (default file named)",
    )
    ap.add_argument(
        "--batch",
        action="append",
        default=[],
        help="a worklist, a guide page or a folder: batch mode, run alone",
    )
    ap.add_argument(
        "--language", default=None, help="language code of a --batch (routing info)"
    )
    ap.add_argument("--constants", default=DEFAULT_CONSTANTS)
    ap.add_argument("--language-names", default=DEFAULT_LANGUAGE_NAMES)
    ap.add_argument(
        "--table",
        action="append",
        default=[],
        help="U+LO..U+HI: a whole Unicode range, gated",
    )
    return ap


def read_fonts(paths):
    """Split the given files into the existing face and the CJK files."""
    existing = []
    cjk = {}
    for p in paths:
        name = p.replace("\\", "/").rsplit("/", 1)[-1]
        try:
            cmap = cmap_of(p)
        except Exception as exc:  # noqa: BLE001 - report any unreadable font
            print("cannot read %s: %s" % (p, exc))
            return None
        if CJK_FILE.match(name):
            cjk[name] = cmap
        else:
            existing.append((name, cmap))
    return Faces(existing, cjk)


def main():
    args = build_parser().parse_args()
    make_console_safe()
    faces = read_fonts(args.font if args.font else default_fonts())
    if faces is None:
        return 2
    if not faces.existing:
        print("cannot judge: no font of the existing face was given")
        return 2
    try:
        ranges = load_ranges(args.constants)
        endonyms = load_endonyms(args.language_names)
    except ToolError as exc:
        print("cannot read the definitions: %s" % exc)
        return 2
    known = known_languages(endonyms)
    endonym_texts = {text: lang for lang, text in (endonyms or {}).items()}
    if endonyms is None:
        print(
            "endonyms: %s not found; no literal is treated as an endonym"
            % safe(os.path.basename(args.language_names))
        )
    else:
        print("endonyms: %d language self-names read" % len(endonyms))

    if args.batch:
        return run_batch(args, faces, ranges, known)

    fails = 0
    cmaps = faces.existing
    declared = read_declared(args.declared)
    fails += report_set("declared set", declared, cmaps, True)
    declared_set = set(ord(c) for c in declared)
    for fname, cmap in cmaps:
        extra = sorted(cp for cp in cmap if cp not in declared_set)
        print(
            "%s: font glyphs not in the declared set: %d %s"
            % (fname, len(extra), ", ".join("U+%04X" % c for c in extra))
        )
        fails += 1 if extra else 0
    fails += report_existing_face_clean(faces, ranges)
    if args.strings:
        fails += report_set("specimen strings", read_strings(args.strings), cmaps, True)

    catalogues = args.catalogue
    if catalogues is None:
        catalogues = discover_catalogues(args.catalogue_dir)
        if not catalogues:
            print(
                "no catalogue found: no pixelart_*.ts in %s"
                % safe(os.path.basename(os.path.normpath(args.catalogue_dir)))
            )
            fails += 1
    if catalogues:
        coll = Collector(ranges)
        for c in catalogues:
            try:
                lang, count = read_catalogue(c, coll, known)
            except ToolError as exc:
                print(exc)
                fails += 1
                continue
            print(
                "catalogue %s: language %s, read %d unique characters"
                % (safe(os.path.basename(c)), lang or "unknown", count)
            )
        fails += report_routed(
            "catalogues (%d files)" % len(catalogues), coll, faces, args.gate_catalogues
        )
    for folder in args.py_dir:
        coll = Collector(ranges)
        nfiles, problems = read_py_literals(folder, coll, endonym_texts)
        for line in problems:
            print(line)
        fails += len(problems)
        tag = os.path.basename(os.path.normpath(folder))
        fails += report_routed(
            "python string literals of %s (%d files, non-ASCII only)" % (tag, nfiles),
            coll,
            faces,
            args.gate_catalogues,
        )
    for folder in args.text_dir:
        coll = Collector(ranges)
        nfiles, problems = read_text_files(folder, coll, known)
        for line in problems:
            print(line)
        fails += len(problems)
        tag = os.path.basename(os.path.normpath(folder))
        fails += report_routed(
            "content text of %s (%d .md/.json files, non-ASCII only)" % (tag, nfiles),
            coll,
            faces,
            args.gate_catalogues,
        )
    if args.endonyms:
        if endonyms is None:
            print("endonyms: nothing examined (no language-names module)")
            fails += 1
        else:
            coll = Collector(ranges)
            read_endonyms(endonyms, coll)
            fails += report_routed(
                "endonym labels (%d)" % len(endonyms), coll, faces, args.gate_catalogues
            )
    if args.measured_set:
        try:
            fails += report_measured(args.measured_set, faces)
        except (OSError, ToolError, ValueError) as exc:
            print("cannot read the measured set: %s" % safe(exc))
            fails += 1
    for spec in args.table:
        fails += report_table(spec, cmaps)
    if args.table:
        report_block_gaps(cmaps)
    print("coverage failures: %d" % fails)
    return 1 if fails else 0


def run_batch(args, faces: Faces, ranges: Ranges, known):
    """Batch mode: each --batch against the existing face, Han and Hangul."""
    fails = report_existing_face_clean(faces, ranges)
    for path in args.batch:
        coll = Collector(ranges)
        nfiles, problems, lang = read_batch(
            path, coll, known, normalise_language(args.language, known)
        )
        for line in problems:
            print(line)
        fails += len(problems)
        name = safe(os.path.basename(os.path.normpath(path)))
        fails += report_batch(name, nfiles, coll, faces, lang)
    print("coverage failures: %d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
