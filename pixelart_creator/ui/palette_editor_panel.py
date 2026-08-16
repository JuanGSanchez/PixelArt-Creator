"""Palette editor panel — add / remove / reorder + import/export (REQ-P3-UI-001/-002).

``Palette_Editor_Panel`` extends the Phase-1 palette surface with editing: add a
swatch (the active colour), remove the selected swatch, reorder by drag-drop or
the keyboard-reachable Move Up / Move Down buttons (binding
:meth:`~pixelart_creator.logic.palette.Palette.move`), and import / export via
:mod:`pixelart_creator.logic.palette_io` behind a file dialog (SC-U002-1). A
malformed import surfaces a user-facing error and never crashes (SC-U002-2).

Every mutation is exactly **one** undoable step: the panel builds a Qt-free
:class:`~pixelart_creator.logic.history.FunctionCommand` (do/undo over the shared
``Palette`` instance, so its identity — and every scene/document reference — is
preserved) and pushes it as a single
:class:`~pixelart_creator.ui.commands.LogicCommand` (SC-U001-2). The panel holds
**no** domain maths (Article I / S11) — colour encode/decode lives in
``logic/palette_io``; disk read/write is the thin UI I/O here (plan §3.3). Strings
are ``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange` (F5); the
controls are keyboard-reachable and legible in both themes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic import history
from pixelart_creator.logic.color import BLACK, RGBA, to_hex
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_io import PaletteIOError, decode, encode
from pixelart_creator.ui.commands import LogicCommand

#: Edge of an editor swatch icon, px (presentation-only sizing).
_SWATCH_PX = 24

#: Maps a save/open dialog filter label to the ``palette_io`` format token.
_FILTERS: List[tuple[str, str, str]] = [
    ("GIMP palette (*.gpl)", "gpl", ".gpl"),
    ("JASC palette (*.pal)", "pal", ".pal"),
    ("Hex list (*.hex *.txt)", "hex", ".hex"),
]


def _set_palette_contents(palette: Palette, colors: List[RGBA]) -> None:
    """Replace ``palette``'s colours in place, preserving the object identity.

    Used by the reversible do/undo callables so the shared ``Palette`` instance
    referenced by the document/scene is mutated (never swapped), keeping every
    binding valid. Pure list orchestration over the palette API — no maths.
    """
    while len(palette):
        palette.remove_at(len(palette) - 1)
    for color in colors:
        palette.append(color)


class Palette_Editor_Panel(QWidget):
    """Editable palette view: add / remove / reorder + import / export."""

    #: Emitted with an RGBA tuple when a swatch is selected (sets active colour).
    colorSelected = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the editable swatch list and its action buttons."""
        super().__init__(parent)
        self._palette: Optional[Palette] = None
        self._undo_stack: Optional[QUndoStack] = None
        self._on_changed: Optional[Callable[[], None]] = None
        self._active_color: RGBA = BLACK
        self._syncing = False

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)

        self._title = QLabel(self)
        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add)
        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove)
        self._up_button = QPushButton(self)
        self._up_button.clicked.connect(lambda: self._on_move(-1))
        self._down_button = QPushButton(self)
        self._down_button.clicked.connect(lambda: self._on_move(1))
        self._import_button = QPushButton(self)
        self._import_button.clicked.connect(self._on_import)
        self._export_button = QPushButton(self)
        self._export_button.clicked.connect(self._on_export)

        edit_row = QHBoxLayout()
        edit_row.addWidget(self._add_button)
        edit_row.addWidget(self._remove_button)
        edit_row.addWidget(self._up_button)
        edit_row.addWidget(self._down_button)
        io_row = QHBoxLayout()
        io_row.addWidget(self._import_button)
        io_row.addWidget(self._export_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._list)
        layout.addLayout(edit_row)
        layout.addLayout(io_row)
        self._retranslate()

    # -- binding ----------------------------------------------------------

    def set_context(
        self,
        palette: Palette,
        undo_stack: QUndoStack,
        on_changed: Callable[[], None],
    ) -> None:
        """Bind the editor to the active document's palette + undo stack.

        Args:
            palette: The shared :class:`Palette` to edit in place.
            undo_stack: The active document's stack (one command per mutation).
            on_changed: Callback invoked after every mutation (and its undo/redo)
                so the shell refreshes the palette panel + canvas display.
        """
        self._palette = palette
        self._undo_stack = undo_stack
        self._on_changed = on_changed
        self.refresh()

    def set_active_color(self, color: RGBA) -> None:
        """Set the colour the Add button appends (the shell's active colour)."""
        self._active_color = color

    def refresh(self) -> None:
        """Repopulate the swatch list from the bound palette (index order)."""
        self._syncing = True
        try:
            self._list.clear()
            if self._palette is None:
                return
            for index, color in enumerate(self._palette.colors()):
                item = QListWidgetItem()
                pixmap = QPixmap(_SWATCH_PX, _SWATCH_PX)
                pixmap.fill(QColor(*color))
                item.setIcon(QIcon(pixmap))
                hex_text = to_hex(color)
                item.setText(hex_text)
                item.setToolTip(hex_text)
                item.setData(Qt.ItemDataRole.UserRole, color)
                item.setData(Qt.ItemDataRole.UserRole + 1, index)
                self._list.addItem(item)
        finally:
            self._syncing = False

    def replace_all(self, colors: List[RGBA], label: str) -> None:
        """Replace the whole palette with ``colors`` as one undoable command.

        Used by the extract-from-image and shade-ramp flows to load a computed
        palette (or an appended ramp) as a single reversible step. Truncated to
        the palette capacity defensively (Article VII).
        """
        if self._palette is None:
            return
        capped = list(colors)[: self._palette_capacity()]
        self._push(self._palette.colors(), capped, label)

    def selected_color(self) -> Optional[RGBA]:
        """Return the RGBA of the selected swatch, or ``None``."""
        items = self._list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    # -- command plumbing -------------------------------------------------

    def _push(self, before: List[RGBA], after: List[RGBA], label: str) -> None:
        """Push one reversible palette edit (do=after, undo=before)."""
        palette = self._palette
        if palette is None or self._undo_stack is None:
            return
        command = history.FunctionCommand(
            do=lambda: _set_palette_contents(palette, after),
            undo=lambda: _set_palette_contents(palette, before),
            label=label,
        )
        self._undo_stack.push(LogicCommand(command, self._refresh_after, label))

    def _refresh_after(self) -> None:
        """Repaint the editor + notify the shell after a mutation / undo / redo."""
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()

    # -- slots ------------------------------------------------------------

    def _on_selection_changed(self) -> None:
        if self._syncing:
            return
        color = self.selected_color()
        if color is not None:
            self.colorSelected.emit(color)

    def _on_add(self) -> None:
        if self._palette is None:
            return
        before = self._palette.colors()
        if len(before) >= self._palette_capacity():
            QMessageBox.warning(
                self, self.tr("Add Colour"), self.tr("The palette is full.")
            )
            return
        after = before + [self._active_color]
        self._push(before, after, self.tr("Add Colour"))

    def _palette_capacity(self) -> int:
        from pixelart_creator.logic.palette import MAX_PALETTE_SIZE

        return MAX_PALETTE_SIZE

    def _on_remove(self) -> None:
        if self._palette is None:
            return
        row = self._list.currentRow()
        before = self._palette.colors()
        if not 0 <= row < len(before):
            return
        after = before[:row] + before[row + 1 :]
        self._push(before, after, self.tr("Remove Colour"))

    def _on_move(self, delta: int) -> None:
        if self._palette is None:
            return
        row = self._list.currentRow()
        before = self._palette.colors()
        target = row + delta
        if not (0 <= row < len(before) and 0 <= target < len(before)):
            return
        after = list(before)
        after.insert(target, after.pop(row))
        self._push(before, after, self.tr("Reorder Palette"))
        self._list.setCurrentRow(target)

    def _on_rows_moved(self, *_args: object) -> None:
        """Turn a completed drag-drop reorder into one reversible command."""
        if self._syncing or self._palette is None:
            return
        before = self._palette.colors()
        after = [
            self._list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self._list.count())
        ]
        if after == before or len(after) != len(before):
            return
        self._push(before, after, self.tr("Reorder Palette"))

    # -- import / export --------------------------------------------------

    def _on_export(self) -> None:
        if self._palette is None:
            return
        filters = ";;".join(label for label, _, _ in _FILTERS)
        path, selected = QFileDialog.getSaveFileName(
            self, self.tr("Export Palette"), "", filters
        )
        if not path:
            return
        fmt = self._fmt_for(path, selected)
        try:
            text = encode(self._palette, fmt)
            Path(path).write_text(text, encoding="utf-8")
        except (PaletteIOError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Export Palette"), str(exc))

    def _on_import(self) -> None:
        if self._palette is None or self._undo_stack is None:
            return
        filters = ";;".join(label for label, _, _ in _FILTERS)
        path, selected = QFileDialog.getOpenFileName(
            self, self.tr("Import Palette"), "", filters
        )
        if not path:
            return
        fmt = self._fmt_for(path, selected)
        try:
            text = Path(path).read_text(encoding="utf-8")
            imported = decode(text, fmt)
        except (PaletteIOError, OSError, ValueError) as exc:
            # A malformed file surfaces an error and never crashes (SC-U002-2).
            QMessageBox.warning(self, self.tr("Import Palette"), str(exc))
            return
        self._push(self._palette.colors(), imported.colors(), self.tr("Import Palette"))

    @staticmethod
    def _fmt_for(path: str, selected_filter: str) -> str:
        """Resolve the ``palette_io`` format from the path suffix / dialog filter."""
        suffix = Path(path).suffix.lower()
        for label, fmt, ext in _FILTERS:
            if suffix == ext or label == selected_filter:
                return fmt
        return "hex"

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Palette Editor"))
        self.setAccessibleName(self.tr("Palette editor panel"))
        self._list.setAccessibleName(self.tr("Editable colour palette"))
        self._add_button.setText(self.tr("Add"))
        self._add_button.setToolTip(self.tr("Add the active colour"))
        self._remove_button.setText(self.tr("Remove"))
        self._up_button.setText(self.tr("Move Up"))
        self._down_button.setText(self.tr("Move Down"))
        self._import_button.setText(self.tr("Import…"))
        self._export_button.setText(self.tr("Export…"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Palette_Editor_Panel"]
