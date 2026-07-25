"""Symmetry-axis selector panel (REQ-P2-UI-011).

``Symmetry_Panel`` exposes the active symmetry axis (none / vertical / horizontal
/ both / diagonal, ``logic.symmetry.SymmetryAxis``) as a keyboard-reachable combo box
and emits :attr:`axisChanged` when it changes; the shell routes strokes through
``logic.symmetry.mirror`` while an axis is active. Presentation only — no mirror
math here (S11). Strings are ``tr()``-wrapped and re-set on
``QEvent.LanguageChange`` (F5).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from pixelart_creator.logic.symmetry import SymmetryAxis


class Symmetry_Panel(QWidget):
    """A combo-box selector for the active symmetry axis."""

    #: Emitted with the newly selected :class:`SymmetryAxis`.
    axisChanged = Signal(object)

    #: Axis order shown in the combo (value stored in the item's user data).
    _AXES: List[SymmetryAxis] = [
        SymmetryAxis.NONE,
        SymmetryAxis.VERTICAL,
        SymmetryAxis.HORIZONTAL,
        SymmetryAxis.BOTH,
        SymmetryAxis.DIAGONAL,
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the axis selector defaulting to ``SymmetryAxis.NONE``."""
        super().__init__(parent)
        self._label = QLabel(self)
        self._combo = QComboBox(self)
        for axis in self._AXES:
            self._combo.addItem("", userData=axis)
        self._combo.currentIndexChanged.connect(self._on_index_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._combo)
        self._retranslate()

    def selected_axis(self) -> SymmetryAxis:
        """Return the currently selected :class:`SymmetryAxis`."""
        axis = self._combo.currentData()
        return axis if isinstance(axis, SymmetryAxis) else SymmetryAxis.NONE

    def _on_index_changed(self, _index: int) -> None:
        self.axisChanged.emit(self.selected_axis())

    def _axis_labels(self) -> List[str]:
        return [
            self.tr("Off"),
            self.tr("Vertical"),
            self.tr("Horizontal"),
            self.tr("Both"),
            self.tr("Diagonal"),
        ]

    def _retranslate(self) -> None:
        self._label.setText(self.tr("Symmetry"))
        self.setAccessibleName(self.tr("Symmetry axis panel"))
        self._combo.setAccessibleName(self.tr("Symmetry axis"))
        for row, text in enumerate(self._axis_labels()):
            self._combo.setItemText(row, text)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
