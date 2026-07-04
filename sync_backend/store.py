"""Backend-side persistence of the per-document CRDT update log (Phase-10 Slice C).

ADR-0027 §4; spec REQ-P10-BACKEND-001. The relay persists the **ordered** CRDT-update
frame log per ``document_id`` so a late-joining client receives the backlog and
converges to the same document (client-side hybrid model, REQ-P10-LOGIC-006/-007). This
is the in-memory store used by CI (the ephemeral in-process backend); a running
deployment would back it with a file/database behind this same interface — the server
depends only on these methods.

Presence/awareness is **ephemeral** and is deliberately **not** stored here (ADR-0028
§4). The log is bounded (:data:`_MAX_BACKLOG_UPDATES`) so a broken/malicious client
cannot exhaust backend memory by streaming unbounded updates (Article VII,
REQ-P10-BACKEND-002). Imports **no** ``ui``/``data``/Qt (ADR-0027 §5); it is a pure,
stdlib-only store.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

__all__ = ["StoreError", "UpdateStore"]

#: Defensive ceiling on the number of retained update frames per document — guards
#: against unbounded memory growth from a hostile client (Article VII,
#: REQ-P10-BACKEND-002). Generous for a real collaborating session; intrinsic to the
#: store (not a client-facing tuning value), so module-local.
_MAX_BACKLOG_UPDATES = 100_000


class StoreError(ValueError):
    """Raised when a document's persisted update log would exceed its bound."""


class UpdateStore:
    """In-memory, ordered per-document CRDT-update-frame log (backend persistence)."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._log: Dict[str, List[bytes]] = {}

    def append(self, document_id: str, frame: bytes) -> None:
        """Append a validated update ``frame`` to ``document_id``'s ordered log.

        Raises:
            StoreError: If the document's log is already at
                :data:`_MAX_BACKLOG_UPDATES` (the backend refuses to grow without
                bound — Article VII).
        """
        log = self._log.setdefault(document_id, [])
        if len(log) >= _MAX_BACKLOG_UPDATES:
            raise StoreError(
                f"document {document_id!r} at _MAX_BACKLOG_UPDATES "
                f"({_MAX_BACKLOG_UPDATES})"
            )
        log.append(bytes(frame))

    def backlog(self, document_id: str) -> Tuple[bytes, ...]:
        """Return ``document_id``'s ordered update frames (empty if none)."""
        return tuple(self._log.get(document_id, ()))

    def documents(self) -> Tuple[str, ...]:
        """Return the ids of all documents with a persisted log (sorted)."""
        return tuple(sorted(self._log))

    def clear(self, document_id: str) -> None:
        """Drop ``document_id``'s persisted log."""
        self._log.pop(document_id, None)
