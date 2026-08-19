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

**Stable frame identity (Q-21, REQ-P9-LOGIC-022; plan §10, added 2026-08-18).**
A frame's identity is the opaque string :data:`FrameId` carried by
``TimelapseFrame.frame_id`` — ``None`` only on a frame loaded from schema 1 or
2. It denotes one frame's own recorded edit, for as long as the session or any
file written from it exists, and is **never reused**, including by a later
edit that lands on the same undo-stack position as a discarded frame. **The
opacity rule: every consumer compares a ``frame_id`` ONLY by equality, and
never parses it to derive a frame's order, position, successor or age** — the
one stated exception is ``data/timelapse_io.py``'s own untrusted-input shape
validation on load, which derives nothing (plan §10.3). This module **mints
no identity** — it has no session, no counter and no entropy source, and
generating one here would make :func:`record_frame` non-deterministic
(REQ-P9-LOGIC-009). The identity is minted by ``ui/timelapse_controls.py``
(a recording-scoped monotonic ordinal beside a per-recording ``secrets``
draw, DEP-12g); this module only **validates** what it is given —
:func:`record_frame` refuses a missing identity on an identity-bearing
(schema-3) session and a duplicate identity within one session, and
:func:`resolve_frame` looks a frame up by identity with exactly two
outcomes, never a third. Removal (:func:`drop_discarded`) and reachability
(:func:`reconstructability`) are decided by identity, never by a position,
a count, or any boundary derived from one (REQ-P9-LOGIC-022(c)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, FrozenSet, Optional, Tuple

from pixelart_creator.logic.constants import (
    MAX_TIMELAPSE_FRAMES,
    TIMELAPSE_FRAME_ID_MAX_LEN,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    import numpy as np

    from pixelart_creator.logic.document import Document

__all__ = [
    "TimelapseError",
    "TimelapseFrameUnresolved",
    "TIMELAPSE_SCHEMA_VERSION",
    "TIMELAPSE_PAYLOAD_SCHEMA_VERSION",
    "TIMELAPSE_IDENTITY_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "FrameId",
    "TimelapseFrame",
    "TimelapseSession",
    "DocumentProvider",
    "ReconstructionSubstrate",
    "ReconstructionBlocker",
    "ReconstructionExtent",
    "Reconstructability",
    "new_session",
    "record_frame",
    "resolve_frame",
    "reconstructability",
    "drop_discarded",
    "replay",
]

#: A frame's stable identity (Q-21, REQ-P9-LOGIC-022; plan §10.1) — an opaque
#: string, compared **only** by equality, never parsed to derive order,
#: position, successor or age. Minted in ``ui/`` (this module has no session,
#: no counter, no entropy) as ``f"{recording_id}:{ordinal}"``, a
#: recording-scoped monotonic ordinal beside a per-recording ``secrets`` draw.
FrameId = str

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
#:
#: **Read-only legacy as of the Q-21 amendment (2026-08-18).** Its *value* is
#: unchanged, but its *role* is: ``data/timelapse_io.py``'s ``serialize_payload``
#: refuses to emit it again, because a build that could still write it could
#: still create the identity-less population ``REQ-P9-DATA-005`` exists to stop
#: creating. A schema-2 file already on disk still **loads** as a readable
#: record (``REQ-P9-DATA-003``); it never **plays** (``NO_IDENTITY``,
#: ``REQ-P9-UI-019``(f)), and it is never migrated, upgraded or re-tagged.
TIMELAPSE_PAYLOAD_SCHEMA_VERSION: str = "2"

#: The Q-21 identity-bearing wire schema version (REQ-P9-LOGIC-022,
#: REQ-P9-DATA-005; DEP-12e; plan §10.3), added **beside**
#: :data:`TIMELAPSE_SCHEMA_VERSION` and :data:`TIMELAPSE_PAYLOAD_SCHEMA_VERSION`
#: rather than reshaping either. A session at this version carries a root
#: ``recording_id`` and every frame's stable ``TimelapseFrame.frame_id``.
#: ``"3"`` rather than a reshaped ``"2"``: schema 2 has never been released,
#: but two different frame shapes sharing one version string is exactly the
#: misparse the version rules exist to prevent, and reusing the number would
#: be the reinterpretation §0b.1 rules out by name. This is the **only**
#: version :func:`~pixelart_creator.data.timelapse_io.serialize_payload`
#: writes going forward.
TIMELAPSE_IDENTITY_SCHEMA_VERSION: str = "3"

#: Schema versions this build can load (ADR-0025 §2). Widened for D-12/Q-21 to
#: accept the command-manifest-only form, the (now read-only) payload-bearing
#: form, and the identity-bearing form. Discrimination between them is by this
#: string **alone** (plan §10.3) — never by sniffing for an ``"identity"`` key,
#: which would let a truncated or hand-edited file select whichever branch is
#: more permissive.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (
    TIMELAPSE_SCHEMA_VERSION,
    TIMELAPSE_PAYLOAD_SCHEMA_VERSION,
    TIMELAPSE_IDENTITY_SCHEMA_VERSION,
)


class TimelapseError(ValueError):
    """Raised on an invalid timelapse session or frame (bounds / structure)."""


class TimelapseFrameUnresolved(TimelapseError):
    """A frame reference names a frame this session does not hold.

    Raised by :func:`resolve_frame` — the second of its two outcomes
    (REQ-P9-LOGIC-022(d)): resolution either succeeds with that frame's own
    recorded content, or fails naming the frame that could not be resolved.
    It never returns a *different* frame's content.
    """


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
        frame_id: This frame's stable identity (:data:`FrameId`;
            REQ-P9-LOGIC-022) — ``None`` **only** on a frame loaded from
            schema 1 or 2, which carry no identity. Compared **only** by
            equality (the opacity rule, plan §10.3): never parsed, never used
            to derive order, position, successor or age. **Additive,
            defaulted** — the shipped two- and three-argument constructions
            still work.
    """

    index: int
    command_id: int
    snapshot_id: Optional[str] = None
    frame_id: Optional["FrameId"] = None

    def __post_init__(self) -> None:
        """Validate the ordinal, command id, snapshot id and frame id shape."""
        _require_nonneg_int(self.index, "index")
        _require_nonneg_int(self.command_id, "command_id")
        if self.snapshot_id is not None and not isinstance(self.snapshot_id, str):
            raise TimelapseError(
                f"snapshot_id must be a str or None, got {self.snapshot_id!r}"
            )
        if self.frame_id is not None:
            if not isinstance(self.frame_id, str) or not self.frame_id:
                raise TimelapseError(
                    f"frame_id must be a non-empty str or None, got {self.frame_id!r}"
                )
            if len(self.frame_id) > TIMELAPSE_FRAME_ID_MAX_LEN:
                raise TimelapseError(
                    f"frame_id length {len(self.frame_id)} exceeds "
                    f"TIMELAPSE_FRAME_ID_MAX_LEN ({TIMELAPSE_FRAME_ID_MAX_LEN})"
                )


@dataclass(frozen=True)
class TimelapseSession:
    """An immutable, ordered timelapse session (the command manifest).

    Attributes:
        schema_version: The format-intrinsic version string
            (``TIMELAPSE_SCHEMA_VERSION``).
        frames: Ordered ``TimelapseFrame`` records; ``<= MAX_TIMELAPSE_FRAMES``,
            contiguous ``index`` values ``0..n-1``.
        recording_id: The per-recording identity half minted once by
            ``ui/timelapse_controls.py`` (REQ-P9-LOGIC-022; plan §10.1) —
            ``None`` unless this session is identity-bearing (schema 3).
    """

    schema_version: str = TIMELAPSE_SCHEMA_VERSION
    frames: Tuple[TimelapseFrame, ...] = field(default_factory=tuple)
    recording_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate the schema version, frame count, ordinals and frame ids."""
        if not isinstance(self.schema_version, str):
            raise TimelapseError(
                f"schema_version must be a str, got {self.schema_version!r}"
            )
        if self.recording_id is not None and not isinstance(self.recording_id, str):
            raise TimelapseError(
                f"recording_id must be a str or None, got {self.recording_id!r}"
            )
        frames = tuple(self.frames)
        object.__setattr__(self, "frames", frames)
        if len(frames) > MAX_TIMELAPSE_FRAMES:
            raise TimelapseError(
                f"{len(frames)} frames exceeds MAX_TIMELAPSE_FRAMES "
                f"({MAX_TIMELAPSE_FRAMES})"
            )
        seen_frame_ids: set = set()
        for expected, frame in enumerate(frames):
            if not isinstance(frame, TimelapseFrame):
                raise TimelapseError(f"expected a TimelapseFrame, got {frame!r}")
            if frame.index != expected:
                raise TimelapseError(
                    f"frame index {frame.index} is not contiguous "
                    f"(expected {expected})"
                )
            if frame.frame_id is not None:
                # (b) never reused: no two frames in one session may share an
                # identity (REQ-P9-LOGIC-022(b)) — a construction-time error,
                # never a silent duplicate.
                if frame.frame_id in seen_frame_ids:
                    raise TimelapseError(
                        f"duplicate frame_id {frame.frame_id!r} at index "
                        f"{frame.index}"
                    )
                seen_frame_ids.add(frame.frame_id)


def new_session(recording_id: Optional[str] = None) -> TimelapseSession:
    """Return a fresh empty session, at the version ``recording_id`` selects.

    ``recording_id is None`` (the default) returns a schema-1 session — the
    unchanged shipped shape (REQ-P9-DATA-003). A non-``None`` ``recording_id``
    (the per-recording identity half minted by ``ui/timelapse_controls.py``,
    plan §10.1) returns an **identity-bearing** schema-3 session, on which
    :func:`record_frame` REQUIRES a ``frame_id``.

    Raises:
        TimelapseError: If ``recording_id`` is neither ``None`` nor a
            non-empty ``str``.
    """
    if recording_id is None:
        return TimelapseSession(schema_version=TIMELAPSE_SCHEMA_VERSION, frames=())
    if not isinstance(recording_id, str) or not recording_id:
        raise TimelapseError(
            f"recording_id must be a non-empty str or None, got {recording_id!r}"
        )
    return TimelapseSession(
        schema_version=TIMELAPSE_IDENTITY_SCHEMA_VERSION,
        frames=(),
        recording_id=recording_id,
    )


def record_frame(
    session: TimelapseSession,
    command_id: int,
    frame_id: Optional["FrameId"] = None,
) -> TimelapseSession:
    """Append one frame for a committed command; return a **new** session.

    The per-committed-command cadence (ADR-0024 §2): the appended frame's ``index``
    is the next ordinal (``len(session.frames)``) and its ``command_id`` is the
    committed command's stable id. Pure — the input session is not mutated
    (REQ-P9-LOGIC-010/-011; SC-L010-1).

    ``frame_id`` (REQ-P9-LOGIC-022; plan §10.1) is **validated, never
    generated**: this function has no session, no counter and no entropy
    source of its own. On an identity-bearing (schema-3) ``session``, a
    ``frame_id`` is **required** — an identity-less live payload recording is
    not a representable state. Shape (non-empty ``str``, bounded length) and
    non-reuse (no two frames in one session may share an identity) are
    enforced by :class:`TimelapseFrame` and :class:`TimelapseSession`
    construction below, so a duplicate or malformed ``frame_id`` raises the
    same way a malformed ``command_id`` does.

    Raises:
        TimelapseError: If appending would exceed ``MAX_TIMELAPSE_FRAMES``,
            ``command_id`` is not a non-negative int, ``session`` is
            identity-bearing and ``frame_id`` is ``None``, or ``frame_id`` is
            malformed or already present in ``session``.
    """
    _require_nonneg_int(command_id, "command_id")
    if len(session.frames) >= MAX_TIMELAPSE_FRAMES:
        raise TimelapseError(
            f"session already at MAX_TIMELAPSE_FRAMES ({MAX_TIMELAPSE_FRAMES})"
        )
    if session.schema_version == TIMELAPSE_IDENTITY_SCHEMA_VERSION and frame_id is None:
        raise TimelapseError(
            "frame_id is required to record a frame in an identity-bearing "
            f"(schema-{TIMELAPSE_IDENTITY_SCHEMA_VERSION}) session "
            "(REQ-P9-LOGIC-022) — this function validates identities, it "
            "never mints one"
        )
    new_frame = TimelapseFrame(
        index=len(session.frames), command_id=command_id, frame_id=frame_id
    )
    return TimelapseSession(
        schema_version=session.schema_version,
        frames=session.frames + (new_frame,),
        recording_id=session.recording_id,
    )


def resolve_frame(session: TimelapseSession, frame_id: "FrameId") -> TimelapseFrame:
    """Return the frame carrying exactly ``frame_id``, or raise naming it.

    Two outcomes and no third (REQ-P9-LOGIC-022(d)): an equality scan over
    ``session.frames`` — no index arithmetic, no fallback branch, no
    "plausible" frame returned when the exact one is absent. Resolution is by
    identity alone (REQ-P9-LOGIC-022(c)): this function never compares
    ``frame_id`` against a position, a count, or any boundary derived from
    one.

    Raises:
        TimelapseFrameUnresolved: If no frame in ``session`` carries
            ``frame_id``.
        TimelapseError: If ``frame_id`` is not a ``str``.
    """
    if not isinstance(frame_id, str):
        raise TimelapseError(f"frame_id must be a str, got {frame_id!r}")
    for frame in session.frames:
        if frame.frame_id == frame_id:
            return frame
    raise TimelapseFrameUnresolved(
        f"no frame with frame_id={frame_id!r} in this session"
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
    #: The frame carries no stable identity (``frame_id is None``) — a schema-2
    #: frame, or a schema-1 frame reached via the SNAPSHOT substrate check
    #: (REQ-P9-UI-019(f); REQ-P9-LOGIC-022; Q-21). Evaluated **after**
    #: ``NO_PAYLOAD`` on the SNAPSHOT substrate (``SC-D005-3``'s precedence): a
    #: schema-1 frame has neither a snapshot nor an identity and must refuse
    #: for the schema-1 reason, not this one.
    NO_IDENTITY = "no-identity"


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
        reachable_frame_ids: The set of :data:`FrameId` values a live history
            can currently place the document at. **``HISTORY`` only.**
            **Superseded 2026-08-18 (Q-21)**: replaces
            ``reachable_command_ids: FrozenSet[int]`` — ``command_id`` is a
            *position*, which ``REQ-P9-LOGIC-022``(c) forbids as a
            reachability test (plan §10 addendum).
        reachable_snapshot_ids: The set of ``snapshot_id`` values a loaded
            payload's snapshot table resolves. **``SNAPSHOT`` only.**
        matches_session: Whether this substrate is in fact the one this
            session was recorded against. ``False`` names the case where a
            snapshot payload was loaded for a different session, or a live
            history has since been reset/replaced (REQ-P9-LOGIC-015).

    Raises:
        TimelapseError: On construction, if ``substrate`` is not a
            :class:`ReconstructionSubstrate`, or if the extent is mis-built —
            a ``SNAPSHOT`` extent carrying ``reachable_frame_ids``, or a
            ``HISTORY`` extent carrying ``reachable_snapshot_ids``. A wrong
            extent must be a construction-time error, never a confident wrong
            verdict.
    """

    substrate: "ReconstructionSubstrate"
    reachable_frame_ids: FrozenSet["FrameId"] = frozenset()
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
        _require_frozenset_of(self.reachable_frame_ids, str, "reachable_frame_ids")
        _require_frozenset_of(
            self.reachable_snapshot_ids, str, "reachable_snapshot_ids"
        )
        if (
            self.substrate is ReconstructionSubstrate.SNAPSHOT
            and self.reachable_frame_ids
        ):
            raise TimelapseError(
                "a SNAPSHOT extent must not carry reachable_frame_ids "
                f"(got {self.reachable_frame_ids!r})"
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
    either substrate is addressed by, and never a count, an extent size or
    any boundary derived from one (REQ-P9-LOGIC-022(c), Q-21). Pure: never
    mutates ``session`` or ``extent``.

    **HISTORY** reachability is now identity-keyed (Q-21, plan §10.2): a
    frame with no identity (``frame_id is None``) blocks with
    :attr:`ReconstructionBlocker.NO_IDENTITY`; a frame with an identity absent
    from ``extent.reachable_frame_ids`` blocks with
    :attr:`ReconstructionBlocker.BEYOND_EXTENT` — a set-membership test, never
    a comparison against the live stack's count or extent.
    **SNAPSHOT** gains the same identity check, ordered **after**
    :attr:`ReconstructionBlocker.NO_PAYLOAD` (``SC-D005-3``'s precedence): a
    schema-1 frame has neither a snapshot nor an identity and must refuse for
    the schema-1 reason; a schema-2 frame has a snapshot but no identity and
    must refuse for :attr:`ReconstructionBlocker.NO_IDENTITY`.

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
            if frame.frame_id is None:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.NO_IDENTITY,
                    detail=f"frame {frame.index} carries no identity",
                )
            if frame.frame_id not in extent.reachable_frame_ids:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.BEYOND_EXTENT,
                    detail=(
                        f"frame {frame.index} (frame_id={frame.frame_id!r}) is "
                        "beyond the substrate's reachable frame ids"
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
            if frame.frame_id is None:
                return Reconstructability(
                    ok=False,
                    first_unreachable_index=frame.index,
                    blocker=ReconstructionBlocker.NO_IDENTITY,
                    detail=f"frame {frame.index} carries no identity",
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


def drop_discarded(
    session: "TimelapseSession", surviving_ids: "FrozenSet[FrameId]"
) -> "TimelapseSession":
    """Drop every frame whose identity is not in ``surviving_ids``.

    **Re-keyed onto identity 2026-08-18 (Q-21, REQ-P9-LOGIC-017 as restated;
    plan §10.2) — supersedes the earlier ``at_position: int`` signature.** A
    position cannot decide removal by itself: the undo stack reuses its
    coordinate space by design, so a positional boundary can retain a frame
    whose own recorded edit was discarded and a later, unrelated edit now
    occupies its old position. Removal is a **set operation on identities**:
    exactly the frames whose ``frame_id`` is a member of ``surviving_ids``
    survive; every survivor's ``frame_id`` and ``command_id`` are
    **preserved unchanged**; what remains is re-indexed to stay contiguous
    ``0 .. n-1`` (the invariant :meth:`TimelapseSession.__post_init__`
    already enforces). No frame that can no longer be reconstructed is
    retained, played, seeked to, or counted (REQ-P9-LOGIC-017). Pure:
    ``session`` is never mutated.

    Args:
        session: The session to prune.
        surviving_ids: The identities still live — typically
            ``frozenset(id_at_index.values())`` from the recording session's
            own index -> identity map at the moment of the discard (plan
            §10.2).

    Raises:
        TimelapseError: If ``surviving_ids`` is not a ``frozenset`` of ``str``.
    """
    _require_frozenset_of(surviving_ids, str, "surviving_ids")
    kept = tuple(f for f in session.frames if f.frame_id in surviving_ids)
    reindexed = tuple(
        TimelapseFrame(
            index=new_index,
            command_id=frame.command_id,
            snapshot_id=frame.snapshot_id,
            frame_id=frame.frame_id,
        )
        for new_index, frame in enumerate(kept)
    )
    return TimelapseSession(
        schema_version=session.schema_version,
        frames=reindexed,
        recording_id=session.recording_id,
    )


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
