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

T7-A (ruling P11-R7, REQ-P11-UI-014): this module cannot perform the asset
registration the export dialog's opt-in requests — the export itself runs
off-thread, so success is known only later, at the window's completion
handlers. Instead it carries the opt-in's answer back to the caller as an
:class:`Export_Registration_Request`; the window decides whether and when to
act on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from pixelart_creator.logic.document import Document
from pixelart_creator.ui.export_dialog import Export_Dialog
from pixelart_creator.ui.export_worker import Export_Controller, ExportTarget


@dataclass(frozen=True)
class Export_Registration_Request:
    """The export dialog's opt-in answer, carried back to the caller.

    Never acted on here — ``ui/main_window.py`` holds this until the export it
    describes actually succeeds (T7-A, ruling P11-R7), then calls
    :meth:`~pixelart_creator.ui.asset_library_actions.Asset_Library_Session.
    register_export_artifact` with these exact fields.
    """

    #: The source document that was submitted for export (never the exported
    #: file's own bytes — REQ-P11-UI-014).
    document: Document
    #: The export settings as used for this run (JSON-scalar values only —
    #: bounded by ``logic.constants.MAX_METADATA_BYTES`` at ingress).
    export_metadata: Mapping[str, object]


def _export_metadata(target: ExportTarget) -> Mapping[str, object]:
    """Build the JSON-scalar metadata bag from the target actually submitted."""
    request = target.request
    return {
        "format": request.fmt.value,
        "preset": request.preset.value,
        "columns": request.columns,
        "padding": request.padding,
        "max_dimension": request.max_dimension,
        "loop": request.loop,
        "tag": request.tag,
        "emit_json": request.emit_json,
        "frame_index": request.frame_index,
        "out_path": target.out_path,
    }


def run_export_dialog(
    parent: QWidget,
    document: Optional[Document],
    controller: Export_Controller,
    frame_index: int = 0,
) -> Optional[Export_Registration_Request]:
    """Open the export dialog and submit the configured target (REQ-P7-UI-001).

    No open document → a graceful notice (never a crash). A dialog dismissed
    without a destination path → a graceful notice. Otherwise the target is
    submitted to ``controller`` (off-thread); the controller's relay surfaces the
    result. This function performs **no** encoding / layout of its own.
    ``frame_index`` is the caller's currently-active frame, forwarded to the
    dialog so a PNG export honours it instead of always frame 0 (CF-18).

    Returns an :class:`Export_Registration_Request` when the user both
    submitted a target AND checked the dialog's "also add to the asset
    library" opt-in (T7-A); ``None`` in every other case (no document,
    cancelled, no path, or the opt-in was left unchecked — REQ-P11-UI-014's
    negative: the export's default behaviour is unchanged).
    """
    if document is None:
        QMessageBox.information(
            parent,
            QCoreApplication.translate("export", "Export"),
            QCoreApplication.translate("export", "Open a document before exporting."),
        )
        return None
    dialog = Export_Dialog(document, parent, frame_index=frame_index)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    target = dialog.export_target()
    if target is None:
        QMessageBox.warning(
            parent,
            QCoreApplication.translate("export", "Export"),
            QCoreApplication.translate(
                "export", "Choose a destination path before exporting."
            ),
        )
        return None
    controller.submit(document, (target,))
    if dialog.register_on_export():
        return Export_Registration_Request(
            document=document, export_metadata=_export_metadata(target)
        )
    return None
