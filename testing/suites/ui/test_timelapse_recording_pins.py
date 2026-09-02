"""REGRESSION PIN — recording behaviour is unchanged (REQ-P9-UI-023).

``SC-UI-023-1``..``-5``, asserted against the **changed** widget (D-12 added
playback/save-refusal behaviour around the same recording path) so these are a
live gate, not a historical claim. Driven through a real :class:`Canvas_View`
+ ``QUndoStack`` — every recorded frame is a genuine pixel edit, never a
``QUndoCommand`` no-op stand-in — so the pins hold for real document mutation,
not merely for a synthetic command. Both themes via the autouse ``theme``
fixture; headless (``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

import numpy as np

from pixelart_creator.logic import timelapse as timelapse_logic
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _bound(qtbot, make_view):
    """A ``Timelapse_Controls`` bound to a real view/document/stack, recording off."""
    view, scene, stack = make_view()
    prepare_for_click(view)
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    document = scene._document
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    return controls, view, scene, stack, document


# --------------------------------------------------------------------------- #
# SC-UI-023-1 -- one frame per forward (committed) command                    #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_1_one_frame_per_forward_command(qtbot, make_view):
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    controls._record_button.setChecked(True)

    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    view.set_active_color(GREEN)
    click_pixel(view, 9, 9)
    view.set_active_color(BLUE)
    click_pixel(view, 14, 14)

    session = controls.session()
    assert len(session.frames) == 3
    assert [f.index for f in session.frames] == [0, 1, 2]  # contiguous


# --------------------------------------------------------------------------- #
# SC-UI-023-2 -- an undo records nothing                                      #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_2_undo_does_not_record(qtbot, make_view):
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    controls._record_button.setChecked(True)
    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    click_pixel(view, 9, 9)
    assert controls.frame_count() == 2

    stack.undo()  # a genuine backward move over a real command

    assert controls.frame_count() == 2  # no frame appended


# --------------------------------------------------------------------------- #
# SC-UI-023-3 -- recording pushes no undo command; document untouched by it   #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_3_toggling_recording_pushes_no_undo_command(qtbot, make_view):
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    before_bytes = np.ascontiguousarray(scene.active_buffer().data).tobytes()

    controls._record_button.setChecked(True)  # on
    controls._record_button.setChecked(False)  # off

    assert stack.count() == 0  # the toggle itself pushed nothing
    after_bytes = np.ascontiguousarray(scene.active_buffer().data).tobytes()
    assert after_bytes == before_bytes  # and mutated no document content

    # And once recording IS on, only the real edit commands land on the
    # stack -- recording adds no command of its own alongside them.
    controls._record_button.setChecked(True)
    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    assert stack.count() == 1
    assert controls.frame_count() == 1


# --------------------------------------------------------------------------- #
# SC-UI-023-4 -- exceeding MAX_TIMELAPSE_FRAMES stops recording with a notice #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_4_exceeding_max_frames_stops_recording_with_a_notice(
    qtbot, make_view, monkeypatch, mute_message_boxes
):
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    monkeypatch.setattr(timelapse_logic, "MAX_TIMELAPSE_FRAMES", 2)
    controls._record_button.setChecked(True)

    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    view.set_active_color(GREEN)
    click_pixel(view, 9, 9)
    assert controls.frame_count() == 2
    assert controls.is_recording() is True

    view.set_active_color(BLUE)
    click_pixel(view, 14, 14)  # the 3rd command -- record_frame raises at the cap

    assert controls.frame_count() == 2  # no frame beyond the bound
    assert controls.is_recording() is False  # recording stopped
    assert controls._record_button.isChecked() is False
    assert any(kind == "warning" for kind, _title, _text in mute_message_boxes)
    # The edit that triggered the stop was still applied normally.
    assert stack.count() == 3


# --------------------------------------------------------------------------- #
# SC-UI-023-5 -- reset() clears the session; persistence still round-trips    #
# --------------------------------------------------------------------------- #


def test_sc_ui_023_5_reset_clears_and_persistence_still_round_trips(
    qtbot, make_view, tmp_path
):
    """Persistence round trip -- re-keyed for identity (Q-21/Amendment 3).

    **Repaired 2026-08-18 (accounting gap closed here directly, rather than
    deferred to the sibling files this belongs beside; see the dispatch report
    for the finding).** ``controls.session()`` is identity-bearing (schema
    3) unconditionally, and the plain ``save_session``/
    ``load_session`` pair (schema-1 command-manifest-only, untouched by
    design) drops ``recording_id`` and every ``TimelapseFrame.frame_id`` on
    write -- it can no longer round-trip this session to an equal one.
    **Substitution (old beside new):**
      - old: ``target = save_session(session, tmp_path / "after-reset")`` /
        ``assert load_session(target) == session``
      - new: ``target = save_session_payload(session, {}, {}, tmp_path /
        "after-reset")`` / ``assert load_session_payload(target).session ==
        session``
    Empty ``snapshots``/``blobs`` are valid: nothing in this test calls the
    widget's own snapshot-building save path (``_build_payload_tables``), so
    every recorded frame's ``snapshot_id`` stays ``None`` and there is
    nothing for the payload tables to resolve. The round trip is now
    byte-for-byte equal, including ``recording_id`` and every frame's
    ``frame_id`` -- strictly stronger than the assertion it replaces; no
    assertion was dropped.
    """
    from pixelart_creator.data.timelapse_io import (
        load_session_payload,
        save_session_payload,
    )

    controls, view, scene, stack, document = _bound(qtbot, make_view)
    controls._record_button.setChecked(True)
    view.set_active_color(RED)
    click_pixel(view, 4, 4)
    assert controls.frame_count() == 1

    counts = []
    controls.frameCountChanged.connect(counts.append)
    controls.reset()

    assert controls.frame_count() == 0
    assert controls.is_recording() is False
    assert counts and counts[-1] == 0  # the count was emitted

    # A session recorded fresh after reset still round-trips byte-for-byte.
    controls._record_button.setChecked(True)
    click_pixel(view, 20, 20)
    click_pixel(view, 25, 25)
    session = controls.session()
    target = save_session_payload(session, {}, {}, tmp_path / "after-reset")
    assert load_session_payload(target).session == session
