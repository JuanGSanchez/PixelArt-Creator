# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure, deterministic local-vs-remote sync-state model — zero Qt (S11).

Phase-10 Slice A (ADR-0026; spec REQ-P10-LOGIC-001). :func:`compute_sync_state` is a
**pure deterministic function** of the local version marker and the port's ordered
version list — no wall-clock, no randomness, no locale, no Qt. It classifies the
relationship between the local working copy and the remote history into one of four
module-local :class:`SyncState` values (an enumerated vocabulary local to this
module, ADR-0001 / BF-2 — the ``BlendMode``/``PlaybackMode`` precedent).

State semantics (``local_version_id`` = the remote ``version_id`` the local copy was
last synchronised to; ``None`` = the local copy has no remote lineage yet;
``versions`` = the ordered remote history from ``CloudPort.list_versions``):

* **UP_TO_DATE** — remote empty and no local marker, *or* the local marker is the
  remote latest.
* **REMOTE_AHEAD** — remote has versions and either the local copy has no marker, or
  the local marker names an *earlier* remote version (remote moved on).
* **LOCAL_AHEAD** — the local copy has a marker but the remote history is empty
  (local work not yet on the remote, or the remote was reset).
* **DIVERGED** — the local marker names a version the remote history does **not**
  contain (the histories forked).

What "DIVERGED" *resolves to* (a merge) is Slice B; Slice A models the *state* only.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence

from pixelart_creator.logic.version_history import CloudVersion

__all__ = [
    "SyncError",
    "SyncState",
    "compute_sync_state",
]


class SyncError(ValueError):
    """Raised when sync-state inputs are malformed (wrong type / bad marker)."""


class SyncState(Enum):
    """The relationship between the local working copy and the remote history.

    A module-local enumerated vocabulary (ADR-0001); values are stable strings.
    """

    UP_TO_DATE = "up_to_date"
    LOCAL_AHEAD = "local_ahead"
    REMOTE_AHEAD = "remote_ahead"
    DIVERGED = "diverged"


def compute_sync_state(
    local_version_id: Optional[str],
    versions: Sequence[CloudVersion],
) -> SyncState:
    """Classify local-vs-remote state — pure and deterministic.

    Args:
        local_version_id: The remote ``version_id`` the local copy last synced to,
            or ``None`` if the local copy has no remote lineage yet.
        versions: The ordered remote history (as returned by
            ``CloudPort.list_versions``). Iterated in order; result never depends
            on set/dict ordering.

    Returns:
        The :class:`SyncState` describing the relationship.

    Raises:
        SyncError: If ``local_version_id`` is not ``None`` and not a non-empty str,
            or ``versions`` is not a sequence of :class:`CloudVersion`.
    """
    if local_version_id is not None and (
        not isinstance(local_version_id, str) or not local_version_id
    ):
        raise SyncError(
            "local_version_id must be a non-empty str or None, got "
            f"{local_version_id!r}"
        )
    try:
        version_tuple = tuple(versions)
    except TypeError as exc:
        raise SyncError(f"versions must be a sequence, got {versions!r}") from exc
    for version in version_tuple:
        if not isinstance(version, CloudVersion):
            raise SyncError(f"expected a CloudVersion, got {version!r}")

    if not version_tuple:
        # Remote history is empty.
        return (
            SyncState.UP_TO_DATE if local_version_id is None else SyncState.LOCAL_AHEAD
        )

    # Remote has versions.
    if local_version_id is None:
        return SyncState.REMOTE_AHEAD

    latest_id = version_tuple[-1].version_id
    if local_version_id == latest_id:
        return SyncState.UP_TO_DATE
    if any(v.version_id == local_version_id for v in version_tuple):
        # Local is based on an earlier remote version; remote moved ahead.
        return SyncState.REMOTE_AHEAD
    # Local marker is unknown to the remote history: the histories forked.
    return SyncState.DIVERGED
