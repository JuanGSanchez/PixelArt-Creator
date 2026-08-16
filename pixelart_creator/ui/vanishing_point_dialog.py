"""Vanishing-point configuration dialog (REQ-P9-UI-005, D-09).

``Vanishing_Point_Dialog`` is the minimal build the D-09 answer asked for: a
1-/2-/3-point mode selector plus one numeric X/Y position pair per active
vanishing point and a horizon-Y field, assembling the
:class:`~pixelart_creator.logic.grids.PerspectiveConfig` the pure
``logic/grids`` construction (:func:`~pixelart_creator.logic.grids.
perspective_guide_lines`) and snap (:func:`~pixelart_creator.logic.grids.
perspective_snap`) already consume via
:meth:`~pixelart_creator.ui.perspective_grid_overlay.Perspective_Grid_Overlay.
set_config`. Drag handles on the canvas are registered future polish and are
deliberately **not** built here (the D-09 answer). No perspective geometry is
computed in this widget (S11) — it only reads/writes the value type; every
numeric bound comes from ``logic/constants`` (S12).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_PERSPECTIVE_VANISHING_POINTS,
)
from pixelart_creator.logic.grids import PerspectiveConfig, VanishingPoint


class Vanishing_Point_Dialog(QDialog):
    """Minimal 1-/2-/3-point vanishing-point configuration dialog (D-09)."""

    def __init__(
        self,
        config: PerspectiveConfig,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the dialog pre-filled from the active ``config``."""
        super().__init__(parent)
        self._mode_label = QLabel(self)
        self._mode_combo = QComboBox(self)
        for point_count in range(1, MAX_PERSPECTIVE_VANISHING_POINTS + 1):
            self._mode_combo.addItem("", userData=point_count)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._horizon_label = QLabel(self)
        self._horizon_spin = QDoubleSpinBox(self)
        self._horizon_spin.setRange(-MAX_CANVAS_HEIGHT, 2 * MAX_CANVAS_HEIGHT)

        self._vp_groups: List[QGroupBox] = []
        self._vp_x: List[QDoubleSpinBox] = []
        self._vp_y: List[QDoubleSpinBox] = []
        self._vp_x_labels: List[QLabel] = []
        self._vp_y_labels: List[QLabel] = []
        vp_layout = QVBoxLayout()
        for _ in range(MAX_PERSPECTIVE_VANISHING_POINTS):
            group = QGroupBox(self)
            x_spin = QDoubleSpinBox(group)
            x_spin.setRange(-MAX_CANVAS_WIDTH, 2 * MAX_CANVAS_WIDTH)
            y_spin = QDoubleSpinBox(group)
            y_spin.setRange(-MAX_CANVAS_HEIGHT, 2 * MAX_CANVAS_HEIGHT)
            form = QFormLayout(group)
            x_label = QLabel(group)
            y_label = QLabel(group)
            form.addRow(x_label, x_spin)
            form.addRow(y_label, y_spin)
            self._vp_groups.append(group)
            self._vp_x.append(x_spin)
            self._vp_y.append(y_spin)
            self._vp_x_labels.append(x_label)
            self._vp_y_labels.append(y_label)
            vp_layout.addWidget(group)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._mode_label)
        layout.addWidget(self._mode_combo)
        layout.addWidget(self._horizon_label)
        layout.addWidget(self._horizon_spin)
        layout.addLayout(vp_layout)
        layout.addWidget(self._buttons)

        self._load_config(config)
        self._retranslate()

    # -- config <-> widgets ------------------------------------------------

    def _load_config(self, config: PerspectiveConfig) -> None:
        """Seed every widget from ``config`` (mode, horizon, finite VP positions)."""
        count = max(
            1, min(len(config.vanishing_points), MAX_PERSPECTIVE_VANISHING_POINTS)
        )
        self._mode_combo.setCurrentIndex(count - 1)
        self._horizon_spin.setValue(config.horizon_y)
        for index, vp in enumerate(
            config.vanishing_points[:MAX_PERSPECTIVE_VANISHING_POINTS]
        ):
            if vp.position is not None:
                self._vp_x[index].setValue(vp.position[0])
                self._vp_y[index].setValue(vp.position[1])
        self._on_mode_changed(self._mode_combo.currentIndex())

    def perspective_config(self) -> PerspectiveConfig:
        """Assemble the :class:`PerspectiveConfig` from the current widget state.

        Builds exactly ``mode`` finite vanishing points (one per visible VP
        group) — a pseudo-VP (direction-only, at infinity) is not offered by
        this minimal dialog.
        """
        mode_data = self._mode_combo.currentData()
        mode = int(mode_data) if mode_data is not None else 1
        vanishing_points = tuple(
            VanishingPoint(position=(self._vp_x[i].value(), self._vp_y[i].value()))
            for i in range(mode)
        )
        return PerspectiveConfig(
            mode=mode,
            vanishing_points=vanishing_points,
            horizon_y=self._horizon_spin.value(),
        )

    # -- ui ------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        mode_data = self._mode_combo.currentData()
        mode = int(mode_data) if mode_data is not None else 1
        for index, group in enumerate(self._vp_groups):
            group.setVisible(index < mode)

    def _mode_labels(self) -> List[str]:
        return [
            self.tr("1-point"),
            self.tr("2-point"),
            self.tr("3-point"),
        ][:MAX_PERSPECTIVE_VANISHING_POINTS]

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Configure Perspective"))
        self._mode_label.setText(self.tr("Vanishing points"))
        self._horizon_label.setText(self.tr("Horizon Y"))
        self._mode_combo.setAccessibleName(self.tr("Vanishing-point mode"))
        self._horizon_spin.setAccessibleName(self.tr("Horizon Y position"))
        for row, text in enumerate(self._mode_labels()):
            self._mode_combo.setItemText(row, text)
        for index, group in enumerate(self._vp_groups):
            title = self.tr("Vanishing point {n}").format(n=index + 1)
            group.setTitle(title)
            self._vp_x_labels[index].setText(self.tr("X"))
            self._vp_y_labels[index].setText(self.tr("Y"))
            self._vp_x[index].setAccessibleName(
                self.tr("Vanishing point {n} X").format(n=index + 1)
            )
            self._vp_y[index].setAccessibleName(
                self.tr("Vanishing point {n} Y").format(n=index + 1)
            )
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
