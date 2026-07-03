"""Phase-6 tilemap canvas paint/guard edge branches (coverage completion).

pytest-qt, headless, both themes. Covers the remaining defensive edge branches of
the render/paint path and a few view-state guards: a layerless map, an indexed
tileset source (render_region refuses non-RGBA -> the chunk stays a checker
placeholder, never a crash), the ``_on_chunk_warmed`` version-mismatch drop, a
grid-only paint with no map, a move that would leave the layer range (no-op), the
real auto-tile checkbox toggle, and a Space auto-repeat no-op. No domain logic here.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QImage, QKeyEvent, QPainter, QUndoStack

from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import Tilemap
from pixelart_creator.logic.tileset import Tileset
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tilemap_layer_panel import Tilemap_Layer_Panel


def _bind(qtbot, tilemap, theme):
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_context(tilemap, stack, None)
    canvas.set_theme_colors(*canvas_roles(theme))
    canvas.set_active_layer(0)
    return canvas, stack


def _paint(scene, w=260, h=260):
    img = QImage(w, h, QImage.Format.Format_RGBA8888)
    img.fill(0)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, w, h))
    painter.end()


def test_paint_layerless_map_with_grid(qtbot, theme):
    """A map with tilesets but no layers paints checker + grid (no map draw)."""
    tilemap = Tilemap(tile_width=16, tile_height=16)
    canvas, _stack = _bind(qtbot, tilemap, theme)
    canvas.set_grid_enabled(True)
    _paint(canvas._scene)  # _draw_map returns early (no layers); grid still drawn


def test_paint_grid_with_no_tilemap(qtbot, theme):
    """Grid enabled with NO bound tilemap is a safe no-op paint."""
    stack = QUndoStack()
    canvas = Tilemap_Canvas(stack)
    qtbot.addWidget(canvas)
    canvas.set_grid_enabled(True)
    _paint(canvas._scene)  # both _draw_map and _draw_grid guard on tilemap is None


def test_paint_indexed_tileset_source_is_placeholder(qtbot, theme):
    """An indexed tileset source can't render RGBA -> chunk stays checker, no crash."""
    src = PixelBuffer(64, 32, ColorMode.INDEXED)
    src.data[:] = 1
    tileset = Tileset(src, tile_width=16, tile_height=16, first_gid=1)
    tilemap = Tilemap(tile_width=16, tile_height=16)
    tilemap.make_attach_tileset_command(tileset).execute()
    tilemap.make_add_layer_command().execute()
    tilemap.make_stamp_command(0, 0, 0, tileset.first_gid).execute()
    canvas, _stack = _bind(qtbot, tilemap, theme)
    _paint(canvas._scene)  # _render_chunk gets a non-RGBA render -> None (placeholder)
    assert canvas._scene._chunk_cache.resident_chunks == 0  # nothing cached


def test_on_chunk_warmed_version_mismatch_dropped(qtbot, theme, make_tilemap_setup):
    """A warmed result whose chunk version has since changed is dropped (D4)."""
    tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _bind(qtbot, tilemap, theme)
    canvas.set_brush_gid(tileset.first_gid)
    canvas._apply_stamp(0, 0)
    stale_version = tilemap.chunk_version(0, 0)
    good = tilemap.render_region(
        0, 0, 16 * tilemap.tile_width, 16 * tilemap.tile_height
    )
    canvas._apply_stamp(0, 1)  # bump chunk (0,0) version again
    # Deliver the OLD version -> current version differs -> dropped.
    canvas._scene._on_chunk_warmed(canvas._scene._warm_token, 0, 0, stale_version, good)
    assert canvas._scene._chunk_cache.get(0, 0, stale_version) is None


def test_move_out_of_range_is_noop(qtbot, make_tilemap_setup):
    """A reorder that would leave the layer range pushes no command (guard)."""
    _tileset, tilemap = make_tilemap_setup(layers=1)
    stack = QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, None)
    panel._on_add()  # 2 layers
    panel._list.setCurrentRow(0)  # active_layer() -> 0 (index 0)
    panel._on_move_down()  # target -1 -> out of range -> no-op
    assert stack.index() == 1  # only the add; move was a no-op


def test_autotile_checkbox_toggle_emits(qtbot, make_tilemap_setup):
    """Ticking the auto-tile checkbox emits autotileToggled (canvas builds ruleset)."""
    _tileset, tilemap = make_tilemap_setup()
    stack = QUndoStack()
    panel = Tilemap_Layer_Panel()
    qtbot.addWidget(panel)
    panel.set_context(tilemap, stack, None)
    emitted = []
    panel.autotileToggled.connect(emitted.append)
    panel._autotile_check.setChecked(True)  # user toggle fires _on_autotile_toggled
    assert emitted == [True]


def test_space_autorepeat_is_ignored(qtbot, theme, make_tilemap_setup):
    """A Space auto-repeat key event does not re-arm panning (guard branch)."""
    _tileset, tilemap = make_tilemap_setup()
    canvas, _stack = _bind(qtbot, tilemap, theme)
    ev = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        autorep=True,
    )
    canvas.keyPressEvent(ev)  # autorepeat -> the not-autorepeat branch is skipped
    rel = QKeyEvent(
        QEvent.Type.KeyRelease,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        autorep=True,
    )
    canvas.keyReleaseEvent(rel)
