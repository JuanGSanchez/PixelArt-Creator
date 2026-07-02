"""Shade-ramp picker acceptance tests (REQ-P3-UI-007).

One test per acceptance criterion for :class:`Shade_Ramp_Picker`:

* SC-U007-1 the picker shows shade / tint / tone ramps of the base colour
  (computed by ``logic/color_theory``).
* SC-U007-2 activating a ramp step applies it; Add appends a whole ramp.
* SC-U007-3 the picker is tr()-wrapped and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pixelart_creator.logic.color_theory import shade_ramp, tint_ramp, tone_ramp
from pixelart_creator.logic.constants import RAMP_STEP_COUNT
from pixelart_creator.ui.shade_ramp_picker import Shade_Ramp_Picker

BASE = (200, 80, 40, 255)


@pytest.fixture
def picker(qtbot) -> Shade_Ramp_Picker:
    widget = Shade_Ramp_Picker()
    qtbot.addWidget(widget)
    widget.set_base_color(BASE)
    return widget


# -- SC-U007-1 (shows the three ramps from logic) ------------------------------


def test_sc_u007_1_shows_ramps_from_logic(picker):
    """SC-U007-1: each row displays the logic ramp colours, RAMP_STEP_COUNT long."""
    assert [s.color() for s in picker._shade] == shade_ramp(BASE)
    assert [s.color() for s in picker._tint] == tint_ramp(BASE)
    assert [s.color() for s in picker._tone] == tone_ramp(BASE)
    assert len(picker._shade) == RAMP_STEP_COUNT


# -- SC-U007-2 (pick applies a step; Add appends the whole ramp) ---------------


def test_sc_u007_2_picking_a_step_emits_the_colour(picker, qtbot):
    """SC-U007-2: activating a ramp swatch emits that colour for the active swatch."""
    swatch = picker._tint[2]
    with qtbot.waitSignal(picker.colorPicked, timeout=1000) as blocker:
        swatch.click()
    assert blocker.args[0] == swatch.color()


def test_sc_u007_2_add_emits_the_whole_ramp(picker, qtbot):
    """SC-U007-2: Add to Palette emits the entire computed ramp."""
    with qtbot.waitSignal(picker.rampAddRequested, timeout=1000) as blocker:
        picker._add_shade.click()
    assert blocker.args[0] == shade_ramp(BASE)


# -- SC-U007-3 (tr()-wrapped, keyboard-reachable, both themes) -----------------


def test_sc_u007_3_controls_labelled_and_focusable(picker):
    """SC-U007-3: labels are set, swatches + Add buttons take keyboard focus."""
    assert picker.accessibleName() != ""
    assert picker._shade_label.text() != ""
    for swatch in picker._shade:
        assert swatch.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert swatch.accessibleName() != ""
    for button in (picker._add_shade, picker._add_tint, picker._add_tone):
        assert button.text() != ""
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
