"""Pure derivation of an asset's content hash and descriptor (REQ-P11-LOGIC-009).

This module is the ``logic/`` half of the determinism split recorded at
``design-docs/specs/phase-11-asset-ingress/plan.md`` §3.2: turning an in-app
source into an asset's **content hash and descriptor** is a pure, Qt-free,
deterministic computation — the same canonical bytes always yield the same
hash and (given the same caller-supplied choices) the same descriptor, with
no dependence on wall-clock, randomness, locale or filesystem state, and no
I/O. It deliberately does **not** own the canonical **bytes**: the canonical
serialiser lives in ``data/`` (``data/project_io`` via
``data/asset_catalog_io.store_asset``), and this module, being ``logic/``,
may not import ``data/`` (Article I §3). Callers — today, ``data/`` ingress
code — produce the canonical bytes first and pass them in; this module never
mints a second serialiser (parent REQ-P11-DATA-007).

This module also never mints an ``asset_id``: a stable identity is an
external decision (the caller's, or a UUID minted by the caller) and minting
one here would make ``descriptor_for`` depend on randomness, which the
requirement explicitly forbids. The caller supplies ``asset_id`` alongside
the display name, kind and tags it already collects (the registration
prompt, RP-1 in ``spec.md``).

LAYER: logic/ — pure Python, ZERO Qt (S11). Enforced by
``main/scripts/check_layering.py``; the only Qt-dependent file outside
``ui/`` is ``ui/commands.py``.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from pixelart_creator.logic.asset_catalog import (
    AssetCatalogModelError,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.content_hash import ContentHashError, content_hash

__all__ = [
    "AssetExtractError",
    "hash_of",
    "descriptor_for",
]


class AssetExtractError(ValueError):
    """Base for every error this module raises.

    A module-specific base lets a caller catch this module's failures
    without catching everything, which is what makes the exception surface
    part of the public contract rather than an implementation leak. Wraps
    the lower-layer errors this module's two functions can surface
    (:class:`~pixelart_creator.logic.content_hash.ContentHashError`,
    :class:`~pixelart_creator.logic.asset_catalog.AssetCatalogModelError`)
    so a caller of this module has one exception type to catch.
    """


def hash_of(blob: bytes) -> str:
    """Return the deterministic content hash of ``blob``.

    A thin, named wrapper over the shipped
    :func:`~pixelart_creator.logic.content_hash.content_hash` — the single
    hashing primitive this module (and every other content-hash consumer)
    goes through, so there is exactly one hash computation in the codebase.

    Args:
        blob: The canonical asset bytes to hash (already produced by the
            shipped ``data/`` serialiser — this function performs no
            serialisation of its own).

    Returns:
        A 64-character lowercase hex SHA-256 digest, stable across
        sessions and platforms for byte-identical input.

    Raises:
        AssetExtractError: If ``blob`` is not ``bytes``/``bytearray``.
    """
    try:
        return content_hash(blob)
    except ContentHashError as exc:
        raise AssetExtractError(f"cannot hash blob: {exc}") from exc


def descriptor_for(
    blob: bytes,
    *,
    asset_id: str,
    name: str,
    kind: AssetKind,
    tags: Sequence[str] = (),
    metadata: Optional[Mapping[str, object]] = None,
    path: Optional[str] = None,
    reference_key: str = "",
) -> AssetDescriptor:
    """Return the :class:`AssetDescriptor` for ``blob``, purely over values.

    Derives the descriptor's ``content_hash`` from ``blob`` via
    :func:`hash_of` and combines it with the caller-supplied identity and
    choices (``asset_id``, ``name``, ``kind``, ``tags``, ``metadata``,
    ``path`` — the registration prompt's RP-1 collection, or an importer's
    already-known descriptor fields) into a frozen, validated
    :class:`AssetDescriptor`. Bytes in, descriptor out: no I/O, no Qt, no
    wall-clock, no randomness, no locale dependence — the same arguments
    always produce the same descriptor.

    ``kind`` must be one of the five shipped :class:`AssetKind` values; the
    tag set is bounded by ``MAX_TAGS_PER_ASSET`` / ``MAX_TAG_BYTES`` and the
    metadata bag by ``MAX_METADATA_BYTES`` — all enforced by
    :class:`AssetDescriptor` itself (:mod:`pixelart_creator.logic.constants`,
    S12), so this function does not duplicate those bounds; it only adapts
    the failure into this module's exception type.

    Args:
        blob: The canonical asset bytes (already produced by the shipped
            ``data/`` serialiser) the descriptor's ``content_hash`` is
            derived from.
        asset_id: The stable identity to record (never minted here — see
            the module docstring).
        name: The non-empty display name.
        kind: The :class:`AssetKind` of the entity ``blob`` represents.
        tags: The initial tag set, if any.
        metadata: An optional JSON-scalar metadata bag.
        path: An optional advisory display/fallback path.
        reference_key: The content-only reference-derivation key (ruling
            P11-R8, ``design-docs/specs/phase-11-asset-ingress/plan.md``
            §3.10), already computed by the caller — this function performs
            no derivation of its own, the same "bytes/key in, descriptor out"
            contract as ``content_hash``. Defaults to ``""`` (*unknown* — no
            derived edge), so a caller that predates this field, or a kind
            that is never a reference target, need not pass it.

    Returns:
        A new, validated :class:`AssetDescriptor` whose ``content_hash`` is
        :func:`hash_of` (``blob``) and whose ``reference_key`` is exactly
        what was passed in.

    Raises:
        AssetExtractError: If ``blob`` cannot be hashed, or the resulting
            descriptor fails validation (invalid identity/kind/name, or the
            tag/metadata bounds are exceeded).
    """
    digest = hash_of(blob)
    try:
        return AssetDescriptor(
            asset_id=asset_id,
            kind=kind,
            name=name,
            content_hash=digest,
            tags=frozenset(tags),
            metadata=metadata if metadata is not None else {},
            path=path,
            reference_key=reference_key,
        )
    except AssetCatalogModelError as exc:
        raise AssetExtractError(f"cannot derive descriptor: {exc}") from exc
