"""Symmetry-axis model & mirrored-coordinate generation (zero Qt, S11).

Given a source pixel and an axis, :func:`mirror` returns the set of coordinates a
stroke must also paint so symmetric art draws itself (live mirror drawing,
REQ-P2-LOGIC-011). The :class:`SymmetryAxis` enum lives here (module-local, plan
PL-D3: enums live with their module, cf. ``ColorMode`` in ``pixel_buffer.py``).
Deterministic and side-effect-free.
"""

from __future__ import annotations

import enum
from typing import Optional, Set, Tuple

Coord = Tuple[int, int]


class SymmetryAxis(enum.Enum):
    """The available mirror axes for live symmetry drawing (CL-9, CL-10)."""

    NONE = "none"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    BOTH = "both"
    DIAGONAL = "diagonal"


def mirror(
    x: int,
    y: int,
    axis: SymmetryAxis,
    width: int,
    height: int,
    axis_pos: Optional[Tuple[int, int]] = None,
) -> Set[Coord]:
    """Return the source coordinate plus its mirror image(s) for ``axis``.

    The returned set always contains ``(x, y)`` itself (when in bounds). Mirror
    images are added per axis, de-duplicated, and clipped to ``0..width-1`` /
    ``0..height-1``:

    * ``VERTICAL`` reflects across the vertical axis -> ``(W-1-x, y)``.
    * ``HORIZONTAL`` reflects across the horizontal axis -> ``(x, H-1-y)``.
    * ``BOTH`` yields the 4-way set (vertical + horizontal + both).
    * ``DIAGONAL`` reflects across the main (top-left -> bottom-right) diagonal.
    * ``NONE`` returns only the source coordinate.

    Args:
        x, y: Source pixel coordinate.
        axis: The active :class:`SymmetryAxis`.
        width, height: Buffer dimensions (non-positive -> empty set).
        axis_pos: The mirror centre ``(ax, ay)``. Defaults to the canvas centre
            ``((W-1)/2, (H-1)/2)`` (CL-9).

    Returns:
        A de-duplicated, in-bounds set of coordinates to paint.
    """
    if width <= 0 or height <= 0:
        return set()

    if axis_pos is None:
        ax = (width - 1) / 2.0
        ay = (height - 1) / 2.0
    else:
        ax = float(axis_pos[0])
        ay = float(axis_pos[1])

    vx = int(round(2.0 * ax - x))
    hy = int(round(2.0 * ay - y))
    dx = int(round(ax + (y - ay)))
    dy = int(round(ay + (x - ax)))

    candidates: Set[Coord] = {(x, y)}
    if axis is SymmetryAxis.VERTICAL:
        candidates.add((vx, y))
    elif axis is SymmetryAxis.HORIZONTAL:
        candidates.add((x, hy))
    elif axis is SymmetryAxis.BOTH:
        candidates.update({(vx, y), (x, hy), (vx, hy)})
    elif axis is SymmetryAxis.DIAGONAL:
        candidates.add((dx, dy))
    # SymmetryAxis.NONE -> only the source coordinate.

    return {(cx, cy) for cx, cy in candidates if 0 <= cx < width and 0 <= cy < height}
