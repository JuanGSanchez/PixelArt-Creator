# SDD Quality Checklist — Phase 10 Slice B (Collaboration UI)

Owner: AGT-06 (QA Expert) · Skill: sdd-checklist · Scope: Slice B only
(shared projects + member roster/roles, comments view/add/thread/resolve with the
edge-caps, presence roster) over the synchronous loopback `SharedProjectAdapter`.
REQ-P10-UI-009/-010/-011. Slice C (real-time cursors, branching, sync backend) is
**not built** and is out of scope.

Gate: satisfied — `specs/phase-10-cloud-collaboration/spec.md` with acceptance
criteria + Gherkin (SC-UI-009-1 / SC-UI-010-1 / SC-UI-011-1) exists.

## Checklist items and evidence

| Item | Evidence | PASS/FAIL |
| --- | --- | --- |
| REQ-P10-UI-009 shared projects (create/open + roster/roles display + management) | `test_shared_projects_panel.py` (11 tests): `test_sc_ui_009_share_lists_members_through_membership_surface` (share + read-back roster/roles, names no provider), draft add/remove/role, `test_reshare_replaces_roster`; wiring in `test_main_window_phase10_slice_b.py::test_end_to_end_share_flows_through_the_window_session` | PASS |
| REQ-P10-UI-009 edge: `MAX_SHARED_MEMBERS` cap + duplicate + empty guards | `test_max_shared_members_edge_cap_refuses_with_warning` (over-cap → QMessageBox.warning), `test_duplicate_member_is_refused_with_feedback`, `test_share_without_name_is_guarded`, `test_share_error_is_surfaced_not_crashed` (SharedProjectError surfaced, no crash) | PASS |
| REQ-P10-UI-010 comments (view + add + thread + resolve) | `test_comments_panel.py` (12 tests): `test_sc_ui_010_add_view_and_resolve_a_comment` (Open→Resolved), `test_sc_ui_010_reply_is_threaded_under_parent` (parent_id nesting) | PASS |
| REQ-P10-UI-010 edge: `MAX_COMMENT_BYTES` (UTF-8 bytes + live counter) | `test_sc_ui_010_byte_cap_measured_on_utf8_not_chars` (multi-byte payload: char count under cap, UTF-8 bytes over → warning, nothing stored), `test_live_byte_counter_uses_utf8_length`, `test_comment_at_the_byte_cap_is_accepted` (boundary) | PASS |
| REQ-P10-UI-010 edge: `MAX_COMMENTS_PER_PROJECT` rejection with feedback | `test_sc_ui_010_project_comment_cap_rejection_is_surfaced` (adapter cap trips → SharedProjectError surfaced as warning) | PASS |
| REQ-P10-UI-011 presence (shows WHO is present; roster/indicator) | `test_presence_panel.py` (13 tests): `test_sc_ui_011_join_announces_local_presence`, `test_sc_ui_011_shows_who_else_is_present`, `test_leave_clears_local_presence`, `test_presence_is_ephemeral_not_persisted` | PASS |
| REQ-P10-UI-011 NO live cursors (Slice C absence) | `test_sc_ui_011_roster_shows_member_ids_no_live_cursor` (presence entry with a cursor payload renders member id only; no `_cursor_overlay` surface) | PASS |
| Collaboration seam (injectable factory + 4 signals) | `test_collaboration_actions.py` (13 tests): injectable/default factory, `sharedProjectChanged`/`membersChanged`/`commentsChanged`/`presenceChanged` waited on, empty reads before share, SharedProjectError before share, `leave` emits `('')` | PASS |
| REQ-P10-UI-006 a11y (accessible names/roles, keyboard operability, focus order) | `test_collab_a11y_theme.py`: accessible-name tests for all interactive controls on the 3 panels, keyboard-reachable (focus policy ≠ NoFocus), single-selection roster+thread, `:focus` ring in QSS | PASS |
| REQ-P10-UI-007 both themes | autouse `theme` fixture (every UI test × light+dark) + `test_panels_lay_out_under_active_theme_without_inline_colour` (valid sizeHint, no inline stylesheet → role-based QSS) | PASS |
| REQ-P10-UI-008 i18n (UI-level) | `test_panels_retranslate_on_language_change` (F5 LanguageChange → strings repopulate), `test_dock_titles_are_populated_and_retranslate`; AGT-05 report §7: `string_audit_check` clean on all 4 new ui files (AGT-07 owns the audit gate) | PASS |
| Cross: ui coverage ≥90/80 on Slice-B additions | `coverage_gate` exit 0 — line 96.84% / branch 86.17% over the 4 new ui modules (per-module: collaboration_actions 96%, shared_projects_panel 95%, comments_panel 92%, presence_panel 99%; all ≥ threshold) | PASS |
| Cross: `pytest -n auto` no segfault / no regression | Full `tests/ui`: **1632 passed, exit 0**, 54.55 s, no segfault/crash; 3 new dock panels registered in the `_LIVE_UI_INSTANCES` drain registry (`_PHASE9_DISPOSABLE`) so no widget leaks under xdist | PASS |
| Cross: teardown / segfault posture | AGT-05 report §3 confirms NO off-thread worker in Slice B (synchronous over loopback); no new `shutdown_*` wiring needed; regression guard green (drain-fixture additions cover the panels) | PASS |

## Ship verdict

**sdd-checklist verdict: SHIP-READY** (Decision CK-D1 Branch A) — every checklist item
has passing evidence. All three Slice-B acceptance criteria (SC-UI-009-1 / SC-UI-010-1 /
SC-UI-011-1) plus the a11y / both-theme / i18n / coverage / xdist-segfault cross-cutting
gates are green. No outstanding S1/S2 blocker. Slice C remains explicitly out of scope
(not built).
