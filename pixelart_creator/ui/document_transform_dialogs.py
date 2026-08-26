"""Modal surfaces for a whole-document geometry transform (canvas-scale-defects).

Presentation only (S11): no enumeration, no cost maths, no resampling — both
figures shown here (the projected byte cost, the target geometry) are
supplied by the caller, which reads them from
``pixelart_creator.logic.doc_transform``.

Both dialogs are real ``QDialog`` subclasses, never a bare ``QMessageBox``:
SC-CSD-U014-1 asserts that *each* dialog re-sets its own texts on
``QEvent.LanguageChange`` (F5), which only a dedicated ``changeEvent``
override can do. Every user-visible message is built from **format
placeholders** — never by concatenating a translated fragment with a number,
because word and unit order differ by language (REQ-CSD-UI-014).

Article V.1/V.3 apply to both dialogs regardless of what the spec names
(``plan.md`` §8.1): every interactive widget carries a non-empty accessible
name, every control is keyboard-reachable with a visible focus indicator, and
no colour is hard-coded here — both dialogs use only the platform's default
palette/theme roles, so they render correctly under either shipped theme.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QLocale, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Document_Transform_Confirm_Dialog(QDialog):
    """Ask before a projected-peak-cost whole-document transform proceeds.

    Shown only when the projected cost exceeds
    ``DOCUMENT_TRANSFORM_CONFIRM_BYTES`` (the caller's decision, not this
    dialog's) — this class only presents the question. The size text comes
    from ``QLocale().formattedDataSize`` (PL-CSD-D5): no unit string is
    authored here, so none can be mistranslated. Declining (or closing) the
    dialog rejects it; proceeding accepts it — nothing else is inferred.
    """

    def __init__(
        self,
        operation_label: str,
        projected_bytes: int,
        target_w: int,
        target_h: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the confirmation for ``operation_label`` at the projected cost."""
        super().__init__(parent)
        self._operation_label = str(operation_label)
        self._projected_bytes = int(projected_bytes)
        self._target_w = int(target_w)
        self._target_h = int(target_h)

        self._message = QLabel(self)
        self._message.setWordWrap(True)

        self._buttons = QDialogButtonBox(self)
        self._proceed = QPushButton(self)
        self._decline = QPushButton(self)
        self._buttons.addButton(self._proceed, QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.addButton(self._decline, QDialogButtonBox.ButtonRole.RejectRole)
        self._proceed.clicked.connect(self.accept)
        self._decline.clicked.connect(self.reject)
        self._decline.setDefault(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message)
        layout.addWidget(self._buttons)

        self._retranslate()

    # -- i18n --------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Confirm Large Transform"))
        self.setAccessibleName(self.tr("Confirm large document transform dialog"))
        size_text = QLocale().formattedDataSize(self._projected_bytes)
        message = self.tr(
            "%1 will resample every layer and mask of this document to "
            "%2 × %3 px, using up to %4 of memory at once. Proceed?"
        )
        message = message.replace("%1", self._operation_label)
        message = message.replace("%2", str(self._target_w))
        message = message.replace("%3", str(self._target_h))
        message = message.replace("%4", size_text)
        self._message.setText(message)
        self._message.setAccessibleName(self.tr("Transform cost summary"))
        self._proceed.setText(self.tr("Proceed"))
        self._proceed.setAccessibleName(self.tr("Proceed with the transform"))
        self._decline.setText(self.tr("Cancel"))
        self._decline.setAccessibleName(self.tr("Cancel the transform"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


class Document_Transform_Progress_Dialog(QDialog):
    """Determinate progress for a whole-document geometry transform.

    ``setRange(0, total)`` at construction and ``setValue(0)`` — the
    indicator is **never** left indeterminate/busy (REQ-CSD-UI-011) and is
    shown unconditionally, including below the cost threshold: there is no
    ``minimumDuration``-style suppression here (SC-CSD-U013-2), so the caller
    may rely on it always appearing. The cancel control is live from before
    the first buffer: clicking it, pressing Escape, or closing the window all
    emit :attr:`cancelled` exactly once each time they fire.
    """

    #: Emitted when the user asks to stop — via the button, Escape, or the
    #: window's close control. The caller (the runner) decides what "stop"
    #: means; this dialog only reports the request.
    cancelled = Signal()

    def __init__(
        self, operation_label: str, total: int, parent: Optional[QWidget] = None
    ) -> None:
        """Build a determinate progress dialog for ``total`` buffers.

        Raises:
            ValueError: If ``total`` is not positive — the range must never
                be ``(0, 0)``, which reads as indeterminate/busy in Qt.
        """
        super().__init__(parent)
        if total <= 0:
            raise ValueError(
                "Document_Transform_Progress_Dialog requires total >= 1, "
                f"got {total!r}"
            )
        self._operation_label = str(operation_label)
        self._total = int(total)

        self._info = QLabel(self)
        self._info.setWordWrap(True)
        self._bar = QProgressBar(self)
        self._bar.setRange(0, self._total)
        self._bar.setValue(0)
        self._cancel_button = QPushButton(self)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        self._cancel_button.setDefault(True)
        self._cancel_button.setFocus()

        layout = QVBoxLayout(self)
        layout.addWidget(self._info)
        layout.addWidget(self._bar)
        layout.addWidget(self._cancel_button)

        self.setModal(True)
        self._retranslate()

    # -- progress ------------------------------------------------------

    def set_progress(self, value: int) -> None:
        """Advance the bar to ``value`` (0..``total``)."""
        self._bar.setValue(int(value))

    # -- cancellation ----------------------------------------------------

    def _on_cancel_clicked(self) -> None:
        self.cancelled.emit()

    def reject(self) -> None:  # noqa: N802 (Qt override -- Escape key)
        """Treat Escape the same as the Cancel button: emit, then reject."""
        self.cancelled.emit()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Treat the window's close control the same as the Cancel button."""
        self.cancelled.emit()
        super().closeEvent(event)

    # -- i18n --------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Transforming Document"))
        self.setAccessibleName(self.tr("Document transform progress dialog"))
        self._info.setText(self.tr("%1…").replace("%1", self._operation_label))
        self._info.setAccessibleName(self.tr("Transform operation in progress"))
        self._bar.setAccessibleName(self.tr("Transform progress"))
        self._cancel_button.setText(self.tr("Cancel"))
        self._cancel_button.setAccessibleName(self.tr("Cancel the transform"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate on QEvent.LanguageChange (F5); delegate otherwise."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
