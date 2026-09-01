# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Non-transparent-pixel bounding box of a frame (zero Qt, REQ-IS-LOGIC-003).

:func:`content_bounds` answers a single question for the "fit to content"
viewport gesture: what is the tight rectangle around every pixel a user has
actually painted, across the **visible** layers of one :class:`~pixelart_creator
.logic.document.Frame`? It is deliberately narrow — geometry only, no
compositing, no mutation — because the caller (``Canvas_View.fit_content()``)
runs it on a gesture path and only needs the rectangle.

**Union over visible layers, not a composited buffer (plan §3.4).** The
result is the union, over every :class:`~pixelart_creator.logic.document.Layer`
reachable through a **visible** chain of the frame's layer tree, of that
layer's own ``alpha > 0`` extent — computed with one vectorised
``np.any(..., axis=2)`` reduction per contributing layer. It is *not* the
alpha extent of a flattened composite: building a full composite of an 8K
frame allocates a ~126 MB throwaway buffer for a value this function never
needs, and the requirement text itself asks for the union across "all visible
layers", not for what a composite would show.

**The known, accepted divergence from a composite:** a layer that is
``visible=True`` but has ``opacity == 0.0`` (or sits under a blend mode that
annihilates its contribution) still contributes its ``alpha > 0`` extent here,
where it would contribute nothing to a composite. This module follows the
shipped, user-facing ``visible`` flag — the word the requirement uses — rather
than "visually contributes"; reversing this choice is local to this module and
its one test (plan §3.4).

A :class:`~pixelart_creator.logic.document.LayerGroup` gates its whole subtree
the same way the compositor does (``logic/blend.py::_reduce_nodes``): a group
with ``visible=False`` hides every layer beneath it regardless of that layer's
own ``visible`` flag, so a leaf's *effective* visibility is the AND of its own
flag and every ancestor group's flag.

A smart layer's contribution is read through
:meth:`~pixelart_creator.logic.document.Layer.effective_buffer`, mirroring the
compositor (``logic/blend.py::_node_source_region``), so a smart layer reports
its *live source's* pixels rather than its own (usually empty) placeholder
buffer.

Mutates no buffer it reads (each layer's ``PixelBuffer.data`` is only read,
never written or copied); Qt-free (S11); imports no ``ui`` or ``data`` module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List, Optional, Tuple

import numpy as np

from pixelart_creator.logic.pixel_buffer import ColorMode

if TYPE_CHECKING:
    from pixelart_creator.logic.document import Frame, Layer, LayerNode


class ContentBoundsError(ValueError):
    """Raised when a layer buffer's geometry does not match the frame canvas."""


def _iter_visible_layers(nodes: "List[LayerNode]") -> "Iterator[Layer]":
    """Yield the :class:`Layer` leaves reachable through an all-visible chain.

    A node — leaf or :class:`~pixelart_creator.logic.document.LayerGroup` —
    with ``visible is False`` hides itself and its whole subtree, matching
    ``logic/blend.py::_reduce_nodes`` (LOGIC-006/011). Does not mutate ``nodes``
    or any node in it.
    """
    for node in nodes:
        if not node.visible:
            continue
        children = getattr(node, "children", None)
        if children is not None:
            yield from _iter_visible_layers(children)
        else:
            yield node  # type: ignore[misc]


def content_bounds(
    frame: "Frame", width: int, height: int
) -> Optional[Tuple[int, int, int, int]]:
    """Return the tight inclusive bbox of the non-transparent union, or ``None``.

    Computes ``(x0, y0, x1, y1)`` — the smallest rectangle containing every
    pixel with ``alpha > 0`` across the union of ``frame``'s **visible** layers
    (module docstring), or ``None`` when no such pixel exists anywhere in the
    frame. Matches :meth:`~pixelart_creator.logic.selection.SelectionMask.bounds`'s
    exact ``Optional[Tuple[int, int, int, int]]`` contract (plan §3.4) so both
    "explicit empty result" idioms in the logic layer share one vocabulary.

    Each contributing layer's buffer is read with one vectorised
    ``np.any(alpha > 0, axis=...)`` row/column reduction — no full-canvas
    composite is allocated (module docstring). Mutates nothing it reads.

    Args:
        frame: The frame whose visible layer tree is examined.
        width: The canvas width every layer buffer must match.
        height: The canvas height every layer buffer must match.

    Raises:
        ContentBoundsError: If a visible layer's effective buffer is not RGBA,
            or its dimensions do not match ``(width, height)``.
    """
    x0 = y0 = None
    x1 = y1 = None

    for layer in _iter_visible_layers(frame.layers):
        buffer = layer.effective_buffer()
        if buffer.mode is not ColorMode.RGBA:
            raise ContentBoundsError(
                f"content_bounds requires RGBA layer buffers, got {buffer.mode.value}"
            )
        if buffer.width != width or buffer.height != height:
            raise ContentBoundsError(
                f"layer buffer {buffer.width}x{buffer.height} does not match "
                f"canvas {width}x{height}"
            )

        opaque = buffer.data[:, :, 3] > 0
        if not opaque.any():
            continue

        rows = np.any(opaque, axis=1)
        cols = np.any(opaque, axis=0)
        row_idx = np.flatnonzero(rows)
        col_idx = np.flatnonzero(cols)
        layer_y0, layer_y1 = int(row_idx[0]), int(row_idx[-1])
        layer_x0, layer_x1 = int(col_idx[0]), int(col_idx[-1])

        x0 = layer_x0 if x0 is None else min(x0, layer_x0)
        y0 = layer_y0 if y0 is None else min(y0, layer_y0)
        x1 = layer_x1 if x1 is None else max(x1, layer_x1)
        y1 = layer_y1 if y1 is None else max(y1, layer_y1)

    if x0 is None:
        return None
    assert y0 is not None and x1 is not None and y1 is not None
    return (x0, y0, x1, y1)
