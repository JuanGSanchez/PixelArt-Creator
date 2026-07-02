# PixelArt Creator — Product Roadmap

A unified pixel-art platform (drawing + animation + tiles + pipeline + automation
+ cloud collaboration), positioned against Aseprite, Pro Motion NG, and
Pixelorama. This roadmap sequences the twelve product phases — frozen in the
design dossier (`docs/dossier-design-pixelart-creator.md` §1, the source of
truth for requirements and architecture) — into incrementally shippable
increments, each gated by the project constitution (`constitution.md`: lint/type,
3-layer architecture, ≥90 % line / ≥80 % branch coverage, a11y + i18n + both
themes, 8K @ 60 fps, validated I/O).

**Build scope.** The near-term build targets **Phases 1–4** (core engine,
advanced drawing, colour/palette incl. the 8K hub, layers); the agent/skill
roster is explicitly extensible to Phases 5–12, which this roadmap documents in
full as reserved scope.

## Foundational engineering rules (every phase)

- **Architecture (S11).** Three layers: `ui/` (PySide6), `logic/` (pure Python,
  zero Qt), `data/` (I/O, zero Qt). Only Qt file outside `ui/` is
  `ui/commands.py`. Enforced by `check_layering` + `check_cycles`.
- **Numerics (S12).** All tuning values live in `logic/constants.py`.
- **Testing (S13).** pytest + pytest-qt + pytest-cov + Hypothesis, headless
  (`QT_QPA_PLATFORM=offscreen`). One test per acceptance criterion; a regression
  test per fix; coverage gate enforced in CI per package.
- **Harness layer.** Native Claude Code hooks (`harness-guard` layer-guard,
  file-lock, protected paths; post-write Black/isort, layering, string-audit,
  path-portability) plus the SDD gates (`sdd-analyze` blocks implement until
  spec/plan/tasks are consistent; `sdd-checklist` before ship).
- **Commits.** Conventional Commits with REQ-IDs, modular per feature slice;
  each commit leaves the gate green.
- **Suitable assets per task.** logic/data → AGT-03 + AGT-04; UI → AGT-05 +
  AGT-06; placement → AGT-01; requirements → AGT-02; i18n → AGT-07; docs →
  AGT-08; CI/commits → AGT-09; rendering/perf → AGT-10; research → Researcher;
  bulk reads → Gleaner.

## Status legend
`[x]` shipped & gated · `[~]` in progress · `[ ]` planned

## REQ-ID allocation
Requirement IDs follow the constitution scheme `REQ-P<phase>-<LAYER>-<NNN>`,
`<LAYER>` ∈ {`UI`, `LOGIC`, `DATA`} (`constitution.md` Art. X). Phase 1 IDs are
concrete (specified & shipping); Phases 2–12 reserve the prefixes below — detailed
REQs are authored per feature in `specs/<feature>/` at specify time, not here.

| Phase | Reserved REQ-ID prefixes |
| --- | --- |
| 1 | `REQ-P1-LOGIC-001..013`, `REQ-P1-DATA-001`, `REQ-P1-UI-001..026` (concrete) |
| 2 | `REQ-P2-LOGIC-*`, `REQ-P2-UI-*` |
| 3 | `REQ-P3-LOGIC-*`, `REQ-P3-UI-*` |
| 4 | `REQ-P4-LOGIC-*`, `REQ-P4-UI-*` |
| 5 | `REQ-P5-LOGIC-*`, `REQ-P5-UI-*` |
| 6 | `REQ-P6-LOGIC-*`, `REQ-P6-DATA-*`, `REQ-P6-UI-*` |
| 7 | `REQ-P7-LOGIC-*`, `REQ-P7-DATA-*`, `REQ-P7-UI-*` |
| 8 | `REQ-P8-LOGIC-*`, `REQ-P8-UI-*` |
| 9 | `REQ-P9-LOGIC-*`, `REQ-P9-UI-*` |
| 10 | `REQ-P10-DATA-*`, `REQ-P10-LOGIC-*`, `REQ-P10-UI-*` |
| 11 | `REQ-P11-DATA-*`, `REQ-P11-UI-*` |
| 12 | `REQ-P12-LOGIC-*`, `REQ-P12-DATA-*`, `REQ-P12-UI-*` |

---

## Phase 1 — Core Engine (foundation)
**Goal:** pixel-perfect storage + stable architecture + undo/redo.
**REQ-IDs:** `REQ-P1-LOGIC-001..013`, `REQ-P1-DATA-001`, `REQ-P1-UI-001..026`.
**Status:** core engine **shipped & gated** (SDD-legalised — `constitution.md` +
`specs/phase-1-core-engine/`, commit `43fc9aa`, CI green, coverage logic
98.5 %/98.0 % + data 100 %); UI increment **in progress** (spec authored:
`specs/phase-1-ui-canvas/`, 26 REQ / 44 acceptance scenarios).

Logic/data (headless, shipped this increment):
- [x] `logic/color.py` — RGBA type, hex, alpha compositing, distance metric.
- [x] `logic/palette.py` — indexed palette (add/reorder/nearest), 256-cap.
- [x] `logic/pixel_buffer.py` — RGBA + indexed NumPy buffer; get/set, fill,
  fill_rect, region, blit (overwrite/blend), non-destructive resize, copy/eq.
- [x] `logic/drawing.py` — pencil/eraser, Bresenham line, rectangle, midpoint
  ellipse, scanline flood-fill (RGBA tolerance + indexed), colour picker.
- [x] `logic/history.py` — reversible command pattern, bounded undo/redo,
  `record_edit` capturing drawing ops as diffs.
- [x] `logic/document.py` — Document → frames → layers → buffer tree; layer &
  frame ops; non-destructive canvas resize.
- [x] `data/project_io.py` — `.pixproj` JSON (+zlib/base64 pixels), defensive
  validated load.

UI (in-progress increment, spec authored, pytest-qt):
- [~] `ui/canvas_scene.py` / `ui/canvas_view.py` — QGraphicsScene tile
  `drawBackground` + QGraphicsView zoom/pan (infinite), nearest-neighbour, no AA
  (F2/F3, tile culling).
- [~] `ui/commands.py` — QUndoCommand bridge delegating to `logic/history.py`.
- [~] `ui/tools/` — pencil/eraser/fill/line/picker tool controllers.
- [~] `ui/main_window.py` — toolbars, palette panel, document tabs.
- [~] `ui/i18n.py` — LanguageManager, `changeEvent`/`tr()` (F5/F6).

**Done means:** logic/data packages pass the coverage gate and ship behind
`constitution.md` (achieved); the 8K canvas renders + accepts left-click paint /
right-click menu with undo/redo, each of the 26 UI REQ-IDs traced to a passing
pytest-qt test in both themes; `.pixproj` round-trips a document losslessly.
**Parity:** matches the pixel-perfect editing core of Aseprite / Pixelorama
(RGBA + indexed buffer, undo history, project file); differentiates on an 8K
single-hub canvas larger than either tool's default working surface.
**Depends on:** none (foundation). Enables every later phase — the buffer,
document frame/layer tree, colour/palette, and history are the substrate they
build on.

## Phase 2 — Advanced Drawing System
**Goal:** full pixel-art editing capability.
**REQ-IDs:** `REQ-P2-LOGIC-*`, `REQ-P2-UI-*` (reserved).
- [ ] Shape tools (rect/ellipse already in logic — add UI + preview drag).
- [ ] Selection: rectangle, lasso, magic wand (`logic/selection.py` mask model).
- [ ] Transforms: flip, rotate 90°, scale NN (`logic/transform.py`).
- [ ] Symmetry drawing (mirror axes), pixel-perfect stroke mode.
- [ ] Grid overlay + snapping; forced AA-off toggle.
- [ ] **RotSprite** clean rotation (8× upscale → NN rotate+downscale → detail
  restore, no new colours) — `logic/rotsprite.py`.
- [ ] Tiled drawing mode (infinite pattern preview).

**Done means:** a selection mask can be made (rect/lasso/wand), moved, and
committed reversibly; flip/rotate-90/scale-NN each pass a logic round-trip test;
RotSprite rotation introduces zero new colours; symmetry + pixel-perfect strokes
produce deterministic output. **Parity:** brings the selection, transform, and
symmetry toolset to Aseprite/Pro Motion NG level; RotSprite matches Pro Motion
NG / Aseprite clean-rotation (a differentiator over base Pixelorama).
**Depends on:** Phase 1 `pixel_buffer` (region/blit), `drawing` primitives, and
`history` (every new op is a reversible command).

## Phase 3 — Color & Palette System (critical)
**Goal:** professional palette workflows.
**REQ-IDs:** `REQ-P3-LOGIC-*`, `REQ-P3-UI-*` (reserved).
- [ ] Palette editor UI (drag/drop reorder — logic reorder exists).
- [ ] Right-click colour hub: Favourites list + Canva-style RGB colour wheel
  with live colour-theory harmonies (the 8K-hub interaction).
- [ ] Indexed mode workflows; colour cycling; palette swap.
- [ ] Shade ramps; dithering brushes (`logic/dither.py`).
- [ ] Palette constraints (NES/Game Boy simulation).
- [ ] Auto palette extraction from images (median-cut / k-means).
- [ ] Palette analytics (usage stats); perceptual matching (CIEDE2000 on the
  `distance_sq` baseline).

**Done means:** the right-click colour hub opens at the cursor and offers
persisted Favourites + a colour wheel whose harmonies (complementary/analogous/
triadic/split-complementary + shade/tint ramps) are computed by tested logic;
palette extraction yields ≤256 colours from an image; NES/Game Boy constraint
sets are enforceable; a picked colour applies immediately to the active swatch.
**Parity:** the harmony-driven colour wheel differentiates against Aseprite /
Pro Motion NG / Pixelorama (none ship a Canva-style live-theory picker); palette
extraction + indexed workflows reach parity with all three. **Depends on:**
Phase 1 `color`/`palette` (distance metric, indexed model); the harmony wheel
requires the grounded colour-theory research (F9) before the widget is built.

## Phase 4 — Layer & Canvas System
**Goal:** non-destructive editing (tree already supports layers/frames).
**REQ-IDs:** `REQ-P4-LOGIC-*`, `REQ-P4-UI-*` (reserved).
- [ ] Blend modes (`logic/blend.py`), opacity/visibility/lock UI.
- [ ] Layer groups; mask layers; reference (non-editable) layers; smart layers.
- [ ] Multiple canvases (tabs / artboards).

**Done means:** each blend mode composites deterministically over a known
base (logic test per mode); opacity/visibility/lock toggles round-trip through
the document tree and `.pixproj`; layer groups and masks nest and flatten
correctly; multiple canvases open as tabs without cross-contaminating state.
**Parity:** blend modes + groups + masks reach Aseprite/Pixelorama layer-model
parity; reference & smart layers differentiate toward Pro Motion NG. **Depends
on:** Phase 1 `document` layer/frame tree + `color.blend_over` / `pixel_buffer`
blit (the blend-mode maths extend the compositing primitive).

## Phase 5 — Animation System (full)
**Goal:** production animation (frames already in the document tree).
**REQ-IDs:** `REQ-P5-LOGIC-*`, `REQ-P5-UI-*` (reserved).
- [ ] Timeline (frames × layers) UI; onion skinning; frame tags/groups.
- [ ] Playback modes (loop / ping-pong / reverse); per-frame duration UI.
- [ ] Multi-animation per file; motion preview window.

**Done means:** the timeline reflects the frame × layer grid; playback honours
loop/ping-pong/reverse and per-frame duration; onion-skin renders N prior/next
frames; frame tags define independent named animations that round-trip in
`.pixproj`. **Parity:** timeline + tags + onion skinning match Aseprite; Pro
Motion NG-level multi-animation-per-file is the differentiator over Pixelorama.
**Depends on:** Phase 1 `document` frame tree (frames pre-exist the timeline);
Phase 4 layer compositing (a frame renders its layer stack).

## Phase 6 — Tilemap & Level Design
**Goal:** game-dev pipeline support.
**REQ-IDs:** `REQ-P6-LOGIC-*`, `REQ-P6-DATA-*`, `REQ-P6-UI-*` (reserved).
- [ ] Tileset editor + tilemap canvas (`logic/tileset.py`, `logic/tilemap.py`).
- [ ] Tile instance linking; stamping tools; auto-tiling rules.
- [ ] Multi-layer + infinite maps; export to Tiled/JSON.

**Done means:** a tileset slices a source image into indexed tiles; a tilemap
stamps linked instances that update when the source tile edits; auto-tiling
rules resolve edges deterministically; the map exports to valid Tiled-compatible
JSON that re-imports losslessly. **Parity:** tileset + tilemap + auto-tiling
reach Pro Motion NG / Tiled-adjacent parity — a capability Aseprite covers only
partially and Pixelorama minimally (differentiator). **Depends on:** Phase 1
`pixel_buffer` (tiles are buffer regions) + `data/project_io` validation
pattern (Tiled/JSON I/O reuses the defensive-load approach).

## Phase 7 — Export & Pipeline Integration
**Goal:** production pipeline compatibility.
**REQ-IDs:** `REQ-P7-LOGIC-*`, `REQ-P7-DATA-*`, `REQ-P7-UI-*` (reserved).
- [ ] Export PNG, GIF (Pillow), sprite sheets, texture atlas (reuse
  `logic/compactor.py` MaxRects), JSON metadata; batch export.
- [ ] Engine presets (Unity, Godot); CLI export automation.

**Done means:** PNG/GIF/sprite-sheet exports are byte-reproducible for a fixed
input; the atlas packer places frames without overlap and emits matching JSON
coordinates; batch + CLI export run headless and produce identical output to the
GUI path; Unity/Godot presets yield engine-ready layouts. **Parity:** sprite
sheet + atlas + engine presets reach Aseprite/Pro Motion NG export parity; the
CLI/batch pipeline differentiates toward automation-heavy studio use. **Depends
on:** Phase 1 `pixel_buffer` (source pixels) + `logic/compactor.py` MaxRects
(F8, atlas packing); Phase 5 frames feed sprite-sheet/GIF export.

## Phase 8 — Automation & Extensibility
**Goal:** power-user workflows.
**REQ-IDs:** `REQ-P8-LOGIC-*`, `REQ-P8-UI-*` (reserved).
- [ ] Scripting engine (sandboxed) + CLI; macro recording.
- [ ] Plugin system (marketplace-ready); batch recolour; procedural generation.

**Done means:** a recorded macro replays to an identical result; the scripting
API drives editing ops through the same reversible-command path as the UI (no
`eval`/`exec` on untrusted input, per constitution Art. VII); plugins load in an
isolated sandbox and cannot bypass the layer boundaries. **Parity:** a scripting
API + plugin marketplace matches Aseprite's Lua scripting and extends past
Pixelorama/Pro Motion NG (differentiator). **Depends on:** Phase 1 `history`
command pattern (scripts/macros wrap the same reversible ops) + the three-layer
boundary that keeps automation out of the UI layer.

## Phase 9 — Visual Aids & UX
**Goal:** high usability.
**REQ-IDs:** `REQ-P9-LOGIC-*`, `REQ-P9-UI-*` (reserved).
- [ ] Real-size preview window; guides & rulers; isometric grids; perspective.
- [ ] Reference board (PureRef-style); multi-view editing; timelapse recording.

**Done means:** the real-size preview mirrors edits live; guides/rulers and
isometric/perspective grids compute snap points from tested geometry logic;
multiple views of one document stay in sync; timelapse captures a reproducible
frame sequence of the edit session. **Parity:** isometric/perspective grids +
reference board reach Pro Motion NG / PureRef-adjacent parity; the integrated
reference board differentiates over Aseprite/Pixelorama. **Depends on:** Phase 1
canvas/document model + Phase 4 multiple-canvas support (multi-view builds on
tabs/artboards).

## Phase 10 — Cloud & Collaboration
**Goal:** modern team workflows.
**REQ-IDs:** `REQ-P10-DATA-*`, `REQ-P10-LOGIC-*`, `REQ-P10-UI-*` (reserved).
- [ ] Cloud save/load, version history, autosave/recovery (`.pixproj` in cloud).
- [ ] Provider adapters (Drive/OneDrive/Dropbox) behind a `data/cloud/` port.
- [ ] Shared projects; comments; presence; conflict resolution; art branching;
  real-time (CRDT/OT) as an advanced tier.

**Done means:** a `.pixproj` round-trips through the cloud port with version
history and autosave/recovery; provider adapters are swappable behind one
`data/cloud/` interface (no provider leak into `logic/`/`ui/`); concurrent edits
converge deterministically via the conflict-resolution/CRDT layer. **Parity:**
cloud sync + real-time collaboration + branching is a category differentiator —
none of Aseprite / Pro Motion NG / Pixelorama ship it (the Figma-like axis).
**Depends on:** Phase 1 `data/project_io` (`.pixproj` is the sync unit) + its
defensive validation, extended behind a cloud port.

## Phase 11 — Team & Asset Management
**Goal:** studio-level workflows.
**REQ-IDs:** `REQ-P11-DATA-*`, `REQ-P11-UI-*` (reserved).
- [ ] Asset library; tagging; search/filter; version control.
- [ ] Dependency tracking (sprite → animation → tileset); cross-project reuse.

**Done means:** assets are cataloged with tags and retrievable by search/filter;
version control records asset revisions; the dependency graph
(sprite → animation → tileset) is queryable and flags a break when a referenced
asset changes; assets reuse across projects without duplication. **Parity:**
a studio asset library + dependency tracking exceeds all three competitors
(differentiator toward pipeline/DAM tooling). **Depends on:** Phase 6 tileset/
tilemap + Phase 5 animation (the entities tracked) and Phase 10 cloud/version
history (shared storage backbone).

## Phase 12 — Performance & Scalability
**Goal:** handle large projects (8K).
**REQ-IDs:** `REQ-P12-LOGIC-*`, `REQ-P12-DATA-*`, `REQ-P12-UI-*` (reserved).
- [ ] Chunked canvas rendering; GPU acceleration; lazy frame/layer loading;
  memory compression; verified by `scripts/perf_profile.py` vs FRAME_BUDGET_MS.

**Done means:** the 8K grid holds `FPS_TARGET = 60` (≤ `FRAME_BUDGET_MS = 16`)
under `scripts/perf_profile.py` for the profiled scenarios; chunked rendering +
lazy frame/layer loading bound memory growth on large multi-frame documents;
GPU (`QOpenGLWidget`) viewport engages without visual regression; the resident
pixel buffer is never culled (only Qt rendering is). **Parity:** sustained 8K @
60 fps with chunked/GPU rendering exceeds the typical working-resolution ceiling
of Aseprite / Pro Motion NG / Pixelorama (differentiator). **Depends on:** the
AGT-10 render strategy (tile culling / dirty-rect / scene-rect, F2–F4/F7) applied
across Phase 1 canvas and every later rendered surface; hardens the whole roster.

---

### Delivery cadence
Each phase ships in vertical slices: **REQ (AGT-02 / sdd-specify+clarify) →
placement & plan (AGT-01 / sdd-plan+tasks) → logic+tests (AGT-03/04) → UI+QA
(AGT-05/06) → i18n (AGT-07) → docs (AGT-08) → analyze+checklist gate → commit
(AGT-09)**. A slice is "done" only when every constitution gate is green.

The near-term build delivers **Phases 1–4**; the agent/skill roster is
explicitly extensible to **Phases 5–12** (documented above as reserved scope),
which enter the same cadence when promoted into build scope. Reserved REQ-ID
prefixes become concrete IDs only at each phase's `specify` step, per feature,
under `specs/<feature>/`.
