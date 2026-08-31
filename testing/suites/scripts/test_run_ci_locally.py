"""Contract tests for ``scripts/run_ci_locally.py`` (ADR-0047 tranche 2).

Contract asserted here, taken from the script's own header::

    ENTRYPOINT: python scripts/run_ci_locally.py [--job quality-gate]
        [--workflow .github/workflows/ci.yml] [--list-jobs] [--dry-run]
        [--event push] [--ref ""] [--input KEY=VALUE ...]
        [--only SUBSTRING ...] [--skip SUBSTRING ...]
    EXIT CODES: 0 all executed steps passed (>=1 step executed) -> local PASS;
        1 at least one executed step failed -> local FAIL;
        2 usage/parse error (workflow/job not found, PyYAML missing, bad
          --input, no bash on PATH) -> BLOCKED;
        3 nothing was actually executed (every step skipped/filtered out, or
          the job-level `if:` was false) -> NO SIGNAL.

WHAT THIS MODULE DELIBERATELY DOES NOT DO (per the follow-up-tranche
instruction): it never lets a fixture's ``run:`` block actually execute.
Every scenario below passes ``--dry-run``, which this script maps to status
``NOT-RUN`` for every ``run:`` step -- the block is parsed and would-execute,
never invoked via ``bash -c``. This module tests the PARSE and the STEP
SELECTION -- job lookup, ``--only``/``--skip`` filtering, ``if:`` condition
evaluation, and ``strategy.matrix.os`` leg selection -- deriving the right
steps in the right order from a hand-built fixture workflow under
``tmp_path``, passed to the script via its own ``--workflow`` flag. The real
``.github/workflows/ci.yml`` is read only for a non-execution sanity check
(``--list-jobs``, which also never executes a `run:` block).

FINDING (reported, not silently absorbed): the header's own EXIT CODES
section maps exit 1 to "at least one executed step failed". The observed
behaviour of ``_select_matrix_os`` (confirmed this session against a fixture
whose ``strategy.matrix.os`` list has no leg matching the local OS) is a
plain ``raise SystemExit(f"...")`` -- a SystemExit constructed with a STRING,
not an int. Python's default top-level handling of a string-valued SystemExit
prints the string to stderr and exits with status **1**, even though this
condition is a usage/configuration mismatch (no OS leg to run at all, zero
steps executed) and reads far closer to the header's own "2 usage/parse
error" bucket than to "a step failed". This is a genuine mismatch between the
documented exit-code contract and the observed behaviour, not smoothed over
here: ``test_matrix_no_matching_os_leg_exits_1_not_2_per_observed_behaviour``
asserts the REAL, currently-observed exit code (1), and this docstring is
where the discrepancy is recorded for AGT-09/AGT-01 to reconcile (either the
header's own wording, or the ``SystemExit`` call site).

A second, more minor observation, not a header mismatch and not asserted as
a "finding" for that reason: ``--dry-run`` can never itself produce exit 0,
because "executed" (per the header) means a step actually ran (``RAN-PASS``/
``RAN-FAIL``); a dry run only ever produces ``NOT-RUN``/``SKIPPED``/``MAPPED``
statuses, so a dry run of a job whose steps would all otherwise pass still
exits 3 ("NO SIGNAL"), not 0. This is a natural consequence of the header's
own definition of "executed", not a contradiction of it, so it is documented
here as context for a reader wondering why every ``--dry-run`` scenario below
asserts exit code 3.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from .conftest import run_script

SCRIPT = "run_ci_locally.py"

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
_SPEC = importlib.util.spec_from_file_location(
    "run_ci_locally", _SCRIPTS_DIR / "run_ci_locally.py"
)
assert _SPEC is not None and _SPEC.loader is not None
run_ci_locally = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("run_ci_locally", run_ci_locally)
_SPEC.loader.exec_module(run_ci_locally)


_FIXTURE_WORKFLOW = """\
name: Fixture CI
on:
  push: {}
  workflow_dispatch:
    inputs:
      mode:
        default: "quick"
jobs:
  demo-job:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Step A
        run: echo "A"
      - name: Step B (conditional)
        if: ${{ github.event_name == 'push' }}
        run: echo "B"
      - name: Step C (conditional false)
        if: ${{ github.event_name == 'workflow_dispatch' }}
        run: echo "C"
      - name: Upload
        uses: actions/upload-artifact@v4
        with:
          name: artifact
          path: dist/
  matrix-job:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    steps:
      - name: Matrix step
        run: echo "matrix"
  no-match-job:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [not-a-real-os-latest, also-not-a-real-os-latest]
    steps:
      - name: No match step
        run: echo "no match"
  gated-job:
    if: ${{ github.event_name == 'workflow_dispatch' }}
    runs-on: ubuntu-latest
    steps:
      - name: Gated step
        run: echo "gated"
"""


@pytest.fixture
def fixture_workflow(tmp_path: Path) -> Path:
    path = tmp_path / "fixture.yml"
    path.write_text(_FIXTURE_WORKFLOW, encoding="utf-8")
    return path


_STEP_STATUSES = ("SKIPPED", "MAPPED", "NOT-RUN", "RAN-PASS", "RAN-FAIL")


def _step_lines(stdout: str) -> list:
    """Pull the ``[STATUS   ] name   detail`` summary-table lines out of
    stdout, in the order the script printed them (== execution/derivation
    order), skipping the banner/log lines around them (some of which, e.g.
    ``[run_ci_locally] workflow=...``, ALSO start with ``[`` and would
    otherwise be mistaken for a step row)."""
    return [
        ln
        for ln in stdout.splitlines()
        if ln.strip().startswith("[")
        and ln.strip()[1:].split(None, 1)[0].rstrip("]") in _STEP_STATUSES
    ]


# --------------------------------------------------------------------------- #
# --list-jobs: never executes a run: block; a pure parse-and-report path.
# --------------------------------------------------------------------------- #
def test_list_jobs_lists_all_jobs_with_correct_step_counts(fixture_workflow):
    result = run_script(SCRIPT, ["--workflow", str(fixture_workflow), "--list-jobs"])
    assert result.returncode == 0, result.stderr
    assert "'demo-job': 6 steps (3 run:, 3 uses:)" in result.stdout
    assert "'matrix-job': 1 steps (1 run:, 0 uses:)" in result.stdout
    assert "matrix.os=['ubuntu-latest', 'windows-latest']" in result.stdout
    assert "'gated-job': 1 steps (1 run:, 0 uses:)" in result.stdout
    assert "(job-level if:)" in result.stdout


# --------------------------------------------------------------------------- #
# --dry-run derives the right steps in the right order (the essential
# "parse and selection" pair for this script), and NEVER executes a run: block.
# --------------------------------------------------------------------------- #
def test_dry_run_derives_steps_in_declared_order_with_conditions_applied(
    fixture_workflow,
):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(fixture_workflow),
            "--job",
            "demo-job",
            "--dry-run",
            "--event",
            "push",
        ],
    )
    # exit 3: a dry run never marks any step RAN-PASS/RAN-FAIL (see module
    # docstring) -- "nothing was actually executed" is the correct, documented
    # reading of a run that only ever parses.
    assert result.returncode == 3, result.stderr

    lines = _step_lines(result.stdout)
    names_and_status = [
        (ln.split("]", 1)[0].strip("[ "), ln.split("]", 1)[1].split(None, 1)[0])
        for ln in lines
    ]
    assert names_and_status == [
        ("SKIPPED", "Checkout"),
        ("MAPPED", "Setup"),
        ("NOT-RUN", "Step"),
        ("NOT-RUN", "Step"),
        ("SKIPPED", "Step"),
        ("SKIPPED", "Upload"),
    ]
    # The two real run: steps that survive their `if:` (Step A unconditional,
    # Step B's `if: github.event_name == 'push'` true under --event push) are
    # both NOT-RUN (parsed, not executed) -- never RAN-PASS/RAN-FAIL, proving
    # this test never let `echo "A"` / `echo "B"` actually run.
    assert "would execute via bash" in result.stdout
    assert 'echo "A"' not in result.stdout.split("would execute via bash")[0][-5:]

    # Step C's `if:` is false under --event push -- evaluated, not executed,
    # and reported as SKIPPED with the condition it failed named in the detail.
    assert (
        "if: \"${{ github.event_name == 'workflow_dispatch' }}\" evaluated false"
        in (result.stdout)
    )


def test_only_filter_selects_steps_by_name_substring(fixture_workflow):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(fixture_workflow),
            "--job",
            "demo-job",
            "--dry-run",
            "--only",
            "Step",
        ],
    )
    assert result.returncode == 3, result.stderr
    lines = _step_lines(result.stdout)
    # Checkout/Setup Python/Upload do not contain "Step" -> excluded.
    assert "excluded: does not match any --only filter ['Step']" in "\n".join(lines)
    step_a_line = next(ln for ln in lines if "Step A" in ln)
    assert "NOT-RUN" in step_a_line
    checkout_line = next(ln for ln in lines if "Checkout" in ln)
    assert "excluded: does not match any --only filter" in checkout_line


def test_skip_filter_excludes_named_step_only(fixture_workflow):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(fixture_workflow),
            "--job",
            "demo-job",
            "--dry-run",
            "--skip",
            "Upload",
        ],
    )
    assert result.returncode == 3, result.stderr
    upload_line = next(ln for ln in _step_lines(result.stdout) if "Upload" in ln)
    assert "excluded by --skip filter 'Upload'" in upload_line
    # Every other step must still be derived (not swept into the skip too).
    step_a_line = next(ln for ln in _step_lines(result.stdout) if "Step A" in ln)
    assert "NOT-RUN" in step_a_line


# --------------------------------------------------------------------------- #
# strategy.matrix.os leg selection.
# --------------------------------------------------------------------------- #
def test_matrix_job_selects_the_leg_matching_the_local_os(fixture_workflow):
    """This test host is Windows (win32); the fixture's ``matrix-job`` lists
    ``[ubuntu-latest, windows-latest]``, so ``windows-latest`` must be the
    selected leg -- proving the selection reads the real local OS, not a
    fixed literal."""
    if run_ci_locally._LOCAL_RUNNER_OS != "Windows":
        pytest.skip(
            f"this test's fixture only covers a Windows leg selection; local "
            f"OS is {run_ci_locally._LOCAL_RUNNER_OS!r} on this run "
            "(Directive 12: stated, not silently skipped)."
        )
    result = run_script(
        SCRIPT,
        ["--workflow", str(fixture_workflow), "--job", "matrix-job", "--dry-run"],
    )
    assert result.returncode == 3, result.stderr
    assert "matrix leg selected: os=windows-latest (local OS)" in result.stdout
    matrix_step_line = next(
        ln for ln in _step_lines(result.stdout) if "Matrix step" in ln
    )
    assert "NOT-RUN" in matrix_step_line


def test_matrix_no_matching_os_leg_exits_1_not_2_per_observed_behaviour(
    fixture_workflow,
):
    """See the module docstring FINDING: a matrix with no leg matching the
    local OS raises a string-valued SystemExit, which Python's default
    handling turns into exit code 1 -- NOT the header's own "2 usage/parse
    error" bucket, even though this is a usage/config mismatch and zero steps
    ever ran. Asserted here as the REAL, observed value (verified-testing
    principle: assert against the system's own behaviour, not the header's
    aspirational mapping).

    The fixture's ``no-match-job`` lists ``matrix.os: [not-a-real-os-latest,
    also-not-a-real-os-latest]`` -- two labels that are not keys of
    ``_RUNNER_OS_BY_LABEL`` (which only knows ``ubuntu-latest``,
    ``windows-latest``, ``macos-latest``), so ``_select_matrix_os`` looks
    up ``None`` for every leg and that can never equal ``_LOCAL_RUNNER_OS``
    on ANY host. This is deliberate: an earlier version of this fixture used
    ``[ubuntu-latest, macos-latest]``, chosen only to avoid the author's own
    Windows machine, and that made the test pass locally while failing on
    hosted ``ubuntu-latest``/``macos-latest`` CI runners, where one of those
    two real labels DOES match the runner's own OS and the "no match" branch
    is never reached (observed failure: ``assert 3 == 1``). Fictional labels
    make the "no leg matches" condition true unconditionally, independent of
    which OS actually runs this test."""
    result = run_script(
        SCRIPT,
        ["--workflow", str(fixture_workflow), "--job", "no-match-job", "--dry-run"],
    )
    assert result.returncode == 1, result.stderr
    assert "has no leg matching this machine's OS" in result.stderr


# --------------------------------------------------------------------------- #
# Job-level `if:` gating -- zero steps derived, exit 3 (NO SIGNAL).
# --------------------------------------------------------------------------- #
def test_job_level_if_false_skips_the_entire_job_exits_3(fixture_workflow):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(fixture_workflow),
            "--job",
            "gated-job",
            "--dry-run",
            "--event",
            "push",
        ],
    )
    assert result.returncode == 3, result.stderr
    assert "job 'gated-job' SKIPPED entirely" in result.stdout
    assert "Gated step" not in result.stdout


# --------------------------------------------------------------------------- #
# BLOCKED path (exit 2): unknown job, missing workflow file.
# --------------------------------------------------------------------------- #
def test_unknown_job_exits_2(fixture_workflow):
    result = run_script(
        SCRIPT,
        ["--workflow", str(fixture_workflow), "--job", "nope", "--dry-run"],
    )
    assert result.returncode == 2, result.stderr
    assert "no job named 'nope'" in result.stderr


def test_missing_workflow_file_exits_2(tmp_path):
    missing = tmp_path / "does-not-exist.yml"
    result = run_script(SCRIPT, ["--workflow", str(missing), "--dry-run"])
    assert result.returncode == 2, result.stderr
    assert "workflow file not found" in result.stderr


def test_malformed_workflow_with_no_jobs_key_exits_2(tmp_path):
    bad = tmp_path / "bad.yml"
    bad.write_text("name: not-a-workflow\n", encoding="utf-8")
    result = run_script(SCRIPT, ["--workflow", str(bad), "--dry-run"])
    assert result.returncode == 2, result.stderr
    assert "does not parse as a workflow" in result.stderr


def test_pyyaml_missing_exits_2(tmp_path):
    """Simulated in-process (not via subprocess): ``sys.modules['yaml'] =
    None`` is the standard way to make a subsequent bare ``import yaml``
    raise ``ImportError`` without uninstalling the real package -- PyYAML
    genuinely is a dependency of this working tree (transitively, via the
    ``mkdocs`` dev extra) and must stay installed for every OTHER test in
    this module, which all invoke the script as a real subprocess."""
    real_yaml = sys.modules.get("yaml")
    sys.modules["yaml"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(SystemExit) as excinfo:
            run_ci_locally._load_workflow(tmp_path / "irrelevant.yml")
        assert excinfo.value.code == 2
    finally:
        if real_yaml is not None:
            sys.modules["yaml"] = real_yaml
        else:
            sys.modules.pop("yaml", None)


# --------------------------------------------------------------------------- #
# Pure expression-evaluator unit tests (in-process, via the loaded module) --
# the `if:`/`env:` expression language the parse-and-selection logic above
# depends on, isolated from the subprocess/workflow-file layer.
# --------------------------------------------------------------------------- #
def test_eval_expr_equality_and_boolean_operators():
    ctx = {"github": {"event_name": "push"}}
    assert run_ci_locally.eval_expr("github.event_name == 'push'", ctx) is True
    assert run_ci_locally.eval_expr("github.event_name != 'push'", ctx) is False
    assert (
        run_ci_locally.eval_expr(
            "github.event_name == 'push' && github.event_name != 'pull_request'", ctx
        )
        is True
    )


def test_eval_expr_starts_with_function():
    ctx = {"github": {"ref": "refs/heads/fix-audit-remediation"}}
    assert (
        run_ci_locally.eval_expr("startsWith(github.ref, 'refs/heads/fix-')", ctx)
        is True
    )
    assert (
        run_ci_locally.eval_expr("startsWith(github.ref, 'refs/tags/')", ctx) is False
    )


def test_eval_condition_handles_the_optional_wrapper():
    ctx = {"github": {"event_name": "push"}}
    assert run_ci_locally.eval_condition("${{ github.event_name == 'push' }}", ctx)
    assert run_ci_locally.eval_condition("github.event_name == 'push'", ctx)
    assert run_ci_locally.eval_condition(None, ctx) is True


def test_secrets_namespace_resolves_to_real_env_or_empty(monkeypatch):
    monkeypatch.setenv("RUN_CI_LOCALLY_TEST_SECRET", "shh")
    monkeypatch.delenv("RUN_CI_LOCALLY_TEST_SECRET_ABSENT", raising=False)
    space = run_ci_locally._SecretsNamespace()
    assert space.get("RUN_CI_LOCALLY_TEST_SECRET") == "shh"
    assert space.get("RUN_CI_LOCALLY_TEST_SECRET_ABSENT", "") == ""
