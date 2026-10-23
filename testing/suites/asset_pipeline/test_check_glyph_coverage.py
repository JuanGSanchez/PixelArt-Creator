# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Contract tests of ``scripts/font/check_glyph_coverage.py`` (the coverage gate).

The subject is the checker that compares a declared character set, the probe text,
the translation catalogues, the string literals of the Python sources, the content
text of the user guide and whole Unicode tables with the cmap of the two built
Nifen Art fonts. The inputs are the COMMITTED declared set, probe text and fonts
(and the shipped catalogues, interface code and guide content); all are only ever
READ. A test that needs a different input writes a COPY under the per-test scratch
folder and points the checker at it.

Scenarios covered (one group each):

* SC-VI-BUILD-004-1 - the catalogues, the interface literals, the guide content and
  the kana / Greek / Cyrillic probe text have zero missing characters in both
  weights, over a non-zero examined count, with the per-block totals printed.
* SC-VI-BUILD-004-2 - the declared set is covered in Regular and in Bold, and its
  size is printed and equals the count its own header declares.
* The command line: exit 0 on a pass, 1 on any gated missing character, 2 on an
  unreadable font; a failure for every mode that examined nothing (declared set,
  probe text, catalogues, ``--py-dir``, ``--text-dir``, ``--table``).
* A planted missing character is caught in every mode (declared set, probe text,
  catalogue, Python literal, content text, table), in one weight only as well as in
  both, and a font glyph outside the declared set is caught too. The number the
  script reports is compared with a count taken straight from the font's cmap.

fontTools is a BUILD-TIME dependency that the project must declare (the dev extra
and ``constraints.txt``; see ``test_build_nifen_art``). If it is not importable
every test here FAILS with a message that says so; none is skipped.

Test seam: ``NIFEN_TOOLS_ROOT`` points the tests at a COPY of the layout so a test
can be shown to catch a mutated script; it is unset in normal runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Sequence, Set, Tuple

import pytest

from .conftest import REPO_ROOT

TOOLS_ROOT = Path(os.environ.get("NIFEN_TOOLS_ROOT") or REPO_ROOT).resolve()
FONT_SCRIPTS = TOOLS_ROOT / "scripts" / "font"
SOURCES = TOOLS_ROOT / "fonts-src" / "nifen-art"
FONT_DIR = TOOLS_ROOT / "pixelart_creator" / "fonts"
I18N_DIR = TOOLS_ROOT / "pixelart_creator" / "i18n"

CHECKER = "check_glyph_coverage.py"
WEIGHTS = ("regular", "bold")
FONT_FILES = {"regular": "NifenArt-Regular.ttf", "bold": "NifenArt-Bold.ttf"}
DECLARED = SOURCES / "coverage" / "declared-set.txt"
PROBE = SOURCES / "coverage" / "probe-text.txt"

#: Real product inputs the gate is asked to cover (read only).
UI_DIR = REPO_ROOT / "pixelart_creator" / "ui"
PACKAGE_DIR = REPO_ROOT / "pixelart_creator"
GUIDE_DIR = REPO_ROOT / "pixelart_creator" / "userguide_content"

#: Characters no committed input contains and the fonts do not carry.
KANJI = "漢"  # a CJK ideograph: out of scope for this typeface
COMBINING_GRAVE = "̀"  # the combining marks are not in the declared set

FONTTOOLS_PIN = "4.63.0"
MISSING_FONTTOOLS = (
    "fontTools is not importable. It is a build-time dependency of the Nifen Art "
    "scripts and the committed fonts were built with fontTools==%s. Declare it in "
    "the dev extra of pyproject.toml and pin it in constraints.txt (CI installs "
    "'-c constraints.txt -e .[dev]' and nothing else), then reinstall. These tests "
    "fail rather than skip so that a missing build dependency is never read as a "
    "pass." % FONTTOOLS_PIN
)

_GUARDED = (FONT_SCRIPTS, TOOLS_ROOT / "fonts-src", FONT_DIR, I18N_DIR)


class Run(NamedTuple):
    returncode: int
    stdout: str
    stderr: str

    @property
    def text(self) -> str:
        return self.stdout + self.stderr


# --------------------------------------------------------------------------
# Fixtures and runner
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_fonttools():
    """Fail (never skip) when the build dependency is missing."""
    if importlib.util.find_spec("fontTools") is None:
        pytest.fail(MISSING_FONTTOOLS, pytrace=False)


def _tree_digest() -> Dict[str, str]:
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
    """A private folder under the configured temp root, removed after the test."""
    root = os.environ.get("ORCH_TEST_TMP")
    if root:
        base = Path(root) / "asset-pipeline-nifen"
        base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="c-", dir=str(base)))
    else:
        folder = tmp_path_factory.mktemp("nifen-coverage")
    yield folder
    shutil.rmtree(folder)


def _child_env(scratch: Path, extra: Optional[Dict[str, str]] = None) -> dict:
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
    if extra:
        env.update(extra)
    return env


def run_checker(
    args: Sequence[object],
    scratch: Path,
    *,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[Path] = None,
) -> Run:
    """Run the checker as a real subprocess (its documented entry point)."""
    done = subprocess.run(
        [sys.executable, "-B", str(FONT_SCRIPTS / CHECKER), *[str(a) for a in args]],
        cwd=str(cwd or TOOLS_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=_child_env(scratch, env),
    )
    return Run(done.returncode, done.stdout, done.stderr)


# --------------------------------------------------------------------------
# Oracles: everything below is computed here, not by the script under test
# --------------------------------------------------------------------------

SET_LINE = re.compile(
    r"^(?P<label>.+?) \| (?P<font>\S+): examined (?P<n>\d+) unique characters, "
    r"missing (?P<miss>\d+)$",
    re.M,
)
FAILURES = re.compile(r"^coverage failures: (\d+)$", re.M)


def parse_sets(text: str) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """(label, font file) -> (examined, missing) as printed."""
    return {
        (m["label"], m["font"]): (int(m["n"]), int(m["miss"]))
        for m in SET_LINE.finditer(text)
    }


def cmap_of(path: Path) -> Set[int]:
    from fontTools.ttLib import TTFont

    return set(TTFont(str(path)).getBestCmap())


def read_declared_chars(path: Path) -> Set[str]:
    """Own parser of the declared-set format: ``label: characters`` per line."""
    chars: Set[str] = set()
    for line in path.read_bytes().decode("utf-8").split("\n"):
        if not line or line.startswith("# "):
            continue
        chars.update(line.split(": ", 1)[1])
    return {c for c in chars if c not in "\n\r\t"}


def declared_count() -> int:
    head = DECLARED.read_text(encoding="utf-8")
    found = re.search(r"\((\d+) unique characters per weight\)", head)
    assert found, "the declared-set header no longer states its count"
    return int(found.group(1))


def probe_chars() -> Set[str]:
    chars: Set[str] = set()
    for line in PROBE.read_bytes().decode("utf-8").split("\n"):
        if line and not line.startswith("# "):
            chars.update(line)
    return {c for c in chars if c not in "\n\r\t"}


def write_declared(scratch: Path, chars: Set[str], name: str = "declared.txt") -> Path:
    """A declared-set file in the checker's format holding exactly ``chars``."""
    path = scratch / name
    body = "# declared set written by the test\n"
    for index, ch in enumerate(sorted(chars)):
        body += "g%d: %s\n" % (index, ch)
    path.write_bytes(body.encode("utf-8"))
    return path


def font_copy_without(
    scratch: Path, weight: str, cps: Sequence[int], name: str
) -> Path:
    """A COPY of a built font whose cmap no longer maps the given code points."""
    from fontTools.ttLib import TTFont

    folder = scratch / name
    folder.mkdir()
    font = TTFont(str(FONT_DIR / FONT_FILES[weight]))
    for table in font["cmap"].tables:
        for cp in cps:
            table.cmap.pop(cp, None)
    target = folder / FONT_FILES[weight]
    font.save(str(target))
    return target


def ts_file(path: Path, *texts: str) -> Path:
    """A minimal Qt catalogue carrying the given translation texts."""
    messages = "".join(
        "<message><source>s%d</source><translation>%s</translation></message>" % (i, t)
        for i, t in enumerate(texts)
    )
    path.write_bytes(
        (
            '<?xml version="1.0" encoding="utf-8"?><TS version="2.1">'
            "<context><name>c</name>%s</context></TS>" % messages
        ).encode("utf-8")
    )
    return path


# --------------------------------------------------------------------------
# SC-VI-BUILD-004-1 / -2: the committed inputs pass, over counted denominators
# --------------------------------------------------------------------------


def test_default_run_covers_the_declared_set_and_the_probe_text_in_both_weights(
    scratch,
):
    """SC-VI-BUILD-004-1 / -2 with no arguments: repository-relative defaults."""
    res = run_checker([], scratch)
    assert res.returncode == 0, res.text
    sets = parse_sets(res.stdout)
    fonts = set(FONT_FILES.values())
    declared = {f: sets[("declared set", f)] for f in fonts}
    probe = {f: sets[("specimen strings", f)] for f in fonts}
    assert set(declared) == fonts
    for font in fonts:
        assert declared[font] == (declared_count(), 0), (font, declared[font])
        assert probe[font] == (len(probe_chars()), 0), (font, probe[font])
        assert "%s: font glyphs not in the declared set: 0" % font in res.stdout
    assert "coverage failures: 0" in res.stdout


def test_the_default_run_does_not_depend_on_the_working_folder(scratch):
    """Defaults come from the script's own location, not from the current folder."""
    elsewhere = scratch / "elsewhere"
    elsewhere.mkdir()
    res = run_checker([], scratch, cwd=elsewhere)
    assert res.returncode == 0, res.text
    assert "coverage failures: 0" in res.stdout


def test_the_declared_set_size_equals_the_count_its_header_states():
    """The printed size, the header, our own parse and the font's cmap agree."""
    own = read_declared_chars(DECLARED)
    assert len(own) == declared_count() > 0
    for weight in WEIGHTS:
        assert {ord(c) for c in own} == cmap_of(FONT_DIR / FONT_FILES[weight])


def test_the_probe_text_carries_kana_greek_and_cyrillic_and_all_are_examined(scratch):
    """SC-VI-BUILD-004-1: the per-block totals show each script was looked at."""
    res = run_checker([], scratch)
    assert res.returncode == 0, res.text
    section = res.stdout.split("specimen strings | ")[1:]
    assert len(section) == 2, "expected one specimen section per weight"
    for body in section:
        for block in ("Hiragana", "Katakana", "Greek and Coptic", "Cyrillic"):
            row = re.search(
                "^ +%s +examined +([0-9]+) +missing +([0-9]+)$" % block, body, re.M
            )
            assert row, "no per-block row for %s" % block
            assert int(row[1]) > 0 and int(row[2]) == 0, (block, row[0])


def test_catalogues_interface_literals_and_guide_content_are_covered_when_gated(
    scratch,
):
    """The production invocation: every source of shipped text, gated, counted."""
    res = run_checker(
        [
            "--gate-catalogues",
            "--catalogue",
            REPO_ROOT / "pixelart_creator" / "i18n" / "pixelart_en.ts",
            "--catalogue",
            REPO_ROOT / "pixelart_creator" / "i18n" / "pixelart_es.ts",
            "--py-dir",
            UI_DIR,
            "--py-dir",
            PACKAGE_DIR,
            "--text-dir",
            GUIDE_DIR,
        ],
        scratch,
    )
    assert res.returncode == 0, res.text
    sets = parse_sets(res.stdout)
    labels = {label for label, _font in sets}
    for prefix in (
        "declared set",
        "specimen strings",
        "catalogues (2 files)",
        "python string literals of ui",
        "python string literals of pixelart_creator",
        "content text of userguide_content",
    ):
        found = [lb for lb in labels if lb.startswith(prefix)]
        assert found, "no section starting %r in:\n%s" % (prefix, res.stdout[:600])
        for label in found:
            for font in FONT_FILES.values():
                examined, missing = sets[(label, font)]
                assert examined > 0, "%s examined nothing in %s" % (label, font)
                assert missing == 0, "%s: %d missing in %s" % (label, missing, font)
    for label in labels:
        if "python string literals" in label or "content text" in label:
            files = int(re.search(r"\((\d+) ", label)[1])
            assert files > 0, "%s scanned no file" % label


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_help_lists_every_mode(scratch):
    res = run_checker(["--help"], scratch)
    assert res.returncode == 0, res.text
    for flag in (
        "--declared",
        "--font",
        "--strings",
        "--catalogue",
        "--py-dir",
        "--text-dir",
        "--gate-catalogues",
        "--table",
    ):
        assert flag in res.stdout, flag


def test_an_unknown_flag_is_a_usage_error(scratch):
    assert run_checker(["--no-such-flag"], scratch).returncode == 2


def test_a_missing_font_is_exit_two_and_named(scratch):
    res = run_checker(["--font", scratch / "absent.ttf"], scratch)
    assert res.returncode == 2, res.text
    assert "cannot read" in res.stdout and "absent.ttf" in res.stdout


def test_a_file_that_is_not_a_font_is_exit_two(scratch):
    junk = scratch / "junk.ttf"
    junk.write_bytes(b"this is not a font file")
    res = run_checker(["--font", junk], scratch)
    assert res.returncode == 2, res.text
    assert "cannot read" in res.stdout


def test_a_missing_declared_file_fails_without_a_clean_verdict(scratch):
    res = run_checker(["--declared", scratch / "absent.txt"], scratch)
    assert res.returncode != 0, res.text
    assert "coverage failures: 0" not in res.stdout


def test_a_malformed_declared_line_stops_the_run(scratch):
    bad = scratch / "bad.txt"
    bad.write_bytes(b"# header\nthis line has no label separator\n")
    res = run_checker(["--declared", bad], scratch)
    assert res.returncode != 0, res.text
    assert "bad line in" in res.text
    assert "coverage failures: 0" not in res.stdout


def test_a_malformed_table_range_is_not_a_pass(scratch):
    res = run_checker(["--table", "U+0041"], scratch)
    assert res.returncode != 0, res.text
    assert "coverage failures: 0" not in res.stdout


def test_a_missing_fonttools_fails_with_exit_two_and_names_it(scratch):
    """With fontTools hidden the checker cannot read a font: exit 2, never 0."""
    shim = scratch / "shim" / "fontTools"
    shim.mkdir(parents=True)
    (shim / "__init__.py").write_text(
        "raise ImportError('fontTools is hidden by the test')\n", encoding="utf-8"
    )
    res = run_checker([], scratch, env={"PYTHONPATH": str(shim.parent)})
    assert res.returncode == 2, res.text
    assert "cannot read" in res.stdout and "fontTools" in res.stdout


# --------------------------------------------------------------------------
# A gate that examined nothing fails (every mode)
# --------------------------------------------------------------------------


def test_an_empty_declared_set_fails(scratch):
    empty = scratch / "empty.txt"
    empty.write_bytes(b"# nothing declared\n")
    res = run_checker(["--declared", empty], scratch)
    assert res.returncode == 1, res.text
    assert "declared set: nothing examined" in res.stdout
    # one failure for the empty set itself, one per font for the glyphs that no
    # declaration covers: the empty set must be counted as a failure of its own
    assert "coverage failures: 3" in res.stdout


def test_an_empty_probe_text_fails(scratch):
    empty = scratch / "empty-probe.txt"
    empty.write_bytes(b"# nothing to probe\n")
    res = run_checker(["--strings", empty], scratch)
    assert res.returncode == 1, res.text
    assert "specimen strings: nothing examined" in res.stdout


def test_a_catalogue_without_text_fails_even_when_not_gated(scratch):
    res = run_checker(["--catalogue", ts_file(scratch / "empty.ts")], scratch)
    assert res.returncode == 1, res.text
    assert "nothing examined" in res.stdout


def test_a_py_dir_that_yields_no_character_fails(scratch):
    ascii_only = scratch / "ascii"
    ascii_only.mkdir()
    (ascii_only / "mod.py").write_text("x = 'plain ascii only'\n", encoding="utf-8")
    for folder in (ascii_only, scratch / "does-not-exist"):
        res = run_checker(["--py-dir", folder], scratch)
        assert res.returncode == 1, (folder, res.text)
        assert "nothing examined" in res.stdout


def test_a_text_dir_that_yields_no_character_fails(scratch):
    only_txt = scratch / "texts"
    only_txt.mkdir()
    (only_txt / "note.txt").write_text("non-ascii ñ in a txt file\n", encoding="utf-8")
    res = run_checker(["--text-dir", only_txt], scratch)
    assert res.returncode == 1, res.text
    assert "nothing examined" in res.stdout


def test_a_table_range_without_an_assigned_code_point_fails(scratch):
    res = run_checker(["--table", "U+0378..U+0379"], scratch)
    assert res.returncode == 1, res.text
    assert "no assigned code point in the range, nothing examined" in res.stdout


# --------------------------------------------------------------------------
# A planted missing character is caught, in every mode
# --------------------------------------------------------------------------


def test_a_planted_character_missing_from_both_weights_fails_the_declared_gate(
    scratch,
):
    """SC-VI-BUILD-004-1 control: two absent characters added to a COPY of the set.

    The count the script prints is compared with a count taken from the fonts' own
    cmaps by this test.
    """
    planted = read_declared_chars(DECLARED) | {KANJI, COMBINING_GRAVE}
    declared = write_declared(scratch, planted)
    res = run_checker(["--declared", declared], scratch)
    assert res.returncode == 1, res.text
    sets = parse_sets(res.stdout)
    for weight in WEIGHTS:
        cmap = cmap_of(FONT_DIR / FONT_FILES[weight])
        oracle = sorted(ord(c) for c in planted if ord(c) not in cmap)
        assert oracle == sorted([ord(KANJI), ord(COMBINING_GRAVE)])
        examined, missing = sets[("declared set", FONT_FILES[weight])]
        assert (examined, missing) == (len(planted), len(oracle))
    assert "U+6F22" in res.stdout and "U+0300" in res.stdout


@pytest.mark.parametrize("weight", WEIGHTS)
def test_a_character_missing_from_one_weight_only_is_attributed_to_that_weight(
    scratch, weight
):
    """A COPY of one font loses 'e': that font fails, the other stays clean."""
    broken = font_copy_without(scratch, weight, [ord("e")], "broken")
    other_weight = "bold" if weight == "regular" else "regular"
    fonts = [broken, FONT_DIR / FONT_FILES[other_weight]]
    # the probe text is switched off so that only the declared-set gate can fail
    res = run_checker(
        [a for f in fonts for a in ("--font", f)] + ["--strings", ""], scratch
    )
    assert res.returncode == 1, res.text
    sets = parse_sets(res.stdout)
    assert sets[("declared set", FONT_FILES[weight])][1] == 1
    assert sets[("declared set", FONT_FILES[other_weight])][1] == 0
    assert "U+0065" in res.stdout


def test_a_font_glyph_outside_the_declared_set_fails(scratch):
    """The declared set is the whole promise: an undeclared glyph is a failure."""
    chars = read_declared_chars(DECLARED) - {"e"}
    res = run_checker(["--declared", write_declared(scratch, chars)], scratch)
    assert res.returncode == 1, res.text
    for font in FONT_FILES.values():
        assert "%s: font glyphs not in the declared set: 1 U+0065" % font in res.stdout


def test_a_planted_character_in_the_probe_text_fails(scratch):
    probe = scratch / "probe.txt"
    probe.write_bytes(("Palette %s Paleta\n" % KANJI).encode("utf-8"))
    res = run_checker(["--strings", probe], scratch)
    assert res.returncode == 1, res.text
    sets = parse_sets(res.stdout)
    for font in FONT_FILES.values():
        examined, missing = sets[("specimen strings", font)]
        assert missing == 1 and examined == len(set("Palette %s Paleta" % KANJI))


def test_a_catalogue_character_is_information_unless_gated(scratch):
    """Catalogue gaps are reported always, and fail only with --gate-catalogues."""
    catalogue = ts_file(scratch / "planted.ts", "Open %s" % KANJI)
    plain = run_checker(["--catalogue", catalogue], scratch)
    gated = run_checker(["--catalogue", catalogue, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        sets = parse_sets(res.stdout)
        for font in FONT_FILES.values():
            assert sets[("catalogues (1 files)", font)][1] == 1
        assert "U+6F22" in res.stdout


def test_a_python_literal_character_is_counted_but_a_comment_is_not(scratch):
    """``--py-dir`` reads string literals only; the missing one fails when gated."""
    folder = scratch / "pycode"
    folder.mkdir()
    # the comment carries a different missing character: only the literal counts
    (folder / "mod.py").write_text(
        "# a comment with 字 in it\nvalue = 'nñ%s'\n" % KANJI, encoding="utf-8"
    )
    plain = run_checker(["--py-dir", folder], scratch)
    gated = run_checker(["--py-dir", folder, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        sets = parse_sets(res.stdout)
        entries = {k: v for k, v in sets.items() if "python string literals" in k[0]}
        assert entries
        for (_label, _font), (examined, missing) in entries.items():
            assert (examined, missing) == (2, 1), "the comment must not be counted"
        assert "U+5B57" not in res.stdout


def test_a_content_text_character_is_counted_for_md_and_json_only(scratch):
    folder = scratch / "guide"
    folder.mkdir()
    (folder / "page.md").write_text("Texto %s\n" % KANJI, encoding="utf-8")
    (folder / "data.json").write_text('{"k": "ñ"}\n', encoding="utf-8")
    (folder / "ignored.txt").write_text("字\n", encoding="utf-8")
    plain = run_checker(["--text-dir", folder], scratch)
    gated = run_checker(["--text-dir", folder, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        entries = {
            k: v for k, v in parse_sets(res.stdout).items() if "content text" in k[0]
        }
        assert entries
        for (_label, _font), (examined, missing) in entries.items():
            assert (examined, missing) == (2, 1)
        assert "(2 .md/.json files" in res.stdout and "U+5B57" not in res.stdout


def _table_rows(text: str) -> List[Tuple[str, int, int, int]]:
    """(font, assigned, range size, missing) of every ``table`` line."""
    return [
        (m[1], int(m[2]), int(m[3]), int(m[4]))
        for m in re.finditer(
            r"^table U\+[0-9A-F]+\.\.U\+[0-9A-F]+ \| (\S+): assigned (\d+) of (\d+) "
            r"code points, missing (\d+)",
            text,
            re.M,
        )
    ]


@pytest.mark.parametrize(
    "lo,hi", [(0x3041, 0x3096), (0x309D, 0x309F), (0x30A1, 0x30FA), (0x30FC, 0x30FF)]
)
def test_the_kana_tables_are_whole_in_both_weights(scratch, lo, hi):
    """Whole Unicode ranges, taken from the character database: no gap in the kana."""
    res = run_checker(["--table", "U+%04X..U+%04X" % (lo, hi)], scratch)
    assert res.returncode == 0, res.text
    assigned = [c for c in range(lo, hi + 1) if unicodedata.category(chr(c)) != "Cn"]
    rows = _table_rows(res.stdout)
    assert {r[0] for r in rows} == set(FONT_FILES.values())
    for _font, n_assigned, size, missing in rows:
        assert (n_assigned, size, missing) == (len(assigned), hi - lo + 1, 0)
    assert len(assigned) > 0
    assert "info: Hiragana: assigned code points not in the font:" in res.stdout


def test_a_table_that_includes_an_assigned_but_absent_code_point_fails(scratch):
    """U+3099 and U+309A are assigned and not drawn: a table over them must fail."""
    res = run_checker(["--table", "U+3041..U+309F"], scratch)
    assert res.returncode == 1, res.text
    for _font, _assigned, _size, missing in _table_rows(res.stdout):
        assert missing == 2
    assert "U+3099" in res.stdout and "U+309A" in res.stdout


def test_a_table_character_missing_from_a_font_is_caught(scratch):
    """Only the table gate can fail here: the declared set is the broken font's own
    (U+3042 removed from both), the probe text is off, and one font is checked."""
    broken = font_copy_without(scratch, "bold", [0x3042], "broken")
    declared = write_declared(scratch, read_declared_chars(DECLARED) - {"あ"})
    res = run_checker(
        [
            "--font",
            broken,
            "--declared",
            declared,
            "--strings",
            "",
            "--table",
            "U+3041..U+3096",
        ],
        scratch,
    )
    assert res.returncode == 1, res.text
    assert "coverage failures: 1" in res.stdout
    assert [r[3] for r in _table_rows(res.stdout)] == [1]
