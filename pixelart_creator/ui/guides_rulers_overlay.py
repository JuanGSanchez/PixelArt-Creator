"""Guides & rulers overlay (REQ-P9-UI-003) — Qt only, binds to logic/guides.

Three cooperating presentation pieces, all bound to the pure
:mod:`pixelart_creator.logic.guides` engine (Article I — this module computes **no**
snap/tick geometry of its own):

* :class:`Guides_Overlay` — a doc-space :class:`QGraphicsItem` on the shared scene
  that draws the created guides (culled to the exposed rect) and exposes a cursor
  ``snap`` that delegates to :func:`~pixelart_creator.logic.guides.snap_guides`.
* :class:`Ruler_Strip` — a horizontal / vertical ruler :class:`QWidget` that paints
  the nice-number ticks from :func:`~pixelart_creator.logic.guides.ruler_ticks` and a
  live coordinate readout from
  :func:`~pixelart_creator.logic.guides.coordinate_readout`; dragging out of a strip
  requests a new guide (the Photoshop/Aseprite model, research §3.1).
* :class:`Guides_Rulers_Overlay` — a controller wiring a
  :class:`~pixelart_creator.ui.canvas_view.Canvas_View` + scene to the overlay item
  and the two ruler strips, keeping them synced to the view transform, and toggling
  the whole aid on/off.

Snap tolerance is a screen-px stickiness converted to doc space via
:func:`~pixelart_creator.logic.guides.screen_tolerance_to_doc` so it feels constant at
every zoom. All user-visible strings are ``tr()``-wrapped with a ``changeEvent``
retranslate (REQ-P9-UI-014).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, QLineF, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.constants import DEFAULT_SNAP_TOLERANCE_PX
from pixelart_creator.logic.guides import (
    Guide,
    GuideOrientation,
    coordinate_readout,
    ruler_ticks,
    screen_tolerance_to_doc,
    snap_guides,
)

#: z-order in the aid band, just below the grid overlays so guides read under grids.
_GUIDES_Z = 3.5

#: Ruler strip thickness in device-independent px (presentation sizing).
_RULER_THICKNESS = 20

#: Default overlay/ruler colours (overridden by the theme's role colours, 025).
_DEFAULT_GUIDE = QColor(60, 190, 200, 200)
_DEFAULT_RULER_BG = QColor(48, 48, 48)
_DEFAULT_RULER_FG = QColor(210, 210, 210)


class Guides_Overlay(QGraphicsItem):
    """Doc-space guide lines + cursor snap (binds to logic/guides).

    Args:
        scene_rect: The document scene rect ``(0, 0, W, H)`` the guides span.
    """

    def __init__(self, scene_rect: QRectF) -> None:
        """Build an empty guide overlay spanning ``scene_rect``."""
        super().__init__()
        self.setZValue(_GUIDES_Z)
        self.setVisible(False)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self._rect = QRectF(scene_rect)
        self._guides: List[Guide] = []
        self._color = QColor(_DEFAULT_GUIDE)

    # -- guide management -------------------------------------------------

    def add_guide(self, orientation: GuideOrientation, position: float) -> Guide:
        """Create and store a guide (validated by ``logic/guides.Guide``)."""
        guide = Guide(orientation=orientation, position=float(position))
        self._guides.append(guide)
        self.update()
        return guide

    def remove_guide(self, guide: Guide) -> None:
        """Remove a stored guide (no-op if absent)."""
        if guide in self._guides:
            self._guides.remove(guide)
            self.update()

    def guide_at(self, x: float, y: float, tolerance_doc: float) -> Optional[Guide]:
        """Return the nearest guide within ``tolerance_doc`` of ``(x, y)`` (D-11).

        Only the guide's own axis is compared (a ``VERTICAL`` guide's ``x``, a
        ``HORIZONTAL`` guide's ``y``), so any point along the guide's full length
        hits it — the drag-anywhere-on-the-line gesture. ``None`` when no guide
        is within tolerance; the nearest wins on multiple hits (deterministic).
        """
        best: Optional[Guide] = None
        best_d: Optional[float] = None
        for guide in self._guides:
            value = x if guide.orientation is GuideOrientation.VERTICAL else y
            d = abs(value - guide.position)
            if d <= tolerance_doc and (best_d is None or d < best_d):
                best = guide
                best_d = d
        return best

    def move_guide(self, guide: Guide, position: float) -> Guide:
        """Replace ``guide`` with one at ``position`` on the same axis (D-11 drag).

        Guides are immutable (:class:`Guide` is frozen), so a move is a
        remove-then-add; returns the new stored :class:`Guide` so the caller
        (the live drag) keeps tracking the correct instance. Safe even if
        ``guide`` is no longer stored (the new guide is still appended).
        """
        if guide in self._guides:
            self._guides.remove(guide)
        moved = Guide(orientation=guide.orientation, position=float(position))
        self._guides.append(moved)
        self.update()
        return moved

    def clear_guides(self) -> None:
        """Remove every guide."""
        if self._guides:
            self._guides = []
            self.update()

    def guides(self) -> Tuple[Guide, ...]:
        """Return an immutable snapshot of the stored guides."""
        return tuple(self._guides)

    def set_scene_rect(self, scene_rect: QRectF) -> None:
        """Track the document geometry (resize / document switch)."""
        self.prepareGeometryChange()
        self._rect = QRectF(scene_rect)
        self.update()

    def set_color(self, color: QColor) -> None:
        """Set the role-based guide colour (legible in both themes, 025)."""
        self._color = QColor(color)
        self.update()

    # -- snap seam (pure geometry lives in logic/guides) ------------------

    def snap(self, x: float, y: float, zoom: float) -> Tuple[float, float]:
        """Snap ``(x, y)`` to the nearest guides within tolerance (delegates to logic).

        The screen-px stickiness is converted to doc space via
        :func:`screen_tolerance_to_doc`; :func:`snap_guides` returns the snapped
        point. No geometry is computed here (Article I; REQ-P9-UI-003).
        """
        tol_doc = screen_tolerance_to_doc(DEFAULT_SNAP_TOLERANCE_PX, zoom)
        return snap_guides(x, y, self._guides, tol_doc)

    # -- QGraphicsItem ----------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        """Return the document scene rect the guides span (Qt override)."""
        return QRectF(self._rect)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Stroke the visible guide lines, culled to the exposed rect (Qt override)."""
        if not self._guides:
            return
        exposed = option.exposedRect
        if exposed.isEmpty():
            exposed = self._rect
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(self._color)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        lines = []
        for guide in self._guides:
            if guide.orientation is GuideOrientation.VERTICAL:
                x = guide.position
                if exposed.left() <= x <= exposed.right():
                    lines.append(QLineF(x, self._rect.top(), x, self._rect.bottom()))
            else:
                y = guide.position
                if exposed.top() <= y <= exposed.bottom():
                    lines.append(QLineF(self._rect.left(), y, self._rect.right(), y))
        painter.drawLines(lines)


class Ruler_Strip(QWidget):
    """A horizontal or vertical ruler strip bound to logic/guides tick + readout.

    Args:
        orientation: :class:`GuideOrientation` — ``HORIZONTAL`` for a top ruler
            (x ticks), ``VERTICAL`` for a left ruler (y ticks).
        view: The :class:`~pixelart_creator.ui.canvas_view.Canvas_View` whose zoom
            and pan drive the tick placement (read only).
    """

    #: Emitted ``(orientation, doc_position)`` when a guide is dragged out.
    guideCreationRequested = Signal(object, float)

    def __init__(
        self,
        orientation: GuideOrientation,
        view: "QWidget",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build a ruler strip for ``orientation`` driven by ``view``."""
        super().__init__(parent)
        self._orientation = orientation
        self._view = view
        self._bg = QColor(_DEFAULT_RULER_BG)
        self._fg = QColor(_DEFAULT_RULER_FG)
        self._cursor_doc: Optional[int] = None
        if orientation is GuideOrientation.HORIZONTAL:
            self.setFixedHeight(_RULER_THICKNESS)
        else:
            self.setFixedWidth(_RULER_THICKNESS)
        self.setMouseTracking(True)
        self._retranslate()

    def set_colors(self, background: QColor, foreground: QColor) -> None:
        """Set role-based ruler colours (legible in both themes, 025)."""
        self._bg = QColor(background)
        self._fg = QColor(foreground)
        self.update()

    def _view_zoom(self) -> float:
        zoom = getattr(self._view, "zoom", None)
        value = float(zoom()) if callable(zoom) else 1.0
        return value if value > 0.0 else 1.0

    def _doc_offset(self) -> Tuple[float, float]:
        """Doc coordinate at the view's top-left corner (pan offset)."""
        map_fn = getattr(self._view, "mapToScene", None)
        if map_fn is None:
            return (0.0, 0.0)
        top_left = map_fn(0, 0)
        return (top_left.x(), top_left.y())

    def sync(self) -> None:
        """Repaint after a view zoom / pan (the controller connects this)."""
        self.update()

    def set_cursor_readout(self, sx: float, sy: float) -> None:
        """Update the live coordinate readout from a scene cursor (via logic)."""
        zoom = self._view_zoom()
        ox, oy = self._doc_offset()
        doc_x, doc_y = coordinate_readout(sx, sy, zoom, (ox, oy))
        self._cursor_doc = (
            doc_x if self._orientation is GuideOrientation.HORIZONTAL else doc_y
        )
        self.update()

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Paint the ruler background, nice-number ticks and labels (Qt override)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), self._bg)
        zoom = self._view_zoom()
        ox, oy = self._doc_offset()
        horizontal = self._orientation is GuideOrientation.HORIZONTAL
        axis_pixels = self.width() if horizontal else self.height()
        offset = ox if horizontal else oy
        if axis_pixels < 1:
            painter.end()
            return
        ticks = ruler_ticks(
            float(axis_pixels),
            zoom,
            float(offset),
            axis_pixels=int(axis_pixels),
        )
        pen = QPen(self._fg)
        pen.setCosmetic(True)
        painter.setPen(pen)
        for tick in ticks:
            screen = (tick.position - offset) * zoom
            if horizontal:
                painter.drawLine(QLineF(screen, 12.0, screen, _RULER_THICKNESS))
                painter.drawText(QPointF(screen + 2.0, 10.0), tick.label)
            else:
                painter.drawLine(QLineF(12.0, screen, _RULER_THICKNESS, screen))
                painter.drawText(QPointF(1.0, screen - 2.0), tick.label)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Dragging out of the ruler requests a guide at the cursor doc position."""
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        zoom = self._view_zoom()
        ox, oy = self._doc_offset()
        pos = event.position()
        if self._orientation is GuideOrientation.HORIZONTAL:
            doc_pos = ox + pos.x() / zoom
        else:
            doc_pos = oy + pos.y() / zoom
        self.guideCreationRequested.emit(self._orientation, float(doc_pos))
        event.accept()

    def _retranslate(self) -> None:
        if self._orientation is GuideOrientation.HORIZONTAL:
            self.setAccessibleName(self.tr("Horizontal ruler"))
            self.setAccessibleDescription(
                self.tr("Drag down to create a horizontal guide")
            )
        else:
            self.setAccessibleName(self.tr("Vertical ruler"))
            self.setAccessibleDescription(
                self.tr("Drag right to create a vertical guide")
            )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the accessible strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Guides_Rulers_Overlay(QObject):
    """Controller wiring a view/scene to the guide overlay + two ruler strips.

    Args:
        view: The :class:`~pixelart_creator.ui.canvas_view.Canvas_View` to overlay.
        scene: The shared :class:`~pixelart_creator.ui.canvas_scene.CanvasScene`.
        scene_rect: The document scene rect ``(0, 0, W, H)``.
    """

    def __init__(
        self,
        view: "QWidget",
        scene: QGraphicsScene,
        scene_rect: QRectF,
        parent: Optional[QObject] = None,
    ) -> None:
        """Wire ``view``/``scene`` to the guide overlay and two ruler strips."""
        super().__init__(parent)
        self._view = view
        self._overlay = Guides_Overlay(scene_rect)
        scene.addItem(self._overlay)
        self._h_ruler = Ruler_Strip(GuideOrientation.HORIZONTAL, view)
        self._v_ruler = Ruler_Strip(GuideOrientation.VERTICAL, view)
        self._h_ruler.guideCreationRequested.connect(self._on_guide_requested)
        self._v_ruler.guideCreationRequested.connect(self._on_guide_requested)
        self._enabled = False
        # Keep the rulers synced to the view transform (pan + zoom).
        zoom_changed = getattr(view, "zoomChanged", None)
        if zoom_changed is not None:
            zoom_changed.connect(self._sync_rulers)

    # -- accessors --------------------------------------------------------

    def overlay_item(self) -> Guides_Overlay:
        """Return the doc-space guide overlay item."""
        return self._overlay

    def horizontal_ruler(self) -> Ruler_Strip:
        """Return the top ruler strip."""
        return self._h_ruler

    def vertical_ruler(self) -> Ruler_Strip:
        """Return the left ruler strip."""
        return self._v_ruler

    # -- toggle -----------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Show/hide the guides overlay + rulers (non-destructive view state)."""
        self._enabled = bool(enabled)
        self._overlay.setVisible(self._enabled)
        self._h_ruler.setVisible(self._enabled)
        self._v_ruler.setVisible(self._enabled)
        if self._enabled:
            self._sync_rulers()

    def is_enabled(self) -> bool:
        """Return whether the aid is on."""
        return self._enabled

    def snap(self, x: float, y: float) -> Tuple[float, float]:
        """Snap a scene point to the guides (delegates to the overlay/logic)."""
        zoom = getattr(self._view, "zoom", None)
        z = float(zoom()) if callable(zoom) else 1.0
        return self._overlay.snap(x, y, z if z > 0.0 else 1.0)

    def set_colors(
        self,
        guide: QColor,
        ruler_bg: QColor,
        ruler_fg: QColor,
    ) -> None:
        """Push role-based colours to the overlay + rulers (both themes, 025)."""
        self._overlay.set_color(guide)
        self._h_ruler.set_colors(ruler_bg, ruler_fg)
        self._v_ruler.set_colors(ruler_bg, ruler_fg)

    # -- wiring -----------------------------------------------------------

    def _sync_rulers(self, *_args: object) -> None:
        self._h_ruler.sync()
        self._v_ruler.sync()

    def _on_guide_requested(
        self, orientation: GuideOrientation, position: float
    ) -> None:
        self._overlay.add_guide(orientation, position)
