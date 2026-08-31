"""Canva-style RGB colour wheel with live harmony swatches (REQ-P3-UI-005).

``Colour_Wheel_Widget`` renders a hue/saturation wheel — a
:class:`~PySide6.QtGui.QConicalGradient` for hue overlaid by a
:class:`~PySide6.QtGui.QRadialGradient` white→transparent for saturation, plus a
separate value/brightness slider (research F9 Topic 1). Dragging or clicking the
wheel picks a hue+saturation; the value slider sets brightness. Because a 2-D
wheel is not keyboard-usable on its own, the widget also exposes **numeric RGB +
HSV spin entries** — the accessible alternative that makes every colour reachable
without a mouse (SC-U005-5).

As the selection changes, the widget recomputes the theory harmonies
(complementary / analogous / triadic / split-complementary + shade/tint ramps) by
**calling** :mod:`pixelart_creator.logic.color_theory` on every move
(SC-U005-2) — the harmony *maths* live in ``logic/`` (C1); this widget only
renders and binds. ``QColor`` HSV APIs are used here only, in ``ui/`` (CL-2).
Every user-facing string is ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (F5). Emits :attr:`colorPicked` with the
picked :class:`~PySide6.QtGui.QColor` on any change that ADOPTS into the
wheel — a drag/nudge/spin edit, or a swatch double-click/keyboard activation.

**Amended 2026-08-31 (REQ-IS-UI-019/-020/-022/-030).** A harmony/shade/tint
swatch's SINGLE click no longer adopts into the wheel at all: it emits
:attr:`swatchPicked` with that swatch's own colour, paint-only, so the
circle's active colour is left unchanged. Only a swatch's double click or a
``Space``/``Return`` activation still adopts (:attr:`colorPicked`), and it
never paints. See ``_SwatchButton`` for the click/double-click
disambiguation this relies on.
"""

from __future__ import annotations

import math
from typing import List, Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.color import CHANNEL_MAX, RGBA, to_hex
from pixelart_creator.logic.color_theory import (
    analogous,
    complementary,
    shade_ramp,
    split_complementary,
    tetradic,
    tint_ramp,
    triadic,
)
from pixelart_creator.logic.constants import RAMP_STEP_COUNT

#: Hue at the top of the circle, in degrees (achromatic fallback keeps this hue).
_HUE_CIRCLE_DEG = 360.0
#: Number of conical-gradient stops sweeping the hue circle (six primaries + wrap).
_HUE_STOPS = 6
#: Edge of a harmony/preview swatch button, px (presentation-only sizing).
_SWATCH_PX = 22
#: Minimum wheel diameter, px (presentation-only sizing).
_WHEEL_MIN_PX = 180
#: Marker radius drawn at the current hue/saturation, px.
_MARKER_PX = 5.0
#: Keyboard nudge steps for the wheel (hue degrees / saturation fraction).
_KEY_HUE_STEP = 5.0
_KEY_SAT_STEP = 0.05


class _SwatchButton(QToolButton):
    """A small keyboard-reachable button showing one RGBA colour.

    Two gestures, two distinct signals (REQ-IS-UI-019/-020/-022, D-11):

    * :attr:`picked` — a single left click. PAINT-only: the caller must
      leave the active colour (the wheel) unchanged.
    * :attr:`activated` — a double left click, or ``Space``/``Return`` while
      focused. ADOPT-only: the caller must not paint.

    ``QAbstractButton.clicked`` fires on every press/release, including the
    first half of a double click, so a plain click→paint connection would
    also paint on the click that turns into a double click. The single-click
    paint is therefore deferred by the platform's double-click interval and
    cancelled if :meth:`mouseDoubleClickEvent` follows — the standard
    click/double-click disambiguation pattern.
    """

    #: Single left click — paint this swatch's colour, leave the wheel alone.
    picked = Signal(object)
    #: Double left click / Space / Return — adopt this swatch's colour into
    #: the wheel, paint nothing.
    activated = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color: RGBA = (0, 0, 0, CHANNEL_MAX)
        self._group = ""
        self.setFixedSize(_SWATCH_PX, _SWATCH_PX)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._single_click_timer = QTimer(self)
        self._single_click_timer.setSingleShot(True)
        self._single_click_timer.timeout.connect(self._emit_picked)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        # Defer: this click may turn out to be the first half of a double
        # click, in which case mouseDoubleClickEvent below cancels it.
        self._single_click_timer.start(QApplication.doubleClickInterval())

    def _emit_picked(self) -> None:
        self.picked.emit(self._color)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Adopt this swatch's colour on a left double click; paint nothing.

        Cancels the deferred single-click paint the first half of the
        gesture scheduled.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._single_click_timer.stop()
            self.activated.emit(self._color)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Space/Enter adopt this swatch's colour, identically to a double click."""
        key = event.key()
        if key in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activated.emit(self._color)
            event.accept()
            return
        super().keyPressEvent(event)

    def set_group(self, name: str) -> None:
        """Set the harmony group this swatch belongs to (announced to AT, A3)."""
        self._group = name
        self._refresh_accessibility()

    def set_color(self, color: RGBA) -> None:
        """Set the swatch fill and accessible name/tooltip to ``color``."""
        self._color = color
        pixmap = QPixmap(_SWATCH_PX - 6, _SWATCH_PX - 6)
        pixmap.fill(QColor(*color))
        self.setIcon(QIcon(pixmap))
        self._refresh_accessibility()

    def _refresh_accessibility(self) -> None:
        # Convey the swatch's harmony group to assistive tech (A11Y-COLHUB-3):
        # e.g. "Complementary #RRGGBB" so the group is announced with the colour.
        hex_label = to_hex(self._color, with_alpha=False)
        self.setToolTip(hex_label)
        label = f"{self._group} {hex_label}" if self._group else hex_label
        self.setAccessibleName(label)

    def color(self) -> RGBA:
        """Return this swatch's RGBA tuple."""
        return self._color


class _WheelPad(QWidget):
    """The 2-D hue (angle) + saturation (radius) wheel surface."""

    #: Emitted with ``(hue_degrees, saturation)`` when the user picks on the wheel.
    hueSatPicked = Signal(float, float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._hue = 0.0
        self._sat = 0.0
        self._value = 1.0
        self.setMinimumSize(_WHEEL_MIN_PX, _WHEEL_MIN_PX)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._retranslate()

    def set_hsv(self, hue: float, sat: float, value: float) -> None:
        """Update the displayed hue/saturation/value (no signal emitted)."""
        self._hue = hue % _HUE_CIRCLE_DEG
        self._sat = max(0.0, min(1.0, sat))
        self._value = max(0.0, min(1.0, value))
        self.update()

    def _geometry(self) -> tuple[float, float, float]:
        rect = self.rect()
        radius = min(rect.width(), rect.height()) / 2.0
        return rect.width() / 2.0, rect.height() / 2.0, radius

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        cx, cy, radius = self._geometry()
        if radius <= 0:
            return
        center = QPointF(cx, cy)
        circle = QRectF(cx - radius, cy - radius, 2 * radius, 2 * radius)

        path = QPainterPath()
        path.addEllipse(circle)
        painter.setClipPath(path)

        # Hue: conical gradient sweeping the six primaries counter-clockwise.
        cone = QConicalGradient(center, 0.0)
        for k in range(_HUE_STOPS + 1):
            pos = k / _HUE_STOPS
            cone.setColorAt(
                min(pos, 0.999999), QColor.fromHsvF(min(pos, 0.999999), 1.0, 1.0)
            )
        painter.fillRect(circle, cone)

        # Saturation: white at the centre fading to transparent at the rim.
        radial = QRadialGradient(center, radius)
        radial.setColorAt(0.0, QColor(255, 255, 255, 255))
        radial.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(circle, radial)

        # Value: darken the whole disc by (1 - value) so brightness is visible.
        darken = int(round((1.0 - self._value) * CHANNEL_MAX))
        if darken > 0:
            painter.fillRect(circle, QColor(0, 0, 0, darken))
        painter.setClipping(False)

        painter.setPen(QPen(QColor(0, 0, 0, 120), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(circle)

        # Selection marker at (hue angle, saturation radius).
        angle = math.radians(self._hue)
        mx = cx + math.cos(angle) * self._sat * radius
        my = cy - math.sin(angle) * self._sat * radius
        painter.setPen(QPen(QColor(0, 0, 0, 220), 2))
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawEllipse(QPointF(mx, my), _MARKER_PX, _MARKER_PX)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Highlight), 2))
            painter.drawEllipse(circle)

    def _pick_from_pos(self, pos: QPointF) -> None:
        cx, cy, radius = self._geometry()
        if radius <= 0:
            return
        dx = pos.x() - cx
        dy = cy - pos.y()
        sat = min(1.0, math.hypot(dx, dy) / radius)
        hue = math.degrees(math.atan2(dy, dx)) % _HUE_CIRCLE_DEG
        self._hue = hue
        self._sat = sat
        self.update()
        self.hueSatPicked.emit(hue, sat)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._pick_from_pos(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick_from_pos(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        hue, sat = self._hue, self._sat
        if key == Qt.Key.Key_Left:
            hue = (hue - _KEY_HUE_STEP) % _HUE_CIRCLE_DEG
        elif key == Qt.Key.Key_Right:
            hue = (hue + _KEY_HUE_STEP) % _HUE_CIRCLE_DEG
        elif key == Qt.Key.Key_Up:
            sat = min(1.0, sat + _KEY_SAT_STEP)
        elif key == Qt.Key.Key_Down:
            sat = max(0.0, sat - _KEY_SAT_STEP)
        else:
            super().keyPressEvent(event)
            return
        self._hue, self._sat = hue, sat
        self.update()
        self.hueSatPicked.emit(hue, sat)
        event.accept()

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Colour wheel"))
        self.setAccessibleDescription(
            self.tr(
                "Hue and saturation wheel; use the arrow keys or the numeric "
                "fields to pick a colour without a mouse"
            )
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Colour_Wheel_Widget(QWidget):
    """Canva-style RGB colour wheel with a value slider and live harmonies."""

    #: Emitted with the picked :class:`QColor` on any user-initiated change
    #: that ADOPTS into the wheel (wheel-pad drag, value slider, numeric
    #: entries, and a harmony/shade/tint swatch's double-click/keyboard
    #: activation — never a swatch's single click).
    colorPicked = Signal(QColor)
    #: Emitted with a harmony/shade/tint swatch's own RGBA tuple on a single
    #: left click (REQ-IS-UI-020). PAINT-only: the wheel's own selection is
    #: deliberately left unchanged, unlike :attr:`colorPicked`.
    swatchPicked = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the wheel, value slider, numeric entries, and harmony swatches."""
        super().__init__(parent)
        self._updating = False
        self._hue = 0.0
        self._sat = 0.0
        self._val = 0.0

        self._wheel = _WheelPad(self)
        self._wheel.hueSatPicked.connect(self._on_wheel_picked)

        self._value_slider = QSlider(Qt.Orientation.Vertical, self)
        self._value_slider.setRange(0, CHANNEL_MAX)
        self._value_slider.valueChanged.connect(self._on_value_changed)
        self._value_label = QLabel(self)

        self._spin_r = self._make_spin(
            CHANNEL_MAX, self._on_rgb_changed, self.tr("Red channel")
        )
        self._spin_g = self._make_spin(
            CHANNEL_MAX, self._on_rgb_changed, self.tr("Green channel")
        )
        self._spin_b = self._make_spin(
            CHANNEL_MAX, self._on_rgb_changed, self.tr("Blue channel")
        )
        self._spin_h = self._make_spin(
            int(_HUE_CIRCLE_DEG) - 1, self._on_hsv_changed, self.tr("Hue")
        )
        self._spin_s = self._make_spin(
            CHANNEL_MAX, self._on_hsv_changed, self.tr("Saturation")
        )
        self._spin_v = self._make_spin(
            CHANNEL_MAX, self._on_hsv_changed, self.tr("Value")
        )

        self._preview = QLabel(self)
        self._hex_label = QLabel(self)

        # Pre-created harmony swatch groups (updated in place on every change so
        # a live wheel move only re-fills icons — no layout thrash, F9/NFR-9).
        self._lbl_comp = QLabel(self)
        self._lbl_analog = QLabel(self)
        self._lbl_triadic = QLabel(self)
        self._lbl_tetradic = QLabel(self)
        self._lbl_split = QLabel(self)
        self._lbl_shades = QLabel(self)
        self._lbl_tints = QLabel(self)
        self._comp = self._make_swatches(1)
        self._analog = self._make_swatches(2)
        self._triadic = self._make_swatches(2)
        self._tetradic = self._make_swatches(3)
        self._split = self._make_swatches(2)
        self._shades = self._make_swatches(RAMP_STEP_COUNT)
        self._tints = self._make_swatches(RAMP_STEP_COUNT)

        self._build_layout()
        self._retranslate()
        self.set_color(QColor(0, 0, 0))

    # -- construction helpers --------------------------------------------

    def _make_spin(self, maximum: int, slot, accessible_name: str) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(0, maximum)
        spin.valueChanged.connect(slot)
        # Named at construction (not only in `_retranslate`) so the control is
        # never briefly unnamed, and so the name travels with the widget through
        # this shared factory rather than depending on the caller remembering
        # to add it elsewhere. `_retranslate` re-sets it on a language change.
        spin.setAccessibleName(accessible_name)
        return spin

    def _make_swatches(self, count: int) -> List[_SwatchButton]:
        buttons: List[_SwatchButton] = []
        for _ in range(count):
            button = _SwatchButton(self)
            button.picked.connect(self.swatchPicked)
            button.activated.connect(self._on_swatch_activated)
            buttons.append(button)
        return buttons

    def _swatch_row(self, label: QLabel, buttons: List[_SwatchButton]) -> QVBoxLayout:
        row = QHBoxLayout()
        for button in buttons:
            row.addWidget(button)
        row.addStretch(1)
        column = QVBoxLayout()
        column.addWidget(label)
        column.addLayout(row)
        return column

    def _build_layout(self) -> None:
        top = QHBoxLayout()
        top.addWidget(self._wheel, 1)
        value_column = QVBoxLayout()
        value_column.addWidget(self._value_label)
        value_column.addWidget(self._value_slider)
        top.addLayout(value_column)

        rgb_form = QFormLayout()
        self._lbl_r = QLabel(self)
        self._lbl_g = QLabel(self)
        self._lbl_b = QLabel(self)
        rgb_form.addRow(self._lbl_r, self._spin_r)
        rgb_form.addRow(self._lbl_g, self._spin_g)
        rgb_form.addRow(self._lbl_b, self._spin_b)
        hsv_form = QFormLayout()
        self._lbl_h = QLabel(self)
        self._lbl_s = QLabel(self)
        self._lbl_v = QLabel(self)
        hsv_form.addRow(self._lbl_h, self._spin_h)
        hsv_form.addRow(self._lbl_s, self._spin_s)
        hsv_form.addRow(self._lbl_v, self._spin_v)
        entries = QHBoxLayout()
        entries.addLayout(rgb_form)
        entries.addLayout(hsv_form)

        preview_row = QHBoxLayout()
        preview_row.addWidget(self._preview)
        preview_row.addWidget(self._hex_label)
        preview_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(entries)
        layout.addLayout(preview_row)
        layout.addLayout(self._swatch_row(self._lbl_comp, self._comp))
        layout.addLayout(self._swatch_row(self._lbl_analog, self._analog))
        layout.addLayout(self._swatch_row(self._lbl_triadic, self._triadic))
        layout.addLayout(self._swatch_row(self._lbl_tetradic, self._tetradic))
        layout.addLayout(self._swatch_row(self._lbl_split, self._split))
        layout.addLayout(self._swatch_row(self._lbl_shades, self._shades))
        layout.addLayout(self._swatch_row(self._lbl_tints, self._tints))

    def focus_widgets(self) -> List[QWidget]:
        """Return the interactive widgets in intended tab order (hub A11Y-COLHUB-2).

        The wheel pad first, then the value slider, the RGB/HSV numeric entries
        (the keyboard-accessible pick path), then each harmony swatch group.
        """
        widgets: List[QWidget] = [
            self._wheel,
            self._value_slider,
            self._spin_r,
            self._spin_g,
            self._spin_b,
            self._spin_h,
            self._spin_s,
            self._spin_v,
        ]
        for group in (
            self._comp,
            self._analog,
            self._triadic,
            self._tetradic,
            self._split,
            self._shades,
            self._tints,
        ):
            widgets.extend(group)
        return widgets

    # -- public API -------------------------------------------------------

    def current_color(self) -> QColor:
        """Return the currently selected colour as a :class:`QColor`."""
        return QColor.fromHsvF(
            (self._hue % _HUE_CIRCLE_DEG) / _HUE_CIRCLE_DEG, self._sat, self._val, 1.0
        )

    def current_rgba(self) -> RGBA:
        """Return the currently selected colour as an RGBA tuple."""
        color = self.current_color()
        return (color.red(), color.green(), color.blue(), color.alpha())

    def set_color(self, color: QColor) -> None:
        """Set the selection to ``color`` and refresh the UI (no signal emitted)."""
        self._ingest(color)
        self._sync_ui()

    # -- internal state ---------------------------------------------------

    def _ingest(self, color: QColor) -> None:
        hue = color.hueF()
        # Achromatic colours report hue -1; keep the last hue so the marker angle
        # is preserved when saturation returns above zero.
        self._hue = self._hue if hue < 0 else hue * _HUE_CIRCLE_DEG
        self._sat = color.saturationF()
        self._val = color.valueF()

    def _emit_change(self) -> None:
        self._sync_ui()
        self.colorPicked.emit(self.current_color())

    def _sync_ui(self) -> None:
        self._updating = True
        try:
            self._wheel.set_hsv(self._hue, self._sat, self._val)
            self._value_slider.setValue(int(round(self._val * CHANNEL_MAX)))
            color = self.current_color()
            self._spin_r.setValue(color.red())
            self._spin_g.setValue(color.green())
            self._spin_b.setValue(color.blue())
            self._spin_h.setValue(int(round(self._hue)) % int(_HUE_CIRCLE_DEG))
            self._spin_s.setValue(int(round(self._sat * CHANNEL_MAX)))
            self._spin_v.setValue(int(round(self._val * CHANNEL_MAX)))
            rgba: RGBA = (color.red(), color.green(), color.blue(), color.alpha())
            self._update_preview(rgba)
            self._update_harmonies(rgba)
        finally:
            self._updating = False

    def _update_preview(self, rgba: RGBA) -> None:
        pixmap = QPixmap(_SWATCH_PX * 2, _SWATCH_PX)
        pixmap.fill(QColor(*rgba))
        self._preview.setPixmap(pixmap)
        hex_text = to_hex(rgba, with_alpha=False)
        self._hex_label.setText(hex_text)
        self._preview.setAccessibleName(
            self.tr("Current colour %1").replace("%1", hex_text)
        )

    def _update_harmonies(self, rgba: RGBA) -> None:
        # Harmony MATHS live in logic/color_theory (C1); recomputed every change.
        self._comp[0].set_color(complementary(rgba))
        for button, color in zip(self._analog, analogous(rgba)):
            button.set_color(color)
        for button, color in zip(self._triadic, triadic(rgba)):
            button.set_color(color)
        for button, color in zip(self._tetradic, tetradic(rgba)):
            button.set_color(color)
        for button, color in zip(self._split, split_complementary(rgba)):
            button.set_color(color)
        for button, color in zip(self._shades, shade_ramp(rgba)):
            button.set_color(color)
        for button, color in zip(self._tints, tint_ramp(rgba)):
            button.set_color(color)

    # -- slots ------------------------------------------------------------

    def _on_wheel_picked(self, hue: float, sat: float) -> None:
        if self._updating:
            return
        self._hue = hue
        self._sat = sat
        self._emit_change()

    def _on_value_changed(self, value: int) -> None:
        if self._updating:
            return
        self._val = value / CHANNEL_MAX
        self._emit_change()

    def _on_rgb_changed(self, _value: int) -> None:
        if self._updating:
            return
        self._ingest(
            QColor(self._spin_r.value(), self._spin_g.value(), self._spin_b.value())
        )
        self._emit_change()

    def _on_hsv_changed(self, _value: int) -> None:
        if self._updating:
            return
        self._hue = float(self._spin_h.value())
        self._sat = self._spin_s.value() / CHANNEL_MAX
        self._val = self._spin_v.value() / CHANNEL_MAX
        self._emit_change()

    def _on_swatch_activated(self, rgba: RGBA) -> None:
        # Double-click / keyboard activation: ADOPT this swatch's colour into
        # the wheel (REQ-IS-UI-022). Never reached by a single click, which
        # is routed through `swatchPicked` instead and never touches the
        # wheel's own state.
        if self._updating:
            return
        self._ingest(QColor(*rgba))
        self._emit_change()

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Colour wheel picker"))
        self._value_label.setText(self.tr("Value"))
        self._value_slider.setAccessibleName(self.tr("Brightness value"))
        self._lbl_r.setText(self.tr("R"))
        self._lbl_g.setText(self.tr("G"))
        self._lbl_b.setText(self.tr("B"))
        self._lbl_h.setText(self.tr("H"))
        self._lbl_s.setText(self.tr("S"))
        self._lbl_v.setText(self.tr("V"))
        self._spin_r.setAccessibleName(self.tr("Red channel"))
        self._spin_g.setAccessibleName(self.tr("Green channel"))
        self._spin_b.setAccessibleName(self.tr("Blue channel"))
        self._spin_h.setAccessibleName(self.tr("Hue"))
        self._spin_s.setAccessibleName(self.tr("Saturation"))
        self._spin_v.setAccessibleName(self.tr("Value"))
        self._hex_label.setAccessibleName(self.tr("Hex colour"))
        comp = self.tr("Complementary")
        analog = self.tr("Analogous")
        triadic_name = self.tr("Triadic")
        tetradic_name = self.tr("Tetradic")
        split = self.tr("Split-complementary")
        shades = self.tr("Shades")
        tints = self.tr("Tints")
        self._lbl_comp.setText(comp)
        self._lbl_analog.setText(analog)
        self._lbl_triadic.setText(triadic_name)
        self._lbl_tetradic.setText(tetradic_name)
        self._lbl_split.setText(split)
        self._lbl_shades.setText(shades)
        self._lbl_tints.setText(tints)
        # Convey each harmony group to assistive tech (A11Y-COLHUB-3): the row
        # label carries an accessible group name, and each swatch is prefixed
        # with the group so a screen reader announces "<group> #RRGGBB".
        harmony = self.tr("harmony")
        for label, name, swatches in (
            (self._lbl_comp, comp, self._comp),
            (self._lbl_analog, analog, self._analog),
            (self._lbl_triadic, triadic_name, self._triadic),
            (self._lbl_tetradic, tetradic_name, self._tetradic),
            (self._lbl_split, split, self._split),
            (self._lbl_shades, shades, self._shades),
            (self._lbl_tints, tints, self._tints),
        ):
            group_name = f"{name} {harmony}"
            label.setAccessibleName(group_name)
            for swatch in swatches:
                swatch.set_group(name)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
