# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
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

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QShowEvent
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

#: Debounce window (ms) coalescing a burst of deferred refresh requests into a
#: single buffer scan (presentation-only timing, not a domain tuning value —
#: cf. _SWATCH_PX). Short enough to feel instant when the dock becomes visible.
_REFRESH_DEBOUNCE_MS = 150


class Palette_Analytics_View(QWidget):
    """Read-only, sortable per-colour / per-index usage table."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the usage table and its Refresh button."""
        super().__init__(parent)
        self._provider: Optional[Callable[[], Optional[Document]]] = None
        # Lazy-scan state: a pending refresh is deferred while the view is not
        # visible (the full-buffer scan is ~tens of seconds at 8K, so opening a
        # document with this dock hidden must do ZERO scan). It is computed when
        # the dock becomes visible; a short single-shot timer coalesces a burst of
        # triggers into one scan (debounce).
        self._pending = False
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_REFRESH_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._recompute_if_pending)

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
        """Recompute + display usage counts NOW (explicit / manual Refresh path).

        This is the eager path: it always scans the active document buffer. It
        backs the Refresh button (an explicit user action taken while the view is
        on screen). The document-open / palette-change triggers instead call
        :meth:`request_refresh`, which defers the scan while the dock is hidden.
        """
        self._debounce.stop()
        self._pending = False
        self._recompute()

    def request_refresh(self) -> None:
        """Request a refresh lazily — scan only while visible, else defer (F7).

        Marks the view dirty and, only when it is actually visible, arms the
        debounce timer so a burst of document edits coalesces into a single scan.
        While the dock is hidden nothing is scanned; the pending refresh is
        computed when :meth:`on_dock_visibility_changed` (or :meth:`showEvent`)
        reports the view has become visible. Net effect: opening a document with
        this dock hidden does ZERO buffer scan.
        """
        self._pending = True
        if self.isVisible():
            self._debounce.start()

    def on_dock_visibility_changed(self, visible: bool) -> None:
        """Compute a deferred refresh when the analytics dock becomes visible.

        Wired to :data:`QDockWidget.visibilityChanged` — the robust Qt signal for
        a dock's real visibility (it fires for tabified docks brought to front,
        (un)minimise and (un)float), unlike a bare ``showEvent`` which a tabbed
        dock does not reliably emit on tab switch.
        """
        if visible and self._pending:
            self._debounce.start()

    def _recompute_if_pending(self) -> None:
        """Debounce-timer slot: run the deferred scan iff one is still pending."""
        if self._pending:
            self._pending = False
            self._recompute()

    def _recompute(self) -> None:
        """Scan the active document and rebuild the usage table (read-only)."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        document = self._provider() if self._provider is not None else None
        if document is not None:
            indexed = document.mode is ColorMode.INDEXED
            for key, count in document_usage_counts(document):
                self._append_row(key, count, indexed)
        self._table.setSortingEnabled(True)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Compute a deferred refresh when the view is shown (non-dock guard).

        Secondary to :meth:`on_dock_visibility_changed`; covers the view being
        shown outside a ``QDockWidget`` (e.g. embedded directly or in a test).
        """
        super().showEvent(event)
        if self._pending:
            self._debounce.start()

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
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Palette_Analytics_View"]
