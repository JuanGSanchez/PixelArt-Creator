"""Cross-project reuse panel — reference a shared asset, no copy (REQ-P11-UI-007).

``Asset_Reuse_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` that
lets the user **reference an existing shared asset into a project** and marks an asset
**shared** when more than one project references it. It holds **no** domain logic
(Article I / S11): a reference is the pure reference-not-copy model the
``logic``/``data`` layer already defines — a project's references are an
:class:`~pixelart_creator.logic.asset_catalog.AssetCatalog` (which stores **references +
metadata, never a copy of the payload**, ADR-0030), and referencing an asset is
``project_catalog.add(descriptor)`` of the *shared* descriptor by its ``asset_id`` +
``content_hash``. **No bytes are ever copied**: the shared blob lives once in the
content-addressable store (:mod:`~pixelart_creator.data.asset_cas`), so referencing does
**not** call :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.put` — the
CAS blob count is unchanged (REQ-P11-UI-007 acceptance). When a
:class:`~pixelart_creator.data.asset_cas.ContentAddressableStore` is bound, the panel
only :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.has`-checks the
shared content is present before referencing it (a read; never a write), surfacing a
translatable error when the shared bytes are absent.

The shared library the assets are referenced *from* is the shared
:class:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session` catalog (the
single source, refreshed on ``catalogChanged``). A project is a named reference set the
panel tracks as presentation state (``Dict[str, AssetCatalog]``); an asset is **shared**
when its ``asset_id`` appears in more than one project's reference catalog — a trivial
count over the logic values, not domain maths. Referencing mutates only the panel's own
project reference sets, never the shared session catalog, so it emits no session change
signal (nothing else observes project references); the panel exposes its own
:data:`~Asset_Reuse_Panel.assetReferenced` signal for callers / tests.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role, so
both themes render correctly (REQ-P11-UI-009). All work is synchronous over in-memory
values — no worker thread, timer, or poller, and **nothing to tear down** (the Slice-1/2
precedent).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetKind,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session

_COL_NAME = 0
_COL_KIND = 1
_COL_SHARED = 2
_COL_COUNT = 3

#: The selected asset row's ``asset_id`` is stashed on the name column.
_ROLE_ASSET = Qt.ItemDataRole.UserRole


class Asset_Reuse_Panel(QWidget):
    """Reference a shared asset into a project without copying its bytes (UI-007)."""

    #: Emitted with ``(asset_id, project)`` after a successful reference.
    assetReferenced = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the project selector, the shared-asset list, and the reference row."""
        super().__init__(parent)
        self._session: Optional[Asset_Library_Session] = None
        self._cas: Optional[ContentAddressableStore] = None
        #: Each project's reference set — an AssetCatalog of references (no payload).
        self._projects: Dict[str, AssetCatalog] = {}

        self._project_label = QLabel(self)
        self._project_combo = QComboBox(self)
        self._new_project_edit = QLineEdit(self)
        self._new_project_edit.returnPressed.connect(self._on_add_project)
        self._add_project_button = QPushButton(self)
        self._add_project_button.clicked.connect(self._on_add_project)
        project_row = QHBoxLayout()
        project_row.addWidget(self._project_label)
        project_row.addWidget(self._project_combo, 1)
        project_row.addWidget(self._new_project_edit, 1)
        project_row.addWidget(self._add_project_button)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(4)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._update_enabled)

        self._reference_button = QPushButton(self)
        self._reference_button.clicked.connect(self._on_reference)
        self._status_label = QLabel(self)
        self._status_label.setWordWrap(True)
        button_row = QHBoxLayout()
        button_row.addWidget(self._reference_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(project_row)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._status_label)
        layout.addLayout(button_row)

        self._retranslate()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Asset_Library_Session) -> None:
        """Bind to a :class:`Asset_Library_Session` (the shared library) and refresh."""
        self._session = session
        session.catalogChanged.connect(self._refresh)
        self._refresh()

    def set_content_store(self, cas: ContentAddressableStore) -> None:
        """Bind the CAS the panel ``has``-checks (never writes) on a reference."""
        self._cas = cas

    # -- project management (presentation state) --------------------------

    def add_project(self, name: str) -> None:
        """Create an empty reference set for ``name`` (no-op when it already exists)."""
        name = name.strip()
        if not name or name in self._projects:
            return
        self._projects[name] = AssetCatalog()
        self._project_combo.addItem(name)
        self._project_combo.setCurrentText(name)
        self._refresh()

    def current_project(self) -> str:
        """Return the selected project name (``""`` when none)."""
        return self._project_combo.currentText()

    def _on_add_project(self) -> None:
        self.add_project(self._new_project_edit.text())
        self._new_project_edit.clear()

    # -- reference (reference-not-copy; no CAS write) ---------------------

    def current_asset_id(self) -> str:
        """Return the selected shared asset's ``asset_id`` (``""`` when none)."""
        item = self._tree.currentItem()
        if item is None:
            return ""
        return str(item.data(_COL_NAME, _ROLE_ASSET))

    def _on_reference(self) -> None:
        """Add the selected shared asset to the project as a reference (no copy)."""
        if self._session is None:
            return
        project = self.current_project()
        asset_id = self.current_asset_id()
        if not project or not asset_id:
            return
        descriptor = self._session.catalog().get(asset_id)
        if descriptor is None:
            self._status_label.setText(self.tr("The selected asset is not available."))
            return
        # Reference-not-copy: the shared bytes must already live once in the CAS; we
        # only confirm their presence (a read) — we never put(), so the blob count is
        # unchanged.
        if self._cas is not None and not self._cas.has(descriptor.content_hash):
            self._status_label.setText(
                self.tr("Shared content for %1 is not available.").replace(
                    "%1", descriptor.name
                )
            )
            return
        try:
            self._projects[project] = self._projects[project].add(descriptor)
        except AssetCatalogModelError:
            self._status_label.setText(
                self.tr("%1 is already referenced in %2.")
                .replace("%1", descriptor.name)
                .replace("%2", project)
            )
            return
        self._status_label.setText(
            self.tr("Referenced %1 into %2.")
            .replace("%1", descriptor.name)
            .replace("%2", project)
        )
        self._refresh()
        self.assetReferenced.emit(asset_id, project)

    # -- read-only seams (test / caller) ----------------------------------

    def reference_count(self, asset_id: str) -> int:
        """Return how many projects reference ``asset_id`` (shared iff ``> 1``)."""
        return sum(
            1
            for catalog in self._projects.values()
            if catalog.get(asset_id) is not None
        )

    def is_shared(self, asset_id: str) -> bool:
        """Return whether ``asset_id`` is referenced by more than one project."""
        return self.reference_count(asset_id) > 1

    def project_references(self, project: str) -> Tuple[str, ...]:
        """Return the ``asset_id`` s referenced by ``project`` (deterministic order)."""
        catalog = self._projects.get(project)
        if catalog is None:
            return ()
        return tuple(descriptor.asset_id for descriptor in catalog.entries())

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        """Repopulate the shared-asset list + its shared / reference-count markers."""
        selected = self.current_asset_id()
        self._tree.clear()
        if self._session is None:
            self._update_enabled()
            return
        restored: Optional[QTreeWidgetItem] = None
        for descriptor in self._session.catalog().entries():
            count = self.reference_count(descriptor.asset_id)
            shared = self.tr("Shared") if count > 1 else ""
            item = QTreeWidgetItem(
                [
                    descriptor.name,
                    self._kind_text(descriptor.kind),
                    shared,
                    str(count),
                ]
            )
            item.setData(_COL_NAME, _ROLE_ASSET, descriptor.asset_id)
            if shared:
                item.setToolTip(_COL_SHARED, shared)
            self._tree.addTopLevelItem(item)
            if descriptor.asset_id == selected:
                restored = item
        if restored is not None:
            self._tree.setCurrentItem(restored)
        self._update_enabled()

    def _update_enabled(self) -> None:
        can_reference = (
            self._session is not None
            and bool(self.current_project())
            and self._tree.currentItem() is not None
        )
        self._reference_button.setEnabled(can_reference)

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
        """(Re)apply every user-visible string (F5)."""
        self.setAccessibleName(self.tr("Cross-project reuse"))
        self._project_label.setText(self.tr("Project:"))
        self._project_combo.setAccessibleName(self.tr("Target project"))
        self._new_project_edit.setPlaceholderText(self.tr("New project name"))
        self._new_project_edit.setAccessibleName(self.tr("New project name"))
        self._add_project_button.setText(self.tr("Add Project"))
        self._add_project_button.setAccessibleName(self.tr("Add a project"))
        self._tree.setHeaderLabels(
            [self.tr("Name"), self.tr("Kind"), self.tr("Shared"), self.tr("Projects")]
        )
        self._tree.setAccessibleName(self.tr("Shared assets"))
        self._reference_button.setText(self.tr("Reference into Project"))
        self._reference_button.setAccessibleName(
            self.tr("Reference the selected asset into the project")
        )
        self._status_label.setAccessibleName(self.tr("Reuse status"))
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the reuse-panel strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
