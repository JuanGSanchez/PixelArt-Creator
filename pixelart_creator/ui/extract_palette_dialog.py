# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Auto-extract-from-image dialog (REQ-P3-UI-010).

``Extract_Palette_Dialog`` loads an image, then extracts a palette of at most ``N``
colours by median-cut or seeded k-means. The extraction maths live in
:mod:`pixelart_creator.logic.quantize` (the ``≤N`` guarantee is enforced there,
SC-U010-1/-2); this dialog only decodes the chosen image to a
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer` (presentation-side image
I/O), reads the ``N`` control (defaulting to ``PALETTE_EXTRACT_DEFAULT_N``) and the
median-cut / k-means choice, and hands the result back via :meth:`result_palette`.
No colour maths live here (Article I / S11). Strings are ``tr()``-wrapped and re-set
on :data:`QEvent.Type.LanguageChange` (F5); every control is keyboard-reachable and
legible in both themes.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QEvent
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import PALETTE_EXTRACT_DEFAULT_N
from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import QuantizeError, kmeans, median_cut

#: Extraction method tokens carried in the method combo's item data.
METHOD_MEDIAN_CUT = "median_cut"
METHOD_KMEANS = "kmeans"


def image_to_buffer(image: QImage) -> PixelBuffer:
    """Convert a :class:`QImage` to an RGBA :class:`PixelBuffer`.

    Presentation-side image decode only (no colour maths): the image is copied
    into a contiguous ``(H, W, 4)`` uint8 array and wrapped in a buffer that
    :mod:`~pixelart_creator.logic.quantize` consumes.
    """
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    raw = np.frombuffer(bytes(converted.constBits()), dtype=np.uint8)
    rows = raw.reshape((height, converted.bytesPerLine()))
    rgba = rows[:, : width * 4].reshape((height, width, 4)).copy()
    buffer = PixelBuffer(width, height, ColorMode.RGBA)
    buffer.data[:, :] = rgba
    return buffer


class Extract_Palette_Dialog(QDialog):
    """Load an image and extract a ``≤N`` palette (median-cut / k-means)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the image chooser, ``N`` spin, method combo, and buttons."""
        super().__init__(parent)
        self._source: Optional[PixelBuffer] = None
        self._result: Optional[Palette] = None

        self._path_label = QLabel(self)
        self._choose_button = QPushButton(self)
        self._choose_button.clicked.connect(self._on_choose_image)

        self._n_spin = QSpinBox(self)
        self._n_spin.setRange(1, MAX_PALETTE_SIZE)
        self._n_spin.setValue(PALETTE_EXTRACT_DEFAULT_N)

        self._method_combo = QComboBox(self)
        self._method_combo.addItem("", METHOD_MEDIAN_CUT)
        self._method_combo.addItem("", METHOD_KMEANS)

        self._n_label = QLabel(self)
        self._method_label = QLabel(self)
        form = QFormLayout()
        form.addRow(self._n_label, self._n_spin)
        form.addRow(self._method_label, self._method_combo)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._choose_button)
        layout.addWidget(self._path_label)
        layout.addLayout(form)
        layout.addWidget(self._buttons)
        self._retranslate()

    # -- public API -------------------------------------------------------

    def result_palette(self) -> Optional[Palette]:
        """Return the extracted palette after the dialog is accepted."""
        return self._result

    def target_count(self) -> int:
        """Return the chosen colour count ``N``."""
        return self._n_spin.value()

    def method(self) -> str:
        """Return the chosen extraction method token."""
        return self._method_combo.currentData()

    # -- slots ------------------------------------------------------------

    def _on_choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Choose Image"),
            "",
            self.tr("Images (*.png *.jpg *.jpeg *.bmp *.gif)"),
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(
                self, self.tr("Extract Palette"), self.tr("Could not load the image.")
            )
            return
        self._source = image_to_buffer(image)
        self._path_label.setText(path)
        self._ok_button.setEnabled(True)

    def _on_accept(self) -> None:
        if self._source is None:
            return
        n = self._n_spin.value()
        try:
            if self.method() == METHOD_KMEANS:
                self._result = kmeans(self._source, n)
            else:
                self._result = median_cut(self._source, n)
        except QuantizeError as exc:
            QMessageBox.warning(self, self.tr("Extract Palette"), str(exc))
            return
        self.accept()

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Extract Palette from Image"))
        self.setAccessibleName(self.tr("Extract palette dialog"))
        self._choose_button.setText(self.tr("Choose Image…"))
        self._path_label.setText(self.tr("No image chosen"))
        self._n_label.setText(self.tr("Colours (N)"))
        self._method_label.setText(self.tr("Method"))
        self._n_spin.setAccessibleName(self.tr("Number of colours"))
        self._method_combo.setAccessibleName(self.tr("Extraction method"))
        self._method_combo.setItemText(0, self.tr("Median cut (fast)"))
        self._method_combo.setItemText(1, self.tr("K-means (higher quality)"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = [
    "Extract_Palette_Dialog",
    "image_to_buffer",
    "METHOD_MEDIAN_CUT",
    "METHOD_KMEANS",
]
