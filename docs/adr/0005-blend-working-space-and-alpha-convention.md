# ADR-0005 — Blend working space and straight-alpha convention for `logic/blend.py`

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-02 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-4-layer-canvas` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 4 introduces `logic/blend.py` — the 13-mode `BlendMode` enum, the per-mode blend
maths, and the stack compositor (REQ-P4-LOGIC-001..007). The blend maths must be pinned to
an authoritative, unambiguous convention before implementation, because the two most common
blend-mode bugs are (a) blending on **premultiplied** instead of straight colour, and (b)
the wrong `soft-light` piecewise variant. The Researcher grounded the maths in the W3C
*Compositing and Blending Level 1* spec (`docs/research-blend-modes.md`, HIGH confidence,
the reference Photoshop/SVG/Krita follow).

Two facts constrain the choice:

1. **The W3C spec is explicit:** *"The blending calculations must not use pre-multiplied
   color values."* (research §0). Colour and alpha are normalised **0..1**; separable modes
   apply `B(Cb, Cs)` per channel on **straight** RGB.
2. **The shipped substrate is straight-alpha.** `color.blend_over` (FU-3, Phase-1) is
   straight-alpha source-over on `uint8` `0..255` tuples, and `PixelBuffer` stores straight
   RGBA `uint8`. REQ-P4-LOGIC-003 requires `NORMAL` to **delegate to `color.blend_over`**,
   not re-derive it.

## Decision

**`logic/blend.py` blends in float32, normalised `0..1`, on straight (non-premultiplied)
alpha, and `NORMAL` delegates to `color.blend_over`.**

- Convert `uint8 → float32` on entry (`/255.0`) and `float32 → uint8` on exit
  (`np.clip(np.round(x*255.0), 0, 255).astype(np.uint8)`).
- Separable modes compute `B(Cb, Cs)` per channel on straight values, then apply the W3C §3
  compositing step: `Cs' = (1−αb)Cs + αb·B; αo = αs + αb(1−αs); αo·Co = αs·Cs' +
  (1−αs)αb·Cb; Co = 0 if αo == 0`.
- `BlendMode.NORMAL` (`B = Cs`) is **not** re-implemented; `blend_pixels(NORMAL, src, dst)`
  returns `color.blend_over(src, dst)` exactly (REQ-P4-LOGIC-003), and a stack of `NORMAL`
  layers equals folding `blend_over` bottom-to-top (SC-L007-1).
- `soft-light` uses the W3C `D(Cb)` sqrt/cubic variant (Horner cubic
  `((16·Cb − 12)·Cb + 4)·Cb` for `Cb ≤ 0.25`, else `sqrt(Cb)`), **not** the Pegtop/pow
  approximation. It is validated against the research §3 reference values (SC-L002-1).
- The blend-formula magic numbers (`/255`, `0.5`, `0.25`, `16/12/4`, the `2·Cs` / `2·Cs−1`
  factors, the `Lum` weights `0.3/0.59/0.11`) are **intrinsic to the W3C algorithm** and per
  ADR-0001 stay **module-local** in `blend.py` — they are not tuning knobs and do not go to
  `constants.py`.

The four **non-separable** modes (hue / saturation / colour / luminosity) are **out of scope
this phase**: the spec's `BlendMode` enumerates exactly **12** — the full W3C separable set,
which **already includes normal** (NORMAL + 11 non-normal separable modes) — and the research §2
marks the non-separable set advanced/deferred. **[FU-13 count correction, 2026-07-02]** the prior
wording "12 separable modes + normal = 13" **double-counted normal** (normal is itself one of the
W3C separable modes); the enum has **12** members, not 13.

## Alternatives Considered

- **Premultiplied-alpha blend pipeline.** Rejected: the W3C spec forbids premultiplied blend
  math, and the shipped `color.blend_over` / `PixelBuffer` are straight-alpha; a premultiplied
  path would diverge from FU-3 and re-introduce the un-premultiply/divide-by-α guard the spec
  warns against. Straight alpha keeps `NORMAL` a literal delegation to `blend_over`.
- **Integer/`uint8` blend math throughout.** Rejected: the piecewise modes (dodge/burn/
  soft-light) need sub-integer precision and division; the W3C formulas are defined on `0..1`
  reals. Float32 in / `uint8` out matches the spec and the F7 NumPy pipeline.
- **Pegtop soft-light approximation.** Rejected: it does not match the W3C/Photoshop result;
  it is the single most common blend bug. The `D(Cb)` variant is dataset-tested.

## Consequences

**Positive.** One authoritative, testable convention; `NORMAL` provably equals FU-3
(no drift from the shipped compositing primitive); a dataset-backed soft-light guard; a
vectorised float pipeline that reuses `PixelBuffer` and holds the F7 performance posture.
`sdd-analyze` and AGT-04 get an unambiguous acceptance criterion (match the research §3
values on known inputs).

**Negative / risk.** Float round-trips must clamp/round deterministically (P2) so identical
inputs give identical `uint8` output; AGT-04's determinism property test (SC-L002-2) guards
this. The float↔uint8 boundary is the one place rounding matters; it is centralised in
`blend.py`'s entry/exit converters.

## Compliance note (T13) — 2026-07-02

AGT-10's T13 profile (`subagent-report-agt-10-rendering-performance-a4b1282f-20260702T181039.md`
§5, D5) found the shipped `logic/blend.py` converts to **`float64`** in its blend path, deviating
from this ADR's decision (**float32**, above). This ADR is **not changed** — float32 was and remains
the mandated working dtype; the implementation must be corrected to `float32` (the entry converter
`/255.0` and all intermediate arrays cast to `np.float32`, exit `np.clip(np.round(x*255.0),0,255)
.astype(np.uint8)`). At 8K the blend is memory-bandwidth bound, so float32 roughly halves per-pixel
memory/time with ample precision for 8-bit output. Owner: **AGT-03**. No behaviour change beyond the
already-deterministic float→uint8 rounding boundary. Cross-referenced by ADR-0007 §Amendment (T13) D5.

## Grounding

- `docs/research-blend-modes.md` §0 (straight-alpha rule, 0..1 range), §1/§3 (per-mode
  formulas + compositing step), §4 (implementation recommendations) — The Researcher, W3C
  *Compositing and Blending Level 1* (HIGH).
- Spec `specs/phase-4-layer-canvas/spec.md` REQ-P4-LOGIC-001/-002/-003; plan §2/§5/§8.
- ADR-0001 (tuning vs. intrinsic constants) — the blend-formula literals are intrinsic.
- Phase-1 `logic/color.py` `blend_over` (FU-3) — the delegation target for `NORMAL`.
