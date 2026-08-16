"""Canvas-render acceptance tests (REQ-P1-UI-001..003, -007 grid).

Scenarios SC-UI-001-1/-2, SC-UI-002-1/-2, SC-UI-003-1/-2, SC-UI-007-1/-2.
Each runs under both themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from pixelart_creator.logic.constants import TILE_SIZE

RED = (255, 0, 0, 255)


def _render(scene, doc_w, doc_h, scale):
    """Render ``scene`` nearest-neighbour into an RGBA image at ``scale``."""
    img = QImage(doc_w * scale, doc_h * scale, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.render(
        painter,
        QRectF(0, 0, doc_w * scale, doc_h * scale),
        QRectF(0, 0, doc_w, doc_h),
    )
    painter.end()
    return img


def _rgba(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


# -- REQ-P1-UI-001 --------------------------------------------------------


def test_sc_ui_001_1_buffer_pixel_rendered_no_aa(make_scene):
    """SC-UI-001-1: buffer pixel (3,3)=RED renders exactly RED, no AA edge."""
    scene = make_scene(8, 8)
    scene.active_buffer().set_pixel(3, 3, RED)
    # The scene now displays the flattened composite (REQ-P4-UI-012); a direct
    # buffer poke bypasses the paint pipeline, so recomposite explicitly.
    scene.refresh_all()
    scale = 20
    img = _render(scene, 8, 8, scale)
    # Centre of the (3,3) cell is exactly RED.
    assert _rgba(img, 3 * scale + scale // 2, 3 * scale + scale // 2) == RED
    # Hard boundary: the column just outside the cell is NOT red and is uniform
    # (no anti-aliased gradient bleeding across the pixel edge).
    outside = _rgba(img, 3 * scale - 1, 3 * scale + scale // 2)
    inside = _rgba(img, 3 * scale, 3 * scale + scale // 2)
    assert inside == RED
    assert outside != RED
    assert outside == _rgba(img, 3 * scale - 1, 3 * scale + scale // 2 + 5)


def test_sc_ui_001_2_magnified_pixel_is_solid_square(make_scene):
    """SC-UI-001-2: at deep zoom a painted pixel is a solid crisp square."""
    scene = make_scene(4, 4)
    scene.active_buffer().set_pixel(1, 1, RED)
    # Recomposite after the direct poke: the scene shows the composite, not the
    # raw active buffer (REQ-P4-UI-012).
    scene.refresh_all()
    scale = 32  # 3200 %
    img = _render(scene, 4, 4, scale)
    x0, y0 = 1 * scale, 1 * scale
    # Every sampled point inside the cell is identical RED (uniform square).
    for sx in (x0 + 1, x0 + scale // 2, x0 + scale - 2):
        for sy in (y0 + 1, y0 + scale // 2, y0 + scale - 2):
            assert _rgba(img, sx, sy) == RED
    # Immediately outside the square is not red (crisp edge).
    assert _rgba(img, x0 - 1, y0 + scale // 2) != RED


# -- REQ-P1-UI-002 --------------------------------------------------------


def test_sc_ui_002_1_scene_rect_matches_document(make_scene):
    """SC-UI-002-1: a new 64x64 document yields sceneRect (0,0,64,64)."""
    scene = make_scene(64, 64)
    assert scene.sceneRect() == QRectF(0, 0, 64, 64)


def test_sc_ui_002_2_resize_updates_scene_rect(make_scene):
    """SC-UI-002-2 (legacy seam): ``on_document_resized`` also updates the scene
    rect, but this entry point is NOT called by any shipped UI action today —
    ``grep`` finds no caller of ``CanvasScene.on_document_resized`` anywhere in
    ``pixelart_creator/`` (AGT-06 audit, T-14). Kept as a direct-API regression
    guard on the method itself; the criterion's SHIPPED coverage is
    ``test_sc_ui_002_2_scale_via_shipped_on_scale_updates_scene_rect`` below,
    which drives the real ``Main_Window._on_scale`` -> ``rebind_active`` ->
    ``_apply_scene_rect`` path a user actually reaches.
    """
    scene = make_scene(64, 64)
    scene._document.resize_canvas(128, 96)
    scene.on_document_resized(128, 96)
    assert scene.sceneRect() == QRectF(0, 0, 128, 96)


def test_sc_ui_002_2_scale_via_shipped_on_scale_updates_scene_rect(qtbot, monkeypatch):
    """SC-UI-002-2 (T-14, AGT-06 audit): the scene rect updates through the
    SHIPPED, user-reachable resize path — ``Main_Window._on_scale`` accepting
    the ``Scale_Dialog`` -> ``_apply_buffer_command`` (dims-changing) ->
    ``CanvasScene.rebind_active`` -> ``CanvasScene._apply_scene_rect`` — not the
    orphaned ``on_document_resized`` direct-API call the prior test exercises.
    """
    from PySide6.QtWidgets import QDialog

    from pixelart_creator.ui.main_window import Main_Window
    from pixelart_creator.ui.transform_dialog import Scale_Dialog

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    src_w, src_h = record.document.width, record.document.height
    assert record.scene.sceneRect() == QRectF(0, 0, src_w, src_h)

    monkeypatch.setattr(Scale_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        Scale_Dialog, "target_size", lambda self: (src_w * 2, src_h * 2)
    )
    win._on_scale()

    assert record.stack.count() == 1
    assert record.scene.sceneRect() == QRectF(0, 0, src_w * 2, src_h * 2)
    record.stack.undo()
    assert record.scene.sceneRect() == QRectF(0, 0, src_w, src_h)


# -- REQ-P1-UI-003 --------------------------------------------------------


def test_sc_ui_003_1_draw_background_only_exposed_rect(make_scene):
    """SC-UI-003-1: drawBackground paints only near the exposed rect."""
    scene = make_scene(64, 64)  # scene size is immaterial to the cull (F2/D2)
    img = QImage(600, 600, QImage.Format.Format_RGBA8888)
    sentinel = Qt.GlobalColor.transparent
    img.fill(sentinel)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, 64, 64))
    painter.end()
    # A pixel inside the exposed rect was painted (opaque checker).
    assert img.pixelColor(10, 10).alpha() == 255
    # A pixel far outside the exposed rect (+ tile ring) is untouched.
    assert img.pixelColor(500, 500).alpha() == 0


def test_sc_ui_003_2_background_tiles_on_tile_size(make_scene):
    """SC-UI-003-2: checker tile boundary falls on a TILE_SIZE multiple."""
    scene = make_scene(256, 256)
    img = QImage(256, 256, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, 200, 200))
    painter.end()
    # Tile (0,0) and tile (1,0) use alternating checker colours; the change
    # occurs exactly at x == TILE_SIZE.
    left_tile = img.pixelColor(TILE_SIZE - 2, 10)
    right_tile = img.pixelColor(TILE_SIZE + 2, 10)
    assert left_tile != right_tile
    assert img.pixelColor(TILE_SIZE - 2, 10) == img.pixelColor(2, 10)


# -- REQ-P1-UI-007 (grid overlay) ----------------------------------------


def test_sc_ui_007_1_grid_off_by_default(make_scene):
    """SC-UI-007-1: the per-pixel grid overlay is off by default (CL-4)."""
    scene = make_scene(32, 32)
    assert scene.is_grid_enabled() is False


def _draw_bg_at_scale(scene, scale, size=32):
    img = QImage(size, size, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    painter.setWorldTransform(QTransform().scale(scale, scale))
    scene.drawBackground(painter, QRectF(0, 0, size, size))
    painter.end()
    return bytes(img.constBits())


def test_sc_ui_007_2_grid_appears_past_threshold(make_scene):
    """SC-UI-007-2: enabled grid shows only past GRID_MIN_PIXEL_EDGE_PX (8)."""
    scene = make_scene(32, 32)
    # Below the legibility threshold: enabling the grid changes nothing drawn.
    below_off = _draw_bg_at_scale(scene, 4)
    scene.set_grid_enabled(True)
    below_on = _draw_bg_at_scale(scene, 4)
    assert below_on == below_off  # grid suppressed at < 8 device px/pixel
    # At/above the threshold: the grid overlay is now painted (output differs).
    scene.set_grid_enabled(False)
    above_off = _draw_bg_at_scale(scene, 8)
    scene.set_grid_enabled(True)
    above_on = _draw_bg_at_scale(scene, 8)
    assert above_on != above_off  # grid visible at >= 8 device px/pixel
