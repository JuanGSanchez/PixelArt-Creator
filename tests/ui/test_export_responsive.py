"""UI responsiveness + cancel during export (SC-UI-010-1, REQ-P7-UI-010).

Export runs on the window-owned single-thread ``QThreadPool`` off the GUI thread,
so submitting a large/batch export never freezes the window: ``submit`` returns
immediately and the GUI event loop keeps processing while the worker runs. Cancel
is cooperative, checked BETWEEN targets, and returns the UI to idle. (Mid-encode
cancel of a single huge target is a known FU-1 per AGT-10 §3/§6 — deliberately NOT
asserted as a blocker here.) Headless, both themes (autouse ``theme`` fixture).
"""

from __future__ import annotations

import threading

import pixelart_creator.ui.export_worker as export_worker
from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.ui.export_worker import ExportTarget
from tests.ui._export_helpers import single_frame_document


def _png_target(tmp_path, name):
    return ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG),
        out_path=str(tmp_path / name),
        label=name,
    )


def _gate_the_worker(monkeypatch, gate: threading.Event):
    """Patch the worker's ``export_document`` to block on ``gate`` before running."""
    real = export_worker.export_document

    def _slow(document, request):
        gate.wait(timeout=5.0)  # hold the WORKER thread, not the GUI thread
        return real(document, request)

    monkeypatch.setattr(export_worker, "export_document", _slow)


def test_sc_ui_010_submit_is_non_blocking_gui_stays_live(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """SC-UI-010-1: while the worker is busy, ``submit`` has already returned and the
    GUI thread keeps processing events (it is NOT frozen)."""
    gate = threading.Event()
    _gate_the_worker(monkeypatch, gate)
    doc = single_frame_document()

    token = export_controller.submit(doc, (_png_target(tmp_path, "r.png"),))
    assert token > 0  # returned immediately, work is off-thread
    assert export_controller.is_busy() is True

    # The GUI thread is free: it can pump its event loop while the worker blocks.
    qtbot.wait(50)
    assert export_controller.is_busy() is True  # still running, GUI not blocked

    # Release the worker; the run completes and the UI returns to idle.
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        gate.set()
    assert export_controller.is_busy() is False
    assert (tmp_path / "r.png").exists()


def test_sc_ui_010_cancel_returns_ui_to_idle(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """SC-UI-010-1: cancelling a running batch returns the controller to idle
    (busy cleared, terminal signal fired) — cancel is observed at a target boundary."""
    gate = threading.Event()
    _gate_the_worker(monkeypatch, gate)
    doc = single_frame_document()

    targets = tuple(_png_target(tmp_path, f"c{i}.png") for i in range(4))
    export_controller.submit(doc, targets)
    assert export_controller.is_busy() is True

    # Cancel while the first target is held; releasing the gate lets the loop reach
    # the next target boundary, see the cancel flag, break, and emit batchFinished.
    export_controller.cancel()
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        gate.set()

    assert export_controller.is_busy() is False
    # Continue-on-cancel stopped early: not every target was written.
    written = sum(1 for i in range(4) if (tmp_path / f"c{i}.png").exists())
    assert written < 4
