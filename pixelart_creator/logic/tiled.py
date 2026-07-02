"""Tiled-drawing wrap model and repeating preview (zero Qt, S11).

Tiled mode treats the canvas as a torus: any paint coordinate maps to
``(x mod W, y mod H)`` so edits wrap seamlessly across edges (CL-14).
:func:`preview_tiling` builds the ``TILED_PREVIEW_REPEAT`` x
``TILED_PREVIEW_REPEAT`` repeating arrangement (data only — no Qt), and
:func:`make_tiled_command` turns a wrapped paint op into a reversible
``history.PixelEdit``. REQ-P2-LOGIC-014.
"""

from __future__ import annotations

from typing import Callable, List, Sequence, Tuple, Union

from pixelart_creator.logic import history
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import TILED_PREVIEW_REPEAT
from pixelart_creator.logic.pixel_buffer import PixelBuffer

Coord = Tuple[int, int]

#: A wrapped paint op: returns the coordinates it intends to paint (which may lie
#: outside the buffer and will be wrapped) plus the value to paint.
TiledPaint = Callable[[], Tuple[Sequence[Coord], Union[RGBA, int]]]


def wrap(x: int, y: int, width: int, height: int) -> Coord:
    """Map ``(x, y)`` onto the torus ``(x mod W, y mod H)`` (handles negatives).

    Raises:
        ValueError: If ``width`` or ``height`` is not positive.
    """
    if width <= 0 or height <= 0:
        raise ValueError(f"width/height must be positive, got {width}x{height}")
    return (x % width, y % height)


def preview_tiling(
    buffer: PixelBuffer, repeat: int = TILED_PREVIEW_REPEAT
) -> PixelBuffer:
    """Return a ``repeat`` x ``repeat`` repeating arrangement of ``buffer``.

    Defaults to 3x3 (``TILED_PREVIEW_REPEAT``, CL-13); the centre tile is the
    editable one, the neighbours are previews. Data only — no Qt.

    Raises:
        ValueError: If ``repeat`` is not a positive int.
    """
    if not isinstance(repeat, int) or isinstance(repeat, bool) or repeat <= 0:
        raise ValueError(f"repeat must be a positive int, got {repeat!r}")
    w, h = buffer.width, buffer.height
    out = PixelBuffer(w * repeat, h * repeat, buffer.mode)
    for row in range(repeat):
        for col in range(repeat):
            out.blit(buffer, col * w, row * h)
    return out


def make_tiled_command(buffer: PixelBuffer, operation: TiledPaint) -> history.Command:
    """Apply a wrapped paint op and capture it as a reversible command.

    ``operation`` returns ``(coords, value)``; each coordinate is wrapped modulo
    ``(W, H)`` (torus, CL-14) before painting ``value``. Returns an **unapplied**
    :class:`history.PixelEdit` of the wrapped changed pixels (push with
    ``execute=True``); ``apply then undo`` restores the buffer exactly
    (SC-L014-4).
    """
    coords, value = operation()
    w, h = buffer.width, buffer.height
    normalised = buffer._normalise_value(value)  # noqa: SLF001 (same-layer intent)
    changes: List[history.PixelChange] = []
    seen: set[Coord] = set()
    for x, y in coords:
        wx, wy = x % w, y % h
        if (wx, wy) in seen:
            continue
        seen.add((wx, wy))
        old = buffer.get_pixel(wx, wy)
        if old != normalised:
            changes.append((wx, wy, old, normalised))
    return history.PixelEdit(buffer, changes, label="tiled edit")
