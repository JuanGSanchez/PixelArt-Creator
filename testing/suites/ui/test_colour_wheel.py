"""Colour wheel + live harmonies acceptance tests (REQ-P3-UI-005, S3b/F9).

One test per acceptance criterion for :class:`Colour_Wheel_Widget`:

* SC-U005-1 picking on the wheel selects a colour and sets the pending pick.
* SC-U005-2 LIVE HARMONIES: every wheel move recomputes the harmony swatches
  by **calling** ``logic.color_theory`` (acceptance-critical).
* SC-U005-3 the harmony swatches reflect the correct angles.
* SC-U005-4 shade/tint ramp swatches update with the selection.
* SC-U005-5 the wheel + entries are keyboard-reachable, carry accessible names,
  and render in both themes (a11y).

The numeric RGB/HSV entries are the accessible, Tab-reachable alternative to the
2-D wheel; tests here also exercise that keyboard path (item 1, keyboard path).
Every test runs twice — light + dark — via the autouse ``theme`` fixture in
``conftest.py``. Headless (``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent

from pixelart_creator.logic import color_theory
from pixelart_creator.ui import colour_wheel_widget as cw_module
from pixelart_creator.ui.colour_wheel_widget import Colour_Wheel_Widget

_BASE = QColor(200, 120, 60)  # a saturated, non-black seed (value > 0)


@pytest.fixture
def wheel(qtbot) -> Colour_Wheel_Widget:
    """A wheel seeded with a saturated colour and a resized pad for picking."""
    widget = Colour_Wheel_Widget()
    qtbot.addWidget(widget)
    widget.set_color(_BASE)
    widget._wheel.resize(200, 200)  # deterministic pad geometry (no show needed)
    return widget


def _press(pad, x: float, y: float) -> QMouseEvent:
    pt = QPointF(x, y)
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pt,
        pt,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


# -- SC-U005-1 -----------------------------------------------------------------


def test_sc_u005_1_wheel_pick_selects_colour(wheel, qtbot):
    """SC-U005-1: a click on the wheel picks a colour and emits ``colorPicked``."""
    before = wheel.current_rgba()
    pad = wheel._wheel
    # Point (150, 100) on a 200x200 pad: right of centre -> hue ~0, saturation ~0.5.
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):
        pad.mousePressEvent(_press(pad, 150.0, 100.0))
    after = wheel.current_rgba()
    assert after != before  # the pick changed the pending selection
    assert wheel.current_color().value() > 0  # value preserved -> not black


# -- SC-U005-2 (acceptance-critical: live harmony on every move) ---------------


def test_sc_u005_2_live_harmony_updates_on_every_move(wheel, qtbot, monkeypatch):
    """SC-U005-2: every wheel move recomputes harmonies via ``color_theory``.

    Spies on the module-level ``complementary`` reference the widget calls, then
    drives several distinct wheel moves and asserts each move recomputed (called
    the logic) and the rendered swatch matches the freshly-computed value.
    """
    calls: list = []
    real = color_theory.complementary
    monkeypatch.setattr(
        cw_module, "complementary", lambda c: calls.append(c) or real(c)
    )

    pad = wheel._wheel
    baseline = len(calls)
    # Three distinct picks (different hue radius/angle) = three moves.
    for x, y in ((150.0, 100.0), (100.0, 40.0), (60.0, 150.0)):
        pad.mousePressEvent(_press(pad, x, y))
        current = wheel.current_rgba()
        # The rendered complementary swatch reflects the just-picked colour.
        assert wheel._comp[0].color() == real(current)
    assert len(calls) - baseline >= 3  # recomputed on every move (via logic)


# -- SC-U005-3 (angle correctness reflected in swatches) -----------------------


def test_sc_u005_3_harmony_swatches_reflect_correct_angles(wheel):
    """SC-U005-3: the swatches equal the logic harmony sets (correct angles)."""
    rgba = wheel.current_rgba()
    assert wheel._comp[0].color() == color_theory.complementary(rgba)
    assert tuple(s.color() for s in wheel._analog) == color_theory.analogous(rgba)
    assert tuple(s.color() for s in wheel._triadic) == color_theory.triadic(rgba)
    assert tuple(s.color() for s in wheel._split) == color_theory.split_complementary(
        rgba
    )


# -- SC-U005-4 (ramps update with selection) -----------------------------------


def test_sc_u005_4_ramp_swatches_update_with_selection(wheel):
    """SC-U005-4: shade/tint ramp swatches equal the logic ramps for the pick."""
    rgba = wheel.current_rgba()
    assert [s.color() for s in wheel._shades] == color_theory.shade_ramp(rgba)
    assert [s.color() for s in wheel._tints] == color_theory.tint_ramp(rgba)


# -- SC-U005-5 (a11y: keyboard-reachable + accessible names, both themes) ------


def test_sc_u005_5_wheel_and_entries_are_keyboard_reachable(wheel):
    """SC-U005-5: wheel + numeric entries are Tab-reachable with accessible names."""
    tab = Qt.FocusPolicy.TabFocus.value
    pad = wheel._wheel
    assert pad.focusPolicy().value & tab  # the 2-D pad is Tab-reachable
    assert pad.accessibleName() != ""
    # The description tells assistive-tech users how to drive the wheel without a
    # mouse (arrow keys / numeric fields) — the keyboard-usability affordance.
    description = pad.accessibleDescription().lower()
    assert "key" in description or "mouse" in description
    for spin in (
        wheel._spin_r,
        wheel._spin_g,
        wheel._spin_b,
        wheel._spin_h,
        wheel._spin_s,
        wheel._spin_v,
    ):
        assert spin.focusPolicy().value & tab  # numeric entries Tab-reachable
        assert spin.accessibleName() != ""  # named for assistive tech


def test_sc_u005_5_swatches_are_keyboard_reachable_and_named(wheel):
    """SC-U005-5: every harmony/ramp swatch is a Tab-reachable, named button."""
    tab = Qt.FocusPolicy.TabFocus.value
    groups = (
        wheel._comp,
        wheel._analog,
        wheel._triadic,
        wheel._split,
        wheel._shades,
        wheel._tints,
    )
    for group in groups:
        for swatch in group:
            assert swatch.focusPolicy().value & tab
            assert swatch.accessibleName() != ""


# -- keyboard path: numeric entries edit the SAME state (item 1) ---------------


def test_rgb_entries_edit_the_selection_state(wheel):
    """The RGB spin entries drive the same selection state as the wheel."""
    with_r, with_g, with_b = 40, 90, 220
    wheel._spin_r.setValue(with_r)
    wheel._spin_g.setValue(with_g)
    wheel._spin_b.setValue(with_b)
    r, g, b, _a = wheel.current_rgba()
    assert (r, g, b) == (with_r, with_g, with_b)
    # Harmonies recompute from the entry-driven colour too.
    assert wheel._comp[0].color() == color_theory.complementary(wheel.current_rgba())


def test_hsv_entries_edit_the_selection_state(wheel):
    """The HSV spin entries drive the same selection state (hue path)."""
    wheel._spin_h.setValue(120)  # green hue
    wheel._spin_s.setValue(255)
    wheel._spin_v.setValue(255)
    color = wheel.current_color()
    assert color.green() >= color.red() and color.green() >= color.blue()


def test_wheel_arrow_keys_move_selection(wheel, qtbot):
    """The wheel pad is usable by keyboard: an arrow key moves the selection."""
    pad = wheel._wheel
    pad.setFocus()
    before = wheel.current_rgba()
    with qtbot.waitSignal(wheel.colorPicked, timeout=1000):
        pad.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier
            )
        )
    assert wheel.current_rgba() != before  # hue advanced via keyboard


# -- perf sanity: live recompute is prompt (informational, generous bound) -----


def test_live_harmony_recompute_is_prompt(wheel):
    """A batch of live recomputes stays well under a generous bound (perf sanity).

    Not a frame-budget gate (that is AGT-10's harness); this only flags gross
    lag in the qtbot timing so QA can route a perf check if it ever regresses.
    """
    start = time.perf_counter()
    for value in range(60, 250, 3):  # ~63 recomputes driven through the entry path
        wheel._spin_r.setValue(value)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"live harmony recompute batch took {elapsed:.3f}s"
