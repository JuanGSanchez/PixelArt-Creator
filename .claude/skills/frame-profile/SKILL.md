---
name: frame-profile
description: >
  Frame-budget profiling skill for the PixelArt Creator platform. Use it (invoked
  by AGT-10 Rendering & Performance) to run and interpret the perf_profile script,
  which measures per-frame render time for a given canvas/zoom scenario headless
  and compares it to FRAME_BUDGET_MS (16 ms / 60 fps, S12). It turns the script's
  pass/over-budget/error exit codes into a profiling report + a directive request
  to AGT-05 (F4/F7).
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity (workflow required)
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P9 — Role Separation (declares OUT-OF-SCOPE)
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
    # P5 inherits AGT-10's context discipline; P10 inherits AGT-10's exit status.
  custom:
    - id: C1
      name: Measurement, not bit-reproducibility
      requires: Frame timings are host-sensitive; P2 applies to the SCENARIO definition + the pass/fail rule (vs FRAME_BUDGET_MS), not to a bit-identical millisecond output.
      rationale: Inventory §5 (perf_profile CP1); P2 applied to the decision rule.
---

SKILL: frame-profile
================================================================================

PURPOSE:
  Quantify render performance for defined scenarios and judge each against the
  frame budget, so AGT-10 issues grounded optimization directives instead of
  guessing where the cost is.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given a scenario spec it runs perf_profile + interprets the exit code unaided.

INPUTS:
  - The scenario (canvas size, zoom level, dirty region, viewport) to profile.
  - FRAME_BUDGET_MS + related constants (logic/constants.py, S12).

OUTPUTS:
  - A profiling report: measured frame time vs FRAME_BUDGET_MS per scenario,
    pass/over-budget verdict, and (on over-budget) a specific hotspot + a directive
    request for render-strategy → AGT-05.

PRECONDITIONS:
  - scripts/perf_profile.py exists; PySide6 present for the headless render; a
    scenario is defined.

PROCEDURE:
  1. Define the scenario deterministically (canvas/zoom/dirty-rect) — the fixed
     input that makes the pass/fail rule reproducible (C1).
  2. Run `python scripts/perf_profile.py` for the scenario; read the exit code:
     0 within budget → pass; 1 over budget → hotspot; 2 error (e.g. PySide6 absent) → BLOCKED.
  3. On over-budget, identify the dominant cost (tile repaint count, item count,
     viewport type) and record it.
  4. Emit the report; on over-budget, hand a directive request to render-strategy
     (AGT-10) which produces the directive AGT-05 implements.

DECISION POINTS:
  - Decision FP-D1:
    Condition: perf_profile exits 2 (PySide6 absent / environment error).
    Branch A: BLOCKED — report the environment gap; do not fabricate a timing.
    Default: A.
  - Decision FP-D2:
    Condition: a scenario passes locally but the target hardware differs.
    Branch A: record the host + treat the verdict as host-relative (C1); re-profile
      on the reference environment before asserting a global pass.
    Default: A.

ERROR HANDLING:
  - Error FP-E1: over-budget with no clear hotspot → widen the scenario set
    (vary zoom/dirty-rect) to localise the cost.
  - Error FP-E2: perf_profile missing → BLOCKED; request the Metaprompter build it.

DEPENDENCIES:
  - scripts/perf_profile.py (AGT-10, Dossier §6.5); logic/constants.py budget.
  - Feeds render-strategy (AGT-10) → AGT-05. Fallback: block if the script/PySide6 absent.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/perf_profile.py).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Authoring the optimization directive → render-strategy (AGT-10).
  - Implementing the fix in ui/ → AGT-05 (canvas-view). Functional tests → AGT-06.
  - Writing the perf_profile script → AGT-09/Metaprompter (this skill runs it).

SOURCES:
  - User requirements: Dossier §1 (S12 FRAME_BUDGET_MS/FPS_TARGET), §2 (F4, F7),
    §6.1 (AGT-10), §6.2 (frame-profile), §8 (perf_profile owner).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), programmatic-determinism.md.
