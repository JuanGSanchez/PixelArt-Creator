#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: check_python_version  (standalone P11 script -- PixelArt Creator system)
# =============================================================================
# PURPOSE: Enforce ONE parametric Python-version source of truth. The repo-root
#   `.python-version` file (read verbatim, exact patch e.g. "3.13.13") is the
#   ONLY place the version is decided; this gate asserts every other pin that
#   cannot itself import a value -- pyproject.toml's install floor / Trove
#   classifier / mypy / black settings, the deployment container base image,
#   and the systemd service unit's interpreter reference -- still agrees with
#   it. Without this gate nothing stops those sites drifting apart again the
#   next time one of them is hand-edited.
# FLAVOUR: standalone
# LOCATION: scripts/check_python_version.py
# INVOKED BY: AGT-09 GitHub/DevOps (CI step + local pre-flight before "done").
# RUNTIME: Python 3.8+ (CPython, stdlib only: re, sys, json, argparse, pathlib).
# ENTRYPOINT: python scripts/check_python_version.py [--root .]
# INPUTS:
#   --root (CLI arg, optional, default "."): repo root; every fixed pin site
#           below is resolved relative to it.
# PIN SITES CHECKED (a FIXED, enumerated list -- not a broad content scan; see
#   EXCLUSION NOTE for why that distinction matters):
#     1. .python-version                              exact patch (SOURCE)
#     2. pyproject.toml  requires-python floor          minor  (">=X.Y")
#     3. pyproject.toml  Trove classifier                minor
#     4. pyproject.toml  [tool.mypy] python_version       minor
#     5. pyproject.toml  [tool.black] target-version       minor ("pyXYZ")
#     6. deploy/Dockerfile  FROM python:...-slim-bookworm  exact patch
#     7. deploy/pixelart-sync.service  `pythonX.Y -m venv` minor
#     8. README.md      user-facing install requirement    minor (PROSE, soft)
#     9. README.es.md   user-facing install requirement    minor (PROSE, soft)
#   A pin is compared at the PRECISION IT ACTUALLY EXPRESSES: a floor and a
#   classifier can only ever state major.minor, so each is compared against
#   the source's major.minor, never demanded to equal the full patch string --
#   doing that would make the gate permanently red for a reason no edit could
#   fix. Only the Dockerfile tag and the source file itself carry a full
#   patch, so those two are the only exact-match comparisons.
# PROSE SITES (8-9) ARE SOFT, SITES 1-7 ARE HARD -- this distinction is load-
#   bearing and deliberate. A hard site (config/manifest) is structured data:
#   its absence or unparseability is itself a finding (BLOCKED). A prose site
#   is free-running English/Spanish text that legitimately gets reworded for
#   reasons that have nothing to do with the Python version -- demanding it
#   always match a fixed shape would make the gate cry wolf on copy-editing
#   and get switched off, taking sites 1-7 down with it. So a prose CLAIM that
#   is FOUND and WRONG is still a hard failure (exit 1); a claim that is not
#   found at all is silently informational (reported in `sites` with
#   found="(claim not present)", contributes NO Finding, never blocks and
#   never fails). Only two narrow, high-precision prose shapes are matched --
#   see CLAIM_PATTERNS -- deliberately not a general English/Spanish version-
#   claim detector; a claim phrased outside these shapes is a residual,
#   accepted risk (see the script's report, not this file, for the boundary
#   statement).
# EXCLUSION NOTE (deliberate, not an oversight): the changelog and any ADR
#   under docs/adr/ are HISTORY -- they record what was true when written and
#   must never be edited retroactively to match a later pin. They are excluded
#   BY CONSTRUCTION here: this script checks the fixed list above, never a
#   broad grep across docs/** or the whole tree, so a historical record is
#   never a candidate finding -- not because it was matched and then filtered
#   out, but because it was never in the scanned set to begin with. If a new
#   live (non-historical) pin site is ever added to the repo, extend the
#   `SITES` list (or `README_RELPATHS` for prose) below explicitly; do not
#   widen this script into a free-text scanner, which would start flagging
#   changelog/ADR prose again. `_is_historical_path()` is a SECOND, defensive
#   layer on top of that enumeration -- it refuses to scan any path whose name
#   contains "changelog" or that sits under a `docs/adr/` directory, so that
#   if `README_RELPATHS` is ever carelessly widened to include a historical
#   document, the historical-record property still holds instead of silently
#   breaking.
# OUTPUTS:
#   stdout: JSON {"root", "source": {file, line, version}, "sites": [...],
#                 "mismatches": [...]}.
#   stderr: human-readable PASS/FAIL summary, one line per mismatch giving its
#           file:line, what was found and what was expected.
# EXIT CODES: 0 every checked site agrees with the source -> COMPLETED ;
#   1 at least one site disagrees -> FAILED ; 2 the source file, or a checked
#   file/pattern, is missing/unparseable -> BLOCKED.
# PRECONDITIONS: --root exists and contains a `.python-version` file holding an
#   exact three-part version (e.g. "3.13.13").
# DETERMINISM NOTE: deterministic; fixed regexes; sites listed and reported in
#   the declaration order above; no time/random/network.
#
# ## Principles Applied
# Inherited: P1 (grounded in the user's "one parametric version source"
#   decision), P2, P3 (entrypoint + I/O), P4, P6 (stdlib only), P7, P9 (one
#   job: version-pin agreement), P10 (exit->status), P11 (script vehicle),
#   P12 (every enumerated site checked, at its own precision, file+line
#   reported), P13.
# Custom: (none)
#
# SOURCES: user decision (Python 3.13.13 everywhere, ONE parametric source =
#   `.python-version`; install floor ">=3.13"); design-docs/research/
#   research-ci-python-3-13-13-pins.md (CPython 3.13.13 real, released
#   2026-04-07, bugfix-supported until 2029-10 vs 3.12's security-only track
#   ending 2028-10; python:3.13.13-slim-bookworm confirmed on Docker Hub,
#   last_updated 2026-05-20); asset-templates.md Script template. Sites 8-9
#   (README prose) added 2026-08-24: orchestrator finding that this gate's
#   6-site config scan missed the one place a user is most likely to read the
#   requirement -- both READMEs' "Python 3.12 or newer" / "Python 3.12 o mas
#   reciente" install line, in English and Spanish, left stale by a prior
#   version bump. Same failure class the gate exists to prevent.
# =============================================================================
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

SOURCE_RELPATH = ".python-version"
SOURCE_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)\s*$")


class Finding:
    """One mismatched pin site."""

    def __init__(
        self,
        site_id: str,
        file: str,
        line: int,
        found: str,
        expected: str,
        precision: str,
    ) -> None:
        self.site_id = site_id
        self.file = file
        self.line = line
        self.found = found
        self.expected = expected
        self.precision = precision

    def as_dict(self) -> dict:
        return {
            "site": self.site_id,
            "file": self.file,
            "line": self.line,
            "found": self.found,
            "expected": self.expected,
            "precision": self.precision,
        }


def _read_lines(path: Path) -> Optional[List[str]]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None


def _find_match(
    lines: List[str], pattern: "re.Pattern[str]"
) -> Optional[Tuple[int, "re.Match[str]"]]:
    for idx, line in enumerate(lines, start=1):
        m = pattern.search(line)
        if m:
            return idx, m
    return None


def _minor(version: Tuple[int, int, int]) -> Tuple[int, int]:
    return (version[0], version[1])


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# A README bullet/sentence is sometimes hard-wrapped by an editor, so the
# claim's trailing word can land on the NEXT physical line (observed live:
# "... and Python 3.12+\nare available." in both README.md and README.es.md).
# `bare_available` below therefore accepts, between the "+" and the verb
# phrase, either ordinary same-line whitespace OR exactly one line break with
# optional surrounding indent -- never a blank line (a real paragraph break),
# so a claim can never be assembled by matching across two unrelated
# sentences. That wrap fragment is written INLINE, as adjacent (juxtaposed,
# not `+`-concatenated) string literals within the same re.compile() call:
# `path_portability_check`'s regex-argument exemption is granted by AST
# parent link and only recognises a `re.compile(...)` call whose argument IS
# the literal Constant -- a `str1 + variable + str2` expression is a BinOp,
# not a Constant, and is not exempt (adjacent literals with no `+` between
# them, in contrast, are folded into one Constant by the parser itself, and
# are exempt). Keep every pattern below as one literal (or juxtaposed
# literals with no `+`) for exactly this reason.
#
# Deliberately narrow: two known, high-value prose SHAPES, not a general
# English/Spanish "this text is about a Python version requirement" detector.
#   requires_python_quoted -- a quoted `requires-python = ">=X.Y"` manifest
#     key echoed into prose. Structured data inside prose; the same pattern
#     already trusted for pyproject.toml itself (check_requires_python).
#   bare_or_newer -- "Python X.Y or newer/or later" (English) or "Python X.Y
#     o mas reciente/o posterior" (Spanish), the install-requirement phrasing
#     actually used in both READMEs' "### Requirements" section.
#   bare_available -- "Python X.Y+ ... are/is available" (English) or
#     "Python X.Y+ ... esten disponibles/esta disponible" (Spanish), the
#     platform-support-statement phrasing actually used in both READMEs'
#     closing paragraph. Requires the literal "+" (a bare "Python 3.12 is
#     available" without it is not a version-floor claim and is not matched).
# A differently-worded future claim (e.g. "you need at least Python 3.13",
# "Python >= 3.13 required") is NOT matched by design -- see the report's
# residual-risk statement; widen this list only with a newly OBSERVED, real
# phrasing, never a guessed general pattern.
CLAIM_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    (
        "requires_python_quoted",
        re.compile(r'requires-python\s*=\s*">=(\d+)\.(\d+)"'),
    ),
    (
        "bare_or_newer",
        re.compile(
            r"Python\s+(\d+)\.(\d+)\+?\s*"
            r"(?:or newer|or later|o m[aá]s reciente|o posterior)\b"
        ),
    ),
    (
        "bare_available",
        re.compile(
            r"Python\s+(\d+)\.(\d+)\+(?:[ \t]+|[ \t]*\n[ \t]*)"
            r"(?:are available|is available|est[eé]n disponibles|"
            r"est[aá] disponible)\b"
        ),
    ),
]

# Defensive second layer, independent of what is actually enumerated in
# README_RELPATHS today -- see EXCLUSION NOTE at the top of this file.
_HISTORICAL_PATH_MARKERS = ("changelog",)


def _is_historical_path(relpath: str) -> bool:
    lower = relpath.lower().replace("\\", "/")
    if "/docs/adr/" in ("/" + lower):
        return True
    for marker in _HISTORICAL_PATH_MARKERS:
        if marker in lower:
            return True
    return False


README_RELPATHS: Tuple[str, ...] = ("README.md", "README.es.md")


def check_readme_prose(
    root: Path, source: Tuple[int, int, int], relpath: str
) -> Tuple[List[dict], List[Finding]]:
    """Scan one user-facing README for the two known version-claim shapes.

    Soft site: a claim that is FOUND and WRONG is a real Finding (fails the
    gate); a claim that is simply not present is informational only -- it is
    never a Finding, so it can never block or fail the gate by itself. Only
    an unreadable file is a hard Finding (mirrors sites 1-7's convention).
    """
    sites: List[dict] = []
    findings: List[Finding] = []
    if _is_historical_path(relpath):
        return sites, findings
    text = _read_text(root / relpath)
    if text is None:
        site_id = "readme_prose:%s" % relpath
        findings.append(Finding(site_id, relpath, 0, "(file unreadable)", "", "minor"))
        return sites, findings
    expected = "%d.%d" % _minor(source)
    for pattern_name, pattern in CLAIM_PATTERNS:
        for m in pattern.finditer(text):
            found_minor = (int(m.group(1)), int(m.group(2)))
            found_str = "%d.%d" % found_minor
            line_no = _line_no(text, m.start())
            site_id = "readme_prose:%s:%s" % (relpath, pattern_name)
            sites.append(
                {
                    "id": site_id,
                    "file": relpath,
                    "line": line_no,
                    "found": found_str,
                    "precision": "minor",
                }
            )
            if found_minor != _minor(source):
                findings.append(
                    Finding(site_id, relpath, line_no, found_str, expected, "minor")
                )
    return sites, findings


def check_requires_python(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "pyproject.toml"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding(
            "requires_python", relpath, 0, "(file unreadable)", "", "minor"
        )
    pattern = re.compile(r'requires-python\s*=\s*">=(\d+)\.(\d+)"')
    hit = _find_match(lines, pattern)
    expected = "%d.%d" % _minor(source)
    if hit is None:
        return None, Finding(
            "requires_python",
            relpath,
            0,
            "(pattern not found)",
            ">=" + expected,
            "minor",
        )
    line_no, m = hit
    found_minor = (int(m.group(1)), int(m.group(2)))
    found_str = ">=%d.%d" % found_minor
    site = {
        "id": "requires_python",
        "file": relpath,
        "line": line_no,
        "found": found_str,
        "precision": "minor",
    }
    if found_minor != _minor(source):
        return site, Finding(
            "requires_python", relpath, line_no, found_str, ">=" + expected, "minor"
        )
    return site, None


def check_classifier(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "pyproject.toml"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding("classifier", relpath, 0, "(file unreadable)", "", "minor")
    pattern = re.compile(r'"Programming Language :: Python :: (\d+)\.(\d+)"')
    hit = _find_match(lines, pattern)
    expected = "%d.%d" % _minor(source)
    if hit is None:
        return None, Finding(
            "classifier", relpath, 0, "(pattern not found)", expected, "minor"
        )
    line_no, m = hit
    found_minor = (int(m.group(1)), int(m.group(2)))
    found_str = "%d.%d" % found_minor
    site = {
        "id": "classifier",
        "file": relpath,
        "line": line_no,
        "found": found_str,
        "precision": "minor",
    }
    if found_minor != _minor(source):
        return site, Finding(
            "classifier", relpath, line_no, found_str, expected, "minor"
        )
    return site, None


def check_mypy(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "pyproject.toml"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding(
            "mypy_python_version", relpath, 0, "(file unreadable)", "", "minor"
        )
    pattern = re.compile(r'python_version\s*=\s*"(\d+)\.(\d+)"')
    hit = _find_match(lines, pattern)
    expected = "%d.%d" % _minor(source)
    if hit is None:
        return None, Finding(
            "mypy_python_version", relpath, 0, "(pattern not found)", expected, "minor"
        )
    line_no, m = hit
    found_minor = (int(m.group(1)), int(m.group(2)))
    found_str = "%d.%d" % found_minor
    site = {
        "id": "mypy_python_version",
        "file": relpath,
        "line": line_no,
        "found": found_str,
        "precision": "minor",
    }
    if found_minor != _minor(source):
        return site, Finding(
            "mypy_python_version", relpath, line_no, found_str, expected, "minor"
        )
    return site, None


def check_black(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "pyproject.toml"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding(
            "black_target_version", relpath, 0, "(file unreadable)", "", "minor"
        )
    # Black's target-version tokens concatenate major+minor with no separator:
    # "py313" == 3.13, "py312" == 3.12. A minor version >=100 would be
    # ambiguous under this token scheme, but Python's own minor series is
    # nowhere near that, so the single-digit-major assumption is safe today.
    pattern = re.compile(r'target-version\s*=\s*\[\s*"py(\d)(\d+)"\s*\]')
    hit = _find_match(lines, pattern)
    expected_token = "py%d%d" % source[0:2]
    if hit is None:
        return None, Finding(
            "black_target_version",
            relpath,
            0,
            "(pattern not found)",
            expected_token,
            "minor",
        )
    line_no, m = hit
    found_minor = (int(m.group(1)), int(m.group(2)))
    found_token = "py%s%s" % (m.group(1), m.group(2))
    site = {
        "id": "black_target_version",
        "file": relpath,
        "line": line_no,
        "found": found_token,
        "precision": "minor",
    }
    if found_minor != _minor(source):
        return site, Finding(
            "black_target_version",
            relpath,
            line_no,
            found_token,
            expected_token,
            "minor",
        )
    return site, None


def check_dockerfile(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "deploy/Dockerfile"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding(
            "dockerfile_base", relpath, 0, "(file unreadable)", "", "exact"
        )
    pattern = re.compile(r"FROM\s+python:(\d+)\.(\d+)\.(\d+)-slim-bookworm")
    hit = _find_match(lines, pattern)
    expected = "%d.%d.%d-slim-bookworm" % source
    if hit is None:
        return None, Finding(
            "dockerfile_base", relpath, 0, "(pattern not found)", expected, "exact"
        )
    line_no, m = hit
    found_exact = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    found = "%d.%d.%d-slim-bookworm" % found_exact
    site = {
        "id": "dockerfile_base",
        "file": relpath,
        "line": line_no,
        "found": found,
        "precision": "exact",
    }
    if found_exact != source:
        return site, Finding(
            "dockerfile_base", relpath, line_no, found, expected, "exact"
        )
    return site, None


def check_systemd(
    root: Path, source: Tuple[int, int, int]
) -> Tuple[Optional[dict], Optional[Finding]]:
    relpath = "deploy/pixelart-sync.service"
    lines = _read_lines(root / relpath)
    if lines is None:
        return None, Finding(
            "systemd_venv_python", relpath, 0, "(file unreadable)", "", "minor"
        )
    pattern = re.compile(r"python(\d+)\.(\d+)\s+-m\s+venv")
    hit = _find_match(lines, pattern)
    expected = "%d.%d" % _minor(source)
    if hit is None:
        return None, Finding(
            "systemd_venv_python", relpath, 0, "(pattern not found)", expected, "minor"
        )
    line_no, m = hit
    found_minor = (int(m.group(1)), int(m.group(2)))
    found_str = "%d.%d" % found_minor
    site = {
        "id": "systemd_venv_python",
        "file": relpath,
        "line": line_no,
        "found": found_str,
        "precision": "minor",
    }
    if found_minor != _minor(source):
        return site, Finding(
            "systemd_venv_python", relpath, line_no, found_str, expected, "minor"
        )
    return site, None


CHECKS = [
    check_requires_python,
    check_classifier,
    check_mypy,
    check_black,
    check_dockerfile,
    check_systemd,
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    args = parser.parse_args(argv)
    root = Path(args.root)

    source_path = root / SOURCE_RELPATH
    source_lines = _read_lines(source_path)
    if source_lines is None or not source_lines:
        sys.stderr.write(
            "check_python_version: BLOCKED -- cannot read %s\n" % (source_path,)
        )
        return 2
    source_match = SOURCE_PATTERN.match(source_lines[0])
    if not source_match:
        sys.stderr.write(
            "check_python_version: BLOCKED -- %s:1 does not hold an exact "
            "three-part version (found %r); the source of truth must be a "
            "precise patch pin, e.g. '3.13.13'.\n" % (source_path, source_lines[0])
        )
        return 2
    source_version = (
        int(source_match.group(1)),
        int(source_match.group(2)),
        int(source_match.group(3)),
    )
    source_version_str = "%d.%d.%d" % source_version

    sites: List[dict] = []
    findings: List[Finding] = []
    blocked = False
    for check in CHECKS:
        site, finding = check(root, source_version)
        if site is not None:
            sites.append(site)
        if finding is not None:
            findings.append(finding)
            if finding.found in ("(file unreadable)", "(pattern not found)"):
                blocked = True

    # Sites 8-9 (README prose, soft): an absent claim contributes no Finding
    # at all, by construction of check_readme_prose -- see that function's
    # docstring. Only "(file unreadable)" blocks; a genuine version mismatch
    # still fails (findings is non-empty) exactly like the hard sites above.
    for readme_relpath in README_RELPATHS:
        readme_sites, readme_findings = check_readme_prose(
            root, source_version, readme_relpath
        )
        sites.extend(readme_sites)
        findings.extend(readme_findings)
        for finding in readme_findings:
            if finding.found == "(file unreadable)":
                blocked = True

    result = {
        "root": str(root),
        "source": {
            "file": SOURCE_RELPATH,
            "line": 1,
            "version": source_version_str,
        },
        "sites": sites,
        "mismatches": [f.as_dict() for f in findings],
    }
    print(json.dumps(result, indent=2, sort_keys=True))

    if blocked:
        sys.stderr.write(
            "check_python_version: BLOCKED -- %d site(s) missing/unreadable/"
            "unparseable (see 'mismatches' with found='(file unreadable)' or "
            "'(pattern not found)').\n"
            % sum(
                1
                for f in findings
                if f.found in ("(file unreadable)", "(pattern not found)")
            )
        )
        return 2
    if findings:
        sys.stderr.write(
            "check_python_version: FAILED -- %d site(s) disagree with %s "
            "(source=%s):\n" % (len(findings), SOURCE_RELPATH, source_version_str)
        )
        for f in findings:
            sys.stderr.write(
                "  %s:%d  [%s]  found=%r expected=%r (%s precision)\n"
                % (f.file, f.line, f.site_id, f.found, f.expected, f.precision)
            )
        return 1

    sys.stderr.write(
        "check_python_version: all %d site(s) agree with %s (source=%s).\n"
        % (len(sites), SOURCE_RELPATH, source_version_str)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
