# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The documentation check of the visual reference (SC-L10N-BUILD-010-6).

The scenario: ``FONTLOG-CJK.txt`` and every other product document that lists the
references Nifen Art's glyphs were drawn with (the national standards and the visual
reference) each name every regional build of the visual reference by the family name,
style and version that the licence finding records from that build's own file, with the
form set it served, and the owner as the finding records that file's copyright record;
each states that the reference was used only as a visual reference, looked at by eye,
and that no glyph, outline or bitmap was taken from it; each states how many drawings
were redrawn with each regional build; the reference is not named as a donor, a source,
a copyright holder or a licensor; the number of documents examined is printed and is not
zero; and a document planted that names the reference as a source or as a donor makes
the check exit non-zero and name the document.

THE CHECK is ``document_findings`` below: this module is the documentation check, there
is no script. ``test_*`` cases run it over the real documents and over plants, each
plant a copy of the real text changed in one place, and require the finding to name the
document.

THE NAMES come from the fixture ``fixtures/visual_reference_names.tsv`` (the recorded
licence finding's family, style, version and owner for each build) and THE ONLY USE
comes from ``fixtures/visual_reference_block.txt`` (the notice block as the
documentation owner wrote it and the orchestrator accepted it); this module holds no
family, style, version, owner or item-4 sentence of its own. The counts come from the
committed redraw records, counted here.

THE DOCUMENTS are found by the module's own scan: the tracked non-code text files
outside ``testing/`` (``git ls-files``, minus ``testing/``, minus ``memory/``, minus
``*.py``, keeping the files that decode as UTF-8) that name one of the three standards
or a family of the fixture. The test modules carry those names as patterns and the
fixtures hold them, so ``testing/`` is outside the population; a citation script is not
a product document. ``memory/`` is the vendored orchestration store (cards and an index
written as prose at every commit), not a product document; the number of files
left out under it is printed.
The list must equal exactly the one document of the product; another document found
fails the case and goes back to the architecture owner. ``git ls-files`` that cannot run
ERRORS (-6 never skips: a machine without git is an error, never a skip).

THE NEGATIVE CHECK reads the paragraphs that name the reference (a fixture family or
the owner): each fixture family is removed from a line before "source" is looked for,
because the recorded family names contain the word, and the copyright-holder check
skips only the line that carries the fixture's owner.

Test seam: ``NIFEN_TOOLS_ROOT`` (a git repository holding the documents).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Tuple

import pytest

from .redraw_support import (
    CJK_SOURCES,
    FONT_DIR,
    TOOLS_ROOT,
    NameRow,
    RepositoryError,
    count_after,
    data_lines,
    make_repo,
    printed,
    read_block,
    read_names,
    tracked_files,
)

#: The three national standards, by the names the documents use for them. ``Jōyō`` is
#: written with its two macrons as code points so that the fold of this file cannot
#: change it.
STANDARDS = ("常用漢字", "J\u014dy\u014d", "表外漢字", "通用规范")
FONTLOG = "pixelart_creator/fonts/FONTLOG-CJK.txt"
NAMES = read_names()
FAMILIES = sorted({row.family for row in NAMES}, key=len, reverse=True)


class Finding(NamedTuple):
    """One thing a document gets wrong: which document, what kind, and the detail."""

    path: str
    kind: str
    detail: str


# --- the population: which documents the check reads ---------------------------------


class Population(NamedTuple):
    documents: List[str]  # the documents that list the references
    examined: int  # the tracked non-code text files that were read
    excluded_memory: int = 0  # the tracked non-code files left out under ``memory/``


def find_documents(root: Path) -> Population:
    """The tracked non-code text files outside ``testing/`` and ``memory/`` that list
    the references."""
    patterns = [p.lower() for p in STANDARDS + tuple(FAMILIES)]
    documents: List[str] = []
    examined = 0
    excluded_memory = 0
    for rel in tracked_files(root):
        if rel.startswith("testing/") or rel.lower().endswith(".py"):
            continue
        if rel.startswith("memory/"):
            excluded_memory += 1
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        examined += 1
        if any(p in text.lower() for p in patterns):
            documents.append(rel)
    return Population(documents, examined, excluded_memory)


def population_findings(documents: Sequence[str]) -> List[Finding]:
    """The list of documents must be exactly the one product document."""
    out = []
    for rel in documents:
        if rel != FONTLOG:
            out.append(
                Finding(rel, "population", "another document lists the references")
            )
    if FONTLOG not in documents:
        out.append(Finding(FONTLOG, "population", "the product document is not found"))
    return out


# --- the check ------------------------------------------------------------------------


def redrawn_counts() -> Dict[str, int]:
    """The redrawn lines of the committed records per form set, counted here."""
    counts: Dict[str, int] = {}
    for line in data_lines(CJK_SOURCES / "redraw-records.txt"):
        fields = line.split("\t")
        if fields[4] == "redrawn":
            counts[fields[1]] = counts.get(fields[1], 0) + 1
    return counts


def usage_text(block: str) -> str:
    """The part of the notice block that follows its last count line: the only-use and
    nothing-taken statements, as the fixture words them."""
    lines = block.split("\n")
    last = max(
        i
        for i, line in enumerate(lines)
        for row in NAMES
        if re.fullmatch(r"\s*%s:\s*\d+\s*" % re.escape(row.label), line)
    )
    return "\n".join(lines[last + 1 :]).strip("\n")


def strip_families(line: str) -> str:
    for family in FAMILIES:
        line = re.sub(re.escape(family), " ", line, flags=re.I)
    return line


WORDS = (
    ("source", re.compile(r"\bsources?\b", re.I)),
    ("donor", re.compile(r"\bdonors?\b", re.I)),
    ("licensor", re.compile(r"\blicen[cs]ors?\b", re.I)),
)
HOLDER = re.compile(r"copyright|\u00a9|\(c\)", re.I)


def document_findings(rel: str, text: str, counts: Dict[str, int]) -> List[Finding]:
    """What one document gets wrong, for each requirement of the scenario."""
    out: List[Finding] = []
    lines = text.split("\n")
    for row in NAMES:
        # the names: one line carries the family, the style, the version and the label
        if not any(
            all(x in line for x in (row.family, row.style, row.version, row.label))
            for line in lines
        ):
            out.append(Finding(rel, "names", "%s: no line names the build" % row.label))
        # the owner, as the finding records it
        if row.owner not in text:
            out.append(Finding(rel, "owner", "%s: the owner is absent" % row.label))
        # how many drawings were redrawn with the build
        found = [
            int(m[1])
            for line in lines
            for m in [re.fullmatch(r"\s*%s:\s*(\d+)\s*" % re.escape(row.label), line)]
            if m
        ]
        if found != [counts.get(row.form_set, -1)]:
            out.append(
                Finding(
                    rel,
                    "count",
                    "%s: %s, the records hold %s"
                    % (row.label, found, counts.get(row.form_set)),
                )
            )
    # the only use: the fixture's statements, word for word
    if usage_text(read_block()) not in text:
        out.append(Finding(rel, "usage", "the only-use statements are absent"))
    # the negative check, over the paragraphs that name the reference
    keys = [f.lower() for f in FAMILIES] + [row.owner.lower() for row in NAMES]
    for paragraph in re.split(r"\n\s*\n", text):
        if not any(k in paragraph.lower() for k in keys):
            continue
        for line in paragraph.split("\n"):
            bare = strip_families(line)
            for kind, pattern in WORDS:
                if pattern.search(bare):
                    out.append(Finding(rel, kind, "the reference is named as one"))
            if HOLDER.search(bare) and not any(row.owner in line for row in NAMES):
                out.append(
                    Finding(rel, "copyright-holder", "named as a copyright holder")
                )
    return out


def kinds(found: Sequence[Finding]) -> List[str]:
    return sorted({f.kind for f in found})


@pytest.fixture(scope="module")
def real_text() -> str:
    return (TOOLS_ROOT / FONTLOG).read_bytes().decode("utf-8")


# --- SC-L10N-BUILD-010-6 on the product's documents ---------------------------------


def test_sc_l10n_build_010_6_the_documents_are_the_one_product_document():
    """SC-L10N-BUILD-010-6: the module's own scan of the tracked non-code text files
    finds the documents that list the references; the list is printed, is not empty,
    holds ``FONTLOG-CJK.txt`` and equals exactly {``FONTLOG-CJK.txt``}: another document
    found fails the case."""
    found = find_documents(TOOLS_ROOT)
    assert found.examined > 0
    assert len(found.documents) > 0 and FONTLOG in found.documents, found
    assert population_findings(found.documents) == [], found.documents
    assert found.documents == [FONTLOG]
    printed(
        documents=found.documents,
        text_files_read=found.examined,
        excluded_under_memory=found.excluded_memory,
    )


def test_sc_l10n_build_010_6_the_documents_examined_are_not_zero(real_text):
    """SC-L10N-BUILD-010-6: the number of documents examined is printed and is not
    zero, and each is read whole (it is not empty)."""
    found = find_documents(TOOLS_ROOT)
    assert len(found.documents) > 0
    assert len(real_text) > 0
    printed(documents_examined=len(found.documents))


def test_sc_l10n_build_010_6_every_regional_build_is_named_by_its_recorded_names(
    real_text,
):
    """SC-L10N-BUILD-010-6: for each row of the fixture, one line of the document holds
    the family, the style, the version and the form set's label, and the document holds
    the owner (checked here directly and through the check)."""
    assert len(NAMES) >= 2
    for row in NAMES:
        lines = [
            ln
            for ln in real_text.split("\n")
            if all(x in ln for x in (row.family, row.style, row.version, row.label))
        ]
        assert len(lines) == 1, (row, lines)
        assert row.owner in real_text, row
    assert [
        f
        for f in document_findings(FONTLOG, real_text, redrawn_counts())
        if f.kind in ("names", "owner")
    ] == []


def test_sc_l10n_build_010_6_the_counts_per_regional_build_are_those_of_the_records(
    real_text,
):
    """SC-L10N-BUILD-010-6: the line that carries a build's label and a count states the
    number of ``redrawn`` lines of the committed records for that form set; the counts
    are printed per typeface."""
    counts = redrawn_counts()
    stated = {}
    for row in NAMES:
        value = count_after(real_text, row.label)
        assert value is not None and value > 0, row
        assert value == counts[row.form_set], (row.label, value, counts)
        stated[row.label] = value
    assert sum(counts.values()) == len(data_lines(CJK_SOURCES / "redraw-records.txt"))
    printed(per_typeface=stated)


def test_sc_l10n_build_010_6_the_only_use_is_stated_as_the_fixture_words_it(real_text):
    """SC-L10N-BUILD-010-6: the document states the only use (a visual reference,
    looked at by eye) and that nothing was taken from it, by the statements of the
    fixture; the fixture itself says so, so it cannot drift into saying less."""
    usage = usage_text(read_block())
    flat = " ".join(usage.lower().split())
    for phrase in (
        "only as a visual reference",
        "by eye",
        "no glyph",
        "outline",
        "bitmap",
    ):
        assert phrase in flat, (phrase, flat)
    assert usage in real_text


def test_sc_l10n_build_010_6_the_block_is_in_the_document_exactly_once(real_text):
    """SC-L10N-BUILD-010-6: the notice block of the fixture is in the document as one
    contiguous run, once."""
    block = read_block()
    assert len(block) > 0 and real_text.count(block) == 1


def test_sc_l10n_build_010_6_the_reference_is_not_a_donor_source_holder_licensor(
    real_text,
):
    """SC-L10N-BUILD-010-6: no paragraph that names the reference names it as a donor,
    a source, a copyright holder or a licensor. The recorded family names contain the
    word "source", so the case first shows that the raw text would trip a naive search
    (the family is removed from a line before "source" is looked for)."""
    assert re.search(r"\bsources?\b", real_text, re.I), "the premise of the removal"
    found = document_findings(FONTLOG, real_text, redrawn_counts())
    assert [f for f in found if f.kind in ("source", "donor", "licensor")] == []
    assert [f for f in found if f.kind == "copyright-holder"] == []
    assert found == [], found


# --- the controls: each plant fails and names the document ---------------------------


def plant_in(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1)


def first_row() -> NameRow:
    return NAMES[0]


def test_sc_l10n_build_010_6_control_the_clean_document_passes(real_text):
    """The control of every plant below: the real text yields no finding."""
    assert document_findings(FONTLOG, real_text, redrawn_counts()) == []


def test_sc_l10n_build_010_6_control_one_builds_version_changed_is_a_finding(real_text):
    """A build's version changed in the document, on its own line only (both builds
    carry the same version): its line no longer names the build as the finding records
    it, and the document is named."""
    row = first_row()
    lines = real_text.split("\n")
    line = next(ln for ln in lines if row.label in ln and row.family in ln)
    other = re.sub(r"\d", lambda m: str((int(m[0]) + 1) % 10), row.version, count=1)
    assert other != row.version
    plant = plant_in(real_text, line, line.replace(row.version, other))
    found = document_findings(FONTLOG, plant, redrawn_counts())
    assert "names" in kinds(found), found
    assert {f.path for f in found} == {FONTLOG}


def test_sc_l10n_build_010_6_control_a_label_moved_off_its_builds_line_is_a_finding(
    real_text,
):
    """A form set's label moved off its build's line (here to a line of its own): no
    line carries the family, the style, the version and the label together."""
    row = first_row()
    line = next(
        ln for ln in real_text.split("\n") if row.label in ln and row.family in ln
    )
    moved = line.replace(": " + row.label, "") + "\n" + row.label + " (moved)"
    plant = plant_in(real_text, line, moved)
    found = document_findings(FONTLOG, plant, redrawn_counts())
    assert "names" in kinds(found), found


def test_sc_l10n_build_010_6_control_the_owner_removed_is_a_finding(real_text):
    """The owner removed from the document: the owner is absent and the document is
    named."""
    row = first_row()
    plant = plant_in(real_text, row.owner, "")
    found = document_findings(FONTLOG, plant, redrawn_counts())
    assert "owner" in kinds(found), found
    assert {f.path for f in found} == {FONTLOG}


def test_sc_l10n_build_010_6_control_a_count_that_is_not_the_records_is_a_finding(
    real_text,
):
    """A count changed by one: it no longer equals the redrawn lines of the records."""
    row = first_row()
    stated = count_after(real_text, row.label)
    assert stated is not None
    plant = plant_in(
        real_text, "%s: %d" % (row.label, stated), "%s: %d" % (row.label, stated + 1)
    )
    assert "count" in kinds(document_findings(FONTLOG, plant, redrawn_counts()))


def test_sc_l10n_build_010_6_control_the_only_use_statements_removed_are_a_finding(
    real_text,
):
    """The only-use and nothing-taken statements removed: the document is named."""
    plant = plant_in(real_text, usage_text(read_block()), "")
    found = document_findings(FONTLOG, plant, redrawn_counts())
    assert "usage" in kinds(found), found


@pytest.mark.parametrize(
    "kind,sentence",
    [
        ("source", "%s is the source of the redrawn drawings."),
        ("donor", "%s is the donor of the redrawn drawings."),
        ("licensor", "%s is the licensor of the redrawn drawings."),
        ("copyright-holder", "Copyright (c) 2014 %s."),
    ],
)
def test_sc_l10n_build_010_6_a_document_that_names_the_reference_as_one_is_named(
    real_text, kind, sentence
):
    """SC-L10N-BUILD-010-6: a document planted that names the reference as a source, as
    a donor, as a licensor or as a copyright holder makes the check fail, naming the
    document and the kind; the unplanted text passed first. The plant is the real text
    with one sentence added after the owner line, so nothing else is wrong with it."""
    row = first_row()
    owner_line = next(ln for ln in real_text.split("\n") if row.owner in ln)
    plant = plant_in(real_text, owner_line, owner_line + "\n" + sentence % row.family)
    assert document_findings(FONTLOG, real_text, redrawn_counts()) == []
    found = document_findings(FONTLOG, plant, redrawn_counts())
    assert kind in kinds(found), found
    assert {f.path for f in found} == {FONTLOG}


def test_sc_l10n_build_010_6_the_owner_line_alone_is_skipped_by_the_holder_check(
    real_text,
):
    """The copyright-holder check skips only the line that carries the owner: the owner
    line (which holds the copyright sign) passes, and a second line with the sign in the
    same paragraph, without the owner, is a finding."""
    row = first_row()
    owner_line = next(ln for ln in real_text.split("\n") if row.owner in ln)
    assert HOLDER.search(owner_line)
    assert "copyright-holder" not in kinds(
        document_findings(FONTLOG, real_text, redrawn_counts())
    )
    plant = plant_in(real_text, owner_line, owner_line + "\n\u00a9 2020 Someone")
    assert "copyright-holder" in kinds(
        document_findings(FONTLOG, plant, redrawn_counts())
    )


# --- the population controls, on scratch repositories ---------------------------------


def doc_repo(scratch: Path, name: str, extra: Dict[str, object]) -> Path:
    files: Dict[str, object] = {FONTLOG: (FONT_DIR / "FONTLOG-CJK.txt").read_bytes()}
    files.update(extra)
    return make_repo(scratch / name, files)


def test_sc_l10n_build_010_6_another_document_that_lists_the_references_fails(
    font_scratch,
):
    """SC-L10N-BUILD-010-6: a second tracked text document that names the visual
    reference is found by the scan, and the case fails and names it (it goes back to the
    architecture owner). The repository is a scratch one; its list passes without it."""
    clean = find_documents(doc_repo(font_scratch, "one", {"docs/other.md": "text\n"}))
    assert clean.documents == [FONTLOG]
    assert population_findings(clean.documents) == []
    named = "The glyphs follow %s and the standard %s.\n" % (FAMILIES[0], STANDARDS[0])
    repo = doc_repo(font_scratch, "two", {"docs/credits.md": named})
    found = find_documents(repo)
    assert sorted(found.documents) == sorted([FONTLOG, "docs/credits.md"])
    findings = population_findings(found.documents)
    assert [f.path for f in findings] == ["docs/credits.md"], findings


def test_sc_l10n_build_010_6_the_population_leaves_out_code_testing_and_binary_files(
    font_scratch,
):
    """SC-L10N-BUILD-010-6 (the population): a Python file, a file under ``testing/``,
    a tracked UTF-8 file under ``memory/`` (the vendored store's card, which names a
    fixture family and a standard) and a file that is not UTF-8 all name the reference
    and none is a document; the reference's family in a plain tracked text file is. The
    file under ``memory/`` is counted as left out, and is not read."""
    naming = "Mentions %s and %s.\n" % (FAMILIES[0], STANDARDS[1])
    files: Dict[str, object] = {
        "scripts/citations.py": naming,
        "testing/suites/x/test_names.py": naming,
        "testing/fixture.txt": naming,
        "memory/cards/lesson-visual-reference.md": naming,
        "data/blob.bin": b"\xff\xfe" + naming.encode("utf-8"),
        "docs/page.txt": naming,
    }
    found = find_documents(doc_repo(font_scratch, "mix", files))
    assert sorted(found.documents) == sorted([FONTLOG, "docs/page.txt"]), found
    assert "memory/cards/lesson-visual-reference.md" not in found.documents, found
    assert found.excluded_memory == 1, found
    assert found.examined >= 2


def test_sc_l10n_build_010_6_a_folder_that_is_not_a_repository_errors_never_skips(
    font_scratch, monkeypatch
):
    """SC-L10N-BUILD-010-6: when ``git ls-files`` cannot run the case
    ERRORS naming the folder, and is never skipped."""
    folder = font_scratch / "no-repository"
    folder.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(font_scratch))
    with pytest.raises(RepositoryError, match="no-repository"):
        find_documents(folder)


def test_sc_l10n_build_010_6_the_fixture_rows_hold_every_part_of_a_name():
    """The fixture holds one row per regional build, each with its form set, label,
    family, style, version and owner, and the counts of the records cover each form
    set the fixture names."""
    counts = redrawn_counts()
    sets: Tuple[str, ...] = tuple(row.form_set for row in NAMES)
    assert len(set(sets)) == len(sets) >= 2
    assert all(s in counts and counts[s] > 0 for s in sets), (sets, counts)
