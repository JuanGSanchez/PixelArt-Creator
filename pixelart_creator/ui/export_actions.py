"""Single-export action — open the dialog and submit to the export controller.

Thin Qt front-end that opens :class:`~pixelart_creator.ui.export_dialog.Export_Dialog`,
builds one :class:`~pixelart_creator.ui.export_worker.ExportTarget`, and submits
it to the window-owned :class:`~pixelart_creator.ui.export_worker.Export_Controller`
as a one-target batch — the **same** off-GUI-thread engine path the batch UI and
the CLI use, so the GUI export is byte-identical to the CLI export
(REQ-P7-UI-007) and stays responsive (REQ-P7-UI-010). Export is **read-only**:
this pushes **no** ``QUndoCommand`` and adds nothing to ``ui/commands.py``
(REQ-P7-UI-009). Success / failure are surfaced by the controller's signal
relay in :class:`~pixelart_creator.ui.main_window.Main_Window` (a user-facing
``QMessageBox`` on failure, never a crash — REQ-P7-UI-008). All strings are
``tr()``-wrapped via ``QCoreApplication.translate`` so a module-level call still
extracts (REQ-P7-UI-013).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from pixelart_creator.logic.document import Document
from pixelart_creator.ui.export_dialog import Export_Dialog
from pixelart_creator.ui.export_worker import Export_Controller


def run_export_dialog(
    parent: QWidget,
    document: Optional[Document],
    controller: Export_Controller,
) -> None:
    """Open the export dialog and submit the configured target (REQ-P7-UI-001).

    No open document → a graceful notice (never a crash). A dialog dismissed
    without a destination path → a graceful notice. Otherwise the target is
    submitted to ``controller`` (off-thread); the controller's relay surfaces the
    result. This function performs **no** encoding / layout of its own.
    """
    if document is None:
        QMessageBox.information(
            parent,
            QCoreApplication.translate("export", "Export"),
            QCoreApplication.translate("export", "Open a document before exporting."),
        )
        return
    dialog = Export_Dialog(document, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    target = dialog.export_target()
    if target is None:
        QMessageBox.warning(
            parent,
            QCoreApplication.translate("export", "Export"),
            QCoreApplication.translate(
                "export", "Choose a destination path before exporting."
            ),
        )
        return
    controller.submit(document, (target,))
