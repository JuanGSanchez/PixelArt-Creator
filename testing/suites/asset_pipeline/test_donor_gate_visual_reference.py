# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The donor gate and the visual reference (SC-L10N-BUILD-002-1 and -3).

Both scenarios belong to REQ-L10N-BUILD-002. The lines under test were added when
REQ-L10N-BUILD-010 chose a typeface as a visual reference:

* SC-L10N-BUILD-002-1: *no typeface named as a visual reference under
  REQ-L10N-BUILD-010 is counted as a donor*. The font build's lint prints one donor (Ark
  Pixel Font) and the 89 donor-derived code points whatever the sources and the licence
  files say about the reference.
* SC-L10N-BUILD-002-3: *given a glyph whose record names the visual reference as its
  visual reference and no font as its source, the lint does not refuse it for that*,
  and *given a glyph whose record names the visual reference as its source, the lint
  exits non-zero, naming the glyph and the font*.

The cases run on the same SCRATCH WORLD as ``test_build_nifen_art.py`` section 12 (its
helpers are imported, so its test seam applies): a copy of the existing face's sources,
a CJK source folder written here, the licence files, ``NOTICE`` and six CJK fonts built
by the real ``--build`` from the scratch records. The real CJK sources are never read.

The world is laid out as ``<root>/fonts-src/nifen-art-cjk`` so that the redraw-record
check and the lint read the SAME files. The visual reference is named in
``redraw-records.txt`` (a glyph record names only ``src=drawn``): the record check
accepts that file and the lint does not refuse the glyphs for it, and the donor gate
reads that file and the real ``FONTLOG-CJK.txt``, which names the reference's family
and owner, without counting either as a donor.

The typeface tokens come from the record check's own constants, and the family, owner
and notice block from the fixtures; this module holds none of them. Each plant is
paired with the clean world, which passes first. Exit codes are asserted exactly (0
clean, 1 a finding).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import List, NamedTuple

import pytest

from . import test_build_nifen_art as nb
from .redraw_support import (
    REDRAW_RECORDS,
    NameRow,
    load_tool,
    printed,
    read_block,
    read_names,
    run_font_tool,
    sha256_hex,
)

RECORDS_TOOL = load_tool(REDRAW_RECORDS)
REF = RECORDS_TOOL.REFERENCES
NAMES = read_names()
DONOR_LINE = "donors declared: 1 (Ark Pixel Font)"
DERIVED_LINE = "donor-derived code points: 89"
FONTLOG_CJK = "FONTLOG-CJK.txt"
REDRAW_FILE = "redraw-records.txt"
OLD_SHA = "0" * 64


class VrWorld(NamedTuple):
    """A scratch world and the root of its CJK folder (``fonts-src/nifen-art-cjk``)."""

    world: nb.World
    root: Path


def glyph_sha(head: str, drawing: str) -> str:
    """The sha256 of a glyph record: its header line and its rows, each with a LF."""
    rows = [ln for ln in drawing.split("\n") if ln]
    return sha256_hex(("\n".join([head] + rows) + "\n").encode("utf-8"))


def redraw_records() -> str:
    """Two redraw records of the world's own glyphs, each naming its own form set's
    build as the visual reference: one with a disagreement, one without."""
    place = "joyo-2010 page=1 pos=1"  # the world's one citation record, U+65E5
    jp = [
        "U+65E5",
        "jp",
        "b2",
        "doubtful",
        "redrawn",
        REF["jp"],
        place,
        "weak in one half",
        OLD_SHA,
        glyph_sha(nb.JP_HEAD.strip(), nb.TEE_DRAWING),
        "2026-11-19",
    ]
    sc = [
        "U+7B80",
        "sc",
        "b3",
        "weakest",
        "redrawn",
        REF["sc"],
        "-",
        "doubtful",
        OLD_SHA,
        glyph_sha(nb.SC_HEAD.strip(), nb.PLUS_DRAWING),
        "2026-11-19",
    ]
    return "# fixture\n" + "\n".join("\t".join(r) for r in (jp, sc)) + "\n"


@pytest.fixture(scope="module")
def vr_fonts(font_scratch_shared: Path) -> Path:
    """The six CJK fonts, built once by the real ``--build`` from the scratch records,
    with the licence files they are linted against."""
    folder = font_scratch_shared / "vr-fonts"
    cjk, fonts = folder / "cjk", folder / "fonts"
    nb.write_cjk_sources(cjk)
    fonts.mkdir(parents=True)
    for name in nb.LICENCE_FILES:
        shutil.copy(nb.FONT_DIR / name, fonts / name)
    shutil.copy(nb.TOOLS_ROOT / "NOTICE", folder / "NOTICE")
    args = ["--build", "--face", "nifen-art-cjk", "--cjk-src", cjk, "--out", fonts]
    args += ["--licence-dir", fonts, "--notice", folder / "NOTICE"]
    res = nb.run_font(nb.BUILD, args, folder)
    assert res.returncode == 0, res.text
    assert len(list(fonts.glob("*.ttf"))) == 6
    return fonts


@pytest.fixture
def vr(font_scratch: Path, vr_fonts: Path) -> VrWorld:
    """A scratch world that holds the redraw records beside its glyph records."""
    root = font_scratch / "vr-root"
    cjk = root / "fonts-src" / "nifen-art-cjk"
    nb.write_cjk_sources(cjk)
    (cjk / REDRAW_FILE).write_bytes(redraw_records().encode("utf-8"))
    src = font_scratch / "world-src"
    shutil.copytree(nb.SOURCES, src)
    fonts = font_scratch / "world-fonts"
    shutil.copytree(vr_fonts, fonts)
    for name in nb.FONT_FILES.values():
        shutil.copy(nb.FONT_DIR / name, fonts / name)
    notice = font_scratch / "NOTICE"
    shutil.copy(nb.TOOLS_ROOT / "NOTICE", notice)
    assert all(n > 0 for n in nb.record_counts(cjk).values())
    return VrWorld(nb.World(src, cjk, fonts, notice, font_scratch), root)


def lint_clean(v: VrWorld) -> nb.Run:
    """The control: the unplanted world passes the CJK lint, over counted records."""
    return nb.clean_lint(v.world)


def violation_naming(res: nb.Run, *tokens: str) -> List[str]:
    """The violation lines that hold every token."""
    return [ln for ln in nb.violations_of(res) if all(t in ln for t in tokens)]


def holder_of(row: NameRow) -> str:
    """The holder in the fixture's owner text: what follows the years."""
    found = re.match(r"^\D*\d{4}(?:\s*-\s*\d{4})?\s*(.+)$", row.owner)
    assert found, row.owner
    return re.split(r"\s*[(;]", found[1])[0].strip()


# --- SC-L10N-BUILD-002-1: the visual reference is not counted as a donor -----------


def test_sc_l10n_build_002_1_the_world_names_the_reference_and_lints_clean(vr):
    """The foundation of the cases below: the scratch world HOLDS the reference's names
    in files the donor gate scans (``FONTLOG-CJK.txt`` carries the notice block of the
    fixture, with every family and owner; the redraw records carry both builds), the
    gate lists both files as examined, and the world lints clean."""
    fontlog = (vr.world.fonts / FONTLOG_CJK).read_bytes().decode("utf-8")
    assert read_block() in fontlog
    for row in NAMES:
        assert row.family in fontlog and row.owner in fontlog, row
    records = (vr.world.cjk / REDRAW_FILE).read_bytes().decode("utf-8")
    assert REF["jp"] in records and REF["sc"] in records
    res = lint_clean(vr)
    assert nb.lint_lines(res, "fonts-src/nifen-art-cjk/%s: examined" % REDRAW_FILE)
    assert nb.lint_lines(res, "pixelart_creator/fonts/%s: examined" % FONTLOG_CJK)


def test_sc_l10n_build_002_1_no_typeface_named_as_a_visual_reference_is_a_donor(vr):
    """SC-L10N-BUILD-002-1: with the visual reference named in the sources and in the
    licence files, the lint prints exactly one donor, Ark Pixel Font, and the 89
    donor-derived code points; none of the reference's families or its owner is among
    the donors declared."""
    res = lint_clean(vr)
    assert nb.lint_lines(res, DONOR_LINE), res.stdout
    assert nb.lint_lines(res, DERIVED_LINE + " "), res.stdout
    declared = nb.lint_lines(res, "donors declared:")
    assert len(declared) == 1, declared
    for row in NAMES:
        assert row.family not in declared[0] and holder_of(row) not in declared[0]
    printed(donors=declared[0], references=len(NAMES))


def test_sc_l10n_build_002_1_control_the_reference_credited_as_a_source_is_refused(vr):
    """Control: the same world with one sentence added to ``FONTLOG-CJK.txt`` that
    credits the reference as the source of drawings is refused by the gate (exit 1,
    the file and the family named), so the world above passes because nothing credits
    the reference, not because the gate is blind to it."""
    lint_clean(vr)
    row = NAMES[0]
    nb.edit_once(
        vr.world.fonts / FONTLOG_CJK,
        nb.FONTLOG_ANCHOR,
        "The strokes are adapted from %s.\n\n" % row.family + nb.FONTLOG_ANCHOR,
    )
    res = nb.cjk_lint(vr.world)
    assert res.returncode == 1, res.text
    assert violation_naming(res, FONTLOG_CJK, row.family), res.stdout


def test_sc_l10n_build_002_1_control_the_references_owner_as_holder_is_a_second_donor(
    vr,
):
    """Control: a copyright line crediting the reference's owner in ``FONTLOG-CJK.txt``
    is refused as a second holder, and the printed donor count is no longer 1. So the
    count of 1 above is a reading of the files, and the reference is counted only when
    it is credited."""
    lint_clean(vr)
    holder = holder_of(NAMES[0])
    nb.edit_once(
        vr.world.fonts / FONTLOG_CJK,
        nb.FONTLOG_ANCHOR,
        nb.FONTLOG_ANCHOR + "\nCopyright (c) 2014, %s.\n" % holder,
    )
    res = nb.cjk_lint(vr.world)
    assert res.returncode == 1, res.text
    assert violation_naming(res, FONTLOG_CJK, holder), res.stdout
    assert not nb.lint_lines(res, DONOR_LINE), res.stdout
    assert nb.lint_lines(res, "donors declared: 2"), res.stdout


def test_sc_l10n_build_002_1_control_the_reference_declared_as_a_donor_is_refused(vr):
    """Control: the reference's family declared as a second donor in the metadata is
    refused (exit 1, the declaring key named)."""
    lint_clean(vr)
    nb.append_to(vr.world.src / "metrics.txt", "donor_name_2 = %s\n" % NAMES[0].family)
    res = nb.cjk_lint(vr.world)
    assert res.returncode == 1, res.text
    assert violation_naming(res, "donor_name_2"), res.stdout


# --- SC-L10N-BUILD-002-3: a glyph whose record names the reference -----------------


def test_sc_l10n_build_002_3_a_glyph_naming_the_reference_as_visual_reference_passes(
    vr, font_scratch
):
    """SC-L10N-BUILD-002-3, first line: the glyphs' records name no font as their source
    (``src=drawn``), and the redraw records name the visual reference as the one looked
    at. The redraw-record check accepts them and the lint does not refuse the glyphs for
    that: exit 0, over a provenance rule (R16) that examined glyphs and found none."""
    assert "src=drawn" in nb.JP_HEAD and "src=drawn" in nb.SC_HEAD
    check = run_font_tool(REDRAW_RECORDS, ["--root", vr.root], font_scratch)
    assert check.returncode == 0, check.text
    assert "redraw records examined: 2" in check.stdout.split("\n")
    res = lint_clean(vr)
    examined, violations = nb.lint_rules(res.stdout)["R16"]
    assert examined > 0 and violations == 0, res.stdout
    printed(r16_examined=examined, record_lines_checked=2)


@pytest.mark.parametrize(
    "form,head,how",
    [
        ("sc", nb.SC_HEAD, "src=copied:{ref}"),
        ("sc", nb.SC_HEAD, "src=traced:{ref}"),
        ("sc", nb.SC_HEAD, "src=drawn copied-from={ref}"),
        ("sc", nb.SC_HEAD, "src=drawn source={ref}"),
        ("jp", nb.JP_HEAD, "src=copied:{ref}"),
    ],
    ids=[
        "sc-copied",
        "sc-traced",
        "sc-copied-from",
        "sc-source-attribute",
        "jp-copied",
    ],
)
def test_sc_l10n_build_002_3_a_glyph_naming_the_reference_as_its_source_is_refused(
    vr, form, head, how
):
    """SC-L10N-BUILD-002-3, second line: a glyph whose record names the visual
    reference as its source, as the value of ``src=`` or as an attribute, makes the
    lint exit 1 and name the glyph and the font. The unplanted world passed first."""
    lint_clean(vr)
    token = REF[form]
    planted = head.replace("src=drawn", how.format(ref=token))
    assert planted != head
    nb.edit_once(vr.world.cjk / nb.CJK_RECORD_FILES[form], head, planted)
    res = nb.cjk_lint(vr.world)
    assert res.returncode == 1, res.text
    cp = head.split()[1]
    assert violation_naming(res, "%s set=%s" % (cp, form), token), res.stdout


def test_sc_l10n_build_002_3_a_build_from_a_glyph_naming_the_reference_as_source_stops(
    vr,
):
    """SC-L10N-BUILD-002-3: ``--build`` over a glyph that names the reference as its
    source is refused and writes no font, as for any font named as a source."""
    token = REF["sc"]
    nb.edit_once(
        vr.world.cjk / "han-sc.txt",
        nb.SC_HEAD,
        nb.SC_HEAD.replace("src=drawn", "src=copied:" + token),
    )
    out = vr.world.scratch / "never-built"
    res = nb.cjk_build(vr.world, out)
    assert res.returncode == 1, res.text
    assert not out.exists() or not list(out.glob("*.ttf"))


def test_sc_l10n_build_002_3_the_clean_world_with_no_reference_record_also_passes(vr):
    """Control of the first line: the same world WITHOUT the redraw records passes too,
    so the reference's presence in the records changes nothing for the gate or R16."""
    with_records = lint_clean(vr)
    (vr.world.cjk / REDRAW_FILE).unlink()
    without = nb.clean_lint(vr.world)
    assert (
        nb.lint_rules(with_records.stdout)["R16"]
        == nb.lint_rules(without.stdout)["R16"]
    )
    assert nb.lint_lines(without, DONOR_LINE)
