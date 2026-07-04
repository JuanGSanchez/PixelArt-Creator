"""Main_Window Slice-1 asset-library wiring + teardown (REQ-P11-UI-001/-002/-003).

The window builds one ``Asset_Library_Session`` and the three dock panels (library /
tagging / search), binds each panel to that session, wires
``assetSelected -> tagging.set_asset`` and ``queryChanged -> library.set_query``, docks
them via the workflow-dock helper, joins the session's undo stack to the window undo
group, and exposes their toggle actions + the ``&Library`` menu (retranslated). This is
the end-to-end integration seam the panels' unit tests build on. Runs under BOTH themes.

Also a teardown regression guard (AGT-05 §3: NO worker was introduced — the session and
panels are ordinary parent-owned Qt objects, so this asserts they dispose cleanly with
the window under the ``_drain_prewarm_after_test`` fixture, and that the three panels
are registered in the conftest ``_PHASE9_DISPOSABLE`` drain set).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_library_panel import Asset_Library_Panel
from pixelart_creator.ui.asset_search_panel import Asset_Search_Panel
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_window_builds_one_session_and_three_panels(qtbot):
    """The window owns a session + the three asset panels."""
    win = _window(qtbot)
    assert isinstance(win._asset_session, Asset_Library_Session)
    assert isinstance(win._asset_library_panel, Asset_Library_Panel)
    assert isinstance(win._asset_tagging_panel, Asset_Tagging_Panel)
    assert isinstance(win._asset_search_panel, Asset_Search_Panel)


def test_library_and_tagging_bound_to_the_same_session(qtbot):
    """The library + tagging panels drive the ONE window session (shared seam)."""
    win = _window(qtbot)
    assert win._asset_library_panel._session is win._asset_session
    assert win._asset_tagging_panel._session is win._asset_session


def test_panels_are_docked(qtbot):
    """The three panels live in dock widgets holding exactly their panel."""
    win = _window(qtbot)
    assert win._asset_library_dock.widget() is win._asset_library_panel
    assert win._asset_search_dock.widget() is win._asset_search_panel
    assert win._asset_tagging_dock.widget() is win._asset_tagging_panel


def test_library_menu_exposes_dock_toggles(qtbot):
    """Each dock's toggle view action is available under the &Library menu."""
    win = _window(qtbot)
    menu_actions = set(win._library_menu.actions())
    for dock in (
        win._asset_library_dock,
        win._asset_search_dock,
        win._asset_tagging_dock,
    ):
        assert dock.toggleViewAction() in menu_actions


def test_selection_flows_from_library_to_tagging(qtbot):
    """Selecting an asset in the library follows through to the tagging panel."""
    win = _window(qtbot)
    win._asset_session.set_catalog(
        AssetCatalog(
            descriptors=(
                AssetDescriptor(
                    asset_id="a1",
                    kind=AssetKind.SPRITE,
                    name="Hero",
                    content_hash="h1",
                    tags=frozenset({"hero"}),
                ),
            )
        )
    )
    library = win._asset_library_panel
    library._tree.setCurrentItem(library._tree.topLevelItem(0))
    assert win._asset_tagging_panel._asset_id == "a1"


def test_search_narrows_the_library_through_the_window_wiring(qtbot):
    """A window-level search narrows the docked library (queryChanged wiring)."""
    win = _window(qtbot)
    win._asset_session.set_catalog(
        AssetCatalog(
            descriptors=(
                AssetDescriptor(
                    asset_id="a1",
                    kind=AssetKind.SPRITE,
                    name="Hero",
                    content_hash="h1",
                ),
                AssetDescriptor(
                    asset_id="a2",
                    kind=AssetKind.TILESET,
                    name="Dungeon",
                    content_hash="h2",
                ),
            )
        )
    )
    win._asset_search_panel._name_edit.setText("hero")
    tree = win._asset_library_panel._tree
    names = {tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())}
    assert names == {"Hero"}


def test_session_undo_stack_joined_to_window_undo_group(qtbot):
    """The session's tag undo stack is a member of the window's undo group."""
    win = _window(qtbot)
    stack = win._asset_session.undo_stack()
    assert isinstance(stack, QUndoStack)
    # The window joins the stack to its shared undo group so global Undo reaches it.
    assert stack in win._undo_group.stacks()


def test_library_dock_title_retranslates(qtbot):
    """The dock titles + &Library menu retranslate on a language change (F5)."""
    win = _window(qtbot)
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert win._asset_library_dock.windowTitle() != ""
    assert win._asset_search_dock.windowTitle() != ""
    assert win._asset_tagging_dock.windowTitle() != ""
    assert win._library_menu.title() != ""


# -- Teardown regression guard (AGT-05 §3: no worker introduced) -------------- #


def test_standalone_panels_are_registered_in_the_drain_set():
    """The three panels are in the conftest ``_PHASE9_DISPOSABLE`` disposal set.

    AGT-05 introduced NO worker (synchronous, in-memory), so there is nothing to
    shut down — but the panels must still be disposed at teardown so no standalone
    instance accumulates across the suite under ``pytest -n auto`` (the disposal-
    hygiene contract; here a regression guard).
    """
    from tests.ui.conftest import _PHASE9_DISPOSABLE

    for cls in (Asset_Library_Panel, Asset_Tagging_Panel, Asset_Search_Panel):
        assert cls in _PHASE9_DISPOSABLE


def test_window_with_asset_panels_disposes_cleanly(qtbot):
    """Building a window (which owns the asset panels) and tearing it down is clean.

    The autouse ``_drain_prewarm_after_test`` fixture disposes the tracked window and
    its parent-owned asset session/panels; this test simply exercises that path (no
    worker, no shutdown_* needed) and asserts construction succeeds.
    """
    win = _window(qtbot)
    assert win._asset_session is not None
    # Teardown (fixture) disposes win + its children with no segfault.
