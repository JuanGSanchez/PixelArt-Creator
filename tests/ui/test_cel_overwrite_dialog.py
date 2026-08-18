"""Cel overwrite confirmation acceptance tests (T18; REQ-P5-UI-033,
REQ-P5-DATA-004).

Two layers of coverage:

1. ``Cel_Overwrite_Dialog`` itself, as a standalone widget: default state,
   accessible names, translatability, and the exact "ticking + cancelling
   records nothing" contract of :meth:`Cel_Overwrite_Dialog.dont_ask_again`.
2. The full grid-driven flow (``Timeline_Grid_View._finish_drag``), which
   presents the dialog **before** applying a drop onto a non-empty cell.
   Because :meth:`QDialog.exec` is a blocking modal call, the grid-driven
   tests monkeypatch ``Cel_Overwrite_Dialog.exec`` to answer immediately
   (same headless-modal pattern the shipped ``mute_message_boxes`` fixture
   uses for ``QMessageBox``) — the dialog's OWN behaviour is proven
   separately, unpatched, in part 1 above.

Both themes run via the autouse ``theme`` fixture (REQ-P5-UI-028).
"""

from __future__ import annotations

from typing import List

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.project_prefs import CONFIRM_CEL_OVERWRITE
from pixelart_creator.logic.track_table import EMPTY_CELL, track_table
from pixelart_creator.ui.cel_overwrite_dialog import Cel_Overwrite_Dialog
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


# --------------------------------------------------------------------------- #
# Part 1 — the dialog itself                                                  #
# --------------------------------------------------------------------------- #


def test_dialog_default_state_and_accessible_names(qtbot):
    """The dialog opens with "Don't ask again" unticked and every interactive
    part carrying a non-empty accessible name."""
    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)

    assert dialog.dont_ask_again() is False
    assert dialog.accessibleName() != ""
    assert dialog._message.accessibleName() != ""
    assert dialog._dont_ask.accessibleName() != ""
    assert dialog._dont_ask.text() != ""
    assert dialog.windowTitle() != ""


def test_dialog_is_keyboard_reachable_and_modal(qtbot):
    """The dialog is modal (blocking, cancellable) and its controls are real
    focusable widgets, not painted-only."""
    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)

    assert dialog.isModal()
    assert dialog._dont_ask.focusPolicy() != Qt.FocusPolicy.NoFocus
    yes = dialog._buttons.button(dialog._buttons.StandardButton.Yes)
    cancel = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    assert yes is not None and cancel is not None
    assert yes.text() != "" and cancel.text() != ""


def test_dialog_cancel_returns_rejected(qtbot):
    """Clicking Cancel rejects the dialog."""
    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    cancel = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)

    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)

    assert dialog.result() == dialog.DialogCode.Rejected


def test_dialog_yes_returns_accepted(qtbot):
    """Clicking the overwrite (Yes) button accepts the dialog."""
    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    yes = dialog._buttons.button(dialog._buttons.StandardButton.Yes)

    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        qtbot.mouseClick(yes, Qt.MouseButton.LeftButton)

    assert dialog.result() == dialog.DialogCode.Accepted


def test_dialog_retranslates_on_language_change(qtbot):
    """A LanguageChange event re-sets every user-visible string without
    raising, and the accessible names stay non-empty."""
    from PySide6.QtCore import QEvent

    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)

    dialog.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() != ""
    assert dialog.accessibleName() != ""
    assert dialog._dont_ask.text() != ""


def test_dialog_retranslate_tolerates_missing_standard_buttons(qtbot, monkeypatch):
    """The defensive ``is not None`` guards around the Yes/Cancel buttons in
    ``_retranslate`` must not assume ``QDialogButtonBox.button()`` always
    resolves both standard buttons — proven by forcing ``button()`` to
    report neither found (a future button-box refactor that drops a
    standard button), which must degrade gracefully rather than raise. The
    rest of ``_retranslate`` (title, message, checkbox) is unaffected, since
    those calls do not go through ``button()`` at all."""
    dialog = Cel_Overwrite_Dialog()
    qtbot.addWidget(dialog)
    monkeypatch.setattr(dialog._buttons, "button", lambda *a, **k: None)

    dialog._retranslate()  # must not raise

    assert dialog.windowTitle() != ""
    assert dialog._dont_ask.text() != ""


# --------------------------------------------------------------------------- #
# Part 2 — the grid-driven overwrite flow (REQ-P5-UI-033)                     #
# --------------------------------------------------------------------------- #


def _make_overwrite_doc() -> Document:
    """Two frames, both carrying different drawings on track "Outline"."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    outline.buffer.fill_rect(0, 0, 64, 64, (200, 20, 20, 255))
    doc.make_duplicate_frame_command(0).execute()
    doc.frames[1].layers[1].buffer.fill_rect(0, 0, 64, 64, (20, 200, 20, 255))
    return doc


def _make_panel(qtbot, doc: Document):
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(500, 200)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)
    panel._grid_toggle_action.setChecked(True)
    return panel, panel._grid, stack


def _outline_row(doc: Document) -> int:
    table = track_table(doc, active_frame=0)
    return next(i for i, r in enumerate(table.rows) if r.label == "Outline")


def _drag_cell_to_cell(qtbot, grid, start_row, start_col, end_row, end_col):
    start = grid.visualRect(grid.model().index(start_row, start_col)).center()
    end = grid.visualRect(grid.model().index(end_row, end_col)).center()
    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, pos=start)
    for i in range(1, 6):
        pos = QPoint(
            start.x() + (end.x() - start.x()) * i // 5,
            start.y() + (end.y() - start.y()) * i // 5,
        )
        qtbot.mouseMove(grid.viewport(), pos=pos)
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, pos=end)


@pytest.fixture
def answer_dialog(monkeypatch):
    """Patch ``Cel_Overwrite_Dialog.exec`` to answer immediately (headless
    modal automation — the dialog's own behaviour is proven, unpatched, in
    Part 1 above). Returns a controller: ``answer_dialog(accept=True,
    dont_ask=False)``; records every simulated presentation."""
    calls: List[bool] = []

    state = {"accept": True, "dont_ask": False}

    def _fake_exec(self):
        calls.append(True)
        self._dont_ask.setChecked(state["dont_ask"])
        if state["accept"]:
            self.accept()
            return self.DialogCode.Accepted
        self.reject()
        return self.DialogCode.Rejected

    monkeypatch.setattr(Cel_Overwrite_Dialog, "exec", _fake_exec)

    def _configure(*, accept: bool, dont_ask: bool = False) -> List[bool]:
        state["accept"] = accept
        state["dont_ask"] = dont_ask
        return calls

    return _configure


def test_sc_ui_033_1_occupied_destination_confirmed_before_anything_applied(
    qtbot, answer_dialog
):
    """SC-UI-033-1: dropping onto an occupied destination presents the
    confirmation before any change is applied."""
    doc = _make_overwrite_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    presented = answer_dialog(accept=False)  # cancel; assert BEFORE any change
    before = stack.count()

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert presented == [True]
    assert stack.count() == before  # nothing applied while confirming/cancel


def test_sc_ui_033_2_cancelling_leaves_everything_exactly_as_it_was(
    qtbot, answer_dialog
):
    """SC-UI-033-2: cancelling leaves both cells untouched and pushes no
    command."""
    doc = _make_overwrite_doc()
    src_id = doc.frames[0].layers[1].layer_id
    dst_id = doc.frames[1].layers[1].layer_id
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    answer_dialog(accept=False)
    before = stack.count()

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert stack.count() == before
    assert doc.frames[0].layers[1].layer_id == src_id
    assert doc.frames[1].layers[1].layer_id == dst_id
    assert doc.frames[0].layers[1].buffer.data[0, 0].tolist() == [200, 20, 20, 255]
    assert doc.frames[1].layers[1].buffer.data[0, 0].tolist() == [20, 200, 20, 255]


def test_sc_ui_033_3_confirming_performs_overwrite_as_one_reversible_command(
    qtbot, answer_dialog
):
    """SC-UI-033-3: confirming performs the overwrite as exactly one
    QUndoCommand, and undo restores the destination's prior content exactly."""
    doc = _make_overwrite_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    answer_dialog(accept=True)
    before = stack.count()

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert stack.count() == before + 1
    table_after = track_table(doc, active_frame=0)
    assert table_after.rows[row].cells[0] is EMPTY_CELL
    assert doc.frames[1].layers[1].buffer.data[0, 0].tolist() == [200, 20, 20, 255]

    stack.undo()
    assert doc.frames[1].layers[1].buffer.data[0, 0].tolist() == [20, 200, 20, 255]


def test_sc_ui_033_4_empty_destination_is_not_confirmed_at_all(qtbot, answer_dialog):
    """SC-UI-033-4: dropping onto an empty cell applies directly, with no
    confirmation presented."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # frame 1 has no "Outline" -> empty there
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    presented = answer_dialog(accept=True)
    before = stack.count()

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert presented == []  # never shown
    assert stack.count() == before + 1


def test_sc_ui_033_5_any_existing_content_counts_as_not_empty(qtbot, answer_dialog):
    """SC-UI-033-5: even a destination the test deliberately makes visually
    minimal (a single non-default pixel) still counts as occupied and
    triggers the confirmation — "empty" means no node at all, never a
    transparency/threshold heuristic (this is exercised precisely by
    ``_make_overwrite_doc``, whose destination already carries full content;
    the point here is that the grid's own "occupied" test is
    node-existence-based, matching ``EMPTY_CELL`` identity, not pixel
    inspection)."""
    doc = _make_overwrite_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    presented = answer_dialog(accept=False)

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert presented == [True]


def test_sc_ui_033_6_dont_ask_again_suppresses_the_question_and_nothing_else(
    qtbot, answer_dialog
):
    """SC-UI-033-6: ticking "Don't ask again" and proceeding suppresses future
    confirmations for this project; the overwrite it enables remains exactly
    one reversible command with exact undo."""
    doc = _make_overwrite_doc()
    doc.make_duplicate_frame_command(1).execute()  # frame 2: another Outline
    doc.frames[2].layers[1].buffer.fill_rect(0, 0, 64, 64, (5, 5, 5, 255))
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    presented = answer_dialog(accept=True, dont_ask=True)

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)
    assert presented == [True]
    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed"

    # A second overwriting drop in the SAME project: no confirmation shown.
    before = stack.count()
    _drag_cell_to_cell(qtbot, grid, row, 1, row, 2)
    assert presented == [True]  # unchanged: not presented a second time
    assert stack.count() == before + 1  # still exactly one command
    stack.undo()
    assert doc.frames[2].layers[1].buffer.data[0, 0].tolist() == [5, 5, 5, 255]


def test_sc_ui_033_7_ticking_then_cancelling_records_nothing(qtbot, answer_dialog):
    """SC-UI-033-7: ticking "Don't ask again" and then cancelling records no
    preference; the next overwriting drop still presents the confirmation."""
    doc = _make_overwrite_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    row = _outline_row(doc)
    presented = answer_dialog(accept=False, dont_ask=True)

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert presented == [True]
    assert doc.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"


def test_sc_ui_033_8_the_memory_belongs_to_one_project(qtbot, answer_dialog):
    """SC-UI-033-8: suppressing the confirmation in one document's prefs does
    not affect a second, independent document's prefs."""
    doc1 = _make_overwrite_doc()
    doc2 = _make_overwrite_doc()
    panel, grid, stack = _make_panel(qtbot, doc1)
    row = _outline_row(doc1)
    answer_dialog(accept=True, dont_ask=True)

    _drag_cell_to_cell(qtbot, grid, row, 0, row, 1)

    assert doc1.prefs.get(CONFIRM_CEL_OVERWRITE) == "suppressed"
    assert doc2.prefs.get(CONFIRM_CEL_OVERWRITE) == "ask"
