"""Characterisation probe: colour-hub pick-COMPLETION signal semantics for a
harmony/shade/tint swatch (measurement task, not an acceptance-criterion
module) — **INVERTED 2026-08-31 for REQ-IS-UI-030 (SC-U030-5),
deliberately, in the same commit as the pick-completion fix.**

**This module originally pinned the BUGGY pre-fix behaviour** (single click
on a harmony swatch silently committed the WHEEL's stale colour; a favourite
click's mechanics description referenced a fused ``itemClicked`` handler that
no longer exists). The fix landed — ``_on_pick_completed`` now commits
the colour of the control that actually COMPLETED the pick, and
``Favourites_Panel``/``_SwatchButton`` each split their single-click and
double-click paths into distinct signals. **This inversion is the licence to invert
this module's assertions to the corrected expectations, and it is bounded to
that: only the two items measured below as genuinely wrong (item 1's commit
colour, and the favourites control's stale mechanics description + signal
counts) were changed. Items 2/3/4 (double-click / Space / Return) already
asserted the CORRECT numbers before this inversion — this session's re-run
confirmed that directly (see the inversion table below) — so only their
"SUSPECTED DEFECT" framing is corrected; their assertions are untouched.**

**Purpose (still accurate).** ``Colour_Hub_Menu._install_pick_completion_watchers``
wires the wheel pad, the value slider and the numeric spin entries to
``_on_pick_completed()`` (called with no argument — the wheel's own current
colour IS theirs). A harmony/shade/tint ``_SwatchButton`` is different: its
single-click ``picked`` signal is wired DIRECTLY to
``Colour_Wheel_Widget.swatchPicked`` -> ``Colour_Hub_Menu._on_pick_completed``
in ``__init__``, called WITH the swatch's own colour as an explicit argument
— so the swatch's colour is committed without ever touching the wheel's own
state (REQ-IS-UI-020/-030). Both the swatch's single click and a Favourites
single click are now deferred by ``QApplication.doubleClickInterval()``
before they emit (``_SwatchButton._single_click_timer`` /
``Favourites_Panel._click_timer``) — the same click/double-click
disambiguation pattern in both places — so a test observing the single-click
leg must wait out that timer instead of asserting immediately after the
synthesized click.

**Findings, all RE-measured this session (Python 3.13.13, PySide6 6.11.1,
pytest-qt 4.5.0, QT_QPA_PLATFORM=offscreen) against the FIXED tree — this
IS the inversion table:**

* SINGLE left click on a harmony swatch: ``colorApplied`` still does **not**
  fire; ``colorCommitted`` now fires once, WAITED OUT past the deferred
  single-click timer, carrying the SWATCH's OWN colour — never the wheel's
  (unchanged) colour. **INVERTED** — this is exactly REQ-IS-UI-030's fix,
  confirmed at the signal level (SC-U030-1).
* SINGLE left click on a Favourites entry: ``colorApplied`` — 0 emissions
  (unchanged, was previously miscategorised as a "control" firing 1); the
  wheel's own colour is left alone. ``colorCommitted`` — 1 emission, WAITED
  OUT past the deferred single-click timer, carrying the favourite's own
  colour (GREEN). **INVERTED** — SC-U019-1/-2/-5.
* DOUBLE left click / keyboard Space / keyboard Return on a harmony swatch:
  ``colorApplied`` fires once with the swatch's own colour;
  ``colorCommitted`` never fires. **NOT inverted — re-confirmed correct.**
  This session's re-run shows this is the intended "adopt, paint nothing"
  shape (REQ-IS-UI-022, SC-U022-2/-3), not a gap: the original docstring's
  "SUSPECTED DEFECT" framing was wrong about the verdict even though its
  raw numbers were already right; only that framing is corrected here.
* Wheel-pad drag-release (control): both legs still fire with the correct
  colour in every case, exactly as before — REQ-IS-UI-021 is the one
  requirement this whole task must not touch, and this control proves it
  didn't.

Every test in this module also runs against both the light and the dark
theme via the autouse, parametrised ``theme`` fixture in ``conftest.py``
(the signal semantics measured here are theme-independent, but the fixture
is autouse for the whole suite so both themes are exercised regardless).
Headless (``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

from typing import Any, List

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.colour_hub_menu import Colour_Hub_Menu

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)


class _Recorder:
    """Records, in order, every value a Qt signal emits (a minimal spy)."""

    def __init__(self, signal: Any) -> None:
        self.values: List[Any] = []
        signal.connect(self.values.append)

    @property
    def count(self) -> int:
        return len(self.values)


@pytest.fixture
def hub(qtbot) -> Colour_Hub_Menu:
    """A shown, exposed, active hub seeded with RED.

    Shown (not just constructed) so the swatch buttons and the Favourites
    list can genuinely take and report keyboard focus under the offscreen
    platform — the same pattern used by
    ``test_colour_wheel_tetradic_harmony.py``'s ``wheel`` fixture for real
    click/focus assertions.
    """
    widget = Colour_Hub_Menu()
    qtbot.addWidget(widget)
    widget.set_color(RED)
    widget.show()
    qtbot.waitExposed(widget)
    widget.activateWindow()
    qtbot.waitActive(widget)
    return widget


# -- item 1: single left click on a harmony swatch -----------------------------


def test_single_left_click_on_harmony_swatch_characterisation(hub, qtbot):
    """INVERTED (was SUSPECTED DEFECT) — pins the CORRECTED, post-fix
    behaviour (REQ-IS-UI-020/-030).

    Measured (``qtbot.mouseClick``, one press + release, on the complementary
    swatch, then WAITED OUT past ``QApplication.doubleClickInterval()`` via
    ``qtbot.waitSignal`` — the single click is now deferred so a following
    double click can cancel it, ``_SwatchButton._single_click_timer``): the
    deferred timer fires ``_emit_picked`` -> ``picked`` ->
    ``Colour_Wheel_Widget.swatchPicked`` -> ``Colour_Hub_Menu.
    _on_pick_completed(color=<swatch colour>)`` — called WITH the swatch's
    own colour as an explicit argument, never falling back to
    ``self._wheel.current_rgba()``.

    Result:
      * ``colorApplied`` — 0 emissions. The swatch's colour is still never
        applied or previewed on a single click (REQ-IS-UI-020 leaves the
        wheel alone, unchanged from before this inversion).
      * ``colorCommitted`` — 1 emission, carrying the SWATCH's OWN colour
        (its complementary) — NOT the wheel's current colour (RED,
        unchanged). This is the exact inversion of the pre-fix finding: the
        WRONG colour above is now the RIGHT one.
    """
    swatch = hub._wheel._comp[0]
    swatch_colour = swatch.color()
    wheel_colour_before = hub.current_rgba()
    assert swatch_colour != wheel_colour_before  # the pick would be a real change

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    with qtbot.waitSignal(hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)

    assert applied.count == 0  # measured: never applied on a single click
    assert committed.count == 1
    assert committed.values[0] == swatch_colour  # the SWATCH's own colour...
    assert committed.values[0] != wheel_colour_before  # ...not the wheel's stale one
    assert hub.current_rgba() == wheel_colour_before  # the wheel itself is untouched


# -- item 2: double left click on the same swatch -------------------------------


def test_double_left_click_on_harmony_swatch_characterisation(hub, qtbot):
    """RE-CONFIRMED CORRECT (framing corrected 2026-08-31; assertions
    UNCHANGED by this inversion — this test already measured the right
    numbers before the fix, per REQ-IS-UI-022's "adopt, paint nothing").

    Measured (``qtbot.mouseDClick``, one full double-click gesture — press,
    release, ``MouseButtonDblClick``, release — on the complementary swatch):
    ``_SwatchButton.mouseDoubleClickEvent`` intercepts the dbl-click event,
    stops the deferred single-click timer (so the first half of the gesture
    never separately fires ``picked``) and emits ``activated`` directly,
    WITHOUT delegating to ``QAbstractButton.mouseDoubleClickEvent`` — so the
    button's own ``clicked`` signal is never observed as firing during the
    whole gesture in this measurement (0 emissions across the full
    sequence, not 1 as a naive press/release/dblclick/release reading would
    suggest).

    Result, for one full ``mouseDClick`` call:
      * ``colorApplied`` — exactly 1 emission, carrying the swatch's OWN
        colour. This is the "adopt into the wheel" leg (SC-U022-2).
      * ``colorCommitted`` — 0 emissions. Leg 2 (the undoable committed
        paint) deliberately never runs for a double-click adopt — that is
        the whole point of REQ-IS-UI-022 ("adopts and paints nothing"), not
        a gap this task closes. The pre-inversion docstring here called
        this a "SUSPECTED DEFECT, second and independent finding"; it was
        not — only that verdict is corrected, the numbers below are
        untouched.
    """
    swatch = hub._wheel._comp[0]
    swatch_colour = swatch.color()
    wheel_colour_before = hub.current_rgba()
    assert swatch_colour != wheel_colour_before

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.mouseDClick(swatch, Qt.MouseButton.LeftButton)

    assert applied.count == 1
    assert applied.values[0] == swatch_colour  # correct colour on this leg
    assert committed.count == 0  # measured gap: leg 2 never runs


# -- item 3: the keyboard path (Space, then separately Enter/Return) -----------


def test_keyboard_space_on_harmony_swatch_characterisation(hub, qtbot):
    """RE-CONFIRMED CORRECT (framing corrected 2026-08-31; assertions
    UNCHANGED by this inversion) — same intended shape as the
    double-click case above, via Space (REQ-IS-UI-022, SC-U022-3).

    Measured (swatch focused, ``qtbot.keyClick(swatch, Qt.Key.Key_Space)``):
    ``_SwatchButton.keyPressEvent`` intercepts Space and emits ``activated``
    directly (the same "adopt" path as the double click), and returns
    WITHOUT calling ``super().keyPressEvent()`` — so ``QToolButton``'s normal
    Space -> ``clicked()`` synthesis never runs either.

    Result:
      * ``colorApplied`` — 1 emission, the swatch's own colour (correct).
      * ``colorCommitted`` — 0 emissions. Intended ("adopt, paint nothing"),
        not a gap — see the double-click test's docstring above.
    """
    swatch = hub._wheel._comp[0]
    swatch.setFocus()
    swatch_colour = swatch.color()
    wheel_colour_before = hub.current_rgba()
    assert swatch_colour != wheel_colour_before

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.keyClick(swatch, Qt.Key.Key_Space)

    assert applied.count == 1
    assert applied.values[0] == swatch_colour
    assert committed.count == 0


def test_keyboard_return_on_harmony_swatch_characterisation(hub, qtbot):
    """RE-CONFIRMED CORRECT (framing corrected 2026-08-31; assertions
    UNCHANGED by this inversion) — same intended shape as the Space
    case above, via Return (REQ-IS-UI-022, SC-U022-3).

    Measured (swatch focused, ``qtbot.keyClick(swatch, Qt.Key.Key_Return)``):
    identical mechanism and identical result to the Space case above —
    ``_SwatchButton.keyPressEvent`` also intercepts Return (and Enter) and
    emits ``activated`` directly, bypassing ``clicked()`` entirely.

    Result:
      * ``colorApplied`` — 1 emission, the swatch's own colour (correct).
      * ``colorCommitted`` — 0 emissions. Intended, same as Space.
    """
    swatch = hub._wheel._comp[0]
    swatch.setFocus()
    swatch_colour = swatch.color()
    wheel_colour_before = hub.current_rgba()
    assert swatch_colour != wheel_colour_before

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.keyClick(swatch, Qt.Key.Key_Return)

    assert applied.count == 1
    assert applied.values[0] == swatch_colour
    assert committed.count == 0


# -- item 4: controls — the paths proven correct ------------------------------


def test_control_favourite_click_characterisation(hub, qtbot):
    """INVERTED (was mislabelled CONTROL) — a left click on a Favourites
    entry is now a PAINT-only leg-2 commit (REQ-IS-UI-019), not a combined
    apply+commit.

    **Why this test changes, not just its framing, unlike items 2-4 above:**
    the pre-inversion version of this test described the mechanics as
    ``QListWidget.itemClicked`` -> ``_on_item_activated`` -> a single fused
    handler that set the wheel AND emitted both signals — that handler no
    longer exists. The fix split ``Favourites_Panel`` into
    ``_on_item_clicked`` (deferred single click -> ``favouritePicked`` ->
    ``Colour_Hub_Menu._on_favourite_picked``, paint-only) and
    ``_on_item_activated`` (double click / Enter -> ``favouriteActivated``,
    adopt-only) — see ``colour_hub_menu.py``'s module docstring, 2026-08-31
    amendment. A single click now defers by
    ``QApplication.doubleClickInterval()`` before it emits at all (the same
    click/double-click disambiguation ``_SwatchButton`` uses), so this test
    must wait out that timer instead of asserting immediately.

    Measured, single click, waited out past the deferred timer:
      * ``colorApplied`` — 0 emissions. The wheel is deliberately left alone
        (SC-U019-2) — this is the OPPOSITE of the pre-inversion measurement
        of 1.
      * ``colorCommitted`` — 1 emission, carrying the favourite's own colour
        (GREEN) — unchanged in VALUE from before, but now reached through
        the single-click-only path rather than a fused handler that also
        touched the wheel.

    This is still the control the harmony-swatch single-click test above
    corroborates against: the same deferred-timer + explicit-colour-argument
    shape, now correct on both surfaces.
    """
    hub.favourites_model().add(GREEN)
    hub._favourites.set_model(hub.favourites_model())
    item = hub._favourites._list.item(0)
    rect = hub._favourites._list.visualItemRect(item)
    wheel_colour_before = hub.current_rgba()
    assert wheel_colour_before != GREEN

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    with qtbot.waitSignal(hub.colorCommitted, timeout=2000):
        qtbot.mouseClick(
            hub._favourites._list.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            rect.center(),
        )

    assert applied.count == 0
    assert committed.count == 1
    assert committed.values[0] == GREEN
    assert hub.current_rgba() == wheel_colour_before  # the wheel itself is untouched


def test_control_wheel_drag_release_characterisation(hub, qtbot):
    """CONTROL — a second known-good path, corroborating the instrument.

    A left-button press on the wheel pad, one move sample, then a release:
    the press and the move each drive ``_WheelPad._pick_from_pos`` ->
    ``hueSatPicked`` -> ``Colour_Wheel_Widget._emit_change`` ->
    ``colorPicked`` -> ``Colour_Hub_Menu.colorApplied`` (the live-preview
    stream, SC-U006-10); the release is caught by ``Colour_Hub_Menu.
    eventFilter`` -> ``_on_pick_completed`` (leg 2, one discrete commit).

    Measured, for exactly one press + one move + one release:
      * ``colorApplied`` — 2 emissions (one per sample: press, then move).
      * ``colorCommitted`` — 1 emission, matching the LAST ``colorApplied``
        value (the final dragged colour) and matching
        ``hub.current_rgba()`` at the end.

    Correct shape: many live previews, one discrete commit, the commit
    matching the final applied colour — this pad is the ONE surface where
    ``colorApplied`` and ``colorCommitted`` are expected to agree, because
    the pad always sets the wheel itself (REQ-IS-UI-021, unchanged by this
    task). The swatch/favourite paths above deliberately do NOT match this
    shape post-fix either: their single click never applies at all
    (``colorApplied`` stays at 0), by design (SC-U019-2/SC-U020-2) — that
    absence of a match is correct there, not a gap, unlike the pre-fix
    finding this module used to pin.
    """
    pad = hub._wheel._wheel
    pad.resize(200, 200)
    qtbot.waitExposed(pad)

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)

    center = pad.rect().center()
    target = QPoint(center.x() + 40, center.y() - 10)
    qtbot.mousePress(pad, Qt.MouseButton.LeftButton, pos=center)
    qtbot.mouseMove(pad, pos=target)
    qtbot.mouseRelease(pad, Qt.MouseButton.LeftButton, pos=target)

    assert applied.count == 2  # exactly the press-sample and the move-sample
    assert committed.count == 1
    assert committed.values[0] == applied.values[-1]  # commit matches final apply
    assert committed.values[0] == hub.current_rgba()
