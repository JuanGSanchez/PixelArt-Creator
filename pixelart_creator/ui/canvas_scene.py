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
from PySide6.QtCore import QLineF, QObject, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QStyleOptionGraphicsItem,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    GRID_MIN_PIXEL_EDGE_PX,
    TILE_BUFFER,
    TILE_SIZE,
    TILED_PREVIEW_REPEAT,
)
from pixelart_creator.logic.document import Document, Layer
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.selection import SelectionMask

#: Default role-based background colours (overridden by the active theme, 025).
_DEFAULT_CHECKER_LIGHT = QColor(200, 200, 200)
_DEFAULT_CHECKER_DARK = QColor(160, 160, 160)
_DEFAULT_GRID = QColor(120, 120, 120, 160)

#: Longest-edge cap (px) of the cached downscaled tiled-preview pixmap. The dimmed
#: neighbour tiles are context only, so they render from one small cached pixmap
#: instead of the full-resolution 8K image blitted per neighbour per frame (OD-1,
#: AGT-10). Presentation-only sizing — not a domain tuning value (cf. _SWATCH_PX,
#: _preview_thumbnail max_edge in main_window); the resident buffer is never culled.
_TILED_PREVIEW_CACHE_MAX_EDGE = 512


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

    def current_image(self) -> QImage:
        """Return the live display image (shared with the tiled-preview item)."""
        return self._image

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


class _SelectionOverlayItem(QGraphicsItem):
    """Marching-ants outline of the active selection mask (REQ-P2-UI-007).

    Boundary edges are detected once (vectorised) when the mask is set; ``paint``
    culls to the exposed rect and strokes each edge twice — a solid dark pen under
    a dashed light pen — so the outline stays legible in **both** themes without a
    per-frame animation. A move offset shifts the drawn outline while a floating
    move is in progress (the pixels are committed only on release).
    """

    _Z = 2.0

    def __init__(self) -> None:
        super().__init__()
        self.setZValue(self._Z)
        self._w = 0
        self._h = 0
        self._edges: list[tuple[float, float, float, float]] = []
        self._offset = (0, 0)
        self._dark = QColor(0, 0, 0, 220)
        self._light = QColor(255, 255, 255, 220)

    def set_mask(self, mask: Optional[SelectionMask]) -> None:
        """Recompute the boundary edge segments from ``mask`` (or clear)."""
        self.prepareGeometryChange()
        self._offset = (0, 0)
        self._edges = []
        if mask is None or mask.is_empty:
            self._w = self._h = 0
            self.update()
            return
        data = mask.data()
        self._h, self._w = int(data.shape[0]), int(data.shape[1])
        self._edges = _boundary_edges(data)
        self.update()

    def set_move_offset(self, dx: int, dy: int) -> None:
        """Offset the drawn outline by ``(dx, dy)`` during a floating move."""
        self._offset = (int(dx), int(dy))
        self.update()

    def set_roles(self, dark: QColor, light: QColor) -> None:
        """Set the two ant colours (theme-legible high contrast)."""
        self._dark = QColor(dark)
        self._light = QColor(light)
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        if self._w <= 0 or self._h <= 0:
            return QRectF()
        ox, oy = self._offset
        return QRectF(ox - 1, oy - 1, self._w + 2, self._h + 2)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if not self._edges:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        ox, oy = self._offset
        exposed = option.exposedRect
        lines = [
            QLineF(x0 + ox, y0 + oy, x1 + ox, y1 + oy)
            for x0, y0, x1, y1 in self._edges
            if exposed.isEmpty()
            or exposed.intersects(
                QRectF(
                    min(x0, x1) + ox - 1,
                    min(y0, y1) + oy - 1,
                    abs(x1 - x0) + 2,
                    abs(y1 - y0) + 2,
                )
            )
        ]
        solid = QPen(self._dark)
        solid.setCosmetic(True)
        solid.setWidth(0)
        painter.setPen(solid)
        painter.drawLines(lines)
        dashed = QPen(self._light)
        dashed.setCosmetic(True)
        dashed.setWidth(0)
        dashed.setDashPattern([4.0, 4.0])
        painter.setPen(dashed)
        painter.drawLines(lines)


class _TiledPreviewItem(QGraphicsItem):
    """Repeating neighbour-tile preview around the editable centre tile (P2-UI-015).

    Draws a CACHED, downscaled pixmap of the buffer at the ``TILED_PREVIEW_REPEAT``
    x ``TILED_PREVIEW_REPEAT`` neighbour offsets (the centre tile is the real
    :class:`_BufferPixmapItem`, which keeps the single 8K bound). The cache is
    rebuilt only when the buffer changes (an edit marks it dirty) — never the full
    8K image blitted per neighbour per frame (OD-1, AGT-10). Nearest-neighbour, AA
    off; only the exposed neighbour rectangles are blitted (culling, D4/F7).
    Neighbours are dimmed so the editable tile reads as primary.
    """

    _Z = -0.5

    def __init__(self, source: _BufferPixmapItem) -> None:
        super().__init__()
        self.setZValue(self._Z)
        self._source = source
        self._w = 0
        self._h = 0
        self._span = TILED_PREVIEW_REPEAT
        self._cache: Optional[QPixmap] = None
        self._cache_dirty = True

    def set_source(self, source: _BufferPixmapItem) -> None:
        """Point the preview at a new buffer item (document / tab switch)."""
        self.prepareGeometryChange()
        self._source = source
        self.mark_dirty()

    def mark_dirty(self) -> None:
        """Invalidate the cached preview pixmap; it is rebuilt on the next paint."""
        self._cache_dirty = True
        self.update()

    def _ensure_cache(self) -> Optional[QPixmap]:
        """Return the cached downscaled pixmap, rebuilding it only when dirty."""
        if not self._cache_dirty and self._cache is not None:
            return self._cache
        image = self._source.current_image()
        iw, ih = image.width(), image.height()
        if iw <= 0 or ih <= 0:
            self._cache = None
            self._cache_dirty = False
            return None
        longest = max(iw, ih)
        if longest > _TILED_PREVIEW_CACHE_MAX_EDGE:
            scale = _TILED_PREVIEW_CACHE_MAX_EDGE / longest
            scaled = image.scaled(
                max(1, int(iw * scale)),
                max(1, int(ih * scale)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,  # nearest-neighbour
            )
        else:
            scaled = image
        self._cache = QPixmap.fromImage(scaled)
        self._cache_dirty = False
        return self._cache

    def _dims(self) -> tuple[int, int]:
        rect = self._source.boundingRect()
        return int(rect.width()), int(rect.height())

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        w, h = self._dims()
        half = self._span // 2
        return QRectF(-half * w, -half * h, self._span * w, self._span * h)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        w, h = self._dims()
        if w <= 0 or h <= 0:
            return
        pixmap = self._ensure_cache()
        if pixmap is None or pixmap.isNull():
            return
        pw, ph = pixmap.width(), pixmap.height()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setOpacity(0.55)
        half = self._span // 2
        exposed = option.exposedRect
        for row in range(-half, half + 1):
            for col in range(-half, half + 1):
                if row == 0 and col == 0:
                    continue  # the real buffer item owns the centre tile
                tile = QRectF(col * w, row * h, w, h)
                clipped = tile.intersected(exposed) if not exposed.isEmpty() else tile
                if clipped.isEmpty():
                    continue
                # Map the (culled) target sub-rect back into the cached pixmap.
                src = QRectF(
                    (clipped.left() - col * w) / w * pw,
                    (clipped.top() - row * h) / h * ph,
                    clipped.width() / w * pw,
                    clipped.height() / h * ph,
                )
                painter.drawPixmap(clipped, pixmap, src)


def _boundary_edges(
    data: "np.ndarray",
) -> list[tuple[float, float, float, float]]:
    """Return the outline edge segments of a boolean mask (pixel-corner coords).

    An edge is emitted on each side of a selected pixel whose neighbour on that
    side is unselected (or off-buffer), so the union traces the selection border.
    Detection is vectorised; the segment list feeds the marching-ants overlay.
    """
    edges: list[tuple[float, float, float, float]] = []
    top = data & ~np.pad(data, ((1, 0), (0, 0)))[:-1, :]
    bottom = data & ~np.pad(data, ((0, 1), (0, 0)))[1:, :]
    left = data & ~np.pad(data, ((0, 0), (1, 0)))[:, :-1]
    right = data & ~np.pad(data, ((0, 0), (0, 1)))[:, 1:]
    for y, x in zip(*np.nonzero(top)):
        edges.append((x, y, x + 1, y))
    for y, x in zip(*np.nonzero(bottom)):
        edges.append((x, y + 1, x + 1, y + 1))
    for y, x in zip(*np.nonzero(left)):
        edges.append((x, y, x, y + 1))
    for y, x in zip(*np.nonzero(right)):
        edges.append((x + 1, y, x + 1, y + 1))
    return edges


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
        self._shape_preview: Optional[QGraphicsItem] = None
        self._selection_overlay = _SelectionOverlayItem()
        self.addItem(self._selection_overlay)
        self._tiled_item = _TiledPreviewItem(self._item)
        self._tiled_item.setVisible(False)
        self.addItem(self._tiled_item)
        self._tiled_enabled = False
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
        return self.active_layer().buffer

    def active_layer(self) -> Layer:
        """Return the active :class:`Layer` (the transform/RotSprite holder)."""
        return self._document.frames[0].layers[-1]

    def set_document(self, document: Document) -> None:
        """Rebind the scene to a different document (tab switch, SC-UI-020-3)."""
        self._document = document
        self._item.set_buffer(self.active_buffer(), document.palette.colors())
        self._tiled_item.set_source(self._item)
        self._selection_overlay.set_mask(None)
        self._apply_scene_rect()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def on_document_resized(self, width: int, height: int) -> None:
        """Re-set the scene rect after ``Document.resize_canvas`` (D3, SC-UI-002-2)."""
        self._item.set_buffer(self.active_buffer(), self._document.palette.colors())
        self._apply_scene_rect()

    def rebind_active(self) -> None:
        """Re-point the scene at the active buffer after a whole-buffer swap.

        Called by :class:`~pixelart_creator.ui.commands.LogicCommand` for
        dimension-changing transforms / RotSprite: the logic ``FunctionCommand``
        has swapped ``Layer.buffer``, so the scene must re-read it and re-fix its
        rect (the document geometry is synced by the caller).
        """
        buffer = self.active_buffer()
        self._document.width = buffer.width
        self._document.height = buffer.height
        self._item.set_buffer(buffer, self._document.palette.colors())
        self._tiled_item.set_source(self._item)
        self._selection_overlay.set_mask(None)
        self._apply_scene_rect()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def _apply_scene_rect(self) -> None:
        """Set the scene rect, expanded for the tiled 3x3 preview when enabled."""
        w, h = self._document.width, self._document.height
        if self._tiled_enabled:
            half = TILED_PREVIEW_REPEAT // 2
            self.setSceneRect(-half * w, -half * h, TILED_PREVIEW_REPEAT * w, h * 3)
        else:
            self.setSceneRect(0, 0, w, h)

    # -- dirty-rect refresh (D5) -----------------------------------------

    def refresh_rect(self, rect: QRectF) -> None:
        """Repaint only ``rect`` after an edit — never a full-scene update (D5)."""
        self._item.sync_region(rect)
        self._item.update(rect)
        if self._tiled_enabled:
            self._tiled_item.mark_dirty()  # rebuild the cached preview pixmap (OD-1)

    def refresh_all(self) -> None:
        """Repaint the whole active buffer (one-shot ops: flip, selection edits)."""
        self._item.sync_region(self._item.boundingRect())
        self._item.update()
        if self._tiled_enabled:
            self._tiled_item.mark_dirty()  # rebuild the cached preview pixmap (OD-1)

    # -- shape / selection previews (D5) ---------------------------------

    def show_shape_preview(
        self,
        kind: str,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: RGBA,
        *,
        filled: bool = False,
        dashed: bool = False,
    ) -> None:
        """Show/update a live rectangle or ellipse preview (commit-free, D5).

        ``kind`` is ``"rectangle"`` or ``"ellipse"``. The preview is a vector
        item drawn with a cosmetic (zoom-independent) pen; it never mutates the
        buffer and pushes no command until the tool commits on release.
        """
        lx, rx = (x0, x1) if x0 <= x1 else (x1, x0)
        ty, by = (y0, y1) if y0 <= y1 else (y1, y0)
        rect = QRectF(lx, ty, rx - lx + 1, by - ty + 1)
        want_ellipse = kind == "ellipse"
        item = self._shape_preview
        if not isinstance(
            item, QGraphicsEllipseItem if want_ellipse else QGraphicsRectItem
        ):
            self._clear_shape_preview()
            item = QGraphicsEllipseItem() if want_ellipse else QGraphicsRectItem()
            item.setZValue(1.5)
            self.addItem(item)
            self._shape_preview = item
        pen = QPen(QColor(*color))
        pen.setCosmetic(True)
        pen.setWidth(0)
        if dashed:
            pen.setDashPattern([4.0, 4.0])
        item.setPen(pen)
        item.setBrush(
            QBrush(QColor(*color)) if filled else QBrush(Qt.BrushStyle.NoBrush)
        )
        item.setRect(rect)

    def show_polygon_preview(self, points: list[tuple[int, int]], color: RGBA) -> None:
        """Show/update the freehand lasso path preview (commit-free, D5)."""
        item = self._shape_preview
        if not isinstance(item, QGraphicsPolygonItem):
            self._clear_shape_preview()
            item = QGraphicsPolygonItem()
            item.setZValue(1.5)
            self.addItem(item)
            self._shape_preview = item
        pen = QPen(QColor(*color))
        pen.setCosmetic(True)
        pen.setWidth(0)
        pen.setDashPattern([4.0, 4.0])
        item.setPen(pen)
        item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        poly = QPolygonF([QPointF(px + 0.5, py + 0.5) for px, py in points])
        item.setPolygon(poly)

    def hide_shape_preview(self) -> None:
        """Remove any active shape/lasso preview (no full-scene repaint)."""
        self._clear_shape_preview()

    def _clear_shape_preview(self) -> None:
        if self._shape_preview is not None:
            self.removeItem(self._shape_preview)
            self._shape_preview = None

    # -- selection overlay (REQ-P2-UI-007) -------------------------------

    def set_selection_mask(self, mask: Optional[SelectionMask]) -> None:
        """Show ``mask`` as the marching-ants overlay (or clear it if ``None``)."""
        self._selection_overlay.set_mask(mask)

    def set_selection_move_offset(self, dx: int, dy: int) -> None:
        """Shift the selection outline during a floating move (pre-commit)."""
        self._selection_overlay.set_move_offset(dx, dy)

    # -- tiled mode (REQ-P2-UI-015) --------------------------------------

    def set_tiled_preview(self, enabled: bool) -> None:
        """Toggle the 3x3 repeating tile preview and expand/restore the rect."""
        self._tiled_enabled = bool(enabled)
        self._tiled_item.setVisible(self._tiled_enabled)
        if self._tiled_enabled:
            self._tiled_item.mark_dirty()  # refresh the cached preview on (re)enable
        self._apply_scene_rect()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def is_tiled_preview_enabled(self) -> bool:
        """Return whether the tiled 3x3 preview is active."""
        return self._tiled_enabled

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
