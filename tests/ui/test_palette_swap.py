"""Palette-swap acceptance tests (REQ-P3-UI-013).

One test per acceptance criterion:

* SC-U013-1 defining + applying an index remap recolours indexed art as ONE
  undoable command.
* SC-U013-2 undo restores the pre-swap buffer exactly.
* SC-U013-3 the swap dialog is tr()-wrapped and keyboard-reachable; it collects a
  remap.

The apply flow is exercised through :class:`Main_Window` (indexed document +
dialog → logic swap command → undo stack). Every test runs in both themes via the
autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pixelart_creator.ui import main_window as mw
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.palette_swap_dialog import Palette_Swap_Dialog


class _FakeSwapDialog:
    """Stand-in for the modal swap dialog: accepts with a fixed mapping."""

    def __init__(self, mapping):
        self._mapping = mapping

    def __call__(self, max_index, parent=None):
        return self

    def exec(self):
        return int(QDialog.DialogCode.Accepted)

    def mapping(self):
        return dict(self._mapping)


@pytest.fixture
def indexed_win(qtbot):
    """A window whose active document has been converted to indexed mode."""
    win = Main_Window()
    qtbot.addWidget(win)
    win._on_convert_to_indexed()
    record = win.active_tab()
    assert record.scene.active_buffer().mode.name == "INDEXED"
    return win, record


# -- SC-U013-1 (apply remap recolours as ONE command) --------------------------


def test_sc_u013_1_apply_remap_is_one_command(indexed_win, monkeypatch):
    """SC-U013-1: applying a remap recolours indexed pixels as one command."""
    win, record = indexed_win
    buffer = record.scene.active_buffer()
    buffer.set_pixel(0, 0, 2)  # paint index 2 so the remap has something to change
    base_count = (
        record.stack.count()
    )  # the RGBA→indexed convert is already on the stack
    monkeypatch.setattr(mw, "Palette_Swap_Dialog", _FakeSwapDialog({2: 1}))
    win._on_palette_swap()
    assert (
        record.stack.count() == base_count + 1
    )  # the swap is exactly one more command
    assert int(buffer.get_pixel(0, 0)) == 1


# -- SC-U013-2 (undo restores the pre-swap buffer exactly) ---------------------


def test_sc_u013_2_undo_restores_pre_swap_buffer(indexed_win, monkeypatch):
    """SC-U013-2: undo of the swap restores the exact prior indices."""
    win, record = indexed_win
    buffer = record.scene.active_buffer()
    buffer.set_pixel(0, 0, 2)
    before = buffer.data.copy()
    monkeypatch.setattr(mw, "Palette_Swap_Dialog", _FakeSwapDialog({2: 1}))
    win._on_palette_swap()
    record.stack.undo()
    assert np.array_equal(buffer.data, before)


# -- SC-U013-3 (dialog tr()-wrapped, keyboard-reachable, collects a remap) -----


def test_sc_u013_3_dialog_collects_mapping_and_is_labelled(qtbot):
    """SC-U013-3: the dialog collects an index→index remap with labelled controls."""
    dialog = Palette_Swap_Dialog(7)
    qtbot.addWidget(dialog)
    dialog._from_spin.setValue(3)
    dialog._to_spin.setValue(5)
    dialog._on_add_pair()
    assert dialog.mapping() == {3: 5}
    assert dialog.windowTitle() != ""
    assert dialog._from_spin.accessibleName() != ""
    assert dialog._to_spin.accessibleName() != ""
    assert dialog._from_spin.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_dialog_remove_pair_drops_the_entry(qtbot):
    """Removing a selected mapping entry drops it from the collected remap."""
    dialog = Palette_Swap_Dialog(7)
    qtbot.addWidget(dialog)
    dialog._from_spin.setValue(1)
    dialog._to_spin.setValue(2)
    dialog._on_add_pair()
    dialog._from_spin.setValue(3)
    dialog._to_spin.setValue(4)
    dialog._on_add_pair()
    dialog._list.setCurrentRow(0)
    dialog._on_remove_pair()
    assert dialog.mapping() == {3: 4}
