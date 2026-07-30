# Tasks — Phase 6: Tilemap & Level Design

| Field | Value |
| --- | --- |
| Feature | `phase-6-tilemap` |
| Author | AGT-01 (Architecture) |
| Date | 2026-07-03 |
| Over | `plan.md` (Slices 6A tileset → 6B tilemap → 6C auto-tile → 6D data → 6E/6F/6G UI) |
| Gate | Dispatch only after `sdd-analyze` C1 passes (Article VIII); each task leaves the gate green (Article IX). |

Status legend: `todo` | `doing` | `done`. Owners per the delegation table (AGT-03 logic/data code,
AGT-04 logic/data tests, AGT-05 UI code, AGT-06 UI/a11y tests, AGT-07 string audit, AGT-10 perf,
AGT-08 docs, AGT-01 architecture/analyze). One owner per task (TK-D1); deterministic sub-steps name
their script (TK-D2). Every REQ maps to ≥1 impl + ≥1 test/verify task.

---

## Slice 6A — tileset (`constants.py`, `tileset.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6A-01 | Add the 9 Phase-6 numerics (`DEFAULT_TILE_WIDTH/HEIGHT=16`, `DEFAULT_TILE_MARGIN/SPACING=0`, `MAX_TILE_DIMENSION`, `MAX_TILESET_TILES`, `MAX_TILEMAP_LAYERS`, `TILEMAP_CHUNK_SIZE=16`, `MAX_TILEMAP_COORD`) with citations. **Names DISTINCT from `TILE_SIZE=64` (BF-2) — never reuse it as the tile dimension.** | AGT-03 | `logic/constants.py` | — | LOGIC-014 / SC-L014-2 / plan §8 | todo |
| T6A-02 | `logic/tileset.py` (new): `Tileset` + `TileRegion` + `TilesetError`; deterministic row-major slice (Tiled formula, size/margin/spacing); `columns`/`rows`/`tile_count`/`mode` (inherits source `ColorMode`); `first_gid`/`contains_gid`/`local_id_for_gid`. Zero Qt; no `document` import. Bounds (`MAX_TILE_DIMENSION`/`MAX_TILESET_TILES`) → `TilesetError`. | AGT-03 | `logic/tileset.py` | T6A-01 | LOGIC-001, 003, 014 / SC-L001-1/2, SC-L003-1/2, SC-L014-1 | todo |
| T6A-03 | `region_of` (pure total map) + `tile_pixels` deriving from `PixelBuffer.region` (PB-1, no stored copy); ColorMode inheritance (CM-1). | AGT-03 | `logic/tileset.py` | T6A-02 | LOGIC-002 / SC-L002-1 | todo |
| T6A-04 | Reversible `make_edit_tile_command` (writes source sub-rectangle for a local id, HIS-1; undo restores prior pixels; seen by all readers) + `make_reslice_command` (bounds-checked). | AGT-03 | `logic/tileset.py` | T6A-03 | LOGIC-004 / SC-L004-1 | todo |
| T6A-05 | Unit + property tests: deterministic slice grid + invalid params; row-major stable ids + global gid/first-gid; tile derives from `region` + ColorMode inherit; reversible source-tile edit seen by all readers; bounds + defaults from constants (≠ `TILE_SIZE`). | AGT-04 | `tests/logic/test_tileset.py` | T6A-04 | LOGIC-001, 002, 003, 004, 014 / SC-L001-1/2, L002-1, L003-1/2, L004-1, L014-1/2 | todo |

## Slice 6B — tilemap model + reversible ops (`tilemap.py`) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6B-01 | `logic/tilemap.py` (new): canonical uint32 cell bit layout (Tiled masks `FLIPPED_*`/`ROTATED_HEXAGONAL_120`/`GID_MASK`, module-local intrinsic) + `TileInstance` (`base_gid`/`flip_h`/`flip_v`/`flip_d`); `TilemapError`; empty cell = gid 0. Zero Qt; no `document` import. | AGT-03 | `logic/tilemap.py` | T6A-04 | LOGIC-005 / SC-L005-1 | todo |
| T6B-02 | `TilemapLayer` chunked-sparse storage (`TILEMAP_CHUNK_SIZE` uint32 chunks keyed by origin; only non-empty chunks; `get`/`cells`; arbitrary/negative coords; empty read = 0; `MAX_TILEMAP_COORD` guard) + `Tilemap` (ordered layers, referenced tilesets, `infinite` flag, `resolve` gid → (tileset, local_id)). | AGT-03 | `logic/tilemap.py` | T6B-01 | LOGIC-005, 009 / SC-L005-1, SC-L009-1 | todo |
| T6B-03 | Reversible `make_stamp_command` / `make_erase_command` / `make_fill_rect_command` (do/undo capturing minimal prior cell state; unknown base gid → `TilemapError`). | AGT-03 | `logic/tilemap.py` | T6B-02 | LOGIC-007 / SC-L007-1/2 | todo |
| T6B-04 | Reversible layer ops `make_add/remove/move_layer_command` + `make_set_layer_visibility_command` (`MAX_TILEMAP_LAYERS` bound) + `make_attach_tileset_command`. Cells at same coord on different layers independent. | AGT-03 | `logic/tilemap.py` | T6B-02 | LOGIC-008, 012 / SC-L008-1, SC-L012-1 | todo |
| T6B-05 | `render_region(x,y,w,h)`: resolve each visible cell's instance → source-tile pixels (flip applied via numpy transform), blit (PB-1), flatten the visible layer stack via `blend.composite_stack` (CO-4); non-destructive (source + cells byte-for-byte unchanged). | AGT-03 | `logic/tilemap.py` | T6B-02 | LOGIC-006, 013 / SC-L006-1, SC-L013-1 | todo |
| T6B-06 | Tests: linked instance (gid+flip, no pixel copy; empty=gid 0); source-tile edit propagates to all instances; reversible stamp/erase/fill + unknown-gid reject; reversible layer add/remove/reorder/visibility + `MAX` bound; arbitrary/negative/sparse coords; render resolves + composites via CO-4 (non-destructive); all-mutations do/undo + view state not reversible. | AGT-04 | `tests/logic/test_tilemap.py` | T6B-05 | LOGIC-005, 006, 007, 008, 009, 012, 013 / SC-L005-1, L006-1, L007-1/2, L008-1, L009-1, L012-1, L013-1 | todo |

## Slice 6C — auto-tiling (`autotile.py` + `tilemap` integration) — pure, zero Qt

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6C-01 | `logic/autotile.py` (new): Blob-47 resolver — documented 8-neighbour bit weights (`TL=1..BR=128`, module-local intrinsic) + edge-implies-corner gating → 256-entry load-time LUT → `resolve_display_index(mask)→0..46` (deterministic, O(1)); `AutotileRuleset` (terrain gid + 47 frame gids) + `resolve_display_gid`; `AutotileError`. Imports only `constants`. | AGT-03 | `logic/autotile.py` | T6A-01 | LOGIC-010 / SC-L010-1 | todo |
| T6C-02 | `tilemap` auto-tile integration: `TilemapLayer.autotile` ruleset; stamp/erase store the LOGICAL placement + derive the display gid + re-resolve affected neighbours, capturing prior display gids so undo restores the cell AND re-resolved neighbours (logical/display separation → reversible). | AGT-03 | `logic/tilemap.py` | T6C-01, T6B-03 | LOGIC-011 / SC-L011-1 | todo |
| T6C-03 | Tests: deterministic neighbour-dependent resolution (identical twice; edge-neighbour change changes result) via Hypothesis; auto-tile reversible (logical placement recovered exactly; re-resolved neighbours restored). | AGT-04 | `tests/logic/test_autotile.py`, `tests/logic/test_tilemap.py` | T6C-02 | LOGIC-010, 011 / SC-L010-1, SC-L011-1 | todo |
| T6C-04 | Run `python scripts/check_layering.py` + `python scripts/check_cycles.py`; confirm `document → tilemap → tileset`, `tilemap → autotile`/`blend` acyclic, all three Qt-free, no `logic → data` edge. Must exit 0. | AGT-03 | `scripts/*` (invoke) | T6B-05, T6C-02 | Article I / plan §11 | todo |

## Slice 6D — data (`tiled_io.py` new; `project_io.py` v4) — Qt-free I/O; DEP-2 (ADR-0014/0016)

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6D-01 | `logic/document.py`: attach `tilesets`/`tilemaps` collections (`__slots__`, created empty) + reversible `make_add/remove_tileset_command` + `make_add/remove_tilemap_command`. | AGT-03 | `logic/document.py` | T6B-04 | LOGIC-012 (attach/detach), DATA-004 (surface) / SC-L012-1 | todo |
| T6D-02 | `data/tiled_io.py` (new) export: Tiled map object (`version`/`tiledversion`/`orientation`/`renderorder`/`infinite`/`nextlayerid`/`nextobjectid`); embedded tilesets w/ `firstgid`; per-cell uint32 GID incl. flip flags; CSV `data` (default) or base64+`gzip`/`zlib`; `chunks[]` (16×16) for infinite, dense `data` for fixed. Portable paths (`pathlib`). Imports GID masks from `logic/tilemap`. | AGT-03 | `data/tiled_io.py` | T6C-04 | DATA-001 / SC-D001-1 | todo |
| T6D-03 | `data/tiled_io.py` import + lossless round-trip: base64 decode→decompress→LE uint32; **clear diagonal bit 0x20000000 even for non-hex**; transform order diagonal→H→V; unknown/extra fields verbatim passthrough (properties/wangsets/object layers/counters) → equivalent tilemap. | AGT-03 | `data/tiled_io.py` | T6D-02 | DATA-002 / SC-D002-1 | todo |
| T6D-04 | `data/tiled_io.py` defensive load: validate map/tile geometry, layer sizes vs S12 bounds, gid-in-tileset-range, payload size vs declared geometry, known encoding/compression/orientation; `zstd`/external `.tsx` → `ProjectIOError`; malformed/out-of-bounds/unknown-orientation → `ProjectIOError`; no `eval`/`exec`. | AGT-03 | `data/tiled_io.py` | T6D-03 | DATA-003 / SC-D003-1 | todo |
| T6D-05 | `data/project_io.py` v4: serialise `tilesets` + `tilemaps` (source-image ref + slicing config; layer stack + linked instances + auto-tile logical placement); `FORMAT_VERSION=4`, `_SUPPORTED_VERSIONS=(1,2,3,4)`; defensive load; v1/v2/v3 back-compat → empty collections. | AGT-03 | `data/project_io.py` | T6D-01 | DATA-004 / SC-D004-1 | todo |
| T6D-06 | Tests: valid Tiled JSON export; export→import lossless round-trip (layers, per-cell gid+flip, visibility/order, geometry, tileset gid mapping, unknown-field passthrough); defensive load (out-of-bounds size / out-of-range gid / oversized payload / unknown orientation / zstd / `.tsx` → `ProjectIOError`); native `.pixproj` v4 round-trip + tilemap-less (v1/v2/v3) back-compat. | AGT-04 | `tests/data/test_tiled_io.py`, `tests/data/test_project_io_tilemap.py` | T6D-05 | DATA-001, 002, 003, 004 / SC-D001-1..D004-1 | todo |
| T6D-07 | Re-run `check_layering` + `check_cycles` after 6D (`data/tiled_io → logic/tilemap`, `data/project_io → logic/tileset`/`tilemap` one-way). Must exit 0. Run `path_portability_check` over new `data/` paths. | AGT-03 | `scripts/*` (invoke) | T6D-05 | Article I / VII | todo |

## Slice 6E — tileset editor UI — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6E-01 | `Tileset_Editor_Panel(QWidget)`: show source image sliced into its tile grid (row-major id layout); select active tile (view state, no undo); `tr()` + `changeEvent` retranslate. | AGT-05 | `ui/tileset_editor_panel.py` | T6D-07 | UI-001 / SC-UI-001-1 | todo |
| T6E-02 | Slicing config (tile size / margin / spacing spin-boxes; defaults from `DEFAULT_TILE_*`; out-of-range rejected) → `make_reslice_command`, one `QUndoCommand`. | AGT-05 | `ui/tileset_editor_panel.py`, `ui/commands.py` | T6E-01 | UI-002, 013 / SC-UI-002-1 | todo |
| T6E-03 | Paint into a source tile → `make_edit_tile_command`, one `QUndoCommand`; placed instances update live. | AGT-05 | `ui/tileset_editor_panel.py`, `ui/commands.py`, `ui/main_window.py` | T6E-02 | UI-003, 013 / SC-UI-003-1 | todo |
| T6E-04 | pytest-qt tests (both themes, offscreen): slice display + select (no undo); re-slice + reject; source-tile edit → instances update + one command. | AGT-06 | `tests/ui/test_tileset_editor.py` | T6E-03 | UI-001, 002, 003, 013, 016 / SC-UI-001-1, 002-1, 003-1 | todo |

## Slice 6F — tilemap canvas + stamping + layers + auto-tile + infinite nav + perf — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6F-01 | `Tilemap_Canvas(QGraphicsView/Scene)`: render the composited layer stack via `tilemap.render_region` on the 8K grid; pan/zoom into unbounded space (view state, no undo). | AGT-05 | `ui/tilemap_canvas.py`, `ui/main_window.py` | T6D-07 | UI-004, 010 / SC-UI-004-1, 010-1 | todo |
| T6F-02 | Stamp / eraser / rectangle-fill tools — each one `QUndoCommand` via `make_stamp/erase/fill_rect_command`; stamp into previously-empty infinite space. | AGT-05 | `ui/tilemap_canvas.py`, `ui/commands.py` | T6F-01 | UI-005, 006, 007, 010, 013 / SC-UI-005-1, 006-1, 007-1, 010-1 | todo |
| T6F-03 | `Tilemap_Layer_Panel(QWidget)`: add / remove / reorder / visibility (one command each); active-layer selection (view state). | AGT-05 | `ui/tilemap_layer_panel.py`, `ui/commands.py` | T6F-01 | UI-008, 013 / SC-UI-008-1 | todo |
| T6F-04 | Auto-tile toggle (per layer/brush); stamping resolves each affected cell's display tile from neighbours; the whole stamp (incl. neighbour re-resolution) undoes as one command. | AGT-05 | `ui/tilemap_layer_panel.py`, `ui/tilemap_canvas.py` | T6F-02, T6F-03 | UI-009, 013 / SC-UI-009-1 | todo |
| T6F-05 | Implement the AGT-10 viewport tile-culling + dirty-rect directive: `render_region` on the visible viewport only; recomposite only the stamped rect (ADR-0007 region path); resident buffers never culled. | AGT-05 | `ui/tilemap_canvas.py` | T6F-02 | UI-014 (impl side) / SC-UI-014-1 | todo |
| T6F-06 | pytest-qt tests (both themes, offscreen): composited stack render; stamp/erase/fill = one command each + undo; pan-into-empty + stamp (nav no command); layer management (one command each); auto-tile on stamp (single undoable command); one-command-per-edit + view ops none. | AGT-06 | `tests/ui/test_tilemap_canvas.py`, `tests/ui/test_tilemap_layers.py` | T6F-04 | UI-004..010, 013, 016 / SC-UI-004-1..010-1, 013-1 | todo |
| T6F-07 | Perf profile (`perf_profile`/`frame-profile`, headless): 8K multi-layer tilemap render/stamp/pan ≤ `FRAME_BUDGET_MS`; over-budget → AGT-10 directive (viewport tile-culling / dirty-rect / scene-rect/BSP tuning), never a budget relaxation. Coordinates with T6F-05. | AGT-10 | `scripts/perf_profile.py` (invoke) | T6F-05 | UI-014 (NFR) / SC-UI-014-1 | todo |

## Slice 6G — import/export UI — Qt only

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T6G-01 | Export action: write the active tilemap to Tiled JSON at a user-chosen (portable) path via `tiled_io.write_tiled_json`. | AGT-05 | `ui/tilemap_io_actions.py`, `ui/main_window.py` | T6F-01 | UI-011 / SC-UI-011-1 | todo |
| T6G-02 | Import action: load a Tiled JSON map via `tiled_io.read_tiled_json` → equivalent tilemap; a malformed file surfaces a user-facing error (no crash). | AGT-05 | `ui/tilemap_io_actions.py`, `ui/main_window.py` | T6G-01 | UI-012 / SC-UI-012-1 | todo |
| T6G-03 | pytest-qt tests (both themes): export writes Tiled JSON to a portable path; import reconstructs; malformed → graceful error. | AGT-06 | `tests/ui/test_tilemap_io_actions.py` | T6G-02 | UI-011, 012, 016 / SC-UI-011-1, 012-1 | todo |

## Cross-cutting / gate tasks

| ID | Description | Owner | Target file(s) | Deps | REQ / acceptance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TG-01 | Update `STRUCTURE.md` with the Phase-6 `tileset.py`/`tilemap.py`/`autotile.py` + `document.py`/`constants.py`/`project_io.py` extensions, the new `data/tiled_io.py`, and the new `ui/` panels (marked planned per house convention). | AGT-01 | `STRUCTURE.md` | plan | Article I map | done |
| TG-02 | `sdd-analyze` C1 gate over constitution/spec/plan/tasks; zero unresolved findings before implement. | AGT-01 | `specs/phase-6-tilemap/analyze-report.md` | tasks | Article VIII | done |
| TG-03 | a11y audit (`a11y-audit`): accessible names/descriptions, keyboard reachability + logical tab order, visible focus on all tileset/tilemap controls (tile cells, slicing spin-boxes, tool buttons, layer list + actions, auto-tile toggle, import/export). | AGT-06 | `tests/ui/*` | T6E-04, T6F-06, T6G-03 | UI-015 / SC-UI-015-1 | todo |
| TG-04 | Both-theme render verification (role-based colours: grid lines, selection highlight, layer-row states) across the tileset editor / canvas chrome / tool bar / layer panel / dialogs. | AGT-06 | `tests/ui/*` | T6E-04, T6F-06, T6G-03 | UI-016 / SC-UI-016-1 | todo |
| TG-05 | String audit (`string_audit_check`): zero unwrapped user-visible strings (tool names/tooltips, slicing labels + units, layer actions, auto-tile labels, import/export dialog text, error messages). | AGT-07 | `ui/*.py` | T6E-03, T6F-04, T6G-02 | UI-017 / SC-UI-017-1 | todo |
| TG-06 | CHANGELOG (`Unreleased`) entries for Phase-6 features tied to REQ-IDs. | AGT-08 | `docs/CHANGELOG.md` | 6A/6B/6C/6D/6E/6F/6G done | Article IX | todo |
| TG-07 | `sdd-checklist` before ship: every REQ has a passing test; both themes + a11y + perf + i18n gates green. | AGT-06 | checklist report | all impl+test done | Article IV/V/VI | todo |
