# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Seeded, deterministic procedural generators (zero Qt, S11).

Five in-house generators — **value noise**, **gradient (Perlin-style) noise**, an
**OpenSimplex-style** simplex-grid gradient noise (patent-safe reformulation,
Researcher §4.1), **cellular automata**, and **dithered gradients** (reusing the
shipped :mod:`logic.dither` ordered-Bayer / Floyd–Steinberg) — each a **pure,
deterministic function of ``(params, seed)``** (same seed + params → identical
output; REQ-P8-LOGIC-012). All are pure NumPy/Python: **no new third-party
dependency** is introduced (consistent with the project's no-new-dep ADRs — nothing
to flag to AGT-01).

Generated content is written into the document **through the reversible-command
path** (HIS-1): :func:`make_procgen_command` returns an efficient
:class:`~pixelart_creator.logic.history.FunctionCommand` that snapshots the target
region and swaps it via a single vectorised NumPy slice assignment on
``execute``/``undo`` (``apply ∘ undo = identity``) — O(1) in Python-level calls, so
even an 8K region is cheap (batch work, not the 16 ms frame loop). Output is bounded
per-axis by :data:`~pixelart_creator.logic.constants.MAX_PROCGEN_DIMENSION`; the
default seed is :data:`~pixelart_creator.logic.constants.DEFAULT_PROCGEN_SEED`.

There is **no ``eval``/``exec``/``compile`` anywhere**; randomness is drawn only
from ``numpy.random.default_rng(seed)`` (deterministic given the seed), never the
wall clock or a global RNG.
"""

from __future__ import annotations

from typing import Callable, Mapping, Tuple

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic.color import RGBA, is_rgba
from pixelart_creator.logic.constants import (
    DEFAULT_PROCGEN_SEED,
    MAX_PROCGEN_DIMENSION,
)
from pixelart_creator.logic.dither import floyd_steinberg, ordered_dither
from pixelart_creator.logic.document import Document, iter_layers
from pixelart_creator.logic.history import Command, FunctionCommand
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

__all__ = [
    "ProcgenError",
    "ALGORITHMS",
    "ALGO_VALUE_NOISE",
    "ALGO_GRADIENT_NOISE",
    "ALGO_OPENSIMPLEX",
    "ALGO_CELLULAR",
    "ALGO_DITHERED_GRADIENT",
    "make_procgen_command",
]

ALGO_VALUE_NOISE = "value_noise"
ALGO_GRADIENT_NOISE = "gradient_noise"
ALGO_OPENSIMPLEX = "opensimplex"
ALGO_CELLULAR = "cellular_automata"
ALGO_DITHERED_GRADIENT = "dithered_gradient"

#: The module-local procgen algorithm vocabulary (enumerated, ADR-0001 / BF-2).
ALGORITHMS: Tuple[str, ...] = (
    ALGO_VALUE_NOISE,
    ALGO_GRADIENT_NOISE,
    ALGO_OPENSIMPLEX,
    ALGO_CELLULAR,
    ALGO_DITHERED_GRADIENT,
)

_BLACK: RGBA = (0, 0, 0, 255)
_WHITE: RGBA = (255, 255, 255, 255)

# Simplex-grid skew/unskew factors (algorithm-intrinsic, ADR-0001).
_F2 = 0.5 * (np.sqrt(3.0) - 1.0)
_G2 = (3.0 - np.sqrt(3.0)) / 6.0

# 8 unit-ish gradient directions for the simplex generator (algorithm-intrinsic).
_GRAD2 = np.array(
    [
        (1.0, 0.0),
        (-1.0, 0.0),
        (0.0, 1.0),
        (0.0, -1.0),
        (1.0, 1.0),
        (-1.0, 1.0),
        (1.0, -1.0),
        (-1.0, -1.0),
    ],
    dtype=np.float64,
)


class ProcgenError(ValueError):
    """Raised on an unknown algorithm, invalid params, or an out-of-bounds size."""


# --------------------------------------------------------------------------- #
# Parameter helpers (defensive; JSON-native inputs)                           #
# --------------------------------------------------------------------------- #


def _int_param(params: Mapping[str, object], key: str, default: int) -> int:
    value = params.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProcgenError(f"procgen param {key!r} must be an int, got {value!r}")
    return value


def _float_param(params: Mapping[str, object], key: str, default: float) -> float:
    value = params.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProcgenError(f"procgen param {key!r} must be a number, got {value!r}")
    return float(value)


def _color_param(params: Mapping[str, object], key: str, default: RGBA) -> RGBA:
    value = params.get(key)
    if value is None:
        return default
    if isinstance(value, (list, tuple)) and len(value) == 4:
        candidate: RGBA = (
            int(value[0]),
            int(value[1]),
            int(value[2]),
            int(value[3]),
        )
        if is_rgba(candidate):
            return candidate
    raise ProcgenError(
        f"procgen param {key!r} must be an RGBA [r,g,b,a], got {value!r}"
    )


def _positive_int(params: Mapping[str, object], key: str, default: int) -> int:
    value = _int_param(params, key, default)
    if value < 1:
        raise ProcgenError(f"procgen param {key!r} must be >= 1, got {value}")
    return value


def _resolve_target(document: Document, params: Mapping[str, object]) -> PixelBuffer:
    """Return the target layer buffer, addressed by stable ``layer_id`` (P2).

    Falls back to the first leaf layer of ``frame_index`` (default 0) when no
    ``layer_id`` is given — deterministic for a given document.
    """
    frame_index = _int_param(params, "frame_index", 0)
    if not 0 <= frame_index < len(document.frames):
        raise ProcgenError(f"procgen frame_index {frame_index} out of range")
    leaves = iter_layers(document.frames[frame_index].layers)
    if not leaves:
        raise ProcgenError("target frame has no layers")
    layer_id = params.get("layer_id")
    if layer_id is None:
        return leaves[0].buffer
    if not isinstance(layer_id, int) or isinstance(layer_id, bool):
        raise ProcgenError(f"procgen layer_id must be an int, got {layer_id!r}")
    for layer in leaves:
        if layer.layer_id == layer_id:
            return layer.buffer
    raise ProcgenError(f"no layer with layer_id {layer_id} in frame {frame_index}")


def _resolve_region(
    buffer: PixelBuffer, params: Mapping[str, object]
) -> Tuple[int, int, int, int]:
    """Return a validated ``(x, y, w, h)`` region within ``buffer`` (per-axis bound)."""
    x = _int_param(params, "x", 0)
    y = _int_param(params, "y", 0)
    w = _int_param(params, "width", buffer.width)
    h = _int_param(params, "height", buffer.height)
    if w < 1 or h < 1:
        raise ProcgenError(f"procgen size must be positive, got {w}x{h}")
    if w > MAX_PROCGEN_DIMENSION or h > MAX_PROCGEN_DIMENSION:
        raise ProcgenError(
            f"procgen size {w}x{h} exceeds MAX_PROCGEN_DIMENSION "
            f"({MAX_PROCGEN_DIMENSION})"
        )
    if x < 0 or y < 0 or x + w > buffer.width or y + h > buffer.height:
        raise ProcgenError(
            f"procgen region ({x},{y},{w},{h}) exceeds buffer "
            f"{buffer.width}x{buffer.height}"
        )
    return x, y, w, h


# --------------------------------------------------------------------------- #
# Scalar-field generators — each returns a float array in [0, 1], shape (h, w) #
# --------------------------------------------------------------------------- #

#: A float scalar field, shape ``(h, w)``.
_FloatField = npt.NDArray[np.float64]
#: An integer index array, shape ``(h, w)``.
_IntField = npt.NDArray[np.intp]
#: One octave function: ``(w, h, frequency, rng) -> field``.
_OctaveFn = Callable[[int, int, int, "np.random.Generator"], _FloatField]


def _fade(t: _FloatField) -> _FloatField:
    """Perlin quintic smoothstep ``6t^5 - 15t^4 + 10t^3`` (algorithm-intrinsic)."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _lattice_coords(w: int, h: int, frequency: int) -> Tuple[
    npt.NDArray[np.intp],
    npt.NDArray[np.intp],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
]:
    """Return integer cell indices + fractional offsets for a ``frequency`` grid."""
    xs = np.linspace(0.0, float(frequency), w, endpoint=False)
    ys = np.linspace(0.0, float(frequency), h, endpoint=False)
    gx, gy = np.meshgrid(xs, ys)
    x0 = np.floor(gx).astype(np.intp)
    y0 = np.floor(gy).astype(np.intp)
    return x0, y0, gx - x0, gy - y0


def _value_noise_octave(
    w: int, h: int, frequency: int, rng: np.random.Generator
) -> npt.NDArray[np.float64]:
    grid = rng.random((frequency + 1, frequency + 1))
    x0, y0, fx, fy = _lattice_coords(w, h, frequency)
    x1, y1 = x0 + 1, y0 + 1
    v00 = grid[y0, x0]
    v10 = grid[y0, x1]
    v01 = grid[y1, x0]
    v11 = grid[y1, x1]
    u, v = _fade(fx), _fade(fy)
    top = v00 * (1.0 - u) + v10 * u
    bottom = v01 * (1.0 - u) + v11 * u
    return top * (1.0 - v) + bottom * v


def _gradient_noise_octave(
    w: int, h: int, frequency: int, rng: np.random.Generator
) -> npt.NDArray[np.float64]:
    angles = rng.random((frequency + 1, frequency + 1)) * (2.0 * np.pi)
    gxg, gyg = np.cos(angles), np.sin(angles)
    x0, y0, fx, fy = _lattice_coords(w, h, frequency)
    x1, y1 = x0 + 1, y0 + 1

    def _dot(
        ix: _IntField, iy: _IntField, dx: _FloatField, dy: _FloatField
    ) -> _FloatField:
        return gxg[iy, ix] * dx + gyg[iy, ix] * dy

    n00 = _dot(x0, y0, fx, fy)
    n10 = _dot(x1, y0, fx - 1.0, fy)
    n01 = _dot(x0, y1, fx, fy - 1.0)
    n11 = _dot(x1, y1, fx - 1.0, fy - 1.0)
    u, v = _fade(fx), _fade(fy)
    top = n00 * (1.0 - u) + n10 * u
    bottom = n01 * (1.0 - u) + n11 * u
    # Gradient noise lands in ~[-0.7, 0.7]; normalise to [0, 1].
    return (top * (1.0 - v) + bottom * v) * 0.7071 + 0.5


def _fbm(
    w: int,
    h: int,
    params: Mapping[str, object],
    rng: np.random.Generator,
    octave_fn: _OctaveFn,
) -> _FloatField:
    """Fractal Brownian sum of ``octaves`` of a base octave function."""
    base_freq = _positive_int(params, "frequency", 4)
    octaves = _positive_int(params, "octaves", 1)
    if octaves > 12:
        raise ProcgenError(f"procgen octaves {octaves} exceeds 12")
    total = np.zeros((h, w), dtype=np.float64)
    amplitude = 1.0
    amplitude_sum = 0.0
    frequency = base_freq
    for _ in range(octaves):
        total += octave_fn(w, h, frequency, rng) * amplitude
        amplitude_sum += amplitude
        amplitude *= 0.5
        frequency *= 2
    field = total / amplitude_sum if amplitude_sum else total
    return np.clip(field, 0.0, 1.0)


def _value_noise_field(
    w: int, h: int, params: Mapping[str, object], rng: np.random.Generator
) -> _FloatField:
    return _fbm(w, h, params, rng, _value_noise_octave)


def _gradient_noise_field(
    w: int, h: int, params: Mapping[str, object], rng: np.random.Generator
) -> _FloatField:
    return _fbm(w, h, params, rng, _gradient_noise_octave)


def _opensimplex_field(
    w: int, h: int, params: Mapping[str, object], rng: np.random.Generator
) -> _FloatField:
    """Compute a patent-safe simplex-grid gradient noise, vectorised over pixels."""
    frequency = _positive_int(params, "frequency", 4)
    perm = rng.permutation(256).astype(np.intp)
    perm = np.concatenate([perm, perm])

    xs = np.linspace(0.0, float(frequency), w, endpoint=False)
    ys = np.linspace(0.0, float(frequency), h, endpoint=False)
    xin, yin = np.meshgrid(xs, ys)

    s = (xin + yin) * _F2
    i = np.floor(xin + s).astype(np.intp)
    j = np.floor(yin + s).astype(np.intp)
    t = (i + j) * _G2
    x0 = xin - (i - t)
    y0 = yin - (j - t)

    upper = x0 > y0
    i1 = np.where(upper, 1, 0).astype(np.intp)
    j1 = np.where(upper, 0, 1).astype(np.intp)

    x1 = x0 - i1 + _G2
    y1 = y0 - j1 + _G2
    x2 = x0 - 1.0 + 2.0 * _G2
    y2 = y0 - 1.0 + 2.0 * _G2

    ii = (i & 255).astype(np.intp)
    jj = (j & 255).astype(np.intp)

    def _corner(dx: _FloatField, dy: _FloatField, gi: _IntField) -> _FloatField:
        tt = 0.5 - dx * dx - dy * dy
        grad = _GRAD2[gi % 8]
        contrib = (tt**4) * (grad[..., 0] * dx + grad[..., 1] * dy)
        return np.where(tt > 0.0, contrib, 0.0)

    gi0 = perm[ii + perm[jj]]
    gi1 = perm[ii + i1 + perm[jj + j1]]
    gi2 = perm[ii + 1 + perm[jj + 1]]

    total = _corner(x0, y0, gi0) + _corner(x1, y1, gi1) + _corner(x2, y2, gi2)
    # 2D simplex output is ~[-1, 1] after the standard ~70 scale; normalise.
    return np.clip(70.0 * total * 0.5 + 0.5, 0.0, 1.0)


def _cellular_field(
    w: int, h: int, params: Mapping[str, object], rng: np.random.Generator
) -> _FloatField:
    """Cave-style cellular automaton; returns a 0/1 field, shape (h, w)."""
    density = _float_param(params, "density", 0.45)
    if not 0.0 <= density <= 1.0:
        raise ProcgenError(f"procgen density {density} out of range 0.0..1.0")
    iterations = _int_param(params, "iterations", 4)
    if not 0 <= iterations <= 64:
        raise ProcgenError(f"procgen iterations {iterations} out of range 0..64")
    alive = (rng.random((h, w)) < density).astype(np.int64)
    for _ in range(iterations):
        padded = np.pad(alive, 1, mode="edge")
        neighbours = (
            padded[:-2, :-2]
            + padded[:-2, 1:-1]
            + padded[:-2, 2:]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
            + padded[2:, :-2]
            + padded[2:, 1:-1]
            + padded[2:, 2:]
        )
        # Classic cave rule: survive with >=4 neighbours, born with >=5.
        alive = ((alive == 1) & (neighbours >= 4)) | ((alive == 0) & (neighbours >= 5))
        alive = alive.astype(np.int64)
    return alive.astype(np.float64)


_FIELD_FN = {
    ALGO_VALUE_NOISE: _value_noise_field,
    ALGO_GRADIENT_NOISE: _gradient_noise_field,
    ALGO_OPENSIMPLEX: _opensimplex_field,
    ALGO_CELLULAR: _cellular_field,
}


def _field_to_rgba(
    field: npt.NDArray[np.float64], low: RGBA, high: RGBA
) -> npt.NDArray[np.uint8]:
    """Map a [0, 1] scalar field to RGBA by per-channel lerp ``low → high``."""
    low_a = np.asarray(low, dtype=np.float64)
    high_a = np.asarray(high, dtype=np.float64)
    ramp = (
        low_a[np.newaxis, np.newaxis, :]
        + field[..., np.newaxis] * (high_a - low_a)[np.newaxis, np.newaxis, :]
    )
    return np.clip(np.round(ramp), 0, 255).astype(np.uint8)


def _dithered_gradient_rgba(
    document: Document,
    w: int,
    h: int,
    params: Mapping[str, object],
) -> npt.NDArray[np.uint8]:
    """Render a smooth two-colour gradient dithered onto the palette (⊆ palette)."""
    if len(document.palette) == 0:
        raise ProcgenError("dithered_gradient needs a non-empty document palette")
    low = _color_param(params, "color_low", _BLACK)
    high = _color_param(params, "color_high", _WHITE)
    direction = params.get("direction", "horizontal")
    if direction not in ("horizontal", "vertical"):
        raise ProcgenError(
            f"procgen direction must be 'horizontal'/'vertical', got {direction!r}"
        )
    mode = params.get("dither", "ordered")
    if mode not in ("ordered", "floyd_steinberg"):
        raise ProcgenError(
            f"procgen dither must be 'ordered'/'floyd_steinberg', got {mode!r}"
        )
    if direction == "horizontal":
        t = np.tile(np.linspace(0.0, 1.0, w), (h, 1))
    else:
        t = np.tile(np.linspace(0.0, 1.0, h)[:, np.newaxis], (1, w))
    source = PixelBuffer(w, h, ColorMode.RGBA)
    source.data[:, :] = _field_to_rgba(t, low, high)
    if mode == "ordered":
        dithered = ordered_dither(source, document.palette)
    else:
        dithered = floyd_steinberg(source, document.palette)
    return dithered.data


def make_procgen_command(
    document: Document,
    *,
    algorithm: str,
    params: Mapping[str, object],
    seed: int = DEFAULT_PROCGEN_SEED,
) -> Command:
    """Build a reversible command writing generated content into ``document``.

    Deterministic in ``(params, seed)`` (REQ-P8-LOGIC-012). Resolves the target
    layer by stable ``layer_id`` (or the frame's first leaf) and an optional
    ``(x, y, width, height)`` region (default the whole buffer, per-axis bounded by
    :data:`~pixelart_creator.logic.constants.MAX_PROCGEN_DIMENSION`), generates the
    region, and returns a :class:`~pixelart_creator.logic.history.FunctionCommand`
    that swaps the region in/out with a single vectorised NumPy assignment
    (``apply ∘ undo = identity``). Returned **unapplied** (the dispatcher /
    ``ui.commands`` applies it).

    Args:
        document: The subject document.
        algorithm: One of :data:`ALGORITHMS`.
        params: JSON-native generation parameters (target/region + algorithm knobs).
        seed: The RNG seed (mandatory for determinism; default
            :data:`~pixelart_creator.logic.constants.DEFAULT_PROCGEN_SEED`).

    Raises:
        ProcgenError: On an unknown algorithm, non-RGBA target, invalid params, or
            a size exceeding the per-axis bound.
    """
    if algorithm not in ALGORITHMS:
        raise ProcgenError(
            f"unknown procgen algorithm {algorithm!r}; expected one of {ALGORITHMS}"
        )
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ProcgenError(f"procgen seed must be an int, got {seed!r}")

    buffer = _resolve_target(document, params)
    if buffer.mode is not ColorMode.RGBA:
        raise ProcgenError("procgen writes RGBA content; target buffer is not RGBA")
    x, y, w, h = _resolve_region(buffer, params)

    rng = np.random.default_rng(seed)
    if algorithm == ALGO_DITHERED_GRADIENT:
        new_region = _dithered_gradient_rgba(document, w, h, params)
    else:
        low = _color_param(params, "color_low", _BLACK)
        high = _color_param(params, "color_high", _WHITE)
        field = _FIELD_FN[algorithm](w, h, params, rng)
        new_region = _field_to_rgba(field, low, high)

    old_region = buffer.data[y : y + h, x : x + w].copy()
    new_region = np.ascontiguousarray(new_region, dtype=np.uint8)

    def _do() -> None:
        buffer.data[y : y + h, x : x + w] = new_region

    def _undo() -> None:
        buffer.data[y : y + h, x : x + w] = old_region

    return FunctionCommand(_do, _undo, label=f"procgen ({algorithm})")
