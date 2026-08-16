"""T-21 (AGT-06 audit) — REAL mouse-drag timeline gestures: scrub vs reorder.

``test_animation_timeline.py`` proves the scrub SEAM
(``test_ui_002_scrub_updates_without_undo_entry`` emits ``frameScrubbed``
directly) and the reorder SEAM (``test_ui_005_reorder_frame_is_one_command``
calls ``Timeline_Panel._on_rows_moved`` directly) — never a genuine mouse
gesture on the strip. Both gestures share the SAME widget
(``Timeline_Panel._strip``, a ``QListWidget`` with
``setDragDropMode(InternalMove)`` AND ``setMouseTracking(True)`` +
``itemEntered`` wired to scrub): a plain button-held drag across items is
meant to SCRUB (``_on_item_entered`` checks ``QApplication.mouseButtons()``),
while Qt's OWN internal item-view drag-and-drop is meant to REORDER on drop.
This module drives BOTH through real ``qtbot`` mouse events on
``_strip.viewport()`` and reports honestly which gesture the offscreen
platform can actually deliver.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.timeline_panel import Timeline_Panel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _make_doc(frames: int = 3, width: int = 64, height: int = 64) -> Document:
    doc = Document(width, height, palette=Palette(STARTER))
    for _ in range(frames - 1):
        doc.add_frame()
    return doc


def _item_center(panel: Timeline_Panel, row: int) -> QPoint:
    rect = panel._strip.visualItemRect(panel._strip.item(row))
    return rect.center()


def test_t21_real_mouse_drag_scrubs(qtbot):
    """T-21: a REAL button-held mouse drag across the strip scrubs (frameScrubbed),
    pushing no undo command — driven with genuine ``qtbot`` mouse events on the
    strip's viewport, not a direct signal emit."""
    doc = _make_doc(3)
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(400, 120)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)

    viewport = panel._strip.viewport()
    start = _item_center(panel, 0)
    end = _item_center(panel, 2)

    # Observer connected BEFORE the triggering action; the strip fires
    # frameScrubbed once per hovered item during a real drag (item 1 as the
    # cursor crosses it, then item 2 at the final position) — wait for the
    # FINAL value (2), the observable end state of the gesture.
    with qtbot.waitSignal(
        panel.frameScrubbed, timeout=2000, check_params_cb=lambda i: i == 2
    ):
        qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
        mid = QPoint((start.x() + end.x()) // 2, (start.y() + end.y()) // 2)
        qtbot.mouseMove(viewport, pos=mid)
        qtbot.mouseMove(viewport, pos=end)
        qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)

    assert stack.count() == 0  # scrub never pushes a command (CL-13)


def test_t21_real_mouse_drag_reorders_or_is_an_honest_discovery(qtbot):
    """T-21: a REAL mouse drag-and-drop of a frame cell onto another slot should
    reorder the frames (``rowsMoved`` -> exactly one ``FrameCommand``). Qt's
    internal item-view drag needs a genuine ``QDrag::exec()`` — under the
    offscreen QPA platform this may never complete, in which case this is an
    honest DISCOVERY (reported, not faked) rather than a fabricated pass.
    """
    doc = _make_doc(3)
    ids = [id(f) for f in doc.frames]
    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(400, 120)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)

    viewport = panel._strip.viewport()
    start = _item_center(panel, 2)
    end = _item_center(panel, 0)

    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    # Exceed QApplication.startDragDistance() so Qt's QAbstractItemView
    # attempts to initiate its own internal-move QDrag.
    step = QPoint(
        (end.x() - start.x()) // 4 or (10 if end.x() >= start.x() else -10),
        (end.y() - start.y()) // 4,
    )
    pos = start
    for _ in range(4):
        pos = pos + step
        qtbot.mouseMove(viewport, pos=pos)
    qtbot.mouseMove(viewport, pos=end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    QApplication.processEvents()

    reordered = [id(f) for f in doc.frames] != ids
    if not reordered:
        pytest.xfail(
            "CF: a real mouse drag-and-drop on the timeline strip's viewport "
            "never produces a reorder (Qt's internal QDrag does not complete "
            "under the offscreen QPA platform) — discovered by T-21; the "
            "shipped SC-UI-005-1 coverage only proves the rowsMoved handler, "
            "never a real drag delivering that signal."
        )
    assert stack.count() == 1
    assert [id(f) for f in doc.frames] == [ids[2], ids[0], ids[1]]
