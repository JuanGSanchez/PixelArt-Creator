"""Deterministic Qt-event helpers for the pytest-qt UI suite (not collected).

Two families live here, and neither replaces the other:

- **Direct-handler helpers** (``press``/``release``/``click_pixel``/``drag_path``/
  ``prepare_for_click`` ...) build synthetic mouse/key events and drive the
  :class:`Canvas_View` handlers **directly** (``view.mousePressEvent(...)`` etc.),
  so a test can target an exact buffer pixel without depending on window layout.
  These are valid unit-level tests of the handler logic, but a direct call
  bypasses viewport hit-testing, widget geometry, event filters, overlay
  stacking and transform mapping — the layers a *real* click actually passes
  through.
- **Real-event helpers** (``real_click_pixel``/``real_press_pixel``/
  ``real_move_pixel``/``real_release_pixel``/``real_right_click_pixel``) deliver
  an actual ``QTest`` mouse event to the view's **viewport widget**, exercising
  that full real path. They take DOCUMENT pixel coordinates and map them
  through the view's own current scene mapping (``mapFromScene``) to a
  viewport point — never a hand-computed offset — so a test cannot silently
  click empty scene and read a no-op as a pass. A previous investigation lost
  time to exactly that mistake: a click at viewport (20, 20) mapped to scene
  (-4.0, -250.0), fired the tool with a negative pixel, and painted nothing —
  which looked like a product bug and was a measurement bug. If the mapped
  point falls outside the viewport's current rect, :func:`viewport_point_for_pixel`
  raises :class:`ViewportTargetError` rather than clicking somewhere arbitrary.

Both families now share that ONE coordinate source, :func:`viewport_point_for_pixel`
— see the contract note on :func:`prepare_for_click` below for why the
direct-handler family did not always work this way, and why it had to change.
"""

from __future__ import annotations

from typing import Iterable, Tuple

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest

LEFT = Qt.MouseButton.LeftButton
MIDDLE = Qt.MouseButton.MiddleButton
RIGHT = Qt.MouseButton.RightButton
NO_BTN = Qt.MouseButton.NoButton
NO_MOD = Qt.KeyboardModifier.NoModifier

Coord = Tuple[int, int]


class ViewportTargetError(RuntimeError):
    """A requested document pixel does not currently map into the viewport.

    Raised by :func:`viewport_point_for_pixel` (and everything built on it)
    instead of delivering a click at a clamped/arbitrary point. A test that
    hits this has asked for a pixel that is scrolled out of view, zoomed out
    of the widget, or otherwise not currently visible — fix the test's setup
    (resize/zoom/scroll/:func:`prepare_for_click` the view), never the
    assertion.
    """


def prepare_for_click(view) -> None:
    """Pin the view's zoom to identity and centre it on the document.

    **The new contract**: after this call, ``view.zoom() == 1.0`` (one scene
    unit is one viewport pixel — deterministic, no scale rounding) and every
    pixel of the document is inside the viewport's current ``rect()``. It
    makes NO promise about which scrollbar value that took, and — unlike the
    old contract — NO promise that viewport point ``(x, y)`` equals scene
    pixel ``(x, y)``. A test that wants a specific document pixel's viewport
    point must go through :func:`viewport_point_for_pixel`, exactly like the
    real-event helpers; every helper in this module already does.

    **Why the old contract broke.** This used to pin the view with
    ``resetTransform()`` + top-left alignment + ``setValue(0)`` on both
    scrollbars, on the assumption that scrollbar value ``0`` always lands
    scene ``(0, 0)`` at viewport ``(0, 0)``. That assumption depended on the
    view's own scrollable scene rect starting at the scene origin, which
    stopped being true once ``Canvas_View`` began inflating its OWN scene
    rect by a pan margin — half a viewport in scene units on every side, so
    every document corner can be brought to the viewport *centre*
    (``_apply_pan_margin``, REQ-CGS-UI-009). The document's own rect
    (``scene.sceneRect()``) is untouched; only the view's is inflated, and the
    inflated rect gets a NEGATIVE origin. Measured directly (16x16 document,
    400x400 view, zoom 1): the view's scrollable rect is
    ``QRectF(-193, -193, 402, 402)`` and the resulting horizontal/vertical
    scrollbar range is ``(-193, -175)`` — nowhere near 0. Two things then both
    go wrong for the old code:

    1. ``setValue(0)`` is silently clamped by Qt into that range (landing on
       ``-175``, the nearest bound), so scene ``(0, 0)`` maps to viewport
       ``(175, 175)`` instead of ``(0, 0)`` — not merely offset, but offset by
       an amount that depends on the viewport size and the document size
       both, so no single constant correction is possible.
    2. Even a "corrected" scrollbar value cannot fix it, because a legal
       scroll position that puts scene ``(0, 0)`` at viewport ``(0, 0)``
       may not exist at all: Qt bounds the scrollbar range to
       ``sceneRect.right() - viewport.width()`` (and the vertical analogue),
       and for a document that is small relative to the viewport plus its
       margin, that bound sits well short of 0. The pan margin is designed to
       let a document corner reach the viewport's *centre*, never its edge,
       by construction — so "scrollbar 0 == scene origin" is not a bug to
       patch, it is a contract that no longer holds for this shape of scene
       rect, in either direction.

    Given that, this function stops trying to make viewport (x, y) equal
    scene pixel (x, y) at all, and instead only guarantees the document is
    reachable; every caller reads the ACTUAL current mapping via
    :func:`viewport_point_for_pixel` (``view.mapFromScene``) to find out where
    a given document pixel really is. That works whether or not the view's
    scene rect has a negative origin, and whether or not the caller resized
    the viewport — verified directly against a negative-origin rect
    (``QRectF(-193, -193, 402, 402)``) as part of this fix.
    """
    view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    view.resetTransform()
    view._zoom = 1.0  # keep the tracked zoom consistent with the reset transform
    view.centerOn(view.scene().sceneRect().center())


def viewport_point_for_pixel(view, x: int, y: int) -> QPoint:
    """Map DOCUMENT pixel ``(x, y)`` to a viewport point via the view's own mapping.

    Targets a point ``0.4`` into the pixel (scene ``x + 0.4``, ``y + 0.4``) —
    the document/scene pixel grid is 1:1 (``CanvasScene.__init__`` calls
    ``setSceneRect(0, 0, document.width, document.height)`` once, F3) — so the
    mapped viewport point lands inside pixel ``(x, y)`` itself rather than on
    a shared edge with a neighbour. Goes through ``view.mapFromScene``, i.e.
    the view's CURRENT zoom/pan/alignment, never a hand-computed offset. This
    is the ONE coordinate source both helper families in this module share —
    see :func:`prepare_for_click` for why the direct-handler family did not
    always route through it.

    NOT ``+ 0.5`` (the geometric centre): ``QGraphicsView.mapFromScene``
    returns a ``QPoint`` and rounds half-away-from-zero, so the exact centre
    of pixel ``(x, y)`` at 1:1 zoom rounds UP to viewport point ``(x + 1, y +
    1)`` — this was caught empirically in this module's own self-tests
    (``test_real_event_harness.py``) as an off-by-one on both the painted
    pixel and the right-click coordinate before the ``0.4`` offset was
    chosen. ``0.4`` stays inside the pixel at any zoom ``>= 1.0`` (the only
    regime this harness is used in) without landing on the rounding boundary.

    Raises :class:`ViewportTargetError` if the mapped point falls outside the
    viewport's current ``rect()`` — fail loudly rather than deliver a click
    somewhere arbitrary and let the caller read silence as a pass.
    """
    scene_pt = QPointF(x + 0.4, y + 0.4)
    viewport_pt = view.mapFromScene(scene_pt)
    vp_rect = view.viewport().rect()
    if not vp_rect.contains(viewport_pt):
        raise ViewportTargetError(
            f"document pixel ({x}, {y}) -> scene ({scene_pt.x()}, {scene_pt.y()}) "
            f"-> viewport ({viewport_pt.x()}, {viewport_pt.y()}), which is outside "
            f"the current viewport rect {vp_rect.width()}x{vp_rect.height()} "
            f"(zoom={view.zoom():.4f}, "
            f"hscroll={view.horizontalScrollBar().value()}, "
            f"vscroll={view.verticalScrollBar().value()}). Resize/zoom/scroll the "
            "view so the pixel is visible before clicking it — this helper never "
            "clamps to the nearest visible point."
        )
    return viewport_pt


def _evt(view, etype: QEvent.Type, x: int, y: int, button, buttons) -> QMouseEvent:
    """Build a synthetic ``QMouseEvent`` at document pixel ``(x, y)``.

    Routed through :func:`viewport_point_for_pixel` — the view's own CURRENT
    mapping — exactly like the real-event helpers below, so a direct-handler
    event lands on the pixel it claims to regardless of scroll/zoom/pan-margin
    state. (This used to hand-build the position as ``(x + 0.2, y + 0.2)`` and
    assume that viewport point equalled scene pixel ``(x, y)`` directly; that
    was only ever true under :func:`prepare_for_click`'s old, now-broken pin —
    see its docstring.)
    """
    point = viewport_point_for_pixel(view, x, y)
    pt = QPointF(point.x(), point.y())
    return QMouseEvent(etype, pt, pt, button, buttons, NO_MOD)


def press(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a single button-press at document pixel ``(x, y)``."""
    view.mousePressEvent(_evt(view, QEvent.Type.MouseButtonPress, x, y, button, button))


def move(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a drag-move at document pixel ``(x, y)`` (button held)."""
    view.mouseMoveEvent(_evt(view, QEvent.Type.MouseMove, x, y, NO_BTN, button))


def release(view, x: int, y: int, button=LEFT) -> None:
    """Deliver a button-release at document pixel ``(x, y)``."""
    view.mouseReleaseEvent(
        _evt(view, QEvent.Type.MouseButtonRelease, x, y, button, NO_BTN)
    )


def click_pixel(view, x: int, y: int, button=LEFT) -> None:
    """Press + release at document pixel ``(x, y)`` (a full click)."""
    press(view, x, y, button)
    release(view, x, y, button)


def drag_path(view, points: Iterable[Coord], button=LEFT) -> None:
    """Press at the first point, move through the rest, release at the last."""
    pts = list(points)
    press(view, pts[0][0], pts[0][1], button)
    for x, y in pts[1:]:
        move(view, x, y, button)
    release(view, pts[-1][0], pts[-1][1], button)


def real_press_pixel(view, x: int, y: int, button=LEFT, modifier=NO_MOD) -> None:
    """Deliver a REAL ``QTest.mousePress`` at document pixel ``(x, y)``.

    Delivered to ``view.viewport()`` (never to ``view`` and never to a
    handler directly), so it passes through Qt's real hit-testing/geometry.
    """
    point = viewport_point_for_pixel(view, x, y)
    QTest.mousePress(view.viewport(), button, modifier, point)


def real_move_pixel(view, x: int, y: int) -> None:
    """Deliver a REAL ``QTest.mouseMove`` to document pixel ``(x, y)``.

    ``QTest.mouseMove`` carries no button argument — Qt tracks the
    already-pressed button internally — so this continues whatever button was
    armed by :func:`real_press_pixel`.
    """
    point = viewport_point_for_pixel(view, x, y)
    QTest.mouseMove(view.viewport(), point)


def real_release_pixel(view, x: int, y: int, button=LEFT, modifier=NO_MOD) -> None:
    """Deliver a REAL ``QTest.mouseRelease`` at document pixel ``(x, y)``."""
    point = viewport_point_for_pixel(view, x, y)
    QTest.mouseRelease(view.viewport(), button, modifier, point)


def real_click_pixel(view, x: int, y: int, button=LEFT, modifier=NO_MOD) -> None:
    """Deliver a REAL ``QTest.mouseClick`` (press + release) at document pixel ``(x, y)``.

    This is the real-event counterpart of :func:`click_pixel`: same call
    shape, but routed through ``QTest.mouseClick`` on the viewport instead of
    a direct ``mousePressEvent``/``mouseReleaseEvent`` call.
    """
    point = viewport_point_for_pixel(view, x, y)
    QTest.mouseClick(view.viewport(), button, modifier, point)


def real_right_click_pixel(view, x: int, y: int, modifier=NO_MOD) -> None:
    """Deliver a REAL right-click (``QTest.mouseClick``) at document pixel ``(x, y)``.

    ``Canvas_View.mousePressEvent`` dispatches the right-click menu itself
    (``_dispatch_menu``) from the button branch — it does not wait for a
    synthesized ``QContextMenuEvent`` — so this works under
    ``QT_QPA_PLATFORM=offscreen`` even though the offscreen platform does not
    synthesize a native context-menu event from a real click (verified
    separately for ``Timeline_Grid_View`` in
    ``test_timeline_grid_gestures.py``, which needed the
    ``QApplication.sendEvent(QContextMenuEvent(...))`` workaround for exactly
    that reason — ``Canvas_View`` does not need it).
    """
    real_click_pixel(view, x, y, button=RIGHT, modifier=modifier)


def real_drag_path(view, points: Iterable[Coord], button=LEFT) -> None:
    """Press at the first document pixel, move through the rest, release at the last.

    The real-event counterpart of :func:`drag_path`, entirely via
    ``QTest``/the viewport. Every point must map inside the current viewport
    or :class:`ViewportTargetError` is raised (fail loudly, not silently).
    """
    pts = list(points)
    real_press_pixel(view, pts[0][0], pts[0][1], button)
    for x, y in pts[1:]:
        real_move_pixel(view, x, y)
    real_release_pixel(view, pts[-1][0], pts[-1][1], button)


def press_space(view) -> None:
    """Deliver a Space key-press (engages the pan modifier, CL-3)."""
    view.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, NO_MOD))


def release_space(view) -> None:
    """Deliver a Space key-release (disengages the pan modifier)."""
    view.keyReleaseEvent(QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, NO_MOD))
