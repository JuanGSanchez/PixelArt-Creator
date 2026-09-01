# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Tilemap layer panel — ordered layer CRUD + auto-tile toggle (part of Phase 6).

``Tilemap_Layer_Panel`` lists a :class:`~pixelart_creator.logic.tilemap.Tilemap`'s
ordered layers and lets the user **add / remove / reorder** them and toggle a
layer's **visibility** — each as **exactly one**
:class:`~pixelart_creator.ui.commands.TilemapCommand` wrapping the reversible
``logic/tilemap`` layer factory (REQ-P6-UI-008/-013). Selecting the active layer
is view state (no undo, CL-13, emitted as :data:`activeLayerChanged`). A per-layer
**auto-tile** checkbox emits :data:`autotileToggled` (the ruleset is built by the
canvas, which owns the active brush) — auto-tile is a brush/layer mode, not a
document mutation, so it is not undoable (REQ-P6-UI-009).

All domain rules (layer bounds, reorder, visibility) live in ``logic/tilemap``
(Article I / S11); this panel binds to that API and wraps its commands. Strings
are ``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange`
(REQ-P6-UI-017); controls carry accessible names, are keyboard reachable
(REQ-P6-UI-015) and theme by role (REQ-P6-UI-016).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import (
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.history import Command
from pixelart_creator.logic.tilemap import Tilemap, TilemapError
from pixelart_creator.ui.commands import TilemapCommand


class Tilemap_Layer_Panel(QWidget):
    """Ordered tilemap-layer list + add/remove/reorder/visibility + auto-tile."""

    #: Emitted with the active layer index (view state, no undo).
    activeLayerChanged = Signal(int)
    #: Emitted when the auto-tile checkbox is toggled (canvas builds the ruleset).
    autotileToggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the layer list, its action toolbar and the auto-tile toggle."""
        super().__init__(parent)
        self._tilemap: Optional[Tilemap] = None
        self._stack: Optional[QUndoStack] = None
        self._on_changed: Optional[Callable[[], None]] = None
        self._rebuilding = False

        self._toolbar = QToolBar(self)
        self._build_actions()
        self._list = QListWidget(self)
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemChanged.connect(self._on_item_changed)

        self._autotile_check = QCheckBox(self)
        self._autotile_check.toggled.connect(self._on_autotile_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._autotile_check)

        self._retranslate()
        self._update_actions()

    # -- context ----------------------------------------------------------

    def set_context(
        self,
        tilemap: Optional[Tilemap],
        stack: Optional[QUndoStack],
        on_changed: Optional[Callable[[], None]],
    ) -> None:
        """Bind the panel to a tilemap + its undo stack + a canvas-refresh hook."""
        self._tilemap = tilemap
        self._stack = stack
        self._on_changed = on_changed
        self.rebuild()

    def set_autotile_checked(self, checked: bool) -> None:
        """Reflect the active layer's auto-tile mode without re-emitting."""
        self._autotile_check.blockSignals(True)
        self._autotile_check.setChecked(checked)
        self._autotile_check.blockSignals(False)

    def active_layer(self) -> Optional[int]:
        """Return the active layer index, or ``None``.

        Resolves the selected list *row* to its stored ``UserRole`` layer index
        (``_row_layer_index``) — the list is displayed **reversed** (top row = last
        layer), so the raw ``currentRow()`` is NOT the layer index once there are
        two or more layers. Every selection-driven layer op (remove / reorder /
        visibility / stamp-target) resolves through here so it targets the layer
        the user actually selected (S2 data-loss fix; REQ-P6-UI-005/-006/-008/-013).
        """
        if self._tilemap is None:
            return None
        index = self._row_layer_index(self._list.currentRow())
        if index is None or not 0 <= index < len(self._tilemap.layers):
            return None
        return index

    # -- list -------------------------------------------------------------

    def rebuild(self) -> None:
        """Rebuild the layer list from the tilemap (top layer first)."""
        self._rebuilding = True
        self._list.clear()
        tilemap = self._tilemap
        if tilemap is not None:
            for index in reversed(range(len(tilemap.layers))):
                layer = tilemap.layers[index]
                item = QListWidgetItem(layer.name)
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked
                )
                self._list.addItem(item)
        self._rebuilding = False
        self._update_actions()

    def _row_layer_index(self, row: int) -> Optional[int]:
        item = self._list.item(row)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return int(value) if value is not None else None

    # -- actions ----------------------------------------------------------

    def _build_actions(self) -> None:
        self._add_action = QAction(self)
        self._add_action.triggered.connect(self._on_add)
        self._remove_action = QAction(self)
        self._remove_action.triggered.connect(self._on_remove)
        self._up_action = QAction(self)
        self._up_action.triggered.connect(self._on_move_up)
        self._down_action = QAction(self)
        self._down_action.triggered.connect(self._on_move_down)
        for action in (
            self._add_action,
            self._remove_action,
            self._up_action,
            self._down_action,
        ):
            self._toolbar.addAction(action)

    def _push(self, command: Command, label: str) -> None:
        if self._stack is None:
            return
        self._stack.push(TilemapCommand(command, self._refresh, label))

    def _refresh(self) -> None:
        self.rebuild()
        if self._on_changed is not None:
            self._on_changed()

    def _on_add(self) -> None:
        tilemap = self._tilemap
        if tilemap is None:
            return
        name = self.tr("Layer %1").replace("%1", str(len(tilemap.layers) + 1))
        try:
            command = tilemap.make_add_layer_command(name=name)
        except TilemapError as exc:
            self._warn(self.tr("Add Layer"), str(exc))
            return
        self._push(command, self.tr("Add Layer"))

    def _on_remove(self) -> None:
        index = self.active_layer()
        tilemap = self._tilemap
        if tilemap is None or index is None:
            return
        try:
            command = tilemap.make_remove_layer_command(index)
        except TilemapError as exc:
            self._warn(self.tr("Remove Layer"), str(exc))
            return
        self._push(command, self.tr("Remove Layer"))

    def _on_move_up(self) -> None:
        self._move(-1)

    def _on_move_down(self) -> None:
        self._move(+1)

    def _move(self, row_delta: int) -> None:
        """Reorder the selected layer by ``row_delta`` **rows** in the visible list.

        The list is displayed **reversed** (top row = last layer), so a reorder
        must be resolved in *row* space and both endpoints mapped through
        ``_row_layer_index`` — never by adding ``row_delta`` to a raw row treated as
        a layer index (the S2 defect). This guarantees the command moves the layer
        the user actually selected to the layer position of the adjacent row
        (REQ-P6-UI-013 / SC-UI-008-1).
        """
        tilemap = self._tilemap
        row = self._list.currentRow()
        target_row = row + row_delta
        if tilemap is None or not 0 <= row < self._list.count():
            return
        if not 0 <= target_row < self._list.count():
            return
        from_index = self._row_layer_index(row)
        to_index = self._row_layer_index(target_row)
        if from_index is None or to_index is None:
            return
        try:
            command = tilemap.make_move_layer_command(from_index, to_index)
        except TilemapError as exc:
            self._warn(self.tr("Reorder Layer"), str(exc))
            return
        self._push(command, self.tr("Reorder Layer"))

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._rebuilding or self._tilemap is None:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if index is None:
            return
        visible = item.checkState() == Qt.CheckState.Checked
        if self._tilemap.layers[int(index)].visible == visible:
            return
        try:
            command = self._tilemap.make_set_layer_visibility_command(
                int(index), visible
            )
        except TilemapError as exc:
            self._warn(self.tr("Layer Visibility"), str(exc))
            return
        self._push(command, self.tr("Toggle Layer Visibility"))

    def _on_row_changed(self, _row: int) -> None:
        index = self.active_layer()
        if index is not None:
            self.activeLayerChanged.emit(index)
        self._update_actions()

    def _on_autotile_toggled(self, checked: bool) -> None:
        self.autotileToggled.emit(bool(checked))

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _update_actions(self) -> None:
        has_map = self._tilemap is not None
        has_sel = self.active_layer() is not None
        self._add_action.setEnabled(has_map)
        self._remove_action.setEnabled(has_sel)
        self._up_action.setEnabled(has_sel)
        self._down_action.setEnabled(has_sel)
        self._autotile_check.setEnabled(has_sel)

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Tilemap layers panel"))
        self._toolbar.setWindowTitle(self.tr("Layer actions"))
        self._list.setAccessibleName(self.tr("Tilemap layers"))
        self._list.setAccessibleDescription(
            self.tr("Ordered map layers; tick to show/hide, top layer first")
        )
        self._add_action.setText(self.tr("Add Layer"))
        self._remove_action.setText(self.tr("Remove Layer"))
        self._up_action.setText(self.tr("Move Up"))
        self._down_action.setText(self.tr("Move Down"))
        self._autotile_check.setText(self.tr("Auto-tile (Blob-47)"))
        self._autotile_check.setToolTip(
            self.tr("Resolve tile edges automatically from neighbours")
        )
        self._autotile_check.setAccessibleName(self.tr("Auto-tile toggle"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Re-translate the panel strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
