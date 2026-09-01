# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Asset-library panel — browse the catalog by kind / name / tags (REQ-P11-UI-001).

``Asset_Library_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget`
that lists the entries of the shared
:class:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session`'s in-memory
catalog in a three-column view (name / kind / tags). It performs **no** domain logic
(Article I / S11): the listing it shows is exactly the result of the pure
:func:`~pixelart_creator.logic.asset_query.query` over the session catalog, and it
re-reads and repaints whenever the catalog changes (``catalogChanged``) — so adding,
removing, or tagging an asset updates the panel (REQ-P11-UI-001 acceptance).

It is also the single **list surface** the search/filter panel drives (REQ-P11-UI-003):
:meth:`set_query` narrows the display to the matching entries; an empty query restores
the full catalog. Selecting a row emits :data:`~Asset_Library_Panel.assetSelected` with
the entry's stable ``asset_id`` (or ``""`` when the selection clears) so the tagging
panel can follow the selection.

Slice 2 adds a **passive break surface** (REQ-P11-UI-006, CL-4): a Status column that
flags any listed asset whose outgoing reference is broken, reflecting the pure
:func:`~pixelart_creator.logic.break_detection.find_broken` reference-validation pass
over the session's dependency graph + catalog. It **refreshes on catalog change** (and
graph change) via ``catalogChanged`` / ``graphChanged`` and raises **no** push
notification / dialog — an asset with a broken reference shows the flag, one with only
valid references shows none.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role, so
both themes render correctly with no per-widget colour (REQ-P11-UI-009). All work is
synchronous over the in-memory catalog / graph — no worker thread / timer (Slice 1/2).
"""

from __future__ import annotations

from typing import FrozenSet, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetDescriptor, AssetKind
from pixelart_creator.logic.asset_query import query
from pixelart_creator.logic.break_detection import find_broken
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session

_COL_NAME = 0
_COL_KIND = 1
_COL_TAGS = 2
_COL_STATUS = 3


class Asset_Library_Panel(QWidget):
    """Browse the catalog; drives the pure query and follows the selection."""

    #: Emitted with the selected entry's ``asset_id`` (``""`` when cleared).
    assetSelected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the three-column catalog view."""
        super().__init__(parent)
        self._session: Optional[Asset_Library_Session] = None
        #: The active filter driven by the search panel (empty = full catalog).
        self._name: Optional[str] = None
        self._tags: Tuple[str, ...] = ()
        self._kind: Optional[AssetKind] = None

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(4)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._on_current_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree, 1)

        self._retranslate()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Asset_Library_Session) -> None:
        """Bind the panel to a :class:`Asset_Library_Session` and refresh the view."""
        self._session = session
        session.catalogChanged.connect(self._refresh)
        # The passive break surface (Slice 2) refreshes on a graph change too.
        session.graphChanged.connect(self._refresh)
        self._refresh()

    # -- search/filter (driven by Asset_Search_Panel) ---------------------

    def set_query(
        self,
        name: str = "",
        tags: Sequence[str] = (),
        kind: Optional[AssetKind] = None,
    ) -> None:
        """Narrow the listed entries to those matching the filter, then refresh.

        Args:
            name: A case-insensitive name substring; ``""`` applies no name filter.
            tags: Tags the entry must carry all of; empty applies no tag filter.
            kind: The :class:`AssetKind` the entry must have; ``None`` applies none.
        """
        self._name = name or None
        self._tags = tuple(tags)
        self._kind = kind
        self._refresh()

    def current_asset_id(self) -> str:
        """Return the selected entry's ``asset_id`` (``""`` when none is selected)."""
        item = self._tree.currentItem()
        if item is None:
            return ""
        return str(item.data(_COL_NAME, Qt.ItemDataRole.UserRole))

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        """Repopulate the tree from the current query over the session catalog."""
        selected = self.current_asset_id()
        self._tree.clear()
        if self._session is None:
            return
        results = query(
            self._session.catalog(),
            name=self._name,
            tags=list(self._tags),
            kind=self._kind,
        )
        broken_sources = self.broken_source_ids()
        restored: Optional[QTreeWidgetItem] = None
        for descriptor in results:
            item = self._make_item(descriptor, broken_sources)
            self._tree.addTopLevelItem(item)
            if descriptor.asset_id == selected:
                restored = item
        if restored is not None:
            self._tree.setCurrentItem(restored)

    def broken_source_ids(self) -> FrozenSet[str]:
        """Return the ids whose outgoing reference is flagged by the validation pass.

        Pure pull over :func:`find_broken` for the session graph + catalog (empty when
        unbound); the panel marks these rows passively (REQ-P11-UI-006).
        """
        if self._session is None:
            return frozenset()
        refs = find_broken(self._session.graph(), self._session.catalog())
        return frozenset(ref.source_id for ref in refs)

    def _make_item(
        self, descriptor: AssetDescriptor, broken_sources: FrozenSet[str]
    ) -> QTreeWidgetItem:
        status = (
            self.tr("Broken reference") if descriptor.asset_id in broken_sources else ""
        )
        item = QTreeWidgetItem(
            [
                descriptor.name,
                self._kind_text(descriptor.kind),
                ", ".join(sorted(descriptor.tags)),
                status,
            ]
        )
        item.setData(_COL_NAME, Qt.ItemDataRole.UserRole, descriptor.asset_id)
        if status:
            item.setToolTip(_COL_STATUS, status)
            item.setToolTip(_COL_NAME, status)
        return item

    def _on_current_changed(self) -> None:
        self.assetSelected.emit(self.current_asset_id())

    # -- i18n -------------------------------------------------------------

    def _kind_text(self, kind: AssetKind) -> str:
        """Return the translated display label for an :class:`AssetKind`."""
        labels = {
            AssetKind.SPRITE: self.tr("Sprite"),
            AssetKind.ANIMATION: self.tr("Animation"),
            AssetKind.TILESET: self.tr("Tileset"),
            AssetKind.TILEMAP: self.tr("Tilemap"),
            AssetKind.PALETTE: self.tr("Palette"),
        }
        return labels.get(kind, kind.value)

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Asset library"))
        self._tree.setHeaderLabels(
            [self.tr("Name"), self.tr("Kind"), self.tr("Tags"), self.tr("Status")]
        )
        self._tree.setAccessibleName(self.tr("Catalog assets"))
        # Re-render the kind column labels already in the tree.
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the library strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
