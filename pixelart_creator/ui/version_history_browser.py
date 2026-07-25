"""Cloud version-history browser (REQ-P10-UI-002).

``Version_History_Browser`` is a presentation-only :class:`~PySide6.QtWidgets.QDialog`
over the ordered, immutable version list produced by the Qt-free
:class:`~pixelart_creator.logic.version_history.VersionHistory` (via the cloud
port's ``list_versions``). It lists each version deterministically (newest last,
as the history orders them), previews the selected version's metadata, and lets
the user pick one to **restore**. It performs **no** cloud I/O and **no** decode
itself — the caller submits the actual ``get`` + defensive PIO-1 decode off the
GUI thread and opens the reconstructed document into a *new* tab, so the current
unsaved state is protected (REQ-P10-DATA-004 semantics).

Every user-visible string is ``tr()``-wrapped with a ``changeEvent`` retranslate
(F5/REQ-P10-UI-008); every interactive control carries an accessible name and the
list is keyboard-reachable (REQ-P10-UI-006); colours come from the active QSS
theme by role, so both themes render correctly (REQ-P10-UI-007).
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelart_creator.logic.version_history import CloudVersion

#: Column order of the version tree (presentation-only layout, not a domain value).
_COL_ORDINAL = 0
_COL_MARKER = 1
_COL_SIZE = 2
_COL_PINNED = 3
_COL_PARENT = 4


class Version_History_Browser(QDialog):
    """List ordered cloud versions and let the user restore one (REQ-P10-UI-002)."""

    def __init__(
        self,
        versions: Sequence[CloudVersion],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build the browser over an already-fetched, ordered ``versions`` list.

        The versions are fetched off the GUI thread by the caller and handed in
        here (this widget never touches the port), so opening the browser cannot
        freeze the UI (REQ-P10-UI-005).
        """
        super().__init__(parent)
        self._versions: tuple[CloudVersion, ...] = tuple(versions)

        self._intro = QLabel(self)
        self._intro.setWordWrap(True)

        self._tree = QTreeWidget(self)
        self._tree.setColumnCount(5)
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        self._tree.itemDoubleClicked.connect(self._on_double_click)

        self._detail = QLabel(self)
        self._detail.setWordWrap(True)
        self._detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self._buttons = QDialogButtonBox(self)
        self._restore_button = QPushButton(self)
        self._buttons.addButton(
            self._restore_button, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._intro)
        layout.addWidget(self._tree, 1)
        layout.addWidget(self._detail)
        layout.addWidget(self._buttons)

        self._populate()
        self._retranslate()
        self._update_enabled()

    # -- population -------------------------------------------------------

    def _populate(self) -> None:
        """Fill the tree from the ordered version list (deterministic order)."""
        self._tree.clear()
        for version in self._versions:
            item = QTreeWidgetItem(
                [
                    str(version.ordinal),
                    str(version.created_marker),
                    str(version.size_bytes),
                    "",  # pinned text set in _retranslate (translatable Yes/No)
                    version.parent_version_id or "",
                ]
            )
            item.setData(_COL_ORDINAL, Qt.ItemDataRole.UserRole, version)
            self._tree.addTopLevelItem(item)
        last = self._tree.topLevelItem(self._tree.topLevelItemCount() - 1)
        if last is not None:
            self._tree.setCurrentItem(last)

    # -- public API -------------------------------------------------------

    def selected_version(self) -> Optional[CloudVersion]:
        """Return the currently selected :class:`CloudVersion`, or ``None``."""
        item = self._tree.currentItem()
        if item is None:
            return None
        version = item.data(_COL_ORDINAL, Qt.ItemDataRole.UserRole)
        return version if isinstance(version, CloudVersion) else None

    # -- slots ------------------------------------------------------------

    def _on_selection_changed(
        self,
        _current: Optional[QTreeWidgetItem],
        _previous: Optional[QTreeWidgetItem],
    ) -> None:
        self._update_detail()
        self._update_enabled()

    def _on_double_click(self, _item: QTreeWidgetItem, _column: int) -> None:
        """Restore the double-clicked version (keyboard Enter also accepts)."""
        if self.selected_version() is not None:
            self.accept()

    def _update_enabled(self) -> None:
        self._restore_button.setEnabled(self.selected_version() is not None)

    def _update_detail(self) -> None:
        version = self.selected_version()
        if version is None:
            self._detail.setText(self.tr("Select a version to restore."))
            return
        # Placeholders (%1..) keep word order translatable (never string '+').
        self._detail.setText(
            self.tr("Version %1 — %2 bytes (created marker %3).")
            .replace("%1", str(version.ordinal))
            .replace("%2", str(version.size_bytes))
            .replace("%3", str(version.created_marker))
        )

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Cloud Version History"))
        self._intro.setText(
            self.tr(
                "Prior cloud saves, oldest first. Restoring opens the chosen "
                "version in a new tab — your current work is not overwritten."
            )
        )
        self._tree.setHeaderLabels(
            [
                self.tr("Version"),
                self.tr("Marker"),
                self.tr("Size (bytes)"),
                self.tr("Pinned"),
                self.tr("Parent"),
            ]
        )
        yes = self.tr("Yes")
        no = self.tr("No")
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item is None:
                continue
            version = item.data(_COL_ORDINAL, Qt.ItemDataRole.UserRole)
            if isinstance(version, CloudVersion):
                item.setText(_COL_PINNED, yes if version.is_pinned else no)
        self._restore_button.setText(self.tr("Restore"))
        self._tree.setAccessibleName(self.tr("Cloud version list"))
        self._restore_button.setAccessibleName(self.tr("Restore selected version"))
        self._update_detail()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the browser strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)
