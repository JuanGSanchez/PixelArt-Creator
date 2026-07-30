# Plan — Phase 6: Tilemap & Level Design

| Field | Value |
| --- | --- |
| Feature | `phase-6-tilemap` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Governed by | `constitution.md` (Articles I, II, III, IV, V, VI, VII, VIII, X, XI) |
| Mode | **FORWARD / PRE-IMPLEMENTATION** — the HOW for Phase 6 before any `logic/tileset.py`, `logic/tilemap.py`, `logic/autotile.py`, `data/tiled_io.py`, tilemap UI, or `.pixproj` tilemap persistence exists. The `PixelBuffer.region`/`.blit` primitive, `ColorMode`, the `history` command pattern, `blend.composite_stack`, the `Document` tree, and the defensive `data/project_io.py` load pattern are **shipped** and reused, not re-authored. |
| Over spec | `specs/phase-6-tilemap/spec.md` (REQ-P6-LOGIC-001..014, REQ-P6-UI-001..017, REQ-P6-DATA-001..004) + `traceability.md` |
| Stack source | S8 (fixed) — no new technology. Domain internals (auto-tiling family + neighbourhood + bit weights, Tiled JSON encoding set + GID flag masks, infinite-map chunking, GID storage type) are **grounded** by The Researcher (`docs/research-phase-6-tilemap-20260703.md`, **landed**) → PL6-D1 Branch B (no RESEARCH REQUEST). |
| ADRs filed | **ADR-0013** (auto-tiling: Blob-47 8-neighbour bitmask + edge-implies-corner gating, documented bit weights, logical/display separation, corner-Wang extensibility); **ADR-0014** (Tiled JSON I/O scope: CSV-default + base64/gzip/zlib encodings, full 4-bit GID flag handling, embedded-emit + external-`.tsj` import, unknown-field verbatim passthrough); **ADR-0015** (tilemap/tileset architecture: three-layer placement, chunked-sparse infinite storage, uint32 GID cell layout, reversible-command contract, constant naming distinct from `TILE_SIZE`); **ADR-0016** (`.pixproj` schema **v4**: `tilesets` + `tilemaps` on `Document`; v1/v2/v3 back-compat empty collections) |

---

## 1. Purpose (HOW)

This plan defines the technical architecture that realises the approved Phase-6 spec — the
**game-dev pipeline** milestone that turns the shipped `PixelBuffer.region`/`.blit` primitive
(PB-1: *a tile is a buffer region of a source image*) into a **tileset → tilemap → auto-tiling →
Tiled-JSON** toolchain. It maps every REQ to its S11 layer, **freezes the public interface of the
new `logic/tileset.py`, `logic/tilemap.py`, `logic/autotile.py`, and `data/tiled_io.py` (plus the
`document.py` collection extension) before implementation** so the DATA and UI slices bind to a
stable contract, rules the four **DEP-2** HOW decisions (auto-tile family, Tiled JSON encoding set,
infinite-map chunking, `.pixproj` schema version) in **ADR-0013/0014/0015/0016**, routes the
**DEP-3** 8K tilemap render/stamp/pan perf strategy to AGT-10, places all new numerics in
`logic/constants.py` with names **distinct from the shipped `TILE_SIZE`** (Article II / BF-2), and
commits the layering so `check_layering`/`check_cycles` stay green (both exit `0` at plan time —
§11). It is decomposed into dependency-ordered work items in `tasks.md`.

No new stack/library/API is introduced (**PL6-D1 → Branch B**: the stack is fixed by S8; the
auto-tiling algorithm family, Tiled JSON semantics, GID flag masks, chunk conventions and GID
storage type are **grounded, not invented** — `docs/research-phase-6-tilemap-20260703.md` has
landed). The `sdd-analyze` C1 gate is run over constitution/spec/plan/tasks as the pre-implement
gate (Article VIII; see `analyze-report.md`).

## 2. Stack / domain decisions (all grounded — no invention, C1)

| Concern | Choice | Grounding |
| --- | --- | --- |
| Language | Python 3.12+ | S8 |
| Tile = source region | A tile is a `PixelBuffer.region` of a source image (PB-1); the tileset stores **no** detached pixel copy — reading a tile derives from the *current* source, so a source edit is seen by every reader (the linking mechanism) | REQ-P6-LOGIC-002/-004/-006; PB-1 |
| Tile ColorMode | Tiles inherit the source image's `ColorMode` (RGBA/INDEXED) | REQ-P6-LOGIC-002; CM-1; CL-15 |
| Tile id ↔ region | Row-major, stable, pure total function `local_id → TileRegion` using the Tiled slicing formula `col=id%columns; row=id//columns; px=margin+col*(tw+spacing); py=margin+row*(th+spacing)` | REQ-P6-LOGIC-001/-003; research §2.2 |
| Global gid space | Multiple tilesets per map under a Tiled-style **first-gid** offset; resolve `gid → (tileset, local_id)` by *largest `first_gid` ≤ stripped gid*, `local_id = stripped_gid − first_gid` | REQ-P6-LOGIC-003; CL-7; research §2.2/Topic 3 |
| Cell = linked instance | A cell stores a **32-bit GID** (uint32), never pixels: low 28 bits = global tile id, top nibble = flip flags; empty cell = gid `0` (Tiled semantics) | REQ-P6-LOGIC-005; CL-3/CL-4; research Topic 3 |
| Cell bit layout | Adopt Tiled 1.12.2's exact masks as our **canonical** cell layout (1:1, lossless): `FLIPPED_HORIZONTALLY=0x80000000`, `FLIPPED_VERTICALLY=0x40000000`, `FLIPPED_DIAGONALLY=0x20000000`, `ROTATED_HEXAGONAL_120=0x10000000`, `GID_MASK=0x0FFFFFFF`; UI exposes at least H/V flip; D bit is preserved through round-trip | CL-3; research §2.6; ADR-0015 |
| Auto-tiling family | **Blob-47** (8-neighbour occupancy bitmask → edge-implies-corner gating → 47 frames) as the shipped default; documented bit weights `TL=1,T=2,TR=4,L=8,R=16,BL=32,B=64,BR=128`; 256-entry load-time LUT; **logical placement stored separately from the derived display frame** (reversible); corner-Wang left as a plugged extensibility point | REQ-P6-LOGIC-010/-011; research Topic 1 / §1.2 / §1.4; ADR-0013 |
| Infinite maps | **Chunked-sparse** storage NOW: layer cells live in `TILEMAP_CHUNK_SIZE`×`TILEMAP_CHUNK_SIZE` (16×16, Tiled default) dense numpy `uint32` chunks keyed by chunk-origin; only non-empty chunks held; arbitrary/negative coords; empty read yields `0`; coord magnitude guarded by `MAX_TILEMAP_COORD` | REQ-P6-LOGIC-009; CL-6; research §2.5; ADR-0015 |
| Map render | Resolve each non-empty cell's gid → source-tile region (apply flip), blit (PB-1), flatten the visible layer stack via `blend.composite_stack` (CO-4); non-destructive | REQ-P6-LOGIC-013; PB-1/CO-4 |
| Reversible ops | Reuse `history.Command`/`FunctionCommand`; `make_*_command` builders live on the model they mutate (`Tilemap` / `Tileset`) and on `Document` for attach/detach; `ui/commands.py` wraps each as **one** `QUndoCommand` | REQ-P6-LOGIC-007/-008/-011/-012, UI-013; HIS-1; S7/C1/F1; ADR-0015 |
| Tiled JSON encodings | **Emit CSV by default** (human-diffable, simplest lossless) + optional base64 with `gzip`/`zlib`; **import accepts** CSV, base64-none, base64-gzip, base64-zlib; `zstd` is **rejected defensively** (`ProjectIOError`) — it needs a non-stdlib dependency (S8 forbids new tech) | REQ-P6-DATA-001/-002/-003; research §2.3 / OD-4; ADR-0014 |
| Tiled tilesets | **Embed** tilesets on export (self-contained, lossless); import accepts **embedded** and **external `.tsj`** (JSON) references (resolved via `pathlib`); external `.tsx` (XML) is deferred (`ProjectIOError`, clear message) | REQ-P6-DATA-001/-002; research §2.2 / OD-6; ADR-0014 |
| Round-trip fidelity | Preserve **unknown/extra fields verbatim** (opaque passthrough of `properties`, `wangsets`, object layers, `nextlayerid`/`nextobjectid`, unknown top-level keys) so export→import is byte-tolerant lossless | REQ-P6-DATA-002; research OD-7; ADR-0014 |
| Defensive load | Reuse `project_io.py` posture: type/bounds-check map & tile geometry, gid-in-tileset-range, layer-data payload size vs geometry, known encoding/compression/orientation; malformed → `ProjectIOError`; **no `eval`/`exec`**; `pathlib` paths (`path_portability_check`) | REQ-P6-DATA-003; Article VII; IO-3 |
| Native persistence | Extend `data/project_io.py`; **bump `FORMAT_VERSION` to 4**; serialise `Document.tilesets` + `Document.tilemaps`; defensive validated load; **read v1/v2/v3 back-compat** (empty tileset/tilemap collections) | REQ-P6-DATA-004; ADR-0016; DEP-2/CL-16; Article VII |
| Render/pan/stamp perf | Viewport tile-culling (resolve only visible chunks/cells) + dirty-rect recomposite on stamp/pan; AGT-10 profiles + tunes; **budget never relaxed** | REQ-P6-UI-014; DEP-3; Article VI; §7 |
| Testing | pytest + Hypothesis (logic/data), pytest-qt both themes (UI), headless | S8, Article IV |
| Quality | Black + isort + flake8 + mypy (strict for `logic/`+`data/`) | Article III |

No Phase-6 logic/data decision places Qt in `logic/` or `data/` (**PL6-D2 → Branch B held**). All
tileset-editor / tilemap-canvas / stamping / layer / auto-tile / import-export widgets live only in
`ui/`; the sole Qt file outside `ui/` remains `ui/commands.py`.

## 3. Architecture — module → layer map (S11)

Dependency direction is one-way (`ui/` → `logic/`+`data/`) and acyclic (verified §11). The new
Qt-free logic edges are `document → tilemap → tileset` and `tilemap → autotile` / `tilemap → blend`
(never the reverse — §3.4).

### 3.1 New / extended `logic/` modules (Slices 6A/6B/6C — pure, zero Qt)

| Module | Change | Responsibility | Depends on (intra-logic) | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | Add `DEFAULT_TILE_WIDTH`/`DEFAULT_TILE_HEIGHT` (`16`), `DEFAULT_TILE_MARGIN`/`DEFAULT_TILE_SPACING` (`0`), `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`, `TILEMAP_CHUNK_SIZE` (`16`), `MAX_TILEMAP_COORD` (leaf; no imports). **Names distinct from the shipped `TILE_SIZE=64` (viewport-cull edge) — never reused (BF-2).** | — | LOGIC-014 |
| `tileset.py` | **new** | `Tileset` referencing a source `PixelBuffer`; deterministic row-major slice (size/margin/spacing) → `TileRegion`; `local_id ↔ region` pure total map; `tile_pixels` derives via `PixelBuffer.region` (PB-1, no stored copy); reversible `make_edit_tile_command` (writes the source sub-rectangle, HIS-1) + `make_reslice_command`; `first_gid` offset + `contains_gid`/`local_id_for_gid` for the global gid space; bounds (`MAX_TILE_DIMENSION`/`MAX_TILESET_TILES`). Zero Qt; **never imports `document`**. | `pixel_buffer` (`PixelBuffer`, `ColorMode`, `region`), `history`, `constants` | LOGIC-001, 002, 003, 004, 014 |
| `autotile.py` | **new** | Blob-47 resolver (pure): 8-neighbour occupancy → edge-implies-corner gating → one of 47 frame indices via a load-time 256-entry LUT (deterministic, O(1)); `AutotileRuleset` (logical terrain gid + 47 display gids); documented bit weights (module-local intrinsic, ADR-0001). Standalone; imports only `constants`. | `constants` | LOGIC-010, 011 |
| `tilemap.py` | **new** | Canonical uint32 cell bit layout (Tiled masks — module-local intrinsic); `TileInstance` view (`base_gid`/`flip_h`/`flip_v`/`flip_d`); `TilemapLayer` (chunked-sparse `uint32` grid, visibility/opacity); `Tilemap` (ordered layers + referenced tilesets + `infinite` flag + gid resolution). Reversible `make_stamp/erase/fill_rect_command`, `make_add/remove/move_layer_command`, `make_set_layer_visibility_command`, `make_attach_tileset_command` (auto-tile re-resolution folded into stamp/erase, capturing neighbour prior state — REQ-P6-LOGIC-011). `render_region` resolves instances (flip) + `blit` (PB-1) + `composite_stack` (CO-4), non-destructive. Zero Qt; **never imports `document`** (structural reuse — §3.4). | `tileset` (`Tileset`), `autotile` (`AutotileRuleset`, resolver), `blend` (`composite_stack`), `pixel_buffer`, `history`, `constants` | LOGIC-005, 006, 007, 008, 009, 012, 013, 014 |
| `document.py` | extend | Attach `tilesets: List[Tileset]` + `tilemaps: List[Tilemap]` collections (added to `__slots__`, created empty); reversible `make_add/remove_tileset_command` + `make_add/remove_tilemap_command` (attach/detach participate in undo, REQ-P6-LOGIC-012). Frame/layer model unchanged (reused). | `tileset`, `tilemap`, `history`, `constants` | LOGIC-012 (attach/detach), DATA-004 (native persistence surface) |

`constants.py` stays a leaf. The Tiled GID flag masks are the **canonical cell bit layout** and are
**module-local intrinsic constants in `tilemap.py`** (deliberately matching Tiled 1.12.2 for a 1:1
lossless map, ADR-0001 exemption — mirroring how the W3C blend-formula magic numbers stay local to
`blend.py`). They live in `logic/` (not `data/`) so `tilemap.py` needs **no** `data` import (a
`logic → data` edge is forbidden); `data/tiled_io.py` imports them from `tilemap.py` (a permitted
`data → logic` edge). The Blob-47 bit weights + 256→47 LUT are algorithm-intrinsic and stay
module-local in `autotile.py` (ADR-0001).

### 3.2 New / extended `data/` modules (Slice 6D — Qt-free I/O; DEP-2)

| Module | Change | Responsibility | Depends on | REQ |
| --- | --- | --- | --- | --- |
| `tiled_io.py` | **new** | Tiled 1.12.2 JSON map export/import. **Export:** map/tileset/layer objects; embedded tilesets w/ `firstgid`; per-cell uint32 GID incl. flip flags; CSV `data` (default) or base64+`gzip`/`zlib`; `chunks[]` for infinite maps, dense `data` for fixed; emit `version`/`tiledversion`/`orientation`/`renderorder`/`infinite`/`nextlayerid`/`nextobjectid`. **Import:** defensive validated load (bounds/gid-range/payload-size/known-encoding-orientation → `ProjectIOError`, no `eval`/`exec`); base64 decode → decompress → LE uint32; clear the diagonal bit `0x20000000` even for non-hex maps; apply transform order diagonal→H→V at render; unknown fields preserved verbatim (opaque passthrough) for lossless round-trip; `zstd`/`.tsx` → `ProjectIOError`. Zero Qt; `pathlib`. | `logic/tilemap` (masks, `Tilemap`, `TilemapLayer`), `logic/tileset` (`Tileset`), `logic/pixel_buffer`, `constants` | DATA-001, 002, 003 |
| `project_io.py` | extend | Serialise `Document.tilesets` (source-image ref + slicing config) + `Document.tilemaps` (layer stack + linked instances + auto-tile logical placement); **`FORMAT_VERSION = 4`**, `_SUPPORTED_VERSIONS = (1, 2, 3, 4)`; defensive validated load; **v1/v2/v3 back-compat read** → empty tileset/tilemap collections. Frame/tag/layer paths (v3) **reused**. | `logic/tileset`, `logic/tilemap`, `logic/document`, `constants` | DATA-004 |

### 3.3 New / extended `ui/` modules (Slices 6E/6F/6G — Qt only)

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `tileset_editor_panel.py` | **new** | `Tileset_Editor_Panel(QWidget)`: show a source image sliced into its tile grid; slicing spin-boxes (size/margin/spacing, defaults from `DEFAULT_TILE_*`, out-of-range rejected); select the active tile (view state, no undo); paint into a source tile → one `QUndoCommand` (placed instances update live); `tr()` + `changeEvent` retranslate. | `tileset` (slice/`region_of`/`make_edit_tile_command`/`make_reslice_command`), `ui/commands` | UI-001, 002, 003, 013, 015, 016, 017 |
| `tilemap_canvas.py` | **new** | `Tilemap_Canvas(QGraphicsView/Scene)`: render the composited layer stack on the 8K grid via `tilemap.render_region`; pan/zoom into unbounded space (view state, no undo); **stamp** / **eraser** / **rectangle-fill** tools (each one `QUndoCommand`); auto-tile resolution on stamp when enabled. Implements the AGT-10 tile-culling / dirty-rect directive (DEP-3). | `tilemap` (`render_region`, `make_stamp/erase/fill_rect_command`), `autotile`, `ui/commands` | UI-004, 005, 006, 007, 009, 010, 013, 014, 015, 016 |
| `tilemap_layer_panel.py` | **new** | `Tilemap_Layer_Panel(QWidget)`: add / remove / reorder / toggle-visibility tilemap layers (one `QUndoCommand` each); active-layer selection (view state); auto-tile toggle per layer/brush. | `tilemap` layer ops, `ui/commands` | UI-008, 009, 013, 015, 016, 017 |
| `tilemap_io_actions.py` | **new** | Export the active tilemap to Tiled JSON at a user-chosen (portable) path; import a Tiled JSON map (defensive load → equivalent tilemap; malformed → user-facing error, no crash). | `data/tiled_io` (export/import) | UI-011, 012, 015, 016, 017 |
| `main_window.py` | extend | Hold the active tileset / active tile / active tilemap / active layer (view state); dock the tileset editor / tilemap canvas / layer panel; wire import/export actions; attach tilesets/tilemaps to the document. | `document` collections, the new panels | UI-001, 004, 008, 011, 012 |
| `commands.py` | extend | One `QUndoCommand` per tileset/tilemap op, delegating to the returned `history.Command`; no domain math. | `history` + all 6A/6B/6C ops | UI-013 |

### 3.4 Layering proof (PL6-D3 — cycle-free by construction)

The new intra-`logic/` edges are `document → tileset`, `document → tilemap`, `tilemap → tileset`,
`tilemap → autotile`, `tilemap → blend`. None of `tileset`, `autotile`, `tilemap` imports
`document`: `tilemap` resolves layer stacks and composites through the existing `blend` API +
`pixel_buffer`, exactly as `blend.py`/`animation.py` avoid a `document` import (PL-D2/PL5-D3
precedent). `autotile` is a leaf over `constants`. The Tiled GID masks live in `tilemap.py` so
`data/tiled_io.py` imports **downward** (`data → logic`), never `logic → data`. Resulting one-way
chain:

```
ui/  →  data/tiled_io     →  logic/tilemap  →  logic/tileset  →  logic/pixel_buffer
     →  data/project_io    →  logic/document →  logic/tilemap  →  logic/autotile  →  logic/constants
                                    │                        └→  logic/blend  →  logic/color, logic/constants
                                    └→  logic/tileset, logic/tilemap
```

No back-edge (`tileset/autotile/tilemap → document`, `blend → tilemap`, or any
`logic/`/`data/` → `ui/`) exists. `check_layering` + `check_cycles` therefore stay `0` (verified
§11 on the shipped tree; the planned edges are acyclic by design and re-verified when 6A/6B/6C/6D
land).

## 4. `logic/tileset.py` — frozen interface contract (Slice 6A)

Frozen **before** implementation so 6B/6D/6E bind to a stable surface. Qt-free. Exceptions subclass
`ValueError` (Phase-1 convention).

```python
class TilesetError(ValueError): ...

@dataclass(frozen=True)
class TileRegion:
    x: int; y: int; width: int; height: int          # source sub-rectangle (px)

class Tileset:
    def __init__(self, source: PixelBuffer, *,
                 tile_width: int = DEFAULT_TILE_WIDTH,
                 tile_height: int = DEFAULT_TILE_HEIGHT,
                 margin: int = DEFAULT_TILE_MARGIN,
                 spacing: int = DEFAULT_TILE_SPACING,
                 name: str = "Tileset", first_gid: int = 1) -> None:
        """Slice deterministically; invalid params / count > MAX_TILESET_TILES /
        edge > MAX_TILE_DIMENSION → TilesetError."""
    @property
    def columns(self) -> int: ...
    @property
    def rows(self) -> int: ...
    @property
    def tile_count(self) -> int: ...
    @property
    def mode(self) -> ColorMode: ...                  # inherits source mode (CM-1)
    @property
    def first_gid(self) -> int: ...
    def region_of(self, local_id: int) -> TileRegion:  # pure, total over 0..tile_count-1
        """Row-major; TilesetError out of range."""
    def tile_pixels(self, local_id: int) -> PixelBuffer:
        """Derives from the *current* source via PixelBuffer.region (PB-1); no stored copy."""
    def contains_gid(self, gid: int) -> bool: ...
    def local_id_for_gid(self, gid: int) -> int: ...   # gid - first_gid (stripped gid)
    def make_edit_tile_command(self, local_id: int, edited: PixelBuffer) -> Command:
        """Writes the source sub-rectangle for local_id (HIS-1); undo restores prior source
        pixels exactly; every reader of that id sees the change (REQ-P6-LOGIC-004/-006)."""
    def make_reslice_command(self, *, tile_width: int, tile_height: int,
                             margin: int, spacing: int) -> Command:
        """Reconfigure slicing reversibly; bounds enforced (REQ-P6-UI-002)."""
```

## 5. `logic/tilemap.py` + `logic/autotile.py` — frozen contracts (Slices 6B/6C)

```python
# --- logic/tilemap.py — canonical uint32 cell bit layout (module-local, Tiled 1.12.2) ---
FLIPPED_HORIZONTALLY_FLAG  = 0x80000000
FLIPPED_VERTICALLY_FLAG    = 0x40000000
FLIPPED_DIAGONALLY_FLAG    = 0x20000000
ROTATED_HEXAGONAL_120_FLAG = 0x10000000
GID_MASK                   = 0x0FFFFFFF   # low 28 bits = global tile id (0 = empty)

class TilemapError(ValueError): ...

@dataclass(frozen=True)
class TileInstance:
    gid: int                                  # full 32-bit cell value
    @property
    def base_gid(self) -> int: ...            # gid & GID_MASK
    @property
    def flip_h(self) -> bool: ...
    @property
    def flip_v(self) -> bool: ...
    @property
    def flip_d(self) -> bool: ...             # preserved through round-trip (CL-3)

class TilemapLayer:
    name: str; visible: bool; opacity: float
    autotile: Optional["AutotileRuleset"]     # None = literal placement
    def get(self, x: int, y: int) -> int:     # 0 for unset (sparse, no fixed wall)
        ...
    def cells(self) -> Iterator[Tuple[int, int, int]]:   # (x, y, gid>0), chunk order
        ...
    # chunked-sparse: TILEMAP_CHUNK_SIZE dense uint32 chunks keyed by chunk-origin;
    # only non-empty chunks stored; |x|,|y| bounded by MAX_TILEMAP_COORD.

class Tilemap:
    def __init__(self, *, name: str = "Tilemap", infinite: bool = True,
                 tile_width: int = DEFAULT_TILE_WIDTH,
                 tile_height: int = DEFAULT_TILE_HEIGHT) -> None: ...
    tilesets: List[Tileset]                   # global gid space (first_gid offsets)
    layers: List[TilemapLayer]
    def resolve(self, gid: int) -> Tuple[Tileset, int]:
        """largest first_gid <= (gid & GID_MASK) → (tileset, local_id); unknown → TilemapError."""
    # Reversible ops (return an UNAPPLIED history.Command) — REQ-P6-LOGIC-007/-008/-011/-012
    def make_stamp_command(self, layer_index: int, x: int, y: int, gid: int) -> Command:
        """Place a linked instance; unknown base gid → TilemapError. If the layer's autotile
        is set, records the LOGICAL placement + re-resolves affected neighbours, capturing prior
        display gids so undo restores the cell AND re-resolved neighbours (REQ-P6-LOGIC-011)."""
    def make_erase_command(self, layer_index: int, x: int, y: int) -> Command: ...
    def make_fill_rect_command(self, layer_index: int, x: int, y: int,
                               w: int, h: int, gid: int) -> Command: ...
    def make_add_layer_command(self, *, name: str, at: Optional[int] = None) -> Command:
        """MAX_TILEMAP_LAYERS bound (TilemapError past it)."""
    def make_remove_layer_command(self, layer_index: int) -> Command: ...
    def make_move_layer_command(self, from_index: int, to_index: int) -> Command: ...
    def make_set_layer_visibility_command(self, layer_index: int, visible: bool) -> Command: ...
    def make_attach_tileset_command(self, tileset: Tileset) -> Command: ...
    def render_region(self, x: int, y: int, w: int, h: int) -> PixelBuffer:
        """Resolve each visible cell's instance to source-tile pixels (flip applied), blit
        (PB-1), flatten the visible layer stack via blend.composite_stack (CO-4). Non-destructive
        (source buffers + cell data byte-for-byte unchanged). REQ-P6-LOGIC-013."""

# --- logic/autotile.py — Blob-47 (pure, deterministic; bit weights module-local) ---
class AutotileError(ValueError): ...
BLOB_TILE_COUNT: int = 47

@dataclass(frozen=True)
class AutotileRuleset:
    terrain_gid: int                 # the LOGICAL tile the user stamps
    frame_gids: Sequence[int]        # 47 display gids (the blob atlas frames)

def resolve_display_index(occupancy_mask: int) -> int:
    """Raw 8-neighbour occupancy 0..255 → one of 47 blob indices via the 256-entry LUT
    (edge-implies-corner gating; Boris the Brave §1.2). Deterministic, O(1) (P2)."""

def resolve_display_gid(ruleset: AutotileRuleset, occupancy_mask: int) -> int:
    """resolve_display_index → ruleset.frame_gids[index]; the display gid the cell shows."""
```

**Notes.** `tilemap.py` needs no `document`/Qt import (PL6-D3): it composites through
`blend.composite_stack` and `pixel_buffer`, resolves gids via its own `tilesets`, and derives
auto-tile display frames via `autotile`. Determinism (P2, SC-L010-1) is intrinsic: the LUT is a
static table, no RNG, no time. Undo restores the exact prior cell contents (id + orientation, or
emptiness) and — under auto-tiling — the re-resolved neighbour display gids (REQ-P6-LOGIC-011).

## 6. `data/` contracts — Tiled JSON I/O (`tiled_io.py`) + `.pixproj` v4 (DEP-2)

```python
# data/tiled_io.py — reuses the project_io defensive posture (IO-3); raises ProjectIOError
def export_tilemap(tilemap: Tilemap, *, encoding: str = "csv",
                   compression: Optional[str] = None) -> dict: ...   # Tiled JSON map object
def write_tiled_json(path: PathLike, tilemap: Tilemap, *,
                     encoding: str = "csv", compression: Optional[str] = None) -> None: ...
def import_tilemap(data: dict) -> Tilemap: ...                       # defensive validated
def read_tiled_json(path: PathLike) -> Tilemap: ...
```

- **Export (REQ-P6-DATA-001).** Map object with `version="1.10"`, `tiledversion="1.12.2"`,
  `type="map"`, `orientation="orthogonal"`, `renderorder="right-down"`, `width`/`height` (tiles),
  `tilewidth`/`tileheight`, `infinite`, `nextlayerid`/`nextobjectid`, `tilesets[]` (**embedded**,
  each with `firstgid`), `layers[]` (tile layers; `data` for fixed, `chunks[]` for infinite).
  Layer data is CSV by default or base64 (`gzip`/`zlib`); GIDs are LE uint32 including flip flags.
- **Import (REQ-P6-DATA-002/-003).** Base64 decode → decompress → LE uint32; **clear the diagonal
  bit `0x20000000` even for non-hex maps** (documented Tiled gotcha, research §2.6); transform order
  diagonal→H→V applied at render. Validate map/tile geometry + layer sizes (against S12 bounds),
  gid-in-tileset-range, payload size vs declared geometry, known encoding/compression/orientation →
  else `ProjectIOError`. `zstd` compression and external `.tsx` (XML) tilesets → `ProjectIOError`
  (unsupported, defensive; both would need new tech — S8). Unknown/extra fields preserved verbatim
  (opaque passthrough) → lossless round-trip of what Tiled expresses beyond our model.
- **`.pixproj` v4 (REQ-P6-DATA-004, ADR-0016).** `data/project_io.py` bumps `FORMAT_VERSION` to
  `4`, `_SUPPORTED_VERSIONS = (1, 2, 3, 4)`; serialises `Document.tilesets` (source-image ref +
  slicing config) + `Document.tilemaps` (layer stack + linked instances + auto-tile logical
  placement); v1/v2/v3 load with empty tileset/tilemap collections (back-compat); defensive tag
  load path (v3) reused. Native mode, not Tiled JSON, on disk (the Tiled path is the interchange).

## 7. Performance — DEP-3 routing to AGT-10 (ADR-0015 §Perf)

REQ-P6-UI-014 binds render/stamp/pan of an 8K (7680×4320) tilemap to `FRAME_BUDGET_MS = 16`.
Resolving every cell of a (possibly infinite) map per frame blows the budget. Architecture
commitment (AGT-10 profiles + tunes; AGT-05 implements; **budget never relaxed**, Article VI §2):

1. **Viewport tile-culling.** `render_region(x, y, w, h)` resolves only the cells intersecting the
   **visible viewport** (only the non-empty chunks in range), never the whole map. The chunked-sparse
   store makes "visible chunks" an O(visible) lookup.
2. **Dirty-rect recomposite.** A stamp/erase/fill recomposites only the affected cells' rect
   (reusing the ADR-0007 region path: `composite_stack(region=…)` returns a region-sized buffer
   blitted into the resident composite), not the full canvas.
3. **Resident tile/pixel data never culled** (Article VI §3, F7) — only Qt rendering is
   viewport-scoped; the tileset source buffers stay resident.
4. **BF-1 (draw method).** Whether tile instances are individual `QGraphicsPixmapItem`s vs. a single
   pre-composited layer pixmap redrawn by dirty region is an AGT-05 HOW; the plan requires only the
   composited-map behaviour + culled/dirty redraw.

**Ownership.** AGT-10 owns the measurement (`perf_profile`/`frame-profile`, e.g. a `--tilemap`
scenario) + any viewport directive; AGT-05 implements the culled/dirty redraw; AGT-01 fixes the
culled-region + non-destructive `render_region` API commitment (ADR-0015). An over-budget profile
yields an AGT-10 optimisation directive, not a budget change.

### 7.1 Shipped render approach (post loop-back — reflected here for plan↔code fidelity, C1)

The DEP-3 seam resolved into three cooperating pieces on the frozen `render_region` API (no signature
or budget change):

1. **Vectorised `render_region` (logic).** `render_region(x, y, w, h)` operates in **pixel space**
   (the composite-region unit, matching `blend.composite_stack` and the `drawBackground` exposed
   rect), resolves only intersecting cells per chunk, applies flip and blits via numpy, and flattens
   the visible stack via `composite_stack` (CO-4). Non-destructive, Qt-free.
2. **Per-chunk `QPixmap` cache (ui).** `ui/tilemap_chunk_cache.py` holds a bounded LRU of one rendered
   `QPixmap` per `TILEMAP_CHUNK_SIZE` chunk, keyed by `(cx, cy)` and **validated by the logic layer's
   O(1) `Tilemap.chunk_version(cx, cy)`** — a monotonic per-chunk counter bumped by every cell/layer
   mutation. A version mismatch is a cache miss → that chunk (only) re-renders; every untouched chunk
   re-blits. Only the derived pixmaps are bounded/culled; resident tileset pixel data is never culled
   (Article VI §3).
3. **Off-GUI-thread cold-warm (ui).** A scene-owned `QThreadPool` worker calls the **Qt-free**
   `render_region` off-thread for cold chunks and returns the `PixelBuffer` over a queued GUI-thread
   signal; the `QPixmap` is constructed only in the GUI-thread slot (no cross-thread Qt). Teardown is
   the deterministic `Tilemap_Canvas.shutdown_warm → MainWindow.shutdown_prewarm → closeEvent` chain
   (mirroring the Phase-5 `CanvasScene.shutdown_prewarm` fix).

`chunk_version` is an **additive, Qt-free** logic surface consistent with ADR-0015 (the render seam
belongs to `logic/`; Qt stays in `ui/`). The two-part perf gate: part-1 `perf_profile.py --tilemap`
vs `FRAME_BUDGET_MS` (16 ms, the per-cell resolve+blit+composite seam); part-2 `--tilemap
--budget-ms <TILEMAP_VIEWPORT_CEILING_MS>` (3000 ms) for the cold full-viewport ceiling.

## 8. Constant placement (Article II / BF-2)

All in `logic/constants.py` (leaf). **New names are DISTINCT from the shipped `TILE_SIZE` (`64`,
the viewport-culling edge) and `TILE_BUFFER` — Phase 6 never reuses them as the tileset tile
dimension** (AGT-02's BF-2 warning honoured):

| Constant | Value | Source |
| --- | --- | --- |
| `DEFAULT_TILE_WIDTH` | `16` | CL-1 (common pixel-art tile; Tiled/Aseprite user-set) — distinct from `TILE_SIZE=64` |
| `DEFAULT_TILE_HEIGHT` | `16` | CL-1 |
| `DEFAULT_TILE_MARGIN` | `0` | CL-2 (Tiled packed default) |
| `DEFAULT_TILE_SPACING` | `0` | CL-2 |
| `MAX_TILE_DIMENSION` | `1024` | defensive bound (Article VII); generous vs pixel-art tile sizes |
| `MAX_TILESET_TILES` | `65536` | defensive bound; ample local-id space under the 28-bit gid range |
| `MAX_TILEMAP_LAYERS` | `256` | defensive bound; parallels `MAX_LAYERS_PER_FRAME` |
| `TILEMAP_CHUNK_SIZE` | `16` | Tiled default chunk edge (research §2.5) |
| `MAX_TILEMAP_COORD` | `1048576` | defensive coord-magnitude guard (2^20) for infinite maps (REQ-P6-LOGIC-009) |

Tiled GID flag masks → **module-local intrinsic** in `tilemap.py` (canonical cell layout, ADR-0001
exemption, matching the `blend.py` formula-constant precedent). Blob-47 bit weights + 256→47 LUT →
module-local intrinsic in `autotile.py`. Tiled `version`/`tiledversion` strings + encoding names →
module-local format identifiers in `tiled_io.py` (ADR-0001, like the Phase-7 extension sets).
`FORMAT_VERSION` stays format-intrinsic local to `project_io.py` (ADR-0001/0006/0012 precedent).

## 9. Implementation strategy — dependency-ordered slices

Logic-first vertical slices (detailed work items in `tasks.md`):

- **6A — tileset (logic)**: `constants.py` + `tileset.py`. REQ-P6-LOGIC-001..004, -014. AGT-03 + AGT-04.
- **6B — tilemap model + reversible ops (logic)**: `tilemap.py` (cell layout, layers, chunked-sparse
  infinite, stamp/erase/fill, layer ops, render). REQ-P6-LOGIC-005..009, -012, -013. AGT-03 + AGT-04.
- **6C — auto-tiling (logic)**: `autotile.py` (Blob-47 LUT + ruleset) + `tilemap` integration
  (logical/display separation, reversible re-resolution). REQ-P6-LOGIC-010, -011. AGT-03 + AGT-04.
- **6D — data**: `tiled_io.py` (Tiled export/import + defensive load) + `project_io.py` v4 (native
  persistence + back-compat). REQ-P6-DATA-001..004. AGT-03 + AGT-04.
- **6E — tileset editor UI**: REQ-P6-UI-001..003, -013, -015..017. AGT-05 + AGT-06 + AGT-07.
- **6F — tilemap canvas + stamping + layers + auto-tile + infinite nav + perf**: REQ-P6-UI-004..010,
  -013, -014 (coordinated with AGT-10, DEP-3), -015, -016. AGT-05 + AGT-06 + AGT-10.
- **6G — import/export UI**: REQ-P6-UI-011, -012, -015..017. AGT-05 + AGT-06 + AGT-07.

Reversible-op boundary: every mutating tileset/tilemap op is a `history.Command` from
`tileset.py`/`tilemap.py`/`document.py`, wrapped as exactly one `QUndoCommand` in `ui/commands.py`
(Article I §2). Pan / zoom / active-tile / active-layer selection mutate no model state → no command
(CL-13).

## 10. Constitution compliance (self-check)

- **I:** `tileset.py`/`tilemap.py`/`autotile.py` + the `document.py`/`constants.py` extensions are
  pure (zero Qt); `data/tiled_io.py` + `project_io.py` are Qt-free I/O; all tileset/tilemap widgets
  in `ui/`; sole outside-`ui/` Qt file stays `ui/commands.py`. `document → tilemap → tileset`,
  `tilemap → autotile`/`blend` one-way; GID masks in `logic/` so no `logic → data` edge (§3.4).
- **II:** nine new numerics in `constants.py`, **names distinct from `TILE_SIZE`** (BF-2); GID masks
  / Blob-47 weights / Tiled version strings are intrinsic-local (ADR-0001).
- **IV:** deterministic slicing, id↔region, instance linking/propagation, reversible
  stamp/erase/fill/layer ops, infinite-sparse addressing, deterministic + reversible auto-tile,
  per-map render reuse (CO-4), Tiled round-trip + defensive load → each maps to a scenario → test
  (`tasks.md`); both themes for UI.
- **V:** REQ-P6-UI-015/016/017 are blocking gates on the tileset editor + tilemap UI.
- **VI:** REQ-P6-UI-014 16 ms budget for the 8K tilemap; viewport tile-culling + dirty-rect;
  resident buffers never culled; budget never relaxed.
- **VII:** tile/layer/coord bounds, invalid-slice guards, defensive validated Tiled/native JSON load;
  no `eval`/`exec`; portable paths.
- **X:** every REQ traces to an S-id / F-finding / forward-inherited primitive (`traceability.md`).
- **XI:** deferring animated tiles, object/collision layers, non-orthogonal orientations, and the
  corner-Wang multi-terrain family (extensibility hook, ADR-0013) adds capability later without
  weakening any article.

## 11. Layering / cycle verification

`python scripts/check_layering.py` → exit **0** (clean, 32 modules) and
`python scripts/check_cycles.py` → exit **0** (no cycles, 78 modules) on the shipped tree at plan
time (baseline, 2026-07-03). The planned edges (`document → tilemap → tileset`, `tilemap → autotile`,
`tilemap → blend`, `data/tiled_io → logic/tilemap`, `data/project_io → logic/tileset`/`tilemap`) are
acyclic by construction (§3.4); both scripts are re-run by AGT-03 when 6A/6B/6C/6D land and gate the
C1 analyze (Article I §4, VIII). See `analyze-report.md` for the C1 verdict.

## 12. Decisions log

| # | Decision | Branch | Rationale |
| --- | --- | --- | --- |
| PL6-D1 | Ungrounded stack/API choice? | **B (no)** | Stack fixed (S8); auto-tile family, Tiled semantics, GID masks, chunking, GID type grounded by landed `docs/research-phase-6-tilemap-20260703.md`. No RESEARCH REQUEST. |
| PL6-D2 | Qt in `logic/`/`data/` or magic number outside `constants.py`? | **B (no)** | All tilemap widgets in `ui/`; nine numerics → `constants.py` (names ≠ `TILE_SIZE`); GID masks / Blob-47 weights / version strings intrinsic-local (ADR-0001). |
| PL6-D3 | tileset/tilemap/autotile layering | — | `document → tilemap → tileset`, `tilemap → autotile`/`blend`; none imports `document`; GID masks in `logic/tilemap` so no `logic → data` edge → acyclic. |
| PL6-D4 | Auto-tiling family (DEP-2a) | Blob-47 | Single-terrain best-in-class self-blend, static inspectable 256→47 LUT ("user-authored deterministic ruleset"), documented bit weights; logical/display split → reversible; corner-Wang extensibility hook (ADR-0013). |
| PL6-D5 | Tiled JSON encoding set (DEP-2b) | CSV emit + base64/gzip/zlib; parse those; reject zstd/`.tsx` | CSV default = simplest lossless/diffable; base64+gzip/zlib use stdlib; zstd/`.tsx` need new tech (S8) → defensive reject; embed on export, accept embedded + external `.tsj`; unknown fields verbatim → lossless round-trip (ADR-0014). |
| PL6-D6 | Infinite-map scope (DEP-2c) | chunked-sparse now | ROADMAP "infinite maps"; 16×16 chunks (Tiled default) are the sparse store; viewport-culled render keeps 8K in budget → full infinite shipped, not deferred (ADR-0015). |
| PL6-D7 | `.pixproj` schema (DEP-2d) | v4 bump | New document-level semantics (tilesets + tilemaps); honest/self-describing + fail-closed (ADR-0016); v1/v2/v3 still load with empty collections. |
| PL6-D8 | Perf (DEP-3) | route to AGT-10 | Viewport tile-culling + dirty-rect recomposite (ADR-0007 region reuse); AGT-10 profiles, AGT-05 implements; budget never relaxed. |
