# Specification — Phase 4: Layer & Canvas System

| Field | Value |
| --- | --- |
| Feature | `phase-4-layer-canvas` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-02 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VII, VIII, X) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no `logic/blend.py` or layer UI exists yet; this spec defines the WHAT/WHY Phase 4 must realise |
| REQ-ID range | `REQ-P4-LOGIC-001..015`, `REQ-P4-UI-001..018` (from the ROADMAP reserved `REQ-P4-*` prefixes) |
| Layer scope | `pixelart_creator/logic/` (new `blend.py`; extend `document.py`) + `pixelart_creator/ui/` (layer panel, canvas compositing, tabs). `.pixproj` persistence extension flagged for a DATA slice (§8, DEP-3). |
| Binds to (upstream, shipped) | Phase 1 `logic/document.py` (`Document → frames → layers → buffer`; layers already carry `opacity`/`visible`/`locked` — the **REV-5** primitive), `logic/color.py` (`blend_over` = normal alpha compositing — the **FU-3** primitive reserved for this phase), `logic/pixel_buffer.py` (`blit(..., blend=True)`), `logic/history.py` (`Command`, `FunctionCommand`, `PixelEdit`, `History`) |
| Depends on (external) | The Researcher — `docs/research-blend-modes.md` (grounds the 12 blend-mode **formulas**; not yet present — see DEP-1). This spec fixes the WHAT/acceptance, not the maths. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The Phase-1 document tree already models `Document → frames → layers → PixelBuffer`, and
each `Layer` already carries `opacity` / `visible` / `locked` attributes (the **REV-5**
primitive). What is missing is the **non-destructive layer compositing** that turns that
tree into a real layer model: blend modes, opacity/visibility/lock as first-class
reversible edits, layer groups, masks, reference and (minimal) smart layers, a canvas
that renders the *composited* stack rather than a single layer, and multiple open
canvases (artboards) via the existing tab system.

Phase 4 is the "non-destructive editing" milestone. It reaches Aseprite / Pixelorama
layer-model parity (blend modes + groups + masks) and differentiates toward Pro Motion
NG (reference & smart layers). It builds strictly on the shipped substrate — the
normal-alpha compositing primitive `color.blend_over` (**FU-3**) becomes the *normal*
blend mode; the eleven non-normal modes extend it. No pixel maths leaks into `ui/`
(Article I).

This document specifies WHAT the layer & canvas system must do and WHY, technology-neutral
at the requirement level. The HOW — the exact blend formulas (grounded by The Researcher,
DEP-1), the dirty-rect recomposite strategy (AGT-10, DEP-2), single-vs-tiled pixmap
compositing (AGT-01/`sdd-plan`) — is downstream. It records the clarification defaults
chosen under the owner's autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**
- **`logic/blend.py` (new).** A `BlendMode` enumeration of the twelve modes — **normal**
  plus the eleven non-normal separable W3C modes **multiply, screen, overlay, darken,
  lighten, colour-dodge, colour-burn, hard-light, soft-light, difference, exclusion** —
  and a pure, deterministic per-pixel
  blend function per mode. *Normal* consumes `color.blend_over` (FU-3). A **stack
  compositor** that flattens an ordered list of layers (respecting each layer's
  visibility, opacity, and blend mode) into a single flat RGBA `PixelBuffer`. Zero Qt.
- **`logic/document.py` (extend).** Layer attribute ops (`set_opacity` / `set_visible` /
  `set_locked` / `set_blend_mode`) and structural ops (add / remove / reorder / duplicate)
  formalised as **reversible** operations (do/undo pairs usable by `ui/commands.py`);
  `Layer` gains a `blend_mode` attribute and a `locked`-guard. **Layer groups** (a group
  node composites its children then blends as one), **mask layers** (a layer's alpha
  modulated by a mask buffer), **reference (non-editable) layers**, and **smart layers**
  (minimal scope — see §6/CL-9). A `blend_mode` and group/mask model added to the tree.
- **`ui/` layer panel.** A layers panel listing the active frame's layers top-to-bottom
  with, per layer: an opacity slider, a visibility toggle, a lock toggle, a blend-mode
  dropdown, and drag-to-reorder; plus add / remove / duplicate and group / ungroup
  actions, and mask / reference / smart-layer affordances. Every mutation is one
  `QUndoCommand`.
- **`ui/` canvas compositing.** The canvas scene renders the **composited layer stack**
  (not just one layer) for the active frame; an edit to any layer triggers a recomposite
  of the affected region (dirty-rect — AGT-10, DEP-2).
- **`ui/` multiple canvases.** Multiple documents / artboards open as tabs (extend the
  Phase-1 tab system); each canvas is state-isolated.

**Out of scope (this phase):** see §6 Non-goals. Notably: the animation timeline that
composites per-frame stacks over time (Phase 5, builds on this compositor); advanced smart
layers (procedural / filter / live-transform objects — deferred, CL-9); the GPU
render-pipeline strategy (AGT-10 plan-level); export of a flattened image (Phase 7). No
plan/tasks/code (AGT-01/03/05); no new technology (fixed by S8); the blend **formulas**
themselves are The Researcher's output, not authored here.

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap
phase. Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Artist / stack-visibility).** As an artist, I want to **show or hide any layer**
  so I can focus on part of my art; a hidden layer contributes nothing to what I see. →
  REQ-P4-LOGIC-006, REQ-P4-UI-003 · `layer-attributes` · P4
- **US-2 (Artist / opacity).** As an artist, I want to **set each layer's opacity** so I
  can fade a layer in or out non-destructively. → REQ-P4-LOGIC-005, REQ-P4-UI-002
  · `layer-attributes` · P4
- **US-3 (Artist / lock).** As an artist, I want to **lock a layer** so I cannot
  accidentally paint on it. → REQ-P4-LOGIC-010, REQ-P4-UI-004 · `layer-attributes` · P4
- **US-4 (Artist / blend-modes).** As an artist, I want to **choose a blend mode per
  layer** (normal, multiply, screen, overlay, …) so I can achieve shading and lighting
  effects; each mode composites deterministically. → REQ-P4-LOGIC-001, -002, -003, -007,
  REQ-P4-UI-005 · `blend-modes` · P4
- **US-5 (Artist / compose).** As an artist, I want the canvas to **show all my layers
  composited together** in the right order so what I see is the finished image. →
  REQ-P4-LOGIC-004, REQ-P4-UI-012 · `layer-compositing` · P4
- **US-6 (Artist / manage-layers).** As an artist, I want to **add, remove, duplicate and
  reorder layers**, each undoable in one step. → REQ-P4-LOGIC-009, REQ-P4-UI-001, -006,
  -007, -013 · `layer-management` · P4
- **US-7 (Artist / groups).** As an artist, I want to **group layers** so the group
  composites its children then blends as a single unit. → REQ-P4-LOGIC-011,
  REQ-P4-UI-008 · `layer-groups` · P4
- **US-8 (Artist / masks).** As an artist, I want to **attach a mask to a layer** so the
  mask modulates the layer's alpha non-destructively. → REQ-P4-LOGIC-012,
  REQ-P4-UI-009 · `mask-layers` · P4
- **US-9 (Artist / reference-layer).** As an artist, I want a **reference (non-editable)
  layer** I can see and trace over but not paint on. → REQ-P4-LOGIC-013,
  REQ-P4-UI-010 · `reference-layers` · P4
- **US-10 (Artist / smart-layer).** As an artist, I want a **smart layer** that mirrors a
  source layer non-destructively (minimal scope — CL-9). → REQ-P4-LOGIC-014,
  REQ-P4-UI-011 · `smart-layers` · P4
- **US-11 (Artist / reversible-layer-ops).** As an artist, I want **every layer operation
  to be undoable** exactly like painting. → REQ-P4-LOGIC-008, -009, REQ-P4-UI-013
  · `layer-reversibility` · P4
- **US-12 (Artist / artboards).** As an artist, I want to **open several canvases /
  artboards as tabs** without one leaking state into another. → REQ-P4-UI-014
  · `multi-canvas` · P4
- **US-13 (Any user / responsive-compositing).** As an artist on a large canvas, I want
  layer edits to **recomposite fast enough to stay at 60 fps**. → REQ-P4-UI-015
  · `recomposite-perf` · P4
- **US-14 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English
  user, I want the layer panel **keyboard-reachable, correct in both themes, fully
  translatable**. → REQ-P4-UI-016, -017, -018 · `a11y`, `theming`, `i18n` · P4

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `blend-modes` | The 12-mode `BlendMode` enum + per-pixel blend maths in `logic/blend.py`. | 4 |
| `layer-compositing` | Flattening an ordered layer stack (visibility/opacity/mode) into one RGBA buffer. | 4 |
| `layer-attributes` | Per-layer opacity / visibility / lock state and their reversible edits. | 4 |
| `layer-management` | Add / remove / duplicate / reorder layers. | 4 |
| `layer-reversibility` | Every layer op wrapped as a single reversible command. | 4 |
| `layer-groups` | Group node that composites children then blends as one. | 4 |
| `mask-layers` | A mask buffer modulating a layer's alpha non-destructively. | 4 |
| `reference-layers` | Visible-but-non-editable layer for tracing. | 4 |
| `smart-layers` | Non-destructive instance mirroring a source layer (minimal scope). | 4 |
| `layer-panel` | The `ui/` panel exposing all layer controls. | 4 |
| `multi-canvas` | Multiple documents / artboards as isolated tabs. | 4 |
| `recomposite-perf` | Dirty-rect recomposite of the stack within the frame budget. | 4 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 4 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-4
capability + forward-inherited primitive (Article X). Requirements are technology-neutral
WHAT statements; a binding to a fixed `logic/` callable is named as a **constraint**, not
a HOW decision.

### `logic/blend.py` — blend-modes

#### REQ-P4-LOGIC-001 — Blend-mode enumeration (single source)
`traces:` S6 (layer model), Phase-4 capability
`logic/blend.py` defines a `BlendMode` enumeration with exactly twelve members — `NORMAL`
plus the eleven non-normal separable W3C modes:
`NORMAL`, `MULTIPLY`, `SCREEN`, `OVERLAY`, `DARKEN`, `LIGHTEN`, `COLOR_DODGE`,
`COLOR_BURN`, `HARD_LIGHT`, `SOFT_LIGHT`, `DIFFERENCE`, `EXCLUSION`. The enum is the single
source of the mode vocabulary shared by the compositor, the document model, the UI
dropdown, and `.pixproj`. The default mode is `NORMAL` (CL-2).

#### REQ-P4-LOGIC-002 — Each blend mode matches the grounded formula on known values
`traces:` Phase-4 capability, F-blend (DEP-1 — `docs/research-blend-modes.md`)
For each `BlendMode`, a pure, deterministic function blends a source channel value over a
destination channel value producing the composited result. Each mode's output on
**known reference values** matches the formula grounded by The Researcher
(`docs/research-blend-modes.md`, DEP-1) — e.g. `multiply(a,b) = a·b/255`,
`screen(a,b) = 255 − (255−a)(255−b)/255`, at the canonical inputs `(0, x)`, `(255, x)`,
`(x, x)`. Blending is channel-wise over RGB with alpha handled per the compositor
(REQ-P4-LOGIC-004); identical inputs always yield identical output (determinism, P2). The
concrete per-mode formulas are DEP-1's output, not fixed here.

#### REQ-P4-LOGIC-003 — Normal mode delegates to `color.blend_over` (FU-3)
`traces:` FU-3 (forward-inherited: `color.blend_over` reserved for Phase-4 normal blend), S7
The `NORMAL` blend mode is straight-alpha source-over compositing and is implemented by
**delegating to `color.blend_over`** (the FU-3 primitive shipped in Phase 1) — it is not
re-derived. A fully opaque source over any destination returns the source; a fully
transparent source returns the destination unchanged (the `blend_over` contract).

#### REQ-P4-LOGIC-004 — Compose an ordered layer stack into a flat RGBA buffer
`traces:` S7 (compositing), Phase-4 capability
A stack compositor takes an ordered list of layers (bottom-to-top z-order, as held in a
`Frame`) and a canvas geometry and returns a **single flat RGBA `PixelBuffer`** of that
geometry. For each pixel, layers are composited from bottom to top: each visible layer's
pixel is blended over the running result using that layer's blend mode and opacity. The
result is deterministic and equals what the canvas must display. Compositing never mutates
the source layer buffers (non-destructive).

#### REQ-P4-LOGIC-005 — Compositing respects per-layer opacity
`traces:` REV-5 (Phase-1 `Layer.opacity`), Phase-4 capability
A layer's `opacity` (0.0..1.0) scales its contribution to the composite: at `1.0` the
layer contributes fully; at `0.0` it contributes nothing; intermediate values scale the
effective alpha of the layer's pixels before the blend. Opacity applies to every blend
mode, not only normal.

#### REQ-P4-LOGIC-006 — A hidden layer contributes nothing
`traces:` REV-5 (Phase-1 `Layer.visible`), Phase-4 capability
A layer with `visible = False` is skipped entirely by the compositor: the flattened result
is identical to the result computed with that layer removed. Toggling a layer's visibility
and re-compositing yields exactly the with/without-layer images.

#### REQ-P4-LOGIC-007 — Compositing respects per-layer blend mode
`traces:` Phase-4 capability, REQ-P4-LOGIC-001..003
Each layer composites using its own `blend_mode`; changing a layer's mode changes only that
layer's contribution to the flattened result and nothing else. A stack of `NORMAL` layers
composites identically to iterated `color.blend_over` (FU-3 equivalence check).

### `logic/document.py` — layer-attributes, layer-management, layer-reversibility

#### REQ-P4-LOGIC-008 — Reversible layer-attribute operations
`traces:` REV-5 (opacity/visible/locked primitives), S7 (command-pattern undo)
Setting a layer's **opacity, visibility, lock state, or blend mode** is a reversible
operation: each exposes a do/undo pair (capturing the minimal prior value) that
`ui/commands.py` wraps in one `QUndoCommand` via the shipped `logic/history.py`
`Command` / `FunctionCommand` pattern. Undo restores exactly the prior attribute value; no
other layer state changes.

#### REQ-P4-LOGIC-009 — Reversible structural operations (add / remove / reorder / duplicate)
`traces:` S7, Phase-4 capability (extends `document.py` add_layer/remove_layer/move_layer)
Adding, removing, reordering, and **duplicating** a layer (or group) are each reversible
single operations: undo of an add removes the added layer; undo of a remove restores the
removed layer at its prior index with its prior contents and attributes; undo of a reorder
restores the prior z-order; undo of a duplicate removes the copy. The existing
`add_layer` / `remove_layer` / `move_layer` are extended (not replaced) to expose the
inverse needed by the command wrapper. The last layer of a frame still cannot be removed
(shipped `DocumentError` invariant).

#### REQ-P4-LOGIC-010 — A locked layer rejects mutation
`traces:` REV-5 (`Layer.locked`), S7, Article VII (defensive)
A layer with `locked = True` rejects any pixel-mutating operation (paint, fill, clear,
mask edit) with a domain error / no-op; unlocking restores editability. Locking is itself
reversible (REQ-P4-LOGIC-008). Visibility and opacity of a locked layer may still change
(they are non-destructive to pixels) — locking guards *pixel* mutation.

#### REQ-P4-LOGIC-011 — Layer groups: composite children then blend as one
`traces:` Phase-4 capability (layer groups), S7
A group node holds an ordered list of child layers (and/or nested groups) and carries its
own opacity / visibility / lock / blend-mode. The compositor **first flattens the group's
children into an intermediate RGBA buffer**, then blends that single buffer over the
running result using the group's own mode and opacity (group-of-normal-children ≠ blowing
the children out individually when the group has non-normal mode/opacity). A hidden group
contributes nothing (its whole subtree is skipped). Group nesting depth is bounded
(CL-6, `MAX_GROUP_NESTING_DEPTH`).

#### REQ-P4-LOGIC-012 — Mask layers: a mask modulates a layer's alpha
`traces:` Phase-4 capability (mask layers), S7
A layer may carry a **mask** — a single-channel (or alpha-of-RGBA) buffer of the same
geometry. When compositing, the layer's per-pixel effective alpha is multiplied by the
mask value at that pixel (mask 0 → pixel fully hidden; mask max → pixel fully shown;
intermediate → proportional). The mask is non-destructive (it never alters the layer's
own pixels) and is itself editable and reversibly attachable/detachable. Compositing a
layer with an all-max mask equals compositing it with no mask.

#### REQ-P4-LOGIC-013 — Reference (non-editable) layers
`traces:` Phase-4 capability (reference layers, Pro-Motion-NG differentiator)
A layer flagged **reference** is composited and visible like any layer but **rejects pixel
mutation** (like a permanent, purpose-declared lock) so it can be traced over. A reference
layer is excluded from the flattened export set only if the user requests (CL-8: reference
layers *do* composite into the on-canvas view by default). The reference flag is reversible.

#### REQ-P4-LOGIC-014 — Smart layers (minimal scope; advanced deferred)
`traces:` Phase-4 capability (smart layers), S6 (extensibility)
A **smart layer** is defined **minimally** (CL-9) as a **non-destructive instance that
mirrors a source layer**: it references a source layer and composites the source's current
pixels (read-only) with its own opacity / visibility / blend mode. Editing the source
updates every smart instance's contribution on the next recomposite; the smart layer's own
pixels are not independently editable. Advanced smart-layer behaviour (live filters,
procedural/transform smart objects, external-file linkage) is **explicitly deferred** to a
later phase (§6, CL-9). Creating/removing a smart layer is reversible.

#### REQ-P4-LOGIC-015 — Bounded layer / group counts (defensive numerics)
`traces:` Article II, Article VII, S12
The layer model enforces named bounds: a maximum layers-per-frame (`MAX_LAYERS_PER_FRAME`)
and a maximum group nesting depth (`MAX_GROUP_NESTING_DEPTH`), both defined once in
`logic/constants.py` (Article II, T4). Exceeding a bound raises a domain error rather than
degrading silently. Default layer opacity is `DEFAULT_LAYER_OPACITY` (= 1.0).

### `ui/` — layer-panel, layer-management, layer-reversibility

#### REQ-P4-UI-001 — Layer panel lists the active frame's layers (top-to-bottom)
`traces:` REV-5, S6
A layers panel lists the active document/frame's layers and groups in **top-to-bottom
z-order** (top of the list = top of the stack), reflecting the `logic/document` tree; the
active/selected layer is single-selected and is the target of paint tools. Groups display
as expandable/collapsible nodes containing their children.

#### REQ-P4-UI-002 — Per-layer opacity slider
`traces:` REV-5 (forward-inherited `Layer.opacity` → Phase-4 UI), Phase-4 capability
Each layer row exposes an **opacity slider** (0–100 %, mapping to `Layer.opacity`
0.0..1.0). Dragging it updates the layer opacity and recomposites the canvas; committing a
change pushes exactly one `QUndoCommand` (REQ-P4-UI-013). The slider reflects the current
opacity when a layer is selected.

#### REQ-P4-UI-003 — Per-layer visibility toggle
`traces:` REV-5 (forward-inherited `Layer.visible` → Phase-4 UI), Phase-4 capability
Each layer row exposes a **visibility toggle**; toggling it flips `Layer.visible`,
recomposites the canvas (a hidden layer disappears from the composite, REQ-P4-LOGIC-006),
and pushes one `QUndoCommand`.

#### REQ-P4-UI-004 — Per-layer lock toggle
`traces:` REV-5 (forward-inherited `Layer.locked` → Phase-4 UI), Phase-4 capability
Each layer row exposes a **lock toggle**; toggling it flips `Layer.locked`. While locked,
paint tools on that layer are no-ops (REQ-P4-LOGIC-010) and the row shows a locked
affordance. Toggling pushes one `QUndoCommand`.

#### REQ-P4-UI-005 — Per-layer blend-mode dropdown
`traces:` REQ-P4-LOGIC-001, Phase-4 capability
Each layer row exposes a **blend-mode dropdown** listing the twelve `BlendMode` members
(REQ-P4-LOGIC-001) with translatable labels. Selecting a mode sets `Layer.blend_mode`,
recomposites the canvas, and pushes one `QUndoCommand`. The dropdown reflects the current
mode.

#### REQ-P4-UI-006 — Drag-to-reorder layers
`traces:` REQ-P4-LOGIC-009, S6
The user can **drag a layer row** to a new position; on drop the layer's z-order changes
(mapping to `Document.move_layer`), the canvas recomposites in the new order
(REQ-P4-LOGIC-007), and one `QUndoCommand` is pushed. Dragging into/out of a group node
re-parents the layer.

#### REQ-P4-UI-007 — Add / remove / duplicate layer actions
`traces:` REQ-P4-LOGIC-009
The panel exposes **add**, **remove**, and **duplicate** actions. Add inserts a new empty
layer above the active layer; remove deletes the active layer (refused on the last layer of
a frame); duplicate inserts a pixel-for-pixel copy with copied attributes above the source.
Each is one `QUndoCommand`.

#### REQ-P4-UI-008 — Group / ungroup actions
`traces:` REQ-P4-LOGIC-011
The panel exposes **group** (wrap the selected layers in a new group node) and **ungroup**
(dissolve a group, promoting its children into the parent at the group's position)
actions. Grouping preserves child order and pixels; the canvas recomposites (a group with
default attributes composites identically to its ungrouped children). Each is one
`QUndoCommand`.

#### REQ-P4-UI-009 — Mask affordance (attach / edit / remove)
`traces:` REQ-P4-LOGIC-012
Each layer row offers a **mask affordance**: add a mask, select it to paint into it
(painting edits the mask buffer, not the layer pixels), and remove it. While a mask is the
active edit target, paint tools modulate the mask; the canvas recomposites with the mask
modulating the layer alpha (REQ-P4-LOGIC-012). Attach/remove are each one `QUndoCommand`.

#### REQ-P4-UI-010 — Reference-layer affordance
`traces:` REQ-P4-LOGIC-013
The panel lets the user mark a layer as **reference** (and clear the flag). A reference
layer shows a distinct affordance, remains visible in the composite, and rejects paint
(paint tools are no-ops on it, mirroring REQ-P4-LOGIC-013). Toggling the flag is one
`QUndoCommand`.

#### REQ-P4-UI-011 — Smart-layer affordance (minimal)
`traces:` REQ-P4-LOGIC-014
The panel lets the user create a **smart layer** from a selected source layer (minimal
scope, CL-9): the smart layer appears as a distinct row that mirrors the source; editing
the source updates the smart layer's composite contribution; the smart layer's own pixels
are not directly editable. Creating/removing it is one `QUndoCommand`. Advanced smart
behaviours are not offered (deferred, §6).

### `ui/` — layer-compositing, multi-canvas

#### REQ-P4-UI-012 — The canvas renders the composited layer stack
`traces:` S1, S7, REQ-P4-LOGIC-004
The canvas scene renders the **flattened composite** of the active frame's layer stack
(via the `logic/blend` compositor), not just the active layer's buffer (the Phase-1
single-layer behaviour is superseded). An edit to any layer, or a change to any layer
attribute/order/group/mask, updates the on-canvas composite for the affected region. The
resident per-layer buffers are never culled (only Qt rendering is, F7 / Article VI §3).

#### REQ-P4-UI-013 — Every layer operation is exactly one undoable command
`traces:` S7, C1, F1, REQ-P4-LOGIC-008, -009
Every layer operation surfaced by the panel — set opacity / visibility / lock /
blend-mode, add / remove / duplicate / reorder, group / ungroup, attach / remove mask,
set reference / smart — is pushed as **exactly one `QUndoCommand`** onto the active
document's `QUndoStack`, delegating to the Qt-free reversible op in
`logic/document` / `logic/history` (Article I: `ui/commands.py` is the only Qt file outside
`ui/`). Undo of any layer op restores the exact prior tree state.

#### REQ-P4-UI-014 — Multiple canvases / artboards as isolated tabs
`traces:` S1, S6, S7 (extends Phase-1 REQ-P1-UI-020 document tabs)
Multiple documents / artboards open as tabs (extending the Phase-1 tab system); switching a
tab makes that canvas active (its layer tree, palette, `QUndoStack`, composite, and scene
rect become current). Layer operations, undo state, and compositing in one canvas **never**
affect another (state isolation). A layer op undone in tab A does not change tab B.

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P4-UI-015 — Performance: 8K multi-layer recomposite within the frame budget *(NFR, Article VI)*
`traces:` S1, S12, F2, F7, Article VI, DEP-2
Rendering and recompositing a multi-layer 8K stack (7680 × 4320) holds
`FPS_TARGET = 60`, i.e. per-frame time ≤ `FRAME_BUDGET_MS = 16`. A single-layer edit must
recomposite only the **affected (dirty) region**, not the whole stack over the whole canvas
(dirty-rect recomposite). This budget is **verified headless by AGT-10**
(`perf_profile` / `frame-profile`); an over-budget measurement yields an AGT-10
optimisation directive (dirty-rect recomposite scope, cached group buffers, viewport
tuning), **never** a relaxation of the budget. The concrete recomposite strategy is
AGT-10 plan-level (DEP-2), out of this spec.

#### REQ-P4-UI-016 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive layer-panel control (row selection, opacity slider, visibility/lock
toggles, blend-mode dropdown, add/remove/duplicate/group/ungroup/mask/reference/smart
actions) exposes an accessible name and, where non-obvious, an accessible description; is
reachable and operable by keyboard (logical tab order + shortcuts); and shows a visible
focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P4-UI-017 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The layer panel and the composited canvas render correctly in both light and dark themes;
colours (including the panel's selection/lock/reference affordances) are defined once by
role, never hard-coded per widget. Both themes are test-verified (AGT-06 pytest-qt, each
acceptance test runnable under both).

#### REQ-P4-UI-018 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 4 (blend-mode labels, layer default names, panel
tooltips, action labels, mask/reference/smart affordance text) is wrapped in
`tr()` / `translate()`; none is a bare literal. Hand-built widgets re-set text on
`QEvent.LanguageChange`. Verified by `string_audit_check` (AGT-07); an unwrapped string is
a blocking finding.

## 6. Non-goals (explicit; deferred)

- **Advanced smart layers** — live filter/adjustment layers, procedural or transform smart
  objects, external-file-linked smart objects. → **deferred** to a later phase (CL-9);
  Phase 4 ships only the minimal non-destructive source-mirroring instance
  (REQ-P4-LOGIC-014). This is the only genuine scope-bounding of the prompt; it is resolved
  by *scoping down*, not by suspending (see §12).
- **Per-frame animation compositing over time** (timeline, onion skin, playback) → **Phase
  5** — Phase 4 gives Phase 5 the single-frame stack compositor it will call per frame.
- **Flattened-image export / sprite-sheet / GIF** → **Phase 7** (the compositor produces
  the flat buffer those consume; export UI is not here).
- **GPU render-pipeline strategy** (dirty-rect recomposite design, cached group buffers,
  QOpenGL viewport, BSP tuning) — AGT-10 **plan-level** directive (DEP-2), not a spec
  requirement here (this spec states only the 16 ms budget, REQ-P4-UI-015).
- **The blend-mode formulas themselves** — grounded by The Researcher
  (`docs/research-blend-modes.md`, DEP-1); this spec fixes the *set of modes* and the
  *acceptance* (each matches its grounded formula on known values), not the maths.
- No plan/tasks (AGT-01), no logic/UI/test code (AGT-03/05/04/06), no new technology
  (fixed by S8).

## 7. Dependencies & assumptions

- **Upstream logic substrate is shipped** (`specs/phase-1-core-engine/`): `Document`
  (`frames → layers → buffer`, `add_layer`/`remove_layer`/`move_layer`,
  `resize_canvas`), `Layer` (already carries `opacity`/`visible`/`locked` — **REV-5**),
  `color.blend_over` (**FU-3** — normal alpha compositing, reserved for this phase),
  `pixel_buffer.blit(..., blend=True)`, `history` (`Command`, `FunctionCommand`,
  `PixelEdit`, `History`, `record_edit`), `constants.*`. Phase 4 **extends** this tree; it
  must not re-implement compositing maths outside `logic/` (Article I).
- Layer ops reuse the shipped `history.FunctionCommand` / `PixelEdit` do/undo pattern so
  `ui/commands.py` stays a thin Qt wrapper (REQ-P4-UI-013, Article I §2).
- The active colour / active layer are held by the window; paint tools target the
  **active layer** (or its active mask), then the canvas recomposites.

## 8. Behaviours flagged for AGT-01 / AGT-10 / DATA (not blockers)

- **DEP-1 (Researcher, formulas).** `docs/research-blend-modes.md` grounds the exact
  per-mode formulas for REQ-P4-LOGIC-002. It is **not yet present**; AGT-01's `sdd-plan`
  must not invent the maths — it consumes the Researcher's findings. The *set* of 12 modes
  and the acceptance shape (match-on-known-values) are fixed here regardless.
- **DEP-2 (AGT-10, plan).** The dirty-rect recomposite strategy that makes REQ-P4-UI-015
  pass — recomposite only the edited region, cache flattened group buffers, viewport
  culling — is AGT-10's render-strategy output. Compositing an 8K multi-layer stack fully
  on every edit will blow `FRAME_BUDGET_MS`; a **dirty-rect recomposite is very likely
  required** (flagged for the plan). This spec fixes only the budget.
- **DEP-3 (AGT-01 / DATA slice).** Persisting the new layer model to `.pixproj` — layer
  `blend_mode`, group nodes, masks, reference/smart flags — extends `data/project_io.py`
  and needs **`REQ-P4-DATA-*` IDs allocated at plan/placement time** (this spec is scoped
  to `REQ-P4-LOGIC-*` / `REQ-P4-UI-*` per the prompt). The ROADMAP "Done means"
  (opacity/visibility/lock + groups/masks round-trip through `.pixproj`) makes this a
  required companion slice. Validated/defensive load per Article VII.
- **BF-1 (AGT-01, plan).** Whether the composite is drawn as one whole-canvas
  `QGraphicsPixmapItem` refreshed per dirty-rect vs. tiled composite items is a HOW
  decision for `sdd-plan`; the spec requires only that the canvas shows the flattened
  stack (REQ-P4-UI-012) within budget (REQ-P4-UI-015).
- **BF-2 (AGT-01, Article II).** New tuning values (default opacity, max layers, max group
  depth) must resolve to named constants in `logic/constants.py` — see §9 / T4. The
  `BlendMode` enum lives in `logic/blend.py` (an enumerated vocabulary, not a numeric tuning
  value); its default member `NORMAL` is the S12-style default (CL-2).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/blend.py` and the `document.py` extensions are
  pure Python, zero Qt; the layer panel and canvas compositing live in `ui/`; the only Qt
  file outside `ui/` remains `ui/commands.py` (layer-op command wrappers, REQ-P4-UI-013).
  Enforced by `check_layering` / `check_cycles`.
- **Article II (numerics):** new tuning values (`DEFAULT_LAYER_OPACITY`,
  `MAX_LAYERS_PER_FRAME`, `MAX_GROUP_NESTING_DEPTH`) go in `logic/constants.py` (T4); no
  literals in `ui/`/`logic/`. Blend-mode formula constants (e.g. `/255`) are intrinsic maths
  local to `blend.py`, not tuning values (parallels the Phase-3 ΔE00/Bayer intrinsic-local
  precedent).
- **Article IV (testing):** each blend mode, the compositor invariants, reversibility, mask
  modulation, group composite-then-blend, and multi-canvas isolation each get a scenario →
  one pytest / Hypothesis test (logic) or pytest-qt test (UI), both themes for UI.
- **Article V (UX):** REQ-P4-UI-016/-017/-018 make a11y + both themes + full
  translatability blocking gates for the layer panel.
- **Article VI (performance):** REQ-P4-UI-015 binds the 16 ms budget for 8K multi-layer
  recomposite; the resident buffers are never culled.
- **Article VII (security):** locked/reference guards and bounded layer/group counts
  (REQ-P4-LOGIC-010, -013, -015) are defensive; `.pixproj` layer-model load stays validated
  (DEP-3).
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited
  primitive (FU-3, REV-5); forward matrix in `traceability.md`.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with
sensible defaults grounded in the dossier and mainstream pixel-art / image-editor norms
(Aseprite / Photoshop / Pixelorama). Each is a **category-1 decision** (A2-D2 Branch B).
**No open clarification blocks planning.**

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Which blend modes? | The **twelve** — NORMAL plus the eleven non-normal separable W3C modes: normal, multiply, screen, overlay, darken, lighten, colour-dodge, colour-burn, hard-light, soft-light, difference, exclusion. | Prompt + ROADMAP Phase-4 bullet; the mainstream Aseprite/Photoshop core set. |
| **CL-2** | Default blend mode & opacity? | **`NORMAL`**, opacity **1.0** (`DEFAULT_LAYER_OPACITY`). | Universal editor default; matches shipped `Layer(opacity=1.0)`. |
| **CL-3** | Layer list order in the panel? | **Top-to-bottom = top-of-stack first** (topmost layer at the top of the list). | Aseprite/Photoshop/Krita convention. |
| **CL-4** | Compositing z-order in logic? | Composite **bottom → top** over the running result. | Standard painter's-algorithm order; matches `color.blend_over(src=upper, dst=lower)`. |
| **CL-5** | Opacity slider granularity? | **0–100 %** integer, mapped to `Layer.opacity` 0.0..1.0. | Editor norm; avoids exposing floats in the UI. |
| **CL-6** | Group nesting depth? | Bounded by **`MAX_GROUP_NESTING_DEPTH`** (default 8), error past it. | Defensive numeric (Art. II/VII); 8 is generous for pixel-art work. |
| **CL-7** | Max layers per frame? | Bounded by **`MAX_LAYERS_PER_FRAME`** (default 256), error past it. | Defensive bound; generous for hand-drawn pixel art. |
| **CL-8** | Do reference layers composite on-canvas? | **Yes** by default — they are visible for tracing; excluded from a *flattened export* only if the user asks (export is Phase 7). | Reference layers exist to be seen while drawing (Pro Motion NG). |
| **CL-9** | Smart-layer scope? | **Minimal**: a non-destructive instance mirroring a source layer (read-only pixels, own opacity/visibility/blend). Advanced (filters/procedural/transform/external-link) **deferred** to a later phase. | Prompt directive to bound it; parity-critical modes (blend/group/mask) ship first, advanced smart is a differentiator that can follow. |
| **CL-10** | Mask channel model? | A same-geometry **alpha/greyscale mask buffer**; mask value multiplies layer alpha (0 hidden … max shown). | Photoshop/Krita mask semantics; reuses `PixelBuffer`. |
| **CL-11** | Locked-layer semantics? | Lock guards **pixel mutation** only; opacity/visibility/mode/order still changeable (non-destructive to pixels). | Aseprite lock behaviour. |
| **CL-12** | Group with non-normal mode? | Group **composites children first**, then blends the group's flat buffer with the group's mode/opacity (isolated group). | Photoshop "pass-through vs. normal" — default to *normal/isolated* group (simplest deterministic model; pass-through deferrable). |
| **CL-13** | Recomposite scope on an edit? | Recomposite only the **dirty region** (spec fixes the requirement; the strategy is AGT-10, DEP-2). | Article VI budget at 8K; full recomposite per edit is infeasible. |
| **CL-14** | New layer default name / position? | New layer inserted **above the active layer**, named `Layer` (translatable, auto-numbered). | Editor norm; consistent with shipped `add_layer` default name. |
| **CL-15** | Multi-canvas isolation? | Each tab owns its **own layer tree + `QUndoStack` + composite**; no cross-tab state. | Extends Phase-1 REQ-P1-UI-020; prevents cross-contamination (ROADMAP "Done means"). |

**SUSPEND / escalate:** *none.* The one genuine scope risk — "smart layers" being
underspecified — is resolved by **scoping to a minimal, bounded definition and deferring
the advanced behaviour** (CL-9 / REQ-P4-LOGIC-014 / §6), which is a category-1 decision, not
a blocker. The blend-mode formulas are a named upstream dependency (DEP-1), not an open
ambiguity: the mode set and acceptance shape are fixed regardless of the maths.

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic scenarios are for **AGT-04** (pytest +
Hypothesis, headless); UI scenarios are for **AGT-06** (pytest-qt,
`QT_QPA_PLATFORM=offscreen`), **each run under BOTH light and dark themes** (REQ-P4-UI-017,
expressed once as a global rule). Scenario ids map to `traceability.md`; tests are authored
later (`pending`).

> Global rule (UI scenarios): *Given the app runs headless
> (`QT_QPA_PLATFORM=offscreen`) — the scenario is executed and asserted identically under
> the light theme and the dark theme.*

### Feature: Blend modes (REQ-P4-LOGIC-001..003, -007)
```gherkin
Scenario: SC-L001-1 the BlendMode enum has exactly the twelve modes
  Given logic/blend.BlendMode
  Then it enumerates NORMAL, MULTIPLY, SCREEN, OVERLAY, DARKEN, LIGHTEN, COLOR_DODGE, COLOR_BURN, HARD_LIGHT, SOFT_LIGHT, DIFFERENCE, EXCLUSION and no others

Scenario Outline: SC-L002-1 each blend mode matches the grounded formula on known values
  Given a source channel <s> and a destination channel <d>
  When the <mode> blend function is applied
  Then the result equals the grounded reference value <expected> from docs/research-blend-modes.md
  Examples: | mode | s | d | expected |
            | MULTIPLY | 128 | 128 | 64 |
            | MULTIPLY | 255 | 200 | 200 |
            | MULTIPLY | 0 | 200 | 0 |
            | SCREEN | 0 | 200 | 200 |
            | SCREEN | 255 | 50 | 255 |
            | DARKEN | 100 | 200 | 100 |
            | LIGHTEN | 100 | 200 | 200 |
            | DIFFERENCE | 200 | 50 | 150 |
  # exact expected values are fixed by DEP-1; table above is illustrative of the shape

Scenario: SC-L003-1 NORMAL mode delegates to color.blend_over
  Given a source RGBA over a destination RGBA
  When the NORMAL blend mode composites them
  Then the result equals color.blend_over(src, dst) exactly

Scenario: SC-L002-2 blending is deterministic (property)
  Given any two in-range RGBA values and any blend mode (Hypothesis)
  When the blend is applied twice
  Then both applications return identical output

Scenario: SC-L007-1 a stack of NORMAL layers equals iterated blend_over (property)
  Given N layers all in NORMAL mode at full opacity (Hypothesis)
  When the stack is composited
  Then the flat result equals folding color.blend_over bottom-to-top
```

### Feature: Stack compositing (REQ-P4-LOGIC-004..007)
```gherkin
Scenario: SC-L004-1 compositing flattens an ordered stack into one RGBA buffer
  Given a bottom RED layer and a top half-alpha BLUE layer
  When the stack is composited
  Then the flat buffer equals BLUE-over-RED per the normal blend, of the canvas geometry

Scenario: SC-L004-2 compositing never mutates the source layer buffers
  Given a two-layer stack
  When it is composited
  Then each source layer buffer is byte-for-byte unchanged

Scenario: SC-L005-1 layer opacity scales the layer contribution
  Given a top opaque WHITE layer over a BLACK layer
  When the top layer opacity is 0.5 and the stack is composited
  Then the composited pixel is the 50%-blended grey (opacity applied to effective alpha)

Scenario: SC-L006-1 a hidden layer contributes nothing
  Given a stack whose top layer is set visible=False
  When it is composited
  Then the flat result is identical to compositing the stack with that layer removed

Scenario: SC-L007-2 changing one layer's blend mode changes only its contribution
  Given a three-layer stack
  When the middle layer's blend mode changes from NORMAL to MULTIPLY
  Then only pixels influenced by the middle layer differ; layers above/below are unaffected in isolation

Scenario: SC-L004-3 z-order is respected
  Given two opaque layers A (bottom) and B (top)
  When composited, the visible pixel is B; when reordered so A is top, the visible pixel is A
```

### Feature: Reversible layer operations (REQ-P4-LOGIC-008..010)
```gherkin
Scenario: SC-L008-1 setting opacity is reversible
  Given a layer at opacity 1.0
  When set_opacity(0.4) is applied as a command and then undone
  Then opacity is 0.4 after do and exactly 1.0 after undo

Scenario: SC-L008-2 setting visibility / lock / blend-mode is reversible
  Given a layer with visible=True, locked=False, mode=NORMAL
  When each attribute is changed via a command and undone
  Then each attribute returns to its exact prior value on undo

Scenario: SC-L009-1 add layer is reversible
  Given a frame with 2 layers
  When a layer is added via a command and undone
  Then the frame has 3 layers after do and exactly the original 2 after undo

Scenario: SC-L009-2 remove layer is reversible (restores contents and index)
  Given a 3-layer frame with a painted middle layer
  When the middle layer is removed via a command and undone
  Then the layer returns at its prior index with identical pixels and attributes

Scenario: SC-L009-3 reorder and duplicate are reversible
  Given a multi-layer frame
  When a reorder and a duplicate are each applied as a command and undone
  Then the z-order and layer count return exactly to the prior state

Scenario: SC-L010-1 a locked layer rejects pixel mutation
  Given a locked layer
  When a paint/fill/clear op targets it
  Then the layer pixels are unchanged (domain error or no-op) and unlocking restores editability

Scenario: SC-L009-4 the last layer of a frame cannot be removed
  Given a frame with one layer
  When a remove is attempted
  Then it raises DocumentError and the frame still has one layer
```

### Feature: Groups, masks, reference, smart (REQ-P4-LOGIC-011..014)
```gherkin
Scenario: SC-L011-1 a group composites its children then blends as one
  Given a group of two children at group opacity 0.5 and group mode NORMAL
  When the stack is composited
  Then the children are flattened first, then that flat buffer is blended at 0.5 (not each child at 0.5)

Scenario: SC-L011-2 a hidden group contributes nothing
  Given a group set visible=False
  When composited
  Then the result equals compositing with the whole group subtree removed

Scenario: SC-L011-3 group nesting depth is bounded
  Given nesting that would exceed MAX_GROUP_NESTING_DEPTH
  When the nesting is attempted
  Then a domain error is raised

Scenario: SC-L012-1 a mask modulates the layer alpha
  Given a fully opaque layer with a mask that is max on the left half and zero on the right half
  When composited
  Then the left half shows the layer and the right half shows the layer below (alpha modulated by the mask)

Scenario: SC-L012-2 an all-max mask equals no mask
  Given a layer with an all-max mask
  When composited
  Then the result equals compositing that layer with no mask

Scenario: SC-L012-3 editing a mask does not alter the layer pixels
  Given a masked layer
  When the mask buffer is edited
  Then the layer's own pixels are byte-for-byte unchanged

Scenario: SC-L013-1 a reference layer composites but rejects pixel mutation
  Given a reference layer
  When it is composited and then a paint op targets it
  Then it appears in the composite and its pixels are unchanged (no-op)

Scenario: SC-L014-1 a smart layer mirrors its source non-destructively
  Given a smart layer instancing a source layer
  When the source layer is edited and the stack is recomposited
  Then the smart layer's contribution reflects the source edit and the smart layer holds no independently editable pixels
```

### Feature: Bounds & defaults (REQ-P4-LOGIC-015)
```gherkin
Scenario: SC-L015-1 layer count is bounded
  Given a frame at MAX_LAYERS_PER_FRAME layers
  When another add is attempted
  Then a domain error is raised

Scenario: SC-L015-2 a new layer defaults to DEFAULT_LAYER_OPACITY and NORMAL
  Given a new layer
  Then its opacity equals DEFAULT_LAYER_OPACITY (1.0) and its blend mode is NORMAL
```

### Feature: Layer panel controls (REQ-P4-UI-001..008)
```gherkin
Scenario: SC-UI-001-1 the panel lists layers top-to-bottom in z-order
  Given a frame with layers [Background(bottom), Sketch, Ink(top)]
  When the layer panel is shown
  Then the rows read top-to-bottom Ink, Sketch, Background

Scenario: SC-UI-002-1 the opacity slider sets layer opacity as one command
  Given a selected layer at 100%
  When the user drags its opacity slider to 40% and releases
  Then Layer.opacity == 0.4, the canvas recomposites, and exactly one command is on the stack

Scenario: SC-UI-003-1 the visibility toggle hides the layer from the composite
  Given a visible top layer contributing to the composite
  When the user toggles its visibility off
  Then the layer disappears from the composited canvas and one command is pushed

Scenario: SC-UI-004-1 the lock toggle makes paint a no-op
  Given a selected layer
  When the user toggles lock on and then paints on the canvas
  Then no pixel changes on that layer and one lock command was pushed

Scenario: SC-UI-005-1 the blend-mode dropdown lists 12 modes and sets the mode
  Given a selected layer's blend-mode dropdown
  Then it offers exactly the 12 BlendMode members with translatable labels
  And selecting MULTIPLY sets Layer.blend_mode to MULTIPLY, recomposites, and pushes one command

Scenario: SC-UI-006-1 drag-reorder changes z-order and recomposites
  Given layers [A(bottom), B(top)] with A and B opaque
  When the user drags A above B
  Then the composited canvas now shows A on top and one command is pushed

Scenario: SC-UI-007-1 add / remove / duplicate each push one command
  Given a 2-layer frame
  When the user adds, then duplicates, then removes a layer
  Then each action changes the tree and pushes exactly one command; removing the last layer is refused

Scenario: SC-UI-008-1 group / ungroup preserve children and are reversible
  Given two selected layers
  When the user groups them and then ungroups
  Then grouping wraps them in a group node (composite unchanged with default attrs) and ungroup restores them; each is one command
```

### Feature: Mask / reference / smart affordances (REQ-P4-UI-009..011)
```gherkin
Scenario: SC-UI-009-1 attaching a mask and painting it modulates the composite
  Given a selected layer
  When the user adds a mask, selects it, and paints zero into the right half
  Then the composite shows the layer masked on the right; the layer pixels are unchanged; attach is one command

Scenario: SC-UI-010-1 a reference layer is visible but rejects paint
  Given the user marks a layer as reference
  When the user tries to paint on it
  Then it remains visible in the composite, no pixel changes, and the flag toggle was one command

Scenario: SC-UI-011-1 a smart layer mirrors its source in the panel
  Given the user creates a smart layer from a source layer
  When the source is edited
  Then the smart layer's composite contribution updates and its own pixels are not directly editable; creation is one command
```

### Feature: Canvas compositing & multi-canvas (REQ-P4-UI-012..014)
```gherkin
Scenario: SC-UI-012-1 the canvas renders the composited stack, not one layer
  Given a document with two visible layers (RED bottom, half-alpha BLUE top)
  When the canvas renders
  Then it shows the composited BLUE-over-RED result, not just the active layer

Scenario: SC-UI-012-2 editing any layer updates the on-canvas composite
  Given a multi-layer canvas
  When the user paints on the active layer
  Then the composited canvas updates in the edited region

Scenario: SC-UI-013-1 every layer op is exactly one undoable command
  Given the layer panel
  When any layer op (opacity/visibility/lock/mode/add/remove/duplicate/reorder/group/ungroup/mask/reference/smart) is performed
  Then exactly one QUndoCommand is pushed and undo restores the exact prior tree state

Scenario: SC-UI-014-1 multiple canvases open as isolated tabs
  Given two documents A and B open in tabs
  When a layer op is performed and undone in A
  Then B's layer tree, composite and undo stack are unaffected

Scenario: SC-UI-014-2 switching tabs switches the active layer context
  Given tabs A and B
  When the user selects tab B
  Then B's layer tree, palette, QUndoStack and composite become the active context
```

### Feature: Performance / a11y / theming / i18n (REQ-P4-UI-015..018) — NFR
```gherkin
Scenario: SC-UI-015-1 an 8K multi-layer edit recomposites within the frame budget
  Given a 7680x4320 document with several layers
  When a single-pixel paint triggers a recomposite
  Then the measured per-frame time is <= FRAME_BUDGET_MS (16 ms) recompositing only the dirty region
  # Measured headless by AGT-10 (perf_profile / frame-profile); over-budget yields an
  # AGT-10 dirty-rect optimisation directive, not a budget relaxation.

Scenario: SC-UI-016-1 layer-panel controls expose accessible names and keyboard focus
  Given the layer panel is shown
  When each control (row, sliders, toggles, dropdown, actions) is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-017-1 the layer panel and composite render correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the panel and composited canvas render legibly with role-based colours (no hard-coded per-widget colour)

Scenario: SC-UI-018-1 no Phase-4 user-visible string is a bare literal
  Given the Phase-4 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (blend-mode labels, layer names, tooltips, actions)
```

---

## 12. Exit / status

- Forward spec authored for Phase 4 — Layer & Canvas System. **33 REQ-IDs**:
  **15 LOGIC** (`REQ-P4-LOGIC-001..015`) + **18 UI** (`REQ-P4-UI-001..018`), each traced to
  an S-id / F-finding / forward-inherited primitive (FU-3 `color.blend_over`→normal blend;
  REV-5 `Layer.opacity/visible/locked`→Phase-4 UI) per Article X.
- **15 clarification defaults** recorded (§10), each grounded in the dossier + mainstream
  editor norms; **no open clarification blocks planning**.
- **No SUSPEND blocker.** The one scope risk ("smart layers") is bounded by a **minimal
  scope + deferral of advanced behaviour** (CL-9 / REQ-P4-LOGIC-014), a category-1 decision.
- **New constants flagged for `logic/constants.py`** (Article II, T4): `DEFAULT_LAYER_OPACITY`
  (1.0), `MAX_LAYERS_PER_FRAME` (256), `MAX_GROUP_NESTING_DEPTH` (8). The `BlendMode` enum
  lives in `logic/blend.py` (vocabulary, not tuning); blend formula constants are
  intrinsic-local to `blend.py`.
- **Dependencies flagged:** DEP-1 (Researcher blend-mode formulas — REQ-P4-LOGIC-002), DEP-2
  (AGT-10 dirty-rect recomposite — REQ-P4-UI-015), DEP-3 (`.pixproj` DATA slice —
  `REQ-P4-DATA-*` to be allocated by AGT-01).
- Acceptance scenarios cover every functional and NFR requirement; forward matrix in
  `traceability.md`. Tests authored later by AGT-04 (logic) / AGT-06 (UI), `pending`.
- **STATUS: COMPLETED.**
