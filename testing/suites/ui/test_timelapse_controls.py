"""Timelapse recording controls acceptance tests (REQ-P9-UI-009 / DATA-001).

Scenario SC-UI-009-1: start/stop recording captures one frame per committed
(forward) command; the recorded session persists via the defensive
``.pixtimelapse`` serialiser and replays to the SAME frame sequence; recording
pushes no undo entry (view/session state). Both themes via the autouse fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QUndoCommand, QUndoStack

from pixelart_creator.data.timelapse_io import (
    TimelapseIOError,
    load_session,
    load_session_payload,
    save_session_payload,
)
from pixelart_creator.logic.timelapse import ReconstructionBlocker, reconstructability
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from pixelart_creator.ui.timelapse_playback import Snapshot_Document_Provider


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
    """SC-UI-009-1: save -> load yields an equal session (the round-trip pin).

    **Re-specified 2026-08-18 (plan §8.2).** The
    round-trip half is unchanged (the pin): a saved-then-reloaded session is
    an equal :class:`TimelapseSession`. The *replay* half is NOT re-asserted
    here as it originally was — this session is a **schema-1**
    (command-manifest-only) recording, and D-12 makes a schema-1 session
    genuinely unplayable (``REQ-P9-UI-019``(a)): it references a live history
    this reloaded session carries no payload for, so
    ``replay(reloaded, <some provider>, renderer)`` is no longer the correct
    call for it at all (a real ``DocumentProvider`` cannot place ANY of these
    frames from a bare reload). What replaces it is the honest verdict:
    ``reconstructability`` reports ``NO_PAYLOAD`` at frame 0, reached as a
    **value** (plan §8.2), never by string-matching a ``logic/`` reason. The
    replayable, payload-carrying case is covered end-to-end by
    ``testing/suites/ui/test_timelapse_reopened.py``.

    **Re-specified a second time, same day (identity re-keying, Q-21/Amendment
    3; an accounting gap closed here directly, rather than
    deferred to the sibling files this belongs beside; see the dispatch report
    for the finding).**
    ``Timelapse_Controls.__init__`` now calls ``new_session(recording_id=...)``
    unconditionally, so ``controls.session()`` is **never** schema-1
    any more -- every session it returns is identity-bearing (schema 3,
    ``TIMELAPSE_IDENTITY_SCHEMA_VERSION``). The plain ``save_session`` /
    ``load_session`` pair is, by this module's own docstring, the untouched
    schema-1 command-manifest-only writer: it carries neither
    ``recording_id`` nor any ``TimelapseFrame.frame_id`` across a write, so
    round-tripping a schema-3 session through it can never again be an equal
    session -- not a transient failure, a structural impossibility once the
    widget only mints identity-bearing sessions. It is also not the pairing
    the widget's own ``_on_save`` uses (``_build_payload_tables`` ->
    ``save_session_payload``), so asserting through it never matched real
    Save-button behaviour even before this re-key. **Substitution (old
    beside new):**
      - old: ``target = save_session(session, tmp_path / "clip")`` /
        ``reloaded = load_session(target)`` / ``assert reloaded == session``
      - new: ``target = save_session_payload(session, {}, {}, tmp_path / "clip")``
        / ``reloaded_payload = load_session_payload(target)`` /
        ``assert reloaded_payload.session == session``
    Empty ``snapshots``/``blobs`` are valid here because every frame is a
    synthetic ``_NoopCommand`` frame with no bound document, so each
    ``TimelapseFrame.snapshot_id`` is ``None`` (nothing to resolve). The
    round trip is now byte-for-byte equal, including ``recording_id`` and
    every frame's ``frame_id`` -- a **strictly stronger** pin than the one it
    replaces, never a weaker one; no assertion here was dropped. The
    ``reconstructability`` verdict is unchanged in shape and value from the
    original (still ``NO_PAYLOAD`` at frame 0): the SNAPSHOT substrate checks
    ``frame.snapshot_id is None`` **before** identity (``SC-D005-3``'s
    precedence), so an empty snapshot table still refuses for the same
    schema-1-era reason even though the frames now carry identity.
    """
    controls = _controls(qtbot)
    stack = QUndoStack()
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    for _ in range(3):
        stack.push(_NoopCommand())
    session = controls.session()
    assert len(session.frames) == 3

    target = save_session_payload(session, {}, {}, tmp_path / "clip")
    assert target.suffix == ".pixtimelapse"
    reloaded_payload = load_session_payload(target)
    assert reloaded_payload.session == session

    verdict = reconstructability(
        reloaded_payload.session,
        Snapshot_Document_Provider(reloaded_payload).extent(),
    )
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.NO_PAYLOAD
    assert verdict.first_unreachable_index == 0


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
