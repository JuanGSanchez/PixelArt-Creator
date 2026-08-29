"""Interaction + defensive-branch coverage for the colour hub (S13 gate).

These tests exercise the reachable interaction and defensive branches of
``colour_wheel_widget`` and ``colour_hub_menu`` that the per-criterion acceptance
tests do not otherwise reach — the value slider, harmony-swatch picking, keyboard
saturation nudges / non-arrow keys, drag-move, the zero-radius guards, and the
Favourites remove/move/full-list guards. They keep the ``pixelart_creator.ui``
package over the ≥90 line / ≥80 branch gate (Article IV / S13) without faking
coverage. They map to the same REQ-P3-UI-004/-005/-006 behaviours. Both themes.

Genuinely headless-unreachable branches are deliberately left uncovered and
justified in the QA report (the ``paintEvent`` focus-ring stroke and the
``_on_wheel_picked`` re-entrancy guard, which the pad never triggers during a
programmatic ``set_hsv`` sync).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent

from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.ui.colour_hub_menu import Favourites_Panel
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


@pytest.fixture
def wheel(qtbot) -> Colour_Wheel_Widget:
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)
    widget.set_color(QColor(200, 120, 60))
    widget._wheel.resize(200, 200)
    return widget


def _key(k) -> QKeyEvent:
    return QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)


def _mouse(etype, x, y, button, buttons) -> QMouseEvent:
    pt = QPointF(x, y)
    return QMouseEvent(etype, pt, pt, button, buttons, Qt.KeyboardModifier.NoModifier)


# -- wheel interaction branches ------------------------------------------------


def test_value_slider_changes_brightness(wheel, qtbot):
    """SC-U005-1: the value slider drives brightness and emits a pick."""
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):
        wheel._value_slider.setValue(64)
    assert wheel.current_color().value() == pytest.approx(64, abs=2)


def test_picking_a_harmony_swatch_selects_it(wheel, qtbot):
    """SC-U005: activating a harmony swatch makes it the pending selection.

    Superseded by REQ-CGS-UI-011 (SC-CGS-UI-011-1): promotion now requires a
    left **double**-click, not a single click/``.click()`` — the intent
    (picking a harmony swatch selects that colour) is still valid; only the
    gesture changed.
    """
    target = wheel._comp[0].color()
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):
        qtbot.mouseDClick(wheel._comp[0], Qt.MouseButton.LeftButton)
    assert wheel.current_rgba() == target


def test_wheel_keyboard_saturation_and_ignored_key(wheel):
    """SC-U005-5: Up/Down nudge saturation; a non-arrow key defers to the base."""
    pad = wheel._wheel
    before = pad._sat
    pad.keyPressEvent(_key(Qt.Key.Key_Up))
    assert pad._sat > before
    mid = pad._sat
    pad.keyPressEvent(_key(Qt.Key.Key_Down))
    assert pad._sat < mid
    pad.keyPressEvent(_key(Qt.Key.Key_Left))  # the remaining arrow branch
    # A non-handled key falls through to the base implementation (no crash).
    pad.keyPressEvent(_key(Qt.Key.Key_A))


def test_wheel_drag_and_non_left_press(wheel):
    """A left-drag repicks; a non-left press defers to the base view."""
    pad = wheel._wheel
    pad.mouseMoveEvent(
        _mouse(
            QEvent.Type.MouseMove,
            140.0,
            90.0,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        )
    )
    assert pad._sat > 0
    # A right-button press is not a pick; it must fall through without error.
    pad.mousePressEvent(
        _mouse(
            QEvent.Type.MouseButtonPress,
            10.0,
            10.0,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
        )
    )


def test_zero_radius_pad_is_a_safe_noop(qtbot):
    """The pad guards against a zero radius (paint + pick) without crashing."""
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)
    pad = widget._wheel
    pad.resize(0, 0)
    img = QImage(1, 1, QImage.Format.Format_ARGB32)
    pad.render(img)  # paintEvent radius<=0 guard
    pad.mousePressEvent(
        _mouse(
            QEvent.Type.MouseButtonPress,
            0.0,
            0.0,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )  # _pick_from_pos radius<=0 guard


def test_pad_paints_with_darkening(wheel):
    """A value < 1 exercises the brightness-darkening paint branch."""
    pad = wheel._wheel
    pad.set_hsv(200.0, 0.8, 0.5)  # value 0.5 -> darken overlay drawn
    img = QImage(120, 120, QImage.Format.Format_ARGB32)
    img.fill(0)
    pad.render(img)  # renders without error; darken branch taken


# -- favourites defensive branches ---------------------------------------------


@pytest.fixture
def panel(qtbot) -> Favourites_Panel:
    widget = Favourites_Panel()
    qtbot.addWidget(widget)
    return widget


def test_remove_with_no_selection_is_noop(panel):
    """SC-U004-1: removing with no current row is a safe no-op."""
    panel.add_favourite(RED)
    panel._list.setCurrentRow(-1)
    panel._on_remove()
    assert panel.model().colors() == [RED]


def test_move_out_of_range_is_noop(panel):
    """SC-U004-1: moving the top row up (out of range) is a safe no-op."""
    panel.add_favourite(RED)
    panel.add_favourite(GREEN)
    panel._list.setCurrentRow(0)
    panel._move(-1)  # target -1, out of range
    assert panel.model().colors() == [RED, GREEN]


def test_activate_item_without_colour_data_is_noop(panel, qtbot):
    """SC-U004-2: activating an item lacking colour data emits nothing."""
    from PySide6.QtWidgets import QListWidgetItem

    item = QListWidgetItem("no-data")
    panel._list.addItem(item)
    # No favouriteChosen must fire for a data-less item.
    with qtbot.assertNotEmitted(panel.favouriteChosen):
        panel._on_item_activated(item)


def test_select_color_absent_is_noop(panel):
    """SC-U004: selecting a colour not in the list leaves the row unchanged."""
    panel.add_favourite(RED)
    panel._list.setCurrentRow(0)
    panel._select_color((1, 2, 3, 255))  # absent -> loop completes, no change
    assert panel._list.currentRow() == 0


def test_add_to_full_favourites_is_noop(panel):
    """SC-U004: adding beyond the model cap is a defensive no-op (no crash)."""
    panel.set_model(Favourites(max_size=1))
    panel.add_favourite(RED)
    panel.add_favourite(GREEN)  # over cap -> FavouritesError caught, ignored
    assert panel.model().colors() == [RED]


def test_idle_move_without_button_defers(wheel):
    """A hover-move with no button held defers to the base (no repick)."""
    pad = wheel._wheel
    before = (pad._hue, pad._sat)
    pad.mouseMoveEvent(
        _mouse(
            QEvent.Type.MouseMove,
            140.0,
            90.0,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    assert (pad._hue, pad._sat) == before


# -- i18n retranslate on QEvent.LanguageChange (F5 / NFR-8) --------------------


def test_language_change_retranslates_wheel(wheel):
    """F5: a LanguageChange event re-runs the wheel/pad retranslation."""
    from PySide6.QtWidgets import QApplication

    wheel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    wheel._wheel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    QApplication.processEvents()
    assert wheel._wheel.accessibleName() != ""  # re-set, non-empty


def test_language_change_retranslates_favourites_panel(panel):
    """F5: a LanguageChange event re-runs the Favourites panel retranslation."""
    panel.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert panel._title.text() != ""


def test_language_change_retranslates_hub(qtbot):
    """F5: a LanguageChange event re-runs the hub retranslation."""
    from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu

    hub = Colour_Hub_Menu()
    qtbot.addWidget(hub)
    hub.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert hub.windowTitle() != ""
