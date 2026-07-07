# Specification — Phase 12: Performance & Scalability

| Field | Value |
| --- | --- |
| Feature | `phase-12-performance-scalability` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-07 |
| Governed by | `constitution.md` (Articles **I**, **II**, **IV**, **VI**, **VIII**, **X**, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION — COMPLETE (no open clarifications, no SUSPEND).** Phase 12 is the **roadmap finale**: it is a **performance-NFR + doc-hygiene hardening phase, NOT a new-feature phase**. Every product behaviour it touches already ships (Phases 1–11). The spec is grounded **measure-first** in AGT-10's baseline `docs/perf/phase12-baseline.md` (measured on HEAD `f73b1a5`, 2026-07-07); it invents **no numbers** — every target is the baseline's measured cost + AGT-10's recommended loose ceiling. The two genuinely-breaching hotspots are scoped for **real optimisation work** (Slice A full-frame flatten; Slice B whole-viewport recomposite / opacity drag); three measured-in-budget / edge-only hotspots are **documented as descoped ("verified, no action")** with their evidence; one optional LOW off-thread item is **flagged, not forced**; and the C3 traceability + docstring leftovers are reconciled (Slice F). |
| REQ-ID range | `REQ-P12-LOGIC-001..007`, `REQ-P12-UI-001..002` — **9 requirements** (8 core + 1 OPTIONAL/LOW). **No `DATA` layer**: Phase 12 adds no new persistence, no serialisation, no schema (output byte-exactness is a **correctness constraint on the optimisation**, not a new format). |
| Layer scope | `pixelart_creator/logic/` (the two ungated compositor hotspots — `blend.composite_stack(region=None)` full-frame flatten and the viewport-scale region recomposite — plus residual `logic/` docstrings and the SDD-artifact reconciliation) + `pixelart_creator/ui/` (the live opacity-slider drag interaction contract; the OPTIONAL off-thread analytics compute). **Zero new `data/` work.** |
| Binds to (upstream, **shipped** — REUSED / HARDENED) | Phase 4 `logic/blend.py` (`composite_stack`, `blend_over`, the 12-mode `BlendMode` enum = NORMAL + 11 separable; ADR-0005/0007, region-sized output + float32 + LayerGroup region-cache); Phase 5 `ui/composite_warmer.py` + `ui/frame_cache.py` (off-GUI-thread flatten worker + 512 MiB LRU, deterministic teardown); Phase 4 `ui/layer_panel.py` opacity-slider + QTimer debounce (D3); `scripts/perf_profile.py` + `.github/workflows/ci.yml` (the existing perf-gate harness — `COMPOSITE_REGION_CEILING_MS=200`, `FRAME_BUDGET_MS=16`, `TILEMAP_VIEWPORT_CEILING_MS=3000`, `OVERLAY_FRAME_CEILING_MS=48`, `REALTIME_APPLY_CEILING_MS=10`); `logic/constants.py` (Article II single-source numerics). Phase 12 **hardens** these paths; it introduces no new product entity. |
| Depends on (external) | **The Researcher — NOT required.** The two confirmed items are solvable **dependency-free** (pure-numpy fast-paths, split-caching, tiling + threading, LOD-during-drag) per baseline §5. **No GPU decision and no new dependency is escalated by this spec.** |
| SDD phase | `specify` + `clarify` **COMPLETE** — no requirement is underspecified, no product-direction choice is open, no target is ungrounded (A2-D2 gate: nothing to SUSPEND). `sdd-plan` (AGT-01) is **UNBLOCKED**; the concrete ceiling **values**, the fast-path/tiling/split-cache algorithms, the off-thread wiring, and the gate wiring are AGT-01/AGT-10/AGT-09 HOW (§8). |

---

## 1. Purpose (WHY)

The platform ships eleven complete phases. Phase 12 — **Performance & Scalability** (roadmap finale) —
does not add capability; it **hardens the measured cost** of the existing engine on the 8K grid and
**closes the requirement-artifact hygiene leftovers** so the spec corpus is internally consistent at ship.

AGT-10 ran a **measure-first baseline** (`docs/perf/phase12-baseline.md`, HEAD `f73b1a5`) over the six
long-standing perf follow-ups. It found the fleet honestly:

- **Two hotspots genuinely breach and are effectively ungated** — the cold full-frame 8K multi-layer
  flatten (`composite_stack(region=None)` = **20 244 ms @ 4 layers → 42 669 ms @ 8 layers**) and the
  whole-viewport multi-layer recomposite driving the live opacity-slider drag (**2 231 ms @ 1080²
  / 7 024 ms @ 1920², 12 layers**). Both are seconds-scale UX stalls; the shipped 16-px `--composite`
  CI gate exercises **only** a 16×16 region so it cannot see either. These are **CONFIRMED work**.
- **Three hotspots are already in budget or edge-only on `f73b1a5`** — the checker background
  (**10.5 ms**, inside the 16 ms budget via F2 exposed-rect culling), palette analytics
  (**281 ms** synthetic near-worst-case / **< 100 ms** realistic, a non-frame batch path already
  lazy + debounced), and the iso overlay at a **literal** 7680×4320 viewport (**144 ms** CPU-raster,
  **cache-miss-only**; the sub-32 px pathological case is **already LOD-fixed** at 0.001 ms; GL engages
  on a real desktop). These are **DESCOPED — "verified, no action"** (§2b), each with an optional,
  non-blocking follow-up.

**The frame budget is a fixed constraint, not a target this phase moves.** Article VI's
`FRAME_BUDGET_MS = 16` (60 fps on the 7680×4320 grid) is **never relaxed** by any Phase-12 requirement.
The two confirmed items are **batch / on-demand paths** (flatten, export, merge-visible; full-resolution
recomposite on commit) that were **never 60-fps paths** — so the 16 ms budget does not *govern* them, and
their acceptance is a **loose catastrophic-regression ceiling** (a named constant, sized above the
optimised cost with headroom for the slow CI runner), **not** a 16 ms bound. The **one** per-frame path
Phase 12 introduces — the *downsampled preview* shown *during* an opacity drag — **does** hold the 16 ms
budget, exactly as Article VI requires. See §5.

**The FU-15 loose-ceiling caution is honoured throughout.** All baseline numbers come from an 8-core
desktop; the GitHub CI runner is 2-core and memory-bandwidth-constrained (**~1.5–2.5× slower** on
numpy-heavy / raster paths). Every new perf ceiling is therefore a **loose catastrophic bound**, never a
tight ~16 ms bound — and the perf REQs state targets that are **not tighter than the 2-core runner can
hold**.

## 2. Scope

**In scope now (WHAT) — CONFIRMED optimisation work (grounded, measurable):**

- **Slice A — cold full-frame 8K multi-layer flatten (`logic/`, FU-P5-PERF).** Bring
  `blend.composite_stack(region=None)` from **~20 s (4L) / ~43 s (8L)** cold down to a **defined
  acceptable cold cost** under a **loose `COMPOSITE_FULL_CEILING_MS`** ceiling, **without changing the
  output** — the flattened bytes must be **byte-exact** vs the current shipped compositor for NORMAL and
  **all 11 separable blend modes** (this bit-exactness is a first-class acceptance criterion). Add a
  **full-frame compositor perf gate** (`region=None` scenario) at that loose ceiling — the path today's
  16-px `--composite` gate is blind to (REQ-P12-LOGIC-001, -002, -003).
- **Slice B — whole-viewport / low-zoom multi-layer recomposite + live opacity-slider drag (`logic/` +
  `ui/`, FU-16 — the *opacity-drag/attr-op recomposite* follow-up, disambiguated in §2c).** Keep the
  interaction **responsive** during a drag (measured **2.2 s–7.0 s** for 12 layers today): a
  **downsampled preview during the drag holds the 16 ms budget**, and on **commit** (mouse-release) the
  **full-resolution recomposite produces the exact same final pixels as today**. Bring the
  full-resolution viewport-scale recomposite under a **loose viewport-scale ceiling** and add a
  **viewport-scale recomposite perf gate** (REQ-P12-LOGIC-004, REQ-P12-UI-001, REQ-P12-LOGIC-005).

**In scope now (WHAT) — Slice F doc-hygiene (requirement-artifact consistency):**

- **Reconcile the C3 traceability + docstring leftovers** so the requirement artifacts are internally
  consistent at the roadmap finale: FU-2 (plan/spec `REQ-P1-LOGIC-004` S1-vs-S2 mismatch), FU-17 (Phase-4
  `SC-UI-*` scenario-number collision with Phase-1), the **FU-16 label collision** (two distinct
  follow-ups both labelled "FU-16", §2c), and FU-4 (residual `logic/` docstrings)
  (REQ-P12-LOGIC-006, -007).

**In scope now (WHAT) — OPTIONAL / LOW (flagged, deferrable — phase ships complete without it):**

- **Off-thread palette-analytics compute (`ui/`, FU-18 residual).** The dock is already lazy +
  debounced (shipped in the Phase-4 8K-open perf fix); the residual is a **281 ms synthetic-worst-case**
  GUI-thread compute when the dock recomputes on a many-colour canvas. An OPTIONAL, dependency-free
  off-thread compute removes even that worst-case freeze (REQ-P12-UI-002 — **LOW, explicitly
  deferrable**).

**Out of scope (this phase):** see §2b (descoped, measured-in-budget/edge-only items) and §6 (non-goals).

### 2b. DESCOPED — measured in-budget / edge-only on HEAD `f73b1a5` (verified, NO action)

Recorded explicitly per the measure-first mandate. Each is **not** optimised this phase; each carries an
**optional, non-blocking** follow-up that AGT-10/AGT-09 may wire later without a Phase-12 acceptance
change. Evidence is AGT-10's baseline (`docs/perf/phase12-baseline.md` §2–§4).

| Item | Measured (HEAD f73b1a5) | Verdict | Why out of scope | Optional (non-blocking) follow-up |
| --- | --- | --- | --- | --- |
| **FU-8** — `drawBackground` checker at fit zoom | **10.5 ms** median (8 160 fillRects, 8K, tile 64, 1920×1080) vs 16 ms | **IN BUDGET** | The historical ~95 ms / 73k-fillRect figure was the pre-culling whole-scene draw; the shipped `drawBackground` paints **only the exposed rect (F2)** — that *is* the fix. | Promote the tiling mode into CI at a **loose** ceiling (≈40–48 ms) to catch a culling regression — **never** a tight 16 ms bound (it is ~65 % of budget on desktop; the 2-core runner + shared frame could exceed 16 ms). |
| **FU-18** — palette analytics on a huge canvas | **281 ms** synthetic near-worst (~16.7 M distinct colours) / **< 100 ms** realistic; already lazy + debounced | **DESCOPE (borderline)** | Not a 60-fps path (on-demand dock compute; `FRAME_BUDGET_MS` does not apply); already a ~995× improvement (Phase-4 8K-open fix). | If the dock recomputes live on every edit, add **off-thread** compute — captured as OPTIONAL **REQ-P12-UI-002** (LOW). |
| **FU-P9-OVERLAY-8K** — iso overlay densest-drawn | **144 ms** only at a **literal** 7680×4320 viewport, CPU-raster, **cache-miss-only**; sub-32 px case **already LOD-fixed** (0.001 ms); GL engages on desktop; realistic 1920×1080 passes the shipped 48 ms gate | **DESCOPE (borderline)** | `DeviceCoordinateCache` pays 144 ms only on cache-miss frames (zoom/config change), not steady-state pan; `perf_profile --overlay` times CPU-raster into a QImage and never exercises the GL viewport, so 144 ms is the raster-fallback cost, not the working-GL desktop cost. | Dependency-free line-budget LOD (cap device-pixel lines/frame) + an `--ov-viewport 7680 4320 --ov-tile 32` scenario at a **loose** ceiling to guard the raster fallback. **No GPU dependency needed.** |

**Genuinely still breaching → scoped as real work:** FU-P5-PERF (Slice A) and FU-16 (Slice B).
**Effectively in budget / edge-only → descoped:** FU-8, FU-18, FU-P9-OVERLAY-8K.

### 2c. The FU-16 label collision (disambiguated here; reconciled by REQ-P12-LOGIC-007)

Two **distinct** follow-ups both carry the label "FU-16" in the session decision/ledger records — a
tracking-identifier collision Slice F resolves:

- **FU-16 (a) — cache-invalidation completeness (optional):** non-`document` `LogicCommand` buffer ops
  (tiled / transform / dither / cycle / swap / constraint / selection-move) do not self-invalidate the
  `LayerGroup` flatten cache; `ui/` covers it defensively in `_recomposite_all`. Correctness is
  maintained; this is an optional micro-optimisation (owner AGT-03). **Not** the Phase-12 Slice-B subject.
- **FU-16 (b) — whole-viewport recomposite / opacity-drag CPU cost:** the attr-op / opacity-drag
  recomposite is still CPU-bound (2.2 s–7.0 s @ 12 layers). **This** is Phase-12 **Slice B**
  (REQ-P12-LOGIC-004 / REQ-P12-UI-001 / REQ-P12-LOGIC-005).

Slice F assigns each a **distinct, non-colliding identifier** in the requirement artifacts so no future
reader conflates them (REQ-P12-LOGIC-007).

## 3. Story map & user stories

Backbone activity → stories, each tagged with a kebab-case feature label + roadmap phase (§3.2). Phase 12
is NFR/hygiene, so the "users" are the artist experiencing the stall and the maintainer keeping the
artifacts consistent + regression-gated. **No story has an open clarification.**

### 3.1 User stories

- **US-1 (Artist / fast-flatten).** As an artist flattening / exporting / merging-visible a large 8K
  multi-layer document, I want the full-frame flatten to complete in an **acceptable, bounded time**
  (not the current 20–43 s freeze) — **with pixel-for-pixel identical output** to today. →
  REQ-P12-LOGIC-001, -002 · `fast-flatten` · P12
- **US-2 (Maintainer / regression-gated flatten).** As a maintainer, I want a **CI perf gate on the
  full-frame flatten** so this catastrophic path can never silently regress again (today's 16-px gate is
  blind to it). → REQ-P12-LOGIC-003 · `perf-gate` · P12
- **US-3 (Artist / responsive opacity drag).** As an artist dragging a layer's opacity slider on a
  low-zoom, many-layer document, I want the canvas to **stay responsive** (live preview, not a
  multi-second stall) and the **committed result to be exactly what it is today**. →
  REQ-P12-LOGIC-004, REQ-P12-UI-001 · `responsive-drag` · P12
- **US-4 (Maintainer / regression-gated recomposite).** As a maintainer, I want a **viewport-scale
  recomposite CI gate** so the whole-viewport recomposite blow-up the 16-px gate misses is caught. →
  REQ-P12-LOGIC-005 · `perf-gate` · P12
- **US-5 (Maintainer / consistent artifacts).** As a maintainer at the roadmap finale, I want the
  requirement artifacts **internally consistent** — no S1-vs-S2 trace mismatch, no colliding scenario
  numbers, no colliding follow-up label, no residual missing docstrings. →
  REQ-P12-LOGIC-006, -007 · `doc-hygiene` · P12
- **US-6 (Artist / no analytics freeze — OPTIONAL).** As an artist with the palette-analytics dock open
  on a many-colour canvas, I want a live recompute to **never freeze the GUI** even in the worst case. →
  REQ-P12-UI-002 (OPTIONAL/LOW) · `responsive-batch` · P12

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase | Status |
| --- | --- | --- | --- |
| `fast-flatten` | Cold full-frame 8K multi-layer flatten bounded by a loose ceiling; output byte-exact. | 12 | drafted |
| `responsive-drag` | Whole-viewport recomposite + opacity drag: preview holds 16 ms, commit output unchanged. | 12 | drafted |
| `perf-gate` | Loose catastrophic-regression CI ceilings on the two previously-ungated compositor hotspots. | 12 | drafted |
| `doc-hygiene` | Requirement-artifact consistency (FU-2/-17/-16-collision) + residual `logic/` docstrings (FU-4). | 12 | drafted |
| `responsive-batch` | OPTIONAL off-thread analytics compute so a worst-case recompute never freezes the GUI (FU-18). | 12 | drafted (OPTIONAL/LOW) |

---

## 4. Functional requirements — FULLY DRAFTED

Each REQ is a technology-neutral WHAT statement with **measurable** acceptance grounded in the baseline.
Concrete ceiling **values**, the fast-path / tiling / split-cache **algorithms**, the off-thread + gate
**wiring**, and the reconciliation **edits** are downstream HOW (§8). A binding to a shipped callable is a
**constraint**, not a HOW choice.

### `logic/` — Slice A: cold full-frame 8K multi-layer flatten (FU-P5-PERF)

#### REQ-P12-LOGIC-001 — Cold full-frame flatten brought to a defined acceptable cold cost *(NFR, Article VI batch posture)*
`traces:` S1 (8K grid), S12 (perf), Article VI (§1 budget is a constraint; batch paths are not 60-fps paths), Article II, baseline §2 #1/#1b + §3 FU-P5-PERF + §6, FU-P5-PERF
The cold full-frame 8K multi-layer flatten — `blend.composite_stack(region=None)` over the full
`(4320, 7680, 4)` canvas — is brought from its measured **~20 244 ms (4 layers) / ~42 669 ms (8 layers)**
cold cost down to a **defined acceptable cold cost** by the dependency-free numpy fast-path + tiling +
off-thread strategy (baseline §3; ADR-0033, AGT-01). The **acceptance gate targets REALISTIC pixel-art
content** — a typical layer count (≤ 8 layers) at **normal sparsity/alpha**, predominantly **NORMAL-mode,
opacity-1, unmasked** layers (so the uint8 source-over fast path applies to most layers), with only a
minority of genuinely non-normal / masked / partial-opacity layers (see the concrete definition below) —
which is **bounded by a loose named ceiling `COMPOSITE_FULL_CEILING_MS`** and passes it with margin
(measured optimised: **~1.5 s @ 4 layers, ~3.4 s @ 8 layers** realistic — a **3.3–12× speed-up** vs the
current 19–37 s). The flatten is a **batch / on-demand op** (flatten, export, merge-visible) — **not** the
per-frame render loop — so Article VI's 16 ms `FRAME_BUDGET_MS` **does not govern it and is neither applied
nor relaxed** here; the loose ceiling is a **catastrophic-regression bound on realistic content**, sized
**above** the optimised realistic cost with headroom for the **~1.5–2.5× slower 2-core CI runner**
(FU-15 caution) — **never** a tight 16 ms bound. **The exact ceiling value is an AGT-01/ADR-0033 HOW**
(§8 DEP-1).

**Realistic vs pathological (concrete definition).** *Realistic pixel-art content* = layers reflecting
typical authoring: a typical layer count (**≤ 8 layers**), each layer at **normal sparsity** (substantial
transparent/empty area — **not** every pixel painted), predominantly **NORMAL** blend at **opacity 1.0**
on **unmasked** layers (so the uint8 source-over fast path applies to the majority), with only a minority
requiring float promotion. This is grounded in the baseline's realistic-vs-dense distinction (baseline §3
FU-P5 "the common case" uint8 fast path; §3 FU-18 "real pixel-art has tens–hundreds of colours"). It is
explicitly **contrasted** with the synthetic **PATHOLOGICAL dense** worst case — **every pixel painted on
every layer AND every layer in a non-normal separable blend mode** — which forces full-canvas float
promotion across all 33 M px × every layer (baseline §2 #1b / §3 FU-P5-PERF).

**The pathological fully-dense worst case is NOT a gated failure.** The rare dense worst case cannot meet
the loose ceiling **dependency-free** (measured optimised **~12.8 s @ 8 layers 8K**, memory-bandwidth
floored at **~5 s** even under ideal threading — see the rationale). It is instead handled by two explicit
guarantees: **(a)** it is **computed OFF the GUI thread** via the existing Phase-5 `composite_warmer`
substrate (which has kept flatten off-thread since Phase 5), so the **UI stays responsive / never freezes**
during it; and **(b)** its cold cost is a **documented, ACCEPTED cold-cost — explicitly NOT a Phase-12
acceptance failure and NOT gated against `COMPOSITE_FULL_CEILING_MS`**. Output invariance holds for
**both** realistic and pathological content (REQ-P12-LOGIC-002, UNCHANGED).

**Rationale (why the gate is realistic-content, not dense).** Byte-exactness (REQ-P12-LOGIC-002) pins the
separable-blend math to a **float64 floor** for non-normal layers; the fully-dense every-pixel-every-layer
case is therefore **memory-bandwidth-floored at ~5 s** even under ideal threading and cannot reach the
loose ceiling without native acceleration. A **native-acceleration dependency (numba / Cython) WOULD meet
it but was CONSIDERED AND DECLINED BY THE USER** to keep the app **dependency-free / portable** for the
upcoming **Phase-13 cross-platform + mobile** targets. The chosen resolution — **realistic-content gate +
off-thread pathological compute + accepted cold-cost** — preserves portability while keeping the realistic
common case fast and the UI responsive in every case.
**Acceptance:** a cold full-frame `composite_stack(region=None)` at 8K over a **REALISTIC 8-layer
pixel-art stack** (normal sparsity/alpha, predominantly NORMAL-mode / opacity-1 / unmasked, per the
definition above) completes **at or under `COMPOSITE_FULL_CEILING_MS`** (and the realistic 4-layer case
comfortably under it), measured headless by `perf_profile --full-frame` on the CI runner; the catastrophic
~20–43 s cost is eliminated for realistic content (measured ~1.5 s / ~3.4 s optimised). The **synthetic
PATHOLOGICAL fully-dense worst case** (every pixel painted on every layer in non-normal modes) is **NOT
gated against `COMPOSITE_FULL_CEILING_MS`**: it is instead required to run **off the GUI thread** (via the
Phase-5 `composite_warmer`, so the UI stays responsive) and its cold cost (~12.8 s @ 8 layers) is a
**documented ACCEPTED cold-cost, not a failure**. The operation is not asserted against the 16 ms
per-frame budget; `check_layering` confirms the compositor stays Qt-free `logic/`.

#### REQ-P12-LOGIC-002 — Full-frame flatten output invariance (byte-exact) *(correctness constraint on the optimisation)*
`traces:` P2 (determinism), Article I (no behaviour change), Article IV (regression tests), ADR-0005/0007 (float32 + region-sized contract), baseline §3 FU-P5-PERF ("WITHOUT changing output"), FU-P5-PERF
The optimised flatten **must not change the produced pixels**. Its output is **byte-identical** to the
current shipped `composite_stack` for **NORMAL** and **all 11 separable blend modes** (the full 12-mode
`BlendMode` set), across representative layer counts, opacities, and masks. Any fast path (e.g. a uint8
source-over path for NORMAL/opacity-1/unmasked layers, promoting to float32 only for genuinely non-normal
layers — baseline §3) is admissible **only if** it reproduces the current bytes exactly; the shipped
NORMAL integer bit-exact contract (FLAG-04-1) is preserved. This is a **first-class acceptance
criterion**, not a tolerance.
**Acceptance:** for NORMAL and each of the 11 separable modes, the optimised full-frame flatten produces a
buffer **byte-equal** to the current shipped compositor's output over the same inputs (bit-exact, no
tolerance); the result is deterministic (same inputs ⇒ byte-identical across runs); no blend mode is
dropped or altered.

#### REQ-P12-LOGIC-003 — Full-frame compositor perf gate *(NFR, Article VI verification / FU-15 loose-gate)*
`traces:` S12, Article VI (§2 verified headless by `perf_profile`), Article II, baseline §1 (ungated audit) + §6 FU-P5, FU-15 (loose ceiling), FU-P5-PERF
A **new `perf_profile` full-frame scenario** (a `region=None` branch, e.g. `--full-frame`) exercises the
full-canvas flatten and is gated in CI at the **loose `COMPOSITE_FULL_CEILING_MS`** ceiling — closing the
gap that today's `--composite` gate (which only composites a 16×16 region, baseline §1) is structurally
blind to. The ceiling is a **single-source named constant** (Article II); its **value** and the
scenario/gate **wiring** are AGT-10 (scenario) / AGT-01 (value) / AGT-09 (CI) HOW (§8). The gate is a
**loose catastrophic-regression bound**, not a 16 ms bound (FU-15).
**Acceptance:** a `perf_profile` full-frame (`region=None`) scenario exists and, run in CI, passes when
the flatten is at/under `COMPOSITE_FULL_CEILING_MS` and **fails** on a catastrophic regression toward the
20–43 s cost; the ceiling resolves to a named constant (no literal at the call site).

### `logic/` + `ui/` — Slice B: whole-viewport recomposite + live opacity drag (FU-16 (b))

#### REQ-P12-LOGIC-004 — Viewport-scale multi-layer recomposite cost reduced; commit output unchanged *(NFR, Article VI batch posture)*
`traces:` S1, S12, Article VI (batch commit path, not 60-fps), Article I (output unchanged), Article II, baseline §2 #2/#2b + §3 FU-16 + §6, FU-16 (b)
The **full-resolution** recomposite of a whole-viewport region (up to ~1920², the low-zoom / whole-canvas
case) over a **many-layer (≥ 12) stack** — measured **2 231 ms (1080²) / 7 024 ms (1920²)** cache-cold at
12 layers — is brought under a **loose named ceiling `VIEWPORT_RECOMPOSITE_CEILING_MS`** (candidate value
an AGT-01/ADR HOW, §8; sized above the optimised cost with 2-core headroom, FU-15 — **not** a 16 ms
bound). The **committed** full-resolution pixels are **unchanged** vs the current build (a correctness
constraint — the optimisation is split-caching / culling / LOD-on-commit, never an output change). The
recomposite stays Qt-free `logic/` (any split-cache of `composite(below)` / `composite(above)` around the
dragged layer, and dirty-region culling to the true exposed rect, live in `logic/` — baseline §3).
**Acceptance:** a full-resolution whole-viewport recomposite (up to 1920², ≥ 12 layers) completes at/under
`VIEWPORT_RECOMPOSITE_CEILING_MS` on the CI runner (the 2–7 s catastrophe eliminated); the committed
result is **byte-exact** vs the current compositor over the same inputs; the recomposite path imports no
Qt (`check_layering` passes); it is not asserted against the 16 ms per-frame budget.

#### REQ-P12-UI-001 — Live opacity-slider drag stays interactive (preview holds 16 ms; commit output unchanged) *(NFR, Article VI — per-frame preview + stays-responsive)*
`traces:` REQ-P12-LOGIC-004, Article VI (§1 — the preview *is* on the per-frame loop, so 16 ms **applies**), Article V, S1, baseline §3 FU-16 (LOD-during-drag; full-res on release), FU-16 (b), Phase-4 D3 (opacity-drag debounce)
While the user **drags** a layer's opacity slider on a low-zoom, many-layer document, the canvas gives
**responsive per-tick feedback** — a **downsampled preview** recomposite that **holds the 16 ms
`FRAME_BUDGET_MS`** (this feedback **is** on the per-frame render loop, so Article VI's budget **applies**
and is **held**, not relaxed). The UI **never stalls for seconds** during the drag. On **commit**
(mouse-release / drag-end) the **full-resolution** recomposite (REQ-P12-LOGIC-004) is applied and the
**final on-screen pixels are identical to the current build**. Whether the preview uses a downsampled LOD
+ split-cache + throttle/off-thread is a HOW (AGT-05/AGT-10, §8); this REQ fixes the observable
**preview-holds-16 ms + stays-responsive + commit-output-unchanged** contract.
**Acceptance:** during an opacity-slider drag on a low-zoom ≥ 12-layer 8K document, per-tick preview
feedback holds the 16 ms budget and the UI stays responsive (no multi-second freeze); on release the
full-resolution recomposite is applied and the committed pixels match the current build (byte-exact per
REQ-P12-LOGIC-004); both light and dark themes behave identically.

#### REQ-P12-LOGIC-005 — Viewport-scale recomposite perf gate *(NFR, Article VI verification / FU-15 loose-gate)*
`traces:` S12, Article VI (§2), Article II, baseline §1 (effectively ungated) + §6 FU-16, FU-15, FU-16 (b)
The shipped `perf_profile --composite` gate is **extended** with a **viewport-scale scenario** (region
1080² and/or 1920², 12 layers) at a **loose `VIEWPORT_RECOMPOSITE_CEILING_MS`** ceiling, so the
whole-viewport recomposite blow-up the current **16-px** `--composite` gate cannot catch (baseline §1) is
guarded. Ceiling is a single-source named constant (Article II); value + scenario + CI wiring are
AGT-01/AGT-10/AGT-09 HOW (§8). Loose catastrophic bound, not 16 ms (FU-15).
**Acceptance:** a `perf_profile` viewport-scale composite scenario (≥ 1080², 12 layers) exists and, in CI,
passes at/under `VIEWPORT_RECOMPOSITE_CEILING_MS` and **fails** on a regression toward the 2–7 s cost;
the ceiling resolves to a named constant.

### `logic/` — Slice F: requirement-artifact + docstring hygiene (C3 leftovers)

#### REQ-P12-LOGIC-006 — Residual `logic/` docstrings completed (FU-4)
`traces:` Article III (quality), §6.7 (maintainability), FU-4 (pydocstyle D101/D102/D105/D107 residuals)
The residual missing docstrings in `pixelart_creator/logic/` flagged by `pydocstyle` (FU-4 — 22 found in
Phase 1, tracked as ~27 residual across later phases; D101/D102/D105/D107) are **completed** so the source
docstrings are consistent with the published-docs contract (PEP 257). Doc-only; **no runtime behaviour
changes** (Article I). Owner is AGT-08 on `logic/` source (this REQ is layered `LOGIC` because its subject
is `logic/` source docstrings). **This spec writes only under `specs/`; it does not touch `docs/`.**
**Acceptance:** `pydocstyle` reports **zero** D101/D102/D105/D107 findings on the previously-flagged
`logic/` modules; no runtime code path changes (tests unaffected).

#### REQ-P12-LOGIC-007 — Requirement-artifact / traceability consistency reconciled (FU-2, FU-17, FU-16 label collision)
`traces:` Article X (§2 traceability), Article VIII (artifact-consistency at the gate), S16, FU-2, FU-17, FU-16 (label collision, §2c)
The C3 requirement-artifact leftovers are reconciled so the SDD artifact corpus is **internally
consistent** at the roadmap finale:
- **FU-2** — the `REQ-P1-LOGIC-004` grounding mismatch (Phase-1 `plan.md` §9 says "via S1/drawing"; the
  spec/traceability say S2) is resolved to a **single, consistent S-id** across plan, spec, and
  traceability.
- **FU-17** — the Phase-4 `SC-UI-*` acceptance-scenario numbers that **collide** with Phase-1's are given
  **phase-unique scenario identifiers** so no `SC-UI-NNN` id refers to two different scenarios across
  phases.
- **FU-16 label collision** — the two distinct follow-ups both labelled "FU-16" (§2c: the
  cache-invalidation-completeness item vs the opacity-drag recomposite item) are given **distinct,
  non-colliding identifiers** in the requirement artifacts.
This REQ is layered `LOGIC` because the reconciled identifiers are predominantly logic/UI SDD artifacts;
it changes **artifact text only** under `specs/` (AGT-01/AGT-02 own the plan/spec/traceability), **no
runtime code**, and **no `docs/`**. It is a traceability-consistency requirement (Article X), not a
behaviour change.
**Acceptance:** `REQ-P1-LOGIC-004` traces to one consistent S-id across plan/spec/traceability (FU-2
closed); no `SC-UI-*` scenario id denotes two different scenarios across Phase-1 and Phase-4 (FU-17
closed); each of the two former "FU-16" follow-ups has a distinct identifier in the artifacts (collision
closed); `sdd-analyze` reports no cross-artifact traceability finding attributable to FU-2/-17/-16.

### `ui/` — OPTIONAL / LOW (flagged, deferrable)

#### REQ-P12-UI-002 — *(OPTIONAL / LOW)* Off-thread palette-analytics compute (FU-18 residual)
`traces:` Article VI (batch posture), Article V, baseline §3 FU-18 (281 ms synthetic worst / < 100 ms realistic; non-frame batch path), FU-18
**OPTIONAL, LOW priority — the phase ships complete without it.** The palette-analytics dock is already
lazy + debounced (shipped in the Phase-4 8K-open perf fix). The residual is that when the dock recomputes
on a many-colour canvas, the compute (**281 ms synthetic near-worst-case**, `< 100 ms` realistic) runs on
the GUI thread and can briefly freeze it. If adopted, the recompute runs **off the GUI thread**
(dependency-free), so even the worst-case many-colour canvas cannot freeze the UI. This is **not** a
frame-budget item (`FRAME_BUDGET_MS` does not apply). Whether to build it is an orchestrator/AGT-01 call;
if deferred, FU-18 remains a documented "verified, no action" descope (§2b).
**Acceptance (if adopted):** a live palette-analytics recompute on a near-worst-case many-colour 8K canvas
does not freeze the GUI thread (the compute runs off-thread; the dock updates when it completes); the
result is unchanged vs the current compute; the operation is not gated by the 16 ms per-frame budget.
**If deferred:** FU-18 stays descoped per §2b with no acceptance owed this phase.

## 5. Non-functional requirements (constitution-tied) — and the FIXED budget constraint

Phase 12 is **entirely** NFR + hygiene; the requirements above are the NFRs. Cross-cutting rules:

- **Article VI is a CONSTRAINT, not a target this phase moves.** `FRAME_BUDGET_MS = 16` (60 fps on
  7680×4320) is **never relaxed** by any Phase-12 requirement. The two confirmed optimisations govern
  **batch / on-demand** paths (full-frame flatten; full-resolution recomposite on commit) that were
  **never 60-fps paths**, so they are bounded by **loose catastrophic-regression ceilings**
  (`COMPOSITE_FULL_CEILING_MS`, `VIEWPORT_RECOMPOSITE_CEILING_MS`) — **not** by 16 ms. The **only**
  per-frame path introduced (the *preview during* an opacity drag, REQ-P12-UI-001) **holds** the 16 ms
  budget exactly as Article VI requires. No requirement here weakens a gate (Article VIII §3).
- **FU-15 loose-ceiling caution (honoured):** all baseline numbers are 8-core desktop; the 2-core CI
  runner is ~1.5–2.5× slower on numpy/raster paths. Every new ceiling is a **loose** bound sized above
  the optimised cost with runner headroom; targets are **not tighter than the 2-core runner can hold**.
- **Article II (bounded numerics):** `COMPOSITE_FULL_CEILING_MS` and `VIEWPORT_RECOMPOSITE_CEILING_MS`
  are **single-source named constants** (values = AGT-01/ADR HOW, §8); no literal at any call/gate site.
- **Article I (three-layer purity):** the compositor optimisations stay Qt-free `logic/`; the only Qt is
  `ui/` (opacity-drag preview; optional off-thread analytics). No new `data/` work.
- **Article IV (testing):** the byte-exactness constraints (REQ-P12-LOGIC-002, -004) and the perf gates
  (REQ-P12-LOGIC-003, -005) are the phase's test spine — regression tests prove output invariance; the
  gates prove the cost bound (AGT-04 logic, AGT-06 UI/acceptance).
- **Article X (traceability):** every REQ traces to a dossier S-id / article / FU item + ≥ 1 acceptance
  scenario (matrix, §9). REQ-P12-LOGIC-007 is itself a traceability-consistency requirement.

## 6. Non-goals (explicit)

- **Relaxing `FRAME_BUDGET_MS`** — forbidden (Article VI §2 / Article VIII §3). The budget is a fixed
  constraint; this phase optimises *under* it, never moves it.
- **New features / new product entities / new persistence or serialisation** — Phase 12 is NFR + hygiene
  only; **no `DATA` layer**, no new schema. Output byte-exactness is a *correctness constraint*, not a
  new format.
- **Optimising the descoped items** (FU-8, FU-18-core, FU-P9-OVERLAY-8K) — measured in-budget / edge-only
  on `f73b1a5` (§2b); documented "verified, no action" with optional non-blocking follow-ups. (FU-18 has
  one OPTIONAL/LOW off-thread REQ, flagged, deferrable.)
- **A GPU / new-dependency decision** — the two confirmed items are solvable dependency-free (baseline §5);
  no escalation is raised. (The only place a GPU escalation *could* arise — forcing GL to fix the 144 ms
  CPU-raster iso worst case — is descoped and has a dependency-free LOD mitigation.)
- **HOW** — concrete ceiling **values**, the fast-path / tiling / split-cache / LOD algorithms, the
  off-thread + gate wiring, and the reconciliation edits are AGT-01/AGT-10/AGT-09 (§8). No plan/tasks/code
  (AGT-01/03/05); no tests (AGT-04/06); this spec touches only `specs/**` and never `docs/**`.

## 7. Dependencies & assumptions

- **Grounded measure-first** in `docs/perf/phase12-baseline.md` (HEAD `f73b1a5`, AGT-10, 2026-07-07) —
  the authoritative source for current costs, targets, and which items are descoped. This spec invents no
  numbers.
- **All upstream substrate is shipped and REUSED/HARDENED:** Phase-4 `blend.composite_stack`
  (region-sized output, float32, LayerGroup region-cache; ADR-0005/0007), the 12-mode `BlendMode` enum
  (bit-exact NORMAL, FLAG-04-1); Phase-5 `composite_warmer` + `frame_cache` (off-thread flatten worker +
  bounded LRU, deterministic teardown); Phase-4 opacity-slider + D3 debounce; `scripts/perf_profile.py` +
  CI. Phase 12 composes/hardens these; it re-implements none of them (Article I).
- **The Researcher is NOT required** and **no GPU / new dependency** is escalated — both confirmed items
  are dependency-free (baseline §5).
- **A2-D2 ambiguity gate:** no requirement is underspecified and no two requirements conflict; every
  target is grounded in the baseline. **Nothing is SUSPENDED.**

## 8. Behaviours flagged for AGT-01 / AGT-10 / AGT-09 (not blockers; HOW)

- **DEP-1 (AGT-01 / ADR — ceiling values):** concrete values for `COMPOSITE_FULL_CEILING_MS` (candidate
  ≈ 1500–2000 ms per baseline §6) and `VIEWPORT_RECOMPOSITE_CEILING_MS`, sized as **loose** bounds above
  the optimised cost with 2-core headroom (FU-15). Single-source in `logic/constants.py` (or the perf
  constants module) per Article II. An ADR is expected for the flatten/recomposite optimisation strategy.
- **DEP-2 (AGT-01 / AGT-03 — algorithms):** the uint8 source-over fast path + float32-only-for-non-normal,
  tiling + thread-pool fan-out, dirty-tile flatten cache (Slice A); the split-cache of
  `composite(below)`/`composite(above)` around the dragged layer + viewport dirty-region culling + LOD
  preview (Slice B). All must preserve byte-exact output (REQ-P12-LOGIC-002, -004).
- **DEP-3 (AGT-10 — perf scenarios) + (AGT-09 — CI wiring):** author the `perf_profile` `--full-frame`
  (region=None) scenario and the viewport-scale `--composite` scenario; wire both into CI at the loose
  named ceilings; also (optional, non-blocking) the FU-8 loose-regression tiling gate (≈40–48 ms) and the
  FU-P9 iso raster-fallback line-budget gate (§2b).
- **DEP-4 (AGT-05 / AGT-10 — drag preview HOW):** the downsampled-LOD preview + throttle/off-thread of
  opacity-drag ticks (REQ-P12-UI-001), reusing the Phase-4 D3 debounce and Phase-5 off-thread substrate.
- **DEP-5 (AGT-01 / AGT-02 / AGT-08 — Slice F edits):** the FU-2/-17/-16-collision reconciliations
  (plan/spec/traceability text) and the FU-4 docstring pass (`logic/` source). Artifact/source text only,
  no runtime change, no `docs/**` touched by this spec.

## 9. Traceability

See `specs/phase-12-performance-scalability/traceability.md` — REQ ↔ dossier S-id / article / FU item ↔
acceptance scenario ↔ (future) test. **All 9 REQs carry ≥ 1 Gherkin scenario** (`acceptance.md`) and a
matrix row; REQ-P12-UI-002 is marked OPTIONAL/LOW. No REQ is untraced or uncovered.

## 10. Clarifications

**None open.** Per the A2-D2 ambiguity gate, no requirement is underspecified and no product-direction
choice is unresolved: Phase 12 adds no features (nothing to disambiguate about behaviour); every target is
the baseline's measured cost + AGT-10's recommended loose ceiling; the FU-18 off-thread item is captured
as an explicitly OPTIONAL/LOW requirement (flagged, not forced) rather than a guess. The only deferred
items are **HOW** (ceiling values + algorithms + wiring, §8), which the house pattern routes to AGT-01 —
not clarifications. **This spec is COMPLETE and `sdd-plan` (AGT-01) is UNBLOCKED.**
