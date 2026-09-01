# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""The display target for a **reopened** timelapse recording (D-12, T11).

``Timelapse_Frame_View`` renders the reconstructed RGBA frames of a **loaded**
recording — one produced by
:func:`pixelart_creator.data.timelapse_io.load_session_payload` and replayed
through :class:`~pixelart_creator.ui.timelapse_playback.Snapshot_Document_Provider`
— and is labelled unmistakably as a reopened recording, never the user's
current work (REQ-P9-UI-024, ``DEP-12f``). It **touches no open document**: it
does not alter one, pushes no ``QUndoCommand``, and does not disturb any
document's history — it only paints the RGBA arrays it is handed.

**The controls are the shipped ones** (``ui/timelapse_controls.py``, T10): this
view is a display target only, not a second control surface — the user learns
one set of play/pause/seek/speed controls and this widget is simply where a
loaded recording's frames appear, distinct from the active canvas
(``REQ-P9-UI-024`` draws exactly this boundary). A host wires
``Timelapse_Controls.frameReady`` to :meth:`display_frame` when playing back a
loaded recording.

Nearest-neighbour scaling, no anti-aliasing (pixel-art fidelity, matching the
shipped buffer-to-``QImage`` conversion pattern already used elsewhere in
``ui/``, e.g. ``ui/timeline_panel.py``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

__all__ = ["Timelapse_Frame_View"]


class Timelapse_Frame_View(QWidget):
    """Renders one reconstructed RGBA frame of a reopened recording at a time."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the banner + frame display, with no frame shown yet."""
        super().__init__(parent)

        self._banner = QLabel(self)
        self._banner.setObjectName("timelapseReopenedBanner")
        self._banner.setAccessibleDescription(
            self.tr("Reopened recording — not the current document")
        )

        self._image_label = QLabel(self)
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setScaledContents(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._banner)
        layout.addWidget(self._image_label, stretch=1)

        self._last_pixmap: Optional[QPixmap] = None
        self._retranslate()

    # -- display target -----------------------------------------------------

    def display_frame(self, rgba: "np.ndarray") -> None:
        """Paint one reconstructed RGBA ``(H, W, 4)`` uint8 array.

        Touches no open document — this is a pure display target. Scaling is
        nearest-neighbour (``Qt.TransformationMode.FastTransformation``), no
        anti-aliasing, matching the pixel-art fidelity convention used across
        the canvas surfaces.
        """
        data = np.ascontiguousarray(rgba)
        height, width = int(data.shape[0]), int(data.shape[1])
        image = QImage(
            data.data, width, height, data.strides[0], QImage.Format.Format_RGBA8888
        ).copy()
        self._last_pixmap = QPixmap.fromImage(image)
        self._rescale()

    def clear(self) -> None:
        """Clear the displayed frame (e.g. the loaded recording was closed)."""
        self._last_pixmap = None
        self._image_label.clear()

    def resizeEvent(self, event: object) -> None:  # noqa: N802 (Qt override)
        """Rescale the currently displayed frame to the new size (Qt override)."""
        self._rescale()
        super().resizeEvent(event)  # type: ignore[arg-type]

    def _rescale(self) -> None:
        if self._last_pixmap is None:
            return
        target = self._image_label.size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._last_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,  # nearest-neighbour
        )
        self._image_label.setPixmap(scaled)

    # -- i18n -----------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Reopened Recording"))
        self.setAccessibleName(self.tr("Reopened timelapse recording"))
        self._banner.setText(
            self.tr("Reopened recording — this is not your current document")
        )
        self._banner.setAccessibleDescription(
            self.tr("Reopened recording — not the current document")
        )

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-set the banner/labels on a language change (Qt override)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
