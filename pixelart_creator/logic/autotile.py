# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Blob-47 auto-tiling resolver (zero Qt, S11).

Auto-tiling resolves a cell's **display tile** as a deterministic function of the
placed (logical) tile and its 8 neighbours' occupancy (REQ-P6-LOGIC-010). This
module ships **Blob-47** (ADR-0013): an 8-neighbour occupancy bitmask reduced to
exactly 47 frames by *edge-implies-corner* gating (Boris the Brave's rule,
research §1.2), resolved through a load-time 256-entry lookup table so resolution
is total, ``O(1)`` and free of RNG/time (P2, SC-L010-1).

The 8-neighbour **bit weights** ``TL=1, T=2, TR=4, L=8, R=16, BL=32, B=64,
BR=128`` (the Godot/Jaconir convention) are an *implementation convention, not a
standard* (research §1.2 / OD-2), so — like the ``blend.py`` W3C formula
constants — they are **module-local intrinsic constants** here (ADR-0001
exemption, ADR-0013), never ``constants.py`` tuning scalars. The tilemap builds
occupancy masks through :func:`mask_from_neighbours` so this convention lives in
exactly one place.

This module imports only :mod:`pixelart_creator.logic.constants` (it uses none of
its scalars today, but the import keeps the leaf shape explicit) and is a pure
leaf over the standard library: it never imports ``document``/``tilemap``/Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "AutotileError",
    "AutotileRuleset",
    "BLOB_TILE_COUNT",
    "mask_from_neighbours",
    "resolve_display_index",
    "resolve_display_gid",
]

#: The number of distinct display frames a Blob-47 ruleset resolves to
#: (256 raw 8-neighbour masks collapse to exactly 47 under edge-implies-corner
#: gating; research §1.2 derivation table). REQ-P6-LOGIC-010.
BLOB_TILE_COUNT: int = 47

# --- Blob-47 bit weights (module-local intrinsic convention, ADR-0013) --------
# The 8 neighbours around a cell (origin top-left, +y is downward), each a
# power-of-two bit. Godot/Jaconir convention (research §1.2). NOT a standard;
# published here + in the ruleset. Corners: TL/TR/BL/BR; cardinal edges: T/L/R/B.
_TL = 0x01
_T = 0x02
_TR = 0x04
_L = 0x08
_R = 0x10
_BL = 0x20
_B = 0x40
_BR = 0x80

_RAW_MASK_MAX = 0xFF  # 8 neighbour bits -> raw mask 0..255


class AutotileError(ValueError):
    """Raised on an invalid auto-tile ruleset or occupancy mask."""


def _canonicalise(mask: int) -> int:
    """Fold a raw 8-neighbour mask onto its edge-implies-corner canonical form.

    A diagonal (corner) bit is meaningful only when **both** its adjacent
    cardinal edges are set (Boris the Brave, research §1.2). A corner whose edges
    are not both present is cleared, collapsing the 256 raw masks to exactly 47
    canonical values.
    """
    m = mask
    if not (m & _T and m & _L):
        m &= ~_TL
    if not (m & _T and m & _R):
        m &= ~_TR
    if not (m & _B and m & _L):
        m &= ~_BL
    if not (m & _B and m & _R):
        m &= ~_BR
    return m & _RAW_MASK_MAX


def _build_lut() -> Tuple[List[int], Tuple[int, ...]]:
    """Build the raw-mask -> frame-index LUT and the canonical-mask ordering.

    Returns ``(lut, canonical)`` where ``lut[raw]`` is the ``0..46`` frame index
    for every raw mask ``0..255`` and ``canonical`` is the sorted tuple of the 47
    distinct canonical masks (``canonical[index]`` is the representative mask of a
    frame). The sort makes the index assignment deterministic (P2).
    """
    canonical_masks = sorted({_canonicalise(m) for m in range(_RAW_MASK_MAX + 1)})
    index_of: Dict[int, int] = {m: i for i, m in enumerate(canonical_masks)}
    lut = [index_of[_canonicalise(m)] for m in range(_RAW_MASK_MAX + 1)]
    return lut, tuple(canonical_masks)


#: 256-entry lookup table built once at import (deterministic, static, O(1) reads).
_DISPLAY_LUT, _CANONICAL_MASKS = _build_lut()

# Fail fast at import if the gating derivation ever stops summing to 47 (a
# regression guard on the algorithm-intrinsic table, ADR-0013 §Consequences).
assert len(_CANONICAL_MASKS) == BLOB_TILE_COUNT, (
    f"Blob-47 gating produced {len(_CANONICAL_MASKS)} frames, expected "
    f"{BLOB_TILE_COUNT}"
)


def mask_from_neighbours(
    tl: bool,
    t: bool,
    tr: bool,
    left: bool,
    right: bool,
    bl: bool,
    b: bool,
    br: bool,
) -> int:
    """Build a raw 8-neighbour occupancy mask (``0..255``) from neighbour flags.

    Each flag is ``True`` when that neighbour cell is occupied. This is the
    single place the Blob-47 bit-weight convention (``TL=1..BR=128``) is applied,
    so callers (``logic/tilemap.py``) never hard-code the weights. Deterministic
    (P2).
    """
    mask = 0
    if tl:
        mask |= _TL
    if t:
        mask |= _T
    if tr:
        mask |= _TR
    if left:
        mask |= _L
    if right:
        mask |= _R
    if bl:
        mask |= _BL
    if b:
        mask |= _B
    if br:
        mask |= _BR
    return mask


def resolve_display_index(occupancy_mask: int) -> int:
    """Resolve a raw 8-neighbour occupancy mask to a Blob-47 frame index.

    Maps ``occupancy_mask`` (``0..255``) to one of ``0..46`` via the load-time
    256-entry LUT (edge-implies-corner gating, research §1.2). Total, ``O(1)`` and
    deterministic — no RNG, no time (P2, SC-L010-1).

    Raises:
        AutotileError: If ``occupancy_mask`` is not an int in ``0..255``.
    """
    if not isinstance(occupancy_mask, int) or isinstance(occupancy_mask, bool):
        raise AutotileError(f"occupancy_mask must be an int, got {occupancy_mask!r}")
    if not 0 <= occupancy_mask <= _RAW_MASK_MAX:
        raise AutotileError(
            f"occupancy_mask {occupancy_mask} out of range 0..{_RAW_MASK_MAX}"
        )
    return _DISPLAY_LUT[occupancy_mask]


@dataclass(frozen=True)
class AutotileRuleset:
    """A single-terrain Blob-47 ruleset: a logical terrain gid + 47 display gids.

    The user stamps the ``terrain_gid`` (the *logical* placement); the display
    gid a cell shows is derived from its neighbourhood via
    :func:`resolve_display_gid` (ADR-0013 logical/display separation, keeping
    auto-tiling reversible and the Tiled round-trip lossless). ``frame_gids`` is
    the 47-frame blob atlas (``frame_gids[index]`` is shown for frame ``index``).

    Raises:
        AutotileError: If ``terrain_gid`` is not a positive int or ``frame_gids``
            does not hold exactly :data:`BLOB_TILE_COUNT` int gids.
    """

    terrain_gid: int
    frame_gids: Tuple[int, ...]

    def __init__(self, terrain_gid: int, frame_gids: Sequence[int]) -> None:
        """Validate and freeze the ruleset (``frame_gids`` coerced to a tuple)."""
        if not isinstance(terrain_gid, int) or isinstance(terrain_gid, bool):
            raise AutotileError(f"terrain_gid must be an int, got {terrain_gid!r}")
        if terrain_gid <= 0:
            raise AutotileError(f"terrain_gid must be positive, got {terrain_gid}")
        frames = tuple(frame_gids)
        if len(frames) != BLOB_TILE_COUNT:
            raise AutotileError(
                f"frame_gids must hold exactly {BLOB_TILE_COUNT} gids, got "
                f"{len(frames)}"
            )
        for gid in frames:
            if not isinstance(gid, int) or isinstance(gid, bool) or gid < 0:
                raise AutotileError(
                    f"each frame gid must be a non-negative int, got {gid!r}"
                )
        object.__setattr__(self, "terrain_gid", terrain_gid)
        object.__setattr__(self, "frame_gids", frames)


def resolve_display_gid(ruleset: AutotileRuleset, occupancy_mask: int) -> int:
    """Resolve the display gid a cell shows under ``ruleset`` for a neighbourhood.

    Chains :func:`resolve_display_index` (mask -> frame index) into
    ``ruleset.frame_gids[index]``. Deterministic (P2).

    Raises:
        AutotileError: If ``ruleset`` is not an :class:`AutotileRuleset` or
            ``occupancy_mask`` is out of range.
    """
    if not isinstance(ruleset, AutotileRuleset):
        raise AutotileError(f"ruleset must be an AutotileRuleset, got {ruleset!r}")
    return ruleset.frame_gids[resolve_display_index(occupancy_mask)]
