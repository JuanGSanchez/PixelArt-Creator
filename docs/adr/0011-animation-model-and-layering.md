# ADR-0011 — Animation model: `logic/animation.py` (Qt-free), `document → animation` edge, cached per-frame composite

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-5-animation` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 5 adds a timeline over the shipped `Document → frames → layers → PixelBuffer` tree: a
`PlaybackMode` vocabulary + pure frame-sequencing engine, onion skinning, frame **tags** (named
animations), reversible frame management, and per-frame durations (REQ-P5-LOGIC-001..014). The
compositor (`blend.composite_stack`, CO-4), `Frame.duration_ms` (FR-2), the `history` command
pattern, and the v2 `.pixproj` frame/layer serialisation are already shipped and must be **reused,
not re-authored** (Article I). Three architecture decisions must be fixed before code lands so the
DATA/UI slices bind to a stable contract:

1. **Where the animation logic lives** and how it avoids putting Qt in `logic/` (Article I) — the
   only new Qt surface is the playback timer.
2. **The layering edge** between the new module and `document.py` (must stay acyclic —
   `check_layering`/`check_cycles`).
3. **How 8K multi-layer scrub/playback holds `FRAME_BUDGET_MS = 16`** (REQ-P5-UI-016, Article VI;
   DEP-3) without re-flattening every layer per tick, and how the eager frame-switch rebuild
   (**FU-19**) is avoided.

## Decision

**Introduce a new Qt-free `logic/animation.py`; make `document → animation` a one-way edge;
delegate all per-frame compositing to `blend.composite_stack`; commit to a cached per-frame
flattened composite for scrub/playback with FU-19 deferral; keep the playback timer in `ui/`.**

- **Module & vocabulary.** `logic/animation.py` (pure, zero Qt) defines `PlaybackMode`
  (`LOOP`/`ONCE`/`PING_PONG`/`REVERSE`, default `LOOP`), a `PLAYBACK_STOP` sentinel, deterministic
  sequencing (`next_frame`/`playback_steps`/`tag_playback_steps`), the `onion_overlay` computation,
  the `FrameTag` model + range validation/clamp helpers, and `AnimationError`. `PlaybackMode` is an
  enumerated vocabulary (like `BlendMode`) and lives here, not in `constants.py` (Article II/BF-2).
- **Layering (acyclic).** `document.py` imports `animation` (it holds `List[FrameTag]` and
  constructs `FrameTag`/`PlaybackMode` in its tag/frame command builders). `animation.py`
  **never imports `document`**: it consumes layer stacks structurally via the existing
  `blend.CompositeNode` Protocol and plain `Sequence[int]` durations, mirroring how `blend.py`
  avoids a `document` import (PL-D2 precedent). Chain: `document → animation → blend → color,
  constants`; no back-edge. `check_layering`/`check_cycles` stay `0`.
- **Compositing reuse (CO-4).** Per-frame render, scrub, onion and playback flatten a frame's own
  layer stack **only** via `blend.composite_stack` (region-aware, ADR-0007 amended). No compositing
  maths is re-implemented (Article I). `onion_overlay` composites each prev/next stack, tints toward
  `ONION_TINT_PREV/NEXT`, and fades linearly from `ONION_SKIN_OPACITY` to `ONION_SKIN_OPACITY_MIN`;
  the active frame is excluded and hidden layers are honoured (they are already absent from the
  composite).
- **Timer in `ui/` (Article I).** The next-frame *decision* is pure `logic/animation`; the wall
  clock (`QTimer`) is `ui/`-only. The sequencing functions are duration-agnostic on the sequencing
  axis (they take `Sequence[int]`), so `animation.py` needs no `Frame`/`Document`/Qt import.
- **Perf (DEP-3 / FU-19).** Each frame's flattened composite is **cached**; scrub/playback switch
  between pre-flattened frame buffers (a blit), never re-flattening per tick. The eager
  `_rebuild_composite`-on-frame-switch path is **deferred (FU-19)** — a switch consults the cache
  and rebuilds only on miss. In-frame edits recomposite only the dirty region (ADR-0007) and
  invalidate that frame's cache entry. Onion is suppressed during playback (CL-11) so it never
  competes with the 16 ms tick. Resident buffers are never culled (Article VI §3, F7). **AGT-10**
  profiles (`perf_profile`/`frame-profile`) and issues any viewport directive; **AGT-05**
  implements the cache + deferred switch; the **budget is never relaxed** (Article VI §2).

## Alternatives Considered

- **Put sequencing/onion in `ui/` (next to the timer).** Rejected: it is Qt-free domain logic and
  must be headless-testable in `logic/` (Article I, IV). Only the `QTimer` is Qt.
- **`animation.py` imports `document` (operate on `Document`/`Frame` directly).** Rejected: it
  creates a `document ↔ animation` cycle once `document` stores tags. Consuming `CompositeNode` +
  `Sequence[int]` keeps the edge one-way (the `blend.py` precedent).
- **Re-flatten every layer per playback tick (no cache).** Rejected: infeasible at 8K (far over
  16 ms), violating Article VI. Cached per-frame composites + FU-19 deferral are required.
- **Fold `PlaybackMode` numerics into `constants.py`.** Rejected: an enum is a vocabulary, not a
  tuning scalar (BF-2, `BlendMode` precedent).

## Consequences

**Positive.** Animation logic is pure, deterministic (P2) and headless-testable; the layering stays
acyclic and enforced; compositing is reused (CO-4), not duplicated; the cached-composite commitment
gives AGT-10/AGT-05 a defined optimisation surface and keeps 8K scrub/playback in budget; the timer
boundary keeps `logic/` Qt-free.

**Negative / risk.** The per-frame composite cache needs correct invalidation (a stale entry
renders a wrong frame) — the contract is: any change to frame *f*'s layer tree invalidates *f*'s
entry; asserted by AGT-06. If profiling still exceeds budget after caching, the AGT-10 directive
escalates to viewport tuning — never a budget relaxation.

## Grounding

- Spec `specs/phase-5-animation/spec.md` §2/§4/§5 (REQ-P5-LOGIC-001/002/003/012/013, REQ-P5-UI-016),
  §8 DEP-1/DEP-3, §10 CL-3/CL-5/CL-6/CL-11/CL-12/CL-14; `plan.md` §3.4/§4/§7.
- Research `docs/research-phase5-animation.md` Q1 (onion), Q2 (playback/ping-pong/timing), Q4
  (timeline model, stable `layer_id`).
- Constitution Article I (three-layer purity), II (numerics/vocabulary), VI (16 ms / never cull /
  never relax), IV (headless determinism).
- ADR-0007 (region-scoped recomposite, amended) reused for the in-frame edit path; ADR-0001
  (vocabulary vs tuning constant); `blend.CompositeNode` Protocol (PL-D2, Phase 4).
