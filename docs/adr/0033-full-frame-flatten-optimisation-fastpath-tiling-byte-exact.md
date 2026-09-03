# ADR-0033 — Full-frame 8K flatten optimisation: uint8 source-over fast-path + blocked/tiled working set + dirty-tile reuse, under a byte-exact invariant

| Field | Value |
| --- | --- |
| Status | **Accepted** (amended 2026-07-07 — Slice-A resolution; see Amendment below) |
| Date | 2026-07-07 |
| Amended | 2026-07-07 — Slice-A resolution: realistic-content gating + off-thread dense case; supersedes the §1 uint8-byte-exactness and §5 dense-ceiling claims |
| Author | Architecture |
| Feature | `phase-12-performance-scalability` (`REQ-P12-LOGIC-001`, `REQ-P12-LOGIC-002`, `REQ-P12-LOGIC-003`; FU-P5-PERF / Slice A) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/phase-12-performance-scalability/spec.md` §2/§4/§8; `docs/perf/phase12-baseline.md` §2 #1/#1b, §3 FU-P5-PERF, §5, §6; constitution Article I / II / IV / VI / VIII; ADR-0005 (blend working space + straight-alpha, bit-exact NORMAL) / ADR-0007 (region-scoped recomposite, full-canvas alloc) |

## Context

Rendering & Performance's measure-first baseline (HEAD `f73b1a5`) found the cold full-frame 8K multi-layer flatten —
`logic/blend.py::composite_stack(region=None)` over the full `(4320, 7680, 4)` canvas — costs **20 244 ms
@ 4 layers → 42 669 ms @ 8 layers** (baseline §2 #1/#1b). It is a **batch / on-demand** op (flatten,
export, merge-visible), **not** a 60-fps path, so Article VI's 16 ms `FRAME_BUDGET_MS` does not *govern*
it — but 20–43 s is an unacceptable UX stall. The path is **effectively ungated**: the shipped
`perf_profile --composite` CI gate composites only a 16×16 region (~0.77 ms), and `composite_stack` has
**no `region=None` branch** in the gate, so the catastrophic full-frame cost is invisible to CI (baseline
§1, §4).

The cost cause (baseline §3): `composite_stack(region=None)` allocates a full `(4320,7680,4)` result and
runs the **float32 separable blend over all 33 M px × every layer**, with per-layer full-canvas
temporaries — linear in layers, full-canvas each call, and paying the float32 round-trip even for the
common NORMAL / opacity-1 / unmasked layer. The shipped output must **not change**: Phase 1–11 depend on
the exact flattened bytes, and ADR-0005's bit-exact NORMAL contract (FLAG-04-1, the float64
`_blend_over_arrays` path) is a frozen invariant. The optimisation is dependency-free (baseline §5) — no
GPU, no new dependency is escalated.

## Decision

**Speed up `composite_stack(region=None)` in place with three dependency-free, byte-exact techniques —
never re-implementing the compositor and never changing the produced pixels.**

### 1. uint8 straight-alpha source-over fast-path for the common case (REQ-P12-LOGIC-001/-002)

- For layers that are **NORMAL mode, opacity 1.0, unmasked**, composite via a uint8 straight-alpha
  source-over path that is **byte-identical** to the shipped float64 `_blend_over_arrays` base case
  (ADR-0005 / FLAG-04-1), skipping the float32 round-trip. Promote to float32 **only** for genuinely
  non-normal / partial-opacity / masked layers (the existing `_composite_float` path, unchanged). This
  removes most of the 33 M-px float conversions.
- **Admissibility rule:** the fast-path is used **only where** it reproduces the current bytes exactly; it
  is a routing optimisation over the existing bit-exact primitives, not a new blend formula.

### 2. Blocked / tiled working set, optionally thread-pool-fanned (REQ-P12-LOGIC-001)

- Tile the full-frame flatten into disjoint blocks and drive each tile through the already-fast region
  compositor (`_composite_region(x, y, w, h)`), blitting each tile at its origin into the full-canvas
  result. Because tiles are **disjoint** and each is composited by the same `_composite_region` used
  today, the tiled full-frame result is **byte-identical** to the single-shot
  `_composite_region(0, 0, W, H)` — there is no cross-tile blend state. Bound the per-tile working set to
  cut peak memory.
- Tiles may be fanned across a thread pool (numpy releases the GIL inside the vectorised blend); the
  reduction order is fixed and disjoint, so threading does **not** perturb output (deterministic).

### 3. Dirty-tile flatten-cache reuse + optional off-thread (REQ-P12-LOGIC-001)

- Cache the flattened buffer per tile and recompute only changed tiles, reusing the existing
  `_flatten_group` MRU-cache precedent + `document.py`'s ancestor-chain invalidation, so a stale tile can
  never render a wrong composite.
- Where non-trivial, run the whole op off the GUI thread via the shipped Phase-5 `ui/composite_warmer.py`
  substrate with a progress cue (a `ui/` concern; `logic/` stays Qt-free). Whether/how the warmer is
  reused is a UI implementation/Rendering & Performance HOW.

### 4. Byte-exact output invariant is a first-class acceptance criterion (REQ-P12-LOGIC-002)

- The optimised full-frame flatten produces a buffer **byte-equal** to the current shipped `composite_stack`
  for **NORMAL and all 11 separable modes**, across representative layer counts / opacities / masks, with
  **zero tolerance**, and is **deterministic** (same inputs ⇒ byte-identical across runs). The test suite's
  regression tests over the 12 modes are the gate.

### 5. A loose full-frame perf gate (REQ-P12-LOGIC-003, Article II / VI / FU-15)

- A new `perf_profile` `--full-frame` (`region=None`) scenario exercises the full-canvas flatten; CI gates
  it at the **single-source named constant `COMPOSITE_FULL_CEILING_MS`** (`logic/constants.py`, candidate
  **3000 ms** — mirroring the shipped full-8K `TILEMAP_VIEWPORT_CEILING_MS`=3000; **SUPERSEDED — this
  3000 ms is the pre-RE-PROFILE *candidate*, retained as the record of what was planned. The finalised
  single-source value is `COMPOSITE_FULL_CEILING_MS` = 15000 ms in `logic/constants.py`; see the "Ceiling
  finalised at 15000 ms" amendment below**). It is a **loose
  catastrophic-regression bound**, sized above the optimised cost with 2-core-runner headroom (FU-15),
  **not** a 16 ms bound and **not** asserted against the frame budget. Rendering & Performance's RE-PROFILE ship gate
  confirms/tightens the value against the measured optimised 2-core cost before DevOps wires CI; the
  scenario is Rendering & Performance HOW, the CI wiring DevOps HOW, the value architecture HOW.

`composite_stack`'s public signature is **preserved** (`composite_stack(nodes, w, h, *, region=None)`); all
new capability is additive/private. `blend.py` keeps its `document`-free posture (PL-D2). No new module,
no new import edge, no `data/` work — `check_layering` / `check_cycles` stay exit 0 (module count
unchanged).

### Amendment (2026-07-07) — Slice-A resolution: realistic-content gating + off-thread dense worst-case

*Immutable-append. The original Decision text above is retained as the record of what was planned. This
subsection records what Slice-A implementation actually resolved, and supersedes the two specific
over-committed claims called out below. It does **not** alter the byte-exact invariant (§4 /
`REQ-P12-LOGIC-002`), which stands.*

Slice-A implementation **confirmed the conditional escalation the baseline predicted**. Two planned claims
did not hold as written and are superseded here:

1. **Supersedes §1 (uint8 source-over "byte-identical" claim).** The baseline's uint8 straight-alpha
   source-over fast-path is **not** byte-exact against the shipped float64 `_blend_over_arrays` base case:
   a uint8 blend drifts **≤1 LSB per channel** vs. the float64 math (ADR-0005). Because
   `REQ-P12-LOGIC-002` requires **zero-tolerance byte-exactness**, that uint8 fast-path was therefore
   **NOT adopted for non-trivial blends**. What *was* shipped fast-paths only the **exact, arithmetic-free
   NORMAL branches** — fully-transparent source (skip) and fully-opaque source over the destination (copy)
   — which are byte-exact by construction. All genuine alpha blending stays on the float64 path. The
   byte-exact invariant (§4) is thus **preserved intact**, at the cost of pinning non-trivial blends to
   float64.

2. **Supersedes §5 (implied "dense content meets the 3000 ms ceiling dependency-free" commitment).** With
   the shipped byte-exact optimisation — **disjoint tiling + threaded fan-out + the exact clear/opaque
   NORMAL fast-paths** — the flatten is **3.3–12× faster**:
   - *realistic pixel-art content:* **19 s → 1.5 s** and **37 s → 3.4 s**;
   - *dense pathological 8-layer 8K:* **42 s → 12.8 s**.

   Byte-exactness pins the blend math to **float64** (per point 1 / ADR-0005), which makes the flatten
   **memory-bandwidth-floored at ~5 s** for the dense case even with **ideal threading**. The dense
   pathological worst-case therefore **cannot meet the 3000 ms `COMPOSITE_FULL_CEILING_MS` ceiling
   dependency-free**. **Native acceleration (numba / Cython) was evaluated** and *would* meet the ceiling,
   but was **DECLINED by user product-direction decision** to keep the application **dependency-free and
   portable** for the upcoming **Phase-13 cross-platform + mobile** work — portability outranks shaving the
   rare dense cold-flatten.

**Accepted resolution (no new dependency):**

- **Gate the full-frame flatten on REALISTIC pixel-art content**, which passes the 3000 ms bound **with
  margin** (1.5 s / 3.4 s). The CI `--full-frame` scenario and `COMPOSITE_FULL_CEILING_MS` remain the
  catastrophic-regression bound for the realistic path; they are **not** asserted against the dense
  pathological content.
- **Run the rare dense worst-case OFF the GUI thread** via the **existing Phase-5
  `ui/composite_warmer.py`** substrate (which has kept the flatten off-thread since Phase 5 — **no UI
  freeze**), with a progress cue. No user-visible stall results; the cost is background/off-thread.
- **Document the pathological dense cold-flatten cost (~12.8 s, ~5 s bandwidth floor) as ACCEPTED** — an
  explicit, bounded, off-thread cost incurred only for the rare 8-layer-dense-8K worst case.

The **shipped byte-exact 3.3–12× win is retained**; only the specific commitment that *all* content
(including dense pathological) hits 3000 ms dependency-free is withdrawn. The public
`composite_stack(nodes, w, h, *, region=None)` signature, the pure Qt-free `logic/blend.py` posture, and
the `check_layering` / `check_cycles` exit-0 status are all **unchanged** by this resolution.

### Amendment (2026-07-07) — Ceiling finalised at 15000 ms (Rendering & Performance RE-PROFILE)

*Immutable-append. Records the outcome of the Rendering & Performance RE-PROFILE ship gate that §5 promised ("Rendering & Performance's
RE-PROFILE ship gate confirms/tightens the value … before DevOps wires CI"). This note does **not** rewrite
any prose above; it supersedes only the ceiling **figure**. Every `3000 ms` in the original Decision §5 and
in the first Amendment above is the **pre-RE-PROFILE candidate** value (the mirror of the full-8K
`TILEMAP_VIEWPORT_CEILING_MS`) and is retained as the historical record of what was planned/reasoned at that
time. The finalised single source of truth is `logic/constants.py`.*

The RE-PROFILE measured the shipped byte-exact optimised flatten on the 2-core CI runner and found the
3000 ms candidate **too tight** for the realistic-content gate — it would flake on healthy code on the slow
2-core runner (the FU-15 loose-ceiling caution). The gate was therefore **loosened, not tightened**. The
finalised single-source value is:

> **`logic/constants.py :: COMPOSITE_FULL_CEILING_MS = 15000`** (ms).

15000 ms gives ~1.85–2.5× margin over the realistic-content 8-layer flatten (≈2.7 s on a fast desktop;
≈5–8 s on the slow 2-core CI runner) while staying ~2.5–4× **below** the ~38–63 s catastrophic-regression
cost it must catch (the measured 20 244 ms (4L) / 42 669 ms (8L) class, which scales worse on the 2-core
runner). The gate's **posture is unchanged**: it is a **loose catastrophic-regression bound** on the
**realistic-content** path only (the dense pathological worst-case still runs off the GUI thread and is
ACCEPTED per the first Amendment — it is **not** asserted against this ceiling), and it is **not** a 16 ms
frame budget. **Reader guidance:** wherever this ADR (Decision §5, the first Amendment, and the Consequences
Amendment) says the realistic path "passes / is under the 3000 ms bound" or names the "3000 ms
`COMPOSITE_FULL_CEILING_MS` ceiling", read the finalised bound as **15000 ms**. The margin conclusion is
unaffected — realistic content (1.5 s / 3.4 s) is comfortably under either figure — and no other
measurement changes (the 19 s→1.5 s / 37 s→3.4 s realistic wins and the 42 s→12.8 s, ~5 s-bandwidth-floored
dense worst-case all stand). No new dependency; the byte-exact invariant (§4 / `REQ-P12-LOGIC-002`), the
public signature, the Qt-free `logic/blend.py` posture, and `check_layering` / `check_cycles` exit-0 are all
unchanged. **ADR-0034 is unaffected.**

## Alternatives Considered

- **Accept a tolerance / approximate the flatten.** Rejected (REQ-P12-LOGIC-002, Article I) — output must
  be byte-exact; downstream phases depend on the exact bytes and ADR-0005's bit-exact NORMAL.
- **GPU / a new dependency (numba, Cython, GL).** Rejected (spec §6 non-goal; baseline §5) — the target is
  reachable dependency-free; numba/Cython would help but are **not** needed, and no GPU decision is
  escalated.
- **Relax `FRAME_BUDGET_MS` or gate the flatten at 16 ms.** Rejected (Article VI §2 / VIII §3) — the
  flatten is a batch path; the budget is a fixed constraint, and the flatten is bounded by a loose
  catastrophic ceiling, not 16 ms.
- **Keep the flatten ungated (rely on the 16-px `--composite` gate).** Rejected (baseline §1/§4) — that
  gate is structurally blind to the full-frame path; a dedicated `region=None` scenario is required.
- **Re-implement `composite_stack` from scratch.** Rejected (Article I reuse) — the fast-path + tiling
  compose the existing bit-exact primitives (`_blend_over_arrays`, `_composite_region`), preserving the
  frozen contracts.

## Consequences

**Positive.** The catastrophic 20–43 s flatten is eliminated under a loose, CI-guarded ceiling; the output
is provably unchanged (byte-exact regression over all 12 modes); the previously-blind full-frame path gains
a CI gate; the change is dependency-free and lands entirely inside the existing pure `logic/blend.py`
(no new module, no layering rule, module count unchanged); the GUI can stay responsive via the shipped
off-thread warmer.

**Negative / risk.** The byte-exact invariant makes the fast-path routing subtle — it must match the
float64 base case exactly (mitigated by the test suite's per-mode regression + determinism tests). The tiled path
adds tiling/threading bookkeeping to `blend.py` (mitigated by disjoint-tile equivalence to
`_composite_region`). The `COMPOSITE_FULL_CEILING_MS` value is a candidate until Rendering & Performance's RE-PROFILE ship
gate measures the optimised 2-core cost (mitigated: loose bound sized above optimised cost with headroom,
and RE-PROFILE precedes CI wiring).

**Amendment (2026-07-07) — Slice-A measured outcome.** The "20–43 s eliminated under a loose CI-guarded
ceiling" positive above holds for **realistic pixel-art content** (19 s → 1.5 s, 37 s → 3.4 s — comfortably
under 3000 ms) and yields a shipped **3.3–12× byte-exact win**. It does **not** hold for the **dense
pathological 8-layer 8K** worst-case (42 s → 12.8 s): because byte-exactness pins the blend to float64
(ADR-0005; the uint8 fast-path drifts ≤1 LSB and was **not** adopted for non-trivial blends), that case is
**memory-bandwidth-floored at ~5 s** and cannot reach 3000 ms **without native acceleration**, which was
**DECLINED** (portability for Phase-13 mobile / cross-platform). *Consequence:* the dense worst-case is
**run off the GUI thread** via the shipped Phase-5 `ui/composite_warmer.py` (no UI freeze) and its
**cold-flatten cost is ACCEPTED and documented**; the CI ceiling gates only the realistic path. **Net:** no
new dependency, byte-exact invariant (§4 / `REQ-P12-LOGIC-002`) intact, portability preserved, the 3.3–12×
win retained, and only the rare dense-pathological sub-second commitment withdrawn. **ADR-0034
(opacity-drag preview) is unaffected** by this resolution.

## Grounding

- Spec §2 (Slice A scope), §4 (REQ-P12-LOGIC-001/-002/-003), §5 (Article VI posture), §8 (DEP-1/-2/-3);
  `acceptance.md` (SC-P12-LOGIC-001-1/-2, -002-1/-2, -003-1); `traceability.md`.
- `docs/perf/phase12-baseline.md` §2 #1/#1b (20–43 s), §3 FU-P5-PERF (fast-path + tiling + dirty-tile +
  off-thread), §5 (dependency-free, no GPU), §6 (loose ceiling ≈1500–2000 ms + full-frame scenario).
- Shipped tree: `logic/blend.py` (`composite_stack`, `_blend_over_arrays` float64 bit-exact NORMAL,
  `_composite_region`, `_flatten_group` MRU cache), `ui/composite_warmer.py` + `ui/frame_cache.py`,
  `scripts/perf_profile.py --composite`, `logic/constants.py`. Constitution Article I / II / IV / VI / VIII.
  ADR-0005 (working space + bit-exact NORMAL), ADR-0007 (region-scoped recomposite + full-canvas alloc).
