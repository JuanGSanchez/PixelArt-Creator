# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tests of ``scripts/font/redraw_set.py`` (SC-L10N-BUILD-010-1, REQ-L10N-BUILD-010).

The scenario: given the grade records of batches 2 to 8, the redraw-set script builds
the set of the not-confident drawings (graded weakest, weak in one half or doubtful,
or on batch 2's list of drawings its designer is not confident about) and the four
named drawings, and no other drawing graded fairly sure. The members are printed by
code point, form set and batch with counts per batch, per grade and per form set; the
number of grade records examined is printed and is non-zero; a drawing of batches 2 to
8 with no recorded grade makes the script exit non-zero and names it.

Every case runs the script as a real subprocess over small tables written HERE, in a
scratch folder. The expected set is computed by this module from the rule in the
scenario (not read from the script's own report), and the real grade tables of the
job are not read: they live outside the product repository. Each case is paired with
the clean run, which passes first, so a failing case cannot be a broken fixture.

The exit codes are asserted exactly (0 built, 1 a check failed, 2 an input could not
be read), never as "non-zero": a plant that exits 2 would otherwise pass for the wrong
reason. Test seam: ``NIFEN_TOOLS_ROOT`` (see ``redraw_support``).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Set, Tuple

import pytest

from .redraw_support import REDRAW_SET, Run, printed, run_font_tool

WEAKEST = "weakest"
WEAK_HALF = "weak in one half"
DOUBTFUL = "doubtful"
SURE = "fairly sure"
B2_LIST = "b2-list"
NOT_CONFIDENT = (WEAKEST, WEAK_HALF, DOUBTFUL, B2_LIST)
GRADE_WORDS = (WEAKEST, WEAK_HALF, DOUBTFUL, SURE, B2_LIST)

#: The four named drawings, from the scenario: code point, form set, order number.
NAMED = (
    ("U+975E", "jp", "517"),
    ("U+54C1", "jp", "523"),
    ("U+76EE", "jp", "525"),
    ("U+8BA1", "sc", "541"),
)


class Grade(NamedTuple):
    """One grade line: code point, form set ("both" names two drawings), batch."""

    cp: str
    form: str
    batch: str
    word: str
    source: str


#: A clean fixture: every drawing graded, the four named drawings present (one of them
#: graded doubtful, to show that a named drawing is in the set once whatever its grade).
GRADES: Tuple[Grade, ...] = (
    Grade("U+4E00", "jp", "b2", B2_LIST, "b2-evidence.md:10"),
    Grade("U+4E8C", "jp", "b2", SURE, "b2-evidence.md:11"),
    Grade("U+4E09", "sc", "b3", WEAKEST, "b3-evidence.md:5"),
    Grade("U+4EBA", "both", "b3", DOUBTFUL, "b3-evidence.md:6"),
    Grade("U+4E5D", "sc", "b3", SURE, "b3-evidence.md:7"),
    Grade("U+5927", "jp", "b4", WEAK_HALF, "b4-evidence.md:2"),
    Grade("U+5C0F", "sc", "b4", SURE, "b4-evidence.md:3"),
    Grade("U+6728", "jp", "b5", SURE, "b5-evidence.md:4"),
    Grade("U+6C34", "sc", "b6", DOUBTFUL, "b6-evidence.md:1"),
    Grade("U+706B", "jp", "b7", WEAKEST, "b7-evidence.md:9"),
    Grade("U+5C71", "jp", "b8", SURE, "b8-evidence.md:3"),
    Grade("U+975E", "jp", "b8", SURE, "b8-evidence.md:20"),
    Grade("U+54C1", "jp", "b8", SURE, "b8-evidence.md:21"),
    Grade("U+76EE", "jp", "b8", DOUBTFUL, "b8-evidence.md:22"),
    Grade("U+8BA1", "sc", "b8", SURE, "b8-evidence.md:23"),
)

Key = Tuple[str, str]


def drawings(grades: Sequence[Grade]) -> List[Tuple[str, str, str]]:
    """The drawn table of a grade list: one row per drawing ("both" is two)."""
    rows = []
    for g in grades:
        for form in ("jp", "sc") if g.form == "both" else (g.form,):
            rows.append((g.cp, form, g.batch))
    return rows


def expected_members(grades: Sequence[Grade]) -> Dict[Key, Tuple[str, str]]:
    """The scenario's rule, applied here: (cp, form) -> (batch, first grade)."""
    named = {(cp, form) for cp, form, _order in NAMED}
    out: Dict[Key, Tuple[str, str]] = {}
    for g in grades:
        for form in ("jp", "sc") if g.form == "both" else (g.form,):
            if g.word in NOT_CONFIDENT or (g.cp, form) in named:
                out[(g.cp, form)] = (g.batch, g.word)
    return out


def tsv(rows: Sequence[Sequence[str]]) -> str:
    return "# fixture\n" + "".join("\t".join(r) + "\n" for r in rows)


class SetRun(NamedTuple):
    run: Run
    out_file: Path
    grade_lines: int

    @property
    def members(self) -> List[List[str]]:
        """The rows the script wrote to its ``--out`` file, as fields."""
        text = self.out_file.read_bytes().decode("utf-8")
        return [
            ln.split("\t")
            for ln in text.split("\n")
            if ln.strip() and not ln.startswith("#")
        ]


def run_set(
    scratch: Path,
    grades: Sequence[Grade] = GRADES,
    *,
    drawn: Sequence[Tuple[str, str, str]] = (),
    grade_rows: Sequence[Sequence[str]] = (),
) -> SetRun:
    """Write the two tables under ``scratch`` and run the script over them."""
    drawn_rows = list(drawn or drawings(grades))
    lines = list(grade_rows or [list(g) for g in grades])
    (scratch / "drawn.tsv").write_bytes(tsv(drawn_rows).encode("utf-8"))
    (scratch / "grades.tsv").write_bytes(tsv(lines).encode("utf-8"))
    out = scratch / "redraw-set.tsv"
    res = run_font_tool(
        REDRAW_SET,
        ["--drawn", scratch / "drawn.tsv", "--grades", scratch / "grades.tsv"]
        + ["--out", out],
        scratch,
    )
    return SetRun(res, out, len(lines))


def clean(scratch: Path) -> SetRun:
    """The control every plant is read against: the clean fixture builds, exit 0."""
    done = run_set(scratch)
    assert done.run.returncode == 0, done.run.text
    assert done.out_file.is_file(), done.run.text
    return done


def keys_of(done: SetRun) -> Set[Key]:
    return {(row[0], row[2]) for row in done.members}


def test_sc_l10n_build_010_1_the_set_is_the_not_confident_drawings_and_the_named(
    font_scratch,
):
    """SC-L10N-BUILD-010-1: the set holds every drawing graded weakest, weak in one
    half or doubtful, every drawing on batch 2's list, and the four named drawings;
    the expected set is computed here from the grade lines, drawing by drawing."""
    done = clean(font_scratch)
    want = expected_members(GRADES)
    assert len(want) > len(NAMED), "the fixture has no not-confident drawing"
    assert keys_of(done) == set(want), done.run.text
    assert len(done.members) == len(want), "a drawing is in the set more than once"
    for row in done.members:
        assert (row[3], row[4]) == want[(row[0], row[2])], row
    printed(grade_lines=done.grade_lines, members=len(done.members))


def test_sc_l10n_build_010_1_the_four_named_drawings_are_in_the_set_by_order(
    font_scratch,
):
    """SC-L10N-BUILD-010-1: U+975E, U+54C1 and U+76EE in the Japanese-form set and
    U+8BA1 in the Simplified-form set are members whatever their grade, each carrying
    its order number; no other member carries one."""
    done = clean(font_scratch)
    by_key = {(row[0], row[2]): row for row in done.members}
    for cp, form, order in NAMED:
        assert (cp, form) in by_key, (cp, form, done.run.text)
        assert by_key[(cp, form)][6] == order, by_key[(cp, form)]
        assert "%s set=%s order %s" % (cp, form, order) in done.run.stdout
    carrying_an_order = {(row[0], row[2]) for row in done.members if row[6] != "-"}
    assert carrying_an_order == {(cp, form) for cp, form, _ in NAMED}


def test_sc_l10n_build_010_1_no_other_fairly_sure_drawing_is_in_the_set(font_scratch):
    """SC-L10N-BUILD-010-1: a drawing graded fairly sure that is not one of the four
    named drawings is not in the set. The fixture holds several, and the case names
    each of them."""
    done = clean(font_scratch)
    named = {(cp, form) for cp, form, _ in NAMED}
    sure = [
        (g.cp, form)
        for g in GRADES
        if g.word == SURE
        for form in ("jp", "sc")
        if g.form in (form, "both") and (g.cp, form) not in named
    ]
    assert len(sure) >= 4, sure
    present = keys_of(done)
    assert [k for k in sure if k in present] == [], done.run.text
    printed(fairly_sure_not_named=len(sure))


def test_sc_l10n_build_010_1_members_are_printed_with_counts_per_batch_grade_form(
    font_scratch,
):
    """SC-L10N-BUILD-010-1: the members are printed by batch, grade and form set with
    counts, and each printed count equals the one this module counts."""
    done = clean(font_scratch)
    want = expected_members(GRADES)
    text = done.run.stdout
    per_batch = {
        m[1]: int(m[4])
        for m in re.finditer(r"^  batch (b?\d+): (\d+) / (\d+) / (\d+)$", text, re.M)
    }
    batches = sorted({b for b, _w in want.values()})
    for b in batches:
        n = sum(1 for bb, _w in want.values() if bb == b)
        assert per_batch.get(b.lstrip("b")) == n, (b, per_batch, text)
    per_grade = {
        m[1]: int(m[2])
        for m in re.finditer(
            r"^  ([a-z0-9 -]+): members (\d+), rows (\d+)$", text, re.M
        )
    }
    for word in GRADE_WORDS:
        n = sum(1 for _b, w in want.values() if w == word)
        assert per_grade.get(word) == n, (word, per_grade, text)
    per_form = {m[1]: int(m[2]) for m in re.finditer(r"^  (jp|sc): (\d+)$", text, re.M)}
    for form in ("jp", "sc"):
        n = sum(1 for (_cp, f) in want if f == form)
        assert per_form.get(form) == n, (form, per_form, text)
    printed(per_batch=per_batch, per_grade=per_grade, per_form=per_form)


def test_sc_l10n_build_010_1_the_records_examined_are_printed_and_non_zero(
    font_scratch,
):
    """SC-L10N-BUILD-010-1: the number of grade records examined is printed, is not
    zero and equals the grade lines of the fixture."""
    done = clean(font_scratch)
    found = re.search(
        r"^grade records examined: files (\d+), lines (\d+)$", done.run.stdout, re.M
    )
    assert found, done.run.stdout
    assert int(found[2]) > 0
    assert int(found[2]) == done.grade_lines, done.run.stdout


def test_sc_l10n_build_010_1_a_drawing_with_no_recorded_grade_fails_and_is_named(
    font_scratch,
):
    """SC-L10N-BUILD-010-1: a drawing of batches 2 to 8 with no recorded grade makes
    the script exit 1 and name it; the same fixture without the plant exits 0."""
    clean(font_scratch)
    plant = font_scratch / "plant"
    plant.mkdir()
    lacking = [g for g in GRADES if g.cp != "U+4E8C"]
    done = run_set(plant, lacking, drawn=drawings(GRADES))
    assert done.run.returncode == 1, done.run.text
    assert "U+4E8C" in done.run.stdout, done.run.stdout
    assert not done.out_file.exists(), "a failed run wrote the set"


def test_sc_l10n_build_010_1_a_run_that_examined_no_record_is_not_a_pass(font_scratch):
    """SC-L10N-BUILD-010-1: the number of grade records examined must not be zero. Two
    tables that hold no record exit 1, having examined 0 grade records: a run that
    examined nothing is not read as a set with no member."""
    clean(font_scratch)
    plant = font_scratch / "plant"
    plant.mkdir()
    (plant / "drawn.tsv").write_bytes(b"# fixture: no drawing\n")
    (plant / "grades.tsv").write_bytes(b"# fixture: no grade record\n")
    res = run_font_tool(
        REDRAW_SET,
        ["--drawn", plant / "drawn.tsv", "--grades", plant / "grades.tsv"],
        plant,
    )
    assert res.returncode == 1, res.text
    assert re.search(r"^grade records examined: files 1, lines 0$", res.stdout, re.M)


def test_sc_l10n_build_010_1_an_unreadable_input_exits_2_not_1(font_scratch):
    """SC-L10N-BUILD-010-1 (exit codes): a table that cannot be read is exit 2, so
    that a plant exiting 1 is a finding about the drawings and not about the file."""
    clean(font_scratch)
    res = run_font_tool(
        REDRAW_SET,
        [
            "--drawn",
            font_scratch / "absent.tsv",
            "--grades",
            font_scratch / "grades.tsv",
        ],
        font_scratch,
    )
    assert res.returncode == 2, res.text
    assert "absent.tsv" in res.stdout


@pytest.mark.parametrize("flag", ["--drawn", "--grades"])
def test_sc_l10n_build_010_1_both_tables_are_required(font_scratch, flag):
    """SC-L10N-BUILD-010-1 (usage): the script refuses a run that names one table
    only, with exit 2."""
    clean(font_scratch)
    res = run_font_tool(REDRAW_SET, [flag, font_scratch / "drawn.tsv"], font_scratch)
    assert res.returncode == 2, res.text
