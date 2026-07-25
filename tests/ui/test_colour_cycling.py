"""Colour-cycling controls acceptance tests (REQ-P3-UI-012).

One test per acceptance criterion for :class:`Colour_Cycling_Panel` (the preview
is non-destructive; committing is a separate undoable action):

* SC-U012-1 selecting a range and playing cycles that range as a preview, without
  mutating the buffer / undo stack.
* SC-U012-2 stopping restores the base palette.
* SC-U012-3 the controls are tr()-wrapped and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.colour_cycling_panel import Colour_Cycling_Panel
from pixelart_creator.ui.main_window import Main_Window

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


@pytest.fixture
def panel(qtbot):
    """A cycling panel bound to the starter palette, recording preview emissions."""
    widget = Colour_Cycling_Panel()
    qtbot.addWidget(widget)
    widget.set_palette(Palette(STARTER))
    widget._start_spin.setValue(0)
    widget._end_spin.setValue(2)
    widget._step_spin.setValue(1)
    emissions: list = []
    widget.previewColors.connect(emissions.append)
    return widget, emissions


# -- SC-U012-1 (play cycles the range as a preview) ----------------------------


def test_sc_u012_1_play_previews_a_rotated_palette(panel):
    """SC-U012-1: a tick while playing emits a rotated (non-identity) palette."""
    widget, emissions = panel
    widget._play_button.setChecked(True)  # start playing
    widget._on_tick()
    assert emissions, "playing did not emit a preview palette"
    assert emissions[-1] != STARTER  # the range was rotated
    assert sorted(emissions[-1]) == sorted(STARTER)  # a rotation, no new colours


def test_sc_u012_1_preview_does_not_touch_the_undo_stack(qtbot):
    """SC-U012-1: previewing on the canvas pushes no undo command (non-destructive)."""
    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    before = record.stack.count()
    win._on_cycle_preview([(1, 2, 3, 255)])  # a preview emission from the panel
    assert record.stack.count() == before


# -- SC-U012-2 (stop restores the base palette) --------------------------------


def test_sc_u012_2_stop_restores_the_base_palette(panel):
    """SC-U012-2: stopping emits the base palette (preview reverted)."""
    widget, emissions = panel
    widget._play_button.setChecked(True)
    widget._on_tick()
    widget.stop()
    assert emissions[-1] == STARTER


# -- SC-U012-3 (tr()-wrapped, keyboard-reachable, both themes) -----------------


def test_sc_u012_3_controls_labelled_and_focusable(panel):
    """SC-U012-3: range spins + play/apply carry labels and take keyboard focus."""
    widget, _emissions = panel
    assert widget.accessibleName() != ""
    for spin in (widget._start_spin, widget._end_spin, widget._step_spin):
        assert spin.accessibleName() != ""
        assert spin.focusPolicy() != Qt.FocusPolicy.NoFocus
    for button in (widget._play_button, widget._apply_button):
        assert button.text() != ""
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus


# -- guard / edge-path coverage (defensive branches) ---------------------------


def test_apply_stops_and_requests_commit(panel, qtbot):
    """Apply stops any preview and emits the commit request with the range."""
    widget, _emissions = panel
    with qtbot.waitSignal(widget.applyRequested, timeout=1000) as blocker:
        widget._apply_button.click()
    assert blocker.args == [0, 2, 1]


def test_tick_with_empty_range_emits_nothing(qtbot):
    """A tick with end < start rotates nothing (guard branch)."""
    widget = Colour_Cycling_Panel()
    qtbot.addWidget(widget)
    widget.set_palette(Palette(STARTER))
    widget._start_spin.setValue(2)
    widget._end_spin.setValue(2)
    got: list = []
    widget.previewColors.connect(got.append)
    widget._start_spin.setMaximum(5)
    widget._start_spin.setValue(3)  # start now > end
    widget._on_tick()
    assert got == []


def test_set_palette_clamps_end_index(qtbot):
    """Binding a smaller palette clamps an out-of-range end index (line 102)."""
    widget = Colour_Cycling_Panel()
    qtbot.addWidget(widget)
    widget._end_spin.setValue(5)
    widget.set_palette(Palette(STARTER[:2]))  # only two colours → upper index 1
    assert widget._end_spin.value() <= 1
