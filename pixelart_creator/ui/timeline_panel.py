# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Timeline panel — frame strip, scrub, duration + frame ops (REQ-P5-UI-001..007).

``Timeline_Panel`` presents the active document's frames as a horizontal strip of
per-frame cells (REQ-P5-UI-001): each cell shows the frame's thumbnail, its 1-based
number, its editable ``duration_ms`` and any tag spans covering it. Clicking a cell
selects it as the active (canvas-displayed) frame; a drag along the strip **scrubs**
(REQ-P5-UI-002) — both emit :data:`frameSelected` / :data:`frameScrubbed` and push
**no** command (selection/scrub mutate no document state, CL-13).

A toolbar drives **add** (after active), **remove** (refuses the last frame),
**duplicate** and per-frame **duration** edit (REQ-P5-UI-003/-004/-006/-007); cells
are drag-reorderable (REQ-P5-UI-005). Every mutation delegates to a ``logic/document``
frame op wrapped as **exactly one**
:class:`~pixelart_creator.ui.commands.FrameCommand` (REQ-P5-UI-015): the panel never
mutates the frames list itself — it builds the reversible ``history.Command`` the
document returns, pushes it onto the active document's :class:`QUndoStack`, and
rebuilds from the document (the single source of truth). No domain maths lives here
(Article I / S11).

All user-visible strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (REQ-P5-UI-019); interactive controls carry
accessible names and are keyboard-reachable (REQ-P5-UI-017); colours come from the
active QSS theme by role, so both themes render correctly (REQ-P5-UI-018).
"""

from __future__ import annotations

from typing import Callable, List, Optional

import numpy as np
from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import DEFAULT_FRAME_DURATION_MS
from pixelart_creator.logic.document import Document, DocumentError, iter_layers
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.commands import FrameCommand
from pixelart_creator.ui.timeline_grid_view import Timeline_Grid_View

#: Index of the strip surface in the cell-surface QStackedWidget — the default
#: (REQ-P5-UI-020: "the strip is the default"). Not a domain constant (Article
#: II does not reach a fixed widget-stack index); grouped with the other
#: presentation literals this module already carries.
_STRIP_SURFACE_INDEX = 0
_GRID_SURFACE_INDEX = 1

#: Longest edge (px) of a cached per-cell frame thumbnail. Presentation-only
#: sizing (like ``_SWATCH_PX`` in ``main_window``); the resident buffer is never
#: culled — only the small display thumbnail is downscaled (F7).
_THUMBNAIL_EDGE = 48

#: Ceiling for the per-frame duration spin box (ms). A presentation-only cap on
#: how high the editor spins (like ``_THUMBNAIL_EDGE``); it is NOT a domain tuning
#: value — the authoritative bound is the logic
#: ``make_set_frame_duration_command`` positive-int guard, which alone validates.
_DURATION_SPIN_MAX = 600_000


class Timeline_Panel(QWidget):
    """Horizontal frame strip bound to the active document (REQ-P5-UI-001..007)."""

    #: Emitted with the frame index a click/keyboard selected (settled — onion on).
    frameSelected = Signal(int)
    #: Emitted with the frame index the cursor is dragging over (scrub — onion off).
    frameScrubbed = Signal(int)
    #: Emitted with a ``layer_id`` the grid cell surface's selection settled on
    #: (REQ-P5-UI-023, BF-G1); the strip has no layer axis and never emits this.
    layerSelected = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the frame strip, the grid, the view toggle and shared actions."""
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._stack: Optional[QUndoStack] = None
        self._on_frames_changed: Optional[Callable[[], None]] = None
        self._active_index = 0
        self._updating = False

        self._toolbar = QToolBar(self)
        self._build_actions()
        self._grid_toggle_action = QAction(self)
        self._grid_toggle_action.setCheckable(True)
        self._grid_toggle_action.setChecked(False)  # strip is the default (UI-020).
        self._grid_toggle_action.toggled.connect(self._on_view_mode_toggled)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._grid_toggle_action)

        self._strip = QListWidget(self)
        self._strip.setFlow(QListWidget.Flow.LeftToRight)
        self._strip.setWrapping(False)
        self._strip.setViewMode(QListWidget.ViewMode.IconMode)
        self._strip.setMovement(QListWidget.Movement.Static)
        self._strip.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._strip.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._strip.setIconSize(QSize(_THUMBNAIL_EDGE, _THUMBNAIL_EDGE))
        self._strip.setSpacing(4)
        self._strip.setUniformItemSizes(False)
        self._strip.currentRowChanged.connect(self._on_row_changed)
        self._strip.itemPressed.connect(self._on_item_pressed)
        self._strip.itemEntered.connect(self._on_item_entered)
        self._strip.setMouseTracking(True)
        # Qt must never reorder the model itself — the document is the single
        # source of truth. Intercept the internal-move drop → one move command.
        self._strip.model().rowsMoved.connect(self._on_rows_moved)

        # The grid is the optional second cell surface (REQ-P5-UI-020/-022); the
        # toolbar, duration editor and tag markers stay siblings, untouched by
        # the swap (T4). It pushes through this panel's own FrameCommand path
        # (_push), so the strip and the grid share one undo discipline.
        self._grid = Timeline_Grid_View(self)
        self._grid.frameActivated.connect(self._on_grid_frame_activated)
        self._grid.frameScrubbed.connect(self._on_grid_frame_scrubbed)
        self._grid.layerActivated.connect(self.layerSelected.emit)

        self._cell_surface = QStackedWidget(self)
        self._cell_surface.addWidget(self._strip)  # index _STRIP_SURFACE_INDEX
        self._cell_surface.addWidget(self._grid)  # index _GRID_SURFACE_INDEX

        self._duration_label = QLabel(self)
        self._duration_spin = QSpinBox(self)
        self._duration_spin.setRange(1, _DURATION_SPIN_MAX)
        self._duration_spin.setValue(DEFAULT_FRAME_DURATION_MS)
        self._duration_spin.editingFinished.connect(self._on_duration_committed)

        duration_bar = QToolBar(self)
        duration_bar.addWidget(self._duration_label)
        duration_bar.addWidget(self._duration_spin)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._cell_surface, 1)
        layout.addWidget(duration_bar)

        self._retranslate()
        self._update_actions()

    # -- context ----------------------------------------------------------

    @property
    def document(self) -> Optional[Document]:
        """The document whose frames the strip reflects."""
        return self._document

    @property
    def active_index(self) -> int:
        """The active (canvas-displayed) frame index."""
        return self._active_index

    def set_context(
        self,
        document: Document,
        stack: QUndoStack,
        on_frames_changed: Callable[[], None],
    ) -> None:
        """Bind the panel to a document + its undo stack + a refresh hook.

        ``on_frames_changed`` is invoked by a :class:`FrameCommand` after a frame
        op (and its undo/redo) so the owner can invalidate the per-frame composite
        cache and recomposite the canvas. Called on document open and every tab
        switch (state isolation).
        """
        self._document = document
        self._stack = stack
        self._on_frames_changed = on_frames_changed
        self._active_index = 0
        self._grid.set_context(document, stack, self._active_index, self._push)
        self.rebuild()

    # -- toolbar actions --------------------------------------------------

    def _build_actions(self) -> None:
        self._add_action = QAction(self)
        self._add_action.triggered.connect(self._on_add)
        self._remove_action = QAction(self)
        self._remove_action.triggered.connect(self._on_remove)
        self._duplicate_action = QAction(self)
        self._duplicate_action.triggered.connect(self._on_duplicate)
        for action in (
            self._add_action,
            self._remove_action,
            self._duplicate_action,
        ):
            self._toolbar.addAction(action)

    # -- strip build ------------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the whole strip from the document (after a structural op)."""
        self._updating = True
        self._strip.clear()
        if self._document is not None:
            count = len(self._document.frames)
            if self._active_index >= count:
                self._active_index = max(0, count - 1)
            for index, frame in enumerate(self._document.frames):
                item = QListWidgetItem()
                item.setIcon(self._thumbnail(index))
                item.setText(self._cell_label(index, frame.duration_ms))
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setToolTip(self._cell_tooltip(index, frame.duration_ms))
                self._strip.addItem(item)
            self._strip.setCurrentRow(self._active_index)
        self._updating = False
        self._grid.rebuild()
        self._sync_duration_spin()
        self._update_actions()

    def _thumbnail(self, index: int) -> QPixmap:
        """Return a downscaled thumbnail of frame ``index`` (nearest-neighbour)."""
        doc = self._document
        if doc is None:
            return QPixmap()
        frame = doc.frames[index]
        try:
            if doc.mode is ColorMode.RGBA:
                composite = composite_stack(frame.layers, doc.width, doc.height)
                image = self._buffer_to_image(composite, doc.palette.colors())
            else:
                # Indexed docs are not composited (RGBA-only compositor); show the
                # frame's topmost leaf layer resolved through the palette LUT.
                leaves = iter_layers(frame.layers)
                if not leaves:
                    return QPixmap()
                image = self._buffer_to_image(leaves[-1].buffer, doc.palette.colors())
        except (DocumentError, ValueError):
            return QPixmap()
        scaled = image.scaled(
            _THUMBNAIL_EDGE,
            _THUMBNAIL_EDGE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,  # thumbnail-only, not canvas
        )
        return QPixmap.fromImage(scaled)

    @staticmethod
    def _buffer_to_image(buffer: PixelBuffer, palette_colors: List[RGBA]) -> QImage:
        """Convert a buffer to an owned RGBA :class:`QImage`."""
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

    def _cell_label(self, index: int, duration_ms: int) -> str:
        """Return the per-cell caption (frame number + tag markers)."""
        text = self.tr("Frame %1").replace("%1", str(index + 1))
        tags = self._tags_for_frame(index)
        if tags:
            text = f"{text}\n{tags}"
        return text

    def _cell_tooltip(self, index: int, duration_ms: int) -> str:
        return (
            self.tr("Frame %1 — %2 ms")
            .replace("%1", str(index + 1))
            .replace("%2", str(duration_ms))
        )

    def _tags_for_frame(self, index: int) -> str:
        """Return a compact marker of any tag names spanning frame ``index``."""
        doc = self._document
        if doc is None:
            return ""
        names = [
            tag.name
            for tag in doc.frame_tags
            if tag.from_frame <= index <= tag.to_frame
        ]
        return ", ".join(names)

    # -- selection / scrub (no command, CL-13) ---------------------------

    def _on_row_changed(self, row: int) -> None:
        if self._updating or row < 0:
            return
        self._active_index = row
        self._sync_duration_spin()
        self._update_actions()
        self.frameSelected.emit(row)

    def _on_item_pressed(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int):
            self._active_index = index
            self.frameSelected.emit(index)

    def _on_item_entered(self, item: QListWidgetItem) -> None:
        # A drag with the button held scrubs; a plain hover does not (checked via
        # the mouse buttons). The canvas continuously shows the frame under the
        # cursor (REQ-P5-UI-002) without altering the document (CL-13).
        if self._updating:
            return
        from PySide6.QtWidgets import QApplication

        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(index, int):
            self._active_index = index
            self.frameScrubbed.emit(index)

    def select_frame(self, index: int) -> None:
        """Highlight ``index`` as the active frame (e.g. driven by playback)."""
        if self._document is None:
            return
        if not 0 <= index < len(self._document.frames):
            return
        self._active_index = index
        self._updating = True
        self._strip.setCurrentRow(index)
        self._updating = False
        self._grid.set_active_frame(index)
        self._sync_duration_spin()
        self._update_actions()

    # -- grid forwarding (T4: the same signals serve both cell surfaces) -----

    def _on_grid_frame_activated(self, index: int) -> None:
        self._active_index = index
        self._updating = True
        self._strip.setCurrentRow(index)
        self._updating = False
        self._sync_duration_spin()
        self._update_actions()
        self.frameSelected.emit(index)

    def _on_grid_frame_scrubbed(self, index: int) -> None:
        self._active_index = index
        self.frameScrubbed.emit(index)

    # -- view-mode toggle (REQ-P5-UI-020) -------------------------------------

    def _on_view_mode_toggled(self, checked: bool) -> None:
        # Pure view state: pushes no QUndoCommand, marks nothing modified, and is
        # never written to .pixproj (REQ-P5-UI-020). The active frame, active
        # layer, playback state and undo stack are all untouched by the switch.
        self._cell_surface.setCurrentIndex(
            _GRID_SURFACE_INDEX if checked else _STRIP_SURFACE_INDEX
        )
        if checked:
            self._grid.set_active_frame(self._active_index)

    # -- frame ops (one FrameCommand each, REQ-P5-UI-015) ----------------

    def _push(self, command: Command, label: str) -> None:
        if self._stack is None:
            return
        self._stack.push(FrameCommand(command, self._refresh, label))

    def _refresh(self) -> None:
        """Run the frame-command follow-up: recomposite + rebuild the strip."""
        if self._on_frames_changed is not None:
            self._on_frames_changed()
        self.rebuild()

    def _on_add(self) -> None:
        doc = self._document
        if doc is None:
            return
        try:
            cmd = doc.make_add_frame_command(after_index=self._active_index)
        except DocumentError:
            return
        # The new frame lands after the active one; follow selection to it.
        self._active_index += 1
        self._push(cmd, self.tr("Add Frame"))

    def _on_remove(self) -> None:
        doc = self._document
        if doc is None:
            return
        try:
            cmd = doc.make_remove_frame_command(self._active_index)
        except DocumentError:
            return  # last-frame removal is refused (REQ-P5-UI-004).
        if self._active_index > 0:
            self._active_index -= 1
        self._push(cmd, self.tr("Remove Frame"))

    def _on_duplicate(self) -> None:
        doc = self._document
        if doc is None:
            return
        try:
            cmd = doc.make_duplicate_frame_command(self._active_index)
        except DocumentError:
            return
        self._active_index += 1  # the copy lands after the source.
        self._push(cmd, self.tr("Duplicate Frame"))

    def _on_rows_moved(
        self,
        _parent: object,
        start: int,
        _end: int,
        _destination: object,
        row: int,
    ) -> None:
        """Translate the strip's internal-move drop into one move command.

        Qt has already reordered its *view* model; the document is untouched. The
        ``rowsMoved`` signal reports the source row (``start``) and the model
        insertion ``row``; we map them to the ``pop``/``insert`` semantics of
        :meth:`~pixelart_creator.logic.document.Document.make_move_frame_command`
        (final index = ``row`` when moving up, ``row - 1`` when moving down), build
        that reversible command, and rebuild from the document so the view and
        model reconcile through the single source of truth (REQ-P5-UI-005).
        """
        if self._updating or self._document is None:
            return
        from_index = start
        to_index = row if row < start else row - 1
        if from_index == to_index or not 0 <= to_index < len(self._document.frames):
            self.rebuild()
            return
        try:
            cmd = self._document.make_move_frame_command(from_index, to_index)
        except DocumentError:
            self.rebuild()
            return
        self._active_index = to_index
        self._push(cmd, self.tr("Reorder Frame"))

    def _on_duration_committed(self) -> None:
        doc = self._document
        if doc is None or self._updating:
            return
        value = self._duration_spin.value()
        if not 0 <= self._active_index < len(doc.frames):
            return
        if doc.frames[self._active_index].duration_ms == value:
            return  # no-op edit pushes no command.
        try:
            cmd = doc.make_set_frame_duration_command(self._active_index, value)
        except DocumentError:
            self._sync_duration_spin()
            return
        self._push(cmd, self.tr("Set Frame Duration"))

    def _sync_duration_spin(self) -> None:
        doc = self._document
        self._duration_spin.blockSignals(True)
        if doc is not None and 0 <= self._active_index < len(doc.frames):
            self._duration_spin.setValue(doc.frames[self._active_index].duration_ms)
            self._duration_spin.setEnabled(True)
        else:
            self._duration_spin.setEnabled(False)
        self._duration_spin.blockSignals(False)

    # -- action enablement ------------------------------------------------

    def _update_actions(self) -> None:
        doc = self._document
        has_doc = doc is not None
        multi = has_doc and len(doc.frames) > 1  # type: ignore[union-attr]
        self._add_action.setEnabled(has_doc)
        self._duplicate_action.setEnabled(has_doc)
        # Remove is refused for the last remaining frame (REQ-P5-UI-004).
        self._remove_action.setEnabled(bool(multi))

    # -- theming (REQ-P5-UI-018) -----------------------------------------

    def set_active_frame_role(self, color: QColor) -> None:
        """Highlight the active cell with a role-based selection colour.

        Presentation-only: colours come from the active theme by role (never
        hard-coded per widget), so the active-frame indicator reads correctly in
        both themes (REQ-P5-UI-018).
        """
        # The list widget's selection already draws from the QSS palette; this
        # hook lets the shell push the theme's highlight role explicitly.
        self._strip.setStyleSheet(
            f"QListWidget::item:selected {{ border: 2px solid {color.name()}; }}"
        )

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Timeline panel"))
        self._toolbar.setWindowTitle(self.tr("Frame actions"))
        self._strip.setAccessibleName(self.tr("Frame strip"))
        self._strip.setAccessibleDescription(
            self.tr("Frames left-to-right in playback order; drag to reorder")
        )
        self._add_action.setText(self.tr("Add Frame"))
        self._add_action.setToolTip(self.tr("Insert a new frame after the active one"))
        self._remove_action.setText(self.tr("Remove Frame"))
        self._remove_action.setToolTip(self.tr("Delete the active frame"))
        self._duplicate_action.setText(self.tr("Duplicate Frame"))
        self._duplicate_action.setToolTip(
            self.tr("Insert a copy of the active frame after it")
        )
        self._grid_toggle_action.setText(self.tr("Grid View"))
        self._grid_toggle_action.setToolTip(
            self.tr("Show frames and layer tracks as a grid instead of a strip")
        )
        self._cell_surface.setAccessibleName(self.tr("Timeline cell surface"))
        self._duration_label.setText(self.tr("Duration"))
        # Leading-space unit suffix, translatable + re-set on language change.
        self._duration_spin.setSuffix(self.tr(" ms"))
        self._duration_spin.setAccessibleName(self.tr("Frame duration"))
        self._duration_spin.setToolTip(
            self.tr("Display time of the active frame, in milliseconds")
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the timeline's strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
            if self._document is not None:
                self.rebuild()
        super().changeEvent(event)
