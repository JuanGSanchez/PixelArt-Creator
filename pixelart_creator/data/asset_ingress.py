# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The atomic asset-ingress boundary — defensive, zero Qt (S11; REQ-P11-DATA-009).

The single write path through which content becomes a catalog entry
(``register``), an untrusted external artifact becomes catalog entries
(``import_artifact``), or a chosen set of catalog entries leaves the library
as a self-contained artifact (``export_subset``). This module is the
``data/`` half of a deliberate determinism split: it produces the
canonical asset **bytes** with the shipped serialiser
(:func:`~pixelart_creator.data.project_io.serialize` +
:func:`~pixelart_creator.logic.content_hash.canonical_json_bytes` — no second
serialiser, parent REQ-P11-DATA-007) and derives every descriptor **through**
:func:`~pixelart_creator.logic.asset_extract.descriptor_for` (T2) — this
module never re-implements descriptor validation.

**The atomic order (ruling P11-R1, plan §3.3) — followed exactly:**

1. **Validate everything first**, purely, in memory: the descriptor (bounds,
   kind, tags, metadata — via ``descriptor_for``) and the catalog addition
   (identity, count — via
   :meth:`~pixelart_creator.logic.asset_catalog.AssetCatalog.add`). A
   rejection here has written nothing.
2. **Observe**
   :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.has` — a
   dedup *observation*, not a rollback guard.
3. **Write the blob** —
   :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.put`,
   itself a dedup no-op on an existing hash.
4. **Commit the catalog last** —
   :func:`~pixelart_creator.data.asset_catalog_io.save_catalog`, whose index
   write is the single commit point (``data/asset_catalog_io.py:274``).
5. **On any failure at or after step 3, nothing is removed.** No removal API
   exists anywhere on the CAS/blob stack and none is added here. A blob left
   by a failed run is invisible to every surface (the catalog index is the
   only enumerator), bounded at ``MAX_BLOB_BYTES``, and reclaimed for free
   when the same ingress is retried (``put`` dedups by content hash).

**The invariant this guarantees, and the one it does not.** *No catalog
entry without its bytes* is absolute. *No bytes without a catalog entry* is
**not** guaranteed — an unreferenced blob is tolerated, bounded and
idempotently reclaimed on retry; a future mark-and-sweep over catalog +
revisions + reference sets is separate, deliberate work and is **not** built
here (plan §3.3).

**Untrusted-input defence (Article VII; REQ-P11-DATA-009).**
:func:`import_artifact`'s payload is a file chosen by the user from outside
the application: it is size-capped before it is even parsed, parsed with
:mod:`json` only (**never** ``eval``/``exec``/``pickle``), schema- and
type-checked, bounded by the named caps
(:data:`~pixelart_creator.logic.constants.MAX_BUNDLE_BYTES`,
:data:`~pixelart_creator.logic.constants.MAX_BUNDLE_ENTRIES`, plus the
descriptor's own :data:`~pixelart_creator.logic.constants.MAX_TAGS_PER_ASSET`
/ :data:`~pixelart_creator.logic.constants.MAX_TAG_BYTES` /
:data:`~pixelart_creator.logic.constants.MAX_METADATA_BYTES`), its recorded
content hash is re-verified against the bytes it actually decodes to, and
every advisory ``path`` it carries is resolved and confirmed to lie within
the library root (``resolve()`` + ``relative_to`` containment) before any
entry built from it is added to the catalog. A rejection at any of those
checks writes nothing — no catalog entry, no blob.

LAYER: data/ — zero Qt (S11). Imports only ``logic/`` (``asset_extract``,
``asset_catalog``, ``content_hash``, ``constants``, ``document``) and other
``data/`` leaves (``asset_catalog_io``, ``asset_cas``, ``project_io``) — no
``ui/`` import, ever. Enforced by ``main/scripts/check_layering.py``.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from pixelart_creator.data import project_io
from pixelart_creator.data.asset_cas import CasError, ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import AssetCatalogError, save_catalog
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_edges import AssetEdgesError, reference_bytes
from pixelart_creator.logic.asset_extract import (
    AssetExtractError,
    descriptor_for,
    hash_of,
)
from pixelart_creator.logic.constants import MAX_BUNDLE_BYTES, MAX_BUNDLE_ENTRIES
from pixelart_creator.logic.content_hash import (
    ContentHashError,
    canonical_json_bytes,
    is_valid_hash,
)
from pixelart_creator.logic.document import Document

__all__ = [
    "IngressError",
    "ARTIFACT_FORMAT_NAME",
    "ARTIFACT_SCHEMA_VERSION",
    "ARTIFACT_SUFFIX",
    "canonical_bytes",
    "register",
    "import_artifact",
    "export_subset",
]

#: The single-asset-artifact format marker — a module-local, format-intrinsic
#: string (ADR-0001 exemption, the PIO-1 ``FORMAT_NAME`` / bundle
#: ``BUNDLE_FORMAT_NAME`` precedent).
ARTIFACT_FORMAT_NAME = "pixassetartifact"

#: Artifact wire schema version — a module-local format-intrinsic string.
ARTIFACT_SCHEMA_VERSION = "1"

#: The single-asset-artifact file extension — the module that owns the
#: ``pixassetartifact`` format also owns its suffix, exactly as
#: ``BUNDLE_SUFFIX`` (:data:`~pixelart_creator.data.asset_export.BUNDLE_SUFFIX`,
#: ``.pixbundle``) sits in the module that owns the project-bundle format
#: (ruling P11-R5, plan §3.7). Distinct from ``BUNDLE_SUFFIX`` and from every
#: other format-intrinsic suffix in ``data/`` (``.pixproj``, ``.pixmacro``,
#: ``.pixboard``, ``.pixtimelapse``, ``.blob``) — checked, not assumed. No
#: ``ui/`` file may open-code this string; it imports this name instead.
ARTIFACT_SUFFIX = ".pixasset"

#: Schema versions this build can import.
_SUPPORTED_ARTIFACT_VERSIONS: Tuple[str, ...] = (ARTIFACT_SCHEMA_VERSION,)


class IngressError(ProjectIOError):
    """Raised when a registration/import/export at the ingress boundary fails.

    A single exception type for every failure this module's three entry
    points can raise (invalid arguments, a rejected untrusted artifact, a
    lower-layer failure from ``descriptor_for``, the catalog model, the CAS,
    or catalog persistence), so a caller has one type to catch. Every raise
    site leaves the catalog and the store exactly as they were before the
    call that raised (§ module docstring, order step 1/5).
    """


# --------------------------------------------------------------------------- #
# Shared defence                                                              #
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise IngressError(message)


def _resolve_within(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` under ``root`` and confirm containment, else raise.

    The same ``resolve()`` + ``relative_to`` containment defence as
    :mod:`~pixelart_creator.data.asset_catalog_io` (Article VII): an absolute
    ``candidate`` or one that escapes ``root`` raises :class:`IngressError`.
    """
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise IngressError(
            f"path {candidate!r} escapes the library root {str(root)!r}"
        ) from exc
    return resolved


def _parse_kind(value: Any) -> AssetKind:
    if not isinstance(value, str):
        raise IngressError(f"kind must be a string, got {value!r}")
    try:
        return AssetKind(value)
    except ValueError as exc:
        raise IngressError(f"unknown asset kind {value!r}") from exc


def _parse_tags(value: Any) -> Tuple[str, ...]:
    _require(isinstance(value, list), "tags must be a list")
    for tag in value:
        _require(isinstance(tag, str), "each tag must be a string")
    return tuple(value)


def _parse_metadata(value: Any) -> Mapping[str, object]:
    _require(isinstance(value, dict), "metadata must be an object")
    for key in value:
        _require(isinstance(key, str), "metadata keys must be strings")
    return value


def canonical_bytes(document: Document) -> bytes:
    """Return ``document``'s canonical asset bytes (ruling P11-R6, plan §3.8).

    The one public spelling of
    ``canonical_json_bytes(project_io.serialize(document))`` — the exact pair
    of calls :func:`register` uses to derive the bytes a catalog entry's
    ``content_hash`` is minted from. This is the single site in ``data/``
    that performs this pairing; a caller in ``logic/`` (which may not import
    ``data/``) or ``ui/`` (which must not re-implement a canonicalisation
    rule) calls this function instead of open-coding the two calls itself.
    Pure: no store, no root, no other I/O.

    Args:
        document: The in-app source to canonicalise.

    Returns:
        The canonical PIO-1 bytes, byte-identical to what :func:`register`
        would hash and store for the same ``document``.

    Raises:
        IngressError: If ``document`` cannot be serialised or canonically
            encoded — the same failure :func:`register`'s step 1 raises for.
    """
    try:
        payload = project_io.serialize(document)
        return canonical_json_bytes(payload)
    except (ProjectIOError, ContentHashError) as exc:
        raise IngressError(f"cannot serialise document: {exc}") from exc


#: The only kinds ``REQ-P11-LOGIC-010`` ever treats as a reference *target*
#: (a tileset points at a sprite; an animation at sprites; a tilemap at a
#: tileset) — ruling P11-R8, plan §3.10. Every other kind records ``""``.
_REFERENCE_TARGET_KINDS = (AssetKind.SPRITE, AssetKind.TILESET)


def _reference_key_for(document: Document, kind: AssetKind) -> str:
    """Return ``document``'s ``reference_key`` for ``kind``, degrading to ``""``.

    T8-B step 5 (ruling P11-R8, plan §3.10): computes
    ``content_hash(reference_bytes(document, kind))`` for the kinds that can
    **be** a reference target (``SPRITE``, ``TILESET``) and returns ``""``
    for every other kind. An **ambiguous** ``TILESET`` document — zero or
    more than one tileset — also degrades to ``""``:
    :func:`~pixelart_creator.logic.asset_edges.reference_bytes` raises
    :class:`~pixelart_creator.logic.asset_edges.AssetEdgesError` for that
    shape, and this function catches exactly that error and returns ``""``
    rather than propagating it — ambiguity degrades to "no edge", never a
    wrong edge, the same guard
    :func:`~pixelart_creator.logic.asset_edges.edges_for` already carries.
    """
    if kind not in _REFERENCE_TARGET_KINDS:
        return ""
    try:
        return hash_of(reference_bytes(document, kind))
    except AssetEdgesError:
        return ""


# --------------------------------------------------------------------------- #
# register — an in-app source (document / selection) becomes a catalog entry #
# --------------------------------------------------------------------------- #


def register(
    document: Document,
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
    root: Union[str, Path],
    *,
    name: str,
    kind: AssetKind,
    tags: Sequence[str] = (),
    metadata: Optional[Mapping[str, object]] = None,
    path: Optional[str] = None,
) -> Tuple[AssetCatalog, AssetDescriptor, bool]:
    """Register ``document`` as a new catalog entry (REQ-P11-DATA-009/-UI-012/-013).

    Mints a fresh ``asset_id`` (a UUID — the registration prompt hands back
    only display data: ``name``/``kind``/``tags``, never an identity, per the
    ``logic/asset_extract`` split), serialises ``document`` to its canonical
    PIO-1 bytes with the shipped serialiser, computes its ``reference_key``
    (T8-B, ruling P11-R8, plan §3.10 — ``""`` for a ``kind`` that is never a
    reference target, or an ambiguous ``TILESET``), derives the descriptor
    through :func:`~pixelart_creator.logic.asset_extract.descriptor_for`, and
    applies the atomic order of the module docstring exactly.

    Args:
        document: The in-app source to register (the active document, or a
            document built from the current selection — the caller's
            concern, not this function's).
        catalog: The catalog to add the new entry to.
        cas: The content-addressable store the canonical bytes are written to.
        root: The catalog root the commit is persisted under.
        name: The non-empty display name (already collected from the user).
        kind: The :class:`AssetKind` (already chosen by the user).
        tags: The initial tag set, if any.
        metadata: An optional JSON-scalar metadata bag (e.g. export settings,
            REQ-P11-UI-014).
        path: An optional advisory display/fallback path; when given, it must
            resolve within ``root``.

    Returns:
        A ``(new_catalog, descriptor, already_present)`` tuple: ``new_catalog``
        is a new value (``catalog`` is unchanged), ``descriptor`` is the
        minted entry, and ``already_present`` is the dedup observation —
        ``True`` when ``cas.has(descriptor.content_hash)`` was ``True``
        *before* this call wrote anything (order step 2), letting the caller
        report *"this content is already in the library"*.

    Raises:
        IngressError: If ``catalog``/``cas`` are the wrong type, ``path``
            escapes ``root``, ``document`` cannot be serialised, the
            descriptor or the catalog addition is invalid (name/kind/tag/
            metadata bounds, or the catalog is at
            :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`), the
            blob cannot be written, or the catalog cannot be committed. Every
            one of these leaves the catalog and the store unchanged — a
            failure reached only after step 3 (the blob write) may leave that
            blob unreferenced (order step 5); nothing else changes.
    """
    if not isinstance(catalog, AssetCatalog):
        raise IngressError(f"expected an AssetCatalog, got {catalog!r}")
    if not isinstance(cas, ContentAddressableStore):
        raise IngressError(f"expected a ContentAddressableStore, got {cas!r}")
    root_path = Path(root)
    if path is not None:
        _require(isinstance(path, str), "path must be a str or None")
        _resolve_within(root_path, path)

    # --- Step 1: validate everything first, purely, in memory. -------------
    blob = canonical_bytes(document)

    asset_id = str(uuid.uuid4())
    reference_key = _reference_key_for(document, kind)
    try:
        descriptor = descriptor_for(
            blob,
            asset_id=asset_id,
            name=name,
            kind=kind,
            tags=tags,
            metadata=metadata,
            path=path,
            reference_key=reference_key,
        )
    except AssetExtractError as exc:
        raise IngressError(f"cannot derive descriptor: {exc}") from exc

    try:
        new_catalog = catalog.add(descriptor)
    except AssetCatalogModelError as exc:
        raise IngressError(f"cannot add {asset_id!r} to the catalog: {exc}") from exc

    # --- Step 2: dedup observation, before anything is written. ------------
    already_present = cas.has(descriptor.content_hash)

    # --- Step 3: write the blob (dedup no-op if already_present). ----------
    try:
        cas.put(blob)
    except CasError as exc:
        raise IngressError(f"cannot store blob for {asset_id!r}: {exc}") from exc

    # --- Step 4: commit the catalog last — the index write is the commit. --
    try:
        save_catalog(new_catalog, root_path)
    except AssetCatalogError as exc:
        raise IngressError(f"cannot commit catalog for {asset_id!r}: {exc}") from exc

    return new_catalog, descriptor, already_present


# --------------------------------------------------------------------------- #
# import_artifact — an untrusted external artifact becomes catalog entries   #
# --------------------------------------------------------------------------- #


def _parse_artifact_manifest(artifact: bytes) -> List[Any]:
    """Return the artifact's ``entries`` list, defensively, else raise.

    Enforces the untrusted-input defence before any entry is inspected: a
    size cap on the raw bytes, ``json``-only parsing (never
    ``eval``/``exec``), the format marker, a supported ``schema_version``,
    and an entry-count cap.
    """
    if not isinstance(artifact, (bytes, bytearray)):
        raise IngressError(f"artifact must be bytes, got {type(artifact).__name__}")
    if len(artifact) > MAX_BUNDLE_BYTES:
        raise IngressError(
            f"artifact is {len(artifact)} bytes, exceeds MAX_BUNDLE_BYTES "
            f"({MAX_BUNDLE_BYTES})"
        )
    try:
        text = bytes(artifact).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IngressError(f"artifact is not valid UTF-8: {exc}") from exc
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngressError(f"artifact is not valid JSON: {exc}") from exc
    _require(isinstance(manifest, dict), "artifact manifest must be a JSON object")
    _require(manifest.get("format") == ARTIFACT_FORMAT_NAME, "not a pixassetartifact")
    schema_version = manifest.get("schema_version")
    _require(
        isinstance(schema_version, str)
        and schema_version in _SUPPORTED_ARTIFACT_VERSIONS,
        f"unsupported artifact schema_version {schema_version!r}",
    )
    entries = manifest.get("entries")
    _require(isinstance(entries, list), "artifact entries must be a list")
    _require(
        len(entries) <= MAX_BUNDLE_ENTRIES,
        f"artifact has {len(entries)} entries, exceeds MAX_BUNDLE_ENTRIES "
        f"({MAX_BUNDLE_ENTRIES})",
    )
    return entries


def _parse_artifact_entry(entry: Any, root: Path) -> Tuple[AssetDescriptor, bytes]:
    """Validate one artifact entry and return its ``(descriptor, blob)``.

    Re-encodes the entry's embedded PIO-1 payload through the shipped
    canonical encoder (never trusting the artifact's own byte layout),
    verifies the entry's *recorded* ``content_hash`` against the *actual*
    hash of those re-encoded bytes (tamper/mismatch defence), confirms any
    advisory ``path`` resolves within ``root``, and derives the final
    descriptor through :func:`~pixelart_creator.logic.asset_extract.descriptor_for`.
    Performs no I/O — purely validates and returns values.
    """
    _require(isinstance(entry, dict), "each artifact entry must be a JSON object")
    asset_id = entry.get("asset_id")
    _require(
        isinstance(asset_id, str) and bool(asset_id),
        "entry asset_id must be a non-empty string",
    )
    name = entry.get("name")
    _require(
        isinstance(name, str) and bool(name),
        "entry name must be a non-empty string",
    )
    recorded_hash = entry.get("content_hash")
    _require(
        is_valid_hash(recorded_hash),
        "entry content_hash must be a valid hex hash",
    )
    kind = _parse_kind(entry.get("kind"))
    tags = _parse_tags(entry.get("tags", []))
    metadata = _parse_metadata(entry.get("metadata", {}))
    path_value = entry.get("path")
    if path_value is not None:
        _require(isinstance(path_value, str), "entry path must be a string or null")
        _resolve_within(root, path_value)
    # T8-B, ruling P11-R8 (plan §3.10): additive and optional — an artifact
    # written before this field existed has no "reference_key" key at all,
    # and `.get(..., "")` reads that as "unknown" (no derived edge on
    # import), not a missing-field rejection. `ARTIFACT_SCHEMA_VERSION` is
    # NOT bumped for this change (measured reason: `_SUPPORTED_ARTIFACT_VERSIONS`
    # is a one-element tuple — see the module docstring).
    reference_key = entry.get("reference_key", "")
    _require(isinstance(reference_key, str), "entry reference_key must be a string")
    payload = entry.get("payload")
    _require(payload is not None, "entry payload is required")

    try:
        blob = canonical_json_bytes(payload)
    except ContentHashError as exc:
        raise IngressError(
            f"entry {asset_id!r} payload is not canonical-encodable: {exc}"
        ) from exc

    actual_hash = hash_of(blob)
    if actual_hash != recorded_hash:
        raise IngressError(
            f"entry {asset_id!r} recorded content_hash {recorded_hash!r} does not "
            f"match its actual bytes ({actual_hash!r})"
        )

    try:
        descriptor = descriptor_for(
            blob,
            asset_id=asset_id,
            name=name,
            kind=kind,
            tags=tags,
            metadata=metadata,
            path=path_value,
            reference_key=reference_key,
        )
    except AssetExtractError as exc:
        raise IngressError(f"cannot derive descriptor for {asset_id!r}: {exc}") from exc
    return descriptor, blob


def import_artifact(
    artifact: bytes,
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
    root: Union[str, Path],
) -> Tuple[AssetCatalog, Tuple[AssetDescriptor, ...]]:
    """Import an untrusted asset artifact, adding its entries to the catalog.

    ``artifact`` is treated as **untrusted input at the moment of ingress**
    (REQ-P11-DATA-009): it is size-capped, parsed with :mod:`json` only, and
    every entry is schema-, bound- and hash-validated **before** anything is
    written (order step 1). The artifact carries its own descriptor per
    entry (RP-5 — import never prompts), so no name/kind/tags are collected
    here.

    Args:
        artifact: The untrusted artifact bytes (as produced by
            :func:`export_subset`, or an equivalent file chosen from disk).
        catalog: The catalog the entries are added to.
        cas: The content-addressable store the entries' bytes are written to.
        root: The catalog root the commit is persisted under.

    Returns:
        A ``(new_catalog, descriptors)`` tuple: ``new_catalog`` is a new
        value carrying every imported entry, and ``descriptors`` is the
        imported entries in artifact order. Importing content whose bytes are
        already in the store adds catalog entries without writing a second
        copy (the CAS dedups by content hash).

    Raises:
        IngressError: If ``catalog``/``cas`` are the wrong type, the artifact
            is malformed, oversized, of an unsupported schema version, any
            entry violates a cap, carries a mismatched content hash, or a
            path that escapes ``root``, the catalog addition is invalid (a
            colliding id, or the catalog is at
            :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`), a
            blob cannot be written, or the catalog cannot be committed. A
            rejection during validation (before any blob is written) leaves
            the catalog and the store byte-for-byte unchanged; a failure
            after the first blob write may leave written blobs unreferenced
            (order step 5) but adds no catalog entry.
    """
    if not isinstance(catalog, AssetCatalog):
        raise IngressError(f"expected an AssetCatalog, got {catalog!r}")
    if not isinstance(cas, ContentAddressableStore):
        raise IngressError(f"expected a ContentAddressableStore, got {cas!r}")
    root_path = Path(root)

    # --- Step 1: validate everything first, purely, in memory. -------------
    raw_entries = _parse_artifact_manifest(artifact)
    pairs: List[Tuple[AssetDescriptor, bytes]] = []
    new_catalog = catalog
    for raw_entry in raw_entries:
        descriptor, blob = _parse_artifact_entry(raw_entry, root_path)
        try:
            new_catalog = new_catalog.add(descriptor)
        except AssetCatalogModelError as exc:
            raise IngressError(
                f"cannot add {descriptor.asset_id!r} to the catalog: {exc}"
            ) from exc
        pairs.append((descriptor, blob))

    # --- Steps 2-3: dedup observation, then write each blob. ---------------
    for descriptor, blob in pairs:
        cas.has(descriptor.content_hash)  # dedup observation (discarded per-entry)
        try:
            cas.put(blob)
        except CasError as exc:
            raise IngressError(
                f"cannot store blob for {descriptor.asset_id!r}: {exc}"
            ) from exc

    # --- Step 4: commit the catalog last, once, for the whole artifact. ----
    try:
        save_catalog(new_catalog, root_path)
    except AssetCatalogError as exc:
        raise IngressError(f"cannot commit imported catalog: {exc}") from exc

    return new_catalog, tuple(descriptor for descriptor, _ in pairs)


# --------------------------------------------------------------------------- #
# export_subset — chosen catalog entries leave as a self-contained artifact  #
# --------------------------------------------------------------------------- #


def _validate_asset_ids(asset_ids: Sequence[str]) -> List[str]:
    if isinstance(asset_ids, (str, bytes)):
        raise IngressError(
            f"asset_ids must be a sequence of ids, got {type(asset_ids).__name__}"
        )
    try:
        unique = sorted(set(asset_ids))
    except TypeError as exc:
        raise IngressError(f"asset_ids must be an iterable of str: {exc}") from exc
    _require(
        len(unique) <= MAX_BUNDLE_ENTRIES,
        f"{len(unique)} asset_ids exceeds MAX_BUNDLE_ENTRIES ({MAX_BUNDLE_ENTRIES})",
    )
    for asset_id in unique:
        _require(
            isinstance(asset_id, str) and bool(asset_id),
            f"each asset_id must be a non-empty str, got {asset_id!r}",
        )
    return unique


def export_subset(
    asset_ids: Sequence[str],
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
) -> bytes:
    """Export exactly ``asset_ids``' entries and blobs as a self-contained artifact.

    Resolves each id against ``catalog``, fetches its content-hash-verified
    bytes from ``cas``, and encodes the result — descriptor plus the
    embedded PIO-1 payload, per entry — with the shipped canonical encoder
    (REQ-P11-UI-016). The advisory ``path`` is dropped from every exported
    entry so the artifact is relocatable and self-contained (identity
    travels as ``asset_id`` + ``content_hash``, the same precedent as
    :func:`~pixelart_creator.data.asset_export.export_project_assets`).

    This function performs no write against ``catalog`` or ``cas``: it only
    reads them, so the atomic write order does not apply to it — the only
    obligation is that every id is validated to exist before any blob is
    fetched.

    Args:
        asset_ids: The catalog entries to export.
        catalog: The catalog the ids resolve against.
        cas: The store the entries' bytes are fetched from (content-hash-
            verified).

    Returns:
        The canonical, self-contained artifact bytes — importable by
        :func:`import_artifact`.

    Raises:
        IngressError: If ``catalog``/``cas`` are the wrong type, an id is not
            in the catalog, a referenced blob cannot be resolved (missing or
            tamper-mismatched), or a resolved payload is not valid JSON.
    """
    if not isinstance(catalog, AssetCatalog):
        raise IngressError(f"expected an AssetCatalog, got {catalog!r}")
    if not isinstance(cas, ContentAddressableStore):
        raise IngressError(f"expected a ContentAddressableStore, got {cas!r}")
    ids = _validate_asset_ids(asset_ids)

    entries: List[Dict[str, Any]] = []
    for asset_id in ids:
        descriptor = catalog.get(asset_id)
        if descriptor is None:
            raise IngressError(f"asset {asset_id!r} is not in the catalog")
        try:
            blob = cas.get(descriptor.content_hash)
        except CasError as exc:
            raise IngressError(f"cannot resolve blob for {asset_id!r}: {exc}") from exc
        try:
            payload = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IngressError(
                f"asset {asset_id!r} payload is not valid JSON: {exc}"
            ) from exc
        entries.append(
            {
                "asset_id": descriptor.asset_id,
                "kind": descriptor.kind.value,
                "name": descriptor.name,
                "content_hash": descriptor.content_hash,
                "tags": sorted(descriptor.tags),
                "metadata": dict(descriptor.metadata),
                "path": None,
                "payload": payload,
                # T8-B, ruling P11-R8 (plan §3.10): the round trip must
                # preserve the reference key, or every asset imported on the
                # far machine derives no edges — SC-P11-UI-016-2's "identical
                # content hashes" promise would be green and the feature dead.
                "reference_key": descriptor.reference_key,
            }
        )

    manifest = {
        "format": ARTIFACT_FORMAT_NAME,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "entries": entries,
    }
    return canonical_json_bytes(manifest)
