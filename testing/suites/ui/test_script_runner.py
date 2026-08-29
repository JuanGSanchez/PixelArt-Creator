"""Script runner — SC-UI-004-1 (REQ-P8-UI-004, -001/-002/-003 logic).

The script runner parses an inert JSON DSL script (``json.loads`` — data, never
code) into ``Op`` steps and hands them to the window, which dispatches them
through the trusted allow-listed ``logic.scripting`` on the off-GUI-thread worker:
scripted edits appear as undoable commands, and a failing / unknown-op script
surfaces a graceful error with no command landing. Headless; both themes.
"""

from __future__ import annotations

from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import (
    RUN_TIMEOUT_MS,
    arrays_equal,
    buffer_of,
)

_VALID_SCRIPT = (
    '[{"name": "procgen",'
    ' "params": {"algorithm": "value_noise", "width": 64, "height": 64},'
    ' "seed": 7}]'
)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_004_script_edit_is_one_undoable_command(qtbot):
    """SC-UI-004-1: a script's edit appears as one undoable command; undo reverts it."""
    win = _window(qtbot)
    tab = win.active_tab()
    stack = tab.stack
    initial = buffer_of(tab.document).copy()

    win._script_runner_panel._editor.setPlainText(_VALID_SCRIPT)
    with qtbot.waitSignal(
        win._automation_controller.runFinished, timeout=RUN_TIMEOUT_MS
    ):
        win._script_runner_panel._on_run()

    assert stack.count() == 1
    assert not arrays_equal(buffer_of(tab.document), initial)
    stack.undo()
    assert arrays_equal(buffer_of(tab.document), initial)


def test_sc_ui_004_unknown_op_script_surfaces_graceful_error(qtbot, mute_message_boxes):
    """SC-UI-004-1: an unknown-op script is rejected by the dispatcher (graceful error)."""
    win = _window(qtbot)
    stack = win.active_tab().stack

    win._script_runner_panel._editor.setPlainText(
        '[{"name": "no_such_op", "params": {}}]'
    )
    with qtbot.waitSignal(
        win._automation_controller.runFinished, timeout=RUN_TIMEOUT_MS
    ):
        win._script_runner_panel._on_run()

    assert stack.count() == 0  # nothing landed
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)


def test_sc_ui_004_invalid_json_rejected_before_dispatch(qtbot, mute_message_boxes):
    """SC-UI-004-1: invalid JSON is rejected in-panel before any worker run (no exec)."""
    win = _window(qtbot)
    stack = win.active_tab().stack

    win._script_runner_panel._editor.setPlainText("{ this is not valid json")
    win._script_runner_panel._on_run()  # parse fails in-panel; no automation submitted

    assert stack.count() == 0
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)
    assert not win._automation_controller.is_busy()
