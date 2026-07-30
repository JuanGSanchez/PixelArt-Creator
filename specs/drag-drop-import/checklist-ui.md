# Quality Checklist — Drag-and-Drop Import, UI Slice A-B (sdd-checklist)

| Field | Value |
| --- | --- |
| Feature | `drag-drop-import` (REQ-NEW-A) |
| Slice | A-B (UI, `REQ-DDI-UI-001..009`) |
| Run by | AGT-06 (QA/Accessibility) |
| Date | 2026-07-03 |
| Spec | `specs/drag-drop-import/spec.md` §11 (SC-U001..U009) |
| Tests | `tests/ui/test_drag_drop_import.py` (74 = 37 unique × 2 themes) |
| Gate | Every in-scope UI criterion has passing pytest-qt evidence; both themes; a11y; ui coverage gate green |

## Scope note
This run covers the **UI** slice (A-B). The DATA-layer criteria (SC-D001..D005,
`REQ-DDI-DATA-001..005`) are AGT-04's pytest/Hypothesis tests (Slice A-A) and are
**out of AGT-06 scope** — their verdict comes from AGT-04's own checklist run.

## Per-criterion checklist (UI)

| REQ | Scenario | Evidence (test id) | Verdict |
| --- | --- | --- | --- |
| UI-001 | SC-U001-1 accept file-URL drag | `test_ui001_accept_drops_enabled`, `_drag_enter_accepts_file_urls`, `_drag_enter_ignores_non_file_payload`, `_drop_without_urls_is_ignored` | PASS |
| UI-001 | SC-U001-2 drop delivers paths to router | `test_ui001_drop_delivers_paths_to_router` | PASS |
| UI-002 | SC-U002-1 image opens new doc regardless of location | `test_ui002_image_routes_new_document_regardless_of_location` | PASS |
| UI-002 | SC-U002-2 each file dispatched to its type branch | `test_ui002_each_type_dispatched_to_its_branch` | PASS |
| UI-003 | SC-U003-1 image → NEW tab, not a layer | `test_ui003_image_opens_new_tab_not_layer` | PASS |
| UI-003 | SC-U003-2 new doc RGBA at image dims | `test_ui003_new_document_is_rgba_at_image_dims` | PASS |
| UI-003 | SC-U003-3 source file unmodified on disk | `test_ui003_source_file_not_modified_on_disk` | PASS |
| UI-003 | (D002-2/-4 at UI) bmp/jpg decode, first-frame GIF | `test_ui003_decodes_other_raster_formats[bmp,jpg]`, `test_ui003_first_frame_of_multiframe_gif` | PASS |
| UI-004 | SC-U004-1 clean doc opens w/o prompt | `test_ui004_clean_document_opens_without_prompt` | PASS |
| UI-004 | SC-U004-2 dirty → Save/Discard/Cancel prompt | `test_ui004_dirty_document_prompts_save_discard_cancel` | PASS |
| UI-004 | SC-U004-3 Cancel aborts, state unchanged | `test_ui004_cancel_aborts_open_leaves_state_unchanged` | PASS |
| UI-004 | SC-U004-4 Save persists then opens (+ cancelled-dialog edge) | `test_ui004_save_persists_then_opens`, `_save_cancelled_dialog_aborts_open` | PASS |
| UI-004 | SC-U004-5 Discard opens without saving | `test_ui004_discard_opens_without_saving` | PASS |
| UI-005 | SC-U005-1/-2/-3 gpl/hex/pal replace in ONE undo step | `test_ui005_palette_replaces_active_in_one_undoable_step[gpl,hex,pal]` | PASS |
| UI-005 | SC-U005-4 reversibility (apply∘undo = identity) | `test_ui005_reversibility_undo_restores_prior_palette` | PASS |
| UI-005 | SC-U005-5 no doc → graceful no-op + notice | `test_ui005_no_open_document_is_graceful_noop_with_notice` | PASS |
| UI-006 | SC-U006-1 unknown → ignore + notice, no crash | `test_ui006_unknown_type_ignored_with_notice_no_crash` | PASS |
| UI-007 | SC-U007-1 corrupt image → error, no tab | `test_ui007_corrupt_image_shows_error_no_tab_no_crash` | PASS |
| UI-007 | SC-U007-2 oversized image → error, no tab | `test_ui007_oversized_image_shows_error_no_tab` | PASS |
| UI-007 | SC-U007-3 malformed palette → error, palette unchanged | `test_ui007_malformed_palette_shows_error_palette_unchanged` | PASS |
| UI-007 | SC-U007-4 invalid .pixproj → error, no open | `test_ui007_invalid_pixproj_shows_error_no_document_opened` | PASS |
| UI-008 | SC-U008-1 N images → N tabs (stable order) | `test_ui008_multiple_images_open_one_tab_each_stable_order` | PASS |
| UI-008 | SC-U008-2 mixed drop routed per type | `test_ui008_mixed_drop_routes_each_by_type` | PASS |
| UI-008 | SC-U008-3 one bad file skipped, rest processed | `test_ui008_one_bad_file_skipped_rest_processed` | PASS |
| UI-008 | SC-U008-4 last palette wins, each own undo step | `test_ui008_last_palette_wins_each_own_undo_step` | PASS |
| UI-008 | SC-U008-5 zero-file drop is a no-op | `test_ui008_zero_file_drop_is_noop` | PASS |
| UI-009 | SC-U009-1 notices tr()-wrapped (string_audit) | `string_audit_check` clean (findings []); `test_ui009_notice_strings_are_translatable_and_rendered` | PASS |
| UI-009 | SC-U009-2 prompt keyboard-reachable + default | `test_ui009_error_dialog_offers_keyboard_reachable_default`; a11y-audit | PASS |
| UI-009 | SC-U009-3 legible in both themes | `test_ui009_window_renders_after_drop_in_active_theme` + autouse both-theme fixture; a11y-audit | PASS |

## Cross-cutting gates

| Item | Evidence | Verdict |
| --- | --- | --- |
| Both themes (light + dark) | autouse `theme` fixture (conftest.py) runs every test ×2 → 74 tests | PASS |
| a11y (REQ-DDI-UI-009) | a11y-audit: accessible name, keyboard + default button, focus visibility, both-theme contrast — all dimensions PASS; 0 findings for AGT-05 | PASS |
| i18n / string audit | `scripts/string_audit_check.py` on `main_window.py` + `image_import.py` → clean, exit 0 | PASS |
| Coverage gate `pixelart_creator.ui` (S13) | `scripts/coverage_gate.py` exit 0 — line 94.05% (≥90), branch 81.13% (≥80); tools 96.71/83.33 | PASS |
| Full `tests/ui` suite (no regression) | `pytest tests/ui -n auto` → 768 passed, 0 failed | PASS |
| Performance / frame budget (S12) | N/A — import is not a per-frame path (spec §7: "AGT-10 no perf-critical path expected") | N/A |
| DATA slice (SC-D001..D005) | Owned by AGT-04 (Slice A-A) — out of this run's scope | DEFERRED → AGT-04 |

## Ship verdict (CK-D1)

**SHIP-READY (UI slice A-B).** Every in-scope UI acceptance criterion (SC-U001..U009)
has a passing pytest-qt test in both themes; a11y, i18n and the `pixelart_creator.ui`
coverage gate are green; the full `tests/ui` suite is green with no regression.
No S1/S2 failure — CK-D2 not triggered, no issue requested.

Whole-feature ship (A-A + A-B) additionally requires AGT-04's DATA-layer checklist
(SC-D001..D005) to be green; that is out of AGT-06 scope and tracked separately.
