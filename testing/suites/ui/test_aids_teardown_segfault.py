"""Phase-9 widget-disposal / xdist-segfault regression guard (Phase-5 class).

Guards CI run 28702019804: a native ``Segmentation fault`` crashed xdist worker
gw1 inside a ``qtbot.waitSignal`` on the Phase-8 automation worker, on
``test_automation_errors.py::…multiop_script_failure_is_atomic[dark]``. Phase 9
added ~162 UI tests, reshuffling the xdist test-to-worker distribution so the
automation test landed next to the Phase-9 visual-aids tests.

Root cause (see ``conftest._PHASE9_DISPOSABLE``): a Phase-9 top-level widget
(``Timelapse_Controls`` binds a **parent-less** test ``QUndoStack`` via
``bind_undo_stack`` → ``stack.indexChanged.connect``; the preview / document /
reference-board views hold a ``QGraphicsView`` on the shared scene) is
``qtbot.addWidget``-registered. Headless there is no running event loop, so
qtbot's teardown ``deleteLater`` never fires and the widget survives the test with
that connection live. The orphan ``QUndoStack`` is then GC-deleted (parent-less,
no other ref) while the widget's C++ object is still alive → a dangling
connection; the NEXT test's event loop (an automation ``waitSignal``) flushes
every accumulated ``DeferredDelete`` at once and dereferences the freed sender →
the PySide6 cross-thread/GC-of-Qt-C++ native segfault.

The fix (owned in ``tests/ui/conftest.py``) tracks these Phase-9 widgets in the
``_LIVE_UI_INSTANCES`` registry and ``shiboken6.delete``-s them SYNCHRONOUSLY,
before the per-test ``gc.collect``, so the connection is torn down cleanly and the
orphan QObject is collected with no live receiver. These tests pin BOTH halves:
the registry covers every Phase-9 disposable class, and an automation run staged
immediately after a Phase-9 leak (the exact CI crash site) stays stable.
"""

from __future__ import annotations

import shiboken6
from PySide6.QtGui import QUndoCommand, QUndoStack

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.multi_view import Multi_View
from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls
from testing.suites.ui._automation_helpers import procgen_op, run_ops
from testing.suites.ui.conftest import _LIVE_UI_INSTANCES, _PHASE9_DISPOSABLE


class _Noop(QUndoCommand):
    """A do-nothing undoable command (drives a forward index change)."""

    def redo(self) -> None:  # noqa: D401
        pass

    def undo(self) -> None:
        pass


def test_phase9_disposable_widgets_join_the_teardown_registry(qtbot, make_scene):
    """Every Phase-9 disposable widget is tracked so the drain fixture disposes it.

    The dangling-connection segfault is only prevented if the leaking widget is
    disposed *synchronously* at teardown. That requires it to be in
    ``_LIVE_UI_INSTANCES``; assert construction registers each class.
    """
    scene = make_scene(16, 16)

    controls = Timelapse_Controls()
    preview = Real_Size_Preview_Window(scene)
    board = Reference_Board()
    doc_view = Multi_View(scene).open_view()
    for widget in (controls, preview, board, doc_view):
        qtbot.addWidget(widget)

    live = set(_LIVE_UI_INSTANCES)
    for widget in (controls, preview, board, doc_view):
        assert type(widget) in _PHASE9_DISPOSABLE
        assert widget in live, f"{type(widget).__name__} must be tracked for disposal"


def test_timelapse_controls_bound_to_orphan_stack_are_disposed(qtbot):
    """A Timelapse_Controls bound to a parent-less QUndoStack is C++-disposed cleanly.

    Reproduces the exact leak (record on, a forward push) the aids-edges tests
    create, then asserts the drain fixture's disposal contract removes the widget's
    C++ object so no dangling ``indexChanged`` connection can survive into a later
    test's event loop. The bound ``QUndoStack`` is parent-less on purpose — the
    condition that made GC delete it out from under the still-live widget.
    """
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    stack = QUndoStack()  # parent-less, exactly like the aids-edges tests
    controls.bind_undo_stack(stack)
    controls._record_button.setChecked(True)
    stack.push(_Noop())
    assert controls.frame_count() == 1

    # The drain fixture disposes it at teardown; prove disposal is available and
    # deterministic here so a regression that drops the registry entry is caught.
    assert controls in set(_LIVE_UI_INSTANCES)
    shiboken6.delete(controls)
    assert not shiboken6.isValid(controls)  # C++ object gone -> connection removed


def test_automation_run_is_stable_after_phase9_widget_leak(qtbot):
    """The CI crash site: an automation run staged after a Phase-9 leak must not crash.

    Runs a real off-GUI-thread automation op through the window's worker (the exact
    ``qtbot.waitSignal`` that segfaulted on gw1). It runs after the leak-producing
    tests above (definition order), so the drain fixture must have already disposed
    their widgets; a regression that stops disposing them re-introduces the native
    segfault here (and across the suite under ``pytest -n auto``).
    """
    win = Main_Window()
    qtbot.addWidget(win)
    tab = win.active_tab()
    before = tab.stack.count()

    run_ops(qtbot, win, [procgen_op(seed=7)])  # the automation waitSignal path

    assert tab.stack.count() == before + 1  # one grouped automation command landed
