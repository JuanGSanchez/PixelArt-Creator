# Traceability Matrix — Phase 2: Advanced Drawing System

REQ-ID ↔ dossier S-id ↔ layer/owner ↔ spec section ↔ Gherkin scenario(s) ↔ test target.
**Mode:** FORWARD / pre-implementation — tests do not exist yet; the "Test target" column
names the test module + harness AGT-04 (logic) / AGT-06 (UI) will author, one test per
scenario (Article IV). Status: **planned** (scenario authored, test pending) ·
**spec-only** (gate/script-enforced, no unit test).

Test module conventions (from Phase-1): logic → `tests/logic/test_<module>.py` (pytest +
Hypothesis); UI → `tests/ui/test_<widget>.py` (pytest-qt, both themes, headless).

## 1. Logic layer (`REQ-P2-LOGIC-*`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces (S-id) | Module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P2-LOGIC-001 | S2, S1 | `logic/selection.py` | §4.1, §11 | SC-L001-1..4 | `tests/logic/test_selection.py` | planned |
| REQ-P2-LOGIC-002 | S2, S5 | `logic/selection.py` | §4.1, §11 | SC-L002-1..4 | `test_selection.py::test_sc_l002_1_rectangle_marks_only_the_rectangle`, `::test_sc_l002_2_swapped_corners_normalise_to_same_mask`, `::test_sc_l002_3_out_of_bounds_rectangle_is_clipped`, `::test_sc_l002_4_fully_out_of_bounds_rectangle_is_empty`, `::test_property_rect_mask_bounds_within_canvas` | landed |
| REQ-P2-LOGIC-003 | S2 | `logic/selection.py` | §4.1, §11 | SC-L003-1..4 | `test_selection.py::test_sc_l003_1_closed_triangle_fills_interior_even_odd`, `::test_sc_l003_2_path_auto_closes_last_to_first`, `::test_sc_l003_3_degenerate_path_selects_at_most_traced_pixels`, `::test_sc_l003_4_lasso_is_deterministic_for_identical_vertices`, `::test_lasso_clips_vertices_to_bounds`, `::test_property_lasso_mask_stays_in_bounds` | landed |
| REQ-P2-LOGIC-004 | S2, S7 (tolerance metric) | `logic/selection.py` | §4.1, §11 | SC-L004-1..4 | `test_selection.py::test_sc_l004_1_wand_selects_only_contiguous_same_colour_region`, `::test_sc_l004_2_tolerance_includes_near_colours_excludes_far`, `::test_sc_l004_3_indexed_matches_exactly_tolerance_ignored`, `::test_sc_l004_4_out_of_bounds_seed_yields_empty_mask` | landed |
| REQ-P2-LOGIC-005 | S2 | `logic/selection.py` | §4.1, §11 | SC-L005-1..6 (SC-L005-6 reversibility) | `test_selection.py::test_sc_l005_1_invert_complements_within_bounds`, `::test_sc_l005_2_clear_deselect_yields_empty_mask`, `::test_sc_l005_3_translate_shifts_and_clips_off_buffer`, `::test_sc_l005_4_combine_add_subtract_replace`, `::test_sc_l005_5_move_lifts_pixels_and_restamps_at_offset`, `::test_sc_l005_5_move_indexed_vacates_index_zero`, `::test_sc_l005_6_move_then_undo_restores_buffer_exactly`, `::test_combine_errors_on_bad_mode_and_mismatched_dims`, `::test_move_selection_argument_validation`, `::test_property_invert_invert_is_identity` | landed |
| REQ-P2-LOGIC-006 | S2 | `logic/selection.py` | §4.1, §11 | SC-L006-1..3 | `test_selection.py::test_sc_l006_1_fill_constrained_to_mask_writes_only_masked_pixels`, `::test_sc_l006_2_no_active_mask_edits_whole_buffer`, `::test_sc_l006_3_helper_returns_exactly_changed_coords`, `::test_apply_masked_dedup_and_unselected_skipped_with_mask` | landed |
| REQ-P2-LOGIC-007 | S2 | `logic/transform.py` | §4.1, §11 | SC-L007-1..3 (SC-L007-2 no-new-colours, -3 reversibility) | `tests/logic/test_transform.py` | planned |
| REQ-P2-LOGIC-008 | S2 | `logic/transform.py` | §4.1, §11 | SC-L008-1..4 (SC-L008-4 no-new-colours) | `test_transform.py::test_sc_l008_1_rotate_cw_on_known_2x3_buffer`, `::test_sc_l008_2_non_square_swaps_width_and_height`, `::test_sc_l008_3_four_cw_and_cw_then_ccw_are_identity`, `::test_sc_l008_4_rotate_introduces_no_new_colours`, `::test_property_rotate90_four_times_identity` | landed |
| REQ-P2-LOGIC-009 | S2, S1 | `logic/transform.py` | §4.1, §11 | SC-L009-1..5 (SC-L009-2/-5 no-new-colours) | `test_transform.py::test_sc_l009_1_scale_2x_doubles_and_maps_each_pixel_to_2x2_block`, `::test_sc_l009_2_scale_introduces_no_new_colours`, `::test_sc_l009_3_non_integer_factor_is_deterministic`, `::test_sc_l009_4_non_positive_target_raises`, `::test_sc_l009_5_scale_down_stays_within_source_palette`, `::test_scale_factor_out_of_bounds_raises`, `::test_property_scale_no_new_colours` | landed |
| REQ-P2-LOGIC-010 | S2 | `logic/transform.py` + `logic/selection.py` | §4.1, §11 | SC-L010-1..3 (SC-L010-3 reversibility) | `test_transform.py::test_sc_l010_1_selection_transform_changes_only_masked_pixels`, `::test_sc_l010_2_whole_buffer_transform_changes_every_pixel`, `::test_sc_l010_2_dim_changing_whole_buffer_uses_function_command`, `::test_sc_l010_3_selection_transform_then_undo_restores_buffer`, `::test_masked_transform_with_empty_mask_is_noop`, `::test_masked_transform_dim_mismatch_raises`, `::test_masked_transform_uncovered_pixel_takes_fill` | landed |
| REQ-P2-LOGIC-011 | S2, S5 | `logic/symmetry.py` | §4.1, §11 | SC-L011-1..6 | `tests/logic/test_symmetry.py` | planned |
| REQ-P2-LOGIC-012 | S2 | `logic/pixel_perfect.py` | §4.1, §11 | SC-L012-1..4 | `tests/logic/test_pixel_perfect.py` | planned |
| REQ-P2-LOGIC-013 | S2; **research F-RotSprite** | `logic/rotsprite.py` | §4.1, §7, §11 | SC-L013-1..5 (SC-L013-1 no-new-colours, acceptance-critical) | `tests/logic/test_rotsprite.py` | planned |
| REQ-P2-LOGIC-014 | S2, S5 | `logic/tiled.py` | §4.1, §11 | SC-L014-1..4 (SC-L014-4 reversibility) | `tests/logic/test_tiled.py` | planned |
| REQ-P2-LOGIC-015 | S7 (C1/F1) (NFR) | all Phase-2 logic + `ui/commands.py` | §4.1, §5, §11 | SC-L015-1 (per-op reversibility) ; SC-L015-2 (spec-only) | per-op reversibility asserts: `test_selection.py::test_sc_l005_6_move_then_undo_restores_buffer_exactly`, `test_transform.py::test_sc_l010_3_selection_transform_then_undo_restores_buffer`, `::test_dim_changing_command_undo_restores_buffer`, `::test_property_whole_buffer_transform_reversible`, `::test_property_flip_flip_identity`; the Article-I layering half of SC-L015-2 stays script-gated by `check_layering` | landed |

## 2. UI layer (`REQ-P2-UI-*`) — owner AGT-05 (impl) / AGT-06 (tests, both themes)

| REQ-ID | Traces (S-id) | Module (indicative) | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P2-UI-001 | S2, S5 | `ui/tools/rectangle_tool.py` | §4.2, §11 | SC-U001-1..4 (SC-U001-3 reversibility) | `tests/ui/test_rectangle_tool.py` | planned |
| REQ-P2-UI-002 | S2, S5 | `ui/tools/ellipse_tool.py` | §4.2, §11 | SC-U002-1..3 (SC-U002-3 reversibility) | `tests/ui/test_ellipse_tool.py` | planned |
| REQ-P2-UI-003 | S2 | `ui/tools/` shape option | §4.2, §11 | SC-U003-1..2 | `tests/ui/test_shape_mode.py` | planned |
| REQ-P2-UI-004 | S2, S5 | `ui/tools/rect_select_tool.py` | §4.2, §11 | SC-U004-1..2 | `tests/ui/test_rect_select_tool.py` | planned |
| REQ-P2-UI-005 | S2 | `ui/tools/lasso_tool.py` | §4.2, §11 | SC-U005-1..2 | `tests/ui/test_lasso_tool.py` | planned |
| REQ-P2-UI-006 | S2 | `ui/tools/magic_wand_tool.py` | §4.2, §11 | SC-U006-1..2 | `tests/ui/test_magic_wand_tool.py` | planned |
| REQ-P2-UI-007 | S2, S5 | `ui/selection_overlay.py` | §4.2, §11 | SC-U007-1..3 (SC-U007-3 reversibility) | `tests/ui/test_selection_overlay.py` | planned |
| REQ-P2-UI-008 | S2 | `ui/main_window.py` (actions) | §4.2, §11 | SC-U008-1..2 | `tests/ui/test_selection_actions.py` | planned |
| REQ-P2-UI-009 | S2 | `ui/main_window.py` + `ui/transform_dialog.py` | §4.2, §11 | SC-U009-1..3 (SC-U009-2 no-new-colours) | `tests/ui/test_transform_actions.py` | planned |
| REQ-P2-UI-010 | S2 | `ui/rotsprite_dialog.py` | §4.2, §11 | SC-U010-1..3 (SC-U010-2 no-new-colours) | `tests/ui/test_rotsprite_action.py` | planned |
| REQ-P2-UI-011 | S2, S5 | `ui/symmetry_panel.py` | §4.2, §11 | SC-U011-1..3 (SC-U011-3 reversibility) | `tests/ui/test_symmetry.py` | planned |
| REQ-P2-UI-012 | S2 | `ui/tools/` pencil option | §4.2, §11 | SC-U012-1..2 | `tests/ui/test_pixel_perfect.py` | planned |
| REQ-P2-UI-013 | S5 | `ui/canvas_view.py` (grid/snap) | §4.2, §11 | SC-U013-1..3 | `tests/ui/test_grid_snap.py` | planned |
| REQ-P2-UI-014 | S1, S5 | `ui/canvas_view.py` / `ui/canvas_scene.py` | §4.2, §11 | SC-U014-1..2 | `tests/ui/test_aa_off.py` | planned |
| REQ-P2-UI-015 | S2, S5 | `ui/tiled_mode.py` / `ui/canvas_scene.py` | §4.2, §11 | SC-U015-1..4 (SC-U015-3 reversibility) | `tests/ui/test_tiled_mode.py` | planned |

*Module names are indicative for `sdd-plan`/AGT-01 placement; final paths are AGT-01's call.*

## 3. Coverage summary (planned)

- **30 REQ-IDs**: 15 LOGIC + 15 UI. Every functional REQ has ≥1 Gherkin scenario.
- **~113 scenarios** authored (logic SC-L001..015 + UI SC-U001..015); each maps to exactly
  one pending test (Article IV: one test per acceptance criterion).
- **Reversibility acceptance** (NFR-3 / R2): SC-L005-6, SC-L007-3, SC-L010-3, SC-L013 undo,
  SC-L014-4, SC-L015-1, SC-U001-3, SC-U002-3, SC-U007-3, SC-U011-3, SC-U015-3.
- **No-new-colours acceptance** (NFR-4 / R2): SC-L007-2, SC-L008-4, SC-L009-2, SC-L009-5,
  SC-L013-1 (acceptance-critical), SC-U009-2, SC-U010-2.
- **Spec-only** (gate-enforced, no unit test): SC-L015-2 (Qt-free purity via
  `check_layering`/`check_cycles`, Article I); NFR-5 constants via review (Article II).

## 4. Notes for sdd-analyze (AGT-01)

- **Every REQ traces to an S-id** (mostly S2 painting, S5 canvas, S1 grid, S7 command
  pattern) — no untraced REQ (Article X satisfied). REQ-P2-LOGIC-013 additionally depends on
  **research F-RotSprite** (algorithm grounding) — this must land before `sdd-plan`
  finalises the RotSprite algorithm; the *acceptance* (no new colours, determinism) is
  fixed here.
- **New constants** (§9 of spec) — `ROTSPRITE_UPSCALE_FACTOR=8`,
  `MAGIC_WAND_DEFAULT_TOLERANCE=0`, `TILED_PREVIEW_REPEAT=3` — must be added to
  `logic/constants.py` (Article II); AGT-01 to rule on `SymmetryAxis` enum placement
  (module-local vs constants) and whether `SCALE_MIN/MAX_FACTOR` guards are needed.
- **New domain exceptions** `SelectionError`, `TransformError` subclass `ValueError` (Phase-1
  convention: `ColorError`, `PaletteError`, `PixelBufferError`, `DocumentError`).
- **Slicing** (§8): 2A logic → 2B UI, optional early shape-tools micro-slice. RotSprite is
  the only logic item gated on external research; the rest of 2A is unblocked.
- **Dependencies** (§7): all Phase-1 logic (`pixel_buffer`, `drawing`, `history`) + Phase-1
  UI (`ui/commands.py`, canvas view/scene, tool-controller pattern) must be present. The
  Phase-1 UI increment is `[~]` in progress; 2B binds to it — AGT-01 to confirm sequencing
  so 2B does not start before its Phase-1 UI substrate is stable.
