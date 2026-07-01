---
name: pytest-scaffold
description: >
  Logic/data test-module scaffolder for the PixelArt Creator platform. Use it
  (invoked by AGT-04 Python Tester) to create a pytest test module + conftest for
  a pure-Python logic/ or data/ unit — no Qt — with tests named test_<module>.py,
  one test per behaviour, arranged for the coverage gate (≥90% line / ≥80% branch,
  S13) verified by the coverage_gate script, and a regression test per fix.
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
    # P5 inherits AGT-04's context discipline; P10 inherits AGT-04's exit status.
---

SKILL: pytest-scaffold
================================================================================

PURPOSE:
  Emit a runnable pytest test module (and conftest fixtures) for a logic/ or data/
  unit, structured so the coverage gate can pass and so each behaviour, edge case,
  and past fix has an explicit test.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the module-under-test's interface it emits a test module + conftest unaided.

INPUTS:
  - The module under test + its interface contract (public functions, exceptions).
  - Any fix id needing a regression test.

OUTPUTS:
  - tests/logic/test_<module>.py or tests/data/test_<module>.py: arrange/act/assert
    tests, one per behaviour + edge/exception path; shared fixtures in conftest.py;
    no Qt import (logic/data tests only).

PRECONDITIONS:
  - The module under test exists and is importable; pytest + pytest-cov available.

PROCEDURE:
  1. Enumerate the public surface (from interface-contract) and every branch/raise.
  2. Write one focused test per behaviour + one per exception/edge; parametrise
     over boundary values sourced from logic/constants.py (S12).
  3. Add a regression test for each named fix (title it with the fix id).
  4. Put shared setup in conftest.py; keep tests deterministic (no time/random
     unless seeded/injected).
  5. Run `pytest` then `python scripts/coverage_gate.py` (≥90/80); if below, add
     tests for the uncovered lines/branches until it exits 0.

DECISION POINTS:
  - Decision PS-D1:
    Condition: a heavy test (large buffer / slow property) would dominate runtime.
    Branch A: mark it with a deselectable marker so CI can run/skip it explicitly.
    Default: A (keep the default suite fast + portable).
  - Decision PS-D2:
    Condition: coverage_gate stays below threshold after obvious cases.
    Branch A: inspect the coverage report, add tests for the exact uncovered
      branches; do not lower the threshold (S13).
    Default: A.

ERROR HANDLING:
  - Error PS-E1: module not importable → BLOCKED; the code (AGT-03) is not ready.
  - Error PS-E2: a test needs randomness → seed it or inject the value (P2).

DEPENDENCIES:
  - The module under test (AGT-03). scripts/coverage_gate.py (Dossier §6.5).
  - Property strategies → hypothesis-strategy. Fallback: plain parametrisation.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/coverage_gate.py + pytest).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - UI / pytest-qt / integration tests → AGT-06 (pytest-qt-harness).
  - The code under test → AGT-03. CI wiring of the gate → AGT-09 (ci-author).
  - Property-strategy design detail → hypothesis-strategy (same agent, separate skill).

SOURCES:
  - User requirements: Dossier §1 (S13 coverage), §6.1 (AGT-04), §6.2 (pytest-scaffold).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    pytest-best-practices instruction (grounded via The Researcher).
