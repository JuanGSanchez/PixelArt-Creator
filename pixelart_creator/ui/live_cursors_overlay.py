"""Live collaborator-cursor overlay (REQ-P10-UI-013) — Qt only, ephemeral.

Phase-10 Slice C. :class:`Live_Cursors_Overlay` is a doc-space
:class:`~PySide6.QtWidgets.QGraphicsItem` on the shared scene that draws **other**
collaborators' cursors + selection live, from the ephemeral presence/awareness channel
(REQ-P10-DATA-010). It mirrors the Phase-9 overlay pattern
(:class:`~pixelart_creator.ui.guides_rulers_overlay.Guides_Overlay`): a per-frame
:meth:`paint` clipped to ``option.exposedRect``, no anti-aliasing, cosmetic pens, and
**no** persisted state — the overlay is never saved into the ``.pixproj`` or the CRDT
sidecar.

**Per-frame design (for AGT-10's FLAG-PERFRAME assessment, ADR-0027 §7).** This overlay
sits on the interactive loop, so it is deliberately minimal:

* **No item cache** — cursors move nearly every frame, so a
  ``DeviceCoordinateCache`` would thrash; the item is cheap enough to redraw. (The
  Phase-9 static guides *do* cache; live cursors must not.)
* **exposedRect culling** — :meth:`paint` skips any cursor/selection whose position is
  outside the exposed rect, so off-screen collaborators cost nothing.
* **Bounded roster** — at most ``MAX_SHARED_MEMBERS`` cursors are ever drawn (the shared
  bound, Article II/VII), so a hostile presence flood cannot make the draw unbounded.
* **Cosmetic, zoom-invariant marks** — a small crosshair + a short name label, drawn in
  device space so they stay a constant size at any zoom (no per-pixel work).

AGT-10 profiles the combined *remote-apply + this draw* against ``FRAME_BUDGET_MS`` and
may direct coalescing (e.g. throttling presence repaints); the item exposes
:meth:`cursor_count` and :meth:`set_cursor` as the seam for that. Every user-visible
string is ``tr()``-wrapped via a translatable member label built by the caller; the
overlay itself renders the caller-supplied ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.constants import MAX_SHARED_MEMBERS

#: z-order: above every Phase-9 aid overlay (guides ``3.5``, grids ``~4``) so live
#: cursors always read on top of the canvas + aids.
_CURSORS_Z = 9.0

#: Crosshair half-length + label offset, device px (cosmetic, zoom-invariant sizing).
_MARK_HALF = 6.0
_LABEL_DX = 8.0
_LABEL_DY = -8.0

#: Fixed alpha for a collaborator selection fill (subtle, non-obscuring).
_SELECTION_ALPHA = 60


@dataclass
class _Cursor:
    """One collaborator's ephemeral cursor + optional selection (doc-space)."""

    x: float
    y: float
    color: QColor
    selection: Optional[QRectF] = None


def cursor_color_for(member_id: str) -> QColor:
    """Return a stable, distinct display colour for ``member_id`` (presentation only).

    Deterministic per id via a hue hash so a collaborator keeps the same colour across
    frames; this is presentation styling, not domain logic (no colour maths from
    ``logic/`` is needed for a per-member marker hue).
    """
    hue = (hash(member_id) & 0xFFFF) % 360
    color = QColor()
    color.setHsv(hue, 200, 235)
    return color


class Live_Cursors_Overlay(QGraphicsItem):
    """Ephemeral overlay of other collaborators' cursors + selection (REQ-P10-UI-013).

    Args:
        scene_rect: The document scene rect ``(0, 0, W, H)`` the overlay spans.
    """

    def __init__(self, scene_rect: QRectF) -> None:
        """Build an empty, hidden live-cursor overlay spanning ``scene_rect``."""
        super().__init__()
        self.setZValue(_CURSORS_Z)
        self.setVisible(False)
        # Deliberately NO cache: cursors move per frame (see module docstring / AGT-10).
        self._rect = QRectF(scene_rect)
        self._cursors: Dict[str, _Cursor] = {}
        # The local member never renders its own cursor from presence.
        self._local_member_id: str = ""

    # -- roster management ------------------------------------------------

    def set_local_member(self, member_id: str) -> None:
        """Set the local member id so its own presence echo is not drawn."""
        self._local_member_id = member_id or ""
        self._cursors.pop(self._local_member_id, None)
        self.update()

    def set_scene_rect(self, scene_rect: QRectF) -> None:
        """Track the document geometry (resize / document switch)."""
        self.prepareGeometryChange()
        self._rect = QRectF(scene_rect)
        self.update()

    def set_cursor(
        self,
        member_id: str,
        x: float,
        y: float,
        selection: Optional[QRectF] = None,
    ) -> None:
        """Set/refresh ``member_id``'s cursor position (+ optional selection rect).

        A bounded roster (``MAX_SHARED_MEMBERS``) caps how many cursors are ever stored,
        so a presence flood cannot grow the draw unbounded (Article VII). The local
        member's own cursor is ignored.
        """
        if not member_id or member_id == self._local_member_id:
            return
        if member_id not in self._cursors and len(self._cursors) >= MAX_SHARED_MEMBERS:
            return
        self._cursors[member_id] = _Cursor(
            x=float(x),
            y=float(y),
            color=cursor_color_for(member_id),
            selection=QRectF(selection) if selection is not None else None,
        )
        self.update()

    def apply_presence(self, payload: dict) -> None:
        """Update the roster from a validated presence mapping (member_id + cursor).

        Reads ``member_id`` and an optional ``cursor`` ``{x, y}`` / ``selection``
        ``{x, y, width, height}`` (the schema
        :func:`~pixelart_creator.logic.cloud_validation.validate_presence` allows). A
        payload without a cursor removes that member's marker (present but idle).
        """
        member_id = payload.get("member_id")
        if not isinstance(member_id, str) or not member_id:
            return
        cursor = payload.get("cursor")
        if not isinstance(cursor, dict):
            self.remove_cursor(member_id)
            return
        try:
            x = float(cursor.get("x", 0))
            y = float(cursor.get("y", 0))
        except (TypeError, ValueError):
            return
        selection = _selection_rect(payload.get("selection"))
        self.set_cursor(member_id, x, y, selection)

    def remove_cursor(self, member_id: str) -> None:
        """Drop a collaborator's cursor (they left / went idle)."""
        if member_id in self._cursors:
            del self._cursors[member_id]
            self.update()

    def clear(self) -> None:
        """Remove every collaborator cursor (on disconnect / document switch)."""
        if self._cursors:
            self._cursors = {}
            self.update()

    def cursor_count(self) -> int:
        """Return how many collaborator cursors are drawn (test/AGT-10 seam)."""
        return len(self._cursors)

    def cursor_ids(self) -> Tuple[str, ...]:
        """Return the current collaborator ids (deterministic order; test seam)."""
        return tuple(sorted(self._cursors))

    # -- QGraphicsItem ----------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        """Return the document scene rect the overlay spans (Qt override)."""
        return QRectF(self._rect)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Draw each visible collaborator cursor + selection, exposedRect-culled.

        Per-frame minimal (AGT-10): no anti-aliasing, cosmetic pens, and every cursor
        outside the exposed rect is skipped so off-screen collaborators cost nothing.
        """
        if not self._cursors:
            return
        exposed = option.exposedRect
        if exposed.isEmpty():
            exposed = self._rect
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for member_id, cursor in self._cursors.items():
            point = QPointF(cursor.x, cursor.y)
            if cursor.selection is not None and cursor.selection.intersects(exposed):
                self._paint_selection(painter, cursor)
            if not exposed.contains(point):
                continue
            self._paint_cursor(painter, member_id, cursor)

    def _paint_selection(self, painter: QPainter, cursor: _Cursor) -> None:
        assert cursor.selection is not None
        pen = QPen(cursor.color)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        fill = QColor(cursor.color)
        fill.setAlpha(_SELECTION_ALPHA)
        painter.setBrush(fill)
        painter.drawRect(cursor.selection)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_cursor(self, painter: QPainter, member_id: str, cursor: _Cursor) -> None:
        pen = QPen(cursor.color)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        cx, cy = cursor.x, cursor.y
        # A cosmetic crosshair: two lengths mapped to device px via the painter scale so
        # the mark stays a constant screen size at any zoom.
        scale = _painter_scale(painter)
        half = _MARK_HALF / scale if scale > 0.0 else _MARK_HALF
        painter.drawLine(QLineF(cx - half, cy, cx + half, cy))
        painter.drawLine(QLineF(cx, cy - half, cx, cy + half))
        label_offset = QPointF(
            _LABEL_DX / scale if scale > 0.0 else _LABEL_DX,
            _LABEL_DY / scale if scale > 0.0 else _LABEL_DY,
        )
        painter.drawText(QPointF(cx, cy) + label_offset, member_id)


def _painter_scale(painter: QPainter) -> float:
    """Return the painter's horizontal world→device scale (for cosmetic sizing)."""
    return abs(painter.worldTransform().m11()) or 1.0


def _selection_rect(value: object) -> Optional[QRectF]:
    """Build a doc-space selection rect from a presence ``selection`` mapping."""
    if not isinstance(value, dict):
        return None
    try:
        x = float(value.get("x", 0))
        y = float(value.get("y", 0))
        width = float(value.get("width", 0))
        height = float(value.get("height", 0))
    except (TypeError, ValueError):
        return None
    if width <= 0.0 or height <= 0.0:
        return None
    return QRectF(x, y, width, height)
