# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Scale dialog — nearest-neighbour resize target (REQ-P2-UI-009).

``Scale_Dialog`` collects a new width/height (or a uniform factor that drives
them) for ``logic.transform.scale_nearest``; it holds **no** scaling math (S11) —
the shell applies the transform as one :class:`QUndoCommand`. The factor range
is **derived from the seeded source size** — ``[1 / src_w, MAX_CANVAS_WIDTH /
src_w]`` (REQ-CSD-UI-004; ``plan.md`` §5.5) — never from a fixed factor
constant, so every reachable target dimension up to ``MAX_CANVAS_*`` has a
factor that can reach it. Bounds otherwise come from ``logic.constants``
(``MAX_CANVAS_*``); no magic numbers here (S12). All strings are
``tr()``-wrapped and re-set on ``QEvent.LanguageChange`` (F5).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH


class Scale_Dialog(QDialog):
    """Modal dialog returning a nearest-neighbour scale target size."""

    def __init__(
        self, width: int, height: int, parent: Optional[QWidget] = None
    ) -> None:
        """Build the dialog seeded with the current ``width`` x ``height``."""
        super().__init__(parent)
        self._src_w = int(width)
        self._src_h = int(height)
        self._updating = False

        self._factor = QDoubleSpinBox(self)
        self._factor.setDecimals(4)
        self._factor.setRange(1.0 / self._src_w, MAX_CANVAS_WIDTH / self._src_w)
        self._factor.setSingleStep(0.5)
        self._factor.setValue(1.0)
        self._factor.valueChanged.connect(self._on_factor_changed)

        self._width = QSpinBox(self)
        self._width.setRange(1, MAX_CANVAS_WIDTH)
        self._width.setValue(self._src_w)
        self._width.valueChanged.connect(self._on_size_changed)

        self._height = QSpinBox(self)
        self._height.setRange(1, MAX_CANVAS_HEIGHT)
        self._height.setValue(self._src_h)
        self._height.valueChanged.connect(self._on_size_changed)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        self._factor_label = QLabel(self)
        self._width_label = QLabel(self)
        self._height_label = QLabel(self)
        self._form = QFormLayout(self)
        self._form.addRow(self._factor_label, self._factor)
        self._form.addRow(self._width_label, self._width)
        self._form.addRow(self._height_label, self._height)
        self._form.addRow(self._buttons)
        self._retranslate()

    # -- result ----------------------------------------------------------

    def target_size(self) -> Tuple[int, int]:
        """Return the chosen ``(width, height)`` target in pixels."""
        return int(self._width.value()), int(self._height.value())

    # -- slots -----------------------------------------------------------

    def _on_factor_changed(self, factor: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._width.setValue(max(1, round(self._src_w * factor)))
        self._height.setValue(max(1, round(self._src_h * factor)))
        self._updating = False

    def _on_size_changed(self, _value: int) -> None:
        if self._updating:
            return
        self._updating = True
        if self._src_w:
            self._factor.setValue(self._width.value() / self._src_w)
        self._updating = False

    # -- i18n ------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Scale Canvas"))
        self.setAccessibleName(self.tr("Scale canvas dialog"))
        self._factor.setAccessibleName(self.tr("Scale factor"))
        self._width.setAccessibleName(self.tr("Target width in pixels"))
        self._height.setAccessibleName(self.tr("Target height in pixels"))
        self._factor_label.setText(self.tr("Factor"))
        self._width_label.setText(self.tr("Width (px)"))
        self._height_label.setText(self.tr("Height (px)"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
