# Plan — Phase 14: In-App, Model-Agnostic AI Assistant

| Field | Value |
| --- | --- |
| Feature | `phase-14-ai-assistant` |
| Author | AGT-01 (Architecture) via `sdd-plan` |
| Date | 2026-07-08 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, **VI**, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW before any `logic/{tool_catalog,assistant}.py`, `data/llm/{port,fake_adapter,openai_compatible,anthropic_translator,token_store}.py`, `data/assistant_cli.py`, or assistant `ui/` exists. The **shipped** Phase-8 safe action surface (`logic/scripting.py` SCR-1, `logic/macro.py` MAC-1, `logic/plugins.py` PLG-1), the Phase-1 undo stack (`logic/history.py` HIS-1), and the Phase-10 `cloud_live` credential-gating pattern (`data/cloud/` CLD-1) are **REUSED, not re-authored**. |
| Over spec | `specs/phase-14-ai-assistant/spec.md` (24 REQ: `REQ-P14-LOGIC-001..008`, `REQ-P14-DATA-001..008`, `REQ-P14-UI-001..008`) + `acceptance.md` + `traceability.md`. §10 clarifications **FROZEN** (D1–D5); 0 open. |
| Stack source | S8 (fixed) — Python 3.12+, stdlib + shipped deps. **NO new hard runtime dependency** (PL14-D5): the real adapters are stdlib-`urllib`; the only live dep is optional `keyring` (already the `cloud_live` dep), behind the `assistant_live` extra. |
| Grounding | The Researcher — `docs/subagent-report-the-researcher-ad2616c7-20260707T220150.md` (LANDED). Grounds every DEP resolution. No further RESEARCH REQUEST needed (A1-D1 Branch B on ≥5-file reads was satisfied by direct substrate reads). |
| ADRs filed (S19-PRIVATE, uncommitted) | **ADR-0039** (assistant action-surface = shipped safe DSL registry + the frozen tool-schema facade contract; Article VII by construction); **ADR-0040** (model-agnostic `LLMPort` ABC + `data/llm/` placement + the `logic`-side `ChatBackend` Protocol bridge + stdlib-urllib OpenAI-compatible client + Anthropic translator + `assistant_live` credential gating); **ADR-0041** (agentic loop + tiered-safety reversibility classification + prompt-injection / untrusted-tool-result defence + bounded numerics); **ADR-0042** (embedding: chat dock + headless `pixelart-assistant` CLI + responsiveness + User-Guide/README surfaces). |

---

## 1. Purpose (HOW)

This plan defines the technical architecture realising the approved Phase-14 spec — the **final roadmap
phase**: an in-app, model-agnostic AI assistant that connects an external LLM, chats in-app, and drives the
user's whole workflow **through the shipped, allow-listed, `eval`/`exec`-free action surface**. It maps
every REQ to its S11 layer, **freezes the public interface** of the new modules before implementation,
resolves the five DEP flags in **ADR-0039/0040/0041/0042**, places the five new numerics in
`logic/constants.py` with names distinct from every shipped constant (Article II / BF-1), and confirms the
**Article VI posture** (the assistant is batch/off the per-frame loop — no AGT-10 per-frame directive
required; DEP-5). It is decomposed **slice-by-slice** in `tasks.md`, each an independently gate-green,
**LOCAL-CI-green** shippable increment (remote Actions is billing-blocked; the local gate is authoritative).

**Central honesty ruling.** The shipped tree has **no** AI/LLM code: no LLM port, no tool-schema facade, no
agentic loop, no tiered classifier, no chat dock, no assistant CLI. Phase 14 **introduces** these. "Reuse
the shipped surface" (D1) is honoured *by composition*: the assistant **introspects and drives** the
frozen Phase-8 `scripting`/`macro` DSL through the frozen `dispatch`; it **adds no executable op and no
registration back-door** (spec §6). The `LLMPort` reuses the *shape* of `data/cloud/port.py`; credential
gating reuses the *pattern* of `cloud_live`. AGT-03 builds new modules; it does not widen a frozen surface.

## 2. The security invariants (Article VII — CENTRAL; ADR-0039/0041)

> **(a) Action surface = the allow-listed registry.** The LLM drives **only** registered ops, mapped 1:1
> onto `macro.Op` and executed through the **single** trusted `scripting.dispatch()`; a non-registered /
> invalid tool-call raises `ScriptError` with the document **byte/state-identical** (SCR-1 atomicity).
> **Zero new interpreter, zero `eval`/`exec`** — Article VII **by construction** (ADR-0021/0022 inherited).
> **(b) Security is registry/permission enforcement, not the prompt.** The whitelist + the tiered gate live
> in `logic/`; no prompt or injected tool-result content can invoke a non-whitelisted op or bypass the
> confirm gate (Researcher R5.3).
> **(c) Tool-results are untrusted, bounded input** — size/count-capped (`cloud_validation` posture, CLD-1),
> data never authority (prompt-injection defence — OWASP #1 in 2026, R5.2).
> **(d) No secrets leak.** Keys live **only** in the OS keyring inside `data/llm/`, never in `.pixproj`/logs,
> and the live path is out of CI (`assistant_live`).

Realised **structurally**: the loop + gate + catalog are pure `logic/` leaves over
`scripting`/`macro`/`history`/`constants`; the port + adapters are `data/llm/` (Qt-free) importing only the
`logic/` value types; `ui/` holds the only Qt. `check_layering`/`check_cycles` stay exit 0 with **no new
rule** (§11).

## 3. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib + shipped deps; reuse SCR-1/MAC-1/PLG-1/HIS-1/CLD-1 | S8 |
| Action surface | shipped Phase-8 `_REGISTRY` + `ParamSchema` + trusted `dispatch`; a **read-only** tool-catalog facade projects each op to a JSON-schema tool; tool-call → `macro.Op` → `dispatch` (no widening) | D1; ADR-0039; R2.5, R5.1 |
| Tool-schema wire | provider-neutral JSON-Schema subset (no `$schema`; `type`/`properties`/`required`/`additionalProperties`); `ParamSchema` → schema faithful projection; `seed` an explicit routed property | DEP-2; ADR-0039; R2.2 |
| LLM port | one Qt-free `LLMPort` ABC in `data/llm/`, mirroring `CloudPort`; verb `respond(conversation, tools) -> AssistantReply`; no provider/HTTP/credential type in signatures | D4; ADR-0040; R1.5 |
| Layering bridge | `logic/` defines the `ChatBackend` **Protocol** + the shared value types; the loop is injected the backend (the `macro.set_dispatcher`/`blend.CompositeNode` precedent) — **no `logic → data` edge** | DEP-1; ADR-0040 §2 |
| Fake adapter | deterministic scripted `LLMPort` (reversible + destructive + malicious-result + multi-step + OpenAI-and-Anthropic-shape emulation); no network/key; the whole contract in CI | D5; ADR-0040; R6.2 |
| Real adapters | stdlib-`urllib` OpenAI-compatible client (OpenAI / Gemini compat / Ollama / llama.cpp) + a thin native-Anthropic translator; **no new hard dep**; credential-gated/out-of-CI | D4; ADR-0040; R1.1–R1.4, R4.1 |
| Tiered safety | logic-level reversibility classification: explicit `REVERSIBLE_OPS` allow-list auto-runs; **default DESTRUCTIVE → confirm-required** (safe default); enforced before dispatch, never prompt-based; undo stack backs the reversible guarantee | D3; DEP-3; ADR-0041; R5.4 |
| Injection defence | tool-results untrusted + bounded caps; only action path is the allow-listed dispatch + the gate; results are data | Article VII; ADR-0041; R5.1/R5.2 |
| Credential gating | mirror `cloud_live`: `assistant_live` optional extra (`keyring`) + `data/llm/token_store.py` (lazy keyring) + `assistant_live` pytest marker deselected in CI; keys never in `.pixproj`/logs | D5; DEP-4; ADR-0040 §5 |
| Embedding | in-app `ui/` chat dock + provider/key config + tiered-confirm; **and** a headless `pixelart-assistant` CLI in `data/assistant_cli.py` (mirrors `pixelart-run`) | D2; ADR-0042 |
| Responsiveness | loop runs off the GUI thread on a window-owned `QThreadPool` worker; **batch/off the per-frame loop** — 16 ms `FRAME_BUDGET_MS` does NOT gate a model call; **no AGT-10 per-frame directive required** (confirm-no-regression only) | DEP-5; Article VI; ADR-0042 §3 |
| Bounds | 5 named constants in `logic/constants.py`; exceeding → domain error | REQ-P14-LOGIC-007; Article II; §10 |
| Docs | new User-Guide **topic** under the existing `automation-and-scripting` section (`len(sections)==12` preserved) + README covering dock + CLI | REQ-P14-UI-008; ADR-0042 §4 |
| Testing | pytest + Hypothesis (logic/data headless via the fake `LLMPort` — catalog, schema projection, dispatch rejection, loop, tiered gate, injection, bounds, no-eval audit); pytest-qt both themes (UI); live adapter tests `@assistant_live`-marked, deselected | S8, Article IV; R6.2 |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

## 4. DEP resolutions (spec §8 — all resolved here)

- **DEP-1 (placement).** `data/llm/` is a **normal `data/` subpackage** (port + fake + real adapters +
  token store), mirroring `data/cloud/`; the CLI is `data/assistant_cli.py` (mirrors
  `data/automation_cli.py`). It is **NOT** a new top-level package (unlike `sync_backend`/`web_viewer`,
  which are out-of-process wire-reached deployables): `data/llm/` is in-process, imported, ships in the
  wheel. Governed by the existing `check_layering` `data` rule — **no rule change**. The **layering bridge**
  (the one subtlety): the loop is in `logic/` but the port is in `data/`; `logic/` defines the `ChatBackend`
  Protocol + shared value types and the concrete adapter is **dependency-injected** — no `logic → data`
  edge. **ADR-0040.** Confirmed `check_layering`/`check_cycles` hold (§11).
- **DEP-2 (tool-schema contract — FROZEN).** `ParamSchema` → JSON-Schema subset projection (type map;
  `required`; `allow_extra → additionalProperties`; `requires_seed →` explicit routed `seed` property);
  tool-call `{name, arguments}` → `macro.Op(name, params=arguments∖seed, seed=arguments.seed)` → `dispatch`;
  the schema is advisory, `ParamSchema.validate` + `dispatch` are authoritative — the projection **never
  widens** what dispatch accepts. **ADR-0039.**
- **DEP-3 (reversibility classification — FROZEN).** Explicit module-local `REVERSIBLE_OPS` allow-list
  (shipped built-ins `batch_recolour`, `procgen`); **default DESTRUCTIVE → confirm-required** (safe default,
  gate-closed); pure/deterministic/unit-testable/logic-level; the undo stack backs the reversible guarantee.
  **ADR-0041 §2.**
- **DEP-4 (packaging).** `assistant_live` optional extra (`keyring==25.7.0`) + `assistant_live` pytest
  marker (deselected in CI) + `pixelart-assistant` `[project.scripts]` entry — mirroring `cloud_live` /
  `pixelart-run`. **AGT-09 wires the pyproject + CI-deselection.** **ADR-0040 §5.**
- **DEP-5 (responsiveness).** Off the GUI thread on a worker; **batch/off the per-frame loop**, not
  `FRAME_BUDGET_MS`-gated; the assistant adds no new per-frame canvas work (its edits are the same undoable
  dispatch ops), so **AGT-10 need only confirm no canvas-frame regression — no render-strategy directive**.
  **ADR-0042 §3.**

## 5. `logic/` interface freeze — Slices 14A + 14C (new, Qt-free)

> Frozen BEFORE implementation (`interface-contract`) so 14B/14C/14D/14E/14F bind to a stable surface. Pure
> leaves over `scripting`/`macro`/`history`/`constants`; **zero Qt, no `data/` import, no `eval`/`exec`.**
> New exception `AssistantError(ValueError)` (loop/gate/bounds); `ScriptError`/`MacroError` reused from the
> dispatch path. `Reversibility` + `Role` are module-local vocabulary (ADR-0001/BF-2), NOT constants.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +5 assistant caps (leaf; names distinct from every shipped constant). | `MAX_ASSISTANT_TURNS`, `MAX_TOOL_CALLS_PER_TURN`, `MAX_TOOL_RESULT_BYTES`, `MAX_CONVERSATION_MESSAGES`, `ASSISTANT_REQUEST_TIMEOUT_S` | LOGIC-007 |
| `tool_catalog.py` | **new** (14A) | Read-only introspection over `_REGISTRY`: `ToolDescriptor(name, description, parameters)`; `build_tool_catalog()` (one descriptor per `registered_ops()`, tracks built-ins + namespaced plugin ops); `param_schema_to_json_schema(ParamSchema)` (frozen projection, ADR-0039 §3); `ToolCall(name, arguments)`; `to_op(ToolCall) -> macro.Op` + `execute_tool_call(document, ToolCall) -> history.Command` via `scripting.dispatch` (non-registered/invalid → `ScriptError`, doc byte-unchanged). Imports `scripting`, `macro`, `constants`. Zero Qt. | `ToolDescriptor`, `ToolCall`, `build_tool_catalog`, `param_schema_to_json_schema`, `to_op`, `execute_tool_call` | LOGIC-001, 002, 003 |
| `assistant.py` | **new** (14C) | Value types `Role`, `Message`, `Conversation`, `AssistantReply` + the `ChatBackend` **Protocol** (`respond(conversation, tools) -> AssistantReply`); `Reversibility` enum + `REVERSIBLE_OPS` + `classify_op(name)` (ADR-0041 §2); the bounded agentic loop `AssistantSession`/`run_turn(document, conversation, backend, *, confirm)` — tiered gate before dispatch, tool-result fed back as untrusted bounded input, iterate to `MAX_*` bounds → final message; `AssistantError`. Imports `tool_catalog`, `scripting`, `macro`, `history`, `constants`. Zero Qt, no `data/`. **No `eval`/`exec`.** | `Role`, `Message`, `Conversation`, `AssistantReply`, `ChatBackend`, `Reversibility`, `classify_op`, `AssistantSession`, `run_turn`, `AssistantError` | LOGIC-004, 005, 006, 007, 008 |

## 6. `data/llm/` + `data/` interface freeze — Slices 14B + 14D + 14F (new, Qt-free)

> `data/` may import `logic/` + `data/`, never `ui/`/Qt. The port imports the `logic/` value types
> (`data → logic`, allowed) and structurally satisfies `logic.assistant.ChatBackend`. `keyring` is
> lazy/optional (14A–14C + fake run without it). New exception `LLMError(ValueError)` family in `port.py`.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `data/llm/port.py` | **new** (14B) | The one `LLMPort(ABC)` — `respond(conversation, tools) -> AssistantReply` (satisfies `ChatBackend`), `is_configured() -> bool` (default `False`); `LLMError` family; no provider/HTTP/credential type in signatures. Imports the `logic` value types. Zero Qt. | `LLMPort`, `LLMError`, (re-export `Conversation`/`AssistantReply`/`ToolDescriptor` shapes) | DATA-001, 007 |
| `data/llm/fake_adapter.py` | **new** (14B) | Deterministic scripted `LLMPort`: a response program (final messages + scripted tool-calls incl. reversible/destructive, malicious-tool-result follow-ups, multi-step, and OpenAI-shape/Anthropic-shape emulation) — no network/key; reproducible run-to-run. | `FakeLLMAdapter` | DATA-002, 005 |
| `data/llm/token_store.py` | **new** (14B) | OS-keyring isolation modelled on `data/cloud/token_store.py`: **lazy** `keyring` import; template `pixelart-creator:assistant:{provider}`; `is_keyring_available`, `store_token`/`load_token`/`delete_token`; keys never leave `data/llm/`. | `store_token`, `load_token`, `delete_token`, `is_keyring_available`, `service_name` | DATA-003, 006 |
| `data/llm/openai_compatible.py` | **new** (14D) | Real stdlib-`urllib` OpenAI-compatible client (`/v1/chat/completions` + tools); maps conversation + `ToolDescriptor`→`{"type":"function",…}` and `tool_calls[]`→`ToolCall`; `ASSISTANT_REQUEST_TIMEOUT_S`; **no new hard dep**; credential-gated. | `OpenAICompatibleAdapter` | DATA-004, 006, 007 |
| `data/llm/anthropic_translator.py` | **new** (14D) | Real stdlib-`urllib` native-Anthropic translator (Messages/`tool_use`/`tool_result`, `input_schema`, `x-api-key`); same port; credential-gated. | `AnthropicAdapter` | DATA-005, 006, 007 |
| `data/assistant_cli.py` | **new** (14F) | Headless Qt-free `pixelart-assistant` driver mirroring `automation_cli.py`: load `.pixproj` (IO-3), construct an `LLMPort` (fake in CI), run `logic.assistant` loop, tiered gate with an explicit `--yes`/confirm affordance for destructive ops (never auto-run), save back; exit 0/1/2. Zero Qt; no `eval`/`exec`. | `main(argv) -> int`, `build_parser` | DATA-008 |

## 7. `ui/` interface freeze — Slice 14E (new; only Qt)

> Binds to 14A/14B/14C logic+data; Qt lives here only; the sole Qt undo-bridge stays `ui/commands.py`
> (one grouped `QUndoCommand` per assistant edit; chat/connect/confirm push none — CL-8 precedent). `ui/`
> holds **no** provider/HTTP type and **no** raw key beyond entry (REQ-P14-DATA-007, REQ-P14-UI-002). Both
> themes, a11y, `tr()`-wrapped strings (AGT-06/AGT-07). See ADR-0042 §1 for the full module table.

| Module | Change | Responsibility | Binds to | REQ |
| --- | --- | --- | --- | --- |
| `assistant_dock.py` | **new** | `Assistant_Dock(QDockWidget)`: transcript + input/send; drives the `logic/` loop via the injected backend, never a provider; shows replies + undoable edits; surfaces errors. | `logic/assistant`, `assistant_worker`, `commands` | UI-001, 004, 005, 006, 007 |
| `provider_config_dialog.py` | **new** | `Provider_Config_Dialog(QDialog)`: endpoint + key entry + select/connect; hands key to `data/llm/token_store`; retains no raw key; provider-agnostic; not-configured degrades. | `data/llm/token_store`, `data/llm/port` | UI-002, 005, 006, 007 |
| `assistant_worker.py` | **new** | `Assistant_Worker(QRunnable)` + signals on a window-owned `QThreadPool`: run the Qt-free loop off the GUI thread; progress/result/error/cancel; no Qt off-thread. | `logic/assistant`, `data/llm/*` | UI-004 |
| `commands.py` | extend | one grouped `QUndoCommand` per assistant **edit** delegating to the dispatch result; chat/connect/confirm push none; no domain math. | `history` + dispatch results | UI-001, 003 |
| `main_window.py` | extend | Assistant menu + dock; hold active document + injected adapter; wire the worker + tiered-confirm surface. | the new assistant UI | UI-001, 003 |

**Tiered-confirm (REQ-P14-UI-003):** the dock renders the logic gate's decision — destructive → explicit
confirm/cancel naming the action; reversible → apply + visible + undoable. UI **never relaxes** the
classification (ADR-0042 §1).

## 8. Docs surface (REQ-P14-UI-008; ADR-0042 §4)

A new in-app User-Guide **topic** under the existing `automation-and-scripting` section
(`len(sections) == len(REQUIRED_AREAS) == 12` preserved — a data change, no new area) + a README launch
surface documenting the dock **and** the `pixelart-assistant` CLI (provider/key config, credential-optional,
tiered-safety). AGT-08 authors the prose; AGT-07 extracts strings.

## 9. Packaging (AGT-09; DEP-4)

- `[project.optional-dependencies]` `assistant_live = ["keyring==25.7.0"]` (not a core dep).
- `[tool.pytest.ini_options].markers` += `assistant_live: live credential-gated provider tests, deselected in CI`.
- CI (`.github/workflows/ci.yml`) `-m` expression += `and not assistant_live`.
- `[project.scripts]` += `pixelart-assistant = "pixelart_creator.data.assistant_cli:main"`.
- `mypy` already covers `keyring.*` via `ignore_missing_imports` (pyproject).

## 10. Numerics (Article II)

Five new named constants in `logic/constants.py`, names distinct from every shipped constant (BF-1);
proposed values in ADR-0041 §4 (`MAX_ASSISTANT_TURNS=16`, `MAX_TOOL_CALLS_PER_TURN=8`,
`MAX_TOOL_RESULT_BYTES=65536`, `MAX_CONVERSATION_MESSAGES=256`, `ASSISTANT_REQUEST_TIMEOUT_S=60`). Exceeding
a bound raises `AssistantError`. No numeric literals for these caps in `logic/`/`data/`/`ui/`.

## 11. Layering / cycle proof (Article I — `check_layering` + `check_cycles` exit 0)

- `logic/tool_catalog.py` → `scripting`, `macro`, `constants` (logic→logic). No Qt/data/ui.
- `logic/assistant.py` → `tool_catalog`, `scripting`, `macro`, `history`, `constants` (logic→logic);
  defines the `ChatBackend` Protocol + shared value types. **Does not import `data/llm/`** — the backend is
  injected (the `macro.set_dispatcher`/`blend.CompositeNode` precedent). No Qt/data/ui.
- `data/llm/port.py` → the `logic` value types (**data→logic, allowed**), `abc`, `dataclasses`.
  `LLMPort` structurally satisfies `ChatBackend`. No Qt.
- `data/llm/{fake_adapter,openai_compatible,anthropic_translator,token_store}.py` → `data/llm/port` +
  `logic` types + stdlib (`urllib`, `json`) + lazy `keyring` (data→data, data→logic). No Qt.
- `data/assistant_cli.py` → `logic/assistant`, `logic/scripting`, `data/llm/*`, `data/project_io`
  (data→logic, data→data). No Qt.
- `ui/*` → `logic/*`, `data/llm/*`, Qt (ui→logic, ui→data, Qt). Allowed.

**No cycle:** `assistant → tool_catalog → scripting`; `data/llm → logic`; `logic` never imports
`data/llm`. **No new top-level package; no `check_layering` rule change.** Baseline confirmed clean at plan
time: `check_layering` (`--root pixelart_creator`) 180 modules clean + (`--root .`) 5 modules clean;
`check_cycles` no cycles on both roots — all exit 0. The plan implies **no** forbidden edge.

## 12. Note for the orchestrator — the `agt-12` LLM-integration asset question (13E-style)

The Researcher (bottom-line (b)) reads the cross-provider normalization + injection-resistant loop as
**leaning SUBSTANTIAL** specialist competence. My architectural read, now that the contracts are frozen:

- The **security-critical, specialist-stakes work is fully specified by ADR-0039/0041** — the action
  surface, the tool-schema projection, the tiered gate, and the injection defence are *ordinary `logic/`*
  once frozen, well within AGT-03's remit. Slices **14A/14B/14C/14F** need **no** new asset.
- The genuine specialist surface is **14D only**: the stdlib-`urllib` cross-provider wire normalization
  (OpenAI `tool_calls` vs Anthropic `tool_use`/`tool_result`, argument-fragment streaming reassembly,
  parallel-call handling, SSE sentinel variance — R1.4, R2.3, R2.4, R4.1). That is not boilerplate
  cloud-HTTP work.
- **Recommendation (per the standing generate-assets-on-demand memory — create when the roster has a gap,
  don't stretch):** a **focused skill** (e.g. `llm-adapter-normalization`) scoped to 14D's wire mapping,
  invoked by AGT-03, is proportionate — a full new `agt-12` agent is likely more than 14D warrants, since
  the loop/gate/catalog are already AGT-03-implementable from the ADRs. **Escalate the skill-vs-agent
  decision to the orchestrator at contract-freeze (13E-style)**; 14A–14C + 14F proceed with the current
  roster regardless. This is a flag, not a blocker.

## 13. Grounding

- Spec/acceptance/traceability `specs/phase-14-ai-assistant/*`. Constitution Articles I, II, IV, V, VI,
  VII, VIII, X, XI.
- Shipped `logic/scripting.py`, `logic/macro.py`, `logic/plugins.py`, `logic/history.py`,
  `data/cloud/{port,token_store,fake_adapter}.py`, `data/automation_cli.py`, `logic/guide_model.py`,
  `pyproject.toml` (`cloud_live` + `pixelart-run`).
- Researcher `docs/subagent-report-the-researcher-ad2616c7-20260707T220150.md`.
- ADR-0039/0040/0041/0042 (this phase); ADR-0021/0022 (Phase-8 security/DSL), ADR-0026 (cloud port),
  ADR-0027/0035 (out-of-three-layer package contrast), ADR-0020 (CLI-in-`data/` lesson), ADR-0029
  (User-Guide layering), ADR-0001 (module-local vocabulary).
