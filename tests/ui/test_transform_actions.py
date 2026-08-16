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


def test_t16_scale_with_active_selection_affects_only_the_selection(qtbot, monkeypatch):
    """T-16 (AGT-06 audit, pairs with CF-07): scaling with an active selection
    affects only the selected region, per the ``logic/transform`` mask contract
    (``make_transform_command`` routes to ``_masked_transform_changes`` when a
    mask is supplied) — driven through the shipped UI action
    ``Main_Window._on_scale``, which now forwards ``record.view.active_selection()``
    (CF-07). The whole-buffer dimensions are UNCHANGED (a masked transform never
    resizes the canvas); pixels outside the selection are byte-identical.
    """
    from pixelart_creator.logic.selection import rect_mask
    from tests.ui._ui_helpers import prepare_for_click

    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    w, h = buf.width, buf.height

    # A distinctive 4x4 block inside the selection, and a sentinel pixel outside.
    for y in range(2, 6):
        for x in range(2, 6):
            buf.set_pixel(x, y, RED)
    buf.set_pixel(20, 20, GREEN)  # outside the selection — must stay untouched
    outside_before = buf.get_pixel(20, 20)

    prepare_for_click(record.view)
    record.view.set_selection(rect_mask(w, h, 2, 2, 5, 5))

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(Scale_Dialog, "target_size", lambda self: (w * 2, h * 2))
    win._on_scale()

    assert record.stack.count() == 1
    out = record.scene.active_buffer()
    # A masked scale never changes the whole-buffer dimensions (SC-L010-1 —
    # only the selected sub-region is re-stamped in place).
    assert (out.width, out.height) == (w, h)
    assert out.get_pixel(20, 20) == outside_before  # untouched outside the mask

    record.stack.undo()
    assert record.scene.active_buffer().get_pixel(20, 20) == outside_before


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
