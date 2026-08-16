"""RotSprite angle dialog with a live preview (REQ-P2-UI-010).

``RotSprite_Dialog`` collects an arbitrary rotation angle and shows a small live
preview of the rotated result. It holds **no** rotation math (S11): the preview
image is produced by a ``render`` callback the shell supplies (which calls
``logic.rotsprite.rotsprite`` on a thumbnail), and the shell applies the real
rotation as one :class:`QUndoCommand`. The UI adds **no** colour of its own — the
"no new colours" guarantee is a logic behaviour (REQ-P2-UI-010). Strings are
``tr()``-wrapped and re-set on ``QEvent.LanguageChange`` (F5).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

#: Angle input bounds, degrees (a full turn either way; not a domain tuning value).
_ANGLE_MIN = -360.0
_ANGLE_MAX = 360.0
#: Preview label edge, px (presentation-only sizing).
_PREVIEW_PX = 128

#: Renders a preview :class:`QImage` for a candidate angle (or ``None``).
PreviewRenderer = Callable[[float], Optional[QImage]]


class RotSprite_Dialog(QDialog):
    """Modal dialog returning an arbitrary rotation angle, with a live preview."""

    def __init__(
        self, render: PreviewRenderer, parent: Optional[QWidget] = None
    ) -> None:
        """Build the dialog; ``render`` produces the preview for a given angle."""
        super().__init__(parent)
        self._render = render

        self._angle = QDoubleSpinBox(self)
        self._angle.setDecimals(1)
        self._angle.setRange(_ANGLE_MIN, _ANGLE_MAX)
        self._angle.setSingleStep(15.0)
        self._angle.setValue(0.0)
        self._angle.valueChanged.connect(self._on_angle_changed)

        self._preview = QLabel(self)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(_PREVIEW_PX, _PREVIEW_PX)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        self._angle_label = QLabel(self)
        self._form = QFormLayout()
        self._form.addRow(self._angle_label, self._angle)
        layout.addLayout(self._form)
        layout.addWidget(self._preview)
        layout.addWidget(self._buttons)

        self._retranslate()
        self._on_angle_changed(0.0)

    # -- result ----------------------------------------------------------

    def angle(self) -> float:
        """Return the chosen rotation angle in degrees."""
        return float(self._angle.value())

    # -- slots -----------------------------------------------------------

    def _on_angle_changed(self, angle: float) -> None:
        image = self._render(angle)
        if image is None or image.isNull():
            self._preview.setText(self.tr("No preview"))
            return
        pixmap = QPixmap.fromImage(image).scaled(
            _PREVIEW_PX,
            _PREVIEW_PX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._preview.setPixmap(pixmap)

    # -- i18n ------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Rotate (RotSprite)"))
        self.setAccessibleName(self.tr("RotSprite rotation dialog"))
        self._angle.setAccessibleName(self.tr("Rotation angle in degrees"))
        self._preview.setAccessibleName(self.tr("Rotation preview"))
        self._angle_label.setText(self.tr("Angle (deg)"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
