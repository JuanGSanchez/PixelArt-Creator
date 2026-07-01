---
name: canvas-view
description: >
  8K canvas QGraphicsView/QGraphicsScene skill for the PixelArt Creator platform.
  Use it (invoked by AGT-05 UI Expert) to build the main hub canvas: the scene
  draws the pixel grid + tile background in QGraphicsScene.drawBackground(painter,
  rect) using only the exposed rect (F2), calls setSceneRect(0,0,W,H) once at init
  for the large 8K scene (F3), and the view handles zoom/pan, grid overlay/snap,
  and left-click paint / right-click menu dispatch (S1, S2, S5). Nearest-neighbour,
  no anti-aliasing. It implements AGT-10's culling/dirty-rect directives; it does
  not author the perf strategy.
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
    # P5 inherits AGT-05's context discipline; P10 inherits AGT-05's exit status.
  custom:
    - id: C1
      name: Scene draws grid, view drives input; perf owned by AGT-10
      requires: Tile/grid background is painted in scene.drawBackground(painter, rect) over the exposed rect only; setSceneRect is set once at init; the view owns zoom/pan/input. Tile-culling, dirty-rect and BSP/QOpenGL choices come from AGT-10's directives (this skill implements them).
      rationale: Dossier §2 F2/F3; §9 C2; §6.1 (AGT-05 implements AGT-10).
---

SKILL: canvas-view
================================================================================

PURPOSE:
  Build the QGraphicsScene + QGraphicsView pair for the 8K pixel hub: scene draws
  the grid/tiles in drawBackground over the exposed region; the view provides
  zoom/pan, optional grid overlay + snapping, and routes left-click paint and
  right-click contextual-menu requests — nearest-neighbour, no AA.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the constants + the logic paint API + AGT-10 directives it builds the pair.

INPUTS:
  - logic/constants.py: MAX_CANVAS_WIDTH (7680), MAX_CANVAS_HEIGHT (4320),
    TILE_SIZE (64), TILE_BUFFER, SCALE_FACTOR, PARALLAX_FACTOR.
  - The logic/ paint API (set-pixel/region, from AGT-03) and the active-swatch state.
  - AGT-10 render directives (tile-culling / dirty-rect / QOpenGL viewport / BSP depth).

OUTPUTS:
  - pixelart_creator/ui/ scene + view classes (CONVENTIONS names): scene.drawBackground
    tiling; setSceneRect(0,0,W,H) at init; view zoom/pan (SCALE_FACTOR), grid
    overlay + snap; left-click → logic paint of the target pixel(s) with the active
    swatch (S2); right-click → emit a signal for the colour menu (colour-hub, S3);
    nearest-neighbour rendering, AA disabled.

PRECONDITIONS:
  - constants.py exists; the logic paint API exists; a file_lock on the ui/ path is held.

PROCEDURE:
  1. Create the scene; call setSceneRect(0, 0, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
     ONCE at init to avoid repeated itemsBoundingRect() on the large scene (F3).
  2. Override drawBackground(painter, rect): paint ONLY the tiles/grid intersecting
     the exposed `rect` (scene coords), TILE_SIZE grid, nearest-neighbour, AA off (F2).
  3. In the view: implement zoom (scale by SCALE_FACTOR), pan, optional grid overlay
     and snap-to-grid; keep per-paint work under FRAME_BUDGET_MS.
  4. Input: mouse-press left → map to pixel coords → call logic paint with the active
     swatch (S2); right → emit a colourMenuRequested(pos) signal for colour-hub (S3).
  5. Apply AGT-10 directives (QGraphicsPixmapItem culling / dirty-rect update /
     QOpenGLWidget viewport / setBspTreeDepth) exactly as issued; do not invent perf
     policy. Run string_audit_check + local pre-flight before done.

DECISION POINTS:
  - Decision CV-D1:
    Condition: an AGT-10 directive specifies the viewport/culling approach.
    Branch A: implement it verbatim (QOpenGLWidget viewport, tile-culling radius,
      dirty-rect region).
    Branch B (no directive yet): implement the correct-but-unoptimised scene/view
      and request the directive; do NOT guess BSP depth / culling policy (C1).
    Default: B (block perf choices until AGT-10 grounds them).
  - Decision CV-D2:
    Condition: pixel data vs render culling.
    Branch A: never cull the pixel BUFFER (it stays resident, F7) — cull only the
      QGraphicsPixmapItem rendering per AGT-10.
    Default: A.

ERROR HANDLING:
  - Error CV-E1: paint exceeds FRAME_BUDGET_MS → report to AGT-10 for a directive;
    surface via perf_profile (AGT-10), do not self-tune blindly.
  - Error CV-E2: logic paint API missing → BLOCKED; request AGT-03.

DEPENDENCIES:
  - logic/constants.py + logic paint API (AGT-03); AGT-10 render directives;
    pyside6-qt6-best-practices; scripts/string_audit_check.py.
  - Right-click menu handled by colour-hub (AGT-05).

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None (reuses scripts/string_audit_check.py; profiling is AGT-10's perf_profile).

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Render-perf STRATEGY / profiling / BSP / culling policy → AGT-10 (render-strategy,
    frame-profile). This skill implements directives, it does not author them.
  - Domain paint/blend math → AGT-03 (numpy-buffer-ops). Undo command → ui/commands.py.
  - The right-click colour picker UI + harmonies → colour-hub. Tests → AGT-06.

SOURCES:
  - User requirements: Dossier §1 (S1, S2, S5, S11, S12), §2 (F2, F3, F4, F7),
    §6.1 (AGT-05/AGT-10), §6.2 (canvas-view), §9 (C2).
  - Official docs (via The Researcher, P1): QGraphicsScene.drawBackground (exposed
    rect) + setSceneRect for large scenes (doc.qt.io qgraphicsscene).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row), pyside6-qt6-best-practices.
