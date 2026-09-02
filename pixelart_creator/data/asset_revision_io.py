# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Revision-history index + per-asset sidecar persistence — zero Qt (S11; ADR-0030 §6).

Persist and reload the append-only, content-hash-addressed revision DAG the
:mod:`~pixelart_creator.logic.asset_version` model defines
(``AssetVersionHistory``/``AssetRevision``), so an asset's revision history survives an
application restart (``REQ-P11-DATA-008``'s revision half; ``SC-P11-INGRESS-E2E-1``'s
restart clause). Before this module, ``AssetRevisionStore._histories`` lived in memory
only — this module gives it a durable home, on the shipped catalog serialiser's own
shape: an index (``<root>/revisions.json``) listing the asset ids that have a history,
plus one per-asset sidecar (``<root>/revisions/<asset_id>.json``). It defines **no
second revision model** — every reconstructed value is rebuilt through
:class:`~pixelart_creator.logic.asset_version.AssetRevision` /
:class:`~pixelart_creator.logic.asset_version.AssetVersionHistory`, so the logic
layer's own ``__post_init__`` bounds (``MAX_ASSET_VERSIONS``) and DAG-acyclicity rule
are the only bound enforced here — this module invents no second cap.

**Untrusted-input defence (Article VII).** Every loaded index/sidecar is parsed with
:mod:`json` only (**never** ``eval``/``exec``/``pickle``), schema- and type-checked,
count-capped (:data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS` on the index
— the revision index is keyed by asset id, the same universe the catalog index bounds),
every ``content_hash``/``parent_hash`` validated as a well-formed hex hash via
:func:`~pixelart_creator.logic.content_hash.is_valid_hash`, every asset id validated as
a safe filename component via the promoted
:func:`~pixelart_creator.data.asset_catalog_io.safe_asset_id`, and every sidecar path
resolved and containment-checked under ``root`` via the promoted
:func:`~pixelart_creator.data.asset_catalog_io.resolve_within`. A helper's
:class:`~pixelart_creator.data.asset_catalog_io.AssetCatalogError` is re-raised here as
:class:`AssetRevisionIOError`, and a model-layer
:class:`~pixelart_creator.logic.asset_version.AssetVersionError` (bounds/DAG violation)
is surfaced the same way. **An absent index loads as an empty mapping, not an error** —
this is what keeps ``REQ-P11-DATA-008``'s "creates nothing on disk" clause true for a
project with no recorded revisions yet. Zero Qt; this module names no UI and resolves
no root of its own — ``root`` is always supplied by the caller (ADR-0051).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union

from pixelart_creator.data.asset_catalog_io import (
    AssetCatalogError,
    resolve_within,
    safe_asset_id,
)
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_version import (
    AssetRevision,
    AssetVersionError,
    AssetVersionHistory,
)
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS
from pixelart_creator.logic.content_hash import is_valid_hash

__all__ = [
    "AssetRevisionIOError",
    "FORMAT_NAME",
    "REVISIONS_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "INDEX_FILENAME",
    "REVISIONS_DIRNAME",
    "write_history",
    "write_index",
    "load_histories",
    "save_histories",
]

#: The revision-index format marker.
FORMAT_NAME = "pixrevisions"

#: Revision-index wire schema version — a module-local format-intrinsic string
#: (ADR-0001 / BF-2, the catalog-index precedent).
REVISIONS_SCHEMA_VERSION: str = "1"

#: Schema versions this build can load.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (REVISIONS_SCHEMA_VERSION,)

#: The revision-index filename under ``root``.
INDEX_FILENAME = "revisions.json"

#: The per-asset revision-sidecar sub-directory under ``root``.
REVISIONS_DIRNAME = "revisions"


class AssetRevisionIOError(ProjectIOError):
    """Raised when a revision history cannot be persisted or is malformed on load."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssetRevisionIOError(message)


def _load_json(path: Path, what: str) -> Any:
    """Read + JSON-parse ``path`` defensively (never eval/exec), else raise."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssetRevisionIOError(f"cannot read {what}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssetRevisionIOError(f"{what} is not valid JSON: {exc}") from exc


def _safe_id(asset_id: str) -> str:
    """Validate ``asset_id`` as a safe sidecar filename component (re-raised)."""
    try:
        return safe_asset_id(asset_id)
    except AssetCatalogError as exc:
        raise AssetRevisionIOError(str(exc)) from exc


def _resolve(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` under ``root`` with containment defence (re-raised)."""
    try:
        return resolve_within(root, candidate)
    except AssetCatalogError as exc:
        raise AssetRevisionIOError(str(exc)) from exc


def _serialise_revision(revision: AssetRevision) -> Dict[str, Any]:
    """Serialise one revision to a plain JSON-ready dict."""
    return {
        "asset_id": revision.asset_id,
        "content_hash": revision.content_hash,
        "created_marker": revision.created_marker,
        "parent_hash": revision.parent_hash,
        "author": revision.author,
    }


def _parse_revision(payload: Any, asset_id: str) -> AssetRevision:
    """Reconstruct one revision from a parsed sidecar entry (defensive).

    Raises:
        AssetRevisionIOError: If any field is missing/mistyped, a hash is not
            well-formed, or the entry breaks a version-model invariant.
    """
    _require(
        isinstance(payload, dict), f"revision entry for {asset_id!r} must be an object"
    )
    entry_asset_id = payload.get("asset_id")
    _require(
        entry_asset_id == asset_id,
        f"revision entry asset_id {entry_asset_id!r} does not match sidecar "
        f"{asset_id!r}",
    )
    content_hash_value = payload.get("content_hash")
    _require(
        is_valid_hash(content_hash_value),
        f"revision content_hash for {asset_id!r} must be a valid hex hash",
    )
    created_marker = payload.get("created_marker")
    _require(
        isinstance(created_marker, int) and not isinstance(created_marker, bool),
        f"revision created_marker for {asset_id!r} must be an int",
    )
    parent_hash = payload.get("parent_hash")
    if parent_hash is not None:
        _require(
            is_valid_hash(parent_hash),
            f"revision parent_hash for {asset_id!r} must be a valid hex hash or null",
        )
    author = payload.get("author")
    if author is not None:
        _require(
            isinstance(author, str) and bool(author),
            f"revision author for {asset_id!r} must be a non-empty string or null",
        )
    try:
        return AssetRevision(
            asset_id=asset_id,
            content_hash=content_hash_value,
            created_marker=created_marker,
            parent_hash=parent_hash,
            author=author,
        )
    except AssetVersionError as exc:  # bounds / self-loop defence
        raise AssetRevisionIOError(f"invalid asset revision: {exc}") from exc


def write_history(
    root: Union[str, Path], asset_id: str, history: AssetVersionHistory
) -> None:
    """Write ``asset_id``'s sidecar as ``<root>/revisions/<asset_id>.json``.

    Creates the revisions directory on demand. Does **not** touch the index — call
    :func:`write_index` after every sidecar in a batch has been written. The commit
    point issues the two in order; they are two functions on purpose.

    Raises:
        AssetRevisionIOError: If ``asset_id`` is not a safe filename, ``history`` is
            not an :class:`AssetVersionHistory`, or the file cannot be written.
    """
    if not isinstance(history, AssetVersionHistory):
        raise AssetRevisionIOError(f"expected an AssetVersionHistory, got {history!r}")
    safe_id = _safe_id(asset_id)
    root_path = Path(root)
    revisions_dir = root_path / REVISIONS_DIRNAME
    try:
        revisions_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AssetRevisionIOError(
            f"cannot create revisions directory under {str(root)!r}: {exc}"
        ) from exc
    sidecar = {
        "asset_id": asset_id,
        "revisions": [_serialise_revision(revision) for revision in history.revisions],
    }
    sidecar_path = revisions_dir / f"{safe_id}.json"
    try:
        sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    except OSError as exc:
        raise AssetRevisionIOError(
            f"cannot write revision sidecar for {asset_id!r}: {exc}"
        ) from exc


def write_index(root: Union[str, Path], asset_ids: Sequence[str]) -> None:
    """Write ``<root>/revisions.json`` listing every asset id with a revision history.

    Raises:
        AssetRevisionIOError: If the file cannot be written.
    """
    root_path = Path(root)
    index = {
        "format": FORMAT_NAME,
        "schema_version": REVISIONS_SCHEMA_VERSION,
        "asset_ids": list(asset_ids),
    }
    try:
        (root_path / INDEX_FILENAME).write_text(json.dumps(index), encoding="utf-8")
    except OSError as exc:
        raise AssetRevisionIOError(f"cannot write revision index: {exc}") from exc


def load_histories(root: Union[str, Path]) -> Dict[str, AssetVersionHistory]:
    """Load every asset's revision history persisted under ``root``.

    An **absent index returns an empty mapping, not an error** — this is what keeps
    ``REQ-P11-DATA-008``'s "creates nothing on disk" clause true for a project with no
    recorded revisions yet. Otherwise the index is validated (``format``,
    ``schema_version`` in :data:`SUPPORTED_SCHEMA_VERSIONS`, ``asset_ids`` a list
    capped at :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`), and each
    sidecar is read **strictly** — a missing sidecar for an indexed id raises, exactly
    as the catalog serialiser's ``load_catalog`` does.

    Raises:
        AssetRevisionIOError: If the index or any indexed sidecar is malformed,
            oversized, exceeds the cap, carries an invalid hash, or an indexed id's
            sidecar is missing.
    """
    root_path = Path(root)
    index_path = root_path / INDEX_FILENAME
    if not index_path.exists():
        return {}

    index = _load_json(index_path, "revision index")
    _require(isinstance(index, dict), "revision index must be a JSON object")
    _require(index.get("format") == FORMAT_NAME, "not a pixrevisions index")
    schema_version = index.get("schema_version")
    _require(
        isinstance(schema_version, str) and schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported revision schema_version {schema_version!r}",
    )
    asset_ids = index.get("asset_ids")
    _require(isinstance(asset_ids, list), "revision index asset_ids must be a list")
    _require(
        len(asset_ids) <= MAX_CATALOG_ASSETS,
        f"revision index exceeds MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS})",
    )

    revisions_dir = root_path / REVISIONS_DIRNAME
    histories: Dict[str, AssetVersionHistory] = {}
    for asset_id in asset_ids:
        _require(
            isinstance(asset_id, str) and bool(asset_id),
            "each revision index asset_id must be a non-empty string",
        )
        safe_id = _safe_id(asset_id)
        sidecar_path = _resolve(revisions_dir, f"{safe_id}.json")
        payload = _load_json(sidecar_path, f"revision sidecar for {asset_id!r}")
        _require(
            isinstance(payload, dict),
            f"revision sidecar for {asset_id!r} must be a JSON object",
        )
        sidecar_asset_id = payload.get("asset_id")
        _require(
            sidecar_asset_id == asset_id,
            f"revision sidecar asset_id {sidecar_asset_id!r} does not match indexed "
            f"id {asset_id!r}",
        )
        entries = payload.get("revisions")
        _require(
            isinstance(entries, list),
            f"revision sidecar for {asset_id!r} must have a 'revisions' list",
        )
        revisions = tuple(_parse_revision(entry, asset_id) for entry in entries)
        try:
            histories[asset_id] = AssetVersionHistory(revisions=revisions)
        except AssetVersionError as exc:  # count / DAG defence
            raise AssetRevisionIOError(
                f"invalid revision history for {asset_id!r}: {exc}"
            ) from exc
    return histories


def save_histories(
    root: Union[str, Path], histories: Mapping[str, AssetVersionHistory]
) -> None:
    """Persist every history in ``histories`` under ``root``.

    Writes every sidecar first, then the index last.

    Raises:
        AssetRevisionIOError: If any asset id is not a safe filename, any value is not
            an :class:`AssetVersionHistory`, or a file cannot be written.
    """
    asset_ids: List[str] = []
    for asset_id, history in histories.items():
        write_history(root, asset_id, history)
        asset_ids.append(asset_id)
    write_index(root, asset_ids)
