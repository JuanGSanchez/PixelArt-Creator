"""Reproducible timelapse session model — pure, per-command, zero Qt (S11).

Records a **reproducible** edit-session frame sequence (ADR-0024 §2, research §6):
one frame per committed undoable command (the Procreate cadence), reusing the
shipped deterministic history (HIS-1). The model stores a **command manifest** —
ordered ``TimelapseFrame(index, command_id)`` records, **not** inline pixels — so a
session re-renders deterministically and stays small (research §6.3).

``replay`` re-derives each frame by **document render** (``blend.composite_stack``,
CO-4) via a caller-supplied pure ``renderer`` — reproducible, resolution-independent
and UI-chrome-free (research §6.2). The same recorded session replayed twice yields
the **same** frame sequence: no wall-clock, no RNG, no locale (REQ-P9-LOGIC-009).

Encoding is **deferred** (ADR-0024 §2, spec §6): Phase 9 ships the reproducible
sequence only; GIF export reuses Phase-7 ``encode_gif`` as a later handoff — this
module never encodes. Constants come from
:mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Tuple

from pixelart_creator.logic.constants import MAX_TIMELAPSE_FRAMES

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    import numpy as np

    from pixelart_creator.logic.document import Document

__all__ = [
    "TimelapseError",
    "TIMELAPSE_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "TimelapseFrame",
    "TimelapseSession",
    "new_session",
    "record_frame",
    "replay",
]

#: Timelapse-session wire schema version — a module-local format-intrinsic string
#: (ADR-0001 / BF-2, the macro ``MACRO_SCHEMA_VERSION`` precedent), consumed by the
#: defensive ``data/timelapse_io.py`` (de)serialiser.
TIMELAPSE_SCHEMA_VERSION: str = "1"

#: Schema versions this build can load (ADR-0025 §2).
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (TIMELAPSE_SCHEMA_VERSION,)


class TimelapseError(ValueError):
    """Raised on an invalid timelapse session or frame (bounds / structure)."""


@dataclass(frozen=True)
class TimelapseFrame:
    """One recorded frame — a reference to a committed command, not pixels.

    Attributes:
        index: The 0-based ordinal of the frame within its session.
        command_id: The stable id of the committed history command (HIS-1) whose
            document state this frame captures.
    """

    index: int
    command_id: int

    def __post_init__(self) -> None:
        """Validate the ordinal and command id (non-negative ints)."""
        _require_nonneg_int(self.index, "index")
        _require_nonneg_int(self.command_id, "command_id")


@dataclass(frozen=True)
class TimelapseSession:
    """An immutable, ordered timelapse session (the command manifest).

    Attributes:
        schema_version: The format-intrinsic version string
            (``TIMELAPSE_SCHEMA_VERSION``).
        frames: Ordered ``TimelapseFrame`` records; ``<= MAX_TIMELAPSE_FRAMES``,
            contiguous ``index`` values ``0..n-1``.
    """

    schema_version: str = TIMELAPSE_SCHEMA_VERSION
    frames: Tuple[TimelapseFrame, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate the schema version, frame count and contiguous ordinals."""
        if not isinstance(self.schema_version, str):
            raise TimelapseError(
                f"schema_version must be a str, got {self.schema_version!r}"
            )
        frames = tuple(self.frames)
        object.__setattr__(self, "frames", frames)
        if len(frames) > MAX_TIMELAPSE_FRAMES:
            raise TimelapseError(
                f"{len(frames)} frames exceeds MAX_TIMELAPSE_FRAMES "
                f"({MAX_TIMELAPSE_FRAMES})"
            )
        for expected, frame in enumerate(frames):
            if not isinstance(frame, TimelapseFrame):
                raise TimelapseError(f"expected a TimelapseFrame, got {frame!r}")
            if frame.index != expected:
                raise TimelapseError(
                    f"frame index {frame.index} is not contiguous "
                    f"(expected {expected})"
                )


def new_session() -> TimelapseSession:
    """Return a fresh empty session at the current schema version."""
    return TimelapseSession(schema_version=TIMELAPSE_SCHEMA_VERSION, frames=())


def record_frame(session: TimelapseSession, command_id: int) -> TimelapseSession:
    """Append one frame for a committed command; return a **new** session.

    The per-committed-command cadence (ADR-0024 §2): the appended frame's ``index``
    is the next ordinal (``len(session.frames)``) and its ``command_id`` is the
    committed command's stable id. Pure — the input session is not mutated
    (REQ-P9-LOGIC-010/-011; SC-L010-1).

    Raises:
        TimelapseError: If appending would exceed ``MAX_TIMELAPSE_FRAMES`` or
            ``command_id`` is not a non-negative int.
    """
    _require_nonneg_int(command_id, "command_id")
    if len(session.frames) >= MAX_TIMELAPSE_FRAMES:
        raise TimelapseError(
            f"session already at MAX_TIMELAPSE_FRAMES ({MAX_TIMELAPSE_FRAMES})"
        )
    new_frame = TimelapseFrame(index=len(session.frames), command_id=command_id)
    return TimelapseSession(
        schema_version=session.schema_version,
        frames=session.frames + (new_frame,),
    )


def replay(
    session: "TimelapseSession",
    document: "Document",
    renderer: "Callable[[Document], np.ndarray]",
) -> "Tuple[np.ndarray, ...]":
    """Deterministically re-render each recorded frame of ``session``.

    Produces one rendered RGBA array per recorded ``TimelapseFrame``, **in order**,
    by invoking the caller-supplied pure ``renderer`` (a ``Document`` -> RGBA
    ``ndarray`` function, e.g. wrapping ``blend.composite_stack``, CO-4) on the
    document state each frame captures. The frame count and order derive from the
    recorded command manifest (HIS-1), **not** screen state; the same session
    replayed twice yields the **identical** frame sequence — no wall-clock, no RNG,
    no locale (REQ-P9-LOGIC-010/-009; SC-L010-1). Pure: ``replay`` never mutates
    ``session`` or ``document``.

    The state reconstruction across the shipped undo history is driven by the
    caller's ``renderer`` (the ``ui/`` timelapse controller steps the HIS-1 stack
    and renders the resulting document); this pure core fixes the deterministic
    cadence, ordering and count.

    Raises:
        TimelapseError: If ``renderer`` is not callable.
    """
    if not callable(renderer):
        raise TimelapseError(f"renderer must be callable, got {renderer!r}")
    return tuple(renderer(document) for _ in session.frames)


def _require_nonneg_int(value: Any, name: str) -> None:
    """Raise :class:`TimelapseError` unless ``value`` is a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TimelapseError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise TimelapseError(f"{name} must be >= 0, got {value}")
