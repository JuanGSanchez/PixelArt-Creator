# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Off-GUI-thread cloud execution + deterministic teardown (REQ-P10-UI-005).

A cloud ``put`` / ``get`` / ``list_versions`` / autosave against the
:class:`~pixelart_creator.data.cloud.port.CloudPort` is batch I/O (a serialised
``.pixproj`` can be hundreds of MB at 8K); running it on the GUI thread would
freeze the window. This module runs the **Qt-free** cloud port off the GUI
thread on a *window-owned* :class:`~PySide6.QtCore.QThreadPool` (never the global
pool), exactly mirroring the sanctioned Phase-7/8
:class:`~pixelart_creator.ui.export_worker.Export_Controller` /
:class:`~pixelart_creator.ui.automation_worker.Automation_Controller` pattern:

* :class:`Cloud_Worker` is a :class:`~PySide6.QtCore.QRunnable` that calls a
  caller-supplied **Qt-free job callable** off the GUI thread. It constructs
  **no** Qt object off-thread and emits result / error / done over a
  GUI-thread-affine signal carrier (auto/queued delivery). The job does only
  Qt-free port I/O (and, for an "open", the Qt-free defensive ``.pixproj``
  decode) and returns a plain, Qt-free result (a ``CloudVersion``, ``bytes``, a
  version tuple, or a reconstructed :class:`~pixelart_creator.logic.document.Document`)
  which the GUI thread consumes.
* :class:`CloudWorkerSignals` is that GUI-thread-affine carrier.
* :class:`Cloud_Controller` owns the pool + carrier + a cooperative cancel
  :class:`threading.Event` + a monotonic token, and exposes an idempotent,
  event-loop-free :meth:`Cloud_Controller.shutdown` that drains the pool and
  releases the carrier so **no worker thread or connected carrier survives into a
  later GC cycle** (the Phase-5 cross-thread GC-of-Qt-C++ segfault; do not
  reintroduce it). Wire it into ``MainWindow.shutdown_prewarm``.

There is **no ``eval`` / ``exec``** here: the worker only *calls* the port; the
open path decodes untrusted bytes through the shipped defensive PIO-1 path
(``deserialize_project`` — REQ-P10-DATA-006), never by interpreting content.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

#: A Qt-free cloud job: given the cooperative cancel event, do the port I/O off
#: the GUI thread and return a plain, Qt-free result object (a ``CloudVersion``,
#: ``bytes``, a ``Tuple[CloudVersion, ...]``, a ``Document``, or ``None`` for a
#: recovery-slot write). It must touch **no** Qt object.
CloudJob = Callable[[threading.Event], object]

#: Bounded wait for a running cloud op to finish on teardown, ms (presentation-
#: only timing, not a domain tuning value — mirrors
#: ``export_worker._EXPORT_SHUTDOWN_WAIT_MS``).
_CLOUD_SHUTDOWN_WAIT_MS = 5000


class CloudWorkerSignals(QObject):
    """GUI-thread-affine carrier for the cloud worker's signals (queued delivery).

    Every signal carries the worker's ``token`` so the controller can drop a
    stale emission from a superseded / cancelled run (the export-controller
    ``token`` precedent), plus the op ``kind`` so the GUI slot knows how to
    handle the result (``"save"`` / ``"open"`` / ``"list_versions"`` /
    ``"restore"`` / ``"autosave"``).
    """

    #: ``(token, kind, result)`` — the job produced a Qt-free result object.
    succeeded = Signal(int, str, object)
    #: ``(token, kind, message)`` — the job raised (surfaced, never a crash).
    failed = Signal(int, str, str)
    #: ``(token,)`` — the job ended (success, failure, or cancel); clears busy.
    done = Signal(int)


class Cloud_Worker(QRunnable):
    """Run one Qt-free cloud job off the GUI thread (REQ-P10-UI-005).

    The port I/O happens here; the *result* is marshalled back to the GUI thread
    over a queued signal. Cancellation is cooperative: the job receives the
    shared cancel event, and a result produced by a superseded / cancelled run is
    dropped (its ``token`` no longer matches).
    """

    def __init__(
        self,
        token: int,
        kind: str,
        job: CloudJob,
        cancel: threading.Event,
        signals: CloudWorkerSignals,
    ) -> None:
        """Capture the cloud job off-thread.

        Holds ``token``, the op ``kind``, the Qt-free ``job`` callable, the shared
        ``cancel`` event, and the GUI-thread ``signals`` carrier. Constructs no Qt
        object.
        """
        super().__init__()
        self._token = int(token)
        self._kind = str(kind)
        self._job = job
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Execute the job, emitting result / error, then the terminal ``done``.

        The terminal ``done`` signal is emitted from a ``finally`` block so it
        fires on EVERY exit path — clean completion, cancel, or any error escaping
        the job — and the controller clears its busy flag off it, so the cloud UI
        can never be stranded on "Working…" no matter what the port raises
        (REQ-P10-UI-005). A job that raises surfaces a typed message; nothing else
        happens (no partial document lands on the GUI thread).
        """
        try:
            if self._cancel.is_set():
                return
            result = self._job(self._cancel)
            if self._cancel.is_set():
                # Superseded / cancelled: discard the result (the port op either
                # completed or raised; nothing is applied to the GUI on cancel).
                return
            self._signals.succeeded.emit(self._token, self._kind, result)
        except Exception as exc:  # noqa: BLE001 - deliberate UI backstop
            # Any port error (CloudError / CloudDataError / ProjectIOError / OSError
            # / value error) surfaces as a user-facing message; it never crashes the
            # app and never re-raises through Qt.
            self._signals.failed.emit(
                self._token, self._kind, f"{type(exc).__name__}: {exc}"
            )
        finally:
            self._signals.done.emit(self._token)


class Cloud_Controller(QObject):
    """Owns the window's cloud ``QThreadPool``, cancel event, carrier + token.

    Re-emits the worker's carrier signals as its own (token-filtered) public
    signals for the cloud UI to bind to, so a superseded run's queued emissions
    never touch the current run's UI. :meth:`shutdown` is the idempotent,
    event-loop-free teardown wired into ``MainWindow.shutdown_prewarm``.
    """

    #: ``(kind, result)`` — the current run produced a Qt-free result object.
    operationSucceeded = Signal(str, object)
    #: ``(kind, message)`` — the current run failed (surfaced to the user).
    operationFailed = Signal(str, str)
    #: emitted when the current run ends (success, failure, or cancel).
    operationFinished = Signal()
    #: ``(busy,)`` — whether a cloud op is in flight (drives UI enablement).
    busyChanged = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create the window-owned single-thread pool + carrier (not the global one)."""
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Cloud ops are serial against one working document / recovery slot; one
        # worker thread keeps ordering deterministic and bounds memory (an 8K
        # serialise is large).
        self._pool.setMaxThreadCount(1)
        self._signals: Optional[CloudWorkerSignals] = CloudWorkerSignals()
        self._signals.succeeded.connect(self._on_succeeded)
        self._signals.failed.connect(self._on_failed)
        self._signals.done.connect(self._on_done)
        self._cancel = threading.Event()
        self._token = 0
        self._busy = False

    # -- queries ----------------------------------------------------------

    def is_busy(self) -> bool:
        """Return whether a cloud op is currently in flight."""
        return self._busy

    # -- submission -------------------------------------------------------

    def submit(self, kind: str, job: CloudJob) -> int:
        """Start ``job`` (tagged ``kind``) off the GUI thread; return the run token.

        Any in-flight run is cancelled first (its later emissions become stale via
        the token bump), a fresh cancel event is armed, and one worker is queued.
        Safe to ignore after :meth:`shutdown` (the carrier is gone, so this
        returns the last token without starting work).
        """
        if self._signals is None:
            return self._token
        # Supersede any in-flight run: signal it to stop; its queued emissions
        # carry the old token and are dropped by the token filter below.
        self._cancel.set()
        self._pool.clear()
        self._token += 1
        self._cancel = threading.Event()
        token = self._token
        worker = Cloud_Worker(token, kind, job, self._cancel, self._signals)
        self._set_busy(True)
        self._pool.start(worker)
        return token

    def cancel(self) -> None:
        """Cooperatively cancel the current run (checked by the job / on result)."""
        self._cancel.set()
        self._pool.clear()

    # -- teardown ---------------------------------------------------------

    def shutdown(self) -> None:
        """Deterministically tear the cloud pool + carrier down (idempotent).

        Mirrors ``Export_Controller.shutdown`` / ``Automation_Controller.shutdown``
        exactly and does NOT rely on the Qt event loop. In order it: bumps the
        token (every queued / in-flight emission becomes a no-op); sets the shared
        cancel event; drops queued runnables and **blocks** (bounded) on
        ``waitForDone`` until the running job finishes and the pool's worker
        threads are removed — so no native worker survives into a later GC cycle
        (the PySide6 cross-thread GC-of-Qt-C++ segfault); then disconnects and
        releases the GUI-thread signal carrier so any still-queued emission has no
        slot to land on. Safe to call repeatedly — from
        ``MainWindow.shutdown_prewarm`` / ``closeEvent`` and from a test teardown
        fixture.
        """
        self._token += 1
        self._cancel.set()
        self._pool.clear()
        self._pool.waitForDone(_CLOUD_SHUTDOWN_WAIT_MS)
        signals = self._signals
        if signals is not None:
            for signal, slot in (
                (signals.succeeded, self._on_succeeded),
                (signals.failed, self._on_failed),
                (signals.done, self._on_done),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    # Already disconnected / carrier already torn down — idempotent.
                    pass
            self._signals = None
        self._set_busy(False)

    # -- carrier relay (token-filtered) -----------------------------------

    @Slot(int, str, object)
    def _on_succeeded(self, token: int, kind: str, result: object) -> None:
        if token == self._token:
            # Idle-before-terminal-emit contract: by the time any consumer sees a
            # terminal signal, ``is_busy()`` is already False. Clear busy (and emit
            # ``busyChanged(False)`` for UI enablement) FIRST, then re-emit the
            # outcome. All on the GUI thread, so ordering is deterministic — no
            # cross-thread race. ``operationFinished`` still fires on the later
            # ``done`` (``_on_done``).
            self._set_busy(False)
            self.operationSucceeded.emit(kind, result)

    @Slot(int, str, str)
    def _on_failed(self, token: int, kind: str, message: str) -> None:
        if token == self._token:
            # Same idle-before-terminal-emit contract as ``_on_succeeded``.
            self._set_busy(False)
            self.operationFailed.emit(kind, message)

    @Slot(int)
    def _on_done(self, token: int) -> None:
        if token == self._token:
            # Terminal ``done`` fires on every exit path (incl. cancel, where
            # neither succeeded nor failed emitted); clearing busy here is the
            # authoritative clear for that path and an idempotent no-op after a
            # succeeded/failed already cleared it.
            self._set_busy(False)
            self.operationFinished.emit()

    # -- helpers ----------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)
