"""Macro record / replay / manage panel (REQ-P8-UI-001, -002, -003).

``Macro_Controls`` is the UI over the frozen macro engine: it **records** the
ordered DSL :class:`~pixelart_creator.logic.macro.Op` stream the user performs
(start / stop is view state, no undo — CL-8), **replays** a macro on the active
document (one undoable grouped command — REQ-P8-UI-002/-009), and **saves /
loads / lists** ``.pixmacro`` files through the defensive, ``eval``-free
:mod:`pixelart_creator.data.macro_io` path (a malformed file surfaces a
user-facing error, never a crash or arbitrary execution — REQ-P8-UI-003).

Presentation + wiring only (S11): recording is captured by the host (which owns
the undo stack) calling :meth:`add_recorded_ops` while :meth:`is_recording` is
true; building the :class:`~pixelart_creator.logic.macro.Macro`, serialising it,
and replaying it are all delegated to ``logic.macro`` / ``data.macro_io`` — no
domain logic and **no ``eval``/``exec``** here. Every user-visible string is
``tr()``-wrapped with a ``changeEvent`` retranslate (REQ-P8-UI-014) and every
control carries an accessible name (REQ-P8-UI-012).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.macro_io import (
    FILE_SUFFIX,
    MacroIOError,
    load_macro,
    save_macro,
)
from pixelart_creator.logic.macro import Macro, MacroError, Op, record
from pixelart_creator.ui.automation_worker import STAGE_COMPLETE, STAGE_RUNNING


class Macro_Controls(QWidget):
    """Record, replay, save, load and list automation macros."""

    #: ``(Macro, label)`` — the host should replay this macro on the active
    #: document (as one undoable grouped command, REQ-P8-UI-002).
    replayRequested = Signal(object, str)
    #: ``(recording,)`` — recording started / stopped (view state, not undoable).
    recordingToggled = Signal(bool)
    #: The user asked to cancel the in-flight automation run (C-07); the host
    #: relays this to ``Automation_Controller.cancel()``.
    cancelRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the record / replay / manage controls with an empty macro list."""
        super().__init__(parent)
        self._recording = False
        self._pending: List[Op] = []
        self._recording_count = 0

        self._status = QLabel(self)
        self._record_button = QPushButton(self)
        self._record_button.setCheckable(True)
        self._record_button.toggled.connect(self._on_record_toggled)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._replay_button = QPushButton(self)
        self._replay_button.clicked.connect(self._on_replay)
        self._save_button = QPushButton(self)
        self._save_button.clicked.connect(self._on_save)
        self._load_button = QPushButton(self)
        self._load_button.clicked.connect(self._on_load)
        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove)
        # Reachable Cancel affordance for an in-flight automation run (C-07):
        # disabled while idle, enabled only while the host reports busy.
        self._cancel_button = QPushButton(self)
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self.cancelRequested)

        manage_row = QHBoxLayout()
        manage_row.addWidget(self._replay_button)
        manage_row.addWidget(self._save_button)
        manage_row.addWidget(self._load_button)
        manage_row.addWidget(self._remove_button)
        manage_row.addWidget(self._cancel_button)

        # Per-target automation progress (D-06): a dedicated QGroupBox keeps this
        # visually distinct from the record/manage controls above it (the user's
        # "clear element boundaries" directive), with no widget-level colour
        # override — rendered entirely from the app's role-based theme
        # (qss-theming). Reflects a replay run, the one automation this panel
        # submits (recording itself has no worker run / progress).
        self._progress_stage_token = ""
        self._progress_group = QGroupBox(self)
        self._progress_status = QLabel(self._progress_group)
        self._progress_bar = QProgressBar(self._progress_group)
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        progress_layout = QVBoxLayout(self._progress_group)
        progress_layout.addWidget(self._progress_status)
        progress_layout.addWidget(self._progress_bar)

        layout = QVBoxLayout(self)
        layout.addWidget(self._record_button)
        layout.addWidget(self._status)
        layout.addWidget(self._list, 1)
        layout.addLayout(manage_row)
        layout.addWidget(self._progress_group)

        self._retranslate()
        self._update_status()

    # -- automation progress (D-06) ----------------------------------------

    def set_target_progress(self, index: int, count: int, stage: str) -> None:
        """Reflect the automation worker's per-target progress on the bar.

        Bound (by the host) to ``Automation_Controller.targetProgress`` — this
        panel computes no domain value; it only echoes ``index``/``count`` onto
        the bar and maps the plain ``stage`` token to a translated label (S11).
        """
        total = max(1, int(count))
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(max(0, min(int(index), total)))
        self._progress_stage_token = stage
        self._progress_status.setText(self._stage_text(stage))

    def _stage_text(self, stage: str) -> str:
        if stage == STAGE_RUNNING:
            return self.tr("Running…")
        if stage == STAGE_COMPLETE:
            return self.tr("Done")
        return self.tr("Idle")

    # -- recording (view state, no undo — CL-8) ---------------------------

    def is_recording(self) -> bool:
        """Whether a macro recording is currently in progress."""
        return self._recording

    def add_recorded_ops(self, ops: List[Op]) -> None:
        """Append the DSL ops of an applied automation edit to the recording.

        Called by the host after an automation edit lands on the undo stack, only
        while :meth:`is_recording` is true. Captures the *inputs* (the DSL ops),
        never a pixel diff (REQ-P8-LOGIC-004).
        """
        if not self._recording:
            return
        self._pending.extend(ops)
        self._update_status()

    def _on_record_toggled(self, recording: bool) -> None:
        """Start a fresh recording, or stop and bank the captured macro."""
        self._recording = recording
        if recording:
            self._pending = []
        else:
            self._bank_recording()
        self.recordingToggled.emit(recording)
        self._retranslate()
        self._update_status()

    def _bank_recording(self) -> None:
        """Turn the captured ops into a :class:`Macro` and add it to the list."""
        if not self._pending:
            return
        try:
            macro = record(self._pending)
        except MacroError as exc:
            QMessageBox.warning(self, self.tr("Macro Error"), str(exc))
            self._pending = []
            return
        self._recording_count += 1
        label = self.tr("Recording %1 (%2 steps)")
        label = label.replace("%1", str(self._recording_count))
        label = label.replace("%2", str(len(macro.ops)))
        self._add_macro(macro, label)
        self._pending = []

    # -- macro list -------------------------------------------------------

    def _add_macro(self, macro: Macro, label: str) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, macro)
        self._list.addItem(item)
        self._list.setCurrentItem(item)

    def _selected_macro(self) -> Optional[Macro]:
        item = self._list.currentItem()
        if item is None:
            return None
        macro = item.data(Qt.ItemDataRole.UserRole)
        return macro if isinstance(macro, Macro) else None

    def _selected_label(self) -> str:
        item = self._list.currentItem()
        return item.text() if item is not None else self.tr("Macro")

    # -- actions ----------------------------------------------------------

    def _on_replay(self) -> None:
        """Ask the host to replay the selected macro (one undoable command)."""
        macro = self._selected_macro()
        if macro is None:
            return
        self.replayRequested.emit(macro, self._selected_label())

    def _on_save(self) -> None:
        """Save the selected macro to a ``.pixmacro`` file (defensive, eval-free)."""
        macro = self._selected_macro()
        if macro is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Macro"),
            "",
            self.tr("Macro files (*%1)").replace("%1", FILE_SUFFIX),
        )
        if not path:
            return
        try:
            save_macro(macro, path)
        except (MacroIOError, MacroError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Save Macro Failed"), str(exc))

    def _on_load(self) -> None:
        """Load a ``.pixmacro`` file; a malformed file surfaces a graceful error.

        Uses the defensive, ``eval``-free ``data.macro_io.load_macro`` (IO-3) — a
        malformed / unsupported-version file raises :class:`MacroIOError` and is
        reported, never executed (REQ-P8-UI-003, REQ-P8-LOGIC-007).
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Load Macro"),
            "",
            self.tr("Macro files (*%1)").replace("%1", FILE_SUFFIX),
        )
        if not path:
            return
        try:
            macro = load_macro(path)
        except (MacroIOError, MacroError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Load Macro Failed"), str(exc))
            return
        self._add_macro(macro, Path(path).name)

    def _on_remove(self) -> None:
        """Remove the selected macro from the session list (files untouched)."""
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)

    # -- enablement -------------------------------------------------------

    def set_busy(self, busy: bool) -> None:
        """Disable replay / recording while an automation run is in flight.

        The Cancel button is the mirror image: reachable ONLY while busy (C-07).
        """
        self._record_button.setEnabled(not busy)
        self._replay_button.setEnabled(not busy)
        self._cancel_button.setEnabled(busy)
        if not busy:
            self._progress_bar.setRange(0, 1)
            self._progress_bar.setValue(0)
            self._progress_stage_token = ""
            self._progress_status.setText(self._stage_text(""))

    # -- i18n -------------------------------------------------------------

    def _update_status(self) -> None:
        if self._recording:
            text = self.tr("Recording… %1 steps captured")
            self._status.setText(text.replace("%1", str(len(self._pending))))
        else:
            self._status.setText(self.tr("Not recording"))

    def _retranslate(self) -> None:
        self._record_button.setText(
            self.tr("Stop Recording") if self._recording else self.tr("Record Macro")
        )
        self._replay_button.setText(self.tr("Replay"))
        self._save_button.setText(self.tr("Save…"))
        self._load_button.setText(self.tr("Load…"))
        self._remove_button.setText(self.tr("Remove"))
        self._cancel_button.setText(self.tr("Cancel"))
        self.setAccessibleName(self.tr("Macro controls"))
        self._record_button.setAccessibleName(self.tr("Record or stop a macro"))
        self._status.setAccessibleName(self.tr("Macro recording status"))
        self._list.setAccessibleName(self.tr("Recorded and loaded macros"))
        self._replay_button.setAccessibleName(self.tr("Replay the selected macro"))
        self._save_button.setAccessibleName(self.tr("Save the selected macro"))
        self._load_button.setAccessibleName(self.tr("Load a macro from a file"))
        self._remove_button.setAccessibleName(self.tr("Remove the selected macro"))
        self._cancel_button.setAccessibleName(self.tr("Cancel the running automation"))
        self._cancel_button.setAccessibleDescription(
            self.tr("Stops the in-flight automation run; enabled only while busy.")
        )
        self._progress_group.setTitle(self.tr("Progress"))
        self._progress_bar.setAccessibleName(self.tr("Macro replay progress"))
        self._progress_status.setText(self._stage_text(self._progress_stage_token))
        self._update_status()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the macro-control strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
