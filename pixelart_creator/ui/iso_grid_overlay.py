"""Isometric-grid overlay item (REQ-P9-UI-004) — Qt only, binds to logic/grids.

``Iso_Grid_Overlay`` is a high-``z`` :class:`QGraphicsItem` added to the shared
:class:`~pixelart_creator.ui.canvas_scene.CanvasScene`. It renders the 2:1-dimetric
diamond lattice by projecting cell indices through
:func:`~pixelart_creator.logic.grids.iso_world_to_screen` and snaps a cursor to the
nearest vertex via :func:`~pixelart_creator.logic.grids.iso_snap_vertex`. **All the
geometry lives in ``logic/grids``** — this overlay computes no transform/snap of its
own (Article I); it only maps the pure results to Qt paint calls.

Performance (Article VI, 16 ms): an LOD gate skips painting entirely when a tile's
on-screen edge (``tile_width * zoom``) drops below
:data:`~pixelart_creator.logic.constants.ISO_GRID_MIN_ON_SCREEN_EDGE_PX` (DIR-1),
drawing is culled to the ``exposedRect`` — only the ``(i, j)`` lattice lines
crossing the visible viewport are stroked and rasterisation is clipped to that rect
(DIR-2) — and the item uses ``DeviceCoordinateCache`` so a pan/zoom that does not
change the config reuses the rasterised grid (research §5.3). Together these restore
the fine-grid zoom-out budget AGT-10 measured at 722 ms. Cache mode / cull scope are
AGT-10-tunable (DEP-3); the geometry is never re-authored here.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from PySide6.QtCore import QLineF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.constants import ISO_GRID_MIN_ON_SCREEN_EDGE_PX
from pixelart_creator.logic.grids import (
    IsoGridConfig,
    iso_screen_to_world,
    iso_snap_vertex,
    iso_world_to_screen,
)

#: z-order above the buffer/selection overlays; the aids draw over the artwork.
_ISO_Z = 4.0

#: Default overlay line colour (overridden by the theme's role colour, 025).
_DEFAULT_LINE = QColor(90, 150, 220, 170)


class Iso_Grid_Overlay(QGraphicsItem):
    """Isometric-lattice overlay bound to :mod:`pixelart_creator.logic.grids`.

    Args:
        scene_rect: The document scene rect ``(0, 0, W, H)`` the overlay spans.
        config: The initial :class:`IsoGridConfig` (2:1 dimetric by default).
    """

    def __init__(
        self,
        scene_rect: QRectF,
        config: Optional[IsoGridConfig] = None,
    ) -> None:
        """Build the overlay for ``scene_rect`` with an optional iso ``config``."""
        super().__init__()
        self.setZValue(_ISO_Z)
        self.setVisible(False)
        # DeviceCoordinateCache: a pan/zoom that leaves the config unchanged reuses
        # the rasterised grid rather than re-stroking every line (research §5.3;
        # AGT-10 may re-tune this per its render directive, DEP-3).
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self._rect = QRectF(scene_rect)
        self._config = config if config is not None else IsoGridConfig()
        self._line = QColor(_DEFAULT_LINE)

    # -- configuration ----------------------------------------------------

    def set_config(self, config: IsoGridConfig) -> None:
        """Replace the iso config and repaint (validated in ``logic/grids``)."""
        self._config = config
        self.update()

    def config(self) -> IsoGridConfig:
        """Return the active :class:`IsoGridConfig`."""
        return self._config

    def set_scene_rect(self, scene_rect: QRectF) -> None:
        """Track the document geometry (resize / document switch)."""
        self.prepareGeometryChange()
        self._rect = QRectF(scene_rect)
        self.update()

    def set_line_color(self, color: QColor) -> None:
        """Set the role-based overlay line colour (legible in both themes, 025)."""
        self._line = QColor(color)
        self.update()

    # -- snap seam (pure geometry lives in logic/grids) -------------------

    def snap(self, sx: float, sy: float) -> Tuple[float, float]:
        """Snap a scene point to the nearest lattice vertex (delegates to logic).

        The overlay supplies the cursor; :func:`iso_snap_vertex` returns the snap
        point. No geometry is computed here (Article I; REQ-P9-UI-004).
        """
        return iso_snap_vertex(sx, sy, self._config)

    # -- QGraphicsItem ----------------------------------------------------

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        """Return the document scene rect the overlay spans (Qt override)."""
        return QRectF(self._rect)

    def _tile_on_screen_edge_px(self, painter: QPainter) -> float:
        """On-screen edge (device px) of one iso tile at the current zoom.

        Mirrors :meth:`CanvasScene._pixel_edge_px` (rectangular grid): the scale
        is read from ``painter.worldTransform().m11()`` — the same source the
        shipped grid gate uses — and multiplied by the tile's world width.
        """
        scale = abs(painter.worldTransform().m11())
        return self._config.tile_width * scale

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        """Stroke the visible iso lattice, LOD-gated and culled (Qt override)."""
        # DIR-1 LOD gate: when a tile's on-screen edge (tile_width * zoom) falls
        # below ISO_GRID_MIN_ON_SCREEN_EDGE_PX the lattice is too dense to read
        # and painting every line blows the 16 ms budget (AGT-10: 722 ms worst
        # case). Skip entirely — mirrors the GRID_MIN_PIXEL_EDGE_PX gate.
        if self._tile_on_screen_edge_px(painter) < ISO_GRID_MIN_ON_SCREEN_EDGE_PX:
            return
        exposed = option.exposedRect
        if exposed.isEmpty():
            exposed = self._rect
        exposed = exposed.intersected(self._rect)
        if exposed.isEmpty():
            return
        # DIR-2: clip rasterisation to the exposed viewport rect so paint cost
        # scales with the visible region — only the portion of each iso line
        # inside ``exposed`` is drawn (pure-Qt clip; no line-clipping math here).
        painter.save()
        painter.setClipRect(exposed)
        # Map the exposed viewport rect to the (i, j) lattice range that crosses
        # it (cull), then stroke only those constant-i / constant-j lines.
        corners = (
            (exposed.left(), exposed.top()),
            (exposed.right(), exposed.top()),
            (exposed.left(), exposed.bottom()),
            (exposed.right(), exposed.bottom()),
        )
        worlds = [iso_screen_to_world(cx, cy, self._config) for cx, cy in corners]
        i_vals = [w[0] for w in worlds]
        j_vals = [w[1] for w in worlds]
        i0 = math.floor(min(i_vals)) - 1
        i1 = math.ceil(max(i_vals)) + 1
        j0 = math.floor(min(j_vals)) - 1
        j1 = math.ceil(max(j_vals)) + 1

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(self._line)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        lines = []
        # Constant-i lines run j0..j1; constant-j lines run i0..i1.
        for i in range(i0, i1 + 1):
            p0 = iso_world_to_screen(i, j0, self._config)
            p1 = iso_world_to_screen(i, j1, self._config)
            lines.append(QLineF(p0[0], p0[1], p1[0], p1[1]))
        for j in range(j0, j1 + 1):
            p0 = iso_world_to_screen(i0, j, self._config)
            p1 = iso_world_to_screen(i1, j, self._config)
            lines.append(QLineF(p0[0], p0[1], p1[0], p1[1]))
        painter.drawLines(lines)
        painter.restore()
