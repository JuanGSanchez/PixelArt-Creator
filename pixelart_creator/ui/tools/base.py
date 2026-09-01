# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
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

from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Set, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QUndoStack

from pixelart_creator.logic import drawing
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.history import PixelChange, PixelEdit
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer, PixelValue
from pixelart_creator.logic.selection import SelectionMask
from pixelart_creator.logic.symmetry import SymmetryAxis, mirror
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.commands import PaintCommand

if TYPE_CHECKING:
    from pixelart_creator.ui.tools.floating_move import FloatingMoveController

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
        """Snapshot `buffer` so later diffs can build the minimal reversible edit."""
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
        invalidate: Optional[Callable[[], None]] = None,
        *,
        target: Optional[EditTarget] = None,
    ) -> Optional[PaintCommand]:
        """Build a :class:`PaintCommand`, or ``None`` if nothing changed (CL-12/-14).

        ``invalidate`` is the D4 cache-safety hook (``scene.invalidate_group_caches``)
        forwarded to the command so a group's flatten cache cannot serve a stale
        composite after the edit; ``None`` for a non-composited target.

        ``target`` is where this edit landed (``ctx.target``, plan §8.2,
        `REQ-P10-UI-025`) — the frame + layer track the branch-recording seam
        attributes the resulting op to. Every ``ui/tools/`` caller
        (``fill.py``, ``line.py``, ``pencil.py`` — all three commit paths —,
        ``shape_base.py``) passes ``target=ctx.target`` explicitly; ``None``
        stays the honest default only for a caller that genuinely has no view
        context (e.g. a headless test building a bare ``Stroke``), never a
        guess (plan §8.2's honest-empty channel; the "unminted layer" sentinel
        is ``ctx.target`` being ``None`` in the first place — see
        ``Canvas_View._make_edit_target``).

        ``record_trace``/``document`` (the *who does the recording* half of
        `REQ-P10-UI-025`, as opposed to *what it is attributed to*) are
        deliberately **not** parameters here: attaching them to every one of
        the six drawing tools' `PaintCommand`/`LogicCommand` construction call
        sites individually would touch files outside this dispatch's write set
        (``ui/tools/{fill,line,pencil,shape_base,dither_tool}.py``,
        ``ui/tools/floating_move.py``). Instead ``ui/canvas_view.py`` hands
        every tool an undo stack that auto-binds the active recording sink
        onto whatever command a tool pushes, *after* construction (see
        ``Canvas_View._RecordingUndoStack`` and
        ``PaintCommand``/``LogicCommand.bind_recording`` in ``ui/commands.py``)
        — one interception point instead of six edited call sites, with the
        exact same observable effect.
        """
        changes: List[PixelChange] = []
        for x, y in sorted(self._touched):
            old = self._before.get_pixel(x, y)
            new = self._buffer.get_pixel(x, y)
            if old != new:
                changes.append((x, y, old, new))
        if not changes:
            return None
        edit = PixelEdit(self._buffer, changes, label=label, target=target)
        return PaintCommand(
            edit, refresh, self.touched_rect(), text=label, invalidate=invalidate
        )


class ToolContext:
    """The live editing context handed to a tool for one interaction.

    Attributes:
        buffer: The active layer buffer being edited.
        active_color: The active RGBA colour (the display colour of the picked
            palette entry; used for previews in every mode).
        active_index: The active palette index used as the paint value in an
            indexed buffer — the palette panel selects it (REQ-P3-UI-014). In an
            RGBA buffer it is ignored (``active_color`` is written instead).
        undo_stack: The active document's undo stack. In production
            ``ui/canvas_view.py`` hands every tool a thin recording wrapper
            around the real ``QUndoStack`` — duck-typed to the same ``push``
            interface, see ``Canvas_View._RecordingUndoStack`` — that attaches
            the active branch's record-trace callback + live ``Document`` to
            every pushed command (T-DRAW-01, `REQ-P10-UI-025`) so every drawing
            tool's commit records, without any tool constructing its
            ``PaintCommand``/``LogicCommand`` any differently than it already
            does. Declared as ``QUndoStack`` here (the interface every real
            caller besides the canvas view still passes) rather than a narrower
            Protocol, so the wrapper's use is confined to and documented at its
            one construction site instead of rippling this file's type into the
            other ``ui/tools/`` modules' own ``QUndoStack``-typed contracts
            (e.g. ``floating_move.LiftContext``) outside this dispatch's write
            set.
        scene: The canvas scene (for dirty-rect refresh + previews).
        target: Where an edit through this context lands — the active frame
            index and the active node's stable ``layer_id`` (``EditTarget``),
            or ``None`` when the active layer has no minted id yet
            (``layer_id == 0``, the documented "unminted" sentinel,
            ``logic/document.py:264``). Consumed by ``Stroke.to_command`` to
            attribute the resulting op for branch recording (`REQ-P10-UI-025`,
            plan §8.2). The context is read from the live ``Document`` here —
            never computed — because a ``PixelBuffer`` does not know which
            layer or frame it belongs to (Article I; plan §8.2).
        set_active_color: Callback the picker uses to set the active colour.
        resolve_palette_color: Callback the picker uses to resolve an indexed
            pixel's palette index to its RGBA colour (REQ-P1-UI-016). Returns
            ``None`` when the index has no matching palette entry (e.g. a
            stale pixel left over from a since-shrunk palette) so the picker
            can no-op instead of raising. ``None`` outside a canvas view (a
            bare ``ToolContext`` built by a test) — the picker then simply
            cannot resolve an indexed pick, matching the pre-existing RGBA-only
            behaviour.
        selection: The active selection mask, or ``None`` (whole buffer, CL-5).
        set_selection: Callback a selection tool uses to set the active mask.
        symmetry_axis: The active symmetry axis for live mirror drawing (P2-UI-011).
        symmetry_pos: Optional mirror centre; ``None`` = canvas centre (CL-9).
        pixel_perfect: Whether freehand strokes are elbow-cleaned (P2-UI-012).
        tiled: Whether edits wrap on the torus (P2-UI-015).
        snap: Whether shape/selection endpoints snap to the pixel grid (P2-UI-013).
        modifiers: Keyboard modifiers at the interaction's press (combine modes).
        floating_controller: The view's floating move/copy controller — a
            selection tool starts a float through it when a press lands inside the
            active mask (REQ-P2-UI-030..034). ``None`` outside a canvas view.
    """

    def __init__(
        self,
        buffer: PixelBuffer,
        active_color: RGBA,
        undo_stack: QUndoStack,
        scene: CanvasScene,
        set_active_color: Callable[[RGBA], None],
        *,
        target: Optional[EditTarget],
        resolve_palette_color: Optional[Callable[[int], Optional[RGBA]]] = None,
        active_index: int = 0,
        selection: Optional[SelectionMask] = None,
        set_selection: Optional[Callable[[Optional[SelectionMask]], None]] = None,
        symmetry_axis: SymmetryAxis = SymmetryAxis.NONE,
        symmetry_pos: Optional[Tuple[int, int]] = None,
        pixel_perfect: bool = False,
        tiled: bool = False,
        snap: bool = False,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
        floating_controller: Optional["FloatingMoveController"] = None,
    ) -> None:
        """Bind the buffer, colour/index, undo stack, scene, and interaction state."""
        self.buffer = buffer
        self.active_color = active_color
        self.active_index = active_index
        self.undo_stack = undo_stack
        self.scene = scene
        self.target = target
        self.set_active_color = set_active_color
        self.resolve_palette_color = resolve_palette_color
        self.selection = selection
        self.set_selection = set_selection
        self.symmetry_axis = symmetry_axis
        self.symmetry_pos = symmetry_pos
        self.pixel_perfect = pixel_perfect
        self.tiled = tiled
        self.snap = snap
        self.modifiers = modifiers
        self.floating_controller = floating_controller

    def paint_value(self) -> PixelValue:
        """Return the value a paint tool writes for the active buffer mode.

        Indexed buffers are painted by the active palette *index* (paint-by-index,
        REQ-P3-UI-014); RGBA buffers are painted with the active RGBA colour. The
        mode decision stays a thin binding — no colour maths lives here (S11).
        """
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
