"""Automation worker / controller unit coverage (REQ-P8-UI-009/-011).

The off-thread bodies (``make_dispatch_job`` / ``make_replay_job`` job closures
and ``Automation_Worker.run``) run on a native Qt ``QThreadPool`` thread, which
coverage.py cannot trace — yet they are the marshalling seam. These tests drive
those bodies DIRECTLY on the main thread (a real signal carrier, synchronous
delivery) to assert the apply-then-revert contract, the emit-on-every-path
behaviour, cancel dropping, and the controller's token-filtered relay. Headless;
both themes.
"""

from __future__ import annotations

import threading

from pixelart_creator.ui.automation_worker import (
    Automation_Controller,
    Automation_Worker,
    AutomationWorkerSignals,
    make_dispatch_job,
    make_replay_job,
)
from tests.ui._automation_helpers import (
    arrays_equal,
    buffer_of,
    macro_of,
    procgen_op,
)


def test_dispatch_job_applies_then_reverts_leaving_document_unchanged(make_document):
    """make_dispatch_job returns an UNAPPLIED command; the live document is restored."""
    doc = make_document(64, 64)
    before = buffer_of(doc).copy()
    job = make_dispatch_job(doc, [procgen_op(seed=7)])
    command = job(threading.Event())
    # The worker leaves NO mutation behind (apply ∘ undo = identity).
    assert arrays_equal(buffer_of(doc), before)
    # …and the returned command re-applies on the GUI thread.
    command.execute()
    assert not arrays_equal(buffer_of(doc), before)


def test_replay_job_applies_then_reverts(make_document):
    """make_replay_job mirrors the dispatch job for the macro path."""
    doc = make_document(64, 64)
    before = buffer_of(doc).copy()
    job = make_replay_job(doc, macro_of(procgen_op(seed=3)))
    command = job(threading.Event())
    assert arrays_equal(buffer_of(doc), before)
    command.execute()
    assert not arrays_equal(buffer_of(doc), before)


def _capture(signals: AutomationWorkerSignals):
    got = {"finished": [], "failed": [], "done": []}
    signals.finished.connect(lambda t, c: got["finished"].append((t, c)))
    signals.failed.connect(lambda t, m: got["failed"].append((t, m)))
    signals.done.connect(lambda t: got["done"].append(t))
    return got


def test_worker_run_emits_finished_then_done_on_success(qtbot, make_document):
    """Automation_Worker.run emits finished + the terminal done on a clean run."""
    doc = make_document(64, 64)
    signals = AutomationWorkerSignals()
    got = _capture(signals)
    worker = Automation_Worker(
        7, make_dispatch_job(doc, [procgen_op(seed=1)]), threading.Event(), signals
    )
    worker.run()
    assert [t for t, _ in got["finished"]] == [7]
    assert got["done"] == [7]


def test_worker_run_skips_when_cancelled_before_start(qtbot, make_document):
    """A cancel set before run drops the result; only the terminal done fires."""
    doc = make_document(64, 64)
    signals = AutomationWorkerSignals()
    got = _capture(signals)
    cancel = threading.Event()
    cancel.set()
    worker = Automation_Worker(
        3, make_dispatch_job(doc, [procgen_op(seed=1)]), cancel, signals
    )
    worker.run()
    assert got["finished"] == []
    assert got["done"] == [3]


def test_worker_run_drops_result_when_cancelled_during_job(qtbot, make_document):
    """A run cancelled while the job runs drops the (reverted) result; done still fires."""
    doc = make_document(64, 64)
    signals = AutomationWorkerSignals()
    got = _capture(signals)
    cancel = threading.Event()

    def _job(_cancel):
        real = make_dispatch_job(doc, [procgen_op(seed=1)])
        command = real(_cancel)
        cancel.set()  # superseded mid-flight
        return command

    worker = Automation_Worker(9, _job, cancel, signals)
    worker.run()
    assert got["finished"] == []  # stale result discarded
    assert got["done"] == [9]


def test_worker_run_emits_failed_then_done_on_error(qtbot, make_document):
    """A raising job surfaces a typed failed message and still fires the terminal done."""
    doc = make_document(64, 64)
    signals = AutomationWorkerSignals()
    got = _capture(signals)

    def _boom(_cancel):
        raise ValueError("kaboom")

    worker = Automation_Worker(5, _boom, threading.Event(), signals)
    worker.run()
    assert got["failed"] and got["failed"][0][0] == 5
    assert "kaboom" in got["failed"][0][1]
    assert got["done"] == [5]


def test_controller_drops_stale_token_emissions(qtbot):
    """The controller's relay drops a superseded run's emissions (token filter)."""
    controller = Automation_Controller()
    try:
        results, fails, finished = [], [], []
        controller.resultReady.connect(results.append)
        controller.failed.connect(fails.append)
        controller.runFinished.connect(lambda: finished.append(True))

        stale = controller._token - 1  # a token that no longer matches
        controller._on_finished(stale, object())
        controller._on_failed(stale, "ignored")
        controller._on_done(stale)

        assert results == [] and fails == [] and finished == []
    finally:
        controller.shutdown()
