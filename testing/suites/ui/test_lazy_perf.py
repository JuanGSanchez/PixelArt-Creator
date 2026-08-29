"""Lazy-path perf-fix coverage for the large-document open freeze.

These tests lock in the two UI-level laziness contracts that fixed the ~56 s
``new_document(8K)`` freeze (the 8K timing assertion itself lives in
``test_main_window.py::test_sc_ui_020_2_8k_document_supported``):

* **Lazy palette analytics** — while the analytics dock is HIDDEN, a
  document-open / document-change must trigger ZERO full-buffer scan; the
  deferred (debounced) scan runs only when the view becomes visible. Backs the
  AGT-05 ``request_refresh`` / ``on_dock_visibility_changed`` mechanism.
* **Lazy initial composite** — a freshly constructed RGBA ``CanvasScene`` starts
  ``_composite_dirty`` (no eager full-stack composite in ``__init__``); the
  composite is computed on the first ``drawBackground`` / paint and is correct.

Every test runs under both themes via the autouse ``theme`` fixture. Headless.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter

import pixelart_creator.ui.palette_analytics_view as analytics_mod
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.palette_analytics_view import Palette_Analytics_View

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]
RED = (230, 30, 30, 255)


def _painted_document() -> Document:
    """A small RGBA document with a few non-background pixels painted."""
    document = Document(8, 8, palette=Palette(STARTER))
    buffer = document.frames[0].layers[0].buffer
    for x in range(4):
        buffer.set_pixel(x, 0, RED)
    return document


# -- Lazy palette analytics ----------------------------------------------------


def test_lazy_analytics_hidden_dock_does_not_scan(qtbot, monkeypatch):
    """(a) request_refresh() while the view is hidden triggers NO buffer scan."""
    calls: list[Document] = []
    real = analytics_mod.document_usage_counts
    monkeypatch.setattr(
        analytics_mod,
        "document_usage_counts",
        lambda doc: (calls.append(doc), real(doc))[1],
    )

    document = _painted_document()
    widget = Palette_Analytics_View()
    qtbot.addWidget(widget)
    widget.set_document_provider(lambda: document)
    # The widget was never shown -> not visible; the lazy path must defer.
    assert widget.isVisible() is False

    widget.request_refresh()

    # No scan happened and the table stays empty; only the dirty flag is set.
    assert calls == []
    assert widget._pending is True
    assert widget._table.rowCount() == 0


def test_lazy_analytics_becoming_visible_scans_and_populates(qtbot, monkeypatch):
    """(b) Making the dock visible runs the debounced scan and populates."""
    calls: list[Document] = []
    real = analytics_mod.document_usage_counts
    monkeypatch.setattr(
        analytics_mod,
        "document_usage_counts",
        lambda doc: (calls.append(doc), real(doc))[1],
    )

    document = _painted_document()
    widget = Palette_Analytics_View()
    qtbot.addWidget(widget)
    widget.set_document_provider(lambda: document)
    widget.request_refresh()  # deferred while hidden
    assert calls == []

    # Report the dock has become visible (the QDockWidget.visibilityChanged path).
    widget.show()
    widget.on_dock_visibility_changed(True)

    # The debounce timer (150 ms) fires; wait for the deferred scan to land.
    qtbot.waitUntil(lambda: widget._table.rowCount() > 0, timeout=2000)

    assert calls  # the deferred scan ran exactly on becoming visible
    assert widget._pending is False
    expected = analytics_mod.document_usage_counts(document)
    assert widget._table.rowCount() == len(expected)


def test_lazy_analytics_debounce_coalesces_burst(qtbot, monkeypatch):
    """A burst of request_refresh() while visible coalesces to a single scan."""
    calls: list[Document] = []
    real = analytics_mod.document_usage_counts
    monkeypatch.setattr(
        analytics_mod,
        "document_usage_counts",
        lambda doc: (calls.append(doc), real(doc))[1],
    )

    document = _painted_document()
    widget = Palette_Analytics_View()
    qtbot.addWidget(widget)
    widget.set_document_provider(lambda: document)
    widget.show()
    qtbot.waitExposed(widget)

    for _ in range(5):
        widget.request_refresh()  # visible -> arms/re-arms the single-shot timer

    qtbot.waitUntil(lambda: widget._table.rowCount() > 0, timeout=2000)
    # Five bursts coalesced into one scan (single-shot debounce).
    assert len(calls) == 1


def test_lazy_analytics_new_document_with_hidden_dock_no_scan(qtbot, monkeypatch):
    """Integration: new_document with the analytics dock hidden does NOT scan."""
    calls: list[Document] = []
    real = analytics_mod.document_usage_counts
    monkeypatch.setattr(
        analytics_mod,
        "document_usage_counts",
        lambda doc: (calls.append(doc), real(doc))[1],
    )

    win = Main_Window()
    qtbot.addWidget(win)
    # The window is never shown in the headless suite, so the tabified analytics
    # dock is not visible: opening documents must defer every scan.
    assert win._analytics_view.isVisible() is False

    win.new_document(32, 32)
    win.new_document(48, 48)

    assert calls == []
    assert win._analytics_view._pending is True
    assert win._analytics_view._table.rowCount() == 0


# -- Lazy initial composite ----------------------------------------------------


def test_scene_starts_composite_dirty_without_eager_composite(make_scene):
    """(c) A fresh RGBA scene allocates the composite but leaves it un-computed."""
    scene = make_scene(16, 16)
    # RGBA scene composites; the buffer is allocated but the full-stack pass is
    # deferred, so construction is O(1) and the dirty flag is set.
    assert scene._compositing is True
    assert scene._composite is not None
    assert scene._composite_dirty is True


def test_scene_first_paint_computes_composite_correctly(make_scene):
    """(c) The first drawBackground/paint computes the composite and clears dirty."""
    scene = make_scene(8, 8)
    scene.active_buffer().set_pixel(3, 3, RED)
    # Deferred: the poked pixel is not yet in the composite until first paint.
    assert scene._composite_dirty is True

    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    # drawBackground calls _ensure_composite() before the pixmap item blits it.
    scene.drawBackground(painter, QRectF(0, 0, 8, 8))
    painter.end()

    assert scene._composite_dirty is False
    assert scene._composite.get_pixel(3, 3) == RED


def test_scene_ensure_composite_is_idempotent(make_scene):
    """A second paint after a clean composite does not re-mark it dirty."""
    scene = make_scene(8, 8)
    img = QImage(8, 8, QImage.Format.Format_RGBA8888)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    scene.drawBackground(painter, QRectF(0, 0, 8, 8))
    scene.drawBackground(painter, QRectF(0, 0, 8, 8))
    painter.end()
    assert scene._composite_dirty is False
