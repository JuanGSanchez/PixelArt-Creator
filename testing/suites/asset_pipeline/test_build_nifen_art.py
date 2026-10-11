# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Contract tests of the Nifen Art font scripts under ``scripts/font/``.

The subjects are ``build_nifen_art.py`` (source lint, deterministic build,
``--check`` byte identity), ``lint_controls.py`` (the injected-defect controls of
the lint), ``nifen_src.py`` (the glyph-source reader the others share) and the
argument contract of the two specimen scripts. The inputs are the COMMITTED
sources under ``fonts-src/nifen-art`` and the COMMITTED fonts under
``pixelart_creator/fonts``; both are only ever READ. Anything that needs a
modified tree works on a COPY under the per-test scratch folder.

Scenarios covered (one group each):

* SC-VI-BUILD-002-1 - two builds, and builds under two ``PYTHONHASHSEED``
  values, are byte-identical for Regular and Bold.
* SC-VI-BUILD-002-2 - the committed fonts are the build's output; ``--check``
  detects a single changed byte in either font and a changed source.
* SC-VI-BUILD-003-1 - the lint reports zero violations over a non-zero count of
  glyph-weights; the 12-row em and the 7-row capital height are checked here
  independently of the lint, and a planted defect per rule is caught.
* SC-VI-BUILD-003-2 / -3 / -4 - Greek capital tonos above-left, identical letters
  sharing one shape, and the shapes kept after review (W/w 7 columns, the ring of
  the A-ring touching the apex, the guillemets 3 rows tall).
* SC-VI-BUILD-010-1 (font half) - the name-table scan examines a non-zero number
  of records, reports none on the built fonts, and reports a planted violation of
  every category it claims to cover (the PNG half is in ``test_derive_app_icons``).
* SC-VI-BUILD-005-2 - the Reserved Font Name clause ends the typeface's own
  copyright line in OFL.txt and in name ID 0 of both fonts (every platform
  record), is recorded in FONTLOG.txt, and is not attached to the Ark Pixel Font
  line; the omission or misplacement planted in a copy of each of the three is
  reported, and examining nothing is a failure (section 10).
* SC-VI-BUILD-011-2 (the direct control) - the donor line removed, altered or
  reordered in name ID 0 of a BUILT font is reported by the build's own
  name-record check, and ``--build`` ends with a violation and exit 1
  (section 11).
* The command line: modes, exit codes (0 pass, 1 violation, 2 source error or
  usage), the denominators printed, and failure when nothing was examined.

Independence of the numbers: the built fonts are read back with fontTools by the
tests themselves (name table, metrics, outlines, cmap); the 12-row em, the capital
height, the tonos zone and the kept shapes are recomputed from the sources with
predicates written here, not taken from the lint's own report.

fontTools is a BUILD-TIME dependency that must be declared by the project (the
dev extra and ``constraints.txt``). If it is not importable every test of this
module FAILS with a message that says so; none is skipped.

Test seam: ``NIFEN_TOOLS_ROOT`` points the tests at a COPY of the layout
(``scripts/font``, ``fonts-src/nifen-art``, ``pixelart_creator/fonts``,
``pixelart_creator/i18n``). It exists so a test can be shown to catch a mutated
script (run the module against a mutant copy and see it fail); it is unset in
normal runs.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unicodedata
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import pytest

from .conftest import REPO_ROOT

# --------------------------------------------------------------------------
# Locations, constants, and the seam
# --------------------------------------------------------------------------

TOOLS_ROOT = Path(os.environ.get("NIFEN_TOOLS_ROOT") or REPO_ROOT).resolve()
FONT_SCRIPTS = TOOLS_ROOT / "scripts" / "font"
SOURCES = TOOLS_ROOT / "fonts-src" / "nifen-art"
FONT_DIR = TOOLS_ROOT / "pixelart_creator" / "fonts"
I18N_DIR = TOOLS_ROOT / "pixelart_creator" / "i18n"

BUILD = "build_nifen_art.py"
WEIGHTS = ("regular", "bold")
FONT_FILES = {"regular": "NifenArt-Regular.ttf", "bold": "NifenArt-Bold.ttf"}

#: The fontTools version the committed fonts were built and proved with. The
#: build is byte-stable only as far as that version is concerned.
FONTTOOLS_PIN = "4.63.0"

MISSING_FONTTOOLS = (
    "fontTools is not importable. It is a build-time dependency of the Nifen Art "
    "scripts and the committed fonts were built with fontTools==%s. Declare it in "
    "the dev extra of pyproject.toml and pin it in constraints.txt (CI installs "
    "'-c constraints.txt -e .[dev]' and nothing else), then reinstall. These tests "
    "fail rather than skip so that a missing build dependency is never read as a "
    "pass." % FONTTOOLS_PIN
)

#: Directories whose contents no test may change (hash-guarded per module).
_GUARDED = (FONT_SCRIPTS, TOOLS_ROOT / "fonts-src", FONT_DIR, I18N_DIR)


class Run(NamedTuple):
    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout + self.stderr


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_fonttools():
    """Fail (never skip) when the build dependency is missing."""
    if importlib.util.find_spec("fontTools") is None:
        pytest.fail(MISSING_FONTTOOLS, pytrace=False)


def _tree_digest() -> Dict[str, str]:
    """Relative path -> sha256 (or a directory marker) of every guarded file."""
    out: Dict[str, str] = {}
    for root in _GUARDED:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(TOOLS_ROOT).as_posix()
            out[rel] = (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else "<directory>"
            )
    return out


@pytest.fixture(scope="module", autouse=True)
def _committed_files_are_never_touched():
    """No test of this module may add, remove or change a committed file."""
    before = _tree_digest()
    assert before, "nothing to guard: the font scripts or sources are missing"
    yield
    after = _tree_digest()
    changed = sorted(
        k for k in set(before) | set(after) if before.get(k) != after.get(k)
    )
    assert not changed, "committed files were touched by the tests: %s" % changed


@pytest.fixture
def scratch(tmp_path_factory):
    """A private folder under the configured temp root, removed after the test.

    ``ORCH_TEST_TMP`` is the root this repository's test runner configures;
    without it the folder comes from pytest's own base temp directory.
    """
    root = os.environ.get("ORCH_TEST_TMP")
    if root:
        base = Path(root) / "asset-pipeline-nifen"
        base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="b-", dir=str(base)))
    else:
        folder = tmp_path_factory.mktemp("nifen-build")
    yield folder
    shutil.rmtree(folder)


# --------------------------------------------------------------------------
# Running the scripts
# --------------------------------------------------------------------------


def _child_env(scratch: Path, extra: Optional[Dict[str, str]] = None) -> dict:
    """Environment for a child: temp folders redirected into the scratch."""
    proc_tmp = scratch / "proc-tmp"
    proc_tmp.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "TMP": str(proc_tmp),
            "TEMP": str(proc_tmp),
            "TMPDIR": str(proc_tmp),
        }
    )
    env.pop("PYTHONHASHSEED", None)
    if extra:
        env.update(extra)
    return env


def run_font(
    script: str,
    args: Sequence[object],
    scratch: Path,
    *,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[Path] = None,
    timeout: int = 300,
) -> Run:
    """Run ``scripts/font/<script>`` as a real subprocess (its documented entry)."""
    done = subprocess.run(
        [sys.executable, "-B", str(FONT_SCRIPTS / script), *[str(a) for a in args]],
        cwd=str(cwd or TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_child_env(scratch, env),
    )
    return Run(done.returncode, done.stdout, done.stderr)


def _modules():
    """Import the script modules in this process, without writing bytecode."""
    sys.dont_write_bytecode = True
    if str(FONT_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(FONT_SCRIPTS))
    return importlib.import_module("nifen_src"), importlib.import_module(
        "build_nifen_art"
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_sources(scratch: Path, name: str = "src") -> Path:
    dst = scratch / name
    shutil.copytree(SOURCES, dst)
    return dst


def plant(scratch: Path, edits: Sequence[Tuple[str, str, str]]) -> Path:
    """A COPY of the sources with each ``(file, old, new)`` edit applied once.

    The anchor must occur exactly once: an edit that silently found nothing would
    leave an unmodified tree and every test built on it would pass for nothing.
    """
    dst = _copy_sources(scratch)
    for name, old, new in edits:
        path = dst / name
        text = path.read_bytes().decode("utf-8")
        assert text.count(old) == 1, "%s: anchor found %d times, expected once: %r" % (
            name,
            text.count(old),
            old[:60],
        )
        path.write_bytes(text.replace(old, new, 1).encode("utf-8"))
    return dst


RULE_LINE = re.compile(
    r"^(R\d{2})\s+(.+?)\s+examined\s+(\d+)\s+violations\s+(\d+)\s*$", re.M
)


def lint_rules(text: str) -> Dict[str, Tuple[int, int]]:
    """Rule code -> (examined, violations) as printed by ``--lint``."""
    return {m[1]: (int(m[3]), int(m[4])) for m in RULE_LINE.finditer(text)}


def violation_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if "VIOLATION" in ln]


def declared_count() -> int:
    """The size of the declared character set, from its own header."""
    head = (SOURCES / "coverage" / "declared-set.txt").read_text(encoding="utf-8")
    found = re.search(r"\((\d+) unique characters per weight\)", head)
    assert found, "the declared-set header no longer states its count"
    return int(found.group(1))


CHECK_BLOCK = re.compile(
    r"(NifenArt-\w+\.ttf)\s+build1 (\S+)\s*\n\s+build2 (\S+)\s*\n"
    r"\s+disk\s+(\S+)\s+(IDENTICAL|DIFFERENT)"
)


# --------------------------------------------------------------------------
# 1. The build dependency
# --------------------------------------------------------------------------


def test_fonttools_is_installed_at_the_pinned_version():
    """The committed fonts were built with one fontTools; a different one is named."""
    import fontTools

    assert fontTools.version == FONTTOOLS_PIN, (
        "fontTools %s is installed but the committed fonts were built and proved "
        "with %s; byte identity across versions is an assumption, not a measurement. "
        "Pin the declared version and, if it must move, rebuild and re-prove the "
        "fonts." % (fontTools.version, FONTTOOLS_PIN)
    )


def test_fonttools_is_declared_for_ci_in_the_dev_extra_and_the_constraints():
    """CI installs only ``-c constraints.txt -e .[dev]``; fontTools must be in both.

    Locally fontTools can arrive as a transitive dependency of an unrelated
    package, so a green run here proves nothing about CI. This reads the two
    declaration files instead.
    """
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        extras = tomllib.load(fh)["project"]["optional-dependencies"]
    dev_names = {
        re.split(r"[<>=!~\[;\s]", spec, maxsplit=1)[0].lower().replace("_", "-")
        for spec in extras["dev"]
    }
    constraint_lines = [
        ln.strip().lower().replace("_", "-")
        for ln in (REPO_ROOT / "constraints.txt")
        .read_text(encoding="utf-8")
        .split("\n")
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    pinned = [ln for ln in constraint_lines if ln.startswith("fonttools==")]
    problems = []
    if "fonttools" not in dev_names:
        problems.append(
            "pyproject.toml [project.optional-dependencies] dev lacks fonttools"
        )
    if pinned != ["fonttools==%s" % FONTTOOLS_PIN]:
        problems.append(
            "constraints.txt must contain exactly 'fonttools==%s' (found %s)"
            % (FONTTOOLS_PIN, pinned or "no pin")
        )
    assert not problems, (
        "fontTools is a build-time dependency of scripts/font and of these tests and "
        "is not declared for CI: " + "; ".join(problems)
    )


@pytest.mark.parametrize("mode", ["--build", "--check"])
def test_a_missing_fonttools_fails_the_build_loudly(scratch, mode):
    """With fontTools hidden, build and check exit non-zero and name the cause."""
    shim = scratch / "shim" / "fontTools"
    shim.mkdir(parents=True)
    (shim / "__init__.py").write_text(
        "raise ImportError('fontTools is hidden by the test')\n", encoding="utf-8"
    )
    out = scratch / "out"
    out.mkdir()
    res = run_font(
        BUILD,
        [mode, "--out", out],
        scratch,
        env={"PYTHONPATH": str(shim.parent)},
    )
    assert res.returncode != 0, res.text
    assert "fontTools" in res.text


# --------------------------------------------------------------------------
# 2. The command line (exit codes, denominators, zero examined)
# --------------------------------------------------------------------------


def test_no_mode_is_a_usage_error(scratch):
    """One of --lint/--build/--check is required: argparse exit 2."""
    res = run_font(BUILD, [], scratch)
    assert res.returncode == 2, res.text
    assert "--lint" in res.stderr and "required" in res.stderr


def test_two_modes_are_a_usage_error(scratch):
    res = run_font(BUILD, ["--lint", "--check"], scratch)
    assert res.returncode == 2, res.text
    assert "not allowed with" in res.stderr


def test_an_unknown_flag_is_a_usage_error(scratch):
    res = run_font(BUILD, ["--lint", "--no-such-flag"], scratch)
    assert res.returncode == 2, res.text


def test_help_exits_zero_and_names_the_three_modes(scratch):
    res = run_font(BUILD, ["--help"], scratch)
    assert res.returncode == 0, res.text
    for flag in ("--lint", "--build", "--check", "--src", "--out", "--tmp"):
        assert flag in res.stdout, flag


def test_lint_of_the_committed_sources_is_clean_over_a_counted_denominator(scratch):
    """SC-VI-BUILD-003-1: zero violations over a non-zero glyph-weight count."""
    res = run_font(BUILD, ["--lint"], scratch)
    assert res.returncode == 0, res.text
    rules = lint_rules(res.stdout)
    expected = {"R%02d" % n for n in range(1, 13)}
    assert expected <= set(rules), "rules missing from the report: %s" % (
        expected - set(rules)
    )
    for code, (examined, violations) in rules.items():
        assert examined > 0, "%s examined nothing" % code
        assert violations == 0, "%s reports %d violations" % (code, violations)
    glyphs = re.search(
        r"glyphs: (\d+) codepoints x 2 weights = (\d+) examined", res.stdout
    )
    assert glyphs, res.stdout[-400:]
    n_cps, n_glyph_weights = int(glyphs[1]), int(glyphs[2])
    assert n_cps == declared_count()
    assert n_glyph_weights == 2 * n_cps > 0
    assert "lint violations: 0" in res.stdout


def test_lint_of_a_missing_source_folder_fails(scratch):
    """No sources is a failure, never a clean run over nothing."""
    res = run_font(BUILD, ["--lint", "--src", scratch / "does-not-exist"], scratch)
    assert res.returncode != 0, res.text
    assert "lint violations: 0" not in res.stdout


def test_lint_of_sources_that_do_not_cover_the_set_is_a_source_error(scratch):
    """A metrics file alone cannot describe the declared set: exit 2, named."""
    only = scratch / "metrics-only"
    only.mkdir()
    shutil.copy(SOURCES / "metrics.txt", only / "metrics.txt")
    res = run_font(BUILD, ["--lint", "--src", only], scratch)
    assert res.returncode == 2, res.text
    assert "source error:" in res.stdout


def test_a_recipe_that_names_a_missing_base_is_a_source_error(scratch):
    src = plant(
        scratch,
        [
            (
                "recipes.txt",
                "recipe U+00E1 = mark U+0061 acute.low",
                "recipe U+00E1 = mark U+E000 acute.low",
            )
        ],
    )
    res = run_font(BUILD, ["--lint", "--src", src], scratch)
    assert res.returncode == 2, res.text
    assert "source error:" in res.stdout


def test_a_rule_that_examines_nothing_fails_the_lint(scratch):
    """Emptying the small-kana set leaves rule R12 with nothing to examine."""
    metrics = (SOURCES / "metrics.txt").read_bytes().decode("utf-8")
    line = re.search(r"^small_kana_cps = .*$", metrics, re.M)
    assert line, "metrics no longer declare small_kana_cps"
    src = plant(scratch, [("metrics.txt", line[0], "small_kana_cps =")])
    res = run_font(BUILD, ["--lint", "--src", src], scratch)
    assert res.returncode != 0, res.text
    if "R12" in res.stdout:
        examined, _ = lint_rules(res.stdout)["R12"]
        assert examined == 0, res.stdout


def test_build_writes_both_fonts_and_prints_what_it_scanned(scratch):
    """SC-VI-BUILD-002-2 / -010-1: sizes and hashes printed are the files', and
    the name-table scan examined records."""
    out = scratch / "out"
    res = run_font(BUILD, ["--build", "--out", out], scratch)
    assert res.returncode == 0, res.text
    scanned = re.search(
        r"name records scanned: (\d+), public-safe violations: (\d+)", res.stdout
    )
    assert scanned and int(scanned[1]) > 0 and int(scanned[2]) == 0, res.stdout
    printed = {
        m[1]: (int(m[2]), m[3])
        for m in re.finditer(
            r"built (\S+)\s+(\d+) bytes\s+sha256 ([0-9a-f]{64})", res.stdout
        )
    }
    assert set(printed) == set(FONT_FILES.values()), res.stdout
    for weight, name in FONT_FILES.items():
        built = out / name
        assert built.is_file(), "%s was not written" % name
        assert printed[name] == (built.stat().st_size, _sha(built))
        assert built.read_bytes() == (FONT_DIR / name).read_bytes(), (
            "%s differs from the committed font" % name
        )


def test_build_is_refused_when_the_lint_fails_and_writes_nothing(scratch):
    src = plant(
        scratch, [("latin-basic.txt", "glyph U+0041 adv=6", "glyph U+0041 adv=7")]
    )
    out = scratch / "out"
    res = run_font(BUILD, ["--build", "--src", src, "--out", out], scratch)
    assert res.returncode == 1, res.text
    assert "build refused: lint failed" in res.stdout
    assert not out.exists() or not list(out.iterdir()), "fonts written despite lint"


def test_check_of_the_committed_fonts_reports_identity_for_both_weights(scratch):
    """SC-VI-BUILD-002-2: the rebuilt files equal the committed files byte for byte."""
    res = run_font(BUILD, ["--check"], scratch)
    assert res.returncode == 0, res.text
    blocks = {m[1]: m for m in CHECK_BLOCK.finditer(res.stdout)}
    assert set(blocks) == set(FONT_FILES.values()), res.stdout
    for name in FONT_FILES.values():
        _n, build1, build2, disk, verdict = blocks[name].groups()
        assert verdict == "IDENTICAL"
        assert build1 == build2 == disk == _sha(FONT_DIR / name)
    assert "--check: 2/2 weights byte-identical" in res.stdout


def test_check_fails_when_the_committed_fonts_are_missing(scratch):
    empty = scratch / "empty"
    empty.mkdir()
    res = run_font(BUILD, ["--check", "--out", empty], scratch)
    assert res.returncode == 1, res.text
    assert "(missing)" in res.stdout
    assert "--check: 0/2 weights byte-identical" in res.stdout


def test_check_leaves_nothing_behind_in_its_scratch_folder(scratch):
    """``--tmp`` is created for the two rebuilds and left empty afterwards."""
    tmp = scratch / "check-tmp"
    res = run_font(BUILD, ["--check", "--tmp", tmp], scratch)
    assert res.returncode == 0, res.text
    assert tmp.is_dir() and list(tmp.iterdir()) == []


@pytest.mark.parametrize("position", ["first", "middle", "last"])
@pytest.mark.parametrize("weight", WEIGHTS)
def test_check_detects_a_single_changed_byte_in_a_built_font(scratch, weight, position):
    """SC-VI-BUILD-002-2: one flipped bit in a COPY of one font fails --check,
    names that weight DIFFERENT and leaves the other weight IDENTICAL."""
    out = scratch / "fonts"
    shutil.copytree(FONT_DIR, out)
    target = out / FONT_FILES[weight]
    data = bytearray(target.read_bytes())
    index = {"first": 0, "middle": len(data) // 2, "last": len(data) - 1}[position]
    data[index] ^= 0x01
    target.write_bytes(bytes(data))
    res = run_font(BUILD, ["--check", "--out", out], scratch)
    assert res.returncode == 1, res.text
    verdicts = {m[1]: m[5] for m in CHECK_BLOCK.finditer(res.stdout)}
    other = FONT_FILES["bold" if weight == "regular" else "regular"]
    assert verdicts[FONT_FILES[weight]] == "DIFFERENT", res.stdout
    assert verdicts[other] == "IDENTICAL", res.stdout
    assert "--check: 0/2 weights byte-identical" in res.stdout


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(
            (
                "metrics.txt",
                "version_string = Version 0.100",
                "version_string = Version 0.101",
            ),
            id="metadata",
        ),
        pytest.param(
            (
                "latin-basic.txt",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####",
                "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n##..#\n#####",
            ),
            id="one-pixel",
        ),
    ],
)
def test_check_detects_a_source_that_no_longer_matches_the_committed_fonts(
    scratch, edit
):
    """The committed fonts must be the build of the committed sources."""
    src = plant(scratch, [edit])
    res = run_font(BUILD, ["--check", "--src", src], scratch)
    assert res.returncode == 1, res.text
    assert "DIFFERENT" in res.stdout
    assert "--check: 0/2 weights byte-identical" in res.stdout


# --------------------------------------------------------------------------
# 3. Determinism (SC-VI-BUILD-002-1)
# --------------------------------------------------------------------------


def _build_into(scratch: Path, name: str, env: Optional[Dict[str, str]] = None) -> Path:
    out = scratch / name
    res = run_font(BUILD, ["--build", "--out", out], scratch, env=env)
    assert res.returncode == 0, res.text
    for font in FONT_FILES.values():
        assert (out / font).is_file(), "%s missing after --build" % font
    return out


def test_two_builds_are_byte_identical_and_equal_the_committed_fonts(scratch):
    first = _build_into(scratch, "build-1")
    second = _build_into(scratch, "build-2")
    for name in FONT_FILES.values():
        a, b = (first / name).read_bytes(), (second / name).read_bytes()
        assert len(a) > 0
        assert a == b, "%s differs between two builds" % name
        assert a == (FONT_DIR / name).read_bytes(), "%s differs from committed" % name


@pytest.mark.parametrize("seed", ["1", "4242"])
def test_the_build_does_not_depend_on_the_hash_seed(scratch, seed):
    """Every hash-ordered iteration inside the build would show up here."""
    out = _build_into(scratch, "seed-%s" % seed, env={"PYTHONHASHSEED": seed})
    for name in FONT_FILES.values():
        built, committed = (out / name).read_bytes(), (FONT_DIR / name).read_bytes()
        assert (
            built == committed
        ), "%s built under PYTHONHASHSEED=%s differs from the committed font" % (
            name,
            seed,
        )


# --------------------------------------------------------------------------
# 4. What the built fonts say (read back with fontTools, not via the script)
# --------------------------------------------------------------------------


def _epoch_1904(stamp: str) -> int:
    """Seconds since 1904-01-01 UTC of ``YYYY-MM-DDTHH:MM:SSZ`` (own formula)."""
    import calendar
    import time

    parsed = time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    return calendar.timegm(parsed) + 2082844800


def _metrics() -> Dict[str, str]:
    nifen_src, _build = _modules()
    return nifen_src.parse_metrics(str(SOURCES / "metrics.txt"))


@pytest.mark.parametrize("weight", WEIGHTS)
def test_built_font_header_and_names_follow_the_typeface_decision(weight):
    """ADR-0071 decision 7: names, weight class, em, fixed timestamps, no hinting."""
    from fontTools.ttLib import TTFont

    font = TTFont(str(FONT_DIR / FONT_FILES[weight]))
    metrics = _metrics()
    names = {rec.nameID: rec.toUnicode() for rec in font["name"].names}
    bold = weight == "bold"
    assert names[1] == "Nifen Art"
    assert names[2] == ("Bold" if bold else "Regular")
    assert names[6] == ("NifenArt-Bold" if bold else "NifenArt-Regular")
    assert font["OS/2"].usWeightClass == (700 if bold else 400)
    assert bool(font["OS/2"].fsSelection & 0x20) == bold  # bold bit
    assert bool(font["OS/2"].fsSelection & 0x40) == (not bold)  # regular bit
    assert bool(font["head"].macStyle & 1) == bold
    assert font["head"].unitsPerEm == 1536
    assert font["head"].created == _epoch_1904(metrics["created_utc"])
    assert font["head"].modified == _epoch_1904(metrics["modified_utc"])
    assert metrics["copyright_holder"] in names[0]
    assert names[9] == metrics["designer"]
    assert "SIL Open Font License" in names[13]
    assert names[14] == metrics["license_url"]
    for table in ("fpgm", "prep", "cvt "):
        assert table not in font, "a hinting program (%s) is present" % table


@pytest.mark.parametrize("weight", WEIGHTS)
def test_built_font_covers_exactly_the_declared_set(weight):
    from fontTools.ttLib import TTFont

    cmap = TTFont(str(FONT_DIR / FONT_FILES[weight])).getBestCmap()
    assert len(cmap) == declared_count() > 0


def test_a_alpha_and_cyrillic_a_share_one_outline_in_the_built_fonts():
    """SC-VI-BUILD-003-3 on the BUILT files: A, Alpha and Cyrillic A are one shape."""
    from fontTools.ttLib import TTFont

    for weight in WEIGHTS:
        font = TTFont(str(FONT_DIR / FONT_FILES[weight]))
        cmap, glyf, hmtx = font.getBestCmap(), font["glyf"], font["hmtx"]
        shapes = set()
        for cp in (0x41, 0x391, 0x410):
            assert cp in cmap, "U+%04X missing from %s" % (cp, weight)
            glyph = glyf[cmap[cp]]
            coords, ends, _flags = glyph.getCoordinates(glyf)
            shapes.add((tuple(coords), tuple(ends), hmtx[cmap[cp]][0]))
        assert len(shapes) == 1, "A, Alpha and Cyrillic A differ in %s" % weight


# --------------------------------------------------------------------------
# 5. The design contract read from the sources (SC-VI-BUILD-003-1..4)
# --------------------------------------------------------------------------

Findings = Tuple[int, List[str]]  # (examined, problems)


def _font_of(src_dir: Path):
    nifen_src, _build = _modules()
    return nifen_src.Font(nifen_src.parse_sources(str(src_dir)))


def _ints(font, *keys: str) -> List[int]:
    return [int(font.srcs.metrics[k]) for k in keys]


def _ink(font, cp: int, weight: str):
    nifen_src, _build = _modules()
    bmp = font.bmp(cp, weight)
    return bmp, nifen_src.bbox(bmp.px)


def em_findings(font) -> Findings:
    """SC-VI-BUILD-003-1: every glyph lies in the 12-row em, in both weights."""
    em_px, bottom, top = _ints(font, "em_px", "em_bottom_px", "em_top_px")
    problems = []
    if top - bottom != em_px:
        problems.append("em box %d..%d is not %d rows" % (bottom, top - 1, em_px))
    examined = 0
    for cp in font.codepoints():
        for weight in WEIGHTS:
            _bmp, bb = _ink(font, cp, weight)
            examined += 1
            if bb is not None and (bb[1] < bottom or bb[3] > top - 1):
                problems.append(
                    "U+%04X %s ink rows %d..%d outside %d..%d"
                    % (cp, weight, bb[1], bb[3], bottom, top - 1)
                )
    return examined, problems


def _capitals() -> List[int]:
    latin = list(range(0x41, 0x5B))
    greek = [c for c in range(0x391, 0x3AA) if c != 0x3A2]
    cyrillic = [c for c in range(0x410, 0x430) if c != 0x419]  # not the breve one
    return latin + greek + cyrillic


def capital_findings(font) -> Findings:
    """SC-VI-BUILD-003-1: capital letters measure 7 rows (top row = cap_px - 1)."""
    (cap,) = _ints(font, "cap_px")
    problems, examined = [], 0
    for cp in _capitals():
        for weight in WEIGHTS:
            _bmp, bb = _ink(font, cp, weight)
            examined += 1
            if bb is None or bb[3] != cap - 1:
                problems.append(
                    "U+%04X %s top row %s, expected %d"
                    % (cp, weight, None if bb is None else bb[3], cap - 1)
                )
            # the plain Latin and Greek capitals sit on the baseline and are 7 rows
            if cp < 0x410 and (bb is None or bb[1] != 0):
                problems.append("U+%04X %s does not sit on the baseline" % (cp, weight))
    return examined, problems


def _greek_capitals_with_tonos() -> List[int]:
    return [
        cp
        for cp in range(0x370, 0x400)
        if unicodedata.category(chr(cp)) == "Lu"
        and "WITH TONOS" in unicodedata.name(chr(cp), "")
    ]


def tonos_findings(font) -> Findings:
    """SC-VI-BUILD-003-2: the tonos lies in the accent zone, above-left, and the
    letter body is exactly the plain capital (nothing to its left)."""
    cap, gap, rows = _ints(font, "cap_px", "cap_mark_gap_rows", "mark_rows")
    zone = range(cap + gap, cap + gap + rows)
    problems, examined = [], 0
    for cp in _greek_capitals_with_tonos():
        recipe = font.recipe_by_cp.get(cp)
        if recipe is None or recipe.op != "mark":
            problems.append("U+%04X has no mark recipe" % cp)
            continue
        nifen_src, _build = _modules()
        base_cp = nifen_src.parse_cp(recipe.args[0])
        for weight in WEIGHTS:
            examined += 1
            px = font.bmp(cp, weight).px
            base = font.bmp(base_cp, weight).px
            body = {p for p in px if p[1] < cap}
            mark = {p for p in px if p[1] >= cap}
            if not mark:
                problems.append("U+%04X %s carries no mark" % (cp, weight))
                continue
            if body != set(base):
                problems.append(
                    "U+%04X %s letter body differs from the plain capital"
                    % (cp, weight)
                )
            bad_rows = sorted({y for _x, y in mark if y not in zone})
            if bad_rows:
                problems.append(
                    "U+%04X %s mark rows %s outside the accent zone %s"
                    % (cp, weight, bad_rows, list(zone))
                )
            # above-left: the mark starts at the letter's left edge and stays
            # within the letter's own columns (so it is above, not beside)
            left, right = min(x for x, _y in base), max(x for x, _y in base)
            mark_left, mark_right = min(x for x, _y in mark), max(x for x, _y in mark)
            if mark_left != left or mark_right > right:
                problems.append(
                    "U+%04X %s mark columns %d..%d are not flush-left within the "
                    "letter columns %d..%d"
                    % (cp, weight, mark_left, mark_right, left, right)
                )
    return examined, problems


def shared_shape_findings(font) -> Findings:
    """SC-VI-BUILD-003-3: A, Alpha and Cyrillic A (and every declared alias) are
    one shape in both weights."""
    problems, examined = [], 0
    for weight in WEIGHTS:
        shapes = {cp: font.bmp(cp, weight) for cp in (0x41, 0x391, 0x410)}
        examined += 1
        if len({(b.px, b.adv) for b in shapes.values()}) != 1:
            problems.append("A, Alpha and Cyrillic A differ in %s" % weight)
    for alias in font.srcs.aliases:
        for weight in WEIGHTS:
            examined += 1
            a, b = font.bmp(alias.target_cp, weight), font.bmp(alias.source_cp, weight)
            if (a.px, a.adv) != (b.px, b.adv):
                problems.append(
                    "alias U+%04X = U+%04X differs in %s"
                    % (alias.target_cp, alias.source_cp, weight)
                )
    return examined, problems


def kept_shape_findings(font) -> Findings:
    """SC-VI-BUILD-003-4: W and w 7 columns wide (advance 8 / 9), the A-ring ring
    touching the apex, the guillemets 3 rows tall."""
    nifen_src, _build = _modules()
    problems, examined = [], 0
    for cp in (0x57, 0x77):
        for weight, advance in (("regular", 8), ("bold", 9)):
            bmp, bb = _ink(font, cp, weight)
            examined += 1
            if bmp.adv != advance:
                problems.append(
                    "U+%04X %s advance %d != %d" % (cp, weight, bmp.adv, advance)
                )
            if weight == "regular" and bb[2] - bb[0] + 1 != 7:
                problems.append(
                    "U+%04X regular is %d columns" % (cp, bb[2] - bb[0] + 1)
                )
    for weight in WEIGHTS:
        examined += 1
        a_ring = font.bmp(0xC5, weight).px
        letter = font.bmp(0x41, weight).px
        ring = {p for p in a_ring if p[1] >= int(font.srcs.metrics["cap_px"])}
        apex = {p for p in letter if p[1] == int(font.srcs.metrics["cap_px"]) - 1}
        touches = any(
            (x + dx, y + dy) in apex
            for x, y in ring
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
        )
        if not touches:
            problems.append("the ring of A-ring does not touch the apex in %s" % weight)
    for cp in (0xAB, 0xBB, 0x2039, 0x203A):
        for weight in WEIGHTS:
            _bmp, bb = _ink(font, cp, weight)
            examined += 1
            if bb[3] - bb[1] + 1 != 3:
                problems.append(
                    "U+%04X %s is %d rows tall" % (cp, weight, bb[3] - bb[1] + 1)
                )
    return examined, problems


CONTRACT = {
    "em": em_findings,
    "capital": capital_findings,
    "tonos": tonos_findings,
    "shared": shared_shape_findings,
    "kept": kept_shape_findings,
}


@pytest.fixture(scope="module")
def committed_font():
    return _font_of(SOURCES)


@pytest.mark.parametrize("name", sorted(CONTRACT))
def test_the_committed_sources_satisfy_the_design_contract(committed_font, name):
    """SC-VI-BUILD-003-1..4 over the committed sources, with a counted denominator."""
    examined, problems = CONTRACT[name](committed_font)
    assert examined > 0, "the %s predicate examined nothing" % name
    assert problems == [], "\n".join(problems[:20])


def test_the_tonos_predicate_has_the_seven_greek_capitals_to_look_at():
    """The unicode database names seven capitals with tonos; all are examined."""
    assert len(_greek_capitals_with_tonos()) == 7


def _record_text(src: Path, name: str, header: str) -> str:
    """The text of one glyph record (header line to the blank line after it)."""
    text = (src / name).read_bytes().decode("utf-8")
    start = text.index(header)
    return text[start : text.index("\n\n", start)]


def _planted_w_six_columns(scratch: Path) -> Path:
    old = _record_text(SOURCES, "latin-basic.txt", "glyph U+0057 ")
    head, *rows = old.split("\n")
    new = "\n".join([head.replace("adv=8", "adv=7")] + [r[:-1] for r in rows])
    return plant(scratch, [("latin-basic.txt", old, new)])


def _planted_guillemet_four_rows(scratch: Path) -> Path:
    old = _record_text(SOURCES, "latin1.txt", "glyph U+00AB ")
    head, *rows = old.split("\n")
    new = "\n".join([head] + rows + [rows[-1]])
    return plant(scratch, [("latin1.txt", old, new)])


def _planted_capital_eight_rows(scratch: Path) -> Path:
    old = _record_text(SOURCES, "latin-basic.txt", "glyph U+0058 ")
    head, *rows = old.split("\n")
    new = "\n".join(
        [head.replace("top=7", "top=8").replace("ext=0..7", "ext=0..8")]
        + [rows[0]]
        + rows
    )
    return plant(scratch, [("latin-basic.txt", old, new)])


def _planted_a_cyrillic_differs(scratch: Path) -> Path:
    old_a = _record_text(SOURCES, "latin-basic.txt", "glyph U+0041 ")
    rows = old_a.split("\n")[1:]
    rows[-1] = "#...."  # one pixel fewer on the last row
    drawn = "glyph U+0410 adv=6 top=7 ext=0..7\n" + "\n".join(rows) + "\n"
    dst = plant(scratch, [("aliases.txt", "alias U+0410 = U+0041   # A = A\n", "")])
    with open(dst / "cyrillic.txt", "ab") as fh:
        fh.write(("\n" + drawn).encode("utf-8"))
    return dst


def _planted_tonos(option: str):
    def build(scratch: Path) -> Path:
        old = "recipe U+0386 = mark U+0391 acute.cap align=left"
        return plant(
            scratch,
            [("recipes.txt", old, "recipe U+0386 = mark U+0391 acute.cap " + option)],
        )

    return build


def _planted_ring_floats(scratch: Path) -> Path:
    return plant(
        scratch,
        [
            (
                "recipes.txt",
                "recipe U+00C5 = mark U+0041 ring.cap join=1",
                "recipe U+00C5 = mark U+0041 ring.cap join=1 rise=1",
            )
        ],
    )


CONTRACT_DEFECTS = [
    pytest.param("em", _planted_capital_eight_rows, id="em-box-bound-unmoved"),
    pytest.param("capital", _planted_capital_eight_rows, id="capital-eight-rows"),
    pytest.param("tonos", _planted_tonos("align=right"), id="tonos-above-right"),
    pytest.param("tonos", _planted_tonos("align=left rise=-8"), id="tonos-at-the-side"),
    pytest.param("shared", _planted_a_cyrillic_differs, id="cyrillic-a-differs"),
    pytest.param("kept", _planted_w_six_columns, id="w-six-columns"),
    pytest.param("kept", _planted_ring_floats, id="ring-floats"),
    pytest.param("kept", _planted_guillemet_four_rows, id="guillemet-four-rows"),
]


@pytest.mark.parametrize("name,builder", CONTRACT_DEFECTS)
def test_each_contract_predicate_catches_its_planted_defect(scratch, name, builder):
    """A predicate that cannot fail proves nothing: plant the defect in a COPY.

    ``em-box-bound-unmoved`` is the control for the em predicate: an eight-row
    capital still lies inside the 12-row em, so the em predicate must stay quiet
    where the capital predicate fires.
    """
    font = _font_of(builder(scratch))
    examined, problems = CONTRACT[name](font)
    assert examined > 0
    if name == "em":
        assert problems == [], "an eight-row capital is still inside the em"
    else:
        assert problems, "the %s predicate did not see the planted defect" % name


# --------------------------------------------------------------------------
# 6. The lint catches injected defects (one per rule)
# --------------------------------------------------------------------------

_X7 = (
    "glyph U+0058 adv=6 top=7 ext=0..7\n#...#\n#...#\n.#.#.\n..#..\n.#.#.\n#...#\n#...#"
)
_X6 = "glyph U+0058 adv=6 top=6 ext=0..6\n#...#\n#...#\n..#..\n.#.#.\n#...#\n#...#"
_X8 = (
    "glyph U+0058 adv=6 top=8 ext=0..8\n#...#\n#...#\n#...#\n.#.#.\n..#..\n.#.#.\n"
    "#...#\n#...#"
)
_H = "glyph U+0048 adv=6 top=7 ext=0..7\n#...#\n#...#\n#...#\n#####"
_O = "glyph U+006F adv=6 top=5 ext=0..5\n.###."


def _unsafe_comment() -> str:
    return "# Greek block, drawn by an A" + "I model."


LINT_DEFECTS = [
    # id, edits, rule, text the violation line must carry
    pytest.param(
        [
            (
                "latin-basic.txt",
                "glyph U+0045 adv=6 top=7 ext=0..7",
                "glyph U+0045 adv=6 top=12 ext=0..7",
            )
        ],
        "R01",
        "U+0045",
        id="R01-ink-outside-the-em",
    ),
    pytest.param(
        [("latin-basic.txt", _X7, _X6)],
        "R02",
        "U+0058",
        id="R02-capital-six-rows",
    ),
    pytest.param(
        [("latin-basic.txt", _X7, _X8)],
        "R02",
        "U+0058",
        id="R02-capital-eight-rows",
    ),
    pytest.param(
        [("latin-basic.txt", "glyph U+0041 adv=6", "glyph U+0041 adv=7")],
        "R03",
        "U+0041",
        id="R03-advance-of-A",
    ),
    pytest.param(
        [
            (
                "latin-basic.txt",
                "glyph U+0057 adv=8 top=7 ext=0..7",
                "glyph U+0057 adv=7 top=7 ext=0..7",
            )
        ],
        "R03",
        "U+0057",
        id="R03-advance-of-W",
    ),
    pytest.param(
        [
            (
                "latin-basic.txt",
                _O,
                "glyph U+006F adv=6 top=7 ext=0..7\n#....\n.....\n.###.",
            )
        ],
        "R04",
        "U+006F",
        id="R04-orphan-pixel-in-o",
    ),
    pytest.param(
        [
            (
                "latin-basic.txt",
                _H,
                _H.replace("#...#\n#...#\n#####", "#...#\n##..#\n#####"),
            )
        ],
        "R05",
        "U+0048",
        id="R05-two-by-two-in-Regular-H",
    ),
    pytest.param(
        [
            (
                "recipes.txt",
                "recipe U+00E1 = mark U+0061 acute.low",
                "recipe U+00E1 = mark U+0061 acute.low rise=-2",
            )
        ],
        "R06",
        "U+00E1",
        id="R06-accent-sunk-into-its-letter",
    ),
    pytest.param(
        [
            (
                "recipes.txt",
                "recipe U+00C5 = mark U+0041 ring.cap join=1",
                "recipe U+00C5 = mark U+0041 ring.cap",
            )
        ],
        "R06",
        "U+00C5",
        id="R06-ring-without-its-declared-join",
    ),
    pytest.param(
        [("symbols.txt", "glyph U+00D7 adv=6", "glyph U+0041 adv=6")],
        "R07",
        "duplicate glyph 65",
        id="R07-duplicate-code-point",
    ),
    pytest.param(
        [("bold-overlays.txt", "bold U+03A9", "bold U+03A8")],
        "R08",
        "U+03A9",
        id="R08-bold-overlay-of-Omega-removed",
    ),
    pytest.param(
        [("greek.txt", "# Greek block.", _unsafe_comment())],
        "R09",
        "greek.txt",
        id="R09-forbidden-token-in-a-comment",
    ),
    pytest.param(
        [
            (
                "hiragana-ark-pixel.txt",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=8",
                "glyph U+3083 adv=12 x=0 cell=full ext=free top=9",
            )
        ],
        "R12",
        "U+3083",
        id="R12-small-ya-raised",
    ),
    pytest.param(
        [("metrics.txt", "units_per_px = 128", "units_per_px = 64")],
        "R11",
        "units_per_px is 64",
        id="R11-units-per-pixel-changed",
    ),
    pytest.param(
        [("metrics.txt", "line_ascent_px = 11", "line_ascent_px = 9")],
        "R11",
        "line box does not contain the em box",
        id="R11-line-box-smaller-than-the-em",
    ),
]


@pytest.mark.parametrize("edits,rule,needle", LINT_DEFECTS)
def test_lint_reports_each_planted_defect_against_its_rule(
    scratch, edits, rule, needle
):
    """SC-VI-BUILD-003-1: a lint that cannot fail proves nothing. Each defect is
    planted in a COPY; the lint must exit 1, count a violation on the named rule
    and name the offending glyph or file on a VIOLATION line."""
    src = plant(scratch, edits)
    res = run_font(BUILD, ["--lint", "--src", src], scratch)
    assert res.returncode == 1, (
        "lint accepted the planted defect:\n" + res.stdout[-600:]
    )
    examined, violations = lint_rules(res.stdout)[rule]
    assert examined > 0 and violations >= 1, res.stdout
    assert any(
        needle in ln for ln in violation_lines(res.stdout)
    ), "no VIOLATION line names %s:\n%s" % (needle, res.stdout[-800:])


def test_r10_reports_an_outline_that_does_not_reproduce_the_grid(monkeypatch):
    """R10 cannot be provoked through the sources (the outline is derived from the
    grid), so its wiring is exercised in process: a contour finder that loses a
    loop must be reported against every glyph-weight, over a non-zero count."""
    nifen_src, build = _modules()
    srcs = nifen_src.parse_sources(str(SOURCES))
    font = nifen_src.Font(srcs)
    real = build.contours
    monkeypatch.setattr(build, "contours", lambda px: real(px)[:-1])
    report = build.lint(srcs, font, build.script_list(), str(SOURCES))
    _code, _title, examined, violations, _info = next(
        r for r in report.rules if r[0] == "R10"
    )
    assert examined == 2 * len(font.codepoints())
    blank = sum(
        1 for cp in font.codepoints() for w in WEIGHTS if not font.bmp(cp, w).px
    )
    assert (
        blank > 0 and len(violations) == examined - blank
    ), "every inked glyph-weight lost a loop (blank ones have nothing to lose)"
    assert report.failed()


# --------------------------------------------------------------------------
# 6b. The widened full-width cell (OF7 Q-29, option a)
# --------------------------------------------------------------------------
#
# The decision: the FULL-WIDTH cell (hiragana, katakana, CJK punctuation) takes
# ink in columns 0..10 in Regular and 0..11 in Bold (it was 1..10 and 1..11), and
# the small kana may be 9 rows tall and, when centred, 9 columns wide (they were
# 8). Half-width, Latin, Greek and Cyrillic limits did not move.
#
# Every limit below is READ from ``metrics.txt`` (the keys the lint itself reads),
# never copied here, except in the one test that pins the decision itself. Each
# catching case is a COPY of the sources with one defect planted by editing the
# committed record, and each is paired with its passing twin: the committed
# record, on the same lint, must be quiet about the same code point. A catching
# case without a quiet twin could be reporting something that was already there.

_RANGE = re.compile(r"\s*(-?\d+)\s*\.\.\s*(-?\d+)\s*$")

HIRAGANA_SRC = "hiragana-ark-pixel.txt"
HIRAGANA_A = 0x3042  # full-size, Regular ink columns 0..10, Bold 0..11
SMALL_A = 0x3041  # centred small kana, 9 x 9 in Regular
KATAKANA_E = 0x30A8  # full-width, left-placed small-kana family, drawn in katakana.txt


def _range_of(key: str) -> Tuple[int, int]:
    """A ``lo..hi`` metrics value, parsed here and not by the script under test."""
    found = _RANGE.match(_metrics()[key])
    assert found, "metrics key %s is no longer a lo..hi range" % key
    return int(found[1]), int(found[2])


def _int_of(key: str) -> int:
    return int(_metrics()[key])


def _weight_limits() -> Dict[str, Tuple[int, int]]:
    return {
        "regular": _range_of("cell_ink_x_regular"),
        "bold": _range_of("cell_ink_x_bold"),
    }


def _record_of(name: str, cp: int) -> Tuple[str, str, List[str]]:
    """``(whole record text, header line, bitmap rows)`` of a committed record."""
    old = _record_text(SOURCES, name, "glyph U+%04X " % cp)
    head, *rows = old.split("\n")
    assert rows and all(
        re.fullmatch(r"[.#]+", r) for r in rows
    ), "U+%04X in %s is not a plain bitmap record" % (cp, name)
    return old, head, rows


def _plant_record(scratch: Path, name: str, cp: int, rewrite) -> Path:
    """A COPY of the sources whose record of ``cp`` is ``rewrite(header, rows)``."""
    old, head, rows = _record_of(name, cp)
    new_head, new_rows = rewrite(head, list(rows))
    assert (new_head, new_rows) != (head, rows), "the rewrite changed nothing"
    return plant(scratch, [(name, old, "\n".join([new_head] + new_rows))])


def _shifted_one_column_right(head: str, rows: List[str]):
    """Every row one column further right (the glyph keeps its shape)."""
    return head, ["." + r for r in rows]


def _one_more_column_of_ink(head: str, rows: List[str]):
    """One pixel beyond the rightmost ink, on the first row that holds it: the
    glyph is exactly one column wider than it was, whatever its width."""
    far = max(r.rfind("#") for r in rows)
    first = next(i for i, r in enumerate(rows) if r.rfind("#") == far)
    out = [r.ljust(far + 2, ".") for r in rows]
    out[first] = out[first][: far + 1] + "#" + out[first][far + 2 :]
    return head, out


def _one_more_row_of_ink(head: str, rows: List[str]):
    """The top row repeated above itself and the header's ``top=`` raised by one:
    the glyph is exactly one row taller, on the same bottom row."""
    top = re.search(r"top=(-?\d+)", head)
    assert top, "no top= in %r" % head
    raised = head.replace(top[0], "top=%d" % (int(top[1]) + 1), 1)
    return raised, [rows[0]] + rows


def _extent(font, cp: int, weight: str) -> Tuple[int, int, int, int]:
    """``(first column, last column, rows, columns)`` of the drawn ink."""
    _bmp, bb = _ink(font, cp, weight)
    assert bb is not None, "U+%04X %s has no ink" % (cp, weight)
    return bb[0], bb[2], bb[3] - bb[1] + 1, bb[2] - bb[0] + 1


def _lint_of(scratch: Path, src: Path = SOURCES) -> Run:
    return run_font(BUILD, ["--lint", "--src", src], scratch)


def _lines_naming(res: Run, cp: int) -> List[str]:
    return [ln for ln in violation_lines(res.stdout) if "U+%04X" % cp in ln]


def _quiet_twin(scratch: Path, cp: int, rule: str) -> None:
    """The committed sources: lint clean, the rule examined, nothing about ``cp``."""
    twin = _lint_of(scratch)
    assert twin.returncode == 0, twin.text[-800:]
    examined, violations = lint_rules(twin.stdout)[rule]
    assert examined > 0 and violations == 0, twin.stdout[-800:]
    assert _lines_naming(twin, cp) == [], "the twin is not quiet about U+%04X" % cp


def _caught(
    scratch: Path,
    planted: Path,
    rule: str,
    needles: Sequence[str],
    absent: Sequence[str] = (),
) -> Run:
    """The lint exits 1 on the copy, counts the rule, and names each needle on a
    VIOLATION line; no line carries any of the ``absent`` texts."""
    res = _lint_of(scratch, planted)
    assert res.returncode == 1, (
        "lint accepted the planted defect:\n" + res.stdout[-600:]
    )
    examined, violations = lint_rules(res.stdout)[rule]
    assert examined > 0 and violations >= len(needles), res.stdout[-800:]
    lines = violation_lines(res.stdout)
    for needle in needles:
        assert any(needle in ln for ln in lines), "no VIOLATION line says %r:\n%s" % (
            needle,
            "\n".join(lines[:12]),
        )
    for text in absent:
        assert not any(text in ln for ln in lines), "unexpected %r:\n%s" % (
            text,
            "\n".join(lines[:12]),
        )
    return res


def test_the_widened_cell_limits_are_the_ones_the_user_approved():
    """OF7 Q-29 (a), pinned once and read from ``metrics.txt``: Regular ink takes
    11 columns, Bold one more, the small kana 9 rows and 9 centred columns. The
    other tests derive everything from the same keys; this is the one place the
    decision itself is written down, so narrowing a key back fails here by name."""
    limits = _weight_limits()
    assert limits["regular"] == (0, 10), "cell_ink_x_regular is not 0..10"
    assert limits["bold"] == (0, 11), "cell_ink_x_bold is not 0..11"
    assert _int_of("small_kana_max_rows") == 9
    assert _int_of("small_kana_centred_max_cols") == 9
    assert _int_of("cell_adv_px") == 12, "the advance did not change with the box"


def test_a_full_width_glyph_with_ink_in_every_allowed_column_passes_r01(scratch):
    """Twin of the R01 catches: U+3042 spans the whole Regular box (11 columns,
    0..10) and the whole Bold box (0..11); R01 examines it and is quiet."""
    font = _font_of(SOURCES)
    for weight, (lo, hi) in _weight_limits().items():
        first, last, _rows, cols = _extent(font, HIRAGANA_A, weight)
        assert (first, last) == (lo, hi), "U+3042 %s does not fill the box" % weight
        assert cols == hi - lo + 1
    _quiet_twin(scratch, HIRAGANA_A, "R01")


R01_CELL_DEFECTS = [
    pytest.param(
        HIRAGANA_SRC,
        HIRAGANA_A,
        _shifted_one_column_right,
        id="hiragana-a-shifted-one-column-right",
    ),
    pytest.param(
        HIRAGANA_SRC,
        HIRAGANA_A,
        _one_more_column_of_ink,
        id="hiragana-a-twelve-columns-wide",
    ),
    pytest.param(
        "katakana.txt",
        KATAKANA_E,
        _shifted_one_column_right,
        id="katakana-e-shifted-one-column-right",
    ),
]


@pytest.mark.parametrize("name,cp,rewrite", R01_CELL_DEFECTS)
def test_ink_beyond_the_cell_columns_is_caught_by_r01(scratch, name, cp, rewrite):
    """Ink one column beyond the widened box is still INSIDE the 12-pixel advance,
    so only the cell box can see it: R01 must say 'kana ink columns' (and not
    'outside advance') for Regular, and for Bold where Bold is over its own limit.
    The committed record, on the same lint, is quiet (the twin)."""
    _quiet_twin(scratch, cp, "R01")
    planted = _plant_record(scratch, name, cp, rewrite)
    font = _font_of(planted)
    adv = _int_of("cell_adv_px")
    needles = []
    for weight, (lo, hi) in _weight_limits().items():
        first, last, _rows, _cols = _extent(font, cp, weight)
        if first < lo or last > hi:
            needles.append(
                "U+%04X %s kana ink columns %d..%d outside cell columns %d..%d"
                % (cp, weight, first, last, lo, hi)
            )
    assert needles and "regular" in needles[0], "the plant stays inside Regular's box"
    first, last, _rows, cols = _extent(font, cp, "regular")
    lo, hi = _weight_limits()["regular"]
    assert last > hi and last <= adv - 1, "the plant must stay inside the advance"
    if rewrite is _one_more_column_of_ink:
        assert cols == hi - lo + 2, "the plant is not exactly one column too wide"
    _caught(
        scratch,
        planted,
        "R01",
        needles,
        absent=["U+%04X regular ink columns" % cp],
    )


def test_the_previous_cell_limits_reject_the_refitted_hiragana(scratch):
    """The refit relies on the widening and the lint reads it from the metrics:
    with Regular and Bold lower bounds put back to one column in, the same
    hiragana (U+3042 starts in column 0) are reported by R01 in both weights."""
    edits = []
    for key, (lo, hi) in (
        ("cell_ink_x_regular", _weight_limits()["regular"]),
        ("cell_ink_x_bold", _weight_limits()["bold"]),
    ):
        edits.append(
            (
                "metrics.txt",
                "%s = %d..%d" % (key, lo, hi),
                "%s = %d..%d" % (key, lo + 1, hi),
            )
        )
    planted = plant(scratch, edits)
    needles = [
        "U+%04X %s kana ink columns %d..%d outside cell columns %d..%d"
        % (HIRAGANA_A, w, lo, hi, lo + 1, hi)
        for w, (lo, hi) in _weight_limits().items()
    ]
    _caught(scratch, planted, "R01", needles)


def test_a_nine_by_nine_centred_small_kana_passes_r12(scratch):
    """Twin of the R12 catches: U+3041 is the largest centred small kana the
    contract allows, 9 rows by 9 columns in Regular (10 columns in Bold, which
    adds one), and R12 examines it and is quiet."""
    font = _font_of(SOURCES)
    rows_max = _int_of("small_kana_max_rows")
    cols_max = _int_of("small_kana_centred_max_cols")
    _f, _l, rows, cols = _extent(font, SMALL_A, "regular")
    assert (rows, cols) == (rows_max, cols_max), "U+3041 Regular is not at the limits"
    _f, _l, rows, cols = _extent(font, SMALL_A, "bold")
    assert (rows, cols) == (rows_max, cols_max + 1), "U+3041 Bold is not at its limits"
    _quiet_twin(scratch, SMALL_A, "R12")


def test_a_ten_row_small_kana_is_caught_by_r12(scratch):
    """One row over the limit (10 where 9 are allowed), bottom row and width
    unchanged, so the height check is the only thing that can fire. Bold is
    corrected by a drawn overlay (still 9 rows), so only Regular is over."""
    _quiet_twin(scratch, SMALL_A, "R12")
    rows_max = _int_of("small_kana_max_rows")
    planted = _plant_record(scratch, HIRAGANA_SRC, SMALL_A, _one_more_row_of_ink)
    font = _font_of(planted)
    _f, _l, rows, _cols = _extent(font, SMALL_A, "regular")
    assert rows == rows_max + 1, "the plant is not exactly one row too tall"
    needles = []
    for weight in WEIGHTS:
        _f, _l, rows, _cols = _extent(font, SMALL_A, weight)
        if rows > rows_max:
            needles.append(
                "U+%04X %s small kana is %d rows tall, more than %d"
                % (SMALL_A, weight, rows, rows_max)
            )
    assert needles and "regular" in needles[0]
    _caught(
        scratch,
        planted,
        "R12",
        needles,
        absent=["U+%04X regular small kana bottom row" % SMALL_A],
    )


def test_a_ten_column_centred_small_kana_is_caught_by_r12(scratch):
    """One column over the limit (10 where 9 are allowed in Regular), still
    centred within its tolerance, so the width check is what fires. The limit of
    a weight is the metrics value, plus one in Bold."""
    _quiet_twin(scratch, SMALL_A, "R12")
    cols_max = _int_of("small_kana_centred_max_cols")
    planted = _plant_record(scratch, HIRAGANA_SRC, SMALL_A, _one_more_column_of_ink)
    font = _font_of(planted)
    _f, _l, _rows, cols = _extent(font, SMALL_A, "regular")
    assert cols == cols_max + 1, "the plant is not exactly one column too wide"
    needles = []
    for weight in WEIGHTS:
        limit = cols_max + (1 if weight == "bold" else 0)
        _f, _l, _rows, cols = _extent(font, SMALL_A, weight)
        if cols > limit:
            needles.append(
                "U+%04X %s small kana is %d columns wide, more than %d"
                % (SMALL_A, weight, cols, limit)
            )
    assert needles and "regular" in needles[0]
    _caught(
        scratch,
        planted,
        "R12",
        needles,
        absent=["U+%04X regular small kana is not centred" % SMALL_A],
    )


@pytest.mark.parametrize(
    "key,message",
    [
        pytest.param(
            "small_kana_max_rows",
            "U+%04X regular small kana is %d rows tall, more than %d",
            id="small-kana-rows",
        ),
        pytest.param(
            "small_kana_centred_max_cols",
            "U+%04X regular small kana is %d columns wide, more than %d",
            id="small-kana-columns",
        ),
    ],
)
def test_the_previous_small_kana_limits_reject_the_refitted_small_a(
    scratch, key, message
):
    """The 9 x 9 small kana depend on the widened keys, read from the metrics:
    put the key one lower and the committed U+3041 is reported by R12."""
    now = _int_of(key)
    planted = plant(
        scratch, [("metrics.txt", "%s = %d" % (key, now), "%s = %d" % (key, now - 1))]
    )
    _caught(scratch, planted, "R12", [message % (SMALL_A, now, now - 1)])


HALF_WIDTH = [
    pytest.param("latin-basic.txt", 0x0048, id="latin-H"),
    pytest.param("greek.txt", 0x0394, id="greek-Delta"),
    pytest.param("cyrillic.txt", 0x0416, id="cyrillic-Zhe"),
]


@pytest.mark.parametrize("name,cp", HALF_WIDTH)
def test_a_half_width_glyph_is_still_held_to_its_own_advance(scratch, name, cp):
    """The half-width limit did not move: ink must lie inside the glyph's own
    advance, and the cell box does not apply to it. Cutting the advance to the
    last ink column is reported by R01 as before ('outside advance'), with no
    'kana' wording; the committed glyph is quiet (the twin)."""
    _quiet_twin(scratch, cp, "R01")
    font = _font_of(SOURCES)
    bmp, bb = _ink(font, cp, "regular")
    assert bmp.adv < _int_of("cell_adv_px"), "U+%04X is not half-width" % cp
    cut = bb[2]  # ink reaches column bb[2], so an advance of bb[2] is one short
    planted = _plant_record(
        scratch,
        name,
        cp,
        lambda head, rows: (head.replace("adv=%d" % bmp.adv, "adv=%d" % cut, 1), rows),
    )
    _caught(
        scratch,
        planted,
        "R01",
        [
            "U+%04X regular ink columns %d..%d outside advance %d"
            % (cp, bb[0], bb[2], cut)
        ],
        absent=["U+%04X regular kana ink columns" % cp],
    )


# --------------------------------------------------------------------------
# 7. The lint's own injected-defect controls (lint_controls.py)
# --------------------------------------------------------------------------


def _controls_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(
        "nifen_lint_controls_under_test", FONT_SCRIPTS / "lint_controls.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CONTROLS = _controls_module()


def test_the_control_catalogue_has_not_shrunk():
    """48 controls were delivered with the lint; removing one weakens it."""
    assert len(_CONTROLS.CONTROLS) >= 48


@pytest.mark.parametrize(
    "control", _CONTROLS.CONTROLS, ids=[c[0] for c in _CONTROLS.CONTROLS]
)
def test_each_lint_control_is_caught(scratch, control, capsys):
    """Every control of ``lint_controls.py`` runs on its own, in parallel with the
    others. A control that skipped (its anchor is no longer in the sources) is a
    failure here: the script counts it but still exits 0, which would hide a
    control that stopped testing anything."""
    _CONTROLS.SCRATCH = str(scratch)
    result = _CONTROLS.run(*control)
    assert result is not None, "control %r was skipped: its anchor is gone" % control[0]
    assert result is True, "control %r was NOT caught by the lint" % control[0]


def test_the_control_runner_reports_a_missed_control(monkeypatch, scratch, capsys):
    """The instrument can itself fail: a control whose edit breaks no rule makes
    ``main`` return 1 and print SOME CONTROL MISSED."""
    harmless = (
        "a comment-only edit breaks nothing",
        [("greek.txt", "# Greek block.", "# Greek block, edited.")],
        "R02",
    )
    monkeypatch.setattr(_CONTROLS, "SCRATCH", str(scratch))
    monkeypatch.setattr(_CONTROLS, "CONTROLS", [harmless])
    assert _CONTROLS.main() == 1
    assert "SOME CONTROL MISSED" in capsys.readouterr().out


def test_the_control_runner_passes_when_every_control_is_caught(
    monkeypatch, scratch, capsys
):
    real = next(c for c in _CONTROLS.CONTROLS if c[2] == "R03")
    monkeypatch.setattr(_CONTROLS, "SCRATCH", str(scratch))
    monkeypatch.setattr(_CONTROLS, "CONTROLS", [real])
    assert _CONTROLS.main() == 0
    out = capsys.readouterr().out
    assert "controls run: 1" in out and "skipped (record not in the sources): 0" in out
    assert "ALL CONTROLS CAUGHT" in out


# --------------------------------------------------------------------------
# 8. The name-table scan (SC-VI-BUILD-010-1, font half)
# --------------------------------------------------------------------------

#: One sample per category of the scan, assembled from pieces so that this file
#: does not trip the scans it tests.
UNSAFE_SAMPLES = {
    "authoring-tool name": "Made with Cl" + "aude",
    "vendor name": "by Anthr" + "opic",
    "authorship token": "drawn by an A" + "I model",
    "orchestration id": "AG" + "T" + "-22",
    "workflow id": "O" + "F7",
    "slug": "pixelart-style-" + "refresh",
    "requirement id": "RE" + "C-4",
    "question id": "Q" + "-24",
    "drive path": "C:" + chr(92) + "work",
    "design folder": "design" + "-docs",
    "profile name": "Us" + "uario",
    "home path": "/Us" + "ers/someone",
    "orchestration term": "the ag" + "ent",
    "workflow term": "the jo" + "b",
}


def test_every_category_of_the_scan_has_a_planted_sample():
    """A category added to the scan must come with a sample here."""
    _src, build = _modules()
    labels = {label for label, _pattern in build.UNSAFE}
    assert labels == set(
        UNSAFE_SAMPLES
    ), "samples missing for %s, unused samples %s" % (
        sorted(labels - set(UNSAFE_SAMPLES)),
        sorted(set(UNSAFE_SAMPLES) - labels),
    )


def test_the_name_scan_examines_records_and_finds_none_in_the_built_fonts():
    from fontTools.ttLib import TTFont

    _src, build = _modules()
    paths = {w: str(FONT_DIR / FONT_FILES[w]) for w in WEIGHTS}
    expected = sum(len(TTFont(p)["name"].names) for p in paths.values())
    examined, violations = build.name_table_scan(paths)
    assert examined == expected > 0
    assert violations == []


@pytest.mark.parametrize("label", sorted(UNSAFE_SAMPLES))
def test_the_name_scan_reports_a_planted_violation_in_a_copy(scratch, label):
    """SC-VI-BUILD-010-1 control: the committed font is copied, one name record is
    replaced, and the scan must report that record under the right category."""
    from fontTools.ttLib import TTFont

    _src, build = _modules()
    font = TTFont(str(FONT_DIR / FONT_FILES["regular"]))
    font["name"].setName(UNSAFE_SAMPLES[label], 0, 3, 1, 0x409)
    planted = scratch / "planted.ttf"
    font.save(str(planted))
    examined, violations = build.name_table_scan({"regular": str(planted)})
    assert examined > 0
    assert any("name ID 0" in v and label in v for v in violations), violations


def test_the_name_scan_stays_quiet_on_a_clean_replacement(scratch):
    """Control for the control: a harmless replacement is not reported."""
    from fontTools.ttLib import TTFont

    _src, build = _modules()
    font = TTFont(str(FONT_DIR / FONT_FILES["regular"]))
    font["name"].setName("Copyright 2026 Someone Else", 0, 3, 1, 0x409)
    planted = scratch / "clean.ttf"
    font.save(str(planted))
    examined, violations = build.name_table_scan({"regular": str(planted)})
    assert examined > 0 and violations == []


def test_a_build_that_scanned_no_name_record_fails(monkeypatch, scratch):
    """``--build`` must not pass over zero examined records."""
    _src, build = _modules()
    monkeypatch.setattr(build, "name_table_scan", lambda paths: (0, []))
    args = type("A", (), {"src": str(SOURCES), "out": str(scratch / "out")})()
    assert build.cmd_build(args) == 1


def test_a_build_with_a_reported_name_violation_fails(monkeypatch, scratch):
    _src, build = _modules()
    monkeypatch.setattr(
        build, "name_table_scan", lambda paths: (3, ["regular name ID 0 contains x"])
    )
    args = type("A", (), {"src": str(SOURCES), "out": str(scratch / "out")})()
    assert build.cmd_build(args) == 1


# --------------------------------------------------------------------------
# 9. The specimen scripts: argument contract
# --------------------------------------------------------------------------

SPECIMEN_SCRIPTS = ["render_specimen_source.py", "render_specimen_qt.py"]


def _palette(path: Path) -> Path:
    roles = {
        "surface": "#FFFFFF",
        "text": "#000000",
        "accent": "#336699",
        "accent_text": "#FFFFFF",
        "background": "#EEEEEE",
        "border": "#999999",
        "disabled_text": "#888888",
        "focus": "#CC3300",
        "frame_edge": "#555555",
        "hover": "#DDDDDD",
        "pressed": "#CCCCCC",
        "title_fill": "#224466",
        "title_text": "#FFFFFF",
    }
    import json

    path.write_text(json.dumps({"light": roles, "dark": roles}), encoding="utf-8")
    return path


@pytest.mark.parametrize("script", SPECIMEN_SCRIPTS)
def test_a_specimen_script_documents_out_and_palette(scratch, script):
    res = run_font(script, ["--help"], scratch)
    assert res.returncode == 0, res.text
    assert "--out" in res.stdout and "--palette" in res.stdout


@pytest.mark.parametrize("script", SPECIMEN_SCRIPTS)
@pytest.mark.parametrize(
    "args,missing",
    [
        ([], "--out"),
        (["--palette", "p.json"], "--out"),
        (["--out", "o"], "--palette"),
    ],
    ids=["no-arguments", "palette-only", "out-only"],
)
def test_a_specimen_script_requires_out_and_palette(scratch, script, args, missing):
    res = run_font(script, args, scratch)
    assert res.returncode == 2, res.text
    assert "required" in res.stderr and missing in res.stderr


@pytest.mark.parametrize("script", SPECIMEN_SCRIPTS)
def test_a_specimen_script_rejects_an_unknown_flag(scratch, script):
    res = run_font(
        script, ["--out", scratch / "o", "--palette", "p", "--bogus"], scratch
    )
    assert res.returncode == 2, res.text


@pytest.mark.parametrize("script", SPECIMEN_SCRIPTS)
def test_a_specimen_script_fails_on_a_missing_palette_file(scratch, script):
    extra = ["--platform", "offscreen"] if script.endswith("_qt.py") else []
    res = run_font(
        script,
        ["--out", scratch / "o", "--palette", scratch / "none.json", *extra],
        scratch,
    )
    assert res.returncode != 0, res.text
    assert "sheets written" not in res.stdout


def test_the_source_specimen_script_fails_on_a_palette_without_a_mode(scratch):
    import json

    bad = scratch / "bad.json"
    bad.write_text(json.dumps({"light": {"surface": "#FFFFFF"}}), encoding="utf-8")
    res = run_font(
        "render_specimen_source.py",
        ["--out", scratch / "o", "--palette", bad, "--work", scratch / "w"],
        scratch,
    )
    assert res.returncode != 0, res.text


def test_the_qt_specimen_script_fails_when_the_font_cannot_be_registered(scratch):
    """An empty font folder makes Qt refuse the fonts: exit 1, no sheets claimed."""
    palette = _palette(scratch / "palette.json")
    fonts = scratch / "no-fonts"
    fonts.mkdir()
    res = run_font(
        "render_specimen_qt.py",
        [
            "--out",
            scratch / "o",
            "--palette",
            palette,
            "--font-dir",
            fonts,
            "--platform",
            "offscreen",
        ],
        scratch,
    )
    assert res.returncode == 1, res.text
    assert "-> id -1" in res.stdout
    assert "Traceback" not in res.stderr, "the refusal must be clean, not a crash"


# --------------------------------------------------------------------------
# 9. A legacy console code page (REQ-VI-BUILD-003, REQ-VI-BUILD-010)
# --------------------------------------------------------------------------
#
# Regression for a defect that only a CI runner showed. A Windows pipe is often
# cp1252; the R08 report of the lint used to print ``chr(c)`` of Greek, Cyrillic
# and kana code points, which that code page cannot encode, so the lint died with
# UnicodeEncodeError on its own report, and the R09 / R12 / R13 lines after it were
# never printed. ``lint_controls.py`` then threw the child's stderr away, so the
# crash read as "control not caught" with no cause. Every other test of this
# module forces UTF-8 on the child (``_child_env``), which is exactly why none of
# them could see it. These run the scripts as the CI console runs them.

#: What the failing runner had: a non-UTF-8 stream encoding, UTF-8 mode off.
LEGACY_CONSOLE = {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1252"}
LEGACY_CODEC = "cp1252"


def run_font_legacy_console(
    script: str, args: Sequence[object], scratch: Path, *, timeout: int = 600
) -> Run:
    """Run a font script with the child's streams on a legacy code page.

    The output is decoded with the SAME code page the child wrote it in, so what
    the assertions read is what a console would have shown.
    """
    done = subprocess.run(
        [sys.executable, "-B", str(FONT_SCRIPTS / script), *[str(a) for a in args]],
        cwd=str(TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding=LEGACY_CODEC,
        errors="replace",
        timeout=timeout,
        env=_child_env(scratch, LEGACY_CONSOLE),
    )
    return Run(done.returncode, done.stdout, done.stderr)


def run_driver_legacy_console(
    driver: str, args: Sequence[object], scratch: Path, *, timeout: int = 600
) -> Run:
    """Run a short driver program (``python -c``) on the legacy console.

    Same environment and decoding as ``run_font_legacy_console``; the driver loads
    a font script by path (``sys.argv[1]``) so it can run a SLICE of it.
    """
    done = subprocess.run(
        [sys.executable, "-B", "-c", driver, *[str(a) for a in args]],
        cwd=str(TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding=LEGACY_CODEC,
        errors="replace",
        timeout=timeout,
        env=_child_env(scratch, LEGACY_CONSOLE),
    )
    return Run(done.returncode, done.stdout, done.stderr)


def child_report(res: Run, what: str, tail: int = 25) -> str:
    """An assertion message that always carries the child's stderr.

    A failure that hides why the child died is the defect this section guards, so
    the message states the exit code, the whole of stderr (or that it was empty)
    and the last lines of stdout.
    """
    err = res.stderr.strip()
    lines = res.stdout.rstrip().splitlines()
    return "\n".join(
        [
            "%s (legacy console %s)" % (what, LEGACY_CODEC),
            "child exit code: %d" % res.returncode,
            "child stderr: %s" % (err if err else "(empty)"),
            "child stdout, last %d of %d lines:" % (min(tail, len(lines)), len(lines)),
            *("  | " + ln for ln in lines[-tail:]),
        ]
    )


def test_the_legacy_console_environment_really_is_a_legacy_console(scratch):
    """Control of the instrument: without it the tests below could pass on a
    UTF-8 stream and prove nothing. The child must report the code page, and the
    characters the lint reports on must not be encodable in it."""
    done = subprocess.run(
        [sys.executable, "-B", "-c", "import sys; print(sys.stdout.encoding)"],
        capture_output=True,
        text=True,
        timeout=60,
        env=_child_env(scratch, LEGACY_CONSOLE),
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().lower().replace("-", "") in (
        "cp1252",
        "windows1252",
    ), done.stdout
    for sample in ("Ω", "Я", "い"):  # Greek, Cyrillic, hiragana
        with pytest.raises(UnicodeEncodeError):
            sample.encode(LEGACY_CODEC)


def test_the_failure_message_carries_the_childs_stderr_or_says_it_was_empty():
    """The message is the only thing a reader of a red CI log has."""
    crashed = Run(
        1, "R08 ...\n", "Traceback (most recent call last):\nUnicodeEncodeError"
    )
    text = child_report(crashed, "the lint")
    assert "UnicodeEncodeError" in text and "child exit code: 1" in text
    quiet = child_report(Run(0, "R08 ...\n", ""), "the lint")
    assert "child stderr: (empty)" in quiet


def test_lint_runs_to_the_end_on_a_legacy_console(scratch):
    """The lint exits 0 with an empty stderr and prints the rules that follow R08
    (R09, R12, R13), each over a non-zero denominator, on a cp1252 stream."""
    res = run_font_legacy_console(BUILD, ["--lint"], scratch)
    assert res.returncode == 0, child_report(res, "--lint did not exit 0")
    assert res.stderr == "", child_report(res, "--lint wrote to stderr")
    assert "Traceback" not in res.text, child_report(res, "--lint crashed")
    rules = lint_rules(res.stdout)
    for code in ("R08", "R09", "R12", "R13"):
        assert code in rules, child_report(res, "%s is missing from the report" % code)
        examined, violations = rules[code]
        assert examined > 0, child_report(res, "%s examined nothing" % code)
        assert violations == 0, child_report(res, "%s reports violations" % code)
    for header in ("R09 ", "R12 ", "R13 "):
        assert header in res.stdout, child_report(res, "no %r header" % header)
    assert "lint violations: 0" in res.stdout, child_report(
        res, "the closing verdict line is missing"
    )


#: The lint controls are run as SHARDS, each in its own child process on the legacy
#: console. One child running all of them took ~85 s idle, past the CI per-test cap
#: (``--timeout=120``) on a loaded Windows runner (CI run 38074754008). The cap is a
#: gate and stays; the work is split so no test item is near it. What each shard
#: guards is unchanged: ``lint_controls.main()`` runs to the end on a cp1252 stream,
#: exits 0, writes nothing to stderr and says how many controls it ran and skipped.
#: That every shard together is the WHOLE catalogue is asserted separately, below.
CONTROL_SHARDS = 16

#: Run by a child on the legacy console: load ``lint_controls.py`` by path, keep one
#: slice of its catalogue and call its own ``main``. Pure ASCII, so the command line
#: itself cannot be what a legacy code page breaks.
_SHARD_DRIVER = """
import importlib.util, sys
sys.dont_write_bytecode = True
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
spec = importlib.util.spec_from_file_location("nifen_lint_controls_shard", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print("catalogue size: %d" % len(module.CONTROLS))
module.CONTROLS = module.CONTROLS[lo:hi]
sys.exit(module.main())
"""

#: Same, but the control never passes and its child output carries Greek, Cyrillic
#: and kana, which is what ``show_child_output`` must print without dying.
_MISSED_DRIVER = r"""
import importlib.util, sys, types
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("nifen_lint_controls_missed", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
child = types.SimpleNamespace(
    returncode=1,
    stdout="R08  Greek, Cyrillic, kana \u03a9 \u042f \u3044\nlint violations: 1\n",
    stderr="\u03a9 \u042f \u3044 on stderr\n",
)
def missed(name, *rest):
    print("%s  expected rule R08 flagged: NO" % name)
    module.show_child_output(child)
    return False
module.run = missed
module.CONTROLS = [("a missed control",)]
sys.exit(module.main())
"""


def _shard_bounds(total: int, shards: int) -> List[Tuple[int, int]]:
    """Contiguous ``[lo, hi)`` slices of ``range(total)``; none is empty."""
    size = -(-total // shards)
    return [(lo, min(lo + size, total)) for lo in range(0, total, size)]


_SHARDS = _shard_bounds(len(_CONTROLS.CONTROLS), CONTROL_SHARDS)


def test_the_control_shards_are_the_whole_catalogue_once():
    """The denominator of the sharded run: the slices are disjoint, in order, and
    together cover every control, so the shards below run exactly as many controls
    as the catalogue holds (and no fewer than the 48 delivered with the lint)."""
    total = len(_CONTROLS.CONTROLS)
    assert total >= 48
    assert _SHARDS and _SHARDS[0][0] == 0 and _SHARDS[-1][1] == total
    for (_, end), (start, _) in zip(_SHARDS, _SHARDS[1:]):
        assert end == start, "shards overlap or leave a gap at %d / %d" % (end, start)
    assert all(lo < hi for lo, hi in _SHARDS)
    assert sum(hi - lo for lo, hi in _SHARDS) == total
    assert len(_SHARDS) <= CONTROL_SHARDS


@pytest.mark.parametrize(
    "lo,hi", _SHARDS, ids=["controls-%d-%d" % bounds for bounds in _SHARDS]
)
def test_lint_controls_run_to_the_end_on_a_legacy_console(scratch, lo, hi):
    """Every control of the shard is caught, the runner says so, nothing reaches
    stderr, and the runner's own count is the shard's size with none skipped."""
    res = run_driver_legacy_console(
        _SHARD_DRIVER, [FONT_SCRIPTS / "lint_controls.py", lo, hi], scratch
    )
    assert res.returncode == 0, child_report(res, "lint_controls did not exit 0")
    assert res.stderr == "", child_report(res, "lint_controls wrote to stderr")
    assert "ALL CONTROLS CAUGHT" in res.stdout, child_report(
        res, "lint_controls did not report every control caught"
    )
    assert "SOME CONTROL MISSED" not in res.stdout, child_report(
        res, "lint_controls reported a missed control"
    )
    size = re.search(r"catalogue size: (\d+)", res.stdout)
    assert size and int(size[1]) == len(_CONTROLS.CONTROLS), child_report(
        res, "the child read a different catalogue than the parent"
    )
    ran = re.search(
        r"controls run: (\d+)\s+skipped \(record not in the sources\): (\d+)",
        res.stdout,
    )
    assert ran, child_report(res, "the controls denominator is missing")
    assert int(ran[1]) == hi - lo and int(ran[2]) == 0, child_report(
        res,
        "controls run / skipped is %s / %s, wanted %d / 0" % (ran[1], ran[2], hi - lo),
    )


def test_a_missed_control_with_non_ascii_child_output_is_reported_on_a_legacy_console(
    scratch,
):
    """The path the healthy shards never reach: a control is NOT caught and the
    runner must print the child's Greek, Cyrillic and kana lines on a cp1252
    stream. It must report the miss (exit 1, SOME CONTROL MISSED), show the
    characters as escapes, and not die with UnicodeEncodeError on its own report."""
    res = run_driver_legacy_console(
        _MISSED_DRIVER, [FONT_SCRIPTS / "lint_controls.py"], scratch
    )
    assert res.returncode == 1, child_report(res, "the miss was not reported by exit 1")
    assert "Traceback" not in res.text, child_report(res, "the runner crashed")
    assert "UnicodeEncodeError" not in res.text, child_report(res, "encoding error")
    assert res.stderr == "", child_report(res, "the runner wrote to stderr")
    assert "SOME CONTROL MISSED" in res.stdout, child_report(
        res, "the miss was swallowed"
    )
    for escape in (r"\u03a9", r"\u042f", r"\u3044"):
        assert escape in res.stdout, child_report(
            res, "%s is not shown as an escape in the report" % escape
        )


# --------------------------------------------------------------------------
# 10. The Reserved Font Name and the donor line
#     (SC-VI-BUILD-005-2, SC-VI-BUILD-011-2)
# --------------------------------------------------------------------------
#
# The build composes the copyright record (name ID 0) from metrics.txt, but no
# rule of the lint and no scan of the build asks whether the typeface's own line
# ends with the Reserved Font Name clause. These tests ask it of the COMMITTED
# artefacts (OFL.txt, name ID 0 of both fonts, FONTLOG.txt) with predicates
# written here, and show every predicate catching its omission in a COPY: the
# artefacts are only read, a plant is written to the per-test scratch folder.
#
# The expected strings are literals on purpose. A test that took them from
# metrics.txt would pass whatever metrics.txt said; one test below compares the
# literals with metrics.txt so that a change of wording in the sources is
# reported as a change, not absorbed.

#: The declaration, as the user ruled it, ending the typeface's own line.
RFN_CLAUSE = 'with Reserved Font Name "Nifen Art".'
#: The Ark Pixel Font line, kept as its author wrote it (no clause attached).
DONOR_LINE = "Copyright (c) 2021, TakWolf (https://takwolf.com)."

#: The three places SC-VI-BUILD-005-2 names; each font is read at every one of
#: its name ID 0 records (Windows and Macintosh), not at the first one only.
RFN_SOURCES = ("OFL.txt", "regular", "bold")

_COPYRIGHT_AT = re.compile(r"(?<=\S) (?=Copyright \(c\) \d{4},)")
_FONTLOG_DECLARATION = re.compile(r'Reserved Font Name:?\s+"Nifen Art"')
_FONTLOG_DONOR_WITH_CLAUSE = re.compile(
    re.escape(DONOR_LINE[:-2]) + r"\)?[.,]?\s*,?\s*with Reserved Font Name"
)

#: (label, kind, text): kind "ofl" is a file, kind "name0" is one name record.
Record = Tuple[str, str, str]


def _read_utf8(path: Path) -> str:
    """Bytes, then an explicit decode: no dependence on the console code page."""
    return path.read_bytes().decode("utf-8")


def read_rfn_records(ofl: Path, fonts: Dict[str, Path]) -> List[Record]:
    """OFL.txt plus every name ID 0 record of each font, as ``Record`` tuples."""
    from fontTools.ttLib import TTFont

    out: List[Record] = [("OFL.txt", "ofl", _read_utf8(ofl))]
    for weight in WEIGHTS:
        with TTFont(str(fonts[weight])) as font:
            for rec in font["name"].names:
                if rec.nameID == 0:
                    label = "%s (platform %d)" % (weight, rec.platformID)
                    out.append((label, "name0", rec.toUnicode()))
    return out


def _copyright_lines(kind: str, text: str) -> List[str]:
    if kind == "ofl":
        header = re.split(r"\r?\n[ \t]*\r?\n", text, maxsplit=1)[0]
        return header.splitlines()
    return _COPYRIGHT_AT.split(text)


def own_line_findings(label: str, kind: str, text: str, holder: str) -> List[str]:
    """The typeface's own line (the second) must end with the clause."""
    lines = _copyright_lines(kind, text)
    if len(lines) != 2:
        return [
            "%s: expected 2 copyright lines (Ark Pixel Font, then the typeface), "
            "found %d" % (label, len(lines))
        ]
    own = lines[1]
    out = []
    if not own.startswith("Copyright (c) 20") or holder not in own:
        out.append("%s: the second line is not the typeface's own: %r" % (label, own))
    if not own.endswith(RFN_CLAUSE):
        out.append(
            "%s: the typeface's own line does not end with %r: %r"
            % (label, RFN_CLAUSE, own[-70:])
        )
    return out


def donor_line_findings(label: str, kind: str, text: str) -> List[str]:
    """The Ark Pixel Font line (the first) is unchanged, with no clause on it."""
    lines = _copyright_lines(kind, text)
    if len(lines) != 2:
        return [
            "%s: expected 2 copyright lines (Ark Pixel Font, then the typeface), "
            "found %d" % (label, len(lines))
        ]
    donor = lines[0]
    if "Reserved Font Name" in donor:
        return [
            "%s: a Reserved Font Name is attached to the donor line: %r"
            % (label, donor)
        ]
    if donor != DONOR_LINE:
        return [
            "%s: the donor line is not kept as its author wrote it: %r" % (label, donor)
        ]
    return []


def fontlog_findings(text: str) -> List[str]:
    out = []
    if not _FONTLOG_DECLARATION.search(text):
        out.append('FONTLOG.txt does not record the Reserved Font Name "Nifen Art"')
    if _FONTLOG_DONOR_WITH_CLAUSE.search(text):
        out.append("FONTLOG.txt attaches a Reserved Font Name to the donor line")
    if DONOR_LINE not in text:
        out.append("FONTLOG.txt does not state the donor line")
    return out


def rfn_verdict(records: Sequence[Record], holder: str) -> Tuple[int, List[str]]:
    """``(records examined, findings)``; examining nothing is itself a finding."""
    findings: List[str] = []
    for label, kind, text in records:
        findings += own_line_findings(label, kind, text, holder)
        findings += donor_line_findings(label, kind, text)
    if not records:
        findings.append("no copyright record was examined")
    return len(records), findings


def _committed_records() -> List[Record]:
    return read_rfn_records(
        FONT_DIR / "OFL.txt", {w: FONT_DIR / FONT_FILES[w] for w in WEIGHTS}
    )


def _holder() -> str:
    return _metrics()["copyright_holder"]


def _of_source(records: Sequence[Record], source: str) -> List[Record]:
    return [r for r in records if r[0].split(" ")[0] == source]


# ----- the committed artefacts ---------------------------------------------


def test_sc_vi_build_005_2_the_check_examines_the_three_places():
    """The denominator: OFL.txt and both fonts, and every font has a record."""
    records = _committed_records()
    seen = {r[0].split(" ")[0] for r in records}
    assert seen == set(RFN_SOURCES), seen
    for weight in WEIGHTS:
        assert _of_source(records, weight), (
            "no name ID 0 record in the %s font" % weight
        )
    examined, findings = rfn_verdict(records, _holder())
    assert examined >= len(RFN_SOURCES) and findings == [], findings


def test_the_expected_strings_agree_with_the_metrics_they_are_built_from():
    metrics = _metrics()
    assert metrics["copyright_rfn_clause"] == RFN_CLAUSE
    assert metrics["copyright_prior_line_1"] == DONOR_LINE


def test_sc_vi_build_005_2_ofl_line_two_ends_with_the_clause():
    lines = _copyright_lines("ofl", _read_utf8(FONT_DIR / "OFL.txt"))
    assert len(lines) == 2, lines
    assert lines[0] == DONOR_LINE
    assert lines[1].startswith("Copyright (c) 20") and _holder() in lines[1]
    assert lines[1].endswith(RFN_CLAUSE), lines[1]


@pytest.mark.parametrize("weight", WEIGHTS)
def test_sc_vi_build_005_2_name_id_0_of_the_font_carries_the_clause(weight):
    records = _of_source(_committed_records(), weight)
    assert records, "no name ID 0 record"
    for label, kind, text in records:
        assert own_line_findings(label, kind, text, _holder()) == []
        assert text.endswith(RFN_CLAUSE), (label, text)
        assert text.count("Reserved Font Name") == 1, (label, text)


@pytest.mark.parametrize("source", RFN_SOURCES)
def test_sc_vi_build_005_2_the_clause_is_not_on_the_donor_line(source):
    records = _of_source(_committed_records(), source)
    assert records
    for label, kind, text in records:
        assert donor_line_findings(label, kind, text) == []
        assert _copyright_lines(kind, text)[0] == DONOR_LINE


def test_sc_vi_build_005_2_fontlog_records_the_declaration():
    text = _read_utf8(FONT_DIR / "FONTLOG.txt")
    assert fontlog_findings(text) == []
    assert _FONTLOG_DECLARATION.search(text)


# ----- the twins: the same predicates against a planted omission ------------


def _plant(text: str, how: str) -> str:
    """One omission or misplacement of the clause, anchored to appear once."""
    assert text.count(RFN_CLAUSE) == 1, text.count(RFN_CLAUSE)
    assert text.count(DONOR_LINE) == 1, text.count(DONOR_LINE)
    attached = DONOR_LINE[:-1] + ", " + RFN_CLAUSE
    own_tail = ", " + RFN_CLAUSE
    if how == "removed":
        out = text.replace(own_tail, ".")
    elif how == "other-name":
        out = text.replace('"Nifen Art".', '"Pixel Art".')
    elif how == "lowercase":
        out = text.replace("with Reserved Font Name", "with reserved font name")
    elif how == "trailing-words":
        out = text.replace(RFN_CLAUSE, RFN_CLAUSE + " Extra words.")
    elif how == "moved-to-donor":
        out = text.replace(own_tail, ".").replace(DONOR_LINE, attached)
    elif how == "also-on-donor":
        out = text.replace(DONOR_LINE, attached)
    else:  # pragma: no cover - a typo in the parametrisation
        raise AssertionError(how)
    assert out != text, "the plant %r changed nothing" % how
    return out


#: how -> (the own-line check must report, the donor-line check must report)
PLANTS = {
    "removed": (True, False),
    "other-name": (True, False),
    "lowercase": (True, False),
    "trailing-words": (True, False),
    "moved-to-donor": (True, True),
    "also-on-donor": (False, True),
}


def _planted_copy(scratch: Path, source: str, how: Optional[str]) -> List[Record]:
    """Copy the artefacts into the scratch folder, plant ``how`` (or nothing) in
    the copy of ``source``, and read the copies with the committed run's reader."""
    from fontTools.ttLib import TTFont

    ofl = scratch / "OFL.txt"
    ofl.write_bytes((FONT_DIR / "OFL.txt").read_bytes())
    fonts = {}
    for weight in WEIGHTS:
        fonts[weight] = scratch / FONT_FILES[weight]
        shutil.copyfile(FONT_DIR / FONT_FILES[weight], fonts[weight])
    if how is not None and source == "OFL.txt":
        ofl.write_bytes(_plant(_read_utf8(ofl), how).encode("utf-8"))
    elif how is not None:
        with TTFont(str(FONT_DIR / FONT_FILES[source])) as font:
            for rec in list(font["name"].names):
                if rec.nameID == 0:
                    font["name"].setName(
                        _plant(rec.toUnicode(), how),
                        0,
                        rec.platformID,
                        rec.platEncID,
                        rec.langID,
                    )
            font.save(str(fonts[source]))
    return read_rfn_records(ofl, fonts)


@pytest.mark.parametrize("source", RFN_SOURCES)
def test_sc_vi_build_005_2_control_an_unplanted_copy_is_clean(scratch, source):
    """The control of the controls: the copy-and-read path invents no finding."""
    examined, findings = rfn_verdict(_planted_copy(scratch, source, None), _holder())
    assert examined >= len(RFN_SOURCES) and findings == [], findings


@pytest.mark.parametrize("how", sorted(PLANTS))
@pytest.mark.parametrize("source", RFN_SOURCES)
def test_sc_vi_build_005_2_control_a_planted_omission_is_reported(scratch, source, how):
    """SC-VI-BUILD-005-2: the declaration removed (or misplaced) in any one of the
    three places is reported, and only by the predicate it concerns."""
    records = _planted_copy(scratch, source, how)
    holder = _holder()
    wants_own, wants_donor = PLANTS[how]
    hit = _of_source(records, source)
    assert hit, "the planted record was not read back"
    own = [f for r in hit for f in own_line_findings(r[0], r[1], r[2], holder)]
    donor = [f for r in hit for f in donor_line_findings(r[0], r[1], r[2])]
    assert bool(own) == wants_own, (how, own)
    assert bool(donor) == wants_donor, (how, donor)
    # the two places left alone stay clean: the plant is the only cause
    others = [r for r in records if r[0].split(" ")[0] != source]
    assert rfn_verdict(others, holder)[1] == []
    examined, findings = rfn_verdict(records, holder)
    assert examined >= len(RFN_SOURCES) and findings, "the plant was not reported"


@pytest.mark.parametrize("weight", WEIGHTS)
def test_sc_vi_build_005_2_control_a_clause_missing_from_one_platform_record_only(
    scratch, weight
):
    """A font can carry the clause in its Windows record and not in the Macintosh
    one; reading only the first record would pass it."""
    from fontTools.ttLib import TTFont

    with TTFont(str(FONT_DIR / FONT_FILES[weight])) as font:
        platforms = {r.platformID for r in font["name"].names if r.nameID == 0}
        assert platforms == {1, 3}, platforms
        for rec in list(font["name"].names):
            if rec.nameID == 0 and rec.platformID == 1:
                font["name"].setName(
                    _plant(rec.toUnicode(), "removed"), 0, 1, rec.platEncID, rec.langID
                )
        font.save(str(scratch / FONT_FILES[weight]))
    other = [w for w in WEIGHTS if w != weight][0]
    shutil.copyfile(FONT_DIR / FONT_FILES[other], scratch / FONT_FILES[other])
    records = read_rfn_records(
        FONT_DIR / "OFL.txt", {w: scratch / FONT_FILES[w] for w in WEIGHTS}
    )
    findings = rfn_verdict(_of_source(records, weight), _holder())[1]
    assert findings and all("platform 1" in f for f in findings), findings
    kept = [r for r in records if "platform 3" in r[0] or r[0].startswith("OFL")]
    assert rfn_verdict(kept, _holder())[1] == []


def test_sc_vi_build_005_2_control_examining_nothing_is_a_failure():
    examined, findings = rfn_verdict([], "anyone")
    assert examined == 0 and findings == ["no copyright record was examined"]


@pytest.mark.parametrize("how", ["removed", "other-name", "attached-to-donor"])
def test_sc_vi_build_005_2_control_a_fontlog_without_the_declaration_is_reported(how):
    text = _read_utf8(FONT_DIR / "FONTLOG.txt")
    assert fontlog_findings(text) == [], "the committed FONTLOG must be clean first"
    if how == "removed":
        planted = _FONTLOG_DECLARATION.sub("Font name", text)
        needle = "does not record"
    elif how == "other-name":
        planted = _FONTLOG_DECLARATION.sub('Reserved Font Name: "Pixel Art"', text)
        needle = "does not record"
    else:
        assert text.count(DONOR_LINE) >= 1
        planted = text.replace(DONOR_LINE, DONOR_LINE[:-1] + ", " + RFN_CLAUSE)
        needle = "attaches"
    assert planted != text
    findings = fontlog_findings(planted)
    assert any(needle in f for f in findings), findings


# --------------------------------------------------------------------------
# 11. A name ID 0 omission planted in the BUILT font (SC-VI-BUILD-011-2)
# --------------------------------------------------------------------------
#
# The existing control removes the donor line from metrics.txt, which only shows
# that the build and the scan agree on what the sources say. These cases build
# the fonts into scratch, change name ID 0 of the BUILT file, and show that the
# name-record check of the build (``name0_scan``) reports the weight it was
# planted in, and that ``--build`` itself ends with a violation and exit 1.


@pytest.fixture(scope="module")
def pristine_build(tmp_path_factory):
    """Both fonts built once into scratch by the real ``--build`` command."""
    root = os.environ.get("ORCH_TEST_TMP")
    if root:
        base = Path(root) / "asset-pipeline-nifen"
        base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="p-", dir=str(base)))
    else:
        folder = tmp_path_factory.mktemp("nifen-pristine")
    out = folder / "built"
    res = run_font(BUILD, ["--build", "--out", out], folder)
    assert res.returncode == 0, res.text
    paths = {w: out / FONT_FILES[w] for w in WEIGHTS}
    assert all(p.is_file() for p in paths.values())
    yield paths
    shutil.rmtree(folder)


def _rewrite_name0(src: Path, dst: Path, rewrite) -> int:
    """Save a copy of ``src`` whose every name ID 0 record is ``rewrite(text)``."""
    from fontTools.ttLib import TTFont

    changed = 0
    with TTFont(str(src)) as font:
        for rec in list(font["name"].names):
            if rec.nameID == 0:
                new = rewrite(rec.toUnicode())
                assert new != rec.toUnicode(), "the rewrite changed nothing"
                font["name"].setName(new, 0, rec.platformID, rec.platEncID, rec.langID)
                changed += 1
        font.save(str(dst))
    assert changed >= 1
    return changed


def _donor_removed(text: str) -> str:
    assert text.count(DONOR_LINE + " ") == 1
    return text.replace(DONOR_LINE + " ", "")


def _donor_altered(text: str) -> str:
    assert text.count("(c) 2021, TakWolf") == 1
    return text.replace("(c) 2021, TakWolf", "(c) 2022, TakWolf")


def _donor_after_own(text: str) -> str:
    assert text.startswith(DONOR_LINE + " Copyright (c) 2026")
    return text[len(DONOR_LINE) + 1 :] + " " + DONOR_LINE


NAME0_PLANTS = {
    "donor-line-removed": _donor_removed,
    "donor-line-altered": _donor_altered,
    "donor-line-after-the-typefaces-line": _donor_after_own,
}


def _sources_of_the_build():
    nifen_src, _build = _modules()
    return nifen_src.parse_sources(str(SOURCES))


def test_name0_scan_is_quiet_on_the_fresh_build_and_the_record_holds_the_line(
    pristine_build,
):
    """The positive control: the planted cases below start from this state."""
    from fontTools.ttLib import TTFont

    _src, build = _modules()
    for weight in WEIGHTS:
        with TTFont(str(pristine_build[weight])) as font:
            record = font["name"].getDebugName(0)
        assert record.startswith(DONOR_LINE + " Copyright (c) 2026"), record
    paths = {w: str(p) for w, p in pristine_build.items()}
    assert build.name0_scan(paths, _sources_of_the_build()) == []


@pytest.mark.parametrize("plant", sorted(NAME0_PLANTS))
@pytest.mark.parametrize("weight", WEIGHTS)
def test_sc_vi_build_011_2_name0_scan_reports_a_planted_name_id_0_omission(
    scratch, pristine_build, weight, plant
):
    """SC-VI-BUILD-011-2: the donor line is removed, altered or reordered in name
    ID 0 of ONE built font; the scan reports that weight and only that weight."""
    _src, build = _modules()
    paths = {}
    for w in WEIGHTS:
        paths[w] = scratch / FONT_FILES[w]
        if w == weight:
            _rewrite_name0(pristine_build[w], paths[w], NAME0_PLANTS[plant])
        else:
            shutil.copyfile(pristine_build[w], paths[w])
    found = build.name0_scan(
        {w: str(p) for w, p in paths.items()}, _sources_of_the_build()
    )
    assert len(found) == 1, found
    assert found[0].startswith("%s name ID 0 does not state" % weight), found
    assert DONOR_LINE in found[0], found


@pytest.mark.parametrize("weight", WEIGHTS)
def test_sc_vi_build_011_2_a_build_with_the_donor_line_lost_from_name_id_0_fails(
    monkeypatch, capsys, scratch, weight
):
    """End to end through ``--build``'s own function: the fonts are built, the
    donor line is then cut out of name ID 0 of one BUILT file, and the build's
    name-record check turns that into a VIOLATION and exit status 1."""
    _src, build = _modules()
    real_build_all = build.build_all

    def build_all_then_damage(srcs, font, out_dir):
        paths = real_build_all(srcs, font, out_dir)
        _rewrite_name0(Path(paths[weight]), Path(paths[weight]), _donor_removed)
        return paths

    args = type("A", (), {"src": str(SOURCES), "out": str(scratch / "out")})()
    monkeypatch.setattr(build, "build_all", build_all_then_damage)
    status = build.cmd_build(args)
    shown = capsys.readouterr().out
    assert status == 1, shown
    assert "VIOLATION %s name ID 0 does not state" % weight in shown, shown
    other = [w for w in WEIGHTS if w != weight][0]
    assert "VIOLATION %s name ID 0" % other not in shown, shown


def test_sc_vi_build_011_2_the_same_build_without_the_damage_passes(capsys, scratch):
    """The control of the end-to-end case: undamaged, the build exits 0."""
    _src, build = _modules()
    args = type("A", (), {"src": str(SOURCES), "out": str(scratch / "out")})()
    status = build.cmd_build(args)
    shown = capsys.readouterr().out
    assert status == 0, shown
    assert "public-safe violations: 0" in shown and "VIOLATION" not in shown, shown
