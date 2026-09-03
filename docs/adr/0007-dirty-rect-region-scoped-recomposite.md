# ADR-0007 — Dirty-rect region-scoped recomposite with cached group buffers

| Field | Value |
| --- | --- |
| Status | **Accepted — AMENDED 2026-07-02** |
| Date | 2026-07-02 |
| Author | Architecture |
| Feature | `phase-4-layer-canvas` |
| Supersedes | — |
| Superseded by | — |
| Amendment driver | Rendering & Performance's performance profile (an internal design record, outside this repository; see §Amendment) |

## Context

REQ-P4-UI-015 (NFR, Article VI) requires an 8K multi-layer stack (7680×4320) to hold
`FPS_TARGET = 60` / `FRAME_BUDGET_MS = 16` on recomposite. A full-canvas recomposite of a
multi-layer stack on **every** edit is infeasible at 8K: a single flatten touches ~33 M
pixels per layer, blowing the 16 ms budget many times over (spec DEP-2, CL-13). The spec
fixes only the budget; the recomposite **strategy** is flagged to architecture (plan-level, DEP-2)
and Rendering & Performance (Qt viewport tuning). This ADR records the architecture-level commitment so the
compositor's public API and the canvas contract are stable before implementation, and so
Rendering & Performance has a defined optimisation surface.

## Decision

**The compositor is region-scoped, and the canvas recomposites only the dirty rectangle;
flattened group buffers are cached and reused when their subtree is unchanged.**

- `logic/blend.composite_stack(nodes, width, height, *, region=None)` accepts an optional
  `region = (x, y, w, h)`. `region=None` composites the whole canvas (initial paint, resize);
  a bounded `region` recomposites **only** that rectangle. The returned buffer / the caller's
  update is confined to the region.
- On any layer edit / attribute / order / group / mask change, `ui/canvas_scene.py`
  recomposites and refreshes **only the affected region** (the union of the edit's dirty rect
  and any dependent overlays), never the whole stack over the whole canvas.
- **Cached group buffers:** a `LayerGroup` flattens its children into an intermediate buffer
  (REQ-P4-LOGIC-011); that intermediate is **cached** and reused while the group's subtree is
  unchanged, so a group with N static children costs one blend, not N, per recomposite.
- The **resident per-layer buffers are never culled** (Article VI §3, F7) — only Qt rendering
  is culled / region-scoped. The pixel data stays fully in memory.
- **Rendering & Performance owns the measurement + Qt tuning:** `frame-profile` / `perf_profile` measures the
  8K recomposite headless. An over-budget result yields a Rendering & Performance directive the UI implementation
  implements — dirty-rect scope, cache scope, `QOpenGLWidget` viewport, `setBspTreeDepth`,
  tiled composite items (BF-1) — and the **budget is never relaxed** (Article VI §2). Architecture
  fixes the region-scoped API + cached-group commitment; Rendering & Performance fixes the render-pipeline
  parameters.

## Alternatives Considered

- **Full-canvas recomposite every edit (simplest).** Rejected: infeasible at 8K — far over
  16 ms, violating Article VI. Only viable for tiny canvases.
- **Whole compositor in `ui/` for direct QPainter tiling.** Rejected: blend maths + stack
  flattening are domain logic and must stay Qt-free in `logic/` (Article I); the UI only
  draws the flat buffer and signals dirty rects.
- **Fixed tile-grid recomposite (always TILE_SIZE tiles).** Deferred, not adopted as the
  base commitment: it is one *tuning* option Rendering & Performance may direct after profiling (BF-1), but the
  base API is an arbitrary-rectangle region so an edit's exact dirty rect drives the cost, not
  a fixed tile quantum. Tiling remains available if profiling shows it wins.

## Consequences

**Positive.** A single edit costs ≈ its dirty rect, not the canvas; groups amortise to one
cached blend; the compositor API (`region=`) and the never-cull buffer rule are stable for
the UI implementation and Rendering & Performance before code lands. Clear ownership split: architecture = region-scoped API +
cache commitment; Rendering & Performance = measured Qt tuning; budget is a hard gate.

**Negative / risk.** Cache invalidation must be correct — a stale group cache would render a
wrong composite. The invalidation contract (any child edit / attribute / order change dirties
the group cache up the ancestor chain) is specified for the implementation/the UI implementation and asserted by QA
(composite-updates-on-edit, SC-UI-012-2). If profiling still exceeds budget after
dirty-rect + group caching, the directive escalates to viewport/tiling tuning — never a budget
relaxation.

## Amendment — 2026-07-02

**Driver.** Rendering & Performance's performance profile
(an internal design record, outside this repository) measured the shipped
`logic/blend.composite_stack` at 8K (7680×4320) and found the region / single-pixel path at
**~140 ms — FAILING SC-UI-015-1 (REQ-P4-UI-015, 16 ms budget) by ~9×**. Root cause (load-bearing):
the cost is **not** the blend — a brush-sized dirty rect blends in ~1.5 ms — but a **mandatory
full-canvas allocation inside `composite_stack`**: it built `result = PixelBuffer(width, height, RGBA)`
(a 126 MB, 33.2 Mpx buffer whose constructor `fill()`s every pixel = ~139.8 ms) on **every** call,
**regardless of `region`**, then wrote only the dirty rect into it. This directly **defeated this
ADR's own dirty-rect intent** — the original Decision already stated *"The returned buffer / the
caller's update is confined to the region,"* but the return-**container** was still full-canvas.
Article VI §2 forbids relaxing the budget, so the contract is amended (not the budget).

**What this amendment changes (the original Decision text above is retained as the audit trail):**

1. **D1 — region call must NOT allocate a full width×height buffer (decisive).**
   `composite_stack(nodes, width, height, *, region=None) -> PixelBuffer` return shape is now:
   - `region=None` → a full-canvas `PixelBuffer(width, height)` (implied scene origin `(0,0)`) — unchanged.
   - `region=(x, y, w, h)` → a **region-sized** `PixelBuffer(w, h)` (numpy shape `(h, w, 4)`) whose
     **implied scene origin is `(x, y)`**; element `(row i, col j)` maps to scene pixel `(x+j, y+i)`.
     It allocates only `(h, w, 4)`, never `(height, width, 4)`.
   - **Region↔scene coordinate contract:** the region is in scene/canvas space (top-left origin,
     +x right, +y down). The caller (`ui/canvas_scene.py`) **blits** the returned buffer into the
     resident scene buffer at `(x, y)`: `scene.data[y:y+h, x:x+w] = returned.data`. `width`/`height`
     still bound/validate the region and inform per-layer sampling offsets (nodes sampled at scene
     coords, `node.buffer[y:y+h, x:x+w]`).
   - **Out-of-bounds / clamping rule:** the region MUST lie fully within `(0,0,width,height)` with
     `w ≥ 1, h ≥ 1`; an out-of-bounds or degenerate region raises `BlendError`. The compositor
     **validates, it does not silently clamp** (P2 determinism, Article VII); the caller clamps its
     dirty rect to the canvas before calling. This removes the ~140 ms floor → a brush-sized edit
     ≈ 1.5 ms → **in budget**. (The in-place `composite_into(dst, …)` alternative was considered;
     region-sized return was chosen as it matches this ADR's existing "confined to the region"
     language with minimal churn — the signature is unchanged.)

2. **D5 — float32 working space (compliance correction).** ADR-0005 already mandates a float32
   blend working space; the shipped implementation deviated to **float64**. It must use **float32**
   (halves per-pixel memory/time at 8K). Recorded here + in ADR-0005 §"Compliance note". No
   behaviour change beyond deterministic float→uint8 rounding (already centralised).

3. **D4 — cached group buffers + partial-stack recomposite are now MANDATORY (not optional).** The
   original ADR committed to cached flattened group buffers; this amendment makes the **invalidation contract
   explicit and required for the implementation**: any child edit / attribute / order / mask change **invalidates
   the group cache up the entire ancestor chain**; a stale cache renders a wrong composite. Asserted
   by QA (SC-UI-012-2). Additionally, **partial-stack recomposite**: cache the composited backdrop
   of layers *below* the changed layer, so an attribute change on layer *k* re-blends only *k..top*.

**Ownership / scope of the amendment.** D1/D4/D5 are **logic-layer** items owned by **the implementation**
(implement) under this amended contract. D2 (viewport-scoped attribute recomposite instead of
whole-stack `refresh_all`) and D3 (opacity-drag debounce to one recomposite per frame) are **UI
directives owned by the UI implementation** (Rendering & Performance report §4). D6 (`QOpenGLWidget` viewport) and D7
(`setBspTreeDepth`) **remain deferred** per Rendering & Performance — needed only for the worst-case whole-viewport,
many-layer recomposite, not for the SC-UI-015-1 single-edit path this amendment fixes. The budget was
**never relaxed** (Article VI §2). The change is **localised to the compositor return shape + working
dtype**: the public signature is unchanged, no imports are added, the layering stays one-way
(`document → blend`, `blend` imports no `document`) — `check_layering` / `check_cycles` re-run clean
this session.

## Grounding

- Rendering & Performance's profile (an internal design record, outside this repository)
  (§2b measured 8K region path ~140 ms; §3 root-cause = full-canvas `PixelBuffer` alloc+fill floor).
- Spec `specs/phase-4-layer-canvas/spec.md` REQ-P4-UI-015 (§5), §8 DEP-2, CL-13; plan §2/§10 (§10 Amendment).
- Constitution Article VI (16 ms / 8K; over-budget → Rendering & Performance directive; resident buffer never
  culled) and Article II (`FRAME_BUDGET_MS`, `FPS_TARGET`, `TILE_SIZE`).
- Research F2/F7 (exposed-rect draw, culling Qt not data) and the `render-strategy` /
  `frame-profile` skill ownership (Rendering & Performance).
- REQ-P4-LOGIC-011 (group composites children then blends as one — the cached intermediate).

## Footnote (2026-08-16) — the NORMAL array path deliberately re-deviates to float64 (scope of D5)

*Immutable-append. Neither the original Decision nor the Amendment above is rewritten; this
footnote records a deliberate, tested narrowing of **D5** so that the divergence between the ADR text
and the shipped code reads as a recorded decision rather than as drift.*

**Provenance.** The 2026-08-16 spec-verification audit `audit-spec-phase-4-layer-canvas-20260816.md`
(F-5) — consolidated as CF-101(d), remediation item R-23.

Amendment item **D5** above requires a **float32** blend working space (ADR-0005 compliance). The
shipped `logic/blend.py` honours that for the **eleven separable non-NORMAL modes**, but the default
**NORMAL** array path is deliberately **float64**: `_blend_over_arrays` is a float64 **replica** of
`logic/color.blend_over` over the 0..255 range — reproducing that function's exact per-channel
expression, its round-half-to-even-then-clip, and both early-return branches (`sa == 255` → `src`,
`sa == 0` → `dst`) via `numpy.where` — rather than a literal delegation. Delegation is not available:
`blend_over(src: RGBA, dst: RGBA) -> RGBA` is a per-pixel tuple function and cannot be applied to an
`(H, W, 4)` array without a Python-level loop.

**Why the re-deviation.** The float32 generic separable path diverged from `blend_over` by **≤ 1 LSB**
at rounding boundaries. REQ-P4-LOGIC-003 / ADR-0005 freeze `blend_arrays(NORMAL)` as equal to
`blend_over` applied elementwise **with zero tolerance**, so on the DEFAULT mode float32 is not merely
slower to agree — it is non-compliant. Bit-exactness beats the float32 memory/time saving on this one
path; the eleven non-NORMAL modes keep the float32 saving.

**It is proven, not asserted.**
`tests/logic/test_blend.py::test_blend_arrays_normal_base_case_equals_blend_over_exactly` and
`::test_blend_arrays_normal_base_case_equals_blend_over_property` assert exact equality against the
`blend_over` oracle with no tolerance, including the `sa == 0 & da == 0` sub-case. The rationale is
also carried in the `_blend_over_arrays` docstring.

**Scope.** D5's float32 mandate is hereby read as governing the **generic separable path (the eleven
non-NORMAL modes)**; the **NORMAL** array path is float64 **by decision**. Nothing else in D5 or in the
Amendment changes — D1's region-sized return shape and D4's cache-invalidation contract stand, no
public signature changes, no import is added, and `check_layering` / `check_cycles` are unaffected
(this is a dtype choice inside one Qt-free `logic/` function).
