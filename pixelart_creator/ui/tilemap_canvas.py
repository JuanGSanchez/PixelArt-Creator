"""Tilemap canvas — composited render + stamping tools (Slice 6F).

``Tilemap_Canvas`` is a :class:`QGraphicsView` over ``_Tilemap_Scene``, a
:class:`QGraphicsScene` whose :meth:`drawBackground` renders the composited layer
stack through the frozen ``Tilemap.render_region`` seam (REQ-P6-UI-004,
REQ-P6-LOGIC-013). It mirrors the shipped
:class:`~pixelart_creator.ui.canvas_view.Canvas_View` architecture — nearest
neighbour, AA off, ``MinimalViewportUpdate``, cursor-anchored wheel zoom, and
middle-/space-drag pan (view state, no undo, CL-13, REQ-P6-UI-010).

**Render seam & performance (DEP-3, AGT-10 D1-D5).**
``drawBackground(painter, rect)`` assembles the exposed ``rect`` from a
**chunk-aligned QPixmap cache** (:class:`~pixelart_creator.ui.tilemap_chunk_cache.
ChunkPixmapCache`): each ``TILEMAP_CHUNK_SIZE`` chunk is rendered once through the
frozen, Qt-free ``render_region`` seam and cached, keyed by ``(cx, cy)`` and
validated by the logic layer's O(1) ``Tilemap.chunk_version`` (D1). A
stamp/erase/fill bumps only the touched chunks' versions in ``logic/`` — so those
chunks miss the cache and re-render while every untouched chunk re-blits
(chunk-scoped dirty invalidation, D2); a pan re-blits cached chunks and renders
only the newly-exposed ones (D3). A never-edited chunk (``chunk_version == 0``) is
empty and skipped entirely (the checker shows through), keeping an infinite/sparse
map cheap. When many cold chunks are exposed at once (the S1 full-viewport freeze),
they are rendered **off the GUI thread** on a scene-owned
:class:`~PySide6.QtCore.QThreadPool` (D4) with the checker as a progressive
placeholder; a small per-frame budget of cold chunks still renders inline so a
stamp / small pan stays instant. The LRU is MiB-bounded so memory stays bounded on
large maps; the resident tileset/pixel data is never culled — only the derived
pixmaps are (Article VI §3). Map-wide changes that ``chunk_version`` does NOT cover
(layer add/remove/reorder/visibility, tileset attach, source-tile edits) clear the
**whole** chunk cache via :meth:`Tilemap_Canvas.refresh`.

**Deterministic teardown (D4, CRITICAL).** The off-thread warmer exposes an
idempotent, event-loop-free :meth:`_Tilemap_Scene.shutdown_warm` (cancel event +
``pool.clear`` + bounded ``waitForDone`` + disconnect/release the signal carrier),
surfaced as :meth:`Tilemap_Canvas.shutdown_warm` and wired into
``MainWindow.shutdown_prewarm`` (hence ``closeEvent`` / ``close_document``), so no
live worker or connected carrier can survive into GC — mirroring the shipped
Phase-5 ``CanvasScene.shutdown_prewarm`` fix exactly.

**Stamping (REQ-P6-UI-005..007/-009).** Stamp / eraser / rectangle-fill each push
**exactly one** :class:`~pixelart_creator.ui.commands.TilemapCommand` wrapping the
``logic/tilemap`` reversible factory; flip/rotate map the active stamp to the GID
flag transform (diagonal→H→V); the per-layer auto-tile toggle sets the layer's
:class:`~pixelart_creator.logic.autotile.AutotileRuleset` so placement resolves
display tiles via ``logic/autotile`` (all domain logic stays in ``logic/`` —
Article I / S11).
"""

from __future__ import annotations

import math
import threading
from enum import Enum
from typing import Callable, Dict, Optional, Tuple

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QTransform,
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QMessageBox, QWidget

from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    OPENGL_VIEWPORT_ENABLED,
    SCALE_FACTOR,
    TILEMAP_CHUNK_SIZE,
    ZOOM_MAX,
    ZOOM_MIN,
)
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    FLIPPED_DIAGONALLY_FLAG,
    FLIPPED_HORIZONTALLY_FLAG,
    FLIPPED_VERTICALLY_FLAG,
    GID_MASK,
    Tilemap,
    TilemapError,
)
from pixelart_creator.ui.commands import TilemapCommand
from pixelart_creator.ui.tilemap_chunk_cache import (
    ChunkPixmapCache,
    InflightMap,
    TilemapChunkWarmRunnable,
    TilemapChunkWarmSignals,
)

#: Initial scene window (px) for a fresh infinite map; grows to include stamps.
_INITIAL_WINDOW = 1024

#: Edge (px) of one checker square drawn behind the map (presentation-only).
_CHECKER_PX = 16

#: Platform name Qt reports with no windowing system (keep the raster viewport).
_OFFSCREEN_PLATFORM = "offscreen"

#: MiB budget of the chunk pixmap LRU (D1). A 16x16 chunk at 16 px tiles is a
#: 256x256 RGBA pixmap (~256 KiB), so ~128 MiB keeps a large working set resident
#: while staying bounded on an infinite / fully filled map. Presentation/resource
#: sizing (like frame_cache's budget), so it lives here in ui/, not logic/constants.
_CHUNK_CACHE_BUDGET_BYTES = 128 * 1024 * 1024

#: Max cold chunks rendered *inline* per paint before the rest stream off-thread
#: (D4). A cold chunk is ~0.84 ms (AGT-10), so a handful stays well under the 16 ms
#: budget and keeps a stamp / small pan instant; a full cold viewport streams.
_SYNC_CHUNK_BUDGET = 8

#: Bounded wait (ms) for an in-flight off-thread chunk render to finish on rebind /
#: window close before the pool is torn down (mirrors canvas_scene's shutdown wait).
_WARM_SHUTDOWN_WAIT_MS = 5000


class TilemapTool(Enum):
    """The three tilemap stamping tools (CL-12)."""

    STAMP = "stamp"
    ERASE = "erase"
    FILL = "fill"


# --- D4 orientation composition (flip/rotate -> GID flag transform) --------- #
# The stamp orientation is one of the eight symmetries of the square, encoded as
# the (flip_d, flip_h, flip_v) flag triple the render applies in diagonal->H->V
# order (logic/tilemap._apply_flip). Composition is computed once from 2x2
# permutation matrices so rotate/flip stay exactly correct through repeats.
_FLIP_H_MAT = np.array([[-1, 0], [0, 1]], dtype=int)
_FLIP_V_MAT = np.array([[1, 0], [0, -1]], dtype=int)
_DIAG_MAT = np.array([[0, 1], [1, 0]], dtype=int)
_ROT_CW_MAT = np.array([[0, -1], [1, 0]], dtype=int)


def _orientation_matrix(flip_d: bool, flip_h: bool, flip_v: bool) -> np.ndarray:
    matrix = np.eye(2, dtype=int)
    if flip_d:
        matrix = _DIAG_MAT @ matrix
    if flip_h:
        matrix = _FLIP_H_MAT @ matrix
    if flip_v:
        matrix = _FLIP_V_MAT @ matrix
    return matrix


_FLAGS_BY_MATRIX: Dict[Tuple[int, ...], Tuple[bool, bool, bool]] = {}
for _d in (False, True):
    for _h in (False, True):
        for _v in (False, True):
            _key = tuple(int(v) for v in _orientation_matrix(_d, _h, _v).flatten())
            _FLAGS_BY_MATRIX[_key] = (_d, _h, _v)


def _rotate_cw(flip_d: bool, flip_h: bool, flip_v: bool) -> Tuple[bool, bool, bool]:
    """Return the (d, h, v) flags after rotating the stamp 90° clockwise."""
    rotated = _ROT_CW_MAT @ _orientation_matrix(flip_d, flip_h, flip_v)
    return _FLAGS_BY_MATRIX[tuple(int(v) for v in rotated.flatten())]


def _buffer_to_qimage(buffer: PixelBuffer) -> QImage:
    """Return an owned RGBA :class:`QImage` copy of an RGBA render buffer."""
    data = np.ascontiguousarray(buffer.data)
    height, width = int(data.shape[0]), int(data.shape[1])
    image = QImage(
        data.data, width, height, data.strides[0], QImage.Format.Format_RGBA8888
    )
    return image.copy()


def _buffer_to_qpixmap(buffer: PixelBuffer) -> QPixmap:
    """Return a :class:`QPixmap` of an RGBA render buffer (GUI thread only)."""
    return QPixmap.fromImage(_buffer_to_qimage(buffer))


def _pixmap_bytes(pixmap: QPixmap) -> int:
    """Estimate a pixmap's resident bytes (32-bit depth) for the LRU budget."""
    return max(1, pixmap.width() * pixmap.height() * 4)


class _Tilemap_Scene(QGraphicsScene):
    """Scene rendering the composited tilemap through ``render_region`` (DEP-3)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Create an empty scene with the initial infinite-map window."""
        super().__init__(parent)
        # A drawBackground-only scene holds no per-item geometry, so a BSP index
        # buys nothing (D5): use NoIndex like the shipped CanvasScene.
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self._tilemap: Optional[Tilemap] = None
        self._grid_enabled = False
        self._checker_light = QColor(255, 255, 255)
        self._checker_dark = QColor(200, 200, 200)
        self._grid_color = QColor(120, 120, 120, 144)
        # Chunk-aligned pixmap cache keyed by (cx, cy), validated by
        # Tilemap.chunk_version (D1). A miss re-renders that chunk only (D2/D3).
        self._chunk_cache = ChunkPixmapCache(_CHUNK_CACHE_BUDGET_BYTES)
        # Off-GUI-thread cold-chunk warm (D4): a dedicated single-thread pool
        # renders cold chunks via the Qt-free render_region and delivers each result
        # to the GUI thread through a QUEUED signal, so the scene converts to a
        # QPixmap and owns the buffer only in _on_chunk_warmed. A monotonic token
        # (bumped on rebind / edit / shutdown) makes any superseded result a no-op;
        # the shared cancel event is a best-effort early exit. NOT the global pool.
        self._warm_signals: Optional[TilemapChunkWarmSignals] = (
            TilemapChunkWarmSignals()
        )
        self._warm_signals.chunkReady.connect(self._on_chunk_warmed)
        self._warm_pool = QThreadPool(self)
        self._warm_pool.setMaxThreadCount(1)
        self._warm_cancel = threading.Event()
        self._warm_token = 0
        self._warm_inflight: InflightMap = {}
        self.setSceneRect(0.0, 0.0, float(_INITIAL_WINDOW), float(_INITIAL_WINDOW))

    def set_tilemap(self, tilemap: Optional[Tilemap]) -> None:
        """Bind the scene to ``tilemap`` and repaint the whole viewport.

        The new map's chunk versions/content are unrelated to the previous one, so
        the whole chunk cache is dropped and any in-flight warm is cancelled.
        """
        self.cancel_warm()
        self._chunk_cache.clear()
        self._tilemap = tilemap
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def tilemap(self) -> Optional[Tilemap]:
        """Return the bound tilemap, or ``None``."""
        return self._tilemap

    def set_theme_colors(
        self, checker_light: QColor, checker_dark: QColor, grid: QColor
    ) -> None:
        """Set the role-based checker/grid colours (both-theme, REQ-P6-UI-016)."""
        self._checker_light = checker_light
        self._checker_dark = checker_dark
        self._grid_color = grid
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def set_grid_enabled(self, enabled: bool) -> None:
        """Toggle the per-tile grid overlay."""
        self._grid_enabled = bool(enabled)
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def ensure_pixel_rect(self, x: int, y: int, w: int, h: int) -> None:
        """Grow the scene rect to include a stamped pixel rect (infinite nav)."""
        rect = self.sceneRect()
        stamped = QRectF(float(x), float(y), float(w), float(h))
        if not rect.contains(stamped):
            self.setSceneRect(rect.united(stamped))

    def drawBackground(  # type: ignore[override]  # noqa: N802
        self, painter: QPainter, rect: QRectF
    ) -> None:
        """Render only the exposed ``rect`` via ``render_region`` (viewport cull)."""
        draw = rect.intersected(self.sceneRect())
        if draw.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self._draw_checker(painter, draw)
        self._draw_map(painter, draw)
        if self._grid_enabled:
            self._draw_grid(painter, draw)

    # -- background helpers ----------------------------------------------

    def _draw_checker(self, painter: QPainter, draw: QRectF) -> None:
        left = int(math.floor(draw.left() / _CHECKER_PX)) * _CHECKER_PX
        top = int(math.floor(draw.top() / _CHECKER_PX)) * _CHECKER_PX
        y = top
        while y < draw.bottom():
            x = left
            while x < draw.right():
                cx = x // _CHECKER_PX
                cy = y // _CHECKER_PX
                color = (
                    self._checker_light if (cx + cy) % 2 == 0 else self._checker_dark
                )
                painter.fillRect(
                    QRectF(float(x), float(y), _CHECKER_PX, _CHECKER_PX), color
                )
                x += _CHECKER_PX
            y += _CHECKER_PX

    def _draw_map(self, painter: QPainter, draw: QRectF) -> None:
        """Assemble the exposed rect from cached chunk pixmaps (D1/D2/D3/D4).

        Iterates the ``TILEMAP_CHUNK_SIZE`` chunks intersecting the exposed rect:
        a cache HIT (matching :meth:`Tilemap.chunk_version`) re-blits; a MISS
        renders the chunk once (inline up to :data:`_SYNC_CHUNK_BUDGET` per paint,
        the rest dispatched off-thread with the checker as a placeholder). A
        never-edited chunk (version ``0``) is empty and skipped entirely, so an
        infinite / sparse map costs only its non-empty chunks.
        """
        tilemap = self._tilemap
        if tilemap is None or not tilemap.layers:
            return
        chunk_w = TILEMAP_CHUNK_SIZE * tilemap.tile_width
        chunk_h = TILEMAP_CHUNK_SIZE * tilemap.tile_height
        if chunk_w <= 0 or chunk_h <= 0 or chunk_w > MAX_CANVAS_WIDTH:
            return
        if chunk_h > MAX_CANVAS_HEIGHT:
            return
        cx0 = int(math.floor(draw.left() / chunk_w))
        cx1 = int(math.floor((math.ceil(draw.right()) - 1) / chunk_w))
        cy0 = int(math.floor(draw.top() / chunk_h))
        cy1 = int(math.floor((math.ceil(draw.bottom()) - 1) / chunk_h))
        rendered_inline = 0
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                version = tilemap.chunk_version(cx, cy)
                if version == 0:
                    continue  # never edited -> empty; checker shows through
                px = cx * chunk_w
                py = cy * chunk_h
                pixmap = self._chunk_cache.get(cx, cy, version)
                if pixmap is None:
                    if rendered_inline < _SYNC_CHUNK_BUDGET:
                        pixmap = self._render_chunk(cx, cy, version, px, py)
                        rendered_inline += 1
                    else:
                        self._dispatch_warm(cx, cy, version, px, py, chunk_w, chunk_h)
                        continue  # placeholder: checker until the warm lands
                if pixmap is not None and not pixmap.isNull():
                    painter.drawPixmap(px, py, pixmap)

    def _render_chunk(
        self, cx: int, cy: int, version: int, px: int, py: int
    ) -> Optional[QPixmap]:
        """Render one chunk inline via ``render_region`` and cache it (D1)."""
        tilemap = self._tilemap
        if tilemap is None:
            return None
        chunk_w = TILEMAP_CHUNK_SIZE * tilemap.tile_width
        chunk_h = TILEMAP_CHUNK_SIZE * tilemap.tile_height
        try:
            buffer = tilemap.render_region(px, py, chunk_w, chunk_h)
        except TilemapError:
            return None  # defensive: never crash the paint loop on a bad cell
        if buffer.mode is not ColorMode.RGBA:
            return None
        pixmap = _buffer_to_qpixmap(buffer)
        self._chunk_cache.put(cx, cy, version, pixmap, _pixmap_bytes(pixmap))
        return pixmap

    # -- off-thread cold-chunk warm (D4) ----------------------------------

    def _dispatch_warm(
        self, cx: int, cy: int, version: int, px: int, py: int, pw: int, ph: int
    ) -> None:
        """Queue a cold chunk's render on the scene-owned pool (dedupe, D4)."""
        tilemap = self._tilemap
        signals = self._warm_signals
        if tilemap is None or signals is None:
            return
        if self._warm_inflight.get((cx, cy)) == version:
            return  # already warming this exact version
        self._warm_inflight[(cx, cy)] = version
        runnable = TilemapChunkWarmRunnable(
            self._warm_token,
            tilemap,
            cx,
            cy,
            version,
            px,
            py,
            pw,
            ph,
            self._warm_cancel,
            signals,
        )
        self._warm_pool.start(runnable)

    def _on_chunk_warmed(
        self, token: int, cx: int, cy: int, version: int, buffer: object
    ) -> None:
        """Receive a warmed chunk on the GUI thread and cache it (queued, D4).

        Ignores a result whose ``token`` no longer matches the active warm session
        (cancelled / superseded / map replaced). The scene converts the buffer to a
        ``QPixmap`` and takes ownership only here, then invalidates just that chunk's
        rect so the next paint blits it (a cache hit).
        """
        if token != self._warm_token:
            return
        if self._warm_inflight.get((cx, cy)) == version:
            del self._warm_inflight[(cx, cy)]
        if not isinstance(buffer, PixelBuffer) or buffer.mode is not ColorMode.RGBA:
            return
        tilemap = self._tilemap
        if tilemap is None:
            return
        # Drop a result already superseded by a newer edit to that chunk.
        if tilemap.chunk_version(cx, cy) != version:
            return
        pixmap = _buffer_to_qpixmap(buffer)
        self._chunk_cache.put(cx, cy, version, pixmap, _pixmap_bytes(pixmap))
        chunk_w = TILEMAP_CHUNK_SIZE * tilemap.tile_width
        chunk_h = TILEMAP_CHUNK_SIZE * tilemap.tile_height
        self.invalidate(
            QRectF(
                float(cx * chunk_w), float(cy * chunk_h), float(chunk_w), float(chunk_h)
            ),
            QGraphicsScene.SceneLayer.BackgroundLayer,
        )

    def cancel_warm(self) -> None:
        """Cancel any in-flight cold warm (rebind / edit); keep the carrier alive.

        Bumps the token so every queued/in-flight result becomes a no-op and drops
        queued runnables. Cheap and idempotent when nothing is warming. The shared
        cancel event is left unset (only :meth:`shutdown_warm` sets it), so a fresh
        dispatch after this needs no event reset.
        """
        if not self._warm_inflight and self._warm_pool.activeThreadCount() == 0:
            self._warm_token += 1
            return
        self._warm_token += 1
        self._warm_pool.clear()
        self._warm_inflight.clear()

    def invalidate_all_chunks(self) -> None:
        """Drop the whole chunk cache + cancel warms (map-wide change, D-whole).

        For changes ``chunk_version`` does not cover — layer add/remove/reorder/
        visibility, tileset attach, and source-tile edits (which change how *all*
        instances render without bumping any per-chunk version) — every cached
        pixmap is potentially stale, so the entire cache is dropped and the scene
        background invalidated. In-flight warms are cancelled: their pixmaps would
        be keyed by a version that is still "current" yet render old content.
        """
        self.cancel_warm()
        self._chunk_cache.clear()
        self.invalidate(self.sceneRect(), QGraphicsScene.SceneLayer.BackgroundLayer)

    def shutdown_warm(self) -> None:
        """Deterministically tear the off-thread warm down (idempotent, D4).

        Mirrors :meth:`~pixelart_creator.ui.canvas_scene.CanvasScene.shutdown_prewarm`
        exactly and does NOT rely on the Qt event loop. In order it: bumps the token
        (every queued/in-flight result becomes a no-op); sets the shared cancel event
        (best-effort early exit for the render); drops queued runnables and **blocks**
        (bounded) on ``waitForDone`` until the running render finishes and the pool's
        worker threads are removed — so no native worker survives into a later GC
        cycle (the PySide6 cross-thread GC-of-Qt-C++ segfault); then disconnects and
        releases the GUI-thread signal carrier so any still-queued emission has no
        slot to land on a torn-down scene. Safe to call repeatedly.
        """
        self._warm_token += 1
        self._warm_cancel.set()
        self._warm_pool.clear()
        self._warm_pool.waitForDone(_WARM_SHUTDOWN_WAIT_MS)
        self._warm_inflight.clear()
        signals = self._warm_signals
        if signals is not None:
            try:
                signals.chunkReady.disconnect(self._on_chunk_warmed)
            except (RuntimeError, TypeError):
                # Already disconnected / carrier already torn down — idempotent.
                pass
            self._warm_signals = None

    def _draw_grid(self, painter: QPainter, draw: QRectF) -> None:
        tilemap = self._tilemap
        if tilemap is None:
            return
        tw, th = tilemap.tile_width, tilemap.tile_height
        painter.setPen(self._grid_color)
        left = int(math.floor(draw.left() / tw)) * tw
        x = left
        while x <= draw.right():
            painter.drawLine(int(x), int(draw.top()), int(x), int(draw.bottom()))
            x += tw
        top = int(math.floor(draw.top() / th)) * th
        y = top
        while y <= draw.bottom():
            painter.drawLine(int(draw.left()), int(y), int(draw.right()), int(y))
            y += th


class Tilemap_Canvas(QGraphicsView):
    """Interactive tilemap view: composited render + stamp/erase/fill tools."""

    #: Emitted after a layer's auto-tile mode changes (drives the panel checkbox).
    autotileChanged = Signal(bool)
    #: Emitted when a stamp/fill is refused because the tilemap has no tileset
    #: bound yet (CI-red field defect, 2026-08-24: the original FIX 5 routed
    #: this refusal through a blocking ``QMessageBox.warning``, which hangs a
    #: headless parallel worker with nothing to dismiss it). Follows the
    #: ``Canvas_View.lockedLayerEditRejected`` precedent exactly -- a signal
    #: the shell surfaces non-blockingly, never a modal, for a refusal
    #: reachable from a plain mouse gesture.
    noTilesetBoundRejected = Signal()
    #: Emitted when a stamp/fill is refused because no tile is selected as the
    #: active brush (a tileset IS bound; the brush gid is 0). Kept distinct
    #: from ``noTilesetBoundRejected`` so the shell shows the honest message
    #: for each case, exactly as the two ``_warn_no_active_brush`` branches
    #: already did.
    noActiveBrushRejected = Signal()

    def __init__(
        self, undo_stack: Optional[QUndoStack] = None, parent: Optional[QWidget] = None
    ) -> None:
        """Create the tilemap view over a fresh :class:`_Tilemap_Scene`."""
        self._scene = _Tilemap_Scene()
        super().__init__(self._scene, parent)
        self._stack = undo_stack
        self._on_changed: Optional[Callable[[], None]] = None
        self._tool = TilemapTool.STAMP
        self._active_layer = 0
        self._brush_base_gid = 0
        self._flip_h = False
        self._flip_v = False
        self._flip_d = False
        self._zoom = 1.0
        self._panning = False
        self._space_held = False
        self._pan_origin = QPoint()
        self._drawing = False
        self._fill_start: Optional[Tuple[int, int]] = None

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
        # D5: this is a drawBackground-only scene, so cache the composited viewport
        # background. On a pan Qt scrolls the cached pixmap and re-runs
        # drawBackground only for the newly-exposed strip (complementing the chunk
        # cache); a chunk invalidate discards just that region of the background
        # cache. No per-item BSP tuning (the scene sets NoIndex).
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self._install_viewport()
        self._retranslate()

    def _install_viewport(self) -> None:
        """Use a GL viewport on desktop; fall back to raster headless (D5).

        Mirrors :class:`~pixelart_creator.ui.canvas_view.Canvas_View`: a
        ``QOpenGLWidget`` viewport where a GL context is available and enabled, and
        the default raster viewport under the offscreen platform / on any GL failure
        so headless CI stays deterministic.
        """
        if not OPENGL_VIEWPORT_ENABLED:
            return
        if QGuiApplication.platformName() == _OFFSCREEN_PLATFORM:
            return
        try:
            from PySide6.QtOpenGLWidgets import QOpenGLWidget

            self.setViewport(QOpenGLWidget())
        except Exception:  # noqa: BLE001 - any GL failure => raster fallback.
            pass

    # -- external wiring --------------------------------------------------

    def set_context(
        self,
        tilemap: Optional[Tilemap],
        stack: Optional[QUndoStack],
        on_changed: Optional[Callable[[], None]],
    ) -> None:
        """Bind the canvas to a tilemap + its undo stack + a panel-refresh hook."""
        self._stack = stack
        self._on_changed = on_changed
        self._active_layer = 0
        self._scene.set_tilemap(tilemap)

    def set_tool(self, tool: TilemapTool) -> None:
        """Set the active stamping tool (stamp / erase / fill)."""
        self._tool = tool

    def active_tool(self) -> TilemapTool:
        """Return the active stamping tool."""
        return self._tool

    def set_active_layer(self, index: int) -> None:
        """Set the layer that receives stamps/erases (view state, no undo)."""
        self._active_layer = int(index)

    def active_layer(self) -> int:
        """Return the active layer index."""
        return self._active_layer

    def set_brush_gid(self, gid: int) -> None:
        """Set the brush's base tile gid (flags applied separately)."""
        self._brush_base_gid = int(gid) & GID_MASK

    def brush_gid(self) -> int:
        """Return the effective stamp gid (base id | current flip flags)."""
        gid = self._brush_base_gid
        if self._flip_h:
            gid |= FLIPPED_HORIZONTALLY_FLAG
        if self._flip_v:
            gid |= FLIPPED_VERTICALLY_FLAG
        if self._flip_d:
            gid |= FLIPPED_DIAGONALLY_FLAG
        return gid

    def set_undo_stack(self, stack: Optional[QUndoStack]) -> None:
        """Rebind the canvas to a different document's undo stack."""
        self._stack = stack

    def set_theme_colors(
        self, checker_light: QColor, checker_dark: QColor, grid: QColor
    ) -> None:
        """Forward role-based theme colours to the scene (REQ-P6-UI-016)."""
        self._scene.set_theme_colors(checker_light, checker_dark, grid)

    def set_grid_enabled(self, enabled: bool) -> None:
        """Toggle the per-tile grid overlay."""
        self._scene.set_grid_enabled(enabled)

    def refresh(self) -> None:
        """Whole-cache invalidation for a map-wide change (D-whole-cache).

        Called for changes ``Tilemap.chunk_version`` does NOT cover — layer
        add/remove/reorder/visibility, tileset attach, and linked source-tile edits
        (which change how *all* instances render). Drops the entire chunk pixmap
        cache, cancels in-flight warms and invalidates the scene background; Qt
        clips ``drawBackground`` to the exposed rect, so only the visible viewport
        is actually re-rendered (from a now-empty cache).
        """
        self._scene.invalidate_all_chunks()

    def shutdown_warm(self) -> None:
        """Deterministically tear down the scene's off-thread chunk warm (D4).

        Idempotent, event-loop-free. Wired into ``MainWindow.shutdown_prewarm``
        (hence ``closeEvent`` / ``close_document``) so no worker thread or connected
        carrier survives the window's teardown into GC.
        """
        self._scene.shutdown_warm()

    # -- flip / rotate (GID flag transform, diagonal->H->V) --------------

    def toggle_flip_h(self) -> None:
        """Toggle the active stamp's horizontal-flip flag."""
        self._flip_h = not self._flip_h

    def toggle_flip_v(self) -> None:
        """Toggle the active stamp's vertical-flip flag."""
        self._flip_v = not self._flip_v

    def rotate_cw(self) -> None:
        """Rotate the active stamp 90° clockwise (composes the GID flags)."""
        self._flip_d, self._flip_h, self._flip_v = _rotate_cw(
            self._flip_d, self._flip_h, self._flip_v
        )

    def stamp_flags(self) -> Tuple[bool, bool, bool]:
        """Return the active stamp's ``(flip_h, flip_v, flip_d)`` flags."""
        return (self._flip_h, self._flip_v, self._flip_d)

    # -- auto-tile mode (per active layer; view/tool state, not undoable) -

    def set_autotile_enabled(self, enabled: bool) -> None:
        """Enable/disable Blob-47 auto-tiling on the active layer (mode change).

        Building the ruleset assumes the active brush's tile is the first of a
        contiguous 47-frame blob atlas (``base_gid .. base_gid+46``). If the
        owning tileset does not contain all 47 frames the toggle is refused with a
        user-facing notice (never a crash). Toggling auto-tile is a brush/layer
        **mode**, not a document mutation, so it pushes no ``QUndoCommand``
        (CL-13); the stamps made under it stay one undoable command each.
        """
        tilemap = self._scene.tilemap()
        if tilemap is None or not 0 <= self._active_layer < len(tilemap.layers):
            return
        layer = tilemap.layers[self._active_layer]
        if not enabled:
            layer.autotile = None
            self.autotileChanged.emit(False)
            return
        base = self._brush_base_gid
        frame_gids = list(range(base, base + BLOB_TILE_COUNT))
        try:
            for gid in frame_gids:
                tilemap.resolve(gid)  # every frame must be a known tile
            ruleset = AutotileRuleset(terrain_gid=base, frame_gids=frame_gids)
        except (TilemapError, ValueError) as exc:
            self._warn(self.tr("Auto-tile"), str(exc))
            self.autotileChanged.emit(False)
            return
        layer.autotile = ruleset
        self.autotileChanged.emit(True)

    def is_autotile_enabled(self) -> bool:
        """Return whether the active layer has an auto-tile ruleset set."""
        tilemap = self._scene.tilemap()
        if tilemap is None or not 0 <= self._active_layer < len(tilemap.layers):
            return False
        return tilemap.layers[self._active_layer].autotile is not None

    # -- zoom / pan (view state, no undo) --------------------------------

    def _fit_zoom(self) -> float:
        rect = self.sceneRect()
        vp = self.viewport().rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return 1.0
        if vp.width() <= 0 or vp.height() <= 0:
            return 1.0
        return min(
            min(vp.width() / rect.width(), vp.height() / rect.height()), ZOOM_MAX
        )

    def _clamp_zoom(self, value: float) -> float:
        # ZOOM_MIN is a flat, absolute floor (user ruling 2026-08-25;
        # `logic/constants.py`'s ZOOM_MIN docstring), applied here to match
        # `Canvas_View._clamp_zoom` (D-20, 2026-08-31). The 2026-08-24
        # `min(ZOOM_MIN, fit_zoom)` formula this superseded is the SAME defect
        # class the paint canvas carried until 92f09d5: below 1:1 this view is
        # minified by a painter with smoothing off (nearest-neighbour point
        # sampling), and this scene draws its own 1-device-pixel grid overlay
        # lines (`_Tilemap_Scene.drawBackground`) -- sparse, single-pixel-wide
        # content that point-sampling can drop between sample points exactly
        # as the checker border did. A document larger than the viewport is
        # viewed by panning at 1:1 rather than a fractional whole-grid fit,
        # the same accepted trade-off `Canvas_View` made.
        return max(ZOOM_MIN, min(value, ZOOM_MAX))

    def set_zoom(self, value: float) -> None:
        """Set an absolute zoom (clamped), anchored on the view centre."""
        target = self._clamp_zoom(value)
        transform = QTransform()
        transform.scale(target, target)
        self.setTransform(transform)
        self._zoom = target

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Cursor-anchored geometric zoom by the ``SCALE_FACTOR`` step."""
        factor = 1.0 + SCALE_FACTOR
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        target = self._clamp_zoom(self._zoom * factor)
        if abs(target - self._zoom) < 1e-9:
            event.accept()
            return
        applied = target / self._zoom
        self.scale(applied, applied)
        self._zoom = target
        event.accept()

    # -- keyboard (Space pan + flip/rotate) ------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Space arms panning; H/V flip and R rotate the active stamp."""
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        elif key == Qt.Key.Key_H:
            self.toggle_flip_h()
        elif key == Qt.Key.Key_V:
            self.toggle_flip_v()
        elif key == Qt.Key.Key_R:
            self.rotate_cw()
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Disarm panning on Space release."""
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self.viewport().unsetCursor()
        super().keyReleaseEvent(event)

    # -- mouse: stamp / erase / fill / pan -------------------------------

    def _cell_at(self, event: QMouseEvent) -> Tuple[int, int]:
        point = self.mapToScene(event.position().toPoint())
        tilemap = self._scene.tilemap()
        tw = tilemap.tile_width if tilemap is not None else 1
        th = tilemap.tile_height if tilemap is not None else 1
        return (int(math.floor(point.x() / tw)), int(math.floor(point.y() / th)))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Pan (middle/Space+left) or begin a stamp/erase/fill (left)."""
        button = event.button()
        if button == Qt.MouseButton.MiddleButton or (
            button == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if button == Qt.MouseButton.LeftButton:
            cx, cy = self._cell_at(event)
            if self._tool is TilemapTool.FILL:
                self._fill_start = (cx, cy)
                self._drawing = True
            elif self._tool is TilemapTool.ERASE:
                self._drawing = True
                self._apply_erase(cx, cy)
            else:
                self._drawing = True
                self._apply_stamp(cx, cy)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Continue panning, or continue a drag stamp/erase (fill waits release)."""
        if self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._pan_origin = event.position().toPoint()
            hbar = self.horizontalScrollBar()
            vbar = self.verticalScrollBar()
            hbar.setValue(hbar.value() - delta.x())
            vbar.setValue(vbar.value() - delta.y())
            event.accept()
            return
        if self._drawing and self._tool is not TilemapTool.FILL:
            cx, cy = self._cell_at(event)
            if self._tool is TilemapTool.ERASE:
                self._apply_erase(cx, cy)
            else:
                self._apply_stamp(cx, cy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Finish a pan, or commit a rectangle-fill on release."""
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
            and self._tool is TilemapTool.FILL
            and self._fill_start is not None
        ):
            cx, cy = self._cell_at(event)
            self._apply_fill(self._fill_start, (cx, cy))
            self._fill_start = None
        self._drawing = False
        super().mouseReleaseEvent(event)

    # -- edit application (one TilemapCommand each) ----------------------

    def _tilemap_ready(self) -> Optional[Tilemap]:
        tilemap = self._scene.tilemap()
        if tilemap is None or self._stack is None:
            return None
        if not 0 <= self._active_layer < len(tilemap.layers):
            return None
        return tilemap

    def _apply_stamp(self, cx: int, cy: int) -> None:
        tilemap = self._tilemap_ready()
        if tilemap is None:
            return
        if self._brush_base_gid == 0:
            self._warn_no_active_brush(tilemap)
            return
        gid = self._brush_base_gid if self.is_autotile_enabled() else self.brush_gid()
        try:
            command = tilemap.make_stamp_command(self._active_layer, cx, cy, gid)
        except TilemapError as exc:
            self._warn(self.tr("Stamp"), str(exc))
            return
        self._push(command, self.tr("Stamp Tile"), cx, cy, 1, 1)

    def _apply_erase(self, cx: int, cy: int) -> None:
        tilemap = self._tilemap_ready()
        if tilemap is None:
            return
        try:
            command = tilemap.make_erase_command(self._active_layer, cx, cy)
        except TilemapError as exc:
            self._warn(self.tr("Erase"), str(exc))
            return
        self._push(command, self.tr("Erase Tile"), cx, cy, 1, 1)

    def _apply_fill(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        tilemap = self._tilemap_ready()
        if tilemap is None:
            return
        if self._brush_base_gid == 0:
            self._warn_no_active_brush(tilemap)
            return
        x0, x1 = sorted((start[0], end[0]))
        y0, y1 = sorted((start[1], end[1]))
        width, height = x1 - x0 + 1, y1 - y0 + 1
        gid = self._brush_base_gid if self.is_autotile_enabled() else self.brush_gid()
        try:
            command = tilemap.make_fill_rect_command(
                self._active_layer, x0, y0, width, height, gid
            )
        except TilemapError as exc:
            self._warn(self.tr("Fill"), str(exc))
            return
        self._push(command, self.tr("Fill Rectangle"), x0, y0, width, height)

    def _push(
        self, command: Command, label: str, cx: int, cy: int, cw: int, ch: int
    ) -> None:
        stack = self._stack
        tilemap = self._scene.tilemap()
        if stack is None or tilemap is None:
            return
        tw, th = tilemap.tile_width, tilemap.tile_height
        # Dirty rect: the cells' pixel span, padded one cell each side to cover
        # auto-tile neighbour re-resolution + grid lines (dirty-rect, DEP-3).
        px = (cx - 1) * tw
        py = (cy - 1) * th
        pw = (cw + 2) * tw
        ph = (ch + 2) * th

        def _refresh() -> None:
            # Chunk-scoped dirty invalidation (D2): the edit already bumped only the
            # touched chunks' versions in logic/, so re-painting this padded cell
            # rect re-renders exactly those chunks (version miss) while untouched
            # chunks re-blit. Cancel any in-flight cold warm so a concurrent
            # off-thread read of a just-mutated chunk can never cache stale content.
            self._scene.cancel_warm()
            self._scene.ensure_pixel_rect(cx * tw, cy * th, cw * tw, ch * th)
            self._scene.invalidate(
                QRectF(float(px), float(py), float(pw), float(ph)),
                QGraphicsScene.SceneLayer.BackgroundLayer,
            )
            if self._on_changed is not None:
                self._on_changed()

        stack.push(TilemapCommand(command, _refresh, label))

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _warn_no_active_brush(self, tilemap: Tilemap) -> None:
        """Surface why a stamp/fill was refused for gid 0 (FIX 5, no-silent-result).

        gid 0 is both the brush's default and the state of a document with no
        tileset bound yet, so the two cases get distinct, honest signals
        instead of one silent no-op -- and, per the CI-red fix of
        2026-08-24, a SIGNAL rather than a blocking ``QMessageBox.warning``:
        this refusal is reachable from a plain mouse gesture (a stray stamp
        click with no brush selected), and a modal there blocks headless
        parallel test workers indefinitely (worker crash, not an assertion
        failure). The shell surfaces the notice non-blockingly, following the
        ``lockedLayerEditRejected`` precedent exactly.
        """
        if not tilemap.tilesets:
            self.noTilesetBoundRejected.emit()
        else:
            self.noActiveBrushRejected.emit()

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Tilemap canvas"))
        self.setAccessibleDescription(
            self.tr(
                "Tilemap: left-click to stamp/erase/fill, middle-drag to pan, "
                "H/V flip, R rotate"
            )
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Re-translate the accessible strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
