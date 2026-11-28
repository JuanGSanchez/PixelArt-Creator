"""Citation records of the Han drawings, the no-entry class and its membership code.

Standard library only; nothing here imports fontTools or the glyph-source library.
build_nifen_art.py imports it for the lint of the CJK face. It can also be run on
its own to print the membership of a measured set in the two Japanese lists:

    python scripts/font/han_citations.py membership --set <measured-set> \\
        --joyo <file> --hyogai <file>

What the records say (fonts-src/nifen-art-cjk/han-citations.txt, one per line,
fields separated by " | ", comments start with #):

    JP | U+65E5 | joyo-2010     | page=<n> pos=<entry No. in the Joyo list> | via=<id>
    JP | U+xxxx | hyogai-2000   | page=<n> slot=<No.> | via=<id>
    SC | U+65E5 | tongyong-2013 | page=<n> cell=<0001-8105> | via=<id>
    JP | U+77E9 | no-entry      | absent=joyo-2010,hyogai-2000 | via=membership

A Japanese-form drawing cites the Joyo kanji table or the table of forms for
characters outside it; a Simplified-form drawing cites the table of general standard
Chinese characters. A character of the Japanese-form set that is listed in neither
Japanese table is a member of the no-entry class, and its Japanese-form drawing
carries the no-entry record: the value no-entry, the two lists it is absent from, and
no place. The class is measured from the two lists by an acceptance run, which writes
no-entry-class.txt; every other run judges against that recorded class and fails when
a part it is bound to has changed.
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
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

sys.dont_write_bytecode = True

CITATIONS_NAME = "han-citations.txt"
CLASS_NAME = "no-entry-class.txt"
MEASURED_REL = ("coverage", "measured-set.txt")

# The standards a record may name, and the one value that names none.
JOYO = "joyo-2010"
HYOGAI = "hyogai-2000"
TONGYONG = "tongyong-2013"
NO_ENTRY = "no-entry"
STANDARDS = (JOYO, HYOGAI, TONGYONG, NO_ENTRY)
SET_STANDARDS = {"JP": (JOYO, HYOGAI), "SC": (TONGYONG,)}
ABSENT_FROM = "%s,%s" % (JOYO, HYOGAI)
# The instruments that may be named by via=. It is information for a reader; the check
# validates only that it is present and one of these. template-identity is the identity
# test of a slot of the table of forms against the recorded character; identity-review
# is the two-reader identity check of a cell or slot.
VIA_TOKENS = (
    "textlayer",
    "hyogai-confirmed",
    "index-agree",
    "membership",
    "template-identity",
    "identity-review",
)
# The two lists an acceptance run reads are the lists of record, and they are named by
# their file names: an acceptance run is refused unless it is given a file with each of
# these names, both in one folder. The folder itself is not named here.
JOYO_LIST_NAME = "joyo-2010.txt"
HYOGAI_LIST_NAME = "hyogai-2000-checked.txt"
# Upper bounds of the places: the table sizes of the three standards.
JOYO_ENTRIES = 2136
HYOGAI_ENTRIES = 1022
TONGYONG_CELLS = 8105

# How the inputs are named in what the check prints. The binding of a recorded class is
# to three inputs, and a stale class names the one that differs.
INPUT_JP_SET = "jp-set"
INPUT_JOYO = "joyo-list"
INPUT_HYOGAI = "hyogai-list"
INPUT_TEXT = {
    INPUT_JP_SET: "the Japanese-form set",
    INPUT_JOYO: "the Jōyō kanji table's list",
    INPUT_HYOGAI: "表外漢字字体表's list",
}

CP_TEXT = re.compile(r"^U\+([0-9A-F]{4,6})$")
VS_RANGES = ((0xFE00, 0xFE0F), (0xE0100, 0xE01EF), (0x180B, 0x180F))


class HanCitationError(Exception):
    """An input of the citation check cannot be read or is not in its form."""


def cp_label(cp: int) -> str:
    return "U+%04X" % cp


def cp_pair(cp: int) -> str:
    return "%s %s" % (cp_label(cp), chr(cp))


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(path: str) -> bytes:
    if not os.path.isfile(path):
        raise HanCitationError("%s is missing" % os.path.basename(path))
    with open(path, "rb") as fh:
        return fh.read()


def decode(data: bytes, name: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise HanCitationError("%s is not UTF-8" % name)


# --------------------------------------------------------------------------
# The measured set and the Japanese-form set's hash
# --------------------------------------------------------------------------


def parse_measured(path: str) -> Dict[str, Set[int]]:
    """The measured set file: {"jp": cps, "sc": cps, "kr": cps}. Strict."""
    name = os.path.basename(path)
    text = decode(read_bytes(path), name)
    sets: Dict[str, Set[int]] = {}
    for number, raw in enumerate(text.split("\n"), 1):
        if not raw or raw.startswith("#"):
            continue
        label, sep, rest = raw.partition(":")
        if not sep or label not in ("jp", "sc", "kr") or label in sets:
            raise HanCitationError(
                "%s:%d is not a '<set>: <characters>' line" % (name, number)
            )
        sets[label] = set(ord(c) for c in rest.strip())
    for label in ("jp", "sc", "kr"):
        if label not in sets:
            raise HanCitationError("%s has no %s line" % (name, label))
    return sets


def jp_set_text(cps: Sequence[int]) -> str:
    """The Japanese-form set as the class records it: U+XXXX and LF per code point,
    ascending."""
    return "".join("%s\n" % cp_label(cp) for cp in sorted(cps))


def jp_set_line(cps: Sequence[int]) -> str:
    return "%s: count=%d sha256=%s" % (
        INPUT_JP_SET,
        len(cps),
        sha256_of(jp_set_text(cps).encode("utf-8")),
    )


# --------------------------------------------------------------------------
# The two lists and the membership of a set in them
# --------------------------------------------------------------------------


@dataclass
class ListFile:
    """A list as a run read it: its bytes, hash and the text."""

    path: str
    name: str
    size: int
    sha256: str
    text: str


def read_list(path: str) -> ListFile:
    name = os.path.basename(path)
    data = read_bytes(path)
    return ListFile(path, name, len(data), sha256_of(data), decode(data, name))


def split_lines(text: str) -> List[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def cp_name(cp: int) -> str:
    return unicodedata.name(chr(cp), "")


def is_vs(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in VS_RANGES)


def is_han(cp: int) -> bool:
    return cp_name(cp).startswith(
        ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH")
    )


def unchecked_slots(header: Sequence[str]) -> List[int]:
    """The slot numbers the header of a list marks as not yet checked: the numbers after
    '(table No.):' up to the line that begins '(In rows', which names another matter."""
    out: List[int] = []
    active = False
    for line in header:
        if not active:
            if "(table No.):" in line:
                active = True
                tail = line.split("(table No.):", 1)[1]
                out.extend(int(n) for n in re.findall(r"[0-9]+", tail))
            continue
        if re.match(r"#\s+\(In rows", line):
            break
        out.extend(int(n) for n in re.findall(r"[0-9]+", line))
    return out


@dataclass
class ListEntries:
    """What a one-character-per-line list holds, as read."""

    header: List[str] = field(default_factory=list)
    entries: List[Tuple[int, int]] = field(default_factory=list)  # (slot, cp)
    bad_lines: List[Tuple[int, str]] = field(default_factory=list)  # (slot, why)
    duplicates: List[int] = field(default_factory=list)  # cps listed twice
    # (slot, cp, the single code point NFC gives it or None): compatibility ideographs
    compat: List[Tuple[int, int, Optional[int]]] = field(default_factory=list)


def parse_entries(text: str) -> ListEntries:
    """Every non-comment line is one entry; its slot is its 1-based position among them.
    A line that is not exactly one Han code point is reported and not an entry."""
    lines = split_lines(text)
    out = ListEntries()
    out.header = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if not ln.startswith("#")]
    for slot, ln in enumerate(body, 1):
        cps = [ord(c) for c in ln]
        if not cps:
            out.bad_lines.append((slot, "empty line"))
        elif len(cps) > 1:
            out.bad_lines.append((slot, "%d code points" % len(cps)))
        elif is_vs(cps[0]):
            out.bad_lines.append((slot, "variation selector alone"))
        elif not is_han(cps[0]):
            out.bad_lines.append((slot, "not a Han code point"))
        else:
            if cp_name(cps[0]).startswith("CJK COMPATIBILITY IDEOGRAPH"):
                folded = unicodedata.normalize("NFC", chr(cps[0]))
                out.compat.append(
                    (slot, cps[0], ord(folded) if len(folded) == 1 else None)
                )
            out.entries.append((slot, cps[0]))
    seen = Counter(cp for _slot, cp in out.entries)
    out.duplicates = sorted(cp for cp, n in seen.items() if n > 1)
    return out


CATEGORIES = ("joyo", "hyogai_checked", "hyogai_unchecked", "hyogai_mixed", "neither")


def classify(
    cp: int,
    joyo: Set[int],
    hyogai_slots: Dict[int, List[int]],
    unchecked: Set[int],
) -> str:
    """joyo | hyogai_checked | hyogai_unchecked | hyogai_mixed | neither.

    A character in the Joyo list is joyo whatever its other standing. Outside it, a
    character listed only at entries the list marks unchecked is hyogai_unchecked: its
    membership turns on an unchecked entry."""
    if cp in joyo:
        return "joyo"
    slots = hyogai_slots.get(cp)
    if not slots:
        return "neither"
    flags = {s in unchecked for s in slots}
    if flags == {False}:
        return "hyogai_checked"
    if flags == {True}:
        return "hyogai_unchecked"
    return "hyogai_mixed"


def tally(
    cps: Sequence[int],
    joyo: Set[int],
    hyogai_slots: Dict[int, List[int]],
    unchecked: Set[int],
) -> Dict[str, List[int]]:
    groups: Dict[str, List[int]] = {c: [] for c in CATEGORIES}
    for cp in cps:
        groups[classify(cp, joyo, hyogai_slots, unchecked)].append(cp)
    return groups


@dataclass
class Membership:
    """The membership of a set in the two lists."""

    counts: Dict[str, int]
    members: List[int]  # the no-entry class, ascending
    apart: List[Tuple[int, int]]  # (cp, slot): outside Joyo, listed only at unchecked
    mixed: List[int]  # outside Joyo, listed at a checked and at an unchecked entry
    unchecked: int
    controls: List[Tuple[str, bool]]
    joyo: ListFile
    hyogai: ListFile


def membership_controls(
    joyo: Set[int], hyogai_slots: Dict[int, List[int]], unchecked: Set[int]
) -> List[Tuple[str, bool]]:
    """The thirteen controls of the membership code, run before any number is used:
    seven that the list validator discriminates, one for the classifier, and five on
    the lists that were given."""
    out: List[Tuple[str, bool]] = []
    synthetic = "\n".join(
        [
            "# header",
            "常",
            "常",
            "",
            "常用",
            "A",
            chr(0xFA10),
            "辻\U000e0100",
            "\U000e0100",
            "鱻",
        ]
    )
    v = parse_entries(synthetic + "\n")
    bad = dict(v.bad_lines)
    checks = (
        ("validator: duplicate found", v.duplicates == [0x5E38]),
        ("validator: empty line found", bad.get(3) == "empty line"),
        ("validator: two-code-point line found", bad.get(4) == "2 code points"),
        ("validator: non-Han found", bad.get(5) == "not a Han code point"),
        (
            "validator: compatibility ideograph found, NFC differs",
            v.compat == [(6, 0xFA10, 0x585A)],
        ),
        (
            "validator: variation selectors found (2 lines)",
            bad.get(7) == "2 code points" and bad.get(8) == "variation selector alone",
        ),
        (
            "validator: valid entries counted (slots 1, 2, 6, 9)",
            [s for s, _c in v.entries] == [1, 2, 6, 9],
        ),
    )
    out.extend(checks)
    cat = tally([1, 2, 3, 4, 5], {1}, {2: [10], 3: [11], 5: [10, 11]}, {11})
    out.append(
        (
            "classifier on synthetic lists",
            cat
            == {
                "joyo": [1],
                "hyogai_checked": [2],
                "hyogai_unchecked": [3],
                "hyogai_mixed": [5],
                "neither": [4],
            },
        )
    )
    out.append(
        (
            "the Joyo list holds U+5E38 (a known Joyo character)",
            0x5E38 in joyo
            and classify(0x5E38, joyo, hyogai_slots, unchecked) == "joyo",
        )
    )
    for cp in (0x9C7B, 0x20000):
        out.append(
            (
                "the lists hold neither %s" % cp_label(cp),
                classify(cp, joyo, hyogai_slots, unchecked) == "neither",
            )
        )
    first_checked = first_unchecked = None
    for slot, cp in sorted((s, c) for c, ss in hyogai_slots.items() for s in ss):
        if cp in joyo:
            continue
        if slot in unchecked and first_unchecked is None:
            first_unchecked = cp
        if slot not in unchecked and first_checked is None:
            first_checked = cp
    out.append(
        (
            "the first checked entry outside the Joyo list reads hyogai_checked",
            first_checked is not None
            and classify(first_checked, joyo, hyogai_slots, unchecked)
            == "hyogai_checked",
        )
    )
    out.append(
        (
            "the first unchecked entry outside the Joyo list reads hyogai_unchecked",
            first_unchecked is not None
            and classify(first_unchecked, joyo, hyogai_slots, unchecked)
            == "hyogai_unchecked",
        )
    )
    return out


def measure_membership(
    jp_cps: Sequence[int], joyo_path: str, hyogai_path: str
) -> Membership:
    """Classify the Japanese-form set against the two lists, as written (code points,
    no normalisation). Raises HanCitationError when a list cannot be read."""
    joyo_file = read_list(joyo_path)
    hyogai_file = read_list(hyogai_path)
    joyo_entries = parse_entries(joyo_file.text)
    hyogai_entries = parse_entries(hyogai_file.text)
    joyo = set(cp for _slot, cp in joyo_entries.entries)
    hyogai_slots: Dict[int, List[int]] = defaultdict(list)
    for slot, cp in hyogai_entries.entries:
        hyogai_slots[cp].append(slot)
    unchecked = set(unchecked_slots(hyogai_entries.header))
    controls = membership_controls(joyo, dict(hyogai_slots), unchecked)
    groups = tally(sorted(jp_cps), joyo, dict(hyogai_slots), unchecked)
    apart = sorted(
        (cp, slot) for cp in groups["hyogai_unchecked"] for slot in hyogai_slots[cp]
    )
    return Membership(
        counts={c: len(groups[c]) for c in CATEGORIES},
        members=sorted(groups["neither"]),
        apart=apart,
        mixed=sorted(groups["hyogai_mixed"]),
        unchecked=len(unchecked),
        controls=controls,
        joyo=joyo_file,
        hyogai=hyogai_file,
    )


# --------------------------------------------------------------------------
# The recorded class (no-entry-class.txt)
# --------------------------------------------------------------------------

CLASS_HEADER = (
    "# The no-entry class, recorded by an acceptance run. Written by the check only."
)


def input_lines(
    jp_cps: Sequence[int], joyo: ListFile, hyogai: ListFile, unchecked: int
):
    """The three input lines that bind a class, as recorded."""
    return [
        jp_set_line(jp_cps),
        "%s: name=%s bytes=%d sha256=%s"
        % (INPUT_JOYO, joyo.name, joyo.size, joyo.sha256),
        "%s: name=%s bytes=%d sha256=%s unchecked=%d"
        % (INPUT_HYOGAI, hyogai.name, hyogai.size, hyogai.sha256, unchecked),
    ]


def run_suffix(lines: Sequence[str]) -> str:
    return sha256_of(("".join(ln + "\n" for ln in lines)).encode("utf-8"))[:12]


def class_text(run_id: str, lines: Sequence[str], members: Sequence[int], apart) -> str:
    out = [CLASS_HEADER, "run: %s" % run_id]
    out.extend(lines)
    out.extend("CLASS %s" % cp_pair(cp) for cp in sorted(members))
    out.extend("APART %s No.%d" % (cp_pair(cp), slot) for cp, slot in sorted(apart))
    return "".join(ln + "\n" for ln in out)


def new_run_id(lines: Sequence[str]) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "%s-%s" % (stamp, run_suffix(lines))


@dataclass
class Recorded:
    """A class as an acceptance run recorded it, with the three inputs it binds."""

    run_id: str
    jp_count: int
    jp_sha256: str
    joyo_name: str
    joyo_bytes: int
    joyo_sha256: str
    hyogai_name: str
    hyogai_bytes: int
    hyogai_sha256: str
    unchecked: int
    members: List[int]
    apart: List[Tuple[int, int]]


def parse_recorded(path: str) -> Recorded:
    """Read no-entry-class.txt strictly. Raises HanCitationError naming the line."""
    name = os.path.basename(path)
    data = read_bytes(path)
    if b"\r" in data:
        raise HanCitationError("%s holds a carriage return" % name)
    text = decode(data, name)
    if not text.endswith("\n"):
        raise HanCitationError("%s does not end with a line feed" % name)
    lines = text[:-1].split("\n")

    def need(index: int, pattern: str, what: str):
        if index >= len(lines):
            raise HanCitationError("%s ends before its %s line" % (name, what))
        m = re.match(pattern + "$", lines[index])
        if not m:
            raise HanCitationError("%s:%d is not the %s line" % (name, index + 1, what))
        return m

    if not lines or not lines[0].startswith("# "):
        raise HanCitationError("%s:1 is not the comment line" % name)
    run = need(1, r"run: ([0-9]{8}T[0-9]{6}Z-[0-9a-f]{12})", "run")
    jp = need(2, r"jp-set: count=(\d+) sha256=([0-9a-f]{64})", INPUT_JP_SET)
    joyo = need(
        3,
        r"joyo-list: name=([A-Za-z0-9._-]+) bytes=(\d+) sha256=([0-9a-f]{64})",
        INPUT_JOYO,
    )
    hyo = need(
        4,
        r"hyogai-list: name=([A-Za-z0-9._-]+) bytes=(\d+) sha256=([0-9a-f]{64}) "
        r"unchecked=(\d+)",
        INPUT_HYOGAI,
    )
    run_id = run.group(1)
    if run_id.rsplit("-", 1)[1] != run_suffix(lines[2:5]):
        raise HanCitationError(
            "%s:2 the run id does not match the three input lines" % name
        )
    members: List[int] = []
    apart: List[Tuple[int, int]] = []
    for index in range(5, len(lines)):
        line = lines[index]
        m = re.match(r"CLASS U\+([0-9A-F]{4,6}) (.)$", line)
        a = re.match(r"APART U\+([0-9A-F]{4,6}) (.) No\.(\d+)$", line)
        if m and not apart:
            cp = int(m.group(1), 16)
            if ord(m.group(2)) != cp:
                raise HanCitationError(
                    "%s:%d the character is not the code point" % (name, index + 1)
                )
            if members and cp <= members[-1]:
                raise HanCitationError(
                    "%s:%d is not in ascending order" % (name, index + 1)
                )
            members.append(cp)
        elif a:
            cp = int(a.group(1), 16)
            if ord(a.group(2)) != cp:
                raise HanCitationError(
                    "%s:%d the character is not the code point" % (name, index + 1)
                )
            apart.append((cp, int(a.group(3))))
        else:
            raise HanCitationError(
                "%s:%d is not a CLASS or APART line (CLASS lines come first)"
                % (name, index + 1)
            )
    return Recorded(
        run_id,
        int(jp.group(1)),
        jp.group(2),
        joyo.group(1),
        int(joyo.group(2)),
        joyo.group(3),
        hyo.group(1),
        int(hyo.group(2)),
        hyo.group(3),
        int(hyo.group(4)),
        members,
        apart,
    )


# --------------------------------------------------------------------------
# The run: acceptance or any other, and the class it judges against
# --------------------------------------------------------------------------


@dataclass
class RunMode:
    """Which kind of run this is. An acceptance run requires both lists and measures
    the class from them; any other run may be given the lists, to compare them with the
    ones the recorded class is bound to."""

    acceptance: bool = False
    joyo_path: Optional[str] = None
    hyogai_path: Optional[str] = None


@dataclass
class ClassView:
    """The class a run judges against, with what it prints about it and the findings
    that the stale rule adds."""

    kind: str  # measured | recorded | none
    run_id: str = ""
    members: List[int] = field(default_factory=list)
    apart: List[Tuple[int, int]] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)
    file_text: Optional[str] = None  # an acceptance run's record, to be written
    controls: List[Tuple[str, bool]] = field(default_factory=list)
    jp_count: int = 0

    def member_set(self) -> Set[int]:
        return set(self.members)


def listing(cps: Sequence[int]) -> str:
    return ", ".join(cp_pair(cp) for cp in cps) if cps else "none"


def apart_listing(apart: Sequence[Tuple[int, int]]) -> str:
    return (
        ", ".join("%s No.%d" % (cp_pair(cp), slot) for cp, slot in apart)
        if apart
        else "none"
    )


def acceptance_view(cjk_dir: str, mode: RunMode, jp_cps: Sequence[int]) -> ClassView:
    """An acceptance run: measure the class from the two lists, in this process, and
    prepare the record that binds it to its three inputs."""
    if not mode.joyo_path or not mode.hyogai_path:
        raise HanCitationError("an acceptance run needs both lists")
    mem = measure_membership(jp_cps, mode.joyo_path, mode.hyogai_path)
    for item in (mem.joyo, mem.hyogai):
        if not re.fullmatch(r"[A-Za-z0-9._-]+", item.name):
            raise HanCitationError(
                "the list file name %r cannot be recorded: letters, digits, dot, "
                "underscore and hyphen only" % item.name
            )
    view = ClassView("measured", controls=mem.controls, jp_count=len(jp_cps))
    lines = input_lines(jp_cps, mem.joyo, mem.hyogai, mem.unchecked)
    view.run_id = new_run_id(lines)
    failed = [n for n, ok in mem.controls if not ok]
    view.members = mem.members
    view.apart = mem.apart
    view.info.append(
        "acceptance run %s: the class is measured from the two lists in this run"
        % view.run_id
    )
    view.info.append(
        "no-entry class (measured in this acceptance run %s): %s - count %d"
        % (view.run_id, listing(mem.members), len(mem.members))
    )
    view.info.append(
        "printed apart, on an unchecked entry: %s - count %d"
        % (apart_listing(mem.apart), len(mem.apart))
    )
    if mem.mixed:
        view.info.append(
            "listed at both a checked and an unchecked entry, not printed apart: %s"
            % listing(mem.mixed)
        )
    view.info.append(
        "entries not yet checked: %d (information; a class member's place in the class "
        "assumes that no unchecked entry lists it)" % mem.unchecked
    )
    for key, item in ((INPUT_JOYO, mem.joyo), (INPUT_HYOGAI, mem.hyogai)):
        view.info.append(
            "list read: %s %s sha256 %s bytes %d"
            % (key, item.path.replace(os.sep, "/"), item.sha256, item.size)
        )
    view.info.append(
        "lists compared: %s %s equal; %s %s equal (the class was measured from them "
        "in this run)"
        % (mem.joyo.name, mem.joyo.sha256[:12], mem.hyogai.name, mem.hyogai.sha256[:12])
    )
    if failed:
        view.violations.append(
            "the membership code failed its controls (%s): no class is recorded"
            % "; ".join(failed)
        )
        view.members, view.apart = [], []
        return view
    view.file_text = class_text(view.run_id, lines, mem.members, mem.apart)
    return view


def recorded_view(cjk_dir: str, mode: RunMode, jp_cps: Sequence[int]) -> ClassView:
    """Any other run: judge against the class the last acceptance run recorded. The
    class is stale when the Japanese-form set differs from the recorded one, or when a
    list this run is given differs from the recorded one; each differing input is named.
    """
    path = os.path.join(cjk_dir, CLASS_NAME)
    view = ClassView("none", jp_count=len(jp_cps))
    given = {INPUT_JOYO: mode.joyo_path, INPUT_HYOGAI: mode.hyogai_path}
    files: Dict[str, ListFile] = {}
    for key, value in given.items():
        if value:
            files[key] = read_list(value)
    rec: Optional[Recorded] = None
    if os.path.exists(path):
        try:
            rec = parse_recorded(path)
        except HanCitationError as exc:
            view.violations.append(
                "%s is malformed and counts as no recorded class: %s"
                % (CLASS_NAME, exc)
            )
    if rec is None:
        view.info.append("no-entry class: none recorded on this run")
        view.info.append(
            "no recorded class means no class: no no-entry record is valid on this run"
        )
        view.info.append(_compared_line(files, None))
        return view
    view.kind = "recorded"
    view.run_id = rec.run_id
    view.members = list(rec.members)
    view.apart = list(rec.apart)
    here = jp_set_line(jp_cps)
    want = "%s: count=%d sha256=%s" % (INPUT_JP_SET, rec.jp_count, rec.jp_sha256)
    if here != want:
        view.violations.append(
            "STALE recorded class: %s differs [%s]: recorded %s, this run %s"
            % (
                INPUT_TEXT[INPUT_JP_SET],
                INPUT_JP_SET,
                want.split(": ", 1)[1],
                here.split(": ", 1)[1],
            )
        )
    recorded = {
        INPUT_JOYO: (rec.joyo_name, rec.joyo_bytes, rec.joyo_sha256),
        INPUT_HYOGAI: (rec.hyogai_name, rec.hyogai_bytes, rec.hyogai_sha256),
    }
    for key, item in files.items():
        name, size, digest = recorded[key]
        if item.sha256 != digest or item.size != size:
            view.violations.append(
                "STALE recorded class: %s differs [%s]: recorded %s bytes=%d "
                "sha256=%s, this run was given %s bytes=%d sha256=%s"
                % (
                    INPUT_TEXT[key],
                    key,
                    name,
                    size,
                    digest,
                    item.name,
                    item.size,
                    item.sha256,
                )
            )
    view.info.append(
        "no-entry class (the recorded class of acceptance run %s; not measured on this "
        "run): %s - count %d" % (rec.run_id, listing(rec.members), len(rec.members))
    )
    view.info.append(
        "printed apart (recorded by acceptance run %s; information, decides nothing on "
        "this run): %s - count %d"
        % (rec.run_id, apart_listing(rec.apart), len(rec.apart))
    )
    view.info.append(
        "entries not yet checked (recorded by acceptance run %s): %d (information)"
        % (rec.run_id, rec.unchecked)
    )
    view.info.append(_compared_line(files, recorded))
    return view


def _compared_line(files: Dict[str, ListFile], recorded) -> str:
    """The line every run prints about the lists: compared with the recorded ones,
    or not given."""
    if not files:
        return "lists: not given on this run, not compared"
    parts = []
    for key in (INPUT_JOYO, INPUT_HYOGAI):
        item = files.get(key)
        if item is None:
            parts.append("%s not given on this run, not compared" % key)
        elif recorded is None:
            parts.append(
                "%s %s no recorded list to compare with" % (item.name, item.sha256[:12])
            )
        else:
            same = item.sha256 == recorded[key][2] and item.size == recorded[key][1]
            parts.append(
                "%s %s %s"
                % (item.name, item.sha256[:12], "equal" if same else "DIFFERS")
            )
    return "lists compared: " + "; ".join(parts)


def class_view(cjk_dir: str, mode: RunMode, jp_cps: Sequence[int]) -> ClassView:
    if mode.acceptance:
        return acceptance_view(cjk_dir, mode, jp_cps)
    return recorded_view(cjk_dir, mode, jp_cps)


def list_refusals(joyo_path: str, hyogai_path: str) -> List[str]:
    """Why an acceptance run must be refused for the lists it was given, one line per
    reason (empty when the lists are the lists of record by name and lie in one folder).
    Only the file names and the folders of the given paths are looked at; no list is
    opened."""
    out: List[str] = []
    for option, path, required in (
        ("--joyo-list", joyo_path, JOYO_LIST_NAME),
        ("--hyogai-list", hyogai_path, HYOGAI_LIST_NAME),
    ):
        given = os.path.basename(path)
        if given != required:
            out.append(
                "refused: %s is named %r, and an acceptance run needs the file name %r"
                % (option, given, required)
            )
    given_in = [os.path.dirname(p) or "." for p in (joyo_path, hyogai_path)]
    folders = [os.path.normcase(os.path.abspath(folder)) for folder in given_in]
    if folders[0] != folders[1]:
        out.append(
            "refused: --joyo-list and --hyogai-list lie in two folders (%s and %s), "
            "and an acceptance run needs both lists in one folder"
            % tuple(folder.replace(os.sep, "/") for folder in given_in)
        )
    return out


def write_class_file(cjk_dir: str, view: ClassView) -> None:
    """Write the record of an acceptance run (binary, LF): to a temporary file in the
    same folder, then replacing the old file in one step. A file that is not replaced
    is left as it was."""
    if view.file_text is None:
        raise HanCitationError("there is no class record to write")
    final = os.path.join(cjk_dir, CLASS_NAME)
    fd, tmp = tempfile.mkstemp(dir=cjk_dir, prefix=".%s-" % CLASS_NAME, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(view.file_text.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# --------------------------------------------------------------------------
# The citation records
# --------------------------------------------------------------------------


@dataclass
class Citation:
    """One record of han-citations.txt."""

    set_key: str
    cp: int
    standard: str
    place: Dict[str, str]
    via: str
    line: int

    def text(self) -> str:
        if self.standard == NO_ENTRY:
            return "no-entry (absent from %s)" % ABSENT_FROM
        return "%s %s" % (
            self.standard,
            " ".join("%s=%s" % (k, v) for k, v in self.place.items()),
        )


@dataclass
class Citations:
    records: Dict[Tuple[int, str], Citation] = field(default_factory=dict)
    # Records that cannot be used: (cp, set) -> why. A drawing of one counts as uncited.
    invalid: Dict[Tuple[int, str], str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    present: bool = False


PLACE_FIELDS = {
    JOYO: ("page", "pos"),
    HYOGAI: ("page", "slot"),
    TONGYONG: ("page", "cell"),
}
PLACE_LIMITS = {"pos": JOYO_ENTRIES, "slot": HYOGAI_ENTRIES, "cell": TONGYONG_CELLS}


def _place(fields: str, keys: Sequence[str]) -> Dict[str, str]:
    """The place of a record: exactly the declared fields, in order, each a number."""
    parts = fields.split(" ")
    if len(parts) != len(keys):
        raise ValueError("the place must be %s" % " ".join("%s=<n>" % k for k in keys))
    out: Dict[str, str] = {}
    for part, key in zip(parts, keys):
        name, sep, value = part.partition("=")
        if not sep or name != key:
            raise ValueError(
                "the place must be %s" % " ".join("%s=<n>" % k for k in keys)
            )
        if key == "cell":
            if (
                not re.fullmatch(r"\d{4}", value)
                or not 1 <= int(value) <= TONGYONG_CELLS
            ):
                raise ValueError(
                    "cell must be four digits, 0001 to %04d" % TONGYONG_CELLS
                )
        else:
            if not re.fullmatch(r"[1-9]\d*", value):
                raise ValueError("%s must be a positive number" % key)
            if key in PLACE_LIMITS and int(value) > PLACE_LIMITS[key]:
                raise ValueError(
                    "%s is beyond the table (%d entries)" % (key, PLACE_LIMITS[key])
                )
        out[name] = value
    return out


def parse_citations(
    path: str, is_han: Optional[Callable[[int], bool]] = None
) -> Citations:
    """Read han-citations.txt strictly. A record that cannot be used is named by its
    line in errors and recorded in invalid, so its drawing counts as uncited. A
    missing file holds no record."""
    out = Citations()
    name = os.path.basename(path)
    if not os.path.exists(path):
        return out
    out.present = True
    data = read_bytes(path)
    if b"\r" in data:
        out.errors.append("%s holds a carriage return: the file is LF only" % name)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        out.errors.append("%s is not UTF-8" % name)
        return out
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        where = "%s:%d" % (name, number)
        fields = [f.strip() for f in line.split("|")]
        ident: Optional[Tuple[int, str]] = None
        try:
            if len(fields) != 5:
                raise ValueError(
                    "a record has five fields: set | code point | standard | place "
                    "| via"
                )
            set_key, cp_text, standard, place_text, via_text = fields
            if set_key not in SET_STANDARDS:
                raise ValueError("unknown set %r (JP or SC)" % set_key)
            m = CP_TEXT.match(cp_text)
            if not m:
                raise ValueError("%r is not a code point (U+XXXX)" % cp_text)
            cp = int(m.group(1), 16)
            ident = (cp, set_key)
            if is_han is not None and not is_han(cp):
                raise ValueError("%s is not a Han code point" % cp_label(cp))
            if standard not in STANDARDS:
                raise ValueError("unknown standard %r" % standard)
            if standard == NO_ENTRY:
                if place_text != "absent=%s" % ABSENT_FROM:
                    raise ValueError(
                        "a no-entry record carries absent=%s and no place" % ABSENT_FROM
                    )
                place: Dict[str, str] = {"absent": ABSENT_FROM}
            else:
                place = _place(place_text, PLACE_FIELDS[standard])
            if not via_text.startswith("via=") or via_text[4:] not in VIA_TOKENS:
                raise ValueError("via= must name one of %s" % ", ".join(VIA_TOKENS))
            record = Citation(set_key, cp, standard, place, via_text[4:], number)
            if ident in out.records or ident in out.invalid:
                out.errors.append(
                    "%s: a second record of %s set=%s" % (where, cp_label(cp), set_key)
                )
                out.invalid.setdefault(ident, "has two records (line %d)" % number)
                continue
            out.records[ident] = record
        except ValueError as exc:
            out.errors.append("%s: %s" % (where, exc))
            if ident is not None:
                out.invalid.setdefault(
                    ident, "its record at line %d is malformed" % number
                )
    return out


# --------------------------------------------------------------------------
# The judgement of the drawings
# --------------------------------------------------------------------------


@dataclass
class RuleResult:
    examined: int = 0
    violations: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)


@dataclass
class Judgement:
    citations: RuleResult = field(default_factory=RuleResult)
    no_borrow: RuleResult = field(default_factory=RuleResult)
    the_class: RuleResult = field(default_factory=RuleResult)
    shared: int = 0
    uncited: int = 0
    identical: int = 0


def _problem(
    record: Optional[Citation],
    set_key: str,
    cp: int,
    members: Set[int],
    kind: str,
) -> Optional[str]:
    """Why a record does not serve a drawing, or None when it does. kind says where the
    class came from: measured, recorded or none."""
    if record is None:
        return None
    allowed = SET_STANDARDS[set_key]
    if record.standard == NO_ENTRY:
        if set_key != "JP":
            return (
                "a no-entry record on a Simplified-form drawing: it is valid only on "
                "the Japanese-form drawing of a member of the no-entry class"
            )
        if kind == "none":
            return (
                "a no-entry record, but no class is recorded on this run: no "
                "no-entry record is valid"
            )
        if cp not in members:
            return (
                "a no-entry record, but %s is not a member of the no-entry class "
                "(%s)"
                % (
                    cp_label(cp),
                    "measured in this run" if kind == "measured" else "recorded",
                )
            )
        return None
    if set_key == "JP" and cp in members:
        return (
            "cites %s, but a member of the no-entry class has no standard entry "
            "and carries the no-entry record" % record.text()
        )
    if record.standard not in allowed:
        return "cites %s, which is not the standard named for a %s drawing (%s)" % (
            record.text(),
            "Japanese-form" if set_key == "JP" else "Simplified-form",
            " or ".join(allowed),
        )
    return None


def load_measured(cjk_dir: str) -> Tuple[Optional[Dict[str, Set[int]]], str]:
    """The measured set of a CJK folder, or None and why it cannot be read."""
    try:
        return parse_measured(os.path.join(cjk_dir, *MEASURED_REL)), ""
    except HanCitationError as exc:
        return None, str(exc)


def judge(
    cjk_dir: str,
    measured: Optional[Dict[str, Set[int]]],
    measured_error: str,
    drawings: Sequence[Tuple[int, str]],
    same_as: Dict[Tuple[int, str], str],
    reach: Callable[[Tuple[int, str]], Set[Tuple[object, str]]],
    pixels_of: Callable[[Tuple[int, str]], Optional[FrozenSet[Tuple[int, int]]]],
    han: Callable[[int], bool],
    view: ClassView,
    acceptance: bool,
) -> Judgement:
    """Judge the Han drawings of the CJK face. drawings are the (code point, set) pairs
    with a record in the jp or sc set; same_as holds the ones that name another set's
    drawing; reach gives everything a drawing is made of; pixels_of gives its bitmap."""
    out = Judgement()
    cit, nb, cls = out.citations, out.no_borrow, out.the_class
    members = view.member_set()

    # The measured set: the shared count and the Japanese-form set the class binds.
    jp_cps: List[int] = []
    shared: List[int] = []
    if measured is None:
        cit.violations.append(
            "%s: the shared count and the class need the measured set" % measured_error
        )
    else:
        jp_cps = sorted(measured["jp"])
        shared = sorted(measured["jp"] & measured["sc"])
    out.shared = len(shared)

    # The records, and what each drawing needs --------------------------------------
    cites = parse_citations(os.path.join(cjk_dir, CITATIONS_NAME), han)
    cit.violations.extend(cites.errors)
    han_drawings = sorted(d for d in drawings if d[1] in ("jp", "sc") and han(d[0]))
    drawn = set(han_drawings)
    shared_set = set(shared)
    judged: Dict[Tuple[int, str], str] = {}
    for cp, s in han_drawings:
        key = (cp, s.upper())
        required = cp in shared_set or (s == "jp" and cp in members)
        rec = cites.records.get(key)
        if key in cites.invalid:
            judged[key] = cites.invalid[key]
        elif rec is None and required:
            judged[key] = "has no citation record" + (
                " (a member of the no-entry class needs the no-entry record)"
                if s == "jp" and cp in members
                else ""
            )
    for key, rec in sorted(cites.records.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        why = _problem(rec, key[1], key[0], members, view.kind)
        if why is not None:
            judged[key] = why
    for key in sorted(cites.invalid):
        judged.setdefault(key, cites.invalid[key])
    for (cp, s), why in sorted(judged.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        line = cites.records[(cp, s)].line if (cp, s) in cites.records else None
        cit.violations.append(
            "%s set=%s%s: %s"
            % (
                cp_pair(cp),
                s.lower(),
                " (%s:%d)" % (CITATIONS_NAME, line) if line else "",
                why,
            )
        )
    out.uncited = len(judged)
    without_drawing = [k for k in cites.records if (k[0], k[1].lower()) not in drawn]
    cit.examined = len(shared) + len(cites.records) + len(cites.invalid)
    if not shared:
        cit.violations.append(
            "the shared count is 0: no Han character is in both the Japanese-form "
            "and the Simplified-form set"
        )
    cit.info.append(
        "shared characters (in both the Japanese-form and the Simplified-form set): %d"
        % len(shared)
    )
    cit.info.append(
        "drawings without a cited place, or citing another standard: %d" % out.uncited
    )
    cit.info.append(
        "citation records read: %d (JP %d, SC %d); records of a drawing not made "
        "yet: %d"
        % (
            len(cites.records),
            sum(1 for k in cites.records if k[1] == "JP"),
            sum(1 for k in cites.records if k[1] == "SC"),
            len(without_drawing),
        )
    )
    both = [cp for cp in shared if (cp, "jp") in drawn and (cp, "sc") in drawn]
    twins = []
    for cp in both:
        a, b = pixels_of((cp, "jp")), pixels_of((cp, "sc"))
        if a is not None and a == b:
            twins.append(cp)
    out.identical = len(twins)
    cit.info.append(
        "shared characters with both drawings made: %d; with the two drawings "
        "pixel-identical: %d (information)" % (len(both), len(twins))
    )
    for cp in twins:
        cit.info.append(
            "pixel-identical %s: JP %s / SC %s"
            % (
                cp_pair(cp),
                (
                    cites.records[(cp, "JP")].text()
                    if (cp, "JP") in cites.records
                    else "no place"
                ),
                (
                    cites.records[(cp, "SC")].text()
                    if (cp, "SC") in cites.records
                    else "no place"
                ),
            )
        )

    # No drawing takes the other set's drawing of the same code point -----------------
    nb.examined = len(han_drawings)
    for ident in han_drawings:
        cp, s = ident
        other = "sc" if s == "jp" else "jp"
        tag = "%s set=%s" % (cp_label(cp), s)
        if ident in same_as:
            nb.violations.append(
                "%s: same-as=%s is refused: a drawing is never shared with another "
                "form set" % (tag, same_as[ident])
            )
        if (cp, other) in reach(ident):
            nb.violations.append(
                "%s is made of the %s drawing of the same code point (by an alias or a "
                "recipe, directly or through other records)" % (tag, other)
            )
    nb.info.append("Han drawings examined for borrowing: %d" % len(han_drawings))

    # The class: measured or recorded, bound to its three inputs -----------------------
    cls.examined = len(jp_cps)
    cls.violations.extend(view.violations)
    cls.info.extend(view.info)
    if acceptance and view.kind == "measured":
        for cp, slot in view.apart:
            if (cp, "jp") in drawn:
                cls.violations.append(
                    "%s No.%d: its Japanese-form drawing is not accepted while the "
                    "character is printed apart on an unchecked entry"
                    % (cp_pair(cp), slot)
                )
    return out


# --------------------------------------------------------------------------
# Command line: the membership of a set in the two lists
# --------------------------------------------------------------------------


def cmd_membership(args: argparse.Namespace) -> int:
    try:
        sets = parse_measured(args.set)
        jp_cps = sorted(sets["jp"])
        mem = measure_membership(jp_cps, args.joyo, args.hyogai)
    except HanCitationError as exc:
        print("membership: %s" % exc)
        return 2
    print(
        "membership of the Japanese-form set (%d characters) in the two lists; "
        "nothing is written" % len(jp_cps)
    )
    for key, item in ((INPUT_JOYO, mem.joyo), (INPUT_HYOGAI, mem.hyogai)):
        print(
            "list read: %s %s sha256 %s bytes %d"
            % (key, item.path.replace(os.sep, "/"), item.sha256, item.size)
        )
    ok = all(good for _name, good in mem.controls)
    print(
        "membership controls: %d of %d pass"
        % (sum(1 for _n, good in mem.controls if good), len(mem.controls))
    )
    for name, good in mem.controls:
        print("  %s: %s" % ("PASS" if good else "FAIL", name))
    print(
        "Japanese-form set: joyo %d, hyogai at checked entries %d, hyogai at unchecked "
        "entries only %d, hyogai at both %d, neither %d"
        % tuple(mem.counts[c] for c in CATEGORIES)
    )
    print("no-entry class: %s - count %d" % (listing(mem.members), len(mem.members)))
    for cp in mem.members:
        print("CLASS %s" % cp_label(cp))
    print("printed apart: %s - count %d" % (apart_listing(mem.apart), len(mem.apart)))
    for cp, slot in mem.apart:
        print("APART %s No.%d" % (cp_label(cp), slot))
    print("UNCHECKED %d" % mem.unchecked)
    return 0 if ok else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser(
        "membership", help="print the membership; never writes the class file"
    )
    p.add_argument("--set", required=True, help="the measured set file")
    p.add_argument("--joyo", required=True, help="the Joyo list")
    p.add_argument("--hyogai", required=True, help="the list of the table of forms")
    args = ap.parse_args(argv)
    return cmd_membership(args)


if __name__ == "__main__":
    sys.exit(main())
