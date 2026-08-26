"""New-document size dialog (File > New, Ctrl+N).

``New_Document_Dialog`` collects a width/height for a brand-new
:class:`~pixelart_creator.logic.document.Document`; it holds **no** document
construction logic (S11) — the caller (``ui/main_window.py``) reads
:meth:`New_Document_Dialog.target_size` and builds the document itself. Bounds
come from ``logic.constants`` (``DEFAULT_CANVAS_WIDTH``/``_HEIGHT``,
``MAX_CANVAS_WIDTH``/``_HEIGHT``); no magic numbers here (S12). The 8K ceiling
is enforced once, in :func:`~pixelart_creator.logic.pixel_buffer._check_dimensions`
— this dialog only keeps the spin boxes from accepting a value that would
already be rejected there, it does not duplicate that check. All strings are
``tr()``-wrapped and re-set on ``QEvent.LanguageChange`` (F5).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from pixelart_creator.logic.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)


class New_Document_Dialog(QDialog):
    """Modal dialog returning the ``(width, height)`` of a new document."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the dialog pre-filled with the shipped default canvas size."""
        super().__init__(parent)

        self._width = QSpinBox(self)
        self._width.setRange(1, MAX_CANVAS_WIDTH)
        self._width.setValue(DEFAULT_CANVAS_WIDTH)

        self._height = QSpinBox(self)
        self._height.setRange(1, MAX_CANVAS_HEIGHT)
        self._height.setValue(DEFAULT_CANVAS_HEIGHT)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        self._width_label = QLabel(self)
        self._height_label = QLabel(self)
        self._form = QFormLayout(self)
        self._form.addRow(self._width_label, self._width)
        self._form.addRow(self._height_label, self._height)
        self._form.addRow(self._buttons)
        self._retranslate()

    # -- result ----------------------------------------------------------

    def target_size(self) -> Tuple[int, int]:
        """Return the chosen ``(width, height)`` in pixels."""
        return int(self._width.value()), int(self._height.value())

    # -- i18n --------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("New Document"))
        self.setAccessibleName(self.tr("New document dialog"))
        self._width.setAccessibleName(self.tr("Document width in pixels"))
        self._height.setAccessibleName(self.tr("Document height in pixels"))
        self._width_label.setText(self.tr("Width (px)"))
        self._height_label.setText(self.tr("Height (px)"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
