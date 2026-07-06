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
arise here — there is no off-GUI-thread object). Loading / persisting a catalog to disk
is a ``data/asset_catalog_io`` concern the caller drives and feeds in via
:meth:`set_catalog`; the session never touches the filesystem.

Only **tag add / remove** is undoable (PL11-D3); adding or removing a whole catalog
entry is library/session state and pushes **no** ``QUndoCommand``.

Slice 2 adds the shared, immutable
:class:`~pixelart_creator.logic.dependency_graph.DependencyGraph` (asset→asset
references) alongside the catalog so the dependency-graph view and the passive
break surface read one source of truth: :meth:`set_graph` swaps the graph and emits
:data:`graphChanged`; the graph is a pure ``logic`` value (cycle-rejecting, acyclic by
construction), so — like the catalog — the session runs **synchronously on the GUI
thread with no worker / timer** and has nothing to tear down.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.asset_catalog import AssetCatalog, AssetDescriptor
from pixelart_creator.logic.dependency_graph import DependencyGraph


class Asset_Library_Session(QObject):
    """Hold the shared in-memory catalog + undo stack for the library panels.

    Args:
        parent: Optional Qt parent (typically the main window).
        catalog: The initial catalog; an empty catalog when omitted.
    """

    #: Emitted after any change to the catalog (add / remove / tag do-undo) so the
    #: bound panels re-read and repaint. No payload — panels pull the fresh catalog.
    catalogChanged = Signal()

    #: Emitted after the dependency graph is replaced (Slice 2) so the dependency-graph
    #: view and the passive break surface re-read and repaint. No payload.
    graphChanged = Signal()

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

    # -- queries ----------------------------------------------------------

    def catalog(self) -> AssetCatalog:
        """Return the current in-memory, immutable catalog value."""
        return self._catalog

    def graph(self) -> DependencyGraph:
        """Return the current in-memory, immutable dependency graph value (Slice 2)."""
        return self._graph

    def undo_stack(self) -> QUndoStack:
        """Return the shared undo stack the tag commands are pushed onto."""
        return self._undo_stack

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

    def set_graph(self, graph: DependencyGraph) -> None:
        """Replace the whole dependency graph and notify (Slice 2, library state).

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
        """
        self._catalog = self._catalog.add(descriptor)
        self.catalogChanged.emit()

    def remove_asset(self, asset_id: str) -> None:
        """Remove the entry for ``asset_id`` and notify (library state, not undoable).

        Delegates to :meth:`AssetCatalog.remove`, whose ``AssetCatalogModelError``
        (unknown id) propagates to the caller to surface.
        """
        self._catalog = self._catalog.remove(asset_id)
        self.catalogChanged.emit()

    # -- tag do/undo apply (invoked by the AddTag/RemoveTag QUndoCommand) --

    def replace_descriptor(self, descriptor: AssetDescriptor) -> None:
        """Swap the entry sharing ``descriptor``'s ``asset_id`` for ``descriptor``.

        The apply hook the tag :class:`QUndoCommand`s call on redo/undo: it removes
        the current entry for that ``asset_id`` and re-adds the supplied descriptor
        (the immutable catalog keeps its ``asset_id``-sorted order, so the entry keeps
        its position), then notifies the panels. No domain logic lives here — the new
        descriptor is produced by the pure ``logic/asset_tags`` do/undo pair.

        Args:
            descriptor: The descriptor (already tag-mutated by the logic op) to install.
        """
        self._catalog = self._catalog.remove(descriptor.asset_id).add(descriptor)
        self.catalogChanged.emit()
