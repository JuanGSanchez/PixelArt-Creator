# Analyze Report (C1) — Phase 9: Visual Aids & UX

| Field | Value |
| --- | --- |
| Feature | `phase-9-visual-aids` |
| Author | Claude (AGT-01, Architecture) via `sdd-analyze` |
| Date | 2026-07-04 |
| Artifacts | `constitution.md`, `specs/phase-9-visual-aids/spec.md`, `plan.md`, `tasks.md` (all present) |
| Gate | **C1 — cross-artifact consistency + coverage** (Article VIII; defaults closed) |
| **Verdict** | **PASS** — 0 unresolved findings; **0 uncovered REQ-IDs** (28/28) |

---

## 1. Gate (step 1)

All four artifacts exist and parse: `constitution.md` (repo root), `spec.md`, `plan.md`, `tasks.md`
(`specs/phase-9-visual-aids/`). Gate open to analysis. (`sdd-analyze` AN-E1/AN-E2 not triggered.)

## 2. spec ↔ constitution compliance (step 2)

| Article | Spec/plan/tasks posture | Verdict |
| --- | --- | --- |
| I (three-layer) | Geometry engine pure `logic/` (`grids`/`guides`/`preview`/`timelapse`, zero Qt) + Qt-free `data/` serialisers; UI-only overlays/preview/board/views/timelapse; `grids`/`guides`/`preview` pure leaves over `constants`, `timelapse` downward-only, **no `logic → data`** (plan §4.4). **No `ui/commands.py` change** — aids non-destructive. | ✅ |
| II (numerics) | 10 new constants in `logic/constants.py`, names distinct from every shipped constant; `GuideOrientation` + timelapse `schema_version` intrinsic-local (plan §8, ADR-0001/BF-2). | ✅ |
| III (quality) | Black/isort/flake8/mypy-strict for `logic/`+`data/`; typed frozen contracts (plan §5). | ✅ |
| IV (testing) | Every REQ + the 10 `[GEO]` geometry contracts → ≥1 headless pytest/Hypothesis or pytest-qt (both themes) task (tasks 9A–9H). Coverage ≥90/80. | ✅ |
| V (UX) | REQ-P9-UI-012/-013/-014 blocking gates (TG-04/05/06); role-based overlay/guide colours legible over artwork in both themes. | ✅ |
| **VI (perf) — APPLIES** | REQ-P9-UI-011 binds the **16 ms `FRAME_BUDGET_MS`** to overlays + multi-view (per-frame render loop, unlike batch Phases 7–8); cache-backed overlays + dirty-rect views; strategy = AGT-10 (DEP-3, plan §7). **Budget never relaxed.** | ✅ |
| VII (security) | Timelapse + reference-board load defensive, validated, **`eval`-free** (IO-3; `TimelapseIOError`/`ReferenceBoardIOError`); `.pixproj` v5 defensive; bounded numerics (10 constants); portable paths (`path_portability_check`). | ✅ |
| VIII (SDD gate) | This report is the pre-implement gate; dispatch held until PASS. | ✅ |
| X (traceability) | Every REQ traces to an S-id / F / forward primitive (DOC-1, PB-1, HIS-1, CO-4, MC-4, IO-3). The 2 allocated DATA REQs follow the `REQ-P<phase>-<LAYER>-<NNN>` scheme (LAYER=DATA, Article X §1) and each traces to ≥1 scenario + test (Article X §2). | ✅ |
| XI (extensibility) | Timelapse video encoding (Phase-7 handoff), hosted reference library / cloud sync (Phase 10), staggered iso, AI perspective inference deferred as clean seams. | ✅ |

No constitution conflict (AN-D2 Branch A not triggered).

## 3. plan ↔ spec fidelity (step 2) — no drift

- The six spec HOW-deferrals (DEP-2a–f) are each ruled: isometric default (ADR-0023 §1, PL9-D4);
  perspective model (ADR-0023 §2, PL9-D5); guides/rulers (ADR-0023 §3, PL9-D6); real-size DPI
  (ADR-0023 §4, PL9-D7); timelapse strategy + storage/encoding (ADR-0024 §2, PL9-D9); reference-board
  model + persistence (ADR-0024 §3 / ADR-0025 §3, PL9-D10).
- **BF-3 (document PPI)** resolved: first-class `Document.ppi` field + `.pixproj` v5 defensive persistence,
  v1–v4 unchanged (ADR-0025 §1, PL9-D8). Spec flagged it as not-acceptance-changing; plan agrees.
- **DEP-3 (16 ms render NFR)** routed to AGT-10/AGT-05 (plan §7, PL9-D13); **Article VI applies this phase**
  (per-frame render loop) — consistent with spec §5 / CL-13.
- **DEP-4 (`REQ-P9-DATA-*` prefix)** resolved: plan **ALLOCATES** the prefix — `REQ-P9-DATA-001`
  (timelapse) + `REQ-P9-DATA-002` (reference board), each formalising the persistence clause **already
  fixed** under REQ-P9-LOGIC-010 / REQ-P9-UI-006 (ADR-0024 §4, PL9-D11). This **diverges** from Phase 8's
  fold (ADR-0022 §4) — justified because Phase 9 has **two distinct serialisers/formats** (the spec,
  PREFIX-NOTE, and CL-15 all note this makes a DATA prefix more clearly warranted than Phase 8's single
  one). **Not acceptance-changing:** each DATA REQ carries the spec's fixed contract verbatim; coverage
  arithmetic 26 base + 2 formalised = 28 (see §4). Consistent — a pre-authorised placement decision, not
  drift.
- **BF-1** (10 constants) placed (plan §8); **BF-2** (`GuideOrientation`/`schema_version` intrinsic-local)
  honoured.
- The plan introduces **no** acceptance not in the spec, and drops **none**. Every observable contract
  (invertible iso transform; nearest-vertex/nearest-guide-within-tolerance snap; `f(PPI, DPI)` scale;
  live mirror; views in sync; reproducible timelapse; defensive `eval`-free persistence) is preserved
  verbatim from the spec's framing.

## 4. tasks ↔ plan completeness + REQ coverage (step 3)

**28/28 REQ-IDs covered** (12 LOGIC + 14 UI + **2 DATA**) — each appears in the plan module map **and** in
≥1 implementation task **and** ≥1 test/verify task. **0 uncovered.**

| REQ | Plan module | Impl task | Test/verify task |
| --- | --- | --- | --- |
| LOGIC-001 [GEO] | grids | T9A-02 | T9A-06 (SC-L001-1) |
| LOGIC-002 [GEO] | grids | T9A-03 | T9A-06 (SC-L002-1) |
| LOGIC-003 [GEO] | grids | T9A-04 | T9A-06 (SC-L003-1) |
| LOGIC-004 [GEO] | grids | T9A-05 | T9A-06 (SC-L004-1) |
| LOGIC-005 [GEO] | guides | T9B-01 | T9B-05 (SC-L005-1) |
| LOGIC-006 [GEO] | guides | T9B-02 | T9B-05 (SC-L006-1) |
| LOGIC-007 [GEO] | preview + document.ppi + project_io v5 | T9B-03, T9B-04, T9E-03 | T9B-05, T9E-04 (SC-L007-1) |
| LOGIC-008 [GEO] | grids/guides/preview/timelapse | T9A-02..T9D-01 | T9A-06, T9D-02 (SC-L008-1) |
| LOGIC-009 [GEO] | all geometry | T9A-03/05, T9B-02/03, T9C-02 | T9A-06, T9B-05, T9C-03, T9D-02 (SC-L009-1) |
| LOGIC-010 [GEO] | timelapse | T9C-01/02 | T9C-03, T9E-04 (SC-L010-1) |
| LOGIC-011 | constants + all | T9A-01 + bound checks | T9A-06/T9B-05/T9C-03 (SC-L011-1) |
| LOGIC-012 | document (shared) | T9B-04 | T9D-02 (SC-L012-1) |
| UI-001 | real_size_preview_window | T9F-01 | T9F-05 (SC-UI-001-1) |
| UI-002 | real_size_preview_window | T9F-01 | T9F-05 (SC-UI-002-1) |
| UI-003 | guides_rulers_overlay | T9F-02 | T9F-05 (SC-UI-003-1) |
| UI-004 | iso_grid_overlay | T9F-03 | T9F-05 (SC-UI-004-1) |
| UI-005 | perspective_grid_overlay | T9F-04 | T9F-05 (SC-UI-005-1) |
| UI-006 | reference_board | T9G-01 | T9G-05, T9E-04 (SC-UI-006-1) |
| UI-007 | multi_view | T9G-02 | T9G-05 (SC-UI-007-1) |
| UI-008 | multi_view | T9G-02 | T9G-05 (SC-UI-008-1) |
| UI-009 | timelapse_controls | T9G-03 | T9G-05 (SC-UI-009-1) |
| UI-010 | main_window (wiring) | T9G-04 | T9G-05 (SC-UI-010-1) |
| UI-011 (NFR) | overlays + multi_view | T9H-01/02 | T9H-03 (SC-UI-011-1) |
| UI-012 (NFR) | (all panels) | T9F-01..T9G-03 | TG-04 (SC-UI-012-1) |
| UI-013 (NFR) | (all panels) | T9F/T9G | TG-05 (SC-UI-013-1) |
| UI-014 (NFR) | (all panels) | T9F/T9G | TG-06 (SC-UI-014-1) |
| **DATA-001** | data/timelapse_io | T9E-01 | T9E-04 (SC-L010-1) |
| **DATA-002** | data/reference_board_io | T9E-02 | T9E-04 (SC-UI-006-1) |

**Orphan tasks (no REQ):** T9D-01 (layering scripts, Article I), TG-01 (STRUCTURE, Article I), TG-02
(this gate, Article VIII), TG-03 (DATA-prefix allocation in traceability, DEP-4/Article X), TG-07
(CHANGELOG, Article IX), TG-08 (checklist, Article IV/V/VI) — each cites its governing article/gate and is
a legitimate cross-cutting task, **not** a stray orphan.

## 5. Conflicts (step 4) — none unresolved

- **Determinism (LOGIC-009) vs reproducible timelapse (LOGIC-010):** resolved — timelapse derives frames
  from the deterministic HIS-1 history via document render (no wall-clock/random/locale), so replay is
  reproducible by construction (plan §3, ADR-0024 §2). No conflict.
- **`DEFAULT_DOCUMENT_PPI` / new constants vs shipped constants:** all 10 names distinct (Article II/BF-1);
  `MAX_GUIDES`/`MAX_REFERENCE_IMAGES`=256 parallel the shipped 256-caps but under distinct names. No
  conflict.
- **DEP-4 DATA-prefix allocation vs the base 26-REQ spec count:** resolved — the 2 DATA REQs formalise
  persistence contracts already fixed under REQ-P9-LOGIC-010 / REQ-P9-UI-006 (spec PREFIX-NOTE, CL-15
  pre-authorise the allocation at plan time as *not acceptance-changing*); coverage preserved (26 base + 2
  formalised = 28, 0 uncovered); traceability.md updated to carry them. Not drift.
- **Article VI 16 ms budget vs overlays + N 8K views:** resolved as a real constraint routed to AGT-10
  (cache-backed overlays + dirty-rect/tile-cull views, plan §7, DEP-3); budget never relaxed. No conflict.
- **The 10 `[GEO]` scenarios (SC-L001..010) in spec §11** match the plan's tested-geometry invariant (§2)
  and each has a dedicated geometry/property test (T9A-06, T9B-05, T9C-03, T9D-02). Consistent.

## 6. Deterministic checks (run separately by AGT-01, plan §11)

- `python scripts/check_layering.py` → exit **0** (clean, 47 modules) — baseline 2026-07-04.
- `python scripts/check_cycles.py` → exit **0** (no cycles, 108 modules) — baseline 2026-07-04.
- Planned Phase-9 edges are acyclic by construction (plan §4.4); AGT-03 re-runs both when 9A–9E land
  (T9D-01).

## 7. Verdict (step 5)

**PASS (C1).** Unresolved-findings list is **empty**; **0 uncovered REQ-IDs** (28/28). The implement gate
is **open** for Phase 9 — the orchestrator may proceed to dispatch Slices 9A→9H (tests authored by
AGT-04/AGT-06, `pending`). The 10 `[GEO]` tested-geometry contracts (the ROADMAP Phase-9 backbone) are each
bound to a dedicated headless test and must be green before ship (TG-08 `sdd-checklist`); the real-size
DPR risk (ADR-0023 §4) and the 16 ms overlay + multi-view budget (REQ-P9-UI-011, AGT-10 DEP-3) are the
two ship-gating watch items.
</content>
