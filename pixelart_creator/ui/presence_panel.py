# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Presence panel — show WHO is present in a shared project (REQ-P10-UI-011).

``Presence_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` over the
active shared project's **ephemeral presence** channel, driving the provider-agnostic
:class:`~pixelart_creator.ui.collaboration_actions.Collaboration_Session` (over the
Qt-free :class:`~pixelart_creator.data.cloud.shared_adapter.SharedProjectAdapter`). It
shows a **roster / awareness indicator of who is present** — the scope of
REQ-P10-UI-011 — and lets the local user **announce** their presence and **leave**. It
is **NOT** live-cursor rendering: drawing other collaborators' cursors/selection live
(REQ-P10-UI-013) is Slice C and is deliberately out of scope here.

Presence is ephemeral (never persisted into the ``.pixproj`` or the CRDT sidecar). In
Slice B there is **no** sync backend and therefore **no** poller / timer / worker: the
roster reflects local announcements over the loopback adapter and is refreshed
synchronously on demand + on the session's presence signal. When the real-time backend
lands (Slice C) a live push replaces the manual refresh — the panel binds to the same
session signal, so no rework is needed.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(F5/REQ-P10-UI-008); every control carries an accessible name and is keyboard-reachable
(REQ-P10-UI-006); colours come from the active QSS theme by role, so both themes render
correctly (REQ-P10-UI-007).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.cloud import SharedProjectError
from pixelart_creator.ui.collaboration_actions import Collaboration_Session


class Presence_Panel(QWidget):
    """Show who is present + announce/leave the local member (REQ-P10-UI-011)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the presence roster, the self-id field, and the join/leave controls."""
        super().__init__(parent)
        self._session: Optional[Collaboration_Session] = None

        self._intro = QLabel(self)
        self._intro.setWordWrap(True)

        self._self_edit = QLineEdit(self)
        self._join_button = QPushButton(self)
        self._join_button.clicked.connect(self._on_join)
        self._leave_button = QPushButton(self)
        self._leave_button.clicked.connect(self._on_leave)
        control_row = QHBoxLayout()
        control_row.addWidget(self._self_edit, 1)
        control_row.addWidget(self._join_button)
        control_row.addWidget(self._leave_button)

        self._list = QListWidget(self)

        layout = QVBoxLayout(self)
        layout.addWidget(self._intro)
        layout.addLayout(control_row)
        layout.addWidget(self._list, 1)

        self._retranslate()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Collaboration_Session) -> None:
        """Bind the panel to a :class:`Collaboration_Session` and refresh the roster."""
        self._session = session
        session.presenceChanged.connect(self._on_presence_changed)
        session.sharedProjectChanged.connect(self._on_shared_changed)
        self._refresh()

    # -- actions ----------------------------------------------------------

    def _self_id(self) -> str:
        return self._self_edit.text().strip()

    def _on_join(self) -> None:
        """Announce the local member as present (ephemeral)."""
        if self._session is None:
            return
        project_id = self._session.active_project_id()
        if project_id is None:
            QMessageBox.information(
                self,
                self.tr("Presence"),
                self.tr("Open a shared project first."),
            )
            return
        member_id = self._self_id()
        if not member_id:
            QMessageBox.information(
                self,
                self.tr("Presence"),
                self.tr("Enter your member id to announce presence."),
            )
            return
        try:
            self._session.announce_presence(project_id, member_id)
        except SharedProjectError as exc:
            QMessageBox.warning(self, self.tr("Presence"), str(exc))

    def _on_leave(self) -> None:
        """Clear the local member's ephemeral presence."""
        if self._session is None:
            return
        project_id = self._session.active_project_id()
        member_id = self._self_id()
        if project_id is None or not member_id:
            return
        self._session.clear_presence(project_id, member_id)

    # -- session reactions ------------------------------------------------

    def _on_presence_changed(self, _project_id: str) -> None:
        self._refresh()

    def _on_shared_changed(self, _project_id: str) -> None:
        self._refresh()

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        self._list.clear()
        if self._session is not None:
            project_id = self._session.active_project_id()
            if project_id is not None:
                for entry in self._session.presence(project_id):
                    self._list.addItem(entry.member_id)
        self._update_enabled()

    def _update_enabled(self) -> None:
        active = self._session is not None and self._session.is_active()
        self._join_button.setEnabled(active)
        self._leave_button.setEnabled(active)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Presence"))
        self._intro.setText(
            self.tr(
                "Members currently present in the shared project. Presence is "
                "ephemeral and is never saved into the project file."
            )
        )
        self._self_edit.setPlaceholderText(self.tr("Your member id"))
        self._self_edit.setAccessibleName(self.tr("Your member id"))
        self._join_button.setText(self.tr("Join"))
        self._join_button.setAccessibleName(self.tr("Announce your presence"))
        self._leave_button.setText(self.tr("Leave"))
        self._leave_button.setAccessibleName(self.tr("Clear your presence"))
        self._list.setAccessibleName(self.tr("Present members"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the presence strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
