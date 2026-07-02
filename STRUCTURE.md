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

## Tests

| Path | Owner | Scope |
| --- | --- | --- |
| `tests/logic/**`, `tests/data/**` | AGT-04 | Shipped core-engine unit/property tests. |
| `tests/ui/**` | AGT-06 | pytest-qt, headless offscreen, both themes, a11y — one test per SC-UI-* (planned). |
</content>
