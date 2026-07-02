"""Pixel-perfect freehand stroke corner removal (zero Qt, S11).

:func:`pixel_perfect` thins a freehand stroke's coordinate sequence to a clean
1-px path by dropping the "elbow" pixel of every L-shaped triple — the exact
rule Aseprite implements in ``IntertwineAsPixelPerfect::joinStroke()`` (research
Topic 2, REQ-P2-LOGIC-012). Leaf module: stdlib only, deterministic.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

Coord = Tuple[int, int]


def _is_elbow(a: Coord, b: Coord, c: Coord) -> bool:
    """Return whether ``b`` is the corner of an L-triple ``a -> b -> c``.

    ``b`` is an elbow when ``a`` shares an x or y with ``b`` (axis-aligned and
    adjacent), ``c`` shares an x or y with ``b``, and ``a`` and ``c`` share
    *neither* coordinate (the path changed direction rather than running
    straight) — the Aseprite corner-removal condition.
    """
    return (
        (a[0] == b[0] or a[1] == b[1])
        and (c[0] == b[0] or c[1] == b[1])
        and a[0] != c[0]
        and a[1] != c[1]
    )


def pixel_perfect(coords: Sequence[Coord]) -> List[Coord]:
    """Remove elbow pixels from a freehand stroke, yielding a clean 1-px path.

    Applies the Aseprite rule (research Topic 2): the middle pixel of every
    L-shaped triple is dropped. Endpoints are never removed; already-clean
    straight or diagonal lines are returned unchanged (idempotent); the surviving
    pixels keep their original order. Consecutive duplicate points are collapsed.

    Args:
        coords: The ordered ``(x, y)`` coordinates of a freehand stroke (as
            produced by filling mouse samples with Bresenham lines).

    Returns:
        The thinned coordinate list. Deterministic for identical input.
    """
    out: List[Coord] = []
    for point in coords:
        if out and out[-1] == point:
            continue  # collapse consecutive duplicates
        out.append(point)
        # Re-check the tail so a removal that creates a new elbow cascades; this
        # keeps every consecutive triple non-elbow (idempotence, order-preserving).
        while len(out) >= 3 and _is_elbow(out[-3], out[-2], out[-1]):
            del out[-2]
    return out
