# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Texture-atlas layout over the shipped MaxRects packer (zero Qt, S11).

Phase 7 packs already-flattened sprite buffers into a single non-overlapping
atlas image by **delegating to** :func:`~pixelart_creator.logic.compactor.compact`
(CP-1 — deterministic MaxRects BSSF, **rotation disabled**, no time/random). This
module does **not** re-implement packing (Article I); it inflates each sprite rect
by the requested inter-sprite ``padding``, hands the rectangles to CP-1, then
blits each sprite at its returned :class:`~pixelart_creator.logic.compactor.Placement`
(axis-aligned — CP-1 never rotates, so the JSON ``rotated`` field is a structural
``false``, ADR-0017).

Like :mod:`~pixelart_creator.logic.blend`, this module imports **no**
``document`` and **no** ``export`` — it operates purely on ``(id, PixelBuffer)``
sprite tuples the caller (``logic/export.py``) already flattened (CO-4), returning
its own :class:`AtlasPlacement` records that ``export`` folds into the single
Aseprite-JSON builder. Keeping the metadata builder in ``export`` means there is
**no** ``atlas -> export`` back-edge, so the import graph stays one-way and acyclic
(``export -> atlas -> compactor``, PL7-D3). All numeric bounds come from
``logic/constants.py`` (S12); the caller passes ``max_dimension`` explicitly to
CP-1 (the compactor imports no constants). REQ-P7-LOGIC-006/-007.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from pixelart_creator.logic.compactor import CompactionError, compact
from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    MAX_ATLAS_DIMENSION,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelBufferError

__all__ = [
    "AtlasError",
    "AtlasPlacement",
    "AtlasResult",
    "pack_atlas",
]


class AtlasError(ValueError):
    """Raised when an atlas cannot be packed or its input is invalid.

    Wraps the packer's :class:`~pixelart_creator.logic.compactor.CompactionError`
    so a sprite set that cannot fit surfaces a single export-domain error (never a
    silent overlap or truncation, Article VII / REQ-P7-LOGIC-006).
    """


@dataclass(frozen=True)
class AtlasPlacement:
    """One sprite's axis-aligned rect on the packed atlas image.

    ``x``/``y`` are the top-left blit coordinate; ``w``/``h`` are the sprite's
    **original** (un-inflated) dimensions — the padding reserved for the gap is
    never part of the reported rect, so cropping ``(x, y, w, h)`` from the atlas
    image returns exactly the sprite's source pixels (REQ-P7-LOGIC-007). Rotation
    is structurally absent (CP-1 never rotates). This is a deliberately local
    record — not ``export.SpriteRect`` — so ``atlas`` never imports ``export``
    (no back-edge, PL7-D3); ``export`` folds it into the Aseprite JSON.
    """

    name: str
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class AtlasResult:
    """The packed atlas image plus its non-overlapping placements + dimensions."""

    image: PixelBuffer
    placements: Tuple[AtlasPlacement, ...]
    width: int
    height: int


def pack_atlas(
    sprites: Sequence[Tuple[str, PixelBuffer]],
    *,
    padding: int = DEFAULT_ATLAS_PADDING,
    max_dimension: int = MAX_ATLAS_DIMENSION,
) -> AtlasResult:
    """Pack ``sprites`` into a single non-overlapping atlas image (CP-1 reuse).

    Each ``(name, buffer)`` sprite rect is inflated by ``padding`` (to reserve the
    inter-sprite gap), the inflated rectangles are packed by
    :func:`~pixelart_creator.logic.compactor.compact` (MaxRects BSSF, rotation
    disabled), then each sprite is blitted (overwrite) at its returned placement.
    Because the inflated cells are non-overlapping, the reported (un-inflated)
    sprite rects are non-overlapping too, and cropping any rect from the atlas
    returns that sprite's exact source pixels (REQ-P7-LOGIC-007). Packing is
    **not** re-implemented (Article I).

    The effective atlas ceiling is clamped to the *buildable*
    :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` maximum —
    ``min(max_dimension, MAX_CANVAS_WIDTH)`` px wide by
    ``min(max_dimension, MAX_CANVAS_HEIGHT)`` px tall (the platform 8K ceiling,
    Article VI). The packed sheet is then materialised as a ``PixelBuffer`` of that
    size, so it can never exceed what the buffer can allocate; any infeasibility
    (a padded cell taller/wider than the buildable ceiling, a set that will not
    fit, or a buffer bound violation) surfaces as :class:`AtlasError`, never as an
    escaping :class:`PixelBufferError` (S2 fix).

    Args:
        sprites: Ordered ``(name, RGBA PixelBuffer)`` pairs; names must be unique.
        padding: Inter-sprite gap, px (``>= 0``); reserved by inflating each rect.
        max_dimension: Requested atlas edge bound, px (``> 0``). The effective
            packing bound is clamped per-axis to the buildable buffer ceiling
            (``MAX_CANVAS_WIDTH`` x ``MAX_CANVAS_HEIGHT``) before being passed to
            CP-1 as ``max_width`` / ``max_height``, so a value above the 8K canvas
            cannot produce an unbuildable sheet.

    Returns:
        An :class:`AtlasResult` with the packed RGBA image, the per-sprite
        :class:`AtlasPlacement` records (sorted by name — ``export`` reorders into
        the metadata sequence), and the used atlas ``width``/``height``.

    Raises:
        AtlasError: On empty/invalid input, duplicate names, a non-RGBA sprite, an
            out-of-range ``padding``/``max_dimension``, or a set that cannot fit
            (wrapping the packer's :class:`CompactionError`).
    """
    if not sprites:
        raise AtlasError("cannot pack an empty sprite set")
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0:
        raise AtlasError(f"padding must be a non-negative int, got {padding!r}")
    if (
        not isinstance(max_dimension, int)
        or isinstance(max_dimension, bool)
        or max_dimension <= 0
    ):
        raise AtlasError(f"max_dimension must be a positive int, got {max_dimension!r}")

    # Clamp the effective atlas ceiling to the *buildable* PixelBuffer maximum
    # (the platform 8K ceiling, Article VI). The sheet is materialised as a
    # PixelBuffer, whose hard cap is MAX_CANVAS_WIDTH x MAX_CANVAS_HEIGHT (a
    # non-square 7680x4320). A caller max_dimension above either axis would let the
    # packer place sprites into a sheet the buffer cannot allocate, raising
    # PixelBufferError (a DIFFERENT class than AtlasError) at build time (S2 defect).
    # Clamping here keeps CP-1 within the buildable bounds and makes the feasibility
    # guard the SINGLE clean failure path. Rotation is disabled, so each padded cell
    # must fit each axis independently.
    max_atlas_w = min(max_dimension, MAX_CANVAS_WIDTH)
    max_atlas_h = min(max_dimension, MAX_CANVAS_HEIGHT)

    buffers: Dict[str, PixelBuffer] = {}
    rects: List[Tuple[str, int, int]] = []
    for name, buffer in sprites:
        if name in buffers:
            raise AtlasError(f"duplicate sprite name {name!r}")
        if buffer.mode is not ColorMode.RGBA:
            raise AtlasError(f"sprite {name!r} must be an RGBA buffer")
        cell_w = buffer.width + padding
        cell_h = buffer.height + padding
        # Termination guard (S2): reject an infeasible sprite set up front so an
        # unsatisfiable ceiling (smaller than a single padded frame) raises
        # promptly *here*, in the atlas domain, rather than depending on the
        # delegated CP-1 packer to detect it. The ceiling is the buildable
        # per-axis bound (max_atlas_w x max_atlas_h) — a padded cell wider/taller
        # than the buffer can allocate can never be placed within it, so packing
        # is unsatisfiable (bounds are fixed; no retry could ever succeed).
        # Raising eagerly keeps the packer's single placement pass strictly
        # bounded and gives the caller a clear which-frame / required-vs-max
        # message instead of a generic wrapped CompactionError or an escaping
        # PixelBufferError. REQ-P7-LOGIC-006.
        if cell_w > max_atlas_w or cell_h > max_atlas_h:
            raise AtlasError(
                f"sprite {name!r} does not fit: padded cell {cell_w}x{cell_h}px "
                f"(frame {buffer.width}x{buffer.height} + padding {padding}) "
                f"exceeds max_dimension {max_dimension}px "
                f"(buildable atlas ceiling {max_atlas_w}x{max_atlas_h}px)"
            )
        buffers[name] = buffer
        rects.append((name, cell_w, cell_h))

    try:
        packing = compact(rects, max_atlas_w, max_atlas_h)
    except CompactionError as exc:
        raise AtlasError(f"atlas does not fit: {exc}") from exc

    width = max(packing.width, 1)
    height = max(packing.height, 1)
    # Guard the sheet allocation: by construction the packed size is within the
    # clamped per-axis ceilings (<= MAX_CANVAS_WIDTH x MAX_CANVAS_HEIGHT), so this
    # cannot exceed the buildable buffer — but defensively translate ANY
    # PixelBuffer bound violation into an AtlasError so no PixelBufferError ever
    # escapes pack_atlas (S2 fix; keep the failure surface single, Article VII).
    try:
        image = PixelBuffer(width, height, ColorMode.RGBA)
    except PixelBufferError as exc:
        raise AtlasError(
            f"packed atlas {width}x{height}px exceeds the buildable PixelBuffer "
            f"ceiling {MAX_CANVAS_WIDTH}x{MAX_CANVAS_HEIGHT}px"
        ) from exc
    placements: List[AtlasPlacement] = []
    for placement in packing.placements:
        buffer = buffers[placement.id]
        image.blit(buffer, placement.x, placement.y)
        placements.append(
            AtlasPlacement(
                name=placement.id,
                x=placement.x,
                y=placement.y,
                w=buffer.width,
                h=buffer.height,
            )
        )
    placements.sort(key=lambda p: p.name)
    return AtlasResult(
        image=image,
        placements=tuple(placements),
        width=packing.width,
        height=packing.height,
    )
