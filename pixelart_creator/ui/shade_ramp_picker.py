# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shade / tint / tone ramp picker (REQ-P3-UI-007).

``Shade_Ramp_Picker`` shows the shade, tint, and tone ramps of a base colour —
computed by :mod:`pixelart_creator.logic.color_theory` (the ramp maths live in
``logic/``, C1) — as rows of keyboard-reachable swatch buttons (``RAMP_STEP_COUNT``
steps each, SC-U007-1). Activating a swatch applies that colour to the active
swatch (:attr:`colorPicked`); an *Add ramp to palette* button appends a whole ramp
(:attr:`rampAddRequested`). The widget holds **no** colour maths (Article I / S11);
strings are ``tr()``-wrapped and re-set on :data:`QEvent.Type.LanguageChange` (F5),
and the ramps stay legible in both themes.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import BLACK, RGBA, to_hex
from pixelart_creator.logic.color_theory import shade_ramp, tint_ramp, tone_ramp
from pixelart_creator.logic.constants import RAMP_STEP_COUNT

#: Edge of a ramp swatch button, px (presentation-only sizing).
_SWATCH_PX = 24


class _RampSwatch(QToolButton):
    """A keyboard-reachable button showing one ramp colour."""

    picked = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color: RGBA = BLACK
        self.setFixedSize(_SWATCH_PX, _SWATCH_PX)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(lambda: self.picked.emit(self._color))

    def set_color(self, color: RGBA) -> None:
        """Set the swatch fill, accessible name, and tooltip to ``color``."""
        self._color = color
        pixmap = QPixmap(_SWATCH_PX - 4, _SWATCH_PX - 4)
        pixmap.fill(QColor(*color))
        self.setIcon(QIcon(pixmap))
        label = to_hex(color)
        self.setToolTip(label)
        self.setAccessibleName(label)

    def color(self) -> RGBA:
        """Return this swatch's RGBA tuple."""
        return self._color


class Shade_Ramp_Picker(QWidget):
    """Shows the shade / tint / tone ramps of a base colour; pick or add."""

    #: Emitted with an RGBA tuple when a ramp swatch is activated.
    colorPicked = Signal(object)
    #: Emitted with a list of RGBA colours when a whole ramp is added.
    rampAddRequested = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the three ramp rows and their Add buttons."""
        super().__init__(parent)
        self._base: RGBA = BLACK

        self._title = QLabel(self)
        self._shade_label = QLabel(self)
        self._tint_label = QLabel(self)
        self._tone_label = QLabel(self)
        self._shade = self._make_row()
        self._tint = self._make_row()
        self._tone = self._make_row()
        self._add_shade = QPushButton(self)
        self._add_shade.clicked.connect(
            lambda: self.rampAddRequested.emit(shade_ramp(self._base))
        )
        self._add_tint = QPushButton(self)
        self._add_tint.clicked.connect(
            lambda: self.rampAddRequested.emit(tint_ramp(self._base))
        )
        self._add_tone = QPushButton(self)
        self._add_tone.clicked.connect(
            lambda: self.rampAddRequested.emit(tone_ramp(self._base))
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addLayout(
            self._row_layout(self._shade_label, self._shade, self._add_shade)
        )
        layout.addLayout(self._row_layout(self._tint_label, self._tint, self._add_tint))
        layout.addLayout(self._row_layout(self._tone_label, self._tone, self._add_tone))
        layout.addStretch(1)
        self._retranslate()
        self.set_base_color(BLACK)

    # -- construction helpers --------------------------------------------

    def _make_row(self) -> List[_RampSwatch]:
        swatches: List[_RampSwatch] = []
        for _ in range(RAMP_STEP_COUNT):
            swatch = _RampSwatch(self)
            swatch.picked.connect(self.colorPicked)
            swatches.append(swatch)
        return swatches

    @staticmethod
    def _row_layout(
        label: QLabel, swatches: List[_RampSwatch], add_button: QPushButton
    ) -> QVBoxLayout:
        buttons = QHBoxLayout()
        for swatch in swatches:
            buttons.addWidget(swatch)
        buttons.addWidget(add_button)
        buttons.addStretch(1)
        column = QVBoxLayout()
        column.addWidget(label)
        column.addLayout(buttons)
        return column

    # -- public API -------------------------------------------------------

    def set_base_color(self, color: RGBA) -> None:
        """Recompute + display the three ramps for base ``color`` (from logic)."""
        self._base = color
        self._fill(self._shade, shade_ramp(color))
        self._fill(self._tint, tint_ramp(color))
        self._fill(self._tone, tone_ramp(color))

    @staticmethod
    def _fill(swatches: List[_RampSwatch], colors: List[RGBA]) -> None:
        for swatch, color in zip(swatches, colors):
            swatch.set_color(color)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Shade Ramps"))
        self.setAccessibleName(self.tr("Shade ramp picker"))
        self._shade_label.setText(self.tr("Shades (toward black)"))
        self._tint_label.setText(self.tr("Tints (toward white)"))
        self._tone_label.setText(self.tr("Tones (toward grey)"))
        for button in (self._add_shade, self._add_tint, self._add_tone):
            button.setText(self.tr("Add to Palette"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Shade_Ramp_Picker"]
