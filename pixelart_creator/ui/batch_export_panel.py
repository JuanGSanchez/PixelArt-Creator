"""Batch export panel — select many targets, export in one action (REQ-P7-UI-005).

``Batch_Export_Panel`` lets the user assemble a list of export **targets** (each
one configured through :class:`~pixelart_creator.ui.export_dialog.Export_Dialog`)
and run them all in **one action** on the window-owned
:class:`~pixelart_creator.ui.export_worker.Export_Controller`. The controller
runs the Qt-free engine off the GUI thread with progress + cancel
(REQ-P7-UI-010), and its worker continues past a failing target
(continue-on-failure, deviation #5): this panel marks each row succeeded /
failed as the per-target signals arrive, so one failure never aborts the rest.

Presentation + wiring only — no encoding / layout logic (that lives in the
frozen ``logic/export`` + ``data/export_io`` engine, S11). Every user-visible
string is ``tr()``-wrapped with a ``changeEvent`` retranslate (REQ-P7-UI-013)
and every control carries an accessible name (REQ-P7-UI-011).
"""

from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.document import Document
from pixelart_creator.ui.export_dialog import Export_Dialog
from pixelart_creator.ui.export_worker import Export_Controller, ExportTarget

#: Optional provider returning the document to export against (the active tab).
DocumentProvider = Callable[[], Optional[Document]]


class Batch_Export_Panel(QWidget):
    """Assemble + run a batch of export targets with per-target status."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build an empty target list with add / remove / export / cancel controls."""
        super().__init__(parent)
        self._controller: Optional[Export_Controller] = None
        self._document_provider: DocumentProvider = lambda: None
        self._targets: List[ExportTarget] = []
        self._running = False

        self._list = QListWidget(self)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add)
        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove)
        self._export_button = QPushButton(self)
        self._export_button.clicked.connect(self._on_export_all)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._on_cancel)
        self._cancel_button.setEnabled(False)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)

        edit_row = QHBoxLayout()
        edit_row.addWidget(self._add_button)
        edit_row.addWidget(self._remove_button)
        run_row = QHBoxLayout()
        run_row.addWidget(self._export_button)
        run_row.addWidget(self._cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list, 1)
        layout.addLayout(edit_row)
        layout.addWidget(self._progress)
        layout.addLayout(run_row)

        self._retranslate()

    # -- wiring -----------------------------------------------------------

    def set_context(
        self, controller: Export_Controller, document_provider: DocumentProvider
    ) -> None:
        """Bind the panel to the window's export controller + document provider.

        Connects the controller's (token-filtered) per-target signals so the panel
        reflects live progress. Idempotent for a given controller instance.
        """
        self._controller = controller
        self._document_provider = document_provider
        controller.progress.connect(self._on_progress)
        controller.targetSucceeded.connect(self._on_target_succeeded)
        controller.targetFailed.connect(self._on_target_failed)
        controller.batchFinished.connect(self._on_batch_finished)
        controller.busyChanged.connect(self._on_busy_changed)

    # -- target editing ---------------------------------------------------

    def _on_add(self) -> None:
        """Configure a new target via the export dialog and append it to the list."""
        document = self._document_provider()
        if document is None:
            return
        dialog = Export_Dialog(document, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = dialog.export_target()
        if target is None:
            return
        self._targets.append(target)
        item = QListWidgetItem(target.label)
        item.setData(Qt.ItemDataRole.UserRole, target.label)
        self._list.addItem(item)

    def _on_remove(self) -> None:
        """Remove the selected target row."""
        row = self._list.currentRow()
        if 0 <= row < len(self._targets):
            self._targets.pop(row)
            self._list.takeItem(row)

    # -- run --------------------------------------------------------------

    def _on_export_all(self) -> None:
        """Submit all targets to the controller in one action (REQ-P7-UI-005)."""
        document = self._document_provider()
        if self._controller is None or document is None or not self._targets:
            return
        self._running = True
        self._progress.setRange(0, len(self._targets))
        self._progress.setValue(0)
        for row in range(self._list.count()):
            item = self._list.item(row)
            item.setText(item.data(Qt.ItemDataRole.UserRole))
        self._controller.submit(document, tuple(self._targets))

    def _on_cancel(self) -> None:
        """Cooperatively cancel the running batch (between targets)."""
        if self._controller is not None:
            self._controller.cancel()

    # -- controller signals (only while THIS panel drives a run) ----------

    def _on_progress(self, done: int, total: int, label: str) -> None:
        if self._running:
            self._progress.setRange(0, total)
            self._progress.setValue(done)

    def _on_target_succeeded(self, index: int, _result: object) -> None:
        if self._running:
            self._mark(index, self.tr("%1 — done"))

    def _on_target_failed(self, index: int, message: str) -> None:
        if self._running:
            self._mark(index, self.tr("%1 — failed: %2").replace("%2", message))

    def _on_batch_finished(self) -> None:
        self._running = False

    def _on_busy_changed(self, busy: bool) -> None:
        """Disable editing / re-export while a run is in flight; enable Cancel."""
        self._add_button.setEnabled(not busy)
        self._remove_button.setEnabled(not busy)
        self._export_button.setEnabled(not busy)
        self._cancel_button.setEnabled(busy)

    def _mark(self, index: int, template: str) -> None:
        if 0 <= index < self._list.count():
            item = self._list.item(index)
            base = item.data(Qt.ItemDataRole.UserRole)
            item.setText(template.replace("%1", base))

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._add_button.setText(self.tr("Add Target…"))
        self._remove_button.setText(self.tr("Remove"))
        self._export_button.setText(self.tr("Export All"))
        self._cancel_button.setText(self.tr("Cancel"))
        self.setAccessibleName(self.tr("Batch export"))
        self._list.setAccessibleName(self.tr("Batch export targets"))
        self._progress.setAccessibleName(self.tr("Batch export progress"))
        self._add_button.setAccessibleName(self.tr("Add export target"))
        self._remove_button.setAccessibleName(self.tr("Remove export target"))
        self._export_button.setAccessibleName(self.tr("Export all targets"))
        self._cancel_button.setAccessibleName(self.tr("Cancel batch export"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the batch-export panel strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
