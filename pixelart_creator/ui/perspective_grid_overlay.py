# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Perspective-grid overlay item (REQ-P9-UI-005) — Qt only, binds to logic/grids.

``Perspective_Grid_Overlay`` is a high-``z`` :class:`QGraphicsItem` on the shared
:class:`~pixelart_creator.ui.canvas_scene.CanvasScene`. It renders the vanishing-point
guide fan produced by
:func:`~pixelart_creator.logic.grids.perspective_guide_lines` (plus the horizon line)
and direction-locks a cursor to the nearest vanishing line via
:func:`~pixelart_creator.logic.grids.perspective_snap` — returning ``None`` beyond the
tolerance (no snap). Configurable 1-/2-/3-point (``<= MAX_PERSPECTIVE_VANISHING_
POINTS``). **The construction + snap maths live in ``logic/grids``** (Article I); this
overlay only maps the returned segments/points to Qt paint calls.

Performance (Article VI, 16 ms): ``DeviceCoordinateCache`` so a pan/zoom that leaves
the config unchanged reuses the rasterised fan (research §5.3; tunable by the
rendering/performance layer, DEP-3).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QLineF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.grids import (
    PerspectiveConfig,
    perspective_guide_lines,
    perspective_snap,
)

#: z-order above the artwork (shares the aid band with the iso overlay).
_PERSPECTIVE_Z = 4.0

#: Guide-fan sample count across the reference edge (render aid density).
_DEFAULT_SAMPLES = 12

#: Default overlay colours (overridden by the theme's role colours, 025).
_DEFAULT_LINE = QColor(220, 130, 90, 150)
_DEFAULT_HORIZON = QColor(220, 90, 90, 200)


class Perspective_Grid_Overlay(QGraphicsItem):
    """Perspective guide-fan overlay bound to :mod:`pixelart_creator.logic.grids`.

    Args:
        scene_rect: The document scene rect ``(0, 0, W, H)`` the overlay spans.
        config: The active :class:`PerspectiveConfig` (1-/2-/3-point).
        samples: The per-VP guide-fan sample count (render density).
    """

    def __init__(
        self,
        scene_rect: QRectF,
        config: PerspectiveConfig,
        samples: int = _DEFAULT_SAMPLES,
    ) -> None:
        """Build the overlay for ``scene_rect`` with ``config`` and ``samples``."""
        super().__init__()
        self.setZValue(_PERSPECTIVE_Z)
        self.setVisible(False)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self._rect = QRectF(scene_rect)
        self._config = config
        self._samples = max(1, int(samples))
        self._line = QColor(_DEFAULT_LINE)
        self._horizon = QColor(_DEFAULT_HORIZON)

    # -- configuration ----------------------------------------------------

    def set_config(self, config: PerspectiveConfig) -> None:
        """Replace the perspective config and repaint (validated in logic/grids)."""
        self._config = config
        self.update()

    def config(self) -> PerspectiveConfig:
        """Return the active :class:`PerspectiveConfig`."""
        return self._config

    def set_scene_rect(self, scene_rect: QRectF) -> None:
        """Track the document geometry (resize / document switch)."""
        self.prepareGeometryChange()
        self._rect = QRectF(scene_rect)
        self.update()

    def set_colors(self, line: QColor, horizon: QColor) -> None:
        """Set role-based overlay colours (legible in both themes, 025)."""
        self._line = QColor(line)
        self._horizon = QColor(horizon)
        self.update()

    # -- snap seam (pure geometry lives in logic/grids) -------------------

    def snap(
        self, sx: float, sy: float, anchor: Tuple[float, float], tolerance: float
    ) -> Optional[Tuple[float, float]]:
        """Direction-lock a cursor to the nearest vanishing line (delegates to logic).

        Returns the snapped point, or ``None`` if no line is within ``tolerance``
        (doc px). No geometry is computed here (Article I; REQ-P9-UI-005).
        """
        return perspective_snap(sx, sy, anchor, self._config, tolerance)

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
        """Stroke the vanishing-point guide fan and horizon line (Qt override)."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # The guide fan samples the canvas bottom edge toward each VP (render aid);
        # logic/grids builds the deterministic segments — none are computed here.
        edge_start = (self._rect.left(), self._rect.bottom())
        edge_end = (self._rect.right(), self._rect.bottom())
        guide_lines = perspective_guide_lines(
            self._config,
            self._samples,
            edge_start=edge_start,
            edge_end=edge_end,
        )
        pen = QPen(self._line)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        painter.drawLines(
            [QLineF(gl.p0[0], gl.p0[1], gl.p1[0], gl.p1[1]) for gl in guide_lines]
        )
        # Horizon line spanning the visible width.
        horizon_pen = QPen(self._horizon)
        horizon_pen.setCosmetic(True)
        horizon_pen.setWidth(0)
        painter.setPen(horizon_pen)
        y_h = self._config.horizon_y
        painter.drawLine(QLineF(self._rect.left(), y_h, self._rect.right(), y_h))
