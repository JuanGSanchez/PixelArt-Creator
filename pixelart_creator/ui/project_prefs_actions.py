"""Project confirmations submenu — the restore path for suppressed preferences.

``build_project_prefs_menu`` renders **one entry per registered**
``logic/project_prefs.py`` preference into an ``&Edit -> Project confirmations``
submenu (REQ-P5-UI-033's restorability half; ADR-0056). Ticking a preference's
"Don't ask again" (``ui/cel_overwrite_dialog.py`` and its future siblings) makes
that entry's checked state true; activating the entry restores the preference to
its declared default so the confirmation asks again. **This is not a settings
dialog** — phase-6 ``REQ-P6-UI-039`` owns that surface, and when it lands it
renders this same registry, so entries move rather than multiply (plan §2).
Setting a preference is not document content (REQ-P5-DATA-004): no
``QUndoCommand`` is pushed. No domain logic lives here (Article I / S11) — this
module only reads ``logic/project_prefs.py``'s registry and calls
``Document.prefs.with_value``.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from pixelart_creator.logic.document import Document
from pixelart_creator.logic.project_prefs import (
    CONFIRM_CEL_OVERWRITE,
    REGISTRY,
    PrefKey,
)

#: The provider the caller supplies: returns the active document, or ``None``
#: when no document is open.
DocumentProvider = Callable[[], Optional[Document]]


class _Project_Prefs_Menu(QMenu):
    """``&Edit -> Project confirmations``: one checkable action per registered key."""

    def __init__(
        self,
        document_provider: DocumentProvider,
        on_changed: Callable[[], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        """Build one action per key currently in ``logic/project_prefs.REGISTRY``.

        ``document_provider`` returns the active document; ``on_changed`` is
        invoked after a preference is restored to its default so the caller can
        refresh anything that depends on it.
        """
        super().__init__(parent)
        self._document_provider = document_provider
        self._on_changed = on_changed
        self._actions: Dict[str, QAction] = {}

        for key in REGISTRY.values():
            self._add_action(key)
        self.aboutToShow.connect(self._sync)

        self._retranslate()

    def _add_action(self, key: PrefKey) -> None:
        action = QAction(self)
        action.setCheckable(True)
        action.setData(key.name)
        action.triggered.connect(lambda _checked, k=key: self._restore(k))
        self.addAction(action)
        self._actions[key.name] = action

    def _restore(self, key: PrefKey) -> None:
        document = self._document_provider()
        if document is None:
            return
        # A preference is not document content (REQ-P5-DATA-004): no
        # QUndoCommand, no dirty-flag implication — a direct assignment.
        document.prefs = document.prefs.with_value(key, key.default)
        self._sync()
        self._on_changed()

    def _sync(self) -> None:
        document = self._document_provider()
        for name, action in self._actions.items():
            key = REGISTRY.get(name)
            if key is None:
                continue
            action.blockSignals(True)
            if document is None:
                action.setChecked(False)
                action.setEnabled(False)
            else:
                action.setEnabled(True)
                action.setChecked(document.prefs.get(key) != key.default)
            action.blockSignals(False)

    # -- i18n / a11y --------------------------------------------------------

    def _label_for(self, key: PrefKey) -> str:
        # Known labels for this slice's own key; a key registered later by
        # another slice (phase-6, phase-11, the canvas warning) through
        # ``project_prefs.register`` falls back to a readable rendering of its
        # name rather than this module inventing a label on that slice's behalf.
        if key.name == CONFIRM_CEL_OVERWRITE.name:
            return self.tr("Confirm before overwriting a cel")
        return self.tr("Confirm: %1").replace("%1", key.name.replace("_", " "))

    def _retranslate(self) -> None:
        self.setTitle(self.tr("Project confirmations"))
        self.setAccessibleName(self.tr("Project confirmations"))
        for name, action in self._actions.items():
            key = REGISTRY.get(name)
            label = self._label_for(key) if key is not None else name
            action.setText(label)
            action.setToolTip(self.tr("Restore this confirmation so it asks again"))

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-translate the submenu's strings on a language change (F5)."""
        if event.type() == QEvent.Type.LanguageChange:
            self._retranslate()
        super().changeEvent(event)


def build_project_prefs_menu(
    document_provider: DocumentProvider,
    on_changed: Callable[[], None],
    parent: Optional[QWidget] = None,
) -> QMenu:
    """Build the ``&Edit -> Project confirmations`` submenu from the registry.

    Args:
        document_provider: Returns the active document, or ``None``.
        on_changed: Invoked (no args) after a preference is restored to its
            default, so the caller can refresh dependents.
        parent: The owning widget (typically the main window), for lifetime.

    Returns:
        The built :class:`QMenu`, ready to add to ``&Edit``.
    """
    return _Project_Prefs_Menu(document_provider, on_changed, parent)
