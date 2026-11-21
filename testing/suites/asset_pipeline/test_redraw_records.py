# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tests of ``scripts/font/check_redraw_records.py`` (SC-L10N-BUILD-010-2 and -3).

The scenarios: every member of the redraw set has exactly one redraw record, naming the
drawing it replaces, its first grade, the visual reference looked at, the disagreement
with its cited place and its new grade; each record names its own form set's build of
the reference; the face holds the redrawn drawing; the new grades, the pixel-equal count
and the drawings whose record records a disagreement are printed and fail nothing; a
member with no record, or a record naming no reference, fails and is named (-2). The
reference is used only where the ruling allows: a reference on a drawing outside the
set, the other form set's build, or a font other than the two builds, each exits
non-zero naming the drawing and the typeface (-3).

Every case runs the script as a real subprocess over a ROOT WRITTEN HERE under the
scratch folder: ``fonts-src/nifen-art-cjk/`` holding the redraw records, the two Han
face files and the citation records, as the script reads them under ``--root``. The
citation file is always present in a clean root (without it the script exits 2, and
every plant would "fail" for the wrong reason); the expected counts are computed from
the records by this module, and the sha256 of a drawing's record is computed here from
the face text, as the script's documentation states it. The exit codes are asserted
exactly (1 for a plant, 0 for the clean root, 2 for a missing input), and a plant is
read against the clean root, which passes first. The typeface tokens are read from the
script's own constants, never written in this module.

The committed records and faces under ``fonts-src/nifen-art-cjk`` are only READ (the
last case of -2); every plant is a scratch copy. Test seam: ``NIFEN_TOOLS_ROOT``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence

import pytest

from .redraw_support import (
    CJK_REL,
    CJK_SOURCES,
    REDRAW_RECORDS,
    TOOLS_ROOT,
    Run,
    data_lines,
    load_tool,
    printed,
    run_font_tool,
    sha256_hex,
)

TOOL = load_tool(REDRAW_RECORDS)
REF_JP = TOOL.REFERENCES["jp"]
REF_SC = TOOL.REFERENCES["sc"]
NO_REF = TOOL.NO_REFERENCE

WEAKEST, WEAK_HALF, DOUBTFUL, SURE = (
    "weakest",
    "weak in one half",
    "doubtful",
    "fairly sure",
)
PLACE_4E8C = "joyo-2010 page=61 pos=700"
NO_ENTRY_PLACE = "no-entry absent=joyo-2010,hyogai-2000"
RECORDS_NAME = "redraw-records.txt"
CITATIONS_NAME = "han-citations.txt"


class Rec(NamedTuple):
    """One redraw record, the eleven fields in the order the script documents."""

    cp: str
    form: str
    batch: str
    first: str
    status: str
    reference: str
    disagreement: str
    new_grade: str
    old_sha: str
    new_sha: str
    date: str = "2026-11-19"

    @property
    def line(self) -> str:
        return "\t".join(self)

    @property
    def key(self) -> str:
        return "%s set=%s" % (self.cp, self.form)


def header(cp: str, form: str) -> str:
    return "glyph %s set=%s src=drawn top=3 x=0" % (cp, form)


#: The faces as they stand after the redraw (what the records' new sha256 must match)
#: and as they stood before it (what the records' old sha256 hashes).
NEW_ROWS: Dict[str, Dict[str, List[str]]] = {
    "jp": {
        "U+4E00": ["###########"],
        "U+4E8C": ["##.", "###"],
        "U+4E5F": ["#.#"],
        "U+975E": ["#.#", "###", "#.#"],
    },
    "sc": {
        "U+4E09": ["###", "#.#"],
        "U+4EBA": ["#.", "##"],
        "U+8BA1": ["##", "#."],
    },
}
OLD_ROWS: Dict[str, Dict[str, List[str]]] = {
    "jp": {
        "U+4E00": ["##########"],
        "U+4E8C": ["#.#"],
        "U+4E5F": ["#.#"],
        "U+975E": ["###"],
    },
    "sc": {
        "U+4E09": ["###", "#.#"],  # pixel-equal: the redraw left it as it was
        "U+4EBA": ["##", "#."],
        "U+8BA1": ["#.", "##"],
    },
}

#: Citation records: U+975E has a no-entry record, U+4E5F and U+8BA1 have none.
CITATIONS = (
    "# fixture\n"
    "JP | U+4E00 | joyo-2010 | page=13 pos=41 | via=textlayer\n"
    "JP | U+4E8C | joyo-2010 | page=61 pos=700 | via=textlayer\n"
    "JP | U+975E | no-entry | absent=joyo-2010,hyogai-2000 | via=membership\n"
    "SC | U+4E09 | tongyong-2013 | page=8 cell=0001 | via=index-agree\n"
    "SC | U+4EBA | tongyong-2013 | page=8 cell=0010 | via=index-agree\n"
)


def sha_of(rows: Dict[str, Dict[str, List[str]]], cp: str, form: str) -> str:
    """The sha256 of a drawing's record: its header line and its rows, each with a LF.

    Written here from the script's documentation, not taken from the script."""
    text = "\n".join([header(cp, form)] + rows[form][cp]) + "\n"
    return sha256_hex(text.encode("utf-8"))


def rec(
    cp: str,
    form: str,
    batch: int,
    first: str,
    reference: str,
    new_grade: str,
    disagreement: str = "-",
    status: str = "redrawn",
) -> Rec:
    return Rec(
        cp,
        form,
        "b%d" % batch,
        first,
        status,
        reference,
        disagreement,
        new_grade,
        sha_of(OLD_ROWS, cp, form),
        sha_of(NEW_ROWS, cp, form),
    )


def base_records() -> List[Rec]:
    return [
        rec("U+4E00", "jp", 2, WEAKEST, REF_JP, DOUBTFUL),
        rec("U+4E8C", "jp", 3, DOUBTFUL, REF_JP, WEAK_HALF, PLACE_4E8C),
        rec("U+975E", "jp", 8, SURE, REF_JP, SURE),
        rec("U+4E09", "sc", 3, WEAKEST, REF_SC, DOUBTFUL),
        rec("U+4EBA", "sc", 9, WEAK_HALF, NO_REF, DOUBTFUL),
        rec("U+8BA1", "sc", 8, SURE, REF_SC, SURE),
    ]


def with_record(
    records: Sequence[Rec], cp: str, form: str, **changes: str
) -> List[Rec]:
    """``records`` with the record of one drawing changed (it must exist once)."""
    hit = [i for i, r in enumerate(records) if (r.cp, r.form) == (cp, form)]
    assert len(hit) == 1, (cp, form, hit)
    out = list(records)
    out[hit[0]] = out[hit[0]]._replace(**changes)
    return out


def member_lines(records: Sequence[Rec]) -> str:
    """A redraw set that names exactly these drawings (the script reads 7 fields)."""
    rows = [
        "\t".join([r.cp, "x", r.form, r.batch, r.first, "a:%d" % i, "-"])
        for i, r in enumerate(records, 1)
    ]
    return "# fixture\n" + "\n".join(rows) + "\n"


def face_text(form: str, rows: Dict[str, Dict[str, List[str]]]) -> str:
    parts = ["# fixture"]
    for cp in sorted(rows[form]):
        parts += ["", header(cp, form)] + rows[form][cp]
    return "\n".join(parts) + "\n"


class Root(NamedTuple):
    """A scratch root and what was written into it."""

    root: Path
    records: List[Rec]
    set_file: Path

    @property
    def records_file(self) -> Path:
        return self.root.joinpath(*CJK_REL, RECORDS_NAME)


def build_root(
    scratch: Path,
    records: Optional[Sequence[Rec]] = None,
    *,
    citations: Optional[str] = CITATIONS,
    new_rows: Optional[Dict[str, Dict[str, List[str]]]] = None,
    set_of: Optional[Sequence[Rec]] = None,
    raw_records: Optional[str] = None,
) -> Root:
    """A root holding the redraw records, the two Han faces and the citation file."""
    recs = list(base_records() if records is None else records)
    folder = scratch / "root"
    cjk = folder.joinpath(*CJK_REL)
    cjk.mkdir(parents=True)
    body = raw_records if raw_records is not None else "\n".join(r.line for r in recs)
    (cjk / RECORDS_NAME).write_bytes(("# fixture\n" + body + "\n").encode("utf-8"))
    faces = new_rows or NEW_ROWS
    for form in ("jp", "sc"):
        (cjk / ("han-%s.txt" % form)).write_bytes(face_text(form, faces).encode())
    if citations is not None:
        (cjk / CITATIONS_NAME).write_bytes(citations.encode("utf-8"))
    set_file = scratch / "redraw-set.tsv"
    set_file.write_bytes(member_lines(set_of or base_records()).encode("utf-8"))
    return Root(folder, recs, set_file)


def check(
    scratch: Path, root: Root, *, with_set: bool = True, partial: bool = False
) -> Run:
    args: List[object] = ["--root", root.root]
    if with_set:
        args += ["--set", root.set_file]
    if partial:
        args.append("--partial")
    return run_font_tool(REDRAW_RECORDS, args, scratch)


def clean(scratch: Path) -> Run:
    """The control every plant is read against: the clean root passes, exit 0."""
    done = check(scratch, build_root(scratch / "clean-control"))
    return done


@pytest.fixture
def control(font_scratch: Path) -> Run:
    (font_scratch / "clean-control").mkdir()
    done = clean(font_scratch)
    assert done.returncode == 0, done.text
    return done


def findings(res: Run, *tokens: str) -> None:
    """One finding line names every token together (a drawing and a typeface, or a
    path). The run's summary lines print the two typeface tokens whatever happens, so
    a token anywhere in the output proves nothing: it must stand on the line of the
    finding. The message sentences are not asserted."""
    lines = res.stdout.split("\n")
    lines = [ln for ln in lines if ln.startswith(("FAILED", "could not"))]
    assert any(all(t in ln for t in tokens) for ln in lines), (tokens, lines)


def plant(font_scratch: Path, name: str) -> Path:
    folder = font_scratch / name
    folder.mkdir()
    return folder


# --- SC-L10N-BUILD-010-2: one record per member, the face holds the drawing ----------


def test_sc_l10n_build_010_2_every_member_has_exactly_one_record(font_scratch, control):
    """SC-L10N-BUILD-010-2: with the set given, every member has one record and none is
    missing; the number of records examined is printed, is not zero and equals the
    lines of the records file; each drawing of the set is named by one line."""
    recs = base_records()
    seen = [r.key for r in recs]
    assert len(seen) == len(set(seen)) == 6, seen
    assert control.returncode == 0, control.text
    found = re.search(r"^redraw records examined: (\d+)$", control.stdout, re.M)
    assert found and int(found[1]) == len(recs) > 0, control.stdout
    members = re.search(
        r"^members of the redraw set: (\d+), with no record yet: (\d+)$",
        control.stdout,
        re.M,
    )
    assert members and (int(members[1]), int(members[2])) == (len(recs), 0)
    printed(records_examined=found[1], members=members[1])


def test_sc_l10n_build_010_2_every_record_names_its_own_form_sets_build(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: the reference of each record is its own form set's build
    (the two the script names), or none on a line of a later batch; the printed counts
    equal the ones this module counts from the records."""
    recs = base_records()
    for r in recs:
        own = REF_JP if r.form == "jp" else REF_SC
        assert r.reference in (own, NO_REF), r
    counts = {
        REF_JP: sum(r.reference == REF_JP for r in recs),
        REF_SC: sum(r.reference == REF_SC for r in recs),
        NO_REF: sum(r.reference == NO_REF for r in recs),
    }
    line = "reference: none %d, %s %d, %s %d" % (
        counts[NO_REF],
        REF_JP,
        counts[REF_JP],
        REF_SC,
        counts[REF_SC],
    )
    assert line in control.stdout.split("\n"), control.stdout
    printed(per_typeface=counts)


def test_sc_l10n_build_010_2_the_face_holds_the_redrawn_drawing(font_scratch, control):
    """SC-L10N-BUILD-010-2: the face holds the redrawn drawing, not the one it
    replaces. Control: each record's new sha256 equals the hash this module takes of
    the face's record. Plant: the face still holds the old drawing of U+4E8C."""
    for r in base_records():
        assert r.new_sha == sha_of(NEW_ROWS, r.cp, r.form)
        assert r.new_sha != sha_of(OLD_ROWS, r.cp, r.form) or r.cp == "U+4E09"
    old_face = {"jp": dict(NEW_ROWS["jp"]), "sc": dict(NEW_ROWS["sc"])}
    old_face["jp"]["U+4E8C"] = OLD_ROWS["jp"]["U+4E8C"]
    done = check(font_scratch, build_root(plant(font_scratch, "p"), new_rows=old_face))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C")


def test_sc_l10n_build_010_2_the_new_grades_are_printed_with_counts_failing_nothing(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: the new grades are printed with their counts, each equal to
    the count this module takes from the records, and the run exits 0."""
    recs = base_records()
    assert control.returncode == 0
    for word in (WEAKEST, WEAK_HALF, DOUBTFUL, SURE):
        n = sum(1 for r in recs if r.new_grade == word)
        assert "  %s: %d" % (word, n) in control.stdout.split("\n"), (word, n)
    printed(
        new_grades={w: sum(r.new_grade == w for r in recs) for w in (DOUBTFUL, SURE)}
    )


def test_sc_l10n_build_010_2_the_pixel_equal_count_is_printed_failing_nothing(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: the number of redrawn drawings whose pixels equal the
    drawing they replace is printed (the fixture holds one) and fails nothing."""
    recs = base_records()
    equal = sum(r.old_sha == r.new_sha for r in recs)
    assert equal == 1
    line = "pixel-equal to the drawing replaced: %d of %d redrawn, information" % (
        equal,
        len(recs),
    )
    assert control.returncode == 0 and line in control.stdout.split(
        "\n"
    ), control.stdout


def test_sc_l10n_build_010_2_disagreements_are_printed_apart_failing_nothing(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: the drawings whose record records a disagreement
    with the cited place are printed apart by code point, form set and cited place,
    with their count, and the run still exits 0."""
    lines = control.stdout.split("\n")
    assert control.returncode == 0
    assert "  disagreement U+4E8C set=jp cited place %s" % PLACE_4E8C in lines
    counted = [ln for ln in lines if ln.startswith("disagreements with the cited")]
    assert len(counted) == 1 and counted[0].endswith(": 1"), counted


def test_sc_l10n_build_010_2_a_member_with_no_record_fails_and_is_named(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a member planted with no redraw record makes the check exit
    1 and name it; a partial run lists it instead and exits 0."""
    recs = [r for r in base_records() if r.cp != "U+8BA1"]
    root = build_root(plant(font_scratch, "p"), recs, set_of=base_records())
    done = check(font_scratch, root)
    assert done.returncode == 1, done.text
    findings(done, "U+8BA1")
    soft = check(font_scratch, root, partial=True)
    assert soft.returncode == 0, soft.text
    assert "with no record yet: 1 (partial run)" in soft.stdout


@pytest.mark.parametrize("cp,form", [("U+4E8C", "jp"), ("U+4E09", "sc")])
def test_sc_l10n_build_010_2_a_record_that_names_no_visual_reference_fails(
    font_scratch, control, cp, form
):
    """SC-L10N-BUILD-010-2: a record of batches 2 to 8 that names no visual reference
    makes the check exit 1 and name the drawing."""
    recs = with_record(base_records(), cp, form, reference=NO_REF)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, cp)


def test_sc_l10n_build_010_2_a_line_left_pending_fails_and_a_held_one_is_refused(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a member line left pending exits 1, naming it, and a line
    with the held status is refused by name (nothing is held)."""
    pending = with_record(base_records(), "U+4E8C", "jp", status="pending")
    done = check(font_scratch, build_root(plant(font_scratch, "p1"), pending))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C")
    assert "pending: 1" in done.stdout.split("\n")
    held = with_record(base_records(), "U+4E8C", "jp", status="held-QRS")
    done = check(font_scratch, build_root(plant(font_scratch, "p2"), held))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C", "held-QRS")


def test_sc_l10n_build_010_2_a_second_line_for_one_drawing_fails(font_scratch, control):
    """SC-L10N-BUILD-010-2: exactly one record per member: a second line for one
    drawing exits 1 and names it."""
    recs = base_records() + [base_records()[1]]
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C")


def test_sc_l10n_build_010_2_a_records_file_with_no_line_examined_fails(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a records file holding no record is not a pass: exit 1
    with 0 records examined."""
    root = build_root(plant(font_scratch, "p"), [], raw_records="# no record")
    done = check(font_scratch, root, with_set=False)
    assert done.returncode == 1, done.text
    assert "redraw records examined: 0" in done.stdout.split("\n")


def test_sc_l10n_build_010_2_the_committed_records_pass_on_the_real_data(font_scratch):
    """SC-L10N-BUILD-010-2 on the product's own data: the committed redraw records,
    read against the committed faces and citation records, exit 0 with 0 pending, and
    the lines examined equal the lines of the file, counted here."""
    path = CJK_SOURCES / RECORDS_NAME
    lines = data_lines(path)
    redrawn = [ln for ln in lines if ln.split("\t")[4] == "redrawn"]
    assert len(lines) > 0 and len(redrawn) == len(lines), "a line is not redrawn"
    done = run_font_tool(REDRAW_RECORDS, [], font_scratch)
    assert done.returncode == 0, done.text
    assert "redraw records examined: %d" % len(lines) in done.stdout.split("\n")
    assert "status: redrawn %d, pending 0" % len(redrawn) in done.stdout.split("\n")
    assert "pending: 0" in done.stdout.split("\n")
    printed(real_records=len(lines), redrawn=len(redrawn), root=TOOLS_ROOT.name)


# --- The citation file (the record form of round 28, restated by r64) -----------------


def test_sc_l10n_build_010_2_a_root_without_the_citation_file_exits_2_naming_it(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: the citation file is read under ``--root``; a root
    without it exits 2 (the script did not run), naming it, and never 1."""
    root = build_root(plant(font_scratch, "p"), citations=None)
    done = check(font_scratch, root)
    assert done.returncode == 2, done.text
    findings(done, CITATIONS_NAME)


def test_sc_l10n_build_010_2_a_disagreement_on_a_drawing_with_no_citation_record(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a drawing that has no citation record carries a dash; a
    disagreement on U+8BA1, which has none, exits 1 and names it."""
    recs = with_record(
        base_records(), "U+8BA1", "sc", disagreement="tongyong-2013 page=1 cell=0001"
    )
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+8BA1")


def test_sc_l10n_build_010_2_a_disagreement_on_a_no_entry_drawing_exits_1(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a no-entry drawing cites no place and carries a dash; a
    disagreement on U+975E exits 1 and names it, even when it repeats the words of the
    no-entry record (which cites no place of a standard)."""
    standard, place = NO_ENTRY_PLACE.split(" ", 1)
    assert CITATIONS.count("| %s | %s |" % (standard, place)) == 1
    recs = with_record(base_records(), "U+975E", "jp", disagreement=NO_ENTRY_PLACE)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+975E")


def test_sc_l10n_build_010_2_a_disagreement_naming_another_place_exits_1(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: a disagreement must equal the drawing's cited place; U+4E8C
    naming another place exits 1 and names the drawing."""
    recs = with_record(
        base_records(), "U+4E8C", "jp", disagreement="joyo-2010 page=99 pos=999"
    )
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C")


def test_sc_l10n_build_010_2_a_named_drawing_on_a_later_batch_naming_none_exits_1(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2: one of the four named drawings names its own form set's
    build whatever its batch field; U+975E on a batch 9 line with ``none`` exits 1."""
    recs = with_record(base_records(), "U+975E", "jp", batch="b9", reference=NO_REF)
    # the set is written from the same records, so that no batch mismatch fails the
    # line for another reason
    root = build_root(plant(font_scratch, "p"), recs, set_of=recs)
    done = check(font_scratch, root)
    assert done.returncode == 1, done.text
    findings(done, "U+975E")


def test_sc_l10n_build_010_2_a_later_batch_may_name_none_or_its_own_build(
    font_scratch, control
):
    """SC-L10N-BUILD-010-2 (the control of the case above): a drawing that is not a
    named one, on a batch 9 line, may name its own build, and the clean root already
    shows it may name none; both exit 0."""
    recs = with_record(base_records(), "U+4EBA", "sc", reference=REF_SC)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 0, done.text


@pytest.mark.parametrize("separator", ["  ", "\t"], ids=["two-spaces", "a-tab"])
def test_sc_l10n_build_010_2_a_disagreement_with_the_wrong_separator_exits_1(
    font_scratch, control, separator
):
    """SC-L10N-BUILD-010-2: the standard and the place are joined by one space; two
    spaces or a tab between them exits 1. A tab adds a field, so the line is named by
    its number as well."""
    standard, place = PLACE_4E8C.split(" ", 1)
    recs = with_record(
        base_records(), "U+4E8C", "jp", disagreement=standard + separator + place
    )
    root = build_root(plant(font_scratch, "p"), recs)
    done = check(font_scratch, root, with_set=separator != "\t")
    assert done.returncode == 1, done.text
    line_number = 1 + 1 + [r.cp for r in recs].index("U+4E8C")
    findings(
        done, "%s:%d" % (RECORDS_NAME, line_number) if separator == "\t" else "U+4E8C"
    )


# --- SC-L10N-BUILD-010-3: the visual reference is used only where the ruling allows ---


@pytest.mark.parametrize("with_set", [True, False], ids=["set-given", "no-set"])
def test_sc_l10n_build_010_3_a_reference_on_a_drawing_outside_the_set_exits_1(
    font_scratch, control, with_set
):
    """SC-L10N-BUILD-010-3, row 'a visual reference named on a drawing outside the
    redraw set that no batch grades not confident': a record of U+4E5F, graded fairly
    sure and not in the set, names a build; the check exits 1, naming the drawing and
    the typeface."""
    extra = rec("U+4E5F", "jp", 3, SURE, REF_JP, SURE)
    recs = base_records() + [extra]
    root = build_root(plant(font_scratch, "p"), recs, set_of=base_records())
    done = check(font_scratch, root, with_set=with_set)
    assert done.returncode == 1, done.text
    findings(done, "U+4E5F", REF_JP)


def test_sc_l10n_build_010_3_the_simplified_build_on_a_japanese_form_drawing(
    font_scratch, control
):
    """SC-L10N-BUILD-010-3, row 'the Simplified Chinese build named on a Japanese-form
    drawing': exit 1, naming U+4E8C and the Simplified-form build."""
    recs = with_record(base_records(), "U+4E8C", "jp", reference=REF_SC)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C", REF_SC)


def test_sc_l10n_build_010_3_the_japanese_build_on_a_simplified_form_drawing(
    font_scratch, control
):
    """SC-L10N-BUILD-010-3, row 'the Japanese build named on a Simplified-form
    drawing': exit 1, naming U+4E09 and the Japanese-form build."""
    recs = with_record(base_records(), "U+4E09", "sc", reference=REF_JP)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+4E09", REF_JP)


@pytest.mark.parametrize(
    "other", ["Yu Gothic Medium", "Microsoft YaHei", "Other Test Face"]
)
def test_sc_l10n_build_010_3_a_font_other_than_the_two_builds_is_refused(
    font_scratch, control, other
):
    """SC-L10N-BUILD-010-3, row 'a font other than those two builds named as a visual
    reference, Yu Gothic Medium or Microsoft YaHei among the plants': exit 1, naming
    the drawing and the font."""
    recs = with_record(base_records(), "U+4E8C", "jp", reference=other)
    done = check(font_scratch, build_root(plant(font_scratch, "p"), recs))
    assert done.returncode == 1, done.text
    findings(done, "U+4E8C", other)
