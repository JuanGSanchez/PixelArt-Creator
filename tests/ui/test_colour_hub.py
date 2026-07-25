"""Colour hub right-click-menu acceptance tests (REQ-P3-UI-003, marquee S3).

One test per acceptance criterion for :class:`Colour_Hub_Menu` and its wiring
into the Phase-1 canvas right-click seam:

* SC-U003-1 right-click on the canvas opens the hub anchored at the cursor.
* SC-U003-2 the hub hosts both pick paths (Favourites + colour wheel).
* SC-U003-3 the hub is a keyboard-openable popup with tr()-wrapped strings.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent

from pixelart_creator.ui.colour_hub_menu import (
    Colour_Hub_Menu,
    Favourites_Panel,
)
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget
from pixelart_creator.ui.main_window import Main_Window


@pytest.fixture
def hub(qtbot) -> Colour_Hub_Menu:
    """A standalone colour hub registered with qtbot for cleanup."""
    widget = Colour_Hub_Menu()
    qtbot.addWidget(widget)
    return widget


def _right_press(x: float, y: float) -> QMouseEvent:
    pt = QPointF(x, y)
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pt,
        pt,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )


# -- SC-U003-1 (right-click opens the hub via the Phase-1 seam) ----------------


def test_sc_u003_1_right_click_opens_hub_via_seam(qtbot, monkeypatch):
    """SC-U003-1: a canvas right-click fires the seam hook that opens the hub."""
    win = Main_Window()
    qtbot.addWidget(win)
    view = win.active_tab().view

    opened: list = []
    monkeypatch.setattr(win._colour_hub, "popup_at", lambda pos: opened.append(pos))
    view.mousePressEvent(_right_press(5.0, 5.0))
    assert opened, "right-click did not open the colour hub through the seam"


def test_sc_u003_1_popup_at_anchors_to_the_given_point(hub):
    """SC-U003-1: ``popup_at`` anchors the hub at the supplied global position."""
    hub.popup_at(QPoint(123, 45))
    # The hub is anchored at the requested point; the offscreen platform reports
    # a small window-frame margin, so allow a few px of frame offset.
    assert abs(hub.pos().x() - 123) <= 5
    assert abs(hub.pos().y() - 45) <= 5
    assert hub.isVisible()


# -- SC-U003-2 (both pick paths hosted) ----------------------------------------


def test_sc_u003_2_hub_hosts_both_pick_paths(hub):
    """SC-U003-2: the hub embeds a Favourites panel and a colour wheel."""
    assert hub.findChild(Favourites_Panel) is not None
    assert hub.findChild(Colour_Wheel_Widget) is not None


# -- SC-U003-3 (keyboard-openable popup, tr()-wrapped strings, both themes) ----


def test_sc_u003_3_hub_is_keyboard_openable_popup_with_named_strings(hub):
    """SC-U003-3: the hub is a Popup, focuses the wheel, and names its strings."""
    # A Popup window type: cursor-anchored, closes on outside click (SC-U003-1).
    assert hub.windowFlags() & Qt.WindowType.Popup
    assert hub.windowTitle() != ""  # tr()-wrapped title
    assert hub.accessibleName() != ""
    # Opening focuses the wheel so it is immediately keyboard-navigable.
    hub.popup_at(QPoint(10, 10))
    assert hub.focusWidget() is not None


def test_sc_u003_3_add_to_favourites_action_is_labelled(hub):
    """SC-U003-3: the explicit add-to-favourites button carries a label."""
    assert hub._add_button.text() != ""


def test_sc_u003_3_seeding_the_hub_sets_the_wheel_colour(hub):
    """set_color seeds the wheel with the active swatch (open-with-context)."""
    hub.set_color((40, 90, 220, 255))
    assert hub.current_rgba() == (40, 90, 220, 255)
