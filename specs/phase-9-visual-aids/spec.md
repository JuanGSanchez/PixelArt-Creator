# Specification — Phase 9: Visual Aids & UX

| Field | Value |
| --- | --- |
| Feature | `phase-9-visual-aids` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-04 |
| Governed by | `constitution.md` (Articles I, II, IV, V, **VI**, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no snap/geometry logic (`logic/grids.py`, `logic/guides.py`, `logic/preview.py`, `logic/timelapse.py`), no real-size preview window, guides/rulers overlay, isometric/perspective grid overlay, reference board, multi-view editing, or timelapse UI exists yet. The `Document` tree, `PixelBuffer`, the `logic/history.py` reversible-command path, Phase 4 `blend.composite_stack`, the Phase-4 multiple-canvas / artboard tab system, and the defensive `data/project_io.py` load pattern are **already shipped** and are reused, not re-authored. This spec defines the WHAT/WHY Phase 9 realises. |
| REQ-ID range | `REQ-P9-LOGIC-001..012`, `REQ-P9-UI-001..014` (from the ROADMAP reserved `REQ-P9-LOGIC-*` / `REQ-P9-UI-*` prefixes). **No `REQ-P9-DATA-*` prefix was reserved** — Phase 9 has **two** genuine data-layer persistence concerns (timelapse frame-sequence persistence + reference-board persistence). Their observable contracts are phrased inside LOGIC/UI REQs and the data-layer prefix allocation is **flagged to the orchestrator / AGT-01** (see PREFIX-NOTE §7 and DEP-4); it is **not acceptance-changing**. |
| Layer scope | `pixelart_creator/logic/` (new `grids.py` — pure isometric grid transform + snap + perspective guide-line construction + snap; new `guides.py` — guide/ruler snap geometry + ruler tick/coordinate computation; new `preview.py` — real-size scale computation `f(document PPI, screen DPI)`; new `timelapse.py` — reproducible edit-session frame-sequence model; new constants) — **zero Qt, fully headless-drivable, UNIT-TESTABLE geometry** (this is the point of "tested geometry logic") + `pixelart_creator/data/` (defensive, `eval`-free serialisation of the recorded timelapse sequence + the reference-board layout via the `project_io.py` pattern, IO-3 — **prefix flagged**, see PREFIX-NOTE) — **zero Qt** + `pixelart_creator/ui/` (real-size preview window, guides/rulers overlay, isometric + perspective grid overlays, reference board, multi-view viewports, timelapse recording controls) — **the only Qt surface**, hosting *rendering + overlays + controls only*, never the snap/geometry math. |
| Binds to (upstream, **shipped** — REUSED) | Phase 1 `logic/document.py` `Document` tree (the **DOC-1** primitive: the single shared subject every view + the preview observes), Phase 1 `logic/pixel_buffer.py` `PixelBuffer.data` / `.region` (the **PB-1** primitive: the pixels the real-size preview mirrors), Phase 1 `logic/history.py` (`Command`/`FunctionCommand`/`History` — the **HIS-1** primitive: the reversible-command path whose edits mirror live to the preview + all views, and whose deterministic replay backs reproducible timelapse), Phase 4 `logic/blend.composite_stack` (the **CO-4** primitive: the composited image the preview + every view render), the Phase-4 multiple-canvas / artboard **tab/viewport** system (REQ-P4-UI-014, CL-15 — the **MC-4** primitive: multi-**view** editing *builds on* the viewport/tab infrastructure — see §7 for the multi-view-vs-multi-canvas distinction), Phase 1/4 `data/project_io.py` defensive-load pattern (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib` — the **IO-3** primitive for timelapse / reference-board persistence) |
| Depends on (external) | The Researcher — `docs/research-phase9-visual-aids.md` (grounds the **isometric transform math** (2:1 dimetric vs true-isometric), **perspective guide-line construction** (1-/2-/3-point vanishing-point geometry), **real-size DPI/PPI scaling** conventions, **snap algorithms + tolerance** norms, **timelapse capture strategies** (per-command vs time-based) + storage/encoding landscape, and the **reference-board** landscape (PureRef). **GEOMETRY-FOCUSED, being produced in parallel** (feeds AGT-01) — see DEP-1. This spec fixes the WHAT/acceptance around the **observable geometry + behaviour contract** (`snap()` returns the nearest grid vertex / nearest guide point per a documented transform; `real_size_scale = f(document PPI, screen DPI)`; an edit mirrors live to the preview + all views; a replayed timelapse yields the same frame sequence) and records the clarification defaults; the geometry **math constants + strategies** are AGT-01/ADR. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The platform already carries everything the visual-aids layer observes and mirrors: the `Document`
tree is the single editable subject (DOC-1); `PixelBuffer` holds the pixels (PB-1);
`logic/history.py` makes **every** state mutation a reversible command on a `History` stack (HIS-1);
`blend.composite_stack` flattens a frame's ordered layer stack into the RGBA image a viewport draws
(CO-4); and the Phase-4 multiple-canvas / artboard system already hosts **document viewports as
tabs** (MC-4, REQ-P4-UI-014). What is missing is the **visual-aids & UX layer** that helps an artist
*see and place* their work precisely: a **real-size preview window** that mirrors edits live,
**guides & rulers**, **isometric grids**, **perspective grids**, a **PureRef-style reference board**,
**multi-view editing** (several views of one document that stay in sync), and **timelapse
recording** of the edit session.

Phase 9 is the "high usability" milestone. Isometric / perspective grids + a reference board reach
**Pro Motion NG / PureRef-adjacent parity**, and the *integrated* reference board differentiates over
Aseprite / Pixelorama. Its defining acceptances are **geometric correctness** and **live
consistency**, and they are **testable**: the guides/rulers and the isometric/perspective grids
**compute their snap points from tested geometry logic** — `snap()` is a **pure, unit-testable
function** (given a cursor position and an isometric grid config, it returns the nearest grid vertex
per the documented transform; the perspective snap returns the nearest point on the nearest guide
within a tolerance); the **real-size scale** is a pure function of the document PPI and the screen
DPI; the **real-size preview mirrors edits live**; **multiple views of one document stay in sync**
(an edit is reflected in the preview and all views without a manual refresh); and a **timelapse
captures a reproducible frame sequence** of the edit session (replaying the recorded session yields
the same frame sequence).

These acceptances are only achievable if the **snap/geometry math** — isometric transforms,
perspective guide-line construction, guide snapping, ruler-tick computation, real-size scale, and the
reproducible timelapse frame-sequence model — is **pure `logic/` (zero Qt)** and therefore
**unit-testable** (this is precisely the point of the ROADMAP's "tested geometry logic"); while the
**rendering** — the overlays, the real-size preview window, the reference board, the multi-view
viewports, and the timelapse recording UI — lives in `ui/` (the only layer that imports Qt,
constitution Article I / S11). The geometry engine is **headless-drivable**, so the same pure snap
functions the overlays call are the ones the unit tests exercise.

This document specifies WHAT the visual-aids layer must do and WHY, technology-neutral at the
requirement level. The HOW — the **isometric default** (2:1 dimetric vs true-isometric), the
**timelapse capture strategy** (per-command vs time-based) + its **storage / encoding**, the exact
**DPI / real-size scaling specifics**, the **reference-board persistence format**, the **perspective
grid configuration** (1-/2-/3-point defaults), and the **snap-tolerance defaults** — are all
downstream (AGT-01 plan/ADR, grounded by the concurrent geometry-focused Researcher report,
DEP-1/DEP-2). Every geometry requirement is phrased around the **observable geometry contract** (the
documented transform / nearest-vertex / nearest-guide-within-tolerance / `f(PPI, DPI)` result), and
every live-consistency requirement around the **observable behaviour** (edit mirrors live; views stay
in sync; timelapse replays identically) — **not** a specific math constant or strategy — so choosing a
default does not change any acceptance criterion. This spec records the clarification defaults chosen
under the owner's autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**

- **`logic/grids.py` (new, Qt-free, unit-testable).** The **isometric grid transform** — a pure,
  documented, invertible mapping between document/pixel coordinates and isometric grid coordinates
  for a given grid config (REQ-P9-LOGIC-001) — and its **snap**: `snap(cursor, iso_config)` returns
  the **nearest grid vertex** per the documented transform (REQ-P9-LOGIC-002). The **perspective
  guide-line construction** — pure geometry that, from a vanishing-point configuration, produces the
  guide lines deterministically (REQ-P9-LOGIC-003) — and its **snap**: the perspective snap returns
  the **nearest point on the nearest guide within a tolerance** (beyond tolerance → no snap,
  REQ-P9-LOGIC-004). All pure `logic/`, zero Qt.
- **`logic/guides.py` (new, Qt-free, unit-testable).** **Guide/ruler snap geometry**: given a set of
  guides (horizontal / vertical / arbitrary) + a cursor + a tolerance, `snap()` returns the nearest
  guide point/intersection within tolerance (REQ-P9-LOGIC-005); and the **ruler tick / coordinate
  readout** computation — a pure function of document dimensions + zoom/offset producing the ruler
  ticks and the cursor's coordinate readout (REQ-P9-LOGIC-006).
- **`logic/preview.py` (new, Qt-free, unit-testable).** **Real-size scale computation**:
  `real_size_scale = f(document PPI, screen DPI)` — a pure function returning the scale factor that
  renders the document at physical real size (REQ-P9-LOGIC-007). The exact DPI/PPI scaling specifics
  are an AGT-01/ADR decision (DEP-2); the `f(PPI, DPI)` contract is fixed here.
- **`logic/timelapse.py` (new, Qt-free, unit-testable).** The **reproducible edit-session
  frame-sequence model**: an ordered record of the edit session such that **replaying the recorded
  session yields the same frame sequence** for the same recorded session (REQ-P9-LOGIC-010) —
  deterministic, deriving frames from the shipped deterministic edit history (HIS-1). The **capture
  strategy** (per-command vs time-based) and the **storage/encoding** are AGT-01/ADR decisions
  (DEP-2); the reproducibility contract is fixed here.
- **Geometry-engine purity & determinism.** The **entire** snap/geometry/scale/timelapse-model engine
  is pure `logic/`, **zero Qt**, headless-drivable and unit-testable (REQ-P9-LOGIC-008), and every
  snap/geometry result is a **deterministic** function of its inputs — no wall-clock, no randomness,
  no locale-dependent behaviour, no unordered iteration whose order can vary (REQ-P9-LOGIC-009).
- **Single-source-of-truth substrate for live mirror + multi-view.** All views and the real-size
  preview observe the **one shared `Document`** (DOC-1); no view holds an independent copy of pixel
  state — this shared-source invariant is the pure substrate that makes the live mirror and multi-view
  sync observable, and it is realised through the shipped reversible-command path (HIS-1)
  (REQ-P9-LOGIC-012).
- **`logic/constants.py` (extend).** New named bounds/defaults: `DEFAULT_ISO_GRID_RATIO` (**value set
  by AGT-01/ADR — the 2:1 dimetric vs true-iso choice, DEP-2**), `DEFAULT_SNAP_TOLERANCE_PX`,
  `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`,
  `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`, `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`
  (Article II). Exceeding a bound raises a domain error.
- **`data/` I/O (prefix flagged — PREFIX-NOTE).** Defensive, validated, **`eval`-free** serialisation
  of the recorded timelapse frame sequence and the reference-board layout through the `project_io.py`
  pattern (IO-3): every field type/bounds-checked, malformed input raises `ProjectIOError`, **never
  `eval`/`exec`**, portable paths.
- **`ui/` visual-aids surfaces (the only Qt).** A **real-size preview window** rendering the document
  at physical real size using the pure scale (REQ-P9-UI-001) that **mirrors edits live**
  (REQ-P9-UI-002); a **guides & rulers** overlay (create/move/remove guides; rulers show coordinates;
  cursor snaps via the pure snap, REQ-P9-UI-003); an **isometric grid** overlay (renders the grid
  from the pure transform; cursor snaps to vertices, REQ-P9-UI-004); a **perspective grid** overlay
  (renders guide lines from the pure construction; cursor snaps to the nearest guide,
  REQ-P9-UI-005); a **PureRef-style reference board** (add / arrange / zoom reference images,
  non-destructive, not part of the document canvas, REQ-P9-UI-006); **multi-view editing** — several
  views of **one** document (REQ-P9-UI-007) that **stay in sync** (REQ-P9-UI-008); and **timelapse
  recording** controls producing the reproducible frame sequence (REQ-P9-UI-009). The UI hosts
  **rendering + overlays + controls only** and calls the **same** pure `logic/` geometry the unit
  tests drive; **no** snap/geometry/scale math lives in `ui/` (Article I).

**Out of scope (this phase):** see §6 Non-goals. Notably: **choosing the isometric default** (2:1
dimetric vs true-iso) → AGT-01 plan/ADR (Researcher, DEP-1/DEP-2); the **timelapse capture strategy**
(per-command vs time-based) + **storage/encoding** → AGT-01/ADR (DEP-2); the **DPI/real-size scaling
specifics** → AGT-01/ADR (DEP-2); the **reference-board persistence format** → AGT-01/ADR (DEP-2);
the **perspective grid configuration** (1-/2-/3-point defaults) and **snap-tolerance defaults** →
AGT-01 (DEP-2); whether long-running timelapse capture / encoding runs on a **worker thread** (HOW)
→ AGT-01/AGT-10 (DEP-3); the **render/perf strategy** for holding the frame budget with overlays +
multi-view (culling, dirty-rect, overlay batching) → AGT-10 (DEP-3). Also out: **exporting** the
timelapse to a video/GIF file as a production format (Phase-7 export handoff — Phase 9 produces the
reproducible *sequence*; a shared export pipeline may consume it later); a **hosted reference-image
library / cloud sync** → Phase 10 (CL-16); **AI-assisted perspective inference** → later phase. No
plan/tasks/code (AGT-01/03/05); no new technology (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Artist / real-size-preview).** As an artist, I want a **real-size preview window** showing
  my art at its true physical size so I can judge how it will actually look. → REQ-P9-LOGIC-007,
  REQ-P9-UI-001 · `real-size-preview` · P9
- **US-2 (Artist / live-mirror).** As an artist, I want the real-size preview to **mirror my edits
  live** so I never have to refresh it manually. → REQ-P9-LOGIC-012, REQ-P9-UI-002 · `live-mirror` · P9
- **US-3 (Artist / guides-rulers).** As an artist, I want **guides and rulers** with coordinate
  readouts, and my cursor to **snap to guides**, so I can align elements precisely. →
  REQ-P9-LOGIC-005, -006, REQ-P9-UI-003 · `guides-rulers` · P9
- **US-4 (Isometric artist / iso-grid).** As an isometric artist, I want an **isometric grid** whose
  vertices my cursor **snaps to** per a correct transform, so my iso art stays on-grid. →
  REQ-P9-LOGIC-001, -002, REQ-P9-UI-004 · `isometric-grid` · P9
- **US-5 (Perspective artist / perspective-grid).** As a perspective artist, I want a **perspective
  grid** whose guide lines my cursor **snaps to** (the nearest guide within tolerance), so I can draw
  in correct perspective. → REQ-P9-LOGIC-003, -004, REQ-P9-UI-005 · `perspective-grid` · P9
- **US-6 (Any user / tested-geometry).** As a user, I want the grids' and guides' snap points to come
  from **tested geometry logic** (pure, deterministic, unit-tested), so snapping is correct and
  reliable rather than a fragile UI hack. → REQ-P9-LOGIC-008, -009 · `tested-geometry` · P9
- **US-7 (Artist / reference-board).** As an artist, I want an integrated **PureRef-style reference
  board** where I can add, arrange, and zoom reference images alongside my canvas, without them
  becoming part of my artwork. → REQ-P9-UI-006 · `reference-board` · P9
- **US-8 (Artist / multi-view).** As an artist, I want **multiple views of one document** (e.g. a
  zoomed-in detail view + a fit-to-window view) open at once. → REQ-P9-LOGIC-012, REQ-P9-UI-007
  · `multi-view` · P9
- **US-9 (Artist / views-in-sync).** As an artist, I want **all views of a document to stay in sync**
  — an edit in one appears in every view and the preview without a manual refresh. →
  REQ-P9-LOGIC-012, REQ-P9-UI-008 · `views-in-sync` · P9
- **US-10 (Content creator / timelapse).** As a content creator, I want to **record a timelapse** of
  my edit session as a **reproducible frame sequence** so I can share how a piece was made. →
  REQ-P9-LOGIC-010, REQ-P9-UI-009 · `timelapse` · P9
- **US-11 (Content creator / reproducible-timelapse).** As a content creator, I want a recorded
  timelapse **replayed to yield the same frame sequence** for the same recorded session, so my
  capture is deterministic and reliable. → REQ-P9-LOGIC-010 · `reproducible-timelapse` · P9
- **US-12 (Any user / non-destructive-aids).** As a user, I want guides, grids, the reference board,
  and the preview to be **view aids that never alter my artwork** and leave no undo entry. →
  REQ-P9-UI-010 · `non-destructive-aids` · P9
- **US-13 (Any user / smooth).** As a user with overlays + multiple views open on a large (up to 8K)
  canvas, I want drawing to **stay smooth** (the frame budget still holds) rather than stuttering. →
  REQ-P9-UI-011 · `render-budget` · P9
- **US-14 (Any user / bounded).** As a user, I want the aids **bounded** (max guides, reference
  images, timelapse frames, simultaneous views, grid spacing) so nothing runs away. →
  REQ-P9-LOGIC-011 · `bounded-aids` · P9
- **US-15 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English user, I
  want the visual-aids panels **keyboard-reachable, correct in both themes, fully translatable**. →
  REQ-P9-UI-012, -013, -014 · `a11y`, `theming`, `i18n` · P9

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `real-size-preview` | A preview window rendering the document at physical real size via `f(PPI, DPI)`. | 9 |
| `live-mirror` | The real-size preview reflects edits live, no manual refresh (shared DOC-1). | 9 |
| `guides-rulers` | Guides + rulers with coordinate readout; cursor snaps to guides (pure geometry). | 9 |
| `isometric-grid` | Isometric grid transform + snap to nearest grid vertex (pure, documented). | 9 |
| `perspective-grid` | Perspective guide-line construction + snap to nearest guide within tolerance. | 9 |
| `tested-geometry` | Snap/geometry math is pure, deterministic `logic/`, unit-testable (zero Qt). | 9 |
| `reference-board` | PureRef-style board: add/arrange/zoom reference images; non-destructive. | 9 |
| `multi-view` | Multiple views of ONE document (distinct from Phase-4 multi-canvas tabs). | 9 |
| `views-in-sync` | An edit reflects in the preview and all views without manual refresh. | 9 |
| `timelapse` | Recording of the edit session as a frame sequence. | 9 |
| `reproducible-timelapse` | A replayed recorded session yields the same frame sequence. | 9 |
| `non-destructive-aids` | Guides/grids/board/preview never mutate the document; no undo entry. | 9 |
| `render-budget` | Overlays + multi-view rendering hold the 16 ms frame budget (Article VI). | 9 |
| `bounded-aids` | Named bounds on guides / references / timelapse frames / views / grid spacing. | 9 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 9 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-9 capability +
forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a fixed shipped callable is named as a **constraint**, not a HOW decision. **[GEO]** marks
a **tested-geometry** requirement — a pure, unit-testable snap/geometry contract (the phase's
defining acceptance backbone; drives AGT-04 unit + Hypothesis tests).

### `logic/grids.py` — isometric grid + perspective guides (new, pure geometry)

#### REQ-P9-LOGIC-001 — Isometric grid transform is a pure, documented, invertible mapping **[GEO]**
`traces:` Phase-9 capability (isometric grids), P2 (determinism), S11, F (iso transform math)
The isometric grid transform is a **pure function** mapping between document/pixel coordinates and
isometric grid coordinates for a given **grid config** (origin, spacing, ratio) **per a documented
transform**. The mapping is **invertible** (grid→pixel→grid round-trips to the same grid coordinate)
and **deterministic** (REQ-P9-LOGIC-009). It lives in `logic/` with **zero Qt**. The concrete
isometric **default ratio** (2:1 dimetric vs true-isometric) is an AGT-01/ADR decision fixed in
`DEFAULT_ISO_GRID_RATIO` (DEP-2, Researcher-grounded); the transform contract — a documented,
invertible, pure mapping — is fixed here and does not change with the chosen ratio.

#### REQ-P9-LOGIC-002 — Isometric snap returns the nearest grid vertex **[GEO]**
`traces:` **DOC-1**, Phase-9 capability (isometric snap), P2, S11
`snap(cursor_position, iso_grid_config)` returns the **nearest isometric grid vertex** to the cursor
per the documented transform (REQ-P9-LOGIC-001) — a **pure, unit-testable** function of
`(cursor, config)`, with a well-defined tie-break so it is deterministic (REQ-P9-LOGIC-009). This is
the "compute snap points from tested geometry logic" contract for isometric grids. The snap does
**not** import Qt and is exercised directly by unit tests without any GUI.

#### REQ-P9-LOGIC-003 — Perspective guide-line construction is pure geometry **[GEO]**
`traces:` Phase-9 capability (perspective grids), P2, S11, F (perspective construction)
Given a **vanishing-point configuration** (1-/2-/3-point, vanishing-point positions, horizon), the
perspective grid's **guide lines are constructed deterministically** by a pure function — the set of
guide lines is a documented function of the configuration. The number of vanishing points is bounded
by `MAX_PERSPECTIVE_VANISHING_POINTS` (REQ-P9-LOGIC-011). Zero Qt. The concrete **default
configuration** (how many points, default positions) is an AGT-01/ADR decision (DEP-2); the
construction contract — deterministic guide lines from a config — is fixed here.

#### REQ-P9-LOGIC-004 — Perspective snap returns the nearest point on the nearest guide within tolerance **[GEO]**
`traces:` Phase-9 capability (perspective snap), P2, S11, F (snap tolerance)
`snap(cursor_position, perspective_config, tolerance)` returns the **nearest point on the nearest
constructed guide line** (REQ-P9-LOGIC-003) **when that point is within `tolerance`**, and returns
**no snap** when the nearest guide is beyond tolerance — a **pure, unit-testable** function with a
deterministic tie-break (REQ-P9-LOGIC-009). The default tolerance is `DEFAULT_SNAP_TOLERANCE_PX`
(REQ-P9-LOGIC-011). This is the "compute snap points from tested geometry logic" contract for
perspective grids.

### `logic/guides.py` — guides / rulers snap geometry (new, pure geometry)

#### REQ-P9-LOGIC-005 — Guide/ruler snap returns the nearest guide point within tolerance **[GEO]**
`traces:` Phase-9 capability (guides & rulers), P2, S11
Given a set of **guides** (horizontal / vertical / arbitrary lines) + a cursor + a tolerance,
`snap()` returns the **nearest guide point or guide intersection within the tolerance**, and no snap
beyond it — a **pure, unit-testable, deterministic** function of `(guides, cursor, tolerance)`
(REQ-P9-LOGIC-009). Guide count is bounded by `MAX_GUIDES` (REQ-P9-LOGIC-011). Zero Qt.

#### REQ-P9-LOGIC-006 — Ruler ticks & coordinate readout are computed from tested geometry **[GEO]**
`traces:` Phase-9 capability (rulers), P2, S11
The **ruler tick positions/labels** and the **cursor coordinate readout** are a **pure, deterministic
function** of `(document dimensions, zoom, view offset)` — computed in `logic/`, not ad-hoc in the
widget. Given the same view parameters the ruler produces the same ticks and the same readout, so the
ruler is unit-testable independently of Qt.

### `logic/preview.py` — real-size scale (new, pure geometry)

#### REQ-P9-LOGIC-007 — Real-size scale is a pure function of document PPI and screen DPI **[GEO]**
`traces:` Phase-9 capability (real-size preview), P2, S11, F (DPI scaling)
`real_size_scale = f(document PPI, screen DPI)` is a **pure, deterministic** function returning the
scale factor at which the document renders at its **physical real size** on a screen of a given DPI.
Given the document's PPI and the screen's DPI it always returns the same factor; the preview window
renders the composited document (CO-4) at that scale (REQ-P9-UI-001). The exact **DPI/PPI scaling
specifics** are an AGT-01/ADR decision (DEP-2); the `f(PPI, DPI)` contract — and that the document
carries (or is assigned, defaulting to `DEFAULT_DOCUMENT_PPI`) a PPI — is fixed here (see BF-3 §8 for
the data-model note if `Document` lacks a PPI attribute).

### `logic/timelapse.py` — reproducible session frame-sequence model (new)

#### REQ-P9-LOGIC-010 — Timelapse captures a reproducible frame sequence of the edit session **[GEO]**
`traces:` **HIS-1** (reversible-command path, forward-inherited), P2 (determinism), Phase-9 capability (timelapse), S11
A timelapse is a **reproducible frame-sequence model** of the edit session: **replaying the recorded
session yields the same frame sequence** for the same recorded session — a **deterministic** function
of the recorded session (it derives frames from the shipped deterministic edit history, HIS-1, using
**no** wall-clock time / randomness / locale-dependent behaviour beyond values explicitly recorded,
REQ-P9-LOGIC-009). Recording the same session and replaying it **twice** yields the **same frame
sequence** each time. Frame count is bounded by `MAX_TIMELAPSE_FRAMES` (REQ-P9-LOGIC-011). The
**capture strategy** (per-command vs time-based) and the **storage/encoding** are AGT-01/ADR
decisions (DEP-2); the reproducibility contract is fixed here.

### Purity, determinism, single-source, bounds (new)

#### REQ-P9-LOGIC-008 — The snap/geometry/scale/timelapse engine is pure `logic/`, Qt-free, unit-testable **[GEO]**
`traces:` Article I, S11, Phase-9 capability
The **entire** snap/geometry engine — isometric transform + snap, perspective construction + snap,
guide/ruler snap + tick computation, real-size scale, and the timelapse frame-sequence model — lives
in `logic/` with **zero Qt imports** and is **drivable without any GUI or event loop**, so the same
pure functions the overlays call are exercised directly by unit tests. This is the ROADMAP's "tested
geometry logic" (the snap math is pure, unit-testable). Enforced by `check_layering` /
`check_cycles`; the only Qt file outside `ui/` remains `ui/commands.py`. The **rendering** of grids /
guides / preview / reference board / views lives in `ui/` and imports the pure geometry — it does
**not** re-implement any snap/geometry math (Article I).

#### REQ-P9-LOGIC-009 — All snap/geometry results are deterministic **[GEO]**
`traces:` P2 (determinism), S6, S11
Every snap/geometry/scale/timelapse result is a **pure, deterministic function** of its inputs: it
uses **no wall-clock time, no randomness, no locale-dependent formatting, and no unordered iteration**
whose order can vary, and every nearest-point/vertex selection has a **well-defined tie-break** so the
same inputs always yield the same output. This determinism is what makes the geometry unit-testable
(REQ-P9-LOGIC-008) and backs the reproducible timelapse (REQ-P9-LOGIC-010).

#### REQ-P9-LOGIC-011 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The visual-aids engine enforces named bounds/defaults defined once in `logic/constants.py`:
`DEFAULT_ISO_GRID_RATIO` (**value set by AGT-01/ADR — 2:1 dimetric vs true-iso, DEP-2**),
`DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`,
`MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`,
`MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`. Exceeding a bound raises a domain error rather than
degrading silently. No numeric literals in `logic/`/`data/`/`ui/` (Article II).

#### REQ-P9-LOGIC-012 — One shared document is the source of truth for all views and the preview
`traces:` **DOC-1**, **HIS-1**, Article I, Phase-9 capability (multi-view / live-mirror), S11
All views of a document **and** the real-size preview observe the **one shared `Document`** (DOC-1);
**no** view holds an independent copy of the pixel/layer state. An edit is a single mutation on that
shared document through the reversible-command path (HIS-1), from which every view and the preview
derive — this shared-source invariant is the **pure substrate** that makes the live mirror
(REQ-P9-UI-002) and multi-view sync (REQ-P9-UI-008) observable without any per-view state
duplication or manual refresh. Simultaneous views of one document are bounded by `MAX_DOCUMENT_VIEWS`
(REQ-P9-LOGIC-011). **NB:** this is distinct from Phase-4 multi-**canvas** (MC-4), where each tab is
an **isolated** *different* document; here many views share **one** document (see §7).

### `ui/` — preview window, overlays, reference board, multi-view, timelapse controls

#### REQ-P9-UI-001 — Real-size preview window renders the document at physical real size
`traces:` REQ-P9-LOGIC-007
A **real-size preview window** renders the composited document (CO-4) at the scale returned by the
pure real-size scale function (REQ-P9-LOGIC-007) so the artwork appears at its true physical size.
The window adds **no** scaling math of its own (Article I); it applies the `logic/` scale.

#### REQ-P9-UI-002 — The real-size preview mirrors edits live (no manual refresh)
`traces:` REQ-P9-LOGIC-012, S7
An edit to the document is **reflected in the real-size preview live** — without any manual refresh —
because the preview observes the one shared document (REQ-P9-LOGIC-012). Drawing on the canvas updates
the preview as part of the same edit; the preview is **read-only** (viewing it never mutates the
document, REQ-P9-UI-010).

#### REQ-P9-UI-003 — Guides & rulers overlay with coordinate readout and snapping
`traces:` REQ-P9-LOGIC-005, -006
The UI shows **rulers** with a live coordinate readout (computed by REQ-P9-LOGIC-006) and lets the
user **create / move / remove guides**; the cursor **snaps to guides** using the pure guide snap
(REQ-P9-LOGIC-005). The overlay **renders** the guides/ticks and calls the `logic/` snap — it does
not compute snap points itself (Article I). Guides are view state (REQ-P9-UI-010).

#### REQ-P9-UI-004 — Isometric grid overlay with snap-to-vertex
`traces:` REQ-P9-LOGIC-001, -002
The UI renders an **isometric grid** from the pure transform (REQ-P9-LOGIC-001) and the cursor
**snaps to the nearest grid vertex** via the pure snap (REQ-P9-LOGIC-002). Grid spacing/config is
bounded (`MIN_GRID_SPACING`/`MAX_GRID_SPACING`, REQ-P9-LOGIC-011). The overlay renders and calls the
`logic/` geometry; it re-implements none of it (Article I). Translatable labels.

#### REQ-P9-UI-005 — Perspective grid overlay with snap-to-guide
`traces:` REQ-P9-LOGIC-003, -004
The UI renders a **perspective grid** — guide lines from the pure construction (REQ-P9-LOGIC-003) —
and the cursor **snaps to the nearest guide within tolerance** via the pure snap (REQ-P9-LOGIC-004);
beyond tolerance there is no snap. The user configures the vanishing points (bounded by
`MAX_PERSPECTIVE_VANISHING_POINTS`). Rendering only; geometry is `logic/` (Article I).

#### REQ-P9-UI-006 — Reference board (PureRef-style): add / arrange / zoom, non-destructive
`traces:` Phase-9 capability (reference board), S6
The UI provides a **PureRef-style reference board** where the user can **add, arrange (move/resize),
and zoom** reference images alongside the canvas. Reference images are **not part of the document
canvas** — they never composite into the artwork and never appear in an export — and are bounded by
`MAX_REFERENCE_IMAGES` (REQ-P9-LOGIC-011). The board layout **persists** via a defensive `eval`-free
serialiser (IO-3, prefix flagged — PREFIX-NOTE §7); a malformed board file surfaces a user-facing
error, not a crash or arbitrary execution. Translatable labels.

#### REQ-P9-UI-007 — Multi-view editing: multiple views of one document
`traces:` REQ-P9-LOGIC-012, **MC-4** (Phase-4 viewport/tab system, forward-inherited)
The UI lets the user open **multiple views of the same document** (e.g. a zoomed detail view and a
fit-to-window overview) at once — **building on** the Phase-4 multiple-canvas / artboard viewport
infrastructure (MC-4) but with all views bound to **one shared document** (REQ-P9-LOGIC-012), not
isolated separate documents (§7). Each view has its own zoom/pan; the underlying document is shared.
Simultaneous views are bounded by `MAX_DOCUMENT_VIEWS`.

#### REQ-P9-UI-008 — Multiple views of one document stay in sync
`traces:` REQ-P9-LOGIC-012, S7
An edit made in one view is **reflected in every other view of that document and in the real-size
preview — without a manual refresh** (they all derive from the one shared document,
REQ-P9-LOGIC-012). View-local state (each view's own zoom/pan/scroll) is **independent** and is
**not** synced. This is the ROADMAP "multiple views of one document stay in sync" contract.

#### REQ-P9-UI-009 — Timelapse recording controls produce a reproducible frame sequence
`traces:` REQ-P9-LOGIC-010
The UI lets the user **start / stop** timelapse recording over an edit session; the result is the
reproducible frame sequence (REQ-P9-LOGIC-010) — replaying the recorded session yields the same frame
sequence. Recording state is view/session state (no undo entry, REQ-P9-UI-010). The concrete capture
strategy + storage/encoding are AGT-01/ADR (DEP-2); a failed recording (e.g. an unwritable path)
surfaces a user-facing error. Translatable labels.

#### REQ-P9-UI-010 — Visual aids are non-destructive; aid/view state is not undoable
`traces:` S7, C1, F1
Guides, rulers, the isometric/perspective grids, the reference board, the real-size preview, the
extra views, and timelapse recording are **view/session aids that never mutate the document** —
enabling a grid, creating a guide, adding a reference image, opening a view, or starting recording
pushes **no `QUndoCommand`** and leaves the artwork/undo history untouched. (Only actual **drawing**
edits — which already go through the shipped HIS-1 path — are undoable, and those are unchanged by
Phase 9.) Viewing the preview or a second view never alters the document.

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P9-UI-011 — Overlays + multi-view rendering hold the 16 ms frame budget *(NFR, Article VI)*
`traces:` S1, S12, Article VI, DEP-3
Rendering the visual aids **on the canvas render loop** — the isometric/perspective grid overlays,
the guides/rulers overlay, and each open view of an up-to-8K (7680 × 4320) document — **holds the
16 ms `FRAME_BUDGET_MS`** (Article VI, 60 fps). **NB (key distinction from Phases 7–8):** unlike
export/automation, these overlays and additional viewports are part of the **per-frame render loop**,
so the 16 ms budget **does** apply. The real-size preview mirroring and timelapse frame capture must
also keep the UI **responsive** (no freeze); whether long-running timelapse capture/encoding runs
**off the GUI thread**, and the **render/perf strategy** (overlay batching, tile-culling, dirty-rect
partial redraw for the extra views) are HOW decisions owned by **AGT-10** (render-strategy) /
AGT-01 (DEP-3) — this spec fixes only the observable budget-holds + stays-responsive contract.

#### REQ-P9-UI-012 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive visual-aids control (guide/ruler toggles + guide handles, isometric/perspective
grid enable + config fields, reference-board add/arrange controls, view-open controls, timelapse
record/stop, real-size preview window) exposes an accessible name and, where non-obvious, an
accessible description; is reachable and operable by keyboard (logical tab order + shortcuts); and
shows a visible focus indicator. Verified by AGT-06 (`a11y-audit`).

#### REQ-P9-UI-013 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The preview window, guides/rulers overlay, isometric/perspective grid overlays, reference board,
multi-view viewports, and timelapse controls render correctly in both light and dark themes; overlay
and guide colours are defined once by role (never hard-coded per widget) and remain legible over
artwork in both themes. Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-P9-UI-014 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 9 (grid/guide/ruler labels + tooltips, perspective config
labels, reference-board labels, view titles, timelapse control text + units, dialog titles, error
messages) is wrapped in `tr()` / `translate()`; none is a bare literal. Hand-built widgets re-set text
on `QEvent.LanguageChange`. Verified by `string_audit_check` (AGT-07); an unwrapped string is a
blocking finding.

## 6. Non-goals (explicit; deferred)

- **Isometric default choice** (2:1 dimetric vs true-isometric) — **AGT-01 plan/ADR**, grounded by
  the geometry-focused Researcher (DEP-1/DEP-2), fixed in `DEFAULT_ISO_GRID_RATIO`. The transform +
  snap contract is fixed (REQ-P9-LOGIC-001/-002).
- **Timelapse capture strategy** (per-command vs time-based) + **storage/encoding** — AGT-01/ADR
  (DEP-2). The reproducibility contract (replay yields the same frame sequence) is fixed
  (REQ-P9-LOGIC-010).
- **DPI/real-size scaling specifics** — AGT-01/ADR (DEP-2). The `f(document PPI, screen DPI)` contract
  is fixed (REQ-P9-LOGIC-007).
- **Reference-board persistence format** — AGT-01/ADR (DEP-2). The WHAT (defensive `eval`-free
  persistence, non-destructive board) is fixed (REQ-P9-UI-006).
- **Perspective grid configuration defaults** (1-/2-/3-point default set, default positions) +
  **snap-tolerance defaults** — AGT-01 (DEP-2); the construction + nearest-guide-within-tolerance
  contract is fixed (REQ-P9-LOGIC-003/-004).
- **Whether timelapse capture/encoding runs on a worker thread**, and the **render/perf strategy** for
  holding the frame budget with overlays + multi-view (culling / dirty-rect / overlay batching) —
  AGT-01/**AGT-10** (DEP-3); this spec fixes only the budget-holds + responsiveness contract
  (REQ-P9-UI-011).
- **Exporting the timelapse to a video/GIF production file** — Phase 9 produces the **reproducible
  frame sequence**; encoding it as a shareable video/GIF is an export concern that may reuse the
  Phase-7 pipeline later (handoff), not a Phase-9 acceptance.
- **A hosted reference-image library / cloud reference sync** — Phase 10 (Cloud & Collaboration,
  CL-16). Phase 9 ships a **local** reference board.
- **AI-assisted perspective inference / auto-vanishing-point detection** → later phase.
- **Re-implementing compositing, the command pattern, or the tab/viewport system** — the preview and
  views compose `blend.composite_stack` (CO-4) over the shared `Document` (DOC-1) through the shipped
  `history` path (HIS-1) and build on the Phase-4 viewport system (MC-4); no re-implementation
  (Article I).
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`,
  `specs/phase-4-layer-canvas/`): the `Document` tree (DOC-1 — the single shared subject every view +
  the preview observes), `PixelBuffer` (PB-1 — the pixels the preview mirrors), the `history`
  reversible-command path (HIS-1 — edits mirror live + back reproducible timelapse),
  `blend.composite_stack` (CO-4 — the composited image the preview + views render), the Phase-4
  multiple-canvas / artboard viewport/tab system (MC-4, REQ-P4-UI-014 / CL-15 — multi-**view** builds
  on it), the `data/project_io.py` defensive-load pattern (IO-3 — timelapse / reference-board
  persistence). Phase 9 **composes** these; it must not re-implement compositing, the command
  pattern, the viewport system, or the JSON-load security posture (Article I / VII).
- **Multi-VIEW vs multi-CANVAS (the ROADMAP dependency, made explicit).** Phase-4 multi-**canvas**
  (MC-4) opens **isolated** *different* documents as tabs — each tab owns its own layer tree +
  `QUndoStack` + composite (Phase-4 CL-15). Phase-9 multi-**view** opens **multiple views of the
  SAME document** that **stay in sync** (REQ-P9-UI-007/-008). Multi-view *builds on* the Phase-4
  viewport infrastructure (the ROADMAP "multi-view builds on tabs/artboards") but shares **one**
  `Document` (REQ-P9-LOGIC-012) — it does **not** respecify Phase 4. This is the central
  disambiguation for AGT-01.
- **NEW vs REUSED (explicit):**
  - **NEW:** `logic/grids.py` (isometric transform + snap, perspective construction + snap),
    `logic/guides.py` (guide/ruler snap + tick computation), `logic/preview.py` (real-size scale),
    `logic/timelapse.py` (reproducible frame-sequence model), new constants
    (`DEFAULT_ISO_GRID_RATIO`, `DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`, `MAX_GRID_SPACING`,
    `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`,
    `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`), all visual-aids UI (preview window, overlays,
    reference board, multi-view viewports, timelapse controls), and the `data/` timelapse +
    reference-board serialisers.
  - **REUSED (not re-authored):** the `Document` tree (DOC-1), `PixelBuffer` (PB-1), the `history`
    command path (HIS-1), `blend.composite_stack` (CO-4), the Phase-4 viewport/tab system (MC-4), the
    `project_io.py` defensive-load pattern (IO-3).
- The visual aids are **non-destructive** (REQ-P9-UI-010): unlike Phases 4/5/6/8, Phase 9 adds
  **no** editing logic to `ui/commands.py` — grids/guides/board/preview/views/timelapse are view aids,
  not undoable edits. Only the existing drawing edits (HIS-1) mutate the document.
- The GUI holds each view's local zoom/pan + the chosen aid configuration (view state); it calls the
  pure `logic/` geometry — the **same** functions the unit tests drive — the foundation of
  REQ-P9-LOGIC-008.
- **PREFIX-NOTE (data-layer prefix — flagged, not blocking).** The ROADMAP reserved only
  `REQ-P9-LOGIC-*` and `REQ-P9-UI-*` for Phase 9; **no `REQ-P9-DATA-*`**. Phase 9 has **two** genuine
  data-layer persistence concerns: (a) the **timelapse frame-sequence** persistence, and (b) the
  **reference-board layout** persistence. Rather than invent a `REQ-P9-DATA-*` prefix, this spec
  phrases each around its **observable contract** — the timelapse's reproducibility inside
  REQ-P9-LOGIC-010 and its defensive `eval`-free persistence via IO-3, the reference board's
  non-destructive defensive persistence inside REQ-P9-UI-006. **Proposal to the orchestrator /
  AGT-01:** allocate a `REQ-P9-DATA-*` prefix at plan time (Phase 9's *two* persistence concerns make
  a data-layer prefix more clearly warranted than Phase 8's single serialiser), or keep them folded
  under REQ-P9-LOGIC-010 / REQ-P9-UI-006. Either way the acceptance (defensive, `eval`-free,
  round-trip, non-destructive) is **fixed and unchanged** — a prefix/placement decision, **not** a
  functional ambiguity. Tracked as DEP-4 (§8).

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-1 (Researcher, grounding — GEOMETRY-FOCUSED).** `docs/research-phase9-visual-aids.md` grounds
  the **isometric transform math** (2:1 dimetric vs true-iso), the **perspective guide-line
  construction** (1-/2-/3-point vanishing-point geometry), the **real-size DPI/PPI scaling**
  conventions, the **snap algorithm + tolerance** norms, the **timelapse capture strategy** (per-command
  vs time-based) + storage/encoding landscape, and the **reference-board** (PureRef) landscape.
  **Being produced in parallel** (per the owner directive) and feeds AGT-01. AGT-01's `sdd-plan` must
  not invent the geometry math — it consumes the Researcher's findings. The *observable geometry +
  behaviour contracts* and the clarification defaults are fixed here regardless (§10).
- **DEP-2 (AGT-01, plan/ADR).** (a) the **isometric default** (2:1 dimetric vs true-iso) →
  `DEFAULT_ISO_GRID_RATIO`; (b) the **timelapse capture strategy** (per-command vs time-based) +
  **storage/encoding**; (c) the **DPI/real-size scaling specifics** (`f(PPI, DPI)` realisation);
  (d) the **reference-board persistence format**; (e) the **perspective grid configuration** (1-/2-/3-
  point defaults, default positions); (f) the **snap-tolerance defaults**. Each is a HOW decision; the
  observable contracts (documented invertible transform; nearest-vertex/nearest-guide-within-tolerance
  snap; `f(PPI, DPI)` scale; live mirror; views in sync; reproducible timelapse) are fixed here. An
  ADR is expected for the geometry model (a/e) with the Researcher as grounding.
- **DEP-3 (AGT-01 / AGT-10, plan — RENDER PERFORMANCE, applies here unlike Phases 7–8).** The
  **render/perf strategy** for holding the 16 ms frame budget with the grid/guide overlays + multiple
  8K views (overlay batching, viewport tile-culling, dirty-rect partial redraw) is an **AGT-10**
  render-strategy decision (REQ-P9-UI-011); whether long-running timelapse capture/encoding runs on a
  **worker thread** is an AGT-01/AGT-10 HOW. Unlike export/automation, Phase-9 overlays/views are on
  the **per-frame render loop**, so Article VI's 16 ms budget **does** apply — coordinate with AGT-10.
- **BF-1 (AGT-01, Article II).** New tuning values (`DEFAULT_ISO_GRID_RATIO`,
  `DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`,
  `MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`,
  `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`) must resolve to named constants in
  `logic/constants.py`; no literals. `DEFAULT_ISO_GRID_RATIO`'s **value** is the AGT-01/ADR iso-default
  decision (DEP-2a).
- **BF-2 (AGT-01, plan).** The exact **module split** of the geometry engine (whether iso + perspective
  share `logic/grids.py` or split; whether real-size scale folds into an existing module) is a HOW
  placement decision — the constraint is only that **all** snap/geometry/scale/timelapse math is
  Qt-free `logic/` and unit-testable (REQ-P9-LOGIC-008), and the overlays re-implement none of it.
- **BF-3 (AGT-01, data-model).** Real-size scale needs a document **PPI**. If the shipped Phase-1
  `Document` does **not** carry a PPI attribute, AGT-01 adds one at plan time (a small data-model
  addition) defaulting to `DEFAULT_DOCUMENT_PPI`. **Not acceptance-changing** — the `f(PPI, DPI)`
  contract (REQ-P9-LOGIC-007) holds regardless of where the PPI is sourced; recorded as CL-3 default.
- **DEP-4 (AGT-01 / orchestrator, prefix allocation).** Per PREFIX-NOTE (§7): decide whether the
  **timelapse** and **reference-board** serialisers get their own `REQ-P9-DATA-*` REQ(s) at plan time
  or stay folded under REQ-P9-LOGIC-010 / REQ-P9-UI-006. Phase 9's **two** persistence concerns make a
  DATA prefix more clearly warranted than Phase 8's single serialiser. **Not acceptance-changing** —
  the defensive/`eval`-free/round-trip/non-destructive contract is fixed regardless.

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/grids.py`, `logic/guides.py`, `logic/preview.py`,
  `logic/timelapse.py`, and the new constants are pure Python, **zero Qt** — this is what makes the
  snap/geometry "tested geometry logic" (unit-testable without a GUI); the timelapse + reference-board
  serialisers live in `data/` (zero Qt); all overlays / preview window / reference board / multi-view
  / timelapse UI live in `ui/`. Phase 9 adds **no** `ui/commands.py` logic (visual aids are
  non-destructive, REQ-P9-UI-010). Enforced by `check_layering` / `check_cycles`.
- **Article II (numerics):** new tuning values go in `logic/constants.py` (BF-1); no literals in
  `ui/`/`logic/`/`data/`. `DEFAULT_ISO_GRID_RATIO`'s value is the AGT-01/ADR iso-default (DEP-2a).
- **Article IV (testing):** the isometric transform (invertible) + snap-to-vertex, perspective
  construction + snap-to-guide-within-tolerance, guide snap, ruler-tick computation, real-size scale
  `f(PPI, DPI)`, geometry determinism, reproducible timelapse, and the shared-source live-mirror /
  multi-view-sync invariant each get a scenario → one pytest / Hypothesis test (logic, headless,
  **unit-testable geometry** — the `[GEO]` rows drive dedicated AGT-04 geometry + property tests) or
  pytest-qt test (UI), both themes for UI. Coverage gate ≥90/80.
- **Article V (UX):** REQ-P9-UI-012/-013/-014 make a11y + both themes + full translatability blocking
  gates for the visual-aids UI (overlay/guide colours legible over artwork in both themes).
- **Article VI (performance) — APPLIES THIS PHASE (unlike Phases 7–8):** REQ-P9-UI-011 binds the
  **16 ms `FRAME_BUDGET_MS`** to overlay + multi-view rendering because these are on the **per-frame
  render loop** (not batch work); the render/perf strategy is AGT-10's (DEP-3).
- **Article VII (security):** the timelapse + reference-board load is defensive, validated,
  **`eval`-free** (IO-3); malformed input raises `ProjectIOError` and surfaces a user-facing error;
  bounded numerics (REQ-P9-LOGIC-011); portable paths (`path_portability_check`).
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited primitive
  (DOC-1, PB-1, HIS-1, CO-4, MC-4, IO-3); forward matrix in `traceability.md`.
- **Article XI (extensibility):** deferring timelapse video export, a hosted reference library / cloud
  sync (Phase 10, CL-16), and AI perspective inference adds capability later without weakening any
  article.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with sensible
defaults grounded in the ROADMAP "Done means", the shipped code, the constitution, and mainstream
visual-aid norms (**Pro Motion NG** iso/perspective grids, **PureRef** reference board, **Aseprite**
guides/rulers/timelapse). Each is a **category-1 decision** (A2-D2 Branch B). **No open clarification
blocks planning.** Genuinely acceptance-changing geometry ambiguities are addressed in
**SUSPEND / escalate** below.

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Where does the snap/geometry math live? | **Pure `logic/`, zero Qt, unit-testable** (`logic/grids.py` / `guides.py` / `preview.py` / `timelapse.py`); the overlays/preview/board/views/timelapse *render* in `ui/` and call the pure geometry. | ROADMAP "compute snap points from tested geometry logic"; Article I / S11 (only `ui/` imports Qt). |
| **CL-2** | Which **isometric default** (2:1 dimetric vs true-iso)? | **DEFERRED to AGT-01/ADR** (DEP-2a), grounded by the geometry Researcher (DEP-1); fixed in `DEFAULT_ISO_GRID_RATIO`. Spec fixes the observable contract: a documented, invertible transform + snap-to-nearest-vertex. | Per owner directive — the ratio is a plan/ADR HOW; acceptance phrased around the transform contract, so the choice does not change acceptance. |
| **CL-3** | Where does the document **PPI** come from for real-size scale? | Real-size scale = `f(document PPI, screen DPI)`; the document carries (or is assigned) a PPI. If Phase-1 `Document` lacks a PPI attribute, AGT-01 adds one at plan time defaulting to `DEFAULT_DOCUMENT_PPI` (BF-3). | ROADMAP "real-size preview"; `f(PPI, DPI)` per the prompt; small data-model addition, not acceptance-changing. |
| **CL-4** | What is "snap" for guides/grids? | A **pure function**: iso → nearest grid vertex; perspective → nearest point on nearest guide within `DEFAULT_SNAP_TOLERANCE_PX`; guides → nearest guide point within tolerance; deterministic tie-break. | ROADMAP "compute snap points from tested geometry logic"; the prompt's testable-contract examples. |
| **CL-5** | What does "mirror edits live" mean? | An edit is **reflected in the preview and all views without a manual refresh**, because all observe the **one shared `Document`** (no per-view pixel copy); realised via HIS-1. | ROADMAP "the real-size preview mirrors edits live"; DOC-1 single-source substrate. |
| **CL-6** | Multi-**view** vs Phase-4 multi-**canvas**? | Multi-**view** = several views of **ONE** document that **stay in sync** (shared `Document`); distinct from Phase-4 multi-**canvas** isolated tabs (different documents). Multi-view *builds on* the Phase-4 viewport system (MC-4), does not respecify it. | ROADMAP "multiple views of one document stay in sync" + "multi-view builds on tabs/artboards"; Phase-4 CL-15 isolation. |
| **CL-7** | What does "views stay in sync" cover? | Document **content** (pixels/layers) syncs across all views + the preview; each view's **local zoom/pan/scroll is independent** (not synced). | Editor norm (detail + overview views); ROADMAP "views of one document stay in sync". |
| **CL-8** | What is a reproducible timelapse? | Replaying the **recorded session** yields the **same frame sequence** for the same session — deterministic, derived from the HIS-1 edit history; capture strategy + encoding deferred to AGT-01. | ROADMAP "timelapse captures a reproducible frame sequence"; P2 determinism. |
| **CL-9** | **Timelapse capture strategy** (per-command vs time-based) + storage/encoding? | **DEFERRED to AGT-01/ADR** (DEP-2b). Spec fixes the observable contract: replay yields the same frame sequence; defensive `eval`-free persistence (IO-3). | Per owner directive — strategy/encoding is a plan/ADR HOW; acceptance around the reproducibility contract. |
| **CL-10** | Is the reference board part of the artwork? | **No** — reference images are a **non-destructive** aid; they never composite into the document, never appear in export, and never push an undo entry. Board layout persists defensively (IO-3). | PureRef norm; ROADMAP "reference board"; REQ-P9-UI-010 non-destructive. |
| **CL-11** | **Reference-board persistence format**? | **DEFERRED to AGT-01/ADR** (DEP-2d). Spec fixes the observable contract: defensive `eval`-free load, malformed → user-facing error, non-destructive. | Per owner directive — format is a plan/ADR HOW. |
| **CL-12** | Are aids/views/recording undoable? | **No** — grids/guides/board/preview/views/timelapse-recording are **view/session state**; only actual drawing edits (existing HIS-1 path) are undoable. Phase 9 adds no `ui/commands.py` logic. | Editor norm; mirrors Phase-4/5/6/8 selection/view state being non-undoable (CL-8 pattern). |
| **CL-13** | Does the 16 ms frame budget apply? | **Yes** — grid/guide overlays + multi-view rendering are on the **per-frame render loop**, so Article VI's 16 ms budget applies (**distinct from Phases 7–8**, where export/automation was batch). Render/perf strategy → AGT-10 (DEP-3). | Article VI (the canvas render loop); overlays render every frame; contrast Phase-7/8 CL-16. |
| **CL-14** | **Perspective grid config** (1-/2-/3-point) + snap tolerance defaults? | **DEFERRED to AGT-01** (DEP-2e/f). Spec fixes the observable contract: deterministic guide-line construction from a config; snap to nearest guide within tolerance; bounded by `MAX_PERSPECTIVE_VANISHING_POINTS`. | Per owner directive — the default set is a plan HOW; acceptance around the construction/snap contract. |
| **CL-15** | Data-layer prefix for timelapse / reference-board persistence? | **No `REQ-P9-DATA-*` was reserved** — persistence folded under REQ-P9-LOGIC-010 / REQ-P9-UI-006 (observable contracts); prefix allocation **flagged to the orchestrator / AGT-01** (PREFIX-NOTE §7, DEP-4). Phase 9's **two** persistence concerns make a DATA prefix more clearly warranted than Phase 8's one. **Not acceptance-changing.** | Per prompt directive — flag rather than invent a prefix; the contract is fixed regardless of placement. |
| **CL-16** | Timelapse video export / hosted reference library scope? | **Deferred**: encoding the timelapse to a shareable video/GIF (Phase-7 export handoff) and a hosted reference library / cloud sync (Phase 10) are out. Phase 9 ships the reproducible *sequence* + a *local* reference board. | Bounds the phase to the ROADMAP Phase-9 bullets + "Done means"; extensible per Art. XI (§6). |
| **CL-17** | Bounds on the aids? | Named constants: `DEFAULT_ISO_GRID_RATIO`, `DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`, `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`; exceeding → domain error. | Art. II single-source; Art. VII defensive (runaway fails safely). |

**SUSPEND / escalate:** *none.* The scope risks — the **isometric default** (2:1 dimetric vs
true-iso), the **timelapse capture strategy** + encoding, the **DPI/real-size scaling specifics**, the
**reference-board persistence format**, and the **perspective config + snap-tolerance defaults** — are
**named HOW decisions** (DEP-1/DEP-2), owned by AGT-01 and grounded by the concurrent
**geometry-focused** Researcher report; the owner directive explicitly reserves them for the plan/ADR.
Crucially, every geometry requirement here is phrased around the **observable geometry + behaviour
contract** — *the isometric transform is a documented, invertible, pure mapping and `snap()` returns
the nearest grid vertex* (REQ-P9-LOGIC-001/-002); *the perspective snap returns the nearest point on
the nearest guide within tolerance* (REQ-P9-LOGIC-004); *`real_size_scale = f(document PPI, screen
DPI)`* (REQ-P9-LOGIC-007); *an edit mirrors live to the preview and all views without manual refresh*
(REQ-P9-UI-002/-008); *a replayed recorded session yields the same frame sequence* (REQ-P9-LOGIC-010)
— so choosing a ratio/strategy/format **does not change any acceptance criterion**. The
**`REQ-P9-DATA-*` prefix** question (CL-15 / PREFIX-NOTE / DEP-4) is a **prefix/placement decision
flagged to the orchestrator**, likewise not acceptance-changing. The **document-PPI source** (CL-3 /
BF-3) is a small data-model default, not acceptance-changing. **No functional or geometry ambiguity
that changes acceptance criteria remains unresolved.**

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic scenarios are for **AGT-04** (pytest + Hypothesis,
headless — the `[GEO]` scenarios are first-class **unit-testable geometry** tests); UI scenarios are
for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`), **each run under BOTH light and dark themes**
(REQ-P9-UI-013, expressed once as a global rule). Scenario ids map to `traceability.md`; tests are
authored later (`pending`).

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the
> scenario is executed and asserted identically under the light theme and the dark theme.*

### Feature: Isometric grid geometry (REQ-P9-LOGIC-001..002)
```gherkin
Scenario: SC-L001-1 the isometric transform is a documented, invertible, pure mapping [GEO]
  Given an isometric grid config (origin, spacing, ratio)
  When a pixel coordinate is mapped to grid coordinates and back
  Then the round-trip returns the original grid coordinate (invertible, per the documented transform)
  And the transform imports no Qt and is a pure deterministic function

Scenario: SC-L002-1 isometric snap returns the nearest grid vertex [GEO]
  Given a cursor position and an isometric grid config
  When snap(cursor, config) is called
  Then it returns the nearest grid vertex per the documented transform, with a deterministic tie-break
  And calling it again with the same inputs returns the identical vertex (pure, unit-testable)
```

### Feature: Perspective grid geometry (REQ-P9-LOGIC-003..004)
```gherkin
Scenario: SC-L003-1 perspective guide-line construction is deterministic from a config [GEO]
  Given a vanishing-point configuration (within MAX_PERSPECTIVE_VANISHING_POINTS)
  When the perspective guide lines are constructed
  Then the set of guide lines is a documented deterministic function of the configuration
  And constructing twice from the same config yields the identical guide-line set

Scenario: SC-L004-1 perspective snap returns the nearest point on the nearest guide within tolerance [GEO]
  Given a cursor position, a perspective config, and a tolerance
  When snap(cursor, config, tolerance) is called
  Then it returns the nearest point on the nearest constructed guide when within tolerance
  And it returns no snap when the nearest guide is beyond tolerance (deterministic tie-break)
```

### Feature: Guides, rulers, real-size scale (REQ-P9-LOGIC-005..007)
```gherkin
Scenario: SC-L005-1 guide snap returns the nearest guide point within tolerance [GEO]
  Given a set of guides (within MAX_GUIDES), a cursor, and a tolerance
  When snap() is called
  Then it returns the nearest guide point or intersection within tolerance, else no snap (pure, deterministic)

Scenario: SC-L006-1 ruler ticks and the coordinate readout are computed from tested geometry [GEO]
  Given document dimensions, a zoom, and a view offset
  When the ruler ticks and cursor coordinate readout are computed
  Then they are a pure deterministic function of the view parameters (unit-testable without Qt)

Scenario: SC-L007-1 real-size scale is a pure function of document PPI and screen DPI [GEO]
  Given a document PPI and a screen DPI
  When real_size_scale = f(document PPI, screen DPI) is computed
  Then it returns the scale rendering the document at physical real size, deterministically for the same inputs
```

### Feature: Timelapse, purity, determinism, single-source, bounds (REQ-P9-LOGIC-008..012)
```gherkin
Scenario: SC-L008-1 the snap/geometry/scale/timelapse engine is Qt-free and unit-testable [GEO]
  Given the logic/ visual-aids geometry modules
  Then they import no Qt (check_layering passes) and every snap/geometry/scale function runs with no GUI or event loop

Scenario: SC-L009-1 all snap/geometry results are deterministic [GEO]
  Given fixed geometry inputs
  When any snap/transform/scale/timelapse function is run twice
  Then both runs produce identical results using no wall-clock time, randomness, or locale-dependent behaviour

Scenario: SC-L010-1 a timelapse replays to the same frame sequence [GEO]
  Given a recorded edit session (within MAX_TIMELAPSE_FRAMES)
  When the recorded session is replayed twice
  Then both replays yield the same frame sequence for the same recorded session
  And a saved-then-reloaded session loads defensively (malformed -> ProjectIOError, no eval/exec) and replays identically

Scenario: SC-L011-1 visual-aid bounds are enforced from constants
  Given a guide set above MAX_GUIDES, a grid spacing outside MIN/MAX_GRID_SPACING, references above MAX_REFERENCE_IMAGES, views above MAX_DOCUMENT_VIEWS, or a timelapse above MAX_TIMELAPSE_FRAMES
  Then a domain error is raised (no silent degradation)
  And DEFAULT_ISO_GRID_RATIO / DEFAULT_SNAP_TOLERANCE_PX / DEFAULT_DOCUMENT_PPI come from constants

Scenario: SC-L012-1 one shared document is the source of truth for all views and the preview
  Given a document observed by multiple views and the real-size preview
  When an edit is applied as a command on that one shared document
  Then no view holds an independent pixel copy and every view/preview derives from the single shared document
```

### Feature: Preview, overlays, reference board, multi-view, timelapse UI (REQ-P9-UI-001..010)
```gherkin
Scenario: SC-UI-001-1 the real-size preview renders the document at physical real size
  Given a document with a known PPI and a screen of known DPI
  When the real-size preview window is shown
  Then it renders the composited document at the logic-computed real-size scale (adding no scaling math of its own)

Scenario: SC-UI-002-1 the real-size preview mirrors edits live
  Given the real-size preview window is open
  When the user draws on the canvas
  Then the preview reflects the edit live without any manual refresh, and viewing the preview never mutates the document

Scenario: SC-UI-003-1 guides & rulers show coordinates and the cursor snaps to guides
  Given the guides & rulers overlay
  When the user creates a guide and moves the cursor near it
  Then the ruler shows the coordinate readout and the cursor snaps to the guide via the logic/ snap (overlay computes no snap itself)

Scenario: SC-UI-004-1 the isometric grid overlay snaps the cursor to the nearest vertex
  Given the isometric grid overlay enabled
  When the user moves the cursor over the grid
  Then the grid renders from the logic/ transform and the cursor snaps to the nearest grid vertex via the logic/ snap

Scenario: SC-UI-005-1 the perspective grid overlay snaps the cursor to the nearest guide
  Given the perspective grid overlay with a configured vanishing-point set
  When the user moves the cursor near a guide line
  Then the guide lines render from the logic/ construction and the cursor snaps to the nearest guide within tolerance (no snap beyond tolerance)

Scenario: SC-UI-006-1 the reference board adds/arranges references non-destructively
  Given the reference board
  When the user adds, moves, resizes, and zooms reference images and saves the board
  Then the references never composite into the document or an export, the board persists defensively, and a malformed board file surfaces a user-facing error (no crash/execution)

Scenario: SC-UI-007-1 the user opens multiple views of one document
  Given a document
  When the user opens a second view (within MAX_DOCUMENT_VIEWS)
  Then both views show the same shared document, each with its own independent zoom/pan

Scenario: SC-UI-008-1 multiple views of one document stay in sync
  Given two open views of one document and the real-size preview
  When the user edits in one view
  Then the edit appears in every view and the preview without a manual refresh, while each view's local zoom/pan stays independent

Scenario: SC-UI-009-1 timelapse recording produces a reproducible frame sequence
  Given the timelapse recording controls
  When the user starts recording, performs edits, and stops
  Then the recorded session replays to the same frame sequence, and recording state pushes no undo entry

Scenario: SC-UI-010-1 visual aids are non-destructive and not undoable
  Given a document with a clean undo stack
  When the user enables a grid, creates a guide, adds a reference, opens a view, and starts recording
  Then none of these mutate the document or push a QUndoCommand (only actual drawing edits are undoable)
```

### Feature: Performance, a11y, theming, i18n (REQ-P9-UI-011..014) — NFR
```gherkin
Scenario: SC-UI-011-1 overlays + multi-view rendering hold the 16 ms frame budget
  Given the isometric/perspective grid + guide overlays and multiple views of an up-to-8K document
  When a frame is rendered
  Then rendering holds the 16 ms FRAME_BUDGET_MS and the preview/timelapse keep the UI responsive
  # Overlays/views are on the per-frame render loop (Article VI applies, unlike Phases 7-8); render/perf strategy is AGT-10 (DEP-3).

Scenario: SC-UI-012-1 visual-aids controls expose accessible names and keyboard focus
  Given the visual-aids controls (grid/guide toggles, perspective config, reference board, view controls, timelapse controls, preview window)
  When each control is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-013-1 the visual-aids UI renders correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the preview, overlays, guides, reference board, views, and timelapse controls render legibly with role-based colours (overlay/guide colours legible over artwork in both themes)

Scenario: SC-UI-014-1 no Phase-9 user-visible string is a bare literal
  Given the Phase-9 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (grid/guide/ruler labels, perspective config, reference-board, view titles, timelapse text/units, errors)
```

---

## 12. Exit / status

- Forward spec authored for Phase 9 — Visual Aids & UX. **26 REQ-IDs**: **12 LOGIC**
  (`REQ-P9-LOGIC-001..012`) + **14 UI** (`REQ-P9-UI-001..014`) + **0 DATA** (no prefix reserved —
  timelapse + reference-board persistence folded under REQ-P9-LOGIC-010 / REQ-P9-UI-006 with the
  prefix flagged to the orchestrator / AGT-01, PREFIX-NOTE §7 / DEP-4), each traced to an S-id /
  F-finding / forward-inherited primitive (DOC-1 `Document` shared subject; PB-1 pixels; HIS-1
  `history` reversible-command path — live-mirror + reproducible-timelapse substrate; CO-4
  `composite_stack`; MC-4 Phase-4 viewport/tab system — multi-view builds on it; IO-3 `project_io.py`
  defensive-load) per Article X.
- **17 clarification defaults** recorded (§10), each grounded in the ROADMAP "Done means", the shipped
  code, the constitution, and Pro Motion NG / PureRef / Aseprite parity; **no open clarification
  blocks planning**.
- **No SUSPEND blocker.** The scope risks — the **isometric default** (2:1 dimetric vs true-iso), the
  **timelapse capture strategy** + encoding, the **DPI/real-size scaling specifics**, the
  **reference-board persistence format**, and the **perspective config + snap-tolerance defaults** —
  are named HOW decisions the owner directive reserves for AGT-01 plan/ADR (DEP-1/DEP-2, grounded by
  the concurrent **geometry-focused** Researcher); every geometry / live-consistency / timelapse REQ
  is phrased around the **observable geometry + behaviour contract** (documented invertible transform;
  nearest-vertex / nearest-guide-within-tolerance snap; `f(PPI, DPI)` scale; live mirror; views in
  sync; reproducible timelapse), so those choices do not change any acceptance criterion.
- **`REQ-P9-DATA-*` prefix question:** **FLAGGED, not blocking.** No DATA prefix was reserved; Phase 9
  has **two** genuine data-layer persistence concerns (the **timelapse frame sequence** and the
  **reference-board layout**), which make a `REQ-P9-DATA-*` prefix **more clearly warranted than
  Phase 8's single serialiser**. Both are phrased around their observable contracts (defensive,
  `eval`-free, round-trip, non-destructive) inside REQ-P9-LOGIC-010 / REQ-P9-UI-006; the prefix
  allocation is proposed to the orchestrator / AGT-01 (PREFIX-NOTE §7 / CL-15 / DEP-4) and is **not
  acceptance-changing**.
- **Document-PPI data-model note (BF-3 / CL-3):** real-size scale needs a document PPI; if the shipped
  `Document` lacks one, AGT-01 adds it (defaulting to `DEFAULT_DOCUMENT_PPI`) at plan time — **not
  acceptance-changing**.
- **NEW vs REUSED (§7):** NEW = `logic/grids.py`, `logic/guides.py`, `logic/preview.py`,
  `logic/timelapse.py`, new constants, all visual-aids UI, and the `data/` timelapse +
  reference-board serialisers. REUSED = the `Document` tree (DOC-1), `PixelBuffer` (PB-1), the
  `history` command path (HIS-1), `blend.composite_stack` (CO-4), the Phase-4 viewport/tab system
  (MC-4), the `project_io.py` defensive-load pattern (IO-3).
- **New constants flagged for `logic/constants.py`** (Article II, BF-1): `DEFAULT_ISO_GRID_RATIO`
  (value = AGT-01/ADR iso-default), `DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`,
  `MAX_GRID_SPACING`, `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`,
  `MAX_TIMELAPSE_FRAMES`, `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI`.
- **Dependencies flagged:** DEP-1 (Researcher `docs/research-phase9-visual-aids.md` — iso math,
  perspective construction, DPI scaling, snap tolerance, timelapse strategy, reference-board
  landscape; geometry-focused, concurrent), DEP-2 (AGT-01 plan/ADR — iso default, timelapse strategy +
  encoding, DPI specifics, reference-board format, perspective config + snap defaults; ADR expected
  for the geometry model), DEP-3 (AGT-01/**AGT-10** — render/perf strategy holding the 16 ms budget
  with overlays + multi-view, and the worker-thread choice for timelapse capture — **Article VI
  applies here, unlike Phases 7-8**), DEP-4 (AGT-01/orchestrator — `REQ-P9-DATA-*` prefix allocation).
- Acceptance scenarios cover every functional and NFR requirement (26 scenarios, incl. 10 first-class
  **[GEO]** tested-geometry scenarios); forward matrix in `traceability.md` (0 uncovered). Tests
  authored later by AGT-04 (logic geometry + Hypothesis) / AGT-06 (UI, both themes), `pending`.
- **STATUS: COMPLETED.**
