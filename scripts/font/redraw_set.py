"""The redraw set of the Han drawings: which drawings are drawn again, and why.

Standard library only. The set is built from two tab-separated tables given on the
command line, and a third, optional one:

    python scripts/font/redraw_set.py --drawn <drawn.tsv> --grades <grades.tsv> \\
        [--after <after.tsv>] [--out <redraw-set.tsv>]
    python scripts/font/redraw_set.py --controls

The tables (one record per line, fields separated by a tab, lines starting with # and
blank lines are not records):

    drawn   code point, form set, batch        the drawings each batch made
    grades  code point, form set, batch, grade, source
    after   code point, form set, batch, grade, date, note

The form set is jp or sc (grades may also say "both", which names the two drawings of
that code point, one in each set). The batch is a number or b<number>. The grade is one
of the four words (weakest, weak in one half, doubtful, fairly sure), or b2-list for a
drawing that sits on the list of batch 2's drawings its designer is not confident
about. The source is the file and line the grade was read from. A line of the third
table gives the grade of a drawing that had none: it carries the date it was given on
and the words "graded after the fact", and it is refused for a drawing that already has
a grade.

The rule. A drawing is not confident when its recorded grade is weakest, weak in one
half or doubtful, or when it is on batch 2's list. The redraw set is every not-confident
drawing of batch 2 onward, and four named drawings whatever their grade. A drawing is in
the set once, however many records name it. The tool fails while a drawing of the drawn
table has no grade, and names it; it fails on a grade for a drawing the batch did not
make, on a named drawing that no batch drew, and on an empty table.

Exit codes: 0 the set was built, 1 a check failed, 2 an input could not be read.
--controls plants each fault in a small table of its own and requires the tool to catch
it (or to leave the drawing out, or to name two members, as the control says).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

WORD_WEAKEST = "weakest"
WORD_WEAK_HALF = "weak in one half"
WORD_DOUBTFUL = "doubtful"
WORD_SURE = "fairly sure"
FOUR_WORDS = (WORD_WEAKEST, WORD_WEAK_HALF, WORD_DOUBTFUL, WORD_SURE)
NOT_CONFIDENT = (WORD_WEAKEST, WORD_WEAK_HALF, WORD_DOUBTFUL)
BATCH2_LIST = "b2-list"
FIRST_BATCH = 2
FORMS = ("jp", "sc")
BOTH = "both"
AFTER_NOTE = "graded after the fact"

# The four drawings named whatever their grade: (code point, form set, order number).
NAMED: Tuple[Tuple[int, str, int], ...] = (
    (0x975E, "jp", 517),
    (0x54C1, "jp", 523),
    (0x76EE, "jp", 525),
    (0x8BA1, "sc", 541),
)

# Figures given as information, never as the definition: not-confident rows per batch,
# the split of two batches by grade word, the drawings with no grade in any list, and
# the total with the four named drawings.
INFO_ROWS: Dict[int, int] = {2: 15, 3: 29, 4: 31, 5: 82, 6: 73, 7: 76, 8: 87}
INFO_WORDS: Dict[int, Tuple[int, int, int]] = {7: (15, 26, 35), 8: (28, 38, 21)}
INFO_UNGRADED = 12
INFO_TOTAL = 397

CP_RE = re.compile(r"^U\+([0-9A-F]{4,6})$")
BATCH_RE = re.compile(r"^b?([0-9]+)$")

Key = Tuple[int, str]


class Drawn(NamedTuple):
    key: Key
    batch: int
    where: str


class Grade(NamedTuple):
    key: Key
    batch: int
    word: str
    source: str
    where: str
    both: bool


class Member(NamedTuple):
    key: Key
    batch: int
    first_grade: str
    source: str
    named: str


@dataclass
class Table:
    """A table's name, as it is printed, and its text."""

    name: str
    text: str


@dataclass
class Analysis:
    """Everything one run found: the failures first, then what is printed."""

    errors: List[str] = field(default_factory=list)
    ungraded: List[Drawn] = field(default_factory=list)
    members: List[Member] = field(default_factory=list)
    drawings: List[Drawn] = field(default_factory=list)
    lines: Dict[str, int] = field(default_factory=dict)
    grade_lines: int = 0
    grade_rows: int = 0
    after_rows: int = 0
    duplicates: int = 0
    conflicts: List[str] = field(default_factory=list)
    word_rows: Dict[int, Dict[str, int]] = field(default_factory=dict)
    line_rows: Dict[int, int] = field(default_factory=dict)
    first_grades: Dict[Key, str] = field(default_factory=dict)
    named_state: List[str] = field(default_factory=list)


def cp_text(cp: int) -> str:
    return "U+%04X" % cp


def key_text(key: Key) -> str:
    return "%s set=%s" % (cp_text(key[0]), key[1])


def parse_cp(token: str) -> Optional[int]:
    m = CP_RE.match(token.strip().upper())
    return int(m.group(1), 16) if m else None


def parse_batch(token: str) -> Optional[int]:
    m = BATCH_RE.match(token.strip().lower())
    return int(m.group(1)) if m else None


def parse_word(token: str, allow_list: bool) -> Optional[str]:
    text = " ".join(token.strip().lower().replace("_", " ").split())
    if text == BATCH2_LIST:
        return BATCH2_LIST if allow_list else None
    text = text.replace("-", " ")
    return text if text in FOUR_WORDS else None


def split_records(
    table: Table, columns: int, errors: List[str]
) -> Tuple[List[Tuple[int, List[str]]], int]:
    """The records of a table: (line number, fields), and how many were examined."""
    records: List[Tuple[int, List[str]]] = []
    examined = 0
    for n, raw in enumerate(table.text.split("\n"), 1):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        examined += 1
        fields = line.split("\t")
        if len(fields) != columns:
            errors.append(
                "%s:%d: %d fields where %d are expected"
                % (table.name, n, len(fields), columns)
            )
            continue
        records.append((n, [f.strip() for f in fields]))
    return records, examined


def read_drawn(table: Table, a: Analysis) -> Dict[Key, Drawn]:
    out: Dict[Key, Drawn] = {}
    records, examined = split_records(table, 3, a.errors)
    a.lines[table.name] = examined
    for n, f in records:
        where = "%s:%d" % (table.name, n)
        cp, batch = parse_cp(f[0]), parse_batch(f[2])
        if cp is None or f[1].lower() not in FORMS or batch is None:
            a.errors.append(
                "%s: not a drawing (code point, jp or sc, batch): %r" % (where, f[:3])
            )
            continue
        if batch < FIRST_BATCH:
            a.errors.append("%s: batch %d is outside the redraw set" % (where, batch))
            continue
        key = (cp, f[1].lower())
        if key in out and out[key].batch != batch:
            a.errors.append(
                "%s: %s is drawn in batch %d and in batch %d"
                % (where, key_text(key), out[key].batch, batch)
            )
            continue
        out.setdefault(key, Drawn(key, batch, where))
    return out


def read_grades(table: Table, a: Analysis) -> List[Grade]:
    out: List[Grade] = []
    records, examined = split_records(table, 5, a.errors)
    a.lines[table.name] = examined
    for n, f in records:
        where = "%s:%d" % (table.name, n)
        cp, batch = parse_cp(f[0]), parse_batch(f[2])
        form = f[1].lower()
        word = parse_word(f[3], True)
        if cp is None or form not in FORMS + (BOTH,) or batch is None or word is None:
            a.errors.append(
                "%s: not a grade record (code point, jp/sc/both, batch, grade): %r"
                % (where, f[:4])
            )
            continue
        a.grade_lines += 1
        a.line_rows[batch] = a.line_rows.get(batch, 0) + (1 if word != WORD_SURE else 0)
        forms = list(FORMS) if form == BOTH else [form]
        for each in forms:
            out.append(Grade((cp, each), batch, word, f[4], where, form == BOTH))
    return out


def check_grade(g: Grade, drawn: Dict[Key, Drawn], a: Analysis) -> bool:
    if g.batch < FIRST_BATCH:
        a.errors.append(
            "%s: %s: batch %d is outside the redraw set"
            % (g.where, key_text(g.key), g.batch)
        )
        return False
    made = drawn.get(g.key)
    if made is None:
        a.errors.append(
            "%s: %s batch %d: a grade for a drawing no batch made"
            % (g.where, key_text(g.key), g.batch)
        )
        return False
    if made.batch != g.batch:
        a.errors.append(
            "%s: %s: graded in batch %d, drawn in batch %d"
            % (g.where, key_text(g.key), g.batch, made.batch)
        )
        return False
    if g.word == BATCH2_LIST and g.batch != 2:
        a.errors.append(
            "%s: %s: the list of batch 2 names a drawing of batch %d"
            % (g.where, key_text(g.key), g.batch)
        )
        return False
    return True


def read_after(
    table: Table, drawn: Dict[Key, Drawn], graded: Dict[Key, List[Grade]], a: Analysis
) -> List[Grade]:
    out: List[Grade] = []
    records, examined = split_records(table, 6, a.errors)
    a.lines[table.name] = examined
    for n, f in records:
        where = "%s:%d" % (table.name, n)
        cp, batch = parse_cp(f[0]), parse_batch(f[2])
        word = parse_word(f[3], False)
        if cp is None or f[1].lower() not in FORMS or batch is None or word is None:
            a.errors.append(
                "%s: not a grade after the fact (code point, jp or sc, batch, "
                "one of the four words): %r" % (where, f[:4])
            )
            continue
        try:
            datetime.date.fromisoformat(f[4])
        except ValueError:
            a.errors.append("%s: %r is not a date (YYYY-MM-DD)" % (where, f[4]))
            continue
        if f[5].lower() != AFTER_NOTE:
            a.errors.append('%s: the note is not "%s": %r' % (where, AFTER_NOTE, f[5]))
            continue
        g = Grade(
            (cp, f[1].lower()), batch, word, "%s:%d" % (table.name, n), where, False
        )
        if not check_grade(g, drawn, a):
            continue
        if g.key in graded:
            a.errors.append(
                "%s: %s already has a grade (%s); it is not graded again"
                % (where, key_text(g.key), graded[g.key][0].where)
            )
            continue
        out.append(g)
    return out


def analyse(
    drawn_table: Table, grades_table: Table, after_table: Optional[Table]
) -> Analysis:
    a = Analysis()
    drawn = read_drawn(drawn_table, a)
    grades = [g for g in read_grades(grades_table, a) if check_grade(g, drawn, a)]
    if a.lines.get(drawn_table.name, 0) == 0:
        a.errors.append("%s: examined: 0 drawn records" % drawn_table.name)
    if a.lines.get(grades_table.name, 0) == 0:
        a.errors.append("%s: examined: 0 grade records" % grades_table.name)
    by_key: Dict[Key, List[Grade]] = {}
    for g in grades:
        by_key.setdefault(g.key, []).append(g)
    if after_table is not None:
        for g in read_after(after_table, drawn, by_key, a):
            by_key.setdefault(g.key, []).append(g)
            a.after_rows += 1
    a.grade_rows = sum(len(v) for v in by_key.values())
    a.drawings = sorted(drawn.values(), key=lambda d: (d.batch, d.key))
    for d in a.drawings:
        if d.key not in by_key:
            a.ungraded.append(d)
    named: Dict[Key, int] = {}
    for cp, form, order in NAMED:
        key = (cp, form)
        if key not in drawn:
            a.errors.append(
                "the named drawing %s (order %d) is in no drawn set"
                % (key_text(key), order)
            )
            a.named_state.append(
                "%s order %d: absent from the drawn sets" % (key_text(key), order)
            )
            continue
        named[key] = order
    for d in a.drawings:
        rows = by_key.get(d.key, [])
        if not rows:
            continue
        a.first_grades[d.key] = rows[0].word
        words = [r.word for r in rows]
        if len(rows) > 1:
            a.duplicates += len(rows) - 1
            if len(set(words)) > 1:
                a.conflicts.append("%s: %s" % (key_text(d.key), ", ".join(words)))
        hard = [r for r in rows if r.word in NOT_CONFIDENT or r.word == BATCH2_LIST]
        if hard or d.key in named:
            pick = hard[0] if hard else rows[0]
            a.members.append(
                Member(
                    d.key,
                    d.batch,
                    pick.word,
                    pick.source,
                    str(named[d.key]) if d.key in named else "-",
                )
            )
    for cp, form, order in NAMED:
        key = (cp, form)
        if key in named:
            grade = a.first_grades.get(key, "no grade")
            a.named_state.append(
                "%s order %d: grade %s, in the set" % (key_text(key), order, grade)
            )
    for d in a.drawings:
        for r in by_key.get(d.key, []):
            counts = a.word_rows.setdefault(d.batch, {})
            counts[r.word] = counts.get(r.word, 0) + 1
    if a.ungraded:
        a.errors.append(
            "ungraded: %d drawings of the drawn table have no recorded grade"
            % len(a.ungraded)
        )
    return a


def tally(items: Sequence[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return out


def render(a: Analysis, tables: Sequence[Table]) -> List[str]:
    out: List[str] = []
    out.append(
        "grade records examined: files %d, lines %d"
        % (
            len([t for t in tables[1:]]),
            sum(a.lines.get(t.name, 0) for t in tables[1:]),
        )
    )
    for t in tables:
        out.append("  %s: %d records examined" % (t.name, a.lines.get(t.name, 0)))
    out.append(
        "grade lines %d, grade rows %d (a line naming both sets is two rows), "
        "after the fact %d" % (a.grade_lines, a.grade_rows, a.after_rows)
    )
    out.append("drawings in the drawn table: %d" % len(a.drawings))
    out.append("redraw set: %d members" % len(a.members))
    batches = sorted(set(d.batch for d in a.drawings))
    out.append("per batch (drawings drawn / grade rows / members):")
    for b in batches:
        out.append(
            "  batch %d: %d / %d / %d"
            % (
                b,
                len([d for d in a.drawings if d.batch == b]),
                sum(a.word_rows.get(b, {}).values()),
                len([m for m in a.members if m.batch == b]),
            )
        )
    out.append(
        "per grade (members, by first grade; grade rows of all drawings beside):"
    )
    rows_all = tally(
        [w for b in a.word_rows.values() for w, n in b.items() for _ in range(n)]
    )
    members_by = tally([m.first_grade for m in a.members])
    for word in FOUR_WORDS + (BATCH2_LIST,):
        out.append(
            "  %s: members %d, rows %d"
            % (word, members_by.get(word, 0), rows_all.get(word, 0))
        )
    out.append("per form set (members):")
    by_form = tally([m.key[1] for m in a.members])
    for form in FORMS:
        out.append("  %s: %d" % (form, by_form.get(form, 0)))
    out.append("the four named drawings:")
    for line in a.named_state:
        out.append("  " + line)
    out.append(
        "duplicates collapsed: %d (a drawing named by more than one grade row); "
        "differing grade words among them: %d" % (a.duplicates, len(a.conflicts))
    )
    for line in a.conflicts:
        out.append("  differing: " + line)
    out.append("ungraded: %d" % len(a.ungraded))
    for d in a.ungraded:
        out.append("  ungraded: %s batch %d (%s)" % (key_text(d.key), d.batch, d.where))
    out.append("against the figures given as information (nothing here fails on them):")
    for b in sorted(INFO_ROWS):
        lines = a.line_rows.get(b, 0)
        drawings = len([m for m in a.members if m.batch == b and m.named == "-"])
        out.append(
            "  batch %d: figure %d, not-confident grade lines %d (%+d), "
            "members %d (%+d)"
            % (
                b,
                INFO_ROWS[b],
                lines,
                lines - INFO_ROWS[b],
                drawings,
                drawings - INFO_ROWS[b],
            )
        )
        if b in INFO_WORDS:
            got = tuple(
                len([m for m in a.members if m.batch == b and m.first_grade == w])
                for w in NOT_CONFIDENT
            )
            out.append(
                "    by word (weakest, weak in one half, doubtful): "
                "figure %s, members %s" % (INFO_WORDS[b], got)
            )
    out.append(
        "  all members: figure %d with the four named, members %d (%+d)"
        % (INFO_TOTAL, len(a.members), len(a.members) - INFO_TOTAL)
    )
    out.append(
        "  drawings graded after the fact: figure %d, got %d"
        % (INFO_UNGRADED, a.after_rows)
    )
    return out


def set_lines(a: Analysis) -> List[str]:
    lines = [
        "# redraw set: code point, character, form set, batch, first grade, "
        "source, named"
    ]
    for m in sorted(a.members, key=lambda m: (m.batch, m.key)):
        lines.append(
            "\t".join(
                [
                    cp_text(m.key[0]),
                    chr(m.key[0]),
                    m.key[1],
                    "b%d" % m.batch,
                    m.first_grade,
                    m.source,
                    m.named,
                ]
            )
        )
    return lines


def failures(a: Analysis) -> List[str]:
    return list(a.errors)


def run(
    drawn: Table, grades: Table, after: Optional[Table]
) -> Tuple[int, List[str], Analysis]:
    a = analyse(drawn, grades, after)
    tables = [drawn, grades] + ([after] if after is not None else [])
    out = render(a, tables)
    bad = failures(a)
    for line in bad:
        out.append("FAILED: " + line)
    return (1 if bad else 0), out, a


def read_table(path: str) -> Table:
    with open(path, "rb") as fh:
        data = fh.read()
    return Table(path.replace("\\", "/").split("/")[-1], data.decode("utf-8"))


def table(rows: Sequence[Sequence[str]]) -> str:
    return "# fixture\n" + "".join("\t".join(r) + "\n" for r in rows)


def fixture() -> Tuple[List[List[str]], List[List[str]]]:
    """A small clean pair of tables: every drawing graded, the four named present."""
    drawn = [
        ["U+4E00", "jp", "b2"],
        ["U+4E8C", "jp", "b2"],
        ["U+4E09", "sc", "b3"],
        ["U+4EBA", "jp", "b3"],
        ["U+4EBA", "sc", "b3"],
        ["U+4E5D", "sc", "b3"],
        ["U+975E", "jp", "b8"],
        ["U+54C1", "jp", "b8"],
        ["U+76EE", "jp", "b8"],
        ["U+8BA1", "sc", "b8"],
    ]
    grades = [
        ["U+4E00", "jp", "b2", BATCH2_LIST, "b2-evidence.md:10"],
        ["U+4E8C", "jp", "b2", WORD_SURE, "b2-evidence.md:11"],
        ["U+4E09", "sc", "b3", WORD_WEAKEST, "b3-evidence.md:5"],
        ["U+4EBA", BOTH, "b3", WORD_DOUBTFUL, "b3-evidence.md:6"],
        ["U+4E5D", "sc", "b3", WORD_SURE, "b3-evidence.md:7"],
        ["U+975E", "jp", "b8", WORD_SURE, "b8-evidence.md:20"],
        ["U+54C1", "jp", "b8", WORD_SURE, "b8-evidence.md:21"],
        ["U+76EE", "jp", "b8", WORD_SURE, "b8-evidence.md:22"],
        ["U+8BA1", "sc", "b8", WORD_SURE, "b8-evidence.md:23"],
    ]
    return drawn, grades


def case(
    drawn: Sequence[Sequence[str]],
    grades: Sequence[Sequence[str]],
    after: Optional[Sequence[Sequence[str]]] = None,
) -> Tuple[int, List[str], Analysis]:
    return run(
        Table("drawn.tsv", table(drawn)),
        Table("grades.tsv", table(grades)),
        Table("after.tsv", table(after)) if after is not None else None,
    )


def controls() -> int:
    results: List[Tuple[str, bool, str]] = []

    def record(label: str, ok: bool, what: str) -> None:
        results.append((label, ok, what))

    drawn, grades = fixture()
    code, out, a = case(drawn, grades)
    keys = [m.key for m in a.members]
    record(
        "base",
        code == 0
        and len(a.members) == 8
        and all((cp, f) in keys for cp, f, _ in NAMED),
        "a clean fixture exits 0 with 8 members, the four named among them "
        "(exit %d, members %d)" % (code, len(a.members)),
    )

    # c1: an ungraded drawing is planted
    code, out, a = case(drawn, [g for g in grades if g[0] != "U+4E8C"])
    record(
        "c1",
        code != 0
        and any(
            "ungraded: U+4E8C" in line or "U+4E8C set=jp batch 2" in line
            for line in out
        ),
        "an ungraded drawing: exit %d, named U+4E8C" % code,
    )
    # c2: an empty grade table
    code, out, a = case(drawn, [])
    record(
        "c2",
        code != 0 and any("examined: 0 grade records" in line for line in out),
        "an empty grade table: exit %d, 'examined: 0 grade records' printed" % code,
    )
    # c3: a fairly sure drawing that is not one of the four is absent
    code, out, a = case(drawn, grades)
    record(
        "c3",
        code == 0
        and (0x4E8C, "jp") not in [m.key for m in a.members]
        and (0x4E5D, "sc") not in [m.key for m in a.members],
        "fairly sure drawings that are not named are absent from the set (exit %d)"
        % code,
    )
    # c4: a named drawing missing from the drawn sets
    code, out, a = case(
        [d for d in drawn if d[0] != "U+54C1"], [g for g in grades if g[0] != "U+54C1"]
    )
    record(
        "c4",
        code != 0
        and any("U+54C1 set=jp (order 523) is in no drawn set" in line for line in out),
        "a named drawing missing from the drawn sets: exit %d, named U+54C1" % code,
    )
    # c5: a grade line for a drawing its batch did not make
    code, out, a = case(
        drawn, grades + [["U+4E8D", "jp", "b4", WORD_WEAKEST, "b4-evidence.md:3"]]
    )
    code_b, out_b, a_b = case(
        drawn, grades + [["U+4E09", "sc", "b4", WORD_WEAKEST, "b4-evidence.md:3"]]
    )
    record(
        "c5",
        code != 0
        and any(
            "U+4E8D set=jp batch 4: a grade for a drawing no batch made" in line
            for line in out
        )
        and code_b != 0
        and any("graded in batch 4, drawn in batch 3" in line for line in out_b),
        "a grade for a drawing no batch made: exit %d; for a drawing another "
        "batch made: exit %d" % (code, code_b),
    )
    # c6: a "both sets" entry names two drawings
    code, out, a = case(drawn, grades)
    both = [m.key for m in a.members if m.key[0] == 0x4EBA]
    record(
        "c6",
        code == 0 and sorted(both) == [(0x4EBA, "jp"), (0x4EBA, "sc")],
        "a 'both sets' entry gives two members: %s"
        % ", ".join(key_text(k) for k in sorted(both)),
    )
    # x1: a grade after the fact for a drawing that already has a grade is refused
    code, out, a = case(
        drawn, grades, [["U+4E8C", "jp", "b2", WORD_WEAKEST, "2026-11-19", AFTER_NOTE]]
    )
    record(
        "x1",
        code != 0 and any("already has a grade" in line for line in out),
        "a grade after the fact on a graded drawing: exit %d, refused" % code,
    )
    # x2: a drawing graded after the fact completes the set
    code, out, a = case(
        drawn,
        [g for g in grades if g[0] != "U+4E8C"],
        [["U+4E8C", "jp", "b2", WORD_DOUBTFUL, "2026-11-19", AFTER_NOTE]],
    )
    record(
        "x2",
        code == 0
        and (0x4E8C, "jp") in [m.key for m in a.members]
        and a.after_rows == 1,
        "an ungraded drawing graded after the fact joins the set: exit %d" % code,
    )
    for label, ok, what in results:
        sys.stdout.write(
            "control %-4s %s: %s\n"
            % (
                label,
                ("passes" if label == "base" else "killed") if ok else "NOT KILLED",
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
    ap.add_argument("--drawn", help="the drawn table")
    ap.add_argument("--grades", help="the grade table")
    ap.add_argument("--after", help="the table of grades given after the fact")
    ap.add_argument("--out", help="write the set here when every check passes")
    ap.add_argument("--controls", action="store_true", help="run the planted controls")
    args = ap.parse_args(argv)
    if args.controls:
        return controls()
    if not args.drawn or not args.grades:
        sys.stdout.write("usage: --drawn and --grades are required\n")
        return 2
    try:
        drawn = read_table(args.drawn)
        grades = read_table(args.grades)
        after = read_table(args.after) if args.after else None
    except (OSError, UnicodeDecodeError) as exc:
        sys.stdout.write("could not read an input: %s\n" % exc)
        return 2
    code, out, a = run(drawn, grades, after)
    for line in out:
        sys.stdout.write(line + "\n")
    if code == 0 and args.out:
        body = ("\n".join(set_lines(a)) + "\n").encode("utf-8")
        with open(args.out, "wb") as fh:
            fh.write(body)
        sys.stdout.write(
            "written: %s, %d members, sha256 %s\n"
            % (
                args.out.replace("\\", "/").split("/")[-1],
                len(a.members),
                hashlib.sha256(body).hexdigest(),
            )
        )
    sys.stdout.write("exit %d\n" % code)
    return code


if __name__ == "__main__":
    sys.exit(main())
