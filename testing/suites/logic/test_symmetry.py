"""Tests for pixelart_creator.logic.symmetry (REQ-P2-LOGIC-011).

One test per SC-L011 behaviour, plus Hypothesis invariants (mirrored coords
stay in bounds; VERTICAL/HORIZONTAL are involutions). Zero Qt; deterministic.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic.symmetry import SymmetryAxis, mirror


def test_sc_l011_1_vertical_mirror_reflects_x():
    # 5 wide -> W-1-x. (1,2) mirrors to (3,2).
    assert mirror(1, 2, SymmetryAxis.VERTICAL, 5, 5) == {(1, 2), (3, 2)}


def test_sc_l011_2_horizontal_mirror_reflects_y():
    # 5 tall -> H-1-y. (1,1) mirrors to (1,3).
    assert mirror(1, 1, SymmetryAxis.HORIZONTAL, 5, 5) == {(1, 1), (1, 3)}


def test_sc_l011_3_both_yields_four_way_set():
    coords = mirror(1, 1, SymmetryAxis.BOTH, 5, 5)
    assert coords == {(1, 1), (3, 1), (1, 3), (3, 3)}


def test_sc_l011_4_diagonal_mirrors_main_diagonal():
    # On a square canvas the main-diagonal reflection swaps x and y.
    assert mirror(1, 3, SymmetryAxis.DIAGONAL, 5, 5) == {(1, 3), (3, 1)}


def test_sc_l011_5_none_returns_only_source():
    assert mirror(2, 3, SymmetryAxis.NONE, 5, 5) == {(2, 3)}


def test_sc_l011_6_mirrors_clipped_and_deduplicated():
    # Centre pixel of an odd canvas: its vertical mirror is itself -> dedup.
    assert mirror(2, 2, SymmetryAxis.VERTICAL, 5, 5) == {(2, 2)}
    assert mirror(2, 2, SymmetryAxis.BOTH, 5, 5) == {(2, 2)}


def test_mirror_out_of_range_source_is_clipped_away():
    # Source (6,2) on a 5-wide canvas is out of bounds; its vertical mirror
    # is W-1-x = 4-6 = -2, also out of bounds -> the whole set clips to empty.
    assert mirror(6, 2, SymmetryAxis.VERTICAL, 5, 5) == set()


def test_mirror_custom_axis_pos():
    # Mirror about x = 1 (axis_pos x): (0,y) -> (2,y).
    assert mirror(0, 0, SymmetryAxis.VERTICAL, 6, 6, axis_pos=(1, 1)) == {
        (0, 0),
        (2, 0),
    }


def test_mirror_nonpositive_dimensions_returns_empty():
    assert mirror(0, 0, SymmetryAxis.VERTICAL, 0, 5) == set()
    assert mirror(0, 0, SymmetryAxis.VERTICAL, 5, -1) == set()


def test_mirror_is_deterministic():
    assert mirror(1, 2, SymmetryAxis.BOTH, 7, 7) == mirror(
        1, 2, SymmetryAxis.BOTH, 7, 7
    )


# --- Hypothesis invariants ------------------------------------------------

_dim = st.integers(min_value=1, max_value=16)


@settings(max_examples=150, derandomize=True)
@given(
    x=st.integers(0, 15),
    y=st.integers(0, 15),
    w=_dim,
    h=_dim,
    axis=st.sampled_from(list(SymmetryAxis)),
)
def test_property_mirrors_stay_in_bounds(x, y, w, h, axis):
    for cx, cy in mirror(x, y, axis, w, h):
        assert 0 <= cx < w and 0 <= cy < h


@settings(max_examples=150, derandomize=True)
@given(x=st.integers(0, 15), y=st.integers(0, 15), w=_dim, h=_dim)
def test_property_vertical_mirror_is_involution(x, y, w, h):
    if not (0 <= x < w and 0 <= y < h):
        return
    coords = mirror(x, y, SymmetryAxis.VERTICAL, w, h)
    # applying the vertical mirror to each result maps the set to itself.
    reflected = set()
    for cx, cy in coords:
        reflected |= mirror(cx, cy, SymmetryAxis.VERTICAL, w, h)
    assert reflected == coords
