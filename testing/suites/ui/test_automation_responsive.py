"""UI responsiveness + cancel during automation — SC-UI-011-1 (REQ-P8-UI-011).

Automation runs on the window-owned single-thread ``QThreadPool`` off the GUI
thread, so submitting a long macro / large batch / big procgen never freezes the
window: ``submit`` returns immediately and the GUI event loop keeps processing
while the worker runs; cancel returns the controller to idle. This is behavioural
responsiveness, NOT the 16 ms frame budget (automation is batch work, spec §5).
The standalone ``automation_controller`` fixture drains + releases its pool +
carrier at teardown (the Phase-5 xdist-segfault guard). Headless; both themes.
"""

from __future__ import annotations

import threading

import pixelart_creator.ui.automation_worker as automation_worker
from pixelart_creator.ui.automation_worker import make_dispatch_job
from testing.suites.ui._automation_helpers import procgen_op


def _gate_engine(monkeypatch, gate: threading.Event) -> None:
    """Hold the WORKER thread inside the Qt-free dispatcher until ``gate`` is set."""
    real = automation_worker.scripting.dispatch

    def _slow(document, ops, on_target=None):
        gate.wait(timeout=5.0)  # blocks the worker thread, not the GUI thread
        return real(document, ops, on_target=on_target)

    monkeypatch.setattr(automation_worker.scripting, "dispatch", _slow)


def test_sc_ui_011_submit_is_non_blocking_gui_stays_live(
    qtbot, monkeypatch, automation_controller, make_document
):
    """SC-UI-011-1: submit returns immediately; the GUI keeps pumping while busy."""
    gate = threading.Event()
    _gate_engine(monkeypatch, gate)
    doc = make_document(64, 64)

    token = automation_controller.submit(make_dispatch_job(doc, [procgen_op(seed=7)]))
    assert token > 0  # returned immediately — work is off-thread
    assert automation_controller.is_busy() is True

    qtbot.wait(50)  # GUI thread free to pump events while the worker blocks
    assert automation_controller.is_busy() is True

    with qtbot.waitSignal(automation_controller.runFinished, timeout=5000):
        gate.set()
    assert automation_controller.is_busy() is False


def test_sc_ui_011_cancel_returns_ui_to_idle(
    qtbot, monkeypatch, automation_controller, make_document
):
    """SC-UI-011-1: cancelling a running automation returns the controller to idle."""
    gate = threading.Event()
    _gate_engine(monkeypatch, gate)
    doc = make_document(64, 64)

    automation_controller.submit(make_dispatch_job(doc, [procgen_op(seed=7)]))
    assert automation_controller.is_busy() is True

    automation_controller.cancel()
    with qtbot.waitSignal(automation_controller.runFinished, timeout=5000):
        gate.set()  # the held worker unblocks, sees the cancel, and finishes
    assert automation_controller.is_busy() is False


def test_sc_ui_011_real_run_completes_and_clears_busy(
    qtbot, automation_controller, make_document
):
    """SC-UI-011-1: an ungated real run completes off-thread and clears busy."""
    doc = make_document(64, 64)
    with qtbot.waitSignal(automation_controller.runFinished, timeout=5000):
        automation_controller.submit(make_dispatch_job(doc, [procgen_op(seed=7)]))
    assert automation_controller.is_busy() is False
