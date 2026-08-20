# ADR-0060 — Ceiling gates take the minimum; `perf_profile.py`'s directive-measurement role keeps the median

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | Decided and recorded 2026-08-20 |
| Author | AGT-10 (Rendering & Performance) — ruling requested directly, via the orchestrator, as the owner of `scripts/perf_profile.py` and of the two fixed test modules; not routed through AGT-01 because the question is self-referential to AGT-10's own measurement instrument and its two derivative CI gates |
| Feature | Cross-cutting: `tests/ui/test_composite_region_perf.py` (T-18), `tests/ui/test_aids_perf.py` (T-26), `scripts/perf_profile.py` |
| Grounded by | REQ-P4-UI-015, REQ-P9-UI-011 (the two named ceilings); `scripts/perf_profile.py`'s own CP1 note ("median <= budget" declared FIXED); `.claude/skills/frame-profile/templates/profile-report.md` ("Report the MEDIAN of several runs, not the best"); `.github/workflows/ci.yml` `quality-gate` job matrix (lines 215-297) and its 13 `perf_profile.py` CI steps (lines 944-1102) |
| Owed by | This is the ruling itself — no implementation task is owed by this ADR (Decision, below) |
| Relates to | `design-docs/deviations-decision-batch-20260816.md` DEV-21 (the three over-ceiling CI failures under measured runner contention); the fix already merged in PR #23 (`tests/ui/test_composite_region_perf.py`, `tests/ui/test_aids_perf.py` — warm-up + minimum-of-N) |

## Context

PR #23 fixed two CI perf-ceiling tests that had failed three times in two cycles —
`test_t18_region_recomposite_holds_the_named_ceiling` (T-18, +5.2% and +19.5% over
`COMPOSITE_REGION_CEILING_MS`) and `test_t26_iso_overlay_paint_holds_the_named_overlay_ceiling`
(T-26, +5.7% over `OVERLAY_FRAME_CEILING_MS`) — every failure re-running GREEN on the identical
commit once the shared self-hosted runner was quiet (DEV-21). The fix replaced a single cold
sample / a median-of-3 with **warm-up + minimum-of-N**, proved empirically (in that PR) to still
fail under an injected artificial slowdown and pass without one. Neither ceiling constant moved.

That fix created a visible divergence: the two tests now assert `min(samples) < ceiling`, while
`scripts/perf_profile.py` — the instrument AGT-10 owns for frame-budget profiling — still asserts
`median <= budget` for every one of its modes, and its own module docstring declares that rule
**FIXED** (CP1: "the pass/fail rule (median <= budget) is fixed... perf profiling is inherently
host-sensitive; P2 applies to the scenario + decision rule"). One physical property — an
operation's render/composite time — is now decided two different ways in one repository. The
question raised at the end of that PR, and the one this ADR answers, is whether that divergence is
correct or a defect.

**The evidence that settles it is infrastructural, not philosophical, and it was not visible from
inside the two test files alone.** `perf_profile.py` is wired directly into CI —
`.github/workflows/ci.yml`'s `quality-gate` job runs 13 dedicated `perf_profile.py` invocations
(the 8K paint/redraw gate, the composite region-recomposite gate FU-15, two tilemap gates, six
overlay gates, the realtime apply-remote gate, the full-frame flatten gate, and the
viewport-recomposite commit gate) — a much larger surface than `perf_profile.py`'s own header
comment discloses ("the `--composite` gate runs in CI" — true, but it undersells the other
twelve). **Every one of those 13 steps carries `if: runner.os == 'Linux'`** (verified: 13 `run:`
lines, 13 matching `if:` guards, one-to-one). The `quality-gate` job's matrix currently runs
**exactly one active leg** — `os: windows-selfhosted`, `runs_on: [self-hosted, Windows, X64]` — the
single shared machine DEV-21's contention came from; the `ubuntu-latest` and `macos-latest` legs
are explicitly commented out ("DISABLED... ZERO hosted minutes while this is in effect").
`runner.os` for the self-hosted Windows leg is `'Windows'`, never `'Linux'`.

**The consequence: all 13 `perf_profile.py` CI steps are currently dead — they do not execute at
all** under the active matrix. The pytest suite that hosts T-18 and T-26, by contrast, runs with no
OS guard (`Tests (pytest, headless, parallel, with coverage XML)`, line 796) — unconditionally, on
the one contended self-hosted leg, every push. That is a structural, not incidental, difference:
T-18/T-26 are the ONLY perf-ceiling checks that currently run at all, and they run on the ONE
machine local work competes with. `perf_profile.py`'s own CI role runs on nothing right now, and
was designed (`if: runner.os == 'Linux'`) to run on a **hosted, single-tenant, ephemeral**
`ubuntu-latest` runner when the disabled leg is restored (the file's own "PUBLIC-REPO HAZARD"
comment says that restoration is required before the repository goes public) — a runner class that
never shares a physical machine with anyone's local work, and therefore was never exposed to the
contention pattern DEV-21 documents.

This is a materially different picture from the one visible at the end of PR #23, where the honest
default assumption was that `perf_profile.py`'s CI-wired steps share the contended self-hosted
runner just as T-18/T-26 do. They do not, by explicit configuration, and currently do not run at
all.

## Decision

**Ruling (a): the divergence is correct and stands. `perf_profile.py`'s pass/fail rule (`median <=
budget`) is NOT changed.** T-18 and T-26 keep minimum-of-N (already merged, unchanged by this
ADR). No implementation task is created by this ruling.

The reasoning is narrower and firmer than option (a)'s framing in the dispatch ("a developer tool
invoked deliberately, usually on a quiet machine") suggested, because the actual mechanism is not
usage convention but CI wiring:

1. **The two instruments do not compete for the same machine, and that is enforced by
   `if: runner.os == 'Linux'`, not by anyone's discipline about when to run a script by hand.**
   T-18/T-26 run unconditionally on `windows-selfhosted` — the one machine DEV-21's contention came
   from. `perf_profile.py`'s 13 CI steps require `Linux`, which the active matrix never provides;
   when that leg existed/returns, it is `ubuntu-latest` — hosted, ephemeral, never shared with local
   work. The premise the dispatch asked me to weigh ("perf_profile is invoked deliberately, usually
   on a quiet machine") is TRUE for `perf_profile.py`'s CI role specifically because that role
   cannot currently execute at all, and was designed to execute somewhere DEV-21's contention could
   not reach even when it does.

2. **A blind, unscoped switch to minimum-of-N would break a use of `perf_profile.py` this ADR must
   not touch: AGT-10's own directive-measurement role.** `.claude/skills/frame-profile/templates/
   profile-report.md` states explicitly: "Report the MEDIAN of several runs, not the best. The
   best run is the one the machine was least busy for, and shipping against it means shipping
   against a condition users will not have." That is the correct statistic for a DIFFERENT
   question than T-18/T-26 ask. A ceiling gate asks "is this catastrophically broken" — contention
   only ever adds latency, so the minimum is the best estimate of the uncontended floor, and a
   genuine regression raises that floor too (proved in PR #23). A frame-budget DIRECTIVE asks "will
   a real user's interactive session feel slow" — and a regression that makes an operation stutter
   or GC-pause MORE OFTEN, without moving its best-case floor, is exactly the kind of regression a
   render-pipeline directive exists to catch, and a minimum-of-N statistic is structurally blind to
   it. Swapping `perf_profile.py`'s reported verdict to minimum would not just diverge from a
   template's wording — it would let AGT-10 silently fail to recommend a directive for a real,
   user-facing rendering regression that a median/p95 measurement would have caught. That risk is
   the actual blast radius of ruling (b), and it is a correctness cost to the render-pipeline
   process, not merely an inconvenience.

3. **What (else) would break under (b), stated concretely, per the dispatch's instruction to weigh
   this honestly:**
   - `AGT-10`'s own agent brief encodes the literal condition "perf_profile exits 0 (median <=
     FRAME_BUDGET_MS)" (Decision A10-D2). Changing the underlying statistic without updating that
     text would make the agent's own governing document describe a rule the script no longer
     implements.
   - Every past profiling report (`design-docs/reports/subagent-report-agt-10-*`,
     `design-docs/specs/phase-1-ui-canvas/render-strategy.md`, `design-docs/reports/
     perf-two-tier-model-20260816.md`, `phase12-baseline.md`, `phase12-sliceB-directive.md`, and
     others) quotes median/p95 numbers and a median-based verdict. A silent statistic change makes
     a future re-run of the same scenario not comparable to its own history without every reader
     first checking which rule produced which number — precisely the "one physical property
     measured two ways... quoted across the two without anyone noticing" risk the dispatch warned
     against, reproduced in the other direction.
   - `--full-frame --content dense` is *deliberately not gated* (REQ-P12-LOGIC-001) and is reported
     for the record on median/p95; a minimum there would misrepresent a knowingly-accepted
     off-thread cold cost as better than it typically is.

4. **The dead-steps finding is reported, not fixed here.** All 13 `perf_profile.py` CI steps are
   currently unreachable under the active `windows-selfhosted`-only matrix — a real gap (the 8K
   paint/redraw, compositor, tilemap, overlay x6, realtime-apply, full-frame-flatten and
   viewport-recomposite gates are not presently exercised by CI at all) but it is CI-wiring
   (`.github/workflows/ci.yml`), which is AGT-09's surface, not AGT-10's, and this ADR's write
   target is `main/docs/adr` only. It is recorded here because it is load-bearing to the ruling: it
   is *why* there is currently zero live exposure to contention for `perf_profile.py`'s CI role, not
   a reason to distrust the ruling. **The condition that would flip this ruling** is stated in
   Consequences, below.

## The "FIXED" declaration

**Not overridden.** `perf_profile.py`'s CP1 note is left exactly as written; nothing in this ADR
changes the script, and the rule it declares fixed remains correct for the reason CP1 gives
(reproducibility of the decision rule against a fixed, deterministic scenario) AND for the
additional, now-confirmed reason CP1 does not itself state: the runner class its CI role actually
executes on (hosted `ubuntu-latest`, when the disabled leg returns) was never exposed to the
shared-machine contention that forced T-18/T-26 to change.

**The declaration should be amended to EXPLAIN the divergence, not to change the rule.** A future
reader who diffs `tests/ui/test_composite_region_perf.py`/`test_aids_perf.py` against
`perf_profile.py` and finds `min` in one place and `median` in the other, with no cross-reference,
will reasonably suspect one of them is a mistake — this ADR exists precisely so that suspicion has
a documented, evidence-backed answer instead of a rediscovery. Recommended follow-up (not this
ADR's write target, not undertaken here): add one sentence to `perf_profile.py`'s CP1 note pointing
at this ADR, and confirm in a small future pass that the two test files' own module docstrings
(already merged in PR #23, which frame the divergence as "quiet machine, deliberate" vs "unattended,
shared runner") still read consistently with this ADR's sharper, infrastructural framing — they are
not contradicted by it, but this ADR is the more precise record and should be the one a future
reader is pointed to.

## Alternatives considered

| Alternative | Why it was not chosen |
| --- | --- |
| **(b) unscoped — switch `perf_profile.py`'s pass/fail rule to minimum-of-N everywhere** | Breaks the `frame-profile` skill's explicit, reasoned "not the best run" methodology; risks a false-negative render-pipeline directive for a regression that raises frequency/tail latency without moving the best-case floor; invalidates the literal wording of AGT-10's own Decision A10-D2; makes every historical median-based profiling report non-comparable to a future re-run without a reader first learning which rule produced which number. |
| **(b) scoped — add a minimum-of-N verdict only for `perf_profile.py`'s CI-invoked runs, keep median for AGT-10's manual runs** | Considered seriously; rejected because the CI-invoked runs currently do not execute at all (dead `if: runner.os == 'Linux'` steps against an active Windows-only matrix) and, when they do, target hosted non-shared infrastructure — so there is no live contention exposure to defend against today. Solving a problem that is not occurring, for a script this ADR was not asked to implement changes to, is not warranted; the trigger for revisiting this is named below. |
| **Leave the divergence unexplained (do nothing)** | Rejected outright — this is the exact "invisible folklore" risk the dispatch named. A ruling with no record would leave the next reader to rediscover the CI-wiring evidence from scratch, or worse, "fix" the discrepancy by guessing. |

## Consequences

**Accepted costs.** `perf_profile.py` and its two derivative test files remain visibly different in
one respect (median vs minimum) with no code-level cross-reference between them until the
recommended CP1-note amendment lands as a small separate documentation pass. Until then, the only
record of *why* is this ADR.

**What this enables.** Both instruments now use the statistic that matches the question each
actually answers: T-18/T-26 answer "is this catastrophically regressed, filtered from a shared
machine's noise" (minimum, proved to still catch a real regression); `perf_profile.py`, in its
AGT-10-directed profiling role, answers "will a real interactive session feel slow" (median + p95,
matching the `frame-profile` skill's own stated design). Neither answer is corrupted by the other's
statistic.

**What it constrains — and the condition that reopens this ruling.** If `perf_profile.py`'s CI
steps are ever moved onto the self-hosted `windows-selfhosted` leg (their `if: runner.os ==
'Linux'` guard removed or widened, or the leg's OS/label changed), OR if the disabled
`ubuntu-latest` leg is restored as a genuinely shared/contended host rather than a dedicated GitHub-
hosted VM, the infrastructural premise this ruling rests on no longer holds, and the minimum-of-N
question for `perf_profile.py`'s CI-invoked pass/fail rule must be re-asked on fresh evidence — not
assumed settled by this ADR. This ADR's ruling is conditioned on the CI wiring recorded in Context,
not on the general shape of the script.

## Compliance

No code was changed by this ADR (write target is `main/docs/adr` only, per the dispatch). No
detector applies to a ruling with no implementation. The infrastructural claims above were verified
directly against `.github/workflows/ci.yml` in this worktree, not summarised from memory:

```
$ awk 'NR>=930 && NR<=1135' .github/workflows/ci.yml | grep -c "run: python scripts/perf_profile.py"
13
$ awk 'NR>=930 && NR<=1135' .github/workflows/ci.yml | grep -c "if: runner.os == 'Linux'"
13
$ grep -n "quality-gate:|runs-on:|matrix:" .github/workflows/ci.yml
  -> quality-gate: runs-on: ${{ matrix.runs_on }}; matrix.include has exactly
     one ACTIVE entry, os: windows-selfhosted, runs_on: [self-hosted, Windows, X64];
     the ubuntu-latest and macos-latest entries are commented out.
$ grep -n "name: Tests (pytest" -A 15 .github/workflows/ci.yml
  -> no `if:` guard on the pytest step; runs on whichever leg is active
     (currently windows-selfhosted, unconditionally).
```

## What this record does not verify

- **That the dead-steps finding (Context, point 4) is itself correct GitHub Actions semantics.**
  It follows directly from `runner.os` documentation (the runner's actual OS, not the matrix `os`
  label) and from reading the matrix as committed; it was not confirmed by triggering an actual CI
  run and observing a skipped-step marker in the Actions UI. If that reading is wrong, this ADR's
  central evidence changes and the ruling must be revisited.
- **That no consumer of `perf_profile.py`'s JSON output outside this repository's own `.claude/`
  skills and `.github/workflows/ci.yml` exists.** The search was repository-wide (`.claude`,
  `main/.github`, `main/docs`, `design-docs`) but not exhaustive of anything outside this
  container's two repositories.
- **That the `frame-profile` skill's template is followed in every past profiling report.** Its
  stated methodology was read and quoted; individual past reports were not each re-audited for
  compliance with it.
