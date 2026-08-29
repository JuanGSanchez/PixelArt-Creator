"""Tests for pixelart_creator.logic.blend (Phase-4 Slice 4A, T4).

Covers the 13-member :class:`BlendMode` vocabulary, the per-channel W3C blend
functions, alpha-aware :func:`blend_arrays` (opacity / mask / immutability), the
single-pixel :func:`blend_pixels` (NORMAL delegation), and the stack compositor
:func:`composite_stack` (visibility / opacity / order / groups / region /
guards). Blend known-values are cross-checked against an *independent*
re-derivation of the W3C Compositing-and-Blending-Level-1 formulas
(``docs/research-blend-modes.md``), not against the implementation itself.

Maps to REQ-P4-LOGIC-001..007, 011, 012 and LOGIC-003/004/005.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pixelart_creator.logic.blend import (
    BlendError,
    BlendMode,
    blend_arrays,
    blend_channel,
    blend_pixels,
    composite_stack,
)
from pixelart_creator.logic.color import blend_over
from pixelart_creator.logic.document import Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import (
    ColorMode,
    PixelBuffer,
    PixelBufferError,
)

# --------------------------------------------------------------------------- #
# Independent W3C re-derivation (the test oracle — NOT the product code).      #
# --------------------------------------------------------------------------- #


def _oracle_b(mode: BlendMode, cb: float, cs: float) -> float:
    """Independent B(Cb, Cs) on 0..1 per W3C Compositing-and-Blending L1."""
    if mode is BlendMode.NORMAL:
        return cs
    if mode is BlendMode.MULTIPLY:
        return cb * cs
    if mode is BlendMode.SCREEN:
        return cb + cs - cb * cs
    if mode is BlendMode.DARKEN:
        return min(cb, cs)
    if mode is BlendMode.LIGHTEN:
        return max(cb, cs)
    if mode is BlendMode.DIFFERENCE:
        return abs(cb - cs)
    if mode is BlendMode.EXCLUSION:
        return cb + cs - 2.0 * cb * cs
    if mode is BlendMode.HARD_LIGHT:
        return (
            cb * 2.0 * cs
            if cs <= 0.5
            else cb + (2.0 * cs - 1.0) - cb * (2.0 * cs - 1.0)
        )
    if mode is BlendMode.OVERLAY:
        return _oracle_b(BlendMode.HARD_LIGHT, cs, cb)
    if mode is BlendMode.COLOR_DODGE:
        if cb == 0.0:
            return 0.0
        if cs >= 1.0:
            return 1.0
        return min(1.0, cb / (1.0 - cs))
    if mode is BlendMode.COLOR_BURN:
        if cb >= 1.0:
            return 1.0
        if cs <= 0.0:
            return 0.0
        return 1.0 - min(1.0, (1.0 - cb) / cs)
    if mode is BlendMode.SOFT_LIGHT:
        d = ((16.0 * cb - 12.0) * cb + 4.0) * cb if cb <= 0.25 else math.sqrt(cb)
        if cs <= 0.5:
            return cb - (1.0 - 2.0 * cs) * cb * (1.0 - cb)
        return cb + (2.0 * cs - 1.0) * (d - cb)
    raise AssertionError(mode)


ALL_MODES = list(BlendMode)


def test_enum_matches_grounded_w3c_separable_set():
    # REQ-P4-LOGIC-001: 12 separable W3C modes (NORMAL + 11 non-normal), grounded
    # in docs/research-blend-modes.md §3 (R-23: the stale "13-member enum" FLAG
    # comment is resolved — the implementation's 12 members are correct).
    assert len(BlendMode) == 12
    assert BlendMode.NORMAL.value == "normal"
    # Value strings are the stable .pixproj tokens.
    assert {m.value for m in BlendMode} == {
        "normal",
        "multiply",
        "screen",
        "overlay",
        "darken",
        "lighten",
        "color_dodge",
        "color_burn",
        "hard_light",
        "soft_light",
        "difference",
        "exclusion",
    }


# --------------------------------------------------------------------------- #
# blend_channel — documented known values + full-mode oracle agreement.        #
# --------------------------------------------------------------------------- #

# The verified known values quoted in the research report / AGT-03 report.
KNOWN_VALUES = [
    (BlendMode.MULTIPLY, 128, 128, 64),
    (BlendMode.SCREEN, 0, 200, 200),
    (BlendMode.DARKEN, 100, 200, 100),
    (BlendMode.LIGHTEN, 100, 200, 200),
    (BlendMode.DIFFERENCE, 200, 50, 150),
]


@pytest.mark.parametrize("mode, cb, cs, expected", KNOWN_VALUES)
def test_blend_channel_documented_known_values(mode, cb, cs, expected):
    # REQ-P4-LOGIC-002..006: research §1/§3 verified constants.
    result = round(blend_channel(mode, cb / 255.0, cs / 255.0) * 255.0)
    assert result == expected


@pytest.mark.parametrize("mode", ALL_MODES)
@pytest.mark.parametrize(
    "cb, cs",
    [
        (0, 0),
        (0, 255),
        (255, 0),
        (255, 255),
        (128, 128),
        (50, 200),
        (200, 50),
        (64, 128),
        (200, 128),
        (10, 240),
    ],
)
def test_blend_channel_matches_w3c_oracle(mode, cb, cs):
    # Every mode, every representative pair, vs the independent W3C formula.
    # T13 D5/B4: the compositor now works in float32 (~1e-7 relative precision),
    # so the float comparison uses a float32-appropriate 1e-6 tolerance (the
    # float64-era 1e-9 no longer holds); uint8 outputs stay identical (below).
    got = blend_channel(mode, cb / 255.0, cs / 255.0)
    exp = _oracle_b(mode, cb / 255.0, cs / 255.0)
    assert got == pytest.approx(exp, abs=1e-6)


def test_soft_light_cubic_branch_cb_le_quarter():
    # REQ-P4-LOGIC: SOFT_LIGHT D(Cb) cubic branch (Cb <= 0.25) with Cs > 0.5.
    cb, cs = 50 / 255.0, 200 / 255.0  # cb ~= 0.196 -> cubic branch
    assert cb <= 0.25
    # 1e-6 tolerance: float32 working space (T13 D5); uint8 result asserted below.
    assert blend_channel(BlendMode.SOFT_LIGHT, cb, cs) == pytest.approx(
        _oracle_b(BlendMode.SOFT_LIGHT, cb, cs), abs=1e-6
    )
    assert round(blend_channel(BlendMode.SOFT_LIGHT, cb, cs) * 255) == 86


def test_soft_light_sqrt_branch_cb_gt_quarter():
    # SOFT_LIGHT D(Cb) sqrt branch (Cb > 0.25) with Cs > 0.5.
    cb, cs = 200 / 255.0, 200 / 255.0  # cb ~= 0.784 -> sqrt branch
    assert cb > 0.25
    assert round(blend_channel(BlendMode.SOFT_LIGHT, cb, cs) * 255) == 215


def test_soft_light_low_source_branch():
    # SOFT_LIGHT Cs <= 0.5 branch (darkening half).
    cb, cs = 100 / 255.0, 50 / 255.0
    assert round(blend_channel(BlendMode.SOFT_LIGHT, cb, cs) * 255) == 63


@pytest.mark.parametrize("mode", ALL_MODES)
def test_blend_channel_rejects_non_blendmode(mode):
    with pytest.raises(BlendError):
        blend_channel("multiply", 0.5, 0.5)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# color-dodge / color-burn divide-by-zero guard edges.                         #
# --------------------------------------------------------------------------- #


def test_color_dodge_guard_edges():
    # Cb==0 -> 0 ; Cs>=1 -> 1 ; the 1/(1-Cs) divide is guarded.
    assert blend_channel(BlendMode.COLOR_DODGE, 0.0, 0.8) == 0.0
    assert blend_channel(BlendMode.COLOR_DODGE, 0.5, 1.0) == 1.0  # Cs==1 divide guard
    # Cb>0, Cs<1 normal path clamps to 1.
    assert blend_channel(BlendMode.COLOR_DODGE, 0.5, 0.9) == pytest.approx(1.0)


def test_color_burn_guard_edges():
    # Cb>=1 -> 1 ; Cs<=0 -> 0 ; the (1-Cb)/Cs divide is guarded.
    assert blend_channel(BlendMode.COLOR_BURN, 1.0, 0.5) == 1.0
    assert blend_channel(BlendMode.COLOR_BURN, 0.5, 0.0) == 0.0  # Cs==0 divide guard
    assert blend_channel(BlendMode.COLOR_BURN, 0.0, 0.5) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# blend_pixels — NORMAL delegation, known values, guards.                      #
# --------------------------------------------------------------------------- #


def test_blend_pixels_normal_delegates_to_blend_over_exactly():
    # LOGIC-003: NORMAL must equal color.blend_over for the same inputs.
    src = (10, 200, 30, 128)
    dst = (240, 20, 60, 200)
    assert blend_pixels(BlendMode.NORMAL, src, dst) == blend_over(src, dst)


@given(
    src=st.tuples(*[st.integers(0, 255)] * 4),
    dst=st.tuples(*[st.integers(0, 255)] * 4),
)
def test_blend_pixels_normal_equals_blend_over_property(src, dst):
    assert blend_pixels(BlendMode.NORMAL, src, dst) == blend_over(src, dst)


@pytest.mark.parametrize("mode, cb, cs, expected", KNOWN_VALUES)
def test_blend_pixels_opaque_known_values(mode, cb, cs, expected):
    # Both opaque -> Co = B(Cb, Cs). src carries Cs, dst carries Cb.
    src = (cs, cs, cs, 255)
    dst = (cb, cb, cb, 255)
    r, g, b, a = blend_pixels(mode, src, dst)
    assert (r, g, b) == (expected, expected, expected)
    assert a == 255


def test_blend_pixels_rejects_non_blendmode():
    with pytest.raises(BlendError):
        blend_pixels("screen", (0, 0, 0, 0), (0, 0, 0, 0))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# blend_arrays — vectorised == per-pixel, opacity, mask forms, immutability.   #
# --------------------------------------------------------------------------- #


def _grid(seed: int, h: int = 3, w: int = 4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w, 4), dtype=np.uint8)


# T13 B4: for every W3C mode, blend_pixels routes through blend_arrays, so the
# vectorised and per-pixel paths are the SAME float32 computation -> bit-exact.
# NORMAL is now ALSO bit-exact: AGT-03 gave blend_arrays(NORMAL) a dedicated
# float64 source-over path that matches color.blend_over / blend_pixels(NORMAL)
# with ZERO tolerance (verified bit-exact over ~4.2M exhaustive pixels). The
# earlier ±1 LSB float32 drift on the NORMAL cross-path is gone, so every mode
# -- NORMAL included -- is asserted with EXACT equality (no tolerance).
def _assert_pixel_equal(mode, got, expected):
    assert tuple(int(v) for v in got) == tuple(int(v) for v in expected)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_blend_arrays_matches_elementwise_blend_pixels(mode):
    # LOGIC-005/007: vectorised path == per-pixel blend_pixels on a small grid.
    src = _grid(1)
    dst = _grid(2)
    out = blend_arrays(mode, src, dst)
    h, w = src.shape[:2]
    for y in range(h):
        for x in range(w):
            sp = tuple(int(v) for v in src[y, x])
            dp = tuple(int(v) for v in dst[y, x])
            _assert_pixel_equal(mode, out[y, x], blend_pixels(mode, sp, dp))


@given(mode=st.sampled_from(ALL_MODES), seed=st.integers(0, 10_000))
def test_blend_arrays_equals_per_pixel_property(mode, seed):
    # Property (LOGIC-005): blend_arrays == elementwise blend_pixels, all modes.
    src = _grid(seed)
    dst = _grid(seed + 7)
    out = blend_arrays(mode, src, dst)
    h, w = src.shape[:2]
    for y in range(h):
        for x in range(w):
            sp = tuple(int(v) for v in src[y, x])
            dp = tuple(int(v) for v in dst[y, x])
            _assert_pixel_equal(mode, out[y, x], blend_pixels(mode, sp, dp))


def test_blend_arrays_normal_base_case_equals_blend_over_exactly():
    # LOGIC-003 (tightened): the NORMAL base case (opacity=1.0, mask=None) is
    # bit-exact -- blend_arrays(NORMAL, src, dst) equals color.blend_over applied
    # elementwise AND equals blend_pixels(NORMAL), with ZERO tolerance. This was
    # a ±1 LSB comparison while the compositor was float32; AGT-03's dedicated
    # float64 source-over path restores exact equality (verified over ~4.2M px).
    src = _grid(1)
    dst = _grid(2)
    out = blend_arrays(BlendMode.NORMAL, src, dst)  # opacity=1.0, mask=None
    h, w = src.shape[:2]
    for y in range(h):
        for x in range(w):
            sp = tuple(int(v) for v in src[y, x])
            dp = tuple(int(v) for v in dst[y, x])
            got = tuple(int(v) for v in out[y, x])
            assert got == blend_over(sp, dp)  # exact vs the blend_over oracle
            assert got == blend_pixels(BlendMode.NORMAL, sp, dp)  # exact vs pixel


@given(seed=st.integers(0, 10_000))
def test_blend_arrays_normal_base_case_equals_blend_over_property(seed):
    # Property (LOGIC-003 tightened): over random grids the NORMAL base case
    # equals color.blend_over elementwise with EXACT equality (no tolerance).
    src = _grid(seed)
    dst = _grid(seed + 3)
    out = blend_arrays(BlendMode.NORMAL, src, dst)
    h, w = src.shape[:2]
    for y in range(h):
        for x in range(w):
            sp = tuple(int(v) for v in src[y, x])
            dp = tuple(int(v) for v in dst[y, x])
            assert tuple(int(v) for v in out[y, x]) == blend_over(sp, dp)


def test_blend_arrays_normal_both_alpha_zero_preserves_dst_rgb():
    # LOGIC-003 sub-case (sa == 0 & da == 0): blend_over returns dst unchanged,
    # so blend_arrays(NORMAL) must preserve the dst RGB (and the zero alpha)
    # bit-exactly -- matching blend_over and blend_pixels(NORMAL) with zero
    # tolerance. Guards the float32-era ±1 LSB drift out of the clear branch.
    src = np.zeros((2, 2, 4), dtype=np.uint8)
    src[:] = (10, 20, 30, 0)  # sa == 0
    dst = np.zeros((2, 2, 4), dtype=np.uint8)
    dst[:] = (40, 50, 60, 0)  # da == 0
    out = blend_arrays(BlendMode.NORMAL, src, dst)
    expected = blend_over((10, 20, 30, 0), (40, 50, 60, 0))
    assert expected == (40, 50, 60, 0)  # oracle: dst RGB preserved, alpha 0
    for y in range(2):
        for x in range(2):
            got = tuple(int(v) for v in out[y, x])
            assert got == expected
            assert got == blend_pixels(
                BlendMode.NORMAL, (10, 20, 30, 0), (40, 50, 60, 0)
            )


def test_blend_arrays_opacity_scales_effective_source_alpha():
    # LOGIC-005: opacity 0 => src invisible (result == dst); 1 => full effect.
    src = np.zeros((2, 2, 4), dtype=np.uint8)
    src[:] = (255, 0, 0, 255)
    dst = np.zeros((2, 2, 4), dtype=np.uint8)
    dst[:] = (0, 0, 255, 255)
    zero = blend_arrays(BlendMode.NORMAL, src, dst, opacity=0.0)
    assert np.array_equal(zero, dst)
    full = blend_arrays(BlendMode.NORMAL, src, dst, opacity=1.0)
    assert np.array_equal(full, src)
    half = blend_arrays(BlendMode.NORMAL, src, dst, opacity=0.5)
    # Half opacity => partially toward src; red channel between dst(0) and src(255).
    assert 0 < int(half[0, 0, 0]) < 255


def test_blend_arrays_opacity_out_of_range_raises():
    src = np.zeros((1, 1, 4), dtype=np.uint8)
    dst = np.zeros((1, 1, 4), dtype=np.uint8)
    with pytest.raises(BlendError):
        blend_arrays(BlendMode.NORMAL, src, dst, opacity=1.5)


@pytest.mark.parametrize("mask_shape", ["hw", "hw1", "rgba"])
def test_blend_arrays_mask_forms_modulate(mask_shape):
    # LOGIC-012: (H,W), (H,W,1) and RGBA-alpha masks all modulate the source.
    src = np.zeros((2, 2, 4), dtype=np.uint8)
    src[:] = (255, 0, 0, 255)
    dst = np.zeros((2, 2, 4), dtype=np.uint8)
    dst[:] = (0, 0, 255, 255)
    if mask_shape == "hw":
        mask = np.zeros((2, 2), dtype=np.uint8)  # 0 => src fully masked out
    elif mask_shape == "hw1":
        mask = np.zeros((2, 2, 1), dtype=np.uint8)
    else:
        mask = np.zeros((2, 2, 4), dtype=np.uint8)  # RGBA, alpha channel used
    masked = blend_arrays(BlendMode.NORMAL, src, dst, mask=mask)
    assert np.array_equal(masked, dst)  # masked-out src contributes nothing

    full_mask = np.full((2, 2), 255, dtype=np.uint8)
    passed = blend_arrays(BlendMode.NORMAL, src, dst, mask=full_mask)
    assert np.array_equal(passed, src)


def test_blend_arrays_mask_wrong_geometry_raises():
    src = np.zeros((2, 2, 4), dtype=np.uint8)
    dst = np.zeros((2, 2, 4), dtype=np.uint8)
    with pytest.raises(BlendError):
        blend_arrays(BlendMode.NORMAL, src, dst, mask=np.zeros((3, 3), dtype=np.uint8))


def test_blend_arrays_shape_mismatch_raises():
    with pytest.raises(BlendError):
        blend_arrays(
            BlendMode.NORMAL,
            np.zeros((2, 2, 4), dtype=np.uint8),
            np.zeros((3, 2, 4), dtype=np.uint8),
        )


def test_blend_arrays_non_rgba_shape_raises():
    with pytest.raises(BlendError):
        blend_arrays(
            BlendMode.NORMAL,
            np.zeros((2, 2, 3), dtype=np.uint8),
            np.zeros((2, 2, 3), dtype=np.uint8),
        )


def test_blend_arrays_rejects_non_blendmode():
    with pytest.raises(BlendError):
        blend_arrays(
            "normal",  # type: ignore[arg-type]
            np.zeros((1, 1, 4), dtype=np.uint8),
            np.zeros((1, 1, 4), dtype=np.uint8),
        )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_blend_arrays_never_mutates_inputs(mode):
    # LOGIC-004: source and destination arrays are left untouched.
    src = _grid(11)
    dst = _grid(12)
    mask = np.full(src.shape[:2], 200, dtype=np.uint8)
    src_before = src.copy()
    dst_before = dst.copy()
    mask_before = mask.copy()
    blend_arrays(mode, src, dst, opacity=0.5, mask=mask)
    assert np.array_equal(src, src_before)
    assert np.array_equal(dst, dst_before)
    assert np.array_equal(mask, mask_before)


# --------------------------------------------------------------------------- #
# composite_stack — visibility / opacity / order / groups / region / guards.   #
# --------------------------------------------------------------------------- #

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)


def _layer(w: int, h: int, fill, **kw) -> Layer:
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.fill(fill)
    return Layer(buf, kw.pop("name", "L"), **kw)


def test_composite_bottom_to_top_order():
    # CL-4: nodes[0] is the bottom; an opaque top layer wins.
    bottom = _layer(2, 2, RED)
    top = _layer(2, 2, BLUE)
    out = composite_stack([bottom, top], 2, 2)
    assert out.get_pixel(0, 0) == BLUE


def test_composite_hidden_layer_is_a_noop():
    # LOGIC-006: a hidden layer contributes nothing (== removed).
    bottom = _layer(2, 2, RED)
    top = _layer(2, 2, BLUE, visible=False)
    with_hidden = composite_stack([bottom, top], 2, 2)
    without = composite_stack([bottom], 2, 2)
    assert with_hidden.get_pixel(0, 0) == without.get_pixel(0, 0) == RED


def test_composite_respects_opacity():
    # LOGIC-005: a semi-transparent top layer mixes toward the backdrop.
    bottom = _layer(2, 2, RED)
    top = _layer(2, 2, BLUE, opacity=0.5)
    out = composite_stack([bottom, top], 2, 2)
    r, g, b, a = out.get_pixel(0, 0)
    assert 0 < b < 255 and 0 < r < 255 and a == 255


def test_composite_respects_blend_mode():
    # LOGIC-007: a MULTIPLY top layer darkens rather than replacing.
    bottom = _layer(2, 2, (128, 128, 128, 255))
    top = _layer(2, 2, (128, 128, 128, 255), blend_mode=BlendMode.MULTIPLY)
    out = composite_stack([bottom, top], 2, 2)
    assert out.get_pixel(0, 0) == (64, 64, 64, 255)


def test_composite_group_flattened_then_blended_as_one():
    # LOGIC-011: a group is flattened internally then blended as a single unit.
    inner_bottom = _layer(2, 2, RED)
    inner_top = _layer(2, 2, BLUE)
    group = LayerGroup("G", [inner_bottom, inner_top], opacity=0.5)
    base = _layer(2, 2, GREEN)
    out = composite_stack([base, group], 2, 2)
    # Group flattens to BLUE (top wins), then blends at 0.5 over GREEN.
    r, g, b, a = out.get_pixel(0, 0)
    assert b > 0 and g > 0  # both the flattened blue and the green backdrop show


def test_composite_hidden_group_is_a_noop():
    inner = _layer(2, 2, BLUE)
    group = LayerGroup("G", [inner], visible=False)
    base = _layer(2, 2, RED)
    out = composite_stack([base, group], 2, 2)
    assert out.get_pixel(0, 0) == RED


def test_composite_region_scopes_recomposite():
    # ADR-0007 §Amendment (T13) D1 / B1: region=(x,y,w,h) returns a region-SIZED
    # (h, w, 4) buffer with implied scene origin (x, y) -- NOT a full-canvas
    # buffer with the outside left transparent. Only in-region reads are valid.
    bottom = _layer(4, 4, RED)
    top = _layer(4, 4, BLUE)
    out = composite_stack([bottom, top], 4, 4, region=(0, 0, 2, 2))
    assert (out.width, out.height) == (2, 2)  # region-sized buffer (B1)
    assert out.data.shape == (2, 2, 4)
    assert out.get_pixel(0, 0) == BLUE  # inside region: top wins
    # Coordinate (3, 3) lies outside a 2x2 buffer -> indexing raises (was: the
    # old contract returned transparent there from a full-canvas buffer, B1).
    with pytest.raises(PixelBufferError):
        out.get_pixel(3, 3)


def test_composite_out_of_bounds_region_raises():
    # B3: the compositor VALIDATES, it never silently clamps. A region that
    # leaves the canvas (was clamped-to-empty -> transparent full canvas)
    # now raises BlendError. Caller must clamp its dirty rect before calling.
    bottom = _layer(4, 4, RED)
    with pytest.raises(BlendError):
        composite_stack([bottom], 4, 4, region=(10, 10, 5, 5))  # fully OOB


@pytest.mark.parametrize(
    "region",
    [
        (10, 10, 5, 5),  # origin off-canvas
        (2, 2, 4, 4),  # x+w and y+h overflow the 4x4 canvas
        (-1, 0, 2, 2),  # negative x
        (0, -1, 2, 2),  # negative y
        (0, 0, 0, 2),  # degenerate width
        (0, 0, 2, 0),  # degenerate height
        (0, 0, -1, 2),  # negative width
        (0, 0, 2, -3),  # negative height
        (0, 0, 5, 2),  # x+w > width
        (0, 0, 2, 5),  # y+h > height
    ],
)
def test_composite_region_invalid_raises_blenderror(region):
    # B3: out-of-bounds / degenerate / negative regions all raise (no clamp).
    bottom = _layer(4, 4, RED)
    with pytest.raises(BlendError):
        composite_stack([bottom], 4, 4, region=region)


def test_composite_region_malformed_tuple_raises():
    # B3: a malformed region tuple (wrong arity / non-int) raises BlendError.
    bottom = _layer(4, 4, RED)
    with pytest.raises(BlendError):
        composite_stack([bottom], 4, 4, region=(0, 0, 2))  # type: ignore[arg-type]
    with pytest.raises(BlendError):
        composite_stack([bottom], 4, 4, region=("a", 0, 2, 2))  # type: ignore[arg-type]


def test_composite_rejects_indexed_buffer():
    idx = Layer(PixelBuffer(2, 2, ColorMode.INDEXED), "idx")
    with pytest.raises(BlendError):
        composite_stack([idx], 2, 2)


def test_composite_rejects_wrong_geometry():
    small = _layer(2, 2, RED)
    with pytest.raises(BlendError):
        composite_stack([small], 4, 4)  # buffer 2x2 != canvas 4x4


def test_composite_mask_modulates_layer():
    # LOGIC-012: a zero mask on the top layer hides it in the composite.
    bottom = _layer(2, 2, RED)
    mask = PixelBuffer(2, 2, ColorMode.RGBA)  # all transparent -> alpha 0
    top = _layer(2, 2, BLUE, mask=mask)
    out = composite_stack([bottom, top], 2, 2)
    assert out.get_pixel(0, 0) == RED


# --------------------------------------------------------------------------- #
# T13 D1/B1/B2 regressions — region-sized return + scene-coordinate mapping.  #
# --------------------------------------------------------------------------- #


def _distinct_layer(w: int, h: int, base: int) -> Layer:
    """A layer whose pixels are a deterministic function of (x, y) so a region
    slice can be checked against its scene coordinates."""
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    for y in range(h):
        for x in range(w):
            buf.set_pixel(x, y, ((base + x) % 256, (base + y) % 256, x % 256, 255))
    return Layer(buf, "distinct")


@pytest.mark.parametrize(
    "region", [(0, 0, 2, 2), (1, 1, 3, 2), (2, 3, 2, 1), (0, 0, 5, 5)]
)
def test_composite_region_shape_is_exactly_hxwx4(region):
    # B1/B2: the region path returns a region-SIZED (h, w, 4) PixelBuffer with
    # implied origin (x, y) -- never a full-canvas buffer.
    x, y, w, h = region
    bottom = _distinct_layer(5, 5, 10)
    out = composite_stack([bottom], 5, 5, region=region)
    assert out.data.shape == (h, w, 4)
    assert (out.width, out.height) == (w, h)
    # And it is genuinely smaller than a full-canvas buffer unless region==canvas.
    assert out.data.nbytes == h * w * 4


def test_composite_region_pixels_match_scene_coordinates():
    # B1: region element (row i, col j) == scene pixel (x + j, y + i). Cross-check
    # the region path against the full-canvas composite at the same scene coords.
    x, y, w, h = 1, 2, 3, 2
    bottom = _distinct_layer(6, 6, 30)
    top = _layer(6, 6, (0, 0, 0, 0))  # fully transparent top: bottom shows through
    full = composite_stack([bottom, top], 6, 6)  # region=None -> full canvas
    region = composite_stack([bottom, top], 6, 6, region=(x, y, w, h))
    for i in range(h):
        for j in range(w):
            assert region.get_pixel(j, i) == full.get_pixel(x + j, y + i)


def test_composite_region_never_allocates_full_canvas():
    # B2: guard against the ~126 MB full-canvas alloc regression -- a large canvas
    # with a tiny region returns a tiny (h, w, 4) buffer, not a canvas-sized one.
    canvas = 256
    bottom = _layer(canvas, canvas, RED)
    top = _layer(canvas, canvas, BLUE)
    out = composite_stack([bottom, top], canvas, canvas, region=(10, 20, 2, 3))
    assert out.data.shape == (3, 2, 4)  # region-sized (h=3, w=2)
    assert out.data.nbytes == 3 * 2 * 4  # 24 bytes, NOT canvas*canvas*4
    assert out.data.nbytes < canvas * canvas * 4
    assert out.get_pixel(0, 0) == BLUE  # top wins inside the region


def test_composite_region_equals_full_canvas_when_region_is_whole_canvas():
    # B1: region == full canvas must equal the region=None composite exactly.
    bottom = _distinct_layer(4, 4, 5)
    top = _layer(4, 4, (0, 0, 0, 0))
    full = composite_stack([bottom, top], 4, 4)
    whole = composite_stack([bottom, top], 4, 4, region=(0, 0, 4, 4))
    assert np.array_equal(full.data, whole.data)


# --------------------------------------------------------------------------- #
# T13 D5/B4 regression — float32 working dtype is uint8-invisible for W3C.     #
# --------------------------------------------------------------------------- #

# Canonical W3C separable known values (independent of the implementation).
_W3C_UINT8 = [
    (BlendMode.MULTIPLY, 128, 128, 64),
    (BlendMode.MULTIPLY, 255, 200, 200),
    (BlendMode.SCREEN, 0, 200, 200),
    (BlendMode.SCREEN, 128, 128, 192),  # 2x - x^2 -> 0.752 -> 191.75 -> 192
    (BlendMode.OVERLAY, 128, 128, 128),
    (BlendMode.DARKEN, 100, 200, 100),
    (BlendMode.LIGHTEN, 100, 200, 200),
    (BlendMode.DIFFERENCE, 200, 50, 150),
    (BlendMode.EXCLUSION, 64, 64, 96),  # 2x(1-x) -> 0.376 -> 95.9 -> 96
    (BlendMode.HARD_LIGHT, 128, 128, 128),
]


@pytest.mark.parametrize("mode, cb, cs, expected", _W3C_UINT8)
def test_float32_dtype_is_uint8_invisible_for_w3c_values(mode, cb, cs, expected):
    # B4: the float32 working space yields the SAME uint8 bytes as the known W3C
    # values -- both via the array path and the single-pixel path.
    src = np.full((2, 2, 4), (cs, cs, cs, 255), dtype=np.uint8)
    dst = np.full((2, 2, 4), (cb, cb, cb, 255), dtype=np.uint8)
    out = blend_arrays(mode, src, dst)
    assert tuple(int(v) for v in out[0, 0]) == (expected, expected, expected, 255)
    r, g, b, a = blend_pixels(mode, (cs, cs, cs, 255), (cb, cb, cb, 255))
    assert (r, g, b, a) == (expected, expected, expected, 255)


def test_float32_working_arrays_are_not_float64():
    # B4: assert the compositor's intermediate really is float32 (the ADR-0005
    # working dtype), so this invariant regresses loudly if it reverts to float64.
    captured = {}
    original = np.empty_like

    def _spy(arr, *a, **k):
        captured["dtype"] = arr.dtype
        return original(arr, *a, **k)

    import pixelart_creator.logic.blend as blend_mod

    blend_mod.np.empty_like = _spy  # type: ignore[assignment]
    try:
        blend_arrays(
            BlendMode.MULTIPLY,
            np.full((2, 2, 4), 128, dtype=np.uint8),
            np.full((2, 2, 4), 128, dtype=np.uint8),
        )
    finally:
        blend_mod.np.empty_like = original  # type: ignore[assignment]
    assert captured["dtype"] == np.float32


# --------------------------------------------------------------------------- #
# T13 D4/B5 regressions — group flatten cache reuse + no-stale-composite.      #
# --------------------------------------------------------------------------- #


def test_group_flatten_cache_populated_and_reused():
    # B5/D4: the first composite populates LayerGroup._composite_cache for the
    # region; a second call with the SAME region reuses it (same array object).
    inner = _layer(4, 4, BLUE)
    group = LayerGroup("G", [inner])
    base = _layer(4, 4, RED)
    assert group._composite_cache is None
    composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    assert group._composite_cache is not None
    key, cached = group._composite_cache
    assert key == (0, 0, 2, 2)
    composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    # Same region -> the cached ndarray object is reused, not rebuilt.
    assert group._composite_cache[1] is cached


def test_group_flatten_cache_never_serves_wrong_composite_after_child_edit():
    # B5/SC-UI-012-2: after editing a child buffer, clearing the cache yields a
    # composite that reflects the change (a stale cache must NEVER win).
    inner = _layer(4, 4, BLUE)
    group = LayerGroup("G", [inner])
    base = _layer(4, 4, RED)
    first = composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    assert first.get_pixel(0, 0) == BLUE
    # Edit the child pixel then invalidate the group's cache (the document layer
    # does this up the ancestor chain; here we assert the compositor honours it).
    inner.buffer.set_pixel(0, 0, GREEN)
    group._composite_cache = None
    updated = composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    assert updated.get_pixel(0, 0) == GREEN


def test_group_flatten_stale_cache_would_be_wrong_without_invalidation():
    # B5: demonstrates WHY invalidation is mandatory -- if the cache is NOT
    # cleared, a same-region recomposite serves the stale (pre-edit) flatten.
    inner = _layer(4, 4, BLUE)
    group = LayerGroup("G", [inner])
    base = _layer(4, 4, RED)
    composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))  # populate cache
    inner.buffer.set_pixel(0, 0, GREEN)  # edit WITHOUT invalidating
    stale = composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    assert stale.get_pixel(0, 0) == BLUE  # stale flatten reused (documents the risk)


def test_group_cache_keyed_by_region():
    # D4: the cache is a single-entry MRU keyed by region; a different region
    # replaces the entry (and recomputes) rather than returning a wrong slice.
    inner = _distinct_layer(4, 4, 7)
    group = LayerGroup("G", [inner])
    base = _layer(4, 4, (0, 0, 0, 0))
    composite_stack([base, group], 4, 4, region=(0, 0, 2, 2))
    assert group._composite_cache[0] == (0, 0, 2, 2)
    composite_stack([base, group], 4, 4, region=(2, 2, 2, 2))
    assert group._composite_cache[0] == (2, 2, 2, 2)


def test_composite_region_group_mask_opacity_combined():
    # B5: region + nested group + mask + opacity still composite correctly.
    # Build a group (inner BLUE) at 0.5 opacity with a full-pass mask over a RED
    # base, and read a sub-region; compare against the full-canvas composite.
    inner = _layer(4, 4, BLUE)
    mask = PixelBuffer(4, 4, ColorMode.RGBA)
    mask.fill((255, 255, 255, 255))  # full-pass mask
    group = LayerGroup("G", [inner], opacity=0.5, mask=mask)
    base = _layer(4, 4, RED)
    full = composite_stack([base, group], 4, 4)
    region = composite_stack([base, group], 4, 4, region=(1, 1, 2, 2))
    for i in range(2):
        for j in range(2):
            assert region.get_pixel(j, i) == full.get_pixel(1 + j, 1 + i)
    # Half-opacity blue over red -> both channels present (purple-ish), a==255.
    r, g, b, a = region.get_pixel(0, 0)
    assert r > 0 and b > 0 and a == 255
