---
name: sdd-checklist
description: >
  SDD "checklist" phase for the PixelArt Creator platform. Use it (invoked by
  AGT-06) to generate and run a quality checklist that validates requirements
  completeness before ship — every REQ-ID/acceptance criterion has a passing test,
  both themes and a11y are covered, and the performance/i18n gates are green. Gate:
  refuses to run unless spec.md (with acceptance criteria) exists.
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
    # P5 inherits AGT-06's; P10 inherits AGT-06's exit status.
  custom:
    - id: C1
      name: Ship gate green
      requires: Ship is allowed only when every checklist item is satisfied by objective evidence (a passing test, a clean script exit, or a cited artifact); an S1/S2 failure forces a HOLD + GitHub issue via AGT-09.
      rationale: Dossier §6.1 (AGT-06), §6.2 (sdd-checklist), §6.7 (checklist gate).
---

SKILL: sdd-checklist
================================================================================

PURPOSE:
  Generate and run a per-feature quality checklist that proves requirements
  completeness and the cross-cutting gates (tests, a11y, both themes, performance,
  i18n) before ship.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES — given
  spec.md acceptance criteria and the test/gate evidence it produces the checklist verdict.

INPUTS:
  - spec.md with acceptance criteria + Gherkin (from AGT-02). Required.
  - Test results (AGT-04/AGT-06), coverage_gate/perf_profile/string_audit outputs. As available.

OUTPUTS:
  - A run checklist: each requirement/criterion + its evidence (passing test id, script exit,
    artifact) + PASS/FAIL, and an overall ship verdict. Destination: specs/<feature>/ + AGT-06.

PRECONDITIONS:
  - spec.md with acceptance criteria exists (gate).

PROCEDURE:
  1. GATE: verify spec.md with acceptance criteria exists; else return needs_input.
  2. Derive one checklist item per REQ-ID/acceptance criterion + cross-cutting items
     (both themes, a11y, coverage ≥90/80, frame budget ≤16 ms, i18n audit clean).
  3. Attach objective evidence to each item (test id, coverage_gate/perf_profile/string_audit
     exit, or cited artifact); mark PASS/FAIL.
  4. Compute the ship verdict: PASS only if every item PASSes; an S1/S2 failure is a hard HOLD.
  5. Write the checklist; hand back to AGT-06 with the verdict.

DECISION POINTS:
  - Decision CK-D1:
    Condition: every checklist item has passing evidence.
    Branch A (true): verdict SHIP-READY.
    Branch B (false): verdict HOLD listing the failing items.
    Default: treat as B (do not declare ship-ready without complete evidence).
  - Decision CK-D2:
    Condition: a failing item is S1 or S2 (core hub).
    Branch A (true): HOLD + request a GitHub issue via AGT-09 through the orchestrator.
    Branch B (false): HOLD only.
    Default: treat as A for S1/S2.

ERROR HANDLING:
  - Error CK-E1:
    Trigger: spec.md/acceptance criteria missing.
    Response: return needs_input naming sdd-specify/clarify.
  - Error CK-E2:
    Trigger: an item lacks any evidence source.
    Response: mark it FAIL (unverified ≠ passed); request the owning agent supply evidence.

DEPENDENCIES:
  - spec.md (AGT-02); test/gate evidence (AGT-04/AGT-06/AGT-09/AGT-10 scripts). Fallback:
    mark unverified items FAIL.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None — evidence comes from the system scripts (coverage_gate, perf_profile, string_audit_check)
    run by their owning agents; this skill consumes their exit codes, it does not bundle them.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Writing tests → AGT-04/AGT-06; code → AGT-03/AGT-05; requirements → AGT-02;
    filing the issue mechanics → AGT-09; performance profiling → AGT-10.

SOURCES:
  - User requirements: Dossier §1 (S1,S2,S13), §6.1 (AGT-06), §6.2 (sdd-checklist), §6.7.
  - Inner assets: asset-templates.md §Skill, spec-driven-development.md §2, principles.md §3 (skill row).
