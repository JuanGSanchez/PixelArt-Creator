"""Pointer acceptance: colour travel and view control.

One test per named scenario of `REQ-IS-UI-008` (plain wheel travels
Favourites), `-009` (``Shift``+wheel zooms), `-011` (middle click/drag
split), `-012` (middle-click picks the first favourite) and `-015`
(``Shift``+left-drag pans except under a selection tool) —
the input-scheme spec §9.3, scenarios ``SC-U008-1..6``,
``SC-U009-1..5``, ``SC-U011-1..4``, ``SC-U012-1..4``, ``SC-U015-1..5``.

Exercised against the implementation landed on ``feat-input-scheme``,
including the **D-16 amendment**:
plain wheel travels Favourites and ``Shift``+wheel zooms on **all four**
scrollable surfaces — the main canvas, the tilemap canvas, each extra
document view, and the reference board — not only the two painting
surfaces D-2 originally scoped. The D-16 extension tests below (reference
board / document view plain-wheel-travels-Favourites) carry no numbered
``SC-U008``/``SC-U009`` id of their own — spec.md predates D-16 and was
never amended — and say so in their own docstring rather than inventing one.

Both light and dark theme run automatically via ``conftest.py``'s autouse
``theme`` fixture; nothing here opts out of it. Headless
(``QT_QPA_PLATFORM=offscreen``), forced by the suite's own
``pytest_configure``.

**Cursor-anchor caveat (SC-U009-1), disclosed, not silently skipped.**
``Canvas_View._zoom_wheel``/``Tilemap_Canvas._zoom_wheel`` set
``QGraphicsView.AnchorUnderMouse`` before scaling; Qt resolves that anchor
from the REAL global cursor position (``QCursor::pos()``), not from the
synthesized ``QWheelEvent``'s own coordinates. Under the offscreen QPA
platform there is no real pointer to move, so "the document point under the
cursor is still under the cursor" cannot be driven deterministically here —
recorded as **could not verify — offscreen platform has no real global
cursor for ``AnchorUnderMouse`` to read**, and NOT presumed passing. What
*is* verified: the zoom step itself, and that the anchor mode configured for
the gesture is still ``AnchorUnderMouse`` (an observable, non-private Qt
view property) — i.e. the relocated code path still requests cursor
anchoring; only the pixel-stability measurement itself is unavailable here.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from pixelart_creator.logic.constants import (
    CLICK_DRAG_THRESHOLD_PX,
    SCALE_FACTOR,
    ZOOM_MIN,
)
from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.ui.multi_view import Multi_View
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas
from pixelart_creator.ui.tools import (
    LassoTool,
    MagicWandTool,
    PencilTool,
    RectSelectTool,
)
from testing.suites.ui._ui_helpers import (
    LEFT,
    MIDDLE,
    move,
    press,
    release,
    viewport_point_for_pixel,
)

NoMod = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier
Alt = Qt.KeyboardModifier.AltModifier

C0 = (10, 20, 30, 255)
C1 = (40, 50, 60, 255)
C2 = (70, 80, 90, 255)
C3 = (100, 110, 120, 255)


def _four_favourites() -> Favourites:
    """A 4-colour list; cursor lands on entry 0 (``Favourites.add`` on the
    first entry into an empty list, ``REQ-IS-LOGIC-001``)."""
    return Favourites([C0, C1, C2, C3])


def _wheel(delta_y: int, modifiers=NoMod) -> QWheelEvent:
    """A real ``QWheelEvent`` notch. Negative ``delta_y`` == wheel DOWN
    (``advance()``); positive == wheel UP (``retreat()``) — matches
    ``Canvas_View._favourites_wheel``'s own ``angleDelta().y() < 0`` test and
    the sibling suites' existing wheel-construction idiom."""
    return QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def _mod_evt(view, etype, x, y, button, buttons, modifiers) -> QMouseEvent:
    """A synthetic mouse event at document pixel ``(x, y)`` carrying
    ``modifiers`` — the modifier-aware counterpart of ``_ui_helpers._evt``
    (which is always ``NO_MOD``), built the same way ``test_rect_select_tool
    .py``'s ``_drag_mod`` does: through the view's OWN current mapping."""
    point = viewport_point_for_pixel(view, x, y)
    pt = QPointF(point.x(), point.y())
    return QMouseEvent(etype, pt, pt, button, buttons, modifiers)


def _drag_mod(view, x0, y0, x1, y1, modifiers, button=LEFT) -> None:
    """Press-move-release at document pixels, carrying ``modifiers`` throughout."""
    view.mousePressEvent(
        _mod_evt(view, QEvent.Type.MouseButtonPress, x0, y0, button, button, modifiers)
    )
    view.mouseMoveEvent(
        _mod_evt(
            view,
            QEvent.Type.MouseMove,
            x1,
            y1,
            Qt.MouseButton.NoButton,
            button,
            modifiers,
        )
    )
    view.mouseReleaseEvent(
        _mod_evt(
            view,
            QEvent.Type.MouseButtonRelease,
            x1,
            y1,
            button,
            Qt.MouseButton.NoButton,
            modifiers,
        )
    )


def _tilemap(qtbot, size=320) -> Tilemap_Canvas:
    """A bare, correctly-sized ``Tilemap_Canvas`` — wheel/middle/Favourites
    gestures need no bound tilemap (mirrors ``test_tilemap_zoom_floor.py``'s
    ``_build_canvas``)."""
    from PySide6.QtWidgets import QApplication

    canvas = Tilemap_Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(size, size)
    QApplication.processEvents()
    return canvas


def _tm_evt(etype, x, y, button, buttons, modifiers=NoMod) -> QMouseEvent:
    """Raw-viewport-pixel mouse event, matching
    ``test_tilemap_canvas_interaction.py``'s own local idiom for this
    surface (no scene-mapping helper is needed: the tilemap wheel/middle
    gestures under test here do not touch tilemap content)."""
    return QMouseEvent(etype, QPointF(x, y), button, buttons, modifiers)


def _tm_press(canvas, x, y, button=MIDDLE, modifiers=NoMod) -> None:
    canvas.mousePressEvent(
        _tm_evt(QEvent.Type.MouseButtonPress, x, y, button, button, modifiers)
    )


def _tm_move(canvas, x, y, button=MIDDLE, modifiers=NoMod) -> None:
    canvas.mouseMoveEvent(
        _tm_evt(QEvent.Type.MouseMove, x, y, Qt.MouseButton.NoButton, button, modifiers)
    )


def _tm_release(canvas, x, y, button=MIDDLE, modifiers=NoMod) -> None:
    canvas.mouseReleaseEvent(
        _tm_evt(
            QEvent.Type.MouseButtonRelease,
            x,
            y,
            button,
            Qt.MouseButton.NoButton,
            modifiers,
        )
    )


def _settle(app, iterations: int = 8) -> None:
    """Flush pending layout/timer-driven passes a bounded number of times
    (matches ``test_colour_pick_semantics.py``'s own idiom)."""
    for _ in range(iterations):
        app.processEvents()


# =========================================================================
# REQ-IS-UI-008 -- plain wheel travels the Favourites list (SC-U008-1..6)
# =========================================================================


def test_sc_u008_1_wheel_down_advances_cursor_and_sets_colour(make_view):
    """SC-U008-1: wheel-down advances the cursor and sets the active colour;
    the zoom level is unchanged."""
    view, _scene, _stack = make_view(64, 64)
    view.set_favourites_model(_four_favourites())
    before_zoom = view.zoom()

    view.wheelEvent(_wheel(-120))

    assert view.active_color() == C1  # entry 0 -> entry 1
    assert view.zoom() == pytest.approx(before_zoom)


def test_sc_u008_2_wheel_up_retreats_the_cursor(make_view):
    """SC-U008-2: wheel-up retreats the cursor (entry 2 -> entry 1)."""
    view, _scene, _stack = make_view(64, 64)
    favs = _four_favourites()
    favs.advance()
    favs.advance()  # cursor: 0 -> 1 -> 2
    view.set_favourites_model(favs)

    view.wheelEvent(_wheel(120))

    assert view.active_color() == C1


def test_sc_u008_3_same_gesture_works_on_the_tilemap_canvas(qtbot):
    """SC-U008-3: a plain wheel-down on the tilemap canvas advances the
    Favourites cursor (via ``colorPicked``) and leaves its zoom unchanged."""
    canvas = _tilemap(qtbot)
    canvas.set_favourites_model(_four_favourites())
    before_zoom = canvas.transform().m11()

    with qtbot.waitSignal(canvas.colorPicked, timeout=1000) as blocker:
        canvas.wheelEvent(_wheel(-120))

    assert blocker.args[0] == C1
    assert canvas.transform().m11() == pytest.approx(before_zoom)


def test_sc_u008_4_travel_wraps_at_the_end_of_the_list(make_view):
    """SC-U008-4: from the last entry, wheel-down wraps to the first."""
    view, _scene, _stack = make_view(64, 64)
    favs = _four_favourites()
    favs.advance()
    favs.advance()
    favs.advance()  # cursor: 0 -> 1 -> 2 -> 3 (last)
    view.set_favourites_model(favs)

    view.wheelEvent(_wheel(-120))

    assert view.active_color() == C0  # wrapped past the last entry


def test_sc_u008_4b_travel_wraps_at_the_start_of_the_list(make_view):
    """The other end of the same wrap rule: from the first entry, wheel-up
    wraps to the last (not written out as its own scenario id in spec.md,
    but the task explicitly requires both ends of the wrap covered)."""
    view, _scene, _stack = make_view(64, 64)
    favs = _four_favourites()  # cursor starts on entry 0
    view.set_favourites_model(favs)

    view.wheelEvent(_wheel(120))

    assert view.active_color() == C3  # wrapped before the first entry


def test_sc_u008_5_empty_favourites_list_is_a_silent_no_op(make_view):
    """SC-U008-5: an empty Favourites list -- no colour change, no zoom
    change, no error -- on the main canvas."""
    view, _scene, _stack = make_view(64, 64)
    view.set_favourites_model(Favourites())
    before_colour = view.active_color()
    before_zoom = view.zoom()

    view.wheelEvent(_wheel(-120))  # must not raise

    assert view.active_color() == before_colour
    assert view.zoom() == pytest.approx(before_zoom)


def test_sc_u008_5b_empty_favourites_list_is_a_silent_no_op_on_tilemap(qtbot):
    """SC-U008-5, tilemap surface: an empty list is a silent no-op there too."""
    canvas = _tilemap(qtbot)
    canvas.set_favourites_model(Favourites())
    before_zoom = canvas.transform().m11()

    canvas.wheelEvent(_wheel(-120))  # must not raise; no colorPicked to wait on

    assert canvas.transform().m11() == pytest.approx(before_zoom)


def test_sc_u008_6_the_gesture_raises_the_colour_feedback_square(qtbot):
    """SC-U008-6: the resulting colour change raises the colour feedback
    square (``REQ-IS-UI-024``), through the real, SHOWN ``Main_Window``
    wiring (``isVisible()`` needs a shown ancestor chain, not merely
    ``show()`` on the overlay itself -- see ``test_colour_pick_semantics.py``
    's ``create_app``/``_settle`` idiom, reused here)."""
    from pixelart_creator.ui.app import create_app

    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._favourites.add(C0)
    win._favourites.add(C1)
    win._favourites.add(C2)
    win._favourites.add(C3)
    record = win.active_tab()
    assert record is not None and record.feedback_overlay is not None
    assert record.feedback_overlay.isVisible() is False

    record.view.wheelEvent(_wheel(-120))
    _settle(app)

    assert win._active_color == C1
    assert record.feedback_overlay.isVisible() is True


# =========================================================================
# D-16 extension -- plain wheel also travels Favourites on the reference
# board and an extra document view. No SC-U008/-009 id of its own: spec.md
# predates D-16 (job-specification.md S14.1) and was never amended to add
# one; the task's own "WHAT LANDED" section is the source for this coverage.
# =========================================================================


def test_d16_plain_wheel_travels_favourites_on_the_reference_board(qtbot):
    """D-16: a plain wheel notch on the reference board travels Favourites
    (never zooms) and is a silent no-op with an empty list."""
    board = Reference_Board()
    qtbot.addWidget(board)
    board.set_favourites_model(_four_favourites())
    before_zoom = board._view.transform().m11()

    with qtbot.waitSignal(board.colorPicked, timeout=1000) as blocker:
        board.wheelEvent(_wheel(-120))

    assert blocker.args[0] == C1
    assert board._view.transform().m11() == pytest.approx(before_zoom)

    board2 = Reference_Board()
    qtbot.addWidget(board2)
    board2.set_favourites_model(Favourites())
    board2.wheelEvent(_wheel(-120))  # empty list: silent no-op, no error


def test_d16_plain_wheel_travels_favourites_on_an_extra_document_view(qtbot, make_view):
    """D-16: a plain wheel notch on an extra document view travels
    Favourites (never zooms) and is a silent no-op with an empty list."""
    _view, scene, _stack = make_view(16, 16)
    mv = Multi_View(scene)
    v = mv.open_view()
    qtbot.addWidget(v)
    v.set_favourites_model(_four_favourites())
    before_zoom = v.transform().m11()

    with qtbot.waitSignal(v.colorPicked, timeout=1000) as blocker:
        v.wheelEvent(_wheel(-120))

    assert blocker.args[0] == C1
    assert v.transform().m11() == pytest.approx(before_zoom)

    v2 = mv.open_view()
    qtbot.addWidget(v2)
    v2.set_favourites_model(Favourites())
    v2.wheelEvent(_wheel(-120))  # empty list: silent no-op, no error
    mv.close_all()


# =========================================================================
# REQ-IS-UI-009 -- Shift+wheel zooms (SC-U009-1..5)
# =========================================================================


def test_sc_u009_1_shift_wheel_up_zooms_in_by_the_shipped_step(make_view):
    """SC-U009-1: Shift+wheel-up zooms in by SCALE_FACTOR, anchored at the
    cursor. See the module docstring for the anchor-pixel caveat."""
    from PySide6.QtWidgets import QGraphicsView

    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(4.0)
    start = view.zoom()

    view.wheelEvent(_wheel(120, Shift))

    assert view.zoom() == pytest.approx(start * (1.0 + SCALE_FACTOR))
    assert view.transformationAnchor() == QGraphicsView.ViewportAnchor.AnchorUnderMouse


def test_sc_u009_2_shift_wheel_down_zooms_out_by_the_shipped_step(make_view):
    """SC-U009-2: Shift+wheel-down zooms out by SCALE_FACTOR."""
    view, _scene, _stack = make_view(1024, 1024)
    view.set_zoom(4.0)
    start = view.zoom()

    view.wheelEvent(_wheel(-120, Shift))

    assert view.zoom() == pytest.approx(start / (1.0 + SCALE_FACTOR))


def test_sc_u009_3_shift_wheel_does_not_change_the_active_colour(make_view):
    """SC-U009-3: Shift+wheel leaves the active colour untouched."""
    view, _scene, _stack = make_view(64, 64)
    view.set_favourites_model(_four_favourites())
    before_colour = view.active_color()

    view.wheelEvent(_wheel(-120, Shift))

    assert view.active_color() == before_colour


def test_sc_u009_4_the_zoom_floor_is_unchanged_under_shift_wheel(make_view):
    """SC-U009-4: repeated Shift+wheel-down never drops zoom below ZOOM_MIN."""
    view, _scene, _stack = make_view(64, 64)
    view.set_zoom(ZOOM_MIN * 2)

    for _ in range(40):
        view.wheelEvent(_wheel(-120, Shift))
        assert view.zoom() >= ZOOM_MIN
    assert view.zoom() == pytest.approx(ZOOM_MIN)


def test_sc_u009_5_the_same_gesture_zooms_the_tilemap_canvas(qtbot):
    """SC-U009-5: Shift+wheel-up zooms the tilemap canvas by its own step."""
    canvas = _tilemap(qtbot)
    canvas.set_zoom(4.0)
    start = canvas.transform().m11()

    canvas.wheelEvent(_wheel(120, Shift))

    assert canvas.transform().m11() == pytest.approx(start * (1.0 + SCALE_FACTOR))


# =========================================================================
# REQ-IS-UI-011 -- middle click and middle drag are separate (SC-U011-1..4)
# =========================================================================


def test_sc_u011_1_middle_press_released_under_the_threshold_is_a_click(make_view):
    """SC-U011-1: released BEFORE crossing the threshold, a middle press is
    a click -- the first-favourite action fires and the scroll position is
    unchanged. Travel == CLICK_DRAG_THRESHOLD_PX - 1, read from the
    constant, not a literal."""
    view, _scene, _stack = make_view(512, 512)
    view.set_favourites_model(_four_favourites())
    hbar, vbar = view.horizontalScrollBar(), view.verticalScrollBar()
    before_h, before_v = hbar.value(), vbar.value()

    press(view, 100, 100, MIDDLE)
    move(view, 100 + (CLICK_DRAG_THRESHOLD_PX - 1), 100, MIDDLE)
    release(view, 100 + (CLICK_DRAG_THRESHOLD_PX - 1), 100, MIDDLE)

    assert view.active_color() == C0  # the first-favourite action fired
    assert hbar.value() == before_h
    assert vbar.value() == before_v


def test_sc_u011_2_middle_press_moved_beyond_the_threshold_pans_not_clicks(make_view):
    """SC-U011-2: moved AT/BEYOND the threshold, a middle press pans and the
    first-favourite action does NOT fire. Travel ==
    CLICK_DRAG_THRESHOLD_PX + 1, read from the constant.

    The FIRST move past the threshold only promotes the pending press to a
    pan and re-anchors ``_pan_origin`` there (``Canvas_View.mouseMoveEvent``,
    "re-anchored so the next delta is not a jump") -- it applies no scroll
    delta itself. A SECOND move is needed to observe the scrollbar actually
    change, which is what this test does (probed directly against the
    running handler before writing this assertion).
    """
    view, _scene, _stack = make_view(512, 512)
    view.set_favourites_model(_four_favourites())
    before_colour = view.active_color()
    hbar, vbar = view.horizontalScrollBar(), view.verticalScrollBar()
    before_h, before_v = hbar.value(), vbar.value()

    press(view, 100, 100, MIDDLE)
    move(view, 100 - (CLICK_DRAG_THRESHOLD_PX + 1), 100, MIDDLE)  # crosses -> promotes
    move(
        view, 100 - (CLICK_DRAG_THRESHOLD_PX + 6), 100, MIDDLE
    )  # applies the pan delta
    release(view, 100 - (CLICK_DRAG_THRESHOLD_PX + 6), 100, MIDDLE)

    assert view.active_color() == before_colour  # first-favourite did NOT fire
    assert (hbar.value(), vbar.value()) != (before_h, before_v)


def test_sc_u011_3_the_pan_cursor_feedback_is_unchanged_during_a_middle_drag(make_view):
    """SC-U011-3: the viewport shows the closed-hand cursor once a middle
    press promotes to a pan, and it is restored on release."""
    view, _scene, _stack = make_view(512, 512)
    initial_shape = view.viewport().cursor().shape()

    press(view, 100, 100, MIDDLE)
    move(view, 100 + (CLICK_DRAG_THRESHOLD_PX + 1), 100, MIDDLE)
    assert view.viewport().cursor().shape() == Qt.CursorShape.ClosedHandCursor
    release(view, 100 + (CLICK_DRAG_THRESHOLD_PX + 1), 100, MIDDLE)

    assert view.viewport().cursor().shape() == initial_shape


def test_sc_u011_4_the_click_drag_split_behaves_the_same_on_the_tilemap_canvas(
    qtbot, make_tilemap_setup
):
    """SC-U011-4: the same click/drag split holds on the tilemap canvas --
    both sides of the boundary, not only the drag side the Gherkin spells out."""
    canvas = _tilemap(qtbot)
    canvas.set_favourites_model(_four_favourites())
    # A bare canvas has no scrollable range at all (probed directly while
    # writing this test); a bound tilemap + one stamp gives the scene real
    # extent to pan across, exactly like
    # ``test_tilemap_canvas_interaction.py``'s own middle-drag pan test.
    tileset, tilemap = make_tilemap_setup()
    from PySide6.QtGui import QUndoStack

    undo_stack = QUndoStack()
    canvas.set_context(tilemap, undo_stack, None)
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)
    canvas._apply_stamp(60, 60)
    hbar, vbar = canvas.horizontalScrollBar(), canvas.verticalScrollBar()

    # Side 1: under the threshold -> click, first favourite fires, no pan.
    with qtbot.waitSignal(canvas.colorPicked, timeout=1000) as blocker:
        _tm_press(canvas, 100, 100)
        _tm_move(canvas, 100 + (CLICK_DRAG_THRESHOLD_PX - 1), 100)
        _tm_release(canvas, 100 + (CLICK_DRAG_THRESHOLD_PX - 1), 100)
    assert blocker.args[0] == C0

    # Side 2: at/over the threshold -> pan; scroll position changes. The
    # first move past the threshold only promotes+re-anchors (see
    # SC-U011-2's docstring); a second move applies the actual pan delta.
    # Moving toward DECREASING x (probed directly while writing this test):
    # the scrollbar starts at its minimum (0), so a move that would push it
    # further negative clamps back to 0 and looks like "nothing happened".
    before_h, before_v = hbar.value(), vbar.value()
    _tm_press(canvas, 200, 100)
    _tm_move(canvas, 200 - (CLICK_DRAG_THRESHOLD_PX + 1), 100)
    _tm_move(canvas, 200 - (CLICK_DRAG_THRESHOLD_PX + 6), 100)
    _tm_release(canvas, 200 - (CLICK_DRAG_THRESHOLD_PX + 6), 100)
    assert (hbar.value(), vbar.value()) != (before_h, before_v)


# =========================================================================
# REQ-IS-UI-012 -- middle click picks the first favourite (SC-U012-1..4)
# =========================================================================


def test_sc_u012_1_unmodified_middle_click_sets_the_first_favourite(make_view):
    """SC-U012-1: an unmodified middle click sets the first favourite and
    places the cursor on entry 0."""
    view, _scene, _stack = make_view(64, 64)
    favs = _four_favourites()
    favs.advance()
    favs.advance()  # cursor on entry 2
    view.set_favourites_model(favs)

    press(view, 10, 10, MIDDLE)
    release(view, 10, 10, MIDDLE)

    assert view.active_color() == C0
    assert favs.cursor_index() == 0


def test_sc_u012_2_the_next_wheel_notch_continues_from_the_first_entry(make_view):
    """SC-U012-2: after a middle-click, the next plain wheel-down continues
    from entry 0 (i.e. lands on entry 1)."""
    view, _scene, _stack = make_view(64, 64)
    favs = _four_favourites()
    favs.advance()
    favs.advance()
    view.set_favourites_model(favs)
    press(view, 10, 10, MIDDLE)
    release(view, 10, 10, MIDDLE)

    view.wheelEvent(_wheel(-120))

    assert view.active_color() == C1


def test_sc_u012_3_empty_favourites_list_is_a_silent_no_op(make_view):
    """SC-U012-3: an empty Favourites list makes a middle click a silent no-op."""
    view, _scene, _stack = make_view(64, 64)
    view.set_favourites_model(Favourites())
    before_colour = view.active_color()

    press(view, 10, 10, MIDDLE)
    release(view, 10, 10, MIDDLE)  # must not raise

    assert view.active_color() == before_colour


def test_sc_u012_4_it_raises_the_colour_feedback_square(qtbot):
    """SC-U012-4: the middle-click colour change raises the colour feedback
    square, through the real, SHOWN ``Main_Window`` wiring (see SC-U008-6's
    docstring for why ``create_app``/``_settle`` is needed here)."""
    from pixelart_creator.ui.app import create_app

    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._favourites.add(C0)
    win._favourites.add(C1)
    record = win.active_tab()
    assert record is not None and record.feedback_overlay is not None
    assert record.feedback_overlay.isVisible() is False

    press(record.view, 10, 10, MIDDLE)
    release(record.view, 10, 10, MIDDLE)
    _settle(app)

    assert win._active_color == C0
    assert record.feedback_overlay.isVisible() is True


# =========================================================================
# REQ-IS-UI-015 -- Shift+left-drag pans, except under a selection tool
# (SC-U015-1..5)
# =========================================================================


def test_sc_u015_1_shift_left_drag_pans_while_a_drawing_tool_is_active(make_view):
    """SC-U015-1: with pencil active, Shift+left-drag pans; no pixel changes."""
    view, scene, stack = make_view(64, 64)
    view.set_tool(PencilTool())
    before = scene.active_buffer().copy()

    _drag_mod(view, 5, 5, 15, 15, Shift)

    assert scene.active_buffer() == before
    assert stack.count() == 0


def _paint_two_disjoint_blocks(scene) -> None:
    """Paint two same-colour, non-touching 3x3 opaque blocks on the active
    buffer: block A at (1,1)-(3,3), block B at (8,8)-(10,10), separated by a
    transparent gap. Geometric tools (rect/lasso) do not care about buffer
    content, but ``MagicWandTool`` selects by colour-CONTIGUITY -- with an
    all-transparent buffer every point belongs to the same single blob, which
    would make an add/subtract test pass trivially without ever exercising
    two distinct regions. The gap keeps the two blocks out of wand contiguity
    with each other despite sharing a colour."""
    buf = scene.active_buffer()
    for x in range(1, 4):
        for y in range(1, 4):
            buf.set_pixel(x, y, (200, 30, 30, 255))
    for x in range(8, 11):
        for y in range(8, 11):
            buf.set_pixel(x, y, (200, 30, 30, 255))


@pytest.mark.parametrize("tool_cls", [RectSelectTool, LassoTool, MagicWandTool])
def test_sc_u015_2_shift_left_drag_adds_to_selection_under_every_selection_tool(
    make_view, tool_cls
):
    """SC-U015-2: with a selection tool active, Shift+left-drag still ADDS to
    the selection (never pans) -- the Gherkin's own Examples table
    (select_rect / select_lasso / select_wand)."""
    view, scene, _stack = make_view(16, 16)
    _paint_two_disjoint_blocks(scene)
    view.set_tool(tool_cls())
    _drag_mod(view, 1, 1, 3, 3, NoMod)
    _drag_mod(view, 8, 8, 10, 10, Shift)

    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # first region kept
    assert mask.is_selected(9, 9)  # second region added by the Shift-drag


@pytest.mark.parametrize("tool_cls", [RectSelectTool, LassoTool, MagicWandTool])
def test_sc_u015_3_alt_drag_still_subtracts_under_every_selection_tool(
    make_view, tool_cls
):
    """SC-U015-3: Alt+left-drag still subtracts, under every selection tool.

    Select block A, ADD block B (Shift), then ALT-drag over block B again to
    subtract it back out -- leaving only block A. Unlike a plain
    press-then-shrink-a-sub-box shape (which only ``select_rect``/
    ``select_lasso`` can express geometrically), this shape is meaningful for
    ``MagicWandTool`` too: its selection is a whole colour-contiguous blob
    per click, so a sub-box subtraction never applies to it -- only
    subtracting a WHOLE, previously-added blob does.
    """
    view, scene, _stack = make_view(16, 16)
    _paint_two_disjoint_blocks(scene)
    view.set_tool(tool_cls())
    _drag_mod(view, 1, 1, 3, 3, NoMod)
    _drag_mod(view, 8, 8, 10, 10, Shift)
    _drag_mod(view, 8, 8, 10, 10, Alt)

    mask = view.active_selection()
    assert mask is not None
    assert mask.is_selected(2, 2)  # block A kept
    assert not mask.is_selected(9, 9)  # block B subtracted back out


def test_sc_u015_4_unmodified_left_drag_still_paints(make_view):
    """SC-U015-4: an unmodified left-drag with the pencil active still paints."""
    view, scene, stack = make_view(64, 64)
    view.set_tool(PencilTool())
    hbar, vbar = view.horizontalScrollBar(), view.verticalScrollBar()
    before_h, before_v = hbar.value(), vbar.value()

    press(view, 5, 5, LEFT)
    release(view, 5, 5, LEFT)

    buf = scene.active_buffer()
    assert buf.get_pixel(5, 5) == view.active_color()
    assert stack.count() == 1
    assert (hbar.value(), vbar.value()) == (before_h, before_v)


def test_sc_u015_5_shift_left_drag_pans_on_the_tilemap_canvas(
    qtbot, make_tilemap_setup
):
    """SC-U015-5: Shift+left-drag pans the tilemap canvas (no selection tools
    there, so it always pans); no tile is stamped."""
    from PySide6.QtGui import QUndoStack

    tileset, tilemap = make_tilemap_setup()
    undo_stack = QUndoStack()
    canvas = _tilemap(qtbot)
    canvas.set_context(tilemap, undo_stack, None)
    canvas.set_active_layer(0)
    canvas.set_brush_gid(tileset.first_gid)
    canvas._apply_stamp(60, 60)  # grow the scene so scrollbars have range
    before = undo_stack.count()
    hbar, vbar = canvas.horizontalScrollBar(), canvas.verticalScrollBar()
    before_h, before_v = hbar.value(), vbar.value()

    _tm_press(canvas, 100, 100, button=LEFT, modifiers=Shift)
    _tm_move(canvas, 60, 60, button=LEFT, modifiers=Shift)
    _tm_release(canvas, 60, 60, button=LEFT, modifiers=Shift)

    assert (hbar.value(), vbar.value()) != (before_h, before_v)
    assert undo_stack.count() == before  # the drag stamped nothing
