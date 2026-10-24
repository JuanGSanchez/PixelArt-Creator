"""Measure the Han and Hangul characters that the shipped text uses.

The drawing list of the CJK face is exactly this set (REQ-L10N-BUILD-001): the
Han and Hangul characters of every catalogue, every guide tree, the language
self-names and the python string literals of the package. Nothing else is drawn
and no base list is added.

    python scripts/font/measure_cjk_set.py [--catalogue-dir <folder>] \
        [--text-dir <folder> ...] [--py-dir <folder> ...] [--out <file>] \
        [--check]

Run from the repository root. Defaults: the catalogues are every pixelart_*.ts in
pixelart_creator/i18n (none found fails), the guide tree is
pixelart_creator/userguide_content, the python literals are those of
pixelart_creator, and the result is written to
fonts-src/nifen-art-cjk/coverage/measured-set.txt.

Each character is routed by the rule of the coverage checker (the same code, so
the two cannot disagree): a Hangul syllable to the KR set; the Han of a language
self-name to its own language's form set only (zh_CN to SC, ja to JP); Han in ja
text to JP and in zh_CN text to SC; any other Han to both form sets. The Han and
Hangul definitions are imported from pixelart_creator/logic/constants.py and the
self-names from pixelart_creator/logic/language_names.py.

The file records the counts per set, the invocation, a hash of each input, the
characters whose script a definition may misjudge, and the change from the
previous measurement. A run that finds nothing new leaves the file untouched.
--check measures and compares with the file without writing it: exit 1 when the
sets differ.

Exit status: 0 done (or unchanged); 1 nothing examined, an input that cannot be
read, or (with --check) a set that differs; 2 the definitions cannot be loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import check_glyph_coverage as cov  # noqa: E402

REPO = cov.REPO
DEFAULT_OUT = cov.DEFAULT_MEASURED
DEFAULT_GUIDE = os.path.join(REPO, "pixelart_creator", "userguide_content")
DEFAULT_PACKAGE = os.path.join(REPO, "pixelart_creator")

#: Names of characters that a script-level reading calls Han or Hangul although the
#: block definitions send them to the existing face (and the converse is checked
#: separately: a code point inside a block that no character is assigned to).
SCRIPT_NAME_PREFIXES = (
    "CJK UNIFIED IDEOGRAPH",
    "CJK COMPATIBILITY IDEOGRAPH",
    "CJK RADICAL",
    "KANGXI RADICAL",
    "HANGUL",
    "IDEOGRAPHIC ITERATION MARK",
    "VERTICAL IDEOGRAPHIC ITERATION MARK",
    "IDEOGRAPHIC CLOSING MARK",
    "IDEOGRAPHIC NUMBER ZERO",
)

HASH_LINE = re.compile(r"^# input (?P<name>[^:]+): .*sha256 (?P<hash>[0-9a-f]{64})$")


def sha256_files(files, base):
    digest = hashlib.sha256()
    for path in files:
        digest.update(cov.posix_rel(path, base).encode("utf-8") + b"\0")
        with open(path, "rb") as fh:
            digest.update(fh.read())
        digest.update(b"\0")
    return digest.hexdigest()


def walk_files(folder, suffixes):
    out = []
    for root, dirs, names in os.walk(folder):
        dirs.sort()
        for name in sorted(names):
            if name.endswith(suffixes):
                out.append(os.path.join(root, name))
    return out


def sha256_contribution(coll):
    """Hash of what an input contributes: each character with its destinations."""
    digest = hashlib.sha256()
    for ch in sorted(coll.chars):
        dest = ",".join(sorted(coll.chars[ch]["dest"]))
        digest.update(("%04X=%s\n" % (ord(ch), dest)).encode("ascii"))
    return digest.hexdigest()


def cjk_counts(coll):
    jp = set(coll.routed("jp"))
    sc = set(coll.routed("sc"))
    kr = set(coll.routed("kr"))
    return jp, sc, kr


def relative_argument(value):
    """An argument as it is recorded: repository-relative, never a local path."""
    if not os.path.isabs(value):
        return value.replace(os.sep, "/")
    try:
        rel = os.path.relpath(value, REPO)
    except ValueError:
        return os.path.basename(value)
    if rel.startswith(".."):
        return os.path.basename(value)
    return rel.replace(os.sep, "/")


def invocation(argv):
    parts = ["python", "scripts/font/measure_cjk_set.py"]
    for item in argv:
        if item.startswith("--"):
            parts.append(item)
        else:
            parts.append(relative_argument(item))
    return " ".join(parts)


def definition_check(coll):
    """Characters a definition may misjudge, for the record.

    Returns (script characters sent to the existing face, assigned-nowhere code
    points inside a Han or Hangul range).
    """
    outside = []
    unassigned = []
    for ch, info in sorted(coll.chars.items()):
        name = unicodedata.name(ch, "")
        if info["dest"] == {"existing"}:
            if name.startswith(SCRIPT_NAME_PREFIXES):
                outside.append(ord(ch))
        elif unicodedata.category(ch) == "Cn":
            unassigned.append(ord(ch))
    return outside, unassigned


def parse_previous(path):
    """(sets, hashes) of an existing measurement, or (None, {}) when unusable."""
    if not os.path.isfile(path):
        return None, {}
    try:
        sets = cov.read_measured_set(path)
    except (OSError, ValueError, cov.ToolError):
        return None, {}
    hashes = {}
    with open(path, "rb") as fh:
        for line in fh.read().decode("utf-8").split("\n"):
            found = HASH_LINE.match(line)
            if found:
                hashes[found.group("name")] = found.group("hash")
    return sets, hashes


def listing(cps):
    return " ".join("U+%04X" % cp for cp in sorted(cps)) or "none"


def delta_lines(previous, current):
    if previous is None:
        return ["first measurement (no earlier file to compare with)"]
    lines = []
    for key in cov.CJK_FACES:
        added = current[key] - previous[key]
        removed = previous[key] - current[key]
        lines.append(
            "%s: added %s; removed %s" % (key, listing(added), listing(removed))
        )
    return lines


def render(inv, sets, groups, hashes, checked, delta):
    jp, sc, kr = sets["jp"], sets["sc"], sets["kr"]
    shared = jp & sc
    out = []
    out.append(
        "# Measured CJK set: the Han and Hangul characters the shipped text uses."
    )
    out.append(
        "# Written by scripts/font/measure_cjk_set.py and by nothing else; this is"
    )
    out.append("# the drawing list of the CJK face. A line is <set>: <characters>.")
    out.append(
        "# jp holds the Japanese Han forms, sc the Simplified Han forms and kr the"
    )
    out.append(
        "# Hangul syllables. A Han character of a language self-name is in the set of"
    )
    out.append(
        "# its own language only; one used by any other text is in both jp and sc."
    )
    out.append("# invocation: %s" % inv)
    out.append(
        "# counts: jp %d, sc %d, kr %d; in both jp and sc %d; jp only %d; sc only %d"
        % (len(jp), len(sc), len(kr), len(shared), len(jp - sc), len(sc - jp))
    )
    for name, files, examined, contributed, digest in groups:
        out.append(
            "# input %s: %s, %d unique characters examined, %s; sha256 %s"
            % (name, files, examined, contributed, digest)
        )
    out.append("# definitions checked against %d unique characters:" % checked["total"])
    out.append(
        "#   script characters sent to the existing face: %s"
        % listing(checked["outside"])
    )
    out.append(
        "#   unassigned code points inside a Han or Hangul range: %s"
        % listing(checked["unassigned"])
    )
    out.append("# change since the previous measurement:")
    for line in delta:
        out.append("#   " + line)
    for key in cov.CJK_FACES:
        out.append("# %s code points: %s" % (key, listing(sets[key])))
    for key in cov.CJK_FACES:
        out.append("%s: %s" % (key, "".join(chr(cp) for cp in sorted(sets[key]))))
    return "\n".join(out) + "\n"


def build_parser():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--catalogue-dir", default=cov.DEFAULT_CATALOGUE_DIR)
    ap.add_argument("--text-dir", action="append", default=None)
    ap.add_argument("--py-dir", action="append", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--constants", default=cov.DEFAULT_CONSTANTS)
    ap.add_argument("--language-names", default=cov.DEFAULT_LANGUAGE_NAMES)
    ap.add_argument(
        "--check",
        action="store_true",
        help="measure and compare with the file; write nothing",
    )
    return ap


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    cov.make_console_safe()
    try:
        ranges = cov.load_ranges(args.constants)
        endonyms = cov.load_endonyms(args.language_names)
    except cov.ToolError as exc:
        print("cannot read the definitions: %s" % exc)
        return 2
    if endonyms is None:
        print("cannot measure: %s not found" % cov.safe(args.language_names))
        return 2
    known = cov.known_languages(endonyms)
    endonym_texts = {text: lang for lang, text in endonyms.items()}
    text_dirs = args.text_dir if args.text_dir is not None else [DEFAULT_GUIDE]
    py_dirs = args.py_dir if args.py_dir is not None else [DEFAULT_PACKAGE]

    failures = 0
    total = cov.Collector(ranges)
    groups = []  # (name, files text, examined, contribution text, hash)

    # catalogues
    catalogues = cov.discover_catalogues(args.catalogue_dir)
    if not catalogues:
        print("no catalogue found: no pixelart_*.ts in the catalogue folder")
        failures += 1
    mine = cov.Collector(ranges)
    for path in catalogues:
        try:
            lang, count = cov.read_catalogue(path, mine, known)
        except cov.ToolError as exc:
            print(exc)
            failures += 1
            continue
        print(
            "catalogue %s: language %s, read %d unique characters"
            % (cov.safe(os.path.basename(path)), lang or "unknown", count)
        )
    groups.append(
        (
            "catalogues",
            "%d files" % len(catalogues),
            len(mine.chars),
            mine,
            sha256_files(catalogues, args.catalogue_dir) if catalogues else "0" * 64,
        )
    )
    total.merge(mine)

    # guide trees
    for folder in text_dirs:
        mine = cov.Collector(ranges)
        nfiles, problems = cov.read_text_files(folder, mine, known)
        for line in problems:
            print(line)
        failures += len(problems)
        files = walk_files(folder, (".md", ".json"))
        print(
            "guide tree %s: %d .md/.json files read"
            % (cov.safe(relative_argument(folder)), nfiles)
        )
        if nfiles == 0:
            print("no .md or .json file below the guide folder")
            failures += 1
        name = "guide tree"
        if len(text_dirs) > 1:
            name += " %s" % cov.safe(os.path.basename(os.path.normpath(folder)))
        groups.append(
            (
                name,
                "%d files" % nfiles,
                len(mine.chars),
                mine,
                sha256_files(files, folder) if files else "0" * 64,
            )
        )
        total.merge(mine)

    # language self-names
    mine = cov.Collector(ranges)
    cov.read_endonyms(endonyms, mine)
    digest = hashlib.sha256()
    for lang in sorted(endonyms):
        digest.update(("%s=%s\n" % (lang, endonyms[lang])).encode("utf-8"))
    groups.append(
        (
            "endonyms",
            "%d labels" % len(endonyms),
            len(mine.chars),
            mine,
            digest.hexdigest(),
        )
    )
    total.merge(mine)

    # python string literals
    for folder in py_dirs:
        mine = cov.Collector(ranges)
        nfiles, problems = cov.read_py_literals(folder, mine, endonym_texts)
        for line in problems:
            print(line)
        failures += len(problems)
        print(
            "python string literals of %s: %d files read"
            % (cov.safe(os.path.basename(os.path.normpath(folder))), nfiles)
        )
        if nfiles == 0:
            print("no .py file below the python folder")
            failures += 1
        name = "python literals"
        if len(py_dirs) > 1:
            name += " %s" % cov.safe(os.path.basename(os.path.normpath(folder)))
        groups.append(
            (
                name,
                "%d files" % nfiles,
                len(mine.chars),
                mine,
                sha256_contribution(mine),
            )
        )
        total.merge(mine)

    if not total.chars:
        print("nothing examined")
        return 1

    jp, sc, kr = cjk_counts(total)
    sets = {"jp": jp, "sc": sc, "kr": kr}
    parts = total.partition()
    print(
        "examined %d unique characters, routed: existing face %d, KR %d, JP only %d, "
        "SC only %d, JP and SC %d (sum %d)"
        % (
            len(total.chars),
            parts["existing"],
            parts["kr"],
            parts["jp"],
            parts["sc"],
            parts["jp+sc"],
            sum(parts.values()),
        )
    )
    if sum(parts.values()) != len(total.chars):
        print("routing error: routed counts do not add up to the examined total")
        failures += 1

    group_rows = []
    for name, files, examined, mine, digest in groups:
        j, s, k = cjk_counts(mine)
        contributed = "Han+Hangul jp %d, sc %d, kr %d" % (len(j), len(s), len(k))
        print("input %s (%s): examined %d, %s" % (name, files, examined, contributed))
        group_rows.append((name, files, examined, contributed, digest))
    print(
        "measured: JP %d, SC %d, Hangul %d; in both JP and SC %d; JP only %d; "
        "SC only %d"
        % (len(jp), len(sc), len(kr), len(jp & sc), len(jp - sc), len(sc - jp))
    )

    outside, unassigned = definition_check(total)
    print(
        "definitions: script characters sent to the existing face: %s; "
        "unassigned code points inside a range: %s"
        % (listing(outside), listing(unassigned))
    )
    checked = {"total": len(total.chars), "outside": outside, "unassigned": unassigned}

    previous, previous_hashes = parse_previous(args.out)
    delta = delta_lines(previous, sets)
    for line in delta:
        print("change: " + line)
    new_hashes = {row[0]: row[4] for row in group_rows}
    same = previous is not None and previous == sets and previous_hashes == new_hashes

    if args.check:
        if previous is None:
            print("check: no readable measurement at the output file")
            failures += 1
        elif previous != sets:
            print("check: the file differs from the measurement")
            failures += 1
        else:
            print("check: the file holds the measured sets")
    elif failures:
        print("not written: %d problem(s) above" % failures)
    elif same:
        print("unchanged: the file already holds this measurement")
    else:
        text = render(invocation(argv), sets, group_rows, new_hashes, checked, delta)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as fh:
            fh.write(text.encode("utf-8"))
        print("written: %s" % cov.safe(relative_argument(args.out)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
