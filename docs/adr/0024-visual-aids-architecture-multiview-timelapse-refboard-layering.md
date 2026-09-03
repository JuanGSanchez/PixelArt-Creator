# ADR-0024 — Visual-aids architecture: multi-view over one shared scene, per-committed-command timelapse, PureRef-style reference board, `REQ-P9-DATA-*` prefix allocation, and three-layer placement

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-04 |
| Author | Architecture |
| Feature | `phase-9-visual-aids` |
| Supersedes | — |
| Superseded by | — |

## Context

ADR-0023 fixes the pure geometry/snap/scale model. This ADR rules the remaining HOW-decisions the spec
deferred to architecture so the DATA/UI slices bind to a stable, layered contract:

1. the **multi-view sync model** — how "multiple views of one document stay in sync" is realised
   (REQ-P9-LOGIC-012, REQ-P9-UI-007/-008; DEP the ROADMAP multi-view-vs-multi-canvas disambiguation);
2. the **timelapse capture strategy + storage/encoding** (DEP-2b, CL-9);
3. the **reference-board model** (DEP-2d partial, CL-11 — the runtime model; the *format* is ADR-0025);
4. the **`REQ-P9-DATA-*` prefix** allocation (DEP-4, PREFIX-NOTE, CL-15);
5. the **file placement / three-layer layering** of every new module (Article I / S11, BF-2);
6. the **render-performance routing** for the 16 ms budget (DEP-3, REQ-P9-UI-011).

Two shipped facts constrain placement (re-applying the ADR-0020/0022 lessons):

- `scripts/check_layering.py` enforces forbidden-import rules **only** on top-level `logic/` and `data/`;
  a new top-level sibling (e.g. `views/`) is an **unscanned Qt blind spot**. All new Qt code therefore
  lives under `ui/`; all engine code under `logic/`/`data/`.
- Qt's Graphics View Framework already gives multi-view for free (research §5): N `QGraphicsView`s on
  **one** `QGraphicsScene` share the scene's items; `scene.changed` auto-repaints every attached view.

## Decision

### 1. Multi-view sync — one shared `Document`, one scene, N views (REQ-P9-LOGIC-012, REQ-P9-UI-007/-008)

- **The invariant:** all views of a document **and** the real-size preview observe the **one shared
  `Document`** (DOC-1); **no** view holds an independent pixel/layer copy. An edit is a single reversible
  command on that shared document (HIS-1); every view + the preview *derive* from it. This shared-source
  invariant is the pure substrate (REQ-P9-LOGIC-012) that makes the live mirror + multi-view sync
  observable with **no per-view state and no manual refresh**.
- **Qt realisation (research §5):** one `QGraphicsScene` per document (the shipped Phase-4 document
  scene), **N `QGraphicsView`s** attached via `view.setScene(sameScene)`, each with its **own transform**
  (independent zoom/pan/scroll — view-local state that is *not* synced, CL-7). On an edit, the changed
  sub-rect is rebuilt (numpy→QImage) and `item.update(changed_rect)` schedules a repaint across **all**
  views showing that region — automatic fan-out via `scene.changed`. This **builds on** the Phase-4
  multiple-canvas / artboard viewport system (MC-4) — a Phase-4 tab is an *isolated different* document;
  a Phase-9 view is *another view of the SAME* document. Phase 4 is **not** respecified.
- Simultaneous views are bounded by `MAX_DOCUMENT_VIEWS`.

### 2. Timelapse — per-committed-command, document-render, reproducible (REQ-P9-LOGIC-010)

- **Cadence: per-committed-command** (research §6.1, Recommendation Matrix; the Procreate model). One
  frame is recorded per undoable command that commits, reusing the shipped deterministic history (HIS-1)
  — **not** time-based. This is what makes replay reproducible: the frame set is a deterministic function
  of the recorded command log, independent of wall-clock/zoom/UI.
- **Source: document render, not screen capture** (research §6.2). Each frame is derived by
  **re-compositing the document state** at that command via `blend.composite_stack` (CO-4) → a numpy
  RGBA array — reproducible, resolution-independent, UI-chrome-free. Screen capture is rejected (couples
  to window state, non-deterministic).
- **Model (pure `logic/timelapse.py`):** a `TimelapseSession` is an ordered record of
  `TimelapseFrame(index, command_id)` (a reference to the committed command), **not** inline pixels;
  `replay(session, document, renderer)` reconstructs each state deterministically and composites it. The
  same recorded session replayed twice yields the **same frame sequence** (REQ-P9-LOGIC-010). Frame count
  bounded by `MAX_TIMELAPSE_FRAMES`; rapid strokes coalesce (one frame per committed command). No
  wall-clock, no RNG, no locale (REQ-P9-LOGIC-009).
- **Storage:** the recorded session (the frame/command manifest) is persisted defensively via `data/`
  (REQ-P9-DATA-001; format in ADR-0025); rendered frame *images* are derived on replay/export (not
  stored inline in the model, keeping it small and reproducible). The UI may cache rendered frames in
  memory for scrubbing (a `ui/` concern).
- **Encoding is out of Phase-9 scope** (spec §6, CL-16). Phase 9 produces the **reproducible sequence**;
  encoding it to a shareable GIF **reuses the Phase-7 GIF export** (`encode_gif`, pure-Python Pillow — no
  new dependency) as a later handoff, and **MP4/ffmpeg is deferred** (optional external encoder, explicit
  consent before any bundling — research §6.4). Phase 9 ships neither encoder path as an acceptance;
  the model is encoder-ready.

### 3. Reference board — separate scene of pixmap items, non-destructive (REQ-P9-UI-006)

- **Model (research §7.2):** a **separate `QGraphicsScene`** (distinct from the document scene of §1),
  populated with one `QGraphicsPixmapItem` per reference image, each independently movable / scalable /
  rotatable and croppable (store a crop `QRectF`), on an infinite pan/zoom board (auto-growing
  `sceneRect`); optional always-on-top window. This is **UI + serialisation only** — there is **no**
  snap-geometry, so **nothing new lands in the pure-logic core** for the board.
- **Non-destructive (CL-10):** reference images are **never** part of the document canvas — they never
  composite into the artwork, never appear in an export, and never push an undo entry (REQ-P9-UI-010).
- Bounded by `MAX_REFERENCE_IMAGES`. Persistence (`{image ref, transform, crop, z-order}` + board
  pan/zoom) is a defensive `eval`-free `data/` serialiser (REQ-P9-DATA-002; format in ADR-0025).

### 4. `REQ-P9-DATA-*` prefix (DEP-4 / PREFIX-NOTE / CL-15) — ALLOCATE (diverging from Phase 8)

- **Decision: ALLOCATE a `REQ-P9-DATA-*` prefix — two DATA REQs.** Unlike Phase 8 (one serialiser →
  folded, ADR-0022 §4), Phase 9 has **two genuinely distinct** data-layer persistence concerns with
  **distinct serialisers, formats, and test modules**:
  - **REQ-P9-DATA-001 — Timelapse session persistence.** Defensive, `eval`-free (de)serialise of the
    recorded `TimelapseSession` (IO-3); round-trip so a saved-then-reloaded session **replays
    identically**; malformed/unknown-version → a `ProjectIOError`-family error. Formalises the
    persistence clause fixed in REQ-P9-LOGIC-010. Test: `tests/data/test_timelapse_io.py`.
  - **REQ-P9-DATA-002 — Reference-board persistence.** Defensive, `eval`-free (de)serialise of the board
    layout `{image ref, transform, crop, z-order}` + board view state (IO-3); non-destructive round-trip;
    malformed → user-facing error, never `eval`/`exec`. Formalises the persistence clause fixed in
    REQ-P9-UI-006. Test: `tests/data/test_reference_board_io.py`.
- **Why allocate here but fold in Phase 8:** two separate wire formats with independent lifecycles read
  more clearly as their own layer requirements than as clauses buried in a LOGIC and a UI REQ; the spec
  and traceability both flagged that Phase 9's *two* concerns make a DATA prefix **more clearly warranted
  than Phase 8's single serialiser** (PREFIX-NOTE, DEP-4, CL-15). **Not acceptance-changing:** each DATA
  REQ's contract is *verbatim* the persistence contract already fixed under REQ-P9-LOGIC-010 /
  REQ-P9-UI-006 — this is a placement/formalisation of pre-authorised acceptance, not new acceptance.
  Coverage: **26 base REQ + 2 formalised DATA REQ = 28**, 0 uncovered (analyze-report §4). The Document
  PPI persistence (`.pixproj` v5, BF-3) is a schema extension of the **shipped** `project_io` grounded by
  REQ-P9-LOGIC-007 and is ruled in ADR-0025 — it is **not** a third DATA REQ (it is not a new serialiser).

### 5. Layer placement (Article I / S11 / BF-2) — all Qt-free except the `ui/` panels + `ui/commands.py`

- **`logic/grids.py`** (new, pure): isometric transform + snap; perspective construction + snap;
  `GridError`. Imports `constants` only (leaf-adjacent).
- **`logic/guides.py`** (new, pure): guide snap + tolerance conversion + ruler ticks + coordinate
  readout; `GuideOrientation` (module-local), `GuideError`. Imports `constants`.
- **`logic/preview.py`** (new, pure): `real_size_scale(doc_ppi, screen_dpi)`; `PreviewError`. Imports
  `constants`.
- **`logic/timelapse.py`** (new, pure): the reproducible session model + `replay`; `TimelapseError`.
  Imports `document`, `blend` (CO-4), `history` (HIS-1), `constants`.
- **`logic/constants.py`** (extend): the 10 new bounds/defaults (§ below).
- **`data/timelapse_io.py`** (new, Qt-free): defensive `eval`-free (de)serialise of a `TimelapseSession`
  (IO-3); `TimelapseIOError(ProjectIOError)`. Imports `logic/timelapse`, `constants` (downward).
- **`data/reference_board_io.py`** (new, Qt-free): defensive `eval`-free (de)serialise of the board
  layout (IO-3); `ReferenceBoardIOError(ProjectIOError)`. Imports `constants` (+ a pure board-layout
  dataclass, see ADR-0025).
- **`data/project_io.py`** (extend, Qt-free): `.pixproj` **v5** — persist `Document.ppi` defensively;
  v1–v4 load unchanged (absent PPI → `DEFAULT_DOCUMENT_PPI`) — ADR-0025.
- **`ui/`** (new, Qt only): `real_size_preview_window.py`, `guides_rulers_overlay.py`,
  `iso_grid_overlay.py`, `perspective_grid_overlay.py`, `reference_board.py`, `multi_view.py` (extra
  views on the shared scene), `timelapse_controls.py`, plus the Qt DPI query + manual-calibration in the
  preview window. **Phase 9 adds NO `ui/commands.py` logic** — visual aids are non-destructive
  (REQ-P9-UI-010); the sole Qt file outside `ui/` remains `ui/commands.py`, unchanged by Phase 9.

**Layering (acyclic — verified §Grounding, gate `0`).** New one-way edges: `grids → {constants}`,
`guides → {constants}`, `preview → {constants}`, `timelapse → {document, blend, history, constants}`,
`data/timelapse_io → {logic/timelapse, constants}`, `data/reference_board_io → {constants}`,
`data/project_io → {…existing…}` (+ PPI field, no new edge), and the `ui/` visual-aids modules →
`logic/{grids,guides,preview,timelapse,document,blend}` + `data/{timelapse_io,reference_board_io,
project_io}`. **No `logic → data`**, **no `logic`/`data` → `ui`/Qt**, no cycle: `grids`/`guides`/`preview`
are pure leaves over `constants`; `timelapse` imports downward only. Acyclic by construction.

### New constants (Article II / BF-1 — `logic/constants.py`, names DISTINCT from every shipped constant)

| Constant | Value | Rationale |
| --- | --- | --- |
| `DEFAULT_ISO_GRID_RATIO` | `2.0` | 2:1 dimetric default (ADR-0023 §1; research §1.1); true-iso configurable |
| `DEFAULT_SNAP_TOLERANCE_PX` | `8` | screen-px stickiness (research §3.3 6–8 px); ÷zoom → doc-px |
| `MIN_GRID_SPACING` | `2` | minimum iso tile width, px (avoids sub-pixel grids) |
| `MAX_GRID_SPACING` | `1024` | maximum iso tile width, px (bounded config) |
| `MAX_GUIDES` | `256` | guide-count ceiling; parallels shipped `MAX_BATCH_RECOLOUR_TARGETS=256` |
| `MAX_PERSPECTIVE_VANISHING_POINTS` | `3` | 1-/2-/3-point perspective (ADR-0023 §2) |
| `MAX_REFERENCE_IMAGES` | `256` | reference-board image ceiling |
| `MAX_TIMELAPSE_FRAMES` | `4096` | frame ceiling; parallels `MAX_MACRO_STEPS`/`MAX_FRAMES=4096` |
| `MAX_DOCUMENT_VIEWS` | `8` | simultaneous views of one document (bounded UI resource) |
| `DEFAULT_DOCUMENT_PPI` | `72.0` | default document PPI for real-size (screen/print baseline; BF-3) |

`GuideOrientation` and the timelapse-session `schema_version` string stay **module-local** enumerated
vocabulary / format-intrinsic (ADR-0001 / BF-2). `grids` clamps tile width to
`[MIN_GRID_SPACING, MAX_GRID_SPACING]` before use.

### 6. Render performance — DEP-3 routing to Rendering & Performance/the UI implementation (REQ-P9-UI-011); the 16 ms budget APPLIES

**Unlike Phases 7–8 (batch work), the grid/guide overlays, the multi-view viewports, and the preview
mirror are on the per-frame render loop, so Article VI's 16 ms `FRAME_BUDGET_MS` APPLIES** (spec §5,
CL-13). Architecture commitment (the strategy itself is Rendering & Performance's, DEP-3):

1. **Overlays are static-cacheable.** Grid/guide/perspective overlays are `QGraphicsItem`s with
   `DeviceCoordinateCache` `cacheMode` so pan/zoom does not re-rasterise them (research §5.3); overlay
   colours are role-based (both themes, REQ-P9-UI-013).
2. **Multi-view uses `MinimalViewportUpdate`** (default) for frequent small brush edits; each view
   repaints only its changed sub-rect via `item.update(changed_rect)` (research §5.1/5.3). Tile-culling
   + dirty-rect partial redraw (the Rendering & Performance render-strategy directive, DEP-3) apply per view so N 8K views
   stay within budget.
3. **The real-size preview + timelapse capture keep the UI responsive.** Timelapse frame capture is a
   pure document render (CO-4); whether long-running capture/encoding runs off the GUI thread is an
   Architecture/Rendering & Performance HOW (the Phase-5/6/7/8 worker precedent) — but Phase 9 defers encoding, so capture is
   the per-command composite already needed for the views.
4. **Ownership.** Rendering & Performance owns the render/perf strategy + `perf_profile` measurement for overlays +
   multi-view on the 8K canvas; the UI implementation implements it; architecture fixes the pure-geometry + shared-scene seam.
   **The 16 ms budget is never relaxed** (spec constraint).

## Alternatives Considered

- **Per-view document copies / manual refresh fan-out.** Rejected: violates REQ-P9-LOGIC-012 (one shared
  document) and the ROADMAP "views stay in sync" contract; Qt's shared-scene multi-view is free
  (research §5.1).
- **Time-based timelapse cadence / screen capture.** Rejected: non-deterministic, couples to window
  state; per-committed-command document render is reproducible (research §6.1/6.2).
- **A new top-level `views/` or `board/` package for the Qt surfaces.** Rejected: `check_layering` blind
  spot (the ADR-0020/0022 lesson); all Qt under `ui/`.
- **Folding both persistence concerns under LOGIC/UI (Phase-8 style).** Rejected here: two distinct wire
  formats/serialisers read more clearly as their own DATA REQs, and the spec flagged the two concerns as
  more warranting a prefix than Phase 8's single one (DEP-4). Kept not-acceptance-changing by mapping each
  DATA REQ verbatim to its already-fixed spec contract.
- **Inlining rendered timelapse frames in the persisted model.** Rejected: bloats the file and breaks
  reproducibility-by-replay; the model stores the command manifest and re-renders (research §6.3).
- **Bundling ffmpeg for MP4 in Phase 9.** Rejected/deferred: an optional external dependency needing
  explicit consent; GIF export (Phase-7 reuse) is the encoder-ready handoff (research §6.4; CL-16).

## Consequences

**Positive.** Multi-view + live-mirror are structural (one shared document, one scene, N views) — no
sync code, no per-view state. Timelapse is reproducible by construction (per-command document render over
HIS-1) and encoder-ready without shipping an encoder. The reference board adds **nothing** to the pure
core. Every engine module stays Qt-free under `check_layering`'s guard; Phase 9 touches no
`ui/commands.py` logic (non-destructive aids). Allocating the DATA prefix gives the two serialisers clean,
independently-testable requirements without changing any acceptance.

**Negative / risk.** Allocating `REQ-P9-DATA-001/-002` introduces two REQ-IDs not in the base spec count;
mitigated by mapping each verbatim to its already-fixed spec contract and recording the arithmetic in the
analyze report (pre-authorised by DEP-4/CL-15, not drift). The 16 ms budget applying to overlays +
multi-view on the 8K canvas is a real constraint routed to Rendering & Performance (DEP-3) — the overlays must be
cache-backed and the views dirty-rect-culled or the budget is missed. The real-size DPR risk (ADR-0023
§4) is carried into the preview window.

## Grounding

- Spec `specs/phase-9-visual-aids/spec.md` §2 (layer scope), §4 (REQ-P9-LOGIC-010/-012, REQ-P9-UI-001..010),
  §5 (REQ-P9-UI-011), §7 (NEW vs REUSED; multi-view-vs-multi-canvas; PREFIX-NOTE), §8 (DEP-2b/d, DEP-3,
  DEP-4, BF-1/BF-2/BF-3), §9 Article I/VI/VII, §10 CL-5/CL-6/CL-7/CL-9/CL-10/CL-11/CL-13/CL-15/CL-16, §11
  SC-L010-1/L012-1, SC-UI-006-1/007-1/008-1/009-1/011-1; `traceability.md` DEP-3/DEP-4, MC-4/HIS-1/CO-4/IO-3
  forward traces.
- Research `docs/research-phase-9-visual-aids-20260704.md` §5 (multi-view: one scene, N views,
  `scene.changed` auto-repaint; §5.3 update modes / cacheMode), §6 (timelapse: per-command;
  document-render; §6.3 store manifest re-render; §6.4 GIF reuse / MP4 optional), §7 (reference board:
  separate scene of pixmap items; §7.2 persistence fields), §8 Recommendation Matrix.
- Shipped `logic/document.py` (DOC-1), `logic/history.py` (HIS-1), `logic/blend.py` `composite_stack`
  (CO-4), the Phase-4 viewport/tab system (MC-4), `data/project_io.py` (IO-3), `scripts/check_layering.py`
  (`FORBIDDEN` = `logic`/`data` only). Constitution Article I/II/VI/VII/X/XI. ADR-0023 (geometry model),
  ADR-0025 (`.pixproj` v5 + persistence formats), ADR-0020/0022 (CLI/Qt-blind-spot placement lesson),
  ADR-0001 (intrinsic-local vocabulary), ADR-0007 (dirty-rect precedent).
