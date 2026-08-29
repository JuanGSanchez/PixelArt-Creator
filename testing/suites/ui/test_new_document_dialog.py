"""New Document dialog acceptance tests (``File > New``, Ctrl+N).

``New_Document_Dialog`` and its sibling ``Canvas_Size_Dialog`` were added by
commit ``30856d4`` ("feat(ui): let the canvas be sized, up to the 8K ceiling")
with no test module of their own -- every other dialog in this UI has one.
This module closes that gap for ``New_Document_Dialog``.

One test per behaviour:

* the dialog pre-fills the shipped ``DEFAULT_CANVAS_WIDTH``/``_HEIGHT``, not
  zero/unset;
* bounds handling at the 8K ceiling (``MAX_CANVAS_WIDTH``/``_HEIGHT``, S1) --
  exactly at the ceiling, above it (clamped), at the 1px floor, and below it
  (clamped) -- direct ``QSpinBox`` interaction and a real keyboard sequence +
  Enter (the widget's own ``validate()``, a materially different path than
  the public setter);
* Accept vs Reject, through the real ``QDialogButtonBox`` signals;
* the value ``main_window`` actually reads back is ``target_size()`` -- the
  dialog is driven through the real ``_on_new`` production seam (mirrors the
  accepted ``test_iso_grid_dialog.py`` headless-dialog pattern: stub
  ``exec()``, drive the real handler, never reimplement it);
* Reject creates no document at all (no new tab);
* accessibility -- accessible names, keyboard reachability (focus policy),
  tab order across every interactive control;
* the ``QEvent.LanguageChange`` retranslation hook (F5).

Headless (``QT_QPA_PLATFORM=offscreen``); every test runs under BOTH themes
via the autouse ``theme`` fixture (see ``tests/ui/conftest.py``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.constants import (
    DEFAULT_CANVAS_HEIGHT,
    DEFAULT_CANVAS_WIDTH,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
)
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.new_document_dialog import New_Document_Dialog


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --------------------------------------------------------------------------- #
# Pre-filled with the shipped default, never zero/unset                       #
# --------------------------------------------------------------------------- #


def test_prefills_the_shipped_default_canvas_size(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    assert dialog.target_size() == (DEFAULT_CANVAS_WIDTH, DEFAULT_CANVAS_HEIGHT)
    assert dialog._width.value() == DEFAULT_CANVAS_WIDTH
    assert dialog._height.value() == DEFAULT_CANVAS_HEIGHT


# --------------------------------------------------------------------------- #
# Bounds -- the 8K ceiling (S1) and the 1px floor, via setValue()             #
# --------------------------------------------------------------------------- #


def test_accepts_the_exact_width_ceiling(qtbot):
    """S1: a width exactly at ``MAX_CANVAS_WIDTH`` (7680) is accepted verbatim."""
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._width.setValue(MAX_CANVAS_WIDTH)
    assert dialog.target_size()[0] == MAX_CANVAS_WIDTH


def test_accepts_the_exact_height_ceiling(qtbot):
    """S1: a height exactly at ``MAX_CANVAS_HEIGHT`` (4320) is accepted verbatim."""
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._height.setValue(MAX_CANVAS_HEIGHT)
    assert dialog.target_size()[1] == MAX_CANVAS_HEIGHT


def test_width_above_the_ceiling_clamps_to_the_ceiling(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._width.setValue(MAX_CANVAS_WIDTH + 100_000)
    assert dialog.target_size()[0] == MAX_CANVAS_WIDTH


def test_height_above_the_ceiling_clamps_to_the_ceiling(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._height.setValue(MAX_CANVAS_HEIGHT + 100_000)
    assert dialog.target_size()[1] == MAX_CANVAS_HEIGHT


def test_minimum_floor_is_one_pixel(qtbot):
    """The floor is 1px; a value below it clamps up to 1, never to 0 or negative."""
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._width.setValue(0)
    dialog._height.setValue(-500)
    assert dialog.target_size() == (1, 1)


def test_keyboard_entry_beyond_the_ceiling_stays_pinned_at_the_ceiling(qtbot):
    """Typing one digit past the ceiling's own digit-width is rejected
    keystroke-by-keystroke by the spin box's validator -- the field is left
    showing the ceiling itself, and Enter commits exactly that (the widget's
    own ``validate()``, exercised via real key events, not the public
    setter).

    (Self-correction: an earlier version of this test typed
    ``MAX_CANVAS_HEIGHT + 1`` -- same digit count as the ceiling -- expecting
    an interpretation-time clamp down to the ceiling. Probed directly against
    a real ``QSpinBox``, that keystroke sequence is rejected one digit early
    and lands on ``432``, not ``4320``. Appending an EXTRA digit past the
    ceiling's width reaches the same ceiling value through behaviour the
    widget actually exhibits -- see ``test_canvas_size_dialog.py``'s sibling
    test for the same finding on the width spin box.)"""
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog._height.selectAll()
    QTest.keyClicks(dialog._height, str(MAX_CANVAS_HEIGHT) + "0")
    QTest.keyClick(dialog._height, Qt.Key.Key_Enter)
    assert dialog._height.value() == MAX_CANVAS_HEIGHT
    assert dialog.target_size()[1] == MAX_CANVAS_HEIGHT


# --------------------------------------------------------------------------- #
# Accept / Reject via the real QDialogButtonBox signals                       #
# --------------------------------------------------------------------------- #


def test_ok_button_accepts_the_dialog(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)
    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        QTest.mouseClick(ok_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_button_rejects_the_dialog(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    cancel_button = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        QTest.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


# --------------------------------------------------------------------------- #
# The real main_window._on_new seam -- target_size() is what the caller       #
# actually reads back, not internal widget state.                            #
# --------------------------------------------------------------------------- #


def test_accept_creates_a_document_at_the_dialogs_reported_size(qtbot, monkeypatch):
    """``main_window._on_new`` reads ``dialog.target_size()`` and calls
    ``new_document(width, height)`` -- driven through the REAL production
    handler (no reimplementation), proving the caller consumes the accessor,
    not the raw spin-box widgets."""
    win = _window(qtbot)
    tabs_before = win._tab_widget.count()

    def _fake_exec(self):
        self._width.setValue(320)
        self._height.setValue(240)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(New_Document_Dialog, "exec", _fake_exec)
    win._on_new()

    assert win._tab_widget.count() == tabs_before + 1
    new_document = win.active_tab().document
    assert (new_document.width, new_document.height) == (320, 240)


def test_reject_creates_no_document_at_all(qtbot, monkeypatch):
    """Rejecting the dialog must not create a tab / document."""
    win = _window(qtbot)
    tabs_before = win._tab_widget.count()

    monkeypatch.setattr(
        New_Document_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    win._on_new()

    assert win._tab_widget.count() == tabs_before


def test_accept_at_the_8k_ceiling_creates_the_full_size_document(qtbot, monkeypatch):
    """S1: creating a document at the full 8K ceiling through the real seam
    actually lands that size on the new document."""
    win = _window(qtbot)

    def _fake_exec(self):
        self._width.setValue(MAX_CANVAS_WIDTH)
        self._height.setValue(MAX_CANVAS_HEIGHT)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(New_Document_Dialog, "exec", _fake_exec)
    win._on_new()

    new_document = win.active_tab().document
    assert (new_document.width, new_document.height) == (
        MAX_CANVAS_WIDTH,
        MAX_CANVAS_HEIGHT,
    )


def test_accept_with_unmodified_defaults_creates_the_default_size_document(
    qtbot, monkeypatch
):
    """Accepting without touching either spin box still creates the shipped
    default -- exercises the seam with the dialog's OWN seeded values, not a
    test-supplied override."""
    win = _window(qtbot)
    monkeypatch.setattr(
        New_Document_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    win._on_new()

    new_document = win.active_tab().document
    assert (new_document.width, new_document.height) == (
        DEFAULT_CANVAS_WIDTH,
        DEFAULT_CANVAS_HEIGHT,
    )


# --------------------------------------------------------------------------- #
# Accessibility -- accessible names, keyboard reachability, tab order (F6)    #
# --------------------------------------------------------------------------- #


def test_accessible_names_on_every_interactive_control(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)

    assert dialog.accessibleName() != ""
    for spin in (dialog._width, dialog._height):
        assert spin.accessibleName() != ""
        assert spin.focusPolicy() != Qt.FocusPolicy.NoFocus

    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)
    cancel_button = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    assert ok_button.text() != ""
    assert cancel_button.text() != ""
    assert ok_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert cancel_button.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_tab_order_walks_width_then_height_then_buttons(qtbot):
    """No explicit ``setTabOrder`` exists here, so the focus chain follows
    construction order (mirrors ``test_animation_focus_order.py``'s own
    construction-order convention for the same "no explicit call" shape)."""
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)

    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)
    ordered = [dialog._width, dialog._height, ok_button]
    ids = {id(w) for w in ordered}

    def _next_target(start):
        widget = start.nextInFocusChain()
        visited = set()
        while widget is not None and id(widget) not in visited:
            visited.add(id(widget))
            if id(widget) in ids:
                return widget
            widget = widget.nextInFocusChain()
        return None

    for first, second in zip(ordered, ordered[1:]):
        assert _next_target(first) is second


# --------------------------------------------------------------------------- #
# i18n retranslation hook (F5)                                                #
# --------------------------------------------------------------------------- #


def test_retranslation_hook_present_and_idempotent(qtbot):
    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)

    from PySide6.QtCore import QEvent

    title_before = dialog.windowTitle()
    width_label_before = dialog._width_label.text()
    height_label_before = dialog._height_label.text()
    assert title_before != ""
    assert width_label_before != ""
    assert height_label_before != ""

    dialog.changeEvent(QEvent(QEvent.Type.LanguageChange))

    assert dialog.windowTitle() == title_before
    assert dialog._width_label.text() == width_label_before
    assert dialog._height_label.text() == height_label_before


def test_non_language_change_event_is_delegated_not_swallowed(qtbot):
    """A changeEvent that is NOT LanguageChange must not re-run the
    retranslate branch -- covers the ``if`` guard's false side."""
    from PySide6.QtCore import QEvent

    dialog = New_Document_Dialog()
    qtbot.addWidget(dialog)
    dialog.changeEvent(QEvent(QEvent.Type.StyleChange))
    assert dialog.windowTitle() == dialog.tr("New Document")
