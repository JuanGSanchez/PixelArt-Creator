"""Palette constraint + auto-extraction (median-cut / k-means) (zero Qt, S11).

Three capabilities over the Phase-1 buffer/palette model:

* :func:`constrain_to_palette` maps an arbitrary-colour buffer onto a fixed
  palette; the output colour set is a subset of the palette (acceptance-critical,
  SC-L009-1/-2). The nearest metric is ``'distance_sq'`` (fast default) or
  ``'ciede2000'`` (opt-in, delegates to
  :mod:`~pixelart_creator.logic.perceptual`, CL-11).
* :func:`median_cut` extracts ≤N colours by Heckbert median-cut (fast,
  deterministic default; SC-L010-1).
* :func:`kmeans` extracts ≤N colours by seeded k-means++ clustering in Lab
  (higher-quality, reproducible; SC-L011-1/-2).

:func:`make_constraint_command` captures a constraint application as a reversible
:class:`~pixelart_creator.logic.history.PixelEdit` (REQ-P3-LOGIC-017).

Grounding: median-cut (Heckbert 1980) and k-means++ / Lab clustering are from
``docs/research-phase3-colour.md`` Topic 3 (F9). Only ``PALETTE_EXTRACT_DEFAULT_N``
and ``KMEANS_SEED`` are tuning scalars in
:mod:`~pixelart_creator.logic.constants`. REQ-P3-LOGIC-009, -010, -011.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import numpy.typing as npt

from pixelart_creator.logic import history, perceptual
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import KMEANS_SEED, PALETTE_EXTRACT_DEFAULT_N
from pixelart_creator.logic.palette import Palette, PaletteError
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import SelectionMask

__all__ = [
    "QuantizeError",
    "constrain_to_palette",
    "median_cut",
    "kmeans",
    "make_constraint_command",
]

_METRICS = ("distance_sq", "ciede2000")


class QuantizeError(ValueError):
    """Raised on an invalid metric or extraction count."""


def _require_rgba(source: PixelBuffer) -> None:
    if source.mode is not ColorMode.RGBA:
        raise QuantizeError("quantization requires an RGBA source buffer")


def _pixels(source: PixelBuffer) -> npt.NDArray[np.int64]:
    """Return the buffer's pixels as an ``(N, 4)`` int array."""
    return source.data.reshape(-1, 4).astype(np.int64)


def _nearest_indices_distance_sq(
    pixels: npt.NDArray[np.int64], pal: npt.NDArray[np.int64]
) -> npt.NDArray[np.intp]:
    best = np.zeros(pixels.shape[0], dtype=np.intp)
    best_dist = np.full(pixels.shape[0], np.inf, dtype=np.float64)
    for i in range(pal.shape[0]):
        diff = (pixels - pal[i]).astype(np.float64)
        dist = np.einsum("ij,ij->i", diff, diff)
        closer = dist < best_dist
        best_dist = np.where(closer, dist, best_dist)
        best = np.where(closer, i, best)
    return best


def constrain_to_palette(
    source: PixelBuffer, palette: Palette, *, metric: str = "distance_sq"
) -> PixelBuffer:
    """Return a copy of ``source`` with every pixel snapped to ``palette``.

    Args:
        source: The RGBA buffer to constrain.
        palette: The fixed target palette (e.g. NES / Game Boy).
        metric: ``'distance_sq'`` (default, fast) or ``'ciede2000'`` (opt-in
            perceptual, CL-11).

    Returns:
        A new buffer whose colour set is a subset of ``palette`` (SC-L009-1/-2),
        each pixel mapped to its nearest palette colour (SC-L009-3); deterministic.

    Raises:
        QuantizeError: If ``source`` is not RGBA or ``metric`` is unknown.
        PaletteError: If ``palette`` is empty.
    """
    _require_rgba(source)
    colors = palette.colors()
    if not colors:
        raise PaletteError("cannot constrain against an empty palette")
    if metric not in _METRICS:
        raise QuantizeError(f"unknown metric {metric!r}; expected one of {_METRICS}")

    pal = np.asarray(colors, dtype=np.int64)
    pixels = _pixels(source)
    # Map unique colours only, then broadcast back (deterministic + efficient).
    unique, inverse = np.unique(pixels, axis=0, return_inverse=True)
    if metric == "distance_sq":
        uniq_idx = _nearest_indices_distance_sq(unique, pal)
    else:
        uniq_idx = np.array(
            [
                perceptual.nearest_index_perceptual(
                    palette, (int(c[0]), int(c[1]), int(c[2]), int(c[3]))
                )
                for c in unique
            ],
            dtype=np.intp,
        )
    mapped = pal[uniq_idx][inverse.reshape(-1)]

    out = PixelBuffer(source.width, source.height, ColorMode.RGBA)
    out.data[:, :] = mapped.reshape(source.height, source.width, 4).astype(np.uint8)
    return out


def _dedup_palette(colors: List[RGBA], limit: int) -> Palette:
    seen: set[RGBA] = set()
    ordered: List[RGBA] = []
    for c in colors:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
        if len(ordered) >= limit:
            break
    return Palette(ordered)


def median_cut(source: PixelBuffer, n: int = PALETTE_EXTRACT_DEFAULT_N) -> Palette:
    """Extract a palette of at most ``n`` colours by median-cut (Heckbert).

    Recursively splits the colour box of greatest range at the median along its
    widest channel until ``n`` boxes exist (or no box is further splittable); each
    box contributes its mean colour. Deterministic for fixed input+``n``
    (SC-L010-4). An image with ≤``n`` distinct colours returns exactly those
    (SC-L010-3).

    Raises:
        QuantizeError: If ``source`` is not RGBA or ``n <= 0``.
    """
    _require_rgba(source)
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise QuantizeError(f"n must be a positive int, got {n!r}")

    pixels = _pixels(source)
    boxes: List[npt.NDArray[np.int64]] = [pixels]

    def _range(box: npt.NDArray[np.int64]) -> int:
        return int((box.max(axis=0) - box.min(axis=0)).max()) if box.size else 0

    while len(boxes) < n:
        # Pick the splittable box (range > 0) with the greatest channel range.
        candidates = [(i, _range(b)) for i, b in enumerate(boxes) if _range(b) > 0]
        if not candidates:
            break
        target = max(candidates, key=lambda item: (item[1], -item[0]))[0]
        box = boxes[target]
        spans = box.max(axis=0) - box.min(axis=0)
        channel = int(np.argmax(spans))
        order = np.argsort(box[:, channel], kind="stable")
        ordered_box = box[order]
        mid = len(ordered_box) // 2
        if mid == 0 or mid == len(ordered_box):
            break
        boxes[target] = ordered_box[:mid]
        boxes.insert(target + 1, ordered_box[mid:])

    means: List[RGBA] = []
    for box in boxes:
        if not box.size:
            continue
        mean = np.round(box.mean(axis=0)).astype(np.int64)
        means.append((int(mean[0]), int(mean[1]), int(mean[2]), int(mean[3])))
    return _dedup_palette(means, n)


def _kmeans_plus_plus_init(
    data: npt.NDArray[np.float64],
    weights: npt.NDArray[np.float64],
    k: int,
    rng: np.random.Generator,
) -> npt.NDArray[np.float64]:
    n = data.shape[0]
    first = int(rng.choice(n, p=weights / weights.sum()))
    centroids = [data[first]]
    for _ in range(1, k):
        dists = np.min(
            np.stack(
                [np.einsum("ij,ij->i", data - c, data - c) for c in centroids], axis=0
            ),
            axis=0,
        )
        weighted = dists * weights
        total = weighted.sum()
        if total <= 0.0:
            centroids.append(data[int(rng.choice(n))])
        else:
            centroids.append(data[int(rng.choice(n, p=weighted / total))])
    return np.stack(centroids, axis=0)


def kmeans(
    source: PixelBuffer, n: int = PALETTE_EXTRACT_DEFAULT_N, *, seed: int = KMEANS_SEED
) -> Palette:
    """Extract a palette of at most ``n`` colours by seeded k-means (k = ``n``).

    Clusters the buffer's unique colours in CIELAB with k-means++ initialisation;
    each cluster contributes the (weighted) mean RGBA of its members. Seeded so
    identical input+``n``+``seed`` reproduces identical output (CL-8, SC-L011-2).
    Returns at most ``n`` colours (SC-L011-1).

    Raises:
        QuantizeError: If ``source`` is not RGBA or ``n <= 0``.
    """
    _require_rgba(source)
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise QuantizeError(f"n must be a positive int, got {n!r}")

    pixels = _pixels(source)
    unique, counts = np.unique(pixels, axis=0, return_counts=True)
    if unique.shape[0] <= n:
        return _dedup_palette(
            [(int(c[0]), int(c[1]), int(c[2]), int(c[3])) for c in unique], n
        )

    lab = np.array(
        [
            perceptual.rgba_to_lab((int(c[0]), int(c[1]), int(c[2]), int(c[3])))
            for c in unique
        ],
        dtype=np.float64,
    )
    weights = counts.astype(np.float64)
    rng = np.random.default_rng(seed)
    centroids = _kmeans_plus_plus_init(lab, weights, n, rng)

    assignment = np.zeros(lab.shape[0], dtype=np.intp)
    for _ in range(64):  # Lloyd iterations; converges to a local optimum.
        dists = np.stack(
            [np.einsum("ij,ij->i", lab - c, lab - c) for c in centroids], axis=0
        )
        new_assignment = np.argmin(dists, axis=0)
        if np.array_equal(new_assignment, assignment):
            break
        assignment = new_assignment
        for j in range(n):
            members = assignment == j
            if members.any():
                w = weights[members]
                centroids[j] = np.average(lab[members], axis=0, weights=w)

    means: List[RGBA] = []
    for j in range(n):
        members = assignment == j
        if not members.any():
            continue
        w = weights[members]
        rgb_mean = np.round(
            np.average(unique[members].astype(np.float64), axis=0, weights=w)
        ).astype(np.int64)
        means.append(
            (int(rgb_mean[0]), int(rgb_mean[1]), int(rgb_mean[2]), int(rgb_mean[3]))
        )
    return _dedup_palette(means, n)


def make_constraint_command(
    buffer: PixelBuffer,
    palette: Palette,
    *,
    metric: str = "distance_sq",
    mask: Optional[SelectionMask] = None,
) -> history.Command:
    """Build a reversible command constraining ``buffer`` onto ``palette``.

    Returns a :class:`history.PixelEdit` (returned **unapplied**) whose undo
    restores the prior pixels exactly (SC-L017-1). With a ``mask`` only masked
    pixels change.

    Raises:
        QuantizeError: If ``metric`` is unknown or ``buffer`` is not RGBA.
        PaletteError: If ``palette`` is empty.
    """
    constrained = constrain_to_palette(buffer, palette, metric=metric)
    changes: List[history.PixelChange] = []
    for y in range(buffer.height):
        for x in range(buffer.width):
            if mask is not None and not mask.is_selected(x, y):
                continue
            old = buffer.get_pixel(x, y)
            new = constrained.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
    return history.PixelEdit(buffer, changes, label="constrain to palette")
