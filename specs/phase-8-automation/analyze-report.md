# Analyze Report (C1) — Phase 8: Automation & Extensibility

| Field | Value |
| --- | --- |
| Feature | `phase-8-automation` |
| Author | Claude (AGT-01, Architecture) via `sdd-analyze` |
| Date | 2026-07-04 |
| Artifacts | `constitution.md`, `specs/phase-8-automation/spec.md`, `plan.md`, `tasks.md` (all present) |
| Gate | **C1 — cross-artifact consistency + coverage** (Article VIII; defaults closed) |
| **Verdict** | **PASS** — 0 unresolved findings; **0 uncovered REQ-IDs** |

---

## 1. Gate (step 1)

All four artifacts exist and parse: `constitution.md` (repo root), `spec.md`, `plan.md`, `tasks.md`
(`specs/phase-8-automation/`). Gate open to analysis. (`sdd-analyze` AN-E1/AN-E2 not triggered.)

## 2. spec ↔ constitution compliance (step 2)

| Article | Spec/plan/tasks posture | Verdict |
| --- | --- | --- |
| I (three-layer) | Engine pure `logic/` + Qt-free `data/`; CLI in `data/` (guarded); UI-only panels; `plugins → scripting` one-way, `macro`↛`scripting`, no `logic → data` (plan §4.4). | ✅ |
| II (numerics) | 6 new constants in `logic/constants.py`, names distinct (`MAX_BATCH_RECOLOUR_TARGETS` ≠ `MAX_BATCH_TARGETS`); op-name/`schema_version`/`Capability` enum intrinsic-local (plan §8, ADR-0001/BF-2). | ✅ |
| IV (testing) | Every REQ + the 6 [SEC] invariants → ≥1 headless pytest/Hypothesis or pytest-qt (both themes) task (tasks 8A–8E). | ✅ |
| V (UX) | REQ-P8-UI-012/-013/-014 blocking gates (TG-03/04/05). | ✅ |
| VI (perf) | REQ-P8-UI-011 = responsiveness (progress/cancel), explicitly NOT the 16 ms budget (plan §7). | ✅ |
| **VII (security)** | **No `eval`/`exec` on any input — satisfied by construction** (DSL executes data; ADR-0021); defensive IO-3 load (`MacroIOError`); deny-by-default + no-auto-run plugins; bounded automation; portable paths. | ✅ |
| VIII (SDD gate) | This report is the pre-implement gate; dispatch held until PASS. | ✅ |
| X (traceability) | Every REQ traces to S-id / F / forward primitive (HIS-1, DOC-1, PB-1, CO-4, PS-1, IO-3, CLI-1). | ✅ |
| XI (extensibility) | Untrusted-plugin OS-isolation, embedded interpreter, hosted registry, remote exec, AI-gen deferred as clean seams. | ✅ |

No constitution conflict (AN-D2 Branch A not triggered).

## 3. plan ↔ spec fidelity (step 2) — no drift

- The five spec HOW-deferrals (DEP-2a–f) are each ruled: security model (ADR-0021, PL8-D4); plugin
  isolation/discovery/manifest (ADR-0021/0022, PL8-D5); macro format/versioning/replay (ADR-0022,
  PL8-D6); CLI grammar+placement (ADR-0022, PL8-D7); procgen set + batch scope (ADR-0022, PL8-D8).
- **DEP-4 (`REQ-P8-DATA-*` prefix)** resolved: plan ratifies the fold under REQ-P8-LOGIC-007 (ADR-0022
  §4, PL8-D9). Spec flagged it as not-acceptance-changing; plan agrees. Consistent.
- **DEP-3 (responsiveness)** routed to AGT-10/AGT-05 (plan §7, PL8-D10). Consistent with spec §5.
- **BF-1** (6 constants) placed (plan §8); **BF-2** (DSL/enum vocabulary intrinsic-local) honoured.
- The plan introduces **no** acceptance not in the spec, and drops **none**. Every observable contract
  (no eval/exec; edits only via reversible commands; deterministic replay; sandbox/deny-by-default;
  CLI==GUI state-identity) is preserved verbatim from the spec's framing.

## 4. tasks ↔ plan completeness + REQ coverage (step 3)

**28/28 REQ-IDs covered** (14 LOGIC + 14 UI + 0 DATA) — each appears in the plan module map **and** in
≥1 implementation task **and** ≥1 test/verify task. **0 uncovered.**

| REQ | Plan module | Impl task | Test/verify task |
| --- | --- | --- | --- |
| LOGIC-001 | scripting | T8A-02/03 | T8A-06 (SC-L001-1 [SEC]) |
| LOGIC-002 | scripting | T8A-03 | T8A-06, T8D-02/03 (SC-L002-1) |
| LOGIC-003 | scripting | T8A-03 | T8A-06 (SC-L003-1 [SEC]) |
| LOGIC-004 | macro | T8A-04 | T8A-06 (SC-L004-1) |
| LOGIC-005 | macro | T8A-05 | T8A-06 (SC-L005-1 [SEC]) |
| LOGIC-006 | macro | T8A-05 | T8A-06 (SC-L006-1) |
| LOGIC-007 | data/macro_io | T8B-03 | T8B-04 (SC-L007-1 [SEC]) |
| LOGIC-008 | plugins | T8B-01 | T8B-04 (SC-L008-1) |
| LOGIC-009 | plugins | T8B-02 | T8B-04 (SC-L009-1 [SEC]) |
| LOGIC-010 | plugins | T8B-02 | T8B-04 (SC-L010-1 [SEC]) |
| LOGIC-011 | batch_ops | T8C-01/03 | T8C-04 (SC-L011-1) |
| LOGIC-012 | procgen | T8C-02/03 | T8C-04 (SC-L012-1) |
| LOGIC-013 | constants + all | T8A-01 + bound checks | T8A-06/T8B-04/T8C-04 (SC-L013-1) |
| LOGIC-014 | data/automation_cli | T8D-01 (+ T8D-04 pyproject) | T8D-02 (SC-L014-1) |
| UI-001 | macro_controls | T8E-01 | T8E-07 (SC-UI-001-1) |
| UI-002 | macro_controls | T8E-01 | T8E-07 (SC-UI-002-1) |
| UI-003 | macro_controls | T8E-01 | T8E-07 (SC-UI-003-1) |
| UI-004 | script_runner_panel | T8E-02 | T8E-07 (SC-UI-004-1) |
| UI-005 | plugin_manager_panel | T8E-03 | T8E-07 (SC-UI-005-1 [SEC-facing]) |
| UI-006 | batch_recolour_panel | T8E-04 | T8E-07 (SC-UI-006-1) |
| UI-007 | procgen_panel | T8E-04 | T8E-07 (SC-UI-007-1) |
| UI-008 | plugin_manager_panel | T8E-03 | T8E-07 (SC-UI-008-1 [SEC-facing]) |
| UI-009 | commands.py | T8E-06 | T8E-07 (SC-UI-009-1) |
| UI-010 | automation_cli/worker | T8E-05 | T8E-08 (SC-UI-010-1) |
| UI-011 | automation_worker | T8E-05 | T8E-08 (SC-UI-011-1) |
| UI-012 | (all panels) | T8E-01..05 | TG-03 (SC-UI-012-1) |
| UI-013 | (all panels) | T8E-01..05 | TG-04 (SC-UI-013-1) |
| UI-014 | (all panels) | T8E-01..05 | TG-05 (SC-UI-014-1) |

**Orphan tasks (no REQ):** TG-01 (STRUCTURE, Article I), TG-02 (this gate, Article VIII), T8D-03
(layering scripts, Article I), TG-06 (CHANGELOG, Article IX), TG-07 (checklist, Article IV/V) — each
cites its governing article/gate and is a legitimate cross-cutting task, **not** a stray orphan.

## 5. Conflicts (step 4) — none unresolved

- Determinism (LOGIC-005) vs stochastic procgen (LOGIC-012): resolved by the **mandatory recorded
  seed** (plan §3/§5; ADR-0022). No conflict.
- `MAX_BATCH_RECOLOUR_TARGETS` vs shipped `MAX_BATCH_TARGETS`: distinct names (Article II/BF-1). No
  conflict.
- Plugin "marketplace-ready" vs Article VII: resolved — P8 ships a **trusted-with-consent local**
  contract; untrusted-marketplace OS-isolation deferred (ADR-0021, Article XI). No conflict.
- The 6 [SEC] scenarios in spec §11 (SC-L001/003/005/007/009/010) match the plan's 6 [SEC] invariants
  and each has a dedicated security test (T8A-06, T8B-04). Consistent.

## 6. Deterministic checks (run separately by AGT-01, plan §11)

- `python scripts/check_layering.py` → exit **0** (clean, 40 modules) — baseline 2026-07-04.
- `python scripts/check_cycles.py` → exit **0** (no cycles, 95 modules) — baseline 2026-07-04.
- Planned Phase-8 edges are acyclic by construction (plan §4.4); AGT-03 re-runs both when 8A–8D land.

## 7. Verdict (step 5)

**PASS (C1).** Unresolved-findings list is **empty**; **0 uncovered REQ-IDs** (28/28). The implement
gate is **open** for Phase 8 — the orchestrator may proceed to dispatch Slices 8A→8E (tests authored
by AGT-04/AGT-06, `pending`). The security-sensitive [SEC] invariants (Article VII) are each bound to
a dedicated test and must be green before ship (TG-07 `sdd-checklist`).
</content>
