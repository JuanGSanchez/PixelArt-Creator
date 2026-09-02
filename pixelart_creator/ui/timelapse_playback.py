# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The two ``DocumentProvider`` implementations for historical replay (D-12).

Qt only (S11) — binds :mod:`pixelart_creator.logic.timelapse`'s substrate-blind
``DocumentProvider`` port (plan §2, corrected by plan §8.3) to the product's two
reconstruction substrates (plan §4.3):

- :class:`History_Document_Provider` steps the **live**, in-session
  ``QUndoStack`` — the ``setIndex`` stepper lives here rather than in
  ``logic/`` (Article I: ``logic/`` imports zero Qt), and it is documented as
  O(distance) sequential replay (repeated ``undo()``/``redo()``), not a seek —
  stepping to a position replays every command in between, so its cost grows
  with distance rather than being constant.
- :class:`Snapshot_Document_Provider` serves a loaded, persisted schema-2
  payload and **borrows nothing**.

Each is a ``DocumentProvider`` in the plan §8.3 sense: it receives the whole
frozen :class:`~pixelart_creator.logic.timelapse.TimelapseFrame` and reads the
key its own substrate is addressed by (``command_id`` or ``snapshot_id``),
never the frame's ordinal — ``frame.index`` is not a reachability key for
either substrate (plan §8.2). Each also builds its own
:class:`~pixelart_creator.logic.timelapse.ReconstructionExtent` in that
section's shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, FrozenSet, Optional, Tuple

from PySide6.QtGui import QUndoStack

from pixelart_creator.data.snapshot_store import document_of
from pixelart_creator.data.timelapse_io import TimelapsePayload
from pixelart_creator.logic.timelapse import (
    FrameId,
    ReconstructionExtent,
    ReconstructionSubstrate,
    TimelapseError,
    TimelapseFrame,
    TimelapseSession,
)
from pixelart_creator.logic.timelapse import replay as _replay

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    import numpy as np

    from pixelart_creator.logic.document import Document

__all__ = ["DocumentGetter", "History_Document_Provider", "Snapshot_Document_Provider"]

#: Returns the *live* document currently bound to a ``QUndoStack``. Every
#: mutating command in this product's undo bridge
#: (:mod:`pixelart_creator.ui.commands`) applies and reverts **in place**, so
#: re-reading this accessor after ``QUndoStack.setIndex`` reflects that
#: history position's own recorded state without this module re-deriving it.
DocumentGetter = Callable[[], "Document"]


class History_Document_Provider:
    """Serves a :class:`Document` from a live, in-session ``QUndoStack``.

    The in-session substrate of the D-12 port (plan §2/§8.2/§8.3):
    ``command_id`` is the ``QUndoStack`` index *after* a forward move
    (``ui/timelapse_controls.py``), so placing the document at a recorded
    frame is ``stack.setIndex(frame.command_id)`` — Qt's own O(distance)
    sequential replay, never a seek.

    This provider **borrows** the live stack and document to read each
    recorded frame's state. It is a context manager so the borrow is always
    returned: the history position, document content (which follows the
    stack's own in-place undo/redo) and undo/redo availability are all
    restored together, in a ``finally``, whichever way the surrounding
    replay ends — completed, paused, stopped, or failed
    (REQ-P9-LOGIC-016). :meth:`replay_all` is the one call sites need so the
    borrow/restore contract cannot be forgotten.

    **Re-keyed onto identity 2026-08-18 (Q-21, REQ-P9-LOGIC-022; plan
    §10.2).** ``extent()`` no longer derives reachability from
    ``frozenset(range(1, stack.count() + 1))`` — a count-derived boundary is
    exactly what ``REQ-P9-LOGIC-022``(c) forbids as a reachability test, and
    it cannot detect a frame whose position is still in range but whose own
    recorded edit was discarded (``SC-L022-5``, R5). The reachable set is
    supplied by the caller (``ui/timelapse_controls.py``'s own
    ``Dict[int, FrameId]`` from stack index to the identity minted when that
    index was last reached forward — the only thing that watched the
    identities being made) at construction time.
    """

    def __init__(
        self,
        stack: QUndoStack,
        document_getter: DocumentGetter,
        reachable_frame_ids: "FrozenSet[FrameId]" = frozenset(),
    ) -> None:
        """Bind the live ``stack``, its document getter and the live identity set.

        ``reachable_frame_ids`` is the recording session's own current
        ``frame_id`` extent (plan §10.2) — this provider does not compute it,
        it only carries it into a :class:`ReconstructionExtent`.
        """
        self._stack = stack
        self._document_getter = document_getter
        self._reachable_frame_ids = reachable_frame_ids
        self._borrowed_index: Optional[int] = None

    def extent(self) -> ReconstructionExtent:
        """Return the HISTORY extent this stack can currently reach.

        Identity-keyed (plan §10.2): the set of ``frame_id`` values the
        recording session's own index -> identity map currently holds live,
        supplied at construction — never a count or a range derived from
        ``stack.count()``.
        """
        return ReconstructionExtent(
            substrate=ReconstructionSubstrate.HISTORY,
            reachable_frame_ids=self._reachable_frame_ids,
        )

    def __call__(self, frame: TimelapseFrame) -> "Document":
        """Step the bound stack to ``frame.command_id`` and return its document.

        Reads the frame's own key, never its ordinal (plan §8.3).
        """
        self._stack.setIndex(frame.command_id)
        return self._document_getter()

    def __enter__(self) -> "History_Document_Provider":
        """Borrow the stack's current position, to be restored on exit."""
        self._borrowed_index = self._stack.index()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Restore the borrowed position/content/undo availability (REQ-P9-LOGIC-016).

        Runs whether the block completed, was left by ``break``/``return``
        (paused or stopped by the caller), or raised (failed) — never
        suppresses an exception (returns ``None``, not ``True``).
        """
        if self._borrowed_index is not None:
            self._stack.setIndex(self._borrowed_index)
            self._borrowed_index = None

    def replay_all(
        self,
        session: TimelapseSession,
        renderer: "Callable[[Document], np.ndarray]",
    ) -> "Tuple[np.ndarray, ...]":
        """Render every recorded frame, borrowing and restoring the stack.

        Equivalent to ``with self: replay(session, self, renderer)`` —
        offered so the borrow/restore contract is never left to a call
        site to remember (REQ-P9-LOGIC-016).
        """
        with self:
            return _replay(session, self, renderer)


class Snapshot_Document_Provider:
    """Serves a :class:`Document` from a loaded, persisted snapshot table.

    The cross-session substrate (plan §2/§8.2/§8.3): reconstructs from a
    schema-2 :class:`~pixelart_creator.data.timelapse_io.TimelapsePayload`
    already loaded by
    :func:`~pixelart_creator.data.timelapse_io.load_session_payload`.
    **Borrows nothing** — no live document or undo stack is touched, so there
    is no position to restore.
    """

    def __init__(self, payload: TimelapsePayload) -> None:
        """Bind the loaded ``payload`` this provider reconstructs frames from."""
        self._payload = payload

    def extent(self) -> ReconstructionExtent:
        """Return the SNAPSHOT extent this payload's table can resolve.

        For a schema-1 recording (no snapshot table at all) this is the
        empty set, so ``reconstructability`` reports ``NO_PAYLOAD`` at frame
        0 — REQ-P9-UI-019(a), reached as a value rather than by
        string-matching a sentence (plan §8.2).
        """
        return ReconstructionExtent(
            substrate=ReconstructionSubstrate.SNAPSHOT,
            reachable_snapshot_ids=frozenset(self._payload.snapshots),
        )

    def __call__(self, frame: TimelapseFrame) -> "Document":
        """Reconstruct the document at ``frame``'s own recorded snapshot.

        Reads ``frame.snapshot_id``, never its ordinal (plan §8.3).

        Raises:
            TimelapseError: If the frame carries no resolvable snapshot.
                Callers are expected to have already refused playback via
                ``reconstructability`` before reaching this call; this is
                the defensive last line, not the refusal path.
        """
        if (
            frame.snapshot_id is None
            or frame.snapshot_id not in self._payload.snapshots
        ):
            raise TimelapseError(
                f"frame {frame.index} has no resolvable snapshot in this payload"
            )
        return document_of(
            self._payload.snapshots[frame.snapshot_id], self._payload.blobs
        )
