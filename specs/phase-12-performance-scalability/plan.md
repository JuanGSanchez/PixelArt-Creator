# Plan — Phase 12: Performance & Scalability

| Field | Value |
| --- | --- |
| Feature | `phase-12-performance-scalability` |
| Author | Claude (AGT-01, Architecture) via `sdd-plan` |
| Date | 2026-07-07 |
| Governed by | `constitution.md` (Articles **I**, **II**, **III**, **IV**, **VI**, **VIII**, **X**, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for the roadmap-finale **NFR + doc-hygiene hardening** phase. It authors **no new product entity, no new module, no `data/` work**: it **hardens the measured cost** of two shipped, effectively-ungated compositor hotspots and **reconciles the C3 requirement-artifact leftovers**. Every product behaviour it touches already ships (Phases 1–11); the flattened/recomposited **bytes must not change** (byte-exact). |
| Over spec | `specs/phase-12-performance-scalability/spec.md` (9 REQ: `REQ-P12-LOGIC-001..007`, `REQ-P12-UI-001..002`; UI-002 OPTIONAL/LOW) + `acceptance.md` (13 Gherkin scenarios) + `traceability.md`. §10 clarifications **NONE OPEN** (A2-D2 gate: nothing SUSPENDED). |
| Grounded measure-first in | `docs/perf/phase12-baseline.md` (AGT-10, HEAD `f73b1a5`, 2026-07-07) — the authoritative source for current cost, target, dependency-free optimisation direction, and which items are descoped. **This plan invents no perf numbers**; every ceiling below is the baseline's measured cost + AGT-10's recommended loose bound, subject to AGT-10's **RE-PROFILE ship-gate** confirmation (§9). |
| Stack source | S8 (fixed) — Python 3.12+, stdlib + NumPy (shipped). **NO new runtime dependency; NO GPU decision.** Both confirmed items are solvable dependency-free (baseline §5). **The Researcher is NOT required** (PL12-D1 Branch B); no AGT-09 manifest change (PL12-D6). |
| ADRs filed | **ADR-0033** (full-frame flatten optimisation strategy: uint8 straight-alpha source-over fast-path + blocked/tiled working set + optional off-thread + dirty-tile cache reuse, under the **byte-exact output invariant** and the loose `COMPOSITE_FULL_CEILING_MS` gate); **ADR-0034** (interaction preview-during-drag: split-cache the flatten around the dragged layer + downsampled-LOD preview that holds 16 ms during the drag + byte-exact full-resolution recomposite on commit, under the loose `VIEWPORT_RECOMPOSITE_CEILING_MS` gate). Numbered after ADR-0032 (Phase 11). |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-12 spec — the
**Performance & Scalability** roadmap finale. It does **not** add capability. It:

1. **Slice A** — brings `logic/blend.py::composite_stack(region=None)` (the cold full-frame 8K
   multi-layer flatten, measured **20 244 ms @ 4L → 42 669 ms @ 8L**, baseline §2 #1/#1b) under a **loose
   named ceiling** `COMPOSITE_FULL_CEILING_MS`, **without changing the produced pixels** — the flatten is
   **byte-exact** vs the current shipped compositor for NORMAL and all 11 separable modes — and adds the
   full-frame (`region=None`) perf gate the shipped 16-px `--composite` gate is structurally blind to.
2. **Slice B** — keeps the whole-viewport / low-zoom multi-layer recomposite driving the live
   opacity-slider drag **responsive** (measured **2 231 ms @ 1080² / 7 024 ms @ 1920², 12L**, baseline
   §2 #2/#2b): a **downsampled preview holds the 16 ms `FRAME_BUDGET_MS` during the drag**, and on
   **commit** the **full-resolution** recomposite produces the **byte-exact same final pixels as today**.
   It brings the full-resolution viewport-scale recomposite under a loose `VIEWPORT_RECOMPOSITE_CEILING_MS`
   and adds the viewport-scale perf gate.
3. **Slice F** — reconciles the C3 requirement-artifact + docstring leftovers (FU-2, FU-17, the FU-16
   label collision, FU-4) so the SDD corpus is internally consistent at the finale.

It maps every REQ to its S11 layer, sets the two loose perf ceilings as **single-source named constants**
in `logic/constants.py` (Article II), rules the DEP-1/DEP-2 HOW in **ADR-0033 / ADR-0034**, confirms the
**Article VI posture** (the two optimisations are batch / on-demand paths bounded by *loose catastrophic*
ceilings; the **only** per-frame path introduced — the drag preview — **holds** 16 ms; the budget is
**never relaxed**), and is decomposed **slice-by-slice** in `tasks.md` per the shipped per-slice
performance flow (AGT-10 directive → AGT-03/AGT-05 implement → AGT-04/AGT-06 regression + correctness →
AGT-10 RE-PROFILE ship gate → AGT-01 final gate → AGT-08 docs → AGT-07 i18n if strings → AGT-09 commit +
gate wiring).

**Central honesty ruling (baseline §1 + §4).** The two hotspots are *effectively ungated*: the shipped
`perf_profile --composite` gate only composites a **16×16 region** (~0.77 ms), so it cannot see either the
full-frame flatten (`composite_stack` has **no `region=None` branch** in the gate) or the whole-viewport
recomposite blow-up. Phase 12 does **not** re-implement the compositor — it adds fast-paths + caching
*within* `composite_stack` (Slice A), a split-cache/LOD support seam in `logic/` + a drag-preview
controller in `ui/` (Slice B), and the two missing gates. **No new module is created; no `data/` work is
done.** Three measured-in-budget / edge-only hotspots (FU-8, FU-18-core, FU-P9-OVERLAY-8K) are **descoped
"verified, no action"** per spec §2b and this plan **creates no work for them**; the optional off-thread
analytics item (REQ-P12-UI-002) is captured **LOW / deferrable** (§7).

## 2. The byte-exact invariant + Article VI posture (CENTRAL; ADR-0033/0034)

> **(a) Output invariance is a hard correctness constraint, not a tolerance.** The optimised full-frame
> flatten (Slice A) and the committed full-resolution viewport recomposite (Slice B) produce a buffer
> **byte-equal** to the current shipped `composite_stack` over the same inputs — for NORMAL **and** all 11
> separable blend modes, across representative layer counts / opacities / masks — with **zero tolerance**
> (REQ-P12-LOGIC-002, -004). The shipped NORMAL integer bit-exact contract (FLAG-04-1 / ADR-0005; the
> float64 `_blend_over_arrays` path) is **preserved**. Any fast path is admissible **only if** it
> reproduces the current bytes exactly and is **deterministic** (same inputs ⇒ byte-identical across runs).
> **(b) The 16 ms `FRAME_BUDGET_MS` is a FIXED constraint, never relaxed (Article VI §2 / VIII §3).** The
> two optimisations govern **batch / on-demand** paths (flatten / export / merge-visible; full-resolution
> recomposite on commit) that were **never 60-fps paths** — so they are bounded by **loose
> catastrophic-regression** ceilings, **not** by 16 ms, and the operation is **not asserted against the
> 16 ms budget**. The **only** per-frame path introduced — the *downsampled preview during* an opacity
> drag (REQ-P12-UI-001) — **holds** the 16 ms budget exactly as Article VI requires.
> **(c) The compositor stays Qt-free `logic/`.** All Slice-A/B compositing maths, split-caching, tiling,
> dirty-tile reuse, and the pure LOD-downsample helper live in `logic/blend.py`; the only Qt is `ui/`
> (the opacity-drag preview controller; the optional off-thread analytics). **No new `data/` work.**
> **(d) FU-15 loose-ceiling caution is honoured throughout.** All baseline numbers are 8-core desktop; the
> GitHub CI runner is 2-core, ~1.5–2.5× slower on numpy/raster paths. Every new ceiling is a **loose**
> bound sized **above** the optimised cost with 2-core headroom — never a tight 16 ms bound — and is
> confirmed/tightened by AGT-10's RE-PROFILE ship gate against the actual optimised 2-core measurement
> before AGT-09 wires CI.

Realised **structurally**: no new module and no new layering edge is introduced. `check_layering` /
`check_cycles` stay exit 0 (§11) — the optimisations land inside the existing pure `logic/blend.py` and
existing `ui/` files; the drag preview reuses the shipped Phase-5 `ui/composite_warmer.py` off-thread
substrate + `ui/frame_cache.py` LRU and the Phase-4 D3 opacity-drag debounce.

## 3. Stack / optimisation decisions (all grounded in the baseline — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language / stack | Python 3.12+; stdlib + NumPy (shipped); reuse `blend.composite_stack`, `color.blend_over`, the 12-mode `BlendMode` enum, `composite_warmer`, `frame_cache`, the opacity-slider D3 debounce | S8; baseline §7 |
| New dependency / GPU | **None** — both confirmed items dependency-free (pure-numpy fast-paths, split-caching, tiling + threading, LOD-during-drag, off-thread) | baseline §5; spec §6 (non-goal); PL12-D1/D6 |
| **Slice A — flatten fast-path** | **uint8 straight-alpha source-over fast path** for NORMAL-mode / opacity-1 / unmasked layers (the common case); promote to float32 **only** for genuinely non-normal / masked / partial-opacity layers. Removes most of the 33 M-px float round-trips. Byte-exact vs `_blend_over_arrays`. | REQ-P12-LOGIC-001/-002; baseline §3 FU-P5 #1; ADR-0033 |
| **Slice A — blocked / tiled working set** | Tile the full-frame flatten into blocks and drive each tile through the already-fast region compositor (`_composite_region`), fanning tiles across a thread pool (numpy releases the GIL); bound the per-tile working set. Output identical to the whole-frame path (tiles are disjoint, blitted at their origin). | REQ-P12-LOGIC-001/-002; baseline §3 FU-P5 #2; ADR-0033 |
| **Slice A — dirty-tile cache reuse** | Cache the flattened buffer per tile; recompute only changed tiles (reuse the `_flatten_group` MRU-cache precedent + `document.py` ancestor-chain invalidation). Optional off-thread with a progress cue (Phase-5 `composite_warmer`). | REQ-P12-LOGIC-001; baseline §3 FU-P5 #3/#4; ADR-0033 |
| **Slice B — split-cache** | At drag-start cache `composite(below)` and `composite(above)` the dragged layer **once**; per tick blend only `below ⊕ (layer·opacity) ⊕ above` (≈2–3 blends, not 12). Pure `logic/blend.py`; byte-exact on commit. | REQ-P12-LOGIC-004; baseline §3 FU-16 #1; ADR-0034 |
| **Slice B — LOD preview during drag** | Recomposite a **downsampled** (nearest-neighbour, pure-numpy) preview that holds 16 ms per tick; full-resolution byte-exact recomposite on mouse-release/commit. Cull to the true exposed viewport rect + dirty region; throttle/off-thread ticks (Phase-4 D3 debounce + Phase-5 warmer). | REQ-P12-UI-001, REQ-P12-LOGIC-004; baseline §3 FU-16 #2/#3/#4; ADR-0034 |
| **Perf ceilings** | Two **single-source named constants** in `logic/constants.py` (§8): `COMPOSITE_FULL_CEILING_MS`, `VIEWPORT_RECOMPOSITE_CEILING_MS`. Loose catastrophic bounds (FU-15), **not** 16 ms. Values = AGT-01/ADR candidates, AGT-10-RE-PROFILE-confirmed. | REQ-P12-LOGIC-003/-005; Article II; baseline §6; DEP-1 |
| **Perf scenarios + gates** | New `perf_profile` `--full-frame` (`region=None`) scenario; new dedicated `perf_profile --viewport-recomposite` viewport-scale COMMIT scenario (region 1080²/1920², 12L) — a distinct flag from the shipped 16-px `--composite` gate (the shipped `scripts/perf_profile.py` implements `--viewport-recomposite`). Wired into CI at the loose named ceilings. Scenario = AGT-10 HOW; CI wiring = AGT-09 HOW. | REQ-P12-LOGIC-003/-005; baseline §6; DEP-3 |
| **Slice F — artifact hygiene** | FU-2 (Phase-1 `plan.md` §9 `REQ-P1-LOGIC-004` S-id mismatch), FU-17 (Phase-1↔Phase-4 `SC-UI-*` scenario-number collision), FU-16 label collision (§2c disambiguation), FU-4 (residual `logic/` docstrings). Artifact/source text only; **no runtime change; no `docs/**`** touched by the SDD artifacts. | REQ-P12-LOGIC-006/-007; spec §2c; DEP-5 |
| Testing | pytest (logic byte-exact regression per mode + determinism; the two `perf_profile` gates), pytest-qt both themes (opacity-drag responsiveness + commit byte-exactness), pydocstyle (FU-4), `sdd-analyze` (FU-2/-17/-16). Headless, deterministic, portable. | Article IV; spec §5 |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`) | Article III |

No Phase-12 decision places Qt in `logic/` (**PL12-D2 → Branch B held**); the two ceilings are the only new
numerics and go to `logic/constants.py` (Article II / BF). The sole Qt file outside `ui/` remains
`ui/commands.py` — **unchanged** this phase (the two optimisations push no new `QUndoCommand`; a flatten /
opacity-commit is not a new undoable op — opacity change is already undoable via the shipped D3 path).

## 4. Architecture — module → layer touch-point map (S11)

Phase 12 adds **no new module**. It **hardens** shipped modules in place. Dependency direction is
unchanged and acyclic (verified §11): `document → blend → color/constants/pixel_buffer`; `ui/ → logic/`.

### 4.1 `logic/` touch-points (pure, zero Qt)

| Module | Change | Responsibility added | REQ | Slice |
| --- | --- | --- | --- | --- |
| `constants.py` *(extend)* | +2 perf ceilings (leaf, no imports) — `COMPOSITE_FULL_CEILING_MS`, `VIEWPORT_RECOMPOSITE_CEILING_MS`. **Names DISTINCT from every shipped ceiling** (`COMPOSITE_REGION_CEILING_MS`, `TILEMAP_VIEWPORT_CEILING_MS`, `OVERLAY_FRAME_CEILING_MS`, `REALTIME_APPLY_CEILING_MS`). | Single-source loose ceilings for the two new gates (Article II). | LOGIC-003, -005 | A / B |
| `blend.py` *(extend)* | **Slice A:** a uint8 source-over fast-path for the flatten's common case + a blocked/tiled full-frame path (optionally thread-pool-fanned) + a dirty-tile flatten-cache seam — all **inside** `composite_stack(region=None)` / private helpers, **byte-exact** vs the current output. **Slice B:** a pure split-cache seam (`composite(below)` / `composite(above)` around a target index) + a pure nearest-neighbour **LOD downsample** helper for the drag preview. **No public signature break** — `composite_stack(nodes, w, h, *, region=None)` is preserved; new capability is additive/private (a preview/split entry point may be added). Zero Qt. | Slice A flatten speedup + Slice B recomposite support. | LOGIC-001, -002, -004 | A / B |

`constants.py` stays a leaf. `blend.py` keeps its `document`-free posture (PL-D2): the compositor consumes
nodes through the structural `CompositeNode` Protocol only. The tiled path composites disjoint tiles via
the existing `_composite_region` and blits at each tile origin, so a tiled full-frame flatten is
byte-identical to the single-shot `_composite_region(0,0,W,H)` (no cross-tile blend state). **No
`logic → data`, no cycle** — no new edge is introduced at all.

### 4.2 `ui/` touch-points (Qt only)

| Module | Change | Responsibility added | REQ | Slice |
| --- | --- | --- | --- | --- |
| `layer_panel.py` *(extend)* | Opacity-slider **drag lifecycle**: on drag-start capture the split-cache; per tick render the downsampled-LOD preview (holds 16 ms) via the throttled D3 debounce; on release/commit apply the full-resolution byte-exact recomposite. No compositing maths in the widget — it calls `logic/blend`. `tr()` + `changeEvent` unchanged. | Live opacity drag stays interactive; commit output unchanged. | UI-001 | B |
| `composite_warmer.py` *(reuse/extend)* | Off-GUI-thread runner for the full-resolution commit recomposite and (optionally) the full-frame flatten, with progress/cancel over queued signals (Phase-5 precedent; deterministic teardown preserved). No Qt off-thread. | Keep the GUI responsive during the batch recomposite/flatten. | UI-001, LOGIC-001 | A / B |
| `frame_cache.py` *(reuse)* | The bounded LRU that holds the split-cache below/above intermediates + the preview during the drag. | Preview + commit cache backing. | UI-001 | B |
| `canvas_scene.py` / `canvas_view.py` *(reuse)* | Display the preview during drag / the full-res result on commit through the existing dirty-rect blit path (no new render policy — AGT-10 owns any culling directive). | Show the preview / committed pixels. | UI-001 | B |
| `palette_analytics_view.py` *(extend — OPTIONAL/LOW)* | *If adopted:* run the analytics recompute off the GUI thread so a near-worst-case many-colour canvas cannot freeze it (result unchanged). Deferrable; if not built, FU-18 stays a documented descope (§2b). | Off-thread analytics compute. | UI-002 (opt) | (opt) |

Every touched `ui/` file keeps its `tr()`-wrapped strings + `changeEvent` retranslate (Article V); a11y +
both themes apply to the opacity-drag interaction (AGT-06 verifies). **No new `ui/` module; no
`ui/commands.py` change.**

### 4.3 Tooling / gate touch-points (outside the three layers — not layer-governed)

| File | Change | Owner | REQ |
| --- | --- | --- | --- |
| `scripts/perf_profile.py` *(extend)* | Add a `--full-frame` (`region=None`) full-canvas flatten scenario; add a dedicated `--viewport-recomposite` viewport-scale COMMIT scenario (region ≥ 1080², 12L). Qt-free numpy + `logic/` only, mirroring the existing `--composite` gate. **(Shipped script implements `--viewport-recomposite` as its own flag, not a `--composite` extension.)** | AGT-10 | LOGIC-003, -005 |
| `.github/workflows/ci.yml` *(extend)* | Two new perf-gate steps: `--full-frame` at `COMPOSITE_FULL_CEILING_MS`; `--viewport-recomposite` at `VIEWPORT_RECOMPOSITE_CEILING_MS`. Ceilings passed from the named constants (no literal). | AGT-09 | LOGIC-003, -005 |

### 4.4 Layering — no new rule, no new module, no new edge

Unlike Phase 10 (which added `sync_backend/`), Phase 12 adds **nothing** to the tree — it edits existing
`logic/`/`ui/` files in place. Therefore `scripts/check_layering.py` / `scripts/check_cycles.py` need **no
edit**, and the module count is **unchanged** (178 layering / 179 cycles). Baseline is clean (§11); each
touched file must keep it green (per-slice gate task).

## 5. Interface / behaviour contract notes (frozen before implementation)

Frozen so AGT-03/AGT-05 bind to a stable, byte-exact-preserving surface. No public break.

```python
# logic/blend.py — composite_stack public signature is PRESERVED (no break):
def composite_stack(nodes, width, height, *, region=None) -> PixelBuffer: ...
#   region=None  -> full-canvas flatten (Slice A optimises the INTERNALS: uint8
#                   source-over fast-path + blocked/tiled working set + dirty-tile
#                   reuse); OUTPUT BYTE-EXACT vs the current build (REQ-P12-LOGIC-002).
#   region=(x,y,w,h) -> unchanged region path.
#
# Slice B support (pure logic/, additive — exact names an AGT-03/ADR HOW):
#   * split-cache seam: cache composite(below idx) / composite(above idx) once,
#     then blend below (+) layer.opacity (+) above per tick (byte-exact on commit).
#   * a pure nearest-neighbour LOD downsample helper for the preview (Qt-free).
# Slice B UI (ui/layer_panel.py): drag-start -> capture split-cache; per tick ->
#   downsampled preview holding 16 ms (throttled, Phase-4 D3); commit -> full-res
#   byte-exact recomposite (REQ-P12-UI-001 / REQ-P12-LOGIC-004).
```

**Contracts.** (i) `composite_stack(region=None)` output is byte-equal to the current build for NORMAL + all
11 separable modes, deterministic (REQ-P12-LOGIC-002). (ii) The committed full-resolution viewport
recomposite is byte-equal to the current compositor (REQ-P12-LOGIC-004). (iii) The drag preview is the
**only** 16 ms-bound path; the flatten and the commit recomposite are **not** asserted against 16 ms
(REQ-P12-UI-001 / spec §5). (iv) No `Qt` import enters `logic/`; `check_layering` stays exit 0.

## 6. Slice F — requirement-artifact + docstring hygiene (C3 leftovers; DEP-5)

Artifact/source **text only**; **no runtime change**; the SDD artifacts touch only `specs/**` (+ `logic/`
source docstrings for FU-4, owned by AGT-08); **never `docs/**`**.

- **FU-2 (`REQ-P1-LOGIC-004` grounding).** Phase-1 `plan.md` §9 point 1 says retrace to "S7 palette /
  **S1** drawing"; the shipped Phase-1 `spec.md` (REV-3) + `traceability.md` resolved it to "S7 (palette
  nearest) + **S2** (flood-fill tolerance)". **Reconcile the plan to the shipped resolution: S7 + S2**
  (the flood-fill tolerance is S2, not S1), so all three artifacts trace `REQ-P1-LOGIC-004` to one
  consistent S-id set. Owner AGT-01 (plan) / AGT-02 (matrix confirm).
- **FU-17 (`SC-UI-*` scenario-number collision).** Phase-1 uses `SC-UI-001..026` and Phase-4 uses
  `SC-UI-001..018` — the same `SC-UI-NNN` id denotes two different scenarios across phases. **Give each
  phase a phase-unique scenario prefix** (e.g. `SC-P1-UI-*` / `SC-P4-UI-*`, matching the Phase-12
  `SC-P12-*` convention already in use), across each phase's `spec.md` / `acceptance.md` /
  `traceability.md`, so no `SC-UI-*` id is ambiguous. Owner AGT-02 (scenario ids) with AGT-01 confirming
  the plan/traceability cross-references.
- **FU-16 label collision (spec §2c).** Two distinct follow-ups both labelled "FU-16": **(a)** the
  cache-invalidation-completeness micro-optimisation (non-`document` buffer ops not self-invalidating the
  `LayerGroup` flatten cache; owner AGT-03; **not** the Phase-12 subject) and **(b)** the whole-viewport /
  opacity-drag recomposite (Phase-12 **Slice B**). **Assign distinct identifiers** in the requirement
  artifacts (e.g. `FU-16a` / `FU-16b`) so no future reader conflates them. Owner AGT-01/AGT-02.
- **FU-4 (residual `logic/` docstrings).** Complete the residual missing docstrings in
  `pixelart_creator/logic/` flagged by `pydocstyle` (D101/D102/D105/D107). **Doc-only; no runtime change**
  (Article I). Owner AGT-08 on `logic/` source (the enumeration is a deterministic `pydocstyle` pass — see
  T12-F-04).

Slice F is **artifact reconciliation**, not behaviour: its acceptance is `pydocstyle` zero-finding (FU-4)
+ single-consistent-S-id / no-colliding-scenario-id / distinct-follow-up-id + `sdd-analyze` reporting **no
cross-artifact traceability finding attributable to FU-2/-17/-16** (REQ-P12-LOGIC-006/-007).

## 7. Performance / render-budget posture (Article VI) + the OPTIONAL item

- **Slice A + Slice-B-commit are batch / on-demand** — bounded by the **loose** `COMPOSITE_FULL_CEILING_MS`
  / `VIEWPORT_RECOMPOSITE_CEILING_MS`, **never** the 16 ms budget; **not asserted** against 16 ms.
- **The drag preview (REQ-P12-UI-001) is the ONE per-frame path** — it **holds** 16 ms; the budget is
  never relaxed (Article VI §2 / VIII §3). No Phase-12 requirement weakens any gate.
- **AGT-10 owns the final directive at build time** (this plan captures the *intended* dependency-free
  approach from baseline §3/§5); AGT-10's **RE-PROFILE ship gate** (per slice) confirms the optimised cost
  is under the ceiling on the CI runner **before** AGT-01's final gate and AGT-09's CI wiring.
- **OPTIONAL / LOW — REQ-P12-UI-002 (off-thread palette analytics, FU-18 residual).** Flagged deferrable.
  The dock is already lazy + debounced; the residual is a 281 ms synthetic-worst-case GUI-thread compute.
  If the orchestrator adopts it, it is a `ui/palette_analytics_view.py` off-thread compute (result
  unchanged, not a frame path). **If deferred, FU-18 stays a documented "verified, no action" descope
  (§2b) with no acceptance owed.** This plan creates **no** work for the other descoped items (FU-8,
  FU-P9-OVERLAY-8K).

## 8. Constant placement (Article II / single-source)

Both in `logic/constants.py` (leaf), beside the shipped perf ceilings. **Values are AGT-01/ADR loose
candidates (DEP-1), RE-PROFILE-confirmed by AGT-10 (§9) before CI wiring.** Names DISTINCT from every
shipped ceiling.

| Constant | Candidate value | Rationale (loose bound, FU-15) / Slice |
| --- | --- | --- |
| `COMPOSITE_FULL_CEILING_MS` | `3000` | Loose catastrophic ceiling for the full-frame 8K flatten. **Mirrors the shipped full-8K `TILEMAP_VIEWPORT_CEILING_MS`=3000 precedent** (the sibling full-canvas batch path): far above the optimised cold cost (baseline §6 candidate ≈1500–2000 ms desktop; warm/off-thread well under 1 s) with 2-core headroom, **orders of magnitude below** the 20–43 s regression. **NOT** 16 ms. AGT-10 RE-PROFILE may tighten toward ≈2000 once the optimised 2-core cold cost is measured. — Slice A |
| `VIEWPORT_RECOMPOSITE_CEILING_MS` | `2000` | Loose catastrophic ceiling for the full-resolution whole-viewport recomposite (gated at ≥1080², 12L). Sits **above** the split-cache-optimised commit cost (baseline: split-cache reduces 12→≈2–3 blends) with 2-core headroom, **below** the measured 2 231 ms (1080²) / 7 024 ms (1920²) catastrophe so the gate bites on a regression. **NOT** 16 ms. AGT-10 RE-PROFILE confirms the value + gate scenario (1080² and/or 1920²) so it holds with headroom. — Slice B |

Both are consumed as **named constants** by `scripts/perf_profile.py` defaults and passed via
`--budget-ms` / `--ceiling-ms` in `.github/workflows/ci.yml` (the `COMPOSITE_REGION_CEILING_MS` /
`TILEMAP_VIEWPORT_CEILING_MS` precedent) — **no literal at any call/gate site** (Article II).

## 9. Implementation strategy — slice-by-slice (each independently gate-green / CI-green)

Detailed work items in `tasks.md`. Per-slice performance flow (the shipped Phase-9/10 pattern): **AGT-10
directive → AGT-03 (logic) / AGT-05 (ui) implement → AGT-04 (logic regression + correctness) / AGT-06 (UI
+ a11y + both themes) → AGT-10 RE-PROFILE ship gate (measures the optimised cost vs the ceiling on the CI
runner) → AGT-01 final gate → AGT-08 docs → AGT-07 i18n if strings → AGT-09 commit + gate wiring.**

- **Slice A — cold full-frame 8K flatten (`logic/`; FU-P5-PERF):** AGT-10 fast-path/tiling/dirty-tile
  directive → AGT-03 `constants` (`COMPOSITE_FULL_CEILING_MS`) + `blend.composite_stack(region=None)`
  fast-path + tiling + dirty-tile reuse (byte-exact) → AGT-04 byte-exact regression (NORMAL + 11 modes) +
  determinism + layering → AGT-10 `perf_profile --full-frame` scenario + RE-PROFILE → AGT-01 gate →
  AGT-09 CI wiring. REQ-P12-LOGIC-001/-002/-003.
- **Slice B — whole-viewport recomposite + live opacity drag (`logic/` + `ui/`; FU-16b):** AGT-10
  split-cache/LOD/cull directive → AGT-03 `constants` (`VIEWPORT_RECOMPOSITE_CEILING_MS`) + `blend`
  split-cache seam + LOD downsample helper (byte-exact commit) → AGT-05 `layer_panel` drag lifecycle
  (preview holds 16 ms; commit full-res) reusing `composite_warmer`/`frame_cache`/D3 → AGT-04 recomposite
  byte-exact + AGT-06 opacity-drag responsiveness both themes → AGT-10 `--viewport-recomposite`
  scenario + RE-PROFILE → AGT-01 gate → AGT-07 i18n (only if new strings) → AGT-09 CI wiring.
  REQ-P12-LOGIC-004/-005, REQ-P12-UI-001.
- **Slice F — artifact + docstring hygiene:** AGT-01 (plan/S-id/follow-up-id reconciliation) + AGT-02
  (traceability + scenario renumber) + AGT-08 (FU-4 `logic/` docstrings) → AGT-01 `sdd-analyze` confirms
  no FU-2/-17/-16 cross-artifact finding. REQ-P12-LOGIC-006/-007. (Executed at implement time; the
  Phase-12 `sdd-analyze` gate over Phase-12 artifacts is unaffected — the FU-2/-17 items live in Phase-1/4
  artifacts, so they are implement-time tasks, not Phase-12 analyze findings.)

**Reversibility boundary:** Phase 12 introduces **no new undoable operation** — a flatten is on-demand
output; the opacity change is already undoable via the shipped Phase-4 D3 path. **No `ui/commands.py`
change.**

## 10. Constitution compliance (self-check)

- **I:** all Slice-A/B compositing/split-cache/tiling/LOD maths stay ZERO-Qt `logic/blend.py`; the only Qt
  is the `ui/` opacity-drag preview (+ optional off-thread analytics); the one Qt file outside `ui/`
  remains `ui/commands.py` (**unchanged**). **No new module, no new edge, no new `data/` work**; baseline
  exit 0 (§11), module count unchanged.
- **II:** 2 new constants in `constants.py`, names DISTINCT from every shipped ceiling; no literal at any
  gate/call site.
- **III:** Black/isort/flake8/mypy-strict for `logic/`; typed; FU-4 completes residual `logic/` docstrings.
- **IV:** byte-exact regression (NORMAL + 11 modes) + determinism (LOGIC-002/-004) and the two
  `perf_profile` gates (LOGIC-003/-005) are the phase's test spine; opacity-drag responsiveness both
  themes (UI-001); pydocstyle (FU-4); `sdd-analyze` (FU-2/-17/-16). Headless / portable. Coverage ≥90/80.
- **VI — CENTRAL:** the two optimisations are batch/on-demand paths bounded by **loose** ceilings, **not**
  16 ms, **not asserted** against 16 ms; the **only** per-frame path (drag preview) **holds** 16 ms; the
  budget is **never relaxed**; no gate weakened (Article VIII §3).
- **VIII:** this plan + `analyze-report.md` are the pre-implement gate; **no implement dispatch until C1
  PASS**.
- **X:** every REQ traces to a dossier S-id / article / FU item + ≥ 1 acceptance scenario
  (`traceability.md`, 9 REQ); REQ-P12-LOGIC-007 is itself a traceability-consistency requirement (FU-2/-17
  + the FU-16 label collision).
- **XI:** the perf-gate harness + named-ceiling pattern extend cleanly (a new loose gate = a new scenario +
  a new named constant, no article weakened) — the finale adds hardening without rewriting any layer.

## 11. Layering / cycle verification

At plan time on the shipped tree (baseline 2026-07-07, HEAD of `feat/phase-1-core-engine`):
- `python scripts/check_layering.py --root pixelart_creator` → **`clean (178 modules)`, exit 0**.
- `python scripts/check_cycles.py --root pixelart_creator` → **`no cycles (179 modules)`, exit 0**.

(`pixelart_creator/` is the single product root; `check_layering` governs only it. There is no second
product package.) The planned Phase-12 changes **add no module and no new import edge** — they edit
existing `logic/blend.py` / `logic/constants.py` / `ui/*.py` in place — so **no `check_layering` /
`check_cycles` rule edit is required** and the module count is unchanged. AGT-03/AGT-05 re-run both
invocations as each slice lands (per-slice gate task). See `analyze-report.md` for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch / choice | Rationale |
| --- | --- | --- | --- |
| PL12-D1 | Ungrounded stack/API choice → Researcher? | **B (no)** | Stack fixed (S8); both confirmed items dependency-free (baseline §5). No RESEARCH REQUEST; no GPU decision. |
| PL12-D2 | Qt in `logic/` or magic number outside `constants.py`? | **B (no)** | All compositing maths stay Qt-free `logic/blend.py`; the 2 ceilings → `constants.py` (distinct names). |
| PL12-D3 | New module / new layering edge? | **B (no)** | Phase 12 **hardens** shipped `blend.py`/`ui/*` in place; adds no module, no edge, no `data/` work; module count unchanged. |
| PL12-D4 | New undoable operation → `ui/commands.py`? | **B (no)** | Flatten is on-demand output; opacity change already undoable via Phase-4 D3. No `ui/commands.py` change. |
| PL12-D5 | Output tolerance on the optimisation? | **NO — byte-exact, zero tolerance** | REQ-P12-LOGIC-002/-004; ADR-0005 bit-exact NORMAL preserved; fast-path admissible only if byte-identical. |
| PL12-D6 | New runtime dependency / GPU? | **B (no)** | Pure-numpy fast-paths + threading + LOD (baseline §5); no manifest change (AGT-09). |
| PL12-D7 | Ceiling altitude (FU-15) | **Loose catastrophic bounds, RE-PROFILE-confirmed; NOT 16 ms** | `COMPOSITE_FULL_CEILING_MS`=3000 (mirrors full-8K `TILEMAP_VIEWPORT_CEILING_MS`), `VIEWPORT_RECOMPOSITE_CEILING_MS`=2000; above optimised cost with 2-core headroom, below the 20–43 s / 2–7 s catastrophe. |
| PL12-D8 | Preview budget posture | **The drag preview HOLDS 16 ms (the one per-frame path); batch paths NOT asserted vs 16 ms** | Article VI §1/§2; budget never relaxed. |
| PL12-D9 | Descoped items (FU-8/-18-core/-P9) | **No work created; documented "verified, no action" (§2b)** | Measured in-budget / edge-only on `f73b1a5`; optional non-blocking follow-ups only. |
| PL12-D10 | REQ-P12-UI-002 (off-thread analytics) | **OPTIONAL / LOW; deferrable** | Not a frame path; already lazy+debounced; if deferred FU-18 stays a documented descope (§7). |
| PL12-D11 | Slice-F execution timing | **Implement-time tasks (AGT-01/02/08); NOT Phase-12 analyze findings** | FU-2/-17 live in Phase-1/4 artifacts; Phase-12 `sdd-analyze` scans Phase-12 constitution/spec/plan/tasks. |
