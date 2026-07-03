"""Application shell — toolbar, palette, tabs, actions, menu (REQ-P1-UI-017..020).

``Main_Window`` wires the presentation together: an exclusive tool toolbar (017),
a single-select :class:`Palette_Panel` (018), document tabs each backed by a
``QUndoStack`` in a shared ``QUndoGroup`` (019/020), a File/Edit/View/Language/
Theme menu bar (019), accessible names on every control (024), a runtime theme
switch (025), and ``changeEvent`` retranslation (022). New documents default to
``DEFAULT_CANVAS_WIDTH`` × ``DEFAULT_CANVAS_HEIGHT`` (020); open/save delegate to
``data/project_io`` (020). It holds no domain logic — every edit routes through a
tool → ``logic/drawing`` → :class:`PaintCommand` (Article I).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import QEvent, QRectF, QStandardPaths, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QCursor,
    QIcon,
    QImage,
    QKeySequence,
    QPixmap,
    QUndoGroup,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QToolBar,
    QWidget,
)

from pixelart_creator.data.favourites_io import (
    FavouritesIOError,
    load_favourites,
    save_favourites,
)
from pixelart_creator.data.project_io import (
    FILE_SUFFIX,
    load_project,
    save_project,
)
from pixelart_creator.logic import history, transform
from pixelart_creator.logic.color import BLACK, RGBA, TRANSPARENT, to_hex
from pixelart_creator.logic.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
)
from pixelart_creator.logic.document import Document, DocumentError, Layer
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.palette_ops import (
    IndexedModeError,
    make_cycle_command,
    make_swap_command,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import QuantizeError, make_constraint_command
from pixelart_creator.logic.rotsprite import make_rotsprite_command, rotsprite
from pixelart_creator.logic.selection import (
    SelectionMask,
    apply_masked,
    rect_mask,
)
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.logic.transform import (
    TransformError,
    scale_nearest,
)
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.colour_cycling_panel import Colour_Cycling_Panel
from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
from pixelart_creator.ui.commands import LogicCommand, PaintCommand
from pixelart_creator.ui.extract_palette_dialog import Extract_Palette_Dialog
from pixelart_creator.ui.i18n import LanguageManager
from pixelart_creator.ui.layer_panel import Layer_Panel
from pixelart_creator.ui.palette_analytics_view import Palette_Analytics_View
from pixelart_creator.ui.palette_constraint_panel import (
    Palette_Constraint_Panel,
    preset_palette,
)
from pixelart_creator.ui.palette_editor_panel import Palette_Editor_Panel
from pixelart_creator.ui.palette_swap_dialog import Palette_Swap_Dialog
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
from pixelart_creator.ui.shade_ramp_picker import Shade_Ramp_Picker
from pixelart_creator.ui.symmetry_panel import Symmetry_Panel
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.tiled_mode import set_tiled_mode
from pixelart_creator.ui.tools import (
    DitherTool,
    EllipseTool,
    EraserTool,
    FloodFillTool,
    LassoTool,
    LineTool,
    MagicWandTool,
    PencilTool,
    PickerTool,
    RectangleTool,
    RectSelectTool,
    Tool,
)
from pixelart_creator.ui.tools.dither_tool import (
    MODE_FLOYD_STEINBERG,
    MODE_ORDERED,
)
from pixelart_creator.ui.transform_dialog import Scale_Dialog

#: A sensible starter palette for a new document (usability, not a spec value).
_STARTER_PALETTE: List[RGBA] = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
    (30, 190, 60, 255),
    (40, 90, 220, 255),
    (240, 220, 40, 255),
]

#: Swatch icon edge, px (presentation-only sizing, not a domain tuning value).
_SWATCH_PX = 24

#: Filename of the app-level Favourites store under AppConfigLocation (ADR-0004).
_FAVOURITES_FILE = "favourites.json"


@dataclass
class _DocTab:
    """Per-tab editing context bound to one open document."""

    document: Document
    scene: CanvasScene
    view: Canvas_View
    stack: QUndoStack


class Palette_Panel(QWidget):
    """Displays the document palette in index order; single-select (018/CL-6)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build an empty single-select swatch list with a colour-mode indicator."""
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        # Colour-mode indicator (RGBA vs Indexed) for the active buffer (P3-UI-014).
        self._mode_label = QLabel(self)
        self._mode: Optional[ColorMode] = None
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(self._mode_label)
        self._retranslate()

    @property
    def colorSelected(self):  # noqa: N802 - expose the inner signal
        """Signal emitted with the selected RGBA tuple."""
        return self._list.itemSelectionChanged

    def selected_color(self) -> Optional[RGBA]:
        """Return the RGBA of the selected swatch, or ``None``."""
        items = self._list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def selected_index(self) -> Optional[int]:
        """Return the palette index of the selected swatch, or ``None`` (P3-UI-014).

        The list is populated in palette index order, so the current row is the
        palette index (the paint-by-index value for an indexed buffer)."""
        row = self._list.currentRow()
        return row if 0 <= row < self._list.count() else None

    def set_mode(self, mode: ColorMode) -> None:
        """Show the active buffer's colour mode (RGBA vs Indexed) (P3-UI-014)."""
        self._mode = mode
        self._retranslate_mode()

    def set_palette(self, palette: Palette) -> None:
        """Populate the panel from ``palette`` in index order."""
        self._list.clear()
        for color in palette.colors():
            item = QListWidgetItem()
            pixmap = QPixmap(_SWATCH_PX, _SWATCH_PX)
            pixmap.fill(QColor(*color))
            item.setIcon(QIcon(pixmap))
            item.setData(Qt.ItemDataRole.UserRole, color)
            item.setToolTip(to_hex(color))
            item.setText(to_hex(color))
            self._list.addItem(item)

    def select_color(self, color: RGBA) -> None:
        """Select the swatch matching ``color`` if present (else clear)."""
        self._list.clearSelection()
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == color:
                item.setSelected(True)
                self._list.setCurrentItem(item)
                return

    def _retranslate(self) -> None:
        self._list.setAccessibleName(self.tr("Colour palette"))
        self.setAccessibleName(self.tr("Palette panel"))
        self._mode_label.setAccessibleName(self.tr("Colour mode"))
        self._retranslate_mode()

    def _retranslate_mode(self) -> None:
        if self._mode is ColorMode.INDEXED:
            text = self.tr("Mode: Indexed")
        elif self._mode is ColorMode.RGBA:
            text = self.tr("Mode: RGBA")
        else:
            text = self.tr("Mode: —")
        self._mode_label.setText(text)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Main_Window(QMainWindow):
    """The Phase-1 editor shell."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the shell, apply the theme, and open one default document."""
        super().__init__(parent)
        app = QApplication.instance()
        assert isinstance(app, QApplication)  # a QApplication must already exist
        self._app = app
        self._language_manager = LanguageManager(app, parent=self)
        self._undo_group = QUndoGroup(self)
        self._tabs_data: List[_DocTab] = []
        self._active_color: RGBA = BLACK
        self._active_index: int = 0
        self._theme = THEME_LIGHT

        self._rectangle_tool = RectangleTool()
        self._ellipse_tool = EllipseTool()
        self._wand_tool = MagicWandTool()
        self._dither_tool = DitherTool()
        self._tools: dict[str, Tool] = {
            PencilTool.tool_id: PencilTool(),
            EraserTool.tool_id: EraserTool(),
            FloodFillTool.tool_id: FloodFillTool(),
            LineTool.tool_id: LineTool(),
            PickerTool.tool_id: PickerTool(),
            RectangleTool.tool_id: self._rectangle_tool,
            EllipseTool.tool_id: self._ellipse_tool,
            RectSelectTool.tool_id: RectSelectTool(),
            LassoTool.tool_id: LassoTool(),
            MagicWandTool.tool_id: self._wand_tool,
            DitherTool.tool_id: self._dither_tool,
        }
        self._active_tool_id = PencilTool.tool_id
        # Per-view Phase-2 drawing modes (applied to each tab's view).
        self._symmetry_axis: SymmetryAxis = SymmetryAxis.NONE
        self._pixel_perfect = False
        self._tiled = False
        self._snap = False

        self._tab_widget = QTabWidget(self)
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self._tab_widget.tabCloseRequested.connect(self.close_document)
        self.setCentralWidget(self._tab_widget)

        self._palette_panel = Palette_Panel(self)
        self._palette_panel.colorSelected.connect(self._on_palette_selected)
        self._palette_dock = QDockWidget(self)
        self._palette_dock.setWidget(self._palette_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._palette_dock)

        self._symmetry_panel = Symmetry_Panel(self)
        self._symmetry_panel.axisChanged.connect(self._on_symmetry_axis_changed)
        self._symmetry_dock = QDockWidget(self)
        self._symmetry_dock.setWidget(self._symmetry_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._symmetry_dock)

        # Phase-4 layer panel (REQ-P4-UI-001..011): the layer/group tree bound to
        # the active document. Its ops push one LayerCommand each; a mutation
        # recomposites the active scene via the per-tab tree-changed hook (UI-013).
        self._layer_panel = Layer_Panel(self)
        self._layer_panel.activeNodeChanged.connect(self._on_active_node_changed)
        self._layer_panel.maskEditToggled.connect(self._on_mask_edit_toggled)
        self._layer_dock = QDockWidget(self)
        self._layer_dock.setWidget(self._layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_dock)

        # Phase-3 Slice-3C palette-workflow surfaces (REQ-P3-UI-001/-002/-007..-013).
        # Each binds to the Slice-3A logic and pushes one QUndoCommand per mutation.
        self._palette_editor = Palette_Editor_Panel(self)
        self._palette_editor.colorSelected.connect(self._on_palette_selected_rgba)
        self._editor_dock = self._add_workflow_dock(self._palette_editor)

        self._constraint_panel = Palette_Constraint_Panel(self)
        self._constraint_panel.constraintRequested.connect(self._on_constrain)
        self._constraint_dock = self._add_workflow_dock(self._constraint_panel)

        self._ramp_picker = Shade_Ramp_Picker(self)
        self._ramp_picker.colorPicked.connect(self._on_ramp_picked)
        self._ramp_picker.rampAddRequested.connect(self._on_ramp_added)
        self._ramp_dock = self._add_workflow_dock(self._ramp_picker)

        self._cycling_panel = Colour_Cycling_Panel(self)
        self._cycling_panel.previewColors.connect(self._on_cycle_preview)
        self._cycling_panel.applyRequested.connect(self._on_cycle_apply)
        self._cycling_dock = self._add_workflow_dock(self._cycling_panel)

        self._analytics_view = Palette_Analytics_View(self)
        self._analytics_view.set_document_provider(self.active_document)
        self._analytics_dock = self._add_workflow_dock(self._analytics_view)
        # Lazy analytics: the full-buffer scan is deferred while this dock is
        # hidden and computed when it becomes visible. visibilityChanged is the
        # robust Qt signal for a tabified dock's real visibility (PERF fix).
        self._analytics_dock.visibilityChanged.connect(
            self._analytics_view.on_dock_visibility_changed
        )

        # Marquee S3/S4 colour hub: a persisted Favourites model + the cursor-
        # anchored hub, wired into each view's Phase-1 right-click seam. A pick
        # applies to the active colour (tool state) — never an undo entry (T17).
        self._favourites = self._load_favourites()
        self._colour_hub = Colour_Hub_Menu(self)
        self._colour_hub.set_favourites_model(self._favourites)
        self._colour_hub.colorApplied.connect(self._on_hub_color_applied)
        self._colour_hub.favouritesChanged.connect(self._save_favourites)

        self._build_actions()
        self._build_toolbar()
        self._build_menu()

        apply_theme(self._app, self._theme)
        self._language_manager.install_from_locale()

        self.new_document()
        self._retranslate()

    # -- actions / toolbar / menu ----------------------------------------

    def _build_actions(self) -> None:
        # Aseprite-conventional single-key tool shortcuts (REQ-P1-UI-024). The
        # Phase-2 keys avoid the Phase-1 set (B/E/G/L/I).
        tool_shortcuts = {
            PencilTool.tool_id: "B",
            EraserTool.tool_id: "E",
            FloodFillTool.tool_id: "G",
            LineTool.tool_id: "L",
            PickerTool.tool_id: "I",
            RectangleTool.tool_id: "R",
            EllipseTool.tool_id: "O",
            RectSelectTool.tool_id: "M",
            LassoTool.tool_id: "Q",
            MagicWandTool.tool_id: "W",
            DitherTool.tool_id: "D",
        }
        self._tool_action_group = QActionGroup(self)
        self._tool_action_group.setExclusive(True)
        self._tool_actions: dict[str, QAction] = {}
        for tool_id in self._tools:
            action = QAction(self)
            action.setCheckable(True)
            action.setData(tool_id)
            key = tool_shortcuts.get(tool_id)
            if key:
                action.setShortcut(QKeySequence(key))
            action.triggered.connect(self._on_tool_action)
            self._tool_action_group.addAction(action)
            self._tool_actions[tool_id] = action
        self._tool_actions[self._active_tool_id].setChecked(True)

        self._undo_action = self._undo_group.createUndoAction(self, self.tr("&Undo"))
        self._undo_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_Z)
        self._redo_action = self._undo_group.createRedoAction(self, self.tr("&Redo"))
        self._redo_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_Y)

        self._new_action = QAction(self)
        self._new_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_N)
        self._new_action.triggered.connect(lambda: self.new_document())
        self._open_action = QAction(self)
        self._open_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_O)
        self._open_action.triggered.connect(self._on_open)
        self._save_action = QAction(self)
        self._save_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_S)
        self._save_action.triggered.connect(self._on_save)
        self._save_as_action = QAction(self)
        self._save_as_action.triggered.connect(self._on_save_as)
        self._close_action = QAction(self)
        self._close_action.triggered.connect(
            lambda: self.close_document(self._tab_widget.currentIndex())
        )

        self._zoom_in_action = QAction(self)
        self._zoom_in_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_Plus)
        self._zoom_in_action.triggered.connect(self._on_zoom_in)
        self._zoom_out_action = QAction(self)
        self._zoom_out_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_Minus)
        self._zoom_out_action.triggered.connect(self._on_zoom_out)
        self._fit_action = QAction(self)
        self._fit_action.triggered.connect(self._on_fit)
        self._grid_action = QAction(self)
        self._grid_action.setCheckable(True)
        self._grid_action.toggled.connect(self._on_grid_toggled)
        self._snap_action = QAction(self)
        self._snap_action.setCheckable(True)
        self._snap_action.toggled.connect(self._on_snap_toggled)
        self._aa_off_action = QAction(self)
        self._aa_off_action.setCheckable(True)
        self._aa_off_action.setChecked(True)  # locked on (CL-15)
        self._aa_off_action.toggled.connect(self._on_aa_off_toggled)

        # Shape + drawing-mode toggles (REQ-P2-UI-003, -012, -015).
        self._filled_action = QAction(self)
        self._filled_action.setCheckable(True)
        self._filled_action.toggled.connect(self._on_filled_toggled)
        self._pixel_perfect_action = QAction(self)
        self._pixel_perfect_action.setCheckable(True)
        self._pixel_perfect_action.toggled.connect(self._on_pixel_perfect_toggled)
        self._tiled_action = QAction(self)
        self._tiled_action.setCheckable(True)
        self._tiled_action.toggled.connect(self._on_tiled_toggled)

        # Selection-op actions (REQ-P2-UI-008).
        self._select_all_action = QAction(self)
        self._select_all_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_A)
        self._select_all_action.triggered.connect(self._on_select_all)
        self._deselect_action = QAction(self)
        self._deselect_action.setShortcut(
            Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_A
        )
        self._deselect_action.triggered.connect(self._on_deselect)
        self._invert_action = QAction(self)
        self._invert_action.setShortcut(Qt.Modifier.CTRL | Qt.Key.Key_I)
        self._invert_action.triggered.connect(self._on_invert_selection)
        self._clear_action = QAction(self)
        self._clear_action.setShortcut(Qt.Key.Key_Delete)
        self._clear_action.triggered.connect(self._on_clear_selection)

        # Transform + RotSprite actions (REQ-P2-UI-009, -010). Flips get direct
        # accelerators (A11Y-P2-2); Shift+H / Shift+V are free (disjoint from the
        # tool single keys and the Ctrl/Del selection shortcuts).
        self._flip_h_action = QAction(self)
        self._flip_h_action.setShortcut(Qt.Modifier.SHIFT | Qt.Key.Key_H)
        self._flip_h_action.triggered.connect(self._on_flip_horizontal)
        self._flip_v_action = QAction(self)
        self._flip_v_action.setShortcut(Qt.Modifier.SHIFT | Qt.Key.Key_V)
        self._flip_v_action.triggered.connect(self._on_flip_vertical)
        self._rotate_cw_action = QAction(self)
        self._rotate_cw_action.triggered.connect(self._on_rotate_cw)
        self._rotate_ccw_action = QAction(self)
        self._rotate_ccw_action.triggered.connect(self._on_rotate_ccw)
        self._scale_action = QAction(self)
        self._scale_action.triggered.connect(self._on_scale)
        self._rotsprite_action = QAction(self)
        self._rotsprite_action.triggered.connect(self._on_rotsprite)

        # Magic-wand tolerance control (REQ-P2-UI-006).
        self._tolerance_spin = QSpinBox(self)
        self._tolerance_spin.setRange(0, 255)
        self._tolerance_spin.setValue(self._wand_tool.tolerance)
        self._tolerance_spin.valueChanged.connect(self._on_tolerance_changed)
        self._tolerance_label = QLabel(self)

        # Dither-mode selector for the dither brush (REQ-P3-UI-008).
        self._dither_mode_combo = QComboBox(self)
        self._dither_mode_combo.addItem("", MODE_ORDERED)
        self._dither_mode_combo.addItem("", MODE_FLOYD_STEINBERG)
        self._dither_mode_combo.currentIndexChanged.connect(
            self._on_dither_mode_changed
        )
        self._dither_mode_label = QLabel(self)

        # Palette-workflow menu actions (REQ-P3-UI-007/-010/-013).
        self._extract_action = QAction(self)
        self._extract_action.triggered.connect(self._on_extract_palette)
        self._swap_action = QAction(self)
        self._swap_action.triggered.connect(self._on_palette_swap)

        # Indexed-mode conversion actions (REQ-P3-UI-014, T22). No standalone
        # QKeySequence — menu items only, so they never clash with the reserved
        # single-key tool shortcuts; the mnemonics are unique within &Palette.
        self._to_indexed_action = QAction(self)
        self._to_indexed_action.triggered.connect(self._on_convert_to_indexed)
        self._to_rgba_action = QAction(self)
        self._to_rgba_action.triggered.connect(self._on_convert_to_rgba)

        self._theme_light_action = QAction(self)
        self._theme_light_action.setCheckable(True)
        self._theme_light_action.setChecked(True)
        self._theme_light_action.triggered.connect(lambda: self.set_theme(THEME_LIGHT))
        self._theme_dark_action = QAction(self)
        self._theme_dark_action.setCheckable(True)
        self._theme_dark_action.triggered.connect(lambda: self.set_theme(THEME_DARK))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_group.addAction(self._theme_light_action)
        self._theme_group.addAction(self._theme_dark_action)

    def _build_toolbar(self) -> None:
        self._toolbar = QToolBar(self)
        self._toolbar.setObjectName("tool_toolbar")
        for tool_id in self._tools:
            self._toolbar.addAction(self._tool_actions[tool_id])
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._filled_action)
        self._toolbar.addAction(self._pixel_perfect_action)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._tolerance_label)
        self._toolbar.addWidget(self._tolerance_spin)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._dither_mode_label)
        self._toolbar.addWidget(self._dither_mode_combo)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._toolbar)

    def _build_menu(self) -> None:
        bar = self.menuBar()
        self._file_menu = bar.addMenu("")
        self._file_menu.addAction(self._new_action)
        self._file_menu.addAction(self._open_action)
        self._file_menu.addAction(self._save_action)
        self._file_menu.addAction(self._save_as_action)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self._close_action)

        self._edit_menu = bar.addMenu("")
        self._edit_menu.addAction(self._undo_action)
        self._edit_menu.addAction(self._redo_action)

        self._select_menu = bar.addMenu("")
        self._select_menu.addAction(self._select_all_action)
        self._select_menu.addAction(self._deselect_action)
        self._select_menu.addAction(self._invert_action)
        self._select_menu.addAction(self._clear_action)

        self._image_menu = bar.addMenu("")
        self._image_menu.addAction(self._flip_h_action)
        self._image_menu.addAction(self._flip_v_action)
        self._image_menu.addAction(self._rotate_cw_action)
        self._image_menu.addAction(self._rotate_ccw_action)
        self._image_menu.addSeparator()
        self._image_menu.addAction(self._scale_action)
        self._image_menu.addAction(self._rotsprite_action)

        self._view_menu = bar.addMenu("")
        self._view_menu.addAction(self._zoom_in_action)
        self._view_menu.addAction(self._zoom_out_action)
        self._view_menu.addAction(self._fit_action)
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._grid_action)
        self._view_menu.addAction(self._snap_action)
        self._view_menu.addAction(self._aa_off_action)
        self._view_menu.addAction(self._tiled_action)
        # Discoverable + keyboard-reachable drawing-mode toggles (A11Y-P2-1): the
        # filled-shape and pixel-perfect toggles were toolbar-only; surface them in
        # the menu with mnemonics alongside the other drawing modes.
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._filled_action)
        self._view_menu.addAction(self._pixel_perfect_action)
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._layer_dock.toggleViewAction())

        self._palette_menu = bar.addMenu("")
        self._palette_menu.addAction(self._extract_action)
        self._palette_menu.addAction(self._swap_action)
        self._palette_menu.addSeparator()
        self._palette_menu.addAction(self._to_indexed_action)
        self._palette_menu.addAction(self._to_rgba_action)
        self._palette_menu.addSeparator()
        self._palette_menu.addAction(self._editor_dock.toggleViewAction())
        self._palette_menu.addAction(self._constraint_dock.toggleViewAction())
        self._palette_menu.addAction(self._ramp_dock.toggleViewAction())
        self._palette_menu.addAction(self._cycling_dock.toggleViewAction())
        self._palette_menu.addAction(self._analytics_dock.toggleViewAction())

        self._theme_menu = bar.addMenu("")
        self._theme_menu.addAction(self._theme_light_action)
        self._theme_menu.addAction(self._theme_dark_action)

        self._language_menu = bar.addMenu("")
        for code in self._language_manager.available_languages():
            action = QAction(code, self)
            action.setData(code)
            action.triggered.connect(self._on_language_action)
            self._language_menu.addAction(action)

    # -- document lifecycle ----------------------------------------------

    def new_document(
        self,
        width: int = DEFAULT_CANVAS_WIDTH,
        height: int = DEFAULT_CANVAS_HEIGHT,
    ) -> Document:
        """Create a new document (default 64×64 RGBA, 8K supported) in a tab."""
        document = Document(width, height, palette=Palette(_STARTER_PALETTE))
        return self._add_document_tab(document, self.tr("Untitled"))

    def open_document(self, path: str) -> Document:
        """Open a ``.pixproj`` via ``data/project_io`` into a new tab (020)."""
        document = load_project(path)
        self._add_document_tab(document, Path(path).name)
        return document

    def save_document(self, path: str) -> None:
        """Save the active document via ``data/project_io`` (020)."""
        record = self.active_tab()
        if record is not None:
            save_project(record.document, path)

    def _add_document_tab(self, document: Document, title: str) -> Document:
        scene = CanvasScene(document)
        stack = QUndoStack(self)
        self._undo_group.addStack(stack)
        view = Canvas_View(scene, stack)
        view.colorPicked.connect(self._on_color_picked)
        view.set_menu_hook(self._open_colour_hub)
        record = _DocTab(document, scene, view, stack)
        self._tabs_data.append(record)
        index = self._tab_widget.addTab(view, title)
        self._tab_widget.setCurrentIndex(index)
        self._apply_theme_to_scene(scene)
        view.set_tool(self._tools[self._active_tool_id])
        view.set_active_color(self._active_color)
        view.set_active_index(self._active_index)
        self._apply_modes_to(record)
        self._bind_palette_workflows(record)
        return document

    def _add_workflow_dock(self, widget: QWidget) -> QDockWidget:
        """Add a Slice-3C workflow widget as a dock tabified with the palette."""
        dock = QDockWidget(self)
        dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self._palette_dock, dock)
        return dock

    def _bind_palette_workflows(self, record: "_DocTab") -> None:
        """Point the palette editor / cycling / dither surfaces at ``record``."""
        palette = record.document.palette
        self._palette_panel.set_palette(palette)
        self._palette_editor.set_active_color(self._active_color)
        self._palette_editor.set_context(palette, record.stack, self._on_palette_edited)
        self._cycling_panel.stop()
        self._cycling_panel.set_palette(palette)
        self._dither_tool.set_palette(palette)
        # Bind the layer panel to this tab's document + undo stack; the
        # tree-changed hook recomposites THIS tab's scene only (state isolation,
        # UI-014). Each tab owns its own document tree, QUndoStack and composite.
        scene = record.scene
        # Structural ops recomposite the whole stack (refresh_all); attribute ops
        # scope to the visible viewport (refresh_visible, D2) and a live opacity
        # drag is throttled to one recomposite/frame (refresh_visible_throttled, D3).
        self._layer_panel.set_context(
            record.document,
            record.stack,
            scene.refresh_all,
            scene.refresh_visible,
            scene.refresh_visible_throttled,
        )
        self._refresh_mode_ui()

    def _apply_modes_to(self, record: _DocTab) -> None:
        """Push the shell's Phase-2 drawing modes onto a tab's view/scene."""
        view = record.view
        view.set_symmetry_axis(self._symmetry_axis)
        view.set_pixel_perfect(self._pixel_perfect)
        view.set_snap_enabled(self._snap)
        view.set_grid_enabled(self._grid_action.isChecked())
        view.reassert_no_antialiasing()
        set_tiled_mode(record.scene, view, self._tiled)

    def close_document(self, index: int) -> None:
        """Close the document tab at ``index``."""
        if not 0 <= index < len(self._tabs_data):
            return
        record = self._tabs_data.pop(index)
        self._undo_group.removeStack(record.stack)
        self._tab_widget.removeTab(index)

    def active_tab(self) -> Optional[_DocTab]:
        """Return the active tab record, or ``None`` if no document is open."""
        index = self._tab_widget.currentIndex()
        if 0 <= index < len(self._tabs_data):
            return self._tabs_data[index]
        return None

    def active_document(self) -> Optional[Document]:
        """Return the active document, or ``None``."""
        record = self.active_tab()
        return record.document if record is not None else None

    # -- slots ------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        record = self.active_tab()
        if record is None:
            return
        self._undo_group.setActiveStack(record.stack)
        record.view.set_tool(self._tools[self._active_tool_id])
        record.view.set_active_color(self._active_color)
        record.view.set_active_index(self._active_index)
        self._apply_modes_to(record)
        self._bind_palette_workflows(record)
        # Lazy: defer the buffer scan unless the analytics dock is visible.
        self._analytics_view.request_refresh()

    def _on_tool_action(self) -> None:
        action = self.sender()
        if isinstance(action, QAction):
            self._active_tool_id = action.data()
            record = self.active_tab()
            if record is not None:
                record.view.set_tool(self._tools[self._active_tool_id])

    def _on_palette_selected(self) -> None:
        # The palette panel drives paint-by-index: the selected row is the paint
        # index on an indexed buffer (REQ-P3-UI-014). Set the colour first, then
        # let the precise row index win over any index_of() duplicate match.
        color = self._palette_panel.selected_color()
        if color is not None:
            self._set_active_color(color)
        index = self._palette_panel.selected_index()
        if index is not None:
            self._set_active_index(index)

    def _on_color_picked(self, color: RGBA) -> None:
        self._set_active_color(color)
        self._palette_panel.select_color(color)

    def _set_active_color(self, color: RGBA) -> None:
        self._active_color = color
        record = self.active_tab()
        if record is not None:
            record.view.set_active_color(color)
            # Keep the paint-by-index value aligned when the colour is an exact
            # palette entry (e.g. a hub/ramp pick that matches, REQ-P3-UI-014).
            index = record.document.palette.index_of(color)
            if index is not None:
                self._set_active_index(index)
        self._palette_editor.set_active_color(color)
        self._ramp_picker.set_base_color(color)

    def _set_active_index(self, index: int) -> None:
        """Set the paint-by-index value and push it to every view (P3-UI-014)."""
        self._active_index = int(index)
        for record in self._tabs_data:
            record.view.set_active_index(self._active_index)

    # -- layer panel (REQ-P4-UI-001, -009) -------------------------------

    def _on_active_node_changed(self, node: object) -> None:
        """The layer panel selected a node → retarget paint at the active leaf.

        A leaf :class:`Layer` becomes the scene's paint/transform target; a group
        selection leaves the paint target unchanged (groups hold no pixels)."""
        record = self.active_tab()
        if record is None:
            return
        if isinstance(node, Layer):
            record.scene.set_active_layer(node)

    def _on_mask_edit_toggled(self, enabled: bool) -> None:
        """Route paint to the active layer's mask buffer when editing a mask
        (REQ-P4-UI-009); the canvas recomposites with the mask modulating alpha."""
        record = self.active_tab()
        if record is not None:
            record.scene.set_mask_edit(enabled)

    # -- palette workflows (REQ-P3-UI-001/-007..-013) --------------------

    def _on_palette_selected_rgba(self, color: RGBA) -> None:
        """A pick in the editor list sets the active colour."""
        self._set_active_color(color)
        self._palette_panel.select_color(color)

    def _on_dither_mode_changed(self, _index: int) -> None:
        self._dither_tool.set_mode(self._dither_mode_combo.currentData())

    def _on_palette_edited(self) -> None:
        """Refresh every palette surface after an editor mutation / undo / redo."""
        record = self.active_tab()
        if record is None:
            return
        palette = record.document.palette
        self._palette_panel.set_palette(palette)
        self._cycling_panel.set_palette(palette)
        self._dither_tool.set_palette(palette)
        record.scene.set_display_palette(palette.colors())
        # Lazy: defer the buffer scan unless the analytics dock is visible.
        self._analytics_view.request_refresh()

    def _on_ramp_picked(self, color: RGBA) -> None:
        """A ramp swatch applies to the active colour (REQ-P3-UI-007)."""
        self._set_active_color(color)
        self._palette_panel.select_color(color)

    def _on_ramp_added(self, colors: List[RGBA]) -> None:
        """Append a whole ramp to the palette as one command (REQ-P3-UI-007)."""
        record = self.active_tab()
        if record is None:
            return
        self._palette_editor.replace_all(
            record.document.palette.colors() + list(colors), self.tr("Add Shade Ramp")
        )

    def _on_constrain(self, preset: str) -> None:
        """Constrain the buffer/selection onto a hardware palette (REQ-P3-UI-009)."""
        record = self.active_tab()
        if record is None:
            return
        palette = preset_palette(preset)
        if palette is None:
            return
        buffer = record.scene.active_buffer()
        mask = record.view.active_selection()
        try:
            command = make_constraint_command(buffer, palette, mask=mask)
        except (QuantizeError, PaletteError) as exc:
            QMessageBox.warning(self, self.tr("Constrain to Palette"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command, record.scene.refresh_all, self.tr("Constrain to Palette")
            )
        )

    def _on_cycle_preview(self, colors: List[RGBA]) -> None:
        """Show a cycled display palette without mutating pixels (REQ-P3-UI-012)."""
        record = self.active_tab()
        if record is not None:
            record.scene.set_display_palette(colors)

    def _on_cycle_apply(self, start: int, end: int, step: int) -> None:
        """Commit a colour-cycle state to the buffer as one command (REQ-P3-UI-012)."""
        record = self.active_tab()
        if record is None:
            return
        buffer = record.scene.active_buffer()
        if buffer.mode is not ColorMode.INDEXED:
            QMessageBox.warning(
                self,
                self.tr("Colour Cycling"),
                self.tr("Colour cycling applies to indexed documents."),
            )
            return
        try:
            command = make_cycle_command(buffer, start, end, step)
        except PaletteError as exc:
            QMessageBox.warning(self, self.tr("Colour Cycling"), str(exc))
            return
        record.stack.push(
            LogicCommand(command, record.scene.refresh_all, self.tr("Colour Cycle"))
        )
        record.scene.set_display_palette(record.document.palette.colors())

    def _on_extract_palette(self) -> None:
        """Extract a ≤N palette from an image into the editor (REQ-P3-UI-010)."""
        record = self.active_tab()
        if record is None:
            return
        dialog = Extract_Palette_Dialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        palette = dialog.result_palette()
        if palette is None:
            return
        self._palette_editor.replace_all(palette.colors(), self.tr("Extract Palette"))

    def _on_palette_swap(self) -> None:
        """Define + apply an index remap as one command (REQ-P3-UI-013)."""
        record = self.active_tab()
        if record is None:
            return
        buffer = record.scene.active_buffer()
        if buffer.mode is not ColorMode.INDEXED:
            QMessageBox.warning(
                self,
                self.tr("Palette Swap"),
                self.tr("Palette swap applies to indexed documents."),
            )
            return
        dialog = Palette_Swap_Dialog(max(0, len(record.document.palette) - 1), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        mapping = dialog.mapping()
        if not mapping:
            return
        try:
            command = make_swap_command(buffer, mapping, record.view.active_selection())
        except PaletteError as exc:
            QMessageBox.warning(self, self.tr("Palette Swap"), str(exc))
            return
        record.stack.push(
            LogicCommand(command, record.scene.refresh_all, self.tr("Palette Swap"))
        )

    # -- indexed-mode conversion (REQ-P3-UI-014, T22) --------------------

    def _on_convert_to_indexed(self) -> None:
        """Convert the whole document RGBA→indexed as one undoable command (T22).

        Colour mode is a document-wide authority (ADR-0008 D1/D5): the logic
        command flips every frame's buffer(s) **and** ``Document.mode`` together,
        collapsing each frame to a single indexed layer (D4 flatten-then-index).
        Exactly one command is pushed onto the tab's undo stack.
        """
        record = self.active_tab()
        if record is None:
            return
        palette = record.document.palette
        try:
            command = record.document.make_convert_to_indexed_command(palette)
        except (DocumentError, IndexedModeError, PaletteError) as exc:
            QMessageBox.warning(self, self.tr("Convert to Indexed"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command,
                self._mode_switch_rebind(record),
                self.tr("Convert to Indexed"),
            )
        )

    def _on_convert_to_rgba(self) -> None:
        """Convert the whole document indexed→RGBA as one undoable command (T22).

        The inverse of :meth:`_on_convert_to_indexed`: the logic command flips
        every frame's single indexed layer to RGBA **and** ``Document.mode`` in one
        step (ADR-0008 D4). Exactly one command is pushed onto the undo stack.
        """
        record = self.active_tab()
        if record is None:
            return
        palette = record.document.palette
        try:
            command = record.document.make_convert_to_rgba_command(palette)
        except (DocumentError, IndexedModeError, PaletteError) as exc:
            QMessageBox.warning(self, self.tr("Convert to RGBA"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command, self._mode_switch_rebind(record), self.tr("Convert to RGBA")
            )
        )

    def _mode_switch_rebind(self, record: "_DocTab") -> Callable[[], None]:
        """Rebind callback for a whole-document colour-mode switch (ADR-0008 D4/D5).

        A mode conversion changes the document's **tree shape** (it collapses to a
        single indexed layer on →indexed, and undo restores the full multi-layer
        RGBA tree), so a narrow ``rebind_active()`` buffer re-point is not enough.
        This does a **full document re-bind + layer-panel repopulate**:

        - ``scene.set_document`` re-reads the tree, resets the active leaf and
          rebuilds the composite off ``Document.mode`` (now the single authority) —
          so on →indexed the RGBA-only compositor is not run over indexed buffers
          (the T14 crash path is gone);
        - ``layer_panel.rebuild`` repopulates the tree so the panel collapses to one
          layer on →indexed and re-expands the multi-layer tree on undo→RGBA;
        - the selection is dropped (indices/structure changed) and the mode
          indicator + convert-action states refresh.

        Runs on apply, undo and redo so the UI always mirrors ``Document.mode``.
        """

        def rebind() -> None:
            record.scene.set_document(record.document)
            self._layer_panel.rebuild()
            record.view.clear_selection()
            self._refresh_mode_ui()

        return rebind

    def _refresh_mode_ui(self) -> None:
        """Sync the mode indicator + convert-action enablement to ``Document.mode``.

        Reads the document-level mode — the single colour-mode authority
        (ADR-0008 D5) — rather than a per-buffer ``active_buffer().mode``.
        """
        record = self.active_tab()
        if record is None:
            self._to_indexed_action.setEnabled(False)
            self._to_rgba_action.setEnabled(False)
            return
        mode = record.document.mode
        self._palette_panel.set_mode(mode)
        self._to_indexed_action.setEnabled(mode is ColorMode.RGBA)
        self._to_rgba_action.setEnabled(mode is ColorMode.INDEXED)

    # -- colour hub (REQ-P3-UI-003/-004/-006) ----------------------------

    def _favourites_path(self) -> Path:
        """Return the app-level Favourites store path (QStandardPaths, ADR-0004).

        The app-config directory is resolved here in ``ui/`` and passed to the
        Qt-free ``data/favourites_io`` layer, keeping ``data/`` free of Qt.
        """
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppConfigLocation
        )
        directory = Path(base) if base else Path.home() / ".pixelart_creator"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / _FAVOURITES_FILE

    def _load_favourites(self):
        """Load the persisted Favourites (empty on first run or on error)."""
        try:
            return load_favourites(self._favourites_path())
        except (FavouritesIOError, OSError):
            from pixelart_creator.logic.favourites import Favourites

            return Favourites()

    def _save_favourites(self) -> None:
        """Persist the Favourites model after an add / remove / reorder."""
        try:
            save_favourites(self._favourites_path(), self._favourites)
        except (FavouritesIOError, OSError):
            pass  # a non-writable config dir must not crash the editor.

    def _open_colour_hub(self, x: int, y: int) -> None:
        """Seam hook: open the hub anchored at buffer pixel ``(x, y)`` (SC-U003-1).

        Anchoring off the buffer pixel (mapped through the active view) — rather
        than the mouse cursor — makes the hub open in the right place for BOTH a
        right-click and a keyboard Menu-key request (A11Y-COLHUB-1)."""
        self._colour_hub.set_color(self._active_color)
        record = self.active_tab()
        if record is not None:
            global_pos = record.view.scene_pixel_to_global(x, y)
        else:
            global_pos = QCursor.pos()
        self._colour_hub.popup_at(global_pos)

    def _on_hub_color_applied(self, color: RGBA) -> None:
        """A hub pick applies immediately to the active swatch (SC-U006-1)."""
        self._set_active_color(color)
        self._palette_panel.select_color(color)

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Project"),
            "",
            self.tr("Pixel projects (*%1)").replace("%1", FILE_SUFFIX),
        )
        if path:
            self.open_document(path)

    def _on_save(self) -> None:
        self._on_save_as()

    def _on_save_as(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Project"),
            "",
            self.tr("Pixel projects (*%1)").replace("%1", FILE_SUFFIX),
        )
        if path:
            self.save_document(path)

    def _on_zoom_in(self) -> None:
        record = self.active_tab()
        if record is not None:
            record.view.zoom_in()

    def _on_zoom_out(self) -> None:
        record = self.active_tab()
        if record is not None:
            record.view.zoom_out()

    def _on_fit(self) -> None:
        record = self.active_tab()
        if record is not None:
            record.view.fit()

    def _on_grid_toggled(self, enabled: bool) -> None:
        for record in self._tabs_data:
            record.view.set_grid_enabled(enabled)

    def _on_snap_toggled(self, enabled: bool) -> None:
        self._snap = bool(enabled)
        for record in self._tabs_data:
            record.view.set_snap_enabled(enabled)

    def _on_aa_off_toggled(self, enabled: bool) -> None:
        # The AA-off guarantee is locked on (CL-15); refuse to disable it.
        if not enabled:
            self._aa_off_action.setChecked(True)
            return
        for record in self._tabs_data:
            record.view.reassert_no_antialiasing()

    def _on_filled_toggled(self, enabled: bool) -> None:
        self._rectangle_tool.set_filled(enabled)
        self._ellipse_tool.set_filled(enabled)

    def _on_pixel_perfect_toggled(self, enabled: bool) -> None:
        self._pixel_perfect = bool(enabled)
        for record in self._tabs_data:
            record.view.set_pixel_perfect(enabled)

    def _on_tiled_toggled(self, enabled: bool) -> None:
        self._tiled = bool(enabled)
        for record in self._tabs_data:
            set_tiled_mode(record.scene, record.view, enabled)

    def _on_tolerance_changed(self, value: int) -> None:
        self._wand_tool.set_tolerance(value)

    def _on_symmetry_axis_changed(self, axis: SymmetryAxis) -> None:
        self._symmetry_axis = axis
        for record in self._tabs_data:
            record.view.set_symmetry_axis(axis)

    # -- selection-op actions (REQ-P2-UI-008) ----------------------------

    def _on_select_all(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        buffer = record.scene.active_buffer()
        mask = rect_mask(
            buffer.width, buffer.height, 0, 0, buffer.width - 1, buffer.height - 1
        )
        record.view.set_selection(mask)

    def _on_deselect(self) -> None:
        record = self.active_tab()
        if record is not None:
            record.view.clear_selection()

    def _on_invert_selection(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        buffer = record.scene.active_buffer()
        current = record.view.active_selection()
        base = (
            current
            if current is not None
            else SelectionMask(buffer.width, buffer.height)
        )
        inverted = base.invert()
        record.view.set_selection(inverted if not inverted.is_empty else None)

    def _on_clear_selection(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        mask = record.view.active_selection()
        if mask is None or mask.is_empty:
            return
        buffer = record.scene.active_buffer()
        box = mask.bounds()
        if box is None:
            return
        x0, y0, x1, y1 = box
        blank = TRANSPARENT if buffer.mode is ColorMode.RGBA else 0

        def clear_op(scratch: PixelBuffer) -> List[tuple[int, int]]:
            scratch.fill_rect(x0, y0, x1 - x0 + 1, y1 - y0 + 1, blank)
            return [
                (x, y)
                for y in range(y0, y1 + 1)
                for x in range(x0, x1 + 1)
                if mask.is_selected(x, y)
            ]

        label = self.tr("Clear Selection")
        edit = history.record_edit(
            buffer, lambda b: apply_masked(b, clear_op, mask), label=label
        )
        dirty = QRectF(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        record.stack.push(
            PaintCommand(
                edit,
                record.scene.refresh_rect,
                dirty,
                text=label,
                invalidate=record.scene.invalidate_group_caches,
            )
        )

    # -- transform + RotSprite actions (REQ-P2-UI-009, -010) -------------

    def _apply_buffer_command(
        self, command: history.Command, dims_change: bool, text: str
    ) -> None:
        record = self.active_tab()
        if record is None:
            return
        if dims_change:

            def rebind() -> None:
                record.scene.rebind_active()
                record.view.clear_selection()

            record.stack.push(LogicCommand(command, rebind, text))
        else:
            record.stack.push(LogicCommand(command, record.scene.refresh_all, text))

    def _apply_transform(
        self, fn: Callable[[PixelBuffer], PixelBuffer], text: str
    ) -> None:
        record = self.active_tab()
        if record is None:
            return
        layer: Layer = record.scene.active_layer()
        mask = record.view.active_selection()
        command = transform.make_transform_command(layer, fn, mask)
        dims_change = isinstance(command, history.FunctionCommand)
        self._apply_buffer_command(command, dims_change, text)

    def _on_flip_horizontal(self) -> None:
        self._apply_transform(transform.flip_horizontal, self.tr("Flip Horizontal"))

    def _on_flip_vertical(self) -> None:
        self._apply_transform(transform.flip_vertical, self.tr("Flip Vertical"))

    def _on_rotate_cw(self) -> None:
        self._apply_transform(transform.rotate_90_cw, self.tr("Rotate 90° CW"))

    def _on_rotate_ccw(self) -> None:
        self._apply_transform(transform.rotate_90_ccw, self.tr("Rotate 90° CCW"))

    def _on_scale(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        dialog = Scale_Dialog(record.document.width, record.document.height, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_w, new_h = dialog.target_size()
        layer: Layer = record.scene.active_layer()

        def fn(buffer: PixelBuffer) -> PixelBuffer:
            return scale_nearest(buffer, new_w, new_h)

        try:
            command = transform.make_transform_command(layer, fn, None)
        except TransformError as exc:
            QMessageBox.warning(self, self.tr("Scale Canvas"), str(exc))
            return
        dims_change = isinstance(command, history.FunctionCommand)
        self._apply_buffer_command(command, dims_change, self.tr("Scale Canvas"))

    def _on_rotsprite(self) -> None:
        record = self.active_tab()
        if record is None:
            return
        dialog = RotSprite_Dialog(self._rotsprite_preview, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        angle = dialog.angle()
        layer: Layer = record.scene.active_layer()
        mask = record.view.active_selection()
        command = make_rotsprite_command(layer, angle, mask)
        dims_change = isinstance(command, history.FunctionCommand)
        self._apply_buffer_command(command, dims_change, self.tr("Rotate (RotSprite)"))

    # -- RotSprite preview rendering (presentation of a logic result) ----

    def _rotsprite_preview(self, angle: float) -> Optional[QImage]:
        record = self.active_tab()
        if record is None:
            return None
        thumbnail = self._preview_thumbnail(record.scene.active_buffer())
        rotated = rotsprite(thumbnail, angle)
        return self._buffer_to_qimage(rotated, record.document.palette.colors())

    @staticmethod
    def _preview_thumbnail(buffer: PixelBuffer) -> PixelBuffer:
        """Down-scale a buffer to a small preview thumbnail (nearest-neighbour)."""
        max_edge = 128
        longest = max(buffer.width, buffer.height)
        if longest <= max_edge:
            return buffer
        factor = max_edge / longest
        tw = max(1, int(buffer.width * factor))
        th = max(1, int(buffer.height * factor))
        return scale_nearest(buffer, tw, th)

    @staticmethod
    def _buffer_to_qimage(buffer: PixelBuffer, palette_colors: List[RGBA]) -> QImage:
        """Convert a buffer to an owned RGBA :class:`QImage` for preview display."""
        if buffer.mode is ColorMode.RGBA:
            rgba = np.ascontiguousarray(buffer.data)
        else:
            lut = np.array(palette_colors or [(0, 0, 0, 255)], dtype=np.uint8)
            idx = np.clip(buffer.data, 0, len(lut) - 1)
            rgba = np.ascontiguousarray(lut[idx])
        image = QImage(
            rgba.data,
            buffer.width,
            buffer.height,
            rgba.strides[0],
            QImage.Format.Format_RGBA8888,
        )
        return image.copy()

    def _on_language_action(self) -> None:
        action = self.sender()
        if isinstance(action, QAction):
            self._language_manager.set_language(action.data())

    # -- theme ------------------------------------------------------------

    def set_theme(self, name: str) -> None:
        """Switch the theme at runtime and repaint canvas roles (025)."""
        self._theme = name
        apply_theme(self._app, name)
        for record in self._tabs_data:
            self._apply_theme_to_scene(record.scene)

    def _apply_theme_to_scene(self, scene: CanvasScene) -> None:
        checker_light, checker_dark, grid = canvas_roles(self._theme)
        scene.set_background_roles(checker_light, checker_dark, grid)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("PixelArt Creator"))
        self._toolbar.setWindowTitle(self.tr("Tools"))
        self._palette_dock.setWindowTitle(self.tr("Palette"))
        self._symmetry_dock.setWindowTitle(self.tr("Symmetry"))
        self._layer_dock.setWindowTitle(self.tr("Layers"))
        self._editor_dock.setWindowTitle(self.tr("Palette Editor"))
        self._constraint_dock.setWindowTitle(self.tr("Constraints"))
        self._ramp_dock.setWindowTitle(self.tr("Shade Ramps"))
        self._cycling_dock.setWindowTitle(self.tr("Colour Cycling"))
        self._analytics_dock.setWindowTitle(self.tr("Analytics"))
        self._tab_widget.setAccessibleName(self.tr("Open documents"))

        labels = {
            PencilTool.tool_id: self.tr("Pencil"),
            EraserTool.tool_id: self.tr("Eraser"),
            FloodFillTool.tool_id: self.tr("Fill"),
            LineTool.tool_id: self.tr("Line"),
            PickerTool.tool_id: self.tr("Colour picker"),
            RectangleTool.tool_id: self.tr("Rectangle"),
            EllipseTool.tool_id: self.tr("Ellipse"),
            RectSelectTool.tool_id: self.tr("Rectangle select"),
            LassoTool.tool_id: self.tr("Lasso select"),
            MagicWandTool.tool_id: self.tr("Magic wand"),
            DitherTool.tool_id: self.tr("Dither"),
        }
        for tool_id, action in self._tool_actions.items():
            label = labels[tool_id]
            action.setText(label)
            # Surface the assigned key in the tooltip so it is discoverable.
            shortcut = action.shortcut().toString()
            action.setToolTip(f"{label} ({shortcut})" if shortcut else label)

        self._new_action.setText(self.tr("&New"))
        self._open_action.setText(self.tr("&Open…"))
        self._save_action.setText(self.tr("&Save"))
        self._save_as_action.setText(self.tr("Save &As…"))
        self._close_action.setText(self.tr("&Close"))
        self._zoom_in_action.setText(self.tr("Zoom &In"))
        self._zoom_out_action.setText(self.tr("Zoom &Out"))
        self._fit_action.setText(self.tr("&Fit to View"))
        self._grid_action.setText(self.tr("Show &Grid"))
        self._snap_action.setText(self.tr("&Snap to Grid"))
        self._aa_off_action.setText(self.tr("&Anti-aliasing Off"))
        self._tiled_action.setText(self.tr("&Tiled Mode"))
        self._theme_light_action.setText(self.tr("Light"))
        self._theme_dark_action.setText(self.tr("Dark"))

        # Mnemonics make the drawing-mode toggles keyboard-reachable (A11Y-P2-1);
        # letters are disjoint from the other View-menu entries.
        self._filled_action.setText(self.tr("Fille&d Shapes"))
        self._pixel_perfect_action.setText(self.tr("&Pixel Perfect"))
        self._tolerance_label.setText(self.tr("Tolerance"))
        self._tolerance_spin.setAccessibleName(self.tr("Magic-wand tolerance"))
        self._dither_mode_label.setText(self.tr("Dither"))
        self._dither_mode_combo.setAccessibleName(self.tr("Dither mode"))
        self._dither_mode_combo.setItemText(0, self.tr("Ordered (Bayer)"))
        self._dither_mode_combo.setItemText(1, self.tr("Floyd–Steinberg"))
        self._extract_action.setText(self.tr("&Extract from Image…"))
        self._swap_action.setText(self.tr("Palette &Swap…"))
        # Mnemonics X / C are unique within the &Palette menu; no global shortcut.
        self._to_indexed_action.setText(self.tr("Convert to Inde&xed"))
        self._to_rgba_action.setText(self.tr("&Convert to RGBA"))

        self._select_all_action.setText(self.tr("Select &All"))
        self._deselect_action.setText(self.tr("&Deselect"))
        self._invert_action.setText(self.tr("&Invert Selection"))
        self._clear_action.setText(self.tr("&Clear Selection"))

        self._flip_h_action.setText(self.tr("Flip &Horizontal"))
        self._flip_v_action.setText(self.tr("Flip &Vertical"))
        self._rotate_cw_action.setText(self.tr("Rotate 90° C&W"))
        self._rotate_ccw_action.setText(self.tr("Rotate 90° CC&W"))
        self._scale_action.setText(self.tr("&Scale…"))
        self._rotsprite_action.setText(self.tr("&Rotate (RotSprite)…"))

        self._file_menu.setTitle(self.tr("&File"))
        self._edit_menu.setTitle(self.tr("&Edit"))
        self._select_menu.setTitle(self.tr("&Select"))
        self._image_menu.setTitle(self.tr("&Image"))
        self._view_menu.setTitle(self.tr("&View"))
        self._palette_menu.setTitle(self.tr("&Palette"))
        self._theme_menu.setTitle(self.tr("&Theme"))
        self._language_menu.setTitle(self.tr("&Language"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
