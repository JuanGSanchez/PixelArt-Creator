# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Timeline grid view — frames (columns) x layer-tracks (rows).

REQ-P5-UI-022..025, -027..-031. ``Timeline_Grid_View`` is a ``QTableView`` +
``QAbstractTableModel`` adapter over the pure, Qt-free ``logic/track_table.py``
derivation (REQ-P5-LOGIC-015). The choice is
load-bearing, not cosmetic (plan §2, ADR-0057): Qt calls ``data()`` only for the
exposed viewport, which **is** REQ-P5-UI-030's culling rather than a hand-rolled one;
the table gives native row/column/count semantics to assistive technology
(REQ-P5-UI-027); and the ``QHeaderView`` is a **structurally separate** widget whose
drag Qt itself never routes to the body — the direct fix for CF-56's "one gesture,
two claimants, no test" defect.

Three gesture zones, disjoint by construction (REQ-P5-UI-025):

- **Header** — ``QHeaderView.setSectionsMovable(True)`` is Qt's own reorder; this
  view only translates the resulting ``sectionMoved`` into one
  ``make_move_frame_command`` (REQ-P5-UI-005) and puts the header back to logical
  order (the document, not the header's transient visual state, is the single
  source of truth).
- **Occupied cell** — a left-press-drag starting on a cell holding a node moves it;
  ``Ctrl`` held copies it (the product's own fixed drag-to-copy convention,
  ``phase-2-floating-selection`` ``REQ-P2-UI-032``) — one ``FrameCommand`` wrapping
  ``Document.make_move_cel_command`` / ``make_copy_cel_command`` (REQ-P5-LOGIC-016).
  A drop onto a non-empty destination is confirmed first
  (:class:`~pixelart_creator.ui.cel_overwrite_dialog.Cel_Overwrite_Dialog`,
  REQ-P5-UI-033), unless the current project's preference registry says
  "suppressed" (``logic/project_prefs.py``, ADR-0056).
- **Body away from any occupied cell** — scrubs: :data:`frameScrubbed` follows the
  cursor's column and pushes **no** command (REQ-P5-UI-002 semantics, reused).

Per-cell visibility (REQ-P5-UI-024) is exactly one ``FrameCommand`` wrapping the
shipped ``Document.set_layer_visible`` for that cell's frame. Selection
(REQ-P5-UI-023) mutates nothing.

The empty-cell **"create a cel here"** affordance (REQ-P5-UI-031) is a
context-menu action reached at an empty cell — mouse right-click or the
platform's own context-menu key/chord (``Shift+F10`` / the ``Menu`` key), which
``QAbstractItemView`` already routes to the current index with no extra code,
so the affordance is pointer- *and* keyboard-reachable by construction
(REQ-P5-UI-027) without inventing a second gesture on top of the drag zones in
REQ-P5-UI-025. It calls the shipped
``Document.make_create_cel_command(frame_index, track_id)`` and pushes exactly
one ``FrameCommand``, exactly like the move/copy path above. Per the
"offered-then-refuses is worse than correctly absent" rule, the menu **is not
built at all** when the destination cell is occupied (the factory's own
outright refusal) or when the destination frame is already at
``MAX_LAYERS_PER_FRAME`` (the factory's other outright refusal) — both are
checked before the menu is shown, not caught after the click.

Strings are ``tr()``-wrapped and re-set on ``QEvent.Type.LanguageChange``
(REQ-P5-UI-029); every colour is a theme role, never hard-coded (REQ-P5-UI-028); no
domain logic lives here (Article I / S11) — this view only calls into
``logic/track_table.py`` and ``logic/document.py``.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np
from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QPoint,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QIcon, QImage, QPalette, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QMenu,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import MAX_LAYERS_PER_FRAME
from pixelart_creator.logic.document import (
    Document,
    DocumentError,
    Layer,
    LayerGroup,
    LayerNode,
    iter_layers,
)
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.project_prefs import CONFIRM_CEL_OVERWRITE
from pixelart_creator.logic.track_table import EMPTY_CELL, Cell, TrackTable, track_table
from pixelart_creator.ui.cel_overwrite_dialog import Cel_Overwrite_Dialog

#: Longest edge (px) of a cached per-cell thumbnail. Mirrors
#: ``timeline_panel._THUMBNAIL_EDGE`` exactly (visual consistency between the two
#: cell surfaces the toggle swaps between); a presentation-only sizing literal,
#: not a domain tuning value (Article II does not reach it, like its strip twin).
_THUMBNAIL_EDGE = 48

#: Custom data roles carried on every cell, alongside the standard Qt roles.
_TRACK_ID_ROLE = Qt.ItemDataRole.UserRole + 1
_EMPTY_ROLE = Qt.ItemDataRole.UserRole + 2

Path = Tuple[int, ...]


def _find_path(
    nodes: Sequence["LayerNode"], target: "LayerNode", prefix: Path = ()
) -> Optional[Path]:
    """Depth-first identity search for ``target``'s address within ``nodes``.

    Structural addressing only (no domain decision, S11) — the same identity-walk
    idiom ``ui/layer_panel.py`` builds while constructing its tree rows. Needed
    because ``Document.set_layer_visible`` takes a path, while the track table
    hands the view the node object itself.
    """
    for index, node in enumerate(nodes):
        if node is target:
            return prefix + (index,)
        if isinstance(node, LayerGroup):
            found = _find_path(node.children, target, prefix + (index,))
            if found is not None:
                return found
    return None


def _node_to_image(buffer: PixelBuffer, palette_colors: List[RGBA]) -> QImage:
    """Convert one node's own buffer to an owned RGBA ``QImage``.

    Mirrors ``timeline_panel._buffer_to_image`` exactly (REQ-P5-UI-022: "a
    thumbnail rendered by the same path the strip uses, including the indexed
    document path"). Duplicated locally rather than imported because the strip's
    helper is private to that module.
    """
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


class _Track_Table_Model(QAbstractTableModel):
    """Read-only adapter: REQ-P5-LOGIC-015's ``TrackTable`` -> Qt's table protocol.

    Columns are document frames; rows are the table's tracks. Every value shown —
    label, thumbnail, visibility check state, accessible text — is read fresh from
    the bound :class:`Document` and the track table derived from it; the model
    never becomes a second source of truth (REQ-P5-UI-022).
    """

    visibilityToggleRequested = Signal(int, int, bool)  # frame_index, row, value

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._table: TrackTable = TrackTable(rows=())

    # -- binding ------------------------------------------------------------

    def bind(self, document: Optional[Document], active_frame: int) -> None:
        """Re-derive the whole table for ``document`` at ``active_frame``."""
        self.beginResetModel()
        self._document = document
        if document is not None and document.frames:
            frame = max(0, min(active_frame, len(document.frames) - 1))
            self._table = track_table(document, active_frame=frame)
        else:
            self._table = TrackTable(rows=())
        self.endResetModel()

    def retranslate(self) -> None:
        """Re-emit header/cell text after a language change (F5)."""
        if self.rowCount() and self.columnCount():
            self.headerDataChanged.emit(
                Qt.Orientation.Horizontal, 0, self.columnCount() - 1
            )
            self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, self.rowCount() - 1)
            top_left = self.index(0, 0)
            bottom_right = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top_left, bottom_right)

    def table(self) -> TrackTable:
        """Return the currently-bound track table."""
        return self._table

    # -- Qt table protocol ---------------------------------------------------

    def rowCount(  # type: ignore[override]  # noqa: N802
        self, parent: QModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._table.rows)

    def columnCount(  # type: ignore[override]  # noqa: N802
        self, parent: QModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid() or self._document is None:
            return 0
        return len(self._document.frames)

    def cell_at(self, row: int, column: int) -> Cell:
        """Return the cell content at ``(row, column)``, or :data:`EMPTY_CELL`."""
        if not 0 <= row < len(self._table.rows):
            return EMPTY_CELL
        cells = self._table.rows[row].cells
        if not 0 <= column < len(cells):
            return EMPTY_CELL
        return cells[column]

    def track_id_at(self, row: int) -> Optional[int]:
        """Return the stable ``layer_id`` for ``row``, or ``None`` if out of range."""
        if not 0 <= row < len(self._table.rows):
            return None
        return self._table.rows[row].layer_id

    def data(  # type: ignore[override]  # noqa: N802
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid():
            return None
        row_obj = self._table.rows[index.row()]
        cell = self.cell_at(index.row(), index.column())
        occupied = cell is not EMPTY_CELL
        frame_label = self.tr("Frame %1").replace("%1", str(index.column() + 1))
        if role == Qt.ItemDataRole.CheckStateRole and occupied:
            visible = bool(getattr(cell, "visible", True))
            return (
                Qt.CheckState.Checked.value
                if visible
                else Qt.CheckState.Unchecked.value
            )
        if (
            role == Qt.ItemDataRole.DecorationRole
            and occupied
            and isinstance(cell, Layer)
        ):
            return self._thumbnail(cell)
        if role == Qt.ItemDataRole.ToolTipRole:
            if occupied:
                return (
                    self.tr("%1, %2")
                    .replace("%1", frame_label)
                    .replace("%2", row_obj.label)
                )
            return (
                self.tr("%1, %2 — empty")
                .replace("%1", frame_label)
                .replace("%2", row_obj.label)
            )
        if role == Qt.ItemDataRole.AccessibleTextRole:
            if occupied:
                return (
                    self.tr("%1, track %2")
                    .replace("%1", frame_label)
                    .replace("%2", row_obj.label)
                )
            return (
                self.tr("%1, track %2, empty")
                .replace("%1", frame_label)
                .replace("%2", row_obj.label)
            )
        if role == Qt.ItemDataRole.AccessibleDescriptionRole:
            return self.tr("Occupied cell") if occupied else self.tr("Empty cell")
        if role == _TRACK_ID_ROLE:
            return row_obj.layer_id
        if role == _EMPTY_ROLE:
            return not occupied
        return None

    def setData(  # type: ignore[override]  # noqa: N802
        self, index: QModelIndex, value: object, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if role == Qt.ItemDataRole.CheckStateRole and index.isValid():
            cell = self.cell_at(index.row(), index.column())
            if cell is not EMPTY_CELL:
                checked = value in (
                    Qt.CheckState.Checked,
                    Qt.CheckState.Checked.value,
                    int(Qt.CheckState.Checked.value),
                )
                self.visibilityToggleRequested.emit(
                    index.column(), index.row(), checked
                )
            # The document is the single source of truth (REQ-P5-UI-022); this
            # model never mutates itself — the view rebinds after the command.
            return False
        return False

    def flags(  # type: ignore[override]  # noqa: N802
        self, index: QModelIndex
    ) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self.cell_at(index.row(), index.column()) is not EMPTY_CELL:
            base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if orientation == Qt.Orientation.Horizontal:
            if self._document is None or not 0 <= section < len(self._document.frames):
                return None
            duration_ms = self._document.frames[section].duration_ms
            if role == Qt.ItemDataRole.DisplayRole:
                return (
                    self.tr("%1\n%2 ms")
                    .replace("%1", str(section + 1))
                    .replace("%2", str(duration_ms))
                )
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return (
                    self.tr("Frame %1, %2 milliseconds")
                    .replace("%1", str(section + 1))
                    .replace("%2", str(duration_ms))
                )
            return None
        if not 0 <= section < len(self._table.rows):
            return None
        row_obj = self._table.rows[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return row_obj.label
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return self.tr("Track %1").replace("%1", row_obj.label)
        return None

    # -- thumbnails -----------------------------------------------------------

    def _thumbnail(self, node: Layer) -> QIcon:
        if self._document is None:
            return QIcon()
        try:
            image = _node_to_image(node.buffer, self._document.palette.colors())
        except (ValueError, AttributeError):
            return QIcon()
        scaled = image.scaled(
            _THUMBNAIL_EDGE,
            _THUMBNAIL_EDGE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,  # nearest-neighbour
        )
        return QIcon(QPixmap.fromImage(scaled))


class _Grid_Delegate(QStyledItemDelegate):
    """Paints an empty cell visibly and accessibly distinct (REQ-P5-UI-022/-028).

    Colour is read from the active theme's own role (``AlternateBase``), never a
    hard-coded value, so the distinction reads correctly in both themes.
    """

    def paint(  # type: ignore[override]  # noqa: N802
        self, painter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        if bool(index.data(_EMPTY_ROLE)):
            painter.save()
            painter.fillRect(
                option.rect,
                option.palette.color(
                    QPalette.ColorGroup.Normal, QPalette.ColorRole.AlternateBase
                ),
            )
            painter.restore()
        super().paint(painter, option, index)


class Timeline_Grid_View(QTableView):
    """Frames x layer-tracks matrix, the grid's optional cell surface."""

    #: Emitted with the frame index a selection (of any kind) settled on
    #: (REQ-P5-UI-023). Pushes no command.
    frameActivated = Signal(int)
    #: Emitted with the ``layer_id`` a cell/row-header selection settled on
    #: (REQ-P5-UI-023). Pushes no command.
    layerActivated = Signal(int)
    #: Emitted with the frame index the cursor is scrubbing over during a body
    #: drag away from any occupied cell (REQ-P5-UI-025). Pushes no command.
    frameScrubbed = Signal(int)
    #: Emitted when a Ctrl+right-click removal was refused because the target
    #: document has only one frame left (D-22). ``Document._ensure_frame_removable``
    #: is the single, unconditional owner of that invariant; this view asks the
    #: bound document itself (``len(document.frames)``) rather than keeping a
    #: second, independently-maintained notion of "removable" — so the two can
    #: never drift apart. Pushes no command; the gesture stays inert.
    lastFrameRemovalRefused = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Wire the table/model/delegate and the three disjoint gesture zones.

        Binds an empty :class:`_Track_Table_Model`, disables Qt's own
        drag-and-drop on the body so the hand-discriminated cell gestures
        are the only claimant, enables the header's own reorder drag
        (CF-56 fix), and connects header/cell click signals to their
        handlers. No document is attached yet — that happens through
        :meth:`set_context`.
        """
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._stack: Optional[QUndoStack] = None
        self._push: Optional[Callable[[Command, str], None]] = None
        self._active_frame = 0

        self._model = _Track_Table_Model(self)
        self.setModel(self._model)
        self.setItemDelegate(_Grid_Delegate(self))

        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Body/cell gestures are hand-discriminated (indexAt + occupancy);
        # Qt's own DnD must not also claim the body.
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setMouseTracking(True)
        self.setIconSize(QSize(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE))

        header = self.horizontalHeader()
        header.setSectionsMovable(True)  # Qt's own header-drag zone (CF-56 fix).
        header.sectionMoved.connect(self._on_header_section_moved)
        header.sectionClicked.connect(self._on_frame_header_clicked)
        vheader = self.verticalHeader()
        vheader.sectionClicked.connect(self._on_track_header_clicked)

        self.clicked.connect(self._on_cell_clicked)
        self._model.visibilityToggleRequested.connect(self._on_visibility_toggle)

        # Empty-cell "create a cel here" affordance (REQ-P5-UI-031): a context
        # menu, reached by right-click OR the platform context-menu key/chord —
        # QAbstractItemView already routes the latter to the current index, so
        # this is keyboard-reachable (REQ-P5-UI-027) with no extra key handling.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu_requested)

        # Gesture-drag state: press position/index, whether the press
        # landed on an occupied cell, and whether the movement threshold fired.
        self._press_pos: Optional[QPoint] = None
        self._press_index: Optional[QModelIndex] = None
        self._press_occupied = False
        self._dragging = False

        self._retranslate()

    # -- context --------------------------------------------------------------

    def set_context(
        self,
        document: Optional[Document],
        stack: Optional[QUndoStack],
        active_frame: int,
        push: Callable[[Command, str], None],
    ) -> None:
        """Bind the grid to a document + its undo stack + the owner's push path.

        ``push`` is the owner's (``Timeline_Panel``) single ``FrameCommand`` push
        path — this view builds no ``QUndoCommand`` of its own kind; every
        mutation it originates is wrapped exactly like a strip frame op.
        """
        self._document = document
        self._stack = stack
        self._push = push
        self._active_frame = active_frame
        self._model.bind(document, active_frame)
        self._restore_current_index()

    def set_active_frame(self, index: int) -> None:
        """Re-derive the table for a new active frame (row order depends on it)."""
        self._active_frame = index
        if self._document is not None:
            self._model.bind(self._document, index)
        self._restore_current_index()

    def rebuild(self) -> None:
        """Rebuild the whole table from the document (after any op, undo/redo)."""
        self._model.bind(self._document, self._active_frame)
        self._restore_current_index()

    def _restore_current_index(self) -> None:
        column = self._active_frame
        if 0 <= column < self._model.columnCount():
            row = max(0, min(self.currentIndex().row(), self._model.rowCount() - 1))
            if self._model.rowCount() > 0:
                self.setCurrentIndex(self._model.index(row, column))

    # -- selection (REQ-P5-UI-023, mutates nothing) ---------------------------

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        column = index.column()
        self._active_frame = column
        self.frameActivated.emit(column)
        cell = self._model.cell_at(index.row(), column)
        if cell is not EMPTY_CELL:
            track_id = self._model.track_id_at(index.row())
            if track_id is not None:
                self.layerActivated.emit(track_id)

    def _on_frame_header_clicked(self, section: int) -> None:
        self._active_frame = section
        self.frameActivated.emit(section)

    def _on_track_header_clicked(self, section: int) -> None:
        # Refused when the active frame has no node on this track (REQ-P5-UI-023):
        # the grid never reports a selection the document cannot hold.
        if self._model.cell_at(section, self._active_frame) is EMPTY_CELL:
            return
        track_id = self._model.track_id_at(section)
        if track_id is not None:
            self.layerActivated.emit(track_id)

    # -- per-cell visibility (REQ-P5-UI-024, one FrameCommand) -----------------

    def _on_visibility_toggle(
        self, frame_index: int, row: int, new_visible: bool
    ) -> None:
        if self._document is None or self._push is None:
            return
        table = self._model.table()
        if not 0 <= row < len(table.rows):
            return
        if not 0 <= frame_index < len(table.rows[row].cells):
            return
        node = table.rows[row].cells[frame_index]
        if node is EMPTY_CELL:
            return
        frame = self._document.frames[frame_index]
        path = _find_path(frame.layers, node)  # type: ignore[arg-type]
        if path is None:
            return
        try:
            cmd = self._document.set_layer_visible(
                list(path), new_visible, frame_index=frame_index
            )
        except DocumentError:
            self.rebuild()
            return
        self._push(cmd, self.tr("Toggle Cel Visibility"))

    # -- empty-cell "create a cel here" (REQ-P5-UI-031, one FrameCommand) ------

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        if self._document is None or self._push is None:
            return
        index = self.indexAt(pos)
        if not index.isValid():
            index = self.currentIndex()
        if not index.isValid():
            return
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl+right-click removes the frame under the cursor — the ONE
            # destructive gesture in the spec, confined to this timeline
            # surface (REQ-IS-UI-017); applies regardless of whether the cell
            # under the cursor happens to be occupied, so it is checked before
            # the empty-cell "Create Cel Here" affordance below.
            self._remove_frame_at(index.column())
            return
        if self._model.cell_at(index.row(), index.column()) is not EMPTY_CELL:
            # No affordance is offered for an occupied cell today — the drag
            # gestures above already cover it (REQ-P5-UI-025).
            return
        frame_index = index.column()
        if not 0 <= frame_index < len(self._document.frames):
            return
        track_id = self._model.track_id_at(index.row())
        if track_id is None:
            return
        frame = self._document.frames[frame_index]
        if len(iter_layers(frame.layers)) >= MAX_LAYERS_PER_FRAME:
            # The factory would refuse outright; an offered-then-refused action
            # is worse than a correctly absent one, so nothing is shown.
            return
        menu = QMenu(self)
        create_action = QAction(self.tr("Create Cel Here"), menu)
        create_action.setToolTip(
            self.tr("Create a new drawing on this track in this frame")
        )
        create_action.triggered.connect(
            lambda: self._create_cel_here(frame_index, track_id)
        )
        menu.addAction(create_action)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _create_cel_here(self, frame_index: int, track_id: int) -> None:
        if self._document is None or self._push is None:
            return
        try:
            cmd = self._document.make_create_cel_command(
                frame_index=frame_index, track_id=track_id
            )
        except DocumentError:
            self.rebuild()
            return
        self._push(cmd, self.tr("Create Cel"))

    # -- Ctrl+right-click removes a frame, timeline-only (REQ-IS-UI-017) -------

    def _remove_frame_at(self, frame_index: int) -> None:
        """Remove ``frame_index`` via the shipped undoable command.

        On the document's last remaining frame the gesture is inert by
        invariant (``Document._ensure_frame_removable`` is the single,
        unconditional owner of "never remove the document's last frame") —
        so asking Yes/No there would ask a question whose answer cannot
        change the outcome (D-22). This checks the SAME source of truth the
        domain does, ``document.frames`` itself, not a second,
        independently-maintained notion of "removable"; on that condition it
        emits :data:`lastFrameRemovalRefused` for the owner to surface as a
        transient status-bar explanation and returns without removing
        anything or building a command.

        On every other frame the removal proceeds exactly as before: no
        confirmation, straight through ``make_remove_frame_command``.
        """
        document = self._document
        if document is None or self._push is None:
            return
        if not 0 <= frame_index < len(document.frames):
            return
        if len(document.frames) <= 1:
            self.lastFrameRemovalRefused.emit()
            return
        try:
            cmd = document.make_remove_frame_command(frame_index)
        except DocumentError:
            return
        self._push(cmd, self.tr("Remove Frame"))

    # -- header drag = reorder (REQ-P5-UI-025) --------------------------------

    def _on_header_section_moved(
        self, _logical: int, old_visual: int, new_visual: int
    ) -> None:
        header = self.horizontalHeader()
        # Qt has already reordered its own view-only visual mapping; the document
        # stays the single source of truth, so the visual mapping is put back and
        # a real move command is built and pushed (mirrors
        # ``timeline_panel._on_rows_moved``).
        header.blockSignals(True)
        header.moveSection(new_visual, old_visual)
        header.blockSignals(False)
        if self._document is None or self._push is None or old_visual == new_visual:
            return
        if not 0 <= new_visual < len(self._document.frames):
            return
        try:
            cmd = self._document.make_move_frame_command(old_visual, new_visual)
        except DocumentError:
            return
        self._active_frame = new_visual
        self._push(cmd, self.tr("Reorder Frame"))

    # -- occupied-cell drag = move/copy; body drag = scrub (REQ-P5-UI-025/-031) --

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Record the press cell and whether it is occupied, arming a possible drag.

        A left press over a valid cell captures the press position, the
        pressed index, and whether that cell already holds a node
        (``self._press_occupied``) — this is what later distinguishes an
        occupied-cell move/copy drag from an empty-body scrub once
        :meth:`mouseMoveEvent` crosses the drag-distance threshold. No drag
        starts here; ``self._dragging`` is reset to ``False``.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self._press_pos = event.position().toPoint()
                self._press_index = index
                self._press_occupied = (
                    self._model.cell_at(index.row(), index.column()) is not EMPTY_CELL
                )
                self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Promote a held left-button press into a drag once it clears Qt's threshold.

        While the button stays down over a cell captured by
        :meth:`mousePressEvent`, this arms ``self._dragging`` the first time
        the pointer moves at least ``QApplication.startDragDistance()`` from
        the press point, then delegates to :meth:`_update_drag_indicator` on
        every move after that — updating the move/copy-vs-scrub cursor and
        indicator without pushing any command yet (that happens on release).
        """
        if self._press_index is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            if not self._dragging:
                moved = (event.position().toPoint() - self._press_pos).manhattanLength()
                if moved >= QApplication.startDragDistance():
                    self._dragging = True
            if self._dragging:
                self._update_drag_indicator(event)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Commit an in-progress drag on release, or just clear the press state.

        If a drag was actually armed (``self._dragging``) and the release is
        the left button, :meth:`_finish_drag` builds and pushes the
        resulting move/copy or scrub command against the target cell under
        the pointer; either way the press/drag bookkeeping is reset and the
        cursor override is cleared via :meth:`_reset_drag_state`.
        """
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._finish_drag(event)
            self._reset_drag_state()
            return
        self._reset_drag_state()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Cancel an in-progress drag on Escape without pushing any command.

        Only intercepts ``Key_Escape`` while ``self._dragging`` is true
        (REQ-P5-UI-031): it clears the drag state and rebuilds the view to
        drop the indicator, changing nothing about the document. Every
        other key is passed to the base ``QTableView`` unchanged.
        """
        if event.key() == Qt.Key.Key_Escape and self._dragging:
            # ESC mid-drag changes nothing and pushes nothing (REQ-P5-UI-031).
            self._reset_drag_state()
            self.rebuild()
            return
        super().keyPressEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Clear any drag-indicator cursor override when the pointer leaves the view.

        Guards against a stale move/copy or scrub cursor being left showing
        once the pointer exits the widget mid-drag; the drag state itself is
        untouched here, only the cursor.
        """
        self.unsetCursor()
        super().leaveEvent(event)

    def _reset_drag_state(self) -> None:
        self._press_pos = None
        self._press_index = None
        self._press_occupied = False
        self._dragging = False
        self.unsetCursor()

    def _update_drag_indicator(self, event) -> None:
        target = self.indexAt(event.position().toPoint())
        if self._press_occupied:
            # The mode is visible before the drop (REQ-P5-UI-031): the cursor
            # shape names move vs. copy, and the highlighted cell names the
            # destination.
            copying = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.setCursor(
                Qt.CursorShape.DragCopyCursor
                if copying
                else Qt.CursorShape.DragMoveCursor
            )
            if target.isValid():
                self.setCurrentIndex(target)
        else:
            # Body drag away from any occupied cell: scrub (REQ-P5-UI-002 reused).
            if target.isValid():
                column = target.column()
                if column != self._active_frame:
                    self._active_frame = column
                self.frameScrubbed.emit(column)

    def _finish_drag(self, event) -> None:
        target = self.indexAt(event.position().toPoint())
        if not self._press_occupied:
            return  # a plain body drag only scrubs; nothing to commit.
        if not target.isValid():
            return  # drop outside the grid changes nothing (REQ-P5-UI-031).
        source_index = self._press_index
        if source_index is None:
            return
        if target == source_index:
            return  # drop on the cel's own cell is a no-op (REQ-P5-LOGIC-016).
        if self._document is None or self._push is None:
            return
        source_track = self._model.track_id_at(source_index.row())
        dest_track = self._model.track_id_at(target.row())
        if source_track is None or dest_track is None:
            return
        source_frame = source_index.column()
        dest_frame = target.column()
        copying = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        dest_cell = self._model.cell_at(target.row(), dest_frame)
        document = self._document
        push = self._push

        def _build_and_push() -> None:
            try:
                if copying:
                    cmd = document.make_copy_cel_command(
                        source_frame_index=source_frame,
                        source_track_id=source_track,
                        dest_frame_index=dest_frame,
                        dest_track_id=dest_track,
                    )
                    label = self.tr("Copy Cel")
                else:
                    cmd = document.make_move_cel_command(
                        source_frame_index=source_frame,
                        source_track_id=source_track,
                        dest_frame_index=dest_frame,
                        dest_track_id=dest_track,
                    )
                    label = self.tr("Move Cel")
            except DocumentError:
                self.rebuild()
                return
            push(cmd, label)

        if dest_cell is EMPTY_CELL:
            _build_and_push()
            return

        # Occupied destination: confirm first (REQ-P5-UI-033), unless the
        # project's own preference registry says "suppressed" (ADR-0056).
        if self._document.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed":
            _build_and_push()
            return
        dialog = Cel_Overwrite_Dialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return  # cancel leaves everything untouched, pushes nothing.
        if dialog.dont_ask_again():
            self._document.prefs = self._document.prefs.with_value(
                CONFIRM_CEL_OVERWRITE, "suppressed"
            )
        _build_and_push()

    # -- i18n / a11y ------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Timeline grid"))
        self.setAccessibleDescription(
            self.tr(
                "Frames as columns, layer tracks as rows; drag a header to "
                "reorder, drag a drawing to move it (hold Ctrl to copy), or open "
                "the context menu on an empty cell to create a cel there"
            )
        )
        self.horizontalHeader().setAccessibleName(self.tr("Frame headers"))
        self.verticalHeader().setAccessibleName(self.tr("Layer track headers"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the grid's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
            self._model.retranslate()
        super().changeEvent(event)
