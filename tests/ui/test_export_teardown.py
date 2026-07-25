"""Export-worker teardown / xdist-segfault guard (REQ-P7-UI-010, TG-03/04).

After a window (or a standalone controller) that used the export worker is
disposed, NO export worker thread or connected signal carrier may survive into a
later test's GC — that is the Phase-5 cross-thread-GC-of-Qt-C++ segfault class the
whole UI suite guards against under ``pytest -n auto``. AGT-05 folded
``Export_Controller.shutdown()`` into ``Main_Window.shutdown_prewarm`` (hence
``closeEvent``); the ``tests/ui/conftest.py`` drain fixture calls
``shutdown_prewarm`` on every tracked ``Main_Window`` at teardown, so a
window-owned export controller IS reached. These tests dispatch a real export,
then prove the deterministic teardown drains the pool and releases the carrier —
for a whole ``Main_Window`` AND for a standalone controller. Headless, both themes.
"""

from __future__ import annotations

from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.ui.export_worker import ExportTarget
from pixelart_creator.ui.main_window import Main_Window
from tests.ui._export_helpers import single_frame_document


def _run_one_export(qtbot, controller, document, out_path):
    target = ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG),
        out_path=str(out_path),
        label="t",
    )
    with qtbot.waitSignal(controller.batchFinished, timeout=5000):
        controller.submit(document, (target,))


def test_main_window_shutdown_drains_export_controller(qtbot, tmp_path):
    """Disposing a Main_Window drains its export controller — no worker/carrier lives."""
    win = Main_Window()
    qtbot.addWidget(win)
    controller = win._export_controller

    _run_one_export(qtbot, controller, win.active_document(), tmp_path / "w.png")
    assert controller._signals is not None  # carrier live before teardown

    win.shutdown_prewarm()  # exactly what closeEvent / the drain fixture calls
    # No worker survives: pool drained, carrier released -> nothing to cross-thread-GC.
    assert controller._signals is None
    assert controller._pool.activeThreadCount() == 0
    assert controller.is_busy() is False

    win.shutdown_prewarm()  # idempotent: a second call is a safe no-op
    assert controller._signals is None


def test_standalone_controller_shutdown_is_idempotent_and_noop_submit(
    qtbot, export_controller, tmp_path
):
    """After shutdown the carrier is released and a further submit is a safe no-op."""
    doc = single_frame_document()
    _run_one_export(qtbot, export_controller, doc, tmp_path / "s.png")

    export_controller.shutdown()
    assert export_controller._signals is None
    assert export_controller._pool.activeThreadCount() == 0

    # A submit after shutdown must not start work or crash (carrier is gone).
    token_before = export_controller._token
    returned = export_controller.submit(
        doc,
        (
            ExportTarget(
                request=ExportRequest(fmt=ExportFormat.PNG),
                out_path=str(tmp_path / "after.png"),
                label="after",
            ),
        ),
    )
    assert returned == token_before
    assert not (tmp_path / "after.png").exists()
    export_controller.shutdown()  # idempotent second call (also the fixture's)
