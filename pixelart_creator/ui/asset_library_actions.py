# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Asset-library session — the shared in-memory catalog the panels bind to (Phase 11).

``Asset_Library_Session`` is a presentation-only :class:`~PySide6.QtCore.QObject`
that holds the **current in-memory** :class:`~pixelart_creator.logic.asset_catalog.
AssetCatalog` for the Slice-1 library surfaces (browse / tag / search — REQ-P11-UI-001/
-002/-003) and owns the **shared undo stack** the tag :class:`QUndoCommand`s push onto
(REQ-P11-UI-002). It performs **no domain logic** of its own (Article I / S11): every
mutation delegates to the Qt-free ``logic``/``data`` layer — the immutable
:class:`AssetCatalog` builders and the ``logic/asset_tags`` do/undo pairs bridged by
``ui/commands.py``. The session is the single source of the catalog so all three panels
stay in sync: any change emits :data:`~Asset_Library_Session.catalogChanged`, on which
each panel re-reads and repaints.

Slice-1 library ops (enumerate, filter, tag, add / remove an entry) are pure in-memory
operations over the immutable catalog value — microsecond-fast even at
``MAX_CATALOG_ASSETS`` — so they run **synchronously on the GUI thread with no worker
thread, timer, or poller** (the Phase-10 Slice-B ``Shared_Projects_Panel`` precedent).
The session therefore owns **nothing to tear down** beyond ordinary Qt parent ownership
(no ``shutdown_*`` is needed; the recurring cross-thread GC-of-Qt-C++ segfault cannot
arise here — there is no off-GUI-thread object). Catalog durability
(``REQ-P11-DATA-008``) is wired through the shipped
``data/asset_catalog_io`` functions:
:meth:`bind_root` loads whatever catalog persists at an already-resolved root (an
absent index reads as an empty catalog, not an error), and every mutation thereafter
is saved straight back to that same root. The session **resolves no root and names no
storage backend itself** — the caller (``ui/main_window.py``) supplies the
already-injected root, and a session that is never bound behaves exactly as before:
purely in-memory, touching the filesystem not at all.

Only **tag add / remove** is undoable (PL11-D3); adding or removing a whole catalog
entry is library/session state and pushes **no** ``QUndoCommand``.

This module adds the shared, immutable
:class:`~pixelart_creator.logic.dependency_graph.DependencyGraph` (asset→asset
references) alongside the catalog so the dependency-graph view and the passive
break surface read one source of truth: :meth:`set_graph` swaps the graph and emits
:data:`graphChanged`; the graph is a pure ``logic`` value (cycle-rejecting, acyclic by
construction), so — like the catalog — the session runs **synchronously on the GUI
thread with no worker / timer** and has nothing to tear down.

**The three in-app registration actions (REQ-P11-UI-012/-013/-014/
-017/-020).** :meth:`register_active_document`, :meth:`register_selection` and
:meth:`register_export_artifact` are the **only** production entry points into
:func:`~pixelart_creator.data.asset_ingress.register` — one shared registration
prompt (:class:`~pixelart_creator.ui.asset_register_dialog.Asset_Register_Dialog`)
and one shared ingress path, exactly as the task requires. Each is presentation
orchestration only (S11): the dialog collects display data, ``data/asset_ingress``
decides whether a registration is valid, and this session never computes a hash, a
descriptor or a dependency edge itself. Every outcome is reported — never silent
(REQ-P11-UI-017) — through :data:`registrationSucceeded` / :data:`registrationFailed`
/ :data:`registrationCancelled`, and, when a widget ``parent`` is supplied, an
additional :class:`~PySide6.QtWidgets.QMessageBox` surfaces a failure using the same
title/idiom :class:`~pixelart_creator.ui.asset_version_browser.Asset_Version_Browser`
already uses for :class:`~pixelart_creator.data.asset_revision_store.
AssetRevisionStoreError`. A single exception type, :class:`~pixelart_creator.data.
asset_ingress.IngressError`, is the one thing this file catches — every precondition
this file itself enforces (an unbound content/revision store, an unknown
``existing_asset_id``) is raised as that same type rather than a second one, so a
caller has exactly one type to catch, matching that type's own documented intent.

**Revision recording (plan §0's discharged confirmation that registration owes the
first record).** A first-time registration mints a fresh ``asset_id`` (via ``register``)
and this session immediately records it as the asset's **first** revision through the
already-wired :class:`~pixelart_creator.data.asset_revision_store.AssetRevisionStore`
— the store was wired for *re*-record only (the restore path in
``Asset_Version_Browser``); nothing recorded revision #1 before this task.
**Re-registering** (``existing_asset_id`` supplied and present in the catalog) does
**not** call ``register`` again — ``register`` only ever mints a *new* entry, and a
second one would duplicate the asset rather than version it. Instead this session
records the new bytes against the **same** ``asset_id`` via
:meth:`~pixelart_creator.data.asset_revision_store.AssetRevisionStore.record`, whose
own content-hash dedup makes *"registering unchanged content appends nothing"*
(REQ-P11-UI-020) automatic rather than a check this file performs itself, and — only
when the content actually changed — swaps in the updated descriptor via the existing
:meth:`replace_descriptor` hook (the same apply hook the tag do/undo pair and the
version browser's restore already use), so ``catalogChanged`` fires exactly as it does
for any other mutation. Restoring an earlier revision remains
:class:`~pixelart_creator.ui.asset_version_browser.Asset_Version_Browser`'s existing,
unmodified job — this file only ensures the history it restores *from* is no longer
always empty.

**Dependency-edge derivation (REQ-P11-LOGIC-010, REQ-P11-UI-018,
ruling P11-R6, amended by ruling P11-R8).** Every successful registration
(first-time or re-registration) is followed, post-commit, by deriving the
newly registered descriptor's direct dependency edges and emitting
:data:`edgesDerived` with the **accumulated** edge set (this session's
current graph plus the newly derived edges). This session computes no edge
itself: :func:`~pixelart_creator.logic.asset_edges.candidate_keys`
(``logic/``) names which sub-objects of the registered document are
reference candidates **and** canonicalises each into its content-only
``reference_key`` bytes in one call — not the whole-project canonical bytes
``register`` stores, which bake in presentation state (layer names) that no
running-application document shape ever matches (ruling P11-R8) — and
:func:`~pixelart_creator.logic.asset_edges.edges_for` (``logic/``) matches
those reference keys into the catalog. This session never calls
:meth:`set_graph` and never imports
:class:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View` —
``ui/main_window.py`` connects :data:`edgesDerived` to
:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View.
show_edges`, which alone decides whether the accumulated set is accepted or
passively rejected as cyclic (the prior graph kept).

:meth:`bind_content_store` and :meth:`bind_revision_store` bind the
:class:`~pixelart_creator.data.asset_cas.ContentAddressableStore` and
:class:`~pixelart_creator.data.asset_revision_store.AssetRevisionStore` the
registration actions write through, on the same carried-in terms as
:meth:`bind_root`: **taken as given, never re-resolved, no backend named here**.
Until both are bound (alongside :meth:`bind_root`), every registration action reports
a plain, translatable "not ready yet" failure rather than raising past this file or
touching the catalog/store.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple, Union

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import (
    INDEX_FILENAME,
    load_catalog,
    save_catalog,
)
from pixelart_creator.data.asset_export import (
    BUNDLE_SUFFIX,
    AssetExportError,
    export_project_bundle,
    import_project_bundle,
)
from pixelart_creator.data.asset_ingress import (
    ARTIFACT_SUFFIX,
    IngressError,
    canonical_bytes,
    export_subset,
    import_artifact,
)
from pixelart_creator.data.asset_ingress import register as ingress_register
from pixelart_creator.data.asset_revision_store import (
    AssetRevisionStore,
    AssetRevisionStoreError,
)
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_edges import candidate_keys, edges_for
from pixelart_creator.logic.dependency_graph import DependencyGraph
from pixelart_creator.logic.document import Document
from pixelart_creator.ui.asset_register_dialog import Asset_Register_Dialog


@dataclass(frozen=True)
class RegistrationOutcome:
    """The result of one successful registration action (REQ-P11-UI-017/-020).

    Attributes:
        asset_id: The asset's stable id — freshly minted on a first
            registration, or the caller-supplied ``existing_asset_id`` on a
            re-registration.
        already_present: ``True`` when the registered content's bytes were
            already stored: the CAS dedup observation (``register``'s own
            ``already_present``) on a first registration, or the revision
            store's content-hash dedup — *"registering unchanged content
            appends nothing"* (REQ-P11-UI-020) — on a re-registration.
        revision_recorded: ``True`` when this action appended a new revision
            to the asset's history. Always ``True`` on a first registration
            (the revision #1 this task owes); ``True`` on a re-registration
            only when the content actually changed.
    """

    asset_id: str
    already_present: bool
    revision_recorded: bool


class Asset_Library_Session(QObject):
    """Hold the shared catalog + undo stack for the library panels.

    In-memory until :meth:`bind_root` is called; bound, it is durable.

    Args:
        parent: Optional Qt parent (typically the main window).
        catalog: The initial catalog; an empty catalog when omitted.
    """

    #: Emitted after any change to the catalog (add / remove / tag do-undo) so the
    #: bound panels re-read and repaint. No payload — panels pull the fresh catalog.
    catalogChanged = Signal()

    #: Emitted after the dependency graph is replaced so the dependency-graph
    #: view and the passive break surface re-read and repaint. No payload.
    graphChanged = Signal()

    #: Emitted after a registration action commits — carries the
    #: :class:`RegistrationOutcome` (REQ-P11-UI-017).
    registrationSucceeded = Signal(object)

    #: Emitted when a registration action cannot commit — carries a
    #: translatable message; the catalog, store and revision history are all
    #: left unchanged (REQ-P11-UI-017).
    registrationFailed = Signal(str)

    #: Emitted when the user cancels the registration prompt — cancelling is
    #: not a failure (REQ-P11-UI-017; RP-4).
    registrationCancelled = Signal()

    #: Emitted after a successful registration's derived dependency edges are
    #: computed (ruling P11-R6, REQ-P11-LOGIC-010 / REQ-P11-UI-018) —
    #: carries the **accumulated** edge set (this session's current graph
    #: edges plus the newly derived ones), because the bound consumer
    #: (:meth:`~pixelart_creator.ui.dependency_graph_view.Dependency_Graph_View.
    #: show_edges`) *replaces* the graph it is handed rather than merging into
    #: it. This session never calls :meth:`set_graph` itself and never imports
    #: the view — ``show_edges`` alone decides whether the accumulated set is
    #: accepted (and, on a closed cycle, rejected passively, the prior graph
    #: kept) — see ``main_window.py``'s connection of this signal.
    edgesDerived = Signal(object)

    #: Emitted after a single library artifact (``.pixasset``) is imported and
    #: merged + committed into the already-open library (ruling P11-R5,
    #: REQ-P11-UI-015/-016) — carries the imported ``Tuple[AssetDescriptor, ...]``.
    libraryImportSucceeded = Signal(object)

    #: Emitted when a library-artifact import cannot commit — a translatable
    #: message; the catalog and store are unchanged.
    libraryImportFailed = Signal(str)

    #: Emitted when the user cancels the "Import asset artifact" file dialog.
    libraryImportCancelled = Signal()

    #: Emitted after a chosen catalog subset is written to a library artifact
    #: file (REQ-P11-UI-016) — carries the destination path as ``str``.
    libraryExportSucceeded = Signal(str)

    #: Emitted when a library-subset export cannot complete — a translatable
    #: message; no file is written.
    libraryExportFailed = Signal(str)

    #: Emitted when the user cancels the "Export asset artifact" file dialog.
    libraryExportCancelled = Signal()

    #: Emitted after a project + its whole reference set is written to a
    #: ``.pixbundle`` file (the shipped
    #: :func:`~pixelart_creator.data.asset_export.export_project_bundle`,
    #: unchanged) — carries the destination path as ``str``.
    projectBundleExportSucceeded = Signal(str)

    #: Emitted when a project-bundle export cannot complete — a translatable
    #: message; no file is written.
    projectBundleExportFailed = Signal(str)

    #: Emitted when the user cancels the "Export project bundle" file dialog.
    projectBundleExportCancelled = Signal()

    #: Emitted after a ``.pixbundle`` is reconstructed into a new project
    #: directory (the shipped
    #: :func:`~pixelart_creator.data.asset_export.import_project_bundle`,
    #: unchanged) — carries the ``(Document, AssetCatalog)`` tuple. This
    #: session's own catalog is untouched: the bundle reconstructs a
    #: **new** project, never merging into the open library (plan Section 3.7).
    projectBundleImported = Signal(object)

    #: Emitted when a project-bundle import cannot complete — a translatable
    #: message; ``target_dir`` is left exactly as it was (the shipped
    #: function's own atomic-move guarantee).
    projectBundleImportFailed = Signal(str)

    #: Emitted when the user cancels the "Import project bundle" file dialog.
    projectBundleImportCancelled = Signal()

    def __init__(
        self,
        parent: Optional[QObject] = None,
        catalog: Optional[AssetCatalog] = None,
        graph: Optional[DependencyGraph] = None,
    ) -> None:
        """Create the session over ``catalog`` / ``graph`` (empty defaults)."""
        super().__init__(parent)
        self._catalog: AssetCatalog = catalog if catalog is not None else AssetCatalog()
        self._graph: DependencyGraph = graph if graph is not None else DependencyGraph()
        #: The shared undo stack the tag commands push onto (REQ-P11-UI-002).
        self._undo_stack = QUndoStack(self)
        #: The durable catalog root once bound (REQ-P11-DATA-008); ``None`` until
        #: :meth:`bind_root` is called, so an unbound session stays purely in-memory.
        self._root: Optional[Path] = None
        #: The content-addressable store the registration actions write blobs
        #: through, once bound; ``None`` until :meth:`bind_content_store`.
        self._cas: Optional[ContentAddressableStore] = None
        #: The revision store the registration actions record through, once
        #: bound; ``None`` until :meth:`bind_revision_store`.
        self._revision_store: Optional[AssetRevisionStore] = None

    # -- queries ----------------------------------------------------------

    def catalog(self) -> AssetCatalog:
        """Return the current in-memory, immutable catalog value."""
        return self._catalog

    def graph(self) -> DependencyGraph:
        """Return the current in-memory, immutable dependency graph value."""
        return self._graph

    def undo_stack(self) -> QUndoStack:
        """Return the shared undo stack the tag commands are pushed onto."""
        return self._undo_stack

    # -- catalog durability (REQ-P11-DATA-008) ------------------------------

    def bind_root(self, root: Union[str, Path]) -> None:
        """Bind the durable catalog root and adopt whatever catalog persists there.

        Loads the catalog under ``root`` via the shipped
        :func:`~pixelart_creator.data.asset_catalog_io.load_catalog` and notifies the
        panels; from this call on, every mutation (:meth:`set_catalog`,
        :meth:`add_descriptor`, :meth:`remove_asset`, :meth:`replace_descriptor`) is
        saved straight back to the same root via
        :func:`~pixelart_creator.data.asset_catalog_io.save_catalog`.

        ``root`` must already be resolved by the caller (``ui/main_window.py``'s
        injected asset root) — this method neither re-resolves a root nor names a
        storage backend (the carried-in placement ruling; plan §0). A root that has
        no catalog index yet reads as an **empty catalog, not an error** (this is
        what keeps "merely opening the application creates nothing on disk" true);
        any other load failure (a malformed or over-cap catalog) propagates as
        :class:`~pixelart_creator.data.asset_catalog_io.AssetCatalogError` for the
        caller to surface.

        Args:
            root: The already-resolved catalog root to load from and save to.
        """
        root_path = Path(root)
        if (root_path / INDEX_FILENAME).is_file():
            self._catalog = load_catalog(root_path)
        else:
            self._catalog = AssetCatalog()
        self._root = root_path
        self.catalogChanged.emit()

    def _persist(self) -> None:
        """Save the current catalog to the bound root, if any (no-op until bound)."""
        if self._root is not None:
            save_catalog(self._catalog, self._root)

    # -- registration wiring (REQ-P11-UI-012/-013/-014/-017/-020) -----------

    def bind_content_store(self, cas: ContentAddressableStore) -> None:
        """Bind the content-addressable store the registration actions write to.

        ``cas`` is taken as given, on the same terms as :meth:`bind_root`: this
        method neither constructs nor resolves a store, and names no backend
        (the carried-in placement ruling; plan §0). The caller
        (``ui/main_window.py``) supplies the already-constructed store.

        Args:
            cas: The content-addressable store to write registered blobs to.
        """
        self._cas = cas

    def bind_revision_store(self, store: AssetRevisionStore) -> None:
        """Bind the revision store the registration actions record through.

        ``store`` is taken as given, on the same terms as :meth:`bind_root`
        and :meth:`bind_content_store`. The caller supplies the
        already-constructed :class:`~pixelart_creator.data.
        asset_revision_store.AssetRevisionStore` (already shared with
        :class:`~pixelart_creator.ui.asset_version_browser.Asset_Version_Browser`
        so restore and registration record into the same history).

        Args:
            store: The revision store to record registrations through.
        """
        self._revision_store = store

    # -- catalog mutation (library state; no QUndoCommand) ----------------

    def set_catalog(self, catalog: AssetCatalog) -> None:
        """Replace the whole catalog (e.g. after a ``load_catalog``) and notify.

        Args:
            catalog: The catalog to adopt.

        Raises:
            TypeError: If ``catalog`` is not an :class:`AssetCatalog`.
        """
        if not isinstance(catalog, AssetCatalog):
            raise TypeError(f"expected an AssetCatalog, got {catalog!r}")
        self._catalog = catalog
        self.catalogChanged.emit()
        self._persist()

    def set_graph(self, graph: DependencyGraph) -> None:
        """Replace the whole dependency graph and notify (library state).

        The supplied graph is a pure ``logic`` value that is **acyclic by
        construction** (:class:`DependencyGraph` rejects a cycle-inducing edge set at
        build time), so no cycle can enter the UI here. No ``QUndoCommand`` is pushed —
        the dependency graph is library/session state, not an editing operation.

        Args:
            graph: The dependency graph to adopt.

        Raises:
            TypeError: If ``graph`` is not a :class:`DependencyGraph`.
        """
        if not isinstance(graph, DependencyGraph):
            raise TypeError(f"expected a DependencyGraph, got {graph!r}")
        self._graph = graph
        self.graphChanged.emit()

    def add_descriptor(self, descriptor: AssetDescriptor) -> None:
        """Add ``descriptor`` to the catalog and notify (library state, not undoable).

        Delegates to :meth:`AssetCatalog.add`, whose ``AssetCatalogModelError`` (a
        duplicate id or an over-cap catalog) propagates to the caller to surface.
        Saved to the bound root (if any) after the panels are notified.
        """
        self._catalog = self._catalog.add(descriptor)
        self.catalogChanged.emit()
        self._persist()

    def remove_asset(self, asset_id: str) -> None:
        """Remove the entry for ``asset_id`` and notify (library state, not undoable).

        Delegates to :meth:`AssetCatalog.remove`, whose ``AssetCatalogModelError``
        (unknown id) propagates to the caller to surface. Saved to the bound root (if
        any) after the panels are notified.
        """
        self._catalog = self._catalog.remove(asset_id)
        self.catalogChanged.emit()
        self._persist()

    # -- tag do/undo apply (invoked by the AddTag/RemoveTag QUndoCommand) --

    def replace_descriptor(self, descriptor: AssetDescriptor) -> None:
        """Swap the entry sharing ``descriptor``'s ``asset_id`` for ``descriptor``.

        The apply hook the tag :class:`QUndoCommand`s call on redo/undo: it removes
        the current entry for that ``asset_id`` and re-adds the supplied descriptor
        (the immutable catalog keeps its ``asset_id``-sorted order, so the entry keeps
        its position), then notifies the panels. No domain logic lives here — the new
        descriptor is produced by the pure ``logic/asset_tags`` do/undo pair. Saved to
        the bound root (if any) after the panels are notified, on redo *and* on undo —
        a tag undo is durable the same way a tag redo is.

        Args:
            descriptor: The descriptor (already tag-mutated by the logic op) to install.
        """
        self._catalog = self._catalog.remove(descriptor.asset_id).add(descriptor)
        self.catalogChanged.emit()
        self._persist()

    # -- import / export actions (ruling P11-R5, plan Section 3.7) ----------
    #
    # Two user commands, never one — they move two different units of
    # transfer (plan Section 3.7's scope correction): the LIBRARY
    # ARTIFACT path (a chosen set of library assets, the ``asset_ingress``
    # shared atomic order) and the PROJECT BUNDLE path (a project plus its
    # whole reference set, the shipped ``asset_export`` bundle functions used
    # AS THEY ARE, unchanged). Obligation (a): the four methods below never
    # share a menu entry or a dialog filter — each builds its filter from the
    # format-owning module's own suffix constant (obligation (b):
    # ``ARTIFACT_SUFFIX`` from ``data.asset_ingress``, ``BUNDLE_SUFFIX`` from
    # ``data.asset_export`` — never a literal here).

    def import_library_artifact(self, parent: Optional[QWidget] = None) -> None:
        """Import one library-artifact (``.pixasset``) file (REQ-P11-UI-015/-016).

        Opens a file-open dialog filtered by
        :data:`~pixelart_creator.data.asset_ingress.ARTIFACT_SUFFIX`, then
        imports the chosen file's bytes through the shared, untrusted-input
        ingress path (:func:`~pixelart_creator.data.asset_ingress.
        import_artifact`) — merged into the already-open catalog and
        committed once (the atomic order, plan Section 3.3). Import does
        **not** re-prompt for name/kind/tags (RP-5): the artifact carries its
        own descriptor per entry.

        Obligation (c): a file whose suffix is
        :data:`~pixelart_creator.data.asset_export.BUNDLE_SUFFIX` is never
        handed to ``import_artifact`` at all — its untrusted bytes are a zip
        archive, not UTF-8 JSON, so the shared path's own format-marker check
        (``asset_ingress.py``'s "not a pixassetartifact") would never even be
        reached; this method recognises the suffix mismatch itself and
        reports a translatable message pointing at
        :meth:`import_project_bundle_from_file` instead, rather than letting
        a decode failure surface as a bare parse error.

        Args:
            parent: The optional widget to parent the file dialog (and a
                failure message box) to.
        """
        try:
            root, cas = self._require_root_and_cas()
        except IngressError as exc:
            self._report_import_failure(exc, parent)
            return

        caption = self.tr("Import asset artifact")
        file_filter = self.tr("Asset artifact (*%1)").replace("%1", ARTIFACT_SUFFIX)
        path_str, _selected = QFileDialog.getOpenFileName(
            parent, caption, "", file_filter
        )
        if not path_str:
            self.libraryImportCancelled.emit()
            return

        path = Path(path_str)
        if path.suffix == BUNDLE_SUFFIX:
            message = self.tr(
                '"%1" is a project bundle, not a single asset. Use '
                '"Import project bundle..." instead.'
            ).replace("%1", path.name)
            self.libraryImportFailed.emit(message)
            if parent is not None:
                QMessageBox.warning(parent, self.tr("Import asset"), message)
            return

        try:
            artifact_bytes = path.read_bytes()
        except OSError as exc:
            self._report_import_failure(exc, parent)
            return

        try:
            new_catalog, descriptors = import_artifact(
                artifact_bytes, self._catalog, cas, root
            )
        except IngressError as exc:
            self._report_import_failure(exc, parent)
            return

        self._catalog = new_catalog
        self.catalogChanged.emit()
        self.libraryImportSucceeded.emit(descriptors)

    def export_library_subset(
        self,
        asset_ids: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Export ``asset_ids``' catalog entries as one library-artifact file.

        Opens a file-save dialog filtered by
        :data:`~pixelart_creator.data.asset_ingress.ARTIFACT_SUFFIX`, encodes
        the chosen subset through the shared ``asset_ingress`` path (its
        :func:`~pixelart_creator.data.asset_ingress.export_subset`, which
        returns bytes), and this method writes the file — matching the
        table in plan Section 3.7 ("this file writes the file").

        Args:
            asset_ids: The catalog entries to export.
            parent: The optional widget to parent the file dialog (and a
                failure message box) to.
        """
        try:
            cas = self._require_cas()
        except IngressError as exc:
            self._report_export_failure(exc, parent)
            return

        caption = self.tr("Export asset artifact")
        file_filter = self.tr("Asset artifact (*%1)").replace("%1", ARTIFACT_SUFFIX)
        path_str, _selected = QFileDialog.getSaveFileName(
            parent, caption, "", file_filter
        )
        if not path_str:
            self.libraryExportCancelled.emit()
            return

        out_path = Path(path_str)
        if out_path.suffix != ARTIFACT_SUFFIX:
            out_path = out_path.with_suffix(ARTIFACT_SUFFIX)

        try:
            artifact_bytes = export_subset(asset_ids, self._catalog, cas)
        except IngressError as exc:
            self._report_export_failure(exc, parent)
            return

        try:
            out_path.write_bytes(artifact_bytes)
        except OSError as exc:
            self._report_export_failure(exc, parent)
            return

        self.libraryExportSucceeded.emit(str(out_path))

    def export_project_bundle_to_file(
        self,
        document: Document,
        reference_ids: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Export ``document`` plus its whole reference set as one ``.pixbundle``.

        The PROJECT BUNDLE command (plan Section 3.7): opens a file-save
        dialog filtered by
        :data:`~pixelart_creator.data.asset_export.BUNDLE_SUFFIX`, then
        writes the bundle through the shipped
        :func:`~pixelart_creator.data.asset_export.export_project_bundle`
        **as it is, unchanged** — the data layer writes the file itself, in
        contrast with :meth:`export_library_subset`.

        Args:
            document: The project whose PIO-1 payload is embedded.
            reference_ids: The asset ids the project references.
            parent: The optional widget to parent the file dialog (and a
                failure message box) to.
        """
        try:
            cas = self._require_cas()
        except IngressError as exc:
            self._report_bundle_export_failure(exc, parent)
            return

        caption = self.tr("Export project bundle")
        file_filter = self.tr("Project bundle (*%1)").replace("%1", BUNDLE_SUFFIX)
        path_str, _selected = QFileDialog.getSaveFileName(
            parent, caption, "", file_filter
        )
        if not path_str:
            self.projectBundleExportCancelled.emit()
            return

        try:
            out_path = export_project_bundle(
                document, reference_ids, self._catalog, cas, Path(path_str)
            )
        except AssetExportError as exc:
            self._report_bundle_export_failure(exc, parent)
            return

        self.projectBundleExportSucceeded.emit(str(out_path))

    def import_project_bundle_from_file(
        self,
        target_dir: Union[str, Path],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Import a ``.pixbundle`` file, reconstructing its project into ``target_dir``.

        The PROJECT BUNDLE command's import half (plan Section 3.7): opens a
        file-open dialog filtered by
        :data:`~pixelart_creator.data.asset_export.BUNDLE_SUFFIX`, then
        reconstructs the project through the shipped
        :func:`~pixelart_creator.data.asset_export.import_project_bundle`
        **as it is, unchanged**. ``target_dir`` must not already exist — the
        shipped function's own precondition; this session neither chooses
        nor creates that directory, taking it as given from the caller, on
        the same terms :meth:`bind_root` takes its root. The reconstructed
        project lands in that **new** directory, never merged into this
        session's own open-library catalog (plan Section 3.7's "Import lands
        in" row).

        Args:
            target_dir: The not-yet-existing directory the bundle is
                reconstructed into.
            parent: The optional widget to parent the file dialog (and a
                failure message box) to.
        """
        try:
            cas = self._require_cas()
        except IngressError as exc:
            self._report_bundle_import_failure(exc, parent)
            return

        caption = self.tr("Import project bundle")
        file_filter = self.tr("Project bundle (*%1)").replace("%1", BUNDLE_SUFFIX)
        path_str, _selected = QFileDialog.getOpenFileName(
            parent, caption, "", file_filter
        )
        if not path_str:
            self.projectBundleImportCancelled.emit()
            return

        try:
            document, catalog = import_project_bundle(Path(path_str), cas, target_dir)
        except AssetExportError as exc:
            self._report_bundle_import_failure(exc, parent)
            return

        self.projectBundleImported.emit((document, catalog))

    def _require_root_and_cas(self) -> Tuple[Path, ContentAddressableStore]:
        """Return ``(root, cas)`` for a library-artifact import, else raise.

        Import needs only the durable root and the content store — never the
        revision store (which :meth:`_require_ingress_ready` also requires
        for the registration actions); an artifact's own descriptors
        carry no revision to record, so gating import on an unrelated
        binding would misreport why it cannot run.
        """
        if self._root is None:
            raise IngressError("the asset library is not bound to a durable root yet")
        if self._cas is None:
            raise IngressError("the asset library's content store is not bound yet")
        return self._root, self._cas

    def _require_cas(self) -> ContentAddressableStore:
        """Return the bound content store for an export action, else raise.

        Export (library-subset or project-bundle) reads from the content
        store and writes no catalog entry, so neither the durable root nor
        the revision store is required here.
        """
        if self._cas is None:
            raise IngressError("the asset library's content store is not bound yet")
        return self._cas

    def _report_import_failure(self, exc: Exception, parent: Optional[QWidget]) -> None:
        """Emit :data:`libraryImportFailed` and, with a ``parent``, a message box."""
        message = self.tr("Could not import the asset: %1").replace("%1", str(exc))
        self.libraryImportFailed.emit(message)
        if parent is not None:
            QMessageBox.warning(parent, self.tr("Import asset"), message)

    def _report_export_failure(self, exc: Exception, parent: Optional[QWidget]) -> None:
        """Emit :data:`libraryExportFailed` and, with a ``parent``, a message box."""
        message = self.tr("Could not export the asset: %1").replace("%1", str(exc))
        self.libraryExportFailed.emit(message)
        if parent is not None:
            QMessageBox.warning(parent, self.tr("Export asset"), message)

    def _report_bundle_export_failure(
        self, exc: Exception, parent: Optional[QWidget]
    ) -> None:
        """Emit :data:`projectBundleExportFailed` and, with a ``parent``, a box."""
        message = self.tr("Could not export the project bundle: %1").replace(
            "%1", str(exc)
        )
        self.projectBundleExportFailed.emit(message)
        if parent is not None:
            QMessageBox.warning(parent, self.tr("Export project bundle"), message)

    def _report_bundle_import_failure(
        self, exc: Exception, parent: Optional[QWidget]
    ) -> None:
        """Emit :data:`projectBundleImportFailed` and, with a ``parent``, a box."""
        message = self.tr("Could not import the project bundle: %1").replace(
            "%1", str(exc)
        )
        self.projectBundleImportFailed.emit(message)
        if parent is not None:
            QMessageBox.warning(parent, self.tr("Import project bundle"), message)

    # -- registration actions (REQ-P11-UI-012/-013/-014/-017/-020) ----------

    def register_active_document(
        self,
        document: Document,
        *,
        parent: Optional[QWidget] = None,
        existing_asset_id: Optional[str] = None,
    ) -> Optional[RegistrationOutcome]:
        """Register the document currently open in the editor (REQ-P11-UI-012).

        Opens the shared registration prompt
        (:class:`~pixelart_creator.ui.asset_register_dialog.Asset_Register_Dialog`);
        on acceptance registers ``document`` through the shared ingress
        path. When ``existing_asset_id`` names an entry already in the
        catalog, this is a **re-registration**: the prompt is prefilled from
        that entry and, on acceptance, changed content is recorded as a new
        revision of the **same** asset instead of adding a duplicate entry
        (REQ-P11-UI-020) — unchanged content records nothing.

        Args:
            document: The active document to register.
            parent: The optional widget to parent the prompt (and a failure
                message box) to.
            existing_asset_id: When re-registering, the asset_id of the
                catalog entry this document was previously registered as.

        Returns:
            The :class:`RegistrationOutcome` on success, or ``None`` on
            cancellation or failure. Additive: every earlier caller that
            ignores the return value keeps working, so this breaks nothing.
        """
        return self._register_via_prompt(
            document, parent=parent, existing_asset_id=existing_asset_id
        )

    def register_selection(
        self,
        document: Optional[Document],
        *,
        parent: Optional[QWidget] = None,
    ) -> Optional[RegistrationOutcome]:
        """Register the current selection's content as an asset (REQ-P11-UI-013).

        ``document`` is a document built from the current selection only —
        constructing it is the caller's concern, not this method's (matching
        :func:`~pixelart_creator.data.asset_ingress.register`'s own
        documented split). When there is **no active selection**,
        ``document`` is ``None``: the prompt never appears and the report is
        a plain "nothing to register", never an implicit whole-document
        registration and never a silent no-op.

        Args:
            document: The selection-only document to register, or ``None``
                when there is no active selection.
            parent: The optional widget to parent the prompt (and a failure
                message box) to.

        Returns:
            The :class:`RegistrationOutcome` on success, or ``None`` on "no
            selection", cancellation or failure.
        """
        if document is None:
            message = self.tr("There is no active selection to register.")
            self.registrationFailed.emit(message)
            return None
        return self._register_via_prompt(document, parent=parent)

    def register_export_artifact(
        self,
        document: Document,
        export_metadata: Mapping[str, object],
        *,
        parent: Optional[QWidget] = None,
    ) -> Optional[RegistrationOutcome]:
        """Register the just-exported document, opting in from the export flow.

        REQ-P11-UI-014: the export itself is the caller's already-completed,
        primary action — this method registers **the source document that was
        exported**, never the exported file's own bytes (no second payload
        format, parent REQ-P11-DATA-007), with ``export_metadata`` (the export
        settings **as used for that run**) recorded on the new entry. Calling
        this method at all *is* the opt-in — a caller that never calls it
        registers nothing, which is what keeps the export flow's default
        behaviour unchanged.

        Args:
            document: The exported document (the source, not the output
                file).
            export_metadata: The export settings used for this run, recorded
                as the entry's metadata (bounded by
                :data:`~pixelart_creator.logic.constants.MAX_METADATA_BYTES`,
                enforced by the shared ingress path).
            parent: The optional widget to parent the prompt (and a failure
                message box) to.

        Returns:
            The :class:`RegistrationOutcome` on success, or ``None`` on
            cancellation or failure.
        """
        return self._register_via_prompt(
            document, parent=parent, metadata=export_metadata
        )

    def _register_via_prompt(
        self,
        document: Document,
        *,
        parent: Optional[QWidget] = None,
        metadata: Optional[Mapping[str, object]] = None,
        existing_asset_id: Optional[str] = None,
    ) -> Optional[RegistrationOutcome]:
        """Run the one shared registration prompt + ingress path for one action.

        Shared by :meth:`register_active_document`, :meth:`register_selection`
        and :meth:`register_export_artifact` — the "one shared prompt,
        one shared ingress path" the task requires. No domain logic
        lives here: this method only orchestrates the dialog and the calls
        into ``data/asset_ingress`` and ``data/asset_revision_store``.

        Returns:
            The :class:`RegistrationOutcome` on success, or ``None`` on
            cancellation or failure — additive to the pre-existing
            signal-only reporting, which is unchanged.
        """
        try:
            root, cas, revision_store = self._require_ingress_ready()
        except IngressError as exc:
            self._report_failure(exc, parent)
            return None

        existing: Optional[AssetDescriptor] = None
        if existing_asset_id is not None:
            existing = self._catalog.get(existing_asset_id)
            if existing is None:
                self._report_failure(
                    IngressError(
                        f"asset {existing_asset_id!r} is no longer in the library"
                    ),
                    parent,
                )
                return None

        dialog = Asset_Register_Dialog(
            parent,
            suggested_name=existing.name if existing is not None else "",
            suggested_kind=existing.kind if existing is not None else AssetKind.SPRITE,
            suggested_tags=tuple(existing.tags) if existing is not None else (),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.registrationCancelled.emit()
            return None

        name = dialog.display_name()
        kind = dialog.kind()
        tags = tuple(dialog.tags())

        try:
            if existing is not None:
                outcome, registered = self._reregister(
                    existing,
                    document,
                    revision_store,
                    name=name,
                    kind=kind,
                    tags=tags,
                )
            else:
                outcome, registered = self._register_new(
                    document,
                    root,
                    cas,
                    revision_store,
                    name=name,
                    kind=kind,
                    tags=tags,
                    metadata=metadata,
                )
        except (IngressError, AssetRevisionStoreError, AssetCatalogModelError) as exc:
            self._report_failure(exc, parent)
            return None

        self.registrationSucceeded.emit(outcome)
        self._derive_and_emit_edges(document, registered)
        return outcome

    def _derive_and_emit_edges(
        self, document: Document, descriptor: AssetDescriptor
    ) -> None:
        """Derive ``descriptor``'s dependency edges and emit them, accumulated.

        The one-call recipe (ruling P11-R8, plan §3.10) the task
        prescribes, and **no rule of its own** — the per-kind reference rule
        and its content-only canonicalisation both live in
        :func:`~pixelart_creator.logic.asset_edges.candidate_keys`
        (``logic/``), which replaces the prior two-call pairing of
        ``candidates_of`` with the whole-project ``canonical_bytes``
        (``data/``): that pairing bakes in presentation state — a layer's
        display name — that no document shape the running application
        produces ever matches, so it derived no edge in production. The
        hash-match still lives in
        :func:`~pixelart_creator.logic.asset_edges.edges_for` (``logic/``),
        now matching on each catalog entry's ``reference_key`` instead of its
        ``content_hash``. This method neither serialises (it does not import
        ``logic.content_hash.canonical_json_bytes`` nor call
        ``data.project_io.serialize``) nor re-implements the per-kind rule
        inline — it only calls :func:`candidate_keys` and emits the result.

        The payload is **accumulated** —
        ``tuple(self.graph().edges) + derived`` — because the bound consumer
        (``Dependency_Graph_View.show_edges``) *replaces* the graph it is
        handed; emitting only ``derived`` would silently wipe every edge
        derived by an earlier registration (P11-R3). This session never
        calls :meth:`set_graph` and never imports the view: whether the
        accumulated set is accepted, or rejected as cyclic (the prior graph
        kept, unraised, with a passive cycle report), is entirely
        ``show_edges``'s decision on the receiving end.

        Args:
            document: The just-registered source document, exactly as passed
                to the registration action — the same object
                :func:`candidate_keys` extracts reference candidates from.
            descriptor: The descriptor now on record for the registered
                asset (freshly minted on a first registration, or the
                descriptor now on record after a re-registration).
        """
        content = candidate_keys(document, descriptor.kind)
        derived = edges_for(descriptor, content, self._catalog)
        self.edgesDerived.emit(tuple(self.graph().edges) + derived)

    def _register_new(
        self,
        document: Document,
        root: Path,
        cas: ContentAddressableStore,
        revision_store: AssetRevisionStore,
        *,
        name: str,
        kind: AssetKind,
        tags: Sequence[str],
        metadata: Optional[Mapping[str, object]],
    ) -> Tuple[RegistrationOutcome, AssetDescriptor]:
        """First-time registration: mint a new entry, then record revision #1.

        Adopts ``register``'s returned catalog directly — ``register`` has
        already committed it via ``save_catalog`` (its own atomic order, plan
        §3.3), so this does **not** call :meth:`_persist` a second time.

        Returns the outcome alongside the freshly minted descriptor, so the
        caller (:meth:`_register_via_prompt`) can derive that descriptor's
        dependency edges without re-reading it from the catalog.
        """
        new_catalog, descriptor, already_present = ingress_register(
            document,
            self._catalog,
            cas,
            root,
            name=name,
            kind=kind,
            tags=tags,
            metadata=metadata,
        )
        self._catalog = new_catalog
        self.catalogChanged.emit()

        blob = canonical_bytes(document)
        revision_store.record(descriptor.asset_id, blob, created_marker=0, author=None)

        return (
            RegistrationOutcome(
                asset_id=descriptor.asset_id,
                already_present=already_present,
                revision_recorded=True,
            ),
            descriptor,
        )

    def _reregister(
        self,
        existing: AssetDescriptor,
        document: Document,
        revision_store: AssetRevisionStore,
        *,
        name: str,
        kind: AssetKind,
        tags: Sequence[str],
    ) -> Tuple[RegistrationOutcome, AssetDescriptor]:
        """Re-registration: record a revision against the same asset_id.

        Never calls :func:`~pixelart_creator.data.asset_ingress.register` —
        that mints a fresh ``asset_id`` every time and would duplicate the
        entry rather than version it. ``AssetRevisionStore.record`` performs
        its own content-hash dedup against the current head, so "unchanged
        content records nothing" (REQ-P11-UI-020) is that store's existing
        behaviour, not a check this method makes. The catalog entry's
        ``content_hash`` (and the user's possibly-edited name/kind/tags) are
        swapped in via the shipped :meth:`replace_descriptor` apply hook —
        the same one the tag do/undo pair and the version browser's restore
        already use — only when a new revision actually resulted.

        Returns the outcome alongside the descriptor now on record for this
        ``asset_id`` (the updated one when a revision was recorded, else the
        unchanged ``existing``), so the caller (:meth:`_register_via_prompt`)
        can derive that descriptor's dependency edges.
        """
        blob = canonical_bytes(document)
        marker = self._next_revision_marker(revision_store, existing.asset_id)
        new_head = revision_store.record(
            existing.asset_id, blob, created_marker=marker, author=None
        )
        revision_recorded = new_head.content_hash != existing.content_hash

        descriptor = existing
        if revision_recorded:
            descriptor = replace(
                existing,
                name=name,
                kind=kind,
                tags=frozenset(tags),
                content_hash=new_head.content_hash,
            )
            self.replace_descriptor(descriptor)

        return (
            RegistrationOutcome(
                asset_id=existing.asset_id,
                already_present=not revision_recorded,
                revision_recorded=revision_recorded,
            ),
            descriptor,
        )

    def _require_ingress_ready(
        self,
    ) -> Tuple[Path, ContentAddressableStore, AssetRevisionStore]:
        """Return ``(root, cas, revision_store)``, else raise ``IngressError``.

        A registration action needs all three bindings
        (:meth:`bind_root`, :meth:`bind_content_store`,
        :meth:`bind_revision_store`); this is the one precondition check this
        file itself performs, reported through the same exception type the
        shared ingress path raises, so a caller has exactly one type to catch
        (matching :class:`~pixelart_creator.data.asset_ingress.IngressError`'s
        own documented intent).
        """
        if self._root is None:
            raise IngressError("the asset library is not bound to a durable root yet")
        if self._cas is None:
            raise IngressError("the asset library's content store is not bound yet")
        if self._revision_store is None:
            raise IngressError("the asset library's revision store is not bound yet")
        return self._root, self._cas, self._revision_store

    @staticmethod
    def _next_revision_marker(store: AssetRevisionStore, asset_id: str) -> int:
        """Return a monotonic ordering marker one past the largest recorded one.

        Presentation sequencing only (never a wall-clock read in the domain
        layer) — the same idiom
        :meth:`~pixelart_creator.ui.asset_version_browser.Asset_Version_Browser.
        _next_marker` already uses for the identical purpose.
        """
        markers = [r.created_marker for r in store.history(asset_id).revisions]
        return (max(markers) + 1) if markers else 0

    def _report_failure(
        self,
        exc: Exception,
        parent: Optional[QWidget],
    ) -> None:
        """Emit :data:`registrationFailed` and, with a ``parent``, a message box.

        The library, the store and the revision history are all unchanged by
        every failure path this file raises or catches (REQ-P11-UI-017) — no
        partial catalog mutation happens before this is reached, except the
        one documented, unavoidable seam: a first-time registration that
        commits successfully but whose *subsequent* revision-#1 recording
        then fails reports here too (``AssetRevisionStoreError``), because
        the two are not one atomic operation — the catalog write already
        happened. That distinction is not hidden: the message names what
        happened via ``str(exc)``, translated as this module's idiom.
        """
        message = self.tr("Could not register the asset: %1").replace("%1", str(exc))
        self.registrationFailed.emit(message)
        if parent is not None:
            QMessageBox.warning(parent, self.tr("Asset registration"), message)
