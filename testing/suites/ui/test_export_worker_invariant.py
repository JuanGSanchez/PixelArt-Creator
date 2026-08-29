"""THE D-1 INVARIANT — the export worker/controller can never strand the UI.

AGT-10's prescription (report af36e502 §5/§7) and the D-1a fix (AGT-05): on a
FAILING target the worker MUST still emit its terminal ``batchFinished`` and drive
``busyChanged(False)`` so the UI returns to idle and surfaces the error, and the
batch MUST continue past the failing target (continue-on-failure). S2-level: a
regression here blocks ship (REQ-P7-UI-005 / -008 / -010). Headless, both themes
(autouse ``theme`` fixture). The controller's ``QThreadPool`` + carrier are
drained by the ``export_controller`` fixture's ``shutdown()`` on teardown.

**D-15 rewrite.** ``Export_Worker.run()`` no longer runs its own per-target
``export_document`` loop — it calls ``logic.export.run_batch`` ONCE and consumes
the returned ``BatchResult`` (fe311a6). The six tests below that used to patch
``export_worker.export_document`` (a name no longer imported into this module —
patching it now raises ``AttributeError``, confirmed against the shipped code
this session) are rewritten to patch ``export_worker.run_batch`` and feed it a
CRAFTED ``BatchResult`` (per AGT-05's own handoff, §"Open items" in report
a24fa5e0), proving the worker's own consumption contract: mixed success/failure,
order stability, ``write_export`` only on the success branch.

**A genuine regression this rewrite surfaced (kept, not watered down).** The
worker's OLD per-target loop caught a bare ``except Exception`` around the whole
``export_document`` + write step — the "unforeseen-type backstop" this file's
docstring names. ``logic.export.run_batch`` documents catching only
``ExportError``/``AtlasError``/``PixelBufferError`` per target; every other
exception type propagates OUT of ``run_batch`` uncaught, and
``Export_Worker.run()`` only wraps the ``run_batch`` CALL in ``except
ExportError`` (for the ``MAX_BATCH_TARGETS`` case) — nothing catches a
non-typed exception raised from INSIDE ``run_batch``'s own per-target loop.
``test_d1_regression_unforeseen_export_exception_no_longer_isolated_per_target``
below reproduces this against the REAL, unmocked ``run_batch`` (patching only
``logic.export.export_document``, the actual seam ``run_batch`` calls) and is
LEFT FAILING — a real defect, reported here with evidence, not fixed (AGT-06
never edits product code). The ``finally`` block still fires (so
``batchFinished``/``busyChanged(False)`` are NOT lost — the UI does not hang),
but continue-on-failure and per-target error reporting are broken for any
exception type outside the three ``run_batch`` now enumerates.
"""

from __future__ import annotations

import threading

import pixelart_creator.ui.export_worker as export_worker
from pixelart_creator.logic.export import (
    BatchResult,
    BatchTargetResult,
    ExportFormat,
    ExportRequest,
    export_document,
)
from pixelart_creator.logic.pixel_buffer import PixelBufferError
from pixelart_creator.ui.export_worker import (
    Export_Worker,
    ExportTarget,
    ExportWorkerSignals,
)
from testing.suites.ui._export_helpers import single_frame_document

#: Marker tags used only to pick which crafted index gets which outcome —
#: never routed to a real failure injection any more (that seam moved: see
#: ``_crafted_run_batch`` below).
_FAIL_PIXELBUFFER = "__fail_pixelbuffer__"
_FAIL_GENERIC = "__fail_generic__"


def _crafted_run_batch(failures: dict) -> callable:
    """Return a fake ``run_batch(document, requests) -> BatchResult``.

    Requests tagged in ``failures`` (``{tag: error_message}``) become a
    ``BatchTargetResult`` with that ``error`` set (exactly the shape the REAL
    ``run_batch`` produces for a caught ``ExportError``/``AtlasError``/
    ``PixelBufferError``); every other request is exported through the REAL,
    unmocked ``export_document`` — so a "succeeding" target in these tests is
    genuinely real bytes, not a stub, and ``write_export`` has real content to
    write (order + write-only-on-success are exercised honestly).
    """

    def _fake(document, requests):
        targets = []
        for index, request in enumerate(requests):
            if request.tag in failures:
                targets.append(
                    BatchTargetResult(
                        index=index, request=request, error=failures[request.tag]
                    )
                )
            else:
                targets.append(
                    BatchTargetResult(
                        index=index,
                        request=request,
                        result=export_document(document, request),
                    )
                )
        return BatchResult(tuple(targets))

    return _fake


def _png_target(tmp_path, name, tag=None):
    return ExportTarget(
        request=ExportRequest(fmt=ExportFormat.PNG, tag=tag),
        out_path=str(tmp_path / name),
        label=name,
    )


def test_d1_invariant_failing_targets_reach_idle_and_batch_continues(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """D-1 INVARIANT: two failing ``BatchResult`` targets AND one genuinely
    succeeding target all still reach ``batchFinished`` + ``busyChanged(False)``;
    the batch continues; the errors are surfaced (never swallowed)."""
    monkeypatch.setattr(
        export_worker,
        "run_batch",
        _crafted_run_batch(
            {
                _FAIL_PIXELBUFFER: "width 8192 exceeds maximum 7680",
                _FAIL_GENERIC: "RuntimeError: totally unforeseen",
            }
        ),
    )
    doc = single_frame_document()

    busy_transitions: list[bool] = []
    failed: list[tuple[int, str]] = []
    ok: list[int] = []
    export_controller.busyChanged.connect(busy_transitions.append)
    export_controller.targetFailed.connect(lambda i, m: failed.append((i, m)))
    export_controller.targetSucceeded.connect(lambda i, _r: ok.append(i))

    targets = (
        _png_target(tmp_path, "a.png", tag=_FAIL_PIXELBUFFER),  # index 0 — fails
        _png_target(tmp_path, "b.png", tag=_FAIL_GENERIC),  # index 1 — fails
        _png_target(tmp_path, "c.png"),  # index 2 — real, succeeds
    )

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, targets)

    assert busy_transitions[0] is True
    assert busy_transitions[-1] is False
    assert export_controller.is_busy() is False

    # Continue-on-failure + ORDER STABILITY: both bad targets reported at their
    # original indices, the good one still succeeded and was written to disk.
    assert {index for index, _ in failed} == {0, 1}
    assert ok == [2]
    assert (tmp_path / "c.png").exists()
    assert not (tmp_path / "a.png").exists()  # write_export never ran for a failure
    assert not (tmp_path / "b.png").exists()

    messages = {index: msg for index, msg in failed}
    assert "8192" in messages[0]
    assert "RuntimeError" in messages[1]


def test_d1_invariant_all_targets_failing_still_reaches_finished(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """Even when EVERY ``BatchResult`` target is a failure, ``batchFinished``
    fires and busy clears — the ``finally``-emitted terminal signal guarantee."""
    monkeypatch.setattr(
        export_worker,
        "run_batch",
        _crafted_run_batch(
            {_FAIL_PIXELBUFFER: "bad buffer", _FAIL_GENERIC: "bad everything"}
        ),
    )
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
    target and the run still finishes idle — no monkeypatch, the genuine engine
    (unaffected by the D-15 rewrite: the write stage still lives in the worker)."""
    doc = single_frame_document()
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
    assert len(failed) == 1
    assert ok == [1]
    assert (tmp_path / "good.png").exists()


def test_d1_write_stage_generic_exception_backstop_still_works(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """The worker's OWN write-stage ``except Exception`` backstop (line ~191,
    UNCHANGED by D-15 — ``run_batch`` never touches the filesystem) still
    isolates a totally unforeseen exception raised from ``write_export``."""

    def _boom(_result, _path):
        raise MemoryError("disk cache exhausted")

    monkeypatch.setattr(export_worker, "write_export", _boom)
    doc = single_frame_document()

    failed: list[str] = []
    export_controller.targetFailed.connect(lambda _i, m: failed.append(m))

    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, (_png_target(tmp_path, "a.png"),))

    assert export_controller.is_busy() is False
    assert len(failed) == 1
    assert "MemoryError" in failed[0]


def test_d1_regression_unforeseen_export_exception_no_longer_isolated_per_target(
    qtbot, monkeypatch, export_controller, tmp_path
):
    """REGRESSION (evidence, not fixed here): before D-15, a bare/unforeseen
    exception raised from ``export_document`` during the EXPORT-COMPUTATION
    stage (not the write stage) was caught by the worker's own per-target
    ``except Exception`` backstop, isolated to that one target, and the batch
    continued (the exact acceptance this file's docstring names — "a generic
    Exception (the unforeseen-type backstop)"). ``logic.export.run_batch`` now
    catches only ``ExportError``/``AtlasError``/``PixelBufferError`` per its own
    documented contract; anything else propagates OUT of ``run_batch`` and is
    NOT caught anywhere in ``Export_Worker.run()`` either (only the
    ``run_batch`` CALL itself is wrapped, in ``except ExportError``, for the
    unrelated ``MAX_BATCH_TARGETS`` case).

    Real, unmocked ``run_batch`` is exercised here (only
    ``logic.export.export_document`` is patched — the actual seam
    ``run_batch`` calls). This test asserts the OLD, still-desired acceptance
    and is EXPECTED TO FAIL against the shipped code — left failing on
    purpose (HARD RULE: a defect found is reported, never fixed here; an
    existing regression guard is never weakened to hide a real defect)."""
    real_export_document = export_document

    def _fake(document, request):
        if request.tag == "boom":
            raise RuntimeError("totally unforeseen mid-batch failure")
        return real_export_document(document, request)

    monkeypatch.setattr(export_worker, "export_document", _fake, raising=False)
    monkeypatch.setattr("pixelart_creator.logic.export.export_document", _fake)
    doc = single_frame_document()

    failed: list[tuple[int, str]] = []
    ok: list[int] = []
    export_controller.targetFailed.connect(lambda i, m: failed.append((i, m)))
    export_controller.targetSucceeded.connect(lambda i, _r: ok.append(i))

    targets = (
        _png_target(tmp_path, "a.png", tag="boom"),  # index 0 — unforeseen raise
        _png_target(tmp_path, "b.png"),  # index 1 — real, should still succeed
    )
    with qtbot.waitSignal(export_controller.batchFinished, timeout=5000):
        export_controller.submit(doc, targets)

    # The UI does not HANG (the finally block always fires) — that half of
    # D-1a survives. But continue-on-failure + per-target reporting for an
    # unforeseen exception type does not: this is the defect.
    assert export_controller.is_busy() is False

    # DESIRED (old, S2-level) acceptance — FAILS against the shipped D-15 code:
    assert ok == [1], "target 1 should still succeed despite target 0's failure"
    assert {i for i, _ in failed} == {0}, "target 0's failure should be reported"


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
    """Driving ``Export_Worker.run()`` in-thread covers every per-target branch
    against a crafted ``BatchResult``: success, two ``run_batch``-reported
    failures, a real write-stage OSError, and the ``finally`` terminal tick."""
    monkeypatch.setattr(
        export_worker,
        "run_batch",
        _crafted_run_batch(
            {_FAIL_PIXELBUFFER: "PixelBufferError: bad buffer", _FAIL_GENERIC: "boom"}
        ),
    )
    doc = single_frame_document()
    blocker = tmp_path / "afile"
    blocker.write_text("x", encoding="utf-8")
    targets = (
        _png_target(tmp_path, "ok.png"),  # 0 — succeeds
        _png_target(tmp_path, "pb.png", tag=_FAIL_PIXELBUFFER),  # 1 — run_batch failure
        _png_target(tmp_path, "boom.png", tag=_FAIL_GENERIC),  # 2 — run_batch failure
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


# --------------------------------------------------------------------------- #
# D-15 grep-gate: one implementation only (Article I)                          #
# --------------------------------------------------------------------------- #


def test_d15_no_second_per_target_loop_implementation_in_export_worker():
    """D-15 grep-gate (Article I): ``export_worker.py`` calls ``run_batch``
    exactly once and no longer imports/catches ``AtlasError`` or
    ``PixelBufferError`` itself — the compute-stage per-target loop lives in
    exactly one place, ``logic.export.run_batch``."""
    import inspect

    source = inspect.getsource(export_worker)
    assert source.count("= run_batch(") == 1  # the single consumption call site
    assert "AtlasError" not in source  # deleted per-target compute-stage catch
    assert "PixelBufferError" not in source
