"""Batch recolour panel — SC-UI-006-1 (REQ-P8-UI-006, REQ-P8-LOGIC-011).

The batch-recolour panel assembles a colour/index remap and applies it across the
frame's layers as ONE undoable action; the transactional ``logic.batch_ops``
composes the shipped ``palette_ops`` (PS-1). Here the panel's own Apply path is
driven and the result verified to land as exactly one command that a single undo
reverts. Headless; both themes.
"""

from __future__ import annotations

import numpy as np

from pixelart_creator.ui.batch_recolour_panel import _MODE_COLOUR
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import (
    GREEN,
    RED,
    RUN_TIMEOUT_MS,
    arrays_equal,
    batch_recolour_op,
    buffer_of,
    paint,
    run_ops,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_006_batch_recolour_lands_as_one_undoable_action(qtbot):
    """SC-UI-006-1: a batch recolour is exactly one undoable command; undo reverts it."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    paint(tab.document, RED)  # known content to remap
    initial = buffer_of(tab.document).copy()

    run_ops(qtbot, win, [batch_recolour_op(src=RED, dst=GREEN)])

    assert stack.count() == 1  # ONE undoable batch action
    assert np.all(buffer_of(tab.document) == np.array(GREEN, dtype=np.uint8))
    stack.undo()
    assert arrays_equal(buffer_of(tab.document), initial)


def test_sc_ui_006_panel_apply_path_emits_and_lands_one_command(qtbot):
    """SC-UI-006-1: driving the panel's colour-remap Apply lands one batch command."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    paint(tab.document, RED)
    panel = win._batch_recolour_panel

    panel._mode_combo.setCurrentIndex(_MODE_COLOUR)  # colour-remap mode
    panel._src_colour = RED
    panel._dst_colour = GREEN
    panel._on_add_pair()  # one src→dst pair

    with qtbot.waitSignal(
        win._automation_controller.runFinished, timeout=RUN_TIMEOUT_MS
    ):
        panel._on_apply()

    assert stack.count() == 1
    assert np.all(buffer_of(tab.document) == np.array(GREEN, dtype=np.uint8))
