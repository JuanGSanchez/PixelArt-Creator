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
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Set, Tuple

import numpy as np
from PySide6.QtCore import (
    QLineF,
    QObject,
    QPointF,
    QRect,
    QRectF,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
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

from pixelart_creator.logic.animation import AnimationError, onion_overlay
from pixelart_creator.logic.blend import (
    BlendError,
    BlendMode,
    blend_arrays,
    composite_range,
    composite_stack,
    downsample_nn,
    upsample_nn,
)
from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    FRAME_BUDGET_MS,
    GRID_MIN_PIXEL_EDGE_PX,
    OPACITY_PREVIEW_MAX_PX,
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
from pixelart_creator.logic.selection import (
    FloatingSelection,
    FloatMode,
    SelectionMask,
    composite_preview,
)
from pixelart_creator.ui.composite_warmer import (
    CompositeWarmSignals,
    FrameCompositeWarmRunnable,
)
from pixelart_creator.ui.frame_cache import FrameCompositeCache

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

#: Memory budget (bytes) of the DERIVED per-frame composite cache (D3, F7-safe).
#: Bounds the flattened render products only — the source layer buffers are NEVER
#: culled (Article VI §3). At 8K a composite is ~132 MB, so ~512 MiB keeps a small
#: residency window (a handful of frames) rather than the previous MAX_FRAMES-sized
#: ~1 GB dict; a cold frame beyond the window is re-warmed off-thread on demand.
#: Presentation/resource sizing — not a domain tuning value (cf.
#: _TILED_PREVIEW_CACHE_MAX_EDGE), so it lives here in ui/, not logic/constants.
_COMPOSITE_CACHE_BUDGET_BYTES = 512 * 1024 * 1024

#: Bounded wait (ms) for an in-flight off-thread warm to finish on tab close / app
#: quit before the pool is torn down. A single flatten is uninterruptible, so a
#: close mid-warm may wait up to one frame's flatten; new frames never start.
_WARM_SHUTDOWN_WAIT_MS = 5000


@dataclass
class _OpacityDragCache:
    """Drag-scoped split-cache for a live opacity-slider drag (Phase-12 Slice B).

    Built once at drag-start over the culled viewport rect ``(x, y, w, h)`` for a
    fixed top-level dragged index ``k`` and LOD factor ``factor`` (ADR-0034 §2 /
    the AGT-10 Slice-B directive §1). Holds the three **downsampled** inputs so
    each throttled tick re-blends ≈2 low-resolution buffers (holding the 16 ms
    ``FRAME_BUDGET_MS``) instead of recompositing the whole stack. It is discarded
    on commit / drag-end and invalidated on any non-opacity op, edit, pan/zoom,
    frame switch or geometry change (§2.3). It caches only DERIVED preview buffers;
    the resident per-layer source buffers are never touched (Article VI §3, F7).

    All compositing maths that produced these buffers live in ``logic/blend``
    (:func:`composite_range` / :func:`downsample_nn`); this record is presentation
    state only (the culled region + LOD inputs), holding no Qt objects, timers or
    threads — so it needs no teardown wiring (it is plain GC-able state).
    """

    #: Top-level index of the dragged node within the frame's sibling list.
    k: int
    #: Culled viewport region (scene space) the preview + commit operate over.
    region: Tuple[int, int, int, int]
    #: Integer nearest-neighbour LOD factor (>= 1) bounding the preview working set.
    factor: int
    #: NN-downsample of ``composite(siblings[:k])`` over the region (the backdrop).
    below_lod: np.ndarray
    #: NN-downsample of ``composite(siblings[k+1:])`` over the region (above stack).
    above_lod: np.ndarray
    #: NN-downsample of the dragged node's own contribution (captured at opacity 1).
    layer_lod: np.ndarray
    #: The dragged node's active blend mode (held constant during the drag).
    blend_mode: BlendMode


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


def _paint_checker_tiles(
    painter: QPainter, rect: QRectF, light: QColor, dark: QColor
) -> None:
    """Fill ``rect`` with the ``TILE_SIZE`` checkerboard (D2).

    Shared by :meth:`CanvasScene.drawBackground` and
    :class:`_FloatingPreviewItem` so a vacated (transparent) MOVE origin reads as
    the checker rather than the buffer pixmap beneath it. Tile indices use
    absolute scene coordinates, so the item's checker aligns pixel-perfectly with
    the scene background.
    """
    left = math.floor(rect.left() / TILE_SIZE) - TILE_BUFFER
    top = math.floor(rect.top() / TILE_SIZE) - TILE_BUFFER
    right = math.ceil(rect.right() / TILE_SIZE) + TILE_BUFFER
    bottom = math.ceil(rect.bottom() / TILE_SIZE) + TILE_BUFFER
    for ty in range(top, bottom):
        for tx in range(left, right):
            colour = light if (tx + ty) % 2 == 0 else dark
            painter.fillRect(
                QRectF(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE),
                colour,
            )


class _FloatingPreviewItem(QGraphicsItem):
    """One **bounded** region-scoped floating-preview layer (REQ-P2-UI-030/-035).

    Paints a single ``composite_preview`` region image over the canvas pixmap:
    the checker is repainted under the region so transparent (vacated) pixels
    read empty instead of showing the buffer pixmap, then the region image is
    blitted. Nearest-neighbour, anti-aliasing off, legible in **both** themes.

    The scene instantiates it **twice** so a MOVE drag never recomposites an
    area that grows with the drag distance (AGT-10 FB-8 / ADR-0009 D3 /
    ADR-0007 T13): a **floated-colours** layer bounded to the selection bbox,
    recomposited per drag frame (z ``_Z``); and a **vacated-origin** layer
    bounded to the fixed origin bbox, composited **once** at lift and reused for
    the whole gesture (z ``_ORIGIN_Z``, just below, so the floated colours draw
    over the origin where they overlap). Each layer's ``boundingRect`` stays a
    single selection bbox — never the union of origin + destination — so a long
    drag keeps a constant, bounded dirty/recomposite area.

    The base buffer is never written until commit — the compositing maths live
    entirely in ``logic/selection.composite_preview`` (Article I); this item
    only blits the returned image. ``ItemClipsToShape`` confines the checker
    ring to the item's region so no paint leaks under the view's
    ``DontSavePainterState`` flag.
    """

    _Z = 1.75
    _ORIGIN_Z = 1.70

    def __init__(self, z: float = _Z) -> None:
        super().__init__()
        self.setZValue(z)
        self.setVisible(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsToShape, True)
        self._region = QRectF()
        self._image = QImage()
        self._checker_light = QColor(_DEFAULT_CHECKER_LIGHT)
        self._checker_dark = QColor(_DEFAULT_CHECKER_DARK)

    def set_roles(self, light: QColor, dark: QColor) -> None:
        """Set the two checker colours (kept in step with the scene's, 025)."""
        self._checker_light = QColor(light)
        self._checker_dark = QColor(dark)
        self.update()

    def set_preview(self, image: QImage, region: QRectF) -> None:
        """Show ``image`` (owns its memory) covering ``region`` (scene coords)."""
        self.prepareGeometryChange()
        self._image = image
        self._region = QRectF(region)
        self.setVisible(not image.isNull() and not self._region.isEmpty())
        self.update()

    def clear_preview(self) -> None:
        """Hide the preview and drop its image (float committed / cancelled)."""
        self.prepareGeometryChange()
        self._image = QImage()
        self._region = QRectF()
        self.setVisible(False)
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        return QRectF(self._region)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if self._image.isNull() or self._region.isEmpty():
            return
        target = self._region
        exposed = option.exposedRect
        if not exposed.isEmpty():
            target = target.intersected(exposed)
        if target.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        # Repaint the checker so a vacated (transparent) MOVE origin reads empty
        # instead of showing the untouched buffer pixmap underneath.
        _paint_checker_tiles(painter, target, self._checker_light, self._checker_dark)
        # Map the (culled) target back into the region-local image coordinates.
        src = target.translated(-self._region.left(), -self._region.top())
        painter.drawImage(target, self._image, src)


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


class _OnionOverlayItem(QGraphicsItem):
    """Onion-skin ghosts drawn behind the active frame (REQ-P5-UI-011).

    Holds a list of pre-recoloured, distance-faded ghost :class:`QImage` s (the
    per-frame composites the Qt-free
    :func:`~pixelart_creator.logic.animation.onion_overlay` produced), ordered
    **farthest-first** so nearer ghosts draw on top. z is below the active buffer
    item (``0``) yet above the tiled preview (``-0.5``), so ghosts show through the
    active composite's transparent pixels. Only the exposed rect is blitted
    (culling, F7). Suppressed during playback (the scene clears it, CL-11).
    """

    _Z = -0.25

    def __init__(self) -> None:
        super().__init__()
        self.setZValue(self._Z)
        self.setVisible(False)
        self._ghosts: List[QImage] = []
        self._w = 0
        self._h = 0

    def set_ghosts(self, ghosts: List[QImage], width: int, height: int) -> None:
        """Show ``ghosts`` (farthest-first) covering the ``width`` × ``height`` area."""
        self.prepareGeometryChange()
        self._ghosts = ghosts
        self._w, self._h = int(width), int(height)
        self.setVisible(bool(ghosts))
        self.update()

    def clear(self) -> None:
        """Hide the overlay and drop its ghost images (onion off / playing)."""
        if not self._ghosts and not self.isVisible():
            return
        self.prepareGeometryChange()
        self._ghosts = []
        self.setVisible(False)
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        return QRectF(0, 0, self._w, self._h)

    def paint(  # noqa: N802 (Qt override)
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: Optional[QWidget] = None,
    ) -> None:
        if not self._ghosts:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        target = option.exposedRect.intersected(self.boundingRect())
        if target.isEmpty():
            target = self.boundingRect()
        if target.isEmpty():
            return
        for image in self._ghosts:
            painter.drawImage(target, image, target)


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

    Cold-frame playback pre-warm (D1/D2) is coordinated here but computed off the
    GUI thread: :meth:`prewarm_frames` dispatches each cold frame's flatten to a
    single-thread pool (:mod:`~pixelart_creator.ui.composite_warmer`) and each
    result lands in the bounded cache via a queued signal; the shell drives a
    progress indicator and the transport from :data:`prewarmStarted` /
    :data:`prewarmAdvanced` / :data:`prewarmFinished`.
    """

    #: Emitted with the number of frames a fresh warm will flatten (indicator show).
    prewarmStarted = Signal(int)
    #: Emitted ``(frame_index, done, total)`` as each cold frame is warmed (queued).
    prewarmAdvanced = Signal(int, int, int)
    #: Emitted when the warm completes or is cancelled (indicator hide).
    prewarmFinished = Signal()

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
        # Deferred-composite guard: __init__ allocates the resident composite
        # buffer but does NOT composite the stack into it (the eager full pass was
        # ~4.4 s at 8K and froze document open — AGT-10 standing flag). The buffer
        # starts zero-filled; the initial full composite is computed lazily on the
        # first paint (drawBackground, before the pixmap item blits it) or on any
        # earlier explicit read via _ensure_composite(). Scene construction is O(1).
        self._composite_dirty = False
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
        # Phase-12 Slice B (FU-16b / ADR-0034): the throttled per-tick action.
        # Normally the D2 viewport recomposite (refresh_visible); during a live
        # opacity drag it is REBOUND to the split-cache LOD preview and restored on
        # commit/cancel. No new timer/thread — the shipped 16 ms _live_timer above
        # drives it, so teardown is unchanged (the timer is already parent-owned).
        self._live_recomposite_fn: Callable[[], None] = self.refresh_visible
        #: Drag-scoped opacity split-cache (None when no drag is live).
        self._opacity_drag: Optional[_OpacityDragCache] = None
        # Per-frame flattened-composite cache (FU-19 / ADR-0011): scrub and
        # playback switch between pre-flattened frame buffers (a blit) instead of
        # re-flattening every layer per tick. ``self._composite`` is always the
        # cache entry for ``self._frame_index`` (all edit paths write into it, so
        # the active frame's entry never goes stale); a switch consults the cache
        # and rebuilds only on a MISS (deferred rebuild, never eager per switch).
        # Keyed by frame index; the whole cache is cleared on a structural frame op
        # (indices shift) via :meth:`refresh_frames`. Bounded by an LRU memory
        # budget (D3): only these DERIVED composites are culled, never the source
        # layer buffers (F7); the active frame is pinned so it is never evicted.
        self._frame_cache = FrameCompositeCache(_COMPOSITE_CACHE_BUDGET_BYTES)
        # Off-GUI-thread pre-warm (D1/D2): a dedicated single-thread pool flattens
        # cold frames via the Qt-free compositor and delivers each result to the
        # GUI thread through a QUEUED signal, so the scene owns the buffer only in
        # _on_frame_warmed. One thread serialises the flattens and caps peak float
        # memory. A warm ``token`` (bumped on start/cancel/edit/close) makes any
        # superseded result a no-op; the shared cancel event is a best-effort early
        # exit. Cancelled on Stop / edit / tab switch / close.
        self._warm_signals: Optional[CompositeWarmSignals] = CompositeWarmSignals()
        self._warm_signals.frameReady.connect(self._on_frame_warmed)
        self._warm_pool = QThreadPool(self)
        self._warm_pool.setMaxThreadCount(1)
        self._warm_cancel = threading.Event()
        self._warm_token = 0
        self._warm_inflight: Set[int] = set()
        self._warm_total = 0
        self._warm_done = 0
        self._warming = False
        # Onion-skin view state (REQ-P5-UI-011/-012); recomputed via the Qt-free
        # logic.onion_overlay. Suppressed while playing (CL-11) and during a scrub
        # drag (kept off the 16 ms budget — recomputed when the frame settles).
        self._onion_enabled = False
        self._onion_prev = 0
        self._onion_next = 0
        self._onion_tint_prev: RGBA = (255, 0, 0, 255)
        self._onion_tint_next: RGBA = (0, 0, 255, 255)
        self._playing = False
        if self._compositing:
            self._composite = PixelBuffer(
                document.width, document.height, ColorMode.RGBA
            )
            # Defer the full-stack composite to the first paint (O(1) construction).
            self._composite_dirty = True
            self._frame_cache.put(self._frame_index, self._composite)
            self._frame_cache.pin(self._frame_index)
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
        # Floating move/copy preview overlay (REQ-P2-UI-030..035); z below the
        # marching-ants overlay, above the buffer pixmap. Hidden until a lift.
        # The floated colours are recomposited per drag frame over ONLY their
        # (bounded) destination bbox; the vacated origin is a SEPARATE one-shot
        # layer just below, composited once at lift — so a long MOVE drag never
        # unions the two into a distance-growing region (AGT-10 FB-8).
        self._float_item = _FloatingPreviewItem()
        self._float_item.set_roles(self._checker_light, self._checker_dark)
        self.addItem(self._float_item)
        self._origin_item = _FloatingPreviewItem(z=_FloatingPreviewItem._ORIGIN_Z)
        self._origin_item.set_roles(self._checker_light, self._checker_dark)
        self.addItem(self._origin_item)
        self._floating_prev: QRectF = QRectF()
        #: Scene rect of the one-shot vacated-origin overlay (empty when none).
        self._origin_region: QRectF = QRectF()
        #: Whether the vacated-origin overlay is currently shown (MOVE only).
        self._origin_shown = False
        self._tiled_item = _TiledPreviewItem(self._item)
        self._tiled_item.setVisible(False)
        self.addItem(self._tiled_item)
        self._tiled_enabled = False
        # Onion ghosts draw behind the active frame composite (REQ-P5-UI-011).
        self._onion_item = _OnionOverlayItem()
        self.addItem(self._onion_item)
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
        self._composite_dirty = False  # deferred initial composite now computed.

    def _ensure_composite(self) -> None:
        """Compute the deferred initial composite on first paint/access (D1 guard).

        ``__init__`` allocates the resident composite buffer but leaves it
        zero-filled and marks it dirty rather than running the ~4.4 s full-stack
        composite eagerly (AGT-10 standing flag: "CanvasScene.__init__
        full-composites every RGBA doc"). This guard fills it exactly once — from
        :meth:`drawBackground` before the pixmap item blits it, or from any earlier
        explicit read of ``self._composite``. It is idempotent: a no-op once the
        composite is fresh, so the dirty-rect (region) recomposite fast paths are
        unaffected. The in-place write in :meth:`_recomposite_all` keeps the
        item's zero-copy ``QImage`` view valid, so no rebuild is needed. FLAGGED
        for an AGT-10 render-strategy re-profile.
        """
        if self._composite_dirty:
            self._recomposite_all()

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
        """(Re)allocate the composite buffer for the current document geometry.

        Drops the whole per-frame composite cache (geometry / tree / frame set may
        have changed, so every cached flatten is suspect) and re-registers the
        freshly recomposited active frame as its cache entry (FU-19 / ADR-0011).
        """
        self.cancel_opacity_drag()  # geometry change invalidates the drag cache (§2.3).
        self._compositing = self._document.mode is ColorMode.RGBA
        self._frame_cache.clear()
        if self._frame_index >= len(self._document.frames):
            self._frame_index = max(0, len(self._document.frames) - 1)
        if self._compositing:
            self._composite = PixelBuffer(
                self._document.width, self._document.height, ColorMode.RGBA
            )
            self._recomposite_all()
            self._frame_cache.put(self._frame_index, self._composite)
            self._frame_cache.pin(self._frame_index)
        else:
            self._composite = None
            self._stale = QRegion()

    # -- frame navigation + per-frame cache (REQ-P5-UI-002, FU-19) -------

    @property
    def frame_index(self) -> int:
        """The active (canvas-displayed) frame index."""
        return self._frame_index

    def set_frame_index(
        self, index: int, *, scrub: bool = False, block_on_miss: bool = True
    ) -> bool:
        """Display frame ``index`` (scrub / selection / playback, REQ-P5-UI-002).

        The FU-19 deferred-rebuild switch (ADR-0011): the current frame's live
        composite is stashed in the per-frame cache, then the target frame is
        served from the cache — a cheap blit on a HIT, a single ``composite_stack``
        flatten only on a MISS (never an eager per-switch full recomposite). Sets
        no document state → pushes no command (CL-13).

        ``scrub=True`` keeps the drag fast and **suppresses onion** (kept off the
        16 ms budget); a settled selection (``scrub=False``) recomputes the onion
        overlay. Playback advances with ``scrub=True`` and onion already cleared.

        ``block_on_miss=False`` (playback advance, D1/D2): on a cache MISS the
        ~20 s 8K flatten is **not** run on the GUI thread — the current display is
        held, an off-thread warm is ensured for ``index``, and ``False`` is
        returned so the transport waits and resumes on the streamed result. The
        default ``block_on_miss=True`` preserves the existing synchronous scrub /
        selection behaviour. Returns whether ``index`` is now displayed.
        """
        if not 0 <= index < len(self._document.frames):
            return False
        self.cancel_opacity_drag()  # a frame switch invalidates the drag cache (§2.3).
        if index == self._frame_index:
            # Re-selecting the current frame: nothing to switch, but a settled
            # selection may still need the onion overlay refreshed.
            if not scrub:
                self._update_onion()
            return True
        if (
            self._compositing
            and not block_on_miss
            and not self._frame_cache.contains(index)
        ):
            # Cold playback advance: never flatten on the GUI thread. Hold the
            # display, warm the frame off-thread, and let the transport resume on
            # the queued result (streaming, D1/D2).
            self._ensure_warm(index)
            return False
        # Stash the current live composite so a later switch back is a blit.
        if self._compositing and self._composite is not None:
            self._ensure_composite()
            self._frame_cache.put(self._frame_index, self._composite)
        self._frame_index = index
        self._active_layer = self._default_active_layer()
        self._mask_edit = False
        if self._compositing:
            self._composite = self._ensure_frame_composite(index)
            self._frame_cache.pin(index)
            self._composite_dirty = False
        self._item.set_buffer(self._display_source(), self._document.palette.colors())
        self._tiled_item.set_source(self._item)
        if scrub:
            self._onion_item.clear()
        else:
            self._update_onion()
        return True

    def _ensure_frame_composite(self, index: int) -> PixelBuffer:
        """Return frame ``index``'s flattened composite, building it on a miss.

        The per-frame cache hit path is a blit (the resident buffer is returned
        unchanged); the miss path flattens that frame's own layer stack **once**
        via :func:`~pixelart_creator.logic.blend.composite_stack` and caches it
        (FU-19). Only ever called for a compositing (RGBA) document. During
        playback the cold-frame flatten runs off-thread instead (see
        :meth:`prewarm_frames`); this synchronous path serves scrub / selection.
        """
        cached = self._frame_cache.get(index)
        if cached is not None:
            return cached
        w, h = self._document.width, self._document.height
        self._document.invalidate_caches(frame_index=index)
        result = composite_stack(self._document.frames[index].layers, w, h)
        self._frame_cache.put(index, result)
        return result

    # -- off-thread playback pre-warm (D1/D2) ----------------------------

    def is_frame_warm(self, index: int) -> bool:
        """Return whether frame ``index`` can be shown without a GUI-thread flatten.

        True for a non-compositing (indexed) document (no flatten needed), for the
        currently displayed frame, and for any frame resident in the derived
        composite cache. The transport consults this to decide whether to advance
        immediately (a blit) or wait for an off-thread warm (D1/D2).
        """
        if not self._compositing:
            return True
        if index == self._frame_index:
            return True
        return self._frame_cache.contains(index)

    def prewarm_frames(self, order: Sequence[int]) -> None:
        """Warm the cold frames in ``order`` off the GUI thread (D1/D2).

        Opens a fresh warm session (new token; the shared cancel is cleared and any
        queued runnables from a prior session are dropped) and dispatches each cold
        frame — one whose composite is not already resident and is not the active
        frame — to the single-thread pool in visitation order, so the earliest
        frames playback needs are flattened first. A no-op for a non-compositing
        document; when nothing is cold the transport streams at cache-hit speed
        (no indicator shown).
        """
        if not self._compositing or self._warm_signals is None:
            return
        self._warm_token += 1
        self._warm_cancel.clear()
        self._warm_pool.clear()
        self._warm_inflight.clear()
        self._warm_total = 0
        self._warm_done = 0
        self._warming = False
        misses = [
            i
            for i in order
            if 0 <= i < len(self._document.frames)
            and i != self._frame_index
            and not self._frame_cache.contains(i)
        ]
        if not misses:
            return
        self._warm_total = len(misses)
        self._warming = True
        self.prewarmStarted.emit(self._warm_total)
        for index in misses:
            self._dispatch_warm(index)

    def _ensure_warm(self, index: int) -> None:
        """Warm frame ``index`` off-thread on demand unless already covered.

        Skips a frame already resident or already in flight; self-healing for a
        frame the bounded cache evicted before playback reached it (re-warmed
        here). Opens a fresh warm episode if none is active (the initial batch
        already finished), otherwise just extends the current one. It never signals
        the frame as *ready* — only :meth:`_on_frame_warmed` does, on the actual
        completion — so the transport never resumes on a not-yet-flattened frame.
        """
        if not self._compositing or self._warm_signals is None:
            return
        if not 0 <= index < len(self._document.frames):
            return
        if self._frame_cache.contains(index) or index in self._warm_inflight:
            return
        started = not self._warming
        if started:
            self._warm_total = 0
            self._warm_done = 0
            self._warming = True
        self._warm_total += 1
        self._dispatch_warm(index)
        if started:
            self.prewarmStarted.emit(self._warm_total)

    def _dispatch_warm(self, index: int) -> None:
        """Queue frame ``index``'s flatten on the pool (invalidate caches first).

        Invalidates the frame's group caches on the GUI thread before dispatch so
        the off-thread flatten recomputes a correct composite, then starts a
        runnable carrying the current warm token.
        """
        self._document.invalidate_caches(frame_index=index)
        self._warm_inflight.add(index)
        signals = self._warm_signals
        if signals is None:
            # The warm subsystem has been shut down (scene/tab teardown); never
            # dispatch a runnable with a released carrier.
            return
        runnable = FrameCompositeWarmRunnable(
            self._warm_token,
            index,
            self._document.frames[index].layers,
            self._document.width,
            self._document.height,
            self._warm_cancel,
            signals,
        )
        self._warm_pool.start(runnable)

    def _on_frame_warmed(self, token: int, index: int, buffer: object) -> None:
        """Receive a warmed composite on the GUI thread and cache it (queued, D2).

        Ignores a result whose ``token`` no longer matches the active warm session
        (the warm was cancelled, superseded or the document mutated). The scene
        takes ownership of the buffer only here, on the GUI thread; it is stored in
        the bounded cache and the transport is nudged via :data:`prewarmAdvanced`.
        """
        if token != self._warm_token:
            return
        self._warm_inflight.discard(index)
        if not isinstance(buffer, PixelBuffer):
            return
        self._frame_cache.put(index, buffer)
        self._warm_done += 1
        self.prewarmAdvanced.emit(index, self._warm_done, self._warm_total)
        if self._warm_done >= self._warm_total:
            self._warming = False
            self.prewarmFinished.emit()

    def cancel_prewarm(self) -> None:
        """Cancel any in-flight warm (Stop / edit / tab switch, D2).

        Bumps the token so every in-flight result becomes a no-op, sets the shared
        cancel event (best-effort early exit) and drops queued runnables. Cheap and
        idempotent when no warm is active.
        """
        if not self._warming and not self._warm_inflight:
            return
        self._warm_token += 1
        self._warm_cancel.set()
        self._warm_pool.clear()
        self._warm_inflight.clear()
        self._warm_total = 0
        self._warm_done = 0
        was_warming = self._warming
        self._warming = False
        if was_warming:
            self.prewarmFinished.emit()

    def shutdown_prewarm(self) -> None:
        """Deterministically tear the off-thread warm down (idempotent, D2).

        Invoked on scene/tab disposal, document replace and window close, and by
        tests in a teardown fixture. It does NOT rely on the Qt event loop
        spinning. In order it:

        1. bumps the warm token so any queued or in-flight result is a no-op;
        2. sets the shared cancel event (best-effort early exit for the flatten);
        3. drops queued runnables (``clear``) and **blocks** (bounded) on
           ``waitForDone`` until the running flatten finishes AND the pool's
           worker threads are removed — so no native worker survives into a
           later GC cycle (the PySide6 cross-thread GC-of-Qt-C++ segfault);
        4. disconnects and releases the GUI-thread ``CompositeWarmSignals``
           carrier, so any still-queued ``frameReady`` emission has no slot to
           land on a torn-down scene and the carrier can be collected without a
           live cross-thread connection.

        A single flatten is uninterruptible, so a close mid-warm may wait up to
        one frame's flatten. Safe to call repeatedly (subsequent calls are a
        cheap no-op once the carrier is released).

        The Phase-12 opacity-drag split-cache is also dropped here: it is plain
        GC-able numpy/state (no Qt object, timer or thread — it reuses the shipped
        ``_live_timer``), so this needs no event-loop spin; it just releases the
        cached preview buffers deterministically on teardown.
        """
        self.cancel_opacity_drag()
        self._warm_token += 1
        self._warm_cancel.set()
        self._warm_pool.clear()
        self._warm_pool.waitForDone(_WARM_SHUTDOWN_WAIT_MS)
        self._warm_inflight.clear()
        self._warm_total = 0
        self._warm_done = 0
        self._warming = False
        signals = self._warm_signals
        if signals is not None:
            # Drop the cross-thread connection so no queued emission is delivered
            # to _on_frame_warmed after teardown, and release the carrier. A
            # runnable still running keeps its own reference alive, so its emit()
            # is a harmless no-op against the now-disconnected carrier.
            try:
                signals.frameReady.disconnect(self._on_frame_warmed)
            except (RuntimeError, TypeError):
                # Already disconnected / carrier already torn down — idempotent.
                pass
            self._warm_signals = None

    def refresh_frames(self, index: Optional[int] = None) -> None:
        """Rebind after a structural frame op (add/remove/reorder/duplicate).

        Called by the :class:`~pixelart_creator.ui.commands.FrameCommand` refresh
        hook: the frames list changed so cached composites (keyed by index) are
        cleared and the active frame — clamped, or set to ``index`` when given — is
        recomposited fresh (:meth:`_rebuild_composite`). Onion is recomputed for
        the settled frame. Any in-flight warm is cancelled — the frame set changed,
        so its indices and results are stale.
        """
        self.cancel_prewarm()
        self.cancel_opacity_drag()  # a frame op invalidates the drag cache (§2.3).
        if index is not None and 0 <= index < len(self._document.frames):
            self._frame_index = index
        self._active_layer = self._default_active_layer()
        self._mask_edit = False
        self._rebuild_composite()
        self._item.set_buffer(self._display_source(), self._document.palette.colors())
        self._tiled_item.set_source(self._item)
        self._update_onion()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    # -- onion skinning (REQ-P5-UI-011/-012) -----------------------------

    def set_playing(self, playing: bool) -> None:
        """Toggle playback state; onion is suppressed while playing (CL-11)."""
        self._playing = bool(playing)
        if self._playing:
            self._onion_item.clear()
        else:
            self._update_onion()

    def set_onion_settings(
        self,
        enabled: bool,
        prev_count: int,
        next_count: int,
        tint_prev: RGBA,
        tint_next: RGBA,
    ) -> None:
        """Apply the onion view settings and recompute the overlay live (UI-012).

        View settings only — no document mutation, no undo (CL-13).
        """
        self._onion_enabled = bool(enabled)
        self._onion_prev = int(prev_count)
        self._onion_next = int(next_count)
        self._onion_tint_prev = tint_prev
        self._onion_tint_next = tint_next
        self._update_onion()

    def _update_onion(self) -> None:
        """Recompute the onion ghosts for the active frame (Qt-free maths in logic).

        Gathers the nearest-first previous/next frame layer stacks around the
        active frame and delegates the composite + distance-fade + z-order to
        :func:`~pixelart_creator.logic.animation.onion_overlay` (S11 — no onion
        maths here). Suppressed when disabled, while playing, or for a
        non-compositing (indexed) document (the compositor is RGBA-only).
        """
        if not self._onion_enabled or self._playing or not self._compositing:
            self._onion_item.clear()
            return
        frames = self._document.frames
        active = self._frame_index
        count = len(frames)
        prev_stacks = [
            frames[active - d].layers
            for d in range(1, self._onion_prev + 1)
            if active - d >= 0
        ]
        next_stacks = [
            frames[active + d].layers
            for d in range(1, self._onion_next + 1)
            if active + d < count
        ]
        if not prev_stacks and not next_stacks:
            self._onion_item.clear()
            return
        w, h = self._document.width, self._document.height
        try:
            contributions = onion_overlay(prev_stacks, next_stacks, w, h)
        except (AnimationError, BlendError):
            self._onion_item.clear()
            return
        prev_len = len(prev_stacks)
        ordered: List[Tuple[int, QImage]] = []
        for i, contribution in enumerate(contributions):
            tint = self._onion_tint_prev if i < prev_len else self._onion_tint_next
            image = self._recolor_silhouette(
                self._preview_qimage(contribution.buffer), tint
            )
            ordered.append((contribution.z_order, image))
        # z_order is -distance; ascending order draws the farthest ghost first so
        # nearer ghosts render on top (matching the logic's z semantics).
        ordered.sort(key=lambda pair: pair[0])
        self._onion_item.set_ghosts([image for _z, image in ordered], w, h)
        self.update(self._onion_item.boundingRect())

    @staticmethod
    def _recolor_silhouette(image: QImage, tint: RGBA) -> QImage:
        """Recolour an alpha silhouette to ``tint``, preserving per-pixel alpha.

        Presentation-only styling — the same class of Qt-side visual choice as the
        marching-ants colours or the tiled-preview dimming (``setOpacity``): an
        onion ghost is an ephemeral view overlay that never becomes document
        pixels, so its *display* tint is applied here in Qt while the composite,
        distance-fade and z-order MATHS stay in ``logic.onion_overlay`` (S11). The
        silhouette's alpha (already faded by distance) is kept; only its RGB is set
        to the configured tint via ``CompositionMode_SourceIn`` (REQ-P5-UI-012).
        """
        base = image.convertToFormat(QImage.Format.Format_RGBA8888)
        out = QImage(base.size(), QImage.Format.Format_RGBA8888)
        out.fill(0)
        painter = QPainter(out)
        painter.drawImage(0, 0, base)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(out.rect(), QColor(*tint))
        painter.end()
        return out

    # -- document binding -------------------------------------------------

    def active_buffer(self) -> PixelBuffer:
        """Return the buffer paint tools mutate.

        This is the active layer's pixels, or its mask while a mask is the
        active edit target (REQ-P4-UI-009).
        """
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
        """Route paint to the active layer's mask buffer, not its pixels.

        No-op unless the active layer carries a mask (REQ-P4-UI-009).
        """
        self._mask_edit = bool(enabled) and self._active_layer.mask is not None

    def is_mask_edit(self) -> bool:
        """Return whether paint currently targets the active layer's mask."""
        return self._mask_edit

    def is_active_editable(self) -> bool:
        """Whether a pixel-mutating paint on the active target is allowed.

        A locked, reference, or smart layer rejects paint (REQ-P4-UI-004/-010;
        CF-11: a smart layer's pixels are derived, not directly editable); a
        mask edit is always allowed (it modulates alpha, not the guarded pixels).
        """
        if self._mask_edit:
            return self._active_layer.mask is not None
        return not (
            self._active_layer.locked
            or self._active_layer.reference
            or self._active_layer.smart_source is not None
        )

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
        self._update_onion()
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
        through the flattened view (REQ-P4-UI-012). A pixel edit mutates a source
        buffer, so any in-flight warm reading it is cancelled (D2 no-race).
        """
        self.cancel_prewarm()
        self.cancel_opacity_drag()  # a pixel edit invalidates the drag cache (§2.3).
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
        A tree change invalidates the warmed frame composites, so any in-flight
        warm is cancelled (D2 no-race).
        """
        self.cancel_prewarm()
        self.cancel_opacity_drag()  # a structural op invalidates the drag cache (§2.3).
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
        The resident per-layer buffers are never culled (Article VI §3, F7). An
        attribute change alters the composite, so any in-flight warm is cancelled
        (D2 no-race).

        Phase-12 Slice B: when this is the **commit** of a live opacity drag (the
        one attribute op pushed on slider release, whose ``LayerCommand`` redo calls
        this), it takes the byte-exact split-cache suffix re-blend
        (:meth:`_commit_opacity_drag`) instead of the naive full-stack region
        recomposite — the committed pixels are byte-identical either way (ADR-0034
        §3), the split-cache path is just the bounded one.
        """
        if self._opacity_drag is not None:
            self._commit_opacity_drag()
            return
        self.cancel_prewarm()
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
        # A pan/zoom changes the culled region V, invalidating the drag cache (§2.3);
        # the rest of the drag then uses the naive byte-exact path.
        self.cancel_opacity_drag()
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
        them to one per-tick action per :data:`FRAME_BUDGET_MS` frame (leading edge
        shows immediately, a trailing flush picks up the last value mid-frame). The
        per-tick action is :attr:`_live_recomposite_fn`: the D2
        :meth:`refresh_visible` normally, or the Phase-12 Slice-B split-cache LOD
        preview while an opacity drag is live (ADR-0034 §3.1 — same shipped timer,
        rebound action). The authoritative final value still commits as exactly one
        ``QUndoCommand`` on slider release, whose redo recomposites full-resolution
        + byte-exact (:meth:`refresh_visible`).
        """
        if self._live_timer.isActive():
            self._live_pending = True
            return
        self._live_recomposite_fn()
        self._live_timer.start()

    def _flush_live_recomposite(self) -> None:
        """Trailing-edge flush of a coalesced live drag (D3)."""
        if self._live_pending:
            self._live_pending = False
            self._live_recomposite_fn()
            self._live_timer.start()

    # -- live opacity-drag split-cache preview + byte-exact commit -------
    #    (Phase-12 Slice B / FU-16b / ADR-0034; AGT-10 Slice-B directive §1-§4)

    def _lod_factor(self, w: int, h: int) -> int:
        """NN LOD factor bounding the preview to :data:`OPACITY_PREVIEW_MAX_PX` px.

        ``D = max(1, ceil(sqrt(area / OPACITY_PREVIEW_MAX_PX)))`` (ADR-0034 §1.3):
        the per-tick preview re-blend then runs over ``<= OPACITY_PREVIEW_MAX_PX``
        px regardless of viewport size, so it holds the 16 ms budget with 2-core
        headroom. Presentation-only LOD policy — the pixel budget itself is the
        single-source logic constant (Article II); no compositing maths here.
        """
        area = max(1, int(w) * int(h))
        return max(1, int(math.ceil(math.sqrt(area / OPACITY_PREVIEW_MAX_PX))))

    def _clamp_visible_region(self) -> Optional[Tuple[int, int, int, int]]:
        """Exposed viewport ∩ canvas as an integer ``(x, y, w, h)`` region.

        ``None`` when no live viewport is attached or the intersection is
        degenerate (the caller then falls back to a whole-canvas path). Mirrors the
        clamping in :meth:`_recomposite_region` so the compositor's bounds check
        never raises.
        """
        visible = self._visible_scene_rect()
        if visible.isEmpty():
            return None
        w, h = self._document.width, self._document.height
        x0 = max(0, int(math.floor(visible.left())))
        y0 = max(0, int(math.floor(visible.top())))
        x1 = min(w, int(math.ceil(visible.right())))
        y1 = min(h, int(math.ceil(visible.bottom())))
        if x1 <= x0 or y1 <= y0:
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    def begin_opacity_drag(self, path: Sequence[int]) -> bool:
        """Build the drag-scoped split-cache for a live opacity drag (ADR-0034 §2).

        Called on ``sliderPressed`` from the layer panel with the dragged node's
        logic index ``path``. Returns ``True`` when the split-cache LOD preview is
        engaged (top-level node, compositing document, a live viewport); ``False``
        when not applicable (indexed doc, a nested node, or no viewport), in which
        case the caller keeps the shipped naive throttled recomposite — both give a
        byte-exact commit, only the during-drag feedback differs. Never raises into
        the GUI: any compositor error falls back to the naive path.

        Only a **top-level** dragged node is split here: the seam splits one flat
        sibling list and the scene composites the top-level node list. A node nested
        in a group changes the group's flattened output (the group is one node in
        the top-level list), which the single-level split does not isolate — those
        keep the naive viewport recomposite (still byte-exact on commit).
        """
        self.cancel_opacity_drag()
        if not self._compositing or self._composite is None:
            return False
        if len(path) != 1:
            return False
        nodes = self._nodes()
        k = int(path[0])
        if not (0 <= k < len(nodes)):
            return False
        region = self._clamp_visible_region()
        if region is None:
            return False
        _, _, w, h = region
        factor = self._lod_factor(w, h)
        node = nodes[k]
        cw, ch = self._document.width, self._document.height
        try:
            below = composite_range(nodes, cw, ch, 0, k, region=region)
            above = composite_range(nodes, cw, ch, k + 1, len(nodes), region=region)
            # Capture the dragged node's own contribution at opacity 1 so each tick
            # can scale it by the live opacity; the opacity is restored at once.
            saved = node.opacity
            node.opacity = 1.0
            try:
                layer = composite_range(nodes, cw, ch, k, k + 1, region=region)
            finally:
                node.opacity = saved
            self._opacity_drag = _OpacityDragCache(
                k=k,
                region=region,
                factor=factor,
                below_lod=downsample_nn(below.data, factor),
                above_lod=downsample_nn(above.data, factor),
                layer_lod=downsample_nn(layer.data, factor),
                blend_mode=node.blend_mode,
            )
        except BlendError:
            self._opacity_drag = None
            return False
        self._live_recomposite_fn = self._preview_opacity_drag
        return True

    def _preview_opacity_drag(self) -> None:
        """Render one LOD preview tick from the split-cache (ADR-0034 §1; 16 ms).

        Two low-resolution blends via the ``logic/blend`` seam —
        ``preview = above_lod OVER (layer_lod · o [node mode] below_lod)`` — over
        the bounded ``<= OPACITY_PREVIEW_MAX_PX`` working set, upsampled
        nearest-neighbour and blitted through the existing dirty-rect path. The
        transient low-res approximation living in the resident composite during the
        drag is acceptable because commit overwrites it byte-exact. No compositing
        maths here — every blend / scale is a logic-seam call.
        """
        cache = self._opacity_drag
        if cache is None or self._composite is None:
            return
        nodes = self._nodes()
        if not (0 <= cache.k < len(nodes)):
            self.cancel_opacity_drag()
            return
        opacity = float(nodes[cache.k].opacity)
        x, y, w, h = cache.region
        lit = blend_arrays(
            cache.blend_mode, cache.layer_lod, cache.below_lod, opacity=opacity
        )
        preview_lod = blend_arrays(BlendMode.NORMAL, cache.above_lod, lit)
        preview = upsample_nn(preview_lod, cache.factor, out_shape=(h, w))
        self._composite.data[y : y + h, x : x + w, :] = preview
        rect = QRectF(x, y, w, h)
        self._item.sync_region(rect)
        self._item.update(rect)
        self._mark_tiled_dirty()

    def _commit_opacity_drag(self) -> None:
        """Byte-exact full-resolution commit of the opacity drag (ADR-0034 §3).

        Runs from :meth:`refresh_visible` when the opacity ``LayerCommand`` redo
        fires on slider release. Uses the ALWAYS-correct suffix re-blend over the
        culled region — ``commit = composite_range(nodes, k, N, base=below_full)``
        with ``below_full = composite_range(nodes, 0, k)`` — which is byte-identical
        to ``composite_stack`` over the region for NORMAL *and* all 11 separable
        modes (the exact prefix substituted by its exact cache). This is **not** the
        ``above``-pre-flatten fast path (that can diverge ``<= 2`` LSB on
        partial-alpha content); the commit is a batch path, not asserted against the
        16 ms budget. The drag cache is then discarded and the throttled action
        restored to the naive path.
        """
        self._live_pending = False
        cache = self._opacity_drag
        self._opacity_drag = None
        self._live_recomposite_fn = self.refresh_visible
        if self._composite is None or cache is None:
            return
        self.cancel_prewarm()
        nodes = self._nodes()
        k = cache.k
        region = self._clamp_visible_region()
        if region is None or not (0 <= k < len(nodes)):
            # No live viewport (rare) — keep the whole composite correct, byte-exact.
            self._recomposite_all()
            self._item.sync_region(self._item.boundingRect())
            self._item.update()
            self._mark_tiled_dirty()
            return
        x, y, w, h = region
        cw, ch = self._document.width, self._document.height
        try:
            below_full = composite_range(nodes, cw, ch, 0, k, region=region)
            result = composite_range(
                nodes, cw, ch, k, len(nodes), region=region, base=below_full.data
            )
        except BlendError:
            # Any seam error → the naive region recomposite (also byte-exact).
            self._recomposite_region(QRectF(x, y, w, h))
        else:
            self._composite.data[y : y + h, x : x + w, :] = result.data
        visible_rect = QRectF(x, y, w, h)
        self._item.sync_region(visible_rect)
        self._item.update(visible_rect)
        canvas = QRect(0, 0, cw, ch)
        self._stale = QRegion(canvas).subtracted(QRegion(visible_rect.toAlignedRect()))
        self._mark_tiled_dirty()

    def cancel_opacity_drag(self) -> None:
        """Discard the drag split-cache without committing (idempotent, §2.3).

        Called on any op that invalidates the drag-scoped cache — a pixel edit, a
        structural / geometry op, a frame switch, or a pan/zoom that changes the
        culled region. Restores the naive throttled action; the invalidating op does
        its own recomposite and any subsequent commit falls back to the naive
        byte-exact path. A cheap no-op when no drag is live.
        """
        if self._opacity_drag is None:
            return
        self._opacity_drag = None
        self._live_pending = False
        self._live_recomposite_fn = self.refresh_visible

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

    # -- floating move/copy preview (REQ-P2-UI-030/-031/-035) ------------

    def begin_floating(self, floating: FloatingSelection) -> None:
        """Show the non-destructive floating preview for ``floating`` (D3 path).

        Two bounded layers are shown (AGT-10 FB-8 fix): the floated colours are
        rendered per drag frame from the **region-scoped** ``composite_preview``
        over their (bounded) destination bbox, and — for a MOVE — the vacated
        origin is composited **once** here into a separate persistent overlay
        (:meth:`_origin_vacate`). Neither is ever unioned into a distance-growing
        region, and the base display buffer is untouched until commit (ADR-0009
        D3 / ADR-0007 T13; the 16 ms budget is never relaxed, Article VI §2).
        """
        self._floating_prev = QRectF()
        self._ensure_composite()
        origin = (
            self._origin_vacate(floating) if floating.mode is FloatMode.MOVE else None
        )
        if origin is None:
            self._origin_item.clear_preview()
            self._origin_region = QRectF()
            self._origin_shown = False
        else:
            image, rect = origin
            self._origin_item.set_preview(image, rect)
            self._origin_region = QRectF(rect)
            self._origin_shown = True
        self.update_floating(floating)

    def update_floating(self, floating: FloatingSelection) -> None:
        """Recompute the floated-colours preview over ONLY its dirty band (D3).

        Per frame only the **incremental** dirty area is invalidated — the old
        float rect ∪ new float rect (the band the float moved through this
        frame) — never a region that grows with the total drag distance. The
        floated colours are composited over their bounded destination bbox
        alone; the vacated origin is the separate one-shot overlay set at lift
        (:meth:`begin_floating`), toggled here with the live mode (a COPY keeps
        the origin intact). No full-canvas allocation (AGT-10 FB-8).
        """
        self._ensure_composite()
        # Toggle the one-shot vacated-origin overlay with the live mode. A
        # MOVE↔COPY switch mid-drag re-lifts the float (same mask/bbox), so the
        # cached vacate image stays valid; only its visibility flips.
        want_origin = (
            floating.mode is FloatMode.MOVE and not self._origin_region.isEmpty()
        )
        origin_dirty = QRectF()
        if want_origin != self._origin_shown:
            self._origin_item.setVisible(want_origin)
            self._origin_shown = want_origin
            origin_dirty = QRectF(self._origin_region)
        region = self._float_region(floating)
        if region is None:
            # Fully off-canvas (e.g. a COPY dragged past the edge): nothing to
            # show now, but keep the float active until commit / cancel.
            new_rect = QRectF()
            self._float_item.clear_preview()
        else:
            rx, ry, rw, rh = region
            preview = composite_preview(floating, self._display_source(), region=region)
            image = self._preview_qimage(preview)
            new_rect = QRectF(rx, ry, rw, rh)
            self._float_item.set_preview(image, new_rect)
        dirty = QRectF(new_rect)
        if not self._floating_prev.isEmpty():
            dirty = self._union(dirty, self._floating_prev)
        if not origin_dirty.isEmpty():
            dirty = self._union(dirty, origin_dirty)
        if not dirty.isEmpty():
            self.update(dirty)
        self._floating_prev = new_rect

    def end_floating(self) -> None:
        """Tear down both floating layers; the buffer item shows the final state."""
        dirty = QRectF(self._floating_prev)
        if not self._origin_region.isEmpty():
            dirty = self._union(dirty, self._origin_region)
        self._floating_prev = QRectF()
        self._origin_region = QRectF()
        self._origin_shown = False
        self._float_item.clear_preview()
        self._origin_item.clear_preview()
        if not dirty.isEmpty():
            self.update(dirty)

    @staticmethod
    def _union(a: QRectF, b: QRectF) -> QRectF:
        """Union of two (possibly empty) scene rects, dropping empty operands."""
        if a.isEmpty():
            return QRectF(b)
        if b.isEmpty():
            return a
        return a.united(b)

    def _origin_vacate(
        self, floating: FloatingSelection
    ) -> Optional[Tuple[QImage, QRectF]]:
        """One-shot vacated-origin overlay for a MOVE: ``(image, scene_rect)``.

        Returns the **pure-vacate** preview of the (fixed) origin bounding box —
        the base with the masked origin pixels read transparent and NOTHING
        stamped — plus its scene rect, or ``None`` when the origin lies fully
        off-canvas. Computed **once** when the float is lifted and reused for the
        whole gesture (the origin bbox and mask never change), so a long MOVE
        drag never re-composites the origin per frame nor grows the recomposited
        area (AGT-10 FB-8 / ADR-0009 D3 / ADR-0007 T13).

        The vacate maths stay in ``logic.composite_preview`` (Article I): the
        stamp is displaced a full float-width past the origin's right edge so the
        region-scoped preview vacates the masked origin pixels but stamps
        nothing; the live offset is restored immediately (single-threaded, so the
        transient set is invisible to the controller). The base is never written.
        """
        fx0, fy0, fx1, fy1 = floating.bounds()
        dx, dy = floating.offset
        # Origin bbox = floated bbox shifted back by the live offset (fixed
        # across the gesture); avoids copying the full-canvas mask here.
        ox0, oy0, ox1, oy1 = fx0 - dx, fy0 - dy, fx1 - dx, fy1 - dy
        w, h = self._document.width, self._document.height
        cx0, cy0 = max(0, ox0), max(0, oy0)
        cx1, cy1 = min(w - 1, ox1), min(h - 1, oy1)
        if cx1 < cx0 or cy1 < cy0:
            return None
        region = (cx0, cy0, cx1 - cx0 + 1, cy1 - cy0 + 1)
        saved = floating.offset
        # Absolute displacement of one float-width guarantees the stamp clears
        # the origin region's right edge regardless of the current offset.
        floating.set_offset(floating.width, 0)
        try:
            preview = composite_preview(floating, self._display_source(), region=region)
        finally:
            floating.set_offset(*saved)
        image = self._preview_qimage(preview)
        return image, QRectF(cx0, cy0, region[2], region[3])

    def _float_region(
        self, floating: FloatingSelection
    ) -> Optional[Tuple[int, int, int, int]]:
        """Bounded dirty region ``(x, y, w, h)`` of the floated destination bbox.

        The floated bbox clamped to canvas — for BOTH modes. Unlike the previous
        implementation it is **never** unioned with the fixed origin bbox: the
        vacated origin is handled once by the separate origin overlay, so this
        region stays a single selection bbox and never grows with the drag
        distance (AGT-10 FB-8). Returns ``None`` when nothing lies on-canvas.
        """
        fx0, fy0, fx1, fy1 = floating.bounds()
        w, h = self._document.width, self._document.height
        cx0, cy0 = max(0, fx0), max(0, fy0)
        cx1, cy1 = min(w - 1, fx1), min(h - 1, fy1)
        if cx1 < cx0 or cy1 < cy0:
            return None
        return (cx0, cy0, cx1 - cx0 + 1, cy1 - cy0 + 1)

    def _preview_qimage(self, preview: PixelBuffer) -> QImage:
        """Build an owned RGBA :class:`QImage` from a preview region buffer.

        Indexed previews are resolved through the document palette LUT (like the
        buffer item's indexed display). ``QImage.copy()`` detaches from the NumPy
        memory so the region buffer can be released.
        """
        if preview.mode is ColorMode.RGBA:
            data = np.ascontiguousarray(preview.data)
        else:
            colors = self._document.palette.colors()
            lut = (
                np.array(colors, dtype=np.uint8)
                if colors
                else np.zeros((1, 4), dtype=np.uint8)
            )
            idx = np.clip(preview.data, 0, max(0, len(colors) - 1))
            data = np.ascontiguousarray(lut[idx])
        h, w = int(data.shape[0]), int(data.shape[1])
        image = QImage(data.data, w, h, data.strides[0], QImage.Format.Format_RGBA8888)
        return image.copy()

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
        self._float_item.set_roles(self._checker_light, self._checker_dark)
        self._origin_item.set_roles(self._checker_light, self._checker_dark)
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    # -- background -------------------------------------------------------

    def drawBackground(  # type: ignore[override]  # noqa: N802
        self, painter: QPainter, rect: QRectF
    ) -> None:
        """Paint checker + optional grid over ONLY the exposed ``rect`` (D2)."""
        # Compute the deferred initial composite before the pixmap item blits it,
        # so scene construction stays O(1) yet the first frame is correct (D1).
        self._ensure_composite()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Snap the tile loop to a TILE_SIZE grid, extend a TILE_BUFFER ring.
        _paint_checker_tiles(painter, rect, self._checker_light, self._checker_dark)

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
