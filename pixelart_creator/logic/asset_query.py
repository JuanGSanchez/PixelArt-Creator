"""Pure, deterministic catalog search/filter — zero Qt (S11).

Search and filter over an :class:`~pixelart_creator.logic.asset_catalog.AssetCatalog`
(REQ-P11-LOGIC-003): a single pure function :func:`query` of
``(catalog, name, tags, kind)`` returning a **stably-ordered** tuple of matching
descriptors. The three predicates **intersect** (name substring AND every requested tag
AND kind); an **empty query returns the full catalog**. Because the result reuses the
catalog's deterministic ``asset_id`` order, the same catalog + same query is
**byte-identical across runs** (P2) — no wall-clock, no randomness, no locale-dependent
ordering (name matching uses Unicode ``str.casefold``, which is locale-independent).

Pure and deterministic: no Qt. This module reaches only ``asset_catalog`` (and, through
it, ``constants``) — a downward leaf, no ``logic -> data`` edge.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)

__all__ = [
    "AssetQueryError",
    "query",
]


class AssetQueryError(ValueError):
    """Raised on a malformed query argument (type defence)."""


def _validate_tags(tags: Any) -> Tuple[str, ...]:
    """Return ``tags`` as a validated tuple of non-empty str, else raise."""
    if isinstance(tags, str):
        raise AssetQueryError("tags must be a sequence of str, not a bare str")
    if not isinstance(tags, Sequence):
        raise AssetQueryError(f"tags must be a sequence of str, got {tags!r}")
    for tag in tags:
        if not isinstance(tag, str) or not tag:
            raise AssetQueryError(f"each tag must be a non-empty str, got {tag!r}")
    return tuple(tags)


def query(
    catalog: AssetCatalog,
    *,
    name: Optional[str] = None,
    tags: Sequence[str] = (),
    kind: Optional[AssetKind] = None,
) -> Tuple[AssetDescriptor, ...]:
    """Return the catalog entries matching every supplied filter, stably ordered.

    Args:
        catalog: The catalog snapshot to search.
        name: A case-insensitive substring of the entry ``name`` (Unicode casefold).
            ``None`` (the default) applies no name filter.
        tags: Tags the entry must carry **all** of (AND). Empty applies no tag filter.
        kind: The :class:`AssetKind` the entry must have. ``None`` applies no kind
            filter.

    Returns:
        The matching descriptors in the catalog's deterministic ``asset_id`` order. An
        empty query (``name=None, tags=(), kind=None``) returns the full catalog.

    Raises:
        AssetQueryError: If ``catalog``, ``name``, ``tags`` or ``kind`` is malformed.
    """
    if not isinstance(catalog, AssetCatalog):
        raise AssetQueryError(f"catalog must be an AssetCatalog, got {catalog!r}")
    if name is not None and not isinstance(name, str):
        raise AssetQueryError(f"name must be a str or None, got {name!r}")
    if kind is not None and not isinstance(kind, AssetKind):
        raise AssetQueryError(f"kind must be an AssetKind or None, got {kind!r}")
    required_tags = _validate_tags(tags)

    needle = name.casefold() if name is not None else None
    tag_set = frozenset(required_tags)

    results = []
    for descriptor in catalog.entries():
        if needle is not None and needle not in descriptor.name.casefold():
            continue
        if tag_set and not tag_set.issubset(descriptor.tags):
            continue
        if kind is not None and descriptor.kind is not kind:
            continue
        results.append(descriptor)
    return tuple(results)
