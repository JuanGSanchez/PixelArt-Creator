# Specification — Phase 14: In-App, Model-Agnostic AI Assistant

| Field | Value |
| --- | --- |
| Feature | `phase-14-ai-assistant` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-08 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, **VII**, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION — COMPLETE.** No AI assistant, no LLM port (`data/llm/`), no tool-schema/introspection facade over the DSL registry, no agentic conversation loop, no tiered-safety classifier, no chat dock, and no `pixelart-assistant` CLI exists yet. The shipped **Phase-8 safe automation surface** is the action surface and is **REUSED, not re-authored**: `logic/scripting.py` (the allow-listed `_REGISTRY`, `ParamSchema`, `register_command`, `registered_ops`, and the single trusted `dispatch()` — **zero `eval`/`exec`, everything undo-backed via `history.GroupCommand`**), `logic/macro.py` (`Op`/`Macro` DSL data types), and `logic/plugins.py` (consent-gated capability model). The shipped **Phase-10 `cloud_live` credential-gating pattern** is the model for this phase's credential gating and is **REUSED**: `data/cloud/token_store.py` (lazy/optional OS-keyring isolation), the `cloud_live` optional-dependency extra + the `cloud_live` pytest marker deselected in CI, and the port + fake-adapter + real-adapter-behind-the-same-interface shape of `data/cloud/`. All product-direction decisions are **FROZEN** (§10.1); no open clarifications remain. |
| REQ-ID range | `REQ-P14-LOGIC-001..008`, `REQ-P14-DATA-001..008`, `REQ-P14-UI-001..008` — **24 REQs, all drafted with full acceptance** (Gherkin in `acceptance.md`). Slice 14A = `LOGIC-001..003`; 14B = `DATA-001..003`; 14C = `LOGIC-004..008`; 14D = `DATA-004..007`; 14E = `UI-001..008`; 14F = `DATA-008`. |
| Layer scope | `pixelart_creator/logic/` (**14A** safe tool-catalog + JSON-schema introspection facade over the DSL registry; **14C** agentic conversation loop + tiered-safety classifier — **zero Qt, headless, unit-testable, no `eval`/`exec`**) + `pixelart_creator/data/llm/` (**14B** model-agnostic `LLMPort` ABC + deterministic fake/mock adapter + credential-gating scaffolding; **14D** stdlib-only OpenAI-compatible client + native-Anthropic translator adapter, credential-gated/out-of-CI — **zero Qt**, mirrors `data/cloud/`) + `pixelart_creator/ui/` (**14E** chat dock + provider/key config + tiered-confirmation surface — the only Qt) + `data/` CLI (**14F** `pixelart-assistant`, Qt-free, mirrors `pixelart-run`). The concrete placement of `data/llm/` (vs `data/`) is an **AGT-01 plan/ADR** decision (§8 DEP-1). |
| Binds to (upstream, **shipped** — REUSED) | Phase-8 `logic/scripting.py` (the **SCR-1** primitive: the allow-listed `_REGISTRY` + `ParamSchema` + `register_command`/`registered_ops`/`is_registered` + the single trusted `dispatch(document, ops)` that validates op-name against the allow-list and params against the schema, applies each op as one already-applied `GroupCommand`, and rolls back on failure — **there is no interpreter to escape; no `eval`/`exec`/`compile`/`__import__` on this path**, ADR-0021/0022), Phase-8 `logic/macro.py` (the **MAC-1** primitive: the `Op`/`Macro` JSON-native DSL data types the LLM emits and `dispatch` consumes), Phase-8 `logic/plugins.py` (the **PLG-1** primitive: the deny-by-default, consent-gated `PluginCapability` whose only surface is the DSL registry — the precedent for exposing the action surface without a back-door), Phase-1 `logic/history.py` (the **HIS-1** primitive: `Command`/`GroupCommand`, the undo stack that makes reversibility classifiable), Phase-10 `data/cloud/` (the **CLD-1** precedent: port ABC + fake adapter in CI + real adapter behind the same interface + `token_store.py` OS-keyring isolation + the `cloud_live` extra/marker credential-gating pattern this phase mirrors as `assistant_live`). |
| Depends on (external) | The Researcher — grounding **COMPLETE**: report `ad2616c7` (cited by the orchestrator). It grounds the security-invariant shape this spec's WHAT is phrased around: **Article VII by construction** (the action surface is the allow-listed registry, security is REGISTRY/PERMISSION enforcement, not the prompt); **tool RESULTS fed back into the loop are UNTRUSTED input** (prompt-injection defence — a tool-result cannot escalate privileges or invoke a non-whitelisted op; bound sizes/counts, reuse the `cloud_validation`-style caps); **Article I three-layer** (logic/data stay Qt-free; the LLM port + adapters live in `data/llm/` mirroring `data/cloud/`; the chat dock lives in `ui/`); **Article II** named constants for any caps. The HOW — exact wire format, the `urllib` client details, the tool-schema contract, the reversibility-classification mechanism, and the exact placement of `data/llm/` — is downstream (AGT-01 plan/ADR). |
| SDD phase | `specify` + `clarify` (this document, §10 clarifications **FROZEN**) → **COMPLETE / ready for `sdd-plan`** (AGT-01) |

---

## 1. Purpose (WHY)

The platform already ships the one thing a safe agentic assistant needs: a **data-driven, allow-listed
action surface with zero code execution**. Phase-8 built `logic/scripting.py` — a `_REGISTRY` of trusted
command factories, a defensive `ParamSchema` per op, and a single trusted `dispatch(document, ops)` that
validates each op-name against the allow-list and its params against the schema, applies the run as one
reversible `history.GroupCommand`, and rolls back on any failure. **There is no interpreter to escape:
ops are *data* mapped to registered factories; there is no `eval`/`exec`/`compile`/`__import__` of user
input anywhere on that path** (ADR-0021/0022, Article VII by construction). Phase-8 also shipped the
consent-gated `plugins.py` capability model whose only surface is that registry — the precedent for
exposing the action surface to an outside actor **without a back-door**.

Phase 14 — the **final roadmap phase** — adds an **in-app, model-agnostic AI assistant**: an agentic
structure that connects an **external** LLM (any provider), chats in-app, and drives the user's whole
workflow **through that existing safe, allow-listed action surface**. The LLM emits **tool-calls** that
map **1:1 onto allow-listed DSL ops** and run through the **existing trusted `dispatch()`** — **zero new
interpreter, zero `eval`/`exec`** (Article VII by construction), **everything undo-backed**. Security is
**registry/permission enforcement, not prompt engineering**: a model (or a malicious tool-result trying
to steer it) simply *cannot* invoke anything that is not a registered op, and cannot escalate past the
tiered-safety gate — because the enforcement lives in `logic/`, not in the prompt.

The assistant is **model-agnostic** (a provider-neutral LLM port over an OpenAI-compatible surface plus a
thin native-Anthropic translator — no lock-in), **credential-optional** (it ships and runs in CI with a
deterministic fake adapter; a real provider needs an out-of-CI, credential-gated extra, mirroring the
Phase-10 `cloud_live` pattern), and **out-of-CI for live calls** (no real key or network in the gate).

This document specifies WHAT and WHY, technology-neutral at the requirement level. The HOW — the exact
tool-schema wire contract, the `urllib` OpenAI-compatible client and Anthropic-translator details, the
concrete reversibility-classification mechanism, the chat-dock layout, and the exact placement of
`data/llm/` — is downstream (AGT-01 plan/ADR, grounded by the Researcher report `ad2616c7`).

## 2. Scope

**In scope now (WHAT), grouped by the six slices (the recommender's decomposition):**

### Slice 14A — safe tool-catalog + JSON-schema introspection over the DSL registry (`logic/`)
- A **tool-catalog introspection facade** (Qt-free, `logic/`) that enumerates the shipped allow-listed
  DSL registry (`scripting.registered_ops()` / `_REGISTRY`) and exposes each registered op as a
  **provider-neutral tool descriptor** — a name + human description + a **JSON-schema** derived from the
  op's shipped `ParamSchema` — suitable for LLM provider **function-calling** (REQ-P14-LOGIC-001,
  REQ-P14-LOGIC-002). The catalog is **read-only over the registry**: it adds **no** new executable op
  and **no** new registration path.
- **Tool-call → DSL op mapping through the trusted dispatch.** A provider tool-call (`{name, arguments}`)
  is translated into a `macro.Op` and executed **only** through the shipped `scripting.dispatch()`; a
  tool-call naming a **non-registered / forbidden op** is **rejected safely** (a domain error, the
  document left **byte-unchanged**), because dispatch validates against the allow-list — **the LLM has no
  path to any op outside the registry** (REQ-P14-LOGIC-003 — the whitelist-enforcement invariant).

### Slice 14B — model-agnostic LLM port + fake adapter + credential-gating scaffolding (`data/llm/`)
- A **model-agnostic `LLMPort` ABC** (Qt-free, `data/llm/`, mirroring `data/cloud/port.py`) that defines
  the **one** provider-neutral chat/function-calling interface every adapter implements: send a
  conversation + the available tool descriptors, receive either an assistant message or one-or-more
  tool-calls. **No provider SDK type, HTTP type, or credential type appears in its signatures**
  (REQ-P14-DATA-001, REQ-P14-DATA-007 posture).
- A **deterministic fake/mock adapter** (Qt-free) that fully implements the port with **scripted,
  reproducible** responses (including scripted tool-calls) so the **entire agentic contract** — the loop,
  tiered safety, whitelist enforcement, prompt-injection defence, model-agnostic behaviour — is
  **CI-testable headlessly with NO real provider key and NO network** (REQ-P14-DATA-002).
- **Credential-gating scaffolding** mirroring the shipped Phase-10 `cloud_live` pattern: an optional
  dependency extra **`assistant_live`**, **OS-keyring token storage** (a `data/llm/` token store modelled
  on `data/cloud/token_store.py` — lazy/optional import, never above the port), and an **`assistant_live`
  pytest marker deselected in CI** (REQ-P14-DATA-003). Keys are **never** written to `.pixproj` or logs.

### Slice 14C — agentic conversation loop + tiered-safety enforcement (`logic/`)
- An **agentic conversation loop** (Qt-free, `logic/`) that: sends the user turn + tool catalog to the
  `LLMPort`; on a tool-call, executes it through the trusted dispatch (14A); feeds the **tool-result back
  into the loop as UNTRUSTED input**; and iterates to a bounded turn/step limit until the model produces
  a final assistant message (REQ-P14-LOGIC-005).
- **Tiered-safety enforcement, at the logic level (NOT prompt-based).** Each candidate tool-call is
  **classified by reversibility** using the shipped undo stack: **reversible / undo-backed** actions
  **auto-run**; **destructive / hard-to-undo** actions **require explicit user confirmation** before they
  execute. The gate is enforced in `logic/` (the loop refuses to dispatch an unconfirmed destructive op),
  never by asking the model to behave (REQ-P14-LOGIC-004 — the tiered-safety-boundary invariant).
- **Prompt-injection defence.** A **tool-result** (the output of a dispatched op, or any content the loop
  feeds back) is treated as **untrusted input**: it is **bounded** (size/count caps, reusing the
  `cloud_validation`-style posture) and it **cannot escalate privileges or cause a non-whitelisted op to
  run** — because the only path to action remains the allow-listed dispatch + the tiered gate, and
  results are data, never instructions with authority (REQ-P14-LOGIC-006 — the injection-resistance
  invariant).
- **Bounded numerics** — every cap (max turns, max tool-calls/turn, max tool-result bytes, max
  conversation tokens/messages) is a **named constant in `logic/constants.py`** (REQ-P14-LOGIC-007,
  Article II). **Zero `eval`/`exec`** across the whole assistant path — **Article VII by construction**,
  source-auditable (REQ-P14-LOGIC-008).

### Slice 14D — real generic provider adapter, credential-gated / out-of-CI (`data/llm/`)
- A **real, generic provider adapter** behind the same `LLMPort`, built **stdlib-only (`urllib`)** as an
  **OpenAI-compatible chat/function-calling client** (covers OpenAI, Google Gemini's OpenAI-compat
  endpoint, Ollama, local llama.cpp) — **no new hard runtime dependency** (REQ-P14-DATA-004).
- A **thin native-Anthropic/Claude translator** behind the **same** `LLMPort`, mapping the port's
  provider-neutral conversation + tool descriptors onto the native Anthropic Messages/tool-use shape and
  back — proving **model-agnostic** parity (REQ-P14-DATA-005).
- The user configures an **arbitrary provider endpoint + API key**; the real adapter path is
  **credential-gated and OUT of the CI gate** (`assistant_live` extra + marker), keys held only in the OS
  keyring inside `data/llm/`, **never in `.pixproj` or logs** (REQ-P14-DATA-006). **No provider/HTTP
  detail leaks above the port** (REQ-P14-DATA-007, Article I).

### Slice 14E — in-app chat dock + config UI + User-Guide topic + README (`ui/`, the only Qt)
- An **in-app PySide6 chat DOCK** (`ui/`) to converse with the assistant and watch it drive the workflow;
  it drives the `logic/` loop and never talks to a provider directly (REQ-P14-UI-001).
- A **provider/key configuration UI** to set the arbitrary endpoint + API key and select/connect a
  provider; the key is handed to the `data/llm/` token store and is **never persisted to `.pixproj` or a
  log**, and `ui/` never holds a raw key beyond entry (REQ-P14-UI-002).
- A **tiered-safety confirmation surface**: destructive/hard-to-undo actions surface an **explicit
  confirm/cancel** prompt (driven by the logic-level classification, REQ-P14-LOGIC-004); reversible
  actions apply without a prompt but remain visible + undoable (REQ-P14-UI-003).
- **Responsiveness** (off the GUI thread; the app never freezes during a model call — REQ-P14-UI-004),
  **a11y** (REQ-P14-UI-005), **both themes** (REQ-P14-UI-006), **i18n** (REQ-P14-UI-007).
- **Standing docs rule (encode):** a **NEW in-app User-Guide topic under the EXISTING
  `automation-and-scripting` section** (a new *topic*, **NOT** a new section — preserving
  `len(sections) == len(REQUIRED_AREAS) == 12`, per shipped `logic/guide_model.py`), **plus** a **README
  launch surface** documenting the assistant dock + the `pixelart-assistant` CLI (REQ-P14-UI-008; README
  shared with 14F).

### Slice 14F — headless `pixelart-assistant` CLI (`data/`, Qt-free)
- A **headless `pixelart-assistant` CLI** (Qt-free, `data/`, **mirroring the shipped `pixelart-run`
  automation CLI**) that runs the same agentic loop against the same `LLMPort` over a `.pixproj`,
  registered as a `[project.scripts]` console entry point (REQ-P14-DATA-008). It uses the same tiered gate
  (a destructive op requires an explicit `--yes`/confirm affordance, never an auto-run) and the same fake
  adapter in CI. README documents it (REQ-P14-UI-008, shared).

**Out of scope (this phase):** see §6 Non-goals. Notably: the concrete tool-schema wire contract, the
`urllib` client's exact request/response shape, the reversibility-classification mechanism, the chat-dock
layout, the exact placement of `data/llm/`, and provider-specific model catalogues/pricing (all
AGT-01/ADR HOW); any new *executable* DSL op or a new registration back-door (the assistant only
introspects + drives the SHIPPED registry); training/fine-tuning/hosting a model (the LLM is always
external); billing/quota; no plan/tasks/code (AGT-01/03/05); no tests (AGT-04/06); no new runtime
technology decided here (S8 — the real adapter is deliberately stdlib-only, no new hard dep).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Artist / ai-chat).** As an artist, I want to **chat with an in-app AI assistant** that
  understands my project and can act on it, so I can describe what I want in words instead of clicking. →
  REQ-P14-UI-001, REQ-P14-LOGIC-005 · `ai-chat` · P14
- **US-2 (Artist / assistant-drives-workflow).** As an artist, I want the assistant to **actually perform
  edits** (recolour, procgen, batch ops, …) through the app's real, undoable action surface, so its
  actions are first-class edits I can undo. → REQ-P14-LOGIC-001, -003, -005 · `assistant-drives-workflow`
  · P14
- **US-3 (Safety-conscious user / tiered-safety).** As a user, I want **reversible actions to just run**
  but **destructive/hard-to-undo actions to ask me first**, enforced by the app (not by trusting the
  model), so the assistant can never quietly do something I can't take back. → REQ-P14-LOGIC-004,
  REQ-P14-UI-003 · `tiered-safety` · P14
- **US-4 (Security-conscious user / whitelist-enforcement).** As a user, I want the assistant to be
  **structurally unable to run anything outside the app's allow-listed operations** — no arbitrary code,
  no `eval`/`exec` — so a bad or manipulated model cannot escape the sandbox. → REQ-P14-LOGIC-003,
  REQ-P14-LOGIC-008 · `whitelist-enforcement` · P14
- **US-5 (Security-conscious user / injection-resistance).** As a user, I want a **malicious tool-result
  or injected instruction to be unable to escalate** — it can't trigger a non-whitelisted action or
  bypass the confirm gate — so untrusted content in the loop stays powerless. → REQ-P14-LOGIC-006 ·
  `injection-resistance` · P14
- **US-6 (Artist / model-agnostic).** As an artist, I want to **use any LLM provider** (OpenAI-compatible
  endpoints, Gemini compat, Ollama, local llama.cpp, or native Anthropic/Claude) behind **one** interface,
  so I'm not locked to one vendor. → REQ-P14-DATA-001, -004, -005 · `model-agnostic` · P14
- **US-7 (Privacy-conscious user / credential-optional).** As a user, I want the assistant to be
  **credential-optional** — it ships and is fully tested with a fake adapter needing **no key**, and I
  supply my own endpoint + key only when I want live calls; **my key is never written to my project file
  or logs**. → REQ-P14-DATA-002, -003, -006, REQ-P14-UI-002 · `credential-optional` · P14
- **US-8 (Power user / headless-assistant).** As a power user, I want a **headless `pixelart-assistant`
  CLI** (mirroring `pixelart-run`) so I can drive the assistant over a `.pixproj` in scripts/automation,
  Qt-free. → REQ-P14-DATA-008 · `headless-assistant` · P14
- **US-9 (Maintainer / testable-without-network).** As a maintainer, I want the **whole agentic contract
  tested by the fake adapter with no network or credentials**, so CI verifies the loop + tiered safety +
  whitelist + injection defence deterministically, and the live path is a deselected marker. →
  REQ-P14-DATA-002, -003, REQ-P14-LOGIC-008 · `testable-adapter` · P14
- **US-10 (Any user / a11y-theme-i18n).** As a keyboard / dark-mode / non-English user, I want the chat
  dock and config UI **keyboard-reachable, correct in both themes, fully translatable**. →
  REQ-P14-UI-005, -006, -007 · `a11y`, `theming`, `i18n` · P14
- **US-11 (Learner / discoverability).** As a new user, I want an **in-app User-Guide topic** (under
  Automation & Scripting) and a **README** entry explaining the assistant + the CLI, so the feature is
  discoverable and documented. → REQ-P14-UI-008 · `docs` · P14

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase | Slice |
| --- | --- | --- | --- |
| `tool-catalog` | Read-only introspection facade exposing each allow-listed DSL op as a JSON-schema tool. | 14 | 14A |
| `whitelist-enforcement` | The LLM can drive only allow-listed ops through trusted `dispatch`; non-registered → safe reject, doc unchanged. | 14 | 14A/14C |
| `llm-port` | The ONE model-agnostic `LLMPort` interface every adapter implements; no provider leak. | 14 | 14B |
| `testable-adapter` | A deterministic fake/mock adapter verifying the whole agentic contract with no network/key. | 14 | 14B |
| `credential-optional` | Credential-gating via `assistant_live` extra + OS keyring + deselected marker; keys never in `.pixproj`/logs. | 14 | 14B/14D |
| `ai-chat` | The in-app conversation loop between the user and the external LLM. | 14 | 14C/14E |
| `assistant-drives-workflow` | The assistant performs real, undoable edits through the shipped action surface. | 14 | 14C |
| `tiered-safety` | Logic-level reversibility gate: reversible auto-runs; destructive requires explicit confirm. | 14 | 14C/14E |
| `injection-resistance` | Tool-results are untrusted, bounded input; cannot escalate or invoke non-whitelisted ops. | 14 | 14C |
| `no-eval-exec` | Zero `eval`/`exec`/`compile`/`__import__` on the whole assistant path (Article VII by construction). | 14 | 14A/14C |
| `model-agnostic` | One port works for OpenAI-compatible + native Anthropic (via translator). | 14 | 14D |
| `headless-assistant` | The Qt-free `pixelart-assistant` CLI mirroring `pixelart-run`. | 14 | 14F |
| `docs` | New in-app User-Guide topic (under Automation, not a new section) + README launch surface. | 14 | 14E/14F |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 14 | 14E |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a principle (`P2` determinism), a constitution article,
and/or a forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a shipped callable (SCR-1 `scripting`, MAC-1 `macro`, PLG-1 `plugins`, HIS-1 `history`, CLD-1
`data/cloud`) is a **constraint**, not a HOW choice.

### Slice 14A — `logic/` — safe tool-catalog + JSON-schema introspection (new, Qt-free)

#### REQ-P14-LOGIC-001 — Tool-catalog facade enumerates the allow-listed DSL registry (read-only)
`traces:` **SCR-1** (`logic/scripting.py`), **PLG-1**, S7, S11, Article I, Article XI, Phase-14 capability (tool catalog)
A Qt-free `logic/` facade exposes the currently **registered** DSL ops (via the shipped
`scripting.registered_ops()` / `is_registered`) as a set of **provider-neutral tool descriptors**, each
carrying a stable op-name + a human-readable description. The facade is **read-only over the registry**:
it introduces **no** new executable op and **no** new registration path — an op is a tool **iff** it is
already in the allow-list (`_REGISTRY`), so the catalog automatically tracks built-ins **and**
consent-gated plugin ops (namespaced `"<plugin>.<op>"`, PLG-1) without a separate list to drift.

#### REQ-P14-LOGIC-002 — Each op is exposed as a JSON-schema tool for provider function-calling
`traces:` **SCR-1** (`ParamSchema`), S11, Article I, Article XI, Researcher `ad2616c7`, Phase-14 capability (introspection)
For each registered op, the facade derives a **JSON-schema tool definition** from the op's shipped
`ParamSchema` (`fields` → property types, `required` → required list, `allow_extra` →
additional-properties posture, `requires_seed` → the seed parameter) so a provider's **function-calling**
surface can select and populate the op's parameters. The schema is a **faithful projection** of the
already-enforced `ParamSchema` (it never widens what dispatch will accept); the concrete JSON-schema wire
contract (draft version, type-name mapping) is an AGT-01/ADR HOW (§8 DEP-2).

#### REQ-P14-LOGIC-003 — A tool-call maps 1:1 to an allow-listed op via trusted dispatch; anything else is safely rejected
`traces:` **SCR-1** (`dispatch` allow-list + atomicity), **MAC-1** (`Op`), Article VII, Article I, S11, Researcher `ad2616c7`
A provider **tool-call** (`{name, arguments}`) is translated into a `macro.Op` and executed **only**
through the shipped trusted `scripting.dispatch(document, ops)` — the **single** validated path (op-name
checked against the allow-list, params against the `ParamSchema`, applied as one reversible
`GroupCommand`, rolled back on failure). A tool-call naming a **non-registered / forbidden op**, or with
**invalid params**, is **rejected safely**: dispatch raises `ScriptError` (surfaced to the loop/user as a
domain error) and the **document is left byte/state-identical to before the call** (the shipped
Phase-1-validate-then-apply atomicity). **The LLM has NO path to any operation outside the registry** —
this is the whitelist-enforcement invariant, enforced by the shipped dispatch, not by the prompt.

### Slice 14C — `logic/` — agentic conversation loop + tiered-safety enforcement (new, Qt-free)

#### REQ-P14-LOGIC-004 — Tiered-safety gate classifies reversibility and gates destructive actions (logic-level)
`traces:` **HIS-1** (undo stack), **SCR-1**, Article VII, Article I, S11, D3 (tiered posture), Researcher `ad2616c7`
Every candidate tool-call is **classified by reversibility** before it can affect the document:
- **Reversible / undo-backed** actions (the shipped ops apply as an undoable `GroupCommand`, HIS-1)
  **auto-run** without prompting.
- **Destructive / hard-to-undo** actions **require explicit user confirmation** before dispatch; without
  confirmation the loop **refuses to dispatch** the op (it is neither applied nor silently skipped past
  the gate — the user is asked, or the CLI requires an explicit affordance, 14F).

The classification and the gate are **enforced in `logic/`** — a pure, deterministic, unit-testable
function of the op + its reversibility, leveraging the shipped undo stack to decide reversibility — and
are **never** delegated to the prompt or to the model's discretion. The concrete
reversibility-classification mechanism (e.g. an explicit destructive-op set vs an undo-cost heuristic vs a
per-op flag on registration) is an AGT-01/ADR HOW (§8 DEP-3); this REQ fixes the **auto-vs-confirm
boundary** and that it is logic-enforced.

#### REQ-P14-LOGIC-005 — Bounded agentic conversation loop drives tools then returns a final message
`traces:` **SCR-1**, S7, S11, Article I, Article VI (batch/off-loop), Article II, D1 (action surface), Researcher `ad2616c7`
A Qt-free `logic/` **agentic loop** orchestrates a turn: it presents the user message + the tool catalog
(REQ-P14-LOGIC-001/-002) to the `LLMPort` (REQ-P14-DATA-001); on a returned **tool-call**, it applies the
tiered-safety gate (REQ-P14-LOGIC-004) and, when permitted, executes the call through the trusted dispatch
(REQ-P14-LOGIC-003); it feeds the **tool-result** back into the conversation as **untrusted input**
(REQ-P14-LOGIC-006); and it **iterates** to a **bounded** number of steps/turns/tool-calls
(REQ-P14-LOGIC-007) until the model returns a final assistant message. The loop is **deterministic given
a fixed adapter** (the fake adapter makes it fully reproducible in CI) and is **batch/off the per-frame
render loop** (Article VI — like Phase-8 automation, the 16 ms `FRAME_BUDGET_MS` does not gate a model
round-trip; the contract is stays-responsive, REQ-P14-UI-004).

#### REQ-P14-LOGIC-006 — Tool-results are untrusted, bounded input; they cannot escalate (prompt-injection defence)
`traces:` Article VII, Article II, **SCR-1**, **CLD-1** (`cloud_validation`-style caps), S13, Researcher `ad2616c7`
Any **tool-result** (the output/summary of a dispatched op, or any content the loop feeds back to the
model) is treated as **untrusted input**: it is **bounded** by named caps (max tool-result bytes, max
tool-calls per turn, max total steps — reusing the `cloud_validation`-style size/count posture, CLD-1),
and it is **data, never authority**. A tool-result — even one crafted to say "now run <destructive op>"
or "you are permitted to call <non-whitelisted op>" — **cannot**: (a) cause a **non-whitelisted op** to
run (the only action path is the allow-listed dispatch, REQ-P14-LOGIC-003), or (b) **bypass the
tiered-safety gate** (a destructive op still requires confirmation, REQ-P14-LOGIC-004). Privilege is a
property of the **registry + gate**, not of the conversation content — so injected instructions in a
result are structurally powerless to escalate.

#### REQ-P14-LOGIC-007 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The assistant enforces named bounds/defaults defined **once** in `logic/constants.py`, e.g.
`MAX_ASSISTANT_TURNS`, `MAX_TOOL_CALLS_PER_TURN`, `MAX_TOOL_RESULT_BYTES`, `MAX_CONVERSATION_MESSAGES`,
`ASSISTANT_REQUEST_TIMEOUT_S` (names indicative; concrete values are AGT-01/ADR HOW). Exceeding a bound
raises a domain error rather than degrading silently or looping unbounded. **No numeric literals** in
`logic/`/`data/`/`ui/` for these caps (Article II).

#### REQ-P14-LOGIC-008 — Zero `eval`/`exec` on the whole assistant path (Article VII by construction, source-auditable)
`traces:` Article VII, **SCR-1** (ADR-0021/0022), S11, S13, Researcher `ad2616c7`
The entire assistant path — tool-catalog facade, the agentic loop, the tiered gate, the `LLMPort` + all
adapters, and the CLI — contains **no `eval`, `exec`, `compile`, or `__import__` of model output or
tool-result content**. Model output is **data** (a message or a `{name, arguments}` tool-call) mapped
onto the allow-listed registry; there is **no interpreter to escape** (inheriting the Phase-8
by-construction guarantee, SCR-1). This is **source-auditable**: a static scan of the Phase-14 modules
finds zero such calls (the acceptance scenario is a source audit; AGT-04/AGT-06 verify).

### Slice 14B — `data/llm/` — model-agnostic LLM port + fake adapter + credential gating (new, Qt-free)

#### REQ-P14-DATA-001 — One model-agnostic `LLMPort` abstracts all providers
`traces:` **CLD-1** (`data/cloud/port.py`), S7, S11, Article I, Article XI, D4 (LLM port), Researcher `ad2616c7`
`data/llm/` defines **one** abstract interface ("the LLM port") that every provider adapter implements,
exposing a bounded, provider-neutral chat/function-calling verb set: given a **conversation** (ordered
messages) + the available **tool descriptors** (REQ-P14-LOGIC-002), return either a final **assistant
message** or one-or-more **tool-calls** (`{name, arguments}`). The interface names **no** provider and
carries **no** provider SDK type, HTTP type, or credential type in its signatures (REQ-P14-DATA-007). It
is pure `data/` (zero Qt), mirroring the shipped `CloudPort` ABC. Adding a provider is adding an adapter
implementing this port — nothing above it changes.

#### REQ-P14-DATA-002 — A deterministic fake/mock adapter implements the whole port, testable with no network or key
`traces:` **CLD-1** (fake adapter in CI), S13, Article IV, S11, D5 (fake in CI), Researcher `ad2616c7`
A **deterministic fake/mock adapter** fully implements the `LLMPort` with **scripted, reproducible**
responses — including scripted **tool-calls** (reversible and destructive), scripted **malicious
tool-result** follow-ups, and scripted multi-step sequences — so the **entire agentic contract** (the
loop -005, tiered safety -004, whitelist enforcement -003, injection resistance -006, model-agnostic
parity -005 real) is **exercised headlessly in CI with NO network access and NO provider key**,
deterministically and portably (Article IV). The fake adapter is the **credential-optional** guarantee:
CI never needs a real key (D5). Real adapters (14D) implement the **same** port.

#### REQ-P14-DATA-003 — Credential-gating scaffolding mirrors the shipped `cloud_live` pattern
`traces:` **CLD-1** (`token_store.py` + `cloud_live` extra/marker), Article VII (no secrets), S11, Article I, D5
The credential-gating scaffolding mirrors the shipped Phase-10 `cloud_live` pattern exactly:
- an **optional-dependency extra `assistant_live`** in `pyproject.toml` (the live-provider deps; **not** a
  core runtime dep — CI must not require it), and
- an **OS-keyring token store** under `data/llm/` (modelled on `data/cloud/token_store.py`: **lazy/optional
  import**, keyed per provider, so all of Slices 14A–14C + the fake adapter import and run **without** the
  keyring package installed), and
- an **`assistant_live` pytest marker** registered in `pyproject.toml` and **deselected in the CI gate**
  (like `cloud_live`), so live-key/network tests never run in CI.
Any provider key is acquired/stored/used **entirely inside** `data/llm/` — **never** in `logic/`/`ui/`,
**never committed**, **never written to a `.pixproj` or a log** (Article VII §3). The port exposes only a
provider-agnostic "configured / not configured" notion; `ui/` never holds a raw key beyond entry.

### Slice 14D — `data/llm/` — real generic provider adapter (new, Qt-free, credential-gated/out-of-CI)

#### REQ-P14-DATA-004 — Stdlib-only OpenAI-compatible client adapter (no new hard dependency)
`traces:` **CLD-1** (real adapter behind same port), S8 (fixed stack / no new hard dep), Article I, D4, Researcher `ad2616c7`
A **real, generic provider adapter** behind the same `LLMPort`, implemented **stdlib-only** (an
OpenAI-compatible chat + function-calling client over `urllib` — **no new hard runtime dependency**), so
a user configuring an **OpenAI-compatible endpoint** (OpenAI, Google Gemini's OpenAI-compat endpoint,
Ollama, local llama.cpp, or any compatible server) can drive the assistant. It maps the port's
provider-neutral conversation + tool descriptors onto the OpenAI-compatible request/response + tool-call
shape and back. The concrete request/response wire format, streaming posture, and retry/timeout handling
are AGT-01/ADR HOW (grounded by Researcher `ad2616c7`).

#### REQ-P14-DATA-005 — Thin native-Anthropic/Claude translator behind the same port (model-agnostic parity)
`traces:` **CLD-1**, S8, Article I, Article XI, D4 (Anthropic translator), Researcher `ad2616c7`
A **thin native-Anthropic/Claude translator** adapter behind the **same** `LLMPort` maps the port's
provider-neutral conversation + tool descriptors onto the **native Anthropic Messages / tool-use** shape
(and the response/tool-use back), proving the port is genuinely **model-agnostic** — the same loop, tool
catalog, and tiered gate work unchanged across an OpenAI-compatible provider and native Anthropic. Also
stdlib-only (`urllib`); no new hard dependency. Exercised in CI **through the fake adapter** (the
model-agnostic acceptance scenario drives the same contract via the fake, no live key), with live
Anthropic calls credential-gated/out-of-CI (REQ-P14-DATA-006).

#### REQ-P14-DATA-006 — Live provider path is credential-gated and out of CI; keys never in `.pixproj` or logs
`traces:` Article VII (no secrets), Article IV, **CLD-1** (`cloud_live` posture), D4/D5, S13
The user configures an **arbitrary provider endpoint + API key**; the real-adapter live path (14D) is
**credential-gated** (`assistant_live` extra) and **OUT of the CI gate** (`assistant_live` marker
deselected, REQ-P14-DATA-003). The key is held **only** in the OS keyring inside `data/llm/`
(REQ-P14-DATA-003), used only to authenticate the outbound provider request, and is **never** written to
a `.pixproj`, a log, or any committed artefact (Article VII §3). CI determinism comes entirely from the
fake adapter (REQ-P14-DATA-002); a missing key/endpoint degrades to a clear "not configured" state, never
a crash.

#### REQ-P14-DATA-007 — No provider/HTTP detail leaks above the LLM port
`traces:` Article I, S11, **CLD-1**
No provider SDK type, credential type, HTTP/`urllib` type, or provider-specific exception appears in
`logic/` or `ui/`, or in the `LLMPort`'s public signatures — they live **only inside** the concrete
adapters under `data/llm/`. `logic/` (the loop, gate, catalog) and `ui/` (the dock) depend solely on the
port's own abstractions and its own exception family. Enforced by `check_layering` / `check_cycles`
(`data/llm/` imports no Qt; the only Qt outside `ui/` remains `ui/commands.py`).

### Slice 14F — `data/` — headless `pixelart-assistant` CLI (new, Qt-free)

#### REQ-P14-DATA-008 — Headless `pixelart-assistant` CLI mirrors `pixelart-run`, Qt-free
`traces:` **CLD-1**, Phase-8 `pixelart-run` (automation CLI precedent), S11, Article I, Article IV, D2 (headless CLI), Article VII
A **headless `pixelart-assistant` CLI** (Qt-free, `data/`, **mirroring the shipped `pixelart-run`**
automation CLI) runs the same agentic loop (REQ-P14-LOGIC-005) against the same `LLMPort` over a
`.pixproj`, and is registered as a `[project.scripts]` console entry point. It reuses the **same tiered
gate** (REQ-P14-LOGIC-004): a **destructive** op requires an **explicit affordance** (e.g. a `--yes` /
confirm flag) — **never** an auto-run — while reversible ops apply and the result is saved back through
the shipped `.pixproj` path. It uses the **fake adapter in CI** (no key/network) and the credential-gated
real adapter otherwise (REQ-P14-DATA-006). Zero Qt; no `eval`/`exec` (REQ-P14-LOGIC-008).

### Slice 14E — `ui/` — chat dock + provider/key config + tiered-confirm + docs (new; only Qt)

#### REQ-P14-UI-001 — In-app chat dock drives the agentic loop
`traces:` REQ-P14-LOGIC-005, S7, Article V, D2 (chat dock)
The UI provides an in-app **chat dock** (a PySide6 dockable panel) where the user converses with the
assistant and watches it drive the workflow — sending a message, seeing the assistant's replies and the
actions it takes (as real, undoable edits). The dock **drives the `logic/` loop** and **never talks to a
provider directly** (no provider/HTTP type in `ui/`, REQ-P14-DATA-007). Errors are surfaced (not
swallowed). Translatable labels.

#### REQ-P14-UI-002 — Provider/key configuration UI; the key is never persisted to `.pixproj` or logs
`traces:` REQ-P14-DATA-003, -006, Article VII (no secrets), Article V
The UI lets the user configure an **arbitrary provider endpoint + API key** and select/connect a
provider through the port's provider-agnostic surface. The entered key is handed to the `data/llm/` token
store (OS keyring) and is **never** written to a `.pixproj`, a log, or any committed artefact; `ui/` does
not retain a raw key beyond the entry hand-off (Article VII §3). The app behaves identically regardless
of the chosen provider (REQ-P14-DATA-001). A "not configured" state degrades gracefully to the fake/no-op
path. Translatable labels.

#### REQ-P14-UI-003 — Tiered-safety confirmation surface (destructive confirm; reversible auto)
`traces:` REQ-P14-LOGIC-004, Article V, Article VII, D3
When the logic-level tiered gate classifies a pending action as **destructive / hard-to-undo**, the UI
surfaces an **explicit confirm / cancel** prompt naming the action, and the action **only** executes on
confirmation; **reversible** actions apply without a prompt but remain **visible and undoable**. The UI
renders the gate's decision — it does **not** re-implement or relax the classification (which lives in
`logic/`, REQ-P14-LOGIC-004). Translatable labels + messages.

#### REQ-P14-UI-004 — The assistant keeps the UI responsive *(NFR, Article VI posture)*
`traces:` REQ-P14-LOGIC-005, S7, Article VI
A model round-trip / agentic step **does not freeze the UI** — it runs off the GUI thread and the app
stays responsive (progress/cancel where a long call warrants it). The assistant is **batch work off the
per-frame loop** (REQ-P14-LOGIC-005) — the 16 ms `FRAME_BUDGET_MS` does not gate a model call; whether a
worker thread/executor is used is an AGT-01/AGT-10 HOW. This REQ fixes the observable **stays-responsive**
contract.

#### REQ-P14-UI-005 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive assistant control (the chat input/send, the message transcript, the confirm/cancel
prompt, the provider/key config fields, connect/disconnect) exposes an accessible name and, where
non-obvious, a description; is keyboard-reachable in a logical order; shows a visible focus indicator.
Verified by AGT-06 (`a11y-audit`).

#### REQ-P14-UI-006 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The chat dock, provider/key config UI, and the tiered-confirm prompt render correctly in both light and
dark themes; colours are defined once by role, never hard-coded per widget. Both themes are test-verified
(AGT-06 pytest-qt).

#### REQ-P14-UI-007 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 14 (chat dock labels/placeholders, action/confirm-prompt text,
config-field labels, provider names shown generically, status/error messages) is wrapped in `tr()` /
`translate()`; none is a bare literal. Hand-built widgets re-set text on `QEvent.LanguageChange`. Verified
by `string_audit_check` (AGT-07); an unwrapped string is blocking.

#### REQ-P14-UI-008 — In-app User-Guide topic (under the existing Automation section) + README launch surface
`traces:` Article V, `logic/guide_model.py` (`REQUIRED_AREAS`), Phase-8/10/11 docs precedent, standing docs rule
The docs surface for the assistant is added as:
- a **NEW in-app User-Guide topic** under the **EXISTING `automation-and-scripting` section** of the
  shipped guide manifest — a **new *topic*, NOT a new section** — so `len(sections)` stays equal to
  `len(REQUIRED_AREAS)` (== 12, per shipped `logic/guide_model.py`; adding a topic is a data change, no
  new required area); AGT-08 authors the prose, and
- a **README launch surface** documenting **both** the in-app assistant dock **and** the
  `pixelart-assistant` CLI (REQ-P14-DATA-008) — how to configure a provider/key, that it is
  credential-optional, and the tiered-safety behaviour.
Content prose is AGT-08's; this REQ fixes that the topic is a **new topic under Automation (not a new
section)** and that the README covers both launch surfaces.

## 5. Non-functional requirements (constitution-tied acceptance)

Captured inline in §4: REQ-P14-LOGIC-005 (off the interactive loop / batch posture, Article VI),
REQ-P14-UI-004 (stays-responsive), REQ-P14-UI-005 (a11y, Article V), REQ-P14-UI-006 (both themes,
Article V), REQ-P14-UI-007 (i18n, Article V), REQ-P14-LOGIC-003/-006/-008 + REQ-P14-DATA-003/-006
(security — whitelist enforcement, untrusted tool-results / prompt-injection defence, zero `eval`/`exec`,
no secrets in `.pixproj`/logs; Article VII), REQ-P14-LOGIC-007 (bounded numerics, Article II),
REQ-P14-DATA-002 (deterministic, headless, no-network testability; Article IV).

**Security posture summary (Article VII, the heart of this phase):**
- **Action surface = the allow-listed registry.** The LLM drives only registered ops through the shipped
  trusted `dispatch`; **zero new interpreter, zero `eval`/`exec`** (REQ-P14-LOGIC-003/-008 — Article VII
  **by construction**, inheriting Phase-8 ADR-0021/0022).
- **Security is registry/permission enforcement, not the prompt.** The whitelist + the tiered gate live
  in `logic/`; no amount of clever prompting or injected tool-result content can invoke a non-whitelisted
  op or bypass the confirm gate (REQ-P14-LOGIC-004/-006).
- **Tool-results are untrusted, bounded input** (prompt-injection defence, `cloud_validation`-style caps —
  REQ-P14-LOGIC-006).
- **No secrets leak.** Keys live only in the OS keyring inside `data/llm/`, never in `.pixproj`/logs, and
  the live path is out of CI (REQ-P14-DATA-003/-006).

## 6. Non-goals (explicit; deferred)

- **The concrete tool-schema wire contract, the `urllib` OpenAI-compatible client's exact request/response
  shape, the native-Anthropic mapping details, the reversibility-classification mechanism, the chat-dock
  layout, and the exact placement of `data/llm/`** — all AGT-01 plan/ADR HOW (grounded by Researcher
  `ad2616c7`). (§8 DEP-1..DEP-3.)
- **Live third-party provider calls in CI** — the real OpenAI-compatible + Anthropic adapters are
  implemented behind the same port but **credential-gated / out of the CI gate** (`assistant_live` extra +
  marker, mirroring `cloud_live`). CI determinism comes entirely from the fake adapter.
- **Any NEW *executable* DSL op or a new registration back-door** — the assistant only **introspects** and
  **drives** the SHIPPED allow-listed registry; it never adds a bypass (that would break the Phase-8
  security model). New ops, if ever wanted, are Phase-8-style registrations owned by AGT-03, not an
  assistant concern.
- **Training/fine-tuning/hosting a model; provider model catalogues/pricing; billing/quota; embedded
  webviews** — the LLM is always **external**, model-agnostic, credential-optional; out of Phase 14.
- **Re-implementing the action surface, the undo stack, or the credential-gating machinery** — Phase 14
  **composes** the shipped `scripting`/`macro`/`plugins`/`history` and the `data/cloud` `cloud_live`
  pattern; it does not fork them (Article I).
- No plan/tasks (AGT-01); no logic/UI/data/CLI/test code (AGT-03/05/04/06); no new runtime technology
  decided here (S8 — the real adapter is deliberately stdlib-only).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED:**
  - **Phase-8** `logic/scripting.py` (SCR-1 — the allow-listed `_REGISTRY` + `ParamSchema` + trusted
    `dispatch`, **the action surface**, `eval`/`exec`-free by construction), `logic/macro.py` (MAC-1 —
    the `Op`/`Macro` DSL types the LLM emits), `logic/plugins.py` (PLG-1 — the consent-gated capability
    precedent for exposing the registry without a back-door).
  - **Phase-1** `logic/history.py` (HIS-1 — the `Command`/`GroupCommand` undo stack that makes
    reversibility classifiable for the tiered gate).
  - **Phase-10** `data/cloud/` (CLD-1 — port ABC + fake-adapter-in-CI + real-adapter-behind-the-same-
    interface + `token_store.py` OS-keyring isolation + the `cloud_live` extra/marker credential-gating
    pattern this phase mirrors as `assistant_live`), and the `cloud_validation`-style size/count caps
    posture reused for bounding tool-results.
  - The shipped `logic/guide_model.py` (`REQUIRED_AREAS` / `automation-and-scripting` section) — the
    User-Guide topic is added under it as a new topic (REQ-P14-UI-008).
  Phase 14 **composes** these; it must not re-implement the action surface, the undo path, or the
  credential machinery (Article I / VII).
- **The allow-listed registry IS the action surface** (D1). The assistant's entire ability to act is
  bounded by what is registered — which is precisely why Article VII holds by construction.
- **Researcher grounding is COMPLETE** (report `ad2616c7`): Article VII by construction (registry action
  surface, no `eval`/`exec`); tool-results are untrusted input (prompt-injection defence, bounded caps);
  Article I three-layer (LLM port + adapters in `data/llm/` mirroring `data/cloud/`; chat dock in `ui/`);
  Article II named constants. This grounds the *HOW* AGT-01 will plan; it introduces no open product
  question (all frozen, §10).
- **Article VI posture:** the assistant is **batch/background** work off the per-frame render loop
  (REQ-P14-LOGIC-005 / REQ-P14-UI-004) — a model round-trip is not `FRAME_BUDGET_MS`-gated; the contract
  is stays-responsive. (Unlike Phase-10 real-time, no per-frame patch-apply is introduced here — the
  assistant's edits are the same undoable ops the app already applies.)
- **NEW vs REUSED (explicit):**
  - **NEW (14A/14C, `logic/`):** the tool-catalog + JSON-schema introspection facade, the agentic loop,
    the tiered-safety classifier/gate, and new constants (`MAX_ASSISTANT_TURNS`,
    `MAX_TOOL_CALLS_PER_TURN`, `MAX_TOOL_RESULT_BYTES`, `MAX_CONVERSATION_MESSAGES`,
    `ASSISTANT_REQUEST_TIMEOUT_S`).
  - **NEW (14B/14D/14F, `data/`):** `data/llm/` (the `LLMPort` ABC + the fake adapter + the stdlib
    OpenAI-compatible adapter + the Anthropic translator + the OS-keyring token store), the `pixelart-
    assistant` CLI, the `assistant_live` optional extra + pytest marker.
  - **NEW (14E, `ui/`):** the chat dock, the provider/key config UI, the tiered-confirm surface, the
    User-Guide topic (data change under the existing Automation section) + README updates.
  - **REUSED:** `logic/scripting.py` (SCR-1), `logic/macro.py` (MAC-1), `logic/plugins.py` (PLG-1),
    `logic/history.py` (HIS-1), `data/cloud/` port+fake+token-store+`cloud_live` pattern (CLD-1),
    `logic/guide_model.py`.

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

*(All §10 items are FROZEN — no open blockers remain. These are HOW/assessment flags for the plan/ADR.)*

- **DEP-1 (AGT-01, placement + ADR).** The exact placement of the LLM port + adapters — **`data/llm/`**
  (this spec's assumption, mirroring `data/cloud/`) **vs** a flat `data/` module — and whether the CLI
  lives at `data/assistant_cli.py` (mirroring `data/automation_cli.py`). AGT-01 owns the placement
  decision + an ADR; `check_layering`/`check_cycles` must stay green (data Qt-free, no cycle).
- **DEP-2 (AGT-01, ADR — the tool-schema contract).** The concrete **tool-schema wire contract**: which
  JSON-schema draft, the `ParamSchema` → JSON-schema type-name mapping, how `allow_extra` /
  `requires_seed` project, and how a provider tool-call's `arguments` map back onto a `macro.Op`'s
  `params`/`seed`. Must be a faithful projection that never widens what `dispatch` accepts
  (REQ-P14-LOGIC-002/-003).
- **DEP-3 (AGT-01, ADR — reversibility classification).** The concrete **reversibility-classification
  mechanism** for the tiered gate (REQ-P14-LOGIC-004): an explicit destructive-op set, a per-op
  reversibility flag on registration, or an undo-cost heuristic over the shipped `GroupCommand`. Must be
  deterministic + unit-testable + logic-level (never prompt-based).
- **DEP-4 (AGT-01/AGT-09, packaging).** The `assistant_live` optional extra + `assistant_live` pytest
  marker (deselected in CI) + the `pixelart-assistant` `[project.scripts]` entry point — mirroring the
  shipped `cloud_live` extra/marker and `pixelart-run` entry (REQ-P14-DATA-003/-008). AGT-09 wires the
  CI marker deselection.
- **DEP-5 (AGT-10, responsiveness HOW).** Whether the model round-trip runs on a worker thread/executor
  to satisfy REQ-P14-UI-004. It is **batch/off the per-frame loop** (not `FRAME_BUDGET_MS`-gated), so
  this is a responsiveness-not-frame-budget assessment.

## 9. Acceptance & traceability

- **Acceptance scenarios (Gherkin):** `specs/phase-14-ai-assistant/acceptance.md` — one-or-more scenarios
  per REQ, including the six mandated security/agentic invariants (tiered-safety boundary, whitelist
  enforcement + document-byte-unchanged, prompt-injection resistance, credential-gating / fake-adapter-in-
  CI, model-agnostic parity via the fake adapter, and the zero-`eval`/`exec` source audit).
- **Traceability matrix:** `specs/phase-14-ai-assistant/traceability.md` — REQ ↔ dossier/article/inherited
  primitive ↔ spec § ↔ Gherkin scenario ↔ expected test id.

## 10. Clarifications

### 10.1 FROZEN product-direction decisions (encoded above — NO open clarifications)

All product-direction decisions for this phase were **adjudicated by the user before AGT-02 began** and
are encoded as requirements above; `sdd-clarify` found **NO unresolved product-direction ambiguity**
(A2-D2 gate: nothing to suspend on). For the record:

| ID | Decision (FROZEN) | Encoded in |
| --- | --- | --- |
| D1 | **Action surface = REUSE the shipped Phase-8 safe DSL/registry.** LLM tool-calls map 1:1 onto allow-listed DSL ops via the existing trusted `dispatch()`; zero new interpreter, zero `eval`/`exec` (Article VII by construction), everything undo-backed. A tool-schema/introspection facade exposes each registered op as a JSON-schema tool. | REQ-P14-LOGIC-001/-002/-003/-005/-008 |
| D2 | **Embedding = BOTH** an in-app PySide6 chat DOCK (`ui/`) **and** a headless `pixelart-assistant` CLI (`data/`, Qt-free, mirrors `pixelart-run`). | REQ-P14-UI-001, REQ-P14-DATA-008 |
| D3 | **Safety posture = TIERED:** reversible/undo-backed → auto-run; destructive/hard-to-undo → explicit user confirmation. Enforced at the logic level, leveraging the undo stack to classify reversibility (not prompt-based). | REQ-P14-LOGIC-004, REQ-P14-UI-003 |
| D4 | **Provider integration = a model-agnostic LLM port** with a stdlib-only (`urllib`) OpenAI-compatible client (OpenAI / Gemini compat / Ollama / local llama.cpp) **plus** a thin native-Anthropic/Claude translator; NO new hard dependency; user configures an arbitrary endpoint + key. | REQ-P14-DATA-001/-004/-005/-006/-007 |
| D5 | **Credential gating = mirror the shipped Phase-10 `cloud_live` pattern:** an `assistant_live` optional extra + OS-keyring token storage + an `assistant_live` pytest marker deselected in CI; a deterministic FAKE adapter used in all CI tests (no real key/network). Keys never in `.pixproj`/logs. | REQ-P14-DATA-002/-003/-006 |

### 10.2 Security invariants (from Researcher `ad2616c7` + constitution) — encoded, not open

- **Article VII by construction** — no `eval`/`exec`/arbitrary code; the action surface **is** the
  allow-listed registry; security is **registry/permission enforcement, not the prompt** →
  REQ-P14-LOGIC-003/-004/-008.
- **Tool RESULTS fed back into the loop are UNTRUSTED input** (prompt-injection defence: results cannot
  escalate privileges or invoke non-whitelisted ops; bound sizes/counts, reuse `cloud_validation`-style
  caps) → REQ-P14-LOGIC-006.
- **Article I three-layer** — logic/data Qt-free; the LLM port + adapters live in `data/llm/` mirroring
  `data/cloud/`; the chat dock in `ui/` → REQ-P14-DATA-001/-007, REQ-P14-UI-001.
- **Article II** — named constants for any caps → REQ-P14-LOGIC-007.
