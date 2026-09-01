# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Cel overwrite confirmation — blocking, cancellable (REQ-P5-UI-033).

``Cel_Overwrite_Dialog`` is shown by ``ui/timeline_grid_view.py`` before any part
of a cel move/copy (``REQ-P5-LOGIC-016``) is applied to a **non-empty** destination
cell. It blocks (modal ``exec()``) and is cancellable: on cancel, the caller must
apply nothing and push no command, so there is nothing on the undo stack to step
over. Ticking **"Don't ask again"** records nothing by itself — the caller reads
:meth:`dont_ask_again` only when :meth:`exec` returns ``Accepted`` (Q-19 ruling:
"ticking and cancelling records nothing"). This dialog does not touch
``logic/project_prefs.py`` itself; persisting the suppression for the current
project is the caller's job (Article I / S11 — no domain logic here).
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


class Cel_Overwrite_Dialog(QDialog):
    """Blocking confirmation before a timeline-grid drop overwrites a cel."""

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
        self.setWindowTitle(self.tr("Overwrite Existing Cel?"))
        self.setAccessibleName(self.tr("Overwrite existing cel confirmation"))
        self._message.setText(
            self.tr(
                "The destination cell already has a drawing on it. Proceeding "
                "replaces that drawing. This can be undone."
            )
        )
        self._message.setAccessibleName(self.tr("Overwrite warning"))
        self._dont_ask.setText(self.tr("Don't ask again for this project"))
        self._dont_ask.setAccessibleName(
            self.tr("Suppress this confirmation for the current project")
        )
        yes_button = self._buttons.button(QDialogButtonBox.StandardButton.Yes)
        if yes_button is not None:
            yes_button.setText(self.tr("Overwrite"))
            yes_button.setAccessibleName(self.tr("Overwrite"))
        cancel_button = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(self.tr("Cancel"))
            cancel_button.setAccessibleName(self.tr("Cancel"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the dialog's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
