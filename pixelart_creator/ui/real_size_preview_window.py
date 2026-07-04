"""Real-size preview window (REQ-P9-UI-001/-002) — Qt only, binds to logic/preview.

``Real_Size_Preview_Window`` shows the document at true physical size and mirrors
edits live. It is a **read-only** :class:`QGraphicsView` on the **shared** document
scene (so ``QGraphicsScene.changed`` repaints it automatically with no manual refresh
— the live-mirror, research §5.1), whose view transform is scaled by the one pure
factor from :func:`~pixelart_creator.logic.preview.real_size_scale` (Article I — this
window adds **no** scaling maths).

DPI handling (the HIGHEST-RISK item, research §4.2 / ADR-0023 §4):

* The physical DPI is queried from Qt via ``QScreen.physicalDotsPerInch()`` — already
  device-independent.
* **DPR is NOT multiplied here.** ``QGraphicsView`` works in device-independent
  coordinates and Qt applies ``devicePixelRatio()`` itself; multiplying manually
  double-scales on HiDPI. The scale is exactly ``physicalDotsPerInch / doc_ppi``.
* A **manual on-screen-ruler calibration** fallback (``Real_Size_Calibration_Dialog``)
  covers monitors whose EDID reports a wrong/absent physical size; the calibrated DPI
  overrides the queried one.
* The scale is **recomputed on ``screenChanged``** so moving the window to a
  different-DPI monitor stays true.

All user-visible strings are ``tr()``-wrapped with a ``changeEvent`` retranslate
(REQ-P9-UI-014).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPainter, QScreen, QShowEvent, QTransform
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.constants import DEFAULT_DOCUMENT_PPI
from pixelart_creator.logic.preview import PreviewError, real_size_scale

#: On-screen calibration bar length in device-independent px (a known ruler the
#: user matches against a real ruler / credit card to derive the true DPI).
_CALIBRATION_BAR_PX = 400

#: Millimetres per inch (calibration converts a measured mm length to DPI).
_MM_PER_INCH = 25.4


class Real_Size_Calibration_Dialog(QDialog):
    """Manual on-screen-ruler DPI calibration (research §4.3 fallback).

    Shows a bar of a known device-independent px length; the user measures it with a
    physical ruler and enters the millimetres, from which the true screen DPI is
    derived: ``dpi = bar_px / (measured_mm / 25.4)``. No physical-size maths beyond
    this unit conversion lives elsewhere.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the calibration dialog (known-length bar + measured-mm input)."""
        super().__init__(parent)
        self._bar_px = _CALIBRATION_BAR_PX
        self._instructions = QLabel(self)
        self._instructions.setWordWrap(True)
        self._bar = QLabel(self)
        self._bar.setFixedWidth(self._bar_px)
        self._bar.setFixedHeight(16)
        self._bar.setStyleSheet("background-color: palette(highlight);")
        self._length_label = QLabel(self)
        self._length_spin = QDoubleSpinBox(self)
        self._length_spin.setRange(1.0, 2000.0)
        self._length_spin.setValue(self._bar_px / 96.0 * _MM_PER_INCH)
        self._length_spin.setSuffix(self.tr(" mm"))
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self._length_label)
        row.addWidget(self._length_spin)
        layout = QVBoxLayout(self)
        layout.addWidget(self._instructions)
        layout.addWidget(self._bar)
        layout.addLayout(row)
        layout.addWidget(self._buttons)
        self._retranslate()

    def measured_dpi(self) -> float:
        """Return the DPI derived from the entered physical length of the bar."""
        measured_mm = self._length_spin.value()
        inches = measured_mm / _MM_PER_INCH
        if inches <= 0.0:
            return DEFAULT_DOCUMENT_PPI
        return self._bar_px / inches

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Calibrate Real Size"))
        self._instructions.setText(
            self.tr(
                "Hold a ruler against the bar below and enter its measured "
                "length so real size matches your screen."
            )
        )
        self._length_label.setText(self.tr("Measured length"))
        self._bar.setAccessibleName(self.tr("Calibration bar"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the dialog strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Real_Size_Preview_Window(QWidget):
    """Live, read-only, true-physical-size preview of the shared document scene.

    Args:
        scene: The **shared** document scene (live-mirror via ``scene.changed``).
        doc_ppi: The document's pixels-per-inch (``Document.ppi``).
    """

    def __init__(
        self,
        scene: QGraphicsScene,
        doc_ppi: float = DEFAULT_DOCUMENT_PPI,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the read-only real-size preview on the shared ``scene``."""
        super().__init__(parent)
        self._doc_ppi = float(doc_ppi)
        #: A user-calibrated DPI override (``None`` => use the queried physical DPI).
        self._manual_dpi: Optional[float] = None
        # A plain read-only view on the SHARED scene: no tools, so it never edits;
        # scene.changed repaints it live (research §5.1). Disable interaction.
        self._view = QGraphicsView(scene, self)
        self._view.setInteractive(False)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._calibrate_button = QPushButton(self)
        self._calibrate_button.clicked.connect(self._open_calibration)
        self._status = QLabel(self)

        controls = QHBoxLayout()
        controls.addWidget(self._status, 1)
        controls.addWidget(self._calibrate_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self._view, 1)
        layout.addLayout(controls)

        self._retranslate()
        self.recompute_scale()

    # -- document binding -------------------------------------------------

    def set_document_ppi(self, doc_ppi: float) -> None:
        """Set the document PPI (document open / PPI change) and rescale."""
        self._doc_ppi = float(doc_ppi)
        self.recompute_scale()

    def set_scene(self, scene: QGraphicsScene) -> None:
        """Rebind the preview to a different shared scene (tab switch)."""
        self._view.setScene(scene)
        self.recompute_scale()

    # -- DPI + scale (Article I: the only maths is logic.real_size_scale) --

    def _screen_dpi(self) -> float:
        """Return the physical DPI to use — the manual override, else Qt's query.

        ``QScreen.physicalDotsPerInch()`` is already device-independent; **DPR is
        not multiplied** (Qt applies it — research §4.2).
        """
        if self._manual_dpi is not None:
            return self._manual_dpi
        screen: Optional[QScreen] = self.screen()
        if screen is None:
            return float(DEFAULT_DOCUMENT_PPI)
        dpi = float(screen.physicalDotsPerInch())
        return dpi if dpi > 0.0 else float(DEFAULT_DOCUMENT_PPI)

    def current_scale(self) -> float:
        """Return the device-independent screen-px-per-doc-px factor (from logic)."""
        try:
            return real_size_scale(self._doc_ppi, self._screen_dpi())
        except PreviewError:
            return 1.0

    def recompute_scale(self) -> None:
        """Apply the real-size transform to the read-only view (screenChanged hook)."""
        scale = self.current_scale()
        transform = QTransform()
        transform.scale(scale, scale)
        self._view.setTransform(transform)
        self._update_status(scale)

    def set_manual_dpi(self, dpi: float) -> None:
        """Override the queried DPI with a calibrated value and rescale."""
        self._manual_dpi = float(dpi) if dpi and dpi > 0.0 else None
        self.recompute_scale()

    def _open_calibration(self) -> None:
        dialog = Real_Size_Calibration_Dialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_manual_dpi(dialog.measured_dpi())

    # -- per-monitor DPI: recompute when moved to another screen ----------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Connect the screen-changed hook and recompute the scale (Qt override)."""
        super().showEvent(event)
        handle = self.windowHandle()
        if handle is not None:
            # Recompute the real-size scale when the window moves to a different-DPI
            # monitor (research §4.3). Reconnect defensively (idempotent).
            try:
                handle.screenChanged.disconnect(self._on_screen_changed)
            except (RuntimeError, TypeError):
                pass
            handle.screenChanged.connect(self._on_screen_changed)
        self.recompute_scale()

    def _on_screen_changed(self, _screen: object) -> None:
        self.recompute_scale()

    # -- i18n -------------------------------------------------------------

    def _update_status(self, scale: float) -> None:
        source = (
            self.tr("calibrated") if self._manual_dpi is not None else self.tr("screen")
        )
        self._status.setText(
            self.tr("Real size: {0:.0f} PPI ({1}), scale {2:.2f}×").format(
                self._screen_dpi(), source, scale
            )
        )

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Real-Size Preview"))
        self.setAccessibleName(self.tr("Real-size preview"))
        self._view.setAccessibleName(self.tr("Real-size document preview"))
        self._calibrate_button.setText(self.tr("Calibrate…"))
        self._update_status(self.current_scale())

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the preview strings on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
