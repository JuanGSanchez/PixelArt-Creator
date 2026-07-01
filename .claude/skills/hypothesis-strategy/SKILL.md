---
name: hypothesis-strategy
description: >
  Property-based testing strategy skill for the PixelArt Creator platform. Use it
  (invoked by AGT-04 Python Tester) to design Hypothesis strategies that generate
  valid pixel/palette/geometry data (bounded RGBA values, in-canvas coordinates,
  colour lists) and the invariants to assert (e.g. apply∘invert = identity for
  reversible ops, alpha-blend idempotence, coordinate bounds), keeping runs
  deterministic and portable.
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

SKILL: hypothesis-strategy
================================================================================

PURPOSE:
  Provide reusable Hypothesis strategies + the properties to check for pixel-art
  domain data, so logic invariants (reversibility, bounds, blend correctness) are
  tested across generated inputs, not just hand-picked examples.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the data shape + the invariant it emits a strategy + property test unaided.

INPUTS:
  - The data type to generate (RGBA colour, pixel coordinate, palette, region).
  - The invariant(s) to assert; logic/constants.py bounds (S12).

OUTPUTS:
  - Hypothesis strategies (e.g. rgba(), coord_within_canvas(), palette()) and the
    @given property tests asserting the invariants, with a fixed seed/profile for
    determinism and deselectable markers for expensive runs.

PRECONDITIONS:
  - Hypothesis is available; the unit under test exposes the invariant to check.

PROCEDURE:
  1. Define bounded strategies: RGBA components in 0..255; coordinates in
     0..MAX_CANVAS_WIDTH/HEIGHT-1 (from constants.py); palettes as small lists.
  2. State each invariant as an assertion over generated inputs (e.g. for a
     reversible op, `apply` then `invert` returns the original buffer region).
  3. Pin a deterministic Hypothesis profile (fixed seed / no flaky deadline) so CI
     is reproducible; mark slow properties deselectable.
  4. Keep strategies portable (no host paths, no wall-clock).
  5. Hand the strategies + properties to pytest-scaffold to include in the suite.

DECISION POINTS:
  - Decision HS-D1:
    Condition: a property is flaky (timing/health-check).
    Branch A: constrain the strategy / disable the deadline for that test; never
      leave a nondeterministic property in the default suite (P2).
    Default: A.
  - Decision HS-D2:
    Condition: generation explores impractically large buffers.
    Branch A: bound sizes to small regions and mark full-canvas properties
      deselectable (run explicitly in CI).
    Default: A.

ERROR HANDLING:
  - Error HS-E1: a discovered counterexample is a real bug → return it to AGT-04
    as a regression test request (feeds AGT-03 to fix).
  - Error HS-E2: strategy generates out-of-bounds data by design → tighten bounds.

DEPENDENCIES:
  - Hypothesis (dev dep, pyproject.toml). logic/constants.py bounds.
  - Consumed by pytest-scaffold (AGT-04). Fallback: plain parametrised tests.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Test module assembly / coverage gate → pytest-scaffold (AGT-04).
  - UI property tests → AGT-06 (pytest-qt-harness).
  - The code under test → AGT-03.

SOURCES:
  - User requirements: Dossier §1 (S8 Hypothesis, S13), §6.1 (AGT-04), §6.2 (hypothesis-strategy).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row),
    pytest-best-practices (Hypothesis determinism, via The Researcher).
