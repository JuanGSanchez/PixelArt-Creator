"""Isometric-grid configuration dialog (REQ-P9-UI-004).

``Iso_Grid_Dialog`` mirrors the shipped
:class:`~pixelart_creator.ui.vanishing_point_dialog.Vanishing_Point_Dialog`
pattern for the isometric aid: a minimal numeric-fields dialog that reads the
active tab's :class:`~pixelart_creator.logic.grids.IsoGridConfig` and, on
accept, hands a new one to
:meth:`~pixelart_creator.ui.iso_grid_overlay.Iso_Grid_Overlay.set_config`. No
lattice geometry is computed here (Article I/S11) — the dialog only reads and
writes the value type; every numeric bound comes from ``logic/constants``
(S12).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_GRID_SPACING,
    MIN_GRID_SPACING,
)
from pixelart_creator.logic.grids import IsoGridConfig

#: Sane bounds for the ``W:H`` tile ratio field (2:1 dimetric default is 2.0;
#: true-iso is ~1.732). Not a lattice geometry decision — just a widget bound
#: keeping the field away from non-finite/degenerate input before it ever
#: reaches ``IsoGridConfig`` validation (S12).
_MIN_RATIO = 0.1
_MAX_RATIO = 10.0


class Iso_Grid_Dialog(QDialog):
    """Minimal isometric-grid configuration dialog (mirrors D-09's pattern)."""

    def __init__(
        self,
        config: IsoGridConfig,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the dialog pre-filled from the active ``config``."""
        super().__init__(parent)
        self._tile_width_label = QLabel(self)
        self._tile_width_spin = QSpinBox(self)
        self._tile_width_spin.setRange(MIN_GRID_SPACING, MAX_GRID_SPACING)

        self._ratio_label = QLabel(self)
        self._ratio_spin = QDoubleSpinBox(self)
        self._ratio_spin.setRange(_MIN_RATIO, _MAX_RATIO)
        self._ratio_spin.setDecimals(3)
        self._ratio_spin.setSingleStep(0.1)

        self._origin_x_label = QLabel(self)
        self._origin_x_spin = QDoubleSpinBox(self)
        self._origin_x_spin.setRange(-MAX_CANVAS_WIDTH, 2 * MAX_CANVAS_WIDTH)

        self._origin_y_label = QLabel(self)
        self._origin_y_spin = QDoubleSpinBox(self)
        self._origin_y_spin.setRange(-MAX_CANVAS_HEIGHT, 2 * MAX_CANVAS_HEIGHT)

        form = QFormLayout()
        form.addRow(self._tile_width_label, self._tile_width_spin)
        form.addRow(self._ratio_label, self._ratio_spin)
        form.addRow(self._origin_x_label, self._origin_x_spin)
        form.addRow(self._origin_y_label, self._origin_y_spin)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._buttons)

        self._load_config(config)
        self._retranslate()

    # -- config <-> widgets --------------------------------------------

    def _load_config(self, config: IsoGridConfig) -> None:
        """Seed every widget from ``config`` (tile width, ratio, origin)."""
        self._tile_width_spin.setValue(config.tile_width)
        self._ratio_spin.setValue(config.ratio)
        ox, oy = config.origin
        self._origin_x_spin.setValue(ox)
        self._origin_y_spin.setValue(oy)

    def iso_config(self) -> IsoGridConfig:
        """Assemble the :class:`IsoGridConfig` from the current widget state."""
        return IsoGridConfig(
            origin=(self._origin_x_spin.value(), self._origin_y_spin.value()),
            tile_width=self._tile_width_spin.value(),
            ratio=self._ratio_spin.value(),
        )

    # -- ui --------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Configure Isometric Grid"))
        self._tile_width_label.setText(self.tr("Tile width"))
        self._ratio_label.setText(self.tr("Tile ratio (W:H)"))
        self._origin_x_label.setText(self.tr("Origin X"))
        self._origin_y_label.setText(self.tr("Origin Y"))
        self._tile_width_spin.setAccessibleName(self.tr("Isometric tile width"))
        self._ratio_spin.setAccessibleName(self.tr("Isometric tile ratio"))
        self._origin_x_spin.setAccessibleName(self.tr("Isometric grid origin X"))
        self._origin_y_spin.setAccessibleName(self.tr("Isometric grid origin Y"))
        ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(self.tr("OK"))
        cancel_button = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(self.tr("Cancel"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate every string on ``QEvent.LanguageChange`` (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
