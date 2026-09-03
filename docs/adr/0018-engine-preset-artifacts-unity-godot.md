# ADR-0018 — Engine-preset artifacts: Unity `.meta` (pinned 2022.3 LTS) + Godot `SpriteFrames.tres` (pinned 4.2)

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-7-export` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 7 must ship **engine presets** — at minimum **Unity** and **Godot** — whose output a named
engine's importer consumes as sprites/animations **without manual fixup** (REQ-P7-LOGIC-011,
REQ-P7-DATA-002, REQ-P7-UI-006). The spec deferred the **exact artifact set** to architecture (DEP-2/CL-7);
the observable contract (engine-ready re-import + byte-reproducible) is fixed. Prior research
(`docs/research-phase-7-export-20260704.md`, Topic 3 + Open decision 3, flags F-4/F-5) laid out the
options and their fragilities:

- **Unity:** (a) uniform grid sheet + Unity auto-slice (zero metadata, but forces equal cells —
  defeats a packed atlas); (b) generate the `.meta` YAML with a populated
  `TextureImporter.spriteSheet` (explicit `rect`/`pivot`/`name` per sprite) — true 1:1 for a packed
  sheet but the `.meta` schema is Unity-version-sensitive (F-4); (c) neutral JSON + a shipped
  AssetPostprocessor C# script.
- **Godot 4:** (a) `SpriteFrames.tres` (best for animations — named `animations` of `AtlasTexture`
  frames + `speed`/`loop`); (b) per-frame `AtlasTexture.tres`; (c) PNG + JSON + a community addon.
  `.tres` header/`format`/UID lines vary 4.0→4.x (F-5).
- **Rotation caveat (both engines):** neither Unity `SpriteMetaData.rect` nor Godot
  `AtlasTexture.region` can express a 90°-rotated region.

The shipped CP-1 packer has rotation **disabled** (no `allowFlip`; ADR-0017), so the rotation caveat
is already satisfied — every emitted region is axis-aligned.

## Decision

**Emit a concrete, deterministic, self-describing text artifact per engine, alongside the exported
PNG sheet/atlas, pinned to one target engine version each:**

- **Unity preset →** the PNG sheet/atlas **+ a Unity `.meta` YAML** targeting **Unity 2022.3 LTS**,
  with `TextureImporter.spriteImportMode = 2` (Multiple), `filterMode = 0` (Point / no blur),
  `textureCompression = 0` (Uncompressed), mipmaps off, and a populated
  `spriteSheet.sprites[]` — one entry per frame with explicit `rect` (px, y-up: Unity's origin is
  bottom-left, so `rect.y = sheet_height − frame.y − frame.h`), `name`, `pivot` (0.5,0.5),
  `alignment=0`, and the paired `internalIDToNameTable` / `nameFileIdTable` entries. This is the true
  "no manual fixup" import for an irregular/packed atlas (research option (b)).
- **Godot preset →** the PNG sheet/atlas **+ a `SpriteFrames` `.tres`** targeting **Godot 4.2**:
  `[gd_resource type="SpriteFrames" format=3 ...]`, one `[ext_resource type="Texture2D"]` for the
  PNG, one `[sub_resource type="AtlasTexture"]` per frame with `atlas = ExtResource(...)` +
  `region = Rect2(x, y, w, h)` (Godot origin is top-left — the atlas rects map directly, no y-flip),
  and an `animations` array grouping frames by Phase-5 `frameTags` name with `speed` (fps derived
  from the tag's mean `duration_ms`) + `loop` (from the tag's `PlaybackMode`). `SpriteFrames` is the
  most engine-ready target for Phase-5 tagged animations (research option (a)).
- **Version pinning (mitigates F-4/F-5).** The target versions (Unity 2022.3 LTS, Godot 4.2) are
  recorded as **module-local format identifiers** in the writer (ADR-0001 exemption — they are
  intrinsic to the wire format, like the Tiled `tiledversion` string in `data/tiled_io.py`), not in
  `constants.py`. The `.meta`/`.tres` are hand-written deterministic text; the fragility is bounded
  by declaring the pinned version in the emitted header + the ADR.
- **Placement (ADR-0020).** The engine-ready **layout + neutral metadata** (which frame at which
  rect, the tags) is computed in `logic/` (REQ-P7-LOGIC-011); the **engine-specific serialisation +
  file write** is `data/export_io.py` (REQ-P7-DATA-002) — the same split as Phase-6
  `data/tiled_io.py` (build+serialise a wire format in `data/`, over a `logic/`-computed model).
- **Rotation-free.** Every region is axis-aligned (CP-1 never rotates), so both artifacts express
  every sprite with a plain rect/region — no per-sprite un-rotate handling (research rotation caveat
  resolved by ADR-0017).
- **Determinism.** Both artifacts are built from the same integer-coordinate layout, stable key/entry
  order, no timestamps, no GUIDs derived from wall-clock (Unity `guid` + Godot `uid` are derived
  deterministically from the sheet content hash, not `datetime.now()`) — byte-reproducible per
  ADR-0019.

## Alternatives Considered

- **Unity uniform-grid + auto-slice (no `.meta`).** Rejected: forces equal-cell layout, defeating the
  MaxRects atlas (REQ-P7-LOGIC-006) and failing "no manual fixup" for a packed/heterogeneous atlas.
- **Unity neutral-JSON + shipped C# AssetPostprocessor.** Rejected for the default deliverable: the
  Aseprite JSON (ADR-0017) is already emitted and a consumer *may* wire an importer, but shipping and
  testing a C# script is outside this Python platform's headless test surface; the `.meta` is the
  in-repo deterministic, test-verifiable artifact.
- **Godot per-frame `AtlasTexture.tres` files.** Rejected as the default: better for sharing static
  frames across scenes, but `SpriteFrames` is the direct target for Phase-5 tagged animations and is
  one file, not N. Per-frame `AtlasTexture` is an Article XI extension.
- **No version pin (emit "latest").** Rejected: `.meta`/`.tres` schemas drift across engine versions
  (F-4/F-5); an unpinned artifact silently rots. Pinning + declaring the version in the header is the
  honest, testable contract.

## Consequences

**Positive.** Each preset produces a single deterministic, in-repo-testable artifact that imports 1:1
into the pinned engine version with no manual fixup, reusing the ADR-0017 rotation-free layout +
Phase-5 tags. The test suite can golden-file both artifacts headlessly.

**Negative / risk.** The `.meta`/`.tres` formats are version-fragile; a user on a different
Unity/Godot version may need a re-import or a minor field tweak — bounded by the declared pin and an
Article XI path to add versions/adapters. Unity's bottom-left origin requires a y-flip on `rect.y`
(a documented, tested transform) that Godot does not; the writer must not conflate the two coordinate
conventions (asserted by the test suite round-trip tests).

## Grounding

- Spec `specs/phase-7-export/spec.md` §2 (engine presets), §4 (REQ-P7-LOGIC-011, REQ-P7-DATA-002),
  §11 SC-L011-1/SC-D002-1; `traceability.md` DEP-2.
- Research `docs/research-phase-7-export-20260704.md` Topic 3 (§3.1 Unity SpriteMetaData/`.meta`,
  §3.2 Godot `SpriteFrames`/`AtlasTexture`, rotation caveat), Open decision 3, flags F-4/F-5.
- Shipped `logic/compactor.py` (rotation disabled — regions are axis-aligned); Phase-5 `frame_tags` +
  `PlaybackMode` (FR-1) → animation grouping; ADR-0017 (the neutral layout/schema both presets
  consume), ADR-0019 (byte-reproducibility), ADR-0020 (logic-computes-layout / data-serialises split).
- Constitution Article II (version strings intrinsic-local, ADR-0001), IV (headless golden-file test),
  VII (portable paths), XI (per-frame AtlasTexture / additional engine versions as extensions).
