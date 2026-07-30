# Tasks — Phase 1: Core Engine (S12 remediation slice)

| Field | Value |
| --- | --- |
| Feature | `phase-1-core-engine` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-02 |
| Derived from | `specs/phase-1-core-engine/plan.md` §6–§7 |
| Governed by | `constitution.md` (Articles I, II, III, IV, VIII, X) |
| Scope | The remediation slice only. Shipped Phase-1 logic/data behaviour is frozen (retroactive); these tasks centralise tuning constants and standardise two consistency points **without changing observable behaviour**. |

Status legend: `todo` · `doing` · `done`.
Each task: **id · owner · target file(s) · dependency · REQ/acceptance link · status.**

The C1 gate (`sdd-analyze`, T8) is **closed** and runs ONLY after T1–T7 are implemented
and re-validated. Nothing here dispatches implement past a red gate (Article VIII).

---

## Ordered tasks

### T1 — Add tuning constants to `logic/constants.py`
- **Owner:** AGT-03 (Python Dev / logic)
- **Target:** `pixelart_creator/logic/constants.py`
- **Depends on:** — (root)
- **Do:** Add three named tuning values, each with a source-citation comment:
  `MAX_PALETTE_SIZE = 256` (8-bit index-space cap; S12-1),
  `DEFAULT_FRAME_DURATION_MS = 100` (default animation timing; S12-2),
  `PROJECT_ZLIB_LEVEL = 9` (`.pixproj` pixel compression level; S12-6). Keep
  `constants.py` a **leaf** (no intra-package imports) so no cycle is introduced.
- **REQ/acceptance:** REQ-P1-LOGIC-012 (S12, Article II).
- **Status:** todo

### T2 — Reference `MAX_PALETTE_SIZE` from constants in `palette.py`
- **Owner:** AGT-03
- **Target:** `pixelart_creator/logic/palette.py` (lines 16, 70–71)
- **Depends on:** T1
- **Do:** Replace the local `MAX_PALETTE_SIZE = 256` with
  `from pixelart_creator.logic.constants import MAX_PALETTE_SIZE` and **re-export** the
  name (keep `MAX_PALETTE_SIZE` bound at module level) so `project_io`'s existing
  `from ...palette import MAX_PALETTE_SIZE` keeps working. No behaviour change.
- **REQ/acceptance:** REQ-P1-LOGIC-005, REQ-P1-LOGIC-012 (SC-L005-11 full-palette-rejects-append must still pass).
- **Status:** todo

### T3 — Reference `DEFAULT_FRAME_DURATION_MS` from constants in `document.py`
- **Owner:** AGT-03
- **Target:** `pixelart_creator/logic/document.py` (lines 17, 70, 140)
- **Depends on:** T1
- **Do:** Replace the local `DEFAULT_FRAME_DURATION_MS = 100` with
  `from pixelart_creator.logic.constants import DEFAULT_FRAME_DURATION_MS` and re-export
  the name (default-arg call sites unchanged). No behaviour change.
- **REQ/acceptance:** REQ-P1-LOGIC-010, REQ-P1-LOGIC-012 (SC-L010-4 / SC-L010-9 must still pass).
- **Status:** todo

### T4 — Dedupe + single-source constants in `data/project_io.py`
- **Owner:** AGT-03
- **Target:** `pixelart_creator/data/project_io.py` (line 44 zlib; line 204 duration)
- **Depends on:** T1, T3
- **Do:** (a) Replace inlined `zlib.compress(raw, 9)` with `PROJECT_ZLIB_LEVEL`
  (import from `logic.constants`). (b) Replace inlined `fdata.get("duration_ms", 100)`
  with `DEFAULT_FRAME_DURATION_MS` (import from `logic.constants` or via `logic.document`
  re-export). On-disk `.pixproj` contract is byte-identical; values are now single-sourced.
- **REQ/acceptance:** REQ-P1-DATA-001, REQ-P1-LOGIC-012 (SC-D001-1/-12 round-trip & defaults must still pass).
- **Status:** todo

### T5 — Correct the `compactor.py` header (interface-truth fix)
- **Owner:** AGT-03
- **Target:** `pixelart_creator/logic/compactor.py` (header lines 18–19)
- **Depends on:** — (independent; may run parallel to T1–T4)
- **Do:** The header falsely claims atlas bounds "default MAX_CANVAS_WIDTH/HEIGHT from
  logic.constants when available". `compact()` requires **explicit** `max_width`/
  `max_height` and imports no constants. Minimal correct fix: **rewrite the header** to
  state the real explicit-args contract (do NOT add a constants import/default — that
  would change the tested signature/behaviour). No code/behaviour change.
- **REQ/acceptance:** REQ-P1-LOGIC-011 (all SC-L011-* must still pass; docstring/interface consistency, Article III §4).
- **Status:** todo

### T6 — Standardise `CompactionError` base class
- **Owner:** AGT-03
- **Target:** `pixelart_creator/logic/compactor.py` (class `CompactionError`, lines 52–57)
- **Depends on:** — (independent; may run parallel to T1–T5)
- **Do:** Change `class CompactionError(Exception)` → `class CompactionError(ValueError)`
  to match the common domain-exception base used by `ColorError`, `PaletteError`,
  `PixelBufferError`, `DocumentError`, `ProjectIOError`. Preserve the `__init__` and the
  stable `reason` token. Supersedes the CL-8 "intentional inconsistency" note.
- **REQ/acceptance:** REQ-P1-LOGIC-011 (CL-8 consistency; SC-L011-6/-7/-8 reason-token behaviour unchanged).
- **Status:** todo

### T7 — Adjust/extend tests + re-run coverage gate
- **Owner:** AGT-04 (Python Tester)
- **Target:** `tests/logic/test_palette.py`, `tests/logic/test_document.py`,
  `tests/data/test_project_io.py`, `tests/logic/test_compactor.py`
- **Depends on:** T2, T3, T4, T5, T6
- **Do:** Confirm existing behaviour tests still pass against the centralised constants
  (imports resolve; no magic-number regression). Add a regression assertion that
  `CompactionError` is a `ValueError` subclass (T6) and that
  `constants.MAX_PALETTE_SIZE` / `DEFAULT_FRAME_DURATION_MS` / `PROJECT_ZLIB_LEVEL` are
  the single source used by palette/document/project_io. Re-run `coverage_gate`
  (≥90 % line / ≥80 % branch per package). **Invoke `python scripts/coverage_gate.py`** (P11).
- **REQ/acceptance:** Article IV (one test per criterion + regression per fix); NFR-5.
- **Status:** todo

### T8 — Re-validate gates, then run the analyze C1 gate
- **Owner:** AGT-01 (Architecture)
- **Target:** `specs/phase-1-core-engine/` (analyze report)
- **Depends on:** T7 (and, upstream, AGT-02's traceability update per plan §9)
- **Do:** (1) **Invoke `python scripts/check_layering.py` and
  `python scripts/check_cycles.py`** — both must exit 0 (Article I; Decision A1-D3).
  (2) Only then run **`sdd-analyze`** across constitution/spec/plan/tasks. Gate stays
  closed until zero unresolved cross-artifact findings (Article VIII; Decision A1-D2).
  Do NOT dispatch implement or ship past a red gate.
- **REQ/acceptance:** Article VIII (analyze gate), Article X (traceability), REQ-P1-LOGIC-013 (S11).
- **Status:** todo

---

## Dependency graph

```
T1 ─┬─> T2 ─┐
    ├─> T3 ─┼─> T4 ─┐
    │       │       ├─> T7 ─> T8
T5 ─────────┼───────┤
T6 ─────────┴───────┘
```

Parallelisable set after T1: {T2, T3}; independent of T1: {T5, T6}. T4 needs T1+T3.
T7 needs all code tasks. T8 is the final gate (also awaits AGT-02's traceability edit,
plan §9) and is the ONLY task that runs `sdd-analyze`.

## Hand-offs (not tasks in this slice)

- **AGT-02:** apply the traceability deltas from plan §9 (REQ-P1-LOGIC-003/-004 Phase-1
  consumption traces; CL-8 resolution note) before T8's analyze. AGT-01 flags; AGT-02 owns.
- **AGT-08:** ADR-0001 (`docs/adr/0001-*.md`) records the tuning-vs-intrinsic boundary
  governing T1–T6 exemptions; already authored by AGT-01, filed under AGT-08's docs path.
- **AGT-09:** commit the slice as `refactor(logic,data): centralise S12 tuning constants`
  with REQ-P1-LOGIC-012 (+ REQ-P1-LOGIC-011 for T5/T6), gate-green (Article IX).
