"""Timelapse recorder controls (REQ-P9-UI-009) — Qt only, binds to logic/timelapse.

``Timelapse_Controls`` records a **reproducible** edit session: one frame per
committed undoable command (the Procreate cadence). It wires the active document's
``QUndoStack`` command-commit path — a *forward* index change (a push or redo, never
an undo) — to :func:`~pixelart_creator.logic.timelapse.record_frame`, appending a
``TimelapseFrame(index, command_id)`` to an immutable
:class:`~pixelart_creator.logic.timelapse.TimelapseSession`. The session persists via
:mod:`pixelart_creator.data.timelapse_io` (``.pixtimelapse`` manifest — command
references, not pixels). Replay re-renders deterministically off the shipped history
(the pure ``logic/timelapse.replay``).

Recording is **view/session state**: it pushes **no** ``QUndoCommand`` and never
mutates the document (REQ-P9-UI-010). A failed record/save (e.g. an unwritable path)
surfaces a user-facing error, never a crash. Encoding is deferred (ADR-0024 §2): this
control ships the reproducible sequence only. Strings are ``tr()``-wrapped with a
``changeEvent`` retranslate (REQ-P9-UI-014).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.timelapse_io import (
    TimelapseIOError,
    load_session,
    save_session,
)
from pixelart_creator.logic.timelapse import (
    TimelapseError,
    TimelapseSession,
    new_session,
    record_frame,
)


class Timelapse_Controls(QWidget):
    """Start/stop/save/load the per-committed-command timelapse session."""

    #: Emitted with the current frame count after a record / load / reset.
    frameCountChanged = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the record/save/load controls with an empty session."""
        super().__init__(parent)
        self._session: TimelapseSession = new_session()
        self._recording = False
        self._stack: Optional[QUndoStack] = None
        self._last_index = 0

        self._record_button = QPushButton(self)
        self._record_button.setCheckable(True)
        self._record_button.toggled.connect(self._on_record_toggled)
        self._save_button = QPushButton(self)
        self._save_button.clicked.connect(self._on_save)
        self._load_button = QPushButton(self)
        self._load_button.clicked.connect(self._on_load)
        self._count_label = QLabel(self)

        controls = QHBoxLayout()
        controls.addWidget(self._record_button)
        controls.addWidget(self._save_button)
        controls.addWidget(self._load_button)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self._count_label)
        self._retranslate()

    # -- undo-stack binding (command-commit capture) ----------------------

    def bind_undo_stack(self, stack: QUndoStack) -> None:
        """Bind the active document's undo stack (document open / tab switch).

        Records one frame on each **forward** index change (a push/redo), never on
        an undo (a backward move). View state only — no document mutation.
        """
        if self._stack is not None:
            try:
                self._stack.indexChanged.disconnect(self._on_stack_index_changed)
            except (RuntimeError, TypeError):
                pass
        self._stack = stack
        self._last_index = stack.index()
        stack.indexChanged.connect(self._on_stack_index_changed)

    def _on_stack_index_changed(self, index: int) -> None:
        forward = index > self._last_index
        self._last_index = index
        if self._recording and forward:
            self._record_committed(index)

    def _record_committed(self, command_id: int) -> None:
        try:
            # command_id: the stable ordinal of the committed history command.
            self._session = record_frame(self._session, command_id)
        except TimelapseError as exc:
            # Frame budget exceeded → stop recording, surface a user-facing notice.
            self._recording = False
            self._record_button.setChecked(False)
            QMessageBox.warning(self, self.tr("Recording stopped"), str(exc))
            return
        self._emit_count()

    # -- session state ----------------------------------------------------

    def session(self) -> TimelapseSession:
        """Return the current immutable timelapse session."""
        return self._session

    def is_recording(self) -> bool:
        """Return whether recording is active."""
        return self._recording

    def frame_count(self) -> int:
        """Return the number of recorded frames."""
        return len(self._session.frames)

    def reset(self) -> None:
        """Discard the recorded session (document open / new session)."""
        self._session = new_session()
        self._recording = False
        self._record_button.setChecked(False)
        self._emit_count()

    def _on_record_toggled(self, checked: bool) -> None:
        self._recording = bool(checked)
        self._retranslate_record()

    # -- persistence (binds to data/timelapse_io) -------------------------

    def _on_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Timelapse"),
            "",
            self.tr("Timelapse (*.pixtimelapse)"),
        )
        if not path:
            return
        try:
            save_session(self._session, path)
        except TimelapseIOError as exc:
            QMessageBox.warning(self, self.tr("Save failed"), str(exc))

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Timelapse"),
            "",
            self.tr("Timelapse (*.pixtimelapse)"),
        )
        if not path:
            return
        try:
            self._session = load_session(path)
        except TimelapseIOError as exc:
            # Malformed / unknown-version manifest → user-facing error, never a crash.
            QMessageBox.warning(self, self.tr("Open failed"), str(exc))
            return
        self._emit_count()

    # -- i18n -------------------------------------------------------------

    def _emit_count(self) -> None:
        self._count_label.setText(
            self.tr("Recorded frames: {0}").format(len(self._session.frames))
        )
        self.frameCountChanged.emit(len(self._session.frames))

    def _retranslate_record(self) -> None:
        self._record_button.setText(
            self.tr("Stop Recording") if self._recording else self.tr("Record")
        )

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Timelapse"))
        self.setAccessibleName(self.tr("Timelapse controls"))
        self._save_button.setText(self.tr("Save…"))
        self._load_button.setText(self.tr("Open…"))
        self._retranslate_record()
        self._emit_count()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the control strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
