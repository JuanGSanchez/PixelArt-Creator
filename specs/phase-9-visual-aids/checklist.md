# Quality Checklist — Phase 9: Visual Aids & UX

Run by AGT-06 (QA/accessibility) via `sdd-checklist`. Gate: `spec.md` with acceptance
criteria exists (PASS). One item per REQ-ID/acceptance criterion + cross-cutting gates,
each with objective evidence and a PASS/FAIL. Ship verdict is PASS only if every item
passes; an S1/S2 failure is a hard HOLD.

**Verdict: SHIP-READY.** 0 failing items, 0 S1/S2 defects. UI suite green in BOTH themes;
logic + data suites green; ui coverage gate green.

Environment: `QT_QPA_PLATFORM=offscreen`, Python 3.13, PySide6. Evidence captured
2026-07-04.

## Cross-cutting gates

| Gate | Threshold | Evidence | Result |
| --- | --- | --- | --- |
| UI coverage (Phase-9 additions) | ≥90% line / ≥80% branch | `coverage_gate.py` → `pixelart_creator.ui` **97.33% line / 87.96% branch**, exit 0 | PASS |
| Both themes | every UI scenario ×light/dark | autouse `theme` fixture (conftest) — 162 UI tests each run light+dark | PASS |
| a11y | names/roles, keyboard, focus | `test_aids_a11y.py` (6 tests) + `a11y-audit` findings below | PASS |
| xdist teardown (segfault class) | no live worker survives teardown | 114 aid tests green under `pytest -n auto`; aids own no worker threads | PASS |
| i18n | no bare user-visible literal | all 7 aid modules tr()-wrap + `changeEvent` retranslate; `test_aids_i18n.py` — **AGT-07 `string_audit_check` is the authoritative gate** | PASS (behavioural) |
| Frame budget (REQ-P9-UI-011) | ≤16 ms render loop | AGT-10 profiling report (722 ms→0.001 ms LOD-skipped, 3.97 ms densest FHD); LOD paint-skip verified `test_iso_grid_overlay.py` | PASS |

> OUT OF SCOPE per orchestrator: the 8K-*viewport* iso-grid 125 ms CPU-raster-fallback
> measurement — DEFERRED to Phase 12 as FU-P9-OVERLAY-8K. Not a Phase-9 ship blocker.

## UI requirements (AGT-06, pytest-qt, both themes)

| REQ | Scenario | Evidence (test) | Result |
| --- | --- | --- | --- |
| REQ-P9-UI-001 | SC-UI-001-1 | `test_preview_window.py::test_sc_ui_001_1_applies_logic_scale_exactly` + `_no_double_dpr_scaling` + `_rescales_on_ppi_change` + `_read_only_view_never_edits` | PASS |
| REQ-P9-UI-002 | SC-UI-002-1 | `test_preview_window.py::..._preview_observes_the_shared_scene` / `..._edit_mirrors_live_no_manual_refresh` / `..._viewing_preview_never_mutates_document` | PASS |
| REQ-P9-UI-003 | SC-UI-003-1 | `test_guides_rulers.py` (snap delegates to logic; ruler readout from logic; drag-creates-guide; toggle) | PASS |
| REQ-P9-UI-004 | SC-UI-004-1 | `test_iso_grid_overlay.py` (snap delegates to `iso_snap_vertex`; deterministic; config reroute) | PASS |
| REQ-P9-UI-005 | SC-UI-005-1 | `test_perspective_grid_overlay.py` (snap within tolerance / no-snap beyond / deterministic / renders) | PASS |
| REQ-P9-UI-006 | SC-UI-006-1 | `test_reference_board.py` (add / bad-image / round-trip / malformed / unknown-version / own-scene) + `test_aids_edges.py` (cap / dialogs / errors) | PASS |
| REQ-P9-UI-007 | SC-UI-007-1 | `test_multi_view.py` (shared scene / MAX_DOCUMENT_VIEWS cap / independent zoom) | PASS |
| REQ-P9-UI-008 | SC-UI-008-1 | `test_multi_view.py::..._edit_syncs_across_views_via_shared_scene` / `..._set_scene_rebinds_all_views` | PASS |
| REQ-P9-UI-009 | SC-UI-009-1 | `test_timelapse_controls.py` (per-forward-command record / undo-no-record / no-undo-push / round-trip+replay / malformed / reset) | PASS |
| REQ-P9-UI-010 | SC-UI-010-1 | `test_aids_non_destructive.py` (enabling every aid keeps undo stack clean + buffer unchanged; overlays are view state) | PASS |
| REQ-P9-UI-011 (NFR) | SC-UI-011-1 | AGT-10 `perf_profile` report; LOD paint-skip `test_iso_grid_overlay.py` (0 draws below gate, cull to exposedRect) | PASS |
| REQ-P9-UI-012 (NFR) | SC-UI-012-1 | `test_aids_a11y.py` (menu labels, preview/board/timelapse/ruler accessible names+descriptions, :focus QSS) | PASS |
| REQ-P9-UI-013 (NFR) | SC-UI-013-1 | `test_aids_theme.py` (overlay colours = theme grid role; light≠dark; reapply repushes) + autouse both-theme run | PASS |
| REQ-P9-UI-014 (NFR) | SC-UI-014-1 | `test_aids_i18n.py` (retranslate on LanguageChange) + tr()-wrapping in all 7 modules; AGT-07 `string_audit_check` authoritative | PASS |

## LOGIC requirements (AGT-04, pytest + Hypothesis, headless) — consumed as QA input

| REQ | Scenario | Evidence | Result |
| --- | --- | --- | --- |
| REQ-P9-LOGIC-001 | SC-L001-1 | `tests/logic/test_grids.py` (invertible iso transform) | PASS |
| REQ-P9-LOGIC-002 | SC-L002-1 | `tests/logic/test_grids.py` (snap → nearest vertex, tie-break) | PASS |
| REQ-P9-LOGIC-003 | SC-L003-1 | `tests/logic/test_grids.py` (deterministic guide-line construction) | PASS |
| REQ-P9-LOGIC-004 | SC-L004-1 | `tests/logic/test_grids.py` (nearest-guide-within-tolerance snap / no snap) | PASS |
| REQ-P9-LOGIC-005 | SC-L005-1 | `tests/logic/test_guides.py` (guide snap within tolerance) | PASS |
| REQ-P9-LOGIC-006 | SC-L006-1 | `tests/logic/test_guides.py` (ruler ticks + coordinate readout, pure) | PASS |
| REQ-P9-LOGIC-007 | SC-L007-1 | `tests/logic/test_preview.py` (`real_size_scale = f(PPI, DPI)`, deterministic) | PASS |
| REQ-P9-LOGIC-008 | SC-L008-1 | `tests/logic/` SC-L008 tags (Qt-free / no event loop) | PASS |
| REQ-P9-LOGIC-009 | SC-L009-1 | `tests/logic/` SC-L009 tags (determinism; no time/random/locale) | PASS |
| REQ-P9-LOGIC-010 | SC-L010-1 | `tests/logic/test_timelapse.py` + `tests/data/test_timelapse_io.py` (reproducible replay; round-trip) | PASS |
| REQ-P9-LOGIC-011 | SC-L011-1 | `tests/logic/` SC-L011 tags (bounds from constants enforced) | PASS |
| REQ-P9-LOGIC-012 | SC-L012-1 | `tests/logic/` SC-L012 tags (one shared Document is source of truth; no per-view copy) + UI corroboration `test_multi_view.py` | PASS |

> Note: the traceability matrix named a forward `tests/logic/test_document_views.py` for
> SC-L012-1; AGT-04 realised SC-L012-1 within the existing logic modules (17 SC-L012
> assertions present). The acceptance criterion is covered — a module-naming variance
> only, not a coverage gap.

## DATA requirements (AGT-04) — consumed as QA input

| REQ | Scenario | Evidence | Result |
| --- | --- | --- | --- |
| REQ-P9-DATA-001 | SC-L010-1 | `tests/data/test_timelapse_io.py` (defensive eval-free load; malformed/unknown-version → `TimelapseIOError`; round-trip) | PASS |
| REQ-P9-DATA-002 | SC-UI-006-1 | `tests/data/test_reference_board_io.py` (defensive eval-free load; malformed → `ReferenceBoardIOError`; non-destructive round-trip) | PASS |
| Document PPI / `.pixproj` v5 (BF-3) | — | `tests/data/test_project_io_v5_ppi.py` (schema extension, `FORMAT_VERSION=5`, `Document.ppi`) | PASS |

## Test-run evidence

- UI (AGT-06 Phase-9 modules): **162 passed** (both themes), 0 failed — headless.
- UI segfault-class check: **114 passed under `pytest -n auto`**, no worker crash.
- LOGIC + DATA (AGT-04 Phase-9 modules): **206 passed**, 0 failed — headless.
- Coverage gate: `pixelart_creator.ui` **97.33% line / 87.96% branch** (≥90/80), exit 0.

## Decision points

- CK-D1: every item has passing evidence → **Branch A: SHIP-READY.**
- CK-D2: no failing item, so no S1/S2 HOLD; no GitHub issue requested.

## Verdict

**SHIP-READY** — hand back to AGT-06 / orchestrator ship gate. Proceed to docs (AGT-08).
