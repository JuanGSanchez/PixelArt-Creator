"""RotSprite arbitrary-angle action acceptance (REQ-P2-UI-010).

Scenarios SC-U010-1 (confirming an angle rotates via rotsprite as ONE undoable
command, no crash), SC-U010-2 (the committed result contains only source colours —
R2) and SC-U010-3 (the angle input + action are tr()-wrapped and keyboard-reachable).
Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.rotsprite_dialog import RotSprite_Dialog

RED = (230, 30, 30, 255)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def _colour_set(buf) -> set:
    return {
        tuple(int(c) for c in px) for px in buf.data.reshape(-1, buf.data.shape[-1])
    }


def _small_tab(win):
    """Open a small document tab so RotSprite's 8x upscale stays fast."""
    win.new_document(16, 16)
    return win.active_tab()


def test_sc_u010_1_and_2_rotsprite_one_command_no_new_colours(qtbot, monkeypatch):
    """SC-U010-1/-2: rotate via rotsprite as ONE command; NO new colours (R2)."""
    win = _window(qtbot)
    record = _small_tab(win)
    buf = record.scene.active_buffer()
    for y in range(6, 10):
        for x in range(6, 10):
            buf.set_pixel(x, y, RED)  # a red square on a transparent field
    src_colours = _colour_set(buf)
    before = buf.copy()

    monkeypatch.setattr(
        RotSprite_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(RotSprite_Dialog, "angle", lambda self: 30.0)
    win._on_rotsprite()  # must not raise (no crash)

    assert record.stack.count() == 1
    out = record.scene.active_buffer()
    assert _colour_set(out).issubset(src_colours)  # no colour absent from source
    record.stack.undo()
    assert record.scene.active_buffer() == before


def test_sc_u010_2_zero_angle_is_identity(qtbot, monkeypatch):
    """SC-U010-2 (support): a 0-degree RotSprite leaves the buffer unchanged."""
    win = _window(qtbot)
    record = _small_tab(win)
    buf = record.scene.active_buffer()
    buf.set_pixel(8, 8, RED)
    before = buf.copy()
    monkeypatch.setattr(
        RotSprite_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    monkeypatch.setattr(RotSprite_Dialog, "angle", lambda self: 0.0)
    win._on_rotsprite()
    assert record.scene.active_buffer() == before


def test_sc_u010_3_dialog_translatable_and_reachable(qtbot):
    """SC-U010-3: the RotSprite dialog + action expose tr() names and are operable."""
    win = _window(qtbot)
    assert win._rotsprite_action.text() != ""
    assert win._rotsprite_action.isEnabled()
    # The dialog itself: constructs without a real render, angle round-trips, names set.
    dialog = RotSprite_Dialog(lambda angle: None)
    qtbot.addWidget(dialog)
    assert dialog.accessibleName() != ""
    assert dialog._angle.accessibleName() != ""
    dialog._angle.setValue(45.0)
    assert dialog.angle() == 45.0
