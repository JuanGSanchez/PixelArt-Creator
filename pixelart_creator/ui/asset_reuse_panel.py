# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Cross-project reuse panel — reference a shared asset, no copy (REQ-P11-UI-007).

``Asset_Reuse_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` that
lets the user **reference an existing shared asset into a project**, marks an asset
**shared** when more than one open project references it, and shows — per in-project
reference — whether it still **resolves** in the local library. It holds **no** domain
logic (Article I / S11): a reference is the pure reference-not-copy model the
``logic`` layer already defines — a project's references are a
:class:`~pixelart_creator.logic.asset_references.ReferenceSet` (**references + display
labels, never a copy of the payload**, ADR-0030), and referencing an asset is
``reference_set.add(AssetReference(...))`` built from the *shared* descriptor's
``asset_id`` + ``content_hash``. **No bytes are ever copied**: the shared blob lives
once in the
content-addressable store (:mod:`~pixelart_creator.data.asset_cas`), so referencing does
**not** call :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.put` — the
CAS blob count is unchanged (REQ-P11-UI-007 acceptance). When a
:class:`~pixelart_creator.data.asset_cas.ContentAddressableStore` is bound, the panel
only :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.has`-checks the
shared content is present before referencing it (a read; never a write), surfacing a
translatable error when the shared bytes are absent.

The shared library the assets are referenced *from* is the shared
:class:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session` catalog (the
single source, refreshed on ``catalogChanged``). A project is a **real, durable**
:class:`~pixelart_creator.logic.asset_references.ReferenceSet` (``REQ-P11-UI-021``) —
the same value :mod:`~pixelart_creator.data.project_io` round-trips at
``FORMAT_VERSION 6`` — which a caller binds through :meth:`set_project_reference_set`
(typically the main window, after ``project_io.load_project_with_asset_refs``);
:meth:`add_project` creates a legitimately **empty** one for a project that references
nothing yet, never a fabricated placeholder. The panel computes **no predicate of its
own**: an asset's *shared* state comes from
:func:`~pixelart_creator.logic.asset_references.shared_ids` (an ``asset_id`` referenced
by more than one currently **open** project — the honesty bound is part of the model,
and the panel's labels state it, never implying knowledge of projects that are not
open) and, per in-project reference, its *resolve* state comes from
:func:`~pixelart_creator.logic.asset_references.resolve_states` /
:func:`~pixelart_creator.logic.asset_references.missing` (identity + content against
the local library catalog — never a name or a path, so renaming a library asset breaks
no reference). Referencing mutates only the panel's own project reference sets, never
the shared session catalog, so it emits no session change signal (nothing else observes
project references); the panel exposes its own
:data:`~Asset_Reuse_Panel.assetReferenced` signal for callers / tests.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role, so
both themes render correctly (REQ-P11-UI-009). All work is synchronous over in-memory
values — no worker thread, timer, or poller, and **nothing to tear down** (the Slice-1/2
precedent).
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Tuple

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
from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.asset_references import (
    STATE_EDITED,
    STATE_RESOLVED,
    AssetReference,
    AssetReferenceError,
    ReferenceSet,
    missing,
    reference_states,
    resolve_states,
    shared_ids,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session

_COL_NAME = 0
_COL_KIND = 1
_COL_SHARED = 2
_COL_COUNT = 3

#: Columns of the in-project reference list (REQ-P11-UI-021 indicators).
_PCOL_NAME = 0
_PCOL_KIND = 1
_PCOL_RESOLVE = 2
_PCOL_SHARED = 3

#: The selected asset row's ``asset_id`` is stashed on the name column (both trees).
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
        #: Each open project's real, durable reference set (REQ-P11-UI-021), bound
        #: through :meth:`set_project_reference_set` or created empty by
        #: :meth:`add_project`. Never a predicate's own scratch state.
        self._projects: Dict[str, ReferenceSet] = {}

        self._project_label = QLabel(self)
        self._project_combo = QComboBox(self)
        self._project_combo.currentIndexChanged.connect(self._refresh)
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

        #: In-project reference list — the resolve-state / shared-state indicators
        #: (REQ-P11-UI-021), over the *current* project's real reference set.
        self._project_refs_label = QLabel(self)
        self._project_tree = QTreeWidget(self)
        self._project_tree.setColumnCount(4)
        self._project_tree.setRootIsDecorated(False)
        self._project_tree.setUniformRowHeights(True)
        self._project_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._missing_label = QLabel(self)
        self._missing_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(project_row)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._status_label)
        layout.addLayout(button_row)
        layout.addWidget(self._project_refs_label)
        layout.addWidget(self._project_tree, 1)
        layout.addWidget(self._missing_label)

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
        """Create a **genuinely empty** reference set for ``name``.

        No-op if ``name`` already exists. An empty
        :class:`~pixelart_creator.logic.asset_references.ReferenceSet` is a correct
        durable state for a project that references nothing yet — not a
        placeholder standing in for real data.
        """
        name = name.strip()
        if not name or name in self._projects:
            return
        self._projects[name] = ReferenceSet()
        self._project_combo.addItem(name)
        self._project_combo.setCurrentText(name)
        self._refresh()

    def set_project_reference_set(
        self, project: str, reference_set: ReferenceSet
    ) -> None:
        """Bind ``project``'s **real, durable** reference set (REQ-P11-UI-021).

        The caller (typically the main window, after
        ``project_io.load_project_with_asset_refs``) supplies the reference set it
        loaded from the project's own file here. This — not a predicate computed over
        scratch state — is the panel's source of truth for the resolve-state and
        shared-state indicators.
        """
        project = project.strip()
        if not project:
            return
        if not isinstance(reference_set, ReferenceSet):
            raise TypeError(f"expected a ReferenceSet, got {reference_set!r}")
        is_new = project not in self._projects
        self._projects[project] = reference_set
        if is_new:
            self._project_combo.addItem(project)
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
        reference = AssetReference(
            asset_id=descriptor.asset_id,
            content_hash=descriptor.content_hash,
            kind=descriptor.kind,
            last_known_name=descriptor.name,
        )
        try:
            self._projects[project] = self._projects[project].add(reference)
        except AssetReferenceError:
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
        """Return how many open projects reference ``asset_id`` (``> 1`` iff shared)."""
        return sum(
            1
            for reference_set in self._projects.values()
            if asset_id in reference_set.asset_ids()
        )

    def is_shared(self, asset_id: str) -> bool:
        """Return whether ``asset_id`` is referenced by more than one **open** project.

        Delegates to :func:`~pixelart_creator.logic.asset_references.shared_ids` — the
        panel computes no predicate of its own. The honesty bound is the model's:
        ``False`` here is not a claim that no project anywhere else references the
        asset, only that no other currently open project's set does.
        """
        return asset_id in shared_ids(self._projects)

    def missing_asset_ids(self, project: str) -> FrozenSet[str]:
        """Return ``project``'s unresolvable reference ``asset_id`` s (REQ-P11-UI-021).

        Delegates to :func:`~pixelart_creator.logic.asset_references.missing` against
        the bound session's local catalog.
        """
        reference_set = self._projects.get(project)
        if reference_set is None or self._session is None:
            return frozenset()
        return missing(reference_set, self._session.catalog())

    def project_references(self, project: str) -> Tuple[str, ...]:
        """Return the ``asset_id`` s referenced by ``project`` (deterministic order)."""
        reference_set = self._projects.get(project)
        if reference_set is None:
            return ()
        return tuple(reference.asset_id for reference in reference_set.entries())

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        """Repopulate both trees and their indicators (REQ-P11-UI-007, -UI-021)."""
        self._refresh_shared_tree()
        self._refresh_project_tree()
        self._update_enabled()

    def _refresh_shared_tree(self) -> None:
        """Repopulate the shared-asset list + its shared / reference-count markers."""
        selected = self.current_asset_id()
        self._tree.clear()
        if self._session is None:
            return
        shared = shared_ids(self._projects)
        restored: Optional[QTreeWidgetItem] = None
        for descriptor in self._session.catalog().entries():
            count = self.reference_count(descriptor.asset_id)
            shared_text = self.tr("Shared") if descriptor.asset_id in shared else ""
            item = QTreeWidgetItem(
                [
                    descriptor.name,
                    self._kind_text(descriptor.kind),
                    shared_text,
                    str(count),
                ]
            )
            item.setData(_COL_NAME, _ROLE_ASSET, descriptor.asset_id)
            if shared_text:
                item.setToolTip(
                    _COL_SHARED, self.tr("Referenced by another open project")
                )
            self._tree.addTopLevelItem(item)
            if descriptor.asset_id == selected:
                restored = item
        if restored is not None:
            self._tree.setCurrentItem(restored)

    def _refresh_project_tree(self) -> None:
        """Show the current project's own references and their resolve / shared state.

        This is the panel's new indicator surface (REQ-P11-UI-021), computed over
        the real, durable :class:`~pixelart_creator.logic.asset_references.ReferenceSet`
        in :attr:`_projects`, never over a widget-local rule.
        """
        self._project_tree.clear()
        project = self.current_project()
        reference_set = self._projects.get(project)
        if self._session is None or reference_set is None:
            self._missing_label.setText("")
            return
        local_catalog = self._session.catalog()
        resolved = resolve_states(reference_set, local_catalog)
        unresolved = missing(reference_set, local_catalog)
        # DEV-41: reference_states refines resolve_states' boolean into three states —
        # a STATE_EDITED reference is present under a changed content_hash, and reads
        # here the same as a STATE_RESOLVED one (REQ-P11-UI-021). missing()'s call and
        # meaning, and the unresolved count label below, are untouched by this.
        states = reference_states(reference_set, local_catalog)
        shared = shared_ids(self._projects)
        for reference in reference_set.entries():
            is_resolved = resolved.get(reference.asset_id, False)
            shows_resolved = states.get(reference.asset_id) in (
                STATE_RESOLVED,
                STATE_EDITED,
            )
            entry = local_catalog.get(reference.asset_id)
            # Resolution is by identity + content, never by name — so a rename in the
            # library breaks no reference; when resolved (or edited-but-present) we
            # show the current name, falling back to the last-known (display-only)
            # name only when genuinely missing from the local library.
            display_name = (
                entry.name
                if (shows_resolved and entry is not None)
                else reference.last_known_name
            )
            resolve_text = (
                self.tr("In library")
                if shows_resolved
                else self.tr("Not found in library")
            )
            shared_text = self.tr("Shared") if reference.asset_id in shared else ""
            item = QTreeWidgetItem(
                [
                    display_name,
                    self._kind_text(reference.kind),
                    resolve_text,
                    shared_text,
                ]
            )
            item.setData(_PCOL_NAME, _ROLE_ASSET, reference.asset_id)
            if not is_resolved:
                item.setToolTip(
                    _PCOL_RESOLVE,
                    self.tr("This reference could not be found in the local library."),
                )
            if shared_text:
                item.setToolTip(
                    _PCOL_SHARED, self.tr("Referenced by another open project")
                )
            self._project_tree.addTopLevelItem(item)
        if unresolved:
            self._missing_label.setText(
                self.tr("%1 unresolved reference(s) in this project.").replace(
                    "%1", str(len(unresolved))
                )
            )
        else:
            self._missing_label.setText(
                self.tr("All references resolve in the local library.")
            )

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
        self._project_refs_label.setText(self.tr("References in this project:"))
        self._project_tree.setHeaderLabels(
            [
                self.tr("Name"),
                self.tr("Kind"),
                self.tr("Resolve state"),
                self.tr("Shared"),
            ]
        )
        self._project_tree.setAccessibleName(
            self.tr("References in the current project")
        )
        self._missing_label.setAccessibleName(self.tr("Missing reference count"))
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the reuse-panel strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
