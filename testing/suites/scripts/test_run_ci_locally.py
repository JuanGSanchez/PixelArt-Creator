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
where the discrepancy is recorded for the CI and architecture owners to reconcile
(either the header's own wording, or the ``SystemExit`` call site).

A second, more minor observation, not a header mismatch and not asserted as
a "finding" for that reason: ``--dry-run`` can never itself produce exit 0,
because "executed" (per the header) means a step actually ran (``RAN-PASS``/
``RAN-FAIL``); a dry run only ever produces ``NOT-RUN``/``SKIPPED``/``MAPPED``
statuses, so a dry run of a job whose steps would all otherwise pass still
exits 3 ("NO SIGNAL"), not 0. This is a natural consequence of the header's
own definition of "executed", not a contradiction of it, so it is documented
here as context for a reader wondering why every ``--dry-run`` scenario below
asserts exit code 3.

THE SECOND PART OF THIS MODULE (REQ-L10N-BUILD-006): the runner reads the
current ``ci.yml``. Its cases are grouped under the headings "step status",
"matrix", "run-block plumbing" and "real bash". The principle above holds for
all of them except the last heading: the status, matrix-default and plumbing
cases run the runner IN-PROCESS with ``_spawn`` (the one seam to a real
process) replaced by a fake that reads the script it was handed, so no
``run:`` block executes. Only the "real bash" cases execute anything, and
what they execute is a single ``echo``/``false`` line or the ``setup`` job's
own ``echo ... >> "${GITHUB_OUTPUT}"`` -- the case that proves the legs of the
real ``ci.yml`` are computed, not assumed. Each is skipped, with its reason
stated, when no working ``bash`` is available; a skip is not a pass.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
    sys.modules["yaml"] = None
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


# =========================================================================== #
# SECOND PART (REQ-L10N-BUILD-006): the runner reads the current ci.yml.
# =========================================================================== #
def _parse(*argv: str):
    return run_ci_locally.build_parser().parse_args(list(argv))


def _status_ctx(failed: bool = False, cancelled: bool = False, **outcomes: str) -> dict:
    """A context whose steps carry the given ``<id>.outcome`` values."""
    return {
        "runner": {"os": "Linux"},
        "github": {"event_name": "push"},
        "needs": {},
        "steps": {f"{step}.outcome": value for step, value in outcomes.items()},
        "_status": {"failed": failed, "cancelled": cancelled},
    }


# --------------------------------------------------------------------------- #
# Expression language: status functions, fromJSON, values from && and ||.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("failed", "cancelled", "expected"),
    [
        (False, False, {"success": True, "failure": False, "cancelled": False}),
        (True, False, {"success": False, "failure": True, "cancelled": False}),
        (False, True, {"success": False, "failure": False, "cancelled": True}),
    ],
)
def test_status_functions_follow_the_job_state(failed, cancelled, expected):
    ctx = _status_ctx(failed=failed, cancelled=cancelled)
    for name, want in expected.items():
        assert run_ci_locally.eval_expr(f"{name}()", ctx) is want, name
    # always() is true in every state, which is the whole point of it.
    assert run_ci_locally.eval_expr("always()", ctx) is True
    # Function names are matched without regard to case, as GitHub does.
    assert run_ci_locally.eval_expr("Always()", ctx) is True


def test_a_planted_unknown_function_is_still_rejected():
    with pytest.raises(run_ci_locally.ExprError, match="unsupported function"):
        run_ci_locally.eval_expr("notAFunction()", _status_ctx())
    with pytest.raises(run_ci_locally.ExprError, match=r"notAFunction\(\)"):
        run_ci_locally.eval_expr("success() && notAFunction()", _status_ctx())
    # A status function given an argument is a malformed call, not a pass.
    with pytest.raises(run_ci_locally.ExprError, match="takes no arguments"):
        run_ci_locally.eval_expr("always('x')", _status_ctx())


def test_a_planted_unknown_function_in_a_workflow_exits_2(tmp_path):
    path = tmp_path / "planted.yml"
    path.write_text(
        "jobs:\n"
        "  planted:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: planted\n"
        "        if: ${{ notAFunction() }}\n"
        "        run: echo x\n",
        encoding="utf-8",
    )
    result = run_script(
        SCRIPT, ["--workflow", str(path), "--job", "planted", "--dry-run"]
    )
    assert result.returncode == 2, result.stderr
    assert "unsupported function: notAFunction()" in result.stderr
    assert "step 'planted'" in result.stderr


def test_from_json_reads_a_list_and_refuses_text_that_is_not_json():
    ctx = _status_ctx()
    ctx["needs"] = {"setup.outputs.os": '["ubuntu-latest", "macos-latest"]'}
    assert run_ci_locally.eval_expr("fromJSON(needs.setup.outputs.os)", ctx) == [
        "ubuntu-latest",
        "macos-latest",
    ]
    ctx["needs"] = {"setup.outputs.os": ""}
    with pytest.raises(run_ci_locally.ExprError, match="not JSON"):
        run_ci_locally.eval_expr("fromJSON(needs.setup.outputs.os)", ctx)


def test_and_or_return_values_as_github_does_and_booleans_print_lowercase():
    linux = _status_ctx()
    windows = _status_ctx()
    windows["runner"] = {"os": "Windows"}
    expr = "runner.os == 'Linux' && '1' || ''"
    assert run_ci_locally.eval_expr(expr, linux) == "1"
    assert run_ci_locally.eval_expr(expr, windows) == ""
    # The value reaches an env: block as "1" or "" -- never "True" or "False".
    assert run_ci_locally.resolve_string("${{ " + expr + " }}", windows) == ""
    assert run_ci_locally.resolve_string("${{ runner.os == 'Linux' }}", linux) == "true"
    assert run_ci_locally.resolve_string("${{ runner.os == 'Linux' }}", windows) == (
        "false"
    )


# --------------------------------------------------------------------------- #
# Step status: which step runs after a failure, and the job still fails.
# --------------------------------------------------------------------------- #
def test_a_step_with_no_status_function_runs_only_while_the_job_is_healthy():
    healthy, failed = _status_ctx(), _status_ctx(failed=True)
    assert run_ci_locally.eval_step_condition(None, healthy) is True
    assert run_ci_locally.eval_step_condition(None, failed) is False
    # An `if:` without a status function is `success() && (<if>)`.
    assert run_ci_locally.eval_step_condition("runner.os == 'Linux'", healthy) is True
    assert run_ci_locally.eval_step_condition("runner.os == 'Linux'", failed) is False
    # One that names a status function is evaluated as written.
    assert run_ci_locally.eval_step_condition("always()", failed) is True
    assert run_ci_locally.eval_step_condition("failure()", failed) is True
    assert run_ci_locally.eval_step_condition("success()", failed) is False
    cancelled = _status_ctx(cancelled=True)
    assert run_ci_locally.eval_step_condition("${{ !cancelled() }}", cancelled) is False


#: The condition the steps after "Font glyph coverage" carry in ci.yml.
_AFTER_GATE = (
    "${{ !cancelled() && (success() || steps.gate.outcome == 'failure') "
    "&& runner.os == 'Linux' }}"
)


def test_the_gate_outcome_condition_reads_the_gate_and_nothing_else():
    ctx = _status_ctx(failed=True, gate="failure")
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, ctx) is True
    # Another step failed and the gate did not: the later step still stops.
    ctx = _status_ctx(failed=True, gate="success")
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, ctx) is False
    ctx = _status_ctx(failed=True, gate="skipped")
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, ctx) is False
    # Nothing failed: it runs, exactly as the implicit success() would let it.
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, _status_ctx()) is True
    # The runner.os half still gates it.
    windows = _status_ctx(gate="failure", failed=True)
    windows["runner"] = {"os": "Windows"}
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, windows) is False
    # Cancelled: it never runs, whatever the gate did.
    cancelled = _status_ctx(failed=True, cancelled=True, gate="failure")
    assert run_ci_locally.eval_step_condition(_AFTER_GATE, cancelled) is False


_STATUS_WORKFLOW = """\
jobs:
  stepper:
    runs-on: ubuntu-latest
    steps:
      - name: before
        run: echo before @BEFORE@
      - name: gate
        id: gate
        if: runner.os == 'Linux'
        run: echo gate @GATE@
      - name: plain
        run: echo plain
      - name: reports own result
        if: ${{ !cancelled() && (success() || steps.gate.outcome == 'failure') }}
        run: echo own @OWN@
      - name: reports own result on Linux
        if: __AFTER_GATE__
        run: echo ownlinux
      - name: always
        if: always()
        run: echo always
      - name: on failure
        if: failure()
        run: echo onfailure
      - name: on success
        if: success()
        run: echo onsuccess
      - name: last
        run: echo last
""".replace("__AFTER_GATE__", _AFTER_GATE)


class _FakeShell:
    """Stands in for ``run_ci_locally._spawn``: reads the script it is handed,
    records it, and answers as a shell would -- without running anything."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, cmd, env):
        script = Path(cmd[-1]).read_bytes().decode("utf-8")
        self.calls.append(
            {
                "cmd": list(cmd),
                "script": script,
                "env": dict(env),
                "temp_existed": Path(env["RUNNER_TEMP"]).is_dir(),
            }
        )
        if "EXPORT-X" in script:
            with open(env["GITHUB_ENV"], "ab") as handle:
                handle.write(b"X=exported\n")
        if "OUTPUT-Y" in script:
            with open(env["GITHUB_OUTPUT"], "ab") as handle:
                handle.write(b"y=out1\n")
        return 1 if "FAIL-ME" in script else 0


@pytest.fixture
def fake_shell(monkeypatch, tmp_path):
    shell = _FakeShell()
    monkeypatch.setattr(run_ci_locally, "_find_bash", lambda: "bash")
    monkeypatch.setattr(run_ci_locally, "_spawn", shell)
    monkeypatch.setenv("ORCH_TEST_TMP", str(tmp_path / "declared-temp-root"))
    return shell


def _run_job(workflow_text: str, job: str, *argv: str):
    doc = yaml.safe_load(workflow_text)
    return run_ci_locally.run_job(doc, job, _parse("--job", job, *argv))


def _statuses(results) -> dict:
    return {r.name: r.status for r in results}


def _stepper(before="", gate="", own="") -> str:
    return (
        _STATUS_WORKFLOW.replace("@BEFORE@", before)
        .replace("@GATE@", gate)
        .replace("@OWN@", own)
    )


def test_a_failing_gate_does_not_hide_the_steps_after_it_and_the_job_fails(fake_shell):
    results = _run_job(_stepper(gate="FAIL-ME"), "stepper", "--runner-os", "Linux")
    assert _statuses(results) == {
        "before": "RAN-PASS",
        "gate": "RAN-FAIL",
        "plain": "NOT-RUN",  # no status function: success() is implied and false
        "reports own result": "RAN-PASS",
        "reports own result on Linux": "RAN-PASS",
        "always": "RAN-PASS",
        "on failure": "RAN-PASS",
        "on success": "NOT-RUN",
        "last": "NOT-RUN",
    }
    # The job fails: the exit code is 1, never 0, and it is the gate's doing.
    assert run_ci_locally.print_summary("stepper", results) == 1
    failed = [r.name for r in results if r.status == "RAN-FAIL"]
    assert failed == ["gate"]


def test_a_later_step_that_fails_does_not_hide_the_next_one(fake_shell):
    results = _run_job(
        _stepper(gate="FAIL-ME", own="FAIL-ME"), "stepper", "--runner-os", "Linux"
    )
    status = _statuses(results)
    assert status["gate"] == "RAN-FAIL"
    assert status["reports own result"] == "RAN-FAIL"
    # Each reports its own result: the one after still ran.
    assert status["reports own result on Linux"] == "RAN-PASS"
    assert run_ci_locally.print_summary("stepper", results) == 1


def test_a_failure_before_the_gate_still_stops_the_steps_after_it(fake_shell):
    """CONTROL. The condition is about the gate, not about failure in general:
    when another step fails first the gate is skipped (never 'failure'), so
    the steps that name the gate stay stopped, as they were."""
    results = _run_job(_stepper(before="FAIL-ME"), "stepper", "--runner-os", "Linux")
    status = _statuses(results)
    assert status["before"] == "RAN-FAIL"
    assert status["gate"] == "NOT-RUN"
    assert status["reports own result"] == "NOT-RUN"
    assert status["reports own result on Linux"] == "NOT-RUN"
    assert status["always"] == "RAN-PASS"
    assert status["on failure"] == "RAN-PASS"
    assert run_ci_locally.print_summary("stepper", results) == 1


def test_a_leg_that_skips_the_gate_behaves_as_before(fake_shell):
    """On a leg where the gate is skipped (here a simulated Windows runner) the
    condition reduces to success(): a failing step stops the steps after it."""
    results = _run_job(_stepper(own="FAIL-ME"), "stepper", "--runner-os", "Windows")
    status = _statuses(results)
    assert status["gate"] == "SKIPPED"
    assert status["plain"] == "RAN-PASS"
    assert status["reports own result"] == "RAN-FAIL"
    assert status["reports own result on Linux"] == "SKIPPED"  # runner.os half
    assert status["last"] == "NOT-RUN"
    assert run_ci_locally.print_summary("stepper", results) == 1


def test_an_all_green_run_executes_every_step_that_applies_and_exits_0(fake_shell):
    results = _run_job(_stepper(), "stepper", "--runner-os", "Linux")
    status = _statuses(results)
    assert status["on failure"] == "SKIPPED"  # failure() is false: nothing failed
    assert [n for n, s in status.items() if s == "RAN-PASS"] == [
        "before",
        "gate",
        "plain",
        "reports own result",
        "reports own result on Linux",
        "always",
        "on success",
        "last",
    ]
    assert run_ci_locally.print_summary("stepper", results) == 0


# --------------------------------------------------------------------------- #
# Matrix: a `fromJSON(needs.<job>.outputs.<name>)` matrix resolves its legs.
# --------------------------------------------------------------------------- #
_MATRIX_WORKFLOW = """\
jobs:
  setup:
    runs-on: ubuntu-latest
    outputs:
      os: ${{ steps.pick.outputs.os }}
    steps:
      - name: pick
        id: pick
        run: |
          if [[ "${{ github.event_name }}" == "pull_request" ]]; then
            echo 'os=["ubuntu-latest", "macos-latest"]' >> "${GITHUB_OUTPUT}"
          else
            echo 'os=["windows-latest"]' >> "${GITHUB_OUTPUT}"
          fi
  gate:
    needs: setup
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: ${{ fromJSON(needs.setup.outputs.os) }}
    steps:
      - name: only step
        run: echo hi
"""


@pytest.fixture
def matrix_workflow(tmp_path: Path) -> Path:
    path = tmp_path / "matrix.yml"
    path.write_text(_MATRIX_WORKFLOW, encoding="utf-8")
    return path


def _legs(stdout: str) -> list:
    found = re.search(r"matrix legs of job '[^']+': (\[[^\]]*\]) \(from", stdout)
    assert found, f"no 'matrix legs' line in:\n{stdout}"
    return ast.literal_eval(found.group(1))


#: A runner OS that is NOT this machine's, so "simulated" is true on every host.
_OTHER_OS, _OTHER_LABEL = (
    ("Windows", "windows-latest")
    if run_ci_locally._LOCAL_RUNNER_OS == "Linux"
    else ("Linux", "ubuntu-latest")
)
#: A runner OS with a leg in the matrix fixture's pull_request list
#: (ubuntu + macos) that is not this machine's.
_PR_OS, _PR_LABEL = (
    ("macOS", "macos-latest")
    if run_ci_locally._LOCAL_RUNNER_OS != "macOS"
    else ("Linux", "ubuntu-latest")
)


def test_a_dry_run_names_the_default_it_used_and_never_resolves_none(
    matrix_workflow,
):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(matrix_workflow),
            "--job",
            "gate",
            "--dry-run",
            "--runner-os",
            _OTHER_OS,
        ],
    )
    assert result.returncode == 3, result.stderr
    assert _legs(result.stdout) == [_OTHER_LABEL]
    assert "DECLARED LOCAL DEFAULT" in result.stdout
    assert "job 'setup' was not run" in result.stdout
    assert f"matrix leg selected: os={_OTHER_LABEL} (simulated OS)" in result.stdout
    assert f"SIMULATED runner OS: {_OTHER_OS}" in result.stdout
    assert f"(SIMULATED runner OS {_OTHER_OS})" in result.stdout  # the summary


def test_a_declared_needs_output_gives_the_legs_and_the_leg_is_selected(
    matrix_workflow,
):
    declared = 'setup.os=["ubuntu-latest","windows-latest","macos-latest"]'
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(matrix_workflow),
            "--job",
            "gate",
            "--dry-run",
            "--needs-output",
            declared,
            "--runner-os",
            _OTHER_OS,
        ],
    )
    assert result.returncode == 3, result.stderr
    assert _legs(result.stdout) == [
        "ubuntu-latest",
        "windows-latest",
        "macos-latest",
    ]
    assert "declared with --needs-output" in result.stdout
    assert f"matrix leg selected: os={_OTHER_LABEL} (simulated OS)" in result.stdout


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        ("setup.os=", "not JSON"),  # the needed job emitted nothing
        ("setup.os=[]", "resolved to no leg"),
        ("setup.os=not json at all", "not JSON"),
    ],
)
def test_a_matrix_that_resolves_to_no_leg_stops_the_run_with_exit_2(
    matrix_workflow, declared, message
):
    result = run_script(
        SCRIPT,
        [
            "--workflow",
            str(matrix_workflow),
            "--job",
            "gate",
            "--dry-run",
            "--needs-output",
            declared,
        ],
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert message in result.stderr
    assert "only step" not in result.stdout  # nothing was run in its place


def test_a_matrix_that_needs_a_job_the_workflow_lacks_exits_2(tmp_path):
    path = tmp_path / "ghost.yml"
    path.write_text(
        _MATRIX_WORKFLOW.replace("needs.setup", "needs.ghost"), encoding="utf-8"
    )
    result = run_script(SCRIPT, ["--workflow", str(path), "--job", "gate"])
    assert result.returncode == 2, result.stdout + result.stderr
    assert "needs job 'ghost', which the workflow does not define" in result.stderr


@pytest.mark.parametrize(
    "argv",
    [
        ["--needs-output", "no-equals-sign"],
        ["--needs-output", "nodot=1"],
        ["--context", "github.event.pull_request.base.sha"],
        ["--context", "secrets.TOKEN=x"],
        ["--context", "github=x"],
    ],
)
def test_malformed_context_and_needs_output_flags_exit_2(matrix_workflow, argv):
    result = run_script(
        SCRIPT,
        ["--workflow", str(matrix_workflow), "--job", "gate", "--dry-run", *argv],
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "must be" in result.stderr


# --------------------------------------------------------------------------- #
# Run-block plumbing: ${{ }} substitution, GITHUB_ENV, GITHUB_OUTPUT,
# RUNNER_TEMP, and GitHub's own `bash -eo pipefail` invocation.
# --------------------------------------------------------------------------- #
_PLUMBING_WORKFLOW = """\
jobs:
  plumbing:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    env:
      JOB_LEVEL: ${{ runner.os == 'Linux' && '1' || '' }}
    steps:
      - name: export
        id: exporter
        run: |
          echo EXPORT-X OUTPUT-Y ${{ matrix.os }}
          echo SHA ${{ github.event.pull_request.base.sha }}
      - name: read back
        run: echo READ ${{ env.X }} ${{ steps.exporter.outputs.y }}
"""


def test_run_blocks_are_substituted_and_see_what_earlier_steps_exported(
    fake_shell, tmp_path
):
    declared_root = tmp_path / "declared-temp-root"
    declared_root.mkdir()
    survivor = declared_root / "not-mine.txt"
    survivor.write_text("keep", encoding="utf-8")

    results = _run_job(
        _PLUMBING_WORKFLOW,
        "plumbing",
        "--runner-os",
        "Linux",
        "--context",
        "github.event.pull_request.base.sha=abc123",
    )
    assert _statuses(results) == {"export": "RAN-PASS", "read back": "RAN-PASS"}
    first, second = fake_shell.calls

    assert first["script"] == "echo EXPORT-X OUTPUT-Y ubuntu-latest\necho SHA abc123\n"
    assert second["script"] == "echo READ exported out1\n"  # GITHUB_ENV, GITHUB_OUTPUT
    assert second["env"]["X"] == "exported"
    assert first["env"]["JOB_LEVEL"] == "1"
    # GitHub's own invocation of `shell: bash`: a failure mid-block fails it.
    assert first["cmd"][1:5] == ["--noprofile", "--norc", "-eo", "pipefail"]
    # RUNNER_TEMP existed while the block ran, and is gone after the run, while
    # the folder it was made in, and what else lives there, is untouched.
    assert first["temp_existed"] is True
    assert not Path(first["env"]["RUNNER_TEMP"]).exists()
    assert survivor.read_text(encoding="utf-8") == "keep"
    assert Path(first["env"]["RUNNER_TEMP"]).parent == declared_root.resolve()


def test_an_env_value_that_is_false_is_empty_not_the_word_false(fake_shell):
    _run_job(_PLUMBING_WORKFLOW, "plumbing", "--runner-os", "Windows")
    assert fake_shell.calls[0]["env"]["JOB_LEVEL"] == ""


def test_an_expression_the_runner_cannot_evaluate_in_a_run_block_exits_2(
    fake_shell,
):
    workflow = (
        "jobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - name: bad\n        run: echo ${{ notAFunction() }}\n"
    )
    with pytest.raises(SystemExit) as excinfo:
        _run_job(workflow, "j")
    assert excinfo.value.code == 2
    assert fake_shell.calls == []  # nothing ran in its place


def test_command_files_hold_name_value_lines_and_delimited_blocks():
    text = "a=1\nb=two words\nbody<<EOF\nline one\nline two\nEOF\nc=3\n"
    assert run_ci_locally._parse_command_file(text) == {
        "a": "1",
        "b": "two words",
        "body": "line one\nline two",
        "c": "3",
    }


# --------------------------------------------------------------------------- #
# Real bash: the only cases that execute anything, and only trivial lines.
# --------------------------------------------------------------------------- #
@pytest.fixture
def real_bash(tmp_path: Path) -> str:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("no bash on PATH: the real-bash cases cannot run here")
    probe = tmp_path / "probe.txt"
    try:
        done = subprocess.run(
            [bash, "--noprofile", "--norc", "-c", f'echo ok > "{probe.as_posix()}"'],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"the bash on PATH could not be started ({exc!r})")
    if done.returncode != 0 or not probe.is_file():
        pytest.skip("the bash on PATH cannot write a posix-form path")
    return bash


def test_the_legs_of_the_current_ci_yml_are_computed_by_its_own_setup_job(
    real_bash,
):
    """Done-when: a run over the current ci.yml lists the quality-gate job's
    legs. ``--only`` with a name no step carries keeps every quality-gate step
    from running; the setup job is the one thing executed, and it is the
    workflow's own computation, not a list written here."""
    nothing = "no-step-is-named-this"
    pr = run_script(SCRIPT, ["--event", "pull_request", "--only", nothing])
    assert pr.returncode == 3, pr.stdout + pr.stderr
    assert _legs(pr.stdout) == ["ubuntu-latest", "windows-latest", "macos-latest"]
    assert "computed by running job 'setup' here" in pr.stdout

    push = run_script(
        SCRIPT, ["--event", "push", "--runner-os", "Windows", "--only", nothing]
    )
    assert push.returncode == 3, push.stdout + push.stderr
    assert _legs(push.stdout) == ["windows-latest"]


def test_the_matrix_fixture_is_computed_per_event_by_real_bash(
    real_bash, matrix_workflow
):
    base = ["--workflow", str(matrix_workflow), "--job", "gate", "--only", "zzz"]
    pr = run_script(SCRIPT, [*base, "--event", "pull_request", "--runner-os", _PR_OS])
    assert pr.returncode == 3, pr.stdout + pr.stderr
    assert _legs(pr.stdout) == ["ubuntu-latest", "macos-latest"]
    assert f"matrix leg selected: os={_PR_LABEL} (simulated OS)" in pr.stdout
    other = run_script(SCRIPT, [*base, "--event", "push", "--runner-os", "Windows"])
    assert other.returncode == 3, other.stdout + other.stderr
    assert _legs(other.stdout) == ["windows-latest"]


def test_a_failing_command_in_the_middle_of_a_block_fails_the_step(real_bash, tmp_path):
    path = tmp_path / "strict.yml"
    path.write_text(
        "jobs:\n"
        "  strict:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: middle failure is not hidden\n"
        "        run: |\n"
        "          false\n"
        "          echo after\n"
        "      - name: cleanup runs anyway\n"
        "        if: always()\n"
        "        run: echo cleaned\n"
        "      - name: skipped by the failure\n"
        "        run: echo never\n",
        encoding="utf-8",
    )
    result = run_script(SCRIPT, ["--workflow", str(path), "--job", "strict"])
    assert result.returncode == 1, result.stdout + result.stderr
    assert re.search(r"\[RAN-FAIL +\] middle failure is not hidden", result.stdout)
    assert re.search(r"\[RAN-PASS +\] cleanup runs anyway", result.stdout)
    assert re.search(r"\[NOT-RUN +\] skipped by the failure", result.stdout)
    # The line after `false` never ran: `echo after` would print it alone.
    assert "\nafter\n" not in result.stdout.replace("\r\n", "\n")


def test_github_env_and_output_files_work_with_a_real_shell(real_bash, tmp_path):
    path = tmp_path / "files.yml"
    path.write_text(
        "jobs:\n"
        "  files:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: write\n"
        "        id: writer\n"
        "        run: |\n"
        '          echo "FROM_FILE=carried" >> "${GITHUB_ENV}"\n'
        '          echo "answer=42" >> "${GITHUB_OUTPUT}"\n'
        "      - name: read\n"
        "        run: |\n"
        '          test "${FROM_FILE}" = carried\n'
        '          test "${{ steps.writer.outputs.answer }}" = 42\n'
        '          test -d "${RUNNER_TEMP}"\n',
        encoding="utf-8",
    )
    result = run_script(SCRIPT, ["--workflow", str(path), "--job", "files"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "executed: 2  passed: 2  failed: 0" in result.stdout
