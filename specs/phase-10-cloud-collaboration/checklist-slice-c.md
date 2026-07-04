# SDD Quality Checklist — Phase 10 Slice C (Real-time + Branching UI)

Owner: AGT-06 (QA Expert) · Skill: sdd-checklist · Scope: Slice C **UI-level** QA gate —
real-time connection wiring + live cursors (REQ-P10-UI-013), art branching
(REQ-P10-UI-012), and the UI wiring of the client transport / real-time apply
(REQ-P10-DATA-010 / REQ-P10-LOGIC-007) exercised over the in-memory loopback transport.
Live provider adapters + the sync backend + the pure logic/data unit contracts are
AGT-04's mocked contract tests (out of this gate). Perf (FLAG-PERFRAME) is AGT-10's and is
DONE (live-cursor overlay PASS ≤1.4 ms; `apply_remote` PASS ≤ 16 ms).

Gate: satisfied — `specs/phase-10-cloud-collaboration/spec.md` with acceptance criteria +
Gherkin (SC-UI-012-1 / SC-UI-013-1 / SC-D010-1 / SC-L007-1/-2) exists.

New test modules (tests/ui, AGT-06): `test_realtime_connection.py`,
`test_live_cursors.py`, `test_branching_ui.py`, `test_realtime_teardown.py`,
`test_slice_c_a11y_theme.py`, `test_slice_c_edges.py` (88 unique tests × light+dark = 176).

## Checklist items and evidence

| Item | Evidence | PASS/FAIL |
| --- | --- | --- |
| REQ-P10-UI-012 art branching (create / switch / merge over the logic model; conflict-free; outcome surfaced) | `test_branching_ui.py`: `test_create_branch_forks_from_mainline`, `test_switch_emits_materialised_document`, `test_merge_is_conflict_free_and_reflects_branch_edits` (a branch's recorded edit survives the merge into a converged Document), `test_merge_completed_summary_carries_name_and_count`; panel: `test_panel_merge_surfaces_conflict_free_outcome` ("conflict-free" readout), `test_panel_create_branch_via_dialog`; window: `test_window_loads_switched_branch_document_into_active_tab` (no QUndoCommand, PL10-D13) | PASS |
| REQ-P10-UI-012 edge/guards (duplicate/mainline name, no base, unknown branch, dialog cancel/warn) | `test_branching_ui.py`: `test_create_duplicate_branch_raises`, `test_create_mainline_named_branch_raises`, `test_merge_mainline_into_itself_raises`, `test_create_branch_without_base_raises`; `test_slice_c_edges.py`: set_base(None) clears, record_on_active mainline no-op, switch/merge unknown raise, panel no-session / no-selection / cancelled-dialog / duplicate-warn guards | PASS |
| REQ-P10-UI-013 live cursors (other collaborators' cursors render on the canvas overlay; roster bounded by `MAX_SHARED_MEMBERS`; disconnect removes a cursor) | `test_live_cursors.py`: `test_apply_presence_adds_a_collaborator_cursor`, `test_set_cursor_and_multiple_collaborators`, `test_roster_is_bounded_by_max_shared_members` (flood capped at MAX_SHARED_MEMBERS), `test_remove_cursor_drops_a_collaborator`, `test_presence_without_cursor_removes_marker`, `test_clear_removes_every_cursor`, `test_local_member_echo_is_not_drawn`, `test_overlay_paints_cursors_and_selection_without_error` (per-frame paint, exposedRect-culled, both themes); window: `test_window_routes_presence_to_active_tab_overlay`, `test_window_disconnect_clears_live_cursors`, `test_window_live_cursor_toggle_sets_overlay_visibility` | PASS |
| REQ-P10-UI-013 ephemeral / Article VII (never persisted; malformed presence ignored) | `test_live_cursors.py::test_malformed_presence_is_ignored`; `test_slice_c_edges.py`: non-numeric cursor ignored, degenerate selection dropped. Overlay holds NO persisted state (never written to `.pixproj`/CRDT sidecar — AGT-05 §3) | PASS |
| REQ-P10-DATA-010 transport wiring (real-time connect/disconnect via INJECTED transport factory; local ops sent; remote update applied on the GUI thread; two in-process clients converge over loopback — no network) | `test_realtime_connection.py`: `test_connect_over_loopback_marks_connected`, `test_local_update_is_sent_and_applied_on_gui_thread` (A's local op relayed to B and folded onto B's live Document — SEC), `test_raster_update_reports_only_touched_dirty_regions` (dirty-rect redraw: only the touched tile), `test_disconnect_leaves_the_relay`; fake-client seam: valid update applies on GUI thread, valid presence routes, malformed frame → `errorOccurred` no crash | PASS |
| REQ-P10-LOGIC-007 realtime apply + branching (UI re-entry) — remote patch applied in place on the GUI thread, dirty regions reported; branch/merge conflict-free | Covered at the UI seam by the DATA-010 + UI-012 rows above (session `_apply_update` → `apply_remote` → `remoteUpdateApplied(regions)`; `_on_remote_update_applied` repaints only the reported rects). Logic-level convergence/branching contract = AGT-04 `test_realtime_apply.py` (out of this gate); AGT-10 FLAG-PERFRAME assessment DONE (`apply_remote` ≤ 16 ms) | PASS |
| Cross: WS-worker teardown / segfault gate (shutdown FIRST; no worker/loop/carrier survives disposal) | `test_realtime_teardown.py`: `test_shutdown_prewarm_stops_realtime_before_dependent_teardown` (ordering: `_realtime_session.shutdown()` runs before the tab scenes), `test_no_realtime_worker_survives_window_disposal` (connect → shutdown_prewarm → shiboken.delete → gc.collect → **no live `pixelart-realtime-worker` thread**), `test_standalone_session_shutdown_joins_worker_and_releases_carrier` (`client._thread is None`, `client._signals is None`, threading.Thread not asyncio), idempotent shutdown, disconnect/reconnect keeps carrier. Client-side uses `threading.Thread` + `queue.Queue` only — NO client asyncio loop (backend-only, never imported by `ui/`) | PASS |
| Cross: drain-fixture additions (new disposables registered) | `tests/ui/conftest.py`: `Branching_Panel` + `Live_Cursors_Overlay` added to `_PHASE9_DISPOSABLE`; `Realtime_Session` tracked via new `_REALTIME_DISPOSABLE` and DRAINED FIRST (`shutdown()`, idempotent + event-loop-free) in `_drain_prewarm_after_test`, then disposed — mirrors `Main_Window.shutdown_prewarm` ordering | PASS |
| Cross: both themes | autouse `theme` fixture — every Slice-C test runs under light + dark (176 = 88 × 2); `test_slice_c_a11y_theme.py::test_panel_lays_out_under_active_theme_without_inline_colour` (valid sizeHint, no inline stylesheet → role-based QSS); overlay paint exercised in both themes | PASS |
| REQ-P10-UI-006 a11y (accessible names/roles, keyboard operability, focus order) | `test_slice_c_a11y_theme.py`: `test_branching_controls_have_accessible_names` (panel/list/buttons/outcome), `test_branching_controls_are_keyboard_reachable` (focusPolicy ≠ NoFocus), `test_visible_focus_indicator_is_themed` (`:focus` in QSS), `test_realtime_actions_have_translatable_text` (live-cursors action checkable/keyboard-operable via the Cloud menu). Overlays are non-interactive ephemeral marks; a11y applies to the controls | PASS |
| REQ-P10-UI-008 i18n (UI-level) | `test_slice_c_a11y_theme.py`: `test_panel_retranslates_on_language_change` (F5 LanguageChange → strings repopulate), `test_branching_strings_are_translatable`, `test_realtime_actions_have_translatable_text`, `test_branching_dock_has_a_title`; AGT-05 §7 + §6: `string_audit_check` clean on all 5 changed ui files (AGT-07 owns the audit gate) | PASS |
| Cross: ui coverage ≥ 90 / 80 on the Slice-C additions | `--cov-branch` over the 4 new ui modules — **line 96% / branch ≈ 91%**, per-module all ≥ threshold: `realtime_worker` 97%, `realtime_actions` 97%, `live_cursors_overlay` 96%, `branching_panel` 93% (line); all branch ≥ 80% | PASS |
| Cross: `pytest -n auto` no segfault / no regression | Full `tests/ui`: **1808 passed, exit 0**, 246.4 s (4:06), no segfault/crash. 1632 (Slice-B baseline) + 176 (Slice-C) = 1808 — no prior test regressed, all new tests green under xdist | PASS |

## Ship verdict

**sdd-checklist verdict: SHIP-READY** (Decision CK-D1 Branch A) — every checklist item has
passing evidence. All Slice-C UI acceptance criteria (SC-UI-012-1 art branching,
SC-UI-013-1 real-time cursors) plus the transport/apply UI wiring (SC-D010-1 / SC-L007-1/-2
at the UI seam) and the a11y / both-themes / i18n / coverage / **ws-worker
teardown-segfault** / xdist cross-cutting gates are green. No outstanding S1/S2 blocker.

Out of this gate (owned elsewhere, not re-verified here): the pure logic/data/backend
convergence + transport + backend contracts (AGT-04 mocked contract tests); live provider
adapters + real WebSocket transport + OAuth (credential-gated, out of CI, CL-B2); the
sync-backend placement + ADR (AGT-01 FLAG-BACKEND); FLAG-PERFRAME profiling (AGT-10, DONE).
