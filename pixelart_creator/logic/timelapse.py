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

**Historical replay (D-12, spec §4.3).** Two substrates can place the document at
a recorded frame's own state: a live, in-session ``QUndoStack`` and a persisted,
cross-session snapshot table. They are unified behind one port,
:data:`DocumentProvider`, so this module stays Qt-free and substrate-blind
(``reconstructability`` decides which substrate a session gets; ``replay`` is the
**same function** for both — REQ-P9-LOGIC-019, "same contract, different
substrate"). The port's parameter is the **whole frozen** ``TimelapseFrame``,
never the ordinal (plan §8.3): a provider reads the key its own substrate is
addressed by (``command_id`` or ``snapshot_id``), since ``frame.index`` is not
a reachability key for either (plan §8.2). ``TimelapseFrame.snapshot_id``
(additive, defaulted) references a schema-2 snapshot when the frame's own
state is persisted rather than re-derived from a live history position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, FrozenSet, Optional, Tuple

from pixelart_creator.logic.constants import MAX_TIMELAPSE_FRAMES

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    import numpy as np

    from pixelart_creator.logic.document import Document

__all__ = [
    "TimelapseError",
    "TIMELAPSE_SCHEMA_VERSION",
    "TIMELAPSE_PAYLOAD_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "TimelapseFrame",
    "TimelapseSession",
    "DocumentProvider",
    "ReconstructionSubstrate",
    "ReconstructionBlocker",
    "ReconstructionExtent",
    "Reconstructability",
    "new_session",
    "record_frame",
    "reconstructability",
    "drop_discarded",
    "replay",
]

#: Timelapse-session wire schema version — a module-local format-intrinsic string
#: (ADR-0001 / BF-2, the macro ``MACRO_SCHEMA_VERSION`` precedent), consumed by the
#: defensive ``data/timelapse_io.py`` (de)serialiser. **Unchanged** by D-12 (plan
#: §5.1): the shipped 10 unmodified ``test_timelapse.py`` assertions and all 13
#: ``test_timelapse_io.py`` assertions pin this literal, never the moved value.
TIMELAPSE_SCHEMA_VERSION: str = "1"

#: The D-12 payload-bearing wire schema version, added **beside**
#: :data:`TIMELAPSE_SCHEMA_VERSION` rather than replacing it (plan §5.1) — a
#: session at this version carries ``TimelapseFrame.snapshot_id`` references into
#: a persisted, content-addressed snapshot table (``data/timelapse_io.py`` schema
#: 2; REQ-P9-DATA-004).
TIMELAPSE_PAYLOAD_SCHEMA_VERSION: str = "2"

#: Schema versions this build can load (ADR-0025 §2). Widened for D-12 to accept
#: both the command-manifest-only form and the payload-bearing form.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (
    TIMELAPSE_SCHEMA_VERSION,
    TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
)


class TimelapseError(ValueError):
    """Raised on an invalid timelapse session or frame (bounds / structure)."""


@dataclass(frozen=True)
class TimelapseFrame:
    """One recorded frame — a reference to a committed command, not pixels.

    Attributes:
        index: The 0-based ordinal of the frame within its session.
        command_id: The stable id of the committed history command (HIS-1) whose
            document state this frame captures.
        snapshot_id: The id of this frame's persisted snapshot in a schema-2
            ``data/timelapse_io.py`` snapshot table, or ``None`` when the frame
            is re-derived from a live history position only (**additive,
            defaulted** — D-12; the shipped two-argument construction still
            works, spec §5.1).
    """

    index: int
    command_id: int
    snapshot_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate the ordinal, command id and optional snapshot id."""
        _require_nonneg_int(self.index, "index")
        _require_nonneg_int(self.command_id, "command_id")
        if self.snapshot_id is not None and not isinstance(self.snapshot_id, str):
            raise TimelapseError(
                f"snapshot_id must be a str or None, got {self.snapshot_id!r}"
            )


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


#: A substrate-blind port: given the whole recorded :class:`TimelapseFrame`,
#: return the :class:`Document` at that frame's own recorded state (D-12, plan
#: §2, corrected by plan §8.3, 2026-08-17 addendum). The **frame**, not the
#: ordinal: neither provider can act on ``frame.index`` alone (plan §8.2 B-1)
#: — the history stepper needs ``frame.command_id``, the snapshot adapter
#: needs ``frame.snapshot_id`` — and passing the frozen frame removes the
#: desync class in which a provider closes over its own copy of the session
#: and re-derives its key by index lookup, disagreeing with ``replay``'s own
#: session. Two implementations exist, both in ``ui/timelapse_playback.py``
#: (Qt/QUndoStack knowledge stays out of ``logic/`` — Article I):
#: ``History_Document_Provider`` steps a live ``QUndoStack``;
#: ``Snapshot_Document_Provider`` reconstructs from a loaded schema-2 payload.
#: Raising from a call is how a provider reports "cannot place the document at
#: this frame" (REQ-P9-LOGIC-013/-015).
DocumentProvider = Callable[["TimelapseFrame"], "Document"]


class ReconstructionSubstrate(Enum):
    """Which substrate a :class:`ReconstructionExtent` describes (plan §8.2).

    ``Enum`` is the shipped ``logic/`` idiom (13 modules deep already).
    """

    HISTORY = "history"
    SNAPSHOT = "snapshot"


class ReconstructionBlocker(Enum):
    """The **code** naming why a frame is unreachable (plan §8.2, Ruling B).

    Never an English sentence: a prose reason born in ``logic/`` can be
    neither translated (``tr()`` wrapping is a ``ui/`` obligation, Article V)
    nor audited (``string_audit_check`` scans for unwrapped *literals*, and
    ``str(verdict.reason)`` is not one). Each code maps to exactly one
    ``tr()``-wrapped sentence in the surface (``ui/``, T10/T16).
    """

    NO_PAYLOAD = "no-payload"  # REQ-P9-UI-019(a) -- schema-1, no snapshot table
    PAYLOAD_INCOMPLETE = "payload-incomplete"  # REQ-P9-UI-019(e)
    BEYOND_EXTENT = "beyond-extent"  # REQ-P9-UI-019(d)
    SUBSTRATE_MISMATCH = "substrate-mismatch"  # history not the one recorded against


@dataclass(frozen=True)
class ReconstructionExtent:
    """What a given substrate can actually reconstruct, in ITS OWN key space.

    Ruled shape (plan §8.2, Ruling B): ``frame.index`` is not a key either
    substrate is addressed by. ``command_id`` diverges from ``index`` by
    construction once ``ui/timelapse_controls.py`` records it only while
    recording is on, and once :func:`drop_discarded` re-indexes survivors
    while keeping their ``command_id``; and snapshot ids are content hashes
    with no ordinal at all. A single ``reachable_count`` therefore has no
    honest value on either substrate — this extent speaks the substrate's
    own key space instead.

    Attributes:
        substrate: Which of the two substrates this extent describes.
        reachable_command_ids: The set of ``command_id`` values a live
            history can currently place the document at. **``HISTORY``
            only.**
        reachable_snapshot_ids: The set of ``snapshot_id`` values a loaded
            payload's snapshot table resolves. **``SNAPSHOT`` only.**
        matches_session: Whether this substrate is in fact the one this
            session was recorded against. ``False`` names the case where a
            snapshot payload was loaded for a different session, or a live
            history has since been reset/replaced (REQ-P9-LOGIC-015).

    Raises:
        TimelapseError: On construction, if ``substrate`` is not a
            :class:`ReconstructionSubstrate`, or if the extent is mis-built —
            a ``SNAPSHOT`` extent carrying ``reachable_command_ids``, or a
            ``HISTORY`` extent carrying ``reachable_snapshot_ids``. A wrong
            extent must be a construction-time error, never a confident wrong
            verdict.
    """

    substrate: "ReconstructionSubstrate"
    reachable_command_ids: FrozenSet[int] = frozenset()
    reachable_snapshot_ids: FrozenSet[str] = frozenset()
    matches_session: bool = True

    def __post_init__(self) -> None:
        """Refuse a mis-built extent — wrong type or the wrong substrate's keys."""
        if not isinstance(self.substrate, ReconstructionSubstrate):
            raise TimelapseError(
                f"substrate must be a ReconstructionSubstrate, got {self.substrate!r}"
            )
        if not isinstance(self.matches_session, bool):
            raise TimelapseError(
                f"matches_session must be a bool, got {self.matches_session!r}"
            )
        _require_frozenset_of(self.reachable_command_ids, int, "reachable_command_ids")
        _require_frozenset_of(
            self.reachable_snapshot_ids, str, "reachable_snapshot_ids"
        )
        if (
            self.substrate is ReconstructionSubstrate.SNAPSHOT
            and self.reachable_command_ids
        ):
            raise TimelapseError(
                "a SNAPSHOT extent must not carry reachable_command_ids "
                f"(got {self.reachable_command_ids!r})"
            )
        if (
            self.substrate is ReconstructionSubstrate.HISTORY
            and self.reachable_snapshot_ids
        ):
            raise TimelapseError(
                "a HISTORY extent must not carry reachable_snapshot_ids "
                f"(got {self.reachable_snapshot_ids!r})"
            )


@dataclass(frozen=True)
class Reconstructability:
    """The verdict :func:`reconstructability` returns.

    ``blocker`` is a **code** (:class:`ReconstructionBlocker`), never a
    string (plan §8.2, Ruling B): the words the user reads are owned by
    ``ui/``, one ``tr()``-wrapped sentence per code. ``detail`` is
    developer-facing only — for exception messages and logs, **never**
    rendered into the surface, including tooltips.

    Attributes:
        ok: ``True`` iff every recorded frame position is reachable.
        first_unreachable_index: The 0-based index of the first frame that is
            not reachable, or ``None`` when ``ok`` is ``True``.
        blocker: The code naming *why* the first unreachable frame is not
            reachable, or ``None`` when ``ok`` is ``True``.
        detail: Developer-facing detail (never displayed), or ``None``.
    """

    ok: bool
    first_unreachable_index: Optional[int] = None
    blocker: Optional["ReconstructionBlocker"] = None
    detail: Optional[str] = None


def reconstructability(
    session: "TimelapseSession", extent: "ReconstructionExtent"
) -> "Reconstructability":
    """Report whether every recorded position of ``session`` is reachable.

    This is the function that decides which substrate a session gets
    (REQ-P9-LOGIC-015): it precedes every playback path. Evaluated over
    ``session.frames`` **in recorded order** so the **first** offending frame
    is the one named. Reachability is checked in the substrate's **own key
    space** (plan §8.2, Ruling B) — never ``frame.index``, which is not a key
    either substrate is addressed by. Pure: never mutates ``session`` or
    ``extent``.

    What this function deliberately does **not** decide, so no caller assumes
    coverage: ``REQ-P9-UI-019``(b), a session recorded against a different
    document — ``logic/`` has no document identity, and
    :attr:`ReconstructionBlocker.SUBSTRATE_MISMATCH` covers only the
    *substrate is not the one recorded against* half, reported via
    ``extent.matches_session``; and (c), an empty session, for which this
    returns ``ok=True`` **correctly** (an empty session is trivially
    reconstructible). Both are ``ui/`` checks (T10).

    Raises:
        TimelapseError: If ``extent`` is not a :class:`ReconstructionExtent`.
    """
    if not isinstance(extent, ReconstructionExtent):
        raise TimelapseError(f"extent must be a ReconstructionExtent, got {extent!r}")
    if not session.frames:
        return Reconstructability(ok=True)
    if not extent.matches_session:
        return Reconstructability(
            ok=False,
            first_unreachable_index=session.frames[0].index,
            blocker=ReconstructionBlocker.SUBSTRATE_MISMATCH,
            detail=(
                "the substrate's history is not the one this session was "
                "recorded against"
            ),
        )
    for frame in session.frames:
        if extent.substrate is ReconstructionSubstrate.HISTORY:
            if frame.command_id not in extent.reachable_command_ids:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.BEYOND_EXTENT,
                    detail=(
                        f"frame {frame.index} (command_id={frame.command_id}) is "
                        "beyond the substrate's reachable command ids"
                    ),
                )
        else:  # ReconstructionSubstrate.SNAPSHOT
            if frame.snapshot_id is None:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.NO_PAYLOAD,
                    detail=f"frame {frame.index} carries no snapshot_id",
                )
            if frame.snapshot_id not in extent.reachable_snapshot_ids:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.PAYLOAD_INCOMPLETE,
                    detail=(
                        f"frame {frame.index} references snapshot "
                        f"{frame.snapshot_id!r}, unresolved in the payload"
                    ),
                )
    return Reconstructability(ok=True)


def drop_discarded(session: "TimelapseSession", at_position: int) -> "TimelapseSession":
    """Drop frames whose recorded command has been discarded from the history.

    A ``QUndoStack`` discards every command past the current index when a new
    command is pushed after an undo (HIS-1); a frame referencing a
    ``command_id`` beyond the live boundary ``at_position`` can no longer be
    reconstructed and is removed. What remains is re-indexed to stay contiguous
    ``0 .. n-1`` (the invariant :meth:`TimelapseSession.__post_init__` already
    enforces) and is fully reconstructible: no frame that can no longer be
    reconstructed is retained, played, seeked to, or counted
    (REQ-P9-LOGIC-017). Pure: ``session`` is never mutated.

    Args:
        session: The session to prune.
        at_position: The highest ``command_id`` still live in the history; a
            frame with a strictly greater ``command_id`` is discarded.

    Raises:
        TimelapseError: If ``at_position`` is not a non-negative int.
    """
    _require_nonneg_int(at_position, "at_position")
    kept = tuple(f for f in session.frames if f.command_id <= at_position)
    reindexed = tuple(
        TimelapseFrame(
            index=new_index,
            command_id=frame.command_id,
            snapshot_id=frame.snapshot_id,
        )
        for new_index, frame in enumerate(kept)
    )
    return TimelapseSession(schema_version=session.schema_version, frames=reindexed)


def replay(
    session: "TimelapseSession",
    provider: "DocumentProvider",
    renderer: "Callable[[Document], np.ndarray]",
) -> "Tuple[np.ndarray, ...]":
    """Deterministically re-render each recorded frame of ``session`` historically.

    Produces one rendered RGBA array per recorded ``TimelapseFrame``, **in
    order**, **each at that frame's own recorded state** (REQ-P9-LOGIC-013):
    ``provider(frame)`` — the **whole frozen frame**, never
    ``provider(frame.index)`` (plan §8.3) — places the :class:`Document` at
    that frame's recorded state (via either substrate — REQ-P9-LOGIC-019,
    "same contract, different substrate"), and the caller-supplied pure
    ``renderer`` (a
    ``Document`` -> RGBA ``ndarray`` function, e.g. wrapping
    ``blend.composite_stack``, CO-4) renders it. The frame count and order
    derive from the recorded command manifest (HIS-1), **not** screen state; the
    same session replayed twice yields the **identical** frame sequence — no
    wall-clock, no RNG, no locale, no unordered iteration (REQ-P9-LOGIC-009).
    Pure: ``replay`` never mutates ``session`` or any document ``provider``
    returns.

    It is **specifically forbidden**, and this implementation never does it, to
    fall back to rendering one already-available document N times when a frame
    cannot be placed — that output is indistinguishable from success while
    being false (REQ-P9-LOGIC-014). When ``provider`` cannot place the document
    at a recorded frame, this function **raises and returns nothing**: no
    partial frame sequence is ever produced.

    Raises:
        TimelapseError: If ``provider`` or ``renderer`` is not callable, or if
            ``provider`` cannot place the document at a recorded frame (the
            underlying exception is chained).
    """
    if not callable(provider):
        raise TimelapseError(f"provider must be callable, got {provider!r}")
    if not callable(renderer):
        raise TimelapseError(f"renderer must be callable, got {renderer!r}")
    frames_out = []
    for frame in session.frames:
        try:
            document = provider(frame)
        except Exception as exc:  # noqa: BLE001 - re-raised as TimelapseError
            raise TimelapseError(
                f"cannot place the document at frame {frame.index}: {exc}"
            ) from exc
        frames_out.append(renderer(document))
    return tuple(frames_out)


def _require_nonneg_int(value: Any, name: str) -> None:
    """Raise :class:`TimelapseError` unless ``value`` is a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TimelapseError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise TimelapseError(f"{name} must be >= 0, got {value}")


def _require_frozenset_of(value: Any, item_type: type, name: str) -> None:
    """Raise :class:`TimelapseError` unless ``value`` is a typed ``frozenset``.

    Args:
        value: The candidate to validate.
        item_type: The required element type (``int`` or ``str``).
        name: The field name to name in a raised error.
    """
    if not isinstance(value, frozenset):
        raise TimelapseError(f"{name} must be a frozenset, got {value!r}")
    for item in value:
        if item_type is int:
            if isinstance(item, bool) or not isinstance(item, int):
                raise TimelapseError(f"{name} must contain only int, got {item!r}")
        elif not isinstance(item, item_type):
            raise TimelapseError(
                f"{name} must contain only {item_type.__name__}, got {item!r}"
            )
