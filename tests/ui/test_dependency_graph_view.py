"""Dependency-graph view acceptance (REQ-P11-UI-005, Gherkin: Dependency graph queryable).

Slice 2: ``Dependency_Graph_View`` visualises the depends-on (``dependencies_of``) and
referenced-by (``dependents_of``) relations for the whole catalog or the selected asset,
reading exactly the pure ``logic/dependency_graph`` queries (no domain logic in the
widget — Article I / S11). It renders only the DIRECT neighbours the model returns, so a
cyclic edge set — which the model rejects at build time and reports — can never hang the
view: :meth:`show_edges` surfaces the reported cycle in a passive label and keeps the
last good graph.

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture. All
graph/break queries are synchronous, worker-free, in-memory calls over the immutable
:class:`DependencyGraph` value (the Slice-1 ``Asset_Library_Session`` precedent), so a
read-back assertion follows the call immediately with no ``qtbot.wait``.

The canonical fixture is the ROADMAP ``sprite -> animation -> tileset -> tilemap`` graph:
an animation references its sprite frame, a tileset references its source sprite, and a
tilemap references its tileset — encoded as edges whose ``source_id`` is the *referencing*
asset (so ``dependents_of("sprite") == {"anim", "tileset"}``, per the acceptance).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.break_detection import find_broken
from pixelart_creator.logic.dependency_graph import (
    DependencyEdge,
    DependencyGraph,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.dependency_graph_view import (
    _COL_ASSET,
    _ROLE_BROKEN,
    _ROLE_EDGE,
    Dependency_Graph_View,
)

#: Content hashes for the four canonical assets (pinned on the edges that target them).
_H_SPRITE = "h-sprite"
_H_ANIM = "h-anim"
_H_TILESET = "h-tileset"
_H_TILEMAP = "h-tilemap"


def _desc(asset_id, kind, name, content_hash, tags=()):
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=content_hash,
        tags=frozenset(tags),
    )


def _fixture_catalog(sprite_hash=_H_SPRITE, tileset_hash=_H_TILESET) -> AssetCatalog:
    """The four-asset catalog; the two hashes are parameterised for break tests."""
    return AssetCatalog(
        descriptors=(
            _desc("anim", AssetKind.ANIMATION, "Walk", _H_ANIM),
            _desc("sprite", AssetKind.SPRITE, "Hero", sprite_hash),
            _desc("tilemap", AssetKind.TILEMAP, "Level1", _H_TILEMAP),
            _desc("tileset", AssetKind.TILESET, "Dungeon", tileset_hash),
        )
    )


def _fixture_graph() -> DependencyGraph:
    """``anim -> sprite``, ``tileset -> sprite``, ``tilemap -> tileset`` (all pinned)."""
    return DependencyGraph(
        edges=(
            DependencyEdge("anim", "sprite", _H_SPRITE),
            DependencyEdge("tileset", "sprite", _H_SPRITE),
            DependencyEdge("tilemap", "tileset", _H_TILESET),
        )
    )


@pytest.fixture
def view(qtbot):
    """A bound ``Dependency_Graph_View`` over the canonical, all-valid fixture."""
    session = Asset_Library_Session(catalog=_fixture_catalog(), graph=_fixture_graph())
    widget = Dependency_Graph_View()
    qtbot.addWidget(widget)
    widget.set_session(session)
    return widget, session


# -- tree-reading seams ------------------------------------------------------- #


def _group_edge_keys(group_item):
    """Return the set of edge keys (source, target) shown under a group row."""
    return {
        group_item.child(i).data(_COL_ASSET, _ROLE_EDGE)
        for i in range(group_item.childCount())
    }


def _scoped_node(widget):
    """Return the single top-level node row (the view is scoped to one asset)."""
    assert widget._tree.topLevelItemCount() == 1
    return widget._tree.topLevelItem(0)


def _dependencies_group(node_item):
    """The 'Dependencies (depends on)' group is the node's first child."""
    return node_item.child(0)


def _dependents_group(node_item):
    """The 'Dependents (referenced by)' group is the node's second child."""
    return node_item.child(1)


# -- REQ-P11-UI-005: direct dependencies + dependents match the model --------- #


def test_selected_asset_shows_direct_dependents_matching_the_model(view):
    """Scoping to 'sprite' shows its DIRECT dependents (anim, tileset), matching the model.

    ``dependents_of("sprite")`` is {anim, tileset}; the view renders exactly those edges
    under the Dependents group and nothing under Dependencies — asserted against the pure
    model (binding, not reimplementation).
    """
    widget, session = view
    widget.set_asset("sprite")
    node = _scoped_node(widget)

    graph = session.graph()
    expected_dependents = {(s, "sprite") for s in graph.dependents_of("sprite")}
    expected_dependencies = {("sprite", t) for t in graph.dependencies_of("sprite")}

    assert _group_edge_keys(_dependents_group(node)) == expected_dependents
    assert expected_dependents == {("anim", "sprite"), ("tileset", "sprite")}
    assert _group_edge_keys(_dependencies_group(node)) == expected_dependencies
    assert expected_dependencies == set()


def test_selected_asset_shows_direct_dependencies_matching_the_model(view):
    """Scoping to 'tilemap' shows its DIRECT dependency (tileset) only — not transitive."""
    widget, session = view
    widget.set_asset("tilemap")
    node = _scoped_node(widget)

    graph = session.graph()
    assert _group_edge_keys(_dependencies_group(node)) == {("tilemap", "tileset")}
    assert graph.dependencies_of("tilemap") == ("tileset",)
    # The tilemap has no dependents (nothing references it).
    assert _group_edge_keys(_dependents_group(node)) == set()


def test_view_renders_only_direct_neighbours_not_transitive(view):
    """The sprite's transitive dependent 'tilemap' is NOT shown as a direct neighbour."""
    widget, session = view
    widget.set_asset("sprite")
    node = _scoped_node(widget)
    direct = _group_edge_keys(_dependents_group(node))
    # tilemap -> tileset -> sprite: tilemap is transitive, so it must not appear directly.
    assert all(source != "tilemap" for source, _target in direct)
    # But the model does report it transitively (the widget renders only direct).
    assert "tilemap" in session.graph().dependents_of("sprite", transitive=True)


def test_whole_catalog_scope_lists_every_node(view):
    """With no asset scoped, the view lists every graph node (whole-catalog view)."""
    widget, session = view
    widget.set_asset("")
    assert widget._tree.topLevelItemCount() == len(session.graph().nodes())


# -- REQ-P11-UI-005: a cycle is shown WITHOUT hanging ------------------------- #


def test_cycle_is_shown_passively_without_hanging(view, qtbot):
    """A cyclic edge set is reported in the passive cycle label; the view never walks it.

    ``show_edges`` asks the model to build the graph; the model rejects the cycle and the
    view surfaces the reported message in a label (no dialog, no walk), keeping the last
    good graph — so a cyclic edge set can never hang the event loop.
    """
    widget, session = view
    good_graph = session.graph()
    widget.show_edges(
        [
            DependencyEdge("a", "b", "hb"),
            DependencyEdge("b", "a", "ha"),
        ]
    )
    # ``isVisibleTo`` (not ``isVisible``): the top-level view is never ``show()``n
    # headless, so the whole ancestor chain reads not-visible; ``isVisibleTo`` asserts the
    # label's own visibility flag independent of the unshown ancestor.
    assert widget._cycle_label.isVisibleTo(widget)
    assert widget._cycle_label.text() != ""
    assert "cycle" in widget._cycle_label.text().lower()
    # The last good graph is kept (the cycle never entered the session).
    assert session.graph() is good_graph
    # The event loop is not blocked: a subsequent spin returns promptly.
    qtbot.wait(1)


def test_valid_edges_replace_the_graph_and_clear_the_cycle_notice(view):
    """A valid edge set sent via ``show_edges`` replaces the graph (graphChanged path)."""
    widget, session = view
    widget.show_edges([DependencyEdge("x", "y", "hy")])
    assert not widget._cycle_label.isVisibleTo(widget)
    assert session.graph().dependencies_of("x") == ("y",)


# -- REQ-P11-UI-006: passive break indicator matches find_broken -------------- #


def test_valid_only_graph_shows_no_break_indicator(view):
    """An all-valid catalog+graph shows the 'No broken references' summary and no flags."""
    widget, session = view
    assert widget.broken_references() == ()
    assert find_broken(session.graph(), session.catalog()) == ()
    assert widget._break_label.text() == widget.tr("No broken references")
    # No edge row is marked broken.
    widget.set_asset("")
    assert not _any_edge_broken(widget)


def test_missing_and_mismatched_targets_flag_the_edges_matching_the_pass(qtbot):
    """A missing target AND a hash-mismatched target are both flagged, matching the pass.

    The view's flagged edges + summary equal ``find_broken`` exactly (binding, not
    reimplementation). Over the fixture graph, sprite's hash is CHANGED so both edges
    into it (anim -> sprite, tileset -> sprite) are hash mismatches, and tileset is
    deleted so tilemap -> tileset is a missing target — both reasons in one fixture.
    """
    # sprite present with a CHANGED hash (mismatch vs the pinned _H_SPRITE); tileset
    # deleted (missing). anim, tileset, tilemap are the broken sources.
    catalog = AssetCatalog(
        descriptors=(
            _desc("anim", AssetKind.ANIMATION, "Walk", _H_ANIM),
            _desc("sprite", AssetKind.SPRITE, "Hero", "h-sprite-CHANGED"),
            _desc("tilemap", AssetKind.TILEMAP, "Level1", _H_TILEMAP),
        )
    )
    session = Asset_Library_Session(catalog=catalog, graph=_fixture_graph())
    widget = Dependency_Graph_View()
    qtbot.addWidget(widget)
    widget.set_session(session)

    from pixelart_creator.logic.break_detection import (
        REASON_HASH_MISMATCH,
        REASON_MISSING,
    )

    broken = widget.broken_references()
    assert broken == find_broken(session.graph(), session.catalog())
    by_edge = {(r.source_id, r.target_id): r.reason for r in broken}
    assert by_edge == {
        ("anim", "sprite"): REASON_HASH_MISMATCH,
        ("tileset", "sprite"): REASON_HASH_MISMATCH,
        ("tilemap", "tileset"): REASON_MISSING,
    }
    # The summary counts every broken reference (both reasons represented).
    assert widget._break_label.text() == widget.tr("Broken references: %1").replace(
        "%1", "3"
    )
    # Exactly those edges are marked broken in the whole-catalog view.
    widget.set_asset("")
    assert _broken_edge_keys(widget) == {
        ("anim", "sprite"),
        ("tileset", "sprite"),
        ("tilemap", "tileset"),
    }


# -- REQ-P11-UI-006: refresh on catalog change (was-broken clears; and vice-versa) #


def test_break_indicator_clears_when_the_reference_is_fixed(qtbot, mute_message_boxes):
    """A was-broken edge clears after the target is restored (catalogChanged refresh)."""
    # Start broken: sprite is ABSENT, so anim/tileset -> sprite are missing.
    catalog = AssetCatalog(
        descriptors=(
            _desc("anim", AssetKind.ANIMATION, "Walk", _H_ANIM),
            _desc("tilemap", AssetKind.TILEMAP, "Level1", _H_TILEMAP),
            _desc("tileset", AssetKind.TILESET, "Dungeon", _H_TILESET),
        )
    )
    session = Asset_Library_Session(catalog=catalog, graph=_fixture_graph())
    widget = Dependency_Graph_View()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert len(widget.broken_references()) == 2  # anim->sprite, tileset->sprite missing

    # Fix it: add the sprite back with the pinned hash -> catalogChanged -> refresh.
    session.add_descriptor(_desc("sprite", AssetKind.SPRITE, "Hero", _H_SPRITE))
    assert widget.broken_references() == ()
    assert widget._break_label.text() == widget.tr("No broken references")
    # Pull-based: no dialog/push was raised by the refresh.
    assert mute_message_boxes == []


def test_break_indicator_appears_when_a_valid_reference_becomes_broken(
    view, mute_message_boxes
):
    """A valid edge becomes broken after the target's hash changes (graphChanged refresh)."""
    widget, session = view
    assert widget.broken_references() == ()
    # Change the sprite's content hash so the pinned edges no longer match.
    session.replace_descriptor(_desc("sprite", AssetKind.SPRITE, "Hero", "h-sprite-v2"))
    broken = widget.broken_references()
    assert {(r.source_id, r.target_id) for r in broken} == {
        ("anim", "sprite"),
        ("tileset", "sprite"),
    }
    assert mute_message_boxes == []  # passive; no push notification


# -- REQ-P11-UI-005/-006: no domain logic in the widget (binds to logic) ------ #


def test_view_binds_to_the_model_and_does_not_recompute(view):
    """Every relation + break flag the view shows equals the pure logic result."""
    widget, session = view
    widget.set_asset("")
    graph = session.graph()
    # The break surface is exactly find_broken (no reimplementation in the widget).
    assert widget.broken_references() == find_broken(graph, session.catalog())
    # Each node's rendered neighbours equal the model's direct queries.
    for i in range(widget._tree.topLevelItemCount()):
        node = widget._tree.topLevelItem(i)
        deps = {t for _s, t in _group_edge_keys(_dependencies_group(node))}
        dependents = {s for s, _t in _group_edge_keys(_dependents_group(node))}
        # Recover the node id from any of its edge rows (or skip an isolated node).
        node_ids = {
            key[0] for key in _group_edge_keys(_dependencies_group(node)) if key
        } | {key[1] for key in _group_edge_keys(_dependents_group(node)) if key}
        if not node_ids:
            continue
        node_id = next(iter(node_ids))
        assert deps == set(graph.dependencies_of(node_id))
        assert dependents == set(graph.dependents_of(node_id))


# -- helpers over the whole-catalog tree -------------------------------------- #


def _iter_edge_items(widget):
    """Yield every edge (leaf) item across the whole-catalog tree."""
    tree = widget._tree
    for i in range(tree.topLevelItemCount()):
        node = tree.topLevelItem(i)
        for g in range(node.childCount()):
            group = node.child(g)
            for c in range(group.childCount()):
                yield group.child(c)


def _any_edge_broken(widget):
    return any(
        bool(item.data(_COL_ASSET, _ROLE_BROKEN)) for item in _iter_edge_items(widget)
    )


def _broken_edge_keys(widget):
    return {
        item.data(_COL_ASSET, _ROLE_EDGE)
        for item in _iter_edge_items(widget)
        if bool(item.data(_COL_ASSET, _ROLE_BROKEN))
    }
