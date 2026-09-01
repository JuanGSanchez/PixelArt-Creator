# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Symmetry-axis selector + position panel (REQ-P2-UI-011, D-28/CF-93).

``Symmetry_Panel`` exposes the active symmetry axis (none / vertical / horizontal
/ both / diagonal, ``logic.symmetry.SymmetryAxis``) as a keyboard-reachable combo box
and emits :attr:`axisChanged` when it changes; the shell routes strokes through
``logic.symmetry.mirror`` while an axis is active. It also exposes the mirror
CENTRE (``logic.symmetry.mirror``'s ``axis_pos`` seam, CL-9) as a pair of
spinboxes bound to the active document's dimensions and emits
:attr:`axisPositionChanged` with an ``Optional[Tuple[int, int]]`` -- ``None``
until the user actually edits a spinbox, so untouched behaviour is unchanged
(``mirror`` then falls back to computing the canvas centre itself). Drag-on-
canvas positioning is registered future polish and is deliberately NOT built
here. Presentation only — no mirror math lives in this widget (S11); the
default-centre value the spinboxes seed from is a plain midpoint display
number, not domain math. Strings are ``tr()``-wrapped and re-set on
``QEvent.LanguageChange`` (F5).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH
from pixelart_creator.logic.symmetry import SymmetryAxis


class Symmetry_Panel(QWidget):
    """A combo-box selector for the active symmetry axis, plus its centre."""

    #: Emitted with the newly selected :class:`SymmetryAxis`.
    axisChanged = Signal(object)
    #: Emitted with the mirror centre as ``Optional[Tuple[int, int]]`` once the
    #: user edits a position spinbox (``None`` = unset, ``mirror`` defaults to
    #: the canvas centre itself, CL-9). Never emitted from programmatic
    #: :meth:`set_canvas_size` calls, so a resize alone never fabricates a
    #: user-authored position.
    axisPositionChanged = Signal(object)

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

        # Axis-position control (D-28/CF-93): a spinbox pair bound to the
        # active document's dimensions (never MAX_CANVAS_* inlined past the
        # constants import). Drag-on-canvas positioning is future polish and
        # is deliberately not built here.
        self._pos_label = QLabel(self)
        self._x_label = QLabel(self)
        self._y_label = QLabel(self)
        self._x_spin = QSpinBox(self)
        self._y_spin = QSpinBox(self)
        self._reset_button = QPushButton(self)
        self._canvas_width = MAX_CANVAS_WIDTH
        self._canvas_height = MAX_CANVAS_HEIGHT
        self._position_dirty = False
        self._apply_canvas_bounds(MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)
        self._x_spin.valueChanged.connect(self._on_position_edited)
        self._y_spin.valueChanged.connect(self._on_position_edited)
        self._reset_button.clicked.connect(self._on_reset_clicked)

        pos_row = QHBoxLayout()
        pos_row.addWidget(self._x_label)
        pos_row.addWidget(self._x_spin)
        pos_row.addWidget(self._y_label)
        pos_row.addWidget(self._y_spin)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._combo)
        layout.addWidget(self._pos_label)
        layout.addLayout(pos_row)
        layout.addWidget(self._reset_button)
        self._retranslate()

    def selected_axis(self) -> SymmetryAxis:
        """Return the currently selected :class:`SymmetryAxis`."""
        axis = self._combo.currentData()
        return axis if isinstance(axis, SymmetryAxis) else SymmetryAxis.NONE

    def axis_position(self) -> Optional[Tuple[int, int]]:
        """Return the user-set mirror centre, or ``None`` while untouched.

        ``None`` preserves current behaviour exactly: ``logic.symmetry.mirror``
        computes the canvas centre itself when ``axis_pos`` is ``None`` (CL-9).
        """
        if not self._position_dirty:
            return None
        return (self._x_spin.value(), self._y_spin.value())

    def set_canvas_size(self, width: int, height: int) -> None:
        """Rebind the spinbox ranges to the active document's ``width``/``height``.

        Resets to the (unset) centre default -- a resize must never silently
        keep a stale, now out-of-bounds, user position. Emits nothing: this is
        a programmatic re-bind, not a user edit.
        """
        self._apply_canvas_bounds(width, height)
        self._position_dirty = False

    def _apply_canvas_bounds(self, width: int, height: int) -> None:
        self._canvas_width = max(1, int(width))
        self._canvas_height = max(1, int(height))
        default_x = (self._canvas_width - 1) // 2
        default_y = (self._canvas_height - 1) // 2
        for spin, upper, default in (
            (self._x_spin, self._canvas_width - 1, default_x),
            (self._y_spin, self._canvas_height - 1, default_y),
        ):
            spin.blockSignals(True)
            spin.setRange(0, upper)
            spin.setValue(default)
            spin.blockSignals(False)

    def _on_position_edited(self, _value: int) -> None:
        self._position_dirty = True
        self.axisPositionChanged.emit(self.axis_position())

    def _on_reset_clicked(self) -> None:
        self._apply_canvas_bounds(self._canvas_width, self._canvas_height)
        self._position_dirty = False
        self.axisPositionChanged.emit(None)

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
        self._pos_label.setText(self.tr("Axis position"))
        self._x_label.setText(self.tr("X"))
        self._y_label.setText(self.tr("Y"))
        self._reset_button.setText(self.tr("Reset to centre"))
        self.setAccessibleName(self.tr("Symmetry axis panel"))
        self._combo.setAccessibleName(self.tr("Symmetry axis"))
        self._x_spin.setAccessibleName(self.tr("Symmetry axis position X"))
        self._y_spin.setAccessibleName(self.tr("Symmetry axis position Y"))
        self._reset_button.setAccessibleName(
            self.tr("Reset symmetry axis position to centre")
        )
        for row, text in enumerate(self._axis_labels()):
            self._combo.setItemText(row, text)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
