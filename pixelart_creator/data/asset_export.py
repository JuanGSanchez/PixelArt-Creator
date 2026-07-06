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

from pathlib import Path
from typing import List, Sequence, Union

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
from pixelart_creator.logic.constants import MAX_CATALOG_ASSETS

__all__ = [
    "AssetExportError",
    "BUNDLE_BLOBS_DIRNAME",
    "export_project_assets",
    "import_project_assets",
]

#: The sub-directory under the bundle root holding the referenced CAS blobs.
BUNDLE_BLOBS_DIRNAME = "blobs"


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
