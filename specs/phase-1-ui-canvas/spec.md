# Specification — Phase 1 (UI Increment): Canvas, Tools, Undo/Redo, Shell & i18n

| Field | Value |
| --- | --- |
| Feature | `phase-1-ui-canvas` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no `ui/` code exists yet; this spec defines the WHAT/WHY the UI increment must realise |
| REQ-ID range | `REQ-P1-UI-001..026` |
| Layer scope | `pixelart_creator/ui/` only — `canvas_scene.py`, `canvas_view.py`, `commands.py`, `tools/`, `main_window.py`, `i18n.py` |
| Binds to (upstream) | `specs/phase-1-core-engine/spec.md` — the shipped, Qt-free `logic/` + `data/` API (Document, PixelBuffer, drawing primitives, History/reversible ops, Palette, constants) |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

Phase 1's headless core engine (`logic/` + `data/`) is shipped and tested. This
increment gives that engine its **first interactive surface**: a PySide6 hub where an
artist can see a document, pick a tool and a colour, paint pixels on an 8K-capable
canvas with zoom/pan, and undo/redo every edit — in either light or dark theme, with a
fully translatable UI.

It is the "walking skeleton" of the product UI: the minimum presentation layer that
turns the pure-Python model into a usable editor, while holding the constitution's
gates (three-layer purity, 60 fps / 16 ms at 8K, a11y, i18n, both themes). It binds to
the logic layer only — it introduces **no** domain logic of its own (Article I). The
sole Qt file permitted outside `ui/` is `ui/commands.py` (QUndoCommand wrappers).

This document specifies WHAT the UI must do and WHY, technology-neutral at the
requirement level (the HOW — QGraphicsScene/View internals, viewport class, dirty-rect
strategy — is `sdd-plan`/AGT-01 + AGT-10 territory). It records the clarification
defaults chosen under the owner's autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**
- `ui/canvas_scene.py` — a scene that renders the active document's pixel buffer + a
  tile/grid background inside `drawBackground(painter, rect)` using **only** the exposed
  rect (F2), with `setSceneRect(0,0,W,H)` set once at init for the 8K scene (F3),
  nearest-neighbour, no anti-aliasing.
- `ui/canvas_view.py` — a view providing zoom (incl. deep zoom) + pan across the 8K
  grid, left-click paint of the target pixel(s) with the active colour (S2), an optional
  grid overlay + snapping (S5), and a right-click dispatch **seam** to a menu hook.
- `ui/commands.py` — QUndoCommand subclasses that wrap the logic-layer reversible ops
  (delegating to `logic/history.py`); one QUndoStack owns undo/redo (S7/C1/F1). The only
  Qt-dependent module outside `ui/`.
- `ui/tools/` — five tool controllers (pencil, eraser, flood-fill, line, colour-picker),
  each binding a canvas interaction to a `logic/drawing.py` primitive and pushing a
  QUndoCommand. No domain logic in the controllers.
- `ui/main_window.py` — a `QMainWindow` with a tool toolbar, a palette panel (display the
  indexed Palette, single-select the active colour → active swatch), document tabs
  (multiple open Documents), undo/redo actions, and a menu bar.
- `ui/i18n.py` — a `LanguageManager` that installs a `QTranslator` by `QLocale`; widgets
  wrap user-visible strings in `tr()` and re-set them on `QEvent.LanguageChange` via
  `changeEvent` (F5/F6).

**Out of scope (this increment):** see §6 Non-goals. Notably S3/S4 the right-click colour
hub, Favourites, and the RGB colour wheel + live harmonies (Phase 3, needs F9);
selection/transform/symmetry/RotSprite (Phase 2); blend-mode/layer UI (Phase 4). No new
technology choices (fixed by S8); no plan/tasks/code (AGT-01/AGT-03/AGT-05).

## 3. Story map & user stories

Backbone activities (big verbs) → stories, each tagged with a kebab-case feature label
and roadmap phase. Feature-label taxonomy is in §3.2.

### 3.1 User stories

- **US-1 (Artist / paint).** As an artist, I want to **left-click on the canvas to paint
  the target pixel** with the active colour so I can draw. → REQ-P1-UI-006, -011
  · `paint-interaction` · P1
- **US-2 (Artist / pick-tool).** As an artist, I want to **choose a tool** (pencil,
  eraser, flood-fill, line, colour-picker) so I can perform different edits. →
  REQ-P1-UI-011..015, -016 · `tool-controllers` · P1
- **US-3 (Artist / pick-colour).** As an artist, I want to **see the document's palette
  and select the active colour** so my strokes use the colour I want; the active swatch
  reflects it. → REQ-P1-UI-017, -015 · `palette-panel` · P1
- **US-4 (Artist / navigate).** As an artist, I want to **zoom (including deep zoom) and
  pan** across the 8K grid, with an optional grid overlay and snapping, so I can work at
  pixel precision. → REQ-P1-UI-004, -005, -007 · `canvas-navigation` · P1
- **US-5 (Artist / see-pixels).** As an artist, I want the canvas to **render my pixels
  crisply** (nearest-neighbour, no blur) and stay responsive on a large canvas. →
  REQ-P1-UI-001, -002, -003, -023 · `canvas-render` · P1
- **US-6 (Artist / undo-redo).** As an artist, I want **undo/redo of every edit** so
  mistakes are cheap; undo reverts exactly the edit I made. → REQ-P1-UI-009, -010, -019
  · `undo-redo` · P1
- **US-7 (Artist / manage-documents).** As an artist, I want to **open several documents
  in tabs** and create a new document at a sensible default size (with 8K supported). →
  REQ-P1-UI-018, -020 · `document-tabs` · P1
- **US-8 (Any user / localise).** As a user in any locale, I want **the whole UI in my
  language**, switchable at runtime without restart. → REQ-P1-UI-021, -022, -026
  · `i18n` · P1
- **US-9 (Any user / accessibility & theme).** As a keyboard user or a user in a dark
  environment, I want **every control reachable by keyboard with a visible focus** and a
  UI **correct in both light and dark themes**. → REQ-P1-UI-024, -025 · `a11y`,
  `theming` · P1
- **US-10 (Artist / colour-hub, FUTURE).** As an artist, I want to **right-click for a
  colour hub** (favourites + RGB wheel with live harmonies). → **deferred to Phase 3**;
  Phase 1 provides only the dispatch **seam** (REQ-P1-UI-008). · `colour-hub` · P3-future

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `canvas-render` | Scene rendering of the pixel buffer + tile/grid background; NN, no AA; scene-rect. | 1 |
| `canvas-navigation` | Zoom, pan, grid overlay + snapping across the 8K grid. | 1 |
| `paint-interaction` | Left-click / drag paint of the active colour onto the target pixel(s). | 1 |
| `tool-controllers` | Pencil / eraser / flood-fill / line / colour-picker controllers binding to logic primitives. | 1 |
| `undo-redo` | QUndoCommand bridge over `logic/history.py`; single QUndoStack. | 1 |
| `palette-panel` | Display the indexed palette; single-select the active colour. | 1 |
| `document-tabs` | Multiple open documents in tabs; new-document creation. | 1 |
| `main-window-chrome` | Toolbar, menu bar, actions wiring. | 1 |
| `i18n` | LanguageManager, QTranslator by QLocale, live retranslate. | 1 |
| `theming` | Light + dark themes, colours by role. | 1 |
| `a11y` | Accessible names/descriptions, keyboard reachability, visible focus. | 1 |
| `colour-hub` | Right-click contextual colour menu, favourites, RGB wheel + harmonies. | 3-future |

## 4. Functional requirements

Each REQ carries `traces:` to the dossier `S-id` / research `F`-finding it realises
(Article X). Requirements are technology-neutral WHAT statements; the binding to a
specific `logic/` callable is named as a **constraint** (the API is fixed upstream), not
as a HOW decision.

### `ui/canvas_scene.py` — canvas-render

#### REQ-P1-UI-001 — Render the pixel buffer, nearest-neighbour, no anti-aliasing
`traces:` S1 (8K grid rendered nearest-neighbour, no AA), F2
The canvas scene displays the pixels of the **active document's active layer buffer**
(`logic/pixel_buffer.PixelBuffer`) so that pixel `(x,y)` in the buffer maps to the scene
cell at `(x,y)`. Rendering is nearest-neighbour with anti-aliasing disabled at every zoom
level (a magnified pixel is a crisp square, never blurred). A change to a buffer pixel is
reflected in the scene at that pixel.

#### REQ-P1-UI-002 — Fix the scene rect once for the large scene
`traces:` S1, F3, S12
At initialisation the scene sets its scene rect to `(0, 0, W, H)` where `W`/`H` are the
active document's dimensions (up to `MAX_CANVAS_WIDTH` × `MAX_CANVAS_HEIGHT` from
`logic/constants.py`), so the view does not recompute the bounding rect from item
geometry. Resizing the document (`Document.resize_canvas`) updates the scene rect.

#### REQ-P1-UI-003 — Tile/grid background drawn only over the exposed rect
`traces:` S1 (tile culling, 64 px tiles), F2, S12
The scene paints its checkerboard/tile background inside `drawBackground(painter, rect)`
covering **only** the exposed `rect` argument (never the whole 8K scene), tiled on
`TILE_SIZE` (64) with `TILE_BUFFER` (1) from `constants.py`. No per-frame allocation
proportional to total scene area occurs.

### `ui/canvas_view.py` — canvas-navigation + paint-interaction

#### REQ-P1-UI-004 — Zoom, including deep zoom, nearest-neighbour
`traces:` S5, S12
The view zooms between a **fit-to-view** minimum and a deep-zoom maximum (default
**6400 %**, CL-1), in geometric steps derived from `SCALE_FACTOR` (CL-2), anchored on the
cursor (CL-15). Magnified pixels stay crisp (NN, no AA — REQ-P1-UI-001). The current zoom
is queryable/observable so other UI (grid threshold, status) can react.

#### REQ-P1-UI-005 — Pan across the 8K grid
`traces:` S5
The view pans across the whole scene via middle-mouse drag and Space+left-drag (CL-3),
with scrollbars as a fallback. Panning never triggers a paint. The view can be
programmatically centred on a scene point (for tests and "fit").

#### REQ-P1-UI-006 — Left-click paints the target pixel(s) with the active colour
`traces:` S2, S7
A left-click (or left-drag) with an active paint tool maps the cursor to the target
buffer pixel(s) (floored integer mapping, CL-12), applies the active tool's `logic/`
drawing primitive with the **active colour**, and pushes **exactly one** undoable command
per stroke (CL-9). A click whose target lies outside the buffer is a no-op (no command
pushed). The command mutates the buffer via the reversible-op path so undo reverts
exactly the affected pixels.

#### REQ-P1-UI-007 — Optional grid overlay + snapping
`traces:` S5
A per-pixel grid overlay is **off by default** and can be toggled on; when enabled it is
only shown once zoom passes a legibility threshold (default: pixel edge ≥ 8 device px,
CL-4) to avoid clutter at low zoom. When snapping is on, tool coordinates snap to whole
pixels. The overlay is drawn in the exposed rect only (consistent with REQ-P1-UI-003).

#### REQ-P1-UI-008 — Right-click dispatches to a menu hook (seam; hub deferred)
`traces:` S3 (deferred), S6 (extensibility)
Right-click on the canvas emits a single dispatch to a replaceable menu hook, passing the
scene/buffer coordinate. In **Phase 1** the hook shows a minimal placeholder context menu
(or a no-op) — the S3/S4 colour hub (favourites + RGB wheel + live harmonies) is
**explicitly deferred to Phase 3** (needs research F9). The seam must let Phase 3 attach
the colour hub without changing the view's public surface.

### `ui/commands.py` — undo-redo

#### REQ-P1-UI-009 — QUndoCommand wrappers over logic reversible ops
`traces:` S7, C1, F1, S11
`ui/commands.py` defines `QUndoCommand` subclass(es) (from `PySide6.QtGui`, F1) that
**delegate** their `redo()`/`undo()` to the Qt-free reversible ops in `logic/history.py`
(e.g. a captured `PixelEdit` / the `record_edit` diff). The command holds no domain logic
of its own — it only bridges Qt's undo framework to the logic command. This is the **only
Qt-importing module outside `ui/`** (Article I §2 / C1).

#### REQ-P1-UI-010 — A single QUndoStack owns undo/redo per document
`traces:` S7, F1
Each open document has one `QUndoStack`; pushing a paint command applies it once; `undo()`
reverts exactly the pixels the command changed and `redo()` re-applies them; the stack's
`canUndo`/`canRedo` state drives the undo/redo actions' enabled state (REQ-P1-UI-019).
Command coalescing follows CL-9 (one command per stroke).

### `ui/tools/` — tool-controllers

#### REQ-P1-UI-011 — Tool-controller contract & active-tool selection
`traces:` S2, S11
Each tool controller is a thin presentation object that (a) translates canvas
mouse events into a `logic/drawing.py` call, (b) supplies the active colour/target buffer,
and (c) produces one QUndoCommand per completed interaction (CL-9). Controllers contain
**no domain logic** (all pixel math lives in `logic/drawing.py`). Exactly one tool is
active at a time; selecting a tool (toolbar or shortcut) makes subsequent canvas
interactions use it. The five tools are pencil, eraser, flood-fill, line, colour-picker
(CL-5).

#### REQ-P1-UI-012 — Pencil tool
`traces:` S2
The pencil controller paints the clicked/dragged pixel(s) with the active colour via
`drawing.pencil`, coalescing a drag into one command.

#### REQ-P1-UI-013 — Eraser tool
`traces:` S2
The eraser controller clears the clicked/dragged pixel(s) (RGBA → transparent; INDEXED →
index 0 per the buffer default) via `drawing.pencil` with the erase value, one command per
stroke.

#### REQ-P1-UI-014 — Flood-fill tool
`traces:` S2
The flood-fill controller fills the contiguous region at the clicked pixel with the active
colour via `drawing.flood_fill`, as one command. An in-bounds seed on an already-matching
region produces no visible change and no command (mirrors the logic no-op).

#### REQ-P1-UI-015 — Line tool
`traces:` S2
The line controller previews a straight line from the press point to the current cursor
during drag and, on release, commits the Bresenham line (`drawing.line`) with the active
colour as one command. The preview does not push a command until release (CL-11).

#### REQ-P1-UI-016 — Colour-picker tool
`traces:` S2, S4
The colour-picker controller reads the colour at the clicked pixel (`drawing.pick_color`)
and sets it as the **active colour / active swatch** (S4). Picking does not mutate the
buffer and pushes no undo command.

### `ui/main_window.py` — main-window-chrome, palette-panel, document-tabs

#### REQ-P1-UI-017 — Tool toolbar
`traces:` S2
A toolbar exposes one action per tool (REQ-P1-UI-012..016); activating an action selects
that tool (REQ-P1-UI-011). Actions are checkable/exclusive so the active tool is visible.

#### REQ-P1-UI-018 — Palette panel with single active-colour selection
`traces:` S4, S7
A palette panel displays the active document's indexed `logic/palette.Palette` colours in
index order. Selecting a swatch is **single-select** (CL-6) and sets the active colour →
active swatch (S4), which subsequent paint tools use. The panel reflects palette changes
(e.g. after a colour-picker pick updating the active swatch, and after opening a document
with a different palette).

#### REQ-P1-UI-019 — Undo/redo actions + menu bar
`traces:` S7, F1
The window provides Undo and Redo actions (menu + toolbar, standard shortcuts) bound to
the active document's `QUndoStack`; each is enabled only when the stack reports it is
possible (REQ-P1-UI-010). A menu bar hosts at least File (New / Open / Save /
Save As / Close), Edit (Undo / Redo), and View (zoom, grid toggle) groupings.

#### REQ-P1-UI-020 — Document tabs & new-document creation
`traces:` S1, S6, S7
Multiple open `logic/document.Document`s are presented as tabs; switching a tab makes that
document active (its buffer, palette, QUndoStack, and scene rect become current).
Creating a new document uses a **default size of 64 × 64** RGBA (CL-7), with arbitrary
sizes up to 8K (`MAX_CANVAS_WIDTH` × `MAX_CANVAS_HEIGHT`) supported. Opening/saving
delegates to `data/project_io.py` (`.pixproj`).

### `ui/i18n.py` — i18n

#### REQ-P1-UI-021 — LanguageManager installs a translator by locale
`traces:` F6, S8
A `LanguageManager` selects the UI language from the system `QLocale` (fallback English,
CL-14) and installs the matching `QTranslator` on the application; it can switch language
at runtime and exposes the available languages.

#### REQ-P1-UI-022 — Live retranslation on LanguageChange
`traces:` F5, F6
Every hand-built widget wraps user-visible text in `tr()` and overrides `changeEvent()`
to re-set that text on `QEvent.LanguageChange`, so switching language at runtime updates
all visible labels/tooltips/menu items **without a restart** (F5).

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P1-UI-023 — Performance: 8K paint/redraw within the frame budget *(NFR, Article VI)*
`traces:` S1, S12, F2, F7, Article VI
Painting and redrawing the 8K grid (7680 × 4320) holds `FPS_TARGET = 60`, i.e. per-frame
render time ≤ `FRAME_BUDGET_MS = 16`. `drawBackground` repaints only the exposed rect
(REQ-P1-UI-003) and off-screen tiles are culled; the resident pixel buffer is never culled
(only Qt rendering is, F7). This budget is **verified headless by AGT-10** (`perf_profile`
/ `frame-profile`); an over-budget measurement yields an AGT-10 optimisation directive,
never a relaxation of the budget. The concrete culling/dirty-rect/viewport strategy is
AGT-10 plan-level (out of this spec).

#### REQ-P1-UI-024 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive widget (tool actions, palette swatches, tabs, undo/redo, menu items,
the canvas view) exposes an accessible name and, where non-obvious, an accessible
description; is reachable and operable by keyboard (logical tab order + shortcuts); and
shows a visible focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P1-UI-025 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The UI renders correctly in both light and dark themes; colours are defined once by role
(never hard-coded per widget) and the canvas checkerboard/grid stays legible in both. Both
themes are test-verified (AGT-06 pytest-qt, each acceptance test runnable under both).

#### REQ-P1-UI-026 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string in `ui/` is wrapped in `tr()`/`translate()`; none is a bare
literal. Verified by `string_audit_check` (AGT-07); an unwrapped string is a blocking
finding.

## 6. Non-goals (explicit; deferred)

- **S3/S4 right-click colour hub** — contextual colour menu, persisted Favourites list,
  Canva-style RGB colour wheel + live harmonies (complementary/analogous/triadic/split/
  ramps). → **Phase 3** (needs research F9). Phase 1 ships **only the dispatch seam**
  (REQ-P1-UI-008).
- **Selection / transform / symmetry / RotSprite / shape-drag preview / tiled mode** →
  **Phase 2**.
- **Blend modes, layer opacity/visibility/lock UI, layer groups/masks, artboards** →
  **Phase 4** (the `Document` tree already carries the attributes; no UI here).
- **Animation timeline / onion skin / playback** → Phase 5 (frames exist in the model).
- **Export / atlas / GIF pipeline** → Phase 7. **Cloud sync** → Phase 10.
- **GPU render-pipeline strategy** (QOpenGL viewport, BSP tuning, dirty-rect design) —
  AGT-10 **plan-level** directive, not a spec requirement here (this spec states only the
  16 ms budget, REQ-P1-UI-023).
- No plan/tasks (AGT-01), no logic/UI/test code (AGT-03/05/04/06), no new technology
  (fixed by S8).

## 7. Dependencies & assumptions

- Upstream logic/data API is **fixed and shipped** (`specs/phase-1-core-engine/spec.md`):
  `Document` (frames→layers→buffer, `resize_canvas`), `PixelBuffer` (get/set/fill,
  bounds), `drawing` (pencil, line, rectangle, ellipse, flood_fill, pick_color — each
  returns changed `(x,y)` coords), `history` (`Command`, `PixelEdit`, `History`,
  `record_edit`), `palette.Palette`, `color.rgba`, `constants.*`. The UI **binds** to
  these; it must not re-implement pixel math (Article I).
- Undo bridging uses `logic/history.py`'s already-applied `PixelEdit`/`record_edit` diffs
  so `ui/commands.py` stays a thin Qt wrapper (REQ-P1-UI-009).
- The active colour is an RGBA value (`color.rgba`) held by the window and consumed by
  tools; the palette panel and colour-picker both write it.

## 8. Behaviours flagged for AGT-01 / AGT-10 (not blockers)

- **BF-1 (AGT-10, plan).** The specific tile-culling / dirty-rect / QOpenGLWidget-viewport
  strategy that makes REQ-P1-UI-023 pass is AGT-10's render-strategy output; this spec
  fixes only the budget and the `drawBackground`-exposed-rect + scene-rect rules (F2/F3).
- **BF-2 (AGT-01, plan).** Whether the canvas draws pixels as a single
  `QGraphicsPixmapItem` (whole-buffer image) vs. tiled pixmap items is a HOW decision for
  `sdd-plan`; the spec requires only NN/no-AA rendering + exposed-rect background + the
  frame budget.
- **BF-3 (AGT-01).** `SCALE_FACTOR`/`PARALLAX_FACTOR` are Phase-1 constants; whether zoom
  step reuses `SCALE_FACTOR` (CL-2) or a new named zoom constant is added to
  `constants.py` is an S12 placement call for AGT-01 (no magic numbers in `ui/`).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** all files here live in `ui/`; the only Qt import
  outside `ui/` remains `ui/commands.py`. Controllers/panels must import `logic/` for all
  domain behaviour and never embed pixel math. Enforced by `check_layering`/`check_cycles`.
- **Article II (numerics):** zoom range/step, grid threshold, default doc size, and any
  tuning value must resolve to named constants in `logic/constants.py` (no literals in
  `ui/`) — see BF-3. Clarification defaults in §10 name candidate values for AGT-01 to
  place.
- **Article V (UX):** REQ-P1-UI-024/-025/-026 make a11y + both themes + full
  translatability blocking gates.
- **Article VI (performance):** REQ-P1-UI-023 binds the 16 ms budget.
- **Article X (traceability):** every REQ above traces to an S-id / F-finding; the
  forward matrix is in `traceability.md`.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with
sensible defaults grounded in the dossier and mainstream pixel-art editor norms
(Aseprite / Pixelorama). Each is recorded as a **category-1 decision** with its rationale
(A2-D2 Branch B). **No open clarification blocks planning; no genuine blocker was found.**

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Zoom range? | **Fit-to-view (min) … 6400 % (max)**. | Aseprite/Pixelorama offer deep zoom for pixel-level work; fit-to-view is the natural minimum for an 8K canvas. |
| **CL-2** | Zoom step? | Geometric step derived from `SCALE_FACTOR = 0.15` (≈ ×1.15 per wheel notch); discrete preset stops (100/200/400/…/6400 %) for keyboard zoom. | Reuses an existing S12 constant (Article II); geometric zoom feels linear to the eye. |
| **CL-3** | Pan gesture? | **Middle-mouse drag** and **Space + left-drag**; scrollbars as fallback. | Mainstream editor convention (Aseprite, Krita, Photoshop). |
| **CL-4** | Grid overlay default & visibility? | **Off by default**; auto-shown only past a zoom threshold (pixel edge ≥ 8 device px); user-toggleable. | Grid at low zoom is visual noise; standard to reveal it when zoomed in. |
| **CL-5** | Tool set for Phase 1? | **Pencil, eraser, flood-fill, line, colour-picker** (the five). | Prompt + ROADMAP Phase-1 UI bullet; each maps to a shipped `logic/drawing.py` primitive. |
| **CL-6** | Palette panel selection model? | **Single-select** active colour (one active swatch). | S4 (one active swatch reflects the current selection). |
| **CL-7** | Default new-document size? | **64 × 64** RGBA; arbitrary sizes up to **8K** (`MAX_CANVAS_*`) supported — 8K is the ceiling, not the default. | Small default matches Aseprite/Pixelorama norms; 8K is S1's supported maximum, not a sane default canvas. |
| **CL-8** | Right-click behaviour in Phase 1? | **Dispatch seam** to a menu hook with a placeholder menu; the S3/S4 colour hub is deferred to Phase 3. | Prompt deferral; the hub needs research F9 (Phase 3). |
| **CL-9** | Undo granularity per stroke? | **One QUndoCommand per completed stroke** (a click-drag pencil stroke coalesces to a single command), not one per pixel. | Usable undo granularity; matches `record_edit` capturing a whole op as one diff. |
| **CL-10** | What sets the active colour? | The **palette panel** (select swatch) and the **colour-picker tool** (pick from canvas) both set the active colour / active swatch. | S4. |
| **CL-11** | Line tool commit timing? | Live preview during drag; **commit one command on mouse release**. | Standard line-tool UX; preview must not pollute undo. |
| **CL-12** | Click → pixel mapping? | Scene point floored to integer pixel `(x,y)`; clicks resolving outside the buffer are **no-ops** (no command). | S1 grid semantics; `logic/drawing` already clips off-buffer coords. |
| **CL-13** | Default theme & switching? | Ship both **light and dark**; default follows OS/light, switchable at runtime. | Article V (both themes correct). |
| **CL-14** | Default language? | System `QLocale`; fallback **English**. | F6 / QLocale-driven selection. |
| **CL-15** | Zoom anchor? | Zoom anchors on the **cursor** (falls back to view centre for keyboard zoom). | Mainstream editor convention. |
| **CL-16** | Culling tile size? | `TILE_SIZE = 64`, `TILE_BUFFER = 1` from `constants.py`. | S1 (64 px tiles) / S12. |

**SUSPEND / escalate:** *none.* Every ambiguity was responsibly defaultable from the
dossier + mainstream norms. Genuine HOW-choices (viewport class, dirty-rect design,
single-vs-tiled pixmap) are deferred to AGT-01/AGT-10 by design (§8), not held as open
clarifications.

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. All are written so **AGT-06** can drive them headless
with **pytest-qt** (`QT_QPA_PLATFORM=offscreen`), and **each is to be run under BOTH the
light and dark themes** (per REQ-P1-UI-025 — expressed once here as a global rule rather
than duplicated per scenario). Scenario ids map to the matrix in `traceability.md`; tests
are authored later by AGT-06 (currently `pending`).

> Global rule (applies to every scenario below): *Given the app runs headless
> (`QT_QPA_PLATFORM=offscreen`) — the scenario is executed and asserted identically under
> the light theme and the dark theme.*

### Feature: Canvas render (REQ-P1-UI-001..003)
```gherkin
Scenario: SC-P1-UI-001-1 a buffer pixel is rendered nearest-neighbour, no AA
  Given a document whose active layer buffer has pixel (3,3) set to RED
  When the canvas scene renders at any zoom
  Then the scene cell for buffer pixel (3,3) shows exactly RED with no anti-aliased edge

Scenario: SC-P1-UI-001-2 magnified pixel is a crisp square
  Given the view is zoomed to 3200%
  When one buffer pixel is painted
  Then its on-screen region is a solid square (no interpolation/blur)

Scenario: SC-P1-UI-002-1 scene rect matches the document size at init
  Given a new 64x64 document
  When the scene is created
  Then sceneRect() equals (0,0,64,64)

Scenario: SC-P1-UI-002-2 resizing the document updates the scene rect
  Given an open document
  When Document.resize_canvas(128,96) is applied
  Then sceneRect() equals (0,0,128,96)

Scenario: SC-P1-UI-003-1 drawBackground repaints only the exposed rect
  Given an 8K-sized scene
  When drawBackground(painter, rect) is invoked with a small exposed rect
  Then only cells intersecting that rect are painted (no full-scene fill)

Scenario Outline: SC-P1-UI-003-2 background tiles on TILE_SIZE
  Given the tile background
  When it is painted over an exposed rect
  Then tile boundaries fall on multiples of TILE_SIZE (64)
  Examples: | exposed | (0,0,64,64) | (100,100,80,80) |
```

### Feature: Zoom / pan / grid (REQ-P1-UI-004..007)
```gherkin
Scenario: SC-P1-UI-004-1 zoom is clamped to the configured range
  Given the fit-to-view minimum and the 6400% maximum
  When the user zooms past either bound
  Then the zoom is clamped to that bound (never below fit, never above 6400%)

Scenario: SC-P1-UI-004-2 a wheel notch scales by the SCALE_FACTOR step
  Given the current zoom Z
  When the user scrolls one notch to zoom in
  Then the new zoom equals Z scaled by the SCALE_FACTOR-derived step, anchored on the cursor

Scenario: SC-P1-UI-005-1 middle-drag pans without painting
  Given an active pencil tool
  When the user middle-drags across the canvas
  Then the view scrolls and buffer pixels are unchanged and no undo command is pushed

Scenario: SC-P1-UI-005-2 space+left-drag pans without painting
  Given Space is held
  When the user left-drags across the canvas
  Then the view pans and no pixel is painted

Scenario: SC-P1-UI-007-1 grid overlay is off by default
  Given a freshly opened canvas
  When it is displayed
  Then the per-pixel grid overlay is not shown

Scenario: SC-P1-UI-007-2 grid overlay appears past the zoom threshold when enabled
  Given the grid overlay is toggled on
  When zoom crosses the legibility threshold (pixel edge >= 8 device px)
  Then the grid overlay becomes visible (and hides again below the threshold)

Scenario: SC-P1-UI-007-3 snapping constrains tool coordinates to whole pixels
  Given snapping is on
  When a tool interaction occurs at a sub-pixel scene point
  Then the resolved coordinate is the floored integer pixel
```

### Feature: Left-click paint (REQ-P1-UI-006)
```gherkin
Scenario: SC-P1-UI-006-1 left-click paints the target pixel and pushes one command
  Given the pencil tool and active colour = BLUE
  When the user left-clicks at the scene point mapping to buffer pixel (10,7)
  Then buffer[10,7] == BLUE and exactly one command is on the QUndoStack

Scenario: SC-P1-UI-006-2 a drag paints all covered pixels as one command
  Given the pencil tool
  When the user left-drags across pixels (0,0)->(3,0)
  Then pixels (0,0),(1,0),(2,0),(3,0) are painted and the QUndoStack depth increased by exactly 1

Scenario: SC-P1-UI-006-3 clicking outside the buffer is a no-op
  Given a 64x64 document
  When the user left-clicks at a scene point outside (0,0,64,64)
  Then no pixel changes and no command is pushed
```

### Feature: Undo / redo bridge (REQ-P1-UI-009..010)
```gherkin
Scenario: SC-P1-UI-010-1 undo reverts exactly the painted pixel(s)
  Given a pencil click set buffer[10,7] to BLUE over prior TRANSPARENT
  When the user triggers Undo
  Then buffer[10,7] returns to TRANSPARENT and no other pixel changed

Scenario: SC-P1-UI-010-2 redo re-applies the reverted edit
  Given the edit above was undone
  When the user triggers Redo
  Then buffer[10,7] is BLUE again

Scenario: SC-P1-UI-010-3 undo/redo actions enable-state tracks the stack
  Given an empty QUndoStack
  Then Undo is disabled and Redo is disabled
  And after one paint Undo is enabled
  And after undo Redo is enabled

Scenario: SC-P1-UI-009-1 the command delegates to logic/history (no domain math in ui)
  Given a paint command
  When it is undone and redone
  Then the pixel changes are exactly those recorded by the logic PixelEdit/record_edit diff
```

### Feature: Tool controllers (REQ-P1-UI-011..016)
```gherkin
Scenario: SC-P1-UI-011-1 exactly one tool is active at a time
  Given the pencil is active
  When the user selects the eraser
  Then the eraser is active and the pencil is not

Scenario: SC-P1-UI-012-1 pencil paints with the active colour (one command per stroke)
  Given pencil active, active colour GREEN
  When the user clicks pixel (2,2)
  Then buffer[2,2] == GREEN and QUndoStack depth increased by 1

Scenario: SC-P1-UI-013-1 eraser clears to the buffer default (one command)
  Given eraser active on an RGBA buffer, pixel (2,2) currently RED
  When the user clicks pixel (2,2)
  Then buffer[2,2] == TRANSPARENT and one undoable command was pushed

Scenario: SC-P1-UI-014-1 flood-fill fills the contiguous region as one command
  Given flood-fill active, active colour YELLOW, a contiguous TRANSPARENT region
  When the user clicks inside the region
  Then the whole contiguous region becomes YELLOW via one command

Scenario: SC-P1-UI-014-2 flood-fill on an already-matching region is a no-op
  Given flood-fill active with active colour equal to the seed pixel colour
  When the user clicks the seed
  Then no pixel changes and no command is pushed

Scenario: SC-P1-UI-015-1 line tool previews on drag and commits one command on release
  Given the line tool, active colour BLACK
  When the user presses at (0,0), drags to (4,0), and releases
  Then during drag no command exists, and on release the Bresenham line (0,0)->(4,0) is painted as exactly one command

Scenario: SC-P1-UI-016-1 colour-picker sets the active colour and pushes no command
  Given pixel (5,5) is CYAN and the picker tool is active
  When the user clicks (5,5)
  Then the active colour/active swatch becomes CYAN, the buffer is unchanged, and no command is pushed
```

### Feature: Main window — toolbar / palette / tabs / actions (REQ-P1-UI-017..020)
```gherkin
Scenario: SC-P1-UI-017-1 the toolbar selects the active tool
  Given the tool toolbar
  When the user activates the "flood-fill" action
  Then the flood-fill controller becomes the active tool and its action is checked

Scenario: SC-P1-UI-018-1 the palette panel shows the document palette in index order
  Given a document with palette [RED, GREEN, BLUE]
  When the palette panel is shown
  Then it displays three swatches in the order RED, GREEN, BLUE

Scenario: SC-P1-UI-018-2 selecting a swatch sets the active colour (single-select)
  Given the palette panel shows [RED, GREEN, BLUE]
  When the user selects the GREEN swatch
  Then the active colour/active swatch is GREEN and only that swatch is selected

Scenario: SC-P1-UI-019-1 undo/redo actions are wired to the active document's stack
  Given an open document with one paint command
  When the user triggers the Edit>Undo menu action
  Then that document's QUndoStack undoes one command

Scenario: SC-P1-UI-020-1 a new document defaults to 64x64
  Given the app
  When the user creates a new document with defaults
  Then a 64x64 RGBA document opens in a new tab and becomes active

Scenario: SC-P1-UI-020-2 an 8K document is supported
  Given the app
  When the user creates a document at 7680x4320
  Then it opens successfully and its scene rect is (0,0,7680,4320)

Scenario: SC-P1-UI-020-3 switching tabs switches the active document context
  Given two open documents A and B in tabs
  When the user selects tab B
  Then B's buffer, palette and QUndoStack become the active context
```

### Feature: Internationalisation (REQ-P1-UI-021..022, -026)
```gherkin
Scenario: SC-P1-UI-021-1 the LanguageManager installs a translator by locale
  Given the system QLocale is a supported language
  When the app starts
  Then the LanguageManager installs the matching QTranslator (falling back to English)

Scenario: SC-P1-UI-022-1 changeEvent re-translates visible labels on LanguageChange
  Given the main window is showing menu/tool labels
  When the language is switched at runtime (a QEvent.LanguageChange is delivered)
  Then every visible label/tooltip/menu item is re-set to the new language without restart

Scenario: SC-P1-UI-026-1 no user-visible string is a bare literal
  Given the ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings
```

### Feature: Accessibility & theming (REQ-P1-UI-024..025)
```gherkin
Scenario: SC-P1-UI-024-1 interactive widgets expose accessible names
  Given the main window is shown
  When each interactive widget (tool actions, palette swatches, tabs, undo/redo, canvas) is inspected
  Then each has a non-empty accessible name

Scenario: SC-P1-UI-024-2 every control is keyboard reachable with visible focus
  Given the main window is shown
  When the user tabs through the controls
  Then focus reaches every interactive control in a logical order and the focused control shows a visible focus indicator

Scenario: SC-P1-UI-025-1 the UI is correct in both themes
  Given the app
  When it is rendered under the light theme and under the dark theme
  Then all widgets and the canvas checkerboard/grid render legibly with role-based colours (no hard-coded per-widget colour)
```

### Feature: Right-click seam (REQ-P1-UI-008)
```gherkin
Scenario: SC-P1-UI-008-1 right-click dispatches to the menu hook with the coordinate
  Given the canvas view with a registered menu hook
  When the user right-clicks at the scene point mapping to buffer pixel (9,9)
  Then the hook is invoked exactly once with buffer coordinate (9,9)

Scenario: SC-P1-UI-008-2 the Phase-1 hook shows only a placeholder (no colour hub)
  Given the default Phase-1 menu hook
  When it is invoked
  Then it shows a placeholder/no-op menu and does not open a colour wheel or favourites list
```

### Feature: Performance (REQ-P1-UI-023) — profiled by AGT-10
```gherkin
Scenario: SC-P1-UI-023-1 a paint redraw at 8K stays within the frame budget
  Given a 7680x4320 document displayed
  When a single-pixel paint triggers a redraw
  Then the measured per-frame render time is <= FRAME_BUDGET_MS (16 ms)
  # Measured headless by AGT-10 (perf_profile / frame-profile); an over-budget result
  # yields an AGT-10 optimisation directive, not a budget relaxation.

Scenario: SC-P1-UI-023-2 panning the 8K canvas culls off-screen tiles
  Given a 7680x4320 document
  When the view pans
  Then only tiles intersecting the exposed rect are painted (background cull holds) and the resident buffer is not culled
```

---

## 12. Exit / status

- Forward spec authored for the Phase-1 UI increment; **26 REQ-IDs**
  (`REQ-P1-UI-001..026`), each traced to an S-id / F-finding (Article X).
- **16 clarification defaults** recorded (§10), each grounded in the dossier + mainstream
  editor norms; **no open clarification blocks planning**.
- **No SUSPEND blocker.** Genuine HOW-choices are deferred to AGT-01/AGT-10 by design
  (§8), not held as ambiguities.
- Acceptance scenarios cover every functional and NFR requirement; tests are authored
  later by AGT-06 (`pending` in the matrix). Forward matrix in `traceability.md`.
- **STATUS: COMPLETED.**
