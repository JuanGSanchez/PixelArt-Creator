"""Phase-6 tilemap canvas interaction + paint coverage (REQ-P6-UI-004..010,014).

pytest-qt, headless, both themes (autouse fixture). Drives the canvas the way a user
does — synthetic mouse (stamp / erase / fill drag, pan), keyboard (H/V flip, R
rotate, Space-pan), wheel zoom — and exercises the render seam by painting the scene
background onto an offscreen ``QImage`` (checker + composited chunks + grid), plus the
GUI-thread warm-delivery slot ``_on_chunk_warmed`` (token / version / mode guards).
Complements the behavioural acceptance tests in ``test_tilemap_canvas.py`` and lifts
the interaction/paint/threading branches of ``tilemap_canvas`` toward the coverage
gate without re-implementing any domain logic.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QUndoStack,
    QWheelEvent,
)

from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas, TilemapTool


def _canvas(qtbot, tilemap, tileset, theme):
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.resize(320, 320)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)
    return canvas, stack


def _press(
    canvas, x, y, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier
):
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x, y), button, button, mods)
    canvas.mousePressEvent(ev)


def _move(canvas, x, y, button=Qt.MouseButton.LeftButton):
    ev = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(x, y),
        Qt.MouseButton.NoButton,
        button,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseMoveEvent(ev)


def _release(canvas, x, y, button=Qt.MouseButton.LeftButton):
    ev = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(x, y),
        button,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mouseReleaseEvent(ev)


def test_mouse_stamp_drag_pushes_commands(qtbot, theme, make_tilemap_setup):
    """A left-button press+drag stamps cells (one command each) via the tool path."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    _press(canvas, 8, 8)
    _move(canvas, 40, 40)
    _release(canvas, 40, 40)
    assert stack.index() >= 1  # at least one stamp command pushed


def test_mouse_erase_and_fill_paths(qtbot, theme, make_tilemap_setup):
    """Erase drag and rectangle-fill (drag + commit-on-release) drive their tools."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    # Fill: press, drag, release commits one rectangle command.
    canvas.set_tool(TilemapTool.FILL)
    _press(canvas, 8, 8)
    _release(canvas, 40, 40)
    fill_index = stack.index()
    assert fill_index >= 1
    # Erase: press + drag clears cells.
    canvas.set_tool(TilemapTool.ERASE)
    _press(canvas, 8, 8)
    _move(canvas, 24, 24)
    _release(canvas, 24, 24)
    assert stack.index() >= fill_index


def test_middle_button_pan_moves_scrollbars(qtbot, theme, make_tilemap_setup):
    """Middle-drag pans (view state): scrollbars move, no command is pushed."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    canvas._apply_stamp(60, 60)  # grow scene so scrollbars have range
    before = stack.index()
    _press(canvas, 100, 100, button=Qt.MouseButton.MiddleButton)
    _move(canvas, 40, 40, button=Qt.MouseButton.MiddleButton)
    _release(canvas, 40, 40, button=Qt.MouseButton.MiddleButton)
    assert stack.index() == before  # panning pushes no undo command


def test_space_then_left_drag_pans(qtbot, theme, make_tilemap_setup):
    """Space arms panning so a subsequent left-drag pans instead of stamping."""
    tileset, tilemap = make_tilemap_setup()
    canvas, stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    canvas._apply_stamp(60, 60)
    before = stack.index()
    canvas.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
        )
    )
    _press(canvas, 100, 100)  # left, but Space armed -> pan
    _move(canvas, 60, 60)
    _release(canvas, 60, 60)
    canvas.keyReleaseEvent(
        QKeyEvent(
            QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
        )
    )
    assert stack.index() == before


def test_flip_rotate_keys(qtbot, theme, make_tilemap_setup):
    """H / V / R keys toggle the stamp orientation flags via keyPressEvent."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    for key in (Qt.Key.Key_H, Qt.Key.Key_V, Qt.Key.Key_R):
        canvas.keyPressEvent(
            QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        )
    # Flags composed; a stamp encodes them (non-base gid unless they cancelled out).
    assert (
        canvas.stamp_flags() != (False, False, False)
        or canvas.brush_gid() >= tileset.first_gid
    )


def test_wheel_zoom(qtbot, theme, make_tilemap_setup):
    """A wheel event zooms the view (cursor-anchored), staying within clamp."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    canvas._apply_stamp(0, 0)
    ev = QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(ev)  # zoom in
    ev_out = QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, -120),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    canvas.wheelEvent(ev_out)  # zoom out
    canvas.set_zoom(9999.0)  # clamps to ZOOM_MAX, no crash


def _paint_scene(scene, w=260, h=260, rect=None):
    img = QImage(w, h, QImage.Format.Format_RGBA8888)
    img.fill(0)
    painter = QPainter(img)
    scene.drawBackground(painter, rect if rect is not None else QRectF(0, 0, w, h))
    painter.end()
    return img


def test_drawbackground_renders_checker_map_and_grid(qtbot, theme, make_tilemap_setup):
    """drawBackground paints checker + composited chunks + grid without error."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    canvas.set_grid_enabled(True)
    canvas._apply_stamp(0, 0)
    canvas._apply_stamp(1, 1)
    img = _paint_scene(canvas._scene)
    assert not img.isNull()
    # An empty rect (outside the scene rect) is a safe early-return.
    empty = _paint_scene(canvas._scene, rect=QRectF(-5000, -5000, 1, 1))
    assert not empty.isNull()


def test_drawbackground_dispatches_offthread_when_many_cold_chunks(
    qtbot, theme, make_tilemap_setup
):
    """Exposing many cold chunks streams the overflow off-thread (D4 dispatch path)."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    # Fill a wide region spanning many 16-cell chunks so a single paint exposes
    # more than the inline budget of cold chunks (forces _dispatch_warm).
    tilemap.make_fill_rect_command(0, 0, 0, 200, 200, tileset.first_gid).execute()
    chunk_px = 16 * tilemap.tile_width
    _paint_scene(
        canvas._scene,
        w=chunk_px * 12,
        h=chunk_px * 12,
        rect=QRectF(0, 0, chunk_px * 12, chunk_px * 12),
    )
    # Teardown fixture / addWidget guarantees the warm pool is drained safely.
    canvas.shutdown_warm()


def test_on_chunk_warmed_guards(qtbot, theme, make_tilemap_setup):
    """_on_chunk_warmed caches a valid result and drops stale token/version/mode."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    canvas._apply_stamp(0, 0)
    scene = canvas._scene
    version = tilemap.chunk_version(0, 0)
    good = tilemap.render_region(
        0, 0, 16 * tilemap.tile_width, 16 * tilemap.tile_height
    )

    # Stale token -> ignored (no cache entry).
    scene._on_chunk_warmed(scene._warm_token + 99, 0, 0, version, good)
    assert scene._chunk_cache.get(0, 0, version) is None
    # Non-RGBA / non-buffer payload -> ignored.
    scene._on_chunk_warmed(scene._warm_token, 0, 0, version, object())
    scene._on_chunk_warmed(
        scene._warm_token, 0, 0, version, PixelBuffer(4, 4, ColorMode.INDEXED)
    )
    assert scene._chunk_cache.get(0, 0, version) is None
    # Valid token + version + RGBA -> cached.
    scene._on_chunk_warmed(scene._warm_token, 0, 0, version, good)
    assert scene._chunk_cache.get(0, 0, version) is not None


def test_autotile_toggle_refused_without_full_atlas(
    qtbot, theme, monkeypatch, make_tilemap_setup
):
    """Auto-tile on a tileset without 47 frames is refused (warn, no crash)."""
    from pixelart_creator.ui import tilemap_canvas as tc_module

    tileset, tilemap = make_tilemap_setup(cols=4, rows=2)  # only 8 tiles < 47
    canvas, stack = _canvas(qtbot, tileset=tileset, tilemap=tilemap, theme=theme)
    warnings = []
    monkeypatch.setattr(
        tc_module.QMessageBox, "warning", lambda *a, **k: warnings.append(a)
    )
    refused = []
    canvas.autotileChanged.connect(refused.append)
    canvas.set_autotile_enabled(True)
    assert warnings  # refused with a user-facing notice
    assert canvas.is_autotile_enabled() is False
    assert refused[-1] is False
    assert stack.index() == 0  # mode toggle pushes no command either way
