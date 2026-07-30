# Tasks — Phase 9: Visual Aids & UX

| Field | Value |
| --- | --- |
| Feature | `phase-9-visual-aids` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-04 |
| Over | `plan.md` (Slices 9A iso+perspective geometry → 9B guides/rulers+real-size+PPI → 9C timelapse model → 9D purity/determinism/single-source → 9E persistence → 9F preview+overlays UI → 9G reference board+multi-view+timelapse UI → 9H render performance) |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII); each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table (AGT-03 logic/data code,
AGT-04 logic/data tests, AGT-05 UI code, AGT-06 UI/a11y tests, AGT-07 string audit, AGT-10 perf,
AGT-08 docs, AGT-09 pyproject/CI/commits, AGT-01 architecture/analyze). One owner per task;
deterministic sub-steps name their script. Every REQ maps to ≥1 impl + ≥1 test/verify task. The
**10 `[GEO]`** tested-geometry scenarios (SC-L001..010) each get a dedicated geometry/property test.

---

## Slice 9A — isometric + perspective geometry (`constants.py`, `grids.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9A-01 | Add the 10 Phase-9 numerics (`DEFAULT_ISO_GRID_RATIO=2.0`, `DEFAULT_SNAP_TOLERANCE_PX=8`, `MIN_GRID_SPACING=2`, `MAX_GRID_SPACING=1024`, `MAX_GUIDES=256`, `MAX_PERSPECTIVE_VANISHING_POINTS=3`, `MAX_REFERENCE_IMAGES=256`, `MAX_TIMELAPSE_FRAMES=4096`, `MAX_DOCUMENT_VIEWS=8`, `DEFAULT_DOCUMENT_PPI=72.0`) with citations. **Names DISTINCT from every shipped constant (BF-1).** | AGT-03 | `logic/constants.py` | — | LOGIC-011 / SC-L011-1 / plan §8 | todo |
| T9A-02 | `logic/grids.py` (new): `IsoGridConfig`; `iso_world_to_screen`/`iso_screen_to_world` — diamond 2:1-dimetric invertible transform (`w=W/2`, `h=w/ratio`; origin-parametric); clamp `tile_width` to `[MIN_GRID_SPACING, MAX_GRID_SPACING]`; `GridError`. Zero Qt. | AGT-03 | `logic/grids.py` | T9A-01 | LOGIC-001, 008 / SC-L001-1 [GEO] | todo |
| T9A-03 | `iso_snap_vertex` — nearest lattice vertex via round-half-up `floor(v+0.5)` on `(i,j)` → reproject; deterministic tie-break. Pure, unit-testable. | AGT-03 | `logic/grids.py` | T9A-02 | LOGIC-002, 009 / SC-L002-1 [GEO] | todo |
| T9A-04 | `VanishingPoint`/`PerspectiveConfig`/`GuideLine`; `perspective_guide_lines(config, samples)` — deterministic fan-of-segments construction per VP (axis-lock pseudo-VPs at infinity); `MAX_PERSPECTIVE_VANISHING_POINTS`. Zero Qt. | AGT-03 | `logic/grids.py` | T9A-01 | LOGIC-003, 011 / SC-L003-1 [GEO] | todo |
| T9A-05 | `perspective_snap(sx, sy, anchor, config, tolerance)` — direction-lock: per VP `d=norm(V-anchor)` (or fixed dir), `proj=anchor+dot·d`, `err=|…|`; nearest `proj` if `min err<=tolerance` else `None`; lowest-index tie-break; skip degenerate `anchor==V`. Pure. | AGT-03 | `logic/grids.py` | T9A-04 | LOGIC-004, 009 / SC-L004-1 [GEO] | todo |
| T9A-06 | Unit + property tests (headless): iso transform round-trips on lattice points [GEO]; `iso_snap_vertex` → nearest vertex + deterministic tie-break + idempotent [GEO]; perspective construction deterministic from config [GEO]; `perspective_snap` → nearest guide within tolerance, `None` beyond, lowest-index tie-break [GEO]; determinism (no time/random/locale) via Hypothesis; grid-spacing + VP bounds from constants → `GridError`. | AGT-04 | `tests/logic/test_grids.py` | T9A-05 | LOGIC-001, 002, 003, 004, 008, 009, 011 / SC-L001-1, L002-1, L003-1, L004-1, L009-1, L011-1 | todo |

## Slice 9B — guides/rulers + real-size scale + document PPI (`guides.py`, `preview.py`, `document.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9B-01 | `logic/guides.py` (new): `GuideOrientation` (module-local), `Guide`; `screen_tolerance_to_doc(tol_px, zoom)=tol_px/zoom`; `snap_guides(x, y, guides, tol_doc)` — per-axis nearest guide within tolerance (ascending-position order; equal-distance → lowest position; unchanged if none); `MAX_GUIDES` → `GuideError`. Zero Qt. | AGT-03 | `logic/guides.py` | T9A-01 | LOGIC-005, 008, 011 / SC-L005-1 [GEO] | todo |
| T9B-02 | `ruler_ticks(doc_length, zoom, offset, *, axis_pixels)` — nice-number `{1,2,5}·10ⁿ` ladder (smallest step with `step*zoom>=min label spacing`); locale-independent integer labels; `coordinate_readout(sx, sy, zoom, offset)`. Pure of the view params. | AGT-03 | `logic/guides.py` | T9B-01 | LOGIC-006, 009 / SC-L006-1 [GEO] | todo |
| T9B-03 | `logic/preview.py` (new): `real_size_scale(doc_ppi, screen_dpi)=screen_dpi/doc_ppi` — pure, deterministic; **no DPR math**; `doc_ppi<=0`/`screen_dpi<=0` → `PreviewError`. Zero Qt. | AGT-03 | `logic/preview.py` | T9A-01 | LOGIC-007, 008, 009 / SC-L007-1 [GEO] | todo |
| T9B-04 | `logic/document.py` (extend): add first-class `ppi: float` (`__slots__`+`__init__`, keyword-only, default `DEFAULT_DOCUMENT_PPI`, validated `>0`/finite → `DocumentError`) for real-size (BF-3). No other change; the shared-document single-source invariant is unchanged. | AGT-03 | `logic/document.py` | T9A-01 | LOGIC-007, 012 / SC-L012-1 | todo |
| T9B-05 | Unit + property tests (headless): guide snap → nearest within tolerance, none beyond, lowest-position tie-break [GEO]; `screen_tolerance_to_doc` = px÷zoom; ruler ticks + readout pure of view params, locale-independent labels [GEO]; `real_size_scale` = screen_dpi/doc_ppi + determinism + `PreviewError` on non-positive [GEO]; `Document.ppi` default = `DEFAULT_DOCUMENT_PPI` + validation; bounds from constants. | AGT-04 | `tests/logic/test_guides.py`, `tests/logic/test_preview.py`, `tests/logic/test_document_ppi.py` | T9B-04 | LOGIC-005, 006, 007, 008, 009, 011, 012 / SC-L005-1, L006-1, L007-1, L009-1 | todo |

## Slice 9C — reproducible timelapse model (`timelapse.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9C-01 | `logic/timelapse.py` (new): `TimelapseFrame(index, command_id)`, `TimelapseSession(schema_version, frames)` (module-local `schema_version`); `record_frame(session, command_id)` — per-committed-command cadence; `> MAX_TIMELAPSE_FRAMES` → `TimelapseError`; pure (returns new session). Zero Qt. | AGT-03 | `logic/timelapse.py` | T9A-01 | LOGIC-010, 011 / SC-L010-1 [GEO] | todo |
| T9C-02 | `replay(session, document, renderer)` — deterministic: reconstruct each recorded state over the HIS-1 history and render via `renderer` (`composite_stack`, CO-4); same session → same frame sequence twice; **no wall-clock/random/locale**. | AGT-03 | `logic/timelapse.py` | T9C-01 | LOGIC-010, 009 / SC-L010-1, L009-1 [GEO] | todo |
| T9C-03 | Unit + property tests (headless): `record_frame` appends one frame per command + `MAX_TIMELAPSE_FRAMES` bound; `replay` twice → identical frame sequence for a fixed recorded session [GEO]; determinism (no time/random/locale) [GEO]; derives frames from the deterministic history (HIS-1) not screen state. | AGT-04 | `tests/logic/test_timelapse.py` | T9C-02 | LOGIC-009, 010, 011 / SC-L009-1, L010-1 | todo |

## Slice 9D — purity / determinism / single-source proof (logic) — gate

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9D-01 | Run `python scripts/check_layering.py` + `python scripts/check_cycles.py`; confirm `grids`/`guides`/`preview` pure leaves over `constants`, `timelapse → {document, blend, history, constants}`, all Qt-free, **no `logic → data`** edge, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T9C-02 | LOGIC-008 / Article I / plan §11 / SC-L008-1 [GEO] | todo |
| T9D-02 | Tests (headless): the whole snap/geometry/scale/timelapse engine imports **no Qt** (source scan across `grids`/`guides`/`preview`/`timelapse`) and runs with **no GUI/event loop** [GEO]; one shared `Document` is the source of truth for all views + the preview — no per-view pixel copy (SC-L012-1). | AGT-04 | `tests/logic/test_visual_aids_purity.py`, `tests/logic/test_document_views.py` | T9D-01 | LOGIC-008, 009, 012 / SC-L008-1, L009-1, L012-1 | todo |

## Slice 9E — persistence (`data/timelapse_io.py`, `data/reference_board_io.py`, `.pixproj` v5) — Qt-free (DEP-4)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9E-01 | `data/timelapse_io.py` (new): `TimelapseIOError(ProjectIOError)`; `save_session`/`load_session` — defensive `eval`-free (de)serialise of the `.pixtimelapse` manifest (`schema_version` + `{index, command_id}`, **not** inline pixels) via IO-3 (type/bounds-check; malformed/unknown-version → `TimelapseIOError`; **never `eval`/`exec`**); portable paths; round-trip → **identical replay**. Zero Qt. | AGT-03 | `data/timelapse_io.py` | T9C-02 | DATA-001 / SC-L010-1 (persist clause of LOGIC-010) | todo |
| T9E-02 | `data/reference_board_io.py` (new): `ReferenceBoardIOError(ProjectIOError)`; `ReferenceImageEntry`/`ReferenceBoardLayout` (pure dataclasses, no Qt); `save_board`/`load_board` — defensive `eval`-free (de)serialise of the `.pixboard` layout (`schema_version` + pan/zoom + `{image path-or-embedded, transform, crop, z_order}` ≤ `MAX_REFERENCE_IMAGES`) via IO-3 (malformed → `ReferenceBoardIOError` user-facing; **never `eval`/`exec`**); portable paths; non-destructive round-trip. Zero Qt. | AGT-03 | `data/reference_board_io.py` | T9A-01 | DATA-002 / SC-UI-006-1 (persist clause of UI-006) | todo |
| T9E-03 | `data/project_io.py` (extend): `.pixproj` **v5** — persist `Document.ppi`; **v1–v4 load unchanged** (absent → `DEFAULT_DOCUMENT_PPI`); out-of-range → `ProjectIOError`; `_SUPPORTED_VERSIONS` += 5. | AGT-03 | `data/project_io.py` | T9B-04 | LOGIC-007 (PPI persist) | todo |
| T9E-04 | Tests (headless): timelapse save→reload defensive (malformed/unknown-version → `TimelapseIOError`, no `eval`/`exec`) + round-trip → identical replay; reference-board save→reload defensive (malformed → `ReferenceBoardIOError`) + non-destructive round-trip; `.pixproj` v5 round-trips `ppi` **and v1–v4 fixtures load byte-for-byte unchanged** with default PPI (regression); `path_portability_check` over the new `data/` paths. | AGT-04 | `tests/data/test_timelapse_io.py`, `tests/data/test_reference_board_io.py`, `tests/data/test_project_io_v5_ppi.py` | T9E-03 | DATA-001, DATA-002, LOGIC-007 / SC-L010-1, SC-UI-006-1 | todo |

## Slice 9F — preview window + overlays UI (`ui/`) — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9F-01 | `Real_Size_Preview_Window(QWidget)`: render the composited document (CO-4) at `preview.real_size_scale` (**no** scaling math of its own); mirror edits live (observes the shared document, read-only); **Qt DPI query** (`QScreen.physicalDotsPerInch()`) + **manual on-screen-ruler calibration** here; recompute on `screenChanged`; **DO NOT multiply DPR**. `tr()` + `changeEvent`. | AGT-05 | `ui/real_size_preview_window.py`, `ui/main_window.py` | T9E-03 | UI-001, 002 / SC-UI-001-1, 002-1 | todo |
| T9F-02 | `Guides_Rulers_Overlay`: create/move/remove guides; rulers show `coordinate_readout` + `ruler_ticks`; cursor snaps via `guides.snap_guides` (overlay computes **no** snap); role-based colours. `tr()` + `changeEvent`. | AGT-05 | `ui/guides_rulers_overlay.py` | T9F-01 | UI-003 / SC-UI-003-1 | todo |
| T9F-03 | `Iso_Grid_Overlay`: render iso grid from `grids.iso_world_to_screen`; snap to nearest vertex via `grids.iso_snap_vertex`; bounded spacing; `DeviceCoordinateCache`. `tr()`. | AGT-05 | `ui/iso_grid_overlay.py` | T9F-01 | UI-004 / SC-UI-004-1 | todo |
| T9F-04 | `Perspective_Grid_Overlay`: render guide lines from `grids.perspective_guide_lines`; snap to nearest guide within tolerance via `grids.perspective_snap` (no snap beyond); configurable VPs (≤ 3); `DeviceCoordinateCache`. `tr()`. | AGT-05 | `ui/perspective_grid_overlay.py` | T9F-01 | UI-005 / SC-UI-005-1 | todo |
| T9F-05 | pytest-qt tests (both themes, offscreen): preview renders composited doc at the logic-computed scale + mirrors edits live + read-only; guides/rulers show readout + snap via `logic/`; iso overlay renders + snaps to vertex; perspective overlay renders + snaps to guide within tolerance (none beyond); all overlays compute no geometry themselves. | AGT-06 | `tests/ui/test_preview_window.py`, `test_guides_rulers.py`, `test_iso_grid_overlay.py`, `test_perspective_grid_overlay.py` | T9F-04 | UI-001..005 / SC-UI-001-1..005-1 | todo |

## Slice 9G — reference board + multi-view + timelapse UI (`ui/`) — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9G-01 | `Reference_Board(QWidget)` over a **separate** `QGraphicsScene`: add/arrange(move/resize)/zoom/crop reference images (one `QGraphicsPixmapItem` each); **non-destructive** (never composites/exports/undoes); persist via `data/reference_board_io` (malformed → user-facing error, no crash/execution); `MAX_REFERENCE_IMAGES`. `tr()` + `changeEvent`. | AGT-05 | `ui/reference_board.py` | T9E-02 | UI-006 / SC-UI-006-1 | todo |
| T9G-02 | `Multi_View` controller: open extra `QGraphicsView`(s) on the **shared** document scene (≤ `MAX_DOCUMENT_VIEWS`); per-view independent zoom/pan; `scene.changed` auto-syncs content across all views + the preview; view titles `tr()`. Builds on the Phase-4 viewport system (MC-4). | AGT-05 | `ui/multi_view.py`, `ui/main_window.py` | T9F-01 | UI-007, 008 / SC-UI-007-1, 008-1 | todo |
| T9G-03 | `Timelapse_Controls(QWidget)`: start/stop recording (view/session state, **no undo**); record one frame per committed command via `timelapse.record_frame`; save/load the session via `data/timelapse_io`; failed record (unwritable path) → user-facing error. `tr()` + units + `changeEvent`. | AGT-05 | `ui/timelapse_controls.py` | T9E-01 | UI-009 / SC-UI-009-1 | todo |
| T9G-04 | Verify **non-destructive** aids: enabling a grid, creating a guide, adding a reference, opening a view, and starting recording push **no** `QUndoCommand` and leave the document + undo stack untouched (Phase 9 adds no `ui/commands.py` logic). | AGT-05 | `ui/main_window.py` (wiring) | T9G-01, T9G-02, T9G-03 | UI-010 / SC-UI-010-1 | todo |
| T9G-05 | pytest-qt tests (both themes, offscreen): reference board add/arrange/zoom + non-destructive + defensive persistence + malformed → error; multiple views of one shared document + independent zoom/pan; edit syncs across all views + preview with no manual refresh; timelapse start/stop → reproducible sequence + recording pushes no undo; enabling any aid pushes no `QUndoCommand` (document uncorrupted). | AGT-06 | `tests/ui/test_reference_board.py`, `test_multi_view.py`, `test_timelapse_controls.py`, `test_aids_non_destructive.py` | T9G-04 | UI-006..010 / SC-UI-006-1..010-1 | todo |

## Slice 9H — render performance (16 ms with overlays + multi-view) — AGT-10 owns strategy (DEP-3)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T9H-01 | Author the render/perf directive (render-strategy): cache-backed overlays (`DeviceCoordinateCache`), `MinimalViewportUpdate`, viewport tile-culling + dirty-rect partial redraw per view so the grid/guide/perspective overlays + N up-to-8K views + preview mirror hold the **16 ms `FRAME_BUDGET_MS`** (Article VI applies — per-frame render loop). **Budget never relaxed.** Grounded by a `perf_profile` measurement. | AGT-10 | perf directive → AGT-05 | T9F-04, T9G-02 | UI-011 / SC-UI-011-1 / DEP-3 | todo |
| T9H-02 | Implement the AGT-10 directive in the overlays + multi-view (cacheMode, update mode, cull/dirty-rect); no geometry math added (Article I). | AGT-05 | `ui/iso_grid_overlay.py`, `ui/perspective_grid_overlay.py`, `ui/guides_rulers_overlay.py`, `ui/multi_view.py` | T9H-01 | UI-011 / SC-UI-011-1 | todo |
| T9H-03 | Profile + verify: `perf_profile` over the overlays + multi-view on the 8K (7680×4320) canvas vs `FRAME_BUDGET_MS`; behavioural pytest-qt that overlays + multi-view render holds budget + preview/timelapse keep the UI responsive (both themes). | AGT-06 + AGT-10 | `scripts/perf_profile.py` (invoke), `tests/ui/test_aids_perf.py` | T9H-02 | UI-011 / SC-UI-011-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-9 `grids.py`/`guides.py`/`preview.py`/`timelapse.py` + `constants.py`/`document.py` extensions, the new `data/timelapse_io.py`/`reference_board_io.py` + `project_io.py` v5, and the new `ui/` visual-aids modules (marked PLANNED per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-9-visual-aids/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | Allocate + record the `REQ-P9-DATA-*` prefix in `traceability.md` (DATA-001 timelapse persistence, DATA-002 reference-board persistence), each mapped verbatim to its fixed spec contract (LOGIC-010 / UI-006). DEP-4 ratification. | AGT-01 | `specs/phase-9-visual-aids/traceability.md` | plan | DEP-4 / Article X | done |
| TG-04 | a11y audit (`a11y-audit`): accessible names/descriptions, keyboard reachability + logical tab order, visible focus on every visual-aids control (guide/ruler toggles + handles, iso/perspective grid enable + config fields, reference-board add/arrange, view-open, timelapse record/stop, preview window). | AGT-06 | `tests/ui/*` | T9F-05, T9G-05 | UI-012 / SC-UI-012-1 | todo |
| TG-05 | Both-theme render verification (role-based colours; overlay/guide colours legible over artwork) across the preview, overlays, reference board, multi-view, timelapse controls. | AGT-06 | `tests/ui/*` | T9F-05, T9G-05 | UI-013 / SC-UI-013-1 | todo |
| TG-06 | String audit (`string_audit_check`): zero unwrapped user-visible strings (grid/guide/ruler labels + tooltips, perspective config labels, reference-board labels, view titles, timelapse control text + units, dialog titles, error messages); `changeEvent` retranslate on hand-built widgets. | AGT-07 | `ui/*.py` | T9G-04 | UI-014 / SC-UI-014-1 | todo |
| TG-07 | CHANGELOG (`Unreleased`) entries for Phase-9 features tied to REQ-IDs. | AGT-08 | `docs/CHANGELOG.md` | 9A/9B/9C/9E/9F/9G done | Article IX | todo |
| TG-08 | `sdd-checklist` before ship: every REQ has a passing test; the 10 `[GEO]` geometry contracts green; reproducible-timelapse + real-size + round-trip green; both themes + a11y + i18n gates green; the 16 ms overlay+multi-view budget green. | AGT-06 | checklist report | all impl+test done | Article IV/V/VI | todo |
