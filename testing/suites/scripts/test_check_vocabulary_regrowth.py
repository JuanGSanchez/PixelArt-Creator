"""Contract tests for ``scripts/check_vocabulary_regrowth.py``.

Contract asserted here, taken verbatim from the script's own header:

    ENTRYPOINT: python scripts/check_vocabulary_regrowth.py [--root .]
                [--base-sha SHA --head-sha SHA]
    EXIT CODES: 0 clean -> COMPLETED ; 1 finding(s) -> FAILED ;
        2 usage/environment error (including any zero denominator) -> BLOCKED.

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
at run time, never in this file's own committed content.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from .conftest import run_script

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
