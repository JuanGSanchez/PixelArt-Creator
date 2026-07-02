"""Colour-cycling controls (REQ-P3-UI-012): non-destructive index-range cycling.

``Colour_Cycling_Panel`` selects a palette index range and plays / stops a
non-destructive preview that rotates that range at ``CYCLE_DEFAULT_FPS`` via a
:class:`QTimer`. The preview only rotates the *display* palette (the buffer is
untouched); pausing restores the base palette (SC-U012-2). The rotation maths live
in :func:`pixelart_creator.logic.palette_ops.cycle_palette`; committing a cycle
state to the buffer is a reversible
:func:`~pixelart_creator.logic.palette_ops.make_cycle_command` wrapped as one
:class:`~pixelart_creator.ui.commands.LogicCommand`. No maths live here
(Article I / S11). Strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (F5); the controls are keyboard-reachable and
legible in both themes.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QEvent, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import CYCLE_DEFAULT_FPS
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.palette_ops import cycle_palette

#: Milliseconds per cycling tick, derived from the tuning FPS (S12).
_TICK_MS = max(1, int(round(1000 / CYCLE_DEFAULT_FPS)))


class Colour_Cycling_Panel(QWidget):
    """Index-range selector + play/stop preview + apply-as-command."""

    #: Emitted with a list of display colours to preview (rotated palette).
    previewColors = Signal(object)
    #: Emitted with ``(start, end, step)`` when Apply commits the cycle state.
    applyRequested = Signal(int, int, int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the range spins, play/stop, and apply controls."""
        super().__init__(parent)
        self._base_colors: List[RGBA] = []
        self._offset = 0

        self._title = QLabel(self)
        self._start_spin = QSpinBox(self)
        self._end_spin = QSpinBox(self)
        self._step_spin = QSpinBox(self)
        self._step_spin.setRange(1, 255)
        self._step_spin.setValue(1)
        for spin in (self._start_spin, self._end_spin):
            spin.setRange(0, 255)
        self._end_spin.setValue(1)

        self._start_label = QLabel(self)
        self._end_label = QLabel(self)
        self._step_label = QLabel(self)
        self._play_button = QPushButton(self)
        self._play_button.setCheckable(True)
        self._play_button.toggled.connect(self._on_play_toggled)
        self._apply_button = QPushButton(self)
        self._apply_button.clicked.connect(self._on_apply)

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

        range_row = QHBoxLayout()
        range_row.addWidget(self._start_label)
        range_row.addWidget(self._start_spin)
        range_row.addWidget(self._end_label)
        range_row.addWidget(self._end_spin)
        range_row.addWidget(self._step_label)
        range_row.addWidget(self._step_spin)
        button_row = QHBoxLayout()
        button_row.addWidget(self._play_button)
        button_row.addWidget(self._apply_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addLayout(range_row)
        layout.addLayout(button_row)
        layout.addStretch(1)
        self._retranslate()

    # -- binding ----------------------------------------------------------

    def set_palette(self, palette: Palette) -> None:
        """Bind the active palette (its colours are the preview base)."""
        self._base_colors = palette.colors()
        upper = max(0, len(self._base_colors) - 1)
        self._start_spin.setMaximum(max(upper, 0))
        self._end_spin.setMaximum(max(upper, 0))
        if self._end_spin.value() > upper:
            self._end_spin.setValue(upper)

    def stop(self) -> None:
        """Stop cycling and restore the base palette (idempotent)."""
        if self._play_button.isChecked():
            self._play_button.setChecked(False)
        else:
            self._reset_preview()

    # -- slots ------------------------------------------------------------

    def _on_play_toggled(self, playing: bool) -> None:
        if playing:
            self._offset = 0
            self._timer.start()
        else:
            self._timer.stop()
            self._reset_preview()

    def _on_tick(self) -> None:
        start, end, step = self._range()
        if not self._base_colors or end < start:
            return
        self._offset += step
        try:
            rotated = cycle_palette(
                Palette(self._base_colors), start, end, self._offset
            )
        except Exception:  # noqa: BLE001 - a bad range never crashes the preview.
            return
        self.previewColors.emit(rotated.colors())

    def _reset_preview(self) -> None:
        self._offset = 0
        if self._base_colors:
            self.previewColors.emit(list(self._base_colors))

    def _on_apply(self) -> None:
        self.stop()
        start, end, step = self._range()
        self.applyRequested.emit(start, end, step)

    def _range(self) -> tuple[int, int, int]:
        return self._start_spin.value(), self._end_spin.value(), self._step_spin.value()

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self._title.setText(self.tr("Colour Cycling"))
        self.setAccessibleName(self.tr("Colour cycling panel"))
        self._start_label.setText(self.tr("Start"))
        self._end_label.setText(self.tr("End"))
        self._step_label.setText(self.tr("Step"))
        self._start_spin.setAccessibleName(self.tr("Cycle range start index"))
        self._end_spin.setAccessibleName(self.tr("Cycle range end index"))
        self._step_spin.setAccessibleName(self.tr("Cycle step"))
        self._play_button.setText(self.tr("Play / Stop"))
        self._apply_button.setText(self.tr("Apply"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Colour_Cycling_Panel"]
