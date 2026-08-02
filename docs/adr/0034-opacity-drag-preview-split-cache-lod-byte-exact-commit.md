# ADR-0034 — Live opacity-drag interaction: split-cache + downsampled-LOD preview holding 16 ms, with a byte-exact full-resolution recomposite on commit

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-07 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-12-performance-scalability` (`REQ-P12-LOGIC-004`, `REQ-P12-UI-001`, `REQ-P12-LOGIC-005`; FU-16b / Slice B) |
| Supersedes | — |
| Superseded by | — |
| Relates to | spec `specs/phase-12-performance-scalability/spec.md` §2/§2c/§4/§8; `docs/perf/phase12-baseline.md` §2 #2/#2b, §3 FU-16, §5, §6; constitution Article I / II / IV / V / VI / VIII; ADR-0007 (region-scoped recomposite); ADR-0033 (flatten byte-exact invariant); Phase-4 D3 (opacity-drag debounce); Phase-5 `composite_warmer` |

## Context

AGT-10's baseline found the whole-viewport / low-zoom multi-layer recomposite driving the **live
opacity-slider drag** costs **2 231 ms @ 1080² / 7 024 ms @ 1920² for a 12-layer stack**, cache-cold each
tick (baseline §2 #2/#2b). A slider drag fires many recomposites/sec, so the interaction stalls for
seconds. It is **effectively ungated**: the shipped `perf_profile --composite` gate only exercises a 16×16
region, so it cannot catch a whole-viewport recomposite blow-up (baseline §1/§4).

Two distinct follow-ups were both historically labelled **"FU-16"** (spec §2c): **(a)** a cache-invalidation
micro-optimisation (non-`document` buffer ops not self-invalidating the `LayerGroup` flatten cache; owner
AGT-03; **not** this subject) and **(b)** the whole-viewport / opacity-drag recomposite CPU cost. **This
ADR is FU-16b only.** Slice F assigns distinct identifiers so the two are never conflated.

The recomposite has a dual nature: the *committed* result (mouse-release) must be **byte-exact** vs today
(a correctness constraint), while the *during-drag* feedback **is** on the per-frame render loop, so
Article VI's 16 ms `FRAME_BUDGET_MS` **applies and must be held** for that path. The commit recomposite is
a **batch** path (not a 60-fps path), bounded by a loose catastrophic ceiling — not 16 ms. The fix is
dependency-free (baseline §5) — no GPU, no new dependency.

## Decision

**Split the flatten cache around the dragged layer and show a downsampled-LOD preview that holds 16 ms
during the drag; on commit apply the full-resolution recomposite that produces byte-exact-identical final
pixels to today.**

### 1. Split-cache around the dragged layer (REQ-P12-LOGIC-004; pure `logic/blend.py`)

- At **drag-start**, cache `composite(below dragged-layer)` and `composite(above dragged-layer)` **once**.
  Per tick, blend only `below ⊕ (layer · opacity) ⊕ above` (≈ 2–3 blends), instead of recompositing all
  12 layers. *(**Superseded, see Amendment 2026-07-07** for the byte-exactness scope of this
  `above`-pre-flatten shortcut: treating the pre-flattened `above` buffer as a **byte-exact commit**
  path — even when every above layer is NORMAL/source-over — is over-broad; that shortcut is byte-exact
  ONLY for hard-edged alpha ∈ {0, 255} content and is scoped to the **preview** in the shipped design.
  The byte-exact **commit** re-blends the `above` sub-range in order via the exact suffix re-blend
  `composite_range(nodes, k, N, base=below)`. The `below ⊕ (layer · opacity) ⊕ above` per-tick form
  remains correct for the deliberately-approximate preview.)* The split-cache seam is a pure, Qt-free addition to `logic/blend.py` (any
  `composite(below)` / `composite(above)` helper around a target index), consistent with the
  `CompositeNode`-Protocol / `document`-free posture (PL-D2).
- **Cull to the true exposed viewport rect + dirty region**, not the whole canvas (ADR-0007 region-scoped
  recomposite precedent).

### 2. Downsampled-LOD preview holds 16 ms during the drag (REQ-P12-UI-001, Article VI §1 — budget APPLIES)

- While dragging, recomposite a **downsampled** (nearest-neighbour, pure-numpy) preview via the split-cache
  and display it; this per-tick feedback **holds the 16 ms `FRAME_BUDGET_MS`** (the budget **applies** to
  this per-frame path and is **held, not relaxed**). Ticks are **throttled / off-thread** via the shipped
  Phase-4 D3 opacity-drag debounce + Phase-5 `ui/composite_warmer.py` + `ui/frame_cache.py`. The UI
  **never stalls for seconds** during the drag.
- The pure LOD-downsample helper lives in `logic/` (Qt-free); the drag lifecycle (start → per-tick preview
  → commit) lives in `ui/layer_panel.py` and calls `logic/blend` — **no compositing maths in the widget**.

### 3. Byte-exact full-resolution recomposite on commit (REQ-P12-LOGIC-004, Article I)

- On **commit** (mouse-release / drag-end), apply the **full-resolution** recomposite; the **final
  on-screen pixels are byte-identical to the current build** over the same inputs (zero tolerance,
  deterministic). The optimisation is split-caching / culling / LOD-on-preview — **never** an output
  change. Both light and dark themes behave identically (Article V). The commit recomposite is a batch
  path — **not** asserted against the 16 ms budget.

### 4. A loose viewport-scale perf gate (REQ-P12-LOGIC-005, Article II / VI / FU-15)

- **Extend** `perf_profile --composite` with a **viewport-scale scenario** (region ≥ 1080² and/or 1920²,
  12 layers); CI gates it at the **single-source named constant `VIEWPORT_RECOMPOSITE_CEILING_MS`**
  (`logic/constants.py`, candidate **2000 ms**) — a **loose catastrophic-regression bound** sized above the
  split-cache-optimised commit cost with 2-core headroom (FU-15), below the 2–7 s catastrophe so the gate
  bites, **not** 16 ms. AGT-10's RE-PROFILE ship gate confirms the value + gate scenario before AGT-09
  wires CI; scenario = AGT-10 HOW, CI wiring = AGT-09 HOW, value = AGT-01 HOW.

**No new undoable operation** — the opacity change is already undoable via the shipped Phase-4 D3 path;
**`ui/commands.py` is unchanged**. No new module, no new import edge, no `data/` work — `check_layering` /
`check_cycles` stay exit 0.

## Alternatives Considered

- **Full-resolution recomposite every tick (no preview LOD).** Rejected — that is the measured 2–7 s
  stall; the per-frame drag path must hold 16 ms.
- **Show the LOD preview as the committed result.** Rejected (REQ-P12-LOGIC-004, Article I) — the commit
  must be full-resolution and byte-exact; the LOD is a *during-drag* preview only.
- **Recomposite all 12 layers per tick without a split-cache.** Rejected — cost is linear in layers; the
  split-cache reduces it to ≈2–3 blends regardless of stack depth.
- **Relax `FRAME_BUDGET_MS` for the drag.** Rejected (Article VI §2 / VIII §3) — the budget is a fixed
  constraint; the preview must be engineered to hold 16 ms.
- **A GPU / new dependency.** Rejected (spec §6 non-goal; baseline §5) — solvable dependency-free
  (split-cache + LOD + throttle/off-thread).
- **Put the split-cache / LOD maths in `ui/`.** Rejected (Article I) — the maths are pure `logic/blend.py`;
  only the drag lifecycle + display is `ui/`.

## Consequences

**Positive.** The opacity-drag interaction stays responsive (16 ms preview) instead of a multi-second
freeze; the committed result is provably unchanged (byte-exact); the previously-blind viewport-scale
recomposite gains a CI gate; the change reuses the shipped D3 debounce + `composite_warmer` + `frame_cache`
and lands inside existing `logic/blend.py` + `ui/layer_panel.py` (no new module, module count unchanged);
the FU-16 label collision is resolved so FU-16a (cache-invalidation) is never conflated with FU-16b (this).

**Negative / risk.** The preview/commit split adds drag-lifecycle state to `ui/layer_panel.py` (mitigated
by reusing the D3 debounce + warmer). The LOD preview is a deliberately *approximate* during-drag view —
acceptable because the **commit** is byte-exact (the observable final pixels match today). The
`VIEWPORT_RECOMPOSITE_CEILING_MS` value is a candidate until AGT-10's RE-PROFILE ship gate measures the
optimised 2-core cost and confirms the gate scenario (mitigated: loose bound with headroom; RE-PROFILE
precedes CI wiring).

## Grounding

- Spec §2 (Slice B scope), §2c (FU-16 label disambiguation), §4 (REQ-P12-LOGIC-004/-005, REQ-P12-UI-001),
  §5 (Article VI — preview holds 16 ms; commit is batch), §8 (DEP-1/-2/-3/-4); `acceptance.md`
  (SC-P12-LOGIC-004-1/-2, SC-P12-UI-001-1/-2, SC-P12-LOGIC-005-1); `traceability.md`.
- `docs/perf/phase12-baseline.md` §2 #2/#2b (2–7 s), §3 FU-16 (split-cache + LOD-during-drag + cull +
  throttle/off-thread), §5 (dependency-free, no GPU), §6 (viewport-scale scenario + loose ceiling).
- Shipped tree: `logic/blend.py` (`composite_stack`, `_composite_region`, region-scoped recomposite),
  `ui/layer_panel.py` (opacity slider + D3 debounce), `ui/composite_warmer.py` + `ui/frame_cache.py`,
  `scripts/perf_profile.py --composite`, `logic/constants.py`. Constitution Article I / II / IV / V / VI /
  VIII. ADR-0007 (region-scoped recomposite), ADR-0033 (flatten byte-exact invariant).

## Amendment — 2026-07-07 (byte-exactness scope of the `above`-pre-flatten shortcut)

**Author:** AGT-01 (Architecture). **Trigger:** AGT-03 empirical characterisation during
Slice-B logic implementation. **Immutable-append:** the original Decision §1/§2/§3 text above is
retained unchanged; this amendment narrows one over-broad claim and records the shipped resolution.
The ADR is **not** superseded — its core decision stands (see §c).

### a. The `above`-pre-flatten byte-exactness claim is narrowed

The original §2.2-anchor claim (the `above`-pre-flatten associativity shortcut — pre-flattening the
`above` sub-range over transparent and compositing it as one source-over buffer,
`above OVER (layer·o OVER below)`) is byte-exact **when all above layers are NORMAL/source-over** is
**OVER-BROAD**. AGT-03 measured that this holds byte-for-byte **ONLY for hard-edged pixel-art content
(alpha ∈ {0, 255})**. On **partial-alpha / anti-aliased** content the pre-flatten diverges by **≤ 2 LSB**
from the in-line re-blend **even under the `is_range_source_over` predicate** — the divergence is
intermediate-uint8 quantisation of the pre-flattened `above`, not a blend-mode error. Measured:
**212 / 400 stress trials** diverged on partial-alpha content under the source-over predicate. Porter-Duff
`over` is mathematically associative, but the two composition orders are **not** byte-identical after
per-step uint8 rounding on fractional alpha.

### b. Shipped resolution — the byte-exact commit uses the exact suffix re-blend (unconditional)

The shipped **byte-exact COMMIT** is `composite_range(nodes, k, N, base=below)` — re-blend the dragged
layer and then the `above` sub-range **in order** over the cached `below` prefix. This is byte-identical to
`composite_stack` **for ALL content (hard-edged and partial-alpha) and all 12 blend modes** (NORMAL + the
11 separable modes), by construction: the `below` prefix is byte-identical to the corresponding prefix of
the full composite and the range folds through the identical `_reduce_nodes` reduction — exactness *by
construction*, not by associativity. The `above`-pre-flatten / all-NORMAL fast path is therefore scoped to
the **during-drag PREVIEW and perf-gate timing ONLY**, where a ≤ 2 LSB approximation on anti-aliased
content is acceptable (the preview is already a nearest-neighbour LOD downsample).

### c. `is_range_source_over` gates preview-eligibility, not commit correctness

The `is_range_source_over(nodes)` predicate gates **whether the bounded `above`-pre-flatten fast path is
eligible**, not commit correctness. Commit correctness is unconditional — it is the `base=below` suffix
re-blend regardless of the above layers' blend modes, and does not consult the predicate. This matches the
shipped docstrings in `logic/blend.py` (`composite_range`, `is_range_source_over`) which already reference
the "ADR-0034 §2.2 caveat"; this amendment is the ADR-side text they point to.

### Core decision unchanged

The ADR's core decision — **split-cache around the dragged layer + downsampled-LOD preview holding 16 ms +
byte-exact full-resolution recomposite on commit** — **still stands**. Only the *mechanism-of-byte-exactness*
is clarified: the commit's byte-exactness comes from the exact suffix re-blend (`composite_range(base=below)`),
not from the `above`-pre-flatten associativity shortcut. Correctness was preserved in the shipped build
throughout; this amendment corrects the ADR text so it does not mislead future work. **ADR-0033 (flatten
byte-exact invariant) is untouched.**
