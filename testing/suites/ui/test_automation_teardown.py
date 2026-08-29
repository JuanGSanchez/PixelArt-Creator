"""Automation-worker teardown / xdist-segfault guard (REQ-P8-UI-011; Phase-5 class).

After a window (or a standalone controller) that used the automation worker is
disposed, NO automation worker thread or connected signal carrier may survive
into a later test's GC — the Phase-5 cross-thread-GC-of-Qt-C++ segfault class the
whole UI suite guards against under ``pytest -n auto``. AGT-05 folded
``Automation_Controller.shutdown()`` into ``Main_Window.shutdown_prewarm`` (hence
``closeEvent``); the ``testing/suites/ui/conftest.py`` drain fixture calls
``shutdown_prewarm`` on every tracked ``Main_Window`` at teardown, so a
window-owned automation controller IS reached. These tests dispatch a real
automation run, then prove the deterministic teardown drains the pool and
releases the carrier — for a whole ``Main_Window`` AND a standalone controller.
Headless, both themes.
"""

from __future__ import annotations

from pixelart_creator.ui.automation_worker import make_dispatch_job
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._automation_helpers import procgen_op, run_ops


def test_main_window_shutdown_drains_automation_controller(qtbot):
    """Disposing a Main_Window drains its automation controller — no worker/carrier lives."""
    win = Main_Window()
    qtbot.addWidget(win)
    controller = win._automation_controller

    run_ops(qtbot, win, [procgen_op(seed=7)])  # exercise the real off-thread worker
    assert controller._signals is not None  # carrier live before teardown

    win.shutdown_prewarm()  # exactly what closeEvent / the drain fixture calls
    assert controller._signals is None  # carrier released → nothing to cross-thread-GC
    assert controller._pool.activeThreadCount() == 0
    assert controller.is_busy() is False

    win.shutdown_prewarm()  # idempotent second call is a safe no-op
    assert controller._signals is None


def test_standalone_controller_shutdown_idempotent_and_noop_submit(
    qtbot, automation_controller, make_document
):
    """After shutdown the carrier is released and a further submit is a safe no-op."""
    doc = make_document(64, 64)
    with qtbot.waitSignal(automation_controller.runFinished, timeout=5000):
        automation_controller.submit(make_dispatch_job(doc, [procgen_op(seed=7)]))

    automation_controller.shutdown()
    assert automation_controller._signals is None
    assert automation_controller._pool.activeThreadCount() == 0

    # A submit after shutdown must not start work or crash (the carrier is gone).
    token_before = automation_controller._token
    returned = automation_controller.submit(
        make_dispatch_job(doc, [procgen_op(seed=1)])
    )
    assert returned == token_before
    automation_controller.shutdown()  # idempotent (also the fixture's teardown call)
