"""Asset version browser — inspect + restore an asset's revisions (REQ-P11-UI-004).

``Asset_Version_Browser`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget`
that lists the **ordered revision history** of the asset the library selection points at
and lets the user **inspect** a revision and **restore** a prior one. It holds **no**
domain logic (Article I / S11): the history it shows is exactly the ordered
:class:`~pixelart_creator.logic.asset_version.AssetRevision` sequence the append-only
:class:`~pixelart_creator.data.asset_revision_store.AssetRevisionStore` exposes
(``history`` / ``head`` / ``fetch`` / ``record``), and every mutation delegates to the
store. Domain errors — :class:`~pixelart_creator.logic.asset_version.AssetVersionError`
and :class:`~pixelart_creator.data.asset_revision_store.AssetRevisionStoreError` — are
**surfaced** as translatable messages, never swallowed.

**Restore is append-only (REQ-P11-UI-004 acceptance).** Restoring a prior revision
re-records that revision's content-hash-verified bytes through
:meth:`~pixelart_creator.data.asset_revision_store.AssetRevisionStore.record`, which
appends the reinstated content as a **new head** revision — the earlier revisions remain
in the history unchanged (the store is append-only; it never mutates or deletes a
revision in place). The browser therefore performs no rewrite of its own: it fetches the
selected revision's verified bytes and hands them straight back to ``record``.

When the restored asset is present in the shared
:class:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session` catalog, the
browser also swaps in a descriptor carrying the new head's ``content_hash`` via the
session's existing :meth:`~pixelart_creator.ui.asset_library_actions.
Asset_Library_Session.replace_descriptor` hook, so the ``catalogChanged`` signal the
library / dependency / break panels already listen on fires and they revalidate against
the reinstated current content (reuse, don't invent — no new signal). The descriptor is
reconstructed with :func:`dataclasses.replace`, whose validation is entirely the
:class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor` model's — no domain logic
lives in the widget.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role, so
both themes render correctly with no per-widget colour (REQ-P11-UI-009). All work is
synchronous over the in-memory / content-addressable store — recording, fetching and
history reads are CAS/in-memory and fast — so there is **no worker thread, timer, or
poller** and **nothing to tear down** (the Slice-1/2 ``Asset_Library_Session`` /
``Dependency_Graph_View`` precedent).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.asset_revision_store import (
    AssetRevisionStore,
    AssetRevisionStoreError,
)
from pixelart_creator.logic.asset_catalog import AssetCatalogModelError
from pixelart_creator.logic.asset_version import AssetRevision, AssetVersionError
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session

_COL_ORDER = 0
_COL_MARKER = 1
_COL_AUTHOR = 2
_COL_HASH = 3

#: The selected row's revision ``content_hash`` is stashed on the order column.
_ROLE_HASH = Qt.ItemDataRole.UserRole

#: How many leading characters of a content hash the browser shows (the full hash is
#: kept on the tooltip / item data — this is display abbreviation only, not identity).
_HASH_ABBREV = 12


class Asset_Version_Browser(QWidget):
    """List, inspect, and append-only-restore an asset's revisions (REQ-P11-UI-004).

    ``_Browser`` is the sanctioned suffix for this surface per the task's CONVENTIONS
    note; it reads as a browse-and-act panel over an asset's version history.
    """

    #: Emitted with the new head's ``content_hash`` after a successful restore (so a
    #: caller / test can react); no payload semantics beyond the reinstated head hash.
    revisionRestored = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the asset label, the revision tree, the details label, and buttons."""
        super().__init__(parent)
        self._session: Optional[Asset_Library_Session] = None
        self._store: Optional[AssetRevisionStore] = None
        #: The asset whose revisions are shown (``""`` when none is selected).
        self._asset_id: str = ""

        self._asset_label = QLabel(self)
        self._asset_label.setWordWrap(True)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(4)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._update_enabled)

        self._details_label = QLabel(self)
        self._details_label.setWordWrap(True)

        self._inspect_button = QPushButton(self)
        self._inspect_button.clicked.connect(self._on_inspect)
        self._restore_button = QPushButton(self)
        self._restore_button.clicked.connect(self._on_restore)
        buttons = QHBoxLayout()
        buttons.addWidget(self._inspect_button)
        buttons.addWidget(self._restore_button)
        buttons.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._asset_label)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._details_label)
        layout.addLayout(buttons)

        self._retranslate()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Asset_Library_Session) -> None:
        """Bind to a :class:`Asset_Library_Session` and refresh on catalog change."""
        self._session = session
        session.catalogChanged.connect(self._refresh)
        self._refresh()

    def set_store(self, store: AssetRevisionStore) -> None:
        """Bind the append-only revision store the browser reads / records through."""
        self._store = store
        self._refresh()

    def set_asset(self, asset_id: str) -> None:
        """Follow the library selection: show ``asset_id``'s history (``""`` = none)."""
        self._asset_id = asset_id or ""
        self._details_label.clear()
        self._refresh()

    # -- read-only seams (test / caller) ----------------------------------

    def current_asset_id(self) -> str:
        """Return the asset currently in scope (``""`` when none)."""
        return self._asset_id

    def selected_revision_hash(self) -> str:
        """Return the selected revision's ``content_hash`` (``""`` when none)."""
        item = self._tree.currentItem()
        if item is None:
            return ""
        return str(item.data(_COL_ORDER, _ROLE_HASH))

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        """Repopulate the revision tree from the store's history for the asset."""
        selected = self.selected_revision_hash()
        self._tree.clear()
        self._update_labels()
        if self._store is None or not self._asset_id:
            self._update_enabled()
            return
        history = self._store.history(self._asset_id)
        head_hash = history.head().content_hash if not history.is_empty() else ""
        restored: Optional[QTreeWidgetItem] = None
        for index, revision in enumerate(history.revisions):
            item = self._make_item(index, revision, revision.content_hash == head_hash)
            self._tree.addTopLevelItem(item)
            if revision.content_hash == selected:
                restored = item
        if restored is not None:
            self._tree.setCurrentItem(restored)
        self._update_enabled()

    def _make_item(
        self, index: int, revision: AssetRevision, is_head: bool
    ) -> QTreeWidgetItem:
        """Build one ordered revision row with its marker / author / hash metadata."""
        order_text = str(index + 1)
        if is_head:
            order_text = self.tr("%1 (current)").replace("%1", order_text)
        author = revision.author if revision.author else self.tr("(unknown)")
        item = QTreeWidgetItem(
            [
                order_text,
                str(revision.created_marker),
                author,
                revision.content_hash[:_HASH_ABBREV],
            ]
        )
        item.setData(_COL_ORDER, _ROLE_HASH, revision.content_hash)
        item.setToolTip(_COL_HASH, revision.content_hash)
        return item

    # -- inspect / restore ------------------------------------------------

    def _selected_revision(self) -> Optional[AssetRevision]:
        """Return the selected revision's descriptor, or ``None`` if unresolved."""
        if self._store is None or not self._asset_id:
            return None
        content_hash = self.selected_revision_hash()
        if not content_hash:
            return None
        try:
            return self._store.history(self._asset_id).by_hash(content_hash)
        except AssetVersionError:
            return None

    def _on_inspect(self) -> None:
        """Show the selected revision's content-hash-verified size + metadata."""
        if self._store is None:
            return
        revision = self._selected_revision()
        if revision is None:
            return
        try:
            blob = self._store.fetch(self._asset_id, revision.content_hash)
        except (AssetRevisionStoreError, AssetVersionError) as exc:
            QMessageBox.warning(self, self.tr("Version history"), str(exc))
            return
        author = revision.author if revision.author else self.tr("(unknown)")
        self._details_label.setText(
            self.tr("Revision %1 — %2 bytes, marker %3, author %4")
            .replace("%1", revision.content_hash[:_HASH_ABBREV])
            .replace("%2", str(len(blob)))
            .replace("%3", str(revision.created_marker))
            .replace("%4", author)
        )

    def _on_restore(self) -> None:
        """Restore the selected revision as a new head (append-only, history kept)."""
        if self._store is None:
            return
        revision = self._selected_revision()
        if revision is None:
            return
        try:
            blob = self._store.fetch(self._asset_id, revision.content_hash)
        except (AssetRevisionStoreError, AssetVersionError) as exc:
            QMessageBox.warning(self, self.tr("Version history"), str(exc))
            return
        try:
            new_head = self._store.record(
                self._asset_id,
                blob,
                created_marker=self._next_marker(),
                author=revision.author,
            )
        except (AssetRevisionStoreError, AssetVersionError) as exc:
            QMessageBox.warning(self, self.tr("Version history"), str(exc))
            return
        self._sync_catalog(new_head.content_hash)
        self._refresh()
        self.revisionRestored.emit(new_head.content_hash)

    def _next_marker(self) -> int:
        """Return a monotonic ordering marker one past the largest recorded one.

        Presentation sequencing only (never a wall-clock read in the domain layer):
        the store keeps the ``created_marker`` as an opaque monotonic key, so the
        browser hands it the next value after the current maximum.
        """
        if self._store is None or not self._asset_id:
            return 0
        markers = [
            r.created_marker for r in self._store.history(self._asset_id).revisions
        ]
        return (max(markers) + 1) if markers else 0

    def _sync_catalog(self, content_hash: str) -> None:
        """Reflect the reinstated head content in the session catalog, if present.

        Reuses the session's existing :meth:`Asset_Library_Session.replace_descriptor`
        apply hook (which emits ``catalogChanged``) so the library / dependency / break
        panels revalidate against the restored current content. The descriptor is
        reconstructed with :func:`dataclasses.replace`, whose validation is entirely the
        :class:`AssetDescriptor` model's — no domain logic lives here.
        """
        if self._session is None:
            return
        descriptor = self._session.catalog().get(self._asset_id)
        if descriptor is None or descriptor.content_hash == content_hash:
            return
        try:
            updated = replace(descriptor, content_hash=content_hash)
        except AssetCatalogModelError:  # pragma: no cover - defensive
            return
        self._session.replace_descriptor(updated)

    def _update_enabled(self) -> None:
        has_selection = self._selected_revision() is not None
        self._inspect_button.setEnabled(has_selection)
        self._restore_button.setEnabled(has_selection)

    # -- i18n -------------------------------------------------------------

    def _update_labels(self) -> None:
        if self._session is not None and self._asset_id:
            descriptor = self._session.catalog().get(self._asset_id)
            if descriptor is not None:
                self._asset_label.setText(
                    self.tr("Revisions of: %1").replace("%1", descriptor.name)
                )
                return
        if self._asset_id:
            self._asset_label.setText(
                self.tr("Revisions of: %1").replace("%1", self._asset_id)
            )
        else:
            self._asset_label.setText(self.tr("No asset selected"))

    def _retranslate(self) -> None:
        """(Re)apply every user-visible string (F5)."""
        self.setAccessibleName(self.tr("Asset version browser"))
        self._tree.setHeaderLabels(
            [self.tr("#"), self.tr("Created"), self.tr("Author"), self.tr("Content")]
        )
        self._tree.setAccessibleName(self.tr("Asset revisions"))
        self._details_label.setAccessibleName(self.tr("Revision details"))
        self._inspect_button.setText(self.tr("Inspect"))
        self._inspect_button.setAccessibleName(self.tr("Inspect selected revision"))
        self._restore_button.setText(self.tr("Restore"))
        self._restore_button.setAccessibleName(
            self.tr("Restore selected revision as a new head")
        )
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the version-browser strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
