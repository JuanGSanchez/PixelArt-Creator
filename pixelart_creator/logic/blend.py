"""Layer blend modes and the stack compositor (zero Qt, S11).

This module owns the Phase-4 compositing maths: the :class:`BlendMode`
vocabulary (12 members — the *single source* shared by the compositor, the
document model, the UI dropdown and ``.pixproj``), the per-mode separable blend
functions, and :func:`composite_stack`, which flattens an ordered layer/group
tree into a single RGBA :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`.

All blend maths follow *W3C Compositing and Blending Level 1*
(``docs/research-blend-modes.md``): work in **float32 normalised 0..1, straight
(non-premultiplied) alpha** (ADR-0005). ``uint8`` enters via ``/255`` and leaves
via ``clip(round(x*255), 0, 255)``. The formula magic numbers (``0.5``,
``0.25``, the ``16/12/4`` Horner cubic, the ``2*Cs`` factors) are *intrinsic* to
the W3C algorithm and stay module-local here (ADR-0001); only tuning scalars
live in :mod:`~pixelart_creator.logic.constants`.

This module **never imports** :mod:`~pixelart_creator.logic.document`: the
compositor consumes nodes through the structural :class:`CompositeNode`
Protocol, keeping the import graph one-way and acyclic
(``document -> blend -> color/constants/pixel_buffer``, PL-D2).
"""

from __future__ import annotations

import enum
from typing import Optional, Protocol, Sequence, Tuple, runtime_checkable

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic.color import RGBA, blend_over
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = [
    "BlendMode",
    "BlendError",
    "CompositeNode",
    "blend_channel",
    "blend_pixels",
    "blend_arrays",
    "composite_stack",
]

#: A dirty-rect region ``(x, y, width, height)`` in pixel coordinates.
Region = Tuple[int, int, int, int]

# Intrinsic W3C soft-light / hard-light thresholds and coefficients (ADR-0001):
# module-local, NOT tuning constants.
_HALF = 0.5
_QUARTER = 0.25
_SOFT_LIGHT_C0 = 16.0
_SOFT_LIGHT_C1 = 12.0
_SOFT_LIGHT_C2 = 4.0
_UINT8_MAX = 255.0


class BlendError(ValueError):
    """Raised when an unknown blend mode or malformed blend input is used."""


class BlendMode(enum.Enum):
    """The 12 supported layer blend modes (REQ-P4-LOGIC-001).

    12 members — ``NORMAL`` plus the eleven non-normal separable W3C modes
    (equivalently: the twelve W3C separable modes, of which ``NORMAL`` is one).
    This enum is the
    single source of the mode vocabulary shared by the compositor, the document
    model, the UI dropdown and the ``.pixproj`` serialiser. The value strings
    are the stable ``.pixproj`` tokens (ADR-0006).
    """

    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    COLOR_DODGE = "color_dodge"
    COLOR_BURN = "color_burn"
    HARD_LIGHT = "hard_light"
    SOFT_LIGHT = "soft_light"
    DIFFERENCE = "difference"
    EXCLUSION = "exclusion"


# --------------------------------------------------------------------------- #
# Structural node protocol (duck-typed; document.Layer / LayerGroup satisfy)   #
# --------------------------------------------------------------------------- #


@runtime_checkable
class CompositeNode(Protocol):
    """Structural view of a compositable node (PL-D2 — no ``document`` import).

    A **leaf** (``document.Layer``) exposes :meth:`effective_buffer` (smart
    layers resolve their source read-only); a **group** (``document.LayerGroup``)
    exposes ``children``. The compositor detects a group by the presence of a
    non-``None`` ``children`` attribute and a leaf by ``effective_buffer``.
    """

    opacity: float
    visible: bool
    blend_mode: BlendMode
    mask: Optional[PixelBuffer]


# --------------------------------------------------------------------------- #
# Per-channel separable blend functions B(Cb, Cs) on straight 0..1 arrays      #
# --------------------------------------------------------------------------- #


def _b_normal(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cs


def _b_multiply(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cb * cs


def _b_screen(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cb + cs - cb * cs


def _b_darken(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.minimum(cb, cs)


def _b_lighten(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.maximum(cb, cs)


def _b_hard_light(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # Cs <= 0.5 -> multiply(Cb, 2*Cs) ; else screen(Cb, 2*Cs - 1).
    low = cb * (2.0 * cs)
    high = cb + (2.0 * cs - 1.0) - cb * (2.0 * cs - 1.0)
    return np.where(cs <= _HALF, low, high)


def _b_overlay(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # overlay(Cb, Cs) == hard-light(Cs, Cb): hard-light with args swapped.
    return _b_hard_light(cs, cb)


def _b_color_dodge(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # Cb==0 -> 0 ; Cs==1 -> 1 ; else min(1, Cb/(1-Cs)).
    denom = 1.0 - cs
    safe = np.where(denom == 0.0, 1.0, denom)
    ratio = np.minimum(1.0, cb / safe)
    out = np.where(cs >= 1.0, 1.0, ratio)
    return np.where(cb == 0.0, 0.0, out)


def _b_color_burn(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # Cb==1 -> 1 ; Cs==0 -> 0 ; else 1 - min(1, (1-Cb)/Cs).
    safe = np.where(cs == 0.0, 1.0, cs)
    ratio = 1.0 - np.minimum(1.0, (1.0 - cb) / safe)
    out = np.where(cs <= 0.0, 0.0, ratio)
    return np.where(cb >= 1.0, 1.0, out)


def _b_soft_light(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    # W3C D(Cb) sqrt/cubic variant (NOT Pegtop) — the error-prone mode.
    d = np.where(
        cb <= _QUARTER,
        ((_SOFT_LIGHT_C0 * cb - _SOFT_LIGHT_C1) * cb + _SOFT_LIGHT_C2) * cb,
        np.sqrt(cb),
    )
    low = cb - (1.0 - 2.0 * cs) * cb * (1.0 - cb)
    high = cb + (2.0 * cs - 1.0) * (d - cb)
    return np.where(cs <= _HALF, low, high)


def _b_difference(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return np.abs(cb - cs)


def _b_exclusion(cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    return cb + cs - 2.0 * cb * cs


#: Dispatch table mapping each mode to its per-channel ``B(Cb, Cs)`` function.
_BLEND_FUNCS = {
    BlendMode.NORMAL: _b_normal,
    BlendMode.MULTIPLY: _b_multiply,
    BlendMode.SCREEN: _b_screen,
    BlendMode.OVERLAY: _b_overlay,
    BlendMode.DARKEN: _b_darken,
    BlendMode.LIGHTEN: _b_lighten,
    BlendMode.COLOR_DODGE: _b_color_dodge,
    BlendMode.COLOR_BURN: _b_color_burn,
    BlendMode.HARD_LIGHT: _b_hard_light,
    BlendMode.SOFT_LIGHT: _b_soft_light,
    BlendMode.DIFFERENCE: _b_difference,
    BlendMode.EXCLUSION: _b_exclusion,
}


def _blend_b(mode: BlendMode, cb: np.ndarray, cs: np.ndarray) -> np.ndarray:
    """Apply the separable blend function ``B(Cb, Cs)`` for ``mode``."""
    try:
        func = _BLEND_FUNCS[mode]
    except KeyError as exc:  # pragma: no cover - enum is exhaustive
        raise BlendError(f"unknown blend mode {mode!r}") from exc
    return func(cb, cs)


def blend_channel(mode: BlendMode, cb: float, cs: float) -> float:
    """Blend one straight, normalised ``0..1`` channel value.

    Computes ``B(Cb, Cs)`` for ``mode`` on scalar backdrop ``cb`` and source
    ``cs`` (both in ``0.0..1.0``); this is the pure blend step *before* the
    alpha compositing of :func:`blend_pixels` / :func:`blend_arrays`.
    Deterministic (P2).

    Raises:
        BlendError: If ``mode`` is not a :class:`BlendMode`.
    """
    if not isinstance(mode, BlendMode):
        raise BlendError(f"mode must be a BlendMode, got {mode!r}")
    cb_arr = np.asarray(cb, dtype=np.float32)
    cs_arr = np.asarray(cs, dtype=np.float32)
    return float(_blend_b(mode, cb_arr, cs_arr))


# --------------------------------------------------------------------------- #
# Alpha-aware compositing (W3C §5.1 general formula) on (H, W, 4) arrays        #
# --------------------------------------------------------------------------- #


def _composite_float(
    mode: BlendMode,
    src: np.ndarray,
    dst: np.ndarray,
    src_alpha: np.ndarray,
) -> np.ndarray:
    """Composite straight-alpha float ``src`` over ``dst`` per the W3C step.

    ``src`` / ``dst`` are ``(H, W, 4)`` float arrays in ``0..1``; ``src_alpha``
    is the *effective* source alpha ``(H, W, 1)`` (already scaled by opacity and
    mask). Returns an ``(H, W, 4)`` straight-alpha float array.
    """
    cs = src[:, :, :3]
    cb = dst[:, :, :3]
    a_s = src_alpha
    a_b = dst[:, :, 3:4]

    blended = _blend_b(mode, cb, cs)
    # Cs' = (1 - ab) * Cs + ab * B(Cb, Cs)
    cs_prime = (1.0 - a_b) * cs + a_b * blended
    # ao = as + ab * (1 - as)
    a_o = a_s + a_b * (1.0 - a_s)
    # ao * Co = as * Cs' + (1 - as) * ab * Cb ; Co = 0 where ao == 0
    premult = a_s * cs_prime + (1.0 - a_s) * a_b * cb
    safe_a = np.where(a_o > 0.0, a_o, 1.0)
    co = np.where(a_o > 0.0, premult / safe_a, 0.0)

    out = np.empty_like(dst)
    out[:, :, :3] = np.clip(co, 0.0, 1.0)
    out[:, :, 3:4] = np.clip(a_o, 0.0, 1.0)
    return out


def _normalise_mask(mask: np.ndarray, height: int, width: int) -> np.ndarray:
    """Return a ``(H, W, 1)`` float ``0..1`` modulation array from ``mask``."""
    arr = np.asarray(mask)
    if arr.ndim == 3:
        # RGBA mask -> use the alpha channel; single-channel (H,W,1) -> squeeze.
        arr = arr[:, :, 3] if arr.shape[2] == 4 else arr[:, :, 0]
    if arr.shape != (height, width):
        raise BlendError(
            f"mask shape {arr.shape} does not match region {(height, width)}"
        )
    out = arr.astype(np.float32)
    if np.issubdtype(np.asarray(mask).dtype, np.integer):
        out = out / _UINT8_MAX
    return np.clip(out, 0.0, 1.0)[:, :, np.newaxis]


def _blend_over_arrays(
    src: npt.NDArray[np.uint8],
    dst: npt.NDArray[np.uint8],
    *,
    opacity: float,
    mask: Optional[npt.NDArray],
) -> npt.NDArray[np.uint8]:
    """Vectorised straight-alpha ``source-over`` — the ``NORMAL`` mode path.

    This mirrors :func:`~pixelart_creator.logic.color.blend_over`
    **bit-for-bit** for the base case (``opacity == 1.0`` **and** ``mask is
    None``): it works in ``float64`` over the ``0..255`` colour range,
    replicates ``blend_over``'s exact per-channel expression together with its
    ``round``-half-to-even-then-clip, and reproduces the two early-return
    branches (``sa == 255`` → ``src`` unchanged, ``sa == 0`` → ``dst``
    unchanged) via :func:`numpy.where`. This restores the frozen contract
    REQ-P4-LOGIC-003 / ADR-0005 — ``blend_arrays(NORMAL)`` equals ``blend_over``
    applied elementwise (and therefore equals ``blend_pixels(NORMAL)``) with
    **zero tolerance**. The float32 generic separable path (kept for the eleven
    non-normal modes, T13 D5) diverged by ≤ 1 LSB at rounding boundaries, which
    this dedicated float64 path removes for the DEFAULT mode.

    For ``opacity < 1.0`` and/or a ``mask``, the source's effective alpha is
    scaled — ``a_s = (src_alpha / 255) * opacity * mask`` — and the same
    source-over composite is applied, matching the single-pixel
    ``blend_pixels(NORMAL)`` "effective src-alpha scaling then source-over"
    semantics. Never mutates its inputs.
    """
    height, width = src.shape[0], src.shape[1]
    sc = src[:, :, :3].astype(np.float64)
    dc = dst[:, :, :3].astype(np.float64)
    src_alpha = src[:, :, 3:4]
    dst_alpha = dst[:, :, 3:4]

    # Effective source alpha in 0..1 (base case: (src_alpha / 255) * 1.0, which
    # is exact and equals blend_over's ``sa_f``).
    a_s = (src_alpha.astype(np.float64) / _UINT8_MAX) * float(opacity)
    if mask is not None:
        a_s = a_s * _normalise_mask(mask, height, width).astype(np.float64)

    # Replicate blend_over's else-branch float64 arithmetic exactly (0..255
    # colour range, same operation order), so rounding boundaries agree.
    da_f = dst_alpha.astype(np.float64) / _UINT8_MAX
    one_minus_as = 1.0 - a_s
    out_a = a_s + da_f * one_minus_as
    safe_a = np.where(out_a > 0.0, out_a, 1.0)
    value = (sc * a_s + dc * da_f * one_minus_as) / safe_a

    comp_rgb = np.clip(np.round(value), 0.0, _UINT8_MAX)
    comp_alpha = np.clip(np.round(out_a * _UINT8_MAX), 0.0, _UINT8_MAX)

    # blend_over early returns: sa == 255 -> src unchanged; sa == 0 -> dst
    # unchanged. In the base case a_s == 1.0 iff sa == 255 and a_s == 0.0 iff
    # sa == 0, so these branches are bit-exact; under opacity/mask they degrade
    # gracefully to "fully opaque -> src" / "zero effective alpha -> dst".
    opaque = a_s >= 1.0
    clear = a_s <= 0.0

    out_rgb = np.where(opaque, sc, np.where(clear, dc, comp_rgb))
    out_alpha = np.where(
        opaque,
        src_alpha.astype(np.float64),
        np.where(clear, dst_alpha.astype(np.float64), comp_alpha),
    )

    out = np.empty_like(src)
    out[:, :, :3] = out_rgb.astype(np.uint8)
    out[:, :, 3:4] = out_alpha.astype(np.uint8)
    return out


def blend_arrays(
    mode: BlendMode,
    src: npt.NDArray[np.uint8],
    dst: npt.NDArray[np.uint8],
    *,
    opacity: float = 1.0,
    mask: Optional[npt.NDArray] = None,
) -> npt.NDArray[np.uint8]:
    """Vectorised ``(H, W, 4)`` uint8 blend of ``src`` over ``dst`` (F7).

    ``NORMAL`` composites through :func:`_blend_over_arrays`, a dedicated
    **float64** path that is bit-exact with
    :func:`~pixelart_creator.logic.color.blend_over` (and thus with
    :func:`blend_pixels` ``NORMAL``) for the base case (REQ-P4-LOGIC-003,
    ADR-0005). The eleven non-normal separable modes work in **float32**
    straight alpha (ADR-0005; T13 D5 — the perf directive stands; those modes
    are ``uint8``-invisible at float32). ``opacity`` (``0..1``) scales the
    source's effective alpha (LOGIC-005); ``mask`` — an ``(H, W)`` /
    ``(H, W, 1)`` single-channel or ``(H, W, 4)`` RGBA (alpha used) array —
    further modulates it per pixel (LOGIC-012). Never mutates its inputs.

    Raises:
        BlendError: On a non-:class:`BlendMode` mode, mismatched shapes, or a
            mask whose geometry does not match ``src``.
    """
    if not isinstance(mode, BlendMode):
        raise BlendError(f"mode must be a BlendMode, got {mode!r}")
    if src.shape != dst.shape or src.ndim != 3 or src.shape[2] != 4:
        raise BlendError(
            f"blend_arrays needs matching (H, W, 4) arrays, got {src.shape} / "
            f"{dst.shape}"
        )
    if not 0.0 <= float(opacity) <= 1.0:
        raise BlendError(f"opacity {opacity} out of range 0.0..1.0")

    if mode is BlendMode.NORMAL:
        return _blend_over_arrays(src, dst, opacity=opacity, mask=mask)

    height, width = src.shape[0], src.shape[1]
    src_f = src.astype(np.float32) / _UINT8_MAX
    dst_f = dst.astype(np.float32) / _UINT8_MAX

    eff_alpha = src_f[:, :, 3:4] * float(opacity)
    if mask is not None:
        eff_alpha = eff_alpha * _normalise_mask(mask, height, width)

    out = _composite_float(mode, src_f, dst_f, eff_alpha)
    return np.clip(np.round(out * _UINT8_MAX), 0, 255).astype(np.uint8)


def blend_pixels(mode: BlendMode, src: RGBA, dst: RGBA) -> RGBA:
    """Composite a single ``src`` RGBA over ``dst`` under ``mode``.

    ``NORMAL`` delegates to
    :func:`~pixelart_creator.logic.color.blend_over` **exactly** (LOGIC-003);
    every other mode applies the W3C blend + compositing step. Deterministic
    (P2).

    Raises:
        BlendError: If ``mode`` is not a :class:`BlendMode`.
    """
    if not isinstance(mode, BlendMode):
        raise BlendError(f"mode must be a BlendMode, got {mode!r}")
    if mode is BlendMode.NORMAL:
        return blend_over(src, dst)
    src_arr = np.array([[src]], dtype=np.uint8)
    dst_arr = np.array([[dst]], dtype=np.uint8)
    out = blend_arrays(mode, src_arr, dst_arr)
    r, g, b, a = (int(v) for v in out[0, 0])
    return (r, g, b, a)


# --------------------------------------------------------------------------- #
# Stack compositor                                                            #
# --------------------------------------------------------------------------- #


def _validate_region(region: Region, width: int, height: int) -> Region:
    """Validate a scene-space ``(x, y, w, h)`` region against the canvas.

    The region MUST lie fully within ``(0, 0, width, height)`` with ``w >= 1``
    and ``h >= 1``. The compositor **validates, it never silently clamps** (P2
    determinism, ADR-0007 §Amendment (T13) D1) — the caller clamps its dirty
    rect to the canvas before calling.

    Raises:
        BlendError: If ``region`` is malformed, degenerate, or out of bounds.
    """
    try:
        x, y, w, h = (int(v) for v in region)
    except (TypeError, ValueError) as exc:
        raise BlendError(
            f"region must be an (x, y, w, h) tuple, got {region!r}"
        ) from exc
    if w < 1 or h < 1:
        raise BlendError(f"region size must be >= 1x1, got {w}x{h}")
    if x < 0 or y < 0 or x + w > width or y + h > height:
        raise BlendError(
            f"region {(x, y, w, h)} is out of bounds for canvas {width}x{height}"
        )
    return (x, y, w, h)


def _node_source_region(
    node: CompositeNode, x: int, y: int, w: int, h: int, width: int, height: int
) -> npt.NDArray[np.uint8]:
    """Return the ``(h, w, 4)`` uint8 source contribution of a leaf ``node``."""
    buffer = node.effective_buffer()  # type: ignore[attr-defined]
    if buffer.mode is not ColorMode.RGBA:
        raise BlendError("composite_stack requires RGBA layer buffers")
    if buffer.width != width or buffer.height != height:
        raise BlendError(
            f"layer buffer {buffer.width}x{buffer.height} does not match canvas "
            f"{width}x{height}"
        )
    return np.ascontiguousarray(buffer.data[y : y + h, x : x + w])


def _flatten_group(
    node: CompositeNode,
    children: Sequence[CompositeNode],
    width: int,
    height: int,
    x: int,
    y: int,
    w: int,
    h: int,
) -> npt.NDArray[np.uint8]:
    """Return a group's flattened children over region ``(x, y, w, h)`` (D4).

    The flattened intermediate (the children composited *before* the group's
    own opacity/blend-mode/mask are applied by the parent) is **cached** on the
    node and reused while the subtree is unchanged (ADR-0007 §Amendment (T13)
    D4). The cache is a single-entry MRU keyed by the region tuple; document.py
    invalidates it (sets ``node._composite_cache = None``) up the whole ancestor
    chain on any child/attribute/order/mask change, so a stale cache can never
    render a wrong composite (SC-UI-012-2).

    The cached array is only ever read as a ``src`` (``blend_arrays`` copies via
    ``astype`` and never mutates its inputs), so returning it is safe. Nodes
    without the ``_composite_cache`` slot (e.g. a non-group duck) simply skip
    caching — keeping ``blend.py`` free of any ``document`` import (PL-D2).
    """
    key = (x, y, w, h)
    cache = getattr(node, "_composite_cache", None)
    if cache is not None and cache[0] == key:
        return cache[1]
    flattened = _composite_region(children, width, height, x, y, w, h)
    if hasattr(node, "_composite_cache"):
        setattr(node, "_composite_cache", (key, flattened))
    return flattened


def _composite_region(
    nodes: Sequence[CompositeNode],
    width: int,
    height: int,
    x: int,
    y: int,
    w: int,
    h: int,
) -> npt.NDArray[np.uint8]:
    """Composite ``nodes`` bottom-to-top over a transparent ``(h, w, 4)`` rect.

    Each leaf/group is sampled at **scene coordinates** — region element
    ``(row i, col j)`` maps to scene pixel ``(x + j, y + i)`` (nodes read
    ``buffer.data[y:y+h, x:x+w]``), so the returned rect can be blitted into the
    resident scene buffer at origin ``(x, y)`` (D1). Group subtrees reuse their
    cached flattened intermediate via :func:`_flatten_group` (D4).
    """
    acc = np.zeros((h, w, 4), dtype=np.uint8)
    for node in nodes:
        if not node.visible:
            continue  # hidden node / group subtree contributes nothing (LOGIC-006/011)
        children = getattr(node, "children", None)
        if children is not None:
            src = _flatten_group(node, children, width, height, x, y, w, h)
        else:
            src = _node_source_region(node, x, y, w, h, width, height)
        mask_arr = None
        if node.mask is not None:
            mask_arr = node.mask.data[y : y + h, x : x + w]
        acc = blend_arrays(
            node.blend_mode, src, acc, opacity=node.opacity, mask=mask_arr
        )
    return acc


def composite_stack(
    nodes: Sequence[CompositeNode],
    width: int,
    height: int,
    *,
    region: Optional[Region] = None,
) -> PixelBuffer:
    """Flatten an ordered node list into one flat RGBA :class:`PixelBuffer`.

    ``nodes`` are composited **bottom-to-top** (CL-4) honouring each node's
    visibility (LOGIC-006), opacity (LOGIC-005), blend mode (LOGIC-007) and mask
    (LOGIC-012); a group is flattened first then blended as one (LOGIC-011).
    Source buffers are never mutated (LOGIC-004).

    Return shape (ADR-0007 §Amendment (T13) D1 — the mandatory full-canvas
    allocation was the ~140 ms 8K region-path floor):

    - ``region=None`` → a **full-canvas** ``PixelBuffer(width, height)`` (numpy
      shape ``(height, width, 4)``), implied scene origin ``(0, 0)``.
    - ``region=(x, y, w, h)`` → a **region-sized** ``PixelBuffer(w, h)`` (numpy
      shape ``(h, w, 4)``), implied scene origin ``(x, y)``. Only ``(h, w, 4)``
      is allocated — **never** a full ``width``×``height`` buffer. Element
      ``(row i, col j)`` maps to scene pixel ``(x + j, y + i)``; the caller
      blits it into the resident scene buffer at ``(x, y)``.

    ``region`` is in scene/canvas space and MUST lie fully within
    ``(0, 0, width, height)`` with ``w >= 1, h >= 1``; an out-of-bounds or
    degenerate region raises :class:`BlendError` (the compositor validates, it
    does not clamp).

    Raises:
        BlendError: If a layer buffer is indexed / a wrong geometry, or
            ``region`` is malformed, degenerate, or out of bounds.
    """
    if region is None:
        result = PixelBuffer(width, height, ColorMode.RGBA)
        result.data[:, :] = _composite_region(nodes, width, height, 0, 0, width, height)
        return result
    x, y, w, h = _validate_region(region, width, height)
    result = PixelBuffer(w, h, ColorMode.RGBA)
    result.data[:, :] = _composite_region(nodes, width, height, x, y, w, h)
    return result
