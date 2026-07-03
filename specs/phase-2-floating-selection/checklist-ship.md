# Ship quality checklist — REQ-C floating selection (phase-2-floating-selection)

Run: 2026-07-03 · Owner: AGT-06 (QA) · Skill: sdd-checklist
Context: re-run after the S2 modifier-collision fix (floating COPY reconciled to **Ctrl-only**, CL-F5).
Gate: `specs/phase-2-floating-selection/spec.md` with acceptance criteria + Gherkin — PRESENT.

## Per-requirement / acceptance-criterion items

| # | REQ / Criterion | Evidence | Verdict |
| --- | --- | --- | --- |
| 1 | REQ-P2-UI-030 (SC-U030-1..2) lift on press-inside / press-outside builds new | `test_floating_selection.py::test_sc_u030_1`, `..._u030_2`; `test_selection_overlay.py` — pass (both themes) | PASS |
| 2 | REQ-P2-UI-031 (SC-U031-1..2) drag = MOVE, integer-pixel offset, non-destructive | `test_sc_u031_1`, `test_sc_u031_2` — pass | PASS |
| 3 | REQ-P2-UI-032 (SC-U032-1) **Ctrl-only** drag = COPY, origin intact | `test_sc_u032_1_ctrl_drag_previews_copy_origin_intact[ctrl-at-press\|ctrl-mid-drag]` — pass | PASS |
| 4 | REQ-P2-UI-032 (SC-U032-2) copy-mode affordance signals COPY, both themes | `test_sc_u032_2_copy_mode_affordance_signals_copy` (Ctrl hint) — pass | PASS |
| 5 | REQ-P2-UI-032 (SC-U032-3, CL-F5) Ctrl copies as ONE cmd; Alt interior drag = shipped subtract (no collision) | `test_sc_u032_3_ctrl_copy_commits_one_command_origin_intact` + `test_rect_select_tool.py` subtract tests — pass | PASS |
| 6 | REQ-P2-UI-033 (SC-U033-1..4) release/Enter/tool-switch/tab-switch commit ONE; mask follows | `test_sc_u033_1`, `_u033_2`, `_u033_3_tool_switch`, `_u033_3_tab_switch`, `_u033_4` — pass | PASS |
| 7 | REQ-P2-UI-034 (SC-U034-1..2) ESC restores exactly, no undo entry, mask returns | `test_sc_u034_1`, `test_sc_u034_2` — pass | PASS |
| 8 | REQ-P2-UI-035 (SC-U035-1..3) one-step undo/redo; NN/AA-off; legible both themes | `test_sc_u035_1`, `_u035_2`, `_u035_3` — pass | PASS |
| 9 | REQ-P2-UI-036 (SC-U036-1..3) active-layer scope; off-canvas discard; a11y/i18n | `test_sc_u036_1`, `_u036_2`, `_u036_3` — pass | PASS |

## Cross-cutting gates

| # | Gate | Evidence | Verdict |
| --- | --- | --- | --- |
| C1 | Both themes (light + dark) | autouse `theme` fixture parametrises every `tests/ui` test ×2; full suite 696 passed | PASS |
| C2 | Accessibility | `test_sc_u036_3` (accessible name, keyboard-reachable commit/cancel, `:focus` visible) + `test_a11y_theme.py`, `test_a11y_colour_hub.py`, `test_a11y_phase2_menu.py` — pass | PASS |
| C3 | Coverage gate ≥90 line / ≥80 branch (`--cov=pixelart_creator.ui`) | line **94.44%** (4245/4495), branch **85.12%** (715/840) — branch margin +5.12 pt | PASS |
| C4 | Frame budget ≤16 ms (S12) | not impacted — modifier fix + test edits touch no drawBackground/culling/render path; AGT-10 profiling report unchanged | PASS |
| C5 | i18n / string audit | float-hint string tr()-wrapped (`test_sc_u036_3`); AGT-05 `string_audit_check` PASS on changed ui files; this change is test-only, no new user-visible strings | PASS |
| C6 | No S1/S2 open | prior S2 modifier collision FIXED (AGT-05 `ab169725`) and verified: 4 `test_rect_select_tool.py` subtract tests restored + 42 FB tests green | PASS |

## Verdict (CK-D1)

Every checklist item has passing objective evidence → **SHIP-READY**.
No S1/S2 failure (CK-D2 not triggered) — no GitHub issue required.
