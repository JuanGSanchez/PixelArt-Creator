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
from typing import Callable, List, Optional, Sequence, Tuple, cast

import numpy as np
from PySide6.QtCore import QEvent, QRectF, QStandardPaths, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QColor,
    QCursor,
    QDragEnterEvent,
    QDropEvent,
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
    QGraphicsScene,
    QGridLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.asset_cas import default_content_store
from pixelart_creator.data.asset_revision_store import AssetRevisionStore
from pixelart_creator.data.asset_storage import default_asset_root
from pixelart_creator.data.favourites_io import (
    FavouritesIOError,
    load_favourites,
    save_favourites,
)
from pixelart_creator.data.file_import import (
    FileImportError,
    FileType,
    ImageImportError,
    classify,
)
from pixelart_creator.data.palette_import import load_palette
from pixelart_creator.data.project_io import (
    FILE_SUFFIX,
    ProjectIOError,
    load_project,
    save_project,
)
from pixelart_creator.logic import history, transform
from pixelart_creator.logic.assistant import ChatBackend
from pixelart_creator.logic.autosave import should_autosave
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.branch_diff import SupervisionResult, supervise
from pixelart_creator.logic.color import BLACK, RGBA, TRANSPARENT, to_hex
from pixelart_creator.logic.constants import (
    AUTOSAVE_INTERVAL_MS,
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    UI_NOTICE_DURATION_MS,
)
from pixelart_creator.logic.document import Document, DocumentError, Layer, iter_layers
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.grids import (
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
)
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Macro, Op
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.palette_ops import (
    IndexedModeError,
    make_cycle_command,
    make_swap_command,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import QuantizeError, make_constraint_command
from pixelart_creator.logic.realtime_apply import RealtimeError
from pixelart_creator.logic.rotsprite import make_rotsprite_command, rotsprite
from pixelart_creator.logic.selection import (
    SelectionMask,
    apply_masked,
    rect_mask,
)
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.logic.sync_state import SyncState, compute_sync_state
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.logic.tileset import Tileset, TilesetError
from pixelart_creator.logic.transform import (
    TransformError,
    scale_nearest,
)
from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import Asset_Library_Panel
from pixelart_creator.ui.asset_reuse_panel import Asset_Reuse_Panel
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel
from pixelart_creator.ui.asset_version_browser import Asset_Version_Browser
from pixelart_creator.ui.assistant_dock import Assistant_Dock
from pixelart_creator.ui.assistant_worker import Assistant_Controller
from pixelart_creator.ui.automation_worker import (
    Automation_Controller,
    make_dispatch_job,
    make_replay_job,
)
from pixelart_creator.ui.batch_export_panel import Batch_Export_Panel
from pixelart_creator.ui.batch_recolour_panel import Batch_Recolour_Panel
from pixelart_creator.ui.branch_diff_dialog import Branch_Diff_Dialog
from pixelart_creator.ui.branching_panel import Branching_Panel, Branching_Session
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.cloud_actions import (
    Cloud_Session,
    make_autosave_job,
    make_list_versions_job,
    make_recover_job,
    make_restore_job,
    make_save_job,
)
from pixelart_creator.ui.cloud_worker import Cloud_Controller
from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.colour_cycling_panel import Colour_Cycling_Panel
from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
from pixelart_creator.ui.commands import (
    AssistantCommand,
    AutomationCommand,
    LogicCommand,
    PaintCommand,
    TilemapCommand,
    TilesetCommand,
)
from pixelart_creator.ui.comments_panel import Comments_Panel
from pixelart_creator.ui.dependency_graph_view import Dependency_Graph_View
from pixelart_creator.ui.export_actions import run_export_dialog
from pixelart_creator.ui.export_worker import Export_Controller
from pixelart_creator.ui.extract_palette_dialog import Extract_Palette_Dialog
from pixelart_creator.ui.frame_tags_panel import Frame_Tags_Panel
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from pixelart_creator.ui.i18n import LanguageManager
from pixelart_creator.ui.image_import import decode_image
from pixelart_creator.ui.iso_grid_dialog import Iso_Grid_Dialog
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay
from pixelart_creator.ui.layer_panel import Layer_Panel
from pixelart_creator.ui.live_cursors_overlay import Live_Cursors_Overlay
from pixelart_creator.ui.macro_controls import Macro_Controls
from pixelart_creator.ui.multi_view import Multi_View
from pixelart_creator.ui.onion_skin_controls import Onion_Skin_Controls, OnionSettings
from pixelart_creator.ui.palette_analytics_view import Palette_Analytics_View
from pixelart_creator.ui.palette_constraint_panel import (
    Palette_Constraint_Panel,
    preset_palette,
)
from pixelart_creator.ui.palette_editor_panel import Palette_Editor_Panel
from pixelart_creator.ui.palette_swap_dialog import Palette_Swap_Dialog
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.playback_controls import Playback_Controls
from pixelart_creator.ui.plugin_manager_panel import Plugin_Manager_Panel
from pixelart_creator.ui.presence_panel import Presence_Panel
from pixelart_creator.ui.prewarm_indicator import Prewarm_Indicator
from pixelart_creator.ui.procgen_panel import Procgen_Panel
from pixelart_creator.ui.project_prefs_actions import build_project_prefs_menu
from pixelart_creator.ui.provider_config_dialog import (
    build_backend,
    load_config,
)
from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from pixelart_creator.ui.realtime_actions import Realtime_Session
from pixelart_creator.ui.recovery_prompt import Recovery_Prompt
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog
from pixelart_creator.ui.script_runner_panel import Script_Runner_Panel
from pixelart_creator.ui.shade_ramp_picker import Shade_Ramp_Picker
from pixelart_creator.ui.shared_projects_panel import Shared_Projects_Panel
from pixelart_creator.ui.symmetry_panel import Symmetry_Panel
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    apply_font_fallbacks,
    apply_theme,
    canvas_roles,
)
from pixelart_creator.ui.tiled_mode import set_tiled_mode
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas, TilemapTool
from pixelart_creator.ui.tilemap_io_actions import (
    export_tilemap_dialog,
    import_tilemap_dialog,
)
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel
from pixelart_creator.ui.tileset_editor_panel import Tileset_Editor_Panel
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from pixelart_creator.ui.timelapse_frame_view import Timelapse_Frame_View
from pixelart_creator.ui.timeline_panel import Timeline_Panel
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
from pixelart_creator.ui.user_guide import User_Guide_Dialog
from pixelart_creator.ui.vanishing_point_dialog import Vanishing_Point_Dialog
from pixelart_creator.ui.version_history_browser import Version_History_Browser

#: Stable cloud recovery-slot key for the working document when no named cloud
#: project is active (presentation-only identifier, not a domain tuning value).
_RECOVERY_PROJECT_ID = "working"

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

#: Longest edge of a RotSprite preview thumbnail, px (presentation-only sizing,
#: not a domain tuning value — cf. _SWATCH_PX).
_PREVIEW_MAX_EDGE_PX = 128


@dataclass
class _DocTab:
    """Per-tab editing context bound to one open document."""

    document: Document
    scene: CanvasScene
    view: Canvas_View
    stack: QUndoStack
    # Phase-9 per-tab visual aids (non-destructive view state; created with the
    # tab, toggled from the Aids menu). ``None`` until the aids are attached.
    guides_rulers: Optional[Guides_Rulers_Overlay] = None
    iso_overlay: Optional[Iso_Grid_Overlay] = None
    # Phase-10 Slice C: the ephemeral live-cursor overlay for this tab's scene
    # (other collaborators' cursors; never persisted). ``None`` until aids attach.
    live_cursors: Optional[Live_Cursors_Overlay] = None
    perspective_overlay: Optional[Perspective_Grid_Overlay] = None
    # D-13: the remote CloudVersion.version_id this tab's document was last saved
    # to / restored from, or None if it has no remote lineage yet. Feeds the
    # read-only, Qt-free ``compute_sync_state`` for the Cloud menu / version
    # browser status line — never computed here.
    local_version_id: Optional[str] = None


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
        palette index (the paint-by-index value for an indexed buffer).
        """
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
        """Re-translate the palette-panel strings on a language change (F5)."""
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
        # Floating move/copy status (REQ-P2-UI-032/-036): the last view-reported
        # float state, surfaced as a status-bar hint (see _update_float_hint).
        self._active_view: Optional[Canvas_View] = None
        self._float_active = False
        self._float_copy = False
        # In-app User Guide (REQ-UG-UI-001..011): a read-only, offline viewer built
        # lazily on first open. Content loads synchronously from the committed
        # bundle — NO off-thread worker/timer — so there is no teardown wiring; the
        # dialog is parented to this window, so it is disposed with it.
        self._user_guide_dialog: Optional[User_Guide_Dialog] = None

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
        #: Live mirror-centre override from the Symmetry_Panel (D-28/CF-93);
        #: ``None`` keeps the shipped canvas-centre default.
        self._symmetry_axis_pos: Optional[Tuple[int, int]] = None
        self._pixel_perfect = False
        self._tiled = False
        self._snap = False

        # Accept OS file-URL drops onto the window (REQ-DDI-UI-001). Drag/drop is
        # routed by file TYPE, not drop location (CL-A1) — see dropEvent /
        # _route_dropped_files. Enabled on the main window so a drop anywhere over
        # the shell reaches the router.
        self.setAcceptDrops(True)

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
        self._symmetry_panel.axisPositionChanged.connect(
            self._on_symmetry_axis_position_changed
        )
        self._symmetry_dock = QDockWidget(self)
        self._symmetry_dock.setWidget(self._symmetry_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._symmetry_dock)

        # Phase-4 layer panel (REQ-P4-UI-001..011): the layer/group tree bound to
        # the active document. Its ops push one LayerCommand each; a mutation
        # recomposites the active scene via the per-tab tree-changed hook (UI-013).
        self._layer_panel = Layer_Panel(self)
        self._layer_panel.activeNodeChanged.connect(self._on_active_node_changed)
        self._layer_panel.maskEditToggled.connect(self._on_mask_edit_toggled)
        self._layer_panel.lockedLayerEditRejected.connect(self._notify_layer_locked)
        self._layer_dock = QDockWidget(self)
        self._layer_dock.setWidget(self._layer_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._layer_dock)

        # Phase-5 animation UI (REQ-P5-UI-001..015): a bottom dock holds the
        # playback transport above the frame strip; the onion + tag panels tabify
        # with the right docks. The QTimer lives in Playback_Controls (ui/ only,
        # CL-14); every frame/tag edit is one FrameCommand; scrub/playback/onion
        # are non-undoable view state (CL-13). The per-frame composite cache +
        # FU-19 deferred switch live in CanvasScene (ADR-0011); this shell wires
        # the panels to the active tab's scene/document/undo-stack.
        self._active_frame = 0
        self._timeline_panel = Timeline_Panel(self)
        self._timeline_panel.frameSelected.connect(self._on_frame_selected)
        self._timeline_panel.frameScrubbed.connect(self._on_frame_scrubbed)
        # Grid cell surface (REQ-P5-UI-023, BF-G1): a cell selection reaches the
        # layer panel through the sibling seam ``Layer_Panel.select_layer``.
        self._timeline_panel.layerSelected.connect(self._layer_panel.select_layer)
        self._playback_controls = Playback_Controls(self)
        self._playback_controls.frameAdvanced.connect(self._on_frame_advanced)
        self._playback_controls.playbackActiveChanged.connect(self._on_playback_active)
        # Non-blocking cold-frame pre-warm indicator (D1): shown in the status bar
        # while cold frames flatten off the GUI thread; Cancel maps to Stop.
        self._prewarm_indicator = Prewarm_Indicator(self)
        self._prewarm_indicator.cancelRequested.connect(self._playback_controls.stop)
        self.statusBar().addPermanentWidget(self._prewarm_indicator)
        timeline_container = QWidget(self)
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.addWidget(self._playback_controls)
        timeline_layout.addWidget(self._timeline_panel, 1)
        self._timeline_dock = QDockWidget(self)
        self._timeline_dock.setWidget(timeline_container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._timeline_dock)

        self._onion_controls = Onion_Skin_Controls(self)
        self._onion_controls.settingsChanged.connect(self._on_onion_settings)
        self._onion_dock = self._add_workflow_dock(self._onion_controls)

        self._frame_tags_panel = Frame_Tags_Panel(self)
        self._frame_tags_panel.playTagRequested.connect(self._on_play_tag)
        self._tags_dock = self._add_workflow_dock(self._frame_tags_panel)

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

        # Phase-6 tilemap surfaces (REQ-P6-UI-001..013): the tileset editor +
        # tilemap layer panel dock on the right (tabified with the palette); the
        # tilemap canvas is a bottom dock rendering the active tilemap through the
        # frozen render_region seam. Active tileset / tilemap are per-tab view
        # state, rebound on document open + tab switch (state isolation, CL-13).
        self._active_tileset: Optional[Tileset] = None
        self._active_tilemap: Optional[Tilemap] = None
        self._tileset_editor = Tileset_Editor_Panel(self)
        self._tileset_editor.activeTileChanged.connect(self._on_tileset_tile_changed)
        self._tileset_dock = self._add_workflow_dock(self._tileset_editor)

        self._tilemap_layer_panel = Tilemap_Layer_Panel(self)
        self._tilemap_layer_panel.activeLayerChanged.connect(
            self._on_tilemap_layer_changed
        )
        self._tilemap_layer_panel.autotileToggled.connect(self._on_autotile_toggled)
        self._tilemap_layer_dock = self._add_workflow_dock(self._tilemap_layer_panel)

        self._tilemap_canvas = Tilemap_Canvas(parent=self)
        self._tilemap_canvas.autotileChanged.connect(
            self._tilemap_layer_panel.set_autotile_checked
        )
        self._tilemap_dock = QDockWidget(self)
        self._tilemap_dock.setWidget(self._tilemap_canvas)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._tilemap_dock)

        # Marquee S3/S4 colour hub: a persisted Favourites model + the cursor-
        # anchored hub, wired into each view's Phase-1 right-click seam. A pick
        # applies to the active colour (tool state) — never an undo entry (T17).
        self._favourites = self._load_favourites()
        self._colour_hub = Colour_Hub_Menu(self)
        self._colour_hub.set_favourites_model(self._favourites)
        self._colour_hub.colorApplied.connect(self._on_hub_color_applied)
        self._colour_hub.favouritesChanged.connect(self._save_favourites)

        # Copy-mode status hint for a live floating move (REQ-P2-UI-032/-036,
        # NFR-8): tr()-wrapped, shown only while a float is active. A11y: the
        # commit/cancel actions are keyboard-reachable on the focused canvas
        # (Enter/Escape); this label announces the state via its accessible name.
        self._float_hint = QLabel(self)
        self._float_hint.setVisible(False)
        self.statusBar().addPermanentWidget(self._float_hint)

        # Phase-7 export (REQ-P7-UI-001..013): a window-owned Export_Controller runs
        # the Qt-free logic/export + data/export_io engine off the GUI thread with
        # progress/cancel (UI-010); its worker continues past a failing target
        # (continue-on-failure, UI-005/-008). Export is read-only — no QUndoCommand
        # (UI-009). Its deterministic teardown is folded into shutdown_prewarm so no
        # worker/carrier survives GC (the Phase-5 xdist-segfault guard, D2/D4). This
        # window is the single place that surfaces a run's result (a QMessageBox on
        # failure); the batch panel reflects per-row progress from the same signals.
        self._export_controller = Export_Controller(self)
        self._export_controller.progress.connect(self._on_export_progress)
        self._export_controller.targetSucceeded.connect(self._on_export_target_ok)
        self._export_controller.targetFailed.connect(self._on_export_target_failed)
        self._export_controller.batchFinished.connect(self._on_export_finished)
        self._export_controller.busyChanged.connect(self._on_export_busy)
        self._export_run_failures: List[str] = []
        self._export_run_ok = 0
        self._batch_export_panel = Batch_Export_Panel(self)
        self._batch_export_panel.set_context(
            self._export_controller, self.active_document
        )
        self._batch_dock = self._add_workflow_dock(self._batch_export_panel)

        # Phase-8 automation (REQ-P8-UI-001..011): a window-owned
        # Automation_Controller runs the Qt-free scripting/macro/procgen/batch
        # engine off the GUI thread with cancel + result marshalling (UI-011); the
        # worker leaves the document unmutated and hands back one unapplied
        # reversible command, which THIS window pushes onto the active tab's undo
        # stack as one AutomationCommand — so every automation EDIT is one undoable
        # step and the observable mutation is strictly GUI-thread (UI-009). Its
        # deterministic teardown is folded into shutdown_prewarm so no worker /
        # carrier survives GC (the Phase-5 xdist-segfault guard). Recording,
        # plugin-enable/disable and selection are view state and push no command
        # (CL-8). No eval/exec is ever performed in ui/ — the panels emit inert DSL
        # ops that the trusted logic dispatcher validates against its allow-list.
        self._automation_controller = Automation_Controller(self)
        self._automation_controller.resultReady.connect(self._on_automation_result)
        self._automation_controller.failed.connect(self._on_automation_failed)
        self._automation_controller.busyChanged.connect(self._on_automation_busy)
        #: The DSL ops of the in-flight automation run (recorded into a macro on
        #: success if recording is active); ``None`` for a macro replay (a replay
        #: is not itself re-recorded).
        self._pending_automation_ops: Optional[List[Op]] = None
        self._pending_automation_label = ""
        #: True while an in-session timelapse playback holds the active tab's
        #: canvas + the shared undo/redo actions read-only (REQ-P9-UI-016);
        #: see ``_on_timelapse_playback_lock_changed``.
        self._playback_locked = False

        self._macro_controls = Macro_Controls(self)
        self._macro_controls.replayRequested.connect(self._on_replay_requested)
        # Reachable Cancel affordance (C-07): relayed straight to the controller's
        # cooperative cancel; the button itself is enabled only while busy.
        self._macro_controls.cancelRequested.connect(self._automation_controller.cancel)
        self._macro_dock = self._add_workflow_dock(self._macro_controls)
        self._script_runner_panel = Script_Runner_Panel(self)
        self._script_runner_panel.automationRequested.connect(self._run_automation_ops)
        self._script_dock = self._add_workflow_dock(self._script_runner_panel)
        self._plugin_manager_panel = Plugin_Manager_Panel(self)
        self._plugin_dock = self._add_workflow_dock(self._plugin_manager_panel)
        self._batch_recolour_panel = Batch_Recolour_Panel(self)
        self._batch_recolour_panel.automationRequested.connect(self._run_automation_ops)
        self._batch_recolour_dock = self._add_workflow_dock(self._batch_recolour_panel)
        self._procgen_panel = Procgen_Panel(self)
        self._procgen_panel.automationRequested.connect(self._run_automation_ops)
        self._procgen_dock = self._add_workflow_dock(self._procgen_panel)

        # Phase-14 AI assistant (REQ-P14-UI-001..004): a window-owned
        # Assistant_Controller runs the Qt-free agentic loop (logic.assistant.run_turn)
        # off the GUI thread (network + dispatch), marshalling the tiered-safety
        # confirmation to the GUI thread and leaving the live document byte-identical;
        # THIS window pushes the turn's commands onto the active tab's undo stack as
        # one AssistantCommand (the observable mutation is strictly GUI-thread, UI-004).
        # The dock drives the loop through an injected data/llm backend built from the
        # persisted, provider-agnostic config — ui/ never names a provider or holds a
        # key (REQ-P14-DATA-007). Deterministic teardown is folded into
        # shutdown_prewarm so no worker / carrier survives GC (the xdist-segfault
        # guard). No eval/exec: model output is data mapped onto the trusted dispatch.
        self._assistant_controller = Assistant_Controller(self)
        self._assistant_dock_widget = Assistant_Dock(
            self._assistant_controller,
            self.active_document,
            self._assistant_backend,
            self,
        )
        self._assistant_dock_widget.editsReady.connect(self._on_assistant_edits)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._assistant_dock_widget
        )
        self.tabifyDockWidget(self._palette_dock, self._assistant_dock_widget)
        # Disable each automation control while a run is in flight (busyChanged).
        for panel in (
            self._macro_controls,
            self._script_runner_panel,
            self._batch_recolour_panel,
            self._procgen_panel,
        ):
            self._automation_controller.busyChanged.connect(panel.set_busy)
            # D-06: live per-target progress on the same four panels' bars.
            self._automation_controller.targetProgress.connect(
                panel.set_target_progress
            )

        # Phase-10 Slice A cloud (REQ-P10-UI-001..008): a window-owned
        # Cloud_Controller runs the Qt-free data/cloud port (put/get/list/autosave)
        # off the GUI thread with cancel + result marshalling (UI-005); the worker
        # constructs no Qt object off-thread and hands back a Qt-free result (a
        # CloudVersion / bytes / version tuple / a defensively-decoded Document),
        # which THIS window consumes on the GUI thread. Its deterministic teardown
        # is folded into shutdown_prewarm so no worker / carrier survives GC (the
        # Phase-5/6/9 xdist-segfault guard). Cloud/sync is session state and pushes
        # NO QUndoCommand (PL10-D13; ui/commands.py untouched). The Cloud_Session is
        # the provider-agnostic connect/disconnect seam (UI-004) — ui/ never sees a
        # provider type or token (DATA-007/-008). No eval/exec: the open path decodes
        # untrusted bytes through the shipped defensive PIO-1 path (DATA-006).
        self._cloud_controller = Cloud_Controller(self)
        self._cloud_controller.operationSucceeded.connect(self._on_cloud_succeeded)
        self._cloud_controller.operationFailed.connect(self._on_cloud_failed)
        self._cloud_session = Cloud_Session(parent=self)
        self._cloud_session.connectionChanged.connect(self._on_cloud_connection_changed)
        #: The cloud project id last saved to / opened from (drives version browse).
        self._cloud_project_id: Optional[str] = None
        #: D-13: the most recently fetched remote version list (cached from the last
        #: "open_list"/"versions"/"save" result) — feeds the read-only
        #: ``compute_sync_state`` for the Cloud menu status line and the version
        #: browser, without a network round trip on every tab switch.
        self._cloud_last_versions: tuple = ()
        #: D-13: the version id of a restore/recover in flight, consumed once the
        #: reconstructed document lands in its new tab (see ``_on_cloud_succeeded``).
        self._pending_restore_version_id: Optional[str] = None
        # Autosave timer (UI-003 support): every AUTOSAVE_INTERVAL_MS it asks the
        # PURE logic.autosave.should_autosave policy (elapsed as an INPUT, no clock
        # read here) whether to write the working document to the port's recovery
        # slot. The slot is distinct from explicit version history, so an autosave
        # never clobbers the last explicit save (DATA-004). Stopped in teardown so
        # no tick fires after the controller is shut down.
        self._autosave_elapsed_ms = 0
        self._autosave_last_marker = 0
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._autosave_timer.start()

        # Phase-10 Slice B collaboration (REQ-P10-UI-009/-010/-011): shared projects
        # + comments + presence, driven by a provider-agnostic Collaboration_Session
        # over the Qt-free data/cloud SharedProjectAdapter (composed in-memory over the
        # loopback FakeCloudAdapter). Every Slice-B op is a PURELY SYNCHRONOUS in-memory
        # call — no network, no I/O — so NO off-GUI-thread worker / timer / poller is
        # introduced (the real sync backend + live push is Slice C, out of scope); the
        # session owns nothing to tear down beyond ordinary Qt parent ownership, so
        # shutdown_prewarm is unchanged. Collaboration is session state and pushes NO
        # QUndoCommand (PL10-D13; ui/commands.py untouched). Payloads are validated by
        # the pure logic/cloud_validation layer inside the adapter (Article VII); no
        # eval/exec. Presence shows WHO is present (UI-011) — NOT live cursors (UI-013,
        # Slice C). The three panels dock alongside the existing workflow docks.
        self._collab_session = Collaboration_Session(parent=self)
        self._shared_projects_panel = Shared_Projects_Panel(self)
        self._shared_projects_panel.set_session(self._collab_session)
        self._shared_dock = self._add_workflow_dock(self._shared_projects_panel)
        self._comments_panel = Comments_Panel(self)
        self._comments_panel.set_session(self._collab_session)
        self._comments_dock = self._add_workflow_dock(self._comments_panel)
        self._presence_panel = Presence_Panel(self)
        self._presence_panel.set_session(self._collab_session)
        self._presence_dock = self._add_workflow_dock(self._presence_panel)

        # Phase-10 Slice C real-time + branching (REQ-P10-UI-012/-013). The
        # Realtime_Session owns an OFF-GUI-THREAD worker (data/cloud TransportPort over
        # the loopback in CI, WebSocket out of CI) that polls/writes the relay; it hands
        # inbound framed bytes back over a queued signal and THIS session decodes +
        # applies them onto the live Document ON THE GUI THREAD (apply_remote is
        # dirty-region scoped — the Article VI re-entry AGT-10 profiles). Its worker has
        # an idempotent, event-loop-free shutdown (shutdown()) wired FIRST into
        # shutdown_prewarm so no worker thread / socket survives into GC (the recurring
        # PySide6 cross-thread xdist segfault — the highest-risk teardown this slice).
        # Real-time is session state and pushes NO QUndoCommand (PL10-D13). ui/ never
        # sees a provider type or token (DATA-007/-008). No eval/exec: inbound frames
        # are decoded/validated by the pure logic/sync_protocol layer (Article VII).
        self._realtime_session = Realtime_Session(parent=self)
        self._realtime_session.remoteUpdateApplied.connect(
            self._on_remote_update_applied
        )
        self._realtime_session.presenceReceived.connect(self._on_presence_received)
        self._realtime_session.connectionChanged.connect(
            self._on_realtime_connection_changed
        )
        self._realtime_session.errorOccurred.connect(self._on_realtime_error)
        #: Live-cursor overlays are per-tab (attached in _create_tab_aids); toggled on
        #: connect. The local member id broadcast with presence (never a token).
        self._realtime_member_id = ""

        # Branching (REQ-P10-UI-012): a git-like branch/switch/merge session over the
        # pure logic/realtime_apply model (conflict-free merge; no manual conflict UI).
        # Branching is session state and pushes NO QUndoCommand (PL10-D13). The merged /
        # switched/merged Document is loaded into the active tab by the slot below.
        self._branching_session = Branching_Session(parent=self)
        self._branching_session.documentSwitched.connect(
            self._on_branch_document_switched
        )
        self._branching_panel = Branching_Panel(self)
        self._branching_panel.set_session(self._branching_session)
        self._branching_dock = self._add_workflow_dock(self._branching_panel)
        # T15 (REQ-P10-UI-014/-025/-026): the open-diff affordance names a branch;
        # this window supplies the active tab's live Document to `supervise` (plan
        # §3.2 — only `ui/` holds it) and builds/shows the modeless
        # `Branch_Diff_Dialog` (T16, landed).
        self._last_supervision: Optional[SupervisionResult] = None
        self._branch_diff_dialog: Optional[Branch_Diff_Dialog] = None
        self._branching_panel.openDiffRequested.connect(self._on_open_diff_requested)

        # Phase-11 Slice 1 asset library (REQ-P11-UI-001/-002/-003): browse the
        # catalog, tag assets, and search/filter — three docked panels bound to one
        # Asset_Library_Session that holds the shared in-memory AssetCatalog and the
        # shared undo stack the tag QUndoCommands push onto (PL11-D3). Every Slice-1
        # library op (enumerate, filter, tag) is a PURELY SYNCHRONOUS in-memory call
        # over the immutable catalog value — no network, no I/O, no off-GUI-thread
        # worker / timer / poller (the Slice-B Shared_Projects_Panel precedent), so
        # shutdown_prewarm is unchanged and no worker survives into GC. Only tag
        # add/remove is undoable; adding/removing a catalog entry is library state and
        # pushes NO QUndoCommand. The tag stack joins the undo group so the global
        # Undo/Redo actions reach it. The search panel drives the pure query on the
        # library panel; the library selection drives the tagging panel.
        self._asset_session = Asset_Library_Session(self)
        self._undo_group.addStack(self._asset_session.undo_stack())
        self._asset_library_panel = Asset_Library_Panel(self)
        self._asset_library_panel.set_session(self._asset_session)
        self._asset_tagging_panel = Asset_Tagging_Panel(self)
        self._asset_tagging_panel.set_session(self._asset_session)
        self._asset_search_panel = Asset_Search_Panel(self)
        self._asset_library_panel.assetSelected.connect(
            self._asset_tagging_panel.set_asset
        )
        self._asset_search_panel.queryChanged.connect(
            self._asset_library_panel.set_query
        )
        self._asset_library_dock = self._add_workflow_dock(self._asset_library_panel)
        self._asset_search_dock = self._add_workflow_dock(self._asset_search_panel)
        self._asset_tagging_dock = self._add_workflow_dock(self._asset_tagging_panel)

        # Phase-11 Slice 2 dependency-graph view + passive break surface
        # (REQ-P11-UI-005/-006): visualise depends-on / dependents for the whole
        # catalog or the selected asset, and flag broken references passively. It
        # binds to the SAME Asset_Library_Session (single source of catalog + graph)
        # and follows the library selection. Every query is a pure, cycle-safe,
        # microsecond-fast in-memory call over the immutable graph value — SYNCHRONOUS
        # on the GUI thread, no worker / timer / poller (the Slice-1 precedent), so
        # shutdown_prewarm is unchanged and nothing survives into GC.
        self._dependency_graph_view = Dependency_Graph_View(self)
        self._dependency_graph_view.set_session(self._asset_session)
        self._asset_library_panel.assetSelected.connect(
            self._dependency_graph_view.set_asset
        )
        self._dependency_dock = self._add_workflow_dock(self._dependency_graph_view)

        # Phase-11 Slice 3 version browser + cross-project reuse
        # (REQ-P11-UI-004/-007): browse an asset's revisions and restore one
        # append-only; reference a shared asset into a project without copying its
        # bytes. Both bind to the SAME Asset_Library_Session (single source of the
        # catalog) and follow the library selection. The append-only revision store
        # and the shared content-addressable store are Qt-free data/ objects held here
        # and shared so bytes are stored ONCE (a reference adds no blob): the version
        # browser records/fetches through the revision store (CAS-backed), and the
        # reuse panel only has()-checks the CAS on a reference — it never put()s, so
        # the CAS blob count is unchanged (reference-not-copy). Every op is a
        # SYNCHRONOUS CAS/in-memory call — no worker / timer / poller (the Slice-1/2
        # precedent), so shutdown_prewarm is unchanged and nothing survives into GC.
        self._asset_content_store = default_content_store(self._asset_root())
        self._asset_revision_store = AssetRevisionStore(self._asset_content_store)
        self._asset_version_browser = Asset_Version_Browser(self)
        self._asset_version_browser.set_session(self._asset_session)
        self._asset_version_browser.set_store(self._asset_revision_store)
        self._asset_library_panel.assetSelected.connect(
            self._asset_version_browser.set_asset
        )
        self._version_browser_dock = self._add_workflow_dock(
            self._asset_version_browser
        )
        self._asset_reuse_panel = Asset_Reuse_Panel(self)
        self._asset_reuse_panel.set_session(self._asset_session)
        self._asset_reuse_panel.set_content_store(self._asset_content_store)
        self._reuse_dock = self._add_workflow_dock(self._asset_reuse_panel)

        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self._init_visual_aids()

        # Register the cross-OS UI-font fallback chain once, before any widget
        # paints, so a single-OS family (Segoe UI / .AppleSystemUIFont / …) never
        # yields .notdef boxes on another OS (REQ-P13-UI-001).
        apply_font_fallbacks()
        apply_theme(self._app, self._theme)
        self._language_manager.install_from_locale()

        self.new_document()
        self._retranslate()

        # Offer autosave recovery once the event loop is running (UI-003). Deferred
        # via a zero-timer so it never blocks construction (a modal dialog in
        # __init__ would stall headless tests); it is a no-op when disconnected /
        # nothing to recover, so a fresh in-memory session simply skips it.
        QTimer.singleShot(0, self._maybe_prompt_recovery)

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
        # Export action (REQ-P7-UI-001): opens the export dialog. Ctrl+Shift+E is
        # free (the tool key E is unmodified; Ctrl+Shift+A is the only other combo).
        self._export_action = QAction(self)
        self._export_action.setShortcut(
            Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_E
        )
        self._export_action.triggered.connect(self._on_export)

        # Phase-10 Slice A cloud actions (REQ-P10-UI-001..004). Every cloud op runs
        # off the GUI thread via the Cloud_Controller; connect/disconnect drives the
        # provider-agnostic Cloud_Session (no provider named, no token in ui/).
        self._cloud_connect_action = QAction(self)
        self._cloud_connect_action.triggered.connect(self._on_cloud_connect)
        self._cloud_disconnect_action = QAction(self)
        self._cloud_disconnect_action.setEnabled(False)
        self._cloud_disconnect_action.triggered.connect(self._on_cloud_disconnect)
        # Save/open/version-browse are gated on a live connection (disabled until
        # connect; _on_cloud_connection_changed toggles them).
        self._cloud_save_action = QAction(self)
        self._cloud_save_action.setEnabled(False)
        self._cloud_save_action.triggered.connect(self._on_cloud_save)
        self._cloud_open_action = QAction(self)
        self._cloud_open_action.setEnabled(False)
        self._cloud_open_action.triggered.connect(self._on_cloud_open)
        self._cloud_versions_action = QAction(self)
        self._cloud_versions_action.setEnabled(False)
        self._cloud_versions_action.triggered.connect(self._on_cloud_versions)
        # D-13: a disabled, non-actionable status entry surfacing the active tab's
        # ``compute_sync_state`` (read-only, Qt-free) — never computed here, only
        # displayed. Its accessible name doubles as the a11y label since a disabled
        # QAction still exposes its text through the menu's accessibility tree.
        self._cloud_status_action = QAction(self)
        self._cloud_status_action.setEnabled(False)
        # Phase-10 Slice C: real-time connect/disconnect + a live-cursor overlay toggle.
        # Connect joins the active document's real-time relay; disconnect leaves it
        # (reconnectable). The overlay toggle is checkable, per-tab visibility.
        self._realtime_connect_action = QAction(self)
        self._realtime_connect_action.triggered.connect(self._on_realtime_connect)
        self._realtime_disconnect_action = QAction(self)
        self._realtime_disconnect_action.setEnabled(False)
        self._realtime_disconnect_action.triggered.connect(self._on_realtime_disconnect)
        self._live_cursors_action = QAction(self)
        self._live_cursors_action.setCheckable(True)
        self._live_cursors_action.toggled.connect(self._on_live_cursors_toggled)

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

        # Help ▸ User Guide + F1 (REQ-UG-UI-001/-002). F1 is the platform Help
        # convention (CL-4); shown on the action so it is discoverable.
        self._user_guide_action = QAction(self)
        self._user_guide_action.setShortcut(QKeySequence(Qt.Key.Key_F1))
        self._user_guide_action.triggered.connect(self._on_user_guide)

        # Phase-6 tilemap actions (REQ-P6-UI-005..012). Stamp/erase/fill are a
        # mutually exclusive tool group driving the tilemap canvas; the flip/rotate
        # actions map the active stamp to the GID flag transform (view state).
        self._new_tileset_action = QAction(self)
        self._new_tileset_action.triggered.connect(self._on_new_tileset_from_image)
        self._new_tilemap_action = QAction(self)
        self._new_tilemap_action.triggered.connect(self._on_new_tilemap)
        self._import_tiled_action = QAction(self)
        self._import_tiled_action.triggered.connect(self._on_import_tiled)
        self._export_tiled_action = QAction(self)
        self._export_tiled_action.triggered.connect(self._on_export_tiled)

        self._tilemap_tool_group = QActionGroup(self)
        self._tilemap_tool_group.setExclusive(True)
        self._stamp_action = QAction(self)
        self._stamp_action.setCheckable(True)
        self._stamp_action.setChecked(True)
        self._stamp_action.setData(TilemapTool.STAMP)
        self._erase_tile_action = QAction(self)
        self._erase_tile_action.setCheckable(True)
        self._erase_tile_action.setData(TilemapTool.ERASE)
        self._fill_tile_action = QAction(self)
        self._fill_tile_action.setCheckable(True)
        self._fill_tile_action.setData(TilemapTool.FILL)
        for action in (
            self._stamp_action,
            self._erase_tile_action,
            self._fill_tile_action,
        ):
            action.triggered.connect(self._on_tilemap_tool_action)
            self._tilemap_tool_group.addAction(action)

        self._stamp_flip_h_action = QAction(self)
        self._stamp_flip_h_action.triggered.connect(self._tilemap_canvas.toggle_flip_h)
        self._stamp_flip_v_action = QAction(self)
        self._stamp_flip_v_action.triggered.connect(self._tilemap_canvas.toggle_flip_v)
        self._stamp_rotate_action = QAction(self)
        self._stamp_rotate_action.triggered.connect(self._tilemap_canvas.rotate_cw)

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
        self._file_menu.addAction(self._export_action)
        self._file_menu.addSeparator()
        self._file_menu.addAction(self._close_action)

        self._edit_menu = bar.addMenu("")
        self._edit_menu.addAction(self._undo_action)
        self._edit_menu.addAction(self._redo_action)
        self._edit_menu.addSeparator()
        # The restore path for suppressed per-project confirmations
        # (REQ-P5-UI-033, ADR-0056) — not the suppressed dialog itself, and not
        # a settings dialog (phase-6 REQ-P6-UI-039 owns that surface, plan §2).
        self._project_prefs_menu = build_project_prefs_menu(
            self.active_document, self._on_project_prefs_changed, self
        )
        self._edit_menu.addMenu(self._project_prefs_menu)

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
        self._view_menu.addAction(self._timeline_dock.toggleViewAction())
        self._view_menu.addAction(self._onion_dock.toggleViewAction())
        self._view_menu.addAction(self._tags_dock.toggleViewAction())
        self._view_menu.addAction(self._batch_dock.toggleViewAction())

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

        self._tilemap_menu = bar.addMenu("")
        self._tilemap_menu.addAction(self._new_tileset_action)
        self._tilemap_menu.addAction(self._new_tilemap_action)
        self._tilemap_menu.addSeparator()
        self._tilemap_menu.addAction(self._stamp_action)
        self._tilemap_menu.addAction(self._erase_tile_action)
        self._tilemap_menu.addAction(self._fill_tile_action)
        self._tilemap_menu.addSeparator()
        self._tilemap_menu.addAction(self._stamp_flip_h_action)
        self._tilemap_menu.addAction(self._stamp_flip_v_action)
        self._tilemap_menu.addAction(self._stamp_rotate_action)
        self._tilemap_menu.addSeparator()
        self._tilemap_menu.addAction(self._import_tiled_action)
        self._tilemap_menu.addAction(self._export_tiled_action)
        self._tilemap_menu.addSeparator()
        self._tilemap_menu.addAction(self._tileset_dock.toggleViewAction())
        self._tilemap_menu.addAction(self._tilemap_layer_dock.toggleViewAction())
        self._tilemap_menu.addAction(self._tilemap_dock.toggleViewAction())

        # Automation & extensibility (Phase 8): the panels are docks; the menu
        # surfaces their toggles so every automation surface is discoverable +
        # keyboard-reachable (REQ-P8-UI-012).
        self._automation_menu = bar.addMenu("")
        self._automation_menu.addAction(self._macro_dock.toggleViewAction())
        self._automation_menu.addAction(self._script_dock.toggleViewAction())
        self._automation_menu.addAction(self._plugin_dock.toggleViewAction())
        self._automation_menu.addAction(self._batch_recolour_dock.toggleViewAction())
        self._automation_menu.addAction(self._procgen_dock.toggleViewAction())

        # Cloud menu (Phase-10 Slice A): consistent with the existing menu bar; the
        # cloud save/load + version history + provider connect surfaces (UI-001..004).
        self._cloud_menu = bar.addMenu("")
        self._cloud_menu.addAction(self._cloud_connect_action)
        self._cloud_menu.addAction(self._cloud_disconnect_action)
        self._cloud_menu.addSeparator()
        self._cloud_menu.addAction(self._cloud_save_action)
        self._cloud_menu.addAction(self._cloud_open_action)
        self._cloud_menu.addSeparator()
        self._cloud_menu.addAction(self._cloud_versions_action)
        self._cloud_menu.addAction(self._cloud_status_action)
        # Slice-B collaboration surfaces, consistent with the existing Cloud menu:
        # dock-toggle actions for shared projects, comments, and presence (UI-009/
        # -010/-011).
        self._cloud_menu.addSeparator()
        self._cloud_menu.addAction(self._shared_dock.toggleViewAction())
        self._cloud_menu.addAction(self._comments_dock.toggleViewAction())
        self._cloud_menu.addAction(self._presence_dock.toggleViewAction())
        # Slice-C real-time + branching surfaces, consistent with the Cloud menu:
        # connect/disconnect the live session, toggle the live-cursor overlay, and the
        # branching dock (UI-012/-013).
        self._cloud_menu.addSeparator()
        self._cloud_menu.addAction(self._realtime_connect_action)
        self._cloud_menu.addAction(self._realtime_disconnect_action)
        self._cloud_menu.addAction(self._live_cursors_action)
        self._cloud_menu.addAction(self._branching_dock.toggleViewAction())

        # Library menu (Phase-11 Slice 1): consistent with the existing menu bar; the
        # asset-library / search / tagging dock toggles (UI-001/-002/-003), each
        # discoverable + keyboard-reachable.
        self._library_menu = bar.addMenu("")
        self._library_menu.addAction(self._asset_library_dock.toggleViewAction())
        self._library_menu.addAction(self._asset_search_dock.toggleViewAction())
        self._library_menu.addAction(self._asset_tagging_dock.toggleViewAction())
        self._library_menu.addAction(self._dependency_dock.toggleViewAction())
        self._library_menu.addAction(self._version_browser_dock.toggleViewAction())
        self._library_menu.addAction(self._reuse_dock.toggleViewAction())

        self._theme_menu = bar.addMenu("")
        self._theme_menu.addAction(self._theme_light_action)
        self._theme_menu.addAction(self._theme_dark_action)

        self._language_menu = bar.addMenu("")
        for code in self._language_manager.available_languages():
            action = QAction(code, self)
            action.setData(code)
            action.triggered.connect(self._on_language_action)
            self._language_menu.addAction(action)

        # Help menu (REQ-UG-UI-001): hosts the User Guide entry, consistent with the
        # existing menu structure (added last, the conventional trailing menu).
        self._help_menu = bar.addMenu("")
        self._help_menu.addAction(self._user_guide_action)
        # AI assistant (Phase-14): the chat dock toggle, discoverable + keyboard-
        # reachable from Help (the action text tracks the dock's translated title).
        self._help_menu.addSeparator()
        self._help_menu.addAction(self._assistant_dock_widget.toggleViewAction())

    # -- Phase-9 visual aids (REQ-P9-UI-001..010) ------------------------

    def _init_visual_aids(self) -> None:
        """Build the shell-level Phase-9 aid windows, controller and Aids menu.

        The real-size preview + timelapse controls are single shell widgets rebound
        to the active tab; the reference board is a separate always-on-top-capable
        window; the multi-view controller opens extra views on the active shared
        scene. Every aid is **non-destructive** view/session state — none pushes a
        ``QUndoCommand`` (REQ-P9-UI-010).
        """
        # A placeholder scene until the first document tab rebinds the preview.
        self._preview_window = Real_Size_Preview_Window(QGraphicsScene(self))
        self._preview_dock = QDockWidget(self)
        self._preview_dock.setWidget(self._preview_window)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._preview_dock)
        self.tabifyDockWidget(self._palette_dock, self._preview_dock)
        self._preview_dock.hide()

        # Timelapse controls: one shell widget; the active tab's undo stack is bound
        # on tab switch so a committed command records one frame (per-command cadence).
        self._timelapse_controls = Timelapse_Controls(self)
        self._timelapse_dock = self._add_workflow_dock(self._timelapse_controls)
        self._timelapse_dock.hide()

        # Reopened-recording display target (REQ-P9-UI-024, DEP-12f): a
        # dock of its own, never the active canvas, so its "reopened
        # recording" banner can never appear over the user's own current
        # work. Fed frameReady only while the shipped controls are
        # reviewing a loaded, payload-carrying session; the read-only lock
        # (playbackEditLockChanged) and the dropped-frames notice
        # (framesDropped) are routed to their production consumers here too.
        self._timelapse_frame_view = Timelapse_Frame_View(self)
        self._timelapse_frame_view_dock = self._add_workflow_dock(
            self._timelapse_frame_view
        )
        self._timelapse_frame_view_dock.hide()
        self._timelapse_controls.frameReady.connect(self._on_timelapse_frame_ready)
        self._timelapse_controls.playbackEditLockChanged.connect(
            self._on_timelapse_playback_lock_changed
        )
        self._timelapse_controls.framesDropped.connect(
            self._on_timelapse_frames_dropped
        )

        # Reference board: a separate window (PureRef-style; optional always-on-top).
        self._reference_board = Reference_Board()
        self._reference_board.setWindowFlag(Qt.WindowType.Window, True)

        # Multi-view of ONE document: extra views on the active tab's shared scene.
        self._multi_view = Multi_View(QGraphicsScene(self))

        # Aids menu (checkable per-tab overlays + window/dock toggles).
        bar = self.menuBar()
        self._aids_menu = bar.addMenu("")
        self._preview_aid_action = self._preview_dock.toggleViewAction()
        self._aids_menu.addAction(self._preview_aid_action)
        self._guides_action = QAction(self)
        self._guides_action.setCheckable(True)
        self._guides_action.toggled.connect(self._on_guides_toggled)
        self._aids_menu.addAction(self._guides_action)
        self._iso_action = QAction(self)
        self._iso_action.setCheckable(True)
        self._iso_action.toggled.connect(self._on_iso_toggled)
        self._aids_menu.addAction(self._iso_action)
        # REQ-P9-UI-004: the minimal iso-grid configuration dialog entry point,
        # in the same menu region as its toggle — mirrors the perspective aid's
        # D-09 pattern below.
        self._iso_config_action = QAction(self)
        self._iso_config_action.triggered.connect(self._on_configure_iso_grid)
        self._aids_menu.addAction(self._iso_config_action)
        self._perspective_action = QAction(self)
        self._perspective_action.setCheckable(True)
        self._perspective_action.toggled.connect(self._on_perspective_toggled)
        self._aids_menu.addAction(self._perspective_action)
        # D-09: the minimal vanishing-point configuration dialog entry point —
        # the perspective aid's natural home (same menu, right after its toggle).
        self._perspective_config_action = QAction(self)
        self._perspective_config_action.triggered.connect(
            self._on_configure_perspective
        )
        self._aids_menu.addAction(self._perspective_config_action)
        self._aids_menu.addSeparator()
        self._new_view_action = QAction(self)
        self._new_view_action.triggered.connect(self._on_new_view)
        self._aids_menu.addAction(self._new_view_action)
        self._reference_board_action = QAction(self)
        self._reference_board_action.triggered.connect(self._on_show_reference_board)
        self._aids_menu.addAction(self._reference_board_action)
        self._aids_menu.addAction(self._timelapse_dock.toggleViewAction())
        self._aids_menu.addAction(self._timelapse_frame_view_dock.toggleViewAction())

    def _create_tab_aids(self, record: "_DocTab") -> QWidget:
        """Create this tab's overlays + rulers, returning the ruler-wrapped view.

        The iso/perspective grid overlays + the doc-space guide overlay are added to
        the tab's scene (culled, cache-backed); the ruler strips wrap the view in a
        grid so the whole tab shows rulers when the guides aid is on. All snap/tick
        maths stays in ``logic/`` (Article I).
        """
        scene_rect = QRectF(0, 0, record.document.width, record.document.height)
        record.iso_overlay = Iso_Grid_Overlay(scene_rect, IsoGridConfig(tile_width=32))
        record.scene.addItem(record.iso_overlay)
        record.perspective_overlay = Perspective_Grid_Overlay(
            scene_rect, self._default_perspective(record.document)
        )
        record.scene.addItem(record.perspective_overlay)
        record.guides_rulers = Guides_Rulers_Overlay(
            record.view, record.scene, scene_rect
        )
        # D-08: bind this tab's aids so the view's cursor snap (guides >
        # perspective > iso > rectangular) can consult their visible+enabled
        # state; rebound to the active tab on every switch, below.
        record.view.set_guides_overlay(record.guides_rulers)
        record.view.set_iso_overlay(record.iso_overlay)
        record.view.set_perspective_overlay(record.perspective_overlay)
        # Phase-10 Slice C: the ephemeral live-cursor overlay (other collaborators'
        # cursors, REQ-P10-UI-013). Above the aids (z ~9); hidden until real-time is
        # connected. No item cache — cursors move per frame (AGT-10 will profile).
        record.live_cursors = Live_Cursors_Overlay(scene_rect)
        record.scene.addItem(record.live_cursors)
        self._apply_aid_theme(record)

        # Wrap the view with the ruler strips (top + left) in a grid container.
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.addWidget(record.guides_rulers.horizontal_ruler(), 0, 1)
        grid.addWidget(record.guides_rulers.vertical_ruler(), 1, 0)
        grid.addWidget(record.view, 1, 1)
        return container

    @staticmethod
    def _default_perspective(document: Document) -> PerspectiveConfig:
        """Build a sensible 2-point default (VPs on a mid-canvas horizon)."""
        w, h = document.width, document.height
        horizon = h / 2.0
        return PerspectiveConfig(
            mode=2,
            vanishing_points=(
                VanishingPoint(position=(-w, horizon)),
                VanishingPoint(position=(2.0 * w, horizon)),
            ),
            horizon_y=horizon,
        )

    def _apply_aid_theme(self, record: "_DocTab") -> None:
        """Push role-based colours to a tab's overlays (both themes legible, 025)."""
        _checker_light, _checker_dark, grid = canvas_roles(self._theme)
        if record.iso_overlay is not None:
            record.iso_overlay.set_line_color(grid)
        if record.perspective_overlay is not None:
            record.perspective_overlay.set_colors(grid, grid)
        if record.guides_rulers is not None:
            record.guides_rulers.set_colors(grid, _checker_dark, _checker_light)

    @staticmethod
    def _render_timelapse_frame(document: Document, frame_index: int) -> np.ndarray:
        """Composite one ``Document`` frame to an RGBA ``ndarray`` (D-12, T9/T10).

        The ``Timelapse_Controls`` renderer (``Document -> np.ndarray``, S11 — no
        domain/composite maths authored here): binds to
        :func:`~pixelart_creator.logic.blend.composite_stack` for an RGBA
        document, mirroring the shipped ``ui/timeline_panel.py`` thumbnail idiom
        for an indexed one (palette LUT over the topmost leaf layer — indexed
        documents are not composited; the compositor is RGBA-only). ``document``
        may hold a different frame count at each historical step than the tab
        that owns it, so an out-of-range ``frame_index`` falls back to frame 0
        rather than raising.
        """
        index = frame_index if 0 <= frame_index < len(document.frames) else 0
        frame = document.frames[index]
        if document.mode is ColorMode.RGBA:
            buffer = composite_stack(frame.layers, document.width, document.height)
            return np.ascontiguousarray(buffer.data)
        leaves = iter_layers(frame.layers)
        if not leaves:
            return np.zeros((document.height, document.width, 4), dtype=np.uint8)
        lut = np.array(document.palette.colors() or [(0, 0, 0, 255)], dtype=np.uint8)
        idx = np.clip(leaves[-1].buffer.data, 0, len(lut) - 1)
        return np.ascontiguousarray(lut[idx])

    def _bind_visual_aids_to_active(self) -> None:
        """Rebind the shell aids to the active tab + sync the Aids-menu state."""
        record = self.active_tab()
        if record is None:
            return
        self._preview_window.set_scene(record.scene)
        self._preview_window.set_document_ppi(record.document.ppi)
        self._multi_view.set_scene(record.scene)
        # D-12: bind this tab's document alongside its stack (REQ-P9-UI-020 — a
        # session belongs to one document) and (re)point the renderer at this
        # tab's currently displayed frame, so a historical replay composites the
        # same frame the canvas shows rather than always frame 0. ``id()`` is the
        # only per-tab document identity available: ``_DocTab`` carries no other
        # stable id and the document object is mutated in place, never
        # reassigned, for this tab's lifetime (ui/timelapse_playback.py).
        self._timelapse_controls.bind_undo_stack(
            record.stack,
            document_getter=lambda: record.document,
            document_id=id(record.document),
        )
        self._timelapse_controls.set_renderer(
            lambda document: self._render_timelapse_frame(
                document, record.scene.frame_index
            )
        )
        # Phase-10 Slice C: rebind the real-time session + branching base to this tab's
        # document, and reflect this tab's live-cursor overlay visibility on the toggle.
        self._realtime_session.set_document(record.document)
        self._branching_session.set_base_document(record.document)
        if record.live_cursors is not None:
            record.live_cursors.set_local_member(self._realtime_member_id)
            record.live_cursors.setVisible(self._live_cursors_action.isChecked())
        # Reflect this tab's overlay visibility without re-triggering the toggles.
        for action, overlay in (
            (self._guides_action, record.guides_rulers),
            (self._iso_action, record.iso_overlay),
            (self._perspective_action, record.perspective_overlay),
        ):
            action.blockSignals(True)
            visible = (
                overlay.is_enabled()
                if isinstance(overlay, Guides_Rulers_Overlay)
                else (overlay.isVisible() if overlay is not None else False)
            )
            action.setChecked(bool(visible))
            action.blockSignals(False)

    def _on_timelapse_frame_ready(self, frame: "np.ndarray") -> None:
        """Route one rendered timelapse frame to its display target (frameReady).

        Only a reopened (payload-carrying) session's frames reach
        :class:`Timelapse_Frame_View` — REQ-P9-UI-024's "reopened recording"
        banner must never appear over the user's own in-session work.
        ``Timelapse_Controls.is_reopened_recording()`` is the same
        distinction :meth:`_on_timelapse_playback_lock_changed`'s emitter
        already gates on, so the two consumers stay consistent with each
        other by construction. An in-session (non-reopened) frame instead goes
        to the active tab's canvas overlay (REQ-P9-UI-016) — the same tab this
        playback locked, since both handlers reach it via :meth:`active_tab`.
        """
        if not self._timelapse_controls.is_reopened_recording():
            record = self.active_tab()
            if record is not None:
                record.scene.show_playback_frame(frame)
            return
        self._timelapse_frame_view.display_frame(frame)
        if not self._timelapse_frame_view_dock.isVisible():
            self._timelapse_frame_view_dock.show()
            self._timelapse_frame_view_dock.raise_()

    def _on_timelapse_playback_lock_changed(self, locked: bool) -> None:
        """Refuse document edits on the active tab during playback (REQ-P9-UI-016).

        Only ever emitted for an in-session (history) playback —
        ``Timelapse_Controls`` gates the emission on
        ``not is_reopened_recording()`` — so the tab this locks genuinely is
        the document the running session was recorded against. Disables
        that tab's canvas view (no drawing, no tool commit) and the shared
        undo/redo actions (no undo/redo); both are re-enabled once playback
        stops (``locked`` becomes ``False``), at which point the playback
        overlay is also hidden so the tab returns to showing the live
        document.
        """
        self._playback_locked = locked
        record = self.active_tab()
        if record is not None:
            record.view.setEnabled(not locked)
            if not locked:
                record.scene.end_playback_frame()
        self._undo_action.setEnabled(not locked and self._can_undo())
        self._redo_action.setEnabled(not locked and self._can_redo())

    def _on_timelapse_frames_dropped(self, count: int) -> None:
        """Surface the timelapse dock so its drop notice reaches the user (UI-021).

        ``Timelapse_Controls`` already sets its own reason-label text on
        this same occurrence (``_on_stack_index_changed``); that text is
        never duplicated here. The dock starts hidden, so without this the
        notice could be produced while nothing shows it.
        """
        del count  # the widget's own reason label already states the count
        if not self._timelapse_dock.isVisible():
            self._timelapse_dock.show()
            self._timelapse_dock.raise_()

    def _on_guides_toggled(self, enabled: bool) -> None:
        record = self.active_tab()
        if record is not None and record.guides_rulers is not None:
            record.guides_rulers.set_enabled(enabled)

    def _on_iso_toggled(self, enabled: bool) -> None:
        record = self.active_tab()
        if record is not None and record.iso_overlay is not None:
            record.iso_overlay.setVisible(enabled)

    def _on_configure_iso_grid(self) -> None:
        """Open the isometric-grid configuration dialog for the active tab (UI-004)."""
        record = self.active_tab()
        if record is None or record.iso_overlay is None:
            return
        dialog = Iso_Grid_Dialog(record.iso_overlay.config(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            record.iso_overlay.set_config(dialog.iso_config())

    def _on_perspective_toggled(self, enabled: bool) -> None:
        record = self.active_tab()
        if record is not None and record.perspective_overlay is not None:
            record.perspective_overlay.setVisible(enabled)

    def _on_configure_perspective(self) -> None:
        """Open the vanishing-point dialog for the active tab (D-09)."""
        record = self.active_tab()
        if record is None or record.perspective_overlay is None:
            return
        dialog = Vanishing_Point_Dialog(record.perspective_overlay.config(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            record.perspective_overlay.set_config(dialog.perspective_config())

    def _on_new_view(self) -> None:
        view = self._multi_view.open_view()
        if view is not None:
            view.show()

    def _on_show_reference_board(self) -> None:
        self._reference_board.show()
        self._reference_board.raise_()

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
        """Save the active document via ``data/project_io`` (020).

        Marks the tab's undo stack **clean** at the saved state so the drag-drop
        dirty guard (REQ-DDI-UI-004) can trust ``QUndoStack.isClean()`` — a saved,
        un-edited document no longer prompts on a ``.pixproj`` drop.
        """
        record = self.active_tab()
        if record is not None:
            save_project(record.document, path)
            record.stack.setClean()

    def _add_document_tab(self, document: Document, title: str) -> Document:
        scene = CanvasScene(document)
        # Off-thread pre-warm progress (D1/D2): each scene reports its own warm; the
        # slots guard on the active tab so a background tab's warm never drives the
        # shared indicator/transport.
        scene.prewarmStarted.connect(self._on_prewarm_started)
        scene.prewarmAdvanced.connect(self._on_prewarm_advanced)
        scene.prewarmFinished.connect(self._on_prewarm_finished)
        stack = QUndoStack(self)
        self._undo_group.addStack(stack)
        view = Canvas_View(scene, stack)
        view.colorPicked.connect(self._on_color_picked)
        view.floatingStateChanged.connect(self._on_floating_state_changed)
        view.lockedLayerEditRejected.connect(self._notify_layer_locked)
        view.set_menu_hook(self._open_colour_hub)
        # T-12: a drop delivered straight to the canvas viewport is routed
        # through the same handler as Main_Window.dropEvent (REQ-DDI-UI-001).
        view.set_drop_router(self._route_dropped_files)
        # T-DRAW-01/REQ-P10-UI-025: bind this tab's branch-recording sink at
        # construction, mirroring set_undo_stack's own tab-construction /
        # tab-switch / branch-switch-or-merge binding points (see
        # _on_tab_changed and _on_branch_document_switched below) — every
        # drawing tool routes through this so a stroke lands in the active
        # branch's op-log instead of being silently dropped at merge.
        view.set_recording(self._branching_session.record_traces, document)
        record = _DocTab(document, scene, view, stack)
        self._tabs_data.append(record)
        # Attach this tab's Phase-9 visual aids and wrap the view with rulers before
        # the tab is shown (setCurrentIndex fires _on_tab_changed, which binds them).
        container = self._create_tab_aids(record)
        index = self._tab_widget.addTab(container, title)
        self._tab_widget.setCurrentIndex(index)
        self._apply_theme_to_scene(scene)
        view.set_tool(self._tools[self._active_tool_id])
        view.set_active_color(self._active_color)
        view.set_active_index(self._active_index)
        self._bind_symmetry_panel(record)
        self._apply_modes_to(record)
        self._bind_palette_workflows(record)
        return document

    def _bind_symmetry_panel(self, record: "_DocTab") -> None:
        """Rebind the Symmetry_Panel's spinbox ranges to ``record``'s document (D-28).

        A resize/tab-switch must never keep a stale, now out-of-bounds user
        position (``Symmetry_Panel.set_canvas_size`` itself resets to the
        unset/centre default); the shell's own tracked override is reset in
        step so ``_apply_modes_to`` pushes the same fresh ``None``.
        """
        self._symmetry_panel.set_canvas_size(
            record.document.width, record.document.height
        )
        self._symmetry_axis_pos = None

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
            scene.begin_opacity_drag,
        )
        self._bind_animation(record)
        self._bind_tilemap(record)
        self._bind_automation(record)
        self._refresh_mode_ui()

    def _bind_animation(self, record: "_DocTab") -> None:
        """Point the timeline / playback / onion / tag surfaces at ``record``.

        Binds each shared animation panel to this tab's document + undo stack and
        syncs them to the tab's persisted active frame (state isolation, CL-13).
        Playback is stopped on rebind so a timer never advances the wrong tab.
        """
        document = record.document
        stack = record.stack
        scene = record.scene
        self._playback_controls.stop()
        self._timeline_panel.set_context(
            document, stack, self._on_timeline_frames_changed
        )
        self._frame_tags_panel.set_context(
            document, stack, self._on_timeline_tags_changed
        )
        self._playback_controls.set_context(
            self._frame_durations, lambda: self._active_frame
        )
        # Bind the transport's off-thread warm to THIS tab's scene (D1/D2).
        self._playback_controls.set_prewarm_context(
            scene.is_frame_warm, scene.prewarm_frames
        )
        # Sync the shared panels to this tab's persisted active frame.
        self._active_frame = scene.frame_index
        self._timeline_panel.select_frame(scene.frame_index)
        self._layer_panel.set_frame_index(scene.frame_index)
        self._onion_controls.settingsChanged.emit(self._onion_controls.settings())

    def _frame_durations(self) -> List[int]:
        """Return the active document's per-frame ``duration_ms`` (authoritative)."""
        document = self.active_document()
        if document is None:
            return []
        return [frame.duration_ms for frame in document.frames]

    # -- animation slots (REQ-P5-UI-002/-008/-011/-014, CL-13) -----------

    def _on_frame_selected(self, index: int) -> None:
        """Select the active (canvas-displayed) frame on a timeline click (no undo)."""
        record = self.active_tab()
        if record is None:
            return
        record.view.commit_active_float()
        self._active_frame = index
        record.scene.set_frame_index(index, scrub=False)
        self._layer_panel.set_frame_index(index)
        record.view.viewport().update()

    def _on_frame_scrubbed(self, index: int) -> None:
        """Scrub on a timeline drag, showing the frame under the cursor (no undo)."""
        record = self.active_tab()
        if record is None:
            return
        self._active_frame = index
        record.scene.set_frame_index(index, scrub=True)
        record.view.viewport().update()

    def _on_frame_advanced(self, index: int) -> None:
        """Advance the displayed frame on a playback tick (scrub-fast, onion off).

        On a cold frame the scene holds the display and warms it off-thread (D1/D2);
        the transport waits and this slot only advances the timeline/view once the
        frame is actually shown, so the marker never runs ahead of a blank frame.
        """
        record = self.active_tab()
        if record is None:
            return
        displayed = record.scene.set_frame_index(index, scrub=True, block_on_miss=False)
        if not displayed:
            return
        self._active_frame = index
        self._timeline_panel.select_frame(index)
        record.view.viewport().update()

    def _on_playback_active(self, active: bool) -> None:
        """Suppress onion skinning while playback is active (CL-11).

        On halt (Stop / Pause / end) cancel any in-flight off-thread warm (D2).
        """
        record = self.active_tab()
        if record is not None:
            record.scene.set_playing(active)
            if not active:
                record.scene.cancel_prewarm()

    def _on_prewarm_started(self, total: int) -> None:
        """Show the pre-warm indicator for the active scene's cold-frame warm (D1)."""
        record = self.active_tab()
        if record is None or self.sender() is not record.scene:
            return
        self._prewarm_indicator.start(total)

    def _on_prewarm_advanced(self, index: int, done: int, total: int) -> None:
        """Update pre-warm progress and stream the frame to the transport (D2)."""
        record = self.active_tab()
        if record is None or self.sender() is not record.scene:
            return
        self._prewarm_indicator.set_progress(done, total)
        self._playback_controls.notify_frame_ready(index)

    def _on_prewarm_finished(self) -> None:
        """Hide the pre-warm indicator (warm complete or cancelled, D1)."""
        self._prewarm_indicator.finish()

    def _on_onion_settings(self, settings: OnionSettings) -> None:
        """Apply the onion view settings to the active scene (live, no undo)."""
        record = self.active_tab()
        if record is None:
            return
        record.scene.set_onion_settings(
            settings.enabled,
            settings.prev_count,
            settings.next_count,
            settings.tint_prev,
            settings.tint_next,
        )

    def _on_play_tag(self, tag: object) -> None:
        """Play a named animation over a tag's range/mode (REQ-P5-UI-014)."""
        from pixelart_creator.logic.animation import FrameTag

        if isinstance(tag, FrameTag):
            self._playback_controls.play_tag(tag)

    def _on_timeline_frames_changed(self) -> None:
        """Handle the ``FrameCommand`` follow-up after a structural frame op.

        Invalidate the per-frame composite cache + recomposite the active frame,
        and re-sync the layer panel's frame index. The timeline rebuilds itself.
        """
        record = self.active_tab()
        if record is None:
            return
        index = self._timeline_panel.active_index
        self._active_frame = index
        record.scene.refresh_frames(index)
        self._layer_panel.set_frame_index(index)
        record.view.viewport().update()

    def _on_timeline_tags_changed(self) -> None:
        """Handle the ``FrameCommand`` follow-up after a tag op (re-render spans)."""
        self._timeline_panel.rebuild()

    def _on_project_prefs_changed(self) -> None:
        """Handle a project confirmation preference restored to its default.

        A preference is not document content (REQ-P5-DATA-004): no recomposite,
        no undo entry. Reserved for a future dependent surface; presently a
        deliberate no-op.
        """
        return None

    def _apply_modes_to(self, record: _DocTab) -> None:
        """Push the shell's Phase-2 drawing modes onto a tab's view/scene."""
        view = record.view
        view.set_symmetry_axis(self._symmetry_axis)
        view.set_symmetry_pos(self._symmetry_axis_pos)
        view.set_pixel_perfect(self._pixel_perfect)
        view.set_snap_enabled(self._snap)
        view.set_grid_enabled(self._grid_action.isChecked())
        view.reassert_no_antialiasing()
        set_tiled_mode(record.scene, view, self._tiled)

    def close_document(self, index: int) -> None:
        """Close the document tab at ``index``."""
        if not 0 <= index < len(self._tabs_data):
            return
        # Stop any playback so the timer never advances a closed document.
        self._playback_controls.stop()
        record = self._tabs_data.pop(index)
        # Close any extra views onto this document's scene before it is dropped
        # (they share the closing scene; a stale view must not outlive it).
        self._multi_view.close_all()
        # Tear down the scene's off-thread warm pool before dropping it (D2).
        record.scene.shutdown_prewarm()
        self._undo_group.removeStack(record.stack)
        self._tab_widget.removeTab(index)

    def shutdown_prewarm(self) -> None:
        """Deterministically tear down every off-thread warm in the window (D2/D4).

        A window-level, idempotent shutdown that drains and releases each tab's
        canvas pre-warm pool + signal carrier, the shared tilemap canvas's
        off-thread chunk-warm pool + carrier, AND the export controller's worker
        pool + carrier (REQ-P7-UI-010). It does not rely on the Qt event loop, so
        it is safe to call directly — from :meth:`closeEvent`, and by tests in a
        teardown fixture to guarantee no worker thread or connected carrier survives
        a :class:`MainWindow` past its use.
        """
        # Phase-10 Slice C: stop the real-time worker FIRST — it is the ONLY off-GUI-
        # thread network worker in the window (a live transport + poll loop), and it
        # must be stopped, its connection closed on the worker thread, and the thread
        # joined (bounded) BEFORE the dependent live-cursor overlays / scenes are torn
        # down. Its shutdown() is idempotent + event-loop-free and releases the carrier,
        # so no worker thread or socket survives into a later GC cycle (the recurring
        # PySide6 cross-thread GC-of-Qt-C++ xdist native segfault — worse here with a
        # live socket). Ordered before every dependent teardown below.
        self._realtime_session.shutdown()
        for record in self._tabs_data:
            record.scene.shutdown_prewarm()
        # The tilemap canvas is a single window-level widget (not per-tab); tear its
        # off-thread chunk warm down here so closeEvent covers it too (D4).
        self._tilemap_canvas.shutdown_warm()
        # The export worker pool + carrier is a single window-level resource; tear it
        # down here so closeEvent covers it too (REQ-P7-UI-010). Idempotent, event-
        # loop-free — no export worker or signal carrier survives into GC.
        self._export_controller.shutdown()
        # The automation worker pool + carrier is likewise a single window-level
        # resource; tear it down here so closeEvent covers it too (REQ-P8-UI-011).
        # Idempotent, event-loop-free — no automation worker or signal carrier
        # survives into a later GC cycle (the Phase-5 xdist-segfault guard).
        self._automation_controller.shutdown()
        # The Phase-10 cloud worker pool + carrier is likewise a single window-level
        # resource; stop the autosave timer FIRST (so no tick submits a job after
        # teardown) then tear the controller down here so closeEvent covers it too
        # (REQ-P10-UI-005). Idempotent, event-loop-free — no cloud worker or signal
        # carrier survives into a later GC cycle (the Phase-5/6/9 xdist-segfault
        # guard). The Cloud_Session holds only a Qt-free port reference (no thread).
        self._autosave_timer.stop()
        self._cloud_controller.shutdown()
        # The Phase-14 assistant controller is likewise a single window-level worker
        # pool + carrier; tear it down here so closeEvent covers it too
        # (REQ-P14-UI-004). Idempotent, event-loop-free — it releases any worker
        # blocked on a pending tiered-safety confirmation (deny) and joins the thread,
        # so no assistant worker or signal carrier survives into a later GC cycle (the
        # recurring xdist-segfault guard).
        self._assistant_controller.shutdown()
        # Phase-9 aids own no worker threads (non-destructive view state), but their
        # separate top-level windows must not outlive the shell: close the extra
        # document views and the reference board deterministically (idempotent).
        self._multi_view.close_all()
        self._reference_board.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Tear down every scene's off-thread warm pool before the window closes.

        A running pool must not be destroyed with a task in flight, so each scene's
        warm is cancelled, awaited (bounded) and its carrier released here (D2).
        """
        self._playback_controls.stop()
        self.shutdown_prewarm()
        super().closeEvent(event)

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

    @staticmethod
    def _edit_target(record: _DocTab) -> Optional[EditTarget]:
        """Return where an edit on ``record``'s active layer lands (`REQ-P10-UI-025`).

        The context — which frame and which layer track an edit landed on —
        exists only in the UI, which holds the active ``Document`` (plan
        §8.2): no ``logic/`` factory has it intrinsically, so every
        `main_window.py` call site that reaches a ``PixelEdit`` supplies it
        from here. ``None`` only when the active layer has not been minted a
        stable id yet (``layer_id == 0``, the documented *unminted* sentinel,
        ``logic/document.py:264``, ``:1729``) — passing ``0`` through would
        either be refused outright (`EditTarget.__post_init__`) or, worse,
        resolve to a real node in frame 0 (plan §8.1's dangerous half-threaded
        case) — so an unminted layer's edits are reported honestly as
        ``unaccounted`` (`REQ-P10-UI-026`) instead of guessed.
        """
        layer = record.scene.active_layer()
        if layer.layer_id <= 0:
            return None
        return EditTarget(frame_index=record.scene.frame_index, layer_id=layer.layer_id)

    # -- drag-and-drop import (REQ-DDI-UI-001..008) -----------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept a drag that carries at least one local file URL (UI-001)."""
        mime = event.mimeData()
        if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Capture the dropped local file paths and route them (UI-001/-008)."""
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        event.acceptProposedAction()
        # A zero-file drop is a no-op (SC-U008-5); otherwise route each path.
        self._route_dropped_files(paths)

    def _route_dropped_files(self, paths: List[str]) -> None:
        """Route each dropped path by classified TYPE, in stable order (UI-002/-008).

        Routing is by file TYPE (REQ-DDI-DATA-003), never by drop location (CL-A1).
        Each file is guarded so one bad file surfaces a notice and never aborts the
        batch or crashes the app (REQ-DDI-UI-006/-007, NFR-9). Multiple palettes
        replace sequentially — the last dropped palette wins (CL-A2).
        """
        for path in paths:
            file_type = classify(path)
            try:
                if file_type is FileType.IMAGE:
                    self._import_image_drop(path)
                elif file_type is FileType.PROJECT:
                    self._import_project_drop(path)
                elif file_type is FileType.PALETTE:
                    self._import_palette_drop(path)
                else:
                    self._notify_unsupported(path)
            except (FileImportError, ProjectIOError) as exc:
                # Corrupt / malformed / oversized / invalid project → error notice,
                # state left intact, batch continues (REQ-DDI-UI-007, SC-U008-3).
                self._notify_import_error(path, exc)

    def _import_image_drop(self, path: str) -> None:
        """IMAGE drop → decode to RGBA and open as a NEW document tab (UI-003).

        Decodes via ``ui/image_import.decode_image`` (QImage, ADR-0010) into an
        RGBA :class:`PixelBuffer`, wraps it in a new :class:`Document`, and opens it
        as a new tab through the shipped ``_add_document_tab`` machinery — **never**
        as a layer on the active document. The source file is not modified.
        """
        buffer = decode_image(path)
        document = Document.from_buffer(buffer, name=Path(path).stem or "Imported")
        self._add_document_tab(document, Path(path).name)

    def _import_project_drop(self, path: str) -> None:
        """PROJECT drop → open, replacing the active doc with a dirty guard (UI-004).

        If the active document has unsaved changes, prompt Save / Discard / Cancel
        first: Cancel aborts (this file only); Save persists then opens; Discard
        opens without saving. The dropped project then **replaces** the previously
        active document (its tab is closed once the project opens).
        """
        record = self.active_tab()
        previous_index = self._tab_widget.currentIndex()
        if record is not None and not record.stack.isClean():
            choice = QMessageBox.warning(
                self,
                self.tr("Unsaved Changes"),
                self.tr(
                    "The current document has unsaved changes. Save it before "
                    "opening the dropped project?"
                ),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                return  # abort: leave everything unchanged (SC-U004-3)
            if choice == QMessageBox.StandardButton.Save and not self._save_for_guard():
                return  # a cancelled save must not lose the unsaved work
        self.open_document(path)
        # REPLACE the previously active document: the project opened in a new tab
        # (now current); close the old tab, if any (indices below the new one are
        # unaffected — the new tab was appended last).
        if record is not None and 0 <= previous_index < len(self._tabs_data):
            self.close_document(previous_index)

    def _import_palette_drop(self, path: str) -> None:
        """PALETTE drop → replace the active palette as ONE undoable command (UI-005).

        Parses the ``.gpl`` / ``.hex`` / ``.pal`` via the Qt-free
        ``data/palette_import.load_palette`` and replaces the active document's
        palette **in place** as a single :class:`LogicCommand` on the tab's undo
        stack, so one Undo restores the prior palette (``apply ∘ undo = identity``,
        SC-U005-4). No open document → a graceful no-op with a notice (SC-U005-5).
        """
        record = self.active_tab()
        if record is None:
            self._notify_no_document()
            return
        new_colors = load_palette(path).colors()
        palette = record.document.palette
        before = palette.colors()
        label = self.tr("Load Palette")
        command = history.FunctionCommand(
            do=lambda: palette.replace(new_colors),
            undo=lambda: palette.replace(before),
            label=label,
        )
        record.stack.push(
            LogicCommand(
                command,
                self._on_palette_edited,
                label,
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
        )

    def _save_for_guard(self) -> bool:
        """Save the active document for the dirty guard; ``False`` if cancelled.

        Prompts for a path (the shipped Save-As flow) and saves via
        :meth:`save_document` (which marks the stack clean). Returns ``False`` when
        the user cancels the file dialog, so the caller can abort the open rather
        than silently discard unsaved work (REQ-DDI-UI-004, Save branch).
        """
        if self.active_tab() is None:
            return True
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Project"),
            "",
            self.tr("Pixel projects (*%1)").replace("%1", FILE_SUFFIX),
        )
        if not path:
            return False
        self.save_document(path)
        return True

    def _notify_unsupported(self, path: str) -> None:
        """Non-blocking notice that a dropped file's type is unsupported (UI-006)."""
        self.statusBar().showMessage(
            self.tr("Unsupported file type: %1").replace("%1", Path(path).name),
            UI_NOTICE_DURATION_MS,
        )

    def _notify_layer_locked(self) -> None:
        """Non-blocking notice that a mask attach/edit/remove was refused.

        The target layer is locked (D-05, REQ-P4-LOGIC-010); unlock it from
        its row's lock toggle (REQ-P4-UI-004) to edit it.
        """
        self.statusBar().showMessage(
            self.tr("Layer is locked."),
            UI_NOTICE_DURATION_MS,
        )

    def _notify_no_document(self) -> None:
        """Non-blocking notice that a palette drop needs an open document (UI-005)."""
        self.statusBar().showMessage(
            self.tr("Open a document before loading a palette."),
            UI_NOTICE_DURATION_MS,
        )

    def _notify_import_error(self, path: str, exc: Exception) -> None:
        """Surface a caught import failure without crashing (UI-007)."""
        QMessageBox.warning(
            self,
            self.tr("Import Failed"),
            self.tr("Could not import %1:\n%2")
            .replace("%1", Path(path).name)
            .replace("%2", str(exc)),
        )

    # -- slots ------------------------------------------------------------

    def _on_tab_changed(self, index: int) -> None:
        # Commit a live float on the view being left before switching (a float is
        # a transient edit state, committed on tool/tab switch — REQ-P2-UI-033).
        if self._active_view is not None:
            self._active_view.commit_active_float()
            # Cancel the outgoing scene's off-thread warm — the transport rebinds
            # to the incoming scene below (D2, no cross-tab warm bleed).
            outgoing = self._active_view.scene()
            if isinstance(outgoing, CanvasScene):
                outgoing.cancel_prewarm()
        record = self.active_tab()
        if record is None:
            self._active_view = None
            # No tab is left to rebind to (the last/only tab just closed) —
            # unbind the timelapse controls explicitly so its existing
            # unconditional _on_stop() teardown (stop timer, release the
            # playback edit lock) still runs; _bind_visual_aids_to_active()
            # below is never reached in this branch, so nothing else stops
            # a still-active in-session playback for a document that no
            # longer has a tab.
            self._timelapse_controls.bind_undo_stack(None)
            self._update_cloud_status()
            return
        self._active_view = record.view
        self._undo_group.setActiveStack(record.stack)
        # Rebind branch recording to the newly-active tab's document, exactly
        # as the undo stack is rebound on the line above (T-DRAW-01) — without
        # this, recording silently switches off the first time the user
        # changes tabs.
        record.view.set_recording(
            self._branching_session.record_traces, record.document
        )
        record.view.set_tool(self._tools[self._active_tool_id])
        record.view.set_active_color(self._active_color)
        record.view.set_active_index(self._active_index)
        self._bind_symmetry_panel(record)
        self._apply_modes_to(record)
        self._bind_palette_workflows(record)
        # Rebind the Phase-9 aids (preview/multi-view/timelapse) to this tab and
        # sync the Aids-menu checkmarks to this tab's overlay state.
        self._bind_visual_aids_to_active()
        # Lazy: defer the buffer scan unless the analytics dock is visible.
        self._analytics_view.request_refresh()
        self._update_cloud_status()

    def _on_tool_action(self) -> None:
        action = self.sender()
        if isinstance(action, QAction):
            record = self.active_tab()
            # Commit a live float before the tool changes (REQ-P2-UI-033).
            if record is not None:
                record.view.commit_active_float()
            self._active_tool_id = action.data()
            if record is not None:
                record.view.set_tool(self._tools[self._active_tool_id])

    def _on_floating_state_changed(self, active: bool, copy: bool) -> None:
        """Update the copy-mode status hint from a view's float state (UI-032/-036)."""
        self._float_active = bool(active)
        self._float_copy = bool(copy)
        self._update_float_hint()

    def _update_float_hint(self) -> None:
        """Show the tr()-wrapped floating move/copy hint while a float is active."""
        if not self._float_active:
            self._float_hint.clear()
            self._float_hint.setVisible(False)
            return
        if self._float_copy:
            self._float_hint.setText(
                self.tr("Copying selection — release, Enter to commit, Esc to cancel")
            )
        else:
            self._float_hint.setText(
                self.tr(
                    "Moving selection — hold Ctrl to copy; "
                    "Enter to commit, Esc to cancel"
                )
            )
        self._float_hint.setVisible(True)

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
        """Retarget paint at the active leaf when the layer panel selects a node.

        A leaf :class:`Layer` becomes the scene's paint/transform target; a group
        selection leaves the paint target unchanged (groups hold no pixels).
        """
        record = self.active_tab()
        if record is None:
            return
        if isinstance(node, Layer):
            record.scene.set_active_layer(node)

    def _on_mask_edit_toggled(self, enabled: bool) -> None:
        """Route paint to the active layer's mask buffer when editing a mask.

        The canvas recomposites with the mask modulating alpha (REQ-P4-UI-009).
        """
        record = self.active_tab()
        if record is not None:
            record.scene.set_mask_edit(enabled)

    # -- palette workflows (REQ-P3-UI-001/-007..-013) --------------------

    def _on_palette_selected_rgba(self, color: RGBA) -> None:
        """Set the active colour from a pick in the editor list."""
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
        """Apply a ramp swatch to the active colour (REQ-P3-UI-007)."""
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
            command = make_constraint_command(
                buffer, palette, mask=mask, target=self._edit_target(record)
            )
        except (QuantizeError, PaletteError) as exc:
            QMessageBox.warning(self, self.tr("Constrain to Palette"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command,
                record.scene.refresh_all,
                self.tr("Constrain to Palette"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
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
            command = make_cycle_command(
                buffer, start, end, step, target=self._edit_target(record)
            )
        except PaletteError as exc:
            QMessageBox.warning(self, self.tr("Colour Cycling"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command,
                record.scene.refresh_all,
                self.tr("Colour Cycle"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
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
            command = make_swap_command(
                buffer,
                mapping,
                record.view.active_selection(),
                target=self._edit_target(record),
            )
        except PaletteError as exc:
            QMessageBox.warning(self, self.tr("Palette Swap"), str(exc))
            return
        record.stack.push(
            LogicCommand(
                command,
                record.scene.refresh_all,
                self.tr("Palette Swap"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
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
                record_trace=self._branching_session.record_traces,
                document=record.document,
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
                command,
                self._mode_switch_rebind(record),
                self.tr("Convert to RGBA"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
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

    def _asset_root(self) -> Path:
        """Return the app asset-store root (``QStandardPaths``, ADR-0051).

        Resolved here in ``ui/`` from ``AppLocalDataLocation`` — the
        non-roaming bulk-data home, deliberately NOT ``AppConfigLocation``
        (ADR-0051 diverges from the Favourites precedent because the CAS is a
        bulk blob store, not a small preference). Falls back to the Qt-free
        ``default_asset_root()`` when Qt names nothing. Side-effect-free: no
        ``mkdir`` here — ``LocalBlobBackend.put_blob`` creates the directory on
        first write, so launching the app never litters the disk.
        """
        base = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        return Path(base) if base else default_asset_root()

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
        right-click and a keyboard Menu-key request (A11Y-COLHUB-1).
        """
        self._colour_hub.set_color(self._active_color)
        record = self.active_tab()
        if record is not None:
            global_pos = record.view.scene_pixel_to_global(x, y)
        else:
            global_pos = QCursor.pos()
        self._colour_hub.popup_at(global_pos)

    def _on_hub_color_applied(self, color: RGBA) -> None:
        """Apply a hub pick immediately to the active swatch (SC-U006-1)."""
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

    # -- cloud (REQ-P10-UI-001..005; Phase-10 Slice A) -------------------

    def _prompt_cloud_project(self, title: str) -> Optional[str]:
        """Prompt for a cloud project name; ``None`` if cancelled/empty."""
        text, ok = QInputDialog.getText(self, title, self.tr("Cloud project name:"))
        if not ok:
            return None
        project_id = text.strip()
        if not project_id:
            QMessageBox.warning(self, title, self.tr("Enter a project name."))
            return None
        return project_id

    def _cloud_requires_connection(self, title: str) -> bool:
        """Return ``True`` if connected; otherwise show a graceful notice."""
        if self._cloud_session.is_connected():
            return True
        QMessageBox.information(
            self, title, self.tr("Connect to a cloud provider first.")
        )
        return False

    def _on_cloud_connect(self) -> None:
        """Connect through the provider-agnostic session (no provider named)."""
        self._cloud_session.connect_provider()

    def _on_cloud_disconnect(self) -> None:
        """Disconnect (release the port); cloud actions gate off connection state."""
        self._cloud_session.disconnect_provider()

    def _on_cloud_connection_changed(self, connected: bool) -> None:
        """Reflect connection state in the cloud action enablement."""
        self._cloud_connect_action.setEnabled(not connected)
        self._cloud_disconnect_action.setEnabled(connected)
        self._cloud_save_action.setEnabled(connected)
        self._cloud_open_action.setEnabled(connected)
        self._cloud_versions_action.setEnabled(connected)
        if not connected:
            self._cloud_last_versions = ()
        self._update_cloud_status()

    def _update_cloud_status(self) -> None:
        """Refresh the Cloud-menu status entry from ``compute_sync_state`` (D-13).

        Read-only: this widget performs no sync-state math, it only asks the
        Qt-free :func:`~pixelart_creator.logic.sync_state.compute_sync_state`
        for the active tab's ``local_version_id`` against the last cached remote
        version list, then displays the tr()-wrapped result. Recomputed on tab
        switch, connection change, and after every cloud save/open/restore.
        """
        record = self.active_tab()
        if record is None or not self._cloud_session.is_connected():
            self._cloud_status_action.setText(self.tr("Cloud status: —"))
            return
        state = compute_sync_state(record.local_version_id, self._cloud_last_versions)
        self._cloud_status_action.setText(self._cloud_status_text(state))

    def _cloud_status_text(self, state: SyncState) -> str:
        """Return the tr()-wrapped Cloud-menu label for a computed sync state."""
        if state is SyncState.UP_TO_DATE:
            return self.tr("Cloud status: Up to date")
        if state is SyncState.LOCAL_AHEAD:
            return self.tr("Cloud status: Not yet saved to cloud")
        if state is SyncState.REMOTE_AHEAD:
            return self.tr("Cloud status: Newer version in cloud")
        return self.tr("Cloud status: Diverged")

    # -- Phase-10 Slice C: real-time + branching (REQ-P10-UI-012/-013) ----

    def _on_realtime_connect(self) -> None:
        """Join the active document's real-time relay (member id prompted once)."""
        title = self.tr("Real-time")
        record = self.active_tab()
        if record is None:
            QMessageBox.information(self, title, self.tr("Open a document first."))
            return
        member_id, ok = QInputDialog.getText(self, title, self.tr("Your member id:"))
        member_id = member_id.strip()
        if not ok or not member_id:
            return
        self._realtime_member_id = member_id
        if record.live_cursors is not None:
            record.live_cursors.set_local_member(member_id)
        self._realtime_session.set_document(record.document)
        # The shared-document id is the active shared project when one is open, else a
        # local id derived from the tab (still hermetic over the loopback transport).
        document_id = self._collab_session.active_project_id() or "local"
        self._realtime_session.connect_realtime(document_id, member_id)

    def _on_realtime_disconnect(self) -> None:
        """Leave the real-time relay (reconnectable; clears the live cursors)."""
        self._realtime_session.disconnect_realtime()
        record = self.active_tab()
        if record is not None and record.live_cursors is not None:
            record.live_cursors.clear()

    def _on_realtime_connection_changed(self, connected: bool) -> None:
        """Reflect the real-time connection state in the action enablement."""
        self._realtime_connect_action.setEnabled(not connected)
        self._realtime_disconnect_action.setEnabled(connected)
        if connected:
            # Auto-show the live-cursor overlay on connect.
            self._live_cursors_action.setChecked(True)

    def _on_realtime_error(self, message: str) -> None:
        """Surface a rejected/failed real-time frame (never a crash — Article VII)."""
        self.statusBar().showMessage(self.tr("Real-time: {msg}").format(msg=message))

    def _on_remote_update_applied(self, regions: object) -> None:
        """Repaint ONLY the tiles a remote CRDT update touched (dirty-rect redraw).

        The document was already mutated in place on the GUI thread by the session
        (:func:`~pixelart_creator.logic.realtime_apply.apply_remote`); here we repaint
        just the reported :class:`~pixelart_creator.logic.realtime_apply.DirtyRegion`
        rects on the active scene (Article VI, ADR-0027 §7 — never a full-scene redraw).
        """
        record = self.active_tab()
        if record is None or not isinstance(regions, (tuple, list)):
            return
        if not regions:
            record.scene.refresh_all()
            return
        for region in regions:
            rect = QRectF(region.x, region.y, region.width, region.height)
            record.scene.refresh_rect(rect)

    def _on_presence_received(self, payload: object) -> None:
        """Route an ephemeral presence payload to the active tab's cursor overlay."""
        record = self.active_tab()
        if record is None or record.live_cursors is None:
            return
        if isinstance(payload, dict):
            record.live_cursors.apply_presence(payload)

    def _on_live_cursors_toggled(self, enabled: bool) -> None:
        """Show/hide the active tab's live-cursor overlay (per-tab view state)."""
        record = self.active_tab()
        if record is not None and record.live_cursors is not None:
            record.live_cursors.setVisible(enabled)

    def _on_branch_document_switched(self, document: object) -> None:
        """Load a switched/merged branch document into the active tab (REQ-P10-UI-012).

        Branching composes whole Qt-free documents (no QUndoCommand, PL10-D13); the
        materialised/merged document is bound to the active scene + rebinds the
        real-time session so later remote updates apply to it.
        """
        record = self.active_tab()
        if record is None or not isinstance(document, Document):
            return
        record.document = document
        record.scene.set_document(document)
        record.scene.refresh_all()
        self._realtime_session.set_document(document)
        # Rebind branch recording to the just-switched/merged document (same
        # T-DRAW-01 seam as tab construction and tab switch) — the branch or
        # mainline document object changes here, so the recording sink must
        # follow it or the next stroke would record against the stale one.
        record.view.set_recording(self._branching_session.record_traces, document)

    def _on_open_diff_requested(self, name: str) -> None:
        """Build + show the modeless pre-merge diff dialog (REQ-P10-UI-014/-025/-026).

        The branching panel names the selected feature branch (``Branching_Panel.
        openDiffRequested``); only this window holds the active tab's live
        ``Document`` (plan §3.2), so it looks both branches up via
        ``Branching_Session.get_branch`` — the selected branch is the diff's
        *source*, the mainline (always ``branch_names()[0]``, ``Branching_Session``'s
        own documented ordering) is the *target* — and hands them to
        ``Branch_Diff_Dialog`` (T16), which computes the divergence and the
        supervision verdict itself, once, at construction. No domain maths happens
        here (Article I): this only looks up and supplies the arguments the pure
        functions/dialog need. The result is also retained on
        ``self._last_supervision`` (unchanged shape) for any other consumer.
        """
        record = self.active_tab()
        if record is None:
            return
        try:
            source_branch = self._branching_session.get_branch(name)
            mainline_name = self._branching_session.branch_names()[0]
            target_branch = self._branching_session.get_branch(mainline_name)
        except RealtimeError:
            return
        self._last_supervision = supervise(source_branch, record.document)
        dialog = Branch_Diff_Dialog(
            name,
            mainline_name,
            source_branch,
            target_branch,
            record.document,
            parent=self,
        )
        dialog.continueToMergeRequested.connect(self._on_branch_diff_continue_to_merge)
        self._branch_diff_dialog = dialog
        dialog.show()

    def _on_branch_diff_continue_to_merge(self, name: str) -> None:
        """Run the shipped merge path from the diff dialog (REQ-P10-UI-018/-019).

        `Branch_Diff_Dialog` performs no merge itself; it only announces which
        branch to merge. This calls the exact same
        ``Branching_Session.merge_to_mainline`` the panel's own Merge button uses
        (no second merge path), then closes the dialog — the merged document
        reaches the active tab via the already-connected ``documentSwitched`` ->
        ``_on_branch_document_switched`` signal, unchanged.
        """
        try:
            self._branching_session.merge_to_mainline(name)
        except RealtimeError as exc:
            QMessageBox.warning(self, self.tr("Merge"), str(exc))
            return
        if self._branch_diff_dialog is not None:
            self._branch_diff_dialog.close()

    def _on_cloud_save(self) -> None:
        """Save the active document to the cloud as a new version (off-thread)."""
        title = self.tr("Save to Cloud")
        if not self._cloud_requires_connection(title):
            return
        record = self.active_tab()
        if record is None:
            QMessageBox.information(self, title, self.tr("Open a document first."))
            return
        project_id = self._prompt_cloud_project(title)
        if project_id is None:
            return
        port = self._cloud_session.port()
        if port is None:
            return
        self._cloud_project_id = project_id
        # Serialise + put run off the GUI thread; the stack is marked clean on the
        # succeeded slot (GUI thread), mirroring save_document's dirty-guard reset.
        self._cloud_controller.submit(
            "save", make_save_job(port, project_id, record.document)
        )

    def _on_cloud_open(self) -> None:
        """Open the latest cloud version of a named project into a new tab."""
        title = self.tr("Open from Cloud")
        if not self._cloud_requires_connection(title):
            return
        project_id = self._prompt_cloud_project(title)
        if project_id is None:
            return
        port = self._cloud_session.port()
        if port is None:
            return
        self._cloud_project_id = project_id
        # list_versions off-thread; the succeeded slot opens the version browser so
        # the user picks a version (the browser drives the actual restore).
        self._cloud_controller.submit(
            "open_list", make_list_versions_job(port, project_id)
        )

    def _on_cloud_versions(self) -> None:
        """Browse the version history of the last-used cloud project (off-thread)."""
        title = self.tr("Cloud Version History")
        if not self._cloud_requires_connection(title):
            return
        project_id = self._cloud_project_id
        if project_id is None:
            project_id = self._prompt_cloud_project(title)
            if project_id is None:
                return
            self._cloud_project_id = project_id
        port = self._cloud_session.port()
        if port is None:
            return
        self._cloud_controller.submit(
            "versions", make_list_versions_job(port, project_id)
        )

    def _on_autosave_tick(self) -> None:
        """Ask the pure autosave policy whether to write the recovery slot.

        Elapsed time is accumulated here and passed as an INPUT to the Qt-free
        :func:`~pixelart_creator.logic.autosave.should_autosave` (REQ-P10-LOGIC-002)
        — the policy reads no clock. On a positive decision the working document is
        written to the port's recovery slot off the GUI thread (distinct from the
        explicit version history, so the last explicit save is never clobbered,
        REQ-P10-DATA-004).
        """
        self._autosave_elapsed_ms += AUTOSAVE_INTERVAL_MS
        record = self.active_tab()
        if record is None:
            return
        dirty = not record.stack.isClean()
        if not should_autosave(
            dirty, self._autosave_elapsed_ms, self._autosave_last_marker
        ):
            return
        self._autosave_last_marker = self._autosave_elapsed_ms
        if not self._cloud_session.is_connected():
            return
        port = self._cloud_session.port()
        if port is None:
            return
        project_id = self._cloud_project_id or _RECOVERY_PROJECT_ID
        self._cloud_controller.submit(
            "autosave", make_autosave_job(port, project_id, record.document)
        )

    def _maybe_prompt_recovery(self) -> None:
        """On startup, offer to restore a discovered recovery slot (REQ-P10-UI-003).

        Only runs when connected and a recovery blob is present; the fetch + decode
        of the recovered document is submitted off the GUI thread on Recover, and
        the reconstructed document opens in a NEW tab (last explicit save intact).
        """
        if not self._cloud_session.is_connected():
            return
        port = self._cloud_session.port()
        if port is None:
            return
        project_id = self._cloud_project_id or _RECOVERY_PROJECT_ID
        try:
            recovery = port.get_recovery(project_id)
        except (
            Exception
        ):  # noqa: BLE001 - a broken recovery slot must not crash startup
            return
        if recovery is None:
            return
        prompt = Recovery_Prompt(self)
        prompt.exec()
        if not prompt.chose_recover():
            return
        # Re-open the autosaved working copy from the RECOVERY SLOT (read via
        # get_recovery, not a version fetch) with the same defensive decode.
        self._cloud_controller.submit("recover", make_recover_job(port, project_id))

    def _on_cloud_succeeded(self, kind: str, result: object) -> None:
        """Consume an off-thread cloud result on the GUI thread (token-filtered)."""
        if kind == "save":
            record = self.active_tab()
            if record is not None:
                record.stack.setClean()
                if isinstance(result, CloudVersion):
                    # D-13: the just-saved version is both the local marker and,
                    # trivially, the whole known remote state — computing sync
                    # from it needs no extra fetch (compute_sync_state is pure).
                    record.local_version_id = result.version_id
                    self._cloud_last_versions = (result,)
            self.statusBar().showMessage(self.tr("Saved to cloud."), 4000)
            self._update_cloud_status()
        elif kind in ("open_list", "versions"):
            self._show_version_browser(result, restore_on_pick=(kind == "open_list"))
        elif kind in ("restore", "recover"):
            if isinstance(result, Document):
                title = (
                    self.tr("Cloud Project")
                    if kind == "restore"
                    else self.tr("Recovered")
                )
                self._add_document_tab(result, title)
                if kind == "restore":
                    restored = self.active_tab()
                    if restored is not None:
                        restored.local_version_id = self._pending_restore_version_id
                self._pending_restore_version_id = None
                self.statusBar().showMessage(self.tr("Restored from cloud."), 4000)
                self._update_cloud_status()

    def _show_version_browser(self, result: object, *, restore_on_pick: bool) -> None:
        """Open the version browser over an off-thread-fetched version list."""
        if not isinstance(result, (tuple, list)):
            return
        versions = tuple(result)
        self._cloud_last_versions = versions
        self._update_cloud_status()
        if not versions:
            QMessageBox.information(
                self,
                self.tr("Cloud Version History"),
                self.tr("No versions found for this project."),
            )
            return
        active = self.active_tab()
        local_version_id = active.local_version_id if active is not None else None
        browser = Version_History_Browser(
            versions, self, local_version_id=local_version_id
        )
        if browser.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = browser.selected_version()
        if chosen is None:
            return
        port = self._cloud_session.port()
        project_id = self._cloud_project_id
        if port is None or project_id is None:
            return
        # Restore is a fresh off-thread get + defensive decode → NEW tab (current
        # unsaved state protected). restore_on_pick distinguishes the open flow's
        # implicit browse from an explicit version browse (both restore identically).
        self._pending_restore_version_id = chosen.version_id
        self._cloud_controller.submit(
            "restore", make_restore_job(port, project_id, chosen.version_id)
        )

    def _on_cloud_failed(self, kind: str, message: str) -> None:
        """Surface a cloud-op failure to the user (never a crash)."""
        QMessageBox.warning(self, self.tr("Cloud"), message)

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

    def _on_symmetry_axis_position_changed(self, pos: object) -> None:
        """Feed the panel's mirror-centre override to every tab's view (D-28)."""
        self._symmetry_axis_pos = pos if isinstance(pos, tuple) else None
        for record in self._tabs_data:
            record.view.set_symmetry_pos(self._symmetry_axis_pos)

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
            buffer,
            lambda b: apply_masked(b, clear_op, mask),
            label=label,
            target=self._edit_target(record),
        )
        dirty = QRectF(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        record.stack.push(
            PaintCommand(
                edit,
                record.scene.refresh_rect,
                dirty,
                text=label,
                invalidate=record.scene.invalidate_group_caches,
                record_trace=self._branching_session.record_traces,
                document=record.document,
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

            record.stack.push(
                LogicCommand(
                    command,
                    rebind,
                    text,
                    record_trace=self._branching_session.record_traces,
                    document=record.document,
                )
            )
        else:
            record.stack.push(
                LogicCommand(
                    command,
                    record.scene.refresh_all,
                    text,
                    record_trace=self._branching_session.record_traces,
                    document=record.document,
                )
            )

    def _apply_transform(
        self, fn: Callable[[PixelBuffer], PixelBuffer], text: str
    ) -> None:
        record = self.active_tab()
        if record is None:
            return
        layer: Layer = record.scene.active_layer()
        mask = record.view.active_selection()
        command = transform.make_transform_command(
            layer, fn, mask, target=self._edit_target(record)
        )
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
        mask = record.view.active_selection()

        def fn(buffer: PixelBuffer) -> PixelBuffer:
            return scale_nearest(buffer, new_w, new_h)

        try:
            command = transform.make_transform_command(
                layer, fn, mask, target=self._edit_target(record)
            )
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
        command = make_rotsprite_command(
            layer, angle, mask, target=self._edit_target(record)
        )
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
        max_edge = _PREVIEW_MAX_EDGE_PX
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

    def _on_user_guide(self) -> None:
        """Open (or raise) the in-app User Guide (REQ-UG-UI-001/-002).

        The viewer is built lazily on first open and reused thereafter. It binds to
        the pure logic/data guide model + defensive reader and requests the active
        UI locale from the LanguageManager, so localised content follows the UI
        language (falling back to the default locale — REQ-UG-UI-011 / CL-3). It is
        parented to this window (disposed with it) and non-modal so the user can keep
        editing while reading.
        """
        if self._user_guide_dialog is None:
            self._user_guide_dialog = User_Guide_Dialog(
                self, locale_provider=self._language_manager.current_language
            )
        dialog = self._user_guide_dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def set_theme(self, name: str) -> None:
        """Switch the theme at runtime and repaint canvas roles (025)."""
        self._theme = name
        apply_theme(self._app, name)
        for record in self._tabs_data:
            self._apply_theme_to_scene(record.scene)
            self._apply_aid_theme(record)
        self._tilemap_canvas.set_theme_colors(*canvas_roles(self._theme))

    def _apply_theme_to_scene(self, scene: CanvasScene) -> None:
        checker_light, checker_dark, grid = canvas_roles(self._theme)
        scene.set_background_roles(checker_light, checker_dark, grid)

    # -- Phase-6 tilemap wiring (REQ-P6-UI-001..013) ---------------------

    def _bind_tilemap(self, record: "_DocTab") -> None:
        """Bind the tileset editor / layer panel / canvas to ``record`` (CL-13).

        The active tileset / tilemap are per-tab view state: kept if still
        attached to the document, else the first attached one (or ``None``). Each
        surface binds to this tab's undo stack so every stamp / layer op pushes
        onto the right :class:`QUndoStack` (state isolation, UI-014).
        """
        doc = record.document
        if self._active_tileset not in doc.tilesets:
            self._active_tileset = doc.tilesets[0] if doc.tilesets else None
        if self._active_tilemap not in doc.tilemaps:
            self._active_tilemap = doc.tilemaps[0] if doc.tilemaps else None
        self._tileset_editor.set_active_color(self._active_color)
        self._tileset_editor.set_active_index(self._active_index)
        self._tileset_editor.set_context(
            self._active_tileset, record.stack, self._refresh_tilemap_canvas
        )
        self._tilemap_layer_panel.set_context(
            self._active_tilemap, record.stack, self._refresh_tilemap_canvas
        )
        self._tilemap_canvas.set_context(self._active_tilemap, record.stack, None)
        self._tilemap_canvas.set_theme_colors(*canvas_roles(self._theme))
        gid = self._tileset_editor.active_gid()
        if gid is not None:
            self._tilemap_canvas.set_brush_gid(gid)

    def _rebind_active_tilemap(self) -> None:
        """Rebind the tilemap surfaces to the active tab (after a structural op)."""
        record = self.active_tab()
        if record is not None:
            self._bind_tilemap(record)

    def _refresh_tilemap_canvas(self) -> None:
        """Repaint the tilemap canvas (linked instances / layer changes)."""
        self._tilemap_canvas.refresh()

    def _on_tileset_tile_changed(self, gid: int) -> None:
        """Point the canvas brush at the tile selected in the tileset editor."""
        self._tilemap_canvas.set_brush_gid(gid)

    def _on_tilemap_layer_changed(self, index: int) -> None:
        """Route the active layer to the canvas + sync the auto-tile checkbox."""
        self._tilemap_canvas.set_active_layer(index)
        self._tilemap_layer_panel.set_autotile_checked(
            self._tilemap_canvas.is_autotile_enabled()
        )

    def _on_autotile_toggled(self, enabled: bool) -> None:
        """Enable/disable Blob-47 auto-tiling on the active layer (mode change)."""
        self._tilemap_canvas.set_autotile_enabled(enabled)

    def _on_tilemap_tool_action(self) -> None:
        """Switch the active tilemap stamping tool (stamp / erase / fill)."""
        action = self.sender()
        if isinstance(action, QAction):
            tool = action.data()
            if isinstance(tool, TilemapTool):
                self._tilemap_canvas.set_tool(tool)

    def _on_new_tileset_from_image(self) -> None:
        """Load an image, slice it into a tileset, attach it to the document."""
        record = self.active_tab()
        if record is None:
            return
        path, _selected = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Tileset Image"),
            "",
            self.tr("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        if not path:
            return
        try:
            source = decode_image(path)
        except ImageImportError as exc:
            QMessageBox.warning(self, self.tr("Open Tileset Image"), str(exc))
            return
        doc = record.document
        first_gid = 1
        for existing in doc.tilesets:
            first_gid = max(first_gid, existing.first_gid + existing.tile_count)
        try:
            tileset = Tileset(source, first_gid=first_gid, name=Path(path).stem)
        except TilesetError as exc:
            QMessageBox.warning(self, self.tr("New Tileset"), str(exc))
            return
        record.stack.push(
            TilesetCommand(
                doc.make_add_tileset_command(tileset),
                self._rebind_active_tilemap,
                self.tr("Add Tileset"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
        )
        if self._active_tilemap is not None:
            record.stack.push(
                TilemapCommand(
                    self._active_tilemap.make_attach_tileset_command(tileset),
                    self._refresh_tilemap_canvas,
                    self.tr("Attach Tileset"),
                    record_trace=self._branching_session.record_traces,
                    document=record.document,
                )
            )
        self._active_tileset = tileset
        self._bind_tilemap(record)

    def _on_new_tilemap(self) -> None:
        """Create an infinite tilemap (with one layer + attached tilesets)."""
        record = self.active_tab()
        if record is None:
            return
        tilemap = Tilemap(name=self.tr("Tilemap"))
        # Build the map's initial contents directly (construction, pre-attach); the
        # whole map is added to the document as one undoable command below.
        tilemap.make_add_layer_command(name=self.tr("Layer 1")).execute()
        for tileset in record.document.tilesets:
            tilemap.make_attach_tileset_command(tileset).execute()
        record.stack.push(
            TilemapCommand(
                record.document.make_add_tilemap_command(tilemap),
                self._rebind_active_tilemap,
                self.tr("Add Tilemap"),
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
        )
        self._active_tilemap = tilemap
        self._bind_tilemap(record)

    def _on_import_tiled(self) -> None:
        """Import a Tiled JSON map into the active document (defensive load)."""
        record = self.active_tab()
        if record is None:
            return
        tilemap = import_tilemap_dialog(self)
        if tilemap is None:
            return
        # Native .pixproj references a tilemap's tilesets by index into the
        # document collection, so register the imported tilesets first. The
        # attach(es) and the tilemap add are one undo unit (CF-15): a single
        # undo removes the imported tilemap AND detaches the imported tilesets.
        label = self.tr("Import Tilemap")
        record.stack.beginMacro(label)
        try:
            for tileset in tilemap.tilesets:
                record.stack.push(
                    TilesetCommand(
                        record.document.make_add_tileset_command(tileset),
                        self._rebind_active_tilemap,
                        self.tr("Attach Tileset"),
                        record_trace=self._branching_session.record_traces,
                        document=record.document,
                    )
                )
            record.stack.push(
                TilemapCommand(
                    record.document.make_add_tilemap_command(tilemap),
                    self._rebind_active_tilemap,
                    label,
                    record_trace=self._branching_session.record_traces,
                    document=record.document,
                )
            )
        finally:
            record.stack.endMacro()
        self._active_tilemap = tilemap
        self._bind_tilemap(record)

    def _on_export_tiled(self) -> None:
        """Export the active tilemap to Tiled JSON (surfaces errors, no crash)."""
        if self._active_tilemap is None:
            QMessageBox.information(
                self,
                self.tr("Export Tiled Map"),
                self.tr("There is no tilemap to export."),
            )
            return
        export_tilemap_dialog(self, self._active_tilemap)

    # -- export (REQ-P7-UI-001, -005, -008, -009, -010) -------------------

    def _on_export(self) -> None:
        """Open the export dialog for the active document (non-destructive).

        Delegates to :func:`~pixelart_creator.ui.export_actions.run_export_dialog`,
        which submits one target to the off-thread export controller. Export is
        read-only — no ``QUndoCommand`` is pushed and ``ui/commands.py`` is
        untouched (REQ-P7-UI-009). The tracked active frame is forwarded so a
        PNG export honours it instead of always frame 0 (CF-18).
        """
        run_export_dialog(
            self,
            self.active_document(),
            self._export_controller,
            frame_index=self._active_frame,
        )

    def _on_export_busy(self, busy: bool) -> None:
        """Reset the per-run result accumulators when a run starts (busyChanged)."""
        if busy:
            self._export_run_failures = []
            self._export_run_ok = 0
            self.statusBar().showMessage(self.tr("Exporting…"))

    def _on_export_progress(self, done: int, total: int, _label: str) -> None:
        """Show non-blocking export progress in the status bar (UI-010)."""
        self.statusBar().showMessage(
            self.tr("Exporting %1 of %2…")
            .replace("%1", str(min(done + 1, total)))
            .replace("%2", str(total))
        )

    def _on_export_target_ok(self, _index: int, _result: object) -> None:
        """Count a successful export target (summarised at run end)."""
        self._export_run_ok += 1

    def _on_export_target_failed(self, _index: int, message: str) -> None:
        """Collect a failed target's message (summarised at run end, UI-008)."""
        self._export_run_failures.append(message)

    def _on_export_finished(self) -> None:
        """Summarise a finished export run: a QMessageBox on any failure (UI-008).

        A single user-facing dialog reports all failed targets (never one popup per
        target and never a crash); a clean run shows a non-blocking status message.
        """
        if self._export_run_failures:
            detail = "\n".join(self._export_run_failures)
            QMessageBox.warning(
                self,
                self.tr("Export Failed"),
                self.tr("%1 export target(s) failed:\n%2")
                .replace("%1", str(len(self._export_run_failures)))
                .replace("%2", detail),
            )
            self.statusBar().clearMessage()
        else:
            self.statusBar().showMessage(
                self.tr("Export complete (%1 file(s)).").replace(
                    "%1", str(self._export_run_ok)
                ),
                UI_NOTICE_DURATION_MS,
            )

    # -- automation (REQ-P8-UI-001..011) ----------------------------------

    def _run_automation_ops(self, ops: List[Op], label: str) -> None:
        """Dispatch DSL ``ops`` on the active document off-thread (UI-004/-006/-007).

        The trusted engine runs on the worker; the resulting reversible command is
        marshalled back to :meth:`_on_automation_result`, which pushes it onto the
        active tab's undo stack as one :class:`AutomationCommand` (the observable
        mutation is strictly GUI-thread). The panels emit inert DSL ops — this
        window never interprets script/plugin content and performs **no**
        ``eval``/``exec`` (Article VII).
        """
        document = self.active_document()
        if document is None or not ops:
            return
        self._pending_automation_ops = list(ops)
        self._pending_automation_label = label
        self._automation_controller.submit(make_dispatch_job(document, list(ops)))

    def _on_replay_requested(self, macro: Macro, label: str) -> None:
        """Replay ``macro`` on the active document as one undoable command (UI-002).

        A replay runs through the same trusted dispatcher and lands on the undo
        stack exactly like a script run; it is not itself re-recorded, so the
        pending-op capture is cleared.
        """
        document = self.active_document()
        if document is None:
            return
        self._pending_automation_ops = None
        self._pending_automation_label = label
        self._automation_controller.submit(make_replay_job(document, macro))

    def _on_automation_result(self, command: Command) -> None:
        """Push a completed automation edit onto the active undo stack (UI-009).

        The worker returns one **unapplied** reversible command with the document
        restored to its pre-run state; wrapping it in a single
        :class:`AutomationCommand` and pushing it applies it on the GUI thread as
        exactly one undoable step. If a recording is active and this run was a
        script / batch / procgen (not a replay), its DSL ops are captured into the
        recording (REQ-P8-LOGIC-004).
        """
        record = self.active_tab()
        if record is None or command is None:
            return
        label = self._pending_automation_label or self.tr("Automation")
        record.stack.push(
            AutomationCommand(
                command,
                record.scene.refresh_all,
                label,
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
        )
        if self._macro_controls.is_recording() and self._pending_automation_ops:
            self._macro_controls.add_recorded_ops(self._pending_automation_ops)
        self._pending_automation_ops = None

    def _on_automation_failed(self, message: str) -> None:
        """Surface a failed / denied / bounded automation run gracefully (UI-008).

        No command is pushed, so the document is left uncorrupted from the undo
        stack's perspective (the worker restores the document before returning; a
        failing dispatch returns no command). A malformed input never executes.
        """
        self._pending_automation_ops = None
        QMessageBox.warning(self, self.tr("Automation Error"), message)

    def _on_automation_busy(self, busy: bool) -> None:
        """Guard the undo stack + surface run status while an automation is live.

        Undo / redo are disabled during the brief off-thread run so the GUI thread
        cannot mutate the document concurrently with the worker; a non-blocking
        status message reflects the run. Also respects a live timelapse playback
        lock (``self._playback_locked``, REQ-P9-UI-016) so this handler can never
        re-enable undo/redo out from under it.
        """
        self._undo_action.setEnabled(
            not busy and not self._playback_locked and self._can_undo()
        )
        self._redo_action.setEnabled(
            not busy and not self._playback_locked and self._can_redo()
        )
        if busy:
            self.statusBar().showMessage(self.tr("Running automation…"))
        else:
            self.statusBar().clearMessage()

    def _can_undo(self) -> bool:
        record = self.active_tab()
        return record is not None and record.stack.canUndo()

    def _can_redo(self) -> bool:
        record = self.active_tab()
        return record is not None and record.stack.canRedo()

    def _bind_automation(self, record: "_DocTab") -> None:
        """Point the procgen / batch panels at the active document (view state)."""
        self._batch_recolour_panel.set_frame_count(len(record.document.frames))

    # -- AI assistant (REQ-P14-UI-001..004) -------------------------------

    def _assistant_backend(self) -> Optional[ChatBackend]:
        """Build the current assistant backend from the persisted config (or ``None``).

        Probed fresh by the dock on each send so a configuration change takes effect
        immediately. Returns a provider-agnostic ``data/llm`` adapter (an
        :class:`~pixelart_creator.logic.assistant.ChatBackend`) or ``None`` when no
        provider is configured — the dock degrades to a clear "not configured" state.
        No provider is named here and no key is handled: construction is cheap and the
        key is read lazily from the OS keyring inside ``data/llm`` at request time
        (REQ-P14-DATA-006/-007).
        """
        config = load_config()
        if config is None:
            return None
        return build_backend(config)

    def _on_assistant_edits(self, commands: object, label: str) -> None:
        """Push one assistant turn's edits onto the active undo stack (UI-003).

        The worker restored the live document and marshalled back the turn's ordered
        **unapplied** commands; wrapping them in a single :class:`AssistantCommand` and
        pushing it applies them on the GUI thread as exactly one undoable step (the
        observable mutation is strictly GUI-thread). A chat-only turn produces no
        command and reaches here with an empty sequence (nothing is pushed).
        """
        record = self.active_tab()
        if record is None or not commands:
            return
        text = label or self.tr("Assistant edit")
        turn_commands = tuple(cast(Sequence[Command], commands))
        record.stack.push(
            AssistantCommand(
                turn_commands,
                record.scene.refresh_all,
                text,
                record_trace=self._branching_session.record_traces,
                document=record.document,
            )
        )

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("PixelArt Creator"))
        self._toolbar.setWindowTitle(self.tr("Tools"))
        self._palette_dock.setWindowTitle(self.tr("Palette"))
        self._symmetry_dock.setWindowTitle(self.tr("Symmetry"))
        self._layer_dock.setWindowTitle(self.tr("Layers"))
        self._timeline_dock.setWindowTitle(self.tr("Timeline"))
        self._onion_dock.setWindowTitle(self.tr("Onion Skin"))
        self._tags_dock.setWindowTitle(self.tr("Frame Tags"))
        self._editor_dock.setWindowTitle(self.tr("Palette Editor"))
        self._constraint_dock.setWindowTitle(self.tr("Constraints"))
        self._ramp_dock.setWindowTitle(self.tr("Shade Ramps"))
        self._cycling_dock.setWindowTitle(self.tr("Colour Cycling"))
        self._analytics_dock.setWindowTitle(self.tr("Analytics"))
        self._tileset_dock.setWindowTitle(self.tr("Tileset Editor"))
        self._tilemap_layer_dock.setWindowTitle(self.tr("Tilemap Layers"))
        self._tilemap_dock.setWindowTitle(self.tr("Tilemap Canvas"))
        self._batch_dock.setWindowTitle(self.tr("Batch Export"))
        self._macro_dock.setWindowTitle(self.tr("Macros"))
        self._script_dock.setWindowTitle(self.tr("Script Runner"))
        self._plugin_dock.setWindowTitle(self.tr("Plugins"))
        self._batch_recolour_dock.setWindowTitle(self.tr("Batch Recolour"))
        self._procgen_dock.setWindowTitle(self.tr("Procedural Generation"))
        self._shared_dock.setWindowTitle(self.tr("Shared Projects"))
        self._comments_dock.setWindowTitle(self.tr("Comments"))
        self._presence_dock.setWindowTitle(self.tr("Presence"))
        self._branching_dock.setWindowTitle(self.tr("Branching"))
        self._asset_library_dock.setWindowTitle(self.tr("Asset Library"))
        self._asset_search_dock.setWindowTitle(self.tr("Asset Search"))
        self._asset_tagging_dock.setWindowTitle(self.tr("Asset Tagging"))
        self._dependency_dock.setWindowTitle(self.tr("Dependency Graph"))
        self._version_browser_dock.setWindowTitle(self.tr("Asset Versions"))
        self._reuse_dock.setWindowTitle(self.tr("Asset Reuse"))
        # Phase-9 aid docks: without a windowTitle their Aids-menu toggleViewAction
        # renders blank and never retranslates. Reuse each widget's own catalogue
        # title ("Real-Size Preview" / "Timelapse") so the toggles are labelled.
        self._preview_dock.setWindowTitle(self.tr("Real-Size Preview"))
        self._timelapse_dock.setWindowTitle(self.tr("Timelapse"))
        self._timelapse_frame_view_dock.setWindowTitle(self.tr("Reopened Recording"))
        self._tab_widget.setAccessibleName(self.tr("Open documents"))
        self._float_hint.setAccessibleName(self.tr("Floating selection status"))
        self._update_float_hint()

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
        self._export_action.setText(self.tr("&Export…"))
        self._close_action.setText(self.tr("&Close"))

        self._cloud_connect_action.setText(self.tr("&Connect…"))
        self._cloud_disconnect_action.setText(self.tr("&Disconnect"))
        self._cloud_save_action.setText(self.tr("&Save to Cloud…"))
        self._cloud_open_action.setText(self.tr("&Open from Cloud…"))
        self._cloud_versions_action.setText(self.tr("&Version History…"))
        self._update_cloud_status()
        self._realtime_connect_action.setText(self.tr("Start &Real-time…"))
        self._realtime_disconnect_action.setText(self.tr("Stop Real-&time"))
        self._live_cursors_action.setText(self.tr("Show &Live Cursors"))
        self._zoom_in_action.setText(self.tr("Zoom &In"))
        self._zoom_out_action.setText(self.tr("Zoom &Out"))
        self._fit_action.setText(self.tr("&Fit to View"))
        self._grid_action.setText(self.tr("Show &Grid"))
        self._snap_action.setText(self.tr("&Snap to Grid"))
        self._aa_off_action.setText(self.tr("&Anti-aliasing Off"))
        self._tiled_action.setText(self.tr("&Tiled Mode"))
        self._theme_light_action.setText(self.tr("Light"))
        self._theme_dark_action.setText(self.tr("Dark"))

        self._new_tileset_action.setText(self.tr("New Tileset from Image…"))
        self._new_tilemap_action.setText(self.tr("New Tilemap"))
        self._import_tiled_action.setText(self.tr("Import Tiled JSON…"))
        self._export_tiled_action.setText(self.tr("Export Tiled JSON…"))
        self._stamp_action.setText(self.tr("Stamp Tool"))
        self._stamp_action.setToolTip(self.tr("Place the selected tile"))
        self._erase_tile_action.setText(self.tr("Tile Eraser"))
        self._erase_tile_action.setToolTip(self.tr("Clear the target cell"))
        self._fill_tile_action.setText(self.tr("Rectangle Fill"))
        self._fill_tile_action.setToolTip(
            self.tr("Fill a dragged rectangle with the selected tile")
        )
        self._stamp_flip_h_action.setText(self.tr("Flip Stamp Horizontal"))
        self._stamp_flip_v_action.setText(self.tr("Flip Stamp Vertical"))
        self._stamp_rotate_action.setText(self.tr("Rotate Stamp 90° CW"))

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

        self._guides_action.setText(self.tr("Guides && &Rulers"))
        self._iso_action.setText(self.tr("&Isometric Grid"))
        self._iso_config_action.setText(self.tr("Configure &Isometric Grid…"))
        self._perspective_action.setText(self.tr("&Perspective Grid"))
        self._perspective_config_action.setText(self.tr("Configure &Perspective…"))
        self._new_view_action.setText(self.tr("&New View"))
        self._reference_board_action.setText(self.tr("Reference &Board"))

        self._file_menu.setTitle(self.tr("&File"))
        self._edit_menu.setTitle(self.tr("&Edit"))
        self._select_menu.setTitle(self.tr("&Select"))
        self._image_menu.setTitle(self.tr("&Image"))
        self._view_menu.setTitle(self.tr("&View"))
        self._aids_menu.setTitle(self.tr("&Aids"))
        self._palette_menu.setTitle(self.tr("&Palette"))
        self._tilemap_menu.setTitle(self.tr("Tile&map"))
        self._automation_menu.setTitle(self.tr("&Automation"))
        self._cloud_menu.setTitle(self.tr("&Cloud"))
        self._library_menu.setTitle(self.tr("&Library"))
        self._theme_menu.setTitle(self.tr("&Theme"))
        self._language_menu.setTitle(self.tr("&Language"))
        self._help_menu.setTitle(self.tr("&Help"))
        self._user_guide_action.setText(self.tr("&User Guide"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the main-window strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
