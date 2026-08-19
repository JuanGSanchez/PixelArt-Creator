"""Tests for the stable frame identity (Q-21, REQ-P9-LOGIC-022; plan §10).

No Qt import: identity is **minted** in ``ui/timelapse_controls.py`` (T34,
a recording-scoped monotonic ordinal beside a per-recording ``secrets``
draw), but this module never mints -- it only *validates* what it is given
(``record_frame``), decides removal/reachability by it (``drop_discarded``,
``reconstructability``), and resolves it (``resolve_frame``). Every helper
below stands in for the minting a real ``ui/`` widget would do, using a
fixed recording id -- exactly the split the module docstring in
``logic/timelapse.py`` describes.

**T37** (this file's first half): identity minting refusal/acceptance,
non-reuse, two-outcome resolution -- SC-L022-2's logic half.

**T39** (this file's second half): a Hypothesis property over generated
commit/undo sequences, run against the REAL (identity-addressed)
implementation -- which must hold for every generated sequence -- and
against a REJECTED position-addressed model, built only inside this test
file, which the property is shown to falsify (SC-L022-6). "Discard" and
"re-record" (the other two operations SC-L022-6 names) are not independent
primitives at the logic layer: an undo that is followed by a commit at a
now-stale position IS a discard-and-re-record, compositionally, exactly as
plan §8.1's "prevention, not detection" note describes -- so the generator
below drives only COMMIT and UNDO, and every R1-R5-shaped collision is a
sequence built from those two.

**Every test ends in an assertion on every branch it reaches** (spec §0b.2,
the QA pin's own defect): no ``return``, ``skip`` or bare ``pass`` inside a
conditional stands in for an assertion anywhere in this file.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple

import pytest
from hypothesis import find, given, settings
from hypothesis import strategies as st

from pixelart_creator.logic.timelapse import (
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
    TimelapseError,
    TimelapseFrame,
    TimelapseFrameUnresolved,
    TimelapseSession,
    drop_discarded,
    new_session,
    record_frame,
    resolve_frame,
)

_RECORDING_ID = "identity-test-recording"


def _frame_id(ordinal: int) -> str:
    return f"{_RECORDING_ID}:{ordinal}"


# =========================================================================== #
# T37 -- identity minting, non-reuse and two-outcome resolution (SC-L022-2)   #
# =========================================================================== #


class TestRecordFrameRequiresIdentityOnIdentityBearingSessions:
    def test_record_frame_refuses_a_missing_frame_id_on_a_schema3_session(self):
        session = new_session(recording_id=_RECORDING_ID)
        with pytest.raises(TimelapseError):
            record_frame(session, command_id=0)  # frame_id defaults to None

    def test_record_frame_accepts_a_frame_id_on_a_schema3_session(self):
        session = new_session(recording_id=_RECORDING_ID)
        session = record_frame(session, command_id=0, frame_id=_frame_id(0))
        assert session.frames[0].frame_id == _frame_id(0)

    def test_record_frame_does_not_require_a_frame_id_on_a_schema1_session(self):
        # Additive, defaulted (T32): the shipped two-argument construction
        # still works unchanged (REQ-P9-DATA-003).
        session = new_session()
        session = record_frame(session, command_id=0)
        assert session.frames[0].frame_id is None


class TestRecordFrameRefusesDuplicateIdentities:
    def test_record_frame_refuses_a_frame_id_already_present_in_the_session(self):
        session = new_session(recording_id=_RECORDING_ID)
        session = record_frame(session, command_id=0, frame_id=_frame_id(0))
        with pytest.raises(TimelapseError):
            record_frame(session, command_id=1, frame_id=_frame_id(0))

    def test_session_construction_refuses_two_frames_sharing_an_identity(self):
        # Construction-time, not just via record_frame's append path
        # (REQ-P9-LOGIC-022(b)): TimelapseSession.__post_init__ itself
        # refuses a duplicate, so no caller can bypass the check by
        # constructing frames directly.
        duplicate = _frame_id(0)
        with pytest.raises(TimelapseError):
            TimelapseSession(
                schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
                frames=(
                    TimelapseFrame(index=0, command_id=0, frame_id=duplicate),
                    TimelapseFrame(index=1, command_id=1, frame_id=duplicate),
                ),
                recording_id=_RECORDING_ID,
            )


class TestDropDiscardedPreservesSurvivorIdentity:
    def test_drop_discarded_preserves_frame_id_while_reindexing(self):
        session = new_session(recording_id=_RECORDING_ID)
        for ordinal in range(4):
            session = record_frame(
                session, command_id=ordinal, frame_id=_frame_id(ordinal)
            )
        surviving = frozenset({_frame_id(1), _frame_id(3)})
        pruned = drop_discarded(session, surviving_ids=surviving)
        assert [f.frame_id for f in pruned.frames] == [_frame_id(1), _frame_id(3)]
        assert [f.index for f in pruned.frames] == [0, 1]

    def test_drop_discarded_drops_exactly_the_complement_of_surviving_ids(self):
        session = new_session(recording_id=_RECORDING_ID)
        for ordinal in range(5):
            session = record_frame(
                session, command_id=ordinal, frame_id=_frame_id(ordinal)
            )
        surviving = frozenset({_frame_id(0), _frame_id(2), _frame_id(4)})
        pruned = drop_discarded(session, surviving_ids=surviving)
        kept = {f.frame_id for f in pruned.frames}
        dropped = {_frame_id(o) for o in range(5)} - kept
        assert kept == surviving
        assert dropped == {_frame_id(1), _frame_id(3)}


class TestResolveFrameHasExactlyTwoOutcomes:
    def test_resolve_frame_returns_the_frame_for_a_live_identity(self):
        session = new_session(recording_id=_RECORDING_ID)
        session = record_frame(session, command_id=7, frame_id=_frame_id(0))
        frame = resolve_frame(session, _frame_id(0))
        assert frame.frame_id == _frame_id(0)
        assert frame.command_id == 7

    def test_resolve_frame_raises_naming_a_dropped_frame(self):
        session = new_session(recording_id=_RECORDING_ID)
        session = record_frame(session, command_id=0, frame_id=_frame_id(0))
        session = record_frame(session, command_id=1, frame_id=_frame_id(1))
        pruned = drop_discarded(session, surviving_ids=frozenset({_frame_id(1)}))
        with pytest.raises(TimelapseFrameUnresolved) as excinfo:
            resolve_frame(pruned, _frame_id(0))
        # The raise branch asserts on the MESSAGE, not merely the type --
        # "it failed somehow" is not "it failed naming the frame" (T37's
        # own done-when).
        assert _frame_id(0) in str(excinfo.value)

    def test_resolve_frame_never_returns_a_different_frames_content(self):
        session = new_session(recording_id=_RECORDING_ID)
        session = record_frame(session, command_id=10, frame_id=_frame_id(0))
        session = record_frame(session, command_id=20, frame_id=_frame_id(1))
        resolved = resolve_frame(session, _frame_id(1))
        assert resolved.frame_id == _frame_id(1)
        assert resolved.command_id == 20
        assert resolved.command_id != 10


def test_two_frames_with_the_same_snapshot_id_carry_distinct_frame_ids():
    # The property a content digest cannot provide (plan §10.1): two frames
    # recording identical content still need distinct identities.
    session = new_session(recording_id=_RECORDING_ID)
    session = record_frame(session, command_id=0, frame_id=_frame_id(0))
    session = record_frame(session, command_id=1, frame_id=_frame_id(1))
    same_snapshot = "snap-identical-content"
    session = TimelapseSession(
        schema_version=session.schema_version,
        frames=tuple(
            TimelapseFrame(
                index=f.index,
                command_id=f.command_id,
                snapshot_id=same_snapshot,
                frame_id=f.frame_id,
            )
            for f in session.frames
        ),
        recording_id=session.recording_id,
    )
    assert session.frames[0].snapshot_id == session.frames[1].snapshot_id
    assert session.frames[0].frame_id != session.frames[1].frame_id


# =========================================================================== #
# T39 -- the invariant over generated rewrite sequences (SC-L022-6)           #
# =========================================================================== #


class Event(Enum):
    COMMIT = "commit"
    UNDO = "undo"


#: Bounded so a sequence is fast to run and to shrink; long enough to
#: generate every R1-R5-shaped collision (an undo followed by a commit,
#: repeated discard-and-rewrite at one position, etc).
_events_strategy = st.lists(
    st.sampled_from([Event.COMMIT, Event.UNDO]), min_size=1, max_size=8
)


def _run_real_model(
    events: List[Event],
) -> Tuple["TimelapseSession", List[Tuple[str, int]], Dict[str, int]]:
    """Drive record_frame + drop_discarded directly (T39: "the rewrite
    ALGEBRA is pure logic/, only the events come from ui/"). Mirrors
    ui/timelapse_controls.py's own algorithm (T34): on every forward
    index change to the current stack position, every id_at_index entry
    at or past it is evicted BEFORE the new identity is minted.

    Returns the final session, every (frame_id, content) reference ever
    issued during the sequence (including ones later discarded), and the
    permanent frame_id -> content map.
    """
    session = new_session(recording_id=_RECORDING_ID)
    id_at_index: Dict[int, str] = {}
    stack_index = 0
    next_ordinal = 0
    next_content = 0
    content_by_frame_id: Dict[str, int] = {}
    ever_issued: set = set()
    references: List[Tuple[str, int]] = []

    for event in events:
        if event is Event.COMMIT:
            for stale_key in [k for k in id_at_index if k >= stack_index]:
                del id_at_index[stale_key]
            frame_id = _frame_id(next_ordinal)
            next_ordinal += 1
            assert frame_id not in ever_issued  # never issued twice
            ever_issued.add(frame_id)
            content = next_content
            next_content += 1
            session = record_frame(session, command_id=stack_index, frame_id=frame_id)
            content_by_frame_id[frame_id] = content
            id_at_index[stack_index] = frame_id
            stack_index += 1
            session = drop_discarded(
                session, surviving_ids=frozenset(id_at_index.values())
            )
            references.append((frame_id, content))
        else:  # Event.UNDO
            if stack_index > 0:
                stack_index -= 1

    return session, references, content_by_frame_id


@settings(max_examples=200, deadline=None)
@given(_events_strategy)
def test_sc_l022_6_identity_resolution_never_returns_another_frames_content(events):
    session, references, content_by_frame_id = _run_real_model(events)
    for frame_id, content in references:
        try:
            frame = resolve_frame(session, frame_id)
        except TimelapseFrameUnresolved as exc:
            # Fails NAMING the frame -- one of the two allowed outcomes.
            assert frame_id in str(exc)
            continue
        # Succeeds with THIS frame's own recorded content -- the other
        # allowed outcome -- and never a different frame's.
        assert frame.frame_id == frame_id
        assert content_by_frame_id[frame.frame_id] == content


def _run_position_model(events: List[Event]) -> Tuple[List[int], List[Tuple[int, int]]]:
    """The REJECTED design: resolution keyed by undo-stack POSITION alone.
    A commit truncates any redo branch at the current position and
    overwrites (or appends) the content there -- exactly the semantics
    REQ-P9-LOGIC-022(c) forbids as a reachability/removal key. Returns the
    position->content table and every (position, content) reference ever
    issued."""
    stack_index = 0
    content_by_position: List[int] = []
    next_content = 0
    references: List[Tuple[int, int]] = []

    for event in events:
        if event is Event.COMMIT:
            content = next_content
            next_content += 1
            content_by_position[stack_index:] = [content]
            references.append((stack_index, content))
            stack_index += 1
        else:  # Event.UNDO
            if stack_index > 0:
                stack_index -= 1

    return content_by_position, references


def _position_model_returns_wrong_content(events: List[Event]) -> bool:
    """True iff resolving some reference BY POSITION, after the whole
    sequence has run, yields a DIFFERENT commit's content than the one
    that reference was taken for -- the defect SC-L022-6's comment names."""
    content_by_position, references = _run_position_model(events)
    for position, content in references:
        if position >= len(content_by_position):
            continue  # position no longer exists -- not this defect
        if content_by_position[position] != content:
            return True
    return False


def test_sc_l022_6_falsifier_position_addressed_model_is_shown_broken():
    """The falsifier is EXHIBITED, not assumed (T39's done-when): Hypothesis
    is asked to find the minimal event sequence that makes the
    position-addressed model return the wrong content for a reference it
    issued, and the search is required to SUCCEED -- `find` raises
    `hypothesis.errors.NoSuchExample` if it cannot, which would itself fail
    this test.

    **Minimal counterexample found at authoring time**: ``[COMMIT, UNDO,
    COMMIT]`` -- one commit at position 0, an undo back to position 0, and a
    second commit that overwrites position 0. The reference taken by the
    FIRST commit named position 0 and its own content; after the rewrite,
    resolving "position 0" under the position-addressed model returns the
    SECOND commit's content -- an undo followed by a commit, exactly as
    SC-L022-6's own comment predicts. The real (identity-addressed) model
    resolves the same held reference correctly (proven by the property
    test above, over the identical sequence class).
    """
    counterexample = find(_events_strategy, _position_model_returns_wrong_content)
    assert _position_model_returns_wrong_content(counterexample) is True
    assert Event.UNDO in counterexample
    assert Event.COMMIT in counterexample
    undo_at = counterexample.index(Event.UNDO)
    assert Event.COMMIT in counterexample[undo_at + 1 :]

    # The identical sequence, run against the REAL model, does NOT exhibit
    # this defect -- the same property this file's main invariant test
    # already proves generatively, restated concretely on the exhibited
    # counterexample so the contrast is visible in one place.
    session, references, content_by_frame_id = _run_real_model(counterexample)
    for frame_id, content in references:
        try:
            frame = resolve_frame(session, frame_id)
        except TimelapseFrameUnresolved as exc:
            assert frame_id in str(exc)
            continue
        assert content_by_frame_id[frame.frame_id] == content
