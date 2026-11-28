# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tests of ``scripts/font/check_foreign_fonts.py`` (SC-L10N-BUILD-010-4).

The scenario: given the font sources, the product repository at the head and the font
build's scripts, the foreign-font scan finds no font file other than Nifen Art's own
and no build script that names or opens a reference font file or any other font file
outside Nifen Art's sources; the numbers of files and scripts examined are printed and
are not zero; and a copy of a font planted in the font sources, or a build script
planted that opens one, makes the scan exit non-zero and name the file.

THE POPULATION is the repository at the head, taken from ``git ls-files`` and never from
a walk of the folder (a walk would reach ``.venv`` and every untracked file). The files
are copied into two scratch folders: the tracked files outside ``testing/`` (the
script population, ruled in r67: the test modules, this one among them, name stand-in
font files to plant them, so they are not build scripts) and the tracked files under
``testing/`` (read by content with the rest). The script is run once with both as
``--tree`` roots and the first as ``--scripts`` root; ``--scripts-skip`` is never used.
A scratch root also holds the tracked TOP-LEVEL files, which a root per folder cannot
reach. Plants are written to a third scratch folder passed as one more root, so the
tracked copy is never changed.

The scan is a CLI: each plant asserts the exit code (0 clean, 1 a finding) and that the
named path or stem is printed, never the message sentence. ``git`` that cannot run, or a
folder that is not a repository, ERRORS here: -4 never skips. The typeface
stems the scripts are searched for are read from the script's own constants.

Test seam: ``NIFEN_TOOLS_ROOT``; for these cases it must be a git repository.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, NamedTuple, Optional, Sequence

import pytest

from . import redraw_support as support
from .redraw_support import (
    FOREIGN_FONTS,
    TOOLS_ROOT,
    RepositoryError,
    Run,
    load_tool,
    make_repo,
    printed,
    run_font_tool,
    tracked_files,
)

TOOL = load_tool(FOREIGN_FONTS)
#: The extensions of a script, written here from the script's documentation.
SCRIPT_SUFFIXES = (".py", ".sh", ".bash", ".cmd", ".bat", ".ps1", ".js", ".mjs", ".cjs")
FONT_SUFFIXES = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2")
SAMPLE = TOOLS_ROOT / "pixelart_creator" / "fonts" / "NifenArt-Regular.ttf"
PLANT_IN_SOURCES = "fonts-src/nifen-art-cjk/NifenArtCJKJP-Regular.ttf"
FIGURES = {
    "files": re.compile(r"^files examined by content: (\d+)$", re.M),
    "fonts": re.compile(
        r"^font files found: (\d+) \(Nifen Art's own (\d+), refused (\d+)\)$", re.M
    ),
    "scripts": re.compile(r"^scripts examined: (\d+)$", re.M),
    "hits": re.compile(r"^script hits: (\d+)$", re.M),
}


class Head(NamedTuple):
    """The repository at the head, copied by ``git ls-files`` into two scratch roots."""

    tracked: List[str]
    code: Path
    tests: Path
    absent: List[str]

    @property
    def exported(self) -> int:
        return len(self.tracked) - len(self.absent)


def is_under_testing(rel: str) -> bool:
    return rel.startswith("testing/")


def export_head(root: Path, scratch: Path) -> Head:
    """Copy the tracked files of ``root`` into ``scratch/code`` (outside ``testing/``)
    and ``scratch/tests`` (under ``testing/``). A tracked file that is not on disk is
    listed, never silently dropped."""
    names = tracked_files(root)
    code, tests = scratch / "code", scratch / "tests"
    code.mkdir(parents=True)
    tests.mkdir(parents=True)
    absent: List[str] = []
    for rel in names:
        source = root / rel
        if not source.is_file():
            absent.append(rel)
            continue
        target = (tests if is_under_testing(rel) else code) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return Head(names, code, tests, absent)


def scan(scratch: Path, head: Head, plant: Optional[Path] = None) -> Run:
    """The scan of the head: both exports by content, the code export for scripts."""
    args: List[object] = ["--tree", head.code, "--tree", head.tests]
    args += ["--scripts", head.code]
    if plant is not None:
        args += ["--tree", plant, "--scripts", plant]
    return run_font_tool(FOREIGN_FONTS, args, scratch)


def figures(res: Run) -> dict:
    """The numbers the scan printed: files, font files, scripts and hits."""
    out = {}
    for name, pattern in FIGURES.items():
        found = pattern.search(res.stdout)
        assert found, (name, res.stdout)
        out[name] = tuple(int(g) for g in found.groups())
    return out


def renamed_family(data: bytes) -> bytes:
    """A copy of a product font with its family name altered, as a foreign font."""
    prefix = TOOL.OWN_FAMILY_PREFIX
    out = data.replace(prefix.encode("utf-16-be"), "Nofen Art".encode("utf-16-be"))
    out = out.replace(prefix.encode("latin-1"), b"Nofen Art")
    assert out != data and len(out) == len(data)
    return out


def write(folder: Path, rel: str, content: object) -> None:
    target = folder / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        content if isinstance(content, bytes) else str(content).encode("utf-8")
    )


@pytest.fixture(scope="module")
def head(font_scratch_shared: Path) -> Head:
    """The repository at the head, exported once and only ever read."""
    return export_head(TOOLS_ROOT, font_scratch_shared / "head")


@pytest.fixture(scope="module")
def head_scan(font_scratch_shared: Path, head: Head) -> Run:
    """The clean scan of the head: every plant below is read against it."""
    return scan(font_scratch_shared, head)


# --- SC-L10N-BUILD-010-4: the repository at the head ----------------------------------


def test_sc_l10n_build_010_4_the_repository_at_the_head_holds_no_foreign_font(
    head, head_scan
):
    """SC-L10N-BUILD-010-4: over the tracked files at the head (``git ls-files``) the
    scan exits 0; the files and scripts examined are not zero and equal the ones this
    module counts from the list; every font file found is Nifen Art's own and none is
    refused."""
    assert head_scan.returncode == 0, head_scan.text
    nums = figures(head_scan)
    scripts = [
        r
        for r in head.tracked
        if not is_under_testing(r) and r.lower().endswith(SCRIPT_SUFFIXES)
    ]
    ttf = [r for r in head.tracked if r.lower().endswith(FONT_SUFFIXES)]
    assert nums["files"][0] == head.exported > 0
    assert nums["scripts"][0] == len(scripts) > 0
    found, allowed, refused = nums["fonts"]
    assert found >= len(ttf) > 0 and allowed == found and refused == 0
    assert nums["hits"][0] == 0
    printed(
        tracked=len(head.tracked),
        absent=len(head.absent),
        files_examined=nums["files"][0],
        font_files=found,
        scripts_examined=nums["scripts"][0],
    )


def test_sc_l10n_build_010_4_the_tracked_top_level_files_are_in_the_population(head):
    """SC-L10N-BUILD-010-4: the tracked files at the top of the repository, which a
    root per folder cannot reach, are in the scanned root, each one."""
    top = [r for r in head.tracked if "/" not in r]
    assert len(top) > 0
    missing = [r for r in top if r not in head.absent and not (head.code / r).is_file()]
    assert missing == []
    printed(top_level=len(top))


def test_sc_l10n_build_010_4_a_font_planted_in_the_font_sources_is_named(
    font_scratch, head, head_scan
):
    """SC-L10N-BUILD-010-4: a copy of a product font whose family is not Nifen Art's,
    planted in the font sources under a Nifen Art file name, makes the scan exit 1 and
    name the file. The clean scan of the head passed first."""
    assert head_scan.returncode == 0, head_scan.text
    plant = font_scratch / "plant"
    write(plant, PLANT_IN_SOURCES, renamed_family(SAMPLE.read_bytes()))
    res = scan(font_scratch, head, plant)
    assert res.returncode == 1, res.text
    assert PLANT_IN_SOURCES in res.stdout, res.stdout
    assert figures(res)["fonts"][2] == 1


@pytest.mark.parametrize(
    "rel",
    ["fonts-src/nifen-art-cjk/notes.txt", "data.bin", "docs/picture.png"],
    ids=["a-text-name", "top-level", "an-image-name"],
)
def test_sc_l10n_build_010_4_a_font_under_another_name_is_found_by_content(
    font_scratch, head, head_scan, rel
):
    """SC-L10N-BUILD-010-4: a font is recognised by its content, never by its name: a
    product font copied under a text name, an image name, or at the top of the
    repository exits 1 and is named."""
    assert head_scan.returncode == 0, head_scan.text
    plant = font_scratch / "plant"
    write(plant, rel, SAMPLE.read_bytes())
    res = scan(font_scratch, head, plant)
    assert res.returncode == 1, res.text
    assert rel in res.stdout, res.stdout


def test_sc_l10n_build_010_4_a_build_script_planted_that_opens_a_font_is_named(
    font_scratch, head, head_scan
):
    """SC-L10N-BUILD-010-4: a build script planted that opens a font file that is not
    Nifen Art's exits 1 and is named with its line."""
    assert head_scan.returncode == 0, head_scan.text
    plant = font_scratch / "plant"
    rel = "scripts/font/planted_build.py"
    stand_in = "Sample" + "Face"
    write(plant, rel, "data = open('" + stand_in + ".ttf', 'rb').read()\n")
    res = scan(font_scratch, head, plant)
    assert res.returncode == 1, res.text
    assert rel + ":1" in res.stdout and stand_in in res.stdout, res.stdout
    assert figures(res)["hits"][0] >= 1


@pytest.mark.parametrize(
    "stem",
    TOOL.REFERENCE_STEMS,
    ids=lambda s: "stem-%d" % TOOL.REFERENCE_STEMS.index(s),
)
def test_sc_l10n_build_010_4_a_script_that_names_a_reference_font_file_is_named(
    font_scratch, head, head_scan, stem
):
    """SC-L10N-BUILD-010-4: a script planted that names a reference font file, one case
    per stem the script searches for (the two earlier typefaces' files, the two
    builds of the visual reference, the folder of reference images), exits 1 and is
    named with the stem."""
    assert head_scan.returncode == 0, head_scan.text
    plant = font_scratch / "plant"
    rel = "scripts/font/planted_build.py"
    write(plant, rel, "# reads " + stem + "\n")
    res = scan(font_scratch, head, plant)
    assert res.returncode == 1, res.text
    assert rel + ":1" in res.stdout and stem in res.stdout, res.stdout


def test_sc_l10n_build_010_4_the_font_tools_are_in_the_script_population_and_clean(
    head, head_scan
):
    """SC-L10N-BUILD-010-4: the scanner and the other tools of ``scripts/font`` are in
    the script population and do not trip the scan they implement (they write the
    names they search for in pieces): the scripts examined include them, 0 hits."""
    own = [
        r for r in head.tracked if r.startswith("scripts/font/") and r.endswith(".py")
    ]
    assert "scripts/font/check_foreign_fonts.py" in own
    nums = figures(head_scan)
    assert head_scan.returncode == 0 and nums["hits"] == (0,)
    assert nums["scripts"][0] >= len(own)


# --- the population is the TRACKED files; scripts are those outside testing/ ---------


def repo_with(scratch: Path, name: str, files: dict) -> Head:
    repo = make_repo(scratch / name, files)
    return export_head(repo, scratch / (name + "-export"))


CLEAN_FILES = {
    "README.txt": "text\n",
    "scripts/build.py": "print('a build that opens NifenArt-Regular.ttf')\n",
}


def test_sc_l10n_build_010_4_the_population_is_the_tracked_files_not_the_folder(
    font_scratch,
):
    """SC-L10N-BUILD-010-4: a foreign font that sits in the working folder but is not
    tracked is outside the population (exit 0); the same file tracked is a finding
    (exit 1, named). The repository is a scratch one built here."""
    foreign = renamed_family(SAMPLE.read_bytes())
    repo = make_repo(font_scratch / "repo", CLEAN_FILES)
    write(repo, "fonts-src/untracked.bin", foreign)  # never added to the index
    head = export_head(repo, font_scratch / "export-1")
    assert head.tracked == sorted(CLEAN_FILES), head.tracked
    res = scan(font_scratch, head)
    assert res.returncode == 0, res.text
    tracked = make_repo(
        font_scratch / "repo-2", {**CLEAN_FILES, "fonts-src/x.bin": foreign}
    )
    res = scan(font_scratch, export_head(tracked, font_scratch / "export-2"))
    assert res.returncode == 1, res.text
    assert "fonts-src/x.bin" in res.stdout


def test_sc_l10n_build_010_4_a_script_under_testing_is_outside_the_script_population(
    font_scratch,
):
    """SC-L10N-BUILD-010-4 (r67): the script population is the tracked scripts outside
    ``testing/``, because the test modules name stand-in fonts to plant them. The same
    script that exits 1 under ``scripts/`` exits 0 under ``testing/``, and a font file
    planted under ``testing/`` is still refused (the file half covers the whole
    repository)."""
    stand_in = "Sample" + "Face"
    script = "x = open('" + stand_in + ".ttf', 'rb')\n"
    outside = make_repo(font_scratch / "a", {**CLEAN_FILES, "scripts/bad.py": script})
    res = scan(font_scratch, export_head(outside, font_scratch / "ea"))
    assert res.returncode == 1 and "scripts/bad.py" in res.stdout, res.text
    inside = make_repo(
        font_scratch / "b", {**CLEAN_FILES, "testing/suites/x/test_bad.py": script}
    )
    res = scan(font_scratch, export_head(inside, font_scratch / "eb"))
    assert res.returncode == 0, res.text
    font = renamed_family(SAMPLE.read_bytes())
    planted = make_repo(font_scratch / "c", {**CLEAN_FILES, "testing/data.bin": font})
    res = scan(font_scratch, export_head(planted, font_scratch / "ec"))
    assert res.returncode == 1 and "testing/data.bin" in res.stdout, res.text


def test_sc_l10n_build_010_4_a_population_with_no_script_is_not_a_pass(font_scratch):
    """SC-L10N-BUILD-010-4: the numbers examined must not be zero. A repository whose
    tracked files hold no script outside ``testing/`` exits 1 with 0 scripts examined,
    and one that holds none at all cannot be exported."""
    head = repo_with(font_scratch, "no-script", {"README.txt": "text\n"})
    res = scan(font_scratch, head)
    assert res.returncode == 1, res.text
    assert figures(res)["scripts"] == (0,)


def test_sc_l10n_build_010_4_a_folder_that_is_not_a_repository_errors_never_skips(
    font_scratch,
):
    """SC-L10N-BUILD-010-4: when ``git ls-files`` cannot run the case
    ERRORS with a message that names the folder, and is never skipped. A folder that
    is not inside a repository, and a git that cannot start, are both an error."""
    folder = font_scratch / "no-repository"
    folder.mkdir()
    ceiling = {"GIT_CEILING_DIRECTORIES": str(font_scratch)}
    with pytest.raises(RepositoryError, match="no-repository"):
        tracked_files(folder, env=ceiling)
    empty = font_scratch / "empty-repository"
    empty.mkdir()
    subprocess.run(["git", "-C", str(empty), "init", "-q"], check=True)
    with pytest.raises(RepositoryError, match="listed no file"):
        tracked_files(empty, env=ceiling)


def test_sc_l10n_build_010_4_a_git_that_cannot_start_errors_never_skips(
    font_scratch, monkeypatch
):
    """SC-L10N-BUILD-010-4: a machine without git is an error of the case,
    not a skip."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(support.subprocess, "run", refuse)
    with pytest.raises(RepositoryError, match="could not run"):
        tracked_files(font_scratch)


def test_sc_l10n_build_010_4_the_scan_needs_both_kinds_of_root(font_scratch, head):
    """SC-L10N-BUILD-010-4 (usage): a run that names no script root, or no tree root,
    is refused with exit 2 and examines nothing."""
    only_tree = run_font_tool(FOREIGN_FONTS, ["--tree", head.code], font_scratch)
    only_scripts = run_font_tool(FOREIGN_FONTS, ["--scripts", head.code], font_scratch)
    assert only_tree.returncode == 2, only_tree.text
    assert only_scripts.returncode == 2, only_scripts.text


def test_sc_l10n_build_010_4_the_tools_own_controls_are_all_killed(font_scratch):
    """SC-L10N-BUILD-010-4: the script's ``--controls`` (planted fonts of other formats,
    a renamed family, scripts that open or name a font) all stand, exit 0, with at
    least one control run and none left unkilled."""
    res = run_font_tool(
        FOREIGN_FONTS, ["--controls", "--sample-font", SAMPLE], font_scratch
    )
    assert res.returncode == 0, res.text
    found = re.search(
        r"^controls: (\d+) run, (\d+) killed, (\d+) not killed$", res.stdout, re.M
    )
    assert found and int(found[1]) > 0 and int(found[3]) == 0, res.stdout
    assert tuple(int(g) for g in found.groups())[0] == int(found[2]) + int(found[3])


def test_sc_l10n_build_010_4_the_two_exports_keep_testing_apart(head: Head):
    """SC-L10N-BUILD-010-4: the export holds the tracked files outside ``testing/`` in
    one root (the script population) and those under ``testing/`` in the other (read
    by content only): neither list is empty and no file is in both."""
    in_code = [r for r in head.tracked if not is_under_testing(r)]
    in_tests = [r for r in head.tracked if is_under_testing(r)]
    assert len(in_code) > 0 and len(in_tests) > 0
    sample: Sequence[str] = [r for r in in_tests if r not in head.absent][:3]
    assert all((head.tests / r).is_file() for r in sample)
    assert not any((head.code / r).exists() for r in sample)
