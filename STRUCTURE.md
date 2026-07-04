# STRUCTURE — Three-Layer Module Map

> The living map of the `pixelart_creator/` three-layer tree (Article I) and each
> module's responsibility + public surface. Maintained by AGT-01 (Architecture) via
> the `interface-contract` / `layer-audit` skills. Layer purity is enforced by
> `scripts/check_layering.py` + `scripts/check_cycles.py` (both must exit `0`).
>
> Layers: `ui/` (PySide6/Qt) → may import `logic/` + `data/`. `logic/` (pure Python,
> **zero Qt**) and `data/` (I/O, **zero Qt**) never import `ui/`. No cycles.

## `pixelart_creator/logic/` — pure domain (zero Qt) — SHIPPED

| Module | Responsibility | Key public surface |
| --- | --- | --- |
| `constants.py` | Single home for numeric tuning values (Article II). | `MAX_CANVAS_WIDTH/HEIGHT`, `TILE_SIZE`, `TILE_BUFFER`, `PARALLAX_FACTOR`, `SCALE_FACTOR`, `FPS_TARGET`, `FRAME_BUDGET_MS`, `MAX_PALETTE_SIZE`, `DEFAULT_FRAME_DURATION_MS`, `PROJECT_ZLIB_LEVEL` **+ (Phase-1 UI, T1):** `GRID_MIN_PIXEL_EDGE_PX`, `OPENGL_VIEWPORT_ENABLED`, `ZOOM_MAX`, `ZOOM_PRESET_STOPS`, `DEFAULT_CANVAS_WIDTH`, `DEFAULT_CANVAS_HEIGHT` |
| `color.py` | RGBA value model, hex (de)serialise, blend, distance. | `rgba`, `is_rgba`, `to_hex`, `from_hex`, `blend_over`, `distance_sq`, `RGBA`, `ColorError` |
| `palette.py` | Indexed palette (≤256), CRUD/reorder/nearest. | `Palette` (get/set/append/remove_at/move/index_of/nearest_index/colors/copy), `PaletteError` |
| `pixel_buffer.py` | NumPy uint8 pixel storage (RGBA/INDEXED), access/region/blit/resize. | `PixelBuffer`, `ColorMode`, `PixelValue`, `PixelBufferError` |
| `drawing.py` | Raster primitives returning changed `(x,y)` coords. | `pencil`, `pick_color`, `line`, `rectangle`, `ellipse`, `flood_fill` |
| `history.py` | Reversible command pattern + bounded undo/redo. | `Command`, `PixelEdit`, `FunctionCommand`, `History`, `record_edit` |
| `document.py` | Document → frames → layers → buffers; resize; **colour-mode authority** — `Document.mode` is the single source of truth (ADR-0008); reversible colour-mode conversion (flatten-then-index / palette-lookup) that flips buffers **and** `Document.mode` atomically, delegating pixels to `palette_ops.to_indexed`/`to_rgba`. | `Document`, `Frame`, `Layer`, `resize_canvas`, `make_convert_to_indexed_command`, `make_convert_to_rgba_command`, `DocumentError` |
| `compactor.py` | Deterministic MaxRects atlas packing (Phase-7 fwd). | `compact`, `Packing`, `Rect`, `CompactionError` |

## `pixelart_creator/logic/` — Phase-2 advanced-drawing — PLANNED (Slice 2A)

> New Qt-free modules frozen by AGT-01 (`interface-contract`) BEFORE implementation so the
> Phase-2 UI slice binds to a stable contract. Exceptions subclass `ValueError` (Phase-1
> convention). `SymmetryAxis` is module-local (plan PL-D3). New constants live in
> `constants.py` (Article II): `ROTSPRITE_UPSCALE_FACTOR=8`, `ROTSPRITE_SIMILARITY_THRESHOLD=100`,
> `MAGIC_WAND_DEFAULT_TOLERANCE=0`, `TILED_PREVIEW_REPEAT=3`, `SCALE_MIN_FACTOR=0.01`, `SCALE_MAX_FACTOR=64.0`.

| Module | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- |
| `selection.py` | Boolean selection-region model + builders + ops + mask-constrained apply + floating move. **Phase-2 floating-selection (REQ-NEW-C, ADR-0009):** non-destructive `FloatingSelection` model + region-scoped `composite_preview` + `copy_selection` sibling builder + `commit_floating` dispatcher; MOVE reuses `move_selection`; `FloatMode` module-local. | `SelectionMask` (is_selected/is_empty/bounds/count/data/copy/invert/cleared/translate/combine), `rect_mask`, `lasso_mask`, `wand_mask`, `apply_masked`, `move_selection`, `SelectionError`, **`FloatMode`, `FloatingSelection`, `lift_selection`, `composite_preview`, `copy_selection`, `commit_floating`** | LOGIC-001..006, 010; **P2-LOGIC-030..036** |
| `transform.py` | Flip / rotate-90 / scale-NN; whole-buffer or selection-aware; reversible builder. | `flip_horizontal`, `flip_vertical`, `rotate_90_cw`, `rotate_90_ccw`, `scale_nearest`, `make_transform_command`, `TransformError` | LOGIC-007..010 |
| `symmetry.py` | Symmetry-axis model + mirrored-coordinate generation. | `SymmetryAxis` (NONE/VERTICAL/HORIZONTAL/BOTH/DIAGONAL), `mirror` | LOGIC-011 |
| `pixel_perfect.py` | Aseprite elbow-removal → clean 1-px stroke path. | `pixel_perfect` | LOGIC-012 |
| `rotsprite.py` | Clean arbitrary-angle rotation (upscale→NN rotate→downscale→detail restore); no new colours. Pins in ADR-0002. | `rotsprite`, `make_rotsprite_command` | LOGIC-013 |
| `tiled.py` | Torus wrap model + 3×3 preview + reversible wrapped edit. | `wrap`, `preview_tiling`, `make_tiled_command` | LOGIC-014 |

## `pixelart_creator/logic/` — Phase-3 colour & palette — PLANNED (Slice 3A)

> Nine new Qt-free modules frozen by AGT-01 (`interface-contract`, plan §6) BEFORE implementation
> so Slices 3B/3C bind to a stable contract. Algorithms grounded by `docs/research-phase3-colour.md`
> (F9). Exceptions subclass `ValueError` (Phase-1 convention); `PaletteError` reused for
> palette-index-bound ops. New tuning scalars → `constants.py` (plan §8: `HARMONY_*_DEG`,
> `RAMP_STEP_COUNT=5`, `BAYER_MATRIX_SIZE=4`, `PALETTE_EXTRACT_DEFAULT_N=16`, `CIEDE2000_KL/KC/KH=1.0`,
> `KMEANS_SEED=0`, `CYCLE_DEFAULT_FPS=10`, `FAVOURITES_MAX=64`). Standard/algorithm constants
> (ΔE00, sRGB/Lab, Bayer, FS) stay **intrinsic-local** (ADR-0001); NES/GB palette data is
> **module-local** in `hardware_palette.py` (ADR-0003). No edits to `color.py`/`palette.py`
> (additive; PL-D6 keeps `palette.py` free of `perceptual` — no cycle).

| Module | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- |
| `color_theory.py` | RGB↔HSV/HSL; harmony sets by hue rotation; shade/tint/tone ramps. | `rgba_to_hsv`/`hsv_to_rgba`/`rgba_to_hsl`/`hsl_to_rgba`, `complementary`/`analogous`/`triadic`/`split_complementary`/`harmony`, `shade_ramp`/`tint_ramp`/`tone_ramp`, `ColorTheoryError` | LOGIC-001..003 |
| `perceptual.py` | sRGB→Lab; ΔE00 (CIEDE2000); perceptual nearest (opt-in over `distance_sq`). | `rgba_to_lab`, `delta_e_2000`, `nearest_index_perceptual` (free fn taking `Palette`, PL-D6) | LOGIC-004, 005 |
| `dither.py` | Ordered/Bayer + Floyd–Steinberg onto a target palette (output ⊆ palette); reversible builder. | `ordered_dither`, `floyd_steinberg`, `make_dither_command`, `DitherError` | LOGIC-006, 007 |
| `hardware_palette.py` | NES (64-entry `2C02G_wiki.pal` decode) + Game Boy (4-shade DMG) reference palettes (module-local data, ADR-0003). | `nes_palette`, `game_boy_palette` (each returns a new independent `Palette`) | LOGIC-008 |
| `quantize.py` | Palette-constraint (⊆) + auto-extract median-cut/k-means (≤N); reversible constraint builder. | `constrain_to_palette`, `median_cut`, `kmeans`, `make_constraint_command`, `QuantizeError` | LOGIC-009..011 |
| `palette_analytics.py` | Per-colour/per-index usage counts across buffer/document (read-only, vectorised F7). | `color_usage_counts`, `index_usage_counts`, `document_usage_counts` | LOGIC-012 |
| `palette_ops.py` | Colour cycling (rotate index range) + palette swap/remap; reversible builders. **Pure mode converters** `to_indexed`/`to_rgba` stay here (called by `document.py`'s conversion commands); the buffer-level `make_to_indexed_command`/`make_to_rgba_command` + `SupportsBuffer` are **retired** — colour-mode authority moved to `document.py` (ADR-0008). | `cycle_palette`, `swap_indices`, `remap_colors`, `to_indexed`, `to_rgba`, `make_cycle_command`, `make_swap_command` | LOGIC-013, 014 |
| `favourites.py` | Persisted, ordered, de-duplicated `Favourites` model + JSON `to/from_serializable`; soft cap. | `Favourites` (add/remove/move/colors/to_serializable/from_serializable), `FavouritesError` | LOGIC-015 |
| `palette_io.py` | Encode/decode `Palette` to/from `.gpl`/`.pal`/hex (defensive, Qt-free). | `encode`, `decode`, `PaletteIOError` | LOGIC-016 |

## `pixelart_creator/logic/` — Phase-4 layer & canvas — BUILT (Slice 4A)

> New `logic/blend.py` + an extension of `document.py`, frozen by AGT-01 (`interface-contract`,
> plan §6) BEFORE implementation so the 4B/4C slices bind to a stable contract. Blend maths grounded
> by `docs/research-blend-modes.md` (W3C Compositing & Blending Level 1). **PL-D2 (cycle-free):**
> `BlendMode` lives in `blend.py`; `document.py` imports it (one-way `document → blend`); `blend.py`
> **never imports `document`** — `composite_stack` consumes nodes via the structural `CompositeNode`
> Protocol. New tuning constants → `constants.py` (T1: `DEFAULT_LAYER_OPACITY=1.0`,
> `MAX_LAYERS_PER_FRAME=256`, `MAX_GROUP_NESTING_DEPTH=8`). Blend-formula magic numbers are
> **intrinsic-local** to `blend.py` (ADR-0001/0005); straight (non-premultiplied) alpha, float32
> 0..1 working space (ADR-0005). New exception `BlendError(ValueError)`; `DocumentError` reused.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +3 tuning bounds (leaf). | `DEFAULT_LAYER_OPACITY`, `MAX_LAYERS_PER_FRAME`, `MAX_GROUP_NESTING_DEPTH` | LOGIC-015 |
| `blend.py` | **new** | `BlendMode` enum (12 — W3C separable set: NORMAL + 11 non-normal; FU-13 corrected from 13, a double-count of normal); separable per-mode maths (W3C); stack compositor honouring visibility/opacity/order/mode/mask + group recursion + region-scoped dirty-rect; NORMAL → `color.blend_over`. Zero `document` import (PL-D2). | `BlendMode` (12 members), `BlendError`, `blend_channel`, `blend_pixels`, `blend_arrays`, `composite_stack(nodes,w,h,*,region=None)`, `CompositeNode` (Protocol) | LOGIC-001..007, 011/012 (compositor side) |
| `document.py` | extend | `Layer` +`blend_mode`/`mask`/`reference`/`smart_source`/`effective_buffer()`; new `LayerGroup` node; reversible attribute + structural + group/mask/reference/smart ops → `history.Command`; lock/reference guard; bounds. | `LayerGroup`, `LayerNode`, `set_layer_opacity/visible/locked/blend_mode`, `make_add/remove/move/duplicate_layer_command`, `make_group/ungroup_command`, `make_attach/detach_mask_command`, `make_set_reference_command`, `make_smart_layer_command`, `ensure_editable` | LOGIC-008..015, 011/012 (node side) |

## `pixelart_creator/logic/` — Phase-5 animation — BUILT (Slice 5A)

> New Qt-free `animation.py` + additive extensions to `document.py` / `constants.py`, on disk and
> green (`check_layering` + `check_cycles` exit 0). Contract frozen by AGT-01 (`interface-contract`,
> plan §4/§5) before implementation so 5B/5C bound to a stable surface. Domain grounded by `docs/research-phase5-animation.md` (Aseprite/Pixelorama parity).
> **PL5-D3 (cycle-free):** the only new intra-logic edge is `document → animation`; `animation.py`
> **never imports `document`** — it consumes layer stacks via `blend.CompositeNode` and durations via
> `Sequence[int]` (the `blend.py` precedent), so `document → animation → blend` stays one-way/acyclic.
> `PlaybackMode` is enumerated **vocabulary** in `animation.py` (not `constants.py`, BF-2). New
> numerics → `constants.py` (`MAX_FRAMES=4096`, `MAX_ONION_SKIN_FRAMES=8`, `DEFAULT_ONION_PREV/NEXT=1`,
> `ONION_TINT_PREV=(255,0,0,255)`, `ONION_TINT_NEXT=(0,0,255,255)`, `ONION_SKIN_OPACITY=0.5`,
> `ONION_SKIN_OPACITY_MIN=0.15`); `DEFAULT_FRAME_DURATION_MS` reused. Animation model + cached
> per-frame composite in **ADR-0011**. New `AnimationError(ValueError)`; `DocumentError` reused.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +8 animation numerics (leaf). | `MAX_FRAMES`, `MAX_ONION_SKIN_FRAMES`, `DEFAULT_ONION_PREV/NEXT`, `ONION_TINT_PREV/NEXT`, `ONION_SKIN_OPACITY`, `ONION_SKIN_OPACITY_MIN` | LOGIC-014 |
| `animation.py` | **new** | `PlaybackMode` enum (LOOP/ONCE/PING_PONG/REVERSE, default LOOP) + `PLAYBACK_STOP`; pure deterministic sequencing (ping-pong endpoints not doubled); onion overlay via `blend.composite_stack`; `FrameTag` model + range validate/clamp; named-animation resolution. Zero Qt, no `document` import (PL5-D3). | `PlaybackMode`, `PLAYBACK_STOP`, `next_frame`, `playback_steps`, `tag_playback_steps`, `onion_overlay`, `OnionContribution`, `FrameTag`, `validate_tag_range`, `clamp_tag_range`, `AnimationError` | LOGIC-001, 002, 003, 009, 011, 012, 013, 014 |
| `document.py` | extend | Reversible frame commands (add/remove/move/duplicate/set-duration); document-level `frame_tags` + reversible tag ops (add/edit/remove) with range-clamp folded into frame add/remove; additive stable `layer_id` on nodes (`_copy_node(new_ids=…)`); `MAX_FRAMES` bound. | `frame_tags`, `make_add/remove/move/duplicate_frame_command`, `make_set_frame_duration_command`, `make_add/edit/remove_tag_command`, `layer_id` | LOGIC-004..010, 014 |

## `pixelart_creator/logic/` — Phase-6 tilemap & level design — BUILT (Slices 6A/6B/6C)

> New Qt-free `tileset.py` + `tilemap.py` + `autotile.py` + additive `document.py`/`constants.py`
> extensions, frozen by AGT-01 (`interface-contract`, plan §4/§5) BEFORE implementation, now SHIPPED
> against those frozen contracts (AGT-03; logic+data 1386 tests green; `check_layering`/`check_cycles`
> exit 0). `tilemap.py` additionally exposes the O(1) `chunk_version(cx, cy)` cache-validation API
> (bumped by every cell/layer mutation) that the `ui/` chunk pixmap cache keys on, and a **vectorised**
> `render_region` (numpy per-chunk resolve+blit) — both Qt-free, on the frozen `render_region` seam. Domain grounded by `docs/research-phase-6-tilemap-20260703.md` (Tiled
> 1.12.2 parity; Blob-47 auto-tiling). **PL6-D3 (cycle-free):** new edges `document → tilemap →
> tileset`, `tilemap → autotile`/`blend`; none imports `document` (`tilemap` composites via
> `blend`/`pixel_buffer`, the `blend.py`/`animation.py` precedent) → acyclic. The **Tiled GID flag
> masks are the canonical uint32 cell layout** and are **module-local intrinsic in `tilemap.py`**
> (matching Tiled 1.12.2, ADR-0001 exemption) so `data/tiled_io.py` imports them downward — **no
> `logic → data` edge**. Blob-47 bit weights + 256→47 LUT module-local in `autotile.py`. New numerics
> → `constants.py` (`DEFAULT_TILE_WIDTH/HEIGHT=16`, `DEFAULT_TILE_MARGIN/SPACING=0`,
> `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`, `TILEMAP_CHUNK_SIZE=16`,
> `MAX_TILEMAP_COORD`) — **names DISTINCT from the shipped `TILE_SIZE=64` (viewport-cull edge, BF-2)**.
> Auto-tiling model in **ADR-0013**; tilemap/tileset architecture + layering + reversible-command
> contract in **ADR-0015**. New `TilesetError`/`TilemapError`/`AutotileError(ValueError)`;
> `DocumentError` reused.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +9 tile/tilemap numerics (leaf); names ≠ `TILE_SIZE`. | `DEFAULT_TILE_WIDTH/HEIGHT`, `DEFAULT_TILE_MARGIN/SPACING`, `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`, `TILEMAP_CHUNK_SIZE`, `MAX_TILEMAP_COORD` | LOGIC-014 |
| `tileset.py` | **new** | `Tileset` over a source `PixelBuffer`; deterministic row-major slice (size/margin/spacing → `TileRegion`); `local_id ↔ region` pure total map; `tile_pixels` derives via `PixelBuffer.region` (PB-1, no stored copy); `first_gid` global gid space; reversible source-tile edit + reslice. Zero Qt; no `document` import. | `Tileset`, `TileRegion`, `region_of`, `tile_pixels`, `first_gid`, `contains_gid`, `local_id_for_gid`, `make_edit_tile_command`, `make_reslice_command`, `TilesetError` | LOGIC-001, 002, 003, 004, 014 |
| `autotile.py` | **new** | Blob-47 resolver: 8-neighbour occupancy → edge-implies-corner gating → 256-entry LUT → one of 47 frame indices (deterministic, O(1)); `AutotileRuleset` (terrain gid + 47 display gids). Bit weights + LUT module-local (ADR-0001). Imports only `constants`. | `resolve_display_index`, `resolve_display_gid`, `AutotileRuleset`, `BLOB_TILE_COUNT`, `AutotileError` | LOGIC-010, 011 |
| `tilemap.py` | **new** | Canonical uint32 cell bit layout (Tiled masks, module-local); `TileInstance` (`base_gid`/`flip_h`/`flip_v`/`flip_d`); `TilemapLayer` (chunked-sparse `uint32` grid); `Tilemap` (ordered layers + tilesets + `infinite` + gid resolve). Reversible stamp/erase/fill + layer add/remove/move/visibility + attach-tileset (auto-tile re-resolution folded in, reversible). `render_region` resolves instances (flip) + blit (PB-1) + `composite_stack` (CO-4), non-destructive. Zero Qt; no `document` import. | `Tilemap`, `TilemapLayer`, `TileInstance`, `FLIPPED_*_FLAG`, `ROTATED_HEXAGONAL_120_FLAG`, `GID_MASK`, `resolve`, `make_stamp/erase/fill_rect_command`, `make_add/remove/move_layer_command`, `make_set_layer_visibility_command`, `make_attach_tileset_command`, `render_region` (vectorised, pixel-space), `chunk_version`, `tiled_passthrough`, `TilemapError` | LOGIC-005, 006, 007, 008, 009, 012, 013, 014 |
| `document.py` | extend | Attach `tilesets`/`tilemaps` collections (`__slots__`, created empty) + reversible attach/detach commands. | `tilesets`, `tilemaps`, `make_add/remove_tileset_command`, `make_add/remove_tilemap_command` | LOGIC-012, DATA-004 (surface) |

## `pixelart_creator/logic/` — Phase-7 export & pipeline integration — BUILT (Slices 7A/7B)

> **Shipped modules:** `logic/export.py`, `logic/atlas.py` (both zero-Qt, verified by
> `check_layering` exit 0 / 40 modules), `logic/constants.py` extended with the 8 export numerics.
> Tests: `tests/logic/test_export.py` (53) + `tests/logic/test_atlas.py` (21). `MAX_ATLAS_DIMENSION`
> aligned to the buildable 8K ceiling (`= MAX_CANVAS_WIDTH = 7680`, per-axis clamp in `atlas.py`).


> New Qt-free `logic/export.py` + `logic/atlas.py` + additive `constants.py` extension, frozen by
> AGT-01 (`interface-contract`, plan §4/§5) BEFORE implementation so Slices 7C/7D/7E bind to a stable
> contract. Domain grounded by `docs/research-phase-7-export-20260704.md` (deterministic Pillow
> PNG/GIF options, Aseprite/TexturePacker JSON landscape, Unity/Godot artifacts, APNG feasibility,
> MaxRects rotation). **PL7-D3 (cycle-free):** new edges `export → atlas`, `export → blend`/`document`/
> `quantize`/`animation`, `atlas → compactor`; neither `export` nor `atlas` imports `document` back or
> imports Qt/`ui` — they are *consumers* of the shipped models (the `blend.py`/`animation.py`
> precedent); the Aseprite-JSON metadata builder lives in `export.py` so `atlas → export` never appears
> → acyclic, no `logic → data` edge. The atlas **delegates to `compactor.compact` (CP-1)** — packing is
> never re-implemented; CP-1 has rotation disabled, so every region is axis-aligned and `rotated` is a
> const `false`. New numerics → `constants.py` (`DEFAULT_SPRITE_SHEET_COLUMNS=8`, `DEFAULT_ATLAS_PADDING=0`,
> `MAX_ATLAS_DIMENSION=8192`, `MAX_BATCH_TARGETS=256`, `MAX_EXPORT_FRAMES=4096`, `PNG_EXPORT_COMPRESS_LEVEL=6`
> — DISTINCT from `PROJECT_ZLIB_LEVEL=9` — `GIF_DEFAULT_LOOP_COUNT=0`, `GIF_FRAME_DISPOSAL=2`). Pillow
> enum/format strings, wire-format version strings, and the `ExportFormat`/`EnginePreset` enums stay
> module-local (ADR-0001/BF-2). Canonical JSON schema in **ADR-0017**; engine presets in **ADR-0018**;
> encoder options + byte-repro scope + APNG deferral in **ADR-0019**; export architecture/layering/CLI
> in **ADR-0020**. New `ExportError`/`AtlasError(ValueError)`.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +8 export numerics (leaf); names distinct from every shipped constant. | `DEFAULT_SPRITE_SHEET_COLUMNS`, `DEFAULT_ATLAS_PADDING`, `MAX_ATLAS_DIMENSION`, `MAX_BATCH_TARGETS`, `MAX_EXPORT_FRAMES`, `PNG_EXPORT_COMPRESS_LEVEL`, `GIF_DEFAULT_LOOP_COUNT`, `GIF_FRAME_DISPOSAL` | LOGIC-012 |
| `export.py` | **new** | Export model + deterministic pipeline: flatten via `composite_stack` (CO-4, non-destructive); byte-reproducible PNG/GIF encode → bytes (Pillow, ADR-0019; GIF fixed shared palette via `quantize.median_cut`); deterministic row-major sprite-sheet; Aseprite-Array JSON metadata (ADR-0017); the shared `export_document` orchestrator + `run_batch`. Zero Qt. | `ExportFormat`, `EnginePreset`, `SpriteRect`, `SheetMetadata`, `ExportRequest`, `ExportResult`, `flatten_frame`, `encode_png`, `encode_gif`, `build_sprite_sheet`, `build_metadata_json`, `export_document`, `run_batch`, `ExportError` | LOGIC-001..005, 008, 009, 010, 011, 012 |
| `atlas.py` | **new** | Texture-atlas layout by **delegating to `compactor.compact` (CP-1)** — non-overlapping, within bounds, axis-aligned (rotation disabled); blit each sprite at its `Placement`; unfit → `AtlasError` wrapping `CompactionError`. Packing NOT re-implemented. Zero Qt; no `document` import. | `pack_atlas`, `AtlasResult`, `AtlasError` | LOGIC-006, 007 |

## `pixelart_creator/data/` — Phase-7 export I/O + headless CLI — BUILT (Slice 7C)

> **Shipped modules:** `data/export_io.py`, `data/export_cli.py` (both zero-Qt, verified by
> `check_layering` exit 0). `export_cli.py` confirmed under `data/` (NOT a new top-level `cli/`
> package — the `check_layering` blind-spot ADR-0020 warns of); imports downward only
> (`data → data`, `data → logic`; no `logic → data`, no Qt, no `ui`). Tests:
> `tests/data/test_export_io.py` (14) + `tests/data/test_export_cli.py` (15). CLI console_script
> `pixelart-export = pixelart_creator.data.export_cli:main` is AGT-09's `pyproject` edit (T7C-07).


> New Qt-free `data/export_io.py` (write exact engine bytes + JSON + engine-preset artifacts) +
> `data/export_cli.py` (headless CLI driver). **ADR-0020:** the CLI lives in `data/` — not a new `cli/`
> package — *specifically* because `check_layering.py` only enforces Qt-freedom on `logic/`/`data/`
> top-level dirs; a `cli/` sibling would be an unscanned Qt blind spot. `data/` may import `logic/` +
> `data/`, never `ui/`/Qt. Engine artifacts (Unity `.meta` 2022.3 / Godot `SpriteFrames.tres` 4.2) are
> built+serialised here over the `logic/`-computed layout (the Phase-6 `tiled_io.py` precedent);
> version strings module-local (ADR-0001). CLI input reuses `project_io.load_project` (IO-3 defensive).
> The `pyproject` `[project.scripts]` entry `pixelart-export = pixelart_creator.data.export_cli:main`
> is an **AGT-09** edit (Article IX). Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `export_io.py` | **new** | Write the **exact** engine bytes + JSON to portable paths (`pathlib`, `path_portability_check`) with NO re-encode (byte-reproducibility preserved); build + write Unity `.meta` (2022.3) + Godot `SpriteFrames.tres` (4.2) engine artifacts from the `logic/` layout (ADR-0018). | `write_export`, `write_engine_preset` | DATA-001, 002, 004 |
| `export_cli.py` | **new** | Headless Qt-free driver: `argparse` (`--input/--format/--preset/--output/--columns/--padding/--loop/--tag/--json`); load `.pixproj` via `project_io.load_project` (IO-3 → `ProjectIOError`); drive the SAME `logic/export`+`data/export_io` (CLI==GUI byte-identity); exit 0/1/2. | `main(argv) -> int` | DATA-003, LOGIC-013 |

## `pixelart_creator/ui/` — Phase-7 export & pipeline integration — BUILT (Slices 7D/7E)

> **Shipped modules:** `ui/export_dialog.py`, `ui/batch_export_panel.py`, `ui/export_worker.py`
> (`Export_Worker`/`Export_Controller` — the only new Qt importers, off-thread runner), and
> `ui/export_actions.py`; `ui/main_window.py` extended with the Export menu + a window-owned
> `Export_Controller`. Deterministic teardown chain: `Export_Controller.shutdown()` ←
> `MainWindow.shutdown_prewarm()` ← `closeEvent()` (no segfault under `-n auto`, QA-proven).
> **No `ui/commands.py` change** — export is non-destructive (0 export refs, verified). Tests: the
> 8 `tests/ui/test_export_*.py` modules (76, both themes).


> Binds to Slice-7A/7B/7C logic+data; Qt lives here only. The export dialog / options / engine-preset
> selector / batch panel / export actions / off-GUI-thread export worker are `ui/`. Export is
> **read-only / non-destructive** — it pushes NO `QUndoCommand` and adds NOTHING to `ui/commands.py`
> (ADR-0020, CL-12). The GUI adds no encode/layout logic — it calls the identical `logic/`+`data/`
> functions the CLI calls (REQ-P7-UI-007, byte-identity). Responsiveness (REQ-P7-UI-010, DEP-3): the
> `Export_Worker` runs the Qt-free engine on a window-owned `QThreadPool` with progress/cancel over
> queued GUI-thread signals (no Qt off-thread; Phase-5/6 warmer precedent) — NOT the 16 ms canvas
> budget (export is batch IO). AGT-10 owns any responsiveness directive; AGT-05 implements. Both themes,
> a11y, `tr()`-wrapped strings (AGT-06/AGT-07).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `export_dialog.py` | **new** | `Export_Dialog(QDialog)`: format picker + per-format options (GIF frame-source/loop; sheet columns/rows/padding; atlas padding/max-dim + JSON toggle; defaults from constants, reject OOR); engine-preset selector; portable destination chooser; `tr()` + `changeEvent`. | `export`, `data/export_io`, `constants` | UI-001..004, 006, 008, 012, 013 |
| `batch_export_panel.py` | **new** | `Batch_Export_Panel(QWidget)`: multi-target/format one-action export via `export.run_batch` on the worker; per-target progress; per-target failure isolated. | `export.run_batch`, `export_worker` | UI-005, 010, 013 |
| `export_worker.py` | **new** | `Export_Worker(QRunnable)` + signals: run the Qt-free `logic/export`+`data/export_io` off the GUI thread; progress/result/error over queued signals; cooperative cancel; no Qt off-thread (DEP-3). | `export`, `data/export_io` | UI-010 |
| `export_actions.py` | **new** | Export menu/toolbar actions; surface `ExportError`/`AtlasError`/`ProjectIOError`/unwritable-path as user-facing errors (no crash, no partial file left as valid). `tr()` strings. | `export_dialog`, `batch_export_panel` | UI-001, 007, 008, 013 |
| `main_window.py` | extend | Add the Export menu + actions; hold active document + parameters (view state); wire dialog/batch panel/worker. **No `ui/commands.py` change** (export non-destructive). | `document`, the new export UI | UI-001, 005, 009 |

## `pixelart_creator/logic/` — Phase-8 automation & extensibility — BUILT (Slices 8A/8B/8C)

> New Qt-free `logic/scripting.py` + `logic/macro.py` + `logic/plugins.py` + `logic/procgen.py` +
> `logic/batch_ops.py` + additive `constants.py` extension, frozen by AGT-01 (`interface-contract`,
> plan §5) BEFORE implementation so Slices 8D/8E bind to a stable contract. **Security is central
> (Article VII):** the scripting surface is a **data-driven command DSL** replayed by a **trusted
> dispatcher** over the shipped `history` reversible commands — **ZERO `eval`/`exec`** on any path
> (the engine executes data, not a language; ADR-0021). Plugins are **trusted-with-consent,
> default-deny, no-auto-run** and may only register/invoke DSL commands (ADR-0021). Domain grounded by
> `docs/research-phase-8-automation-20260704.md` (pysandbox/RestrictedPython settled-unsafe; Option A
> DSL; `importlib.metadata` discovery; OpenSimplex procgen). **PL8-D3 (cycle-free):** `plugins →
> scripting` is the ONLY inbound edge to `scripting` (the command registry lives in `scripting`);
> `scripting` never imports `plugins`; `macro` never imports `scripting` (the dispatcher imports
> `macro`); none imports `document` back or Qt/`ui` → acyclic, no `logic → data` edge. Batch recolour
> **composes `palette_ops` (PS-1)** — recolour maths not re-implemented (Article I). New numerics →
> `constants.py` (`MAX_MACRO_STEPS=4096`, `MAX_SCRIPT_OPS=100000`, `MAX_PLUGINS_LOADED=64`,
> `MAX_BATCH_RECOLOUR_TARGETS=256` — DISTINCT from Phase-7 `MAX_BATCH_TARGETS=256` —
> `MAX_PROCGEN_DIMENSION=7680`, `DEFAULT_PROCGEN_SEED=0`). DSL op-name vocabulary, macro
> `schema_version` string, and the plugin `Capability` enum stay module-local (ADR-0001/BF-2). Security
> model in **ADR-0021**; macro format / plugin discovery / CLI placement / procgen-batch scope /
> layering in **ADR-0022**. New `ScriptError`/`MacroError`/`PluginError`/`ProcgenError`/`BatchError(ValueError)`.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +6 automation numerics (leaf); names distinct from every shipped constant. | `MAX_MACRO_STEPS`, `MAX_SCRIPT_OPS`, `MAX_PLUGINS_LOADED`, `MAX_BATCH_RECOLOUR_TARGETS`, `MAX_PROCGEN_DIMENSION`, `DEFAULT_PROCGEN_SEED` | LOGIC-013 |
| `scripting.py` | **new** | Command registry (op-name → trusted `history.Command` factory + param schema) + trusted dispatcher (validate + construct + push; one grouped undoable `Command`; `MAX_SCRIPT_OPS`); scripting API. **No `eval`/`exec`.** Zero Qt. | `Op`, `register_command`, `dispatch`, `ScriptError` | LOGIC-001, 002, 003, 013 |
| `macro.py` | **new** | Macro model: `record` an ordered `{op, params, seed}` list (resolved inputs + stable ids + seed, not a pixel diff; `MAX_MACRO_STEPS`); `replay` deterministically via the dispatcher → one grouped undoable `Command`. No `scripting` import (no back-edge). Zero Qt. | `Macro`, `record`, `replay`, `MacroError` | LOGIC-004, 005, 006 |
| `plugins.py` | **new** | Plugin host: `entry_points` discovery (inert); defensive manifest validation; module-local `Capability` vocabulary; capability object exposing only the DSL API; **deny-by-default**; `MAX_PLUGINS_LOADED`. Imports `scripting` one-way. Zero Qt. | `Capability`, `PluginManifest`, `discover`, `enable`, `PluginError` | LOGIC-008, 009, 010, 013 |
| `procgen.py` | **new** | Seeded generators — OpenSimplex + value/gradient noise + cellular automata + dithered gradients (reuse `dither`); deterministic `(params, seed)`; write via reversible command over `PixelBuffer` (PB-1), composite via CO-4; `MAX_PROCGEN_DIMENSION` per-axis clamp. Zero Qt. | `make_procgen_command`, `ProcgenError` | LOGIC-012, 013 |
| `batch_ops.py` | **new** | Batch recolour: compose `palette_ops` (PS-1) across many targets as ONE transactional reversible command; each output == single op; per-target failure isolated; `MAX_BATCH_RECOLOUR_TARGETS`. Zero Qt. | `make_batch_recolour_command`, `BatchError` | LOGIC-011, 013 |

## `pixelart_creator/data/` — Phase-8 automation persistence + headless CLI — BUILT (Slices 8B/8D)

> New Qt-free `data/macro_io.py` (defensive `eval`-free (de)serialise of macros/plugin manifests/script
> inputs, IO-3) + `data/automation_cli.py` (headless CLI driver). **ADR-0022:** the CLI lives in
> `data/` — not a new `cli/` package — *specifically* because `check_layering.py` only enforces
> Qt-freedom on `logic/`/`data/` top-level dirs; a `cli/` sibling is an unscanned Qt blind spot (the
> Phase-7 `export_cli` lesson). `data/` may import `logic/` + `data/`, never `ui/`/Qt. **DEP-4 ratified:**
> the macro/plugin/script serialiser stays folded under REQ-P8-LOGIC-007 — **no `REQ-P8-DATA-*` prefix
> allocated** (not acceptance-changing; ADR-0022 §4). CLI input reuses `project_io.load_project` (IO-3
> defensive). The `pyproject` `[project.scripts]` entry `pixelart-run =
> pixelart_creator.data.automation_cli:main` is an **AGT-09** edit (Article IX). Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `macro_io.py` | **new** | Defensive `eval`-free (de)serialise a `.pixmacro` (DSL list + versions + seeds) + plugin manifests + script inputs via IO-3 (type/bounds-check; malformed/unknown-version → `MacroIOError`; never `eval`/`exec`; portable paths); round-trip-identical. | `save_macro`, `load_macro`, `load_manifest`, `MacroIOError` | LOGIC-007 (folded) |
| `automation_cli.py` | **new** | Headless Qt-free driver: `argparse` (`--input/--macro/--output/--seed/--param`); load `.pixproj` via `project_io.load_project` (IO-3 → `ProjectIOError`) + `macro_io.load_macro`; replay via the SAME `logic/scripting` dispatcher (CLI==GUI state-identity); write OUT; exit 0/1/2. | `main(argv) -> int` | LOGIC-014 |

## `pixelart_creator/ui/` — Phase-8 automation & extensibility — BUILT (Slice 8E)

> Binds to Slice-8A/8B/8C/8D logic+data; Qt lives here only. The macro controls / script runner /
> plugin manager / batch-recolour + procgen panels / off-GUI-thread automation worker are `ui/`; the
> sole Qt undo-bridge stays `ui/commands.py` — one grouped `QUndoCommand` per automation **edit**
> (script/macro/batch/procgen), while **recording, plugin-enable/disable, and selection are
> view/session state and push no command** (CL-8, REQ-P8-UI-009). The GUI adds no engine logic — it
> replays the identical DSL through the identical `logic/scripting` dispatcher the CLI drives
> (REQ-P8-UI-010, state-identity). Responsiveness (REQ-P8-UI-011, DEP-3): `Automation_Worker` runs the
> Qt-free engine on a window-owned `QThreadPool` with progress/cancel over queued GUI-thread signals
> (no Qt off-thread; Phase-5/6/7 warmer precedent) — NOT the 16 ms canvas budget (automation is batch
> work). AGT-10 owns any responsiveness directive; AGT-05 implements. The plugin manager **shows a
> plugin's declared permissions before enable** (REQ-P8-UI-005, informed grant). Both themes, a11y,
> `tr()`-wrapped strings (AGT-06/AGT-07).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `macro_controls.py` | **new** | `Macro_Controls(QWidget)`: start/stop record (view state); run/replay (one undoable grouped command); save/load/list via `data/macro_io` (malformed → graceful error); `tr()` + `changeEvent`. | `macro`, `data/macro_io`, `ui/commands` | UI-001, 002, 003 |
| `script_runner_panel.py` | **new** | `Script_Runner_Panel(QWidget)`: run a DSL script over `scripting` on the worker; edits undoable; failing script → graceful error. | `scripting`, `automation_worker`, `ui/commands` | UI-004 |
| `plugin_manager_panel.py` | **new** | `Plugin_Manager_Panel(QWidget)`: install/enable/disable/list; **permissions shown before enable**; sandboxed run; denied/failed → user-facing error. Enable/disable = view state. | `plugins`, `data/macro_io` | UI-005, 008 |
| `batch_recolour_panel.py` | **new** | `Batch_Recolour_Panel(QWidget)`: recolour a target set as ONE undoable action via `batch_ops` on the worker; per-target progress/failure isolation. | `batch_ops`, `automation_worker`, `ui/commands` | UI-006 |
| `procgen_panel.py` | **new** | `Procgen_Panel(QWidget)`: parameters + seed; generate via `procgen` (one undoable command); same seed → same output; reject OOR sizes; `tr()` + units + `changeEvent`. | `procgen`, `ui/commands` | UI-007 |
| `automation_worker.py` | **new** | `Automation_Worker(QRunnable)` + signals on a window-owned `QThreadPool`: run the Qt-free engine off the GUI thread; progress/result/error over queued signals; cooperative cancel; no Qt off-thread (DEP-3). | `scripting`, `macro`, `batch_ops`, `procgen` | UI-011 |
| `commands.py` | extend | One grouped `QUndoCommand` per automation edit delegating to the returned `history.Command`(s); recording/enable/selection push none. No domain math. | `history` + 8A–8D ops | UI-009 |
| `main_window.py` | extend | Add the Automation menu + dock the panels; hold active document + parameters (view state); wire the worker. | `document`, the new automation UI | UI-001, 005, 009 |

## `pixelart_creator/logic/` — Phase-9 visual aids & UX — PLANNED (Slices 9A/9B/9C)

> New Qt-free `logic/grids.py` + `logic/guides.py` + `logic/preview.py` + `logic/timelapse.py` +
> additive `constants.py`/`document.py` extensions, frozen by AGT-01 (`interface-contract`, plan §5)
> BEFORE implementation so Slices 9E–9H bind to a stable contract. **Tested geometry is central
> (Article I + P2):** the entire snap/transform/scale/timelapse-model engine is **pure, deterministic,
> zero-Qt, unit-testable** — the SAME function the overlays call is the one AGT-04 property-tests (the
> ROADMAP "compute snap points from tested geometry logic"; the 10 `[GEO]` scenarios). Documented
> deterministic tie-breaks: round-half-up (iso vertex), lowest-VP-index (perspective), lowest-position
> (guides). Domain grounded by `docs/research-phase-9-visual-aids-20260704.md` (2:1-dimetric iso;
> direction-lock perspective; doc-coord guides + screen-px÷zoom tolerance; real-size = screen_DPI/doc_PPI
> with Qt applying DPR). **PL9-D3 (cycle-free):** `grids`/`guides`/`preview` are pure leaves over
> `constants`; `timelapse` imports downward (`document`/`blend`/`history`); none imports Qt/`ui` or `data`
> → acyclic. New numerics → `constants.py` (`DEFAULT_ISO_GRID_RATIO=2.0`, `DEFAULT_SNAP_TOLERANCE_PX=8`,
> `MIN_GRID_SPACING=2`, `MAX_GRID_SPACING=1024`, `MAX_GUIDES=256`, `MAX_PERSPECTIVE_VANISHING_POINTS=3`,
> `MAX_REFERENCE_IMAGES=256`, `MAX_TIMELAPSE_FRAMES=4096`, `MAX_DOCUMENT_VIEWS=8`, `DEFAULT_DOCUMENT_PPI=72.0`).
> `GuideOrientation` + the timelapse `schema_version` string stay module-local (ADR-0001/BF-2). Geometry
> model in **ADR-0023**; architecture/multi-view/timelapse/reference-board/DATA-prefix/layering in
> **ADR-0024**; `.pixproj` v5 + PPI + persistence formats in **ADR-0025**. New `GridError`/`GuideError`/
> `PreviewError`/`TimelapseError(ValueError)`. Phase 9 adds **no** `ui/commands.py` logic (aids
> non-destructive).

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `constants.py` | extend | +10 visual-aids numerics (leaf); names distinct from every shipped constant. | `DEFAULT_ISO_GRID_RATIO`, `DEFAULT_SNAP_TOLERANCE_PX`, `MIN_GRID_SPACING`, `MAX_GRID_SPACING`, `MAX_GUIDES`, `MAX_PERSPECTIVE_VANISHING_POINTS`, `MAX_REFERENCE_IMAGES`, `MAX_TIMELAPSE_FRAMES`, `MAX_DOCUMENT_VIEWS`, `DEFAULT_DOCUMENT_PPI` | LOGIC-011 |
| `grids.py` | **new** | Isometric 2:1-dimetric diamond transform (invertible) + snap-to-nearest-vertex; perspective guide-line construction + direction-lock snap-to-nearest-VP within tolerance (1-/2-/3-point). Clamps spacing; `MAX_PERSPECTIVE_VANISHING_POINTS`. Deterministic tie-breaks. **Zero Qt.** | `IsoGridConfig`, `iso_world_to_screen`, `iso_screen_to_world`, `iso_snap_vertex`, `VanishingPoint`, `PerspectiveConfig`, `GuideLine`, `perspective_guide_lines`, `perspective_snap`, `GridError` | LOGIC-001, 002, 003, 004, 008, 009, 011 |
| `guides.py` | **new** | Doc-coord guide snap (per-axis, within `screen-px÷zoom` tolerance) + nice-number `{1,2,5}·10ⁿ` ruler ticks + coordinate readout (locale-independent). `GuideOrientation` module-local; `MAX_GUIDES`. **Zero Qt.** | `GuideOrientation`, `Guide`, `screen_tolerance_to_doc`, `snap_guides`, `RulerTick`, `ruler_ticks`, `coordinate_readout`, `GuideError` | LOGIC-005, 006, 008, 009, 011 |
| `preview.py` | **new** | `real_size_scale(doc_ppi, screen_dpi)=screen_dpi/doc_ppi` — pure, deterministic; **no DPR math** (Qt applies it). **Zero Qt.** | `real_size_scale`, `PreviewError` | LOGIC-007, 008, 009 |
| `timelapse.py` | **new** | Reproducible per-committed-command session model (`{index, command_id}` manifest, not inline pixels) + deterministic `replay` re-rendering each state via `composite_stack` (CO-4) over the HIS-1 history; `MAX_TIMELAPSE_FRAMES`; `schema_version` module-local. **Zero Qt.** | `TimelapseFrame`, `TimelapseSession`, `record_frame`, `replay`, `TimelapseError` | LOGIC-008, 009, 010, 011 |
| `document.py` | extend | Add first-class `ppi: float` field (default `DEFAULT_DOCUMENT_PPI`, validated) for real-size scale (BF-3); no other change. | `Document.ppi` | LOGIC-007, 012 |

## `pixelart_creator/data/` — Phase-9 visual-aids persistence + `.pixproj` v5 — PLANNED (Slice 9E)

> New Qt-free `data/timelapse_io.py` + `data/reference_board_io.py` (defensive `eval`-free IO-3
> serialisers) + a `.pixproj` **v5** extension of `data/project_io.py` (persist `Document.ppi`). **DEP-4
> RATIFIED — `REQ-P9-DATA-*` prefix ALLOCATED** (unlike Phase 8's folded single serialiser): two distinct
> serialisers/formats → **REQ-P9-DATA-001** (timelapse session) + **REQ-P9-DATA-002** (reference board),
> each formalising a persistence contract already fixed under REQ-P9-LOGIC-010 / REQ-P9-UI-006 (not
> acceptance-changing; ADR-0024 §4). `TimelapseIOError`/`ReferenceBoardIOError` subclass `ProjectIOError`
> (IO-3). The `.pixproj` v5 PPI persistence is a schema extension of the **shipped** `project_io` grounded
> by REQ-P9-LOGIC-007 (v1–v4 load unchanged → `DEFAULT_DOCUMENT_PPI`) — **not** a DATA REQ (ADR-0025 §1).
> `data/` may import `logic/`+`data/`, never `ui/`/Qt. Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `timelapse_io.py` | **new** | Defensive `eval`-free (de)serialise a `.pixtimelapse` manifest (`schema_version` + `{index, command_id}`, not inline pixels) via IO-3 (type/bounds-check; malformed/unknown-version → `TimelapseIOError`; never `eval`/`exec`; portable paths); round-trip → identical replay. | `save_session`, `load_session`, `TimelapseIOError` | DATA-001 |
| `reference_board_io.py` | **new** | Defensive `eval`-free (de)serialise a `.pixboard` layout (`schema_version` + pan/zoom + `{image path-or-embedded, transform, crop, z_order}` ≤ `MAX_REFERENCE_IMAGES`) via IO-3 (malformed → `ReferenceBoardIOError` user-facing; never `eval`/`exec`); non-destructive round-trip. Pure `data/` dataclasses (no Qt). | `ReferenceImageEntry`, `ReferenceBoardLayout`, `save_board`, `load_board`, `ReferenceBoardIOError` | DATA-002 |
| `project_io.py` | extend | `.pixproj` **v5**: persist `Document.ppi`; v1–v4 load unchanged (absent → `DEFAULT_DOCUMENT_PPI`); out-of-range → `ProjectIOError`; `_SUPPORTED_VERSIONS` += 5. | `save_project`/`load_project` (v5) | LOGIC-007 |

## `pixelart_creator/ui/` — Phase-9 visual aids & UX — PLANNED (Slices 9F/9G/9H)

> Binds to Slice-9A/9B/9C/9E logic+data; Qt lives here only. The real-size preview window / guides-rulers
> overlay / iso + perspective grid overlays / reference board / multi-view viewports / timelapse controls
> are `ui/`; they **render + call the pure `logic/` geometry** and re-implement **none** of it (Article I).
> **Phase 9 adds NO `ui/commands.py` logic** — visual aids are non-destructive (REQ-P9-UI-010): enabling a
> grid, creating a guide, adding a reference, opening a view, or starting recording pushes **no**
> `QUndoCommand`; only the shipped HIS-1 drawing edits are undoable. **Multi-view** = N `QGraphicsView`s on
> the **one shared** document scene (`scene.changed` auto-repaints all — research §5), builds on MC-4,
> distinct from Phase-4 isolated multi-canvas tabs. **Real-size DPI (HIGHEST-RISK, research §4.2):** the Qt
> DPI query (`QScreen.physicalDotsPerInch()`) + manual on-screen-ruler calibration live in the preview
> window; **DPR is applied by Qt — the window must NOT multiply it** (device-independent coords), recompute
> on `screenChanged`. **Performance (REQ-P9-UI-011, DEP-3): the 16 ms `FRAME_BUDGET_MS` APPLIES** (overlays
> + views are on the per-frame render loop, unlike Phase-7/8 batch work) — cache-backed overlays
> (`DeviceCoordinateCache`), `MinimalViewportUpdate`, tile-cull + dirty-rect per view; AGT-10 owns the
> strategy, AGT-05 implements; budget never relaxed. Both themes (role-based overlay/guide colours legible
> over artwork), a11y, `tr()`-wrapped strings (AGT-06/AGT-07).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `real_size_preview_window.py` | **new** | `Real_Size_Preview_Window(QWidget)`: render composited doc (CO-4) at `preview.real_size_scale` (no scaling math of its own); mirror edits live (shared doc, read-only); Qt DPI query + manual calibration here; recompute on `screenChanged`; **no DPR mult**. `tr()` + `changeEvent`. | `preview`, `blend`, `document` | UI-001, 002 |
| `guides_rulers_overlay.py` | **new** | `Guides_Rulers_Overlay`: create/move/remove guides; rulers show `coordinate_readout`+`ruler_ticks`; cursor snaps via `guides.snap_guides` (no snap math itself). Role-based colours; `tr()`. | `guides` | UI-003 |
| `iso_grid_overlay.py` | **new** | `Iso_Grid_Overlay`: render iso grid from `grids.iso_world_to_screen`; snap to nearest vertex via `grids.iso_snap_vertex`; `DeviceCoordinateCache`. `tr()`. | `grids` | UI-004 |
| `perspective_grid_overlay.py` | **new** | `Perspective_Grid_Overlay`: render guide lines from `grids.perspective_guide_lines`; snap to nearest guide within tolerance via `grids.perspective_snap`; configurable VPs (≤3); `DeviceCoordinateCache`. `tr()`. | `grids` | UI-005 |
| `reference_board.py` | **new** | `Reference_Board(QWidget)` over a **separate** `QGraphicsScene` of `QGraphicsPixmapItem`s: add/arrange/zoom/crop references; **non-destructive**; persist via `data/reference_board_io` (malformed → user-facing error); `MAX_REFERENCE_IMAGES`. `tr()` + `changeEvent`. | `data/reference_board_io` | UI-006 |
| `multi_view.py` | **new** | `Multi_View`: open extra `QGraphicsView`(s) on the **shared** document scene (≤`MAX_DOCUMENT_VIEWS`); per-view independent zoom/pan; `scene.changed` auto-syncs all views + preview. Builds on MC-4. `tr()`. | `document` (shared scene) | UI-007, 008 |
| `timelapse_controls.py` | **new** | `Timelapse_Controls(QWidget)`: start/stop recording (view/session state, no undo); record one frame per committed command via `timelapse.record_frame`; save/load session via `data/timelapse_io`; failed record → user-facing error. `tr()` + units + `changeEvent`. | `timelapse`, `data/timelapse_io` | UI-009 |
| `main_window.py` | extend | Add the View-Aids menu + dock/toggle the overlays, preview, reference board, extra views, timelapse controls; hold each view's local zoom/pan + aid config (view state). **No `ui/commands.py` change** (aids non-destructive). | `document`, the new visual-aids UI | UI-001, 003, 010 |

## `pixelart_creator/data/` — Phase-6 Tiled JSON I/O + `.pixproj` v4 — BUILT (Slice 6D)

> New Qt-free `data/tiled_io.py` (Tiled 1.12.2 JSON export/import) + `data/project_io.py` v4 extension.
> Tiled encoding set (CSV-default emit + base64/gzip/zlib; zstd + external `.tsx` rejected; full 4-bit
> GID flag handling incl. diagonal-clear + transform diagonal→H→V; embedded emit + external `.tsj`
> import; unknown-field verbatim passthrough) ruled in **ADR-0014**. `.pixproj` **v4** (tilesets +
> tilemaps on `Document`; v1/v2/v3 back-compat empty collections) ruled in **ADR-0016**;
> `FORMAT_VERSION=4` (`_SUPPORTED_VERSIONS=(1,2,3,4)`, format-intrinsic local — ADR-0001). Defensive
> validated load (Article VII); reuses the `project_io.py` posture (IO-3). `tiled_io` imports the GID
> masks from `logic/tilemap` (downward `data → logic`). Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `tiled_io.py` | **new** | Tiled JSON map export (embedded tilesets + firstgid; CSV/base64+gzip/zlib; chunks[] infinite / dense data fixed; version/tiledversion/orientation/renderorder/counters) + defensive import (base64→decompress→LE uint32; clear 0x20000000; transform diagonal→H→V; validate geometry/gid-range/payload/orientation → `ProjectIOError`; zstd/`.tsx` rejected; unknown fields verbatim → lossless round-trip). Portable paths. | `export_tilemap`, `write_tiled_json`, `import_tilemap`, `read_tiled_json` (raises `ProjectIOError`) | DATA-001, 002, 003 |
| `project_io.py` | extend | Serialise `tilesets` + `tilemaps` (logical auto-tile placement, not baked frames); schema v4; defensive load + v1/v2/v3 back-compat read (empty collections). Frames/tags/layers (v3) reused. | `serialize`, `deserialize`, `save_project`, `load_project`, `FORMAT_VERSION=4`, `ProjectIOError` | DATA-004 |

## `pixelart_creator/ui/` — Phase-6 tilemap & level design — BUILT (Slices 6E/6F/6G)

> Binds to Slice-6A/6B/6C/6D logic+data; Qt lives here only. The tileset editor / tilemap canvas /
> stamping tools / layer panel / auto-tile toggle / import-export actions are `ui/`; the sole Qt
> undo-bridge stays `ui/commands.py` (one `QUndoCommand` per tileset/tilemap op). The 8K tilemap
> canvas implements the AGT-10 viewport tile-culling + dirty-rect directive (DEP-3, plan §7): a
> per-chunk `QPixmap` cache (`tilemap_chunk_cache.py`, bounded LRU keyed by `(cx, cy)` + `chunk_version`)
> plus an off-GUI-thread cold-warm worker on a scene-owned `QThreadPool` that calls the Qt-free
> `render_region` off-thread and hands the `PixelBuffer` back over a queued GUI-thread signal (no
> cross-thread QPixmap; Qt stays in `ui/`). Deterministic teardown chain
> `Tilemap_Canvas.shutdown_warm → MainWindow.shutdown_prewarm → closeEvent` (mirrors the Phase-5
> `CanvasScene.shutdown_prewarm` fix; QA proved no segfault under `-n auto`). Resident tile/pixel data
> never culled — only derived pixmaps (Article VI §3). Perf loop-back CLOSED ≤16 ms; UI QA SHIP-READY
> after S2+S3 fixes. Both themes, a11y, tr()-wrapped strings (AGT-06/AGT-07).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `tileset_editor_panel.py` | **new** | `Tileset_Editor_Panel(QWidget)`: sliced-tile grid display + active-tile select (view state); slicing spin-boxes (defaults from `DEFAULT_TILE_*`, reject out-of-range) → reslice command; paint into a source tile → one command (instances update live); `tr()` + `changeEvent`. | `tileset`, `ui/commands` | UI-001, 002, 003, 013, 015..017 |
| `tilemap_canvas.py` | **new** | `Tilemap_Canvas(QGraphicsView/Scene)`: composited stack render via `tilemap.render_region`; pan/zoom unbounded (view state); stamp/eraser/rectangle-fill (one command each); auto-tile on stamp; viewport tile-culling + per-chunk pixmap cache + off-thread cold-warm; deterministic `shutdown_warm` teardown. | `tilemap`, `autotile`, `tilemap_chunk_cache`, `ui/commands` | UI-004..007, 009, 010, 013, 014, 016 |
| `tilemap_chunk_cache.py` | **new** | `ChunkPixmapCache` (bounded LRU of one `QPixmap` per `TILEMAP_CHUNK_SIZE` chunk, keyed by `(cx, cy)` + validated by `Tilemap.chunk_version`) + `TilemapChunkWarmSignals`/`TilemapChunkWarmRunnable` (off-GUI-thread cold-warm on a scene-owned `QThreadPool` calling the Qt-free `render_region`; result returned via queued signal; only derived pixmaps culled, never resident pixels — Article VI §3). | `tilemap.render_region`, `tilemap.chunk_version` | UI-014 |
| `tiled_mode.py` | **new** | Qt-free tilemap-view mode helper (no Qt import). | `tilemap` | UI-004 |
| `tilemap_layer_panel.py` | **new** | `Tilemap_Layer_Panel(QWidget)`: add/remove/reorder/visibility (one command each); active-layer select (view state); auto-tile toggle. | `tilemap` layer ops, `ui/commands` | UI-008, 009, 013, 015..017 |
| `tilemap_io_actions.py` | **new** | Export active tilemap → Tiled JSON (portable path); import Tiled JSON → equivalent tilemap; malformed → user-facing error. | `data/tiled_io` | UI-011, 012, 015..017 |
| `main_window.py` | extend | Active tileset/tile/tilemap/layer (view state); dock the editor/canvas/layer panel; wire import/export; attach tilesets/tilemaps to the document. | `document` collections, new panels | UI-001, 004, 008, 011, 012 |
| `commands.py` | extend | One `QUndoCommand` per tileset/tilemap op, delegating to the returned `history.Command`; no domain math. | `history` + 6A/6B/6C ops | UI-013 |

## `pixelart_creator/data/` — Phase-5 `.pixproj` v3 — BUILT (Slice 5B)

> `data/project_io.py` extended to persist `frame_tags` (native `PlaybackMode` value strings) +
> per-node `layer_id`. Schema-v3 decision + v1/v2 back-compat read + native-mode (not Aseprite
> `direction`) ruled in **ADR-0012**; `FORMAT_VERSION` bumped to **3** (`_SUPPORTED_VERSIONS=(1,2,3)`;
> the bump itself is format-intrinsic, stays local — ADR-0001). Defensive validated tag load
> (Article VII); v1/v2 (tagless) load with an empty collection + minted `layer_id`s. Frames +
> `duration_ms` reused (v2 path unchanged). Imports `logic/animation` (`FrameTag`, `PlaybackMode`).
> Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `project_io.py` | extend | Serialise `frame_tags` + `layer_id`; schema v3; defensive tag load + v1/v2 back-compat read. | `serialize`, `deserialize`, `save_project`, `load_project`, `FORMAT_VERSION=3`, `ProjectIOError` | DATA-001, 002, 003 |

## `pixelart_creator/ui/` — Phase-5 animation — BUILT (Slice 5C)

> Binds to Slice-5A/5B logic; Qt lives here only. The `QTimer` (playback clock, CL-14) and all
> timeline/onion/tag widgets are `ui/`; the sole Qt undo-bridge stays `ui/commands.py` (one
> `QUndoCommand` per frame/tag op). Onion overlay drawn behind the active frame (BF-1: separate
> tinted pixmap items vs pre-blend is an AGT-05 HOW). Per-frame composite cache + **off-thread
> pre-warm** (playback perf loop-back D1/D2/D3, ADR-0011 §Perf): `frame_cache.py` (LRU of composited
> frames, Qt-free), `composite_warmer.py` (`QRunnable` that calls the Qt-free `blend.composite_stack`
> off the GUI thread — no Qt crosses into `logic/`), `prewarm_indicator.py` (progress widget); onion
> suppressed during playback (CL-11). D4 further budget-tuning deferred to Phase 12 (FU-P5-PERF).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `timeline_panel.py` | **new** | `Timeline_Panel(QWidget)`: frames×layer-track grid + thumbnails; select + drag-scrub (no undo); add/remove/reorder/duplicate + per-frame duration (one command each); tag spans. | `document` frame ops, `animation`, `ui/commands`, `frame_cache` | UI-001..007, 013, 015, 017..019 |
| `playback_controls.py` | **new** | `Playback_Controls(QWidget)`: play/pause/stop + mode selector (4 tr-labels, default LOOP); owns `QTimer`; advances via `animation.playback_steps` honouring `duration_ms`; named-animation "play tag"; streams cold frames via the pre-warm worker. | `animation`, active document, `composite_warmer` | UI-008, 009, 010, 014, 017..019 |
| `onion_skin_controls.py` | **new** | `Onion_Skin_Controls(QWidget)`: toggle + prev/next count + tint (view settings, no undo). | `animation.onion_overlay`, `constants` | UI-011, 012, 017..019 |
| `frame_tags_panel.py` | **new** | Create/edit/delete tag over a range + per-tag mode/repeat/colour (one command each); select-and-play. | `document` tag ops, `animation`, `ui/commands` | UI-013, 014, 015, 017..019 |
| `frame_cache.py` | **new** | `FrameCache`: bounded LRU (`OrderedDict`) of composited per-frame `PixelBuffer`s keyed by frame; invalidate on edit. **Zero Qt** (imports only `logic/pixel_buffer`). | `logic/pixel_buffer` | UI-016 |
| `composite_warmer.py` | **new** | `FrameCompositeWarmRunnable(QRunnable)` + warmer/`Signal`: flattens a frame's layer stack **off the GUI thread** by calling the Qt-free `blend.composite_stack`, emitting the resident `PixelBuffer` back to the GUI thread — no Qt leaks into `logic/`. | `logic/blend.composite_stack`, `frame_cache` | UI-016 |
| `prewarm_indicator.py` | **new** | Pre-warm progress widget (`Signal`, `changeEvent` retranslate); shows cold-range warming state during scrub/playback. | — (pure Qt widget) | UI-016, 019 |
| `canvas_scene.py` | extend | Render active/scrubbed/playing frame composite (cache hit or async warm); draw onion overlay behind active frame when toggled; suppress onion during playback. | `blend.composite_stack`, `animation.onion_overlay`, `frame_cache`, `composite_warmer` | UI-002, 011 |
| `main_window.py` | extend | Active frame index; dock timeline/playback/onion/tag UI; own per-frame composite cache + invalidation + pre-warm wiring. | `document`, tabs, new panels, `frame_cache` | UI-001, 002, 008, 016 |
| `commands.py` | extend | One `QUndoCommand` per frame/tag op; no domain math. | `history` + 5A frame/tag ops | UI-015 |

## `pixelart_creator/data/` — I/O & persistence (zero Qt) — SHIPPED

| Module | Responsibility | Key public surface |
| --- | --- | --- |
| `project_io.py` | Validated `.pixproj` (JSON) serialise/deserialise/save/load. | `serialize`, `deserialize`, `save_project`, `load_project`, `ProjectIOError` |

## `pixelart_creator/data/` — Phase-3 — PLANNED (Slice 3A)

| Module | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- |
| `favourites_io.py` | App-level JSON persistence of `Favourites` (ADR-0004); mirrors `project_io.py`; path supplied by UI (`QStandardPaths`), so `data/` stays Qt-free. | `save_favourites(path, favourites)`, `load_favourites(path)`, `FavouritesIOError` | LOGIC-015 (persistence), UI-004 |

## `pixelart_creator/data/` — Phase-4 `.pixproj` v2 — BUILT (Slice 4B)

> `data/project_io.py` extended to persist the richer layer model. Schema-v2 decision + v1
> back-compat read ruled in **ADR-0006**; `FORMAT_VERSION` bumped to **2** (the version bump itself is
> format-intrinsic, stays local — ADR-0001); defensive validated load (Article VII) that also
> **reads legacy v1 files** (flat layers → `NORMAL`, no groups/masks). AGT-01 allocates the DATA IDs
> (plan §7). Zero Qt.

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `project_io.py` | extend | Serialise per-node blend_mode/opacity/visible/lock + nested groups + masks + reference/smart links; schema v2; defensive load + v1 back-compat read. | `serialize`, `deserialize`, `save_project`, `load_project`, `FORMAT_VERSION=2`, `ProjectIOError` | DATA-001..005 |

## `pixelart_creator/data/` — Phase-7 drag-drop import — BUILT (Slice A-A)

> New Qt-free `data/` modules for REQ-NEW-A drag-drop import, on disk and green (`check_layering`
> + `check_cycles` clean). The palette **parser** is **REUSED** (`logic/palette_io.decode`); only a
> thin path-loader is new. Image decode is ruled into `ui/` (QImage, ADR-0010) — not `data/`.
> No new numeric constant (image bounds reuse `MAX_CANVAS_*`; palette ceiling reuses
> `MAX_PALETTE_SIZE`); extension sets are module-local format identifiers (ADR-0001 exemption).

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `file_import.py` | **new** | File-type classifier + shared import-error family (Qt-free, pure). | `FileType` (IMAGE/PROJECT/PALETTE/UNKNOWN), `classify(path)`, `IMAGE_EXTENSIONS`, `PALETTE_EXTENSIONS`, `PROJECT_EXTENSION`, `PALETTE_FORMAT_BY_EXTENSION`, `FileImportError`, `PaletteImportError`, `ImageImportError` | DATA-003, -005 |
| `palette_import.py` | **new** | Palette path-loader: read file → dispatch ext→fmt → delegate to `logic.palette_io.decode`; wrap errors as `PaletteImportError`. | `load_palette(path) -> Palette` | DATA-001 (reuses `palette_io`) |
| `project_io.py` | no change | REUSED for the PROJECT branch (`load_project`). | `load_project`, `ProjectIOError` | DATA-004 |

## `pixelart_creator/logic/` — Phase-7 drag-drop import — BUILT (Slice A-A additions)

| Module | Change | Responsibility | Key public surface | REQ |
| --- | --- | --- | --- | --- |
| `palette.py` | extend | In-place bulk replace so a palette load is one reversible command. | `Palette.replace(colors)` | UI-005 (enabler) |
| `document.py` | extend | Factory seeding a single-frame RGBA document from a decoded buffer. | `Document.from_buffer(buffer, *, palette=None, name="Imported")` | UI-003 (enabler) |
| `palette_io.py` | no change | REUSED — `decode(text, fmt) -> Palette` parses `.gpl`/`.pal`/`hex`. | `decode`, `encode`, `PaletteIOError` | DATA-001 |

## `pixelart_creator/ui/` — Phase-7 drag-drop import — BUILT (Slice A-B)

> Qt lives here only. QImage decode (ADR-0010) hands `logic` a packed RGBA buffer — no Qt crosses
> the boundary. Drop events + router + dirty prompt + notices extend `main_window.py`; the palette
> load reuses the shipped `ui/commands.LogicCommand` over the tab's `QUndoStack` (one undo step).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `image_import.py` | **new** | `decode_image(path) -> PixelBuffer`: QImage → `Format_RGBA8888`, honour `bytesPerLine`, bounds-check pre-alloc, first-frame GIF; raise `ImageImportError`. | `PySide6`, `logic.pixel_buffer`, `logic.constants`, `data.file_import` | DATA-002 |
| `main_window.py` | extend | `setAcceptDrops`/`dragEnter`/`drop` events; `_route_dropped_files` (stable order, per-file guard); image→new tab; palette→undoable replace; `.pixproj`→dirty-guard replace; notices; `save_document` `setClean()`. | `ui/image_import`, `data/file_import`, `data/palette_import`, `data/project_io`, `logic/document`, `ui/commands` | UI-001..009 |

## `pixelart_creator/ui/` — Phase-4 layer & canvas — BUILT (Slice 4C)

> Binds to Slice-4A logic (`blend.composite_stack`, `document` layer ops) + `data/project_io` v2; Qt
> lives here only. `ui/commands.py` (extended) is the sole Qt undo-bridge and delegates to the
> `history.Command` each layer op returns (one `QUndoCommand` per op, no domain math — Article I).
> Canvas recomposites the dirty region only (ADR-0007, **amended T13**: `composite_stack(region=…)`
> returns a region-sized `(h,w,4)` buffer blitted into the resident composite at `(x,y)` — no
> full-canvas alloc on the region path; contract signature unchanged); resident buffers never culled (F7).

| Module | Change | Responsibility | Binds to (logic/data) | REQ |
| --- | --- | --- | --- | --- |
| `layer_panel.py` | **new** | `Layer_Panel(QWidget)`: top-to-bottom layer list; per-row opacity slider / visibility / lock / blend-mode dropdown (12 tr-labels, populated by iterating `list(BlendMode)` — no hard count) / drag-reorder; add/remove/duplicate/group/ungroup; mask + reference + smart affordances; expandable groups; single-selection active layer. | `document` ops, `blend.BlendMode`, `ui/commands` | UI-001..011, 013, 016..018 |
| `canvas_scene.py` | extend | Render the flattened composite via `blend.composite_stack`; refresh only the dirty region on edit. | `blend.composite_stack`, `document` | UI-012 |
| `main_window.py` | extend | Multi-canvas / artboard tabs: per-tab layer tree + `QUndoStack` + composite + scene rect; dock the layer panel; wire to the active document. | `document`, tabs | UI-014 |
| `commands.py` | extend | One `QUndoCommand` per layer op, delegating to the returned `history.Command`; dirty-rect recomposite signalling; no domain math. | `history` + all 4A ops | UI-013 |

## `pixelart_creator/ui/` — PySide6 presentation — PLANNED (Phase-1 UI increment)

> All Qt lives here. Widgets bind to `logic/`+`data/` and carry **no** domain logic
> (Article I). Naming: QWidget subclasses → PascalCase + `_View`/`_Panel`/`_Dialog`
> (top-level shell → `_Window`); non-widget classes → plain PascalCase.

| Module | Responsibility | Public surface | REQ |
| --- | --- | --- | --- |
| `__init__.py` | Package marker. | — | — |
| `i18n.py` | `LanguageManager(QObject)`: `QLocale`-driven `QTranslator` install/swap + live-retranslate signal. | `LanguageManager`, `set_language`, `install_from_locale`, `available_languages`, `languageChanged` | 021, 022 |
| `commands.py` | `PaintCommand(QUndoCommand)` — Qt↔logic undo bridge over `PixelEdit` (D5 dirty-rect). No domain math. | `PaintCommand` | 009, 010 |
| `canvas_scene.py` | `CanvasScene(QGraphicsScene)`: one whole-buffer pixmap item (D1), `setSceneRect` once (D3), `drawBackground` exposed-rect checker+grid (D2), `NoIndex` (D7). | `CanvasScene`, `set_document`, `refresh_rect`, `set_grid_enabled`, `on_document_resized` | 001, 002, 003, 007 |
| `canvas_view.py` | `Canvas_View(QGraphicsView)`: zoom/pan/paint/grid/right-click seam, `MinimalViewportUpdate` (D4), dirty-rect (D5), `QOpenGLWidget` gated by `OPENGL_VIEWPORT_ENABLED` (D6). | `Canvas_View`, `set_tool`, `set_active_color`, `set_menu_hook`, `zoom_in/out`, `set_zoom`, `zoom`, `center_on`, `zoomChanged`, `rightClicked` | 004, 005, 006, 007, 008 |
| `tools/base.py` | `Tool` ABC + `ToolContext`; builds `PaintCommand` via `record_edit`. | `Tool`, `ToolContext` | 011 |
| `tools/pencil.py` | `PencilTool`: `drawing.pencil`, drag→one command. | `PencilTool` | 011, 012 |
| `tools/eraser.py` | `EraserTool`: `drawing.pencil` erase value. | `EraserTool` | 011, 013 |
| `tools/fill.py` | `FloodFillTool`: `drawing.flood_fill`; no-op ⇒ no command. | `FloodFillTool` | 011, 014 |
| `tools/line.py` | `LineTool`: preview on drag, commit on release. | `LineTool` | 011, 015 |
| `tools/picker.py` | `PickerTool`: `drawing.pick_color` → active colour; no command. | `PickerTool` | 011, 016 |
| `theme.py` | Light + dark QSS by role; runtime switch. | `apply_theme`, `available_themes`, `THEME_LIGHT`, `THEME_DARK` | 025 |
| `main_window.py` | `Main_Window(QMainWindow)` shell + `Palette_Panel(QWidget)`: toolbar, palette, document tabs, per-doc `QUndoStack`, Undo/Redo actions, menu bar, New/Open/Save via `data/project_io`. | `Main_Window`, `new_document`, `open_document`, `save_document`, `active_document`, `Palette_Panel` | 017, 018, 019, 020, 022, 024, 025 |

## `pixelart_creator/ui/` — Phase-2 advanced-drawing — BUILT (Slice 2B; FU-10 refresh)

> Binds to Slice-2A logic; Qt lives here only. `ui/commands.py` (extended) is the sole Qt
> undo-bridge and delegates to the `history.Command` each logic op returns (no domain math).
> FU-10: modules now on disk; the two shared bases below were added during 2B build.

| Module | Responsibility | Binds to (logic) | REQ |
| --- | --- | --- | --- |
| `tools/shape_base.py` | `ShapeTool(Tool)` — shared shape-tool base (live preview, commit-on-release, filled/outline option). | `drawing` | UI-001..003 |
| `tools/selection_base.py` | `SelectionTool(Tool)` — shared selection-tool base (combine modifiers, mask commit). | `selection` | UI-004..006 |
| `tools/rectangle_tool.py` | Rectangle shape tool: live preview, commit-on-release. | `drawing.rectangle` | UI-001, 003 |
| `tools/ellipse_tool.py` | Ellipse shape tool. | `drawing.ellipse` | UI-002, 003 |
| `tools/rect_select_tool.py` | Rectangle selection + combine modifiers. | `selection.rect_mask` + ops | UI-004 |
| `tools/lasso_tool.py` | Freehand lasso selection. | `selection.lasso_mask` | UI-005 |
| `tools/magic_wand_tool.py` | Magic-wand selection + tolerance. | `selection.wand_mask` | UI-006 |
| `selection_overlay.py` | Marching-ants outline + drag-to-move. | `selection.move_selection` | UI-007 |
| `transform_dialog.py` | Scale dialog (factor / target, NN). | `transform.scale_nearest` | UI-009 |
| `rotsprite_dialog.py` | Angle input + preview. | `rotsprite.rotsprite` | UI-010 |
| `symmetry_panel.py` | Axis selector; live mirrored strokes. | `symmetry.mirror` | UI-011 |
| `tiled_mode.py` | Tiled toggle + 3×3 preview + wrapped edits. | `tiled.wrap`/`preview_tiling` | UI-015 |
| `main_window.py` (extend) | Selection-op / transform / RotSprite actions; pixel-perfect, grid/snap, AA-off toggles. | selection ops, transform, `pixel_perfect` | UI-008, 009, 012, 013 |
| `canvas_view.py`/`canvas_scene.py` (extend) | AA-off render-hint lock (all previews); grid/snap refinements. | — (render policy) | UI-013, 014 |
| `commands.py` (extend) | One `QUndoCommand` per new mutating op. | `history` + all 2A ops | UI reversibility, LOGIC-015 |

## `pixelart_creator/ui/` — Phase-2 floating-selection (REQ-NEW-C) — BUILT (Slice F-B; ADR-0009)

> Binds to Slice-F-A logic (`selection.lift_selection`/`composite_preview`/`commit_floating`/
> `FloatMode`). Qt only. Undo **reuses** `ui/commands.LogicCommand` (no new command class — it
> already wraps any unapplied `history.Command` the commit builders return). The live drag
> preview is **region-scoped** (ADR-0007-aligned, ADR-0009 D3): per mouse-move calls
> `composite_preview(region=…)` — no full-canvas alloc. NN / AA-off, both themes. Ctrl-only =
> COPY, Alt stays the shipped CL-4 subtract (CL-F5). The `base → floating_move` seam import is
> kept acyclic by a **`TYPE_CHECKING` `LiftContext` `Protocol`** in `floating_move.py` (the tool
> `ToolContext` satisfies it structurally, so no `base` import — `check_cycles` clean, Article I).

| Module | Change | Responsibility | Binds to (logic) | REQ |
| --- | --- | --- | --- | --- |
| `tools/floating_move.py` | **new** | `FloatingMoveController` — single owner of one active float's lift→drag→commit/cancel lifecycle, reachable from mouse (`SelectionTool`), key (`Canvas_View`), and tool-switch (`Main_Window`) events. Declares the `LiftContext` `Protocol` (TYPE_CHECKING) to break the `base` import cycle. No domain math. | `lift_selection`/`composite_preview`/`commit_floating`/`FloatMode`, scene, `ui/commands.LogicCommand` | UI-030..036 |
| `canvas_scene.py` | extend | New `_FloatingPreviewItem(QGraphicsItem)` (floated colours, NN/AA-off, both themes) — one item for the float, one at `_ORIGIN_Z` for the MOVE-vacated origin via `_origin_vacate(...)` — + scene `begin_floating`/`update_floating`/`end_floating`; reuses `_SelectionOverlayItem.set_move_offset` for the marching-ants outline. | `selection.composite_preview` | UI-030..032, 035 |
| `tools/selection_base.py` | extend | Delegate the in-mask press/drag/release move path to `FloatingMoveController` (replaces the inline destructive `_commit_move`); build gestures unchanged; copy modifier disambiguated from build combine — `_COPY_MODIFIERS = ControlModifier` only (CL-F5). | `FloatingMoveController` | UI-030..033, 036 |
| `canvas_view.py` | extend | Route `keyPressEvent`: Enter/Return → `commit()`; Escape → `cancel()`; re-sample modifiers per mouse-move so Ctrl held mid-drag toggles COPY. | controller | UI-033, 034 |
| `main_window.py` | extend | Commit an active float on tool-switch; wire controller into the doc session; `tr()` copy-mode status hint (keyboard-reachable, both themes). | controller | UI-032, 033, 036 |
| `commands.py` | **no change** | Reuse `LogicCommand(commit_floating(...), refresh, label)` — one `QUndoCommand` per commit. | `history` | UI-035 |

## `pixelart_creator/ui/` — Phase-3 colour & palette — PLANNED (Slices 3B/3C)

> Binds to Slice-3A logic + `data/favourites_io`; Qt lives here only. The colour hub wires into the
> confirmed Phase-1 `Canvas_View.set_menu_hook`/`rightClicked(x,y)` seam. `QColor` HSV APIs are used
> only here (CL-2). Every mutating op is one `QUndoCommand` via `ui/commands.py` (plan §10).

| Module | Responsibility | Binds to (logic/data) | REQ | Slice |
| --- | --- | --- | --- | --- |
| `colour_wheel_widget.py` | Canva-style RGB wheel (conical+radial gradient + value slider) with live harmony/ramp swatches. | `color_theory` | UI-005 | 3B |
| `colour_hub_menu.py` | Cursor-anchored right-click hub: Favourites (persisted) + wheel; pick → active swatch; explicit add-to-favourites. | `favourites`, `color_theory`, `data/favourites_io`, canvas seam | UI-003, 004, 006 | 3B |
| `palette_editor_panel.py` | Add/remove/drag-drop reorder + import/export actions (thin disk I/O). | `palette.move`, `palette_io` | UI-001, 002 | 3C |
| `shade_ramp_picker.py` | Shade/tint/tone ramp picker → apply/add. | `color_theory` ramps | UI-007 | 3C |
| `tools/dither_tool.py` | Ordered/Bayer + Floyd–Steinberg dither brushes; stroke = one command. | `dither` | UI-008 | 3C |
| `palette_constraint_panel.py` | NES / Game Boy constraint presets (one command). | `hardware_palette`, `quantize` | UI-009 | 3C |
| `extract_palette_dialog.py` | Extract ≤N palette from image (N + median-cut/k-means). | `quantize` | UI-010 | 3C |
| `palette_analytics_view.py` | Read-only sortable per-colour usage view. | `palette_analytics` | UI-011 | 3C |
| `colour_cycling_panel.py` | Index-range + play/pause non-destructive cycling preview. | `palette_ops` cycle | UI-012 | 3C |
| `palette_swap_dialog.py` | Define + apply an index remap (one command). | `palette_ops` swap | UI-013 | 3C |
| `main_window.py` (extend) | Indexed-mode RGBA↔indexed switch + paint-by-index; wire hub/editor/panels. | `document`, `palette` | UI-014 | 3C |
| `commands.py` (extend) | One `QUndoCommand` per new mutating op (dither/constraint/cycle-commit/swap/palette-edit). | `history` + 3A ops | LOGIC-017 | 3B/3C |

## Tests

| Path | Owner | Scope |
| --- | --- | --- |
| `tests/logic/**`, `tests/data/**` | AGT-04 | Shipped core-engine unit/property tests. |
| `tests/ui/**` | AGT-06 | pytest-qt, headless offscreen, both themes, a11y — one test per SC-UI-* (planned). |
| `tests/data/cloud/**`, `tests/backend/**` | AGT-04 | Phase-10 cloud/backend headless tests (fake adapter + loopback transport + in-process backend); `cloud_live` marker = out-of-CI (planned). |

## `pixelart_creator/logic/` — Phase-10 cloud & collaboration — PLANNED (Slices 10A/10B/10C)

> New Qt-free `logic/` models frozen by AGT-01 (`interface-contract`, plan §5) BEFORE implementation.
> Exceptions subclass `ValueError` (Phase-1 convention); `SyncState` + the CRDT message vocabulary are
> module-local (ADR-0001). New constants (`constants.py`, plan §8, Article II/BF-1/BF-3):
> `AUTOSAVE_INTERVAL_MS`, `MAX_CLOUD_VERSIONS`, `MAX_CLOUD_PROJECT_BYTES`, `CLOUD_RETRY_LIMIT`,
> `MAX_SHARED_MEMBERS`, `MAX_COMMENT_BYTES`, `MAX_COMMENTS_PER_PROJECT`, `MAX_CRDT_UPDATE_BYTES`,
> `CRDT_TILE_SIZE_PX` (all names distinct from shipped). pycrdt/NumPy are third-party pure deps (no Qt).

| Module | Responsibility | Public surface | REQ | Slice |
| --- | --- | --- | --- | --- |
| `sync_state.py` | Pure deterministic local-vs-remote sync state. | `SyncState`, `compute_sync_state`, `SyncError` | LOGIC-001 | 10A |
| `autosave.py` | Pure autosave decision fn (elapsed as input, no clock). | `should_autosave`, `AutosaveError` | LOGIC-002 | 10A |
| `version_history.py` | Ordered, immutable cloud version history (≤ `MAX_CLOUD_VERSIONS`). | `CloudVersion`, `VersionHistory`, `VersionHistoryError` | LOGIC-003 | 10A |
| `cloud_validation.py` | Pure untrusted-input validators + CRDT message vocabulary (schema + size/depth/byte caps; no eval/exec). **Shared by `data/cloud/` AND `sync_backend/`.** | `validate_crdt_update`, `validate_comment`, `validate_membership`, `validate_presence`, `CloudValidationError` | DATA-009/-010, BACKEND-002 | 10B/10C |
| `convergence.py` | HYBRID convergence: pycrdt tree/sequence CRDT (structure) + pure tile/region-LWW (raster); logical-clock+site-id; deterministic, 8K-scalable. | `converge`, `ConvergenceError` | LOGIC-006 | 10B |
| `realtime_apply.py` | Real-time apply of remote CRDT/OT updates + git-like branch/merge. **Per-frame flagged (AGT-10).** | `apply_remote`, `branch`, `merge`, `RealtimeError` | LOGIC-007 | 10C |

## `pixelart_creator/data/cloud/` — Phase-10 cloud port + adapters — PLANNED (Slices 10A/10B/10C)

> New ZERO-Qt `data/` subpackage (governed by the `data` layer rule). No provider SDK/transport type
> leaks above the port; tokens live only here via the OS keyring. `CloudDataError` subclasses
> `ProjectIOError` (PIO-1 family). Provider SDKs imported only in `providers/*`.

| Module | Responsibility | Binds to | REQ | Slice |
| --- | --- | --- | --- | --- |
| `port.py` | The ONE `CloudPort` ABC + normalized `RemoteItem`/`CloudVersion`/`Cursor`/`CloudCapabilities`; `CloudError`/`CloudDataError`. | `logic/version_history`, `constants` | DATA-001, 007 | 10A |
| `fake_adapter.py` | Local-FS/in-memory adapter implementing the whole port (round-trip/versions/recovery); CI, no network/creds. | `port`, `data/project_io` (PIO-1) | DATA-002..005 | 10A |
| `auth.py` | Pure PKCE (`S256`) + loopback (RFC 8252) + token exchange + Device Grant (RFC 8628). | `token_store`, `constants` | DATA-008 | 10A |
| `token_store.py` | OS-keyring token isolation (`keyring`), keyed `pixelart-creator:cloud:{provider}`. | `constants` | DATA-008 | 10A |
| `providers/{drive,onedrive,dropbox}.py` | Real adapters behind the same port; **credential-gated / out-of-CI**. | `port`, `auth` | DATA-001, 007, 008 | 10A |
| `shared_adapter.py` | Shared-project storage + membership behind the port family (fake impl in CI). | `port`, `logic/cloud_validation` | DATA-009 | 10B |
| `transport.py` / `loopback_transport.py` / `ws_transport.py` | Client `TransportPort` for CRDT+presence; loopback (CI) + WebSocket (out-of-CI). | `logic/cloud_validation`, `constants` | DATA-010 | 10C |

## `sync_backend/` — Phase-10 real-time sync backend — PLANNED (Slice 10C; OUTSIDE the three layers, ADR-0027)

> A NEW first-class top-level package (sibling of `pixelart_creator/`), **outside** the three layers and
> **excluded from the desktop wheel**. Governed by the new `check_layering` `sync_backend` rule: imports
> **no** `ui`/`data`/Qt; **may** reuse pure `logic/`. The desktop client reaches it only over the
> `data/cloud/` transport port at run time (never by import). CI-testable in-process/subprocess over loopback.

| Module | Responsibility | Binds to | REQ | Slice |
| --- | --- | --- | --- | --- |
| `server.py` | asyncio WebSocket relay of CRDT updates + awareness/presence; spin-up API for CI; validates every payload (no eval/exec); never receives/stores tokens. | `logic/{cloud_validation, convergence}`, `constants`, `websockets` | BACKEND-001, 002 | 10C |
| `store.py` | Per-`document_id` ordered update-log + latest-presence persistence (in-memory CI; file-backed running). | `logic/constants` | BACKEND-001 | 10C |

## `pixelart_creator/ui/` — Phase-10 cloud & collaboration UI — PLANNED (Slices 10A/10B/10C)

> Qt only. Cloud ops run off the GUI thread (`cloud_worker.py`). No `ui/commands.py` change (cloud/collab/
> real-time are sync/session state, not undoable). Slice-C real-time cursor draw is per-frame flagged (AGT-10).

| Module | Responsibility | Binds to | REQ | Slice |
| --- | --- | --- | --- | --- |
| `cloud_worker.py` | Off-GUI-thread runner for cloud put/get/list/autosave (stays-responsive). | `data/cloud/*` | UI-005 | 10A |
| `cloud_actions.py` | Save-to/open-from cloud (defensive open) + provider connect/disconnect (provider-agnostic). | `data/cloud/port`, `logic/sync_state` | UI-001, 004, 005 | 10A |
| `version_history_browser.py` | `Version_History_Browser` — list/preview/restore prior versions. | `logic/version_history`, `data/cloud/port` | UI-002 | 10A |
| `recovery_prompt.py` | `Recovery_Prompt` — recover/discard on restart (no clobber). | `logic/autosave`, `data/cloud/port` | UI-003 | 10A |
| `shared_projects_panel.py` | `Shared_Projects_Panel` — share/invite/see members. | `data/cloud/shared_adapter` | UI-009 | 10B |
| `comments_panel.py` | `Comments_Panel` — add/thread/resolve validated comments. | `data/cloud/shared_adapter` | UI-010 | 10B |
| `presence_panel.py` | `Presence_Panel` — who else is present (ephemeral). | `data/cloud/transport` | UI-011 | 10B |
| `branching_panel.py` | `Branching_Panel` — branch/diff/merge (conflict-free). | `logic/realtime_apply` | UI-012 | 10C |
| `realtime_cursors_overlay.py` | `Realtime_Cursors_Overlay` — live ephemeral cursors (per-frame, AGT-10). | `data/cloud/transport`, `logic/realtime_apply` | UI-013 | 10C |
</content>
