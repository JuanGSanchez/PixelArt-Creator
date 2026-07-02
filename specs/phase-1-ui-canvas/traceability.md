# Traceability Matrix — Phase 1 (UI Increment): `phase-1-ui-canvas`

REQ-ID ↔ dossier `S-id` / research `F` ↔ spec section ↔ Gherkin scenario(s) ↔ test id(s).

**Mode:** REALISED / post-implementation. **AGT-06** has authored the `ui/` suite under
`tests/ui/` (pytest-qt, `QT_QPA_PLATFORM=offscreen`, both themes); the test-id column now
carries the concrete authored test node-ids (or the AGT-10 `perf_profile` / AGT-07
`string_audit_check` evidence for the two script-gated NFRs). No row remains `pending`.

Status legend:
- **scenario-ready** — has ≥1 Gherkin acceptance scenario, now backed by ≥1 authored AGT-06 pytest-qt test.
- **script-verified** — additionally proven by a deterministic script/audit
  (`string_audit_check`, `a11y-audit`, `perf_profile`/`frame-profile`,
  `check_layering`/`check_cycles`) as well as a pytest-qt scenario.
- (no row is `uncovered`: every REQ has ≥1 scenario.)

| REQ-ID | Traces (S-id / F) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P1-UI-001 | S1, F2 | §4, §11 | SC-UI-001-1, SC-UI-001-2 | `tests/ui/test_canvas_scene.py::test_sc_ui_001_1_buffer_pixel_rendered_no_aa`, `::test_sc_ui_001_2_magnified_pixel_is_solid_square` | scenario-ready |
| REQ-P1-UI-002 | S1, F3, S12 | §4, §11 | SC-UI-002-1, SC-UI-002-2 | `tests/ui/test_canvas_scene.py::test_sc_ui_002_1_scene_rect_matches_document`, `::test_sc_ui_002_2_resize_updates_scene_rect` | scenario-ready |
| REQ-P1-UI-003 | S1, F2, S12 | §4, §11 | SC-UI-003-1, SC-UI-003-2 | `tests/ui/test_canvas_scene.py::test_sc_ui_003_1_draw_background_only_exposed_rect`, `::test_sc_ui_003_2_background_tiles_on_tile_size` | scenario-ready |
| REQ-P1-UI-004 | S5, S12 | §4, §11 | SC-UI-004-1, SC-UI-004-2 | `tests/ui/test_canvas_view.py::test_sc_ui_004_1_zoom_clamped_to_range`, `::test_sc_ui_004_2_wheel_notch_scales_by_step`, `::test_sc_ui_004_presets_and_zoom_max`, `::test_sc_ui_004_zoom_changed_signal` | scenario-ready |
| REQ-P1-UI-005 | S5 | §4, §11 | SC-UI-005-1, SC-UI-005-2 | `tests/ui/test_canvas_view.py::test_sc_ui_005_1_middle_drag_pans_without_painting`, `::test_sc_ui_005_2_space_left_drag_pans_without_painting` | scenario-ready |
| REQ-P1-UI-006 | S2, S7 | §4, §11 | SC-UI-006-1, SC-UI-006-2, SC-UI-006-3 | `tests/ui/test_paint.py::test_sc_ui_006_1_click_paints_pixel_one_command`, `::test_sc_ui_006_2_drag_paints_all_pixels_one_command`, `::test_sc_ui_006_3_click_outside_buffer_is_noop` | scenario-ready |
| REQ-P1-UI-007 | S5 | §4, §11 | SC-UI-007-1, SC-UI-007-2, SC-UI-007-3 | `tests/ui/test_canvas_scene.py::test_sc_ui_007_1_grid_off_by_default`, `::test_sc_ui_007_2_grid_appears_past_threshold`; `tests/ui/test_canvas_view.py::test_sc_ui_007_3_snapping_floors_to_whole_pixel` | scenario-ready |
| REQ-P1-UI-008 | S3 (deferred), S6 | §4, §11 | SC-UI-008-1, SC-UI-008-2 | `tests/ui/test_canvas_view.py::test_sc_ui_008_1_right_click_dispatches_with_coord`, `::test_sc_ui_008_2_default_hook_shows_placeholder_only` | scenario-ready |
| REQ-P1-UI-009 | S7, C1, F1, S11 | §4, §11 | SC-UI-009-1 | `tests/ui/test_undo.py::test_sc_ui_009_1_command_delegates_to_logic_diff` | scenario-ready |
| REQ-P1-UI-010 | S7, F1 | §4, §11 | SC-UI-010-1, SC-UI-010-2, SC-UI-010-3 | `tests/ui/test_undo.py::test_sc_ui_010_1_undo_reverts_exactly_painted_pixel`, `::test_sc_ui_010_2_redo_reapplies_edit`, `::test_sc_ui_010_3_action_enable_state_tracks_stack` | scenario-ready |
| REQ-P1-UI-011 | S2, S11 | §4, §11 | SC-UI-011-1 | `tests/ui/test_tools.py::test_sc_ui_011_1_exactly_one_tool_active`; `tests/ui/test_main_window.py::test_sc_ui_011_1_tool_actions_are_exclusive` | scenario-ready |
| REQ-P1-UI-012 | S2 | §4, §11 | SC-UI-012-1 | `tests/ui/test_tools.py::test_sc_ui_012_1_pencil_paints_active_colour` | scenario-ready |
| REQ-P1-UI-013 | S2 | §4, §11 | SC-UI-013-1 | `tests/ui/test_tools.py::test_sc_ui_013_1_eraser_clears_to_default` | scenario-ready |
| REQ-P1-UI-014 | S2 | §4, §11 | SC-UI-014-1, SC-UI-014-2 | `tests/ui/test_tools.py::test_sc_ui_014_1_fill_fills_region_one_command`, `::test_sc_ui_014_2_fill_on_matching_region_is_noop` | scenario-ready |
| REQ-P1-UI-015 | S2 | §4, §11 | SC-UI-015-1 | `tests/ui/test_tools.py::test_sc_ui_015_1_line_previews_then_commits_one_command` | scenario-ready |
| REQ-P1-UI-016 | S2, S4 | §4, §11 | SC-UI-016-1 | `tests/ui/test_tools.py::test_sc_ui_016_1_picker_sets_active_colour_no_command` | scenario-ready |
| REQ-P1-UI-017 | S2 | §4, §11 | SC-UI-017-1 | `tests/ui/test_main_window.py::test_sc_ui_017_1_toolbar_selects_active_tool` | scenario-ready |
| REQ-P1-UI-018 | S4, S7 | §4, §11 | SC-UI-018-1, SC-UI-018-2 | `tests/ui/test_main_window.py::test_sc_ui_018_1_palette_panel_shows_colours_in_index_order`, `::test_sc_ui_018_2_selecting_swatch_sets_active_colour` | scenario-ready |
| REQ-P1-UI-019 | S7, F1 | §4, §11 | SC-UI-019-1 | `tests/ui/test_main_window.py::test_sc_ui_019_1_undo_action_wired_to_active_stack` | scenario-ready |
| REQ-P1-UI-020 | S1, S6, S7 | §4, §11 | SC-UI-020-1, SC-UI-020-2, SC-UI-020-3 | `tests/ui/test_main_window.py::test_sc_ui_020_1_new_document_defaults_to_64`, `::test_sc_ui_020_2_8k_document_supported`, `::test_sc_ui_020_3_tab_switch_changes_active_context` | scenario-ready |
| REQ-P1-UI-021 | F6, S8 | §4, §11 | SC-UI-021-1 | `tests/ui/test_i18n.py::test_sc_ui_021_1_language_manager_installs_by_locale` | scenario-ready |
| REQ-P1-UI-022 | F5, F6 | §4, §11 | SC-UI-022-1 | `tests/ui/test_i18n.py::test_sc_ui_022_1_change_event_retranslates_on_language_change`, `::test_sc_ui_022_1_palette_panel_retranslates` | scenario-ready |
| REQ-P1-UI-023 (NFR) | S1, S12, F2, F7, Art. VI | §5, §11 | SC-UI-023-1, SC-UI-023-2 | AGT-10 `perf_profile --width 7680 --height 4320` — within `FRAME_BUDGET_MS` (median 0.883 ms, p95 0.975 ms, 510 tiles/frame — not full-scene), exit 0 | script-verified |
| REQ-P1-UI-024 (NFR) | Art. V §1 | §5, §11 | SC-UI-024-1, SC-UI-024-2 | `tests/ui/test_a11y_theme.py::test_sc_ui_024_1_interactive_widgets_expose_accessible_names`, `::test_sc_ui_024_2_keyboard_reachable_with_visible_focus` + `a11y-audit` (2 LOW findings, non-blocking) | script-verified |
| REQ-P1-UI-025 (NFR) | Art. V §3 | §5, §11 | SC-UI-025-1 (+ every scenario run in both themes) | `tests/ui/test_a11y_theme.py::test_sc_ui_025_1_both_themes_role_based_and_distinct` + autouse both-theme param (all 79 UI tests × light/dark = 158 runs) | scenario-ready |
| REQ-P1-UI-026 (NFR) | Art. V §2, F6 | §5, §11 | SC-UI-026-1 | AGT-07 `string_audit_check` (14 `ui/` files) — clean, 0 findings, exit 0 | script-verified |

## Coverage summary

- **26 of 26 REQ-IDs** have **≥1 acceptance scenario** (0 uncovered).
- **44 Gherkin scenarios** total across the 26 requirements.
- **0 REQ-IDs** are spec-only: even the NFRs (perf, a11y, theming, i18n) carry a
  pytest-qt scenario in addition to their script/audit gate.
- **Test ids:** all realised — AGT-06 authored one pytest-qt test per scenario (Article IV:
  one test per acceptance criterion), each runnable under both light and dark themes; the two
  script-gated NFRs (REQ-P1-UI-023 perf, REQ-P1-UI-026 i18n string audit) are proven by the
  AGT-10 `perf_profile` and AGT-07 `string_audit_check` evidence respectively. **0 rows
  remain `pending`; every REQ now has spec + scenario + a concrete test/evidence.**

## Cross-layer trace (UI binds to shipped logic/data)

The UI requirements bind to the already-shipped Phase-1 core-engine REQs (see
`specs/phase-1-core-engine/`). This is the forward realisation of GAP-1..5 recorded there.

| UI REQ | Binds to core-engine REQ | Gap closed (core-engine §7) |
| --- | --- | --- |
| REQ-P1-UI-001/-003 | REQ-P1-LOGIC-006 (PixelBuffer) | GAP-1 (S1 render + tile culling) |
| REQ-P1-UI-006, -012..015 | REQ-P1-LOGIC-008 (drawing primitives) | GAP-2 (S2 click→paint binding) |
| REQ-P1-UI-016 | REQ-P1-LOGIC-008 (`pick_color`) | GAP-2 |
| REQ-P1-UI-004/-005/-007 | (view over the buffer/scene) | GAP-3 (S5 zoom/pan/grid) |
| REQ-P1-UI-009/-010 | REQ-P1-LOGIC-009 (History / PixelEdit / record_edit) | GAP-5 (S7 QUndoCommand bridge) |
| REQ-P1-UI-017 | REQ-P1-LOGIC-005 (Palette) | (palette display) |
| REQ-P1-UI-018/-020 | REQ-P1-LOGIC-010 (Document), REQ-P1-DATA-001 (`.pixproj`) | (document tabs / new / open-save) |
| REQ-P1-UI-023 | REQ-P1-LOGIC-012 (constants) + F2/F3/F7 | GAP-4 (S7 render pipeline / perf) |

## Gap list (for AGT-01 `sdd-plan`/`sdd-analyze` and AGT-06)

- **No requirement lacks an acceptance scenario, and no requirement lacks a test/evidence.**
  AGT-06 has authored the `tests/ui/` suite (158 passed, 0 failed; coverage gate green); the
  matrix is fully realised — 0 uncovered REQs remain.
- **Plan-level HOW deferred (not gaps):** BF-1 (AGT-10 render strategy for REQ-P1-UI-023),
  BF-2 (single-vs-tiled pixmap), BF-3 (zoom-step constant placement in `constants.py`,
  Article II) — see spec §8.
- **Article II watch:** AGT-01 must ensure zoom range/step (CL-1/CL-2), grid threshold
  (CL-4), default document size (CL-7) resolve to **named constants** in
  `logic/constants.py` — no literals in `ui/`.
- **Article X:** every REQ traces to an S-id or F-finding above; REQ-P1-UI-008 traces to
  the deferred S3 (seam only) + S6 extensibility — acceptable (it explicitly defers the
  hub to Phase 3, not an untraced requirement).

## Notes for `sdd-analyze` (AGT-01)

- This spec + matrix are internally consistent and now fully realised: 26 REQs, 26 with
  scenarios, 26 with concrete authored tests/evidence, 0 uncovered. The AGT-06 test set exists
  under `tests/ui/` (SDD order complete: specify→clarify→plan→tasks→analyze→implement→test).
- No open clarification (spec §10): all 16 ambiguities resolved with grounded defaults;
  none blocks planning.
