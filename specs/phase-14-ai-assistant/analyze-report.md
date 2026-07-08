# Analyze Report (C1) — Phase 14: In-App, Model-Agnostic AI Assistant

| Field | Value |
| --- | --- |
| Feature | `phase-14-ai-assistant` |
| Author | Claude (AGT-01, Architecture) via `sdd-analyze` |
| Date | 2026-07-08 |
| Pass | **FINAL / POST-IMPLEMENTATION** (T14-X01 — all six slices 14A–14F SHIPPED; supersedes the 2026-07-08 forward/pre-implementation C1) |
| Artifacts | `constitution.md`, `specs/phase-14-ai-assistant/{spec.md, acceptance.md, traceability.md, plan.md, tasks.md}` + ADR-0039/0040/0041/0042 (private) + the landed `pixelart_creator/{logic,data,ui}` modules and `tests/` |
| **Verdict** | **PASS — every REQ IMPLEMENTED + TRACED to a landed test; all six security invariants covered (incl. SC-L005-3 turn-atomicity); five script roots exit 0; zero unresolved cross-artifact findings. Phase 14 is COMPLETE.** |

---

## 0. Gate precondition

All four required artifacts exist and parse: `constitution.md`, `spec.md`, `plan.md`, `tasks.md`
(+ `acceptance.md`, `traceability.md`). Gate precondition met (no AN-E1/AN-E2). This is the **final** C1:
it re-runs the cross-artifact check against the **shipped code + landed tests**, not just the forward
artifacts.

## 1. Spec ↔ constitution compliance (verified against shipped code)

| Article | Requirement | Status |
| --- | --- | --- |
| I — three-layer purity | logic/data Qt-free; ui only Qt; one-way deps; no cycle | **PASS** — `check_layering --root pixelart_creator` clean (194 modules) + `--root .` clean (5) exit 0; `check_cycles --root {pixelart_creator, sync_backend, web_viewer}` no cycles exit 0 (196/3/9). The loop (`logic/assistant.py`) reaches the port (`data/llm/`) via the `logic`-side `ChatBackend` Protocol + injection — **no `logic → data` edge**; `data/llm/` imports only `logic` types + stdlib. No new top-level package. |
| II — single-source constants | every numeric once in `constants.py` | **PASS** — 5 named caps landed in `logic/constants.py` (`MAX_ASSISTANT_TURNS=16`, `MAX_TOOL_CALLS_PER_TURN=8`, `MAX_TOOL_RESULT_BYTES=65536`, `MAX_CONVERSATION_MESSAGES=256`, `ASSISTANT_REQUEST_TIMEOUT_S=60`), distinct from every shipped constant; bounds tests read them (no literals). |
| III — formatted/linted/typed | Black/isort/flake8/mypy | **PASS** — each slice's commit landed under the local quality gate. |
| IV — headless coverage, one-per-criterion | fake adapter, ≥90/80 | **PASS** — whole contract CI-testable via the fake `LLMPort` (`tests/data/test_llm_fake_adapter.py`), no key/network; live path `@assistant_live` deselected. |
| V — a11y / i18n / both themes | UI | **PASS** — `tests/ui/test_assistant_dock.py` covers accessible names/keyboard (`test_dock_accessible_names_present`, `test_dock_keyboard_send_drives_a_turn`), both-theme render (`test_dock_and_dialog_render_in_current_theme[light/dark]`), retranslate (`test_dock_retranslates_without_crash`). |
| VI — performance / 16 ms | per-frame budget | **PASS** — assistant is batch/off the per-frame loop; the loop runs off the GUI thread on the window-owned `QThreadPool` (`ui/assistant_worker.py`); `FRAME_BUDGET_MS` does not gate a model call. No AGT-10 directive (DEP-5, ADR-0042 §3). |
| VII — security | validated input, no `eval`/`exec`, no secrets | **PASS (central, verified)** — action surface = allow-listed `dispatch` (no widening — `tool_catalog.py`); **zero `eval`/`exec`/`compile`/`__import__` audited across all three Phase-14 logic modules** (LOGIC-008); tool-results untrusted + bounded (LOGIC-006); tiered gate logic-enforced (LOGIC-004); keys only in keyring inside `data/llm/`, lazy at request time (`_base.py`/`token_store.py`), never in `.pixproj`/logs (verified `test_key_never_appears_in_logs_stdout_or_repr`); live path out-of-CI. |
| VIII — SDD gate law | analyze before implement | **PASS** — the forward C1 opened the gate; this final C1 confirms the shipped result. |
| X — REQ-ID scheme + traceability | `REQ-P<phase>-<LAYER>-<NNN>` + traced | **PASS** — 24 REQs conform; each now traces to a **landed** test (see `traceability.md`, all rows `covered (landed)`). |
| XI — extensibility | clean extension | **PASS** — `LLMPort` is the provider seam; two real adapters (`openai_compatible.py`, `anthropic_translator.py`) added over the shared `_base.py`/`_http.py` with no rule change. |

No constitution conflict (AN-D2 not triggered).

## 2. Plan ↔ spec ↔ shipped-code fidelity (no drift)

- **DEP-1..DEP-5 resolved and honoured in code:** `data/llm/` is a normal `data/` subpackage (not a top-level
  package); the tool-schema projection never widens `validate` (`test_projection_is_never_wider_than_validate`);
  the tiered gate is explicit allow-list + default-DESTRUCTIVE (`classify_op`); docs added a **topic**
  (`ai-assistant`) under `automation-and-scripting`, `manifest.json` still **12 sections**; the loop runs off
  the GUI thread (worker) — no per-frame work.
- **No new hard dependency (S8):** real adapters are stdlib-`urllib` only (`_http.py`); the only optional dep
  is `keyring` behind the `assistant_live` extra, lazily imported (`test_keyring_import_is_lazy_not_module_level`).
- **NEW post-freeze addition — turn-atomicity (SC-L005-3):** the spec/acceptance added a mid-turn error
  contract after the initial plan; the shipped `AssistantError.applied_commands` + `__cause__` preservation +
  byte-identical revert satisfies it and is fully traced (LOGIC-005). No contradiction with any FROZEN D1–D5.

## 3. Tasks ↔ plan ↔ landed completeness + coverage

**Every REQ-ID appears in the plan, in ≥1 task, and now maps to a landed test.** No orphan task; no
REQ-with-no-coverage. `tasks.md` marked all 36 slice tasks DONE (post-implementation status block).

| REQ-ID | Task(s) | Landed test file | Acceptance |
| --- | --- | --- | --- |
| LOGIC-001/-002/-003 | T14A-01..05 | `tests/logic/test_tool_catalog.py` | SC-L001/002/003-* |
| LOGIC-004/-005/-006/-007 | T14C-01..06 | `tests/logic/test_assistant_loop.py` | SC-L004/005/006/007-* |
| LOGIC-008 | T14C-05 | `test_assistant.py` + `test_assistant_loop.py` + `test_tool_catalog.py` (audit) | SC-L008-1 |
| DATA-001 | T14B-01/-02/-06 | `tests/data/test_llm_port.py` + `tests/logic/test_assistant.py` | SC-D001-1 |
| DATA-002 | T14B-03/-06 | `tests/data/test_llm_fake_adapter.py` | SC-D002-1 |
| DATA-003 | T14B-04/-05/-06 | `tests/data/test_llm_token_store.py` | SC-D003-1/-2 |
| DATA-004 | T14D-01/-03 | `tests/data/test_llm_openai_compatible.py` + `test_llm_http.py` (+ live `[assistant_live]`) | SC-D004-1/-2 |
| DATA-005 | T14D-02/-03 | `tests/data/test_llm_adapter_parity.py` + `test_llm_anthropic_translator.py` (+ live) | SC-D005-1/-2 |
| DATA-006 | T14B-04, T14D-01/-02/-03 | `test_llm_token_store.py` + adapter not-configured | SC-D006-1/-2 |
| DATA-007 | T14B-02, T14D-01/-02/-04 | `test_llm_port.py` + `test_llm_http.py` + scripts exit 0 | SC-D007-1 |
| DATA-008 | T14F-01/-02/-03 | `tests/data/test_assistant_cli.py` | SC-D008-1/-2 |
| UI-001..007 | T14E-01..07 | `tests/ui/test_assistant_dock.py` (consolidated) | SC-UI-001..007 |
| UI-008 | T14E-08/-09 | `tests/logic/test_guide_model.py` + `tests/data/test_guide_content.py` | SC-UI-008-1/-2 |

**Coverage: 24/24 REQs implemented + traced to landed tests; 0 uncovered; 0 orphan task.** Six mandated
invariants all covered by landed tests (see `traceability.md` §Coverage summary).

## 4. Conflicts / dangling references

**None.** Editorial drift resolved (not a code finding): the forward `tasks.md`/`traceability.md` predicted
per-concern test module names + a `tests/data/llm/` subdir + separate UI test files; the shipped suite
consolidated the 14A tests into `test_tool_catalog.py`, the 14C tests into `test_assistant_loop.py`
(+ `test_assistant.py`), the `data/llm` tests **flat** under `tests/data/test_llm_*.py`, and the whole 14E UI
surface into `tests/ui/test_assistant_dock.py`. `traceability.md` + `tasks.md` are updated to the shipped
paths. No requirement lost coverage; no contradictory or dangling reference remains.

## 5. Deterministic script gate (Article I evidence — final)

```
python scripts/check_layering.py --root pixelart_creator  -> clean (194 modules)   exit 0
python scripts/check_layering.py --root .                 -> clean (5 modules)     exit 0
python scripts/check_cycles.py   --root pixelart_creator  -> no cycles (196)       exit 0
python scripts/check_cycles.py   --root sync_backend      -> no cycles (3)         exit 0
python scripts/check_cycles.py   --root web_viewer        -> no cycles (9)         exit 0
```

All five roots exit 0. `pixelart_creator` grew +14 modules over the 2026-07-07 web_viewer gate (180 → 194)
for Phase-14, with **no forbidden edge and no new top-level package** — exactly as the plan (§11) predicted.

## 6. Observations (non-blocking)

- `logic/assistant.py` was touched by 14B (value types + `ChatBackend` Protocol) and 14C (loop/gate/atomicity)
  as designed (freeze-then-implement); each slice left the module gate-green.
- The `llm-adapter-normalization` skill was applied to factor the shared `_base.py`/`_http.py` transport +
  credential base — a 14D refinement, layering-clean, private (leading-underscore) so not part of the public
  `data/llm` surface. Documented in STRUCTURE.md.
- Local gate remains authoritative (remote Actions billing-blocked); AGT-09 owns the `assistant_live`
  CI-deselection (`-m "... and not assistant_live"`) when remote CI resumes.

## 7. Verdict

**PASS (AN-D1 Branch A) — FINAL.** Every REQ-P14-* is implemented and traced to a landed test; the six
mandated invariants (tiered-safety, whitelist, injection resistance, credential-gating, model-agnostic-via-fake,
zero-eval/exec) and the new SC-L005-3 turn-atomicity are all covered; five script roots exit 0; zero
unresolved cross-artifact finding; no code gap. **Phase 14 is COMPLETE.** Only editorial drift (test-path
predictions) was fixed — no work is routed out.
