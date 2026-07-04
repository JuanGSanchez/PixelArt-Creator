# Tasks — Phase 8: Automation & Extensibility

| Field | Value |
| --- | --- |
| Feature | `phase-8-automation` |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-04 |
| Over | `plan.md` (Slices 8A command-DSL/dispatcher/macro → 8B plugin host/persistence → 8C batch/procgen → 8D headless CLI → 8E automation UI) |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII); each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table (AGT-03 logic/data code,
AGT-04 logic/data tests, AGT-05 UI code, AGT-06 UI/a11y tests, AGT-07 string audit, AGT-10 perf,
AGT-08 docs, AGT-09 pyproject/CI/commits, AGT-01 architecture/analyze). One owner per task;
deterministic sub-steps name their script. Every REQ maps to ≥1 impl + ≥1 test/verify task. The
**6 [SEC]** scenarios (SC-L001/003/005/007/009/010) each get a dedicated security test.

---

## Slice 8A — command-DSL + trusted dispatcher + macro model (`constants.py`, `scripting.py`, `macro.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T8A-01 | Add the 6 Phase-8 numerics (`MAX_MACRO_STEPS=4096`, `MAX_SCRIPT_OPS=100000`, `MAX_PLUGINS_LOADED=64`, `MAX_BATCH_RECOLOUR_TARGETS=256`, `MAX_PROCGEN_DIMENSION=7680`, `DEFAULT_PROCGEN_SEED=0`) with citations. **Names DISTINCT from every shipped constant (BF-1); `MAX_BATCH_RECOLOUR_TARGETS` ≠ `MAX_BATCH_TARGETS`.** | AGT-03 | `logic/constants.py` | — | LOGIC-013 / SC-L013-1 / plan §8 | todo |
| T8A-02 | `logic/scripting.py` (new): `Op` dataclass; the command **registry** (`register_command(name, factory, schema)`) + module-local op-name vocabulary; `ScriptError`. Registry is the ONLY way an op becomes executable (no back-door). Zero Qt, **no `eval`/`exec`/`compile`**. | AGT-03 | `logic/scripting.py` | T8A-01 | LOGIC-001 / SC-L001-1 | todo |
| T8A-03 | `dispatch(document, ops)` — the trusted dispatcher: validate each op-name against the registry + params against its schema (defensive), construct each reversible `history.Command`, push it, return one grouped `Command` (undoable). `> MAX_SCRIPT_OPS` → `ScriptError`; unknown op / bad params → `ScriptError`. **No untrusted input reaches `eval`/`exec` — the engine executes data, not a language.** | AGT-03 | `logic/scripting.py` | T8A-02 | LOGIC-001, 002, 003, 013 / SC-L001-1, L002-1, L003-1, L013-1 | todo |
| T8A-04 | `logic/macro.py` (new): `Macro` dataclass (`schema_version`/`min_app_version`/`ops`); `record(command_stream)` — capture ordered reversible ops (resolved params + stable `layer_id`/frame ids + `seed`), NOT a pixel diff; `MAX_MACRO_STEPS` bound; `MacroError`. Does **not** import `scripting` (no back-edge). | AGT-03 | `logic/macro.py` | T8A-03 | LOGIC-004 / SC-L004-1 | todo |
| T8A-05 | `replay(document, macro)` — deterministic pure replay via `scripting.dispatch` → one grouped undoable `Command`; **no wall-clock/unseeded-RNG/locale/order-unstable iteration**; state-identical to the original run. | AGT-03 | `logic/macro.py` | T8A-04 | LOGIC-005, 006 / SC-L005-1, L006-1 | todo |
| T8A-06 | Unit + property tests (headless): scripted edit == `Command` on `History` + undoable + **no back-door mutation path** [SEC]; dispatcher passes **no** input to `eval`/`exec` (source scan + crafted malicious payload rejected, never run) [SEC]; deterministic replay == original run twice + no time/random/locale [SEC]; replay is one undoable grouped command; `MAX_SCRIPT_OPS`/`MAX_MACRO_STEPS` bounds from constants. | AGT-04 | `tests/logic/test_scripting.py`, `tests/logic/test_scripting_security.py`, `tests/logic/test_macro.py` | T8A-05 | LOGIC-001, 002, 003, 004, 005, 006, 013 / SC-L001-1, L002-1, L003-1, L004-1, L005-1, L006-1, L013-1 | todo |

## Slice 8B — plugin host + sandbox + persistence (`plugins.py`, `data/macro_io.py`) — pure/Qt-free

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T8B-01 | `logic/plugins.py` (new): `Capability` enum (module-local vocabulary); `PluginManifest` dataclass; `discover()` via `importlib.metadata.entry_points(group="pixelart_creator.plugins")` (inert — no auto-load/auto-run); manifest validation (defensive; malformed/unsupported → `PluginError`). Zero Qt. | AGT-03 | `logic/plugins.py` | T8A-03 | LOGIC-008 / SC-L008-1 | todo |
| T8B-02 | `enable(manifest, granted)` — load + hand a **capability object** exposing ONLY the DSL command-registration/dispatch API + granted caps; **deny-by-default** on ungranted (domain error, no silent bypass); plugin cannot import/reach `ui/`, touch FS/network outside grants, or mutate outside a command; `MAX_PLUGINS_LOADED` bound. Imports `scripting` one-way. | AGT-03 | `logic/plugins.py` | T8B-01 | LOGIC-009, 010, 013 / SC-L009-1, L010-1, L013-1 | todo |
| T8B-03 | `data/macro_io.py` (new): `MacroIOError(ProjectIOError)`; `save_macro`/`load_macro` + `load_manifest` — defensive `eval`-free (de)serialise via the IO-3 pattern (every field type/bounds-checked; malformed/out-of-bounds/unknown-version → `MacroIOError`; **never `eval`/`exec`**); portable paths (`path_portability_check`); round-trip-identical. Zero Qt. | AGT-03 | `data/macro_io.py` | T8A-05 | LOGIC-007 / SC-L007-1 (folded — DEP-4) | todo |
| T8B-04 | Tests (headless): valid plugin loads + registers only via the command path; malformed/unsupported → `PluginError` [SEC]; sandbox denies `ui/` reach / ungranted FS-net / direct mutation [SEC]; deny-by-default capability + `MAX_PLUGINS_LOADED` bound [SEC]; macro save→reload defensive (malformed → `MacroIOError`, no `eval`/`exec`) + round-trip-identical replay [SEC]; `path_portability_check` over new `data/` paths. | AGT-04 | `tests/logic/test_plugins.py`, `tests/logic/test_plugins_sandbox.py`, `tests/data/test_macro_io.py` | T8B-03 | LOGIC-007, 008, 009, 010 / SC-L007-1, L008-1, L009-1, L010-1 | todo |

## Slice 8C — batch recolour + procedural generation (`batch_ops.py`, `procgen.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T8C-01 | `logic/batch_ops.py` (new): `make_batch_recolour_command(targets, mapping)` — **compose `palette_ops` (PS-1** swap/remap/cycle; recolour maths NOT re-implemented) across many targets as ONE transactional reversible command; each per-target output == its single-op counterpart; per-target failure isolated (others uncorrupted); `MAX_BATCH_RECOLOUR_TARGETS` bound. `BatchError`. Zero Qt. | AGT-03 | `logic/batch_ops.py` | T8A-01 | LOGIC-011, 013 / SC-L011-1, L013-1 | todo |
| T8C-02 | `logic/procgen.py` (new): seeded generators — OpenSimplex (patent-safe) + value/gradient noise + cellular automata + dithered gradients (reuse `logic/dither`); `make_procgen_command(document, *, algorithm, params, seed=DEFAULT_PROCGEN_SEED)` — deterministic `(params, seed)` → written via a reversible command over `PixelBuffer` (PB-1), composite via `composite_stack` (CO-4) where a stack is involved; `MAX_PROCGEN_DIMENSION` per-axis clamp; `ProcgenError`. Zero Qt. | AGT-03 | `logic/procgen.py` | T8A-01 | LOGIC-012, 013 / SC-L012-1, L013-1 | todo |
| T8C-03 | Register `batch_recolour` + procgen algorithms as **built-in DSL commands** (so scripts/macros/CLI invoke them declaratively; undoable + macro-recordable by construction). | AGT-03 | `logic/scripting.py` | T8C-01, T8C-02 | LOGIC-001, 011, 012 / SC-L001-1, L011-1, L012-1 | todo |
| T8C-04 | Tests (headless): each batch output == single op + reversible + per-target failure isolation; procgen seeded determinism (same seed → identical content twice) + written via commands + `MAX_PROCGEN_DIMENSION` reject; bounds from constants. | AGT-04 | `tests/logic/test_batch_recolour.py`, `tests/logic/test_procgen.py` | T8C-03 | LOGIC-011, 012, 013 / SC-L011-1, L012-1, L013-1 | todo |

## Slice 8D — headless automation CLI (`data/automation_cli.py`) — Qt-free

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T8D-01 | `data/automation_cli.py` (new): `main(argv)` — `argparse` grammar (`--input/--macro/--output/--seed/--param`); load `.pixproj` via **`project_io.load_project`** (IO-3 → `ProjectIOError`) + `macro_io.load_macro` (→ `MacroIOError`); replay via the SAME `logic/scripting` dispatcher the GUI uses; write OUT via `project_io`; exit 0 ok / 1 `ScriptError`\|`MacroError`\|`PluginError` / 2 bad-args\|`ProjectIOError`\|`MacroIOError`. Placed in `data/` (Qt-free, guarded by `check_layering`). | AGT-03 | `data/automation_cli.py` | T8B-03, T8C-03 | LOGIC-014 / SC-L014-1 | todo |
| T8D-02 | Tests (headless): CLI==GUI **state-identity** for a fixed `.pixproj` + fixed macro (replay via CLI vs via the GUI dispatcher → state-identical `Document`); defensive CLI load (malformed/unknown-version → `ProjectIOError`/`MacroIOError`); exit codes; `path_portability_check` over new `data/` paths. | AGT-04 | `tests/data/test_automation_cli.py` | T8D-01 | LOGIC-014, 002 / SC-L014-1, SC-UI-010-1 | todo |
| T8D-03 | Run `python scripts/check_layering.py` + `python scripts/check_cycles.py`; confirm `scripting → {history, document, macro, procgen, batch_ops}`, `macro → {history, document}` (↛`scripting`), `plugins → scripting` (one-way), `data/macro_io`/`automation_cli` downward-only, all Qt-free, no `logic → data` edge, no cycle. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T8D-01 | Article I / plan §11 | todo |
| T8D-04 | Add the `pyproject` console entrypoint `[project.scripts]` `pixelart-run = "pixelart_creator.data.automation_cli:main"`. **AGT-09 owns pyproject (Article IX).** | AGT-09 | `pyproject.toml` | T8D-01 | LOGIC-014 (entrypoint) | todo |

## Slice 8E — automation UI (macro controls, script runner, plugin manager, panels, worker) — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T8E-01 | `Macro_Controls(QWidget)`: start/stop record (view state, no undo); run/replay (one undoable grouped command == recording); save/load/list via `data/macro_io` (malformed → user-facing error, no crash/execution); `tr()` + `changeEvent`. | AGT-05 | `ui/macro_controls.py`, `ui/main_window.py` | T8D-03 | UI-001, 002, 003 / SC-UI-001-1, 002-1, 003-1 | todo |
| T8E-02 | `Script_Runner_Panel(QWidget)`: run a DSL script over `scripting` on the worker; scripted edits appear as undoable commands; failing script → graceful error. `tr()`. | AGT-05 | `ui/script_runner_panel.py` | T8E-01 | UI-004 / SC-UI-004-1 | todo |
| T8E-03 | `Plugin_Manager_Panel(QWidget)`: install/enable/disable/list; **display declared permissions BEFORE enable**; enabled plugin runs under the capability model; denied/failed → user-facing error (no silent boundary crossing); enable/disable = view state (no undo). `tr()`. | AGT-05 | `ui/plugin_manager_panel.py` | T8E-01 | UI-005, 008 / SC-UI-005-1, 008-1 | todo |
| T8E-04 | `Batch_Recolour_Panel(QWidget)` + `Procgen_Panel(QWidget)`: batch recolour a target set as ONE undoable action (per-target progress/failure isolation); procgen parameters + seed (one undoable command; same seed → same output; reject OOR sizes); `tr()` + units + `changeEvent`. | AGT-05 | `ui/batch_recolour_panel.py`, `ui/procgen_panel.py` | T8E-01 | UI-006, 007 / SC-UI-006-1, 007-1 | todo |
| T8E-05 | `ui/automation_worker.py`: `Automation_Worker(QRunnable)` on a window-owned `QThreadPool` + signals; run the **Qt-free** engine off the GUI thread; progress/result/error over queued signals; cooperative cancel; **no Qt off-thread** (Phase-5/6/7 warmer precedent). Implements the AGT-10 responsiveness directive (DEP-3). | AGT-05 | `ui/automation_worker.py` | T8E-01 | UI-011 / SC-UI-011-1 | todo |
| T8E-06 | `ui/commands.py` extend: one grouped `QUndoCommand` per automation **edit** (script/macro/batch/procgen) delegating to the returned `history.Command`(s); **recording, plugin-enable/disable, and selection push no command**. No domain math. | AGT-05 | `ui/commands.py`, `ui/main_window.py` | T8E-02, T8E-03, T8E-04 | UI-009 / SC-UI-009-1 | todo |
| T8E-07 | pytest-qt tests (both themes, offscreen): record→replay==recording + one undo reverts; malformed macro → graceful error; scripted edits undoable + failing script error; plugin permissions shown before enable + sandboxed run + denied → error [SEC-facing]; batch one-action + per-target isolation + one undo; procgen seed reproduces + undoable + reject OOR; failing/denied/runaway → graceful error + document uncorrupted [SEC-facing]; one grouped `QUndoCommand` per edit + view/session ops none. | AGT-06 | `tests/ui/test_macro_controls.py`, `test_macro_manager.py`, `test_script_runner.py`, `test_plugin_manager.py`, `test_batch_recolour_panel.py`, `test_procgen_panel.py`, `test_automation_errors.py`, `test_automation_undo.py` | T8E-06 | UI-001..009 / SC-UI-001-1..009-1 | todo |
| T8E-08 | pytest-qt parity + responsiveness (both themes): GUI-run automation == CLI-run automation state-identity (drive the dispatcher via the GUI worker and via `automation_cli.main`, assert state-identical); UI stays responsive (processes events / cancel) during a long macro / large batch / big (8K) procgen — behavioural, **NOT** the 16 ms budget. | AGT-06 | `tests/ui/test_automation_parity.py`, `tests/ui/test_automation_responsive.py` | T8E-05, T8D-02 | UI-010, 011 / SC-UI-010-1, 011-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-8 `scripting.py`/`macro.py`/`plugins.py`/`procgen.py`/`batch_ops.py` + `constants.py` extension, the new `data/macro_io.py`/`automation_cli.py`, and the new `ui/` automation modules (marked PLANNED per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-8-automation/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | a11y audit (`a11y-audit`): accessible names/descriptions, keyboard reachability + logical tab order, visible focus on every automation control (macro record/run, macro list, script runner, plugin manager list + install/enable/disable + permission display, batch-target list, procgen parameter/seed fields, progress/cancel). | AGT-06 | `tests/ui/*` | T8E-07, T8E-08 | UI-012 / SC-UI-012-1 | todo |
| TG-04 | Both-theme render verification (role-based colours) across the automation panels + progress/error surfaces. | AGT-06 | `tests/ui/*` | T8E-07, T8E-08 | UI-013 / SC-UI-013-1 | todo |
| TG-05 | String audit (`string_audit_check`): zero unwrapped user-visible strings (macro/script/plugin labels + tooltips, permission text, batch/procgen option labels + units, progress text, dialog titles, error messages); `changeEvent` retranslate on hand-built widgets. | AGT-07 | `ui/*.py` | T8E-06 | UI-014 / SC-UI-014-1 | todo |
| TG-06 | CHANGELOG (`Unreleased`) entries for Phase-8 features tied to REQ-IDs. | AGT-08 | `docs/CHANGELOG.md` | 8A/8B/8C/8D/8E done | Article IX | todo |
| TG-07 | `sdd-checklist` before ship: every REQ has a passing test; the 6 [SEC] invariants green; CLI==GUI + deterministic replay + round-trip green; both themes + a11y + i18n gates green. | AGT-06 | checklist report | all impl+test done | Article IV/V | todo |
</content>
