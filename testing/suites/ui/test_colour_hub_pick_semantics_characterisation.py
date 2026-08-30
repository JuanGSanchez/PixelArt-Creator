"""Characterisation probe: colour-hub pick-COMPLETION signal semantics for a
harmony/shade/tint swatch (measurement task, not an acceptance-criterion
module).

**Purpose.** ``Colour_Hub_Menu._install_pick_completion_watchers`` connects
every ``QAbstractButton`` found under the wheel — including each harmony/
shade/tint ``_SwatchButton`` — to ``_on_pick_completed``, which always emits
``colorCommitted`` with ``self._wheel.current_rgba()`` (the WHEEL's current
colour). A ``_SwatchButton``, however, only transfers its OWN colour into the
wheel via its private ``picked`` signal, emitted from ``_on_clicked()``,
which is called ONLY by the overridden ``mouseDoubleClickEvent`` (left
button) and by ``keyPressEvent`` (Space/Return/Enter) — never by a plain
single click, which the class docstring says is deliberately reserved for
focusing the swatch, not promoting it.

The tests below DRIVE the real widgets (``qtbot.mouseClick`` /
``qtbot.mouseDClick`` / ``qtbot.keyClick``, real ``QAbstractButton.clicked``
signal machinery under the offscreen Qt platform) and record every
``colorApplied`` / ``colorCommitted`` emission with a plain signal recorder —
nothing here is inferred from reading the source. Two control tests (a
Favourites click, a wheel-pad drag-release) are included FIRST in intent
(documented last for narrative flow) precisely so a known-good result is
established: a probe that cannot show a correct signal cannot be trusted to
report an incorrect one honestly.

**Findings, all measured this session (Python 3.13.13, PySide6 6.11.1,
pytest-qt 4.5.0, QT_QPA_PLATFORM=offscreen):**

* SINGLE left click on a harmony swatch: ``colorApplied`` does **not** fire;
  ``colorCommitted`` fires once, with the WHEEL's stale colour — never the
  swatch's own colour. **SUSPECTED DEFECT** — this is the inference the
  measurement task set out to check, and it is confirmed: a single click
  would silently commit an undoable paint stroke (``colorCommitted`` -> the
  shell's ``run_tool_at``, per this module's docstring) in the WRONG colour,
  while giving no visible preview at all.
* DOUBLE left click / keyboard Space / keyboard Return on a harmony swatch:
  ``colorApplied`` fires once with the swatch's own (correct) colour, but
  ``colorCommitted`` never fires at all. **SUSPECTED DEFECT, a second and
  independent finding** — the "adopt" gesture applies the colour but never
  commits an undoable stroke, contrary to this module's own docstring, which
  frames "each harmony/shade/tint swatch button: ``clicked``" as one atomic,
  already-completed pick.
* Favourites click / wheel-pad drag-release (controls): both legs fire with
  the correct colour in every case — proving the instrument observes a
  correct result before either suspected defect above is trusted.

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
    """SUSPECTED DEFECT — pins TODAY's actual (believed-wrong) behaviour.

    Measured (``qtbot.mouseClick``, one press + release, on the complementary
    swatch): the swatch's inherited ``QAbstractButton.clicked`` fires from the
    plain press/release pair — ``_SwatchButton`` never overrides
    ``mousePressEvent``/``mouseReleaseEvent``, only ``mouseDoubleClickEvent``.
    That ``clicked`` is wired, indiscriminately, to
    ``Colour_Hub_Menu._on_pick_completed``.

    Result:
      * ``colorApplied`` — 0 emissions. The swatch's colour is never applied
        or previewed on a single click.
      * ``colorCommitted`` — 1 emission, carrying the WHEEL's current colour
        (RED, unchanged) — NOT the swatch's own colour (its complementary).

    This is expected to be inverted once the pending semantic change ships
    (single click paints in the swatch's OWN colour); today it is wrong.
    """
    swatch = hub._wheel._comp[0]
    swatch_colour = swatch.color()
    wheel_colour_before = hub.current_rgba()
    assert swatch_colour != wheel_colour_before  # the pick would be a real change

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.mouseClick(swatch, Qt.MouseButton.LeftButton)

    assert applied.count == 0  # measured: never applied on a single click
    assert committed.count == 1
    assert committed.values[0] == wheel_colour_before  # the WHEEL's stale colour...
    assert committed.values[0] != swatch_colour  # ...not the swatch's own colour


# -- item 2: double left click on the same swatch -------------------------------


def test_double_left_click_on_harmony_swatch_characterisation(hub, qtbot):
    """SUSPECTED DEFECT (second, independent finding) — pins TODAY's behaviour.

    Measured (``qtbot.mouseDClick``, one full double-click gesture — press,
    release, ``MouseButtonDblClick``, release — on the complementary swatch):
    ``_SwatchButton.mouseDoubleClickEvent`` intercepts the dbl-click event and
    calls ``_on_clicked()`` directly, WITHOUT delegating to
    ``QAbstractButton.mouseDoubleClickEvent`` — so the button's own
    ``clicked`` signal is never observed as firing during the whole gesture
    in this measurement (0 emissions across the full sequence, not 1 as a
    naive press/release/dblclick/release reading would suggest).

    Result, for one full ``mouseDClick`` call:
      * ``colorApplied`` — exactly 1 emission, carrying the swatch's OWN
        colour. This leg is correct: this is the documented "promotion
        reserved for the double-click gesture" path.
      * ``colorCommitted`` — 0 emissions. Leg 2 (the undoable committed
        stroke, per this module's docstring) never runs for a double-click
        adopt, even though ``_install_pick_completion_watchers`` documents
        "each harmony/shade/tint swatch button: ``clicked`` — already one
        atomic gesture" as its completion signal.
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
    """SUSPECTED DEFECT — same shape as the double-click finding, via Space.

    Measured (swatch focused, ``qtbot.keyClick(swatch, Qt.Key.Key_Space)``):
    ``_SwatchButton.keyPressEvent`` intercepts Space, calls ``_on_clicked()``
    directly (the same "adopt" path as the double click), and returns
    WITHOUT calling ``super().keyPressEvent()`` — so ``QToolButton``'s normal
    Space -> ``clicked()`` synthesis never runs either.

    Result:
      * ``colorApplied`` — 1 emission, the swatch's own colour (correct).
      * ``colorCommitted`` — 0 emissions (measured gap, same as double-click).
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
    """SUSPECTED DEFECT — same shape as the double-click finding, via Return.

    Measured (swatch focused, ``qtbot.keyClick(swatch, Qt.Key.Key_Return)``):
    identical mechanism and identical result to the Space case above —
    ``_SwatchButton.keyPressEvent`` also intercepts Return (and Enter) and
    calls ``_on_clicked()`` directly, bypassing ``clicked()`` entirely.

    Result:
      * ``colorApplied`` — 1 emission, the swatch's own colour (correct).
      * ``colorCommitted`` — 0 emissions (measured gap, same as Space).
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


# -- item 4: controls — the paths believed to be correct ------------------------


def test_control_favourite_click_characterisation(hub, qtbot):
    """CONTROL — a known-good path; the instrument must observe it correctly.

    A left click on a Favourites entry drives ``QListWidget.itemClicked`` ->
    ``Favourites_Panel._on_item_activated`` -> ``Colour_Hub_Menu.
    _on_favourite_chosen``, which explicitly sets the wheel to the
    favourite's colour BEFORE emitting both signals itself (not via
    ``_on_pick_completed``).

    Measured: ``colorApplied`` and ``colorCommitted`` each fire exactly once,
    BOTH carrying the favourite's own colour (GREEN) — never the wheel's
    prior colour (RED). This is the correct shape the harmony-swatch
    single-click path above is missing: proof the recorder + qtbot mouse
    driving can observe a right answer, so the swatch findings above are
    real findings, not a broken test.
    """
    hub.favourites_model().add(GREEN)
    hub._favourites.set_model(hub.favourites_model())
    item = hub._favourites._list.item(0)
    rect = hub._favourites._list.visualItemRect(item)
    wheel_colour_before = hub.current_rgba()
    assert wheel_colour_before != GREEN

    applied = _Recorder(hub.colorApplied)
    committed = _Recorder(hub.colorCommitted)
    qtbot.mouseClick(
        hub._favourites._list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        rect.center(),
    )

    assert applied.count == 1
    assert applied.values[0] == GREEN
    assert committed.count == 1
    assert committed.values[0] == GREEN


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
    matching the final applied colour — unlike either harmony-swatch path
    above, where the committed colour (when it fires at all) never matches
    what was actually applied.
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
