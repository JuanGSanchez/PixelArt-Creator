"""Passive break surface + a11y + both-theme render (REQ-P11-UI-006 / -008 / -009).

Slice 2 surfaces broken references PASSIVELY on two seams that share one
``Asset_Library_Session``: a Status column on ``Asset_Library_Panel`` (this module's
focus) and the per-edge status on ``Dependency_Graph_View`` (covered alongside it here for
the a11y + both-theme gates, TG-05 / TG-06 Slice-2 slice). The indicator reflects the pure
``logic/break_detection.find_broken`` pass exactly, refreshes on ``catalogChanged`` /
``graphChanged`` (triggered revalidation), and raises NO dialog / push notification — an
asset whose outgoing reference is broken shows the flag; a valid-only asset shows none.

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture. All
queries are synchronous, worker-free, in-memory calls, so a read-back follows immediately.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

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
from pixelart_creator.ui.asset_library_panel import (
    _COL_NAME,
    _COL_STATUS,
    Asset_Library_Panel,
)
from pixelart_creator.ui.dependency_graph_view import Dependency_Graph_View


def _desc(asset_id, kind, name, content_hash, tags=()):
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=content_hash,
        tags=frozenset(tags),
    )


@pytest.fixture
def broken_session():
    """A session whose graph has BOTH a missing-target and a hash-mismatched edge.

    ``walk`` references the present ``hero`` (valid) AND an absent ``ghost`` (missing);
    ``dungeon`` references ``hero`` with a stale pin (hash mismatch). So ``walk`` and
    ``dungeon`` are broken sources; ``hero`` (no outgoing edge) is valid-only.
    """
    catalog = AssetCatalog(
        descriptors=(
            _desc("dungeon", AssetKind.TILESET, "Dungeon", "h-dungeon"),
            _desc("hero", AssetKind.SPRITE, "Hero", "h-hero"),
            _desc("walk", AssetKind.ANIMATION, "Walk", "h-walk"),
        )
    )
    graph = DependencyGraph(
        edges=(
            DependencyEdge("walk", "hero", "h-hero"),  # valid
            DependencyEdge("walk", "ghost", "h-ghost"),  # missing target
            DependencyEdge("dungeon", "hero", "h-hero-OLD"),  # hash mismatch
        )
    )
    return Asset_Library_Session(catalog=catalog, graph=graph)


@pytest.fixture
def library(qtbot, broken_session):
    """An ``Asset_Library_Panel`` bound to the broken-reference session."""
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    widget.set_session(broken_session)
    return widget, broken_session


def _status_by_name(widget):
    """Return a ``{display name: Status-column text}`` map of the listed rows."""
    tree = widget._tree
    return {
        tree.topLevelItem(i).text(_COL_NAME): tree.topLevelItem(i).text(_COL_STATUS)
        for i in range(tree.topLevelItemCount())
    }


# -- REQ-P11-UI-006: the panel Status column flags broken sources ------------- #


def test_panel_flags_broken_sources_and_leaves_valid_assets_clear(library):
    """Broken-source rows show the indicator; the valid-only asset shows nothing.

    ``walk`` (a missing target) and ``dungeon`` (a hash mismatch) are flagged; ``hero``
    (no broken outgoing reference) is clear — the two break reasons and the negative case
    in one assertion.
    """
    widget, session = library
    status = _status_by_name(widget)
    flag = widget.tr("Broken reference")
    assert status == {"Walk": flag, "Dungeon": flag, "Hero": ""}
    # The flagged sources equal the pure pass exactly (binding, not reimplementation).
    expected_sources = {
        ref.source_id for ref in find_broken(session.graph(), session.catalog())
    }
    assert widget.broken_source_ids() == frozenset(expected_sources)
    assert widget.broken_source_ids() == frozenset({"walk", "dungeon"})


def test_panel_status_matches_find_broken(library):
    """The set of flagged rows equals ``find_broken`` mapped through the catalog listing."""
    widget, session = library
    broken_sources = widget.broken_source_ids()
    flagged = {
        widget._tree.topLevelItem(i).data(_COL_NAME, Qt.ItemDataRole.UserRole)
        for i in range(widget._tree.topLevelItemCount())
        if widget._tree.topLevelItem(i).text(_COL_STATUS)
    }
    assert flagged == set(broken_sources)


def test_valid_only_session_shows_no_status_flags(qtbot):
    """A catalog+graph with only valid references shows an empty Status column."""
    catalog = AssetCatalog(
        descriptors=(
            _desc("hero", AssetKind.SPRITE, "Hero", "h-hero"),
            _desc("walk", AssetKind.ANIMATION, "Walk", "h-walk"),
        )
    )
    graph = DependencyGraph(edges=(DependencyEdge("walk", "hero", "h-hero"),))
    session = Asset_Library_Session(catalog=catalog, graph=graph)
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert widget.broken_source_ids() == frozenset()
    assert set(_status_by_name(widget).values()) == {""}


# -- REQ-P11-UI-006: the flag refreshes on catalog change (pull-based, no push) #


def test_panel_flag_clears_when_the_reference_is_fixed(qtbot, mute_message_boxes):
    """A was-broken row clears after the missing target is added (catalogChanged)."""
    catalog = AssetCatalog(
        descriptors=(_desc("walk", AssetKind.ANIMATION, "Walk", "h-walk"),)
    )
    graph = DependencyGraph(edges=(DependencyEdge("walk", "hero", "h-hero"),))
    session = Asset_Library_Session(catalog=catalog, graph=graph)
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert widget.broken_source_ids() == frozenset({"walk"})  # hero missing

    session.add_descriptor(_desc("hero", AssetKind.SPRITE, "Hero", "h-hero"))
    assert widget.broken_source_ids() == frozenset()
    assert _status_by_name(widget)["Walk"] == ""
    assert mute_message_boxes == []  # pull-based refresh; no dialog raised


def test_panel_flag_appears_when_a_valid_reference_becomes_broken(
    library, mute_message_boxes
):
    """A valid row becomes flagged after the target's hash changes (catalogChanged)."""
    widget, session = library
    # Re-pin walk->hero to hero's current hash so walk starts with only the ghost break;
    # then break the hero reference by changing hero's content hash.
    session.set_graph(
        DependencyGraph(edges=(DependencyEdge("walk", "hero", "h-hero"),))
    )
    assert widget.broken_source_ids() == frozenset()  # only valid edge now
    session.replace_descriptor(_desc("hero", AssetKind.SPRITE, "Hero", "h-hero-v2"))
    assert widget.broken_source_ids() == frozenset({"walk"})
    assert _status_by_name(widget)["Walk"] == widget.tr("Broken reference")
    assert mute_message_boxes == []


def test_panel_has_no_domain_logic_binds_to_find_broken(library):
    """The panel recomputes nothing: its flags equal ``find_broken`` over the session."""
    widget, session = library
    assert widget.broken_source_ids() == frozenset(
        ref.source_id for ref in find_broken(session.graph(), session.catalog())
    )


# -- REQ-P11-UI-008: a11y on the view's controls + the break indicator -------- #


@pytest.fixture
def view(qtbot, broken_session):
    """A ``Dependency_Graph_View`` bound to the broken-reference session."""
    widget = Dependency_Graph_View()
    qtbot.addWidget(widget)
    widget.set_session(broken_session)
    return widget, broken_session


def test_view_controls_have_accessible_names(view):
    """The view, its relation tree, the break indicator, and cycle notice are named."""
    widget, _session = view
    assert widget.accessibleName() != ""
    assert widget._tree.accessibleName() != ""
    assert widget._break_label.accessibleName() != ""  # the break indicator
    assert widget._cycle_label.accessibleName() != ""


def test_view_break_indicator_is_populated_and_named(view):
    """The break summary label carries text (legible) and an accessible name."""
    widget, _session = view
    assert widget._break_label.text() != ""
    assert widget._break_label.accessibleName() == widget.tr("Broken reference summary")


def test_view_tree_is_keyboard_reachable(view):
    """The relation tree accepts keyboard focus (not NoFocus) — logical single target."""
    widget, _session = view
    assert widget._tree.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert widget._tree.selectionMode() == widget._tree.SelectionMode.SingleSelection


def test_visible_focus_indicator_is_themed(view):
    """A visible focus ring is themed once by role (``:focus`` QSS), both themes."""
    assert ":focus" in QApplication.instance().styleSheet()


# -- REQ-P11-UI-009: both themes render with role-based colours (no inline) ---- #


def test_view_and_status_column_carry_no_inline_colour(view, library, theme):
    """View + break Status column lay out under the active theme with no inline colour.

    The autouse ``theme`` fixture runs this under BOTH light and dark; colours come from
    the applied QSS role palette (no per-widget hard-coded colour), and the break
    indicator stays populated (legible) in both themes.
    """
    widget, _session = view
    panel, _s2 = library
    for w in (widget, widget._tree, widget._break_label, widget._cycle_label, panel):
        assert w.styleSheet() == ""
    assert widget.sizeHint().isValid()
    assert panel.sizeHint().isValid()
    # The break indicator renders legibly (populated) under the active theme.
    assert widget._break_label.text() != ""
    assert any(status for status in _status_by_name(panel).values())


def test_view_retranslates_on_language_change(view):
    """The view re-sets its tr() strings on ``QEvent.LanguageChange`` (F5) without crash."""
    widget, _session = view
    QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
    assert widget._tree.headerItem().text(0) != ""
    assert widget._break_label.text() != ""
