"""Selection-operation actions acceptance (REQ-P2-UI-008).

Scenarios SC-U008-1 (invert / clear / deselect / select-all actions are
tr()-wrapped and keyboard-reachable) and SC-U008-2 (clear is undoable; deselect
empties the active mask). Both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtGui import QKeySequence

from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.ui.main_window import Main_Window

RED = (230, 30, 30, 255)
TRANSPARENT = (0, 0, 0, 0)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_u008_1_actions_translatable_and_reachable(qtbot):
    """SC-U008-1: the selection actions carry labels and keyboard shortcuts."""
    win = _window(qtbot)
    for action in (
        win._select_all_action,
        win._deselect_action,
        win._invert_action,
        win._clear_action,
    ):
        assert action.text() != ""  # tr()-wrapped (accessible name)
        assert not action.shortcut().isEmpty()  # keyboard-reachable
    assert win._select_all_action.shortcut() == QKeySequence("Ctrl+A")
    assert win._clear_action.shortcut() == QKeySequence("Del")


def test_sc_u008_2_select_all_invert_deselect(qtbot):
    """SC-U008-2: select-all selects the buffer; invert complements; deselect empties."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    win._on_select_all()
    mask = record.view.active_selection()
    assert mask is not None and mask.count() == buf.width * buf.height
    win._on_invert_selection()
    assert record.view.active_selection() is None  # complement of all is empty
    win._on_deselect()
    assert record.view.active_selection() is None


def test_sc_u008_2_clear_is_undoable(qtbot):
    """SC-U008-2: clearing a selection is a single undoable command."""
    win = _window(qtbot)
    record = win.active_tab()
    buf = record.scene.active_buffer()
    buf.set_pixel(3, 3, RED)
    before = buf.copy()
    record.view.set_selection(rect_mask(buf.width, buf.height, 2, 2, 4, 4))
    win._on_clear_selection()
    assert record.stack.count() == 1
    assert buf.get_pixel(3, 3) == TRANSPARENT
    record.stack.undo()
    assert record.scene.active_buffer() == before
