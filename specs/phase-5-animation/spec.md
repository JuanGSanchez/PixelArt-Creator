# Specification — Phase 5: Animation System

| Field | Value |
| --- | --- |
| Feature | `phase-5-animation` |
| Author | AGT-02 (Requirements) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no `logic/animation.py`, timeline UI, or frame-tag persistence exists yet; the `Frame` tree + `Frame.duration_ms` + `blend.composite_stack` + `.pixproj` v2 frame/layer serialisation are **already shipped** and are reused, not re-authored. This spec defines the WHAT/WHY Phase 5 realises. |
| REQ-ID range | `REQ-P5-LOGIC-001..014`, `REQ-P5-UI-001..019`, `REQ-P5-DATA-001..003` (from ROADMAP reserved `REQ-P5-LOGIC-*` / `REQ-P5-UI-*`; `REQ-P5-DATA-*` newly required because frame **tags** extend `.pixproj` — see §7/DEP-2) |
| Layer scope | `pixelart_creator/logic/` (new `animation.py`; extend `document.py` with reversible frame ops + frame-tag storage; new constants) + `pixelart_creator/ui/` (timeline panel, playback controls, onion-skin, frame-tags, per-frame duration) + `pixelart_creator/data/` (`project_io.py` frame-tag persistence). |
| Binds to (upstream, **shipped** — REUSED) | Phase 1 `logic/document.py` (`Document → frames → layers → PixelBuffer`; **`Frame.duration_ms` already present**; `add_frame`/`remove_frame` direct mutators — the **FR-1** primitive), `logic/constants.py` `DEFAULT_FRAME_DURATION_MS` (**the FR-2 primitive**, re-exported by `document.py`), Phase 4 `logic/blend.composite_stack` (renders one frame's layer stack — the **CO-4** primitive reserved for per-frame animation render), `logic/history.py` (`Command`, `FunctionCommand`, `History`), `data/project_io.py` v2 (**already serialises frames + layers + `duration_ms`** — the **IO-2** primitive) |
| Depends on (external) | The Researcher — `docs/research-phase5-animation.md` (grounds onion-skin internals, frame-tag schema, timeline-model conventions, playback timing). **Not yet present (concurrent)** — see DEP-1. This spec fixes the WHAT/acceptance and records Aseprite-parity defaults; the HOW is AGT-01/AGT-03. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The Phase-1 document tree already models `Document → frames → layers → PixelBuffer`, and
**each `Frame` already carries a `duration_ms`** (default `DEFAULT_FRAME_DURATION_MS`). Phase 4
gave the platform `blend.composite_stack`, which flattens one frame's layer stack into a single
RGBA buffer. What is missing is the **animation system** that turns a list of frames into a
*timeline*: reversible frame management (add / remove / reorder / duplicate), a per-frame
duration editor, a playback engine (loop / once / ping-pong / reverse), onion skinning, frame
**tags** that define independent named animations, a timeline UI over the frame × layer grid,
and persistence of tags in `.pixproj`.

Phase 5 is the "production animation" milestone. Timeline + tags + onion skinning reach
**Aseprite** parity; **multiple named animations per file** (frame tags with per-tag playback
modes) is the **Pro Motion NG-level differentiator** over Pixelorama. It builds strictly on the
shipped substrate — frames pre-date the timeline, `composite_stack` renders each frame, and
`.pixproj` v2 already round-trips frames + per-frame durations. No pixel/compositing maths is
re-implemented; the playback **timing driver** (a Qt timer) is the only new Qt surface and lives
in `ui/` (Article I).

This document specifies WHAT the animation system must do and WHY, technology-neutral at the
requirement level. The HOW — the exact onion-tint blend, the timeline widget model, the dirty-rect
recomposite that keeps scrubbing/playback within budget (AGT-10), the frame-tag JSON schema
version (AGT-01) — is downstream. It records the clarification defaults chosen under the owner's
autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**

- **`logic/animation.py` (new, Qt-free).** A `PlaybackMode` enumeration (**LOOP, ONCE,
  PING_PONG, REVERSE**); a **pure, deterministic frame-sequencing engine** that, given a frame
  count / range, a current position, and a mode, yields the next frame index (and the frame's
  `duration_ms`); an **onion-skin overlay** computation (N previous / M next composited frames,
  tinted and at reduced opacity); a **`FrameTag`** model (name + inclusive `[from, to]` frame
  range + its own `PlaybackMode` + optional repeat count); and **named-animation playback** that
  runs a tag's sub-range under the tag's mode.
- **`logic/document.py` (extend, Qt-free).** Frame operations formalised as **reversible**
  do/undo commands usable by `ui/commands.py`: **add / remove / reorder / duplicate** a frame and
  **set a frame's duration**. `remove` still refuses the last frame. A **frame-tags collection**
  stored on the `Document` with reversible **create / edit / delete**; tag ranges are kept valid
  when frames are added or removed. (Today `add_frame` / `remove_frame` exist only as
  **direct, non-reversible** mutators and there is **no reorder or duplicate** — this phase adds
  the reversible command wrappers and the two missing ops.)
- **`logic/constants.py` (extend).** New named bounds/defaults: `MAX_FRAMES`,
  `MAX_ONION_SKIN_FRAMES`, `DEFAULT_ONION_PREV`, `DEFAULT_ONION_NEXT`, onion tint colours
  (`ONION_TINT_PREV`, `ONION_TINT_NEXT`) and `ONION_SKIN_OPACITY` (Article II). `DEFAULT_FRAME_DURATION_MS`
  is **reused** (already present, FR-2).
- **`ui/` timeline panel.** A timeline showing **frames (columns) × layers (rows)** for the
  active document; frame **selection / scrub** (clicking or dragging along the timeline sets the
  canvas-displayed frame); per-frame **duration** editing; add / remove / reorder (drag) /
  duplicate frame actions — each one `QUndoCommand`.
- **`ui/` playback controls.** Play / pause / stop; a **playback-mode** selector
  (loop / once / ping-pong / reverse); playback advances the displayed frame honouring each
  frame's `duration_ms`.
- **`ui/` onion skinning.** A toggle; previous/next **count** controls and a **tint** scheme
  (configurable); the onion overlay renders behind the active frame while editing.
- **`ui/` frame tags.** Create / edit / delete a named tag over a frame range with a per-tag
  playback mode; select a tag and **play that named animation**.
- **`data/project_io.py` (extend).** Persist frame **tags** (name / range / mode / repeat) in
  `.pixproj`; frames + per-frame `duration_ms` **already round-trip (v2, reused)**. Defensive,
  validated load; back-compat read of tagless projects.

**Out of scope (this phase):** see §6 Non-goals. Notably: **cel-level layer × frame linking**
(a single layer's identity/content shared across frames as linked cels) — **deferred** (CL-9);
Phase 5 uses the shipped **independent per-frame layer stacks**. A **dedicated real-size motion
preview window** (PureRef-style dockable) → **Phase 9**; Phase 5 previews motion by playing back
**on the canvas**. GIF / sprite-sheet export of the animation → **Phase 7**. The dirty-rect
recomposite **strategy** → AGT-10 plan-level. No plan/tasks/code (AGT-01/03/05); no new
technology (fixed by S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Animator / manage-frames).** As an animator, I want to **add, remove, reorder and
  duplicate frames**, each undoable in one step, so I can build and edit a sequence
  non-destructively. → REQ-P5-LOGIC-004, -005, -006, -007, REQ-P5-UI-003, -004, -005, -006,
  -015 · `frame-management` · P5
- **US-2 (Animator / timing).** As an animator, I want to **set each frame's display duration**
  so I can control the pace of the animation. → REQ-P5-LOGIC-008, REQ-P5-UI-007 · `frame-timing` · P5
- **US-3 (Animator / playback).** As an animator, I want to **play, pause and stop** the
  animation and choose **loop / once / ping-pong / reverse** so I can preview motion. →
  REQ-P5-LOGIC-001, -002, -003, REQ-P5-UI-008, -009, -010 · `playback` · P5
- **US-4 (Animator / onion-skin).** As an animator, I want to **toggle onion skinning** and set
  how many previous/next frames show and their tint, so I can see adjacent frames while drawing. →
  REQ-P5-LOGIC-012, REQ-P5-UI-011, -012 · `onion-skin` · P5
- **US-5 (Animator / tags).** As an animator, I want to **create, edit and delete named frame
  tags** over a range so one file can hold several independent animations (walk, run, idle). →
  REQ-P5-LOGIC-009, -010, REQ-P5-UI-013 · `frame-tags` · P5
- **US-6 (Animator / named-animation).** As an animator, I want to **play a tag as its own named
  animation** with the tag's own playback mode, so I can preview just the walk cycle. →
  REQ-P5-LOGIC-011, REQ-P5-UI-014 · `named-animation` · P5
- **US-7 (Animator / timeline).** As an animator, I want a **timeline showing frames × layers**
  where I can **select and scrub** frames to see each on the canvas. → REQ-P5-UI-001, -002
  · `timeline` · P5
- **US-8 (Animator / per-frame render).** As an animator, I want each frame to show its **full
  composited layer stack** (visibility/opacity/blend honoured), reusing the layer compositor. →
  REQ-P5-LOGIC-013 · `frame-compositing` · P5
- **US-9 (Animator / persistence).** As an animator, I want **frames, per-frame durations and
  frame tags to round-trip** through `.pixproj` so my animation reopens exactly. →
  REQ-P5-DATA-001, -002, -003 · `animation-persistence` · P5
- **US-10 (Animator / reversibility).** As an animator, I want **every timeline / tag operation
  to be undoable** exactly like painting. → REQ-P5-LOGIC-004..010, REQ-P5-UI-015
  · `frame-reversibility` · P5
- **US-11 (Any user / responsive-playback).** As an animator on a large canvas, I want
  **scrubbing and playback of an 8K multi-layer frame to stay at 60 fps**. → REQ-P5-UI-016
  · `playback-perf` · P5
- **US-12 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English
  user, I want the timeline, playback and tag controls **keyboard-reachable, correct in both
  themes, fully translatable**. → REQ-P5-UI-017, -018, -019 · `a11y`, `theming`, `i18n` · P5

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `playback` | `PlaybackMode` enum + the pure frame-sequencing engine (loop/once/ping-pong/reverse) + timing. | 5 |
| `frame-management` | Reversible add / remove / reorder / duplicate of frames. | 5 |
| `frame-timing` | Per-frame `duration_ms` and its reversible edit. | 5 |
| `onion-skin` | Tinted, reduced-opacity overlay of N prev / M next composited frames. | 5 |
| `frame-tags` | `FrameTag` model (name + inclusive range + mode) and its reversible edits. | 5 |
| `named-animation` | Playing a tag's sub-range under the tag's own mode (multi-animation per file). | 5 |
| `timeline` | The `ui/` frames × layers grid with selection/scrub. | 5 |
| `frame-compositing` | Per-frame render reusing Phase-4 `blend.composite_stack` (CO-4). | 5 |
| `frame-reversibility` | Every frame/tag op wrapped as a single reversible command. | 5 |
| `animation-persistence` | `.pixproj` round-trip of frames + durations (reused) + tags (new). | 5 |
| `playback-perf` | Scrub/playback recomposite of an 8K multi-layer frame within the frame budget. | 5 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 5 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-5 capability +
forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a fixed `logic/` callable is named as a **constraint**, not a HOW decision.

### `logic/animation.py` — playback, onion-skin, tags (new)

#### REQ-P5-LOGIC-001 — Playback-mode enumeration (single source)
`traces:` S6 (unified platform / animation), Phase-5 capability
`logic/animation.py` defines a `PlaybackMode` enumeration with exactly four members —
`LOOP`, `ONCE`, `PING_PONG`, `REVERSE`. The enum is the single source of the playback-mode
vocabulary shared by the sequencing engine, the frame-tag model, the UI mode selector, and
`.pixproj`. The default mode is `LOOP` (CL-3).

#### REQ-P5-LOGIC-002 — Deterministic frame sequencing per mode
`traces:` Phase-5 capability, F-anim (DEP-1)
A **pure, deterministic** sequencing function, given a frame range (start..end inclusive), a
current position, and a `PlaybackMode`, yields the **next** frame index (or a stop signal for a
completed non-looping run):
- **LOOP:** advances start→end, then wraps to start indefinitely.
- **ONCE:** advances start→end once, then **stops on the last frame** (no wrap).
- **REVERSE:** advances end→start, then (looping) wraps to end.
- **PING_PONG:** advances start→end, then end→start, bouncing — **endpoint frames are not
  doubled** (order for a 4-frame range: `0,1,2,3,2,1,0,1,2,3,…`, CL-5).
Identical inputs always yield identical output (determinism, P2). A single-frame range yields
that frame for every mode.

#### REQ-P5-LOGIC-003 — Playback timing source is per-frame duration
`traces:` FR-2 (`DEFAULT_FRAME_DURATION_MS`, forward-inherited), Article VI, Phase-5 capability
The **authoritative timing source is each frame's `duration_ms`** (CL-6): the sequencing engine
pairs each yielded frame index with that frame's `duration_ms` so the UI timing driver waits that
many milliseconds before advancing. A new frame defaults to `DEFAULT_FRAME_DURATION_MS`
(reused, FR-2). An optional uniform **FPS** convenience is expressed by *setting* frame durations
(`duration_ms = round(1000 / fps)`), not by a competing clock — per-frame ms remains the single
source of truth.

#### REQ-P5-LOGIC-004 — Reversible add-frame command
`traces:` FR-1 (`add_frame` extended), S7 (command-pattern undo)
Adding a frame is a reversible operation exposing a do/undo pair (a new frame with one empty layer
and `DEFAULT_FRAME_DURATION_MS`, inserted after the active frame) that `ui/commands.py` wraps in
one `QUndoCommand` via `logic/history.py`. Undo removes exactly the added frame; the frame count
returns exactly to prior. The frame count is bounded by `MAX_FRAMES` (REQ-P5-LOGIC-014).

#### REQ-P5-LOGIC-005 — Reversible remove-frame command (refuses last)
`traces:` FR-1 (`remove_frame` extended), S7
Removing a frame is reversible: undo restores the removed frame at its prior index with its exact
layer tree and `duration_ms`. Removing the **last remaining frame is refused** with a
`DocumentError` (the shipped `remove_frame` invariant is preserved). Any frame tag whose range
referenced the removed frame is adjusted/clamped and that adjustment is part of the same
reversible operation (REQ-P5-LOGIC-010).

#### REQ-P5-LOGIC-006 — Reversible reorder-frame command
`traces:` Phase-5 capability (new op — no `move_frame` exists today), S7
Moving a frame from one index to another is a reversible single operation: undo restores the prior
frame order exactly. Reordering does not alter any frame's layers or duration. (There is **no**
frame-reorder op in the shipped `document.py`; this adds it.)

#### REQ-P5-LOGIC-007 — Reversible duplicate-frame command
`traces:` Phase-5 capability (new op), S7
Duplicating a frame inserts a **deep, independent copy** (its full layer tree copied
pixel-for-pixel, its `duration_ms` copied) immediately after the source; editing the copy never
affects the source and vice-versa. It is reversible (undo removes the copy) and bounded by
`MAX_FRAMES`. (No frame-duplicate op exists today; this adds it, mirroring the layer
`make_duplicate_layer_command` deep-copy pattern.)

#### REQ-P5-LOGIC-008 — Reversible set-frame-duration command
`traces:` FR-2 (`Frame.duration_ms`, forward-inherited), S7, Article VII (defensive)
Setting a frame's `duration_ms` is a reversible operation capturing the prior value; undo restores
it exactly. A duration must be a **positive integer** (the shipped `Frame` invariant); a
non-positive value raises `DocumentError` rather than being silently coerced.

#### REQ-P5-LOGIC-009 — Frame-tag model (named animation range)
`traces:` Phase-5 capability (multi-animation-per-file — Pro-Motion-NG differentiator), S6
A `FrameTag` carries a **name**, an **inclusive frame range** `[from_frame, to_frame]`
(`from_frame ≤ to_frame`, both within the current frame count), a **`PlaybackMode`**, and an
optional **repeat count** (`0`/absent = infinite for looping modes). A `Document` holds an ordered
collection of tags. Tags may overlap. Construction with an out-of-range or inverted range raises
`DocumentError`. Tag names need not be unique but the collection preserves creation order (CL-8).

#### REQ-P5-LOGIC-010 — Reversible tag create / edit / delete; ranges kept valid
`traces:` Phase-5 capability (frame tags), S7
Creating, editing (rename / re-range / change mode / repeat) and deleting a `FrameTag` are each
reversible single operations (undo restores the exact prior tag collection). When a frame is
**added or removed** (REQ-P5-LOGIC-004/-005), every tag range is kept valid — clamped to the new
frame bounds — as part of that operation's reversible do/undo, so no tag can reference a
non-existent frame.

#### REQ-P5-LOGIC-011 — Named-animation playback over a tag's sub-range
`traces:` Phase-5 capability (named animation), REQ-P5-LOGIC-002
Playing a `FrameTag` runs the sequencing engine (REQ-P5-LOGIC-002) over the tag's
`[from_frame, to_frame]` sub-range under the **tag's own** `PlaybackMode` and repeat count —
independently of the document's global playback mode. A `ONCE` tag with a repeat count of 3 plays
its range three times then stops. This is the mechanism that makes one file hold several
independent named animations.

#### REQ-P5-LOGIC-012 — Onion-skin overlay (tinted prev/next composited frames)
`traces:` Phase-5 capability (onion skinning), F-anim (DEP-1), CO-4 (forward-inherited)
An onion-skin computation, given the active frame index, a previous count `P` and next count `N`
(each `0..MAX_ONION_SKIN_FRAMES`), returns an ordered set of overlay contributions: for each of
the up-to-`P` previous and up-to-`N` next frames, the frame's **composited layer stack** (via
`blend.composite_stack`, CO-4) tinted toward `ONION_TINT_PREV` (previous) or `ONION_TINT_NEXT`
(next) and scaled by `ONION_SKIN_OPACITY` (optionally falling off with distance). Farther frames
render behind nearer ones; the active frame is unaffected. A layer hidden in a frame stays hidden
in that frame's onion contribution (visibility honoured, CL-12). The computation is pure,
deterministic, and Qt-free; it is **not** rendered during active playback (CL-11).

#### REQ-P5-LOGIC-013 — Per-frame render reuses the Phase-4 stack compositor (CO-4)
`traces:` CO-4 (forward-inherited: `blend.composite_stack` reserved for per-frame animation render), S7
Rendering any frame for display, scrub, onion or playback flattens **that frame's own layer
stack** by **delegating to `blend.composite_stack`** (the CO-4 primitive shipped in Phase 4) —
honouring each layer's visibility / opacity / blend mode / groups / masks. The animation system
does **not** re-implement compositing maths (Article I). Compositing never mutates the frame's
source buffers (non-destructive).

#### REQ-P5-LOGIC-014 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The animation model enforces named bounds/defaults defined once in `logic/constants.py`:
`MAX_FRAMES` (max frames per document), `MAX_ONION_SKIN_FRAMES` (max prev/next onion count),
`DEFAULT_ONION_PREV` / `DEFAULT_ONION_NEXT` (default onion counts, = 1 each, CL-4),
`ONION_TINT_PREV` (red) / `ONION_TINT_NEXT` (blue) (CL-4), and `ONION_SKIN_OPACITY`.
`DEFAULT_FRAME_DURATION_MS` is **reused** (FR-2, already present). Exceeding a bound raises a
domain error rather than degrading silently.

### `ui/` — timeline, playback, onion, tags

#### REQ-P5-UI-001 — Timeline panel shows frames × layers
`traces:` S6, Phase-5 capability
A timeline panel presents the active document as a grid of **frames (columns) × layers (rows)**,
reflecting the `logic/document` tree (each frame's own layer stack, CL-9). The active frame and
active layer are indicated; frames are ordered left-to-right in playback order.

#### REQ-P5-UI-002 — Frame selection and scrub
`traces:` S1, S6, Phase-5 capability
Clicking a frame column selects it as the **active (canvas-displayed) frame**; dragging along the
timeline **scrubs** — the canvas continuously shows the frame under the cursor (its composited
layer stack, REQ-P5-LOGIC-013). Selecting a frame does not modify the document (no undo entry).

#### REQ-P5-UI-003 — Add-frame action
`traces:` REQ-P5-LOGIC-004
The timeline exposes an **add frame** action inserting a new empty-layer frame after the active
frame; it recomposites/refreshes the timeline and pushes exactly one `QUndoCommand`.

#### REQ-P5-UI-004 — Remove-frame action (refuses last)
`traces:` REQ-P5-LOGIC-005
The timeline exposes a **remove frame** action deleting the active frame; refused (disabled /
error) when only one frame remains. Pushes exactly one `QUndoCommand`; undo restores the frame.

#### REQ-P5-UI-005 — Reorder frames by drag
`traces:` REQ-P5-LOGIC-006
The user can **drag a frame column** to a new position; on drop the frame order changes and one
`QUndoCommand` is pushed. Playback and scrub reflect the new order.

#### REQ-P5-UI-006 — Duplicate-frame action
`traces:` REQ-P5-LOGIC-007
The timeline exposes a **duplicate frame** action inserting a deep copy after the source; one
`QUndoCommand` is pushed; editing the copy does not affect the source.

#### REQ-P5-UI-007 — Per-frame duration editor
`traces:` REQ-P5-LOGIC-008, FR-2
Each frame exposes an editable **duration** (milliseconds, defaulting to
`DEFAULT_FRAME_DURATION_MS`); committing a change sets that frame's `duration_ms` and pushes one
`QUndoCommand`. The editor reflects the current value and rejects non-positive input.

#### REQ-P5-UI-008 — Playback transport: play / pause / stop
`traces:` REQ-P5-LOGIC-002, -003
Playback controls offer **play**, **pause**, and **stop**. Play advances the displayed frame over
time using the sequencing engine and each frame's `duration_ms`; pause freezes on the current
frame; stop halts and returns to the frame that was active when playback started. The timing
driver (timer) is `ui/`-only; the sequence is `logic/animation` (Article I).

#### REQ-P5-UI-009 — Playback-mode selector
`traces:` REQ-P5-LOGIC-001
A control selects the **global** playback mode — loop / once / ping-pong / reverse — with
translatable labels, defaulting to **loop** (CL-3). The selection drives which
`PlaybackMode` the engine uses for whole-document playback.

#### REQ-P5-UI-010 — Playback honours per-frame durations
`traces:` REQ-P5-LOGIC-003
During playback each frame is displayed for its own `duration_ms` (a 500 ms frame lingers five
times as long as a 100 ms frame). Changing a frame's duration changes its on-screen dwell time on
the next pass.

#### REQ-P5-UI-011 — Onion-skin toggle
`traces:` REQ-P5-LOGIC-012
A toggle enables/disables **onion skinning**. When on (and not playing), the canvas renders the
tinted prev/next overlay behind the active frame (REQ-P5-LOGIC-012); when off, only the active
frame shows.

#### REQ-P5-UI-012 — Onion prev/next count + tint controls (configurable)
`traces:` REQ-P5-LOGIC-012, -014
The user can set how many **previous** and **next** frames the onion shows
(`0..MAX_ONION_SKIN_FRAMES`, defaulting to `DEFAULT_ONION_PREV` / `DEFAULT_ONION_NEXT` = 1/1) and
the **tint** for each (defaulting to red for previous, blue for next, CL-4). Changes update the
overlay live. These are view settings, not document edits (no undo entry, CL-13).

#### REQ-P5-UI-013 — Frame-tags UI (create / edit / delete)
`traces:` REQ-P5-LOGIC-009, -010
The UI lets the user **create** a named tag over a selected frame range, **edit** it (rename,
re-range, change its playback mode / repeat), and **delete** it. Tags are shown against the
timeline spanning their range. Each mutation pushes exactly one `QUndoCommand`.

#### REQ-P5-UI-014 — Named-animation playback of a tag
`traces:` REQ-P5-LOGIC-011
The user can **select a tag and play it** as its own animation: playback runs the tag's range
under the tag's own playback mode / repeat (REQ-P5-LOGIC-011), independently of the global mode.

#### REQ-P5-UI-015 — Every frame / tag operation is exactly one undoable command
`traces:` S7, C1, F1, REQ-P5-LOGIC-004..010
Every timeline/tag operation surfaced by the UI — add / remove / reorder / duplicate frame, set
frame duration, create / edit / delete tag — is pushed as **exactly one `QUndoCommand`** onto the
active document's `QUndoStack`, delegating to the Qt-free reversible op in
`logic/document` / `logic/history` (Article I: `ui/commands.py` is the only Qt file outside
`ui/`). Undo restores the exact prior state. Selection, scrub, playback and onion view-settings are
**not** undoable (they do not mutate the document, CL-13).

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P5-UI-016 — Performance: 8K multi-layer scrub/playback within the frame budget *(NFR, Article VI)*
`traces:` S1, S12, F2, F7, Article VI, DEP-3
Scrubbing or playing an animation whose frames are multi-layer 8K stacks (7680 × 4320) holds
`FPS_TARGET = 60`, i.e. per-frame recomposite/display time ≤ `FRAME_BUDGET_MS = 16`. Advancing a
frame must recomposite only what changed (dirty-rect recomposite; a cached per-frame composite is
expected) rather than flattening every layer over the whole canvas each tick. **Verified headless
by AGT-10** (`perf_profile` / `frame-profile`); an over-budget measurement yields an AGT-10
optimisation directive (cached frame composites, dirty-rect, viewport tuning), **never** a
relaxation of the budget. The resident per-layer/per-frame buffers are never culled (only Qt
rendering is, F7 / Article VI §3). The concrete recomposite strategy is AGT-10 plan-level (DEP-3).

#### REQ-P5-UI-017 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive timeline / playback / onion / tag control (frame cells, duration editor,
play/pause/stop, mode selector, onion toggle + count/tint controls, tag create/edit/delete, tag
play) exposes an accessible name and, where non-obvious, an accessible description; is reachable
and operable by keyboard (logical tab order + shortcuts, e.g. space = play/pause); and shows a
visible focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P5-UI-018 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The timeline, playback controls, onion controls and tag UI render correctly in both light and dark
themes; colours (including tag spans, active-frame indicator, onion-control swatches) are defined
once by role, never hard-coded per widget. The **onion tint colours** (`ONION_TINT_PREV/NEXT`) are
content-overlay colours (from constants), not theme role colours, and read legibly in both themes.
Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-P5-UI-019 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 5 (playback-mode labels, transport tooltips, onion
labels, tag names/dialog text, frame-duration units, timeline action labels) is wrapped in
`tr()` / `translate()`; none is a bare literal. Hand-built widgets re-set text on
`QEvent.LanguageChange`. Verified by `string_audit_check` (AGT-07); an unwrapped string is a
blocking finding.

### `data/` — animation-persistence

#### REQ-P5-DATA-001 — Frame tags persist and round-trip
`traces:` IO-2 (extend), S7, Phase-5 capability
`.pixproj` serialises the document's frame **tags** — each tag's name, inclusive `[from, to]`
range, `PlaybackMode`, and repeat count. Saving then loading a tagged document restores the tag
collection **identically** (names, ranges, modes, repeat, order). The schema-version bump vs. an
additive field on v2 is an AGT-01 plan decision (DEP-2).

#### REQ-P5-DATA-002 — Frames + per-frame durations round-trip (reused v2)
`traces:` IO-2 (reused — `duration_ms` already serialised), S7
A multi-frame document with distinct per-frame `duration_ms` values round-trips losslessly through
`.pixproj`. This behaviour **already ships in v2** (`data/project_io.py` writes and validates
`duration_ms`); Phase 5 states it as an **animation-level acceptance** and reuses the shipped path
rather than re-implementing it. Frame **order** is preserved.

#### REQ-P5-DATA-003 — Defensive validated load of tags; back-compat
`traces:` Article VII, IO-2
Loading `.pixproj` **validates** tag data before use: a tag with an out-of-range/inverted frame
range, an unknown `PlaybackMode`, a non-int/negative repeat, or a malformed tag object raises
`ProjectIOError` (never silent acceptance, never `eval`/`exec`). A project **without** a tags
field (older / tagless) loads successfully with an empty tag collection (back-compat).

## 6. Non-goals (explicit; deferred)

- **Cel-level layer × frame linking** — a single layer's identity/content shared across frames as
  *linked cels* (edit once, propagates), and a true frames × *shared-layers* matrix. → **deferred**
  (CL-9). The shipped tree gives each `Frame` its **own independent layer list**; Phase 5's
  timeline presents that model (frames × the active frame's layer stack) and adds frame-level ops.
  Cross-frame linked cels are a substantial new model that can follow without weakening any article
  (Article XI). This is the one genuine scope-bounding decision; resolved by *scoping down*, not by
  suspending (§12).
- **Dedicated real-size / motion preview window** (separate dockable, PureRef-style) → **Phase 9**
  (Visual Aids: "real-size preview window"). Phase 5 previews motion by **playing back on the
  canvas** (REQ-P5-UI-008), which satisfies the ROADMAP "motion preview" intent minimally.
- **GIF / sprite-sheet / animation export** → **Phase 7** (frames feed the export path; the
  compositor and per-frame render Phase 5 provides are the inputs, but no export UI here).
- **GPU / dirty-rect recomposite strategy** (cached per-frame composites, viewport tuning) —
  AGT-10 **plan-level** directive (DEP-3); this spec states only the 16 ms budget
  (REQ-P5-UI-016).
- **Onion-skin exact tint blend maths / distance-falloff curve, timeline widget model** — grounded
  by The Researcher (`docs/research-phase5-animation.md`, DEP-1); this spec fixes the *behaviour*
  (tinted prev/next composited overlay at reduced opacity) and Aseprite-parity defaults, not the
  precise blend.
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`,
  `specs/phase-4-layer-canvas/`): `Frame` with **`duration_ms`** (FR-2), `Document.add_frame` /
  `remove_frame` (FR-1 — direct mutators, **extended** here into reversible commands),
  `DEFAULT_FRAME_DURATION_MS` (reused), `blend.composite_stack` (CO-4 — per-frame render),
  `history` (`Command`, `FunctionCommand`, `History`), `data/project_io.py` **v2** (already
  round-trips frames + layers + `duration_ms`, IO-2). Phase 5 **extends** these; it must not
  re-implement compositing or frame storage (Article I).
- **NEW vs REUSED (explicit):**
  - **NEW:** `logic/animation.py` (`PlaybackMode`, sequencing engine, onion overlay, `FrameTag`
    model, named-animation playback); reversible frame commands
    (`make_add_frame_command` / `make_remove_frame_command` / `make_move_frame_command` /
    `make_duplicate_frame_command` / `make_set_frame_duration_command`) — note **`move`/`duplicate`
    frame ops do not exist today**; frame-tags storage + reversible tag ops on `Document`; new
    constants (`MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`, onion defaults/tints, `ONION_SKIN_OPACITY`);
    all timeline/playback/onion/tag UI + the `.pixproj` tag persistence.
  - **REUSED (not re-authored):** the `Frame` tree, `Frame.duration_ms`,
    `DEFAULT_FRAME_DURATION_MS`, `blend.composite_stack`, the `history` command pattern, and the
    v2 `.pixproj` frame/layer/`duration_ms` serialisation.
- Frame ops reuse the shipped `history.FunctionCommand` do/undo pattern so `ui/commands.py` stays a
  thin Qt wrapper (REQ-P5-UI-015, Article I §2), mirroring the Phase-4 layer-command precedent.
- The active frame / active layer are held by the window; the playback timer is `ui/`; the canvas
  renders the active (or scrubbed / playing) frame via `blend.composite_stack`.

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-1 (Researcher, grounding).** `docs/research-phase5-animation.md` grounds onion-skin
  internals (tint blend, distance falloff), the frame-tag schema conventions, the timeline widget
  model, and playback timing precision. **Not yet present (concurrent).** AGT-01's `sdd-plan` must
  not invent these — it consumes the Researcher's findings. The *behaviour set* and Aseprite-parity
  defaults are fixed here regardless (§10).
- **DEP-2 (AGT-01 / DATA schema).** Persisting frame **tags** extends `data/project_io.py`. Whether
  this is a **schema-version bump (v3)** or an **additive optional field on v2** is an AGT-01 plan
  decision; back-compat read of tagless projects is required either way (REQ-P5-DATA-003). Final
  `REQ-P5-DATA-*` count may be refined at plan time; this spec allocates `-001..-003`.
- **DEP-3 (AGT-10, plan).** The recomposite strategy that makes REQ-P5-UI-016 pass — **cache each
  frame's composited buffer**, recomposite only dirty regions on edit, cull only Qt rendering — is
  AGT-10's render-strategy output. Playing an 8K multi-layer animation by re-flattening every layer
  every tick will blow `FRAME_BUDGET_MS`; a cached-frame-composite + dirty-rect approach is very
  likely required (flagged for the plan). This spec fixes only the budget.
- **BF-1 (AGT-01, plan).** Whether onion overlays are drawn as separate tinted
  `QGraphicsPixmapItem`s behind the active frame vs. pre-blended into one overlay buffer is a HOW
  decision; the spec requires only the tinted prev/next behaviour (REQ-P5-LOGIC-012).
- **BF-2 (AGT-01, Article II).** New tuning values (`MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`,
  `DEFAULT_ONION_PREV/NEXT`, `ONION_TINT_PREV/NEXT`, `ONION_SKIN_OPACITY`) must resolve to named
  constants in `logic/constants.py`; `DEFAULT_FRAME_DURATION_MS` is reused. The `PlaybackMode` enum
  lives in `logic/animation.py` (vocabulary, not a numeric tuning value); its default `LOOP` is the
  S12-style default (CL-3).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/animation.py` and the `document.py` extensions are
  pure Python, zero Qt; the timeline/playback/onion/tag panels live in `ui/`; the playback **timer**
  is `ui/`; the only Qt file outside `ui/` remains `ui/commands.py` (frame/tag command wrappers,
  REQ-P5-UI-015). Enforced by `check_layering` / `check_cycles`.
- **Article II (numerics):** new tuning values go in `logic/constants.py` (BF-2); no literals in
  `ui/`/`logic/`/`data/`. `DEFAULT_FRAME_DURATION_MS` is reused. Tint colours are named constants.
- **Article IV (testing):** each playback mode, the sequencing determinism, onion overlay, frame
  reversibility, tag reversibility, per-frame render reuse, and `.pixproj` tag round-trip + defensive
  load each get a scenario → one pytest / Hypothesis test (logic/data) or pytest-qt test (UI), both
  themes for UI.
- **Article V (UX):** REQ-P5-UI-017/-018/-019 make a11y + both themes + full translatability
  blocking gates for the timeline and playback UI.
- **Article VI (performance):** REQ-P5-UI-016 binds the 16 ms budget for 8K multi-layer
  scrub/playback; the resident buffers are never culled.
- **Article VII (security):** frame/tag bounds, positive-duration guard, and **defensive validated
  `.pixproj` tag load** (REQ-P5-DATA-003, REQ-P5-LOGIC-014) are defensive; no `eval`/`exec`.
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited
  primitive (FR-1/FR-2, CO-4, IO-2); forward matrix in `traceability.md`.
- **Article XI (extensibility):** deferring cel-linking (CL-9) and the dedicated preview window
  (Phase 9) adds capability later without weakening any article.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with sensible
defaults grounded in the dossier, the shipped code, and mainstream pixel-art norms (**Aseprite**
parity, Pro Motion NG, Pixelorama). Each is a **category-1 decision** (A2-D2 Branch B). **No open
clarification blocks planning.**

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Which playback modes? | The **four** — loop, once, ping-pong, reverse — as `PlaybackMode`. | Prompt + ROADMAP Phase-5 bullet; Aseprite's animation-direction set. |
| **CL-2** | Default frame duration? | **`DEFAULT_FRAME_DURATION_MS`** (the shipped constant, ~100 ms) — **reused**, not redefined. | `logic/document.py`/`constants.py` already define it (FR-2); reusing keeps a single source (Art. II). |
| **CL-3** | Default playback mode? | **`LOOP`**. | Universal animation-editor default (Aseprite/Pixelorama loop by default). |
| **CL-4** | Onion prev/next default counts + tint + configurable? | **1 previous / 1 next** by default (`DEFAULT_ONION_PREV/NEXT`); tint **red = previous / blue = next** (`ONION_TINT_PREV/NEXT`); **configurable** counts + tint via UI (REQ-P5-UI-012). | Aseprite onion-skin defaults (1/1, red/blue). |
| **CL-5** | Ping-pong endpoint behaviour? | **Endpoints not doubled** — `0,1,2,3,2,1,0,1,…` (bounce reflects, does not repeat the end/start frame). | Aseprite ping-pong; avoids a visible stutter at the turn. |
| **CL-6** | Playback timing source — per-frame ms vs FPS? | **Per-frame `duration_ms` is authoritative**; a uniform-FPS convenience just sets all durations (`round(1000/fps)`), not a separate clock. | Matches the shipped `Frame.duration_ms` (FR-2); Aseprite is per-frame-ms with an FPS helper. |
| **CL-7** | Timeline model — cel linking or per-frame stacks? | **Per-frame independent layer stacks** (the shipped tree). Cel-level layer × frame **linking is DEFERRED** (CL-9). | The shipped `Frame` owns its own layer list; linked cels are a substantial new model, boundable per Art. XI (§6). |
| **CL-8** | Tag name uniqueness / overlap? | Names **need not be unique**; ranges **may overlap**; collection preserves creation order. | Aseprite allows duplicate/overlapping tags; simplest deterministic model. |
| **CL-9** | Scope of "smart"/advanced animation — cel linking, live preview window? | **Deferred**: linked cels → later phase; dedicated preview window → Phase 9. Phase 5 ships timeline + playback + onion + tags over per-frame stacks and previews on-canvas. | Bounds the phase to parity-critical capability; differentiator (multi-animation-per-file via tags) still ships. |
| **CL-10** | Layer visibility/opacity/blend during playback? | Each frame renders via **`blend.composite_stack`** (CO-4), fully honouring per-layer visibility/opacity/blend/groups/masks. | Reuses the Phase-4 compositor; playback shows the true composited frame. |
| **CL-11** | Onion skin during playback? | **Suppressed during active playback** (an editing aid only); shown when paused/stopped with onion toggled on. | Aseprite hides onion while playing; avoids a muddled preview. |
| **CL-12** | Onion honours hidden layers? | **Yes** — a layer hidden in a frame is hidden in that frame's onion contribution (onion uses the composited frame). | Consistent with CL-10; the onion shows what the frame actually renders. |
| **CL-13** | Are selection / scrub / playback / onion settings undoable? | **No** — they do not mutate the document; only frame/tag *edits* are `QUndoCommand`s (REQ-P5-UI-015). | Editor norm; scrubbing/playing is view state, mirrors Phase-4 active-layer selection being non-undoable. |
| **CL-14** | Where does the playback clock live? | The **timer is `ui/`**; the sequence (next-frame decision) is pure `logic/animation` (Art. I). | Keeps `logic/` Qt-free; only `ui/` touches `QTimer`. |
| **CL-15** | `.pixproj` schema for tags — new version or additive? | **AGT-01 plan decision** (v3 bump vs additive v2 field, DEP-2); **back-compat read of tagless projects is required** either way (REQ-P5-DATA-003). Durations already persist (v2, reused). | Persistence-mechanism HOW belongs to the plan; the WHAT (tags round-trip, back-compat) is fixed here. |
| **CL-16** | Frame count bound? | Bounded by **`MAX_FRAMES`** (Art. II/VII); error past it. | Defensive numeric; parallels `MAX_LAYERS_PER_FRAME`. |

**SUSPEND / escalate:** *none.* The one genuine scope risk — **cel-level layer × frame linking** —
is resolved by **scoping Phase 5 to the shipped per-frame independent layer stacks and deferring
linked cels** (CL-7/CL-9, §6), a category-1 decision, not a blocker. The onion-skin blend maths and
timeline widget model are a named upstream dependency (DEP-1, Researcher), not an open ambiguity:
the behaviour and Aseprite-parity defaults are fixed regardless. The `.pixproj` schema-version
choice is a plan-level HOW (DEP-2/CL-15), not a spec ambiguity.

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic/data scenarios are for **AGT-04** (pytest + Hypothesis,
headless); UI scenarios are for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`), **each run
under BOTH light and dark themes** (REQ-P5-UI-018, expressed once as a global rule). Scenario ids
map to `traceability.md`; tests are authored later (`pending`).

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the
> scenario is executed and asserted identically under the light theme and the dark theme.*

### Feature: Playback engine (REQ-P5-LOGIC-001..003)
```gherkin
Scenario: SC-L001-1 the PlaybackMode enum has exactly the four modes
  Given logic/animation.PlaybackMode
  Then it enumerates LOOP, ONCE, PING_PONG, REVERSE and no others
  And the default playback mode is LOOP

Scenario Outline: SC-L002-1 each mode yields the correct frame sequence over a 4-frame range
  Given a frame range 0..3 and mode <mode>
  When the next frame is requested repeatedly from position 0 for 10 steps
  Then the emitted indices equal <sequence>
  Examples: | mode      | sequence                          |
            | LOOP      | 0,1,2,3,0,1,2,3,0,1               |
            | ONCE      | 0,1,2,3,stop,stop,stop,stop,stop,stop |
            | REVERSE   | 3,2,1,0,3,2,1,0,3,2               |
            | PING_PONG | 0,1,2,3,2,1,0,1,2,3               |

Scenario: SC-L002-2 sequencing is deterministic (property)
  Given any frame range, start position and mode (Hypothesis)
  When the sequence is generated twice
  Then both runs emit identical indices

Scenario: SC-L002-3 a single-frame range yields that frame for every mode
  Given a frame range 2..2 and any mode
  When the next frame is requested repeatedly
  Then every emitted index is 2 (no out-of-range)

Scenario: SC-L003-1 the timing source is each frame's duration_ms
  Given frames with durations [100, 500, 100]
  When the sequence is generated
  Then each emitted step pairs the frame index with that frame's duration_ms
  And a new frame's duration equals DEFAULT_FRAME_DURATION_MS
```

### Feature: Reversible frame operations (REQ-P5-LOGIC-004..008)
```gherkin
Scenario: SC-L004-1 add frame is reversible
  Given a document with 2 frames
  When a frame is added via a command and then undone
  Then the document has 3 frames after do and exactly 2 after undo

Scenario: SC-L005-1 remove frame is reversible (restores contents, index, duration)
  Given a 3-frame document whose middle frame is painted and has duration 250
  When the middle frame is removed via a command and then undone
  Then the frame returns at its prior index with identical layers and duration 250

Scenario: SC-L005-2 the last frame of a document cannot be removed
  Given a document with one frame
  When a remove-frame is attempted
  Then it raises DocumentError and the document still has one frame

Scenario: SC-L006-1 reorder frame is reversible
  Given frames [A, B, C]
  When B is moved before A via a command and then undone
  Then the order is [B, A, C] after do and exactly [A, B, C] after undo

Scenario: SC-L007-1 duplicate frame deep-copies and is reversible
  Given a frame with a painted layer stack and duration 200
  When the frame is duplicated via a command
  Then a copy is inserted after it with identical pixels and duration 200
  And editing the copy leaves the source unchanged
  And undo removes exactly the copy

Scenario: SC-L008-1 setting a frame duration is reversible and rejects non-positive
  Given a frame at duration 100
  When set-duration(400) is applied as a command and then undone
  Then the duration is 400 after do and exactly 100 after undo
  And set-duration(0) raises DocumentError
```

### Feature: Frame tags & named animation (REQ-P5-LOGIC-009..011)
```gherkin
Scenario: SC-L009-1 a FrameTag stores name, inclusive range, mode and repeat
  Given a document with 6 frames
  When a tag "walk" over frames 1..4 with mode PING_PONG is created
  Then the tag reports name "walk", range [1,4], mode PING_PONG
  And an out-of-range or inverted range raises DocumentError

Scenario: SC-L010-1 tag create / edit / delete is reversible
  Given a document with no tags
  When a tag is created, edited (renamed + re-ranged), then deleted, each via a command
  Then each undo restores the exact prior tag collection

Scenario: SC-L010-2 tag ranges stay valid when a frame is removed
  Given a tag "run" over frames 2..5 and a 6-frame document
  When frame 5 is removed
  Then the tag range is clamped to a valid range within the new frame count
  And undo restores both the frame and the original tag range

Scenario: SC-L011-1 playing a tag runs its sub-range under the tag's own mode
  Given a tag "idle" over frames 2..3 with mode ONCE and repeat 2
  When the named animation is played
  Then the sequence is 2,3,2,3,stop (its range, twice, then stops) independent of the global mode
```

### Feature: Onion skinning & per-frame render (REQ-P5-LOGIC-012..013)
```gherkin
Scenario: SC-L012-1 the onion overlay tints previous and next composited frames
  Given active frame 2 with 1 previous and 1 next onion frame
  When the onion overlay is computed
  Then it includes frame 1 tinted toward ONION_TINT_PREV and frame 3 tinted toward ONION_TINT_NEXT
  And each is scaled by ONION_SKIN_OPACITY and the active frame is unchanged

Scenario: SC-L012-2 onion counts are bounded and honour hidden layers
  Given an onion prev/next count above MAX_ONION_SKIN_FRAMES
  Then a domain error is raised
  And a frame whose top layer is hidden contributes its composited (layer-hidden) image to the onion

Scenario: SC-L013-1 a frame renders via blend.composite_stack (CO-4 reuse)
  Given a frame with a RED bottom layer and a half-alpha BLUE top layer
  When the frame is rendered for display
  Then the result equals blend.composite_stack of that frame's layers (compositing not re-implemented)
  And the frame's source buffers are byte-for-byte unchanged
```

### Feature: Bounds & defaults (REQ-P5-LOGIC-014)
```gherkin
Scenario: SC-L014-1 frame count is bounded
  Given a document at MAX_FRAMES frames
  When another add-frame is attempted
  Then a domain error is raised

Scenario: SC-L014-2 onion defaults come from constants
  Given a fresh onion configuration
  Then the previous/next counts equal DEFAULT_ONION_PREV / DEFAULT_ONION_NEXT (1 / 1)
  And the tints equal ONION_TINT_PREV (red) / ONION_TINT_NEXT (blue)
```

### Feature: Timeline & frame management UI (REQ-P5-UI-001..007)
```gherkin
Scenario: SC-UI-001-1 the timeline shows frames as columns and layers as rows
  Given a document with 3 frames and 2 layers
  When the timeline panel is shown
  Then there are 3 frame columns in playback order and the layer rows reflect the active frame's stack

Scenario: SC-UI-002-1 selecting and scrubbing a frame updates the canvas without an undo entry
  Given a multi-frame document
  When the user clicks frame 2 and then scrubs across the timeline
  Then the canvas shows the composited frame under the cursor and no QUndoCommand is pushed

Scenario: SC-UI-003-1 add-frame inserts after the active frame as one command
  Given a 2-frame document with frame 1 active
  When the user triggers add-frame
  Then a new frame appears after frame 1 and exactly one QUndoCommand is pushed

Scenario: SC-UI-004-1 remove-frame is one command and refused on the last frame
  Given a document
  When the user removes a frame (with >1 frame) and later tries to remove the last frame
  Then the first removal pushes one command and the last-frame removal is refused

Scenario: SC-UI-005-1 dragging a frame reorders it as one command
  Given frames [A, B, C]
  When the user drags C between A and B
  Then the order becomes [A, C, B], playback reflects it, and one QUndoCommand is pushed

Scenario: SC-UI-006-1 duplicate-frame inserts a deep copy as one command
  Given a painted frame
  When the user duplicates it
  Then a copy appears after it, editing the copy does not change the source, and one command is pushed

Scenario: SC-UI-007-1 the per-frame duration editor sets duration_ms as one command
  Given a frame at 100 ms
  When the user sets its duration to 400 ms and commits
  Then Frame.duration_ms == 400, one QUndoCommand is pushed, and a non-positive input is rejected
```

### Feature: Playback controls (REQ-P5-UI-008..010)
```gherkin
Scenario: SC-UI-008-1 play / pause / stop drive the displayed frame
  Given a multi-frame document
  When the user presses play, then pause, then stop
  Then play advances frames over time, pause freezes on the current frame, and stop returns to the pre-play frame

Scenario: SC-UI-009-1 the mode selector offers the four modes and drives playback
  Given the playback-mode selector
  Then it offers exactly LOOP, ONCE, PING_PONG, REVERSE with translatable labels defaulting to LOOP
  And selecting PING_PONG makes playback bounce without doubling endpoints

Scenario: SC-UI-010-1 playback honours per-frame durations
  Given frames with durations [100, 500, 100]
  When the animation plays
  Then the 500 ms frame is displayed about five times as long as each 100 ms frame
```

### Feature: Onion skinning UI (REQ-P5-UI-011..012)
```gherkin
Scenario: SC-UI-011-1 the onion toggle shows/hides the overlay and is suppressed during playback
  Given a paused multi-frame document with the active frame in the middle
  When the user toggles onion skinning on
  Then the tinted prev/next overlay renders behind the active frame
  And when playback starts the onion overlay is suppressed

Scenario: SC-UI-012-1 onion prev/next counts and tints are configurable view settings
  Given the onion controls
  When the user sets previous=2, next=1 and changes the previous tint
  Then the overlay updates live to show 2 previous and 1 next frame with the new tint and no QUndoCommand is pushed
```

### Feature: Frame tags & named-animation UI (REQ-P5-UI-013..014)
```gherkin
Scenario: SC-UI-013-1 create / edit / delete a tag each push one command
  Given a multi-frame document
  When the user creates a tag over a range, edits its name/range/mode, then deletes it
  Then each action changes the tag set, shows the tag span on the timeline, and pushes exactly one QUndoCommand

Scenario: SC-UI-014-1 selecting a tag plays it as its own named animation
  Given a tag "walk" over frames 1..4 with mode PING_PONG
  When the user selects the tag and presses play-tag
  Then playback runs frames 1..4 bouncing under the tag's own mode, independent of the global mode
```

### Feature: Reversibility, performance, a11y, theming, i18n (REQ-P5-UI-015..019) — incl. NFR
```gherkin
Scenario: SC-UI-015-1 every frame/tag op is exactly one undoable command; view ops are not
  Given the timeline and tag UI
  When any frame/tag edit (add/remove/reorder/duplicate frame, set duration, create/edit/delete tag) is performed
  Then exactly one QUndoCommand is pushed and undo restores the exact prior state
  And selection / scrub / playback / onion-setting changes push no command

Scenario: SC-UI-016-1 scrubbing / playing an 8K multi-layer frame stays within the frame budget
  Given a 7680x4320 document with several layers and multiple frames
  When the user scrubs and plays the animation
  Then the measured per-frame recomposite/display time is <= FRAME_BUDGET_MS (16 ms), advancing via cached/dirty-rect recomposite
  # Measured headless by AGT-10 (perf_profile / frame-profile); over-budget yields an AGT-10
  # optimisation directive (cached frame composites / dirty-rect), not a budget relaxation.

Scenario: SC-UI-017-1 timeline / playback / tag controls expose accessible names and keyboard focus
  Given the timeline and playback UI is shown
  When each control (frame cells, duration editor, transport, mode selector, onion controls, tag actions) is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order (space = play/pause), and shows a visible focus indicator

Scenario: SC-UI-018-1 the timeline and playback UI render correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the timeline, tag spans, active-frame indicator and controls render legibly with role-based colours; onion tint colours read legibly in both themes

Scenario: SC-UI-019-1 no Phase-5 user-visible string is a bare literal
  Given the Phase-5 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (mode labels, transport tooltips, onion labels, tag dialog text, duration units)
```

### Feature: `.pixproj` animation persistence (REQ-P5-DATA-001..003)
```gherkin
Scenario: SC-D001-1 frame tags round-trip through .pixproj
  Given a document with tags [("walk",1,4,PING_PONG,0), ("idle",0,0,ONCE,3)]
  When it is saved and reloaded
  Then the loaded tag collection equals the original (names, ranges, modes, repeat, order)

Scenario: SC-D002-1 frames and per-frame durations round-trip (reused v2)
  Given a 4-frame document with durations [100, 250, 500, 100]
  When it is saved and reloaded
  Then the frame count, order, and each frame's duration_ms are identical

Scenario: SC-D003-1 tag load is defensive and tagless projects still load
  Given .pixproj payloads with an inverted tag range, an out-of-range frame, and an unknown mode
  When each is loaded
  Then each raises ProjectIOError (no eval/exec, no silent acceptance)
  And a payload with no tags field loads successfully with an empty tag collection
```

---

## 12. Exit / status

- Forward spec authored for Phase 5 — Animation System. **36 REQ-IDs**: **14 LOGIC**
  (`REQ-P5-LOGIC-001..014`) + **19 UI** (`REQ-P5-UI-001..019`) + **3 DATA**
  (`REQ-P5-DATA-001..003`), each traced to an S-id / F-finding / forward-inherited primitive
  (FR-1 `add_frame`/`remove_frame`→reversible commands; FR-2 `Frame.duration_ms` /
  `DEFAULT_FRAME_DURATION_MS`→timing; CO-4 `blend.composite_stack`→per-frame render;
  IO-2 v2 `.pixproj`→durations reused + tags extended) per Article X.
- **16 clarification defaults** recorded (§10), each grounded in the shipped code + Aseprite
  parity; **no open clarification blocks planning**.
- **No SUSPEND blocker.** The one scope risk — **cel-level layer × frame linking** — is bounded by
  scoping to the shipped per-frame layer stacks + deferral (CL-7/CL-9), a category-1 decision.
- **NEW vs REUSED (§7):** NEW = `logic/animation.py`, reversible frame commands (incl. the missing
  `move`/`duplicate` frame ops), frame-tag storage + reversible tag ops, new constants, all
  timeline/playback/onion/tag UI, `.pixproj` tag persistence. REUSED = `Frame` tree,
  `Frame.duration_ms`, `DEFAULT_FRAME_DURATION_MS`, `blend.composite_stack` (CO-4),
  `history` command pattern, v2 `.pixproj` frame/layer/`duration_ms` serialisation.
- **New constants flagged for `logic/constants.py`** (Article II, BF-2): `MAX_FRAMES`,
  `MAX_ONION_SKIN_FRAMES`, `DEFAULT_ONION_PREV` (1), `DEFAULT_ONION_NEXT` (1), `ONION_TINT_PREV`
  (red), `ONION_TINT_NEXT` (blue), `ONION_SKIN_OPACITY`. `DEFAULT_FRAME_DURATION_MS` reused.
  `PlaybackMode` enum lives in `logic/animation.py`.
- **Dependencies flagged:** DEP-1 (Researcher `docs/research-phase5-animation.md` — onion/tag/
  timeline/timing grounding, concurrent/not-yet-present), DEP-2 (AGT-01 `.pixproj` tag schema
  version — v3 vs additive), DEP-3 (AGT-10 cached-frame / dirty-rect recomposite — REQ-P5-UI-016).
- Acceptance scenarios cover every functional and NFR requirement; forward matrix in
  `traceability.md` (0 uncovered). Tests authored later by AGT-04 (logic/data) / AGT-06 (UI),
  `pending`.
- **STATUS: COMPLETED.**
