"""Colour-hub apply + active-swatch acceptance tests (REQ-P3-UI-006, S4).

One test per acceptance criterion for the pick -> active-swatch path:

* SC-U006-1 ACTIVE SWATCH (acceptance-critical): after a wheel pick the active
  swatch equals the picked colour.
* SC-U006-2 after picking a favourite the active swatch equals that favourite.
* SC-U006-3 the next left-click paints the newly-picked active colour (S2).
* SC-U006-4 saving to Favourites is an explicit action, distinct from applying.

The active swatch is the shell's active paint colour (``Main_Window`` tool
state); a pick sets it without touching the undo stack (T17). Every test runs in
both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest

from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
from pixelart_creator.ui.main_window import Main_Window

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)


@pytest.fixture
def hub(qtbot) -> Colour_Hub_Menu:
    """A standalone colour hub seeded with a non-black colour."""
    widget = Colour_Hub_Menu()
    qtbot.addWidget(widget)
    widget.set_color(RED)
    return widget


@pytest.fixture
def window(qtbot) -> Main_Window:
    """A main window whose colour hub is wired to the active-swatch handler."""
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# -- SC-U006-1 (wheel pick -> active swatch, acceptance-critical) --------------


def test_sc_u006_1_wheel_pick_sets_active_swatch(window):
    """SC-U006-1: a wheel pick applies immediately to the shell active swatch."""
    hub = window._colour_hub
    hub.set_color(RED)
    # Drive a pick through the numeric entry (a deterministic wheel pick path);
    # this emits colorPicked -> colorApplied -> the shell active-swatch handler.
    hub._wheel._spin_g.setValue(200)
    picked = hub.current_rgba()
    assert window._active_color == picked  # active swatch equals the pick
    stack = window.active_tab().stack
    assert stack.count() == 0  # a pick is tool state, never an undo entry (T17)


def test_sc_u006_1_hub_emits_applied_on_wheel_pick(hub, qtbot):
    """SC-U006-1: the hub re-emits the wheel pick as ``colorApplied``."""
    with qtbot.waitSignal(hub.colorApplied, timeout=1000) as blocker:
        hub._wheel._spin_b.setValue(180)
    assert blocker.args[0] == hub.current_rgba()


# -- SC-U006-2 (favourite pick -> active swatch) -------------------------------


def test_sc_u006_2_favourite_pick_sets_active_swatch(window):
    """SC-U006-2: picking a favourite applies that favourite to the swatch."""
    hub = window._colour_hub
    hub.favourites_model().add(GREEN)
    hub._favourites.set_model(hub.favourites_model())
    item = hub._favourites._list.item(0)
    hub._favourites._on_item_activated(item)
    assert window._active_color == GREEN


# -- SC-U006-3 (next left-click paints the newly-picked colour, S2) ------------


def test_sc_u006_3_next_left_click_paints_applied_colour(window):
    """SC-U006-3: after a pick, the next left-click paints the active colour."""
    from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

    hub = window._colour_hub
    hub.set_color(RED)
    hub._wheel._spin_g.setValue(160)  # apply a pick to the active swatch
    applied = window._active_color

    view = window.active_tab().view
    prepare_for_click(view)
    assert view.active_color() == applied  # the pick propagated to the view
    click_pixel(view, 3, 3)
    buffer = window.active_tab().scene.active_buffer()
    assert buffer.get_pixel(3, 3) == applied


# -- SC-U006-4 (saving to Favourites is explicit, distinct from applying) ------


def test_sc_u006_4_pick_does_not_grow_favourites(hub):
    """SC-U006-4: a wheel pick applies but does NOT silently add a favourite."""
    before = hub.favourites_model().colors()
    hub._wheel._spin_r.setValue(10)  # a pick (apply)
    assert hub.favourites_model().colors() == before  # unchanged


def test_sc_u006_4_add_to_favourites_is_explicit(hub):
    """SC-U006-4: the explicit add button stores the current colour."""
    before = len(hub.favourites_model())
    hub._on_add_current()  # the explicit "Add to Favourites" action
    assert len(hub.favourites_model()) == before + 1
    assert hub.current_rgba() in hub.favourites_model().colors()
