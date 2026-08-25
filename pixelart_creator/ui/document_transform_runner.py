"""Qt orchestration for a whole-document geometry transform (canvas-scale-defects).

Bridges the Qt-free ``logic/doc_transform.py`` engine into a modal cost gate,
determinate progress and GUI-thread stepping (PL-CSD-D2, ``plan.md``
§5.2/§5.3). Holds no domain maths (S11): every byte counted, every buffer
resampled and the reversible command itself all come from
``logic/doc_transform.py``; this module only drives the dialogs and the
zero-timer step chain.

**Atomicity is structural, not asserted here.** Nothing in this module ever
names a :class:`~pixelart_creator.logic.document.Layer` attribute — it steps
a Qt-free :class:`~pixelart_creator.logic.doc_transform.DocumentTransformRun`
and, only once every buffer has resampled, asks that module to build the one
command that commits them all. Declining the confirmation or cancelling the
run both return ``None`` with no command ever constructed, which is why
"nothing reaches the undo stack" holds by construction rather than by
unwinding (REQ-CSD-UI-012).

**GUI thread only.** One buffer resamples per chained zero-delay
``QTimer.singleShot``, driven inside the progress dialog's own modal event
loop — no ``QThreadPool``, no worker thread. ``plan.md`` §5.3 records the
four reasons and the ``Layer.buffer`` thread-confinement ruling this shape
depends on; do not substitute a thread without re-opening that ruling.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtWidgets import QDialog, QWidget

from pixelart_creator.logic import history
from pixelart_creator.logic.constants import DOCUMENT_TRANSFORM_CONFIRM_BYTES
from pixelart_creator.logic.doc_transform import (
    DocTransformError,
    DocumentTransformRun,
    enumerate_targets,
    make_document_transform_command,
    projected_peak_bytes,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.ui.document_transform_dialogs import (
    Document_Transform_Confirm_Dialog,
    Document_Transform_Progress_Dialog,
)


class Document_Transform_Runner(QObject):
    """Drives one whole-document transform: cost gate, progress, atomic commit.

    :meth:`run` returns an **unapplied**
    :class:`~pixelart_creator.logic.history.Command` once every buffer has
    resampled, or ``None`` if the user declined the confirmation or
    cancelled the run. Refuses re-entry: only one run may be live on a given
    instance at a time (:exc:`~pixelart_creator.logic.doc_transform.DocTransformError`
    otherwise) — a fresh instance is cheap and the ordinary way to run again.
    """

    #: Emitted after each buffer resamples, with the run's ``done`` count —
    #: the deterministic hook a test uses to cancel at an exact step
    #: (``plan.md`` §5.3 reason 2).
    stepped = Signal(int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create an idle runner. Call :meth:`run` to drive one transform."""
        super().__init__(parent)
        self._running = False
        self._cancel_requested = False

    def cancel(self) -> None:
        """Request cancellation of the live run.

        Honoured **between** buffers, never mid-buffer — a single
        :meth:`~pixelart_creator.logic.doc_transform.DocumentTransformRun.step`
        call is synchronous and is always allowed to finish, so cancelling at
        any point produces the same early return
        (REQ-CSD-UI-012 criterion 6).
        """
        self._cancel_requested = True

    def run(
        self,
        document: Document,
        transform: Callable[[PixelBuffer], PixelBuffer],
        new_width: int,
        new_height: int,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> Optional[history.Command]:
        """Run one whole-document transform to completion, or return ``None``.

        Implements ``plan.md`` §5.2 step-for-step:

        1. Enumerate the targets and cost the projected run.
        2. If the projection is **strictly greater than**
           ``DOCUMENT_TRANSFORM_CONFIRM_BYTES``, ask
           :class:`~pixelart_creator.ui.document_transform_dialogs.Document_Transform_Confirm_Dialog`
           — landing exactly on the threshold stays silent
           (SC-CSD-U015-3). Declining returns ``None`` **before** any
           progress dialog is built (REQ-CSD-UI-010).
        3. Show the determinate progress dialog and step one buffer per
           chained zero-delay timer, inside the dialog's own modal event
           loop, emitting :attr:`stepped` after each buffer.
        4. Cancelling returns ``None``; nothing was ever committed.
        5. Once every buffer has resampled, build and return the command —
           the caller pushes it onto its own undo stack.

        At most one question is ever asked per call (REQ-CSD-UI-013): the
        confirmation, at most once, before any resampling; cancellation
        never re-presents it and never asks the user to confirm the cancel.

        Raises:
            DocTransformError: If a run is already live on this instance.
        """
        if self._running:
            raise DocTransformError(
                "Document_Transform_Runner does not support a re-entrant run"
            )
        self._running = True
        self._cancel_requested = False
        try:
            targets = enumerate_targets(document)
            run = DocumentTransformRun(targets)
            projected = projected_peak_bytes(document, new_width, new_height)
            if projected > DOCUMENT_TRANSFORM_CONFIRM_BYTES:
                confirm = Document_Transform_Confirm_Dialog(
                    label, projected, new_width, new_height, parent
                )
                if confirm.exec() != QDialog.DialogCode.Accepted:
                    return None  # REQ-CSD-UI-010: declined, nothing built

            if run.total == 0:
                # Nothing to resample (an empty document) — no progress
                # dialog to show (its range must never be (0, 0)); the
                # command still needs building so geometry-only state (if
                # any) commits through the one reversible path.
                return make_document_transform_command(
                    document, run, new_width, new_height, label
                )

            progress = Document_Transform_Progress_Dialog(label, run.total, parent)
            progress.cancelled.connect(self.cancel)
            loop = QEventLoop(self)
            failure: list[BaseException] = []

            def _tick() -> None:
                if self._cancel_requested:
                    loop.quit()
                    return
                try:
                    run.step(transform)
                except BaseException as exc:  # noqa: BLE001 (re-raised below)
                    # A Python exception raised inside a Qt slot invoked from
                    # the event loop (this callback, reached via
                    # QTimer.singleShot) does NOT propagate back through
                    # loop.exec() to this method's caller — PySide6 reports
                    # it to sys.excepthook and the loop keeps running, which
                    # would otherwise hang here forever waiting for a
                    # buffer that failed and never advanced. Caught,
                    # stashed and re-raised after the loop quits, so a
                    # transform error (e.g. an invalid target size) still
                    # reaches the caller synchronously, exactly as it did
                    # before this batch routed the call through a timer
                    # chain. Verified against
                    # test_scale_error_is_reported_not_raised.
                    failure.append(exc)
                    loop.quit()
                    return
                progress.set_progress(run.done)
                self.stepped.emit(run.done)
                if self._cancel_requested or run.finished:
                    loop.quit()
                    return
                QTimer.singleShot(0, self, _tick)

            QTimer.singleShot(0, self, _tick)
            progress.open()
            loop.exec()
            # Disconnect before closing: Document_Transform_Progress_Dialog's
            # closeEvent() override emits `cancelled` on ANY close, including
            # this courtesy call after the loop has already exited normally
            # (finished or already cancelled) — left connected, a successful
            # completion would retroactively flip `_cancel_requested` and be
            # reported as a cancel.
            progress.cancelled.disconnect(self.cancel)
            progress.close()

            if failure:
                raise failure[0]

            if self._cancel_requested or not run.finished:
                return None  # nothing built, nothing reaches the undo stack

            return make_document_transform_command(
                document, run, new_width, new_height, label
            )
        finally:
            self._running = False


def run_document_transform(
    document: Document,
    transform: Callable[[PixelBuffer], PixelBuffer],
    new_width: int,
    new_height: int,
    label: str,
    parent: Optional[QWidget] = None,
    runner: Optional[Document_Transform_Runner] = None,
) -> Optional[history.Command]:
    """Run one whole-document transform on ``runner`` (or a fresh instance).

    Thin convenience wrapper around :meth:`Document_Transform_Runner.run`.
    ``runner`` is exposed as a parameter — rather than always constructed
    internally — so a caller (a test in particular) can connect to
    :attr:`Document_Transform_Runner.stepped` *before* the run starts and
    act deterministically at an exact step (``plan.md`` §5.3 reason 2).
    """
    owner = runner if runner is not None else Document_Transform_Runner(parent)
    return owner.run(document, transform, new_width, new_height, label, parent)
