# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Autosave-recovery prompt on restart (REQ-P10-UI-003).

``Recovery_Prompt`` is a presentation-only :class:`~PySide6.QtWidgets.QDialog`
shown at startup when the cloud port's recovery slot holds unsaved work
(discovered via ``get_recovery`` — REQ-P10-DATA-004). It offers **Recover** or
**Discard**; the caller performs the actual off-GUI-thread fetch + defensive
PIO-1 decode and opens the recovered document into a *new* tab, so the user's
last explicit save is never clobbered (REQ-P10-DATA-004 no-clobber). Choosing
Discard simply dismisses the prompt — the recovery slot is untouched until the
user next autosaves.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(F5/REQ-P10-UI-008); the buttons are keyboard-reachable with accessible names
(REQ-P10-UI-006) and the dialog renders correctly in both QSS themes
(REQ-P10-UI-007). It owns no worker thread and is fully disposable.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Recovery_Prompt(QDialog):
    """Offer to recover unsaved autosaved work found at startup (REQ-P10-UI-003)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the prompt; call :meth:`exec` and read :meth:`chose_recover`."""
        super().__init__(parent)

        self._message = QLabel(self)
        self._message.setWordWrap(True)

        self._buttons = QDialogButtonBox(self)
        self._recover_button = QPushButton(self)
        self._discard_button = QPushButton(self)
        self._buttons.addButton(
            self._recover_button, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._buttons.addButton(
            self._discard_button, QDialogButtonBox.ButtonRole.RejectRole
        )
        # Recover is the safe default (focused): Enter recovers, Escape discards.
        self._recover_button.setDefault(True)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message)
        layout.addWidget(self._buttons)

        self._retranslate()

    # -- public API -------------------------------------------------------

    def chose_recover(self) -> bool:
        """Return ``True`` if the dialog was accepted (Recover), else ``False``."""
        return self.result() == QDialog.DialogCode.Accepted

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Recover Unsaved Work"))
        self._message.setText(
            self.tr(
                "Unsaved work from a previous session was found. Recover it into "
                "a new tab? Your last explicit save is not affected."
            )
        )
        self._recover_button.setText(self.tr("Recover"))
        self._discard_button.setText(self.tr("Discard"))
        self._recover_button.setAccessibleName(self.tr("Recover unsaved work"))
        self._discard_button.setAccessibleName(self.tr("Discard unsaved work"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the prompt strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
