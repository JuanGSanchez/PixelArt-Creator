# ADR-0045 — Local CI execution strategy: derive-and-run over self-hosted / containerized

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-30 |
| Author | AGT-09 (GitHub / DevOps) |
| Feature | CI-execution fallback + local feedback loop |
| Supersedes | — |
| Superseded by | — |
| Relates to | `.github/workflows/ci.yml` (ci-author skill, F11), ADR-0043 (`tests/deploy/` integration job), `scripts/coverage_gate.py` / `scripts/path_portability_check.py` (the gates this strategy must not bypass) |

## Context

### The gate that has never gated

GitHub Actions on this account (`JuanGSanchez/PixelArt-Creator`) is currently blocked at the
account level. This was **verified this session**, not assumed, by two independent checks:

1. `gh run list --limit 30` over the visible run history shows every run since
   **2026-07-07T19:19:14Z** (run `28892331597`, the first short-duration failure after a run of
   genuine 15–17-minute passes/failures earlier that day) through the most recent run today
   (**2026-07-30T16:47:23Z**, run `30563047346`) completing in **3–29 seconds** with conclusion
   `failure`. That is not a workflow failure shape — a real quality-gate run takes 16–48 minutes
   (the job's own `timeout-minutes: 75` comment records ~46–48 min for the full offscreen-Qt
   suite); a run that fails in single-digit seconds never reached its first step.
2. `gh api .../check-runs/<id>/annotations` on two of those runs — one from the start of the
   window (`85775429882`, 2026-07-08) and one from today (`90940672348`, 2026-07-30) — returns the
   **identical, verbatim** annotation on both:

   > "The job was not started because recent account payments have failed or your spending limit
   > needs to be increased. Please check the 'Billing & plans' section in your settings"

   Every job in every affected run — `quality-gate` (all three OS legs), `integration`,
   `regenerate-constraints`, and (where triggered) `build-installers` — carries this same
   annotation, with zero `steps` recorded in the run's job list. The workflow was never entered;
   no command in it has executed on GitHub's infrastructure in over three weeks.

The consequence is structural, not cosmetic. `ci.yml` layers the coverage gate over both roots
(`--cov=pixelart_creator` and the separate `sync_backend`/`web_viewer` measurement), the docs and
docstring gates (`mkdocs build --strict`, the time-boxed `pydocstyle` exception), `flake8`/`mypy`/
`black`/`isort`, the nine perf-ceiling gates, and the `tests/deploy/` + `tests/backend/`
integration suite (ADR-0043). Every one of these is **correctly authored** — grounded, gated,
thresholded per the constitution — but **none of them has executed as a control** in over three
weeks. The workflow file is presently a specification of intent that GitHub's billing state
prevents from ever being checked. A red build and a build that was never attempted look identical
in the repository's history (`conclusion: failure` either way); only the annotation and the
duration distinguish them, and nothing short of reading both currently does.

### The user's decision

CI must be runnable **locally** — both as a fallback for whenever Actions billing is exhausted,
and as a way to get real feedback on a change without spending hosted minutes at all, billing
state aside. The user specifically raised: **reuse the existing workflow definition** rather than
maintain a second, hand-written description of the same checks.

That constraint is not a style preference; it targets a defect class this project already paid
for once. `ci.yml`'s own comment on the `check_layering.py` step records that the `--root .`
invocation "was previously MISSING even though the comment here claimed it dispatched everything,
so `sync_backend/` and `web_viewer/` had ZERO layering enforcement" — a hand-maintained claim
(the comment) drifted from the hand-maintained reality (the command), and CI stayed green through
the gap because nothing forced the two to agree. A hand-copied local script listing "the same
commands" is exactly that shape: two independent authorships of the same intent, with nothing
compiling one from the other. It will diverge, silently, the next time someone edits one and
forgets the other — and a local gate that has silently drifted from the real one is **worse** than
having no local gate, because it manufactures false confidence at the exact moment the team is
leaning on it hardest (i.e. while Actions is unavailable).

### Three approaches considered

**Approach 1 — self-hosted runner.** The officially supported route. A self-hosted runner
registered against this repository executes `ci.yml` unmodified, through GitHub's own runner
agent, so there is no parsing/derivation step and no drift risk at all — this is the real
workflow, on real infrastructure, just not GitHub's hosted compute. Self-hosted runners are not
metered against Actions minutes, which is exactly why this is attractive under a billing block:
minutes exhaustion or a failed card should not need to stop a self-hosted leg.

*What is verified:* none of this account's mechanics around self-hosted runners specifically.
*What is NOT verified, and must not be asserted either way:* **whether an account already blocked
for failed payment still permits registering and running jobs on a self-hosted runner, as
distinct from an account that has merely hit a spending limit.** GitHub's documented billing
model treats "payment failed" and "spending limit reached" as different account states, and it is
plausible — but not confirmed from this machine, which has no billing-portal access and no way to
register a runner without first deciding to do so — that a failed-payment block suspends the
*account's* ability to consume any Actions capacity, self-hosted included, while a spending-limit
block only stops metered *hosted* minutes. This is recorded here as the **open question it is**:
it must be **tested** (register a runner, dispatch a run, observe whether it is accepted or
rejected with the same billing annotation) rather than assumed in either direction.

Independent of that open question, self-hosted has a second, unconditional limit worth recording
now: a runner registered on this machine (Windows 11) covers only the **Windows** leg of the
3-OS `quality-gate` matrix. The Linux-only static/lint/coverage/docs/perf gates, the `integration`
job (Docker + Nginx, Ubuntu-only), and the Linux leg of `regenerate-constraints` all need a Linux
host; the macOS leg needs a Mac. One self-hosted Windows runner does not close those gaps — it
would need a self-hosted Linux box and a self-hosted Mac beside it to match the matrix, which is
infrastructure this project does not have today.

**Approach 2 — run the workflow locally in containers** (e.g. `act`, or a hand-rolled Docker
runner-image emulation). Like the self-hosted route, this executes the *actual* workflow file —
no separate parser, no derivation, no drift risk — and it can additionally emulate the Linux
runner image on any host that has Docker, which self-hosted-on-this-machine cannot. It is
confirmed unavailable here: **Docker is not installed on this machine** (`docker --version` →
`command not found`), and neither is the WSL2 backend most Windows Docker installs depend on
(`wsl --status` → "El Subsistema de Windows para Linux no está instalado"). Even where Docker is
present, this route only ever reaches the **Linux-container** legs — Windows and macOS runner
images are not containers Docker can run on any host, so `windows-latest`/`macos-latest` legs and
the native-installer `build-installers` matrix's non-Linux legs stay out of reach regardless.

**Approach 3 — a local runner script that DERIVES its steps from the workflow file.** Works today
with **no infrastructure and no billing dependency**: no runner registration, no Docker, no WSL.
It cannot execute the *real* GitHub Actions engine — it is an approximation, always — but it can
be built so that approximation is **honest by construction**: it parses `ci.yml` itself and runs
the selected job's `run:` blocks in order, so there is exactly one authored description of "what
the gate checks" (the workflow) and zero hand-maintained copies of it to drift.

## Decision

**Approach 3 is built now, todayto give the fallback and local-feedback capability the user
asked for without waiting on the open self-hosted question or on installing Docker/WSL.**
Approaches 1 and 2 are not rejected — they remain the more faithful options and are recorded
below as follow-on work, gated on real answers the project does not have yet (the self-hosted
billing question; a Docker/WSL install decision this ADR does not make). Building the script does
not preclude adding either later; the three approaches are complementary in principle (a local
script for cheap fast feedback, a self-hosted runner or `act` for close-to-real confidence, hosted
Actions for the actual CI signal once billing is resolved) rather than mutually exclusive.

### Why Approach 3 is built the way it is (the critical design constraint)

The script (`scripts/run_ci_locally.py`) **parses `ci.yml` with PyYAML and executes the `run:`
blocks of the selected job, in the order they appear in the file.** It does not contain a
hand-written list of pytest/flake8/mypy/coverage invocations anywhere. This is the direct
countermeasure to the defect class described in Context: because the script's only source of
"what to run" is the workflow file itself, the two can never independently drift — there is
nothing to keep in sync, because there is only one authored copy. When `ci.yml` gains a step, the
next local run picks it up with no script edit; when a step's command changes, so does the local
run's command, by construction, not by someone remembering to also touch a second file.

This shapes what the script can and cannot promise, and the shape is deliberate:

- **Steps that are a shell `run:` block execute for real**, in this environment, with this
  machine's tools.
- **Steps that use a marketplace or setup action (`uses:`) cannot be executed locally** — there is
  no local equivalent of GitHub's action-invocation machinery, and fabricating one (e.g. faking
  what `actions/checkout` does) would be exactly the kind of invented behaviour this project's
  sourcing discipline (P1) forbids. Each such step is mapped to an honest local substitute where
  one exists (`actions/setup-python` → print the locally active interpreter version instead of
  installing the pinned one; `actions/setup-node` → print the locally available Node version;
  `actions/checkout` → no-op, the script already runs against the local working tree;
  `actions/upload-artifact` → no-op, the produced file is left on disk and its path is printed)
  or is **skipped with a stated reason** when no honest substitute exists. Every skip is reported
  in the run summary — never silent — because a silently-skipped step is the same false-confidence
  failure mode as a hand-copied command list, just wearing a different disguise.
- **`if:` conditions are evaluated**, not ignored, against a small, explicit simulated context
  (`runner.os` from the real local OS; `matrix.os` auto-selected to the one leg that matches the
  local OS, since a Windows machine cannot truthfully claim to be running the `ubuntu-latest` leg;
  `env.*`/`secrets.*` resolved from real local environment variables of the same name, defaulting
  to empty exactly as an absent GitHub secret would; `github.event_name`/`github.ref`/`inputs.*`
  from CLI flags). Getting this right matters as much as running the commands: most of this
  workflow's static/lint/docs/coverage/perf steps are `if: runner.os == 'Linux'`-gated, so a local
  run on this Windows machine correctly executes only a fraction of the `quality-gate` job — and
  the script says so loudly rather than quietly running nothing and calling it done.
- **Shell handling is explicit, not assumed.** `ci.yml` sets `defaults: run: shell: bash` on every
  job precisely so the one pytest invocation with `\` continuations behaves identically on all
  three hosted OSes; this machine's default shell is PowerShell, but a POSIX `bash` **is**
  available here (Git for Windows ships one, confirmed at
  `C:\Program Files\Git\usr\bin\bash.exe`, resolvable as plain `bash` on `PATH`), so the script
  invokes each `run:` block through that `bash`, matching the workflow's own shell choice instead
  of silently reinterpreting the block under PowerShell semantics (which would change quoting,
  `$VAR` expansion, and multi-line continuation behaviour, and would then be simulating a workflow
  ci.yml never asked for).
- **A failing executed step stops the run there**, mirroring GitHub Actions' own default (no
  `continue-on-error` is set anywhere in this workflow) — the script does not keep charging ahead
  past a failed step and then report a misleadingly partial "pass".
- **The run ends with a clear per-step summary** (ran-and-passed / ran-and-failed / skipped, each
  with its reason) and a **non-zero exit if any executed step failed**, and a **distinct non-zero
  exit if literally nothing executed** (e.g. every step was OS-gated away on this leg) — a local
  run that skipped everything and exited 0 would be the quietest and most dangerous failure mode
  of all: a green result that checked nothing.

### The supervision rule (normative)

**A local execution of `scripts/run_ci_locally.py` is never "CI passed."** It is evidence of a
different, and structurally weaker, kind: the same commands the workflow defines, run in a
different environment, with incomplete step coverage (only the OS-gated steps matching the local
machine; every `uses:`-based step skipped or approximated), on a single OS leg, without GitHub's
own runner image, without the concurrency guard, and without a durable, shareable, third-party
record of the result. Concretely, and without exception:

- No commit message, PR description, issue, status report, or agent `EXIT_STATUS` block may say
  "CI passed", "CI green", or equivalent, on the basis of a local run. It must say **"local run
  passed"** (or the equivalent phrase this ADR's implementers choose), naming the job and OS leg
  that ran, so a later reader cannot mistake it for the hosted signal.
- A local pass does **not** authorize merging past a required-status-check gate that names the
  real `ci` workflow, and does not substitute for AGT-06 QA sign-off predicated on CI.
  Branch-protection status checks, where configured, must keep pointing at the real GitHub Actions
  job names — this local script is not registered as a status check and must not be made to look
  like one.
- The script enforces its own half of this rule at the tool level: every invocation prints an
  unmissable banner, both before and after execution, stating in plain words that this is a local
  run and not a CI run, and the summary explicitly names which steps did **not** run and why, so
  the incompleteness travels with the result rather than being left to the reader's memory.
- This rule binds every agent and every human in this project equally. It is recorded here, in an
  ADR, rather than only in the script's help text, because the failure mode it guards against —
  quietly treating a weaker signal as the strong one — is a governance failure, not a UX
  nicety, and belongs in the same durable record as the threshold-integrity rules the rest of the
  pipeline already answers to.

## Consequences

**Positive.**

- The project has a working CI-shaped feedback loop the moment this ADR lands, independent of
  GitHub's billing state, with zero new infrastructure and zero new billing exposure.
- The reuse constraint is met structurally, not by convention: `ci.yml` stays the **only** place
  the checks are described. A future edit to a `run:` block, a new step, or a reordered gate is
  picked up by the local script automatically, closing off the exact "comment says X, code does Y"
  drift class the layering-check history already demonstrated is real on this project.
- The self-hosted and container options are not foreclosed. Both remain available as strictly
  *more* faithful upgrades once their respective blockers (the billing-state question; a Docker/
  WSL install decision) are resolved, and neither requires undoing the script built here.

**Negative / accepted cost.**

- The local script is, and will remain, an **approximation**. It cannot execute a `uses:` step,
  cannot reproduce GitHub's runner image or its pre-installed toolchain versions exactly, and on
  this machine can only ever exercise the Windows leg of the OS matrix — the Linux-only gates
  (lint, mypy, both coverage measurements, the docs/docstring gates, all nine perf ceilings, and
  the `tests/deploy`/`tests/backend` integration job) do not run locally here at all. This is
  reported, not hidden, but it is a real and durable capability gap, not a rounding error: a local
  "all green" on this machine says nothing about roughly two-thirds of the checks this project's
  own quality bar depends on.
- `actions/setup-python` and `actions/setup-node` cannot install the pinned toolchain versions
  locally; the script can only report what is already on `PATH` and flag a mismatch, so a passing
  local step under a mismatched interpreter/Node version is weaker evidence than the same step in
  CI, and the script's own summary must keep saying so every time.
- The open self-hosted-runner billing question is **not answered by shipping this script** — it
  remains open, and Approach 1 stays unavailable as a stronger fallback until someone actually
  tests it and records the result.

**Obligations created (tracked here, not discharged by this ADR).**

1. Test whether a self-hosted runner is accepted on this billing-blocked account (Approach 1's
   open question) and record the answer — do not assume either outcome. Owner: AGT-09, on a future
   dispatch; no REQ-ID exists for this yet.
2. If/when Docker + WSL2 (or an equivalent) is installed on a project machine, re-evaluate
   Approach 2 (`act` or similar) as a closer-to-real local option for the Linux-container legs;
   this ADR does not decide to install that infrastructure.
3. `scripts/run_ci_locally.py`'s local-equivalent mappings for `uses:` steps are a fixed,
   hand-maintained table (`actions/checkout`, `actions/setup-python`, `actions/setup-node`,
   `actions/upload-artifact`, plus a generic "no mapping known" fallback for anything else). A new
   action type added to `ci.yml` in the future will fall through to the generic skip until someone
   extends that table — which is itself reported (not silent), but is a known, load-bearing seam
   worth naming so a future reader does not mistake the generic fallback for a deliberate
   evaluation of that specific action.
