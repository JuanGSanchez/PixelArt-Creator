# Tasks — Phase 14: In-App, Model-Agnostic AI Assistant

| Field | Value |
| --- | --- |
| Feature | `phase-14-ai-assistant` |
| Author | Claude (AGT-01, Architecture) via `sdd-tasks` |
| Date | 2026-07-08 |
| Over | `plan.md` + ADR-0039/0040/0041/0042; spec/acceptance/traceability |
| Gate | Article VIII — **no implement dispatch until `analyze-report.md` (C1) passes.** This tasks list is C1-analysed. |
| CI note | Remote GitHub Actions is billing-blocked; **the LOCAL gate is authoritative** — each task/slice must leave `check_layering` + `check_cycles` (both roots) exit 0, Black/isort/flake8/mypy clean, pytest + `coverage_gate` (≥90 line / ≥80 branch) green, `string_audit_check` clean (UI), and `path_portability_check` clean. |

## Dependency order (slice-by-slice — each an independently gate-green shippable increment)

```
14A (logic tool-catalog + schema)         ── freezes the tool contract
   └─▶ 14B (data/llm port + fake + token store + assistant_live scaffold)
          └─▶ 14C (logic agentic loop + tiered gate + injection defence)
                 ├─▶ 14D (real stdlib-urllib OpenAI-compat + Anthropic adapters, out-of-CI)
                 ├─▶ 14F (headless pixelart-assistant CLI)
                 └─▶ 14E (chat dock + config + tiered-confirm + docs)
```

14A→14B→14C are strictly sequential (contract → port → loop). 14D, 14F, 14E each depend on 14C (loop) +
14B (fake adapter) and are otherwise independent. Owners: **AGT-03** logic/data, **AGT-05** ui,
**AGT-04** logic/data tests, **AGT-06** ui/a11y tests, **AGT-07** i18n, **AGT-08** docs, **AGT-09**
pyproject/CI/commits. Every task carries its REQ + acceptance-scenario (SC-…) link.

---

## Slice 14A — safe tool-catalog + JSON-schema introspection (`logic/`)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14A-01 | Author `logic/tool_catalog.py`: `ToolDescriptor(name, description, parameters)`; `build_tool_catalog()` over `scripting.registered_ops()` (read-only; tracks built-ins + namespaced plugin ops; no new op, no registration path). Module-local per-op description table (ADR-0001). | AGT-03 | `logic/tool_catalog.py` | LOGIC-001 · SC-L001-1/-2 |
| T14A-02 | Implement `param_schema_to_json_schema(ParamSchema)` — the FROZEN projection (ADR-0039 §3): type map, `required`, `allow_extra→additionalProperties`, `requires_seed→` explicit routed `seed` property; faithful (never widens `validate`). | AGT-03 | `logic/tool_catalog.py` | LOGIC-002 · SC-L002-1 |
| T14A-03 | Implement `ToolCall(name, arguments)`, `to_op(ToolCall)` (peel `seed`, rest→params), `execute_tool_call(document, ToolCall)` via `scripting.dispatch` — non-registered/invalid → `ScriptError`, document byte-unchanged; valid → one undoable `GroupCommand`. NO widening of dispatch/registry. | AGT-03 | `logic/tool_catalog.py` | LOGIC-003 · SC-L003-1/-2/-3 |
| T14A-04 | Tests: catalog == registered ops + read-only + plugin-op tracking; schema faithful projection (never permits what `validate` rejects); tool-call dispatch rejection (byte-unchanged) + valid undoable group. Headless, no Qt. | AGT-04 | `tests/logic/test_tool_catalog.py`, `test_tool_schema.py`, `test_toolcall_dispatch.py` | LOGIC-001/-002/-003 · SC-L001/002/003-* |
| T14A-05 | Commit (Conventional + REQ-IDs); confirm local gate + `check_layering`/`check_cycles` (both roots) exit 0. | AGT-09 | — | LOGIC-001..003 |

## Slice 14B — model-agnostic LLM port + fake adapter + credential gating (`data/llm/`)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14B-01 | Freeze + author `logic/assistant.py` value types **only** needed by the port now: `Role`, `Message`, `Conversation`, `AssistantReply`, and the `ChatBackend` Protocol (the loop body lands in 14C). (`interface-contract` — the cross-slice contract 14B binds to.) | AGT-03 | `logic/assistant.py` (types + Protocol) | DATA-001 (contract) |
| T14B-02 | Author `data/llm/port.py`: `LLMPort(ABC)` — `respond(conversation, tools) -> AssistantReply` (satisfies `ChatBackend`), `is_configured()`; `LLMError` family; **no provider/HTTP/credential type** in signatures. Imports the `logic` value types (data→logic). Zero Qt. | AGT-03 | `data/llm/port.py`, `data/llm/__init__.py` | DATA-001, 007 · SC-D001-1 |
| T14B-03 | Author `data/llm/fake_adapter.py`: deterministic scripted `LLMPort` (final messages + scripted tool-calls incl. reversible/destructive, malicious-tool-result follow-ups, multi-step, OpenAI-shape + Anthropic-shape emulation); no network/key; reproducible. | AGT-03 | `data/llm/fake_adapter.py` | DATA-002 · SC-D002-1 |
| T14B-04 | Author `data/llm/token_store.py`: lazy/optional `keyring`; template `pixelart-creator:assistant:{provider}`; `store/load/delete_token`, `is_keyring_available`. Keys never leave `data/llm/`; imports without keyring installed. | AGT-03 | `data/llm/token_store.py` | DATA-003, 006 · SC-D003-1/-2, SC-D006-1 |
| T14B-05 | pyproject: add `assistant_live = ["keyring==25.7.0"]` extra + register `assistant_live` pytest marker. (CI-deselection wired in T14E-G / whenever CI runs — see §CI.) | AGT-09 | `pyproject.toml` | DATA-003 · SC-D003-1 |
| T14B-06 | Tests: `LLMPort` shape (no provider/HTTP/credential type; Qt-free); fake adapter drives the contract with no key/network + reproducible; credential-gating (extra + lazy keyring + imports without keyring; no key in `.pixproj`/log). | AGT-04 | `tests/data/llm/test_llm_port.py`, `test_fake_adapter.py`, `test_credential_gating.py` | DATA-001/-002/-003 · SC-D001/002/003-* |
| T14B-07 | Commit; confirm local gate + layering/cycles (both roots) exit 0 (incl. `--root .` unaffected). | AGT-09 | — | DATA-001..003 |

## Slice 14C — agentic conversation loop + tiered-safety enforcement (`logic/`)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14C-01 | Add the 5 caps to `logic/constants.py` (`MAX_ASSISTANT_TURNS`, `MAX_TOOL_CALLS_PER_TURN`, `MAX_TOOL_RESULT_BYTES`, `MAX_CONVERSATION_MESSAGES`, `ASSISTANT_REQUEST_TIMEOUT_S`), names distinct from every shipped constant; values per ADR-0041 §4. | AGT-03 | `logic/constants.py` | LOGIC-007 · SC-L007-1 |
| T14C-02 | Author the tiered gate in `logic/assistant.py`: `Reversibility` enum + `REVERSIBLE_OPS` (built-ins) + `classify_op(name)` (default DESTRUCTIVE); pure/deterministic/logic-level. | AGT-03 | `logic/assistant.py` | LOGIC-004 · SC-L004-1/-2/-3 |
| T14C-03 | Author the bounded agentic loop `AssistantSession`/`run_turn(document, conversation, backend, *, confirm)`: present catalog to backend; on tool-call apply the gate then `execute_tool_call`; feed tool-result back as untrusted bounded input; iterate to `MAX_*` → final message; `AssistantError` on breach. `AssistantError`. | AGT-03 | `logic/assistant.py` | LOGIC-005 · SC-L005-1/-2 |
| T14C-04 | Injection defence: bound tool-results by `MAX_TOOL_RESULT_BYTES` / `MAX_TOOL_CALLS_PER_TURN` / turns; ensure a malicious result cannot invoke a non-whitelisted op or bypass the gate (results are data). | AGT-03 | `logic/assistant.py` | LOGIC-006 · SC-L006-1/-2/-3 |
| T14C-05 | Tests: tiered gate (reversible auto / destructive withheld until confirm / logic-enforced); loop (multi-step scripted run via fake → final message; bounded halt; deterministic); injection (malicious result cannot escalate; oversized bounded); bounds from constants (no literals); **static no-`eval`/`exec`/`compile`/`__import__` source audit over all Phase-14 modules**. | AGT-04 | `tests/logic/test_tiered_safety.py`, `test_agentic_loop.py`, `test_injection_resistance.py`, `test_assistant_bounds.py`, `test_no_eval_exec_audit.py` | LOGIC-004/-005/-006/-007/-008 · SC-L004/005/006/007/008-* |
| T14C-06 | Commit; confirm local gate + layering/cycles exit 0. | AGT-09 | — | LOGIC-004..008 |

## Slice 14D — real generic provider adapters (`data/llm/`, credential-gated / out-of-CI)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14D-01 | Author `data/llm/openai_compatible.py`: stdlib-`urllib` OpenAI-compatible client (`/v1/chat/completions` + tools); map conversation + `ToolDescriptor`→`{"type":"function",…}`, `tool_calls[]`→`ToolCall`; `ASSISTANT_REQUEST_TIMEOUT_S`; **no new hard dep**; not-configured degrades cleanly. *(Candidate for the `llm-adapter-normalization` skill / agt-12 — plan §12; orchestrator decides.)* | AGT-03 | `data/llm/openai_compatible.py` | DATA-004, 006, 007 · SC-D004-1/-2, SC-D006-2 |
| T14D-02 | Author `data/llm/anthropic_translator.py`: stdlib-`urllib` native-Anthropic translator (Messages/`tool_use`/`tool_result`, `input_schema`, `x-api-key`); same `LLMPort`; credential-gated. | AGT-03 | `data/llm/anthropic_translator.py` | DATA-005, 006, 007 · SC-D005-2 |
| T14D-03 | Tests: OpenAI-compat adapter stdlib-only + no new hard dep + same port (in-CI); model-agnostic parity (same loop/catalog/gate for OpenAI-shape + Anthropic-shape **via the fake**, in-CI); live tests `@pytest.mark.assistant_live` (deselected in CI). | AGT-04 | `tests/data/llm/test_openai_compatible_adapter.py`, `test_model_agnostic.py`, `test_openai_live.py` `[assistant_live]`, `test_anthropic_live.py` `[assistant_live]` | DATA-004/-005/-006/-007 · SC-D004/005/006/007-* |
| T14D-04 | Commit; confirm local gate + layering/cycles exit 0; `check_layering` confirms no provider/`urllib` leak above the port (`data/llm/` Qt-free). | AGT-09 | — | DATA-004..007 |

## Slice 14F — headless `pixelart-assistant` CLI (`data/`, Qt-free)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14F-01 | Author `data/assistant_cli.py` mirroring `automation_cli.py`: `argparse`; load `.pixproj` (IO-3); construct `LLMPort` (fake in CI); run `logic.assistant` loop; **destructive op requires explicit `--yes`/confirm affordance (never auto-run)**; save back; exit 0/1/2. Zero Qt; no `eval`/`exec`. | AGT-03 | `data/assistant_cli.py` | DATA-008 · SC-D008-1/-2 |
| T14F-02 | pyproject `[project.scripts]` += `pixelart-assistant = "pixelart_creator.data.assistant_cli:main"`. | AGT-09 | `pyproject.toml` | DATA-008 |
| T14F-03 | Tests: CLI runs the loop over a `.pixproj` (fake adapter, no key/network), Qt-free, saved back; destructive requires explicit affordance (never auto-run); reversible applies. | AGT-04 | `tests/data/test_assistant_cli.py` | DATA-008 · SC-D008-1/-2 |
| T14F-04 | Commit; confirm local gate + layering/cycles exit 0. | AGT-09 | — | DATA-008 |

## Slice 14E — chat dock + provider/key config + tiered-confirm + docs (`ui/`, the only Qt)

| ID | Task | Owner | Target file(s) | REQ / Acceptance |
| --- | --- | --- | --- | --- |
| T14E-01 | Author `ui/assistant_worker.py`: `Assistant_Worker(QRunnable)` + signals on a window-owned `QThreadPool`; run the Qt-free loop off the GUI thread; progress/result/error/cancel; no Qt off-thread. | AGT-05 | `ui/assistant_worker.py` | UI-004 · SC-UI-004-1 |
| T14E-02 | Author `ui/assistant_dock.py`: `Assistant_Dock(QDockWidget)` — transcript + input/send; drives the `logic/` loop via the injected backend (never a provider); shows replies + undoable edits; errors surfaced; `tr()` + `changeEvent`. | AGT-05 | `ui/assistant_dock.py` | UI-001 · SC-UI-001-1 |
| T14E-03 | Author `ui/provider_config_dialog.py`: endpoint + key entry + select/connect; hand key to `data/llm/token_store`; retain no raw key; provider-agnostic; not-configured degrades; `tr()`. | AGT-05 | `ui/provider_config_dialog.py` | UI-002 · SC-UI-002-1 |
| T14E-04 | Tiered-confirm surface: destructive → explicit confirm/cancel naming the action (renders the logic gate's decision, never relaxes it); reversible → apply + visible + undoable. Extend `ui/commands.py` (one grouped `QUndoCommand` per assistant edit; chat/connect/confirm push none). Wire menu/dock in `ui/main_window.py`. | AGT-05 | `ui/commands.py`, `ui/main_window.py`, `ui/assistant_dock.py` | UI-003 · SC-UI-003-1 |
| T14E-05 | i18n: wrap every user-visible string in `tr()`/`translate()`; `changeEvent` retranslate; run `string_audit_check` (clean). Extract → `.ts`, compile → `.qm`, wire `LanguageManager`. | AGT-07 | `ui/assistant_*`, i18n catalogues | UI-007 · SC-UI-007-1 |
| T14E-06 | UI tests (pytest-qt, both themes): dock drives loop (not a provider) + shows replies/edits + errors; provider config hands key to keyring store, retains none, never in `.pixproj`/log; tiered-confirm (destructive confirm/cancel; reversible auto+undoable; UI doesn't relax); responsiveness (no freeze during model round-trip, off GUI thread). | AGT-06 | `tests/ui/test_assistant_dock.py`, `test_provider_config.py`, `test_tiered_confirm.py`, `test_assistant_responsive.py` | UI-001/-002/-003/-004 · SC-UI-001/002/003/004-* |
| T14E-07 | a11y + both-theme verification: accessible names/descriptions, keyboard reach, focus visibility (`a11y-audit`); both-theme render (role-based colours). AGT-05 fixes findings. | AGT-06 | `tests/ui/test_assistant_a11y.py` + both-theme fixtures | UI-005/-006 · SC-UI-005/006-1 |
| T14E-08 | Docs: new in-app User-Guide **topic** under the existing `automation-and-scripting` section (preserve `len(sections)==len(REQUIRED_AREAS)==12`) + README launch surface (dock + `pixelart-assistant` CLI; provider/key config; credential-optional; tiered-safety). | AGT-08 | userguide content + manifest, `README` | UI-008 · SC-UI-008-1/-2 |
| T14E-09 | Guide-model test: new topic under Automation; `len(sections)==12` unchanged. | AGT-06/AGT-04 | `tests/logic/test_guide_model.py` | UI-008 · SC-UI-008-1 |
| T14E-10 | Commit; confirm local gate (incl. `string_audit_check`, both-theme, a11y) + layering/cycles exit 0. | AGT-09 | — | UI-001..008 |

## Cross-cutting / CI

- **CI marker deselection (AGT-09):** when CI runs (currently local-authoritative), the `-m` expression
  gains `and not assistant_live` (alongside `not slow and not gpu and not cloud_live and not integration`),
  so the 14D live tests never run in the gate. Coverage gate ≥90/80 measured over the fake-adapter path.
- **Traceability sync (AGT-01/AGT-02):** on implementation, flip each REQ's test id from `pending` to the
  landed test in `traceability.md` (AGT-01 syncs traceability only; AGT-02 owns spec content).
- **No implement dispatch** until `analyze-report.md` (C1) is PASS (Article VIII).
