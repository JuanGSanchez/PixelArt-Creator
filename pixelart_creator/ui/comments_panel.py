# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Comments panel — view, add, thread, and resolve comments (REQ-P10-UI-010).

``Comments_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` over the
active shared project's comment thread, driving the provider-agnostic
:class:`~pixelart_creator.ui.collaboration_actions.Collaboration_Session` (over the
Qt-free :class:`~pixelart_creator.data.cloud.shared_adapter.SharedProjectAdapter`). It
lists comments (threaded under their parent via ``parent_id``), lets the user **add** a
comment — optionally as a **reply** to the selected one — and **resolve** a comment. It
performs **no** cloud logic of its own; all work is synchronous over the loopback
adapter (no worker thread — Slice B).

Comment text is **untrusted, validated** input (Article VII): the per-comment
``MAX_COMMENT_BYTES`` cap is enforced at the UI edge (measured on the UTF-8 encoding,
matching the adapter's own check) with a live byte counter and user feedback, and the
per-project ``MAX_COMMENTS_PER_PROJECT`` cap is surfaced when the adapter reports it.
The adapter re-validates as defence in depth; there is **no** ``eval`` / ``exec``.
Region attachment is accepted by the validator but the normalized
:class:`~pixelart_creator.data.cloud.shared_adapter.ProjectComment` does not surface a
region, so no region UI is presented (the model, not this panel, bounds that).

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(F5/REQ-P10-UI-008); every control carries an accessible name and is keyboard-reachable
(REQ-P10-UI-006); colours come from the active QSS theme by role, so both themes render
correctly (REQ-P10-UI-007).
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.data.cloud import ProjectComment, SharedProjectError
from pixelart_creator.logic.constants import MAX_COMMENT_BYTES
from pixelart_creator.ui.collaboration_actions import Collaboration_Session


class Comments_Panel(QWidget):
    """View / add / thread / resolve comments on the active shared project."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the author field, threaded comment view, and add/resolve controls."""
        super().__init__(parent)
        self._session: Optional[Collaboration_Session] = None

        self._author_label = QLabel(self)
        self._author_edit = QLineEdit(self)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(3)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._update_enabled)

        self._editor = QPlainTextEdit(self)
        self._editor.textChanged.connect(self._update_counter)
        self._counter = QLabel(self)

        self._reply_check = QPushButton(self)
        self._reply_check.setCheckable(True)
        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add)
        self._resolve_button = QPushButton(self)
        self._resolve_button.clicked.connect(self._on_resolve)
        buttons = QHBoxLayout()
        buttons.addWidget(self._reply_check)
        buttons.addWidget(self._resolve_button)
        buttons.addStretch(1)
        buttons.addWidget(self._add_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._author_label)
        layout.addWidget(self._author_edit)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._editor)
        layout.addWidget(self._counter)
        layout.addLayout(buttons)

        self._retranslate()
        self._update_counter()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Collaboration_Session) -> None:
        """Bind the panel to a :class:`Collaboration_Session` and refresh the view."""
        self._session = session
        session.commentsChanged.connect(self._on_comments_changed)
        session.sharedProjectChanged.connect(self._on_shared_changed)
        self._refresh()

    # -- actions ----------------------------------------------------------

    def _on_add(self) -> None:
        """Add the editor text as a comment (optionally a reply), with edge caps."""
        if self._session is None:
            return
        project_id = self._session.active_project_id()
        if project_id is None:
            QMessageBox.information(
                self,
                self.tr("Comments"),
                self.tr("Open a shared project before commenting."),
            )
            return
        author_id = self._author_edit.text().strip()
        if not author_id:
            QMessageBox.information(
                self,
                self.tr("Comments"),
                self.tr("Enter your member id before commenting."),
            )
            return
        text = self._editor.toPlainText()
        if not text.strip():
            return
        if len(text.encode("utf-8")) > MAX_COMMENT_BYTES:
            QMessageBox.warning(
                self,
                self.tr("Comments"),
                self.tr("A comment may be at most %1 bytes.").replace(
                    "%1", str(MAX_COMMENT_BYTES)
                ),
            )
            return
        parent_id = (
            self._selected_comment_id() if self._reply_check.isChecked() else None
        )
        try:
            self._session.add_comment(project_id, author_id, text, parent_id)
        except SharedProjectError as exc:
            QMessageBox.warning(self, self.tr("Comments"), str(exc))
            return
        self._editor.clear()
        self._reply_check.setChecked(False)

    def _on_resolve(self) -> None:
        """Resolve the selected comment."""
        if self._session is None:
            return
        project_id = self._session.active_project_id()
        comment_id = self._selected_comment_id()
        if project_id is None or comment_id is None:
            return
        try:
            self._session.resolve_comment(project_id, comment_id)
        except SharedProjectError as exc:
            QMessageBox.warning(self, self.tr("Comments"), str(exc))

    # -- session reactions ------------------------------------------------

    def _on_comments_changed(self, _project_id: str) -> None:
        self._refresh()

    def _on_shared_changed(self, _project_id: str) -> None:
        self._refresh()

    # -- view population --------------------------------------------------

    def _refresh(self) -> None:
        self._tree.clear()
        if self._session is None:
            self._update_enabled()
            return
        project_id = self._session.active_project_id()
        if project_id is None:
            self._update_enabled()
            return
        items: Dict[str, QTreeWidgetItem] = {}
        for comment in self._session.comments(project_id):
            item = self._make_item(comment)
            parent = items.get(comment.parent_id) if comment.parent_id else None
            if parent is not None:
                parent.addChild(item)
            else:
                self._tree.addTopLevelItem(item)
            items[comment.comment_id] = item
        self._tree.expandAll()
        self._update_enabled()

    def _make_item(self, comment: ProjectComment) -> QTreeWidgetItem:
        status = self.tr("Resolved") if comment.resolved else self.tr("Open")
        item = QTreeWidgetItem([comment.author_id, comment.text, status])
        item.setData(0, Qt.ItemDataRole.UserRole, comment.comment_id)
        return item

    def _selected_comment_id(self) -> Optional[str]:
        item = self._tree.currentItem()
        if item is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value) if isinstance(value, str) else None

    def _update_counter(self) -> None:
        used = len(self._editor.toPlainText().encode("utf-8"))
        self._counter.setText(
            self.tr("%1 / %2 bytes")
            .replace("%1", str(used))
            .replace("%2", str(MAX_COMMENT_BYTES))
        )

    def _update_enabled(self) -> None:
        has_selection = self._selected_comment_id() is not None
        self._resolve_button.setEnabled(has_selection)
        self._reply_check.setEnabled(has_selection)

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Comments"))
        self._author_label.setText(self.tr("Your member id:"))
        self._author_edit.setPlaceholderText(self.tr("e.g. alice"))
        self._author_edit.setAccessibleName(self.tr("Comment author id"))
        self._tree.setHeaderLabels(
            [self.tr("Author"), self.tr("Comment"), self.tr("Status")]
        )
        self._tree.setAccessibleName(self.tr("Comment thread"))
        self._editor.setPlaceholderText(self.tr("Write a comment…"))
        self._editor.setAccessibleName(self.tr("New comment text"))
        self._reply_check.setText(self.tr("Reply to selected"))
        self._reply_check.setAccessibleName(self.tr("Reply to the selected comment"))
        self._add_button.setText(self.tr("Add Comment"))
        self._add_button.setAccessibleName(self.tr("Add the comment"))
        self._resolve_button.setText(self.tr("Resolve"))
        self._resolve_button.setAccessibleName(self.tr("Resolve the selected comment"))
        self._counter.setAccessibleName(self.tr("Comment byte count"))
        self._update_counter()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the comments strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
