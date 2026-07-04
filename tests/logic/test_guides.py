"""Tests for pixelart_creator.logic.guides — guide snap, rulers, readout.

The Phase-9 [GEO] guides/rulers backbone (REQ-P9-LOGIC-005/-006/-009): snap_guides
snaps each axis to the nearest guide within tolerance and leaves points outside
tolerance unchanged (deterministic lowest-position tie-break);
screen_tolerance_to_doc = screen_px / zoom; ruler_ticks produce nice-number ticks
for representative zoom/axis windows; coordinate_readout floors screen -> doc.
Zero Qt. Maps to SC-L005-1 / SC-L006-1.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import constants
from pixelart_creator.logic.guides import (
    Guide,
    GuideError,
    GuideOrientation,
    RulerTick,
    coordinate_readout,
    ruler_ticks,
    screen_tolerance_to_doc,
    snap_axis,
    snap_guides,
)

V = GuideOrientation.VERTICAL
H = GuideOrientation.HORIZONTAL


# --------------------------------------------------------------------------- #
# Guide construction + validation                                             #
# --------------------------------------------------------------------------- #


def test_guide_stores_orientation_and_float_position():
    g = Guide(V, 10)
    assert g.orientation is V
    assert g.position == 10.0
    assert isinstance(g.position, float)


@pytest.mark.parametrize(
    "args",
    [
        ("vertical", 1.0),  # orientation not an enum
        (V, "x"),  # position not a number
        (V, True),  # bool
        (V, float("inf")),  # non-finite
    ],
)
def test_guide_rejects_invalid(args):
    with pytest.raises(GuideError):
        Guide(*args)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-005 — screen tolerance conversion                              #
# --------------------------------------------------------------------------- #


def test_screen_tolerance_to_doc_is_px_over_zoom():
    assert screen_tolerance_to_doc(8.0, 2.0) == 4.0
    assert screen_tolerance_to_doc(8.0, 0.5) == 16.0


def test_screen_tolerance_default_constant():
    # The default screen tolerance is the named constant (S12).
    assert constants.DEFAULT_SNAP_TOLERANCE_PX == 8
    assert screen_tolerance_to_doc(constants.DEFAULT_SNAP_TOLERANCE_PX, 1.0) == 8.0


@pytest.mark.parametrize(
    "tol,zoom",
    [(-1.0, 1.0), (1.0, 0.0), (1.0, -2.0), (float("nan"), 1.0), (1.0, float("inf"))],
)
def test_screen_tolerance_rejects_invalid(tol, zoom):
    with pytest.raises(GuideError):
        screen_tolerance_to_doc(tol, zoom)


def test_screen_tolerance_rejects_non_number_type():
    # Exercises the "must be a number" guard directly.
    with pytest.raises(GuideError):
        screen_tolerance_to_doc("x", 1.0)  # type: ignore[arg-type]
    with pytest.raises(GuideError):
        screen_tolerance_to_doc(1.0, None)  # type: ignore[arg-type]


def test_ruler_ticks_decade_advance_when_step_between_five_and_ten():
    # min_doc_step = 50/zoom lands in (5, 10) -> the nice ladder advances a decade.
    ticks = ruler_ticks(1000.0, zoom=50.0 / 6.0, offset=0.0, axis_pixels=800)
    assert ticks
    step = ticks[1].position - ticks[0].position
    assert step == 10.0  # advanced past {1,2,5} at 10^0 to 1·10^1


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-005 — snap_axis + snap_guides                                  #
# --------------------------------------------------------------------------- #


def test_snap_axis_snaps_within_tolerance():
    assert snap_axis(10.4, [10.0, 50.0], tolerance_doc=1.0) == 10.0


def test_snap_axis_leaves_value_outside_tolerance():
    assert snap_axis(10.4, [50.0], tolerance_doc=1.0) == 10.4


def test_snap_axis_lowest_position_tie_break():
    # Value exactly between two guides -> the lower position wins.
    assert snap_axis(15.0, [10.0, 20.0], tolerance_doc=10.0) == 10.0


def test_snap_axis_empty_positions_returns_value():
    assert snap_axis(3.0, [], tolerance_doc=5.0) == 3.0


def test_snap_guides_axes_independent():
    # SC-L005-1: vertical guides snap x, horizontal guides snap y; independently.
    guides = [Guide(V, 100.0), Guide(H, 50.0)]
    assert snap_guides(100.6, 49.7, guides, tolerance_doc=1.0) == (100.0, 50.0)


def test_snap_guides_only_x_when_no_horizontal_in_range():
    guides = [Guide(V, 100.0), Guide(H, 500.0)]
    x, y = snap_guides(100.4, 20.0, guides, tolerance_doc=1.0)
    assert x == 100.0
    assert y == 20.0  # unchanged: nearest horizontal guide out of tolerance


def test_snap_guides_no_snap_leaves_point():
    guides = [Guide(V, 100.0), Guide(H, 50.0)]
    assert snap_guides(5.0, 5.0, guides, tolerance_doc=1.0) == (5.0, 5.0)


def test_snap_guides_empty_set():
    assert snap_guides(3.0, 7.0, [], tolerance_doc=5.0) == (3.0, 7.0)


def test_snap_guides_rejects_over_max_guides():
    guides = [Guide(V, float(k)) for k in range(constants.MAX_GUIDES + 1)]
    with pytest.raises(GuideError):
        snap_guides(0.0, 0.0, guides, tolerance_doc=1.0)


def test_snap_guides_rejects_non_guide_entry():
    with pytest.raises(GuideError):
        snap_guides(0.0, 0.0, ["nope"], tolerance_doc=1.0)  # type: ignore[list-item]


@pytest.mark.parametrize(
    "x,y,tol",
    [
        (float("nan"), 0.0, 1.0),
        (0.0, float("inf"), 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, float("nan")),
    ],
)
def test_snap_guides_rejects_bad_numbers(x, y, tol):
    with pytest.raises(GuideError):
        snap_guides(x, y, [Guide(V, 1.0)], tolerance_doc=tol)


@given(
    x=st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    guide_pos=st.floats(
        min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False
    ),
    tol=st.floats(
        min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
    ),
)
def test_property_snap_guides_within_iff_close(x, guide_pos, tol):
    # REQ-P9-LOGIC-005: x snaps to the guide iff |x - guide| <= tolerance.
    guides = [Guide(V, guide_pos)]
    snapped_x, _ = snap_guides(x, 0.0, guides, tolerance_doc=tol)
    if abs(x - guide_pos) <= tol:
        assert snapped_x == pytest.approx(guide_pos)
    else:
        assert snapped_x == pytest.approx(x)


# --------------------------------------------------------------------------- #
# REQ-P9-LOGIC-006 — ruler ticks + coordinate readout                          #
# --------------------------------------------------------------------------- #


def test_ruler_ticks_are_nice_numbers_and_major():
    ticks = ruler_ticks(1000.0, zoom=1.0, offset=0.0, axis_pixels=500)
    assert ticks  # non-empty
    assert all(isinstance(t, RulerTick) for t in ticks)
    assert all(t.major for t in ticks)
    # Nice step at zoom 1.0, min label spacing 50px -> step 50; ticks at 0,50,...
    positions = [t.position for t in ticks]
    assert positions[0] == 0.0
    step = positions[1] - positions[0]
    mantissa = step / (10 ** math.floor(math.log10(step)))
    assert mantissa in (1.0, 2.0, 5.0)


def test_ruler_ticks_step_grows_when_zoomed_out():
    tight = ruler_ticks(10000.0, zoom=1.0, offset=0.0, axis_pixels=500)
    loose = ruler_ticks(10000.0, zoom=0.1, offset=0.0, axis_pixels=500)
    tight_step = tight[1].position - tight[0].position
    loose_step = loose[1].position - loose[0].position
    assert loose_step > tight_step


def test_ruler_ticks_respect_offset_window():
    ticks = ruler_ticks(10000.0, zoom=1.0, offset=200.0, axis_pixels=300)
    # Window is [200, 500]; every tick lies within it.
    assert all(200.0 <= t.position <= 500.0 for t in ticks)


def test_ruler_tick_labels_are_locale_independent_integers():
    ticks = ruler_ticks(1000.0, zoom=1.0, offset=0.0, axis_pixels=500)
    for t in ticks:
        # Integer positions produce plain integer strings, no separators.
        assert "," not in t.label
        assert t.label == str(int(t.position))


def test_ruler_ticks_deterministic():
    a = ruler_ticks(1000.0, zoom=1.5, offset=13.0, axis_pixels=400)
    b = ruler_ticks(1000.0, zoom=1.5, offset=13.0, axis_pixels=400)
    assert a == b


@pytest.mark.parametrize(
    "zoom,axis_pixels",
    [(0.0, 100), (-1.0, 100), (1.0, 0), (1.0, -5)],
)
def test_ruler_ticks_reject_invalid(zoom, axis_pixels):
    with pytest.raises(GuideError):
        ruler_ticks(1000.0, zoom=zoom, offset=0.0, axis_pixels=axis_pixels)


def test_ruler_ticks_reject_non_int_axis_pixels():
    with pytest.raises(GuideError):
        ruler_ticks(1000.0, zoom=1.0, offset=0.0, axis_pixels=True)  # type: ignore[arg-type]
    with pytest.raises(GuideError):
        ruler_ticks(1000.0, zoom=1.0, offset=0.0, axis_pixels=1.5)  # type: ignore[arg-type]


def test_ruler_ticks_fractional_step_trims_label():
    # A very zoomed-in ruler can pick a sub-unit step -> trimmed float labels.
    ticks = ruler_ticks(10.0, zoom=500.0, offset=0.0, axis_pixels=500)
    assert ticks
    # At least one label should be a trimmed non-integer (no trailing zeros).
    assert any("." in t.label for t in ticks) or all(
        t.label == str(int(t.position)) for t in ticks
    )


def test_coordinate_readout_floors_screen_to_doc():
    # doc = offset + screen / zoom, floored.
    assert coordinate_readout(20.0, 40.0, zoom=2.0, offset=(0.0, 0.0)) == (10, 20)


def test_coordinate_readout_applies_offset():
    assert coordinate_readout(10.0, 10.0, zoom=1.0, offset=(5.0, 7.0)) == (15, 17)


def test_coordinate_readout_floor_negative():
    assert coordinate_readout(-1.0, -1.0, zoom=1.0, offset=(0.0, 0.0)) == (-1, -1)


@pytest.mark.parametrize("zoom", [0.0, -1.0])
def test_coordinate_readout_rejects_bad_zoom(zoom):
    with pytest.raises(GuideError):
        coordinate_readout(1.0, 1.0, zoom=zoom, offset=(0.0, 0.0))


def test_coordinate_readout_rejects_bad_offset():
    with pytest.raises(GuideError):
        coordinate_readout(1.0, 1.0, zoom=1.0, offset=(0.0,))  # type: ignore[arg-type]
