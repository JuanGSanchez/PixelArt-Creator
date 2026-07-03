"""Tests for pixelart_creator.logic.autotile (REQ-P6-LOGIC-010, ADR-0013).

Blob-47 resolver: the 256 raw 8-neighbour masks collapse to exactly 47 display
frames under edge-implies-corner gating, resolved through a load-time LUT so
resolution is deterministic and total (SC-L010-1). Covers the LUT invariants,
neighbour-mask packing, ruleset validation, and the determinism / exhaustive
256->47 collapse property (Hypothesis). Zero Qt; deterministic.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.autotile import (
    BLOB_TILE_COUNT,
    AutotileError,
    AutotileRuleset,
    mask_from_neighbours,
    resolve_display_gid,
    resolve_display_index,
)

# The private Blob-47 bit weights (module-local convention) — used only as a
# test oracle to prove mask_from_neighbours applies them in exactly one place.
_TL, _T, _TR, _L, _R, _BL, _B, _BR = 1, 2, 4, 8, 16, 32, 64, 128


def _frames(start: int = 1) -> list[int]:
    """Return a valid 47-gid frame atlas."""
    return list(range(start, start + BLOB_TILE_COUNT))


# --------------------------------------------------------------------------- #
# LUT invariants (256 -> 47 collapse)                                         #
# --------------------------------------------------------------------------- #


def test_blob_tile_count_is_47():
    assert BLOB_TILE_COUNT == 47


def test_resolve_all_masks_in_range_0_to_46():
    for mask in range(256):
        assert 0 <= resolve_display_index(mask) <= BLOB_TILE_COUNT - 1


def test_256_masks_collapse_to_exactly_47_frames_exhaustively():
    # SC-L010-1: the collapse is exhaustive and consistent — every one of the 47
    # frame indices is produced and no index outside 0..46 appears.
    produced = {resolve_display_index(mask) for mask in range(256)}
    assert produced == set(range(BLOB_TILE_COUNT))


def test_edge_implies_corner_gating_clears_ungated_corners():
    # A corner bit is meaningful only when BOTH its adjacent cardinal edges are
    # set; a lone corner collapses onto the empty-neighbourhood frame.
    empty = resolve_display_index(0)
    assert resolve_display_index(_TL) == empty
    assert resolve_display_index(_TR) == empty
    assert resolve_display_index(_BL) == empty
    assert resolve_display_index(_BR) == empty


def test_gated_corner_changes_frame_when_both_edges_present():
    # T|L present: adding the TL corner is now meaningful and must change frame.
    both_edges = _T | _L
    assert resolve_display_index(both_edges | _TL) != resolve_display_index(both_edges)


@pytest.mark.parametrize("bad", [256, -1, 0x100, 1000])
def test_resolve_index_rejects_out_of_range(bad):
    with pytest.raises(AutotileError):
        resolve_display_index(bad)


@pytest.mark.parametrize("bad", [True, False, 1.5, "3", None])
def test_resolve_index_rejects_non_int(bad):
    with pytest.raises(AutotileError):
        resolve_display_index(bad)


# --------------------------------------------------------------------------- #
# Neighbour-mask packing                                                      #
# --------------------------------------------------------------------------- #


def test_mask_all_false_is_zero_all_true_sets_eight_bits():
    assert mask_from_neighbours(*([False] * 8)) == 0
    full = mask_from_neighbours(*([True] * 8))
    assert bin(full).count("1") == 8
    assert full == 0xFF


def test_mask_from_neighbours_matches_bit_weight_oracle():
    # Proves the TL=1..BR=128 convention is applied here (and only here).
    order = (_TL, _T, _TR, _L, _R, _BL, _B, _BR)
    for i, weight in enumerate(order):
        flags = [False] * 8
        flags[i] = True
        assert mask_from_neighbours(*flags) == weight


def test_mask_from_neighbours_is_bitwise_or_of_contributions():
    m = mask_from_neighbours(True, False, True, False, True, False, True, False)
    assert m == (_TL | _TR | _R | _B)


# --------------------------------------------------------------------------- #
# AutotileRuleset validation                                                  #
# --------------------------------------------------------------------------- #


def test_ruleset_valid_stores_frames_as_tuple():
    rs = AutotileRuleset(7, _frames())
    assert rs.terrain_gid == 7
    assert rs.frame_gids == tuple(_frames())
    assert isinstance(rs.frame_gids, tuple)


def test_ruleset_is_frozen():
    rs = AutotileRuleset(1, _frames())
    with pytest.raises(Exception):
        rs.terrain_gid = 2  # type: ignore[misc]


@pytest.mark.parametrize("terrain", [0, -1, True, 1.0, "1", None])
def test_ruleset_rejects_bad_terrain(terrain):
    with pytest.raises(AutotileError):
        AutotileRuleset(terrain, _frames())


@pytest.mark.parametrize("frames", [_frames()[:-1], _frames() + [99], []])
def test_ruleset_rejects_wrong_frame_count(frames):
    with pytest.raises(AutotileError):
        AutotileRuleset(1, frames)


@pytest.mark.parametrize("bad_frame", [-1, True, 1.5, "x"])
def test_ruleset_rejects_bad_frame_gid(bad_frame):
    frames = _frames()
    frames[10] = bad_frame
    with pytest.raises(AutotileError):
        AutotileRuleset(1, frames)


def test_resolve_display_gid_chains_index_into_frames():
    rs = AutotileRuleset(1, _frames(start=100))
    for mask in range(256):
        assert (
            resolve_display_gid(rs, mask) == rs.frame_gids[resolve_display_index(mask)]
        )


def test_resolve_display_gid_rejects_non_ruleset():
    with pytest.raises(AutotileError):
        resolve_display_gid(object(), 0)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Property: determinism + exhaustive collapse (pure LUT)                      #
# --------------------------------------------------------------------------- #


@given(mask=st.integers(min_value=0, max_value=255))
def test_property_resolution_is_deterministic(mask):
    # Same neighbourhood -> same display frame, always (pure LUT, no RNG/time).
    first = resolve_display_index(mask)
    assert first == resolve_display_index(mask)
    assert 0 <= first < BLOB_TILE_COUNT


@given(
    flags=st.tuples(*([st.booleans()] * 8)),
)
def test_property_mask_then_resolve_is_stable(flags):
    mask = mask_from_neighbours(*flags)
    assert 0 <= mask <= 255
    idx = resolve_display_index(mask)
    assert idx == resolve_display_index(mask_from_neighbours(*flags))


@given(mask=st.integers(min_value=0, max_value=255))
def test_property_lone_corner_addition_is_idempotent_when_edges_absent(mask):
    # Adding a corner bit whose two edges are not both present cannot change the
    # resolved frame (edge-implies-corner gating is stable under such additions).
    base = resolve_display_index(mask)
    for corner, e1, e2 in ((_TL, _T, _L), (_TR, _T, _R), (_BL, _B, _L), (_BR, _B, _R)):
        if not (mask & e1 and mask & e2):
            assert resolve_display_index((mask | corner) & 0xFF) == base
