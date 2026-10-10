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
                "hiragana.txt",
                "glyph U+3083 adv=12 x=1 cell=full ext=free top=7",
                "glyph U+3083 adv=12 x=1 cell=full ext=free top=8",
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
