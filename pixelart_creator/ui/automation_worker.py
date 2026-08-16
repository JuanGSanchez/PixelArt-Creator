"""Off-GUI-thread automation execution + deterministic teardown (REQ-P8-UI-011).

A long macro replay, a large batch recolour, or a big (up to 8K) procedural
generation is slow, CPU-bound batch work; running it on the GUI thread would
freeze the window. This module runs the **Qt-free** automation engine
(:mod:`pixelart_creator.logic.scripting` / :mod:`~pixelart_creator.logic.macro`
/ :mod:`~pixelart_creator.logic.procgen` / :mod:`~pixelart_creator.logic.batch_ops`)
off the GUI thread on a *window-owned* :class:`~PySide6.QtCore.QThreadPool`
(never the global pool), exactly mirroring the sanctioned Phase-5/6/7
:class:`~pixelart_creator.ui.export_worker.Export_Controller` /
``composite_warmer`` / ``TilemapScene.shutdown_warm`` pattern:

* :class:`Automation_Worker` is a :class:`~PySide6.QtCore.QRunnable` that calls a
  caller-supplied **Qt-free job callable** off the GUI thread. It constructs
  **no** Qt object off-thread and emits result / error / done over a
  GUI-thread-affine signal carrier (auto/queued delivery).
* :class:`AutomationWorkerSignals` is that GUI-thread-affine carrier.
* :class:`Automation_Controller` owns the pool + carrier + a cooperative cancel
  :class:`threading.Event` + a monotonic token, and exposes an idempotent,
  event-loop-free :meth:`Automation_Controller.shutdown` that drains the pool and
  releases the carrier so **no worker thread or connected carrier survives into a
  later GC cycle** (the Phase-5 cross-thread GC-of-Qt-C++ segfault; do not
  reintroduce it). Wire it into ``MainWindow.shutdown_prewarm``.

**GUI-thread mutation invariant (the plan §7 / prompt directive).** The document
is a pure, Qt-free object with no Qt thread affinity, but to honour Qt model
affinity the *live* document is only ever mutated **on the GUI thread** via the
undo stack. The off-thread job therefore does the heavy computation (building the
reversible command — noise-field generation, palette remap, per-op dispatch) and
then leaves the document in its **original state** before returning: for the
``dispatch`` / ``replay`` path (which apply during construction, per the frozen
:mod:`logic.scripting` contract), the job applies then immediately reverts
(``apply ∘ undo = identity``), so the worker leaves **no** mutation behind. It
emits the resulting **unapplied** reversible
:class:`~pixelart_creator.logic.history.Command` back over a queued signal; the
GUI thread then wraps it in one ``AutomationCommand`` and pushes it onto the
active document's :class:`~PySide6.QtGui.QUndoStack`, so the actual, observable
mutation happens on the GUI thread (mirroring how export/warm marshal results via
queued signals). No :class:`~PySide6.QtCore.QObject` / Qt-C++ object is ever
constructed or touched off the GUI thread.

There is **no ``eval`` / ``exec``** here: the worker only *calls* the trusted,
allow-listed logic engine — it never interprets plugin or script *content*.

**Per-target progress (D-06, additive).** :class:`AutomationWorkerSignals` carries
one new ``progress`` signal — ``(token, target_index, target_count, stage)`` —
alongside the unchanged ``finished`` / ``failed`` / ``done`` signals;
:class:`Automation_Controller` relays it (token-filtered, exactly like the other
per-run signals) as ``targetProgress``. ``target_count`` is the number of DSL ops
the run comprises (each dispatched op is one automation "target"), known upfront
from the job's own op/macro list and carried on the job callable via
:class:`_CountedJob` — no change to the ``AutomationJob`` call contract
(``job(cancel) -> Command``), so existing direct-call test seams
(``job(threading.Event())``) are unaffected. ``stage`` is a plain, untranslated
token (``"running"`` / ``"complete"``) the consuming panel maps to a translated
label; this module has no widget context to ``tr()`` from. Because
``logic.scripting.dispatch`` / ``logic.macro.replay`` apply their whole op list as
one atomic call (by design — see their docstrings), no intra-run, per-op step is
observable from here without a progress hook threaded through those APIs (an
AGT-03 logic-layer change, out of this module's scope); this signal reports the
real, upfront-known target count at run-start (``0``/count) and run-complete
(``count``/count).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from pixelart_creator.logic import macro as macro_engine
from pixelart_creator.logic import scripting
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command
from pixelart_creator.logic.macro import Macro, Op

#: A Qt-free automation job: given the cooperative cancel event, do the heavy
#: engine work off the GUI thread and return an **unapplied** reversible
#: :class:`~pixelart_creator.logic.history.Command` (the live document is left in
#: its original state — see the module docstring). Closures over the pure
#: ``logic`` engine + the document + the DSL ops; it must touch **no** Qt object.
AutomationJob = Callable[[threading.Event], Command]

#: Bounded wait for a running automation job to finish on teardown, ms
#: (presentation-only timing, not a domain tuning value — mirrors
#: ``export_worker._EXPORT_SHUTDOWN_WAIT_MS``).
_AUTOMATION_SHUTDOWN_WAIT_MS = 5000

#: Fallback per-run target count for a job that carries no ``target_count``
#: (e.g. an ad-hoc test double) — a single, indivisible target.
_DEFAULT_TARGET_COUNT = 1

#: The ``stage`` token :attr:`AutomationWorkerSignals.progress` reports when a run
#: starts (D-06). Plain, untranslated — the consuming panel maps it to a label.
STAGE_RUNNING = "running"
#: The ``stage`` token reported when a run's job has produced its result.
STAGE_COMPLETE = "complete"


class _CountedJob:
    """Wrap an :data:`AutomationJob` with its known, upfront per-run target count.

    Preserves the exact ``job(cancel) -> Command`` call contract (D-06's addition
    is purely additive): :class:`Automation_Worker` reads ``target_count`` via
    ``getattr(..., "target_count", 1)`` before calling the job, so a plain
    function/lambda job (no such attribute, e.g. a test double) still runs
    unchanged and simply reports a single target.
    """

    __slots__ = ("_fn", "target_count")

    def __init__(self, fn: AutomationJob, target_count: int) -> None:
        """Wrap ``fn``, recording ``target_count`` (clamped to at least one)."""
        self._fn = fn
        self.target_count = max(_DEFAULT_TARGET_COUNT, int(target_count))

    def __call__(self, cancel: threading.Event) -> Command:
        """Delegate to the wrapped job, unchanged."""
        return self._fn(cancel)


def make_dispatch_job(document: Document, ops: Sequence[Op]) -> AutomationJob:
    """Build a Qt-free job that dispatches ``ops`` and leaves ``document`` unchanged.

    The heavy work — validating each op against the trusted allow-list registry
    and constructing each reversible command (noise-field generation / palette
    remap) — happens inside :func:`pixelart_creator.logic.scripting.dispatch`,
    which applies the ops in order (a later op may depend on an earlier one's
    effect). The job then immediately reverts the resulting group
    (``apply ∘ undo = identity``), so the worker returns the **unapplied** grouped
    command with the live document restored to its original state; the GUI thread
    performs the observable mutation by pushing it onto the undo stack. Any
    ``ScriptError`` propagates and is surfaced as a user-facing error (no mutation
    lands on the undo stack). There is **no ``eval``/``exec``** — ops are data.
    """
    op_list = list(ops)

    def job(_cancel: threading.Event) -> Command:
        command = scripting.dispatch(document, op_list)
        command.undo()
        return command

    return _CountedJob(job, len(op_list))


def make_replay_job(document: Document, macro: Macro) -> AutomationJob:
    """Build a Qt-free job that replays ``macro`` and leaves ``document`` unchanged.

    Mirrors :func:`make_dispatch_job` for the macro path: replay runs through the
    one trusted dispatcher (deterministic, REQ-P8-LOGIC-005), and the resulting
    grouped command is reverted so the worker leaves no mutation behind; the GUI
    thread applies it via the undo stack (one undoable replay — REQ-P8-UI-002).
    """

    def job(_cancel: threading.Event) -> Command:
        command = macro_engine.replay(document, macro)
        command.undo()
        return command

    return _CountedJob(job, len(macro.ops))


class AutomationWorkerSignals(QObject):
    """GUI-thread-affine carrier for the automation worker's signals (queued).

    Every signal carries the worker's ``token`` so the controller can drop a
    stale emission from a superseded / cancelled run (the export-controller
    ``token`` precedent).
    """

    #: ``(token, Command)`` — the job produced an unapplied reversible command.
    finished = Signal(int, object)
    #: ``(token, message)`` — the job raised (surfaced to the user, never a crash).
    failed = Signal(int, str)
    #: ``(token,)`` — the job ended (success, failure, or cancel); clears busy.
    done = Signal(int)
    #: ``(token, target_index, target_count, stage)`` — per-target progress (D-06,
    #: additive). See the module docstring for what ``target_count``/``stage``
    #: mean and why no intra-run step is reported.
    progress = Signal(int, int, int, str)


class Automation_Worker(QRunnable):
    """Run one Qt-free automation job off the GUI thread (REQ-P8-UI-011).

    The heavy engine work happens here; the *result* (an unapplied reversible
    command) is marshalled back to the GUI thread, which performs the actual
    document mutation via the undo stack. Cancellation is cooperative: the job
    receives the shared cancel event, and a result produced by a superseded /
    cancelled run is dropped (its ``token`` no longer matches).
    """

    def __init__(
        self,
        token: int,
        job: AutomationJob,
        cancel: threading.Event,
        signals: AutomationWorkerSignals,
    ) -> None:
        """Capture the automation job off-thread.

        Holds ``token``, the Qt-free ``job`` callable, the shared ``cancel`` event,
        and the GUI-thread ``signals`` carrier. Constructs no Qt object.
        """
        super().__init__()
        self._token = int(token)
        self._job = job
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Execute the job, emitting result / error, then the terminal ``done``.

        The terminal ``done`` signal is emitted from a ``finally`` block so it
        fires on EVERY exit path — clean completion, cancel, or any error escaping
        the job — and the controller clears its busy flag off it, so the
        automation UI can never be stranded on "Running…" no matter what the
        engine raises (REQ-P8-UI-008/-011). A job that raises surfaces a typed
        message; because a failed ``dispatch`` leaves no returned command, nothing
        is pushed to the undo stack (the document is uncorrupted from the GUI's
        perspective — no automation edit landed).

        Also emits the per-target ``progress`` signal (D-06, additive) at run-start
        (``0``/``target_count``, :data:`STAGE_RUNNING`) and, on a clean result, at
        run-complete (``target_count``/``target_count``, :data:`STAGE_COMPLETE`).
        ``target_count`` comes from the job's own ``target_count`` attribute
        (``getattr(..., "target_count", 1)``) — see :class:`_CountedJob`.
        """
        total = max(
            _DEFAULT_TARGET_COUNT,
            int(getattr(self._job, "target_count", _DEFAULT_TARGET_COUNT)),
        )
        try:
            if self._cancel.is_set():
                return
            self._signals.progress.emit(self._token, 0, total, STAGE_RUNNING)
            result = self._job(self._cancel)
            if self._cancel.is_set():
                # Superseded / cancelled: the job restored the document to its
                # original state (apply ∘ undo = identity), so discarding the
                # result leaks no mutation.
                return
            self._signals.progress.emit(self._token, total, total, STAGE_COMPLETE)
            self._signals.finished.emit(self._token, result)
        except Exception as exc:  # noqa: BLE001 - deliberate UI backstop
            # Any engine error (ScriptError / MacroError / ProcgenError /
            # BatchError / PluginError / value error) surfaces as a user-facing
            # message; it never crashes the app and never re-raises through Qt.
            self._signals.failed.emit(self._token, f"{type(exc).__name__}: {exc}")
        finally:
            self._signals.done.emit(self._token)


class Automation_Controller(QObject):
    """Owns the window's automation ``QThreadPool``, cancel event, carrier + token.

    Re-emits the worker's carrier signals as its own (token-filtered) public
    signals for the automation UI to bind to, so a superseded run's queued
    emissions never touch the current run's UI. :meth:`shutdown` is the
    idempotent, event-loop-free teardown wired into
    ``MainWindow.shutdown_prewarm``.
    """

    #: ``(Command,)`` — the current run produced an unapplied reversible command
    #: (the GUI thread wraps + pushes it onto the undo stack).
    resultReady = Signal(object)
    #: ``(message,)`` — the current run failed (surfaced to the user).
    failed = Signal(str)
    #: emitted when the current run ends (success, failure, or cancel).
    runFinished = Signal()
    #: ``(busy,)`` — whether an automation run is in flight (drives UI enablement).
    busyChanged = Signal(bool)
    #: ``(target_index, target_count, stage)`` — token-filtered relay of the
    #: current run's per-target progress (D-06, additive); a superseded run's
    #: progress is dropped like every other per-run signal here.
    targetProgress = Signal(int, int, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create the window-owned single-thread pool + carrier (not the global one)."""
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Automation is serial (one live document, ordered undo stack); one worker
        # thread keeps runs deterministic and bounds memory (an 8K procgen field).
        self._pool.setMaxThreadCount(1)
        self._signals: Optional[AutomationWorkerSignals] = AutomationWorkerSignals()
        self._signals.finished.connect(self._on_finished)
        self._signals.failed.connect(self._on_failed)
        self._signals.done.connect(self._on_done)
        self._signals.progress.connect(self._on_progress)
        self._cancel = threading.Event()
        self._token = 0
        self._busy = False

    # -- queries ----------------------------------------------------------

    def is_busy(self) -> bool:
        """Return whether an automation run is currently in flight."""
        return self._busy

    # -- submission -------------------------------------------------------

    def submit(self, job: AutomationJob) -> int:
        """Start ``job`` off the GUI thread; return the run token.

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
        worker = Automation_Worker(token, job, self._cancel, self._signals)
        self._set_busy(True)
        self._pool.start(worker)
        return token

    def cancel(self) -> None:
        """Cooperatively cancel the current run (checked by the job / on result)."""
        self._cancel.set()
        self._pool.clear()

    # -- teardown ---------------------------------------------------------

    def shutdown(self) -> None:
        """Deterministically tear the automation pool + carrier down (idempotent).

        Mirrors ``Export_Controller.shutdown`` / ``TilemapScene.shutdown_warm``
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
        self._pool.waitForDone(_AUTOMATION_SHUTDOWN_WAIT_MS)
        signals = self._signals
        if signals is not None:
            for signal, slot in (
                (signals.finished, self._on_finished),
                (signals.failed, self._on_failed),
                (signals.done, self._on_done),
                (signals.progress, self._on_progress),
            ):
                try:
                    signal.disconnect(slot)
                except (RuntimeError, TypeError):
                    # Already disconnected / carrier already torn down — idempotent.
                    pass
            self._signals = None
        self._set_busy(False)

    # -- carrier relay (token-filtered) -----------------------------------

    @Slot(int, object)
    def _on_finished(self, token: int, command: object) -> None:
        if token == self._token:
            self.resultReady.emit(command)

    @Slot(int, str)
    def _on_failed(self, token: int, message: str) -> None:
        if token == self._token:
            self.failed.emit(message)

    @Slot(int)
    def _on_done(self, token: int) -> None:
        if token == self._token:
            self._set_busy(False)
            self.runFinished.emit()

    @Slot(int, int, int, str)
    def _on_progress(self, token: int, index: int, count: int, stage: str) -> None:
        if token == self._token:
            self.targetProgress.emit(index, count, stage)

    # -- helpers ----------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)
