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

**Rendering is generic by domain size (plan §3.4, ruling P11-R2), not keyed on
any one slice's key name.** A two-member domain (``phase-5``'s
``confirm_cel_overwrite``) still renders as a single checkable action whose
activation restores the default — byte-for-byte what shipped before this
ruling. A domain with more than two members (``phase-11``'s
``asset_library_edit``) renders as a nested, exclusive submenu — one checkable
action per value — because a single checkbox cannot show which of two
non-default outcomes is remembered. Both shapes read/write through the same
``logic/project_prefs.py`` seam and neither pushes a ``QUndoCommand``.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from pixelart_creator.logic.asset_references import ASSET_LIBRARY_EDIT
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.project_prefs import (
    CONFIRM_CEL_OVERWRITE,
    REGISTRY,
    PrefKey,
)

#: A domain wider than this renders as a nested exclusive submenu rather than
#: a single checkable action (plan §3.4) — a plain boolean-shaped preference
#: (ask / suppressed) keeps the shipped single-checkbox rendering.
_BINARY_DOMAIN_SIZE = 2

#: Menu-rendering strings share one translation context with the class below
#: so :func:`value_label_for` — a free function, exported for a future
#: renderer (phase-6's settings dialog) — is caught by the same ``tr()``
#: extraction pass as the class's own strings.
_TR_CONTEXT = "_Project_Prefs_Menu"


def value_label_for(key: PrefKey, value: str) -> str:
    """Return ``value``'s label, in the user's own words, for ``key``.

    Exported at module level (plan §3.4) so a later renderer of the same
    ``logic/project_prefs.REGISTRY`` — phase-6's ``REQ-P6-UI-039`` settings
    dialog is the named future consumer — shows the identical strings this
    submenu does, rather than maintaining a second copy.

    A key this module does not itself own (a future slice's) falls back to a
    readable rendering of the raw value rather than inventing a label on that
    slice's behalf — the same policy ``_label_for`` applies to unknown keys.
    """
    if key.name == ASSET_LIBRARY_EDIT.name:
        labels = {
            "ask": QCoreApplication.translate(
                "_Project_Prefs_Menu", "Ask me every time"
            ),
            "always_pick_up": QCoreApplication.translate(
                "_Project_Prefs_Menu", "Always pick up the library change"
            ),
            "always_keep_referenced": QCoreApplication.translate(
                "_Project_Prefs_Menu", "Always keep the referenced version"
            ),
        }
        if value in labels:
            return labels[value]
    return QCoreApplication.translate("_Project_Prefs_Menu", "Set to: %1").replace(
        "%1", value.replace("_", " ")
    )


#: The provider the caller supplies: returns the active document, or ``None``
#: when no document is open.
DocumentProvider = Callable[[], Optional[Document]]


class _Project_Prefs_Menu(QMenu):
    """``&Edit -> Project confirmations``: one entry per registered key.

    A two-value key renders as one checkable action; a key with more than
    two values renders as a nested exclusive submenu (plan §3.4).
    """

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
        self._submenus: Dict[str, QMenu] = {}
        self._value_actions: Dict[str, Dict[str, QAction]] = {}

        for key in REGISTRY.values():
            if len(key.domain) > _BINARY_DOMAIN_SIZE:
                self._add_submenu(key)
            else:
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

    def _add_submenu(self, key: PrefKey) -> None:
        # A domain with more than two members cannot be shown by one checkbox
        # (plan §3.4, ruling P11-R2): a nested menu holds one checkable action
        # per value, in an exclusive group, so exactly one reads "checked" —
        # the remembered outcome — at a time.
        submenu = QMenu(self)
        menu_action = submenu.menuAction()
        menu_action.setData(key.name)
        self.addMenu(submenu)
        group = QActionGroup(submenu)
        group.setExclusive(True)
        value_actions: Dict[str, QAction] = {}
        for value in sorted(key.domain):
            action = QAction(submenu)
            action.setCheckable(True)
            action.setData((key.name, value))
            action.setActionGroup(group)
            action.triggered.connect(
                lambda _checked, k=key, v=value: self._select(k, v)
            )
            submenu.addAction(action)
            value_actions[value] = action
        self._submenus[key.name] = submenu
        self._value_actions[key.name] = value_actions

    def _restore(self, key: PrefKey) -> None:
        document = self._document_provider()
        if document is None:
            return
        # A preference is not document content (REQ-P5-DATA-004): no
        # QUndoCommand, no dirty-flag implication — a direct assignment.
        document.prefs = document.prefs.with_value(key, key.default)
        self._sync()
        self._on_changed()

    def _select(self, key: PrefKey, value: str) -> None:
        document = self._document_provider()
        if document is None:
            return
        # Same non-undoable direct-assignment contract as _restore — picking
        # a remembered outcome is not document content either.
        document.prefs = document.prefs.with_value(key, value)
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
        for name, value_actions in self._value_actions.items():
            key = REGISTRY.get(name)
            submenu = self._submenus.get(name)
            if key is None:
                continue
            enabled = document is not None
            current = document.prefs.get(key) if document is not None else None
            if submenu is not None:
                submenu.menuAction().setEnabled(enabled)
            for value, action in value_actions.items():
                action.blockSignals(True)
                action.setEnabled(enabled)
                action.setChecked(enabled and current == value)
                action.blockSignals(False)

    # -- i18n / a11y --------------------------------------------------------

    def _label_for(self, key: PrefKey) -> str:
        # Known labels for this slice's own key; a key registered later by
        # another slice (phase-6, phase-11, the canvas warning) through
        # ``project_prefs.register`` falls back to a readable rendering of its
        # name rather than this module inventing a label on that slice's behalf.
        if key.name == CONFIRM_CEL_OVERWRITE.name:
            return self.tr("Confirm before overwriting a cel")
        if key.name == ASSET_LIBRARY_EDIT.name:
            return self.tr("When a referenced library asset changes")
        return self.tr("Confirm: %1").replace("%1", key.name.replace("_", " "))

    def _retranslate(self) -> None:
        self.setTitle(self.tr("Project confirmations"))
        self.setAccessibleName(self.tr("Project confirmations"))
        for name, action in self._actions.items():
            key = REGISTRY.get(name)
            label = self._label_for(key) if key is not None else name
            action.setText(label)
            action.setToolTip(self.tr("Restore this confirmation so it asks again"))
        for name, submenu in self._submenus.items():
            key = REGISTRY.get(name)
            label = self._label_for(key) if key is not None else name
            submenu.setTitle(label)
            submenu.setAccessibleName(label)
            for value, action in self._value_actions.get(name, {}).items():
                if key is not None:
                    action.setText(value_label_for(key, value))
                else:
                    action.setText(value)

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
