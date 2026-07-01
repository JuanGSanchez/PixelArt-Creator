---
name: sdd-clarify
description: >
  SDD "clarify" phase for the PixelArt Creator platform. Use it (invoked by
  AGT-02) to resolve underspecified areas of a feature's spec.md through
  structured questioning BEFORE any planning, recording answers back into spec.md,
  and to emit Gherkin acceptance scenarios as an output step. Gate: refuses to run
  unless spec.md exists.
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
    # P5 inherits AGT-02's; P10 inherits AGT-02's exit status.
  custom:
    - id: C1
      name: No plan while ambiguous
      requires: The clarify phase must resolve or explicitly defer every open question and record it into spec.md before sdd-plan may run; unresolved ambiguity blocks planning.
      rationale: spec-driven-development.md §2 (clarify gate).
---

SKILL: sdd-clarify
================================================================================

PURPOSE:
  Drive out ambiguity in spec.md via structured questioning, record the answers into
  spec.md, and generate Gherkin acceptance scenarios for the clarified requirements.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES — given
  spec.md it produces the clarification set and Gherkin unaided.

INPUTS:
  - spec.md (from sdd-specify). Required.
  - User answers to clarification questions (via AGT-02 / orchestrator). As needed.

OUTPUTS:
  - Clarifications block appended into spec.md (each Q, its answer, and the resolved decision).
  - Gherkin acceptance scenarios (Given/When/Then) per clarified requirement + a traceability
    row linking REQ-ID → scenario. Destination: spec.md / specs/<feature>/.

PRECONDITIONS:
  - spec.md exists (gate). 

PROCEDURE:
  1. GATE: verify spec.md exists; if missing, return needs_input (run sdd-specify first).
  2. Scan spec.md for underspecified areas (ambiguous quantities, undefined states, missing
     error/edge behaviour, unstated non-functionals).
  3. Emit a numbered, prioritized question list; route to the user via AGT-02/orchestrator.
  4. Record each answer as a resolved decision (category-1 source) back into spec.md.
  5. Generate Gherkin scenarios for each clarified requirement; add REQ-ID→scenario traceability.
  6. Confirm no open question remains (or is explicitly deferred with rationale); hand back.

DECISION POINTS:
  - Decision CL-D1:
    Condition: an open question remains unanswered.
    Branch A (true): keep the feature in needs_input; do NOT clear the clarify gate (C1).
    Branch B (false): mark clarify complete.
    Default: treat as A (block planning while ambiguous).
  - Decision CL-D2:
    Condition: a clarification changes a functional requirement.
    Branch A (true): update spec.md's requirement + its acceptance criteria + Gherkin together.
    Branch B (false): append clarification only.
    Default: treat as A (keep spec, criteria, and Gherkin consistent).

ERROR HANDLING:
  - Error CL-E1:
    Trigger: spec.md missing.
    Response: return needs_input; name sdd-specify as the predecessor.
  - Error CL-E2:
    Trigger: a question is unanswerable without a product decision the user must make.
    Response: surface it explicitly; do not invent an answer (P1).

DEPENDENCIES:
  - spec.md (sdd-specify / AGT-02). Fallback: block until it exists.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Architecture/stack → sdd-plan (AGT-01); tasks → sdd-tasks; code → AGT-03/AGT-05;
    running acceptance tests from the Gherkin → AGT-06.

SOURCES:
  - User requirements: Dossier §6.2 (sdd-clarify), §6.6 (gherkin disposition).
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §2, principles.md §3 (skill row).
