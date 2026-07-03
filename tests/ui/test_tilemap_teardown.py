"""Phase-6 off-thread chunk-warm teardown / xdist-segfault guard (REQ-P6-UI-014, S1).

The tilemap canvas owns an off-GUI-thread chunk warmer (``_Tilemap_Scene``
``QThreadPool`` + ``TilemapChunkWarmSignals`` carrier). If a live worker or a
connected carrier survives a disposed window, a later test's GC cross-thread-GCs Qt
C++ objects and crashes PySide6 natively — the Phase-5 xdist ``worker 'gwN' crashed``
segfault class. AGT-05 wired ``Tilemap_Canvas.shutdown_warm()`` into
``MainWindow.shutdown_prewarm()`` (hence ``closeEvent``). These tests DISPATCH a real
off-thread warm, then prove the deterministic teardown drains the pool and releases
the carrier — for a standalone canvas AND for a whole ``Main_Window``. The module is
designed to pass under ``pytest -n auto`` with no worker crash (run in verification).
"""

from __future__ import annotations

from PySide6.QtGui import QUndoStack

from pixelart_creator.logic.constants import TILEMAP_CHUNK_SIZE
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas


def _dispatch_a_warm(canvas, tilemap, tileset):
    """Stamp content and enqueue one real off-thread chunk render on the scene."""
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)
    canvas._apply_stamp(0, 0)  # chunk (0,0) now has content + version > 0
    scene = canvas._scene
    version = tilemap.chunk_version(0, 0)
    chunk_px = TILEMAP_CHUNK_SIZE * tilemap.tile_width
    scene._dispatch_warm(0, 0, version, 0, 0, chunk_px, chunk_px)


def test_standalone_canvas_shutdown_warm_drains_and_releases(
    qtbot, theme, make_tilemap_setup
):
    """A standalone canvas: shutdown_warm drains the pool and releases the carrier."""
    tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))

    _dispatch_a_warm(canvas, tilemap, tileset)
    assert canvas._scene._warm_signals is not None  # carrier live before teardown

    canvas.shutdown_warm()
    scene = canvas._scene
    # No worker survives: pool drained, carrier released -> nothing to cross-thread-GC.
    assert scene._warm_signals is None
    assert scene._warm_pool.activeThreadCount() == 0
    assert not scene._warm_inflight

    canvas.shutdown_warm()  # idempotent: a second call is a safe no-op
    assert scene._warm_signals is None


def test_main_window_shutdown_prewarm_drains_tilemap_warmer(
    qtbot, theme, make_tilemap_setup
):
    """Disposing a Main_Window drains its tilemap warmer — no worker/carrier lives."""
    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    assert record is not None

    tileset, tilemap = make_tilemap_setup()
    record.document.make_add_tileset_command(tileset).execute()
    record.document.make_add_tilemap_command(tilemap).execute()
    win._active_tileset = tileset
    win._active_tilemap = tilemap
    win._bind_tilemap(record)

    _dispatch_a_warm(win._tilemap_canvas, tilemap, tileset)
    assert win._tilemap_canvas._scene._warm_signals is not None

    win.shutdown_prewarm()  # what closeEvent calls
    scene = win._tilemap_canvas._scene
    assert scene._warm_signals is None  # carrier released via shutdown_warm wiring
    assert scene._warm_pool.activeThreadCount() == 0
    win.shutdown_prewarm()  # idempotent


def test_cancel_warm_keeps_carrier_but_drains_inflight(
    qtbot, theme, make_tilemap_setup
):
    """cancel_warm (rebind/edit) drops in-flight work but keeps the carrier alive."""
    tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))

    _dispatch_a_warm(canvas, tilemap, tileset)
    canvas._scene.cancel_warm()
    # Lighter cousin of shutdown: carrier stays alive for a later dispatch.
    assert canvas._scene._warm_signals is not None
    assert not canvas._scene._warm_inflight
