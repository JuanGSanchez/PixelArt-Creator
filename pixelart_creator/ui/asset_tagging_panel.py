# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Asset-tagging panel — add / remove tags on the selected asset (REQ-P11-UI-002).

``Asset_Tagging_Panel`` is a presentation-only :class:`~PySide6.QtWidgets.QWidget` that
edits the tag set of the asset currently selected in the library. It holds **no** domain
logic (Article I / S11): every tag edit is the pure, reversible
:mod:`pixelart_creator.logic.asset_tags` do/undo pair, wrapped by
:class:`~pixelart_creator.ui.commands.AddTagCommand` /
:class:`~pixelart_creator.ui.commands.RemoveTagCommand` and pushed onto the shared
:class:`QUndoStack` the :class:`~pixelart_creator.ui.asset_library_actions.
Asset_Library_Session` owns — so a tag edit is **undoable** and, when undone, restores
the exact prior tag set (REQ-P11-UI-002 acceptance). The change flows through the
session's in-memory catalog and re-populates the tag list via ``catalogChanged``.

Bounds are enforced at the ``asset_tags`` factory **before** a command is built: a tag
over :data:`~pixelart_creator.logic.constants.MAX_TAG_BYTES`, or one that would exceed
:data:`~pixelart_creator.logic.constants.MAX_TAGS_PER_ASSET`, raises
:class:`~pixelart_creator.logic.asset_tags.AssetTagError`, which the panel surfaces as a
**translatable** message and never pushes to the stack (REQ-P11-UI-002 acceptance —
"rejected with a translatable message").

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate (F5 /
REQ-P11-UI-010); every interactive control carries an accessible name and is
keyboard-reachable (REQ-P11-UI-008); colours come from the active QSS theme by role
(REQ-P11-UI-009). All work is synchronous over the in-memory catalog — no worker thread
/ timer (Slice 1).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetDescriptor
from pixelart_creator.logic.asset_tags import (
    AssetTagError,
    make_add_tag,
    make_remove_tag,
)
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.commands import AddTagCommand, RemoveTagCommand


class Asset_Tagging_Panel(QWidget):
    """Add / remove tags on the selected asset, undoably (REQ-P11-UI-002)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Build the tag list, the add-tag row, and the remove control."""
        super().__init__(parent)
        self._session: Optional[Asset_Library_Session] = None
        #: The asset whose tags are being edited (``""`` when none is selected).
        self._asset_id: str = ""

        self._asset_label = QLabel(self)

        self._tag_list = QListWidget(self)
        self._tag_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tag_list.currentItemChanged.connect(self._update_enabled)

        self._tag_edit = QLineEdit(self)
        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_tag)
        self._tag_edit.returnPressed.connect(self._on_add_tag)
        add_row = QHBoxLayout()
        add_row.addWidget(self._tag_edit, 1)
        add_row.addWidget(self._add_button)

        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove_tag)

        layout = QVBoxLayout(self)
        layout.addWidget(self._asset_label)
        layout.addWidget(self._tag_list, 1)
        layout.addLayout(add_row)
        layout.addWidget(self._remove_button)

        self._retranslate()
        self._update_enabled()

    # -- binding ----------------------------------------------------------

    def set_session(self, session: Asset_Library_Session) -> None:
        """Bind the panel to a :class:`Asset_Library_Session` and refresh."""
        self._session = session
        session.catalogChanged.connect(self._refresh_tags)
        self._refresh_tags()

    def set_asset(self, asset_id: str) -> None:
        """Follow the library selection: edit ``asset_id``'s tags (``""`` = none)."""
        self._asset_id = asset_id or ""
        self._refresh_tags()

    # -- tag edits (undoable via the shared stack) ------------------------

    def _on_add_tag(self) -> None:
        """Add the typed tag to the selected asset as one undoable command."""
        if self._session is None:
            return
        descriptor = self._current_descriptor()
        if descriptor is None:
            return
        tag = self._tag_edit.text().strip()
        if not tag:
            return
        try:
            tag_op = make_add_tag(descriptor, tag)
        except AssetTagError as exc:
            QMessageBox.warning(self, self.tr("Tagging"), str(exc))
            return
        command = AddTagCommand(
            tag_op,
            self._session.replace_descriptor,
            self.tr('Add tag "%1"').replace("%1", tag),
        )
        self._session.undo_stack().push(command)
        self._tag_edit.clear()

    def _on_remove_tag(self) -> None:
        """Remove the selected tag from the selected asset as one undoable command."""
        if self._session is None:
            return
        descriptor = self._current_descriptor()
        if descriptor is None:
            return
        item = self._tag_list.currentItem()
        if item is None:
            return
        tag = item.text()
        try:
            tag_op = make_remove_tag(descriptor, tag)
        except AssetTagError as exc:
            QMessageBox.warning(self, self.tr("Tagging"), str(exc))
            return
        command = RemoveTagCommand(
            tag_op,
            self._session.replace_descriptor,
            self.tr('Remove tag "%1"').replace("%1", tag),
        )
        self._session.undo_stack().push(command)

    # -- helpers ----------------------------------------------------------

    def _current_descriptor(self) -> Optional[AssetDescriptor]:
        """Return the selected asset's descriptor, or ``None`` if unresolved."""
        if self._session is None or not self._asset_id:
            return None
        return self._session.catalog().get(self._asset_id)

    def _refresh_tags(self) -> None:
        """Repopulate the tag list from the current asset descriptor."""
        self._tag_list.clear()
        descriptor = self._current_descriptor()
        if descriptor is not None:
            for tag in sorted(descriptor.tags):
                self._tag_list.addItem(tag)
        self._update_labels()
        self._update_enabled()

    def _update_enabled(self) -> None:
        has_asset = self._current_descriptor() is not None
        self._tag_edit.setEnabled(has_asset)
        self._add_button.setEnabled(has_asset)
        self._remove_button.setEnabled(
            has_asset and self._tag_list.currentItem() is not None
        )

    # -- i18n -------------------------------------------------------------

    def _update_labels(self) -> None:
        descriptor = self._current_descriptor()
        if descriptor is None:
            self._asset_label.setText(self.tr("No asset selected"))
        else:
            self._asset_label.setText(
                self.tr("Tags for: %1").replace("%1", descriptor.name)
            )

    def _retranslate(self) -> None:
        self.setAccessibleName(self.tr("Asset tagging"))
        self._tag_list.setAccessibleName(self.tr("Asset tags"))
        self._tag_edit.setPlaceholderText(self.tr("New tag"))
        self._tag_edit.setAccessibleName(self.tr("New tag"))
        self._add_button.setText(self.tr("Add Tag"))
        self._add_button.setAccessibleName(self.tr("Add tag to asset"))
        self._remove_button.setText(self.tr("Remove Tag"))
        self._remove_button.setAccessibleName(self.tr("Remove selected tag"))
        self._update_labels()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the tagging strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
