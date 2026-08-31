"""Canvas view — navigation, paint dispatch, right-click seam (D4/D5/D6).

``Canvas_View`` provides zoom (fit-to-view … ``ZOOM_MAX``, cursor-anchored,
``SCALE_FACTOR`` step, ``ZOOM_PRESET_STOPS`` keyboard) (CL-1/-2/-15), pan
(middle-drag / Space+left-drag, never painting) (CL-3), left-click/drag paint via
the active tool with floored coordinates (CL-9/-12), a per-pixel grid threshold
(CL-4), and a replaceable right-click menu **seam** (CL-8). It sets
``MinimalViewportUpdate`` (D4) and, when ``OPENGL_VIEWPORT_ENABLED`` and a GL
context is available, a ``QOpenGLWidget`` viewport with a raster fallback for
headless/offscreen runs (D6). Rendering stays nearest-neighbour, AA off.

No domain logic lives here: the view maps events to floored pixels and delegates
painting to the tool controllers (Article I).
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QContextMenuEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QResizeEvent,
    QTransform,
    QUndoCommand,
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QMenu, QWidget

from pixelart_creator.logic.color import BLACK, RGBA
from pixelart_creator.logic.constants import (
    CLICK_DRAG_THRESHOLD_PX,
    DEFAULT_SNAP_TOLERANCE_PX,
    OPENGL_VIEWPORT_ENABLED,
    SCALE_FACTOR,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_PRESET_STOPS,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.edit_trace import EditTarget
from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.logic.guides import (
    Guide,
    GuideOrientation,
    screen_tolerance_to_doc,
)
from pixelart_creator.logic.selection import SelectionMask
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.commands import RecordTraceCallback
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay
from pixelart_creator.ui.perspective_grid_overlay import Perspective_Grid_Overlay
from pixelart_creator.ui.tools.base import Tool, ToolContext
from pixelart_creator.ui.tools.floating_move import FloatingMoveController

Coord = Tuple[int, int]

#: Platform name reported by Qt when running without a windowing system.
_OFFSCREEN_PLATFORM = "offscreen"


def _viewport_update_mode_for(
    widget: QWidget,
) -> QGraphicsView.ViewportUpdateMode:
    """Return the update mode Qt documents as correct for ``widget`` (REQ-CGS-UI-002).

    Qt 6 states verbatim that ``FullViewportUpdate`` "is the preferred update
    mode for viewports that do not support partial updates, such as
    QOpenGLWidget", and that ``MinimalViewportUpdate`` "is QGraphicsView's
    default mode" — Qt does not switch it for you when a GL viewport is
    installed. Checked via ``inherits`` (a ``QObject`` string test) rather
    than an ``isinstance`` against ``PySide6.QtOpenGLWidgets.QOpenGLWidget``,
    so this module-level helper stays import-free: the GL module is only ever
    imported inside :meth:`Canvas_View._install_viewport` and
    :meth:`Canvas_View.setViewport`, never at module scope (a headless run
    with no system GL library must not fail merely importing ``ui/``).
    """
    if widget.inherits("QOpenGLWidget"):
        return QGraphicsView.ViewportUpdateMode.FullViewportUpdate
    return QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate


class _RecordingUndoStack:
    """Auto-attaches the view's active branch-recording sink to every push.

    Every one of the six ``ui/tools/`` drawing controllers (pencil, line, fill,
    the shared shape base, dither, floating-move) already builds its own
    ``PaintCommand``/``LogicCommand`` and calls exactly one thing on
    ``ctx.undo_stack``: ``push(command)`` (confirmed by grep across the package —
    no other member of the real ``QUndoStack`` is ever reached through a
    :class:`~pixelart_creator.ui.tools.base.ToolContext`). Standing between that
    call and the real stack lets this one interception point call the pushed
    command's own ``bind_recording`` (``ui/commands.py`` — present on
    ``PaintCommand`` and every ``LogicCommand``) with the view's current
    :data:`~pixelart_creator.ui.commands.RecordTraceCallback` and live
    :class:`~pixelart_creator.logic.document.Document` **before** the real
    ``QUndoStack.push`` fires the command's first ``redo()`` (T-DRAW-01,
    `REQ-P10-UI-025`) — so every drawing tool's commit records on a branch,
    without editing any of those six controllers' own command-construction call
    sites, which sit outside this dispatch's write set (``ui/tools/base.py``,
    ``ui/canvas_view.py``, ``ui/commands.py``, ``ui/branching_panel.py`` only).

    Duck-typed to ``QUndoStack``'s ``push`` signature only; every other member a
    caller might want (``undo``, ``redo``, ``isClean``, …) stays on the real
    stack the view already keeps and exposes elsewhere — this wrapper is never
    substituted for the document tab's own ``QUndoStack`` (``main_window.py``'s
    ``record.stack``), only for the one reference a :class:`ToolContext` is
    built with.
    """

    def __init__(self, view: "Canvas_View") -> None:
        """Bind to ``view``, whose current stack/recording sink is read live."""
        self._view = view

    def push(self, command: QUndoCommand) -> None:
        """Bind the active recording sink onto ``command``, then push it for real."""
        bind = getattr(command, "bind_recording", None)
        if bind is not None:
            bind(self._view._record_trace, self._view._recording_document)
        self._view._undo_stack.push(command)


class Canvas_View(QGraphicsView):
    """Interactive view over a :class:`CanvasScene`."""

    #: Emitted with the current zoom scale after any zoom change.
    zoomChanged = Signal(float)
    #: Emitted with the buffer ``(x, y)`` when the canvas is right-clicked (seam).
    rightClicked = Signal(int, int)
    #: Emitted with the picked RGBA tuple when the colour-picker sets a colour.
    colorPicked = Signal(object)
    #: Emitted ``(is_active, is_copy)`` when a floating move/copy state changes
    #: (drives the shell's copy-mode status hint, REQ-P2-UI-032/-036).
    floatingStateChanged = Signal(bool, bool)
    #: Emitted when a paint/mask-edit stroke is refused because the active
    #: layer is locked (D-05); the shell surfaces a "layer is locked" notice.
    lockedLayerEditRejected = Signal()
    #: Emitted when a left-click lands outside the active document's bounds
    #: (FIX 5, 2026-08-24 field defect): a click there must not arm a stroke,
    #: and must not fail silently — the shell surfaces a notice, following the
    #: ``lockedLayerEditRejected`` precedent exactly.
    outOfDocumentClickRejected = Signal()
    #: Emitted when a paint/mask-edit is refused because the active layer is a
    #: REFERENCE or SMART layer (REQ-P3-UI-006 clause 5: non-editable targets
    #: are three classes, not two — locked, reference, and smart — and every
    #: one of them must be surfaced, never silently swallowed). Distinct from
    #: ``lockedLayerEditRejected`` so the shell can show the right notice;
    #: ``is_active_editable()`` returns ``False`` for all three classes, and
    #: this signal covers the two this view previously dropped on the floor.
    nonEditableLayerEditRejected = Signal()
    #: Emitted when a tool ran (the guards passed) but produced no pixel
    #: change — e.g. a flood fill on a region that already holds the picked
    #: colour (REQ-P1-UI-014), or a pencil placed on a pixel that already
    #: holds it — so no undo entry was pushed. An explicit, deliberate gesture
    #: (a completed colour-hub pick, REQ-P3-UI-006 clause 6) must never answer
    #: with silence even when it changed nothing.
    toolRunNoChange = Signal()

    #: The three selection tools whose Shift/Alt modifiers stay the shipped
    #: add/subtract combine gesture (REQ-IS-UI-015) — Shift+drag pans for
    #: every other tool. Mirrors ``Main_Window._SELECTION_ENTRY_TOOL_IDS``.
    _SELECTION_TOOL_IDS = frozenset({"select_rect", "select_lasso", "select_wand"})

    def __init__(
        self,
        scene: CanvasScene,
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Create the view over ``scene`` bound to ``undo_stack``."""
        super().__init__(scene, parent)
        self._scene = scene
        self._undo_stack = undo_stack
        # Branch-recording sink for the drawing tools (T-DRAW-01, `REQ-P10-UI-025`):
        # bound externally via `set_recording` (mirrors `set_undo_stack`'s pattern);
        # `None` on a tab whose document has no active branch session attached,
        # in which case `_RecordingUndoStack.push` binds `None` and every
        # `PaintCommand`/`LogicCommand`'s own `_fire_record_trace` stays the
        # documented no-op (``ui/commands.py``).
        self._record_trace: Optional[RecordTraceCallback] = None
        self._recording_document: Optional[Document] = None
        #: The wrapper every :class:`~pixelart_creator.ui.tools.base.ToolContext`
        #: is actually built with (see :class:`_RecordingUndoStack`); reads
        #: ``self._undo_stack``/``self._record_trace``/``self._recording_document``
        #: live at each push, so `set_undo_stack`/`set_recording` need not rebuild it.
        self._recording_stack = _RecordingUndoStack(self)
        self._tool: Optional[Tool] = None
        self._active_color: RGBA = BLACK
        self._active_index: int = 0
        self._zoom = 1.0
        self._panning = False
        #: A middle press awaiting the click/drag verdict (REQ-IS-UI-011):
        #: ``True`` between a middle press and either its release under
        #: ``CLICK_DRAG_THRESHOLD_PX`` (a click) or its promotion to
        #: ``_panning`` once the cursor travels past the threshold (a drag).
        self._middle_pending = False
        self._space_held = False
        self._drawing = False
        self._pan_origin = QPoint()
        #: The persisted Favourites model a plain wheel notch / unmodified
        #: middle click travel (REQ-IS-UI-008/-012); ``None`` until the shell
        #: binds one via :meth:`set_favourites_model` (T-21).
        self._favourites: Optional[Favourites] = None
        self._ctx: Optional[ToolContext] = None
        self._menu_hook: Optional[Callable[[int, int], None]] = None
        # File-drop routing seam (CF: T-12) — a real drag/drop delivered to
        # QGraphicsView's viewport is otherwise translated into a
        # QGraphicsSceneDragDropEvent and swallowed by the scene (no item
        # accepts it), so it never reaches Main_Window.dropEvent. Only a
        # URL-carrying drag is taken over here and handed to this router; every
        # other drag keeps QGraphicsView's own scene-forwarding behaviour.
        self._drop_router: Optional[Callable[[List[str]], None]] = None
        self.setAcceptDrops(True)
        # One floating move/copy controller per view (REQ-P2-UI-030..034); it
        # owns the active float so release / Enter / tool-switch can all commit it.
        self._floating_controller = FloatingMoveController()
        self._floating_controller.state_changed = self._emit_floating_state
        # Phase-2 drawing modes / active selection (bound into each ToolContext).
        self._symmetry_axis: SymmetryAxis = SymmetryAxis.NONE
        #: Live mirror-centre override fed to ``logic.symmetry.mirror`` via each
        #: stroke's :class:`ToolContext` (D-28/CF-93); ``None`` keeps the shipped
        #: canvas-centre default. Fed by the shell's Symmetry_Panel.
        self._symmetry_pos: Optional[Tuple[int, int]] = None
        self._pixel_perfect = False
        self._tiled = False
        self._snap = False
        self._selection: Optional[SelectionMask] = None
        # Phase-9 aid seams consulted at the cursor level (D-08 precedence: guides
        # > perspective > iso > rectangular; D-11 guide drag/remove). Bound by the
        # shell per active tab (main_window._create_tab_aids /
        # _bind_visual_aids_to_active); None until a tab has bound its aids.
        self._guides_overlay: Optional[Guides_Rulers_Overlay] = None
        self._iso_overlay: Optional[Iso_Grid_Overlay] = None
        self._perspective_overlay: Optional[Perspective_Grid_Overlay] = None
        #: The guide currently being dragged (D-11), or ``None``.
        self._guide_drag: Optional[Guide] = None
        #: Raw (pre-snap) scene point at the start of the current stroke — the
        #: perspective direction-lock anchor (``logic.grids.perspective_snap``).
        self._stroke_anchor: Optional[Tuple[float, float]] = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontSavePainterState, True
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName(self.tr("Canvas"))
        self.setAccessibleDescription(
            self.tr("Pixel canvas: left-click to paint, middle-drag to pan")
        )
        self._install_viewport()
        # The pan margin is re-derived whenever the scene's OWN rect changes
        # (document load/resize, tiled-mode toggle) so it never goes stale
        # against a superseded document size (REQ-CGS-UI-009).
        self._scene.sceneRectChanged.connect(self._on_scene_rect_changed)
        self._apply_pan_margin()

    # -- pan headroom (REQ-CGS-UI-009) -------------------------------------

    def _on_scene_rect_changed(self, _rect: QRectF) -> None:
        """Re-derive the view's inflated pan-margin rect.

        Triggered after the scene's own rect changes (document load/resize,
        tiled-mode toggle), so the margin never goes stale against a
        superseded document size (REQ-CGS-UI-009).
        """
        self._apply_pan_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        """Re-derive the pan margin.

        Half a viewport in scene units moves with the viewport's own size.
        """
        super().resizeEvent(event)
        self._apply_pan_margin()

    # -- viewport (D6) ----------------------------------------------------

    def _install_viewport(self) -> None:
        """Use a GL viewport on desktop; fall back to raster headless (D6)."""
        if not OPENGL_VIEWPORT_ENABLED:
            return
        if QGuiApplication.platformName() == _OFFSCREEN_PLATFORM:
            return  # headless/offscreen: keep the default raster viewport.
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget

            self.setViewport(QOpenGLWidget())
        except Exception:  # noqa: BLE001 - any GL failure ⇒ raster fallback.
            pass

    def setViewport(self, widget: QWidget, /) -> None:  # noqa: N802 (Qt override)
        """Match the update mode to whichever viewport is actually installed.

        ``QAbstractScrollArea::setViewport`` is non-virtual, so Qt's C++
        constructor installs the DEFAULT viewport directly and never routes
        through this Python override — the ``MinimalViewportUpdate`` set at
        construction (:216-218, above) is the base case for THAT viewport and
        is left untouched here. This override only fires for a viewport
        installed through an explicit ``setViewport(...)`` call: this view's
        own ``_install_viewport`` GL branch, and any other caller (including
        this fix's regression test) that calls it directly.

        Qt 6 documents ``FullViewportUpdate`` as required for a viewport that
        "does not support partial updates, such as QOpenGLWidget" — see
        :func:`_viewport_update_mode_for` (REQ-CGS-UI-002); every other
        viewport keeps ``MinimalViewportUpdate``, matching every drawing
        tool's partial ``refresh_rect`` commit path (REQ-CGS-UI-001).
        """
        super().setViewport(widget)
        self.setViewportUpdateMode(_viewport_update_mode_for(widget))
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
        except Exception:  # noqa: BLE001 - no system GL module ⇒ nothing to do.
            return
        if isinstance(widget, QOpenGLWidget):
            # Defensive only — NOT Qt-documented like the mode switch above.
            # Forum-level evidence only (the research pass could not read the
            # relevant Qt bug-ticket bodies): applied alongside the documented
            # FullViewportUpdate mode in case some path still attempts a
            # partial repaint directly on the GL widget itself.
            widget.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)

    # -- external wiring --------------------------------------------------

    def set_tool(self, tool: Tool) -> None:
        """Set the active tool controller (exactly one active, REQ-P1-UI-011)."""
        self._tool = tool

    def active_tool(self) -> Optional[Tool]:
        """Return the active tool controller."""
        return self._tool

    def set_favourites_model(self, favourites: Favourites) -> None:
        """Bind the persisted Favourites model a plain wheel notch / an
        unmodified middle click travel (REQ-IS-UI-008/-012, T-21)."""
        self._favourites = favourites

    def floating_controller(self) -> FloatingMoveController:
        """Return this view's floating move/copy controller."""
        return self._floating_controller

    def commit_active_float(self) -> None:
        """Commit any active floating move before a tool/tab switch (REQ-P2-UI-033)."""
        if self._floating_controller.is_active():
            self._floating_controller.commit()

    def _emit_floating_state(self, active: bool, copy: bool) -> None:
        """Relay the controller's state change to the shell (status hint)."""
        self.floatingStateChanged.emit(active, copy)

    def set_active_color(self, color: RGBA) -> None:
        """Set the active colour subsequent paint tools use (CL-10)."""
        self._active_color = color

    def active_color(self) -> RGBA:
        """Return the active colour."""
        return self._active_color

    def set_active_index(self, index: int) -> None:
        """Set the active palette index painted on an indexed buffer (P3-UI-014)."""
        self._active_index = int(index)

    def active_index(self) -> int:
        """Return the active palette index used for paint-by-index."""
        return self._active_index

    def set_undo_stack(self, undo_stack: QUndoStack) -> None:
        """Rebind the view to a different document's undo stack (tab switch)."""
        self._undo_stack = undo_stack

    def set_recording(
        self,
        record_trace: Optional[RecordTraceCallback],
        document: Optional[Document],
    ) -> None:
        """Bind the active branch-recording sink (T-DRAW-01, `REQ-P10-UI-025`).

        The caller (``ui/main_window.py``, outside this dispatch's write set)
        supplies its ``Branching_Session.record_traces`` and the active tab's
        live ``Document`` here — mirroring how it already calls
        :meth:`set_undo_stack` on tab construction, tab switch, and after a
        branch switch/merge (``ui/branching_panel.py``'s
        ``documentSwitched``/``activeBranchChanged`` handling). Every drawing
        tool's push routes through :class:`_RecordingUndoStack`, which reads
        these two values live, so calling this again (e.g. on
        ``activeBranchChanged``) takes effect on the very next stroke — no
        rebuild of the context or the wrapper needed. ``(None, None)`` is the
        safe default this view starts with (no branching session attached yet);
        every drawing tool then records nothing, exactly the documented
        no-op (``ui/commands.py``'s ``_fire_record_trace``), never a guess.
        """
        self._record_trace = record_trace
        self._recording_document = document

    def set_menu_hook(self, hook: Optional[Callable[[int, int], None]]) -> None:
        """Register a replaceable right-click menu hook (Phase-3 seam, CL-8)."""
        self._menu_hook = hook

    def set_drop_router(self, router: Optional[Callable[[List[str]], None]]) -> None:
        """Register the window's dropped-file router (CF: T-12, REQ-DDI-UI-001).

        ``router`` receives the local file paths of a URL drag delivered to
        THIS viewport — the same routing ``Main_Window.dropEvent`` uses, so a
        drop landing on the canvas is handled identically to one landing
        anywhere else on the window.
        """
        self._drop_router = router

    def set_grid_enabled(self, enabled: bool) -> None:
        """Toggle the per-pixel grid overlay (delegates to the scene, CL-4)."""
        self._scene.set_grid_enabled(enabled)

    # -- Phase-9 aid seams (D-08/D-09/D-11) -------------------------------

    def set_guides_overlay(self, overlay: Optional[Guides_Rulers_Overlay]) -> None:
        """Bind the active tab's guides/rulers controller (D-08 cursor snap, D-11)."""
        self._guides_overlay = overlay

    def set_iso_overlay(self, overlay: Optional[Iso_Grid_Overlay]) -> None:
        """Bind the active tab's isometric-grid overlay (D-08 cursor snap)."""
        self._iso_overlay = overlay

    def set_perspective_overlay(
        self, overlay: Optional[Perspective_Grid_Overlay]
    ) -> None:
        """Bind the active tab's perspective-grid overlay (D-08 cursor snap)."""
        self._perspective_overlay = overlay

    # -- Phase-2 drawing modes -------------------------------------------

    def set_symmetry_axis(self, axis: SymmetryAxis) -> None:
        """Set the live mirror-drawing axis (REQ-P2-UI-011)."""
        self._symmetry_axis = axis

    def symmetry_axis(self) -> SymmetryAxis:
        """Return the active symmetry axis."""
        return self._symmetry_axis

    def set_symmetry_pos(self, pos: Optional[Tuple[int, int]]) -> None:
        """Set the mirror-centre override (D-28); ``None`` = canvas centre."""
        self._symmetry_pos = pos

    def symmetry_pos(self) -> Optional[Tuple[int, int]]:
        """Return the active mirror-centre override, or ``None``."""
        return self._symmetry_pos

    def set_pixel_perfect(self, enabled: bool) -> None:
        """Toggle pixel-perfect elbow cleaning for freehand strokes (P2-UI-012)."""
        self._pixel_perfect = bool(enabled)

    def set_tiled(self, enabled: bool) -> None:
        """Toggle torus-wrapped tiled painting for freehand strokes (P2-UI-015)."""
        self._tiled = bool(enabled)

    def set_snap_enabled(self, enabled: bool) -> None:
        """Toggle endpoint snapping to the pixel grid (REQ-P2-UI-013)."""
        self._snap = bool(enabled)

    def reassert_no_antialiasing(self) -> None:
        """Re-lock the AA-off render hints (REQ-P2-UI-014; REQ-P1-UI-001).

        The canvas is nearest-neighbour with anti-aliasing and smooth-pixmap
        transform disabled at every zoom. This re-asserts that guarantee (the
        toggle stays effectively locked on) whenever the shell touches it.
        """
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

    # -- active selection (REQ-P2-UI-004..008) ---------------------------

    def set_selection(self, mask: Optional[SelectionMask]) -> None:
        """Set the active selection mask and refresh the overlay."""
        self._selection = mask
        self._scene.set_selection_mask(mask)

    def active_selection(self) -> Optional[SelectionMask]:
        """Return the active selection mask, or ``None``."""
        return self._selection

    def clear_selection(self) -> None:
        """Deselect (empty the active mask) and clear the overlay."""
        self.set_selection(None)

    # -- zoom (CL-1/-2/-15) ----------------------------------------------

    def zoom(self) -> float:
        """Return the current zoom scale."""
        return self._zoom

    def _content_rect(self) -> QRectF:
        """Return the document's own rect — never the view's inflated pan margin.

        This is the scene's ``sceneRect()`` (the document, or the 3x3 tiled-mode
        area under ``set_tiled``): ``_fit_zoom`` reads it to fit the whole
        document, and every off-canvas semantic test (guide-drop) reads it too.
        The VIEW carries a separately-inflated scene rect for pan headroom
        (``_apply_pan_margin``); that inflated rect is never substituted here.
        """
        return self._scene.sceneRect()

    def _fit_zoom(self) -> float:
        rect = self._content_rect()
        vp = self.viewport().rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return 1.0
        if vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        fit = min(vp.width() / rect.width(), vp.height() / rect.height())
        return min(fit, ZOOM_MAX)

    def _clamp_zoom(self, z: float) -> float:
        # ZOOM_MIN is a flat, absolute floor (user ruling 2026-08-25;
        # `logic/constants.py`'s ZOOM_MIN docstring). Below 1:1 the canvas is
        # minified by a painter with smoothing off (nearest-neighbour point
        # sampling), so an isolated pixel between sample points is not drawn at
        # all until the sampling grid happens to re-align — "my drawing was
        # invisible until I moved something". `fit()` is clamped by this same
        # floor, so a document larger than the viewport lands at exactly 1.0
        # rather than a fractional whole-grid fit; it is viewed by panning
        # instead (the accepted trade-off, put to the user and accepted). This
        # supersedes the 2026-08-24 `min(ZOOM_MIN, fit_zoom)` reasoning, which
        # was sound for grid visibility alone but did not account for the
        # point-sampling loss below 1:1.
        return max(ZOOM_MIN, min(z, ZOOM_MAX))

    def _apply_pan_margin(self) -> None:
        """Inflate the VIEW's own scene rect so every corner stays reachable.

        Sets ``self.setSceneRect(...)`` (the view's scrollable range) to the
        document's :meth:`_content_rect` inflated by half a viewport in scene
        units on every side, plus one screen pixel of slack (also converted to
        scene units) so Qt's scrollbar-range rounding does not fall one pixel
        short of the far corner. The scene's OWN rect (``self._scene.sceneRect()``,
        read by :meth:`_fit_zoom` and rewritten by tiled mode) is never touched
        here — only the view's, via the base-class ``setSceneRect`` override
        QGraphicsView provides for exactly this purpose.

        Half a viewport in scene units is not a fixed pixel count: it scales
        with the live viewport size and the current zoom, so it is computed
        fresh here rather than hoisted into a constant that would be correct
        at only one window size and one zoom.
        """
        rect = self._content_rect()
        vp = self.viewport().rect()
        zoom = self._zoom if self._zoom > 0 else 1.0
        margin_x = vp.width() / (2 * zoom) + 1.0 / zoom
        margin_y = vp.height() / (2 * zoom) + 1.0 / zoom
        self.setSceneRect(rect.adjusted(-margin_x, -margin_y, margin_x, margin_y))

    def set_zoom(self, z: float) -> None:
        """Set an absolute zoom (clamped), anchored on the view centre."""
        target = self._clamp_zoom(z)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        transform = QTransform()
        transform.scale(target, target)
        self.setTransform(transform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom = target
        self.zoomChanged.emit(target)
        self._apply_pan_margin()  # the pan headroom scales with zoom too
        self._scene.recomposite_exposed()  # zoom-out may expose stale area (D2)

    def fit(self) -> None:
        """Zoom so the whole scene fits the viewport (the zoom minimum)."""
        self.set_zoom(self._fit_zoom())

    def zoom_in(self) -> None:
        """Snap up to the next keyboard preset stop (CL-2)."""
        for stop in ZOOM_PRESET_STOPS:
            if stop > self._zoom + 1e-6:
                self.set_zoom(stop)
                return
        self.set_zoom(ZOOM_MAX)

    def zoom_out(self) -> None:
        """Snap down to the previous keyboard preset stop (CL-2)."""
        for stop in reversed(ZOOM_PRESET_STOPS):
            if stop < self._zoom - 1e-6:
                self.set_zoom(stop)
                return
        self.fit()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        """``Shift``+wheel zooms (REQ-IS-UI-009); plain wheel travels
        Favourites (REQ-IS-UI-008, T-21 — displaces the zoom that plain wheel
        performed until 2026-08-31)."""
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._zoom_wheel(event)
        else:
            self._favourites_wheel(event)

    def _zoom_wheel(self, event: QWheelEvent) -> None:
        """Geometric cursor-anchored zoom by the ``SCALE_FACTOR`` step (CL-2/-15).

        Relocated from plain wheel to ``Shift``+wheel (REQ-IS-UI-009); the
        step, anchor, floor and ceiling are otherwise unmodified.
        """
        factor = 1.0 + SCALE_FACTOR
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        target = self._clamp_zoom(self._zoom * factor)
        if abs(target - self._zoom) < 1e-9:
            event.accept()
            return
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        applied = target / self._zoom
        self.scale(applied, applied)
        self._zoom = target
        self.zoomChanged.emit(target)
        self._apply_pan_margin()  # the pan headroom scales with zoom too
        self._scene.recomposite_exposed()  # zoom-out may expose stale area (D2)
        event.accept()

    def _favourites_wheel(self, event: QWheelEvent) -> None:
        """Plain wheel steps the Favourites cursor (REQ-IS-UI-008).

        Wheel down **advances**, wheel up **retreats** — ``CL-IS-02``, a
        flagged assumption chosen to match list-scroll convention and cheap
        to reverse if the user disagrees. A silent no-op with no favourites
        bound or an empty list (never zooms, never errors).
        """
        if self._favourites is None:
            event.accept()
            return
        if event.angleDelta().y() < 0:
            color = self._favourites.advance()
        else:
            color = self._favourites.retreat()
        if color is not None:
            self._on_color_picked(color)
        event.accept()

    # -- lazy off-screen recomposite (D2 follow-up) ----------------------

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # noqa: N802 (Qt override)
        """Refresh any off-screen-stale composite scrolled into view (D2).

        An attribute change recomposites only the visible viewport
        (``CanvasScene.refresh_visible``); the rest of the canvas is marked stale
        and brought up to date here as it pans/zooms into view, so the flattened
        composite stays correct without ever recompositing the whole 33 Mpx stack.
        A cheap no-op when nothing is stale.
        """
        super().scrollContentsBy(dx, dy)
        self._scene.recomposite_exposed()

    # -- keyboard (Space pan modifier) -----------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Commit/cancel a floating move on Enter/Escape; else track Space-pan."""
        # A live floating move commits on Enter/Return and cancels on Escape
        # (REQ-P2-UI-033/-034); these keys are inert when no float is active.
        if self._floating_controller.is_active():
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._floating_controller.commit()
                event.accept()
                return
            if key == Qt.Key.Key_Escape:
                self._floating_controller.cancel()
                event.accept()
                return
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Clear the Space-pan modifier and restore the cursor on Space release."""
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self.viewport().unsetCursor()
        super().keyReleaseEvent(event)

    # -- mouse: paint / pan / seam ---------------------------------------

    def _pixel_at(self, event: QMouseEvent) -> Coord:
        pt = self.mapToScene(event.position().toPoint())
        snapped = self._snap_scene_point(pt)
        return math.floor(snapped.x()), math.floor(snapped.y())

    def _snap_scene_point(self, point: QPointF) -> QPointF:
        """Resolve the cursor through the winning Phase-9 aid's snap (D-08).

        Ruled precedence (D-08 answer): the first VISIBLE **and** ENABLED aid in
        ``guides > perspective > iso`` order owns the cursor for this call — a
        hidden/disabled aid never participates, and no more than one aid ever
        snaps a given point. When no aid is visible+enabled the point is
        returned unchanged, so the caller's existing floor-to-pixel behaviour
        (the rectangular grid, the precedence's last rank) is exactly the prior,
        untouched behaviour. No snap/tick geometry is computed here — every
        branch delegates to the aid's own ``logic/``-backed ``snap()`` (Article I).
        """
        guides = self._guides_overlay
        if guides is not None and guides.is_enabled():
            sx, sy = guides.snap(point.x(), point.y())
            return QPointF(sx, sy)
        perspective = self._perspective_overlay
        if perspective is not None and perspective.isVisible():
            anchor = self._stroke_anchor or (point.x(), point.y())
            tol_doc = screen_tolerance_to_doc(DEFAULT_SNAP_TOLERANCE_PX, self._zoom)
            snapped = perspective.snap(point.x(), point.y(), anchor, tol_doc)
            return point if snapped is None else QPointF(*snapped)
        iso = self._iso_overlay
        if iso is not None and iso.isVisible():
            sx, sy = iso.snap(point.x(), point.y())
            return QPointF(sx, sy)
        return point

    def _hit_test_guide(self, point: QPointF) -> Optional[Guide]:
        """Return the guide within snap tolerance of ``point``, if any (D-11)."""
        overlay = self._guides_overlay
        if overlay is None or not overlay.is_enabled():
            return None
        tol_doc = screen_tolerance_to_doc(DEFAULT_SNAP_TOLERANCE_PX, self._zoom)
        return overlay.overlay_item().guide_at(point.x(), point.y(), tol_doc)

    def _make_edit_target(self) -> Optional[EditTarget]:
        """Return where an edit through this view lands (`REQ-P10-UI-025`).

        Read from the live ``Document`` the scene binds to — the active frame
        index and the active leaf layer's stable cross-frame ``layer_id``
        (plan §8.2). ``None`` only when the active layer has not been minted a
        stable id yet (``layer_id == 0``, the documented *unminted* sentinel,
        ``logic/document.py:264``, ``:1729``): passing ``0`` through would
        either be refused outright (`EditTarget.__post_init__`) or, worse,
        resolve to a real node in frame 0 (plan §8.1) — so an unminted layer's
        edits are reported honestly as ``unaccounted`` instead.
        """
        layer = self._scene.active_layer()
        if layer.layer_id <= 0:
            return None
        return EditTarget(frame_index=self._scene.frame_index, layer_id=layer.layer_id)

    def _make_context(self) -> ToolContext:
        return ToolContext(
            buffer=self._scene.active_buffer(),
            active_color=self._active_color,
            active_index=self._active_index,
            # `_recording_stack` duck-types `QUndoStack.push` only (the sole
            # member every `ui/tools/` controller calls on `ctx.undo_stack`,
            # confirmed by grep) and auto-binds the active branch-recording
            # sink onto every pushed command before delegating to the real
            # stack (T-DRAW-01, `REQ-P10-UI-025`; see `_RecordingUndoStack`).
            undo_stack=self._recording_stack,  # type: ignore[arg-type]
            scene=self._scene,
            target=self._make_edit_target(),
            set_active_color=self._on_color_picked,
            resolve_palette_color=self._resolve_palette_color,
            selection=self._selection,
            set_selection=self.set_selection,
            symmetry_axis=self._symmetry_axis,
            symmetry_pos=self._symmetry_pos,
            pixel_perfect=self._pixel_perfect,
            tiled=self._tiled,
            snap=self._snap,
            floating_controller=self._floating_controller,
        )

    def _on_color_picked(self, color: RGBA) -> None:
        self._active_color = color
        self.colorPicked.emit(color)

    def _resolve_palette_color(self, index: int) -> Optional[RGBA]:
        """Resolve an indexed pixel's palette ``index`` to its RGBA colour.

        Fed to every :class:`ToolContext` as ``resolve_palette_color`` for the
        picker tool (REQ-P1-UI-016). Reads the active document's live palette
        off :attr:`_recording_document` — the same ``Document`` the recording
        stack binds each pushed command to, kept current by ``set_recording``
        on every tab/branch switch (T-DRAW-01) — rather than the buffer, which
        carries no palette of its own (Article I). Returns ``None`` for an
        out-of-range index (a stale pixel left over from a since-shrunk
        palette) or when no document is bound yet, so the picker no-ops
        instead of crashing.
        """
        document = self._recording_document
        if document is None:
            return None
        palette = document.palette
        if 0 <= index < len(palette):
            return palette.get(index)
        return None

    def run_tool_at(self, x: int, y: int) -> bool:
        """Run the active tool as one press+release at pixel ``(x, y)``.

        REQ-P3-UI-006 leg (2): a completed colour-hub pick runs the ACTIVE
        tool at the anchor pixel, producing **exactly** what a left-button
        press-and-release at that pixel would — no more, no less (clause 2).
        Reuses the identical guards :meth:`mousePressEvent` enforces — a
        locked/reference/smart active layer or an anchor outside the document
        refuses the run with the same non-blocking rejection signal a
        rejected left-click surfaces, no stroke armed, no undo entry (clause
        5) — so this is never a second, divergent code path for those checks.

        Returns whether the tool actually ran (``False`` on any refusal).
        A run that changed nothing still returns ``True``; it separately
        emits :attr:`toolRunNoChange` so that case is never silent either
        (clause 6). Uses the CURRENT active colour/tool — the caller is
        responsible for having applied the picked colour first (leg 1, which
        is never refused, REQ-P3-UI-006 clause 1).
        """
        if self._tool is None:
            return False
        if not self._scene.is_active_editable():
            if self._scene.active_layer().locked:
                self.lockedLayerEditRejected.emit()
            else:
                self.nonEditableLayerEditRejected.emit()
            return False
        buf = self._scene.active_buffer()
        if not (0 <= x < buf.width and 0 <= y < buf.height):
            self.outOfDocumentClickRejected.emit()
            return False
        ctx = self._make_context()
        before = self._undo_stack.count()
        self._tool.on_press(x, y, ctx)
        self._tool.on_release(x, y, ctx)
        if self._undo_stack.count() == before:
            self.toolRunNoChange.emit()
        return True

    def _is_selection_tool_active(self) -> bool:
        return self._tool is not None and self._tool.tool_id in self._SELECTION_TOOL_IDS

    def _shift_pans(self, event: QMouseEvent) -> bool:
        """Whether ``Shift``+left-drag should pan instead of paint (REQ-IS-UI-015).

        ``True`` only when ``Shift`` is held and the active tool is not one of
        the three selection tools — those keep ``Shift``/``Alt`` as their
        shipped add/subtract combine modifiers, untouched.
        """
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            return False
        return not self._is_selection_tool_active()

    def _pick_first_favourite(self) -> None:
        """An unmodified middle click sets the first favourite (REQ-IS-UI-012)."""
        if self._favourites is None:
            return
        color = self._favourites.first()
        if color is not None:
            self._on_color_picked(color)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a pan, open the right-click menu, or start a paint stroke."""
        button = event.button()
        if button == Qt.MouseButton.MiddleButton:
            # Deferred: a middle press is a click or a drag depending on how far
            # it travels before release (REQ-IS-UI-011) — decided in
            # mouseMoveEvent/mouseReleaseEvent, never here.
            self._middle_pending = True
            self._pan_origin = event.position().toPoint()
            event.accept()
            return
        if button == Qt.MouseButton.LeftButton and self._space_held:
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if button == Qt.MouseButton.RightButton:
            self._dispatch_menu(event)
            event.accept()
            return
        if button == Qt.MouseButton.LeftButton:
            scene_pt = self.mapToScene(event.position().toPoint())
            guide_hit = self._hit_test_guide(scene_pt)
            if guide_hit is not None:
                # A press on an existing guide starts a drag-to-move (D-11); the
                # guides aid owns the gesture instead of the active paint tool.
                self._guide_drag = guide_hit
                event.accept()
                return
            if self._shift_pans(event):
                self._panning = True
                self._pan_origin = event.position().toPoint()
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        if button == Qt.MouseButton.LeftButton and self._tool is not None:
            # A locked or reference active layer rejects paint (P4-UI-004/-010);
            # the guard lives in the scene (it knows the active layer/mask). A
            # rejection creates no undo entry — the tool is never armed below.
            if not self._scene.is_active_editable():
                # Three non-editable classes, not two (REQ-P3-UI-006 clause 5):
                # locked, reference, and smart all fail ``is_active_editable()``,
                # and none may refuse silently.
                if self._scene.active_layer().locked:
                    self.lockedLayerEditRejected.emit()
                else:
                    self.nonEditableLayerEditRejected.emit()
                event.accept()
                return
            x, y = self._pixel_at(event)
            buf = self._scene.active_buffer()
            if not (0 <= x < buf.width and 0 <= y < buf.height):
                # Out-of-document click (FIX 5): must not arm a stroke, and must
                # not fail silently (no-silent-result rule) — surfaced by the
                # shell exactly like the locked-layer rejection above.
                self.outOfDocumentClickRejected.emit()
                event.accept()
                return
            self._ctx = self._make_context()
            self._ctx.modifiers = event.modifiers()
            # The raw (pre-snap) press point anchors a perspective direction-lock
            # for the rest of this stroke (D-08; logic.grids.perspective_snap).
            raw_pt = self.mapToScene(event.position().toPoint())
            self._stroke_anchor = (raw_pt.x(), raw_pt.y())
            self._drawing = True
            self._tool.on_press(x, y, self._ctx)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Continue an active pan, guide drag, or paint drag, tracking the cursor."""
        if self._middle_pending:
            here = event.position().toPoint()
            travel = (here - self._pan_origin).manhattanLength()
            if travel >= CLICK_DRAG_THRESHOLD_PX:
                # The press has crossed the click/drag threshold (REQ-IS-UI-011):
                # promote to a real pan, anchored from here so the next move's
                # delta is not a jump back to the original press point.
                self._middle_pending = False
                self._panning = True
                self._pan_origin = here
                self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._pan_origin = event.position().toPoint()
            hbar = self.horizontalScrollBar()
            vbar = self.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            event.accept()
            return
        if self._guide_drag is not None:
            self._update_guide_drag(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if self._drawing and self._tool is not None and self._ctx is not None:
            # Re-sample modifiers each move so Ctrl held mid-drag toggles the
            # floating move to COPY (REQ-P2-UI-032; the press only sampled once).
            self._ctx.modifiers = event.modifiers()
            x, y = self._pixel_at(event)
            self._tool.on_move(x, y, self._ctx)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def _update_guide_drag(self, point: QPointF) -> None:
        """Move the in-drag guide to ``point`` on its own axis (D-11)."""
        overlay = self._guides_overlay
        guide = self._guide_drag
        if overlay is None or guide is None:
            return
        position = (
            point.x() if guide.orientation is GuideOrientation.VERTICAL else point.y()
        )
        self._guide_drag = overlay.overlay_item().move_guide(guide, position)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End an active pan, or commit the active paint stroke on release."""
        if self._middle_pending and event.button() == Qt.MouseButton.MiddleButton:
            # Released before crossing the threshold: a click (REQ-IS-UI-011).
            # An unmodified click picks the first favourite (REQ-IS-UI-012); a
            # modified one is left for the modifier-specific gesture that owns
            # it (T-23) and is a deliberate no-op here.
            self._middle_pending = False
            if event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self._pick_first_favourite()
            event.accept()
            return
        if self._panning and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self.viewport().unsetCursor()
            event.accept()
            return
        if self._guide_drag is not None and event.button() == Qt.MouseButton.LeftButton:
            self._finish_guide_drag(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        if (
            self._drawing
            and event.button() == Qt.MouseButton.LeftButton
            and self._tool is not None
            and self._ctx is not None
        ):
            self._ctx.modifiers = event.modifiers()
            x, y = self._pixel_at(event)
            self._tool.on_release(x, y, self._ctx)
            self._drawing = False
            self._ctx = None
            self._stroke_anchor = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _finish_guide_drag(self, point: QPointF) -> None:
        """End the guide drag: drop it if released off-canvas (D-11).

        Drag-off-canvas removes the guide through the overlay's PUBLIC
        ``remove_guide`` (never a private path); released on-canvas simply
        leaves it at the last :meth:`_update_guide_drag` position.
        """
        overlay = self._guides_overlay
        guide = self._guide_drag
        self._guide_drag = None
        if overlay is None or guide is None:
            return
        if not self._content_rect().contains(point):
            overlay.overlay_item().remove_guide(guide)

    # -- right-click seam (CL-8) -----------------------------------------

    def _dispatch_menu(self, event: QMouseEvent) -> None:
        x, y = self._pixel_at(event)
        self.rightClicked.emit(x, y)
        scene_pt = self.mapToScene(event.position().toPoint())
        guide_hit = self._hit_test_guide(scene_pt)
        if guide_hit is not None:
            # Context-action removal gesture (D-11), an alternative to
            # drag-off-canvas — both reach the overlay's PUBLIC remove_guide.
            self._show_guide_context_menu(guide_hit, event.globalPosition().toPoint())
            return
        if self._menu_hook is not None:
            self._menu_hook(x, y)
            return
        self._show_placeholder_menu(event.globalPosition().toPoint())

    def _show_guide_context_menu(self, guide: Guide, global_pos: QPoint) -> None:
        """Offer to remove ``guide`` (the D-11 context-action removal gesture)."""
        overlay = self._guides_overlay
        menu = QMenu(self)
        remove_action = menu.addAction(self.tr("Remove guide"))
        remove_action.setEnabled(overlay is not None)
        if overlay is not None:
            remove_action.triggered.connect(
                lambda: overlay.overlay_item().remove_guide(guide)
            )
        menu.exec(global_pos)

    def _show_placeholder_menu(self, global_pos: QPoint) -> None:
        """Phase-1 placeholder menu — the colour hub is deferred to Phase 3."""
        menu = QMenu(self)
        placeholder = menu.addAction(self.tr("No canvas actions yet"))
        placeholder.setEnabled(False)
        menu.exec(global_pos)

    def contextMenuEvent(  # noqa: N802 (Qt override)
        self, event: QContextMenuEvent
    ) -> None:
        """Open the colour hub from the keyboard (Menu key / Shift+F10).

        Makes the hub reachable without a mouse (A11Y-COLHUB-1, SC-U003-3). Mouse
        right-clicks are already handled in :meth:`mousePressEvent`, so only the
        keyboard-triggered request is serviced here to avoid a double menu. With no
        cursor to anchor to, the hub opens at the viewport centre; the seam hook
        maps the buffer pixel back to a screen position (device-independent).
        """
        if event.reason() != QContextMenuEvent.Reason.Keyboard:
            super().contextMenuEvent(event)
            return
        view_point = self.viewport().rect().center()
        scene_point = self.mapToScene(view_point)
        x, y = math.floor(scene_point.x()), math.floor(scene_point.y())
        self.rightClicked.emit(x, y)
        if self._menu_hook is not None:
            self._menu_hook(x, y)
        else:
            self._show_placeholder_menu(self.viewport().mapToGlobal(view_point))
        event.accept()

    def scene_pixel_to_global(self, x: int, y: int) -> QPoint:
        """Map a buffer pixel to a global screen point (hub anchor, any device)."""
        view_point = self.mapFromScene(QPointF(x + 0.5, y + 0.5))
        return self.viewport().mapToGlobal(view_point)

    # -- file-drop routing (CF: T-12, REQ-DDI-UI-001) ---------------------

    @staticmethod
    def _is_url_drag(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
        mime = event.mimeData()
        return mime.hasUrls() and any(url.isLocalFile() for url in mime.urls())

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Take over a URL drag; leave every other drag to the scene (D4/D5/D6).

        Without this override, ``QGraphicsView`` translates the event into a
        ``QGraphicsSceneDragDropEvent`` for the scene, which has no item that
        accepts it — the drag is then rejected and never reaches
        ``Main_Window`` on drop.
        """
        if self._is_url_drag(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        """Keep accepting a URL drag as it moves; delegate everything else."""
        if self._is_url_drag(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Route a URL drop through the window's file-drop handling (T-12).

        A drop delivered straight to this viewport used to be silently
        swallowed by the scene (no import, no notice, no crash) — this closes
        that gap by calling the same router ``Main_Window.dropEvent`` uses, so
        a drop landing on the canvas behaves identically to one landing
        anywhere else on the window. A missing router (view constructed
        without one) or a non-URL drag both fall back to the prior
        scene-forwarding behaviour.
        """
        if self._is_url_drag(event) and self._drop_router is not None:
            paths = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.isLocalFile()
            ]
            event.acceptProposedAction()
            self._drop_router(paths)
            return
        super().dropEvent(event)

    # -- i18n -------------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the accessible name/description on QEvent.LanguageChange (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self.setAccessibleName(self.tr("Canvas"))
            self.setAccessibleDescription(
                self.tr("Pixel canvas: left-click to paint, middle-drag to pan")
            )
        super().changeEvent(event)
