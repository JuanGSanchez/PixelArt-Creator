"""Script runner — SC-UI-004-1 (REQ-P8-UI-004, -001/-002/-003 logic).

The script runner parses an inert JSON DSL script (``json.loads`` — data, never
code) into ``Op`` steps and hands them to the window, which dispatches them
through the trusted allow-listed ``logic.scripting`` on the off-GUI-thread worker:
scripted edits appear as undoable commands, and a failing / unknown-op script
surfaces a graceful error with no command landing. Headless; both themes.
"""

from __future__ import annotations

import json
import logging

import pytest

from pixelart_creator.ui.failure_messages import failure_kind, failure_text
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


def test_sc_ui_004_invalid_json_shows_the_sentence_and_no_exception_text(
    qtbot, mute_message_boxes, caplog
):
    """SC-UI-004-1 + REQ-L10N-UI-018: a rejected script never shows the parser's text.

    Invalid JSON is rejected in-panel: the box reads "Invalid JSON: " followed by the
    sentence for the failure's kind (a ``json.JSONDecodeError`` is a ``ValueError``)
    in the active language. Neither the decoder's own message nor its type name is in
    it, and the detail is logged. The four messages the panel writes itself for a
    malformed step are still shown as they were, and nothing is dispatched.
    """
    win = _window(qtbot)
    stack = win.active_tab().stack
    panel = win._script_runner_panel

    bad_text = "{ this is not valid json"
    with pytest.raises(json.JSONDecodeError) as raised:
        json.loads(bad_text)
    decoder_error = raised.value
    sentence = failure_text(failure_kind(decoder_error))

    panel._editor.setPlainText(bad_text)
    with caplog.at_level(logging.WARNING):
        panel._on_run()

    assert stack.count() == 0
    assert not win._automation_controller.is_busy()
    boxes = [text for kind, _title, text in mute_message_boxes if kind == "warning"]
    assert len(boxes) == 1
    shown = boxes[0]
    assert shown.startswith("Invalid JSON: ")
    assert shown.endswith(sentence)
    assert decoder_error.msg not in shown
    assert str(decoder_error) not in shown
    assert type(decoder_error).__name__ not in shown
    logged = [str(record.exc_info[1]) for record in caplog.records if record.exc_info]
    assert str(decoder_error) in logged

    # The panel's own four messages for a well-formed JSON text with a bad shape
    # still reach the user unchanged (they carry no exception text), one box each.
    own_messages = {
        '{"name": "procgen"}': "A script must be a JSON array of steps.",
        '[{"params": {}}]': "Each step needs a 'name' and optional 'params'/'seed'.",
        '[{"name": 5}]': "Step 'name' must be a string.",
        '[{"name": "procgen", "params": 3}]': "Step 'params' must be an object.",
    }
    for script, message in own_messages.items():
        before = len(mute_message_boxes)
        panel._editor.setPlainText(script)
        panel._on_run()
        assert [text for _kind, _title, text in mute_message_boxes[before:]] == [
            message
        ], script
        assert stack.count() == 0
