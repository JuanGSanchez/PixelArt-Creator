# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared-project storage + membership behind the cloud port family (zero Qt, S11).

Phase-10 Slice B (ADR-0026 §2/§6; spec REQ-P10-DATA-009, CL-B1/CL-B5). A shared
``.pixproj`` gains a **membership** roster (bounded members with a role), a **comment**
store (thread/resolve), and an **ephemeral presence** channel — all behind the SAME
cloud-port family, so the CI-tested :class:`~pixelart_creator.data.cloud.fake_adapter.
FakeCloudAdapter` (composed here for the ``.pixproj`` blob storage) makes the whole
Slice-B storage contract exercisable **headlessly with no network or credentials**.

Every membership / comment / presence payload is **untrusted input** (Article VII):
each is schema-validated with strict caps by the pure
:mod:`pixelart_creator.logic.cloud_validation` validators (``MAX_SHARED_MEMBERS`` /
``MAX_COMMENTS_PER_PROJECT`` / ``MAX_COMMENT_BYTES``), **never** ``eval``/``exec``'d;
malformed/oversized input is rejected with :class:`SharedProjectError` (a ``CloudError``
subclass — the ``data/cloud/`` error family, no provider detail leaks upward,
REQ-P10-DATA-007). **Presence is ephemeral** — kept in memory only, never written to the
``.pixproj`` or the CRDT sidecar (ADR-0028 §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pixelart_creator.data.cloud.fake_adapter import FakeCloudAdapter
from pixelart_creator.data.cloud.port import CloudError, CloudPort
from pixelart_creator.logic.cloud_validation import (
    CloudValidationError,
    validate_comment,
    validate_membership,
    validate_presence,
)
from pixelart_creator.logic.constants import MAX_COMMENTS_PER_PROJECT

__all__ = [
    "SharedProjectError",
    "RemoteMember",
    "ProjectComment",
    "PresenceEntry",
    "SharedProjectAdapter",
]


class SharedProjectError(CloudError):
    """Raised on an invalid share / membership / comment / presence operation.

    Subclasses ``CloudError`` so the shared adapter's failures stay inside the
    ``data/cloud/`` error family; validation failures from the pure
    :mod:`~pixelart_creator.logic.cloud_validation` layer are re-raised as this type
    (Article VII: reject with a ``data/cloud/`` error subclass, no ``eval``/``exec``).
    """


@dataclass(frozen=True)
class RemoteMember:
    """A normalized, provider-agnostic shared-project member (no provider field)."""

    member_id: str
    role: str


@dataclass(frozen=True)
class ProjectComment:
    """A normalized, validated comment on a shared project."""

    comment_id: str
    author_id: str
    text: str
    resolved: bool = False
    parent_id: Optional[str] = None


@dataclass(frozen=True)
class PresenceEntry:
    """A normalized, ephemeral presence record (never persisted)."""

    member_id: str
    cursor: Optional[Mapping[str, Any]] = None
    selection: Optional[Mapping[str, Any]] = None


@dataclass
class _SharedState:
    """In-memory state for one shared project: roster + comments + presence."""

    members: Tuple[RemoteMember, ...] = ()
    comments: List[ProjectComment] = field(default_factory=list)
    #: Ephemeral presence keyed by member_id — never persisted (ADR-0028 §4).
    presence: Dict[str, PresenceEntry] = field(default_factory=dict)


def _require_project_id(project_id: object) -> str:
    if not isinstance(project_id, str) or not project_id:
        raise SharedProjectError(
            f"project_id must be a non-empty str, got {project_id!r}"
        )
    return project_id


class SharedProjectAdapter:
    """Shared-project storage + membership + comments + presence (zero Qt).

    Composes an underlying :class:`~pixelart_creator.data.cloud.port.CloudPort` (the
    fake adapter by default) for the ``.pixproj`` blob storage and layers the Slice-B
    collaboration state on top. All payloads are validated via the pure
    :mod:`~pixelart_creator.logic.cloud_validation` layer before they are stored.
    """

    def __init__(self, port: Optional[CloudPort] = None) -> None:
        """Create the adapter over a blob-storage ``port`` (a fake adapter by default).

        Args:
            port: The underlying :class:`CloudPort` used for ``.pixproj`` blob storage.
                Defaults to an in-memory :class:`FakeCloudAdapter` so the whole Slice-B
                contract runs in CI with no network/credentials.
        """
        self._port: CloudPort = port if port is not None else FakeCloudAdapter()
        self._shared: Dict[str, _SharedState] = {}

    @property
    def port(self) -> CloudPort:
        """The underlying blob-storage :class:`CloudPort` (provider-agnostic)."""
        return self._port

    def _state(self, project_id: str) -> _SharedState:
        state = self._shared.get(project_id)
        if state is None:
            raise SharedProjectError(f"project {project_id!r} is not shared")
        return state

    # -- .pixproj blob passthrough (the shared project's artwork) ---------- #

    def put_project(self, project_id: str, blob: bytes) -> None:
        """Store a shared project's ``.pixproj`` bytes via the underlying port."""
        self._port.put(_require_project_id(project_id), blob)

    def get_project(self, project_id: str, version_id: str) -> bytes:
        """Fetch a shared project's stored ``.pixproj`` bytes (untrusted, validated)."""
        return self._port.get(_require_project_id(project_id), version_id)

    # -- membership -------------------------------------------------------- #

    def share(
        self, project_id: str, membership_payload: Mapping[str, Any]
    ) -> Tuple[RemoteMember, ...]:
        """Share ``project_id`` with a validated, bounded membership roster.

        The payload is schema-validated (``project_id`` + a ``members`` list bounded by
        ``MAX_SHARED_MEMBERS``, each with a known role); its ``project_id`` must match.

        Returns:
            The normalized member roster.

        Raises:
            SharedProjectError: If the payload is malformed / oversized, or its
                ``project_id`` does not match ``project_id``.
        """
        project_id = _require_project_id(project_id)
        try:
            validated = validate_membership(membership_payload)
        except CloudValidationError as exc:
            raise SharedProjectError(str(exc)) from exc
        if validated["project_id"] != project_id:
            raise SharedProjectError(
                f"membership project_id {validated['project_id']!r} does not match "
                f"{project_id!r}"
            )
        roster = tuple(
            RemoteMember(member_id=m["member_id"], role=m["role"])
            for m in validated["members"]
        )
        state = self._shared.setdefault(project_id, _SharedState())
        state.members = roster
        return roster

    def members(self, project_id: str) -> Tuple[RemoteMember, ...]:
        """Return the shared project's member roster (deterministic order)."""
        return self._state(_require_project_id(project_id)).members

    # -- comments ---------------------------------------------------------- #

    def add_comment(
        self, project_id: str, comment_payload: Mapping[str, Any]
    ) -> ProjectComment:
        """Add a validated comment to a shared project (bounded, thread-aware).

        The payload is schema-validated (``comment_id`` + ``author_id`` + ``text`` ≤
        ``MAX_COMMENT_BYTES``, optional ``resolved`` / ``parent_id``); the per-project
        count is bounded by ``MAX_COMMENTS_PER_PROJECT``.

        Raises:
            SharedProjectError: If the payload is malformed / oversized, the project is
                not shared, the ``comment_id`` is duplicate, a ``parent_id`` is unknown,
                or the comment cap is reached.
        """
        project_id = _require_project_id(project_id)
        state = self._state(project_id)
        try:
            validated = validate_comment(comment_payload)
        except CloudValidationError as exc:
            raise SharedProjectError(str(exc)) from exc
        if len(state.comments) >= MAX_COMMENTS_PER_PROJECT:
            raise SharedProjectError(
                f"project {project_id!r} already at MAX_COMMENTS_PER_PROJECT "
                f"({MAX_COMMENTS_PER_PROJECT})"
            )
        comment_id = validated["comment_id"]
        if any(c.comment_id == comment_id for c in state.comments):
            raise SharedProjectError(f"duplicate comment_id {comment_id!r}")
        parent_id = validated.get("parent_id")
        if parent_id is not None and not any(
            c.comment_id == parent_id for c in state.comments
        ):
            raise SharedProjectError(f"unknown parent comment {parent_id!r}")
        comment = ProjectComment(
            comment_id=comment_id,
            author_id=validated["author_id"],
            text=validated["text"],
            resolved=bool(validated.get("resolved", False)),
            parent_id=parent_id,
        )
        state.comments.append(comment)
        return comment

    def comments(self, project_id: str) -> Tuple[ProjectComment, ...]:
        """Return the shared project's comments in insertion order (deterministic)."""
        return tuple(self._state(_require_project_id(project_id)).comments)

    def resolve_comment(self, project_id: str, comment_id: str) -> ProjectComment:
        """Mark a comment resolved; return the updated comment.

        Raises:
            SharedProjectError: If the project is not shared or the comment is unknown.
        """
        project_id = _require_project_id(project_id)
        state = self._state(project_id)
        for index, comment in enumerate(state.comments):
            if comment.comment_id == comment_id:
                updated = ProjectComment(
                    comment_id=comment.comment_id,
                    author_id=comment.author_id,
                    text=comment.text,
                    resolved=True,
                    parent_id=comment.parent_id,
                )
                state.comments[index] = updated
                return updated
        raise SharedProjectError(f"unknown comment {comment_id!r}")

    # -- presence (ephemeral, never persisted) ----------------------------- #

    def set_presence(
        self, project_id: str, presence_payload: Mapping[str, Any]
    ) -> PresenceEntry:
        """Record a member's ephemeral presence (validated; never persisted).

        Raises:
            SharedProjectError: If the payload is malformed or the project is unshared.
        """
        project_id = _require_project_id(project_id)
        state = self._state(project_id)
        try:
            validated = validate_presence(presence_payload)
        except CloudValidationError as exc:
            raise SharedProjectError(str(exc)) from exc
        entry = PresenceEntry(
            member_id=validated["member_id"],
            cursor=validated.get("cursor"),
            selection=validated.get("selection"),
        )
        state.presence[entry.member_id] = entry
        return entry

    def presence(self, project_id: str) -> Tuple[PresenceEntry, ...]:
        """Return the current ephemeral presence entries (deterministic order).

        Ordered by ``member_id`` so the (in-memory, ephemeral) presence channel yields
        a stable read; presence is never persisted into the ``.pixproj`` or sidecar.
        """
        state = self._state(_require_project_id(project_id))
        return tuple(state.presence[mid] for mid in sorted(state.presence))

    def clear_presence(self, project_id: str, member_id: str) -> None:
        """Drop a member's ephemeral presence (e.g. on disconnect)."""
        state = self._state(_require_project_id(project_id))
        state.presence.pop(member_id, None)
