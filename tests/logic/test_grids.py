"""Tests for pixelart_creator.logic.grids — isometric + perspective geometry.

The Phase-9 [GEO] backbone (REQ-P9-LOGIC-001..004, -008, -009): the isometric
world<->screen transform is a pure, exact, invertible mapping and its snap is
idempotent and returns the nearest lattice vertex (2:1 dimetric default AND a
true-iso ratio); perspective_snap direction-locks to the nearest vanishing line
within tolerance (and None beyond it) for 1-/2-/3-point configs; and
perspective_guide_lines produces the documented deterministic fan. Round-trip
identity + snap idempotence are proven with Hypothesis over random integer
lattice coords and configs (conftest "ci" profile → derandomised, portable).

Zero Qt. Maps to SC-L001-1 / SC-L002-1 / SC-L003-1 / SC-L004-1.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.grids import (
    GridError,
    GuideLine,
    IsoGridConfig,
    PerspectiveConfig,
    VanishingPoint,
    iso_screen_to_world,
    iso_snap_cell,
    iso_snap_vertex,
    iso_world_to_screen,
    perspective_guide_lines,
    perspective_snap,
)

# Representative configs: 2:1 dimetric default and a true-isometric ratio.
DIMETRIC = IsoGridConfig(origin=(0.0, 0.0), tile_width=32, ratio=2.0)
TRUE_ISO = IsoGridConfig(origin=(11.0, -7.0), tile_width=64, ratio=math.sqrt(3.0))


# --------------------------------------------------------------------------- #
# IsoGridConfig construction + validation                                     #
# --------------------------------------------------------------------------- #


def test_default_iso_ratio_is_single_sourced_from_constants():
    # Article II / S12: the default ratio is the named constant, not a literal.
    assert IsoGridConfig().ratio == constants.DEFAULT_ISO_GRID_RATIO
    assert constants.DEFAULT_ISO_GRID_RATIO == 2.0


def test_iso_half_dimensions():
    cfg = IsoGridConfig(tile_width=32, ratio=2.0)
    assert cfg.half_width == 16.0
    # 2:1 dimetric => h = W/4.
    assert cfg.half_height == 8.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"origin": (0, 0, 0)},  # not an (x, y) pair
        {"origin": ("a", 0)},  # non-numeric component
        {"tile_width": True},  # bool is not an int
        {"tile_width": 1.5},  # float is not an int
        {"tile_width": constants.MIN_GRID_SPACING - 1},  # below bound
        {"tile_width": constants.MAX_GRID_SPACING + 1},  # above bound
        {"ratio": 0.0},  # not > 0
        {"ratio": -1.0},  # negative
        {"ratio": float("inf")},  # non-finite
        {"ratio": True},  # bool is not a number
    ],
)
def test_iso_config_rejects_invalid(kwargs):
    with pytest.raises(GridError):
        IsoGridConfig(**kwargs)


def test_iso_config_accepts_spacing_bounds():
    # The inclusive bounds must construct cleanly.
    IsoGridConfig(tile_width=constants.MIN_GRID_SPACING)
    IsoGridConfig(tile_width=constants.MAX_GRID_SPACING)


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-001 — invertible world<->screen transform                      #
# --------------------------------------------------------------------------- #


def test_iso_world_to_screen_documented_formula():
    # sx = (i-j)*w + ox ; sy = (i+j)*h + oy.
    cfg = IsoGridConfig(origin=(100.0, 50.0), tile_width=32, ratio=2.0)
    sx, sy = iso_world_to_screen(3, 1, cfg)
    assert sx == (3 - 1) * 16.0 + 100.0
    assert sy == (3 + 1) * 8.0 + 50.0


@pytest.mark.parametrize("cfg", [DIMETRIC, TRUE_ISO])
def test_iso_round_trip_exact_on_lattice(cfg):
    # SC-L001-1: world -> screen -> world is exact on integer lattice points.
    for i in range(-5, 6):
        for j in range(-5, 6):
            sx, sy = iso_world_to_screen(i, j, cfg)
            ri, rj = iso_screen_to_world(sx, sy, cfg)
            assert math.isclose(ri, i, abs_tol=1e-9)
            assert math.isclose(rj, j, abs_tol=1e-9)


@pytest.mark.parametrize("cfg", [DIMETRIC, TRUE_ISO])
def test_iso_screen_round_trip_continuous(cfg):
    # The inverse composed the other way is also identity (continuous points).
    for sx, sy in [(0.0, 0.0), (13.5, -4.25), (-100.0, 200.0)]:
        i, j = iso_screen_to_world(sx, sy, cfg)
        rx, ry = iso_world_to_screen(i, j, cfg)
        assert math.isclose(rx, sx, abs_tol=1e-9)
        assert math.isclose(ry, sy, abs_tol=1e-9)


@given(
    i=st.integers(min_value=-1000, max_value=1000),
    j=st.integers(min_value=-1000, max_value=1000),
    tile_width=st.integers(min_value=constants.MIN_GRID_SPACING, max_value=256),
    ratio=st.floats(
        min_value=0.25, max_value=8.0, allow_nan=False, allow_infinity=False
    ),
    ox=st.floats(
        min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    oy=st.floats(
        min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
)
def test_property_iso_round_trip_identity(i, j, tile_width, ratio, ox, oy):
    # REQ-P9-LOGIC-001/-009 (Hypothesis): world->screen->world is identity on the
    # lattice for arbitrary integer coords + configs.
    cfg = IsoGridConfig(origin=(ox, oy), tile_width=tile_width, ratio=ratio)
    sx, sy = iso_world_to_screen(i, j, cfg)
    ri, rj = iso_screen_to_world(sx, sy, cfg)
    assert math.isclose(ri, i, rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(rj, j, rel_tol=1e-9, abs_tol=1e-6)


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-002 — snap to nearest vertex + idempotence                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("cfg", [DIMETRIC, TRUE_ISO])
def test_iso_snap_returns_a_lattice_vertex(cfg):
    # A snapped point lands exactly on some integer lattice vertex.
    sx, sy = iso_snap_vertex(13.7, -4.2, cfg)
    i, j = iso_screen_to_world(sx, sy, cfg)
    assert math.isclose(i, round(i), abs_tol=1e-9)
    assert math.isclose(j, round(j), abs_tol=1e-9)


@pytest.mark.parametrize("cfg", [DIMETRIC, TRUE_ISO])
def test_iso_snap_is_idempotent(cfg):
    # SC-L002-1: snapping an already-snapped point returns it unchanged.
    once = iso_snap_vertex(21.3, 7.8, cfg)
    twice = iso_snap_vertex(once[0], once[1], cfg)
    assert twice == pytest.approx(once)


@pytest.mark.parametrize("cfg", [DIMETRIC, TRUE_ISO])
def test_iso_snap_returns_nearest_vertex(cfg):
    # A point very close to a known vertex snaps to that vertex, not a neighbour.
    target = iso_world_to_screen(2, -3, cfg)
    nudged = (target[0] + 0.4, target[1] - 0.3)
    snapped = iso_snap_vertex(*nudged, cfg)
    assert snapped == pytest.approx(target)


def test_iso_snap_half_up_tie_break_is_deterministic():
    # round-half-up: a coord exactly between two lattice points resolves upward.
    cfg = IsoGridConfig(origin=(0.0, 0.0), tile_width=32, ratio=2.0)
    # Screen point whose world coords are exactly (0.5, 0.5) -> rounds to (1, 1).
    sx, sy = iso_world_to_screen(0.5, 0.5, cfg)
    snapped = iso_snap_vertex(sx, sy, cfg)
    assert snapped == pytest.approx(iso_world_to_screen(1, 1, cfg))


@given(
    sx=st.floats(
        min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    sy=st.floats(
        min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    tile_width=st.integers(min_value=constants.MIN_GRID_SPACING, max_value=128),
    ratio=st.floats(
        min_value=0.5, max_value=4.0, allow_nan=False, allow_infinity=False
    ),
)
def test_property_iso_snap_idempotent(sx, sy, tile_width, ratio):
    # REQ-P9-LOGIC-002/-009 (Hypothesis): snap∘snap == snap for any input.
    cfg = IsoGridConfig(tile_width=tile_width, ratio=ratio)
    once = iso_snap_vertex(sx, sy, cfg)
    twice = iso_snap_vertex(once[0], once[1], cfg)
    assert twice[0] == pytest.approx(once[0], abs=1e-6)
    assert twice[1] == pytest.approx(once[1], abs=1e-6)


def test_iso_snap_cell_floors_to_containing_cell():
    cfg = IsoGridConfig(origin=(0.0, 0.0), tile_width=32, ratio=2.0)
    # A point just inside cell (2, -1).
    sx, sy = iso_world_to_screen(2.3, -0.6, cfg)
    assert iso_snap_cell(sx, sy, cfg) == (2, -1)


def test_iso_transform_rejects_non_numeric():
    with pytest.raises(GridError):
        iso_world_to_screen("x", 0, DIMETRIC)  # type: ignore[arg-type]
    with pytest.raises(GridError):
        iso_screen_to_world(0, float("nan"), DIMETRIC)


# --------------------------------------------------------------------------- #
# VanishingPoint / PerspectiveConfig construction + validation                #
# --------------------------------------------------------------------------- #


def test_vanishing_point_normalises_direction():
    vp = VanishingPoint(direction=(3.0, 4.0))
    assert vp.direction == pytest.approx((0.6, 0.8))


def test_vanishing_point_requires_position_or_direction():
    with pytest.raises(GridError):
        VanishingPoint()


def test_vanishing_point_rejects_zero_direction():
    with pytest.raises(GridError):
        VanishingPoint(direction=(0.0, 0.0))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": 0},  # below 1
        {"mode": constants.MAX_PERSPECTIVE_VANISHING_POINTS + 1},  # above bound
        {"mode": True},  # bool
        {"mode": 1.0},  # float
    ],
)
def test_perspective_config_rejects_bad_mode(kwargs):
    with pytest.raises(GridError):
        PerspectiveConfig(
            vanishing_points=(VanishingPoint(position=(10.0, 0.0)),), **kwargs
        )


def test_perspective_config_requires_a_vanishing_point():
    with pytest.raises(GridError):
        PerspectiveConfig(mode=1, vanishing_points=())


def test_perspective_config_rejects_too_many_vps():
    vps = tuple(
        VanishingPoint(position=(float(k), 0.0))
        for k in range(constants.MAX_PERSPECTIVE_VANISHING_POINTS + 1)
    )
    with pytest.raises(GridError):
        PerspectiveConfig(mode=1, vanishing_points=vps)


def test_perspective_config_rejects_non_vp_entry():
    with pytest.raises(GridError):
        PerspectiveConfig(mode=1, vanishing_points=("nope",))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-003 — perspective guide-line construction                       #
# --------------------------------------------------------------------------- #


def test_perspective_guide_lines_finite_vp_count_and_endpoints():
    # SC-L003-1: one segment per (VP × sample); finite-VP segments end at the VP.
    vp = VanishingPoint(position=(100.0, 0.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    lines = perspective_guide_lines(cfg, 3, edge_start=(0.0, 0.0), edge_end=(0.0, 60.0))
    assert len(lines) == 3
    assert all(isinstance(ln, GuideLine) for ln in lines)
    # Sample points evenly on the edge; each ends at the VP.
    assert lines[0].p0 == (0.0, 0.0)
    assert lines[1].p0 == (0.0, 30.0)
    assert lines[2].p0 == (0.0, 60.0)
    for ln in lines:
        assert ln.p1 == (100.0, 0.0)


def test_perspective_guide_lines_two_vps():
    cfg = PerspectiveConfig(
        mode=2,
        vanishing_points=(
            VanishingPoint(position=(100.0, 0.0)),
            VanishingPoint(position=(-100.0, 0.0)),
        ),
    )
    lines = perspective_guide_lines(cfg, 4, edge_start=(0.0, 0.0), edge_end=(0.0, 90.0))
    assert len(lines) == 2 * 4


def test_perspective_guide_lines_single_sample():
    vp = VanishingPoint(position=(50.0, 50.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    lines = perspective_guide_lines(cfg, 1, edge_start=(1.0, 2.0), edge_end=(9.0, 9.0))
    assert len(lines) == 1
    # Single sample uses t=0 -> the edge start.
    assert lines[0].p0 == (1.0, 2.0)


def test_perspective_guide_lines_pseudo_vp_extends_along_direction():
    vp = VanishingPoint(direction=(1.0, 0.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    lines = perspective_guide_lines(cfg, 2, edge_start=(0.0, 0.0), edge_end=(0.0, 10.0))
    # span = edge length (10); segment extends 10 in the +x unit direction.
    assert lines[0].p1 == pytest.approx((10.0, 0.0))


def test_perspective_guide_lines_is_deterministic():
    vp = VanishingPoint(position=(100.0, 0.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    a = perspective_guide_lines(cfg, 5, edge_start=(0.0, 0.0), edge_end=(0.0, 40.0))
    b = perspective_guide_lines(cfg, 5, edge_start=(0.0, 0.0), edge_end=(0.0, 40.0))
    assert a == b


@pytest.mark.parametrize("samples", [0, -1, True, 2.0])
def test_perspective_guide_lines_rejects_bad_samples(samples):
    vp = VanishingPoint(position=(1.0, 1.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    with pytest.raises(GridError):
        perspective_guide_lines(
            cfg, samples, edge_start=(0.0, 0.0), edge_end=(1.0, 1.0)  # type: ignore[arg-type]
        )


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-004 — perspective snap (direction-lock, tolerance, tie-break)   #
# --------------------------------------------------------------------------- #


def test_perspective_snap_point_on_ray_snaps_to_itself():
    # A cursor exactly on a VP ray snaps to itself (err == 0 <= tolerance).
    anchor = (0.0, 0.0)
    vp = VanishingPoint(position=(10.0, 0.0))  # ray along +x
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    on_ray = (5.0, 0.0)
    snapped = perspective_snap(on_ray[0], on_ray[1], anchor, cfg, tolerance=1.0)
    assert snapped == pytest.approx(on_ray)


def test_perspective_snap_projects_onto_nearest_ray_within_tolerance():
    anchor = (0.0, 0.0)
    vp = VanishingPoint(position=(10.0, 0.0))  # ray along +x
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    # Point slightly off the +x ray: perpendicular error 0.5 <= tolerance.
    snapped = perspective_snap(5.0, 0.5, anchor, cfg, tolerance=1.0)
    assert snapped == pytest.approx((5.0, 0.0))


def test_perspective_snap_returns_none_beyond_tolerance():
    # SC-L004-1: beyond tolerance -> no snap.
    anchor = (0.0, 0.0)
    vp = VanishingPoint(position=(10.0, 0.0))
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    assert perspective_snap(5.0, 5.0, anchor, cfg, tolerance=1.0) is None


def test_perspective_snap_chooses_nearest_of_multiple_vps():
    anchor = (0.0, 0.0)
    cfg = PerspectiveConfig(
        mode=2,
        vanishing_points=(
            VanishingPoint(position=(10.0, 0.0)),  # +x ray
            VanishingPoint(position=(0.0, 10.0)),  # +y ray
        ),
    )
    # Point near the +y ray: should project onto +y.
    snapped = perspective_snap(0.3, 6.0, anchor, cfg, tolerance=1.0)
    assert snapped == pytest.approx((0.0, 6.0))


def test_perspective_snap_lowest_index_tie_break():
    # Equal perpendicular error to two symmetric rays -> lowest VP index wins.
    anchor = (0.0, 0.0)
    cfg = PerspectiveConfig(
        mode=2,
        vanishing_points=(
            VanishingPoint(direction=(1.0, 0.0)),  # +x
            VanishingPoint(direction=(0.0, 1.0)),  # +y
        ),
    )
    # (3, 3) is equidistant from both rays; index 0 (+x) wins -> projects to (3,0).
    snapped = perspective_snap(3.0, 3.0, anchor, cfg, tolerance=10.0)
    assert snapped == pytest.approx((3.0, 0.0))


def test_perspective_snap_skips_degenerate_vp_at_anchor():
    anchor = (5.0, 5.0)
    cfg = PerspectiveConfig(
        mode=2,
        vanishing_points=(
            VanishingPoint(position=(5.0, 5.0)),  # degenerate: on the anchor
            VanishingPoint(position=(15.0, 5.0)),  # +x ray from anchor
        ),
    )
    snapped = perspective_snap(9.0, 5.2, anchor, cfg, tolerance=1.0)
    assert snapped == pytest.approx((9.0, 5.0))


def test_perspective_snap_pseudo_vp_direction():
    anchor = (0.0, 0.0)
    vp = VanishingPoint(direction=(0.0, 1.0))  # +y axis-lock
    cfg = PerspectiveConfig(mode=1, vanishing_points=(vp,))
    snapped = perspective_snap(0.4, 8.0, anchor, cfg, tolerance=1.0)
    assert snapped == pytest.approx((0.0, 8.0))


@pytest.mark.parametrize("tolerance", [-1.0, float("inf"), float("nan")])
def test_perspective_snap_rejects_bad_tolerance(tolerance):
    cfg = PerspectiveConfig(
        mode=1, vanishing_points=(VanishingPoint(position=(1.0, 0.0)),)
    )
    with pytest.raises(GridError):
        perspective_snap(1.0, 1.0, (0.0, 0.0), cfg, tolerance)


def test_perspective_snap_rejects_malformed_anchor():
    cfg = PerspectiveConfig(
        mode=1, vanishing_points=(VanishingPoint(position=(1.0, 0.0)),)
    )
    with pytest.raises(GridError):
        perspective_snap(1.0, 1.0, (0.0,), cfg, tolerance=1.0)  # type: ignore[arg-type]


def test_perspective_snap_deterministic_repeated():
    cfg = PerspectiveConfig(
        mode=1, vanishing_points=(VanishingPoint(position=(10.0, 3.0)),)
    )
    a = perspective_snap(4.0, 2.0, (0.0, 0.0), cfg, tolerance=5.0)
    b = perspective_snap(4.0, 2.0, (0.0, 0.0), cfg, tolerance=5.0)
    assert a == b
