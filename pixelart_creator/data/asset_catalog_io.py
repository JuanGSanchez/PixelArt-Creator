"""Catalog + per-asset sidecar persistence — defensive, zero Qt (S11; ADR-0030 §1/§2).

Persist and reload an :class:`~pixelart_creator.logic.asset_catalog.AssetCatalog`
locally
(REQ-P11-DATA-001/-002/-003/-007). Identity is by **stable ``AssetId`` + per-asset
sidecar** (the Unity/Godot/Unreal common thread, Researcher §1): each descriptor is
written to ``<root>/assets/<asset_id>.json``, indexed by ``<root>/catalog.json``. The
catalog stores **references + metadata**, never a copy of the asset payload.

The asset **payload** is the shipped **PIO-1** ``.pixproj`` form — this module
**composes** ``data/project_io`` (:func:`store_asset` / :func:`load_asset`) to
serialise/reconstruct an asset's bytes through the content-addressable store, and
defines
**no second serialiser** (REQ-P11-DATA-007 / Article I). The canonical bytes are
produced
by :func:`~pixelart_creator.logic.content_hash.canonical_json_bytes` so an asset
round-trips to an *equivalent* entity via PIO-1.

**Untrusted-input defence (Article VII, REQ-P11-DATA-002; Researcher §5).** Every loaded
catalog/sidecar is treated as untrusted: parsed with :mod:`json` only (**never**
``eval``/``exec``/``pickle``), schema- and type-checked, size/count-capped
(:data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS` and the descriptor's own
tag / metadata caps), the ``content_hash`` validated as a well-formed hex hash, and
every
path — an ``asset_id`` used as a sidecar filename and the advisory ``path`` field — is
**path-traversal-defended**: resolved and confirmed contained within ``root``
(``resolve()`` + ``relative_to`` containment; ``..`` and absolute-path escapes
rejected).
Malformed / oversized / escaping input raises :class:`AssetCatalogError` (a
:class:`~pixelart_creator.data.project_io.ProjectIOError` subclass — the PIO-1 family,
so
a caller may catch either). Zero Qt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from pixelart_creator.data import project_io
from pixelart_creator.data.asset_cas import ContentAddressableStore
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS
from pixelart_creator.logic.content_hash import canonical_json_bytes, is_valid_hash
from pixelart_creator.logic.document import Document

__all__ = [
    "AssetCatalogError",
    "FORMAT_NAME",
    "CATALOG_SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "INDEX_FILENAME",
    "ASSETS_DIRNAME",
    "save_catalog",
    "load_catalog",
    "store_asset",
    "load_asset",
]

#: The catalog-index format marker.
FORMAT_NAME = "pixcatalog"

#: Catalog wire schema version — a module-local format-intrinsic string (ADR-0001 /
#: BF-2,
#: the macro/timelapse/reference-board precedent).
CATALOG_SCHEMA_VERSION: str = "1"

#: Schema versions this build can load.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (CATALOG_SCHEMA_VERSION,)

#: The catalog-index filename under ``root``.
INDEX_FILENAME = "catalog.json"

#: The per-asset sidecar sub-directory under ``root``.
ASSETS_DIRNAME = "assets"

#: Characters an ``asset_id`` may contain to be a safe sidecar filename component.
_SAFE_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


class AssetCatalogError(ProjectIOError):
    """Raised when a catalog cannot be persisted or is malformed on load."""


# --------------------------------------------------------------------------- #
# Path-traversal defence                                                      #
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssetCatalogError(message)


def _safe_asset_id(asset_id: str) -> str:
    """Return ``asset_id`` if it is a safe filename component, else raise.

    An id used as a sidecar filename must not be a path separator, ``.``/``..``, or
    contain any character outside :data:`_SAFE_ID_CHARS` — so it can never escape the
    assets directory (Article VII path-traversal defence).
    """
    if not isinstance(asset_id, str) or not asset_id:
        raise AssetCatalogError(f"asset_id must be a non-empty str, got {asset_id!r}")
    if asset_id in (".", "..") or "/" in asset_id or "\\" in asset_id:
        raise AssetCatalogError(f"asset_id {asset_id!r} is not a safe filename")
    if any(ch not in _SAFE_ID_CHARS for ch in asset_id):
        raise AssetCatalogError(
            f"asset_id {asset_id!r} contains characters unsafe for a filename"
        )
    return asset_id


def _resolve_within(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` under ``root`` and confirm containment, else raise.

    The robust path-traversal defence (Researcher §5): canonicalize with ``resolve()``
    (collapsing ``..`` and symlinks), then confirm the result is inside ``root`` via
    ``relative_to``. An absolute ``candidate`` or one escaping ``root`` raises.
    """
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise AssetCatalogError(
            f"path {candidate!r} escapes the catalog root {str(root)!r}"
        ) from exc
    return resolved


# --------------------------------------------------------------------------- #
# Descriptor <-> sidecar                                                       #
# --------------------------------------------------------------------------- #


def _serialise_descriptor(descriptor: AssetDescriptor) -> Dict[str, Any]:
    """Serialise a descriptor to a plain JSON-ready sidecar dict (tags sorted)."""
    return {
        "asset_id": descriptor.asset_id,
        "kind": descriptor.kind.value,
        "name": descriptor.name,
        "content_hash": descriptor.content_hash,
        "tags": sorted(descriptor.tags),
        "metadata": dict(descriptor.metadata),
        "path": descriptor.path,
    }


def _parse_kind(value: Any) -> AssetKind:
    if not isinstance(value, str):
        raise AssetCatalogError(f"kind must be a string, got {value!r}")
    try:
        return AssetKind(value)
    except ValueError as exc:
        raise AssetCatalogError(f"unknown asset kind {value!r}") from exc


def _parse_tags(value: Any) -> Tuple[str, ...]:
    _require(isinstance(value, list), "tags must be a list")
    for tag in value:
        _require(isinstance(tag, str), "each tag must be a string")
    return tuple(value)


def _parse_metadata(value: Any) -> Mapping[str, object]:
    """Return the sidecar ``metadata`` object (deep validation is the descriptor's)."""
    _require(isinstance(value, dict), "metadata must be an object")
    for key in value:
        _require(isinstance(key, str), "metadata keys must be strings")
    return value


def _parse_descriptor(payload: Any, root: Path) -> AssetDescriptor:
    """Reconstruct a descriptor from a parsed sidecar dict (defensive).

    Raises:
        AssetCatalogError: If any field is missing/mistyped/out of bounds, the
            ``content_hash`` is not a valid hash, or the advisory ``path`` escapes
            ``root``.
    """
    _require(isinstance(payload, dict), "sidecar must be a JSON object")
    asset_id = payload.get("asset_id")
    _require(
        isinstance(asset_id, str) and bool(asset_id),
        "sidecar asset_id must be a non-empty string",
    )
    _safe_asset_id(asset_id)
    name = payload.get("name")
    _require(
        isinstance(name, str) and bool(name),
        "sidecar name must be a non-empty string",
    )
    content_hash_value = payload.get("content_hash")
    _require(
        is_valid_hash(content_hash_value),
        "sidecar content_hash must be a valid hex hash",
    )
    kind = _parse_kind(payload.get("kind"))
    tags = _parse_tags(payload.get("tags", []))
    metadata = _parse_metadata(payload.get("metadata", {}))
    path_value = payload.get("path")
    if path_value is not None:
        _require(isinstance(path_value, str), "sidecar path must be a string or null")
        # Defend the advisory path: it must resolve within the catalog root.
        _resolve_within(root, path_value)
    try:
        return AssetDescriptor(
            asset_id=asset_id,
            kind=kind,
            name=name,
            content_hash=content_hash_value,
            tags=frozenset(tags),
            metadata=metadata,
            path=path_value,
        )
    except AssetCatalogModelError as exc:  # bounds / scalar-type defence
        raise AssetCatalogError(f"invalid asset descriptor: {exc}") from exc


# --------------------------------------------------------------------------- #
# Catalog persistence                                                          #
# --------------------------------------------------------------------------- #


def save_catalog(catalog: AssetCatalog, root: Union[str, Path]) -> None:
    """Persist ``catalog`` under ``root`` as an index + per-asset sidecars.

    Writes ``<root>/catalog.json`` (the index) and one
    ``<root>/assets/<asset_id>.json`` sidecar per entry (created on demand).

    Raises:
        AssetCatalogError: If ``catalog`` is not an :class:`AssetCatalog`, an
            ``asset_id`` is not a safe filename, or the files cannot be written.
    """
    if not isinstance(catalog, AssetCatalog):
        raise AssetCatalogError(f"expected an AssetCatalog, got {catalog!r}")
    root_path = Path(root)
    assets_dir = root_path / ASSETS_DIRNAME
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AssetCatalogError(
            f"cannot create catalog root {str(root)!r}: {exc}"
        ) from exc

    asset_ids: List[str] = []
    for descriptor in catalog.entries():
        safe_id = _safe_asset_id(descriptor.asset_id)
        sidecar = _serialise_descriptor(descriptor)
        sidecar_path = assets_dir / f"{safe_id}.json"
        try:
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
        except OSError as exc:
            raise AssetCatalogError(
                f"cannot write sidecar for {descriptor.asset_id!r}: {exc}"
            ) from exc
        asset_ids.append(descriptor.asset_id)

    index = {
        "format": FORMAT_NAME,
        "schema_version": CATALOG_SCHEMA_VERSION,
        "asset_ids": asset_ids,
    }
    try:
        (root_path / INDEX_FILENAME).write_text(json.dumps(index), encoding="utf-8")
    except OSError as exc:
        raise AssetCatalogError(f"cannot write catalog index: {exc}") from exc


def load_catalog(root: Union[str, Path]) -> AssetCatalog:
    """Load and validate the catalog persisted under ``root``.

    Raises:
        AssetCatalogError: If the index or any sidecar is missing, malformed, oversized,
            exceeds a cap, carries an invalid hash, or references a path escaping
            ``root``.
    """
    root_path = Path(root)
    index = _load_json(root_path / INDEX_FILENAME, "catalog index")
    _require(isinstance(index, dict), "catalog index must be a JSON object")
    _require(index.get("format") == FORMAT_NAME, "not a pixcatalog index")
    schema_version = index.get("schema_version")
    _require(
        isinstance(schema_version, str) and schema_version in SUPPORTED_SCHEMA_VERSIONS,
        f"unsupported catalog schema_version {schema_version!r}",
    )
    asset_ids = index.get("asset_ids")
    _require(isinstance(asset_ids, list), "catalog asset_ids must be a list")
    _require(
        len(asset_ids) <= MAX_CATALOG_ASSETS,
        f"catalog exceeds MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS})",
    )

    assets_dir = root_path / ASSETS_DIRNAME
    descriptors: List[AssetDescriptor] = []
    for asset_id in asset_ids:
        _require(
            isinstance(asset_id, str) and bool(asset_id),
            "each asset_id must be a non-empty string",
        )
        safe_id = _safe_asset_id(asset_id)
        sidecar_path = _resolve_within(assets_dir, f"{safe_id}.json")
        payload = _load_json(sidecar_path, f"sidecar for {asset_id!r}")
        descriptors.append(_parse_descriptor(payload, root_path))

    try:
        return AssetCatalog(descriptors=tuple(descriptors))
    except AssetCatalogModelError as exc:  # duplicate id / count defence
        raise AssetCatalogError(f"invalid catalog: {exc}") from exc


def _load_json(path: Path, what: str) -> Any:
    """Read + JSON-parse ``path`` defensively (never eval/exec), else raise."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssetCatalogError(f"cannot read {what}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssetCatalogError(f"{what} is not valid JSON: {exc}") from exc


# --------------------------------------------------------------------------- #
# Asset payload composition (PIO-1 + CAS) — no new serialiser                  #
# --------------------------------------------------------------------------- #


def store_asset(
    document: Document,
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
    *,
    asset_id: str,
    kind: AssetKind,
    name: str,
    tags: Sequence[str] = (),
    metadata: Optional[Mapping[str, object]] = None,
    path: Optional[str] = None,
) -> Tuple[AssetCatalog, AssetDescriptor]:
    """Store ``document``'s PIO-1 bytes in the CAS and catalog its descriptor.

    Stores the payload bytes in the content-addressable store and adds the resulting
    descriptor to ``catalog``. Composes ``data/project_io`` (PIO-1) for the payload
    — the canonical bytes are the PIO-1 serialisation encoded by
    :func:`canonical_json_bytes` — and adds no second serialiser (REQ-P11-DATA-007).
    The bytes are stored once (dedup) and addressed by their content hash, which
    becomes the descriptor's ``content_hash``.

    Returns:
        A ``(new_catalog, descriptor)`` tuple (the catalog is a new value; the input is
        unchanged).

    Raises:
        AssetCatalogError: If the descriptor is invalid or the ``asset_id`` collides.
        ProjectIOError: If ``document`` cannot be serialised by PIO-1.
        CasError: If the payload exceeds :data:`MAX_BLOB_BYTES`.
    """
    payload = project_io.serialize(document)
    blob = canonical_json_bytes(payload)
    digest = cas.put(blob)
    try:
        descriptor = AssetDescriptor(
            asset_id=asset_id,
            kind=kind,
            name=name,
            content_hash=digest,
            tags=frozenset(tags),
            metadata=metadata if metadata is not None else {},
            path=path,
        )
        new_catalog = catalog.add(descriptor)
    except AssetCatalogModelError as exc:
        raise AssetCatalogError(f"cannot store asset {asset_id!r}: {exc}") from exc
    return new_catalog, descriptor


def load_asset(descriptor: AssetDescriptor, cas: ContentAddressableStore) -> Document:
    """Reconstruct the PIO-1 :class:`Document` an asset descriptor references.

    Fetches the descriptor's content-hash-verified bytes from the CAS and reconstructs
    an
    *equivalent* entity via PIO-1
    :func:`~pixelart_creator.data.project_io.deserialize` (no second serialiser).

    Raises:
        CasError: If the blob is absent or its content hash mismatches (tamper defence).
        AssetCatalogError: If the fetched bytes are not decodable JSON.
        ProjectIOError: If the decoded payload is not a valid ``.pixproj`` document.
    """
    if not isinstance(descriptor, AssetDescriptor):
        raise AssetCatalogError(f"expected an AssetDescriptor, got {descriptor!r}")
    blob = cas.get(descriptor.content_hash)
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssetCatalogError(
            f"asset {descriptor.asset_id!r} payload is not valid JSON: {exc}"
        ) from exc
    return project_io.deserialize(payload)
