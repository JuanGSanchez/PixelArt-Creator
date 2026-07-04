"""Timelapse recording controls acceptance tests (REQ-P9-UI-009 / DATA-001).

Scenario SC-UI-009-1: start/stop recording captures one frame per committed
(forward) command; the recorded session persists via the defensive
``.pixtimelapse`` serialiser and replays to the SAME frame sequence; recording
pushes no undo entry (view/session state). Both themes via the autouse fixture.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QUndoCommand, QUndoStack

from pixelart_creator.data.timelapse_io import (
    TimelapseIOError,
    load_session,
    save_session,
)
from pixelart_creator.logic.timelapse import replay
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls


class _NoopCommand(QUndoCommand):
    """A do-nothing undoable command (drives forward index changes)."""

    def redo(self) -> None:  # noqa: D401
        pass

    def undo(self) -> None:
        pass


def _controls(qtbot):
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    return controls


# --- SC-UI-009-1: recording captures forward commands ----------------------- #


def test_sc_ui_009_1_records_one_frame_per_forward_command(qtbot):
    """SC-UI-009-1: each committed (forward) command records exactly one frame."""
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)  # start recording
    assert controls.is_recording() is True
    stack.push(_NoopCommand())
    stack.push(_NoopCommand())
    assert controls.frame_count() == 2


def test_sc_ui_009_1_undo_does_not_record(qtbot):
    """SC-UI-009-1: an undo (backward move) records no frame."""
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    stack.push(_NoopCommand())
    stack.push(_NoopCommand())
    assert controls.frame_count() == 2
    stack.undo()  # backward — must not append a frame
    assert controls.frame_count() == 2


def test_sc_ui_009_1_recording_pushes_no_undo_command(qtbot):
    """SC-UI-009-1: toggling/recording adds nothing to the document undo stack."""
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    # Only the explicit edit commands are on the stack — recording itself adds none.
    stack.push(_NoopCommand())
    assert stack.count() == 1
    assert controls.frame_count() == 1


# --- SC-UI-009-1 / DATA-001: persistence + reproducible replay -------------- #


def test_sc_ui_009_1_session_round_trips_and_replays_identically(qtbot, tmp_path):
    """SC-UI-009-1: save -> load yields an equal session that replays identically."""
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    for _ in range(3):
        stack.push(_NoopCommand())
    session = controls.session()
    assert len(session.frames) == 3

    target = save_session(session, tmp_path / "clip")
    assert target.suffix == ".pixtimelapse"
    reloaded = load_session(target)
    assert reloaded == session

    # Deterministic replay: a fixed renderer yields the identical frame sequence
    # for the reloaded session (reproducible-timelapse contract).
    frame = np.zeros((2, 2, 4), dtype=np.uint8)
    renderer = lambda _doc: frame.copy()  # noqa: E731
    seq_a = replay(reloaded, object(), renderer)
    seq_b = replay(reloaded, object(), renderer)
    assert len(seq_a) == 3
    assert all(np.array_equal(x, y) for x, y in zip(seq_a, seq_b))


def test_sc_ui_009_1_malformed_manifest_raises(tmp_path):
    """SC-UI-009-1: a malformed .pixtimelapse raises TimelapseIOError (no eval)."""
    bad = tmp_path / "broken.pixtimelapse"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(TimelapseIOError):
        load_session(bad)


def test_sc_ui_009_1_reset_clears_session(qtbot):
    """SC-UI-009-1: reset discards recorded frames and stops recording."""
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    stack.push(_NoopCommand())
    assert controls.frame_count() == 1
    controls.reset()
    assert controls.frame_count() == 0
    assert controls.is_recording() is False
