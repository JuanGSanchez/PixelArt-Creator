# ADR-0017 — Canonical sprite-sheet / atlas JSON schema: Aseprite-compatible (Array), rotation-free, trim-off default

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-7-export` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 7 emits **JSON metadata** describing every frame/sprite laid out on a sprite sheet or packed
into a texture atlas (REQ-P7-LOGIC-007/-008, REQ-P7-DATA-004). The spec deferred the **canonical
schema** to architecture (DEP-2/CL-6): the observable contract is fixed — a *valid, deterministic,
self-consistent* document whose coordinates round-trip against the packed image and that a named
tool re-imports — but the concrete schema is a HOW decision. Prior research
(`docs/research-phase-7-export-20260704.md`, Topic 2 + Open decision 1/2) surfaced three families:

- **Aseprite JSON** (Hash/Array layouts) — de-facto pixel-art interchange; native `frameTags` +
  per-frame `duration` map the shipped Phase-5 `Frame.duration_ms` + `frame_tags` (FR-1) 1:1;
  Aseprite **never rotates** in packing (`rotated` always `false`).
- **TexturePacker JSON** — same field vocabulary + `pivot` + `rotated` (TexturePacker *does* rotate
  90° to improve density, swapping `frame.w/h`).
- Emit both / an own schema.

A load-bearing fact from the shipped code: `logic/compactor.py` (CP-1, the MaxRects packer Phase 7
reuses, REQ-P7-LOGIC-006) has **rotation disabled** — it exposes **no `allowFlip`**, and its
`Placement(id, x, y, w, h)` carries **no rotation flag**. A reused-compactor atlas therefore *never*
produces a rotated region. Prior research also flagged (Topic 3) that neither Unity
`SpriteMetaData.rect` nor Godot `AtlasTexture.region` can express a rotated source region.

## Decision

**Adopt the Aseprite JSON *Array* layout as the single canonical sprite-sheet / atlas metadata
schema. Rotation is structurally absent (the CP-1 packer never rotates); trimming is OFF by default
this phase; Phase-5 `frame_tags` + `duration_ms` map straight into `meta.frameTags` + per-frame
`duration`.**

- **Array layout.** `"frames"` is an **ordered array**, each entry carrying its own `filename`
  (stable, index-addressable, avoids Aseprite's Hash-vs-index quirks). Per-frame fields:
  `filename`, `frame{x,y,w,h}` (rect on the sheet/atlas), `rotated` (**always `false`**),
  `trimmed`, `spriteSourceSize{x,y,w,h}`, `sourceSize{w,h}`, `duration` (ms).
- **`meta` block.** `app="pixelart-creator"`, `version` (our app version string), `image`
  (the sheet/atlas PNG filename), `format="RGBA8888"`, `size{w,h}`, `scale="1"`, and
  `frameTags[]` = `{name, from, to, direction}` built from the document's `frame_tags` (FR-1):
  `from`/`to` are indices into the `frames` array; `direction` maps the shipped `PlaybackMode`
  (`LOOP`/`ONCE`→`forward`, `REVERSE`→`reverse`, `PING_PONG`→`pingpong`).
- **Rotation is structurally absent.** Because CP-1 has no `allowFlip`, `rotated` is emitted as a
  constant `false` and `frame.w/h` are never swapped. This keeps the atlas Aseprite-compatible AND
  directly re-importable by Unity/Godot (whose region types cannot express rotation — ADR-0018). No
  rotation-derivation logic is needed on the compactor's `Placement`.
- **Trim OFF by default (this phase).** Frames are exported at full `sourceSize`; `trimmed=false`,
  `spriteSourceSize = {x:0, y:0, w:sourceSize.w, h:sourceSize.h}`, `frame.w/h == sourceSize.w/h`.
  This makes the coordinate/pixel round-trip (REQ-P7-LOGIC-007) trivially exact and sidesteps the
  Aseprite `--trim` + empty-frame `frameTags` index-desync bug (research §2.1, issue #1244). Trim +
  extrusion are an extensibility hook (Article XI), deferred without changing any acceptance
  criterion (the `spriteSourceSize`/`sourceSize` fields already carry the future offset).
- **Determinism.** The metadata is serialised with `json.dumps(obj, ensure_ascii=False,
  separators=(",", ":"), sort_keys=True)` over **integer** coordinates only — no floats, no
  wall-clock/`generated-on` field, stable key order — so it is byte-reproducible (REQ-P7-LOGIC-008,
  ADR-0019). No `pivot` (a TexturePacker extension) is emitted; pixel-art frames pivot at origin.
- **Not TexturePacker, not both.** One canonical schema keeps the byte-reproducibility + round-trip
  surface single (research matrix A: "emit both" = 2× the surface to test). Aseprite is the best
  pixel-art ecosystem fit and the only one that needs no rotation handling.

## Alternatives Considered

- **TexturePacker JSON (with `rotated`/`pivot`).** Rejected: the CP-1 packer never rotates, so
  `rotated` would always be `false` anyway; `pivot` is meaningless for origin-pivoted pixel-art
  frames; and rotation-capable schemas complicate Unity/Godot import (ADR-0018) for zero density gain
  here.
- **Emit both Aseprite + TexturePacker.** Rejected: doubles the deterministic-bytes + round-trip test
  matrix (Article IV) for no capability the single canonical schema lacks. A TexturePacker adapter is
  an Article XI extension if a consumer ever needs it.
- **Aseprite Hash layout.** Rejected: object-keyed frames are order-sensitive to serialise
  deterministically and reproduce the single-frame/empty-frame indexing quirks (research §2.1); the
  Array layout is explicitly ordered and index-addressable.
- **Trim ON by default.** Rejected this phase: trimming introduces the `spriteSourceSize` offset math
  and the Aseprite empty-frame `frameTags` desync risk into the *first* export release; deferring it
  keeps the round-trip exact and is a clean Article XI addition later.

## Consequences

**Positive.** One deterministic, byte-reproducible schema that maps Phase-5 tags/durations natively,
round-trips coordinates↔pixels exactly (trim-off), needs no rotation handling (CP-1 can't rotate),
and re-imports cleanly into both target engines. Single test surface for reproducibility + round-trip.

**Negative / risk.** Trim-off sheets/atlases are less densely packed than a trimming exporter would
produce (accepted — density is not a Phase-7 acceptance; extensibility hook preserved). Consumers
expecting *exact* Aseprite indexing under trimming must be re-validated when trim lands (deferred).
`meta.version` must be a fixed/injected value, never a build timestamp, or byte-reproducibility breaks
(enforced by ADR-0019's no-volatile-metadata rule).

## Grounding

- Spec `specs/phase-7-export/spec.md` §4 (REQ-P7-LOGIC-007/-008), §6 (canonical-schema non-goal),
  §10 CL-5/CL-6/CL-17, §11 SC-L007-1/SC-L008-1; `traceability.md` DEP-2, REQ-P7-DATA-004.
- Research `docs/research-phase-7-export-20260704.md` Topic 2 (§2.1 Aseprite Array example, §2.3 trim/
  rotation invariants, §2.4 Phase-5 tag/duration mapping), Topic 5 (CP-1 rotation flag), Open
  decisions 1/2/7, flags F-3.
- Shipped `logic/compactor.py` — `compact(rects, max_width, max_height) -> Packing`, rotation disabled,
  `Placement` has no rotation flag (CP-1).
- Constitution Article IV (headless deterministic test per criterion), X (traceability), XI
  (trim/extrusion/TexturePacker as later extensions); ADR-0018 (engine presets consume this schema),
  ADR-0019 (byte-reproducibility option set), ADR-0020 (module placement of the metadata builder).
- Forward-inherited: FR-1 (`Frame.duration_ms` + `frame_tags`, `PlaybackMode`), CP-1 (`compact`).
