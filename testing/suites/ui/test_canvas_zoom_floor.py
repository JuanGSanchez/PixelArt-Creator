"""Zoom-floor + pan-reachability acceptance tests (REQ-CGS-UI-008, -009).

**REQ-CGS-UI-008 — the canvas is never zoomed out below 1:1.** The floor
(``ZOOM_MIN`` == 1.0) must hold no matter which of the four available
zoom-out routes is used: the zoom-out control, a keyboard preset stop, the
wheel gesture, and ``fit()``. A floor that holds for one route and leaks
through another is the exact shape of defect this module guards against
(``SC-CGS-UI-008-1``); an 8K document must land at exactly 1.0 when it is
created or opened (``SC-CGS-UI-008-2``); zooming in must be unaffected and
still reach ``ZOOM_MAX`` (``SC-CGS-UI-008-3``).

**REQ-CGS-UI-009 — every part of the canvas is reachable by panning,
including each of the four corners at the viewport centre.** The
measurement that motivated the corner assertion below
(``plan.md`` §3.7, ruling CGS-R3, finding M-5): with the scene's OWN rect
equal to the document (the pre-fix shape,
``canvas_scene.py`` ``setSceneRect(0, 0, document.width, document.height)``),
a 512-px document viewed through a 224-px viewport at zoom 1 lets the
viewport centre reach only scene ``[111, 399]`` on EACH axis -- so neither
corner ``(0, 0)`` nor ``(512, 512)`` could ever be centred.
``Canvas_View._apply_pan_margin`` fixes this by inflating the VIEW's own
scene rect (never the scene's own, which ``_fit_zoom`` reads and tiled mode
rewrites) by half a viewport in scene units, plus a small derived slack, so
this module reuses the SAME 512-px document / 224-px viewport pairing --
the exact scenario the fix was measured against, not an arbitrary one.

Both light and dark theme run automatically (the autouse ``theme`` fixture
in ``conftest.py`` parametrises every test in this suite). Zoom and pan
geometry do not depend on theme at all, so this module makes no attempt to
opt out of that parametrisation -- there is no supported per-test opt-out in
this suite, and every other module accepts the same doubling; it simply
does not exercise anything theme-related on top of it.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QUndoStack, QWheelEvent
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_PRESET_STOPS,
)
from pixelart_creator.ui.canvas_view import Canvas_View

_DOC_SIZE = 512
_VIEWPORT_SIZE = 224  # the exact pairing measured in plan.md §3.7 (M-5)

#: Half a document pixel (``SC-CGS-UI-009-1``): scrollbars are integer-valued
#: and Qt rounds, so the implementation compensates with a small derived
#: slack (``_apply_pan_margin``'s ``+ 1.0 / zoom``) rather than eliminating
#: rounding outright. Tight enough to catch a genuine regression (a corner
#: landing a whole document pixel away, as the pre-fix M-5 shape did) while
#: staying honest about the rounding that legitimately exists.
CORNER_TOLERANCE_DOC_PX = 0.5

# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


def _build_view(make_scene, qtbot, doc_w: int, doc_h: int, vp_w: int, vp_h: int):
    """Build a ``Canvas_View`` over a fresh scene, settled to a REAL viewport.

    A bare ``resize()``/``setFixedSize()`` leaves ``viewport().rect()`` stale
    until Qt processes the pending scrollbar-space layout pass -- measured
    directly while building this module: immediately after
    ``setFixedSize(224, 224)`` the viewport still reported ``624x478`` (the
    pre-resize default), settling to the correct, scrollbar-adjusted
    ``208x208`` only once ``QApplication.processEvents()`` ran. ``set_zoom``
    is then called once more (its own current value; a no-op on the zoom
    itself) purely to force ``_apply_pan_margin`` to recompute against the
    SETTLED viewport size rather than the transitional one seen at
    construction/resize.
    """
    scene = make_scene(doc_w, doc_h)
    stack = QUndoStack()
    view = Canvas_View(scene, stack)
    qtbot.addWidget(view)
    view.setFixedSize(vp_w, vp_h)
    QApplication.processEvents()
    view.set_zoom(view.zoom())
    return view, scene, stack


def _viewport_centre_scene_point(view) -> QPointF:
    """Return the scene point currently at the viewport's true geometric centre.

    ``QGraphicsView.mapToScene`` only accepts an integer ``QPoint`` (there is
    no fractional device pixel to map), so this samples the device pixel that
    CONTAINS the viewport's continuous centre: ``width // 2`` /
    ``height // 2`` on each axis.

    Deliberately NOT ``viewport().rect().center()``: a ``QRect``'s
    ``center()`` derives from ``right()``/``bottom()`` (``left + width - 1``),
    which truncates half a pixel short of the true centre on an even-sized
    viewport. This was caught empirically while building this module -- see
    the report's withdrawn finding: an initial probe using ``rect().center()``
    measured every corner landing exactly 1.0 document pixel short (a
    seemingly failing result), and switching to ``width // 2`` /
    ``height // 2`` reproduced the SAME scenario at exactly 0.0 -- the
    original -1.0 was this harness's own measurement bug, not a product
    defect.
    """
    vp = view.viewport().rect()
    centre_px = QPoint(vp.width() // 2, vp.height() // 2)
    return QPointF(view.mapToScene(centre_px))


# --------------------------------------------------------------------------- #
# REQ-CGS-UI-008 / SC-CGS-UI-008-1 -- the floor holds by EVERY route.         #
# --------------------------------------------------------------------------- #


def test_sc_cgs_ui_008_1_floor_holds_via_zoom_out_control(make_scene, qtbot):
    """SC-CGS-UI-008-1 (route 1/4 -- the zoom-out control).

    ``Canvas_View.zoom_out()`` is the method every zoom-out control
    (View-menu action, Ctrl+- shortcut) calls -- ``main_window.py``'s
    ``_on_zoom_out`` binds directly to it. Starting from ``ZOOM_MAX`` and
    calling it enough times to walk every preset stop down past the floor,
    the zoom never drops below ``ZOOM_MIN``, and stays exactly there once
    reached (the ``fit()``-fallback branch ``zoom_out`` takes once no lower
    preset remains).

    Built over a document LARGER than the viewport (the same 512/224 pairing
    used elsewhere in this module): on a document smaller than the viewport
    ``fit()``'s fallback branch would zoom IN past 1.0 instead of landing on
    the floor, which is a different, valid behaviour this test must not
    mistake for a defect (caught while building this module -- see the
    report's withdrawn finding).
    """
    view, _scene, _stack = _build_view(
        make_scene, qtbot, _DOC_SIZE, _DOC_SIZE, _VIEWPORT_SIZE, _VIEWPORT_SIZE
    )
    view.set_zoom(ZOOM_MAX)
    for _ in range(len(ZOOM_PRESET_STOPS) + 2):  # walk every stop, then overshoot
        view.zoom_out()
        assert view.zoom() >= ZOOM_MIN
    assert view.zoom() == pytest.approx(ZOOM_MIN)


@pytest.mark.parametrize("stop", ZOOM_PRESET_STOPS)
def test_sc_cgs_ui_008_1_floor_holds_via_keyboard_preset_stop(make_scene, qtbot, stop):
    """SC-CGS-UI-008-1 (route 2/4 -- each keyboard preset stop).

    ``zoom_out()`` IS the keyboard-preset mechanism (``main_window.py``
    binds ``Ctrl+-`` directly to it). Parametrising the STARTING zoom over
    every entry of ``ZOOM_PRESET_STOPS`` proves the floor holds no matter
    which rung of the ladder the keyboard shortcut is pressed from, not only
    from the top. Same larger-than-viewport document as the sibling test
    above, for the same reason (the lowest stop's fallback route is
    ``fit()``, which only represents "zooming out" when the document is
    larger than the viewport).
    """
    view, _scene, _stack = _build_view(
        make_scene, qtbot, _DOC_SIZE, _DOC_SIZE, _VIEWPORT_SIZE, _VIEWPORT_SIZE
    )
    view.set_zoom(stop)
    view.zoom_out()
    assert view.zoom() >= ZOOM_MIN
    if stop == ZOOM_PRESET_STOPS[0]:  # already at the lowest preset (== ZOOM_MIN)
        assert view.zoom() == pytest.approx(ZOOM_MIN)


def test_sc_cgs_ui_008_1_floor_holds_via_wheel_gesture(make_view):
    """SC-CGS-UI-008-1 (route 3/4 -- the wheel gesture).

    Delivers real ``QWheelEvent`` zoom-out notches (negative ``angleDelta``,
    the same construction ``test_canvas_view.py``'s wheel test uses) straight
    into ``view.wheelEvent`` -- enough of them to reach and then try to pass
    the floor.
    """
    view, _scene, _stack = make_view(64, 64)
    view.set_zoom(ZOOM_MIN * 2)  # start above the floor, well within range
    wheel_out = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, -120),  # negative angle delta => zoom out
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    for _ in range(40):  # enough notches to reach and then try to cross the floor
        view.wheelEvent(wheel_out)
        assert view.zoom() >= ZOOM_MIN
    assert view.zoom() == pytest.approx(ZOOM_MIN)


def test_sc_cgs_ui_008_1_floor_holds_via_fit(make_scene, qtbot):
    """SC-CGS-UI-008-1 (route 4/4 -- ``fit()``).

    On a document larger than the viewport, the UNFLOORED fit computation
    (``_fit_zoom()``) is genuinely sub-1:1 -- asserted directly so this test
    is proven to exercise the clamp and not merely coincide with it -- yet
    ``fit()`` itself lands at exactly ``ZOOM_MIN``, never below.
    """
    view, _scene, _stack = _build_view(make_scene, qtbot, 512, 512, 224, 224)
    raw_fit = view._fit_zoom()
    assert raw_fit < ZOOM_MIN  # the document really is larger than the viewport
    view.fit()
    assert view.zoom() == pytest.approx(ZOOM_MIN)


# --------------------------------------------------------------------------- #
# SC-CGS-UI-008-2 -- an 8K document lands at exactly 1.0 on open.             #
# --------------------------------------------------------------------------- #


def test_sc_cgs_ui_008_2_8k_document_lands_at_exactly_one(make_scene, qtbot):
    """SC-CGS-UI-008-2: an 8K document (``MAX_CANVAS_WIDTH`` x
    ``MAX_CANVAS_HEIGHT``) opened into a realistic viewport lands at exactly
    ``ZOOM_MIN`` -- exercised via ``fit()``, the route ``main_window.py``
    calls on every new/opened tab (``_add_document_tab``'s ``view.fit()``,
    and again from ``apply_first_launch_layout``).
    """
    view, _scene, _stack = _build_view(
        make_scene, qtbot, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT, 800, 600
    )
    raw_fit = view._fit_zoom()
    assert raw_fit < ZOOM_MIN  # 800x600 into 7680x4320 is genuinely sub-1:1
    view.fit()
    assert view.zoom() == pytest.approx(ZOOM_MIN)


# --------------------------------------------------------------------------- #
# SC-CGS-UI-008-3 -- zoom-in is unaffected and still reaches ZOOM_MAX.        #
# --------------------------------------------------------------------------- #


def test_sc_cgs_ui_008_3_zoom_in_still_reaches_zoom_max(make_view):
    """SC-CGS-UI-008-3: zoom-in still reaches ``ZOOM_MAX`` and stops there --
    the floor change must not have narrowed the ceiling.
    """
    view, _scene, _stack = make_view(64, 64)
    view.set_zoom(ZOOM_MIN)
    for _ in range(len(ZOOM_PRESET_STOPS) + 2):  # walk every stop, then overshoot
        view.zoom_in()
        assert view.zoom() <= ZOOM_MAX
    assert view.zoom() == pytest.approx(ZOOM_MAX)


# --------------------------------------------------------------------------- #
# REQ-CGS-UI-009 -- every corner is reachable at the viewport centre.        #
# --------------------------------------------------------------------------- #


def test_sc_cgs_ui_009_1_every_corner_reaches_the_viewport_centre(make_scene, qtbot):
    """SC-CGS-UI-009-1: each of the document's four corners can be positioned
    at the centre of the viewport, within half a document pixel.

    Given a document larger than the viewport at 100% zoom (asserted, not
    assumed) -- the exact 512-px-document / 224-px-viewport pairing measured
    in ``plan.md`` M-5 -- when the user pans toward each of the four corners
    in turn, then each corner can be positioned at the centre of the
    viewport.
    """
    view, _scene, _stack = _build_view(
        make_scene, qtbot, _DOC_SIZE, _DOC_SIZE, _VIEWPORT_SIZE, _VIEWPORT_SIZE
    )
    vp = view.viewport().rect()
    assert _DOC_SIZE > vp.width()  # Given: the document IS larger than the viewport
    assert _DOC_SIZE > vp.height()

    corners = [(0, 0), (_DOC_SIZE, 0), (0, _DOC_SIZE), (_DOC_SIZE, _DOC_SIZE)]
    for cx, cy in corners:
        view.centerOn(QPointF(cx, cy))
        centre = _viewport_centre_scene_point(view)
        shortfall_x = abs(centre.x() - cx)
        shortfall_y = abs(centre.y() - cy)
        assert shortfall_x <= CORNER_TOLERANCE_DOC_PX, (
            f"corner ({cx}, {cy}): viewport centre reached scene "
            f"({centre.x()}, {centre.y()}) -- x shortfall {shortfall_x} "
            f"exceeds the {CORNER_TOLERANCE_DOC_PX}-doc-px tolerance"
        )
        assert shortfall_y <= CORNER_TOLERANCE_DOC_PX, (
            f"corner ({cx}, {cy}): viewport centre reached scene "
            f"({centre.x()}, {centre.y()}) -- y shortfall {shortfall_y} "
            f"exceeds the {CORNER_TOLERANCE_DOC_PX}-doc-px tolerance"
        )


def test_sc_cgs_ui_009_2_reachable_again_after_panning_back(make_scene, qtbot):
    """SC-CGS-UI-009-2: no part of the canvas becomes unreachable.

    Given the user has panned to a canvas corner, when the user pans back
    across the document toward each other corner in turn, then every one of
    them can still be brought into view -- the reachable range is not
    exhausted or left "stuck" by having visited an extreme first.
    """
    view, _scene, _stack = _build_view(
        make_scene, qtbot, _DOC_SIZE, _DOC_SIZE, _VIEWPORT_SIZE, _VIEWPORT_SIZE
    )
    view.centerOn(QPointF(0, 0))  # pan to a corner first
    _viewport_centre_scene_point(view)  # (observed only to force the pan through)

    corners_after = [
        (_DOC_SIZE, _DOC_SIZE),  # the opposite corner
        (_DOC_SIZE, 0),
        (0, _DOC_SIZE),
        (0, 0),  # back to the start
    ]
    for cx, cy in corners_after:
        view.centerOn(QPointF(cx, cy))
        centre = _viewport_centre_scene_point(view)
        assert abs(centre.x() - cx) <= CORNER_TOLERANCE_DOC_PX, (cx, cy, centre)
        assert abs(centre.y() - cy) <= CORNER_TOLERANCE_DOC_PX, (cx, cy, centre)
