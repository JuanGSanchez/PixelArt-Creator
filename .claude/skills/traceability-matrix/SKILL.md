---
name: traceability-matrix
description: >
  Requirements-traceability matrix builder for the PixelArt Creator platform.
  Use it (invoked by AGT-02 Requirements) to build and maintain the
  REQ ↔ spec ↔ acceptance-scenario ↔ test matrix that proves every requirement
  is specified, has acceptance criteria, and is covered by at least one test —
  the evidence sdd-analyze and AGT-06 consume before ship.
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
    # P5 inherits AGT-02's context discipline; P10 inherits AGT-02's exit status.
---

SKILL: traceability-matrix
================================================================================

PURPOSE:
  Produce the matrix linking each REQ-ID to the spec section that defines it, the
  Gherkin acceptance scenario(s) that verify it, and the test id(s) that exercise
  it — surfacing any requirement with no scenario or no test (a coverage gap).

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given spec.md, the scenarios, and the test index it emits the matrix + a gap list.

INPUTS:
  - spec.md (REQ-IDs), the Gherkin scenarios (from sdd-clarify), and the test
    index (test node ids from tests/, gathered via the orchestrator/Gleaner).

OUTPUTS:
  - A matrix (Markdown table): REQ-ID | spec section | scenario id(s) | test id(s)
    | status (covered / spec-only / uncovered).
  - A gap list: REQ-IDs missing a scenario or a test (feeds AGT-02/AGT-06).

PRECONDITIONS:
  - spec.md exists with REQ-IDs; scenarios exist (may be empty → all uncovered).

PROCEDURE:
  1. Enumerate REQ-IDs from spec.md.
  2. For each, locate the acceptance scenario(s) and the test id(s) that name/
     cover it; when reading ≥5 files to find them, request the Gleaner via the
     orchestrator (do not read them directly).
  3. Mark status: covered (scenario + test), spec-only (no test yet), or
     uncovered (no scenario).
  4. Emit the matrix + the gap list; return to AGT-02; the gaps drive test asks
     to AGT-04/AGT-06 and clarifications back to sdd-clarify.

DECISION POINTS:
  - Decision TM-D1:
    Condition: the file set to scan is ≥ the Gleaner threshold (5).
    Branch A (true): GATHERING REQUEST via the orchestrator; use the gather file.
    Branch B (false): read directly.
    Default: if unknown, treat as true (dispatch the Gleaner).
  - Decision TM-D2:
    Condition: a REQ-ID has no acceptance criteria at all.
    Branch A: mark uncovered AND return it to sdd-clarify (AGT-02) — a requirement
      without a testable criterion is not shippable.
    Default: A.

ERROR HANDLING:
  - Error TM-E1: spec.md absent → BLOCKED; request AGT-02 draft it (sdd-specify).
  - Error TM-E2: duplicate/renumbered REQ-IDs → flag the collision to AGT-02.

DEPENDENCIES:
  - spec.md + scenarios (AGT-02); test index (AGT-04/AGT-06 outputs). Fallback:
    if tests do not yet exist, list every REQ as spec-only/uncovered.
  - The Gleaner (via orchestrator) for multi-file scans.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Writing the spec/scenarios → sdd-specify / sdd-clarify (AGT-02).
  - Writing the tests → AGT-04 (logic/data) / AGT-06 (ui).
  - The cross-artifact consistency gate → sdd-analyze (AGT-01).

SOURCES:
  - User requirements: Dossier §6.1 (AGT-02), §6.2 (traceability-matrix), §1 (S13 coverage).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    spec-driven-development.md (analyze/coverage).
