"""Palette analytics view (REQ-P3-UI-011): per-colour / per-index usage counts.

``Palette_Analytics_View`` is a **read-only**, sortable table of how often each
colour (RGBA document) or palette index (indexed document) is used across the
active document. The counts come from
:func:`pixelart_creator.logic.palette_analytics.document_usage_counts` (vectorised,
read-only, F7) — this view never mutates anything and holds no maths (Article I /
S11). It refreshes on demand from a supplied document provider. Strings are
``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange` (F5); the table is
keyboard-reachable and legible in both themes.
"""

from __future__ import annotations

from typing import Callable, Optional, cast

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import RGBA, to_hex
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette_analytics import document_usage_counts
from pixelart_creator.logic.pixel_buffer import ColorMode

#: Edge of a colour-swatch icon in the table, px (presentation-only sizing).
_SWATCH_PX = 18


class Palette_Analytics_View(QWidget):
    """Read-only, sortable per-colour / per-index usage table."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the usage table and its Refresh button."""
        super().__init__(parent)
        self._provider: Optional[Callable[[], Optional[Document]]] = None

        self._title = QLabel(self)
        self._table = QTableWidget(0, 2, self)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._refresh_button = QPushButton(self)
        self._refresh_button.clicked.connect(self.refresh)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._table)
        layout.addWidget(self._refresh_button)
        self._retranslate()

    # -- binding ----------------------------------------------------------

    def set_document_provider(self, provider: Callable[[], Optional[Document]]) -> None:
        """Bind a callable returning the active document (or ``None``)."""
        self._provider = provider

    def refresh(self) -> None:
        """Recompute + display usage counts for the active document (read-only)."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        document = self._provider() if self._provider is not None else None
        if document is not None:
            indexed = document.mode is ColorMode.INDEXED
            for key, count in document_usage_counts(document):
                self._append_row(key, count, indexed)
        self._table.setSortingEnabled(True)

    def _append_row(self, key: object, count: int, indexed: bool) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        if indexed:
            key_item = QTableWidgetItem()
            # Numeric DisplayRole so the column sorts by index, not lexically.
            key_item.setData(Qt.ItemDataRole.DisplayRole, cast(int, key))
        else:
            color = cast(RGBA, key)
            key_item = QTableWidgetItem(to_hex(color))
            pixmap = QPixmap(_SWATCH_PX, _SWATCH_PX)
            pixmap.fill(QColor(*color))
            key_item.setIcon(QIcon(pixmap))
        count_item = QTableWidgetItem()
        count_item.setData(Qt.ItemDataRole.DisplayRole, int(count))
        self._table.setItem(row, 0, key_item)
        self._table.setItem(row, 1, count_item)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Palette Analytics"))
        self.setAccessibleName(self.tr("Palette analytics view"))
        self._table.setAccessibleName(self.tr("Colour usage counts"))
        self._table.setHorizontalHeaderLabels(
            [self.tr("Colour / Index"), self.tr("Usage count")]
        )
        self._refresh_button.setText(self.tr("Refresh"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Palette_Analytics_View"]
