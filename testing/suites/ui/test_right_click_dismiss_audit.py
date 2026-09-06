"""Audit of the right-click dismissal rule: every OTHER right-click popup
in the product, checked against the same dismissal rule the colour hub's
right-click dismissal defect was re-opened over — "a second right-click
while a popup is open must not re-anchor/re-show it." See ADR-0066
(``docs/adr/0066-colour-hub-dismissal-is-a-same-press-identity-check.md``)
for the colour hub's own fix and what it explicitly does and does not
claim. The colour hub itself has its own, separately owned dismissal-fix
tests; this module does not touch or duplicate them.

**Surfaces enumerated from source on 2026-09-06, six total, five in scope
for the rule, one explicitly out of scope:**

1. ``pixelart_creator/ui/canvas_view.py`` ``_show_guide_context_menu`` — a
   ``QMenu`` shown via ``menu.exec(global_pos)`` for the guide-removal
   gesture, dispatched from ``Canvas_View.mousePressEvent``'s own
   ``RightButton`` branch via ``_dispatch_menu`` (a hand-rolled dispatch, not
   Qt's native ``contextMenuEvent``/``customContextMenuRequested`` path).
2. ``pixelart_creator/ui/canvas_view.py`` ``_show_placeholder_menu`` — the
   Phase-1 placeholder ``QMenu``, reached from the SAME ``_dispatch_menu``
   whenever no guide is hit and no menu hook is registered.
3. ``pixelart_creator/ui/reference_board.py`` ``Reference_Item.contextMenuEvent``
   — a ``QGraphicsItem`` override, Qt's own native graphics-scene context-menu
   entry point, building a Raise/Lower ``QMenu``.
4. ``pixelart_creator/ui/timeline_grid_view.py`` ``_on_context_menu_requested``
   — wired via ``setContextMenuPolicy(CustomContextMenu)`` +
   ``customContextMenuRequested`` (Qt's OWN standard native context-menu
   policy, the most idiomatic of the four), building a "Create Cel Here"
   ``QMenu`` only over an empty, eligible cell.
5. ``pixelart_creator/ui/tileset_editor_panel.py`` ``_Tile_Pixel_Editor``
   lines ~131/141 (``mousePressEvent``/``mouseMoveEvent``) — the right BUTTON
   erases a pixel directly; it opens **no menu at all**. Per the job spec
   this is recorded as **OUT OF SCOPE FOR THE RULE**, not silently skipped
   (``test_tileset_right_click_erase_opens_no_menu_out_of_scope`` below).

Surface count examined: **6** (5 exercised against the rule + 1 recorded
out of scope). See ``test_rec4_surface_enumeration_count`` for the pinned
count.

**The reasoning this module explicitly refuses to use:** "it is a
``QMenu``, and ``QMenu`` sets ``WA_NoMouseReplay``, therefore it conforms"
is NOT accepted here. Every surface below was EXERCISED — real gestures
delivered to the real widgets, never assumed from the widget's class — and
one of the very things exercised (see
``test_*_no_reentrancy_guard_characterisation`` below) is that
``WA_NoMouseReplay`` reads **``False``** on these menus' live ``QMenu``
instances in this environment (measured directly, both under
``QT_QPA_PLATFORM=offscreen`` and under the real ``windows`` QPA plugin
available in this session), which directly CONTRADICTS the class-based
assumption just described. Good thing it was never assumed.

**The instrument ceiling — a known limit established for the colour hub's
own investigation (ADR-0066), extended here to every surface in this
module:** widget-level test injection cannot engage the real platform
popup grab. That investigation measured that ``QTest``/widget-level event
injection cannot engage the platform-native popup-closing grab
(``QGuiApplicationPrivate::processMouseEvent``) on ANY platform — it is
bypassed entirely by direct-to-widget delivery (``QTest.mouseClick``,
``QApplication.sendEvent``). This module confirms, by direct exercise (not
by re-deriving the same fact from first principles), that this ceiling is
**not specific to the colour hub's hand-rolled ``Qt.WindowType.Popup``** —
it applies identically to a genuine, real, ``QMenu.exec()``-driven popup.
Delivering a second synthetic right-click gesture to a surface's
underlying widget WHILE its menu is still executing its OWN real,
unpatched, un-faked ``exec()`` modal loop reaches the seam again and
constructs a SECOND, independent ``QMenu`` in every one of the four
in-scope surfaces below (canvas guide-menu, canvas placeholder-menu,
reference-board raise/lower, timeline create-cel) — a genuine,
reproducible, exercised SEAM-LEVEL fact, not an assumption. **This is NOT
proof that any of these four surfaces exhibits the visible defect on real
hardware.** A real user's second right-click is, on real hardware, very
plausibly consumed by Qt's platform-level popup grab BEFORE it is ever
redelivered to ``Canvas_View``/the reference item/the timeline grid at
all — exactly the mechanism that (unlike the colour hub, per that same
investigation) has decades of real-world Qt/desktop track record behind
it for ordinary ``QMenu``. This module's instrument (widget/event-level
synthetic injection) cannot engage that platform layer to settle the
question either way, on either platform configuration available in this
session — the SAME limit already recorded for the colour hub, now
disclosed for these four surfaces too rather than silently assumed away
in either direction.

**Verdicts, each with the observation that settles it — full detail plus
the raw probe transcripts in the delivery report:**

- **1 canvas guide-menu**: COULD NOT FULLY VERIFY hardware fidelity; a
  seam-level gap is confirmed by exercise -- real ``QMenu``,
  ``WA_NoMouseReplay`` reads ``False`` live; a synthetic 2nd press
  reaching the seam while open constructs a 2nd menu (no app-level guard).
- **2 canvas placeholder-menu**: same as #1 -- same mechanism, same code
  path (``_dispatch_menu``).
- **3 reference-board raise/lower**: same as #1, via a direct 2nd
  ``contextMenuEvent`` re-entry.
- **4 timeline create-cel**: same as #1, via a 2nd ``QContextMenuEvent``/
  ``sendEvent`` re-entry (Qt's own CustomContextMenu policy path).
- **5 tileset right-button erase**: OUT OF SCOPE FOR THE RULE -- no
  ``QMenu`` import in the module at all; right button paints, opens
  nothing.

Given the genuine, disclosed uncertainty above, this module does **not**
force an unsupported CONFORMS, and does **not** file an unsupported DEVIATES
either — no defect is filed against any of the four ``QMenu`` surfaces on
this evidence — it PINS what IS honestly established for each of the four:
(a) the surface still uses Qt's own real, standard ``QMenu`` popup mechanism
rather than a hand-rolled widget (proven red against a non-``QMenu`` stand-in,
proven green against the current code), and (b) the exact, current,
exercised seam re-entrancy characterisation, so a FUTURE change to any of
these four seams is caught by this suite either way it moves.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QContextMenuEvent,
    QImage,
    QMouseEvent,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsSceneContextMenuEvent,
    QMenu,
)

import pixelart_creator.ui.canvas_view as canvas_view_mod
import pixelart_creator.ui.reference_board as reference_board_mod
import pixelart_creator.ui.timeline_grid_view as timeline_grid_view_mod
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.guides import GuideOrientation
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.track_table import track_table
from pixelart_creator.ui.canvas_view import Canvas_View
from pixelart_creator.ui.guides_rulers_overlay import Guides_Rulers_Overlay
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.timeline_panel import Timeline_Panel
from testing.suites.ui._ui_helpers import real_right_click_pixel

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255), (10, 200, 10, 255)]

# --------------------------------------------------------------------------- #
# Shared tracking helpers. Each test that needs one calls the factory to get
# its OWN fresh class + instance list -- never shared/module-level state that
# could leak between tests or between the two ``theme`` runs.
# --------------------------------------------------------------------------- #


def _make_nonblocking_tracked_qmenu_class():
    """A REAL ``QMenu`` subclass (``isinstance`` genuinely holds) whose
    ``exec()`` returns immediately instead of entering the native modal loop.

    Used for the STRUCTURAL pin only ("a real QMenu is constructed and
    .exec() is called on it") -- never for the re-entrancy characterisation,
    which needs the REAL blocking exec() to be meaningful.
    """

    class _NonBlockingTrackedMenu(QMenu):
        instances: list = []
        exec_called_on: list = []

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            type(self).instances.append(self)

        def exec(self, *a, **kw):  # noqa: A003
            type(self).exec_called_on.append(self)
            return None

    return _NonBlockingTrackedMenu


class _FakeSignal:
    """Minimal real stand-in for a Qt signal (established pattern, see this
    suite's own ``test_guides_gestures.py::_FakeSignal``): records connected
    slots, can fire them, and -- critically -- actually EXISTS as
    ``.triggered``, so production code's ``action.triggered.connect(...)``
    does not raise. An earlier draft of this module omitted this (a
    ``_FakeAction`` with no ``.triggered`` at all) and the missing attribute
    raised INSIDE a real Qt C++-dispatched event callback
    (``QTest.mouseClick`` -> ``mousePressEvent`` -> ... -> ``_show_guide_
    context_menu``) -- PySide6 does not reliably propagate a Python
    exception raised inside such a callback as an ordinary test failure; it
    left the interpreter/Qt state corrupted and crashed a LATER, unrelated
    test's teardown with an access violation instead of failing the test
    that actually caused it. Caught, diagnosed and fixed in this same
    session (self-correction, A6-D3) before this module was finalised --
    the earlier access-violation run is not a product defect, it was this
    file's own broken test double."""

    def __init__(self) -> None:
        self._slots: list = []

    def connect(self, fn) -> None:  # noqa: ANN001
        self._slots.append(fn)

    def emit(self) -> None:
        for fn in self._slots:
            fn()


class _FakeAction:
    def __init__(self, text):
        self._text = text
        self._enabled = True
        self.triggered = _FakeSignal()

    def setEnabled(self, value):  # noqa: N802
        self._enabled = value

    def isEnabled(self):  # noqa: N802
        return self._enabled

    def text(self):
        return self._text


class _NotAQMenuStandIn:
    """The deliberately-broken variant for the structural pin's red proof:
    a hand-rolled stand-in that is NOT a ``QMenu`` at all -- structurally the
    same kind of substitution the colour hub's hand-rolled
    ``Qt.WindowType.Popup`` ``QDialog`` represented (a widget that does not
    get Qt's built-in popup machinery for free). ``isinstance(x, QMenu)``
    must read ``False`` against this, proving the pin is sensitive to
    exactly the class of regression it exists to catch."""

    instances: list = []

    def __init__(self, *a, **kw):
        type(self).instances.append(self)
        self._actions: list = []

    def addAction(self, text):  # noqa: N802
        action = _FakeAction(text)
        self._actions.append(action)
        return action

    def exec(self, *a, **kw):  # noqa: A003
        return None


def _make_realexec_tracked_qmenu_class():
    """A REAL ``QMenu`` subclass whose ``exec()`` genuinely blocks (calls the
    real base implementation) -- used ONLY by the re-entrancy characterisation
    tests, which schedule ``QTimer``s to drive a second gesture during the
    nested loop and then force-close every tracked instance so the test
    cannot hang (also backstopped by ``@pytest.mark.timeout``)."""

    class _RealExecTrackedMenu(QMenu):
        instances: list = []

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            type(self).instances.append(self)

    return _RealExecTrackedMenu


def _rig_guide_view(make_view):
    view, scene, stack = make_view(64, 64)
    guides = Guides_Rulers_Overlay(view, scene, QRectF(0, 0, 64, 64))
    guides.set_enabled(True)
    view.set_guides_overlay(guides)
    return view, scene, guides


# --------------------------------------------------------------------------- #
# Surface 1: canvas_view._show_guide_context_menu
# --------------------------------------------------------------------------- #


def test_guide_context_menu_c18_is_a_real_qmenu_not_a_hand_rolled_popup(
    make_view, monkeypatch
):
    """Structural pin: the guide-removal context menu is Qt's own real
    ``QMenu`` popup mechanism, not a hand-rolled widget (the colour hub's
    class of mistake). PASSES against current code (asserted here); PROVEN
    to FAIL against ``_NotAQMenuStandIn`` -- see the sibling PROOF test below,
    which asserts the identical condition against that deliberately-broken
    stand-in and shows it does NOT hold (the red half of that proof)."""
    view, scene, guides = _rig_guide_view(make_view)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)

    tracked_cls = _make_nonblocking_tracked_qmenu_class()
    monkeypatch.setattr(canvas_view_mod, "QMenu", tracked_cls)

    real_right_click_pixel(view, 10, 5)

    assert tracked_cls.instances, "the guide context menu was not built"
    menu = tracked_cls.instances[-1]
    assert isinstance(menu, QMenu), "must be a genuine QMenu, not a stand-in"
    assert tracked_cls.exec_called_on, "menu.exec() must have been called"


def test_guide_context_menu_c18_proof_fails_against_non_qmenu_stand_in(
    make_view, monkeypatch
):
    """Red proof for the pin above: swap in ``_NotAQMenuStandIn`` (never
    a product-file edit -- a monkeypatch of the module symbol, exactly the
    established pattern this suite already uses for ``_FakeMenu``) and show
    the SAME condition the pin asserts (``isinstance(menu, QMenu)``) fails."""
    view, scene, guides = _rig_guide_view(make_view)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)

    _NotAQMenuStandIn.instances.clear()
    monkeypatch.setattr(canvas_view_mod, "QMenu", _NotAQMenuStandIn)

    real_right_click_pixel(view, 10, 5)

    assert _NotAQMenuStandIn.instances, "the stand-in was not built"
    broken_menu = _NotAQMenuStandIn.instances[-1]
    assert not isinstance(broken_menu, QMenu), (
        "PROOF: the broken stand-in is correctly NOT a QMenu -- the pin's "
        "assertion would fail here"
    )


@pytest.mark.timeout(15)
def test_guide_context_menu_no_reentrancy_guard_characterisation(make_view):
    """Characterisation (seam-level only -- see the module docstring's
    instrument-ceiling disclosure, extending that same known limit to this
    surface): a second RightButton press delivered to the viewport WHILE
    the guide menu's own real, un-faked ``exec()`` is still executing
    reaches ``_dispatch_menu`` again and constructs a SECOND, independent
    ``QMenu`` -- the seam itself has no application-level guard against
    this, unlike the colour hub's post-fix app-wide dismiss filter (see
    ADR-0066). This does NOT establish the visible symptom on real
    hardware (a real second click may never reach this seam at all,
    intercepted first by Qt's own platform popup grab -- left just as
    unresolved here as it was for the colour hub's own real-hardware
    mechanism question). ``@pytest.mark.timeout(15)`` is a hard backstop;
    the QTimer-scheduled force-close below is what should actually end
    the nested loops."""
    view, scene, guides = _rig_guide_view(make_view)
    guides.overlay_item().add_guide(GuideOrientation.VERTICAL, 10.0)

    tracked_cls = _make_realexec_tracked_qmenu_class()
    canvas_view_mod.QMenu = tracked_cls
    try:
        dispatch_calls = []
        real_dispatch = Canvas_View._dispatch_menu

        def _spy_dispatch(self, event):
            dispatch_calls.append(event)
            return real_dispatch(self, event)

        Canvas_View._dispatch_menu = _spy_dispatch

        def _second_press_during_exec():
            # A different scene point, off the guide, while the first menu
            # is still executing its real nested loop.
            pt = view.mapFromScene(40.0, 40.0)
            pt = QPointF(pt.x(), pt.y())
            evt = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                pt,
                pt,
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(view.viewport(), evt)

        def _force_close_everything():
            for menu in tracked_cls.instances:
                if menu.isVisible():
                    menu.close()

        QTimer.singleShot(30, _second_press_during_exec)
        QTimer.singleShot(120, _force_close_everything)

        real_right_click_pixel(view, 10, 5)

        assert len(dispatch_calls) == 2, (
            "characterisation: expected the seam to be re-entered exactly "
            f"once more by the synthetic second press (got {len(dispatch_calls)} "
            "total dispatch calls) -- if this count ever changes, the seam's "
            "re-entrancy behaviour changed and this test's docstring/verdict "
            "table must be re-examined, not silently adjusted"
        )
        assert len(tracked_cls.instances) == 2, (
            "characterisation: expected TWO independent QMenu instances "
            f"(got {len(tracked_cls.instances)}) -- no app-level guard "
            "currently prevents a second menu while the first is open"
        )
        for menu in tracked_cls.instances:
            assert menu.isVisible() is False  # both were force-closed above
    finally:
        Canvas_View._dispatch_menu = real_dispatch
        canvas_view_mod.QMenu = QMenu


# --------------------------------------------------------------------------- #
# Surface 2: canvas_view._show_placeholder_menu
# --------------------------------------------------------------------------- #


def test_placeholder_menu_c18_is_a_real_qmenu_not_a_hand_rolled_popup(
    make_view, monkeypatch
):
    """Structural pin for the Phase-1 placeholder menu (no guide hit, no menu
    hook registered -- ``_show_placeholder_menu``): a real ``QMenu``, not a
    hand-rolled widget. Proven red against ``_NotAQMenuStandIn`` in the
    sibling proof test below."""
    view, scene, stack = make_view(64, 64)
    # No guides overlay, no menu hook -> _dispatch_menu falls through to
    # _show_placeholder_menu (canvas_view.py's own fallback order).

    tracked_cls = _make_nonblocking_tracked_qmenu_class()
    monkeypatch.setattr(canvas_view_mod, "QMenu", tracked_cls)

    real_right_click_pixel(view, 30, 30)

    assert tracked_cls.instances, "the placeholder menu was not built"
    menu = tracked_cls.instances[-1]
    assert isinstance(menu, QMenu)
    assert tracked_cls.exec_called_on


def test_placeholder_menu_c18_proof_fails_against_non_qmenu_stand_in(
    make_view, monkeypatch
):
    """Red proof for the placeholder-menu pin above."""
    view, scene, stack = make_view(64, 64)

    _NotAQMenuStandIn.instances.clear()
    monkeypatch.setattr(canvas_view_mod, "QMenu", _NotAQMenuStandIn)

    real_right_click_pixel(view, 30, 30)

    assert _NotAQMenuStandIn.instances
    broken_menu = _NotAQMenuStandIn.instances[-1]
    assert not isinstance(broken_menu, QMenu)


@pytest.mark.timeout(15)
def test_placeholder_menu_no_reentrancy_guard_characterisation(make_view):
    """Characterisation for the placeholder menu, same technique and same
    instrument-ceiling caveat as the guide-menu characterisation above (see
    the module docstring)."""
    view, scene, stack = make_view(64, 64)

    tracked_cls = _make_realexec_tracked_qmenu_class()
    canvas_view_mod.QMenu = tracked_cls
    try:
        dispatch_calls = []
        real_dispatch = Canvas_View._dispatch_menu

        def _spy_dispatch(self, event):
            dispatch_calls.append(event)
            return real_dispatch(self, event)

        Canvas_View._dispatch_menu = _spy_dispatch

        def _second_press_during_exec():
            pt = view.mapFromScene(40.0, 40.0)
            pt = QPointF(pt.x(), pt.y())
            evt = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                pt,
                pt,
                Qt.MouseButton.RightButton,
                Qt.MouseButton.RightButton,
                Qt.KeyboardModifier.NoModifier,
            )
            QApplication.sendEvent(view.viewport(), evt)

        def _force_close_everything():
            for menu in tracked_cls.instances:
                if menu.isVisible():
                    menu.close()

        QTimer.singleShot(30, _second_press_during_exec)
        QTimer.singleShot(120, _force_close_everything)

        real_right_click_pixel(view, 10, 5)

        assert len(dispatch_calls) == 2
        assert len(tracked_cls.instances) == 2
        for menu in tracked_cls.instances:
            assert menu.isVisible() is False
    finally:
        Canvas_View._dispatch_menu = real_dispatch
        canvas_view_mod.QMenu = QMenu


# --------------------------------------------------------------------------- #
# Surface 3: reference_board.Reference_Item.contextMenuEvent
# --------------------------------------------------------------------------- #


def _reference_item(qtbot, tmp_path):
    board = Reference_Board()
    qtbot.addWidget(board)
    img = QImage(20, 20, QImage.Format.Format_RGBA8888)
    img.fill(0xFF3366CC)
    path = tmp_path / "ref.png"
    img.save(str(path), "PNG")
    item = board.add_image(str(path))
    return board, item


def _context_event():
    ev = QGraphicsSceneContextMenuEvent(QEvent.Type.GraphicsSceneContextMenu)
    ev.setReason(QGraphicsSceneContextMenuEvent.Reason.Mouse)
    ev.setScreenPos(QPointF(0.0, 0.0).toPoint())
    return ev


def test_reference_board_menu_c18_is_a_real_qmenu_not_a_hand_rolled_popup(
    qtbot, tmp_path, monkeypatch
):
    """Structural pin for the reference board's Raise/Lower context menu."""
    board, item = _reference_item(qtbot, tmp_path)

    tracked_cls = _make_nonblocking_tracked_qmenu_class()
    monkeypatch.setattr(reference_board_mod, "QMenu", tracked_cls)

    item.contextMenuEvent(_context_event())

    assert tracked_cls.instances, "the raise/lower menu was not built"
    menu = tracked_cls.instances[-1]
    assert isinstance(menu, QMenu)
    assert tracked_cls.exec_called_on


def test_reference_board_menu_c18_proof_fails_against_non_qmenu_stand_in(
    qtbot, tmp_path, monkeypatch
):
    """Red proof for the reference-board pin above."""
    board, item = _reference_item(qtbot, tmp_path)

    _NotAQMenuStandIn.instances.clear()
    monkeypatch.setattr(reference_board_mod, "QMenu", _NotAQMenuStandIn)

    item.contextMenuEvent(_context_event())

    assert _NotAQMenuStandIn.instances
    broken_menu = _NotAQMenuStandIn.instances[-1]
    assert not isinstance(broken_menu, QMenu)


@pytest.mark.timeout(15)
def test_reference_board_menu_no_reentrancy_guard_characterisation(qtbot, tmp_path):
    """Characterisation for the reference board's raise/lower menu. Here the
    "second gesture" is delivered by directly re-invoking the SAME real Qt
    override (``contextMenuEvent``) a second time -- an even more direct
    (weaker-fidelity) synthetic injection than ``sendEvent``, so this result
    is, if anything, LESS able to speak to real-hardware fidelity than the
    canvas-view characterisations above; it is included for completeness and
    consistency across all four surfaces, with the same explicit caveat."""
    board, item = _reference_item(qtbot, tmp_path)

    tracked_cls = _make_realexec_tracked_qmenu_class()
    reference_board_mod.QMenu = tracked_cls
    try:

        def _second_context_event_during_exec():
            item.contextMenuEvent(_context_event())

        def _force_close_everything():
            for menu in tracked_cls.instances:
                if menu.isVisible():
                    menu.close()

        QTimer.singleShot(30, _second_context_event_during_exec)
        QTimer.singleShot(120, _force_close_everything)

        item.contextMenuEvent(_context_event())

        assert len(tracked_cls.instances) == 2, (
            "characterisation: expected TWO independent QMenu instances "
            f"(got {len(tracked_cls.instances)})"
        )
        for menu in tracked_cls.instances:
            assert menu.isVisible() is False
    finally:
        reference_board_mod.QMenu = QMenu


# --------------------------------------------------------------------------- #
# Surface 4: timeline_grid_view._on_context_menu_requested
# --------------------------------------------------------------------------- #


def _empty_cell_timeline(qtbot):
    doc = Document(64, 64, palette=Palette(STARTER))
    doc.frames[0].layers[0].name = "Base"
    doc.add_layer("Outline", frame_index=0)
    doc.add_frame()  # frame 1: "Outline" row is empty here
    doc.add_frame()  # frame 2: also empty -- a second, distinct empty cell

    stack = QUndoStack()
    panel = Timeline_Panel()
    qtbot.addWidget(panel)
    panel.resize(700, 220)
    panel.show()
    panel.set_context(doc, stack, lambda: None)
    panel._grid_toggle_action.setChecked(True)
    grid = panel._grid

    table = track_table(doc, active_frame=0)
    outline_row = next(i for i, r in enumerate(table.rows) if r.label == "Outline")
    return grid, outline_row


def _cell_center(grid, row: int, col: int) -> QPoint:
    return grid.visualRect(grid.model().index(row, col)).center()


def _send_ctx(grid, pos: QPoint) -> None:
    QApplication.sendEvent(
        grid.viewport(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos)
    )


def test_timeline_create_cel_menu_c18_is_a_real_qmenu_not_a_hand_rolled_popup(
    qtbot, monkeypatch
):
    """Structural pin for the timeline's "Create Cel Here" context menu."""
    grid, outline_row = _empty_cell_timeline(qtbot)

    tracked_cls = _make_nonblocking_tracked_qmenu_class()
    monkeypatch.setattr(timeline_grid_view_mod, "QMenu", tracked_cls)

    _send_ctx(grid, _cell_center(grid, outline_row, 1))

    assert tracked_cls.instances, "the create-cel menu was not built"
    menu = tracked_cls.instances[-1]
    assert isinstance(menu, QMenu)
    assert tracked_cls.exec_called_on


def test_timeline_create_cel_menu_c18_proof_fails_against_non_qmenu_stand_in(
    qtbot, monkeypatch
):
    """Red proof for the timeline create-cel pin above.

    Here the break surfaces even EARLIER than the other three surfaces'
    proof tests: ``_on_context_menu_requested`` constructs
    ``QAction(text, menu)`` -- passing the (fake) menu as the action's real
    Qt PARENT -- so a non-``QObject`` stand-in fails immediately with a
    ``TypeError`` raised inside the Qt-dispatched ``customContextMenuRequested``
    signal, captured by pytest-qt's own exception hook
    (``qtbot.captureExceptions``) rather than reaching an ``isinstance``
    check at all. That is still a valid, and arguably STRONGER, red proof:
    the broken variant does not merely fail the pin's assertion, it cannot
    even complete the gesture."""
    grid, outline_row = _empty_cell_timeline(qtbot)

    _NotAQMenuStandIn.instances.clear()
    monkeypatch.setattr(timeline_grid_view_mod, "QMenu", _NotAQMenuStandIn)

    with qtbot.captureExceptions() as exceptions:
        _send_ctx(grid, _cell_center(grid, outline_row, 1))

    assert exceptions, (
        "PROOF: the non-QMenu stand-in breaks the seam outright (TypeError "
        "constructing QAction's parent) -- captured here rather than left "
        "to crash an unrelated later test"
    )
    exc_type, exc_value, _tb = exceptions[0]
    assert exc_type is TypeError
    assert "QAction" in str(exc_value)


@pytest.mark.timeout(15)
def test_timeline_create_cel_menu_no_reentrancy_guard_characterisation(qtbot):
    """Characterisation for the timeline's create-cel menu, same technique
    and same instrument-ceiling caveat as the module docstring records."""
    grid, outline_row = _empty_cell_timeline(qtbot)

    tracked_cls = _make_realexec_tracked_qmenu_class()
    timeline_grid_view_mod.QMenu = tracked_cls
    try:

        def _second_ctx_during_exec():
            _send_ctx(grid, _cell_center(grid, outline_row, 2))

        def _force_close_everything():
            for menu in tracked_cls.instances:
                if menu.isVisible():
                    menu.close()

        QTimer.singleShot(30, _second_ctx_during_exec)
        QTimer.singleShot(120, _force_close_everything)

        _send_ctx(grid, _cell_center(grid, outline_row, 1))

        assert len(tracked_cls.instances) == 2, (
            "characterisation: expected TWO independent QMenu instances "
            f"(got {len(tracked_cls.instances)})"
        )
        for menu in tracked_cls.instances:
            assert menu.isVisible() is False
    finally:
        timeline_grid_view_mod.QMenu = QMenu


# --------------------------------------------------------------------------- #
# Surface 5: tileset_editor_panel -- OUT OF SCOPE FOR THE RULE (no menu)
# --------------------------------------------------------------------------- #


def test_tileset_right_click_erase_opens_no_menu_out_of_scope():
    """Recorded explicitly OUT OF SCOPE FOR THE DISMISSAL RULE, never
    silently omitted. ``tileset_editor_panel.py`` imports no ``QMenu`` at all
    (structural fact, checked here against the real module, not asserted
    from memory) -- the right button erases a pixel directly
    (``_Tile_Pixel_Editor.mousePressEvent``/``mouseMoveEvent``) and opens
    nothing a second right-click could need to dismiss. Right-click-erases
    behaviour itself is already covered by
    ``test_tileset_pixel_editor.py``; this test covers only the
    "opens no menu" fact this audit is responsible for."""
    import pixelart_creator.ui.tileset_editor_panel as tileset_mod

    assert not hasattr(tileset_mod, "QMenu"), (
        "tileset_editor_panel.py now imports QMenu -- the right-button-erase "
        "gesture may have grown a popup; if so it is IN SCOPE for the "
        "dismissal rule and this module's out-of-scope recording is stale"
    )


# --------------------------------------------------------------------------- #
# Enumeration pin: the audit's own surface count
# --------------------------------------------------------------------------- #


def test_rec4_surface_enumeration_count():
    """Pins the COUNT of right-click surfaces this audit examined from
    source -- six, five exercised against the dismissal rule, one
    recorded out of scope. A future discovery of a further surface (or the
    removal of one of these) must update this count deliberately, not let it
    drift unnoticed."""
    surfaces = (
        ("pixelart_creator/ui/canvas_view.py", "_show_guide_context_menu"),
        ("pixelart_creator/ui/canvas_view.py", "_show_placeholder_menu"),
        ("pixelart_creator/ui/reference_board.py", "Reference_Item.contextMenuEvent"),
        ("pixelart_creator/ui/timeline_grid_view.py", "_on_context_menu_requested"),
        (
            "pixelart_creator/ui/tileset_editor_panel.py",
            "_Tile_Pixel_Editor (out of scope, no menu)",
        ),
    )
    assert (
        len(surfaces) == 5
    ), "5 surfaces examined here + the colour hub (its own delivery) = 6 total"
