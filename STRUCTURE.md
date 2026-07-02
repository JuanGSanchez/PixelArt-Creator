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
| `selection.py` | Boolean selection-region model + builders + ops + mask-constrained apply + floating move. | `SelectionMask` (is_selected/is_empty/bounds/count/data/copy/invert/cleared/translate/combine), `rect_mask`, `lasso_mask`, `wand_mask`, `apply_masked`, `move_selection`, `SelectionError` | LOGIC-001..006, 010 |
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
</content>
