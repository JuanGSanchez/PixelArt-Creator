"""Tests for pixelart_creator.logic.atlas (REQ-P7-LOGIC-006, -007).

MaxRects atlas layout over the shipped CP-1 packer: sprites pack **without
overlap** and within bounds (SC-L006-1), rotation is OFF (no swapped dims), and
the coordinate/pixel round-trip holds — cropping each placement returns the source
sprite (SC-L007-1). A set that cannot fit surfaces AtlasError (no silent overlap or
truncation). Zero Qt; deterministic. Includes a Hypothesis non-overlap property.
"""

from __future__ import annotations

import time
from typing import List, Tuple

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.atlas import AtlasError, AtlasPlacement, pack_atlas
from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    MAX_ATLAS_DIMENSION,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.logic.pixel_buffer import (
    ColorMode,
    PixelBuffer,
    PixelBufferError,
)

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)


def sprite(name: str, w: int, h: int, color: Tuple[int, int, int, int]):
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.fill(color)
    return name, buf


def rects_overlap(a: AtlasPlacement, b: AtlasPlacement) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def _mixed_sprites():
    return [
        sprite("0", 4, 4, RED),
        sprite("1", 8, 4, GREEN),
        sprite("2", 4, 8, BLUE),
        sprite("3", 6, 6, YELLOW),
    ]


# --------------------------------------------------------------------------- #
# SC-L006-1 — non-overlap + in-bounds                                          #
# --------------------------------------------------------------------------- #


def test_pack_atlas_no_overlap_and_in_bounds() -> None:
    """REQ-P7-LOGIC-006: every placement is non-overlapping and within bounds."""
    result = pack_atlas(_mixed_sprites(), padding=0, max_dimension=64)
    placements = result.placements
    for i, a in enumerate(placements):
        assert a.x >= 0 and a.y >= 0
        assert a.x + a.w <= result.width and a.y + a.h <= result.height
        for b in placements[i + 1 :]:
            assert not rects_overlap(a, b), f"{a.name} overlaps {b.name}"


def test_pack_atlas_no_rotation() -> None:
    """REQ-P7-LOGIC-006: rotation is OFF — placement dims match the source dims."""
    sprites = _mixed_sprites()
    by_name = {name: buf for name, buf in sprites}
    result = pack_atlas(sprites, max_dimension=64)
    for placement in result.placements:
        src = by_name[placement.name]
        assert (placement.w, placement.h) == (src.width, src.height)
    # AtlasPlacement carries no rotation field at all.
    assert not hasattr(result.placements[0], "rotated")


def test_pack_atlas_placements_sorted_by_name() -> None:
    """pack_atlas returns placements sorted by name (deterministic order)."""
    result = pack_atlas(_mixed_sprites(), max_dimension=64)
    names = [p.name for p in result.placements]
    assert names == sorted(names) == ["0", "1", "2", "3"]


# --------------------------------------------------------------------------- #
# SC-L007-1 — coordinate/pixel round-trip                                      #
# --------------------------------------------------------------------------- #


def test_pack_atlas_coord_pixel_round_trip() -> None:
    """REQ-P7-LOGIC-007: cropping each rect returns the exact source pixels."""
    sprites = _mixed_sprites()
    by_name = {name: buf for name, buf in sprites}
    result = pack_atlas(sprites, padding=0, max_dimension=64)
    for placement in result.placements:
        src = by_name[placement.name]
        crop = result.image.region(placement.x, placement.y, placement.w, placement.h)
        assert np.array_equal(crop.data, src.data)


def test_pack_atlas_round_trip_with_padding() -> None:
    """REQ-P7-LOGIC-007: padding reserves a gap yet rects still round-trip exactly."""
    sprites = _mixed_sprites()
    by_name = {name: buf for name, buf in sprites}
    result = pack_atlas(sprites, padding=2, max_dimension=64)
    for i, a in enumerate(result.placements):
        for b in result.placements[i + 1 :]:
            assert not rects_overlap(a, b)
        crop = result.image.region(a.x, a.y, a.w, a.h)
        assert np.array_equal(crop.data, by_name[a.name].data)


def test_pack_atlas_defaults_from_constants() -> None:
    """REQ-P7-LOGIC-012: default padding / max_dimension come from constants."""
    result = pack_atlas([sprite("0", 4, 4, RED)])
    assert DEFAULT_ATLAS_PADDING == 0
    # D-1b (AGT-03): MAX_ATLAS_DIMENSION is re-aligned to the buildable platform
    # 8K width ceiling (7680), NOT the former 8192 which exceeded MAX_CANVAS_WIDTH
    # and let a packed sheet raise PixelBufferError at allocation. Compare against
    # the constant, not a literal, so the two can never silently drift apart again.
    assert MAX_ATLAS_DIMENSION == MAX_CANVAS_WIDTH
    assert result.width >= 4 and result.height >= 4


# --------------------------------------------------------------------------- #
# Validation + fit-or-error                                                    #
# --------------------------------------------------------------------------- #


def test_pack_atlas_cannot_fit_raises() -> None:
    """REQ-P7-LOGIC-006: a set too large for max_dimension raises AtlasError."""
    with pytest.raises(AtlasError, match="does not fit"):
        pack_atlas([sprite("0", 10, 10, RED)], max_dimension=4)


def test_pack_atlas_single_frame_exceeds_max_dimension_raises_promptly() -> None:
    """REQ-P7-LOGIC-006 (regression): a single 16x16 frame with max_dimension=1 is
    unsatisfiable, so the pre-flight feasibility guard raises AtlasError *promptly*
    (no hang) with a message naming the frame and its required-vs-max size."""
    start = time.perf_counter()
    with pytest.raises(AtlasError, match="does not fit") as exc_info:
        pack_atlas([sprite("hero", 16, 16, RED)], max_dimension=1)
    # The guard is eager (fires before the delegated packer), so it terminates
    # essentially instantly rather than spinning — a generous ceiling suffices.
    assert time.perf_counter() - start < 1.0
    message = str(exc_info.value)
    assert "exceeds max_dimension" in message
    assert "hero" in message and "16x16" in message


def test_pack_atlas_padded_cell_exceeds_max_dimension_raises() -> None:
    """REQ-P7-LOGIC-006 (regression): padding inflates a 4x4 frame to a 6x6 cell,
    which exceeds max_dimension=4, so the guard rejects it (the *padded* cell, not
    the bare frame, is what must fit)."""
    with pytest.raises(AtlasError, match="does not fit") as exc_info:
        pack_atlas([sprite("tile", 4, 4, GREEN)], padding=2, max_dimension=4)
    message = str(exc_info.value)
    assert "exceeds max_dimension" in message
    assert "6x6" in message


def test_pack_atlas_collective_overflow_raises() -> None:
    """REQ-P7-LOGIC-006 (regression): frames that each fit max_dimension alone but
    cannot fit *together* surface AtlasError via the wrapped CompactionError — the
    other unsatisfiable path (distinct from the single-frame pre-flight guard) still
    raises, not hangs. Two 8x8 cells cannot share an 8x8 atlas."""
    sprites = [sprite("a", 8, 8, RED), sprite("b", 8, 8, BLUE)]
    with pytest.raises(AtlasError, match="atlas does not fit") as exc_info:
        pack_atlas(sprites, padding=0, max_dimension=8)
    # Each frame individually satisfies the pre-flight guard (8 == max_dimension),
    # so this is the delegated packer's collective-overflow signal, not the guard.
    assert "exceeds max_dimension" not in str(exc_info.value)


def test_pack_atlas_oversized_axis_raises_atlas_error_not_pixelbuffer() -> None:
    """D-1b (AGT-03 S2 regression): an atlas that exceeds the *buildable* per-axis
    ceiling surfaces :class:`AtlasError`, never an escaping :class:`PixelBufferError`.

    A 10x4320 frame with padding=1 inflates to a padded cell of 11x4321. Even with
    ``max_dimension=8192`` (above the former, now-removed 8192 literal), the effective
    per-axis ceiling is clamped to ``min(8192, MAX_CANVAS_WIDTH=7680)`` x
    ``min(8192, MAX_CANVAS_HEIGHT=4320)`` = 7680x4320. The padded height 4321 exceeds
    4320, so the packed sheet could never be materialised as a PixelBuffer (whose hard
    cap is 7680x4320). Before D-1b the mismatched 8192 bound let such a sheet reach
    buffer allocation and raise PixelBufferError (a DIFFERENT class); now the atlas
    domain rejects it eagerly as AtlasError. ``pytest.raises(AtlasError)`` is itself
    the leak guard — PixelBufferError is not an AtlasError subclass, so were it to
    escape this call would fail rather than pass — and the isinstance assertion
    documents the contract explicitly.
    """
    with pytest.raises(AtlasError) as exc_info:
        pack_atlas([sprite("tall", 10, 4320, RED)], padding=1, max_dimension=8192)
    # No PixelBufferError leaks: the raised error is an AtlasError and NOT the
    # buffer-domain error the pre-D-1b (8192) bound would have surfaced.
    assert not isinstance(exc_info.value, PixelBufferError)
    message = str(exc_info.value)
    assert "does not fit" in message
    assert "exceeds max_dimension" in message
    # The message names the padded cell (4321 tall) and the buildable ceiling.
    assert "4321" in message
    assert f"{MAX_CANVAS_WIDTH}x{MAX_CANVAS_HEIGHT}" in message


def test_pack_atlas_boundary_sheet_builds_successfully() -> None:
    """D-1b (AGT-03): a frame that fills the buildable ceiling EXACTLY still packs.

    A single 7680x4320 (=MAX_CANVAS_WIDTH x MAX_CANVAS_HEIGHT) frame with padding=0 sits
    right on the per-axis ceiling, so the feasibility guard admits it and the sheet is
    materialised as a full-size PixelBuffer without raising — proving the D-1b alignment
    rejects only the genuinely-unbuildable case, not a feasible boundary one.
    """
    result = pack_atlas(
        [sprite("full", MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT, RED)],
        padding=0,
        max_dimension=8192,
    )
    assert result.width <= MAX_CANVAS_WIDTH
    assert result.height <= MAX_CANVAS_HEIGHT
    (placement,) = result.placements
    assert (placement.w, placement.h) == (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
    assert result.image.width == result.width
    assert result.image.height == result.height


def test_pack_atlas_empty_raises() -> None:
    """REQ-P7-LOGIC-006: an empty sprite set is a domain error."""
    with pytest.raises(AtlasError, match="empty"):
        pack_atlas([])


@pytest.mark.parametrize("padding", [-1, True])
def test_pack_atlas_bad_padding(padding) -> None:
    """REQ-P7-LOGIC-012: padding must be a non-negative, non-bool int."""
    with pytest.raises(AtlasError, match="padding"):
        pack_atlas([sprite("0", 4, 4, RED)], padding=padding)


@pytest.mark.parametrize("max_dimension", [0, -1, True])
def test_pack_atlas_bad_max_dimension(max_dimension) -> None:
    """REQ-P7-LOGIC-012: max_dimension must be a positive, non-bool int."""
    with pytest.raises(AtlasError, match="max_dimension"):
        pack_atlas([sprite("0", 4, 4, RED)], max_dimension=max_dimension)


def test_pack_atlas_duplicate_name_raises() -> None:
    """REQ-P7-LOGIC-006: duplicate sprite names are rejected."""
    with pytest.raises(AtlasError, match="duplicate"):
        pack_atlas([sprite("dup", 4, 4, RED), sprite("dup", 4, 4, GREEN)])


def test_pack_atlas_non_rgba_raises() -> None:
    """REQ-P7-LOGIC-006: a non-RGBA sprite is rejected."""
    with pytest.raises(AtlasError, match="RGBA"):
        pack_atlas([("i", PixelBuffer(4, 4, ColorMode.INDEXED))])


# --------------------------------------------------------------------------- #
# Hypothesis — random frame-size sets are always non-overlapping + in-bounds   #
# --------------------------------------------------------------------------- #


@given(
    sizes=st.lists(
        st.tuples(st.integers(1, 12), st.integers(1, 12)),
        min_size=1,
        max_size=8,
    )
)
def test_pack_atlas_non_overlap_property(sizes: List[Tuple[int, int]]) -> None:
    """REQ-P7-LOGIC-006/-007: packing any small size set is non-overlapping,

    in-bounds, and round-trips pixel-for-pixel."""
    colors = [(i * 20 % 256, 0, 0, 255) for i in range(len(sizes))]
    sprites = [sprite(str(i), w, h, colors[i]) for i, (w, h) in enumerate(sizes)]
    by_name = {name: buf for name, buf in sprites}
    result = pack_atlas(sprites, padding=0, max_dimension=256)
    placements = result.placements
    for i, a in enumerate(placements):
        assert a.x >= 0 and a.y >= 0
        assert a.x + a.w <= result.width and a.y + a.h <= result.height
        assert np.array_equal(
            result.image.region(a.x, a.y, a.w, a.h).data, by_name[a.name].data
        )
        for b in placements[i + 1 :]:
            assert not rects_overlap(a, b)
