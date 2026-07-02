"""Palette-swap dialog (REQ-P3-UI-013): define + apply an index remap.

``Palette_Swap_Dialog`` lets the user build an index→index remap (old → new) and
apply it to recolour indexed art. Applying it is a reversible
:func:`pixelart_creator.logic.palette_ops.make_swap_command` wrapped as one
:class:`~pixelart_creator.ui.commands.LogicCommand`, so undo restores the pre-swap
buffer exactly (SC-U013-1/-2). This dialog only collects the mapping; the swap
maths live in ``logic/`` (Article I / S11). Strings are ``tr()``-wrapped and re-set
on :data:`QEvent.Type.LanguageChange` (F5); every control is keyboard-reachable and
legible in both themes.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class Palette_Swap_Dialog(QDialog):
    """Collect an index→index remap to apply to an indexed buffer."""

    def __init__(self, max_index: int = 255, parent: Optional[QWidget] = None) -> None:
        """Build the from/to spins, the mapping list, and dialog buttons."""
        super().__init__(parent)
        self._mapping: Dict[int, int] = {}
        bound = max(0, min(255, max_index))

        self._from_spin = QSpinBox(self)
        self._to_spin = QSpinBox(self)
        for spin in (self._from_spin, self._to_spin):
            spin.setRange(0, bound)
        self._from_label = QLabel(self)
        self._to_label = QLabel(self)
        self._add_button = QPushButton(self)
        self._add_button.clicked.connect(self._on_add_pair)
        self._remove_button = QPushButton(self)
        self._remove_button.clicked.connect(self._on_remove_pair)

        self._list = QListWidget(self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        pair_row = QHBoxLayout()
        pair_row.addWidget(self._from_label)
        pair_row.addWidget(self._from_spin)
        pair_row.addWidget(self._to_label)
        pair_row.addWidget(self._to_spin)
        pair_row.addWidget(self._add_button)
        pair_row.addWidget(self._remove_button)
        layout = QVBoxLayout(self)
        layout.addLayout(pair_row)
        layout.addWidget(self._list)
        layout.addWidget(self._buttons)
        self._retranslate()

    # -- public API -------------------------------------------------------

    def mapping(self) -> Dict[int, int]:
        """Return the collected index→index remap (copy)."""
        return dict(self._mapping)

    # -- slots ------------------------------------------------------------

    def _on_add_pair(self) -> None:
        src, dst = self._from_spin.value(), self._to_spin.value()
        self._mapping[src] = dst
        self._refresh_list()

    def _on_remove_pair(self) -> None:
        row = self._list.currentRow()
        keys = sorted(self._mapping)
        if 0 <= row < len(keys):
            del self._mapping[keys[row]]
            self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.clear()
        for src in sorted(self._mapping):
            self._list.addItem(f"{src} → {self._mapping[src]}")

    # -- i18n -------------------------------------------------------------

    def _retranslate(self) -> None:
        self.setWindowTitle(self.tr("Palette Swap"))
        self.setAccessibleName(self.tr("Palette swap dialog"))
        self._from_label.setText(self.tr("From index"))
        self._to_label.setText(self.tr("To index"))
        self._from_spin.setAccessibleName(self.tr("Source index"))
        self._to_spin.setAccessibleName(self.tr("Target index"))
        self._add_button.setText(self.tr("Add"))
        self._remove_button.setText(self.tr("Remove"))
        self._list.setAccessibleName(self.tr("Index remap entries"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


__all__ = ["Palette_Swap_Dialog"]
