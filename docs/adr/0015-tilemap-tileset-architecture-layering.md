# ADR-0015 — Tilemap/tileset architecture: three-layer placement, chunked-sparse infinite storage, uint32 GID cell layout, reversible-command contract

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-07-03 |
| Author | Architecture |
| Feature | `phase-6-tilemap` |
| Supersedes | — |
| Superseded by | — |

## Context

Phase 6 introduces the tileset/tilemap model over the shipped substrate: tiles are `PixelBuffer`
regions (PB-1), reversibility reuses the `history` command pattern (HIS-1), multi-layer flatten
reuses `blend.composite_stack` (CO-4). Several architecture decisions must be fixed before code lands
so the DATA/UI slices bind to a stable contract:

1. **File placement** under the three-layer rule (Article I / S11): where `tileset.py`, `tilemap.py`,
   the auto-tiling module, and the Tiled/native I/O live, and how the import graph stays acyclic
   (`check_layering`/`check_cycles`).
2. **Infinite-map storage scope** (DEP-2c): full chunked infinite now vs fixed-size with a
   chunk-ready model, against the ROADMAP "infinite maps" line and the 8K/16 ms budget.
3. **The cell representation** — how a linked instance (gid + flip) is stored, and where the Tiled
   GID flag masks live without creating a forbidden `logic → data` edge.
4. **The reversible-command contract** (DEP + REQ-P6-LOGIC-012): which mutations get do/undo factories
   consistent with the shipped `document.py` `make_*_command` pattern, so the implementation has a fixed contract
   and `ui/commands.py` stays a thin Qt wrapper.

Requirements flagged (BF-2) that new tile constants must be **distinct from the shipped `TILE_SIZE=64`**
(the viewport-culling edge) with unambiguous names.

## Decision

**Place `tileset.py`, `tilemap.py`, `autotile.py` as pure Qt-free `logic/` modules; store tilemap
layers as chunked-sparse uint32 grids supporting full infinite maps now; adopt Tiled's exact 32-bit
GID layout as the canonical cell representation defined in `logic/tilemap.py`; and expose every model
mutation as a `history.Command` factory on the model it mutates.**

- **Placement (Article I).** `logic/tileset.py` (slicing + id↔region + source-tile edit),
  `logic/tilemap.py` (cell model + layers + chunked-sparse infinite + render + reversible ops),
  `logic/autotile.py` (Blob-47 resolver, ADR-0013) are **pure Python, zero Qt**. `data/tiled_io.py`
  owns the Tiled JSON I/O and `data/project_io.py` (extended, ADR-0016) owns native `.pixproj`
  persistence — both **zero Qt**. The tileset editor, tilemap canvas, stamping/layer/auto-tile
  controls and import/export actions live in `ui/`; the **sole Qt file outside `ui/` remains
  `ui/commands.py`**.
- **Layering (acyclic, PL6-D3).** Edges are `document → tileset`, `document → tilemap`,
  `tilemap → tileset`, `tilemap → autotile`, `tilemap → blend`. None of `tileset`/`autotile`/
  `tilemap` imports `document` — `tilemap` composites through the existing `blend`/`pixel_buffer`
  APIs and resolves gids via its own `tilesets` list, mirroring how `blend.py`/`animation.py` avoid a
  `document` import (PL-D2/PL5-D3). `autotile` is a leaf over `constants`. `check_layering` +
  `check_cycles` stay `0`.
- **Cell layout in `logic/`, not `data/` (no `logic → data` edge).** The canonical cell value is a
  **32-bit unsigned int**: low 28 bits = global tile id (`0` = empty, Tiled semantics), top nibble =
  flip/rotate flags. The masks (`FLIPPED_HORIZONTALLY_FLAG=0x80000000`,
  `FLIPPED_VERTICALLY_FLAG=0x40000000`, `FLIPPED_DIAGONALLY_FLAG=0x20000000`,
  `ROTATED_HEXAGONAL_120_FLAG=0x10000000`, `GID_MASK=0x0FFFFFFF`) are **module-local intrinsic
  constants in `logic/tilemap.py`** (deliberately matching Tiled 1.12.2 for a 1:1 lossless map,
  ADR-0001 exemption — the `blend.py` formula-constant precedent). They live in `logic/` so
  `data/tiled_io.py` imports them **downward** (`data → logic`, permitted); a forbidden
  `logic → data` edge never appears.
- **Chunked-sparse infinite maps NOW (PL6-D6).** A `TilemapLayer` stores cells in
  `TILEMAP_CHUNK_SIZE`×`TILEMAP_CHUNK_SIZE` (16×16, Tiled default) dense numpy `uint32` chunks keyed
  by chunk-origin; **only non-empty chunks are held**. Coordinates are arbitrary integers (incl.
  negative), guarded by `MAX_TILEMAP_COORD`; reading an unset cell yields `0`. This satisfies the
  unbounded-sparse contract (REQ-P6-LOGIC-009) directly and maps 1:1 onto Tiled's `chunks[]` (fixed
  maps use one dense `data` block). Full infinite is **shipped, not deferred** — the chunk store *is*
  the sparse model, and viewport-culled rendering (below) keeps it in budget.
- **Render contract.** `Tilemap.render_region(x, y, w, h)` resolves each **visible** cell's instance
  to its source-tile pixels (applying the flip transform), blits via `PixelBuffer.blit` (PB-1), and
  flattens the visible layer stack via `blend.composite_stack` (CO-4). It is **non-destructive**
  (source buffers + cell data byte-for-byte unchanged) and resolves **only the requested region** —
  the seam Rendering & Performance's viewport tile-culling + dirty-rect strategy plugs into (DEP-3, plan §7). Resident
  tile/pixel data is never culled (Article VI §3).
- **Reversible-command contract (HIS-1, REQ-P6-LOGIC-012).** Every model mutation is a
  `history.Command` factory on the model it mutates: on `Tilemap` — `make_stamp_command`,
  `make_erase_command`, `make_fill_rect_command`, `make_add/remove/move_layer_command`,
  `make_set_layer_visibility_command`, `make_attach_tileset_command`; on `Tileset` —
  `make_edit_tile_command` (writes the source sub-rectangle), `make_reslice_command`; on `Document` —
  `make_add/remove_tileset_command`, `make_add/remove_tilemap_command`. Each captures the **minimal
  prior state** and restores it exactly on undo. Under auto-tiling, the stamp/erase command **also
  captures the prior display gids of the re-resolved neighbours** so undo restores the whole affected
  region (ADR-0013 logical/display separation). View state (pan/zoom/active-tile/active-layer
  selection) is **not** a mutation and gets no command (CL-13). `ui/commands.py` wraps each returned
  `Command` in exactly one `QUndoCommand`.
- **Constant naming (Article II / BF-2).** New numerics — `DEFAULT_TILE_WIDTH`/`DEFAULT_TILE_HEIGHT`
  (`16`), `DEFAULT_TILE_MARGIN`/`DEFAULT_TILE_SPACING` (`0`), `MAX_TILE_DIMENSION`,
  `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`, `TILEMAP_CHUNK_SIZE` (`16`), `MAX_TILEMAP_COORD` — go in
  `logic/constants.py` with names **distinct from the shipped `TILE_SIZE=64`** (the viewport-culling
  edge, a *rendering* concept). Phase 6 **never** reuses `TILE_SIZE`/`TILE_BUFFER` as the tileset
  tile dimension.

## Alternatives Considered

- **Auto-tiling folded into `tilemap.py`.** Rejected: the Blob-47 LUT + bit weights are a
  self-contained, independently-testable concern; a leaf `autotile.py` keeps `tilemap.py` focused and
  the LUT unit-testable in isolation.
- **GID masks in `data/tiled_io.py`.** Rejected: `tilemap.py` needs them to interpret a cell's flip
  bits at render time, and a `logic → data` import is **forbidden** (Article I). Placing the
  canonical layout in `logic/tilemap.py` and importing it downward from `data/` is the only acyclic
  arrangement.
- **Fixed-size maps now, chunks later.** Rejected: the spec's unbounded-sparse contract
  (REQ-P6-LOGIC-009) and the ROADMAP "infinite maps" line are Phase-6 acceptance; a chunked-sparse
  store is the natural fit and maps 1:1 onto Tiled `chunks[]`, so deferring it would add a later
  migration for no gain. Viewport-culled rendering (DEP-3) makes infinite affordable at 8K.
- **A single dense array per layer (no chunks).** Rejected: an unbounded/negative coordinate space
  cannot be a single dense array; chunking is what makes "empty region costs nothing" true.
- **Command builders on a separate `commands`/service module.** Rejected: the shipped precedent puts
  `make_*_command` on the model (`document.py` frame/layer/tag ops); keeping stamp/erase/layer
  builders on `Tilemap`/`Tileset` matches it and keeps the model self-describing.

## Consequences

**Positive.** The three logic modules are pure, deterministic and headless-testable; layering stays
acyclic and enforced; the uint32 cell layout is both the internal model and the Tiled wire format
(one representation, lossless); infinite maps ship on a sparse store that is affordable at 8K via
viewport culling; every edit is one reversible command wrapped by `ui/commands.py`; the constants are
unambiguous and never collide with `TILE_SIZE`.

**Negative / risk.** The chunk store needs correct empty-cell/empty-chunk semantics (a lingering
empty chunk wastes memory but is not incorrect); the test suite asserts sparse behaviour (SC-L009-1). The
auto-tile neighbour re-resolution must be captured in the reversible command or undo leaves stale
frames — the contract makes it mandatory (SC-L011-1). Render performance at 8K depends on the Rendering & Performance
viewport-culling directive landing (DEP-3); the `render_region` API is the fixed seam, and the budget
is never relaxed (Article VI).

## Grounding

- Spec `specs/phase-6-tilemap/spec.md` §2/§4 (REQ-P6-LOGIC-005/-007/-008/-009/-012/-013), §8
  DEP-2/DEP-3/BF-1/BF-2, §9, §10 CL-3/CL-4/CL-6/CL-13; `plan.md` §3/§4/§5/§7/§8, §12 PL6-D3/D6.
- Research `docs/research-phase-6-tilemap-20260703.md` Topic 2 (§2.5 chunks, §2.6 GID masks), Topic 3
  (uint32 cell layout, numpy mapping), OD-5/OD-8.
- Constitution Article I (three-layer purity + acyclic), II (numerics in `constants.py`;
  intrinsic-local masks, ADR-0001; `TILE_SIZE` distinct — BF-2), VI (16 ms / never cull / never
  relax), VII (coord/tile/layer bounds), IV (headless determinism).
- ADR-0007 (region-scoped recomposite reused for dirty-rect), ADR-0013 (auto-tile logical/display
  split), ADR-0014 (Tiled I/O imports the GID masks), ADR-0016 (`.pixproj` v4 persists the model);
  PB-1/CO-4/HIS-1 forward-inherited primitives.
