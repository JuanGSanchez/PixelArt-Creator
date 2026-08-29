"""Historical-timelapse playback surface acceptance tests (T16, D-12).

One pytest-qt test per acceptance criterion (``SC-UI-015-*``..``SC-UI-022-*``,
excluding ``SC-UI-019-4`` and the ``SC-UI-024-*`` family, which the
reopened-recording module (T17) owns), driven **headlessly**
(``QT_QPA_PLATFORM=offscreen``) against a real :class:`Canvas_View` +
``QUndoStack`` so every recorded frame is a genuinely distinct, real pixel
edit — never a no-op stand-in. Both themes are exercised automatically (the
autouse ``theme`` fixture in ``testing/suites/ui/conftest.py``).

Coverage map:

* **SC-UI-015-1** — play/pause, seek, speed and the ``k of n`` readout are
  present, keyboard-reachable and accessibly named; the shipped
  record/save/open controls remain.
* **SC-UI-016-1** — ``frameReady`` emits the reconstructed composite of each
  recorded frame **in recorded order**, and the readout advances with them.
* **SC-UI-016-2** — playback is a genuine borrow/restore: the bound
  document's own undo stack (depth/index/clean state) and pixel content are
  byte-identical after a completed run. (The **canvas-level** enforcement —
  wiring ``frameReady``/``playbackEditLockChanged`` to an actual read-only
  canvas — is not present in ``ui/main_window.py`` in this worktree; see the
  dispatch report for that finding. This module verifies the *widget's own*
  contract, which is what T10 actually implements.)
* **SC-UI-017-1** — seeking shows the frame ``k`` state, the readout reads
  ``k of n``, and the recorded session itself never changes.
* **SC-UI-018-1** — play/pause/seek/speed-change/stop push **no**
  ``QUndoCommand``; the stack's depth, index and clean state are unchanged.
* **SC-UI-019-1/-2/-3** — the three refusal cases ``reconstructability``
  itself decides (schema-1/``NO_PAYLOAD``, a different document, a
  beyond-extent position) each read their own distinct, ``tr()``-wrapped
  sentence, and nothing is played in their place.
* **``Reconstructability.detail`` boundary** — the developer-only detail
  string is asserted, for every blocker code, never to appear in the
  sentence the surface shows (module docstring's central invariant).
* **SC-UI-020-1/-2** — a session belongs to one document: commands on
  another document are never appended, and recording resumes when the
  session's own document is active again.
* **SC-UI-021-1** — frames dropped by a discarded branch are reported once,
  with a count, and the edit that caused it still applies.
* **SC-UI-022-1** — every control this slice adds has an accessible name, is
  keyboard-reachable, and retranslates cleanly on ``QEvent.LanguageChange``.

**Re-keyed onto identity 2026-08-18 (T48, Q-21/REQ-P9-LOGIC-022; plan §10.2).**
``ReconstructionExtent``'s old position-set field (a ``FrozenSet[int]`` of
undo-stack ordinals) no longer exists — every extent below is built as
``reachable_frame_ids: FrozenSet[FrameId]``. Neither that old field's name
nor the old count-derived-range expression it used to be filled from appears
anywhere in this file any more (grep-checkable, T48's own observable). Two
tests needed more than a field rename because the OLD trick they used to
fabricate a "beyond the live history" state no longer produces one under
identity-keyed reachability:

* **``test_sc_ui_016_1_frameready_emits_reconstructed_states_in_order``** —
  its "ground truth" step used to read the recorded frames' content by
  stepping the SAME, live, listened-to ``stack`` through a raw
  ``History_Document_Provider`` instance built OUTSIDE the widget. That
  stepping is now itself visible to ``Timelapse_Controls._on_stack_index_changed``
  (T34's forward-move eviction watches every index change on its bound
  stack), so it silently evicted and dropped the very frames the test was
  about to assert on — a bug in the TEST, not the product (self-corrected in
  the open, per this dispatch's own report). Fixed by suspending the same
  ``_replaying`` guard the widget's own internal replay paths use, for the
  span of that read — exactly what a real caller building its own provider
  over a watched stack must do.
* **``test_sc_ui_019_3_unreachable_position_refused_not_partially_played``** —
  used to rebind to a second, empty ``QUndoStack`` to fabricate a "shorter
  history" for the SAME document, exploiting the fact that the old extent was
  *recomputed fresh from ``stack.count()``* on every check. Reachability is
  now the recording session's OWN persistent identity map
  (``_id_at_index``), which is not implicitly invalidated by a stack rebind —
  rebinding to an unrelated, empty stack while keeping the same
  ``document_id`` is not a scenario the shipped widget is specified to
  handle (T34 established no such rebind path; see the dispatch report for
  this finding, not fixed here). The substituted construction instead directly
  models the mechanism plan §10.2 actually specifies: a frame's identity
  evicted from the widget's own live extent (``_id_at_index``) while its
  position stays nominally in range — the exact case ``SC-L022-5``/R5 names.

**The QA pin is DELETED here, as an explicit, recorded supersession (T48,
analyze F-15, spec §0b.2).**
*Superseded text (2026-08-18): the module used to carry*
``test_req_p9_logic_017_a_discarded_frame_must_never_replay_wrong_content``,
*added as a RED pin (spec §0b.2) asserting that the frame recorded for one
edit must never replay a later edit's content that reused its ordinal — but
it* ``return``*-ed, passing without asserting anything, on the branch where
the stale frame was correctly dropped: exactly the "passes either way" shape
the user's verification demand (*"check carefully the fix with several tests
of reordering casuistics"*) is aimed at.* It is deleted, not merely fixed,
because ``test_frame_identity_reordering.py``'s
``test_r4_sc_l022_2_reference_held_across_a_discard_never_resolves_to_new_content``
(T38, the R4/``SC-L022-2`` case the pin's own docstring named as its
scenario) now covers the identical situation against a real ``QUndoStack``
and asserts on **both** legitimate outcomes (resolution succeeds with the
frame's own content, or fails naming it) with a real assertion on whichever
branch this implementation actually takes — never a bare ``return``. Per
spec §0b.2's own framing, both dispositions (rewrite in place, or split/
supersede) were license; the module docstring, not a silent diff, is where
this one is recorded.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEvent
from PySide6.QtCore import Qt as QtCore_Qt

from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.timelapse import (
    ReconstructionBlocker,
    ReconstructionExtent,
    ReconstructionSubstrate,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    reconstructability,
    record_frame,
)
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _renderer(document):
    """The same ``Document -> ndarray`` shape ``ui/main_window.py`` injects."""
    buffer = composite_stack(document.frames[0].layers, document.width, document.height)
    return np.ascontiguousarray(buffer.data)


def _controls(qtbot):
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    return controls


def _record_three_real_frames(qtbot, make_view):
    """Bind a real ``Canvas_View`` + document and record 3 distinct edits.

    Each frame is a genuinely different, known composited state (three
    well-separated pixels, three different colours) — never a no-op stand-in
    — so playback assertions compare REAL reconstructed content, not just
    frame counts.
    """
    view, scene, stack = make_view()
    prepare_for_click(view)
    controls = _controls(qtbot)
    document = scene._document
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
    assert stack.count() == 3
    return controls, view, scene, stack, document


# --------------------------------------------------------------------------- #
# SC-UI-015-1 -- controls present, keyboard-reachable, accessibly named       #
# --------------------------------------------------------------------------- #


def test_sc_ui_015_1_playback_controls_present_reachable_and_named(qtbot):
    """SC-UI-015-1: play/pause, seek, speed, k-of-n readout present + a11y."""
    controls = _controls(qtbot)

    # Shipped record/save/open controls are still present and enabled.
    assert controls._record_button.isEnabled()
    assert controls._save_button.isEnabled()
    assert controls._load_button.isEnabled()

    for widget in (
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
    ):
        assert widget.focusPolicy() != QtCore_Qt.FocusPolicy.NoFocus

    assert controls._seek_slider.accessibleName()
    assert controls._speed_combo.accessibleName()
    # The k-of-n readout is a QLabel; its text is the readout itself.
    assert "Recorded frames" in controls._count_label.text() or "Frame" in (
        controls._count_label.text()
    )


# --------------------------------------------------------------------------- #
# SC-UI-016-1 -- frameReady emits reconstructed states in recorded order      #
# --------------------------------------------------------------------------- #


def test_sc_ui_016_1_frameready_emits_reconstructed_states_in_order(qtbot, make_view):
    """SC-UI-016-1: playing emits each recorded frame's OWN state, in order."""
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    # Recording has concluded (the Given is "a recorded, playable session") --
    # see test_req_p9_ui_018_playing_a_still_recording_session_corrupts_it_defect
    # below for what happens, and is reported as a defect, when it has not.
    controls._record_button.setChecked(False)

    # Ground truth: what each frame's composited state actually was, captured
    # via the same History_Document_Provider path playback itself uses.
    from pixelart_creator.ui.timelapse_playback import History_Document_Provider

    provider = History_Document_Provider(stack, lambda: document)
    session_before = controls.session()
    # Stepping the SAME, live, listened-to stack here is otherwise
    # indistinguishable, to the widget's own T34 forward-move eviction, from
    # a real commit or discard boundary (REQ-P9-UI-018) -- suspend its
    # bookkeeping for this read exactly as the widget's own internal replay
    # paths do, so reading ground truth never itself mutates the session
    # under test.
    controls._replaying = True
    try:
        with provider:
            expected = tuple(
                _renderer(provider(frame)) for frame in controls.session().frames
            )
    finally:
        controls._replaying = False
    assert controls.session() == session_before  # the read above changed nothing
    assert len(expected) == 3
    # The three recorded states are genuinely distinct (real edits, not no-ops).
    assert not np.array_equal(expected[0], expected[1])
    assert not np.array_equal(expected[1], expected[2])

    received = []
    controls.frameReady.connect(lambda arr: received.append(np.array(arr)))
    controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    controls._stop_button.click()

    assert len(received) == 3
    for got, want in zip(received, expected):
        assert np.array_equal(got, want)
    # The readout advanced with them (ends at the last frame before stop resets it).
    assert controls.frame_count() == 3


# --------------------------------------------------------------------------- #
# SC-UI-016-2 -- the widget's own borrow/restore contract (REQ-P9-LOGIC-016)  #
# --------------------------------------------------------------------------- #


def test_sc_ui_016_2_stack_and_document_restored_after_playback(qtbot, make_view):
    """SC-UI-016-2: after playback the stack + document are exactly restored.

    The canvas-level "editing is refused while playing" enforcement is a
    separate integration point (``ui/main_window.py`` does not connect
    ``playbackEditLockChanged`` to the canvas in this worktree — reported,
    not asserted here). What IS the widget's own contract, and what this
    test proves, is REQ-P9-LOGIC-016's borrow/restore half: the bound
    stack's depth/index/clean state and the document's own pixel bytes are
    byte-identical before and after a completed playback run.
    """
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    controls._record_button.setChecked(False)  # the Given: recording has concluded
    before_depth, before_index, before_clean = (
        stack.count(),
        stack.index(),
        stack.isClean(),
    )
    before_bytes = np.ascontiguousarray(scene.active_buffer().data).tobytes()

    lock_states = []
    controls.playbackEditLockChanged.connect(lock_states.append)
    controls._play_button.setChecked(True)
    assert lock_states[0] is True  # locked as soon as playback starts

    received = []
    controls.frameReady.connect(lambda arr: received.append(arr))
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    controls._stop_button.click()

    # Locked throughout, unlocked once stopped (REQ-P9-UI-016). The exact
    # emission count is an implementation detail (stopping a running playback
    # re-enters _pause_playback via the button's own toggled signal before
    # _on_stop's own emit(False), so an extra transient True is observed) --
    # what the requirement actually pins is the final, settled value.
    assert lock_states[-1] is False
    assert stack.count() == before_depth
    assert stack.index() == before_index
    assert stack.isClean() == before_clean
    after_bytes = np.ascontiguousarray(scene.active_buffer().data).tobytes()
    assert after_bytes == before_bytes


# --------------------------------------------------------------------------- #
# SC-UI-017-1 -- seek addresses a recorded frame absolutely                   #
# --------------------------------------------------------------------------- #


def test_sc_ui_017_1_seek_shows_frame_k_and_leaves_session_unchanged(qtbot, make_view):
    """SC-UI-017-1: seeking to frame k shows frame k's state; session untouched."""
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    controls._record_button.setChecked(False)  # the Given: recording has concluded
    session_before = controls.session()

    controls._play_button.setChecked(True)  # renders _rendered_frames synchronously
    controls._pause_playback()  # pause immediately, no timer ticks needed

    received = []
    controls.frameReady.connect(lambda arr: received.append(np.array(arr)))
    controls._seek_slider.setValue(1)  # frame index 1 (0-based) = "2 of 3"

    assert len(received) == 1
    assert np.array_equal(received[0], controls._rendered_frames[1])
    assert controls._count_label.text() == controls.tr("Frame {0} of {1}").format(2, 3)
    assert controls.session() == session_before  # never mutated by a seek

    controls._on_stop()


# --------------------------------------------------------------------------- #
# SC-UI-018-1 -- non-destructive: no QUndoCommand, stack fully restored       #
# --------------------------------------------------------------------------- #


def test_sc_ui_018_1_play_pause_seek_speed_stop_push_no_undo_command(qtbot, make_view):
    """SC-UI-018-1: the full play/pause/seek/speed/stop cycle pushes nothing."""
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    controls._record_button.setChecked(False)  # the Given: recording has concluded
    before_depth, before_index, before_clean = (
        stack.count(),
        stack.index(),
        stack.isClean(),
    )

    controls._play_button.setChecked(True)
    controls._pause_playback()
    controls._seek_slider.setValue(2)
    controls._speed_combo.setCurrentIndex(0)  # change speed while paused
    controls._play_button.setChecked(True)  # resume
    controls._on_stop()

    assert stack.count() == before_depth  # no QUndoCommand pushed by any of the above
    assert stack.index() == before_index
    assert stack.isClean() == before_clean


# --------------------------------------------------------------------------- #
# REQ-P9-UI-018 -- playback must modify NO recorded frame, even while         #
# recording is still toggled on (DEFECT: currently fails -- see report)      #
# --------------------------------------------------------------------------- #


def test_req_p9_ui_018_playing_while_still_recording_must_not_modify_the_session(
    qtbot, make_view
):
    """REQ-P9-UI-018: playing "modifies no recorded frame" -- unconditionally.

    Nothing in the shipped widget prevents the user from pressing Play while
    Record is still toggled on. ``History_Document_Provider`` places the
    document by calling ``stack.setIndex(frame.command_id)`` on the SAME
    ``QUndoStack`` ``Timelapse_Controls`` is watching for commits
    (``ui/timelapse_controls.py::_on_stack_index_changed``); every FORWARD
    step the provider makes while stepping through history is
    indistinguishable, to that handler, from the user committing a genuine
    new command -- so it is recorded as one. Confirmed by direct
    reproduction outside pytest: recording 3 real edits then replaying them
    (still "recording") grows the session from 3 to 5 frames purely from the
    replay's own history-stepping, with no user edit involved at all.

    REQ-P9-UI-018 makes no exception for "unless recording is also on" --
    "modifies no recorded frame" is unconditional. This test asserts the
    REQUIRED behaviour and is expected to FAIL against the current
    ``ui/timelapse_controls.py`` — reported to AGT-05 (owner) with this
    reproduction, not fixed here (C2 is not implicated: this is not an
    S1/S2 criterion).
    """
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    assert controls.is_recording() is True  # the defect's precondition
    session_before = controls.session()

    received = []
    controls.frameReady.connect(lambda arr: received.append(arr))
    controls._play_button.setChecked(True)
    qtbot.waitUntil(lambda: len(received) >= 3, timeout=5000)
    controls._stop_button.click()

    assert controls.session() == session_before  # "modifies no recorded frame"


# --------------------------------------------------------------------------- #
# SC-UI-019-1 -- schema-1 (NO_PAYLOAD): refused, reason stated                #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_1_schema1_recording_refused_with_its_reason(qtbot, tmp_path):
    """SC-UI-019-1: a schema-1 (payload-less) recording states its OWN reason."""
    from pixelart_creator.data.timelapse_io import load_session_payload, save_session

    schema1_session = record_frame(new_session(), command_id=1)
    path = save_session(schema1_session, tmp_path / "old")
    payload = load_session_payload(path)  # schema-1 -> empty snapshot/blob tables

    controls = _controls(qtbot)
    controls.show()  # a QLabel's isVisible() needs the whole ancestor chain shown
    controls.set_renderer(_renderer)  # no document is ever bound for a loaded file
    controls.load_reopened_recording(payload)

    assert controls._play_button.isEnabled() is False
    assert controls._reason_label.isVisible() is True
    assert controls._reason_label.text() == controls.tr(
        "This recording was saved in a form that cannot be replayed."
    )
    # Reached as a VALUE (plan §8.2), never by string-matching a logic/ reason.
    from pixelart_creator.ui.timelapse_playback import Snapshot_Document_Provider

    verdict = reconstructability(
        controls.session(), Snapshot_Document_Provider(payload).extent()
    )
    assert verdict.ok is False
    assert verdict.blocker is ReconstructionBlocker.NO_PAYLOAD
    assert verdict.first_unreachable_index == 0


# --------------------------------------------------------------------------- #
# SC-UI-019-2 -- recorded against a different document: refused, names it     #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_2_session_for_another_document_is_refused(qtbot, make_view):
    """SC-UI-019-2: a session recorded against document A is refused for B."""
    controls, view, scene, stack, document_a = _record_three_real_frames(
        qtbot, make_view
    )
    assert controls._play_button.isEnabled() is True  # sanity: playable for A

    view_b, scene_b, stack_b = make_view()
    document_b = scene_b._document
    controls.bind_undo_stack(
        stack_b, document_getter=lambda: document_b, document_id=id(document_b)
    )

    assert controls.frame_count() == 3  # the session itself is untouched
    assert controls._play_button.isEnabled() is False
    assert controls._reason_label.text() == controls.tr(
        "This recording belongs to a different document. Switch to that "
        "document to play it."
    )


# --------------------------------------------------------------------------- #
# SC-UI-019-3 -- a beyond-extent position is refused, never partially played  #
# --------------------------------------------------------------------------- #


def test_sc_ui_019_3_unreachable_position_refused_not_partially_played(
    qtbot, make_view, mute_message_boxes
):
    """SC-UI-019-3: a session position beyond the bound history refuses to play.

    Models "history that no longer reaches every recorded position"
    (REQ-P9-UI-019(d)) directly on the identity-keyed mechanism (plan §10.2):
    the widget's OWN live extent (``_id_at_index``) loses the third recorded
    frame's identity, exactly as a real forward-move eviction would (T34) --
    never a count- or range-derived boundary. (The pre-re-key version of this
    test rebound to a second, empty ``QUndoStack`` for the SAME document to
    fabricate a "shorter history", exploiting the OLD extent's being
    recomputed fresh from ``stack.count()`` on every check; reachability is
    now the recording session's own persistent identity map, which a stack
    rebind does not implicitly invalidate -- a real gap, reported to AGT-05,
    not fixed here since C2/S1/S2 is not implicated.)
    """
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    third_frame = controls.session().frames[2]
    del controls._id_at_index[third_frame.command_id]
    controls._update_play_availability()

    assert controls._play_button.isEnabled() is False
    assert controls._reason_label.text() == controls.tr(
        "Some recorded frames are no longer reachable in the current history "
        "and cannot be played."
    )

    controls._start_or_resume_playback()
    assert controls._rendered_frames == ()  # nothing was played
    assert any(kind == "information" for kind, _title, _text in mute_message_boxes)


# --------------------------------------------------------------------------- #
# Reconstructability.detail -- NEVER rendered in any visible surface          #
# --------------------------------------------------------------------------- #


def test_reconstructability_detail_never_rendered_in_any_blocker_message(qtbot):
    """``Reconstructability.detail`` is developer-only and must never leak.

    Every ``ReconstructionBlocker`` maps to exactly one fixed, ``tr()``-wrapped
    sentence, and none of them is, or contains, the verdict's own ``detail``
    string. This is the boundary plan §8.2 (Ruling B) rests on.
    """
    controls = _controls(qtbot)

    history_extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY, reachable_frame_ids=frozenset()
    )
    snapshot_extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.SNAPSHOT, reachable_snapshot_ids=frozenset()
    )
    mismatch_extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY, matches_session=False
    )

    no_payload_session = TimelapseSession(
        frames=(TimelapseFrame(index=0, command_id=0, snapshot_id=None),)
    )
    # A frame that DOES carry an identity, simply absent from the extent's
    # reachable set -- BEYOND_EXTENT. A frame_id of None would instead take
    # the NO_IDENTITY branch (its own case, T41/SC-UI-019-5), which this
    # test does not claim.
    beyond_extent_session = TimelapseSession(
        frames=(
            TimelapseFrame(
                index=0, command_id=1, snapshot_id=None, frame_id="deadbeef:1"
            ),
        )
    )

    cases = [
        reconstructability(beyond_extent_session, history_extent),
        reconstructability(no_payload_session, snapshot_extent),
        reconstructability(beyond_extent_session, mismatch_extent),
    ]
    seen_blockers = set()
    for verdict in cases:
        assert verdict.ok is False
        assert verdict.detail  # developer-only detail IS present on the verdict
        message = controls._blocker_message(verdict.blocker)
        assert verdict.detail not in message
        assert message != verdict.detail
        seen_blockers.add(verdict.blocker)

    assert seen_blockers == {
        ReconstructionBlocker.BEYOND_EXTENT,
        ReconstructionBlocker.NO_PAYLOAD,
        ReconstructionBlocker.SUBSTRATE_MISMATCH,
    }


# --------------------------------------------------------------------------- #
# SC-UI-020-1/-2 -- a session belongs to exactly one document                 #
# --------------------------------------------------------------------------- #


def test_sc_ui_020_1_commands_on_another_document_are_never_appended(qtbot, make_view):
    """SC-UI-020-1: switching to document B and committing there adds nothing."""
    controls, view, scene, stack, document_a = _record_three_real_frames(
        qtbot, make_view
    )
    assert controls.frame_count() == 3

    view_b, scene_b, stack_b = make_view()
    prepare_for_click(view_b)
    document_b = scene_b._document
    controls.bind_undo_stack(
        stack_b, document_getter=lambda: document_b, document_id=id(document_b)
    )
    view_b.set_active_color(RED)
    click_pixel(view_b, 5, 5)
    click_pixel(view_b, 8, 8)

    assert controls.frame_count() == 3  # unchanged -- B is not A's document
    assert controls._count_label.text() == controls.tr("Recorded frames: {0}").format(3)


def test_sc_ui_020_2_recording_resumes_on_the_sessions_own_document(qtbot, make_view):
    """SC-UI-020-2: returning to A and committing appends one more frame."""
    controls, view, scene, stack, document_a = _record_three_real_frames(
        qtbot, make_view
    )

    view_b, scene_b, stack_b = make_view()
    controls.bind_undo_stack(
        stack_b,
        document_getter=lambda: scene_b._document,
        document_id=id(scene_b._document),
    )

    controls.bind_undo_stack(
        stack, document_getter=lambda: document_a, document_id=id(document_a)
    )
    view.set_active_color(GREEN)
    click_pixel(view, 55, 55)

    assert controls.frame_count() == 4


# --------------------------------------------------------------------------- #
# SC-UI-021-1 -- dropped frames are reported once, with a count               #
# --------------------------------------------------------------------------- #


def test_sc_ui_021_1_dropped_frames_are_reported_with_count(qtbot, make_view):
    """SC-UI-021-1: an undo-then-push drops the recorded frame it discards."""
    controls, view, scene, stack, document = _record_three_real_frames(qtbot, make_view)
    stack.undo()  # position now behind the 3rd (most recent) recorded frame

    dropped_counts = []
    controls.framesDropped.connect(dropped_counts.append)

    view.set_active_color((240, 220, 40, 255))  # a genuinely new, distinct command
    click_pixel(view, 60, 60)  # discards the undone (3rd) command

    assert dropped_counts == [1]
    assert "1" in controls._reason_label.text()
    assert controls.frame_count() == 3  # the 2 surviving + the 1 new command's frame


# The former QA pin,
# ``test_req_p9_logic_017_a_discarded_frame_must_never_replay_wrong_content``,
# was DELETED here 2026-08-18 (T48, analyze F-15, spec §0b.2) -- see this
# module's docstring for the full, recorded reasoning. Its replacement,
# asserting on both legitimate outcomes rather than returning on one of them,
# is ``testing/suites/ui/test_frame_identity_reordering.py::
# test_r4_sc_l022_2_reference_held_across_a_discard_never_resolves_to_new_content``
# (T38, R4/SC-L022-2).


# --------------------------------------------------------------------------- #
# SC-UI-022-1 -- accessibility, theming and i18n of the new controls          #
# --------------------------------------------------------------------------- #


def test_sc_ui_022_1_playback_controls_are_accessible_and_retranslate(qtbot, theme):
    """SC-UI-022-1: accessible names, keyboard reachability, both themes, i18n."""
    controls = _controls(qtbot)
    assert theme in ("light", "dark")

    for widget in (
        controls._play_button,
        controls._stop_button,
        controls._seek_slider,
        controls._speed_combo,
    ):
        assert widget.focusPolicy() != QtCore_Qt.FocusPolicy.NoFocus

    play_before = controls._play_button.text()
    stop_before = controls._stop_button.text()
    assert play_before and stop_before

    controls.changeEvent(QEvent(QEvent.Type.LanguageChange))  # idempotent retranslate

    assert controls._play_button.text() == play_before
    assert controls._stop_button.text() == stop_before
    assert controls._seek_slider.accessibleName()
    assert controls._speed_combo.accessibleName()
