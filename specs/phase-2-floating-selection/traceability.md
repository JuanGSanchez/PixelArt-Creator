# Traceability Matrix — Floating-Selection Move / Copy (REQ-NEW-C)

REQ-ID ↔ user requirement / dossier S-id ↔ layer/owner ↔ spec section ↔ Gherkin
scenario(s) ↔ test target.
**Mode:** BACKWARD / post-implementation (pre-commit gate, 2026-07-03) — impl + tests exist
on disk and pass (`tests/logic/test_floating_selection.py` + `tests/ui/test_floating_selection.py`
= 84 passing, headless). The "Test target" column names the on-disk module (one test per
scenario, Article IV). Status: **done** (impl + ≥1 passing test) ·
**spec-only** (gate/script-enforced, no unit test).

Test module conventions (from Phase-1/2): logic → `tests/logic/test_<module>.py` (pytest +
Hypothesis); UI → `tests/ui/test_<widget>.py` (pytest-qt, both themes, headless).

## 1. Logic layer (`REQ-P2-LOGIC-030..036`) — owner AGT-03 (impl) / AGT-04 (tests)

| REQ-ID | Traces | Module | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P2-LOGIC-030 | REQ-NEW-C; S2, S1 | `logic/selection.py` (`FloatMode`, `FloatingSelection`, `lift_selection`) | §4.1, §11 | SC-L030-1..5 | `tests/logic/test_floating_selection.py` | done |
| REQ-P2-LOGIC-031 | REQ-NEW-C; S2, S5 | `logic/selection.py` (`composite_preview`) | §4.1, §11 | SC-L031-1..4 (SC-L031-1/-2 non-destructive) | `test_floating_selection.py::test_sc_l031_1_move_preview_vacates_origin_and_stamps_offset`, `::test_sc_l031_2_copy_preview_keeps_origin_and_adds_offset`, `::test_sc_l031_3_preview_is_deterministic`, `::test_sc_l031_4_off_canvas_offset_clips_preview`, `::test_sc_l031_region_return_is_region_sized_and_matches_full_slice`, `::test_sc_l031_region_out_of_bounds_or_degenerate_raises`, `::test_sc_l031_region_non_int_component_raises`, `::test_sc_l031_preview_base_dimension_mismatch_raises`, `::test_property_lift_and_preview_are_non_destructive`, `::test_property_region_preview_equals_full_slice` | done |
| REQ-P2-LOGIC-032 | REQ-NEW-C; S2, S7 | `logic/selection.py` (`commit_floating` MOVE / reuses `move_selection`) | §4.1, §11 | SC-L032-1..5 (SC-L032-2 reversibility, -5 indexed vacate) | `test_floating_selection.py::test_sc_l032_1_move_commit_vacates_origin_and_stamps`, `::test_sc_l032_2_move_commit_reversible_apply_undo_identity`, `::test_sc_l032_3_move_commit_is_exactly_one_pixeledit`, `::test_sc_l032_4_zero_offset_move_commit_is_noop`, `::test_sc_l032_5_indexed_move_vacates_index_zero`, `::test_sc_l032_move_commit_equals_move_selection_regression`, `::test_property_commit_apply_undo_is_identity` | done |
| REQ-P2-LOGIC-033 | REQ-NEW-C; S2, S7 | `logic/selection.py` (`copy_selection` builder) | §4.1, §11 | SC-L033-1..4 (SC-L033-2 reversibility, -4 indexed) | `test_floating_selection.py::test_sc_l033_1_copy_commit_stamps_dest_keeps_origin`, `::test_sc_l033_2_copy_commit_reversible`, `::test_sc_l033_3_copy_commit_is_exactly_one_command`, `::test_sc_l033_4_copy_keeps_origin_in_indexed_mode`, `::test_sc_l033_copy_introduces_no_new_colours`, `::test_copy_selection_zero_offset_is_noop`, `::test_copy_selection_validates_arguments` | done |
| REQ-P2-LOGIC-034 | REQ-NEW-C; S2 | `logic/selection.py` (cancel = no-op) | §4.1, §11 | SC-L034-1 (non-destructive cancel) | `test_floating_selection.py::test_sc_l034_1_cancel_discards_float_buffer_unchanged` | done |
| REQ-P2-LOGIC-035 | REQ-NEW-C; S2, S5 | `logic/selection.py` (off-canvas clip) | §4.1, §11 | SC-L035-1..3 (off-canvas clip) | `test_floating_selection.py::test_sc_l035_1_off_canvas_pixels_discarded_on_commit_not_wrapped`, `::test_sc_l035_2_move_fully_off_canvas_still_vacates_whole_origin`, `::test_sc_l035_3_off_canvas_clipping_is_deterministic` | done |
| REQ-P2-LOGIC-036 | REQ-NEW-C; S2; ADR-0008 | `logic/selection.py` (Qt-free purity) | §4.1, §11 | SC-L036-1..2 ; SC-L036-3 (spec-only) | `test_floating_selection.py::test_sc_l036_1_lift_from_rect_lasso_wand_masks`, `::test_sc_l036_2_dimension_mismatch_raises_selection_error`; the Qt-free-purity half (SC-L036-3) stays script-gated by `check_layering`/`check_cycles` | done / spec-only |

## 2. UI layer (`REQ-P2-UI-030..036`) — owner AGT-05 (impl) / AGT-06 (tests, both themes)

| REQ-ID | Traces | Module (indicative) | Spec § | Scenario(s) | Test target | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P2-UI-030 | REQ-NEW-C; S2, S5 | `ui/tools/floating_move.py` + `ui/canvas_scene.py` | §4.2, §11 | SC-U030-1..2 (SC-U030-1 non-destructive) | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-031 | REQ-NEW-C; S2, S5 | `ui/tools/floating_move.py` | §4.2, §11 | SC-U031-1..2 | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-032 | REQ-NEW-C; S2, S5 | `ui/tools/floating_move.py` + `selection_base.py` (Ctrl-only) | §4.2, §11 | SC-U032-1..3 (SC-U032-3 modifier disambiguation, CL-F5) | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-033 | REQ-NEW-C; S2, S7 | `ui/tools/floating_move.py` + `ui/commands.py` | §4.2, §11 | SC-U033-1..4 | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-034 | REQ-NEW-C; S2 | `ui/tools/floating_move.py` + `ui/canvas_view.py` (Escape) | §4.2, §11 | SC-U034-1..2 | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-035 | REQ-NEW-C; S2, S7, S1 | `ui/tools/floating_move.py` + `ui/canvas_scene.py` | §4.2, §11 | SC-U035-1..3 (SC-U035-1 reversibility, -3 both themes) | `tests/ui/test_floating_selection.py` | done |
| REQ-P2-UI-036 | REQ-NEW-C; S2, S5; ADR-0008 | `ui/tools/floating_move.py` + `ui/canvas_view.py` | §4.2, §11 | SC-U036-1..3 (SC-U036-3 a11y/i18n) | `tests/ui/test_floating_selection.py` | done |

*Final on-disk paths (AGT-01 placement): the move controller shipped as
`ui/tools/floating_move.py` (not a separate `selection_overlay.py`); the floating move extends
the shipped REQ-P2-UI-007 selection-overlay/move interaction via `canvas_scene._FloatingPreviewItem`.*

## 3. Coverage summary (BUILT — verified 2026-07-03)

- **14 REQ-IDs**: 7 LOGIC (`REQ-P2-LOGIC-030..036`) + 7 UI (`REQ-P2-UI-030..036`).
- **14 impl / 14 tested / 0 uncovered.** Every functional REQ has ≥1 on-disk impl and ≥1
  passing test.
- **84 tests pass** headless (`QT_QPA_PLATFORM=offscreen`): logic `test_floating_selection.py`
  (SC-L030..036 + Hypothesis non-destructive/reversibility invariants) and UI
  `test_floating_selection.py` (SC-U030..036, both themes). SC-L036-3 remains gate-enforced
  (spec-only) via `check_layering`/`check_cycles` (both exit 0).
- **Non-destructiveness acceptance** (NFR-3 / REQ-NEW-C core): SC-L030-1, SC-L031-1,
  SC-L031-2, SC-L034-1, SC-U030-1.
- **Reversibility acceptance** (NFR-4): SC-L032-2, SC-L033-2, SC-U035-1.
- **Off-canvas-clip acceptance** (CL-F1): SC-L031-4, SC-L035-1..3, SC-U036-2.
- **Indexed-vacate acceptance** (CL-F2): SC-L032-5, SC-L033-4.
- **Spec-only** (gate-enforced, no unit test): SC-L036-3 (Qt-free purity via
  `check_layering`/`check_cycles`, Article I); NFR-6 (no new constants) via review (Article II).

## 4. Notes for sdd-analyze (AGT-01)

- **Every REQ traces to REQ-NEW-C + an S-id** (S2 region editing, S5 canvas, S1 grid, S7
  command pattern) — no untraced REQ (Article X satisfied). No Researcher dependency (all
  primitives shipped).
- **REQ-ID sub-band** `030..036` deliberately avoids the shipped Phase-2 `001..015` band
  (addresses FU-17 collision risk for this feature).
- **Reuse over new code:** REQ-P2-LOGIC-032 (MOVE) reuses the shipped
  `selection.move_selection`; only REQ-P2-LOGIC-033 (COPY) is a genuinely new builder, plus
  the `FloatingSelection` model (030) and the preview-composite function (031). AGT-01 to fix
  (a) the empty-mask contract (SelectionError vs no-float sentinel — SC-L030-3), (b) the
  `FloatingSelection` public surface, (c) any `FloatMode` enum placement.
- **No new constants** (§9 of spec): RGBA vacate = `color.TRANSPARENT`; indexed vacate =
  index `0` (existing convention, CL-F2). No `constants.py` change expected.
- **ADR-0008 dependency:** the indexed vacate (index 0, single-layer) and active-layer scope
  rely on `Document.mode` being the single authority; confirm consistency at plan time.
- **Slicing** (§8): F-A logic → F-B UI. F-A can proceed immediately (deps shipped).
- **Clarifications** CL-F1..F8 recorded as category-1 defaults; **no SUSPEND** open.
