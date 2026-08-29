"""Tests for pixelart_creator.logic.timelapse — reproducible session model.

REQ-P9-LOGIC-010 [GEO]: record_frame appends one contiguous frame per committed
command (returning a new immutable session, never mutating the input); replay is
deterministic — the same recorded session replayed twice yields the same frame
count and order via a caller-supplied pure renderer. Bounds (MAX_TIMELAPSE_FRAMES)
and structural validation raise TimelapseError. Zero Qt. Maps to SC-L010-1.
"""

from __future__ import annotations

import numpy as np
import pytest

from pixelart_creator.logic import constants
from pixelart_creator.logic.timelapse import (
    SUPPORTED_SCHEMA_VERSIONS,
    TIMELAPSE_SCHEMA_VERSION,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
    new_session,
    record_frame,
    replay,
)


def test_new_session_is_empty_at_current_schema():
    s = new_session()
    assert s.schema_version == TIMELAPSE_SCHEMA_VERSION
    assert s.frames == ()
    assert TIMELAPSE_SCHEMA_VERSION in SUPPORTED_SCHEMA_VERSIONS


# --------------------------------------------------------------------------- #
# TimelapseFrame / TimelapseSession validation                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("index,command_id", [(-1, 0), (0, -1), (True, 0), (0, 1.0)])
def test_frame_rejects_invalid(index, command_id):
    with pytest.raises(TimelapseError):
        TimelapseFrame(index=index, command_id=command_id)  # type: ignore[arg-type]


def test_session_rejects_non_str_schema():
    with pytest.raises(TimelapseError):
        TimelapseSession(schema_version=1)  # type: ignore[arg-type]


def test_session_rejects_non_contiguous_indices():
    frames = (
        TimelapseFrame(index=0, command_id=10),
        TimelapseFrame(index=2, command_id=11),  # gap
    )
    with pytest.raises(TimelapseError):
        TimelapseSession(frames=frames)


def test_session_rejects_non_frame_entry():
    with pytest.raises(TimelapseError):
        TimelapseSession(frames=("nope",))  # type: ignore[arg-type]


def test_session_rejects_over_max_frames():
    frames = tuple(
        TimelapseFrame(index=k, command_id=k)
        for k in range(constants.MAX_TIMELAPSE_FRAMES + 1)
    )
    with pytest.raises(TimelapseError):
        TimelapseSession(frames=frames)


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-010 — record_frame (per-command cadence, immutable)            #
# --------------------------------------------------------------------------- #


def test_record_frame_appends_contiguous_index():
    s0 = new_session()
    s1 = record_frame(s0, command_id=42)
    s2 = record_frame(s1, command_id=43)
    assert [(f.index, f.command_id) for f in s2.frames] == [(0, 42), (1, 43)]


def test_record_frame_is_pure_does_not_mutate_input():
    s0 = new_session()
    record_frame(s0, command_id=1)
    # Original session unchanged (frozen, functional update).
    assert s0.frames == ()


def test_record_frame_rejects_bad_command_id():
    with pytest.raises(TimelapseError):
        record_frame(new_session(), command_id=-1)
    with pytest.raises(TimelapseError):
        record_frame(new_session(), command_id=True)  # type: ignore[arg-type]


def test_record_frame_rejects_when_at_capacity():
    frames = tuple(
        TimelapseFrame(index=k, command_id=k)
        for k in range(constants.MAX_TIMELAPSE_FRAMES)
    )
    full = TimelapseSession(frames=frames)
    with pytest.raises(TimelapseError):
        record_frame(full, command_id=999)


# --------------------------------------------------------------------------- #
# T15 (spec §8, plan R-2) — replay(session, provider, renderer) is genuinely   #
# historical: a DocumentProvider places the document at each frame's own      #
# recorded state; replay is FORBIDDEN to fall back to N renders of one        #
# already-available document (REQ-P9-LOGIC-013, -014). Rewrite authorised in  #
# advance; the other ten tests in this module are untouched (T15 done-when).  #
# --------------------------------------------------------------------------- #


def _history(n: int):
    """``n`` distinct 1x1 RGBA "documents" — one per committed pixel-changing
    command. A plain object stands in for ``Document`` here: ``replay`` never
    inspects the document's type, it only threads ``provider(frame)`` through
    the caller-supplied ``renderer`` (Article I: no Qt/Document coupling
    needed to prove the historical contract). Indexed by ``command_id``,
    which in this fixture is built equal to the frame's ordinal (plan §8.2
    Ruling B: the port is keyed by the frame's own ``command_id``, never by
    the ordinal — ``testing/suites/logic/test_timelapse_replay.py`` exercises the
    divergent case)."""
    return [np.full((1, 1, 4), k + 1, dtype=np.uint8) for k in range(n)]


def _history_provider(history):
    """A ``DocumentProvider`` that places "the document" at its own recorded
    state — the in-session substrate's idiom (a live history stepped to a
    command position), stateless and re-buildable per replay call. Keyed by
    the ``TimelapseFrame`` itself (plan §8.3): ``replay`` calls
    ``provider(frame)``, never ``provider(frame.index)``."""

    def provider(frame):
        return history[frame.command_id]

    return provider


def _array_renderer(document):
    """A pure ``Document -> ndarray`` renderer: the array *is* the state."""
    return document.copy()


def test_replay_frame_count_matches_manifest():
    session = new_session()
    for cid in range(5):
        session = record_frame(session, command_id=cid)
    history = _history(5)
    frames = replay(session, _history_provider(history), _array_renderer)
    assert len(frames) == 5


def test_replay_is_deterministic_same_count_and_order():
    # SC-L018-1: the same recorded session replayed twice yields the same seq.
    session = new_session()
    for cid in range(4):
        session = record_frame(session, command_id=cid)
    history = _history(4)
    first = replay(session, _history_provider(history), _array_renderer)
    second = replay(session, _history_provider(history), _array_renderer)
    assert len(first) == len(second) == 4
    for a, b in zip(first, second):
        assert np.array_equal(a, b)


def test_replay_empty_session_yields_no_frames():
    assert replay(new_session(), _history_provider([]), _array_renderer) == ()


def test_replay_rejects_non_callable_renderer():
    # provider must itself be a valid callable so this isolates the renderer
    # check (replay validates provider before renderer).
    with pytest.raises(TimelapseError):
        replay(new_session(), _history_provider([]), renderer=123)  # type: ignore[arg-type]


def test_replay_does_not_mutate_session():
    session = record_frame(new_session(), command_id=0)
    history = _history(1)
    replay(session, _history_provider(history), _array_renderer)
    assert [f.command_id for f in session.frames] == [0]
