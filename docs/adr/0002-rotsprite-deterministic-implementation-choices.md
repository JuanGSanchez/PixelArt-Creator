# ADR-0002 — RotSprite deterministic implementation choices (the four unpublished pins)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-2-advanced-drawing` |
| Supersedes | — |
| Superseded by | — |

## Context

REQ-P2-LOGIC-013 requires a clean arbitrary-angle rotation (RotSprite) whose output
introduces **no colour absent from the source** (R2, acceptance-critical) and is
**deterministic** for a fixed `(buffer, angle)` (NFR-2). The Researcher grounded the
canonical four-stage pipeline — upscale ×8 (three *similarity*-based Scale2× passes) →
rotation-offset search → nearest-neighbour rotate + downscale → single-pixel detail
restoration — in `docs/research-rotsprite-pixelperfect.md`.

That report explicitly flags **four choices the accessible secondary sources do NOT
publish**; they are implementation decisions that must be fixed to make the algorithm
deterministic and testable:

1. the Scale2× **similarity threshold** (RotSprite's "similar, not equal" test),
2. the **pivot convention** (centre-of-pixel vs centre-of-canvas),
3. the offset-search **tie-break** rule, and
4. the **out-of-bounds fill** value.

The "no new colours" guarantee is independent of all four (the pipeline is copy-only:
Scale2× and nearest-neighbour only ever copy existing pixels), so pinning them cannot
violate R2 — they affect quality and reproducibility, not palette safety.

## Decision

AGT-01 pins the four choices deterministically. They become AGT-03 acceptance
(SC-L013-*) and are immutable here.

1. **Similarity threshold** — `ROTSPRITE_SIMILARITY_THRESHOLD = 100` (in `logic/constants.py`),
   applied as `color.distance_sq(a, b) <= ROTSPRITE_SIMILARITY_THRESHOLD` — the **same
   squared-RGBA metric** the project already uses for `flood_fill` / magic-wand. √100 = 10
   ≈ a modest single-channel delta: it merges near-duplicate / antialiased fringe pixels
   while keeping distinct pixel-art palette entries (which typically differ by ≫10 per
   channel) separate. INDEXED buffers use exact index equality (threshold ignored),
   matching CL-16.
2. **Pivot convention** — rotation about the **geometric centre of the pixel grid**,
   `((W-1)/2.0, (H-1)/2.0)` (centre-of-pixel). The output buffer is the **same `W×H`** as
   the input. The `pivot` parameter defaults to this; an explicit pivot is honoured for
   selection-region rotation.
3. **Offset-search tie-break** — over offsets `(dx, dy)` in
   `0..(FACTOR-1) × 0..(FACTOR-1)` on the 8× image, minimise the sum of squared neighbour
   colour differences (non-boundary samples weighted); **on equal cost choose the
   lexicographically smallest `(dx, dy)`** (dx ascending, then dy ascending), scan started
   from `(0, 0)`.
4. **Out-of-bounds fill** — uncovered destination pixels are filled **transparent RGBA
   `(0, 0, 0, 0)`** (INDEXED: **index `0`**). The `fill` parameter defaults to this.

The upscale factor is `ROTSPRITE_UPSCALE_FACTOR = 8` (three Scale2× passes, 2×2×2).

## Consequences

- The whole pipeline is integer / nearest-neighbour and copy-only; with the four pins
  fixed it is reproducible in NumPy (NFR-2). `0°`/`360°` returns an equal buffer; a fully
  transparent input stays transparent (SC-L013-2/-3).
- Output colour set ⊆ input colour set is guaranteed structurally, not by clamping
  (SC-L013-1, R2).
- AGT-03 implements exactly these values; AGT-04 asserts them (upscale factor sourced from
  `constants.py`, SC-L013-5; determinism + no-new-colours via Hypothesis).
- Memory cost is dominated by the ×8 upscale (64× pixel count during processing); AGT-10
  may later issue a streaming/cap directive for very large sprites — not a change to these
  pins.
- If a future higher-fidelity similarity metric is wanted, that is a **new ADR** superseding
  this one, not an edit — these pins are immutable acceptance for Phase 2.

**Sources:** `docs/research-rotsprite-pixelperfect.md` (Topic 1 + §Limitations);
`specs/phase-2-advanced-drawing/spec.md` §4.1 REQ-P2-LOGIC-013, §10 CL-12, §9;
`specs/phase-2-advanced-drawing/plan.md` §5; `constitution.md` Article II.
