"""Immutable, content-hash-addressed asset-revision DAG — pure, zero Qt (S11).

The per-asset version model Phase 11 introduces (ADR-0030 §6; REQ-P11-LOGIC-006). It
reuses the *shape* of the shipped Phase-10
:class:`~pixelart_creator.logic.version_history.VersionHistory` (ordered, immutable,
``append`` yields a new value, bounded by a named constant) at **asset granularity** —
but it is a **distinct model**: a revision is addressed by the asset's ``content_hash``
(the CAS key + change-detector, :mod:`~pixelart_creator.logic.content_hash`) and linked
to its predecessor by ``parent_hash``, so the revisions form a **directed acyclic
graph** (a linear content-addressed chain in the append-only single-head case). It has
**no CRDT dependency** — asset revisions never route through the Phase-10
live-collaboration CRDT (which serves live documents only, ADR-0030 §6).

:class:`AssetRevision` is a frozen, deterministic descriptor;
:class:`AssetVersionHistory` is an **ordered, immutable** sequence of them:
:meth:`~AssetVersionHistory.append` returns a *new* history (never mutating the prior
one), :meth:`~AssetVersionHistory.head` returns the most recent revision, and
:meth:`~AssetVersionHistory.is_unchanged` is the content-hash change-detector at
version-model granularity ("unchanged" for a hash equal to the head's, "changed"
otherwise). The count is bounded by
:data:`~pixelart_creator.logic.constants.MAX_ASSET_VERSIONS` — exceeding it raises
:class:`AssetVersionError` rather than degrading silently (Article II/VII).

Acyclicity is enforced structurally: a revision's ``parent_hash`` may reference the
``content_hash`` of an **earlier** revision (or be an out-of-history root), never itself
or a later revision — so no cycle can be constructed. Pure and deterministic: no Qt, no
wall-clock, no randomness, no locale. ``created_marker`` is an opaque monotonic ordering
key supplied by the caller (the Phase-10 precedent — never a clock read inside this
module). Constants come from :mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from pixelart_creator.logic.constants import MAX_ASSET_VERSIONS

__all__ = [
    "AssetVersionError",
    "AssetRevision",
    "AssetVersionHistory",
]


class AssetVersionError(ValueError):
    """Raised on an invalid asset revision or history (bounds / ordering / type)."""


def _require_nonneg_int(value: Any, name: str) -> None:
    """Raise :class:`AssetVersionError` unless ``value`` is a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AssetVersionError(f"{name} must be an int, got {value!r}")
    if value < 0:
        raise AssetVersionError(f"{name} must be >= 0, got {value}")


def _require_opt_nonempty_str(value: Any, name: str) -> None:
    """Validate an optional non-empty-string field.

    Raise :class:`AssetVersionError` unless ``value`` is ``None`` or a non-empty
    str.
    """
    if value is None:
        return
    if not isinstance(value, str) or not value:
        raise AssetVersionError(
            f"{name} must be a non-empty str or None, got {value!r}"
        )


@dataclass(frozen=True)
class AssetRevision:
    """One immutable revision of an asset — a content-hash-addressed DAG node.

    Attributes:
        asset_id: The stable id of the asset this revision belongs to (non-empty str).
        content_hash: The content hash of this revision's canonical bytes (non-empty
            str; the CAS key + change-detector). Deep hex validation is a ``data/``
            concern (the revision store validates the CAS key).
        created_marker: An opaque monotonic ordering marker supplied by the caller
            (never a wall-clock read inside this pure module).
        parent_hash: The ``content_hash`` of the revision this one descends from, or
            ``None`` for a root revision. It must not equal this revision's own
            ``content_hash`` (no self-loop); within a history it must reference an
            *earlier* revision (acyclicity).
        author: An optional free-form author label, or ``None``.
    """

    asset_id: str
    content_hash: str
    created_marker: int
    parent_hash: Optional[str] = None
    author: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate id, content hash, ordering key, parent link, and author."""
        if not isinstance(self.asset_id, str) or not self.asset_id:
            raise AssetVersionError(
                f"asset_id must be a non-empty str, got {self.asset_id!r}"
            )
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise AssetVersionError(
                f"content_hash must be a non-empty str, got {self.content_hash!r}"
            )
        _require_nonneg_int(self.created_marker, "created_marker")
        _require_opt_nonempty_str(self.parent_hash, "parent_hash")
        _require_opt_nonempty_str(self.author, "author")
        if self.parent_hash is not None and self.parent_hash == self.content_hash:
            raise AssetVersionError(
                f"parent_hash must not equal the revision's own content_hash "
                f"({self.content_hash!r}) — a revision cannot be its own parent"
            )


@dataclass(frozen=True)
class AssetVersionHistory:
    """An immutable, ordered asset-revision DAG (content-hash-addressed).

    Attributes:
        revisions: The ordered :class:`AssetRevision` records;
            ``<= MAX_ASSET_VERSIONS``.
            Each revision's ``parent_hash`` (when set) references an earlier revision's
            ``content_hash`` or an out-of-history root, so the parent links form a DAG
            (a linear chain in the append-only single-head case).
    """

    revisions: Tuple[AssetRevision, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate member types, count, and the acyclic parent-link structure."""
        revisions = tuple(self.revisions)
        object.__setattr__(self, "revisions", revisions)
        # Validate every member's TYPE FIRST — before any code that reads a member's
        # attributes (``content_hash``/``parent_hash``, the ``all_hashes`` computation,
        # the DAG/parent checks) or the count bound. A non-AssetRevision member must
        # surface a domain :class:`AssetVersionError`, never a leaked ``AttributeError``
        # from touching ``.content_hash`` on a bad member; keeping this guard live (not
        # dead) is what makes defensive direct-constructor input safe.
        for revision in revisions:
            if not isinstance(revision, AssetRevision):
                raise AssetVersionError(f"expected an AssetRevision, got {revision!r}")
        if len(revisions) > MAX_ASSET_VERSIONS:
            raise AssetVersionError(
                f"{len(revisions)} revisions exceeds MAX_ASSET_VERSIONS "
                f"({MAX_ASSET_VERSIONS})"
            )
        # Every revision must belong to the same asset, and every ``parent_hash`` that
        # names a content hash present in this history must name one that appears
        # STRICTLY earlier — so a cycle (a parent pointing at itself or a later
        # revision) can never be constructed (the DAG guarantee).
        all_hashes = [r.content_hash for r in revisions]
        asset_id: Optional[str] = None
        seen_earlier: set[str] = set()
        for index, revision in enumerate(revisions):
            if asset_id is None:
                asset_id = revision.asset_id
            elif revision.asset_id != asset_id:
                raise AssetVersionError(
                    f"revision asset_id {revision.asset_id!r} does not match the "
                    f"history's asset_id {asset_id!r}"
                )
            parent = revision.parent_hash
            if (
                parent is not None
                and parent not in seen_earlier
                and parent in all_hashes
            ):
                raise AssetVersionError(
                    f"parent_hash {parent!r} of revision {index} references a "
                    f"non-earlier revision — the parent links must form a DAG"
                )
            seen_earlier.add(revision.content_hash)

    def append(self, revision: AssetRevision) -> "AssetVersionHistory":
        """Return a **new** history with ``revision`` appended (pure).

        The prior history is never mutated. The appended revision must keep the DAG
        acyclic (its ``parent_hash``, when present, references an earlier revision or an
        out-of-history root, never itself or a later revision — validated on
        construction of the new history).

        Raises:
            AssetVersionError: If ``revision`` is not an :class:`AssetRevision`,
                appending would exceed :data:`MAX_ASSET_VERSIONS`, its ``asset_id``
                differs from the history's, or its ``parent_hash`` breaks acyclicity.
        """
        if not isinstance(revision, AssetRevision):
            raise AssetVersionError(f"expected an AssetRevision, got {revision!r}")
        if len(self.revisions) >= MAX_ASSET_VERSIONS:
            raise AssetVersionError(
                f"history already at MAX_ASSET_VERSIONS ({MAX_ASSET_VERSIONS})"
            )
        return AssetVersionHistory(revisions=self.revisions + (revision,))

    def head(self) -> AssetRevision:
        """Return the most recent (last-appended) revision.

        Raises:
            AssetVersionError: If the history is empty.
        """
        if not self.revisions:
            raise AssetVersionError("asset version history is empty")
        return self.revisions[-1]

    def is_empty(self) -> bool:
        """Return whether the history holds no revisions (never raises)."""
        return not self.revisions

    def is_unchanged(self, content_hash: str) -> bool:
        """Return whether ``content_hash`` equals the head revision's content hash.

        The content-hash change-detector at version-model granularity
        (REQ-P11-LOGIC-006): ``True`` means "unchanged" (recording this content would be
        a dedup no-op against the current head), ``False`` means "changed" (or the
        history is empty, so there is nothing to be unchanged from).
        """
        if not self.revisions:
            return False
        return self.revisions[-1].content_hash == content_hash

    def by_hash(self, content_hash: str) -> AssetRevision:
        """Return the most recent revision whose content hash equals ``content_hash``.

        Raises:
            AssetVersionError: If no revision carries that content hash.
        """
        for revision in reversed(self.revisions):
            if revision.content_hash == content_hash:
                return revision
        raise AssetVersionError(f"no revision with content_hash {content_hash!r}")
