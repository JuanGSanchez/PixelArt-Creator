"""Qt-free cloud job builders + worker unit paths (REQ-P10-UI-001/-005).

The job builders (``make_save_job`` / ``make_open_job`` / ``make_latest_open_job``
/ ``make_list_versions_job`` / ``make_restore_job`` / ``make_autosave_job``) and
``Cloud_Worker.run`` execute OFF the GUI thread in production, so they are
exercised here **synchronously on the main thread** (the seam is a plain callable)
to verify their contract deterministically and to cover the success / cancel /
error / finally paths that a threaded run hides from coverage. Headless, both
themes via the autouse fixture (these are thread-free and theme-invariant).
"""

from __future__ import annotations

import threading

from pixelart_creator.data.cloud import (
    CloudError,
    FakeCloudAdapter,
    deserialize_project,
    serialize_project,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.version_history import CloudVersion
from pixelart_creator.ui.cloud_actions import (
    make_autosave_job,
    make_latest_open_job,
    make_list_versions_job,
    make_open_job,
    make_restore_job,
    make_save_job,
)
from pixelart_creator.ui.cloud_worker import (
    Cloud_Controller,
    Cloud_Worker,
    CloudWorkerSignals,
)

STARTER = [(0, 0, 0, 255), (255, 255, 255, 255), (230, 30, 30, 255)]


def _doc(w: int = 12, h: int = 12) -> Document:
    return Document(w, h, palette=Palette(STARTER))


def _connected_port() -> FakeCloudAdapter:
    return FakeCloudAdapter(connected=True)


def _no_cancel() -> threading.Event:
    return threading.Event()  # never set -> not cancelled


# -- job builders (run the closure directly on the main thread) ----------------


def test_save_job_serialises_and_puts_a_version():
    """make_save_job stores a new version and returns its CloudVersion."""
    port = _connected_port()
    version = make_save_job(port, "p", _doc())(_no_cancel())
    assert isinstance(version, CloudVersion)
    assert len(port.list_versions("p")) == 1


def test_open_job_fetches_and_defensively_decodes():
    """make_open_job fetches a version's bytes and decodes an equivalent Document."""
    port = _connected_port()
    doc = _doc(10, 10)
    version = port.put("p", serialize_project(doc))
    opened = make_open_job(port, "p", version.version_id)(_no_cancel())
    assert isinstance(opened, Document)
    assert (opened.width, opened.height) == (10, 10)


def test_latest_open_job_opens_the_newest_version():
    """make_latest_open_job opens the latest stored version."""
    port = _connected_port()
    port.put("p", serialize_project(_doc(8, 8)))
    port.put("p", serialize_project(_doc(9, 9)))
    opened = make_latest_open_job(port, "p")(_no_cancel())
    assert (opened.width, opened.height) == (9, 9)  # newest wins


def test_list_versions_job_returns_ordered_history():
    """make_list_versions_job returns the ordered version tuple."""
    port = _connected_port()
    port.put("p", serialize_project(_doc()))
    port.put("p", serialize_project(_doc()))
    versions = make_list_versions_job(port, "p")(_no_cancel())
    assert [v.ordinal for v in versions] == [0, 1]


def test_restore_job_matches_open_job_decode():
    """make_restore_job decodes a specific prior version (same discipline as open)."""
    port = _connected_port()
    v = port.put("p", serialize_project(_doc(7, 7)))
    restored = make_restore_job(port, "p", v.version_id)(_no_cancel())
    assert (restored.width, restored.height) == (7, 7)


def test_autosave_job_writes_recovery_slot_and_returns_none():
    """make_autosave_job writes the recovery slot (distinct from history) -> None."""
    port = _connected_port()
    result = make_autosave_job(port, "p", _doc())(_no_cancel())
    assert result is None
    assert port.get_recovery("p") is not None
    assert port.list_versions("p") == ()  # no version created by autosave


# -- Cloud_Worker.run paths (synchronous) --------------------------------------


def _run_worker(kind, job, cancel):
    """Run one worker synchronously, collecting its carrier emissions."""
    signals = CloudWorkerSignals()
    got = {"succeeded": [], "failed": [], "done": []}
    signals.succeeded.connect(lambda t, k, r: got["succeeded"].append((k, r)))
    signals.failed.connect(lambda t, k, m: got["failed"].append((k, m)))
    signals.done.connect(lambda t: got["done"].append(t))
    Cloud_Worker(1, kind, job, cancel, signals).run()
    return got


def test_worker_success_emits_succeeded_then_done():
    """A clean job emits succeeded and the terminal done."""
    got = _run_worker("save", lambda _c: "RESULT", _no_cancel())
    assert got["succeeded"] == [("save", "RESULT")]
    assert got["done"] == [1]
    assert got["failed"] == []


def test_worker_cancel_before_run_skips_job_but_still_done():
    """A pre-set cancel skips the job entirely but still fires done (finally)."""
    cancel = threading.Event()
    cancel.set()
    ran = []
    got = _run_worker("save", lambda _c: ran.append(True), cancel)
    assert ran == []  # job body never executed
    assert got["succeeded"] == []
    assert got["done"] == [1]


def test_worker_cancel_after_run_discards_result_but_done_fires():
    """A cancel raised during the job discards the result; done still fires."""
    cancel = threading.Event()

    def job(_c):
        cancel.set()  # superseded while running
        return "STALE"

    got = _run_worker("open", job, cancel)
    assert got["succeeded"] == []  # result discarded
    assert got["done"] == [1]


def test_worker_error_emits_failed_then_done():
    """A raising job emits failed with a typed message, then done (never a crash)."""

    def job(_c):
        raise CloudError("kaboom")

    got = _run_worker("save", job, _no_cancel())
    assert got["failed"] and "kaboom" in got["failed"][0][1]
    assert "CloudError" in got["failed"][0][1]
    assert got["done"] == [1]


# -- Cloud_Controller edge paths -----------------------------------------------


def test_controller_stale_token_emission_is_dropped(qtbot):
    """A superseded run's emission (old token) is filtered out by the controller."""
    controller = Cloud_Controller()
    try:
        seen = []
        controller.operationSucceeded.connect(lambda k, r: seen.append((k, r)))
        # Simulate a stale carrier emission carrying an old token.
        controller._token = 5
        controller._on_succeeded(4, "save", "old")  # stale -> dropped
        controller._on_succeeded(5, "save", "cur")  # current -> relayed
        assert seen == [("save", "cur")]
    finally:
        controller.shutdown()


def test_controller_cancel_clears_pending(qtbot):
    """cancel() sets the cooperative event and clears the pool (no crash)."""
    controller = Cloud_Controller()
    try:
        controller.cancel()  # nothing in flight -> safe no-op
        assert controller.is_busy() is False
    finally:
        controller.shutdown()


def test_controller_submit_after_shutdown_is_noop(qtbot):
    """After shutdown the carrier is gone; submit returns the last token, no work."""
    port = _connected_port()
    controller = Cloud_Controller()
    controller.shutdown()
    before = controller._token
    returned = controller.submit("save", make_save_job(port, "p", _doc()))
    assert returned == before
    assert port.list_versions("p") == ()  # nothing ran
