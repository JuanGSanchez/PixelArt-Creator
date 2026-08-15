# Traceability Matrix — Phase 8: `phase-8-automation`

REQ-ID ↔ dossier `S-id` / research `F` / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) ↔ test id(s).

**Mode:** SHIPPED / POST-IMPLEMENTATION (re-verified at the Phase-8 FINAL architecture gate, AGT-01,
2026-07-04). Every REQ has **≥1 acceptance scenario in `spec.md §11`** AND **≥1 shipped test module**
— AGT-04 (logic/data, headless, incl. the first-class security tests) and AGT-06 (UI, both themes)
have landed all modules. The **[SEC]** rows are the phase's paramount security invariants (Article VII)
and each has a dedicated shipped security test. The Test id(s) column names the *shipped* module +
behaviour; all referenced modules exist on disk under `tests/`.

Status legend:
- **covered (shipped)** — has ≥1 Gherkin acceptance scenario in `spec.md §11` AND ≥1 shipped test
  module on disk. (no REQ is `uncovered`: every REQ has both impl + ≥1 test. **0 uncovered**.)

## Logic requirements (`logic/scripting.py` + `logic/macro.py` + `logic/plugins.py` new; `logic/constants.py` extend)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) (shipped) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P8-LOGIC-001 **[SEC]** | **HIS-1** (`history` command pattern), **DOC-1**, S7, C1 | §4, §11 | SC-L001-1 | `tests/logic/test_scripting.py` (scripted edit == Command on History; undoable; no back-door mutation) | covered (shipped) |
| REQ-P8-LOGIC-002 | Article I, S11, Phase-8 cap | §4, §11 | SC-L002-1 | headless-drivable is demonstrated by the pure-logic suite itself (no QApplication anywhere in it): `test_scripting.py::test_dispatch_valid_multiop_is_one_reversible_group_single_undo`, `::test_dispatch_group_with_seeded_procgen_replays_identically`, `::test_dispatch_atomic_invalid_last_op_leaves_document_identical`, `::test_dispatch_atomic_midapplication_factory_failure_rolls_back`, `::test_procgen_op_applies_reversibly`. The Qt-free / no-event-loop half stays script-gated by `check_layering`/`check_cycles` (exit 0). | covered (shipped) |
| REQ-P8-LOGIC-003 **[SEC]** | **Article VII §1**, **IO-3**, S7 | §4, §11 | SC-L003-1 | `tests/logic/test_scripting_security.py` (no untrusted input → eval/exec; defensive reject) | covered (shipped) |
| REQ-P8-LOGIC-004 | **HIS-1**, Phase-8 cap (macro record), S7 | §4, §11 | SC-L004-1 | `tests/logic/test_macro.py` (record = ordered reversible ops, not pixel diff) | covered (shipped) |
| REQ-P8-LOGIC-005 **[SEC]** | P2, Phase-8 cap (macro replay), S6, S7 | §4, §11 | SC-L005-1 | `tests/logic/test_macro.py` (deterministic replay == original run; no time/random/locale) | covered (shipped) |
| REQ-P8-LOGIC-006 | **HIS-1**, S7, C1 | §4, §11 | SC-L006-1 | `tests/logic/test_macro.py` (replay is one undoable grouped command) | covered (shipped) |
| REQ-P8-LOGIC-007 **[SEC]** *(prefix flagged)* | **IO-3** (`project_io` pattern), **Article VII §1**, P2 | §4, §11 | SC-L007-1 | `tests/data/test_macro_io.py` (defensive `eval`-free load; malformed → ProjectIOError; round-trip-identical replay) | covered (shipped) |
| REQ-P8-LOGIC-008 | Phase-8 cap (plugin system), Article XI, S6 | §4, §11 | SC-L008-1 | `tests/logic/test_plugins.py` (versioned/declared-capability contract; malformed rejected) | covered (shipped) |
| REQ-P8-LOGIC-009 **[SEC]** | **Article VII**, Article I, Phase-8 cap (sandbox), S11 | §4, §11 | SC-L009-1 | `tests/logic/test_plugins_sandbox.py` (no ui/ reach; no ungranted FS/net; no direct mutation) | covered (shipped) |
| REQ-P8-LOGIC-010 **[SEC]** | **Article VII**, Phase-8 cap, S12 | §4, §11 | SC-L010-1 | `tests/logic/test_plugins_sandbox.py` (deny-by-default capability; MAX_PLUGINS_LOADED bound) | covered (shipped) |
| REQ-P8-LOGIC-011 | **PS-1** (`palette_ops` recolour), P2, Phase-8 cap (batch recolour), S6 | §4, §11 | SC-L011-1 | `tests/logic/test_batch_recolour.py` (each batch output == single op; reversible; per-target failure isolated) | covered (shipped) |
| REQ-P8-LOGIC-012 | **PB-1**, **CO-4**, P2, Phase-8 cap (procedural gen), S6 | §4, §11 | SC-L012-1 | `tests/logic/test_procgen.py` (seeded determinism; written via commands; MAX_PROCGEN_DIMENSION) | covered (shipped) |
| REQ-P8-LOGIC-013 | Article II, Article VII, S12 | §4, §11 | SC-L013-1 | `tests/logic/test_scripting.py` / `test_macro.py` / `test_batch_recolour.py` (bounds from constants enforced) | covered (shipped) |
| REQ-P8-LOGIC-014 | **IO-3**, **DOC-1**, **CLI-1** (`export_cli` precedent), P2, S11 | §4, §11 | SC-L014-1 | `tests/data/test_automation_cli.py` + `tests/ui/test_automation_parity.py` (CLI==GUI result-identity) | covered (shipped) |

## UI requirements (`ui/` macro controls / script runner / plugin manager / batch-recolour + procedural panels)

| REQ-ID | Traces (S-id / F / inherited) | Spec § | Scenario(s) | Test id(s) (shipped) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P8-UI-001 | REQ-P8-LOGIC-004 | §4, §11 | SC-UI-001-1 | `tests/ui/test_macro_controls.py` (start/stop record; recording not undoable) | covered (shipped) |
| REQ-P8-UI-002 | REQ-P8-LOGIC-005, -006 | §4, §11 | SC-UI-002-1 | `test_macro_controls.py::test_sc_ui_002_replay_is_one_undoable_action_that_reverts_exactly`, `::test_sc_ui_002_replay_is_deterministic_same_seed` | covered (shipped) |
| REQ-P8-UI-003 | REQ-P8-LOGIC-007 | §4, §11 | SC-UI-003-1 | `tests/ui/test_macro_manager.py` (save/load/list; malformed → graceful error) | covered (shipped) |
| REQ-P8-UI-004 | REQ-P8-LOGIC-001, -002, -003 | §4, §11 | SC-UI-004-1 | `tests/ui/test_script_runner.py` (scripted edits undoable; failing script → error) | covered (shipped) |
| REQ-P8-UI-005 **[SEC-facing]** | REQ-P8-LOGIC-008, -009, -010 | §4, §11 | SC-UI-005-1 | `tests/ui/test_plugin_manager.py` (permissions shown before enable; sandboxed run; denied → error) | covered (shipped) |
| REQ-P8-UI-006 | REQ-P8-LOGIC-011 | §4, §11 | SC-UI-006-1 | `tests/ui/test_batch_recolour_panel.py` (multi-target one action; per-target progress/failure; one undo) | covered (shipped) |
| REQ-P8-UI-007 | REQ-P8-LOGIC-012 | §4, §11 | SC-UI-007-1 | `tests/ui/test_procgen_panel.py` (seed reproduces output; undoable; reject OOR) | covered (shipped) |
| REQ-P8-UI-008 **[SEC-facing]** | Article VII, REQ-P8-LOGIC-003, -009, -010, -013 | §4, §11 | SC-UI-008-1 | `tests/ui/test_automation_errors.py` (malformed/denied/runaway → graceful error; document uncorrupted) | covered (shipped) |
| REQ-P8-UI-009 | S7, C1, F1, REQ-P8-LOGIC-001, -006 | §4, §11 | SC-UI-009-1 | `tests/ui/test_automation_undo.py` (one grouped QUndoCommand per edit; view/session ops none) | covered (shipped) |
| REQ-P8-UI-010 | REQ-P8-LOGIC-002, -014, P2 | §4, §11 | SC-UI-010-1 | `tests/ui/test_automation_parity.py` (GUI == CLI result; GUI adds no engine logic) | covered (shipped) |
| REQ-P8-UI-011 (NFR) | S1, S12, Article VI, DEP-3 | §5, §11 | SC-UI-011-1 | `tests/ui/test_automation_responsive.py` (event processing / cancel during long automation) | covered (shipped) |
| REQ-P8-UI-012 | Article V §1 (NFR) | §5, §11 | SC-UI-012-1 | `test_automation_a11y.py::test_sc_ui_012_macro_controls_expose_accessible_names`, `::test_sc_ui_012_script_runner_exposes_accessible_names`, `::test_sc_ui_012_plugin_manager_exposes_accessible_names`, `::test_sc_ui_012_batch_recolour_exposes_accessible_names`, `::test_sc_ui_012_procgen_exposes_accessible_names_and_units`, `::test_sc_ui_012_controls_are_keyboard_focusable`, `::test_sc_ui_012_automation_menu_is_populated`; AGT-06 `a11y-audit` | covered (shipped) |
| REQ-P8-UI-013 (NFR) | Article V §3 | §5, §11 | SC-UI-013-1 (+ every UI scenario in both themes) | both-theme `[light]`/`[dark]` fixtures across the `tests/ui/test_*.py` automation modules | covered (shipped) |
| REQ-P8-UI-014 | Article V §2, F6 (NFR) | §5, §11 | SC-UI-014-1 | **retranslate clause (partial):** `test_automation_panels_edges.py` → `test_procgen_retranslate_branch` (written in prose, not as a parseable test id, because it does NOT cover this REQ — recording it would close the question falsely) — the ONLY Phase-8 retranslate assertion found (PA-08 search, 2026-08-15); it covers the procgen panel alone, not the macro / script-runner / plugin-manager / batch-recolour panels. **The "no bare literal / every string `tr()`-wrapped" clause is script-gated** by AGT-07 `string_audit_check`. **Test owed → AGT-06:** extend the `LanguageChange` assertion to the remaining four automation panels. | covered (procgen only); **retranslate test owed (AGT-06)** |

## DATA requirements — none reserved (see PREFIX-NOTE)

> **No `REQ-P8-DATA-*` prefix was reserved** for Phase 8. Automation genuinely needs a **data-layer
> serialiser** (recorded macros / plugin manifests / script inputs). Its **observable security
> contract** — defensive, `eval`-free load via the IO-3 pattern, round-trip-identical replay — is
> fixed under **REQ-P8-LOGIC-007** and its expected test modules are `tests/data/test_macro_io.py`
> and `tests/data/test_automation_cli.py`. **DEP-4 (flagged to orchestrator / AGT-01):** allocate a
> `REQ-P8-DATA-*` prefix at plan time **if** AGT-01 decides the serialiser warrants its own data-layer
> REQ(s), else keep it folded under REQ-P8-LOGIC-007. **Not acceptance-changing** — the contract is
> fixed regardless of placement.

## Coverage summary

- **28 of 28 REQ-IDs** (14 LOGIC + 14 UI + 0 DATA) have **≥1 acceptance scenario** in `spec.md §11`
  AND **both shipped impl + ≥1 shipped test module** (**0 uncovered**). Shipped test modules:
  `tests/logic/{test_scripting,test_scripting_security,test_macro,test_plugins,test_plugins_sandbox,
  test_procgen,test_batch_recolour}.py`, `tests/data/{test_macro_io,test_automation_cli}.py`, and the
  `tests/ui/` automation modules (`test_macro_controls,test_macro_manager,test_script_runner,
  test_plugin_manager,test_batch_recolour_panel,test_procgen_panel,test_automation_errors,
  test_automation_undo,test_automation_parity,test_automation_responsive,test_automation_a11y,
  test_automation_teardown,test_automation_worker_unit,test_automation_panels_edges`).
- **28 Gherkin scenarios**, including **6 first-class security scenarios**: SC-L001-1
  (reversible-command-only edit), SC-L003-1 (no untrusted input → eval/exec), SC-L005-1
  (deterministic identical replay), SC-L007-1 (defensive persistence), SC-L009-1 (sandbox / no
  layer-boundary bypass), SC-L010-1 (deny-by-default capability) — plus the [SEC-facing] UI scenarios
  SC-UI-005-1 and SC-UI-008-1.
- SDD order COMPLETE: specify+clarify → plan (ADR-0021/0022) → tasks → analyze (PASS) → implement →
  test → checklist (SHIP-READY). Logic/data tests by AGT-04 (headless, incl. security tests), UI tests
  by AGT-06 (both themes). Re-verified at the FINAL architecture gate (AGT-01, 2026-07-04):
  check_layering exit 0, check_cycles exit 0, no `eval`/`exec` on any automation path.
- The NFRs: REQ-P8-UI-014 (i18n) will carry `string_audit_check` script evidence at ship;
  REQ-P8-UI-011 (responsiveness) is a behavioural pytest-qt assertion (event processing / cancel
  during long automation) — **not** the 16 ms canvas frame budget, which does not apply to automation
  (spec §5).

## Forward-inherited primitive traces (Article X §2 — explicit)

The prompt directs Phase 8 to formally reflect what it inherits forward vs. builds new:

| Inherited primitive | Origin | Phase-8 forward trace |
| --- | --- | --- |
| **HIS-1** — `logic/history.py` `Command` (`execute`/`undo`), `FunctionCommand`, `PixelEdit`, `History` — the reversible-command path | `logic/history.py` (Phase 1, shipped) | → REQ-P8-LOGIC-001 (scripting edits only via a Command) → -004/-006 (macro = ordered commands; replay undoable) → REQ-P8-UI-009 (one grouped QUndoCommand per automation edit) |
| **DOC-1** — the `Document` tree | `logic/document.py` (Phase 1, shipped) | → REQ-P8-LOGIC-001 / -014 (the automation subject; CLI Document == GUI Document) |
| **PB-1** — `PixelBuffer` (`.data`/`.region`/`.blit`) | `logic/pixel_buffer.py` (Phase 1, shipped) | → REQ-P8-LOGIC-012 (procedural gen writes pixels via commands) |
| **CO-4** — `blend.composite_stack` (layer-stack flatten) | `logic/blend.py` (Phase 4, shipped) | → REQ-P8-LOGIC-012 (procedural gen composites a layer stack where involved) |
| **PS-1** — `palette_ops` recolour / palette-swap | `logic/palette_ops.py` (Phase 3, shipped) | → REQ-P8-LOGIC-011 (batch recolour composes recolour; not re-implemented) |
| **IO-3** — `data/project_io.py` defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib`) | `data/project_io.py` (Phase 1/4, shipped) | → REQ-P8-LOGIC-003 (no eval/exec) → REQ-P8-LOGIC-007 (defensive macro/plugin/script load) → REQ-P8-LOGIC-014 (CLI input load) |
| **CLI-1** — `data/export_cli.py` Qt-free headless CLI entrypoint (imports only `logic/`+`data/`) | `data/export_cli.py` (Phase 7, shipped) | → REQ-P8-LOGIC-014 (automation CLI placement lesson: headless, Qt-free, GUI-identical) |

## Cross-layer trace (UI binds to new logic)

| UI REQ | Binds to logic REQ / shipped | Note |
| --- | --- | --- |
| REQ-P8-UI-001 | REQ-P8-LOGIC-004 | record controls drive the macro model |
| REQ-P8-UI-002 | REQ-P8-LOGIC-005/-006 | replay == recording; one undo |
| REQ-P8-UI-003 | REQ-P8-LOGIC-007 | defensive save/load; graceful error |
| REQ-P8-UI-004 | REQ-P8-LOGIC-001/-002/-003 | script runner over the pure engine; edits undoable |
| REQ-P8-UI-005 | REQ-P8-LOGIC-008/-009/-010 | plugin manager; permissions shown before enable; sandboxed |
| REQ-P8-UI-006 | REQ-P8-LOGIC-011 | batch-recolour panel over the deterministic batch op |
| REQ-P8-UI-007 | REQ-P8-LOGIC-012 | procedural panel; seed reproduces output |
| REQ-P8-UI-008 | REQ-P8-LOGIC-003/-009/-010/-013 | graceful/denied automation error surfacing |
| REQ-P8-UI-009 | REQ-P8-LOGIC-001/-006 | one grouped QUndoCommand per automation edit |
| REQ-P8-UI-010 | REQ-P8-LOGIC-002/-014 | GUI automation == CLI (same pure engine) |

## Dependency / gap list (for AGT-01 `sdd-plan` / `sdd-analyze`)

- **DEP-1 (Researcher — SECURITY-FOCUSED).** `docs/research-phase8-automation.md` grounds the
  scripting security-model options (data-driven DSL / RestrictedPython / OS isolation /
  trusted-with-consent), the plugin isolation mechanism, the macro file-format / versioning landscape,
  and procedural-generation algorithm families — **being produced in parallel** (feeds AGT-01). AGT-01
  must not invent the security model; the observable security contracts + automation-parity defaults
  (spec §10) are fixed regardless.
- **DEP-2 (AGT-01 / plan/ADR).** (a) scripting security model; (b) plugin isolation mechanism;
  (c) plugin manifest / capability-grant vocabulary + registry format; (d) macro file format /
  versioning; (e) CLI entrypoint location/grammar; (f) procedural-gen algorithm set. Each is a HOW
  decision; the observable contracts (no eval/exec on untrusted input; edits only via reversible
  commands; deterministic replay; sandbox cannot bypass boundaries; CLI==GUI) are fixed. **An ADR is
  expected for the security model (a/b)** (Article VII), grounded by DEP-1.
- **DEP-3 (AGT-01 / AGT-10).** Worker-thread vs GUI-thread for REQ-P8-UI-011 responsiveness — the pure
  engine is thread-agnostic (Qt-free). Plan-level; automation is **not** the 16 ms render loop.
- **DEP-4 (AGT-01 / orchestrator — PREFIX).** Allocate a `REQ-P8-DATA-*` prefix for the
  macro/plugin/script serialiser at plan time, or keep it folded under REQ-P8-LOGIC-007. **Not
  acceptance-changing.**
- **Article II watch (BF-1).** AGT-01 must place `MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS`,
  `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED`
  in `logic/constants.py` (no literals).
- **Article I / VII watch (BF-2).** All scripting/macro/plugin/procedural engine logic must be Qt-free
  (`logic/`+`data/`), the CLI entrypoint must import no Qt (CLI-1 mirror), the plugin sandbox must not
  reach `ui/`, and **no untrusted input may reach `eval`/`exec`** — this is the phase's paramount
  invariant (REQ-P8-LOGIC-003/-009). Automation edits push one grouped `QUndoCommand` via
  `ui/commands.py` (REQ-P8-UI-009).

## Recommended slicing (logic-first vertical slices)

1. **Slice A — scripting engine core (logic).** REQ-P8-LOGIC-001, -002, -003, -013 (`logic/scripting.py`:
   reversible-command-only API, Qt-free engine, no-eval/exec invariant, bounds). ADR for the security
   model (AGT-01, DEP-2) grounded by the Researcher (DEP-1). AGT-03 + AGT-04 (security tests).
2. **Slice B — macro record/replay + persistence (logic/data).** REQ-P8-LOGIC-004, -005, -006, -007
   (`logic/macro.py`; defensive serialiser; deterministic identical replay). AGT-03 + AGT-04.
3. **Slice C — plugin host + sandbox (logic).** REQ-P8-LOGIC-008, -009, -010 (`logic/plugins.py`;
   isolation mechanism per DEP-2; deny-by-default). AGT-03 + AGT-04 (security tests).
4. **Slice D — batch recolour + procedural gen (logic).** REQ-P8-LOGIC-011, -012 (compose PS-1;
   seeded determinism via commands). AGT-01 fixes the procgen algorithm set (DEP-2). AGT-03 + AGT-04.
5. **Slice E — headless automation CLI (logic/data).** REQ-P8-LOGIC-014 (Qt-free entrypoint;
   CLI==GUI). AGT-01 fixes the CLI grammar (DEP-2). AGT-03 + AGT-04.
6. **Slice F — automation UI (macro controls, script runner, plugin manager, panels).**
   REQ-P8-UI-001..009, -012..014. AGT-05 + AGT-06.
7. **Slice G — headless parity + responsiveness.** REQ-P8-UI-010, -011 (coordinated with AGT-10,
   DEP-3). AGT-05 + AGT-06 + AGT-10.

## Notes for `sdd-analyze` (AGT-01)

- Spec + matrix are internally consistent: 28 REQs, 28 with scenarios, 0 uncovered; tests `pending`
  (forward). SDD order: specify+clarify (this) → plan → tasks → analyze → implement → test.
- **No open clarification** (spec §10): all 16 ambiguities resolved with grounded defaults; the
  security-model / isolation / macro-format / CLI-grammar / procgen-set scope risks are named HOW
  decisions (DEP-1/DEP-2), not suspended, and every scripting/plugin/macro/procedural REQ is phrased
  around the observable security + behaviour contract so those choices do not change acceptance.
- **Four named dependencies** (DEP-1 Researcher security grounding, DEP-2 AGT-01 plan/ADR — ADR
  expected for the security model, DEP-3 AGT-01/AGT-10 responsiveness, DEP-4 AGT-01/orchestrator
  `REQ-P8-DATA-*` prefix) must be resolved/allocated before/within the plan — none blocks this spec.
- **Security-sensitive phase:** Article VII is central. The six [SEC] / [SEC-facing] scenarios must
  each map to a dedicated AGT-04 / AGT-06 security test at ship.
