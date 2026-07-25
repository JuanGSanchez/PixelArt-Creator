"""Off-GUI-thread AI-assistant turn execution + tiered-confirm marshalling.

Phase-14 Slice 14E (REQ-P14-UI-004; DEP-5). A single agentic turn
(:func:`~pixelart_creator.logic.assistant.run_turn`) interleaves **network** LLM
round-trips (``ChatBackend.respond``) with **CPU** DSL dispatch; running it on the GUI
thread would freeze the 16 ms render loop. This module runs the **Qt-free** loop off
the GUI thread on a *window-owned* :class:`~PySide6.QtCore.QThreadPool` (never the
global pool), mirroring the sanctioned Phase-8/10
:class:`~pixelart_creator.ui.automation_worker.Automation_Controller` /
:class:`~pixelart_creator.ui.cloud_worker.Cloud_Controller` pattern:

* :class:`Assistant_Worker` is a :class:`~PySide6.QtCore.QRunnable` that runs one
  caller-supplied **Qt-free job** off the GUI thread. It constructs **no** Qt object
  off-thread and emits result / error / done over a GUI-thread-affine signal carrier.
* :class:`AssistantWorkerSignals` is that GUI-thread-affine carrier.
* :class:`Assistant_Controller` owns the pool + carrier + a cooperative cancel
  :class:`threading.Event` + a monotonic token, builds the loop job, and marshals the
  **tiered-safety confirmation** across the worker/GUI boundary. Its idempotent,
  event-loop-free :meth:`Assistant_Controller.shutdown` drains the pool and releases
  the carrier so **no worker thread or connected carrier survives into a later GC
  cycle** (the recurring PySide6 cross-thread GC-of-Qt-C++ xdist segfault). Fold it
  into ``MainWindow.shutdown_prewarm``.

**GUI-thread mutation invariant (plan §7 precedent).** The live document is only ever
mutated on the GUI thread via the undo stack. The off-thread job runs the whole turn
against the live document (the heavy per-op dispatch happens here), then — mirroring
``automation_worker.make_dispatch_job`` — **reverts** every applied command in reverse
order (``apply ∘ undo = identity``) so the worker leaves the document byte-identical,
and returns the ordered **unapplied** commands. The GUI thread wraps them in one
:class:`~pixelart_creator.ui.commands.AssistantCommand` and pushes it, so the
observable mutation is strictly GUI-thread.

**Error-path atomicity (ADR-0041 §1 amendment).** A turn is atomic on failure too. If
the loop applies ≥1 reversible command and *then* fails mid-turn (a bound breach, a
transcript overflow, or an ``LLMError`` from the backend), ``run_turn`` does NOT
auto-revert — it raises an
:class:`~pixelart_creator.logic.assistant.AssistantError` exposing the ordered
already-applied commands via
:attr:`~pixelart_creator.logic.assistant.AssistantError.applied_commands`. The worker
job **reverts those commands in reverse** so the live document is left byte-identical,
then re-raises the underlying cause (``exc.__cause__`` when present, e.g. the
``LLMError``) so the dock surfaces a meaningful message. Nothing is recorded as an undo
step and the GUI thread NEVER receives a partial ``AssistantCommand`` on error — a
failed turn is observationally a no-op on the document.

**Tiered-confirm marshalling (the critical boundary, REQ-P14-LOGIC-004/-UI-003).** The
loop runs on the worker thread, but a **destructive** tool-call's
:class:`~pixelart_creator.logic.assistant.ConfirmationRequest` must be answered by a
**GUI-thread** dialog. The injected confirm callback (invoked on the worker thread)
emits :attr:`AssistantWorkerSignals.confirmRequested` over the queued carrier and then
**blocks the worker** on a :class:`threading.Event` until the GUI thread calls
:meth:`Assistant_Controller.provide_confirmation`. It **defaults to deny**: a dismissed
dialog, a cancel, or teardown all release the wait returning ``False``, so a
destructive action is **never** auto-approved. Reversible ops auto-run in the loop and
never raise a confirmation (no dialog).

There is **no ``eval`` / ``exec``** here: the worker only *calls* the trusted logic
loop; model output is data mapped onto the allow-listed dispatch (Article VII).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Tuple

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from pixelart_creator.logic.assistant import (
    AssistantError,
    ChatBackend,
    ConfirmationRequest,
    Conversation,
    Message,
    ToolDescriptor,
    run_turn,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.history import Command

__all__ = [
    "TurnOutcome",
    "AssistantWorkerSignals",
    "Assistant_Worker",
    "Assistant_Controller",
]

#: Bounded wait for a running assistant turn to finish on teardown, ms (presentation-
#: only timing, not a domain tuning value — mirrors
#: ``automation_worker._AUTOMATION_SHUTDOWN_WAIT_MS``).
_ASSISTANT_SHUTDOWN_WAIT_MS = 5000

#: A Qt-free assistant job: given the cancel event + the confirm callback, run one
#: bounded turn off the GUI thread and return its :class:`TurnOutcome` (the live
#: document left byte-identical — see the module docstring). Touches no Qt object.
AssistantJob = Callable[
    [threading.Event, Callable[[ConfirmationRequest], bool]], "TurnOutcome"
]


@dataclass(frozen=True)
class TurnOutcome:
    """The Qt-free result of one bounded turn, marshalled back to the GUI thread.

    Carries the full updated :attr:`conversation` transcript (for rendering), the
    terminating assistant :attr:`reply`, and the turn's ordered **unapplied**
    :attr:`commands` (reverted by the worker; the GUI thread re-applies them as one
    :class:`~pixelart_creator.ui.commands.AssistantCommand`). A chat-only turn has an
    empty :attr:`commands`.
    """

    conversation: Conversation
    reply: Message
    commands: Tuple[Command, ...] = field(default_factory=tuple)


class AssistantWorkerSignals(QObject):
    """GUI-thread-affine carrier for the assistant worker's signals (queued delivery).

    Every signal carries the worker's ``token`` so the controller can drop a stale
    emission from a superseded / cancelled run (the export-controller ``token``
    precedent).
    """

    #: ``(token, ConfirmationRequest)`` — a destructive tool-call needs GUI-thread
    #: approval; the controller re-emits it for the dock's confirm dialog.
    confirmRequested = Signal(int, object)
    #: ``(token, TurnOutcome)`` — the turn produced a result (transcript + commands).
    succeeded = Signal(int, object)
    #: ``(token, message)`` — the turn raised (surfaced to the user, never a crash).
    failed = Signal(int, str)
    #: ``(token,)`` — the turn ended (success, failure, or cancel); clears busy.
    done = Signal(int)


class Assistant_Worker(QRunnable):
    """Run one Qt-free assistant turn off the GUI thread (REQ-P14-UI-004).

    The network + dispatch work happens here; the *result* (a :class:`TurnOutcome`
    with the live document left byte-identical) is marshalled back to the GUI thread,
    which performs the actual undoable mutation. Cancellation is cooperative: the job
    receives the shared cancel event, and a result produced by a superseded /
    cancelled run is dropped (its ``token`` no longer matches).
    """

    def __init__(
        self,
        token: int,
        job: AssistantJob,
        confirm: Callable[[ConfirmationRequest], bool],
        cancel: threading.Event,
        signals: AssistantWorkerSignals,
    ) -> None:
        """Capture the assistant job + the marshalling confirm callback off-thread."""
        super().__init__()
        self._token = int(token)
        self._job = job
        self._confirm = confirm
        self._cancel = cancel
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 (QRunnable override)
        """Execute the turn, emitting result / error, then the terminal ``done``.

        The terminal ``done`` fires from a ``finally`` on EVERY exit path — clean
        completion, cancel, or any error escaping the loop — so the busy indicator can
        never be stranded. A turn that raises
        (:class:`~pixelart_creator.logic.assistant.AssistantError`,
        :class:`~pixelart_creator.data.llm.port.LLMError`, or any value error) surfaces
        a typed message and pushes nothing to the undo stack.
        """
        try:
            if self._cancel.is_set():
                return
            outcome = self._job(self._cancel, self._confirm)
            if self._cancel.is_set():
                # Superseded / cancelled: the job restored the document to its
                # original state, so discarding the outcome leaks no mutation.
                return
            self._signals.succeeded.emit(self._token, outcome)
        except Exception as exc:  # noqa: BLE001 - deliberate UI backstop
            self._signals.failed.emit(self._token, f"{type(exc).__name__}: {exc}")
        finally:
            self._signals.done.emit(self._token)


class Assistant_Controller(QObject):
    """Owns the window's assistant ``QThreadPool``, cancel event, carrier + token.

    Re-emits the worker's carrier signals as its own (token-filtered) public signals
    so a superseded run's queued emissions never touch the current run's UI, and
    marshals the tiered-safety confirmation across the worker/GUI boundary.
    :meth:`shutdown` is the idempotent, event-loop-free teardown wired into
    ``MainWindow.shutdown_prewarm``.
    """

    #: ``(token, ConfirmationRequest)`` — a destructive tool-call awaits GUI-thread
    #: approval; the dock shows a confirm dialog and calls
    #: :meth:`provide_confirmation` with the same ``token``.
    confirmRequested = Signal(int, object)
    #: ``(TurnOutcome,)`` — the current run produced a result (the GUI thread renders
    #: the transcript + wraps/pushes the commands onto the undo stack).
    turnReady = Signal(object)
    #: ``(message,)`` — the current run failed (surfaced to the user).
    failed = Signal(str)
    #: emitted when the current run ends (success, failure, or cancel).
    runFinished = Signal()
    #: ``(busy,)`` — whether an assistant turn is in flight (drives UI enablement).
    busyChanged = Signal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create the window-owned single-thread pool + carrier (not the global one)."""
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # A turn is serial against one live document + ordered undo stack; one worker
        # thread keeps ordering deterministic and bounds memory.
        self._pool.setMaxThreadCount(1)
        self._signals: Optional[AssistantWorkerSignals] = AssistantWorkerSignals()
        self._signals.confirmRequested.connect(self._on_confirm_requested)
        self._signals.succeeded.connect(self._on_succeeded)
        self._signals.failed.connect(self._on_failed)
        self._signals.done.connect(self._on_done)
        self._cancel = threading.Event()
        self._confirm_event = threading.Event()
        self._confirm_answer = False
        self._token = 0
        self._busy = False

    # -- queries ----------------------------------------------------------

    def is_busy(self) -> bool:
        """Return whether an assistant turn is currently in flight."""
        return self._busy

    # -- submission -------------------------------------------------------

    def submit(
        self,
        document: Document,
        conversation: Conversation,
        backend: ChatBackend,
        *,
        tools: Optional[Sequence[ToolDescriptor]] = None,
    ) -> int:
        """Start one bounded turn off the GUI thread; return the run token.

        Any in-flight run is superseded first (its later emissions become stale via
        the token bump, and any worker blocked on a confirmation is released to deny).
        The job runs :func:`~pixelart_creator.logic.assistant.run_turn` against
        ``document`` with the marshalling confirm callback, then reverts the applied
        commands so the live document is left byte-identical for the GUI thread to
        re-apply. Safe to ignore after :meth:`shutdown` (the carrier is gone).
        """
        if self._signals is None:
            return self._token
        # Supersede any in-flight run: cancel it and release any pending confirm wait.
        self._cancel.set()
        self._confirm_event.set()
        self._pool.clear()
        self._token += 1
        self._cancel = threading.Event()
        self._confirm_event = threading.Event()
        cancel = self._cancel
        confirm_event = self._confirm_event
        token = self._token
        signals = self._signals

        def confirm(request: ConfirmationRequest) -> bool:
            """Marshal one destructive confirmation to the GUI thread (deny-default)."""
            self._confirm_answer = False
            confirm_event.clear()
            signals.confirmRequested.emit(token, request)
            confirm_event.wait()
            if cancel.is_set():
                return False
            return self._confirm_answer

        def job(
            _cancel: threading.Event,
            _confirm: Callable[[ConfirmationRequest], bool],
        ) -> TurnOutcome:
            try:
                result = run_turn(
                    document, conversation, backend, confirm=_confirm, tools=tools
                )
            except AssistantError as exc:
                # Mid-turn failure. Per the frozen logic contract (ADR-0041 §1),
                # run_turn does NOT auto-revert: any command already applied this
                # turn is still ON the live document and exposed via
                # exc.applied_commands. The turn failed atomically, so nothing may
                # persist — revert the partial commands in reverse
                # (apply ∘ undo = identity) to leave the live document BYTE-IDENTICAL,
                # then surface the error. We do NOT record these as an undo step and
                # NOT re-apply them: the GUI thread must never receive a partial
                # AssistantCommand on error. Raise the underlying cause when present
                # (e.g. the LLMError) so the dock shows the meaningful message.
                for command in reversed(exc.applied_commands):
                    command.undo()
                raise (exc.__cause__ if exc.__cause__ is not None else exc) from None
            # Success: leave the live document restored; the GUI thread re-applies the
            # turn's commands as one undoable AssistantCommand (mirrors
            # make_dispatch_job).
            for command in reversed(result.commands):
                command.undo()
            return TurnOutcome(
                conversation=result.conversation,
                reply=result.reply,
                commands=tuple(result.commands),
            )

        worker = Assistant_Worker(token, job, confirm, cancel, signals)
        self._set_busy(True)
        self._pool.start(worker)
        return token

    def provide_confirmation(self, token: int, approved: bool) -> None:
        """Answer a pending destructive-action confirmation (GUI thread → worker).

        Called by the dock's confirm dialog with the same ``token`` the
        :attr:`confirmRequested` signal carried. A stale/ superseded token is ignored.
        Storing the answer then setting the event releases the blocked worker; a
        dismissed dialog passes ``approved=False`` (deny — a destructive action is
        never auto-approved).
        """
        if token != self._token:
            return
        self._confirm_answer = bool(approved)
        self._confirm_event.set()

    def cancel(self) -> None:
        """Cooperatively cancel the current run (also releases a pending confirm)."""
        self._cancel.set()
        self._confirm_event.set()
        self._pool.clear()

    # -- teardown ---------------------------------------------------------

    def shutdown(self) -> None:
        """Deterministically tear the assistant pool + carrier down (idempotent).

        Mirrors ``Automation_Controller.shutdown`` and does NOT rely on the Qt event
        loop. It bumps the token (every queued / in-flight emission becomes a no-op);
        sets the cancel event; **releases any worker blocked on a confirmation**
        (setting the confirm event → the confirm returns deny); drops queued runnables
        and **blocks** (bounded) on ``waitForDone`` until the running turn finishes and
        the pool's worker threads are removed — so no native worker survives into a
        later GC cycle (the PySide6 cross-thread GC-of-Qt-C++ segfault); then
        disconnects and releases the GUI-thread signal carrier. Safe to call
        repeatedly — from ``MainWindow.shutdown_prewarm`` / ``closeEvent`` and a test
        teardown fixture.
        """
        self._token += 1
        self._cancel.set()
        self._confirm_event.set()
        self._pool.clear()
        self._pool.waitForDone(_ASSISTANT_SHUTDOWN_WAIT_MS)
        signals = self._signals
        if signals is not None:
            for signal, slot in (
                (signals.confirmRequested, self._on_confirm_requested),
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

    @Slot(int, object)
    def _on_confirm_requested(self, token: int, request: object) -> None:
        if token == self._token:
            self.confirmRequested.emit(token, request)

    @Slot(int, object)
    def _on_succeeded(self, token: int, outcome: object) -> None:
        if token == self._token:
            self._set_busy(False)
            self.turnReady.emit(outcome)

    @Slot(int, str)
    def _on_failed(self, token: int, message: str) -> None:
        if token == self._token:
            self._set_busy(False)
            self.failed.emit(message)

    @Slot(int)
    def _on_done(self, token: int) -> None:
        if token == self._token:
            self._set_busy(False)
            self.runFinished.emit()

    # -- helpers ----------------------------------------------------------

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)
