# Traceability Matrix — Phase 1: Core Engine

REQ-ID ↔ dossier S-id ↔ spec section ↔ Gherkin scenario(s) ↔ existing test id(s).
Status: **covered** (scenario + passing test) · **spec-only** (no unit test; enforced by
script/review) · **uncovered** (no scenario).

Test ids are `pytest` node ids `<file>::<function>` under `tests/`.

| REQ-ID | Traces (S-id) | Spec § | Scenario(s) | Test id(s) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P1-LOGIC-001 | S8, S1 | §4, §11 | SC-L001-1..4 | test_color.py::test_rgba_defaults_opaque, ::test_rgba_out_of_range_rejected, ::test_rgba_rejects_non_int_and_bool, ::test_is_rgba | covered |
| REQ-P1-LOGIC-002 | S7 | §4, §11 | SC-L002-1..4 | test_color.py::test_hex_roundtrip_with_and_without_alpha, ::test_from_hex_variants, ::test_from_hex_invalid, ::test_hex_roundtrip_property | covered |
| REQ-P1-LOGIC-003 **[REVIEW]** | → Ph4 (foundational primitive; no Phase-1 caller) | §4, §8 REV-2, §11 | SC-L003-1..3 | test_color.py::test_blend_over_opaque_source_returns_source, ::test_blend_over_transparent_source_returns_dest, ::test_blend_over_half_alpha_on_opaque, ::test_blend_over_transparent_source_returns_dest_even_if_dest_transparent | covered |
| REQ-P1-LOGIC-004 | S7 (palette nearest), S2 (flood-fill tolerance); → Ph3 perceptual | §4, §11 | SC-L004-1 | test_color.py::test_distance_sq_zero_and_symmetric | covered |
| REQ-P1-LOGIC-005 **[REVIEW]** | S7 (partial / Ph3) | §4, §8 REV-4, §11 | SC-L005-1..13 | test_palette.py::test_construct_and_len_iter, ::test_append_returns_index_and_get, ::test_append_rejects_non_rgba, ::test_set_replaces, ::test_get_bad_index, ::test_remove_at_shifts, ::test_move_reorders, ::test_move_bad_target, ::test_index_of_exact_and_missing, ::test_nearest_index_ties_to_lower, ::test_nearest_index_empty_raises, ::test_full_palette_rejects_append, ::test_copy_is_independent_and_eq, ::test_eq_notimplemented_for_other_type, ::test_repr_contains_class_name | covered |
| REQ-P1-LOGIC-006 | S1, S8 | §4, §11 | SC-L006-1..13 | test_pixel_buffer.py::test_default_rgba_is_transparent, ::test_indexed_buffer_defaults_zero, ::test_prefill_rgba_and_indexed, ::test_bad_dimensions, ::test_non_int_dimensions_rejected, ::test_dimension_exceeds_max, ::test_bad_mode, ::test_set_get_pixel, ::test_out_of_bounds_access, ::test_wrong_value_type_for_mode, ::test_indexed_fill_rect, ::test_fill_and_fill_rect_clipped, ::test_in_bounds | covered |
| REQ-P1-LOGIC-007 | S1, S8 (blit-blend = own NumPy impl, → Ph4; not `color.blend_over`) | §4, §11 | SC-L007-1..10 | test_pixel_buffer.py::test_region_copy_independent, ::test_region_out_of_bounds, ::test_blit_overwrite_and_clip, ::test_blit_mode_mismatch, ::test_blit_blend_on_indexed_rejected, ::test_blit_blend_composites_alpha, ::test_resize_pad_and_crop_preserve_content, ::test_resize_with_offset, ::test_copy_equality_and_independence, ::test_eq_notimplemented_and_mode_diff, ::test_data_is_uint8_array_and_repr | covered |
| REQ-P1-LOGIC-008 | S1, S2 | §4, §11 | SC-L008-1..19 | test_drawing.py::test_pencil_in_and_out_of_bounds, ::test_pick_color, ::test_line_horizontal_and_diagonal, ::test_line_single_point, ::test_line_vertical, ::test_line_steep, ::test_line_clips_out_of_bounds_endpoints, ::test_rectangle_outline_perimeter_only, ::test_rectangle_filled, ::test_rectangle_normalises_swapped_corners, ::test_ellipse_outline_and_fill, ::test_ellipse_various_aspect_ratios_stay_in_bounds, ::test_ellipse_degenerate_becomes_line, ::test_flood_fill_contiguous_region, ::test_flood_fill_noop_when_same_color, ::test_flood_fill_out_of_bounds_seed, ::test_flood_fill_indexed, ::test_flood_fill_tolerance_rgba, ::test_matches_type_mismatch_returns_false | covered |
| REQ-P1-LOGIC-009 | S7 | §4, §11 | SC-L009-1..12 | test_history.py::test_pixel_edit_execute_and_undo, ::test_function_command, ::test_history_push_execute_undo_redo, ::test_history_push_without_execute, ::test_new_push_clears_redo, ::test_undo_redo_empty_returns_none, ::test_history_limit_drops_oldest, ::test_history_bad_limit, ::test_clear, ::test_record_edit_captures_drawing_op, ::test_record_edit_ignores_unchanged_pixels, ::test_record_edit_roundtrip_via_history | covered |
| REQ-P1-LOGIC-010 | S7 (Layer attrs → §8 REV-5; Frame → REV-6) | §4, §11 | SC-L010-1..12 | test_document.py::test_new_document_has_one_frame_one_layer, ::test_document_accepts_palette_and_metadata, ::test_layer_opacity_validation, ::test_layer_repr, ::test_frame_duration_validation_and_repr, ::test_add_and_remove_layer, ::test_remove_last_layer_refused, ::test_remove_layer_bad_index, ::test_move_layer_reorders, ::test_move_layer_bad_index, ::test_add_and_remove_frame, ::test_remove_last_frame_refused, ::test_bad_frame_index, ::test_resize_canvas_all_buffers, ::test_document_repr | covered |
| REQ-P1-LOGIC-011 **[REVIEW]** | F8 (research) / Ph7 | §4, §8 REV-1, §11 | SC-L011-1..11 | test_compactor.py::test_compact_returns_packing_with_all_rects, ::test_compact_no_overlaps_and_within_bounds, ::test_compact_accepts_rect_namedtuples, ::test_compact_is_deterministic, ::test_empty_input_gives_empty_packing, ::test_rect_too_big_raises_does_not_fit, ::test_bad_atlas_bounds, ::test_malformed_rects_raise, ::test_does_not_fit_when_area_exhausted, ::test_smoke_entrypoint_returns_zero, ::test_property_all_placed_without_overlap | covered |
| REQ-P1-LOGIC-012 | S12 | §4, §9 | — (enforced by review; §9 findings) | (no unit test; `constants.py` imported by test_pixel_buffer.py::test_dimension_exceeds_max) | spec-only |
| REQ-P1-LOGIC-013 (NFR) | S11 | §4, §5 | — (enforced by script) | scripts/check_layering.py, scripts/check_cycles.py (Article I) | spec-only |
| REQ-P1-DATA-001 | S7, Article VII | §4, §11 | SC-D001-1..12 | test_project_io.py::test_roundtrip_preserves_everything, ::test_indexed_roundtrip, ::test_save_keeps_existing_suffix, ::test_serialize_shape, ::test_deserialize_rejects_malformed, ::test_deserialize_rejects_wrong_payload_size, ::test_deserialize_rejects_bad_palette_entry, ::test_deserialize_too_many_palette_colors, ::test_load_missing_file, ::test_load_invalid_json, ::test_load_non_object_json, ::test_defaults_applied_for_optional_fields | covered |

## Coverage summary

- **12 of 14 REQ-IDs** are **covered** (Gherkin scenario + at least one passing test).
- **2 REQ-IDs** are **spec-only** by design: REQ-P1-LOGIC-012 (S12, enforced by review /
  §9 findings) and REQ-P1-LOGIC-013 (S11, enforced by `check_layering`/`check_cycles`).
  Neither is a coverage gap — both are gate-enforced NFRs, not unit-testable behaviours.
- **0 uncovered** REQ-IDs (every functional REQ has ≥1 scenario and ≥1 test).

## Gap list (for AGT-04/AGT-06 and sdd-clarify)

- No functional REQ lacks a test. No test asks are outstanding for the shipped logic/data.
- Open items are **not** coverage gaps but adjudication items:
  - §8 ORCHESTRATOR REVIEW (REV-1, REV-2, REV-4..7; REV-3 withdrawn — now traced) —
    scope attribution of early-shipped behaviour.
  - §7 Gaps (GAP-1..7) — Phase-1 dossier requirements owned by the pending UI increment
    / later phases (produce their own REQ-P1-UI-* / later-phase REQs when specified).
  - §9 S12 findings (S12-1..8) — routed to AGT-01 `sdd-analyze` / AGT-03.

## Notes for sdd-analyze (AGT-01)

- REQ-P1-LOGIC-004 is now traced to **S7 (palette nearest) + S2 (flood-fill tolerance)**
  — it is consumed within Phase 1 by `palette.nearest_index` and `drawing.flood_fill`
  (Phase-3 perceptual matching is a forward note only). It is therefore no longer a
  no-S-id finding (§8 REV-3 withdrawn).
- REQ-P1-LOGIC-011 remains the only functional REQ with **no** dossier S-id trace (only
  research F8 / forward Phase-7); Article X requires every REQ to trace to an S-id. This
  is a genuine cross-artifact finding for `sdd-analyze` — resolve via the §8 REV-1
  adjudication (attach a Phase-7 REQ trace or reclassify), not by inventing an S-id.
- REQ-P1-LOGIC-003 (`color.blend_over`) traces **forward to Phase-4** only and has no
  in-code Phase-1 caller (`blit(blend=True)` reimplements blending in NumPy) — a
  foundational primitive shipped early; adjudicate via §8 REV-2.
- CompactionError base-class consistency (CL-8) is **resolved by task T6**:
  `CompactionError` subclasses `ValueError` like every other domain error (preserving its
  `reason` token). No longer an accepted inconsistency — a decided remediation (T6/AGT-03,
  regression in T7).
