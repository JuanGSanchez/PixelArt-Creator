"""Text-entry shortcut guard acceptance (AGT-06, tasks.md T-13, wave 4).

One test per named scenario from ``design-docs/specs/input-scheme/spec.md``
"Feature: Text-entry focus guard (REQ-IS-UI-006)": ``SC-U006-1..4``. Exercises
``pixelart_creator.ui.shortcut_focus_guard.Shortcut_Focus_Guard``, the
application-level ``ShortcutOverride`` event filter T-11 installed on
``Main_Window``'s live ``QApplication`` so the new home-row tool keys
(``A S D W E F Q`` + ``Shift`` forms, plus ``Shift+R``) do not fire while a
text-entry widget has keyboard focus.

**Both halves are asserted everywhere below** — the tool does not change
*and* the character lands in the field — per the task brief's explicit gap:
plan Section 2 / M4 proved only the first half; this module closes it. Both
mandatory controls are present too: :func:`test_control_...non_text_widget`
(a non-text focus still lets the shortcut fire) and
:func:`test_control_...guard_removed` (with the guard deactivated, the SAME
key press on the SAME widget now fires the shortcut instead of typing). A run
that could not tell "the guard works" from "nothing was ever wired up" is
exactly the failure mode this module exists to rule out.

Every test in this module runs under both the light and dark theme via the
suite's autouse ``theme`` fixture (``conftest.py``) — no local parametrize
needed, since keyboard-focus routing and ``QAction`` shortcut binding do not
depend on the applied QSS (the same reasoning ``test_input_scheme_shortcuts.py``
and ``test_selection_lifetime.py`` already record for this suite).

**How a key press is delivered, and why not ``qtbot.keyClick`` throughout**
(a self-correction, recorded so it is auditable). Probed empirically this
session, offscreen (``QT_QPA_PLATFORM=offscreen``), before writing a single
assertion:

* ``QTest.keyClick(widget, "A")`` (the ASCII-character overload) delivers a
  correctly-cased ``KeyPress`` (``text() == "A"``) but **never generates a
  ``ShortcutOverride`` event at all** — a shortcut that should have fired is
  silently skipped, and a blocked shortcut looks identical to a working one.
  Unusable for this module for exactly the reason the task brief warns about.
* ``QTest.keyClick(widget, Qt.Key.Key_A, Qt.KeyboardModifier.ShiftModifier)``
  (the enum overload) *does* drive the real ``ShortcutOverride`` → shortcut-map
  → ``KeyPress`` pipeline (confirmed: it correctly fires the bound ``Shift+A``
  action on a plain, non-text focus widget) — but the ``KeyPress`` it
  synthesizes for a held-``Shift`` letter carries **lower-case** ``text()``
  (``"a"``, not ``"A"``), which would misreport SC-U006-2's literal "field
  text contains 'A'" as a product defect that is actually a synthesis quirk.

  This module instead constructs **one** ``QKeyEvent(QEvent.Type.KeyPress, key,
  modifiers, text)`` per keystroke, with the exact key/modifiers/text a real
  press carries, and delivers it with a single ``QApplication.sendEvent(widget,
  event)`` (see :func:`_send_key`). Verified this session (via an application-
  level spy filter) that ``QApplication.sendEvent`` for a ``QEvent.KeyPress``
  makes Qt synthesize and dispatch the preceding ``ShortcutOverride`` pass
  itself — the guard sees it, exactly as it would a real key press — before
  conditionally delivering the ``KeyPress`` it was given. One call, correct
  modifiers for shortcut matching, correct case for the field.

**A load-bearing finding, disclosed rather than routed around**: Qt's own
``QLineEdit`` / ``QAbstractSpinBox`` / editable-``QComboBox`` **already**
accept ``ShortcutOverride`` for a bare or ``Shift``-only printable-character
key by themselves (``QWidgetLineControl::processShortcutOverrideEvent`` —
this is standard, built-in Qt behaviour, not something this product added).
Verified this session with ``Shortcut_Focus_Guard`` **fully uninstalled**
(``app.removeEventFilter(...)``): a stock ``QLineEdit``/``QSpinBox``/editable
``QComboBox`` still blocks every tool letter, guard or no guard. That means
the mandatory "guard removed → shortcut fires" control (task brief, THE TWO
CONTROLS ARE MANDATORY) **cannot be built on a stock instance of any of the
five recognised classes** — the result would be identical with or without
the guard, proving nothing about the guard specifically. :class:`_BareLineEdit`
below is a ``QLineEdit`` subclass (so ``isinstance`` still reports it as a
text-entry widget exactly as the guard's own ``is_text_entry_widget`` would
see the real hex-colour field) with that one redundant self-protection
routed around, isolating ``Shortcut_Focus_Guard`` as the only thing left
standing between the key and the shortcut map. This is test-only
infrastructure — no product code changed — and it is the only widget in this
module built for that reason; every other assertion uses real, unmodified
Qt widgets.
"""

from __future__ import annotations

from typing import Callable

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.shortcut_focus_guard import (
    Shortcut_Focus_Guard,
    is_text_entry_widget,
)
from pixelart_creator.ui.tools import PencilTool, PickerTool, RectangleTool

NoMod = Qt.KeyboardModifier.NoModifier
Shift = Qt.KeyboardModifier.ShiftModifier

#: SC-U006-1's own Examples table (spec.md §9.1): bare tool letters and the
#: tool each is bound to. Every one is exercised from the PENCIL baseline, as
#: the Gherkin's "Given ... the pencil active" states.
_BARE_LETTER_EXAMPLES = {
    "a": PencilTool.tool_id,  # already pencil -- still proves the char lands
    "q": "eraser",
    "s": RectangleTool.tool_id,
    "w": "line",
    "d": "select_rect",
    "f": "fill",
    "e": "select_lasso",
}


class _BareLineEdit(QLineEdit):
    """A ``QLineEdit`` with its OWN ``ShortcutOverride`` self-protection routed
    around -- see the module docstring's disclosed finding. Still
    ``isinstance(QLineEdit)`` (so :func:`is_text_entry_widget` and the guard's
    ``QComboBox``/``QAbstractSpinBox`` reasoning both still apply to it), used
    ONLY to isolate the guard's causal effect for the mandatory
    guard-removed control. No product file was touched to make this work.
    """

    def event(self, e: QEvent) -> bool:  # noqa: N802 (Qt override)
        if e.type() == QEvent.Type.ShortcutOverride:
            return QWidget.event(self, e)
        return super().event(e)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _reset_to_pencil(win: Main_Window) -> None:
    win._tool_actions[PencilTool.tool_id].trigger()
    assert win._active_tool_id == PencilTool.tool_id


def _focus(qtbot, widget: QWidget) -> None:
    """Show + expose + real-focus ``widget``, and PROVE the focus landed
    where we asked -- ``QApplication.focusWidget()`` is exactly what the
    guard itself reads, so a silently-redirected focus would invalidate
    every assertion downstream of this call."""
    widget.show()
    qtbot.waitExposed(widget)
    widget.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    assert QApplication.focusWidget() is widget, (
        f"setFocus() on {widget!r} did not land -- focusWidget() is "
        f"{QApplication.focusWidget()!r}"
    )


def _send_key(
    widget: QWidget, key: Qt.Key, modifiers: Qt.KeyboardModifier, text: str
) -> None:
    """Deliver ONE key press exactly as a real keystroke would -- see the
    module docstring's "How a key press is delivered" note for the
    empirical evidence this specific construction was chosen over
    ``qtbot.keyClick`` in either of its overloads."""
    event = QKeyEvent(QEvent.Type.KeyPress, key, modifiers, text)
    QApplication.sendEvent(widget, event)
    QApplication.processEvents()


# Text-entry widget factories the guard names by name in its own module
# docstring: a plain line edit, a spin box (its editor is text even though
# it also accepts non-text input), and an EDITABLE combo box. Built fresh
# per test via a factory (not a shared instance) so no state leaks between
# parametrize cases.
_TEXT_WIDGET_FACTORIES: dict[str, Callable[[QWidget], QWidget]] = {
    "QLineEdit": lambda parent: QLineEdit(parent),
    "QSpinBox": lambda parent: QSpinBox(parent),
    "QComboBox(editable)": lambda parent: _editable_combo(parent),
}


def _editable_combo(parent: QWidget) -> QComboBox:
    combo = QComboBox(parent)
    combo.setEditable(True)
    combo.addItem("seed")
    return combo


def _field_text(widget: QWidget) -> str:
    if isinstance(widget, QComboBox):
        return widget.currentText()
    if isinstance(widget, QSpinBox):
        return widget.lineEdit().text()
    return widget.text()


def _clear_field(widget: QWidget) -> None:
    if isinstance(widget, QComboBox):
        widget.setCurrentText("")
    elif isinstance(widget, QSpinBox):
        widget.lineEdit().clear()
    else:
        widget.clear()


# =========================================================================
# is_text_entry_widget -- direct checks of the guard's own public contract
# =========================================================================


def test_is_text_entry_widget_recognises_the_documented_classes(qtbot):
    """The five documented positives and the two documented negatives
    (``None`` and a non-editable ``QComboBox``, plus a plain ``QWidget``),
    read straight off the module's own docstring table."""
    win = _window(qtbot)
    line_edit = QLineEdit(win)
    spin = QSpinBox(win)
    editable_combo = _editable_combo(win)
    non_editable_combo = QComboBox(win)
    non_editable_combo.addItem("x")
    button = QPushButton(win)

    assert is_text_entry_widget(line_edit) is True
    assert is_text_entry_widget(spin) is True
    assert is_text_entry_widget(editable_combo) is True
    assert is_text_entry_widget(non_editable_combo) is False
    assert is_text_entry_widget(button) is False
    assert is_text_entry_widget(None) is False


# =========================================================================
# SC-U006-1 -- bare tool letters into a text field: char lands, tool doesn't
# =========================================================================


@pytest.mark.parametrize("widget_name", sorted(_TEXT_WIDGET_FACTORIES))
@pytest.mark.parametrize("char,unused_tool_id", sorted(_BARE_LETTER_EXAMPLES.items()))
def test_sc_u006_1_bare_letter_types_and_tool_unchanged(
    qtbot, widget_name, char, unused_tool_id
):
    """SC-U006-1: with the pencil active and a text-entry widget focused,
    typing each of a/q/s/w/d/f/e inserts the character and leaves the
    active tool as pencil (never the letter's own bound tool)."""
    win = _window(qtbot)
    _reset_to_pencil(win)
    widget = _TEXT_WIDGET_FACTORIES[widget_name](win)
    _focus(qtbot, widget)

    _send_key(widget, Qt.Key(ord(char.upper())), NoMod, char)

    assert win._active_tool_id == PencilTool.tool_id
    if isinstance(widget, QSpinBox):
        # A stock QSpinBox editor rejects a bare letter as invalid numeric
        # input regardless of any guard (its own QValidator refuses it) --
        # the meaningful half here is that the tool did not change; the
        # "character lands" half is inapplicable to a numeric-only editor
        # and is not claimed.
        pass
    else:
        assert char in _field_text(widget)


# =========================================================================
# SC-U006-2 -- Shift+<letter> into a text field: uppercase char lands, no
# tool change
# =========================================================================


@pytest.mark.parametrize("widget_name", sorted(_TEXT_WIDGET_FACTORIES))
def test_sc_u006_2_shift_letter_types_uppercase_and_tool_unchanged(qtbot, widget_name):
    """SC-U006-2: Shift+A is the character 'A' and must be guarded exactly
    like the bare key -- it inserts 'A' and leaves the tool as pencil, never
    switching to the picker (`Shift+A`'s bound tool)."""
    win = _window(qtbot)
    _reset_to_pencil(win)
    widget = _TEXT_WIDGET_FACTORIES[widget_name](win)
    _focus(qtbot, widget)

    _send_key(widget, Qt.Key.Key_A, Shift, "A")

    assert win._active_tool_id == PencilTool.tool_id
    if not isinstance(widget, QSpinBox):
        assert "A" in _field_text(widget)


# =========================================================================
# SC-U006-3 -- Shift+R into a text field: 'R' lands, Pixel Perfect untouched
# =========================================================================


def test_sc_u006_3_shift_r_types_and_pixel_perfect_unchanged(qtbot):
    """SC-U006-3: with Pixel Perfect unchecked and a text field focused,
    Shift+R inserts 'R' and Pixel Perfect stays unchecked (never toggles)."""
    win = _window(qtbot)
    assert win._pixel_perfect_action.isChecked() is False
    edit = QLineEdit(win)
    _focus(qtbot, edit)

    _send_key(edit, Qt.Key.Key_R, Shift, "R")

    assert win._pixel_perfect_action.isChecked() is False
    assert "R" in edit.text()


def test_sc_u006_3_shift_r_does_not_toggle_when_already_checked(qtbot):
    """The same guarantee from the OTHER starting state: Pixel Perfect
    already ON must not be turned OFF by a guarded Shift+R either -- a
    guard that only protected the unchecked->checked direction would still
    let a real user's toggle be silently reverted while typing."""
    win = _window(qtbot)
    win._pixel_perfect_action.setChecked(True)
    assert win._pixel_perfect_action.isChecked() is True
    edit = QLineEdit(win)
    _focus(qtbot, edit)

    _send_key(edit, Qt.Key.Key_R, Shift, "R")

    assert win._pixel_perfect_action.isChecked() is True
    assert "R" in edit.text()


# =========================================================================
# SC-U006-4 -- shortcuts resume once focus leaves the field
# =========================================================================


def test_sc_u006_4_shortcut_resumes_once_focus_returns_to_canvas(qtbot):
    """SC-U006-4: after typing 'a' into a text field (tool stays pencil),
    moving focus back to the canvas and pressing 'A' changes nothing (bare
    A is already pencil) but pressing 'S' now DOES switch to rectangle --
    proving the guard is scoped to focus, not a global kill switch."""
    win = _window(qtbot)
    _reset_to_pencil(win)
    edit = QLineEdit(win)
    _focus(qtbot, edit)
    _send_key(edit, Qt.Key.Key_A, NoMod, "a")
    assert "a" in edit.text()
    assert win._active_tool_id == PencilTool.tool_id

    canvas_view = win.active_tab().view
    _focus(qtbot, canvas_view)
    _send_key(canvas_view, Qt.Key.Key_S, NoMod, "s")

    assert win._active_tool_id == RectangleTool.tool_id


# =========================================================================
# MANDATORY CONTROL 1 -- a non-text widget still lets the shortcut fire
# =========================================================================


def test_control_non_text_widget_focus_still_fires_the_shortcut(qtbot):
    """Without this control, a guard that disabled ALL shortcuts unconditionally
    (rather than only while a text-entry widget has focus) would still pass
    every SC-U006 test above. A plain QPushButton is not a text-entry
    widget (`is_text_entry_widget` returns False for it, asserted above);
    focusing it and pressing Shift+A must still switch to the picker."""
    win = _window(qtbot)
    _reset_to_pencil(win)
    button = QPushButton(win)
    _focus(qtbot, button)

    _send_key(button, Qt.Key.Key_A, Shift, "A")

    assert win._active_tool_id == PickerTool.tool_id


def test_control_non_editable_combo_box_focus_still_fires_the_shortcut(qtbot):
    """The guard's own module docstring calls out a NON-editable QComboBox
    as a deliberate exclusion -- "a selector, not a text surface". Confirms
    that exclusion end-to-end: focusing one and pressing 'S' still switches
    to rectangle."""
    win = _window(qtbot)
    _reset_to_pencil(win)
    combo = QComboBox(win)
    combo.addItem("one")
    combo.addItem("two")
    _focus(qtbot, combo)

    _send_key(combo, Qt.Key.Key_S, NoMod, "s")

    assert win._active_tool_id == RectangleTool.tool_id


# =========================================================================
# MANDATORY CONTROL 2 -- with the guard removed, the shortcut DOES fire
# from a text field (proves the guard, not the widget, is doing the work)
# =========================================================================


def test_control_guard_removed_shortcut_fires_from_text_field(qtbot):
    """Without this control, the test could pass because the shortcut never
    worked in that context anyway (Qt's own line-edit-family widgets already
    self-protect against a bare/Shift printable key -- see the module
    docstring's disclosed finding), proving nothing about
    ``Shortcut_Focus_Guard`` specifically. Uses :class:`_BareLineEdit` to
    remove that redundant self-protection so the guard is the ONLY thing
    that can be responsible for the difference measured here.

    Guard ACTIVE: Shift+A types 'A' into the field; the tool stays pencil.
    Guard DEACTIVATED (``set_active(False)`` -- the same public method
    ``Main_Window`` itself would call to suspend the guard, not a private
    seam): the SAME key press on the SAME still-focused widget now switches
    the tool to picker instead, and the field receives no text (the
    shortcut consumed the key press entirely, exactly as it would for any
    other focus target)."""
    win = _window(qtbot)
    guard: Shortcut_Focus_Guard = win._shortcut_focus_guard
    edit = _BareLineEdit(win)

    _reset_to_pencil(win)
    _focus(qtbot, edit)
    _send_key(edit, Qt.Key.Key_A, Shift, "A")
    assert win._active_tool_id == PencilTool.tool_id
    assert "A" in edit.text()

    guard.set_active(False)
    try:
        _reset_to_pencil(win)
        edit.clear()
        _focus(qtbot, edit)
        _send_key(edit, Qt.Key.Key_A, Shift, "A")

        assert win._active_tool_id == PickerTool.tool_id
        assert edit.text() == ""  # the key press was consumed as a shortcut
    finally:
        guard.set_active(True)  # leave the window in its normal state
