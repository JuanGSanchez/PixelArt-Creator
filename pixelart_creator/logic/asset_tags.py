"""Reversible asset-tag operations — pure, zero Qt (S11; HIS-1 pattern).

Tagging expressed as pure **do/undo pairs** (REQ-P11-LOGIC-002 / REQ-P11-DATA-003): each
factory returns a ``(do, undo)`` tuple of no-argument callables. ``do()`` returns the
new
:class:`~pixelart_creator.logic.asset_catalog.AssetDescriptor` with the tag added /
removed; ``undo()`` returns the exact prior descriptor — so ``ui/commands.py`` can wrap
the pair in a single ``QUndoCommand`` (the shipped ``logic/history`` reversible-op
precedent) while the ``logic/`` layer stays Qt-free (S11, PL11-D3).

The operations are **deterministic** and **idempotent**: adding an already-present tag
or
removing an absent tag yields a descriptor equal to the input (a no-op), and ``do`` /
``undo`` capture only the minimal prior state (the original descriptor). Bounds are
checked
**at factory time** (before the pair enters the undo stack) so the UI surfaces an error
early: a tag over :data:`~pixelart_creator.logic.constants.MAX_TAG_BYTES`, or an add
that
would exceed :data:`~pixelart_creator.logic.constants.MAX_TAGS_PER_ASSET`, raises
:class:`AssetTagError` (Article II/VII). The descriptor's own ``__post_init__`` is the
ultimate bound guard; this module fails earlier with a tag-specific error.

Pure and deterministic: no Qt, no wall-clock, no randomness, no locale. Constants come
from :mod:`pixelart_creator.logic.constants` (S12).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Tuple

from pixelart_creator.logic.asset_catalog import AssetDescriptor
from pixelart_creator.logic.constants import MAX_TAG_BYTES, MAX_TAGS_PER_ASSET

__all__ = [
    "AssetTagError",
    "TagOp",
    "make_add_tag",
    "make_remove_tag",
]

#: A reversible tag operation: ``(do, undo)``, each returning an
#: :class:`AssetDescriptor`.
TagOp = Tuple[Callable[[], AssetDescriptor], Callable[[], AssetDescriptor]]


class AssetTagError(ValueError):
    """Raised on an invalid tag or a bound-exceeding tag operation."""


def _validate_entry_and_tag(entry: Any, tag: Any) -> None:
    """Validate the operand descriptor and the tag string (type + byte cap)."""
    if not isinstance(entry, AssetDescriptor):
        raise AssetTagError(f"entry must be an AssetDescriptor, got {entry!r}")
    if not isinstance(tag, str) or not tag:
        raise AssetTagError(f"tag must be a non-empty str, got {tag!r}")
    if len(tag.encode("utf-8")) > MAX_TAG_BYTES:
        raise AssetTagError(f"tag {tag!r} exceeds MAX_TAG_BYTES ({MAX_TAG_BYTES})")


def make_add_tag(entry: AssetDescriptor, tag: str) -> TagOp:
    """Return a reversible ``(do, undo)`` pair that adds ``tag`` to ``entry``.

    ``do()`` returns a descriptor whose tags include ``tag`` (idempotent — if ``tag`` is
    already present, ``do()`` returns ``entry`` unchanged); ``undo()`` returns the
    original ``entry``. The bound check happens now, not at ``do`` time
    (REQ-P11-LOGIC-002).

    Raises:
        AssetTagError: If ``entry`` is not a descriptor, ``tag`` is not a non-empty str
            within :data:`MAX_TAG_BYTES`, or adding a new ``tag`` would exceed
            :data:`MAX_TAGS_PER_ASSET`.
    """
    _validate_entry_and_tag(entry, tag)
    already_present = tag in entry.tags
    if not already_present and len(entry.tags) + 1 > MAX_TAGS_PER_ASSET:
        raise AssetTagError(
            f"adding {tag!r} would exceed MAX_TAGS_PER_ASSET ({MAX_TAGS_PER_ASSET})"
        )

    def do() -> AssetDescriptor:
        if already_present:
            return entry
        return dataclasses.replace(entry, tags=entry.tags | {tag})

    def undo() -> AssetDescriptor:
        return entry

    return do, undo


def make_remove_tag(entry: AssetDescriptor, tag: str) -> TagOp:
    """Return a reversible ``(do, undo)`` pair that removes ``tag`` from ``entry``.

    ``do()`` returns a descriptor without ``tag`` (idempotent — if ``tag`` is absent,
    ``do()`` returns ``entry`` unchanged); ``undo()`` returns the original ``entry``
    (restoring the removed tag).

    Raises:
        AssetTagError: If ``entry`` is not a descriptor, or ``tag`` is not a non-empty
            str within :data:`MAX_TAG_BYTES`.
    """
    _validate_entry_and_tag(entry, tag)
    present = tag in entry.tags

    def do() -> AssetDescriptor:
        if not present:
            return entry
        return dataclasses.replace(entry, tags=entry.tags - {tag})

    def undo() -> AssetDescriptor:
        return entry

    return do, undo
