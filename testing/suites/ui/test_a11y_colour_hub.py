"""Accessibility re-verification for the colour hub (A11Y-COLHUB-1/2/3).

Confirms three accessibility fixes are resolved, in BOTH themes:

* A11Y-COLHUB-1 the hub opens from the keyboard (Menu key / Shift+F10) via the
  canvas ``contextMenuEvent`` seam, with no mouse.
* A11Y-COLHUB-2 the hub sets an explicit tab order across every interactive
  widget (Favourites path → wheel path → Add-to-Favourites), all focusable.
* A11Y-COLHUB-3 the harmony swatches carry accessible names announcing their
  harmony group.

Headless; the autouse ``theme`` fixture runs every test in light and dark.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent

from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
from pixelart_creator.ui.main_window import Main_Window


@pytest.fixture
def hub(qtbot) -> Colour_Hub_Menu:
    widget = Colour_Hub_Menu()
    qtbot.addWidget(widget)
    widget.set_color((40, 90, 220, 255))  # seed the wheel so swatches populate
    return widget


# -- A11Y-COLHUB-1 (keyboard-openable, no mouse) -------------------------------


def test_a11y_colhub_1_keyboard_context_menu_opens_hub(qtbot, monkeypatch):
    """A11Y-COLHUB-1: a keyboard-reason context-menu event opens the hub."""
    win = Main_Window()
    qtbot.addWidget(win)
    view = win.active_tab().view

    opened: list = []
    monkeypatch.setattr(win._colour_hub, "popup_at", lambda pos: opened.append(pos))
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Keyboard, QPoint(4, 4), QPoint(40, 40)
    )
    view.contextMenuEvent(event)
    assert opened, "the keyboard Menu-key request did not open the colour hub"


def test_a11y_colhub_1_mouse_reason_defers_to_press_handler(qtbot, monkeypatch):
    """A11Y-COLHUB-1: a non-keyboard reason does NOT double-open via contextMenuEvent.

    Mouse right-clicks are serviced in ``mousePressEvent``; the context-menu
    override only handles the keyboard reason, so a Mouse-reason event must not
    fire the hub a second time."""
    win = Main_Window()
    qtbot.addWidget(win)
    view = win.active_tab().view
    opened: list = []
    monkeypatch.setattr(win._colour_hub, "popup_at", lambda pos: opened.append(pos))
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, QPoint(4, 4), QPoint(40, 40)
    )
    view.contextMenuEvent(event)
    assert not opened


# -- A11Y-COLHUB-2 (explicit tab order over focusable widgets) -----------------


def test_a11y_colhub_2_tab_order_covers_focusable_widgets(hub):
    """A11Y-COLHUB-2: the intended tab order spans both pick paths + Add, focusable."""
    ordered = [
        *hub._favourites.focus_widgets(),
        *hub._wheel.focus_widgets(),
        hub._add_button,
    ]
    assert len(ordered) >= 5  # favourites path + wheel path + add button
    for widget in ordered:
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus


def _next_target(start, targets):
    """Walk the focus chain from ``start`` to the next widget in ``targets``."""
    ids = {id(w) for w in targets}
    widget = start.nextInFocusChain()
    visited = set()
    while widget is not None and id(widget) not in visited:
        visited.add(id(widget))
        if id(widget) in ids:
            return widget
        widget = widget.nextInFocusChain()
    return None


def test_a11y_colhub_2_explicit_tab_order_walks_the_hub(hub):
    """A11Y-COLHUB-2: the focus chain visits the ordered widgets consecutively.

    ``setTabOrder(a, b)`` makes ``b`` the next tabbable widget after ``a`` (Qt
    interleaves each widget's internal children, so we walk to the next *target*
    rather than assuming a direct ``nextInFocusChain``)."""
    ordered = [
        *hub._favourites.focus_widgets(),
        *hub._wheel.focus_widgets(),
        hub._add_button,
    ]
    for first, second in zip(ordered, ordered[1:]):
        assert _next_target(first, ordered) is second


# -- A11Y-COLHUB-3 (harmony swatches carry accessible names) -------------------


def test_a11y_colhub_3_harmony_swatches_have_group_accessible_names(hub):
    """A11Y-COLHUB-3: each harmony swatch names its group + colour to assistive tech."""
    wheel = hub._wheel
    groups = (
        (wheel._comp, wheel._lbl_comp.text()),
        (wheel._analog, wheel._lbl_analog.text()),
        (wheel._triadic, wheel._lbl_triadic.text()),
        (wheel._split, wheel._lbl_split.text()),
    )
    for swatches, group_label in groups:
        assert group_label != ""
        for swatch in swatches:
            name = swatch.accessibleName()
            assert name != ""
            assert name.startswith(group_label)
