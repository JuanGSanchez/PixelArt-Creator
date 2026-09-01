# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Non-blocking playback pre-warm progress indicator (D1).

``Prewarm_Indicator`` is a small status-bar strip shown while cold animation
frames are flattened **off** the GUI thread (D1/D2): a label, a determinate
progress bar (frames prepared / total) and a **Cancel** button. It never blocks
input — the window stays fully responsive while it is visible — and the Cancel
button lets the user abort the warm (wired by the shell to Stop, which cancels the
in-flight warm).

All user-visible strings are ``tr()``-wrapped and re-set on
:data:`QEvent.Type.LanguageChange` (REQ-P5-UI-019); the bar and button carry
accessible names and the Cancel button is keyboard-reachable. Colours come from
the active theme's QSS (role-based, not hard-coded), so it renders correctly in
both light and dark themes.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QWidget,
)


class Prewarm_Indicator(QWidget):
    """A non-blocking, cancellable playback pre-warm progress strip (D1)."""

    #: Emitted when the user cancels the pre-warm (wired to Stop by the shell).
    cancelRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the status-bar label, progress bar and Cancel button."""
        super().__init__(parent)
        self._label = QLabel(self)
        self._bar = QProgressBar(self)
        self._bar.setMinimum(0)
        self._bar.setMaximum(1)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedWidth(120)
        self._cancel_button = QToolButton(self)
        self._cancel_button.clicked.connect(self.cancelRequested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        layout.addWidget(self._cancel_button)

        self._retranslate()
        self.setVisible(False)

    def start(self, total: int) -> None:
        """Show the indicator for a warm of ``total`` frames, reset to zero."""
        self._bar.setMaximum(max(1, int(total)))
        self._bar.setValue(0)
        self.setVisible(True)

    def set_progress(self, done: int, total: int) -> None:
        """Update the bar to ``done``/``total`` frames prepared and keep it shown."""
        clamped_total = max(1, int(total))
        self._bar.setMaximum(clamped_total)
        self._bar.setValue(max(0, min(int(done), clamped_total)))
        self.setVisible(True)

    def finish(self) -> None:
        """Hide the indicator (warm complete or cancelled)."""
        self.setVisible(False)

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Playback preparation progress"))
        self._label.setText(self.tr("Preparing playback…"))
        self._bar.setAccessibleName(self.tr("Frames prepared"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._cancel_button.setToolTip(self.tr("Cancel playback preparation"))
        self._cancel_button.setAccessibleName(self.tr("Cancel playback preparation"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the indicator's strings on a language change."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
