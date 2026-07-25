# Tasks — Phase 12: Performance & Scalability

| Field | Value |
| --- | --- |
| Feature | `phase-12-performance-scalability` |
| Author | Claude (AGT-01, Architecture) via `sdd-tasks` |
| Date | 2026-07-07 |
| Over | `plan.md` + `docs/adr/0033-*` (flatten strategy) + `docs/adr/0034-*` (drag preview) — **slice-by-slice**, each an independently gate-green, CI-green shippable increment. Slice A (full-frame flatten fast-path + tiling + dirty-tile + `--full-frame` gate) → Slice B (viewport recomposite split-cache + opacity-drag LOD preview + viewport-scale gate) → Slice F (artifact + docstring hygiene). |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII). **NO implementation begins until C1 is green — this gate is the blocker.** Each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table: **AGT-10** perf directive +
scenario + RE-PROFILE ship gate; **AGT-03** logic code; **AGT-05** UI code; **AGT-04** logic regression +
correctness + perf-probe tests; **AGT-06** UI/a11y/both-theme tests; **AGT-07** string audit/i18n;
**AGT-08** docs + FU-4 docstrings; **AGT-09** ci.yml + commits; **AGT-01** architecture/analyze/gate +
Slice-F artifact reconciliation; **AGT-02** traceability + scenario renumber. One owner per task;
deterministic sub-steps name their script. Every REQ maps to ≥ 1 impl + ≥ 1 test/verify task. **Per-slice
performance flow:** AGT-10 directive → AGT-03/AGT-05 implement → AGT-04/AGT-06 regression + correctness →
**AGT-10 RE-PROFILE ship gate** → AGT-01 final gate → AGT-08 docs → AGT-07 i18n (if strings) → AGT-09
commit + gate wiring.

**Byte-exact invariant (CENTRAL):** the optimised full-frame flatten (Slice A) and the committed
full-resolution viewport recomposite (Slice B) MUST be **byte-equal** to the current shipped compositor
for NORMAL + all 11 separable modes, zero tolerance, deterministic (REQ-P12-LOGIC-002/-004). **The only
16 ms-bound path is the drag preview (REQ-P12-UI-001);** the flatten and the commit recomposite are batch
paths bounded by loose named ceilings, **not** asserted vs 16 ms (Article VI; budget never relaxed).

---

## Slice A — cold full-frame 8K multi-layer flatten (`logic/`; FU-P5-PERF)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-A-00 | **AGT-10 directive:** confirm the dependency-free flatten strategy at build time (baseline §3/§5, ADR-0033): uint8 straight-alpha source-over fast-path for NORMAL/opacity-1/unmasked layers; blocked/tiled full-frame working set via `_composite_region` (thread-pool fan optional); dirty-tile flatten-cache reuse; optional off-thread via `composite_warmer`. Byte-exact invariant is non-negotiable. | AGT-10 | perf directive → AGT-03 | analyze C1 | LOGIC-001 / baseline §3 FU-P5 | todo |
| T12-A-01 | Add `COMPOSITE_FULL_CEILING_MS = 3000` (loose full-frame catastrophic ceiling; mirrors full-8K `TILEMAP_VIEWPORT_CEILING_MS`) with a citation docstring. **Name DISTINCT from every shipped ceiling** (`COMPOSITE_REGION_CEILING_MS`/`TILEMAP_VIEWPORT_CEILING_MS`/`OVERLAY_FRAME_CEILING_MS`/`REALTIME_APPLY_CEILING_MS`). Value is AGT-10-RE-PROFILE-confirmed at T12-A-05. | AGT-03 | `logic/constants.py` | T12-A-00 | LOGIC-003 / plan §8, ADR-0033 §5 | todo |
| T12-A-02 | Optimise `composite_stack(region=None)` **in place**: uint8 source-over fast-path (byte-exact vs `_blend_over_arrays` for NORMAL/op-1/unmasked) + float32 only for non-normal/masked/partial-opacity; blocked/tiled working set over disjoint tiles through `_composite_region` (byte-identical to the single-shot path); dirty-tile flatten-cache seam reusing the `_flatten_group` MRU + `document.py` ancestor invalidation. **Public signature preserved.** Zero Qt (`document`-free, PL-D2). | AGT-03 | `logic/blend.py` | T12-A-01 | LOGIC-001, -002 / "cold full-frame flatten … at or under ceiling", "byte-exact" | todo |
| T12-A-03 | Byte-exact + determinism regression tests (headless): for NORMAL **and each of the 11 separable modes**, the optimised full-frame `composite_stack(region=None)` output is **byte-equal** to the current compositor over the same layers/opacities/masks (bit-exact, no tolerance); run twice ⇒ byte-identical; representative 4-layer + 8-layer mixed-blend stacks; no mode dropped/altered. `check_layering`/`check_cycles` exit 0 (compositor stays Qt-free `logic/`). | AGT-04 | `tests/logic/test_blend_fullframe.py`, `scripts/*` (invoke) | T12-A-02 | LOGIC-002 / SC-P12-LOGIC-002-1/-2 | todo |
| T12-A-04 | Author the `perf_profile` `--full-frame` (`region=None`) full-canvas flatten scenario (Qt-free numpy + `logic/` only, mirroring `--composite`): 8-layer mixed-blend 8K stack, cold, median/p95 vs `COMPOSITE_FULL_CEILING_MS`; exit 0/1/2 per the harness contract. | AGT-10 | `scripts/perf_profile.py` | T12-A-02 | LOGIC-003 / SC-P12-LOGIC-003-1 | todo |
| T12-A-05 | **AGT-10 RE-PROFILE ship gate:** measure the optimised cold full-frame flatten (4L + 8L) via `--full-frame` on the CI-class runner; confirm at/under `COMPOSITE_FULL_CEILING_MS` (4L comfortably under) and that the catastrophic 20–43 s cost is eliminated; confirm or tighten the constant value (feed back to T12-A-01 if tightened). Not asserted vs 16 ms. | AGT-10 | re-profile report → AGT-01/AGT-03 | T12-A-04, T12-A-03 | LOGIC-001, -003 / SC-P12-LOGIC-001-1/-2 | todo |
| T12-A-06 | Wire the `--full-frame` gate into CI at `COMPOSITE_FULL_CEILING_MS` (passed from the named constant, no literal — the `--composite`/`--tilemap` precedent); place after the existing compositor gate. | AGT-09 | `.github/workflows/ci.yml` | T12-A-05 | LOGIC-003 / SC-P12-LOGIC-003-1 | todo |
| T12-A-07 | Re-run `check_layering --root pixelart_creator` + `check_cycles --root pixelart_creator`: confirm the flatten optimisation adds no Qt to `logic/`, no new module, no new edge, no cycle; module count unchanged (178/179). Must exit 0. | AGT-03 | `scripts/*` (invoke) | T12-A-02 | LOGIC-001 / Article I / plan §11 | todo |

## Slice B — whole-viewport recomposite + live opacity-slider drag (`logic/` + `ui/`; FU-16b)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-B-00 | **AGT-10 directive:** confirm the dependency-free Slice-B strategy (baseline §3/§5, ADR-0034): split-cache `composite(below)`/`composite(above)` around the dragged layer (≈2–3 blends, not 12); downsampled-LOD preview holding 16 ms during drag; cull to the exposed viewport rect + dirty region; throttle/off-thread ticks (Phase-4 D3 + Phase-5 warmer); full-resolution byte-exact recomposite on commit. | AGT-10 | perf directive → AGT-03/AGT-05 | analyze C1 | LOGIC-004, UI-001 / baseline §3 FU-16 | todo |
| T12-B-01 | Add `VIEWPORT_RECOMPOSITE_CEILING_MS = 2000` (loose viewport-scale catastrophic ceiling) with a citation docstring. **Name DISTINCT from every shipped ceiling.** Value AGT-10-RE-PROFILE-confirmed at T12-B-06. | AGT-03 | `logic/constants.py` | T12-B-00 | LOGIC-005 / plan §8, ADR-0034 §4 | todo |
| T12-B-02 | Add the pure `logic/blend.py` Slice-B support seam (Qt-free, additive, `document`-free): split-cache helper for `composite(below idx)` / `composite(above idx)` around a target index (byte-exact when re-composed on commit) + a pure nearest-neighbour **LOD downsample** helper for the preview. No public signature break. | AGT-03 | `logic/blend.py` | T12-B-01 | LOGIC-004 / "recomposite path imports no Qt", byte-exact | todo |
| T12-B-03 | Byte-exact recomposite regression tests (headless): the full-resolution whole-viewport recomposite (up to 1920², ≥ 12 layers) via the split-cache commit path is **byte-equal** to the current compositor over the same inputs (NORMAL + 11 modes, no tolerance); the recomposite path imports no Qt (`check_layering`); not asserted vs 16 ms. | AGT-04 | `tests/logic/test_viewport_recomposite_byte_exact.py`, `scripts/*` (invoke) | T12-B-02 | LOGIC-004 / SC-P12-LOGIC-004-1/-2 | todo |
| T12-B-04 | Opacity-slider **drag lifecycle** in `ui/layer_panel.py`: on drag-start capture the split-cache; per tick render the downsampled-LOD preview (throttled via the Phase-4 D3 debounce; off-thread via `composite_warmer`, cached in `frame_cache`); on release/commit apply the full-resolution byte-exact recomposite and display it through the existing dirty-rect path. **No compositing maths in the widget** (calls `logic/blend`). `tr()` + `changeEvent` preserved; both themes identical. | AGT-05 | `ui/layer_panel.py`, `ui/composite_warmer.py`, `ui/frame_cache.py`, `ui/canvas_scene.py`/`ui/canvas_view.py` | T12-B-02 | UI-001 / SC-P12-UI-001-1/-2 | todo |
| T12-B-05 | pytest-qt tests (both themes, offscreen): during an opacity drag on a low-zoom ≥ 12-layer 8K document, each per-tick downsampled preview **holds the 16 ms `FRAME_BUDGET_MS`** and the UI stays responsive (no multi-second freeze); on release the full-resolution recomposite is applied and the committed pixels match the current build (byte-exact per T12-B-03); light and dark behave identically; a11y (focus/keyboard) on the slider preserved. | AGT-06 | `tests/ui/test_opacity_drag_responsive.py` | T12-B-04 | UI-001 / SC-P12-UI-001-1/-2 | todo |
| T12-B-06 | Author the dedicated `perf_profile --viewport-recomposite` **viewport-scale split-cache COMMIT gate** scenario (region ≥ 1080²/1920², 12 layers) at `VIEWPORT_RECOMPOSITE_CEILING_MS` (a distinct flag from the shipped 16-px `--composite` gate — the shipped `scripts/perf_profile.py` implements `--viewport-recomposite`, not a `--composite` extension); **AGT-10 RE-PROFILE ship gate:** measure the optimised commit recomposite on the CI-class runner, confirm at/under the ceiling (2–7 s catastrophe eliminated), confirm/tighten the constant + the gate scenario (feed back to T12-B-01). Not asserted vs 16 ms. | AGT-10 | `scripts/perf_profile.py`, re-profile report → AGT-01/AGT-03 | T12-B-02 | LOGIC-005 / SC-P12-LOGIC-005-1 | todo |
| T12-B-07 | Wire the `--viewport-recomposite` gate into CI at `VIEWPORT_RECOMPOSITE_CEILING_MS` (passed from the named constant, no literal). | AGT-09 | `.github/workflows/ci.yml` | T12-B-06 | LOGIC-005 / SC-P12-LOGIC-005-1 | todo |
| T12-B-08 | String audit (`string_audit_check`) on `ui/layer_panel.py` **only if** the drag lifecycle adds any new user-visible string (e.g. a "preview" status); wrap in `tr()` + `changeEvent` retranslate. Skipped if no new string. | AGT-07 | `ui/layer_panel.py` | T12-B-04 | UI-001 (Article V) | todo |
| T12-B-09 | Re-run `check_layering` + `check_cycles`: confirm the split-cache/LOD seam adds no Qt to `logic/`, no new module/edge/cycle; module count unchanged. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T12-B-02 | LOGIC-004 / Article I / plan §11 | todo |

## Slice F — requirement-artifact + docstring hygiene (C3 leftovers; DEP-5)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-F-01 | **FU-2:** reconcile Phase-1 `plan.md` §9 point 1 (`REQ-P1-LOGIC-004` grounding) to the shipped Phase-1 spec/traceability resolution — **S7 (palette nearest) + S2 (flood-fill tolerance)** (the plan currently says "S1 drawing"). Confirm all three artifacts trace `REQ-P1-LOGIC-004` to one consistent S-id set. Artifact text only; no runtime change; no `docs/**`. | AGT-01 | `specs/phase-1-core-engine/plan.md` | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-1 | todo |
| T12-F-02 | **FU-17:** give Phase-1 and Phase-4 `SC-UI-*` scenarios **phase-unique identifiers** (e.g. `SC-P1-UI-*` / `SC-P4-UI-*`, matching the `SC-P12-*` convention) across each phase's `spec.md`/`acceptance.md`/`traceability.md`, so no `SC-UI-NNN` id denotes two different scenarios across phases. Update cross-references. Artifact text only. | AGT-02 | `specs/phase-1-ui-canvas/*`, `specs/phase-4-layer-canvas/*` | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-2 | todo |
| T12-F-03 | **FU-16 label collision:** assign distinct identifiers (e.g. `FU-16a` cache-invalidation / `FU-16b` opacity-drag recomposite, per spec §2c) in the requirement artifacts so the two former "FU-16" follow-ups are never conflated. | AGT-01 | `specs/phase-12-performance-scalability/*` (+ any FU ledger reference) | analyze C1 | LOGIC-007 / SC-P12-LOGIC-007-3 | todo |
| T12-F-04 | **FU-4:** complete the residual missing docstrings in `pixelart_creator/logic/` flagged by `pydocstyle` (D101/D102/D105/D107). Enumerate the flagged modules via a `pydocstyle` pass, add PEP 257 docstrings; **doc-only, no runtime change** (Article I). | AGT-08 | `pixelart_creator/logic/*.py` (docstrings) | analyze C1 | LOGIC-006 / SC-P12-LOGIC-006-1 | todo |
| T12-F-05 | Verify Slice F: `pydocstyle` reports **zero** D101/D102/D105/D107 on the previously-flagged `logic/` modules (tests unaffected); `REQ-P1-LOGIC-004` traces to one consistent S-id across plan/spec/traceability; no `SC-UI-*` id is ambiguous across Phase-1/Phase-4; each former "FU-16" follow-up has a distinct id; `sdd-analyze` reports no cross-artifact traceability finding attributable to FU-2/-17/-16. | AGT-01 | `scripts/*` (invoke), analyze | T12-F-01..04 | LOGIC-006, -007 / SC-P12-LOGIC-006-1, -007-1/-2/-3 | todo |

## OPTIONAL / LOW — off-thread palette analytics (REQ-P12-UI-002, FU-18 residual; deferrable)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T12-U2-01 | **OPTIONAL / LOW — build only if the orchestrator adopts it.** Run the palette-analytics recompute **off the GUI thread** (dependency-free, Phase-7/8/10 worker precedent) so a near-worst-case many-colour 8K canvas cannot freeze the UI; result **unchanged** vs the current compute; not a frame-budget path. If deferred, FU-18 stays a documented "verified, no action" descope (spec §2b) with **no acceptance owed**. | AGT-05 | `ui/palette_analytics_view.py` | (orchestrator adopt) | UI-002 / SC-P12-UI-002-1 (if adopted) / -2 (if deferred) | todo |
| T12-U2-02 | *(if adopted)* pytest-qt test: a live analytics recompute on a near-worst-case many-colour 8K canvas does not freeze the GUI (compute off-thread; dock updates on completion); result unchanged; not gated by 16 ms. | AGT-06 | `tests/ui/test_analytics_offthread.py` | T12-U2-01 | UI-002 / SC-P12-UI-002-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-12 hardened touch-points (`logic/blend.py`, `logic/constants.py` +2 ceilings, `ui/layer_panel.py`/`composite_warmer`/`frame_cache`, the perf scenarios/gates) — marked PLANNED; note **no new module / no `data/` work**. | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; **zero unresolved findings before implement**. | AGT-01 | `specs/phase-12-performance-scalability/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | Confirm **no `check_layering`/`check_cycles` rule edit needed** (no new module/edge; everything edits existing `logic/`/`ui/` in place); baseline exit 0 (178/179). | AGT-01 | `scripts/*` (invoke) | plan | Article I / plan §4.4/§11 | done |
| TG-04 | Manifest: **no new runtime dependency; no GPU** (both items dependency-free); confirm no `pyproject.toml` change (PL12-D6). No new pytest marker (the perf gates are Qt-free numpy, no marker — the `--composite`/`--tilemap` precedent). | AGT-09 | `pyproject.toml` (confirm no change) | plan | PL12-D6 / spec §6 | todo |
| TG-05 | a11y verification on the opacity-slider drag interaction (focus visible, keyboard-reachable, preview does not trap focus) across both themes. | AGT-06 | `tests/ui/*` | T12-B-05 | UI-001 (Article V) | todo |
| TG-06 | CHANGELOG (`Unreleased`) entries for the Phase-12 flatten/recomposite hardening + the two new perf gates, tied to REQ-IDs, per slice. | AGT-08 | `docs/CHANGELOG.md` | Slice A/B impl+test done | Article IX | todo |
| TG-07 | `sdd-checklist` before ship: every REQ has a passing test/verify; byte-exact flatten (12 modes) + byte-exact commit recomposite + drag preview holds 16 ms + full-frame gate + viewport-scale gate all green; both themes + a11y green; FU-4 pydocstyle zero + FU-2/-17/-16 reconciled; **no batch path asserted vs 16 ms and the budget never relaxed** (Article VI). | AGT-06 | checklist report | all impl+test done | Article IV/V/VI/VIII | todo |
