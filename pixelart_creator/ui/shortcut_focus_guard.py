# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Application-level shortcut guard for text-entry widgets (REQ-IS-UI-006).

The eleven tool actions in ``main_window.py`` carry ``QAction`` shortcuts on
the default ``Qt.ShortcutContext.WindowShortcut`` context, so a bare letter
fires anywhere in the window -- including while the user is typing into a
hex-colour field or a layer-name edit. The new home-row keys (``A S D W E F
Q`` plus their ``Shift`` forms) are far more likely to occur inside ordinary
text than the old ``B G I L M O R`` set, so this guard exists to stop a typed
word from silently switching tools (or toggling Pixel Perfect on
``Shift+R``) while a text-entry widget has keyboard focus.

**The chosen mechanism, and why not the alternative.** An application-level
``eventFilter`` on the live ``QApplication`` intercepts
``QEvent.Type.ShortcutOverride`` -- the event Qt sends to the focus widget
*before* deciding whether a key press is a shortcut -- and, while a
text-entry widget has focus, accepts (consumes) it for a plain character key
with no ``Ctrl``/``Alt``/``Meta`` modifier. That stops the key from being
matched against any ``QAction`` shortcut at all, so it falls through to the
focus widget's own ``keyPressEvent`` and types normally. Disabling the tool
actions on ``focusChanged`` instead was considered and rejected: it greys
eleven toolbar buttons every time the user clicks into a text field, which
reads as the application breaking rather than as a guard the user never
sees (plan `input-scheme` Section 2, "Text-entry shortcut guard").

**What counts as "a text-entry widget", stated precisely.** A naive
``isinstance`` check against a single class misses two real surfaces this
product has: an editable ``QComboBox`` (its internal line edit does not
always surface as :meth:`QApplication.focusWidget` under every platform
plugin -- checking the combo box itself is required, not just its child) and
a ``QAbstractSpinBox`` (a numeric spin box or date/time edit, whose internal
line edit has the same property). The rule implemented by
:func:`is_text_entry_widget` is:

* :class:`~PySide6.QtWidgets.QLineEdit`, :class:`~PySide6.QtWidgets.QTextEdit`
  and :class:`~PySide6.QtWidgets.QPlainTextEdit` (and any subclass) --
  direct text-entry widgets, which also covers the inline editors
  ``QAbstractItemView`` creates on demand (Qt's default item delegate uses a
  ``QLineEdit`` subclass for text roles);
* :class:`~PySide6.QtWidgets.QAbstractSpinBox` (and any subclass, e.g.
  ``QSpinBox``, ``QDoubleSpinBox``, ``QDateEdit``) -- its value is edited as
  text even though the widget also accepts non-text input;
* an *editable* :class:`~PySide6.QtWidgets.QComboBox` (``isEditable()`` is
  ``True``) -- a non-editable combo box is a selector, not a text surface,
  and is deliberately excluded so a shortcut still fires with one focused.

Nothing broader than that: a plain button, checkbox, list view (not being
edited), slider, or the canvas viewport is not a text-entry widget, and a
tool key pressed while one of those has focus still changes the tool -- this
guard is not a blanket shortcut off-switch.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

#: Modifiers that, when held, mean the key press is not ordinary text entry
#: (e.g. Ctrl+S/Ctrl+Z) and must be left alone so the app-level shortcut
#: still fires even while a text-entry widget has focus. ``Shift`` is
#: deliberately absent -- ``Shift+A`` types "A" and must be guarded exactly
#: like the bare key (REQ-IS-UI-006, SC-U006-2).
_NON_TEXT_MODIFIERS = (
    Qt.KeyboardModifier.ControlModifier
    | Qt.KeyboardModifier.AltModifier
    | Qt.KeyboardModifier.MetaModifier
)


def is_text_entry_widget(widget: Optional[QWidget]) -> bool:
    """Return whether ``widget`` is a surface a character key should type into.

    See the module docstring for the exact rule and what it deliberately
    excludes.
    """
    if widget is None:
        return False
    if isinstance(widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
        return True
    if isinstance(widget, QComboBox) and widget.isEditable():
        return True
    return False


def _is_guardable_character_press(event: QKeyEvent) -> bool:
    """Return whether ``event`` is a plain (optionally ``Shift``ed) character key.

    Excludes any press carrying ``Ctrl``/``Alt``/``Meta`` (those are never
    ordinary text and must keep working as app-level shortcuts, e.g.
    ``Ctrl+S``) and excludes non-printable keys (``Escape``, arrows, ``Tab``,
    …), which are not text either.
    """
    if event.modifiers() & _NON_TEXT_MODIFIERS:
        return False
    text = event.text()
    return bool(text) and text.isprintable()


class Shortcut_Focus_Guard(QObject):
    """Consumes ``ShortcutOverride`` while a text-entry widget has focus.

    Installed once on the live :class:`QApplication` (application-level
    filter, per REQ-IS-UI-006 / plan Section 2 M4) -- not on any one widget --
    so it sees every key press regardless of which text field the user is in.
    Holds no domain state and calls into no ``logic/`` module: this is a
    pure Qt focus/event decision (S11).
    """

    def __init__(self, app: QApplication, parent: Optional[QObject] = None) -> None:
        """Wrap ``app``; ``parent`` defaults to ``app`` so Qt keeps it alive."""
        super().__init__(parent if parent is not None else app)
        self._app = app
        self._active = True

    def set_active(self, active: bool) -> None:
        """Enable/disable the guard without uninstalling the event filter."""
        self._active = bool(active)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Consume a guardable ``ShortcutOverride`` while focus is text entry."""
        if (
            self._active
            and event.type() == QEvent.Type.ShortcutOverride
            and isinstance(event, QKeyEvent)
            and _is_guardable_character_press(event)
            and is_text_entry_widget(QApplication.focusWidget())
        ):
            event.accept()
            return True
        return super().eventFilter(watched, event)
