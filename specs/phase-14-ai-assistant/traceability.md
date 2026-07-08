# Traceability Matrix — Phase 14: `phase-14-ai-assistant`

REQ-ID ↔ dossier `S-id` / principle / article / forward-inherited primitive ↔ spec section ↔ Gherkin
scenario(s) (`acceptance.md`) ↔ expected test id(s).

**Mode:** FORWARD / PRE-IMPLEMENTATION — **COMPLETE** (authored at `specify`+`clarify`, §10 FROZEN,
AGT-02, 2026-07-08). **All six slices fully drafted** — **24 REQs**: `REQ-P14-LOGIC-001..008` (8) +
`REQ-P14-DATA-001..008` (8) + `REQ-P14-UI-001..008` (8). Every REQ has **≥1 acceptance scenario in
`acceptance.md`**; tests are **`pending`** (authored later by AGT-04 — logic/data, headless via the fake
`LLMPort` adapter — and AGT-06 — UI, both themes — after `sdd-plan`/`sdd-tasks`). **No `uncovered` rows
remain**; all product-direction decisions (D1–D5) are FROZEN. Live-provider adapter scenarios
(SC-D004-2, SC-D005-2) are `@out-of-ci` (`assistant_live` marker, deselected — mirrors `cloud_live`).

Status legend:
- **spec'd (forward)** — has ≥1 Gherkin acceptance scenario in `acceptance.md`; test `pending`.

Inherited-primitive keys: **SCR-1** = Phase-8 `logic/scripting.py` (allow-listed registry + trusted
`dispatch`); **MAC-1** = Phase-8 `logic/macro.py` (`Op`/`Macro`); **PLG-1** = Phase-8 `logic/plugins.py`
(consent-gated capability); **HIS-1** = Phase-1 `logic/history.py` (`Command`/`GroupCommand` undo stack);
**CLD-1** = Phase-10 `data/cloud/` (port + fake adapter + `token_store` + `cloud_live` extra/marker).

## Slice 14A — LOGIC — safe tool-catalog + JSON-schema introspection (`logic/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-LOGIC-001 | **SCR-1**, **PLG-1**, S7, S11, Article I, Article XI | §2 (14A), §4, §10.1 (D1) | SC-L001-1, SC-L001-2 | `tests/logic/test_tool_catalog.py` (catalog == registered ops; read-only; tracks plugin op) | spec'd (forward) |
| REQ-P14-LOGIC-002 | **SCR-1** (`ParamSchema`), S11, Article I, Article XI, Researcher `ad2616c7` | §2 (14A), §4 | SC-L002-1 | `tests/logic/test_tool_schema.py` (JSON-schema is a faithful ParamSchema projection; never widens) | spec'd (forward) |
| REQ-P14-LOGIC-003 *(invariant: whitelist)* | **SCR-1** (dispatch allow-list + atomicity), **MAC-1**, Article VII, Article I, S11, Researcher `ad2616c7` | §2 (14A), §4, §5, §10.2 | SC-L003-1, SC-L003-2, SC-L003-3 | `tests/logic/test_toolcall_dispatch.py` (non-registered/invalid → ScriptError, doc byte-unchanged; valid → undoable group) | spec'd (forward) |

## Slice 14C — LOGIC — agentic conversation loop + tiered-safety enforcement (`logic/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-LOGIC-004 *(invariant: tiered-safety)* | **HIS-1**, **SCR-1**, Article VII, Article I, S11, D3, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.1 (D3) | SC-L004-1, SC-L004-2, SC-L004-3 | `tests/logic/test_tiered_safety.py` (reversible auto-runs; destructive withheld until explicit confirm; logic-enforced) | spec'd (forward) |
| REQ-P14-LOGIC-005 | **SCR-1**, **HIS-1** (Command revert), S7, S11, Article I, Article VI (batch), Article II, D1, Researcher `ad2616c7` | §2 (14C), §4, §5 | SC-L005-1, SC-L005-2, SC-L005-3 | `tests/logic/test_assistant_loop.py` (multi-step scripted run → final message; bounded halt; deterministic under fake; **turn-atomicity on a mid-turn error — `AssistantError.applied_commands` exposes the ordered applied commands, non-`AssistantError` cause wrapped with `__cause__` preserved, revert → byte-identical**) | spec'd (forward) |
| REQ-P14-LOGIC-006 *(invariant: injection)* | Article VII, Article II, **SCR-1**, **CLD-1** (`cloud_validation`-style caps), S13, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.2 | SC-L006-1, SC-L006-2, SC-L006-3 | `tests/logic/test_injection_resistance.py` (malicious result cannot invoke non-whitelisted op / bypass gate; oversized result bounded) | spec'd (forward) |
| REQ-P14-LOGIC-007 | Article II, Article VII, S12 | §2 (14C), §4, §5, §10.2 | SC-L007-1 | `tests/logic/test_assistant_bounds.py` (caps from constants; no literals; bound breach → domain error) | spec'd (forward) |
| REQ-P14-LOGIC-008 *(invariant: no-eval/exec)* | Article VII, **SCR-1** (ADR-0021/0022), S11, S13, Researcher `ad2616c7` | §2 (14C), §4, §5, §10.2 | SC-L008-1 | `tests/logic/test_no_eval_exec_audit.py` (static source audit: zero eval/exec/compile/__import__ of model output across Phase-14 modules) | spec'd (forward) |

## Slice 14B — DATA — model-agnostic LLM port + fake adapter + credential gating (`data/llm/`)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-001 | **CLD-1** (`data/cloud/port.py`), S7, S11, Article I, Article XI, D4, Researcher `ad2616c7` | §2 (14B), §4, §10.1 (D4) | SC-D001-1 | `tests/data/llm/test_llm_port.py` (one provider-neutral chat/function-calling interface; no provider/HTTP/credential type; Qt-free) | spec'd (forward) |
| REQ-P14-DATA-002 *(invariant: credential-gating)* | **CLD-1** (fake in CI), S13, Article IV, S11, D5, Researcher `ad2616c7` | §2 (14B), §4, §5, §10.1 (D5) | SC-D002-1 | `tests/data/llm/test_fake_adapter.py` (whole contract driven with no key/network; reproducible scripted responses) | spec'd (forward) |
| REQ-P14-DATA-003 *(invariant: credential-gating)* | **CLD-1** (`token_store.py` + `cloud_live` extra/marker), Article VII (no secrets), S11, Article I, D5 | §2 (14B), §4, §5, §10.1 (D5) | SC-D003-1, SC-D003-2 | `tests/data/llm/test_credential_gating.py` (assistant_live extra + lazy keyring store + deselected marker; imports without keyring; no key in .pixproj/logs) | spec'd (forward) |

## Slice 14D — DATA — real generic provider adapter (`data/llm/`, credential-gated/out-of-CI)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-004 | **CLD-1**, S8 (no new hard dep), Article I, D4, Researcher `ad2616c7` | §2 (14D), §4 | SC-D004-1, SC-D004-2 *(@out-of-ci)* | `tests/data/llm/test_openai_compatible_adapter.py` (stdlib/urllib only; no new hard dep; same port) + `test_openai_live.py` **[assistant_live, deselected in CI]** | spec'd (forward) |
| REQ-P14-DATA-005 *(invariant: model-agnostic)* | **CLD-1**, S8, Article I, Article XI, D4, Researcher `ad2616c7` | §2 (14D), §4, §5 | SC-D005-1, SC-D005-2 *(@out-of-ci)* | `tests/data/llm/test_model_agnostic.py` (same loop/catalog/gate for OpenAI-compat + Anthropic shapes via the fake) + `test_anthropic_live.py` **[assistant_live, deselected in CI]** | spec'd (forward) |
| REQ-P14-DATA-006 *(invariant: credential-gating)* | Article VII (no secrets), Article IV, **CLD-1** (`cloud_live` posture), D4/D5, S13 | §2 (14D), §4, §5, §10.2 | SC-D006-1, SC-D006-2 | `tests/data/llm/test_credential_gating.py` (key only in keyring, never in .pixproj/logs; not-configured degrades cleanly) | spec'd (forward) |
| REQ-P14-DATA-007 | Article I, S11, **CLD-1** | §2 (14D), §4, §5, §10.2 | SC-D007-1 | `tests/data/llm/test_llm_port.py` + `check_layering`/`check_cycles` exit 0 (no provider/HTTP leak above the port; data/llm Qt-free) | spec'd (forward) |

## Slice 14F — DATA — headless `pixelart-assistant` CLI (`data/`, Qt-free)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-DATA-008 *(invariant: tiered-safety in CLI)* | **CLD-1**, `pixelart-run` precedent, S11, Article I, Article IV, D2, Article VII | §2 (14F), §4, §10.1 (D2) | SC-D008-1, SC-D008-2 | `tests/data/test_assistant_cli.py` (loop over .pixproj, Qt-free, saved back; destructive requires explicit affordance, never auto-run; fake adapter in CI) | spec'd (forward) |

## Slice 14E — UI — chat dock + provider/key config + tiered-confirm + docs (`ui/`; only Qt)

| REQ-ID | Traces (S-id / principle / article / inherited) | Spec § | Scenario(s) | Test id(s) (expected — pending) | Status |
| --- | --- | --- | --- | --- | --- |
| REQ-P14-UI-001 | REQ-P14-LOGIC-005, S7, Article V, D2 | §2 (14E), §4, §10.1 (D2) | SC-UI-001-1 `[light][dark]` | `tests/ui/test_assistant_dock.py` (dock drives the logic loop, never a provider; shows replies + undoable edits; errors surfaced) | spec'd (forward) |
| REQ-P14-UI-002 *(invariant: no secrets)* | REQ-P14-DATA-003, -006, Article VII, Article V | §2 (14E), §4, §5 | SC-UI-002-1 `[light][dark]` | `tests/ui/test_provider_config.py` (key handed to keyring store; ui retains no raw key; never in .pixproj/logs; provider-agnostic) | spec'd (forward) |
| REQ-P14-UI-003 *(invariant: tiered-safety)* | REQ-P14-LOGIC-004, Article V, Article VII, D3 | §2 (14E), §4, §5, §10.1 (D3) | SC-UI-003-1 `[light][dark]` | `tests/ui/test_tiered_confirm.py` (destructive → explicit confirm/cancel; reversible auto + undoable; UI renders gate, does not relax) | spec'd (forward) |
| REQ-P14-UI-004 (NFR) | REQ-P14-LOGIC-005, S7, Article VI | §2 (14E), §4, §5 | SC-UI-004-1 | `tests/ui/test_assistant_responsive.py` (no UI freeze during model round-trip; off GUI thread); AGT-01/AGT-10 worker HOW (DEP-5) | spec'd (forward) |
| REQ-P14-UI-005 (NFR) | Article V §1 | §2 (14E), §4, §5 | SC-UI-005-1 `[light][dark]` | `tests/ui/test_assistant_a11y.py` (accessible names / keyboard / focus); AGT-06 `a11y-audit` | spec'd (forward) |
| REQ-P14-UI-006 (NFR) | Article V §3 | §2 (14E), §4, §5 | SC-UI-006-1 (+ every UI scenario `[light]`/`[dark]`) | both-theme fixtures across `tests/ui/test_assistant_*` | spec'd (forward) |
| REQ-P14-UI-007 (NFR) | Article V §2, F6 | §2 (14E), §4, §5 | SC-UI-007-1 | tr()-wrapped assistant UI + `changeEvent` retranslate; AGT-07 `string_audit_check` | spec'd (forward) |
| REQ-P14-UI-008 | Article V, `logic/guide_model.py` (`REQUIRED_AREAS`), docs precedent, standing docs rule | §2 (14E), §4 | SC-UI-008-1, SC-UI-008-2 | `tests/logic/test_guide_model.py` (new topic under `automation-and-scripting`; `len(sections)==len(REQUIRED_AREAS)==12`) + README review (AGT-08) | spec'd (forward) |

## Coverage summary

- **24 / 24 REQs** have ≥1 acceptance scenario (`acceptance.md`) → **0 uncovered**.
- **Tests:** all `pending` (forward mode) — authored post-`sdd-tasks` by AGT-04 (logic/data, fake
  adapter, headless) + AGT-06 (UI, both themes). Live-provider tests (`SC-D004-2`, `SC-D005-2`) carry the
  `assistant_live` marker and are **deselected in CI** (mirrors `cloud_live`).
- **Six mandated security/agentic invariants — all covered:**
  - tiered-safety boundary → REQ-P14-LOGIC-004 (SC-L004-1/-2/-3), REQ-P14-UI-003 (SC-UI-003-1),
    REQ-P14-DATA-008 (SC-D008-2);
  - whitelist enforcement (doc byte-unchanged) → REQ-P14-LOGIC-003 (SC-L003-1/-2);
  - prompt-injection resistance → REQ-P14-LOGIC-006 (SC-L006-1/-2/-3);
  - credential-gating (fake adapter in CI, keys never in `.pixproj`/logs) → REQ-P14-DATA-002/-003/-006
    (SC-D002-1, SC-D003-1/-2, SC-D006-1);
  - model-agnostic (one port, OpenAI-compatible + Anthropic via the fake) → REQ-P14-DATA-005 (SC-D005-1);
  - zero `eval`/`exec` source audit → REQ-P14-LOGIC-008 (SC-L008-1).
- **Gap list: EMPTY.** No REQ lacks a scenario; no duplicate/collision REQ-IDs.
- **Flags for AGT-01 (plan/ADR, §8 of spec):** DEP-1 (exact placement of `data/llm/` + the CLI module),
  DEP-2 (the tool-schema wire contract — a faithful `ParamSchema` → JSON-schema projection), DEP-3 (the
  reversibility-classification mechanism for the tiered gate), DEP-4 (packaging: `assistant_live` extra +
  marker + `pixelart-assistant` entry point), DEP-5 (AGT-10 responsiveness-not-frame-budget assessment).
