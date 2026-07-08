---
name: llm-adapter-normalization
description: >
  Cross-provider LLM wire-normalization skill for the PixelArt Creator platform.
  Use it (invoked by AGT-03 Python Dev) to implement a real provider adapter
  BEHIND the shipped model-agnostic `data/llm/port.py` `LLMPort` (Phase-14 Slice
  14D): one stdlib-`urllib` OpenAI-compatible `POST /v1/chat/completions` "tools"
  client (covers OpenAI, Gemini's compat endpoint, Ollama, local llama.cpp) plus a
  thin native-Anthropic translator (`tool_use`/`tool_result`, `input_schema`,
  `x-api-key`), each mapping ONLY — never executing — to/from the neutral
  `logic/assistant.py` value types (`Role`/`Message`/`Conversation`/`AssistantReply`,
  `ToolDescriptor`/`ToolCall`). Credential-gated via `token_store`, behind the
  `assistant_live` extra, out of CI. STDLIB-ONLY — no new hard dependency, no
  provider SDK, no `eval`/`exec`, no action execution (Article VII, ADR-0040).
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity (workflow required)
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P9 — Role Separation (declares OUT-OF-SCOPE)
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
    # P5 inherits AGT-03's context discipline; P10 inherits AGT-03's exit status.
  custom:
    - id: C1
      name: stdlib-only, no new hard dependency
      requires: The adapter POSTs + streams over Python's `urllib.request` + `json` + `ssl` ONLY; no provider SDK (`openai`/`anthropic`/`google-genai`), no MCP/agent-SDK/LiteLLM, no new hard dependency. The only live dep is the optional `keyring` behind the `assistant_live` extra (lazy in `token_store`).
      rationale: ADR-0040 (stdlib-`urllib` adapters, no new hard dep, mirrors `cloud_live`); Researcher ad2616c7 R4.1 (stdlib SSE feasible in a few dozen lines) / R3.1–R3.4 (MCP/SDK add a real dependency tree) / R6.3 (packaging).
    - id: C2
      name: maps only — never executes (Article VII)
      requires: The adapter is a pure request/response translator between the neutral `logic` value types and each provider wire. It performs NO action execution, contains NO `eval`/`exec`/`compile`/`__import__`, and treats every provider payload + tool result as untrusted data. Execution stays in the 14C `run_turn` loop through the trusted `execute_tool_call` dispatch.
      rationale: `data/llm/port.py` + `logic/assistant.py` docstrings (Article VII — a tool result is data, never a privilege); ADR-0040 §2/§3; Researcher ad2616c7 R5.1 (action-selector) / R5.2 (tool results are untrusted, prompt-injection is OWASP #1).
---

SKILL: llm-adapter-normalization
================================================================================

PURPOSE:
  Give AGT-03 the reusable, grounded pattern for the ONE genuine specialist task in
  Slice 14D — normalizing the cross-provider function-calling wire — so a concrete
  `LLMPort` adapter maps every request/response between the shipped neutral
  `logic/assistant.py` vocabulary and a provider's HTTP shape without any new
  dependency, any provider SDK, or any execution path. One OpenAI-compatible
  stdlib-`urllib` core covers OpenAI + Gemini's compat endpoint + Ollama + llama.cpp;
  a thin translator covers native Anthropic; both satisfy the same `respond` contract.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given the shipped `port.py`/`assistant.py`/`tool_catalog.py`/`token_store.py`
  seams + a provider endpoint/key, it produces a mapping-only adapter unaided; the
  two wire shapes + the neutral-type map are specified in full below.

INPUTS:
  - The target provider family (OpenAI-compatible vs native-Anthropic) + its base
    endpoint URL (user-supplied at runtime, treated as untrusted; R4.3).
  - The shipped seams: `data/llm/port.py` (`LLMPort` ABC + `LLMError`/
    `LLMNotConfiguredError`/`LLMResponseError`), `logic/assistant.py` neutral types
    (`Role`, `Message`, `Conversation`, `AssistantReply` + `.final`/`.calling`),
    `logic/tool_catalog.py` (`ToolDescriptor`, `ToolCall`), `data/llm/token_store.py`
    (`load_token`), `logic/constants.py` (`ASSISTANT_REQUEST_TIMEOUT_S`,
    `MAX_TOOL_RESULT_BYTES`).

OUTPUTS:
  - A `pixelart_creator/data/llm/` adapter module (Qt-free) subclassing `LLMPort`:
    `respond(conversation, tools) -> AssistantReply` + `is_configured() -> bool`,
    implementing the outbound (neutral → wire) and inbound (wire → neutral) maps
    below, normalizing every failure into the `LLMError` family, credential-gated
    and deselected in CI. No new op, no execution, no provider/HTTP/credential type
    surfaced above the port (mirrors `CloudPort`; ADR-0040 §1/§3).

PRECONDITIONS:
  - Slices 14A–14C are on disk (the neutral types, `ChatBackend`, `run_turn`, and
    the `tool_catalog` projection are FROZEN); `port.py` + `token_store.py` exist.
  - Placement decided (a normal `data/llm/` module, DEP-1 — governed by the existing
    `check_layering` `data` rule; `data → logic` allowed, no `logic → data`, no Qt).

PROCEDURE:
  1. OpenAI-compatible CORE (R1.1/R1.3/R1.5; covers OpenAI, Gemini compat
     `.../v1beta/openai/`, Ollama, llama.cpp). `POST {endpoint}/v1/chat/completions`
     over `urllib.request` with body:
     `{"model", "messages":[…], "tools":[…], "tool_choice", "stream"}`.
     - `messages[]`: each `{role, content}`; an assistant tool-call turn carries
       `tool_calls[]`; a tool RESULT is a separate `{"role":"tool", "tool_call_id",
       "content"}` message (R1.1).
     - `tools[]`: one entry per `ToolDescriptor` as
       `{"type":"function","function":{"name","description","parameters":<the
       descriptor's JSON-schema>}}` (R2.2; the 14A projection is already JSON-schema).
     - Response (non-stream): parse `choices[0].message` — `.content` and/or
       `.tool_calls[]`, each `{id, type:"function", function:{name, arguments}}`
       where `arguments` is a JSON STRING to `json.loads` (R1.1).
  2. SSE STREAMING (R2.4/R4.1) — orthogonal to the loop: read the response line by
     line, strip the `data: ` prefix, `json.loads` each chunk, read
     `choices[0].delta`, and REASSEMBLE tool-call `function.arguments` string
     fragments keyed by `tool_calls[].index`/`id` before mapping; finalize on the
     `[DONE]` sentinel OR on stream close (tolerate sentinel variance — Ollama bug,
     R1.3). Bring up incrementally: plain text → streaming → tools (R2.1).
  3. ANTHROPIC TRANSLATOR (R1.4/R1.5) — the thin structural delta to native Anthropic
     (`POST {endpoint}/v1/messages`), ↔ the SAME neutral types:
     - Tool def: flat `{name, description, input_schema}` (NO `function` wrapper;
       `input_schema`, not `parameters`).
     - Model tool call: a content block `{"type":"tool_use","id","name","input"}`
       where `input` is an already-parsed object (no `json.loads`).
     - Result feedback: a `{"role":"user"}` message whose content array LEADS with
       `{"type":"tool_result","tool_use_id",…}` (tool_result blocks MUST come first,
       free text after).
     - Headers: `x-api-key` + `anthropic-version` (NOT `Authorization: Bearer`).
     - Streaming: typed SSE events (`message_start`/`content_block_delta`/…).
  4. NEUTRAL-TYPE MAPPING (bidirectional; the single load-bearing contract). Outbound
     `Conversation.messages` → `messages[]`: `Role.SYSTEM/USER/ASSISTANT` → the wire
     role literal (`Role` subclasses `str`); `Role.TOOL` → OpenAI `role:"tool"` +
     `Message.tool_call_id` / Anthropic `tool_result` block (results-first). Neutral
     `Sequence[ToolDescriptor]` → `tools[]` per the wire in step 1/3. Inbound → build
     an `AssistantReply`: a final message → `AssistantReply.final(content)`; requested
     tool-calls → `AssistantReply.calling(*calls, content=narration)`, each provider
     call mapped to a neutral `ToolCall(name=…, arguments=<dict>)` (OpenAI
     `function.name` + `json.loads(function.arguments)`; Anthropic `tool_use.name` +
     `.input`), preserving the provider id for `tool_call_id` pairing. `is_final` is
     `not tool_calls`. The 14C loop turns each `ToolCall` into a bounded `Role.TOOL`
     result message (via `bound_tool_result`, `MAX_TOOL_RESULT_BYTES`) that the NEXT
     `respond` maps back onto the wire — the adapter maps that inert data, never runs
     it (C2).
  5. CREDENTIAL + SAFETY. Pull the key via `token_store.load_token(provider, account)`
     inside the adapter; NEVER log it, never write it to a `.pixproj` (ADR-0040 §5).
     `is_configured()` returns `True` only when key + endpoint are present; a request
     without them raises `LLMNotConfiguredError` (credential-optional — degrade, don't
     crash). Hand-roll timeouts/bounded retries on `urllib` (`ASSISTANT_REQUEST_TIMEOUT_S`;
     `urllib` gives no pooling/retry niceties, R4.1). Validate the endpoint
     scheme/host, TLS-only (R4.3). Normalize EVERY transport/provider/parse failure
     into the `LLMError` family (step ERROR HANDLING). Test deterministically against
     the 14B `FakeLLMAdapter` and/or a recorded VCR-style cassette with
     `Authorization`/`x-api-key` REDACTED (R6.2); real network runs ONLY under the
     `assistant_live` marker/extra, deselected in CI — no live key in the gate (R6.1).

DECISION POINTS:
  - Decision LA-D1:
    Condition: the target provider serves native Anthropic (no `/v1/chat/completions`).
    Branch A: use the Anthropic translator (step 3) — `tool_use`/`tool_result`,
      `input_schema`, `x-api-key`, typed SSE (R1.4).
    Branch B: use the OpenAI-compatible core (step 1) — covers OpenAI, Gemini compat,
      Ollama, llama.cpp, most third parties (R1.2/R1.3/R1.5).
    Default: B unless the provider/endpoint is declared Anthropic-native (R1.5 — one
      core covers 3 of the 4 named families; Anthropic is the sole structural
      non-conformer). Both branches map to the identical neutral types (step 4).
  - Decision LA-D2:
    Condition: the caller/endpoint requests an SSE `stream`.
    Branch A: stream — parse `data:` lines / typed events, reassemble tool-call
      argument fragments by index/id, then map the assembled message (step 2).
    Branch B: non-stream — map the single JSON body (`choices[0].message` / the
      Anthropic content blocks).
    Default: B (simplest; streaming is orthogonal — accumulate, then run the same map).
  - Decision LA-D3:
    Condition: one turn returns more than one `tool_calls` / `tool_use` block (parallel).
    Branch A: map ALL of them into `AssistantReply.tool_calls` (a tuple); the 14C loop
      gates + dispatches each and feeds one `Role.TOOL` result per call (R2.3).
    Default: A (handle both single and batched; the `MAX_TOOL_CALLS_PER_TURN` cap is
      the loop's, not the adapter's).

ERROR HANDLING:
  - Error LA-E1: missing key/endpoint → `is_configured()` returns `False`; a `respond`
    attempt raises `LLMNotConfiguredError` — never a crash (credential-optional,
    ADR-0040 §5 / `port.py`).
  - Error LA-E2: non-2xx, malformed/oversized/unparseable payload, or transport error
    → normalize to `LLMResponseError`; NEVER leak a raw `urllib.HTTPError`/`URLError`/
    `json.JSONDecodeError` above the port (the untrusted-response boundary, `port.py`).
  - Error LA-E3: SSE terminator variance (Ollama `[DONE]` interop bug, R1.3) → tolerate
    a missing/variant sentinel; finalize the reassembled message on stream close.
  - Error LA-E4: timeout / transient network → bounded hand-rolled retry within
    `ASSISTANT_REQUEST_TIMEOUT_S`; on exhaustion raise `LLMResponseError` (R4.1 caveat).

DEPENDENCIES:
  - Python stdlib ONLY: `urllib.request`, `json`, `ssl` (C1 — no new hard dep, R4.1).
  - `data/llm/port.py`: `LLMPort` (implement `respond`/`is_configured`) + the
    `LLMError` family to raise. `logic/assistant.py`: `Role`/`Message`/`Conversation`/
    `AssistantReply` (map to/from). `logic/tool_catalog.py`: `ToolDescriptor` (→
    `tools[]`) + `ToolCall` (← model calls). `data/llm/token_store.py`: `load_token`.
    `logic/constants.py`: `ASSISTANT_REQUEST_TIMEOUT_S`, `MAX_TOOL_RESULT_BYTES`.
  - Optional `keyring` behind the `assistant_live` extra (lazy in `token_store`; the
    extra/marker/`pixelart-assistant` script are AGT-09's `pyproject` edits).
  - Fallback: not configured → `is_configured()` `False`, feature degrades gracefully.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - The `LLMPort` ABC + `LLMError` family themselves → shipped 14B `port.py`; this
    skill implements adapters BEHIND it. The deterministic `FakeLLMAdapter` → 14B.
  - The tool catalog / `ParamSchema`→JSON-schema projection / `ToolCall`→`Op` dispatch
    → 14A `tool_catalog.py` (the adapter consumes `ToolDescriptor`/`ToolCall`, never
    re-derives them).
  - The agentic loop, turn/message bounds, tiered `classify_op` confirm gate, and
    tool-result bounding → 14C `assistant.py` (`run_turn`/`AssistantSession`/
    `bound_tool_result`). ACTION EXECUTION → the trusted `execute_tool_call` dispatch
    ONLY (Article VII). The adapter maps; it never runs an op (C2).
  - No `eval`/`exec`/`compile`/`__import__`; no provider SDK; no MCP/agent-SDK/LiteLLM
    new hard dependency (R3.1–R3.4/R4.2).
  - UI provider-config dialog / not-configured degrade surface → 14E `ui/`. Headless
    `pixelart-assistant` CLI → 14F `assistant_cli.py`. `pyproject` extra/marker/CI
    deselection → AGT-09.

SOURCES:
  - User requirements: Phase-14 spec REQ-P14-DATA-004/-005/-006/-007 (14D real
    OpenAI-compatible + Anthropic adapters, credential-gating, provider-agnostic port);
    STRUCTURE.md §`data/llm/` (14D module map); the standing `generate-assets-on-demand`
    memory (fill a genuine specialist gap with a right-sized asset).
  - Official docs (via The Researcher, P1): report
    `docs/subagent-report-the-researcher-ad2616c7-20260707T220150.md` — R1
    (OpenAI-compatible wire + Gemini/Ollama/llama.cpp coverage + the four Anthropic
    deltas), R2 (tool-call loop, JSON-schema tools, parallel calls, streaming
    reassembly), R3 (thin in-process adapter vs MCP/SDK), R4 (stdlib-`urllib`
    feasibility + credential handling), R5 (action-selector, untrusted tool results,
    Article VII), R6 (fake adapter + VCR redaction + optional-extra/CI isolation);
    the OpenAI/Gemini/Ollama/Anthropic wire docs cited therein.
  - Inner assets: ADR-0040 §1/§2/§3/§5 (the one model-agnostic `LLMPort`, the
    `ChatBackend` layering bridge + DI, the `AssistantReply` reply contract, keyring
    credential-gating) as implemented + quoted in the shipped `data/llm/port.py`,
    `logic/assistant.py`, `data/llm/token_store.py`, and `logic/tool_catalog.py`;
    asset-templates.md §Skill; principles.md §3 (skill row).
