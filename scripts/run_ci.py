#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: run_ci  (standalone P11 script -- PixelArt Creator system)
# =============================================================================
# PURPOSE: THE ROUTER. Decide, per invocation, whether GitHub Actions can
#   actually execute a run for this repo/branch/HEAD, and act accordingly:
#     - HEALTHY              -> report it; hand off to Actions only if
#                                --dispatch is explicitly given (never
#                                silently).
#     - BLOCKED_AT_JOB_START  -> run the same checks LOCALLY: the Windows leg
#       / NO_RUNS / UNKNOWN     natively (ADR-0045's scripts/
#                                run_ci_locally.py), and report BOTH the
#                                Linux and macOS legs as permanently
#                                UNCOVERABLE on this host shape -- there is
#                                no local execution mechanism for either.
#   This is the fallback layer the user asked for on top of
#   docs/adr/0045-local-ci-execution-strategy.md's `scripts/run_ci_locally.py`
#   (which this script calls, never re-implements -- see CRITICAL DESIGN
#   CONSTRAINT below).
# FLAVOUR: standalone
# LOCATION: scripts/run_ci.py
# INVOKED BY: AGT-09 GitHub/DevOps; any developer who wants "just make CI run,
#   whichever way is actually available right now."
# RUNTIME: Python 3.10+ (CPython, stdlib only -- `gh` CLI (authenticated) and
#   `git` on PATH for classification and for the Windows leg).
# ENTRYPOINT: python scripts/run_ci.py [--repo OWNER/NAME] [--branch NAME]
#             [--head-sha SHA] [--gh-limit N] [--classify-only]
#             [--dispatch [--dispatch-target {build-installers,regenerate-constraints}]]
#             [--local] [--only SUBSTRING ...] [--skip SUBSTRING ...]
# INPUTS:
#   --repo        (CLI, optional): "owner/name". Default: resolved via
#                 `gh repo view --json nameWithOwner`.
#   --branch      (CLI, optional): default: the current git branch (read-only
#                 `git rev-parse --abbrev-ref HEAD`).
#   --head-sha    (CLI, optional): default: the current git HEAD
#                 (`git rev-parse HEAD`). Used to find the run the current
#                 tree actually corresponds to; if no run matches, the most
#                 recent run on the branch is used instead (reported as such,
#                 never silently).
#   --gh-limit    (CLI, optional, default 20): how many recent runs `gh run
#                 list` fetches to search for a HEAD match -- scoped to the
#                 ci.yml workflow only (CI_WORKFLOW_FILE, see
#                 fetch_recent_runs()'s own note) so a build-installers/
#                 regenerate-constraints run never outranks a real CI run.
#   --classify-only (CLI flag): print the classification and STOP. Never runs
#                 the local fallback and never dispatches. This is the
#                 read-only inspection mode this script's default behaviour
#                 with respect to GitHub always is (see OUTPUTS) -- the flag
#                 additionally suppresses the *local* fallback run too, so it
#                 is safe to call repeatedly for a status check alone.
#   --dispatch    (CLI flag): the ONLY way this script ever triggers a real
#                 GitHub Actions run. Opt-in, outward-facing, never implied by
#                 any other flag. Only takes effect when classification is
#                 HEALTHY; requires --dispatch-target for CLARITY, not because
#                 quality-gate/integration lack a manual-dispatch path.
#                 REWRITTEN 2026-09-01 (CI lean-push split, AGT-09): the
#                 2026-08-02 note this replaced explained a `target` input on
#                 ci.yml's own shared `workflow_dispatch` -- that analysis was
#                 CORRECT THEN and is OBSOLETE NOW, because the mechanism it
#                 described no longer exists. As of this change,
#                 `build-installers` and `regenerate-constraints` each moved
#                 out of ci.yml into their OWN workflow file
#                 (.github/workflows/build-installers.yml,
#                 .github/workflows/regenerate-constraints.yml), each with a
#                 bare `workflow_dispatch:` trigger and NO input at all -- the
#                 job-level `if:` guard both used to carry is gone too, because
#                 each file's own trigger already scopes its one job. ci.yml
#                 itself now holds only `setup`, `quality-gate` and
#                 `integration`; none of the three carries a job-level `if:`
#                 either, so a plain `gh workflow run ci.yml` always runs all
#                 three. --dispatch-target therefore now selects WHICH WORKFLOW
#                 FILE to dispatch, not which of two jobs additionally runs
#                 alongside ci.yml's always-on jobs:
#                 `--dispatch-target build-installers` dispatches
#                 build-installers.yml; `--dispatch-target
#                 regenerate-constraints` dispatches
#                 regenerate-constraints.yml; neither call passes any `-f`
#                 input (neither file has one to accept) and neither touches
#                 ci.yml at all. --dispatch-target stays required here so this
#                 script never guesses which of the three workflow files the
#                 caller meant.
#   --local       (CLI flag): force the local fallback to run even when
#                 classification is HEALTHY (e.g. to sanity-check locally
#                 without spending hosted minutes). Fallback already runs
#                 automatically for BLOCKED_AT_JOB_START / NO_RUNS / UNKNOWN --
#                 this flag only matters for the HEALTHY case.
#   --only/--skip (CLI, repeatable): forwarded verbatim to the
#                 `run_ci_locally.py` invocation this script makes for the
#                 Windows leg, to filter which steps of the `quality-gate`
#                 job actually execute.
# OUTPUTS:
#   stdout: the classification (status + evidence + which run/job it came
#     from), then, when the fallback runs, a live stream per leg and a final
#     per-leg summary table (ran-pass / ran-fail / blocked / uncoverable, on
#     what, with which evidence class) plus the ADR-0045 supervision reminder:
#     A LOCAL PASS IS NEVER "CI PASSED".
# EXIT CODES:
#   0  every leg that actually ran passed, AND at least one leg ran.
#   1  at least one leg that ran FAILED.
#   2  BLOCKED before any leg could even be attempted: no `gh`/no git/parse
#      error/classification could not be determined, OR (in --dispatch mode)
#      the dispatch itself could not be issued, OR the only coverable leg
#      (Windows) was itself BLOCKED (e.g. this invocation is not on a
#      Windows host).
#   3  NO SIGNAL: nothing executed at all (e.g. classification came back
#      HEALTHY with neither --dispatch nor --local given, so nothing was
#      attempted on purpose, or every leg reported this run was UNCOVERABLE).
#   A run whose only "covered" legs were BLOCKED and/or UNCOVERABLE must NOT
#   exit 0 -- see overall_exit().
# PRECONDITIONS: run from (or given paths pointing at) a checkout of this
#   repository; `gh` authenticated for the classification step (read-only
#   calls only: `gh run list`, `gh run view`, `gh api .../annotations` --
#   this script NEVER calls a git/gh WRITE operation except the one explicit,
#   opt-in `gh workflow run` inside do_dispatch()).
# DETERMINISM NOTE: NOT deterministic -- see run_ci_locally.py's own note,
#   which applies identically to the Windows leg this script drives. The
#   classification step additionally depends on GitHub's current billing/
#   dispatch state, which can change between two invocations seconds apart.
#
# HONESTY, STATED PLAINLY (do not weaken this in a future edit):
#   The Windows leg and the classification logic are verified on a Windows
#   11 Home host (ADR-0045). Linux and macOS have NO local fallback
#   mechanism on this host, or on any host: a prior version of this script
#   carried a Linux-container leg (Docker/Podman + a bind-mounted
#   `.ci/Dockerfile`, plus an apt-list drift guard) that was authored and
#   never once built or run in any session. It was removed by explicit user
#   decision on 2026-08-02, once CI moved to a self-hosted Windows runner and
#   the never-exercised container path stopped being worth maintaining. Say
#   so plainly: Linux is UNCOVERABLE here now, the same category macOS has
#   always been in -- not "blocked, needs a runtime" -- because there is
#   deliberately no local mechanism for it any more, not a missing one
#   waiting to be installed.
#
# CRITICAL DESIGN CONSTRAINT (inherited from ADR-0045, ci-author skill): this
# script contains NO hand-written list of pytest/flake8/mypy/etc invocations.
# The Windows leg delegates to `scripts/run_ci_locally.py --job
# quality-gate`, which is the ONE place that parses ci.yml and runs its
# `run:` blocks. Duplicating that parsing here would recreate the exact "two
# independent authorships of the same intent" defect class ADR-0045 was
# written to close.
#
# ## Principles Applied
# Inherited: P1 (the blocked-dispatch signature is the one measured this
#   session, not invented; Linux/macOS are stated UNCOVERABLE rather than
#   assumed coverable or silently dropped), P6, P9 (one job: route to Actions
#   or to the honest local fallback), P10 (four distinct exit codes so
#   "nothing ran" and "everything attempted passed" can never be confused),
#   P11.
# Custom: read-only by default with respect to GitHub (C1: dispatching is an
#   irreversible, outward-facing action and stays behind an explicit flag,
#   never inferred).
#
# SOURCES: this session's `gh run list` / `gh api .../check-runs/.../
#   annotations` output against run 30567099577 (HEAD a3f42de0a042a0ae2ef3a77e
#   0c90ebb5aa0bffdd on `main`) -- the exact billing annotation text and the
#   3-5s / zero-`steps` job shape quoted in BILLING_BLOCK_ANNOTATION_SUBSTRING
#   and BLOCKED_MAX_JOB_ELAPSED_S below were read from that run directly, not
#   copied from a report; docs/adr/0045-local-ci-execution-strategy.md;
#   design-docs/research/research-local-ci-github-docker.md (E2: `gh run
#   list`/REST `GET /repos/{owner}/{repo}/actions/runs` is the correct,
#   official mechanism for this); scripts/run_ci_locally.py (reused, not
#   duplicated). The Linux-container leg this file once carried (and the
#   `.ci/Dockerfile` + `scripts/check_ci_docker_drift.py` it depended on) was
#   removed by user decision 2026-08-02; the removal's own report records
#   what was deleted and why. docs/adr/0046-ci-router-actions-first-local-
#   fallback.md's amendment trail is owned/amended elsewhere, not by this
#   edit.
# =============================================================================
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_CI_LOCALLY = REPO_ROOT / "scripts" / "run_ci_locally.py"

#: --dispatch-target value -> the workflow FILE it dispatches (CI
#: lean-push split, 2026-09-01, AGT-09): `build-installers` and
#: `regenerate-constraints` each moved out of ci.yml into their own file,
#: each with a bare `workflow_dispatch:` trigger and no input -- do_dispatch()
#: below issues a plain `gh workflow run <file>` per target, with no
#: `-f target=...` (that input no longer exists anywhere).
DISPATCH_TARGET_WORKFLOWS = {
    "build-installers": "build-installers.yml",
    "regenerate-constraints": "regenerate-constraints.yml",
}

SUPERVISION_BANNER = (
    "=" * 78
    + "\n"
    + '  A LOCAL RUN IS NEVER "CI PASSED" (ADR-0045\'s supervision rule).\n'
    + '  Say "local run passed" and name the leg + evidence class -- never\n'
    + '  "CI passed" or "CI green" on the basis of anything this script ran.\n'
    + "=" * 78
)


class RouterError(Exception):
    """Classification/dispatch could not proceed (gh/git failure, bad JSON, ...)."""


# --------------------------------------------------------------------------
# Classification: is GitHub Actions dispatch actually able to execute a job?
# --------------------------------------------------------------------------

#: Verbatim (case-sensitive-enough) substring of the billing-block annotation
#: GitHub attaches to a job it never started. CONFIRMED THIS SESSION, exact
#: text, via `gh api repos/JuanGSanchez/PixelArt-Creator/check-runs/
#: 90954249751/annotations` against run 30567099577 (the `quality-gate
#: (ubuntu-latest)` job, HEAD a3f42de0...):
#:   "The job was not started because recent account payments have failed or
#:    your spending limit needs to be increased. Please check the 'Billing &
#:    plans' section in your settings"
#: A shortened, still-unambiguous substring is matched (not the whole
#: sentence) so a minor GitHub wording tweak upstream (e.g. punctuation)
#: does not silently break detection.
BILLING_BLOCK_ANNOTATION_SUBSTRING = (
    "job was not started because recent account payments have failed"
)

#: A job GitHub never started completes in single-digit seconds -- MEASURED
#: this session: the four failed jobs of run 30567099577 each ran 3-5s
#: (startedAt/completedAt from `gh run view --json jobs`, elapsed computed
#: below) with an EMPTY `steps` list. ADR-0045 separately recorded a wider
#: 3-29s range across the whole affected run history -- that is a per-RUN
#: range spanning several jobs with staggered start times, not a per-JOB
#: elapsed time, so it is not contradicted by the tighter per-job threshold
#: used here. This threshold is intentionally generous relative to the 3-5s
#: actually measured, and still far below any real job's runtime (minutes).
BLOCKED_MAX_JOB_ELAPSED_S = 10.0

#: A job that genuinely started (whether it then passed or failed on its own
#: merits) takes meaningfully longer than a same-second billing rejection.
#: This is a HEURISTIC FLOOR, not a measured constant -- picked with
#: headroom above BLOCKED_MAX_JOB_ELAPSED_S, and documented as a heuristic
#: rather than dressed up as precise.
HEALTHY_MIN_JOB_ELAPSED_S = 30.0


@dataclass
class JobObservation:
    name: str
    conclusion: Optional[str]
    elapsed_seconds: Optional[float]
    steps_count: Optional[int]
    annotations: List[str] = field(default_factory=list)

    def _annotation_hit(self) -> bool:
        return any(BILLING_BLOCK_ANNOTATION_SUBSTRING in a for a in self.annotations)

    def _never_started_shape(self) -> bool:
        """The "sub-10s zero-step" shape: BOTH fast AND zero recorded steps.
        Either alone (see looks_weakly_blocked) is weaker evidence -- a job
        can legitimately be fast with a step or two skipped by an `if:`, and
        `steps_count` can be `None`/unreliable if the API shape ever changes.
        """
        fast = (
            self.elapsed_seconds is not None
            and self.elapsed_seconds < BLOCKED_MAX_JOB_ELAPSED_S
        )
        zero_steps = self.steps_count == 0
        return fast and zero_steps

    def looks_blocked(self) -> bool:
        """Strong signature: the billing annotation AND the sub-10s zero-step
        shape, together, on a `failure` job. This is the ONLY combination
        this module treats as confirmed BLOCKED_AT_JOB_START evidence for a
        single job."""
        return (
            self.conclusion == "failure"
            and self._annotation_hit()
            and self._never_started_shape()
        )

    def looks_weakly_blocked(self) -> bool:
        """Exactly one of {annotation, never-started shape} present, not
        both -- weaker evidence, contributes to UNKNOWN, never to
        BLOCKED_AT_JOB_START on its own."""
        if self.conclusion != "failure":
            return False
        hit = self._annotation_hit()
        shape = self._never_started_shape()
        return hit != shape

    def looks_healthy(self) -> bool:
        return (
            self.elapsed_seconds is not None
            and self.elapsed_seconds >= HEALTHY_MIN_JOB_ELAPSED_S
        )


def classify_dispatch(jobs: List[JobObservation]) -> Tuple[str, str]:
    """Classify Actions dispatch health from one run's job observations.

    Returns ``(status, reason)`` with ``status`` in {"HEALTHY",
    "BLOCKED_AT_JOB_START", "UNKNOWN"}. ("NO_RUNS" is decided one level up in
    `classify_current_state`, when there is no run to look at in the first
    place -- this function always has at least attempted to classify a real
    run's jobs.)
    """
    actionable = [j for j in jobs if j.conclusion not in (None, "skipped", "cancelled")]
    if not actionable:
        return (
            "UNKNOWN",
            "every job in the run was skipped/cancelled/still pending -- no "
            "evidence either way",
        )

    blocked = [j for j in actionable if j.looks_blocked()]
    healthy = [j for j in actionable if j.looks_healthy()]
    weak = [j for j in actionable if j.looks_weakly_blocked()]

    if blocked and not healthy:
        names = ", ".join(j.name for j in blocked)
        return (
            "BLOCKED_AT_JOB_START",
            f"{len(blocked)} job(s) show the full blocked signature (billing "
            f"annotation AND < {BLOCKED_MAX_JOB_ELAPSED_S:.0f}s zero-step "
            f"failure): {names}",
        )
    if healthy and not blocked:
        names = ", ".join(j.name for j in healthy)
        return (
            "HEALTHY",
            f"{len(healthy)} job(s) ran for a real duration "
            f"(>= {HEALTHY_MIN_JOB_ELAPSED_S:.0f}s): {names}",
        )
    if blocked and healthy:
        return (
            "UNKNOWN",
            f"contradictory signals in the same run: {len(blocked)} job(s) "
            f"look blocked and {len(healthy)} job(s) look healthy -- not "
            "classifying either way",
        )
    if weak:
        names = ", ".join(j.name for j in weak)
        return (
            "UNKNOWN",
            f"{len(weak)} job(s) show only ONE of the two blocked signals "
            f"(annotation XOR sub-{BLOCKED_MAX_JOB_ELAPSED_S:.0f}s/zero-step), "
            f"which is weaker evidence than both together: {names}",
        )
    return "UNKNOWN", "no job matched a blocked, healthy, or weakly-blocked pattern"


def _elapsed_seconds(job: Dict[str, Any]) -> Optional[float]:
    started, completed = job.get("startedAt"), job.get("completedAt")
    if not started or not completed:
        return None
    try:
        t0 = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (t1 - t0).total_seconds()


def build_job_observations(
    jobs_raw: List[Dict[str, Any]],
    repo: str,
    fetch_annotations: Callable[[str, Any], List[str]],
) -> List[JobObservation]:
    obs: List[JobObservation] = []
    for j in jobs_raw:
        conclusion = j.get("conclusion")
        steps = j.get("steps")
        steps_count = len(steps) if isinstance(steps, list) else None
        annotations: List[str] = []
        if conclusion == "failure":
            annotations = fetch_annotations(repo, j.get("databaseId"))
        obs.append(
            JobObservation(
                name=str(j.get("name", "<job>")),
                conclusion=conclusion,
                elapsed_seconds=_elapsed_seconds(j),
                steps_count=steps_count,
                annotations=annotations,
            )
        )
    return obs


# --------------------------------------------------------------------------
# gh/git-calling functions (the ONLY place this script talks to GitHub or
# reads the local repo state). All read-only except do_dispatch().
# --------------------------------------------------------------------------
def _run_text(cmd: List[str], cwd: Path = REPO_ROOT) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RouterError(
            f"`{' '.join(cmd)}` failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def resolve_repo() -> str:
    return _run_text(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    ).strip()


def current_head_sha() -> str:
    return _run_text(["git", "rev-parse", "HEAD"]).strip()


def current_branch() -> str:
    return _run_text(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()


#: The CI workflow file `fetch_recent_runs()` scopes to by default (CI
#: lean-push split, 2026-09-01 follow-up, AGT-09): before the split this
#: repository had exactly one workflow file, so an unfiltered `gh run list`
#: could only ever return ci.yml runs. As of the split there are three
#: (ci.yml, build-installers.yml, regenerate-constraints.yml), and
#: build-installers.yml fires on `v*` tags -- release time, exactly when a
#: caller is most likely to ask "is CI healthy?" and exactly when the most
#: recent run on the repo may NOT be a ci.yml run at all. Left unfiltered,
#: classify_current_state() could read a build-installers run's job shape (a
#: single per-OS matrix job, no quality-gate/integration at all) as the CI
#: verdict.
CI_WORKFLOW_FILE = "ci.yml"


def fetch_recent_runs(
    repo: str,
    branch: Optional[str],
    limit: int,
    workflow: Optional[str] = CI_WORKFLOW_FILE,
) -> List[Dict[str, Any]]:
    """List recent workflow runs, scoped to ``workflow`` by default.

    ``workflow`` defaults to :data:`CI_WORKFLOW_FILE` ("ci.yml") because the
    production caller inside `classify_current_state()` is asking a
    CI-health question, and CI health is judged from CI runs, not from an
    unrelated workflow's runs (see the module-level note above). Pass
    ``workflow=None`` explicitly for the (currently unused) case of wanting
    every workflow's runs unfiltered, or a different file name to scope to a
    DIFFERENT workflow -- `do_dispatch()` below does exactly that for its
    post-dispatch run-URL lookup, scoping to whichever file it just
    dispatched rather than inheriting this default.
    """
    cmd = [
        "gh",
        "run",
        "list",
        "--repo",
        repo,
        "--limit",
        str(limit),
        "--json",
        "databaseId,event,headBranch,headSha,status,conclusion,createdAt,"
        "updatedAt,displayTitle",
    ]
    if branch:
        cmd += ["--branch", branch]
    if workflow:
        cmd += ["--workflow", workflow]
    try:
        return json.loads(_run_text(cmd))
    except json.JSONDecodeError as exc:
        raise RouterError(f"gh run list returned unparsable JSON: {exc}") from exc


def fetch_run_jobs(repo: str, run_id: Any) -> List[Dict[str, Any]]:
    try:
        data = json.loads(
            _run_text(
                ["gh", "run", "view", str(run_id), "--repo", repo, "--json", "jobs"]
            )
        )
    except json.JSONDecodeError as exc:
        raise RouterError(f"gh run view returned unparsable JSON: {exc}") from exc
    return data.get("jobs", [])


def fetch_job_annotations(repo: str, job_id: Any) -> List[str]:
    """Non-fatal on failure: a broken annotation fetch weakens the evidence
    (falls through to `looks_weakly_blocked`/UNKNOWN) rather than aborting
    the whole classification."""
    if job_id is None:
        return []
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}/check-runs/{job_id}/annotations"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return [str(a.get("message", "")) for a in data if isinstance(a, dict)]


def classify_current_state(
    repo: str,
    branch: Optional[str],
    head_sha: Optional[str],
    limit: int,
    *,
    fetch_runs: Optional[
        Callable[[str, Optional[str], int], List[Dict[str, Any]]]
    ] = None,
    fetch_jobs: Optional[Callable[[str, Any], List[Dict[str, Any]]]] = None,
    fetch_annotations: Optional[Callable[[str, Any], List[str]]] = None,
) -> Tuple[str, Optional[Dict[str, Any]], str, List[JobObservation]]:
    """Top-level classification. Injectable fetch_* callables let tests
    supply canned data with ZERO network access; production callers get the
    real `gh`-calling functions by default."""
    fetch_runs = fetch_runs or fetch_recent_runs
    fetch_jobs = fetch_jobs or fetch_run_jobs
    fetch_annotations = fetch_annotations or fetch_job_annotations

    runs = fetch_runs(repo, branch, limit)
    if not runs:
        return (
            "NO_RUNS",
            None,
            "no workflow runs found" + (f" on branch {branch!r}" if branch else ""),
            [],
        )

    chosen: Optional[Dict[str, Any]] = None
    match_kind = ""
    if head_sha:
        for r in runs:
            if r.get("headSha") == head_sha:
                chosen, match_kind = r, "exact HEAD sha match"
                break
    if chosen is None:
        chosen = runs[0]  # `gh run list` returns newest first
        match_kind = "latest run on branch (no exact HEAD match found)"

    if chosen.get("status") != "completed":
        return (
            "UNKNOWN",
            chosen,
            f"{match_kind}; run {chosen.get('databaseId')} status="
            f"{chosen.get('status')!r} (not completed yet)",
            [],
        )

    jobs_raw = fetch_jobs(repo, chosen["databaseId"])
    jobs = build_job_observations(jobs_raw, repo, fetch_annotations)
    status, reason = classify_dispatch(jobs)
    return status, chosen, f"{match_kind}; {reason}", jobs


def print_classification(
    repo: str,
    branch: Optional[str],
    head_sha: Optional[str],
    status: str,
    run_ref: Optional[Dict[str, Any]],
    reason: str,
    jobs: List[JobObservation],
) -> None:
    print("-" * 78)
    print(
        f"run_ci: classification for {repo} (branch={branch!r}, head_sha={head_sha!r})"
    )
    if run_ref is not None:
        print(
            f"  run: {run_ref.get('databaseId')}  event={run_ref.get('event')!r}  "
            f"headSha={run_ref.get('headSha')}  status={run_ref.get('status')!r}"
        )
    print(f"  STATUS: {status}")
    print(f"  reason: {reason}")
    for j in jobs:
        print(
            f"    job {j.name!r}: conclusion={j.conclusion!r} "
            f"elapsed={j.elapsed_seconds!r}s steps={j.steps_count!r} "
            f"annotations={j.annotations!r}"
        )
    print("-" * 78)


# --------------------------------------------------------------------------
# Dispatch (the ONLY irreversible/outward-facing action -- opt-in via
# --dispatch, gated by C1, NEVER exercised automatically).
# --------------------------------------------------------------------------
def do_dispatch(repo: str, args: argparse.Namespace) -> int:
    if not args.dispatch_target:
        print(
            "run_ci: --dispatch requires --dispatch-target "
            "{build-installers,regenerate-constraints}. REWRITTEN 2026-09-01 "
            "(CI lean-push split, AGT-09): each target now names its OWN "
            "workflow file, not a `target` input on a shared "
            "`workflow_dispatch` in ci.yml -- ci.yml itself now holds only "
            "`setup`, `quality-gate` and `integration`, none gated by a "
            "job-level `if:`, so a plain `gh workflow run ci.yml` always runs "
            "all three. `--dispatch-target build-installers` instead "
            "dispatches .github/workflows/build-installers.yml, and "
            "`--dispatch-target regenerate-constraints` dispatches "
            ".github/workflows/regenerate-constraints.yml -- neither of "
            "those two files accepts any workflow_dispatch input any more, "
            "so neither call passes `-f`. --dispatch-target stays required "
            "here so this script never guesses which of the three workflow "
            "files the caller meant.",
            file=sys.stderr,
        )
        return 2
    workflow_file = DISPATCH_TARGET_WORKFLOWS[args.dispatch_target]
    cmd = [
        "gh",
        "workflow",
        "run",
        workflow_file,
        "--repo",
        repo,
    ]
    print(
        "run_ci: DISPATCHING an Actions run -- outward-facing, opt-in action: "
        f"{' '.join(cmd)}"
    )
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"run_ci: dispatch failed: {proc.stderr.strip()}", file=sys.stderr)
        return 2
    time.sleep(2)  # give GitHub a moment to register the new run before we look it up
    try:
        runs = fetch_recent_runs(repo, args.branch, 1, workflow=workflow_file)
    except RouterError as exc:
        print(f"run_ci: dispatched, but could not look up the new run: {exc}")
        return 0
    if runs:
        run_id = runs[0]["databaseId"]
        print(
            f"run_ci: dispatched. Run URL: "
            f"https://github.com/{repo}/actions/runs/{run_id}"
        )
    else:
        print("run_ci: dispatched, but `gh run list` did not yet show a new run.")
    return 0


# --------------------------------------------------------------------------
# The local fallback: Windows natively; Linux and macOS UNCOVERABLE. There
# used to be a Linux-container leg here (Docker/Podman + a bind-mounted
# .ci/Dockerfile); it was never built or run in any session and was removed
# by user decision 2026-08-02 once CI moved to a self-hosted Windows runner.
# Linux now sits in the same UNCOVERABLE category macOS has always been in --
# see linux_leg()/macos_leg() below.
# --------------------------------------------------------------------------
@dataclass
class LegResult:
    leg: str  # "linux" | "windows" | "macos"
    outcome: str  # "RAN-PASS" | "RAN-FAIL" | "BLOCKED" | "UNCOVERABLE"
    detail: str
    evidence_class: str


def _passthrough_filters(args: argparse.Namespace) -> List[str]:
    flags: List[str] = []
    for s in getattr(args, "only", []) or []:
        flags += ["--only", s]
    for s in getattr(args, "skip", []) or []:
        flags += ["--skip", s]
    return flags


def run_windows_leg(args: argparse.Namespace, local_os: str) -> LegResult:
    if local_os != "Windows":
        return LegResult(
            "windows",
            "BLOCKED",
            f"the windows leg needs a native Windows host to run natively; this "
            f"invocation is on {local_os}",
            "n/a",
        )
    cmd = [
        sys.executable,
        str(RUN_CI_LOCALLY),
        "--job",
        "quality-gate",
    ] + _passthrough_filters(args)
    print(f"[run_ci] windows leg (native): {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    rc = proc.returncode
    if rc == 0:
        return LegResult(
            "windows", "RAN-PASS", "run_ci_locally.py exited 0", "local-native"
        )
    if rc == 1:
        return LegResult(
            "windows",
            "RAN-FAIL",
            "run_ci_locally.py exited 1: an executed step failed",
            "local-native",
        )
    if rc == 3:
        return LegResult(
            "windows",
            "BLOCKED",
            "run_ci_locally.py exited 3: nothing executed (every step "
            "skipped/gated) -- no signal from this leg",
            "local-native",
        )
    return LegResult(
        "windows",
        "BLOCKED",
        f"run_ci_locally.py exited {rc}: usage/parse error",
        "local-native",
    )


def linux_leg() -> LegResult:
    """UNCOVERABLE, deliberately, not "blocked, needs a runtime": a prior
    version of this script ran the Linux leg inside a container (Docker or
    Podman, building `.ci/Dockerfile`), but that path was authored, never
    once built or run in any session, and removed by explicit user decision
    on 2026-08-02 once CI moved to a self-hosted Windows runner. There is now
    no local execution mechanism for the Linux leg on ANY host, the same
    category macOS has always been in -- see macos_leg()."""
    return LegResult(
        "linux",
        "UNCOVERABLE",
        "no local execution mechanism exists for the Linux leg on any host "
        "shape. A prior Linux-container leg (Docker/Podman + a bind-mounted "
        ".ci/Dockerfile, plus an apt-list drift guard) was removed by user "
        "decision 2026-08-02 -- it had never been built or run in any "
        "session and CI now runs on a self-hosted Windows runner. Coverage "
        "requires hosted GitHub Actions' own ubuntu-latest runner (once "
        "dispatch is unblocked) or a self-hosted Linux runner; there is "
        "deliberately no local fallback mechanism for it any more.",
        "n/a",
    )


def macos_leg() -> LegResult:
    return LegResult(
        "macos",
        "UNCOVERABLE",
        "macOS cannot be containerized on non-Apple hardware by ANY container "
        "technology, on ANY host OS (an Apple licensing constraint, not a "
        "Docker/Podman limitation -- confirmed by this session's research: no "
        "Docker page claims otherwise, and no competing container tech does "
        "either). No local fallback exists for this leg regardless of what "
        "runs this script. Coverage requires real Apple hardware, a macOS "
        "cloud CI provider, or GitHub's own macos-latest runner once Actions "
        "dispatch is unblocked.",
        "n/a",
    )


def run_fallback(args: argparse.Namespace, local_os: str) -> List[LegResult]:
    return [
        linux_leg(),
        run_windows_leg(args, local_os),
        macos_leg(),
    ]


def overall_exit(legs: List[LegResult]) -> int:
    """0 every leg that ran passed AND >=1 leg ran; 1 a leg that ran failed;
    2 nothing ran but something was BLOCKED; 3 NO SIGNAL (nothing ran and
    nothing was even blocked -- e.g. only UNCOVERABLE legs, or an empty
    list). An all-BLOCKED or all-UNCOVERABLE run must NOT exit 0 -- neither
    path below can reach 0 unless something in `ran` is non-empty."""
    ran = [leg for leg in legs if leg.outcome in ("RAN-PASS", "RAN-FAIL")]
    failed = [leg for leg in ran if leg.outcome == "RAN-FAIL"]
    blocked = [leg for leg in legs if leg.outcome == "BLOCKED"]
    if failed:
        return 1
    if ran:
        return 0
    if blocked:
        return 2
    return 3


def print_summary(legs: List[LegResult]) -> None:
    print("\n" + "-" * 78)
    print("run_ci: LOCAL FALLBACK SUMMARY")
    print("-" * 78)
    for leg in legs:
        print(
            f"  [{leg.outcome:11s}] {leg.leg:8s} "
            f"evidence={leg.evidence_class:22s} {leg.detail}"
        )
    print("-" * 78)
    print(SUPERVISION_BANNER)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=(
            "Try GitHub Actions dispatch first (read-only classification); "
            "fall back to running the same checks locally -- Windows "
            "natively, Linux and macOS UNCOVERABLE -- when Actions cannot "
            "actually execute a run."
        )
    )
    ap.add_argument("--repo", default=None, help="owner/name (default: `gh repo view`)")
    ap.add_argument("--branch", default=None, help="default: current git branch")
    ap.add_argument("--head-sha", default=None, help="default: current git HEAD")
    ap.add_argument("--gh-limit", type=int, default=20)
    ap.add_argument(
        "--classify-only",
        action="store_true",
        help="print the classification and stop -- never runs the fallback, "
        "never dispatches",
    )
    ap.add_argument("--dispatch", action="store_true")
    ap.add_argument(
        "--dispatch-target",
        choices=["build-installers", "regenerate-constraints"],
        default=None,
    )
    ap.add_argument(
        "--local",
        action="store_true",
        help="force the local fallback to run even when classification is HEALTHY",
    )
    ap.add_argument("--only", action="append", default=[], metavar="SUBSTRING")
    ap.add_argument("--skip", action="append", default=[], metavar="SUBSTRING")
    return ap.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    import platform

    args = parse_args(argv)

    try:
        repo = args.repo or resolve_repo()
    except RouterError as exc:
        print(f"run_ci: could not resolve the repository: {exc}", file=sys.stderr)
        return 2

    head_sha = args.head_sha
    if head_sha is None:
        try:
            head_sha = current_head_sha()
        except RouterError:
            head_sha = None  # non-fatal: falls back to "latest run on branch"

    branch = args.branch
    if branch is None:
        try:
            branch = current_branch()
        except RouterError:
            branch = None

    try:
        status, run_ref, reason, jobs = classify_current_state(
            repo, branch, head_sha, args.gh_limit
        )
    except RouterError as exc:
        print(f"run_ci: classification failed: {exc}", file=sys.stderr)
        return 2

    print_classification(repo, branch, head_sha, status, run_ref, reason, jobs)

    if args.classify_only:
        return 0

    if status == "HEALTHY":
        if args.dispatch:
            return do_dispatch(repo, args)
        if not args.local:
            print(
                "run_ci: classification is HEALTHY and neither --dispatch nor "
                "--local was given -- nothing executed on purpose. Pass "
                "--dispatch to hand off to Actions, or --local to also verify "
                "locally."
            )
            return 3  # NO SIGNAL: nothing was attempted, by design

    local_os = {"Linux": "Linux", "Windows": "Windows", "Darwin": "macOS"}.get(
        platform.system(), platform.system()
    )
    legs = run_fallback(args, local_os)
    print_summary(legs)
    return overall_exit(legs)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nrun_ci: interrupted.", file=sys.stderr)
        sys.exit(130)
