"""Canvas Size dialog (Image > Canvas Size...) — resizes the active document.

``Canvas_Size_Dialog`` collects a new width/height for the **existing**
document; it holds **no** resize math (S11) — the caller
(``ui/main_window.py``) reads :meth:`Canvas_Size_Dialog.target_size` and wraps
:meth:`~pixelart_creator.logic.document.Document.resize_canvas` in a
:class:`~pixelart_creator.ui.commands.CanvasResizeCommand` so the resize is one
undoable step (F1/FIX-05). Bounds come from ``logic.constants``
(``MAX_CANVAS_WIDTH``/``_HEIGHT``); no magic numbers here (S12). The resize
always anchors the existing content at the top-left (``offset_x=offset_y=0``);
:meth:`~pixelart_creator.logic.pixel_buffer.PixelBuffer.resize` crops/pads from
the bottom-right accordingly. All strings are ``tr()``-wrapped and re-set on
``QEvent.LanguageChange`` (F5).
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

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH


class Canvas_Size_Dialog(QDialog):
    """Modal dialog returning the ``(width, height)`` target for a resize."""

    def __init__(
        self, width: int, height: int, parent: Optional[QWidget] = None
    ) -> None:
        """Build the dialog seeded with the current ``width`` x ``height``."""
        super().__init__(parent)

        self._width = QSpinBox(self)
        self._width.setRange(1, MAX_CANVAS_WIDTH)
        self._width.setValue(int(width))

        self._height = QSpinBox(self)
        self._height.setRange(1, MAX_CANVAS_HEIGHT)
        self._height.setValue(int(height))

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
        """Return the chosen ``(width, height)`` target in pixels."""
        return int(self._width.value()), int(self._height.value())

    # -- i18n --------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Canvas Size"))
        self.setAccessibleName(self.tr("Canvas size dialog"))
        self._width.setAccessibleName(self.tr("Target canvas width in pixels"))
        self._height.setAccessibleName(self.tr("Target canvas height in pixels"))
        self._width_label.setText(self.tr("Width (px)"))
        self._height_label.setText(self.tr("Height (px)"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
