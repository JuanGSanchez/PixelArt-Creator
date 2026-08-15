# Traceability Matrix — Phase 5: `phase-5-animation`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** IMPLEMENTED / pre-commit gate (`analyze` PASS, 2026-07-03). Every REQ has **≥1 acceptance
scenario** and is now covered by **≥1 shipped test** authored by **AGT-04** (logic/data: pytest +
Hypothesis) and **AGT-06** (UI: pytest-qt, both themes). The `Test id(s)` column names the on-disk
test file(s). The two script-gated NFRs (REQ-P5-UI-016 perf, REQ-P5-UI-019 string audit) carry
behavioural tests here **plus** their deferred script evidence: AGT-10 `perf_profile --animation`
(loop-backs D1/D2/D3 landed via the off-thread pre-warm; D4 deferred to Phase 12 as FU-P5-PERF) and
AGT-07 `string_audit_check`.

Status legend:
- **covered** — has ≥1 Gherkin acceptance scenario **and ≥1 shipped test**.
- (no row is `uncovered`: every REQ has ≥1 scenario + ≥1 test.)

## Logic requirements (`logic/animation.py` new + `logic/document.py` extend)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P5-LOGIC-001 | S6, Phase-5 cap | §4, §11 | SC-L001-1 | `test_animation.py` (`test_playback_mode_*`, `test_sequence_*`) | covered |
| REQ-P5-LOGIC-002 | Phase-5 cap, **F-anim (DEP-1)** | §4, §11 | SC-L002-1, SC-L002-2, SC-L002-3 | `test_animation.py` (modes + `test_sequence_is_deterministic`/`_stays_in_range` Hypothesis) | covered |
| REQ-P5-LOGIC-003 | **FR-2** (`DEFAULT_FRAME_DURATION_MS`), Art. VI | §4, §11 | SC-L003-1 | `test_animation.py` (`test_playback_steps_pairs_index_with_duration`) | covered |
| REQ-P5-LOGIC-004 | **FR-1** (`add_frame`→reversible), S7 | §4, §11 | SC-L004-1 | `test_document_frames.py` (`make_add_frame_command`) | covered |
| REQ-P5-LOGIC-005 | **FR-1** (`remove_frame`→reversible), S7 | §4, §11 | SC-L005-1, SC-L005-2 | `test_document_frames.py` (`make_remove_frame_command` + refuse-last) | covered |
| REQ-P5-LOGIC-006 | Phase-5 cap (new `move_frame`), S7 | §4, §11 | SC-L006-1 | `test_document_frames.py` (`make_move_frame_command`) | covered |
| REQ-P5-LOGIC-007 | Phase-5 cap (new `duplicate_frame`), S7 | §4, §11 | SC-L007-1 | `test_document_frames.py` (`make_duplicate_frame_command` deep-copy) | covered |
| REQ-P5-LOGIC-008 | **FR-2** (`Frame.duration_ms`), S7, Art. VII | §4, §11 | SC-L008-1 | `test_document_frames.py` (`make_set_frame_duration_command`) | covered |
| REQ-P5-LOGIC-009 | Phase-5 cap (frame tags), S6 | §4, §11 | SC-L009-1 | `test_animation.py` (`FrameTag` defaults) + `test_document_frames.py` (`make_add_tag_command`) | covered |
| REQ-P5-LOGIC-010 | Phase-5 cap (frame tags), S7 | §4, §11 | SC-L010-1, SC-L010-2 | `test_document_frames.py` (`make_edit_tag_command`/`make_remove_tag_command` + range clamp) | covered |
| REQ-P5-LOGIC-011 | Phase-5 cap (named animation), REQ-P5-LOGIC-002 | §4, §11 | SC-L011-1 | `test_animation.py::test_tag_playback_steps_uses_tag_mode_and_range`, `::test_playback_steps_subrange`, `::test_playback_steps_repeat_gives_exact_passes_for_every_mode` | covered |
| REQ-P5-LOGIC-012 | Phase-5 cap (onion), **F-anim (DEP-1)**, **CO-4** | §4, §11 | SC-L012-1, SC-L012-2 | `test_animation.py` (`test_onion_overlay_*` — tint/fade/z-order/hidden-layers) | covered |
| REQ-P5-LOGIC-013 | **CO-4** (`blend.composite_stack`→per-frame render), S7 | §4, §11 | SC-L013-1 | `test_animation.py::test_onion_overlay_honours_hidden_layers`, `::test_onion_overlay_region_passthrough`, `::test_onion_contribution_is_frozen`, `::test_onion_overlay_scales_alpha_by_opacity_and_excludes_active` (all drive `logic/animation.py` L375/L381, the two `composite_stack` call sites — CO-4 reuse, non-destructive) + `test_animation_canvas_frames.py::test_scene_cache_hit_roundtrip`, `::test_scene_indexed_doc_no_onion_no_warm` + `test_animation_timeline_wiring.py::test_composite_warm_runnable_emits` | covered |
| REQ-P5-LOGIC-014 | Art. II, Art. VII, S12 | §4, §11 | SC-L014-1, SC-L014-2 | `test_animation.py` (`test_onion_*_rejects_*_over_bound`, `test_onion_defaults_and_tints_come_from_constants`) + `test_document_frames.py` (`MAX_FRAMES`) | covered |

## UI requirements (`ui/` timeline / playback / onion / tags)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P5-UI-001 | S6, Phase-5 cap | §4, §11 | SC-UI-001-1 | `test_animation_timeline.py` (`test_ui_001_*`) + `test_animation_timeline_wiring.py` (thumbnail/markers) | covered |
| REQ-P5-UI-002 | S1, S6, Phase-5 cap | §4, §11 | SC-UI-002-1 | `test_animation_timeline.py` (`test_ui_002_scrub_updates_without_undo_entry`) + `test_animation_canvas_frames.py` (`test_scene_scrub_switch_*`) | covered |
| REQ-P5-UI-003 | REQ-P5-LOGIC-004 | §4, §11 | SC-UI-003-1 | `test_animation_timeline.py::test_ui_003_add_frame_is_one_command` | covered |
| REQ-P5-UI-004 | REQ-P5-LOGIC-005 | §4, §11 | SC-UI-004-1 | `test_animation_timeline.py::test_ui_004_remove_frame_one_command_and_refuses_last`, `test_animation_guards.py::test_timeline_remove_at_index_zero_keeps_active` | covered |
| REQ-P5-UI-005 | REQ-P5-LOGIC-006 | §4, §11 | SC-UI-005-1 | `test_animation_timeline.py::test_ui_005_reorder_frame_is_one_command`, `test_animation_timeline_wiring.py::test_timeline_guard_and_theme_branches` (no-op / invalid reorder guards) | covered |
| REQ-P5-UI-006 | REQ-P5-LOGIC-007 | §4, §11 | SC-UI-006-1 | `test_animation_timeline.py::test_ui_006_duplicate_frame_deep_copy_one_command` | covered |
| REQ-P5-UI-007 | REQ-P5-LOGIC-008, FR-2 | §4, §11 | SC-UI-007-1 | `test_animation_timeline.py::test_ui_007_duration_editor_sets_duration_one_command`, `test_animation_timeline_wiring.py::test_timeline_duration_spin_disabled_without_frames`, `test_animation_guards.py::test_timeline_duration_committed_out_of_range` | covered |
| REQ-P5-UI-008 | REQ-P5-LOGIC-002, -003 | §4, §11 | SC-UI-008-1 | `test_animation_timeline.py` (`test_ui_008_play_pause_stop_drive_frames`) + `test_animation_timeline_wiring.py` (pause/resume/stream) | covered |
| REQ-P5-UI-009 | REQ-P5-LOGIC-001 | §4, §11 | SC-UI-009-1 | `test_animation_timeline.py::test_ui_009_mode_selector_offers_four_modes_default_loop`, `::test_ui_009_modes_advance_correctly`, `::test_ui_009_once_stops_at_end` | covered |
| REQ-P5-UI-010 | REQ-P5-LOGIC-003 | §4, §11 | SC-UI-010-1 | `test_animation_timeline.py::test_ui_010_playback_honours_per_frame_duration`, `test_animation_timeline_wiring.py::test_playback_no_context_and_empty_durations` | covered |
| REQ-P5-UI-011 | REQ-P5-LOGIC-012 | §4, §11 | SC-UI-011-1 | `test_animation_timeline.py` (`test_ui_011_onion_toggle_*`) + `test_animation_canvas_frames.py` (onion refresh/suppress) | covered |
| REQ-P5-UI-012 | REQ-P5-LOGIC-012, -014 | §4, §11 | SC-UI-012-1 | `test_animation_timeline.py::test_ui_012_onion_counts_and_tint_are_view_settings`, `test_animation_timeline_wiring.py::test_onion_tint_pickers` + bounds in `tests/logic/test_animation.py::test_onion_overlay_rejects_prev_count_over_bound`, `::test_onion_overlay_rejects_next_count_over_bound`, `::test_onion_defaults_and_tints_come_from_constants` | covered |
| REQ-P5-UI-013 | REQ-P5-LOGIC-009, -010 | §4, §11 | SC-UI-013-1 | `test_animation_timeline.py` (`test_ui_013_tag_create_edit_delete_each_one_command`) + `test_animation_timeline_wiring.py` (tag dialog paths) | covered |
| REQ-P5-UI-014 | REQ-P5-LOGIC-011 | §4, §11 | SC-UI-014-1 | `test_animation_timeline.py::test_ui_014_select_tag_plays_named_animation`, `test_animation_timeline_wiring.py::test_tags_panel_dialog_paths`, `::test_tag_dialog_new_defaults` | covered |
| REQ-P5-UI-015 | S7, C1, F1, REQ-P5-LOGIC-004..010 | §4, §11 | SC-UI-015-1 | `test_animation_timeline.py` (`test_ui_015_view_ops_push_no_command` + one-command asserts in `test_ui_003..007`/`013`) | covered |
| REQ-P5-UI-016 | S1, S12, F2, F7, Art. VI, DEP-3 (NFR) | §5, §11 | SC-UI-016-1 | **cache / dirty-rect / off-thread clause only:** `test_animation.py::test_onion_overlay_region_passthrough` + `test_animation_canvas_frames.py::test_scene_cold_playback_advance_is_async`, `::test_scene_cache_hit_roundtrip`, `::test_scene_scrub_switch_suppresses_onion` + `test_animation_timeline.py::test_prewarm_derived_cache_honours_bound`, `::test_prewarm_cold_range_warms_then_ready` + `test_animation_timeline_wiring.py::test_composite_warm_runnable_emits`, `::test_frame_cache_api_branches`. **The ≤ `FRAME_BUDGET_MS` budget itself has NO assertion in the test tree** — script-gated by AGT-10 `perf_profile --animation` (D1/D2/D3 landed; D4→FU-P5-PERF), which `build_matrix` does not scan. | covered (mechanism); budget script-gated |
| REQ-P5-UI-017 (NFR) | Art. V §1 | §5, §11 | SC-UI-017-1 | `test_animation_timeline.py` (`test_ui_017_*` — accessible names/keyboard/focus) | covered |
| REQ-P5-UI-018 (NFR) | Art. V §3 | §5, §11 | SC-UI-018-1 (+ every UI scenario in both themes) | `test_animation_timeline.py` (both-theme fixtures) + `test_animation_timeline_wiring.py` (`test_timeline_guard_and_theme_branches`) | covered |
| REQ-P5-UI-019 | Art. V §2, F6 (NFR) | §5, §11 | SC-UI-019-1 | **retranslate clause:** `test_animation_guards.py::test_timeline_unbound_guards` (delivers `QEvent.LanguageChange`), `test_animation_timeline_wiring.py::test_timeline_guard_and_theme_branches`, `::test_tags_panel_no_selection_guards` (both re-run `_retranslate` via the module's `LanguageChange` helper, F5). **The "no bare literal / every string `tr()`-wrapped" clause is script-gated** by AGT-07 `string_audit_check`, not asserted by any test. | covered (retranslate); wrapping script-gated |

## DATA requirements (`.pixproj` — tags new; durations reused v2)

> DEP-2 **RESOLVED (ADR-0012):** tag persistence is a **schema-version bump to v3** (native
> `PlaybackMode` value strings + per-node `layer_id`), `_SUPPORTED_VERSIONS=(1,2,3)`; back-compat read
> of tagless v1/v2 projects (empty tag collection + minted `layer_id`) is preserved.

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P5-DATA-001 | **IO-2** (extend), S7, Phase-5 cap | §4, §11 | SC-D001-1 | `test_project_io_v3.py` (tag + `layer_id` round-trip) | covered |
| REQ-P5-DATA-002 | **IO-2** (reused — `duration_ms` already serialised), S7 | §4, §11 | SC-D002-1 | `test_project_io_v3.py` + `test_project_io_v2.py` (durations reused) | covered |
| REQ-P5-DATA-003 | Art. VII, IO-2 | §4, §11 | SC-D003-1 | `test_project_io_v3.py` (defensive tag load + v1/v2 back-compat) | covered |

## Coverage summary

- **36 of 36 REQ-IDs** (14 LOGIC + 19 UI + 3 DATA) have **≥1 acceptance scenario AND ≥1 shipped
  test** (**0 uncovered**).
- Test modules on disk: `tests/logic/test_animation.py`, `tests/logic/test_document_frames.py`,
  `tests/data/test_project_io_v3.py` (+ reused `test_project_io_v2.py`), `tests/ui/test_animation_timeline.py`,
  `tests/ui/test_animation_timeline_wiring.py`, `tests/ui/test_animation_guards.py`,
  `tests/ui/test_animation_canvas_frames.py`.
- **~35 Gherkin scenarios** across the requirements, incl. the multi-mode sequence outline
  SC-L002-1 and the property scenario SC-L002-2 (Hypothesis determinism).
- **0 REQ-IDs** are spec-only: the two NFRs (UI-016 perf, UI-019 string audit) carry behavioural
  tests here; their deferred **script** evidence is owned by AGT-10 (`perf_profile`) / AGT-07
  (`string_audit_check`) and does not gate this architecture pre-commit check.

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 5 to formally reflect what it inherits forward vs. builds new:

| Inherited primitive | Origin | Phase-5 forward trace |
| --- | --- | --- |
| **FR-1** — `Document.add_frame` / `remove_frame` (direct mutators) | `logic/document.py` (Phase 1, shipped) | → REQ-P5-LOGIC-004/-005 (**extended** into reversible commands; `move`/`duplicate` are NEW ops with no shipped equivalent → REQ-P5-LOGIC-006/-007) |
| **FR-2** — `Frame.duration_ms` + `DEFAULT_FRAME_DURATION_MS` | `logic/document.py` + `logic/constants.py` (Phase 1, shipped) | → REQ-P5-LOGIC-003 (timing source) → REQ-P5-LOGIC-008 (reversible set) → REQ-P5-UI-007/-010 |
| **CO-4** — `blend.composite_stack` (per-frame layer-stack flatten) | `logic/blend.py` (Phase 4, shipped) | → REQ-P5-LOGIC-013 (per-frame render delegates to it) → REQ-P5-LOGIC-012 (onion uses composited frames) |
| **IO-2** — `.pixproj` **v2** frame/layer/`duration_ms` serialisation | `data/project_io.py` (Phase 4, shipped) | → REQ-P5-DATA-002 (durations **reused**, not re-authored) → REQ-P5-DATA-001/-003 (**extended** with tags + defensive load) |

## Cross-layer trace (UI binds to new + shipped logic)

| UI REQ | Binds to logic/data REQ / shipped | Note |
| --- | --- | --- |
| REQ-P5-UI-003/-004/-005/-006 | REQ-P5-LOGIC-004/-005/-006/-007 | reversible add/remove/reorder/duplicate frame |
| REQ-P5-UI-007 | REQ-P5-LOGIC-008 + FR-2 | per-frame duration editor over `Frame.duration_ms` |
| REQ-P5-UI-008/-009/-010 | REQ-P5-LOGIC-001/-002/-003 | transport + mode selector over the sequencing engine (timer in `ui/`) |
| REQ-P5-UI-011/-012 | REQ-P5-LOGIC-012/-014 | onion toggle + count/tint over the onion overlay |
| REQ-P5-UI-013/-014 | REQ-P5-LOGIC-009/-010/-011 | tag CRUD + named-animation playback |
| REQ-P5-UI-015 | REQ-P5-LOGIC-004..010 via `ui/commands.py` | one QUndoCommand per frame/tag op (Article I) |
| REQ-P5-UI-002 | REQ-P5-LOGIC-013 (CO-4) | scrub renders the composited frame |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher).** `docs/research-phase5-animation.md` grounds onion-skin blend/falloff, the
  frame-tag schema conventions, the timeline widget model, and playback timing precision — **not
  yet present (concurrent)**. AGT-01 must not invent these; the behaviour set + Aseprite-parity
  defaults (spec §10) are fixed regardless.
- **DEP-2 (AGT-01 / DATA schema).** `.pixproj` tag persistence — **v3 bump vs additive v2 field** is
  a plan decision; back-compat read of tagless projects required (REQ-P5-DATA-003). Final
  `REQ-P5-DATA-*` count may be refined at plan.
- **DEP-3 (AGT-10).** Cached-per-frame-composite + dirty-rect recomposite strategy for
  REQ-P5-UI-016 / SC-UI-016-1 — re-flattening every layer per playback tick at 8K will exceed
  `FRAME_BUDGET_MS`. Plan-level.
- **Article II watch (BF-2).** AGT-01 must place `MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`,
  `DEFAULT_ONION_PREV/NEXT`, `ONION_TINT_PREV/NEXT`, `ONION_SKIN_OPACITY` in `logic/constants.py`
  (no literals); `DEFAULT_FRAME_DURATION_MS` is reused; the `PlaybackMode` enum lives in
  `logic/animation.py`.

## Recommended slicing (logic-first vertical slices)

1. **Slice A — playback engine (logic).** REQ-P5-LOGIC-001..003, -014 (`logic/animation.py`:
   `PlaybackMode`, sequencing, timing source, constants). AGT-03 + AGT-04.
2. **Slice B — reversible frame ops (logic).** REQ-P5-LOGIC-004..008 (extend `document.py`:
   add/remove/reorder/duplicate frame + set duration as do/undo commands; `move`/`duplicate` are
   new ops). AGT-03 + AGT-04.
3. **Slice C — frame tags + named animation + onion (logic).** REQ-P5-LOGIC-009..013. AGT-03 + AGT-04.
4. **Slice D — `.pixproj` tag persistence (data).** REQ-P5-DATA-001..003 (tags round-trip +
   defensive/back-compat; durations reused). AGT-01 fixes the schema-version (DEP-2). AGT-03 + AGT-04.
5. **Slice E — timeline + frame management UI.** REQ-P5-UI-001..007, -015, -017..019. AGT-05 + AGT-06.
6. **Slice F — playback + onion UI.** REQ-P5-UI-008..012. AGT-05 + AGT-06.
7. **Slice G — tags UI + named-animation + perf.** REQ-P5-UI-013, -014, -016 (coordinated with
   **AGT-10**, DEP-3). AGT-05 + AGT-06 + AGT-10.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 36 REQs, 36 with scenarios, 0 uncovered; tests
  `pending` (forward). SDD order: specify+clarify (this) → plan → tasks → analyze → implement → test.
- **No open clarification** (spec §10): all 16 ambiguities resolved with grounded defaults; the
  cel-linking scope risk is bounded (per-frame stacks + deferral, CL-7/CL-9), not suspended.
- **Three named dependencies** (DEP-1 Researcher grounding, DEP-2 `.pixproj` tag schema, DEP-3
  AGT-10 recomposite) must be resolved/allocated before/within the plan — none blocks this spec.
