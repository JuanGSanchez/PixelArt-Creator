"""Animation engine — playback, onion-skin and frame tags (zero Qt, S11).

Phase 5 turns the shipped ``Document -> frames -> layers -> PixelBuffer`` tree
into a *timeline*. This module owns the pure, deterministic animation domain:

* the :class:`PlaybackMode` vocabulary (``LOOP`` / ``ONCE`` / ``PING_PONG`` /
  ``REVERSE``, default ``LOOP``) and the :data:`PLAYBACK_STOP` sentinel;
* deterministic frame **sequencing** (:func:`next_frame`,
  :func:`playback_steps`, :func:`tag_playback_steps`) — per-frame ``duration_ms``
  is the authoritative timing source (FR-2);
* the **onion-skin** overlay computation (:func:`onion_overlay`) which composites
  each previous/next frame stack via
  :func:`~pixelart_creator.logic.blend.composite_stack`, tints it toward
  :data:`~pixelart_creator.logic.constants.ONION_TINT_PREV` / ``ONION_TINT_NEXT``
  and fades it by distance;
* the :class:`FrameTag` model (named animation range) plus range
  validation/clamp helpers.

Like :mod:`~pixelart_creator.logic.blend`, this module **never imports**
:mod:`~pixelart_creator.logic.document`: it consumes layer stacks structurally
through the :class:`~pixelart_creator.logic.blend.CompositeNode` Protocol and
plain ``Sequence[int]`` durations, keeping the import graph one-way and acyclic
(``document -> animation -> blend -> color/constants/pixel_buffer``, PL5-D3 /
ADR-0011). The playback wall-clock (a ``QTimer``) lives in ``ui/`` only; every
next-frame *decision* here is pure and clock-free (P2, Article I).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np

from pixelart_creator.logic.blend import CompositeNode, composite_stack
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    MAX_ONION_SKIN_FRAMES,
    ONION_SKIN_OPACITY,
    ONION_SKIN_OPACITY_MIN,
    ONION_TINT_NEXT,
    ONION_TINT_PREV,
)
from pixelart_creator.logic.pixel_buffer import PixelBuffer

__all__ = [
    "AnimationError",
    "PlaybackMode",
    "DEFAULT_PLAYBACK_MODE",
    "PLAYBACK_STOP",
    "next_frame",
    "playback_steps",
    "tag_playback_steps",
    "OnionContribution",
    "onion_overlay",
    "FrameTag",
    "validate_tag_range",
    "clamp_tag_range",
]

_UINT8_MAX = 255.0


class AnimationError(ValueError):
    """Raised on an invalid playback range, onion bound, or tag range."""


class PlaybackMode(enum.Enum):
    """The four supported playback modes (REQ-P5-LOGIC-001).

    The single source of the playback-mode vocabulary shared by the sequencing
    engine, the :class:`FrameTag` model, the UI mode selector and ``.pixproj``
    (the value strings are the stable ``.pixproj`` tokens, ADR-0012). Like
    :class:`~pixelart_creator.logic.blend.BlendMode` this is an enumerated
    *vocabulary*, not a numeric tuning value, so it lives here rather than in
    ``constants.py`` (BF-2).
    """

    LOOP = "loop"  # start->end, wrap to start (default)
    ONCE = "once"  # start->end, stop on the last frame (no wrap)
    PING_PONG = "ping_pong"  # start->end->start, endpoints NOT doubled (CL-5)
    REVERSE = "reverse"  # end->start, wrap to end when looping


#: The default playback mode for a document / new tag (CL-3).
DEFAULT_PLAYBACK_MODE: PlaybackMode = PlaybackMode.LOOP


class _PlaybackStop:
    """Type of the :data:`PLAYBACK_STOP` sentinel (a private singleton)."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "PLAYBACK_STOP"


#: Yielded by :func:`next_frame` when a non-looping run (``ONCE``) completes.
PLAYBACK_STOP: _PlaybackStop = _PlaybackStop()

#: A frame index yielded by the sequencer, or the completion sentinel.
FrameStep = Union[int, _PlaybackStop]

#: The set of modes that repeat indefinitely when ``repeat`` is unset.
_LOOPING_MODES = (PlaybackMode.LOOP, PlaybackMode.PING_PONG, PlaybackMode.REVERSE)


# --------------------------------------------------------------------------- #
# Deterministic frame sequencing (REQ-P5-LOGIC-002/003)                        #
# --------------------------------------------------------------------------- #


def _entry(mode: PlaybackMode, start: int, end: int) -> Tuple[int, int]:
    """Return the ``(entry_index, entry_direction)`` for a playback ``mode``.

    Forward modes (``LOOP`` / ``ONCE`` / ``PING_PONG``) enter at ``start`` moving
    ``+1``; ``REVERSE`` enters at ``end`` moving ``-1``.
    """
    if mode is PlaybackMode.REVERSE:
        return end, -1
    return start, 1


def next_frame(
    current: int, direction: int, start: int, end: int, mode: PlaybackMode
) -> Tuple[FrameStep, int]:
    """Return ``(next_index_or_PLAYBACK_STOP, new_direction)`` for one step.

    Pure and deterministic (no clock, no RNG — P2). ``current`` must lie in the
    inclusive range ``start..end`` and ``direction`` must be ``-1`` or ``+1``.

    - **LOOP:** advance ``+1``, wrapping ``end -> start`` (never stops).
    - **ONCE:** advance ``+1``; stepping past ``end`` yields
      :data:`PLAYBACK_STOP`.
    - **REVERSE:** advance ``-1``, wrapping ``start -> end`` (never stops).
    - **PING_PONG:** advance by ``direction``; reflect at either endpoint —
      endpoint frames are **not** doubled (CL-5), so the returned direction
      flips and the next index steps back inward.
    - A single-frame range (``start == end``) yields that frame for every mode.

    Raises:
        AnimationError: If ``mode`` is not a :class:`PlaybackMode`, the range is
            inverted, ``current`` is out of range, or ``direction`` is invalid.
    """
    if not isinstance(mode, PlaybackMode):
        raise AnimationError(f"mode must be a PlaybackMode, got {mode!r}")
    if start > end:
        raise AnimationError(f"inverted range: start {start} > end {end}")
    if not start <= current <= end:
        raise AnimationError(f"current {current} outside range {start}..{end}")
    if direction not in (-1, 1):
        raise AnimationError(f"direction must be -1 or +1, got {direction!r}")

    if start == end:
        return start, direction

    if mode is PlaybackMode.LOOP:
        nxt = current + 1
        return (start if nxt > end else nxt), 1
    if mode is PlaybackMode.ONCE:
        nxt = current + 1
        return (PLAYBACK_STOP, 1) if nxt > end else (nxt, 1)
    if mode is PlaybackMode.REVERSE:
        nxt = current - 1
        return (end if nxt < start else nxt), -1

    # PING_PONG — reflect at the endpoints without doubling them.
    nxt = current + direction
    if nxt > end:
        return current - 1, -1
    if nxt < start:
        return current + 1, 1
    return nxt, direction


def _single_pass_indices(mode: PlaybackMode, start: int, end: int) -> List[int]:
    """Return the index sequence for **one pass** of ``mode`` over ``start..end``.

    Concatenating this list yields the full playback sequence (verified against
    SC-L002-1): ``LOOP``/``ONCE`` -> ``[start..end]``; ``REVERSE`` ->
    ``[end..start]``; ``PING_PONG`` -> ``[start..end] + (end-1..start+1)`` (a full
    bounce with endpoints emitted once, CL-5). A single-frame range is ``[start]``.
    """
    if start == end:
        return [start]
    forward = list(range(start, end + 1))
    if mode is PlaybackMode.REVERSE:
        return list(range(end, start - 1, -1))
    if mode is PlaybackMode.PING_PONG:
        return forward + list(range(end - 1, start, -1))
    return forward  # LOOP, ONCE


def playback_steps(
    durations: Sequence[int],
    mode: PlaybackMode,
    *,
    start: int = 0,
    end: Optional[int] = None,
    repeat: int = 0,
) -> Iterator[Tuple[int, int]]:
    """Yield ``(frame_index, duration_ms)`` pairs for a playback run.

    Per-frame ``duration_ms`` is the authoritative timing source (REQ-P5-LOGIC-003,
    CL-6): each yielded index is paired with ``durations[index]`` so the ``ui/``
    timing driver waits that long before advancing. ``end`` defaults to
    ``len(durations) - 1``.

    ``repeat`` is the number of passes over the range: ``repeat > 0`` yields
    exactly that many passes then stops (for **every** mode — e.g. an ``ONCE``
    tag with ``repeat=2`` plays its range twice then stops, SC-L011-1);
    ``repeat <= 0`` means *infinite* for looping modes (``LOOP`` / ``PING_PONG`` /
    ``REVERSE``) and a *single* pass for ``ONCE``.

    Deterministic (P2): identical arguments yield identical index sequences.

    Raises:
        AnimationError: On empty ``durations``, an out-of-range/inverted
            ``start``/``end``, a non-:class:`PlaybackMode` ``mode``, or a
            non-int/negative ``repeat``.
    """
    n = len(durations)
    if n < 1:
        raise AnimationError("durations must be non-empty")
    if not isinstance(mode, PlaybackMode):
        raise AnimationError(f"mode must be a PlaybackMode, got {mode!r}")
    if end is None:
        end = n - 1
    if not (0 <= start <= end <= n - 1):
        raise AnimationError(f"range {start}..{end} invalid for {n} frames")
    if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat < 0:
        raise AnimationError(f"repeat must be a non-negative int, got {repeat!r}")

    indices = _single_pass_indices(mode, start, end)
    if repeat > 0:
        for _pass in range(repeat):
            for index in indices:
                yield index, durations[index]
        return
    if mode not in _LOOPING_MODES:  # ONCE with repeat <= 0 -> a single pass.
        for index in indices:
            yield index, durations[index]
        return
    while True:  # looping mode, infinite.
        for index in indices:
            yield index, durations[index]


def tag_playback_steps(
    tag: "FrameTag", durations: Sequence[int]
) -> Iterator[Tuple[int, int]]:
    """Yield the playback steps for a named animation (REQ-P5-LOGIC-011).

    Runs :func:`playback_steps` over the tag's inclusive ``[from_frame, to_frame]``
    sub-range under the tag's **own** :class:`PlaybackMode` and ``repeat`` count,
    independently of any document-global mode.
    """
    return playback_steps(
        durations,
        tag.mode,
        start=tag.from_frame,
        end=tag.to_frame,
        repeat=tag.repeat,
    )


# --------------------------------------------------------------------------- #
# Onion-skin overlay (REQ-P5-LOGIC-012/013)                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OnionContribution:
    """One onion ghost: a composited, tinted, faded frame to draw behind active.

    ``buffer`` is the frame's flattened RGBA composite tinted toward the onion
    tint and scaled in alpha by the distance falloff. ``z_order`` orders the
    ghosts: it is negative (below the active frame, ``z = 0``) and ``-distance``,
    so farther ghosts (more negative) render behind nearer ones.
    """

    buffer: PixelBuffer
    z_order: int


def _linear_opacity(distance: int, count: int) -> float:
    """Linear onion opacity for a ghost at 1-based ``distance`` of ``count``.

    ``distance == 1`` (nearest) -> :data:`ONION_SKIN_OPACITY`; ``distance ==
    count`` (farthest) -> :data:`ONION_SKIN_OPACITY_MIN`; a single ghost uses the
    nearest opacity.
    """
    if count <= 1:
        return ONION_SKIN_OPACITY
    frac = (distance - 1) / (count - 1)
    return ONION_SKIN_OPACITY + frac * (ONION_SKIN_OPACITY_MIN - ONION_SKIN_OPACITY)


def _tint_and_fade(buffer: PixelBuffer, tint: RGBA, opacity: float) -> PixelBuffer:
    """Return a copy of ``buffer`` tinted toward ``tint`` and faded by ``opacity``.

    The tint's **alpha** channel is the mix strength ``t = tint_alpha / 255``:
    each pixel's RGB is blended ``rgb * (1 - t) + tint_rgb * t`` (the default
    fully-opaque tints yield a solid tint silhouette; a UI may pass a lower-alpha
    tint for a partial recolour). The pixel's own alpha (already excluding hidden
    layers, honouring CL-12) is scaled by ``opacity``. Never mutates ``buffer``.
    """
    tr, tg, tb, ta = tint
    t = ta / _UINT8_MAX
    out = buffer.copy()
    data = out.data
    rgb = data[:, :, :3].astype(np.float64)
    tint_rgb = np.array([tr, tg, tb], dtype=np.float64)
    blended = rgb * (1.0 - t) + tint_rgb * t
    data[:, :, :3] = np.clip(np.round(blended), 0, 255).astype(np.uint8)
    alpha = data[:, :, 3].astype(np.float64) * float(opacity)
    data[:, :, 3] = np.clip(np.round(alpha), 0, 255).astype(np.uint8)
    return out


def onion_overlay(
    prev_stacks: Sequence[Sequence[CompositeNode]],
    next_stacks: Sequence[Sequence[CompositeNode]],
    width: int,
    height: int,
    *,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> List[OnionContribution]:
    """Compute the onion-skin ghost contributions around the active frame.

    ``prev_stacks[0]`` / ``next_stacks[0]`` are the **nearest** previous/next
    neighbour layer stacks; index grows with distance. Each stack is flattened
    via :func:`~pixelart_creator.logic.blend.composite_stack` (CO-4 reuse — no
    compositing maths re-implemented, REQ-P5-LOGIC-013), tinted toward
    :data:`~pixelart_creator.logic.constants.ONION_TINT_PREV` (previous) or
    ``ONION_TINT_NEXT`` (next), and faded linearly from
    :data:`~pixelart_creator.logic.constants.ONION_SKIN_OPACITY` (nearest) to
    ``ONION_SKIN_OPACITY_MIN`` (farthest). Hidden layers are already absent from
    each composite (CL-12). The active frame is not part of the set and is
    unchanged. Pure and Qt-free; **not** rendered during playback (CL-11).

    Both counts are bounded by
    :data:`~pixelart_creator.logic.constants.MAX_ONION_SKIN_FRAMES`.

    Args:
        prev_stacks: Nearest-first previous frame layer stacks.
        next_stacks: Nearest-first next frame layer stacks.
        width, height: Canvas geometry the stacks composite against.
        region: Optional ``(x, y, w, h)`` scene-space region (passed straight to
            :func:`~pixelart_creator.logic.blend.composite_stack`); ``None``
            composites the full canvas.

    Returns:
        The list of :class:`OnionContribution` (previous ghosts then next ghosts).

    Raises:
        AnimationError: If either count exceeds ``MAX_ONION_SKIN_FRAMES``.
        BlendError: If a layer buffer geometry is wrong or ``region`` is invalid.
    """
    if len(prev_stacks) > MAX_ONION_SKIN_FRAMES:
        raise AnimationError(
            f"previous onion count {len(prev_stacks)} exceeds "
            f"MAX_ONION_SKIN_FRAMES ({MAX_ONION_SKIN_FRAMES})"
        )
    if len(next_stacks) > MAX_ONION_SKIN_FRAMES:
        raise AnimationError(
            f"next onion count {len(next_stacks)} exceeds "
            f"MAX_ONION_SKIN_FRAMES ({MAX_ONION_SKIN_FRAMES})"
        )

    contributions: List[OnionContribution] = []
    prev_count = len(prev_stacks)
    for distance, stack in enumerate(prev_stacks, start=1):
        composite = composite_stack(stack, width, height, region=region)
        opacity = _linear_opacity(distance, prev_count)
        ghost = _tint_and_fade(composite, ONION_TINT_PREV, opacity)
        contributions.append(OnionContribution(ghost, -distance))
    next_count = len(next_stacks)
    for distance, stack in enumerate(next_stacks, start=1):
        composite = composite_stack(stack, width, height, region=region)
        opacity = _linear_opacity(distance, next_count)
        ghost = _tint_and_fade(composite, ONION_TINT_NEXT, opacity)
        contributions.append(OnionContribution(ghost, -distance))
    return contributions


# --------------------------------------------------------------------------- #
# Frame-tag model (REQ-P5-LOGIC-009/010)                                       #
# --------------------------------------------------------------------------- #


@dataclass
class FrameTag:
    """A named animation over an inclusive frame range (REQ-P5-LOGIC-009).

    ``from_frame <= to_frame`` and both index into the document's frames. ``mode``
    and ``repeat`` are the tag's own playback semantics (``repeat = 0`` means
    infinite for looping modes); ``color`` is a ``#rrggbbaa`` UI marker. Tag names
    need not be unique and ranges may overlap; the owning collection preserves
    creation order (CL-8). Range validity against a frame count is enforced by the
    :class:`~pixelart_creator.logic.document.Document` builder that owns that
    context (it raises :class:`~pixelart_creator.logic.document.DocumentError`);
    :func:`validate_tag_range` / :func:`clamp_tag_range` are the free-standing
    helpers.
    """

    name: str
    from_frame: int
    to_frame: int
    mode: PlaybackMode = PlaybackMode.LOOP
    repeat: int = 0
    color: str = "#ff0000ff"

    def __post_init__(self) -> None:
        """Validate the tag's own range shape (types, non-negative, ordered).

        Delegates to :func:`validate_tag_range` with a ``frame_count`` derived
        from ``to_frame`` itself, so this checks the tag's OWN well-formedness
        (both bounds are ints, ``0 <= from_frame <= to_frame``) without needing
        the document's actual frame count — validating a range against the real
        frame count stays the :class:`~pixelart_creator.logic.document.Document`
        builder's job (ADR-0011: this module never imports ``document``, a
        one-way edge).

        Raises:
            AnimationError: If either bound is not an int, or the range is
                inverted or negative.
        """
        frame_count = (
            self.to_frame + 1
            if isinstance(self.to_frame, int) and not isinstance(self.to_frame, bool)
            else 1
        )
        validate_tag_range(self.from_frame, self.to_frame, frame_count)


def validate_tag_range(from_frame: int, to_frame: int, frame_count: int) -> None:
    """Validate an inclusive tag range against a frame count.

    Raises:
        AnimationError: If either bound is not an int, ``frame_count < 1``, or the
            range is inverted or steps outside ``0..frame_count - 1``.
    """
    for label, value in (("from_frame", from_frame), ("to_frame", to_frame)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise AnimationError(f"{label} must be an int, got {value!r}")
    if frame_count < 1:
        raise AnimationError(f"frame_count must be >= 1, got {frame_count}")
    if not 0 <= from_frame <= to_frame < frame_count:
        raise AnimationError(
            f"tag range [{from_frame}, {to_frame}] invalid for " f"{frame_count} frames"
        )


def clamp_tag_range(tag: FrameTag, frame_count: int) -> FrameTag:
    """Return a copy of ``tag`` with its range clamped into the frame count.

    Both bounds are clamped into ``0..frame_count - 1`` (order preserved), keeping
    a tag valid after frames are added/removed (REQ-P5-LOGIC-010). Every other
    field is copied unchanged.

    Raises:
        AnimationError: If ``frame_count < 1``.
    """
    if frame_count < 1:
        raise AnimationError(f"frame_count must be >= 1, got {frame_count}")
    high = frame_count - 1
    new_from = min(max(tag.from_frame, 0), high)
    new_to = min(max(tag.to_frame, 0), high)
    if new_from > new_to:
        new_from = new_to
    return FrameTag(
        tag.name, new_from, new_to, mode=tag.mode, repeat=tag.repeat, color=tag.color
    )
