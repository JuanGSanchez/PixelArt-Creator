# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Shared-projects panel — share a project + manage the member roster (REQ-P10-UI-009).

``Shared_Projects_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget`
that drives the provider-agnostic
:class:`~pixelart_creator.ui.collaboration_actions.Collaboration_Session` (over the
Qt-free :class:`~pixelart_creator.data.cloud.shared_adapter.SharedProjectAdapter`). It
lets the user name a shared project, build a **member roster** (``member_id`` + a
bounded, provider-agnostic **role** from :data:`MEMBER_ROLES`), and **share / update**
it — then re-reads and displays the normalized roster. It performs **no** cloud logic of
its own and names **no** provider (DATA-007). All work is synchronous over the loopback
adapter (no worker thread — Slice B).

The member cap ``MAX_SHARED_MEMBERS`` is enforced at the UI edge with user feedback
(Add is refused past the cap), backed by the adapter's own validation as defence in
depth (Article VII). Every user-visible string is ``tr()``-wrapped with a
``changeEvent`` retranslate (F5/REQ-P10-UI-008); every interactive control carries an
accessible name and is keyboard-reachable (REQ-P10-UI-006); colours come from the active
QSS theme by role, so both themes render correctly (REQ-P10-UI-007).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.cloud import SharedProjectError
from pixelart_creator.logic.cloud_validation import MEMBER_ROLES
from pixelart_creator.logic.constants import MAX_SHARED_MEMBERS
from pixelart_creator.ui.collaboration_actions import Collaboration_Session

#: Fixed display order for the role combo (a stable subset of the module-local
#: :data:`MEMBER_ROLES` vocabulary; presentation ordering, not a domain value).
_ROLE_ORDER: Tuple[str, ...] = tuple(
    role for role in ("owner", "editor", "viewer") if role in MEMBER_ROLES
)

_COL_MEMBER = 0
_COL_ROLE = 1


class Shared_Projects_Panel(QWidget):
    """Share the current project + build/manage its member roster (REQ-P10-UI-009)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the share controls, the editable roster, and the roster view."""
        super().__init__(parent)
        self._session: Optional[Collaboration_Session] = None
        #: The roster being edited before it is committed via Share/Update.
        self._draft: List[Tuple[str, str]] = []

        # -- share target ------------------------------------------------
        self._project_label = QLabel(self)
        self._project_edit = QLineEdit(self)

        # -- add-member row ----------------------------------------------
        self._member_edit = QLineEdit(self)
        self._role_combo = QComboBox(self)
        for role in _ROLE_ORDER:
            self._role_combo.addItem("", role)  # text set in _retranslate
        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_member)
        add_row = QHBoxLayout()
        add_row.addWidget(self._member_edit, 1)
        add_row.addWidget(self._role_combo)
        add_row.addWidget(self._add_button)

        # -- editable roster ---------------------------------------------
        self._roster_group = QGroupBox(self)
        self._roster_tree = QTreeWidget(self._roster_group)
        self._roster_tree.setColumnCount(2)
        self._roster_tree.setRootIsDecorated(False)
        self._roster_tree.setUniformRowHeights(True)
        self._roster_tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._roster_tree.currentItemChanged.connect(self._update_enabled)
        self._remove_button = QPushButton(self._roster_group)
        self._remove_button.clicked.connect(self._on_remove_member)
        self._share_button = QPushButton(self._roster_group)
        self._share_button.clicked.connect(self._on_share)
        roster_buttons = QHBoxLayout()
        roster_buttons.addWidget(self._remove_button)
        roster_buttons.addStretch(1)
        roster_buttons.addWidget(self._share_button)
        roster_layout = QVBoxLayout(self._roster_group)
        roster_layout.addWidget(self._roster_tree, 1)
        roster_layout.addLayout(roster_buttons)

        # -- committed roster (read-back) --------------------------------
        self._members_group = QGroupBox(self)
        self._members_view = QTreeWidget(self._members_group)
        self._members_view.setColumnCount(2)
        self._members_view.setRootIsDecorated(False)
        self._members_view.setUniformRowHeights(True)
        self._members_view.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        members_layout = QVBoxLayout(self._members_group)
        members_layout.addWidget(self._members_view, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(self._project_label)
        layout.addWidget(self._project_edit)
        layout.addLayout(add_row)
        layout.addWidget(self._roster_group, 1)
        layout.addWidget(self._members_group, 1)

        self._retranslate()
        self._refresh_draft()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Collaboration_Session) -> None:
        """Bind the panel to a :class:`Collaboration_Session` and refresh the view."""
        self._session = session
        session.membersChanged.connect(self._on_members_changed)
        session.sharedProjectChanged.connect(self._on_shared_changed)
        self._refresh_members()

    # -- draft roster edits ----------------------------------------------

    def _on_add_member(self) -> None:
        """Add the typed member + selected role to the draft roster (edge-capped)."""
        member_id = self._member_edit.text().strip()
        if not member_id:
            return
        if any(existing == member_id for existing, _ in self._draft):
            QMessageBox.information(
                self,
                self.tr("Shared Project"),
                self.tr("Member %1 is already in the roster.").replace("%1", member_id),
            )
            return
        if len(self._draft) >= MAX_SHARED_MEMBERS:
            QMessageBox.warning(
                self,
                self.tr("Shared Project"),
                self.tr("A shared project may have at most %1 members.").replace(
                    "%1", str(MAX_SHARED_MEMBERS)
                ),
            )
            return
        role = self._role_combo.currentData()
        self._draft.append((member_id, str(role)))
        self._member_edit.clear()
        self._refresh_draft()
        self._update_enabled()

    def _on_remove_member(self) -> None:
        """Remove the selected draft member."""
        item = self._roster_tree.currentItem()
        if item is None:
            return
        member_id = item.text(_COL_MEMBER)
        self._draft = [entry for entry in self._draft if entry[0] != member_id]
        self._refresh_draft()
        self._update_enabled()

    def _on_share(self) -> None:
        """Commit the draft roster to the session (share / update the project)."""
        if self._session is None:
            return
        project_id = self._project_edit.text().strip()
        if not project_id:
            QMessageBox.information(
                self,
                self.tr("Shared Project"),
                self.tr("Enter a shared-project name first."),
            )
            return
        if not self._draft:
            QMessageBox.information(
                self,
                self.tr("Shared Project"),
                self.tr("Add at least one member before sharing."),
            )
            return
        try:
            self._session.share(project_id, tuple(self._draft))
        except SharedProjectError as exc:
            QMessageBox.warning(self, self.tr("Shared Project"), str(exc))

    # -- session reactions ------------------------------------------------

    def _on_shared_changed(self, project_id: str) -> None:
        if project_id:
            self._project_edit.setText(project_id)
        self._refresh_members()

    def _on_members_changed(self, _project_id: str) -> None:
        self._refresh_members()

    # -- view population --------------------------------------------------

    def _refresh_draft(self) -> None:
        self._roster_tree.clear()
        for member_id, role in self._draft:
            item = QTreeWidgetItem([member_id, self._role_text(role)])
            item.setData(_COL_ROLE, Qt.ItemDataRole.UserRole, role)
            self._roster_tree.addTopLevelItem(item)

    def _refresh_members(self) -> None:
        self._members_view.clear()
        if self._session is None:
            return
        project_id = self._session.active_project_id()
        if project_id is None:
            return
        for member in self._session.members(project_id):
            self._members_view.addTopLevelItem(
                QTreeWidgetItem([member.member_id, self._role_text(member.role)])
            )

    def _update_enabled(self) -> None:
        self._remove_button.setEnabled(self._roster_tree.currentItem() is not None)
        self._share_button.setEnabled(bool(self._draft))

    # -- i18n -------------------------------------------------------------

    def _role_text(self, role: str) -> str:
        """Return the translated label for a raw role id (fallback to the id)."""
        labels = {
            "owner": self.tr("Owner"),
            "editor": self.tr("Editor"),
            "viewer": self.tr("Viewer"),
        }
        return labels.get(role, role)

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Shared projects"))
        self._project_label.setText(self.tr("Shared-project name:"))
        self._project_edit.setPlaceholderText(self.tr("e.g. team-sprite"))
        self._project_edit.setAccessibleName(self.tr("Shared-project name"))
        self._member_edit.setPlaceholderText(self.tr("Member id to invite"))
        self._member_edit.setAccessibleName(self.tr("Member id to invite"))
        self._role_combo.setAccessibleName(self.tr("Member role"))
        for index, role in enumerate(_ROLE_ORDER):
            self._role_combo.setItemText(index, self._role_text(role))
        self._add_button.setText(self.tr("Add Member"))
        self._add_button.setAccessibleName(self.tr("Add member to roster"))
        self._roster_group.setTitle(self.tr("Roster to share"))
        self._members_group.setTitle(self.tr("Current members"))
        self._remove_button.setText(self.tr("Remove"))
        self._remove_button.setAccessibleName(self.tr("Remove selected member"))
        self._share_button.setText(self.tr("Share / Update"))
        self._share_button.setAccessibleName(self.tr("Share or update the project"))
        headers = [self.tr("Member"), self.tr("Role")]
        self._roster_tree.setHeaderLabels(headers)
        self._members_view.setHeaderLabels(headers)
        self._roster_tree.setAccessibleName(self.tr("Editable member roster"))
        self._members_view.setAccessibleName(self.tr("Shared member list"))
        # Re-render role labels already in the trees (draft + committed).
        self._refresh_draft()
        self._refresh_members()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the shared-projects strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
