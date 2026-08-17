"""Off-GUI-thread export execution + deterministic teardown (REQ-P7-UI-010).

Exporting a large (up to 8K) document or a big batch is a slow, batch-IO
operation; running it on the GUI thread would freeze the window. This module
runs the **Qt-free** export engine off the GUI thread on a *window-owned*
``QThreadPool`` (never the global pool), exactly mirroring the sanctioned
Phase-5 :mod:`pixelart_creator.ui.composite_warmer` /
:meth:`pixelart_creator.ui.tilemap_canvas.TilemapScene.shutdown_warm` pattern:

* :class:`Export_Worker` is a :class:`~PySide6.QtCore.QRunnable` that calls the
  Qt-free :func:`~pixelart_creator.logic.export.export_document` +
  :func:`~pixelart_creator.data.export_io.write_export` /
  :func:`~pixelart_creator.data.export_io.write_engine_preset` off the GUI
  thread. It constructs **no** Qt object off-thread and emits progress / result
  / error over a GUI-thread-affine signal carrier (auto/queued delivery).
* :class:`ExportWorkerSignals` is that GUI-thread-affine carrier.
* :class:`Export_Controller` owns the pool + carrier + a cooperative
  cancel :class:`threading.Event` + a monotonic token, and exposes an
  idempotent, event-loop-free :meth:`Export_Controller.shutdown` that drains
  the pool and releases the carrier so **no worker thread or connected carrier
  survives into a later GC cycle** (the Phase-5 cross-thread GC-of-Qt-C++
  segfault; do not reintroduce it). Wire it into ``MainWindow.shutdown_prewarm``.

**Continue-on-failure (D-15).** ``logic.export.run_batch`` now performs the
continue-on-failure loop itself (REQ-P7-UI-005 / REQ-P7-LOGIC-010) and returns
a deterministic-order :class:`~pixelart_creator.logic.export.BatchResult`. The
worker CONSUMES it — it builds the ``ExportRequest`` sequence, calls
``run_batch(document, requests)`` once, then iterates the returned
:class:`~pixelart_creator.logic.export.BatchResult.targets` in order, emitting
:attr:`ExportWorkerSignals.targetSucceeded` / :attr:`ExportWorkerSignals.targetFailed`
per :class:`~pixelart_creator.logic.export.BatchTargetResult.success`. This is
the single batch-loop implementation (Article I); the worker's own per-target
``try``/``except`` loop is gone. ``run_batch`` only builds bytes in memory —
it never touches the filesystem — so ``write_export`` / ``write_engine_preset``
stay in the worker, called only on the success branch, once per succeeding
target. Single exports go through the identical one-target-batch path, so the
GUI export is byte-identical to the CLI export (REQ-P7-UI-007): both call the
same ``export_document`` (via ``run_batch``) + ``write_export`` engine, with no
UI-side transformation.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from pixelart_creator.data.export_io import (
    ExportWriteError,
    write_engine_preset,
    write_export,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportError,
    ExportRequest,
    run_batch,
)

#: Bounded wait for a running export to finish on teardown, ms (presentation-only
#: timing, not a domain tuning value — mirrors ``_WARM_SHUTDOWN_WAIT_MS``).
_EXPORT_SHUTDOWN_WAIT_MS = 5000


@dataclass(frozen=True)
class ExportTarget:
    """One export unit: a frozen :class:`ExportRequest` + its destination path.

    ``label`` is a display string for the batch UI (already ``tr()``-built by the
    caller); it is presentation-only and never affects the exported bytes.
    """

    request: ExportRequest
    out_path: str
    label: str = ""


class ExportWorkerSignals(QObject):
    """GUI-thread-affine carrier for the export worker's signals (queued delivery).

    Every signal carries the worker's ``token`` so the controller can drop a
    stale emission from a superseded / cancelled run (the composite-warmer
    ``token`` precedent).
    """

    #: ``(token, done, total, label)`` — a target is about to run.
    progress = Signal(int, int, int, str)
    #: ``(token, index, ExportResult)`` — a target finished successfully.
    targetSucceeded = Signal(int, int, object)
    #: ``(token, index, message)`` — a target failed (batch continues).
    targetFailed = Signal(int, int, str)
    #: ``(token,)`` — the whole run finished (all targets done, or cancelled).
    batchFinished = Signal(int)


class Export_Worker(QRunnable):
    """Run a sequence of export targets off the GUI thread (REQ-P7-UI-010).

    Continue-on-failure: a failing target emits ``targetFailed`` and the run
    proceeds to the next target (never a ``logic.run_batch`` raise). Cancellation
    is cooperative and checked *between* targets (export is batch IO, not the
    per-frame render loop, so there is no sub-target interrupt point).
    """

    def __init__(
        self,
        token: int,
        document: Document,
        targets: Sequence[ExportTarget],
        cancel: threading.Event,
        signals: ExportWorkerSignals,
    ) -> None:
        """Capture the export job off-thread.

        Holds ``token``, the source ``document`` (read-only, so the flatten is
        non-destructive and safe off-thread — the composite-warmer precedent), the
        ordered ``targets``, the shared ``cancel`` event, and the GUI-thread
        ``signals`` carrier.
        """
        super().__init__()
        self._token = int(token)
        self._document = document
        self._targets: Tuple[ExportTarget, ...] = tuple(targets)
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Run the batch via ``logic.export.run_batch``, then write the successes.

        ``run_batch`` performs the continue-on-failure loop and returns a
        :class:`~pixelart_creator.logic.export.BatchResult` whose ``targets`` are in
        the original, deterministic request order. This worker does not
        re-implement that loop: it calls ``run_batch`` once, then walks the
        returned targets, writing bytes to disk only for the ones that
        succeeded. A write-stage failure (``ExportWriteError``/``OSError``) is
        still reported as a per-target failure and does not abort the rest of
        the batch. The terminal signal (``batchFinished`` + the full-progress
        tick) is emitted from a ``finally`` block so it fires on EVERY exit
        path — clean completion, cancel, or an unforeseen error escaping the
        per-target write guard. The controller clears its busy flag off that
        terminal signal, so the export UI can never be stranded on
        "Exporting…" no matter what a target does (REQ-P7-UI-008/-010).

        Cancellation is cooperative: it is checked between targets, both before
        dispatching a progress tick and before writing a successful result to
        disk, since ``run_batch`` itself has no cooperative interrupt point.
        """
        total = len(self._targets)
        try:
            requests = [target.request for target in self._targets]
            try:
                batch_result = run_batch(self._document, requests)
            except ExportError as exc:
                # ``run_batch`` raises only when ``requests`` itself is too large
                # (MAX_BATCH_TARGETS); every target is reported failed with the
                # same message rather than stranding the UI with no signal at all.
                for index in range(total):
                    self._signals.progress.emit(self._token, index, total, "")
                    self._signals.targetFailed.emit(self._token, index, str(exc))
                return
            for index, target in enumerate(self._targets):
                if self._cancel.is_set():
                    break
                self._signals.progress.emit(self._token, index, total, target.label)
                target_result = batch_result.targets[index]
                if not target_result.success:
                    # CONTINUE-ON-FAILURE (D-15): report the failure captured by
                    # ``run_batch`` and move on; one bad target never aborts the
                    # rest or crashes the app (REQ-P7-UI-005/-008).
                    self._signals.targetFailed.emit(
                        self._token, index, str(target_result.error)
                    )
                    continue
                result = target_result.result
                assert result is not None  # success implies result is set
                try:
                    write_export(result, target.out_path)
                    preset = target.request.preset
                    if preset is not EnginePreset.NONE and result.metadata is not None:
                        write_engine_preset(preset, result.metadata, target.out_path)
                except (ExportWriteError, OSError) as exc:
                    # A successful export can still fail to WRITE (disk full,
                    # permissions, …); that too is a per-target failure, not a
                    # batch abort (REQ-P7-UI-005/-008).
                    self._signals.targetFailed.emit(self._token, index, str(exc))
                    continue
                except Exception as exc:  # noqa: BLE001 - deliberate UI backstop
                    # SAFETY NET: an unforeseen error type must STILL not strand the UI
                    # on "Exporting…". Surface it to the user (never silently swallow)
                    # with its type prefixed for diagnosis, then continue like any other
                    # per-target failure (REQ-P7-UI-005/-008).
                    self._signals.targetFailed.emit(
                        self._token, index, f"{type(exc).__name__}: {exc}"
                    )
                    continue
                self._signals.targetSucceeded.emit(self._token, index, result)
        finally:
            # TERMINAL SIGNAL ALWAYS FIRES (even on a signal-emit failure or cancel):
            # the full-progress tick lets a determinate bar reach 100%, and
            # ``batchFinished`` drives the controller to clear busy → the UI returns to
            # idle. This is the guarantee that "Exporting…" can never hang forever.
            self._signals.progress.emit(self._token, total, total, "")
            self._signals.batchFinished.emit(self._token)


class Export_Controller(QObject):
    """Owns the window's export ``QThreadPool``, cancel event, carrier + token.

    Re-emits the worker's carrier signals as its own (token-filtered) public
    signals for the export UI to bind to, so a superseded run's queued emissions
    never touch the current run's UI. :meth:`shutdown` is the idempotent,
    event-loop-free teardown wired into ``MainWindow.shutdown_prewarm``.
    """

    #: ``(done, total, label)`` — current-run progress.
    progress = Signal(int, int, str)
    #: ``(index, ExportResult)`` — a current-run target succeeded.
    targetSucceeded = Signal(int, object)
    #: ``(index, message)`` — a current-run target failed (run continues).
    targetFailed = Signal(int, str)
    #: emitted when the current run finishes (or is cancelled).
    batchFinished = Signal()
    #: ``(busy,)`` — whether an export run is in flight (drives UI enablement).
    busyChanged = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create the window-owned single-thread pool + carrier (not the global one)."""
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Export is a serial, ordered pipeline; one worker thread keeps target
        # order deterministic and bounds memory (a batch of 8K flattens).
        self._pool.setMaxThreadCount(1)
        self._signals: Optional[ExportWorkerSignals] = ExportWorkerSignals()
        self._signals.progress.connect(self._on_progress)
        self._signals.targetSucceeded.connect(self._on_target_succeeded)
        self._signals.targetFailed.connect(self._on_target_failed)
        self._signals.batchFinished.connect(self._on_batch_finished)
        self._cancel = threading.Event()
        self._token = 0
        self._busy = False

    # -- queries ----------------------------------------------------------

    def is_busy(self) -> bool:
        """Return whether an export run is currently in flight."""
        return self._busy

    # -- submission -------------------------------------------------------

    def submit(self, document: Document, targets: Sequence[ExportTarget]) -> int:
        """Start exporting ``targets`` off the GUI thread; return the run token.

        Any in-flight run is cancelled first (its later emissions become stale via
        the token bump), a fresh cancel event is armed, and one worker is queued.
        A no-target submit is a no-op. Safe to ignore after :meth:`shutdown`
        (the carrier is gone, so this returns the last token without starting work).
        """
        if self._signals is None or not targets:
            return self._token
        # Supersede any in-flight run: signal it to stop; its queued emissions carry
        # the old token and are dropped by the token filter below.
        self._cancel.set()
        self._pool.clear()
        self._token += 1
        self._cancel = threading.Event()
        token = self._token
        worker = Export_Worker(token, document, targets, self._cancel, self._signals)
        self._set_busy(True)
        self._pool.start(worker)
        return token

    def cancel(self) -> None:
        """Cooperatively cancel the current run (checked between targets)."""
        self._cancel.set()
        self._pool.clear()

    # -- teardown ---------------------------------------------------------

    def shutdown(self) -> None:
        """Deterministically tear the export pool + carrier down (idempotent).

        Mirrors ``TilemapScene.shutdown_warm`` / ``CanvasScene.shutdown_prewarm``
        exactly and does NOT rely on the Qt event loop. In order it: bumps the
        token (every queued / in-flight emission becomes a no-op); sets the shared
        cancel event (best-effort early exit between targets); drops queued
        runnables and **blocks** (bounded) on ``waitForDone`` until the running
        export finishes and the pool's worker threads are removed — so no native
        worker survives into a later GC cycle (the PySide6 cross-thread
        GC-of-Qt-C++ segfault); then disconnects and releases the GUI-thread
        signal carrier so any still-queued emission has no slot to land on. Safe
        to call repeatedly — from ``MainWindow.shutdown_prewarm`` / ``closeEvent``
        and from a test teardown fixture.
        """
        self._token += 1
        self._cancel.set()
        self._pool.clear()
        self._pool.waitForDone(_EXPORT_SHUTDOWN_WAIT_MS)
        signals = self._signals
        if signals is not None:
            for signal, slot in (
                (signals.progress, self._on_progress),
                (signals.targetSucceeded, self._on_target_succeeded),
                (signals.targetFailed, self._on_target_failed),
                (signals.batchFinished, self._on_batch_finished),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    # Already disconnected / carrier already torn down — idempotent.
                    pass
            self._signals = None
        self._set_busy(False)

    # -- carrier relay (token-filtered) -----------------------------------

    @Slot(int, int, int, str)
    def _on_progress(self, token: int, done: int, total: int, label: str) -> None:
        if token == self._token:
            self.progress.emit(done, total, label)

    @Slot(int, int, object)
    def _on_target_succeeded(self, token: int, index: int, result: object) -> None:
        if token == self._token:
            self.targetSucceeded.emit(index, result)

    @Slot(int, int, str)
    def _on_target_failed(self, token: int, index: int, message: str) -> None:
        if token == self._token:
            self.targetFailed.emit(index, message)

    @Slot(int)
    def _on_batch_finished(self, token: int) -> None:
        if token == self._token:
            self._set_busy(False)
            self.batchFinished.emit()

    # -- helpers ----------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)
