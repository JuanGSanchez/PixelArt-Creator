"""Canvas scene — buffer rendering + tiled background (D1/D2/D3/D7).

``CanvasScene`` presents the active document layer's
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` as **one** whole-buffer
``QGraphicsPixmapItem`` (D1), fixes its scene rect once at init and on resize
(D3), and paints the checkerboard + optional per-pixel grid inside
``drawBackground(painter, rect)`` over **only** the exposed ``rect`` (D2). The
single-item scene uses ``NoIndex`` (D7). Rendering is nearest-neighbour with
anti-aliasing disabled at every zoom (REQ-P1-UI-001).

An attribute change (opacity/visibility/lock/blend-mode) recomposites only the
**exposed viewport rect ∩ canvas** (``refresh_visible``, D2) — never the whole
33 Mpx stack; the off-screen remainder is marked stale and refreshed lazily when
panned into view (``recomposite_exposed``). A live opacity-slider drag coalesces
to at most one viewport recomposite per frame (``refresh_visible_throttled``, D3).
The resident per-layer buffers are never culled — only the recomposited/redrawn
area is scoped (Article VI §3, F7).

No domain logic lives here: pixels come from the logic buffer; this module only
maps that buffer to Qt paint calls (Article I).
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QLineF, QObject, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QRegion,
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

from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    FRAME_BUDGET_MS,
    GRID_MIN_PIXEL_EDGE_PX,
    TILE_BUFFER,
    TILE_SIZE,
    TILED_PREVIEW_REPEAT,
)
from pixelart_creator.logic.document import (
    Document,
    Layer,
    LayerNode,
    iter_layers,
)
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
    """Scene rendering the active frame's composited layer stack + background.

    For an RGBA document the scene shows the **flattened composite** of the
    active frame's layer/group tree, produced by
    :func:`~pixelart_creator.logic.blend.composite_stack` (REQ-P4-UI-012); an
    edit recomposites only the affected **dirty region** via
    ``composite_stack(..., region=...)`` (ADR-0007, DEP-2). The resident
    per-layer buffers are never culled — only Qt rendering is (F7). An indexed
    document keeps the Phase-1 single-active-layer display (the compositor is
    RGBA-only), so palette-index workflows are unaffected.

    Paint tools target the panel-selected **active leaf layer** (or its mask
    while a mask is the edit target); the scene composites the whole stack for
    display. No compositing maths lives here — this module only calls the
    ``logic/blend`` compositor and maps its buffer to Qt paint calls (Article I).
    """

    def __init__(self, document: Document, parent: Optional[QObject] = None) -> None:
        """Create the scene for ``document`` and fix its scene rect (D3)."""
        super().__init__(parent)
        # A single large pixmap item gains nothing from a BSP index (D7).
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self._document = document
        self._frame_index = 0
        self._active_layer: Layer = self._default_active_layer()
        self._mask_edit = False
        # The compositor is RGBA-only; indexed docs keep the Phase-1 path.
        self._compositing = document.mode is ColorMode.RGBA
        self._composite: Optional[PixelBuffer] = None
        # Canvas area whose composite is stale — the off-screen remainder left
        # unrecomposited by a viewport-scoped attribute change (D2). Refreshed
        # lazily by recomposite_exposed() as it pans into view. Empty == clean.
        self._stale = QRegion()
        # One-shot throttle coalescing a live opacity-drag to <=1 recomposite
        # per frame (D3); the final value still commits as one QUndoCommand.
        self._live_timer = QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(FRAME_BUDGET_MS)
        self._live_timer.timeout.connect(self._flush_live_recomposite)
        self._live_pending = False
        if self._compositing:
            self._composite = PixelBuffer(
                document.width, document.height, ColorMode.RGBA
            )
            self._recomposite_all()
        self._grid_enabled = False
        self._checker_light = QColor(_DEFAULT_CHECKER_LIGHT)
        self._checker_dark = QColor(_DEFAULT_CHECKER_DARK)
        self._grid_color = QColor(_DEFAULT_GRID)
        self._item = _BufferPixmapItem(
            self._display_source(), document.palette.colors()
        )
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

    # -- compositing (REQ-P4-UI-012, ADR-0007) ---------------------------

    def _default_active_layer(self) -> Layer:
        """Return the topmost leaf layer of the active frame (paint default)."""
        leaves = iter_layers(self._document.frames[self._frame_index].layers)
        return leaves[-1]

    def _nodes(self) -> List[LayerNode]:
        """Return the active frame's top-level node list (bottom-to-top)."""
        return self._document.frames[self._frame_index].layers

    def _display_source(self) -> PixelBuffer:
        """Buffer the pixmap item shows: the composite (RGBA) or active layer."""
        if self._compositing and self._composite is not None:
            return self._composite
        return self.active_buffer()

    def _recomposite_all(self) -> None:
        """Recompose the whole stack into the resident composite buffer.

        Drops the frame's group flatten caches first: a whole-stack pass recomputes
        every group anyway, so clearing costs no D4 region-cache benefit yet
        guarantees no stale flatten survives a full refresh. This covers the
        non-``document`` buffer ops routed through :meth:`refresh_all`
        (tiled / transform / RotSprite / dither / cycle / swap / constraint /
        selection-move via :class:`~pixelart_creator.ui.commands.LogicCommand`),
        which — unlike the ``document`` attribute/structural ops — do not
        self-invalidate the group cache.
        """
        if self._composite is None:
            return
        self._document.invalidate_caches(frame_index=self._frame_index)
        w, h = self._document.width, self._document.height
        result = composite_stack(self._nodes(), w, h)
        self._composite.data[:, :, :] = result.data
        self._stale = QRegion()  # the whole composite is now fresh.

    def _recomposite_region(self, rect: QRectF) -> None:
        """Recompose only ``rect`` into the composite buffer (dirty-rect path, D1).

        ``composite_stack(region=(x,y,w,h))`` now returns a **region-sized**
        ``(h, w, 4)`` buffer whose origin is ``(x, y)`` (AGT-03 T13 / ADR-0007 D1),
        so the returned data blits straight into the resident scene buffer at that
        origin — no full-canvas indexing. The region is clamped to the canvas here
        (0 ≤ x0 < x1 ≤ w, 0 ≤ y0 < y1 ≤ h) so the compositor's bounds check never
        raises ``BlendError``.
        """
        if self._composite is None:
            return
        w, h = self._document.width, self._document.height
        x0 = max(0, int(math.floor(rect.left())))
        y0 = max(0, int(math.floor(rect.top())))
        x1 = min(w, int(math.ceil(rect.right())))
        y1 = min(h, int(math.ceil(rect.bottom())))
        if x1 <= x0 or y1 <= y0:
            return
        result = composite_stack(self._nodes(), w, h, region=(x0, y0, x1 - x0, y1 - y0))
        # D1: the returned buffer is region-sized (origin (x0, y0)), not full-canvas.
        self._composite.data[y0:y1, x0:x1, :] = result.data

    def _rebuild_composite(self) -> None:
        """(Re)allocate the composite buffer for the current document geometry."""
        self._compositing = self._document.mode is ColorMode.RGBA
        if self._compositing:
            self._composite = PixelBuffer(
                self._document.width, self._document.height, ColorMode.RGBA
            )
            self._recomposite_all()
        else:
            self._composite = None
            self._stale = QRegion()

    # -- document binding -------------------------------------------------

    def active_buffer(self) -> PixelBuffer:
        """Return the buffer paint tools mutate: the active layer's pixels, or
        its mask while a mask is the active edit target (REQ-P4-UI-009)."""
        if self._mask_edit and self._active_layer.mask is not None:
            return self._active_layer.mask
        return self._active_layer.buffer

    def active_layer(self) -> Layer:
        """Return the active leaf :class:`Layer` (paint / transform target).

        Narrowed to a leaf ``Layer`` — ``Frame.layers`` is now a tree of
        :class:`~pixelart_creator.logic.document.LayerNode` (leaf or group), so
        the transform/RotSprite holder is the panel-selected active leaf, not
        ``layers[-1]`` (which may be a group).
        """
        return self._active_layer

    def set_active_layer(self, layer: Layer) -> None:
        """Set the active leaf layer paint/transform ops target (REQ-P4-UI-001).

        For an indexed (non-composited) document the display re-points at the new
        active layer's buffer; for an RGBA document the composite is unchanged.
        """
        self._active_layer = layer
        self._mask_edit = False
        if not self._compositing:
            self._item.set_buffer(self.active_buffer(), self._document.palette.colors())

    def set_mask_edit(self, enabled: bool) -> None:
        """Route paint to the active layer's mask buffer, not its pixels
        (REQ-P4-UI-009). No-op unless the active layer carries a mask."""
        self._mask_edit = bool(enabled) and self._active_layer.mask is not None

    def is_mask_edit(self) -> bool:
        """Return whether paint currently targets the active layer's mask."""
        return self._mask_edit

    def is_active_editable(self) -> bool:
        """Whether a pixel-mutating paint on the active target is allowed.

        A locked or reference layer rejects paint (REQ-P4-UI-004/-010); a mask
        edit is always allowed (it modulates alpha, not the guarded pixels).
        """
        if self._mask_edit:
            return self._active_layer.mask is not None
        return not (self._active_layer.locked or self._active_layer.reference)

    def set_display_palette(self, colors: List[RGBA]) -> None:
        """Re-derive the indexed display from ``colors`` without touching pixels.

        Used by the non-destructive colour-cycling preview (REQ-P3-UI-012): the
        buffer indices are untouched; only the display LUT the item resolves them
        through changes. A no-op-equivalent for RGBA buffers (they ignore the LUT).
        """
        if self._compositing:
            return  # the RGBA composite ignores the palette LUT (P4-UI-012).
        self._item.set_buffer(self.active_buffer(), colors)
        if self._tiled_enabled:
            self._tiled_item.mark_dirty()

    def set_document(self, document: Document) -> None:
        """Rebind the scene to a different document (tab switch, SC-UI-020-3)."""
        self._document = document
        self._frame_index = 0
        self._active_layer = self._default_active_layer()
        self._mask_edit = False
        self._rebuild_composite()
        self._item.set_buffer(self._display_source(), document.palette.colors())
        self._tiled_item.set_source(self._item)
        self._selection_overlay.set_mask(None)
        self._apply_scene_rect()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def on_document_resized(self, width: int, height: int) -> None:
        """Re-set the scene rect after ``Document.resize_canvas`` (D3, SC-UI-002-2)."""
        self._rebuild_composite()
        self._item.set_buffer(self._display_source(), self._document.palette.colors())
        self._apply_scene_rect()

    def rebind_active(self) -> None:
        """Re-point the scene at the active buffer after a whole-buffer swap.

        Called by :class:`~pixelart_creator.ui.commands.LogicCommand` for
        dimension-changing transforms / RotSprite: the logic ``FunctionCommand``
        has swapped ``Layer.buffer``, so the scene must re-read it and re-fix its
        rect (the document geometry is synced by the caller).
        """
        buffer = self._active_layer.buffer
        self._document.width = buffer.width
        self._document.height = buffer.height
        self._rebuild_composite()
        self._item.set_buffer(self._display_source(), self._document.palette.colors())
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

    def _mark_tiled_dirty(self) -> None:
        """Invalidate the cached tiled-preview pixmap after a change (OD-1)."""
        if self._tiled_enabled:
            self._tiled_item.mark_dirty()

    def refresh_rect(self, rect: QRectF) -> None:
        """Repaint only ``rect`` after an edit — never a full-scene update (D5).

        When compositing, the dirty region is recomposited from the layer stack
        first (``composite_stack(region=...)``, ADR-0007) so the edit shows
        through the flattened view (REQ-P4-UI-012).
        """
        if self._compositing:
            self._recomposite_region(rect)
        self._item.sync_region(rect)
        self._item.update(rect)
        self._mark_tiled_dirty()

    def refresh_all(self) -> None:
        """Repaint the whole composite (structural ops, tab/geometry changes).

        A layer-**tree** change (add/remove/reorder/group/ungroup) recomposites
        the whole stack before repainting (REQ-P4-UI-013). Attribute changes take
        the viewport-scoped :meth:`refresh_visible` path instead (D2), never this.
        """
        if self._compositing:
            self._recomposite_all()
        self._item.sync_region(self._item.boundingRect())
        self._item.update()
        self._mark_tiled_dirty()

    # -- viewport-scoped attribute recomposite (D2/D3) -------------------

    def _visible_scene_rect(self) -> QRectF:
        """Union of the attached views' visible scene rects, clipped to canvas.

        Returns an **empty** rect when no live viewport is attached (e.g. the
        scene is momentarily view-less); callers fall back to a whole-canvas
        recomposite so the resident buffer stays correct.
        """
        visible = QRectF()
        for view in self.views():
            viewport = view.viewport()
            if viewport is None or viewport.rect().isEmpty():
                continue
            mapped = view.mapToScene(viewport.rect()).boundingRect()
            visible = visible.united(mapped)
        if visible.isEmpty():
            return QRectF()
        canvas = QRectF(0, 0, self._document.width, self._document.height)
        return visible.intersected(canvas)

    def refresh_visible(self) -> None:
        """Recomposite only the exposed viewport rect ∩ canvas (D2 attribute path).

        Opacity/visibility/lock/blend-mode changes affect a layer's whole extent,
        but only the region currently on screen must be recomposited **now**; the
        off-screen remainder is recorded as stale and refreshed lazily by
        :meth:`recomposite_exposed` when it pans into view (F2/F7 viewport culling
        applied to compositing). This never recomposites the whole 33 Mpx canvas.
        The resident per-layer buffers are never culled (Article VI §3, F7).
        """
        if not self._compositing:
            self._item.sync_region(self._item.boundingRect())
            self._item.update()
            self._mark_tiled_dirty()
            return
        visible = self._visible_scene_rect()
        if visible.isEmpty():
            # No live viewport — keep the whole composite correct (rare path).
            self._recomposite_all()
            self._item.sync_region(self._item.boundingRect())
            self._item.update()
            self._mark_tiled_dirty()
            return
        self._recomposite_region(visible)
        self._item.sync_region(visible)
        self._item.update(visible)
        canvas = QRect(0, 0, self._document.width, self._document.height)
        # The whole canvas minus the just-recomposited viewport is now stale.
        self._stale = QRegion(canvas).subtracted(QRegion(visible.toAlignedRect()))
        self._mark_tiled_dirty()

    def recomposite_exposed(self) -> None:
        """Refresh any stale composite region scrolled into view (lazy D2 follow-up).

        Called by the view after a pan/scroll/zoom. Recomposites the part of the
        stale set now visible and drops it from the stale region, so an off-screen
        attribute change becomes correct on pan without a full-canvas recomposite.
        A cheap no-op when nothing is stale.
        """
        if not self._compositing or self._stale.isEmpty():
            return
        visible = self._visible_scene_rect()
        if visible.isEmpty():
            return
        visible_region = QRegion(visible.toAlignedRect())
        exposed = self._stale.intersected(visible_region)
        if exposed.isEmpty():
            return
        rect = QRectF(exposed.boundingRect())
        self._recomposite_region(rect)
        self._item.sync_region(rect)
        self._item.update(rect)
        self._stale = self._stale.subtracted(visible_region)
        self._mark_tiled_dirty()

    def refresh_visible_throttled(self) -> None:
        """Coalesce a live opacity-drag to at most one recomposite per frame (D3).

        A slider drag emits a value change per pixel of travel; throttling routes
        them to one :meth:`refresh_visible` per :data:`FRAME_BUDGET_MS` frame
        (leading edge shows immediately, a trailing flush picks up the last value
        mid-frame). The authoritative final value still commits as exactly one
        ``QUndoCommand`` on slider release, whose redo takes the immediate
        :meth:`refresh_visible`.
        """
        if self._live_timer.isActive():
            self._live_pending = True
            return
        self.refresh_visible()
        self._live_timer.start()

    def _flush_live_recomposite(self) -> None:
        """Trailing-edge flush of a coalesced live drag (D3)."""
        if self._live_pending:
            self._live_pending = False
            self.refresh_visible()
            self._live_timer.start()

    def invalidate_group_caches(self) -> None:
        """Drop the frame's LayerGroup flatten caches after a pixel edit (D4 hook).

        Wired into :class:`~pixelart_creator.ui.commands.PaintCommand` on BOTH
        redo and undo (AGT-03 ``Document.invalidate_caches``) so a group's cached
        flatten can never serve a stale composite for the edited region
        (ADR-0007 D4). The whole active frame is cleared (``ref=None``): this is
        robust to active-layer / tree drift across undo history and costs only a
        lazy cache repopulation on the next region recomposite. No-op for an
        indexed (non-composited) document.
        """
        if not self._compositing:
            return
        self._document.invalidate_caches(frame_index=self._frame_index)

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
