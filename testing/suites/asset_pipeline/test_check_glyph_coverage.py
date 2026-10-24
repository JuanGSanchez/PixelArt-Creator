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
* SC-L10N-BUILD-001-1 / -5 (the real tree through the production
  invocation) - every scan is face-aware: Hangul is judged by the KR face, the Han
  of an endonym by its own language's form set only (SC for the Simplified name, JP
  for the Japanese one), Han in ``ja`` text by JP, Han in ``zh_CN`` text by SC, any
  other Han by both form sets, everything else by the existing face. The routed
  counts per face are computed here from the endonym table and the fonts' cmaps.
* The command line: exit 0 on a pass, 1 on any gated missing character, 2 on an
  unreadable font; a failure for every mode that examined nothing (declared set,
  probe text, catalogues, ``--py-dir``, ``--text-dir``, ``--table``).
* A planted missing character is caught in every mode (declared set, probe text,
  catalogue, Python literal, content text, table), in one weight only as well as in
  both, and a font glyph outside the declared set is caught too. The number the
  script reports is compared with a count taken straight from the font's cmap.
* Batch mode (``--batch``, the contract in the checker's own docstring), over
  SCRATCH pages and worklists only - never the real Korean guide tree, which is in
  progress and uses syllables the KR face does not draw yet: a Latin-only batch
  passes with every CJK face saying "nothing routed"; an undrawn Hangul syllable of
  a ko page fails on both KR weights; an undrawn Han of a ja page fails on both JP
  weights and is never asked of SC; a router that sends a character to no face (or
  to a mix of faces) is a named routing error and not a silent drop; and each
  face's examined count equals the characters routed to that face.

fontTools is a BUILD-TIME dependency that the project must declare (the dev extra
and ``constraints.txt``; see ``test_build_nifen_art``). If it is not importable
every test here FAILS with a message that says so; none is skipped.

Test seam: ``NIFEN_TOOLS_ROOT`` points the tests at a COPY of the layout so a test
can be shown to catch a mutated script; it is unset in normal runs.
"""

from __future__ import annotations

import ast
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
    script: Optional[Path] = None,
) -> Run:
    """Run the checker as a real subprocess (its documented entry point).

    ``script`` names another copy of the checker (a deliberately broken one, built
    under the per-test scratch folder); the committed script is the default.
    """
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script or FONT_SCRIPTS / CHECKER),
            *[str(a) for a in args],
        ],
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
# Oracles of the two faces: every number below is computed here
# --------------------------------------------------------------------------

LANGUAGE_NAMES = TOOLS_ROOT / "pixelart_creator" / "logic" / "language_names.py"

#: The Han form set that draws a language's own name, by catalogue code.
FORM_OF_ENDONYM = {"zh_CN": "sc", "ja": "jp"}

#: face -> weight -> font file name. ``existing`` is the Nifen Art pair.
FACE_FILES: Dict[str, Dict[str, str]] = {
    "existing": dict(FONT_FILES),
    **{
        face: {
            weight: "NifenArtCJK%s-%s.ttf" % (face.upper(), weight.capitalize())
            for weight in WEIGHTS
        }
        for face in ("jp", "sc", "kr")
    },
}

ROUTED_LINE = re.compile(
    r"^(?P<label>.+?): examined (?P<n>\d+) unique characters, routed: existing face "
    r"(?P<existing>\d+), KR (?P<kr>\d+), JP only (?P<jp>\d+), SC only (?P<sc>\d+), "
    r"JP and SC (?P<both>\d+) \(sum (?P<sum>\d+)\)$",
    re.M,
)


def clean_catalogue(scratch: Path) -> List[object]:
    """``--catalogue`` arguments naming a scratch catalogue with nothing to miss.

    A scan without ``--catalogue`` discovers every ``pixelart_*.ts`` of the real
    package, and with ``--gate-catalogues`` a language not yet drawn would fail the
    run for a reason that is not the one under test.
    """
    return ["--catalogue", ts_file(scratch / "pixelart_en.ts", "Open")]


def plain_chars(*texts: str) -> int:
    """Unique characters a scratch catalogue of ``texts`` routes to the existing
    face: those that are neither Han nor Hangul, and the ``s0``, ``s1`` ... source
    labels that ``ts_file`` writes."""
    seen = set()
    for index, text in enumerate(texts):
        seen.update(
            c for c in "s%d%s" % (index, text) if not (is_han(c) or is_hangul(c))
        )
    return len(seen)


def endonyms() -> Dict[str, str]:
    """The language self-names, read from the one source (executed, not imported,
    so that no bytecode is written next to the product code)."""
    namespace: Dict[str, object] = {}
    exec(  # noqa: S102 - the product's own constant table, read only
        compile(LANGUAGE_NAMES.read_bytes(), str(LANGUAGE_NAMES), "exec"), namespace
    )
    return dict(namespace["ENDONYMS"])  # type: ignore[call-overload]


def is_han(ch: str) -> bool:
    """Own definition, from the character database (not the script's ranges)."""
    return unicodedata.name(ch, "").startswith("CJK UNIFIED IDEOGRAPH")


def is_hangul(ch: str) -> bool:
    return unicodedata.name(ch, "").startswith("HANGUL SYLLABLE")


def face_cmap(face: str, weight: str) -> Set[int]:
    path = FONT_DIR / FACE_FILES[face][weight]
    assert path.is_file(), (
        "%s is not built: the CJK faces are required here" % path.name
    )
    return cmap_of(path)


def assert_undrawn(chars: str) -> None:
    """The planted characters are in none of the six CJK files (a precondition,
    so that a 'missing' below cannot be a coincidence of the plant)."""
    for face in ("jp", "sc", "kr"):
        for weight in WEIGHTS:
            held = [c for c in chars if ord(c) in face_cmap(face, weight)]
            assert not held, (face, weight, held)


def package_literal_chars() -> Set[str]:
    """Own walk: the unique non-ASCII characters inside string literals of every
    .py file of the package (docstrings included, as the checker reads them)."""
    found: Set[str] = set()
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_bytes(), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.update(c for c in node.value if ord(c) > 127)
    return found


def route_package_chars(chars: Set[str], names: Dict[str, str]) -> Dict[str, Set[str]]:
    """The faces that must draw each character of the package's literals.

    Hangul -> KR; the Han of the zh_CN / ja self-name -> SC / JP only; any other
    Han -> both form sets; everything else -> the existing face.
    """
    own: Dict[str, Set[str]] = {"sc": set(), "jp": set()}
    for code, form in FORM_OF_ENDONYM.items():
        own[form] |= {c for c in names[code] if is_han(c)}
    faces: Dict[str, Set[str]] = {k: set() for k in ("existing", "kr", "jp", "sc")}
    for ch in chars:
        if is_hangul(ch):
            faces["kr"].add(ch)
        elif is_han(ch):
            if ch in own["sc"]:
                faces["sc"].add(ch)
            elif ch in own["jp"]:
                faces["jp"].add(ch)
            else:
                faces["sc"].add(ch)
                faces["jp"].add(ch)
        else:
            faces["existing"].add(ch)
    return faces


def face_lines(text: str, prefix: str) -> Dict[str, Dict[str, Tuple[int, int]]]:
    """face -> weight -> (examined, missing) of the ONE section starting ``prefix``.

    A line that is not printed for a face and weight fails here: a silent section
    is never read as 'nothing missing'.
    """
    sets = parse_sets(text)
    labels = {label for label, _font in sets if label.startswith(prefix)}
    assert len(labels) == 1, (prefix, sorted(labels), text[:400])
    label = labels.pop()
    out: Dict[str, Dict[str, Tuple[int, int]]] = {}
    for face, files in FACE_FILES.items():
        out[face] = {}
        for weight, font in files.items():
            assert (label, font) in sets, "no line for %s | %s" % (label, font)
            out[face][weight] = sets[(label, font)]
    return out


def assert_faces(text: str, prefix: str, **expected: Tuple[int, int]) -> None:
    """Every face's line, in both weights, equals (examined, missing)."""
    assert set(expected) == set(FACE_FILES), sorted(expected)
    got = face_lines(text, prefix)
    for face, per_weight in got.items():
        for weight, line in per_weight.items():
            assert line == expected[face], (prefix, face, weight, line, expected[face])


def routed_parts(text: str, prefix: str) -> Dict[str, int]:
    """The routed-counts line of the ONE section starting ``prefix``."""
    found = [m for m in ROUTED_LINE.finditer(text) if m["label"].startswith(prefix)]
    assert len(found) == 1, (prefix, len(found))
    return {k: int(v) for k, v in found[0].groupdict().items() if k != "label"}


def missing_code_points(text: str, prefix: str, font: str) -> List[int]:
    """The code points named on the ``missing:`` line under one section/font line."""
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if line.startswith(prefix) and (" | %s: " % font) in line:
            for follow in lines[index + 1 :]:
                if not follow.startswith("    "):
                    break
                if follow.startswith("    missing: "):
                    return sorted(
                        int(h, 16) for h in re.findall(r"U\+([0-9A-F]{4,6}) ", follow)
                    )
            return []
    raise AssertionError("no line for %s | %s" % (prefix, font))


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
    """The production invocation: every source of shipped text, gated, counted.

    SC-L10N-BUILD-001-1 / -5 over the real tree and both faces: every line the run
    prints, the six CJK files included, reads 0 missing; and for the package's
    string literals the routed counts are exactly those the endonym table and the
    fonts' cmaps give (existing face + SC + JP + KR = examined).
    """
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
            # the routed scans print one line per CJK file as well, per weight
            if not prefix.startswith(("declared set", "specimen strings")):
                for face in ("jp", "sc", "kr"):
                    for font in FACE_FILES[face].values():
                        assert (label, font) in sets, "no line: %s | %s" % (label, font)
                        assert sets[(label, font)][1] == 0, (label, font)
    for label in labels:
        if "python string literals" in label or "content text" in label:
            files = int(re.search(r"\((\d+) ", label)[1])
            assert files > 0, "%s scanned no file" % label
    # the routed counts of the package's literals, from this module's own oracles
    names = endonyms()
    chars = package_literal_chars()
    routed = route_package_chars(chars, names)
    own_han = {c for lang in FORM_OF_ENDONYM for c in names[lang] if is_han(c)}
    assert {
        c for c in chars if is_han(c)
    } == own_han, "a Han literal that is no endonym"
    assert {c for c in chars if is_hangul(c)} == {
        c for c in names["ko"] if is_hangul(c)
    }
    prefix = "python string literals of pixelart_creator"
    expected = {}
    for face, files in FACE_FILES.items():
        wanted = routed[face]
        for weight, font in files.items():
            absent = sum(1 for c in wanted if ord(c) not in face_cmap(face, weight))
            expected[(face, weight)] = (len(wanted), absent)
    assert (len(routed["sc"]), len(routed["jp"]), len(routed["kr"])) == (4, 3, 3)
    assert routed["sc"] == set("简体中文") and routed["jp"] == set("日本語")
    got = face_lines(res.stdout, prefix)
    for (face, weight), line in expected.items():
        assert got[face][weight] == line, (face, weight, got[face][weight], line)
        assert line[1] == 0, "%s %s: %d missing" % (face, weight, line[1])
    assert sum(len(v) for v in routed.values()) == len(chars)
    parts = routed_parts(res.stdout, prefix)
    assert parts == {
        "n": len(chars),
        "existing": len(routed["existing"]),
        "kr": len(routed["kr"]),
        "jp": len(routed["jp"] - routed["sc"]),
        "sc": len(routed["sc"] - routed["jp"]),
        "both": len(routed["jp"] & routed["sc"]),
        "sum": len(chars),
    }, parts


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
    """Catalogue gaps are reported always, and fail only with --gate-catalogues.

    The planted Han character sits in a catalogue of no known language, so it is
    required of BOTH form sets (JP and SC, both weights) and of no other face; the
    existing face's line examines the rest of the text and reads 0 missing.
    """
    assert_undrawn(KANJI)
    catalogue = ts_file(scratch / "planted.ts", "Open %s" % KANJI)
    plain = run_checker(["--catalogue", catalogue], scratch)
    gated = run_checker(["--catalogue", catalogue, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        assert_faces(
            res.stdout,
            "catalogues (1 files)",
            existing=(plain_chars("Open " + KANJI), 0),
            jp=(1, 1),
            sc=(1, 1),
            kr=(0, 0),
        )
        assert "U+6F22" in res.stdout


def test_a_python_literal_character_is_counted_but_a_comment_is_not(scratch):
    """``--py-dir`` reads string literals only; the missing one fails when gated.

    The Han character is in a literal that is no endonym, so both form sets must
    draw it; the existing face's line holds only the other character of the literal.
    """
    assert_undrawn(KANJI + "字")
    folder = scratch / "pycode"
    folder.mkdir()
    # the comment carries a different missing character: only the literal counts
    (folder / "mod.py").write_text(
        "# a comment with 字 in it\nvalue = 'nñ%s'\n" % KANJI, encoding="utf-8"
    )
    clean = clean_catalogue(scratch)
    plain = run_checker(["--py-dir", folder, *clean], scratch)
    gated = run_checker(["--py-dir", folder, *clean, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        # the comment's character would raise the JP and SC counts to 2 if read
        assert_faces(
            res.stdout,
            "python string literals of pycode",
            existing=(1, 0),
            jp=(1, 1),
            sc=(1, 1),
            kr=(0, 0),
        )
        assert "U+6F22" in res.stdout and "U+5B57" not in res.stdout


def test_a_content_text_character_is_counted_for_md_and_json_only(scratch):
    """Only .md and .json are content text; a Han in a folder of no known language
    is required of both form sets, and a .txt file's character is not read."""
    assert_undrawn(KANJI + "字")
    folder = scratch / "guide"
    folder.mkdir()
    (folder / "page.md").write_text("Texto %s\n" % KANJI, encoding="utf-8")
    (folder / "data.json").write_text('{"k": "ñ"}\n', encoding="utf-8")
    (folder / "ignored.txt").write_text("字\n", encoding="utf-8")
    clean = clean_catalogue(scratch)
    plain = run_checker(["--text-dir", folder, *clean], scratch)
    gated = run_checker(["--text-dir", folder, *clean, "--gate-catalogues"], scratch)
    assert plain.returncode == 0, plain.text
    assert gated.returncode == 1, gated.text
    for res in (plain, gated):
        assert_faces(
            res.stdout,
            "content text of guide",
            existing=(1, 0),
            jp=(1, 1),
            sc=(1, 1),
            kr=(0, 0),
        )
        assert "(2 .md/.json files" in res.stdout and "U+5B57" not in res.stdout
        assert "U+6F22" in res.stdout


# --------------------------------------------------------------------------
# SC-L10N-BUILD-001-1 / -5: every scan is face-aware
# --------------------------------------------------------------------------


def test_without_the_cjk_fonts_the_package_scan_names_exactly_the_endonym_points(
    scratch,
):
    """Control (SC-L10N-BUILD-001-5): with only the two existing-face files in
    ``--font`` the real package's scan fails and names the 10 endonym code points.

    Each form set is named by its own points only: 简 体 中 文 for SC, 日 本 語 for
    JP and 한 국 어 for KR; the existing face still reads 0 missing.
    """
    names = endonyms()
    expected = {
        "sc": sorted(ord(c) for c in names["zh_CN"] if is_han(c)),
        "jp": sorted(ord(c) for c in names["ja"] if is_han(c)),
        "kr": sorted(ord(c) for c in names["ko"] if is_hangul(c)),
    }
    assert [len(v) for v in expected.values()] == [4, 3, 3]
    existing_only = [
        a for f in FACE_FILES["existing"].values() for a in ("--font", FONT_DIR / f)
    ]
    res = run_checker(
        existing_only
        + [
            "--gate-catalogues",
            "--catalogue",
            I18N_DIR / "pixelart_en.ts",
            "--py-dir",
            PACKAGE_DIR,
        ],
        scratch,
    )
    assert res.returncode == 1, res.text
    prefix = "python string literals of pixelart_creator"
    named: List[int] = []
    for face, points in expected.items():
        for font in FACE_FILES[face].values():
            got = missing_code_points(res.stdout, prefix, font)
            assert got == points, (font, got, points)
            named.extend(got)
    assert len(named) == 2 * 10 and sorted(set(named)) == sorted(
        sum(expected.values(), [])
    )
    for font in FACE_FILES["existing"].values():
        assert missing_code_points(res.stdout, prefix, font) == []
    assert "font not provided: every routed character counts as missing" in res.stdout


@pytest.mark.parametrize("origin", ["ko", "fr"])
def test_hangul_is_routed_to_the_kr_face_whatever_the_language(scratch, origin):
    """SC-L10N-BUILD-001-5: a Hangul syllable is judged by the KR face only.

    한 is drawn there and 뷁 is not; the existing face and both form sets examine
    nothing, so the miss is reported on the KR lines alone.
    """
    assert_undrawn("뷁")
    assert ord("한") in face_cmap("kr", "regular") and ord("한") in face_cmap(
        "kr", "bold"
    )
    catalogue = ts_file(scratch / ("pixelart_%s.ts" % origin), "한뷁")
    res = run_checker(["--catalogue", catalogue, "--gate-catalogues"], scratch)
    assert res.returncode == 1, res.text
    assert_faces(
        res.stdout,
        "catalogues (1 files)",
        existing=(plain_chars("한뷁"), 0),
        jp=(0, 0),
        sc=(0, 0),
        kr=(2, 1),
    )
    total = plain_chars("한뷁") + 2
    assert routed_parts(res.stdout, "catalogues (1 files)") == {
        "n": total,
        "existing": total - 2,
        "kr": 2,
        "jp": 0,
        "sc": 0,
        "both": 0,
        "sum": total,
    }
    for font in FACE_FILES["kr"].values():
        assert missing_code_points(res.stdout, "catalogues (1 files)", font) == [
            ord("뷁")
        ]


#: language of the text -> (the character its form set draws, expected JP/SC lines)
HAN_CASES = {
    "ja": ("日", {"jp": (2, 1), "sc": (0, 0)}),
    "zh_CN": ("简", {"jp": (0, 0), "sc": (2, 1)}),
    "fr": ("日", {"jp": (2, 1), "sc": (2, 2)}),
}


def _han_text_run(scratch: Path, source: str, language: str, text: str) -> Run:
    """Run the checker over ``text`` seen as ``language`` text, as a catalogue or as
    a user-guide tree (a folder named for the language below the content root)."""
    if source == "catalogue":
        catalogue = ts_file(scratch / ("pixelart_%s.ts" % language), text)
        return run_checker(["--catalogue", catalogue, "--gate-catalogues"], scratch)
    page = scratch / "guide" / language / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text(text + "\n", encoding="utf-8")
    return run_checker(
        [
            "--text-dir",
            scratch / "guide",
            *clean_catalogue(scratch),
            "--gate-catalogues",
        ],
        scratch,
    )


@pytest.mark.parametrize("source", ["catalogue", "guide tree"])
@pytest.mark.parametrize("language", sorted(HAN_CASES))
def test_han_is_routed_by_the_language_of_the_text(scratch, source, language):
    """SC-L10N-BUILD-001-5: Han in ja text is required of JP only, Han in zh_CN text
    of SC only, and Han in the text of any other language of both form sets.

    Each text holds one character drawn by the set of its language (日 in JP, 简 in
    SC) and the undrawn 漢, so the miss shows which faces were asked.
    """
    drawn, wanted = HAN_CASES[language]
    assert_undrawn(KANJI)
    res = _han_text_run(scratch, source, language, drawn + KANJI)
    assert res.returncode == 1, res.text
    prefix = (
        "catalogues (1 files)" if source == "catalogue" else "content text of guide"
    )
    # fr: 日 is drawn by JP only, so SC misses both characters
    existing = (plain_chars(drawn + KANJI), 0) if source == "catalogue" else (0, 0)
    assert_faces(res.stdout, prefix, existing=existing, kr=(0, 0), **wanted)
    jp_missing = missing_code_points(res.stdout, prefix, FACE_FILES["jp"]["bold"])
    sc_missing = missing_code_points(res.stdout, prefix, FACE_FILES["sc"]["bold"])
    assert jp_missing == ([ord(KANJI)] if wanted["jp"][0] else [])
    if language == "fr":
        assert sc_missing == sorted([ord(drawn), ord(KANJI)])
    else:
        assert sc_missing == ([ord(KANJI)] if wanted["sc"][0] else [])


def test_an_endonym_literal_is_required_of_its_own_form_set_only(scratch):
    """SC-L10N-BUILD-001-5: a literal that is exactly an endonym goes to its own face.

    简体中文 is SC's alone and is never required of JP; 日本語 is JP's alone and is
    never required of SC; 한국어 is KR's. All three are drawn, so the run exits 0.
    """
    names = endonyms()
    folder = scratch / "names"
    folder.mkdir()
    (folder / "mod.py").write_text(
        "A = %r\nB = %r\nC = %r\n" % (names["zh_CN"], names["ja"], names["ko"]),
        encoding="utf-8",
    )
    res = run_checker(
        ["--py-dir", folder, *clean_catalogue(scratch), "--gate-catalogues"], scratch
    )
    assert res.returncode == 0, res.text
    assert_faces(
        res.stdout,
        "python string literals of names",
        existing=(0, 0),
        jp=(len(set(names["ja"])), 0),
        sc=(len(set(names["zh_CN"])), 0),
        kr=(len(set(names["ko"])), 0),
    )
    assert not set(names["zh_CN"]) & set(names["ja"]), "the two names share a character"


def test_a_literal_that_is_more_than_an_endonym_is_required_of_both_form_sets(scratch):
    """SC-L10N-BUILD-001-5: only a literal EQUAL to an endonym is routed as one.

    日本語 inside a longer literal is any other Han: JP draws it, SC does not, so the
    SC lines miss all three characters and the run fails.
    """
    names = endonyms()
    folder = scratch / "longer"
    folder.mkdir()
    (folder / "mod.py").write_text(
        "A = %r\n" % (names["ja"] + " text"), encoding="utf-8"
    )
    res = run_checker(
        ["--py-dir", folder, *clean_catalogue(scratch), "--gate-catalogues"], scratch
    )
    assert res.returncode == 1, res.text
    assert_faces(
        res.stdout,
        "python string literals of longer",
        existing=(0, 0),
        jp=(3, 0),
        sc=(3, 3),
        kr=(0, 0),
    )


def test_the_endonym_labels_scan_routes_each_name_to_its_own_face(scratch):
    """SC-L10N-BUILD-001-5, ``--endonyms``: the eight self-names, routed and counted."""
    names = endonyms()
    plain = {
        c for text in names.values() for c in text if not (is_han(c) or is_hangul(c))
    }
    res = run_checker(
        ["--endonyms", *clean_catalogue(scratch), "--gate-catalogues"], scratch
    )
    assert res.returncode == 0, res.text
    assert_faces(
        res.stdout,
        "endonym labels (%d)" % len(names),
        existing=(len(plain), 0),
        jp=(3, 0),
        sc=(4, 0),
        kr=(3, 0),
    )
    parts = routed_parts(res.stdout, "endonym labels")
    assert parts["sum"] == parts["n"] == len(plain) + 10


def test_a_face_with_nothing_routed_says_so_and_does_not_fail_alone(scratch):
    """A plain-Latin catalogue routes nothing to the CJK faces: stated, exit 0."""
    res = run_checker([*clean_catalogue(scratch), "--gate-catalogues"], scratch)
    assert res.returncode == 0, res.text
    assert_faces(
        res.stdout,
        "catalogues (1 files)",
        existing=(plain_chars("Open"), 0),
        jp=(0, 0),
        sc=(0, 0),
        kr=(0, 0),
    )
    for face in ("JP", "SC", "KR"):
        assert "nothing routed to the %s face" % face in res.stdout


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


# --------------------------------------------------------------------------
# Batch mode (--batch): scratch pages and worklists, never the real guide tree
# --------------------------------------------------------------------------
#
# The Korean guide tree of the working tree is in progress and uses syllables the
# KR face does not draw yet, so none of these tests reads it: every batch below is
# written under the per-test scratch folder. The counts expected are computed here
# from the character database and the fonts' cmaps (own oracles), not from the
# script's ranges.

BATCH_PREFIX = "batch "

BATCH_SUMMARY = re.compile(
    r"^batch .+?: examined (?P<n>\d+) unique characters, routed: existing face "
    r"(?P<existing>\d+), Han (?P<han>\d+), Hangul (?P<hangul>\d+) "
    r"\(sum (?P<sum>\d+)\)$",
    re.M,
)
BATCH_DEST = re.compile(
    r"^    routed by destination: existing face (?P<existing>\d+), KR (?P<kr>\d+), "
    r"JP only (?P<jp>\d+), SC only (?P<sc>\d+), JP and SC (?P<both>\d+) "
    r"\(sum (?P<sum>\d+)\)$",
    re.M,
)

#: The page of a ko batch. The heading and the Latin words are ASCII (a page reads
#: its non-ASCII characters only); U+00E9 goes to the existing face, U+D55C is drawn
#: by the KR face and U+BDC1 is not.
KO_PAGE = "# Guide\n\nOpen é 한 뷁\n"
UNDRAWN_HANGUL = "뷁"
#: U+65E5 U+672C U+8A9E are drawn by the JP face, U+6F22 is drawn by no CJK file.
JA_PAGE = "# Guide\n\n日本語 漢\n"


def batch_page(scratch: Path, language: str, text: str, folder: str = "guide") -> Path:
    """``<scratch>/<folder>/<language>/page.md`` holding ``text``; returns the page."""
    page = scratch / folder / language / "page.md"
    page.parent.mkdir(parents=True)
    page.write_bytes(text.encode("utf-8"))
    return page


def batch_worklist(scratch: Path, language: str, translations: list) -> Path:
    """A worklist whose ``source`` and ``context`` carry a character (U+0416) that no
    translation has, so a count that includes them is visible."""
    import json

    entries = [
        {"context": "CtxЖ", "source": "SrcЖ", "translation": form}
        for form in translations
    ]
    path = scratch / "work" / "worklist.json"
    path.parent.mkdir()
    path.write_bytes(
        json.dumps(
            {"language": language, "entries": entries}, ensure_ascii=False
        ).encode("utf-8")
    )
    return path


def page_chars(text: str) -> Set[str]:
    """What a page contributes: its non-ASCII characters (own parse)."""
    return {c for c in text if ord(c) > 127}


def worklist_chars(translations: list) -> Set[str]:
    """What a worklist contributes: every character of every translation form."""
    forms: List[str] = []
    for item in translations:
        forms.extend([item] if isinstance(item, str) else item)
    return {c for form in forms for c in form if c not in "\n\r\t"}


def batch_routing(chars: Set[str], language: str) -> Dict[str, Set[str]]:
    """The faces that must draw each character of a ``language`` batch (own rules).

    Hangul -> KR; Han -> JP only in ja text, SC only in zh_CN text, both form sets in
    the text of any other language; everything else -> the existing face.
    """
    own = FORM_OF_ENDONYM.get(language)
    out: Dict[str, Set[str]] = {k: set() for k in ("existing", "kr", "jp", "sc")}
    for ch in chars:
        if is_hangul(ch):
            out["kr"].add(ch)
        elif is_han(ch):
            for form in [own] if own else ["jp", "sc"]:
                out[form].add(ch)
        else:
            out["existing"].add(ch)
    return out


def batch_expected(
    routing: Dict[str, Set[str]],
) -> Dict[Tuple[str, str], Tuple[int, int]]:
    """(face, weight) -> (examined, missing) from the routing and the real cmaps."""
    expected = {}
    for face, wanted in routing.items():
        for weight in WEIGHTS:
            cmap = face_cmap(face, weight)
            expected[(face, weight)] = (
                len(wanted),
                sum(1 for c in wanted if ord(c) not in cmap),
            )
    return expected


def batch_numbers(pattern: "re.Pattern[str]", text: str) -> Dict[str, int]:
    """The ONE line a batch prints for ``pattern``, as numbers."""
    found = list(pattern.finditer(text))
    assert len(found) == 1, (pattern.pattern[:40], len(found), text[:500])
    return {k: int(v) for k, v in found[0].groupdict().items()}


def every_font_args() -> List[object]:
    """``--font`` arguments naming all eight built files."""
    names = [n for files in FACE_FILES.values() for n in files.values()]
    return [a for n in names for a in ("--font", FONT_DIR / n)]


def broken_checker(scratch: Path, old: str, new: str) -> Path:
    """A COPY of the checker with ``old`` replaced by ``new`` (it must occur once).

    The copy lives under the scratch folder and is run with ``script=``; the
    committed script is never touched. Paths the copy would derive from its own
    location are all passed on the command line by the caller.
    """
    source = (FONT_SCRIPTS / CHECKER).read_bytes().decode("utf-8")
    assert source.count(old) == 1, (
        "the patch target is not in the checker exactly once - the checker was "
        "refactored, so rebuild this broken copy: %r" % old
    )
    target = scratch / "broken" / "scripts" / "font" / CHECKER
    target.parent.mkdir(parents=True)
    target.write_bytes(source.replace(old, new).encode("utf-8"))
    return target


def assert_all_drawn_by(face: str, chars: str) -> None:
    for weight in WEIGHTS:
        held = face_cmap(face, weight)
        assert all(ord(c) in held for c in chars), (face, weight, chars)


@pytest.mark.parametrize("source", ["page", "worklist"])
def test_batch_of_latin_only_passes_and_every_cjk_face_says_nothing_was_routed(
    scratch, source
):
    """A batch with no Han and no Hangul: exit 0, the existing face judges all of it,
    and KR, JP and SC each print 'nothing routed' (examined 0, missing 0) per weight.

    ``page`` is a guide page (its non-ASCII characters are read); ``worklist`` is a
    translation worklist (every character of the translations is read).
    """
    if source == "page":
        text = "# Ouvrir\n\nÇa va, señor – über ß ¿Qué?\n"
        target = batch_page(scratch, "fr", text)
        chars = page_chars(text)
    else:
        forms = [
            "Ouvrir",
            "Ça va, señor",
            ["un fichier", "über ß ¿Qué?"],
        ]
        target = batch_worklist(scratch, "fr", forms)
        chars = worklist_chars(forms)
    routing = batch_routing(chars, "fr")
    assert chars and not (routing["kr"] | routing["jp"] | routing["sc"])
    total = len(chars)
    res = run_checker(["--batch", target], scratch)
    assert res.returncode == 0, res.text
    assert "coverage failures: 0" in res.stdout
    assert "nothing examined" not in res.stdout
    assert_faces(
        res.stdout, BATCH_PREFIX, existing=(total, 0), jp=(0, 0), sc=(0, 0), kr=(0, 0)
    )
    for face in ("JP", "SC", "KR"):
        assert res.stdout.count("nothing routed to the %s face" % face) == 2, face
    assert batch_numbers(BATCH_DEST, res.stdout) == {
        "existing": total,
        "kr": 0,
        "jp": 0,
        "sc": 0,
        "both": 0,
        "sum": total,
    }
    assert batch_numbers(BATCH_SUMMARY, res.stdout) == {
        "n": total,
        "existing": total,
        "han": 0,
        "hangul": 0,
        "sum": total,
    }


@pytest.mark.parametrize("target", ["page", "folder"])
def test_batch_of_a_ko_page_with_an_undrawn_hangul_syllable_fails_on_both_kr_weights(
    scratch, target
):
    """U+BDC1 is in no CJK file: exit 1 and it is named on KR Regular AND KR Bold,
    with the line it was found on, while every other face reads missing 0.

    The page is named for its folder (``ko``) either as the file or as the folder
    that contains it.
    """
    assert_undrawn(UNDRAWN_HANGUL)
    assert_all_drawn_by("kr", "한")
    page = batch_page(scratch, "ko", KO_PAGE)
    shown = page if target == "page" else page.parent.parent
    segment = "page.md:3" if target == "page" else "ko/page.md:3"
    res = run_checker(["--batch", shown], scratch)
    assert res.returncode == 1, res.text
    assert_faces(
        res.stdout, BATCH_PREFIX, existing=(1, 0), jp=(0, 0), sc=(0, 0), kr=(2, 1)
    )
    for font in FACE_FILES["kr"].values():
        assert missing_code_points(res.stdout, BATCH_PREFIX, font) == [0xBDC1], font
    assert (
        len(
            re.findall(
                r"^    missing: U\+BDC1 [^\n]* - segment: %s$" % re.escape(segment),
                res.stdout,
                re.M,
            )
        )
        == 2
    ), res.stdout
    for face in ("existing", "jp", "sc"):
        for font in FACE_FILES[face].values():
            assert missing_code_points(res.stdout, BATCH_PREFIX, font) == [], font
    assert "language of the batch: ko" in res.stdout
    assert "coverage failures: 2" in res.stdout
    assert batch_numbers(BATCH_DEST, res.stdout) == {
        "existing": 1,
        "kr": 2,
        "jp": 0,
        "sc": 0,
        "both": 0,
        "sum": 3,
    }


@pytest.mark.parametrize("how", ["folder name", "--language flag"])
def test_batch_of_a_ja_page_with_an_undrawn_han_fails_on_both_jp_weights(scratch, how):
    """U+6F22 is in no CJK file: as ja text it is required of JP only, so it is named
    on JP Regular AND JP Bold and the SC face is asked for nothing.

    The language comes either from the folder named ``ja`` or, in a neutral folder,
    from ``--language ja``.
    """
    assert_undrawn("漢")
    assert_all_drawn_by("jp", "日本語")
    folder = "ja" if how == "folder name" else "neutral"
    page = batch_page(scratch, folder, JA_PAGE)
    extra = [] if how == "folder name" else ["--language", "ja"]
    res = run_checker(["--batch", page, *extra], scratch)
    assert res.returncode == 1, res.text
    assert_faces(
        res.stdout, BATCH_PREFIX, existing=(0, 0), jp=(4, 1), sc=(0, 0), kr=(0, 0)
    )
    for font in FACE_FILES["jp"].values():
        assert missing_code_points(res.stdout, BATCH_PREFIX, font) == [0x6F22], font
    for face in ("existing", "sc", "kr"):
        for font in FACE_FILES[face].values():
            assert missing_code_points(res.stdout, BATCH_PREFIX, font) == [], font
    assert res.stdout.count("nothing routed to the SC face") == 2
    assert "language of the batch: ja" in res.stdout
    assert "coverage failures: 2" in res.stdout
    assert batch_numbers(BATCH_DEST, res.stdout) == {
        "existing": 0,
        "kr": 0,
        "jp": 4,
        "sc": 0,
        "both": 0,
        "sum": 4,
    }


def test_batch_control_the_same_han_page_in_another_language_asks_both_form_sets(
    scratch,
):
    """Control for the ja case: the page is the same bytes, the language is not ja,
    and now SC is asked for the four characters as well (it draws none of them)."""
    page = batch_page(scratch, "fr", JA_PAGE)
    res = run_checker(["--batch", page], scratch)
    assert res.returncode == 1, res.text
    expected = batch_expected(batch_routing(page_chars(JA_PAGE), "fr"))
    assert expected[("jp", "regular")] == (4, 1)
    assert expected[("sc", "regular")] == (4, 4)
    assert_faces(
        res.stdout, BATCH_PREFIX, existing=(0, 0), jp=(4, 1), sc=(4, 4), kr=(0, 0)
    )
    assert batch_numbers(BATCH_DEST, res.stdout)["both"] == 4


#: The line of ``route`` that sends Hangul to KR, and what a broken router sends it to.
HANGUL_ROUTE = 'return {"kr"}'
BROKEN_ROUTERS = {
    "empty destination": "return set()",
    "mixed destination": 'return {"kr", "existing"}',
}


@pytest.mark.parametrize("router", sorted(BROKEN_ROUTERS))
def test_batch_with_a_router_that_misplaces_hangul_is_a_named_routing_error(
    scratch, router
):
    """A Hangul syllable routed to no face (or to a mix of faces) must not vanish.

    The checker is run twice over the same ko page. The committed script is the
    control: no routing error, KR examines both syllables. A COPY of it whose router
    sends Hangul to nowhere (or to the existing face and KR at once) must exit 1
    with 'routing error' and name the characters it could not place.
    """
    page = batch_page(scratch, "ko", KO_PAGE)
    args = [
        *every_font_args(),
        "--constants",
        TOOLS_ROOT / "pixelart_creator" / "logic" / "constants.py",
        "--language-names",
        LANGUAGE_NAMES,
        "--batch",
        page,
    ]
    control = run_checker(args, scratch)
    assert control.returncode == 1, control.text  # U+BDC1 is undrawn
    assert "routing error" not in control.stdout, control.stdout
    assert "unrouted:" not in control.stdout
    assert_faces(
        control.stdout, BATCH_PREFIX, existing=(1, 0), jp=(0, 0), sc=(0, 0), kr=(2, 1)
    )

    script = broken_checker(scratch, HANGUL_ROUTE, BROKEN_ROUTERS[router])
    res = run_checker(args, scratch, script=script)
    assert res.returncode == 1, res.text
    assert "routing error: routed counts sum to 1, not 3" in res.stdout, res.stdout
    for cp in (0xD55C, 0xBDC1):
        assert re.search(r"^    unrouted: U\+%04X " % cp, res.stdout, re.M), res.stdout
    if router == "empty destination":
        # nothing else fails: the two syllables are on no line at all, and the exit
        # status is the routing error alone
        assert_faces(
            res.stdout, BATCH_PREFIX, existing=(1, 0), jp=(0, 0), sc=(0, 0), kr=(0, 0)
        )
        assert "coverage failures: 1" in res.stdout


@pytest.mark.parametrize("source", ["page", "worklist"])
def test_batch_each_face_is_judged_over_exactly_the_characters_routed_to_it(
    scratch, source
):
    """The examined count of every face and weight equals the characters routed to
    that face, and the two summary lines agree with it.

    The text is French-tagged, so its Han go to both form sets (JP draws the two
    here, SC draws neither) and its Hangul to KR (both syllables are drawn). The
    worklist also holds a source and a context character that are no translation and
    so must not be counted. The expected numbers come from the character database
    and the fonts' cmaps.
    """
    forms = [
        "Ça va, señor",
        "日本 — 한국",
        ["é", "über ß"],
    ]
    if source == "page":
        text = "# Guide\n\n" + "\n".join(
            f if isinstance(f, str) else " ".join(f) for f in forms
        )
        target = batch_page(scratch, "fr", text + "\n")
        chars = page_chars(text)
    else:
        target = batch_worklist(scratch, "fr", forms)
        chars = worklist_chars(forms)
    assert "Ж" not in chars
    routing = batch_routing(chars, "fr")
    assert (len(routing["kr"]), len(routing["jp"]), len(routing["sc"])) == (2, 2, 2)
    res = run_checker(["--batch", target], scratch)
    expected = batch_expected(routing)
    assert expected[("sc", "bold")] == (2, 2) and expected[("jp", "bold")] == (2, 0)
    assert expected[("kr", "bold")] == (2, 0)
    assert res.returncode == 1, res.text  # SC draws neither Han
    got = face_lines(res.stdout, BATCH_PREFIX)
    for (face, weight), line in expected.items():
        assert got[face][weight] == line, (face, weight, got[face][weight], line)
    total = len(chars)
    n_existing = len(routing["existing"])
    assert n_existing + 2 + 2 == total
    assert batch_numbers(BATCH_SUMMARY, res.stdout) == {
        "n": total,
        "existing": n_existing,
        "han": 2,
        "hangul": 2,
        "sum": total,
    }
    assert batch_numbers(BATCH_DEST, res.stdout) == {
        "existing": n_existing,
        "kr": 2,
        "jp": 0,
        "sc": 0,
        "both": 2,
        "sum": total,
    }
