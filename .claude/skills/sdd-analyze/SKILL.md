---
name: sdd-analyze
description: >
  SDD "analyze" phase for the PixelArt Creator platform — the gate before implement.
  Use it (invoked by AGT-01) to run a cross-artifact consistency and coverage check
  across constitution.md, spec.md, plan.md, and tasks.md, producing an analysis
  report. No implement dispatch is allowed until analyze passes with zero
  unresolved findings. Gate: refuses to run unless all four artifacts exist.
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
    # P5 inherits AGT-01's; P10 inherits AGT-01's exit status.
  custom:
    - id: C1
      name: Hard implement gate
      requires: A non-empty unresolved-findings list keeps the gate CLOSED; the orchestrator must not dispatch any implement agent until this skill reports zero unresolved findings.
      rationale: spec-driven-development.md §2 (analyze is the gate); Dossier §6.7/§7.
---

SKILL: sdd-analyze
================================================================================

PURPOSE:
  Cross-check constitution.md, spec.md, plan.md, and tasks.md for consistency and
  full coverage; emit an analysis report that opens or holds the implement gate.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES — given
  the four artifacts it produces the analysis report and gate verdict unaided.

INPUTS:
  - constitution.md, spec.md, plan.md, tasks.md (all four). Required.

OUTPUTS:
  - Analysis report: per-artifact findings (drift, gaps, conflicts, uncovered REQ-IDs,
    orphan tasks) + a single gate verdict (PASS / HOLD with the unresolved list).
    Destination: specs/<feature>/ + AGT-01/orchestrator.

PRECONDITIONS:
  - All four artifacts exist (gate). If reading them crosses the Gleaner threshold, AGT-01
    routes the read to The Gleaner.

PROCEDURE:
  1. GATE: verify constitution.md, spec.md, plan.md, tasks.md all exist; else return
     needs_input naming the missing artifact.
  2. Check spec↔constitution compliance; plan↔spec fidelity (no drift); tasks↔plan completeness.
  3. Coverage: every REQ-ID appears in the plan and in at least one task; flag uncovered REQs
     and orphan tasks (tasks with no REQ-ID).
  4. Conflicts: list any cross-artifact contradiction; resolve UP to the constitution.
  5. Emit the findings list + gate verdict; PASS only if the unresolved list is empty (C1).

DECISION POINTS:
  - Decision AN-D1:
    Condition: the unresolved-findings list is empty.
    Branch A (true): verdict PASS; the orchestrator may proceed to implement.
    Branch B (false): verdict HOLD; return findings to the owning phase (AGT-01/AGT-02) to fix.
    Default: treat as B (gate closed) — implement never proceeds on an unrun/failed analyze.
  - Decision AN-D2:
    Condition: a finding is a constitution conflict.
    Branch A (true): require the spec/plan/tasks to change, not the constitution.
    Branch B (false): normal drift/coverage fix.
    Default: treat as A for constitution conflicts.

ERROR HANDLING:
  - Error AN-E1:
    Trigger: an artifact is missing.
    Response: return needs_input naming it and the phase that produces it.
  - Error AN-E2:
    Trigger: an artifact is unparseable/empty.
    Response: HOLD with that artifact flagged; do not pass the gate.

DEPENDENCIES:
  - constitution.md (AGT-01), spec.md (AGT-02), plan.md + tasks.md (AGT-01). Fallback: block.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None — cross-artifact analysis is judgement over prose; the layering/cycle scripts
    (check_layering, check_cycles) are run separately by AGT-01, not bundled here.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Authoring any artifact → sdd-specify/clarify/plan/tasks; code → AGT-03/AGT-05;
    dispatch → orchestrator; quality checklist → sdd-checklist (AGT-06).

SOURCES:
  - User requirements: Dossier §6.2 (sdd-analyze), §6.7 (analyze gate), §7 (convergence gates).
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §2, principles.md §3 (skill row).
