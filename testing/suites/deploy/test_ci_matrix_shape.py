"""CI-matrix SHAPE test for the ``quality-gate`` and ``integration`` jobs
(T-40, remediation register; WP-6.6 extended it to ``integration``, decision
batch 2026-08-16; brought to the post-revert flat-matrix truth by the
hosted-runner revert that landed as d7daaa3).

Placed under ``testing/suites/deploy/`` (moved from ``tests/deploy/`` on
2026-08-30, see ADR-0065) -- AGT-09's owned surface (ADR-0043 §1 covers
the pipeline vehicles this agent runs; ``.github/workflows/ci.yml`` itself is
this agent's surface too) -- but deliberately **NOT**
``@pytest.mark.integration``, same ruling and precedent as
``test_packaging_artifacts.py`` and ``test_run_ci_router.py`` already in this
directory: this is a read-only YAML parse with no subprocess, no Docker, no
Nginx, no network. It belongs in the default gate.

WHY THIS TEST EXISTS: ``ci.yml``'s cross-OS ``quality-gate`` matrix and its
dedicated ``integration`` job are the two surfaces most likely to drift
silently -- a matrix that narrows (a future edit drops a leg), widens
(someone adds a leg without updating this table), or is reshaped (flat
``matrix.os`` collapsed back into a per-leg ``include:`` block, or vice
versa) should be REPORTED BY THE SUITE, not discovered later by manual audit
of the workflow file. Likewise a silent repoint of ``integration``'s
``runs-on`` (hosted <-> self-hosted, or to a different hosted OS) or a
dropped test root from its ``pytest -m integration`` invocation.

CURRENT SHAPE (post-revert, matches ci.yml as committed at d7daaa3): both
jobs run on PLAIN HOSTED GitHub runners -- there is no self-hosted leg or
self-hosted label anywhere in this workflow any more. ``quality-gate`` is a
FLAT ``matrix: {os: [...]}`` (no per-leg ``include:`` map, so there is no
per-leg ``runs_on``/``timeout`` to assert -- see the job-level
``timeout-minutes`` assertion below, which is the shape this table's old
per-leg ``timeout`` field was replaced by). ``integration`` runs on a single
``ubuntu-latest`` string, not a self-hosted label array.
"""

from __future__ import annotations

import yaml

from .conftest import REPO_ROOT

CI_YAML = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# EXPECTATION TABLE (T-40) -- the quality-gate matrix's CURRENT truth, named
# explicitly so any silent narrowing OR widening is caught here.
#
# *** WHEN THE MATRIX CHANGES, THIS TABLE MUST BE UPDATED IN THE SAME COMMIT
# *** THAT CHANGES ci.yml's quality-gate matrix -- that is the entire point
# *** of asserting against a named constant instead of a bare leg count: a
# *** maintainer who forgets leaves a RED test, not a green one that quietly
# *** stopped meaning anything.
EXPECTED_QUALITY_GATE_OS_LIST = ["ubuntu-latest", "windows-latest", "macos-latest"]

# The per-leg ``timeout`` field the old ``include:``-shaped table used to
# carry no longer exists (the flat matrix has no per-leg key to hang it on);
# its replacement is this ONE job-level wall-clock cap, asserted separately
# below so that coverage is not silently lost in the revert.
EXPECTED_QUALITY_GATE_JOB_TIMEOUT_MINUTES = 75


def _load_ci_yaml() -> dict:
    return yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))


def test_quality_gate_matrix_leg_count_matches_expectation_table():
    data = _load_ci_yaml()
    observed_oses = data["jobs"]["quality-gate"]["strategy"]["matrix"]["os"]
    assert len(observed_oses) == len(EXPECTED_QUALITY_GATE_OS_LIST), (
        f"quality-gate matrix now has {len(observed_oses)} leg(s): "
        f"{observed_oses} -- EXPECTED_QUALITY_GATE_OS_LIST in this test "
        f"still declares {len(EXPECTED_QUALITY_GATE_OS_LIST)}: "
        f"{EXPECTED_QUALITY_GATE_OS_LIST}. If this narrowing/widening was "
        "deliberate, update EXPECTED_QUALITY_GATE_OS_LIST in this test in "
        "the SAME commit that changed ci.yml."
    )


def test_quality_gate_matrix_legs_match_expectation_table_exactly():
    """Not just the count: the exact OS list, IN ORDER, must match the
    declared table -- a silent reorder, rename (e.g. ``windows-latest`` ->
    a pinned ``windows-2025``) or swap-in of a self-hosted label is caught
    here even when the leg COUNT happens to stay the same."""
    data = _load_ci_yaml()
    observed_oses = data["jobs"]["quality-gate"]["strategy"]["matrix"]["os"]
    assert observed_oses == EXPECTED_QUALITY_GATE_OS_LIST


def test_quality_gate_strategy_fail_fast_and_job_timeout():
    """Two independent shape facts kept in one test so the table stays at
    six tests (the number this file has carried since T-40), not because
    they are conceptually the same check:

    - fail-fast: false is load-bearing (ci.yml's own comment: a genuine
      platform-specific regression on one leg must not cancel the others) --
      a silent flip to true would be a real behaviour change this suite
      should catch, not just the leg table.
    - timeout-minutes is the job-level wall-clock cap that REPLACED the old
      per-leg ``timeout`` field EXPECTED_QUALITY_GATE_LEGS used to carry
      (the flat ``matrix.os`` shape has no per-leg key left to hang a
      per-leg timeout on). Without this assertion a silent widening or
      narrowing of the single job-level cap would go uncaught by this suite
      entirely -- exactly the kind of coverage the revert could otherwise
      have silently dropped."""
    data = _load_ci_yaml()
    assert data["jobs"]["quality-gate"]["strategy"]["fail-fast"] is False
    assert (
        data["jobs"]["quality-gate"]["timeout-minutes"]
        == EXPECTED_QUALITY_GATE_JOB_TIMEOUT_MINUTES
    )


# EXPECTATION for the `integration` job's runs-on target -- post-revert
# (d7daaa3), this is a single hosted OS string, not a self-hosted label
# array. *** WHEN THIS CHANGES, UPDATE THIS CONSTANT IN THE SAME COMMIT. ***
EXPECTED_INTEGRATION_RUNS_ON = "ubuntu-latest"


def test_integration_job_exists_and_is_not_commented_out():
    """The ``integration`` job must be real YAML, not prose inside a comment
    block. Before WP-6.2 the entire job was commented out, so
    ``data["jobs"]`` never had an ``"integration"`` key at all -- this is the
    exact silent-disable shape a future edit could reintroduce."""
    data = _load_ci_yaml()
    assert "integration" in data["jobs"], (
        "the integration job is missing from the parsed workflow -- either it "
        "was commented out again (WP-6.2 re-enabled it) or renamed; update "
        "this test in the SAME commit if the rename/removal was deliberate"
    )


def test_integration_job_runs_on_self_hosted_windows_labels():
    """Not just present: pinned to ``ubuntu-latest`` -- post-revert
    (d7daaa3) this job runs on a plain hosted runner, so a silent repoint to
    a self-hosted label array (or to a different hosted OS) is exactly the
    kind of drift this suite exists to catch. Name kept for history/grep
    continuity with the pre-revert self-hosted-era assertion it replaces;
    the assertion itself now checks the opposite direction -- that no
    self-hosted label has crept back in."""
    data = _load_ci_yaml()
    assert data["jobs"]["integration"]["runs-on"] == EXPECTED_INTEGRATION_RUNS_ON


def test_integration_job_names_both_test_roots():
    """HARD RULE (ADR-0043 §3a): the integration job's pytest invocation must
    name BOTH ``testing/suites/deploy/`` and ``testing/suites/backend/`` --
    naming only one is exactly how a suite silently stops running while the
    check stays green (after the ADR-0043 move, ``pytest -m integration
    tests/backend/`` alone collected 0 and exited 5; the roots were later
    relocated under ``testing/suites/`` on 2026-08-30, ADR-0065). A read-only
    substring check on the step's own
    command, so a future edit that drops either root fails here instead of
    silently shrinking coverage."""
    data = _load_ci_yaml()
    steps = data["jobs"]["integration"]["steps"]
    run_commands = " ".join(
        step.get("run", "") for step in steps if isinstance(step, dict)
    )
    assert "testing/suites/deploy/" in run_commands
    assert "testing/suites/backend/" in run_commands
