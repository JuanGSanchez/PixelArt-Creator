# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Pure pixel-drawing algorithms over a :class:`PixelBuffer` (zero Qt, S11).

These are the raster primitives the Phase 1 tools (pencil, eraser, line, fill,
colour picker) and later shape tools are built from. Each mutating routine
returns the list of ``(x, y)`` coordinates it actually changed, clipped to the
buffer — the caller turns that into a reversible undo record
(see ``logic/history.py``). Algorithms are deterministic (P2).
"""

from __future__ import annotations

from typing import List, Tuple, Union

from pixelart_creator.logic.color import RGBA, distance_sq
from pixelart_creator.logic.pixel_buffer import PixelBuffer, PixelValue

Coord = Tuple[int, int]


def _plot(buf: PixelBuffer, x: int, y: int, value: Union[RGBA, int]) -> bool:
    """Set one in-bounds pixel; return whether it was in bounds."""
    if not buf.in_bounds(x, y):
        return False
    buf.set_pixel(x, y, value)
    return True


def pencil(buf: PixelBuffer, x: int, y: int, value: Union[RGBA, int]) -> List[Coord]:
    """Draw a single pixel (pencil / eraser share this)."""
    return [(x, y)] if _plot(buf, x, y, value) else []


def pick_color(buf: PixelBuffer, x: int, y: int) -> PixelValue:
    """Colour-picker: read the pixel value at ``(x, y)``."""
    return buf.get_pixel(x, y)


def line(
    buf: PixelBuffer, x0: int, y0: int, x1: int, y1: int, value: Union[RGBA, int]
) -> List[Coord]:
    """Draw a 1-px line with Bresenham's integer algorithm."""
    changed: List[Coord] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = x0, y0
    while True:
        if _plot(buf, cx, cy, value):
            changed.append((cx, cy))
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sx
        if e2 <= dx:
            err += dx
            cy += sy
    return changed


def rectangle(
    buf: PixelBuffer,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    value: Union[RGBA, int],
    *,
    filled: bool = False,
) -> List[Coord]:
    """Draw a rectangle defined by two opposite corners (outline or filled)."""
    lx, rx = (x0, x1) if x0 <= x1 else (x1, x0)
    ty, by = (y0, y1) if y0 <= y1 else (y1, y0)
    changed: List[Coord] = []
    seen: set[Coord] = set()

    def put(x: int, y: int) -> None:
        if (x, y) not in seen and _plot(buf, x, y, value):
            seen.add((x, y))
            changed.append((x, y))

    if filled:
        for y in range(ty, by + 1):
            for x in range(lx, rx + 1):
                put(x, y)
        return changed
    for x in range(lx, rx + 1):
        put(x, ty)
        put(x, by)
    for y in range(ty, by + 1):
        put(lx, y)
        put(rx, y)
    return changed


def ellipse(
    buf: PixelBuffer,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    value: Union[RGBA, int],
    *,
    filled: bool = False,
) -> List[Coord]:
    """Draw an ellipse inscribed in the bounding box ``(x0,y0)-(x1,y1)``.

    Uses the midpoint ellipse algorithm on the integer bounding box. When
    ``filled``, horizontal spans between symmetric points are filled.
    """
    lx, rx = (x0, x1) if x0 <= x1 else (x1, x0)
    ty, by = (y0, y1) if y0 <= y1 else (y1, y0)
    a = (rx - lx) / 2.0
    b = (by - ty) / 2.0
    cx = (lx + rx) / 2.0
    cy = (ty + by) / 2.0

    changed: List[Coord] = []
    seen: set[Coord] = set()

    def put(x: int, y: int) -> None:
        if (x, y) not in seen and _plot(buf, x, y, value):
            seen.add((x, y))
            changed.append((x, y))

    def emit(px: int, py: int) -> None:
        # Four-way symmetry around the (possibly half-integer) centre.
        xs = {int(round(cx + px)), int(round(cx - px))}
        ys = {int(round(cy + py)), int(round(cy - py))}
        if filled:
            xmin, xmax = min(xs), max(xs)
            for yy in ys:
                for xx in range(xmin, xmax + 1):
                    put(xx, yy)
        else:
            for xx in xs:
                for yy in ys:
                    put(xx, yy)

    if a < 0.5 or b < 0.5:  # degenerate: a line or point
        return rectangle(buf, x0, y0, x1, y1, value, filled=True)

    x = 0.0
    y = b
    a2 = a * a
    b2 = b * b
    # Region 1
    d1 = b2 - a2 * b + 0.25 * a2
    dx = 2 * b2 * x
    dy = 2 * a2 * y
    while dx < dy:
        emit(int(round(x)), int(round(y)))
        if d1 < 0:
            x += 1
            dx += 2 * b2
            d1 += dx + b2
        else:
            x += 1
            y -= 1
            dx += 2 * b2
            dy -= 2 * a2
            d1 += dx - dy + b2
    # Region 2
    d2 = b2 * (x + 0.5) ** 2 + a2 * (y - 1) ** 2 - a2 * b2
    while y >= 0:
        emit(int(round(x)), int(round(y)))
        if d2 > 0:
            y -= 1
            dy -= 2 * a2
            d2 += a2 - dy
        else:
            y -= 1
            x += 1
            dx += 2 * b2
            dy -= 2 * a2
            d2 += dx - dy + a2
    return changed


def _matches(a: PixelValue, b: PixelValue, tolerance: int) -> bool:
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if isinstance(a, tuple) and isinstance(b, tuple):
        if tolerance <= 0:
            return a == b
        return distance_sq(a, b) <= tolerance * tolerance
    return False


def flood_fill(
    buf: PixelBuffer,
    x: int,
    y: int,
    value: Union[RGBA, int],
    *,
    tolerance: int = 0,
) -> List[Coord]:
    """Scanline flood-fill the contiguous region matching the seed pixel.

    Args:
        buf: Target buffer.
        x, y: Seed coordinate (must be in bounds).
        value: Replacement value.
        tolerance: For RGBA, max per-pixel RGBA distance treated as "same"
            (0 = exact match). Ignored for indexed buffers.

    Returns:
        The coordinates filled (empty if the seed already equals ``value`` and
        so nothing changes).
    """
    if not buf.in_bounds(x, y):
        return []
    target = buf.get_pixel(x, y)
    replacement = buf._normalise_value(value)  # noqa: SLF001 (same-module intent)
    if _matches(target, replacement, 0):
        return []

    changed: List[Coord] = []
    filled: set[Coord] = set()
    stack: List[Coord] = [(x, y)]
    width = buf.width

    while stack:
        sx, sy = stack.pop()
        if (sx, sy) in filled:
            continue
        # Walk left/right to the run extent.
        left = sx
        while (
            left - 1 >= 0
            and (left - 1, sy) not in filled
            and _matches(buf.get_pixel(left - 1, sy), target, tolerance)
        ):
            left -= 1
        right = sx
        while (
            right + 1 < width
            and (right + 1, sy) not in filled
            and _matches(buf.get_pixel(right + 1, sy), target, tolerance)
        ):
            right += 1
        for px in range(left, right + 1):
            if (px, sy) in filled:
                continue
            if not _matches(buf.get_pixel(px, sy), target, tolerance):
                continue
            buf.set_pixel(px, sy, value)
            filled.add((px, sy))
            changed.append((px, sy))
            for ny in (sy - 1, sy + 1):
                if (
                    0 <= ny < buf.height
                    and (px, ny) not in filled
                    and _matches(buf.get_pixel(px, ny), target, tolerance)
                ):
                    stack.append((px, ny))
    return changed
