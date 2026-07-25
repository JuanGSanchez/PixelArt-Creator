# Specification — Phase 6: Tilemap & Level Design

| Field | Value |
| --- | --- |
| Feature | `phase-6-tilemap` |
| Author | Claude (AGT-02, Requirements) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — no `logic/tileset.py`, `logic/tilemap.py`, tilemap UI, or Tiled-JSON I/O exists yet. The `PixelBuffer` (region/blit) core, `ColorMode`, the `history` command pattern, `blend.composite_stack`, and the defensive `data/project_io.py` load pattern are **already shipped** and are reused, not re-authored. This spec defines the WHAT/WHY Phase 6 realises. |
| REQ-ID range | `REQ-P6-LOGIC-001..014`, `REQ-P6-UI-001..017`, `REQ-P6-DATA-001..004` (from the ROADMAP reserved `REQ-P6-LOGIC-*` / `REQ-P6-UI-*` / `REQ-P6-DATA-*` prefixes) |
| Layer scope | `pixelart_creator/logic/` (new `tileset.py`, `tilemap.py`; new constants; attach a tileset/tilemap collection to `document.py`) + `pixelart_creator/ui/` (tileset editor panel, tilemap canvas, stamping tools, layer/auto-tile controls, import/export actions) + `pixelart_creator/data/` (Tiled-compatible JSON export/import; native `.pixproj` tileset/tilemap persistence — both reuse the `project_io.py` defensive-load pattern). |
| Binds to (upstream, **shipped** — REUSED) | Phase 1 `logic/pixel_buffer.py` (`PixelBuffer.region(x,y,w,h)` returns a sub-rectangle copy; `.blit(src, dx, dy, blend=)`; `.data` NumPy view — the **PB-1** primitive: *tiles are buffer regions of a source image*), `logic/pixel_buffer.ColorMode` (RGBA / INDEXED — the **CM-1** primitive), `logic/history.py` (`Command`, `FunctionCommand`, `History` — the **HIS-1** primitive), Phase 4 `logic/blend.composite_stack` (flattens an ordered layer stack — the **CO-4** primitive reserved for multi-layer tilemap flatten), Phase 1/4 `data/project_io.py` (defensive, type/bounds-checked, no-`eval`, `pathlib` load; `ProjectIOError`; `_SUPPORTED_VERSIONS` — the **IO-3** primitive/pattern), `logic/document.py` (`Document` tree — the **DOC-1** primitive the tileset/tilemap collection attaches to for native persistence) |
| Depends on (external) | The Researcher — `docs/research-phase6-tilemap.md` (grounds the auto-tiling algorithm family (blob-47 vs Wang/terrain) + neighbourhood convention, the Tiled JSON encoding set, and infinite-map chunking conventions). **Concurrent / not-yet-present** — see DEP-1. This spec fixes the WHAT/acceptance and records Tiled-parity defaults; the HOW is AGT-01/AGT-10. |
| SDD phase | `specify` + `clarify` (this document) → consumed by `sdd-plan` (AGT-01) |

---

## 1. Purpose (WHY)

The platform already has the raw substrate a tilemap needs: `PixelBuffer` exposes
`region(x, y, w, h)` (a sub-rectangle) and `blit(source, dx, dy, blend=)`, so a *tile* is
naturally **a buffer region of a source image** (PB-1); `ColorMode` distinguishes RGBA vs indexed
storage (CM-1); the `history` command pattern (HIS-1) makes any state mutation reversible; Phase 4
`blend.composite_stack` (CO-4) flattens an ordered layer stack; and `data/project_io.py` (IO-3)
already demonstrates the defensive, validated, `eval`-free JSON load the platform mandates
(Article VII). What is missing is the **tilemap & level-design system** that turns those primitives
into a game-dev pipeline: a **tileset** that slices a source image into indexed tiles, a **tilemap**
that stamps **linked instances** (a cell references a tile *by id* — not a pixel copy — so a
source-tile edit propagates to every placed instance), **stamping tools**, **auto-tiling rules**
that resolve edges **deterministically and reversibly**, **multi-layer** and **infinite**
(unbounded, sparse) maps, and **Tiled-compatible JSON** export that **re-imports losslessly**.

Phase 6 is the "game-dev pipeline" milestone. Tileset + tilemap + auto-tiling reach **Pro Motion NG
/ Tiled-adjacent** parity — a capability Aseprite covers only partially and Pixelorama minimally —
so the tilemap system is the phase's differentiator. It builds strictly on the shipped substrate:
tiles are `PixelBuffer` regions (PB-1), reversibility reuses the `history` command pattern (HIS-1),
multi-layer map flatten reuses `composite_stack` (CO-4), and the Tiled/native JSON I/O reuses the
`project_io.py` defensive-load pattern (IO-3). No pixel maths or JSON-parsing security posture is
re-invented.

This document specifies WHAT the tilemap system must do and WHY, technology-neutral at the
requirement level. The HOW — the **auto-tiling algorithm family** (blob-47 vs Wang/terrain sets)
and neighbourhood convention, the **Tiled JSON encoding set** (CSV vs base64+zlib layer data,
firstgid mapping), the **infinite-map chunking** scheme, the `.pixproj` schema-version bump, and the
tile-culling / dirty-rect render strategy that keeps an 8K tilemap within budget — are all
downstream (AGT-01 plan/ADR grounded by the Researcher; AGT-10 render-strategy). The auto-tiling
requirement is phrased around the **observable contract** (determinism, reversibility,
edge-neighbour dependence), **not** a specific algorithm. This spec records the clarification
defaults chosen under the owner's autonomous-progress directive (§10).

## 2. Scope

**In scope (WHAT):**

- **`logic/tileset.py` (new, Qt-free).** A **`Tileset`** that references a **source image**
  (`PixelBuffer`) and **slices** it into a grid of fixed-size **indexed tiles** — tile width /
  height plus optional **margin** and **spacing** — assigning each tile a **stable, deterministic
  id/index** (row-major). A tile is defined by its `(tileset, id) → source-region` mapping; reading
  a tile's pixels **derives** them from the *current* source image via `PixelBuffer.region` (PB-1),
  so **editing the source is seen by every reader** (the mechanism behind instance linking). Tiles
  inherit the source image's `ColorMode` (CM-1). A tileset may reference **one or more** source
  images/tilesets under a Tiled-style global tile-id (gid) space (CL-7).
- **`logic/tilemap.py` (new, Qt-free).** A **`Tilemap`** as an ordered stack of **layers**, each an
  **unbounded, sparse grid of cells**; a non-empty cell holds a **linked tile instance** that
  references a tileset tile **by id** (plus an optional orientation — flip H / flip V, CL-3), never
  a pixel copy (REQ-P6-LOGIC-005/-006). **Auto-tiling rules** that, given a placed (logical) tile
  and its **neighbour** configuration, resolve the **display tile deterministically and reversibly**
  (REQ-P6-LOGIC-010/-011). Reversible do/undo ops (stamp / erase / rectangle-fill / add-remove-
  reorder layer) usable by `ui/commands.py` (HIS-1). A **render contract** that resolves each cell's
  instance to its source-tile pixels and composites the layer stack (reusing PB-1 `blit` /
  CO-4 semantics), non-destructively.
- **`logic/constants.py` (extend).** New named bounds/defaults: `DEFAULT_TILE_WIDTH`,
  `DEFAULT_TILE_HEIGHT`, `DEFAULT_TILE_MARGIN`, `DEFAULT_TILE_SPACING`, `MAX_TILE_DIMENSION`,
  `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS` (Article II). **NB:** the shipped `TILE_SIZE` (`64`) and
  `TILE_BUFFER` are the **viewport-culling** tile edge, a *rendering* concept — **distinct** from the
  tileset **tile dimension**; Phase 6 must **not** conflate them (BF-2).
- **`logic/document.py` (extend, Qt-free).** Attach a tileset/tilemap **collection** to the
  `Document` (DOC-1) so tilesets and tilemaps live in the project tree and round-trip natively; the
  attach/detach ops are reversible where they participate in undo.
- **`ui/` tileset editor.** Load/show a source image sliced into tiles; configure slicing (tile
  size, margin, spacing); **select** the active tile; **edit** a source tile's pixels (painting into
  the tileset tile) with placed instances updating live.
- **`ui/` tilemap canvas + stamping tools.** A tilemap canvas on the 8K grid showing the composited
  layer stack; a **stamp** tool (place the selected tile as a linked instance), an **eraser**, and a
  **rectangle/area fill** stamp — each a single `QUndoCommand`; pan/scroll into unbounded map space.
- **`ui/` layer + auto-tile controls.** Tilemap-layer management (add / remove / reorder /
  visibility); an **auto-tiling** toggle/mode so placing tiles resolves edges automatically.
- **`ui/` import/export actions.** Export the tilemap to **Tiled-compatible JSON**; **import** a
  Tiled JSON map (reconstructing an equivalent tilemap).
- **`data/` I/O.** **Tiled-compatible JSON export** and a **lossless re-import** (round-trip
  identity); a **defensive, validated** Tiled-JSON load (reuse the `project_io.py` pattern, IO-3);
  and **native `.pixproj` persistence** of tilesets + tilemaps (round-trip; back-compat read of
  tilemap-less projects).

**Out of scope (this phase):** see §6 Non-goals. Notably: choosing the **auto-tiling algorithm
family** (blob-47 vs Wang/terrain) and neighbourhood convention → AGT-01 plan/ADR (Researcher,
DEP-1/DEP-2); the **Tiled JSON encoding set** (CSV vs base64+zlib layer data, external `.tsx`
tileset vs embedded) → AGT-01 plan (DEP-2); **infinite-map chunking** scheme → AGT-01 plan (DEP-2);
the **tile-culling / dirty-rect render strategy** → AGT-10 (DEP-3); the `.pixproj` **schema-version**
choice → AGT-01 (DEP-2). Also out: **animated tiles** and **object/collision layers** (Tiled's
object groups) → later phase (CL-9); **isometric / hexagonal / staggered** map orientations
(orthogonal only this phase, CL-9); **baking** a tilemap to a flat pixel image → Phase 7 export
path. No plan/tasks/code (AGT-01/03/05); no new technology (S8).

## 3. Story map & user stories

Backbone activities → stories, each tagged with a kebab-case feature label and roadmap phase.
Feature-label taxonomy in §3.2.

### 3.1 User stories

- **US-1 (Level designer / build-tileset).** As a level designer, I want to **slice a source image
  into indexed tiles** (choosing tile size / margin / spacing) so I have a reusable tile palette. →
  REQ-P6-LOGIC-001, -002, -003, REQ-P6-UI-001, -002 · `tileset` · P6
- **US-2 (Level designer / edit-tile-once).** As a level designer, I want **editing a source tile to
  update every placed instance** so I can retheme a whole map from one edit. → REQ-P6-LOGIC-004,
  -006, REQ-P6-UI-003 · `tile-linking` · P6
- **US-3 (Level designer / stamp).** As a level designer, I want to **stamp the selected tile onto
  the map**, erase, and area-fill, each undoable, so I can lay out a level. → REQ-P6-LOGIC-005, -007,
  REQ-P6-UI-004, -005, -006, -007 · `stamping` · P6
- **US-4 (Level designer / auto-tile).** As a level designer, I want **auto-tiling to resolve tile
  edges automatically** from neighbours so borders/paths connect without manual picking, and I want
  it **deterministic and undoable**. → REQ-P6-LOGIC-010, -011, REQ-P6-UI-009 · `auto-tiling` · P6
- **US-5 (Level designer / layers).** As a level designer, I want **multiple map layers** (add /
  remove / reorder / hide) so I can separate ground, decor, and collision-visual layers. →
  REQ-P6-LOGIC-008, REQ-P6-UI-008 · `map-layers` · P6
- **US-6 (Level designer / infinite-map).** As a level designer, I want an **unbounded (infinite)
  map** I can keep extending in any direction so I am not boxed by a fixed size. →
  REQ-P6-LOGIC-009, REQ-P6-UI-010 · `infinite-map` · P6
- **US-7 (Level designer / render).** As a level designer, I want the canvas to show the **composited
  map** — every layer's cells resolved to their source-tile pixels, honouring layer order/visibility
  — reusing the layer compositor. → REQ-P6-LOGIC-013 · `map-render` · P6
- **US-8 (Game dev / Tiled-export).** As a game developer, I want to **export the map to
  Tiled-compatible JSON** so my engine/toolchain can consume it. → REQ-P6-DATA-001,
  REQ-P6-UI-011 · `tiled-export` · P6
- **US-9 (Game dev / lossless-round-trip).** As a game developer, I want **exporting then importing**
  the JSON to yield an **equivalent map** (no data loss) so the format is a safe interchange. →
  REQ-P6-DATA-002, REQ-P6-UI-012 · `round-trip` · P6
- **US-10 (Any user / safe-load).** As a user opening a foreign JSON, I want a **defensive validated
  load** that rejects malformed/out-of-bounds files rather than crashing or executing them. →
  REQ-P6-DATA-003 · `safe-load` · P6
- **US-11 (Any user / native-persistence).** As a user, I want my **tilesets and tilemaps to
  round-trip in `.pixproj`** so my project reopens exactly, and older tilemap-less projects still
  open. → REQ-P6-DATA-004 · `native-persistence` · P6
- **US-12 (Any user / reversibility).** As a user, I want **every tileset/tilemap edit undoable**
  exactly like painting; navigation/selection is not undoable. → REQ-P6-LOGIC-007, -012,
  REQ-P6-UI-013 · `reversibility` · P6
- **US-13 (Any user / responsive-canvas).** As a user on a large map, I want the **8K tilemap canvas
  to stay at 60 fps** while stamping and panning. → REQ-P6-UI-014 · `tilemap-perf` · P6
- **US-14 (Any user / a11y-theme-i18n).** As a keyboard user / dark-mode user / non-English user, I
  want the tileset editor, tilemap tools and dialogs **keyboard-reachable, correct in both themes,
  fully translatable**. → REQ-P6-UI-015, -016, -017 · `a11y`, `theming`, `i18n` · P6

### 3.2 Feature-label taxonomy (canonical, kebab-case)

| Label | Definition | Phase |
| --- | --- | --- |
| `tileset` | `Tileset` model: slicing a source image into stable indexed tiles (size/margin/spacing). | 6 |
| `tile-linking` | Linked instances reference a tile by id; a source-tile edit propagates to all instances. | 6 |
| `stamping` | Reversible stamp / erase / rectangle-fill placement of linked instances. | 6 |
| `auto-tiling` | Deterministic, reversible, neighbour-dependent resolution of a cell's display tile. | 6 |
| `map-layers` | Ordered tilemap layers (add / remove / reorder / visibility). | 6 |
| `infinite-map` | Unbounded, sparse cell addressing over arbitrary integer coordinates. | 6 |
| `map-render` | Resolve each cell's instance to source-tile pixels + composite the layer stack (CO-4). | 6 |
| `tiled-export` | Export the tilemap to Tiled-compatible JSON. | 6 |
| `round-trip` | Export→import yields an equivalent tilemap (lossless identity). | 6 |
| `safe-load` | Defensive, validated, `eval`-free load of Tiled/native JSON (IO-3 pattern). | 6 |
| `native-persistence` | Tilesets + tilemaps round-trip in `.pixproj`; back-compat with older projects. | 6 |
| `reversibility` | Every tileset/tilemap edit wrapped as a single reversible command. | 6 |
| `tilemap-perf` | 8K tilemap canvas render/stamp/pan within the frame budget. | 6 |
| `theming` / `a11y` / `i18n` | Both themes, keyboard/focus, translatable strings. | 6 |

---

## 4. Functional requirements

Each REQ carries `traces:` to a dossier `S-id`, a research `F`-finding, or a Phase-6 capability +
forward-inherited primitive (Article X). Requirements are technology-neutral WHAT statements; a
binding to a fixed shipped callable is named as a **constraint**, not a HOW decision.

### `logic/tileset.py` — slicing, indexing, tile-edit source of truth (new)

#### REQ-P6-LOGIC-001 — Tileset slices a source image into indexed tiles (deterministic grid)
`traces:` S6 (unified platform / game-dev pipeline), Phase-6 capability
A `Tileset` references a **source image** (`PixelBuffer`) and slices it into a grid of fixed-size
tiles given a **tile width**, **tile height**, optional **margin** (border offset before the first
tile) and **spacing** (gap between tiles). The number of tiles and each tile's grid position are a
**deterministic function** of `(source dimensions, tile size, margin, spacing)`. Slicing is pure
and repeatable: identical inputs always yield the identical tile grid (P2). Tile dimensions are
bounded by `MAX_TILE_DIMENSION` and the count by `MAX_TILESET_TILES` (REQ-P6-LOGIC-014); invalid
slicing parameters raise a domain error rather than degrading silently (Article VII).

#### REQ-P6-LOGIC-002 — Tiles are source-image buffer regions (PB-1 reuse, not pixel copies)
`traces:` **PB-1** (`PixelBuffer.region`/`.blit`, forward-inherited), Phase-6 capability
A tile is defined by its `(tileset, id) → source-region` mapping. Reading a tile's pixels **derives**
the region from the *current* source image via `PixelBuffer.region` (PB-1); the tileset does **not**
store a detached pixel copy per tile as its source of truth. Tiles inherit the source image's
`ColorMode` (CM-1: RGBA or indexed). The tileset does not re-implement pixel storage or region
extraction (Article I) — it composes the shipped `PixelBuffer` primitive.

#### REQ-P6-LOGIC-003 — Stable, deterministic tile id ↔ region mapping
`traces:` Phase-6 capability, S6, P2 (determinism)
Each tile has a **stable id/index** assigned **row-major** (left-to-right, top-to-bottom) from the
sliced grid. The mapping `id → source region` is a **pure, total function** over the valid id range;
the same id always addresses the same region for a given slicing configuration. When multiple
source images/tilesets are referenced (CL-7), ids compose into a **global tile-id (gid) space** with
a Tiled-style per-tileset first-gid offset so a `Tilemap` cell can name any tile unambiguously.

#### REQ-P6-LOGIC-004 — Source-tile edit is the single source of truth for that tile
`traces:` **PB-1**, Phase-6 capability, S7 (reversible edit)
Editing a source tile means writing the **sub-rectangle of the source image** for that tile id
(reusing the shipped reversible pixel-edit pattern, HIS-1). Because every reader derives a tile's
pixels from the current source region (REQ-P6-LOGIC-002), **one edit is seen by every consumer of
that tile id** — this is the mechanism that makes instance linking (REQ-P6-LOGIC-006) propagate.
The edit is reversible (undo restores the prior source pixels exactly).

### `logic/tilemap.py` — instances, layers, infinite, auto-tiling, render (new)

#### REQ-P6-LOGIC-005 — Tilemap model: layered, sparse grid of linked tile instances
`traces:` S6, Phase-6 capability
A `Tilemap` is an **ordered stack of layers**; each layer is a grid of **cells**; a non-empty cell
holds a **tile instance**. An instance **references a tileset tile by its (global) id** and an
optional **orientation** (flip horizontal / flip vertical, CL-3) — it is **not** a pixel copy. An
empty cell = no instance (Tiled gid 0 semantics, CL-4). The instance model reserves exactly the
data a Tiled cell needs (gid + flip flags) so it round-trips (REQ-P6-DATA-002).

#### REQ-P6-LOGIC-006 — Linked-instance propagation on source-tile edit
`traces:` **PB-1**, Phase-6 capability (tile-instance linking), S6
Because a cell stores a **tile id** (not pixels, REQ-P6-LOGIC-005) and the map render resolves that
id against the tileset's current source (REQ-P6-LOGIC-002/-013), **editing a source tile propagates
to every placed instance of that tile id, everywhere on every layer**, without touching the cells.
No per-instance pixel duplication exists to fall out of sync. This holds for arbitrarily many
instances of the same tile.

#### REQ-P6-LOGIC-007 — Reversible stamp / erase / rectangle-fill ops
`traces:` **HIS-1** (`history` command pattern, forward-inherited), S7
Placing an instance (**stamp**), clearing a cell (**erase**), and filling a rectangular region with
a tile (**rectangle-fill**) are each **reversible** operations exposing a do/undo pair (capturing the
minimal prior cell state) that `ui/commands.py` wraps in one `QUndoCommand` via `logic/history.py`.
Undo restores the exact prior cell contents (id + orientation, or emptiness). A stamp naming an
invalid/unknown tile id raises a domain error.

#### REQ-P6-LOGIC-008 — Multi-layer maps (ordered, reversible layer ops)
`traces:` S6, Phase-6 capability, S7
A `Tilemap` supports **multiple ordered layers**; **add / remove / reorder** a layer and toggle a
layer's **visibility** are reversible single operations (undo restores the exact prior layer order /
contents / visibility). Layer count is bounded by `MAX_TILEMAP_LAYERS` (REQ-P6-LOGIC-014). Cells on
different layers at the same coordinate are independent.

#### REQ-P6-LOGIC-009 — Infinite (unbounded, sparse) map addressing
`traces:` S6, Phase-6 capability, Article VII (defensive)
A tilemap layer addresses cells at **arbitrary integer coordinates**, including **negative** ones —
there is **no fixed width/height wall**; the map can be extended in any direction. Storage is
**sparse** (only non-empty cells are held), so an empty region costs nothing. Reading an unset cell
yields *empty* (not an error). The concrete **chunking / sparse-storage scheme** is an AGT-01 plan
decision (DEP-2); this spec fixes only the *observable* unbounded-sparse contract. Coordinate
magnitudes are guarded against pathological values (defensive bound, Article VII).

#### REQ-P6-LOGIC-010 — Auto-tiling resolves edges deterministically from neighbours *(contract, not algorithm)*
`traces:` Phase-6 capability (auto-tiling), **F-tilemap (DEP-1)**, P2 (determinism)
When auto-tiling is enabled, the **display tile** shown in a cell is a **deterministic function of
that cell's placed (logical) tile and its neighbouring cells' occupancy/configuration**: given the
same cell and the same neighbourhood, the resolved display tile is **always identical** (P2). At
minimum the contract depends on the **4 edge-adjacent neighbours** (up/down/left/right); an
8-neighbour (corner-aware) neighbourhood is permitted by the plan (CL-5). The requirement fixes the
**observable contract** — *determinism* + *edge-neighbour dependence* — and does **not** choose the
algorithm family (blob-47 vs Wang/terrain) or the tile-set layout; those are AGT-01 plan/ADR
decisions grounded by the Researcher (DEP-1/DEP-2).

#### REQ-P6-LOGIC-011 — Auto-tiling is reversible / round-trips to the logical placement
`traces:` Phase-6 capability (auto-tiling), S7, P2
Auto-tiling is **reversible**: the map stores the **logical** placement (which terrain/tile the user
stamped); the **display tile is derived** and can be recomputed at any time from the logical
placement + neighbourhood. Given a placed tile and its neighbours, resolving the display tile and
then reverting (recomputing from the logical layer, or undoing the placement) yields the **original
placement exactly** — no information is lost by auto-tiling. Auto-tile resolution triggered by a
stamp/erase participates in that operation's single reversible command (REQ-P6-LOGIC-007), so undo
restores both the edited cell and any neighbour cells whose display tile the edit re-resolved.

#### REQ-P6-LOGIC-012 — Every tilemap-model mutation is a reversible do/undo op
`traces:` **HIS-1**, S7, C1
All tilemap/tileset **state mutations** that participate in undo — stamp, erase, rectangle-fill,
layer add/remove/reorder/visibility, source-tile pixel edit, tileset attach/detach, auto-tile
re-resolution — are expressed as **pure do/undo pairs** in the Qt-free `logic/` layer, so
`ui/commands.py` can wrap each in exactly one `QUndoCommand` (Article I: `ui/commands.py` is the only
Qt file outside `ui/`). Undo restores the exact prior state. View state (pan, zoom, active-tile
selection, active-layer selection) is **not** a model mutation and is **not** reversible (CL-13).

#### REQ-P6-LOGIC-013 — Map render resolves instances and composites layers (PB-1 / CO-4 reuse)
`traces:` **PB-1**, **CO-4** (`blend.composite_stack`, forward-inherited), S7
Rendering a tilemap region for display/export **resolves each non-empty cell's instance** to its
source-tile pixels (via the tileset, REQ-P6-LOGIC-002, applying the instance's flip orientation) and
**composites the visible layer stack** top-to-bottom, honouring per-layer visibility/order — reusing
`PixelBuffer.blit` (PB-1) for tile placement and delegating multi-layer flatten to
`blend.composite_stack` (CO-4) where a layer stack must be flattened. The renderer does **not**
re-implement compositing maths (Article I) and **never mutates** the tileset source buffers or the
cell data (non-destructive).

#### REQ-P6-LOGIC-014 — Bounded numerics & defaults (single source)
`traces:` Article II, Article VII, S12
The tileset/tilemap model enforces named bounds/defaults defined once in `logic/constants.py`:
`DEFAULT_TILE_WIDTH` / `DEFAULT_TILE_HEIGHT` (default tile size, CL-1), `DEFAULT_TILE_MARGIN` /
`DEFAULT_TILE_SPACING` (default `0` / `0`, CL-2), `MAX_TILE_DIMENSION` (max tile edge),
`MAX_TILESET_TILES` (max tiles per tileset), `MAX_TILEMAP_LAYERS` (max map layers). Exceeding a
bound raises a domain error rather than degrading silently. **NB (BF-2):** the shipped `TILE_SIZE`
(`64`) / `TILE_BUFFER` constants are the **viewport-culling** tile edge (a *rendering* concept) and
are **distinct** from the tileset **tile dimension** — Phase 6 introduces separate constants and
must not reuse `TILE_SIZE` as the tile-slicing size.

### `ui/` — tileset editor, tilemap canvas, stamping, layers, auto-tile, import/export

#### REQ-P6-UI-001 — Tileset editor shows a sliced source image and selects a tile
`traces:` REQ-P6-LOGIC-001, -003
A tileset editor panel shows the source image sliced into its tile grid; the user **selects** the
active tile (highlighted). The panel reflects the deterministic id layout (REQ-P6-LOGIC-003).
Selection is view state (no undo entry, CL-13).

#### REQ-P6-UI-002 — Slicing configuration (tile size / margin / spacing)
`traces:` REQ-P6-LOGIC-001, -014
The user sets **tile width / height**, **margin**, and **spacing**; the tileset re-slices and the
grid updates. Defaults come from `DEFAULT_TILE_*` constants; out-of-range values are rejected
(REQ-P6-LOGIC-014). Reconfiguring the slice is a document mutation (its undo behaviour follows
REQ-P6-UI-013).

#### REQ-P6-UI-003 — Edit a source tile; placed instances update live
`traces:` REQ-P6-LOGIC-004, -006
The user can **paint into a source tile** in the tileset editor; because instances are linked
(REQ-P6-LOGIC-006), **every placed instance of that tile on the tilemap updates** without re-stamping.
The pixel edit is one `QUndoCommand` (REQ-P6-LOGIC-004).

#### REQ-P6-UI-004 — Tilemap canvas shows the composited map
`traces:` REQ-P6-LOGIC-013, S1
A tilemap canvas renders the **composited** layer stack (each cell resolved to its source-tile
pixels, layer order/visibility honoured, REQ-P6-LOGIC-013) on the 8K grid, with pan/zoom.

#### REQ-P6-UI-005 — Stamp tool places a linked instance
`traces:` REQ-P6-LOGIC-005, -007
A **stamp** tool places the selected tile as a **linked instance** at the target cell; each stamp
pushes exactly one `QUndoCommand`. Stamping resolves any auto-tiling if enabled (REQ-P6-UI-009).

#### REQ-P6-UI-006 — Eraser tool clears a cell
`traces:` REQ-P6-LOGIC-007
An **eraser** tool clears the target cell (sets it empty); each erase pushes exactly one
`QUndoCommand`; undo restores the prior instance.

#### REQ-P6-UI-007 — Rectangle / area-fill stamp
`traces:` REQ-P6-LOGIC-007
A **rectangle-fill** stamp fills a dragged rectangular region with the selected tile as one
`QUndoCommand`. (A same-tile flood **bucket** is optional / plan-level, CL-12.)

#### REQ-P6-UI-008 — Tilemap layer management
`traces:` REQ-P6-LOGIC-008
The UI lets the user **add / remove / reorder** tilemap layers and toggle a layer's **visibility**;
each structural change pushes exactly one `QUndoCommand`. The active layer receives stamps/erases.

#### REQ-P6-UI-009 — Auto-tiling toggle / mode
`traces:` REQ-P6-LOGIC-010, -011
The user can **enable auto-tiling** (per layer / per brush); when enabled, stamping/erasing resolves
each affected cell's **display tile** from its neighbours (REQ-P6-LOGIC-010) deterministically, and
the operation remains a single undoable command that restores neighbour re-resolution on undo
(REQ-P6-LOGIC-011). When disabled, the placed tile is shown as-is.

#### REQ-P6-UI-010 — Infinite-map navigation
`traces:` REQ-P6-LOGIC-009
The user can **pan/scroll beyond the current populated bounds** in any direction and stamp into
previously empty space; the map extends without a fixed-size wall (REQ-P6-LOGIC-009). Navigation is
view state (no undo entry, CL-13).

#### REQ-P6-UI-011 — Export to Tiled-compatible JSON
`traces:` REQ-P6-DATA-001
An **export** action writes the active tilemap to **Tiled-compatible JSON** (REQ-P6-DATA-001) at a
user-chosen path (portable path handling, Article VII).

#### REQ-P6-UI-012 — Import Tiled JSON
`traces:` REQ-P6-DATA-002, -003
An **import** action loads a Tiled JSON map, reconstructing an equivalent tilemap
(REQ-P6-DATA-002) via the defensive load (REQ-P6-DATA-003); a malformed file surfaces a user-facing
error, not a crash.

#### REQ-P6-UI-013 — Every tileset/tilemap edit is exactly one undoable command; view ops are not
`traces:` S7, C1, F1, REQ-P6-LOGIC-007, -008, -012
Every tileset/tilemap **edit** surfaced by the UI — stamp / erase / rectangle-fill, layer
add/remove/reorder/visibility, source-tile pixel edit, slicing reconfigure, tileset attach — is
pushed as **exactly one `QUndoCommand`** onto the active document's `QUndoStack`, delegating to the
Qt-free reversible op in `logic/` (Article I). Undo restores the exact prior state. **Navigation,
zoom, active-tile selection, and active-layer selection are not undoable** (view state, CL-13).

## 5. Non-functional requirements (constitution-tied acceptance)

#### REQ-P6-UI-014 — Performance: 8K tilemap canvas render/stamp/pan within the frame budget *(NFR, Article VI)*
`traces:` S1, S12, F2, F7, Article VI, DEP-3
Rendering, stamping into, and panning an **8K (7680 × 4320)** tilemap holds `FPS_TARGET = 60`, i.e.
per-frame render/update time ≤ `FRAME_BUDGET_MS = 16`. Advancing/updating must render only the
**visible viewport** and recomposite only **what changed** (tile-culling + dirty-rect) rather than
resolving every cell over the whole map each frame. **Verified headless by AGT-10**
(`perf_profile` / `frame-profile`); an over-budget measurement yields an AGT-10 optimisation
directive (viewport tile-culling, dirty-rect recomposite, scene-rect / BSP tuning), **never** a
relaxation of the budget. The resident pixel/tile data is never culled — only Qt rendering is
(Article VI §3). The concrete render strategy is AGT-10 plan-level (DEP-3).

#### REQ-P6-UI-015 — Accessibility *(NFR, Article V)*
`traces:` Article V §1
Every interactive tileset/tilemap control (tile grid cells, slicing spin-boxes, tool buttons
[stamp / erase / fill], layer list + add/remove/reorder/visibility, auto-tile toggle, import/export
actions) exposes an accessible name and, where non-obvious, an accessible description; is reachable
and operable by keyboard (logical tab order + shortcuts); and shows a visible focus indicator.
Verified by AGT-06 (`a11y-audit`).

#### REQ-P6-UI-016 — Both themes correct *(NFR, Article V)*
`traces:` Article V §3
The tileset editor, tilemap canvas chrome, tool bar, layer panel, and dialogs render correctly in
both light and dark themes; colours (grid lines, selection highlight, layer-row states) are defined
once by role, never hard-coded per widget. Both themes are test-verified (AGT-06 pytest-qt).

#### REQ-P6-UI-017 — All user-visible strings translatable *(NFR, Article V)*
`traces:` Article V §2, F6
Every user-visible string added by Phase 6 (tool names/tooltips, slicing labels + units, layer
actions, auto-tile labels, import/export dialog text, error messages) is wrapped in `tr()` /
`translate()`; none is a bare literal. Hand-built widgets re-set text on `QEvent.LanguageChange`.
Verified by `string_audit_check` (AGT-07); an unwrapped string is a blocking finding.

### `data/` — Tiled JSON I/O + native persistence

#### REQ-P6-DATA-001 — Export tilemap to Tiled-compatible JSON
`traces:` **IO-3** (`project_io.py` pattern, forward-inherited), S6, S7, Phase-6 capability
The tilemap serialises to **Tiled-compatible JSON** — map dimensions/infinite flag, tile size,
layer stack (per layer: name, visibility, cell data), and tileset reference(s) with the Tiled
first-gid mapping, and per-cell gid including flip flags. Paths are built portably (`pathlib`,
Article VII §2). The **exact encoding set** (CSV vs base64+zlib layer data; embedded vs external
tileset) is an AGT-01 plan decision (DEP-2); this spec fixes only that the output is a **valid Tiled
map** consumable by Tiled/Tiled-adjacent tooling.

#### REQ-P6-DATA-002 — Tiled JSON re-imports losslessly (round-trip identity)
`traces:` **IO-3**, S7, Phase-6 capability, P2
Importing a Tiled JSON map produced by REQ-P6-DATA-001 reconstructs an **equivalent tilemap**:
export→import yields a tilemap whose layer stack, per-cell tile ids + flip orientation, layer
visibility/order, map/tile geometry, and tileset gid mapping are **identical** to the original
(round-trip identity). No cell, layer, orientation flag, or tileset link is lost or altered. Where
Tiled expresses a concept the platform also models, the round-trip preserves it exactly; concepts
the platform does not model (§6 non-goals) are out of scope, not silently corrupted.

#### REQ-P6-DATA-003 — Defensive, validated Tiled/JSON load (IO-3 pattern)
`traces:` Article VII, **IO-3**
Loading Tiled/native JSON **validates** every field before use — map/tile dimensions and layer
sizes are type- and bounds-checked (against the S12 canvas/tile bounds), gids are checked against
the declared tileset ranges, layer-data payloads are size-validated against the declared geometry —
and a malformed / out-of-bounds / oversized / unknown-orientation document raises `ProjectIOError`
(never silent acceptance, **never `eval`/`exec`**), reusing the shipped `project_io.py` defensive
posture (IO-3). Paths are portable (`path_portability_check`).

#### REQ-P6-DATA-004 — Native `.pixproj` persistence of tilesets + tilemaps (round-trip; back-compat)
`traces:` **IO-3**, **DOC-1**, S7, Phase-6 capability
`.pixproj` serialises the document's **tilesets** (source-image reference + slicing config) and
**tilemaps** (layer stack + linked instances + auto-tile logical placement), and a saved-then-loaded
project restores them **identically**. A project **without** tileset/tilemap data (older) loads
successfully with an empty tilemap collection (**back-compat**). Whether this is a **schema-version
bump** or an **additive field** on the current version is an AGT-01 plan decision (DEP-2); back-compat
read is required either way, reusing the defensive-load pattern (IO-3).

## 6. Non-goals (explicit; deferred)

- **Auto-tiling algorithm family & neighbourhood convention** (blob-47 vs Wang/terrain sets;
  4- vs 8-neighbour) — **AGT-01 plan/ADR**, grounded by the Researcher (DEP-1/DEP-2). This spec fixes
  only the observable contract (determinism, reversibility, edge-neighbour dependence,
  REQ-P6-LOGIC-010/-011).
- **Tiled JSON encoding set** (CSV vs base64+zlib layer data; embedded vs external `.tsx` tilesets)
  and **infinite-map chunking scheme** — AGT-01 plan (DEP-2). The WHAT (valid Tiled map, lossless
  round-trip, unbounded-sparse contract) is fixed here.
- **`.pixproj` schema-version choice** (bump vs additive field) for tilemap persistence — AGT-01
  plan (DEP-2, CL-9); back-compat is required regardless (REQ-P6-DATA-004).
- **Tile-culling / dirty-rect render strategy** for the 8K tilemap — AGT-10 plan-level (DEP-3); this
  spec states only the 16 ms budget (REQ-P6-UI-014).
- **Animated tiles** (per-tile frame sequences) and **object/collision layers** (Tiled object
  groups) → later phase (CL-9). Phase 6 ships tile + tilemap + auto-tiling over orthogonal maps.
- **Non-orthogonal map orientations** (isometric / hexagonal / staggered) → later phase (CL-9);
  orthogonal only this phase.
- **Baking** a tilemap down to a flat pixel image / sprite sheet → **Phase 7** export path (the map
  render REQ-P6-LOGIC-013 is the input, but no bake/flatten-export UI here).
- No plan/tasks (AGT-01), no logic/UI/data/test code (AGT-03/05/04/06), no new technology (S8).

## 7. Dependencies & assumptions

- **Upstream substrate is shipped and REUSED** (`specs/phase-1-core-engine/`,
  `specs/phase-4-layer-canvas/`): `PixelBuffer.region`/`.blit`/`.data` (PB-1 — *tiles are buffer
  regions*), `ColorMode` (CM-1), `history` (`Command`, `FunctionCommand`, `History` — HIS-1),
  `blend.composite_stack` (CO-4 — multi-layer flatten), `data/project_io.py` defensive-load pattern
  (`ProjectIOError`, `_SUPPORTED_VERSIONS`, type/bounds checks, no `eval`, `pathlib` — IO-3), the
  `Document` tree (DOC-1). Phase 6 **composes** these; it must not re-implement pixel storage,
  compositing, the command pattern, or the JSON security posture (Article I / VII).
- **NEW vs REUSED (explicit):**
  - **NEW:** `logic/tileset.py` (`Tileset` — slicing, id↔region mapping, source-tile edit),
    `logic/tilemap.py` (`Tilemap` — layers, linked instances, infinite/sparse addressing, auto-tile
    resolution, render contract), the reversible stamp/erase/fill/layer/auto-tile commands, the
    tileset/tilemap collection on `Document`, new constants (`DEFAULT_TILE_*`, `MAX_TILE_DIMENSION`,
    `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`), all tileset/tilemap UI, and the Tiled-JSON
    export/import + native `.pixproj` tilemap persistence.
  - **REUSED (not re-authored):** `PixelBuffer` region/blit (PB-1), `ColorMode` (CM-1), the `history`
    command pattern (HIS-1), `blend.composite_stack` (CO-4), the `project_io.py` defensive-load
    pattern (IO-3), and the `Document` tree (DOC-1).
- Tilemap ops reuse the shipped `history.FunctionCommand` do/undo pattern so `ui/commands.py` stays a
  thin Qt wrapper (REQ-P6-UI-013, Article I §2), mirroring the Phase-4/5 command precedent.
- The active tileset / active tile / active layer / viewport are held by the window (view state); the
  canvas renders the composited map via the logic-layer render contract (REQ-P6-LOGIC-013).

## 8. Behaviours flagged for AGT-01 / AGT-10 / Researcher (not blockers)

- **DEP-1 (Researcher, grounding).** `docs/research-phase6-tilemap.md` grounds the auto-tiling
  algorithm family (blob-47 vs Wang/terrain) + neighbourhood convention, the Tiled JSON encoding set,
  and infinite-map chunking conventions. **Concurrent / not-yet-present.** AGT-01's `sdd-plan` must
  not invent these — it consumes the Researcher's findings. The *observable contract* and
  Tiled-parity defaults are fixed here regardless (§10).
- **DEP-2 (AGT-01, plan/ADR).** (a) **Auto-tiling algorithm family** + neighbourhood (blob-47 vs
  Wang; 4- vs 8-neighbour); (b) **Tiled JSON encoding set** (CSV vs base64+zlib layer data; embedded
  vs external tileset); (c) **infinite-map chunking** scheme; (d) **`.pixproj` schema-version** for
  tilemap persistence. Each is a HOW decision; back-compat read of tilemap-less projects is required
  either way (REQ-P6-DATA-004). Final `REQ-P6-DATA-*` count may be refined at plan time; this spec
  allocates `-001..-004`.
- **DEP-3 (AGT-10, plan).** The render strategy that makes REQ-P6-UI-014 pass — **viewport
  tile-culling** of the visible cells + **dirty-rect recomposite** on stamp/pan, resolving only the
  visible viewport rather than the whole (possibly infinite) map — is AGT-10's render-strategy
  output. Resolving every cell every frame at 8K will blow `FRAME_BUDGET_MS`; a culled + dirty-rect
  approach is expected (flagged for the plan). This spec fixes only the budget.
- **BF-1 (AGT-01, plan).** Whether tile instances are drawn as individual `QGraphicsPixmapItem`s vs.
  a single pre-composited layer pixmap redrawn by dirty region is a HOW decision; the spec requires
  only the composited-map behaviour (REQ-P6-LOGIC-013).
- **BF-2 (AGT-01, Article II).** New tuning values (`DEFAULT_TILE_WIDTH/HEIGHT`,
  `DEFAULT_TILE_MARGIN/SPACING`, `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`) must
  resolve to named constants in `logic/constants.py`. The shipped `TILE_SIZE` (`64`) / `TILE_BUFFER`
  are the **viewport-culling** edge (a rendering concept) and must **not** be reused as the tileset
  tile dimension (REQ-P6-LOGIC-014). No enumerated auto-tile *rule ids* are pinned here (algorithm
  family is DEP-2).

## 9. Constitution-compliance notes

- **Article I (three-layer purity):** `logic/tileset.py`, `logic/tilemap.py`, and the `document.py`
  extension are pure Python, zero Qt; the tileset editor / tilemap canvas / tools live in `ui/`; the
  Tiled-JSON + `.pixproj` I/O lives in `data/` (zero Qt); the only Qt file outside `ui/` remains
  `ui/commands.py` (stamp/erase/layer/tile-edit command wrappers, REQ-P6-UI-013). Enforced by
  `check_layering` / `check_cycles`.
- **Article II (numerics):** new tuning values go in `logic/constants.py` (BF-2); no literals in
  `ui/`/`logic/`/`data/`. `TILE_SIZE` (viewport-culling) is **not** the tile dimension.
- **Article IV (testing):** deterministic slicing, id↔region mapping, instance linking/propagation,
  reversible stamp/erase/fill/layer ops, infinite-sparse addressing, deterministic + reversible
  auto-tile resolution, per-map render reuse (CO-4), and the Tiled round-trip + defensive load each
  get a scenario → one pytest / Hypothesis test (logic/data) or pytest-qt test (UI), both themes for
  UI.
- **Article V (UX):** REQ-P6-UI-015/-016/-017 make a11y + both themes + full translatability
  blocking gates for the tileset editor and tilemap UI.
- **Article VI (performance):** REQ-P6-UI-014 binds the 16 ms budget for the 8K tilemap canvas; the
  resident pixel/tile data is never culled.
- **Article VII (security):** tile/layer/coordinate bounds, invalid-slice guards, and the
  **defensive validated Tiled/native JSON load** (REQ-P6-DATA-003, REQ-P6-LOGIC-014) are defensive;
  no `eval`/`exec`; portable paths.
- **Article X (traceability):** every REQ traces to an S-id / F-finding / forward-inherited
  primitive (PB-1, CM-1, HIS-1, CO-4, IO-3, DOC-1); forward matrix in `traceability.md`.
- **Article XI (extensibility):** deferring animated tiles, object/collision layers, and
  non-orthogonal orientations (CL-9) adds capability later without weakening any article.

---

## 10. Clarifications (resolved via `sdd-clarify`)

Per the owner's autonomous-progress directive, ordinary ambiguities are resolved with sensible
defaults grounded in the ROADMAP "Done means", the shipped code, and mainstream tilemap norms
(**Tiled** parity, Pro Motion NG). Each is a **category-1 decision** (A2-D2 Branch B). **No open
clarification blocks planning.**

| # | Question | Resolution (default) | Rationale / grounding |
| --- | --- | --- | --- |
| **CL-1** | Default tile size? | **`DEFAULT_TILE_WIDTH` / `DEFAULT_TILE_HEIGHT`** in `constants.py`, default **16 × 16**; configurable per tileset. | Common pixel-art tile size; Tiled/Aseprite tiles are user-set. Distinct from `TILE_SIZE` (viewport cull, 64). |
| **CL-2** | Margin / spacing support? | **Supported**, default **0 / 0** (`DEFAULT_TILE_MARGIN`/`_SPACING`); configurable. | Tiled tileset slicing supports margin + spacing; 0/0 is the packed default. |
| **CL-3** | Instance orientation (flip/rotate)? | Instances carry **flip-horizontal / flip-vertical** flags (preserved through round-trip); diagonal/rotation reserved to the Tiled flag set but UI exposes at least H/V flip. | Tiled cell gids carry H/V/diagonal flip bits; H/V flip is the pixel-art norm; enables lossless round-trip. |
| **CL-4** | Empty-cell representation? | **Absence of an instance = empty**; maps to **Tiled gid 0** on export/import. | Tiled semantics (gid 0 = empty); sparse storage. |
| **CL-5** | Auto-tile neighbourhood? | Contract depends on **at least the 4 edge-adjacent** neighbours; **8-neighbour (corner-aware)** permitted by the plan. Algorithm family (blob-47/Wang) → AGT-01/ADR. | Observable contract per prompt; family + exact neighbourhood is a HOW (DEP-1/DEP-2). |
| **CL-6** | Infinite-map storage? | **Unbounded, sparse** addressing over arbitrary (incl. negative) integer coords; chunking scheme → AGT-01 (DEP-2). | ROADMAP "infinite maps"; Tiled infinite maps are chunked — chunking is HOW. |
| **CL-7** | One tileset per map or many? | **One or more** tilesets per map under a Tiled-style **global gid** space (per-tileset first-gid offset). | Tiled maps reference multiple tilesets via firstgid; needed for lossless round-trip. |
| **CL-8** | Instances linked or bakeable? | **Always linked** (reference tile id); a source-tile edit propagates (REQ-P6-LOGIC-006). Baking to pixels → Phase 7 export. | ROADMAP "linked instances that update when the source tile edits"; baking is an export concern. |
| **CL-9** | Scope of "level design" — animated tiles, object/collision layers, iso/hex? | **Deferred**: animated tiles, object/collision layers, non-orthogonal orientations → later phase. Phase 6 ships tileset + tilemap + auto-tiling + multi-layer + infinite over **orthogonal** maps. | Bounds the phase to the ROADMAP Phase-6 bullets + "Done means"; extensible per Art. XI (§6). |
| **CL-10** | Auto-tile reversibility model? | Map stores the **logical** placement; the **display tile is derived** and recomputable; undo restores the logical placement + re-resolved neighbours (REQ-P6-LOGIC-011). | Reversibility per prompt; separating logical vs display keeps round-trip lossless. |
| **CL-11** | Source-tile edit mechanism / undo? | Editing a source tile writes the **source image sub-rectangle** for that id (reusing the reversible pixel-edit pattern, HIS-1); one `QUndoCommand`. | Reuses PB-1 + the shipped reversible-op pattern; propagation is automatic (REQ-P6-LOGIC-006). |
| **CL-12** | Stamping tool set? | **Stamp (single) + eraser + rectangle-fill** as the default set; a same-tile flood **bucket** is optional/plan-level. | Minimal Tiled-parity tool set; bucket is a convenience the plan may add. |
| **CL-13** | Are navigation / selection undoable? | **No** — pan / zoom / active-tile / active-layer selection are view state; only tileset/tilemap *edits* are `QUndoCommand`s (REQ-P6-UI-013). | Editor norm; mirrors Phase-4/5 selection being non-undoable. |
| **CL-14** | 8K tilemap perf budget? | Bound by **`FRAME_BUDGET_MS` (16 ms)** for the visible viewport; tile-culling + dirty-rect strategy → AGT-10 (DEP-3). | Article VI; the render strategy is AGT-10's, the budget is fixed. |
| **CL-15** | Tile colour mode? | Tiles inherit the **source image's `ColorMode`** (RGBA or indexed, CM-1). | The source is a `PixelBuffer` with a fixed mode; tiles are its regions. |
| **CL-16** | Native `.pixproj` persistence of tilemaps? | **Yes** — tilesets + tilemaps round-trip in `.pixproj`; back-compat read of tilemap-less projects (REQ-P6-DATA-004); schema-version choice → AGT-01 (DEP-2). | The tilemap is part of the document; must reopen exactly, mirroring the Phase-5 tag-persistence precedent. |

**SUSPEND / escalate:** *none.* The scope risks — **auto-tiling algorithm family**, the **Tiled JSON
encoding set**, and **infinite-map chunking** — are **named HOW decisions** (DEP-1/DEP-2, grounded by
the Researcher and owned by AGT-01), not open functional ambiguities: this spec fixes the *observable
contract* (deterministic + reversible + edge-neighbour-dependent auto-tiling; valid Tiled map that
round-trips losslessly; unbounded-sparse map) and Tiled-parity defaults regardless. The
"level-design" scope is bounded by *scoping down* to orthogonal maps + deferring animated tiles /
object layers / non-orthogonal orientations (CL-9), a category-1 decision, not a blocker. **No
functional ambiguity that changes acceptance criteria remains unresolved.**

---

## 11. Acceptance criteria — Gherkin scenarios

One scenario per testable behaviour. Logic/data scenarios are for **AGT-04** (pytest + Hypothesis,
headless); UI scenarios are for **AGT-06** (pytest-qt, `QT_QPA_PLATFORM=offscreen`), **each run under
BOTH light and dark themes** (REQ-P6-UI-016, expressed once as a global rule). Scenario ids map to
`traceability.md`; tests are authored later (`pending`).

> Global rule (UI scenarios): *Given the app runs headless (`QT_QPA_PLATFORM=offscreen`) — the
> scenario is executed and asserted identically under the light theme and the dark theme.*

### Feature: Tileset slicing & tile identity (REQ-P6-LOGIC-001..004)
```gherkin
Scenario: SC-L001-1 a tileset slices a source image into a deterministic tile grid
  Given a 64x32 source image, tile size 16x16, margin 0, spacing 0
  When the tileset is sliced
  Then it yields 4x2 = 8 tiles and re-slicing the same inputs yields the identical grid

Scenario: SC-L001-2 invalid slicing parameters are rejected
  Given a source image and a tile size exceeding MAX_TILE_DIMENSION (or non-positive)
  When slicing is attempted
  Then a domain error is raised (no silent degradation)

Scenario: SC-L002-1 a tile derives its pixels from the source region (PB-1), not a stored copy
  Given a sliced tileset over a source image
  When tile id 3's pixels are read
  Then they equal PixelBuffer.region of that id's source rectangle
  And the tile's ColorMode equals the source image's ColorMode

Scenario: SC-L003-1 tile ids are stable and row-major; id -> region is a pure function
  Given a sliced tileset
  Then tile ids run row-major left-to-right top-to-bottom
  And id -> source-region is total over the valid id range and identical on repeat

Scenario: SC-L003-2 multiple tilesets compose into a global gid space
  Given two tilesets referenced by one map with first-gid offsets
  Then every tile is addressable by a unique global gid (Tiled first-gid model)

Scenario: SC-L004-1 editing a source tile is reversible and seen by all readers
  Given a sliced tileset with a tile painted red
  When the source tile's sub-rectangle is edited to blue via a command and then undone
  Then every reader of that tile id sees blue after do and red after undo
```

### Feature: Linked instances & tilemap model (REQ-P6-LOGIC-005..008)
```gherkin
Scenario: SC-L005-1 a cell stores a linked instance (tile id + orientation), not pixels
  Given a tilemap layer
  When tile id 5 with flip-horizontal is stamped at cell (2,3)
  Then the cell reports gid 5 and flip-horizontal and holds no pixel copy
  And an empty cell reports empty (Tiled gid 0 semantics)

Scenario: SC-L006-1 a source-tile edit propagates to every placed instance
  Given tile id 5 stamped at 100 cells across two layers
  When the source tile id 5 is edited
  Then rendering every one of those cells reflects the edit (no per-instance duplication)

Scenario: SC-L007-1 stamp / erase / rectangle-fill are reversible
  Given a tilemap layer
  When a stamp, an erase, and a rectangle-fill are each applied via a command and then undone
  Then each undo restores the exact prior cell contents (id + orientation, or empty)

Scenario: SC-L007-2 stamping an unknown tile id is rejected
  Given a tilemap and a gid outside every referenced tileset
  When a stamp is attempted
  Then a domain error is raised

Scenario: SC-L008-1 map layers add / remove / reorder / visibility are reversible
  Given a tilemap with layers [A, B]
  When a layer is added, reordered, hidden, and removed, each via a command and then undone
  Then each undo restores the exact prior layer order, contents, and visibility
  And exceeding MAX_TILEMAP_LAYERS raises a domain error
```

### Feature: Infinite map & auto-tiling (REQ-P6-LOGIC-009..011)
```gherkin
Scenario: SC-L009-1 cells address arbitrary integer coordinates, sparsely
  Given an empty tilemap layer
  When a tile is stamped at (-1000, 5000) and an unset cell (0,0) is read
  Then the stamp succeeds (no fixed-size wall), (0,0) reads empty, and only non-empty cells are stored

Scenario: SC-L010-1 auto-tiling resolves the display tile deterministically from neighbours
  Given auto-tiling enabled and a placed tile with a fixed neighbour configuration
  When the display tile is resolved twice
  Then both resolutions yield the identical display tile (determinism)
  And changing an edge-adjacent neighbour changes the resolved display tile

Scenario: SC-L011-1 auto-tiling is reversible / preserves the logical placement
  Given auto-tiling enabled and a stamp that re-resolves neighbouring cells
  When the display tiles are resolved and then the stamp is undone
  Then the logical placement is recovered exactly and re-resolved neighbours are restored
```

### Feature: Reversibility & map render (REQ-P6-LOGIC-012..013)
```gherkin
Scenario: SC-L012-1 every model mutation is a do/undo pair; view state is not
  Given the tilemap model
  When any edit (stamp/erase/fill, layer op, source-tile edit, slice reconfigure, attach) is applied
  Then it exposes a do/undo pair that restores the exact prior state
  And changing pan/zoom/active-tile/active-layer selection produces no reversible mutation

Scenario: SC-L013-1 the map renders by resolving instances and compositing layers (PB-1 / CO-4 reuse)
  Given a two-layer map with a bottom opaque tile and a top half-alpha tile at the same cell
  When a viewport region is rendered
  Then each cell's instance is resolved to source-tile pixels (flip applied) and blitted,
       and the layer stack is flattened via blend.composite_stack (compositing not re-implemented)
  And the tileset source buffers and cell data are byte-for-byte unchanged
```

### Feature: Bounds & defaults (REQ-P6-LOGIC-014)
```gherkin
Scenario: SC-L014-1 tileset/tilemap bounds come from constants and are enforced
  Given a slice producing more than MAX_TILESET_TILES tiles, or a layer count over MAX_TILEMAP_LAYERS
  Then a domain error is raised

Scenario: SC-L014-2 default tile size / margin / spacing come from constants and are distinct from TILE_SIZE
  Given a fresh tileset configuration
  Then the tile size equals DEFAULT_TILE_WIDTH / DEFAULT_TILE_HEIGHT and margin/spacing default to 0/0
  And the tileset tile dimension is not the viewport-cull TILE_SIZE (64)
```

### Feature: Tileset editor & slicing UI (REQ-P6-UI-001..003)
```gherkin
Scenario: SC-UI-001-1 the tileset editor shows sliced tiles and selects one
  Given a source image sliced into tiles
  When the tileset editor is shown and the user clicks a tile
  Then the tiles are laid out by their row-major ids and the clicked tile becomes the active selection (no undo entry)

Scenario: SC-UI-002-1 slicing configuration re-slices the tileset
  Given the tileset editor
  When the user sets tile size, margin and spacing
  Then the tile grid updates to the new slice and out-of-range values are rejected

Scenario: SC-UI-003-1 editing a source tile updates placed instances live
  Given tile id 5 stamped on the tilemap and the tileset editor open
  When the user paints into source tile id 5
  Then every placed instance updates on the canvas and the edit is one QUndoCommand
```

### Feature: Tilemap canvas & stamping tools (REQ-P6-UI-004..007)
```gherkin
Scenario: SC-UI-004-1 the tilemap canvas shows the composited layer stack
  Given a multi-layer tilemap
  When the canvas is shown
  Then it renders each cell resolved to its source-tile pixels with layer order and visibility honoured

Scenario: SC-UI-005-1 the stamp tool places a linked instance as one command
  Given the selected tile and an empty target cell
  When the user stamps
  Then a linked instance appears at the cell and exactly one QUndoCommand is pushed

Scenario: SC-UI-006-1 the eraser clears a cell as one command
  Given a cell holding an instance
  When the user erases it
  Then the cell becomes empty, one QUndoCommand is pushed, and undo restores the instance

Scenario: SC-UI-007-1 rectangle-fill fills a region as one command
  Given the selected tile
  When the user drags a rectangle-fill over a region
  Then every cell in the region holds the tile and exactly one QUndoCommand is pushed
```

### Feature: Layers, auto-tile, infinite navigation, import/export (REQ-P6-UI-008..013)
```gherkin
Scenario: SC-UI-008-1 tilemap layer management pushes one command per change
  Given a tilemap
  When the user adds, reorders, hides, and removes a layer
  Then each change pushes exactly one QUndoCommand and the active layer receives stamps

Scenario: SC-UI-009-1 enabling auto-tiling resolves edges on stamp, undoably
  Given auto-tiling enabled on the active layer
  When the user stamps a tile adjacent to existing tiles
  Then affected cells' display tiles resolve deterministically from neighbours
  And the whole stamp (including neighbour re-resolution) undoes as one command

Scenario: SC-UI-010-1 the user can pan into empty infinite-map space and stamp
  Given a tilemap
  When the user pans far beyond the populated bounds and stamps
  Then the stamp succeeds with no fixed-size wall and navigation pushes no QUndoCommand

Scenario: SC-UI-011-1 export writes Tiled-compatible JSON
  Given a tilemap
  When the user triggers export
  Then a Tiled-compatible JSON file is written to the chosen (portable) path

Scenario: SC-UI-012-1 import reconstructs an equivalent tilemap; malformed input errors gracefully
  Given a Tiled JSON map file and, separately, a malformed file
  When the user imports each
  Then the valid file yields an equivalent tilemap and the malformed file surfaces a user-facing error (no crash)

Scenario: SC-UI-013-1 every edit is one undoable command; view ops are not
  Given the tileset/tilemap UI
  When any edit (stamp/erase/fill, layer op, source-tile edit, slice reconfigure) is performed
  Then exactly one QUndoCommand is pushed and undo restores the exact prior state
  And pan / zoom / active-tile / active-layer selection push no command
```

### Feature: Performance, a11y, theming, i18n (REQ-P6-UI-014..017) — NFR
```gherkin
Scenario: SC-UI-014-1 an 8K tilemap canvas renders/stamps/pans within the frame budget
  Given a 7680x4320 multi-layer tilemap
  When the user renders, stamps into, and pans the canvas
  Then the measured per-frame render/update time is <= FRAME_BUDGET_MS (16 ms), rendering only the visible viewport via tile-culling / dirty-rect
  # Measured headless by AGT-10 (perf_profile / frame-profile); over-budget yields an AGT-10
  # optimisation directive (viewport tile-culling / dirty-rect), not a budget relaxation.

Scenario: SC-UI-015-1 tileset/tilemap controls expose accessible names and keyboard focus
  Given the tileset editor and tilemap tool UI
  When each control (tile cells, slicing spin-boxes, tool buttons, layer list + actions, auto-tile toggle, import/export) is inspected and tabbed through
  Then each has a non-empty accessible name, is keyboard reachable in a logical order, and shows a visible focus indicator

Scenario: SC-UI-016-1 the tilemap UI renders correctly in both themes
  Given the app
  When rendered under the light theme and the dark theme
  Then the tileset editor, canvas chrome, tool bar, layer panel and dialogs render legibly with role-based colours

Scenario: SC-UI-017-1 no Phase-6 user-visible string is a bare literal
  Given the Phase-6 ui/ sources
  When string_audit_check runs
  Then it reports zero unwrapped user-visible strings (tool names/tooltips, slicing labels/units, layer actions, auto-tile labels, import/export dialog text, errors)
```

### Feature: Tiled JSON I/O & native persistence (REQ-P6-DATA-001..004)
```gherkin
Scenario: SC-D001-1 a tilemap exports to valid Tiled-compatible JSON
  Given a multi-layer tilemap referencing one or more tilesets
  When it is exported
  Then the JSON is a valid Tiled map (dimensions, tile size, layer stack with cell gids + flip flags, tileset first-gid mapping)

Scenario: SC-D002-1 export then import yields an equivalent tilemap (lossless round-trip)
  Given a tilemap with several layers, flipped instances, and multiple tilesets
  When it is exported and re-imported
  Then the imported tilemap equals the original in layer stack, per-cell gid + flip, layer visibility/order, geometry, and tileset gid mapping

Scenario: SC-D003-1 JSON load is defensive and rejects malformed input
  Given JSON payloads with an out-of-bounds map size, a gid outside the tileset range, an over-sized layer-data payload, and an unknown flip/orientation code
  When each is loaded
  Then each raises ProjectIOError (no eval/exec, no silent acceptance) and paths are portable

Scenario: SC-D004-1 tilesets/tilemaps round-trip in .pixproj; tilemap-less projects still load
  Given a document with tilesets and a tilemap
  When it is saved and reloaded
  Then the tilesets and tilemap are restored identically
  And a project without any tilemap data loads successfully with an empty tilemap collection
```

---

## 12. Exit / status

- Forward spec authored for Phase 6 — Tilemap & Level Design. **35 REQ-IDs**: **14 LOGIC**
  (`REQ-P6-LOGIC-001..014`) + **17 UI** (`REQ-P6-UI-001..017`) + **4 DATA**
  (`REQ-P6-DATA-001..004`), each traced to an S-id / F-finding / forward-inherited primitive
  (PB-1 `PixelBuffer.region`/`.blit` → tiles-as-regions + stamping; CM-1 `ColorMode` → tile mode;
  HIS-1 `history` command pattern → reversibility; CO-4 `blend.composite_stack` → multi-layer
  flatten; IO-3 `project_io.py` defensive-load pattern → Tiled/native JSON I/O; DOC-1 `Document`
  tree → native persistence) per Article X.
- **16 clarification defaults** recorded (§10), each grounded in the ROADMAP "Done means", the
  shipped code, and Tiled parity; **no open clarification blocks planning**.
- **No SUSPEND blocker.** The scope risks — auto-tiling **algorithm family**, the **Tiled JSON
  encoding set**, and **infinite-map chunking** — are named HOW decisions (DEP-1/DEP-2), not open
  functional ambiguities; the observable contracts (deterministic + reversible + edge-neighbour
  auto-tiling; valid Tiled map with lossless round-trip; unbounded-sparse map) are fixed here.
  "Level design" scope is bounded to orthogonal maps + deferral of animated tiles / object layers /
  non-orthogonal orientations (CL-9), a category-1 decision.
- **NEW vs REUSED (§7):** NEW = `logic/tileset.py`, `logic/tilemap.py`, reversible stamp/erase/fill/
  layer/auto-tile + source-tile-edit commands, the tileset/tilemap collection on `Document`, new
  constants, all tileset/tilemap UI, Tiled-JSON export/import + native `.pixproj` persistence.
  REUSED = `PixelBuffer` region/blit (PB-1), `ColorMode` (CM-1), the `history` command pattern
  (HIS-1), `blend.composite_stack` (CO-4), the `project_io.py` defensive-load pattern (IO-3), the
  `Document` tree (DOC-1).
- **New constants flagged for `logic/constants.py`** (Article II, BF-2): `DEFAULT_TILE_WIDTH` (16),
  `DEFAULT_TILE_HEIGHT` (16), `DEFAULT_TILE_MARGIN` (0), `DEFAULT_TILE_SPACING` (0),
  `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`. The shipped `TILE_SIZE` (64,
  viewport-culling) is **distinct** and must not be reused as the tile dimension.
- **Dependencies flagged:** DEP-1 (Researcher `docs/research-phase6-tilemap.md` — auto-tile family /
  neighbourhood, Tiled encoding set, infinite-map chunking; concurrent/not-yet-present), DEP-2
  (AGT-01 plan/ADR — auto-tile family, JSON encoding set, chunking, `.pixproj` schema version), DEP-3
  (AGT-10 — viewport tile-culling + dirty-rect recomposite for REQ-P6-UI-014).
- Acceptance scenarios cover every functional and NFR requirement; forward matrix in
  `traceability.md` (0 uncovered). Tests authored later by AGT-04 (logic/data) / AGT-06 (UI),
  `pending`.
- **STATUS: COMPLETED.**
</content>
</invoke>
