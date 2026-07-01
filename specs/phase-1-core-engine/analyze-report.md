# Analyze Report — Phase 1: Core Engine (C1 gate)

| Field | Value |
| --- | --- |
| Feature | `phase-1-core-engine` |
| Phase | `sdd-analyze` (Article VIII gate, C1) — task T8 |
| Author | Claude (AGT-01, Architecture) |
| Date | 2026-07-02 |
| Artifacts | `constitution.md` · `spec.md` + `traceability.md` · `plan.md` + `tasks.md` · `docs/adr/0001-*.md` · remediated `logic/**` + `data/**` |
| Verdict | **PASS** — zero unresolved cross-artifact findings |

---

## 0. Gate preconditions (Article VIII)

All four required artifacts exist and are parseable: `constitution.md`, `spec.md`,
`plan.md`, `tasks.md`. Traceability matrix + ADR-0001 present. Gate is permitted to run.

## 1. Deterministic layering / cycle gates (Article I)

| Script | Result | Exit |
| --- | --- | --- |
| `python scripts/check_layering.py` | `clean (11 modules)` | **0** |
| `python scripts/check_cycles.py` | `no cycles (12 modules)` | **0** |

Both exit 0 (Decision A1-D3 → Branch B, accept). Article I satisfied; REQ-P1-LOGIC-013
(S11 Qt-free purity) holds. No script errored (no exit 2).

## 2. Remediation verified against code ground truth (T1–T6)

Not rubber-stamped — the plan/tasks claims were checked against source:

| Task | Claim | Verified |
| --- | --- | --- |
| T1 | 3 tuning constants added to `constants.py` w/ citations | `MAX_PALETTE_SIZE=256` (L15), `DEFAULT_FRAME_DURATION_MS=100` (L16), `PROJECT_ZLIB_LEVEL=9` (L17). `constants.py` still a leaf. ✓ |
| T2 | `palette.py` imports + re-exports `MAX_PALETTE_SIZE` | import L14, `__all__` re-export L19, used L73–74. ✓ |
| T3 | `document.py` imports + re-exports `DEFAULT_FRAME_DURATION_MS` | import L14, re-export L21, default-arg L74/L144. ✓ |
| T4 | `project_io.py` single-sources both values | imports L21/L24; `zlib.compress(raw, PROJECT_ZLIB_LEVEL)` L49; `get("duration_ms", DEFAULT_FRAME_DURATION_MS)` L209. No inline `100`/`9`. ✓ |
| T5 | compactor header states real explicit-args contract | header L18 "REQUIRED explicit positive-int args"; false "default MAX_CANVAS" claim removed. ✓ |
| T6 | `CompactionError` → `ValueError` | `class CompactionError(ValueError)` L53, matching the other 5 domain errors. ✓ |

S12 (Article II) is now satisfied by the remediation; ADR-0001 governs the
tuning-vs-intrinsic boundary and the EXEMPT intrinsics stay local (correctly not moved).

## 3. Cross-artifact consistency

- **spec ↔ constitution:** REQ scheme conforms to Article X (`REQ-P<phase>-<LAYER>-<NNN>`).
  Article II/S12 findings (§9) are all dispositioned by plan §7 + ADR-0001. Article VII
  defensive-load requirements match REQ-P1-DATA-001. No spec decision contradicts an
  article (Article VIII supremacy holds).
- **plan ↔ spec:** module→layer map (plan §3) covers all 8 shipped modules + `project_io`;
  data model (plan §5) matches REQ-P1-DATA-001; no drift. Stack fully grounded by S8 (no
  invention).
- **tasks ↔ plan:** T1–T8 realise plan §6 steps 1–5 + §8 verification + Article VIII gate.
  Dependency graph acyclic and complete. **No orphan task** — every task carries a
  REQ/acceptance link.

## 4. Coverage (Article X / Article IV)

- 14 REQ-IDs total. **12 covered** (Gherkin scenario + ≥1 passing test); **2 spec-only by
  design** (REQ-P1-LOGIC-012 S12 enforced by review; REQ-P1-LOGIC-013 S11 enforced by
  scripts). **0 uncovered.**
- Test/coverage evidence (T7, established): 159 tests pass headless; logic 98.51% line /
  98.05% branch, data 100/100 — both clear the 90/80 gate (Article IV / NFR-5).
- Traceability delta for REQ-P1-LOGIC-004 is **applied**: now traces S7 (palette nearest)
  + S2 (flood-fill tolerance) in spec §4 and `traceability.md` — closing the earlier
  Article X "no-S-id" concern for -004 without inventing an S-id.

## 5. Findings dispositioned as RESOLVED (not blocking)

Per the authoritative orchestrator adjudication (2026-07-02) and ADR-0001:

- **REV-1..7 RATIFIED** as foundational primitives shipped early — no code removal.
- **REQ-P1-LOGIC-011** (MaxRects compactor): traces research F8 → forward Phase-7 (ROADMAP
  P7 texture atlas). RESOLVED by ratification (foundational library shipped early).
- **REQ-P1-LOGIC-003** (`color.blend_over`): forward → Phase-4 blend modes; the Phase-1
  alpha-compositing *capability* is separately covered by REQ-P1-LOGIC-007 (`blit(blend=True)`,
  traces S1/S8). RESOLVED.
- **`distance_sq`** consumed within Phase-1 (palette nearest + flood-fill tolerance) → -004
  traced to S7/S2. RESOLVED.
- **S12 intrinsics** (`0..255`, channel `4`, `255.0`, `FORMAT_VERSION=1`, Bresenham/ellipse
  literals): ADR-0001-EXEMPT, correctly left local. RESOLVED.

## 6. Non-blocking observations (advisory; do not hold the gate)

1. **OBS-1 (AGT-02, cosmetic):** plan §9 item 1 parenthetically wrote the -004 drawing
   trace as "S1 via drawing", whereas spec §4 / §11 / `traceability.md` (the requirement
   authority) consistently use **S2** (flood-fill tolerance). The spec set is internally
   consistent; only the plan's loose parenthetical differs. Optional: align plan wording.
2. **OBS-2 (AGT-02, durability):** Article X's literal text says "dossier S-id". REQ-P1-
   LOGIC-011 (F8/Ph7) and -003 (Ph4) trace to a research finding / forward phase rather
   than an S1–S19 id; the orchestrator ratification is the governing resolution. Recommend
   the durable Phase-7 / Phase-4 specs formally inherit these REQs (a Phase-7 REQ inherits
   -011; Phase-4 inherits the -003 blend-mode semantics) so the forward trace lands on a
   concrete requirement when those phases open.

Neither observation is a cross-artifact contradiction or a coverage gap; both are advisory
follow-ups for AGT-02, not gate blockers.

## 7. Verdict

**PASS (C1 open).** Zero unresolved cross-artifact findings (Decision AN-D1 → Branch A;
Decision A1-D2 → Branch A). constitution ↔ spec ↔ plan ↔ tasks ↔ code ↔ tests are
consistent; every REQ is specified, has acceptance criteria, and (where applicable) a
passing test; S12 is satisfied by the verified remediation; layering/cycle gates exit 0;
no orphan tasks; naming/architecture/numerics conform to the constitution and CONVENTIONS.
The orchestrator may proceed to accept the retroactive Phase-1 core-engine slice.

**EXIT_STATUS: COMPLETED** (analyze ran, produced a PASS verdict).
