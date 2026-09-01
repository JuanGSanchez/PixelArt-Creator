# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure asset-catalog model — deterministic, zero Qt (S11).

The catalog identity model (ADR-0030 §1; REQ-P11-DATA-001 / REQ-P11-LOGIC-001): every
asset is a catalog entry identified by a **stable ``AssetId``** (a UUID string,
decoupled
from the filesystem path — the Unity-GUID / Godot-UID role, Researcher §1), carrying its
:class:`AssetKind`, a display ``name``, a set of ``tags``, a ``metadata`` bag, the
``content_hash`` of its canonical bytes (the CAS key + change-detector, ADR-0030 §3),
and
an **advisory** ``path`` (display/fallback only — resolved *through* the ``asset_id``,
never authoritative). All cross-asset references are stored as
``(asset_id, content_hash)``, so a move/rename is never a break (only a deleted id or a
hash mismatch is — ADR-0031).

:class:`AssetDescriptor` is a frozen, deterministic value; :class:`AssetCatalog` is an
**immutable, ordered** collection — :meth:`~AssetCatalog.add` /
:meth:`~AssetCatalog.remove`
return a *new* catalog, :meth:`~AssetCatalog.entries` yields a deterministic
(``asset_id``-sorted) order so downstream queries are byte-identical across runs, and
the
size is bounded by :data:`~pixelart_creator.logic.constants.MAX_CATALOG_ASSETS`
(Article II/VII). The catalog stores **references + metadata**, never a copy of the
asset
payload (that is the shipped PIO-1 ``.pixproj`` form — REQ-P11-DATA-007).

Pure and deterministic: no Qt, no wall-clock, no randomness, no locale. Constants come
from :mod:`pixelart_creator.logic.constants` (S12); the tag/metadata caps are enforced
here so a descriptor is *always* within bounds however it is built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from pixelart_creator.logic.constants import (
    MAX_CATALOG_ASSETS,
    MAX_METADATA_BYTES,
    MAX_TAG_BYTES,
    MAX_TAGS_PER_ASSET,
)
from pixelart_creator.logic.content_hash import canonical_json_bytes

__all__ = [
    "AssetCatalogModelError",
    "AssetKind",
    "AssetDescriptor",
    "AssetCatalog",
]

#: JSON scalar types permitted in an asset ``metadata`` bag (untrusted-input safe — no
#: nested containers, so a metadata payload cannot smuggle unbounded depth). ``bool`` is
#: a subclass of ``int`` and is allowed intentionally.
_METADATA_SCALARS = (str, int, float, bool, type(None))


class AssetCatalogModelError(ValueError):
    """Raised on an invalid asset descriptor or catalog (type / bounds / identity)."""


class AssetKind(Enum):
    """The enumerated vocabulary of cataloged asset kinds (module-local, ADR-0001).

    Each member maps to a shipped tracked entity: ``SPRITE`` -> a ``PixelBuffer`` /
    ``Document`` layer, ``ANIMATION`` -> a Phase-5 ``Frame`` / named animation,
    ``TILESET`` -> a Phase-6 ``Tileset``, ``TILEMAP`` -> a ``Tilemap``, ``PALETTE`` -> a
    palette (REQ-P11-DATA-001). The string values are the stable persisted form.
    """

    SPRITE = "sprite"
    ANIMATION = "animation"
    TILESET = "tileset"
    TILEMAP = "tilemap"
    PALETTE = "palette"


def _validate_tags(tags: Any) -> "frozenset[str]":
    """Return ``tags`` as a validated ``frozenset[str]``, else raise.

    Each tag is a non-empty ``str`` within :data:`MAX_TAG_BYTES` (UTF-8); the count is
    ``<= MAX_TAGS_PER_ASSET`` (Article VII). Deterministic and order-independent (a
    set).
    """
    try:
        tag_set = frozenset(tags)
    except TypeError as exc:
        raise AssetCatalogModelError(f"tags must be an iterable of str: {exc}") from exc
    if len(tag_set) > MAX_TAGS_PER_ASSET:
        raise AssetCatalogModelError(
            f"{len(tag_set)} tags exceeds MAX_TAGS_PER_ASSET ({MAX_TAGS_PER_ASSET})"
        )
    for tag in tag_set:
        if not isinstance(tag, str) or not tag:
            raise AssetCatalogModelError(
                f"each tag must be a non-empty str, got {tag!r}"
            )
        if len(tag.encode("utf-8")) > MAX_TAG_BYTES:
            raise AssetCatalogModelError(
                f"tag {tag!r} exceeds MAX_TAG_BYTES ({MAX_TAG_BYTES})"
            )
    return tag_set


def _validate_metadata(metadata: Any) -> "MappingProxyType[str, object]":
    """Return ``metadata`` as an immutable, validated mapping, else raise.

    Keys are ``str``; values are JSON scalars (no nested containers); the canonical JSON
    encoding is ``<= MAX_METADATA_BYTES`` (Article VII). Returned as a read-only
    :class:`~types.MappingProxyType` so the frozen descriptor stays immutable.
    """
    if not isinstance(metadata, Mapping):
        raise AssetCatalogModelError(
            f"metadata must be a mapping, got {type(metadata).__name__}"
        )
    validated: Dict[str, object] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise AssetCatalogModelError(f"metadata key must be a str, got {key!r}")
        if not isinstance(value, _METADATA_SCALARS):
            raise AssetCatalogModelError(
                f"metadata value for {key!r} must be a JSON scalar, got {value!r}"
            )
        validated[key] = value
    size = len(canonical_json_bytes(validated))
    if size > MAX_METADATA_BYTES:
        raise AssetCatalogModelError(
            f"metadata is {size} bytes, exceeds MAX_METADATA_BYTES "
            f"({MAX_METADATA_BYTES})"
        )
    return MappingProxyType(validated)


@dataclass(frozen=True)
class AssetDescriptor:
    """One catalog entry — a pure, deterministic reference to a shipped entity.

    Attributes:
        asset_id: The stable identity of the asset (a non-empty str; a UUID in
        practice),
            decoupled from the filesystem path. References use this + ``content_hash``.
        kind: The :class:`AssetKind` of the referenced entity.
        name: The human-readable display name (a non-empty str).
        content_hash: The content hash of the asset's canonical bytes (a non-empty str;
            the CAS key + change-detector). Deep hex validation is a ``data/`` concern.
        tags: The free-form tag set; ``<= MAX_TAGS_PER_ASSET`` tags, each within
            ``MAX_TAG_BYTES``.
        metadata: An immutable JSON-scalar metadata bag; canonical size within
            ``MAX_METADATA_BYTES``.
        path: The advisory current location (display/fallback only); resolved *through*
            ``asset_id``, never authoritative. ``None`` when unknown.
        reference_key: The content-only reference-derivation key (ruling P11-R8)
            — a hex content hash of
            :func:`~pixelart_creator.logic.asset_edges.reference_bytes`,
            distinct from ``content_hash``: this key answers *"is this the same
            pictorial content?"* (edge derivation only, ``REQ-P11-LOGIC-010``),
            while ``content_hash`` answers *"are these the same stored bytes?"*
            (dedup/retrieval/identity, unchanged by this field). Defaulted to
            ``""``, meaning *unknown* — a pre-``reference_key`` sidecar or
            artifact entry parses with ``""`` and simply derives no edge (never
            a crash). Recorded only for kinds that can **be** a reference
            target (``SPRITE``, ``TILESET``); every other kind, and an
            ambiguous ``TILESET`` (zero or more than one tileset), also
            records ``""``. A **defaulted trailing field**: it is added last so
            no existing keyword-argument call site moves.
    """

    asset_id: str
    kind: AssetKind
    name: str
    content_hash: str
    tags: "frozenset[str]" = frozenset()
    metadata: Mapping[str, object] = field(default=MappingProxyType({}), hash=False)
    path: Optional[str] = None
    reference_key: str = ""

    def __post_init__(self) -> None:
        """Validate identity, kind, name, hash, tags, metadata and advisory path."""
        if not isinstance(self.asset_id, str) or not self.asset_id:
            raise AssetCatalogModelError(
                f"asset_id must be a non-empty str, got {self.asset_id!r}"
            )
        if not isinstance(self.kind, AssetKind):
            raise AssetCatalogModelError(
                f"kind must be an AssetKind, got {self.kind!r}"
            )
        if not isinstance(self.name, str) or not self.name:
            raise AssetCatalogModelError(
                f"name must be a non-empty str, got {self.name!r}"
            )
        if not isinstance(self.content_hash, str) or not self.content_hash:
            raise AssetCatalogModelError(
                f"content_hash must be a non-empty str, got {self.content_hash!r}"
            )
        object.__setattr__(self, "tags", _validate_tags(self.tags))
        object.__setattr__(self, "metadata", _validate_metadata(self.metadata))
        if self.path is not None and not isinstance(self.path, str):
            raise AssetCatalogModelError(
                f"path must be a str or None, got {self.path!r}"
            )
        if not isinstance(self.reference_key, str):
            raise AssetCatalogModelError(
                f"reference_key must be a str, got {self.reference_key!r}"
            )


@dataclass(frozen=True)
class AssetCatalog:
    """An immutable, ordered set of :class:`AssetDescriptor` s keyed by ``asset_id``.

    Attributes:
        descriptors: The catalog entries; unique ``asset_id`` s,
            ``<= MAX_CATALOG_ASSETS``. Enumeration order is deterministic (sorted by
            ``asset_id``) so downstream queries are byte-identical across runs.
    """

    descriptors: Tuple[AssetDescriptor, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate member types, uniqueness, count, and normalise the order."""
        descriptors = tuple(self.descriptors)
        if len(descriptors) > MAX_CATALOG_ASSETS:
            raise AssetCatalogModelError(
                f"{len(descriptors)} assets exceeds MAX_CATALOG_ASSETS "
                f"({MAX_CATALOG_ASSETS})"
            )
        seen: set[str] = set()
        for descriptor in descriptors:
            if not isinstance(descriptor, AssetDescriptor):
                raise AssetCatalogModelError(
                    f"expected an AssetDescriptor, got {descriptor!r}"
                )
            if descriptor.asset_id in seen:
                raise AssetCatalogModelError(
                    f"duplicate asset_id {descriptor.asset_id!r}"
                )
            seen.add(descriptor.asset_id)
        ordered = tuple(sorted(descriptors, key=lambda d: d.asset_id))
        object.__setattr__(self, "descriptors", ordered)

    def add(self, entry: AssetDescriptor) -> "AssetCatalog":
        """Return a **new** catalog with ``entry`` added (pure).

        Raises:
            AssetCatalogModelError: If ``entry`` is not an :class:`AssetDescriptor`, its
                ``asset_id`` is already present, or adding would exceed
                :data:`MAX_CATALOG_ASSETS`.
        """
        if not isinstance(entry, AssetDescriptor):
            raise AssetCatalogModelError(f"expected an AssetDescriptor, got {entry!r}")
        if any(d.asset_id == entry.asset_id for d in self.descriptors):
            raise AssetCatalogModelError(
                f"asset_id {entry.asset_id!r} is already in the catalog"
            )
        if len(self.descriptors) >= MAX_CATALOG_ASSETS:
            raise AssetCatalogModelError(
                f"catalog already at MAX_CATALOG_ASSETS ({MAX_CATALOG_ASSETS})"
            )
        return AssetCatalog(descriptors=self.descriptors + (entry,))

    def remove(self, asset_id: str) -> "AssetCatalog":
        """Return a **new** catalog with the entry for ``asset_id`` removed (pure).

        Raises:
            AssetCatalogModelError: If no entry has that ``asset_id``.
        """
        kept = tuple(d for d in self.descriptors if d.asset_id != asset_id)
        if len(kept) == len(self.descriptors):
            raise AssetCatalogModelError(f"no asset with id {asset_id!r}")
        return AssetCatalog(descriptors=kept)

    def get(self, asset_id: str) -> Optional[AssetDescriptor]:
        """Return the entry for ``asset_id``, or ``None`` if absent (never raises)."""
        for descriptor in self.descriptors:
            if descriptor.asset_id == asset_id:
                return descriptor
        return None

    def entries(self) -> Tuple[AssetDescriptor, ...]:
        """Return all entries in the deterministic (``asset_id``-sorted) order."""
        return self.descriptors
