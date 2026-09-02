"""Acceptance tests for the corrected colour-hub pick semantics.

One test per named Gherkin scenario in the input-scheme spec
under REQ-IS-UI-019, -020, -021 (no-change control), -022, -023, -030 (the
defect FIX), and the REQ-IS-UI-028 regression scenarios this task's slice of
that requirement owns: SC-R-26, SC-R-27, SC-R-28, SC-R-29, SC-R-30, SC-R-34.

**Two observation levels, chosen per scenario's own wording, never guessed:**

* **Signal level** (``Colour_Hub_Menu``/``Colour_Wheel_Widget`` built in
  isolation, no ``Main_Window``) for a scenario phrased in terms of
  ``colorApplied``/``colorCommitted`` emissions or the wheel's own displayed
  colour (e.g. SC-U019-4/-5, SC-U021-1/-4, SC-U022-2/-3, SC-U030-1/-3/-4,
  SC-R-29, SC-R-30).
* **Pixel level**, through a real ``Main_Window`` built by
  ``pixelart_creator.ui.app.create_app`` (the same construction
  ``test_regression_field_defects_20260824.py`` uses), for a scenario that
  literally says "pixel", "painted colour" or "anchor pixel holds"
  (SC-U019-1/-2/-3, SC-U020-1/-2/-3, SC-U021-2/-3, SC-U022-1/-4, SC-U023-1/-2/
  -3, SC-U030-2, SC-R-26, SC-R-28, SC-R-34).

**CONFIRMED PRODUCT DEFECT, found while writing this module (measured this
session, not inferred from reading source) — reported, not fixed here
(P9/C2):**

``Main_Window._on_hub_color_committed`` (``ui/main_window.py:3891-3896``,
outside the fix's write scope of ``colour_hub_menu.py``/``colour_wheel_widget.py``
and outside this module's own write scope) receives ``Colour_Hub_Menu``'s
``colorCommitted`` signal WITH the completing control's own colour as its
``color`` argument — the fix at the widget level is correct, proven by
:func:`test_sc_u030_1_harmony_swatch_commits_its_own_colour_not_wheels_stale`
below — but the handler **never reads that argument**. It calls
``self._hub_anchor_view.run_tool_at(x, y)`` with no colour parameter at all,
and ``run_tool_at`` paints with ``Canvas_View._active_color`` — which is only
ever updated by ``colorApplied`` (leg 1). A Favourites/harmony-swatch single
click is, by design (SC-U019-2/SC-U020-2), a PAINT-only leg-2 commit that
never fires ``colorApplied`` — so the active colour it deliberately leaves
alone is exactly the (stale) colour ``run_tool_at`` ends up painting with,
instead of the picked control's own colour ``colorCommitted`` carried.

Measured directly (throwaway probe, ``D:/tmp/agt06-t26/probe5.py``, discarded
after use): wheel seeded RED (230,30,30,255); complementary swatch reads
(30,230,230,255); a real single click on that swatch, waited out through its
deferred single-click timer, commits (30,230,230,255) on the
``Colour_Hub_Menu.colorCommitted`` signal (correct, matches SC-U030-1) —
but the buffer pixel at the hub anchor ends up **(230,30,30,255)**, the stale
active colour, not the swatch's own colour. The wheel pad is UNAFFECTED
(SC-R-34/SC-U021-2/-3/SC-U023-3 below all pass): its drag keeps
``colorApplied`` in lock-step with every sample, so ``_active_color`` is
never stale by the time it commits.

This means, at the true pixel level, REQ-IS-UI-019 (SC-U019-1), REQ-IS-UI-020
(SC-U020-1, SC-U020-3 for all seven groups) and REQ-IS-UI-023 (SC-U023-1/-2)
do NOT hold end-to-end, and REQ-IS-UI-030's own SC-U030-2 ("a harmony swatch
can now paint its own colour") does not hold either — despite the isolated
widget-level fix (SC-U030-1/-3/-4) being correct. The tests below assert the
literal, spec-correct expectation in every case (never weakened to match the
observed defect, per the verified-testing hard rule) — the ones enumerated
above are therefore EXPECTED TO FAIL on this tree, and their failure IS the
report. Routed to the UI layer (owner of ``ui/main_window.py``) via the
orchestrator; not fixed here (P9).

Every test in this module also runs against both the light and the dark
theme via the autouse, parametrised ``theme`` fixture in ``conftest.py``.
Headless (``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

from typing import Any, List

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixelart_creator.data.favourites_io import load_favourites, save_favourites
from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.ui.app import create_app
from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu
from pixelart_creator.ui.tools import (
    DitherTool,
    EraserTool,
    LassoTool,
    MagicWandTool,
    PencilTool,
    PickerTool,
    RectSelectTool,
)
from testing.suites.ui._ui_helpers import real_right_click_pixel

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 60, 230, 255)
BLACK = (0, 0, 0, 255)


class _Recorder:
    """Records, in order, every value a Qt signal emits (a minimal spy)."""

    def __init__(self, signal: Any) -> None:
        self.values: List[Any] = []
        signal.connect(self.values.append)

    @property
    def count(self) -> int:
        return len(self.values)


def _settle(app: QApplication, iterations: int = 8) -> None:
    """Flush pending layout/timer-driven passes a bounded number of times."""
    for _ in range(iterations):
        app.processEvents()


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def hub(qtbot) -> Colour_Hub_Menu:
    """A shown, exposed, active hub seeded with RED (isolated, no document)."""
    widget = Colour_Hub_Menu()
    qtbot.addWidget(widget)
    widget.set_color(RED)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    return widget


def _favourite_item(win_or_hub, colour):
    """Find the Favourites ``QListWidgetItem`` carrying ``colour``."""
    hub_widget = (
        win_or_hub._colour_hub if hasattr(win_or_hub, "_colour_hub") else win_or_hub
    )
    listw = hub_widget._favourites._list
    return next(
        listw.item(i)
        for i in range(listw.count())
        if listw.item(i).data(Qt.ItemDataRole.UserRole) == colour
    )


def _open_hub_with_tool(app, win, tool_cls, x: int, y: int):
    """Set ``tool_cls`` active, open the hub anchored at buffer pixel (x, y)."""
    record = win.active_tab()
    win._active_tool_id = tool_cls.tool_id
    record.view.set_tool(win._tools[tool_cls.tool_id])
    win._open_colour_hub(x, y)
    _settle(app)
    return record


# --------------------------------------------------------------------------- #
# REQ-IS-UI-019 — single click on a Favourites entry paints                   #
# --------------------------------------------------------------------------- #


def test_sc_u019_1_single_click_paints_favourites_colour_at_anchor(qtbot):
    """SC-U019-1: pixel level.

    CONFIRMED DEFECT (module docstring) — expected to fail on this tree:
    the anchor pixel ends up the stale active colour (BLACK), not RED.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, PencilTool, 7, 9)
    before_count = record.stack.count()

    win._colour_hub.favourites_model().add(RED)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, RED)

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        win._colour_hub._favourites._on_item_clicked(item)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(7, 9) == RED
    assert record.stack.count() - before_count == 1


def test_sc_u019_2_single_click_does_not_change_active_colour(qtbot):
    """SC-U019-2: the active colour and the wheel's display stay BLACK."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    assert win._active_color == BLACK
    _open_hub_with_tool(app, win, PencilTool, 7, 9)

    win._colour_hub.favourites_model().add(RED)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, RED)

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        win._colour_hub._favourites._on_item_clicked(item)
    _settle(app)

    assert win._active_color == BLACK
    assert win._colour_hub.current_rgba() == BLACK


def test_sc_u019_3_non_consuming_tool_paints_nothing(qtbot):
    """SC-U019-3: select_rect active -> a favourite click paints no pixel,
    pushes no undo entry."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, RectSelectTool, 7, 9)
    before_count = record.stack.count()
    before_pixel = record.scene.active_buffer().get_pixel(7, 9)

    win._colour_hub.favourites_model().add(RED)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, RED)
    win._colour_hub._favourites._on_item_clicked(item)
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(7, 9) == before_pixel
    assert record.stack.count() == before_count


def test_sc_u019_4_single_and_double_click_are_distinct_handlers(qtbot):
    """SC-U019-4: a double click fires colorApplied once with RED,
    colorCommitted zero times, and paints no pixel."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, PencilTool, 7, 9)
    before_count = record.stack.count()
    before_pixel = record.scene.active_buffer().get_pixel(7, 9)

    win._colour_hub.favourites_model().add(RED)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, RED)

    applied = _Recorder(win._colour_hub.colorApplied)
    committed = _Recorder(win._colour_hub.colorCommitted)
    win._colour_hub._favourites._on_item_activated(item)  # double-click path
    _settle(app)

    assert applied.count == 1
    assert applied.values[0] == RED
    assert committed.count == 0
    assert record.scene.active_buffer().get_pixel(7, 9) == before_pixel
    assert record.stack.count() == before_count


def test_sc_u019_5_single_click_fires_only_the_commit_leg(hub, qtbot):
    """SC-U019-5: colorCommitted fires exactly once with RED,
    colorApplied fires zero times (signal level)."""
    hub.favourites_model().add(GREEN)
    hub._favourites.set_model(hub.favourites_model())
    item = _favourite_item(hub, GREEN)

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    with qtbot.waitSignal(hub.colorCommitted, timeout=2000):
        hub._favourites._on_item_clicked(item)

    assert committed.count == 1
    assert committed.values[0] == GREEN
    assert applied.count == 0


# --------------------------------------------------------------------------- #
# REQ-IS-UI-020 — single click on a theory swatch paints                      #
# --------------------------------------------------------------------------- #


def test_sc_u020_1_single_click_paints_swatchs_own_colour(qtbot):
    """SC-U020-1: pixel level.

    CONFIRMED DEFECT (module docstring) — expected to fail on this tree:
    the anchor pixel ends up the stale active colour (RED), not the
    complementary swatch's own colour.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(BLUE)
    record = _open_hub_with_tool(app, win, PencilTool, 3, 4)

    swatch = win._colour_hub._wheel._comp[0]
    swatch_colour = swatch.color()
    assert swatch_colour != BLUE

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(3, 4) == swatch_colour
    assert record.scene.active_buffer().get_pixel(3, 4) != BLUE


def test_sc_u020_2_single_click_does_not_change_active_colour(qtbot):
    """SC-U020-2: the active colour and the wheel's display stay BLUE."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(BLUE)
    _open_hub_with_tool(app, win, PencilTool, 3, 4)

    swatch = win._colour_hub._wheel._comp[0]
    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)
    _settle(app)

    assert win._active_color == BLUE
    assert win._colour_hub.current_rgba() == BLUE


_HARMONY_GROUPS = [
    "complementary",
    "analogous",
    "triadic",
    "tetradic",
    "split-complementary",
    "shades",
    "tints",
]

_GROUP_ATTR = {
    "complementary": "_comp",
    "analogous": "_analog",
    "triadic": "_triadic",
    "tetradic": "_tetradic",
    "split-complementary": "_split",
    "shades": "_shades",
    "tints": "_tints",
}

#: The swatch INDEX exercised per group. ``shade_ramp``/``tint_ramp`` (SC-
#: L003-1/-2, ``logic/color_theory.py``) both document "the first entry is
#: the base colour" -- index 0 of ``_shades``/``_tints`` therefore equals the
#: wheel's own seeded colour by construction, which would make this test
#: coincidentally pass even under the confirmed defect (the stale active
#: colour and the "swatch's own colour" would be the same value for the
#: WRONG reason). Caught empirically while writing this module: a first
#: draft using index 0 uniformly reported shades/tints as passing where
#: every other group correctly failed. Index 1 is a real, non-degenerate
#: ramp step for both.
_GROUP_INDEX = {"shades": 1, "tints": 1}


@pytest.mark.parametrize("group", _HARMONY_GROUPS)
def test_sc_u020_3_every_harmony_group_behaves_the_same(qtbot, group):
    """SC-U020-3: pixel level, every one of the seven harmony groups.

    CONFIRMED DEFECT (module docstring) — expected to fail on this tree for
    every group (none of the seven is the wheel pad).
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(BLUE)
    record = _open_hub_with_tool(app, win, PencilTool, 3, 4)

    index = _GROUP_INDEX.get(group, 0)
    swatch = getattr(win._colour_hub._wheel, _GROUP_ATTR[group])[index]
    swatch_colour = swatch.color()
    assert swatch_colour != BLUE, (
        f"fixture invalid for group {group!r} index {index}: swatch colour "
        "coincides with the seeded active colour, which would make this "
        "test pass for the wrong reason"
    )

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(3, 4) == swatch_colour


# --------------------------------------------------------------------------- #
# REQ-IS-UI-021 — the wheel pad is not a swatch, no-change control            #
# --------------------------------------------------------------------------- #


def test_sc_u021_1_wheel_pad_drag_applies_live(hub, qtbot):
    """SC-U021-1: the active colour (the wheel's own display) follows the
    cursor sample by sample during a drag."""
    pad = hub._wheel._wheel
    pad.resize(200, 200)
    qtbot.waitExposed(pad)

    applied = _Recorder(hub.colorApplied)
    qtbot.mousePress(pad, Qt.MouseButton.LeftButton, pos=QPoint(30, 170))
    qtbot.mouseMove(pad, pos=QPoint(60, 140))
    qtbot.mouseMove(pad, pos=QPoint(90, 110))
    qtbot.mouseMove(pad, pos=QPoint(120, 80))
    qtbot.mouseMove(pad, pos=QPoint(150, 50))
    qtbot.mouseRelease(pad, Qt.MouseButton.LeftButton, pos=QPoint(150, 50))

    assert applied.count == 5  # press + 4 move samples
    assert applied.values[-1] == hub.current_rgba()


def test_sc_u021_2_wheel_pad_commits_exactly_once_on_release(qtbot):
    """SC-U021-2: pixel level -- exactly one undo entry, pixel is the
    release-point colour (PASSES -- the wheel pad is unaffected)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(RED)
    record = _open_hub_with_tool(app, win, PencilTool, 5, 5)
    before_count = record.stack.count()

    pad = win._colour_hub._wheel._wheel
    pad.resize(120, 120)
    pad.show()
    qtbot.waitExposed(pad)

    applied: List[Any] = []
    win._colour_hub.colorApplied.connect(applied.append)
    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(60, 60)
    )
    for point in (QPoint(70, 50), QPoint(80, 40), QPoint(90, 30)):
        QTest.mouseMove(pad, point)
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(90, 30)
    )
    _settle(app)

    assert record.stack.count() - before_count == 1
    assert record.scene.active_buffer().get_pixel(5, 5) == applied[-1]


def test_sc_u021_3_single_click_on_wheel_pad_applies_and_commits(qtbot):
    """SC-U021-3: a plain click on the pad applies AND commits, as today."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(RED)
    record = _open_hub_with_tool(app, win, PencilTool, 5, 5)

    pad = win._colour_hub._wheel._wheel
    pad.resize(120, 120)
    pad.show()
    qtbot.waitExposed(pad)

    applied: List[Any] = []
    win._colour_hub.colorApplied.connect(applied.append)
    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        QTest.mouseClick(
            pad,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(80, 40),
        )
    _settle(app)

    assert win._active_color == applied[-1]
    assert record.scene.active_buffer().get_pixel(5, 5) == applied[-1]


def test_sc_u021_4_no_double_click_gesture_on_wheel_pad(hub, qtbot):
    """SC-U021-4: a double click on the pad behaves as two ordinary picks --
    no adopt-without-commit path was introduced."""
    pad = hub._wheel._wheel
    pad.resize(200, 200)
    qtbot.waitExposed(pad)

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    point = QPoint(150, 50)
    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    QTest.mouseDClick(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )

    # Every press is an ordinary apply-sample; every release is an ordinary
    # commit -- no distinct "adopt, paint nothing" branch exists on the pad.
    assert applied.count >= 2
    assert committed.count == applied.count == committed.count or committed.count >= 2


# --------------------------------------------------------------------------- #
# REQ-IS-UI-022 — double click / Space / Return adopt, paint nothing          #
# --------------------------------------------------------------------------- #


def test_sc_u022_1_double_click_favourite_adopts_without_painting(qtbot):
    """SC-U022-1: pixel level -- active colour becomes RED, pixel and undo
    depth are unchanged."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, PencilTool, 7, 9)
    before_count = record.stack.count()
    before_pixel = record.scene.active_buffer().get_pixel(7, 9)

    win._colour_hub.favourites_model().add(RED)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, RED)
    win._colour_hub._favourites._on_item_activated(item)
    _settle(app)

    assert win._active_color == RED
    assert record.scene.active_buffer().get_pixel(7, 9) == before_pixel
    assert record.stack.count() == before_count


def test_sc_u022_2_double_click_harmony_swatch_adopts_without_painting(hub, qtbot):
    """SC-U022-2: signal level -- colorApplied once with the swatch's own
    colour, colorCommitted zero times, active colour becomes that colour."""
    swatch = hub._wheel._comp[0]
    swatch_colour = swatch.color()
    wheel_before = hub.current_rgba()
    assert swatch_colour != wheel_before

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.mouseDClick(swatch, Qt.MouseButton.LeftButton)

    assert applied.count == 1
    assert applied.values[0] == swatch_colour
    assert committed.count == 0
    assert hub.current_rgba() == swatch_colour


@pytest.mark.parametrize("key", [Qt.Key.Key_Space, Qt.Key.Key_Return])
def test_sc_u022_3_space_and_return_behave_as_the_double_click(hub, qtbot, key):
    """SC-U022-3: Space, and separately Return, on a focused swatch adopt
    without painting."""
    swatch = hub._wheel._comp[0]
    swatch.setFocus()
    swatch_colour = swatch.color()

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.keyClick(swatch, key)

    assert applied.count == 1
    assert applied.values[0] == swatch_colour
    assert committed.count == 0
    assert hub.current_rgba() == swatch_colour


def test_sc_u022_4_adopting_raises_the_colour_feedback_square(qtbot):
    """SC-U022-4: double-clicking a favourite raises the cursor feedback
    square filled with that colour."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = win.active_tab()
    assert record.feedback_overlay is not None
    assert record.feedback_overlay.isVisible() is False

    win._open_colour_hub(4, 4)
    win._colour_hub.favourites_model().add(GREEN)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, GREEN)
    win._colour_hub._favourites._on_item_activated(item)
    _settle(app)

    assert record.feedback_overlay.isVisible() is True


# --------------------------------------------------------------------------- #
# REQ-IS-UI-023 — a committed pick paints what was clicked                    #
# --------------------------------------------------------------------------- #


def test_sc_u023_1_swatch_click_paints_swatchs_colour_not_wheels(qtbot):
    """SC-U023-1: pixel level.

    CONFIRMED DEFECT (module docstring) -- expected to fail on this tree.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(BLUE)
    record = _open_hub_with_tool(app, win, PencilTool, 3, 4)

    swatch = win._colour_hub._wheel._comp[0]
    swatch_colour = swatch.color()

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)
    _settle(app)

    painted = record.scene.active_buffer().get_pixel(3, 4)
    assert painted == swatch_colour
    assert painted != BLUE


def test_sc_u023_2_favourite_that_differs_from_the_wheel_paints_its_own(qtbot):
    """SC-U023-2: pixel level.

    CONFIRMED DEFECT (module docstring) -- expected to fail on this tree.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(BLUE)
    record = _open_hub_with_tool(app, win, PencilTool, 3, 4)

    win._colour_hub.favourites_model().add(GREEN)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, GREEN)

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        win._colour_hub._favourites._on_item_clicked(item)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(3, 4) == GREEN


def test_sc_u023_3_wheel_pad_still_paints_its_own_release_colour(qtbot):
    """SC-U023-3: pixel level (PASSES -- the wheel pad is unaffected)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._set_active_color(RED)
    record = _open_hub_with_tool(app, win, PencilTool, 5, 5)

    pad = win._colour_hub._wheel._wheel
    pad.resize(120, 120)
    pad.show()
    qtbot.waitExposed(pad)

    applied: List[Any] = []
    win._colour_hub.colorApplied.connect(applied.append)
    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(60, 60)
    )
    QTest.mouseMove(pad, QPoint(90, 30))
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(90, 30)
    )
    _settle(app)

    release_colour = applied[-1]
    assert record.scene.active_buffer().get_pixel(5, 5) == release_colour


# --------------------------------------------------------------------------- #
# REQ-IS-UI-030 — the DEFECT FIX itself                                       #
# --------------------------------------------------------------------------- #


def test_sc_u030_1_harmony_swatch_commits_its_own_colour_not_wheels_stale(qtbot):
    """SC-U030-1: signal level, exact Gherkin colours.

    PASSES -- proves the widget-level fix (``_on_pick_completed``
    committing the completing control's OWN colour) is correct in isolation.
    The gap this module reports is downstream of this signal, in
    ``ui/main_window.py``, not here.
    """
    hub = Colour_Hub_Menu()
    qtbot.addWidget(hub)
    hub.set_color((230, 30, 30, 255))
    hub.show()
    qtbot.waitExposed(hub)

    swatch = hub._wheel._comp[0]
    assert swatch.color() == (30, 230, 230, 255)

    committed = _Recorder(hub.colorCommitted)
    with qtbot.waitSignal(hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)

    assert committed.count == 1
    assert committed.values[0] == (30, 230, 230, 255)
    assert committed.values[0] != (230, 30, 30, 255)


def test_sc_u030_2_harmony_swatch_can_now_paint_its_own_colour(qtbot):
    """SC-U030-2: pixel level -- "the anchor pixel holds that known colour".

    CONFIRMED DEFECT (module docstring) -- expected to fail on this tree.
    This is the sharpest expression of the finding: the fix's own stated
    goal ("a harmony swatch can now paint its own colour") does not hold at
    the pixel a user actually sees painted.
    """
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, PencilTool, 6, 6)

    swatch = win._colour_hub._wheel._comp[0]
    swatch_colour = swatch.color()

    with qtbot.waitSignal(win._colour_hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)
    _settle(app)

    assert record.scene.active_buffer().get_pixel(6, 6) == swatch_colour


def test_sc_u030_3_the_fix_does_not_make_the_double_click_paint(qtbot):
    """SC-U030-3: signal level, exact Gherkin colours."""
    hub = Colour_Hub_Menu()
    qtbot.addWidget(hub)
    hub.set_color((230, 30, 30, 255))
    hub.show()
    qtbot.waitExposed(hub)

    swatch = hub._wheel._comp[0]
    assert swatch.color() == (30, 230, 230, 255)

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.mouseDClick(swatch, Qt.MouseButton.LeftButton)

    assert committed.count == 0
    assert applied.count == 1
    assert applied.values[0] == (30, 230, 230, 255)


def test_sc_u030_4_the_fix_does_not_regress_the_two_controls(hub, qtbot):
    """SC-U030-4: signal level -- a Favourites click and a wheel-pad
    drag-release still commit their own colours correctly."""
    hub.favourites_model().add(GREEN)
    hub._favourites.set_model(hub.favourites_model())
    item = _favourite_item(hub, GREEN)

    fav_committed = _Recorder(hub.colorCommitted)
    with qtbot.waitSignal(hub.colorCommitted, timeout=2000):
        hub._favourites._on_item_clicked(item)
    assert fav_committed.count == 1
    assert fav_committed.values[0] == GREEN

    pad = hub._wheel._wheel
    pad.resize(200, 200)
    qtbot.waitExposed(pad)
    applied = _Recorder(hub.colorApplied)
    pad_committed = _Recorder(hub.colorCommitted)
    qtbot.mousePress(pad, Qt.MouseButton.LeftButton, pos=QPoint(30, 170))
    qtbot.mouseMove(pad, pos=QPoint(150, 50))
    qtbot.mouseRelease(pad, Qt.MouseButton.LeftButton, pos=QPoint(150, 50))

    assert pad_committed.count == 1
    assert pad_committed.values[0] == applied.values[-1]


# SC-U030-5 ("the characterisation suite is INVERTED by this change,
# deliberately") is satisfied procedurally, not by a runtime assertion here:
# job 2 of this task rewrote
# testing/suites/ui/test_colour_hub_pick_semantics_characterisation.py's
# assertions to the corrected expectations, and step 7 (RUN THE SUITE) of
# the QA report re-runs that module and records it green. A dedicated
# assertion in THIS module re-testing that file's own content would be
# circular; the concrete verification is the characterisation module's own
# green run, reported alongside this one.


# --------------------------------------------------------------------------- #
# REQ-IS-UI-028 (this task's slice) -- SC-R-26, -27, -28, -29, -30, -34       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tool_cls, expected_occurs",
    [
        (PencilTool, True),
        (EraserTool, False),
        (PickerTool, False),
        (DitherTool, False),
        (RectSelectTool, False),
        (LassoTool, False),
        (MagicWandTool, False),
    ],
)
def test_sc_r_26_hub_tool_gate_unchanged(qtbot, tool_cls, expected_occurs):
    """SC-R-26: the leg-2 tool gate fires for pencil and none of the six
    named non-consuming tools (a fresh window per case -- no state bleed
    across tool ids)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    record = _open_hub_with_tool(app, win, tool_cls, 2, 2)
    before_count = record.stack.count()

    target = (11, 22, 33, 255)
    win._colour_hub.favourites_model().add(target)
    win._colour_hub._favourites.set_model(win._colour_hub.favourites_model())
    item = _favourite_item(win, target)
    win._colour_hub._favourites._on_item_clicked(item)
    qtbot.wait(QApplication.doubleClickInterval() + 100)
    _settle(app)

    ran = record.stack.count() - before_count == 1
    assert ran is expected_occurs


def test_sc_r_27_favourites_management_unchanged(qtbot, tmp_path):
    """SC-R-27: dedup, FAVOURITES_MAX cap refusal, Move Up/Down/Remove, and
    persistence across a save + reload -- all through a scratch copy under
    ``tmp_path`` (never a real user artifact)."""
    from pixelart_creator.logic.constants import FAVOURITES_MAX
    from pixelart_creator.logic.favourites import FavouritesError

    fav = Favourites()
    fav.add(RED)
    fav.add(RED)  # duplicate: no-op
    assert list(fav.colors()) == [RED]

    fav.add(GREEN)
    fav.add(BLUE)
    assert list(fav.colors()) == [RED, GREEN, BLUE]

    fav.move(0, 2)
    assert list(fav.colors()) == [GREEN, BLUE, RED]

    fav.remove(GREEN)
    assert list(fav.colors()) == [BLUE, RED]

    full = Favourites(max_size=2)
    full.add((1, 1, 1, 255))
    full.add((2, 2, 2, 255))
    with pytest.raises(FavouritesError):
        full.add((3, 3, 3, 255))  # beyond max_size, refused (not silently accepted)
    assert len(full) == 2
    assert FAVOURITES_MAX >= 64

    path = tmp_path / "favourites.json"
    save_favourites(path, fav)
    reloaded = load_favourites(path)
    assert list(reloaded.colors()) == list(fav.colors())


def test_sc_r_28_hub_still_anchors_on_the_buffer_pixel(qtbot):
    """SC-R-28: a non-unit zoom + a scrolled viewport; a real right-click and
    a keyboard-reason context-menu request at the same buffer pixel anchor
    the hub at that same pixel."""
    import math

    app, win = create_app([])
    qtbot.addWidget(win)
    win.resize(900, 700)
    _settle(app)

    record = win.active_tab()
    view = record.view
    view.resize(200, 200)
    view.show()
    qtbot.waitExposed(view)

    target = (5, 5)
    view.set_zoom(2.0)
    view.centerOn(QPointF(target[0] + 0.5, target[1] + 0.5))
    _settle(app)
    assert (
        view.horizontalScrollBar().value() != 0 or view.verticalScrollBar().value() != 0
    )

    real_right_click_pixel(view, *target)
    _settle(app)
    assert win._hub_anchor == target

    win._colour_hub.hide()
    _settle(app)

    view_point = view.viewport().rect().center()
    scene_point = view.mapToScene(view_point)
    expected_px = (math.floor(scene_point.x()), math.floor(scene_point.y()))
    assert expected_px == target  # the view is centred on it; sanity check

    global_pos = view.viewport().mapToGlobal(view_point)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, view_point, global_pos)
    view.contextMenuEvent(event)
    _settle(app)

    assert win._hub_anchor == target


def test_sc_r_29_keyboard_promotion_of_focused_swatch_still_works(hub, qtbot):
    """SC-R-29: Space, and separately Enter, on a focused swatch promote its
    colour as the active colour."""
    for key in (Qt.Key.Key_Space, Qt.Key.Key_Enter):
        hub.set_color(RED)
        swatch = hub._wheel._comp[0]
        swatch.setFocus()
        swatch_colour = swatch.color()
        applied = _Recorder(hub.colorApplied)
        qtbot.keyClick(swatch, key)
        assert applied.count == 1
        assert applied.values[0] == swatch_colour
        assert hub.current_rgba() == swatch_colour


def test_sc_r_30_harmony_groups_recompute_live(hub, qtbot):
    """SC-R-30: moving across the wheel pad updates the harmony groups on
    every move (measured on the complementary group; representative -- all
    seven groups are recomputed together by the same
    ``_update_harmonies`` call)."""
    pad = hub._wheel._wheel
    pad.resize(200, 200)
    qtbot.waitExposed(pad)

    comp_before = hub._wheel._comp[0].color()
    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(20, 20)
    )
    comp_after_press = hub._wheel._comp[0].color()
    QTest.mouseMove(pad, QPoint(180, 40))
    comp_after_move = hub._wheel._comp[0].color()
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(180, 40)
    )

    assert comp_after_press != comp_before
    assert comp_after_move != comp_after_press


def test_sc_r_34_wheel_pad_still_applies_live_and_commits_on_release(qtbot):
    """SC-R-34: pixel level -- live apply during the drag, exactly one
    commit on release carrying the release colour, and the anchor pixel
    holds it. The wheel pad is one of the two controls this whole task
    proves unchanged (PASSES)."""
    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    # NOT BLACK: BLACK is value=0 in HSV, and the wheel pad only ever picks
    # hue/saturation (the value slider is a separate control) -- starting
    # from BLACK, every pad sample stays BLACK regardless of where it is
    # clicked, which would make "the drag actually moved off the seed"
    # trivially true for the wrong reason (caught empirically: a first
    # draft using BLACK as the seed left win._active_color == BLACK after
    # the whole drag, looking like a defect that was actually a fixture
    # mistake -- see the RED seed used by every other wheel-pad test above).
    win._set_active_color(RED)
    record = _open_hub_with_tool(app, win, PencilTool, 5, 5)
    before_count = record.stack.count()

    pad = win._colour_hub._wheel._wheel
    pad.resize(120, 120)
    pad.show()
    qtbot.waitExposed(pad)

    applied: List[Any] = []
    committed = _Recorder(win._colour_hub.colorCommitted)
    win._colour_hub.colorApplied.connect(applied.append)

    QTest.mousePress(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(60, 60)
    )
    for point in (QPoint(70, 50), QPoint(80, 40), QPoint(90, 30), QPoint(100, 20)):
        QTest.mouseMove(pad, point)
    QTest.mouseRelease(
        pad, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(100, 20)
    )
    _settle(app)

    assert win._active_color != RED  # the drag actually moved off the seed
    assert applied[0] != applied[-1]  # it followed the cursor, not a single jump
    assert committed.count == 1
    assert committed.values[0] == applied[-1]
    assert record.stack.count() - before_count == 1
    assert record.scene.active_buffer().get_pixel(5, 5) == applied[-1]
