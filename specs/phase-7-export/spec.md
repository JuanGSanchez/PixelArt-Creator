# Specification — Phase 7: Export & Pipeline Integration

| Field | Value |
| --- | --- |
| Feature | `phase-7-export` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no export engine (`logic/export.py`, `logic/atlas.py`), export UI, engine-preset writers, or CLI export entrypoint exists yet. The `PixelBuffer` (source pixels), `blend.composite_stack` (per-frame layer flatten), the `Document → frames` tree, the deterministic `logic/compactor.py` MaxRects packer, and the defensive `data/project_io.py` load pattern are **already shipped** and are reused, not re-authored. This spec defines the WHAT/WHY Phase 7 realises. |
| REQ-ID range | `REQ-P7-LOGIC-001..013`, `REQ-P7-UI-001..013`, `REQ-P7-DATA-001..004` (from the ROADMAP reserved `REQ-P7-LOGIC-*` / `REQ-P7-UI-*` / `REQ-P7-DATA-*` prefixes) |
| Layer scope | `pixelart_creator/logic/` (new `export.py` — export model + the deterministic, byte-reproducible encoding/layout pipeline for PNG / GIF / sprite-sheet; new `atlas.py` — texture-atlas layout reusing `compactor.compact` (CP-1); new constants) — **zero Qt, fully headless-drivable** + `pixelart_creator/data/` (portable file/JSON serialisation of encoded bytes + metadata; engine-preset artifact writers (Unity / Godot); reading a fixed `.pixproj` for the CLI path via the `project_io.py` pattern, IO-3) — **zero Qt** + `pixelart_creator/ui/` (export dialogs/menus: format pickers, GIF/sheet/atlas options, batch-export UI, engine-preset selection, progress) — **the only Qt surface** + a **headless CLI export entrypoint** (Qt-free; imports only `logic/` + `data/`) that drives the same export engine so CLI output equals GUI output byte-for-byte. |
| Binds to (upstream, **shipped** — REUSED) | Phase 1 `logic/pixel_buffer.py` (`PixelBuffer.data` / `.region` — the source pixels being exported — the **PB-1** primitive), Phase 4 `logic/blend.composite_stack` (flattens one frame's ordered layer stack into a single RGBA buffer — the **CO-4** primitive reused to produce the flat image every export encodes), Phase 1/5 `logic/document.py` `Document → frames` (`Frame` + `Frame.duration_ms` — the **FR-1** primitive: the frame sequence feeding sprite-sheet / GIF export), `logic/compactor.py` `compact(rects, max_width, max_height) -> Packing` (deterministic MaxRects BSSF, **rotation disabled**, no time/random; `Placement(id,x,y,w,h)`; `CompactionError` — the **CP-1** primitive for non-overlapping atlas packing), Phase 1/4 `data/project_io.py` (defensive, type/bounds-checked, no-`eval`, `pathlib` load; `ProjectIOError`; `_SUPPORTED_VERSIONS` — the **IO-3** primitive/pattern the CLI reuses to load a fixed input), `logic/document.py` (`Document` tree — the **DOC-1** export subject) |
| Depends on (external) | The Researcher — `docs/research-phase7-export.md` (grounds deterministic Pillow PNG/GIF encoder options, the sprite-sheet / atlas JSON schema landscape (Aseprite JSON vs TexturePacker), Unity/Godot import-artifact conventions, and APNG feasibility). **Concurrent — being produced in parallel** (feeds AGT-01) — see DEP-1. This spec fixes the WHAT/acceptance around the observable contract and records export-parity defaults; the HOW is AGT-01/ADR. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The platform already produces everything an export pipeline consumes: `PixelBuffer` holds the
source pixels (PB-1); `blend.composite_stack` flattens one frame's ordered layer stack into a single
RGBA buffer (CO-4); the `Document → frames` tree carries the animation frame sequence with per-frame
`duration_ms` (FR-1); the shipped `logic/compactor.py` MaxRects packer places rectangles into a
single atlas **deterministically, rotation disabled, with no wall-clock or randomness** (CP-1); and
`data/project_io.py` demonstrates the defensive, validated, `eval`-free load the platform mandates
(IO-3). What is missing is the **export & pipeline-integration system** that turns those primitives
into production output: **PNG** (single flat image), **animated GIF** (from the frame sequence),
**sprite sheets** (frames laid out on a grid), a **texture atlas** (MaxRects-packed sprites) with
**JSON metadata**, **batch export**, **engine presets** (Unity, Godot), and **CLI export
automation**.

Phase 7 is the "production pipeline" milestone. Sprite sheet + atlas + engine presets reach
**Aseprite / Pro Motion NG export parity**; the **CLI / batch pipeline** differentiates toward
automation-heavy studio use. Its defining acceptance is **reproducibility**: PNG / GIF /
sprite-sheet exports are **byte-reproducible for a fixed input** — the same document exported twice
yields byte-identical files, across runs *and between the GUI and CLI paths*; the atlas packer
places frames **without overlap** and emits **JSON coordinates that match the packed image**; and
**batch + CLI export run headless and produce output identical to the GUI path**. These are only
achievable if the entire encoding / layout / packing / metadata pipeline is **pure, deterministic,
and Qt-free** — living in `logic/` + `data/` — so that the GUI dialogs and the headless CLI drive
the *same* engine (Article I). This is precisely what makes CLI output equal GUI output byte-for-byte.

This document specifies WHAT the export system must do and WHY, technology-neutral at the
requirement level. The HOW — the **canonical sprite-sheet / atlas JSON schema** (Aseprite-compatible
vs TexturePacker vs both), the **exact engine-preset artifacts** (Unity `.meta` vs JSON; Godot
`SpriteFrames`/`.tres` vs `AtlasTexture`), whether **APNG** is in Phase-7 scope, the **specific
Pillow encoder options** (which must be deterministic), and the **GIF palette-reduction approach**
(reuse `logic/quantize.py` vs Pillow) — are all downstream (AGT-01 plan/ADR grounded by the
Researcher). Export-format requirements are phrased around the **observable contract** — a valid
file a named engine/tool re-imports, byte-reproducible bytes, lossless non-overlapping placement —
**not** a specific schema. This spec records the clarification defaults chosen under the owner's
autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**

- **`logic/export.py` (new, Qt-free).** An **export model** (a chosen format + parameters + source)
  and a **pure, deterministic encoding/layout pipeline**: flatten a frame/document to a single flat
  RGBA image (delegating to `blend.composite_stack`, CO-4, over `PixelBuffer` source pixels, PB-1);
  encode a flat image to **byte-reproducible PNG**; encode the frame sequence (FR-1) + per-frame
  durations to a **byte-reproducible animated GIF**; lay out frames into a **sprite sheet**
  (deterministic grid) and encode it byte-reproducibly; build the **JSON metadata** (frame/sprite
  rects, sheet geometry, durations/tag info) deterministically. The pipeline runs **without any GUI
  / event loop** (this is the CLI==GUI substrate).
- **`logic/atlas.py` (new, Qt-free).** A **texture-atlas layout** that packs frame/sprite rectangles
  into a single atlas image by **delegating to `compactor.compact` (CP-1, MaxRects, rotation off,
  deterministic)** — placements are **non-overlapping** and within the atlas bounds; the emitted
  JSON coordinates **match** where each sprite is blitted; a rectangle that cannot fit surfaces the
  packer's domain error (`CompactionError`). It does **not** re-implement packing.
- **`logic/constants.py` (extend).** New named bounds/defaults: `DEFAULT_SPRITE_SHEET_COLUMNS`,
  `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`
  (Article II). Atlas bounds passed to `compactor.compact` come from named constants (the compactor
  imports none — callers pass them, CP-1).
- **Engine presets (Unity, Godot).** Named presets parameterise the sprite-sheet / atlas layout +
  metadata so the output is an **engine-ready layout** a named engine's importer consumes without
  manual fixup. The layout/metadata computation is Qt-free (`logic/`); the artifact **files** are
  written by `data/` (below).
- **Batch export.** A single operation exports **multiple targets** (frames / tags / documents /
  formats) deterministically; each produced output is **identical** to the equivalent single export.
- **CLI export automation (headless entrypoint, Qt-free).** A CLI entrypoint that imports only
  `logic/` + `data/` (no Qt), reads a fixed `.pixproj` (via IO-3), and exports it to a chosen
  format / preset **headless** — its output **byte-identical** to the GUI export of the same
  document + parameters.
- **`data/` I/O.** Write the encoded bytes + JSON metadata to disk **portably** (`pathlib`,
  `path_portability_check`), writing exactly the deterministic bytes the engine produced; write the
  **engine-preset artifact files** (Unity / Godot); read a fixed `.pixproj` for the CLI path via the
  **defensive `project_io.py` load pattern** (IO-3).
- **`ui/` export dialogs/menus.** Format picker (PNG / GIF / sprite-sheet / atlas), format options
  (GIF loop/frame-source, sheet columns/rows/padding, atlas padding + metadata toggle), engine-preset
  selection (Unity / Godot), a **batch-export** UI, a destination-path chooser (portable), and
  progress/error feedback. Export is **read-only / non-destructive** (no document mutation, no undo
  entry). The GUI invokes the **same** `logic/` + `data/` engine as the CLI.

**Out of scope (this phase):** see §6 Non-goals. Notably: choosing the **canonical sprite-sheet /
atlas JSON schema** (Aseprite-compatible vs TexturePacker vs both) → AGT-01 plan/ADR (Researcher,
DEP-1/DEP-2); the **exact engine-preset artifacts** (Unity `.meta` vs JSON; Godot
`SpriteFrames`/`.tres` vs `AtlasTexture`) → AGT-01 plan/ADR (DEP-2); whether **APNG** is a Phase-7
format → AGT-01 (DEP-2, CL-8); the **specific Pillow encoder options** and the **GIF
palette-reduction approach** → AGT-01 (DEP-2, must be deterministic); whether export runs on a
**worker thread** (UI responsiveness HOW) → AGT-01/AGT-10 (DEP-3); the **CLI entrypoint location /
argument grammar** → AGT-01 (DEP-2). Also out: a **new packing algorithm** (the shipped MaxRects
CP-1 is reused, not replaced); **video / spritesheet-video** export, **normal-map / palette-swap
batch bake**, and a **generic plugin export API** → Phase 8 (CL-13). No plan/tasks/code
(AGT-01/03/05); no new technology (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Artist / export-image).** As an artist, I want to **export my artwork to PNG** so I can
  share or use a single flat image. → REQ-P7-LOGIC-001, -003, REQ-P7-UI-001 · `image-export` · P7
- **US-2 (Animator / export-gif).** As an animator, I want to **export my animation to an animated
  GIF** honouring each frame's duration so it plays correctly anywhere. → REQ-P7-LOGIC-004,
  REQ-P7-UI-002 · `animation-export` · P7
- **US-3 (Game dev / sprite-sheet).** As a game developer, I want to **export my frames to a sprite
  sheet** with a configurable grid so my engine can slice it. → REQ-P7-LOGIC-005, REQ-P7-UI-003
  · `sprite-sheet` · P7
- **US-4 (Game dev / texture-atlas).** As a game developer, I want to **pack my sprites into a
  texture atlas without overlap** so I minimise draw calls / texture count. → REQ-P7-LOGIC-006,
  REQ-P7-UI-004 · `texture-atlas` · P7
- **US-5 (Game dev / metadata).** As a game developer, I want **JSON metadata whose coordinates
  match the packed image exactly** so my importer locates every sprite. → REQ-P7-LOGIC-007, -008,
  REQ-P7-DATA-004, REQ-P7-UI-004 · `export-metadata` · P7
- **US-6 (Any user / reproducible).** As a user (and a CI pipeline), I want **exporting the same
  document twice to yield byte-identical files** so my builds are reproducible. → REQ-P7-LOGIC-002,
  -003, -004, -005 · `byte-reproducible` · P7
- **US-7 (Studio / batch).** As a studio user, I want to **export many targets/formats in one batch**
  so I do not click through the dialog repeatedly, and each output must match its single export. →
  REQ-P7-LOGIC-010, REQ-P7-UI-005 · `batch-export` · P7
- **US-8 (Studio / cli).** As an automation user, I want a **headless CLI that exports a `.pixproj`
  to a format/preset** so my build script produces the same output as the GUI without a display. →
  REQ-P7-LOGIC-013, REQ-P7-DATA-003 · `cli-export` · P7
- **US-9 (Studio / headless-parity).** As a studio user, I want the **CLI/batch output to be
  byte-identical to the GUI output** so scripted and interactive exports never diverge. →
  REQ-P7-LOGIC-009, -013, REQ-P7-UI-007 · `headless-parity` · P7
- **US-10 (Game dev / engine-preset).** As a game developer, I want **Unity and Godot presets** that
  produce an engine-ready layout so the exported assets import cleanly into my engine. →
  REQ-P7-LOGIC-011, REQ-P7-DATA-002, REQ-P7-UI-006 · `engine-preset` · P7
- **US-11 (Any user / safe-input).** As a user running the CLI on a `.pixproj`, I want a **defensive
  validated load** that rejects a malformed file rather than crashing or executing it. →
  REQ-P7-DATA-003 · `safe-input` · P7
- **US-12 (Any user / non-destructive).** As a user, I want **exporting to never change my document**
  and to leave no undo entry. → REQ-P7-UI-009 · `non-destructive` · P7
- **US-13 (Any user / responsive).** As a user exporting a large document or a big batch, I want the
  **UI to stay responsive** with progress and cancel rather than freezing. → REQ-P7-UI-010
  · `export-responsive` · P7
- **US-14 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English user, I
  want the export dialogs, options, and batch UI **keyboard-reachable, correct in both themes, fully
  translatable**. → REQ-P7-UI-011, -012, -013 · `a11y`, `theming`, `i18n` · P7

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `image-export` | Single flat-image PNG export of a composited frame (CO-4). | 7 |
| `animation-export` | Animated GIF export from the frame sequence honouring per-frame durations. | 7 |
| `sprite-sheet` | Deterministic grid layout of frames into one sheet image. | 7 |
| `texture-atlas` | MaxRects-packed (CP-1) non-overlapping atlas of sprites. | 7 |
| `export-metadata` | Deterministic JSON metadata whose coordinates match the packed image. | 7 |
| `byte-reproducible` | Same input → byte-identical output across runs and between GUI/CLI. | 7 |
| `batch-export` | One operation exporting multiple targets/formats; each == its single export. | 7 |
| `cli-export` | Headless, Qt-free CLI entrypoint driving the same export engine. | 7 |
| `headless-parity` | CLI/batch output byte-identical to the GUI path (same pure engine). | 7 |
| `engine-preset` | Unity / Godot presets yielding an engine-ready layout + artifacts. | 7 |
| `safe-input` | Defensive, validated, `eval`-free load of the CLI's `.pixproj` input (IO-3). | 7 |
| `non-destructive` | Export never mutates the document; no undo entry. | 7 |
| `export-responsive` | The GUI stays responsive (progress/cancel) during a large/batch export. | 7 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 7 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-7 capability +
forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a fixed shipped callable is named as a **constraint**, not a HOW decision.

### `logic/export.py` + `logic/atlas.py` — the deterministic, headless export engine (new)

#### REQ-P7-LOGIC-001 — Flatten a frame/document to a single export image (CO-4 / PB-1 reuse)
`traces:` **CO-4** (`blend.composite_stack`, forward-inherited), **PB-1**, S6, S7
Producing the pixels every export encodes is done by **flattening a frame's ordered layer stack**
into a single RGBA image via **`blend.composite_stack` (CO-4)** — honouring each layer's
visibility / opacity / blend mode / groups / masks — over the source `PixelBuffer` pixels (PB-1).
The export engine does **not** re-implement compositing maths (Article I) and **never mutates** the
document's source buffers (non-destructive). The flat image is the input to PNG / GIF / sprite-sheet
/ atlas encoding.

#### REQ-P7-LOGIC-002 — The export pipeline is a pure, deterministic function of its inputs *(reproducibility backbone)*
`traces:` P2 (determinism), S6, Phase-7 capability
Every export stage — flatten, encode, sprite-sheet layout, atlas pack, metadata build — is a
**pure, deterministic function** of `(document/frames, format, parameters)`: it uses **no wall-clock
time, no randomness, no locale-dependent formatting, and no unordered iteration** whose order can
vary. Given identical inputs it produces **identical output bytes** every time. This determinism is
the mechanism behind byte-reproducibility (REQ-P7-LOGIC-003/-004/-005) and CLI==GUI identity
(REQ-P7-LOGIC-009/-013). The shipped MaxRects packer (CP-1) is already deterministic (no
time/random) and is reused unchanged.

#### REQ-P7-LOGIC-003 — PNG export is byte-reproducible
`traces:` P2, Phase-7 capability, S6
Encoding a fixed flat image (REQ-P7-LOGIC-001) to **PNG** yields **byte-identical bytes across
runs** — no embedded timestamp, no volatile ancillary metadata, deterministic encoder options.
Exporting the same document to PNG twice produces two files whose bytes are equal. (The specific
deterministic Pillow options are an AGT-01 plan decision, DEP-2; the WHAT is a valid PNG that is
byte-reproducible.)

#### REQ-P7-LOGIC-004 — Animated GIF export (from frames + durations) is byte-reproducible
`traces:` **FR-1** (`Document → frames`, `Frame.duration_ms`, forward-inherited), P2, Phase-7 capability
Encoding the document's **frame sequence** (FR-1), each flattened via CO-4, into an **animated GIF**
that honours each frame's `duration_ms` yields **byte-identical bytes across runs** for a fixed
input. Frame order, per-frame duration, loop behaviour, and palette reduction are all deterministic.
A single-frame source exports a single-image GIF/PNG. (The GIF palette-reduction approach — reuse
`logic/quantize.py` vs Pillow — and the specific encoder options are AGT-01 plan decisions, DEP-2;
they must be deterministic; whether **APNG** is also offered is deferred, CL-8/DEP-2.)

#### REQ-P7-LOGIC-005 — Sprite-sheet layout is deterministic and byte-reproducible
`traces:` **FR-1**, P2, Phase-7 capability
Laying out the frame sequence (FR-1) into a **sprite sheet** is a **deterministic function** of
`(frame set, frame size, layout parameters — columns/rows/padding)`: frames are placed **row-major**
in a fixed grid, yielding a single flat sheet image encoded byte-reproducibly (REQ-P7-LOGIC-003
applies to the sheet image). Identical inputs always yield the identical sheet and the identical
bytes. Layout defaults come from `logic/constants.py` (`DEFAULT_SPRITE_SHEET_COLUMNS`,
`DEFAULT_ATLAS_PADDING`, REQ-P7-LOGIC-012).

#### REQ-P7-LOGIC-006 — Texture-atlas packing places sprites without overlap (CP-1 reuse)
`traces:` **CP-1** (`compactor.compact` MaxRects, forward-inherited, F8), Phase-7 capability, P2
Packing sprite/frame rectangles into a **texture atlas** is done by **delegating to
`compactor.compact(rects, max_width, max_height)` (CP-1)** — the shipped deterministic MaxRects
(BSSF, **rotation disabled**) packer. The returned `Placement`s are **non-overlapping** and lie
within the atlas bounds; each sprite is blitted at exactly its placement. Atlas bounds come from
named constants (`MAX_ATLAS_DIMENSION`; CP-1 imports none — the caller passes them). A rectangle
that cannot fit surfaces the packer's `CompactionError` as a domain error (never a silent overlap or
truncation, Article VII). The atlas layout does **not** re-implement packing (Article I).

#### REQ-P7-LOGIC-007 — Atlas / sprite-sheet JSON coordinates match the packed image
`traces:` **CP-1**, Phase-7 capability, P2
The emitted JSON **coordinates** (per-sprite frame rect: `x`, `y`, `w`, `h`, plus source size) are
**exactly** the placements used to blit each sprite into the atlas/sheet image — the metadata is a
faithful description of the pixels. For every sprite, the pixels at its JSON rect in the exported
image equal that sprite's source pixels (allowing declared padding). Reading the JSON and cropping
the image at each rect **locates every sprite exactly** (round-trip identity between coordinates and
pixels).

#### REQ-P7-LOGIC-008 — JSON metadata is deterministic and complete *(schema-neutral)*
`traces:` **IO-3** (`project_io.py` pattern, forward-inherited), P2, Phase-7 capability
The sprite-sheet / atlas **JSON metadata** — every frame/sprite rect, source size, sheet/atlas
dimensions, and per-frame duration / tag information where applicable — is produced
**deterministically** (stable key ordering, locale-independent number formatting) so it is
**byte-reproducible** (REQ-P7-LOGIC-002), and it **describes every exported frame/sprite** (no
sprite missing). The **canonical schema** (Aseprite-compatible vs TexturePacker vs both) is an
AGT-01 plan/ADR decision (DEP-2); this spec fixes only that the metadata is a **valid, deterministic,
self-consistent document** that a named tool/engine re-imports (REQ-P7-DATA-004).

#### REQ-P7-LOGIC-009 — The export engine is fully headless / Qt-free (CLI==GUI substrate)
`traces:` Article I, S11, Phase-7 capability
The **entire** export pipeline — flatten (CO-4), encode (PNG/GIF/sheet), atlas pack (CP-1), metadata
build, and file/JSON serialisation — lives in `logic/` + `data/` with **zero Qt imports** and is
**drivable without any GUI or event loop**. Because the GUI dialogs and the CLI entrypoint both call
this same pure engine, their outputs are byte-identical (REQ-P7-LOGIC-013, REQ-P7-UI-007). Enforced
by `check_layering` / `check_cycles`; the only Qt outside `ui/` remains `ui/commands.py` (and export
adds none, since export is not an undoable command).

#### REQ-P7-LOGIC-010 — Batch export is deterministic; each output equals its single export
`traces:` Phase-7 capability (batch), P2, S6
A **batch export** exports **multiple targets** (frames / tags / documents / formats) in one
operation. Batch is an **ordered iteration over the same pure per-target export** (no shared mutable
state that reorders output): each produced file is **byte-identical** to the file that the single,
one-at-a-time export of that same target + parameters would produce. Batch size is bounded by
`MAX_BATCH_TARGETS` (REQ-P7-LOGIC-012); a per-target failure is reported without corrupting the other
targets' outputs.

#### REQ-P7-LOGIC-011 — Engine presets (Unity, Godot) yield engine-ready layouts
`traces:` Phase-7 capability (engine presets), F8 landscape, S6
Named **engine presets** — at minimum **Unity** and **Godot** — parameterise the export
(sprite-sheet / atlas layout + the metadata/artifact set) so the output is an **engine-ready
layout**: a named engine's importer consumes the exported image + artifacts as sprites / animations
**without manual fixup**. The layout + metadata computation is pure `logic/` (Qt-free); the artifact
**files** are written by `data/` (REQ-P7-DATA-002). The **exact artifact set** (Unity `.meta` vs
JSON; Godot `SpriteFrames`/`.tres` vs `AtlasTexture`) is an AGT-01 plan/ADR decision (DEP-2); this
spec fixes only the observable **engine-ready re-import** contract.

#### REQ-P7-LOGIC-012 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The export engine enforces named bounds/defaults defined once in `logic/constants.py`:
`DEFAULT_SPRITE_SHEET_COLUMNS` (default sheet grid width, CL-5), `DEFAULT_ATLAS_PADDING` (inter-sprite
padding, CL-15), `MAX_ATLAS_DIMENSION` (atlas bound passed to `compactor.compact`, CP-1),
`MAX_BATCH_TARGETS` (batch bound, CL-10), `MAX_EXPORT_FRAMES` (frames per sheet/GIF). Exceeding a
bound raises a domain error rather than degrading silently. No numeric literals in
`logic/`/`data/`/`ui/` (Article II). The compactor imports **no** constants — the atlas caller passes
`max_width`/`max_height` from these named constants explicitly (CP-1 contract).

#### REQ-P7-LOGIC-013 — CLI export automation: headless entrypoint, CLI==GUI byte-identity
`traces:` **IO-3**, **DOC-1**, Phase-7 capability (CLI), P2, S11
A **headless CLI export entrypoint** — imports only `logic/` + `data/` (zero Qt) — reads a fixed
`.pixproj` (via the defensive load, IO-3 / REQ-P7-DATA-003), and exports it to a chosen format /
engine preset **without a GUI or display**. For a fixed `.pixproj` + parameters, the CLI's output is
**byte-identical** to the GUI export of the same document + parameters (both drive the pure engine,
REQ-P7-LOGIC-009). The CLI **entrypoint location and argument grammar** are an AGT-01 plan decision
(DEP-2); the WHAT is a headless, Qt-free driver producing GUI-identical bytes.

### `ui/` — export dialogs, options, batch UI, engine presets

#### REQ-P7-UI-001 — Export dialog: format, options, destination
`traces:` REQ-P7-LOGIC-001, -003
An export dialog/menu lets the user choose a **format** (PNG / GIF / sprite-sheet / atlas), set the
format's options, and pick a **destination path** (portable, Article VII §2). Triggering export
invokes the `logic/` + `data/` engine (REQ-P7-LOGIC-009) and writes the file(s).

#### REQ-P7-UI-002 — GIF / animation export options
`traces:` REQ-P7-LOGIC-004
For GIF/animation export the UI exposes the **frame source** (whole document or a selected tag) and
loop behaviour; the export honours each frame's `duration_ms` (REQ-P7-LOGIC-004). Translatable
labels.

#### REQ-P7-UI-003 — Sprite-sheet export options
`traces:` REQ-P7-LOGIC-005
For sprite-sheet export the UI exposes the **grid layout** (columns / rows) and **padding**,
defaulting to the `DEFAULT_SPRITE_SHEET_COLUMNS` / `DEFAULT_ATLAS_PADDING` constants; out-of-range
values are rejected (REQ-P7-LOGIC-012).

#### REQ-P7-UI-004 — Atlas export options + JSON metadata
`traces:` REQ-P7-LOGIC-006, -007, REQ-P7-DATA-004
For texture-atlas export the UI exposes **padding** and the atlas **max dimension**, and a **JSON
metadata** toggle/path; the packed atlas is non-overlapping (REQ-P7-LOGIC-006) and the JSON
coordinates match the packed image (REQ-P7-LOGIC-007). An atlas that cannot fit surfaces a
user-facing error (REQ-P7-UI-008).

#### REQ-P7-UI-005 — Batch export UI
`traces:` REQ-P7-LOGIC-010
The UI lets the user **select multiple targets and/or formats** and export them in **one action**
(REQ-P7-LOGIC-010); progress is shown per target and a per-target failure is reported without
aborting the others.

#### REQ-P7-UI-006 — Engine-preset selection
`traces:` REQ-P7-LOGIC-011, REQ-P7-DATA-002
The export UI offers **engine presets** — at least **Unity** and **Godot** — that select the
engine-ready layout + artifact set (REQ-P7-LOGIC-011 / REQ-P7-DATA-002). Translatable labels.

#### REQ-P7-UI-007 — GUI export is byte-identical to the CLI export (headless parity)
`traces:` REQ-P7-LOGIC-009, -013, P2
The GUI export path invokes the **same** `logic/` + `data/` engine as the CLI (REQ-P7-LOGIC-009);
exporting a fixed document + parameters via the GUI yields bytes **identical** to the CLI export of
the same input (REQ-P7-LOGIC-013). The GUI adds **no** encoding/layout logic of its own.

#### REQ-P7-UI-008 — Export errors surface gracefully
`traces:` Article VII, REQ-P7-LOGIC-006
A failing export — an atlas whose sprites cannot fit (`CompactionError`), an unwritable path, or a
malformed CLI input reflected into the GUI — surfaces a **user-facing error message**, not a crash
or a silently-truncated file. No partial/corrupt file is left as if it were a valid export.

#### REQ-P7-UI-009 — Export is non-destructive; no undo entry
`traces:` S7, C1, CL-12
Exporting **never mutates** the document (source buffers, frames, layers, tags are unchanged) and
pushes **no `QUndoCommand`** — export is a read-only IO operation, not an editing command. Running
an export then undoing has no export-related effect.

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P7-UI-010 — UI responsiveness during large / batch export *(NFR, Article VI)*
`traces:` S1, S12, Article VI, DEP-3
Exporting a large (up to 8K, 7680 × 4320) document or a big batch keeps the **GUI responsive** — it
continues to process events (progress updates, cancel) and does **not** freeze for the duration of
the export. Whether the export runs on a **worker thread** vs the GUI thread is a HOW decision
(AGT-01/AGT-10, DEP-3); this spec fixes only the observable **stays-responsive + progress + cancel**
contract. **NB:** export is a batch IO operation, **not** the per-frame render loop — the 16 ms
`FRAME_BUDGET_MS` (Article VI §, the 8K canvas render budget) does **not** apply to export
throughput; the requirement is responsiveness, not a per-frame budget.

#### REQ-P7-UI-011 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive export control (format picker, GIF/sheet/atlas option fields, engine-preset
selector, batch-target list, destination-path chooser, export/cancel buttons) exposes an accessible
name and, where non-obvious, an accessible description; is reachable and operable by keyboard
(logical tab order + shortcuts); and shows a visible focus indicator. Verified by AGT-06
(`a11y-audit`).

#### REQ-P7-UI-012 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The export dialogs, option panels, batch UI, and progress/error surfaces render correctly in both
light and dark themes; colours are defined once by role, never hard-coded per widget. Both themes are
test-verified (AGT-06 pytest-qt).

#### REQ-P7-UI-013 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 7 (format names, option labels + units, engine-preset names,
batch labels, progress text, dialog titles, error messages) is wrapped in `tr()` / `translate()`;
none is a bare literal. Hand-built widgets re-set text on `QEvent.LanguageChange`. Verified by
`string_audit_check` (AGT-07); an unwrapped string is a blocking finding.

### `data/` — encoded-output serialisation, engine artifacts, CLI input load

#### REQ-P7-DATA-001 — Portable serialisation of encoded outputs + JSON metadata
`traces:` **IO-3** (`project_io.py` pattern, forward-inherited), Article VII §2, Phase-7 capability
Writing the exported PNG / GIF / sprite-sheet / atlas bytes and the JSON metadata to disk uses
**portable paths** (`pathlib`, verified by `path_portability_check`) and writes **exactly the
deterministic bytes the engine produced** — the file layer performs **no** re-encoding or
transformation that could add nondeterminism (byte-reproducibility is preserved from
`logic/` through the write, REQ-P7-LOGIC-002/-003/-004/-005).

#### REQ-P7-DATA-002 — Engine-preset artifacts are written (Unity / Godot)
`traces:` REQ-P7-LOGIC-011, **IO-3**, Phase-7 capability
For an engine-preset export the `data/` layer writes the engine-ready **artifact file(s)** alongside
the exported image (per the preset), **deterministically** and to **portable paths**. The **exact
artifact set** (Unity `.meta` vs JSON; Godot `SpriteFrames`/`.tres` vs `AtlasTexture`) is an AGT-01
plan/ADR decision (DEP-2); this spec fixes that the written artifacts make the output **engine-ready**
(REQ-P7-LOGIC-011) and are byte-reproducible.

#### REQ-P7-DATA-003 — CLI input load via the defensive IO-3 pattern
`traces:` Article VII, **IO-3**, **DOC-1**
The CLI reads its input `.pixproj` through the **shipped defensive-load pattern** (IO-3): every field
is type- and bounds-checked, a malformed / out-of-bounds / unknown-version document raises
`ProjectIOError` (never silent acceptance, **never `eval`/`exec`**), and paths are portable. The
loaded `Document` (DOC-1) is the **same** in-memory document the GUI's open produces from that file —
the precondition that makes CLI==GUI byte-identity hold (REQ-P7-LOGIC-013).

#### REQ-P7-DATA-004 — Written JSON metadata is a valid, re-importable interchange document
`traces:` REQ-P7-LOGIC-007, -008, **IO-3**, P2
The written sprite-sheet / atlas JSON is a **valid document** that the named target tool/engine
re-imports (observable contract), and reading it back **locates every sprite** in the exported image
(round-trip identity between the JSON coordinates and the atlas/sheet pixels, REQ-P7-LOGIC-007). Any
path that re-reads exported metadata does so defensively (IO-3: validated, no `eval`). The **canonical
schema** is AGT-01/ADR (DEP-2); validity + coordinate/pixel round-trip is fixed here.

## 6. Non-goals (explicit; deferred)

- **Canonical sprite-sheet / atlas JSON schema** (Aseprite-compatible vs TexturePacker vs both) —
  **AGT-01 plan/ADR**, grounded by the Researcher (DEP-1/DEP-2). This spec fixes only the observable
  contract (valid, deterministic, coordinate/pixel round-trip, re-importable by a named tool,
  REQ-P7-LOGIC-007/-008, REQ-P7-DATA-004).
- **Exact engine-preset artifacts** (Unity `.meta` vs JSON; Godot `SpriteFrames`/`.tres` vs
  `AtlasTexture`) — AGT-01 plan/ADR (DEP-2). The WHAT (engine-ready re-import) is fixed
  (REQ-P7-LOGIC-011, REQ-P7-DATA-002).
- **Whether APNG is a Phase-7 format** (in addition to animated GIF) — AGT-01 plan/ADR (DEP-2,
  CL-8). Phase 7's animated-export acceptance is fixed on **GIF**; adding APNG later does not change
  the existing criteria.
- **Specific Pillow encoder options** and the **GIF palette-reduction approach** (reuse
  `logic/quantize.py` vs Pillow) — AGT-01 plan (DEP-2); they must be **deterministic** so
  byte-reproducibility holds (REQ-P7-LOGIC-002/-003/-004).
- **Whether export runs on a worker thread** (UI responsiveness HOW) — AGT-01/AGT-10 (DEP-3); this
  spec fixes only the responsiveness contract (REQ-P7-UI-010).
- **CLI entrypoint location / argument grammar** — AGT-01 plan (DEP-2); the WHAT is a headless,
  Qt-free driver with GUI-identical output (REQ-P7-LOGIC-013).
- **A new packing algorithm** — the shipped **MaxRects `compactor.compact` (CP-1)** is reused, not
  replaced; no re-implementation (REQ-P7-LOGIC-006, Article I).
- **Video / animated-spritesheet-video export, normal-map / palette-swap batch bake, a generic
  plugin export API** → **Phase 8** (Automation & Extensibility, CL-13). Phase 7 ships PNG / GIF /
  sprite-sheet / atlas + JSON + batch + CLI + Unity/Godot presets.
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`,
  `specs/phase-4-layer-canvas/`, `specs/phase-5-animation/`, and the shipped `logic/compactor.py`):
  `PixelBuffer.data`/`.region` (PB-1 — source pixels), `blend.composite_stack` (CO-4 — per-frame
  flatten), `Document → frames` + `Frame.duration_ms` (FR-1 — the sequence for sheet/GIF),
  `compactor.compact` (CP-1 — deterministic MaxRects, rotation off, `CompactionError`), the
  `data/project_io.py` defensive-load pattern (IO-3 — the CLI's input load), the `Document` tree
  (DOC-1 — the export subject). Phase 7 **composes** these; it must not re-implement compositing,
  packing, or the JSON-load security posture (Article I / VII).
- **NEW vs REUSED (explicit):**
  - **NEW:** `logic/export.py` (export model + deterministic PNG/GIF/sprite-sheet encoding & layout +
    metadata build), `logic/atlas.py` (atlas layout over CP-1), new constants
    (`DEFAULT_SPRITE_SHEET_COLUMNS`, `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`,
    `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`), the engine-preset layouts, the batch driver, the
    **headless CLI export entrypoint** (Qt-free), all export UI, and the `data/` output/artifact
    writers.
  - **REUSED (not re-authored):** `PixelBuffer` (PB-1), `blend.composite_stack` (CO-4), the
    `Document → frames` tree + `Frame.duration_ms` (FR-1), `compactor.compact` MaxRects (CP-1), the
    `project_io.py` defensive-load pattern (IO-3), the `Document` tree (DOC-1).
- The GUI holds the active document + chosen export parameters (view state); it calls the pure
  `logic/`+`data/` engine, which is the **same** engine the CLI drives — this identity is the
  foundation of REQ-P7-UI-007 / REQ-P7-LOGIC-013.
- Export is **not** an editing command (no `QUndoCommand`, REQ-P7-UI-009), so — unlike Phases 4/5/6 —
  Phase 7 adds **no** new logic to `ui/commands.py`.

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-1 (Researcher, grounding).** `docs/research-phase7-export.md` grounds deterministic Pillow
  PNG/GIF encoder options, the sprite-sheet/atlas JSON schema landscape (Aseprite JSON vs
  TexturePacker), Unity/Godot import-artifact conventions, and APNG feasibility. **Concurrent —
  being produced in parallel** (per the owner directive) and feeds AGT-01. AGT-01's `sdd-plan` must
  not invent these — it consumes the Researcher's findings. The *observable contracts* and
  export-parity defaults are fixed here regardless (§10).
- **DEP-2 (AGT-01, plan/ADR).** (a) **canonical sprite-sheet / atlas JSON schema** (Aseprite vs
  TexturePacker vs both); (b) **exact engine-preset artifacts** (Unity `.meta` vs JSON; Godot
  `SpriteFrames`/`.tres` vs `AtlasTexture`); (c) whether **APNG** is a Phase-7 format; (d) **specific
  Pillow encoder options** + the **GIF palette-reduction approach** (must be deterministic); (e) the
  **CLI entrypoint location / argument grammar**. Each is a HOW decision; the observable contracts
  (byte-reproducible, coordinate/pixel round-trip, engine-ready re-import, CLI==GUI) are fixed here.
  Final `REQ-P7-DATA-*` count may be refined at plan time; this spec allocates `-001..-004`.
- **DEP-3 (AGT-01 / AGT-10, plan).** Whether the export runs on a **worker thread** (to satisfy the
  UI-responsiveness NFR, REQ-P7-UI-010) is a HOW decision; the pure engine is thread-agnostic
  (Qt-free). This spec fixes only responsiveness + progress + cancel, **not** a per-frame budget
  (export is not the render loop).
- **BF-1 (AGT-01, Article II).** New tuning values (`DEFAULT_SPRITE_SHEET_COLUMNS`,
  `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`) must
  resolve to named constants in `logic/constants.py`; the atlas caller passes `MAX_ATLAS_DIMENSION`
  explicitly to `compactor.compact` (CP-1 imports no constants).
- **BF-2 (AGT-01, plan).** Whether PNG/GIF encoding lives in `logic/export.py` producing in-memory
  bytes with `data/` writing them, or the encoder is split further, is a HOW placement decision — the
  constraint is only that all encoding/packing/serialising is **Qt-free** (`logic/`+`data/`) and
  deterministic (REQ-P7-LOGIC-009, Article I).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/export.py`, `logic/atlas.py`, and the new constants are
  pure Python, zero Qt; the `data/` output/artifact writers + CLI input load are zero Qt; the export
  dialogs/menus live in `ui/`; the **CLI entrypoint imports only `logic/`+`data/`** (no Qt). Export
  adds **no** `ui/commands.py` logic (it is not an undoable command). Enforced by `check_layering` /
  `check_cycles`. This purity is what makes CLI==GUI byte-identity possible (REQ-P7-LOGIC-009).
- **Article II (numerics):** new tuning values go in `logic/constants.py` (BF-1); no literals in
  `ui/`/`logic/`/`data/`. The compactor (CP-1) imports none — atlas bounds are passed explicitly.
- **Article IV (testing):** flatten-reuse (CO-4), pipeline determinism, PNG/GIF/sheet
  byte-reproducibility, atlas non-overlap + coordinate/pixel round-trip, deterministic metadata,
  batch==single, engine-ready presets, and CLI==GUI byte-identity each get a scenario → one pytest /
  Hypothesis test (logic/data, headless) or pytest-qt test (UI), both themes for UI.
- **Article V (UX):** REQ-P7-UI-011/-012/-013 make a11y + both themes + full translatability blocking
  gates for the export UI.
- **Article VI (performance):** REQ-P7-UI-010 binds a **responsiveness** contract for large/batch
  export (progress + cancel, no freeze); the 16 ms per-frame canvas budget does **not** apply to
  export throughput (export is not the render loop).
- **Article VII (security):** atlas/batch/frame bounds, the fit-or-error packer contract, and the
  **defensive validated `.pixproj` load** for the CLI input (REQ-P7-DATA-003) are defensive; no
  `eval`/`exec`; portable paths (`path_portability_check`).
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited primitive
  (PB-1, CO-4, FR-1, CP-1, IO-3, DOC-1); forward matrix in `traceability.md`.
- **Article XI (extensibility):** deferring APNG, video export, batch bake, and a plugin export API
  (Phase 8, CL-8/CL-13) adds capability later without weakening any article.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with sensible
defaults grounded in the ROADMAP "Done means", the shipped code, and mainstream export norms
(**Aseprite** / Pro Motion NG / TexturePacker parity). Each is a **category-1 decision** (A2-D2
Branch B). **No open clarification blocks planning.**

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Which formats in Phase 7? | **PNG, animated GIF, sprite sheet, texture atlas** (+ JSON metadata), plus **batch**, **CLI**, and **Unity/Godot presets** — exactly the ROADMAP Phase-7 bullets. | ROADMAP Phase-7 scope + "Done means". |
| **CL-2** | What does GIF export cover? | **Animated GIF** from the document's **frame sequence** (FR-1) honouring per-frame `duration_ms`; a single-frame source exports a single image. | Phase 5 frames feed GIF (ROADMAP dependency); Aseprite GIF is per-frame-ms. |
| **CL-3** | Byte-reproducibility scope? | **PNG, GIF, sprite-sheet image bytes AND their JSON metadata** are byte-identical for a fixed input **across runs and between GUI and CLI**; the atlas image + coords are likewise reproducible. | ROADMAP "Done means" (byte-reproducible; identical across runs and GUI/CLI). |
| **CL-4** | Atlas packer — new or reused? | **Reuse `compactor.compact` (CP-1)** — MaxRects BSSF, rotation off, deterministic. No new packer. | ROADMAP "reuse `logic/compactor.py` MaxRects"; F8/FIX-13. |
| **CL-5** | Sprite-sheet layout default? | **Deterministic row-major grid**; default columns from `DEFAULT_SPRITE_SHEET_COLUMNS`; columns/rows + padding configurable. | Aseprite/TexturePacker sheet norms; deterministic layout for reproducibility. |
| **CL-6** | Canonical sprite-sheet/atlas **JSON schema** (Aseprite vs TexturePacker vs both)? | **DEFERRED to AGT-01/ADR** (DEP-2). Spec fixes the observable contract: valid, deterministic, coordinate/pixel round-trip, re-importable by a named tool. | Per owner directive — schema is a plan/ADR HOW; acceptance phrased around the contract, so the choice does not change acceptance. |
| **CL-7** | Exact **engine artifacts** (Unity `.meta`/JSON; Godot `SpriteFrames`/`.tres`/`AtlasTexture`)? | **DEFERRED to AGT-01/ADR** (DEP-2). Spec fixes "engine re-imports as engine-ready". | Per owner directive — artifact set is a plan/ADR HOW. |
| **CL-8** | Is **APNG** in Phase-7 scope? | **DEFERRED to AGT-01/ADR** (DEP-2). Animated-export acceptance is fixed on **GIF**; APNG may be added later without changing existing criteria. | Per owner directive; Art. XI extensibility. |
| **CL-9** | Specific **Pillow options** / GIF palette reduction? | **DEFERRED to AGT-01** (DEP-2); must be **deterministic** so byte-reproducibility holds. GIF palette reduction may reuse `logic/quantize.py` or Pillow (plan choice). | HOW; the WHAT (byte-reproducible + valid) is fixed. |
| **CL-10** | Batch export scope? | Export **multiple targets/formats in one operation**; each output **byte-identical** to its single export; bounded by `MAX_BATCH_TARGETS`. | ROADMAP "batch export"; determinism (P2). |
| **CL-11** | CLI export scope? | **Headless entrypoint** exporting a `.pixproj` to a format/preset; output **byte-identical to the GUI**; imports only `logic/`+`data/` (Qt-free). | ROADMAP "CLI export automation" + "batch+CLI headless produce identical output to GUI". |
| **CL-12** | Is export a document mutation / undoable? | **No** — export is a **read-only IO op**: non-destructive, no `QUndoCommand`, no undo entry. | Editor norm; export reads, never edits. |
| **CL-13** | What pixels are exported? | The **composited/flattened** frame via `blend.composite_stack` (CO-4) — honouring layer visibility/opacity/blend/groups/masks; PNG = current composited frame, GIF/sheet = the frame sequence. | Reuses the Phase-4 compositor; exports what the canvas shows. |
| **CL-14** | Cross-OS reproducibility? | Tested acceptance is **same input → same bytes across runs and between GUI/CLI** (per ROADMAP); the deterministic pipeline also supports cross-OS reproducibility but the fixed criterion matches the ROADMAP wording (not overclaimed). | ROADMAP "Done means" wording; avoids overspecifying beyond the stated contract. |
| **CL-15** | Atlas bounds / padding defaults? | From named constants: `MAX_ATLAS_DIMENSION` (passed to `compactor.compact`), `DEFAULT_ATLAS_PADDING`. Fit-or-`CompactionError`. | Art. II; CP-1 requires explicit caller-passed bounds. |
| **CL-16** | Export performance budget? | **No 16 ms per-frame budget** (export is not the render loop). NFR is **UI responsiveness** (progress + cancel, no freeze) for large/batch export; worker-thread choice → AGT-01/AGT-10 (DEP-3). | Art. VI applies to the canvas render loop; export is batch IO. |
| **CL-17** | Sprite-sheet vs atlas distinction? | **Sprite sheet** = uniform row-major grid of same-size frames (animation); **texture atlas** = MaxRects-packed (CP-1) possibly heterogeneous sprites with coordinate JSON. | Aseprite (sheet) vs TexturePacker (atlas) norms. |

**SUSPEND / escalate:** *none.* The scope risks — the **canonical JSON schema**, the **exact engine
artifacts**, **APNG**, and the **specific Pillow / GIF-quantisation options** — are **named HOW
decisions** (DEP-1/DEP-2, grounded by the concurrent Researcher report and owned by AGT-01), and the
owner directive explicitly reserves them for the plan/ADR. Crucially, every export-format requirement
here is phrased around the **observable contract** (byte-reproducible bytes; coordinate/pixel
round-trip; a valid file a named engine/tool re-imports; CLI==GUI byte-identity), so choosing a
schema/artifact/option **does not change any acceptance criterion** — it is a HOW, not an open
functional ambiguity. **No functional ambiguity that changes acceptance criteria remains unresolved.**

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic/data scenarios are for **AGT-04** (pytest + Hypothesis,
headless); UI scenarios are for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`), **each run under
BOTH light and dark themes** (REQ-P7-UI-012, expressed once as a global rule). Scenario ids map to
`traceability.md`; tests are authored later (`pending`).

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the
> scenario is executed and asserted identically under the light theme and the dark theme.*

### Feature: Flatten & deterministic pipeline (REQ-P7-LOGIC-001..002)
```gherkin
Scenario: SC-L001-1 a frame is flattened to one export image via blend.composite_stack (CO-4 reuse)
  Given a frame with a RED bottom layer and a half-alpha BLUE top layer
  When the export engine produces the flat image for that frame
  Then the result equals blend.composite_stack of that frame's layers (compositing not re-implemented)
  And the frame's source buffers are byte-for-byte unchanged (non-destructive)

Scenario: SC-L002-1 the export pipeline is a pure deterministic function of its inputs
  Given a fixed document and fixed export parameters
  When any export stage (flatten / encode / layout / pack / metadata) is run twice
  Then both runs produce identical output bytes
  And the pipeline uses no wall-clock time, randomness, or locale-dependent formatting
```

### Feature: Byte-reproducible PNG / GIF / sprite-sheet (REQ-P7-LOGIC-003..005)
```gherkin
Scenario: SC-L003-1 PNG export is byte-reproducible
  Given a fixed flat image
  When it is exported to PNG twice
  Then the two PNG byte streams are identical (no timestamp / volatile metadata)

Scenario: SC-L004-1 animated GIF export is byte-reproducible and honours per-frame durations
  Given a fixed frame sequence with durations [100, 500, 100]
  When it is exported to an animated GIF twice
  Then the two GIF byte streams are identical
  And the encoded per-frame delays reflect each frame's duration_ms

Scenario: SC-L005-1 sprite-sheet layout is deterministic and byte-reproducible
  Given a fixed frame set, frame size, columns and padding
  When the sprite sheet is laid out and encoded twice
  Then the frames are placed row-major in the grid and the two sheet byte streams are identical
```

### Feature: Texture atlas & metadata (REQ-P7-LOGIC-006..008)
```gherkin
Scenario: SC-L006-1 the atlas packs sprites without overlap via the MaxRects packer (CP-1 reuse)
  Given a set of sprite rectangles that fit within MAX_ATLAS_DIMENSION
  When the atlas is packed via compactor.compact
  Then every placement is non-overlapping and within bounds (packing not re-implemented)
  And a sprite set that cannot fit raises a CompactionError domain error (no silent overlap/truncation)

Scenario: SC-L007-1 atlas / sprite-sheet JSON coordinates match the packed image
  Given a packed atlas and its JSON metadata
  When each sprite's JSON rect is cropped from the exported image
  Then the cropped pixels equal that sprite's source pixels for every sprite (coordinate/pixel round-trip)

Scenario: SC-L008-1 JSON metadata is deterministic and complete
  Given a fixed sprite set
  When the metadata is built twice
  Then both metadata documents are byte-identical (stable key order, locale-independent numbers)
  And every exported sprite/frame is described (none missing)
```

### Feature: Headless engine, batch, presets, CLI (REQ-P7-LOGIC-009..013)
```gherkin
Scenario: SC-L009-1 the export engine is Qt-free and runs without a GUI/event loop
  Given the logic/ and data/ export modules
  Then they import no Qt (check_layering passes) and a full export runs with no GUI or event loop

Scenario: SC-L010-1 each batch output equals its single export
  Given a batch of several targets and formats (within MAX_BATCH_TARGETS)
  When the batch is exported and each target is also exported singly
  Then every batch output file is byte-identical to its single-export counterpart
  And a per-target failure is reported without corrupting the other outputs

Scenario: SC-L011-1 an engine preset yields an engine-ready layout
  Given the Unity preset and, separately, the Godot preset
  When a document is exported under each preset
  Then the output image + artifacts form a layout the named engine's importer consumes without manual fixup

Scenario: SC-L012-1 export bounds/defaults come from constants and are enforced
  Given a batch above MAX_BATCH_TARGETS, or an atlas above MAX_ATLAS_DIMENSION, or a sheet above MAX_EXPORT_FRAMES
  Then a domain error is raised
  And default sheet columns / atlas padding equal DEFAULT_SPRITE_SHEET_COLUMNS / DEFAULT_ATLAS_PADDING

Scenario: SC-L013-1 the CLI export of a fixed .pixproj equals the GUI export byte-for-byte
  Given a fixed .pixproj and fixed export parameters
  When it is exported via the headless CLI and via the GUI path
  Then the two output files are byte-identical (both drive the same pure engine)
```

### Feature: Export UI — dialogs, options, batch, presets (REQ-P7-UI-001..009)
```gherkin
Scenario: SC-UI-001-1 the export dialog chooses a format, options and destination
  Given the export dialog
  When the user picks PNG, sets options and a destination path
  Then the export writes the file via the logic/data engine to the chosen (portable) path

Scenario: SC-UI-002-1 GIF export options set the frame source and loop; durations are honoured
  Given the GIF export options
  When the user selects the frame source (document or a tag) and loop behaviour
  Then the exported GIF plays those frames honouring each frame's duration_ms

Scenario: SC-UI-003-1 sprite-sheet options set columns/rows and padding
  Given the sprite-sheet export options
  When the user sets columns/rows and padding
  Then the sheet uses that grid, defaults come from constants, and out-of-range values are rejected

Scenario: SC-UI-004-1 atlas options set padding + max dimension and toggle JSON metadata
  Given the atlas export options
  When the user sets padding, max dimension and enables JSON metadata
  Then the packed atlas is non-overlapping and the JSON coordinates match the packed image

Scenario: SC-UI-005-1 the batch UI exports multiple targets in one action
  Given several selected targets/formats
  When the user triggers a single batch export
  Then all targets are exported with per-target progress and a per-target failure does not abort the others

Scenario: SC-UI-006-1 an engine preset is selectable and drives the export
  Given the export UI
  When the user selects the Unity preset (then the Godot preset)
  Then the export produces that engine's ready layout + artifacts

Scenario: SC-UI-007-1 the GUI export is byte-identical to the CLI export
  Given a fixed document and parameters
  When the same export is run via the GUI and via the CLI
  Then the two output files are byte-identical and the GUI adds no encoding/layout logic of its own

Scenario: SC-UI-008-1 a failing export surfaces a user-facing error, not a crash
  Given an atlas whose sprites cannot fit (or an unwritable path)
  When the user triggers the export
  Then a user-facing error is shown and no partial/corrupt file is left as a valid export

Scenario: SC-UI-009-1 export is non-destructive and pushes no undo command
  Given a document
  When the user exports it
  Then the document (buffers/frames/layers/tags) is unchanged and no QUndoCommand is pushed
```

### Feature: Performance, a11y, theming, i18n (REQ-P7-UI-010..013) — NFR
```gherkin
Scenario: SC-UI-010-1 the UI stays responsive during a large / batch export
  Given a large (up to 8K) document or a big batch
  When the user triggers the export
  Then the UI keeps processing events (progress updates, cancel) and does not freeze
  # Worker-thread vs GUI-thread is AGT-01/AGT-10 (DEP-3); the 16 ms canvas frame budget does not apply to export throughput.

Scenario: SC-UI-011-1 export controls expose accessible names and keyboard focus
  Given the export dialogs and batch UI
  When each control (format picker, option fields, preset selector, batch list, path chooser, export/cancel) is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-012-1 the export UI renders correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the export dialogs, option panels, batch UI and progress/error surfaces render legibly with role-based colours

Scenario: SC-UI-013-1 no Phase-7 user-visible string is a bare literal
  Given the Phase-7 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (format names, option labels/units, preset names, batch labels, progress text, errors)
```

### Feature: Output serialisation, engine artifacts, CLI input (REQ-P7-DATA-001..004)
```gherkin
Scenario: SC-D001-1 encoded bytes + JSON are written portably and unchanged
  Given the engine's deterministic output bytes and JSON metadata
  When they are written to disk
  Then the files contain exactly those bytes (no re-encoding), paths are portable (path_portability_check)

Scenario: SC-D002-1 engine-preset artifacts are written deterministically and portably
  Given an engine-preset export (Unity, then Godot)
  When the export is written
  Then the engine-ready artifact file(s) are written alongside the image, deterministically, to portable paths

Scenario: SC-D003-1 the CLI input load is defensive; malformed input errors, valid input matches the GUI
  Given a valid .pixproj and, separately, a malformed / out-of-bounds / unknown-version one
  When the CLI loads each
  Then the malformed file raises ProjectIOError (no eval/exec, no silent acceptance)
  And the valid file yields the same in-memory Document the GUI open produces

Scenario: SC-D004-1 the written JSON is valid and re-importable; coordinates round-trip against the image
  Given an exported atlas/sheet image and its written JSON metadata
  When the JSON is read back and each rect is located in the image
  Then the JSON is a valid document a named tool re-imports and every sprite is located exactly
```

---

## 12. Exit / status

- Forward spec authored for Phase 7 — Export & Pipeline Integration. **30 REQ-IDs**: **13 LOGIC**
  (`REQ-P7-LOGIC-001..013`) + **13 UI** (`REQ-P7-UI-001..013`) + **4 DATA**
  (`REQ-P7-DATA-001..004`), each traced to an S-id / F-finding / forward-inherited primitive
  (PB-1 source pixels; CO-4 `blend.composite_stack` → per-frame flatten; FR-1 `Document → frames` +
  `Frame.duration_ms` → sheet/GIF source; CP-1 `compactor.compact` MaxRects → non-overlapping atlas;
  IO-3 `project_io.py` defensive-load → CLI input; DOC-1 `Document` tree → export subject) per
  Article X.
- **17 clarification defaults** recorded (§10), each grounded in the ROADMAP "Done means", the
  shipped code, and export parity (Aseprite / TexturePacker / Pro Motion NG); **no open clarification
  blocks planning**.
- **No SUSPEND blocker.** The scope risks — the **canonical JSON schema**, the **exact engine
  artifacts**, **APNG**, and the **specific Pillow / GIF-quantisation options** — are named HOW
  decisions the owner directive reserves for AGT-01 plan/ADR (DEP-1/DEP-2); every export-format REQ
  is phrased around the observable contract (byte-reproducible; coordinate/pixel round-trip;
  engine-ready re-import; CLI==GUI byte-identity), so those choices do not change any acceptance
  criterion.
- **NEW vs REUSED (§7):** NEW = `logic/export.py`, `logic/atlas.py`, new constants, engine-preset
  layouts, the batch driver, the headless Qt-free CLI entrypoint, all export UI, and the `data/`
  output/artifact writers. REUSED = `PixelBuffer` (PB-1), `blend.composite_stack` (CO-4),
  `Document → frames` + `Frame.duration_ms` (FR-1), `compactor.compact` MaxRects (CP-1), the
  `project_io.py` defensive-load pattern (IO-3), the `Document` tree (DOC-1). Export is **not** an
  undoable command — Phase 7 adds no `ui/commands.py` logic.
- **New constants flagged for `logic/constants.py`** (Article II, BF-1): `DEFAULT_SPRITE_SHEET_COLUMNS`,
  `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`. The atlas
  caller passes `MAX_ATLAS_DIMENSION` explicitly to `compactor.compact` (CP-1 imports none).
- **Dependencies flagged:** DEP-1 (Researcher `docs/research-phase7-export.md` — Pillow options, JSON
  schema landscape, Unity/Godot artifacts, APNG feasibility; concurrent/being produced in parallel),
  DEP-2 (AGT-01 plan/ADR — JSON schema, engine artifacts, APNG scope, Pillow/GIF options, CLI
  grammar), DEP-3 (AGT-01/AGT-10 — worker-thread choice for REQ-P7-UI-010).
- Acceptance scenarios cover every functional and NFR requirement; forward matrix in
  `traceability.md` (0 uncovered). Tests authored later by AGT-04 (logic/data) / AGT-06 (UI),
  `pending`.
- **STATUS: COMPLETED.**
