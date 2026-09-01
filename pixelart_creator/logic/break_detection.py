# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure, content-hash-gated reference-validation pass — deterministic, zero Qt (S11).

Break detection is the **passive flag** Phase 11 raises when a referenced asset goes
missing or changes (REQ-P11-LOGIC-005; ADR-0031 §3; CL-4). A reference — a
:class:`~pixelart_creator.logic.dependency_graph.DependencyEdge` from a referencing
asset to its target — is **BROKEN** when either:

* its ``target_id`` is **missing** from the catalog (the target asset was deleted), or
* the target's current
  :attr:`~pixelart_creator.logic.asset_catalog.AssetDescriptor.content_hash` **no longer
  matches** the edge's ``pinned_hash`` (the target's bytes changed since the reference
  was recorded).

:func:`find_broken` is a **pure, pull-based** function (no notifications, no event push
— a live push alert is an explicit FUTURE enhancement): the caller runs it and reads the
result. When ``changed_ids`` is supplied it applies **content-hash gating** — using the
dependency graph's
:meth:`~pixelart_creator.logic.dependency_graph.DependencyGraph.dependents_of`
traversal to restrict the pass to the incoming edges of the changed nodes (the only
edges that can *newly* break), so a catalog change triggers a targeted revalidation
rather than a full-graph rescan. A present, unchanged, hash-matching target is **never**
falsely flagged.

This module composes :mod:`~pixelart_creator.logic.dependency_graph` and reads
:class:`~pixelart_creator.logic.asset_catalog.AssetCatalog` descriptors — both downward
``logic`` leaves. Pure and deterministic: no Qt, no wall-clock, no randomness, no
locale-dependent ordering; it never imports ``data/`` (no ``logic -> data`` edge).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from pixelart_creator.logic.asset_catalog import AssetCatalog
from pixelart_creator.logic.dependency_graph import DependencyEdge, DependencyGraph

__all__ = [
    "BreakDetectionError",
    "BrokenReference",
    "REASON_MISSING",
    "REASON_HASH_MISMATCH",
    "find_broken",
]

#: Break-reason vocabulary (module-local enumerated strings, ADR-0001 / BF-2 — the
#: BlendMode/PlaybackMode precedent; not numeric tuning values for ``constants``).
REASON_MISSING = "missing"
REASON_HASH_MISMATCH = "hash-mismatch"


class BreakDetectionError(ValueError):
    """Raised on a malformed argument to the reference-validation pass (type check)."""


@dataclass(frozen=True)
class BrokenReference:
    """One flagged reference: the edge ``source_id`` -> ``target_id`` and why it broke.

    Attributes:
        source_id: The referencing asset (the edge source).
        target_id: The referenced asset that is missing or changed (the edge target).
        reason: :data:`REASON_MISSING` (target absent from the catalog) or
            :data:`REASON_HASH_MISMATCH` (target present but its ``content_hash`` no
            longer matches the edge's ``pinned_hash``).
    """

    source_id: str
    target_id: str
    reason: str


def _validate_changed_ids(changed_ids: Iterable[str]) -> "frozenset[str]":
    """Return ``changed_ids`` as a validated ``frozenset[str]``, else raise."""
    if isinstance(changed_ids, str):
        raise BreakDetectionError(
            "changed_ids must be an iterable of str, not a bare str"
        )
    try:
        ids = frozenset(changed_ids)
    except TypeError as exc:
        raise BreakDetectionError(
            f"changed_ids must be an iterable of str: {exc}"
        ) from exc
    for asset_id in ids:
        if not isinstance(asset_id, str) or not asset_id:
            raise BreakDetectionError(
                f"each changed id must be a non-empty str, got {asset_id!r}"
            )
    return ids


def find_broken(
    graph: DependencyGraph,
    catalog: AssetCatalog,
    *,
    changed_ids: Optional[Iterable[str]] = None,
) -> Tuple[BrokenReference, ...]:
    """Return the broken references in ``graph`` against ``catalog``, stably ordered.

    An edge is broken when its ``target_id`` is missing from ``catalog``
    (:data:`REASON_MISSING`) or the target's current ``content_hash`` differs from the
    edge's ``pinned_hash`` (:data:`REASON_HASH_MISMATCH`).

    Args:
        graph: The dependency graph whose edges are validated.
        catalog: The catalog snapshot the targets are resolved against.
        changed_ids: When ``None`` (default) every edge is validated. When supplied,
            **content-hash gating** restricts the pass to the incoming edges of the
            changed nodes — the only edges that can newly break — via the graph's
            ``dependents_of`` traversal; a present, unchanged, hash-matching target is
            never falsely flagged.

    Returns:
        The broken references in a stable ``(source_id, target_id)``-sorted order (an
        empty tuple when nothing is broken). Pure, deterministic, pull-based.

    Raises:
        BreakDetectionError: If ``graph``, ``catalog`` or ``changed_ids`` is malformed.
    """
    if not isinstance(graph, DependencyGraph):
        raise BreakDetectionError(f"graph must be a DependencyGraph, got {graph!r}")
    if not isinstance(catalog, AssetCatalog):
        raise BreakDetectionError(f"catalog must be an AssetCatalog, got {catalog!r}")

    edges = _edges_to_check(graph, changed_ids)

    broken: List[BrokenReference] = []
    for edge in edges:
        descriptor = catalog.get(edge.target_id)
        if descriptor is None:
            broken.append(
                BrokenReference(edge.source_id, edge.target_id, REASON_MISSING)
            )
        elif descriptor.content_hash != edge.pinned_hash:
            broken.append(
                BrokenReference(edge.source_id, edge.target_id, REASON_HASH_MISMATCH)
            )
    broken.sort(key=lambda ref: (ref.source_id, ref.target_id))
    return tuple(broken)


def _edges_to_check(
    graph: DependencyGraph, changed_ids: Optional[Iterable[str]]
) -> Tuple[DependencyEdge, ...]:
    """Return the edges the pass must validate (all, or the content-hash-gated subset).

    With ``changed_ids`` supplied, only the **incoming** edges of the changed nodes can
    newly break, so the pass uses the graph's ``dependents_of`` traversal to find each
    changed node's referencing assets and validates exactly those edges — never a
    full-graph rescan.
    """
    if changed_ids is None:
        return graph.edges

    changed = _validate_changed_ids(changed_ids)
    edge_by_key: Dict[Tuple[str, str], DependencyEdge] = {
        (edge.source_id, edge.target_id): edge for edge in graph.edges
    }
    gated: Set[Tuple[str, str]] = set()
    for target_id in changed:
        for source_id in graph.dependents_of(target_id):
            gated.add((source_id, target_id))
    return tuple(edge_by_key[key] for key in sorted(gated))
