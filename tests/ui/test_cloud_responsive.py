"""Cloud ops stay off the GUI thread + fail gracefully (SC-UI-005-1, REQ-P10-UI-005).

Every cloud op runs on the window-owned single-thread pool off the GUI thread, so
``submit`` returns immediately and the event loop keeps running while the worker
is busy — the UI never freezes. A failing op surfaces as a ``QMessageBox`` via
``operationFailed`` and never crashes the app (the terminal ``done`` fires from a
``finally``, so busy can never strand). Headless (offscreen), both themes.
"""

from __future__ import annotations

import threading

from PySide6.QtWidgets import QInputDialog

import pixelart_creator.ui.cloud_actions as cloud_actions
from pixelart_creator.data.cloud import CloudError, FakeCloudAdapter
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.ui.cloud_actions import Cloud_Session, make_save_job
from pixelart_creator.ui.cloud_worker import Cloud_Controller
from pixelart_creator.ui.main_window import Main_Window

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc() -> Document:
    return Document(16, 16, palette=Palette(STARTER))


def test_sc_ui_005_submit_is_non_blocking_gui_stays_live(qtbot, monkeypatch):
    """SC-UI-005-1: while the worker is busy the GUI thread keeps pumping events."""
    gate = threading.Event()
    real_serialize = cloud_actions.serialize_project

    def _slow_serialize(document):
        gate.wait(timeout=5.0)  # hold the WORKER thread, not the GUI thread
        return real_serialize(document)

    monkeypatch.setattr(cloud_actions, "serialize_project", _slow_serialize)

    session = Cloud_Session()
    session.connect_provider()
    port = session.port()
    controller = Cloud_Controller()
    try:
        token = controller.submit("save", make_save_job(port, "proj", _doc()))
        assert token > 0  # returned immediately; work is off-thread
        assert controller.is_busy() is True

        qtbot.wait(50)  # the GUI thread pumps freely while the worker blocks
        assert controller.is_busy() is True  # still running, GUI not frozen

        with qtbot.waitSignal(controller.operationFinished, timeout=5000):
            gate.set()
        assert controller.is_busy() is False
    finally:
        gate.set()
        controller.shutdown()


def test_sc_ui_005_failure_surfaces_via_signal_not_crash(qtbot):
    """SC-UI-005-1: a port error surfaces on operationFailed (never a crash)."""

    class _RaisingAdapter(FakeCloudAdapter):
        def put(self, *a, **k):
            raise CloudError("simulated provider outage")

    session = Cloud_Session(factory=lambda: _RaisingAdapter(connected=True))
    session.connect_provider()
    port = session.port()
    controller = Cloud_Controller()
    try:
        # Record the failed outcome, but BLOCK on the terminal ``operationFinished``
        # (fired off the finally-run ``done``) before asserting idle — so the idle
        # check is robust to GUI-thread scheduling instead of assuming the failed
        # relay has already cleared busy by the time we look. Still asserts the real
        # behaviour: the error surfaces on ``operationFailed`` and, once the terminal
        # signal is delivered, the UI is not stranded on "Working…".
        failures: list = []
        controller.operationFailed.connect(lambda k, m: failures.append((k, m)))
        with qtbot.waitSignal(controller.operationFinished, timeout=5000):
            controller.submit("save", make_save_job(port, "proj", _doc()))
        assert len(failures) == 1  # failed fired before the terminal
        kind, message = failures[0]
        assert kind == "save"
        assert "simulated provider outage" in message
        # Busy cleared via the terminal done -> the UI is not stranded on "Working…".
        assert controller.is_busy() is False
    finally:
        controller.shutdown()


def test_sc_ui_005_window_failure_shows_message_box(
    qtbot, monkeypatch, mute_message_boxes
):
    """SC-UI-005-1: a failed Main_Window cloud save surfaces a warning message box."""
    win = Main_Window()
    qtbot.addWidget(win)
    win._on_cloud_connect()

    def _boom(document):
        raise CloudError("serialise failed")

    monkeypatch.setattr(cloud_actions, "serialize_project", _boom)
    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: ("proj", True))
    )

    with qtbot.waitSignal(win._cloud_controller.operationFailed, timeout=5000):
        win._on_cloud_save()
    qtbot.wait(20)  # let the queued warning slot run on the GUI thread
    # _on_cloud_failed routed to QMessageBox.warning (recorded by the fixture).
    assert any(kind == "warning" for kind, _t, _msg in mute_message_boxes)
