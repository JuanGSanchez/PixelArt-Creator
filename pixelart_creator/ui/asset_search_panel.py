# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Asset search/filter panel — drive the pure catalog query (REQ-P11-UI-003).

``Asset_Search_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` that
collects a **name** substring, **tag(s)**, and a **kind** filter and drives the pure,
deterministic :func:`~pixelart_creator.logic.asset_query.query` (via the library panel's
``set_query``). It holds
**no** domain logic (Article I / S11): it only translates its controls into query
arguments — the filtering and ordering are entirely the Qt-free query. The three filters
**intersect** (name AND tags AND kind); clearing every control restores the full catalog
(REQ-P11-UI-003 acceptance).

It emits :data:`~Asset_Search_Panel.queryChanged` with ``(name, tags, kind)`` on every
edit so the caller can bind it to the library panel; the tag box accepts a
comma-separated list, and the kind combo carries an "All kinds" entry plus one entry per
:class:`~pixelart_creator.logic.asset_catalog.AssetKind`.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role
(REQ-P11-UI-009). All work is synchronous over the in-memory catalog — no worker thread
/ timer (Slice 1).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetKind

#: The fixed display order of the kind combo (after the "All kinds" entry).
_KIND_ORDER: Tuple[AssetKind, ...] = (
    AssetKind.SPRITE,
    AssetKind.ANIMATION,
    AssetKind.TILESET,
    AssetKind.TILEMAP,
    AssetKind.PALETTE,
)


class Asset_Search_Panel(QWidget):
    """Search (name) + filter (tag / kind) controls driving the pure query."""

    #: Emitted with ``(name, tags, kind)`` whenever a control changes. ``name`` is
    #: a possibly-empty str, ``tags`` a list of str, ``kind`` an ``AssetKind`` or
    #: ``None``. The library panel consumes it via ``set_query``.
    queryChanged = Signal(str, list, object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the name, tag, and kind controls plus a clear button."""
        super().__init__(parent)

        self._name_label = QLabel(self)
        self._name_edit = QLineEdit(self)
        self._name_edit.textChanged.connect(self._emit_query)

        self._tag_label = QLabel(self)
        self._tag_edit = QLineEdit(self)
        self._tag_edit.textChanged.connect(self._emit_query)

        self._kind_label = QLabel(self)
        self._kind_combo = QComboBox(self)
        self._kind_combo.addItem("", None)  # "All kinds"; text set in _retranslate
        for kind in _KIND_ORDER:
            self._kind_combo.addItem("", kind)
        self._kind_combo.currentIndexChanged.connect(self._emit_query)

        self._clear_button = QPushButton(self)
        self._clear_button.clicked.connect(self.clear)

        form = QFormLayout()
        form.addRow(self._name_label, self._name_edit)
        form.addRow(self._tag_label, self._tag_edit)
        form.addRow(self._kind_label, self._kind_combo)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._clear_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self._retranslate()

    # -- query state ------------------------------------------------------

    def name_filter(self) -> str:
        """Return the current name substring (possibly empty)."""
        return self._name_edit.text().strip()

    def tag_filters(self) -> List[str]:
        """Return the current tag filters (comma-split, trimmed, non-empty)."""
        raw = self._tag_edit.text()
        return [tag.strip() for tag in raw.split(",") if tag.strip()]

    def kind_filter(self) -> Optional[AssetKind]:
        """Return the selected :class:`AssetKind`, or ``None`` for "All kinds"."""
        data = self._kind_combo.currentData()
        return data if isinstance(data, AssetKind) else None

    def clear(self) -> None:
        """Reset every control (restores the full catalog on the next emit)."""
        self._name_edit.clear()
        self._tag_edit.clear()
        self._kind_combo.setCurrentIndex(0)
        self._emit_query()

    # -- emission ---------------------------------------------------------

    def _emit_query(self) -> None:
        self.queryChanged.emit(
            self.name_filter(), self.tag_filters(), self.kind_filter()
        )

    # -- i18n -------------------------------------------------------------

    def _kind_text(self, kind: AssetKind) -> str:
        labels = {
            AssetKind.SPRITE: self.tr("Sprite"),
            AssetKind.ANIMATION: self.tr("Animation"),
            AssetKind.TILESET: self.tr("Tileset"),
            AssetKind.TILEMAP: self.tr("Tilemap"),
            AssetKind.PALETTE: self.tr("Palette"),
        }
        return labels.get(kind, kind.value)

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Asset search and filter"))
        self._name_label.setText(self.tr("Name:"))
        self._name_edit.setPlaceholderText(self.tr("Search by name"))
        self._name_edit.setAccessibleName(self.tr("Search by name"))
        self._tag_label.setText(self.tr("Tags:"))
        self._tag_edit.setPlaceholderText(self.tr("Filter by tags (comma-separated)"))
        self._tag_edit.setAccessibleName(self.tr("Filter by tags"))
        self._kind_label.setText(self.tr("Kind:"))
        self._kind_combo.setAccessibleName(self.tr("Filter by kind"))
        self._kind_combo.setItemText(0, self.tr("All kinds"))
        for index, kind in enumerate(_KIND_ORDER, start=1):
            self._kind_combo.setItemText(index, self._kind_text(kind))
        self._clear_button.setText(self.tr("Clear"))
        self._clear_button.setAccessibleName(self.tr("Clear the search and filters"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the search strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
