# PixelArt Creator — Product Roadmap

A unified pixel-art platform (drawing + animation + tiles + pipeline + automation
+ cloud collaboration), positioned against Aseprite, Pro Motion NG, and
Pixelorama. This roadmap sequences the twelve product phases from
`Specifications.txt` into incrementally shippable increments, each gated by the
project constitution (lint/type, 3-layer architecture, ≥90 % line / ≥80 % branch
coverage, a11y + i18n + both themes, 8K @ 60 fps, validated I/O).

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

---

## Phase 1 — Core Engine (foundation)
**Goal:** pixel-perfect storage + stable architecture + undo/redo.

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

UI (next increment, pytest-qt):
- [ ] `ui/canvas_scene.py` / `ui/canvas_view.py` — QGraphicsScene tile
  `drawBackground` + QGraphicsView zoom/pan (infinite), nearest-neighbour, no AA
  (F2/F3, S1 tile culling).
- [ ] `ui/commands.py` — QUndoCommand bridge delegating to `logic/history.py`.
- [ ] `ui/tools/` — pencil/eraser/fill/line/picker tool controllers.
- [ ] `ui/main_window.py` — toolbars, palette panel, document tabs.
- [ ] `ui/i18n.py` — LanguageManager, `changeEvent`/`tr()` (F5/F6).

## Phase 2 — Advanced Drawing System
**Goal:** full pixel-art editing capability.
- [ ] Shape tools (rect/ellipse already in logic — add UI + preview drag).
- [ ] Selection: rectangle, lasso, magic wand (`logic/selection.py` mask model).
- [ ] Transforms: flip, rotate 90°, scale NN (`logic/transform.py`).
- [ ] Symmetry drawing (mirror axes), pixel-perfect stroke mode.
- [ ] Grid overlay + snapping; forced AA-off toggle.
- [ ] **RotSprite** clean rotation (8× upscale → NN rotate+downscale → detail
  restore, no new colours) — `logic/rotsprite.py`.
- [ ] Tiled drawing mode (infinite pattern preview).

## Phase 3 — Color & Palette System (critical)
**Goal:** professional palette workflows.
- [ ] Palette editor UI (drag/drop reorder — logic reorder exists).
- [ ] Indexed mode workflows; colour cycling; palette swap.
- [ ] Shade ramps; dithering brushes (`logic/dither.py`).
- [ ] Palette constraints (NES/Game Boy simulation).
- [ ] Auto palette extraction from images (median-cut / k-means).
- [ ] Palette analytics (usage stats); perceptual matching (CIEDE2000 on the
  `distance_sq` baseline).

## Phase 4 — Layer & Canvas System
**Goal:** non-destructive editing (tree already supports layers/frames).
- [ ] Blend modes (`logic/blend.py`), opacity/visibility/lock UI.
- [ ] Layer groups; mask layers; reference (non-editable) layers; smart layers.
- [ ] Multiple canvases (tabs / artboards).

## Phase 5 — Animation System (full)
**Goal:** production animation (frames already in the document tree).
- [ ] Timeline (frames × layers) UI; onion skinning; frame tags/groups.
- [ ] Playback modes (loop / ping-pong / reverse); per-frame duration UI.
- [ ] Multi-animation per file; motion preview window.

## Phase 6 — Tilemap & Level Design
**Goal:** game-dev pipeline support.
- [ ] Tileset editor + tilemap canvas (`logic/tileset.py`, `logic/tilemap.py`).
- [ ] Tile instance linking; stamping tools; auto-tiling rules.
- [ ] Multi-layer + infinite maps; export to Tiled/JSON.

## Phase 7 — Export & Pipeline Integration
**Goal:** production pipeline compatibility.
- [ ] Export PNG, GIF (Pillow), sprite sheets, texture atlas (reuse
  `logic/compactor.py` MaxRects), JSON metadata; batch export.
- [ ] Engine presets (Unity, Godot); CLI export automation.

## Phase 8 — Automation & Extensibility
**Goal:** power-user workflows.
- [ ] Scripting engine (sandboxed) + CLI; macro recording.
- [ ] Plugin system (marketplace-ready); batch recolour; procedural generation.

## Phase 9 — Visual Aids & UX
**Goal:** high usability.
- [ ] Real-size preview window; guides & rulers; isometric grids; perspective.
- [ ] Reference board (PureRef-style); multi-view editing; timelapse recording.

## Phase 10 — Cloud & Collaboration
**Goal:** modern team workflows.
- [ ] Cloud save/load, version history, autosave/recovery (`.pixproj` in cloud).
- [ ] Provider adapters (Drive/OneDrive/Dropbox) behind a `data/cloud/` port.
- [ ] Shared projects; comments; presence; conflict resolution; art branching;
  real-time (CRDT/OT) as an advanced tier.

## Phase 11 — Team & Asset Management
**Goal:** studio-level workflows.
- [ ] Asset library; tagging; search/filter; version control.
- [ ] Dependency tracking (sprite → animation → tileset); cross-project reuse.

## Phase 12 — Performance & Scalability
**Goal:** handle large projects (8K).
- [ ] Chunked canvas rendering; GPU acceleration; lazy frame/layer loading;
  memory compression; verified by `scripts/perf_profile.py` vs FRAME_BUDGET_MS.

---

### Delivery cadence
Each phase ships in vertical slices: **REQ (AGT-02 / sdd-specify+clarify) →
placement & plan (AGT-01 / sdd-plan+tasks) → logic+tests (AGT-03/04) → UI+QA
(AGT-05/06) → i18n (AGT-07) → docs (AGT-08) → analyze+checklist gate → commit
(AGT-09)**. A slice is "done" only when every constitution gate is green.
