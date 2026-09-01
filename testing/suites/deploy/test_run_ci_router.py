"""Unit tests for `scripts/run_ci.py`, the GitHub-Actions/local-fallback router.

Placed under ``testing/suites/deploy/`` (moved from ``tests/deploy/`` on
2026-08-30, ADR-0065) per this task's direction (AGT-09's owned
surface, ADR-0043) even though these tests differ in shape from
``test_vps_localhost.py``/``test_nginx_wss_localhost.py``: they exercise the
router's pure classification logic and its exit-code contract, not the
launcher-subprocess/Docker/Nginx deployment-acceptance pattern those modules
use. Deliberately **NOT** ``@pytest.mark.integration``: every test here is
hermetic (no network, no subprocess spawn of the real backend, no Docker/
Nginx requirement) and must run in the default gate, which is exactly what
lets this module serve as this session's own proof that the router's
classification logic behaves correctly -- see the accompanying report for
the real, observed `pytest` run.

No test in this module makes a real network or ``gh`` call. Every
``gh``/``git``-calling function the router exposes is exercised one of
three ways: `fetch_recent_runs`/`fetch_run_jobs`/`fetch_job_annotations`
are replaced with a canned fake via `classify_current_state`'s injectable
`fetch_runs`/`fetch_jobs`/`fetch_annotations` parameters; `run_windows_leg`,
`do_dispatch`, and `fetch_recent_runs`/`classify_current_state` called
directly (not through the injectable parameters, added 2026-09-01 to pin
the ci.yml workflow-scoping fix -- see the tests near the end of this
file) monkeypatch `run_ci.subprocess.run` itself to capture the
constructed command and return a canned completed-process stand-in,
never shelling out; and the rest (`classify_dispatch`, `overall_exit`,
`macos_leg`, `linux_leg`) are exercised directly as pure functions that
never shell out at all.

The router's local fallback covers ONLY the Windows leg (natively); the
Linux leg it once ran inside a container (Docker/Podman + a bind-mounted
``.ci/Dockerfile``) was removed by user decision 2026-08-02 -- it had never
been built or run in any session and CI now runs on a self-hosted Windows
runner. `linux_leg()` is a pure function (like `macos_leg()`) that always
reports UNCOVERABLE, so its test needs no monkeypatching and passes
identically on any host.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

# `scripts/` is not an installed package (no `scripts/__init__.py`), so import
# run_ci.py directly by file path -- the same pattern used by this project's
# other scripts-under-test call sites.
_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
_SPEC = importlib.util.spec_from_file_location("run_ci", _SCRIPTS_DIR / "run_ci.py")
assert _SPEC is not None and _SPEC.loader is not None
run_ci = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("run_ci", run_ci)
_SPEC.loader.exec_module(run_ci)

JobObservation = run_ci.JobObservation
classify_dispatch = run_ci.classify_dispatch
classify_current_state = run_ci.classify_current_state
build_job_observations = run_ci.build_job_observations
overall_exit = run_ci.overall_exit
macos_leg = run_ci.macos_leg
linux_leg = run_ci.linux_leg
run_windows_leg = run_ci.run_windows_leg
LegResult = run_ci.LegResult
fetch_recent_runs = run_ci.fetch_recent_runs
do_dispatch = run_ci.do_dispatch


# --------------------------------------------------------------------------- #
# Real-shaped fixture: run 30567099577 (HEAD a3f42de0a042a0ae2ef3a77e0c90ebb5
# aa0bffdd on `main`), as observed THIS session via
#   gh run list --json databaseId,headSha,status,conclusion,...
#   gh run view 30567099577 --json jobs
#   gh api repos/JuanGSanchez/PixelArt-Creator/check-runs/90954249751/annotations
# Every value below (job names, conclusions, elapsed, the exact annotation
# text) is copied from that real output, not invented.
# --------------------------------------------------------------------------- #
_BILLING_ANNOTATION = (
    "The job was not started because recent account payments have failed or "
    "your spending limit needs to be increased. Please check the 'Billing & "
    "plans' section in your settings"
)


def _raw_job(
    name: str, conclusion, started: str, completed: str, steps: List[Any]
) -> Dict[str, Any]:
    return {
        "databaseId": hash(name) & 0xFFFFFFFF,
        "name": name,
        "conclusion": conclusion,
        "status": "completed",
        "startedAt": started,
        "completedAt": completed,
        "steps": steps,
    }


def _blocked_run_30567099577_jobs_raw() -> List[Dict[str, Any]]:
    """The 4 failed + 2 skipped jobs of the real blocked run, shaped exactly
    as `gh run view --json jobs` reported them (steps: [] on every failed
    job; skipped jobs carry no annotation and are excluded from
    classification as non-actionable)."""
    return [
        _raw_job(
            "quality-gate (macos-latest)",
            "failure",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:46Z",
            [],
        ),
        _raw_job(
            "quality-gate (ubuntu-latest)",
            "failure",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:44Z",
            [],
        ),
        _raw_job(
            "integration (ubuntu-latest)",
            "failure",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:44Z",
            [],
        ),
        _raw_job(
            "quality-gate (windows-latest)",
            "failure",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:44Z",
            [],
        ),
        _raw_job(
            "regenerate-constraints (ubuntu-latest, manual)",
            "skipped",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:41Z",
            [],
        ),
        _raw_job(
            "build-installers (${{ matrix.os }})",
            "skipped",
            "2026-07-30T17:41:41Z",
            "2026-07-30T17:41:41Z",
            [],
        ),
    ]


def _fake_annotations_all_billing_blocked(repo: str, job_id) -> List[str]:
    return [_BILLING_ANNOTATION]


def test_classify_dispatch_real_shaped_blocked_fixture_is_blocked_at_job_start():
    jobs_raw = _blocked_run_30567099577_jobs_raw()
    jobs = build_job_observations(
        jobs_raw, "JuanGSanchez/PixelArt-Creator", _fake_annotations_all_billing_blocked
    )
    status, reason = classify_dispatch(jobs)
    assert status == "BLOCKED_AT_JOB_START"
    assert "billing" in reason.lower()


def test_classify_current_state_real_shaped_blocked_fixture_via_injected_fakes():
    """End-to-end through classify_current_state with injected fakes -- zero
    network, but exercises the exact same code path a real invocation does."""

    def fake_fetch_runs(repo, branch, limit):
        return [
            {
                "databaseId": 30567099577,
                "event": "push",
                "headBranch": "main",
                "headSha": "a3f42de0a042a0ae2ef3a77e0c90ebb5aa0bffdd",
                "status": "completed",
                "conclusion": "failure",
                "createdAt": "2026-07-30T17:41:40Z",
                "updatedAt": "2026-07-30T17:41:47Z",
                "displayTitle": "ci(tooling): ...",
            }
        ]

    def fake_fetch_jobs(repo, run_id):
        assert run_id == 30567099577
        return _blocked_run_30567099577_jobs_raw()

    status, run_ref, reason, jobs = classify_current_state(
        "JuanGSanchez/PixelArt-Creator",
        "main",
        "a3f42de0a042a0ae2ef3a77e0c90ebb5aa0bffdd",
        20,
        fetch_runs=fake_fetch_runs,
        fetch_jobs=fake_fetch_jobs,
        fetch_annotations=_fake_annotations_all_billing_blocked,
    )
    assert status == "BLOCKED_AT_JOB_START"
    assert run_ref is not None and run_ref["databaseId"] == 30567099577
    assert "exact HEAD sha match" in reason
    assert len(jobs) == 6


def test_classify_current_state_no_runs():
    status, run_ref, reason, jobs = classify_current_state(
        "owner/repo", "main", "deadbeef", 20, fetch_runs=lambda repo, branch, limit: []
    )
    assert status == "NO_RUNS"
    assert run_ref is None
    assert jobs == []


def test_classify_current_state_run_still_in_progress_is_unknown():
    def fake_fetch_runs(repo, branch, limit):
        return [
            {
                "databaseId": 1,
                "headSha": "abc123",
                "status": "in_progress",
                "conclusion": None,
            }
        ]

    status, run_ref, reason, jobs = classify_current_state(
        "owner/repo", "main", "abc123", 20, fetch_runs=fake_fetch_runs
    )
    assert status == "UNKNOWN"
    assert "not completed yet" in reason
    assert jobs == []


def test_classify_current_state_falls_back_to_latest_run_when_head_sha_absent():
    def fake_fetch_runs(repo, branch, limit):
        return [
            {
                "databaseId": 2,
                "headSha": "other-sha",
                "status": "completed",
                "conclusion": "success",
            }
        ]

    def fake_fetch_jobs(repo, run_id):
        return [
            _raw_job(
                "quality-gate (ubuntu-latest)",
                "success",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:20:00Z",
                [1, 2, 3],
            )
        ]

    status, run_ref, reason, jobs = classify_current_state(
        "owner/repo",
        "main",
        "this-sha-does-not-appear-anywhere",
        20,
        fetch_runs=fake_fetch_runs,
        fetch_jobs=fake_fetch_jobs,
        fetch_annotations=lambda repo, job_id: [],
    )
    assert status == "HEALTHY"
    assert "no exact HEAD match found" in reason


def test_classify_dispatch_healthy_fixture():
    jobs = [
        JobObservation("quality-gate (ubuntu-latest)", "success", 1620.0, 40, []),
        JobObservation("quality-gate (windows-latest)", "success", 980.0, 35, []),
    ]
    status, reason = classify_dispatch(jobs)
    assert status == "HEALTHY"


def test_classify_dispatch_weak_signal_annotation_without_fast_shape_is_unknown():
    # Annotation present, but NOT the sub-10s/zero-step shape (elapsed is 20s
    # -- above BLOCKED_MAX_JOB_ELAPSED_S=10 and below HEALTHY_MIN_JOB_ELAPSED_S
    # =30, i.e. deliberately in the ambiguous middle) -- weaker evidence than
    # both signals together, must not be classified BLOCKED_AT_JOB_START (and
    # must not be misread as HEALTHY either, since it never crosses the
    # healthy floor).
    jobs = [
        JobObservation(
            "quality-gate (ubuntu-latest)",
            "failure",
            20.0,
            3,
            [
                "The job was not started because recent account payments have "
                "failed or your spending limit needs to be increased."
            ],
        )
    ]
    status, reason = classify_dispatch(jobs)
    assert status == "UNKNOWN"
    assert "weaker evidence" in reason


def test_classify_dispatch_weak_signal_fast_shape_without_annotation_is_unknown():
    # Fast + zero-step, but NO billing annotation (e.g. a genuine transient
    # infra hiccup) -- must not be classified BLOCKED_AT_JOB_START either.
    jobs = [JobObservation("quality-gate (ubuntu-latest)", "failure", 4.0, 0, [])]
    status, reason = classify_dispatch(jobs)
    assert status == "UNKNOWN"


def test_classify_dispatch_contradictory_signals_is_unknown():
    jobs = [
        JobObservation(
            "quality-gate (ubuntu-latest)", "failure", 3.0, 0, [_BILLING_ANNOTATION]
        ),
        JobObservation("quality-gate (windows-latest)", "success", 1200.0, 30, []),
    ]
    status, reason = classify_dispatch(jobs)
    assert status == "UNKNOWN"
    assert "contradictory" in reason


def test_classify_dispatch_all_skipped_is_unknown():
    jobs = [
        JobObservation("build-installers (ubuntu-latest)", "skipped", 0.1, 0, []),
        JobObservation("regenerate-constraints", None, None, None, []),
    ]
    status, reason = classify_dispatch(jobs)
    assert status == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Exit-code contract (overall_exit): the hard rule under test is that an
# uncoverable-only or blocked-only run must NOT exit 0.
# --------------------------------------------------------------------------- #
def test_overall_exit_all_passed_and_something_ran_is_zero():
    legs = [
        LegResult("linux", "UNCOVERABLE", "n/a", "n/a"),
        LegResult("windows", "RAN-PASS", "ok", "local-native"),
        LegResult("macos", "UNCOVERABLE", "n/a", "n/a"),
    ]
    assert overall_exit(legs) == 0


def test_overall_exit_a_failure_is_one():
    legs = [
        LegResult("linux", "UNCOVERABLE", "n/a", "n/a"),
        LegResult("windows", "RAN-FAIL", "a test failed", "local-native"),
        LegResult("macos", "UNCOVERABLE", "n/a", "n/a"),
    ]
    assert overall_exit(legs) == 1


def test_overall_exit_blocked_only_is_two_never_zero():
    legs = [
        LegResult("linux", "UNCOVERABLE", "n/a", "n/a"),
        LegResult("windows", "BLOCKED", "not a windows host", "n/a"),
        LegResult("macos", "UNCOVERABLE", "n/a", "n/a"),
    ]
    rc = overall_exit(legs)
    assert rc == 2
    assert rc != 0


def test_overall_exit_uncoverable_only_is_three_never_zero():
    legs = [
        LegResult("linux", "UNCOVERABLE", "n/a", "n/a"),
        LegResult("macos", "UNCOVERABLE", "n/a", "n/a"),
    ]
    rc = overall_exit(legs)
    assert rc == 3
    assert rc != 0


def test_overall_exit_empty_is_three():
    assert overall_exit([]) == 3


# --------------------------------------------------------------------------- #
# Per-leg behaviour: macOS and Linux are always UNCOVERABLE (pure functions,
# no monkeypatching needed -- neither leg has a local execution mechanism on
# any host).
# --------------------------------------------------------------------------- #
def test_macos_leg_is_always_uncoverable():
    leg = macos_leg()
    assert leg.outcome == "UNCOVERABLE"
    assert "Apple" in leg.detail or "apple" in leg.detail.lower()


def test_linux_leg_is_always_uncoverable():
    leg = linux_leg()
    assert leg.leg == "linux"
    assert leg.outcome == "UNCOVERABLE"
    assert leg.evidence_class == "n/a"
    assert "removed" in leg.detail.lower()


def test_run_fallback_reports_linux_uncoverable_windows_blocked_off_windows_host():
    """End-to-end through run_fallback on a non-Windows host: linux and macos
    are UNCOVERABLE, windows is BLOCKED (no native host), and the overall
    exit code must therefore be 2 -- never 0 -- via overall_exit."""
    args = types.SimpleNamespace(only=[], skip=[])
    legs = run_ci.run_fallback(args, "Linux")
    by_leg = {leg.leg: leg for leg in legs}
    assert by_leg["linux"].outcome == "UNCOVERABLE"
    assert by_leg["macos"].outcome == "UNCOVERABLE"
    assert by_leg["windows"].outcome == "BLOCKED"
    assert overall_exit(legs) == 2


def test_run_windows_leg_blocked_on_non_windows_host():
    args = types.SimpleNamespace(only=[], skip=[])
    leg = run_windows_leg(args, "Linux")
    assert leg.outcome == "BLOCKED"
    assert "windows host" in leg.detail.lower()


def test_run_windows_leg_maps_subprocess_return_codes(monkeypatch):
    args = types.SimpleNamespace(only=[], skip=[])

    class _FakeCompleted:
        def __init__(self, rc):
            self.returncode = rc

    for rc, expected_outcome in (
        (0, "RAN-PASS"),
        (1, "RAN-FAIL"),
        (3, "BLOCKED"),
        (2, "BLOCKED"),
    ):
        monkeypatch.setattr(
            run_ci.subprocess, "run", lambda *a, **k: _FakeCompleted(rc)
        )
        leg = run_windows_leg(args, "Windows")
        assert leg.outcome == expected_outcome, f"rc={rc}"


# --------------------------------------------------------------------------- #
# ci.yml workflow-scoping fix (coordinator-requested, 2026-09-01 follow-up to
# the CI lean-push split): before the split this repository had exactly one
# workflow file, so an unfiltered `gh run list` could only ever return ci.yml
# runs. After the split there are three (ci.yml, build-installers.yml,
# regenerate-constraints.yml), and build-installers.yml fires on `v*` tags --
# release time, exactly when a caller is most likely to ask run_ci.py "is CI
# healthy?" and exactly when the most recent run on the repo may NOT be a
# ci.yml run at all. CI health must be judged from CI runs, not from an
# installer run -- these tests pin exactly that.
# --------------------------------------------------------------------------- #
def _capture_gh_calls(monkeypatch):
    """Monkeypatch run_ci.subprocess.run to capture every constructed `gh`
    command (as a list, never a shell string) and return a canned completed
    process (`returncode=0`, `stdout="[]"`, a valid empty JSON array) --
    never touching the network. Returns the list the calls are appended to."""
    captured: List[List[str]] = []

    class _FakeCompleted:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def fake_run(cmd, *args, **kwargs):
        captured.append(list(cmd))
        return _FakeCompleted()

    monkeypatch.setattr(run_ci.subprocess, "run", fake_run)
    return captured


def test_fetch_recent_runs_scopes_to_ci_workflow_by_default(monkeypatch):
    captured = _capture_gh_calls(monkeypatch)

    fetch_recent_runs("owner/repo", "main", 20)

    assert len(captured) == 1
    cmd = captured[0]
    assert "--workflow" in cmd, (
        f"fetch_recent_runs()'s default call built {cmd!r} with no "
        "--workflow filter -- gh run list would return runs from EVERY "
        "workflow in the repo, so a build-installers or "
        "regenerate-constraints run could be read as the CI verdict"
    )
    assert cmd[cmd.index("--workflow") + 1] == run_ci.CI_WORKFLOW_FILE == "ci.yml"


def test_classify_current_state_production_default_scopes_to_ci_workflow(monkeypatch):
    """Same regression, proven one level up: `classify_current_state`'s own
    PRODUCTION default (no injected `fetch_runs` fake -- every other test in
    this file injects one) must build the same ci.yml-scoped `gh run list`
    command. This is the actual call path a real invocation of run_ci.py
    takes when asking "is CI healthy?"."""
    captured = _capture_gh_calls(monkeypatch)

    classify_current_state("owner/repo", "main", "deadbeef", 20)

    assert len(captured) == 1
    cmd = captured[0]
    assert cmd[cmd.index("--workflow") + 1] == "ci.yml"


def test_fetch_recent_runs_workflow_none_is_explicitly_unfiltered(monkeypatch):
    """The escape hatch stays available and explicit, never silent: passing
    ``workflow=None`` opts OUT of the ci.yml default -- confirms the default
    is a parameter a caller can override, not a hard-coded narrowing nobody
    could undo."""
    captured = _capture_gh_calls(monkeypatch)

    fetch_recent_runs("owner/repo", None, 5, workflow=None)

    assert "--workflow" not in captured[0]


def test_do_dispatch_scopes_post_dispatch_lookup_to_dispatched_workflow(monkeypatch):
    """`do_dispatch()` issues TWO `gh` calls: the dispatch itself, then a
    lookup for the new run's URL. The dispatch must name the workflow FILE
    the target maps to (no `-f target=...` -- neither new file accepts an
    input any more); the lookup must scope to that SAME file, not silently
    fall back to the ci.yml default, or a concurrently-running ci.yml run
    could be reported as the just-dispatched run's URL."""
    captured = _capture_gh_calls(monkeypatch)
    monkeypatch.setattr(run_ci.time, "sleep", lambda *_: None)

    args = types.SimpleNamespace(
        dispatch_target="build-installers", branch="fix-ci-lean-push"
    )
    rc = do_dispatch("JuanGSanchez/PixelArt-Creator", args)

    assert rc == 0
    assert len(captured) == 2
    dispatch_cmd, lookup_cmd = captured
    assert dispatch_cmd == [
        "gh",
        "workflow",
        "run",
        "build-installers.yml",
        "--repo",
        "JuanGSanchez/PixelArt-Creator",
    ]
    assert "-f" not in dispatch_cmd
    assert lookup_cmd[lookup_cmd.index("--workflow") + 1] == "build-installers.yml"
