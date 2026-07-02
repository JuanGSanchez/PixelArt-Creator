"""Deterministic Qt-event helpers for the pytest-qt UI suite (not collected).

These build synthetic mouse/key events and drive the :class:`Canvas_View`
handlers directly so a test can target an exact buffer pixel without depending
on window layout. :func:`prepare_for_click` pins the view to identity transform +
top-left alignment + zero scroll, so a viewport point ``(x, y)`` maps to scene
pixel ``(x, y)`` (self-consistent, no display needed).
"""

from __future__ import annotations

from typing import Iterable, Tuple

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent

LEFT = Qt.MouseButton.LeftButton
MIDDLE = Qt.MouseButton.MiddleButton
RIGHT = Qt.MouseButton.RightButton
NO_BTN = Qt.MouseButton.NoButton
NO_MOD = Qt.KeyboardModifier.NoModifier

Coord = Tuple[int, int]


def prepare_for_click(view) -> None:
    """Pin the view so viewport point ``(x, y)`` maps to scene pixel ``(x, y)``."""
    view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    view.resetTransform()
    view._zoom = 1.0  # keep the tracked zoom consistent with the reset transform
    view.horizontalScrollBar().setValue(0)
    view.verticalScrollBar().setValue(0)


def _evt(etype: QEvent.Type, x: float, y: float, button, buttons) -> QMouseEvent:
    # +0.2 keeps QPointF.toPoint() (which the view applies) inside pixel (x, y).
    pt = QPointF(x + 0.2, y + 0.2)
    return QMouseEvent(etype, pt, pt, button, buttons, NO_MOD)


def press(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a single button-press at buffer pixel ``(x, y)``."""
    view.mousePressEvent(_evt(QEvent.Type.MouseButtonPress, x, y, button, button))


def move(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a drag-move at buffer pixel ``(x, y)`` (button held)."""
    view.mouseMoveEvent(_evt(QEvent.Type.MouseMove, x, y, NO_BTN, button))


def release(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a button-release at buffer pixel ``(x, y)``."""
    view.mouseReleaseEvent(_evt(QEvent.Type.MouseButtonRelease, x, y, button, NO_BTN))


def click_pixel(view, x: int, y: int, button=LEFT) -> None:
    """Press + release at buffer pixel ``(x, y)`` (a full click)."""
    press(view, x, y, button)
    release(view, x, y, button)


def drag_path(view, points: Iterable[Coord], button=LEFT) -> None:
    """Press at the first point, move through the rest, release at the last."""
    pts = list(points)
    press(view, pts[0][0], pts[0][1], button)
    for x, y in pts[1:]:
        move(view, x, y, button)
    release(view, pts[-1][0], pts[-1][1], button)


def press_space(view) -> None:
    """Deliver a Space key-press (engages the pan modifier, CL-3)."""
    view.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, NO_MOD))


def release_space(view) -> None:
    """Deliver a Space key-release (disengages the pan modifier)."""
    view.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, NO_MOD))
