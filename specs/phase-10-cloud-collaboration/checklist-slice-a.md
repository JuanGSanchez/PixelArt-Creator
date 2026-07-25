# SDD Quality Checklist — Phase 10 Slice A (Cloud UI)

Owner: AGT-06 (QA Expert) · Skill: sdd-checklist · Scope: Slice A only
(cloud connect/disconnect + fake adapter, `.pixproj` round-trip, version history +
restore, autosave/recovery UI). REQ-P10-UI-001..008. Slice B/C not in scope.

Gate: satisfied — `specs/phase-10-cloud-collaboration/spec.md` with acceptance
criteria + Gherkin exists.

## Checklist items and evidence

| Item | Evidence | PASS/FAIL |
| --- | --- | --- |
| REQ-P10-UI-001 save/load | `test_cloud_save_load.py`, `test_cloud_jobs.py` | PASS |
| REQ-P10-UI-002 version browser | `test_version_history_browser.py` | PASS |
| REQ-P10-UI-003 recovery (Recover/Discard, no-clobber, recovered-copy restore) | `test_recovery_prompt.py` — all 10 PASS both themes; `test_sc_ui_003_startup_recover_opens_recovered_tab` asserts the real recovered working copy (geometry + palette) restored from the recovery slot via `make_recover_job` -> `port.get_recovery` | **PASS** |
| REQ-P10-UI-004 connect | `test_cloud_connect.py` | PASS |
| REQ-P10-UI-005 responsive/off-thread | `test_cloud_responsive.py`, `test_cloud_jobs.py` | PASS |
| REQ-P10-UI-006 a11y | `test_cloud_a11y_theme.py` + a11y-audit | PASS |
| REQ-P10-UI-007 both themes | autouse `theme` fixture (all tests x2: light+dark) | PASS |
| REQ-P10-UI-008 i18n (UI-level) | retranslate test; AGT-07 `string_audit_check` clean | PASS |
| Cross: ui coverage >=90/80 | `coverage_gate` exit 0 on Slice-A cloud UI modules (line 97.5% / branch 87.5%; per-module: recovery_prompt 100%, cloud_worker 97%, version_history_browser 97%, cloud_actions 91%) | PASS |
| Cross: `pytest -n auto` no segfault/regress | `1518 passed, 0 xfailed`, exit 0, no segfault/crash | PASS |
| Cross: worker teardown deterministic | `test_cloud_teardown.py` regression assertions | PASS |

## Ship verdict

**sdd-checklist verdict: SHIP** (Decision CK-D1 Branch A) — every checklist item
has passing evidence. The sole prior S2 blocker (REQ-P10-UI-003 autosave-recovery
restore) is RESOLVED by AGT-05 (`make_recover_job` -> `port.get_recovery` wired into
`Main_Window._maybe_prompt_recovery`) and verified by AGT-06: the strict-xfail marker
was removed and the acceptance test now asserts the real recovered working copy in
both themes. No outstanding S1/S2. Verdict updated from HOLD -> SHIP.
