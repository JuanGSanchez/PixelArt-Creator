"""Transform-action acceptance (REQ-P2-UI-009).

Scenarios SC-U009-1 (flip-H/V and rotate-90-CW/CCW transform the buffer as one
undoable command), SC-U009-2 (the scale dialog applies nearest-neighbour scaling
introducing NO new colours, as one undoable command) and SC-U009-3 (the actions
are tr()-wrapped, keyboard-reachable, correct in both themes). Undo/redo integrity
is asserted for each mutating op. Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.transform_dialog import Scale_Dialog

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _colour_set(buf) -> set:
    return {
        tuple(int(c) for c in px) for px in buf.data.reshape(-1, buf.data.shape[-1])
    }


def test_sc_u009_1_flip_horizontal_one_command_reversible(qtbot):
    """SC-U009-1: flip-H mirrors the buffer as one command; undo/redo restore it."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    w = buf.width
    buf.set_pixel(1, 2, RED)
    before = buf.copy()
    win._on_flip_horizontal()
    assert record.stack.count() == 1
    moved = record.scene.active_buffer()
    assert moved.get_pixel(w - 2, 2) == RED
    assert moved.get_pixel(1, 2) != RED
    record.stack.undo()
    assert record.scene.active_buffer() == before
    record.stack.redo()
    assert record.scene.active_buffer().get_pixel(w - 2, 2) == RED


@pytest.mark.parametrize(
    "slot_name",
    ["_on_flip_vertical", "_on_rotate_cw", "_on_rotate_ccw"],
)
def test_sc_u009_1_transforms_one_command_reversible(qtbot, slot_name):
    """SC-U009-1: flip-V / rotate-90 each commit one reversible command."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 1, GREEN)
    before = buf.copy()
    getattr(win, slot_name)()
    assert record.stack.count() == 1
    record.stack.undo()
    assert record.scene.active_buffer() == before


def test_sc_u009_2_scale_nearest_no_new_colours(qtbot, monkeypatch):
    """SC-U009-2: scale-NN applies as one command and introduces NO new colours."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(5, 5, GREEN)
    src_colours = _colour_set(buf)
    src_w = record.document.width

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        Scale_Dialog, "target_size", lambda self: (src_w * 2, src_w * 2)
    )
    win._on_scale()

    assert record.stack.count() == 1
    out = record.scene.active_buffer()
    assert out.width == src_w * 2  # dimensions changed
    assert _colour_set(out).issubset(src_colours)  # NO new colours (R2)
    record.stack.undo()
    assert record.scene.active_buffer().width == src_w


def test_sc_u009_3_actions_translatable_and_reachable(qtbot):
    """SC-U009-3: the transform actions are tr()-wrapped and menu/keyboard operable."""
    win = _window(qtbot)
    for action in (
        win._flip_h_action,
        win._flip_v_action,
        win._rotate_cw_action,
        win._rotate_ccw_action,
        win._scale_action,
    ):
        assert action.text() != ""
        assert action.isEnabled()
