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

from pixelart_creator.ui import failure_messages
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
    """SC-UI-004-1: an unknown-op script is rejected by the dispatcher (graceful
    error)."""
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
    """SC-UI-004-1: invalid JSON is rejected in-panel before any worker run (no
    exec)."""
    win = _window(qtbot)
    stack = win.active_tab().stack

    win._script_runner_panel._editor.setPlainText("{ this is not valid json")
    win._script_runner_panel._on_run()  # parse fails in-panel; no automation submitted

    assert stack.count() == 0
    assert any(kind == "warning" for kind, *_ in mute_message_boxes)
    assert not win._automation_controller.is_busy()


def _assert_sentence_on_its_own_line(shown: str, lead_in: str, sentence: str) -> None:
    """Fail unless ``shown`` is the lead-in, a line break and the sentence alone.

    REQ-L10N-UI-020 clause 1: the sentence never continues on the lead-in's line, so
    the lead-in line holds the lead-in and nothing of the sentence (clause 3: the
    lead-in keeps what it says, minus the space that stood before the sentence), and
    the sentence is the whole of what follows the line break, as the catalogue holds
    it (clause 2).
    """
    first, found, rest = shown.partition("\n")
    assert sentence not in first, f"{sentence!r} continues on the line of {lead_in!r}"
    assert found, f"{sentence!r} does not start on a line of its own: {shown!r}"
    assert first == lead_in, f"the lead-in line is {first!r}, not {lead_in!r}"
    assert rest == sentence, f"after {lead_in!r} the line is {rest!r}, not {sentence!r}"


def test_sc_ui_004_invalid_json_shows_the_sentence_and_no_exception_text(
    qtbot, mute_message_boxes, caplog
):
    """SC-UI-004-1 + REQ-L10N-UI-018: a rejected script never shows the parser's text.

    Invalid JSON is rejected in-panel: the box reads the lead-in "Invalid JSON:" and,
    on a line of its own after it (REQ-L10N-UI-020 clause 1), the sentence for the
    failure's kind (a ``json.JSONDecodeError`` is a ``ValueError``) in the active
    language, as the catalogue holds it (clause 2). Neither the decoder's own message
    nor its type name is in it, and the detail is logged. The four messages the panel
    writes itself for a malformed step are still shown as they were, and nothing is
    dispatched.
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
    assert sentence == "A value was not valid for this operation."
    _assert_sentence_on_its_own_line(shown, "Invalid JSON:", sentence)
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


def test_sc_ui_004_the_inline_junction_of_the_invalid_json_box_is_caught(
    qtbot, monkeypatch, mute_message_boxes
):
    """REQ-L10N-UI-020 control: the old inline junction fails the verdict.

    ``failure_on_own_line`` is replaced, at the seam the panel calls, by the
    composition the interface used before (the sentence in the placeholder, on the
    lead-in's line). The real panel is driven; the box reads
    ``Invalid JSON: <sentence>`` and the verdict that the test above applies must
    reject it, naming the sentence. Written beside literals that it accepts and
    rejects, so the verdict's two sides are both seen.
    """
    sentence = "A value was not valid for this operation."
    _assert_sentence_on_its_own_line(
        f"Invalid JSON:\n{sentence}", "Invalid JSON:", sentence
    )
    for fault in (
        f"Invalid JSON: {sentence}",  # the old composition
        f"Invalid JSON:{sentence}",  # no break at all
        f"Invalid JSON: \n{sentence}",  # the space left before the break
        f"Invalid JSON:\n{sentence}\n",  # a stray line after the sentence
        f"Invalid JSON:\n{sentence[0].lower()}{sentence[1:]}",  # not its catalogue form
    ):
        with pytest.raises(AssertionError):
            _assert_sentence_on_its_own_line(fault, "Invalid JSON:", sentence)

    monkeypatch.setattr(
        failure_messages,
        "failure_on_own_line",
        lambda template, placeholder, text: template.replace(placeholder, text),
    )
    win = _window(qtbot)
    win._script_runner_panel._editor.setPlainText("{ this is not valid json")
    win._script_runner_panel._on_run()
    boxes = [text for kind, _title, text in mute_message_boxes if kind == "warning"]
    assert boxes == [
        f"Invalid JSON: {sentence}"
    ], f"the plant did not reach the box: {boxes}"
    with pytest.raises(
        AssertionError, match="continues on the line of 'Invalid JSON:'"
    ):
        _assert_sentence_on_its_own_line(boxes[0], "Invalid JSON:", sentence)
