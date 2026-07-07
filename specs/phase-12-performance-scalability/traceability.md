# Traceability matrix — Phase 12: Performance & Scalability

REQ ↔ dossier S-id / constitution article / FU item ↔ acceptance scenario ↔ (future) test. Proves every
requirement is specified and has an acceptance scenario. **All 9 REQs are `DRAFTED`** (grounded
measure-first in `docs/perf/phase12-baseline.md`, HEAD `f73b1a5`); REQ-P12-UI-002 is **OPTIONAL/LOW**.
Tests are authored later by AGT-04 (logic regression + perf probe) / AGT-06 (UI + acceptance) / AGT-08
(docstrings) / AGT-01+AGT-02 (Slice-F artifact edits).

| REQ-ID | Layer | Slice | Traces (S-id / article / FU) | Acceptance scenario | Test (future) | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P12-LOGIC-001 | logic | A | S1, S12, Art VI (batch), Art II, ADR-0033, baseline §2#1/#1b/§3/§6, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-001-1/-2/-3 (realistic-content perf gate + off-thread pathological guarantee) | AGT-10 `perf_profile --full-frame` realistic gate + AGT-04 `tests/logic/test_blend_fullframe.py`; pathological off-thread via `composite_warmer` (accepted cold-cost, ungated) | DRAFTED |
| REQ-P12-LOGIC-002 | logic | A | P2, Art I, Art IV, ADR-0005/0007, baseline §3, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-002-1/-2 | `tests/logic/test_blend_fullframe.py` | DRAFTED |
| REQ-P12-LOGIC-003 | logic | A | S12, Art VI §2, Art II, baseline §1/§6, FU-15, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-003-1 | `perf_profile --full-frame` (CI gate) | DRAFTED |
| REQ-P12-LOGIC-004 | logic | B | S1, S12, Art VI (batch), Art I, Art II, baseline §2#2/§3/§6, FU-16 (b) | acceptance.md · SC-P12-LOGIC-004-1/-2 | `test_viewport_recomposite_perf` + `_byte_exact` | DRAFTED |
| REQ-P12-UI-001 | ui | B | REQ-P12-LOGIC-004, Art VI §1 (per-frame preview; responsiveness/no-freeze — holds 16 ms up to ~1080–1280², graceful ~25–40 fps at ~1920²; budget DEFINITION unchanged), Art V, S1, baseline §3 + Slice-B RE-PROFILE (AGT-10), FU-16 (b), Slice-A portability decision | acceptance.md · SC-P12-UI-001-1/-2 | `tests/ui/test_opacity_drag.py` — responsiveness-by-mechanism (downsampled preview + `OPACITY_PREVIEW_MAX_PX`=16384) + no-freeze (both themes), plus the `perf_profile --viewport-recomposite` commit gate (byte-exact per REQ-P12-LOGIC-004) | DRAFTED |
| REQ-P12-LOGIC-005 | logic | B | S12, Art VI §2, Art II, baseline §1/§6, FU-15, FU-16 (b) | acceptance.md · SC-P12-LOGIC-005-1 | `perf_profile --composite` viewport scenario (CI gate) | DRAFTED |
| REQ-P12-LOGIC-006 | logic | F | Art III, §6.7, FU-4 | acceptance.md · SC-P12-LOGIC-006-1 | `pydocstyle` (logic/ docstrings) | DRAFTED |
| REQ-P12-LOGIC-007 | logic | F | Art X §2, Art VIII, S16, FU-2, FU-17, FU-16 (collision) | acceptance.md · SC-P12-LOGIC-007-1/-2/-3 | `sdd-analyze` (cross-artifact consistency) | DRAFTED |
| REQ-P12-UI-002 | ui | (opt) | Art VI (batch), Art V, baseline §3, FU-18 | acceptance.md · SC-P12-UI-002-1/-2 | `test_analytics_offthread` (if adopted) | DRAFTED (OPTIONAL/LOW) |

## Descoped items — recorded for traceability (verified, NO action; §2b of spec)

| FU item | Measured (f73b1a5) | Verdict | Optional (non-blocking) follow-up |
| --- | --- | --- | --- |
| FU-8 (checker background) | 10.5 ms vs 16 ms budget | IN BUDGET — descoped | loose tiling regression gate ≈40-48 ms |
| FU-18 (palette analytics) | 281 ms synthetic worst / <100 ms realistic; lazy+debounced | descoped (borderline) | OPTIONAL REQ-P12-UI-002 (off-thread) |
| FU-P9-OVERLAY-8K (iso overlay) | 144 ms only at literal 8K viewport, CPU-raster, cache-miss-only; sub-32px LOD-fixed; GL on desktop | descoped (borderline) | line-budget LOD + loose raster-fallback gate |

## Coverage summary

- **REQs total:** 9 — LOGIC 7, UI 2, DATA 0 (no new persistence; output byte-exactness is a correctness
  constraint, not a format).
- **Covered (acceptance + Gherkin + trace):** 9 / 9 — 0 pending, 0 blocked, 0 SUSPENDED.
- **Scoped for optimisation work:** FU-P5-PERF (Slice A — REQ-P12-LOGIC-001/-002/-003), FU-16 (b)
  (Slice B — REQ-P12-LOGIC-004/-005, REQ-P12-UI-001).
- **Documented as descoped ("verified, no action"):** FU-8, FU-18 (core), FU-P9-OVERLAY-8K (§2b).
- **Doc-hygiene reconciled:** FU-2, FU-17, FU-16 label collision, FU-4 (Slice F — REQ-P12-LOGIC-006/-007).
- **Optional / LOW (flagged, deferrable):** REQ-P12-UI-002 (FU-18 off-thread).
- **Budget integrity:** no REQ relaxes the `FRAME_BUDGET_MS = 16` DEFINITION (Article VI §2 / VIII §3).
  Batch paths use **loose named ceilings** (`COMPOSITE_FULL_CEILING_MS`, `VIEWPORT_RECOMPOSITE_CEILING_MS`);
  the only per-frame path (opacity-drag preview, REQ-P12-UI-001) is a **responsiveness/no-freeze** path —
  it eliminates the old multi-second freeze and **holds** 16 ms up to ~1080–1280² viewports, then
  **degrades gracefully** to ~25–40 fps at ~1920² (float64 re-blend floor + area-scaled upsample; a hard
  16 ms wall everywhere would need a dependency/GPU, declined for portability per the Slice-A decision;
  `OPACITY_PREVIEW_MAX_PX`=16384 maximises the in-budget range, low-zoom Slice-A handoff beyond it). The
  byte-exact commit (REQ-P12-LOGIC-004) is **unchanged**.
- **Every REQ** traces to a dossier S-id / article + a FU item + ≥ 1 Gherkin scenario. **No REQ is
  untraced or uncovered.**
- **Gate:** the matrix is complete — `sdd-analyze` / `sdd-plan` (AGT-01) are **UNBLOCKED**.
