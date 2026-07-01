---
name: render-strategy
description: >
  GPU render-pipeline strategy skill for the PixelArt Creator platform. Use it
  (invoked by AGT-10 Rendering & Performance) to author the optimization directives
  AGT-05 implements for the 8K canvas: QGraphicsScene.drawBackground tiling scope,
  viewport tile-culling of QGraphicsPixmapItems, dirty-rect partial redraw,
  QOpenGLWidget viewport, setSceneRect, and setBspTreeDepth tuning — each grounded
  in F2/F3/F4/F7 and justified by a frame-profile measurement. Strategy only; it
  writes no ui/ code.
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
      name: Directives, not code
      requires: This skill produces a written directive (what to change + why + the expected budget effect); AGT-05 implements it in ui/ (canvas-view). AGT-10 never authors widget code.
      rationale: Dossier §6.1 (AGT-10 issues directives AGT-05 implements); §9 C2.
---

SKILL: render-strategy
================================================================================

PURPOSE:
  Decide HOW the 8K canvas renders within budget and express it as concrete,
  grounded directives (culling policy, dirty-rect scope, viewport, BSP depth,
  setSceneRect) that AGT-05 can implement verbatim.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the profiling report + the canvas design it emits directives unaided.

INPUTS:
  - A frame-profile report (hotspots vs FRAME_BUDGET_MS); the current canvas-view
    design; constants (TILE_SIZE, TILE_BUFFER, FRAME_BUDGET_MS, S12).

OUTPUTS:
  - Render directives for AGT-05: e.g. "cull QGraphicsPixmapItems outside the
    viewport ±TILE_BUFFER tiles"; "repaint only the dirty rect in drawBackground";
    "use a QOpenGLWidget viewport"; "set setBspTreeDepth=N (verify by profiling)";
    "setSceneRect(0,0,W,H) at init" — each with the F-finding + expected budget effect.

PRECONDITIONS:
  - A frame-profile measurement (or a clear a-priori bottleneck) exists.

PROCEDURE:
  1. Read the frame-profile report; locate the dominant cost.
  2. Choose the minimal, grounded intervention: tiling scope to the exposed rect (F2);
     setSceneRect once at init to avoid itemsBoundingRect() recompute (F3); cull
     rendered items (not pixel data, F7); dirty-rect partial redraw; QOpenGLWidget
     viewport; setBspTreeDepth tuning (F4 — default auto acceptable for static 8K,
     verify by profiling).
  3. Write the directive: the change, the grounding finding, and the expected
     effect on frame time; do NOT write ui/ code (C1).
  4. Hand the directive to AGT-05 (canvas-view); after they implement, request a
     re-profile (frame-profile) to confirm the budget is met.

DECISION POINTS:
  - Decision RS-D1:
    Condition: a proposed optimization would cull PIXEL DATA to save memory.
    Branch A: reject — the 8K RGBA buffer stays resident (F7); cull only the
      QGraphicsPixmapItem RENDERING.
    Default: A.
  - Decision RS-D2:
    Condition: a BSP-depth or viewport change is proposed without measurement.
    Branch A: require a frame-profile before/after (F4 says verify by profiling);
      do not assert a perf gain unmeasured (P1/P2).
    Default: A.

ERROR HANDLING:
  - Error RS-E1: after AGT-05 implements, re-profile still over budget → issue the
    next-most-impactful directive; iterate (bounded by the inner-loop governance).
  - Error RS-E2: no measurement available → request frame-profile first (do not
    guess the hotspot).

DEPENDENCIES:
  - frame-profile (AGT-10) for measurement; canvas-view (AGT-05) implements.
    constants.py budget. Fallback: block a directive until a measurement grounds it.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (measurement is frame-profile's perf_profile).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Implementing directives in ui/ → AGT-05 (canvas-view). Running the profiler →
    frame-profile (AGT-10). Widget structure/undo → AGT-05. Logic/blend math → AGT-03.

SOURCES:
  - User requirements: Dossier §1 (S1, S5, S12), §2 (F2, F3, F4, F7), §6.1 (AGT-10),
    §6.2 (render-strategy), §9 (C2).
  - Official docs (via The Researcher, P1): QGraphicsScene.drawBackground / setSceneRect /
    setBspTreeDepth / QOpenGLWidget viewport (doc.qt.io qgraphicsscene, per F2/F3/F4).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), programmatic-determinism.md.
