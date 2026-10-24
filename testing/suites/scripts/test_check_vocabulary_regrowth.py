"""Contract tests for ``scripts/check_vocabulary_regrowth.py``.

Contract asserted here, taken verbatim from the script's own header:

    ENTRYPOINT: python scripts/check_vocabulary_regrowth.py [--root .]
                [--base-sha SHA --head-sha SHA]
                python scripts/check_vocabulary_regrowth.py [--root .]
                --paths PATH [PATH ...] [--vendor-names]
    EXIT CODES: 0 clean -> COMPLETED ; 1 finding(s) -> FAILED ;
        2 usage/environment error (including any zero denominator) -> BLOCKED.

The first half of the module pins the pull-request mode (``--root`` and the
commit range), which the scoped scan must leave exactly as it was. The second
half, from the section headed "Scoped scan", pins ``--paths``: every occurrence
reported, the AI-attribution family, the number of files scanned printed and
gated. Each scoped-scan case there is a function that drives the script on a
clean fixture and on a planted one; it is registered together with MUTANTS,
copies of the script with one guarded line altered so that the rule the case
defends is gone, and the module's generic tests run the case twice -- against
the real script it must hold, against each broken copy it must raise an
``AssertionError`` -- so a case that cannot tell a working script from a
broken one fails the suite at once.

Every fixture is a hand-built, throwaway git repository under ``tmp_path``,
never the real working tree -- the eight patterns are planted and committed
there, then the script is pointed at it via its own ``--root`` flag.

NOTE ON THIS FILE'S OWN SOURCE -- IT IS **NOT** ONE OF THE GATE'S EXCLUDED
PATHS (narrowed 2026-09-06, see the script's own module docstring,
"SELF-TRIPPING RESOLUTION" -- only ``scripts/check_vocabulary_regrowth.py``
itself is exempt). Every planted token below is therefore built by RUNTIME
STRING CONCATENATION via ``_token(prefix, suffix)``, two separate string
arguments that are only ever joined at RUN TIME -- never written already
joined, and never spelled out again afterwards in a comment or docstring
either -- so this test module's own tracked source contains no real, intact
instance of any of the eight patterns, and needs no exemption to stay clean
under the gate it tests. The one real, intact instance of each token exists
only inside the throwaway fixture files this test writes under ``tmp_path``
at run time, never in this file's own committed content. The same holds for
the AI-attribution strings the scoped-scan cases plant: each is joined from
fragments by ``_join`` at run time.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from .conftest import SCRIPTS_DIR, run_script

SCRIPT = "check_vocabulary_regrowth.py"


def _token(prefix, suffix):
    """Join `prefix` + `suffix` (suffix carries its own leading hyphen) at
    RUNTIME so the intact result never appears as a literal in this file's
    own source -- see the module docstring."""
    return prefix + suffix


# A single representative sample token, reused by several tests below that
# need "some real AGT-nn-shaped token" rather than testing the family itself
# (that is PLANTED's job). Built the same way, for the same reason.
_SAMPLE_TOKEN = _token("AGT", "-09")


# --------------------------------------------------------------------------- #
# Fixture helper: a throwaway git repository under tmp_path.
# --------------------------------------------------------------------------- #
def _git(repo, *args):
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
    return completed.stdout


def _init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    return repo


def _commit_all(repo, message):
    _git(repo, "add", "-A")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _write(repo, rel_path, content):
    full = repo / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# The essential pair: a clean tree exits 0.
# --------------------------------------------------------------------------- #
def test_clean_tree_exits_0(tmp_path):
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _commit_all(repo, "chore: seed clean tree")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []
    assert payload["scanned"]["files_examined"] > 0
    assert payload["scanned"]["commit_message_check"] == "skipped"
    assert "SKIPPED" in result.stderr  # loud, never silent


# --------------------------------------------------------------------------- #
# Each of the eight patterns is caught, planted one at a time and quoted.
# Tokens are built from (prefix, suffix) pairs via _token() -- never an
# intact literal in this file's own source (see module docstring).
# --------------------------------------------------------------------------- #
# The first element of each tuple is the pattern's own key, as reported in a
# finding's "pattern" field -- built via _token() like every planted token
# below, NEVER written already joined, since for the two literal families
# (unlike the six digit-suffix families, whose "-nn"/"-n" spelling is not
# itself a real instance) that key IS the literal pattern text.
PLANTED = [
    ("AGT-nn", "AGT", "-09"),
    ("REC-n", "REC", "-3"),
    ("OQ-n", "OQ", "-2"),
    ("T-nn(bare)", "T", "-12"),
    ("DEV-n", "DEV", "-4"),
    ("WP-n", "WP", "-7"),
    (_token("design", "-docs"), "design", "-docs"),
    (_token("subagent", "-report"), "subagent", "-report"),
]


@pytest.mark.parametrize(
    "pattern_name, prefix, suffix", PLANTED, ids=[p[0] for p in PLANTED]
)
def test_each_pattern_is_caught(tmp_path, pattern_name, prefix, suffix):
    token = _token(prefix, suffix)
    content = "note: " + token + " is mentioned here.\n"
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _write(repo, "planted.txt", content)
    _commit_all(repo, "test: plant %s occurrence" % pattern_name)

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["kind"] == "file"
    assert finding["pattern"] == pattern_name
    assert finding["file"] == "planted.txt"
    assert finding["token"] == token


# --------------------------------------------------------------------------- #
# The allowlisted product_boundary.py path checks do NOT trip it.
# --------------------------------------------------------------------------- #
def test_allowlisted_product_boundary_design_docs_checks_pass(tmp_path):
    design_docs = _token("design", "-docs")
    repo = _init_repo(tmp_path)
    _write(
        repo,
        "memory/product_boundary.py",
        '"""' + design_docs + ' check."""\n'
        'if (parent / "' + design_docs + '").is_dir():\n'
        "    pass\n",
    )
    _write(
        repo,
        "testing/product_boundary.py",
        '"""another ' + design_docs + ' check."""\n'
        'if (parent / "' + design_docs + '").is_dir():\n'
        "    pass\n",
    )
    _commit_all(repo, "chore: seed allowlisted product_boundary.py files")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []
    # Both files were still scanned and counted -- the allowlist suppresses
    # specific (path, pattern) hits, it does not exclude the path outright.
    assert payload["scanned"]["files_examined"] >= 2


def test_gitignore_naming_design_docs_is_excluded(tmp_path):
    """`.gitignore` legitimately NAMES the same directory pattern the
    allowlisted product_boundary.py checks above look for, as an ignore
    rule -- excluded outright, distinct from the allowlist mechanism
    above."""
    repo = _init_repo(tmp_path)
    _write(repo, ".gitignore", _token("design", "-docs") + "/\n")
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _commit_all(repo, "chore: seed .gitignore naming the excluded directory pattern")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []


def test_memory_graph_prefix_is_excluded(tmp_path):
    """Anything under `memory/graph/` is a generated store, excluded
    outright even when it happens to carry a token."""
    repo = _init_repo(tmp_path)
    _write(
        repo,
        "memory/graph/nodes.jsonl",
        '{"note": "' + _SAMPLE_TOKEN + ' mentioned"}\n',
    )
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _commit_all(repo, "chore: seed memory/graph store content")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []


# --------------------------------------------------------------------------- #
# SELF-TRIPPING RESOLUTION is NARROW (2026-09-06): only the gate's own source
# is excluded. Its test module and the CI step that wires it are NOT
# excluded, and must never become so by accident -- a planted token at either
# path must still be caught.
# --------------------------------------------------------------------------- #
def test_self_trip_exclusion_covers_only_the_scripts_own_file(tmp_path):
    """The ONE file the gate excludes by exact path -- its own source -- is
    never scanned, even when it carries a real token."""
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _write(
        repo,
        "scripts/check_vocabulary_regrowth.py",
        "# " + _SAMPLE_TOKEN + "\n",
    )
    _commit_all(repo, "chore: seed the gate's own excluded source file")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["findings"] == []


def test_ci_workflow_path_is_scanned_not_excluded(tmp_path):
    """PINS the narrowing: `.github/workflows/ci.yml` must be SCANNED, not
    skipped, so nobody re-adds a whole-file exemption for it later without
    this test going red. (Measured defect this guards against: a planted
    token committed into ci.yml under the ORIGINAL three-file allowlist
    scanned clean -- exactly the hole the original vocabulary cleanup
    closed.)"""
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _write(
        repo,
        ".github/workflows/ci.yml",
        "# owned by " + _SAMPLE_TOKEN + "\n",
    )
    _commit_all(repo, "chore: seed a token inside ci.yml")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["file"] == ".github/workflows/ci.yml"
    assert finding["pattern"] == "AGT-nn"
    assert finding["token"] == _SAMPLE_TOKEN


def test_own_test_module_path_is_scanned_not_excluded(tmp_path):
    """The gate's OWN test module path is likewise not exempt -- a token
    planted at that exact path (in a fixture repo, never this file) must
    still be caught."""
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _write(
        repo,
        "testing/suites/scripts/test_check_vocabulary_regrowth.py",
        "# " + _SAMPLE_TOKEN + "\n",
    )
    _commit_all(repo, "chore: seed a token inside the test module path")

    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert len(payload["findings"]) == 1
    finding = payload["findings"][0]
    assert finding["file"] == "testing/suites/scripts/test_check_vocabulary_regrowth.py"
    assert finding["pattern"] == "AGT-nn"
    assert finding["token"] == _SAMPLE_TOKEN


# --------------------------------------------------------------------------- #
# The zero-denominator case fails: a gate that scanned nothing has not
# passed.
# --------------------------------------------------------------------------- #
def test_zero_tracked_files_exits_2(tmp_path):
    repo = _init_repo(tmp_path)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "chore: empty init")

    result = run_script(SCRIPT, ["--root", str(repo)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "zero-files-examined"


def test_missing_root_exits_2(tmp_path):
    missing = tmp_path / "does-not-exist"
    result = run_script(SCRIPT, ["--root", str(missing)])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "root-not-found"


# --------------------------------------------------------------------------- #
# The bounded commit-message half: only the commits a pull request ADDS,
# never the whole history; a loud, explicit skip outside a pull request;
# never a silent pass on either half of a malformed range.
# --------------------------------------------------------------------------- #
def test_commit_message_token_in_range_is_caught(tmp_path):
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    base_sha = _commit_all(repo, "chore: seed base tree")
    _write(repo, "second.txt", "still nothing.\n")
    head_sha = _commit_all(
        repo, "fix: patch behaviour for " + _SAMPLE_TOKEN + " follow-up"
    )

    result = run_script(
        SCRIPT, ["--root", str(repo), "--base-sha", base_sha, "--head-sha", head_sha]
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 1, result.stderr
    assert payload["scanned"]["commit_message_check"] == "ran"
    assert payload["scanned"]["commit_messages_examined"] == 1
    commit_findings = [f for f in payload["findings"] if f["kind"] == "commit-message"]
    assert len(commit_findings) == 1
    assert commit_findings[0]["pattern"] == "AGT-nn"
    assert commit_findings[0]["token"] == _SAMPLE_TOKEN


def test_commit_message_check_skipped_loudly_without_a_range(tmp_path):
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    _commit_all(repo, "fix: patch behaviour for " + _SAMPLE_TOKEN + " follow-up")

    # No --base-sha/--head-sha: the commit carries a real token, but the
    # commit-message half is skipped (no range available) -- it must never
    # silently pass NOR silently fail the run over content it never examined.
    result = run_script(SCRIPT, ["--root", str(repo)])
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["scanned"]["commit_message_check"] == "skipped"
    assert payload["scanned"]["commit_messages_examined"] is None
    assert "SKIPPED" in result.stderr
    assert "not a pull_request run" in result.stderr


def test_half_specified_commit_range_is_a_usage_error_exit_2(tmp_path):
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    sha = _commit_all(repo, "chore: seed tree")

    result = run_script(SCRIPT, ["--root", str(repo), "--base-sha", sha])
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "half-specified-commit-range"


def test_zero_commit_range_exits_2(tmp_path):
    repo = _init_repo(tmp_path)
    _write(repo, "readme.txt", "Nothing to see here.\n")
    sha = _commit_all(repo, "chore: seed tree")

    result = run_script(
        SCRIPT, ["--root", str(repo), "--base-sha", sha, "--head-sha", sha]
    )
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"] == "zero-commits-examined"


# =========================================================================== #
# Scoped scan: ``--paths``
#
# Every case below builds a throwaway git repository under ``tmp_path``, plants
# files in it WITHOUT committing them unless the case is about committed
# content (``--paths`` lists untracked, non-ignored files too), and drives the
# script as a subprocess through its own flags. Planted tokens are joined from
# fragments at run time (see the module docstring).
# =========================================================================== #
def _join(*parts):
    """Join fragments at RUN TIME so the intact result is never in this file."""
    return "".join(parts)


_VENDOR_MODEL = _join("Clau", "de")  # the assistant vendor's model family
_VENDOR = _join("Anthro", "pic")  # the assistant vendor
_OTHER_VENDOR = _join("Chat", "GPT")
_PLANTED_ID = _token("AGT", "-07")
_SPACES_20 = " " * 20
_ADJ_LINE = '_ADJ_VERBS = "generated|written|translated|authored|drafted|produced'
_CHATBOT_TAIL = '|chatbot)" % (_VENDOR, _ALNUM, _ALNUM)'


class _Run(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def _run(script: Path, repo: Path, *args: str) -> _Run:
    """Run ``script`` (the real one or a broken copy) against ``repo``."""
    completed = subprocess.run(
        [sys.executable, str(script), "--root", str(repo), *args],
        cwd=str(repo.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return _Run(completed.returncode, completed.stdout, completed.stderr)


def _json(run: _Run) -> dict:
    """Parse the script's stdout; anything else (a traceback) is a failure."""
    try:
        payload = json.loads(run.stdout)
    except ValueError:
        raise AssertionError(
            "stdout is not JSON: exit %d, stdout %r, stderr %r"
            % (run.returncode, run.stdout[:300], run.stderr[-300:])
        ) from None
    assert isinstance(payload, dict), payload
    return payload


def _scan(script: Path, repo: Path, *paths: str, extra=()):
    """Run the scoped scan and return ``(run, payload)``."""
    run = _run(script, repo, "--paths", *paths, *extra)
    return run, _json(run)


def _field(mapping: dict, key: str):
    """Return ``mapping[key]``, failing as an assertion when it is absent."""
    assert key in mapping, (key, mapping)
    return mapping[key]


def _put(repo: Path, rel: str, content) -> None:
    """Write ``content`` (text as UTF-8, or bytes) to ``repo/rel`` byte for byte."""
    full = repo / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    full.write_bytes(data)


def _new_repo(work: Path, name: str = "one") -> Path:
    """Create an empty throwaway repository under ``work`` and return it."""
    holder = work / name
    holder.mkdir()
    return _init_repo(holder)


def _by_file(payload: dict) -> dict:
    """Group a scan's findings by file as ``{file: [(line, pattern, token)]}``."""
    grouped: dict = {}
    for finding in _field(payload, "findings"):
        grouped.setdefault(finding["file"], []).append(
            (finding["line"], finding["pattern"], finding["token"])
        )
    return grouped


# --------------------------------------------------------------------------- #
# Broken copies of the script, and the registry of cases that must tell them
# from the real one.
# --------------------------------------------------------------------------- #
class _Edit(NamedTuple):
    """One text replacement applied to a broken copy of the script."""

    old: str
    new: str


class _Mutant(NamedTuple):
    """A labelled set of edits that makes a broken copy of the script."""

    label: str
    edits: tuple


def _mutant(label: str, *edits: _Edit) -> _Mutant:
    return _Mutant(label, edits)


def _edit(old: str, new: str) -> _Edit:
    return _Edit(old, new)


def _disable(name: str) -> _Mutant:
    """A mutant whose attribution pattern ``name`` can never match."""
    key = '"attribution:%s": re.compile(' % name
    return _mutant(
        "disable-" + name,
        _edit(key, key + 'r"(?!)") if True else re.compile('),
    )


def _broken_script(folder: Path, mutant: _Mutant) -> Path:
    """Copy the script into ``folder`` and apply ``mutant``'s edits.

    Bytes in, bytes out. An anchor that is not found exactly once, or an edit
    that leaves a script that does not compile, raises: a control must fail
    for the reason it names and for no other.
    """
    folder.mkdir(parents=True)
    data = (SCRIPTS_DIR / SCRIPT).read_bytes()
    for one in mutant.edits:
        old, new = one.old.encode("utf-8"), one.new.encode("utf-8")
        if b"\r\n" in data:
            old, new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
        found = data.count(old)
        assert found == 1, "%s: anchor found %dx" % (mutant.label, found)
        data = data.replace(old, new)
    compile(data, SCRIPT, "exec")
    target = folder / SCRIPT
    target.write_bytes(data)
    return target


class _Case(NamedTuple):
    """A regression case and the broken copies it must fail against."""

    name: str
    run: Callable[[Path, Path], None]
    mutants: tuple


_CASES: list = []


def _regression(*mutants: _Mutant):
    """Register the decorated ``case_<name>`` function with its mutants."""

    def register(function):
        _CASES.append(_Case(function.__name__.removeprefix("case_"), function, mutants))
        return function

    return register


# --------------------------------------------------------------------------- #
# Every occurrence, not only an introduced one.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant(
        "first-line-only",
        _edit(
            "for lineno, line in enumerate(_split_lines(text), start=1):",
            "for lineno, line in enumerate(_split_lines(text)[:1], start=1):",
        ),
    ),
    _mutant(
        "first-match-per-line",
        _edit(
            '"token": _quote(m.group(0)),\n'
            "                    }\n"
            "                )\n"
            "    return findings",
            '"token": _quote(m.group(0)),\n'
            "                    }\n"
            "                )\n"
            "                break\n"
            "    return findings",
        ),
    ),
    _mutant(
        "no-pattern-reaches-the-report",
        _edit(
            "    return findings, counts, per_path",
            "    return [], counts, per_path",
        ),
    ),
)
def case_every_occurrence_is_reported(script: Path, work: Path) -> None:
    """A committed token is reported on every line and every time it occurs."""
    token = _PLANTED_ID
    repo = _new_repo(work)
    _put(repo, "a/one.txt", "x\ny\nz\nw\nsee %s and %s\n%s\n" % (token, token, token))
    _put(repo, "a/b/two.txt", token + "\n")
    _put(repo, "three.txt", "nothing here\n")
    _commit_all(repo, "chore: seed committed occurrences")

    run, payload = _scan(script, repo, "a", "three.txt")
    assert run.returncode == 1, run.stderr
    grouped = _by_file(payload)
    assert sorted(grouped) == ["a/b/two.txt", "a/one.txt"]
    assert grouped["a/b/two.txt"] == [(1, "AGT-nn", token)]
    assert grouped["a/one.txt"] == [
        (5, "AGT-nn", token),
        (5, "AGT-nn", token),
        (6, "AGT-nn", token),
    ]

    clean = _new_repo(work, "two")
    _put(clean, "a.txt", "nothing here\n")
    run, payload = _scan(script, clean, ".")
    assert run.returncode == 0, run.stderr
    assert _field(payload, "findings") == []


# --------------------------------------------------------------------------- #
# Which files, and which bytes: git's own list, read from disk.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant("no-untracked-files", _edit('                "--others",\n', "")),
    _mutant("no-ignore-rules", _edit('                "--exclude-standard",\n', "")),
    _mutant(
        "reads-head-not-disk",
        _edit(
            'with open(os.path.join(root, rel), "rb") as handle:\n'
            + " " * 28
            + "data = handle.read()",
            'data = subprocess.run(["git", "show", "HEAD:" + rel], cwd=root, '
            "capture_output=True, check=True).stdout",
        ),
    ),
)
def case_the_files_are_gits_list_read_from_disk(script: Path, work: Path) -> None:
    """Uncommitted edits and new files are scanned; ignored scratch is not."""
    token = _PLANTED_ID
    repo = _new_repo(work)
    _put(repo, ".gitignore", "scratch/\n")
    _put(repo, "kept.txt", "clean\n")
    _commit_all(repo, "chore: seed a clean tree")
    _put(repo, "kept.txt", "clean\n" + token + "\n")  # an uncommitted edit
    _put(repo, "fresh/new.txt", token + "\n")  # untracked, not ignored
    _put(repo, "scratch/ignored.txt", token + "\n")  # ignored

    edited = _run(script, repo, "--paths", "kept.txt")
    assert edited.returncode == 1, edited.stderr
    assert _by_file(_json(edited)) == {"kept.txt": [(2, "AGT-nn", token)]}

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 1, run.stderr
    assert sorted(_by_file(payload)) == ["fresh/new.txt", "kept.txt"]
    scanned = _field(payload, "scanned")
    assert _field(scanned, "files_examined") == 2
    assert _field(scanned, "files_excluded") == 1  # .gitignore itself

    named = _run(script, repo, "--paths", "scratch/ignored.txt")
    assert named.returncode == 2, named.stderr
    assert _field(_json(named), "error") == "zero-files-examined"


@_regression(
    _mutant(
        "directories-not-recursed",
        _edit(
            'resolved.append((arg, sorted(p for p in out.split("\\x00") if p)))',
            'resolved.append((arg, sorted(p for p in out.split("\\x00")'
            ' if p and p.count("/") <= rel.count("/") + 1)))',
        ),
    ),
    _mutant(
        "a-file-is-scanned-once-per-argument", _edit("if rel not in seen:", "if True:")
    ),
)
def case_directories_recurse_and_a_file_counts_once(script: Path, work: Path) -> None:
    """A deep file is found through its directory, and two arguments reach it once."""
    token = _PLANTED_ID
    repo = _new_repo(work)
    _put(repo, "d/e/f/g.txt", token + "\n")
    _put(repo, "d/top.txt", "clean\n")

    run, payload = _scan(script, repo, "d")
    assert run.returncode == 1, run.stderr
    assert _by_file(payload) == {"d/e/f/g.txt": [(1, "AGT-nn", token)]}
    assert _field(_field(payload, "scanned"), "files_examined") == 2

    run, payload = _scan(script, repo, "d", "d/e/f/g.txt")
    assert run.returncode == 1, run.stderr
    assert len(_field(payload, "findings")) == 1
    scanned = _field(payload, "scanned")
    assert _field(scanned, "files_examined") == 2
    assert _field(scanned, "per_path") == {"d": 2, "d/e/f/g.txt": 1}

    absolute = _run(script, repo, "--paths", str(repo / "d" / "e"))
    assert absolute.returncode == 1, absolute.stderr
    assert _by_file(_json(absolute)) == {"d/e/f/g.txt": [(1, "AGT-nn", token)]}


# --------------------------------------------------------------------------- #
# The number of files scanned is printed, and a scan of nothing fails.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant(
        "binary-and-excluded-counted-as-scanned",
        _edit(
            'sum(1 for v in seen.values() if v == "examined"),',
            "len(seen),",
        ),
    ),
    _mutant(
        "count-not-printed",
        _edit("path(s): scanned %d ", "path(s): seen %d "),
    ),
    _mutant(
        "count-not-in-the-json",
        _edit(
            "scanned = dict(counts, per_path=per_path,",
            "scanned = dict(per_path=per_path,",
        ),
    ),
)
def case_the_number_of_files_scanned_is_printed(script: Path, work: Path) -> None:
    """The denominator is exact: text files only, binary and excluded counted apart."""
    repo = _new_repo(work)
    _put(repo, "docs/a.txt", "clean\n")
    _put(repo, "docs/b.txt", "clean\n")
    _put(repo, "docs/pic.bin", b"\x00\x01\x02")
    _put(repo, ".gitignore", "scratch/\n")
    _put(repo, "scripts/check_vocabulary_regrowth.py", "# " + _PLANTED_ID + "\n")

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 0, run.stderr
    scanned = _field(payload, "scanned")
    assert _field(scanned, "files_examined") == 2
    assert _field(scanned, "files_skipped_binary") == 1
    assert _field(scanned, "files_excluded") == 2
    assert _field(scanned, "per_path") == {".": 2}
    assert "scanned 2 text file(s)" in run.stderr


@_regression(
    _mutant(
        "a-scan-of-nothing-passes",
        _edit('if counts["files_examined"] == 0 or empty:', "if False:"),
    ),
    _mutant(
        "an-empty-argument-hides-behind-the-total",
        _edit(
            'if counts["files_examined"] == 0 or empty:',
            'if counts["files_examined"] == 0:',
        ),
    ),
)
def case_a_scan_of_nothing_fails(script: Path, work: Path) -> None:
    """Zero scanned files, or one argument that contributed none, is exit 2."""
    repo = _new_repo(work)
    _put(repo, "docs/a.txt", "clean\n")
    _put(repo, "bin/pic.bin", b"\x00\x01\x02")
    (repo / "empty").mkdir()

    only_binary = _run(script, repo, "--paths", "bin")
    assert only_binary.returncode == 2, only_binary.stderr
    assert _field(_json(only_binary), "error") == "zero-files-examined"
    assert "examined 0 text file(s)" in only_binary.stderr

    mistyped = _run(script, repo, "--paths", "docs", "empty")
    assert mistyped.returncode == 2, mistyped.stderr
    assert _field(_json(mistyped), "error") == "zero-files-examined"
    assert "'empty'" in mistyped.stderr

    healthy = _run(script, repo, "--paths", "docs")
    assert healthy.returncode == 0, healthy.stderr


# --------------------------------------------------------------------------- #
# The eight patterns, with the gate's own exclusions and allowlist.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant(
        "the-eight-patterns-are-not-applied",
        _edit(
            "families = list(PATTERNS.items()) + list(ATTRIBUTION_PATTERNS.items())",
            "families = list(ATTRIBUTION_PATTERNS.items())",
        ),
    ),
    _mutant(
        "a-named-path-bypasses-the-exclusions",
        _edit(
            "if excluded(rel):\n" + _SPACES_20 + 'seen[rel] = "excluded"',
            "if False:\n" + _SPACES_20 + 'seen[rel] = "excluded"',
        ),
    ),
    _mutant(
        "the-allowlist-is-ignored",
        _edit("if (rel, name) in ALLOWLIST_HITS:", "if (rel, name) in ():"),
    ),
)
def case_a_planted_internal_identifier_exits_1(script: Path, work: Path) -> None:
    """Each of the eight families, planted alone, is reported with its token."""
    repo = _new_repo(work)
    expected = {}
    for index, (pattern_name, prefix, suffix) in enumerate(PLANTED):
        token = _token(prefix, suffix)
        _put(repo, "plant_%d.txt" % index, "note: " + token + " is mentioned.\n")
        expected["plant_%d.txt" % index] = [(1, pattern_name, token)]
    _put(repo, "planted_id.txt", "owner " + _PLANTED_ID + "\n")
    expected["planted_id.txt"] = [(1, "AGT-nn", _PLANTED_ID)]
    design_docs = _token("design", "-docs")
    _put(repo, "memory/repo_guard.py", "# " + design_docs + " check\n")
    _put(repo, "memory/graph/nodes.jsonl", _PLANTED_ID + "\n")

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 1, run.stderr
    assert _by_file(payload) == expected
    scanned = _field(payload, "scanned")
    assert _field(scanned, "files_examined") == len(expected) + 1  # + repo_guard.py
    assert _field(scanned, "files_excluded") == 1  # memory/graph/


# --------------------------------------------------------------------------- #
# The AI-attribution family: each shape, and the shipped words it must not hit.
# --------------------------------------------------------------------------- #
ATTRIBUTION_PLANTS = [
    ({"attribution:co-authored-by"}, "Co-Authored-By: " + _VENDOR_MODEL),
    (
        {"attribution:co-authored-by", "attribution:vendor-email"},
        _join("Co-Authored-By: ", _VENDOR_MODEL, " <no", "reply@", _VENDOR, ".com>"),
    ),
    (
        {"attribution:generated-by", "attribution:assistant-tool"},
        _join("Generated with ", _VENDOR_MODEL, " Code"),
    ),
    (
        {"attribution:generated-by"},
        _join("<comment>Translated ", "by an AI</comment>"),
    ),
    (
        {"attribution:generated-by"},
        _join("this text was written ", "using a language model"),
    ),
    ({"attribution:ai-adjective"}, _join("AI", "-generated translation")),
    ({"attribution:author-field"}, _join('"translator": "', _VENDOR_MODEL, '"')),
    ({"attribution:author-field"}, "Last-Translator: " + _OTHER_VENDOR),
    ({"attribution:vendor-email"}, _join(_VENDOR_MODEL.lower(), "@example.org")),
    (
        {"attribution:vendor-url"},
        _join("see https://", _VENDOR_MODEL.lower(), ".ai/c/1"),
    ),
    ({"attribution:assistant-tool"}, "built with " + _VENDOR_MODEL + " Code"),
]

#: Lines of SHIPPED text that name the vendor on purpose; none may be a finding.
SHIPPED_WORDS = [
    "<source>%s (%s)</source>" % (_VENDOR, _VENDOR_MODEL),
    "the %s option talks to %s natively" % (_VENDOR, _VENDOR_MODEL),
    '"keywords": ["%s", "%s", "gemini"]' % (_VENDOR.lower(), _VENDOR_MODEL.lower()),
    _join("endpoint https://api.", _VENDOR.lower(), ".com"),
    _join("service pixelart-creator:assistant:", "open", "ai"),
    "Compatible con " + _join("Open", "AI"),
    "AI-assisted perspective inference is a later phase",
    "the AI assistant proposes an action; you confirm it",
    "Translated by the team; reviewed by the maintainers",
    "Author: Juan Garcia Sanchez",
]


@_regression(
    *[
        _disable(name)
        for name in (
            "co-authored-by",
            "generated-by",
            "ai-adjective",
            "author-field",
            "vendor-email",
            "vendor-url",
            "assistant-tool",
        )
    ]
)
def case_each_attribution_shape_exits_1(script: Path, work: Path) -> None:
    """Every shape of the family, planted alone in its own file, is named."""
    repo = _new_repo(work)
    for index, (_, text) in enumerate(ATTRIBUTION_PLANTS):
        _put(repo, "plant_%d.txt" % index, text + "\n")

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 1, run.stderr
    grouped = _by_file(payload)
    for index, (expected, _) in enumerate(ATTRIBUTION_PLANTS):
        name = "plant_%d.txt" % index
        found = {pattern for _, pattern, _ in grouped.get(name, [])}
        assert found == expected, (name, found, expected)


@_regression(
    _mutant(
        "bare-vendor-names-by-default",
        _edit("if vendor_names:", "if True:"),
    ),
    _mutant(
        "a-key-word-after-a-hyphen-is-a-key",
        _edit("(?<![%s_-])", "(?<![%s])"),
    ),
    _mutant(
        "ai-assisted-is-an-attribution",
        _edit(_ADJ_LINE + '"', _ADJ_LINE + '|assisted"'),
    ),
    _mutant(
        "the-api-host-is-a-session-link",
        _edit(
            '    "gemini[.]google[.]com",\n)',
            '    "gemini[.]google[.]com",\n    "api[.]anthropi" + "c[.]com",\n)',
        ),
    ),
    _mutant(
        "any-word-after-by-is-an-ai",
        _edit(_CHATBOT_TAIL, _CHATBOT_TAIL.replace("|chatbot", "|chatbot|[a-z]+")),
    ),
)
def case_the_shipped_vendor_words_are_not_findings(script: Path, work: Path) -> None:
    """The provider label, the guide sentence and the default endpoint pass."""
    repo = _new_repo(work)
    _put(repo, "shipped.txt", "\n".join(SHIPPED_WORDS) + "\n")

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 0, (run.stderr, _field(payload, "findings"))
    assert _field(payload, "findings") == []
    assert _field(_field(payload, "scanned"), "files_examined") == 1


@_regression(
    _mutant(
        "the-flag-does-nothing",
        _edit(
            "if vendor_names:\n        families.append(BARE_VENDOR_PATTERN)",
            "if False:\n        families.append(BARE_VENDOR_PATTERN)",
        ),
    ),
    _mutant(
        "the-flag-without-paths-is-accepted",
        _edit("if args.paths is None and args.vendor_names:", "if False:"),
    ),
)
def case_bare_vendor_names_are_opt_in(script: Path, work: Path) -> None:
    """The flag adds the bare names, and means nothing without ``--paths``."""
    repo = _new_repo(work)
    _put(repo, "text.txt", "%s and %s\n" % (_VENDOR, _VENDOR_MODEL))

    default, payload = _scan(script, repo, ".")
    assert default.returncode == 0, default.stderr
    assert _field(_field(payload, "scanned"), "vendor_names") is False

    run, payload = _scan(script, repo, ".", extra=("--vendor-names",))
    assert run.returncode == 1, run.stderr
    assert _by_file(payload) == {
        "text.txt": [
            (1, "attribution:vendor-name", _VENDOR),
            (1, "attribution:vendor-name", _VENDOR_MODEL),
        ]
    }
    assert _field(_field(payload, "scanned"), "vendor_names") is True

    alone = _run(script, repo, "--vendor-names")
    assert alone.returncode == 2, alone.stderr
    assert _field(_json(alone), "error") == "vendor-names-without-paths"


# --------------------------------------------------------------------------- #
# Usage errors: never a silent pass.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant(
        "a-commit-range-is-ignored",
        _edit("if args.paths is not None and (", "if False and ("),
    ),
    _mutant(
        "a-missing-path-is-not-checked",
        _edit("if not os.path.exists(full):", "if False:"),
    ),
    _mutant(
        "a-path-outside-the-root-is-not-checked",
        _edit('if rel == ".." or rel.startswith("../"):', "if False:"),
    ),
)
def case_usage_errors_exit_2(script: Path, work: Path) -> None:
    """A range with ``--paths``, a missing path and an outside path are exit 2."""
    repo = _new_repo(work)
    _put(repo, "a.txt", "clean\n")
    sha = _commit_all(repo, "chore: seed tree")

    ranged = _run(
        script, repo, "--paths", "a.txt", "--base-sha", sha, "--head-sha", sha
    )
    assert ranged.returncode == 2, ranged.stderr
    assert _field(_json(ranged), "error") == "paths-with-commit-range"

    missing = _run(script, repo, "--paths", "a.txt", "no/such/dir")
    assert missing.returncode == 2, missing.stderr
    assert _field(_json(missing), "error") == "path-not-found"

    outside = _run(script, repo, "--paths", "a.txt", "..")
    assert outside.returncode == 2, outside.stderr
    assert _field(_json(outside), "error") == "path-outside-root"


# --------------------------------------------------------------------------- #
# Line numbers and bytes: what an editor shows, whatever the file holds.
# --------------------------------------------------------------------------- #
@_regression(
    _mutant(
        "lines-split-on-unicode-separators",
        _edit(
            '.split("\\n")',
            ".splitlines()",
        ),
    ),
    _mutant(
        "undecodable-bytes-crash-the-scan",
        _edit(
            'text = data.decode("utf-8", errors="replace")',
            'text = data.decode("utf-8")',
        ),
    ),
)
def case_line_numbers_and_bytes_survive_real_files(script: Path, work: Path) -> None:
    """CRLF, a Unicode line separator, CJK text and a stray byte keep the line."""
    token = _PLANTED_ID
    repo = _new_repo(work)
    crlf = "\u4f60\u597d\u2028\u3053\u3093\r\nsecond\r\n" + token + "\r\n"
    _put(repo, "cjk.ts", crlf)
    _put(repo, "latin.txt", b"caf\xe9\n" + token.encode("ascii") + b"\n")

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 1, run.stderr
    assert _by_file(payload) == {
        "cjk.ts": [(3, "AGT-nn", token)],
        "latin.txt": [(2, "AGT-nn", token)],
    }
    assert "Traceback" not in run.stderr


@_regression(
    _mutant(
        "a-file-deleted-from-disk-crashes-the-scan",
        _edit(
            "# e.g. tracked in the index but deleted from disk\n"
            + " " * 24
            + 'seen[rel] = "unreadable"\n'
            + " " * 24
            + "continue",
            "raise",
        ),
    ),
)
def case_a_tracked_file_deleted_from_disk_is_counted(script: Path, work: Path) -> None:
    """A path still in the index but gone from disk is counted, not a crash."""
    repo = _new_repo(work)
    _put(repo, "keep.txt", "clean\n")
    _put(repo, "gone.txt", "clean\n")
    _commit_all(repo, "chore: seed two files")
    (repo / "gone.txt").unlink()

    run, payload = _scan(script, repo, ".")
    assert run.returncode == 0, run.stderr
    scanned = _field(payload, "scanned")
    assert _field(scanned, "files_examined") == 1
    assert _field(scanned, "files_unreadable") == 1


# --------------------------------------------------------------------------- #
# The generic tests: every case against the real script and its broken copies.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("case", [pytest.param(c, id=c.name) for c in _CASES])
def test_scoped_case_holds_on_the_real_script(case: _Case, tmp_path: Path) -> None:
    """The clean fixture exits 0 and the planted one exits 1, as the case states."""
    work = tmp_path / "work"
    work.mkdir()
    case.run(SCRIPTS_DIR / SCRIPT, work)


@pytest.mark.parametrize(
    ("case", "broken"),
    [
        pytest.param(c, m, id="%s--%s" % (c.name, m.label))
        for c in _CASES
        for m in c.mutants
    ],
)
def test_scoped_case_fails_on_a_broken_copy(
    case: _Case, broken: _Mutant, tmp_path: Path
) -> None:
    """With the defended rule removed from a copy of the script the case fails."""
    script = _broken_script(tmp_path / "scripts", broken)
    work = tmp_path / "work"
    work.mkdir()
    with pytest.raises(AssertionError):
        case.run(script, work)


def test_every_scoped_case_has_a_broken_copy() -> None:
    """A case registered without a mutant would be a control that controls nothing."""
    assert _CASES
    assert [case.name for case in _CASES if not case.mutants] == []


def test_an_unmodified_copy_behaves_like_the_real_script(tmp_path: Path) -> None:
    """The broken-copy machinery is neutral: a copy with no edit passes the cases."""
    script = _broken_script(tmp_path / "scripts", _Mutant("unmodified", ()))
    for case in _CASES[:3]:
        work = tmp_path / case.name
        work.mkdir()
        case.run(script, work)


# --------------------------------------------------------------------------- #
# The pull-request mode is unchanged by the scoped scan.
# --------------------------------------------------------------------------- #
def test_pull_request_mode_keeps_its_report_and_its_families(tmp_path):
    """Same keys, no ``mode``, and the attribution family is not run there."""
    shaped = _join("Co-Authored-By: ", _VENDOR_MODEL, "\nTranslated by an AI\n")
    repo = _new_repo(tmp_path)
    _put(repo, "readme.txt", shaped)
    base_sha = _commit_all(repo, "chore: seed base tree")
    _put(repo, "second.txt", "still nothing.\n")
    head_sha = _commit_all(repo, "docs: " + _join("Generated with ", _VENDOR_MODEL))

    plain = _run(SCRIPTS_DIR / SCRIPT, repo)
    assert plain.returncode == 0, plain.stderr
    payload = _json(plain)
    assert sorted(payload) == ["findings", "scanned"]
    assert sorted(payload["scanned"]) == [
        "commit_message_check",
        "commit_messages_examined",
        "files_examined",
        "files_skipped_binary",
        "tracked_paths",
    ]

    ranged = _run(
        SCRIPTS_DIR / SCRIPT, repo, "--base-sha", base_sha, "--head-sha", head_sha
    )
    assert ranged.returncode == 0, ranged.stderr
    assert _json(ranged)["findings"] == []
    assert _json(ranged)["scanned"]["commit_messages_examined"] == 1
