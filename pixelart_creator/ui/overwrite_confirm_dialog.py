"""Floating-selection overwrite confirmation — blocking, cancellable (REQ-P2-UI-037).

``Overwrite_Confirm_Dialog`` is shown by ``ui/tools/floating_move.py`` before a
floating-selection commit (``REQ-P2-UI-033``) would overwrite a **non-empty**
destination, as reported by ``logic/selection.destination_is_empty``
(``REQ-P2-LOGIC-037``). It blocks (modal ``exec()``) and is cancellable: on
cancel, the caller must apply nothing and push no command, and the float stays
active at its current offset — this is deliberately not the same as
``REQ-P2-UI-034``'s ESC, which abandons the float. Ticking **"Don't ask
again"** records nothing by itself — the caller reads :meth:`dont_ask_again`
only when :meth:`exec` returns ``Accepted`` (Q-19 ruling: "ticking and
cancelling records nothing"). This dialog does not touch
``logic/project_prefs.py`` itself; persisting the suppression for the current
project is the caller's job (Article I / S11 — no domain logic here).

Follows ``ui/cel_overwrite_dialog.py``'s ``Cel_Overwrite_Dialog`` shape exactly
(plan §10.5) so the two per-project "Don't ask again" confirmations share one
mental model.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class Overwrite_Confirm_Dialog(QDialog):
    """Blocking confirmation before a floating-selection commit overwrites content."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the modal warning with its "Don't ask again" checkbox."""
        super().__init__(parent)
        self.setModal(True)

        self._message = QLabel(self)
        self._message.setWordWrap(True)
        self._dont_ask = QCheckBox(self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message)
        layout.addWidget(self._dont_ask)
        layout.addWidget(self._buttons)

        self._retranslate()

    def dont_ask_again(self) -> bool:
        """Return whether "Don't ask again" was ticked.

        Meaningful only when :meth:`exec` returned
        ``QDialog.DialogCode.Accepted`` — the caller must not read this after a
        cancel (Q-19: "ticking and cancelling records nothing").
        """
        return self._dont_ask.isChecked()

    # -- i18n / a11y ------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Overwrite Existing Pixels?"))
        self.setAccessibleName(self.tr("Overwrite existing pixels confirmation"))
        self._message.setText(
            self.tr(
                "The destination already has pixels on it. Continuing replaces "
                "that content. This can be undone."
            )
        )
        self._message.setAccessibleName(self.tr("Overwrite warning"))
        self._dont_ask.setText(self.tr("Don't ask again for this project"))
        self._dont_ask.setAccessibleName(
            self.tr("Suppress this confirmation for the current project")
        )
        continue_button = self._buttons.button(QDialogButtonBox.StandardButton.Yes)
        if continue_button is not None:
            continue_button.setText(self.tr("Continue"))
            continue_button.setAccessibleName(self.tr("Continue"))
        cancel_button = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(self.tr("Cancel"))
            cancel_button.setAccessibleName(self.tr("Cancel"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the dialog's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
