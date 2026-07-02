# Tasks — Phase 1 (UI Increment): `phase-1-ui-canvas`

| Field | Value |
| --- | --- |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Source | `plan.md` (HOW) over approved `spec.md` (REQ-P1-UI-001..026) + `render-strategy.md` (D1–D7) |
| SDD phase | `tasks` → consumed by `sdd-analyze` (C1 gate) then orchestrator dispatch |
| Mode | FORWARD / pre-implementation — no `ui/` code exists yet |

Dependency-ordered. Each task: **id · owner · target file(s) · REQ / acceptance link ·
predecessor**. All `ui/` widgets bind to the shipped Qt-free `logic/`+`data/` API and add
**zero** domain logic (Article I). All tests run headless (`QT_QPA_PLATFORM=offscreen`),
both themes (Article IV/V). Commits are AGT-09, gate-green, REQ-tagged (Article IX).

---

## Ordered tasks

### T1 — Add UI tuning constants (the ONLY logic-layer task in this slice)
- **Owner:** AGT-03 (Python Dev) · skill `logic-scaffold`
- **File:** `pixelart_creator/logic/constants.py`
- **Do:** add, pure-Python, **zero Qt** (Article II) —
  - `GRID_MIN_PIXEL_EDGE_PX = 8` (render-strategy §10; CL-4)
  - `OPENGL_VIEWPORT_ENABLED = True` (render-strategy §10; D6)
  - `ZOOM_MAX = 64.0` (6400 % deep-zoom ceiling; CL-1)
  - `ZOOM_PRESET_STOPS = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)` (keyboard preset stops 100..6400 %; CL-2)
  - `DEFAULT_CANVAS_WIDTH = 64`, `DEFAULT_CANVAS_HEIGHT = 64` (CL-7)
  - **Reuse** existing `SCALE_FACTOR` (0.15) for the geometric zoom step (`1.0 + SCALE_FACTOR`) — **no** new step constant (BF-3). **No** `ZOOM_MIN` (fit-to-view is computed, not a literal). **No** `BSP_TREE_DEPTH` (D7 auto/NoIndex).
- **REQ / acceptance:** enables REQ-P1-UI-004, -007, -020, -023 (Article II single-source).
- **Predecessor:** none.

### T2 — LanguageManager + ui package
- **Owner:** AGT-05 (UI Expert) · skills `ts-qm-build`, `widget-scaffold`
- **Files:** `pixelart_creator/ui/__init__.py`, `pixelart_creator/ui/i18n.py`
- **Do:** `LanguageManager(QObject)` — select from `QLocale` (fallback English, CL-14), install/swap `QTranslator`, emit `languageChanged` to drive live retranslate (F5/F6).
- **REQ / acceptance:** REQ-P1-UI-021 (SC-UI-021-1), REQ-P1-UI-022 (SC-UI-022-1).
- **Predecessor:** none.

### T3 — QUndoCommand bridge + QUndoStack wiring
- **Owner:** AGT-05 · skill `reversible-op` (consumes logic pattern)
- **File:** `pixelart_creator/ui/commands.py`
- **Do:** `PaintCommand(QUndoCommand)` wrapping a logic `PixelEdit`; `redo()/undo()` delegate to `PixelEdit.execute()/undo()` + a dirty-rect callback (D5). No domain math — the sole Qt↔logic undo bridge. Binds shipped `logic/history` (`PixelEdit`, `record_edit`, `History`).
- **REQ / acceptance:** REQ-P1-UI-009 (SC-UI-009-1), REQ-P1-UI-010 (SC-UI-010-1..3).
- **Predecessor:** none (binds shipped `logic/history.py`).

### T4 — Canvas scene (render pipeline D1/D2/D3/D7)
- **Owner:** AGT-05 · skill `canvas-view`
- **File:** `pixelart_creator/ui/canvas_scene.py`
- **Do:** `CanvasScene(QGraphicsScene)` — one whole-buffer `QGraphicsPixmapItem`, NN, AA off (D1); `setSceneRect(0,0,W,H)` once + on resize (D3); `drawBackground(painter, rect)` checker + optional per-pixel grid (≥ `GRID_MIN_PIXEL_EDGE_PX`) over the exposed rect only, tiled `TILE_SIZE`/`TILE_BUFFER` (D2); `setItemIndexMethod(NoIndex)` (D7); role-based colours (025); `refresh_rect` for dirty updates.
- **REQ / acceptance:** REQ-P1-UI-001 (SC-UI-001-1/-2), -002 (SC-UI-002-1/-2), -003 (SC-UI-003-1/-2), -007 (grid draw, SC-UI-007-1/-2).
- **Predecessor:** T1.

### T5 — Canvas view (navigation/paint/seam D4/D5/D6)
- **Owner:** AGT-05 · skill `canvas-view`
- **File:** `pixelart_creator/ui/canvas_view.py`
- **Do:** `Canvas_View(QGraphicsView)` — zoom fit…`ZOOM_MAX`, cursor-anchored, `SCALE_FACTOR` step, `ZOOM_PRESET_STOPS` keyboard (CL-1/-2/-15); pan middle-drag + Space+left-drag, no paint (CL-3); left-click/drag → active tool, floored coord, off-buffer no-op (CL-9/-12); grid threshold (CL-4); right-click → replaceable menu hook, placeholder (CL-8); `MinimalViewportUpdate` (D4); dirty-rect `item.update` (D5); `QOpenGLWidget` viewport gated by `OPENGL_VIEWPORT_ENABLED` + raster fallback (D6).
- **REQ / acceptance:** REQ-P1-UI-004 (SC-UI-004-1/-2), -005 (SC-UI-005-1/-2), -006 (SC-UI-006-1..3), -007 (SC-UI-007-2/-3), -008 (SC-UI-008-1/-2).
- **Predecessor:** T1, T3, T4.

### T6 — Tool controllers (five)
- **Owner:** AGT-05 · skill `widget-scaffold`
- **Files:** `pixelart_creator/ui/tools/__init__.py`, `base.py`, `pencil.py`, `eraser.py`, `fill.py`, `line.py`, `picker.py`
- **Do:** `Tool` ABC + `PencilTool`/`EraserTool`/`FloodFillTool`/`LineTool`/`PickerTool`. Each maps events → floored coord → a `logic/drawing.py` primitive via `record_edit`, wraps a `PaintCommand`, pushes one command per stroke (CL-9/-11); picker sets active colour, no mutation/no command (CL-10). **No domain math** in controllers (Article I).
- **REQ / acceptance:** REQ-P1-UI-011 (SC-UI-011-1), -012 (SC-UI-012-1), -013 (SC-UI-013-1), -014 (SC-UI-014-1/-2), -015 (SC-UI-015-1), -016 (SC-UI-016-1).
- **Predecessor:** T3, T5.

### T7 — Themes (light + dark, QSS by role)
- **Owner:** AGT-05 · skill `qss-theming`
- **File:** `pixelart_creator/ui/theme.py`
- **Do:** matched light + dark QSS, colours defined once by role (never per-widget), runtime switch; default OS/light (CL-13). Canvas checker/grid roles legible in both.
- **REQ / acceptance:** REQ-P1-UI-025 (SC-UI-025-1).
- **Predecessor:** T2.

### T8 — Main window shell (toolbar / palette / tabs / actions / menu)
- **Owner:** AGT-05 · skills `widget-scaffold`, `colour-hub` (seam only)
- **File:** `pixelart_creator/ui/main_window.py`
- **Do:** `Main_Window(QMainWindow)` — exclusive tool toolbar (017); `Palette_Panel(QWidget)` single-select in index order, sets active colour (018/CL-6); document tabs, per-doc `QUndoStack`, tab-switch swaps active context (020/SC-UI-020-3); Undo/Redo actions bound to active stack, enable-state from `canUndo/canRedo` (019); menu bar File(New/Open/Save/Save As/Close)/Edit(Undo/Redo)/View(zoom, grid) (019); New at `DEFAULT_CANVAS_*`, 8K supported, Open/Save via `data/project_io` (020); accessible names on every control (024); apply theme (025); `changeEvent` retranslate (022).
- **REQ / acceptance:** REQ-P1-UI-017 (SC-UI-017-1), -018 (SC-UI-018-1/-2), -019 (SC-UI-019-1), -020 (SC-UI-020-1..3); + -022, -024, -025 cross-cutting.
- **Predecessor:** T2, T3, T5, T6, T7.

### T9 — pytest-qt UI tests (one per acceptance criterion, both themes, a11y)
- **Owner:** AGT-06 (QA Expert) · skills `pytest-qt-harness`, `a11y-audit`, `sdd-checklist`
- **Files:** `tests/ui/**` (one `test_*` per SC-UI-* scenario; `conftest.py`)
- **Do:** one pytest-qt test per acceptance criterion (SC-UI-001..022), headless offscreen, each run under **both** light and dark themes; a11y audit (accessible names, keyboard reachability, visible focus). Coverage gate ≥90/80.
- **REQ / acceptance:** REQ-P1-UI-024 (SC-UI-024-1/-2), -025 (SC-UI-025-1 + every scenario both themes); coverage for 001..022.
- **Predecessor:** T1–T8.

### T10 — String audit + `.ts` extraction
- **Owner:** AGT-07 (Localisation) · skills `string-extract`, `ts-qm-build`
- **Files:** `ui/**` audit; `.ts` catalogues
- **Do:** run `string_audit_check` over the new `ui/` files (report zero unwrapped user-visible strings); extract wrapped strings with `pyside6-lupdate` into `.ts`.
- **REQ / acceptance:** REQ-P1-UI-026 (SC-UI-026-1).
- **Predecessor:** T8.

### T11 — Performance profiling (post-implementation)
- **Owner:** AGT-10 (Rendering & Performance) · skill `frame-profile`
- **Do:** run `scripts/perf_profile.py` scenarios P-A..P-D (render-strategy §9); pass criterion `median_ms ≤ FRAME_BUDGET_MS`(16); over-budget ⇒ AGT-10 optimisation directive to AGT-05, never a budget relaxation (Article VI).
- **REQ / acceptance:** REQ-P1-UI-023 (SC-UI-023-1/-2).
- **Predecessor:** T4, T5.

### T12 — Docs + ADR + changelog
- **Owner:** AGT-08 (Documenter) · skills `mkdocs-site`, `changelog` (AGT-01 `adr-author` for the D1/BF-2/BF-3 decision if promoted to an ADR)
- **Files:** `docs/**` (usage/API pages, `docs/adr/` if an ADR is cut, `docs/CHANGELOG.md` Unreleased)
- **Do:** document the UI slice; capture the single-item-canvas + zoom-constant decisions as an ADR under `docs/adr/`; add Unreleased changelog entries keyed to REQ-IDs.
- **Predecessor:** T8, T9.

### T13 — Commit (Conventional, REQ-tagged, gate-green)
- **Owner:** AGT-09 (GitHub/DevOps) · skills `ci-author`, `release`
- **Do:** stage the slice as Conventional Commits carrying REQ-P1-UI-* ids; each commit leaves quality (III), tests+coverage (IV), layering (I), and the SDD gate (VIII) green.
- **Predecessor:** T1–T12 (post-verification).

---

## REQ → task coverage matrix (every REQ maps to ≥1 task)

| REQ-ID | Task(s) | REQ-ID | Task(s) |
| --- | --- | --- | --- |
| REQ-P1-UI-001 | T4 | REQ-P1-UI-014 | T6 |
| REQ-P1-UI-002 | T4 | REQ-P1-UI-015 | T6 |
| REQ-P1-UI-003 | T4 | REQ-P1-UI-016 | T6 |
| REQ-P1-UI-004 | T1, T5 | REQ-P1-UI-017 | T8 |
| REQ-P1-UI-005 | T5 | REQ-P1-UI-018 | T8 |
| REQ-P1-UI-006 | T5 | REQ-P1-UI-019 | T8 |
| REQ-P1-UI-007 | T1, T4, T5 | REQ-P1-UI-020 | T1, T8 |
| REQ-P1-UI-008 | T5 | REQ-P1-UI-021 | T2 |
| REQ-P1-UI-009 | T3 | REQ-P1-UI-022 | T2, T8 |
| REQ-P1-UI-010 | T3 | REQ-P1-UI-023 | T4, T5, T11 |
| REQ-P1-UI-011 | T6 | REQ-P1-UI-024 | T8, T9 |
| REQ-P1-UI-012 | T6 | REQ-P1-UI-025 | T7, T9 |
| REQ-P1-UI-013 | T6 | REQ-P1-UI-026 | T10 |

**26 / 26 REQ-IDs mapped to ≥1 task. 0 uncovered.**

## Status
- 13 dependency-ordered tasks; one logic-layer task (T1, Article II), the rest `ui/`
  + verification/docs/commit. Every REQ-P1-UI-* maps to ≥1 task.
- Feeds `sdd-analyze` (C1 gate).
- **STATUS: COMPLETED.**
</content>
