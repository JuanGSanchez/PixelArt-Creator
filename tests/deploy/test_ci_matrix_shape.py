"""CI-matrix SHAPE test for the ``quality-gate`` job (T-40, remediation register).

Placed under ``tests/deploy/`` -- AGT-09's owned surface (ADR-0043 §1 covers
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
