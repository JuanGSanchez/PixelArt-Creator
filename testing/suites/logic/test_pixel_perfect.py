"""Tests for pixelart_creator.logic.pixel_perfect (REQ-P2-LOGIC-012).

One test per SC-L012 behaviour, plus Hypothesis invariants (idempotence;
endpoints preserved; no elbow triple survives). Zero Qt; deterministic.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pixelart_creator.logic.pixel_perfect import pixel_perfect


def _has_elbow(coords):
    """Whether any consecutive triple forms a removable L-elbow."""
    for i in range(len(coords) - 2):
        a, b, c = coords[i], coords[i + 1], coords[i + 2]
        if (
            (a[0] == b[0] or a[1] == b[1])
            and (c[0] == b[0] or c[1] == b[1])
            and a[0] != c[0]
            and a[1] != c[1]
        ):
            return True
    return False


def test_sc_l012_1_l_triple_loses_its_elbow_pixel():
    # (0,0)->(1,0)->(1,1): (1,0) is the elbow; removing it leaves a clean step.
    assert pixel_perfect([(0, 0), (1, 0), (1, 1)]) == [(0, 0), (1, 1)]


def test_sc_l012_2_straight_line_is_unchanged():
    line = [(0, 0), (1, 0), (2, 0), (3, 0)]
    assert pixel_perfect(line) == line


def test_sc_l012_2_diagonal_line_is_unchanged():
    diag = [(0, 0), (1, 1), (2, 2), (3, 3)]
    assert pixel_perfect(diag) == diag


def test_sc_l012_2_idempotent_on_already_clean_result():
    once = pixel_perfect([(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)])
    assert pixel_perfect(once) == once


def test_sc_l012_3_surviving_pixels_keep_original_order():
    result = pixel_perfect([(0, 0), (1, 0), (1, 1), (2, 1)])
    # endpoints preserved and order is monotone along the path.
    assert result[0] == (0, 0)
    assert result[-1] == (2, 1)


def test_sc_l012_4_deterministic_for_identical_input():
    coords = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2)]
    assert pixel_perfect(coords) == pixel_perfect(list(coords))


def test_endpoints_never_removed():
    # A 3-pixel L: the two endpoints must survive, only the middle drops.
    result = pixel_perfect([(0, 0), (0, 1), (1, 1)])
    assert (0, 0) in result and (1, 1) in result


def test_consecutive_duplicates_are_collapsed():
    assert pixel_perfect([(2, 2), (2, 2), (2, 2)]) == [(2, 2)]


def test_empty_and_single_input():
    assert pixel_perfect([]) == []
    assert pixel_perfect([(5, 5)]) == [(5, 5)]


def test_staircase_cascades_to_clean_diagonal():
    # A pixel staircase should thin toward a clean diagonal (no elbows remain).
    stair = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2), (3, 3)]
    result = pixel_perfect(stair)
    assert not _has_elbow(result)
    assert result[0] == (0, 0) and result[-1] == (3, 3)


# --- Hypothesis invariants ------------------------------------------------


@st.composite
def _walk(draw):
    """A connected 4/8-neighbour freehand walk of integer coordinates."""
    n = draw(st.integers(min_value=1, max_value=25))
    x = draw(st.integers(-5, 5))
    y = draw(st.integers(-5, 5))
    coords = [(x, y)]
    for _ in range(n):
        dx = draw(st.sampled_from([-1, 0, 1]))
        dy = draw(st.sampled_from([-1, 0, 1]))
        x += dx
        y += dy
        coords.append((x, y))
    return coords


@settings(max_examples=200, derandomize=True)
@given(coords=_walk())
def test_property_result_has_no_elbow(coords):
    assert not _has_elbow(pixel_perfect(coords))


@settings(max_examples=200, derandomize=True)
@given(coords=_walk())
def test_property_idempotent(coords):
    once = pixel_perfect(coords)
    assert pixel_perfect(once) == once


@settings(max_examples=200, derandomize=True)
@given(coords=_walk())
def test_property_endpoints_preserved(coords):
    result = pixel_perfect(coords)
    # first and last distinct points are preserved.
    assert result[0] == coords[0]
    assert result[-1] == coords[-1]
