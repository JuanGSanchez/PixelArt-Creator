"""Search / filter acceptance (REQ-P11-UI-003, Gherkin: Search and filter).

The search panel collects a name substring, comma-split tag(s), and a kind and
emits ``queryChanged(name, tags, kind)``; wired to ``Asset_Library_Panel.set_query`` it
drives the pure ``logic/asset_query.query`` so the library narrows to the matching
entries. The three filters INTERSECT (name AND tags AND kind); ``clear()`` restores the
full catalog. This suite wires the two panels through the session exactly as the window
does, then asserts the shown rows narrow / restore.

Every test runs under BOTH themes via the autouse ``theme`` fixture; the query is a
pure, synchronous function, so the narrowed view is asserted immediately (no wait).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import _COL_NAME, Asset_Library_Panel
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel


def _desc(asset_id, kind, name, tags=()):
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=f"hash-{asset_id}",
        tags=frozenset(tags),
    )


@pytest.fixture
def wired(qtbot):
    """A search panel wired to a library panel over a shared, mixed catalog."""
    session = Asset_Library_Session(
        catalog=AssetCatalog(
            descriptors=(
                _desc("a1", AssetKind.SPRITE, "Hero", ("hero", "player")),
                _desc("a2", AssetKind.SPRITE, "Heroine", ("hero",)),
                _desc("a3", AssetKind.TILESET, "Dungeon", ("tileset-a",)),
                _desc("a4", AssetKind.ANIMATION, "Hero Walk", ("hero",)),
            )
        )
    )
    library = Asset_Library_Panel()
    search = Asset_Search_Panel()
    qtbot.addWidget(library)
    qtbot.addWidget(search)
    library.set_session(session)
    # Wire exactly as Main_Window does.
    search.queryChanged.connect(library.set_query)
    return search, library, session


def _shown_names(library):
    tree = library._tree
    return {
        tree.topLevelItem(i).text(_COL_NAME) for i in range(tree.topLevelItemCount())
    }


# -- REQ-P11-UI-003: name substring narrows the list ------------------------- #


def test_name_substring_narrows_to_matches(wired):
    """Typing a name substring narrows the library to case-insensitive matches."""
    search, library, _session = wired
    search._name_edit.setText("hero")  # case-insensitive
    assert _shown_names(library) == {"Hero", "Heroine", "Hero Walk"}


def test_name_substring_is_case_insensitive(wired):
    """The name filter uses casefold (Unicode, locale-independent)."""
    search, library, _session = wired
    search._name_edit.setText("DUNGEON")
    assert _shown_names(library) == {"Dungeon"}


# -- REQ-P11-UI-003: tag + kind filters -------------------------------------- #


def test_tag_filter_narrows_to_tagged_entries(wired):
    """Filtering by a tag returns exactly the entries carrying it."""
    search, library, _session = wired
    search._tag_edit.setText("player")
    assert _shown_names(library) == {"Hero"}


def test_comma_split_tags_are_anded(wired):
    """Comma-separated tags AND together (both must be present)."""
    search, library, _session = wired
    search._tag_edit.setText("hero, player")
    assert _shown_names(library) == {"Hero"}


def test_kind_filter_narrows_to_kind(wired):
    """Selecting a kind narrows to entries of that kind."""
    search, library, _session = wired
    index = search._kind_combo.findData(AssetKind.SPRITE)
    search._kind_combo.setCurrentIndex(index)
    assert _shown_names(library) == {"Hero", "Heroine"}


# -- REQ-P11-UI-003: combined filters intersect ------------------------------ #


def test_combined_name_tag_kind_intersect(wired):
    """A name + tag + kind query returns the intersection of all three."""
    search, library, _session = wired
    search._name_edit.setText("hero")
    search._tag_edit.setText("hero")
    index = search._kind_combo.findData(AssetKind.SPRITE)
    search._kind_combo.setCurrentIndex(index)
    # name~hero AND tag hero AND kind sprite -> Hero, Heroine (Hero Walk is animation).
    assert _shown_names(library) == {"Hero", "Heroine"}


# -- REQ-P11-UI-003: clear restores the full catalog ------------------------- #


def test_clear_restores_the_full_catalog(wired):
    """Clearing every control restores the full catalog list."""
    search, library, _session = wired
    search._name_edit.setText("hero")
    search._tag_edit.setText("player")
    assert _shown_names(library) == {"Hero"}
    search.clear()
    assert _shown_names(library) == {"Hero", "Heroine", "Dungeon", "Hero Walk"}


# -- queryChanged payload shape ---------------------------------------------- #


def test_query_changed_carries_name_tags_kind(wired, qtbot):
    """``queryChanged`` emits ``(name:str, tags:list, kind:AssetKind|None)``."""
    search, _library, _session = wired
    with qtbot.waitSignal(search.queryChanged, timeout=1000) as blocker:
        search._tag_edit.setText("hero, player")
    name, tags, kind = blocker.args
    assert name == ""
    assert tags == ["hero", "player"]
    assert kind is None


def test_query_accessors_reflect_controls(wired):
    """The typed accessors return trimmed name, split tags, and the selected kind."""
    search, _library, _session = wired
    search._name_edit.setText("  Hero  ")
    search._tag_edit.setText(" hero , , player ")
    index = search._kind_combo.findData(AssetKind.TILESET)
    search._kind_combo.setCurrentIndex(index)
    assert search.name_filter() == "Hero"
    assert search.tag_filters() == ["hero", "player"]  # trimmed, empties dropped
    assert search.kind_filter() is AssetKind.TILESET


def test_all_kinds_entry_yields_none_kind(wired):
    """The 'All kinds' combo entry maps to ``None`` (no kind filter)."""
    search, _library, _session = wired
    search._kind_combo.setCurrentIndex(0)
    assert search.kind_filter() is None
