"""Unit + property tests for ``pixelart_creator.logic.dependency_graph`` (S11, no Qt).

Covers the pure, queryable asset-dependency graph (ADR-0031 §1/§2; REQ-P11-LOGIC-004):
direct + transitive ``dependencies_of`` / ``dependents_of`` over the acceptance
``sprite -> animation -> tileset -> tilemap`` fixture in a stable, deterministic order;
cycle rejection (a cycle-inducing edge / self-loop raises, and the acyclic graph never
hangs on a query); idempotent re-add + conflicting-``pinned_hash`` rejection; the
transitive depth bound imported from ``logic/constants`` (``MAX_DEPENDENCY_DEPTH`` — no
inlined literal); and — via Hypothesis over permuted edge-insertion orders — that the
built graph and its queries are order-independent / byte-identical.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import dependency_graph
from pixelart_creator.logic.constants import MAX_DEPENDENCY_DEPTH
from pixelart_creator.logic.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
    DependencyGraphError,
)

# --------------------------------------------------------------------------- #
# Acceptance fixture: sprite -> animation -> tileset -> tilemap                #
#   (REQ-P11-LOGIC-004 / acceptance "Dependency graph is queryable")          #
#                                                                             #
#   Each DependencyEdge is source_id -> target_id ("source references target"):#
#     * animation A references sprite S   (S is a frame of A)                  #
#     * tileset   T references sprite S   (S is T's source image)             #
#     * tilemap   M references tileset T  (M uses T)                          #
# --------------------------------------------------------------------------- #

SPRITE = "asset-sprite-s"
ANIM = "asset-anim-a"
TILESET = "asset-tileset-t"
TILEMAP = "asset-tilemap-m"

H_S = "5" * 64
H_T = "7" * 64


def sample_graph() -> DependencyGraph:
    """Return the acceptance dependency graph (A->S, T->S, M->T)."""
    return DependencyGraph(
        edges=(
            DependencyEdge(ANIM, SPRITE, H_S),
            DependencyEdge(TILESET, SPRITE, H_S),
            DependencyEdge(TILEMAP, TILESET, H_T),
        )
    )


# --------------------------------------------------------------------------- #
# DependencyEdge — field validation                                           #
# --------------------------------------------------------------------------- #


def test_edge_is_frozen_value() -> None:
    edge = DependencyEdge("a", "b", H_S)
    assert edge == DependencyEdge("a", "b", H_S)
    with pytest.raises(Exception):
        edge.source_id = "changed"  # type: ignore[misc]


def test_edge_rejects_empty_source() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge("", "b", H_S)


def test_edge_rejects_non_str_source() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge(1, "b", H_S)  # type: ignore[arg-type]


def test_edge_rejects_empty_target() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge("a", "", H_S)


def test_edge_rejects_non_str_target() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge("a", 2, H_S)  # type: ignore[arg-type]


def test_edge_rejects_empty_pinned_hash() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge("a", "b", "")


def test_edge_rejects_non_str_pinned_hash() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyEdge("a", "b", None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# DependencyGraph — construction / normalisation                              #
# --------------------------------------------------------------------------- #


def test_empty_graph_has_no_nodes() -> None:
    assert DependencyGraph().nodes() == ()
    assert DependencyGraph().edges == ()


def test_graph_rejects_non_edge_member() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyGraph(edges=("not-an-edge",))  # type: ignore[arg-type]


def test_graph_normalises_edges_to_sorted_order() -> None:
    g = sample_graph()
    keys = [(e.source_id, e.target_id) for e in g.edges]
    assert keys == sorted(keys)


def test_constructor_collapses_identical_duplicate_edges() -> None:
    edge = DependencyEdge(ANIM, SPRITE, H_S)
    g = DependencyGraph(edges=(edge, edge))
    assert g.edges == (edge,)


def test_constructor_rejects_conflicting_pinned_hash() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyGraph(
            edges=(
                DependencyEdge(ANIM, SPRITE, H_S),
                DependencyEdge(ANIM, SPRITE, H_T),
            )
        )


def test_nodes_returns_sorted_endpoints() -> None:
    assert sample_graph().nodes() == (ANIM, SPRITE, TILEMAP, TILESET)


# --------------------------------------------------------------------------- #
# Direct + transitive queries over the acceptance fixture (deterministic)     #
# --------------------------------------------------------------------------- #


def test_direct_dependents_of_sprite() -> None:
    # Who references S directly -> animation A and tileset T (sorted).
    assert sample_graph().dependents_of(SPRITE) == (ANIM, TILESET)


def test_transitive_dependents_of_sprite_includes_tilemap() -> None:
    # A, T reference S; M references T -> transitive closure adds M.
    assert sample_graph().dependents_of(SPRITE, transitive=True) == (
        ANIM,
        TILEMAP,
        TILESET,
    )


def test_direct_dependencies_of_tilemap() -> None:
    # What M references directly -> tileset T.
    assert sample_graph().dependencies_of(TILEMAP) == (TILESET,)


def test_transitive_dependencies_of_tilemap_includes_sprite() -> None:
    # M -> T -> S : transitive dependencies of M are {T, S}.
    assert sample_graph().dependencies_of(TILEMAP, transitive=True) == (SPRITE, TILESET)


def test_leaf_has_no_dependencies_or_isolated_dependents() -> None:
    g = sample_graph()
    # Sprite S references nothing (it is a pure target).
    assert g.dependencies_of(SPRITE) == ()
    assert g.dependencies_of(SPRITE, transitive=True) == ()
    # Nothing references the tilemap M (top of the chain).
    assert g.dependents_of(TILEMAP) == ()
    assert g.dependents_of(TILEMAP, transitive=True) == ()


def test_query_for_absent_id_is_empty() -> None:
    g = sample_graph()
    assert g.dependencies_of("ghost") == ()
    assert g.dependents_of("ghost", transitive=True) == ()


def test_query_rejects_empty_asset_id() -> None:
    with pytest.raises(DependencyGraphError):
        sample_graph().dependencies_of("")


def test_query_rejects_non_str_asset_id() -> None:
    with pytest.raises(DependencyGraphError):
        sample_graph().dependents_of(42)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# add_edge — pure, cycle-safe, idempotent                                     #
# --------------------------------------------------------------------------- #


def test_add_edge_returns_new_graph_leaving_original_unchanged() -> None:
    base = DependencyGraph()
    added = base.add_edge(DependencyEdge(ANIM, SPRITE, H_S))
    assert base.edges == ()
    assert added.edges == (DependencyEdge(ANIM, SPRITE, H_S),)


def test_add_edge_rejects_non_edge() -> None:
    with pytest.raises(DependencyGraphError):
        DependencyGraph().add_edge("nope")  # type: ignore[arg-type]


def test_add_identical_edge_is_idempotent_noop() -> None:
    g = sample_graph()
    same = DependencyEdge(ANIM, SPRITE, H_S)
    result = g.add_edge(same)
    assert result is g


def test_add_conflicting_pinned_hash_is_rejected() -> None:
    g = sample_graph()
    with pytest.raises(DependencyGraphError):
        g.add_edge(DependencyEdge(ANIM, SPRITE, H_T))


def test_add_edge_rejects_self_loop() -> None:
    # A self-reference is a 1-cycle -> rejected, never stored.
    with pytest.raises(DependencyGraphError):
        DependencyGraph().add_edge(DependencyEdge(SPRITE, SPRITE, H_S))


def test_add_cycle_inducing_edge_is_rejected() -> None:
    # A->S, T->S, M->T ; adding S->M closes the cycle S->M->T->S.
    g = sample_graph()
    with pytest.raises(DependencyGraphError):
        g.add_edge(DependencyEdge(SPRITE, TILEMAP, H_T))


def test_constructor_rejects_cyclic_edge_set_without_hanging() -> None:
    # A cyclic edge set is reported at construction (never an infinite loop).
    with pytest.raises(DependencyGraphError):
        DependencyGraph(
            edges=(
                DependencyEdge("x", "y", H_S),
                DependencyEdge("y", "z", H_S),
                DependencyEdge("z", "x", H_S),
            )
        )


# --------------------------------------------------------------------------- #
# Depth bound — from logic/constants, not an inlined literal                  #
# --------------------------------------------------------------------------- #


def test_depth_bound_is_the_named_constant() -> None:
    # The module's bound is the single-source constant (no magic literal, S12).
    assert dependency_graph.MAX_DEPENDENCY_DEPTH is MAX_DEPENDENCY_DEPTH


def _linear_chain(length: int) -> DependencyGraph:
    """Return an acyclic chain n0 -> n1 -> ... -> n(length) of ``length`` edges."""
    width = len(str(length))
    nodes = [f"n{i:0{width}d}" for i in range(length + 1)]
    edges = tuple(DependencyEdge(nodes[i], nodes[i + 1], H_S) for i in range(length))
    return DependencyGraph(edges=edges), nodes


def test_chain_within_depth_bound_traverses() -> None:
    g, nodes = _linear_chain(MAX_DEPENDENCY_DEPTH - 1)
    reached = g.dependencies_of(nodes[0], transitive=True)
    assert reached == tuple(sorted(nodes[1:]))


def test_chain_deeper_than_depth_bound_raises() -> None:
    g, nodes = _linear_chain(MAX_DEPENDENCY_DEPTH + 5)
    with pytest.raises(DependencyGraphError):
        g.dependencies_of(nodes[0], transitive=True)


# --------------------------------------------------------------------------- #
# Determinism (Hypothesis) — permuted insertion order is byte-identical       #
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
    edges = [DependencyEdge(node_ids[i], node_ids[j], H_S) for (i, j) in chosen]
    return node_ids, edges


@given(dag=_dags(), data=st.data())
def test_graph_and_queries_are_insertion_order_independent(dag, data) -> None:
    node_ids, edges = dag
    permuted = data.draw(st.permutations(edges))

    from_constructor = DependencyGraph(edges=tuple(edges))
    built_by_add = DependencyGraph()
    for edge in permuted:
        built_by_add = built_by_add.add_edge(edge)

    # Same normalised edge tuple regardless of how the graph was assembled.
    assert from_constructor.edges == built_by_add.edges

    for node in node_ids:
        assert from_constructor.dependencies_of(node) == built_by_add.dependencies_of(
            node
        )
        assert from_constructor.dependents_of(node) == built_by_add.dependents_of(node)
        assert from_constructor.dependencies_of(
            node, transitive=True
        ) == built_by_add.dependencies_of(node, transitive=True)
        assert from_constructor.dependents_of(
            node, transitive=True
        ) == built_by_add.dependents_of(node, transitive=True)
        # Deterministic sorted order.
        deps = from_constructor.dependencies_of(node, transitive=True)
        assert list(deps) == sorted(deps)
