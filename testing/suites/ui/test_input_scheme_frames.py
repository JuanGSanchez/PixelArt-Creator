"""Acceptance: the four Ctrl frame gestures + the content-fit action.

One test per acceptance criterion of `REQ-IS-UI-010` (Ctrl+wheel travels
frames), `-013` (Shift+middle-click frames the painted pixels), `-014`
(Ctrl+middle-click goes to frame 1), `-016` (Ctrl+left-click adds a frame;
Ctrl+left-drag still copies), `-017` (Ctrl+right-click removes a frame, on
the timeline only) and `-018` (the content-fit view action) --
the input-scheme spec SS9.3/9.4, scenarios
``SC-U010-1..4``, ``SC-U013-1..3``, ``SC-U014-1..3``, ``SC-U016-1..6``,
``SC-U017-1..6``, ``SC-U018-1..5`` -- plus the regression scenarios this
task's own edited handlers (``canvas_view.py``, ``main_window.py``,
``timeline_grid_view.py``) are named against in this task's "Done
when" clause: ``SC-R-04``, ``SC-R-05``, ``SC-R-10``, ``SC-R-11``, ``SC-R-13``,
``SC-R-14``.

Both light and dark theme run automatically via ``conftest.py``'s autouse
``theme`` fixture. Headless (``QT_QPA_PLATFORM=offscreen``), forced by the
suite's own ``pytest_configure``.

**Deliberately NOT covered here, and why (recorded, not silently skipped):**

- SC-U016-5's "press Ctrl+left ... while a floating move is live" sub-case is
  covered only INDIRECTLY, through the wheel (this file's
  ``test_ctrl_wheel_is_suppressed_while_a_floating_move_is_live``) and
  middle-click (``test_ctrl_middle_click_is_suppressed_while_a_floating_
  move_is_live``) siblings of the same guard clause
  (``not self._floating_controller.is_active()``). A literal second LEFT
  press while a float from an EARLIER press is still active (never released)
  can only be produced by calling ``mousePressEvent`` twice in a row without
  an intervening release -- something a real pointer sequence cannot do, but
  a direct-handler test can. Probed directly while writing this module:
  ``SelectionTool.on_press``/``FloatingMoveController.begin`` have no
  documented re-entrancy contract for that shape, and `begin()` will happily
  overwrite ``self._floating`` if called while already active -- so a test
  asserting "the floating move is still live and unaltered" for that literal
  second-press shape would be asserting undocumented behaviour outside this
  task's own diff, not proving REQ-IS-UI-016's guard. The guard clause ITSELF
  (`is_active()` gating the Ctrl-left click/drag defer) is exercised cleanly
  by the wheel/middle-click siblings instead, which touch no tool logic at
  all. **could not verify (the click-specific sub-case) -- undocumented
  SelectionTool re-entrancy, outside this task's diff** -- counts as NOT
  covered, not presumed passing.
- SC-R-05 (Ctrl-drag still copies a cel in the timeline grid) and SC-R-15
  (tilemap H/V/R stamp keys) touch code this task's diff never modified
  (``timeline_grid_view.py``'s LEFT-drag ``_finish_drag`` reads its OWN live
  ``event.modifiers()``; ``tilemap_canvas.py`` is unchanged by this task's
  diff entirely -- confirmed via ``git diff --stat``). SC-R-05 is still
  pinned below per this task's explicit "Done when" clause (same view
  class this task edited); SC-R-15 is left to REQ-IS-UI-028's own dedicated
  regression suite (``test_input_scheme_regression.py``,
  ``testing/suites/ui``), which is that requirement's one canonical home
  per the traceability matrix.

**RULED BEHAVIOUR CHANGE (D-22), superseding the MEASURED DEFECT this module
used to report:** the original ``SC-U017-3``/``SC-U017-4`` pair was written
against literal spec text describing a Yes/No confirmation on the document's
last remaining frame -- and a prior run of this suite MEASURED that pairing
impossible: ``Document._ensure_frame_removable`` refuses to leave the
document with zero frames UNCONDITIONALLY (``pixelart_creator/logic/
document.py``), so an accepted confirmation could never proceed and Yes/No
produced the identical no-op. Shown that conflict, the user ruled (D-22): on
the last remaining frame, drop the dialog entirely and show a transient
status-bar explanation instead -- the gesture stays inert, but the user
learns why. ``Timeline_Grid_View._remove_frame_at`` now emits
``lastFrameRemovalRefused`` instead of prompting, and ``Main_Window``
surfaces it via ``_notify_last_frame_removal_refused``. Both tests below are
rewritten to that ruled behaviour; the domain invariant itself is
deliberately NOT relaxed, and every other frame is unaffected -- confirmed by
leaving ``SC-U017-1``/``SC-U017-2`` (multi-frame removal + undo, direct, no
confirmation ever asked there) untouched and green.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QContextMenuEvent,
    QMouseEvent,
    QUndoStack,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QMessageBox

from pixelart_creator.logic.constants import (
    CLICK_DRAG_THRESHOLD_PX,
    UI_NOTICE_DURATION_MS,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.favourites import Favourites
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.selection import rect_mask
from pixelart_creator.logic.track_table import EMPTY_CELL, track_table
from pixelart_creator.ui.canvas_scene import CanvasScene
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import canvas_roles
from pixelart_creator.ui.timeline_grid_view import Timeline_Grid_View
from pixelart_creator.ui.tools import PencilTool, RectSelectTool
from testing.suites.ui._ui_helpers import (
    LEFT,
    MIDDLE,
    RIGHT,
    drag_path,
    prepare_for_click,
    viewport_point_for_pixel,
)

NoMod = Qt.KeyboardModifier.NoModifier
CTRL = Qt.KeyboardModifier.ControlModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier

STARTER = [
    (0, 0, 0, 255),
    (255, 255, 255, 255),
    (230, 30, 30, 255),
]
RED = (230, 30, 30, 255)
GREEN = (30, 190, 60, 255)
BLUE = (40, 90, 220, 255)


# =========================================================================
# shared helpers
# =========================================================================


def _settle(app, iterations: int = 8) -> None:
    """Flush pending layout/timer-driven passes a bounded number of times
    (matches ``test_colour_pick_semantics.py``'s own idiom)."""
    for _ in range(iterations):
        app.processEvents()


def _wheel(delta_y: int, modifiers=NoMod) -> QWheelEvent:
    """A real ``QWheelEvent`` notch. Negative ``delta_y`` == wheel DOWN;
    positive == wheel UP -- matches ``Canvas_View._frame_step_wheel``'s own
    ``angleDelta().y() < 0`` test (mirrors ``test_input_scheme_pointer.py``'s
    identical helper)."""
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
    """A synthetic ``QMouseEvent`` at document pixel ``(x, y)`` carrying
    ``modifiers``, routed through the view's own CURRENT mapping (mirrors
    ``test_input_scheme_pointer.py``/``test_floating_selection.py``)."""
    point = viewport_point_for_pixel(view, x, y)
    pt = QPointF(point.x(), point.y())
    return QMouseEvent(etype, pt, pt, button, buttons, modifiers)


def press_mod(view, x, y, button, modifiers=NoMod) -> None:
    view.mousePressEvent(
        _mod_evt(view, QEvent.Type.MouseButtonPress, x, y, button, button, modifiers)
    )


def move_mod(view, x, y, button, modifiers=NoMod) -> None:
    view.mouseMoveEvent(
        _mod_evt(
            view,
            QEvent.Type.MouseMove,
            x,
            y,
            Qt.MouseButton.NoButton,
            button,
            modifiers,
        )
    )


def release_mod(view, x, y, button, modifiers=NoMod) -> None:
    view.mouseReleaseEvent(
        _mod_evt(
            view,
            QEvent.Type.MouseButtonRelease,
            x,
            y,
            button,
            Qt.MouseButton.NoButton,
            modifiers,
        )
    )


def _send_context_menu(widget, pos: QPoint, reason=None) -> None:
    """Deliver a real ``QContextMenuEvent`` via ``sendEvent`` -- Qt's own
    public event-delivery mechanism (matches
    ``test_timeline_grid_gestures.py``'s ``_request_context_menu``, needed
    because the offscreen platform does not synthesize one from a real
    click/key on ``Timeline_Grid_View``)."""
    if reason is None:
        reason = QContextMenuEvent.Reason.Mouse
    QApplication.sendEvent(widget, QContextMenuEvent(reason, pos))


@pytest.fixture
def build_view(qtbot, theme):
    """Factory: ``(view, scene, stack, document)``, a click-ready
    :class:`Canvas_View` bound to a fresh, theme-correct multi-frame
    document -- ``view.set_recording(None, document)`` binds
    ``_recording_document`` (bound the same way ``_add_document_tab`` does:
    the SAME ``Document`` instance the scene itself holds), which
    ``_frame_step_wheel``/``_goto_first_frame``/``fit_content`` all read.
    Resized to a large, known viewport (600x500) BEFORE
    ``prepare_for_click`` pins zoom to 1.0, so every geometry assertion below
    reads its own expectation from ``view.viewport().rect()`` rather than
    guessing the platform's default widget size.
    """

    def _build(frames: int = 3, width: int = 64, height: int = 64):
        document = Document(width, height, palette=Palette(STARTER))
        for _ in range(frames - 1):
            document.add_frame()
        scene = CanvasScene(document)
        scene.set_background_roles(*canvas_roles(theme))
        stack = QUndoStack()
        view = Canvas_View(scene, stack)
        qtbot.addWidget(view)
        view.resize(600, 500)
        QApplication.processEvents()
        prepare_for_click(view)
        view.set_tool(PencilTool())
        view.set_active_color(BLUE)
        view.set_recording(None, document)
        return view, scene, stack, document

    return _build


def _n_frame_doc(n: int = 4, width: int = 64, height: int = 64) -> Document:
    doc = Document(width, height, palette=Palette(STARTER))
    for _ in range(n - 1):
        doc.add_frame()
    return doc


def _make_panel(qtbot, doc: Document):
    """A shown, exposed :class:`Timeline_Panel` bound to ``doc`` -- the
    lightest real harness for `REQ-IS-UI-017`, which lives entirely inside
    `Timeline_Grid_View` (mirrors ``test_timeline_grid_gestures.py``'s own
    ``_make_panel``)."""
    from pixelart_creator.ui.timeline_panel import Timeline_Panel

    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(700, 220)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    qtbot.waitExposed(panel)
    panel._grid_toggle_action.setChecked(True)
    return panel, panel._grid, stack


def _cell_center(grid, row: int, col: int) -> QPoint:
    return grid.visualRect(grid.model().index(row, col)).center()


class _FakeMenu(QObject):
    """A no-exec ``QMenu`` stand-in so the modal ``exec()`` never blocks
    headless (the established pattern -- ``test_canvas_view.py``/
    ``test_timeline_grid_gestures.py``'s own ``_FakeMenu``). Subclasses
    ``QObject`` because ``timeline_grid_view.py`` constructs a real
    ``QAction(text, menu)`` with this instance as its parent."""

    instances: list = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._actions: list = []
        _FakeMenu.instances.append(self)

    def addAction(self, action):  # noqa: N802
        self._actions.append(action)
        return action

    def actions(self):
        return list(self._actions)

    def exec(self, *args, **kwargs):  # noqa: A003
        return None  # never enters a modal loop


def _empty_cell_doc():
    """A two-track document: "Outline" occupied at frame 0, empty at frame 1
    (matches ``test_timeline_grid_gestures.py``'s own fixture shape)."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    outline = doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    return doc, outline.layer_id


# =========================================================================
# REQ-IS-UI-010 -- Ctrl+wheel travels frames (SC-U010-1..4)
# =========================================================================


def test_sc_u010_1_ctrl_wheel_down_advances_one_frame(build_view):
    """SC-U010-1: Ctrl+wheel-down advances the active frame by one; zoom is
    unchanged. (0-based: "frame 2 current" -> index 1; "frame 3" -> index 2 --
    the timeline-follows-along clause is proven at the Main_Window level in
    ``test_sc_u010_1_integration_...`` below.)"""
    view, scene, _stack, _doc = build_view(frames=5)
    scene.set_frame_index(1)
    before_zoom = view.zoom()
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    view.wheelEvent(_wheel(-120, CTRL))

    assert fired == [2]
    assert view.zoom() == pytest.approx(before_zoom)


def test_sc_u010_2_ctrl_wheel_up_retreats_one_frame(build_view):
    """SC-U010-2: Ctrl+wheel-up retreats the active frame by one."""
    view, scene, _stack, _doc = build_view(frames=5)
    scene.set_frame_index(2)
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    view.wheelEvent(_wheel(120, CTRL))

    assert fired == [1]


def test_sc_u010_3_a_single_frame_document_is_a_silent_no_op(build_view):
    """SC-U010-3: on a single-frame document, Ctrl+wheel-down is a silent
    no-op -- frame 1 is still current, and no error is raised."""
    view, scene, _stack, _doc = build_view(frames=1)
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    view.wheelEvent(_wheel(-120, CTRL))  # must not raise

    assert fired == []
    assert scene.frame_index == 0


def test_sc_u010_4_ctrl_wheel_does_not_change_colour_or_zoom(build_view):
    """SC-U010-4: Ctrl+wheel changes neither the active colour nor the zoom."""
    view, _scene, _stack, _doc = build_view(frames=5)
    view.set_favourites_model(
        Favourites(
            [
                (10, 20, 30, 255),
                (40, 50, 60, 255),
                (70, 80, 90, 255),
                (100, 110, 120, 255),
            ]
        )
    )
    before_colour = view.active_color()
    before_zoom = view.zoom()

    view.wheelEvent(_wheel(-120, CTRL))

    assert view.active_color() == before_colour
    assert view.zoom() == pytest.approx(before_zoom)


def test_ctrl_wheel_is_suppressed_while_a_floating_move_is_live(build_view):
    """Not a numbered SC id: REQ-IS-UI-016's suppression guard text reads
    "every Ctrl frame gesture", not only the click one -- pins the wheel
    gesture's OWN copy of the guard clause in ``_frame_step_wheel``."""
    view, scene, _stack, _doc = build_view(frames=3, width=16, height=16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    controller = view.floating_controller()
    press_mod(view, 3, 3, LEFT)
    move_mod(view, 6, 6, LEFT)
    assert controller.is_active()
    before_index = scene.frame_index
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    view.wheelEvent(_wheel(-120, CTRL))

    assert fired == []
    assert scene.frame_index == before_index
    controller.cancel()  # do not leak an active float


def test_sc_u010_1_integration_timeline_follows_the_canvas_frame_step(qtbot):
    """SC-U010-1 (integration): the timeline, not only the scene, follows a
    Ctrl+wheel frame step, through the real ``Main_Window`` wiring
    (``frameNavigationRequested -> _navigate_to_frame``)."""
    from pixelart_creator.ui.app import create_app

    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._timeline_panel._add_action.trigger()
    win._timeline_panel._add_action.trigger()  # 3 frames total
    win._on_frame_selected(1)  # "frame 2 current"
    record = win.active_tab()
    before_zoom = record.view.zoom()

    record.view.wheelEvent(_wheel(-120, CTRL))
    _settle(app)

    assert record.scene.frame_index == 2
    assert win._timeline_panel.active_index == 2
    assert record.view.zoom() == pytest.approx(before_zoom)


# =========================================================================
# REQ-IS-UI-014 -- Ctrl+middle-click goes to the first frame (SC-U014-1..3)
# =========================================================================


def test_sc_u014_1_the_first_frame_becomes_current(build_view):
    """SC-U014-1: Ctrl+middle-click selects frame 1 through the shipped
    frame-selection path."""
    view, scene, _stack, _doc = build_view(frames=5)
    scene.set_frame_index(3)
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    press_mod(view, 10, 10, MIDDLE, CTRL)
    release_mod(view, 10, 10, MIDDLE, CTRL)

    assert fired == [0]


def test_sc_u014_2_already_on_frame_1_is_a_no_op(build_view):
    """SC-U014-2: already on frame 1, Ctrl+middle-click neither errors nor
    pushes a command -- the undo stack depth is unchanged."""
    view, scene, stack, _doc = build_view(frames=5)
    assert scene.frame_index == 0
    before_depth = stack.count()
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    press_mod(view, 10, 10, MIDDLE, CTRL)
    release_mod(view, 10, 10, MIDDLE, CTRL)

    assert fired == []
    assert scene.frame_index == 0
    assert stack.count() == before_depth


def test_sc_u014_3_no_frame_is_added_or_removed(build_view):
    """SC-U014-3: the gesture changes the current frame, never the frame
    count."""
    view, scene, _stack, doc = build_view(frames=5)
    scene.set_frame_index(2)
    frames_before = len(doc.frames)

    press_mod(view, 10, 10, MIDDLE, CTRL)
    release_mod(view, 10, 10, MIDDLE, CTRL)

    assert len(doc.frames) == frames_before


def test_ctrl_middle_click_is_suppressed_while_a_floating_move_is_live(build_view):
    """Not a numbered SC id: the REQ-IS-UI-016 suppression guard applies to
    the middle-click frame gesture too (``_goto_first_frame``'s own
    ``is_active()`` check)."""
    view, scene, _stack, _doc = build_view(frames=3, width=16, height=16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    controller = view.floating_controller()
    press_mod(view, 3, 3, LEFT)
    move_mod(view, 6, 6, LEFT)
    assert controller.is_active()
    scene.set_frame_index(2)  # not on frame 1, so the gesture WOULD navigate
    fired = []
    view.frameNavigationRequested.connect(fired.append)

    press_mod(view, 20, 1, MIDDLE, CTRL)
    release_mod(view, 20, 1, MIDDLE, CTRL)

    assert fired == []
    assert scene.frame_index == 2
    controller.cancel()  # do not leak an active float


# =========================================================================
# REQ-IS-UI-016 -- Ctrl+left-click adds a frame; Ctrl+left-drag still copies
# (SC-U016-1..6)
# =========================================================================


def test_sc_u016_1_ctrl_left_click_under_threshold_requests_add_frame(build_view):
    """SC-U016-1 (signal level): a Ctrl+left press released under the
    click/drag threshold requests a frame add. ``Canvas_View`` builds no
    domain result of its own (Article I) -- the actual command push, the
    frame-count effect and the undo-stack growth are proven at the
    Main_Window level below (undoability, item 4)."""
    view, _scene, _stack, _doc = build_view(frames=3)
    fired = []
    view.addFrameRequested.connect(lambda: fired.append(True))

    press_mod(view, 10, 10, LEFT, CTRL)
    move_mod(view, 10 + (CLICK_DRAG_THRESHOLD_PX - 1), 10, LEFT, CTRL)
    release_mod(view, 10 + (CLICK_DRAG_THRESHOLD_PX - 1), 10, LEFT, CTRL)

    assert fired == [True]


def test_sc_u016_3_ctrl_left_drag_over_threshold_does_not_request_add_frame(build_view):
    """SC-U016-3: a Ctrl+left press moved PAST the threshold before release
    does not request a frame add -- the document frame count is unchanged."""
    view, _scene, _stack, doc = build_view(frames=3)
    frames_before = len(doc.frames)
    fired = []
    view.addFrameRequested.connect(lambda: fired.append(True))

    press_mod(view, 10, 10, LEFT, CTRL)
    move_mod(view, 10 + (CLICK_DRAG_THRESHOLD_PX + 5), 10, LEFT, CTRL)
    release_mod(view, 10 + (CLICK_DRAG_THRESHOLD_PX + 5), 10, LEFT, CTRL)

    assert fired == []
    assert len(doc.frames) == frames_before


def test_sc_u016_6_an_unmodified_left_click_still_paints(build_view):
    """SC-U016-6: an unmodified left click still paints; the frame count is
    unaffected."""
    view, scene, stack, doc = build_view(frames=3)
    frames_before = len(doc.frames)
    buf = scene.active_buffer()

    press_mod(view, 5, 5, LEFT, NoMod)
    release_mod(view, 5, 5, LEFT, NoMod)

    assert buf.get_pixel(5, 5) == view.active_color()
    assert stack.count() == 1
    assert len(doc.frames) == frames_before


def test_sc_u016_1_and_2_integration_add_frame_then_undo(qtbot):
    """SC-U016-1 + SC-U016-2 (undoability, item 4): through the real
    ``Main_Window`` wiring, a Ctrl+left click adds a frame immediately after
    the active one, pushes exactly ONE undo entry, and ``Ctrl+Z`` (here,
    ``stack.undo()``) restores the prior frame count."""
    from pixelart_creator.ui.app import create_app

    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)
    win._timeline_panel._add_action.trigger()
    win._timeline_panel._add_action.trigger()  # 3 frames, active index 2
    win._on_frame_selected(1)  # "frame 2 current"
    record = win.active_tab()
    prepare_for_click(record.view)
    old_frame_at_2 = record.document.frames[2]
    before = record.stack.count()

    press_mod(record.view, 5, 5, LEFT, CTRL)
    move_mod(record.view, 5 + (CLICK_DRAG_THRESHOLD_PX - 1), 5, LEFT, CTRL)
    release_mod(record.view, 5 + (CLICK_DRAG_THRESHOLD_PX - 1), 5, LEFT, CTRL)
    _settle(app)

    assert len(record.document.frames) == 4
    assert record.document.frames[3] is old_frame_at_2  # pushed down by one
    assert record.document.frames[2] is not old_frame_at_2  # the new frame
    assert record.stack.count() == before + 1  # exactly ONE undo entry

    record.stack.undo()
    _settle(app)

    assert len(record.document.frames) == 3


def test_regression_ctrl_held_at_press_still_starts_and_copies_the_float(build_view):
    """Pins the regression the implementer found and fixed while building
    REQ-IS-UI-016's Ctrl+left click/drag deferral: float-copy
    (REQ-P2-UI-032) has NO distance threshold -- it arms at PRESS, unlike
    every other drag in this feature. A first attempt deferred EVERY
    Ctrl+left press (including one that lands inside a live selection and
    would itself start a float) exactly like the frame-add gesture, which
    swallowed the float-copy press until the deferred click/drag verdict
    resolved on release/move -- breaking REQ-P2-UI-032. The shipped fix
    (``_press_would_float``) skips the defer entirely for a press that would
    float, so THIS press must behave exactly like an unmodified press: the
    float starts on PRESS, with no threshold, and Ctrl is honoured as COPY
    from the very first move."""
    view, scene, _stack, document = build_view(frames=3, width=16, height=16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    buf.set_pixel(3, 3, GREEN)
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    controller = view.floating_controller()
    frames_before = len(document.frames)

    press_mod(view, 3, 3, LEFT, CTRL)  # interior press, Ctrl held from the start

    assert controller.is_active(), (
        "a Ctrl press that would start a float was deferred instead of "
        "starting the float immediately -- the regression this test pins"
    )
    move_mod(view, 8, 8, LEFT, CTRL)
    assert controller.is_active() and controller.is_copy()
    release_mod(view, 8, 8, LEFT, CTRL)

    assert len(document.frames) == frames_before  # no frame was added
    if controller.is_active():
        controller.cancel()  # do not leak an active float


def test_sc_u016_4_ctrl_applied_mid_drag_still_switches_float_to_copy(build_view):
    """SC-U016-4 / SC-R-04: a float already lifted by a PLAIN press (no
    Ctrl) still switches to COPY when Ctrl is applied mid-drag -- re-sampled
    every move (REQ-P2-UI-032), untouched by the new Ctrl click/drag
    deferral because the press itself carried no Ctrl."""
    view, scene, _stack, document = build_view(frames=2, width=16, height=16)
    view.set_tool(RectSelectTool())
    buf = scene.active_buffer()
    buf.set_pixel(2, 2, RED)
    view.set_selection(rect_mask(16, 16, 2, 2, 4, 4))
    controller = view.floating_controller()
    frames_before = len(document.frames)

    press_mod(view, 3, 3, LEFT, NoMod)  # plain press lifts the float
    assert controller.is_active() and not controller.is_copy()

    move_mod(view, 8, 8, LEFT, CTRL)  # Ctrl held mid-drag

    assert controller.is_active() and controller.is_copy()
    release_mod(view, 8, 8, LEFT, CTRL)

    assert len(document.frames) == frames_before


# =========================================================================
# REQ-IS-UI-017 -- Ctrl+right-click removes a frame, timeline only
# (SC-U017-1..6)
# =========================================================================


def test_sc_u017_1_ctrl_right_click_removes_a_frame_on_a_multiframe_document(
    qtbot, monkeypatch
):
    """SC-U017-1 (item 1, branch a) + undoability (item 4): Ctrl+right-click
    on the timeline removes the frame under the cursor via the shipped
    undoable command -- exactly one undo entry."""
    doc = _n_frame_doc(4)
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.ControlModifier),
    )

    pos = _cell_center(grid, 0, 2)
    _send_context_menu(grid.viewport(), pos)

    assert len(doc.frames) == 3
    assert stack.count() == before + 1


def test_sc_u017_2_undo_restores_the_removed_frame_with_its_pixels(qtbot, monkeypatch):
    """SC-U017-2: undo restores the removed frame, with its exact pixel
    content."""
    doc = _n_frame_doc(4)
    doc.frames[2].layers[0].buffer.fill_rect(0, 0, doc.width, doc.height, GREEN)
    panel, grid, stack = _make_panel(qtbot, doc)
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.ControlModifier),
    )
    pos = _cell_center(grid, 0, 2)
    _send_context_menu(grid.viewport(), pos)
    assert len(doc.frames) == 3

    stack.undo()

    assert len(doc.frames) == 4
    assert doc.frames[2].layers[0].buffer.get_pixel(0, 0) == GREEN


def test_sc_u017_3_last_frame_refuses_silently_no_dialog_signal_fires(
    qtbot, monkeypatch
):
    """SC-U017-3, REWRITTEN BY RULING D-22 (item 1, the safeguard on a
    genuinely single-frame document).

    The literal spec text this test used to assert against -- a Yes/No
    confirmation, with a decline branch that removes nothing -- was shown to
    the user alongside a MEASURED finding: ``Document._ensure_frame_removable``
    refuses to leave the document with zero frames UNCONDITIONALLY
    (``pixelart_creator/logic/document.py``), so an ACCEPTED confirmation
    could never proceed either -- Yes and No were the same no-op wearing a
    dialog. The user ruled (D-22): drop the dialog on the last remaining
    frame entirely; explain instead of asking a question whose answer cannot
    change the outcome.

    This test now proves the RULED shape directly, not merely its absence of
    side effects (a "nothing was removed" assertion alone would have passed
    against the OLD broken behaviour too -- that is exactly how the original
    defect hid): no ``QMessageBox`` is ever raised (spied for zero calls, not
    just an unasserted absence), ``Timeline_Grid_View.lastFrameRemovalRefused``
    fires (signal observer connected BEFORE the triggering gesture), and the
    frame count is unchanged. The undo stack is asserted unchanged too -- no
    command was ever built, let alone pushed."""
    doc = _n_frame_doc(1)
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    dialog_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: dialog_calls.append((a, k))),
    )
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.ControlModifier),
    )
    pos = _cell_center(grid, 0, 0)

    with qtbot.waitSignal(grid.lastFrameRemovalRefused, timeout=1000):
        _send_context_menu(grid.viewport(), pos)

    assert dialog_calls == [], (
        "a QMessageBox.question was raised on the last remaining frame -- "
        "D-22 ruled the dialog dropped entirely in favour of a status-bar "
        "explanation"
    )
    assert len(doc.frames) == 1  # nothing removed
    assert stack.count() == before  # no command built, let alone pushed


def test_sc_u017_4_last_frame_explanation_reaches_the_status_bar(qtbot, monkeypatch):
    """SC-U017-4, REWRITTEN BY RULING D-22 (item 1, the explanation the user
    actually sees).

    The literal spec text this test used to assert -- accepting the
    confirmation proceeds through the undoable remove-frame command -- was
    MEASURED impossible in the same session that produced this rewrite (see
    ``test_sc_u017_3`` above and this module's own docstring): the domain
    invariant is deliberately NOT relaxed, so "accepting" can never remove
    the document's last frame. Shown that conflict, the user ruled (D-22)
    that the gesture stays inert and explains itself instead.

    A refusal signal nobody displays is the same defect one layer up, so
    this test does not stop at the signal (``test_sc_u017_3`` already proves
    that): it builds a real ``Main_Window`` -- the object that actually owns
    the status bar and the ``lastFrameRemovalRefused`` connection
    (``Main_Window.__init__``, wired via ``findChild(Timeline_Grid_View)``)
    -- and proves the ``tr()``ed notice actually reaches
    ``statusBar().showMessage`` for ``UI_NOTICE_DURATION_MS``, exactly the
    shape the shipped ``_notify_layer_locked`` sibling notice is proven with
    in ``test_locked_layer_enforcement.py``. A fresh ``Main_Window`` opens one
    Untitled tab whose ``Document`` already starts with exactly one frame
    (``Document.__init__``), so no extra setup is needed to reach the
    single-frame condition."""
    win = Main_Window()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    record = win.active_tab()
    assert record is not None
    assert len(record.document.frames) == 1  # the single-frame starting point

    grid = win._timeline_panel.findChild(Timeline_Grid_View)
    assert grid is not None
    win._timeline_panel._grid_toggle_action.setChecked(True)  # strip is default
    QApplication.processEvents()

    dialog_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: dialog_calls.append((a, k))),
    )
    status_calls = []
    monkeypatch.setattr(
        win.statusBar(),
        "showMessage",
        lambda text, timeout=0: status_calls.append((text, timeout)),
    )
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.ControlModifier),
    )
    pos = _cell_center(grid, 0, 0)

    with qtbot.waitSignal(grid.lastFrameRemovalRefused, timeout=1000):
        _send_context_menu(grid.viewport(), pos)

    assert dialog_calls == []  # no dialog either, on this surface
    assert status_calls, "statusBar().showMessage was never called"
    text, timeout = status_calls[-1]
    assert text == win.tr(
        "This is the last remaining frame; a document must keep at least one."
    )
    assert timeout == UI_NOTICE_DURATION_MS
    assert len(record.document.frames) == 1  # still nothing removed


@pytest.mark.parametrize(
    "modifiers", [NoMod, CTRL], ids=["no_ctrl_SC-R-10", "ctrl_SC-U017-5"]
)
def test_right_click_on_the_canvas_opens_the_hub_and_removes_nothing(
    build_view, modifiers
):
    """SC-R-10 (no_ctrl) + SC-U017-5 (ctrl) -- item 2, the asymmetry's CANVAS
    half: on ``Canvas_View``, right-click -- modified by Ctrl or not --
    behaves identically. ``mousePressEvent``'s RightButton branch is
    UNCONDITIONAL (reads no modifier at all), so this is the same code path
    whether or not Ctrl is held; REQ-IS-UI-017 confines removal to the
    timeline (SC-U017-1..4 above)."""
    view, _scene, _stack, doc = build_view(frames=4)
    calls = []
    view.set_menu_hook(lambda x, y: calls.append((x, y)))
    frames_before = len(doc.frames)

    press_mod(view, 9, 9, RIGHT, modifiers)

    assert calls == [(9, 9)]
    assert len(doc.frames) == frames_before


def test_sc_u017_6_ctrl_right_click_on_the_tilemap_canvas_removes_nothing(qtbot):
    """SC-U017-6 -- item 2, the asymmetry's TILEMAP half: Ctrl+right-click
    on the tilemap canvas is a no-op there. Confirmed against this task's
    own diff (``git diff --stat``) that ``tilemap_canvas.py`` is UNCHANGED:
    ``Tilemap_Canvas.mousePressEvent`` has no ``RightButton`` branch at all,
    so it falls straight to the Qt base implementation. Proven against an
    independent multi-frame animation ``Document`` to make the "removes
    nothing" claim concrete, even though nothing connects the two objects at
    all -- which is itself the point: the surfaces are structurally
    independent."""
    from pixelart_creator.ui.tilemap_canvas import Tilemap_Canvas

    canvas = Tilemap_Canvas()
    qtbot.addWidget(canvas)
    canvas.resize(300, 300)
    QApplication.processEvents()
    doc = _n_frame_doc(4)
    frames_before = len(doc.frames)

    evt = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(50, 50), RIGHT, RIGHT, CTRL)
    canvas.mousePressEvent(evt)  # must not raise

    assert len(doc.frames) == frames_before


def test_sc_r14_plain_right_click_on_an_empty_cell_still_offers_create_cel_here(
    qtbot, monkeypatch
):
    """SC-R-14 (this task's own edited handler, the code path adjacent to
    this task's change): the new Ctrl-branch this task added at the TOP of
    ``_on_context_menu_requested`` (before the empty-cell affordance) must
    not disturb an UNMODIFIED right-click. ``QApplication.keyboardModifiers()``
    reports no Ctrl here, so the new branch's ``if`` is false and control
    falls through unchanged to the pre-existing "Create Cel Here" affordance
    (REQ-P5-UI-031). (Header-drag reorder and occupied/empty-cell drag --
    SC-R-14's other three sub-behaviours -- touch code this task's diff
    never modified and are already covered by
    ``test_timeline_grid_gestures.py``; this pin targets specifically the
    code path this task changed.)"""
    doc, _outline_id = _empty_cell_doc()
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    _FakeMenu.instances.clear()
    monkeypatch.setattr("pixelart_creator.ui.timeline_grid_view.QMenu", _FakeMenu)
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.NoModifier),
    )

    pos = _cell_center(grid, outline_row, 1)
    _send_context_menu(grid.viewport(), pos)

    assert (
        _FakeMenu.instances
    ), "Create Cel Here was not offered for a plain right-click"
    actions = _FakeMenu.instances[-1].actions()
    assert len(actions) == 1
    actions[0].trigger()

    assert stack.count() == before + 1


def test_sc_r05_ctrl_drag_still_copies_a_cel_in_the_timeline_grid(qtbot):
    """SC-R-05 (this task's own "Done when" clause -- asserted on the
    same modifier, same view class this task edited): an occupied cel
    Ctrl-dragged onto an empty cell still COPIES (``_finish_drag``'s own,
    entirely separate ``event.modifiers()`` check on a LEFT-button drag --
    untouched by the new Ctrl+RIGHT-click removal branch, which lives in
    ``_on_context_menu_requested`` and reads the static
    ``QApplication.keyboardModifiers()`` instead)."""
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()
    panel, grid, stack = _make_panel(qtbot, doc)
    before = stack.count()
    table_before = track_table(doc, active_frame=0)
    outline_row = next(
        i for i, r in enumerate(table_before.rows) if r.label == "Outline"
    )
    assert table_before.rows[outline_row].cells[1] is EMPTY_CELL

    start = _cell_center(grid, outline_row, 0)
    end = _cell_center(grid, outline_row, 1)
    qtbot.mousePress(grid.viewport(), Qt.MouseButton.LeftButton, CTRL, pos=start)
    for i in range(1, 6):
        pos = QPoint(
            start.x() + (end.x() - start.x()) * i // 5,
            start.y() + (end.y() - start.y()) * i // 5,
        )
        qtbot.mouseMove(grid.viewport(), pos=pos)
    qtbot.mouseRelease(grid.viewport(), Qt.MouseButton.LeftButton, CTRL, pos=end)

    assert stack.count() == before + 1
    table_after = track_table(doc, active_frame=0)
    assert table_after.rows[outline_row].cells[0] is not EMPTY_CELL  # source retained
    assert (
        table_after.rows[outline_row].cells[1] is not EMPTY_CELL
    )  # destination filled


def test_sc_r11_the_menu_key_still_opens_the_hub(build_view):
    """SC-R-11: the keyboard-reachable Menu-key/Shift+F10 hub-open path
    (``Canvas_View.contextMenuEvent``, ``reason=Keyboard``) is untouched by
    this task -- it reads no Ctrl state at all, and lives entirely below the
    ``RightButton`` press branch this task left unconditional."""
    from PySide6.QtGui import QContextMenuEvent as _CME

    view, _scene, _stack, _doc = build_view(frames=2)
    calls = []
    view.set_menu_hook(lambda x, y: calls.append((x, y)))
    center = view.viewport().rect().center()

    view.contextMenuEvent(_CME(_CME.Reason.Keyboard, center))

    assert calls, "the Menu-key path did not open the colour hub"


def test_sc_r13_unmodified_left_press_on_a_guide_still_drags_it(build_view):
    """SC-R-13: a plain (non-Ctrl) left-press on an existing guide still
    starts the guide-drag through ``_hit_test_guide`` -- unaffected by the
    new Ctrl+left click/drag deferral this task added directly above it in
    ``Canvas_View.mousePressEvent``, whose branch only matches
    ``event.modifiers() == Qt.KeyboardModifier.ControlModifier``, so an
    unmodified press falls straight through to the untouched guide check."""
    from pixelart_creator.logic.guides import GuideOrientation
    from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay

    view, scene, _stack, _doc = build_view(frames=2, width=64, height=64)
    guides = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, 64, 64))
    guides.set_enabled(True)
    view.set_guides_overlay(guides)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)

    drag_path(view, [(10, 5), (25, 5)])

    remaining = guides.overlay_item().guides()
    assert len(remaining) == 1
    assert remaining[0].position == 25.0


# =========================================================================
# REQ-IS-UI-013 -- Shift+middle-click frames the painted pixels
# (SC-U013-1..3)
# =========================================================================


def test_sc_u013_1_shift_middle_click_frames_the_painted_pixels(build_view):
    """SC-U013-1: Shift+middle-click zooms and centres so the painted-pixel
    bounding box fits the viewport, within the shipped zoom floor/ceiling."""
    view, scene, _stack, _doc = build_view(frames=1, width=256, height=256)
    scene.active_buffer().fill_rect(100, 100, 41, 41, RED)
    vp = view.viewport().rect()
    expected_zoom = view._clamp_zoom(min(vp.width() / 41.0, vp.height() / 41.0))

    press_mod(view, 10, 10, MIDDLE, SHIFT)
    release_mod(view, 10, 10, MIDDLE, SHIFT)

    assert view.zoom() == pytest.approx(expected_zoom)
    centre = view.mapToScene(vp.center())
    tol = max(1.0, 2.0 / max(expected_zoom, 0.01))
    assert centre.x() == pytest.approx(120.5, abs=tol)
    assert centre.y() == pytest.approx(120.5, abs=tol)


def test_sc_u013_2_empty_canvas_falls_back_to_fit_on_shift_middle_click(build_view):
    """SC-U013-2: on a canvas with no non-transparent pixel, Shift+middle-
    click falls back to the shipped ``fit()`` behaviour and does not error."""
    view, _scene, _stack, _doc = build_view(frames=1, width=64, height=64)
    view.fit()
    expected_zoom = view.zoom()
    view.set_zoom(5.0)

    press_mod(view, 10, 10, MIDDLE, SHIFT)
    release_mod(view, 10, 10, MIDDLE, SHIFT)  # must not raise

    assert view.zoom() == pytest.approx(expected_zoom)


def test_sc_u013_3_shift_middle_drag_still_pans_and_does_not_centre(build_view):
    """SC-U013-3: Shift+middle-DRAG (over the click/drag threshold) still
    pans -- it does not invoke the content-fit centring."""
    view, scene, _stack, _doc = build_view(frames=1, width=256, height=256)
    scene.active_buffer().fill_rect(100, 100, 41, 41, RED)
    before_zoom = view.zoom()
    hbar, vbar = view.horizontalScrollBar(), view.verticalScrollBar()
    before_h, before_v = hbar.value(), vbar.value()

    press_mod(view, 100, 100, MIDDLE, SHIFT)
    move_mod(view, 100 - (CLICK_DRAG_THRESHOLD_PX + 1), 100, MIDDLE, SHIFT)
    move_mod(view, 100 - (CLICK_DRAG_THRESHOLD_PX + 6), 100, MIDDLE, SHIFT)
    release_mod(view, 100 - (CLICK_DRAG_THRESHOLD_PX + 6), 100, MIDDLE, SHIFT)

    assert view.zoom() == pytest.approx(before_zoom)  # not centred/zoomed
    assert (hbar.value(), vbar.value()) != (before_h, before_v)


# =========================================================================
# REQ-IS-UI-018 -- the content-fit view action (SC-U018-1..5)
# =========================================================================


def test_sc_u018_1_fit_content_frames_the_painted_pixels(build_view):
    """SC-U018-1: the action zooms and centres the viewport on the
    non-transparent-pixel bounding box, clamped by the shipped zoom
    floor/ceiling."""
    view, scene, _stack, _doc = build_view(frames=1, width=256, height=256)
    scene.active_buffer().fill_rect(100, 100, 41, 41, RED)
    vp = view.viewport().rect()
    expected_zoom = view._clamp_zoom(min(vp.width() / 41.0, vp.height() / 41.0))

    view.fit_content()

    assert view.zoom() == pytest.approx(expected_zoom)
    centre = view.mapToScene(vp.center())
    tol = max(1.0, 2.0 / max(expected_zoom, 0.01))
    assert centre.x() == pytest.approx(120.5, abs=tol)
    assert centre.y() == pytest.approx(120.5, abs=tol)


def test_sc_u018_5_fit_content_on_an_empty_canvas_falls_back_to_fit(build_view):
    """SC-U018-5: an empty canvas falls back to ``fit()``."""
    view, _scene, _stack, _doc = build_view(frames=1, width=64, height=64)
    view.fit()
    expected_zoom = view.zoom()
    view.set_zoom(5.0)

    view.fit_content()

    assert view.zoom() == pytest.approx(expected_zoom)


def test_fit_content_with_no_bound_document_also_falls_back_to_fit(build_view):
    """Not a numbered SC id: ``fit_content`` also falls back when NO
    document is bound at all (``self._recording_document is None``) --
    distinct from the empty-canvas SC-U018-5/SC-U013-2 case, and required by
    the task text ("must fall back to the existing fit rather than doing
    nothing or throwing")."""
    view, _scene, _stack, _doc = build_view(frames=1, width=64, height=64)
    view.set_recording(None, None)
    view.fit()
    expected_zoom = view.zoom()
    view.set_zoom(5.0)

    view.fit_content()  # must not raise

    assert view.zoom() == pytest.approx(expected_zoom)


def test_sc_u018_2_and_4_view_menu_has_both_fit_actions_translated_and_distinct(qtbot):
    """SC-U018-2: the content-fit action is reachable from the View menu as
    a named, translated entry. SC-U018-4: it is distinguishable from the
    existing Fit to View action -- both remain separately reachable."""
    from pixelart_creator.ui.app import create_app

    app, win = create_app([])
    qtbot.addWidget(win)
    _settle(app)

    actions = win._view_menu.actions()
    assert win._fit_action in actions
    assert win._fit_content_action in actions
    assert win._fit_content_action is not win._fit_action
    assert win._fit_content_action.text() != ""
    assert win._fit_action.text() != win._fit_content_action.text()

    # F5 (Article V.2): LanguageChange re-sets the text without leaving it
    # empty -- the retranslate wiring this task's diff added.
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))
    assert win._fit_content_action.text() != ""


def test_sc_u018_3_fit_to_view_still_fits_the_whole_document(build_view):
    """SC-U018-3: Fit to View still exists and still fits the WHOLE
    document rectangle -- unaffected by the new content-fit action, proven
    by round-tripping through content-fit and back."""
    view, scene, _stack, _doc = build_view(frames=1, width=256, height=256)
    view.fit()
    whole_doc_zoom = view.zoom()  # the untouched _fit_action's own result

    scene.active_buffer().fill_rect(100, 100, 41, 41, RED)
    view.fit_content()
    assert view.zoom() != pytest.approx(
        whole_doc_zoom
    )  # content-fit really is narrower

    view.fit()  # Fit to View again

    assert view.zoom() == pytest.approx(whole_doc_zoom)
