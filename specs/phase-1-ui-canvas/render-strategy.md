# Render Strategy — Phase 1 (8K Canvas GPU Pipeline)

| Field | Value |
| --- | --- |
| Author | AGT-10 (Rendering & Performance) |
| Date | 2026-07-02 |
| Mode | **STRATEGY / PRE-IMPLEMENTATION** — directives only; no `ui/` code. Profiling (`frame-profile`) runs AFTER AGT-05 implements. |
| Owns | render-pipeline strategy over `ui/canvas_scene.py` + `ui/canvas_view.py` (dossier C2: scene owns tile `drawBackground`, view owns zoom/pan/input, **AGT-10 owns the perf strategy over both**). |
| Implemented by | AGT-05 (UI Expert) — `canvas-view` skill. |
| Folded into plan by | AGT-01 (resolves BF-1/BF-2/BF-3 in `plan.md`). |
| Budget | `FRAME_BUDGET_MS = 16` / `FPS_TARGET = 60` (constitution Article VI, S12). |
| Grounding | dossier §2 F2, F3, F4, F7; spec REQ-P1-UI-001..008, -023; constitution Art. I/II/VI. |

> Each directive: **directive → grounding → rationale → what AGT-05 must do.**
> Every numeric introduced resolves to an `UPPER_SNAKE_CASE` constant in
> `logic/constants.py` (Article II); the new-constant list is §10, for AGT-03.

---

## D1 — Scene structure: a single whole-buffer `QGraphicsPixmapItem`

**Directive.** Present the active document's buffer as **one** `QGraphicsPixmapItem`
holding the whole 8K image — **not** a grid of tiled pixmap items.

**Grounding.** F7 (a full RGBA 8K buffer ≈ 126 MB is cheap to keep resident; only
`QGraphicsPixmapItem` *rendering* is culled, never pixel data); F2/F3; REQ-P1-UI-001, -002;
BF-2 (this is the HOW-choice the spec left to AGT-01/AGT-10).

**Rationale.**
- Qt already clips a pixmap item's `paint()` to the exposed viewport rect, so a single
  item is culled to the visible region **without** splitting pixel data into items — the
  blit only rasterises visible pixels. Tiling the *pixel data* into hundreds/thousands of
  `QGraphicsPixmapItem`s buys no blit saving and instead bloats the scene index, multiplies
  per-item bookkeeping, and fragments every edit across item boundaries.
- **Edit-locality:** a single item makes dirty-rect trivial — `item.update(QRectF)` over the
  changed pixel rect (D5) invalidates only those pixels. A tiled-item design would force an
  edit that straddles a tile seam to touch multiple items.
- **Budget:** the per-frame cost that matters is the `drawBackground` checker/grid tiling
  (D2) plus the clipped pixmap blit — both bounded by the *viewport*, not by the 8K total.
- Tiling belongs to the **background** (D2, F2) and to viewport culling of *rendering*
  (D4), **not** to slicing the resident buffer (F7).

**What AGT-05 must do.** Add exactly one `QGraphicsPixmapItem` (whole-buffer image, from the
`logic/pixel_buffer.PixelBuffer`) to the scene; render nearest-neighbour, AA disabled at all
zooms (REQ-P1-UI-001). Do not slice the buffer into per-tile pixmap items. Keep the buffer
fully resident (F7); cull only rendering (D4).

---

## D2 — Background/grid drawn only over the exposed `rect`

**Directive.** Draw the checkerboard/tile background **and** the optional per-pixel grid
inside `QGraphicsScene.drawBackground(painter, rect)` using **only** the `rect` argument
(the exposed region, in scene coords). Tile on `TILE_SIZE` (64) with a `TILE_BUFFER` (1)
ring. **Never** iterate the whole 8K scene.

**Grounding.** F2 (tile/grid background belongs in `drawBackground(painter, rect)`, rect =
exposed region, scene coords); REQ-P1-UI-003, -007; CL-4/CL-16; S1.

**Rationale.** The exposed `rect` is the only region that needs painting per frame; iterating
the full scene would be O(8K area) per frame and blow the 16 ms budget. Snapping the loop
start to a `TILE_SIZE` multiple keeps the checker phase-stable while covering only the exposed
tiles + the 1-tile buffer ring. This is precisely the loop the `perf_profile` scenario
measures (`scripts/perf_profile.py`, `draw_background_tiles`).

**What AGT-05 must do.**
- Compute the tile loop bounds from `rect` only: start at
  `floor(rect.left()/TILE_SIZE)*TILE_SIZE` / `floor(rect.top()/TILE_SIZE)*TILE_SIZE`, extend
  one `TILE_BUFFER` tile past `rect.right()/rect.bottom()`; fill checker cells in scene coords.
  No allocation proportional to total scene area.
- **Per-pixel grid lines** (REQ-P1-UI-007) are drawn in the same exposed-rect loop but only
  when the view's current on-screen pixel edge ≥ `GRID_MIN_PIXEL_EDGE_PX` (8 device px, CL-4)
  **and** the overlay is toggled on (off by default). Below the threshold, draw checker only.
- The checker colours are role-based (theme light/dark, REQ-P1-UI-025) — not hard-coded.

---

## D3 — `setSceneRect(0,0,W,H)` once at init (F3)

**Directive.** Set the scene rect explicitly once at scene init, and re-set it on document
resize. Exact call:

```
self.setSceneRect(0, 0, doc.width, doc.height)   # once at init (W,H ≤ MAX_CANVAS_WIDTH/HEIGHT)
```
re-issued inside the `Document.resize_canvas(w, h)` handler as `self.setSceneRect(0, 0, w, h)`.

**Grounding.** F3 (`scene.setSceneRect(0,0,w,h)` must be set explicitly for large scenes to
avoid repeated `itemsBoundingRect()`); REQ-P1-UI-002 (SC-UI-002-1/-2); S1.

**Rationale.** Without an explicit scene rect, `QGraphicsView` recomputes the bounding rect
from `itemsBoundingRect()` on scroll/zoom — an O(items) sweep that is wasteful at 8K. Fixing
it once makes scroll-range and mapping O(1).

**What AGT-05 must do.** Call `setSceneRect(0,0,W,H)` exactly once in scene `__init__` from the
document dimensions; re-set it (never append/accumulate) when `resize_canvas` fires. Assert
`sceneRect() == (0,0,W,H)` is satisfiable for the acceptance tests.

---

## D4 — Viewport culling of *rendering* (buffer stays resident)

**Directive.** Rely on `QGraphicsView`'s exposed-rect painting to cull off-screen rendering;
set the view's viewport update mode to **minimal** so only the dirty viewport region repaints.
The resident pixel buffer is **never** culled (F7).

**Grounding.** F7 (only `QGraphicsPixmapItem` rendering is culled, not pixel data); F2; C2;
REQ-P1-UI-023 (SC-UI-023-2: panning culls off-screen tiles, resident buffer not culled);
constitution Art. VI §3.

**Rationale.** With the single-item design (D1), culling is *inherent*: the view passes only
the exposed rect to `drawBackground` (D2) and clips the pixmap item's `paint()` to the visible
region. The one pipeline lever that changes per-frame cost is the **viewport update mode** —
`FullViewportUpdate` would repaint the entire widget on every edit and defeat dirty-rect (D5).
`MinimalViewportUpdate` repaints only the mapped dirty region.

**What AGT-05 must do.**
- Set `view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)`
  (do **not** use `FullViewportUpdate`).
- Do **not** attempt to cull/evict pixel data or the pixmap item — keep it fully resident
  (F7). Culling is a *rendering* concern only, satisfied by the exposed-rect + item clip.
- Ensure panning (REQ-P1-UI-005) does not force a full-scene repaint (SC-UI-023-2).

---

## D5 — Dirty-rect partial redraw on a paint edit

**Directive.** On a paint edit, invalidate **only** the affected pixel rect via
`item.update(QRectF)` (or `scene.update(QRectF)` over the changed region) — **never** a
full-scene `scene.update()` / no-arg repaint.

**Grounding.** F2/F7; REQ-P1-UI-006 (paint), -023 (SC-UI-023-1: single-pixel paint redraw ≤
16 ms); constitution Art. VI.

**Rationale.** The `logic/drawing.py` primitives already return the changed `(x,y)` coords
(spec §7). Bounding those into one `QRectF` and updating just that rect keeps a single-pixel or
small-stroke edit's repaint cost proportional to the edit, not to the 8K scene. Combined with
`MinimalViewportUpdate` (D4) the view then repaints only the mapped viewport region.

**What AGT-05 must do.**
- After a tool applies a primitive, take the returned changed-coords set, compute its bounding
  `QRectF` (in scene/pixel coords), refresh that region of the pixmap item, and call
  `item.update(bounding_rect)` (or `scene.update(bounding_rect)`).
- Never call the no-argument `scene.update()` / `viewport().update()` on an edit.
- The line-tool *preview* (REQ-P1-UI-015) must also update only the preview's bounding rect,
  and clear the previous preview rect (no full repaint) while dragging.

---

## D6 — `QOpenGLWidget` viewport for GPU-accelerated blits

**Directive.** Set a `QOpenGLWidget` as the `QGraphicsView` viewport for GPU-accelerated
blitting of the large scaled pixmap, gated behind the `OPENGL_VIEWPORT_ENABLED` toggle
constant, with a raster fallback when the toggle is off or a GL context is unavailable.
**Recommendation: enabled by default** on the interactive desktop app.

**Grounding.** F7 (large resident pixmap → blit cost dominates at deep zoom); constitution
Art. VI; REQ-P1-UI-004 (deep zoom to 6400%).

**Rationale / trade-off.**
- **For:** at deep zoom and during pan the dominant cost is blitting/scaling the large pixmap;
  a GL viewport moves that to the GPU, giving smooth 60 fps pan/zoom that a raster viewport
  can miss at 8K.
- **Against:** a GL viewport needs a working GL context. Headless/offscreen (CI,
  `QT_QPA_PLATFORM=offscreen`) and some drivers/VMs may lack one; a GL viewport can also
  interact awkwardly with partial `MinimalViewportUpdate` on some drivers.
- **Resolution:** make it a runtime toggle (`OPENGL_VIEWPORT_ENABLED`) so the app uses GL on
  desktop and degrades to the default raster viewport headless / when GL init fails.
  The `frame-profile` harness measures the raster `drawBackground` tiling path (it renders to a
  `QImage`, not the widget), so the GL benefit is verified interactively / by the pytest-qt
  redraw test, not by `perf_profile`. **Mark as a profiling/verify knob (§9 P-B/P-C).**

**What AGT-05 must do.** Construct the view so that, when `OPENGL_VIEWPORT_ENABLED` is true and
a GL context initialises, `view.setViewport(QOpenGLWidget())` is used; otherwise fall back to
the standard raster viewport. Do not hard-code the choice; read the constant.

---

## D7 — `setBspTreeDepth` / scene index for a static single-item scene

**Directive.** Accept the **default auto** BSP-tree depth for the Phase-1 static 8K scene
(F4). Because the scene holds a single large pixmap item (D1), also consider
`scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)`. Treat both the index
method and any explicit `setBspTreeDepth` value as **profiling knobs** — introduce an explicit
depth constant **only if** profiling demonstrates a win.

**Grounding.** F4 (`setBspTreeDepth` tunable; default auto-tuning acceptable for static 8K
grids — verify in profiling); constitution Art. II (add a constant only when a value is
actually introduced).

**Rationale.** The BSP tree accelerates *item* lookup. With one item, BSP indexing gives no
benefit and its reindex-on-update cost is pure overhead — `NoIndex` can be strictly better and
avoids reindexing when the pixmap item updates (D5). No explicit depth is warranted up front;
per Article II we do **not** pre-add a `BSP_TREE_DEPTH` constant that isn't yet used.

**What AGT-05 must do.** Leave BSP depth at auto for now; set `NoIndex` on the single-item
scene. Expose no magic number. If §9 profiling later shows a benefit from an explicit depth,
AGT-10 will issue a follow-up directive and AGT-03 will add the constant then.

---

## 8. Constitution / scope notes

- **Article I:** every directive targets `ui/canvas_scene.py` / `ui/canvas_view.py`; no
  domain logic is introduced — tools bind to `logic/drawing.py` (spec §7). AGT-10 authors
  **no** `ui/` code (P9).
- **Article II:** the two numerics introduced (§10) go to `logic/constants.py`; no literal
  appears in `ui/`.
- **Article VI:** the budget is `FRAME_BUDGET_MS = 16`; an over-budget profile (D-A10-D2
  Branch B) yields an optimisation directive, never a budget relaxation.
- **Out of my lane (do not fold into these directives):** zoom range/step constants
  (6400 % max, `SCALE_FACTOR` reuse) are BF-3 → AGT-01/AGT-05 (`canvas-navigation`), not a
  render-pipeline numeric. Grid *visibility* threshold IS mine (it gates `drawBackground`
  work), so `GRID_MIN_PIXEL_EDGE_PX` is listed below.

---

## 9. Profiling plan (runs AFTER AGT-05 implements — `frame-profile`)

`scripts/perf_profile.py` renders the exposed-rect tile `drawBackground` headless
(`QT_QPA_PLATFORM=offscreen`) and reports `{median_ms, p95_ms, tiles_per_frame, within_budget}`.
**Pass criterion (every scenario): `median_ms ≤ FRAME_BUDGET_MS` (16) → script exit `0`.**
`p95_ms` is recorded for tail awareness; the gate is the median (per script contract + C2).
Exit `1` = over budget → AGT-10 issues an optimisation directive to AGT-05 (D-A10-D2 Branch B),
PARTIAL until re-profiled green. Exit `2` = PySide6/offscreen unavailable → BLOCKED (A10-E2).

| Id | Scenario | Command | Why |
| --- | --- | --- | --- |
| **P-A** | **8K full-view at fit zoom** (worst-case tile count — whole scene exposed) | `python scripts/perf_profile.py --width 7680 --height 4320 --zoom 0.25 --viewport 1920 1080 --frames 60` | Stress case: at fit (1920/7680 ≈ 0.25) the exposed rect ≈ whole 8K, so the checker loop paints the most tiles. If this passes, D2 tiling holds the budget. |
| **P-B** | **Deep zoom (6400 %)** | `python scripts/perf_profile.py --zoom 64 --viewport 1920 1080 --frames 60` | At 6400 % the exposed scene rect is tiny (few tiles) — verifies the tile loop stays cheap while the pixmap is scaled huge (D6/GL benefit region). |
| **P-C** | **1:1 baseline** | `python scripts/perf_profile.py --zoom 1.0 --viewport 1920 1080 --frames 60` | Default working zoom; sanity baseline for the tiling path. |
| **P-D** | **Single-pixel-edit dirty-rect** (partial-repaint proxy) | `python scripts/perf_profile.py --zoom 1.0 --viewport 64 64 --frames 60` | Models D5: a single-pixel edit repaints only its mapped (~tile-sized) region. Small exposed rect → minimal tiles; must be far under budget. |

**Notes for the profiling pass.**
- P-A is the gating case for SC-UI-023-2 (pan cull) and Article VI; P-D corresponds to
  SC-UI-023-1 (single-pixel paint redraw). The *interactive* GL benefit (D6) and the true view
  dirty-rect repaint are additionally confirmed by AGT-06's pytest-qt SC-UI-023-1 measurement —
  `perf_profile` covers the `drawBackground` component only (it renders to a `QImage`).
- If a scenario returns exit `1`, candidate directives to AGT-05 (in order): confirm
  `MinimalViewportUpdate` (D4); confirm no full-scene `update()` (D5); reduce tiles/frame by
  trimming `TILE_BUFFER`; enable/confirm `OPENGL_VIEWPORT_ENABLED` (D6); then evaluate an
  explicit `setBspTreeDepth` (D7). Re-profile until green.
- Sweeps (e.g. tile size vs frame time) may use an ephemeral script wrapping `perf_profile`;
  discard after (P11).

---

## 10. New tuning constants (for AGT-03 → `logic/constants.py`, Article II)

| Constant | Value | Meaning | Directive / grounding |
| --- | --- | --- | --- |
| `GRID_MIN_PIXEL_EDGE_PX` | `8` | The per-pixel grid overlay is drawn in `drawBackground` only when a buffer pixel's on-screen edge ≥ this many device px (below it, checker only) — gates grid-draw work. | D2; CL-4; REQ-P1-UI-007 |
| `OPENGL_VIEWPORT_ENABLED` | `True` | When true (and a GL context initialises) the `QGraphicsView` viewport is a `QOpenGLWidget` for GPU-accelerated blits; false / GL-unavailable falls back to the raster viewport. | D6; F7; Art. VI |

Not introduced now (Article II — add only when used): no `BSP_TREE_DEPTH` constant — D7 keeps
BSP at auto / `NoIndex`; a constant is added only if profiling (§9) proves an explicit depth
wins.

---

## 11. Status

- Render-pipeline directives D1–D7 authored, each grounded (F2/F3/F4/F7) and traced to the
  spec REQ / clarification, for AGT-05 to implement and AGT-01 to fold into `plan.md` (BF-1/-2).
- Profiling plan (§9) defined with four `perf_profile` scenarios and the `median ≤ 16 ms`
  pass criterion; runs post-implementation (`frame-profile`). No measurement asserted yet
  (C2 — never claim a budget pass without a run).
- Two new constants listed for AGT-03 (§10).
- **EXIT_STATUS: COMPLETED** (strategy + profiling plan done; profiling deferred until AGT-05
  implements — no over-budget directive outstanding).
