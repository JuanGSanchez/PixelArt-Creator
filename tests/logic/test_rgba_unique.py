"""Tests for pixelart_creator.logic._rgba_unique (fast RGBA-unique reduction).

AGT-03 replaced ``np.unique(pixels, axis=0, ...)`` with a packed-uint32 1-D unique
(``unique_rgba_counts`` / ``unique_rgba_inverse``) to kill the 8K palette hotspot,
claiming *byte-for-byte identical* output with the ascending-(R,G,B,A) order
contract (SC-L012-4) preserved by re-sorting the small unique set via ``np.lexsort``.

This module is the equality/determinism oracle for that migration:

* the helper's ``(unique_rows, counts)`` / ``(unique_rows, inverse)`` EQUAL a
  reference ``np.unique(pixels, axis=0, return_counts=/return_inverse=)`` across
  all-same / empty / single / mixed / dense-random / non-contiguous / order-edge
  inputs (channel-differing rows that would misorder under a little-endian uint32
  view), and the returned rows are ascending by (R, G, B, A);
* a Hypothesis property compares helper vs reference over random small RGBA arrays;
* the migrated callers (palette_analytics / quantize / palette_ops) stay correct
  and deterministic;
* a large near-uniform buffer yields the correct small unique set (correctness
  smoke only — NO wall-clock assertion; perf is validated by the orchestrator).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from pixelart_creator.logic._rgba_unique import (
    unique_rgba_counts,
    unique_rgba_inverse,
)
from pixelart_creator.logic.hardware_palette import game_boy_palette, nes_palette
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_analytics import color_usage_counts
from pixelart_creator.logic.palette_ops import to_indexed, to_rgba
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import constrain_to_palette, kmeans

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
RED = (255, 0, 0, 255)


# -- reference oracle (the previous np.unique(axis=0) implementation) ----------


def _ref_counts(pixels):
    """Reference ``(unique_rows, counts)`` via ``np.unique(axis=0)``."""
    unique, counts = np.unique(pixels, axis=0, return_counts=True)
    return unique, counts


def _ref_inverse(pixels):
    """Reference ``(unique_rows, inverse)`` via ``np.unique(axis=0)``."""
    unique, inverse = np.unique(pixels, axis=0, return_inverse=True)
    return unique, np.asarray(inverse).reshape(-1)


def _assert_ascending_rgba(rows):
    """Assert ``rows`` are strictly ascending as (R, G, B, A) tuples (SC-L012-4)."""
    tuples = [tuple(int(v) for v in r) for r in rows]
    assert tuples == sorted(set(tuples))


# -- named case fixtures ------------------------------------------------------


def _all_same():
    return np.tile(np.array([RED], dtype=np.uint8), (32, 1))


def _empty():
    return np.empty((0, 4), dtype=np.uint8)


def _single():
    return np.array([[12, 34, 56, 78]], dtype=np.uint8)


def _mixed():
    return np.array(
        [BLACK, WHITE, RED, RED, BLACK, WHITE, WHITE, RED],
        dtype=np.uint8,
    )


def _dense_random():
    rng = np.random.default_rng(20260703)
    return rng.integers(0, 256, size=(4096, 4), dtype=np.uint8)


def _non_contiguous():
    # Build an (N, 8) block and slice the first 4 columns -> non-C-contiguous view.
    rng = np.random.default_rng(7)
    wide = rng.integers(0, 6, size=(300, 8), dtype=np.uint8)
    view = wide[:, :4]
    assert not view.flags["C_CONTIGUOUS"]
    return view


def _order_edge_r():
    # Rows share (G, B, A) but differ in R; a little-endian uint32 view sorts by
    # A (top byte) first, so the naive packed order would misplace these. The
    # required order is R-primary ascending.
    return np.array(
        [[5, 0, 0, 255], [3, 0, 0, 255], [9, 0, 0, 0], [3, 0, 0, 255]],
        dtype=np.uint8,
    )


def _order_edge_channels():
    # One row per single-channel difference, to catch any byte-order regression.
    return np.array(
        [
            [10, 20, 30, 40],
            [11, 20, 30, 40],  # R differs
            [10, 21, 30, 40],  # G differs
            [10, 20, 31, 40],  # B differs
            [10, 20, 30, 41],  # A differs
        ],
        dtype=np.uint8,
    )


_CASES = {
    "all_same": _all_same,
    "empty": _empty,
    "single": _single,
    "mixed": _mixed,
    "dense_random": _dense_random,
    "non_contiguous": _non_contiguous,
    "order_edge_r": _order_edge_r,
    "order_edge_channels": _order_edge_channels,
}


# -- unique_rgba_counts equals the reference ----------------------------------


@pytest.mark.parametrize("name", sorted(_CASES))
def test_counts_equal_reference(name):
    pixels = _CASES[name]()
    ref_unique, ref_counts = _ref_counts(pixels)
    unique, counts = unique_rgba_counts(pixels)

    assert unique.dtype == np.uint8
    np.testing.assert_array_equal(unique, ref_unique)
    np.testing.assert_array_equal(counts, ref_counts)
    # The counts must still sum to the pixel total (SC-L012-1).
    assert int(counts.sum()) == pixels.shape[0]
    _assert_ascending_rgba(unique)


@pytest.mark.parametrize("name", sorted(_CASES))
def test_inverse_equals_reference(name):
    pixels = _CASES[name]()
    ref_unique, ref_inverse = _ref_inverse(pixels)
    unique, inverse = unique_rgba_inverse(pixels)

    assert unique.dtype == np.uint8
    np.testing.assert_array_equal(unique, ref_unique)
    np.testing.assert_array_equal(inverse, ref_inverse)
    _assert_ascending_rgba(unique)
    # unique[inverse] reconstructs the original row sequence exactly.
    if pixels.shape[0]:
        np.testing.assert_array_equal(unique[inverse], np.ascontiguousarray(pixels))


def test_order_edge_is_r_primary_not_uint32_order():
    # Explicit witness that the re-sort fixes the little-endian uint32 misorder.
    unique, _ = unique_rgba_counts(_order_edge_r())
    got = [tuple(int(v) for v in r) for r in unique]
    assert got == [(3, 0, 0, 255), (5, 0, 0, 255), (9, 0, 0, 0)]


# -- determinism --------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_CASES))
def test_counts_deterministic(name):
    pixels = _CASES[name]()
    u1, c1 = unique_rgba_counts(pixels)
    u2, c2 = unique_rgba_counts(pixels)
    np.testing.assert_array_equal(u1, u2)
    np.testing.assert_array_equal(c1, c2)


@pytest.mark.parametrize("name", sorted(_CASES))
def test_inverse_deterministic(name):
    pixels = _CASES[name]()
    u1, i1 = unique_rgba_inverse(pixels)
    u2, i2 = unique_rgba_inverse(pixels)
    np.testing.assert_array_equal(u1, u2)
    np.testing.assert_array_equal(i1, i2)


# -- input validation ---------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((4, 3), dtype=np.uint8),  # wrong channel count
        np.zeros((4, 4, 4), dtype=np.uint8),  # wrong ndim
        np.zeros((4, 4), dtype=np.int64),  # wrong dtype
    ],
)
def test_counts_rejects_bad_shape_or_dtype(bad):
    with pytest.raises(ValueError):
        unique_rgba_counts(bad)


@pytest.mark.parametrize(
    "bad",
    [
        np.zeros((4, 3), dtype=np.uint8),
        np.zeros((4, 4, 4), dtype=np.uint8),
        np.zeros((4, 4), dtype=np.int64),
    ],
)
def test_inverse_rejects_bad_shape_or_dtype(bad):
    with pytest.raises(ValueError):
        unique_rgba_inverse(bad)


# -- Hypothesis: helper == reference over random small RGBA arrays ------------

_rgba_rows = hnp.arrays(
    dtype=np.uint8,
    shape=st.integers(min_value=0, max_value=64).map(lambda n: (n, 4)),
    # Narrow value domain forces collisions so counts/inverse are exercised.
    elements=st.integers(min_value=0, max_value=6),
)

_rgba_rows_full = hnp.arrays(
    dtype=np.uint8,
    shape=st.integers(min_value=1, max_value=48).map(lambda n: (n, 4)),
    elements=st.integers(min_value=0, max_value=255),
)


@given(pixels=_rgba_rows)
def test_property_counts_match_reference(pixels):
    ref_unique, ref_counts = _ref_counts(pixels)
    unique, counts = unique_rgba_counts(pixels)
    np.testing.assert_array_equal(unique, ref_unique)
    np.testing.assert_array_equal(counts, ref_counts)
    _assert_ascending_rgba(unique)


@given(pixels=_rgba_rows)
def test_property_inverse_match_reference(pixels):
    ref_unique, ref_inverse = _ref_inverse(pixels)
    unique, inverse = unique_rgba_inverse(pixels)
    np.testing.assert_array_equal(unique, ref_unique)
    np.testing.assert_array_equal(inverse, ref_inverse)
    if pixels.shape[0]:
        np.testing.assert_array_equal(unique[inverse], pixels)


@given(pixels=_rgba_rows_full)
def test_property_inverse_reconstructs_full_domain(pixels):
    unique, inverse = unique_rgba_inverse(pixels)
    np.testing.assert_array_equal(unique[inverse], pixels)
    _assert_ascending_rgba(unique)


# -- migrated-caller re-verification (correctness + determinism) --------------


def _random_rgba_buffer(w=24, h=24, seed=3, hi=256):
    rng = np.random.default_rng(seed)
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.data[:, :, :3] = rng.integers(0, hi, size=(h, w, 3), dtype=np.uint8)
    buf.data[:, :, 3] = 255
    return buf


def test_palette_analytics_counts_match_direct_reference():
    # color_usage_counts is built on unique_rgba_counts; its counts must match a
    # direct np.unique(axis=0) tally and be deterministic (SC-L012-1/-4).
    buf = _random_rgba_buffer(hi=8)
    ref_unique, ref_counts = _ref_counts(buf.data.reshape(-1, 4))
    ref = {tuple(int(v) for v in c): int(n) for c, n in zip(ref_unique, ref_counts)}
    counts = color_usage_counts(buf)
    assert dict(counts) == ref
    assert sum(n for _, n in counts) == buf.width * buf.height
    assert counts == color_usage_counts(buf)  # deterministic


def test_constrain_to_palette_maps_each_pixel_to_true_nearest():
    # constrain uses unique_rgba_inverse to broadcast the per-unique nearest index
    # back to every pixel; verify against an independent per-pixel nearest oracle.
    buf = _random_rgba_buffer(w=16, h=16, seed=9)
    pal = game_boy_palette()
    out = constrain_to_palette(buf, pal)
    assert out.mode is ColorMode.RGBA

    colours = np.asarray(pal.colors(), dtype=np.int64)
    src = buf.data.reshape(-1, 4).astype(np.int64)
    diff = src[:, None, :] - colours[None, :, :]
    dist = np.einsum("ijk,ijk->ij", diff, diff)
    nearest = np.argmin(dist, axis=1)  # ties -> lower index (argmin first min)
    expected = colours[nearest].astype(np.uint8).reshape(buf.height, buf.width, 4)
    np.testing.assert_array_equal(out.data, expected)
    # Deterministic re-run.
    assert constrain_to_palette(buf, pal) == out


def test_to_indexed_to_rgba_roundtrip_equals_constrain():
    # to_indexed uses unique_rgba_inverse; to_rgba(to_indexed(x)) reproduces the
    # palette-quantised image == constrain_to_palette output (module contract).
    buf = _random_rgba_buffer(w=16, h=16, seed=11)
    pal = nes_palette()
    indexed = to_indexed(buf, pal)
    assert indexed.mode is ColorMode.INDEXED
    restored = to_rgba(indexed, pal)
    assert restored == constrain_to_palette(buf, pal)
    # Colour set of the result is a subset of the palette.
    result_colours = {tuple(int(v) for v in p) for p in restored.data.reshape(-1, 4)}
    assert result_colours <= {tuple(c) for c in pal.colors()}
    # Deterministic.
    assert to_indexed(buf, pal) == indexed


def test_kmeans_counts_path_deterministic_over_many_colours():
    # kmeans branches through unique_rgba_counts when #colours > n; check that the
    # counts-weighted extraction is reproducible (SC-L011-2) after the migration.
    buf = _random_rgba_buffer(w=32, h=32, seed=5, hi=64)
    first = kmeans(buf, 8)
    second = kmeans(buf, 8)
    assert first.colors() == second.colors()
    assert len(first) <= 8


# -- large near-uniform buffer smoke (correctness only, NO timing) ------------


def test_large_blank_buffer_single_unique():
    # A blank large buffer must reduce to exactly one colour with the full count.
    buf = PixelBuffer(1000, 1000, ColorMode.RGBA)  # 1,000,000 transparent-black px
    unique, counts = unique_rgba_counts(buf.data.reshape(-1, 4))
    assert unique.shape == (1, 4)
    assert tuple(int(v) for v in unique[0]) == (0, 0, 0, 0)
    assert int(counts[0]) == 1_000_000


def test_large_near_uniform_buffer_small_unique_set():
    # A near-uniform large buffer (a handful of stray pixels) yields a small,
    # correct unique set — the property that made the packed reduction fast.
    buf = PixelBuffer(1000, 1000, ColorMode.RGBA)
    buf.fill(WHITE)
    buf.set_pixel(0, 0, RED)
    buf.set_pixel(1, 0, BLACK)
    pixels = buf.data.reshape(-1, 4)
    ref_unique, ref_counts = _ref_counts(pixels)
    unique, counts = unique_rgba_counts(pixels)
    np.testing.assert_array_equal(unique, ref_unique)
    np.testing.assert_array_equal(counts, ref_counts)
    assert unique.shape[0] == 3
    assert int(counts.sum()) == 1_000_000
