# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Cross-project reuse export — reference-set bundling, defensive, zero Qt (S11).

Export the assets a project references into a **self-contained, portable artifact**
(REQ-P11-DATA-005; ADR-0030 §5). The reuse model is **reference-not-copy**: a project
holds ``(asset_id -> content_hash)`` references, and the shared bytes live once in the
content-addressable store (:mod:`~pixelart_creator.data.asset_cas`). Export **resolves
the reference set and bundles exactly the referenced CAS blobs** — no more, no fewer —
so the exported project opens self-contained on another machine.

The bundle is a directory artifact that **composes the shipped catalog IO**
(:mod:`~pixelart_creator.data.asset_catalog_io`) — a ``catalog.json`` index + per-asset
sidecars written by :func:`~pixelart_creator.data.asset_catalog_io.save_catalog` — plus
a ``blobs/`` sub-directory holding each referenced blob once, keyed by its content hash
through a :class:`~pixelart_creator.data.asset_cas.ContentAddressableStore`. Reusing the
shipped IO means the bundle inherits its whole **untrusted-input defence** on import
(Article VII; REQ-P11-DATA-005 acceptance "imported reference is
path-traversal-defended"):
:func:`~pixelart_creator.data.asset_catalog_io.load_catalog` parses with :mod:`json`
only (**never** ``eval``/``exec``), schema- and cap-validates, and
**path-traversal-defends** every path (``resolve()`` + containment).
:func:`import_project_assets` layers on the content-hash-verified blob fetch (tamper
defence) and its own ``resolve()`` + containment guard on the ``blobs/`` directory.

:class:`AssetExportError` subclasses
:class:`~pixelart_creator.data.project_io.ProjectIOError` (the PIO-1 family), so a
caller may catch either. Zero Qt; CI-testable headless with no network/credentials.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List, Sequence, Tuple, Union

from pixelart_creator.data import project_io
from pixelart_creator.data.asset_cas import CasError, ContentAddressableStore
from pixelart_creator.data.asset_catalog_io import (
    AssetCatalogError,
    load_catalog,
    save_catalog,
)
from pixelart_creator.data.asset_storage import LocalBlobBackend
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetCatalogModelError,
    AssetDescriptor,
)
from pixelart_creator.logic.constants import (
    MAX_BUNDLE_BYTES,
    MAX_BUNDLE_ENTRIES,
    MAX_BUNDLE_ENTRY_BYTES,
    MAX_CATALOG_ASSETS,
)
from pixelart_creator.logic.content_hash import canonical_json_bytes
from pixelart_creator.logic.document import Document

__all__ = [
    "AssetExportError",
    "BUNDLE_BLOBS_DIRNAME",
    "BUNDLE_SUFFIX",
    "BUNDLE_FORMAT_NAME",
    "BUNDLE_SCHEMA_VERSION",
    "BUNDLE_MANIFEST_FILENAME",
    "BUNDLE_PROJECT_FILENAME",
    "export_project_assets",
    "import_project_assets",
    "export_project_bundle",
    "import_project_bundle",
]

#: The sub-directory under the bundle root holding the referenced CAS blobs.
BUNDLE_BLOBS_DIRNAME = "blobs"

#: The file extension of a single-file portable bundle (ADR-0037 §1).
BUNDLE_SUFFIX = ".pixbundle"

#: The portable-bundle manifest format marker — a module-local, format-intrinsic
#: string (ADR-0001 exemption, the PIO-1 ``FORMAT_NAME`` / catalog ``FORMAT_NAME``
#: precedent; NOT a numeric tuning value for :mod:`~pixelart_creator.logic.constants`).
BUNDLE_FORMAT_NAME = "pixbundle"

#: Portable-bundle wire schema version — a module-local format-intrinsic string
#: (ADR-0037 §1 "a version tag is embedded so import can reject an unknown version").
BUNDLE_SCHEMA_VERSION = "1"

#: Schema versions this build can import.
_SUPPORTED_BUNDLE_VERSIONS: Tuple[str, ...] = (BUNDLE_SCHEMA_VERSION,)

#: The bundle manifest member (format marker + schema_version), at the archive root.
BUNDLE_MANIFEST_FILENAME = "manifest.json"

#: The embedded ``.pixproj`` project-payload member, at the archive root.
BUNDLE_PROJECT_FILENAME = "project.pixproj"

#: Fixed archive-member timestamp (the ZIP epoch floor) so the same project yields a
#: functionally-equivalent bundle across OSes (ADR-0037 §1 determinism).
#: Format-intrinsic metadata, not a numeric tuning value (ADR-0001 exemption).
_BUNDLE_MEMBER_DATE_TIME = (1980, 1, 1, 0, 0, 0)

#: Fixed archive-member external attributes (regular file, mode 0o644) — held constant
#: so member metadata does not vary by OS (ADR-0037 §1). Format-intrinsic (ADR-0001).
_BUNDLE_MEMBER_EXTERNAL_ATTR = 0o644 << 16

#: Streamed-extraction read granularity, bytes — an I/O chunk size (implementation
#: detail, not a domain tuning value): the per-member uncompressed byte count is
#: accumulated a chunk at a time so a lying header is caught mid-stream (ADR-0037 §2).
_BUNDLE_READ_CHUNK_BYTES = 65536


class AssetExportError(ProjectIOError):
    """Raised when a reference set cannot be exported or an import bundle is invalid."""


def _validate_reference_ids(reference_ids: Sequence[str]) -> List[str]:
    """Return the deduplicated, sorted reference ids, else raise.

    Deterministic (sorted) and cap-bounded (``<= MAX_CATALOG_ASSETS``) so a malformed
    or oversized reference set is rejected before any blob is resolved (Article VII).
    """
    if isinstance(reference_ids, (str, bytes)):
        raise AssetExportError(
            "reference_ids must be a sequence of ids, got "
            f"{type(reference_ids).__name__}"
        )
    try:
        unique = sorted(set(reference_ids))
    except TypeError as exc:
        raise AssetExportError(
            f"reference_ids must be an iterable of str: {exc}"
        ) from exc
    if len(unique) > MAX_CATALOG_ASSETS:
        raise AssetExportError(
            f"{len(unique)} references exceeds MAX_CATALOG_ASSETS "
            f"({MAX_CATALOG_ASSETS})"
        )
    for asset_id in unique:
        if not isinstance(asset_id, str) or not asset_id:
            raise AssetExportError(
                f"each reference id must be a non-empty str, got {asset_id!r}"
            )
    return unique


def _resolve_within(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` under ``root`` and confirm containment, else raise.

    The same ``resolve()`` + containment path-traversal defence as
    :mod:`~pixelart_creator.data.asset_catalog_io` (Article VII): an absolute or an
    escaping
    ``candidate`` is rejected.
    """
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise AssetExportError(
            f"path {candidate!r} escapes the export bundle root {str(root)!r}"
        ) from exc
    return resolved


def export_project_assets(
    reference_ids: Sequence[str],
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
    out: Union[str, Path],
) -> None:
    """Bundle exactly the blobs a project's references resolve to into ``out``.

    Resolves each id in ``reference_ids`` against ``catalog``, fetches its
    content-hash-verified bytes from ``cas``, and writes a self-contained bundle under
    ``out``: a ``catalog.json`` index + per-asset sidecars (via the shipped
    :func:`~pixelart_creator.data.asset_catalog_io.save_catalog`) and a ``blobs/``
    directory holding **exactly** the referenced blobs, each stored once (dedup). The
    advisory ``path`` field is dropped from the bundled descriptors so the artifact
    is relocatable and self-contained (identity is by ``asset_id`` + ``content_hash``).

    Raises:
        AssetExportError: If ``catalog``/``cas`` are the wrong type, a reference id is
            not in the catalog, a referenced blob cannot be resolved, or the bundle
            cannot be written.
    """
    if not isinstance(catalog, AssetCatalog):
        raise AssetExportError(f"expected an AssetCatalog, got {catalog!r}")
    if not isinstance(cas, ContentAddressableStore):
        raise AssetExportError(f"expected a ContentAddressableStore, got {cas!r}")
    ids = _validate_reference_ids(reference_ids)

    bundled: List[AssetDescriptor] = []
    for asset_id in ids:
        descriptor = catalog.get(asset_id)
        if descriptor is None:
            raise AssetExportError(f"reference {asset_id!r} is not in the catalog")
        # Relocate: drop the advisory path so the bundle is self-contained.
        try:
            bundled.append(
                AssetDescriptor(
                    asset_id=descriptor.asset_id,
                    kind=descriptor.kind,
                    name=descriptor.name,
                    content_hash=descriptor.content_hash,
                    tags=descriptor.tags,
                    metadata=descriptor.metadata,
                    path=None,
                )
            )
        except AssetCatalogModelError as exc:  # pragma: no cover - defensive
            raise AssetExportError(
                f"invalid descriptor for {asset_id!r}: {exc}"
            ) from exc

    try:
        sub_catalog = AssetCatalog(descriptors=tuple(bundled))
    except AssetCatalogModelError as exc:
        raise AssetExportError(f"cannot build export catalog: {exc}") from exc

    out_path = Path(out)
    try:
        out_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AssetExportError(
            f"cannot create export root {str(out)!r}: {exc}"
        ) from exc

    blobs_root = _resolve_within(out_path, BUNDLE_BLOBS_DIRNAME)
    bundle_cas = ContentAddressableStore(LocalBlobBackend(root=blobs_root))
    for descriptor in bundled:
        try:
            blob = cas.get(descriptor.content_hash)
        except CasError as exc:
            raise AssetExportError(
                f"cannot resolve blob for {descriptor.asset_id!r}: {exc}"
            ) from exc
        bundle_cas.put(blob)

    try:
        save_catalog(sub_catalog, out_path)
    except AssetCatalogError as exc:
        raise AssetExportError(f"cannot write export catalog: {exc}") from exc


def import_project_assets(
    bundle: Union[str, Path],
    cas: ContentAddressableStore,
) -> AssetCatalog:
    """Open an export bundle self-contained, importing its blobs into ``cas``.

    Loads the bundle's catalog through the shipped defensive
    :func:`~pixelart_creator.data.asset_catalog_io.load_catalog` (schema + caps +
    path-traversal defence + no ``eval``/``exec``), then fetches each referenced blob
    from the bundle's ``blobs/`` directory **content-hash-verified** and stores it
    into the target ``cas`` (dedup). Returns the reconstructed catalog.

    Raises:
        AssetExportError: If ``cas`` is the wrong type, the bundle is malformed /
            escapes its root / violates a cap, or a bundled blob is missing or fails
            hash verification.
    """
    if not isinstance(cas, ContentAddressableStore):
        raise AssetExportError(f"expected a ContentAddressableStore, got {cas!r}")
    bundle_path = Path(bundle)
    try:
        catalog = load_catalog(bundle_path)
    except AssetCatalogError as exc:
        raise AssetExportError(f"cannot open export bundle: {exc}") from exc

    blobs_root = _resolve_within(bundle_path, BUNDLE_BLOBS_DIRNAME)
    bundle_cas = ContentAddressableStore(LocalBlobBackend(root=blobs_root))
    for descriptor in catalog.entries():
        try:
            blob = bundle_cas.get(descriptor.content_hash)
        except CasError as exc:
            raise AssetExportError(
                f"export bundle missing/invalid blob for {descriptor.asset_id!r}: {exc}"
            ) from exc
        cas.put(blob)
    return catalog


# --------------------------------------------------------------------------- #
# Single-file portable bundle (.pixbundle) — deterministic zip, defensive      #
# (Slice 13B; ADR-0037; REQ-P13-DATA-006/-007/-008)                            #
# --------------------------------------------------------------------------- #


def _serialise_project_payload(document: Document) -> bytes:
    """Return the PIO-1 ``.pixproj`` payload bytes for ``document`` (deterministic).

    Composes the shipped PIO-1 serialiser
    (:func:`~pixelart_creator.data.project_io.serialize`) and the shipped canonical
    encoder (:func:`~pixelart_creator.logic.content_hash.canonical_json_bytes`) — the
    same "canonical PIO-1 bytes" pairing
    :func:`~pixelart_creator.data.asset_catalog_io.store_asset` uses. No second
    serialiser is introduced (Article I); the bytes are stable across sessions/OSes so
    the same project yields a functionally-equivalent bundle (ADR-0037 §1).

    Raises:
        AssetExportError: If ``document`` is not a :class:`Document` or cannot be
            serialised.
    """
    if not isinstance(document, Document):
        raise AssetExportError(f"expected a Document, got {document!r}")
    try:
        payload = project_io.serialize(document)
        return canonical_json_bytes(payload)
    except (ProjectIOError, ValueError) as exc:  # normalise to the export family
        raise AssetExportError(f"cannot serialise project payload: {exc}") from exc


def _write_deterministic_zip(source_root: Path, out_path: Path) -> None:
    """Zip every file under ``source_root`` into ``out_path`` deterministically.

    Members are written ``ZIP_DEFLATED`` with **POSIX forward-slash** internal paths
    (never OS backslashes), in a stable sorted order, with fixed member metadata
    (constant timestamp + mode) so the archive is functionally equivalent across OSes
    (ADR-0037 §1). Directory records are omitted (import recreates parents), keeping the
    archive minimal.
    """
    files = sorted(p for p in source_root.rglob("*") if p.is_file())
    try:
        with zipfile.ZipFile(
            out_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for file_path in files:
                arcname = file_path.relative_to(source_root).as_posix()
                info = zipfile.ZipInfo(
                    filename=arcname, date_time=_BUNDLE_MEMBER_DATE_TIME
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = _BUNDLE_MEMBER_EXTERNAL_ATTR
                archive.writestr(info, file_path.read_bytes())
    except OSError as exc:
        raise AssetExportError(f"cannot write bundle {str(out_path)!r}: {exc}") from exc


def export_project_bundle(
    document: Document,
    reference_ids: Sequence[str],
    catalog: AssetCatalog,
    cas: ContentAddressableStore,
    out: Union[str, Path],
) -> Path:
    """Export a project + every referenced asset into one portable ``.pixbundle`` file.

    Produces a **single, self-contained, deterministic** stdlib ``zipfile`` archive
    (``ZIP_DEFLATED``; ADR-0037 §1) embedding, under **POSIX forward-slash** internal
    paths with fixed member metadata:

    * ``manifest.json`` — the bundle format marker + embedded ``schema_version``;
    * ``project.pixproj`` — the PIO-1 project payload (the shipped serialiser output,
      canonical-encoded — no second serialiser, Article I);
    * ``catalog.json`` + ``assets/<asset_id>.json`` sidecars + ``blobs/`` — **every**
      CAS blob the project references, resolved and written by the shipped
      :func:`export_project_assets` reference-set resolution (no re-implemented CAS
      logic, Article I), each blob stored once keyed by its content hash.

    The archive therefore carries everything needed to reconstruct the project on
    another machine with no external file dependency (REQ-P13-DATA-006). Zero Qt.

    Args:
        document: The project whose PIO-1 payload is embedded.
        reference_ids: The asset ids the project references (resolved against
            ``catalog`` → their CAS blobs are bundled).
        catalog: The catalog the references resolve against.
        cas: The store the referenced blobs are fetched from (content-hash-verified).
        out: The destination path; a non-``.pixbundle`` suffix is replaced.

    Returns:
        The path the bundle was written to.

    Raises:
        AssetExportError: If ``document``/``catalog``/``cas`` are the wrong type, a
            reference is missing, a blob cannot be resolved, or the bundle cannot be
            written.
    """
    payload_bytes = _serialise_project_payload(document)
    manifest_bytes = canonical_json_bytes(
        {"format": BUNDLE_FORMAT_NAME, "schema_version": BUNDLE_SCHEMA_VERSION}
    )

    out_path = Path(out)
    if out_path.suffix != BUNDLE_SUFFIX:
        out_path = out_path.with_suffix(BUNDLE_SUFFIX)

    staging = Path(tempfile.mkdtemp(prefix="pixbundle-export-"))
    try:
        # Reuse the shipped directory-bundle exporter for catalog + sidecars + blobs.
        export_project_assets(reference_ids, catalog, cas, staging)
        (staging / BUNDLE_PROJECT_FILENAME).write_bytes(payload_bytes)
        (staging / BUNDLE_MANIFEST_FILENAME).write_bytes(manifest_bytes)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise AssetExportError(
                f"cannot create bundle parent {str(out_path.parent)!r}: {exc}"
            ) from exc
        _write_deterministic_zip(staging, out_path)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return out_path


def _safe_member_relpath(name: str, extract_root: Path) -> Path:
    """Return the contained destination path for archive member ``name``, else raise.

    The zip-slip / path-traversal defence (Article VII; ADR-0037 §2): a member name is
    rejected if it is absolute, carries a Windows drive, contains a backslash, or has
    any ``..`` component; the result is then ``resolve()``d and confirmed to stay within
    ``extract_root`` (belt-and-braces containment). No symlink is ever created — members
    are always written as regular files — so a symlink-escape entry cannot redirect a
    write outside the target.
    """
    if not isinstance(name, str) or not name:
        raise AssetExportError(
            f"bundle member name must be a non-empty str, got {name!r}"
        )
    if "\\" in name or name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
        raise AssetExportError(f"bundle member {name!r} is not a safe relative path")
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise AssetExportError(
            f"bundle member {name!r} contains an unsafe path segment"
        )
    root_resolved = extract_root.resolve()
    resolved = (root_resolved / name).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise AssetExportError(
            f"bundle member {name!r} escapes the import target"
        ) from exc
    return resolved


def _extract_member_streamed(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, dest: Path
) -> None:
    """Stream one archive member to ``dest``, enforcing the per-entry uncompressed cap.

    The bytes are copied a chunk at a time and the running decompressed size is compared
    to :data:`MAX_BUNDLE_ENTRY_BYTES` on every chunk, so a member whose header
    under-reports its size (a zip bomb) is aborted mid-stream before it can exhaust
    memory/disk (ADR-0037 §2 — "enforced during streamed extraction so a lying header
    cannot exhaust memory/disk"). ``zipfile.extractall`` is deliberately **not** used.
    """
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with archive.open(info, mode="r") as source, open(dest, "wb") as target:
            while True:
                chunk = source.read(_BUNDLE_READ_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_BUNDLE_ENTRY_BYTES:
                    raise AssetExportError(
                        f"bundle member {info.filename!r} exceeds "
                        f"MAX_BUNDLE_ENTRY_BYTES ({MAX_BUNDLE_ENTRY_BYTES}) "
                        "during extraction"
                    )
                target.write(chunk)
    except (OSError, zipfile.BadZipFile, EOFError) as exc:
        raise AssetExportError(
            f"cannot extract bundle member {info.filename!r}: {exc}"
        ) from exc


def _load_bundle_manifest(manifest_path: Path) -> None:
    """Parse + validate the bundle manifest (json only; never eval/exec), else raise.

    Confirms the format marker and that the embedded ``schema_version`` is one this
    build supports (ADR-0037 §1) — an unknown version is rejected with
    :class:`AssetExportError`.
    """
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssetExportError(f"cannot read bundle manifest: {exc}") from exc
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssetExportError(f"bundle manifest is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise AssetExportError("bundle manifest must be a JSON object")
    if manifest.get("format") != BUNDLE_FORMAT_NAME:
        raise AssetExportError("not a pixbundle manifest")
    schema_version = manifest.get("schema_version")
    if (
        not isinstance(schema_version, str)
        or schema_version not in _SUPPORTED_BUNDLE_VERSIONS
    ):
        raise AssetExportError(f"unsupported bundle schema_version {schema_version!r}")


def _reconstruct_project(project_path: Path) -> Document:
    """Read + json-parse (never eval/exec) the embedded ``.pixproj`` into a Document.

    Reuses the shipped defensive PIO-1 deserialiser
    (:func:`~pixelart_creator.data.project_io.deserialize`); a malformed payload raises
    :class:`AssetExportError` (the PIO-1 family).
    """
    try:
        text = project_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssetExportError(f"cannot read bundle project payload: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssetExportError(
            f"bundle project payload is not valid JSON: {exc}"
        ) from exc
    try:
        return project_io.deserialize(payload)
    except ProjectIOError as exc:
        raise AssetExportError(f"bundle project payload is invalid: {exc}") from exc


def import_project_bundle(
    bundle: Union[str, Path],
    cas: ContentAddressableStore,
    target_dir: Union[str, Path],
) -> Tuple[Document, AssetCatalog]:
    """Import an untrusted ``.pixbundle``, reconstructing the project + its assets.

    Treats the ``.pixbundle`` as **fully untrusted** (Article VII; ADR-0037 §2) and
    never writes into ``target_dir`` until every check has passed:

    * **Size / count caps.** The archive file size ≤ :data:`MAX_BUNDLE_BYTES`; the
      member count ≤ :data:`MAX_BUNDLE_ENTRIES`; each member's header uncompressed size
      ≤ :data:`MAX_BUNDLE_ENTRY_BYTES` — **and** the same per-member cap is re-enforced
      during streamed extraction so a lying header cannot exhaust memory/disk.
    * **Path-traversal / zip-slip containment.** Every member name is rejected if
      absolute / drive-qualified / backslashed / ``..``-bearing and its resolved
      destination is confirmed within a scratch dir; members are written only as regular
      files (no symlink is created), so no write can escape the target.
    * **Extract to scratch + atomic move.** Members are extracted to a private scratch
      directory (a sibling of ``target_dir`` for a same-filesystem move); ``target_dir``
      is created by an atomic :func:`os.replace` **only after** the whole bundle
      validates — so a rejected bundle leaves **nothing** partial at the target.
    * **json-only parse.** The manifest and the ``.pixproj`` payload are parsed with
      :mod:`json` only (**never** ``eval``/``exec``); the catalog + blobs are loaded via
      the shipped defensive :func:`import_project_assets`, which content-hash-verifies
      each blob (tamper defence) and path-traversal-defends the catalog.

    Args:
        bundle: The ``.pixbundle`` file to import (untrusted).
        cas: The store the embedded (content-hash-verified) blobs are imported into.
        target_dir: The directory the validated bundle contents are atomically moved to;
            it must not already exist.

    Returns:
        A ``(document, catalog)`` tuple — the reconstructed project and its catalog.

    Raises:
        AssetExportError: If ``cas`` is the wrong type, ``target_dir`` already exists,
            the bundle is malformed / oversized / unknown-version, a member escapes the
            target (traversal / zip-slip), or a blob fails hash verification. No
            partial-valid project is left at ``target_dir`` on any failure.
    """
    if not isinstance(cas, ContentAddressableStore):
        raise AssetExportError(f"expected a ContentAddressableStore, got {cas!r}")
    bundle_path = Path(bundle)
    target_path = Path(target_dir)
    if target_path.exists():
        raise AssetExportError(
            f"import target {str(target_dir)!r} already exists; refusing to overwrite"
        )

    try:
        total_bytes = bundle_path.stat().st_size
    except OSError as exc:
        raise AssetExportError(f"cannot open bundle {str(bundle)!r}: {exc}") from exc
    if total_bytes > MAX_BUNDLE_BYTES:
        raise AssetExportError(
            f"bundle is {total_bytes} bytes, exceeds MAX_BUNDLE_BYTES "
            f"({MAX_BUNDLE_BYTES})"
        )

    try:
        target_parent = target_path.resolve().parent
        target_parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AssetExportError(f"cannot prepare import target parent: {exc}") from exc

    scratch = Path(tempfile.mkdtemp(prefix="pixbundle-import-", dir=target_parent))
    try:
        try:
            archive = zipfile.ZipFile(bundle_path, mode="r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise AssetExportError(f"bundle is not a valid archive: {exc}") from exc
        with archive:
            infos = archive.infolist()
            if len(infos) > MAX_BUNDLE_ENTRIES:
                raise AssetExportError(
                    f"bundle has {len(infos)} entries, exceeds MAX_BUNDLE_ENTRIES "
                    f"({MAX_BUNDLE_ENTRIES})"
                )
            for info in infos:
                if info.is_dir():
                    continue
                if info.file_size > MAX_BUNDLE_ENTRY_BYTES:
                    raise AssetExportError(
                        f"bundle member {info.filename!r} declares {info.file_size} "
                        f"bytes, exceeds MAX_BUNDLE_ENTRY_BYTES "
                        f"({MAX_BUNDLE_ENTRY_BYTES})"
                    )
                dest = _safe_member_relpath(info.filename, scratch)
                _extract_member_streamed(archive, info, dest)

        _load_bundle_manifest(scratch / BUNDLE_MANIFEST_FILENAME)
        document = _reconstruct_project(scratch / BUNDLE_PROJECT_FILENAME)
        # Content-hash-verify + import every referenced blob via the shipped defence.
        catalog = import_project_assets(scratch, cas)

        try:
            os.replace(scratch, target_path)
        except OSError as exc:
            raise AssetExportError(
                f"cannot finalise import into {str(target_dir)!r}: {exc}"
            ) from exc
        return document, catalog
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
