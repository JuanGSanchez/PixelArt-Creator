"""Canvas scene — buffer rendering + tiled background (D1/D2/D3/D7).

``CanvasScene`` presents the active document layer's
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` as **one** whole-buffer
``QGraphicsPixmapItem`` (D1), fixes its scene rect once at init and on resize
(D3), and paints the checkerboard + optional per-pixel grid inside
``drawBackground(painter, rect)`` over **only** the exposed ``rect`` (D2). The
single-item scene uses ``NoIndex`` (D7). Rendering is nearest-neighbour with
anti-aliasing disabled at every zoom (REQ-P1-UI-001).

No domain logic lives here: pixels come from the logic buffer; this module only
maps that buffer to Qt paint calls (Article I).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QLineF, QObject, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    GRID_MIN_PIXEL_EDGE_PX,
    TILE_BUFFER,
    TILE_SIZE,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

#: Default role-based background colours (overridden by the active theme, 025).
_DEFAULT_CHECKER_LIGHT = QColor(200, 200, 200)
_DEFAULT_CHECKER_DARK = QColor(160, 160, 160)
_DEFAULT_GRID = QColor(120, 120, 120, 160)


class _BufferPixmapItem(QGraphicsPixmapItem):
    """One whole-buffer item drawing a live :class:`QImage` view of the buffer.

    For an RGBA buffer the ``QImage`` shares the buffer's NumPy memory, so pixel
    edits are reflected without a copy; only a dirty-rect repaint is scheduled
    (D5). For an indexed buffer a derived RGBA image is kept and re-synced over
    the changed region. Nothing is culled from the resident buffer (F7).
    """

    def __init__(
        self, buffer: PixelBuffer, palette_colors: List[Tuple[int, int, int, int]]
    ) -> None:
        super().__init__()
        self._buffer = buffer
        self._palette: List[Tuple[int, int, int, int]] = list(palette_colors)
        self._display: np.ndarray = np.empty((1, 1, 4), dtype=np.uint8)
        self._image = QImage()
        self._rebuild()

    def set_buffer(
        self,
        buffer: PixelBuffer,
        palette_colors: List[Tuple[int, int, int, int]],
    ) -> None:
        """Point the item at a new buffer/palette and rebuild the display image."""
        self.prepareGeometryChange()
        self._buffer = buffer
        self._palette = list(palette_colors)
        self._rebuild()
        self.update()

    def _rebuild(self) -> None:
        buf = self._buffer
        w, h = buf.width, buf.height
        if buf.mode is ColorMode.RGBA:
            # Zero-copy: the QImage shares the buffer's memory (live updates).
            self._display = buf.data
        else:
            self._display = np.zeros((h, w, 4), dtype=np.uint8)
            self._sync_indexed(0, 0, w, h)
        self._image = QImage(
            self._display.data,
            w,
            h,
            self._display.strides[0],
            QImage.Format.Format_RGBA8888,
        )
        # A single pixmap keeps the item a genuine QGraphicsPixmapItem (D1); the
        # live image is what paint() blits, so this is only a placeholder.
        self.setPixmap(QPixmap(1, 1))

    def _sync_indexed(self, x: int, y: int, w: int, h: int) -> None:
        if self._buffer.mode is ColorMode.RGBA or not self._palette:
            return
        lut = np.array(self._palette, dtype=np.uint8)
        idx = self._buffer.data[y : y + h, x : x + w]
        clamped = np.clip(idx, 0, len(self._palette) - 1)
        self._display[y : y + h, x : x + w] = lut[clamped]

    def sync_region(self, rect: QRectF) -> None:
        """Re-derive the indexed display over ``rect`` (no-op for RGBA)."""
        if self._buffer.mode is ColorMode.RGBA:
            return
        x0 = max(0, int(math.floor(rect.left())))
        y0 = max(0, int(math.floor(rect.top())))
        x1 = min(self._buffer.width, int(math.ceil(rect.right())))
        y1 = min(self._buffer.height, int(math.ceil(rect.bottom())))
        if x1 > x0 and y1 > y0:
            self._sync_indexed(x0, y0, x1 - x0, y1 - y0)

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        return QRectF(0, 0, self._buffer.width, self._buffer.height)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        # Blit only the exposed sub-rectangle (culls off-screen rendering, F7/D4).
        target = option.exposedRect.intersected(self.boundingRect())
        if target.isEmpty():
            return
        painter.drawImage(target, self._image, target)


class CanvasScene(QGraphicsScene):
    """Scene rendering the active document buffer + tiled background."""

    def __init__(self, document: Document, parent: Optional[QObject] = None) -> None:
        """Create the scene for ``document`` and fix its scene rect (D3)."""
        super().__init__(parent)
        # A single large pixmap item gains nothing from a BSP index (D7).
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self._document = document
        self._grid_enabled = False
        self._checker_light = QColor(_DEFAULT_CHECKER_LIGHT)
        self._checker_dark = QColor(_DEFAULT_CHECKER_DARK)
        self._grid_color = QColor(_DEFAULT_GRID)
        self._item = _BufferPixmapItem(self.active_buffer(), document.palette.colors())
        self.addItem(self._item)
        self._preview_item: Optional[QGraphicsLineItem] = None
        self.setSceneRect(0, 0, document.width, document.height)

    # -- line-tool preview (D5) ------------------------------------------

    def show_line_preview(
        self, x0: int, y0: int, x1: int, y1: int, color: RGBA
    ) -> None:
        """Show/update the line-tool preview; updates only its own rect (D5)."""
        if self._preview_item is None:
            self._preview_item = QGraphicsLineItem()
            self._preview_item.setZValue(1.0)
            self.addItem(self._preview_item)
        pen = QPen(QColor(*color))
        pen.setCosmetic(True)
        pen.setWidth(0)
        self._preview_item.setPen(pen)
        # +0.5 centres the preview on the pixel grid.
        self._preview_item.setLine(x0 + 0.5, y0 + 0.5, x1 + 0.5, y1 + 0.5)

    def hide_line_preview(self) -> None:
        """Remove the line-tool preview (no full-scene repaint)."""
        if self._preview_item is not None:
            self.removeItem(self._preview_item)
            self._preview_item = None

    # -- document binding -------------------------------------------------

    def active_buffer(self) -> PixelBuffer:
        """Return the active layer's buffer (top layer of the first frame)."""
        layers = self._document.frames[0].layers
        return layers[-1].buffer

    def set_document(self, document: Document) -> None:
        """Rebind the scene to a different document (tab switch, SC-UI-020-3)."""
        self._document = document
        self._item.set_buffer(self.active_buffer(), document.palette.colors())
        self.setSceneRect(0, 0, document.width, document.height)
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def on_document_resized(self, width: int, height: int) -> None:
        """Re-set the scene rect after ``Document.resize_canvas`` (D3, SC-UI-002-2)."""
        self._item.set_buffer(self.active_buffer(), self._document.palette.colors())
        self.setSceneRect(0, 0, width, height)

    # -- dirty-rect refresh (D5) -----------------------------------------

    def refresh_rect(self, rect: QRectF) -> None:
        """Repaint only ``rect`` after an edit — never a full-scene update (D5)."""
        self._item.sync_region(rect)
        self._item.update(rect)

    # -- grid overlay -----------------------------------------------------

    def set_grid_enabled(self, enabled: bool) -> None:
        """Toggle the per-pixel grid overlay (off by default, CL-4)."""
        self._grid_enabled = bool(enabled)
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def is_grid_enabled(self) -> bool:
        """Return whether the grid overlay is toggled on."""
        return self._grid_enabled

    # -- theming (025) ----------------------------------------------------

    def set_background_roles(
        self, checker_light: QColor, checker_dark: QColor, grid: QColor
    ) -> None:
        """Set role-based background colours (legible in both themes, 025)."""
        self._checker_light = QColor(checker_light)
        self._checker_dark = QColor(checker_dark)
        self._grid_color = QColor(grid)
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    # -- background -------------------------------------------------------

    def drawBackground(  # type: ignore[override]  # noqa: N802
        self, painter: QPainter, rect: QRectF
    ) -> None:
        """Paint checker + optional grid over ONLY the exposed ``rect`` (D2)."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Snap the tile loop to a TILE_SIZE grid, extend a TILE_BUFFER ring.
        left = math.floor(rect.left() / TILE_SIZE) - TILE_BUFFER
        top = math.floor(rect.top() / TILE_SIZE) - TILE_BUFFER
        right = math.ceil(rect.right() / TILE_SIZE) + TILE_BUFFER
        bottom = math.ceil(rect.bottom() / TILE_SIZE) + TILE_BUFFER

        for ty in range(top, bottom):
            for tx in range(left, right):
                colour = (
                    self._checker_light if (tx + ty) % 2 == 0 else self._checker_dark
                )
                painter.fillRect(
                    QRectF(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                    colour,
                )

        if (
            self._grid_enabled
            and self._pixel_edge_px(painter) >= GRID_MIN_PIXEL_EDGE_PX
        ):
            self._draw_grid(painter, rect)

    def _pixel_edge_px(self, painter: QPainter) -> float:
        """On-screen edge (device px) of one buffer pixel at the current zoom."""
        return abs(painter.worldTransform().m11())

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        pen = painter.pen()
        pen.setColor(self._grid_color)
        pen.setCosmetic(True)
        pen.setWidth(0)
        painter.setPen(pen)
        x0 = max(0, math.floor(rect.left()))
        x1 = min(self._document.width, math.ceil(rect.right()))
        y0 = max(0, math.floor(rect.top()))
        y1 = min(self._document.height, math.ceil(rect.bottom()))
        for x in range(x0, x1 + 1):
            painter.drawLine(QLineF(x, y0, x, y1))
        for y in range(y0, y1 + 1):
            painter.drawLine(QLineF(x0, y, x1, y))
