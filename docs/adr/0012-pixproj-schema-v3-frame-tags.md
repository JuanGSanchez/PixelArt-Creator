# ADR-0012 — `.pixproj` schema version 3 (frame tags + stable `layer_id`) with v1/v2 back-compat load

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | AGT-01 (Architecture) |
| Feature | `phase-5-animation` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 5 adds frame **tags** — named animations, each a `{name, from, to, mode, repeat, color}`
range — to the `Document` (REQ-P5-LOGIC-009, REQ-P5-DATA-001), and an additive stable cross-frame
`layer_id` on each layer/group node so the timeline/onion/tags can address layer *tracks*
(research Q4 caveat). Per-frame `duration_ms` and the richer layer model **already persist** in
`.pixproj` v2 (`data/project_io.py`, ADR-0006), so only tags + `layer_id` are new. DEP-2 directs
AGT-01 to rule whether this is a schema-version bump or an additive field on v2; back-compat read of
tagless projects is required regardless (REQ-P5-DATA-003). Article VII requires the load stay
defensive (validated, bounds-checked, no `eval`/`exec`).

Two design questions follow: (1) does the format version change, and (2) how are frame-tag playback
modes represented on disk — natively, or in Aseprite's `direction` vocabulary (research Q3)?

## Decision

**Bump `FORMAT_VERSION` to `3`; serialise `frame_tags` (native `PlaybackMode` value strings) +
per-node `layer_id`; accept `version in {1, 2, 3}`; load v1/v2 (tagless) with an empty tag
collection and minted `layer_id`s. Saving always writes v3.**

- **Serialise (v3):** a document-level `"frame_tags"` array of `{name, from, to, mode, repeat,
  color}`; each node gains `"layer_id"` (int). `mode` is the **native `PlaybackMode` value string**
  (`"loop"`/`"once"`/`"ping_pong"`/`"reverse"`). Per-frame `"duration_ms"` and the v2 layer model
  are unchanged (reused).
- **Native mode, not Aseprite `direction` (decisive).** The research Q3 `direction ∈
  {forward,reverse,pingpong,pingpong_reverse}` is the **Phase-7 export** shape, not the on-disk
  representation. Aseprite's `direction` cannot express our `LOOP`-vs-`ONCE` distinction (a repeat
  concern in Aseprite), so storing `direction` would lose state and break REQ-P5-DATA-001 ("modes
  restored identically"). `.pixproj` stores the native mode; Phase-7 export maps `mode` →
  `direction` + `repeat`.
- **Deserialise (defensive, Article VII / REQ-P5-DATA-003):** reject an inverted/out-of-range tag
  range, an unknown `mode`, a non-int/negative `repeat`, a malformed tag object, or a `frame_tags`
  that is not a list — each with `ProjectIOError`. No `eval`/`exec`; paths via `pathlib`. A payload
  without `frame_tags` loads with an empty collection; nodes lacking `layer_id` get minted ids
  (back-compat).
- `FORMAT_VERSION` stays **format-intrinsic**, local to `project_io.py` (ADR-0001 / ADR-0006
  precedent). `_SUPPORTED_VERSIONS = (1, 2, 3)`; the v2 frame/layer parse path is reused, extended
  only to read tags + `layer_id`.

## Alternatives Considered

- **Additive optional field on v2 (no version bump).** Rejected. It technically keeps back-compat
  (the shipped v2 loader ignores unknown top-level keys), but it repeats exactly what ADR-0006
  rejected for Phase 4: `frame_tags` is **new document-level semantics** (named animations) and
  `layer_id` is new node identity, and the version field is the honest, self-describing signal —
  ADR-0006 explicitly anticipated the *animation timeline* as a future version. A v3 stamp makes a
  Phase-4 v2 reader **fail-closed** on a tag-bearing file rather than silently dropping the
  animations (Article VII posture). The bump costs nothing: v1/v2 still load with empty tags.
- **Store Aseprite `direction` for near-direct export.** Rejected: lossy for our `PlaybackMode`
  (loses `LOOP`/`ONCE`), breaking the lossless round-trip acceptance. Export mapping belongs to
  Phase 7.
- **New file extension / separate tag sidecar.** Rejected: over-engineered; `.pixproj` is the one
  project format (S7); a version field inside it is the standard evolution and preserves one
  save/open path.
- **v3-only loader (drop v1/v2).** Rejected: orphans every file saved by Phases 1–4. Back-compat
  read is mandatory; back-compat *write* is not (forward-incompat is acceptable, per ADR-0006).

## Consequences

**Positive.** Tags + `layer_id` round-trip losslessly (REQ-P5-DATA-001); tagless v1/v2 projects
keep opening (REQ-P5-DATA-002/003); the version field keeps the format self-describing for Phase 7
export; one defensive validator, one save/open path. Native-mode storage keeps the round-trip
lossless and defers the Aseprite mapping to the export phase that owns it.

**Negative / risk.** The loader gains a third branch (v1/v2/v3); all three are covered by AGT-04
tests, including a checked-in v2 fixture that loads (empty tags) and re-saves as v3. Tag validation
must be fail-closed (Article VII); the loader rejects malformed/out-of-range tags rather than
clamping on load (clamping is a *runtime* frame-op concern, REQ-P5-LOGIC-010, not a load concern).

## Grounding

- Spec `specs/phase-5-animation/spec.md` §4 (REQ-P5-DATA-001/002/003), §8 DEP-2, §10 CL-15;
  `traceability.md` DEP-2; `plan.md` §6.
- Research `docs/research-phase5-animation.md` Q3 (frame-tag schema, Aseprite `frameTags`), Q4
  (stable `layer_id`).
- ADR-0006 (`.pixproj` v2 layer model + version-bump rationale + v1 back-compat), ADR-0001
  (`FORMAT_VERSION` intrinsic-local); ADR-0011 (native `PlaybackMode`).
- Constitution Article VII (validated, bounds-checked, no `eval`/`exec`), II (`FORMAT_VERSION`
  intrinsic exemption).
- Shipped `data/project_io.py` (`FORMAT_VERSION = 2`, `_SUPPORTED_VERSIONS = (1, 2)` → `(1, 2, 3)`).
