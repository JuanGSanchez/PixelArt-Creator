# Tilemap & level design

The **tilemap system** turns a source image into a reusable **tileset** and lets
you paint large levels with those tiles on a **multi-layer, infinite map**: slice
an image into indexed tiles, stamp / erase / fill cells, let **auto-tiling**
resolve borders for you, flip and rotate tiles as you place them, and
**export / import** the whole map as Tiled-compatible JSON. Every map edit is a
single undo step.

!!! note "Logical vs. displayed tiles"
    Auto-tiling separates the tile you *place* (the **logical** tile) from the
    tile that is *shown* (the **display** tile). You paint one "wall" tile and
    the map picks the correct edge/corner variant from its neighbours; the
    logical placement is what is stored and what round-trips, so the result is
    **deterministic and reversible**. Turning auto-tiling off shows the logical
    tile directly.

## Tilesets

A **tileset** is a source image sliced into a grid of equally-sized tiles. Open
the **Tileset** panel and add a tileset from an image; the slicer reads the
image with your **tile size**, optional outer **margin** and inter-tile
**spacing**, and indexes the resulting tiles left-to-right, top-to-bottom
starting at `0`.

- Each tile is a region of the source buffer, so a tileset is **backed by one
  image** rather than many copies.
- **Editing a source tile propagates** to every placed instance of that tile
  across every layer — repaint the tile once and the whole level updates.
- The panel shows the sliced tiles as a pick grid; the selected tile is the one
  the stamp tool paints.

!!! tip "Margin and spacing"
    `margin` is the border skipped around the whole image; `spacing` is the gap
    skipped **between** tiles. Sheets exported with a 1-px gutter typically need
    `spacing = 1` (and `margin = 1` if the gutter also wraps the edge) so the
    slicer lands exactly on each tile.

## Painting a tilemap

The **tilemap canvas** paints cells on a grid, one tile per cell. Pick a tile in
the tileset panel, then use the map tools:

| Tool | What it does |
| --- | --- |
| **Stamp** | Places the selected tile in the cell under the cursor (drag to paint a run). |
| **Erase** | Clears the cell back to empty. |
| **Fill** | Flood-fills the contiguous region of like cells under the cursor with the selected tile. |

Each stamp / erase / fill is **exactly one undo step**, and undo restores the
exact prior cells. Painting near existing tiles re-resolves the **auto-tile**
neighbourhood so borders stay correct as you draw (see below).

### Flip and rotate

Before you stamp, you can transform the tile: **H-flip** and **V-flip** mirror
it, and **rotate** steps it through the four right-angle orientations (the D4
rotations). The transform is stored per placed cell as a compact flag on the
tile, so flipping or rotating a tile costs **no extra tileset entries** and
round-trips losslessly. Transforms compose in a fixed order (diagonal, then
horizontal, then vertical) so a given combination always renders identically.

## Auto-tiling

**Auto-tiling** resolves each cell's *display* tile from its **eight
neighbours** (the Blob-47 scheme: an 8-neighbour bitmask with edge-implies-corner
gating, giving 47 distinct tiles). Paint a single "terrain" tile and the map
fills in the correct straight edges, inner and outer corners automatically.

- **Toggle** auto-tiling with the auto-tile control. When it is **on**, painting,
  erasing or filling a cell also re-resolves the affected cell **and its
  neighbours** so the border is always consistent — all inside the same one undo
  step.
- The resolution is a **pure, deterministic function** of the logical placement
  and neighbours, so the same map always renders the same display tiles.
- Turning auto-tiling **off** shows the logical tile you placed directly, without
  border resolution.

## Layers and infinite maps

A tilemap is **multi-layer** — stack a background, terrain and detail layer, each
painted independently — using the same layer model as the rest of the editor
(add / remove / reorder / show-hide). The **Tilemap Layers** panel manages the
stack; visible layers composite together for display.

The map itself is **infinite**: cells are stored as a **sparse grid of 16×16
chunks**, so only the regions you actually paint consume memory. You can stamp
far from the origin (in any direction) without pre-sizing the map, and empty
regions cost nothing. Each cell is a 32-bit tile id (GID) carrying the tile
index plus its flip/rotate flags.

!!! note "Large-map rendering"
    Each visible chunk is rendered once and cached; panning re-uses cached chunks
    rather than repainting them, so scrolling a large map stays smooth. The
    **first** paint of a freshly-visible region is warmed in the background (off
    the GUI thread) so the window stays responsive while it catches up; a warmed
    chunk is a fast blit thereafter, and the cache is held within a bounded
    memory budget.

## Tiled JSON export / import

The map exports to **Tiled-compatible JSON** and re-imports **losslessly** — a
round-trip preserves the layers, every cell and its flip/rotate flags, and any
fields the editor does not itself use (unknown fields are passed through
verbatim).

- **Export** writes a valid Tiled map. Layer data is emitted as **CSV by
  default**; **base64** (raw / gzip / zlib compressed) is also supported.
- **Import** reads Tiled maps written with CSV or base64 (empty / gzip / zlib)
  layer data, and accepts an **external `.tsj`** tileset reference.
- Import is a **defensive, validated load**: a malformed map, an unsupported
  **zstd**-compressed layer, or an external **`.tsx`** tileset reference are
  rejected with a clear error rather than a crash or silent corruption.

!!! tip "Round-trip fidelity"
    Because unknown fields survive the round-trip and flip/rotate flags are
    preserved bit-for-bit, you can move a map between PixelArt Creator and Tiled
    without losing data the other tool added.

## Persistence

Tilesets and tilemaps round-trip through `.pixproj` (schema **version 4**).
Saving then reopening a project restores every tileset (its source and slicing
config) and every tilemap (its layers, cells and per-cell flip/rotate flags)
identically. Projects saved by earlier versions (**v1 / v2 / v3**, before
tilemaps existed) still open — they simply load with no tilesets or tilemaps.

## Undo, redo and what is *not* undoable

- **Undoable (one step each):** stamp / erase / fill a cell (including any
  auto-tile neighbour re-resolution), and add / remove / reorder / show-hide a
  tilemap layer.
- **Not undoable (view state):** selecting a tile in the tileset panel, toggling
  auto-tiling, choosing a flip / rotate for the next stamp, and panning the map.

## What is not covered

- **zstd-compressed** Tiled layer data and **external `.tsx`** tilesets on import
  — rejected by design (import accepts CSV / base64 gzip/zlib and external
  `.tsj`); use one of the supported encodings.
- **Corner / edge Wang** tile sets beyond the Blob-47 8-neighbour scheme — the
  auto-tiler is designed to extend to them in a later phase.
- **Animated tiles** and **object layers** — a later phase; this release covers
  tile layers.
