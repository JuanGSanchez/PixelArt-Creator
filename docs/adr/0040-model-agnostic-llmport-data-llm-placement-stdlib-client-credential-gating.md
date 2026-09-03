# ADR-0040 — Model-agnostic `LLMPort` ABC, `data/llm/` placement, the logic-side Protocol bridge, stdlib-urllib client + Anthropic translator, and credential gating (DEP-1/DEP-4)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-08 |
| Author | Architecture |
| Feature | `phase-14-ai-assistant` (Slices 14B, 14D) |
| Privacy | **S19-PRIVATE — docs/ is gitignored; this ADR is NOT committed.** |
| Relates to | ADR-0026 (cloud-port design — the mirrored precedent), ADR-0027/0035 (out-of-three-layer packages — the *contrast*), ADR-0039/0041/0042 |

## Context

Phase 14 must reach any external LLM behind **one** provider-neutral interface (spec D4;
REQ-P14-DATA-001/-004/-005/-007), be **credential-optional** (fake adapter in CI, real path
credential-gated/out-of-CI — D5; REQ-P14-DATA-002/-003/-006), and add **no new hard runtime dependency**
(S8). Prior research (`ad2616c7`) grounds: (R1.1–R1.5) OpenAI `/v1/chat/completions` "tools" is the
de-facto agnostic wire covering OpenAI + Gemini's OpenAI-compat endpoint + Ollama + llama.cpp; Anthropic is
the sole structural non-conformer (a thin translator or gateway); (R4.1) a **stdlib-`urllib`
OpenAI-compatible client incl. SSE is feasible with zero new hard dependency**; (R3.1–R3.4) MCP / vendor
agent SDKs solve a *different* problem and add real dependency trees + churn — the **thin in-process
adapter** is the minimal, lowest-attack-surface fit; (R4.3/R6.1) mirror the Phase-10 `cloud_live`
optional-extra + OS-keyring pattern.

Spec §8 DEP-1 defers to architecture: the exact placement of the port + adapters + CLI, and confirmation that it
stays within the three-layer model. This ADR rules placement, the layering bridge that lets a `logic/`
loop use a `data/` port **without a forbidden `logic → data` edge**, the two real adapters, and the
credential-gating scaffolding.

## Decision

### 1. `data/llm/` — a normal `data/` subpackage, NOT a new top-level package (DEP-1)

The LLM port + adapters live in a new `pixelart_creator/data/llm/` subpackage, mirroring `data/cloud/`:

| Module | Responsibility |
| --- | --- |
| `data/llm/port.py` | The one `LLMPort` ABC + the port's own `LLMError` family + a provider-agnostic `is_configured()` notion + normalized adapter-facing helpers. Zero Qt. |
| `data/llm/fake_adapter.py` | Deterministic, scripted `LLMPort` — no network, no key (14B). Zero Qt. |
| `data/llm/openai_compatible.py` | Real stdlib-`urllib` OpenAI-compatible client (14D). Zero Qt. |
| `data/llm/anthropic_translator.py` | Real stdlib-`urllib` native-Anthropic translator (14D). Zero Qt. |
| `data/llm/token_store.py` | Lazy/optional OS-keyring token isolation (14B scaffold; 14D live). Zero Qt. |

**Why a `data/` subpackage and NOT a new top-level package** (the explicit DEP-1 confirmation). The
Phase-10 `sync_backend/` (ADR-0027) and Phase-13 `web_viewer/` (ADR-0035) became first-class top-level
packages **outside** the three layers *because they are out-of-process deployables* — a separate service
and a separate web client that must not import Qt and that reach the app **over the wire at runtime, never
by Python import**, and are excluded from the desktop wheel. `data/llm/` is the **opposite**: it is pure
in-process Python that IS part of the desktop distributable and is imported directly, exactly like
`data/cloud/`. It is therefore governed by the **existing `data` rule** in `check_layering.py` (zero Qt,
no `ui/` import, no `sync_backend`/`web_viewer` import) — **no new `check_layering` rule, no new top-level
package, no `pyproject` `exclude` entry** is required. (It IS a `data/` module, so it ships in the wheel;
correct — the assistant is an in-app feature.)

### 2. The layering bridge — a `logic/`-side `ChatBackend` Protocol + dependency injection (DEP-1, CENTRAL)

The agentic loop lives in `logic/` (14C, ADR-0041) but must call the port. `logic/` **must not import
`data/`** (Article I). Resolution — the established `macro.set_dispatcher` / `blend.CompositeNode` /
`animation` structural-injection precedent:

- **`logic/assistant.py` defines the abstraction the loop needs** as a PEP 544 **`ChatBackend` Protocol**
  (structural), plus the normalized, pure-`logic` value types it exchanges: `Message`, `Role`,
  `Conversation`, `ToolCall` (re-exported from `tool_catalog`), and `AssistantReply` (either a final
  assistant `Message` or one-or-more `ToolCall`s). The loop is typed **against `ChatBackend`** and receives
  the backend by **dependency injection** (constructor/parameter).
- **`data/llm/port.py` defines `LLMPort(ABC)`** — the base every concrete adapter subclasses. Its one core
  verb, `respond(conversation: Conversation, tools: Sequence[ToolDescriptor]) -> AssistantReply`,
  **structurally satisfies `ChatBackend`**. `port.py` imports the value types from `logic/` (a
  `data → logic` edge, **allowed**); `logic/` never imports `data/llm/` (**no edge, no cycle**). The
  caller — `ui/` (14E) or `data/assistant_cli.py` (14F) — constructs the concrete adapter and injects it.

Net: the shared vocabulary is single-sourced in `logic/` (data may import logic), the loop depends only on
a `logic/` Protocol, and the concrete adapter is injected. `check_layering`/`check_cycles` stay exit 0
(§proof in plan §11). This is the single most important structural ruling of Phase 14.

### 3. `LLMPort` — one provider-neutral verb set; no provider/HTTP/credential leak (REQ-P14-DATA-001/-007)

`respond(conversation, tools) -> AssistantReply` is the bounded core: given an ordered `Conversation` +
the available `ToolDescriptor`s, return either a final assistant `Message` or one-or-more `ToolCall`s. The
signatures name **no** provider, and carry **no** provider SDK type, HTTP/`urllib` type, or credential type
(mirrors `CloudPort`, REQ-P14-DATA-007). A provider-agnostic `is_configured() -> bool` reports
configured/not-configured (default `False`; `ui/` never sees a key — the `CloudPort.is_connected`
precedent). Adding a provider = adding an adapter; nothing above the port changes (Article XI).

### 4. Adapters: fake in CI; real stdlib-urllib OpenAI-compatible + Anthropic translator out-of-CI

- **`fake_adapter.py` (14B)** — a deterministic `LLMPort` fed a **scripted response program** (ordered
  replies incl. scripted tool-calls — reversible and destructive, scripted malicious tool-result
  follow-ups, scripted multi-step sequences, and both OpenAI-shaped and Anthropic-shaped emulation for the
  model-agnostic parity test). No network, no key. It is the **credential-optional guarantee**: the whole
  agentic contract (loop, tiered safety, whitelist, injection defence, model-agnostic parity) is exercised
  headlessly in CI (REQ-P14-DATA-002; SC-D002-1, SC-D005-1). The `FakeCloudAdapter` precedent.
- **`openai_compatible.py` (14D)** — a real adapter, **stdlib-`urllib` only** (POST JSON to
  `<endpoint>/v1/chat/completions`; accumulate the response; parse `choices[].message.tool_calls[]` →
  `ToolCall`, `.arguments` JSON-string parsed defensively). Covers OpenAI, Gemini OpenAI-compat, Ollama,
  llama.cpp, most third parties (R1.1–R1.3, R1.5). **No new hard runtime dependency** (REQ-P14-DATA-004;
  SC-D004-1). Wraps `ToolDescriptor.parameters` as `{"type":"function","function":{...}}` (ADR-0039 §7).
- **`anthropic_translator.py` (14D)** — a thin real adapter mapping the port's neutral conversation + tools
  onto native Anthropic Messages/`tool_use`/`tool_result` and back (`input_schema` not `parameters`,
  `x-api-key` + `anthropic-version`, `tool_result` blocks results-first — R1.4). Also stdlib-`urllib`.
  Proves genuine model-agnosticism (REQ-P14-DATA-005). Streaming/SSE, retries, and timeout
  (`ASSISTANT_REQUEST_TIMEOUT_S`) are hand-rolled per R4.1's caveats; sentinel-variance tolerated (R1.3).
- The two real adapters are **credential-gated / OUT of the CI gate** (`assistant_live` extra + marker,
  §5). Live tests (`SC-D004-2`, `SC-D005-2`) carry `@pytest.mark.assistant_live`, deselected in CI. A
  missing key/endpoint degrades to a clear "not configured" state, never a crash (REQ-P14-DATA-006;
  SC-D006-2).

### 5. Credential gating — mirror `cloud_live` exactly (DEP-4; REQ-P14-DATA-003/-006)

- **`pyproject` optional extra** `assistant_live = ["keyring==25.7.0"]` (same pin as `cloud_live`; the
  stdlib-urllib client needs no HTTP dep, so keyring is the only live dep). NOT a core dep — CI installs
  base + `.[dev]` and never needs it. **DevOps owns the edit.**
- **`data/llm/token_store.py`** — modelled on `data/cloud/token_store.py`: `keyring` imported **lazily,
  inside the functions**, so all of 14A–14C + the fake adapter import and run **without `keyring`
  installed** (SC-D003-2). Service-name template `pixelart-creator:assistant:{provider}`; per-provider
  keying; `is_keyring_available()` for graceful degrade. Keys are acquired/stored/used **entirely inside
  `data/llm/`** — never in `logic/`/`ui/`, never in a `.pixproj` or a log, never committed (Article VII §3;
  REQ-P14-DATA-006, SC-D006-1). `mypy` `ignore_missing_imports` already covers `keyring.*` (pyproject).
- **`pytest` marker** `assistant_live` registered in `[tool.pytest.ini_options].markers` and **deselected
  in the CI gate** (DevOps extends the ci.yml `-m "not …"` expression with `and not assistant_live`).

## Alternatives Considered

- **Put the `LLMPort` ABC in `logic/` (loop imports it directly; adapters in `data/` implement it).**
  Rejected: the spec (REQ-P14-DATA-001, DEP-1) mandates the ABC in `data/llm/` mirroring `data/cloud/`, and
  provider/transport concerns belong in `data/`. The `ChatBackend` Protocol (§2) is the clean bridge that
  keeps the ABC in `data/` while letting the `logic/` loop stay `data/`-free.
- **A new top-level `assistant/` package (à la `sync_backend`/`web_viewer`).** Rejected: those are
  out-of-process, wire-reached, wheel-excluded deployables; `data/llm/` is in-process, imported, shipped —
  a `data/` subpackage (DEP-1 §1).
- **MCP host/client, or a vendor agent SDK (OpenAI Agents / LangChain), or LiteLLM as the core.** Rejected
  (R3.1–R3.4, R4.2): MCP solves cross-host interop the single in-app host does not need and pulls
  `anyio`/`pydantic`/`websockets`/`pywin32`; vendor SDKs add lock-in + weight; LiteLLM is MIT but a
  substantial dep tree — all violate the no-new-hard-dep bar. Stdlib-urllib + a thin Anthropic translator
  is the grounded minimal fit. (LiteLLM/any-llm remain the documented fallback if hand-maintaining
  cross-provider adapters becomes untenable — a future ADR, not now.)
- **Reuse the `cloud_live` extra/marker for the assistant.** Rejected: a distinct `assistant_live`
  extra/marker keeps the two credential surfaces independently installable/deselectable (spec D5 names
  `assistant_live` explicitly).

## Consequences

**Positive.** One Qt-free port; providers are swappable (Article XI); the whole contract is
deterministically CI-testable via the fake adapter with no key/network; the loop stays `logic/`-pure via
the Protocol bridge; keys are OS-managed and isolated in `data/llm/`; **zero new hard runtime dependency**
(only the optional `keyring`, already used by `cloud_live`). `check_layering`/`check_cycles` stay 0 with
**no rule change**.

**Negative / risk.** Hand-rolled `urllib` transport must implement retries/timeouts/chunk-reassembly/SSE
sentinel-variance that a library would provide (R4.1 caveats) — carried by the 14D adapters and their
out-of-CI live tests; the fake adapter fixes the in-CI contract so this drift is out-of-gate. Cross-provider
tool-call normalization (OpenAI `tool_calls` vs Anthropic `tool_use`/`tool_result`, argument-fragment
streaming, parallel calls) is genuine specialist competence (research bottom-line (b)) — flagged as a
candidate for a possible dedicated 14D adapter specialist/skill (plan §12).

## Grounding

- Spec §2 (14B/14D), §4 REQ-P14-DATA-001/-002/-003/-004/-005/-006/-007, §7, §8 DEP-1/DEP-4, §10.1 D4/D5;
  `acceptance.md` SC-D001-1, SC-D002-1, SC-D003-1/-2, SC-D004-1/-2, SC-D005-1/-2, SC-D006-1/-2, SC-D007-1.
- Shipped `data/cloud/port.py` + `token_store.py` + `fake_adapter.py` (the mirrored precedent);
  `pyproject.toml` `cloud_live` extra + `cloud_live` marker.
- Research note `ad2616c7` R1.1–R1.5, R3.1–R3.4, R4.1–R4.3, R6.1–R6.3 + bottom-line (a)/(b).
- Constitution Article I (three-layer + injection bridge precedent), IV (fake→CI), VII (no secrets), XI.
  ADR-0026 (cloud port), ADR-0027/0035 (out-of-three-layer packages — the contrast).
