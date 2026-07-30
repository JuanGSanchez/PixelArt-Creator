# Analyze Report (C1 gate) — Phase 6: Tilemap & Level Design

| Field | Value |
| --- | --- |
| Feature | `phase-6-tilemap` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Artifacts | `constitution.md`, `specs/phase-6-tilemap/spec.md`, `plan.md`, `tasks.md` (all present) |
| Scripts | `check_layering.py` exit **0** (clean, 32 modules); `check_cycles.py` exit **0** (no cycles, 78 modules) — run at plan time 2026-07-03 |
| Verdict | **PASS (C1)** — gate OPEN for implement (AN-D1 Branch A); zero unresolved cross-artifact findings, 0 uncovered REQ |

---

## 1. Gate precondition

All four artifacts exist and parse (AN-E1/E2 clear). Constitution governs; spec is `specify+clarify`
COMPLETE (35 REQ: 14 LOGIC + 17 UI + 4 DATA, 16 clarifications resolved, 0 open, no SUSPEND); plan +
tasks + ADR-0013/0014/0015/0016 authored this session.

## 2. spec ↔ constitution compliance

| Article | Check | Result |
| --- | --- | --- |
| I (three-layer) | `tileset.py`/`tilemap.py`/`autotile.py` Qt-free; `data/tiled_io.py` + `project_io.py` Qt-free; all tilemap widgets in `ui/`; sole outside-`ui/` Qt file stays `ui/commands.py`; `document → tilemap → tileset`, `tilemap → autotile`/`blend` one-way; GID masks in `logic/tilemap` → no `logic → data` edge | PASS (plan §3.4; ADR-0015; scripts exit 0) |
| II (numerics) | 9 new tuning values in `constants.py`, **names distinct from `TILE_SIZE=64`** (BF-2); GID masks / Blob-47 weights / Tiled version strings intrinsic-local (ADR-0001) | PASS (plan §8; ADR-0015) |
| IV (testing) | one test per criterion, headless, both themes for UI; Hypothesis for determinism (slice, auto-tile) | PASS (tasks T6A-05, T6B-06, T6C-03, T6D-06, T6E-04, T6F-06, T6G-03) |
| V (UX) | a11y + both themes + tr() as blocking gates | PASS (UI-015/016/017 → TG-03/TG-04/TG-05) |
| VI (perf) | 8K tilemap render/stamp/pan ≤ 16 ms; viewport tile-culling + dirty-rect; never cull resident data; never relax | PASS (UI-014 → T6F-05 impl + T6F-07 profile; ADR-0015 §Render/plan §7) |
| VII (security) | defensive validated Tiled/native JSON load; tile/layer/coord bounds; invalid-slice guards; no eval/exec; portable paths | PASS (ADR-0014/0016; T6D-04/05, T6A-02 guards; T6D-07 `path_portability_check`) |
| VIII (SDD gate) | this analyze | PASS (§6) |
| X (traceability) | every REQ traces to S-id/F/inherited primitive + ≥1 scenario | PASS (`traceability.md`, 35/35 covered) |
| XI (extensibility) | animated tiles / object-collision layers / non-orthogonal orientations / corner-Wang deferred without weakening any article | PASS (spec §6; ADR-0013 corner-Wang hook; plan §10) |

No spec decision conflicts with an article (AN-D2 not triggered).

## 3. plan ↔ spec fidelity (no drift)

- Every spec capability is realised in the plan: tileset slicing + id↔region + source-tile edit
  (§2/§4), linked instances + layers + infinite/sparse + render (§2/§5), auto-tiling
  deterministic/reversible (§2/§5, ADR-0013), Tiled JSON export/round-trip/defensive load (§6,
  ADR-0014), native `.pixproj` v4 (§6, ADR-0016), constants (§8), UI panels (§3.3).
- **DEP-1** (Researcher grounding) satisfied — `docs/research-phase-6-tilemap-20260703.md` landed;
  plan cites Topics 1–3 + confirmed Tiled 1.12.2 facts throughout; PL6-D1 → Branch B (no invention).
- **DEP-2** four HOW decisions **ruled**: (a) auto-tile family → **Blob-47** (ADR-0013); (b) Tiled
  JSON encoding set → **CSV emit + base64/gzip/zlib; reject zstd/`.tsx`; embedded emit + external
  `.tsj` import; verbatim passthrough** (ADR-0014); (c) infinite-map → **chunked-sparse now**
  (ADR-0015); (d) `.pixproj` → **v4** (ADR-0016). Consistent with REQ-P6-LOGIC-009/-010/-011,
  REQ-P6-DATA-001/-002/-003/-004, and CL-3/-5/-6/-7/-16.
- **DEP-3** (perf) **routed** to AGT-10: viewport tile-culling + dirty-rect on the `render_region`
  seam (plan §7, ADR-0015 §Render, task T6F-07); budget never relaxed (Article VI).
- BF-1 (tile draw method) left as an AGT-05 HOW; BF-2 (constant placement + `TILE_SIZE` distinctness)
  resolved (§8, ADR-0015). Interface contracts for `tileset.py` (§4), `tilemap.py`/`autotile.py` (§5),
  `tiled_io.py`/`project_io.py` v4 (§6) frozen before implementation, as directed.

No requirement is dropped, weakened, or contradicted by the plan.

## 4. tasks ↔ plan completeness / coverage

**Every REQ-ID (14 LOGIC + 17 UI + 4 DATA = 35) appears in the plan and in ≥1 impl + ≥1 test/verify
task.** Coverage matrix (impl → test):

- LOGIC-001/003/014 → T6A-02 → T6A-05; LOGIC-002 → T6A-03 → T6A-05; LOGIC-004 → T6A-04 → T6A-05.
- LOGIC-005/009 → T6B-01/02 → T6B-06; LOGIC-006/013 → T6B-05 → T6B-06; LOGIC-007 → T6B-03 → T6B-06;
  LOGIC-008/012 → T6B-04 (+T6D-01 attach) → T6B-06.
- LOGIC-010 → T6C-01 → T6C-03; LOGIC-011 → T6C-02 → T6C-03.
- UI-001 → T6E-01 → T6E-04; UI-002 → T6E-02 → T6E-04; UI-003 → T6E-03 → T6E-04.
- UI-004/010 → T6F-01 → T6F-06; UI-005/006/007 → T6F-02 → T6F-06; UI-008 → T6F-03 → T6F-06;
  UI-009 → T6F-04 → T6F-06; UI-013 → T6E-02/03 + T6F-02/03/04 → T6E-04/T6F-06; UI-014 → T6F-05 → T6F-07.
- UI-011 → T6G-01 → T6G-03; UI-012 → T6G-02 → T6G-03.
- UI-015 → TG-03 (`a11y-audit`); UI-016 → both-theme fixtures across T6E-04/T6F-06/T6G-03 + TG-04;
  UI-017 → TG-05 (`string_audit_check`).
- DATA-001 → T6D-02 → T6D-06; DATA-002 → T6D-03 → T6D-06; DATA-003 → T6D-04 → T6D-06; DATA-004 →
  T6D-05 → T6D-06.

**No uncovered REQ (0/35).** **No orphan implementation task:** the only non-REQ tasks are gate/process
tasks tied to articles (T6C-04/T6D-07 → Article I layering + Article VII portability; TG-01 → Article
I map; TG-02 → Article VIII; TG-06 → Article IX; TG-07 → Article IV/V/VI checklist) — intentional,
not orphans. Every task names one owner (TK-D1) and its target file(s); deterministic sub-steps name
their script (TK-D2: T6C-04/T6D-07 `check_layering`/`check_cycles`, T6D-07 `path_portability_check`,
TG-05 `string_audit_check`, T6F-07 `perf_profile`).

## 5. Cross-artifact observations (resolved, non-blocking)

- **O-1 (canonical cell layout matches Tiled).** The plan/ADR-0015 adopt Tiled 1.12.2's exact 32-bit
  GID masks as the *internal* cell layout (uint32), beyond the spec's model-neutral "gid + flip
  flags" (CL-3). Deliberate: it makes the model and the Tiled wire form one representation → lossless
  round-trip (REQ-P6-DATA-002). Additive, grounded (research §2.6/Topic 3), contradicts no REQ.
- **O-2 (`zstd` + external `.tsx` refused).** ADR-0014 refuses `zstd` layer compression and external
  `.tsx` (XML) tilesets on import (`ProjectIOError`), because both need new technology (S8). The spec
  requires a "valid Tiled map that round-trips losslessly" (REQ-P6-DATA-001/-002) and a defensive
  load that rejects rather than crashes (REQ-P6-DATA-003) — refusing an unsupported encoding *is* the
  defensive posture; our own CSV/base64+gzip/zlib output round-trips losslessly. No conflict; an
  explicit, documented scope boundary.
- **O-3 (full infinite shipped, not deferred).** ADR-0015 ships chunked-sparse infinite now rather
  than "fixed-size with a chunk-ready model." This *exceeds* the minimum by satisfying
  REQ-P6-LOGIC-009 directly; the ROADMAP "infinite maps" line and CL-6 support it; viewport-culled
  rendering (DEP-3) keeps it in budget. No spec conflict.
- **O-4 (verbatim passthrough for round-trip).** ADR-0014 preserves unknown Tiled fields verbatim
  (properties/wangsets/object layers/counters) to guarantee lossless reimport. The spec allows
  "concepts the platform does not model are out of scope, not silently corrupted" (REQ-P6-DATA-002);
  verbatim carry is the stronger, safer reading. Additive, no conflict.
- **O-5 (auto-tile bit-weight convention is ours).** The 8-neighbour bit weights (ADR-0013) are a
  documented implementation convention, not a standard (research §1.2/OD-2). Fixed + published in
  `autotile.py`; determinism asserted by SC-L010-1. No spec conflict (the spec fixes only the
  observable contract).

None of O-1..O-5 is an unresolved cross-artifact contradiction; all are additive, grounded, and
non-blocking.

## 6. Verdict

**PASS — C1 gate OPEN.** Zero unresolved findings; spec↔constitution compliant, plan↔spec faithful,
tasks↔plan complete (35/35 REQ covered, impl+test), layering + cycle scripts exit 0. All four DEP-2
HOW decisions are ruled by ADR-0013/0014/0015/0016; DEP-3 perf is routed to AGT-10 on the fixed
`render_region` seam; DEP-1 grounding is landed. Per Article VIII the orchestrator may proceed to
`implement` (Slice 6A first). The gate defaults closed; it is opened here only because the unresolved
list is empty.

## 7. Notes for implement dispatch

- **Slice order:** 6A (tileset) → 6B (tilemap model) → 6C (auto-tiling) → 6D (data) → 6E/6F/6G (UI),
  with T6C-04 + T6D-07 re-running `check_layering`/`check_cycles` after the logic + data edges land.
- **AGT-03/AGT-04** implement against the frozen contracts (plan §4/§5/§6); the reversible-command
  factories return an **unapplied** `history.Command` (Phase-4/5 precedent) so `ui/commands.py` stays
  a thin wrapper.
- **AGT-10** owns the 8K tilemap perf profile (T6F-07) on the `render_region` viewport-culling seam;
  an over-budget measurement yields an optimisation directive, never a budget relaxation.

## 8. FINAL architecture gate (post-implementation, AGT-01, 2026-07-03) — PASS

Re-run at ship time, after Phase-6 was fully built and all domain gates went green (logic+data 1386
tests; UI QA SHIP-READY after S2+S3 fixes; perf loop-back CLOSED ≤16 ms; i18n + docs green).

- **Scripts (actually run on the shipped tree):** `check_layering.py` → exit **0** (clean, **36
  modules**); `check_cycles.py` → exit **0** (no cycles, **87 modules**). Three-layer rule confirmed:
  `logic/{autotile,tileset,tilemap}` + `data/tiled_io` are **zero-Qt**; GID masks stay module-local in
  `logic/tilemap.py` (`FLIPPED_*`/`GID_MASK`), imported **downward** by `data/tiled_io.py` — **no
  `logic → data` edge**; the Qt importers are exactly `ui/{tileset_editor_panel,tilemap_canvas,`
  `tilemap_layer_panel,tilemap_io_actions,tilemap_chunk_cache}` (`tiled_mode.py` is Qt-free); the
  off-thread chunk warmer keeps Qt in `ui/` and calls the Qt-free `render_region` off-thread on a
  scene-owned `QThreadPool`, returning the `PixelBuffer` via a queued GUI-thread signal (no leak).
- **Traceability:** 35/35 REQ (14 LOGIC + 17 UI + 4 DATA) have both a shipped implementation and ≥1
  passing test; **0 uncovered**. `traceability.md` updated to the real shipped test modules.
- **C1:** spec ↔ plan ↔ tasks ↔ ADR-0013/0014/0015/0016 remain coherent after the perf loop-back and
  the S2/S3 fixes; the vectorised `render_region` + per-chunk `QPixmap` cache + O(1) `chunk_version`
  API are reflected in `plan.md §7.1` and `STRUCTURE.md`. No drift.
- **Teardown discipline sanctioned:** `Tilemap_Canvas.shutdown_warm → MainWindow.shutdown_prewarm →
  closeEvent` mirrors the Phase-5 `CanvasScene.shutdown_prewarm` fix; QA proved no segfault under
  `-n auto`. Architecturally ratified.

### 8.1 Adjudication of the 5 AGT-03 deviations (report `subagent-report-agt-03-python-dev-aebf75e8`)

| # | Deviation | Verdict | Rationale |
| --- | --- | --- | --- |
| D-1 | `render_region(x, y, w, h)` operates in **pixel space** (not tile space) | **RATIFY** | ADR-0015 froze the seam + non-destructive contract, not the coordinate unit. Pixel-space matches `blend.composite_stack`'s region semantics (ADR-0007) and the `drawBackground` exposed-rect / viewport-cull seam (DEP-3). Consistent with ADR-0015 + Article VI; recorded in plan §7.1. |
| D-2 | Custom lossless tileset-pixel embed key `"pixelartcreator:source"` (zlib+base64) in Tiled export | **RATIFY** | ADR-0014 mandates embedded tilesets + lossless round-trip + verbatim unknown-field passthrough; a namespaced custom property is exactly the sanctioned carrier and real Tiled ignores it. Foreign files get a blank RGBA source so gid/region mapping still resolves — pixel content is not part of REQ-P6-DATA-002's "equivalent tilemap". Consistent with ADR-0014. |
| D-3 | `Tilemap.tiled_passthrough: Dict[str, Any]` opaque round-trip carrier | **RATIFY** | Directly realises ADR-0014's verbatim-passthrough requirement (unknown top-level keys, per-tileset extras, non-tile layers). Plain JSON-able, Qt-free, not serialised into `.pixproj` (native format lists its own fields). Consistent with ADR-0014 + Article I. |
| D-4 | `make_attach_tileset_command` appends the tileset using its **declared `first_gid`** (no auto-offset) | **RATIFY** | Plan §2/§5 + ADR-0015 fix the global gid space as "Tiled-style first-gid where the tileset declares its firstgid"; `resolve()` picks the largest `first_gid ≤ base` and the defensive path rejects unknown gids. No auto-assignment is mandated. Consistent. |
| D-5 | Native `.pixproj` tilemap→tileset refs stored as **indices into `document.tilesets`**; `serialize` raises `ProjectIOError` for an unattached tileset | **RATIFY** | ADR-0016 persists `Document.tilesets`+`Document.tilemaps`; index refs are the natural normalised serialisation, and the fail-closed guard is Article VII defensive posture. No contract signature affected. Consistent with ADR-0016 + Article VII. |

**All 5 RATIFIED; 0 FLAGGED.** No architectural inconsistency; no uncovered REQ; the 8K/16 ms budget
is not relaxed. **FINAL GATE: PASS — CLEARED FOR COMMIT** (AGT-09 owns the commit; AGT-09 to wire the
two-part `ci.yml` tilemap perf gate: part-1 `perf_profile.py --tilemap` vs `FRAME_BUDGET_MS` 16 ms;
part-2 `--tilemap --budget-ms 3000` from `TILEMAP_VIEWPORT_CEILING_MS`).
