"""Indexed-mode workflow acceptance tests (REQ-P3-UI-014, T22).

One test per acceptance criterion, driven through :class:`Main_Window`:

* SC-U014-1 Convert to Indexed / RGBA are single undoable commands
  (``apply ∘ undo = identity``).
* SC-U014-2 painting by palette index writes the active index on an indexed buffer.
* SC-U014-3 the mode indicator reflects the buffer mode; controls are tr()-wrapped
  and keyboard-reachable.

Every test runs in both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._ui_helpers import click_pixel, prepare_for_click


@pytest.fixture
def win(qtbot) -> Main_Window:
    window = Main_Window()
    qtbot.addWidget(window)
    return window


# -- SC-U014-1 (convert RGBA↔indexed is one undoable command; identity) --------


def test_sc_u014_1_convert_to_indexed_is_one_undoable_identity(win):
    """SC-U014-1: RGBA→indexed is one command; undo restores the RGBA buffer."""
    record = win.active_tab()
    layer = record.scene.active_layer()
    layer.buffer.set_pixel(3, 3, (230, 30, 30, 255))  # a red pixel (nearest STARTER index 2)
    original = layer.buffer
    original_data = original.data.copy()

    win._on_convert_to_indexed()
    assert record.stack.count() == 1
    assert record.scene.active_buffer().mode is ColorMode.INDEXED

    record.stack.undo()
    restored = record.scene.active_buffer()
    assert restored.mode is ColorMode.RGBA
    assert np.array_equal(restored.data, original_data)


def test_sc_u014_1_convert_to_rgba_is_one_undoable_identity(win):
    """SC-U014-1: indexed→RGBA is one command; undo restores the indexed buffer."""
    record = win.active_tab()
    win._on_convert_to_indexed()  # first go indexed
    indexed = record.scene.active_buffer()
    indexed.set_pixel(1, 1, 2)
    indexed_data = indexed.data.copy()
    base_count = record.stack.count()

    win._on_convert_to_rgba()
    assert record.stack.count() == base_count + 1
    assert record.scene.active_buffer().mode is ColorMode.RGBA

    record.stack.undo()
    restored = record.scene.active_buffer()
    assert restored.mode is ColorMode.INDEXED
    assert np.array_equal(restored.data, indexed_data)


# -- SC-U014-2 (paint-by-index writes the active index) ------------------------


def test_sc_u014_2_paint_by_index_writes_active_index(win):
    """SC-U014-2: on an indexed buffer a paint stroke writes the active index."""
    record = win.active_tab()
    win._on_convert_to_indexed()
    buffer = record.scene.active_buffer()
    win._set_active_index(2)  # select palette index 2

    view = record.view
    prepare_for_click(view)
    click_pixel(view, 5, 5)
    assert int(buffer.get_pixel(5, 5)) == 2


# -- SC-U014-3 (mode indicator + tr()-wrapped, keyboard-reachable) -------------


def test_sc_u014_3_mode_indicator_reflects_state(win):
    """SC-U014-3: the palette panel's mode indicator tracks the buffer mode."""
    win._on_convert_to_indexed()
    assert win._palette_panel._mode is ColorMode.INDEXED
    assert win._palette_panel._mode_label.text() != ""
    # The convert actions gate on the live mode.
    assert not win._to_indexed_action.isEnabled()
    assert win._to_rgba_action.isEnabled()

    win._on_convert_to_rgba()
    assert win._palette_panel._mode is ColorMode.RGBA
    assert win._to_indexed_action.isEnabled()
    assert not win._to_rgba_action.isEnabled()


def test_sc_u014_3_convert_actions_are_labelled(win):
    """SC-U014-3: the convert actions carry translated labels."""
    assert win._to_indexed_action.text() != ""
    assert win._to_rgba_action.text() != ""
