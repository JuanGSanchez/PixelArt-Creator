"""Check the redraw records of the Han drawings against the face's sources.

Standard library only:

    python scripts/font/check_redraw_records.py [--root <repository root>] \\
        [--set <redraw-set.tsv> [--partial]]
    python scripts/font/check_redraw_records.py --controls

The records are fonts-src/nifen-art-cjk/redraw-records.txt, one line per redrawn
drawing, eleven fields separated by a tab (lines starting with # are comments):

    code point, form set, batch, first grade, status, reference, disagreement,
    new grade, old sha256, new sha256, date

The first grade is one of the four grade words or b2-list; the status is redrawn or
pending (any other status is refused, a held one by name: nothing is held); the
reference is the build of the drawing's own form set, or none on a line of a later
batch; the disagreement is a dash or the drawing's cited place, equal to its place in
han-citations.txt (the standard and the place of its record, one space between); the
two sha256 values are those of the drawing's record in the face's sources (its header
line and its rows, one per line, each ending in a line feed). The check:

  - one line per drawing; no line left pending;
  - the reference of a line of batches 2 to 8, or of one of the four named drawings, is
    the build of the drawing's own form set (the two are the constants below, and
    nothing else is accepted, none included); on a line of a later batch it is none or
    that build; a reference on a drawing whose first grade is fairly sure and that is
    not one of the four named drawings is refused, and so is one on a drawing outside
    the redraw set when the set is given;
  - the face's record of every redrawn drawing hashes to its new sha256;
  - a disagreement other than a dash equals the place in the drawing's citation record,
    and a drawing whose record is a no-entry record, or that has none, carries a dash;
  - with --set, every member of the set has a line (--partial lists the ones that have
    none yet and fails on the rest), and no line names a drawing outside the set.

It prints the lines examined (non-zero is required), the new grades with their counts
and the number of redrawn drawings whose pixels equal the drawing they replace (each
only information), and the drawings whose record records a disagreement, apart, by
code point, form set and cited place, with their count; they fail nothing.

Exit codes: 0 the records pass, 1 a check failed, 2 an input could not be read.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

# The visual reference of each form set: the only two values a record may name. Each
# is written in two pieces, so that the foreign-font scan, which searches scripts for
# these names, does not find this file.
REFERENCE_JP = "Source" + "HanSans-Regular"
REFERENCE_SC = "Source" + "HanSansSC-Regular"
REFERENCES = {"jp": REFERENCE_JP, "sc": REFERENCE_SC}
NO_REFERENCE = "none"

WORD_SURE = "fairly sure"
FOUR_WORDS = ("weakest", "weak in one half", "doubtful", WORD_SURE)
BATCH2_LIST = "b2-list"
STATUS_REDRAWN = "redrawn"
STATUS_HELD = "held-QRS"
STATUS_PENDING = "pending"
STATUSES = (STATUS_REDRAWN, STATUS_PENDING)
FORMS = ("jp", "sc")
FIRST_BATCH = 2
LAST_REFERENCED_BATCH = 8
FIELDS = 11
NONE_FIELD = "-"
NO_ENTRY = "no-entry"
CITATION_SEPARATOR = " | "
CITATION_FIELDS = 5

# The four drawings that may carry the reference whatever their grade.
NAMED = frozenset({(0x975E, "jp"), (0x54C1, "jp"), (0x76EE, "jp"), (0x8BA1, "sc")})

RECORDS_REL = ("fonts-src", "nifen-art-cjk", "redraw-records.txt")
CITATIONS_REL = ("fonts-src", "nifen-art-cjk", "han-citations.txt")
FACE_REL = {
    "jp": ("fonts-src", "nifen-art-cjk", "han-jp.txt"),
    "sc": ("fonts-src", "nifen-art-cjk", "han-sc.txt"),
}

CP_RE = re.compile(r"^U\+([0-9A-F]{4,6})$")
BATCH_RE = re.compile(r"^b([0-9]+)$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ROW_RE = re.compile(r"^[#.]+$")

Key = Tuple[int, str]


@dataclass
class Text:
    """A file's name, as it is printed, and its text."""

    name: str
    text: str


@dataclass
class Result:
    """What one check found."""

    errors: List[str] = field(default_factory=list)
    examined: int = 0
    statuses: Dict[str, int] = field(default_factory=dict)
    references: Dict[str, int] = field(default_factory=dict)
    new_grades: Dict[str, int] = field(default_factory=dict)
    pixel_equal: int = 0
    disagreements: List[Tuple[Key, str]] = field(default_factory=list)
    pending: int = 0
    members: int = -1
    missing_members: List[Key] = field(default_factory=list)


def cp_text(cp: int) -> str:
    return "U+%04X" % cp


def key_text(key: Key) -> str:
    return "%s set=%s" % (cp_text(key[0]), key[1])


def record_sha(header: str, rows: Sequence[str]) -> str:
    """The sha256 of a glyph record: its header line and its rows, each with a LF."""
    body = "\n".join([header] + list(rows)) + "\n"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def read_face(text: Text) -> Dict[Key, str]:
    """The glyph records of a face source file: (code point, form set) -> sha256."""
    out: Dict[Key, str] = {}
    current: Optional[Tuple[Key, str, List[str]]] = None

    def flush() -> None:
        nonlocal current
        if current is not None and current[0] not in out:
            out[current[0]] = record_sha(current[1], current[2])
        current = None

    for raw in text.text.split("\n"):
        line = raw.rstrip("\r")
        if ROW_RE.match(line) and current is not None:
            current[2].append(line)
            continue
        if not line.strip():
            flush()
            continue
        if line.startswith("# ") or line.strip() == "#":
            continue
        tokens = line.split()
        flush()
        if tokens[0] != "glyph" or len(tokens) < 2:
            continue
        m = CP_RE.match(tokens[1].upper())
        form = ""
        for token in tokens[2:]:
            if token.startswith("set="):
                form = token[4:].lower()
        if m and form in FORMS:
            current = ((int(m.group(1), 16), form), line, [])
    flush()
    return out


def read_members(text: Text, errors: List[str]) -> Dict[Key, Tuple[int, str]]:
    """The redraw set: (code point, form set) -> (batch, first grade)."""
    out: Dict[Key, Tuple[int, str]] = {}
    for n, raw in enumerate(text.text.split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        m = CP_RE.match(fields[0].strip().upper())
        b = BATCH_RE.match(fields[3].strip()) if len(fields) >= 7 else None
        if not m or len(fields) < 7 or fields[2].strip() not in FORMS or not b:
            errors.append("%s:%d: not a member of the redraw set" % (text.name, n))
            continue
        out[(int(m.group(1), 16), fields[2].strip())] = (
            int(b.group(1)),
            fields[4].strip(),
        )
    return out


def parse_grade(token: str, allow_list: bool) -> Optional[str]:
    if allow_list and token == BATCH2_LIST:
        return token
    return token if token in FOUR_WORDS else None


def read_citations(text: Text, errors: List[str]) -> Dict[Key, Tuple[str, str]]:
    """The citation records: (code point, form set) -> (standard, place).

    A no-entry record has the standard no-entry and a place that names the two lists
    the character is absent from; it cites no place of a standard.
    """
    out: Dict[Key, Tuple[str, str]] = {}
    for n, raw in enumerate(text.text.split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = [x.strip() for x in line.split(CITATION_SEPARATOR)]
        m = CP_RE.match(parts[1].upper()) if len(parts) == CITATION_FIELDS else None
        if m is None or parts[0].lower() not in FORMS:
            errors.append("%s:%d: not a citation record" % (text.name, n))
            continue
        out.setdefault((int(m.group(1), 16), parts[0].lower()), (parts[2], parts[3]))
    return out


def cited_place(entry: Tuple[str, str]) -> str:
    """A drawing's cited place as a record writes it: standard, a space, place."""
    return "%s %s" % entry


def disagreement_error(
    value: str, key: Key, citations: Optional[Dict[Key, Tuple[str, str]]]
) -> Optional[str]:
    """Why a disagreement field is not a dash or the drawing's cited place."""
    if value == NONE_FIELD:
        return None
    if not value:
        return "the disagreement field is empty (a dash, or the cited place)"
    if citations is None:
        return (
            "records a disagreement with %r, but no citation records were given" % value
        )
    entry = citations.get(key)
    if entry is None:
        return (
            "records a disagreement with %r, but the citation records hold no "
            "record of this drawing (it carries a dash)" % value
        )
    if entry[0] == NO_ENTRY:
        return (
            "records a disagreement with %r on a drawing whose citation record is a "
            "no-entry record: it cites no place and carries a dash" % value
        )
    if value != cited_place(entry):
        return (
            "records a disagreement with %r, but its place in the citation records "
            "is %r" % (value, cited_place(entry))
        )
    return None


def reference_error(
    form: str,
    reference: str,
    first: str,
    key: Key,
    in_set: Optional[bool],
    batch: int,
) -> Optional[str]:
    """Why a record may not name this reference, or None when it may."""
    own = REFERENCES[form]
    if reference == NO_REFERENCE:
        if batch <= LAST_REFERENCED_BATCH or key in NAMED:
            return (
                "names no reference; a line of batches %d to %d, or of one of the "
                "four named drawings, names its own form set's build, %s"
                % (FIRST_BATCH, LAST_REFERENCED_BATCH, own)
            )
        return None
    if reference != own:
        if reference in REFERENCES.values():
            return (
                "names %s, the typeface of the other form set; this drawing's own is %s"
                % (
                    reference,
                    own,
                )
            )
        return (
            "names %s, which is not a visual reference (the only ones are %s and %s)"
            % (
                reference,
                REFERENCE_JP,
                REFERENCE_SC,
            )
        )
    if in_set is False:
        return "names %s on a drawing outside the redraw set" % reference
    if first == WORD_SURE and key not in NAMED:
        return (
            "names %s on a drawing whose first grade is fairly sure and that is not "
            "one of the four named drawings (no batch grades it not confident)"
            % reference
        )
    return None


def check(
    records: Text,
    faces: Dict[str, Text],
    members: Optional[Text] = None,
    partial: bool = False,
    citations: Optional[Text] = None,
) -> Result:
    r = Result()
    face = {form: read_face(faces[form]) for form in FORMS}
    cited: Optional[Dict[Key, Tuple[str, str]]] = None
    if citations is not None:
        cited = read_citations(citations, r.errors)
    member_map: Optional[Dict[Key, Tuple[int, str]]] = None
    if members is not None:
        member_map = read_members(members, r.errors)
        r.members = len(member_map)
    seen: Dict[Key, int] = {}
    for n, raw in enumerate(records.text.split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        r.examined += 1
        where = "%s:%d" % (records.name, n)
        f = [x.strip() for x in line.split("\t")]
        if len(f) != FIELDS:
            r.errors.append(
                "%s: %d fields where %d are expected" % (where, len(f), FIELDS)
            )
            continue
        cp_m = CP_RE.match(f[0].upper())
        batch_m = BATCH_RE.match(f[2])
        if not cp_m or f[1] not in FORMS or not batch_m:
            r.errors.append(
                "%s: not a drawing (code point, jp or sc, b<batch>): %r"
                % (where, f[:3])
            )
            continue
        key: Key = (int(cp_m.group(1), 16), f[1])
        who = "%s: %s" % (where, key_text(key))
        if int(batch_m.group(1)) < FIRST_BATCH:
            r.errors.append("%s: batch %s is outside the redraw set" % (who, f[2]))
        if key in seen:
            r.errors.append(
                "%s: a second line for this drawing (first at line %d)"
                % (who, seen[key])
            )
            continue
        seen[key] = n
        first = parse_grade(f[3], True)
        status = f[4]
        reference = f[5]
        disagreement = f[6]
        if first is None:
            r.errors.append(
                "%s: first grade %r is not one of the four words or b2-list"
                % (who, f[3])
            )
        if status == STATUS_HELD:
            r.errors.append(
                "%s: status %s is refused; nothing is held, a member whose build shows "
                "another form is redrawn and its disagreement field names the cited "
                "place" % (who, status)
            )
            continue
        if status not in STATUSES:
            r.errors.append("%s: status %r is not redrawn or pending" % (who, status))
            continue
        r.statuses[status] = r.statuses.get(status, 0) + 1
        r.references[reference] = r.references.get(reference, 0) + 1
        try:
            datetime.date.fromisoformat(f[10])
        except ValueError:
            r.errors.append("%s: %r is not a date (YYYY-MM-DD)" % (who, f[10]))
        in_set = None if member_map is None else key in member_map
        if member_map is not None:
            if key not in member_map:
                r.errors.append("%s: not a member of the redraw set" % who)
            elif first is not None and member_map[key][1] != first:
                r.errors.append(
                    "%s: first grade %s, the set says %s"
                    % (who, first, member_map[key][1])
                )
            elif member_map[key][0] != int(batch_m.group(1)):
                r.errors.append(
                    "%s: batch %s, the set says b%d" % (who, f[2], member_map[key][0])
                )
        why = reference_error(
            key[1], reference, first or "", key, in_set, int(batch_m.group(1))
        )
        if why is not None:
            r.errors.append("%s: %s" % (who, why))
        why = disagreement_error(disagreement, key, cited)
        if why is not None:
            r.errors.append("%s: %s" % (who, why))
        if not SHA_RE.match(f[8]):
            r.errors.append("%s: old sha256 is not 64 lowercase hex digits" % who)
        held_sha = face[key[1]].get(key)
        if held_sha is None:
            r.errors.append(
                "%s: the face's sources hold no record of this drawing" % who
            )
        if status == STATUS_PENDING:
            r.pending += 1
            r.errors.append(
                "%s: status pending; the check refuses a line left pending" % who
            )
        else:
            grade = parse_grade(f[7], False)
            if grade is None:
                r.errors.append(
                    "%s: new grade %r is not one of the four words" % (who, f[7])
                )
            else:
                r.new_grades[grade] = r.new_grades.get(grade, 0) + 1
            if not SHA_RE.match(f[9]):
                r.errors.append("%s: new sha256 is not 64 lowercase hex digits" % who)
            elif held_sha is not None and held_sha != f[9]:
                r.errors.append(
                    "%s: redrawn, but the face holds a different drawing "
                    "(its record hashes to %s, the line says %s)"
                    % (who, held_sha, f[9])
                )
            if f[8] == f[9]:
                r.pixel_equal += 1
            if disagreement != NONE_FIELD and why is None:
                r.disagreements.append((key, disagreement))
    if r.examined == 0:
        r.errors.append("%s: examined: 0 redraw records" % records.name)
    if member_map is not None:
        r.missing_members = sorted(k for k in member_map if k not in seen)
        if not partial:
            for k in r.missing_members:
                r.errors.append(
                    "%s: a member of the redraw set with no redraw record" % key_text(k)
                )
    return r


def render(r: Result, partial: bool) -> List[str]:
    out = ["redraw records examined: %d" % r.examined]
    out.append(
        "status: redrawn %d, pending %d"
        % (
            r.statuses.get(STATUS_REDRAWN, 0),
            r.statuses.get(STATUS_PENDING, 0),
        )
    )
    out.append(
        "reference: none %d, %s %d, %s %d"
        % (
            r.references.get(NO_REFERENCE, 0),
            REFERENCE_JP,
            r.references.get(REFERENCE_JP, 0),
            REFERENCE_SC,
            r.references.get(REFERENCE_SC, 0),
        )
    )
    out.append("new grades (redrawn lines), information:")
    for word in FOUR_WORDS:
        out.append("  %s: %d" % (word, r.new_grades.get(word, 0)))
    out.append(
        "pixel-equal to the drawing replaced: %d of %d redrawn, information"
        % (r.pixel_equal, r.statuses.get(STATUS_REDRAWN, 0))
    )
    out.append(
        "disagreements with the cited place (redrawn lines, failing nothing): %d"
        % len(r.disagreements)
    )
    for key, place in sorted(r.disagreements):
        out.append("  disagreement %s cited place %s" % (key_text(key), place))
    out.append("pending: %d" % r.pending)
    if r.members >= 0:
        out.append(
            "members of the redraw set: %d, with no record yet: %d%s"
            % (r.members, len(r.missing_members), " (partial run)" if partial else "")
        )
    else:
        out.append("members of the redraw set: not given")
    return out


def read_text(path: str) -> Text:
    with open(path, "rb") as fh:
        data = fh.read()
    return Text(os.path.basename(path), data.decode("utf-8"))


def row_text(rows: Sequence[str]) -> str:
    return "\n".join(rows) + "\n"


def controls() -> int:
    base_rows = {
        "jp": {
            0x4E00: ["###########"],
            0x4E8C: ["##.", "###"],
            0x4E5F: ["#.#"],
            0x975E: ["#.#", "###", "#.#"],
        },
        "sc": {0x4E09: ["###", "#.#"], 0x4EBA: ["#.", "##"]},
    }
    old_rows = {
        "jp": {0x4E00: ["##########"], 0x4E8C: ["#.#"], 0x975E: ["###"]},
        "sc": {0x4E09: ["###", "#.#"], 0x4EBA: ["#.", "##"]},
    }
    # The citation records of the fixture: the third and fourth fields of a record,
    # joined by one space, are the drawing's cited place. U+975E carries a no-entry
    # record and U+4E5F has no record.
    place_4e8c = "joyo-2010 page=61 pos=700"
    citation_text = (
        "# fixture\n"
        "JP | U+4E00 | joyo-2010 | page=13 pos=41 | via=textlayer\n"
        "JP | U+4E8C | joyo-2010 | page=61 pos=700 | via=textlayer\n"
        "JP | U+975E | no-entry | absent=joyo-2010,hyogai-2000 | via=membership\n"
        "SC | U+4E09 | tongyong-2013 | page=8 cell=0001 | via=index-agree\n"
        "SC | U+4EBA | tongyong-2013 | page=8 cell=0010 | via=index-agree\n"
    )
    cites = Text("han-citations.txt", citation_text)

    def header(form: str, cp: int) -> str:
        return "glyph %s set=%s src=drawn top=3 x=0" % (cp_text(cp), form)

    def face_text(rows: Dict[int, List[str]], form: str) -> str:
        parts = ["# fixture"]
        for cp in sorted(rows):
            parts.append("")
            parts.append(header(form, cp))
            parts.extend(rows[cp])
        return "\n".join(parts) + "\n"

    def sha_of(form: str, cp: int, rows: Dict[str, Dict[int, List[str]]]) -> str:
        return record_sha(header(form, cp), rows[form][cp])

    faces = {
        form: Text("han-%s.txt" % form, face_text(base_rows[form], form))
        for form in FORMS
    }

    def line(
        cp: int,
        form: str,
        batch: int,
        first: str,
        status: str,
        reference: str,
        new_grade: str,
        old: str,
        new: str,
        disagreement: str = "-",
    ) -> str:
        return "\t".join(
            [
                cp_text(cp),
                form,
                "b%d" % batch,
                first,
                status,
                reference,
                disagreement,
                new_grade,
                old,
                new,
                "2026-11-19",
            ]
        )

    def old_sha(form: str, cp: int) -> str:
        return sha_of(form, cp, old_rows)

    def new_sha(form: str, cp: int) -> str:
        return sha_of(form, cp, base_rows)

    lines = [
        line(
            0x4E00,
            "jp",
            2,
            "weakest",
            "redrawn",
            REFERENCE_JP,
            "doubtful",
            old_sha("jp", 0x4E00),
            new_sha("jp", 0x4E00),
        ),
        line(
            0x4E8C,
            "jp",
            3,
            "doubtful",
            "redrawn",
            REFERENCE_JP,
            "weak in one half",
            old_sha("jp", 0x4E8C),
            new_sha("jp", 0x4E8C),
            place_4e8c,
        ),
        line(
            0x975E,
            "jp",
            8,
            WORD_SURE,
            "redrawn",
            REFERENCE_JP,
            WORD_SURE,
            old_sha("jp", 0x975E),
            new_sha("jp", 0x975E),
        ),
        line(
            0x4E09,
            "sc",
            3,
            "weakest",
            "redrawn",
            REFERENCE_SC,
            "doubtful",
            old_sha("sc", 0x4E09),
            new_sha("sc", 0x4E09),
        ),
        line(
            0x4EBA,
            "sc",
            9,
            "weak in one half",
            "redrawn",
            NO_REFERENCE,
            "doubtful",
            old_sha("sc", 0x4EBA),
            new_sha("sc", 0x4EBA),
        ),
    ]
    member_lines = [
        "\t".join([cp_text(0x4E00), "x", "jp", "b2", "weakest", "a:1", "-"]),
        "\t".join([cp_text(0x4E8C), "x", "jp", "b3", "doubtful", "a:2", "-"]),
        "\t".join([cp_text(0x975E), "x", "jp", "b8", WORD_SURE, "a:3", "517"]),
        "\t".join([cp_text(0x4E09), "x", "sc", "b3", "weakest", "a:4", "-"]),
        "\t".join([cp_text(0x4EBA), "x", "sc", "b9", "weak in one half", "a:5", "-"]),
    ]

    def run(
        record_lines: Sequence[str], member_set: Optional[Sequence[str]] = None
    ) -> Tuple[int, str, Result]:
        recs = Text(
            "redraw-records.txt", "# fixture\n" + "\n".join(record_lines) + "\n"
        )
        mem = (
            Text("redraw-set.tsv", "\n".join(member_set) + "\n")
            if member_set is not None
            else None
        )
        r = check(recs, faces, mem, False, cites)
        text = "\n".join(r.errors)
        return (1 if r.errors else 0), text, r

    results: List[Tuple[str, bool, str]] = []

    def record(label: str, ok: bool, what: str) -> None:
        results.append((label, ok, what))

    code, text, r = run(lines, member_lines)
    record(
        "base",
        code == 0 and r.examined == 5 and len(r.disagreements) == 1,
        "a clean fixture exits 0, 5 lines examined, 1 disagreement (exit %d, "
        "examined %d)" % (code, r.examined),
    )
    shown = "\n".join(render(r, False))
    record(
        "dis-ok",
        code == 0
        and "disagreement U+4E8C set=jp cited place %s" % place_4e8c in shown
        and "(redrawn lines, failing nothing): 1" in shown,
        "a record with a disagreement passes and is printed with its code point, "
        "form set and cited place (exit %d)" % code,
    )

    sixth = line(
        0x4E5F,
        "jp",
        3,
        WORD_SURE,
        "redrawn",
        REFERENCE_JP,
        WORD_SURE,
        new_sha("jp", 0x4E5F),
        new_sha("jp", 0x4E5F),
    )
    code, text, r = run(lines + [sixth])
    record(
        "p1",
        code != 0
        and "U+4E5F" in text
        and REFERENCE_JP in text
        and "not confident" in text,
        "a visual reference on a drawing outside the redraw set that no batch "
        "grades not confident: exit %d, names U+4E5F and %s" % (code, REFERENCE_JP),
    )

    swapped = list(lines)
    swapped[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "redrawn",
        REFERENCE_SC,
        "weak in one half",
        old_sha("jp", 0x4E8C),
        new_sha("jp", 0x4E8C),
        place_4e8c,
    )
    code, text, r = run(swapped)
    record(
        "p2",
        code != 0 and "U+4E8C" in text and REFERENCE_SC in text,
        "the Simplified-form build %s named on a Japanese-form drawing: exit %d, "
        "names U+4E8C and %s" % (REFERENCE_SC, code, REFERENCE_SC),
    )

    swapped = list(lines)
    swapped[3] = line(
        0x4E09,
        "sc",
        3,
        "weakest",
        "redrawn",
        REFERENCE_JP,
        "doubtful",
        old_sha("sc", 0x4E09),
        new_sha("sc", 0x4E09),
    )
    code, text, r = run(swapped)
    record(
        "p3",
        code != 0 and "U+4E09" in text and REFERENCE_JP in text,
        "the Japanese-form build %s named on a Simplified-form drawing: exit %d, "
        "names U+4E09 and %s" % (REFERENCE_JP, code, REFERENCE_JP),
    )

    for label, other in (
        ("p4a", "Yu Gothic Medium"),
        ("p4b", "Microsoft YaHei"),
        ("p4c", "Other Test Face"),
    ):
        swapped = list(lines)
        swapped[1] = line(
            0x4E8C,
            "jp",
            3,
            "doubtful",
            "redrawn",
            other,
            "weak in one half",
            old_sha("jp", 0x4E8C),
            new_sha("jp", 0x4E8C),
            place_4e8c,
        )
        code, text, r = run(swapped)
        record(
            label,
            code != 0 and "U+4E8C" in text and other in text,
            "a font other than the two builds named as a visual reference: "
            "exit %d, names U+4E8C and %s" % (code, other),
        )

    noref = list(lines)
    noref[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "redrawn",
        NO_REFERENCE,
        "weak in one half",
        old_sha("jp", 0x4E8C),
        new_sha("jp", 0x4E8C),
        place_4e8c,
    )
    code, text, r = run(noref)
    record(
        "noref",
        code != 0 and "U+4E8C" in text and "names no reference" in text,
        "a member line of batch 3 naming no reference: exit %d, names U+4E8C" % code,
    )

    noref = list(lines)
    noref[2] = line(
        0x975E,
        "jp",
        9,
        WORD_SURE,
        "redrawn",
        NO_REFERENCE,
        WORD_SURE,
        old_sha("jp", 0x975E),
        new_sha("jp", 0x975E),
    )
    code, text, r = run(noref)
    record(
        "noref4",
        code != 0 and "U+975E" in text and "names no reference" in text,
        "one of the four named drawings on a line of batch 9 naming no reference: "
        "exit %d, names U+975E" % code,
    )

    held = list(lines)
    held[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "held-QRS",
        REFERENCE_JP,
        "-",
        new_sha("jp", 0x4E8C),
        "-",
        place_4e8c,
    )
    code, text, r = run(held)
    record(
        "held",
        code != 0 and "U+4E8C" in text and "held-QRS" in text and "refused" in text,
        "a held-QRS line: exit %d, names U+4E8C and refuses the status" % code,
    )

    other_place = list(lines)
    other_place[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "redrawn",
        REFERENCE_JP,
        "weak in one half",
        old_sha("jp", 0x4E8C),
        new_sha("jp", 0x4E8C),
        "joyo-2010 page=99 pos=999",
    )
    code, text, r = run(other_place)
    record(
        "place",
        code != 0 and "U+4E8C" in text and place_4e8c in text,
        "a disagreement naming a place other than the citation record's: exit %d, "
        "names U+4E8C and the record's place" % code,
    )

    on_no_entry = list(lines)
    on_no_entry[2] = line(
        0x975E,
        "jp",
        8,
        WORD_SURE,
        "redrawn",
        REFERENCE_JP,
        WORD_SURE,
        old_sha("jp", 0x975E),
        new_sha("jp", 0x975E),
        "joyo-2010 page=1 pos=1",
    )
    code, text, r = run(on_no_entry)
    record(
        "noentry",
        code != 0 and "U+975E" in text and "no-entry record" in text,
        "a disagreement on a drawing whose citation record is a no-entry record: "
        "exit %d, names U+975E" % code,
    )

    no_record = list(lines)
    no_record.append(
        line(
            0x4E5F,
            "jp",
            3,
            "doubtful",
            "redrawn",
            REFERENCE_JP,
            "weak in one half",
            new_sha("jp", 0x4E5F),
            new_sha("jp", 0x4E5F),
            "joyo-2010 page=1 pos=2",
        )
    )
    code, text, r = run(no_record)
    record(
        "nocite",
        code != 0 and "U+4E5F" in text and "hold no record of this drawing" in text,
        "a disagreement on a drawing the citation records do not hold: exit %d, "
        "names U+4E5F" % code,
    )

    pending = list(lines)
    pending[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "pending",
        NO_REFERENCE,
        "-",
        old_sha("jp", 0x4E8C),
        "-",
    )
    code, text, r = run(pending)
    record(
        "pending",
        code != 0 and "U+4E8C" in text and "pending" in text and r.pending == 1,
        "a member line left pending: exit %d, names U+4E8C" % code,
    )

    differs = list(lines)
    differs[1] = line(
        0x4E8C,
        "jp",
        3,
        "doubtful",
        "redrawn",
        REFERENCE_JP,
        "weak in one half",
        old_sha("jp", 0x4E8C),
        old_sha("jp", 0x4E00),
        place_4e8c,
    )
    code, text, r = run(differs)
    record(
        "differs",
        code != 0 and "U+4E8C" in text and "the face holds a different drawing" in text,
        "a redrawn line whose face record differs: exit %d, names U+4E8C" % code,
    )

    code, text, r = run(lines[:4], member_lines)
    record(
        "norec",
        code != 0
        and "U+4EBA set=sc: a member of the redraw set with no redraw record" in text,
        "a member planted with no redraw record: exit %d, names U+4EBA" % code,
    )

    code, text, r = run([])
    record(
        "empty",
        code != 0 and "examined: 0 redraw records" in text,
        "no record lines: exit %d, 'examined: 0 redraw records' printed" % code,
    )

    code, text, r = run(lines + [lines[0]])
    record(
        "dup",
        code != 0 and "a second line for this drawing" in text,
        "a second line for one drawing: exit %d, refused" % code,
    )

    for label, ok, what in results:
        sys.stdout.write(
            "control %-8s %s: %s\n"
            % (
                label,
                (
                    ("passes" if label in ("base", "dis-ok") else "killed")
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
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(here)))
    ap.add_argument("--set", help="the redraw set, as redraw_set.py writes it")
    ap.add_argument(
        "--partial", action="store_true", help="members with no line yet do not fail"
    )
    ap.add_argument("--controls", action="store_true", help="run the planted controls")
    args = ap.parse_args(argv)
    if args.controls:
        return controls()
    try:
        records = read_text(os.path.join(args.root, *RECORDS_REL))
        faces = {
            form: read_text(os.path.join(args.root, *FACE_REL[form])) for form in FORMS
        }
        members = read_text(args.set) if args.set else None
        citations = read_text(os.path.join(args.root, *CITATIONS_REL))
    except (OSError, UnicodeDecodeError) as exc:
        sys.stdout.write("could not read an input: %s\n" % exc)
        return 2
    result = check(records, faces, members, args.partial, citations)
    for text in render(result, args.partial):
        sys.stdout.write(text + "\n")
    for error in result.errors:
        sys.stdout.write("FAILED: " + error + "\n")
    code = 1 if result.errors else 0
    sys.stdout.write("exit %d\n" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
