# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Registration prompt — the one shared collection surface (RP-1..RP-5).

``Asset_Register_Dialog`` is the single prompt every in-app registration action
(register-document, register-selection, the export opt-in — T7) shows before an
asset enters the library. Per the ruling contracted once at ``spec.md``'s
"registration prompt" section (CL-P11-6, RP-1..RP-5) it collects **only** a
**display name**, an **asset kind** chosen from the five shipped
:class:`~pixelart_creator.logic.asset_catalog.AssetKind` values, and an
**optional tag set** (RP-1) — the asset's **id**, its **content hash** and its
**dependency edges** are computed elsewhere, never typed here, so this dialog
holds no domain logic and calls into no ``logic/`` construction function
(Article I / S11): it hands the caller three plain values
(:meth:`display_name`, :meth:`kind`, :meth:`tags`) and lets the caller (T7,
then T3's ingress boundary via ``logic/asset_extract.descriptor_for``) do the
computing.

The dialog may open **prefilled** with a suggested name/kind (RP-2), but only
the text the user leaves in the fields when they accept is ever read back — an
overwritten suggestion leaves no trace, because the accessors read live widget
state, not the constructor's suggestion. Input is **validated as it is typed**
(RP-3): an empty/whitespace-only name and a tag set that would exceed
:data:`~pixelart_creator.logic.constants.MAX_TAGS_PER_ASSET` or put any one tag
over :data:`~pixelart_creator.logic.constants.MAX_TAG_BYTES` (UTF-8) both keep
the accept button disabled and show a translatable reason, so this dialog can
never hand back a combination the asset layer would reject — comparing typed
input to the shipped numeric caps is presentation-side guidance, not a
construction of the domain object those caps ultimately belong to. The dialog
is **cancellable** (RP-4): :meth:`exec` returns ``QDialog.DialogCode.Rejected``
and the caller must read no accessor and change nothing — cancelling is not an
error.

Every user-visible string is ``tr()``-wrapped with a ``changeEvent``
retranslate (F5); every interactive control carries an accessible name and is
keyboard-reachable; colours come from the active QSS theme by role only (no
literal colour appears in this file), so the dialog renders correctly under
both the light and the dark theme (``ui/theme.py``).
"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.asset_catalog import AssetKind
from pixelart_creator.logic.constants import MAX_TAG_BYTES, MAX_TAGS_PER_ASSET

#: Combo order = the five shipped kinds, in the vocabulary's own declaration
#: order (``logic/asset_catalog.AssetKind`` — RP-1's "five shipped kinds").
_KIND_ORDER = (
    AssetKind.SPRITE,
    AssetKind.ANIMATION,
    AssetKind.TILESET,
    AssetKind.TILEMAP,
    AssetKind.PALETTE,
)


class Asset_Register_Dialog(QDialog):
    """Collect a display name, kind and optional tags for one new asset entry."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        suggested_name: str = "",
        suggested_kind: AssetKind = AssetKind.SPRITE,
        suggested_tags: Iterable[str] = (),
    ) -> None:
        """Build the prompt, prefilled from the caller's suggestion (RP-2).

        Args:
            parent: Optional Qt parent.
            suggested_name: Initial text of the name field; the user's own
                edit (or the unedited suggestion) is what :meth:`display_name`
                returns, never this argument itself.
            suggested_kind: Initial selection of the kind combo.
            suggested_tags: Initial contents of the tag field, joined with
                ``", "`` for display; purely a starting point (RP-2).
        """
        super().__init__(parent)
        self.setModal(True)

        self._name_edit = QLineEdit(self)
        self._name_edit.setText(suggested_name)
        self._name_edit.textChanged.connect(self._validate)

        self._kind_combo = QComboBox(self)
        for kind in _KIND_ORDER:
            self._kind_combo.addItem("", kind)
        index = self._kind_combo.findData(suggested_kind)
        self._kind_combo.setCurrentIndex(index if index >= 0 else 0)

        self._tags_edit = QLineEdit(self)
        self._tags_edit.setText(", ".join(suggested_tags))
        self._tags_edit.textChanged.connect(self._validate)

        self._name_label = QLabel(self)
        self._kind_label = QLabel(self)
        self._tags_label = QLabel(self)
        self._error_label = QLabel(self)
        self._error_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow(self._name_label, self._name_edit)
        form.addRow(self._kind_label, self._kind_combo)
        form.addRow(self._tags_label, self._tags_edit)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addWidget(self._buttons)

        self._retranslate()
        self._validate()

    # -- accessors read by the caller only after Accepted (RP-4) ----------

    def display_name(self) -> str:
        """Return the display name the user left in the field, stripped."""
        return self._name_edit.text().strip()

    def kind(self) -> AssetKind:
        """Return the :class:`AssetKind` currently selected in the combo."""
        return self._kind_combo.currentData()

    def tags(self) -> "frozenset[str]":
        """Return the parsed, de-duplicated tag set (``frozenset()`` if none)."""
        return self._parsed_tags()[0]

    # -- validation (RP-3) --------------------------------------------------

    def _parsed_tags(self) -> "tuple[frozenset[str], Optional[str]]":
        """Split the tag field on commas and check it against the named caps.

        Returns the parsed tag set plus a translatable rejection reason, or
        ``None`` for the reason when the tag set is within the caps. Blank
        entries produced by e.g. a trailing comma are dropped silently — an
        empty tag set is not itself an error, since the tag set is optional
        (RP-1).
        """
        raw = self._tags_edit.text().split(",")
        tags = frozenset(piece.strip() for piece in raw if piece.strip())
        if len(tags) > MAX_TAGS_PER_ASSET:
            return tags, self.tr("Too many tags: %1 given, %2 allowed.").replace(
                "%1", str(len(tags))
            ).replace("%2", str(MAX_TAGS_PER_ASSET))
        for tag in tags:
            if len(tag.encode("utf-8")) > MAX_TAG_BYTES:
                return tags, self.tr(
                    'Tag "%1" is too long (%2 bytes allowed).'
                ).replace("%1", tag).replace("%2", str(MAX_TAG_BYTES))
        return tags, None

    def _validate(self) -> None:
        """Re-check the form and enable/disable the accept button (RP-3)."""
        reason: Optional[str] = None
        if not self.display_name():
            reason = self.tr("Enter a name for this asset.")
        else:
            _tags, tag_reason = self._parsed_tags()
            reason = tag_reason
        self._error_label.setText(reason or "")
        ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(reason is None)

    # -- i18n / a11y ----------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Register Asset"))
        self.setAccessibleName(self.tr("Asset registration prompt"))

        self._name_label.setText(self.tr("Name"))
        self._name_edit.setAccessibleName(self.tr("Asset display name"))
        self._name_edit.setPlaceholderText(self.tr("Display name"))

        self._kind_label.setText(self.tr("Kind"))
        self._kind_combo.setAccessibleName(self.tr("Asset kind"))
        self._kind_combo.setItemText(0, self.tr("Sprite"))
        self._kind_combo.setItemText(1, self.tr("Animation"))
        self._kind_combo.setItemText(2, self.tr("Tileset"))
        self._kind_combo.setItemText(3, self.tr("Tilemap"))
        self._kind_combo.setItemText(4, self.tr("Palette"))

        self._tags_label.setText(self.tr("Tags"))
        self._tags_edit.setAccessibleName(self.tr("Asset tags, comma-separated"))
        self._tags_edit.setPlaceholderText(self.tr("Optional tags, comma-separated"))

        self._error_label.setAccessibleName(self.tr("Registration validation message"))

        ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(self.tr("Register"))
            ok_button.setAccessibleName(self.tr("Register asset"))
        cancel_button = self._buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText(self.tr("Cancel"))
            cancel_button.setAccessibleName(self.tr("Cancel registration"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the prompt's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
