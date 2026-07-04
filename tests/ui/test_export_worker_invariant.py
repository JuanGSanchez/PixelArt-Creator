"""THE D-1 INVARIANT — the export worker/controller can never strand the UI.

AGT-10's prescription (report af36e502 §5/§7) and the D-1a fix (AGT-05): on a
FAILING target the worker MUST still emit its terminal ``batchFinished`` and drive
``busyChanged(False)`` so the UI returns to idle and surfaces the error, and the
batch MUST continue past the failing target (continue-on-failure). This is the
regression test that would have caught the "Exporting…" hang — it exercises BOTH
of AGT-10's named failure kinds: a ``PixelBufferError`` (a ``ValueError`` subclass
that a *default* atlas export can raise, originally outside the worker's typed
catch) and a *generic* ``Exception`` (the unforeseen-type backstop).

S2-level: a regression here blocks ship (REQ-P7-UI-005 / -008 / -010). Headless,
both themes (autouse ``theme`` fixture). The controller's ``QThreadPool`` + carrier
are drained by the ``export_controller`` fixture's ``shutdown()`` on teardown.
"""

from __future__ import annotations

import threading

import pixelart_creator.ui.export_worker as export_worker
from pixelart_creator.logic.export import ExportFormat, ExportRequest
from pixelart_creator.logic.pixel_buffer import PixelBufferError
from pixelart_creator.ui.export_worker import (
    Export_Worker,
    ExportTarget,
    ExportWorkerSignals,
)
from tests.ui._export_helpers import single_frame_document

#: Marker tags routed by the fake ``export_document`` to a specific failure.
_FAIL_PIXELBUFFER = "__fail_pixelbuffer__"
_FAIL_GENERIC = "__fail_generic__"


def _install_failing_export(monkeypatch):
    """Patch ``export_worker.export_document`` to fail on the two marker tags.

    A target whose request ``tag`` is the PixelBuffer marker raises
    ``PixelBufferError`` (the default-atlas failure mode AGT-10 found); the generic
    marker raises a bare ``RuntimeError`` (the unforeseen-type backstop); any other
    target runs the real engine and succeeds.
    """
    real = export_worker.export_document

    def _fake(document, request):
        if request.tag == _FAIL_PIXELBUFFER:
            raise PixelBufferError("width 8192 exceeds maximum 7680")
        if request.tag == _FAIL_GENERIC:
            raise RuntimeError("totally unforeseen")
        return real(document, request)

    monkeypatch.setattr(export_worker, "export_document", _fake)


def _png_target(tmp_path, name, tag=None):
    return ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG, tag=tag),
        out_path=str(tmp_path / name),
        label=name,
    )


def test_d1_invariant_failing_targets_reach_idle_and_batch_continues(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """D-1 INVARIANT: a PixelBufferError target AND a generic-Exception target both
    still reach ``batchFinished`` + ``busyChanged(False)``; the batch continues and
    the surviving good target succeeds; the errors are surfaced (never swallowed)."""
    _install_failing_export(monkeypatch)
    doc = single_frame_document()

    busy_transitions: list[bool] = []
    failed: list[tuple[int, str]] = []
    ok: list[int] = []
    export_controller.busyChanged.connect(busy_transitions.append)
    export_controller.targetFailed.connect(lambda i, m: failed.append((i, m)))
    export_controller.targetSucceeded.connect(lambda i, _r: ok.append(i))

    targets = (
        _png_target(tmp_path, "a.png", tag=_FAIL_PIXELBUFFER),  # index 0 — raises
        _png_target(tmp_path, "b.png", tag=_FAIL_GENERIC),  # index 1 — raises
        _png_target(tmp_path, "c.png"),  # index 2 — real, succeeds
    )

    # The terminal signal MUST fire even though two targets raise.
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, targets)

    # Returns to idle: the last busy transition is False and is_busy() is cleared.
    assert busy_transitions[0] is True
    assert busy_transitions[-1] is False
    assert export_controller.is_busy() is False

    # Continue-on-failure: both bad targets reported, the good one still succeeded
    # and its file was written (one failure never aborts the rest).
    assert {index for index, _ in failed} == {0, 1}
    assert ok == [2]
    assert (tmp_path / "c.png").exists()

    # Errors are SURFACED (not swallowed): the generic backstop prefixes the type.
    messages = {index: msg for index, msg in failed}
    assert "8192" in messages[0]
    assert "RuntimeError" in messages[1]


def test_d1_invariant_all_targets_failing_still_reaches_finished(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """Even when EVERY target raises, ``batchFinished`` fires and busy clears — the
    ``finally``-emitted terminal signal is what guarantees "Exporting…" cannot
    hang forever (D-1a)."""
    _install_failing_export(monkeypatch)
    doc = single_frame_document()

    finished: list[bool] = []
    export_controller.batchFinished.connect(lambda: finished.append(True))

    targets = (
        _png_target(tmp_path, "x.png", tag=_FAIL_PIXELBUFFER),
        _png_target(tmp_path, "y.png", tag=_FAIL_GENERIC),
    )
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, targets)

    assert finished == [True]
    assert export_controller.is_busy() is False


def test_d1_invariant_unwritable_path_target_is_reported_not_fatal(
    qtbot, export_controller, tmp_path
):
    """A real OSError (write into a path whose parent is a FILE) is reported per
    target and the run still finishes idle — no monkeypatch, the genuine engine."""
    doc = single_frame_document()
    # Make ``blocker`` a regular file, then try to write "under" it as if a dir.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    bad = ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG),
        out_path=str(blocker / "nested.png"),
        label="bad",
    )
    good = _png_target(tmp_path, "good.png")

    failed: list[str] = []
    ok: list[int] = []
    export_controller.targetFailed.connect(lambda _i, m: failed.append(m))
    export_controller.targetSucceeded.connect(lambda i, _r: ok.append(i))

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, (bad, good))

    assert export_controller.is_busy() is False
    assert len(failed) == 1  # the bad target surfaced an error
    assert ok == [1]  # the good target still exported
    assert (tmp_path / "good.png").exists()


# --------------------------------------------------------------------------- #
# White-box worker.run() coverage (synchronous — coverage cannot trace the      #
# QThreadPool worker thread, so the run() body is exercised in-thread here).    #
# --------------------------------------------------------------------------- #


def _collector_signals():
    """Return an ``ExportWorkerSignals`` plus lists recording each emission."""
    signals = ExportWorkerSignals()
    rec = {"progress": [], "ok": [], "failed": [], "finished": []}
    signals.progress.connect(lambda t, d, tot, lbl: rec["progress"].append((d, tot)))
    signals.targetSucceeded.connect(lambda t, i, r: rec["ok"].append(i))
    signals.targetFailed.connect(lambda t, i, m: rec["failed"].append((i, m)))
    signals.batchFinished.connect(lambda t: rec["finished"].append(t))
    return signals, rec


def test_worker_run_synchronous_isolates_failures_and_emits_terminal(
    monkeypatch, tmp_path
):
    """Driving ``Export_Worker.run()`` in-thread covers every per-target branch:
    success, the PixelBufferError catch, the generic backstop, the OSError catch,
    and the ``finally`` terminal tick + ``batchFinished``."""
    _install_failing_export(monkeypatch)
    doc = single_frame_document()
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    targets = (
        _png_target(tmp_path, "ok.png"),  # 0 — succeeds
        _png_target(tmp_path, "pb.png", tag=_FAIL_PIXELBUFFER),  # 1 — PixelBufferError
        _png_target(tmp_path, "boom.png", tag=_FAIL_GENERIC),  # 2 — generic backstop
        ExportTarget(  # 3 — OSError (write under a file)
            request=ExportRequest(fmt=ExportFormat.PNG),
            out_path=str(blocker / "n.png"),
            label="oserr",
        ),
    )
    signals, rec = _collector_signals()
    worker = Export_Worker(7, doc, targets, threading.Event(), signals)
    worker.run()

    assert rec["finished"] == [7]  # terminal signal fired exactly once
    assert rec["ok"] == [0]
    assert {i for i, _ in rec["failed"]} == {1, 2, 3}
    assert rec["progress"][-1] == (4, 4)  # final full-progress tick


def test_worker_run_cancel_before_start_still_emits_terminal(tmp_path):
    """A worker whose cancel event is already set breaks at the first boundary and
    still emits the terminal ``batchFinished`` (the pre-loop cancel branch)."""
    doc = single_frame_document()
    cancel = threading.Event()
    cancel.set()
    signals, rec = _collector_signals()
    worker = Export_Worker(
        3, doc, (_png_target(tmp_path, "never.png"),), cancel, signals
    )
    worker.run()

    assert rec["finished"] == [3]
    assert rec["ok"] == []
    assert not (tmp_path / "never.png").exists()


def test_controller_relay_drops_stale_token_emissions(export_controller):
    """A superseded run's queued emissions (token != current) are dropped by the
    relay slots — covers the false branch of each token filter."""
    export_controller._token = 5  # current run
    emitted: list[str] = []
    export_controller.progress.connect(lambda *_a: emitted.append("p"))
    export_controller.targetSucceeded.connect(lambda *_a: emitted.append("s"))
    export_controller.targetFailed.connect(lambda *_a: emitted.append("f"))
    export_controller.batchFinished.connect(lambda: emitted.append("b"))

    stale = 1
    export_controller._on_progress(stale, 0, 1, "")
    export_controller._on_target_succeeded(stale, 0, object())
    export_controller._on_target_failed(stale, 0, "x")
    export_controller._on_batch_finished(stale)

    assert emitted == []  # every stale emission dropped
