"""Pure, queryable asset-dependency graph — deterministic, zero Qt (S11).

Asset→asset references form a **directed acyclic graph** of stable
:class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor` ids
(REQ-P11-LOGIC-004; ADR-0031 §1/§2): a ``sprite`` is a frame *of* an ``animation``,
a ``sprite`` is the source image *of* a ``tileset``, a ``tileset`` is used *by* a
``tilemap``. Each reference is a :class:`DependencyEdge` from the **referencing** asset
(``source_id``) to the **referenced** asset (``target_id``), carrying the
``pinned_hash`` — the target's ``content_hash`` recorded when the reference was made
(the break-detection change-detector, :mod:`~pixelart_creator.logic.break_detection`).

:class:`DependencyGraph` is an **immutable, ordered** value (the
:class:`~pixelart_creator.logic.asset_catalog.AssetCatalog` idiom):
:meth:`~DependencyGraph.add_edge` returns a *new* graph and **rejects a cycle-inducing
edge** (raising :class:`DependencyGraphError`), so the stored graph is always acyclic.
It is **queryable** — :meth:`~DependencyGraph.dependencies_of` (what an asset
references) and :meth:`~DependencyGraph.dependents_of` (what references an asset) return
the **direct** neighbours or, with ``transitive=True``, the full reachable closure
(direct + transitive) in a **stable, deterministic** (``asset_id``-sorted) order.

Traversal is **cycle-safe** (a white/grey/black DFS detects and *reports* a cycle at
:meth:`~DependencyGraph.add_edge` time — never an infinite loop) and **depth-bounded**
by :data:`~pixelart_creator.logic.constants.MAX_DEPENDENCY_DEPTH` (a transitive walk
that would exceed it raises rather than spinning). Pure and deterministic: no Qt, no
wall-clock, no randomness, no locale-dependent ordering. This module reaches only
``constants`` — a downward leaf, no ``logic -> data`` edge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from pixelart_creator.logic.constants import MAX_DEPENDENCY_DEPTH

__all__ = [
    "DependencyGraphError",
    "DependencyEdge",
    "DependencyGraph",
]

#: DFS vertex colours for cycle detection (algorithm-intrinsic markers, ADR-0001 — a
#: white/grey/black tri-colour DFS, not a numeric tuning value for ``constants``).
_WHITE, _GREY, _BLACK = 0, 1, 2


class DependencyGraphError(ValueError):
    """Raised on a malformed edge, a conflicting pin, a cycle, or a depth overrun."""


@dataclass(frozen=True)
class DependencyEdge:
    """One directed asset reference: ``source_id`` references ``target_id``.

    Attributes:
        source_id: The **referencing** asset's stable id (a non-empty str).
        target_id: The **referenced** asset's stable id (a non-empty str). Must differ
            from ``source_id`` (a self-reference is a 1-cycle).
        pinned_hash: The target's ``content_hash`` recorded when the reference was made
            (a non-empty str; the break-detection change-detector). Deep hex validation
            is a ``data/`` concern (parity with ``AssetDescriptor.content_hash``).
    """

    source_id: str
    target_id: str
    pinned_hash: str

    def __post_init__(self) -> None:
        """Validate the two endpoints and the pinned hash are non-empty strings."""
        if not isinstance(self.source_id, str) or not self.source_id:
            raise DependencyGraphError(
                f"source_id must be a non-empty str, got {self.source_id!r}"
            )
        if not isinstance(self.target_id, str) or not self.target_id:
            raise DependencyGraphError(
                f"target_id must be a non-empty str, got {self.target_id!r}"
            )
        if not isinstance(self.pinned_hash, str) or not self.pinned_hash:
            raise DependencyGraphError(
                f"pinned_hash must be a non-empty str, got {self.pinned_hash!r}"
            )


def _detect_cycle(
    forward: Dict[str, Tuple[str, ...]], nodes: Tuple[str, ...]
) -> Optional[Tuple[str, ...]]:
    """Return a cycle path if the forward adjacency has one, else ``None``.

    A cycle-safe, iterative white/grey/black DFS (no recursion — the node set can be
    large): a ``_GREY`` neighbour is a back edge, i.e. a cycle. Deterministic: nodes and
    neighbours are visited in sorted order, so the *reported* cycle is stable.
    """
    colour: Dict[str, int] = {node: _WHITE for node in nodes}
    for start in nodes:
        if colour[start] != _WHITE:
            continue
        colour[start] = _GREY
        path: List[str] = [start]
        stack: List[Tuple[str, int]] = [(start, 0)]
        while stack:
            node, index = stack[-1]
            neighbours = forward.get(node, ())
            if index < len(neighbours):
                stack[-1] = (node, index + 1)
                nxt = neighbours[index]
                if colour[nxt] == _GREY:
                    return tuple(path[path.index(nxt) :] + [nxt])
                if colour[nxt] == _WHITE:
                    colour[nxt] = _GREY
                    path.append(nxt)
                    stack.append((nxt, 0))
            else:
                colour[node] = _BLACK
                stack.pop()
                path.pop()
    return None


@dataclass(frozen=True)
class DependencyGraph:
    """An immutable, acyclic, ordered set of :class:`DependencyEdge` s.

    Attributes:
        edges: The reference edges; unique per ``(source_id, target_id)`` pair,
            enumerated in a deterministic ``(source_id, target_id)``-sorted order so
            downstream passes are byte-identical across runs. The construction enforces
            acyclicity (a cyclic edge set raises :class:`DependencyGraphError`).
    """

    edges: Tuple[DependencyEdge, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate member types, collapse duplicates, reject cycles, normalise order.

        Raises:
            DependencyGraphError: If a member is not a :class:`DependencyEdge`, two
                edges share a ``(source_id, target_id)`` pair with a conflicting
                ``pinned_hash``, or the edge set contains a cycle.
        """
        by_key: Dict[Tuple[str, str], DependencyEdge] = {}
        for edge in self.edges:
            if not isinstance(edge, DependencyEdge):
                raise DependencyGraphError(f"expected a DependencyEdge, got {edge!r}")
            key = (edge.source_id, edge.target_id)
            existing = by_key.get(key)
            if existing is not None and existing.pinned_hash != edge.pinned_hash:
                raise DependencyGraphError(
                    f"conflicting pinned_hash for edge {key!r}: "
                    f"{existing.pinned_hash!r} vs {edge.pinned_hash!r}"
                )
            by_key[key] = edge
        ordered = tuple(by_key[key] for key in sorted(by_key))
        forward = _forward_adjacency(ordered)
        cycle = _detect_cycle(forward, _nodes(ordered))
        if cycle is not None:
            raise DependencyGraphError(
                "dependency cycle detected: " + " -> ".join(cycle)
            )
        object.__setattr__(self, "edges", ordered)

    def add_edge(self, edge: DependencyEdge) -> "DependencyGraph":
        """Return a **new** graph with ``edge`` added (pure); reject a cycle.

        Adding an edge identical to an existing one (same triple) is an idempotent
        no-op that returns an equivalent graph.

        Raises:
            DependencyGraphError: If ``edge`` is not a :class:`DependencyEdge`, an edge
                for the same ``(source_id, target_id)`` already exists with a different
                ``pinned_hash``, or adding ``edge`` would introduce a cycle.
        """
        if not isinstance(edge, DependencyEdge):
            raise DependencyGraphError(f"expected a DependencyEdge, got {edge!r}")
        for existing in self.edges:
            if (
                existing.source_id == edge.source_id
                and existing.target_id == edge.target_id
            ):
                if existing.pinned_hash == edge.pinned_hash:
                    return self
                raise DependencyGraphError(
                    f"edge ({edge.source_id!r} -> {edge.target_id!r}) already exists "
                    f"with a different pinned_hash"
                )
        return DependencyGraph(edges=self.edges + (edge,))

    def nodes(self) -> Tuple[str, ...]:
        """Return every id appearing as an edge endpoint, sorted (deterministic)."""
        return _nodes(self.edges)

    def dependencies_of(
        self, asset_id: str, *, transitive: bool = False
    ) -> Tuple[str, ...]:
        """Return the ids ``asset_id`` **references** (its dependencies), sorted.

        Args:
            asset_id: The asset whose dependencies to return (a non-empty str). An id
                with no outgoing edges (or absent from the graph) yields an empty tuple.
            transitive: When ``False`` (default) return only the **direct** targets;
                when ``True`` return the full reachable closure (direct + transitive).

        Returns:
            The dependency ids in a stable ``asset_id``-sorted order.

        Raises:
            DependencyGraphError: If ``asset_id`` is not a non-empty str, or (when
                ``transitive``) the walk exceeds :data:`MAX_DEPENDENCY_DEPTH`.
        """
        return self._query(asset_id, _forward_adjacency(self.edges), transitive)

    def dependents_of(
        self, asset_id: str, *, transitive: bool = False
    ) -> Tuple[str, ...]:
        """Return the ids that **reference** ``asset_id`` (its dependents), sorted.

        Args:
            asset_id: The asset whose dependents to return (a non-empty str). An id with
                no incoming edges (or absent from the graph) yields an empty tuple.
            transitive: When ``False`` (default) return only the **direct** dependents;
                when ``True`` return the full reverse-reachable closure (direct +
                transitive).

        Returns:
            The dependent ids in a stable ``asset_id``-sorted order.

        Raises:
            DependencyGraphError: If ``asset_id`` is not a non-empty str, or (when
                ``transitive``) the walk exceeds :data:`MAX_DEPENDENCY_DEPTH`.
        """
        return self._query(asset_id, _reverse_adjacency(self.edges), transitive)

    def _query(
        self,
        asset_id: str,
        adjacency: Dict[str, Tuple[str, ...]],
        transitive: bool,
    ) -> Tuple[str, ...]:
        """Return the neighbours of ``asset_id`` in ``adjacency`` (direct/closure)."""
        if not isinstance(asset_id, str) or not asset_id:
            raise DependencyGraphError(
                f"asset_id must be a non-empty str, got {asset_id!r}"
            )
        if not transitive:
            return tuple(sorted(adjacency.get(asset_id, ())))
        reached: Set[str] = set()
        current: Set[str] = set(adjacency.get(asset_id, ()))
        depth = 1
        while current:
            if depth > MAX_DEPENDENCY_DEPTH:
                raise DependencyGraphError(
                    f"transitive traversal from {asset_id!r} exceeds "
                    f"MAX_DEPENDENCY_DEPTH ({MAX_DEPENDENCY_DEPTH})"
                )
            nxt: Set[str] = set()
            for node in current:
                if node in reached:
                    continue
                reached.add(node)
                for neighbour in adjacency.get(node, ()):
                    if neighbour not in reached:
                        nxt.add(neighbour)
            current = nxt
            depth += 1
        reached.discard(asset_id)
        return tuple(sorted(reached))


def _nodes(edges: Tuple[DependencyEdge, ...]) -> Tuple[str, ...]:
    """Return the sorted set of ids appearing as any edge endpoint (deterministic)."""
    ids: Set[str] = set()
    for edge in edges:
        ids.add(edge.source_id)
        ids.add(edge.target_id)
    return tuple(sorted(ids))


def _forward_adjacency(edges: Tuple[DependencyEdge, ...]) -> Dict[str, Tuple[str, ...]]:
    """Map each ``source_id`` to its sorted tuple of ``target_id`` s (dependencies)."""
    pending: Dict[str, Set[str]] = {}
    for edge in edges:
        pending.setdefault(edge.source_id, set()).add(edge.target_id)
    return {src: tuple(sorted(targets)) for src, targets in pending.items()}


def _reverse_adjacency(edges: Tuple[DependencyEdge, ...]) -> Dict[str, Tuple[str, ...]]:
    """Map each ``target_id`` to its sorted tuple of ``source_id`` s (dependents)."""
    pending: Dict[str, Set[str]] = {}
    for edge in edges:
        pending.setdefault(edge.target_id, set()).add(edge.source_id)
    return {tgt: tuple(sorted(sources)) for tgt, sources in pending.items()}
