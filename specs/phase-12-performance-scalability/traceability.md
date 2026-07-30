# Traceability matrix — Phase 12: Performance & Scalability

REQ ↔ dossier S-id / constitution article / FU item ↔ acceptance scenario ↔ **landed test**. Proves every
requirement is specified, has an acceptance scenario, and names the test or gate that covers it
(grounded measure-first in `docs/perf/phase12-baseline.md`, HEAD `f73b1a5`). **8 of 9 REQs are
`IMPLEMENTED`**; the 9th, REQ-P12-UI-002, is a declared **OPTIONAL/LOW** item that was **NOT ADOPTED**.

**T12-X01 editorial reconciliation (2026-07-30).** This matrix previously read *"↔ (future) test"*,
*"Tests are authored later by AGT-04 / AGT-06 / AGT-08 / AGT-01+AGT-02"* and *"All 9 REQs are `DRAFTED`"*
— for a phase whose tests and CI gates had already landed. Following the Phase-13 precedent (T13-X01),
the **Test** column now names the **actual landed test files and CI gates**, and the header no longer
claims the tests are future work. One cell was not merely stale but **unresolvable**:
`REQ-P12-LOGIC-004` cited `test_viewport_recomposite_perf` + `_byte_exact`, and **neither name resolves to a
test file that exists**. It is replaced below with the tests that actually cover the requirement. **Every
path in the Test column was verified to exist**, and both perf gates were verified wired in
`.github/workflows/ci.yml` — **cited by CI step name, not by line number** (see the M-8 correction below).

**M-9 correction (2026-07-30) — the provenance claim above was wrong.** The sentence previously read:
*"`REQ-P12-LOGIC-004` cited `test_viewport_recomposite_perf` + `_byte_exact`, and **neither name exists
anywhere in the repository** — the string `test_viewport_recomposite_perf` occurs only in this file and
in `tasks.md`."* The string `test_viewport_recomposite_perf` **occurs only in this file** — a search of the
repository returns hits nowhere else, including `tasks.md`, which **exists and has never contained it**
(verified against the committed history, and re-verified in the working tree: the only matches are the
three occurrences in this matrix). What `tasks.md` does contain is the **different** stem
`tests/logic/test_viewport_recomposite_byte_exact.py` (T12-B-03, still `todo`, and likewise not on disk) —
the probable origin of the `_byte_exact` half of the old cell, and of the mistaken "and in `tasks.md`"
attribution. **The substantive finding is unchanged and stands:** the cited test name
`test_viewport_recomposite_perf` resolved to nothing anywhere in the repository.

**M-8 correction (2026-07-30) — this matrix cited CI line numbers that had already moved.** It previously
read *"both perf gates were verified wired in `.github/workflows/ci.yml` (`--full-frame` at L371,
`--viewport-recomposite` at L387)"*, and each affected row likewise cited *"wired at
`.github/workflows/ci.yml` L371"* / *"L387"*. Those line numbers were captured before a concurrent edit to
that workflow and were carried across unchecked; the two `run:` lines now sit at L425 and L441. **They are
not re-cited by number.** Every reference below now names the **CI step**, which survives edits to the file:
- `--full-frame` → `.github/workflows/ci.yml`, job `quality-gate`, step
  **"Full-frame flatten perf gate (Slice-A, realistic-content ceiling)"**
- `--viewport-recomposite` → `.github/workflows/ci.yml`, job `quality-gate`, step
  **"Viewport-recomposite commit perf gate (Slice-B, opacity-drag)"**

Both step names were verified to appear verbatim in the workflow, under the `quality-gate` job, each
guarded by `if: runner.os == 'Linux'`.

Evidence basis: HIGH = an explicit `REQ-P12-…` string appears in the test file itself (exhaustive scan
of `main/tests/**/*.py`, expanding the shorthand suffix form `REQ-P12-LOGIC-001/-002`) or the gate is
present in `ci.yml`. MEDIUM = artifact/tool presence only, no executable trace located. Test *bodies*
were not executed as part of this reconciliation.

| REQ-ID | Layer | Slice | Traces (S-id / article / FU) | Acceptance scenario | Test | Status |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-P12-LOGIC-001 | logic | A | S1, S12, Art VI (batch), Art II, ADR-0033, baseline §2#1/#1b/§3/§6, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-001-1/-2/-3 (realistic-content perf gate + off-thread pathological guarantee) | AGT-10 `perf_profile --full-frame` realistic gate + AGT-04 `tests/logic/test_blend_fullframe.py`; pathological off-thread via `pixelart_creator/ui/composite_warmer.py` (accepted cold-cost, ungated). Gate wired in `.github/workflows/ci.yml`, job `quality-gate`, step **"Full-frame flatten perf gate (Slice-A, realistic-content ceiling)"** (`python scripts/perf_profile.py --full-frame --content realistic --layers 8 --frames 3`); REQ-ID at `test_blend_fullframe.py` L19/L273 | IMPLEMENTED (HIGH) |
| REQ-P12-LOGIC-002 | logic | A | P2, Art I, Art IV, ADR-0005/0007, baseline §3, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-002-1/-2 | `tests/logic/test_blend_fullframe.py` (11 `REQ-P12-LOGIC-002` references, L5–L479) | IMPLEMENTED (HIGH) |
| REQ-P12-LOGIC-003 | logic | A | S12, Art VI §2, Art II, baseline §1/§6, FU-15, FU-P5-PERF | acceptance.md · SC-P12-LOGIC-003-1 | `scripts/perf_profile.py --full-frame` CI gate, wired in `.github/workflows/ci.yml`, job `quality-gate`, step **"Full-frame flatten perf gate (Slice-A, realistic-content ceiling)"** | IMPLEMENTED (HIGH) |
| REQ-P12-LOGIC-004 | logic | B | S1, S12, Art VI (batch), Art I, Art II, baseline §2#2/§3/§6, FU-16 (b) | acceptance.md · SC-P12-LOGIC-004-1/-2 | `tests/logic/test_blend_range.py` (byte-exact legs; 5 `REQ-P12-LOGIC-004` references at L11/29/181/233/569) + `tests/ui/test_opacity_drag.py` (commit byte-exactness, L161/219/227) + `scripts/perf_profile.py --viewport-recomposite` CI gate, wired in `.github/workflows/ci.yml`, job `quality-gate`, step **"Viewport-recomposite commit perf gate (Slice-B, opacity-drag)"**. **Replaces the unresolvable `test_viewport_recomposite_perf` + `_byte_exact` cell — neither name resolves to an existing test file (T12-X01; provenance corrected by M-9 in the header).** | IMPLEMENTED (HIGH) |
| REQ-P12-UI-001 | ui | B | REQ-P12-LOGIC-004, Art VI §1 (per-frame preview; responsiveness/no-freeze — holds 16 ms up to ~1080–1280², graceful ~25–40 fps at ~1920²; budget DEFINITION unchanged), Art V, S1, baseline §3 + Slice-B RE-PROFILE (AGT-10), FU-16 (b), Slice-A portability decision | acceptance.md · SC-P12-UI-001-1/-2 | `tests/ui/test_opacity_drag.py` — responsiveness-by-mechanism (downsampled preview + `OPACITY_PREVIEW_MAX_PX`=16384) + no-freeze (both themes), plus the `scripts/perf_profile.py --viewport-recomposite` commit gate (byte-exact per REQ-P12-LOGIC-004, `ci.yml` job `quality-gate`, step **"Viewport-recomposite commit perf gate (Slice-B, opacity-drag)"**); 4 `REQ-P12-UI-001` references at L5/9/288/456 | IMPLEMENTED (HIGH) |
| REQ-P12-LOGIC-005 | logic | B | S12, Art VI §2, Art II, baseline §1/§6, FU-15, FU-16 (b) | acceptance.md · SC-P12-LOGIC-005-1 | `scripts/perf_profile.py --viewport-recomposite` CI gate, wired in `.github/workflows/ci.yml`, job `quality-gate`, step **"Viewport-recomposite commit perf gate (Slice-B, opacity-drag)"** | IMPLEMENTED (HIGH) |
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
