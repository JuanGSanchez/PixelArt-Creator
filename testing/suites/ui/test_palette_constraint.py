"""Palette-constraint (NES / Game Boy) acceptance tests (REQ-P3-UI-009).

One test per acceptance criterion, driven through :class:`Main_Window` so the
panel signal → logic constraint command → undo-stack wiring is exercised:

* SC-U009-1 applying NES constrains the buffer as ONE undoable command; the
  resulting colour set is ⊆ the NES palette.
* SC-U009-2 applying Game Boy constrains to a ⊆ GB colour set.
* SC-U009-3 the presets are tr()-wrapped and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt

from pixelart_creator.logic.hardware_palette import game_boy_palette, nes_palette
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.palette_constraint_panel import PRESET_GAME_BOY, PRESET_NES


@pytest.fixture
def win(qtbot) -> Main_Window:
    window = Main_Window()
    qtbot.addWidget(window)
    return window


def _seed(buffer) -> None:
    """Fill a few pixels with arbitrary off-palette colours."""
    for x, color in enumerate(
        [(10, 200, 30, 255), (240, 12, 250, 255), (17, 90, 111, 255)]
    ):
        buffer.set_pixel(x, 0, color)


def _buffer_colors(buffer):
    return {
        tuple(int(v) for v in buffer.get_pixel(x, y))
        for y in range(buffer.height)
        for x in range(buffer.width)
    }


# -- SC-U009-1 (NES: one command, ⊆ NES palette) -------------------------------


def test_sc_u009_1_nes_is_one_command_subset_of_nes(win):
    """SC-U009-1: NES constraint is one undoable command; output ⊆ NES palette."""
    record = win.active_tab()
    buffer = record.scene.active_buffer()
    _seed(buffer)
    before = buffer.data.copy()
    win._on_constrain(PRESET_NES)
    assert record.stack.count() == 1
    assert _buffer_colors(buffer).issubset(set(nes_palette().colors()))
    record.stack.undo()
    assert np.array_equal(buffer.data, before)


# -- SC-U009-2 (Game Boy: ⊆ GB palette) ----------------------------------------


def test_sc_u009_2_game_boy_subset_of_gb(win):
    """SC-U009-2: Game Boy constraint yields a colour set ⊆ the GB palette."""
    record = win.active_tab()
    buffer = record.scene.active_buffer()
    _seed(buffer)
    win._on_constrain(PRESET_GAME_BOY)
    assert record.stack.count() == 1
    assert _buffer_colors(buffer).issubset(set(game_boy_palette().colors()))


# -- SC-U009-3 (presets tr()-wrapped + keyboard-reachable, both themes) --------


def test_sc_u009_3_presets_labelled_and_focusable(win):
    """SC-U009-3: NES / GB preset buttons carry labels and take keyboard focus."""
    panel = win._constraint_panel
    assert panel.accessibleName() != ""
    for button in (panel._nes_button, panel._gb_button):
        assert button.text() != ""
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
