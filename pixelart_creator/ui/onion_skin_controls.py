"""Onion-skin controls — toggle + prev/next counts + tint (REQ-P5-UI-011/-012).

``Onion_Skin_Controls`` is a **view-settings** panel (no undo, CL-13): an enable
toggle (REQ-P5-UI-011), previous/next ghost **count** spin boxes bounded by
``0..MAX_ONION_SKIN_FRAMES`` and defaulting to ``DEFAULT_ONION_PREV`` /
``DEFAULT_ONION_NEXT`` (1/1), and a **tint** swatch for each side defaulting to
``ONION_TINT_PREV`` (red = previous) / ``ONION_TINT_NEXT`` (blue = next, CL-4).

Changing any control emits :data:`settingsChanged` with the current settings; the
shell forwards them to the canvas scene, which computes the overlay via the Qt-free
:func:`~pixelart_creator.logic.animation.onion_overlay` (all onion compositing /
distance-fade / z-order maths stay in ``logic/`` — this widget only chooses the
counts + tint, S11). The overlay is suppressed during playback (CL-11).

All strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (REQ-P5-UI-019); controls carry accessible names
and are keyboard-reachable (REQ-P5-UI-017); the tint swatches are content-overlay
colours (from constants), legible in both themes (REQ-P5-UI-018).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from pixelart_creator.logic.color import RGBA
from pixelart_creator.logic.constants import (
    DEFAULT_ONION_NEXT,
    DEFAULT_ONION_PREV,
    MAX_ONION_SKIN_FRAMES,
    ONION_TINT_NEXT,
    ONION_TINT_PREV,
)


@dataclass(frozen=True)
class OnionSettings:
    """A snapshot of the onion view settings (no undo — CL-13)."""

    enabled: bool
    prev_count: int
    next_count: int
    tint_prev: RGBA
    tint_next: RGBA


class Onion_Skin_Controls(QWidget):
    """Onion toggle + prev/next count + tint pickers (REQ-P5-UI-011/-012)."""

    #: Emitted with the current :class:`OnionSettings` on any change (live update).
    settingsChanged = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the enable toggle, prev/next counts and tint pickers."""
        super().__init__(parent)
        self._tint_prev: RGBA = ONION_TINT_PREV
        self._tint_next: RGBA = ONION_TINT_NEXT

        self._enable_check = QCheckBox(self)
        self._enable_check.toggled.connect(self._emit)

        self._prev_spin = QSpinBox(self)
        self._prev_spin.setRange(0, MAX_ONION_SKIN_FRAMES)
        self._prev_spin.setValue(DEFAULT_ONION_PREV)
        self._prev_spin.valueChanged.connect(self._emit)

        self._next_spin = QSpinBox(self)
        self._next_spin.setRange(0, MAX_ONION_SKIN_FRAMES)
        self._next_spin.setValue(DEFAULT_ONION_NEXT)
        self._next_spin.valueChanged.connect(self._emit)

        self._prev_tint_button = QPushButton(self)
        self._prev_tint_button.clicked.connect(self._pick_prev_tint)
        self._next_tint_button = QPushButton(self)
        self._next_tint_button.clicked.connect(self._pick_next_tint)
        self._paint_swatch(self._prev_tint_button, self._tint_prev)
        self._paint_swatch(self._next_tint_button, self._tint_next)

        prev_row = QHBoxLayout()
        prev_row.setContentsMargins(0, 0, 0, 0)
        prev_row.addWidget(self._prev_spin)
        prev_row.addWidget(self._prev_tint_button)
        next_row = QHBoxLayout()
        next_row.setContentsMargins(0, 0, 0, 0)
        next_row.addWidget(self._next_spin)
        next_row.addWidget(self._next_tint_button)

        self._form = QFormLayout(self)
        self._form.addRow(self._enable_check)
        self._prev_label = self._form_row(self.tr("Previous frames"), prev_row)
        self._next_label = self._form_row(self.tr("Next frames"), next_row)

        self._retranslate()

    def _form_row(self, label_text: str, row_layout: QHBoxLayout) -> "QLabel":
        label = QLabel(label_text, self)
        container = QWidget(self)
        container.setLayout(row_layout)
        self._form.addRow(label, container)
        return label

    # -- queries ----------------------------------------------------------

    def settings(self) -> OnionSettings:
        """Return the current onion view settings."""
        return OnionSettings(
            enabled=self._enable_check.isChecked(),
            prev_count=self._prev_spin.value(),
            next_count=self._next_spin.value(),
            tint_prev=self._tint_prev,
            tint_next=self._tint_next,
        )

    # -- tint pickers -----------------------------------------------------

    def _pick_prev_tint(self) -> None:
        color = self._ask_color(self._tint_prev, self.tr("Previous-frame tint"))
        if color is not None:
            self._tint_prev = color
            self._paint_swatch(self._prev_tint_button, color)
            self._emit()

    def _pick_next_tint(self) -> None:
        color = self._ask_color(self._tint_next, self.tr("Next-frame tint"))
        if color is not None:
            self._tint_next = color
            self._paint_swatch(self._next_tint_button, color)
            self._emit()

    def _ask_color(self, current: RGBA, title: str) -> Optional[RGBA]:
        initial = QColor(*current)
        chosen = QColorDialog.getColor(
            initial,
            self,
            title,
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not chosen.isValid():
            return None
        return (chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())

    @staticmethod
    def _paint_swatch(button: QPushButton, color: RGBA) -> None:
        """Fill a tint button with its colour (role-independent overlay swatch)."""
        r, g, b, a = color
        button.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, {a}); min-width: 24px;"
        )

    # -- emit -------------------------------------------------------------

    def _emit(self, *_args: object) -> None:
        self.settingsChanged.emit(self.settings())

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Onion skin controls"))
        self._enable_check.setText(self.tr("Enable onion skinning"))
        self._enable_check.setAccessibleName(self.tr("Onion skin toggle"))
        self._prev_label.setText(self.tr("Previous frames"))
        self._next_label.setText(self.tr("Next frames"))
        self._prev_spin.setAccessibleName(self.tr("Previous onion frame count"))
        self._prev_spin.setToolTip(self.tr("How many earlier frames to ghost"))
        self._next_spin.setAccessibleName(self.tr("Next onion frame count"))
        self._next_spin.setToolTip(self.tr("How many later frames to ghost"))
        self._prev_tint_button.setText(self.tr("Tint…"))
        self._prev_tint_button.setAccessibleName(self.tr("Previous-frame tint"))
        self._next_tint_button.setText(self.tr("Tint…"))
        self._next_tint_button.setAccessibleName(self.tr("Next-frame tint"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the onion-skin control labels on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
