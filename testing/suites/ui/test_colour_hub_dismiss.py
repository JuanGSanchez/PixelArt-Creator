"""Regression tests for the fix to the right-click dismissal defect
(dismiss-on-right-click).

One test per acceptance scenario for the dismissal rule: while the colour
hub is visible, a further right-click -- anywhere, including inside the
hub -- or the Menu key / Shift+F10 must dismiss it rather than
re-anchoring it at a new position, and the dismissal rule must consume
exactly ONE gesture, never every subsequent one.

Every test here was proven to FAIL against the unfixed code at commit
f87f6be before being counted as a regression test -- see the QA report for
the quoted, verbatim failure output of each.

SEAM CONTRACT VS. PLATFORM GRAB -- READ BEFORE CHANGING A TEST HERE
(non-negotiable; see also ADR-0066,
`docs/adr/0066-colour-hub-dismissal-is-a-same-press-identity-check.md`,
which records this decision and what it explicitly does not claim):

``QTest.mouseClick`` / ``QTest.keyClick`` deliver a real ``QMouseEvent`` /
``QKeyEvent`` via ``QApplication``'s own ``notify()``/``sendEvent()`` path,
so they DO reach an application-wide ``QObject.eventFilter`` -- confirmed
empirically this session (a filter installed on ``QApplication.instance()``
observed both event types from both helpers). What they structurally CANNOT
do, on ANY platform, offscreen or Windows alike, is engage the native
platform-integration grab that implements a ``Qt.WindowType.Popup``'s own
"outside click auto-closes it" behaviour -- that grab lives beneath Qt's
own widget-level event dispatch entirely. Every test below therefore pins
the SEAM CONTRACT ONLY: "while the hub is visible, this gesture ends with
it not visible, and the seam is not re-entered / re-anchored." None of them
claims anything about the real popup grab on genuine hardware; that
hardware-level evidence is recorded separately, from the maintainer's own
manual, interactive probe -- run outside this automated suite entirely,
against the real desktop platform, never against a hardcoded machine path.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.app import create_app
from testing.suites.ui._ui_helpers import prepare_for_click, real_right_click_pixel


def _settle(app: QApplication, iterations: int = 8) -> None:
    """Flush pending layout/event-loop passes a bounded number of times.

    Mirrors ``test_colour_pick_semantics.py``'s own ``_settle`` helper (same
    suite, same contract) -- the app-wide event filter and the popup's
    ``show()``/``hide()`` calls need a few processed event-loop turns to
    settle under the offscreen platform.
    """
    for _ in range(iterations):
        app.processEvents()


@pytest.fixture
def window(qtbot):
    """A shown ``Main_Window`` with its canvas view pinned for real Qt events.

    Real ``QTest``-delivered events (never a direct ``mousePressEvent``/
    ``keyPressEvent`` call) are the ONLY way to reach the app-wide dismiss
    filter installed on ``QApplication.instance()`` by ``Colour_Hub_Menu`` --
    calling a handler method directly in Python bypasses ``QApplication``'s
    own event dispatch (and therefore every application-wide event filter)
    entirely, which would silently test nothing about this fix.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    win.resize(900, 700)
    _settle(app)
    record = win.active_tab()
    view = record.view
    view.resize(200, 200)
    view.show()
    qtbot.waitExposed(view)
    prepare_for_click(view)
    _settle(app)
    return app, win, view


# -- A right-click ANYWHERE ELSE dismisses the open hub --------------------


def test_right_click_elsewhere_dismisses_hub_and_does_not_reanchor(window):
    """SEAM CONTRACT ONLY (see module docstring).

    Given the hub is open (via a real right-click on the canvas),
    When a further real right-click lands at a DIFFERENT canvas pixel,
    Then the hub ends up not visible, and it is not silently re-anchored to
    the new pixel first (its last on-screen position is unchanged) -- this
    is exactly the right-click dismissal defect this fix addresses: the
    unfixed seam moved the still-visible hub to the new anchor instead of
    dismissing it.
    """
    app, win, view = window
    first = (5, 5)
    second = (40, 40)

    real_right_click_pixel(view, *first)
    _settle(app)
    assert win._colour_hub.isVisible(), "the first right-click did not open the hub"
    anchored_pos = win._colour_hub.pos()

    real_right_click_pixel(view, *second)
    _settle(app)

    assert not win._colour_hub.isVisible(), (
        "hub is still visible after a right-click elsewhere on the canvas -- "
        "the right-click dismissal defect (hub reopened/reanchored instead)"
    )
    assert win._colour_hub.pos() == anchored_pos, (
        "hub was moved to the new pixel before being hidden -- it must never "
        "be re-anchored by the dismissing gesture"
    )


# -- A right-click INSIDE the hub (on the wheel pad) dismisses it too, -----
# with NO dead zone, and picks/commits nothing.


def test_right_click_on_wheel_pad_inside_hub_dismisses_without_picking(window, qtbot):
    """SEAM CONTRACT ONLY (see module docstring).

    Given the hub is open,
    When a right-click lands INSIDE it, on the wheel pad,
    Then the hub ends up not visible, and that press applies no colour
    (``colorApplied``) and commits none (``colorCommitted``) -- maintainer
    ruling 2026-09-06: one uniform dismiss rule, no dead zone inside the
    hub's own controls.
    """
    app, win, view = window
    real_right_click_pixel(view, 5, 5)
    _settle(app)
    hub = win._colour_hub
    assert hub.isVisible(), "the right-click did not open the hub"

    pad = hub._find_wheel_pad()
    assert pad is not None, "could not locate the wheel pad widget to target"

    with (
        qtbot.assertNotEmitted(hub.colorApplied, wait=200),
        qtbot.assertNotEmitted(hub.colorCommitted, wait=200),
    ):
        QTest.mouseClick(pad, Qt.MouseButton.RightButton, pos=pad.rect().center())
        _settle(app)

    assert not hub.isVisible(), (
        "hub is still visible after a right-click ON the wheel pad -- the "
        "'no dead zone' dismissal rule is not honoured"
    )


# -- The Menu key / Shift+F10 toggle the hub the same way ------------------


@pytest.mark.parametrize(
    "key, modifier",
    [
        (Qt.Key.Key_Menu, Qt.KeyboardModifier.NoModifier),
        (Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier),
    ],
    ids=["menu-key", "shift-f10"],
)
def test_dismiss_key_toggles_the_hub_open_and_closed(window, key, modifier):
    """SEAM CONTRACT ONLY (see module docstring).

    Given the hub is open (opened via the keyboard seam,
    ``Canvas_View.contextMenuEvent`` with ``Reason.Keyboard``, the same path
    ``test_a11y_colhub_1_keyboard_context_menu_opens_hub`` already exercises
    for opening),
    When the Menu key or Shift+F10 is pressed,
    Then the hub ends up not visible;
    Given the hub is now closed,
    When the SAME key is pressed again,
    Then the hub opens again, anchored at the viewport centre -- keyboard
    parity with the mouse gesture (A11Y-COLHUB-1), preserved rather than
    diverged.
    """
    app, win, view = window
    hub = win._colour_hub

    centre = view.viewport().rect().center()
    global_centre = view.viewport().mapToGlobal(centre)

    view.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, centre, global_centre)
    )
    _settle(app)
    assert hub.isVisible(), "the keyboard-reason context menu did not open the hub"

    QTest.keyClick(view, key, modifier)
    _settle(app)
    assert (
        not hub.isVisible()
    ), f"the dismiss key ({key!r}, {modifier!r}) did not close the open hub"

    view.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, centre, global_centre)
    )
    _settle(app)
    assert hub.isVisible(), (
        "the same key, pressed again while the hub was closed, failed to "
        "reopen it -- the dismissal rule's 'one gesture' guarantee must "
        "not spill onto the keyboard trigger"
    )
    reopened_pos = hub.pos()
    assert abs(reopened_pos.x() - global_centre.x()) <= 5
    assert abs(reopened_pos.y() - global_centre.y()) <= 5


# -- The dismissal rule consumes exactly ONE gesture ------------------------


def test_dismissal_consumes_exactly_one_gesture_not_every_future_click(window):
    """SEAM CONTRACT ONLY (see module docstring).

    Given the hub is open, and then dismissed by one right-click,
    When a THIRD, separate right-click lands at yet another canvas pixel,
    Then the hub opens again, anchored there -- proving the rule dismisses
    exactly one open hub rather than making the hub permanently harder (or
    impossible) to reopen. A fix that (over-corrects and) never resets its
    dismiss/identity guard would keep the hub closed forever from here on;
    this test fails exactly that way if it regresses.
    """
    app, win, view = window
    hub = win._colour_hub

    first = (5, 5)
    second = (20, 20)
    third = (40, 40)

    real_right_click_pixel(view, *first)
    _settle(app)
    assert hub.isVisible(), "the first right-click did not open the hub at all"

    real_right_click_pixel(view, *second)
    _settle(app)
    assert (
        not hub.isVisible()
    ), "the second, dismissing right-click did not close the hub"

    real_right_click_pixel(view, *third)
    _settle(app)
    assert hub.isVisible(), (
        "a THIRD, separate right-click after a dismissal did not reopen the "
        "hub -- the dismissal rule is consuming more than the one gesture it "
        "is meant to"
    )
    assert win._hub_anchor == third
