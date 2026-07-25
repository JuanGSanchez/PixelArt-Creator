"""Byte-exactness + tiling/threading tests for the optimised full-frame flatten.

Phase-12 Slice A (ADR-0033) optimised ``composite_stack(region=None)`` with a
disjoint-tiling + threaded fan-out + exact NORMAL clear/opaque fast-path
strategy. REQ-P12-LOGIC-002 makes byte-exactness a HARD acceptance criterion:
the optimised full-frame output MUST be byte-identical to the exact per-pixel
compositor for NORMAL *and* all 11 separable blend modes, across representative
multi-layer stacks (mixed modes, partial/full/zero alpha, opacity < 1.0, masks).

These tests pin that invariant against an **independent exact reference**
(:func:`_reference_flatten`) that composites bottom-to-top through the exact
:func:`~pixelart_creator.logic.blend.blend_arrays` primitive *unconditionally*
— it never takes the clear-skip / opaque-copy fast-path and never tiles. Every
comparison therefore proves the fast-path routing **and** the tiling/threading
produce the same bytes as the pinned exact math. Tiling is exercised across
multiple :data:`FLATTEN_TILE_EDGE_PX` values (seam detection) and threading is
exercised single- vs multi-worker (:data:`FLATTEN_MAX_WORKERS`) for determinism.

Maps to REQ-P12-LOGIC-001 (bounded full-frame flatten — behaviour), -002
(byte-exact output invariance, first-class), -003 (the gated path); acceptance
scenarios SC-P12-LOGIC-002-1 (byte-exact NORMAL + 11 modes) and -002-2
(deterministic). No Qt (S11); deterministic + headless + fast (S13).
"""

from __future__ import annotations

import numpy as np
import pytest

import pixelart_creator.logic.blend as blend_mod
from pixelart_creator.logic.blend import (
    BlendMode,
    CompositeNode,
    composite_stack,
)
from pixelart_creator.logic.constants import (
    FLATTEN_MAX_WORKERS,
    FLATTEN_TILE_EDGE_PX,
)
from pixelart_creator.logic.document import Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

# --------------------------------------------------------------------------- #
# Mode vocabularies (single-sourced from the enum, never hand-listed).         #
# --------------------------------------------------------------------------- #

ALL_MODES = list(BlendMode)
SEPARABLE_MODES = [m for m in BlendMode if m is not BlendMode.NORMAL]


def test_separable_mode_count_is_eleven():
    # Anchors the "11 separable modes" this suite must prove byte-exact so a
    # future enum change surfaces here instead of silently skipping a mode.
    assert len(SEPARABLE_MODES) == 11
    assert BlendMode.NORMAL not in SEPARABLE_MODES


# --------------------------------------------------------------------------- #
# Independent EXACT reference — the test oracle (NOT the optimised product).   #
# --------------------------------------------------------------------------- #


def _reference_composite_region(
    nodes,
    width: int,
    height: int,
    x: int,
    y: int,
    rw: int,
    rh: int,
) -> np.ndarray:
    """Exact bottom-to-top composite of ``nodes`` over ``(x, y, rw, rh)``.

    Deliberately mirrors the *semantics* of the product's ``_composite_region``
    but **always** routes every visible node through the exact
    :func:`blend_arrays` primitive — it never takes the clear-skip or
    opaque-copy fast-path and never tiles. Comparing the optimised full-frame
    flatten against this pins BOTH the fast-path routing AND the tiling/threading
    to the exact per-pixel math (REQ-P12-LOGIC-002).
    """
    acc = np.zeros((rh, rw, 4), dtype=np.uint8)
    for node in nodes:
        if not node.visible:
            continue
        children = getattr(node, "children", None)
        if children is not None:
            src = _reference_composite_region(children, width, height, x, y, rw, rh)
        else:
            buf = node.effective_buffer()
            src = np.ascontiguousarray(buf.data[y : y + rh, x : x + rw])
        mask_arr = None
        if node.mask is not None:
            mask_arr = node.mask.data[y : y + rh, x : x + rw]
        acc = blend_mod.blend_arrays(
            node.blend_mode, src, acc, opacity=node.opacity, mask=mask_arr
        )
    return acc


def _reference_flatten(nodes, width: int, height: int) -> np.ndarray:
    """Exact whole-canvas flatten reference (single-shot, fast-path-free)."""
    return _reference_composite_region(nodes, width, height, 0, 0, width, height)


# --------------------------------------------------------------------------- #
# Layer / stack builders (deterministic content).                              #
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


def _representative_stack(h: int, w: int) -> list:
    """A mixed multi-layer stack covering the REQ-P12-LOGIC-002 content matrix.

    Includes: a fully-opaque NORMAL base (opaque fast-path), a NORMAL layer
    with partial alpha, a fully-transparent NORMAL layer (clear fast-path skip),
    a NORMAL layer at opacity < 1.0 (float fall-back), a masked NORMAL layer
    (float fall-back), and several non-normal separable-mode layers.
    """
    base = _layer_from_array(_opaque_rgba(1, h, w), name="opaque-base")
    partial = _layer_from_array(_rand_rgba(2, h, w, sparsity=0.5), name="partial")
    transparent = _layer_from_array(
        np.zeros((h, w, 4), dtype=np.uint8), name="transparent"
    )
    faded = _layer_from_array(
        _rand_rgba(3, h, w, sparsity=0.3), name="faded", opacity=0.6
    )
    mask = _mask_from_array(_rand_rgba(4, h, w, sparsity=0.0))
    masked = _layer_from_array(_opaque_rgba(5, h, w), name="masked", mask=mask)
    multiply = _layer_from_array(
        _rand_rgba(6, h, w, sparsity=0.2),
        name="mul",
        blend_mode=BlendMode.MULTIPLY,
    )
    soft = _layer_from_array(
        _rand_rgba(7, h, w, sparsity=0.2),
        name="soft",
        blend_mode=BlendMode.SOFT_LIGHT,
        opacity=0.8,
    )
    return [base, partial, transparent, faded, masked, multiply, soft]


def _single_mode_stack(mode: BlendMode, h: int, w: int) -> list:
    """An opaque base + one ``mode`` layer with partial alpha over it."""
    base = _layer_from_array(_opaque_rgba(11, h, w), name="base")
    top = _layer_from_array(
        _rand_rgba(12, h, w, sparsity=0.35), name=mode.value, blend_mode=mode
    )
    return [base, top]


def _assert_full_frame_byte_exact(nodes, width: int, height: int) -> None:
    """Assert ``composite_stack(region=None)`` == the exact reference, byte-wise."""
    out = composite_stack(nodes, width, height, region=None)
    reference = _reference_flatten(nodes, width, height)
    assert out.data.shape == (height, width, 4)
    assert out.data.dtype == np.uint8
    assert np.array_equal(out.data, reference)


# --------------------------------------------------------------------------- #
# 1. BYTE-EXACT full-frame vs the exact reference — NORMAL + each separable.   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def small_tiles(monkeypatch):
    """Force a tiny tile edge so even small canvases exercise the tiled path."""
    monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", 8)
    return 8


def test_byte_exact_normal_full_frame(small_tiles):
    # REQ-P12-LOGIC-002 / SC-P12-LOGIC-002-1: NORMAL mode is byte-exact.
    h, w = 24, 40
    _assert_full_frame_byte_exact(_single_mode_stack(BlendMode.NORMAL, h, w), w, h)


@pytest.mark.parametrize("mode", SEPARABLE_MODES)
def test_byte_exact_each_separable_mode_full_frame(mode, small_tiles):
    # REQ-P12-LOGIC-002 / SC-P12-LOGIC-002-1: each of the 11 separable modes is
    # byte-exact through the tiled full-frame path (no seam, no fast-path drift).
    h, w = 24, 40
    _assert_full_frame_byte_exact(_single_mode_stack(mode, h, w), w, h)


def test_byte_exact_mixed_mode_stack_full_frame(small_tiles):
    # REQ-P12-LOGIC-002: a mixed-mode stack (partial alpha / full opacity / full
    # transparency / opacity < 1.0 / masks) is byte-exact vs the exact reference.
    h, w = 30, 33
    _assert_full_frame_byte_exact(_representative_stack(h, w), w, h)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_byte_exact_masked_and_partial_opacity_layer(mode, small_tiles):
    # REQ-P12-LOGIC-002: a masked, partial-opacity, non-normal layer forces the
    # exact float fall-back path; byte-exactness must still hold for every mode.
    h, w = 20, 20
    base = _layer_from_array(_opaque_rgba(21, h, w), name="base")
    mask = _mask_from_array(_rand_rgba(22, h, w, sparsity=0.3))
    top = _layer_from_array(
        _rand_rgba(23, h, w, sparsity=0.4),
        name="top",
        blend_mode=mode,
        opacity=0.55,
        mask=mask,
    )
    _assert_full_frame_byte_exact([base, top], w, h)


def test_byte_exact_nested_group_stack(small_tiles):
    # REQ-P12-LOGIC-002 / LOGIC-011: a nested group (flattened then blended as
    # one, at opacity < 1.0 with a mask, in a non-normal mode) is byte-exact.
    h, w = 26, 22
    inner_a = _layer_from_array(_opaque_rgba(31, h, w), name="ia")
    inner_b = _layer_from_array(
        _rand_rgba(32, h, w, sparsity=0.3),
        name="ib",
        blend_mode=BlendMode.SCREEN,
    )
    gmask = _mask_from_array(_rand_rgba(33, h, w, sparsity=0.0))
    group = LayerGroup(
        "G",
        [inner_a, inner_b],
        opacity=0.7,
        blend_mode=BlendMode.OVERLAY,
        mask=gmask,
    )
    base = _layer_from_array(_opaque_rgba(34, h, w), name="base")
    _assert_full_frame_byte_exact([base, group], w, h)


# --------------------------------------------------------------------------- #
# 2. TILING correctness — result independent of FLATTEN_TILE_EDGE_PX.          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("edge", [4, 8, 16, 64, FLATTEN_TILE_EDGE_PX])
@pytest.mark.parametrize("dims", [(40, 24), (33, 30), (1, 50), (50, 1)])
def test_tiling_result_independent_of_tile_edge(edge, dims, monkeypatch):
    # REQ-P12-LOGIC-001/-002: tile boundaries introduce no seam. For every tile
    # edge the tiled full-frame result equals the exact single-shot reference,
    # so any off-by-one at a tile boundary would surface as a mismatch.
    monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", edge)
    w, h = dims
    _assert_full_frame_byte_exact(_representative_stack(h, w), w, h)


def test_tiling_all_edges_agree_byte_for_byte(monkeypatch):
    # REQ-P12-LOGIC-002: the flatten is byte-identical across a range of tile
    # sizes (not merely each == reference), pinning tile-size independence.
    w, h = 37, 29
    nodes = _representative_stack(h, w)
    results = []
    for edge in (3, 8, 13, 64, 1024):
        monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", edge)
        results.append(composite_stack(nodes, w, h, region=None).data.copy())
    for other in results[1:]:
        assert np.array_equal(results[0], other)


def test_full_frame_equals_single_shot_region_over_tiled_canvas(monkeypatch):
    # ADR-0033 §2: the tiled region=None flatten is byte-identical to the
    # single-shot _composite_region path (region==whole canvas), which does NOT
    # tile — a direct check of "tiling changes no produced pixel".
    monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", 8)
    w, h = 41, 27  # > edge in both dims => genuinely multi-tile
    nodes = _representative_stack(h, w)
    tiled = composite_stack(nodes, w, h, region=None)
    single_shot = composite_stack(nodes, w, h, region=(0, 0, w, h))
    assert np.array_equal(tiled.data, single_shot.data)


# --------------------------------------------------------------------------- #
# 3. THREADING determinism — identical bytes across worker counts / runs.      #
# --------------------------------------------------------------------------- #


def _force_workers(monkeypatch, *, max_workers: int, cpus: int, edge: int) -> None:
    """Pin the fan-out inputs so the worker count is deterministic in test."""
    monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", edge)
    monkeypatch.setattr(blend_mod, "FLATTEN_MAX_WORKERS", max_workers)
    monkeypatch.setattr(blend_mod.os, "cpu_count", lambda: cpus)


def test_threading_single_vs_multi_worker_identical(monkeypatch):
    # REQ-P12-LOGIC-002: the threaded fan-out is independent of worker count.
    # Force the serial (workers<=1) path and the threaded (workers>=2) path over
    # the SAME multi-tile canvas; the bytes must be identical.
    w, h = 41, 33  # multiple 8-px tiles in both axes
    nodes = _representative_stack(h, w)

    _force_workers(monkeypatch, max_workers=1, cpus=FLATTEN_MAX_WORKERS, edge=8)
    serial = composite_stack(nodes, w, h, region=None).data.copy()

    _force_workers(
        monkeypatch, max_workers=FLATTEN_MAX_WORKERS, cpus=FLATTEN_MAX_WORKERS, edge=8
    )
    threaded = composite_stack(nodes, w, h, region=None).data.copy()

    assert np.array_equal(serial, threaded)
    # And both equal the exact fast-path-free reference.
    assert np.array_equal(serial, _reference_flatten(nodes, w, h))


def test_threading_deterministic_across_repeated_runs(monkeypatch):
    # SC-P12-LOGIC-002-2: repeated threaded runs yield byte-identical output
    # (completion order must never perturb the result).
    w, h = 45, 37
    nodes = _representative_stack(h, w)
    _force_workers(
        monkeypatch, max_workers=FLATTEN_MAX_WORKERS, cpus=FLATTEN_MAX_WORKERS, edge=8
    )
    first = composite_stack(nodes, w, h, region=None).data.copy()
    for _ in range(5):
        again = composite_stack(nodes, w, h, region=None).data
        assert np.array_equal(first, again)


def test_serial_multi_tile_matches_threaded_and_single_tile(monkeypatch):
    # Exercises the three _composite_full_frame branches — single-tile direct,
    # serial multi-tile (workers<=1), threaded multi-tile — and pins them equal.
    w, h = 20, 20
    nodes = _representative_stack(h, w)

    # Single tile: edge larger than the canvas => direct single-shot path.
    monkeypatch.setattr(blend_mod, "FLATTEN_TILE_EDGE_PX", 64)
    single_tile = composite_stack(nodes, w, h, region=None).data.copy()

    _force_workers(monkeypatch, max_workers=1, cpus=FLATTEN_MAX_WORKERS, edge=8)
    serial_multi = composite_stack(nodes, w, h, region=None).data.copy()

    _force_workers(
        monkeypatch, max_workers=FLATTEN_MAX_WORKERS, cpus=FLATTEN_MAX_WORKERS, edge=8
    )
    threaded_multi = composite_stack(nodes, w, h, region=None).data.copy()

    assert np.array_equal(single_tile, serial_multi)
    assert np.array_equal(single_tile, threaded_multi)


# --------------------------------------------------------------------------- #
# 4. Fast-path coverage — opaque-over, transparent-skip, exact fall-back.      #
# --------------------------------------------------------------------------- #


def test_fast_path_opaque_layer_fully_replaces_backdrop(small_tiles):
    # ADR-0033 §1 opaque branch: a fully-opaque NORMAL/opacity-1/unmasked layer
    # occludes everything below, byte-for-byte (acc = src.copy()).
    h, w = 20, 24
    below = _layer_from_array(_rand_rgba(41, h, w, sparsity=0.3), name="below")
    opaque = _layer_from_array(_opaque_rgba(42, h, w), name="opaque")
    out = composite_stack([below, opaque], w, h, region=None)
    assert np.array_equal(out.data, opaque.buffer.data)
    # And byte-exact vs the exact (non-fast-path) reference.
    assert np.array_equal(out.data, _reference_flatten([below, opaque], w, h))


def test_fast_path_transparent_layer_is_a_noop(small_tiles):
    # ADR-0033 §1 clear branch: a fully-transparent NORMAL/opacity-1/unmasked
    # layer is skipped and is byte-identical to it being absent.
    h, w = 22, 26
    base = _layer_from_array(_opaque_rgba(51, h, w), name="base")
    over = _layer_from_array(_rand_rgba(52, h, w, sparsity=0.4), name="over")
    clear = _layer_from_array(np.zeros((h, w, 4), dtype=np.uint8), name="clear")
    with_clear = composite_stack([base, over, clear], w, h, region=None)
    without = composite_stack([base, over], w, h, region=None)
    assert np.array_equal(with_clear.data, without.data)


def test_fall_back_to_exact_for_non_normal_masked_low_opacity(small_tiles):
    # ADR-0033 §1: layers that are non-NORMAL / masked / opacity<1.0 bypass the
    # fast-path and use the exact float compositor; still byte-exact vs oracle.
    h, w = 20, 20
    base = _layer_from_array(_opaque_rgba(61, h, w), name="base")
    non_normal = _layer_from_array(
        _rand_rgba(62, h, w, sparsity=0.2),
        name="mul",
        blend_mode=BlendMode.MULTIPLY,
    )
    low_op = _layer_from_array(
        _rand_rgba(63, h, w, sparsity=0.2), name="faded", opacity=0.4
    )
    mask = _mask_from_array(_rand_rgba(64, h, w, sparsity=0.3))
    masked = _layer_from_array(_opaque_rgba(65, h, w), name="masked", mask=mask)
    _assert_full_frame_byte_exact([base, non_normal, low_op, masked], w, h)


def test_hidden_layer_excluded_from_full_frame(small_tiles):
    # LOGIC-006: a hidden layer contributes nothing to the full-frame flatten.
    h, w = 18, 18
    base = _layer_from_array(_opaque_rgba(71, h, w), name="base")
    hidden = _layer_from_array(_opaque_rgba(72, h, w), name="hidden", visible=False)
    out = composite_stack([base, hidden], w, h, region=None)
    assert np.array_equal(out.data, base.buffer.data)


# --------------------------------------------------------------------------- #
# 5. [Hypothesis] property — random small stacks are byte-exact + deterministic
# --------------------------------------------------------------------------- #

from hypothesis import given  # noqa: E402  (placed with its strategies)
from hypothesis import strategies as st  # noqa: E402


@st.composite
def _random_stacks(draw):
    """Draw a small, bounded multi-layer stack spec (dims/modes/alpha/masks)."""
    w = draw(st.integers(min_value=1, max_value=9))
    h = draw(st.integers(min_value=1, max_value=9))
    n = draw(st.integers(min_value=1, max_value=5))
    specs = []
    for _ in range(n):
        specs.append(
            {
                "mode": draw(st.sampled_from(ALL_MODES)),
                "opacity": draw(st.sampled_from([0.0, 0.25, 0.5, 0.75, 1.0])),
                "visible": draw(st.booleans()),
                "has_mask": draw(st.booleans()),
                "sparsity": draw(st.sampled_from([0.0, 0.3, 0.6, 1.0])),
                "seed": draw(st.integers(min_value=0, max_value=2**31 - 1)),
            }
        )
    return w, h, specs


def _build_stack(specs, h: int, w: int) -> list:
    nodes = []
    for i, spec in enumerate(specs):
        arr = _rand_rgba(spec["seed"], h, w, sparsity=spec["sparsity"])
        kw = {
            "name": f"L{i}",
            "blend_mode": spec["mode"],
            "opacity": spec["opacity"],
            "visible": spec["visible"],
        }
        if spec["has_mask"]:
            kw["mask"] = _mask_from_array(
                _rand_rgba(spec["seed"] + 1, h, w, sparsity=0.2)
            )
        nodes.append(_layer_from_array(arr, **kw))
    return nodes


@given(stack=_random_stacks(), edge=st.sampled_from([3, 5, 8, 1024]))
def test_property_full_frame_byte_exact_and_deterministic(stack, edge):
    # REQ-P12-LOGIC-002 / SC-P12-LOGIC-002-1/-2: for random bounded multi-layer
    # stacks (random modes/alpha/opacity/masks/visibility), the tiled+threaded
    # full-frame flatten is byte-identical to the exact reference AND stable
    # across repeated runs. Tile edge is varied to co-exercise seam correctness.
    w, h, specs = stack
    nodes = _build_stack(specs, h, w)

    original_edge = blend_mod.FLATTEN_TILE_EDGE_PX
    blend_mod.FLATTEN_TILE_EDGE_PX = edge
    try:
        out1 = composite_stack(nodes, w, h, region=None).data
        out2 = composite_stack(nodes, w, h, region=None).data
        reference = _reference_flatten(nodes, w, h)
    finally:
        blend_mod.FLATTEN_TILE_EDGE_PX = original_edge

    assert np.array_equal(out1, reference)  # byte-exact vs exact math
    assert np.array_equal(out1, out2)  # deterministic across runs


def test_composite_node_protocol_still_satisfied_by_layer_and_group():
    # Sanity: the structural CompositeNode protocol the compositor relies on is
    # satisfied by both leaf and group, so the reference and product read the
    # same duck-typed surface (opacity / visible / blend_mode / mask).
    layer = _layer_from_array(_opaque_rgba(81, 4, 4))
    group = LayerGroup("G", [layer])
    assert isinstance(layer, CompositeNode)
    assert isinstance(group, CompositeNode)
