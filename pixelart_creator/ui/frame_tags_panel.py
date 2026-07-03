"""Frame-tags panel — named-animation CRUD + play (REQ-P5-UI-013/-014).

``Frame_Tags_Panel`` lists the active document's ordered frame **tags** (named
animations) and lets the user **create** a tag over a frame range, **edit** it
(rename / re-range / change mode / repeat / colour) and **delete** it — each as
**exactly one** :class:`~pixelart_creator.ui.commands.FrameCommand`
(REQ-P5-UI-013/-015), delegating to the reversible ``logic/document`` tag ops. It
can also **select a tag and play it** as its own animation (REQ-P5-UI-014) by
emitting :data:`playTagRequested`; the shell routes that to
:meth:`~pixelart_creator.ui.playback_controls.Playback_Controls.play_tag`.

``Tag_Dialog`` collects the tag fields; the range / mode / repeat / colour are
validated by the ``logic/document`` builder (raising ``DocumentError``), so the
panel never re-implements the domain rules (Article I / S11). All strings are
``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange`
(REQ-P5-UI-019); controls carry accessible names, are keyboard-reachable
(REQ-P5-UI-017) and theme by role (REQ-P5-UI-018).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QUndoStack
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.animation import (
    DEFAULT_PLAYBACK_MODE,
    FrameTag,
    PlaybackMode,
)
from pixelart_creator.logic.color import ColorError, from_hex, to_hex
from pixelart_creator.logic.document import Document, DocumentError
from pixelart_creator.logic.history import Command
from pixelart_creator.ui.commands import FrameCommand


def _mode_label(widget: QWidget, mode: PlaybackMode) -> str:
    """Return the translatable label for a playback mode (shared with playback)."""
    labels = {
        PlaybackMode.LOOP: widget.tr("Loop"),
        PlaybackMode.ONCE: widget.tr("Once"),
        PlaybackMode.PING_PONG: widget.tr("Ping-Pong"),
        PlaybackMode.REVERSE: widget.tr("Reverse"),
    }
    return labels.get(mode, mode.value)


class Tag_Dialog(QDialog):
    """Collect / edit a tag's fields (name, range, mode, repeat, colour)."""

    def __init__(
        self,
        frame_count: int,
        tag: Optional[FrameTag] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the tag field editors, seeded from ``tag`` when editing."""
        super().__init__(parent)
        high = max(0, frame_count - 1)
        self._color: str = tag.color if tag is not None else "#ff0000ff"

        self._name_edit = QLineEdit(self)
        self._from_spin = QSpinBox(self)
        self._from_spin.setRange(0, high)
        self._to_spin = QSpinBox(self)
        self._to_spin.setRange(0, high)
        self._mode_combo = QComboBox(self)
        for mode in PlaybackMode:
            self._mode_combo.addItem(_mode_label(self, mode), mode)
        self._repeat_spin = QSpinBox(self)
        self._repeat_spin.setRange(0, 9999)
        self._color_button = QPushButton(self)
        self._color_button.clicked.connect(self._pick_color)

        if tag is not None:
            self._name_edit.setText(tag.name)
            self._from_spin.setValue(min(tag.from_frame, high))
            self._to_spin.setValue(min(tag.to_frame, high))
            mode_idx = self._mode_combo.findData(tag.mode)
            if mode_idx >= 0:
                self._mode_combo.setCurrentIndex(mode_idx)
            self._repeat_spin.setValue(tag.repeat)
        else:
            default_idx = self._mode_combo.findData(DEFAULT_PLAYBACK_MODE)
            if default_idx >= 0:
                self._mode_combo.setCurrentIndex(default_idx)
        self._paint_color_button()

        self._form = QFormLayout()
        self._name_label = QLabel(self)
        self._from_label = QLabel(self)
        self._to_label = QLabel(self)
        self._mode_label_widget = QLabel(self)
        self._repeat_label = QLabel(self)
        self._color_label = QLabel(self)
        self._form.addRow(self._name_label, self._name_edit)
        self._form.addRow(self._from_label, self._from_spin)
        self._form.addRow(self._to_label, self._to_spin)
        self._form.addRow(self._mode_label_widget, self._mode_combo)
        self._form.addRow(self._repeat_label, self._repeat_spin)
        self._form.addRow(self._color_label, self._color_button)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addWidget(self._buttons)
        self._retranslate()

    def _pick_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        try:
            initial = QColor(*from_hex(self._color))
        except ColorError:
            initial = QColor(255, 0, 0, 255)
        chosen = QColorDialog.getColor(
            initial,
            self,
            self.tr("Tag colour"),
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if chosen.isValid():
            self._color = to_hex(
                (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())
            )
            self._paint_color_button()

    def _paint_color_button(self) -> None:
        try:
            r, g, b, a = from_hex(self._color)
        except ColorError:
            r, g, b, a = (255, 0, 0, 255)
        self._color_button.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, {a}); min-width: 32px;"
        )

    def result_fields(self) -> tuple[str, int, int, PlaybackMode, int, str]:
        """Return ``(name, from, to, mode, repeat, color)`` collected in the dialog."""
        mode = self._mode_combo.currentData()
        return (
            self._name_edit.text(),
            self._from_spin.value(),
            self._to_spin.value(),
            mode if isinstance(mode, PlaybackMode) else DEFAULT_PLAYBACK_MODE,
            self._repeat_spin.value(),
            self._color,
        )

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Frame Tag"))
        self._name_label.setText(self.tr("Name"))
        self._from_label.setText(self.tr("From frame"))
        self._to_label.setText(self.tr("To frame"))
        self._mode_label_widget.setText(self.tr("Mode"))
        self._repeat_label.setText(self.tr("Repeat (0 = infinite)"))
        self._color_label.setText(self.tr("Colour"))
        self._name_edit.setAccessibleName(self.tr("Tag name"))
        self._from_spin.setAccessibleName(self.tr("Tag start frame"))
        self._to_spin.setAccessibleName(self.tr("Tag end frame"))
        self._mode_combo.setAccessibleName(self.tr("Tag playback mode"))
        self._repeat_spin.setAccessibleName(self.tr("Tag repeat count"))
        self._color_button.setText(self.tr("Colour…"))
        self._color_button.setAccessibleName(self.tr("Tag colour"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the tag panel/dialog strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Frame_Tags_Panel(QWidget):
    """Tag list + create/edit/delete/play bound to the active document."""

    #: Emitted with the :class:`FrameTag` to play as a named animation (UI-014).
    playTagRequested = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the tag list and its Add / Edit / Delete / Play toolbar."""
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._stack: Optional[QUndoStack] = None
        self._on_tags_changed: Optional[Callable[[], None]] = None

        self._toolbar = QToolBar(self)
        self._build_actions()
        self._list = QListWidget(self)
        self._list.currentRowChanged.connect(lambda _row: self._update_actions())
        self._list.itemDoubleClicked.connect(lambda _item: self._on_edit())

        self._play_button = QPushButton(self)
        self._play_button.clicked.connect(self._on_play)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addWidget(self._play_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._list, 1)
        layout.addLayout(button_row)

        self._retranslate()
        self._update_actions()

    # -- context ----------------------------------------------------------

    def set_context(
        self,
        document: Document,
        stack: QUndoStack,
        on_tags_changed: Callable[[], None],
    ) -> None:
        """Bind the panel to a document + its undo stack + a refresh hook.

        ``on_tags_changed`` is invoked by a :class:`FrameCommand` after a tag op
        (and its undo/redo) so the timeline tag spans re-render. Called on document
        open and every tab switch.
        """
        self._document = document
        self._stack = stack
        self._on_tags_changed = on_tags_changed
        self.rebuild()

    def rebuild(self) -> None:
        """Rebuild the tag list from the document (after a tag op)."""
        self._list.clear()
        if self._document is not None:
            for index, tag in enumerate(self._document.frame_tags):
                item = QListWidgetItem(self._tag_caption(tag))
                item.setData(Qt.ItemDataRole.UserRole, index)
                self._list.addItem(item)
        self._update_actions()

    def _tag_caption(self, tag: FrameTag) -> str:
        return (
            self.tr("%1  [%2–%3]  %4")
            .replace("%1", tag.name or self.tr("(unnamed)"))
            .replace("%2", str(tag.from_frame + 1))
            .replace("%3", str(tag.to_frame + 1))
            .replace("%4", _mode_label(self, tag.mode))
        )

    # -- actions ----------------------------------------------------------

    def _build_actions(self) -> None:
        from PySide6.QtGui import QAction

        self._add_action = QAction(self)
        self._add_action.triggered.connect(self._on_add)
        self._edit_action = QAction(self)
        self._edit_action.triggered.connect(self._on_edit)
        self._remove_action = QAction(self)
        self._remove_action.triggered.connect(self._on_remove)
        for action in (self._add_action, self._edit_action, self._remove_action):
            self._toolbar.addAction(action)

    def _selected_index(self) -> Optional[int]:
        row = self._list.currentRow()
        if self._document is None or not 0 <= row < len(self._document.frame_tags):
            return None
        return row

    def _push(self, command: Command, label: str) -> None:
        if self._stack is None:
            return
        self._stack.push(FrameCommand(command, self._refresh, label))

    def _refresh(self) -> None:
        if self._on_tags_changed is not None:
            self._on_tags_changed()
        self.rebuild()

    def _on_add(self) -> None:
        doc = self._document
        if doc is None:
            return
        dialog = Tag_Dialog(len(doc.frames), None, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, from_frame, to_frame, mode, repeat, color = dialog.result_fields()
        try:
            cmd = doc.make_add_tag_command(
                name, from_frame, to_frame, mode=mode, repeat=repeat, color=color
            )
        except DocumentError as exc:
            self._warn(self.tr("Add Tag"), str(exc))
            return
        self._push(cmd, self.tr("Add Tag"))

    def _on_edit(self) -> None:
        doc = self._document
        index = self._selected_index()
        if doc is None or index is None:
            return
        dialog = Tag_Dialog(len(doc.frames), doc.frame_tags[index], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, from_frame, to_frame, mode, repeat, color = dialog.result_fields()
        try:
            cmd = doc.make_edit_tag_command(
                index,
                name=name,
                from_frame=from_frame,
                to_frame=to_frame,
                mode=mode,
                repeat=repeat,
                color=color,
            )
        except DocumentError as exc:
            self._warn(self.tr("Edit Tag"), str(exc))
            return
        self._push(cmd, self.tr("Edit Tag"))

    def _on_remove(self) -> None:
        doc = self._document
        index = self._selected_index()
        if doc is None or index is None:
            return
        try:
            cmd = doc.make_remove_tag_command(index)
        except DocumentError:
            return
        self._push(cmd, self.tr("Remove Tag"))

    def _on_play(self) -> None:
        doc = self._document
        index = self._selected_index()
        if doc is None or index is None:
            return
        self.playTagRequested.emit(doc.frame_tags[index])

    def _warn(self, title: str, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(self, title, message)

    def _update_actions(self) -> None:
        has_doc = self._document is not None
        has_sel = self._selected_index() is not None
        self._add_action.setEnabled(has_doc)
        self._edit_action.setEnabled(has_sel)
        self._remove_action.setEnabled(has_sel)
        self._play_button.setEnabled(has_sel)

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Frame tags panel"))
        self._toolbar.setWindowTitle(self.tr("Tag actions"))
        self._list.setAccessibleName(self.tr("Frame tags"))
        self._list.setAccessibleDescription(
            self.tr("Named animations; double-click to edit")
        )
        self._add_action.setText(self.tr("Add Tag"))
        self._edit_action.setText(self.tr("Edit Tag"))
        self._remove_action.setText(self.tr("Remove Tag"))
        self._play_button.setText(self.tr("Play Tag"))
        self._play_button.setToolTip(
            self.tr("Play the selected tag as its own animation")
        )
        self._play_button.setAccessibleName(self.tr("Play tag"))
        if self._document is not None:
            self.rebuild()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the tag panel/dialog strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
