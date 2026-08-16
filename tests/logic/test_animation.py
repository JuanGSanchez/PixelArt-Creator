"""Tests for the Phase-5 animation engine (Slice 5A, zero Qt).

Covers :mod:`pixelart_creator.logic.animation`: the :class:`PlaybackMode`
vocabulary + default, deterministic frame sequencing for every mode
(:func:`next_frame`, :func:`playback_steps`, :func:`tag_playback_steps`), the
onion-skin overlay (tint / fade / z-order / bounds / hidden-layer honour), the
:class:`FrameTag` model, and the range validate/clamp helpers.

Maps to REQ-P5-LOGIC-001..003, -009..014 and Gherkin SC-L001-1 / SC-L002-1..3 /
SC-L003-1 / SC-L009-1 / SC-L011-1 / SC-L012-1..2 / SC-L014-2.
"""

from __future__ import annotations

import itertools
from typing import List, Union

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import animation as anim
from pixelart_creator.logic.animation import (
    DEFAULT_PLAYBACK_MODE,
    PLAYBACK_STOP,
    AnimationError,
    FrameTag,
    OnionContribution,
    PlaybackMode,
    clamp_tag_range,
    next_frame,
    onion_overlay,
    playback_steps,
    tag_playback_steps,
    validate_tag_range,
)
from pixelart_creator.logic.constants import (
    DEFAULT_ONION_NEXT,
    DEFAULT_ONION_PREV,
    MAX_ONION_SKIN_FRAMES,
    ONION_SKIN_OPACITY,
    ONION_SKIN_OPACITY_MIN,
    ONION_TINT_NEXT,
    ONION_TINT_PREV,
)
from pixelart_creator.logic.document import Layer
from pixelart_creator.logic.pixel_buffer import PixelBuffer

WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


# --------------------------------------------------------------------------- #
# Sequence helper (drives next_frame from each mode's entry point)             #
# --------------------------------------------------------------------------- #


def _emit(
    start: int, end: int, mode: PlaybackMode, steps: int
) -> List[Union[int, str]]:
    """Emit ``steps`` sequenced indices via :func:`next_frame` (``"stop"`` sentinel)."""
    if mode is PlaybackMode.REVERSE:
        current, direction = end, -1
    else:
        current, direction = start, 1
    out: List[Union[int, str]] = [current]
    stopped = False
    while len(out) < steps:
        if stopped:
            out.append("stop")
            continue
        nxt, direction = next_frame(current, direction, start, end, mode)
        if nxt is PLAYBACK_STOP:
            out.append("stop")
            stopped = True
        else:
            assert isinstance(nxt, int)
            out.append(nxt)
            current = nxt
    return out


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-001 — PlaybackMode enum (SC-L001-1)                             #
# --------------------------------------------------------------------------- #


def test_playback_mode_has_exactly_four_members():
    assert {m.name for m in PlaybackMode} == {"LOOP", "ONCE", "PING_PONG", "REVERSE"}


def test_default_playback_mode_is_loop():
    assert DEFAULT_PLAYBACK_MODE is PlaybackMode.LOOP


def test_playback_mode_values_are_stable_pixproj_tokens():
    assert PlaybackMode.LOOP.value == "loop"
    assert PlaybackMode.ONCE.value == "once"
    assert PlaybackMode.PING_PONG.value == "ping_pong"
    assert PlaybackMode.REVERSE.value == "reverse"


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-002 — deterministic sequencing per mode (SC-L002-1..3)          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (PlaybackMode.LOOP, [0, 1, 2, 3, 0, 1, 2, 3, 0, 1]),
        (
            PlaybackMode.ONCE,
            [0, 1, 2, 3, "stop", "stop", "stop", "stop", "stop", "stop"],
        ),
        (PlaybackMode.REVERSE, [3, 2, 1, 0, 3, 2, 1, 0, 3, 2]),
        (PlaybackMode.PING_PONG, [0, 1, 2, 3, 2, 1, 0, 1, 2, 3]),
    ],
)
def test_sequence_over_four_frame_range(mode, expected):
    assert _emit(0, 3, mode, 10) == expected


def test_ping_pong_endpoints_not_doubled():
    # A full bounce over 0..3 must never repeat 0 or 3 consecutively (CL-5).
    seq = _emit(0, 3, PlaybackMode.PING_PONG, 14)
    for a, b in zip(seq, seq[1:]):
        assert a != b


def test_once_returns_stop_sentinel_stepping_past_end():
    nxt, direction = next_frame(3, 1, 0, 3, PlaybackMode.ONCE)
    assert nxt is PLAYBACK_STOP
    assert direction == 1


def test_reverse_wraps_start_to_end():
    nxt, direction = next_frame(0, -1, 0, 3, PlaybackMode.REVERSE)
    assert nxt == 3 and direction == -1


def test_loop_wraps_end_to_start():
    nxt, direction = next_frame(3, 1, 0, 3, PlaybackMode.LOOP)
    assert nxt == 0 and direction == 1


def test_ping_pong_reflects_at_lower_endpoint():
    nxt, direction = next_frame(0, -1, 0, 3, PlaybackMode.PING_PONG)
    assert nxt == 1 and direction == 1


@pytest.mark.parametrize("mode", list(PlaybackMode))
def test_single_frame_range_yields_that_frame(mode):
    # SC-L002-3: a start==end range yields the frame for every mode, never stops.
    seq = _emit(2, 2, mode, 8)
    assert seq == [2] * 8


def test_two_frame_edge_cases_all_modes():
    assert _emit(0, 1, PlaybackMode.LOOP, 5) == [0, 1, 0, 1, 0]
    assert _emit(0, 1, PlaybackMode.ONCE, 5) == [0, 1, "stop", "stop", "stop"]
    assert _emit(0, 1, PlaybackMode.REVERSE, 5) == [1, 0, 1, 0, 1]
    # PING_PONG over two frames degenerates to a straight alternation.
    assert _emit(0, 1, PlaybackMode.PING_PONG, 5) == [0, 1, 0, 1, 0]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"current": 0, "direction": 1, "start": 0, "end": 3, "mode": "loop"},
        {"current": 0, "direction": 1, "start": 3, "end": 0, "mode": PlaybackMode.LOOP},
        {"current": 5, "direction": 1, "start": 0, "end": 3, "mode": PlaybackMode.LOOP},
        {"current": 0, "direction": 2, "start": 0, "end": 3, "mode": PlaybackMode.LOOP},
    ],
)
def test_next_frame_rejects_invalid_input(kwargs):
    with pytest.raises(AnimationError):
        next_frame(**kwargs)


@given(
    lo=st.integers(min_value=0, max_value=20),
    span=st.integers(min_value=0, max_value=20),
    mode=st.sampled_from(list(PlaybackMode)),
    steps=st.integers(min_value=1, max_value=30),
)
def test_sequence_is_deterministic(lo, span, mode, steps):
    # SC-L002-2: identical inputs always emit identical indices (P2).
    end = lo + span
    assert _emit(lo, end, mode, steps) == _emit(lo, end, mode, steps)


@given(
    lo=st.integers(min_value=0, max_value=10),
    span=st.integers(min_value=0, max_value=10),
    mode=st.sampled_from(list(PlaybackMode)),
    steps=st.integers(min_value=1, max_value=40),
)
def test_sequence_stays_in_range(lo, span, mode, steps):
    end = lo + span
    for value in _emit(lo, end, mode, steps):
        if value != "stop":
            assert lo <= value <= end


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-003 — playback_steps timing pairing (SC-L003-1)                 #
# --------------------------------------------------------------------------- #


def test_playback_steps_pairs_index_with_duration():
    # REQ-P5-LOGIC-011 (R-25): playback_steps yields (index, duration) pairs.
    durations = [100, 500, 100]
    steps = list(itertools.islice(playback_steps(durations, PlaybackMode.LOOP), 5))
    assert steps == [(0, 100), (1, 500), (2, 100), (0, 100), (1, 500)]


def test_playback_steps_once_single_pass_when_repeat_unset():
    steps = list(playback_steps([10, 20, 30], PlaybackMode.ONCE))
    assert steps == [(0, 10), (1, 20), (2, 30)]


def test_playback_steps_repeat_gives_exact_passes_for_every_mode():
    # ONCE + repeat=2 plays its range twice then stops (SC-L011-1 mechanism).
    steps = list(playback_steps([10, 20], PlaybackMode.ONCE, repeat=2))
    assert steps == [(0, 10), (1, 20), (0, 10), (1, 20)]


def test_playback_steps_reverse_single_pass_indices():
    steps = list(itertools.islice(playback_steps([1, 2, 3], PlaybackMode.REVERSE), 5))
    assert [i for i, _ in steps] == [2, 1, 0, 2, 1]


def test_playback_steps_ping_pong_bounces():
    steps = list(
        itertools.islice(playback_steps([1, 2, 3, 4], PlaybackMode.PING_PONG), 8)
    )
    assert [i for i, _ in steps] == [0, 1, 2, 3, 2, 1, 0, 1]


def test_playback_steps_subrange():
    steps = list(playback_steps([1, 2, 3, 4], PlaybackMode.ONCE, start=1, end=2))
    assert steps == [(1, 2), (2, 3)]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"durations": [], "mode": PlaybackMode.LOOP},
        {"durations": [1, 2], "mode": "loop"},
        {"durations": [1, 2], "mode": PlaybackMode.LOOP, "start": 1, "end": 0},
        {"durations": [1, 2], "mode": PlaybackMode.LOOP, "end": 5},
        {"durations": [1, 2], "mode": PlaybackMode.LOOP, "repeat": -1},
        {"durations": [1, 2], "mode": PlaybackMode.LOOP, "repeat": True},
    ],
)
def test_playback_steps_rejects_invalid_input(kwargs):
    with pytest.raises(AnimationError):
        list(playback_steps(**kwargs))


def test_tag_playback_steps_uses_tag_mode_and_range():
    # SC-L011-1: an ONCE tag with repeat 2 over 2..3 plays 2,3,2,3 then stops.
    tag = FrameTag("idle", 2, 3, mode=PlaybackMode.ONCE, repeat=2)
    steps = list(tag_playback_steps(tag, [100, 100, 200, 300]))
    assert steps == [(2, 200), (3, 300), (2, 200), (3, 300)]


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-012 — onion-skin overlay (SC-L012-1..2)                         #
# --------------------------------------------------------------------------- #


def _layer_stack(color, *, visible=True):
    """A one-layer composite stack (a Layer is a CompositeNode) painted solid."""
    buf = PixelBuffer(2, 2)
    buf.fill(color)
    return [Layer(buf, "L", visible=visible)]


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-013 (T-05) — SC-L013-1, literal: per-frame render ==             #
# composite_stack of that frame's (stack's) layers, not re-implemented.        #
# --------------------------------------------------------------------------- #


def test_sc_l013_1_onion_composite_delegates_to_composite_stack_on_the_stack():
    """SC-L013-1: onion_overlay's per-frame render is literally composite_stack
    called on that frame's own layer stack (CO-4 reuse, no independent
    compositing maths, REQ-P5-LOGIC-013)."""
    from unittest.mock import patch

    from pixelart_creator.logic import animation as anim_mod
    from pixelart_creator.logic.animation import composite_stack as _real

    stack = _layer_stack(WHITE)
    with patch.object(anim_mod, "composite_stack", wraps=_real) as spy:
        onion_overlay([stack], [], 2, 2)
    spy.assert_called_once_with(stack, 2, 2, region=None)


def test_onion_overlay_tints_prev_toward_prev_tint_and_next_toward_next():
    prev = [_layer_stack(WHITE)]
    nxt = [_layer_stack(WHITE)]
    ghosts = onion_overlay(prev, nxt, 2, 2)
    assert len(ghosts) == 2
    prev_ghost, next_ghost = ghosts
    # A fully-opaque tint (alpha 255) drives rgb entirely to the tint colour.
    assert tuple(prev_ghost.buffer.data[0, 0, :3]) == ONION_TINT_PREV[:3]
    assert tuple(next_ghost.buffer.data[0, 0, :3]) == ONION_TINT_NEXT[:3]


def test_onion_overlay_scales_alpha_by_opacity_and_excludes_active():
    prev = [_layer_stack(WHITE)]
    active_before = prev[0][0].buffer.get_pixel(0, 0)
    ghosts = onion_overlay(prev, [], 2, 2)
    expected_alpha = round(255 * ONION_SKIN_OPACITY)
    assert int(ghosts[0].buffer.data[0, 0, 3]) == expected_alpha
    # The source (active) stack buffer is never mutated.
    assert prev[0][0].buffer.get_pixel(0, 0) == active_before


def test_onion_overlay_z_order_farther_is_more_negative():
    prev = [_layer_stack(WHITE), _layer_stack(WHITE)]
    ghosts = onion_overlay(prev, [], 2, 2)
    assert [g.z_order for g in ghosts] == [-1, -2]
    assert all(g.z_order < 0 for g in ghosts)


def test_onion_overlay_linear_fade_by_distance():
    prev = [_layer_stack(WHITE), _layer_stack(WHITE)]
    ghosts = onion_overlay(prev, [], 2, 2)
    near = int(ghosts[0].buffer.data[0, 0, 3])
    far = int(ghosts[1].buffer.data[0, 0, 3])
    assert near == round(255 * ONION_SKIN_OPACITY)
    assert far == round(255 * ONION_SKIN_OPACITY_MIN)
    assert far < near


def test_onion_overlay_empty_when_no_counts():
    assert onion_overlay([], [], 2, 2) == []


def test_onion_overlay_honours_hidden_layers():
    # SC-L012-2: a hidden layer contributes nothing -> transparent ghost.
    hidden_stack = [_layer_stack(WHITE, visible=False)]
    ghosts = onion_overlay(hidden_stack, [], 2, 2)
    assert int(ghosts[0].buffer.data[0, 0, 3]) == 0


def test_onion_overlay_rejects_prev_count_over_bound():
    too_many = [_layer_stack(WHITE) for _ in range(MAX_ONION_SKIN_FRAMES + 1)]
    with pytest.raises(AnimationError):
        onion_overlay(too_many, [], 2, 2)


def test_onion_overlay_rejects_next_count_over_bound():
    too_many = [_layer_stack(WHITE) for _ in range(MAX_ONION_SKIN_FRAMES + 1)]
    with pytest.raises(AnimationError):
        onion_overlay([], too_many, 2, 2)


def test_onion_overlay_region_passthrough():
    prev = [_layer_stack(WHITE)]
    ghosts = onion_overlay(prev, [], 2, 2, region=(0, 0, 1, 1))
    assert ghosts[0].buffer.width == 1 and ghosts[0].buffer.height == 1


def test_onion_contribution_is_frozen():
    contribution = OnionContribution(PixelBuffer(1, 1), -1)
    with pytest.raises(Exception):
        contribution.z_order = -2  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-014 — onion defaults from constants (SC-L014-2)                 #
# --------------------------------------------------------------------------- #


def test_onion_defaults_and_tints_come_from_constants():
    assert DEFAULT_ONION_PREV == 1 and DEFAULT_ONION_NEXT == 1
    assert ONION_TINT_PREV == (255, 0, 0, 255)
    assert ONION_TINT_NEXT == (0, 0, 255, 255)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-009 — FrameTag model + range helpers (SC-L009-1)                #
# --------------------------------------------------------------------------- #


def test_frame_tag_defaults():
    tag = FrameTag("walk", 1, 4)
    assert tag.mode is PlaybackMode.LOOP
    assert tag.repeat == 0
    assert tag.color == "#ff0000ff"


# Regression test for C-06 — proven by reversion in the commit pass
def test_frame_tag_construction_validates_range_via_post_init():
    """FrameTag("x", 5, 2) raises AnimationError AT CONSTRUCTION time.

    Before the fix, an inverted (from_frame > to_frame) FrameTag could be built
    with no validation and would only fail later, elsewhere, in a confusing way.
    __post_init__ now delegates to validate_tag_range immediately.
    """
    with pytest.raises(AnimationError):
        FrameTag("x", 5, 2)


def test_frame_tag_construction_rejects_negative_from_frame():
    """Regression test for C-06 — proven by reversion in the commit pass."""
    with pytest.raises(AnimationError):
        FrameTag("x", -1, 2)


def test_frame_tag_construction_accepts_a_valid_range():
    """Regression test for C-06 — proven by reversion in the commit pass."""
    tag = FrameTag("x", 2, 5)  # no raise
    assert (tag.from_frame, tag.to_frame) == (2, 5)


def test_validate_tag_range_accepts_valid():
    validate_tag_range(1, 4, 6)  # no raise


@pytest.mark.parametrize(
    "args",
    [
        (True, 4, 6),  # bool from_frame
        (1, 4.0, 6),  # non-int to_frame
        (1, 4, 0),  # frame_count < 1
        (4, 1, 6),  # inverted
        (1, 6, 6),  # out of range (to == count)
        (-1, 4, 6),  # negative
    ],
)
def test_validate_tag_range_rejects_invalid(args):
    with pytest.raises(AnimationError):
        validate_tag_range(*args)


def test_clamp_tag_range_clamps_high_bound():
    clamped = clamp_tag_range(FrameTag("run", 2, 5), 5)
    assert (clamped.from_frame, clamped.to_frame) == (2, 4)
    assert clamped.name == "run"


def test_clamp_tag_range_preserves_fields():
    tag = FrameTag("t", 0, 0, mode=PlaybackMode.PING_PONG, repeat=3, color="#00ff00ff")
    clamped = clamp_tag_range(tag, 4)
    assert clamped.mode is PlaybackMode.PING_PONG
    assert clamped.repeat == 3
    assert clamped.color == "#00ff00ff"


def test_clamp_tag_range_collapses_when_both_above_count():
    clamped = clamp_tag_range(FrameTag("t", 5, 9), 3)
    assert clamped.from_frame == 2 and clamped.to_frame == 2


def test_clamp_tag_range_rejects_zero_frame_count():
    with pytest.raises(AnimationError):
        clamp_tag_range(FrameTag("t", 0, 0), 0)


@given(
    frame_count=st.integers(min_value=1, max_value=32),
    lo=st.integers(min_value=-10, max_value=40),
    hi=st.integers(min_value=-10, max_value=40),
)
def test_clamp_tag_range_always_produces_valid_range(frame_count, lo, hi):
    # Repaired for C-06: FrameTag.__post_init__ now validates its OWN range
    # (validate_tag_range) at construction, so an inverted/negative (lo, hi)
    # pair can no longer be built via the constructor directly. Build a valid
    # tag first, then set the raw (possibly out-of-range) bounds by attribute
    # assignment — FrameTag is a plain (non-frozen) dataclass, so this bypasses
    # __post_init__ and still exercises clamp_tag_range's own defensive
    # handling of an arbitrary (lo, hi) pair, preserving the original property:
    # clamp_tag_range always produces a range valid_tag_range accepts.
    tag = FrameTag("t", 0, 0)
    tag.from_frame = lo
    tag.to_frame = hi
    clamped = clamp_tag_range(tag, frame_count)
    validate_tag_range(clamped.from_frame, clamped.to_frame, frame_count)


def test_module_all_surface():
    for name in anim.__all__:
        assert hasattr(anim, name)
