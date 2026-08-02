# ADR-0039 — Assistant action-surface = the shipped safe DSL registry + the tool-schema facade contract (DEP-2)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-08 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-14-ai-assistant` (Slice 14A) |
| Privacy | **S19-PRIVATE — docs/ is gitignored; this ADR is NOT committed.** |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0021/0022 (Phase-8 automation security model + DSL/dispatch), ADR-0040/0041/0042 (Phase-14) |

## Context

Phase 14 adds an in-app, model-agnostic AI assistant that must **drive the user's workflow through the
shipped, allow-listed, `eval`/`exec`-free action surface** (spec D1; REQ-P14-LOGIC-001/-002/-003). The
shipped Phase-8 `logic/scripting.py` is that surface: a `_REGISTRY` of trusted `(factory, ParamSchema)`
pairs, `registered_ops()`/`is_registered()` introspection, and the single trusted
`dispatch(document, ops)` that validates each `macro.Op` name against the allow-list and its params
against the op's `ParamSchema`, applies the run as one already-applied reversible `history.GroupCommand`,
and rolls back atomically on failure. There is **no interpreter to escape** (ADR-0021/0022, Article VII by
construction).

The spec froze the WHAT and deferred the HOW to AGT-01 (spec §8 DEP-2): the concrete **tool-schema wire
contract** — which JSON-schema shape, the `ParamSchema` → JSON-schema type mapping, how `allow_extra` /
`requires_seed` project, and how a provider tool-call's `arguments` map back onto a `macro.Op` — **without
widening `dispatch` or bypassing the allow-list**. The Researcher (`ad2616c7` R2.5, R5.1) confirms the
shipped registry is, by construction, the peer-reviewed **action-selector pattern**: the model is "an
LLM-modulated switch statement" that only *selects* a registered op and *fills typed args*; the registry
executes. This ADR freezes that contract so the loop (14C), the adapters (14B/14D), and their tests bind
to one stable projection.

## Decision

### 1. Placement — a read-only introspection facade in `logic/` (14A)

`pixelart_creator/logic/tool_catalog.py` (NEW, zero Qt) is the tool-catalog facade. It imports only
`scripting`, `macro`, and `constants` (a pure `logic` leaf; `check_layering`/`check_cycles` stay 0). It is
**read-only over the registry**: it introduces **no** new executable op and **no** new registration path.
An op is a tool **iff** `scripting.is_registered(name)` — so the catalog automatically tracks built-ins
**and** consent-gated, namespaced plugin ops (`"<plugin>.<op>"`, PLG-1) with no second list to drift
(REQ-P14-LOGIC-001; SC-L001-1/-2).

### 2. The provider-neutral tool descriptor (frozen value type)

`ToolDescriptor(name: str, description: str, parameters: Mapping[str, object])` — `parameters` is a
JSON-schema **object** dict. `build_tool_catalog() -> tuple[ToolDescriptor, ...]` enumerates
`scripting.registered_ops()` and derives one descriptor per op. `description` is a stable, human-readable
string (the model reads it as the contract — Researcher R2.2); AGT-03 sources it from a module-local
per-op description table (module-local vocabulary, ADR-0001/BF-2) — **not** `logic/constants.py` (it is
not a numeric).

### 3. `ParamSchema` → JSON-schema projection (FROZEN)

The schema is a **faithful projection** of the shipped `ParamSchema` — it **never permits arguments that
`ParamSchema.validate` would reject** (REQ-P14-LOGIC-002; SC-L002-1). Rules:

- **Wire dialect:** a **provider-neutral JSON-Schema subset** (compatible with both draft-07 and 2020-12,
  the function-calling lowest common denominator). **No `$schema` key** is emitted (providers reject/ignore
  it). Only these keywords appear: `type`, `properties`, `required`, `additionalProperties`, and per-property
  `type` + `description`. The adapters (14D) wrap this dict per provider (§7 below); the dict itself is
  identical across providers.
- **Object envelope:** every tool's `parameters` is `{"type": "object", "properties": {...},
  "required": [...], "additionalProperties": <bool>}`.
- **`fields` → `properties` type mapping** (Python type → JSON-schema `type`):
  `str`→`"string"`, `int`→`"integer"`, `float`→`"number"`, `bool`→`"boolean"`, `list`→`"array"`,
  `dict`→`"object"`, `type(None)`→`"null"`. A **tuple of accepted types** projects to a JSON-schema type
  **array** (union), e.g. `(int, float)`→`{"type": ["integer", "number"]}`. (JSON-schema `"integer"`
  excludes booleans, matching `ParamSchema`'s explicit `bad_bool` rejection — faithful.)
- **`required` → `required`:** the op's `ParamSchema.required` tuple, verbatim.
- **`allow_extra` → `additionalProperties`:** `additionalProperties = ParamSchema.allow_extra`. When
  `allow_extra` is `True` (e.g. `procgen`'s algorithm-specific knobs), `additionalProperties: true`; when
  `False`, `additionalProperties: false` (strict — the preferred, adherence-improving posture, Researcher
  R2.2). Extra values remain JSON by construction, so the `_is_json_native` guard in `validate` is
  automatically satisfied.
- **`requires_seed` → an explicit `seed` property.** `seed` is a **sibling of `params`** on `macro.Op`,
  not a param field. The projection therefore adds `properties["seed"] = {"type": "integer",
  "description": ...}`; `seed` is added to `required` **iff** `ParamSchema.requires_seed` is `True`. (Even
  when `allow_extra` is `True`, `seed` is declared explicitly so it is typed and documented, and is always
  routed to `Op.seed` on the way back — §4.)

### 4. Tool-call → `macro.Op` mapping through the trusted `dispatch` (FROZEN)

An incoming, provider-normalized tool-call is the logic value type
`ToolCall(name: str, arguments: Mapping[str, object])` (produced by the adapter, §7). `to_op(call)` maps
it deterministically:

```
seed   = arguments.get("seed")             # peeled off, whatever allow_extra is
params = {k: v for k, v in arguments.items() if k != "seed"}
op     = macro.Op(name=call.name, params=params, seed=seed)
```

Execution is **only** `scripting.dispatch(document, [op])` — the single validated path. The JSON-schema is
**advisory to the model**; `dispatch` + `ParamSchema.validate` are the **authoritative enforcement**. A
tool-call naming a non-registered op, or with invalid/extra/mistyped params, raises `ScriptError` in
dispatch's up-front validate phase, and the document is left **byte/state-identical** (the shipped
Phase-1-validate-then-apply atomicity) — REQ-P14-LOGIC-003, SC-L003-1/-2. A valid call applies as one
reversible `GroupCommand` (SC-L003-3). **The LLM has no path to any op outside `_REGISTRY`**, because the
enforcement lives in `logic/`, not in the projection or the prompt.

### 5. Faithful-projection guarantee (the non-widening invariant)

For every op, `{arguments the projected schema permits}` ⊆ `{arguments ParamSchema.validate accepts}`
(after `seed` routing). This holds because every schema keyword is *derived from the same `ParamSchema`*:
types mirror `fields`, `required` mirrors `required` (+ `seed` iff `requires_seed`), `additionalProperties`
mirrors `allow_extra`. The projection is never looser than `validate`; where it is *stricter*
(`additionalProperties: false`) that only helps the model, and `dispatch` remains the final arbiter. AGT-04
asserts this directly (SC-L002-1: "the schema never permits arguments the shipped `ParamSchema.validate`
would reject").

### 6. What this ADR does NOT do

No new *executable* DSL op; no new `register_command` back-door; **no change to the frozen
`scripting.register_command`/`dispatch`/`ParamSchema` signatures** (widening them would re-author the
Phase-8 security surface — spec §6 non-goal). The facade is pure introspection + a data mapping.

### 7. Cross-provider wrapping (delegated to the adapters, ADR-0040)

The adapters wrap the *identical* `ToolDescriptor.parameters` dict per provider and normalize the model's
tool-call back to `ToolCall`:
- OpenAI-compatible: `{"type":"function","function":{"name","description","parameters":<dict>}}`; model
  returns `tool_calls[].function.arguments` (a JSON **string** the adapter parses) + `.id`.
- Anthropic native: `{"name","description","input_schema":<dict>}`; model returns a `tool_use` content
  block `{"id","name","input"}` (`input` already an object).
Both normalize to the same `ToolCall(name, arguments)`; the loop and catalog are provider-agnostic.

## Alternatives Considered

- **Widen `register_command` to carry a JSON-schema / description.** Rejected: re-authors the frozen
  Phase-8 surface (spec §6), and the `ParamSchema` already carries everything the projection needs.
- **Let the model emit a full `macro.Macro` / multi-op list per tool-call.** Rejected: one tool-call = one
  `Op` keeps the action-selector shape (R5.1) and the tiered gate (ADR-0041) per-action; multi-op batches
  remain expressible as multiple tool-calls in one turn (bounded by `MAX_TOOL_CALLS_PER_TURN`).
- **Emit JSON-Schema with `$schema`/draft-2020-12-only vocabulary (`prefixItems`, `$defs`).** Rejected:
  reduces provider portability; the flat subset covers every `ParamSchema` shape faithfully.
- **Trust the projected schema as the enforcement boundary (skip re-validation in dispatch).** Rejected
  (Article VII / R5.3): the model can ignore the schema; `dispatch` + `ParamSchema.validate` must stay the
  sole authority.

## Consequences

**Positive.** The assistant's entire ability to act is bounded by `_REGISTRY` — Article VII by
construction, inheriting ADR-0021/0022. Built-ins and plugin ops are exposed automatically with no drift.
The contract is one stable dict shape both adapter families wrap, and one deterministic `to_op` mapping,
so 14C/14D/tests bind to a frozen surface. Zero new op, zero `eval`/`exec`.

**Negative / risk.** The projection must be re-checked if a future `ParamSchema` gains a new field kind
(e.g. nested typed objects) — mitigated by the faithful-projection test (SC-L002-1) which fails loudly if
the schema ever out-permits `validate`. Rich constraints a model could use (enums, min/max) are not
projected in v1 (the shipped `ParamSchema` does not carry them); adding them later is an additive
projection change, not a contract break.

## Grounding

- Spec `specs/phase-14-ai-assistant/spec.md` §2 (14A), §4 REQ-P14-LOGIC-001/-002/-003, §8 DEP-2, §10.1 D1;
  `acceptance.md` SC-L001-1/-2, SC-L002-1, SC-L003-1/-2/-3.
- Shipped `logic/scripting.py` (`_REGISTRY`, `ParamSchema`, `dispatch`, `registered_ops`), `logic/macro.py`
  (`Op`), `logic/plugins.py` (namespaced plugin ops). Constitution Article I, II, VII, X.
- Researcher `docs/subagent-report-the-researcher-ad2616c7-20260707T220150.md` R2.1/R2.2/R2.5 (loop +
  schema best-practice + catalog→tools), R5.1 (action-selector pattern), R5.3 (enforcement in code).
- ADR-0021 (Phase-8 security model), ADR-0022 (DSL/dispatch/CLI placement).
