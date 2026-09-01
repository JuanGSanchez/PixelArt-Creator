# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Batch recolour — many targets, one transactional reversible command (zero Qt, S11).

Batch recolour **composes the shipped** :mod:`logic.palette_ops` (PS-1 —
:func:`~pixelart_creator.logic.palette_ops.swap_indices` for indexed buffers,
:func:`~pixelart_creator.logic.palette_ops.remap_colors` for RGBA buffers): it does
**not** re-implement any recolour maths (Article I). It applies the *same* pure
per-target op across many targets as **one transactional reversible command**
(REQ-P8-LOGIC-011): each per-target result is byte-identical to the single,
one-at-a-time recolour of that target with the same mapping, and the whole batch is
one undoable step (:class:`~pixelart_creator.logic.history.GroupCommand`).

Transactional / failure isolation: every target is **validated and its
per-target command built before anything is applied**. An invalid target (mode
mismatch, out-of-range mapping) raises :class:`BatchError` naming the target index
with **zero mutation** — so a per-target failure never corrupts the other targets.
Target count is bounded by
:data:`~pixelart_creator.logic.constants.MAX_BATCH_RECOLOUR_TARGETS`.

The mappings are supplied to ``palette_ops`` (the recolour authority); this module
only orchestrates, snapshots, and groups. There is **no ``eval``/``exec``** here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

import numpy as np

from pixelart_creator.logic import palette_ops
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import MAX_BATCH_RECOLOUR_TARGETS
from pixelart_creator.logic.history import Command, FunctionCommand, GroupCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = [
    "BatchError",
    "RecolourTarget",
    "ColorMapping",
    "make_batch_recolour_command",
]


class BatchError(ValueError):
    """Raised on an empty/oversized target set or an invalid per-target recolour."""


@dataclass(frozen=True)
class RecolourTarget:
    """One recolour target: a buffer to remap, plus a human-readable label."""

    buffer: PixelBuffer
    label: str = "layer"


@dataclass(frozen=True)
class ColorMapping:
    """A recolour mapping — exactly one of an index remap **or** a colour remap.

    ``index_map`` targets :data:`~pixelart_creator.logic.pixel_buffer.ColorMode.INDEXED`
    buffers (``old_index -> new_index``, applied via ``palette_ops.swap_indices``);
    ``color_map`` targets ``RGBA`` buffers (``old_rgba -> new_rgba``, applied via
    ``palette_ops.remap_colors``). Both are order-independent (the shipped ops read
    the original buffer and write a copy), so replay is deterministic (P2).
    """

    index_map: Optional[Mapping[int, int]] = None
    color_map: Optional[Mapping[RGBA, RGBA]] = None

    def __post_init__(self) -> None:
        """Validate that exactly one of ``index_map`` / ``color_map`` is set."""
        if (self.index_map is None) == (self.color_map is None):
            raise BatchError("ColorMapping needs exactly one of index_map or color_map")


def _target_command(
    index: int, target: RecolourTarget, mapping: ColorMapping
) -> Command:
    """Build one reversible per-target recolour command via ``palette_ops`` (PS-1).

    Snapshots the buffer, computes the remapped buffer with the shipped op, and
    returns a :class:`~pixelart_creator.logic.history.FunctionCommand` that swaps
    the data with a single vectorised assignment (``apply ∘ undo = identity``).
    """
    if not isinstance(target, RecolourTarget):
        raise BatchError(f"target {index} is not a RecolourTarget: {target!r}")
    buffer = target.buffer
    try:
        if buffer.mode is ColorMode.INDEXED:
            if mapping.index_map is None:
                raise BatchError(
                    f"target {index} ({target.label!r}) is indexed but the mapping "
                    "has no index_map"
                )
            remapped = palette_ops.swap_indices(buffer, mapping.index_map)
        else:
            if mapping.color_map is None:
                raise BatchError(
                    f"target {index} ({target.label!r}) is RGBA but the mapping has "
                    "no color_map"
                )
            remapped = palette_ops.remap_colors(buffer, mapping.color_map)
    except palette_ops.PaletteError as exc:  # normalise PS-1 errors to BatchError
        raise BatchError(
            f"target {index} ({target.label!r}) recolour failed: {exc}"
        ) from exc

    old_data = buffer.data.copy()
    new_data = np.ascontiguousarray(remapped.data.copy())

    def _do() -> None:
        buffer.data[:, :] = new_data

    def _undo() -> None:
        buffer.data[:, :] = old_data

    return FunctionCommand(_do, _undo, label=f"recolour {target.label}")


def make_batch_recolour_command(
    targets: Sequence[RecolourTarget], mapping: ColorMapping
) -> Command:
    """Compose one transactional reversible batch recolour across ``targets``.

    Builds and validates every per-target command **before applying anything**
    (so an invalid target aborts with :class:`BatchError` and zero mutation —
    per-target failure isolation, REQ-P8-LOGIC-011), then returns one
    :class:`~pixelart_creator.logic.history.GroupCommand` (returned **unapplied**;
    the dispatcher / ``ui.commands`` applies it as a single undoable step). Each
    per-target output equals the single equivalent ``palette_ops`` op (PS-1).

    Args:
        targets: The buffers to recolour (``1..MAX_BATCH_RECOLOUR_TARGETS``).
        mapping: The index/colour remap applied to every target.

    Raises:
        BatchError: On an empty/oversized target set, a mode/mapping mismatch, or
            an out-of-range mapping (normalised from ``palette_ops``).
    """
    if not isinstance(mapping, ColorMapping):
        raise BatchError(f"mapping must be a ColorMapping, got {mapping!r}")
    if not targets:
        raise BatchError("batch recolour needs at least one target")
    if len(targets) > MAX_BATCH_RECOLOUR_TARGETS:
        raise BatchError(
            f"batch exceeds MAX_BATCH_RECOLOUR_TARGETS ({MAX_BATCH_RECOLOUR_TARGETS})"
        )
    commands = [_target_command(i, target, mapping) for i, target in enumerate(targets)]
    return GroupCommand(commands, label="batch recolour")
