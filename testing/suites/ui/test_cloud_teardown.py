"""Cloud-worker teardown / xdist-segfault guard (REQ-P10-UI-005, Phase-5/6/9 class).

This is an off-GUI-thread worker slice — the exact recurring PySide6 native-
segfault class. After a ``Main_Window`` (or a standalone ``Cloud_Controller``) that
used the cloud worker is disposed, NO cloud worker thread or connected signal
carrier may survive into a later test's GC. AGT-05 folded
``Cloud_Controller.shutdown()`` (and ``_autosave_timer.stop()``) into
``Main_Window.shutdown_prewarm`` -> ``closeEvent``; the ``testing/suites/ui/conftest.py``
drain fixture calls ``shutdown_prewarm`` on every tracked ``Main_Window`` at
teardown, and now also disposes the parent-less cloud dialogs. These tests dispatch
a real cloud op, then prove the deterministic teardown drains the pool + releases
the carrier — for a whole window AND a standalone controller. Headless, both themes.
"""

from __future__ import annotations

from pixelart_creator.data.cloud import CloudError, FakeCloudAdapter
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.cloud_actions import Cloud_Session, make_save_job
from pixelart_creator.ui.cloud_worker import Cloud_Controller
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.recovery_prompt import Recovery_Prompt
from pixelart_creator.ui.version_history_browser import Version_History_Browser

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc() -> Document:
    return Document(16, 16, palette=Palette(STARTER))


def _run_one_save(qtbot, controller, port):
    with qtbot.waitSignal(controller.operationFinished, timeout=5000):
        controller.submit("save", make_save_job(port, "proj", _doc()))


def test_main_window_shutdown_drains_cloud_controller(qtbot):
    """Disposing a Main_Window drains its cloud controller — no worker/carrier lives.

    Regression assertion for the off-thread-worker segfault class: after a real
    cloud op and ``shutdown_prewarm``, the pool has zero live worker threads, the
    GUI-thread carrier is released, busy is cleared, and the autosave timer stopped.
    """
    win = Main_Window()
    qtbot.addWidget(win)
    win._on_cloud_connect()
    controller = win._cloud_controller
    port = win._cloud_session.port()

    _run_one_save(qtbot, controller, port)
    assert controller._signals is not None  # carrier live before teardown
    assert win._autosave_timer.isActive() is True

    win.shutdown_prewarm()  # exactly what closeEvent / the drain fixture calls
    # No cloud worker survives: pool drained, carrier released, timer stopped.
    assert controller._signals is None
    assert controller._pool.activeThreadCount() == 0
    assert controller.is_busy() is False
    assert win._autosave_timer.isActive() is False

    win.shutdown_prewarm()  # idempotent: a second call is a safe no-op
    assert controller._signals is None


def test_standalone_controller_shutdown_idempotent_and_noop_submit(qtbot):
    """After shutdown the carrier is released and a further submit is a safe no-op."""
    session = Cloud_Session()
    session.connect_provider()
    port = session.port()
    controller = Cloud_Controller()
    try:
        _run_one_save(qtbot, controller, port)
        controller.shutdown()
        assert controller._signals is None
        assert controller._pool.activeThreadCount() == 0

        # A submit after shutdown must not start work or crash (carrier is gone).
        token_before = controller._token
        returned = controller.submit("save", make_save_job(port, "proj", _doc()))
        assert returned == token_before
    finally:
        controller.shutdown()  # idempotent second call


def test_cloud_dialogs_own_no_worker_thread(qtbot):
    """The cloud dialogs are fully disposable — they hold no QThreadPool of their own.

    ``Version_History_Browser`` / ``Recovery_Prompt`` do only presentation over an
    already-fetched result; the off-thread work lives in ``Cloud_Controller``. So a
    dialog built directly (and registered in the drain fixture's disposable set) can
    be disposed synchronously with nothing live to cross-thread-GC.
    """
    versions = (
        CloudVersion(version_id="p:0", ordinal=0, created_marker=0, size_bytes=10),
    )
    browser = Version_History_Browser(versions)
    qtbot.addWidget(browser)
    prompt = Recovery_Prompt()
    qtbot.addWidget(prompt)

    from PySide6.QtCore import QThreadPool

    for dialog in (browser, prompt):
        pools = dialog.findChildren(QThreadPool)
        assert pools == []  # no dialog-owned worker pool


def test_shutdown_after_failed_op_still_clears_busy(qtbot):
    """A failing op still fires the terminal done (finally), so busy never strands."""

    class _RaisingAdapter(FakeCloudAdapter):
        def put(self, *a, **k):
            raise CloudError("boom")

    session = Cloud_Session(factory=lambda: _RaisingAdapter(connected=True))
    session.connect_provider()
    port = session.port()
    controller = Cloud_Controller()
    try:
        with qtbot.waitSignal(controller.operationFinished, timeout=5000):
            controller.submit("save", make_save_job(port, "proj", _doc()))
        assert controller.is_busy() is False  # cleared off the finally-fired done
    finally:
        controller.shutdown()
