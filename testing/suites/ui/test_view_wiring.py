"""Canvas view/scene wiring + branch coverage (REQ-P1-UI-002,-004,-005,-007).

Covers reachable setters and defensive branches: undo-stack rebind, grid
delegate, fit, wheel clamp no-op, keyboard non-space + space-release paths,
mouse fall-through to the base view, scene document rebind, preview-hide guard,
and the indexed-buffer render path. Both themes.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QKeyEvent, QMouseEvent, QPainter, QUndoStack

from pixelart_creator.logic.constants import ZOOM_MAX, ZOOM_MIN
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View

RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


def _mouse(etype, x, y, button, buttons):
    pt = QPointF(x, y)
    return QMouseEvent(etype, pt, pt, button, buttons, Qt.KeyboardModifier.NoModifier)


# -- view setters / zoom edges -------------------------------------------


def test_set_undo_stack_rebinds(make_view):
    """set_undo_stack rebinds the view to another document's stack (tab switch)."""
    view, _scene, _stack = make_view(32, 32)
    other = QUndoStack()
    view.set_undo_stack(other)
    assert view._undo_stack is other


def test_set_grid_enabled_delegates_to_scene(make_view):
    """set_grid_enabled toggles the scene's grid overlay (CL-4)."""
    view, scene, _stack = make_view(32, 32)
    view.set_grid_enabled(True)
    assert scene.is_grid_enabled() is True


def test_fit_sets_zoom_to_fit_minimum(make_view):
    """REQ-CGS-UI-008: fit() floors at ZOOM_MIN (1:1), not the document's raw
    fit-to-view computation, for a document larger than the viewport (-004).

    Superseded 2026-08-25: this used to assert ``zoom() == _fit_zoom()``
    exactly, which held only because the pre-ruling floor WAS the raw fit.
    This document's raw fit-to-view is still sub-1:1 -- that is exactly the
    case ZOOM_MIN's flat floor now guards against.
    """
    view, _scene, _stack = make_view(1024, 1024)
    raw_fit = view._fit_zoom()
    assert raw_fit < ZOOM_MIN  # premise: this document would fit below 100%
    view.fit()
    assert view.zoom() == pytest.approx(ZOOM_MIN)  # floored, never below it


def test_wheel_at_ceiling_is_noop(make_view):
    """A wheel notch at ZOOM_MAX makes no change (clamp no-op, -004)."""
    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(ZOOM_MAX)
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWheelEvent

    wheel = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    view.wheelEvent(wheel)
    assert view.zoom() == ZOOM_MAX


def test_zoom_out_below_first_preset_falls_to_fit(make_view):
    """REQ-CGS-UI-008: zoom_out() with no lower preset falls back to fit(),
    which is itself floored at ZOOM_MIN (-004).

    Superseded 2026-08-25: a request of 0.5 (below the old ``min(ZOOM_MIN,
    fit_zoom)`` floor) used to land AT the document's raw sub-1:1 fit.
    ``set_zoom`` now clamps 0.5 straight to ZOOM_MIN before the fallback path
    even runs; zoom_out()'s "no lower preset -> fit()" branch is still
    exercised, and fit() still cannot go below ZOOM_MIN either.
    """
    view, _scene, _stack = make_view(1024, 1024)
    assert view._fit_zoom() < ZOOM_MIN  # premise: raw fit is sub-1:1
    view.set_zoom(0.5)  # requests below the floor -> clamps to ZOOM_MIN
    assert view.zoom() == pytest.approx(ZOOM_MIN)
    view.zoom_out()  # no preset stop below ZOOM_MIN -> falls back to fit()
    assert view.zoom() == pytest.approx(ZOOM_MIN)  # fit() is floored too


# -- keyboard + mouse fall-through ---------------------------------------


def test_non_space_key_and_space_release(make_view):
    """A non-space key defers to the base view; Space release ends the modifier."""
    view, _scene, _stack = make_view(32, 32)
    view.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.NoModifier)
    )
    # engage then release Space
    view.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
        )
    )
    assert view._space_held is True
    view.keyReleaseEvent(
        QKeyEvent(
            QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier
        )
    )
    assert view._space_held is False


def test_left_click_without_tool_defers_to_base(make_view):
    """A left click with no active tool falls through to the base view."""
    view, scene, stack = make_view(32, 32)
    view.set_tool(None)
    before = scene.active_buffer().copy()
    view.mousePressEvent(
        _mouse(
            QEvent.Type.MouseButtonPress,
            4,
            4,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        )
    )
    assert scene.active_buffer() == before
    assert stack.count() == 0


def test_idle_move_and_release_defer_to_base(make_view):
    """A move/release while neither panning nor drawing defers to the base."""
    view, scene, stack = make_view(32, 32)
    before = scene.active_buffer().copy()
    view.mouseMoveEvent(
        _mouse(
            QEvent.Type.MouseMove,
            4,
            4,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
        )
    )
    view.mouseReleaseEvent(
        _mouse(
            QEvent.Type.MouseButtonRelease,
            4,
            4,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        )
    )
    assert scene.active_buffer() == before
    assert stack.count() == 0


# -- scene rebind / preview guard ----------------------------------------


def test_scene_set_document_rebinds_buffer_and_rect(make_document):
    """CanvasScene.set_document swaps the active buffer + scene rect (SC-UI-020-3)."""
    scene = CanvasScene(make_document(32, 32))
    doc_b = Document(48, 24, palette=Palette([RED, GREEN]))
    doc_b.frames[0].layers[-1].buffer.set_pixel(1, 1, GREEN)
    scene.set_document(doc_b)
    assert scene.sceneRect() == QRectF(0, 0, 48, 24)
    assert scene.active_buffer().get_pixel(1, 1) == GREEN


def test_hide_line_preview_without_preview_is_safe(make_document):
    """Hiding a non-existent line preview is a safe no-op (guard)."""
    scene = CanvasScene(make_document(16, 16))
    scene.hide_line_preview()  # no preview created yet
    assert scene._preview_item is None


# -- indexed-buffer render path ------------------------------------------


def test_indexed_scene_renders_palette_colour(theme):
    """An indexed buffer renders through its palette LUT (canvas_scene indexed)."""
    doc = Document(8, 8, mode=ColorMode.INDEXED, palette=Palette([RED, GREEN, BLUE]))
    doc.frames[0].layers[-1].buffer.set_pixel(3, 3, 2)  # index 2 == BLUE
    scene = CanvasScene(doc)
    scene.refresh_rect(QRectF(3, 3, 1, 1))  # exercises indexed sync_region
    scale = 10
    img = QImage(8 * scale, 8 * scale, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.render(painter, QRectF(0, 0, 8 * scale, 8 * scale), QRectF(0, 0, 8, 8))
    painter.end()
    c = img.pixelColor(3 * scale + scale // 2, 3 * scale + scale // 2)
    assert (c.red(), c.green(), c.blue(), c.alpha()) == BLUE
