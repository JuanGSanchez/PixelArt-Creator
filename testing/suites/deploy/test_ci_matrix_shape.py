"""CI-matrix SHAPE test for the ``quality-gate`` and ``integration`` jobs
(T-40, remediation register; WP-6.6 extended it to ``integration``, decision
batch 2026-08-16).

Placed under ``testing/suites/deploy/`` (moved from ``tests/deploy/`` on
2026-08-30, see ADR-0065) -- AGT-09's owned surface (ADR-0043 §1 covers
the pipeline vehicles this agent runs; ``.github/workflows/ci.yml`` itself is
this agent's surface too) -- but deliberately **NOT**
``@pytest.mark.integration``, same ruling and precedent as
``test_packaging_artifacts.py`` and ``test_run_ci_router.py`` already in this
directory: this is a read-only YAML parse with no subprocess, no Docker, no
Nginx, no network. It belongs in the default gate.

WHY THIS TEST EXISTS: ``ci.yml`` currently runs the cross-OS quality-gate
matrix on a SINGLE self-hosted Windows leg only (user decision 2026-08-02,
cost-avoidance -- see the "TEMPORARY" revert block at the top of that file).
The two hosted legs (ubuntu-latest, macos-latest) are commented out, not
deleted, pending that revert. A matrix that silently narrows further (e.g. a
future edit drops the one remaining leg, or accidentally leaves a
half-uncommented hosted leg producing a malformed fourth entry) or silently
widens (someone uncomments a leg without updating this table, or the revert
happens without anyone noticing this suite needed a matching update) should
be REPORTED BY THE SUITE, not discovered later by manual audit of the
workflow file.

WP-6.2 (2026-08-16, D-16/D-17) re-enabled the ``integration`` job -- it was
previously ENTIRELY commented out, so ``data["jobs"]`` never even had an
``"integration"`` key and this file had nothing to assert about it. It now
targets the same self-hosted Windows label set as the ``quality-gate``
windows-selfhosted leg. The same silent-narrow/silent-widen risk applies here
too (a future edit repointing it back to a hosted runner, or dropping either
named test root from its ``pytest -m integration`` invocation, must fail this
suite, not wait for a manual audit) -- ``EXPECTED_INTEGRATION_RUNS_ON`` and
the two functions below cover it.
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
# *** stopped meaning anything. In particular, carrying out the "REVERT" steps
# *** documented at the top of ci.yml (restoring the ubuntu-latest and
# *** macos-latest legs, removing the windows-selfhosted leg) requires
# *** updating EXPECTED_QUALITY_GATE_LEGS to the post-revert 2-leg (or 3-leg,
# *** if windows-latest is also restored) shape.
EXPECTED_QUALITY_GATE_LEGS = [
    {
        "os": "windows-selfhosted",
        "runs_on": ["self-hosted", "Windows", "X64"],
        "timeout": 45,
    },
]


def _load_ci_yaml() -> dict:
    return yaml.safe_load(CI_YAML.read_text(encoding="utf-8"))


def test_quality_gate_matrix_leg_count_matches_expectation_table():
    data = _load_ci_yaml()
    include = data["jobs"]["quality-gate"]["strategy"]["matrix"]["include"]
    observed_oses = [leg.get("os") for leg in include]
    expected_oses = [leg["os"] for leg in EXPECTED_QUALITY_GATE_LEGS]
    assert len(include) == len(EXPECTED_QUALITY_GATE_LEGS), (
        f"quality-gate matrix now has {len(include)} leg(s): {observed_oses} "
        f"-- EXPECTED_QUALITY_GATE_LEGS in this test still declares "
        f"{len(EXPECTED_QUALITY_GATE_LEGS)}: {expected_oses}. If this "
        "narrowing/widening was deliberate, update EXPECTED_QUALITY_GATE_LEGS "
        "in this test in the SAME commit that changed ci.yml."
    )


def test_quality_gate_matrix_legs_match_expectation_table_exactly():
    """Not just the count: the OS set, runs-on target and per-leg timeout must
    match the declared table exactly (dict equality on every field)."""
    data = _load_ci_yaml()
    include = data["jobs"]["quality-gate"]["strategy"]["matrix"]["include"]
    assert include == EXPECTED_QUALITY_GATE_LEGS


def test_quality_gate_strategy_fail_fast_is_false():
    """fail-fast: false is load-bearing (ci.yml's own comment: a genuine
    platform-specific regression on one leg must not cancel the others) --
    a silent flip to true would be a real behaviour change this suite should
    catch, not just the leg table."""
    data = _load_ci_yaml()
    assert data["jobs"]["quality-gate"]["strategy"]["fail-fast"] is False


# EXPECTATION for the `integration` job's runs-on target (WP-6.2, 2026-08-16,
# D-16/D-17) -- same self-hosted label set as the quality-gate
# windows-selfhosted leg above. *** WHEN THIS CHANGES (e.g. the eventual
# public-repo revert to ubuntu-latest), UPDATE THIS CONSTANT IN THE SAME
# COMMIT. ***
EXPECTED_INTEGRATION_RUNS_ON = ["self-hosted", "Windows", "X64"]


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
    """Not just present: pinned to the self-hosted labels, matching the
    zero-hosted-minutes hard constraint (D-16/D-17) -- a silent repoint back
    to a hosted runner (or a widened/narrowed label set) is exactly the
    PUBLIC-REPO HAZARD ci.yml's own comment warns against making by accident
    before the repository is actually public."""
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
