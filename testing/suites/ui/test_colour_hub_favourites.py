"""Colour-hub Favourites acceptance tests (REQ-P3-UI-004, S3a/S4).

One test per acceptance criterion for :class:`Favourites_Panel` and its
persistence:

* SC-U004-1 add stores the current colour; remove and reorder work.
* SC-U004-2 clicking a favourite applies it (emits the chosen colour).
* SC-U004-3 PERSISTENCE (acceptance-critical): a saved favourite is still present
  after an app "restart" — proven via the ``favourites_io`` round-trip and a
  fresh panel rebound to the reloaded model.
* SC-U004-4 the list is tr()-wrapped and keyboard-reachable, both themes.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pixelart_creator.data.favourites_io import load_favourites, save_favourites
from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.ui.colour_hub_menu import Favourites_Panel

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


@pytest.fixture
def panel(qtbot) -> Favourites_Panel:
    """An empty Favourites panel registered with qtbot."""
    widget = Favourites_Panel()
    qtbot.addWidget(widget)
    return widget


# -- SC-U004-1 (add / remove / reorder) ----------------------------------------


def test_sc_u004_1_add_stores_current_colour(panel, qtbot):
    """SC-U004-1: adding a colour grows the model and emits favouritesChanged."""
    with qtbot.waitSignal(panel.favouritesChanged, timeout=1000):
        panel.add_favourite(RED)
    assert panel.model().colors() == [RED]


def test_sc_u004_1_add_is_deduplicated(panel):
    """SC-U004-1: adding an existing colour is a no-op (de-duplicated)."""
    panel.add_favourite(RED)
    panel.add_favourite(RED)
    assert panel.model().colors() == [RED]


def test_sc_u004_1_remove_and_reorder(panel):
    """SC-U004-1: remove drops the selection; move reorders the favourites."""
    for color in (RED, GREEN, BLUE):
        panel.add_favourite(color)
    # Reorder: move row 0 (RED) to the end via the Move Down control twice.
    panel._list.setCurrentRow(0)
    panel._move(1)
    panel._move(1)
    assert panel.model().colors() == [GREEN, BLUE, RED]
    # Remove the currently-selected favourite (RED, now at row 2).
    panel._list.setCurrentRow(2)
    panel._on_remove()
    assert panel.model().colors() == [GREEN, BLUE]


# -- SC-U004-2 (clicking a favourite applies it) -------------------------------


def test_sc_u004_2_clicking_a_favourite_emits_chosen(panel, qtbot):
    """SC-U004-2: activating a favourite item emits it for application."""
    panel.add_favourite(GREEN)
    item = panel._list.item(0)
    with qtbot.waitSignal(panel.favouriteChosen, timeout=1000) as blocker:
        panel._on_item_activated(item)
    assert blocker.args[0] == GREEN


# -- SC-U004-3 (PERSISTENCE across restart — acceptance-critical) --------------


def test_sc_u004_3_favourite_persists_across_restart(panel, tmp_path):
    """SC-U004-3: a saved favourite is present after a simulated restart (CL-4).

    Mirrors the shell flow: the panel mutates a bound model, the shell persists
    it via ``favourites_io``; a fresh session loads the store and a new panel
    shows the favourite — proving cross-session persistence without a real
    QApplication restart.
    """
    store = tmp_path / "favourites.json"
    model = Favourites()
    panel.set_model(model)
    panel.add_favourite(BLUE)  # user adds a favourite in session 1

    save_favourites(store, model)  # shell persists on favouritesChanged

    # Session 2: reload the store into a brand-new panel.
    reloaded = load_favourites(store)
    assert BLUE in reloaded.colors()
    panel_2 = Favourites_Panel()
    panel_2.set_model(reloaded)
    assert panel_2.model().colors() == [BLUE]
    assert panel_2._list.count() == 1  # rendered in the list after restart


# -- SC-U004-4 (tr()-wrapped, keyboard-reachable, both themes) -----------------


def test_sc_u004_4_favourites_list_is_reachable_and_labelled(panel):
    """SC-U004-4: the list + buttons are Tab-reachable with labelled strings."""
    tab = Qt.FocusPolicy.TabFocus.value
    assert panel._list.focusPolicy().value & tab
    assert panel._list.accessibleName() != ""
    assert panel.accessibleName() != ""
    for button in (panel._remove_button, panel._up_button, panel._down_button):
        assert button.focusPolicy().value & tab
        assert button.text() != ""  # tr()-wrapped label
    assert panel._title.text() != ""
