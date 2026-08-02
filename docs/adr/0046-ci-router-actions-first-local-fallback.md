# ADR-0046 — CI router: try GitHub Actions dispatch first, fall back to the local runner per-OS

| Field | Value |
| --- | --- |
| Status | **Accepted** (amended 2026-08-02, twice, same day — first: billing block lifted, recurrence expected; second: the container Linux leg removed, never having been built or run; see both Amendments below) |
| Date | 2026-08-02 |
| Amended | 2026-08-02 (same-day, first) — the hosted-runner billing block recorded below as current fact was measured lifting later the same session; supersedes the Context/Decision/Consequences framing that Actions "cannot execute" this project's gates, and re-scopes the router from primary CI path to fallback + recurrence detector. 2026-08-02 (same-day, second) — `main/.ci/Dockerfile`, the `.ci/` directory, `scripts/check_ci_docker_drift.py` and its test module were deleted (never built, never run; CI now runs on a self-hosted Windows runner); the dispatch classifier and the Windows-native local leg survive; the `ubuntu-latest` local-fallback leg is reclassified from `BLOCKED` to `UNCOVERABLE` (macOS's category). |
| Author | AGT-09 (GitHub / DevOps) |
| Feature | CI-execution fallback + local feedback loop (extends ADR-0045) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0045 (`scripts/run_ci_locally.py` — local CI execution strategy, the single-source-of-truth ruling this ADR preserves), `.github/workflows/ci.yml` (ci-author skill, F11), `scripts/coverage_gate.py` / `scripts/path_portability_check.py` (the gates neither script bypasses) |

## Context

### Amendment (2026-08-02, same day) — the billing block lifted; read this before the rest of Context

*Immutable-append. The Context, Decision, and Consequences text below is retained verbatim as the record of
what was true earlier this session — it is not rewritten to look as though the block never happened. This
subsection supersedes the framing that GitHub Actions "cannot execute this project's gates" as a **current**
fact. It was current on 2026-07-30 and had **lifted** by 2026-08-02.*

Run `30567099577` (2026-07-30, cited below and in ADR-0045) shows the billing-blocked signature plainly:
zero steps executed, sub-10-second `failure`, the payment-hold annotation on every failed job. That
observation stands, unedited.

Later the **same day** this ADR was first accepted (2026-08-02), commit
`aa4b6d1e003a46c9b82f22c563aa09854e6473b3` (verified this session via
`git -C main cat-file -e <sha>^{commit}`) was pushed to `main` and triggered run `30749285915`. **All four
real jobs started and executed steps on GitHub-hosted runners** — no billing annotation appeared on any of
them. The run itself completed `failure`, but for an unrelated reason: `integration (ubuntu-latest)` and
both `quality-gate (macos-latest)` / `quality-gate (windows-latest)` legs were `success`; the sole failure,
`quality-gate (ubuntu-latest)`, was a **false positive** in the Ubuntu-only path-portability lint (an
escaped hyphen inside a regex character class read as a Windows path separator), fixed and committed
separately as `d9e7b18` (verified this session to resolve). The two on-demand jobs (`build-installers`,
`regenerate-constraints`) were `skipped` by their own guards, as designed — unchanged from the original
Context.

**Cause of the recovery: the monthly included-minutes window reset**, not a repair of anything broken. This
is load-bearing for how the rest of this ADR must now be read: the block is **expected to recur** when the
window is exhausted again on this account. It was a **state change** (quota exhausted → quota reset →
[expected] quota exhausted again), not a fault that has been fixed once and for all. Every classification
`HEALTHY` / `BLOCKED_AT_JOB_START` / `NO_RUNS` / `UNKNOWN` in the router (Decision, below) therefore keeps
its full value going forward — it is not dead code for a problem that "is over."

**Consequently, the router's role changes from primary CI path to fallback-plus-detector**, and hosted
GitHub Actions — not `run_ci.py` — is the primary way this project runs its checks, because Actions alone
covers the macOS leg, which no local fallback can ever cover (see the per-OS coverage table below,
unchanged). Everywhere the Decision or Consequences sections below describe the router's local fallback as
the *only* available path, read that as true for the 2026-07-30 window and **expected to become true again**
at the next quota exhaustion, not as a standing description of how CI runs today.

### Amendment (2026-08-02, second, same day) — the container Linux leg removed, never having been built or run

*Immutable-append. The Decision, Per-OS coverage table, and Consequences text below describing
`main/.ci/Dockerfile` and `scripts/check_ci_docker_drift.py` as present-but-`BLOCKED` artifacts is
retained verbatim as the record of what was built and what was true earlier this same day. This
subsection supersedes that framing as a **current** description of the repository: those two
artifacts, and the drift-guard's test module, no longer exist.*

By user decision (2026-08-02), the Docker-based Linux CI fallback was removed: `main/.ci/Dockerfile`,
the `main/.ci/` directory that held it, `scripts/check_ci_docker_drift.py` (the apt-list drift guard
described below), and that guard's test module are all deleted. **None of the three was ever built or
run in any session** — this is not a removal of something that failed; it is the removal of an
authored-but-untried approach, made unnecessary now that CI executes on a self-hosted Windows runner
(see the first Amendment above on the router's fallback/detector role). Nothing here should be read as
"the container approach failed" — it was never tried.

What survives from this ADR's router, and why:

- **The dispatch classifier** (`HEALTHY` / `BLOCKED_AT_JOB_START` / `NO_RUNS` / `UNKNOWN`, described in
  Decision below) is unchanged and kept deliberately: it regains value the moment this repository goes
  public and resumes consuming metered hosted minutes, at which point the billing-block signature this
  ADR documents can recur.
- **The Windows-native local leg** is unchanged: it still delegates to ADR-0045's
  `scripts/run_ci_locally.py --job quality-gate`, per the "ADR-0045 is preserved and extended" ruling
  below, which this removal does not touch.
- **The container-runtime detection, the bind-mount invocation into `main/.ci/Dockerfile`, and the "no
  runtime found" `BLOCKED` result are gone**, along with the Dockerfile and the drift guard themselves.
- **The `ubuntu-latest` local-fallback leg moves category: from `BLOCKED` (meaning "needs a container
  runtime this host doesn't have yet") to `UNCOVERABLE`** — the same category the `macos-latest` leg
  already occupied in the Per-OS coverage table below — because no local mechanism for it exists any
  more, not merely an uninstalled one. The coverage table's `ubuntu-latest` row, printed further down
  as "container — requires a container runtime not installed yet," is stale in exactly this way: read it
  as history, not as the router's present classification.
- **The exit-code contract is unchanged and was re-proven after the removal**: `0` at least one leg ran
  and every attempted leg passed; `1` a leg that ran failed; `2` `BLOCKED`; `3` NO SIGNAL. An
  uncoverable-only run still exits `3`, never `0` — verified against the router as it stands post-removal,
  not assumed to still hold from before the change.
- **Verification obtained by the agent that made this removal** (recorded here, not independently
  re-verified in this documentation pass, and not claimed as more than what is listed): the
  `tests/deploy/` suite went from 30 passed before the removal to 20 passed after, with the delta fully
  accounted for by the deleted drift-guard test module; a full-suite collect-only run reported 5676 tests
  with zero import errors; `flake8`/`black`/`isort`/`mypy` were clean on the changed files; and the
  classifier still returns a real classification when run against the live repository.

### The blocked signature is narrower than ADR-0045 recorded

ADR-0045 established that GitHub Actions on this account has not executed a
job in over three weeks, evidenced by short-duration `failure` runs carrying
a billing annotation. This session re-measured that signature with more
precision than "workflow dispatch is blocked": **run creation is not
blocked — job START on billed hosted runners is.** Against the live
repository, run `30567099577` (2026-07-30, `main`, HEAD
`a3f42de0a042a0ae2ef3a77e0c90ebb5aa0bffdd` — confirmed this session to
resolve via `git -C main cat-file -e <sha>^{commit}`) shows all six jobs
created normally; four reached `conclusion: failure` in 3–5 seconds with
**zero steps executed**, and two were `skipped` by their own conditional
guards. Every failed job carries the same annotation, verbatim:

> "The job was not started because recent account payments have failed or
> your spending limit needs to be increased. Please check the 'Billing &
> plans' section in your settings"

The distinguishing signature is therefore: a run exists → a job's
`conclusion` is `failure` → its elapsed time is under roughly 10 seconds →
it recorded zero steps → it carries that annotation. A run with a genuinely
executed job (any duration ≥ ~30s) is not blocked in this sense, whatever its
pass/fail outcome. Because two of the two host constants noted below are
permanent, and one is measured-but-uninstalled, this signature has to be
classified programmatically at every invocation rather than assumed to still
hold from a prior session.

### Host constraints, measured this session

No Docker and no Podman are on `PATH`. **WSL is not installed** (`wsl
--status` reports the subsystem absent). The host is **Windows 11 Home**, so
Hyper-V and Windows containers are unavailable **permanently** — this is an
edition constraint, not a pending-install gap the way Docker/WSL are. The
`gh` CLI is authenticated with scopes `gist, read:org, repo, workflow` —
**no `user` scope**, so the GitHub billing REST API is unreachable from this
host; detection of the blocked state must be attempt-and-observe against
`gh run list` / `gh run view` / `gh api .../annotations`, never a direct
billing-state query.

### Decision

Add a routing layer, `scripts/run_ci.py`, that classifies GitHub Actions
dispatch health from the signature above into `HEALTHY` /
`BLOCKED_AT_JOB_START` / `NO_RUNS` / `UNKNOWN`, and routes to local execution
whenever it is not `HEALTHY`. The router is read-only with respect to GitHub
by default; the only outward-facing, irreversible action it can take —
`gh workflow run` — sits behind an explicit `--dispatch` flag, never implied
by any other flag, and was not exercised in the session that built it. Three
artifacts were built, all already implemented and present on disk:

- `main/scripts/run_ci.py` — the router described above, whose local
  fallback runs the Linux leg in a container, the Windows leg natively, and
  reports the macOS leg as permanently uncoverable. **(Amended 2026-08-02 —
  see the Amendment at the top of Context: this router is a fallback plus an
  automatic recurrence detector for the billing-block signature, not this
  project's primary way of running its checks. Hosted GitHub Actions is the
  primary path and is the only path that covers the macOS leg at all.)**
- `main/.ci/Dockerfile` — the Linux CI image. Its apt package list is copied
  verbatim from `ci.yml`'s own "Install Qt runtime OS libraries (Ubuntu)"
  step and sets `QT_QPA_PLATFORM=offscreen`; project source is **bind-mounted
  at run time**, never baked into the image, so the container always tests
  the real, current working tree. **(Amended 2026-08-02, second — this file
  and the `main/.ci/` directory holding it were deleted the same day, never
  having been built or run; see the second Amendment above.)**
- `main/scripts/check_ci_docker_drift.py` — a guard that parses both
  `ci.yml`'s Qt-libraries step and the Dockerfile's `apt-get install` block
  and fails closed (exit 1) the moment the two package lists disagree. It is
  wired into `run_ci.py`'s Linux-leg build path (a stale image is refused
  rather than silently built) but is **not** wired into `ci.yml` itself —
  recorded below as a known gap, not an oversight. **(Amended 2026-08-02,
  second — this script and its test module were deleted the same day, never
  having been run in any session; see the second Amendment above.)**

### ADR-0045 is preserved and extended, not overturned

ADR-0045 ruled that the CI workflow file (`ci.yml`) stays the single source
of truth for what the checks are, and built `scripts/run_ci_locally.py` to
parse and execute `ci.yml`'s `run:` blocks directly rather than maintain a
second, hand-written command list. This ADR's router does not duplicate any
check command: both the Windows leg and the Linux-container leg of
`run_ci.py`'s fallback **delegate to `run_ci_locally.py --job quality-gate`**
— the router only decides *whether* and *where* to invoke it (Actions,
Windows-native, or Linux-container), never re-implementing *what* it invokes.
ADR-0045's supervision rule — that a local execution is never "CI passed" —
is inherited unchanged and reprinted by the router itself: every invocation
prints an unmissable banner, both before and after execution, stating "A
LOCAL RUN IS NEVER 'CI PASSED'" and naming the ADR-0045 supervision rule
explicitly.

### Per-OS coverage — a stated, permanent limitation, not a TODO

| Leg | Local fallback |
| --- | --- |
| `ubuntu-latest` | container — requires a container runtime not installed yet (Docker or Podman; neither present on this host) |
| `windows-latest` | natively on the host — works today |
| `macos-latest` | **none, ever.** macOS cannot be containerised on non-Apple hardware, on any host OS, by any container technology. This is an Apple licensing constraint, not a Docker/Podman limitation. |

A full-matrix green result is therefore **unobtainable locally**, regardless
of what runtime is eventually installed, because of the macOS leg alone.
**(Amended 2026-08-02 — this row is unchanged and un-softened: run
`30749285915` measured hosted Actions covering all three OS legs including
macOS, which is exactly the coverage this local table says can never be
reproduced locally. That is the reason Actions, not this router, is the
primary CI path — see the Amendment at the top of Context.)**

**(Amended 2026-08-02, second — the table's `ubuntu-latest` row above is now
history, not current classification. The container fallback it describes was
removed the same day, never having been built or run; the local fallback for
`ubuntu-latest` is reclassified `UNCOVERABLE`, joining `macos-latest` in that
category, rather than `BLOCKED` pending a runtime install. See the second
Amendment at the top of Context for the full account.)**

## Alternatives Considered

- **`nektos/act`.** A third-party CLI that parses `.github/workflows/*.yml`
  and executes its steps as Docker containers entirely locally, without
  contacting the GitHub Actions dispatch service — genuinely unaffected by
  the billing block. Not chosen as the primary mechanism because `act`'s own
  maintainers document it as an *approximation* of hosted-runner behaviour,
  not parity with it; it remains a valid fallback if the router's Linux image
  proves too heavy to hand-maintain, and is recorded as such, but the router
  built here is the primary path.
- **Hosted runners with a `container:` key.** Changes the *environment a job
  runs in* once GitHub has started it; it does not change *whether GitHub
  starts the job* at all. A job dispatched by the billing-blocked account
  still fails at start regardless of any `container:` key in its definition
  — this alternative does not address the measured failure mode and was
  rejected on that basis alone.
- **Self-hosted runners.** Self-hosted-runner compute is documented as free
  and unmetered, which is attractive under a billing hold — but GitHub's own
  Secure Use Reference states self-hosted runners "should almost never be
  used for public repositories on GitHub, because any user can open pull
  requests against the repository and compromise the environment," and this
  repository is intended to become public. Recorded here as a **time-limited
  bridge that must be removed before publication**, not as a durable part of
  this decision. Separately, whether an account already blocked for failed
  payment still permits *dispatching* a job to an already-registered
  self-hosted runner — as distinct from the runner's minutes being unbilled —
  is **not stated by any official GitHub source found this session**; this is
  an inference gap, not a confirmed fact in either direction. A probe of this
  question (register a runner, attempt a dispatch, observe) has been set up,
  but **its outcome is not yet known and is not recorded here as a result.**
  **(Amendment, 2026-08-02 — the question lost its test conditions, not
  answered.** A self-hosted runner, `pixelart-local-probe` (Windows x64), was
  registered against this repository on 2026-08-02. No job was ever
  dispatched to it while the billing hold was active — the hold lifted (quota
  reset; see the Amendment at the top of Context) before the probe could be
  exercised against a blocked account. Whether a payment hold blocks
  self-hosted dispatch therefore **remains unanswered, and is now untestable
  on this account** until the block recurs at the next quota exhaustion. This
  is recorded as an open question whose test window closed, **not** as a
  negative or positive result in either direction. Separately, and tracked
  under a different record (not this ADR): the user has since directed that
  the `windows-latest` leg be moved onto `pixelart-local-probe` to avoid
  re-exhausting the metered included-minutes window, because self-hosted
  minutes are unbilled; that migration is in progress, and it carries the
  same removal-before-publication obligation already recorded above for any
  self-hosted bridge use — reprinted, not newly created, by this amendment.
  No REQ-ID is cited for that migration record because none has been found
  for it this session; one is not fabricated here.)**
- **Making the repository public.** GitHub documents GitHub Actions as free
  for standard hosted runners on public repositories, which is plausibly a
  complete fix for the measured billing block. Not adopted as part of this
  decision because publication is gated behind a review that has not
  happened; recorded here as an **open path**, not a decision this ADR makes.

## Consequences

**Positive.**

- The Windows leg was executed end-to-end this session and genuinely passed:
  `run_ci_locally.py --job quality-gate` under the router's Windows-native
  path ran **5673 tests, exit 0** (`5673 passed, 44 warnings in 147.88s`,
  plus the project-install step, both real subprocess runs, not summarised
  from memory). This is the first time this suite has run through a
  CI-shaped path (dispatch classification → routed execution → pass/fail
  verdict) since the account's billing block began.
- The reuse discipline from ADR-0045 is extended, not just repeated: the
  router adds *where to run* without adding a second *what to run* — the only
  authored description of the checks remains `ci.yml`, parsed by
  `run_ci_locally.py`.
- The drift guard makes the Dockerfile/workflow apt-list agreement
  self-enforcing rather than a comment nobody re-verifies, and it fails
  closed (blocks the image build) rather than silently shipping a stale
  image.

**Negative / accepted cost.**

- **The Linux container leg has never been built or run.** It is
  code-complete and derived correctly from `ci.yml` (drift-guard-verified),
  but this session's host has no Docker, no Podman, and no WSL2, so nothing
  exercised it. The router reports this leg as `BLOCKED`, never as a pass —
  this is stated plainly here and must not be softened in any later
  reference to this work. **(Amended 2026-08-02, second — this bullet is
  retained verbatim as history. The Linux container leg was removed the same
  day, still never having been built or run in any session; it is no longer
  `BLOCKED`, it is `UNCOVERABLE` — see the second Amendment at the top of
  Context.)**
- A full-matrix green result is unobtainable locally, permanently, because of
  the macOS leg (see the coverage table above) — no future local tooling
  change closes that gap.
- A local pass remains evidence of a structurally weaker kind than a real
  GitHub Actions run and must never be recorded or cited as "CI passed."
  ADR-0045's supervision rule is inherited here, not restated as new: the
  router enforces it at the tool level with the printed banner described
  above.
- The drift guard runs from the router's Linux leg but is **not** wired into
  the CI workflow itself — a known, reported gap, not an oversight. Wiring it
  in would require editing `ci.yml`, out of scope for the work this ADR
  records.
- `ci.yml`'s `workflow_dispatch` trigger exposes only two on-demand jobs
  (`build-installers`, `regenerate-constraints`); the `quality-gate`/
  `integration` jobs the router classifies have **no manual-dispatch path**
  in the committed workflow at all. `--dispatch` reports this gap rather than
  inventing a workaround for it.

**Amendment (2026-08-02) — the Positive/Negative consequences above described a CI-unavailable world; that
world is not the current one.** *Immutable-append. The Positive and Negative bullets above are retained
verbatim as the record of what was true when the router was built and this ADR first accepted. This
amendment restates them against the measured 2026-08-02 state and must be read alongside them, not in
place of them.*

- Every Positive/Negative bullet above that reads as though the router's Windows-native local run is *the*
  way this project currently gets a passing signal is superseded: run `30749285915` (2026-08-02, same
  session) shows hosted GitHub Actions executing and passing `integration (ubuntu-latest)`,
  `quality-gate (macos-latest)`, and `quality-gate (windows-latest)` directly, with only an unrelated
  Ubuntu-lint false positive (fixed as `d9e7b18`) breaking a full-green result. The 5673-test Windows-native
  pass recorded above (147.88 s) remains true and is not retracted — it is simply no longer the *only*
  green signal available, now that Actions itself runs.
- **The Linux container leg is unchanged: it has never been built or run.** This amendment does not soften
  that — no container runtime is installed on this host today, hosted Actions' own `ubuntu-latest` leg is a
  distinct execution path from `main/.ci/Dockerfile`, and the local container leg's `BLOCKED` status is
  exactly as unverified now as when this ADR was first accepted. **(Amended 2026-08-02, second, later the
  same day — `main/.ci/Dockerfile` and the drift guard were deleted, still never having been built or run;
  the leg's local-fallback status changed from `BLOCKED` to `UNCOVERABLE`, the same category `macos-latest`
  already occupied. See the second Amendment at the top of Context.)**
- **The router's ongoing value is as a fallback plus an automatic detector for a recurrence of the
  billing-block signature described in Context**, not as a superseded artifact to be retired. Because the
  cause of the 2026-08-02 recovery was a **monthly included-minutes window reset** rather than a fix, the
  same signature (run created, job `failure` in <10s, zero steps, the payment-hold annotation) is **expected
  to recur** when the window is next exhausted. The router's `HEALTHY` / `BLOCKED_AT_JOB_START` / `NO_RUNS`
  / `UNKNOWN` classification and its Windows-native + Linux-container fallback paths keep their designed
  purpose for that recurrence; only their *primacy* changes, from "the only way to get a signal" to "the
  fallback for when Actions is quota-blocked again."
- **Hosted GitHub Actions is the primary CI path** as of this amendment, precisely because it is the only
  path that covers `macos-latest` — see the per-OS coverage table above, unchanged, and the Alternatives
  amendment on self-hosted runners.

**Exit-code contract (normative).** `0` — at least one leg ran and every
attempted leg passed; `1` — a leg that ran failed; `2` — nothing ran but
something was `BLOCKED` before any leg could be attempted; `3` — NO SIGNAL,
nothing executed at all (every leg `BLOCKED` and/or `UNCOVERABLE`, or
classification came back `HEALTHY` with neither `--dispatch` nor `--local`
given). A run whose only legs were blocked or uncoverable must not exit `0`.
**(Amended 2026-08-02, second — this contract is unchanged by the container-leg
removal and was re-proven afterward: an uncoverable-only run (Linux now
`UNCOVERABLE` alongside macOS) still exits `3`, never `0`. See the second
Amendment at the top of Context.)**

**Obligations created (tracked here, not discharged by this ADR).**

1. Resolve the self-hosted-runner billing-dispatch question (whether a
   payment-hold account still permits dispatch to an already-registered
   self-hosted runner) via the probe already set up, and record the actual
   outcome once observed — not assumed from either direction. Owner: AGT-09,
   on a future dispatch; no REQ-ID exists for this yet (none of the affected
   area's existing ADRs — ADR-0045, ADR-0043 — cite one for this specific
   obligation, and none is fabricated here per this project's sourcing
   discipline). **(Amended 2026-08-02 — this obligation is now stalled, not
   discharged: the billing hold lifted (quota reset) before `probe` could be
   exercised against a blocked account, so the question is untestable on this
   account until the block recurs. The obligation stands unchanged and is
   re-owed at the next quota exhaustion; see the Alternatives-section
   amendment above for the full account.)**
2. If a self-hosted runner is ever used as the bridge alternative, remove it
   before this repository is made public, per GitHub's own Secure Use
   Reference caution quoted above.
3. Decide, separately, whether to make the repository public (which would
   plausibly remove the billing block entirely for hosted runners) — gated on
   a review that has not happened; not decided by this ADR.
4. Install a container runtime (Docker or Podman) on a project host and
   actually build/run `.ci/Dockerfile` at least once, so the Linux leg's
   `BLOCKED` status can be replaced with a real, observed pass or fail rather
   than remaining permanently unverified. **(Superseded 2026-08-02, second,
   same day — by user decision, `main/.ci/Dockerfile` was deleted, never
   having been built or run, now that CI runs on a self-hosted Windows
   runner. This obligation is discharged by removal, not by completion: there
   is no longer a Dockerfile to build or run. See the second Amendment at the
   top of Context.)**
5. Wire `scripts/check_ci_docker_drift.py` into `.github/workflows/ci.yml`
   itself, if and when editing that workflow is in scope for a future task —
   not done here. **(Superseded 2026-08-02, second, same day — the script and
   its test module were deleted the same day this obligation was recorded,
   never having been wired into `ci.yml` or exercised in any session. This
   obligation is discharged by removal, not by completion. See the second
   Amendment at the top of Context.)**
