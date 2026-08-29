"""Macro record / replay controls — SC-UI-001-1, SC-UI-002-1 (REQ-P8-UI-001/-002).

SC-UI-001-1 — the user starts/stops recording; the captured edits become an
ordered macro and recording state is NOT an undo entry (view state, CL-8).
SC-UI-002-1 — replaying a macro lands as ONE undoable action whose single undo
reverts the whole replay, the result matches the recording, and the same seed
reproduces an identical document (deterministic replay). Headless; every test
also runs under both themes via the autouse ``theme`` fixture (REQ-P8-UI-013).
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pixelart_creator.logic.macro import Macro
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import (
    arrays_equal,
    buffer_of,
    macro_of,
    procgen_op,
    replay,
    run_ops,
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_001_record_start_stop_captures_ops_and_is_not_undoable(qtbot):
    """SC-UI-001-1: start/stop recording captures the edits; the toggle is not undoable."""
    win = _window(qtbot)
    controls = win._macro_controls
    stack = win.active_tab().stack

    assert not controls.is_recording()
    # Start recording — view/session state, pushes NO undo command (CL-8).
    controls._record_button.setChecked(True)
    assert controls.is_recording()
    assert stack.count() == 0

    # One automation edit performed while recording is captured into the macro.
    run_ops(qtbot, win, [procgen_op(seed=7)])
    assert stack.count() == 1  # the EDIT is one undoable command…

    # Stop recording — banks the captured macro; the toggle adds no undo entry.
    controls._record_button.setChecked(False)
    assert not controls.is_recording()
    assert stack.count() == 1
    assert controls._list.count() == 1

    macro = controls._list.item(0).data(Qt.ItemDataRole.UserRole)
    assert isinstance(macro, Macro)
    assert len(macro.ops) == 1  # ordered reversible op captured, not a pixel diff


def test_sc_ui_002_replay_is_one_undoable_action_that_reverts_exactly(qtbot):
    """SC-UI-002-1: a macro replay is one undoable command; one undo reverts it all."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    replay(qtbot, win, macro_of(procgen_op(seed=7)))
    after = buffer_of(tab.document).copy()

    assert stack.count() == 1  # exactly one grouped QUndoCommand for the whole replay
    assert not arrays_equal(initial, after)  # the replay edited the document

    stack.undo()  # ONE undo reverts the whole replay to the exact prior state
    assert arrays_equal(buffer_of(tab.document), initial)


def test_sc_ui_002_replay_is_deterministic_same_seed(qtbot):
    """SC-UI-002-1: the same macro + same initial document → an identical result."""
    macro = macro_of(procgen_op(seed=7))

    win1 = _window(qtbot)
    replay(qtbot, win1, macro)
    first = buffer_of(win1.active_document()).copy()

    win2 = _window(qtbot)
    replay(qtbot, win2, macro)
    second = buffer_of(win2.active_document()).copy()

    assert arrays_equal(first, second)  # deterministic (SC-UI-002 / SC-L005 at the UI)
