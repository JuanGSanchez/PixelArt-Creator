"""Shared-project collaboration session seam (REQ-P10-UI-009/-010/-011).

Phase-10 **Slice B** binds the shared-projects / comments / presence panels to the
frozen, Qt-free
:class:`~pixelart_creator.data.cloud.shared_adapter.SharedProjectAdapter`
(shared projects + membership + comments + ephemeral presence, DATA-009). Every
collaboration operation in Slice B is a **purely synchronous, in-memory call over the
loopback path** — the adapter composes an in-memory
:class:`~pixelart_creator.data.cloud.fake_adapter.FakeCloudAdapter` (no network, no
credentials, no I/O) — so **no off-GUI-thread worker, timer, or poller is introduced
here** (the real sync backend + live push is Slice C, out of scope). There is therefore
**nothing new to tear down**: this is a plain object-owned :class:`QObject`.

:class:`Collaboration_Session` is the provider-agnostic seam the panels drive: it holds
the active :class:`SharedProjectAdapter` (built by an injectable factory — the fake
loopback adapter by default; a test or a later slice swaps the factory with **no** panel
change) and the active shared-project id, wraps the adapter's verbs so a validation /
domain failure surfaces as a caught :class:`SharedProjectError`, and emits change
signals the panels refresh from. ``ui/`` never sees a provider type or a token
(DATA-007/-008) — only the abstract adapter and normalized value objects
(:class:`RemoteMember` / :class:`ProjectComment` / :class:`PresenceEntry`).

No ``eval`` / ``exec``: every membership / comment / presence payload is validated by
the pure :mod:`pixelart_creator.logic.cloud_validation` layer inside the adapter
(Article VII) before it is stored; this module only builds inert mapping payloads and
forwards them.
"""

from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from PySide6.QtCore import QObject, Signal

from pixelart_creator.data.cloud import (
    PresenceEntry,
    ProjectComment,
    RemoteMember,
    SharedProjectAdapter,
)

#: Factory that builds a fresh :class:`SharedProjectAdapter` for a session. Injectable
#: so a test (or a later real-backed slice) swaps the loopback adapter with no UI change
#: — the adapter is the provider-agnostic seam (REQ-P10-DATA-007).
SharedAdapterFactory = Callable[[], SharedProjectAdapter]


def _default_shared_factory() -> SharedProjectAdapter:
    """Build the default Slice-B adapter: an in-memory loopback shared adapter.

    Deterministic, no network, no credentials — the whole Slice-B collaboration
    contract runs headlessly. A real-backed adapter is a drop-in replacement passed
    to :class:`Collaboration_Session`.
    """
    return SharedProjectAdapter()


class Collaboration_Session(QObject):
    """Provider-agnostic shared-project session over the loopback adapter (Slice B).

    Holds the active :class:`SharedProjectAdapter` (or ``None`` before a project is
    shared) + the active shared-project id, and re-emits collaboration changes as Qt
    signals the panels refresh from. Purely synchronous — owns no worker/timer, so it
    needs no deterministic teardown beyond ordinary Qt parent ownership.
    """

    #: ``(project_id,)`` — the active shared project changed (``""`` when none).
    sharedProjectChanged = Signal(str)
    #: ``(project_id,)`` — the member roster changed for this project.
    membersChanged = Signal(str)
    #: ``(project_id,)`` — the comment thread changed for this project.
    commentsChanged = Signal(str)
    #: ``(project_id,)`` — the ephemeral presence roster changed for this project.
    presenceChanged = Signal(str)

    def __init__(
        self,
        factory: Optional[SharedAdapterFactory] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """Create an inactive session bound to ``factory`` (default loopback)."""
        super().__init__(parent)
        self._factory: SharedAdapterFactory = factory or _default_shared_factory
        self._adapter: Optional[SharedProjectAdapter] = None
        self._project_id: Optional[str] = None
        #: Monotonic UI-side comment-id source (presentation identifier, not a
        #: domain value); a str id keeps the adapter's schema happy + deterministic.
        self._comment_ids = itertools.count(1)

    # -- queries ----------------------------------------------------------

    def adapter(self) -> Optional[SharedProjectAdapter]:
        """Return the active :class:`SharedProjectAdapter`, or ``None``."""
        return self._adapter

    def active_project_id(self) -> Optional[str]:
        """Return the active shared-project id, or ``None`` when none is open."""
        return self._project_id

    def is_active(self) -> bool:
        """Return whether a shared project is currently open."""
        return self._adapter is not None and self._project_id is not None

    # -- membership -------------------------------------------------------

    def share(
        self, project_id: str, members: Sequence[Tuple[str, str]]
    ) -> Tuple[RemoteMember, ...]:
        """Share ``project_id`` with a full ``(member_id, role)`` roster.

        Builds the adapter on first use, forwards a validated membership payload,
        makes ``project_id`` the active shared project, and emits
        :attr:`sharedProjectChanged` + :attr:`membersChanged`. Re-sharing an already
        shared project replaces its roster (there is no incremental add in the port).

        Raises:
            SharedProjectError: If the payload is malformed / oversized (surfaced by
                the caller). Propagated unchanged so the panel can show it.
        """
        if self._adapter is None:
            self._adapter = self._factory()
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "members": [
                {"member_id": member_id, "role": role} for member_id, role in members
            ],
        }
        roster = self._adapter.share(project_id, payload)
        newly_active = self._project_id != project_id
        self._project_id = project_id
        if newly_active:
            self.sharedProjectChanged.emit(project_id)
        self.membersChanged.emit(project_id)
        return roster

    def members(self, project_id: str) -> Tuple[RemoteMember, ...]:
        """Return the shared project's member roster (deterministic order)."""
        if self._adapter is None:
            return ()
        return self._adapter.members(project_id)

    def leave(self) -> None:
        """Close the active shared project (clears the active id; keeps state)."""
        self._project_id = None
        self.sharedProjectChanged.emit("")

    # -- comments ---------------------------------------------------------

    def add_comment(
        self,
        project_id: str,
        author_id: str,
        text: str,
        parent_id: Optional[str] = None,
    ) -> ProjectComment:
        """Add a validated comment (optionally threaded under ``parent_id``).

        Generates a UI-side ``comment_id``, forwards a validated payload, and emits
        :attr:`commentsChanged`. The adapter enforces ``MAX_COMMENT_BYTES`` /
        ``MAX_COMMENTS_PER_PROJECT`` (Article VII) as defence in depth behind the
        panel's own edge check.

        Raises:
            SharedProjectError: On a malformed / oversized / duplicate / capped
                comment (surfaced by the caller).
        """
        if self._adapter is None:
            self._adapter = self._factory()
        payload: Dict[str, Any] = {
            "comment_id": f"c{next(self._comment_ids)}",
            "author_id": author_id,
            "text": text,
        }
        if parent_id is not None:
            payload["parent_id"] = parent_id
        comment = self._adapter.add_comment(project_id, payload)
        self.commentsChanged.emit(project_id)
        return comment

    def comments(self, project_id: str) -> Tuple[ProjectComment, ...]:
        """Return the shared project's comments in insertion order."""
        if self._adapter is None:
            return ()
        return self._adapter.comments(project_id)

    def resolve_comment(self, project_id: str, comment_id: str) -> ProjectComment:
        """Mark a comment resolved and emit :attr:`commentsChanged`.

        Raises:
            SharedProjectError: If the project is not shared or the comment is unknown.
        """
        if self._adapter is None:
            raise _not_shared(project_id)
        updated = self._adapter.resolve_comment(project_id, comment_id)
        self.commentsChanged.emit(project_id)
        return updated

    # -- presence (ephemeral, never persisted) ----------------------------

    def announce_presence(self, project_id: str, member_id: str) -> PresenceEntry:
        """Record ``member_id`` as present (ephemeral) and emit the change.

        Presence carries no cursor here — Slice B shows *who* is present
        (REQ-P10-UI-011); live cursor rendering is Slice C (REQ-P10-UI-013).

        Raises:
            SharedProjectError: If the project is not shared (surfaced by the caller).
        """
        if self._adapter is None:
            raise _not_shared(project_id)
        entry = self._adapter.set_presence(project_id, {"member_id": member_id})
        self.presenceChanged.emit(project_id)
        return entry

    def presence(self, project_id: str) -> Tuple[PresenceEntry, ...]:
        """Return the current ephemeral presence entries (deterministic order)."""
        if self._adapter is None:
            return ()
        return self._adapter.presence(project_id)

    def clear_presence(self, project_id: str, member_id: str) -> None:
        """Drop a member's ephemeral presence and emit the change."""
        if self._adapter is None:
            return
        self._adapter.clear_presence(project_id, member_id)
        self.presenceChanged.emit(project_id)


def _not_shared(project_id: str) -> Exception:
    """Build the shared adapter's own error for an operation before any share."""
    # Imported lazily so this module keeps a single import site for the error type
    # and the type is exactly the data/cloud family the panels already catch.
    from pixelart_creator.data.cloud import SharedProjectError

    return SharedProjectError(f"project {project_id!r} is not shared")
