# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Multi-view editing (REQ-P9-UI-007/-008) — Qt only, one shared scene.

``Multi_View`` opens extra :class:`QGraphicsView` viewports onto the **one** shared
document :class:`~pixelart_creator.ui.canvas_scene.CanvasScene`. Because every view
calls ``setScene(sameScene)``, an edit committed on the document repaints **all**
views (and the real-size preview) automatically through ``QGraphicsScene.changed`` —
no manual fan-out, no per-view pixel copy (research §5.1; the single-source invariant
REQ-P9-LOGIC-012). Each view keeps its **own** transform, so zoom/pan is independent
per viewport.

This is multi-**view** of ONE document — distinct from the Phase-4 multi-**canvas**
tabs (each a separate document/scene). The count is capped at ``MAX_DOCUMENT_VIEWS``.
The extra views are plain read/navigate viewports (``NoDrag``); painting stays in the
primary :class:`~pixelart_creator.ui.canvas_view.Canvas_View`. All view titles are
``tr()``-wrapped.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from pixelart_creator.logic.constants import MAX_DOCUMENT_VIEWS
from pixelart_creator.logic.favourites import Favourites

#: Per-wheel-notch zoom step for an extra view (independent of the primary view).
_WHEEL_ZOOM_STEP = 1.15


class Document_View(QGraphicsView):
    """An extra navigate-only viewport on the shared document scene.

    Independent zoom/pan; never paints (no tool) so it cannot corrupt the shared
    document — edits arrive live via ``scene.changed`` (REQ-P9-UI-008).
    """

    #: Emitted with the picked RGBA tuple when a plain wheel notch travels the
    #: shared Favourites cursor (REQ-IS-UI-008, T-21/D-16 — this surface is a
    #: navigate-only view of the SAME live document scene as the primary
    #: Canvas_View, so the active colour it sets is real document context).
    colorPicked = Signal(object)

    def __init__(
        self,
        scene: QGraphicsScene,
        index: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build an extra navigate-only viewport on the shared ``scene``."""
        super().__init__(scene, parent)
        self._index = index
        #: The persisted Favourites model bound via :meth:`set_favourites_model`
        #: (T-21); ``None`` until the shell binds one.
        self._favourites: Optional[Favourites] = None
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._retranslate()

    def set_favourites_model(self, favourites: Favourites) -> None:
        """Bind the persisted Favourites model a plain wheel notch travels.

        REQ-IS-UI-008, T-21.
        """
        self._favourites = favourites

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        """Zoom on ``Shift``+wheel, otherwise travel the Favourites list.

        ``Shift``+wheel zooms (REQ-IS-UI-009, D-16); plain wheel travels
        Favourites (REQ-IS-UI-008, D-16).
        """
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._zoom_wheel(event)
        else:
            self._favourites_wheel(event)

    def _zoom_wheel(self, event: QWheelEvent) -> None:
        """Cursor-anchored independent zoom for this viewport.

        Relocated from plain wheel to ``Shift``+wheel (D-16); this view's own
        step and anchor are otherwise unmodified.
        """
        factor = _WHEEL_ZOOM_STEP
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        self.scale(factor, factor)
        event.accept()

    def _favourites_wheel(self, event: QWheelEvent) -> None:
        """Plain wheel steps the Favourites cursor (REQ-IS-UI-008, D-16).

        Wheel down **advances**, wheel up **retreats** (``CL-IS-02`` — see
        ``Canvas_View._favourites_wheel``). A silent no-op with no favourites
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
            self.colorPicked.emit(color)
        event.accept()

    def _retranslate(self) -> None:
        title = self.tr("Document view {0}").format(self._index)
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setAccessibleDescription(
            self.tr("An extra synced view of the same document (independent zoom/pan)")
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the view title/accessible strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Multi_View:
    """Controller opening/closing extra views on one shared document scene.

    Args:
        scene: The shared :class:`~pixelart_creator.ui.canvas_scene.CanvasScene`.
    """

    def __init__(self, scene: QGraphicsScene) -> None:
        """Bind the controller to the shared document ``scene``."""
        self._scene = scene
        self._views: List[Document_View] = []
        #: The persisted Favourites model applied to every view opened from
        #: now on (T-21); ``None`` until the shell binds one.
        self._favourites: Optional[Favourites] = None

    def set_scene(self, scene: QGraphicsScene) -> None:
        """Rebind every open extra view to a new shared scene (tab switch)."""
        self._scene = scene
        for view in self._views:
            view.setScene(scene)

    def set_favourites_model(self, favourites: Favourites) -> None:
        """Bind the persisted Favourites model every extra view's wheel travels.

        Applies to every current AND future extra view's plain wheel notch
        (REQ-IS-UI-008, T-21).
        """
        self._favourites = favourites
        for view in self._views:
            view.set_favourites_model(favourites)

    def open_view(self) -> Optional[Document_View]:
        """Open one extra viewport on the shared scene (``<= MAX_DOCUMENT_VIEWS``).

        Returns the new view, or ``None`` if the cap is reached. The primary
        Canvas_View counts as view 1, so at most ``MAX_DOCUMENT_VIEWS - 1`` extras
        are opened.
        """
        if len(self._views) >= MAX_DOCUMENT_VIEWS - 1:
            return None
        view = Document_View(self._scene, index=len(self._views) + 2)
        view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        view.destroyed.connect(lambda *_a, v=view: self._forget(v))
        if self._favourites is not None:
            view.set_favourites_model(self._favourites)
        self._views.append(view)
        return view

    def views(self) -> List[Document_View]:
        """Return the open extra views."""
        return list(self._views)

    def count(self) -> int:
        """Return the number of open extra views."""
        return len(self._views)

    def close_all(self) -> None:
        """Close every extra view (document/tab teardown)."""
        for view in list(self._views):
            view.close()
        self._views = []

    def _forget(self, view: Document_View) -> None:
        if view in self._views:
            self._views.remove(view)
