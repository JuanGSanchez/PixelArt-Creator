"""Tests for in-session historical reconstruction (T13): DocumentProvider,
reconstructability, drop_discarded and historical replay
(REQ-P9-LOGIC-013..-018). No Qt import -- the QUndoStack stepper is a `ui/`
concern (DEP-12b); here a plain dict keyed by ``command_id`` stands in for
"a live, steppable history", exercising exactly the observable contract
`logic/timelapse.py` promises: replay places the document at each frame's
OWN recorded state via an injected DocumentProvider, never falls back to N
renders of one document, and never mutates what it borrows.

**Written against plan.md §8.2/§8.3 (2026-08-17 addendum, AGT-01 Ruling B)**,
NOT against the shape shipped in this worktree at dispatch time
(``ReconstructionExtent(reachable_count, matches_session)``,
``DocumentProvider = Callable[[int], Document]``). Ruling B is dated after
and supersedes what AGT-03 implemented; per Decision A4-D3 the tests follow
the ruling and the (currently stale) product code is reported to AGT-03,
not silently accommodated. Until `logic/timelapse.py` is updated to the
ruled shape, this module fails to import (`ReconstructionSubstrate`,
`ReconstructionBlocker` do not exist yet) -- that failure IS the evidence.

SC-L013-1/-2, SC-L014-1/-2, SC-L015-1/-2, SC-L016-1/-2, SC-L017-1/-2,
SC-L018-1/-2.

**Re-keyed 2026-08-18 (Q-21, T33/T47) onto the stable frame identity**
(REQ-P9-LOGIC-022). ``ReconstructionExtent``'s old command-id-keyed reachable
set field was superseded by ``reachable_frame_ids: FrozenSet[FrameId]`` and
``drop_discarded``'s old integer position keyword by
``drop_discarded(session, surviving_ids=FrozenSet[FrameId])`` -- a *position*
is exactly what REQ-P9-LOGIC-022(c) forbids as a reachability/removal key,
because the undo stack reuses its coordinate space by design. Every session
built by this module's helper is now **identity-bearing** (schema 3):
``reconstructability``'s HISTORY branch checks ``frame.frame_id is None``
before anything else, so a schema-1 (no-identity) session recorded through
this helper would block on ``NO_IDENTITY`` before a single SC-L015/-L017
assertion could even be reached -- minting an identity per frame is what
lets these tests keep exercising ``BEYOND_EXTENT`` / ``SUBSTRATE_MISMATCH`` /
survivor-preservation the way they did before the re-key.

**Substitutions this re-keying made (old assertion -> new assertion), listed
per the T47 done-when -- no assertion below was deleted, each was replaced
by its identity-keyed equivalent:**

1. ``test_sc_l017_1_frames_above_a_discarded_branch_are_removed`` /
   ``..._original_session_is_not_mutated`` / ``..._what_remains_...`` --
   OLD: drop_discarded took an integer position boundary keyword.
   NEW: ``drop_discarded(session, surviving_ids=frozenset({...frame_id}))``
   (the set of identities to keep) -- same kept/dropped frames for these
   fixtures, restated as *which identities survive*, plus a new assertion
   that each survivor's ``frame_id`` is preserved unchanged (T33's stated
   guarantee, not claimed before this re-key).
2. ``test_drop_discarded_rejects_negative_position`` -- OLD: asserted a
   negative integer position keyword is refused. That parameter no longer exists
   (``surviving_ids`` is a ``frozenset``, which has no sign). NEW:
   ``test_drop_discarded_rejects_non_frozenset_surviving_ids`` asserts the
   equivalent malformed-input refusal on the new signature: a
   non-``frozenset`` (a plain ``set``) is rejected the same way a negative
   position used to be -- ``_require_frozenset_of``'s own contract.
3. ``test_sc_l015_1_fully_reachable_history_session_reports_playable`` /
   ``..._unreachable_history_session_names_first_offending_frame`` /
   ``..._substrate_mismatch_names_the_first_frame`` /
   ``test_sc_l013_reindexed_by_command_id_reports_correctly_after_a_gap`` --
   OLD: ``ReconstructionExtent`` took the old command-id-keyed reachable set.
   NEW: ``ReconstructionExtent(reachable_frame_ids=frozenset({...FrameId}))``
   -- the same reachable/unreachable command positions, translated through
   the helper's own command_id -> frame_id map, so the *scenario* (which
   frames are reachable) is unchanged and only the *key space* is re-keyed.
4. ``test_extent_post_init_refuses_snapshot_extent_carrying_command_ids`` --
   OLD: constructed a SNAPSHOT extent with a stray old command-id-keyed
   kwarg. NEW:
   ``test_extent_post_init_refuses_snapshot_extent_carrying_frame_ids``
   constructs it with a stray ``reachable_frame_ids`` kwarg -- the same
   "wrong substrate's keys" construction-time refusal, on the new field.
5. ``test_sc_l018_2_no_frame_carries_a_timestamp`` -- OLD:
   ``field_names == {"index", "command_id", "snapshot_id"}``. NEW: the same
   set plus ``"frame_id"`` -- ``TimelapseFrame`` gained the field
   additively (T32); the "no timestamp" assertion is unchanged and still
   the point of the test.
"""

from __future__ import annotations

import copy
import dataclasses

import numpy as np
import pytest

from pixelart_creator.logic import constants
from pixelart_creator.logic.timelapse import (
    Reconstructability,
    ReconstructionBlocker,
    ReconstructionExtent,
    ReconstructionSubstrate,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
    drop_discarded,
    new_session,
    reconstructability,
    record_frame,
    replay,
)

# --------------------------------------------------------------------------- #
# A fake, pure "live history" -- a dict keyed by command_id (NOT by ordinal;  #
# plan §8.2 B-1: frame.index is not the key either substrate is addressed    #
# by), standing in for a QUndoStack stepped to a given command position (the #
# real stepper is ui/timelapse_playback.py, T9, out of scope for a Qt-free   #
# logic test).                                                               #
# --------------------------------------------------------------------------- #

#: A fixed per-module recording id (Q-21, T47 re-key) -- this module is
#: Qt-free and mints nothing itself (that stays ui/'s job, T34); a constant
#: string is all a *validating* test needs, since `record_frame` only checks
#: shape and non-reuse, never provenance.
_RECORDING_ID = "test-recording-replay"


def _frame_id(command_id) -> str:
    """The identity this module's helper mints for ``command_id`` (Q-21)."""
    return f"{_RECORDING_ID}:{command_id}"


def _session_with_command_ids(command_ids):
    """Build an identity-bearing session whose frames carry the GIVEN command
    ids, in order -- deliberately not equal to the frame's own index for some
    fixtures, since that divergence is exactly what Ruling B (B-1) is about.
    **Identity-bearing since the 2026-08-18 re-key (Q-21, T47)**: a schema-1
    (no-identity) session would block every HISTORY reconstructability check
    on NO_IDENTITY before BEYOND_EXTENT/SUBSTRATE_MISMATCH could ever be
    observed, which is not what SC-L015/-L017 are testing."""
    session = new_session(recording_id=_RECORDING_ID)
    for cid in command_ids:
        session = record_frame(session, command_id=cid, frame_id=_frame_id(cid))
    return session


def _history(command_ids, base: int = 1):
    """``{command_id: distinct 1x1 RGBA array}`` -- the value "at" each
    command position a live history would be stepped to."""
    return {
        cid: np.full((1, 1, 4), base + k, dtype=np.uint8)
        for k, cid in enumerate(command_ids)
    }


def _history_provider(store: dict):
    def provider(frame: TimelapseFrame):
        if frame.command_id not in store:
            raise RuntimeError(f"command {frame.command_id} not live")
        return store[frame.command_id]

    return provider


def _identity_renderer(array):
    return array.copy()


class _SteppingProvider:
    """A stateful fake DocumentProvider tracking (position, undo/redo
    availability) like a real QUndoStack -- so this module can prove
    REQ-P9-LOGIC-016's restoration contract is COMPATIBLE with `replay`
    (the actual borrow/restore implementation is ui/timelapse_playback.py,
    T9; the mechanism -- wrap the call in try/finally -- is what's proven
    here). Keyed by command_id, per Ruling B."""

    def __init__(self, store: dict, fail_at_command_id=None):
        self._store = store
        self.position = -1
        self.undo_available = False
        self.redo_available = len(store) > 0
        self._fail_at = fail_at_command_id

    def __call__(self, frame: TimelapseFrame):
        if self._fail_at is not None and frame.command_id == self._fail_at:
            raise RuntimeError(f"cannot step to command {frame.command_id}")
        self.position = frame.command_id
        self.undo_available = frame.command_id > min(self._store, default=0)
        self.redo_available = frame.command_id < max(self._store, default=0)
        return self._store[frame.command_id]

    def snapshot_state(self):
        return (self.position, self.undo_available, self.redo_available)

    def restore_state(self, state):
        self.position, self.undo_available, self.redo_available = state


def _replay_with_restore(session, provider, renderer):
    """The borrow/restore pattern REQ-P9-LOGIC-016 requires of a real
    DocumentProvider: content/position/undo-redo are restored in a
    `finally`, regardless of completion, truncation or failure."""
    pre = provider.snapshot_state()
    try:
        return replay(session, provider, renderer)
    finally:
        provider.restore_state(pre)


# --------------------------------------------------------------------------- #
# SC-L013 -- each frame reconstructs its OWN recorded state                   #
# --------------------------------------------------------------------------- #


def test_sc_l013_1_each_frame_reconstructs_its_own_recorded_position():
    # command_ids deliberately diverge from frame.index (10, 11, 12 vs 0, 1, 2)
    # -- Ruling B (B-1): the key is command_id, never the ordinal.
    command_ids = [10, 11, 12]
    session = _session_with_command_ids(command_ids)
    history = _history(command_ids)
    frames = replay(session, _history_provider(history), _identity_renderer)
    assert len(frames) == 3
    for produced, cid in zip(frames, command_ids):
        assert np.array_equal(produced, history[cid])
    assert not (
        np.array_equal(frames[0], frames[1]) and np.array_equal(frames[1], frames[2])
    )


def test_sc_l013_2_replay_is_not_n_renders_of_the_current_state():
    command_ids = [10, 11, 12]
    session = _session_with_command_ids(command_ids)
    history = _history(command_ids)
    current_document = history[command_ids[-1]]  # doc "at its latest state"
    frames = replay(session, _history_provider(history), _identity_renderer)
    assert any(not np.array_equal(f, current_document) for f in frames)
    assert np.array_equal(frames[-1], current_document)


# --------------------------------------------------------------------------- #
# SC-L014 -- no live history -> raises, never a partial/fallback sequence     #
# --------------------------------------------------------------------------- #


def test_sc_l014_1_no_way_to_place_document_raises_and_returns_nothing():
    session = _session_with_command_ids([1, 2])

    def failing_provider(_frame):
        raise RuntimeError("no live history bound")

    with pytest.raises(TimelapseError):
        replay(session, failing_provider, _identity_renderer)


def test_sc_l014_2_never_falls_back_to_n_renders_of_current_document():
    session = _session_with_command_ids([1, 2, 3, 4])
    current = np.full((1, 1, 4), 9, dtype=np.uint8)
    calls = {"n": 0}

    def cannot_step_provider(_frame):
        calls["n"] += 1
        raise RuntimeError("history cannot be stepped")

    with pytest.raises(TimelapseError):
        replay(session, cannot_step_provider, lambda _doc: current.copy())
    # It failed on the FIRST frame it could not place -- it never iterated
    # all n frames rendering the one document it already had.
    assert calls["n"] == 1


# --------------------------------------------------------------------------- #
# SC-L015 -- reconstructability decided before anything is rendered           #
#            (plan §8.2 ruled shape: substrate-keyed extent, blocker codes)   #
#            **Re-keyed onto identity 2026-08-18 (Q-21, T47) -- substitution  #
#            #3 in the module docstring.**                                    #
# --------------------------------------------------------------------------- #


def test_sc_l015_1_fully_reachable_history_session_reports_playable():
    command_ids = [1, 2, 3]
    session = _session_with_command_ids(command_ids)
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY,
        reachable_frame_ids=frozenset(_frame_id(c) for c in command_ids),
    )
    verdict = reconstructability(session, extent)
    assert verdict.ok is True
    assert verdict.first_unreachable_index is None
    assert verdict.blocker is None


def test_sc_l015_1_reconstructability_never_renders():
    sig_params = list(
        reconstructability.__code__.co_varnames[
            : reconstructability.__code__.co_argcount
        ]
    )
    assert "renderer" not in sig_params


def test_sc_l015_2_unreachable_history_session_names_first_offending_frame():
    # command_ids [1,2,3,4,5]; only 1,2,3 are live -> frame index 3
    # (command_id 4) is the first unreachable one.
    command_ids = [1, 2, 3, 4, 5]
    session = _session_with_command_ids(command_ids)
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY,
        reachable_frame_ids=frozenset(_frame_id(c) for c in (1, 2, 3)),
    )
    verdict = reconstructability(session, extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == 3
    assert verdict.blocker is ReconstructionBlocker.BEYOND_EXTENT


def test_sc_l015_2_substrate_mismatch_names_the_first_frame():
    session = _session_with_command_ids([1, 2])
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY,
        reachable_frame_ids=frozenset(_frame_id(c) for c in (1, 2)),
        matches_session=False,
    )
    verdict = reconstructability(session, extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == 0
    assert verdict.blocker is ReconstructionBlocker.SUBSTRATE_MISMATCH


def test_sc_l013_reindexed_by_command_id_reports_correctly_after_a_gap():
    # B-1's own example: a session recorded from command 5 onward, checked
    # against a history holding only commands 0-2, must NOT be reported
    # fully reconstructible -- proving the fix over the rejected
    # `frame.index >= reachable_count` comparison. Re-keyed onto identity:
    # the "reachable" set below names identities that belong to NO frame in
    # this session (a *different*, hypothetical recording's commands 0-2) --
    # the frame_id-keyed equivalent of "positions this session never held".
    session = _session_with_command_ids([5, 6, 7])
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY,
        reachable_frame_ids=frozenset(_frame_id(c) for c in (0, 1, 2)),
    )
    verdict = reconstructability(session, extent)
    assert verdict.ok is False
    assert verdict.first_unreachable_index == 0  # not one of its frames exists


def test_reconstructability_empty_session_is_always_ok():
    extent = ReconstructionExtent(substrate=ReconstructionSubstrate.HISTORY)
    verdict = reconstructability(new_session(), extent)
    assert verdict.ok is True


def test_reconstructability_rejects_non_extent_argument():
    with pytest.raises(TimelapseError):
        reconstructability(
            _session_with_command_ids([1]), extent="not an extent"
        )  # type: ignore[arg-type]


def test_extent_post_init_refuses_history_extent_carrying_snapshot_ids():
    with pytest.raises(TimelapseError):
        ReconstructionExtent(
            substrate=ReconstructionSubstrate.HISTORY,
            reachable_snapshot_ids=frozenset({"deadbeef"}),
        )


def test_extent_post_init_refuses_snapshot_extent_carrying_frame_ids():
    # Substitution #4 (module docstring): re-keyed from the superseded
    # the old command-id-keyed kwarg onto `reachable_frame_ids` -- same
    # construction-time refusal (a SNAPSHOT extent must not carry the
    # HISTORY substrate's own key space), on the new field name.
    with pytest.raises(TimelapseError):
        ReconstructionExtent(
            substrate=ReconstructionSubstrate.SNAPSHOT,
            reachable_frame_ids=frozenset({_frame_id(1)}),
        )


# --------------------------------------------------------------------------- #
# SC-L016 -- reconstruction restores what it borrowed                        #
# --------------------------------------------------------------------------- #


def test_sc_l016_1_restored_after_a_completed_replay():
    command_ids = [1, 2, 3]
    history = _history(command_ids)
    session = _session_with_command_ids(command_ids)
    provider = _SteppingProvider(history)
    pre = provider.snapshot_state()

    frames = _replay_with_restore(session, provider, _identity_renderer)

    assert len(frames) == 3
    assert provider.snapshot_state() == pre


def test_sc_l016_1_restored_after_a_replay_stopped_part_way():
    command_ids = [1, 2, 3, 4, 5]
    history = _history(command_ids)
    full_session = _session_with_command_ids(command_ids)
    provider = _SteppingProvider(history)
    pre = provider.snapshot_state()

    # "Stopped part way": only the first 2 frames were played before the
    # user pressed stop -- a truncated session stands in for that, since
    # `replay` itself has no cancellation token (that lives in ui/, T10).
    partial_session = TimelapseSession(
        schema_version=full_session.schema_version,
        frames=full_session.frames[:2],
        recording_id=full_session.recording_id,
    )
    frames = _replay_with_restore(partial_session, provider, _identity_renderer)

    assert len(frames) == 2
    assert provider.snapshot_state() == pre


def test_sc_l016_1_restored_after_a_replay_that_fails():
    command_ids = [1, 2, 3, 4]
    history = _history(command_ids)
    session = _session_with_command_ids(command_ids)
    provider = _SteppingProvider(history, fail_at_command_id=3)
    pre = provider.snapshot_state()

    with pytest.raises(TimelapseError):
        _replay_with_restore(session, provider, _identity_renderer)

    assert provider.snapshot_state() == pre


def test_sc_l016_2_replay_adds_no_history_entry_and_session_is_unchanged():
    command_ids = [1, 2, 3]
    history = _history(command_ids)
    session = _session_with_command_ids(command_ids)
    session_before = copy.deepcopy(session)
    history_len_before = len(history)

    replay(session, _history_provider(history), _identity_renderer)

    assert len(history) == history_len_before  # no entry appended
    assert session == session_before
    assert [f.command_id for f in session.frames] == [
        f.command_id for f in session_before.frames
    ]


# --------------------------------------------------------------------------- #
# SC-L017 -- discarded-branch frames leave the session                        #
#            **Re-keyed onto identity 2026-08-18 (Q-21, T47) -- substitution  #
#            #1 in the module docstring: the old int position keyword became  #
#            `surviving_ids=frozenset(FrameId)`.**                            #
# --------------------------------------------------------------------------- #


def test_sc_l017_1_frames_above_a_discarded_branch_are_removed():
    session = _session_with_command_ids([0, 1, 2, 3, 4])
    # The user undid back past the third recorded position (command_id 2)
    # and committed a new command, discarding the redo branch above it --
    # restated as *which identities survive* rather than *which positions*.
    surviving = frozenset(_frame_id(c) for c in (0, 1, 2))
    pruned = drop_discarded(session, surviving_ids=surviving)
    assert [f.command_id for f in pruned.frames] == [0, 1, 2]
    assert [f.index for f in pruned.frames] == [0, 1, 2]
    # New assertion (not claimed before this re-key, T33's stated guarantee):
    # every survivor's frame_id is preserved unchanged, not re-minted.
    assert [f.frame_id for f in pruned.frames] == [_frame_id(c) for c in (0, 1, 2)]


def test_sc_l017_1_original_session_is_not_mutated():
    session = _session_with_command_ids([0, 1, 2, 3, 4])
    surviving = frozenset(_frame_id(c) for c in (0, 1))
    drop_discarded(session, surviving_ids=surviving)
    assert [f.command_id for f in session.frames] == [0, 1, 2, 3, 4]


def test_sc_l017_2_what_remains_after_a_discard_still_reconstructs():
    session = _session_with_command_ids([0, 1, 2, 3, 4])
    surviving = frozenset(_frame_id(c) for c in (0, 1, 2))
    pruned = drop_discarded(session, surviving_ids=surviving)
    history = _history([0, 1, 2])  # matches the 3 kept commands
    extent = ReconstructionExtent(
        substrate=ReconstructionSubstrate.HISTORY,
        reachable_frame_ids=frozenset(_frame_id(c) for c in (0, 1, 2)),
    )
    verdict = reconstructability(pruned, extent)
    assert verdict.ok is True
    frames = replay(pruned, _history_provider(history), _identity_renderer)
    assert len(frames) == 3
    for produced, cid in zip(frames, [0, 1, 2]):
        assert np.array_equal(produced, history[cid])


def test_drop_discarded_rejects_non_frozenset_surviving_ids():
    # Substitution #2 (module docstring): a negative int position keyword no longer exists
    # to be negative -- `surviving_ids` is a frozenset, which has no sign.
    # The equivalent malformed-input refusal on the new signature: a plain
    # `set` (not a `frozenset`) is rejected by `_require_frozenset_of`.
    with pytest.raises(TimelapseError):
        drop_discarded(
            _session_with_command_ids([1]), surviving_ids={_frame_id(1)}
        )  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# SC-L018 -- determinism, pacing and bounds                                   #
# --------------------------------------------------------------------------- #


def test_sc_l018_1_same_session_replayed_twice_is_byte_identical():
    command_ids = [1, 2, 3, 4]
    session = _session_with_command_ids(command_ids)
    history = _history(command_ids)
    first = replay(session, _history_provider(history), _identity_renderer)
    second = replay(session, _history_provider(history), _identity_renderer)
    assert len(first) == len(second)
    for a, b in zip(first, second):
        assert np.array_equal(a, b)


def test_sc_l018_2_no_frame_carries_a_timestamp():
    # Substitution #5 (module docstring): `frame_id` was added additively
    # (T32) -- the field-name set is widened by exactly that name, and the
    # "no timestamp" assertion (the actual point of this test) is unchanged.
    field_names = {f.name for f in dataclasses.fields(TimelapseFrame)}
    assert "timestamp" not in field_names
    assert field_names == {"index", "command_id", "snapshot_id", "frame_id"}


def test_sc_l018_2_playback_speeds_and_default_are_named_constants():
    assert isinstance(constants.TIMELAPSE_PLAYBACK_SPEEDS, tuple)
    assert 1.0 in constants.TIMELAPSE_PLAYBACK_SPEEDS
    assert isinstance(constants.TIMELAPSE_PLAYBACK_FPS_DEFAULT, int)
    assert constants.TIMELAPSE_PLAYBACK_FPS_DEFAULT == constants.CYCLE_DEFAULT_FPS
    # Derivation cited in plan §4.2: bounded by FPS_TARGET // CYCLE_DEFAULT_FPS.
    assert max(constants.TIMELAPSE_PLAYBACK_SPEEDS) <= (
        constants.FPS_TARGET // constants.CYCLE_DEFAULT_FPS
    )
