# Traceability Matrix — Phase 9: `phase-9-visual-aids`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** FORWARD / PRE-IMPLEMENTATION (authored at `specify`+`clarify`, AGT-02, 2026-07-04). Every
REQ has **≥1 acceptance scenario in `spec.md §11`**; tests are **`pending`** — authored later by
AGT-04 (logic geometry, headless, incl. the first-class `[GEO]` unit + Hypothesis tests) and AGT-06
(UI, both themes) after `sdd-plan` / `sdd-tasks`. The **[GEO]** rows are the phase's defining
"tested geometry logic" contracts (ROADMAP Phase-9 "Done means") — each maps to a dedicated AGT-04
unit test. The Test id(s) column names the *expected* module + behaviour (forward).

Status legend:
- **spec'd (forward)** — has ≥1 Gherkin acceptance scenario in `spec.md §11`; test `pending`.
  (no REQ is `uncovered`: every REQ has ≥1 scenario. **0 uncovered**.)

## Logic requirements (`logic/grids.py` + `logic/guides.py` + `logic/preview.py` + `logic/timelapse.py` new; `logic/constants.py` extend)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P9-LOGIC-001 **[GEO]** | Phase-9 cap (iso grids), P2, S11, F (iso transform) | §4, §11 | SC-L001-1 | `tests/logic/test_grids.py` (documented invertible iso transform; pure) | spec'd (forward) |
| REQ-P9-LOGIC-002 **[GEO]** | **DOC-1**, Phase-9 cap (iso snap), P2, S11 | §4, §11 | SC-L002-1 | `tests/logic/test_grids.py` (snap → nearest grid vertex; deterministic tie-break) | spec'd (forward) |
| REQ-P9-LOGIC-003 **[GEO]** | Phase-9 cap (perspective grids), P2, S11, F (perspective) | §4, §11 | SC-L003-1 | `tests/logic/test_grids.py` (deterministic guide-line construction from config) | spec'd (forward) |
| REQ-P9-LOGIC-004 **[GEO]** | Phase-9 cap (perspective snap), P2, S11, F (tolerance) | §4, §11 | SC-L004-1 | `tests/logic/test_grids.py` (snap → nearest point on nearest guide within tolerance; else no snap) | spec'd (forward) |
| REQ-P9-LOGIC-005 **[GEO]** | Phase-9 cap (guides & rulers), P2, S11 | §4, §11 | SC-L005-1 | `tests/logic/test_guides.py` (guide snap → nearest guide point within tolerance) | spec'd (forward) |
| REQ-P9-LOGIC-006 **[GEO]** | Phase-9 cap (rulers), P2, S11 | §4, §11 | SC-L006-1 | `tests/logic/test_guides.py` (ruler ticks + coordinate readout are pure of view params) | spec'd (forward) |
| REQ-P9-LOGIC-007 **[GEO]** | Phase-9 cap (real-size preview), P2, S11, F (DPI scaling) | §4, §11 | SC-L007-1 | `tests/logic/test_preview.py` (real_size_scale = f(PPI, DPI); deterministic) | spec'd (forward) |
| REQ-P9-LOGIC-008 | **[GEO]** Article I, S11, Phase-9 cap | §4, §11 | SC-L008-1 | unit-testable-without-Qt is demonstrated by the pure-logic suites themselves: `test_grids.py::test_iso_world_to_screen_documented_formula`, `::test_iso_round_trip_exact_on_lattice`, `::test_perspective_guide_lines_finite_vp_count_and_endpoints`, `test_guides.py::test_ruler_ticks_deterministic`, `test_timelapse.py::test_replay_is_deterministic_same_count_and_order` (none constructs a QApplication). The Qt-free / no-event-loop half stays script-gated by `check_layering`/`check_cycles` (exit 0). | landed |
| REQ-P9-LOGIC-009 | **[GEO]** P2 (determinism), S6, S11 | §4, §11 | SC-L009-1 | `test_grids.py::test_iso_snap_half_up_tie_break_is_deterministic`, `::test_perspective_guide_lines_is_deterministic`, `::test_perspective_snap_deterministic_repeated`, `::test_perspective_snap_lowest_index_tie_break`, `::test_iso_snap_is_idempotent`, `::test_property_iso_round_trip_identity`, `::test_property_iso_snap_idempotent` (Hypothesis) + `test_guides.py::test_ruler_ticks_deterministic` + `test_timelapse.py::test_replay_is_deterministic_same_count_and_order` | landed |
| REQ-P9-LOGIC-010 **[GEO]** *(prefix flagged)* | **HIS-1** (reversible-command path), P2, Phase-9 cap (timelapse), S11 | §4, §11 | SC-L010-1 | `tests/logic/test_timelapse.py` + `tests/data/test_timelapse_io.py` (reproducible frame sequence; defensive `eval`-free load; round-trip-identical replay) | spec'd (forward) |
| REQ-P9-LOGIC-011 | Article II, Article VII, S12 | §4, §11 | SC-L011-1 | `test_grids.py::test_default_iso_ratio_is_single_sourced_from_constants`, `::test_iso_config_accepts_spacing_bounds`, `::test_iso_config_rejects_invalid`, `::test_perspective_config_rejects_too_many_vps`, `::test_perspective_snap_rejects_bad_tolerance` + `test_guides.py::test_screen_tolerance_default_constant`, `::test_screen_tolerance_rejects_invalid`, `::test_snap_guides_rejects_over_max_guides` + `test_timelapse.py::test_session_rejects_over_max_frames`, `::test_record_frame_rejects_when_at_capacity` | landed |
| REQ-P9-LOGIC-012 | **DOC-1**, **HIS-1**, Article I, Phase-9 cap (multi-view/live-mirror), S11 | §4, §11 | SC-L012-1 | `tests/logic/test_document_views.py` (one shared Document is source of truth; no per-view pixel copy) | spec'd (forward) |

## UI requirements (`ui/` preview window / overlays / reference board / multi-view / timelapse controls)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P9-UI-001 | REQ-P9-LOGIC-007 | §4, §11 | SC-UI-001-1 | `tests/ui/test_preview_window.py` (renders composited doc at logic-computed real-size scale) | spec'd (forward) |
| REQ-P9-UI-002 | REQ-P9-LOGIC-012, S7 | §4, §11 | SC-UI-002-1 | `test_preview_window.py::test_sc_ui_002_1_edit_mirrors_live_no_manual_refresh`, `::test_sc_ui_002_1_preview_observes_the_shared_scene`, `::test_sc_ui_002_1_viewing_preview_never_mutates_document`, `::test_sc_ui_001_1_read_only_view_never_edits` | landed |
| REQ-P9-UI-003 | REQ-P9-LOGIC-005, -006 | §4, §11 | SC-UI-003-1 | `tests/ui/test_guides_rulers.py` (coordinate readout; snap-to-guide via logic/) | spec'd (forward) |
| REQ-P9-UI-004 | REQ-P9-LOGIC-001, -002 | §4, §11 | SC-UI-004-1 | `tests/ui/test_iso_grid_overlay.py` (renders from transform; snap-to-vertex via logic/) | spec'd (forward) |
| REQ-P9-UI-005 | REQ-P9-LOGIC-003, -004 | §4, §11 | SC-UI-005-1 | `tests/ui/test_perspective_grid_overlay.py` (renders guide lines; snap-to-guide within tolerance) | spec'd (forward) |
| REQ-P9-UI-006 | Phase-9 cap (reference board), S6 | §4, §11 | SC-UI-006-1 | `tests/ui/test_reference_board.py` + `tests/data/test_reference_board_io.py` (add/arrange/zoom; non-destructive; defensive persistence; malformed → error) | spec'd (forward) |
| REQ-P9-UI-007 | REQ-P9-LOGIC-012, **MC-4** (Phase-4 viewport/tab system) | §4, §11 | SC-UI-007-1 | `tests/ui/test_multi_view.py` (multiple views of one shared document; independent zoom/pan) | spec'd (forward) |
| REQ-P9-UI-008 | REQ-P9-LOGIC-012, S7 | §4, §11 | SC-UI-008-1 | `test_multi_view.py::test_sc_ui_008_1_edit_syncs_across_views_via_shared_scene`, `::test_sc_ui_008_1_set_scene_rebinds_all_views`, `::test_sc_ui_007_1_open_view_shares_the_one_scene`, `::test_sc_ui_007_1_independent_zoom_per_view` (local zoom/pan stays independent) | landed |
| REQ-P9-UI-009 | REQ-P9-LOGIC-010 | §4, §11 | SC-UI-009-1 | `tests/ui/test_timelapse_controls.py` (start/stop; reproducible sequence; recording not undoable) | spec'd (forward) |
| REQ-P9-UI-010 | S7, C1, F1 | §4, §11 | SC-UI-010-1 | `tests/ui/test_aids_non_destructive.py` (no QUndoCommand for grid/guide/reference/view/recording; document untouched) | spec'd (forward) |
| REQ-P9-UI-011 (NFR) | S1, S12, Article VI, DEP-3 | §5, §11 | SC-UI-011-1 | `tests/ui/test_aids_perf.py` (overlays + multi-view hold FRAME_BUDGET_MS; preview/timelapse responsive); AGT-10 render-strategy + `perf_profile` | spec'd (forward) |
| REQ-P9-UI-012 (NFR) | Article V §1 | §5, §11 | SC-UI-012-1 | `tests/ui/test_aids_a11y.py` (accessible names / keyboard / focus); AGT-06 `a11y-audit` | spec'd (forward) |
| REQ-P9-UI-013 (NFR) | Article V §3 | §5, §11 | SC-UI-013-1 (+ every UI scenario in both themes) | both-theme `[light]`/`[dark]` fixtures across the `tests/ui/test_*` visual-aids modules | spec'd (forward) |
| REQ-P9-UI-014 (NFR) | Article V §2, F6 | §5, §11 | SC-UI-014-1 | tr()-wrapped visual-aids UI + `changeEvent` retranslate; AGT-07 `string_audit_check` | spec'd (forward) |

## DATA requirements — `REQ-P9-DATA-*` prefix ALLOCATED (DEP-4 ratified at plan time, AGT-01)

> **DEP-4 resolved (plan §12, PL9-D11; ADR-0024 §4):** because Phase 9 has **two** genuinely distinct
> data-layer persistence concerns with **distinct serialisers, formats, and test modules** (unlike
> Phase 8's single serialiser, which was folded — ADR-0022 §4), AGT-01 **allocates a `REQ-P9-DATA-*`
> prefix** — two DATA REQs. Each formalises a persistence contract **already fixed** under
> REQ-P9-LOGIC-010 / REQ-P9-UI-006, so this is a **placement/formalisation** of pre-authorised
> acceptance, **NOT acceptance-changing**. The Document-PPI persistence (`.pixproj` v5, BF-3) is a
> schema extension of the **shipped** `project_io` grounded by REQ-P9-LOGIC-007 — **not** a new
> serialiser and therefore **not** a DATA REQ (ADR-0025 §1).

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P9-DATA-001 *(formalises REQ-P9-LOGIC-010 persist clause)* | **IO-3**, **HIS-1**, P2, Article VII, ADR-0024 §4 / ADR-0025 §2 | §4 (LOGIC-010), §11 | SC-L010-1 | `tests/data/test_timelapse_io.py` (defensive `eval`-free load; malformed/unknown-version → `TimelapseIOError`; round-trip → identical replay) | spec'd (forward) |
| REQ-P9-DATA-002 *(formalises REQ-P9-UI-006 persist clause)* | **IO-3**, Article VII, ADR-0024 §4 / ADR-0025 §3 | §4 (UI-006), §11 | SC-UI-006-1 | `tests/data/test_reference_board_io.py` (defensive `eval`-free load; malformed → `ReferenceBoardIOError` user-facing; non-destructive round-trip) | spec'd (forward) |

> Both `TimelapseIOError`/`ReferenceBoardIOError` subclass `ProjectIOError` (IO-3 family). The two DATA
> REQs carry the **same** observable contracts previously phrased inside REQ-P9-LOGIC-010 (round-trip →
> identical replay) and REQ-P9-UI-006 (non-destructive defensive persistence); allocating them adds no
> new acceptance — it gives each serialiser its own layer requirement + test module.

## Coverage summary

- **28 of 28 REQ-IDs** (12 LOGIC + 14 UI + **2 DATA**, the DEP-4 allocation) have **≥1 acceptance
  scenario** in `spec.md §11` (**0 uncovered**); the 2 DATA REQs formalise the persistence clauses of
  REQ-P9-LOGIC-010 / REQ-P9-UI-006 (not acceptance-changing), so coverage is preserved: 26 base + 2
  formalised = 28. tests **`pending`** (forward). Expected test modules:
  `tests/logic/{test_grids,test_guides,test_preview,test_timelapse,test_document_views}.py`,
  `tests/data/{test_timelapse_io,test_reference_board_io}.py`, and the `tests/ui/` visual-aids modules
  (`test_preview_window,test_guides_rulers,test_iso_grid_overlay,test_perspective_grid_overlay,
  test_reference_board,test_multi_view,test_timelapse_controls,test_aids_non_destructive,test_aids_perf,
  test_aids_a11y`).
- **26 Gherkin scenarios**, including **10 first-class `[GEO]` tested-geometry scenarios**: SC-L001-1
  (invertible iso transform), SC-L002-1 (iso snap → nearest vertex), SC-L003-1 (perspective
  construction), SC-L004-1 (perspective snap → nearest guide within tolerance), SC-L005-1 (guide
  snap), SC-L006-1 (ruler ticks), SC-L007-1 (real-size scale `f(PPI, DPI)`), SC-L008-1 (Qt-free
  unit-testable engine), SC-L009-1 (determinism), SC-L010-1 (reproducible timelapse) — the ROADMAP
  Phase-9 "compute snap points from tested geometry logic" backbone.
- SDD order: specify+clarify (this) → plan (ADR expected for the geometry model — iso ratio +
  perspective config, DEP-2) → tasks → analyze → implement → test → checklist. Logic geometry tests by
  AGT-04 (headless, incl. Hypothesis for the pure snap functions), UI tests by AGT-06 (both themes).
- The NFRs: REQ-P9-UI-014 (i18n) will carry `string_audit_check` script evidence at ship;
  REQ-P9-UI-012 (a11y) an `a11y-audit`; **REQ-P9-UI-011 (performance) is bound to the 16 ms
  `FRAME_BUDGET_MS` — Article VI APPLIES this phase** (overlays + multi-view are on the per-frame
  render loop, unlike Phase-7/8 export/automation batch work) — verified via AGT-10's `perf_profile`
  + a behavioural pytest-qt assertion.

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 9 to formally reflect what it inherits forward vs. builds new:

| Inherited primitive | Origin | Phase-9 forward trace |
| --- | --- | --- |
| **DOC-1** — the `Document` tree | `logic/document.py` (Phase 1, shipped) | → REQ-P9-LOGIC-012 (one shared Document is the source of truth for all views + the preview) → REQ-P9-LOGIC-002 (grid snap over document coordinates) |
| **PB-1** — `PixelBuffer` (`.data`/`.region`) | `logic/pixel_buffer.py` (Phase 1, shipped) | → REQ-P9-UI-002 (the pixels the real-size preview mirrors) |
| **HIS-1** — `logic/history.py` `Command`/`FunctionCommand`/`History` (the reversible-command path) | `logic/history.py` (Phase 1, shipped) | → REQ-P9-LOGIC-010 (reproducible timelapse derives frames from the deterministic edit history) → REQ-P9-LOGIC-012 / REQ-P9-UI-002/-008 (an edit is one shared-document mutation that mirrors live to preview + all views) → REQ-P9-UI-010 (only HIS-1 drawing edits are undoable; aids are not) |
| **CO-4** — `blend.composite_stack` (layer-stack flatten) | `logic/blend.py` (Phase 4, shipped) | → REQ-P9-UI-001 (the preview + every view render the composited document) |
| **MC-4** — Phase-4 multiple-canvas / artboard viewport/tab system (REQ-P4-UI-014 / CL-15: each tab owns its own tree + QUndoStack + composite) | `ui/` (Phase 4, shipped) | → REQ-P9-UI-007 (multi-**view** builds on the viewport/tab infrastructure but shares **one** document — distinct from Phase-4 isolated multi-**canvas** tabs) |
| **IO-3** — `data/project_io.py` defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib`) | `data/project_io.py` (Phase 1/4, shipped) | → REQ-P9-LOGIC-010 (defensive timelapse persistence) → REQ-P9-UI-006 (defensive reference-board persistence) |

## Cross-layer trace (UI binds to new logic)

| UI REQ | Binds to logic REQ / shipped | Note |
| --- | --- | --- |
| REQ-P9-UI-001 | REQ-P9-LOGIC-007 | preview applies the pure real-size scale |
| REQ-P9-UI-002 | REQ-P9-LOGIC-012 | live mirror via the one shared document |
| REQ-P9-UI-003 | REQ-P9-LOGIC-005/-006 | guides/rulers overlay calls the pure snap + tick geometry |
| REQ-P9-UI-004 | REQ-P9-LOGIC-001/-002 | iso overlay renders the transform; snaps to vertex |
| REQ-P9-UI-005 | REQ-P9-LOGIC-003/-004 | perspective overlay renders guide lines; snaps within tolerance |
| REQ-P9-UI-006 | — (reference board) + IO-3 | non-destructive board; defensive persistence |
| REQ-P9-UI-007 | REQ-P9-LOGIC-012, MC-4 | multiple views of one shared document (builds on viewport system) |
| REQ-P9-UI-008 | REQ-P9-LOGIC-012 | edit syncs across all views + preview |
| REQ-P9-UI-009 | REQ-P9-LOGIC-010 | timelapse controls over the reproducible sequence model |
| REQ-P9-UI-010 | REQ-P9-LOGIC-012 (shared doc) | aids are non-destructive; no QUndoCommand |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher — GEOMETRY-FOCUSED).** `docs/research-phase9-visual-aids.md` grounds the
  isometric transform math (2:1 dimetric vs true-iso), perspective guide-line construction (1-/2-/3-
  point), real-size DPI/PPI scaling, snap algorithm + tolerance norms, timelapse capture strategy
  (per-command vs time-based) + encoding landscape, and the reference-board (PureRef) landscape —
  **being produced in parallel** (feeds AGT-01). AGT-01 must not invent the geometry math; the
  observable geometry contracts + clarification defaults (spec §10) are fixed regardless.
- **DEP-2 (AGT-01 / plan/ADR).** (a) iso default (2:1 dimetric vs true-iso) → `DEFAULT_ISO_GRID_RATIO`;
  (b) timelapse capture strategy + storage/encoding; (c) DPI/real-size scaling specifics; (d)
  reference-board persistence format; (e) perspective config (1-/2-/3-point defaults); (f)
  snap-tolerance defaults. Each is a HOW decision; the observable contracts (documented invertible
  transform; nearest-vertex / nearest-guide-within-tolerance snap; `f(PPI, DPI)`; live mirror; views
  in sync; reproducible timelapse) are fixed. **An ADR is expected for the geometry model (a/e)**,
  grounded by DEP-1.
- **DEP-3 (AGT-01 / AGT-10 — RENDER PERFORMANCE).** The render/perf strategy for holding the 16 ms
  `FRAME_BUDGET_MS` with the grid/guide overlays + multiple 8K views (overlay batching, viewport
  tile-culling, dirty-rect partial redraw) is an **AGT-10 render-strategy** decision; the
  worker-thread choice for long-running timelapse capture/encoding is an AGT-01/AGT-10 HOW. **Unlike
  Phases 7-8, Article VI's 16 ms budget APPLIES** — overlays + views are on the per-frame render loop
  (REQ-P9-UI-011).
- **DEP-4 (AGT-01 / orchestrator — PREFIX).** Allocate a `REQ-P9-DATA-*` prefix for the **timelapse**
  and **reference-board** serialisers at plan time (Phase 9's **two** persistence concerns make it
  more clearly warranted than Phase 8's single serialiser), or keep them folded under
  REQ-P9-LOGIC-010 / REQ-P9-UI-006. **Not acceptance-changing.**
- **BF-1 (Article II watch).** AGT-01 must place `DEFAULT_ISO_GRID_RATIO`, `DEFAULT_SNAP_TOLERANCE_PX`,
  `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`,
  `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`, `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI` in
  `logic/constants.py` (no literals); `DEFAULT_ISO_GRID_RATIO`'s **value** is the DEP-2a iso-default.
- **BF-2 (Article I watch).** All snap/geometry/scale/timelapse math must be Qt-free (`logic/`) and
  unit-testable; the overlays/preview/board/views/timelapse UI re-implement none of it
  (REQ-P9-LOGIC-008). Phase 9 adds **no** `ui/commands.py` logic (visual aids are non-destructive,
  REQ-P9-UI-010).
- **BF-3 (data-model).** Real-size scale needs a document **PPI**; if Phase-1 `Document` lacks one,
  AGT-01 adds it (defaulting to `DEFAULT_DOCUMENT_PPI`) at plan time. Not acceptance-changing
  (REQ-P9-LOGIC-007 holds regardless of the PPI source).

## Recommended slicing (logic-first vertical slices)

1. **Slice A — isometric grid geometry (logic).** REQ-P9-LOGIC-001, -002, -008, -009 (`logic/grids.py`:
   invertible transform, snap-to-vertex, purity, determinism). ADR for the iso ratio (AGT-01, DEP-2a)
   grounded by the Researcher (DEP-1). AGT-03 + AGT-04 (geometry + Hypothesis tests).
2. **Slice B — perspective grid geometry (logic).** REQ-P9-LOGIC-003, -004 (`logic/grids.py`:
   guide-line construction + snap-to-nearest-guide-within-tolerance). AGT-01 fixes the perspective
   config (DEP-2e). AGT-03 + AGT-04.
3. **Slice C — guides, rulers, real-size scale (logic).** REQ-P9-LOGIC-005, -006, -007
   (`logic/guides.py` snap + ticks; `logic/preview.py` real-size scale `f(PPI, DPI)`). AGT-01 fixes
   DPI specifics + PPI data-model (DEP-2c / BF-3). AGT-03 + AGT-04.
4. **Slice D — timelapse model + shared-source substrate (logic).** REQ-P9-LOGIC-010, -011, -012
   (`logic/timelapse.py` reproducible sequence; bounds; one-shared-document invariant). AGT-01 fixes
   the capture strategy (DEP-2b). AGT-03 + AGT-04.
5. **Slice E — persistence (data).** timelapse + reference-board serialisers (REQ-P9-LOGIC-010 /
   REQ-P9-UI-006 contracts; DEP-4 prefix). AGT-03 + AGT-04.
6. **Slice F — preview window + overlays UI.** REQ-P9-UI-001..005, -012..014. AGT-05 + AGT-06.
7. **Slice G — reference board + multi-view + timelapse UI.** REQ-P9-UI-006..010. AGT-05 + AGT-06.
8. **Slice H — render performance (16 ms budget with overlays + multi-view).** REQ-P9-UI-011
   (coordinated with AGT-10, DEP-3). AGT-05 + AGT-06 + AGT-10.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 26 REQs, 26 with scenarios, 0 uncovered; tests `pending`
  (forward). SDD order: specify+clarify (this) → plan → tasks → analyze → implement → test.
- **No open clarification** (spec §10): all 17 ambiguities resolved with grounded defaults; the iso
  default / timelapse strategy / DPI specifics / reference-board format / perspective config scope
  risks are named HOW decisions (DEP-1/DEP-2), not suspended, and every geometry/live-consistency/
  timelapse REQ is phrased around the observable contract so those choices do not change acceptance.
- **Four named dependencies** (DEP-1 Researcher geometry grounding, DEP-2 AGT-01 plan/ADR — ADR
  expected for the geometry model, DEP-3 AGT-01/AGT-10 render performance — **Article VI applies this
  phase**, DEP-4 AGT-01/orchestrator `REQ-P9-DATA-*` prefix) must be resolved/allocated before/within
  the plan — none blocks this spec.
- **Geometry-central phase:** the 10 `[GEO]` scenarios are the ROADMAP "tested geometry logic"
  backbone; each must map to a dedicated AGT-04 unit/Hypothesis test at ship. **Performance-sensitive:**
  Article VI's 16 ms budget applies to overlay + multi-view rendering (REQ-P9-UI-011), unlike the
  batch-work Phases 7-8 — coordinate with AGT-10.
- **Multi-view disambiguation (§7):** multi-**view** (many views of one shared document, in sync) is
  distinct from Phase-4 multi-**canvas** (isolated different-document tabs); multi-view builds on the
  Phase-4 viewport system (MC-4) without respecifying it. This is the central design clarification.
