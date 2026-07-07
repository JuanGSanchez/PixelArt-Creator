# Analyze Report (C1) — Phase 14: In-App, Model-Agnostic AI Assistant

| Field | Value |
| --- | --- |
| Feature | `phase-14-ai-assistant` |
| Author | Claude (AGT-01, Architecture) via `sdd-analyze` |
| Date | 2026-07-08 |
| Artifacts | `constitution.md`, `specs/phase-14-ai-assistant/{spec.md, acceptance.md, traceability.md, plan.md, tasks.md}` + ADR-0039/0040/0041/0042 (private) |
| **Verdict** | **PASS — zero unresolved cross-artifact findings (C1 satisfied, Article VIII). The implement gate MAY open.** |

---

## 0. Gate precondition

All four required artifacts exist and are parseable: `constitution.md`, `spec.md`, `plan.md`, `tasks.md`
(+ `acceptance.md`, `traceability.md`). Gate precondition met (no AN-E1/AN-E2). Analysis proceeds.

## 1. Spec ↔ constitution compliance

| Article | Requirement | Status |
| --- | --- | --- |
| I — three-layer purity | logic/data Qt-free; ui only Qt; one-way deps; no cycle | **PASS** — plan §11 proves it; the loop (`logic/`) reaches the port (`data/llm/`) via a `logic`-side `ChatBackend` **Protocol** + injection (ADR-0040 §2), so **no `logic → data` edge**; `data/llm` imports only `logic` types + stdlib. Baseline `check_layering`/`check_cycles` exit 0 (both roots). No new top-level package, no rule change. |
| II — single-source constants | every numeric once in `constants.py` | **PASS** — 5 named caps (`MAX_ASSISTANT_TURNS`, `MAX_TOOL_CALLS_PER_TURN`, `MAX_TOOL_RESULT_BYTES`, `MAX_CONVERSATION_MESSAGES`, `ASSISTANT_REQUEST_TIMEOUT_S`), names distinct from every shipped constant; no literals (LOGIC-007; T14C-01). |
| III — formatted/linted/typed | Black/isort/flake8/mypy | **PASS** — every slice's commit task enforces the local quality gate. |
| IV — headless coverage, one-per-criterion | fake adapter, ≥90/80 | **PASS** — the whole contract is CI-testable via the fake `LLMPort` (no key/network); one test per SC; coverage gate on the fake path; live tests `@assistant_live` deselected (DATA-002; T14*-tests). |
| V — a11y / i18n / both themes | UI | **PASS** — T14E-05 (i18n + `string_audit_check`), T14E-06 (both themes), T14E-07 (a11y). |
| VI — performance / 16 ms | per-frame budget | **PASS** — assistant is batch/off the per-frame loop; `FRAME_BUDGET_MS` does not gate a model call; no new per-frame canvas work → no AGT-10 directive (DEP-5, ADR-0042 §3). |
| VII — security | validated input, no `eval`/`exec`, no secrets | **PASS (central)** — action surface = allow-listed `dispatch` (no widening, ADR-0039); zero `eval`/`exec` + source audit (LOGIC-008; T14C-05); tool-results untrusted + bounded (LOGIC-006); tiered gate logic-enforced (LOGIC-004); keys only in keyring inside `data/llm/`, never in `.pixproj`/logs, live path out-of-CI (DATA-003/-006). |
| VIII — SDD gate law | analyze before implement | **PASS** — this report is the gate; tasks forbid dispatch until PASS. |
| X — REQ-ID scheme + traceability | `REQ-P<phase>-<LAYER>-<NNN>` + traced | **PASS** — 24 REQs conform; each traces to article/primitive + ≥1 SC + expected test. |
| XI — extensibility | clean extension | **PASS** — `LLMPort` is the provider extension seam; adding a provider = adding an adapter. |

No constitution conflict (AN-D2 not triggered).

## 2. Plan ↔ spec fidelity (no drift)

- **DEP-1..DEP-5 all resolved** in the plan/ADRs exactly as the spec deferred them (plan §4; ADR-0039–0042).
  No decision reopens a FROZEN D1–D5; no HOW contradicts a spec WHAT.
- **Placement:** spec assumes `data/llm/` mirroring `data/cloud/` + CLI mirroring `automation_cli.py`; plan
  confirms `data/llm/` subpackage + `data/assistant_cli.py`, NOT a new top-level package — consistent with
  the spec's assumption and the `sync_backend`/`web_viewer` contrast (ADR-0040 §1).
- **Tool-schema contract (DEP-2):** plan/ADR-0039 freeze a faithful `ParamSchema`→JSON-schema projection
  that never widens `dispatch` — matches REQ-P14-LOGIC-002/-003 verbatim ("faithful projection", "never
  permits arguments `validate` would reject", "no path outside the registry").
- **Reversibility (DEP-3):** plan/ADR-0041 pick the explicit-allow-list-with-default-DESTRUCTIVE mechanism
  — within the spec's stated candidate space and satisfying "deterministic + unit-testable + logic-level +
  never prompt-based" (REQ-P14-LOGIC-004).
- **Docs (UI-008):** plan/ADR-0042 add a **topic** under the existing `automation-and-scripting` section,
  preserving `len(sections) == len(REQUIRED_AREAS) == 12` — verified against shipped
  `logic/guide_model.py` (12 areas incl. `automation-and-scripting`). No drift.
- **No new hard dependency (S8):** plan §Stack + ADR-0040 keep the real adapters stdlib-`urllib`; only the
  optional `keyring` behind `assistant_live` — matches spec §6 non-goal ("no new runtime technology").

## 3. Tasks ↔ plan completeness + coverage

**Every REQ-ID appears in the plan and in ≥1 task; no orphan task** (every task carries its REQ-IDs;
commit/packaging/CI tasks carry the slice's REQs).

| REQ-ID | Plan § | Task(s) | Acceptance |
| --- | --- | --- | --- |
| LOGIC-001 | §5 | T14A-01, T14A-04 | SC-L001-1/-2 |
| LOGIC-002 | §5 | T14A-02, T14A-04 | SC-L002-1 |
| LOGIC-003 | §5 | T14A-03, T14A-04 | SC-L003-1/-2/-3 |
| LOGIC-004 | §5 | T14C-02, T14C-05 | SC-L004-1/-2/-3 |
| LOGIC-005 | §5 | T14C-03, T14C-05 | SC-L005-1/-2 |
| LOGIC-006 | §5 | T14C-04, T14C-05 | SC-L006-1/-2/-3 |
| LOGIC-007 | §5/§10 | T14C-01, T14C-05 | SC-L007-1 |
| LOGIC-008 | §2 | T14C-05 (source audit) | SC-L008-1 |
| DATA-001 | §6 | T14B-01, T14B-02, T14B-06 | SC-D001-1 |
| DATA-002 | §6 | T14B-03, T14B-06 | SC-D002-1 |
| DATA-003 | §6/§9 | T14B-04, T14B-05, T14B-06 | SC-D003-1/-2 |
| DATA-004 | §6 | T14D-01, T14D-03 | SC-D004-1/-2 |
| DATA-005 | §6 | T14D-02, T14D-03 | SC-D005-1/-2 |
| DATA-006 | §6 | T14B-04, T14D-01/-02, T14D-03 | SC-D006-1/-2 |
| DATA-007 | §6/§11 | T14B-02, T14D-01/-02, T14D-04 | SC-D007-1 |
| DATA-008 | §6 | T14F-01/-02/-03 | SC-D008-1/-2 |
| UI-001 | §7 | T14E-02, T14E-06 | SC-UI-001-1 |
| UI-002 | §7 | T14E-03, T14E-06 | SC-UI-002-1 |
| UI-003 | §7 | T14E-04, T14E-06 | SC-UI-003-1 |
| UI-004 | §7 | T14E-01, T14E-06 | SC-UI-004-1 |
| UI-005 | §7 | T14E-07 | SC-UI-005-1 |
| UI-006 | §7 | T14E-07 | SC-UI-006-1 |
| UI-007 | §8 | T14E-05 | SC-UI-007-1 |
| UI-008 | §8 | T14E-08, T14E-09 | SC-UI-008-1/-2 |

**Coverage: 24/24 REQs in plan + tasks; 0 uncovered; 0 orphan tasks.** Six mandated security/agentic
invariants all mapped (tiered-safety SC-L004-*/SC-UI-003-1/SC-D008-2; whitelist SC-L003-1/-2; injection
SC-L006-*; credential-gating SC-D002-1/SC-D003-*/SC-D006-1; model-agnostic SC-D005-1; no-eval audit
SC-L008-1).

## 4. Conflicts

**None.** No cross-artifact contradiction. Cross-checks passed: LLMPort placement (data/llm — spec/plan
agree); constants distinct from shipped; ADR numbers 0039–0042 free (highest committed ADR is 0038); the
`ChatBackend` Protocol bridge is consistent with Article I and the shipped `macro.set_dispatcher`/
`blend.CompositeNode` precedent; `assistant_live` extra/marker mirror shipped `cloud_live`;
`pixelart-assistant` entry mirrors `pixelart-run`.

## 5. Observations (non-blocking, not findings)

- **`logic/assistant.py` is touched in two slices:** 14B (T14B-01) freezes its value types + `ChatBackend`
  Protocol (the port's contract); 14C adds the loop/gate body. This is intentional interface-contract
  discipline (freeze-then-implement), not drift; each slice leaves the module gate-green.
- **`agt-12` / `llm-adapter-normalization` asset:** flagged to the orchestrator (plan §12) — a 14D-only
  decision at contract-freeze; does not block 14A–14C/14F and is not a C1 finding.
- **Local-CI authoritative:** remote Actions is billing-blocked; each slice's gate is the local run
  (layering/cycles/quality/tests/coverage/string-audit/path-portability). AGT-09 owns the
  `assistant_live` CI-deselection when remote CI resumes.

## 6. Deterministic script baseline (Article I evidence)

At plan/analyze time, with no Phase-14 code yet on disk: `python scripts/check_layering.py` →
`clean (180 modules)` exit 0; `--root .` → `clean (5 modules)` exit 0; `check_cycles` → no cycles, exit 0
on both roots. The plan implies **no** forbidden edge (§11), so these stay 0 as Phase-14 modules land.

## 7. Verdict

**PASS (AN-D1 Branch A).** Zero unresolved cross-artifact findings. The C1 gate is satisfied
(Article VIII); the orchestrator may dispatch implementation slice-by-slice (14A→14B→14C→{14D,14F,14E}) per
`tasks.md`. Each slice must re-verify the local gate + `check_layering`/`check_cycles` (both roots) exit 0
before its commit (Article IX).
