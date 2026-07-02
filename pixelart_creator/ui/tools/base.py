"""Tool-controller contract + stroke helper (REQ-P1-UI-011; CL-9/-12).

A :class:`Tool` maps floored pixel coordinates (CL-12) to ``logic/drawing.py``
primitives and, via :class:`Stroke`, coalesces a whole click-drag into a single
reversible :class:`~pixelart_creator.logic.history.PixelEdit` (CL-9) wrapped in a
:class:`~pixelart_creator.ui.commands.PaintCommand`. The controllers hold no
pixel math — that lives in ``logic/drawing.py`` (Article I). This module only
performs undo bookkeeping (capture-before / diff-after, the same pattern as
:func:`logic.history.record_edit`) and Qt wiring.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Set, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic import drawing
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.history import PixelChange, PixelEdit
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue
from pixelart_creator.logic.selection import SelectionMask
from pixelart_creator.logic.symmetry import SymmetryAxis, mirror
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.commands import PaintCommand

Coord = Tuple[int, int]


def bounding_rect(coords: Set[Coord]) -> QRectF:
    """Return the inclusive pixel bounding rect of ``coords`` (empty if none)."""
    if not coords:
        return QRectF()
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    x0, y0 = min(xs), min(ys)
    return QRectF(x0, y0, max(xs) - x0 + 1, max(ys) - y0 + 1)


def mirror_coords(coords: Iterable[Coord], ctx: "ToolContext") -> Set[Coord]:
    """Return the mirror images of ``coords`` for the context's symmetry axis.

    Delegates the mirror geometry to :func:`logic.symmetry.mirror` (no math in the
    controller, S11). Empty when symmetry is off. The source coords are excluded
    so the caller stamps only the *extra* mirrored pixels.
    """
    axis = ctx.symmetry_axis
    if axis is SymmetryAxis.NONE:
        return set()
    w, h = ctx.buffer.width, ctx.buffer.height
    out: Set[Coord] = set()
    for x, y in coords:
        for m in mirror(x, y, axis, w, h, ctx.symmetry_pos):
            if m != (x, y):
                out.add(m)
    return out


class Stroke:
    """Accumulates a drag's pixel changes into one reversible edit (CL-9).

    A snapshot is taken at construction; primitives mutate the live buffer and
    report the coordinates they touched. :meth:`to_command` diffs the touched
    pixels against the snapshot to build a minimal :class:`PixelEdit`.
    """

    def __init__(self, buffer: PixelBuffer) -> None:
        self._buffer = buffer
        self._before = buffer.copy()
        self._touched: Set[Coord] = set()

    def pencil(self, x: int, y: int, value: PixelValue) -> List[Coord]:
        """Plot a single pixel through ``drawing.pencil``; return changed coords."""
        coords = drawing.pencil(self._buffer, x, y, value)
        self._touched.update(coords)
        return coords

    def line(
        self, x0: int, y0: int, x1: int, y1: int, value: PixelValue
    ) -> List[Coord]:
        """Plot a Bresenham segment through ``drawing.line`` (gap-free drag)."""
        coords = drawing.line(self._buffer, x0, y0, x1, y1, value)
        self._touched.update(coords)
        return coords

    def stamp(self, coords: Iterable[Coord], value: PixelValue) -> List[Coord]:
        """Plot each coordinate through ``drawing.pencil`` (mirror / cleaned path)."""
        painted: List[Coord] = []
        for cx, cy in coords:
            painted.extend(drawing.pencil(self._buffer, cx, cy, value))
        self._touched.update(painted)
        return painted

    def absorb(self, coords: Iterable[Coord]) -> None:
        """Register coords changed by an external op (e.g. a masked shape commit).

        The op (``drawing.rectangle`` / ``apply_masked``) mutates the buffer and
        returns the coords it changed; recording them lets :meth:`to_command` diff
        against the pre-op snapshot to build the minimal reversible edit.
        """
        self._touched.update(coords)

    def revert_touched(self) -> None:
        """Restore every touched pixel to its pre-stroke value (keeps dirty rect).

        Used by the pixel-perfect and tiled modes, which live-plot a provisional
        path and then rebuild the committed edit from the clean snapshot.
        """
        for cx, cy in self._touched:
            self._buffer.set_pixel(cx, cy, self._before.get_pixel(cx, cy))

    def flood_fill(self, x: int, y: int, value: PixelValue) -> None:
        """Fill the contiguous region through ``drawing.flood_fill``."""
        self._touched.update(drawing.flood_fill(self._buffer, x, y, value))

    def last_rect(self, coords: Set[Coord]) -> QRectF:
        """Bounding rect of a coord set (for live dirty-rect refresh, D5)."""
        return bounding_rect(coords)

    def touched_rect(self) -> QRectF:
        """Bounding rect of every pixel touched so far."""
        return bounding_rect(self._touched)

    def to_command(
        self,
        refresh: Callable[[QRectF], None],
        label: str,
    ) -> Optional[PaintCommand]:
        """Build a :class:`PaintCommand`, or ``None`` if nothing changed (CL-12/-14)."""
        changes: List[PixelChange] = []
        for x, y in sorted(self._touched):
            old = self._before.get_pixel(x, y)
            new = self._buffer.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
        if not changes:
            return None
        edit = PixelEdit(self._buffer, changes, label=label)
        return PaintCommand(edit, refresh, self.touched_rect(), text=label)


class ToolContext:
    """The live editing context handed to a tool for one interaction.

    Attributes:
        buffer: The active layer buffer being edited.
        active_color: The active RGBA colour (the display colour of the picked
            palette entry; used for previews in every mode).
        active_index: The active palette index used as the paint value in an
            indexed buffer — the palette panel selects it (REQ-P3-UI-014). In an
            RGBA buffer it is ignored (``active_color`` is written instead).
        undo_stack: The active document's undo stack.
        scene: The canvas scene (for dirty-rect refresh + previews).
        set_active_color: Callback the picker uses to set the active colour.
        selection: The active selection mask, or ``None`` (whole buffer, CL-5).
        set_selection: Callback a selection tool uses to set the active mask.
        symmetry_axis: The active symmetry axis for live mirror drawing (P2-UI-011).
        symmetry_pos: Optional mirror centre; ``None`` = canvas centre (CL-9).
        pixel_perfect: Whether freehand strokes are elbow-cleaned (P2-UI-012).
        tiled: Whether edits wrap on the torus (P2-UI-015).
        snap: Whether shape/selection endpoints snap to the pixel grid (P2-UI-013).
        modifiers: Keyboard modifiers at the interaction's press (combine modes).
    """

    def __init__(
        self,
        buffer: PixelBuffer,
        active_color: RGBA,
        undo_stack: QUndoStack,
        scene: CanvasScene,
        set_active_color: Callable[[RGBA], None],
        *,
        active_index: int = 0,
        selection: Optional[SelectionMask] = None,
        set_selection: Optional[Callable[[Optional[SelectionMask]], None]] = None,
        symmetry_axis: SymmetryAxis = SymmetryAxis.NONE,
        symmetry_pos: Optional[Tuple[int, int]] = None,
        pixel_perfect: bool = False,
        tiled: bool = False,
        snap: bool = False,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        self.buffer = buffer
        self.active_color = active_color
        self.active_index = active_index
        self.undo_stack = undo_stack
        self.scene = scene
        self.set_active_color = set_active_color
        self.selection = selection
        self.set_selection = set_selection
        self.symmetry_axis = symmetry_axis
        self.symmetry_pos = symmetry_pos
        self.pixel_perfect = pixel_perfect
        self.tiled = tiled
        self.snap = snap
        self.modifiers = modifiers

    def paint_value(self) -> PixelValue:
        """Return the value a paint tool writes for the active buffer mode.

        Indexed buffers are painted by the active palette *index* (paint-by-index,
        REQ-P3-UI-014); RGBA buffers are painted with the active RGBA colour. The
        mode decision stays a thin binding — no colour maths lives here (S11)."""
        if self.buffer.mode is ColorMode.INDEXED:
            return self.active_index
        return self.active_color


class Tool:
    """Abstract active-tool controller (one active at a time, REQ-P1-UI-011)."""

    #: Stable identifier used by the toolbar/shortcuts.
    tool_id: str = "tool"

    def on_press(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle a left-button press at floored pixel ``(x, y)``."""

    def on_move(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle a left-drag move at floored pixel ``(x, y)``."""

    def on_release(self, x: int, y: int, ctx: ToolContext) -> None:
        """Handle the left-button release that completes the interaction."""
