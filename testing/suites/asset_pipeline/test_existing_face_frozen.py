# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The existing Nifen Art face stays as the v0.4.0 merge left it (SC-L10N-BUILD-001-4).

The subject is ``build_nifen_art.py --verify-freeze``: it compares every file of the
existing face (the 26 glyph sources under ``fonts-src/nifen-art``, the two built fonts,
``FONTLOG.txt`` and ``OFL.txt``) with ``fonts-src/nifen-art-cjk/existing-face.sha256``,
refuses a listed file that is missing, a file that differs and a file the manifest does
not list, and prints ``freeze check: N files compared, V violations``.

Independence of the numbers: the manifest is parsed here, each file is hashed here with
``hashlib``, the set of files the manifest must cover is walked here, and the Han and
Hangul ranges are written out here from the Unicode block assignments. None of these
is read from the script under test or from ``pixelart_creator/logic/constants.py``.

Every glyph-free case works on a SCRATCH ROOT built under ``tmp_path`` from copies of
the committed files; the committed files are only ever read, and a module-level guard
hashes them before and after.

Test seam: ``NIFEN_TOOLS_ROOT`` points the module at a COPY of the layout, like
``test_build_nifen_art.py``, so a case can be shown to fail against a broken copy of the
script.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, NamedTuple, Tuple

import pytest

from .conftest import REPO_ROOT

TOOLS_ROOT = Path(os.environ.get("NIFEN_TOOLS_ROOT") or REPO_ROOT).resolve()
BUILD = TOOLS_ROOT / "scripts" / "font" / "build_nifen_art.py"
MANIFEST_REL = "fonts-src/nifen-art-cjk/existing-face.sha256"
MANIFEST = TOOLS_ROOT / Path(*MANIFEST_REL.split("/"))
FACE_SRC_REL = "fonts-src/nifen-art"
FONTS_REL = "pixelart_creator/fonts"
FACE_FONT_FILES = (
    "NifenArt-Bold.ttf",
    "NifenArt-Regular.ttf",
    "FONTLOG.txt",
    "OFL.txt",
)

#: The size of the frozen face, pinned on purpose. The manifest is "written once and
#: never regenerated to agree with a changed face", so a manifest that lists fewer
#: files is a weaker freeze, not a tidier one. 26 sources + 2 fonts + 2 text files.
FROZEN_FILE_COUNT = 30

#: Han and Hangul as the Unicode block assignments give them (Blocks.txt): CJK Extension
#: A, CJK Unified Ideographs, CJK Compatibility Ideographs, Extensions B to H; Hangul
#: Syllables. Written out here so the case does not read the product's own constants.
HAN_BLOCKS = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x323AF))
HANGUL_BLOCKS = ((0xAC00, 0xD7A3),)

FREEZE_LINE = re.compile(
    r"^freeze check: (\d+) files compared, (\d+) violations$", re.M
)
INFO_LINE = re.compile(
    r"^existing face frozen: (\d+) files compared, (\d+) identical, "
    r"(\d+) missing or changed, (\d+) not listed$",
    re.M,
)


class Run(NamedTuple):
    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout + self.stderr


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_entries() -> List[Tuple[str, str]]:
    """``(relative path, sha256)`` of each non-comment manifest line."""
    entries: List[Tuple[str, str]] = []
    for line in MANIFEST.read_bytes().decode("utf-8").split("\n"):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        digest, sep, rel = line.partition("  ")
        assert sep and re.fullmatch(r"[0-9a-f]{64}", digest), line
        entries.append((rel, digest))
    return entries


def the_face_files() -> List[str]:
    """Every file the freeze must cover, walked from the tree, not the manifest."""
    base = TOOLS_ROOT / "fonts-src" / "nifen-art"
    found = sorted(
        "%s/%s" % (FACE_SRC_REL, p.relative_to(base).as_posix())
        for p in base.rglob("*")
        if p.is_file()
    )
    return found + sorted("%s/%s" % (FONTS_REL, name) for name in FACE_FONT_FILES)


def run_freeze(root: Path, cjk_src: Path, tmp: Path) -> Run:
    """``--verify-freeze`` as a real subprocess on a given root and manifest folder."""
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(BUILD),
            "--verify-freeze",
            "--root",
            str(root),
            "--cjk-src",
            str(cjk_src),
        ],
        cwd=str(TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=dict(
            os.environ,
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONIOENCODING="utf-8",
            TMP=str(tmp),
            TEMP=str(tmp),
            TMPDIR=str(tmp),
        ),
    )
    return Run(done.returncode, done.stdout, done.stderr)


def freeze_numbers(res: Run) -> Tuple[int, int]:
    """``(files compared, violations)`` from the closing line, which must be there."""
    found = FREEZE_LINE.search(res.stdout)
    assert found, "no 'freeze check: N files compared, V violations' line:\n" + res.text
    return int(found[1]), int(found[2])


@pytest.fixture(scope="module", autouse=True)
def _the_frozen_files_are_never_touched():
    """No case of this module changes a file of the existing face or its manifest."""
    watched = [TOOLS_ROOT / Path(*rel.split("/")) for rel in the_face_files()]
    watched.append(MANIFEST)
    before = {str(p): _sha(p) for p in watched}
    assert len(before) == FROZEN_FILE_COUNT + 1
    yield
    after = {str(p): _sha(p) for p in watched}
    assert before == after, "a frozen file was touched by the tests"


class Root(NamedTuple):
    root: Path
    cjk: Path
    manifest: Path
    tmp: Path

    def path(self, rel: str) -> Path:
        return self.root / Path(*rel.split("/"))


@pytest.fixture
def scratch_root(tmp_path):
    """A scratch repository root holding COPIES of the 30 files and of the manifest."""
    root = tmp_path / "root"
    for rel in the_face_files():
        dst = root / Path(*rel.split("/"))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TOOLS_ROOT / Path(*rel.split("/")), dst)
    cjk = root / "fonts-src" / "nifen-art-cjk"
    cjk.mkdir(parents=True)
    shutil.copy(MANIFEST, cjk / "existing-face.sha256")
    proc_tmp = tmp_path / "proc-tmp"
    proc_tmp.mkdir()
    return Root(root, cjk, cjk / "existing-face.sha256", proc_tmp)


def verify(world: Root) -> Run:
    return run_freeze(world.root, world.cjk, world.tmp)


# --------------------------------------------------------------------------
# The manifest, read independently of the script
# --------------------------------------------------------------------------


def test_sc_l10n_build_001_4_the_manifest_lists_30_files_and_the_tree_matches_it():
    """SC-L10N-BUILD-001-4: the manifest names 30 files, they are the files of the
    face (walked from the tree, not from the manifest), each exists, and each hashes
    to the digest the manifest holds."""
    entries = manifest_entries()
    paths = [rel for rel, _digest in entries]
    assert len(entries) == FROZEN_FILE_COUNT, len(entries)
    assert len(set(paths)) == len(paths), "a file is listed twice"
    assert sorted(paths) == the_face_files()
    wrong = [
        rel
        for rel, digest in entries
        if _sha(TOOLS_ROOT / Path(*rel.split("/"))) != digest
    ]
    assert not wrong, "files that differ from the manifest: %s" % wrong


def test_sc_l10n_build_001_4_verify_freeze_passes_over_a_counted_denominator():
    """SC-L10N-BUILD-001-4: on the committed tree ``--verify-freeze`` exits 0, prints
    that it compared 30 files with 0 violations, and the 30 is the number of manifest
    entries the test counted itself."""
    res = run_freeze(TOOLS_ROOT, MANIFEST.parent, Path(os.environ.get("TEMP", ".")))
    assert res.returncode == 0, res.text
    compared, violations = freeze_numbers(res)
    assert compared == len(manifest_entries()) == FROZEN_FILE_COUNT
    assert violations == 0
    assert "VIOLATION" not in res.stdout
    info = INFO_LINE.search(res.stdout)
    assert info and tuple(int(g) for g in info.groups()) == (30, 30, 0, 0), res.text


def test_sc_l10n_build_001_4_the_unplanted_scratch_root_is_clean(scratch_root):
    """Control of every planted case below: the scratch root, before any change,
    passes with the same 30 files compared. A scratch root that failed on its own would
    make each planted case pass for the wrong reason."""
    res = verify(scratch_root)
    assert res.returncode == 0, res.text
    assert freeze_numbers(res) == (30, 0)


# --------------------------------------------------------------------------
# One byte changed, in each of the 30 files
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rel", [e[0] for e in manifest_entries()])
def test_sc_l10n_build_001_4_a_one_byte_change_to_a_manifest_file_fails_and_names_it(
    scratch_root, rel
):
    """SC-L10N-BUILD-001-4: one byte of one scratch copy of a manifest file is changed.
    The check exits 1, names that file as differing from the manifest and no other, and
    prints 30 compared with 1 violation."""
    path = scratch_root.path(rel)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 1
    path.write_bytes(bytes(data))
    assert _sha(path) != dict(manifest_entries())[rel]
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    named = [ln for ln in res.stdout.split("\n") if "differs from the manifest" in ln]
    assert named == ["  VIOLATION %s differs from the manifest" % rel], res.text
    assert freeze_numbers(res) == (30, 1)


@pytest.mark.parametrize(
    "rel",
    [
        "fonts-src/nifen-art/symbols.txt",
        "pixelart_creator/fonts/NifenArt-Regular.ttf",
        "pixelart_creator/fonts/OFL.txt",
    ],
)
def test_sc_l10n_build_001_4_a_listed_file_that_is_missing_fails_and_names_it(
    scratch_root, rel
):
    """SC-L10N-BUILD-001-4: a listed file that is gone is a violation and not a file
    to skip; only 29 are compared."""
    scratch_root.path(rel).unlink()
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    assert "  VIOLATION %s is listed but missing" % rel in res.stdout, res.text
    assert freeze_numbers(res) == (29, 1)


@pytest.mark.parametrize(
    "rel",
    [
        "fonts-src/nifen-art/extra.txt",
        "fonts-src/nifen-art/coverage/extra.txt",
    ],
)
def test_sc_l10n_build_001_4_a_file_added_to_the_frozen_face_fails_and_names_it(
    scratch_root, rel
):
    """SC-L10N-BUILD-001-4: a file under ``fonts-src/nifen-art`` that the manifest does
    not list, at the top and in the ``coverage`` folder, fails and is named."""
    scratch_root.path(rel).write_bytes(b"# an added file\n")
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    assert (
        "  VIOLATION %s is not in the manifest: a file was added to the frozen face"
        % rel
        in res.stdout
    ), res.text
    assert freeze_numbers(res) == (30, 1)


def test_sc_l10n_build_001_4_a_missing_manifest_fails_with_nothing_compared(
    scratch_root,
):
    """SC-L10N-BUILD-001-4: without the manifest the check cannot answer, and says so
    with exit 1 and 0 files compared; it does not pass on an empty comparison."""
    scratch_root.manifest.unlink()
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    assert "existing-face.sha256 is missing" in res.stdout, res.text
    assert freeze_numbers(res) == (0, 1)


def test_sc_l10n_build_001_4_a_malformed_manifest_line_fails_and_names_it(
    scratch_root,
):
    """SC-L10N-BUILD-001-4: a line that is not ``<sha256>  <path>`` is refused."""
    with open(scratch_root.manifest, "ab") as fh:
        fh.write(b"not a hash line\n")
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    assert "is not '<sha256>  <path>'" in res.stdout, res.text
    assert freeze_numbers(res) == (30, 1)


def test_sc_l10n_build_001_4_a_manifest_that_matches_no_file_compares_nothing_and_fails(
    scratch_root,
):
    """SC-L10N-BUILD-001-4: a zero-file comparison is a failure, never a pass. The
    scratch root loses every file of the face, and the check ends with 0 compared."""
    for rel in the_face_files():
        scratch_root.path(rel).unlink()
    res = verify(scratch_root)
    assert res.returncode == 1, res.text
    assert "nothing was compared" in res.stdout, res.text
    compared, violations = freeze_numbers(res)
    assert compared == 0 and violations >= 1


# --------------------------------------------------------------------------
# The existing face holds no Han and no Hangul
# --------------------------------------------------------------------------


def _count_in(cmap, blocks) -> int:
    return sum(1 for cp in cmap if any(lo <= cp <= hi for lo, hi in blocks))


@pytest.mark.parametrize("name", ["NifenArt-Regular.ttf", "NifenArt-Bold.ttf"])
def test_sc_l10n_build_001_4_the_existing_face_holds_0_han_and_0_hangul(name):
    """SC-L10N-BUILD-001-4 (the CJK face exists so the existing one does not grow): the
    committed Regular and Bold fonts map 0 Han and 0 Hangul code points, over a
    character map that is not empty and does hold the kana the face is known for."""
    from fontTools.ttLib import TTFont

    with TTFont(str(TOOLS_ROOT / Path(*FONTS_REL.split("/")) / name)) as font:
        cmap = font.getBestCmap()
    assert len(cmap) > 500, "the character map was not read: %d code points" % len(cmap)
    assert 0x3042 in cmap and 0x0041 in cmap
    assert _count_in(cmap, HAN_BLOCKS) == 0
    assert _count_in(cmap, HANGUL_BLOCKS) == 0


def test_sc_l10n_build_001_4_control_the_han_and_hangul_reader_sees_them_in_a_font(
    tmp_path,
):
    """Control of the case above: the same reader, on a scratch font that does map one
    Han and one Hangul code point, counts one of each, so '0' means none and not
    'could not see'."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont

    pen = TTGlyphPen(None)
    names = [".notdef", "uni4E2D", "uniD55C"]
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({0x4E2D: "uni4E2D", 0xD55C: "uniD55C"})
    builder.setupGlyf({name: pen.glyph() for name in names})
    builder.setupHorizontalMetrics({name: (1024, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Control", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    path = tmp_path / "control.ttf"
    builder.save(str(path))
    with TTFont(str(path)) as font:
        cmap = font.getBestCmap()
    assert _count_in(cmap, HAN_BLOCKS) == 1
    assert _count_in(cmap, HANGUL_BLOCKS) == 1


def test_sc_l10n_build_001_4_the_scratch_files_are_copies_of_the_committed_ones(
    scratch_root,
):
    """The planted cases above change COPIES: after a scratch change, the committed
    file keeps the digest the manifest holds (the module guard checks the same for all
    30 at the end of the run)."""
    rel = "fonts-src/nifen-art/metrics.txt"
    scratch_root.path(rel).write_bytes(b"changed\n")
    assert _sha(TOOLS_ROOT / Path(*rel.split("/"))) == dict(manifest_entries())[rel]
