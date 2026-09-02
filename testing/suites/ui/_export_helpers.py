"""Shared builders for the Phase-7 export UI tests (testing/suites/ui only).

Pure-logic document factories the export UI binds to — no Qt is needed to build
them, so they exercise the frozen ``logic``/``data`` export engine exactly as the
widgets do (Article I / S11). Kept out of ``conftest`` fixtures so the parity /
worker / batch modules can share them without import gymnastics.
"""

from __future__ import annotations

from pixelart_creator.logic.document import Document, PlaybackMode
from pixelart_creator.logic.palette import Palette

#: A tiny deterministic palette (mirrors ``conftest.STARTER``).
_STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def paint(document: Document, frame_index: int, colour, *, box=None) -> None:
    """Fill ``box`` (or the whole frame) of ``document``'s frame with ``colour``.

    Writes straight into the frame's first layer buffer so the export flatten
    (CO-4) produces non-trivial, deterministic pixels.
    """
    layer = document.frames[frame_index].layers[0]
    data = layer.buffer.data
    if box is None:
        data[:, :] = colour
    else:
        x0, y0, x1, y1 = box
        data[y0:y1, x0:x1] = colour


def single_frame_document(width: int = 32, height: int = 32) -> Document:
    """Return a 1-frame RGBA document with a painted red block (for PNG/atlas)."""
    doc = Document(width, height, palette=Palette(_STARTER))
    paint(doc, 0, RED, box=(4, 4, width - 4, height - 4))
    return doc


def animation_document(
    frames: int = 3, width: int = 16, height: int = 16, *, tag: bool = False
) -> Document:
    """Return a multi-frame document with distinct per-frame colours + durations.

    Frame durations are deliberately non-uniform ([120, 480, 120, ...]) so a GIF
    export's per-frame delays are observably duration-faithful (FR-1). When
    ``tag`` is set a ``"walk"`` LOOP tag spanning every frame is appended, so the
    GIF frame-source combo lists a named tag.
    """
    doc = Document(width, height, palette=Palette(_STARTER))
    paint(doc, 0, RED)
    palette = [RED, GREEN, BLUE]
    for index in range(1, frames):
        duration = 480 if index == 1 else 120
        doc.add_frame(duration_ms=duration)
        paint(doc, index, palette[index % len(palette)])
    if tag:
        doc.make_add_tag_command(
            "walk", 0, frames - 1, mode=PlaybackMode.LOOP
        ).execute()
    return doc
