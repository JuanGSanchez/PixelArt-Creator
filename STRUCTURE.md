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
| `document.py` | Document → frames → layers → buffers; resize. | `Document`, `Frame`, `Layer`, `resize_canvas`, `DocumentError` |
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

## `pixelart_creator/data/` — I/O & persistence (zero Qt) — SHIPPED

| Module | Responsibility | Key public surface |
| --- | --- | --- |
| `project_io.py` | Validated `.pixproj` (JSON) serialise/deserialise/save/load. | `serialize`, `deserialize`, `save_project`, `load_project`, `ProjectIOError` |

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

## `pixelart_creator/ui/` — Phase-2 advanced-drawing — PLANNED (Slice 2B)

> Binds to Slice-2A logic; Qt lives here only. `ui/commands.py` (extended) is the sole Qt
> undo-bridge and delegates to the `history.Command` each logic op returns (no domain math).

| Module | Responsibility | Binds to (logic) | REQ |
| --- | --- | --- | --- |
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

## Tests

| Path | Owner | Scope |
| --- | --- | --- |
| `tests/logic/**`, `tests/data/**` | AGT-04 | Shipped core-engine unit/property tests. |
| `tests/ui/**` | AGT-06 | pytest-qt, headless offscreen, both themes, a11y — one test per SC-UI-* (planned). |
</content>
