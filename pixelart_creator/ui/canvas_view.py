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

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QContextMenuEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QTransform,
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsView, QMenu, QWidget

from pixelart_creator.logic.color import BLACK, RGBA
from pixelart_creator.logic.constants import (
    OPENGL_VIEWPORT_ENABLED,
    SCALE_FACTOR,
    ZOOM_MAX,
    ZOOM_PRESET_STOPS,
)
from pixelart_creator.logic.selection import SelectionMask
from pixelart_creator.logic.symmetry import SymmetryAxis
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.tools.base import Tool, ToolContext
from pixelart_creator.ui.tools.floating_move import FloatingMoveController

Coord = Tuple[int, int]

#: Platform name reported by Qt when running without a windowing system.
_OFFSCREEN_PLATFORM = "offscreen"


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
        self._tool: Optional[Tool] = None
        self._active_color: RGBA = BLACK
        self._active_index: int = 0
        self._zoom = 1.0
        self._panning = False
        self._space_held = False
        self._drawing = False
        self._pan_origin = QPoint()
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
        self._pixel_perfect = False
        self._tiled = False
        self._snap = False
        self._selection: Optional[SelectionMask] = None

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

    # -- external wiring --------------------------------------------------

    def set_tool(self, tool: Tool) -> None:
        """Set the active tool controller (exactly one active, REQ-P1-UI-011)."""
        self._tool = tool

    def active_tool(self) -> Optional[Tool]:
        """Return the active tool controller."""
        return self._tool

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

    # -- Phase-2 drawing modes -------------------------------------------

    def set_symmetry_axis(self, axis: SymmetryAxis) -> None:
        """Set the live mirror-drawing axis (REQ-P2-UI-011)."""
        self._symmetry_axis = axis

    def symmetry_axis(self) -> SymmetryAxis:
        """Return the active symmetry axis."""
        return self._symmetry_axis

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

    def _fit_zoom(self) -> float:
        rect = self.sceneRect()
        vp = self.viewport().rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return 1.0
        if vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        fit = min(vp.width() / rect.width(), vp.height() / rect.height())
        return min(fit, ZOOM_MAX)

    def _clamp_zoom(self, z: float) -> float:
        return max(self._fit_zoom(), min(z, ZOOM_MAX))

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
        """Geometric cursor-anchored zoom by the ``SCALE_FACTOR`` step (CL-2/-15)."""
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
        self._scene.recomposite_exposed()  # zoom-out may expose stale area (D2)
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
        return math.floor(pt.x()), math.floor(pt.y())

    def _make_context(self) -> ToolContext:
        return ToolContext(
            buffer=self._scene.active_buffer(),
            active_color=self._active_color,
            active_index=self._active_index,
            undo_stack=self._undo_stack,
            scene=self._scene,
            set_active_color=self._on_color_picked,
            selection=self._selection,
            set_selection=self.set_selection,
            symmetry_axis=self._symmetry_axis,
            symmetry_pos=None,
            pixel_perfect=self._pixel_perfect,
            tiled=self._tiled,
            snap=self._snap,
            floating_controller=self._floating_controller,
        )

    def _on_color_picked(self, color: RGBA) -> None:
        self._active_color = color
        self.colorPicked.emit(color)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Start a pan, open the right-click menu, or start a paint stroke."""
        button = event.button()
        if button == Qt.MouseButton.MiddleButton or (
            button == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if button == Qt.MouseButton.RightButton:
            self._dispatch_menu(event)
            event.accept()
            return
        if button == Qt.MouseButton.LeftButton and self._tool is not None:
            # A locked or reference active layer rejects paint (P4-UI-004/-010);
            # the guard lives in the scene (it knows the active layer/mask). A
            # rejection creates no undo entry — the tool is never armed below.
            if not self._scene.is_active_editable():
                if self._scene.active_layer().locked:
                    self.lockedLayerEditRejected.emit()
                event.accept()
                return
            self._ctx = self._make_context()
            self._ctx.modifiers = event.modifiers()
            x, y = self._pixel_at(event)
            self._drawing = True
            self._tool.on_press(x, y, self._ctx)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Continue an active pan or an active paint drag, tracking the cursor."""
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._pan_origin = event.position().toPoint()
            hbar = self.horizontalScrollBar()
            vbar = self.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
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

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """End an active pan, or commit the active paint stroke on release."""
        if self._panning and event.button() in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self.viewport().unsetCursor()
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
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- right-click seam (CL-8) -----------------------------------------

    def _dispatch_menu(self, event: QMouseEvent) -> None:
        x, y = self._pixel_at(event)
        self.rightClicked.emit(x, y)
        if self._menu_hook is not None:
            self._menu_hook(x, y)
            return
        self._show_placeholder_menu(event.globalPosition().toPoint())

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
