"""Dependency-graph view + passive break surface (REQ-P11-UI-005 / -006).

``Dependency_Graph_View`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget`
that **visualises** the asset dependency graph — the depends-on (``dependencies_of``)
and referenced-by (``dependents_of``) relations — for either the whole catalog or the
single asset the library selection points at (REQ-P11-UI-005). It holds **no** domain
logic (Article I / S11): the relations it draws are exactly the result of the pure,
deterministic queries on
:class:`~pixelart_creator.logic.dependency_graph.DependencyGraph`, and the break flags
it surfaces are exactly the result of the pure
:func:`~pixelart_creator.logic.break_detection.find_broken` reference-validation pass.

**Cycle-safe by construction (no hang).** A stored :class:`DependencyGraph` is *acyclic*
— the model rejects a cycle-inducing edge set at build time and *reports* the cycle
(``DependencyGraphError``) rather than looping. This view therefore never performs its
own recursive walk: it renders only the **direct** neighbours the model returns
(``dependencies_of`` / ``dependents_of`` — finite, sorted tuples), so no traversal loop
can exist in the widget and a cyclic edge set can never hang it. :meth:`show_edges`
consumes that guarantee: it asks the model to build the graph and, when the model
reports a cycle, it **displays the reported cycle passively** (a label — never a walk,
never a dialog) and keeps the last good graph.

**Passive break surface (REQ-P11-UI-006, CL-4).** The break indicator is *pull-based*:
it reflects ``find_broken`` over the current graph + catalog, refreshes on
``catalogChanged`` / ``graphChanged`` (triggered revalidation), and is shown as a
summary label plus per-edge status text. It raises **no** push notification / dialog —
an asset
with a broken reference shows the indicator; one with only valid references shows none.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role, so
both themes render correctly with no per-widget colour (REQ-P11-UI-009). All work is
synchronous over the in-memory graph/catalog — no worker thread / timer (the Slice-1
``Asset_Library_Session`` precedent: pure ``logic`` queries over immutable values are
microsecond-fast, so nothing is off-loaded and nothing needs teardown).
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetCatalog, AssetKind
from pixelart_creator.logic.break_detection import (
    REASON_HASH_MISMATCH,
    REASON_MISSING,
    BrokenReference,
    find_broken,
)
from pixelart_creator.logic.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphError,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session

_COL_ASSET = 0
_COL_STATUS = 1

#: Item roles: whether a row is a broken edge, and the edge it stands for.
_ROLE_BROKEN = Qt.ItemDataRole.UserRole
_ROLE_EDGE = Qt.ItemDataRole.UserRole + 1


class Dependency_Graph_View(QWidget):
    """Visualise depends-on / dependents and surface broken references passively."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the break-summary label, the cycle notice, and the relation tree."""
        super().__init__(parent)
        self._session: Optional[Asset_Library_Session] = None
        #: The asset in scope (``""`` = the whole catalog).
        self._asset_id: str = ""
        #: The last cycle the model reported at :meth:`show_edges` (``""`` = none).
        self._cycle_report: str = ""

        self._break_label = QLabel(self)
        self._break_label.setWordWrap(True)

        self._cycle_label = QLabel(self)
        self._cycle_label.setWordWrap(True)
        self._cycle_label.setVisible(False)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(2)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        layout = QVBoxLayout(self)
        layout.addWidget(self._break_label)
        layout.addWidget(self._cycle_label)
        layout.addWidget(self._tree, 1)

        self._retranslate()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Asset_Library_Session) -> None:
        """Bind to a :class:`Asset_Library_Session` and refresh on its changes."""
        self._session = session
        session.catalogChanged.connect(self._refresh)
        session.graphChanged.connect(self._refresh)
        self._refresh()

    def set_asset(self, asset_id: str) -> None:
        """Scope the view to ``asset_id`` (``""`` shows the whole catalog)."""
        self._asset_id = asset_id or ""
        self._refresh()

    def show_edges(self, edges: Sequence[DependencyEdge]) -> None:
        """Build a graph from ``edges`` and display it; a cycle is reported passively.

        Delegates cycle detection to the model: on success the session graph is
        replaced (``graphChanged`` triggers the refresh); on a reported cycle the
        :class:`DependencyGraphError` message is surfaced in the passive cycle label
        and the last good graph is kept — the view never walks the edges itself, so a
        cyclic edge set can never hang it (REQ-P11-UI-005 acceptance).

        Args:
            edges: The dependency edges to build the graph from.
        """
        try:
            graph = DependencyGraph(edges=tuple(edges))
        except DependencyGraphError as exc:
            self._cycle_report = str(exc)
            self._refresh()
            return
        self._cycle_report = ""
        if self._session is not None:
            self._session.set_graph(graph)
        else:
            self._refresh()

    # -- read-only helpers (test / caller seams) --------------------------

    def scope_asset_id(self) -> str:
        """Return the asset currently in scope (``""`` = whole catalog)."""
        return self._asset_id

    def broken_references(self) -> Tuple[BrokenReference, ...]:
        """Return the whole-graph broken references from the validation pass."""
        if self._session is None:
            return ()
        return find_broken(self._session.graph(), self._session.catalog())

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        """Repopulate the tree + break surface from the current graph/catalog."""
        self._tree.clear()
        self._cycle_label.setVisible(bool(self._cycle_report))
        if self._cycle_report:
            self._cycle_label.setText(
                self.tr("Dependency cycle detected (graph unchanged): %1").replace(
                    "%1", self._cycle_report
                )
            )
        if self._session is None:
            self._update_break_summary(())
            return

        graph = self._session.graph()
        catalog = self._session.catalog()
        broken = find_broken(graph, catalog)
        broken_by_edge: Dict[Tuple[str, str], str] = {
            (ref.source_id, ref.target_id): ref.reason for ref in broken
        }

        scope_nodes = (self._asset_id,) if self._asset_id else graph.nodes()
        for node in scope_nodes:
            self._tree.addTopLevelItem(
                self._make_node_item(node, graph, catalog, broken_by_edge)
            )
        self._tree.expandAll()
        self._update_break_summary(self._scope_broken(broken))

    def _make_node_item(
        self,
        node: str,
        graph: DependencyGraph,
        catalog: AssetCatalog,
        broken_by_edge: Dict[Tuple[str, str], str],
    ) -> QTreeWidgetItem:
        """Build the ``node`` row with its Dependencies / Dependents child groups."""
        item = QTreeWidgetItem([self._label(node, catalog), ""])
        deps_group = QTreeWidgetItem([self.tr("Dependencies (depends on)"), ""])
        for target in graph.dependencies_of(node):
            # A dependency edge node -> target; the neighbour shown is the target.
            deps_group.addChild(
                self._make_edge_item(node, target, target, catalog, broken_by_edge)
            )
        dependents_group = QTreeWidgetItem([self.tr("Dependents (referenced by)"), ""])
        for source in graph.dependents_of(node):
            # A dependent edge source -> node; the neighbour shown is the source.
            dependents_group.addChild(
                self._make_edge_item(source, node, source, catalog, broken_by_edge)
            )
        item.addChild(deps_group)
        item.addChild(dependents_group)
        return item

    def _make_edge_item(
        self,
        source: str,
        target: str,
        neighbour: str,
        catalog: AssetCatalog,
        broken_by_edge: Dict[Tuple[str, str], str],
    ) -> QTreeWidgetItem:
        """Build one neighbour row, marked passively when its edge is broken.

        The row labels ``neighbour`` (the endpoint that is not the owning node) and,
        when the edge ``(source, target)`` is flagged by the validation pass, shows a
        translatable break status + tooltip (passive; no dialog).
        """
        edge_key = (source, target)
        reason = broken_by_edge.get(edge_key)
        child = QTreeWidgetItem([self._label(neighbour, catalog), ""])
        child.setData(_COL_ASSET, _ROLE_EDGE, edge_key)
        child.setData(_COL_ASSET, _ROLE_BROKEN, reason is not None)
        if reason is not None:
            status = self.tr("Broken (%1)").replace("%1", self._reason_text(reason))
            child.setText(_COL_STATUS, status)
            child.setToolTip(_COL_STATUS, status)
            child.setToolTip(_COL_ASSET, status)
        return child

    def _scope_broken(
        self, broken: Tuple[BrokenReference, ...]
    ) -> Tuple[BrokenReference, ...]:
        """Filter ``broken`` to the current scope (all when the whole catalog)."""
        if not self._asset_id:
            return broken
        return tuple(
            ref for ref in broken if self._asset_id in (ref.source_id, ref.target_id)
        )

    # -- i18n / labels ----------------------------------------------------

    def _label(self, asset_id: str, catalog: AssetCatalog) -> str:
        """Return a display label for ``asset_id`` (name + kind, else the raw id)."""
        descriptor = catalog.get(asset_id)
        if descriptor is None:
            return asset_id
        return (
            self.tr("%1 (%2)")
            .replace("%1", descriptor.name)
            .replace("%2", self._kind_text(descriptor.kind))
        )

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

    def _reason_text(self, reason: str) -> str:
        """Return the translated wording for a break reason."""
        if reason == REASON_MISSING:
            return self.tr("missing target")
        if reason == REASON_HASH_MISMATCH:
            return self.tr("changed target")
        return reason

    def _update_break_summary(self, broken: Tuple[BrokenReference, ...]) -> None:
        """Set the passive break-summary label from the in-scope broken references."""
        count = len(broken)
        if count == 0:
            self._break_label.setText(self.tr("No broken references"))
        else:
            self._break_label.setText(
                self.tr("Broken references: %1").replace("%1", str(count))
            )
        self._break_label.setAccessibleName(self.tr("Broken reference summary"))

    def _retranslate(self) -> None:
        """(Re)apply every user-visible string (F5)."""
        self.setAccessibleName(self.tr("Dependency graph"))
        self._tree.setHeaderLabels([self.tr("Asset"), self.tr("Status")])
        self._tree.setAccessibleName(self.tr("Dependency relations"))
        self._cycle_label.setAccessibleName(self.tr("Dependency cycle notice"))
        self._refresh()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the dependency-view strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
