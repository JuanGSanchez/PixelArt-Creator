# ADR-0044 — Web-viewer pixel fidelity is **byte-exact (0 LSB)**; the ±1 LSB harness tolerance is withdrawn

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-31 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-13-cross-platform` (Slice 13E — web companion viewer) |
| Supersedes | — |
| Superseded by | — |
| Relates to | ADR-0036 §A.4/A.6 (**refined** — A.4/A.6 state no tolerance; this ADR supplies the missing number), ADR-0005 + REQ-P4-LOGIC-003 (`blend_arrays(NORMAL)` == `blend_over` at **zero** tolerance — the governing precedent), ADR-0033/ADR-0034 (byte-exact fast paths), ADR-0035 (`web_viewer/` placement) |

## Context

The web viewer's pixel-fidelity requirement was stated three incompatible ways, and an agent
authoring tests against it correctly refused to invent a number and escalated instead:

| Source | Says |
| --- | --- |
| the shipped comparison harness — `web_viewer/tests/generate_reference.py`, `test_render_fidelity.py`, `viewer_core.test.mjs` | **≤ 1 LSB** per channel |
| the web-client agent's constraint **C3** | **0 LSB** — exact |
| **ADR-0036 §A.4/A.6** | **no number at all** |

Three sources, three answers, and the loosest one is the one CI actually enforces. That is the worst
possible arrangement: the strictest statement is unenforced prose, the vaguest is the architecture
of record, and the shipped gate silently accepts a class of error nobody ever decided to accept.

### What the harness actually compares

Before ruling I read what is being compared, because a tolerance introduced to paper over a real
rounding difference means something entirely different from one added defensively.

- **Reference side.** `generate_reference.py` builds a deterministic op-log (2 layers, an opaque base
  tile, an offset edge tile at `tile_x=1`, a partial-alpha top tile, a stale LWW loser, and a
  `LayerAttrOp` opacity of 0.75), pushes it through the **shipped** `sync_protocol` ->
  `realtime_apply.apply_remote` -> `convergence` -> `blend.composite_stack` path, and takes the
  resulting composited RGBA as truth.
- **Mirror side.** The same op-log is replayed through a Python transcription of `viewer.js`'s pure
  logic (`decodeMessage` -> `decodeUpdate` -> LWW `accept` -> `blendTile` source-over).
- **Real-JS side.** `viewer_core.test.mjs` runs the *actual shipped* `viewer_core.mjs` under node
  against the emitted `fidelity_fixture.json` and diffs against the same expected bytes.

So the comparison is: **the shipped Python compositor vs. the shipped JS compositor, on identical
wire input.** Both are straight-alpha source-over in the 0..255 range, in the same operation order,
in float64 (JS numbers are float64), finishing with round-half-to-even — numpy's `np.round` on one
side, ECMAScript `ToUint8Clamp` (implicit on assignment into a `Uint8ClampedArray`) on the other.

### Why the tolerance exists — the decisive finding

**It does not paper over a real difference. Its stated justification is contradicted by the same
file, sixty lines later.**

`generate_reference.py`'s module docstring justifies the margin as *"the frontend-flagged
`Uint8ClampedArray`-vs-numpy rounding margin."* Its own `_u8_clamp` docstring then says:

> *numpy `np.round` (used by the shipped `_blend_over_arrays`) is also round-half-to-even, so the
> two agree.*

And the **shipped product** goes further still. `viewer_core.mjs`'s `blendTile` documents:

> *assigning a float to it performs ECMAScript `ToUint8Clamp` (round-half-to-EVEN + clip), matching
> numpy's `np.round` + clip in the shipped `_blend_over_arrays` — **the exact rounding that produced
> the 0-LSB match**.*

The product already claims 0. Only the gate still permits 1. The tolerance is **defensive residue**
from before `viewer_core.mjs` was extracted, when the JS was untested and a margin looked prudent.

### Measurement, not inference

Obligation: prove it, do not reason about it.

```
Real shipped JS (viewer_core.mjs) vs the shipped Python reference, over fidelity_fixture.json:
    dims 68 x 3, 816 channels
    max |diff|      = 0
    channels != 0   = 0            (fixture field still records tolerance_lsb: 1)

Python mirror of viewer.js vs the same reference:
    max |diff|      = 0
    exact pixels    = 204 / 204

Randomised stress, 60 trials, same op shape, seeded:
    opacity drawn from {1.0, 0.999, 0.75, 0.5019607843137255, 0.5, 0.33, 0.1}
    random RGBA source patterns (all alpha values reachable)
    max |diff| across all 60 trials = 0
```

Zero. Not "within one" — **zero**, on every channel, including the deliberately awkward
`0.5019607843137255` (= 128/255) opacity chosen to land on rounding boundaries. The ±1 licence has
**never been exercised**. It is not buying compatibility with anything; it is buying silence about a
future regression.

## Decision

### 1. The web viewer's pixel-fidelity contract is **byte-exact: 0 LSB per channel**

The reconstructed RGBA the viewer composites MUST equal the shipped
`realtime_apply` -> `convergence` -> `blend.composite_stack` composite **byte for byte**, for the
same op-log. **The web-client agent's constraint C3 was right and stands unchanged.** The harness is
wrong and the architecture of record was silent; both are corrected here, not the constraint.

### 2. Why 1 LSB is not acceptable *in this product*

Four reasons, in descending force. The first is the one that would settle it alone.

**(a) The project already ruled this exact question, in the compositor the viewer is reproducing.**
`logic/blend.py::_blend_over_arrays` exists *because* the generic float32 separable path *"diverged
by ≤ 1 LSB at rounding boundaries, which this dedicated float64 path removes for the DEFAULT
mode."* That work restored **REQ-P4-LOGIC-003 / ADR-0005**: `blend_arrays(NORMAL)` equals
`blend_over` elementwise with **zero tolerance** — a *frozen contract*. ADR-0033 and ADR-0034
likewise required their optimised paths to be **byte-exact** against the naive composite. The
platform has paid, repeatedly and deliberately, to eliminate error of precisely this magnitude. A
viewer whose entire job is to reproduce that compositor's output cannot hold a **weaker** contract
than the compositor itself. Permitting ±1 in the browser would mean the desktop is bit-exact with
itself while the browser is licensed to drift — same document, same ops, same arithmetic, two
standards. That is not a tolerance; it is an inconsistency with a number attached.

**(b) In pixel art the exact value *is* the content.** This is not photographic imagery where 1/255
is beneath perception and therefore beneath concern. The medium's unit of work is the individual
pixel and its exact value: users choose colours by hex, curate palettes, and depend on **exact
equality** for flood-fill, replace-colour and palette-index semantics. Rendering `#3C6E90` as
`#3C6E91` is invisible to the eye and corrosive to the semantics — two regions the artist made
identical can render non-identical; an eyedropper or screenshot round-trip stops matching the
palette; a viewer-side "which pixels are this colour" question gets a different answer than the
editor's. The perceptual argument for ±1 is real and irrelevant, because the failure it licenses is
not a perceptual one.

**(c) ADR-0036 §A.6(e) is already a zero-tolerance criterion on the other half of the pipeline.** It
requires every source pixel to occupy an `S × DPR` block of physical pixels *"each block being a
single flat RGBA **equal to the source pixel**"* — no interpolated boundary, integer scale,
`imageSmoothingEnabled = false`, `image-rendering: pixelated`. A ±1 tolerance upstream of that does
not soften anything; it means the flat block is rendered exactly, faithfully and crisply in the
**wrong colour**, magnified into an `S × DPR` square of it. Nearest-neighbour scaling does not
launder a compositing error — it enlarges it. Leaving A.6 at 0 while A.4 tolerates 1 is the
contradiction in miniature.

**(d) A per-step tolerance is a ratchet, not a bound.** The ±1 is asserted on the *final* image of a
**2-layer** fixture. Nothing in it constrains **accumulation**: layers composite sequentially, so a
per-blend licence of 1 LSB over a 12-layer document has no stated bound at all. Either the number is
0 — which is stable under composition, since exact ∘ exact = exact — or the contract owes a
depth-dependent bound that nobody has written and nobody wants to maintain. 0 is the only value that
survives the document growing.

### 3. Scope of the rule — stated precisely, so it is not over- or under-read

The 0-LSB rule binds **the compositing path the viewer actually implements**: LWW op replay, layer
draw order, layer `visible`, layer `opacity`, and **straight-alpha source-over** blending, finishing
in a `Uint8ClampedArray`. Verified against the shipped code: `compositeModel` honours `visible` and
`opacity` only, and `viewer.js` performs exactly **one** canvas operation — `putImageData` — of the
already-composited buffer.

**Explicitly carved out and NOT decided here:** the eleven **non-normal blend modes**. The wire
op-log carries no blend-mode attribute the viewer honours, so no such pixel exists today. On the
desktop those modes run through the float32 separable path that the platform itself documents as
diverging ≤ 1 LSB (ADR-0005, T13 D5). If a non-normal mode is ever surfaced in the viewer it
inherits *that* situation, and the tolerance for it must be decided **then, in the open** — it is
not pre-relaxed by this ADR, and this ADR must not be cited as having settled it.

### 4. What this forbids (the real cost, named)

Ruling 0 costs **nothing measured** — the shipped code already meets it, at margin zero. The cost is
prospective and it is a genuine constraint on `agt-11-web-client`:

- **The browser's own compositing may not be used to composite layers.** `ctx.globalAlpha` +
  `drawImage`, `globalCompositeOperation: "source-over"`, or layering multiple `<canvas>` elements
  are all implementation-defined (typically premultiplied 8-bit, engine-dependent) and will **not**
  be byte-exact. The viewer must keep doing the blend itself and `putImageData` the finished buffer
  — which is exactly what it does now. This ADR freezes that.
- **`Uint8ClampedArray` is load-bearing, not incidental.** Swapping in a `Uint8Array` with manual
  `Math.round` would change half-way rounding from half-to-even to half-away-from-zero and break
  exactness immediately.
- **No fixed-point / integer-approximate blending** as a performance optimisation, and no WebGL/WebGPU
  offload of the composite unless it is proven byte-exact by the same gate.

If any of those becomes necessary for performance, it comes **back here as an amendment with a
measurement**, not as a quiet loosening of an assertion.

### 5. Form: a new ADR, not an amendment to ADR-0036

Considered and rejected: folding this into ADR-0036 as Addendum B. ADR-0036's Addendum A is
explicitly a **pre-build** resolution of six contract points, written before the JS replay existed —
at which time no tolerance *could* have been decided, which is precisely why A.4/A.6 state no
number. Inserting a **post-ship measurement** into that document would blur the record of what was
known when, and the ruling additionally governs artifacts outside ADR-0036's scope (a test harness,
a node gate, an agent constraint). ADR-0036 is left **untouched and immutable**; this ADR names it as
refined.

## Consequences

**Obligations on the harness (owner: AGT-06, who owns `web_viewer/tests`; NOT discharged here — the
harness is outside this change's declared write surface).** All six are mechanical; none of them can
fail, because the measured delta is already 0:

1. `web_viewer/tests/test_render_fidelity.py:42` — `assert int(diff.max()) <= 1` becomes
   `assert int(diff.max()) == 0`; rename `test_js_mirror_matches_shipped_reference_within_1_lsb` to
   a `..._byte_exact` name so the test's *name* stops asserting the withdrawn contract.
2. `web_viewer/tests/viewer_core.test.mjs:35` — `const TOLERANCE_LSB = 1;` becomes `= 0`. Keep the
   constant (the failure message quoting the measured `maxDiff` is worth keeping); update the test
   title, which currently reads "within +/-1 LSB".
3. `web_viewer/tests/generate_reference.py` — `main()`'s `if max_diff > 1:` becomes `if max_diff != 0:`;
   the printed `"... LSB (tolerance +/-1)"` line and the PASS/FAIL strings updated.
4. Same file, module docstring ¶2 — **delete the false justification**. The claim that ±1 covers "the
   frontend-flagged `Uint8ClampedArray`-vs-numpy rounding margin" is contradicted by `_u8_clamp`'s
   own docstring and by measurement. Replace it with the byte-exactness statement and a pointer here.
5. `fidelity_fixture.json` — the emitted `"tolerance_lsb": 1` becomes `0`. **The expected RGBA is
   already byte-identical**, so this is the only field that changes. Regeneration here is legitimate
   *because the delta is 0*; the standing integrity rule is unaffected — **a fixture is never
   regenerated to make a non-zero delta disappear.**
6. `test_render_fidelity.py` and `generate_reference.py` both assert in prose that
   `pyproject.toml` pins `testpaths = ["tests"]` and that `web_viewer/tests` is *"never
   auto-collected"* / *"NOT part of the default gate"*. **This is stale and materially wrong**: the
   manifest reads `testpaths = ["tests", "web_viewer/tests"]`, so these tests **do** run in the
   default gate on every push. Fix both comments — a reader who believes them will mis-judge the
   blast radius of a change here.

**Obligation on evidence breadth (owner: AGT-06 / AGT-13).** One 68×3, two-layer fixture with a
single opacity is **thin** support for a byte-exactness contract, even though it currently passes at
0. The randomised 60-trial stress reported above found 0 everywhere, but that evidence lives in this
ADR, not in the repo as a standing test. A second fixture (or a parameterised one) should cover:
≥ 3 stacked layers; a hidden layer (`visible: false`); opacity/alpha pairs landing on `.5` rounding
boundaries; a tile at non-zero `tile_y`; and a partial tile clipped by the canvas edge. Byte-exact is
a strong claim and deserves to be tested where it is most likely to fail.

**Obligation on the agent roster (owner: whoever holds the roster; NOT touched here).** `C3` needs no
change — it was correct. Any *other* agent constraint quoting "±1 LSB" must be brought to 0 and
cite this ADR.

**Positive.** One number, in one place, with a measurement behind it. The gate now fails on the first
byte of drift instead of absorbing it, which is what a fidelity gate is for. The viewer's contract
matches the compositor's frozen `blend_over` contract instead of being quietly weaker than it.

**Negative / accepted.** `agt-11-web-client` loses several plausible optimisation routes (§4), and a
future browser-engine change to `ToUint8Clamp` semantics — vanishingly unlikely, it is specified in
ECMA-262 — would surface as a hard CI failure rather than an absorbed ±1. That visibility is the
intent.

## Not verified (stated per the obligation to say what was not checked)

- **No real browser was exercised.** Exactness was measured under **node v24.18.0** against the
  shipped `viewer_core.mjs`, and against a Python transcription. Node and browsers share the ECMA-262
  `ToUint8Clamp` definition, so the result should carry, but no Chrome/Safari/Firefox run backs this
  ADR.
- **ADR-0036 §A.6's device criterion (real iOS Safari at DPR > 1) remains unverified by me.** This
  ADR governs the composite that is handed to `putImageData`; it says nothing new about the
  display/scaling half beyond noting that A.6 is already a 0-tolerance criterion.
- **The 60-trial stress used one op-log *shape*** (2 layers, 2 tiles, one opacity attr) with
  randomised colour/alpha/opacity. It does **not** cover layer counts > 2, hidden layers, non-zero
  `tile_y`, or edge-clipped tiles — which is exactly why the evidence-breadth obligation above is
  filed rather than waived.
