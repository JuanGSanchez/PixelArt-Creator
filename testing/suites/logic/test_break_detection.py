"""Unit + property tests for :mod:`pixelart_creator.logic.break_detection` (S11, no Qt).

Covers the pure, pull-based reference-validation pass (ADR-0031 §3; REQ-P11-LOGIC-005):
``find_broken`` flags an edge to a **missing** target (``REASON_MISSING``) or a
**hash-mismatched** present target (``REASON_HASH_MISMATCH``), never false-positives an
unchanged/present/hash-matching target, gates revalidation to the dependents of
``changed_ids`` (a stale-but-unchanged reference elsewhere is NOT reflagged), returns a
stable ``(source_id, target_id)``-sorted result, and — via Hypothesis over permuted
edge-insertion orders — is order-independent / byte-identical.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.break_detection import (
    REASON_HASH_MISMATCH,
    REASON_MISSING,
    BreakDetectionError,
    BrokenReference,
    find_broken,
)
from pixelart_creator.logic.dependency_graph import DependencyEdge, DependencyGraph

# Recorded (pinned) hash of each referenced target when the edge was made.
PIN = "a" * 64
# A divergent "current" hash — the target's bytes changed since the reference.
CHANGED = "b" * 64


def descriptor(asset_id: str, content_hash: str = PIN) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        kind=AssetKind.SPRITE,
        name=f"name-{asset_id}",
        content_hash=content_hash,
    )


# --------------------------------------------------------------------------- #
# BrokenReference value + reason vocabulary                                    #
# --------------------------------------------------------------------------- #


def test_broken_reference_is_frozen_value() -> None:
    ref = BrokenReference("b", "a", REASON_MISSING)
    assert ref == BrokenReference("b", "a", REASON_MISSING)
    with pytest.raises(Exception):
        ref.reason = REASON_HASH_MISMATCH  # type: ignore[misc]


def test_reason_vocabulary_is_distinct() -> None:
    assert REASON_MISSING != REASON_HASH_MISMATCH


# --------------------------------------------------------------------------- #
# Break pass — missing / hash-mismatch / clean                                 #
# --------------------------------------------------------------------------- #


def test_flags_missing_target() -> None:
    # B references A, but A is absent from the catalog -> REASON_MISSING.
    graph = DependencyGraph(edges=(DependencyEdge("b", "a", PIN),))
    catalog = AssetCatalog(descriptors=(descriptor("b"),))
    assert find_broken(graph, catalog) == (BrokenReference("b", "a", REASON_MISSING),)


def test_flags_hash_mismatched_target() -> None:
    # A is present, but its current content_hash no longer matches the pin.
    graph = DependencyGraph(edges=(DependencyEdge("b", "a", PIN),))
    catalog = AssetCatalog(
        descriptors=(descriptor("b"), descriptor("a", content_hash=CHANGED))
    )
    assert find_broken(graph, catalog) == (
        BrokenReference("b", "a", REASON_HASH_MISMATCH),
    )


def test_present_unchanged_target_is_never_flagged() -> None:
    # A present with a matching hash -> no false positive (empty result).
    graph = DependencyGraph(edges=(DependencyEdge("b", "a", PIN),))
    catalog = AssetCatalog(descriptors=(descriptor("b"), descriptor("a")))
    assert find_broken(graph, catalog) == ()


def test_empty_graph_reports_no_breaks() -> None:
    assert find_broken(DependencyGraph(), AssetCatalog()) == ()


def test_result_is_sorted_by_source_then_target() -> None:
    graph = DependencyGraph(
        edges=(
            DependencyEdge("z", "a", PIN),
            DependencyEdge("m", "a", PIN),
            DependencyEdge("a", "q", PIN),
        )
    )
    # None of a/q/z present -> all three flagged missing, stably sorted.
    catalog = AssetCatalog(descriptors=(descriptor("m"),))
    result = find_broken(graph, catalog)
    keys = [(r.source_id, r.target_id) for r in result]
    assert keys == sorted(keys)
    assert keys == [("a", "q"), ("m", "a"), ("z", "a")]


# --------------------------------------------------------------------------- #
# changed_ids gating — only dependents of changed nodes are revalidated        #
# --------------------------------------------------------------------------- #


def test_changed_ids_gates_revalidation_to_dependents_of_changed_nodes() -> None:
    # Two independent stale references: B->A and D->C are BOTH hash-mismatched.
    graph = DependencyGraph(
        edges=(
            DependencyEdge("b", "a", PIN),
            DependencyEdge("d", "c", PIN),
        )
    )
    catalog = AssetCatalog(
        descriptors=(
            descriptor("b"),
            descriptor("d"),
            descriptor("a", content_hash=CHANGED),
            descriptor("c", content_hash=CHANGED),
        )
    )
    # Only A "changed" this pass -> only B->A is revalidated; the stale-but-
    # unchanged D->C is NOT reflagged (content-hash gating).
    result = find_broken(graph, catalog, changed_ids={"a"})
    assert result == (BrokenReference("b", "a", REASON_HASH_MISMATCH),)


def test_changed_ids_empty_set_revalidates_nothing() -> None:
    graph = DependencyGraph(edges=(DependencyEdge("b", "a", PIN),))
    catalog = AssetCatalog(descriptors=(descriptor("b"),))  # a missing
    # No node declared changed -> no edge revalidated, even though a is missing.
    assert find_broken(graph, catalog, changed_ids=set()) == ()


def test_changed_ids_none_revalidates_every_edge() -> None:
    graph = DependencyGraph(edges=(DependencyEdge("b", "a", PIN),))
    catalog = AssetCatalog(descriptors=(descriptor("b"),))
    assert find_broken(graph, catalog, changed_ids=None) == (
        BrokenReference("b", "a", REASON_MISSING),
    )


# --------------------------------------------------------------------------- #
# Argument validation                                                          #
# --------------------------------------------------------------------------- #


def test_rejects_non_graph() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken("not-a-graph", AssetCatalog())  # type: ignore[arg-type]


def test_rejects_non_catalog() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken(DependencyGraph(), "not-a-catalog")  # type: ignore[arg-type]


def test_rejects_bare_str_changed_ids() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken(DependencyGraph(), AssetCatalog(), changed_ids="a")


def test_rejects_non_iterable_changed_ids() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken(
            DependencyGraph(), AssetCatalog(), changed_ids=123  # type: ignore[arg-type]
        )


def test_rejects_non_str_changed_id_element() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken(DependencyGraph(), AssetCatalog(), changed_ids={5})


def test_rejects_empty_str_changed_id_element() -> None:
    with pytest.raises(BreakDetectionError):
        find_broken(DependencyGraph(), AssetCatalog(), changed_ids={""})


# --------------------------------------------------------------------------- #
# Determinism (Hypothesis) — permuted insertion order is byte-identical        #
# --------------------------------------------------------------------------- #


@st.composite
def _dags(draw):
    """Draw an acyclic edge set over nodes n0..n(k) (only lower->higher index)."""
    n = draw(st.integers(min_value=2, max_value=6))
    node_ids = [f"n{i}" for i in range(n)]
    possible = [(i, j) for i in range(n) for j in range(i + 1, n)]
    chosen = draw(
        st.lists(st.sampled_from(possible), unique=True, max_size=len(possible))
    )
    edges = [DependencyEdge(node_ids[i], node_ids[j], PIN) for (i, j) in chosen]
    return node_ids, edges


@given(dag=_dags(), data=st.data())
def test_find_broken_is_insertion_order_independent(dag, data) -> None:
    node_ids, edges = dag
    permuted = data.draw(st.permutations(edges))

    # Per node: present+matching / present+changed / missing.
    descriptors = []
    for node in node_ids:
        state = data.draw(st.sampled_from(["ok", "changed", "missing"]))
        if state == "missing":
            continue
        content = PIN if state == "ok" else CHANGED
        descriptors.append(descriptor(node, content_hash=content))
    catalog = AssetCatalog(descriptors=tuple(descriptors))

    graph_a = DependencyGraph(edges=tuple(edges))
    graph_b = DependencyGraph(edges=tuple(permuted))

    result_a = find_broken(graph_a, catalog)
    result_b = find_broken(graph_b, catalog)
    assert result_a == result_b

    keys = [(r.source_id, r.target_id) for r in result_a]
    assert keys == sorted(keys)
