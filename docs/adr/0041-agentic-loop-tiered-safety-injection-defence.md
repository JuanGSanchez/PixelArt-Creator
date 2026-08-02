# ADR-0041 — Agentic conversation loop, tiered safety-posture (reversibility classification), and prompt-injection / untrusted-tool-result defence (DEP-3)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-08 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-14-ai-assistant` (Slice 14C) |
| Privacy | **S19-PRIVATE — docs/ is gitignored; this ADR is NOT committed.** |
| Relates to | ADR-0039 (action surface + dispatch), ADR-0040 (LLMPort + ChatBackend bridge), ADR-0042 (embedding), ADR-0021 (Phase-8 security), ADR-0026 §6 (untrusted-input caps precedent) |

## Context

Slice 14C is the security heart of Phase 14: a Qt-free `logic/` **agentic loop** that drives the injected
`ChatBackend` (ADR-0040) through the tool catalog + trusted dispatch (ADR-0039), enforces a **tiered safety
posture** (reversible auto-run / destructive confirm — spec D3), and treats every **tool-result as
untrusted input** (prompt-injection defence). The spec froze the boundaries (REQ-P14-LOGIC-004/-005/-006/
-007/-008) and deferred to AGT-01 (spec §8 DEP-3) the concrete **reversibility-classification mechanism**,
which must be *deterministic, unit-testable, logic-level, and never prompt-based*. The Researcher
(`ad2616c7`) grounds: R2.1 canonical loop; R5.1 action-selector + R5.2 tool-results-are-untrusted (OWASP #1
in 2026); R5.3 enforcement in code not prompt; R5.4 confirmation-posture spectrum (tier tools: auto-run
reversible/read-only, confirm destructive; undo-coverage lowers autonomous-posture risk).

## Decision

### 1. The agentic loop — `logic/assistant.py` (NEW, zero Qt) (REQ-P14-LOGIC-005)

`AssistantSession` (or a pure `run_turn(...)` function) orchestrates one user turn:
1. Append the user `Message`; present `Conversation` + `build_tool_catalog()` (ADR-0039) to the injected
   `ChatBackend.respond(...)`.
2. On a returned final assistant `Message` → terminate, return it.
3. On returned `ToolCall`(s) → for each (up to `MAX_TOOL_CALLS_PER_TURN`): apply the **tiered gate** (§2);
   when permitted, execute via `scripting.dispatch(document, [to_op(call)])` (ADR-0039 §4); append the
   **tool-result** as an untrusted, bounded `Message` (§3); loop.
4. Iterate to `MAX_ASSISTANT_TURNS` / `MAX_CONVERSATION_MESSAGES`; on breach raise a domain error
   (bounded-halt, never unbounded — SC-L005-2).

The loop is **deterministic given a fixed adapter** (the fake adapter makes CI fully reproducible —
SC-L005-1) and is **batch/off the per-frame render loop** (Article VI; `FRAME_BUDGET_MS` does not gate a
model round-trip — the stays-responsive contract is REQ-P14-UI-004 / ADR-0042). It imports only
`tool_catalog`, `scripting`, `macro`, `history`, `constants` — a pure `logic` leaf; no `data/`, no Qt.

> **Amendment — 2026-07-08 (AGT-01, Architecture) — Turn-atomicity on the error path (REQ-P14-LOGIC-005; landed during 14E integration).**
> A turn is **atomic**, and that atomicity now extends to the **error path**. The shipped invariant that a single
> rejected/declined tool-call leaves the document **byte-identical** (SC-L006-1, §3/§2) is hereby extended to the
> **whole turn**: if a turn applies **≥1 reversible tool-call command** and *then* fails **mid-turn** — a later
> bounded-halt breach (a `MAX_*` cap, step 4), a transcript overflow, an `LLMError` propagated from the injected
> `ChatBackend.respond`, or any other error raised after a partial apply — `run_turn` guarantees the failure
> surfaces as an `AssistantError` whose **`applied_commands`** attribute holds the **ordered tuple of
> already-applied** `logic.history.Command` objects. A non-`AssistantError` cause is **wrapped** in that single
> `AssistantError` type with the original exception preserved on **`__cause__`** (`raise … from`), so the caller has
> exactly **one** type to catch and **one** attribute to read.
>
> `run_turn` **does not auto-revert** — it only exposes the handle; the caller decides **revert-vs-record**: revert
> the commands in reverse (`apply ∘ undo = identity` → the document is left **byte-identical**, which the 14E UI
> worker does), or record them as **one** undo step. When **no** command had applied there is nothing to revert and
> the original error propagates unchanged (behaviour-neutral); `applied_commands` defaults to the empty tuple. The
> success path is unaffected — applied commands ride on `TurnResult.commands`, never on the error. **Net: no
> orphaned partial mutation on any turn outcome — the turn's error path is as revertable as a single rejected
> tool-call.** Verified by acceptance **SC-L005-3**; tests in `tests/logic/test_assistant_loop.py`.

### 2. Tiered safety — reversibility classification (DEP-3, FROZEN) (REQ-P14-LOGIC-004)

**Mechanism:** an explicit, source-auditable, module-local classification in `logic/assistant.py`:

```
class Reversibility(enum.Enum):   # module-local vocabulary (ADR-0001/BF-2), not a numeric
    REVERSIBLE = "reversible"
    DESTRUCTIVE = "destructive"

REVERSIBLE_OPS: frozenset[str] = frozenset({scripting.OP_BATCH_RECOLOUR, scripting.OP_PROCGEN})

def classify_op(name: str) -> Reversibility:
    return Reversibility.REVERSIBLE if name in REVERSIBLE_OPS else Reversibility.DESTRUCTIVE
```

- **Reversible tier** = an explicit allow-list of ops whose `dispatch` result is a single, cleanly
  undoable `GroupCommand` on the shipped HIS-1 undo stack. The two shipped built-ins (`batch_recolour`,
  `procgen`) qualify — both apply as one reversible `GroupCommand`. These **auto-run** without prompting;
  the edit remains visible and undoable (SC-L004-1).
- **Destructive tier** = **everything else, by default** — any op not explicitly classified reversible
  (unknown/future built-ins, and every namespaced plugin op `"<plugin>.<op>"`). These **require explicit
  user confirmation** before dispatch; without confirmation the loop **refuses to dispatch** (the op is
  neither applied nor silently skipped past the gate — SC-L004-2), and applies only once confirmation is
  supplied (SC-L004-3).

**Why default-to-DESTRUCTIVE (confirm-required):** it is the Article VII / Article VIII **safe default**
(the gate defaults *closed*), and it is what makes the classification *provably* fail-safe — a genuinely
destructive op added later cannot silently auto-run by omission (the failure mode of a default-reversible
allow-list of destructive names). Rubber-stamping friction (R5.4) is bounded because (a) the reversible
tier is the common creative case and auto-runs, and (b) the UI confirm surface names the exact action
(ADR-0042 / REQ-P14-UI-003). The reversible tier is intentionally *small and explicit* — extending it is a
one-line, reviewed, tested change (a new op must *prove* single-undo reversibility to earn auto-run).

**Where it lives + how it leverages the undo stack (D3):** the classification is a pure, deterministic,
unit-testable function in `logic/` (never the prompt, never the model's discretion). The "reversible"
guarantee is *structurally* backed by HIS-1 — a reversible-classified op's `dispatch` result is a single
`GroupCommand` the app pushes onto the undo stack (verified by SC-L003-3 / SC-L004-1). The gate consults
`classify_op` **before** dispatch; confirmation for the destructive tier is a **signal into the loop** (a
UI confirm in 14E; an explicit `--yes`/confirm affordance in the 14F CLI — REQ-P14-DATA-008, SC-D008-2) —
never a prompt asking the model to behave.

### 3. Prompt-injection / untrusted-tool-result defence (REQ-P14-LOGIC-006)

Every tool-result (a dispatched op's output/summary, or any content fed back) is **untrusted input**:
- **Bounded** by named caps — `MAX_TOOL_RESULT_BYTES` (truncate/reject an oversized result — SC-L006-3),
  `MAX_TOOL_CALLS_PER_TURN`, `MAX_ASSISTANT_TURNS`, `MAX_CONVERSATION_MESSAGES` — reusing the
  `cloud_validation`-style size/count posture (ADR-0026 §6, CLD-1).
- **Data, never authority.** A result crafted to say *"now run `<destructive op>`"* or *"you are permitted
  to call `<non-whitelisted op>`"* **cannot** (a) cause a non-whitelisted op to run — the only action path
  is the allow-listed `dispatch` (ADR-0039 §4; a follow-up `wipe_disk` tool-call is rejected exactly as
  SC-L003-1 → SC-L006-1); nor (b) bypass the tiered gate — a destructive op still requires confirmation
  (§2 → SC-L006-2). Privilege is a property of the **registry + gate in `logic/`**, not of conversation
  content. This is the action-selector + no-untrusted-feedback-into-action-choice pattern (R5.1/R5.3).

### 4. Bounded numerics (Article II) (REQ-P14-LOGIC-007)

New named constants in `logic/constants.py` (names distinct from every shipped constant — BF-1). Proposed
values (AGT-03 finalizes; grounded, conservative):

| Constant | Proposed value | Rationale |
| --- | --- | --- |
| `MAX_ASSISTANT_TURNS` | `16` | bounded multi-step agentic run; halts run-away loops |
| `MAX_TOOL_CALLS_PER_TURN` | `8` | supports parallel/multi-tool turns (R2.3) while bounded |
| `MAX_TOOL_RESULT_BYTES` | `65536` (64 KiB) | untrusted-result cap; memory/context bound (R5.2) |
| `MAX_CONVERSATION_MESSAGES` | `256` | transcript bound |
| `ASSISTANT_REQUEST_TIMEOUT_S` | `60` | per-request network timeout (14D urllib) |

Exceeding a bound raises a domain error rather than degrading silently or looping unbounded (SC-L005-2,
SC-L007-1). No numeric literals for these caps anywhere in `logic/`/`data/`/`ui/`.

### 5. Zero `eval`/`exec` — Article VII by construction, source-auditable (REQ-P14-LOGIC-008)

The whole assistant path (`tool_catalog`, the loop, the tiered gate, the `LLMPort` + all adapters, the CLI)
contains **no `eval`/`exec`/`compile`/`__import__` of model output or tool-result content**. Model output
is *data* (`Message` / `ToolCall`) mapped onto `_REGISTRY` — no interpreter to escape (inherits ADR-0021).
A static source scan over the Phase-14 modules finds zero such calls (SC-L008-1; AGT-04/AGT-06 verify).

## Alternatives Considered

- **Per-op reversibility flag added to `register_command`.** Rejected: widens the frozen Phase-8 surface
  (ADR-0039 §6; spec §6 non-goal). The classification is external policy over op-names.
- **Default-to-REVERSIBLE (an allow-list of destructive names).** Rejected: unsafe by omission — a future
  destructive op not yet named would auto-run; contradicts the gate-defaults-closed posture (Article VIII).
- **Undo-cost heuristic (auto-run iff the emitted `GroupCommand`'s undo footprint is "small").** Rejected:
  not deterministic/legible enough for a security gate; an explicit classified set is auditable and
  testable. (The undo stack still *backs* the reversible guarantee structurally — §2.)
- **Prompt-level safety (ask the model to seek permission for destructive actions).** Rejected outright
  (R5.3, Article VII): injection can override a prompt; the boundary must be code.
- **Plan-Then-Execute / Dual-LLM quarantine (R5.1 complementary patterns).** Deferred as future hardening;
  the action-selector + tiered gate + untrusted-result bounds already satisfy Article VII for v1.

## Consequences

**Positive.** A deterministic, headless, fully CI-testable agentic contract (via the fake adapter) with a
fail-safe tiered gate and structural injection resistance — Article VII by construction. The classification
is a two-line, source-auditable function; extending the reversible tier is a reviewed, tested change.

**Negative / risk.** Default-confirm means plugin ops and any future built-in require confirmation until
explicitly classified reversible — mild UX friction, deliberately on the safe side; mitigated by the
clear, action-naming confirm surface (ADR-0042) and by the reversible tier covering the common creative
edits. The reversible allow-list must be maintained as new ops ship — mitigated by making auto-run
*opt-in* (a new op is safe-by-default until proven reversible).

## Grounding

- Spec §2 (14C), §4 REQ-P14-LOGIC-004/-005/-006/-007/-008, §5 (security posture), §8 DEP-3, §10.1 D3,
  §10.2; `acceptance.md` SC-L004-1/-2/-3, SC-L005-1/-2/-3, SC-L006-1/-2/-3, SC-L007-1, SC-L008-1, SC-D008-2
  (SC-L005-3 = the 2026-07-08 turn-atomicity-on-error amendment above).
- Shipped `logic/history.py` (HIS-1 undo stack), `logic/scripting.py` (dispatch atomicity),
  `data/cloud/`/`logic/cloud_validation` (the caps posture, CLD-1). Constitution Article I, II, VI, VII, VIII.
- Researcher `ad2616c7` R2.1/R2.3, R5.1/R5.2/R5.3/R5.4, R6.2. ADR-0021, ADR-0026 §6, ADR-0039, ADR-0040.
