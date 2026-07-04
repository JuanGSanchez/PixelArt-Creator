# Ship quality checklist — Phase 8 automation UI (phase-8-automation)

Run: 2026-07-04 · Owner: AGT-06 (QA) · Skill: sdd-checklist
Context: re-run after AGT-03's **atomic-dispatch fix** closed the S2 blocker
SC-UI-008-1 (a failed multi-op automation script must leave the `Document`
byte-identical, off the undo stack). The strict-xfail that pinned the defect in
`tests/ui/test_automation_errors.py` has been REMOVED and the criterion now passes.
Gate: `specs/phase-8-automation/spec.md` with acceptance criteria + Gherkin (§11) — PRESENT.

## Per-requirement / acceptance-criterion items (UI, both themes)

| # | REQ / Criterion | Evidence (`tests/ui/…`, both `[light]`/`[dark]`) | Verdict |
| --- | --- | --- | --- |
| 1 | REQ-P8-UI-001 (SC-UI-001-1) macro record start/stop; recording not undoable | `test_macro_controls.py` — pass | PASS |
| 2 | REQ-P8-UI-002 (SC-UI-002-1) replay == recording; one undo reverts | `test_macro_controls.py` — pass | PASS |
| 3 | REQ-P8-UI-003 (SC-UI-003-1) macro save/load/list; malformed → graceful error | `test_macro_manager.py` — pass | PASS |
| 4 | REQ-P8-UI-004 (SC-UI-004-1) script runner; scripted edit is one undoable command; failing script → error | `test_script_runner.py::test_sc_ui_004_script_edit_is_one_undoable_command`, `..._unknown_op_script_surfaces_graceful_error`, `..._invalid_json_rejected_before_dispatch` — pass | PASS |
| 5 | REQ-P8-UI-005 **[SEC-facing]** (SC-UI-005-1) plugin manager; permissions shown before enable; sandboxed run; denied → error | `test_plugin_manager.py` — pass | PASS |
| 6 | REQ-P8-UI-006 (SC-UI-006-1) batch-recolour panel; multi-target one action; one undo | `test_batch_recolour_panel.py` — pass | PASS |
| 7 | REQ-P8-UI-007 (SC-UI-007-1) procgen panel; seed reproduces output; undoable; reject out-of-range | `test_procgen_panel.py` — pass | PASS |
| 8 | REQ-P8-UI-008 **[SEC-facing]** (SC-UI-008-1) failing/denied/runaway automation → graceful error, **document uncorrupted (atomic)** | `test_automation_errors.py::test_sc_ui_008_unknown_op_surfaces_error_document_uncorrupted`, `..._out_of_range_procgen_surfaces_error_uncorrupted`, `..._runaway_script_hits_bound_gracefully`, **`..._multiop_script_failure_is_atomic` (xfail REMOVED — now PASSES)**, **`..._valid_multiop_run_is_one_undoable_step` (NEW)** — pass | PASS |
| 9 | REQ-P8-UI-009 (SC-UI-009-1) one grouped QUndoCommand per automation edit; view/session ops none | `test_automation_undo.py::test_sc_ui_009_each_edit_is_exactly_one_grouped_command`, `..._recording_and_selection_push_no_command`, `..._plugin_enable_disable_push_no_command` — pass | PASS |
| 10 | REQ-P8-UI-010 (SC-UI-010-1) GUI-run automation == CLI-run automation (headless parity) | `test_automation_parity.py` — pass | PASS |
| 11 | REQ-P8-UI-011 (NFR, SC-UI-011-1) UI responsive / cancellable during long-running automation | `test_automation_responsive.py` — pass | PASS |
| 12 | REQ-P8-UI-012 (NFR, SC-UI-012-1) accessibility: accessible names / keyboard / focus | `test_automation_a11y.py` + AGT-06 `a11y-audit` — pass | PASS |
| 13 | REQ-P8-UI-013 (NFR, SC-UI-013-1) both themes correct | every `tests/ui` automation module runs ×2 via the autouse `theme` fixture — pass | PASS |
| 14 | REQ-P8-UI-014 (NFR, SC-UI-014-1) all user-visible automation strings translatable | tr()-wrapped automation UI + `changeEvent` retranslate; AGT-07 `string_audit_check` (owner AGT-07); this QA change is test-only, adds no user-visible strings | PASS |

## Cross-cutting gates

| # | Gate | Evidence | Verdict |
| --- | --- | --- | --- |
| C1 | Both themes (light + dark) | autouse `theme` fixture parametrises every `tests/ui` test ×2; **full `tests/ui` suite 1262 passed, 0 failed, 0 xfail** under `-n auto` | PASS |
| C2 | Accessibility | `test_automation_a11y.py` (accessible names, keyboard-reachable controls, `:focus` visible) + `test_a11y_theme.py` — pass | PASS |
| C3 | Coverage gate ≥90 line / ≥80 branch (`--cov=pixelart_creator.ui`) | `coverage_gate.py` exit 0 — **`pixelart_creator.ui` line 94.07% / branch 81.38%**; `pixelart_creator.ui.tools` 96.71% / 83.33%; automation module `ui/automation_worker.py` line 98.20% / branch 100.00% (was 97.61/89.29 — no regression) | PASS |
| C4 | Frame budget ≤16 ms (S12) | N/A — automation is **not** the 16 ms canvas render loop (spec §5); AGT-10 profiling path untouched by this QA change | PASS |
| C5 | i18n / string audit | REQ-P8-UI-014; AGT-07 `string_audit_check` (owner); this change is test-only, no new user-visible strings | PASS |
| C6 | No S1/S2 open | **prior S2 SC-UI-008-1 atomicity defect CLOSED** by AGT-03's atomic dispatch (validate-all-up-front → one GroupCommand → reverse-order rollback); verified at UI level: failed multi-op run leaves the document byte-identical + pushes no command, and a valid multi-op run is one undoable step (both themes). No worker crash / no teardown slowdown (`shutdown_prewarm` intact). | PASS |

## Verdict (CK-D1)

Every checklist item has passing objective evidence → **SHIP-READY (Phase-8 UI QA PASS)**.
The prior S2 blocker (SC-UI-008-1 automation atomicity) is CLOSED — CK-D2 no longer
triggered; no open S1/S2, so no GitHub issue / HOLD required.
