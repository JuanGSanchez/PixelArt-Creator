"""Ordered, immutable cloud version-history model — pure, zero Qt (S11).

The version model for the Phase-10 cloud layer (Slice A, ADR-0026 §5). A cloud
version is a small metadata **envelope** *around* a ``.pixproj``'s bytes — never
inside the artwork file (BF-2; the ADR-0025 sidecar precedent), so the shipped
PIO-1 ``.pixproj`` format is transported as-is and never forked (Article I).

:class:`CloudVersion` is the normalized descriptor the ``data/cloud/`` port returns
(no provider field leaks upward — REQ-P10-DATA-007); :class:`VersionHistory` is an
**ordered, immutable** sequence of them: ``append`` yields a *new* history without
mutating the prior one, iteration order is deterministic (strictly ascending
``ordinal``), and the count is bounded by
:data:`~pixelart_creator.logic.constants.MAX_CLOUD_VERSIONS` — exceeding it raises
:class:`VersionHistoryError` rather than degrading silently (Article II/VII).

Pure and deterministic: no wall-clock, no randomness, no locale. The ``created_marker``
is an opaque monotonic ordering key supplied by the adapter (never read from a clock
inside this module). Constants come from
:mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from pixelart_creator.logic.constants import (
    MAX_CLOUD_PROJECT_BYTES,
    MAX_CLOUD_VERSIONS,
)

__all__ = [
    "VersionHistoryError",
    "CloudVersion",
    "VersionHistory",
]


class VersionHistoryError(ValueError):
    """Raised on an invalid cloud version or history (bounds / ordering / type)."""


def _require_nonneg_int(value: Any, name: str) -> None:
    """Raise :class:`VersionHistoryError` unless ``value`` is a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise VersionHistoryError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise VersionHistoryError(f"{name} must be >= 0, got {value}")


def _require_opt_nonempty_str(value: Any, name: str) -> None:
    """Raise :class:`VersionHistoryError` unless ``value`` is ``None`` or a str."""
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise VersionHistoryError(
            f"{name} must be a non-empty str or None, got {value!r}"
        )


@dataclass(frozen=True)
class CloudVersion:
    """One cloud version — a metadata envelope around a stored ``.pixproj`` blob.

    Attributes:
        version_id: Stable, provider-agnostic id of this version (non-empty).
        ordinal: Monotonic 0-based ordering key within the project's history.
        created_marker: Opaque monotonic ordering marker supplied by the adapter
            (never a wall-clock read inside this pure module).
        size_bytes: Stored ``.pixproj`` blob size; ``<= MAX_CLOUD_PROJECT_BYTES``.
        is_pinned: Whether the version is pinned against provider auto-pruning
            (surfaced where ``CloudCapabilities.supports_named_revisions``).
        parent_version_id: The ``version_id`` this version was ``put`` against
            (optimistic-concurrency parent), or ``None`` for the first version.
        remote_revision_id: The provider revision id this local version maps to
            (the ``local -> remote`` reconciliation map, BF-2), or ``None``.
    """

    version_id: str
    ordinal: int
    created_marker: int
    size_bytes: int
    is_pinned: bool = False
    parent_version_id: Optional[str] = None
    remote_revision_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate id, ordering keys, size cap, and optional references."""
        if not isinstance(self.version_id, str) or not self.version_id:
            raise VersionHistoryError(
                f"version_id must be a non-empty str, got {self.version_id!r}"
            )
        _require_nonneg_int(self.ordinal, "ordinal")
        _require_nonneg_int(self.created_marker, "created_marker")
        _require_nonneg_int(self.size_bytes, "size_bytes")
        if self.size_bytes > MAX_CLOUD_PROJECT_BYTES:
            raise VersionHistoryError(
                f"size_bytes {self.size_bytes} exceeds MAX_CLOUD_PROJECT_BYTES "
                f"({MAX_CLOUD_PROJECT_BYTES})"
            )
        if not isinstance(self.is_pinned, bool):
            raise VersionHistoryError(
                f"is_pinned must be a bool, got {self.is_pinned!r}"
            )
        _require_opt_nonempty_str(self.parent_version_id, "parent_version_id")
        _require_opt_nonempty_str(self.remote_revision_id, "remote_revision_id")


@dataclass(frozen=True)
class VersionHistory:
    """An immutable, ordered cloud version history.

    Attributes:
        versions: Ordered :class:`CloudVersion` records with strictly ascending
            ``ordinal`` and unique ``version_id``; ``<= MAX_CLOUD_VERSIONS``.
    """

    versions: Tuple[CloudVersion, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate count, member types, unique ids, and ascending ordinals."""
        versions = tuple(self.versions)
        object.__setattr__(self, "versions", versions)
        if len(versions) > MAX_CLOUD_VERSIONS:
            raise VersionHistoryError(
                f"{len(versions)} versions exceeds MAX_CLOUD_VERSIONS "
                f"({MAX_CLOUD_VERSIONS})"
            )
        seen_ids: set[str] = set()
        prev_ordinal: Optional[int] = None
        for version in versions:
            if not isinstance(version, CloudVersion):
                raise VersionHistoryError(f"expected a CloudVersion, got {version!r}")
            if version.version_id in seen_ids:
                raise VersionHistoryError(
                    f"duplicate version_id {version.version_id!r}"
                )
            seen_ids.add(version.version_id)
            if prev_ordinal is not None and version.ordinal <= prev_ordinal:
                raise VersionHistoryError(
                    f"ordinal {version.ordinal} is not strictly ascending "
                    f"(previous was {prev_ordinal})"
                )
            prev_ordinal = version.ordinal

    def append(self, version: CloudVersion) -> "VersionHistory":
        """Return a **new** history with ``version`` appended (pure).

        The appended version's ``ordinal`` must be strictly greater than the
        current last ordinal, and its ``version_id`` must be unique.

        Raises:
            VersionHistoryError: If appending would exceed ``MAX_CLOUD_VERSIONS``,
                break strictly-ascending ordinals, or duplicate a ``version_id``.
        """
        if not isinstance(version, CloudVersion):
            raise VersionHistoryError(f"expected a CloudVersion, got {version!r}")
        if len(self.versions) >= MAX_CLOUD_VERSIONS:
            raise VersionHistoryError(
                f"history already at MAX_CLOUD_VERSIONS ({MAX_CLOUD_VERSIONS})"
            )
        return VersionHistory(versions=self.versions + (version,))

    def latest(self) -> CloudVersion:
        """Return the most recent version (highest ordinal / last appended).

        Raises:
            VersionHistoryError: If the history is empty.
        """
        if not self.versions:
            raise VersionHistoryError("version history is empty")
        return self.versions[-1]

    def by_id(self, version_id: str) -> CloudVersion:
        """Return the version with ``version_id``.

        Raises:
            VersionHistoryError: If no version has that id.
        """
        for version in self.versions:
            if version.version_id == version_id:
                return version
        raise VersionHistoryError(f"no version with id {version_id!r}")
