"""Non-destructive visual-aids acceptance tests (REQ-P9-UI-010).

Scenario SC-UI-010-1: enabling a grid, creating a guide, adding a reference,
opening a view, and starting recording mutate neither the document nor the undo
stack — visual aids are view/session state and push no QUndoCommand. Only actual
drawing edits (the shipped HIS-1 path) are undoable. Both themes via the autouse
fixture.
"""

from __future__ import annotations

from pixelart_creator.logic.guides import GuideOrientation
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_010_1_enabling_aids_pushes_no_undo_command(qtbot):
    """SC-UI-010-1: toggling every aid leaves the undo stack clean and empty."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record is not None
    assert record.stack.count() == 0
    assert record.stack.isClean()
    buffer_before = record.scene.active_buffer().copy()

    # Enable the grid overlays, guides/rulers, open a view, show the board, record.
    win._iso_action.setChecked(True)
    win._perspective_action.setChecked(True)
    win._guides_action.setChecked(True)
    if record.guides_rulers is not None:
        record.guides_rulers.overlay_item().add_guide(GuideOrientation.VERTICAL, 8.0)
    win._on_new_view()
    win._on_show_reference_board()
    win._timelapse_controls._record_button.setChecked(True)

    # None of the aids touched the document or its undo history.
    assert record.stack.count() == 0
    assert record.stack.isClean()
    assert record.scene.active_buffer() == buffer_before
    win._multi_view.close_all()
    win._reference_board.close()


def test_sc_ui_010_1_grid_overlays_are_hidden_view_state(qtbot):
    """SC-UI-010-1: overlay visibility is view state, defaulting to off."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.iso_overlay is not None
    assert record.perspective_overlay is not None
    # Overlays exist but are not shown until the Aids menu toggles them on.
    assert record.iso_overlay.isVisible() is False
    assert record.perspective_overlay.isVisible() is False
    win._iso_action.setChecked(True)
    assert record.iso_overlay.isVisible() is True
    # Still no document mutation from a pure view-state toggle.
    assert record.stack.count() == 0
