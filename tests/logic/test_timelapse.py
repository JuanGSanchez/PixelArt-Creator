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
# REQ-P9-LOGIC-010 — replay determinism (count + order)                        #
# --------------------------------------------------------------------------- #


def _counting_renderer():
    """A pure-enough renderer emitting a distinct RGBA frame per call."""
    calls = {"n": 0}

    def render(_document):
        n = calls["n"]
        calls["n"] += 1
        return np.full((1, 1, 4), n % 256, dtype=np.uint8)

    return render


def test_replay_frame_count_matches_manifest():
    session = new_session()
    for cid in range(5):
        session = record_frame(session, command_id=cid)
    frames = replay(session, object(), _counting_renderer())
    assert len(frames) == 5


def test_replay_is_deterministic_same_count_and_order():
    # SC-L010-1: the same recorded session replayed twice yields the same seq.
    session = new_session()
    for cid in range(4):
        session = record_frame(session, command_id=cid)
    first = replay(session, object(), _counting_renderer())
    second = replay(session, object(), _counting_renderer())
    assert len(first) == len(second) == 4
    for a, b in zip(first, second):
        assert np.array_equal(a, b)


def test_replay_empty_session_yields_no_frames():
    assert replay(new_session(), object(), _counting_renderer()) == ()


def test_replay_rejects_non_callable_renderer():
    with pytest.raises(TimelapseError):
        replay(new_session(), object(), renderer=123)  # type: ignore[arg-type]


def test_replay_does_not_mutate_session():
    session = record_frame(new_session(), command_id=7)
    replay(session, object(), _counting_renderer())
    assert [f.command_id for f in session.frames] == [7]
