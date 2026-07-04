"""Asset-library browse + session acceptance (REQ-P11-UI-001, Gherkin: Asset catalog).

Slice 1: the library panel lists the shared session catalog's entries by name / kind /
tags via the injected ``Asset_Library_Session`` seam (NO filesystem — the catalog is fed
in memory via ``set_catalog`` / ``add_descriptor``), re-reads on ``catalogChanged`` so
adding / removing an asset updates the panel, and follows the selection by emitting
``assetSelected`` with the stable ``asset_id`` (the tagging-panel seam). Covers the
session's catalog mutation surface (set_catalog / add_descriptor / remove_asset /
replace_descriptor) that all three panels share.

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture. The
session is synchronous and worker-free, so a read-back assertion follows the call
immediately with no ``qtbot.wait`` (AGT-05 §7).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import (
    _COL_KIND,
    _COL_NAME,
    _COL_TAGS,
    Asset_Library_Panel,
)


def _desc(
    asset_id: str,
    kind: AssetKind = AssetKind.SPRITE,
    name: str = "Hero",
    tags=(),
) -> AssetDescriptor:
    """Build a valid descriptor (content_hash is any non-empty str for the model)."""
    return AssetDescriptor(
        asset_id=asset_id,
        kind=kind,
        name=name,
        content_hash=f"hash-{asset_id}",
        tags=frozenset(tags),
    )


def _catalog(*descriptors: AssetDescriptor) -> AssetCatalog:
    return AssetCatalog(descriptors=tuple(descriptors))


@pytest.fixture
def library(qtbot):
    """A bound ``Asset_Library_Panel`` over a fresh, populated loopback session."""
    session = Asset_Library_Session(
        catalog=_catalog(
            _desc("a1", AssetKind.SPRITE, "Hero", ("hero", "player")),
            _desc("a2", AssetKind.TILESET, "Dungeon", ("tileset-a",)),
            _desc("a3", AssetKind.ANIMATION, "Walk", ("hero",)),
        )
    )
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    return widget, session


def _rows(widget):
    """Return the ``(name, kind, tags)`` cells currently shown in the tree."""
    tree = widget._tree
    return [
        (
            tree.topLevelItem(i).text(_COL_NAME),
            tree.topLevelItem(i).text(_COL_KIND),
            tree.topLevelItem(i).text(_COL_TAGS),
        )
        for i in range(tree.topLevelItemCount())
    ]


# -- REQ-P11-UI-001: the panel lists exactly the catalog's entries ------------ #


def test_panel_lists_every_catalog_entry_with_kind_name_tags(library):
    """The panel shows exactly the catalog entries with correct kind/name/tags."""
    widget, _session = library
    rows = _rows(widget)
    assert widget._tree.topLevelItemCount() == 3
    # asset_id-sorted: a1 (Hero/Sprite), a2 (Dungeon/Tileset), a3 (Walk/Animation).
    assert rows[0] == ("Hero", "Sprite", "hero, player")
    assert rows[1] == ("Dungeon", "Tileset", "tileset-a")
    assert rows[2] == ("Walk", "Animation", "hero")


def test_empty_session_lists_nothing(qtbot):
    """A panel bound to an empty catalog lists no rows (no crash)."""
    session = Asset_Library_Session()
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert widget._tree.topLevelItemCount() == 0


def test_unbound_panel_refreshes_to_empty(qtbot):
    """A constructed-but-unbound panel refreshes cleanly (session-None branch)."""
    widget = Asset_Library_Panel()
    qtbot.addWidget(widget)
    # ``_refresh`` was already invoked at construction with no session.
    assert widget._tree.topLevelItemCount() == 0
    assert widget.current_asset_id() == ""


# -- REQ-P11-UI-001: adding / removing an asset updates the panel ------------- #


def test_add_descriptor_updates_the_panel(library):
    """Adding an asset to the session catalog appends its row (catalogChanged)."""
    widget, session = library
    session.add_descriptor(_desc("a4", AssetKind.PALETTE, "Sunset", ("palette",)))
    rows = _rows(widget)
    assert widget._tree.topLevelItemCount() == 4
    assert ("Sunset", "Palette", "palette") in rows


def test_remove_asset_updates_the_panel(library):
    """Removing an asset from the session catalog drops its row (catalogChanged)."""
    widget, session = library
    session.remove_asset("a2")
    names = [name for name, _kind, _tags in _rows(widget)]
    assert widget._tree.topLevelItemCount() == 2
    assert "Dungeon" not in names


def test_set_catalog_replaces_the_view(library):
    """Replacing the whole catalog repopulates the panel (e.g. after a load)."""
    widget, session = library
    session.set_catalog(_catalog(_desc("z9", AssetKind.TILEMAP, "Level1")))
    assert _rows(widget) == [("Level1", "Tilemap", "")]


# -- REQ-P11-UI-001: selection drives ``assetSelected`` ----------------------- #


def test_selecting_a_row_emits_asset_selected_with_its_id(library, qtbot):
    """Selecting a row emits ``assetSelected`` with the entry's stable asset_id."""
    widget, _session = library
    with qtbot.waitSignal(widget.assetSelected, timeout=1000) as blocker:
        widget._tree.setCurrentItem(widget._tree.topLevelItem(0))
    assert blocker.args == ["a1"]
    assert widget.current_asset_id() == "a1"


def test_selection_is_restored_after_a_catalog_change(library):
    """A selected asset stays selected across a catalogChanged refresh."""
    widget, session = library
    widget._tree.setCurrentItem(widget._tree.topLevelItem(0))  # a1
    assert widget.current_asset_id() == "a1"
    session.add_descriptor(_desc("a5", AssetKind.SPRITE, "Villain"))
    # The refresh rebuilt the tree but restored the a1 selection.
    assert widget.current_asset_id() == "a1"


def test_current_asset_id_is_empty_with_no_selection(library):
    """With nothing selected, ``current_asset_id`` returns the empty string."""
    widget, _session = library
    assert widget.current_asset_id() == ""


# -- Session catalog-mutation surface (shared by all three panels) ------------ #


def test_session_replace_descriptor_swaps_the_entry(library):
    """``replace_descriptor`` (the tag-command apply hook) swaps an entry in place."""
    widget, session = library
    updated = _desc("a1", AssetKind.SPRITE, "Hero", ("hero", "player", "boss"))
    session.replace_descriptor(updated)
    tags = {d.asset_id: d.tags for d in session.catalog().entries()}
    assert "boss" in tags["a1"]
    # The panel re-read the swap.
    assert ("Hero", "Sprite", "boss, hero, player") in _rows(widget)


def test_session_set_catalog_rejects_non_catalog(library):
    """``set_catalog`` type-guards its input with a clean ``TypeError``."""
    _widget, session = library
    with pytest.raises(TypeError):
        session.set_catalog(["not", "a", "catalog"])


def test_session_add_duplicate_id_raises_model_error(library):
    """Adding a duplicate asset_id surfaces the catalog model error (not a crash)."""
    _widget, session = library
    with pytest.raises(AssetCatalogModelError):
        session.add_descriptor(_desc("a1", AssetKind.SPRITE, "Clone"))


def test_session_remove_unknown_id_raises_model_error(library):
    """Removing an unknown asset_id surfaces the catalog model error."""
    _widget, session = library
    with pytest.raises(AssetCatalogModelError):
        session.remove_asset("nope")


def test_session_exposes_its_shared_undo_stack(library):
    """The session owns the shared undo stack the tag commands push onto."""
    _widget, session = library
    stack = session.undo_stack()
    assert stack is session.undo_stack()  # stable identity
    assert stack.count() == 0
