"""Reopened cross-session timelapse recording acceptance tests (D-12).

Covers ``SC-UI-024-1``..``-4`` (a saved, payload-carrying recording reopens and
plays through the SAME shipped controls, on a dedicated, unmistakably-labelled
display target that touches no open document) and ``SC-UI-019-4`` (a
payload-carrying file whose payload cannot fully resolve is refused with its
reason, never partially played) — driven **headlessly**
(``QT_QPA_PLATFORM=offscreen``), both themes via the autouse ``theme`` fixture.

"Restart" is modelled as a **fresh** :class:`Timelapse_Controls` /
:class:`Timelapse_Frame_View` pair reading the file a first instance wrote —
there is no in-memory state shared between them, exactly as a real process
restart would leave none.

**Repaired 2026-08-18 (Q-21/REQ-P9-LOGIC-022).** ``_record_and_save``'s
"ground truth" step used to read the recorded frames' content by stepping the
SAME, live, listened-to ``stack`` through a raw ``History_Document_Provider``
built outside the widget. That stepping is now itself visible to
``Timelapse_Controls._on_stack_index_changed`` (the forward-move eviction
watches every index change on its bound stack), so it silently evicted and
dropped frames from the very session ``_on_save`` was about to snapshot — a
bug in the TEST, not the product (self-corrected in the open, per this
dispatch's own report; it was the root cause behind every failure this module
had before the repair, not four independent ones). Fixed by suspending the
same ``_replaying`` guard the widget's own internal replay paths use, for the
span of that read.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QFileDialog

from pixelart_creator.data.timelapse_io import load_session_payload, save_session
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.timelapse import (
    ReconstructionBlocker,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    reconstructability,
    record_frame,
)
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from pixelart_creator.ui.timelapse_frame_view import Timelapse_Frame_View
from pixelart_creator.ui.timelapse_playback import (
    History_Document_Provider,
    Snapshot_Document_Provider,
)
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _renderer(document):
    buffer = composite_stack(document.frames[0].layers, document.width, document.height)
    return np.ascontiguousarray(buffer.data)


def _controls(qtbot):
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    return controls


def _record_and_save(qtbot, make_view, tmp_path, monkeypatch, name="clip"):
    """Record 3 real, distinct edits and save them as a schema-2 payload file.

    Returns ``(saved_path, expected_frames, controls, stack, document)`` where
    ``expected_frames`` is the ground-truth in-session composite of each
    recorded frame, captured via the same provider playback itself uses.
    """
    view, scene, stack = make_view()
    prepare_for_click(view)
    document = scene._document
    controls = _controls(qtbot)
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls.set_renderer(_renderer)
    controls._record_button.setChecked(True)

    view.set_active_color(RED)
    click_pixel(view, 5, 5)
    view.set_active_color(GREEN)
    click_pixel(view, 20, 20)
    view.set_active_color(BLUE)
    click_pixel(view, 40, 40)
    assert controls.frame_count() == 3
    # Recording has concluded (the Given is "a recording MADE and saved") --
    # stepping the SAME watched stack below to build the ground truth would
    # otherwise itself be recorded as new commits (a real defect, reported
    # separately in testing/suites/ui/test_timelapse_playback.py's
    # test_req_p9_ui_018_playing_while_still_recording_must_not_modify_the_session).
    controls._record_button.setChecked(False)

    provider = History_Document_Provider(stack, lambda: document)
    # Stepping the SAME, live, listened-to stack here is otherwise
    # indistinguishable, to the widget's own forward-move eviction, from
    # a real commit or discard boundary (REQ-P9-UI-018) -- suspend its
    # bookkeeping for this read exactly as the widget's own internal replay
    # paths do (fixed 2026-08-18: this ground-truth read used to mutate
    # -- and shrink -- the very session ``_on_save`` was about to snapshot,
    # a bug in the TEST, not the product; corrected in the open per this
    # dispatch's own report).
    session_before = controls.session()
    controls._replaying = True
    try:
        with provider:
            expected = tuple(
                _renderer(provider(frame)) for frame in controls.session().frames
            )
    finally:
        controls._replaying = False
    assert controls.session() == session_before  # the read above changed nothing

    saved_path = tmp_path / name
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(saved_path), "")),
    )
    controls._save_button.click()  # the real _on_save path

    return saved_path.with_suffix(".pixtimelapse"), expected, controls, stack, document


# --------------------------------------------------------------------------- #
# SC-UI-024-1 -- record -> save -> "restart" -> open -> play                  #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_1_full_workflow_matches_the_in_session_sequence(
    qtbot, make_view, tmp_path, monkeypatch
):
    """SC-UI-024-1: a reopened recording replays the SAME sequence in-session did."""
    saved, expected, _old_controls, _stack, _doc = _record_and_save(
        qtbot, make_view, tmp_path, monkeypatch
    )
    assert saved.exists()

    # A FRESH controls instance + a fresh frame view -- models a restarted app.
    reopened = _controls(qtbot)
    reopened.set_renderer(_renderer)
    frame_view = Timelapse_Frame_View()
    qtbot.addWidget(frame_view)
    displayed = []
    reopened.frameReady.connect(frame_view.display_frame)
    reopened.frameReady.connect(lambda arr: displayed.append(np.array(arr)))

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(saved), ""))
    )
    reopened._load_button.click()  # the real _on_load path

    assert reopened._play_button.isEnabled() is True  # a payload-carrying file plays
    reopened._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(displayed) >= 3, timeout=5000)
    reopened._stop_button.click()

    assert len(displayed) == 3
    for got, want in zip(displayed, expected):
        assert np.array_equal(got, want)

    # Play/pause, seek and speed behave exactly as the in-session case.
    reopened._play_button.setChecked(True)
    reopened._pause_playback()
    seen = []
    reopened.frameReady.connect(lambda arr: seen.append(np.array(arr)))
    reopened._seek_slider.setValue(2)  # a genuine change (slider starts at 0)
    reopened._seek_slider.setValue(0)  # seek back to the first recorded frame
    assert np.array_equal(seen[-1], expected[0])
    reopened._speed_combo.setCurrentIndex(0)
    reopened._on_stop()


# --------------------------------------------------------------------------- #
# SC-UI-024-2 -- playing a reopened recording disturbs no open document       #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_2_playing_a_reopened_recording_does_not_disturb_open_work(
    qtbot, make_view, tmp_path, monkeypatch
):
    """SC-UI-024-2: an unrelated open document's stack/content are untouched."""
    saved, _expected, _rec_controls, _rec_stack, _rec_doc = _record_and_save(
        qtbot, make_view, tmp_path, monkeypatch
    )

    # A SEPARATE, currently open document + its own controls instance -- the
    # realistic case: the user has document B open and opens a saved file.
    view_b, scene_b, stack_b = make_view()
    prepare_for_click(view_b)
    document_b = scene_b._document
    view_b.set_active_color(RED)
    click_pixel(view_b, 3, 3)  # one real edit of "the user's current work"

    controls = _controls(qtbot)
    controls.bind_undo_stack(
        stack_b, document_getter=lambda: document_b, document_id=id(document_b)
    )
    controls.set_renderer(_renderer)
    before_depth, before_index, before_clean = (
        stack_b.count(),
        stack_b.index(),
        stack_b.isClean(),
    )
    before_bytes = np.ascontiguousarray(scene_b.active_buffer().data).tobytes()

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(saved), ""))
    )
    controls._load_button.click()

    received = []
    controls.frameReady.connect(lambda arr: received.append(arr))
    controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    controls._stop_button.click()

    assert stack_b.count() == before_depth  # no QUndoCommand was pushed
    assert stack_b.index() == before_index
    assert stack_b.isClean() == before_clean
    after_bytes = np.ascontiguousarray(scene_b.active_buffer().data).tobytes()
    assert after_bytes == before_bytes


# --------------------------------------------------------------------------- #
# SC-UI-024-3 -- the reopened display target is unmistakably labelled         #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_3_reopened_view_identifies_itself_as_not_the_active_document(qtbot):
    """SC-UI-024-3: the display target says "reopened recording", not "your work"."""
    frame_view = Timelapse_Frame_View()
    qtbot.addWidget(frame_view)

    assert "reopened" in frame_view.windowTitle().lower()
    assert frame_view.accessibleName()
    assert "reopened" in frame_view.accessibleName().lower()
    banner = frame_view._banner.text().lower()
    assert "reopened" in banner
    assert "not" in banner  # "...this is not your current document"
    assert "reopened" in frame_view._banner.accessibleDescription().lower()

    frame_view.display_frame(np.zeros((2, 2, 4), dtype=np.uint8))
    # The frame view touches no document -- it only owns a QPixmap it painted.
    assert frame_view._last_pixmap is not None


# --------------------------------------------------------------------------- #
# SC-UI-024-4 -- schema-1 and payload-carrying outcomes sit side by side      #
# --------------------------------------------------------------------------- #


def test_sc_ui_024_4_the_two_loaded_outcomes_are_distinguishable(
    qtbot, make_view, tmp_path, monkeypatch
):
    """SC-UI-024-4: one surface, two honestly different outcomes."""
    payload_path, _expected, _c, _s, _d = _record_and_save(
        qtbot, make_view, tmp_path, monkeypatch, name="playable"
    )
    schema1_session = record_frame(new_session(), command_id=1)
    schema1_path = save_session(schema1_session, tmp_path / "old")

    controls = _controls(qtbot)
    controls.set_renderer(_renderer)

    controls.load_reopened_recording(load_session_payload(payload_path))
    assert controls._play_button.isEnabled() is True
    assert controls._reason_label.isVisible() is False

    controls.load_reopened_recording(load_session_payload(schema1_path))
    assert controls._play_button.isEnabled() is False
    assert controls._reason_label.text() == controls.tr(
        "This recording was saved in a form that cannot be replayed."
    )


# --------------------------------------------------------------------------- #
# SC-UI-019-4 -- a payload-carrying file whose payload cannot fully resolve   #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_4_incomplete_payload_refused_names_first_bad_frame_no_leak(
    qtbot, make_view, tmp_path, monkeypatch, mute_message_boxes
):
    """SC-UI-019-4: PAYLOAD_INCOMPLETE is refused; nothing played; no detail leak.

    Models "the payload-carrying file's saved data is incomplete" at the
    ``ui/`` layer: the loaded payload's own snapshot table cannot resolve
    every frame the SESSION records — the shape ``reconstructability``
    reports as ``PAYLOAD_INCOMPLETE`` (plan §8.2), asserted here as a VALUE,
    never by reading any exception or ``detail`` string.
    """
    saved, _expected, _c, _s, _d = _record_and_save(
        qtbot, make_view, tmp_path, monkeypatch
    )
    payload = load_session_payload(saved)

    controls = _controls(qtbot)
    controls.set_renderer(_renderer)
    controls.load_reopened_recording(payload)
    assert controls._play_button.isEnabled() is True  # sane before the corruption

    # Extend the SESSION with one more frame referencing a snapshot id absent
    # from this payload's own table -- the payload itself stays well-formed;
    # only the session now outruns what it can resolve. The extra frame DOES
    # carry a (locally-fabricated but valid-shaped) identity: NO_IDENTITY is
    # evaluated before PAYLOAD_INCOMPLETE (precedence, SC-D005-3), so an
    # identity-less frame would take that branch instead and this test would
    # no longer be exercising PAYLOAD_INCOMPLETE at all.
    extra = TimelapseFrame(
        index=3,
        command_id=99,
        snapshot_id="not-in-this-payload",
        frame_id=f"{controls._session.recording_id}:99",
    )
    controls._session = TimelapseSession(
        schema_version=controls._session.schema_version,
        frames=controls._session.frames + (extra,),
    )
    controls._update_play_availability()

    verdict = reconstructability(
        controls._session, Snapshot_Document_Provider(payload).extent()
    )
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.PAYLOAD_INCOMPLETE
    assert verdict.first_unreachable_index == 3
    assert verdict.detail  # developer-only detail exists on the verdict...

    assert controls._play_button.isEnabled() is False
    reason = controls._reason_label.text()
    assert reason == controls.tr(
        "This recording's saved data is incomplete and cannot be fully replayed."
    )
    # ...and it never appears anywhere in the visible surface, including any
    # tooltip -- the boundary the whole design rests on (plan §8.2 B-3).
    assert verdict.detail not in reason
    for widget in (
        controls._record_button,
        controls._save_button,
        controls._load_button,
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
        controls._reason_label,
        controls._count_label,
    ):
        assert verdict.detail not in widget.toolTip()

    controls._start_or_resume_playback()
    assert controls._rendered_frames == ()  # nothing was played in its place
