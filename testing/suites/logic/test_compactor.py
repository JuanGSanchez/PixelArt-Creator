"""Tests for pixelart_creator.logic.compactor (MaxRects sprite packing)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic import compactor
from pixelart_creator.logic.compactor import (
    CompactionError,
    Packing,
    Placement,
    Rect,
    compact,
)


def _overlap(a: Placement, b: Placement) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def test_compact_returns_packing_with_all_rects():
    rects = [("a", 64, 64), ("b", 32, 128), ("c", 100, 20), ("d", 40, 40)]
    packing = compact(rects, 256, 256)
    assert isinstance(packing, Packing)
    assert {p.id for p in packing.placements} == {"a", "b", "c", "d"}


def test_compact_no_overlaps_and_within_bounds():
    rects = [(f"r{i}", 10 + i, 20 - (i % 5)) for i in range(15)]
    packing = compact(rects, 128, 128)
    for p in packing.placements:
        assert 0 <= p.x and 0 <= p.y
        assert p.x + p.w <= 128 and p.y + p.h <= 128
    for i, a in enumerate(packing.placements):
        for b in packing.placements[i + 1 :]:
            assert not _overlap(a, b)


def test_compact_accepts_rect_namedtuples():
    packing = compact([Rect("x", 16, 16), Rect("y", 16, 16)], 64, 64)
    assert len(packing.placements) == 2


def test_compact_is_deterministic():
    rects = [("a", 30, 30), ("b", 30, 30), ("c", 15, 45)]
    assert compact(rects, 100, 100) == compact(rects, 100, 100)


def test_empty_input_gives_empty_packing():
    packing = compact([], 64, 64)
    assert packing.placements == []
    assert packing.width == 0 and packing.height == 0


def test_rect_too_big_raises_does_not_fit():
    with pytest.raises(CompactionError) as exc:
        compact([("big", 100, 10)], 50, 50)
    assert exc.value.reason == "does-not-fit"


def test_bad_atlas_bounds():
    with pytest.raises(CompactionError) as exc:
        compact([("a", 1, 1)], 0, 10)
    assert exc.value.reason == "invalid-input"


@pytest.mark.parametrize(
    "bad",
    [
        [("a", 1)],  # wrong arity
        [("a", -1, 5)],  # negative
        [("a", 1.5, 5)],  # non-int
    ],
)
def test_malformed_rects_raise(bad):
    with pytest.raises(CompactionError):
        compact(bad, 64, 64)


def test_does_not_fit_when_area_exhausted():
    # Four 40x40 rects cannot fit a 64x64 atlas.
    with pytest.raises(CompactionError) as exc:
        compact([(f"r{i}", 40, 40) for i in range(4)], 64, 64)
    assert exc.value.reason == "does-not-fit"


def test_smoke_entrypoint_returns_zero():
    assert compactor._smoke() == 0


def test_compaction_error_is_valueerror_subclass():
    # Regression (T6, CL-8): CompactionError must share the ValueError domain base
    # used by ColorError/PaletteError/PixelBufferError/DocumentError/ProjectIOError.
    assert issubclass(CompactionError, ValueError)


def test_compaction_error_caught_as_valueerror():
    # Callers relying on the common ValueError base must catch CompactionError.
    with pytest.raises(ValueError) as exc:
        compact([("a", 1, 1)], 0, 10)
    assert isinstance(exc.value, CompactionError)
    assert exc.value.reason == "invalid-input"


@given(
    st.lists(
        st.tuples(st.integers(1, 20), st.integers(1, 20)),
        min_size=1,
        max_size=8,
    )
)
def test_property_all_placed_without_overlap(sizes):
    rects = [(f"r{i}", w, h) for i, (w, h) in enumerate(sizes)]
    packing = compact(rects, 256, 256)
    assert len(packing.placements) == len(rects)
    for i, a in enumerate(packing.placements):
        for b in packing.placements[i + 1 :]:
            assert not _overlap(a, b)
