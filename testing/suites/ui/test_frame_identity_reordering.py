"""Frame-identity reordering casuistics (T38, REQ-P9-LOGIC-022(g)).

One pytest-qt test per enumerated collision case **R1-R5**
(``SC-L022-1``, ``-2``, ``-3``, ``-4``, ``-5``) — the user's own verification
demand, *"check carefully the fix with several tests of reordering
casuistics"* — driven **headlessly** (``QT_QPA_PLATFORM=offscreen``) against
a **real** :class:`~pixelart_creator.ui.canvas_view.Canvas_View` +
``QUndoStack`` + :class:`~pixelart_creator.ui.timelapse_controls.Timelapse_Controls`,
never a logic-only stand-in for the stack: this is precisely where a
position-addressed implementation fails and a mocked stack would not
discharge the case (T38's own done-when). Both themes are exercised
automatically (the autouse ``theme`` fixture in ``tests/ui/conftest.py``).

Every scenario here is written, per spec §11's preamble, so a
**position-addressed** implementation FAILS it — each is mechanically proved
to fail against the pre-identity tree with
``scripts/prove_test_catches.py`` (reverting ``pixelart_creator/logic/timelapse.py``
and ``pixelart_creator/ui/timelapse_controls.py``), the output quoted in the
dispatch report. No branch below returns, skips or passes out of an
assertion — the shape the shipped QA pin took and the user's verification
demand is aimed squarely at (spec §0b.2); where a Then is legitimately
either-or (R4), both arms of the conditional carry their own assertion.

Every new-API import (``resolve_frame``, ``FrameId``, ``TimelapseFrameUnresolved``,
``History_Document_Provider``) is deliberately **local to each test function**,
never at module level: at HEAD (the pre-D-12 tree, the only baseline this
worktree has to prove against — see the dispatch report) none of these names
exist in ``logic/timelapse.py`` at all, and a module-level import of a name
that does not exist there is a **collection** error (pytest exit 2), which
``prove_test_catches.py`` correctly refuses to read as a proof (that exit code
means "the run never happened", not "the test failed") — it would make every
test in this file INCONCLUSIVE instead of PROVEN. A local import inside the
test body fails as a normal test FAILURE/ERROR when the run actually reaches
it, which is the real, mechanical proof this file exists to produce.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._ui_helpers import click_pixel, prepare_for_click

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)
YELLOW = (240, 220, 40, 255)
CYAN = (0, 200, 200, 255)
MAGENTA = (200, 30, 200, 255)
GREY = (128, 128, 128, 255)
WHITE = (250, 250, 250, 255)


def _renderer(document):
    """The same ``Document -> ndarray`` shape ``ui/main_window.py`` injects."""
    buffer = composite_stack(document.frames[0].layers, document.width, document.height)
    return np.ascontiguousarray(buffer.data)


def _bound(qtbot, make_view):
    """A recording-ready ``Timelapse_Controls`` bound to a real view/document/stack."""
    view, scene, stack = make_view()
    prepare_for_click(view)
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    document = scene._document
    controls.bind_undo_stack(
        stack, document_getter=lambda: document, document_id=id(document)
    )
    controls.set_renderer(_renderer)
    controls._record_button.setChecked(True)
    return controls, view, scene, stack, document


def _paint(view, colour, x, y):
    """One genuinely new, distinct committed edit at buffer pixel ``(x, y)``."""
    view.set_active_color(colour)
    click_pixel(view, x, y)


def _pixel_at(controls, stack, document, frame, x, y):
    """The colour genuinely recorded for ``frame``, via a real historical step.

    Uses :class:`History_Document_Provider` — the SAME class production
    playback uses — over the SAME live, listened-to ``stack``. Suspends the
    widget's own record/discard bookkeeping for the borrow/step span exactly
    as the widget's own ``_replaying`` guard does (REQ-P9-UI-018): reading
    ground truth off a stack ``Timelapse_Controls`` is itself watching must
    never be misread as a real commit or a discard boundary by the very
    widget under test.
    """
    from pixelart_creator.ui.timelapse_playback import History_Document_Provider

    provider = History_Document_Provider(stack, lambda: document)
    controls._replaying = True
    try:
        with provider:
            content = _renderer(provider(frame))
    finally:
        controls._replaying = False
    return tuple(int(v) for v in content[y, x])


# --------------------------------------------------------------------------- #
# R1 / SC-L022-1 -- an edit reusing a discarded position gets a NEW identity   #
# --------------------------------------------------------------------------- #


def test_r1_sc_l022_1_edit_reusing_a_discarded_position_gets_a_new_identity(
    qtbot, make_view
):
    """R1/SC-L022-1: a command taking a discarded position never inherits its id.

    Position-addressed: the discarded command's ordinal (``command_id``) IS
    the frame's identity, and ``QUndoStack.push`` after an undo hands the new
    command the SAME ordinal the discarded one had — so the noted and the new
    identity are EQUAL, and the first assertion below is arithmetically false
    under that design.
    """
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    _paint(view, RED, 5, 5)
    _paint(view, GREEN, 20, 20)
    _paint(view, BLUE, 40, 40)
    assert controls.frame_count() == 3
    noted = controls.session().frames[2]
    noted_id = noted.frame_id
    assert noted_id is not None

    stack.undo()  # position now behind the 3rd (BLUE) recorded command
    _paint(view, YELLOW, 60, 60)  # a DIFFERENT command; reuses the vacated position

    frames_now = controls.session().frames
    assert len(frames_now) == 3  # the 2 survivors + the 1 new command's frame
    new_frame = frames_now[2]
    # The position IS legitimately reused (that is required behaviour, not a
    # defect) -- what must NOT be reused is the identity.
    assert new_frame.command_id == noted.command_id
    assert new_frame.frame_id != noted_id
    assert noted_id not in {f.frame_id for f in frames_now}
    # The discarded (BLUE) frame has left the session: nothing now in it
    # resolves to BLUE at the pixel BLUE touched -- the new (YELLOW) command's
    # own content is what the reused position now recorded.
    assert _pixel_at(controls, stack, document, new_frame, 60, 60) == YELLOW


# --------------------------------------------------------------------------- #
# R4 / SC-L022-2 -- a reference held across a discard never resolves wrong    #
# --------------------------------------------------------------------------- #


def test_r4_sc_l022_2_reference_held_across_a_discard_never_resolves_to_new_content(
    qtbot, make_view
):
    """R4/SC-L022-2: the QA pin's own case, both branches genuinely asserted.

    Two outcomes are legitimate (REQ-P9-LOGIC-022(d)): the held reference
    resolves to ITS OWN recorded content, or resolution fails naming it.
    Whichever one this implementation actually takes, this test asserts on
    THAT branch -- it never returns or passes without asserting, which is
    exactly what the shipped QA pin
    (``test_req_p9_logic_017_a_discarded_frame_must_never_replay_wrong_content``,
    ``tests/ui/test_timelapse_playback.py``) failed to do on its drop path.
    Position-addressed: resolving by the held frame's ``command_id`` returns
    the NEW command's content (they now sit at the same position), which
    satisfies neither the "own content" nor the "fails naming it" branch --
    both ``assert`` blocks below fail under that design.
    """
    from pixelart_creator.logic.timelapse import TimelapseFrameUnresolved, resolve_frame
    from pixelart_creator.ui.timelapse_playback import History_Document_Provider

    controls, view, scene, stack, document = _bound(qtbot, make_view)
    _paint(view, RED, 5, 5)
    _paint(view, GREEN, 20, 20)
    _paint(view, BLUE, 40, 40)
    held_frame = controls.session().frames[2]  # the BLUE @ (40, 40) edit

    stack.undo()  # position now behind the 3rd (BLUE) recorded command
    _paint(view, YELLOW, 40, 40)  # a DIFFERENT command, SAME pixel, SAME position

    branch_taken = None
    try:
        resolved = resolve_frame(controls.session(), held_frame.frame_id)
    except TimelapseFrameUnresolved as exc:
        branch_taken = "failed"
        # Fails NAMING the frame (REQ-P9-LOGIC-022(d)) -- not silently, not
        # with an unrelated message.
        assert held_frame.frame_id in str(exc)
    else:
        branch_taken = "resolved"
        # Resolves to THAT frame's own (BLUE) content -- never the new one.
        got = _pixel_at(controls, stack, document, resolved, 40, 40)
        assert got == BLUE

    assert branch_taken in ("failed", "resolved")  # exactly one, always asserted

    # Unconditional, over BOTH possible branches: the new (YELLOW) command's
    # colour is never what the held (BLUE) reference resolves to, and the
    # discarded identity never appears again in the live session.
    new_frame = controls.session().frames[-1]
    assert new_frame.frame_id != held_frame.frame_id
    assert held_frame.frame_id not in {f.frame_id for f in controls.session().frames}
    provider = History_Document_Provider(stack, lambda: document)
    got_new = _pixel_at(controls, stack, document, new_frame, 40, 40)
    assert got_new == YELLOW
    assert got_new != BLUE


# --------------------------------------------------------------------------- #
# R2 / SC-L022-3 -- re-recorded frames carry identities never issued before   #
# --------------------------------------------------------------------------- #


def test_r2_sc_l022_3_rerecorded_frames_carry_identities_never_issued_before(
    qtbot, make_view
):
    """R2/SC-L022-3: discard-then-re-record never collides, and replay is honest.

    Position-addressed: the two re-recorded frames reuse the two discarded
    frames' ordinals as their "identity", so the session holds colliding
    identities and the pairwise-distinct assertion fails.
    """
    controls, view, scene, stack, document = _bound(qtbot, make_view)
    _paint(view, RED, 1, 1)
    _paint(view, GREEN, 2, 2)
    _paint(view, BLUE, 3, 3)
    _paint(view, YELLOW, 4, 4)
    _paint(view, CYAN, 5, 5)
    assert controls.frame_count() == 5
    discarded_ids = {f.frame_id for f in controls.session().frames[3:5]}  # YELLOW, CYAN

    stack.undo()
    stack.undo()  # position now behind the 4th and 5th recorded frames
    _paint(view, MAGENTA, 6, 6)  # discards YELLOW+CYAN, takes the 4th position
    _paint(view, GREY, 7, 7)  # the 5th position
    _paint(view, WHITE, 8, 8)  # the 6th position

    frames_now = controls.session().frames
    ids_now = [f.frame_id for f in frames_now]
    assert len(frames_now) == 6  # the 3 survivors + the 3 newly recorded
    assert len(ids_now) == len(set(ids_now))  # no two frames share an identity
    assert discarded_ids.isdisjoint(ids_now)  # no discarded identity survives

    expected = [
        (frames_now[0], 1, 1, RED),
        (frames_now[1], 2, 2, GREEN),
        (frames_now[2], 3, 3, BLUE),
        (frames_now[3], 6, 6, MAGENTA),
        (frames_now[4], 7, 7, GREY),
        (frames_now[5], 8, 8, WHITE),
    ]
    for frame, x, y, colour in expected:
        assert _pixel_at(controls, stack, document, frame, x, y) == colour


# --------------------------------------------------------------------------- #
# R3 / SC-L022-4 -- repeated discards at ONE position, pairwise-distinct ids  #
# --------------------------------------------------------------------------- #


def test_r3_sc_l022_4_repeated_discards_at_one_position_issue_pairwise_distinct_ids(
    qtbot, make_view
):
    """R3/SC-L022-4: three discard-and-rewrite rounds at ONE stack position.

    Position-addressed: every round shares the SAME ordinal (position 1), so
    all three "identities" are equal and the pairwise-distinct assertion
    fails; every surviving reference resolves to the LAST round's colour.
    """
    from pixelart_creator.logic.timelapse import TimelapseFrameUnresolved, resolve_frame

    controls, view, scene, stack, document = _bound(qtbot, make_view)

    _paint(view, RED, 9, 9)  # round 1
    round1 = controls.session().frames[0]
    id1 = round1.frame_id

    stack.undo()
    _paint(view, GREEN, 9, 9)  # round 2, SAME position, SAME pixel
    round2 = controls.session().frames[0]
    id2 = round2.frame_id

    stack.undo()
    _paint(view, BLUE, 9, 9)  # round 3, SAME position, SAME pixel
    round3 = controls.session().frames[0]
    id3 = round3.frame_id

    assert len({id1, id2, id3}) == 3  # pairwise distinct across all three rounds

    session_now = controls.session()
    assert len(session_now.frames) == 1  # only the LIVE round survives

    # Round 3 (the survivor) resolves to its own colour.
    resolved3 = resolve_frame(session_now, id3)
    assert _pixel_at(controls, stack, document, resolved3, 9, 9) == BLUE

    # Rounds 1 and 2 were each discarded in their turn -- resolution FAILS,
    # naming the frame, and never silently returns round 3's (BLUE) colour
    # under an earlier round's identity.
    for stale_id in (id1, id2):
        with pytest.raises(TimelapseFrameUnresolved) as exc_info:
            resolve_frame(session_now, stale_id)
        assert stale_id in str(exc_info.value)


# --------------------------------------------------------------------------- #
# R5 / SC-L022-5 -- recorded count / live stack disagreement, both directions #
# --------------------------------------------------------------------------- #


def test_r5_sc_l022_5_recorded_count_and_live_stack_disagreement_decided_by_identity(
    qtbot, make_view
):
    """R5/SC-L022-5: a count- or position-derived boundary is never the test.

    Built against a REAL ``QUndoStack``'s two genuinely different live
    extents (before and after a discard-and-regrow), never a synthetic
    extent -- this is the sharpest case: a frame whose recorded POSITION
    still lies within the live stack's current extent, but whose IDENTITY was
    evicted, must be reported unreconstructible and named regardless.

    Position-addressed: a frame whose ordinal is still ``<= stack.count()``
    is admitted -- both ``verdict.ok is False`` assertions below fail under
    that design, because the position-derived boundary would read every
    frame here as "in range" and say nothing is wrong.
    """
    from pixelart_creator.logic.timelapse import (
        ReconstructionBlocker,
        TimelapseSession,
        reconstructability,
    )
    from pixelart_creator.ui.timelapse_playback import History_Document_Provider

    controls, view, scene, stack, document = _bound(qtbot, make_view)
    _paint(view, RED, 11, 11)
    _paint(view, GREEN, 12, 12)
    _paint(view, BLUE, 13, 13)
    assert controls.frame_count() == 3
    older_session = controls.session()  # 3 frames: RED, GREEN, BLUE
    older_extent = History_Document_Provider(
        stack,
        lambda: document,
        reachable_frame_ids=frozenset(controls._id_at_index.values()),
    ).extent()
    stale_frame = older_session.frames[1]  # GREEN -- about to be discarded below

    # The live stack GROWS past the older snapshot, discarding positions 2/3:
    # undo past GREEN and BLUE, then commit two NEW commands over them.
    stack.undo()
    stack.undo()
    _paint(view, YELLOW, 14, 14)  # NEW command at position 2 -- discards GREEN
    _paint(view, CYAN, 15, 15)  # NEW command at position 3 -- discards BLUE
    current_session = controls.session()
    current_extent = History_Document_Provider(
        stack,
        lambda: document,
        reachable_frame_ids=frozenset(controls._id_at_index.values()),
    ).extent()

    # -- Direction 1: "frames were dropped while the stack grew" -----------
    # `older_session` still names GREEN by an identity the CURRENT live
    # extent no longer holds, even though GREEN's recorded POSITION
    # (command_id) still lies well inside the grown stack's range/count.
    assert stale_frame.command_id <= stack.count()  # "in range" positionally
    verdict = reconstructability(older_session, current_extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == stale_frame.index
    assert verdict.blocker is ReconstructionBlocker.BEYOND_EXTENT
    assert stale_frame.frame_id not in current_extent.reachable_frame_ids

    # And RED (index 0), whose identity IS still live, is independently
    # reported reconstructible -- the verdict is per-identity, not a blanket
    # refusal of the whole stale session.
    solo_survivor = TimelapseSession(
        schema_version=older_session.schema_version,
        frames=(older_session.frames[0],),
        recording_id=older_session.recording_id,
    )
    assert reconstructability(solo_survivor, current_extent).ok is True

    # -- Direction 2: "the stack has shrunk below the recorded count" ------
    # The CURRENT session (with its new, live frames) checked against the
    # OLDER, narrower extent from before those frames existed -- the current
    # frames' identities are simply absent from it. Same per-identity rule,
    # same verdict shape, no boundary re-derived from a count anywhere.
    verdict2 = reconstructability(current_session, older_extent)
    assert verdict2.ok is False
    assert verdict2.blocker is ReconstructionBlocker.BEYOND_EXTENT
    assert current_session.frames[1].frame_id not in older_extent.reachable_frame_ids
