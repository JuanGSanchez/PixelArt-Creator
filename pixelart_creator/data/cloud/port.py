"""The one cloud-storage port — normalized types + transport codec (zero Qt, S11).

Phase-10 Slice A (ADR-0026 §1/§5/§6; spec REQ-P10-DATA-001/-002/-006/-007). Defines
the **single** provider-agnostic :class:`CloudPort` ABC every adapter implements — a
bounded verb set over an opaque ``.pixproj`` blob keyed by a ``project_id`` — plus
the normalized value types (:class:`RemoteItem`, :class:`Cursor`,
:class:`CloudCapabilities`) and the ``CloudError`` family. The version descriptor is
:class:`~pixelart_creator.logic.version_history.CloudVersion` (imported, not
redefined). **No provider SDK type, HTTP/credential type, or provider-specific
exception appears in these signatures** — capability differences are surfaced through
:class:`CloudCapabilities`, change tracking through an opaque :class:`Cursor`
(REQ-P10-DATA-007).

The ``.pixproj`` is the atomic **sync unit** (REQ-P10-DATA-002): this module composes
the shipped PIO-1 serialiser (``data/project_io``) — it adds **no** new format
(Article I). :func:`serialize_project` / :func:`deserialize_project` are the
port-level transport codec; :func:`deserialize_project` is the **untrusted-input
defence** (REQ-P10-DATA-006, Article VII): a blob is size-capped against
:data:`~pixelart_creator.logic.constants.MAX_CLOUD_PROJECT_BYTES` *before* decoding,
malformed/oversized/unknown-version raises :class:`CloudDataError` (a
``ProjectIOError`` subclass), and content is **never** ``eval``/``exec``'d.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Tuple

from pixelart_creator.data.project_io import ProjectIOError, deserialize, serialize
from pixelart_creator.logic.constants import MAX_CLOUD_PROJECT_BYTES
from pixelart_creator.logic.version_history import CloudVersion

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime coupling
    from pixelart_creator.logic.document import Document

__all__ = [
    "CloudError",
    "CloudDataError",
    "RemoteItem",
    "Cursor",
    "CloudCapabilities",
    "CloudPort",
    "serialize_project",
    "deserialize_project",
]


class CloudError(ValueError):
    """Base of the cloud port's own exception family (provider-agnostic)."""


class CloudDataError(ProjectIOError):
    """Raised when an untrusted cloud blob is oversized or malformed.

    Subclasses ``ProjectIOError`` (the PIO-1 family) so a caller may catch either
    it or a plain ``ProjectIOError`` from the shipped defensive load path.
    """


@dataclass(frozen=True)
class RemoteItem:
    """A normalized remote object listing (no provider field leaks upward)."""

    id: str
    name: str
    size_bytes: int


@dataclass(frozen=True)
class Cursor:
    """An opaque change-tracking token the port persists and replays.

    Unifies Drive changes-token / Graph ``deltaLink`` / Dropbox folder-cursor
    (Researcher §1.3) — its contents are provider-internal and never inspected
    above the port.
    """

    token: str


@dataclass(frozen=True)
class CloudCapabilities:
    """Normalized provider capability flags (differences surfaced, never leaked).

    Attributes:
        supports_named_revisions: The provider can pin a durable named revision
            (e.g. Drive ``keepForever``).
        supports_revision_delete: Individual revisions can be deleted.
        max_versions_per_call: Provider cap on versions returned per list call, or
            ``None`` if unbounded.
        change_feed_scope: ``"project"`` / ``"drive"`` — the change-feed granularity.
        supports_optimistic_concurrency: ``put`` honours a ``parent_version`` guard.
    """

    supports_named_revisions: bool
    supports_revision_delete: bool
    max_versions_per_call: Optional[int]
    change_feed_scope: str
    supports_optimistic_concurrency: bool


def serialize_project(document: "Document") -> bytes:
    """Serialise a ``Document`` to ``.pixproj`` transport bytes (PIO-1, no new format).

    Composes the shipped ``project_io.serialize`` (Article I) and encodes the JSON
    as UTF-8 bytes — the atomic sync unit the port transports (REQ-P10-DATA-002).
    """
    payload: Any = serialize(document)
    return json.dumps(payload).encode("utf-8")


def deserialize_project(blob: bytes) -> "Document":
    """Reconstruct a ``Document`` from untrusted cloud ``.pixproj`` bytes (defensive).

    The untrusted-input defence (REQ-P10-DATA-006, Article VII): the blob is
    size-capped against ``MAX_CLOUD_PROJECT_BYTES`` **before** any decode, then
    UTF-8/JSON decoded and validated through the shipped PIO-1 defensive path
    (``project_io.deserialize``). Content is **never** ``eval``/``exec``'d.

    Raises:
        CloudDataError: If ``blob`` is not bytes, exceeds ``MAX_CLOUD_PROJECT_BYTES``,
            or is not valid UTF-8 JSON.
        ProjectIOError: If the decoded payload is a malformed / unknown-version
            ``.pixproj`` (from the PIO-1 defensive path).
    """
    if not isinstance(blob, (bytes, bytearray)):
        raise CloudDataError(
            f"cloud project blob must be bytes, got {type(blob).__name__}"
        )
    if len(blob) > MAX_CLOUD_PROJECT_BYTES:
        raise CloudDataError(
            f"cloud project blob {len(blob)} bytes exceeds MAX_CLOUD_PROJECT_BYTES "
            f"({MAX_CLOUD_PROJECT_BYTES})"
        )
    try:
        text = bytes(blob).decode("utf-8")
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloudDataError(
            f"cloud project blob is not valid UTF-8 JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise CloudDataError("cloud project blob must decode to a JSON object")
    return deserialize(payload)


class CloudPort(ABC):
    """The one provider-agnostic cloud-storage interface (ADR-0026 §1).

    Every adapter (the fake adapter; later, real Drive/OneDrive/Dropbox adapters)
    implements this. The blob is a ``.pixproj``'s bytes; the ``project_id`` is a
    provider-agnostic key. Callers validate fetched bytes with
    :func:`deserialize_project` (untrusted-input defence).
    """

    @abstractmethod
    def put(
        self,
        project_id: str,
        blob: bytes,
        *,
        parent_version: Optional[str] = None,
    ) -> CloudVersion:
        """Store a new version of ``project_id``; return its :class:`CloudVersion`.

        Where the provider supports optimistic concurrency, ``parent_version`` is
        the ``version_id`` the write is expected to follow; a mismatch is a
        conflict (``CloudError``).
        """

    @abstractmethod
    def get(self, project_id: str, version_id: str) -> bytes:
        """Fetch a specific version's raw ``.pixproj`` bytes (validated by caller)."""

    @abstractmethod
    def list_versions(self, project_id: str) -> Tuple[CloudVersion, ...]:
        """Return the ordered version history (stable, deterministic order)."""

    @abstractmethod
    def latest(self, project_id: str) -> CloudVersion:
        """Return the most recent :class:`CloudVersion` of ``project_id``."""

    @abstractmethod
    def delete(self, project_id: str) -> None:
        """Delete ``project_id`` (all versions + its recovery slot)."""

    @abstractmethod
    def put_recovery(self, project_id: str, blob: bytes) -> None:
        """Store the working ``.pixproj`` to the autosave/recovery slot.

        Distinct from the explicit version history — writing recovery never
        touches the user's last explicit saved version (REQ-P10-DATA-004).
        """

    @abstractmethod
    def get_recovery(self, project_id: str) -> Optional[bytes]:
        """Return the recovery-slot bytes, or ``None`` if none exists."""

    @abstractmethod
    def capabilities(self) -> CloudCapabilities:
        """Return this adapter's normalized :class:`CloudCapabilities`."""

    def is_connected(self) -> bool:
        """Whether the adapter is connected (provider-agnostic; no token exposed).

        Default ``False``; concrete adapters override. ``ui/`` never sees a token
        (REQ-P10-DATA-008).
        """
        return False
