# Specification — Phase 2: Advanced Drawing System

| Field | Value |
| --- | --- |
| Feature | `phase-2-advanced-drawing` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — defines the WHAT/WHY for Phase 2 before any Phase-2 code exists |
| REQ-ID range | `REQ-P2-LOGIC-001..015`, `REQ-P2-UI-001..015` |
| Layer scope | `pixelart_creator/logic/` (new: `selection.py`, `transform.py`, `symmetry.py`, `rotsprite.py`, `pixel_perfect.py`, `tiled.py`) + `pixelart_creator/ui/` (new tool controllers, overlays, actions) |
| Binds to (upstream) | `specs/phase-1-core-engine/spec.md` (shipped `logic/`+`data/`) and `specs/phase-1-ui-canvas/spec.md` (canvas view/scene, `ui/commands.py`, tool-controller pattern) |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) → `sdd-tasks` |

---

## 1. Purpose (WHY)

Phase 1 delivered the pixel-perfect storage core (buffer, document tree, drawing
primitives, reversible history, `.pixproj` I/O) and its first interactive surface
(canvas, five tools, undo/redo, palette panel, i18n). Phase 2 turns that editor into a
**full pixel-art editing environment** — the capability set an artist expects from
Aseprite / Pro Motion NG / Pixelorama: interactive shape tools, selections
(rectangle / lasso / magic-wand) that constrain every edit, buffer/selection transforms
(flip, rotate-90, scale-NN), clean arbitrary-angle rotation (RotSprite), live symmetry
drawing, a pixel-perfect stroke mode, tiled (seamless-pattern) drawing, and grid /
anti-aliasing refinements.

This document specifies **WHAT** each capability must do and **WHY**, technology-neutral
at the requirement level. The HOW (QGraphicsScene overlay strategy, preview-item classes,
the RotSprite algorithm internals) belongs to `sdd-plan`/AGT-01, AGT-10 (render), and
AGT-03 (logic implementation). RotSprite's algorithm is being grounded by **The
Researcher** (see §7 Dependencies); this spec fixes RotSprite's **WHAT and acceptance
contract** (clean rotation, zero new colours) and does not prescribe its internals.

Every Phase-2 mutating operation is a **reversible command** wrapped as a single
`QUndoCommand` via `ui/commands.py` over `logic/history.py` (Article I / S7 pattern); the
domain logic stays Qt-free (Article I / S11).

## 2. Scope

**In scope (WHAT) — logic (`logic/`, Qt-free):**
- `logic/selection.py` — a boolean **selection mask** model over buffer dimensions;
  rectangle, lasso (freehand polygon, even-odd fill), and magic-wand (contiguous colour +
  tolerance) constructors; selection ops (move, clear, invert, deselect, add/subtract);
  and **mask-constrained** application of drawing/edit operations.
- `logic/transform.py` — flip horizontal/vertical, rotate 90° CW/CCW, scale
  nearest-neighbour; each applicable to a whole buffer **or** a masked/region selection,
  returning a new/rewritten buffer with a reversible diff.
- `logic/symmetry.py` — a symmetry-axis model (vertical / horizontal / both / diagonal)
  that, given a source coordinate, yields the set of mirrored coordinates a stroke must
  also paint (live mirrored drawing).
- `logic/pixel_perfect.py` — the corner-removal rule that thins a freehand stroke's
  coordinate sequence to a clean 1-px line (removes the "elbow" pixel of an L-triple).
- `logic/rotsprite.py` — clean arbitrary-angle rotation (upscale → NN rotate → downscale →
  detail restore) that **introduces no colours absent from the source**.
- `logic/tiled.py` — the tiled-drawing wrap model: edits wrap modulo the tile dimensions
  (torus topology); the repeating-preview tiling is derived from it.

**In scope (WHAT) — UI (`ui/`):**
- Shape tool controllers (rectangle, ellipse) with **live preview drag** and a
  **filled / outline** mode, committing on mouse-release as one undoable command.
- Selection tool controllers (rectangle / lasso / magic-wand), a selection overlay
  ("marching-ants" mask outline), move interaction, and selection-op actions (invert,
  clear, deselect).
- Transform actions (flip / rotate-90 / scale) and a RotSprite arbitrary-angle action,
  each applied to the buffer or the active selection as one undoable command.
- Symmetry-mode UI (axis selector, live mirrored strokes), pixel-perfect stroke toggle,
  tiled-drawing mode UI (3×3 repeating preview), grid-overlay/snapping refinements, and a
  **forced anti-aliasing-OFF** toggle guaranteeing pixels never smooth.

**Out of scope (this phase):** the colour hub / Favourites / RGB harmony wheel (Phase 3,
needs F9); blend modes / layer groups / masks (Phase 4); animation timeline (Phase 5);
export/atlas (Phase 7). No new technology choices (stack fixed by S8). No plan / tasks /
code (AGT-01 / AGT-03 / AGT-05). The RotSprite **algorithm internals** are grounded by
The Researcher, not authored here.

## 3. Story map & feature-label taxonomy

Backbone activities (big verbs) → stories, each tagged with a kebab-case feature label and
roadmap phase. This extends the Phase-1 taxonomy (`paint-interaction`, `tool-controllers`,
`palette-panel`, `canvas-navigation`, `canvas-render`, `undo-redo`).

### 3.1 User stories

- **US-1 (Artist / draw-shapes).** As an artist, I want to **drag out a rectangle or
  ellipse with a live preview** and release to commit, choosing filled or outline, so I
  can place exact shapes. → REQ-P2-UI-001..003 · `shape-tools` · P2
- **US-2 (Artist / select-region).** As an artist, I want to **select a region** by
  rectangle, freehand lasso, or magic-wand (contiguous colour) so I can work on just that
  area. → REQ-P2-LOGIC-001..004, REQ-P2-UI-004..006 · `selection` · P2
- **US-3 (Artist / edit-selection).** As an artist, I want to **move, invert, clear, or
  deselect** a selection, and have every edit **constrained to the selected pixels**, so I
  can manipulate isolated regions. → REQ-P2-LOGIC-005, -006, REQ-P2-UI-007, -008 ·
  `selection-ops` · P2
- **US-4 (Artist / transform).** As an artist, I want to **flip, rotate 90°, and scale
  (nearest-neighbour)** the canvas or a selection so I can reorient and resize art without
  blur. → REQ-P2-LOGIC-007..010, REQ-P2-UI-009 · `transforms` · P2
- **US-5 (Artist / clean-rotate).** As an artist, I want an **arbitrary-angle rotation
  (RotSprite)** that stays crisp and **introduces no new colours** so rotated sprites keep
  their palette. → REQ-P2-LOGIC-013, REQ-P2-UI-010 · `rotsprite` · P2
- **US-6 (Artist / symmetry).** As an artist, I want **live mirror-symmetry drawing**
  (vertical / horizontal / both / diagonal) so symmetric art draws itself. →
  REQ-P2-LOGIC-011, REQ-P2-UI-011 · `symmetry` · P2
- **US-7 (Artist / clean-lines).** As an artist, I want a **pixel-perfect stroke mode**
  that removes elbow pixels so freehand lines are clean 1-px paths. →
  REQ-P2-LOGIC-012, REQ-P2-UI-012 · `pixel-perfect` · P2
- **US-8 (Artist / tiles).** As an artist, I want a **tiled drawing mode** whose edits wrap
  seamlessly and whose preview shows the repeating tile so I can author seamless patterns.
  → REQ-P2-LOGIC-014, REQ-P2-UI-015 · `tiled-drawing` · P2
- **US-9 (Artist / precision).** As an artist, I want **grid overlay + snapping
  refinements** and a **guaranteed anti-aliasing-off** view so pixels stay crisp at every
  zoom. → REQ-P2-UI-013, -014 · `canvas-aids` · P2
- **US-10 (Artist / reversibility).** As an artist, I want **every** shape, selection move,
  transform, RotSprite, and tiled edit to be **one undoable step**. →
  REQ-P2-LOGIC-015 (all mutating REQs) · `undo-redo` · P2 (extends P1)

### 3.2 Feature-label taxonomy (Phase 2 additions)

`shape-tools` · `selection` · `selection-ops` · `transforms` · `rotsprite` · `symmetry` ·
`pixel-perfect` · `tiled-drawing` · `canvas-aids` — all `P2`, all aligned to the ROADMAP
Phase-2 bullets and extensible to Phases 3–4 without renaming.

## 4. Functional requirements

Each REQ carries `traces:` to the dossier S-id(s) it realises (or notes it is a Phase-2
capability). Layer, owner agent, and acceptance scenarios are in `traceability.md`.

### 4.1 Logic layer (`REQ-P2-LOGIC-*`)

#### REQ-P2-LOGIC-001 — Selection mask model
`traces:` S2 (painting scoped to pixels), S1 (per-pixel editable grid); Phase-2 capability
A `SelectionMask` represents a boolean region over a buffer's `(width, height)`: a NumPy
`bool` array (or equivalent), origin top-left `(x,y)`, matching a buffer's dimensions. It
exposes `is_selected(x, y)`, `is_empty`, `bounds()` (the tight bounding box of selected
pixels, or `None` when empty), `contains`/count of selected pixels, `copy()`, and value
equality. An **empty** mask means "nothing selected"; a caller treats *no active mask* as
"whole buffer" (see CL-5). Zero Qt. Invalid dimensions raise `SelectionError`
(subclasses `ValueError`, matching the Phase-1 domain-error convention).

#### REQ-P2-LOGIC-002 — Rectangle selection
`traces:` S2, S5 (rectangular region on the canvas); Phase-2 capability
A constructor builds a `SelectionMask` from a rectangle given by two opposite corners
(swapped corners normalised, per `drawing.rectangle`), clipped to buffer bounds. A
zero/negative rectangle produces an empty mask.

#### REQ-P2-LOGIC-003 — Lasso (freehand polygon) selection
`traces:` S2; Phase-2 capability
A constructor builds a `SelectionMask` from an ordered list of polygon vertices (the
freehand path), **auto-closed** from the last vertex to the first, filled by the even-odd
(scanline) rule (CL-3). Points are clipped to bounds; a degenerate path (< 3 distinct
points) yields at most the traced pixels. Deterministic (P2).

#### REQ-P2-LOGIC-004 — Magic-wand (contiguous colour) selection
`traces:` S2 (colour-matched region); reuses S7/S2 tolerance metric; Phase-2 capability
A constructor selects the **contiguous** region of pixels matching a seed pixel within a
colour `tolerance`, reusing the Phase-1 scanline-contiguity + `color.distance_sq`
semantics of `drawing.flood_fill` (RGBA tolerance via squared distance; **exact** match on
INDEXED, tolerance ignored — CL-16). Default tolerance is `MAGIC_WAND_DEFAULT_TOLERANCE`
(CL-1). Contiguous by default (CL-2). An out-of-bounds seed yields an empty mask.

#### REQ-P2-LOGIC-005 — Selection operations (move / clear / invert / deselect / combine)
`traces:` S2; Phase-2 capability
Mask algebra and region ops: `invert()` (complement within buffer bounds), `clear()`/
`deselect()` (→ empty mask), `translate(dx, dy)` (shift the mask, clipping off-buffer
selection), and combine modes `add` / `subtract` / `replace` (CL-4). **Moving selected
pixels** is a floating op: the selected pixels are lifted (leaving the vacated area filled
with transparent / index 0 — CL-6) and re-stamped at the offset; committing produces a
reversible pixel diff. Bad offsets/args raise `SelectionError`.

#### REQ-P2-LOGIC-006 — Mask-constrained edit application
`traces:` S2 (edits scoped to the selection); Phase-2 capability
A helper applies a drawing/edit result to a buffer **only** at coordinates inside the
active mask: pixels outside the mask are never written. With no active mask the operation
covers the whole buffer (CL-5). It returns the coordinates actually changed so the caller
builds a reversible record. Determinism preserved (P2).

#### REQ-P2-LOGIC-007 — Flip horizontal / vertical
`traces:` S2; Phase-2 capability
`flip_horizontal` / `flip_vertical` mirror a buffer (or a masked/region sub-buffer) about
its centre axis. Reversible (applying twice = identity — see NFR). No new colours are
introduced (a pure permutation of existing pixels). Deterministic.

#### REQ-P2-LOGIC-008 — Rotate 90° CW / CCW
`traces:` S2; Phase-2 capability
`rotate_90_cw` / `rotate_90_ccw` rotate a buffer (or floating selection region) by 90°.
For a non-square subject the width/height **swap** (CL-8). Four CW rotations = identity;
CW then CCW = identity. Pure pixel permutation → no new colours. Deterministic.

#### REQ-P2-LOGIC-009 — Scale nearest-neighbour
`traces:` S2, S1 (resize the pixel grid); Phase-2 capability
`scale_nearest` resamples a buffer (or selection region) to a new size using
**nearest-neighbour only** — no interpolation, so **no colour absent from the source is
ever produced** (acceptance-critical, R2). Integer and non-integer scale factors are
allowed; target coordinates map back by floor/round to a source pixel. Non-positive target
size raises `TransformError` (subclasses `ValueError`).

#### REQ-P2-LOGIC-010 — Transform target: buffer or selection
`traces:` S2; Phase-2 capability
Each transform (REQ-P2-LOGIC-007..009, and RotSprite -013) applies either to the **whole
buffer** or to the **active selection region** (its bounding-box sub-buffer masked by the
selection). When applied to a selection, only masked pixels are transformed and re-stamped;
unmasked pixels are untouched. The op yields a reversible pixel diff.

#### REQ-P2-LOGIC-011 — Symmetry axis model & mirrored-coordinate generation
`traces:` S2 (mirrored painting), S5 (canvas axes); Phase-2 capability
A `SymmetryAxis` enum — `NONE` / `VERTICAL` / `HORIZONTAL` / `BOTH` / `DIAGONAL` (CL-9,
CL-10; enum flagged for AGT-01 constants placement, §9) — and a `mirror(x, y, axis,
width, height, axis_pos=None)` function returning the **set** of coordinates a stroke must
also paint (the source plus its mirror images), de-duplicated, clipped to bounds. `BOTH`
yields 4-way mirroring; `DIAGONAL` mirrors across the main diagonal. Axis position defaults
to the canvas centre (CL-9). Deterministic; zero Qt.

#### REQ-P2-LOGIC-012 — Pixel-perfect stroke corner-removal
`traces:` S2 (clean 1-px freehand strokes); Phase-2 capability
`pixel_perfect(coords)` takes the ordered coordinate sequence of a freehand stroke and
removes the "elbow" pixel of every L-shaped triple (the middle pixel of three consecutive
pixels forming a right angle), yielding a clean 1-px-thick path (CL-11). Idempotent on an
already-clean line; deterministic; order-preserving for the surviving pixels. Zero Qt.

#### REQ-P2-LOGIC-013 — RotSprite clean arbitrary-angle rotation
`traces:` S2; Phase-2 capability; **algorithm grounded by The Researcher** (see §7)
`rotsprite(buffer, angle_degrees)` rotates a buffer by an arbitrary angle producing a clean
result via upscale → nearest-neighbour rotate → downscale → detail restore, using
`ROTSPRITE_UPSCALE_FACTOR = 8` (CL-12, ROADMAP). **Acceptance-critical (R2): the output
contains no colour that is not present in the source buffer** — the palette is preserved.
0° / 360° returns an equal buffer; fully transparent input stays transparent. Deterministic
for a fixed input+angle. The internal algorithm is specified by the Researcher's finding,
not here — this REQ owns the WHAT and the no-new-colours + determinism acceptance only.

#### REQ-P2-LOGIC-014 — Tiled-drawing wrap model
`traces:` S2, S5 (canvas topology); Phase-2 capability
A tiled model maps any (possibly out-of-range) paint coordinate to `(x mod W, y mod H)` so
edits **wrap** on a torus (CL-14). It exposes the wrap function and a `preview_tiling`
helper that yields the `TILED_PREVIEW_REPEAT`-by-`TILED_PREVIEW_REPEAT` (default 3×3, CL-13)
arrangement of the tile for the repeating preview. Applying a wrapped edit produces a
reversible diff of the actually-changed (wrapped) pixels. Zero Qt.

#### REQ-P2-LOGIC-015 — Reversible-command integration for all Phase-2 edits *(NFR)*
`traces:` S7 (command-pattern undo/redo, C1/F1); Phase-2 capability
Every Phase-2 **mutating** operation — shape commit, selection move, flip, rotate-90,
scale-NN, RotSprite, and tiled edit — is expressible as a Phase-1 reversible command
(`PixelEdit` diff via `history.record_edit`, or a `FunctionCommand` do/undo pair for
whole-buffer replacements), so `ui/commands.py` wraps it as **one** `QUndoCommand`.
Invariant: `apply ∘ undo = identity` for each op. No Qt in the logic path (Article I).

### 4.2 UI layer (`REQ-P2-UI-*`)

#### REQ-P2-UI-001 — Rectangle shape tool controller
`traces:` S2, S5; Phase-2 capability
A tool controller that, on press-drag, shows a **live rectangle preview** following the
cursor and, on release, commits `drawing.rectangle` as **one** `QUndoCommand`. Honours the
filled/outline mode (REQ-P2-UI-003) and the active colour (active swatch, S2). Binds to
logic only — no domain logic in the controller.

#### REQ-P2-UI-002 — Ellipse shape tool controller
`traces:` S2, S5; Phase-2 capability
As REQ-P2-UI-001 but for `drawing.ellipse` (live ellipse preview, commit-on-release, one
`QUndoCommand`, filled/outline, active colour).

#### REQ-P2-UI-003 — Shape filled / outline mode
`traces:` S2; Phase-2 capability
A shared, translatable UI option toggles filled vs outline for the shape tools; the chosen
mode is passed to `drawing.rectangle` / `drawing.ellipse` `filled=` at commit. Default:
outline (CL-17, Aseprite/Pixelorama default).

#### REQ-P2-UI-004 — Rectangle selection tool controller
`traces:` S2, S5; Phase-2 capability
Press-drag to build a rectangle selection (live preview), release to set the active
`SelectionMask` (REQ-P2-LOGIC-002). Supports replace/add/subtract via modifier keys (CL-4).

#### REQ-P2-UI-005 — Lasso selection tool controller
`traces:` S2; Phase-2 capability
Freehand drag traces a polygon path; on release the auto-closed lasso mask
(REQ-P2-LOGIC-003) becomes the active selection. Live path preview during the drag.

#### REQ-P2-UI-006 — Magic-wand selection tool controller
`traces:` S2; Phase-2 capability
Click selects the contiguous colour region (REQ-P2-LOGIC-004) as the active mask, with a
translatable **tolerance** control (default `MAGIC_WAND_DEFAULT_TOLERANCE`).

#### REQ-P2-UI-007 — Selection overlay & move interaction
`traces:` S2, S5; Phase-2 capability
The active selection renders as a visible **mask outline** ("marching ants" or equivalent
high-contrast boundary, correct in both themes). Dragging inside the selection **moves**
it (REQ-P2-LOGIC-005 floating move); committing on release/deselect is **one**
`QUndoCommand`.

#### REQ-P2-UI-008 — Selection operation actions
`traces:` S2; Phase-2 capability
Translatable, keyboard-reachable actions for **invert**, **clear**, **deselect** (and
select-all) wired to `logic/selection.py` ops; destructive ops (clear) are undoable.

#### REQ-P2-UI-009 — Transform actions (flip / rotate-90 / scale)
`traces:` S2; Phase-2 capability
Translatable menu/toolbar actions for flip-H, flip-V, rotate-90-CW, rotate-90-CCW, and a
scale dialog (integer/float factor or target size, nearest-neighbour). Each applies to the
buffer or active selection (REQ-P2-LOGIC-010) as **one** `QUndoCommand`.

#### REQ-P2-UI-010 — RotSprite arbitrary-angle action
`traces:` S2; Phase-2 capability
A translatable action + angle input (with a preview) invokes `logic/rotsprite.py`
(REQ-P2-LOGIC-013) on the buffer or selection, committing as **one** `QUndoCommand`. The UI
surfaces the "no new colours" guarantee only through behaviour (it adds none of its own).

#### REQ-P2-UI-011 — Symmetry-mode UI
`traces:` S2, S5; Phase-2 capability
A translatable axis selector (none / vertical / horizontal / both / diagonal) sets the
active `SymmetryAxis`; while active, freehand/pencil/shape strokes paint their **mirrored
coordinates live** (REQ-P2-LOGIC-011) within the same `QUndoCommand`.

#### REQ-P2-UI-012 — Pixel-perfect stroke toggle
`traces:` S2; Phase-2 capability
A translatable toggle that, when on, routes freehand pencil strokes through
`logic/pixel_perfect.py` (REQ-P2-LOGIC-012) before committing, so the committed stroke is a
clean 1-px path.

#### REQ-P2-UI-013 — Grid overlay & snapping refinements
`traces:` S5 (grid overlay + snapping); Phase-2 capability
Refines the Phase-1 grid overlay + snapping: a translatable toggle for the grid overlay and
for snapping; snapping constrains shape/selection endpoints to grid intersections when on.
Correct in both themes; overlay drawn without mutating pixel data.

#### REQ-P2-UI-014 — Forced anti-aliasing-OFF toggle
`traces:` S1 (nearest-neighbour, no anti-aliasing), S5; Phase-2 capability
A guarantee (surfaced as a toggle defaulting **on/locked**) that the canvas never enables
antialiasing or smooth-pixmap-transform render hints at any zoom (CL-15) — pixels are always
nearest-neighbour, hard-edged. Applies to canvas + all previews (shape, selection, tiled).

#### REQ-P2-UI-015 — Tiled drawing mode UI
`traces:` S2, S5; Phase-2 capability
A translatable tiled-mode toggle: while on, the canvas shows the `TILED_PREVIEW_REPEAT`×
`TILED_PREVIEW_REPEAT` (3×3) repeating tile preview (REQ-P2-LOGIC-014) and edits **wrap**
across tile edges; the committed edit is **one** `QUndoCommand` over the wrapped pixels.

## 5. Non-functional requirements

- **NFR-1 (Purity, S11 / Article I).** All new `logic/` modules import **zero** Qt; only
  `ui/commands.py` and `ui/` touch Qt.
- **NFR-2 (Determinism, P2).** Selection, transform, symmetry, pixel-perfect, RotSprite,
  and tiled logic produce identical output for identical input (test-asserted).
- **NFR-3 (Reversibility).** `apply ∘ undo = identity` for every mutating op
  (REQ-P2-LOGIC-015); each is exactly one `QUndoCommand`.
- **NFR-4 (No new colours, R2).** Scale-NN (REQ-P2-LOGIC-009) and RotSprite
  (REQ-P2-LOGIC-013) introduce **no** colour absent from the source; flip/rotate-90 are
  pure permutations. Test-asserted by comparing output colour set ⊆ input colour set.
- **NFR-5 (Numerics, S12 / Article II).** New constants (§9) live only in
  `logic/constants.py`; no magic numbers at call sites.
- **NFR-6 (Coverage, S13 / Article IV).** ≥90 % line / ≥80 % branch per package; logic via
  pytest + Hypothesis, UI via pytest-qt in **both themes**, headless.
- **NFR-7 (a11y + i18n + both themes, Article V).** Every new user-visible string wrapped
  in `tr()`; new widgets override `changeEvent`; all controls keyboard-reachable with
  visible focus; selection/grid overlays legible in both themes.
- **NFR-8 (Performance, S12 / Article VI).** Live previews, symmetry mirroring, and the
  tiled 3×3 preview hold `FRAME_BUDGET_MS = 16` at 8K; over-budget → an AGT-10 directive,
  never a relaxed budget.

## 6. Non-goals (explicit)

- No colour hub / Favourites / RGB harmony wheel (Phase 3, needs F9).
- No blend modes / layer groups / masks / reference layers (Phase 4).
- No animation timeline / onion-skin (Phase 5); no tilemap/tileset editor (Phase 6 — the
  Phase-2 "tiled drawing" mode is a seamless-pattern paint mode, **not** a tilemap).
- No export / sprite-sheet / atlas pipeline (Phase 7).
- No perceptual colour matching (CIEDE2000) — Phase 3; magic-wand reuses the Phase-1
  `distance_sq` metric.
- No new technology choices (stack fixed by S8); no plan/tasks/code.

## 7. Dependencies

**On Phase 1 (hard):**
- `logic/pixel_buffer.py` — `region()`, `blit()` (overwrite/blend), `copy()`, `resize()`,
  `get_pixel`/`set_pixel`, `fill_rect` — the substrate for selection extraction, transform
  output, and tiled wrap. (REQ-P1-LOGIC-006/-007)
- `logic/drawing.py` — `rectangle`, `ellipse` (shape tools), `line` (previews/pixel-perfect
  reference), scanline contiguity of `flood_fill` + `color.distance_sq` (magic-wand).
  (REQ-P1-LOGIC-008/-004)
- `logic/history.py` — `Command` / `PixelEdit` / `FunctionCommand` / `record_edit`
  reversible-op pattern — every Phase-2 op is built on it. (REQ-P1-LOGIC-009)
- `ui/commands.py` — the QUndoCommand bridge that wraps each logic op as one undo step.
  (phase-1-ui-canvas)
- `ui/canvas_view.py` / `ui/canvas_scene.py` — the canvas surface Phase-2 overlays
  (shape/selection preview, tiled 3×3 preview, grid) render into; the AA-off guarantee
  extends its render-hint policy. (phase-1-ui-canvas, F2/F3)
- `ui/tools/` tool-controller pattern — the Phase-2 shape/selection tools follow it.

**On research (hard for one REQ):**
- **RotSprite research (The Researcher, via orchestrator).** REQ-P2-LOGIC-013 depends on the
  grounded RotSprite algorithm (upscale factor, rotate + downscale + detail-restore steps,
  the no-new-colours guarantee mechanism). This spec fixes the acceptance contract; the
  *internals* must be grounded before `sdd-plan` finalises the algorithm. **Not a blocker
  for this spec** — the WHAT and acceptance are specifiable now.

**Downstream:** AGT-01 (`sdd-plan` consumes this spec); AGT-06 (Gherkin → pytest-qt
acceptance tests); AGT-03/04 (logic + tests); AGT-05 (UI + pytest-qt); AGT-07 (i18n of new
strings); AGT-10 (render/perf of previews + overlays).

## 8. Recommended slicing (for the orchestrator)

Phase 2 is large; it **should be split into two vertical sub-slices** (mirroring the
Phase-1 core-engine → UI split), with an optional early parallel slice for shapes:

- **Slice 2A — Advanced-drawing LOGIC** (`REQ-P2-LOGIC-001..015`). All Qt-free logic:
  `selection.py`, `transform.py`, `symmetry.py`, `pixel_perfect.py`, `rotsprite.py`,
  `tiled.py` + new constants + pytest/Hypothesis coverage. **Ships first** — it is the
  substrate every UI control binds to. RotSprite (REQ-P2-LOGIC-013) is **gated on the
  Researcher's finding**; the rest of 2A does not depend on it and can proceed in parallel.
- **Slice 2B — Advanced-drawing UI** (`REQ-P2-UI-001..015`). Tool controllers, overlays,
  transform/RotSprite actions, symmetry/pixel-perfect/tiled/grid/AA toggles + pytest-qt
  (both themes) + i18n. **Depends on 2A** for every non-shape control.
- **Optional early micro-slice — Shape tools UI** (`REQ-P2-UI-001..003`). These bind
  **only** to already-shipped Phase-1 `drawing.rectangle`/`ellipse`; they need **no** new
  Phase-2 logic and can start immediately, in parallel with 2A. Recommend the orchestrator
  either front-load them into 2B or run them as a standalone early slice to deliver visible
  value fast.

Rationale: keeps each slice within one constitution-gated increment, lets the RotSprite
research land without blocking the rest, and keeps the Qt-free logic testable headlessly
before any UI exists. Final task ordering is AGT-01/orchestrator's call.

## 9. New constants (for AGT-03 — Article II / S12)

New tuning values MUST be added to `logic/constants.py` with a source citation and imported
by name (never inlined). Flagged here for AGT-03; AGT-01 confirms the tuning-vs-intrinsic
and enum-placement classification.

| Constant | Proposed value | Rationale / source | Classification |
| --- | --- | --- | --- |
| `ROTSPRITE_UPSCALE_FACTOR` | `8` | ROADMAP Phase 2 ("8× upscale"); RotSprite research (F-RotSprite) | Tuning (algorithm parameter) → `constants.py` |
| `MAGIC_WAND_DEFAULT_TOLERANCE` | `0` | Parity with `flood_fill` exact default; Aseprite default 0 (CL-1) | Tuning → `constants.py` |
| `TILED_PREVIEW_REPEAT` | `3` | 3×3 seamless-pattern preview (Aseprite tiled mode) (CL-13) | Tuning → `constants.py` |
| `SymmetryAxis` (enum) | `NONE/VERTICAL/HORIZONTAL/BOTH/DIAGONAL` | Symmetry axis set (CL-9/10) | **Enum** — AGT-01 to rule: module-local (`symmetry.py`) vs `constants.py`; enums conventionally live with their module (cf. `ColorMode` in `pixel_buffer.py`) |
| `SCALE_MIN_FACTOR` / `SCALE_MAX_FACTOR` | *(candidate)* e.g. `0.01` / `64.0` | Guard rails for scale-NN target size vs `MAX_CANVAS_*` | Tuning candidate — AGT-01 to confirm need; otherwise clamp to `MAX_CANVAS_WIDTH/HEIGHT` |

Note: none of these duplicate an existing `constants.py` value. `SelectionError` /
`TransformError` are domain exceptions (subclass `ValueError`, per Phase-1 convention), not
numerics.

## 10. Clarifications (resolved defaults, per authoring rule R5)

Ordinary ambiguities are resolved here with sensible defaults grounded in the dossier +
Aseprite / Pro Motion NG / Pixelorama norms, and recorded as category-1 decisions
(A2-D2 Branch B). **No open clarification blocks planning** (see §11).

- **CL-1 — Magic-wand default tolerance?** `MAGIC_WAND_DEFAULT_TOLERANCE = 0` (exact),
  matching `flood_fill`'s default and Aseprite; user-adjustable via the tolerance control,
  reusing `color.distance_sq`.
- **CL-2 — Magic-wand contiguous vs global?** **Contiguous** by default (like `flood_fill`);
  a global (all-matching-pixels) mode is deferred as an optional later refinement, not
  Phase-2 scope.
- **CL-3 — Lasso closure & fill?** The freehand path **auto-closes** (last→first vertex);
  interior filled by the **even-odd (scanline)** rule; boundary pixels included.
- **CL-4 — Selection combine modes?** `replace` (default), `add` (Shift), `subtract`
  (Alt/Ctrl) — standard Aseprite/Pixelorama modifiers.
- **CL-5 — Editing with no active selection?** Treated as "whole buffer selected" — an
  absent/empty mask does **not** block drawing; edits cover the buffer as in Phase 1.
- **CL-6 — Moving a selection: cut or copy?** **Cut** (lift): moving lifts the selected
  pixels, leaving the vacated area filled transparent (RGBA) / index 0 (indexed);
  copy-move (hold modifier) is an optional later refinement. Commit = one undoable command.
- **CL-7 — Scale-NN interpolation?** **Nearest-neighbour only**, never interpolated, so no
  new colours; non-integer factors permitted (coordinates map back by floor/round).
- **CL-8 — Rotate-90 on a non-square subject?** Width/height **swap**; a whole-buffer
  rotate-90 resizes the buffer accordingly; a selection rotate-90 rotates the floating
  region.
- **CL-9 — Symmetry axis position?** Defaults to the **canvas centre**; position is
  adjustable. `DIAGONAL` mirrors across the main (top-left→bottom-right) diagonal.
- **CL-10 — Symmetry "both"?** `BOTH` = horizontal **and** vertical simultaneously (4-way
  mirror). `DIAGONAL` is a distinct axis.
- **CL-11 — Pixel-perfect rule?** Remove the **elbow (middle) pixel** of every L-shaped
  triple in the freehand coordinate sequence → clean 1-px path; applies to freehand pencil
  strokes only (not shape tools). Idempotent on an already-clean line.
- **CL-12 — RotSprite upscale factor?** `ROTSPRITE_UPSCALE_FACTOR = 8` (ROADMAP);
  angle in degrees; **no colour absent from the source may appear** in the output; the
  detailed algorithm is grounded by The Researcher (§7).
- **CL-13 — Tiled preview repeat?** `TILED_PREVIEW_REPEAT = 3` (3×3 grid; the centre tile is
  the editable one, the 8 neighbours are previews).
- **CL-14 — Tiled wrap topology?** **Torus** — painting past an edge wraps to the opposite
  edge (`x mod W`, `y mod H`).
- **CL-15 — Forced AA-off scope?** The canvas and **all** previews never enable
  antialiasing / smooth-pixmap-transform at any zoom; nearest-neighbour always (S1).
- **CL-16 — Magic-wand on INDEXED buffers?** **Exact** index match; tolerance ignored
  (matches `flood_fill` INDEXED semantics).
- **CL-17 — Shape tool default mode?** **Outline** (Aseprite/Pixelorama default); filled is
  the toggled alternative.

No item required SUSPEND: the RotSprite internals are a *plan-time* research dependency, not
a *requirement-time* ambiguity — the acceptance contract (clean rotation, zero new colours,
determinism) is specifiable now (A2-D2 Branch B).

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour, phrased for **headless** testing (logic via pytest,
UI via pytest-qt in **both themes**). Reversibility and "no new colours" acceptance are
called out per R2. Scenario ↔ REQ ↔ (future) test mapping is in `traceability.md`.

### Feature: Selection mask model (REQ-P2-LOGIC-001)
```gherkin
Scenario: SC-L001-1 an empty mask reports empty and no bounds
  Given a SelectionMask sized to a 4x4 buffer with nothing selected
  Then is_empty is True and bounds() is None and no pixel is_selected

Scenario: SC-L001-2 a mask reports its selected pixels and tight bounds
  Given a mask with pixels (1,1) and (2,3) selected
  Then is_selected is True there, False elsewhere, and bounds() is (1,1,2,3)

Scenario: SC-L001-3 copy is equal but independent
  Given a mask, when I copy it and mutate the copy
  Then the original is unchanged and equality distinguishes them

Scenario: SC-L001-4 bad dimensions raise SelectionError
  Given width or height <= 0
  When I build a SelectionMask
  Then SelectionError is raised
```

### Feature: Rectangle selection (REQ-P2-LOGIC-002)
```gherkin
Scenario: SC-L002-1 rectangle selection marks the rectangle only
  Given a rectangle (1,1)-(2,2) on a 4x4 buffer
  Then exactly those 4 pixels are selected

Scenario: SC-L002-2 swapped corners normalise to the same mask
  Given (2,2)-(1,1) and (1,1)-(2,2)
  Then both produce an equal mask

Scenario: SC-L002-3 out-of-bounds rectangle is clipped
  Given a rectangle extending past the buffer
  Then only in-bounds pixels are selected

Scenario: SC-L002-4 a zero/negative rectangle yields an empty mask
```

### Feature: Lasso selection (REQ-P2-LOGIC-003)
```gherkin
Scenario: SC-L003-1 a closed triangle path fills its interior (even-odd)
  Given vertices forming a triangle
  Then interior + boundary pixels are selected and outside pixels are not

Scenario: SC-L003-2 the path auto-closes last-to-first vertex

Scenario: SC-L003-3 a degenerate path (<3 distinct points) selects at most the traced pixels

Scenario: SC-L003-4 lasso is deterministic for identical vertices
```

### Feature: Magic-wand selection (REQ-P2-LOGIC-004)
```gherkin
Scenario: SC-L004-1 wand selects the contiguous same-colour region only
  Given a buffer with a contiguous red block and a separate red block
  When I wand-select a pixel in the first block with tolerance 0
  Then only the first block's pixels are selected

Scenario: SC-L004-2 tolerance includes near colours, excludes far (RGBA)
  Examples: near-match included | far-match excluded

Scenario: SC-L004-3 indexed buffer matches exactly, tolerance ignored (CL-16)

Scenario: SC-L004-4 an out-of-bounds seed yields an empty mask
```

### Feature: Selection operations (REQ-P2-LOGIC-005)
```gherkin
Scenario: SC-L005-1 invert complements the selection within bounds
Scenario: SC-L005-2 clear/deselect yields an empty mask
Scenario: SC-L005-3 translate shifts the mask and clips off-buffer selection
Scenario: SC-L005-4 add/subtract/replace combine two masks correctly
Scenario: SC-L005-5 moving selected pixels lifts them (vacated area transparent) and re-stamps at the offset
Scenario: SC-L005-6 REVERSIBILITY: a selection move, then undo, restores the original buffer exactly
```

### Feature: Mask-constrained editing (REQ-P2-LOGIC-006)
```gherkin
Scenario: SC-L006-1 a fill constrained to a mask writes only masked pixels
  Given an active mask over part of the buffer
  When I apply a fill through the mask-constrained helper
  Then pixels outside the mask are unchanged

Scenario: SC-L006-2 with no active mask the whole buffer is editable (CL-5)

Scenario: SC-L006-3 the helper returns exactly the coordinates it changed
```

### Feature: Flip (REQ-P2-LOGIC-007)
```gherkin
Scenario: SC-L007-1 flip_horizontal mirrors columns; flip_vertical mirrors rows
Scenario: SC-L007-2 NO NEW COLOURS: the output colour set equals the input colour set
Scenario: SC-L007-3 REVERSIBILITY: flipping twice restores the original buffer (apply∘undo = identity)
```

### Feature: Rotate 90° (REQ-P2-LOGIC-008)
```gherkin
Scenario: SC-L008-1 rotate_90_cw on a known 2x3 buffer yields the expected 3x2 result
Scenario: SC-L008-2 non-square buffer swaps width and height (CL-8)
Scenario: SC-L008-3 four CW rotations return an equal buffer; CW then CCW returns an equal buffer
Scenario: SC-L008-4 NO NEW COLOURS: output colour set equals input colour set
```

### Feature: Scale nearest-neighbour (REQ-P2-LOGIC-009)
```gherkin
Scenario: SC-L009-1 scale 2x doubles dimensions; each source pixel maps to a 2x2 block
Scenario: SC-L009-2 NO NEW COLOURS: every output colour is present in the source (R2)
Scenario: SC-L009-3 non-integer factor maps coordinates by floor/round deterministically
Scenario: SC-L009-4 a non-positive target size raises TransformError
Scenario: SC-L009-5 scale down then the reverse mapping stays within the source palette
```

### Feature: Transform target buffer-or-selection (REQ-P2-LOGIC-010)
```gherkin
Scenario: SC-L010-1 a transform on a selection changes only masked pixels; unmasked untouched
Scenario: SC-L010-2 a transform on the whole buffer (no mask) transforms every pixel
Scenario: SC-L010-3 REVERSIBILITY: a selection transform then undo restores the buffer exactly
```

### Feature: Symmetry mirroring (REQ-P2-LOGIC-011)
```gherkin
Scenario: SC-L011-1 VERTICAL mirror of (x,y) yields (W-1-x, y)
Scenario: SC-L011-2 HORIZONTAL mirror yields (x, H-1-y)
Scenario: SC-L011-3 BOTH yields the 4-way set (dedup, in-bounds)
Scenario: SC-L011-4 DIAGONAL mirrors across the main diagonal
Scenario: SC-L011-5 NONE returns only the source coordinate
Scenario: SC-L011-6 mirrored coordinates are clipped to bounds and de-duplicated
```

### Feature: Pixel-perfect stroke (REQ-P2-LOGIC-012)
```gherkin
Scenario: SC-L012-1 an L-shaped triple loses its elbow pixel, leaving a clean path
Scenario: SC-L012-2 an already-clean straight/diagonal line is unchanged (idempotent)
Scenario: SC-L012-3 surviving pixels keep their original order
Scenario: SC-L012-4 pixel_perfect is deterministic for identical input
```

### Feature: RotSprite (REQ-P2-LOGIC-013)
```gherkin
Scenario: SC-L013-1 NO NEW COLOURS: rotating by an arbitrary angle produces only colours present in the source (R2, acceptance-critical)
Scenario: SC-L013-2 rotating by 0 (or 360) returns an equal buffer
Scenario: SC-L013-3 a fully transparent buffer stays fully transparent after rotation
Scenario: SC-L013-4 rotation is deterministic for a fixed buffer and angle
Scenario: SC-L013-5 the upscale factor used is ROTSPRITE_UPSCALE_FACTOR (from constants.py)
```

### Feature: Tiled-drawing wrap (REQ-P2-LOGIC-014)
```gherkin
Scenario: SC-L014-1 a coordinate past the right/bottom edge wraps to (x mod W, y mod H)
Scenario: SC-L014-2 a negative coordinate wraps to the opposite edge
Scenario: SC-L014-3 preview_tiling yields a 3x3 (TILED_PREVIEW_REPEAT) arrangement of the tile
Scenario: SC-L014-4 REVERSIBILITY: a wrapped edit then undo restores the buffer exactly
```

### Feature: Reversible-command integration (REQ-P2-LOGIC-015)
```gherkin
Scenario: SC-L015-1 each Phase-2 mutating op produces a Command whose undo is its exact inverse
  Examples: shape-commit | selection-move | flip | rotate-90 | scale-NN | rotsprite | tiled-edit
Scenario: SC-L015-2 the op path imports zero Qt (verified by check_layering, Article I)
```

### Feature: Rectangle shape tool (REQ-P2-UI-001)
```gherkin
Scenario: SC-U001-1 press-drag shows a live rectangle preview following the cursor (both themes)
Scenario: SC-U001-2 release commits the rectangle as exactly ONE undoable command
Scenario: SC-U001-3 REVERSIBILITY: undo removes the whole rectangle in one step; redo restores it
Scenario: SC-U001-4 the committed rectangle uses the active colour (S2)
```

### Feature: Ellipse shape tool (REQ-P2-UI-002)
```gherkin
Scenario: SC-U002-1 press-drag shows a live ellipse preview (both themes)
Scenario: SC-U002-2 release commits the ellipse as exactly ONE undoable command
Scenario: SC-U002-3 REVERSIBILITY: undo removes the ellipse in one step
```

### Feature: Shape filled/outline mode (REQ-P2-UI-003)
```gherkin
Scenario: SC-U003-1 outline mode commits perimeter only; filled mode commits the interior
Scenario: SC-U003-2 the mode control is tr()-wrapped and keyboard-reachable (a11y, both themes)
```

### Feature: Rectangle selection tool (REQ-P2-UI-004)
```gherkin
Scenario: SC-U004-1 press-drag sets a rectangle selection matching the dragged region
Scenario: SC-U004-2 Shift adds / Alt subtracts from the existing selection (CL-4)
```

### Feature: Lasso selection tool (REQ-P2-UI-005)
```gherkin
Scenario: SC-U005-1 a freehand drag sets an auto-closed lasso selection
Scenario: SC-U005-2 the path preview is visible during the drag (both themes)
```

### Feature: Magic-wand selection tool (REQ-P2-UI-006)
```gherkin
Scenario: SC-U006-1 a click selects the contiguous colour region as the active mask
Scenario: SC-U006-2 the tolerance control (tr()-wrapped) changes the selected extent
```

### Feature: Selection overlay & move (REQ-P2-UI-007)
```gherkin
Scenario: SC-U007-1 the active selection shows a high-contrast outline legible in both themes
Scenario: SC-U007-2 dragging inside the selection moves it; release commits ONE undoable command
Scenario: SC-U007-3 REVERSIBILITY: undo restores the pre-move pixels exactly
```

### Feature: Selection operation actions (REQ-P2-UI-008)
```gherkin
Scenario: SC-U008-1 invert / clear / deselect / select-all actions are tr()-wrapped and keyboard-reachable
Scenario: SC-U008-2 clear is undoable; deselect empties the active mask
```

### Feature: Transform actions (REQ-P2-UI-009)
```gherkin
Scenario: SC-U009-1 flip-H/V and rotate-90-CW/CCW actions transform the buffer or selection as one undoable command
Scenario: SC-U009-2 the scale dialog applies nearest-neighbour scaling (no new colours) as one undoable command
Scenario: SC-U009-3 actions are tr()-wrapped, keyboard-reachable, correct in both themes
```

### Feature: RotSprite action (REQ-P2-UI-010)
```gherkin
Scenario: SC-U010-1 entering an angle and confirming rotates the buffer/selection via rotsprite as ONE undoable command
Scenario: SC-U010-2 NO NEW COLOURS: the committed result contains only source colours (R2)
Scenario: SC-U010-3 the angle input + action are tr()-wrapped and keyboard-reachable
```

### Feature: Symmetry-mode UI (REQ-P2-UI-011)
```gherkin
Scenario: SC-U011-1 selecting an axis makes freehand strokes paint their mirror(s) live within one command
Scenario: SC-U011-2 the axis selector is tr()-wrapped, keyboard-reachable, correct in both themes
Scenario: SC-U011-3 REVERSIBILITY: undo removes the whole mirrored stroke in one step
```

### Feature: Pixel-perfect toggle (REQ-P2-UI-012)
```gherkin
Scenario: SC-U012-1 with pixel-perfect on, a freehand stroke commits a clean 1px path (no elbow pixels)
Scenario: SC-U012-2 the toggle is tr()-wrapped and keyboard-reachable
```

### Feature: Grid overlay & snapping (REQ-P2-UI-013)
```gherkin
Scenario: SC-U013-1 the grid-overlay toggle shows/hides the grid without mutating pixel data
Scenario: SC-U013-2 with snapping on, a shape/selection endpoint snaps to a grid intersection
Scenario: SC-U013-3 the overlay is legible in both themes; toggles are tr()-wrapped
```

### Feature: Forced AA-off (REQ-P2-UI-014)
```gherkin
Scenario: SC-U014-1 the canvas never enables antialiasing/smooth-pixmap-transform at any zoom (render hints off)
Scenario: SC-U014-2 shape/selection/tiled previews render nearest-neighbour, hard-edged
```

### Feature: Tiled drawing mode (REQ-P2-UI-015)
```gherkin
Scenario: SC-U015-1 enabling tiled mode shows a 3x3 (TILED_PREVIEW_REPEAT) repeating preview
Scenario: SC-U015-2 painting near an edge wraps to the opposite edge; the preview updates seamlessly
Scenario: SC-U015-3 REVERSIBILITY: a wrapped edit is one undoable command
Scenario: SC-U015-4 the tiled-mode toggle is tr()-wrapped and keyboard-reachable
```

---

## 12. Exit / status

- Forward pre-implementation spec authored for ROADMAP Phase 2.
- 30 REQ-IDs (15 LOGIC + 15 UI); 17 clarification defaults recorded (§10); 5 new-constant
  entries flagged for AGT-03 (§9); reversibility + no-new-colours acceptance included (R2).
- All ordinary ambiguities resolved with grounded defaults; RotSprite internals are a
  plan-time research dependency (§7), not a requirement blocker.
- Recommended slicing: **2A logic → 2B UI** (+ optional early shape-tools micro-slice) — §8.
- No SUSPEND blocker.
- **STATUS: COMPLETED.**
