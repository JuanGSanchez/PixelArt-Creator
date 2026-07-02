# Plan — Phase 1 (UI Increment): Canvas, Tools, Undo/Redo, Shell & i18n

| Field | Value |
| --- | --- |
| Feature | `phase-1-ui-canvas` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| SDD phase | `plan` (HOW) over the approved `spec.md` + `clarify` defaults §10 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VIII, X) |
| Inputs | `spec.md` (REQ-P1-UI-001..026, 44 Gherkin, §10 CL-defaults, §8 deferred HOW), `traceability.md`, `render-strategy.md` (AGT-10 D1–D7 + §10 constants), `specs/phase-1-core-engine/spec.md` (shipped logic/data API) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no `ui/` code exists yet; this plan fixes the HOW and resolves BF-1/BF-2/BF-3 |
| Consumed by | `sdd-tasks` (→ `tasks.md`) then `sdd-analyze` (C1 gate) |

---

## 1. Architecture overview (WHAT the HOW must hold)

The increment adds the first presentation layer over the shipped, Qt-free
`logic/` + `data/` engine. Every new file lives under `pixelart_creator/ui/**`.
The UI **binds** to the logic API and introduces **zero** domain logic
(Article I). The stack is fixed (S8): PySide6 / Qt6, `QGraphicsScene`/`QGraphicsView`
for the canvas, `QUndoStack`/`QUndoCommand` for undo, `QTranslator` for i18n. No new
technology is chosen here.

### 1.1 The three-layer boundary (Article I — non-negotiable)

- **All new modules are under `pixelart_creator/ui/`.** No file is added to
  `logic/` or `data/` in this slice **except** the pure-numeric additions to
  `logic/constants.py` (T1, Article II — zero Qt).
- **Qt lives only in `ui/`.** `logic/` and `data/` keep **zero** Qt imports. The
  bridge module is `ui/commands.py` (QUndoCommand wrappers) — it is inside `ui/`,
  so it is compliant; the constitution's "only Qt file outside `ui/`" clause is
  satisfied because no `logic/`/`data/` module imports Qt at all.
- **Dependency direction is one-way:** `ui/` → `logic/` + `data/`; never the
  reverse; no cycles. Enforced by `check_layering` + `check_cycles` (both must
  exit `0`; exit `2` ⇒ BLOCKED, never "clean").
- **Widgets carry no domain logic.** Every pixel/geometry/colour computation is a
  call into `logic/` (`drawing`, `pixel_buffer`, `history`, `palette`, `color`,
  `document`) or `data/project_io`. Controllers/panels/views hold only Qt wiring,
  event→coordinate mapping, and presentation state (active tool, active colour).

### 1.2 Canvas rendering approach — AGT-10 directives D1–D7 (resolves BF-1/BF-2)

The canvas implements AGT-10's render-strategy verbatim; each directive is the
plan-level HOW the spec deferred:

| Dir | Decision folded into this plan | Target |
| --- | --- | --- |
| **D1** | Present the active layer buffer as **one** `QGraphicsPixmapItem` (whole-buffer image), **not** tiled pixmap items. Nearest-neighbour, AA disabled at every zoom (REQ-P1-UI-001). Buffer stays fully resident (F7). | `canvas_scene.py` |
| **D2** | Draw checkerboard **and** optional per-pixel grid inside `drawBackground(painter, rect)` using **only** the exposed `rect`; tile on `TILE_SIZE`(64) + `TILE_BUFFER`(1) ring; never iterate the 8K scene (REQ-P1-UI-003, -007). Checker/grid colours are role-based (REQ-P1-UI-025). | `canvas_scene.py` |
| **D3** | `setSceneRect(0,0,W,H)` **once** at scene `__init__` from doc dims; re-set (never accumulate) on `Document.resize_canvas` (REQ-P1-UI-002). | `canvas_scene.py` |
| **D4** | `view.setViewportUpdateMode(MinimalViewportUpdate)`; rely on exposed-rect painting to cull *rendering*; never cull the resident buffer (REQ-P1-UI-023 / SC-UI-023-2). | `canvas_view.py` |
| **D5** | On a paint edit, `item.update(QRectF)` over **only** the changed-coords bounding rect (from the primitive's returned coords); never a no-arg `scene.update()`. Line-tool preview updates/clears only its bounding rect (REQ-P1-UI-006, -015, -023). | `canvas_view.py`, tools |
| **D6** | `QOpenGLWidget` viewport gated behind `OPENGL_VIEWPORT_ENABLED`; raster fallback when the toggle is off or a GL context is unavailable (headless CI). Read the constant; never hard-code the choice (REQ-P1-UI-004). | `canvas_view.py` |
| **D7** | Leave BSP depth at **auto**; set `scene.setItemIndexMethod(NoIndex)` for the single-item scene. Introduce **no** `BSP_TREE_DEPTH` constant unless profiling (§9 of render-strategy) proves a win. | `canvas_scene.py` |

**BF-2 resolved:** single whole-buffer `QGraphicsPixmapItem` (D1), not tiled items.
**BF-1 resolved:** the culling/dirty-rect/viewport strategy is D2/D4/D5/D6; the
16 ms budget (REQ-P1-UI-023) is **verified** post-implementation by AGT-10
`perf_profile` (P-A..P-D), never asserted here (C2).

### 1.3 The 16 clarification defaults as the behavioral contract (spec §10)

The plan binds every CL-default as a fixed behaviour:

| CL | Contract encoded in the plan |
| --- | --- |
| CL-1 | Zoom range **fit-to-view (min) … `ZOOM_MAX`=64.0 (6400 %) (max)**; clamp to both bounds (SC-UI-004-1). |
| CL-2 | Wheel zoom = geometric step `1.0 + SCALE_FACTOR` (≈×1.15) per notch; keyboard zoom snaps to `ZOOM_PRESET_STOPS` (100..6400 %). **BF-3 resolved: reuse `SCALE_FACTOR`** for the step; add `ZOOM_MAX` + `ZOOM_PRESET_STOPS` as new named constants. |
| CL-3 | Pan = **middle-drag** and **Space+left-drag**; scrollbars as fallback; pan never paints (SC-UI-005-1/-2). |
| CL-4 | Grid overlay **off by default**; auto-shown only when on-screen pixel edge ≥ `GRID_MIN_PIXEL_EDGE_PX`(8) **and** toggled on (SC-UI-007-1/-2). |
| CL-5 | Exactly five tools: pencil, eraser, flood-fill, line, colour-picker. |
| CL-6 | Palette panel is **single-select** (one active swatch) (SC-UI-018-2). |
| CL-7 | New document default **64×64 RGBA** (`DEFAULT_CANVAS_WIDTH`/`_HEIGHT`); arbitrary sizes up to `MAX_CANVAS_*` (SC-UI-020-1/-2). |
| CL-8 | Right-click = dispatch **seam** to a replaceable menu hook; Phase-1 hook shows a placeholder; colour hub deferred to Phase 3 (SC-UI-008-1/-2). |
| CL-9 | **One `QUndoCommand` per completed stroke** (drag coalesces) (SC-UI-006-2). |
| CL-10 | Active colour set by **palette panel** and **colour-picker** (SC-UI-016-1, -018-2). |
| CL-11 | Line tool: live preview during drag, **commit one command on release** (SC-UI-015-1). |
| CL-12 | Scene point **floored** to integer pixel; off-buffer click is a **no-op** (no command) (SC-UI-006-3). |
| CL-13 | Ship light + dark; default follows OS/light; runtime switch (REQ-P1-UI-025). |
| CL-14 | Language from system `QLocale`; fallback **English** (SC-UI-021-1). |
| CL-15 | Zoom anchors on the **cursor** (view-centre for keyboard zoom) (SC-UI-004-2). |
| CL-16 | Culling tile size `TILE_SIZE`=64, `TILE_BUFFER`=1 (existing constants). |

### 1.4 Data flow

`Document` (per tab) → active `Frame` → active `Layer` → `PixelBuffer`. The scene
renders that buffer as one pixmap item (D1). A tool controller maps a view mouse
event → floored `(x,y)` (CL-12) → calls a `logic/drawing.py` primitive **inside**
`logic.history.record_edit` to capture a `PixelEdit`, wraps it in a
`ui/commands.PaintCommand`, and pushes it on the active document's `QUndoStack`
(CL-9). The command's `redo/undo` delegate to `PixelEdit.execute/undo` (D5 refresh
of the changed rect). The palette panel and the picker tool both write the window's
active colour (CL-10).

---

## 2. Module map (each `ui/` file: responsibility + public surface)

Naming (Article III §3): **QWidget subclasses** → PascalCase + suffix
(`_View`/`_Panel`/`_Dialog`; the singular top-level shell uses the `_Window`
analog — an explicit Architecture ruling recorded here, as `QMainWindow` is the
application shell, not a reusable widget). **Non-widget classes** (QGraphicsScene,
QObject, QUndoCommand, plain controllers) → plain PascalCase, no widget suffix.
Modules are `snake_case`. Every module + public callable carries a PEP 257
docstring and PEP 484 types (Article III §4). Interface contracts are stewarded
via the `interface-contract` skill; STRUCTURE.md is the living map.

| Module | Responsibility | Public surface (Qt-in-ui only) | REQ |
| --- | --- | --- | --- |
| `ui/__init__.py` | Package marker. | — | — |
| `ui/i18n.py` | `LanguageManager(QObject)`: select language from `QLocale` (fallback English), install/swap `QTranslator` on the app, emit a signal that triggers live retranslate. | `LanguageManager(app)`, `.available_languages()`, `.current_language()`, `.set_language(code)`, `install_from_locale()`, `languageChanged` signal | 021, 022 |
| `ui/commands.py` | Qt undo bridge. `PaintCommand(QUndoCommand)` wraps a logic `PixelEdit`; `redo()/undo()` delegate to `PixelEdit.execute()/undo()` + a dirty-rect callback. **The sole Qt↔logic undo bridge.** No domain math. | `PaintCommand(pixel_edit, on_change, text)` | 009, 010 |
| `ui/canvas_scene.py` | `CanvasScene(QGraphicsScene)`: hold one `QGraphicsPixmapItem` of the active buffer (D1); `setSceneRect` once (D3); `drawBackground(painter, rect)` checker+grid over exposed rect only (D2); `NoIndex` (D7); refresh a pixel rect from the buffer. | `CanvasScene(document)`, `.set_document(doc)`, `.refresh_rect(QRectF)`, `.set_grid_enabled(bool)`, `.on_document_resized(w,h)` | 001, 002, 003, 007 |
| `ui/canvas_view.py` | `Canvas_View(QGraphicsView)`: zoom (fit…`ZOOM_MAX`, cursor-anchored, `SCALE_FACTOR` step, preset stops) (D6/CL-1/-2/-15); pan (middle/Space+left) (CL-3); left-click/drag → active tool (CL-9/-12); grid threshold `GRID_MIN_PIXEL_EDGE_PX` (CL-4); right-click → replaceable menu hook (CL-8); `MinimalViewportUpdate` (D4); dirty-rect update (D5). | `Canvas_View(scene, undo_stack)`, `.set_tool(tool)`, `.set_active_color(rgba)`, `.set_menu_hook(cb)`, `.zoom_in/out()`, `.set_zoom(z)`, `.zoom()`, `.center_on(pt)`, `zoomChanged`, `rightClicked(coord)` | 004, 005, 006, 007, 008 |
| `ui/tools/base.py` | `Tool` abstract controller: `on_press/move/release(coord, ctx)`; builds `PaintCommand` via `record_edit`; **no domain math**. | `Tool` (ABC), `ToolContext` (buffer, active_color, undo_stack, scene) | 011 |
| `ui/tools/pencil.py` | `PencilTool`: `drawing.pencil` with active colour; drag coalesces to one command. | `PencilTool(Tool)` | 011, 012 |
| `ui/tools/eraser.py` | `EraserTool`: `drawing.pencil` with the erase value (RGBA transparent / INDEXED 0). | `EraserTool(Tool)` | 011, 013 |
| `ui/tools/fill.py` | `FloodFillTool`: `drawing.flood_fill`; in-bounds no-op ⇒ no command. | `FloodFillTool(Tool)` | 011, 014 |
| `ui/tools/line.py` | `LineTool`: preview on drag (bounding-rect update only), commit `drawing.line` on release (CL-11). | `LineTool(Tool)` | 011, 015 |
| `ui/tools/picker.py` | `PickerTool`: `drawing.pick_color`; sets active colour/swatch; no mutation, no command (CL-10/-16). | `PickerTool(Tool)` | 011, 016 |
| `ui/theme.py` | Light + dark QSS themes (colours by role, never per-widget), runtime switch (CL-13). | `apply_theme(app, name)`, `available_themes()`, `THEME_LIGHT`, `THEME_DARK` | 025 |
| `ui/main_window.py` | `Main_Window(QMainWindow)` shell: tool toolbar (exclusive actions), `Palette_Panel(QWidget)` (single-select, index order), document tabs (`QTabWidget`), per-document `QUndoStack`, Undo/Redo actions bound to the active stack, menu bar (File/Edit/View), accessible names on every control (024), theme apply (025), `changeEvent` retranslate (022), New at `DEFAULT_CANVAS_*`, Open/Save via `data/project_io`. | `Main_Window()`, `.new_document()`, `.open_document(path)`, `.save_document(path)`, `.active_document()`, `Palette_Panel(palette)` | 017, 018, 019, 020, 022, 024, 025 |

`ui/tools/__init__.py` re-exports the five controllers.

---

## 3. Constitution conformance (self-check before the gate)

- **Article I:** all files under `ui/**` (+ pure `logic/constants.py`); Qt confined
  to `ui/`; verified by `check_layering` + `check_cycles`.
- **Article II:** every new numeric goes to `logic/constants.py` (T1); **no literal
  in `ui/`**. New constants: `GRID_MIN_PIXEL_EDGE_PX`, `OPENGL_VIEWPORT_ENABLED`,
  `ZOOM_MAX`, `ZOOM_PRESET_STOPS`, `DEFAULT_CANVAS_WIDTH`, `DEFAULT_CANVAS_HEIGHT`.
  **BF-3 ruling:** the geometric zoom step **reuses `SCALE_FACTOR`** (`1.0 +
  SCALE_FACTOR`), so no new step constant. Fit-to-view minimum is **computed**
  (viewport/scene ratio), not a literal ⇒ **no `ZOOM_MIN` constant** (Article II:
  add a constant only when a literal value is actually used). Core-engine §9 S12
  items (`MAX_PALETTE_SIZE`, `DEFAULT_FRAME_DURATION_MS`, `PROJECT_ZLIB_LEVEL`) are
  already centralised in `constants.py` — no further action in this slice.
- **Article III:** Black/isort/flake8/mypy; naming per §2; docstrings + types.
- **Article IV:** AGT-06 authors one pytest-qt test per acceptance criterion,
  headless offscreen, both themes; coverage gate ≥90/80.
- **Article V:** a11y names/keyboard/focus (024), both themes by role (025), all
  strings `tr()`-wrapped + `changeEvent` retranslate (022, 026).
- **Article VI:** 16 ms budget (023) verified by AGT-10 `perf_profile` post-impl.
- **Article X:** every REQ-P1-UI-* maps to ≥1 task (§ tasks.md) and traces per
  `traceability.md`.

## 4. Deferred / out of scope (unchanged from spec §6)

Right-click colour hub / favourites / RGB wheel + harmonies (Phase 3, F9);
selection/transform/symmetry (Phase 2); blend-mode/layer UI (Phase 4); animation
(Phase 5); export (Phase 7); cloud sync (Phase 10). Phase 1 ships only the
right-click **seam** (008).

## 5. Status

- HOW fixed over the approved spec; BF-1/BF-2/BF-3 resolved (§1.2, §3).
- Module map (§2) + constant additions (§3) defined; STRUCTURE.md updated.
- Feeds `sdd-tasks` (`tasks.md`) then `sdd-analyze` (C1 gate).
- **STATUS: COMPLETED.**
</content>
</invoke>
