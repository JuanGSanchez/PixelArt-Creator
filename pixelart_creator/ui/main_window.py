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
from typing import List, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QIcon,
    QKeySequence,
    QPixmap,
    QUndoGroup,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QTabWidget,
    QToolBar,
    QWidget,
)

from pixelart_creator.data.project_io import (
    FILE_SUFFIX,
    load_project,
    save_project,
)
from pixelart_creator.logic.color import BLACK, RGBA, to_hex
from pixelart_creator.logic.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.i18n import LanguageManager
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.tools import (
    EraserTool,
    FloodFillTool,
    LineTool,
    PencilTool,
    PickerTool,
    Tool,
)

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
        """Build an empty single-select swatch list."""
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)
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
        self._theme = THEME_LIGHT

        self._tools: dict[str, Tool] = {
            PencilTool.tool_id: PencilTool(),
            EraserTool.tool_id: EraserTool(),
            FloodFillTool.tool_id: FloodFillTool(),
            LineTool.tool_id: LineTool(),
            PickerTool.tool_id: PickerTool(),
        }
        self._active_tool_id = PencilTool.tool_id

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

        self._build_actions()
        self._build_toolbar()
        self._build_menu()

        apply_theme(self._app, self._theme)
        self._language_manager.install_from_locale()

        self.new_document()
        self._retranslate()

    # -- actions / toolbar / menu ----------------------------------------

    def _build_actions(self) -> None:
        # Aseprite-conventional single-key tool shortcuts (REQ-P1-UI-024).
        tool_shortcuts = {
            PencilTool.tool_id: "B",
            EraserTool.tool_id: "E",
            FloodFillTool.tool_id: "G",
            LineTool.tool_id: "L",
            PickerTool.tool_id: "I",
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

        self._view_menu = bar.addMenu("")
        self._view_menu.addAction(self._zoom_in_action)
        self._view_menu.addAction(self._zoom_out_action)
        self._view_menu.addAction(self._fit_action)
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._grid_action)

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
        record = _DocTab(document, scene, view, stack)
        self._tabs_data.append(record)
        index = self._tab_widget.addTab(view, title)
        self._tab_widget.setCurrentIndex(index)
        self._apply_theme_to_scene(scene)
        view.set_tool(self._tools[self._active_tool_id])
        view.set_active_color(self._active_color)
        self._palette_panel.set_palette(document.palette)
        return document

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
        self._palette_panel.set_palette(record.document.palette)

    def _on_tool_action(self) -> None:
        action = self.sender()
        if isinstance(action, QAction):
            self._active_tool_id = action.data()
            record = self.active_tab()
            if record is not None:
                record.view.set_tool(self._tools[self._active_tool_id])

    def _on_palette_selected(self) -> None:
        color = self._palette_panel.selected_color()
        if color is not None:
            self._set_active_color(color)

    def _on_color_picked(self, color: RGBA) -> None:
        self._set_active_color(color)
        self._palette_panel.select_color(color)

    def _set_active_color(self, color: RGBA) -> None:
        self._active_color = color
        record = self.active_tab()
        if record is not None:
            record.view.set_active_color(color)

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
        record = self.active_tab()
        if record is not None:
            record.view.set_grid_enabled(enabled)

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
        self._tab_widget.setAccessibleName(self.tr("Open documents"))

        labels = {
            PencilTool.tool_id: self.tr("Pencil"),
            EraserTool.tool_id: self.tr("Eraser"),
            FloodFillTool.tool_id: self.tr("Fill"),
            LineTool.tool_id: self.tr("Line"),
            PickerTool.tool_id: self.tr("Colour picker"),
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
        self._theme_light_action.setText(self.tr("Light"))
        self._theme_dark_action.setText(self.tr("Dark"))

        self._file_menu.setTitle(self.tr("&File"))
        self._edit_menu.setTitle(self.tr("&Edit"))
        self._view_menu.setTitle(self.tr("&View"))
        self._theme_menu.setTitle(self.tr("&Theme"))
        self._language_menu.setTitle(self.tr("&Language"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
