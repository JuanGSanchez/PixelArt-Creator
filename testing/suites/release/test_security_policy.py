# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tests of the published security policy, ``SECURITY.md``.

Two statements are checked, each on the real files and on planted ones.

* The version it names as current. Every statement in ``SECURITY.md`` that names
  a current version must equal the version ``pyproject.toml`` declares; a scan of
  the file with the product's vocabulary token list (the one
  ``scripts/check_vocabulary_regrowth.py`` applies to the tracked tree) finds no
  hit; and the file as it stood on ``main`` on 2026-11-14 (it named 0.3.1), planted
  beside a later ``pyproject.toml``, fails and names the stale version.
* The policy for 0.4.0. ``SECURITY.md`` names 0.4.0, states that its security
  support has ended, and states that only the latest released version receives
  security fixes. A planted file saying that 0.4.0 receives security fixes fails and
  names the statement, and the ``[0.4.1]`` entry of ``CHANGELOG.md`` is read and
  must agree with the file on 0.4.0 (the last release that installs on the older
  Python, and the newer Python every later release needs).

A check that examined nothing proves nothing, so each check fails when it finds
nothing to examine, and each planted case runs the same function the real-file case
runs, so a function that cannot tell a stale file from a true one fails at once.

The real-file cases read the repository root. Three environment variables point
them at other copies (``SECURITY_POLICY_FILE``, ``SECURITY_POLICY_PYPROJECT`` and
``SECURITY_POLICY_CHANGELOG``); with none set, the committed files are read. The
files are only ever READ; no case writes anything.

This module's own text is scanned by the same vocabulary gate it uses, so every
planted token is joined at run time from two fragments and never written intact.
"""

from __future__ import annotations

import functools
import importlib.util
import os
import re
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

#: Repo root: testing/suites/release/test_security_policy.py -> parents[3].
REPO_ROOT = Path(__file__).resolve().parents[3]

#: The entry of CHANGELOG.md that states the Python floor and names 0.4.0.
CHANGELOG_ENTRY_VERSION = "0.4.1"
#: The release whose security support the policy states has ended.
ENDED_VERSION = "0.4.0"

#: SECURITY.md as it stood on ``main`` on 2026-11-14. It names 0.3.1 as current and
#: states no policy for 0.4.0.
MAIN_SECURITY_2026_11_14 = """\
# Security Policy

## Supported Versions

PixelArt Creator is currently in **0.x**, pre-1.0 development
(`pyproject.toml` reports `version = "0.3.1"`, classified
`Development Status :: 3 - Alpha`). Only the **latest released 0.x
version** is supported with security fixes; there is no long-term-support
branch at this stage.

| Version        | Supported          |
| -------------- | ------------------- |
| Latest 0.x     | :white_check_mark:  |
| Older releases | :x:                  |

## Reporting a Vulnerability

Please **do not** open a public issue for a security vulnerability.

Report it privately using GitHub's **Private vulnerability reporting**
feature, from this repository's **Security** tab ("Report a vulnerability").
That channel goes directly to the maintainer and is not visible publicly
until a fix is available.

Please include, as far as you can:

- a description of the vulnerability and its potential impact,
- steps to reproduce it (a minimal project file, script, or input),
- the affected version/commit and your OS.

## What to expect

This project is maintained by one person. Reports will be acknowledged as
soon as practical, and a fix or mitigation will be prioritized for
confirmed vulnerabilities. There is no guaranteed response-time SLA at this
stage of the project, but private reports are read.

If a report turns out not to be exploitable or is out of scope, you will
still get a reply explaining why.
"""

#: A small policy that satisfies every check; the planted cases below change one
#: statement of it at a time.
GOOD_POLICY = """\
# Security Policy

## Supported Versions

(`pyproject.toml` reports `version = "0.7.0"`). Only the **latest released
version** receives security fixes. The latest released version is **0.7.0**.

| Version        | Supported           |
| -------------- | ------------------- |
| 0.7.0 (latest) | :white_check_mark:  |
| Older releases | :x:                 |

### Version 0.4.0

Security support for **0.4.0** has ended. It was the last release that
installs on Python 3.13; every later release needs Python 3.14 or newer.
"""

#: A changelog with the entry the policy is compared against.
GOOD_CHANGELOG = """\
# Changelog

## [Unreleased]

### Added

- Something new.

## [0.4.1] - 2026-11-14

### Changed

- **BREAKING:** the minimum supported Python is raised from 3.13 to **3.14**.
  To upgrade, use Python 3.14 or newer, or stay on 0.4.0, the last release that
  installs on Python 3.13.

## [0.4.0] - 2026-10-23

### Added

- An earlier thing.
"""


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    """The file's text, decoded as UTF-8 from its bytes."""
    return path.read_bytes().decode("utf-8")


def _path(variable: str, default: Path) -> Path:
    """The path named by ``variable`` when it is set, else ``default``."""
    override = os.environ.get(variable)
    return Path(override) if override else default


@pytest.fixture
def security_path() -> Path:
    return _path("SECURITY_POLICY_FILE", REPO_ROOT / "SECURITY.md")


@pytest.fixture
def pyproject_path() -> Path:
    return _path("SECURITY_POLICY_PYPROJECT", REPO_ROOT / "pyproject.toml")


@pytest.fixture
def changelog_path() -> Path:
    return _path("SECURITY_POLICY_CHANGELOG", REPO_ROOT / "CHANGELOG.md")


def declared_version(pyproject_text: str) -> str:
    """The ``[project] version`` of a ``pyproject.toml`` text."""
    return str(tomllib.loads(pyproject_text)["project"]["version"])


def _pyproject_declaring(version: str) -> str:
    """A planted ``pyproject.toml`` text that declares ``version``."""
    return f'[project]\nname = "planted"\nversion = "{version}"\n'


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")


def _fail(message: str) -> None:
    """Fail with an ``AssertionError`` that carries ``message``."""
    raise AssertionError(message)


def _plain(text: str) -> str:
    """The text with line endings made LF and emphasis and code marks removed."""
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("**", "")
        .replace("`", "")
    )


def _flat(text: str) -> str:
    """The text with every run of whitespace, line breaks included, made one space."""
    return re.sub(r"\s+", " ", text).strip()


def _units(text: str) -> list[str]:
    """Split a Markdown text into units: a heading, a table row, or a paragraph.

    A paragraph is a run of prose lines joined by single spaces, so a sentence
    wrapped over several lines is one sentence.
    """
    units: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            units.append(_flat(" ".join(run)))
            run.clear()

    for raw in _plain(text).split("\n"):
        line = raw.strip()
        if not line:
            flush()
        elif line.startswith(("#", "|")):
            flush()
            units.append(_flat(line))
        elif line.startswith(("- ", "* ")):
            flush()
            run.append(line)
        else:
            run.append(line)
    flush()
    return units


def _sentences(text: str) -> list[str]:
    """Every sentence of the text; wrapped lines joined, rows and headings whole."""
    found: list[str] = []
    for unit in _units(text):
        found.extend(s.strip() for s in _SENTENCE_BREAK.split(unit) if s.strip())
    return found


def _names(text: str, version: str) -> bool:
    """Whether ``text`` names exactly ``version`` (not a longer number)."""
    start = 0
    while (at := text.find(version, start)) != -1:
        before = text[at - 1 : at]
        after = text[at + len(version) : at + len(version) + 2]
        continues_before = before.isdigit() or before == "."
        continues_after = after[:1].isdigit() or (
            after[:1] == "." and after[1:].isdigit()
        )
        if not continues_before and not continues_after:
            return True
        start = at + 1
    return False


# ---------------------------------------------------------------------------
# The version named as current
# ---------------------------------------------------------------------------

#: The statements that name a version as the current one, each with the wording it
#: is recognised by. A new way of naming the current version belongs here.
CURRENT_STATEMENTS = (
    (
        "the version the file says pyproject.toml reports",
        re.compile(r'version\s*=\s*"(\d+\.\d+\.\d+)"'),
    ),
    (
        "the latest released version",
        re.compile(r"latest\s+released\s+version\s+is\s+(\d+\.\d+\.\d+)"),
    ),
    (
        "the table row marked latest",
        re.compile(r"\|\s*(\d+\.\d+\.\d+)\s*\(latest\)"),
    ),
)


def current_versions(security_text: str) -> list[tuple[int, str, str]]:
    """Every (line, statement, version) where the text names a version as current."""
    plain = _plain(security_text)
    found: list[tuple[int, str, str]] = []
    for label, pattern in CURRENT_STATEMENTS:
        for match in pattern.finditer(plain):
            found.append(
                (plain.count("\n", 0, match.start()) + 1, label, match.group(1))
            )
    return sorted(found)


def assert_current_versions_match(
    security_text: str, declared: str
) -> list[tuple[int, str, str]]:
    """Fail unless every current version the text names equals ``declared``.

    Fails, too, when the text names no current version at all: a file that says
    nothing about it cannot be shown to agree.
    """
    found = current_versions(security_text)
    if not found:
        _fail(
            "SECURITY.md names no current version, "
            "so none can be compared with pyproject.toml"
        )
    stale = [
        (line, label, version) for line, label, version in found if version != declared
    ]
    if stale:
        named = "; ".join(
            f"line {line} ({label}) says {version}" for line, label, version in stale
        )
        _fail(
            f"SECURITY.md names a stale current version: {named}; "
            f"pyproject.toml declares {declared}"
        )
    return found


# ---------------------------------------------------------------------------
# The product's vocabulary token list
# ---------------------------------------------------------------------------


@functools.cache
def _scanner() -> ModuleType:
    """The vocabulary gate's module, loaded from ``scripts/`` by path."""
    path = REPO_ROOT / "scripts" / "check_vocabulary_regrowth.py"
    spec = importlib.util.spec_from_file_location(
        "security_policy_vocabulary_scan", path
    )
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vocabulary_findings(text: str) -> list[dict[str, object]]:
    """Every hit of the product's token list, attribution family included."""
    findings: list[dict[str, object]] = _scanner().scoped_text_findings(
        "SECURITY.md", text, False
    )
    return findings


def _planted_tokens() -> dict[str, str]:
    """One token per family of the list, each joined here so none is written intact."""
    return {
        "agent id": "AG" + "T-" + "12",
        "record id": "RE" + "C-" + "3",
        "open question id": "O" + "Q-" + "7",
        "bare task id": "T" + "-" + "21",
        "deviation id": "DE" + "V-" + "9",
        "work package id": "W" + "P-" + "4",
        "design folder": "design" + "-docs/notes",
        "report file": "subagent" + "-report-x.md",
    }


# ---------------------------------------------------------------------------
# The policy for the ended version
# ---------------------------------------------------------------------------

_ENDED = re.compile(
    r"\bsupport\b.*?\b(?:has|have)\s+ended\b|\bno\s+longer\s+(?:receives?|supported)\b",
    re.IGNORECASE,
)
_RECEIVES = re.compile(
    r"\b(?:receives?|gets?|is\s+given|are\s+given|continues?\s+to\s+receive"
    r"|is\s+(?:still\s+)?supported|remains?\s+supported)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(?:no\s+longer|not|never|ended|without)\b", re.IGNORECASE)
_ONLY_LATEST = re.compile(
    r"\bonly\s+the\s+latest\s+released\s+(?:\S+\s+)?version\b.*?\bsecurity\s+fixes\b",
    re.IGNORECASE,
)


def _claims_fixes(sentence: str) -> bool:
    """Whether the sentence says the version it names receives security fixes."""
    return bool(_RECEIVES.search(sentence)) and not _NEGATION.search(sentence)


def assert_ended_version_policy(
    security_text: str, version: str = ENDED_VERSION
) -> list[str]:
    """Fail unless the text names ``version`` and states that its support ended.

    Fails on any sentence that says ``version`` receives security fixes, and names
    that sentence. Returns the sentences that name ``version``.
    """
    named = [s for s in _sentences(security_text) if _names(s, version)]
    if not named:
        _fail(f"SECURITY.md does not name {version}")
    claims = [s for s in named if _claims_fixes(s)]
    if claims:
        _fail(
            f"SECURITY.md states that {version} receives security fixes: {claims[0]!r}"
        )
    if not any(_ENDED.search(s) for s in named):
        _fail(
            f"SECURITY.md names {version} but does not state that "
            "its security support has ended"
        )
    return named


def assert_only_latest_receives_fixes(security_text: str) -> str:
    """Fail unless the text states that only the latest released version is fixed."""
    for sentence in _sentences(security_text):
        if _ONLY_LATEST.search(sentence):
            return sentence
    _fail(
        "SECURITY.md does not state that only the latest released version "
        "receives security fixes"
    )
    return ""


# ---------------------------------------------------------------------------
# The changelog entry
# ---------------------------------------------------------------------------

# The 0.4.0 written out, equal to ENDED_VERSION: a pattern keeps its escapes whole.
_LAST_ON = re.compile(
    r"(?<![\d.])0\.4\.0,?\s+the\s+last\s+release\s+that\s+installs"
    r"\s+on\s+Python\s+(\d+\.\d+)"
)
_RAISED = re.compile(r"raised\s+from\s+(\d+\.\d+)\s+to\s+(\d+\.\d+)")
_SECURITY_LAST_ON = re.compile(
    r"last\s+release\s+that\s+installs\s+on\s+Python\s+(\d+\.\d+)"
)
_SECURITY_NEEDS = re.compile(r"needs\s+Python\s+(\d+\.\d+)\s+or\s+newer")


def changelog_entry(changelog_text: str, version: str) -> tuple[str, str]:
    """The heading line and the body of the ``[version]`` entry of a changelog."""
    lines = changelog_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    heading = re.compile(rf"^##\s*\[{re.escape(version)}\]")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        _fail(f"CHANGELOG.md has no [{version}] entry")
    assert start is not None
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## [")),
        len(lines),
    )
    return lines[start], "\n".join(lines[start + 1 : end])


def _block_naming(security_text: str, version: str) -> str:
    """The text about ``version``: from its first mention to the next heading."""
    units = _units(security_text)
    start = next(
        (
            i
            for i, u in enumerate(units)
            if _names(u, version) and not u.startswith("|")
        ),
        None,
    )
    if start is None:
        return ""
    block = [units[start]]
    for unit in units[start + 1 :]:
        if unit.startswith("#") and not _names(unit, version):
            break
        block.append(unit)
    return " ".join(block)


def assert_agrees_with_changelog(security_text: str, entry_body: str) -> dict[str, str]:
    """Fail unless SECURITY.md and the changelog entry agree on the ended version.

    The entry gives two facts: the last release that installs on the older Python,
    and the newer Python every later release needs. SECURITY.md's text about the
    ended version must state both, and state no other. The entry itself must not
    say that the ended version receives security fixes.
    """
    entry = _flat(_plain(entry_body))
    last_on = _LAST_ON.search(entry)
    raised = _RAISED.search(entry)
    if last_on is None or raised is None:
        _fail(
            f"the [{CHANGELOG_ENTRY_VERSION}] entry no longer states the last release "
            "on the older Python and the new floor, "
            f"so {ENDED_VERSION} cannot be compared"
        )
    assert last_on is not None and raised is not None
    claims = [
        s
        for s in _sentences(entry_body)
        if _names(s, ENDED_VERSION) and _claims_fixes(s)
    ]
    if claims:
        _fail(
            f"the [{CHANGELOG_ENTRY_VERSION}] entry states that {ENDED_VERSION} "
            f"receives security fixes: {claims[0]!r}"
        )
    block = _flat(_block_naming(security_text, ENDED_VERSION))
    if not block:
        _fail(
            f"SECURITY.md has no text about {ENDED_VERSION} to compare with the entry"
        )
    facts = {
        "the last release on the older Python": (_SECURITY_LAST_ON, last_on.group(1)),
        "the Python every later release needs": (_SECURITY_NEEDS, raised.group(2)),
    }
    agreed: dict[str, str] = {}
    for label, (pattern, expected) in facts.items():
        stated = {m.group(1) for m in pattern.finditer(block)}
        if stated != {expected}:
            _fail(
                f"SECURITY.md and the [{CHANGELOG_ENTRY_VERSION}] entry disagree on "
                f"{ENDED_VERSION}, {label}: the entry says Python {expected}, "
                f"SECURITY.md says {sorted(stated) or 'nothing'}"
            )
        agreed[label] = expected
    return agreed


# ---------------------------------------------------------------------------
# The current version
# ---------------------------------------------------------------------------


def test_every_current_version_security_md_names_equals_pyproject(
    security_path: Path, pyproject_path: Path
) -> None:
    """Every statement naming a current version equals the declared version."""
    declared = declared_version(_read(pyproject_path))
    found = assert_current_versions_match(_read(security_path), declared)
    print(f"read {security_path} and {pyproject_path}: declared {declared}")
    for line, label, version in found:
        print(f"  line {line}: {label} -> {version}")
    assert len(found) >= 1


def test_security_md_scan_with_the_vocabulary_token_list_finds_no_hit(
    security_path: Path,
) -> None:
    """The product's token list finds nothing in the policy file."""
    scanner = _scanner()
    families = list(scanner.PATTERNS)
    assert families, "the vocabulary gate exposes an empty token list"
    text = _read(security_path)
    lines = len(text.replace("\r\n", "\n").split("\n"))
    findings = vocabulary_findings(text)
    print(f"scanned {security_path}: {lines} lines, {len(families)} token families")
    assert lines > 1
    assert findings == [], f"vocabulary hits in SECURITY.md: {findings}"


def test_stale_policy_from_main_beside_a_later_pyproject_fails_naming_the_version() -> (
    None
):
    """The file as on ``main`` on 2026-11-14 fails against a later declared version."""
    assert "0.3.1" in MAIN_SECURITY_2026_11_14
    with pytest.raises(AssertionError) as excinfo:
        assert_current_versions_match(
            MAIN_SECURITY_2026_11_14, declared_version(_pyproject_declaring("0.4.1"))
        )
    print(excinfo.value)
    message = str(excinfo.value)
    assert "stale current version" in message
    assert "says 0.3.1" in message
    assert "pyproject.toml declares 0.4.1" in message


def test_one_stale_statement_among_current_ones_fails_naming_it() -> None:
    """Every current-version statement is held to the declared version."""
    mixed = GOOD_POLICY.replace("version is **0.7.0**", "version is **0.6.9**")
    assert mixed != GOOD_POLICY
    with pytest.raises(AssertionError) as excinfo:
        assert_current_versions_match(mixed, "0.7.0")
    message = str(excinfo.value)
    assert "says 0.6.9" in message
    assert "latest released version" in message
    assert "says 0.7.0" not in message


def test_a_policy_naming_no_current_version_fails() -> None:
    """A file that names no current version cannot pass by saying nothing."""
    with pytest.raises(AssertionError, match="names no current version"):
        assert_current_versions_match(
            "# Security Policy\n\nReport privately.\n", "0.7.0"
        )


def test_a_pair_that_agrees_passes(security_path: Path) -> None:
    """The real policy beside a pyproject declaring the version it names passes.

    The planted ``pyproject.toml`` declares the one version the file itself names
    as current, so this shows the file is consistent with itself, whatever the
    repository's own ``pyproject.toml`` reads at the moment.
    """
    text = _read(security_path)
    named = {version for _, _, version in current_versions(text)}
    assert (
        len(named) == 1
    ), f"SECURITY.md names more than one current version: {sorted(named)}"
    (version,) = named
    print(f"planted pyproject.toml declares {version}")
    found = assert_current_versions_match(
        text, declared_version(_pyproject_declaring(version))
    )
    assert len(found) >= 1


def test_the_good_policy_agrees_with_a_matching_pyproject() -> None:
    """Control: the small satisfying policy passes against the version it names."""
    assert assert_current_versions_match(GOOD_POLICY, "0.7.0")


# ---------------------------------------------------------------------------
# The vocabulary scan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("family", sorted(_planted_tokens()))
def test_scan_detects_a_planted_token_of_every_family(family: str) -> None:
    """Control: the scan is not blind to any token family."""
    token = _planted_tokens()[family]
    planted = GOOD_POLICY + f"\nSee {token} for details.\n"
    findings = vocabulary_findings(planted)
    print(f"{family}: {token!r} -> {[(f['pattern'], f['line']) for f in findings]}")
    hits = [f for f in findings if f["token"] and str(f["token"]) in token]
    assert hits, f"{family} was not detected"
    planted_line = planted.count("\n", 0, planted.index(token)) + 1
    assert {f["line"] for f in hits} == {planted_line}


def test_scan_finds_nothing_in_a_clean_policy() -> None:
    """Control: the scan does not flag a clean text."""
    assert vocabulary_findings(GOOD_POLICY) == []
    assert vocabulary_findings(MAIN_SECURITY_2026_11_14) == []


# ---------------------------------------------------------------------------
# The policy for 0.4.0
# ---------------------------------------------------------------------------


def test_security_md_names_0_4_0_and_states_its_support_ended(
    security_path: Path,
) -> None:
    """The policy names 0.4.0 and states that its security support has ended."""
    named = assert_ended_version_policy(_read(security_path))
    print(f"read {security_path}")
    for sentence in named:
        print(f"  names {ENDED_VERSION}: {sentence}")


def test_security_md_states_only_the_latest_version_receives_fixes(
    security_path: Path,
) -> None:
    """The policy states that only the latest released version receives fixes."""
    sentence = assert_only_latest_receives_fixes(_read(security_path))
    print(f"read {security_path}: {sentence}")


def test_security_md_agrees_with_the_changelog_entry_on_0_4_0(
    security_path: Path, changelog_path: Path
) -> None:
    """SECURITY.md and the [0.4.1] entry agree on what 0.4.0 was and what followed."""
    heading, body = changelog_entry(_read(changelog_path), CHANGELOG_ENTRY_VERSION)
    agreed = assert_agrees_with_changelog(_read(security_path), body)
    print(f"read {security_path} and {changelog_path}, entry {heading!r}")
    for label, python in agreed.items():
        print(f"  agree on {label}: Python {python}")
    assert len(agreed) == 2


def test_the_policy_from_main_states_no_policy_for_0_4_0() -> None:
    """The file as on ``main`` on 2026-11-14 does not name 0.4.0, so the check fails."""
    with pytest.raises(AssertionError) as excinfo:
        assert_ended_version_policy(MAIN_SECURITY_2026_11_14)
    assert "does not name 0.4.0" in str(excinfo.value)


def test_a_policy_saying_0_4_0_receives_fixes_fails_naming_the_statement() -> None:
    """A planted file that says 0.4.0 receives security fixes fails and quotes it."""
    statement = "Version 0.4.0 still receives security fixes."
    planted = GOOD_POLICY.replace(
        "Security support for **0.4.0** has ended.", statement
    )
    assert statement in planted
    with pytest.raises(AssertionError, match="receives security fixes") as excinfo:
        assert_ended_version_policy(planted)
    assert statement in str(excinfo.value)


def test_a_policy_naming_0_4_0_without_stating_the_end_fails() -> None:
    """Naming 0.4.0 is not enough: the end of its support must be stated."""
    planted = GOOD_POLICY.replace(
        "Security support for **0.4.0** has ended.",
        "Version 0.4.0 is an older release.",
    )
    assert planted != GOOD_POLICY
    with pytest.raises(
        AssertionError, match="does not state that its security support has ended"
    ):
        assert_ended_version_policy(planted)


def test_a_sentence_about_0_4_0_that_denies_fixes_is_not_a_claim_of_fixes() -> None:
    """Control: 'no longer receives security fixes' is not read as 'receives'."""
    assert not _claims_fixes(
        "Staying on 0.4.0 means running a version that "
        "no longer receives security fixes."
    )
    assert _claims_fixes("0.4.0 receives security fixes.")


def test_a_policy_that_does_not_say_only_the_latest_is_fixed_fails() -> None:
    """The statement that only the latest release is fixed must be present."""
    planted = GOOD_POLICY.replace(
        "Only the **latest released\nversion** receives security fixes.",
        "Several releases receive security fixes.",
    )
    assert planted != GOOD_POLICY
    with pytest.raises(AssertionError, match="only the latest released version"):
        assert_only_latest_receives_fixes(planted)


def test_the_good_policy_satisfies_every_policy_check() -> None:
    """Control: the small satisfying policy passes the 0.4.0 checks."""
    assert assert_ended_version_policy(GOOD_POLICY)
    assert assert_only_latest_receives_fixes(GOOD_POLICY)
    _, body = changelog_entry(GOOD_CHANGELOG, CHANGELOG_ENTRY_VERSION)
    assert assert_agrees_with_changelog(GOOD_POLICY, body) == {
        "the last release on the older Python": "3.13",
        "the Python every later release needs": "3.14",
    }


def test_a_missing_changelog_entry_fails() -> None:
    """The [0.4.1] entry must exist to be read."""
    with pytest.raises(AssertionError, match=r"no \[0\.4\.1\] entry"):
        changelog_entry("# Changelog\n\n## [Unreleased]\n\n- Something.\n", "0.4.1")


def test_a_policy_that_disagrees_with_the_changelog_on_the_older_python_fails() -> None:
    """A planted file naming another last Python for 0.4.0 fails against the entry."""
    planted = GOOD_POLICY.replace("installs on Python 3.13", "installs on Python 3.12")
    assert planted != GOOD_POLICY
    _, body = changelog_entry(GOOD_CHANGELOG, CHANGELOG_ENTRY_VERSION)
    with pytest.raises(AssertionError, match="disagree"):
        assert_agrees_with_changelog(planted, body)


def test_a_policy_that_omits_the_newer_python_fails() -> None:
    """A planted file that does not state the Python every later release needs fails."""
    planted = GOOD_POLICY.replace(
        "; every later release needs Python 3.14 or newer.", "."
    )
    assert planted != GOOD_POLICY
    _, body = changelog_entry(GOOD_CHANGELOG, CHANGELOG_ENTRY_VERSION)
    with pytest.raises(AssertionError, match="nothing"):
        assert_agrees_with_changelog(planted, body)


def test_a_changelog_entry_that_says_0_4_0_receives_fixes_fails() -> None:
    """A planted entry that contradicts the policy is caught."""
    planted = GOOD_CHANGELOG.replace(
        "\n## [0.4.0] - 2026-10-23",
        "\n- Version 0.4.0 still receives security fixes.\n\n## [0.4.0] - 2026-10-23",
    )
    assert planted != GOOD_CHANGELOG
    _, body = changelog_entry(planted, CHANGELOG_ENTRY_VERSION)
    with pytest.raises(AssertionError) as excinfo:
        assert_agrees_with_changelog(GOOD_POLICY, body)
    assert "entry states that 0.4.0 receives security fixes" in str(excinfo.value)
    assert "Version 0.4.0 still receives security fixes." in str(excinfo.value)


def test_an_entry_that_states_neither_python_fact_fails() -> None:
    """With nothing to compare, the agreement check fails instead of passing."""
    with pytest.raises(AssertionError, match="cannot be compared"):
        assert_agrees_with_changelog(
            GOOD_POLICY, "- A change that says nothing of Python.\n"
        )


def test_the_two_texts_may_wrap_the_same_sentence_differently() -> None:
    """Control: line breaks inside a sentence do not change what it says."""
    wrapped = GOOD_POLICY.replace(
        "It was the last release that\ninstalls on Python 3.13;",
        "It was the\nlast release\nthat installs on\nPython 3.13;",
    )
    assert wrapped != GOOD_POLICY
    _, body = changelog_entry(GOOD_CHANGELOG, CHANGELOG_ENTRY_VERSION)
    assert assert_agrees_with_changelog(wrapped, body)
