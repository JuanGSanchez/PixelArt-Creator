# Analyze Report (C1 gate) — Phase 5: Animation System

| Field | Value |
| --- | --- |
| Feature | `phase-5-animation` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Artifacts | `constitution.md`, `specs/phase-5-animation/spec.md`, `plan.md`, `tasks.md` (all present) |
| Scripts | `check_layering.py` exit **0** (clean, 32 modules); `check_cycles.py` exit **0** (no cycles, 78 modules) — re-run at pre-commit 2026-07-03 |
| Verdict | **PASS (C1)** — gate OPEN for implement (AN-D1 Branch A). **Re-confirmed PASS at pre-commit** after implement+test (see §7) |

---

## 1. Gate precondition

All four artifacts exist and parse (AN-E1/E2 clear). Constitution v1.0 governs; spec is
`specify+clarify` COMPLETE (36 REQ, 16 clarifications resolved, 0 open); plan + tasks authored this
session.

## 2. spec ↔ constitution compliance

| Article | Check | Result |
| --- | --- | --- |
| I (three-layer) | `animation.py` Qt-free; `QTimer`/panels in `ui/`; sole outside-`ui/` Qt file stays `ui/commands.py`; `document → animation` one-way | PASS (plan §3.4; scripts exit 0) |
| II (numerics) | 8 new tuning values in `constants.py`; `PlaybackMode` vocabulary in `animation.py`; `DEFAULT_FRAME_DURATION_MS` reused | PASS (plan §8) |
| IV (testing) | one test per criterion, headless, both themes for UI | PASS (tasks T5A-09..12, T5C-07..11) |
| V (UX) | a11y + both themes + tr() as blocking gates | PASS (UI-017/018/019 → T5C-10/11/12) |
| VI (perf) | 8K scrub/playback ≤ 16 ms; cached composite; never cull; never relax | PASS (UI-016 → T5C-06 impl + T5C-13 profile; ADR-0011 §Perf) |
| VII (security) | defensive validated v3 tag load; frame/onion/tag bounds; positive-duration guard; no eval/exec | PASS (ADR-0012; T5B-02, T5A-07 guards) |
| X (traceability) | every REQ traces to S-id/F/inherited primitive + ≥1 scenario | PASS (`traceability.md`, 36/36 covered) |
| VIII (SDD gate) | this analyze | PASS (§6) |
| XI (extensibility) | cel-linking + Phase-9 preview deferred without weakening any article | PASS (spec §6, plan §6/§10) |

No spec decision conflicts with an article (AN-D2 not triggered).

## 3. plan ↔ spec fidelity (no drift)

- Every spec capability is realised in the plan: `PlaybackMode`+sequencing (§2/§4), onion overlay
  (§2/§4), FrameTag model + named animation (§4/§5), reversible frame/tag ops (§5), per-frame render
  reuse of `composite_stack` (§2), constants (§8), UI panels (§3.3).
- **DEP-1** (Researcher grounding) satisfied — `docs/research-phase5-animation.md` landed; plan
  cites Q1–Q4 throughout; PL5-D1 → Branch B (no invention).
- **DEP-2** (`.pixproj` schema) **ruled**: v3 bump + native `PlaybackMode` + v1/v2 back-compat
  (ADR-0012, plan §6). Consistent with REQ-P5-DATA-001/002/003 and CL-15.
- **DEP-3** (perf) **routed** to AGT-10 with FU-19 folded in (plan §7, ADR-0011 §Perf, task T5C-13);
  budget never relaxed (Article VI).
- BF-1 (onion draw method) left as an AGT-05 HOW; BF-2 (constant placement) resolved (§8).
- Interface contracts for `animation.py` (§4) and `document.py` frame/tag ops (§5) frozen before
  implementation, as directed.

No requirement is dropped, weakened, or contradicted by the plan.

## 4. tasks ↔ plan completeness / coverage

**Every REQ-ID (14 LOGIC + 19 UI + 3 DATA = 36) appears in the plan and in ≥1 impl + ≥1 test/verify
task.** Coverage matrix (impl → test):

- LOGIC-001..003 → T5A-02/03 → T5A-09; LOGIC-004..008 → T5A-06/07 → T5A-11; LOGIC-009 → T5A-04 →
  T5A-12; LOGIC-010/011 → T5A-08 → T5A-12; LOGIC-012/013/014 → T5A-01/05/07 → T5A-10/11.
- UI-001/002 → T5C-01 → T5C-07; UI-003..007/015 → T5C-02 → T5C-07; UI-008..010 → T5C-03 → T5C-08;
  UI-011/012 → T5C-04 → T5C-09; UI-013 → T5C-05 → T5C-09; UI-014 → T5C-05 → T5C-08; UI-016 →
  T5C-06 → T5C-13; UI-017 → T5C-10; UI-018 → T5C-11; UI-019 → T5C-12.
- DATA-001/002 → T5B-01 → T5B-03; DATA-003 → T5B-02 → T5B-04.

**No uncovered REQ.** **No orphan implementation task:** the only non-REQ tasks are gate/process
tasks tied to articles (T5A-13/T5B-05 → Article I layering; TG-01 → Article I map; TG-02 → Article
VIII; TG-03 → Article IX; TG-04 → Article IV/V/VI checklist) — intentional, not orphans. Every task
names one owner (TK-D1) and its target file(s); deterministic sub-steps name their script (TK-D2:
T5A-13/T5B-05 `check_layering`/`check_cycles`, T5C-12 `string_audit_check`, T5C-13 `perf_profile`).

## 5. Cross-artifact observations (resolved, non-blocking)

- **O-1 (`FrameTag.color`).** The plan/ADR-0012 include an Aseprite-style `color` UI-marker field
  (research Q3 + the orchestrator directive) beyond the spec REQ-P5-LOGIC-009 minimum
  (name/range/mode/repeat). Additive, grounded, contradicts no REQ. **Resolved:** persisted under
  v3; T5B-03's round-trip assertion should include `color` alongside the 5 core fields checked by
  SC-D001-1. Advisory within an existing task — not a gate finding.
- **O-2 (`ONION_SKIN_OPACITY_MIN`).** The plan adds this constant for the research-grounded linear
  distance falloff (spec §4 marks falloff "optional"). Additive and Article II-compliant (in
  `constants.py`). Flagged **medium reliability** (research Q1) — confirm at implementation.
- **O-3 (onion default 1/1).** Plan uses spec CL-4's Aseprite 1/1 (spec authoritative) over the
  research's medium-reliability 2/2 suggestion. Consistent, no conflict.
- **O-4 (stable `layer_id`).** Additive per research Q4; enables timeline tracks; full cross-frame
  track unification deferred with cel linking (spec §6). No spec conflict.

None of O-1..O-4 is an unresolved cross-artifact contradiction; all are additive, grounded, and
non-blocking.

## 6. Verdict

**PASS — C1 gate OPEN.** Zero unresolved findings; spec↔constitution compliant, plan↔spec faithful,
tasks↔plan complete (36/36 REQ covered, impl+test), layering + cycle scripts exit 0. Per Article
VIII the orchestrator may proceed to `implement` (Slice 5A first). The gate defaults closed; it is
opened here only because the unresolved list is empty.

## 7. Pre-commit re-confirmation (2026-07-03, post implement + test)

Re-run of the C1 gate over the shipped Phase-5 tree, immediately before commit:

- **Scripts.** `python scripts/check_layering.py` → exit **0** (clean, 32 modules);
  `python scripts/check_cycles.py` → exit **0** (no cycles, 78 modules). Verified: `logic/animation.py`
  is **Qt-free** (imports only `blend`/`color`/`constants`/`pixel_buffer`) and **never imports
  `document`** — the sole new intra-logic edge is `document → animation → blend` (acyclic, PL5-D3).
  The new off-thread pre-warm worker keeps Qt in `ui/` only: `ui/composite_warmer.py`
  (`QObject`/`QRunnable`/`Signal`) calls the **Qt-free** `blend.composite_stack` on a worker thread;
  `ui/frame_cache.py` holds an LRU of `PixelBuffer`s with **zero Qt**; `ui/prewarm_indicator.py` is a
  pure widget. No `logic → Qt` leak.
- **Coverage.** 36/36 REQ (14 LOGIC + 19 UI + 3 DATA) map to ≥1 impl + ≥1 shipped test; **0
  uncovered** (`traceability.md` refreshed — stale `pending` test names replaced with the seven
  on-disk modules).
- **C1 consistency.** spec ↔ impl ↔ tests aligned; ADR-0011 (animation model + cached/off-thread
  composite) and ADR-0012 (`.pixproj` **v3** — `FORMAT_VERSION=3`, `_SUPPORTED_VERSIONS=(1,2,3)`)
  both on disk and reflected in `document.py`/`animation.py`/`project_io.py`.
- **Perf loop-back.** DEP-3 playback perf loop-back **D1/D2/D3 landed** (per-frame composite cache
  `ui/frame_cache.py` + off-thread pre-warm `ui/composite_warmer.py` + pre-warm indicator so the
  8K per-tick flatten no longer blocks the GUI thread). **D4 deferred to Phase 12** as
  **FU-P5-PERF** (further budget-tuning under the render-perf epic); Article VI budget never relaxed.

**Verdict: PASS — cleared for commit.**
