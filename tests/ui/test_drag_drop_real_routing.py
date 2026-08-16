"""T-12 — REAL Qt drag/drop event routing onto the canvas viewport.

``tests/ui/test_drag_drop_import.py`` proves the drop-handling *logic*
(``Main_Window.dragEnterEvent`` / ``dropEvent``) by calling those handlers
directly. That is a legitimate unit test of the routing/dispatch logic, but it
never proves the event actually **reaches** ``Main_Window`` when a real drag is
delivered to the canvas — the audit's suspicion (AGT-06 dispatch, T-12) is that
the canvas viewport is a :class:`~PySide6.QtWidgets.QGraphicsView` viewport
CHILD widget, and Qt drag/drop events are targeted at the widget under the
cursor, not the top-level window. ``Main_Window.setAcceptDrops(True)`` does
NOT itself make a child widget accept drops.

This test drives the REAL Qt event path: it builds genuine
``QDragEnterEvent`` / ``QDropEvent`` objects and delivers them via
``QApplication.sendEvent`` to the actual canvas viewport widget (the widget
that would be "under the cursor" for a drop landing on the canvas) — never
calling ``Main_Window.dropEvent`` directly.

**Fixed (regression test for the drop-routing fix — proven by reversion in
the commit pass).** T-12 originally discovered — and this module PINNED as a
strict ``xfail`` — that a drop delivered to ``Canvas_View.viewport()`` never
reached ``Main_Window.dropEvent`` (``QGraphicsView.dropEvent`` swallowed it
into a ``QGraphicsSceneDragDropEvent`` the scene never accepted, so it never
bubbled up). AGT-05 fixed the routing (``Canvas_View`` drag/drop overrides +
a ``set_drop_router`` seam wired in ``Main_Window._add_document_tab``); the
``xfail`` marker was removed once the fix made the test XPASS.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.main_window import Main_Window


def _make_png(path: Path, width: int, height: int, color=(230, 30, 30, 255)) -> Path:
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor(*color))
    assert image.save(str(path), "PNG")
    return path


def _mime(paths) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return mime


def test_t12_real_drop_on_canvas_viewport_reaches_main_window_import(qtbot, tmp_path):
    """T-12: a REAL drop delivered to the canvas viewport widget opens a new tab.

    Builds ``QDragEnterEvent``/``QDropEvent`` and delivers them via
    ``QApplication.sendEvent`` directly to ``Canvas_View.viewport()`` — the
    concrete widget under the cursor for a drop landing "on the canvas" — never
    calling ``Main_Window.dragEnterEvent``/``dropEvent`` directly. This is the
    real Qt event-routing path (the same one a native drag would take).

    Regression test for the drop-routing fix — proven by reversion in the
    commit pass. T-12 originally discovered that a drop delivered to
    ``Canvas_View.viewport()`` never reached ``Main_Window.dropEvent`` (Qt's
    ``QGraphicsView.dropEvent`` override swallowed it into a
    ``QGraphicsSceneDragDropEvent`` the scene never accepted). AGT-05 fixed
    this with ``Canvas_View`` drag/drop overrides plus a ``set_drop_router``
    seam wired in ``Main_Window._add_document_tab`` — a real drop on the
    canvas viewport now reaches the import routing.
    """
    # Regression test for the T-12 drop-routing fix — proven by reversion in
    # the commit pass.
    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    viewport = record.view.viewport()

    img = _make_png(tmp_path / "dropped.png", 6, 4)
    before = win._tab_widget.count()

    # Keep ``mime`` alive across both deliveries: neither event owns it.
    mime = _mime([str(img)])
    enter = QDragEnterEvent(
        QPoint(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, enter)
    del enter

    drop = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, drop)
    del drop

    # REAL routing reached Main_Window's import path: a new tab opened for the
    # dropped image (REQ-DDI-UI-001/-003).
    assert win._tab_widget.count() == before + 1
