"""Byte-exactness + helper tests for the Phase-12 Slice-B ``composite_range`` seam.

Phase-12 Slice B (ADR-0034) added a contiguous-range composite seam to
``logic/blend.py`` to drive the opacity-drag / viewport recomposite: a split
cache around a dragged layer index ``k`` where

* ``below  = composite_range(nodes, W, H, 0, k)`` — the exact prefix accumulator,
* the **byte-exact COMMIT** = ``composite_range(nodes, W, H, k, N, base=below)`` —
  re-blends the suffix ``nodes[k:N]`` over the cached prefix.

REQ-P12-LOGIC-004 makes the *commit* byte-exactness a HARD acceptance criterion:
``below`` then the ``base=below`` suffix re-blend must be byte-identical to
``composite_stack`` over the full stack, for NORMAL *and* all 11 separable modes,
**including partial-alpha / anti-aliased content under non-NORMAL above layers** —
exactly where the ``above``-pre-flatten associativity shortcut was measured to
diverge by <= 2 LSB (ADR-0034 Amendment 2026-07-07). The commit is exact *by
construction* (identical ``_reduce_nodes`` reduction seeded by the exact prefix),
not by associativity; these tests pin that.

They also cover:
* PREFIX exactness — ``composite_range(nodes, 0, k)`` equals ``composite_stack``
  over ``nodes[:k]`` (over full-region, sub-rect, and ``region=None``);
* the ``is_range_source_over`` preview-eligibility predicate (true only for
  NORMAL / opacity-1.0 / unmasked visible nodes);
* the nearest-neighbour ``downsample_nn`` / ``upsample_nn`` LOD helpers (no
  interpolation, deterministic, shape / round-trip, bounded by
  ``OPACITY_PREVIEW_MAX_PX``).

Maps to REQ-P12-LOGIC-004 (commit byte-exact) + REQ-P12-UI-001 (LOD preview
helpers); acceptance SC-P12-LOGIC-004-2. No Qt (S11); deterministic + headless
(S13). The oracle is the shipped ``composite_stack`` — the "current compositor"
the requirement pins byte-equality against.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import pixelart_creator.logic.blend as blend_mod
from pixelart_creator.logic.blend import (
    BlendError,
    BlendMode,
    composite_range,
    composite_stack,
    downsample_nn,
    is_range_source_over,
    upsample_nn,
)
from pixelart_creator.logic.constants import OPACITY_PREVIEW_MAX_PX
from pixelart_creator.logic.document import Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

# --------------------------------------------------------------------------- #
# Mode vocabularies (single-sourced from the enum, never hand-listed).         #
# --------------------------------------------------------------------------- #

ALL_MODES = list(BlendMode)
SEPARABLE_MODES = [m for m in BlendMode if m is not BlendMode.NORMAL]


def test_separable_mode_count_is_eleven():
    # Anchors the "12 modes = NORMAL + 11 separable" this suite must prove
    # commit-byte-exact; a future enum change surfaces here, not silently.
    assert len(ALL_MODES) == 12
    assert len(SEPARABLE_MODES) == 11
    assert BlendMode.NORMAL not in SEPARABLE_MODES


# --------------------------------------------------------------------------- #
# Deterministic content + layer/stack builders.                                #
# --------------------------------------------------------------------------- #


def _layer_from_array(arr: np.ndarray, **kw) -> Layer:
    """Build a :class:`Layer` whose RGBA buffer is a copy of ``arr``."""
    h, w = arr.shape[:2]
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.data[:, :] = arr
    return Layer(buf, kw.pop("name", "L"), **kw)


def _mask_from_array(arr: np.ndarray) -> PixelBuffer:
    """Build an RGBA mask :class:`PixelBuffer` from an ``(h, w, 4)`` array."""
    h, w = arr.shape[:2]
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.data[:, :] = arr
    return buf


def _rand_rgba(seed: int, h: int, w: int, *, sparsity: float = 0.4) -> np.ndarray:
    """Deterministic random RGBA with ``sparsity`` fraction of alpha==0 pixels."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(h, w, 4), dtype=np.uint8)
    if sparsity > 0.0:
        transparent = rng.random((h, w)) < sparsity
        arr[transparent, 3] = 0
    return arr


def _opaque_rgba(seed: int, h: int, w: int) -> np.ndarray:
    """Deterministic random RGB with full (255) alpha everywhere."""
    arr = _rand_rgba(seed, h, w, sparsity=0.0)
    arr[:, :, 3] = 255
    return arr


def _partial_alpha_rgba(seed: int, h: int, w: int) -> np.ndarray:
    """Deterministic random RGBA with alpha strictly in ``1..254`` (all fractional).

    This is the anti-aliased / semi-transparent content class where the
    ``above``-pre-flatten shortcut was measured to diverge by <= 2 LSB even under
    ``is_range_source_over`` (ADR-0034 Amendment): the ``base=below`` suffix
    re-blend commit must still be byte-exact here.
    """
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(h, w, 4), dtype=np.uint8)
    # Force every alpha into the open (0, 255) interval -> genuinely partial.
    arr[:, :, 3] = rng.integers(1, 255, size=(h, w), dtype=np.uint8)
    return arr


def _stack_for_mode(mode: BlendMode, h: int, w: int, *, partial: bool) -> list:
    """A multi-layer stack whose *above* layers use ``mode`` (partial-alpha option).

    Ordered bottom-to-top: an opaque NORMAL base, then several partial/full-alpha
    layers interleaving NORMAL and ``mode`` (some at opacity < 1.0, one masked).
    With >= 5 layers there are multiple interior splits ``k`` whose suffix
    (the *above* stack) contains non-NORMAL ``mode`` layers over the dragged one —
    the exact case ADR-0034's amendment says the pre-flatten shortcut breaks and
    the ``base=below`` re-blend must be byte-exact.
    """
    content = (
        _partial_alpha_rgba
        if partial
        else (lambda s, hh, ww: _rand_rgba(s, hh, ww, sparsity=0.3))
    )
    base = _layer_from_array(_opaque_rgba(101, h, w), name="base")
    l1 = _layer_from_array(content(102, h, w), name="n1")
    l2 = _layer_from_array(content(103, h, w), name=f"{mode.value}-a", blend_mode=mode)
    l3 = _layer_from_array(content(104, h, w), name="n2", opacity=0.65)
    mask = _mask_from_array(_partial_alpha_rgba(105, h, w))
    l4 = _layer_from_array(
        content(106, h, w),
        name=f"{mode.value}-b",
        blend_mode=mode,
        opacity=0.8,
        mask=mask,
    )
    return [base, l1, l2, l3, l4]


def _regions(w: int, h: int) -> list:
    """The region matrix: whole-canvas (None), full-region tuple, and a sub-rect."""
    return [None, (0, 0, w, h), (3, 2, w - 8, h - 6)]


# --------------------------------------------------------------------------- #
# Assertions — prefix + commit byte-exactness vs the shipped composite_stack.  #
# --------------------------------------------------------------------------- #


def _assert_prefix_byte_exact(nodes, w, h, region) -> None:
    """``composite_range(nodes, 0, k)`` == ``composite_stack(nodes[:k])`` for all k."""
    n = len(nodes)
    for k in range(0, n + 1):
        prefix = composite_range(nodes, w, h, 0, k, region=region)
        oracle = composite_stack(list(nodes[:k]), w, h, region=region)
        assert prefix.data.dtype == np.uint8
        assert prefix.data.shape == oracle.data.shape
        assert np.array_equal(prefix.data, oracle.data), f"prefix k={k} region={region}"


def _assert_commit_byte_exact(nodes, w, h, region) -> None:
    """The split-cache commit == the full ``composite_stack`` for every split k.

    ``below = composite_range(nodes, 0, k)``; ``commit =
    composite_range(nodes, k, N, base=below)`` MUST be byte-identical to
    ``composite_stack(nodes)`` (REQ-P12-LOGIC-004 / ADR-0034 §3 + Amendment §b).
    """
    n = len(nodes)
    full = composite_stack(list(nodes), w, h, region=region)
    for k in range(0, n + 1):
        below = composite_range(nodes, w, h, 0, k, region=region)
        commit = composite_range(nodes, w, h, k, n, region=region, base=below.data)
        assert commit.data.dtype == np.uint8
        assert commit.data.shape == full.data.shape
        assert np.array_equal(commit.data, full.data), (
            f"COMMIT byte-exact FAILED at k={k}, region={region} — "
            f"suffix re-blend diverged from composite_stack"
        )


# --------------------------------------------------------------------------- #
# 1. PREFIX byte-exactness — NORMAL + every separable mode, all regions.       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", ALL_MODES)
def test_prefix_byte_exact_each_mode_hard_edged(mode):
    # composite_range(...,0,k) == composite_stack(nodes[:k]) for hard-edged
    # content, across full-region, sub-rect and region=None.
    h, w = 30, 33
    nodes = _stack_for_mode(mode, h, w, partial=False)
    for region in _regions(w, h):
        _assert_prefix_byte_exact(nodes, w, h, region)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_prefix_byte_exact_each_mode_partial_alpha(mode):
    # Same prefix invariant on genuinely partial-alpha (anti-aliased) content.
    h, w = 28, 31
    nodes = _stack_for_mode(mode, h, w, partial=True)
    for region in _regions(w, h):
        _assert_prefix_byte_exact(nodes, w, h, region)


def test_prefix_empty_range_is_transparent():
    # composite_range(...,0,0) folds no nodes -> transparent, == composite_stack([]).
    h, w = 12, 14
    nodes = _stack_for_mode(BlendMode.MULTIPLY, h, w, partial=True)
    for region in _regions(w, h):
        prefix = composite_range(nodes, w, h, 0, 0, region=region)
        assert not prefix.data.any()  # all-zero transparent rect
        assert np.array_equal(
            prefix.data, composite_stack([], w, h, region=region).data
        )


# --------------------------------------------------------------------------- #
# 2. COMMIT byte-exactness — the hard REQ-P12-LOGIC-004 acceptance.            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", ALL_MODES)
def test_commit_byte_exact_each_mode_hard_edged(mode):
    # below then base=below suffix re-blend == full composite_stack, hard-edged.
    h, w = 30, 33
    nodes = _stack_for_mode(mode, h, w, partial=False)
    for region in _regions(w, h):
        _assert_commit_byte_exact(nodes, w, h, region)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_commit_byte_exact_each_mode_partial_alpha_non_normal_above(mode):
    # THE HARD CASE (ADR-0034 Amendment): partial-alpha content with non-NORMAL
    # ``mode`` layers ABOVE the split. The pre-flatten shortcut diverges by
    # <= 2 LSB here; the base=below suffix re-blend must be byte-EXACT for every
    # split k, every region, every mode.
    h, w = 28, 31
    nodes = _stack_for_mode(mode, h, w, partial=True)
    for region in _regions(w, h):
        _assert_commit_byte_exact(nodes, w, h, region)


def test_commit_byte_exact_representative_mixed_stack():
    # A single mixed stack (opaque base, partial NORMAL, transparent, faded,
    # masked, MULTIPLY, SOFT_LIGHT) — the same content matrix Slice A used —
    # commits byte-exact for every split and region.
    h, w = 26, 29
    base = _layer_from_array(_opaque_rgba(1, h, w), name="opaque-base")
    partial = _layer_from_array(_partial_alpha_rgba(2, h, w), name="partial")
    transparent = _layer_from_array(np.zeros((h, w, 4), np.uint8), name="clear")
    faded = _layer_from_array(_partial_alpha_rgba(3, h, w), name="faded", opacity=0.6)
    mask = _mask_from_array(_opaque_rgba(4, h, w))
    masked = _layer_from_array(_opaque_rgba(5, h, w), name="masked", mask=mask)
    mul = _layer_from_array(
        _partial_alpha_rgba(6, h, w), name="mul", blend_mode=BlendMode.MULTIPLY
    )
    soft = _layer_from_array(
        _partial_alpha_rgba(7, h, w),
        name="soft",
        blend_mode=BlendMode.SOFT_LIGHT,
        opacity=0.8,
    )
    nodes = [base, partial, transparent, faded, masked, mul, soft]
    for region in _regions(w, h):
        _assert_commit_byte_exact(nodes, w, h, region)


def test_commit_byte_exact_with_nested_group_above():
    # A nested group (flattened then blended as one, non-normal + masked + faded)
    # sitting ABOVE the split still commits byte-exact via the suffix re-blend.
    h, w = 24, 22
    base = _layer_from_array(_opaque_rgba(31, h, w), name="base")
    dragged = _layer_from_array(_partial_alpha_rgba(32, h, w), name="dragged")
    inner_a = _layer_from_array(_opaque_rgba(33, h, w), name="ia")
    inner_b = _layer_from_array(
        _partial_alpha_rgba(34, h, w), name="ib", blend_mode=BlendMode.SCREEN
    )
    gmask = _mask_from_array(_opaque_rgba(35, h, w))
    group = LayerGroup(
        "G", [inner_a, inner_b], opacity=0.7, blend_mode=BlendMode.OVERLAY, mask=gmask
    )
    nodes = [base, dragged, group]
    for region in _regions(w, h):
        _assert_commit_byte_exact(nodes, w, h, region)


def test_commit_base_is_not_mutated():
    # composite_range must copy ``base`` defensively (never fold over the caller's
    # cached ``below`` array) — the split-cache reuses ``below`` across ticks.
    h, w = 16, 18
    nodes = _stack_for_mode(BlendMode.MULTIPLY, h, w, partial=True)
    k = 2
    below = composite_range(nodes, w, h, 0, k)
    snapshot = below.data.copy()
    _ = composite_range(nodes, w, h, k, len(nodes), base=below.data)
    assert np.array_equal(below.data, snapshot)  # below untouched


# --------------------------------------------------------------------------- #
# 3. composite_range argument validation.                                      #
# --------------------------------------------------------------------------- #


def test_composite_range_rejects_bad_bounds():
    h, w = 8, 8
    nodes = _stack_for_mode(BlendMode.NORMAL, h, w, partial=False)
    n = len(nodes)
    for start, stop in [(-1, 2), (2, 1), (0, n + 1), (n + 1, n + 2)]:
        with pytest.raises(BlendError):
            composite_range(nodes, w, h, start, stop)


def test_composite_range_rejects_bad_base_geometry():
    h, w = 10, 12
    nodes = _stack_for_mode(BlendMode.NORMAL, h, w, partial=False)
    wrong_shape = np.zeros((h + 1, w, 4), dtype=np.uint8)
    wrong_dtype = np.zeros((h, w, 4), dtype=np.float32)
    with pytest.raises(BlendError):
        composite_range(nodes, w, h, 0, 1, base=wrong_shape)
    with pytest.raises(BlendError):
        composite_range(nodes, w, h, 0, 1, base=wrong_dtype)


def test_composite_range_rejects_out_of_bounds_region():
    h, w = 10, 12
    nodes = _stack_for_mode(BlendMode.NORMAL, h, w, partial=False)
    with pytest.raises(BlendError):
        composite_range(nodes, w, h, 0, 1, region=(5, 5, w, h))  # exceeds canvas


# --------------------------------------------------------------------------- #
# 4. is_range_source_over predicate.                                           #
# --------------------------------------------------------------------------- #


def test_is_range_source_over_empty_is_true():
    assert is_range_source_over([]) is True


def test_is_range_source_over_all_plain_normal_is_true():
    h, w = 4, 4
    nodes = [
        _layer_from_array(_opaque_rgba(1, h, w), name="a"),
        _layer_from_array(_partial_alpha_rgba(2, h, w), name="b"),
    ]
    assert is_range_source_over(nodes) is True


@pytest.mark.parametrize("mode", SEPARABLE_MODES)
def test_is_range_source_over_false_for_non_normal_mode(mode):
    h, w = 4, 4
    nodes = [
        _layer_from_array(_opaque_rgba(1, h, w), name="a"),
        _layer_from_array(_opaque_rgba(2, h, w), name="b", blend_mode=mode),
    ]
    assert is_range_source_over(nodes) is False


def test_is_range_source_over_false_for_partial_opacity():
    h, w = 4, 4
    nodes = [_layer_from_array(_opaque_rgba(1, h, w), name="a", opacity=0.5)]
    assert is_range_source_over(nodes) is False


def test_is_range_source_over_false_for_masked_layer():
    h, w = 4, 4
    mask = _mask_from_array(_opaque_rgba(9, h, w))
    nodes = [_layer_from_array(_opaque_rgba(1, h, w), name="a", mask=mask)]
    assert is_range_source_over(nodes) is False


def test_is_range_source_over_skips_hidden_disqualifiers():
    # Hidden nodes contribute nothing, so an invisible non-normal / masked /
    # faded layer cannot break the source-over eligibility of the visible range.
    h, w = 4, 4
    mask = _mask_from_array(_opaque_rgba(9, h, w))
    nodes = [
        _layer_from_array(_opaque_rgba(1, h, w), name="ok"),
        _layer_from_array(
            _opaque_rgba(2, h, w),
            name="hidden-mul",
            blend_mode=BlendMode.MULTIPLY,
            opacity=0.3,
            mask=mask,
            visible=False,
        ),
    ]
    assert is_range_source_over(nodes) is True


def test_is_range_source_over_false_when_visible_disqualifier_present():
    h, w = 4, 4
    nodes = [
        _layer_from_array(_opaque_rgba(1, h, w), name="ok"),
        _layer_from_array(
            _opaque_rgba(2, h, w), name="mul", blend_mode=BlendMode.MULTIPLY
        ),
    ]
    assert is_range_source_over(nodes) is False


# --------------------------------------------------------------------------- #
# 5. downsample_nn / upsample_nn — NN, deterministic, shape / round-trip.      #
# --------------------------------------------------------------------------- #


def test_downsample_nn_is_top_left_stride_sample():
    # Pure stride subsample arr[::f, ::f] — the top-left of each f x f block,
    # NO interpolation / averaging.
    arr = _rand_rgba(1, 12, 16, sparsity=0.0)
    out = downsample_nn(arr, 3)
    assert out.shape == (math.ceil(12 / 3), math.ceil(16 / 3), 4)
    assert np.array_equal(out, arr[::3, ::3])
    assert out.dtype == np.uint8


def test_downsample_nn_factor_one_is_identity_content():
    arr = _rand_rgba(2, 7, 9, sparsity=0.0)
    out = downsample_nn(arr, 1)
    assert out.shape == arr.shape
    assert np.array_equal(out, arr)


def test_downsample_nn_deterministic():
    arr = _rand_rgba(3, 10, 10, sparsity=0.3)
    assert np.array_equal(downsample_nn(arr, 2), downsample_nn(arr, 2))


def test_downsample_nn_rejects_factor_below_one():
    arr = _rand_rgba(4, 4, 4)
    with pytest.raises(BlendError):
        downsample_nn(arr, 0)


def test_upsample_nn_is_pixel_replication():
    # np.repeat replication — each source pixel repeated f x f, NO interpolation.
    arr = _rand_rgba(5, 4, 5, sparsity=0.0)
    out = upsample_nn(arr, 3)
    assert out.shape == (4 * 3, 5 * 3, 4)
    for i in range(out.shape[0]):
        for j in range(out.shape[1]):
            assert tuple(out[i, j]) == tuple(arr[i // 3, j // 3])


def test_upsample_nn_out_shape_crops():
    arr = _rand_rgba(6, 4, 4, sparsity=0.0)
    out = upsample_nn(arr, 3, out_shape=(10, 11))
    assert out.shape == (10, 11, 4)
    assert np.array_equal(out, np.repeat(np.repeat(arr, 3, 0), 3, 1)[:10, :11])


def test_upsample_nn_rejects_bad_args():
    arr = _rand_rgba(7, 4, 4)
    with pytest.raises(BlendError):
        upsample_nn(arr, 0)
    with pytest.raises(BlendError):
        upsample_nn(arr, 2, out_shape=(0, 5))


def test_downsample_then_upsample_is_block_constant_round_trip():
    # upsample(downsample(x, f), f, out_shape=x) == the f x f block-constant view
    # where each block takes x's top-left sample (NN LOD display step).
    arr = _rand_rgba(8, 15, 13, sparsity=0.0)
    f = 4
    lod = downsample_nn(arr, f)
    restored = upsample_nn(lod, f, out_shape=arr.shape[:2])
    assert restored.shape == arr.shape
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            assert tuple(restored[i, j]) == tuple(arr[(i // f) * f, (j // f) * f])


def test_downsample_then_upsample_factor_one_is_identity():
    arr = _rand_rgba(9, 6, 8, sparsity=0.2)
    lod = downsample_nn(arr, 1)
    restored = upsample_nn(lod, 1, out_shape=arr.shape[:2])
    assert np.array_equal(restored, arr)


def test_downsample_factor_bounds_working_set_to_opacity_preview_max_px():
    # REQ-P12-UI-001 / ADR-0034 §2: the LOD factor is DERIVED from the single-source
    # OPACITY_PREVIEW_MAX_PX budget (no hard-coded factor). For a viewport larger
    # than the budget, downsampling by the derived factor clamps the preview
    # working set to <= OPACITY_PREVIEW_MAX_PX pixels.
    edge = int(math.isqrt(OPACITY_PREVIEW_MAX_PX)) * 2  # area == 4x the budget
    area = edge * edge
    assert area > OPACITY_PREVIEW_MAX_PX  # genuinely over-budget viewport
    factor = max(1, math.ceil(math.sqrt(area / OPACITY_PREVIEW_MAX_PX)))
    viewport = np.zeros((edge, edge, 4), dtype=np.uint8)
    lod = downsample_nn(viewport, factor)
    assert lod.shape[0] * lod.shape[1] <= OPACITY_PREVIEW_MAX_PX


# --------------------------------------------------------------------------- #
# 6. [Hypothesis] property — random stacks: split-cache commit == composite_stack
# --------------------------------------------------------------------------- #

from hypothesis import given  # noqa: E402  (placed with its strategies)
from hypothesis import strategies as st  # noqa: E402


@st.composite
def _random_stacks(draw):
    """Draw a bounded multi-layer stack spec (dims/modes/alpha/masks) + split k."""
    w = draw(st.integers(min_value=1, max_value=9))
    h = draw(st.integers(min_value=1, max_value=9))
    n = draw(st.integers(min_value=1, max_value=6))
    specs = []
    for _ in range(n):
        specs.append(
            {
                "mode": draw(st.sampled_from(ALL_MODES)),
                "opacity": draw(st.sampled_from([0.0, 0.4, 0.75, 1.0])),
                "visible": draw(st.booleans()),
                "has_mask": draw(st.booleans()),
                # 'partial' forces fractional alpha (the divergent-shortcut case);
                # others cover zero / full / mixed alpha.
                "alpha": draw(st.sampled_from(["zero", "full", "mixed", "partial"])),
                "seed": draw(st.integers(min_value=0, max_value=2**31 - 1)),
            }
        )
    k = draw(st.integers(min_value=0, max_value=n))
    return w, h, specs, k


def _content(spec, h, w):
    kind = spec["alpha"]
    if kind == "zero":
        return np.zeros((h, w, 4), dtype=np.uint8)
    if kind == "full":
        return _opaque_rgba(spec["seed"], h, w)
    if kind == "partial":
        return _partial_alpha_rgba(spec["seed"], h, w)
    return _rand_rgba(spec["seed"], h, w, sparsity=0.4)  # mixed


def _build_stack(specs, h, w):
    nodes = []
    for i, spec in enumerate(specs):
        kw = {
            "name": f"L{i}",
            "blend_mode": spec["mode"],
            "opacity": spec["opacity"],
            "visible": spec["visible"],
        }
        if spec["has_mask"]:
            kw["mask"] = _mask_from_array(_partial_alpha_rgba(spec["seed"] + 1, h, w))
        nodes.append(_layer_from_array(_content(spec, h, w), **kw))
    return nodes


@given(stack=_random_stacks())
def test_property_split_cache_commit_byte_exact_and_deterministic(stack):
    # REQ-P12-LOGIC-004 / SC-P12-LOGIC-004-2: for random bounded multi-layer stacks
    # (random modes / opacity / masks / visibility incl. partial alpha) and a random
    # split k, the split-cache commit (below then base=below suffix re-blend) is
    # byte-identical to composite_stack over the full stack, and deterministic.
    w, h, specs, k = stack
    nodes = _build_stack(specs, h, w)
    n = len(nodes)
    k = min(k, n)

    full = composite_stack(list(nodes), w, h, region=None).data
    below = composite_range(nodes, w, h, 0, k, region=None)
    commit1 = composite_range(nodes, w, h, k, n, region=None, base=below.data).data
    commit2 = composite_range(nodes, w, h, k, n, region=None, base=below.data).data

    assert np.array_equal(commit1, full)  # commit byte-exact vs composite_stack
    assert np.array_equal(commit1, commit2)  # deterministic across runs


def test_module_exposes_slice_b_seam():
    # Sanity: the Slice-B public surface is exported (composite_range +
    # predicate + NN helpers) so downstream ui/ imports resolve.
    for name in (
        "composite_range",
        "is_range_source_over",
        "downsample_nn",
        "upsample_nn",
    ):
        assert name in blend_mod.__all__
