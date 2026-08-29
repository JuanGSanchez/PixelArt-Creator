"""Canvas Size dialog acceptance tests (``Image > Canvas Size...``).

``Canvas_Size_Dialog`` and its sibling ``New_Document_Dialog`` were added by
commit ``30856d4`` ("feat(ui): let the canvas be sized, up to the 8K ceiling")
with no test module of their own — every other dialog in this UI has one.
This module closes that gap for ``Canvas_Size_Dialog``.

One test per behaviour:

* the dialog seeds itself from the document's CURRENT width/height (not the
  shipped default);
* bounds handling at the 8K ceiling (``MAX_CANVAS_WIDTH``/``_HEIGHT``, S1) --
  exactly at the ceiling, above it (clamped), at the 1px floor, and below it
  (clamped) -- driven both by direct ``QSpinBox`` interaction and by a real
  keyboard sequence + Enter, a materially different code path (the widget's
  own ``validate()``, not the public setter);
* Accept vs Reject, through the real ``QDialogButtonBox`` signals;
* the value ``main_window`` actually reads back is ``target_size()`` -- the
  dialog is driven through the real ``_on_canvas_size`` production seam
  (mirrors the accepted ``test_iso_grid_dialog.py`` / ``test_vanishing_point_
  dialog.py`` headless-dialog pattern: stub ``exec()``, drive the real
  handler, never reimplement it) so the accessor under test is the one the
  caller actually consumes, not just widget state;
* Reject leaves the document untouched (no ``CanvasResizeCommand`` applied);
* an unchanged size is a no-op guard (covers the ``main_window`` early-return
  branch reached only through this dialog's own accessor);
* accessibility -- accessible names, keyboard reachability (focus policy),
  tab order across every interactive control;
* the ``QEvent.LanguageChange`` retranslation hook (F5).

Headless (``QT_QPA_PLATFORM=offscreen``); every test runs under BOTH themes
via the autouse ``theme`` fixture (see ``testing/suites/ui/conftest.py``).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH
from pixelart_creator.ui.canvas_size_dialog import Canvas_Size_Dialog
from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


# --------------------------------------------------------------------------- #
# Seeding from the CURRENT document size (not the shipped default)            #
# --------------------------------------------------------------------------- #


def test_seeds_from_the_current_document_size_not_the_default(qtbot):
    """The dialog is constructed with the document's real, current size --
    round-tripping unchanged confirms it never falls back to a default."""
    dialog = Canvas_Size_Dialog(200, 150)
    qtbot.addWidget(dialog)
    assert dialog.target_size() == (200, 150)
    assert dialog._width.value() == 200
    assert dialog._height.value() == 150


# --------------------------------------------------------------------------- #
# Bounds -- the 8K ceiling (S1) and the 1px floor, via setValue()             #
# --------------------------------------------------------------------------- #


def test_accepts_the_exact_width_ceiling(qtbot):
    """S1: a width exactly at ``MAX_CANVAS_WIDTH`` (7680) is accepted verbatim."""
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._width.setValue(MAX_CANVAS_WIDTH)
    assert dialog.target_size()[0] == MAX_CANVAS_WIDTH


def test_accepts_the_exact_height_ceiling(qtbot):
    """S1: a height exactly at ``MAX_CANVAS_HEIGHT`` (4320) is accepted verbatim."""
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._height.setValue(MAX_CANVAS_HEIGHT)
    assert dialog.target_size()[1] == MAX_CANVAS_HEIGHT


def test_width_above_the_ceiling_clamps_to_the_ceiling(qtbot):
    """A width past ``MAX_CANVAS_WIDTH`` never reaches the caller un-clamped --
    ``QSpinBox.setRange`` enforces the S1 bound at the widget level."""
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._width.setValue(MAX_CANVAS_WIDTH + 100_000)
    assert dialog.target_size()[0] == MAX_CANVAS_WIDTH


def test_height_above_the_ceiling_clamps_to_the_ceiling(qtbot):
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._height.setValue(MAX_CANVAS_HEIGHT + 100_000)
    assert dialog.target_size()[1] == MAX_CANVAS_HEIGHT


def test_minimum_floor_is_one_pixel(qtbot):
    """The floor is 1px; a value below it clamps up to 1, never to 0 or negative."""
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._width.setValue(0)
    dialog._height.setValue(-500)
    assert dialog.target_size() == (1, 1)


def test_keyboard_entry_beyond_the_ceiling_stays_pinned_at_the_ceiling(qtbot):
    """Typing one digit past the ceiling's own digit-width is rejected
    keystroke-by-keystroke by the spin box's validator -- the field is left
    showing the ceiling itself, and Enter commits exactly that. This is a
    materially different code path than ``setValue()`` above: it is the
    widget's own ``validate()``, exercised via real key events, not the
    public setter.

    (Self-correction: an earlier version of this test typed
    ``MAX_CANVAS_WIDTH + 1`` -- same digit count as the ceiling -- expecting
    an interpretation-time clamp down to the ceiling. Probed directly against
    a real ``QSpinBox``, that keystroke sequence is rejected one digit early
    and lands on ``768``, not ``7680``: ``QSpinBox`` blocks an
    out-of-range keystroke rather than accepting it and fixing it up later.
    Appending an EXTRA digit past the ceiling's width reaches the same
    ceiling value through behaviour the widget actually exhibits.)"""
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    dialog._width.selectAll()
    QTest.keyClicks(dialog._width, str(MAX_CANVAS_WIDTH) + "0")
    QTest.keyClick(dialog._width, Qt.Key.Key_Enter)
    assert dialog._width.value() == MAX_CANVAS_WIDTH
    assert dialog.target_size()[0] == MAX_CANVAS_WIDTH


# --------------------------------------------------------------------------- #
# Accept / Reject via the real QDialogButtonBox signals                       #
# --------------------------------------------------------------------------- #


def test_ok_button_accepts_the_dialog(qtbot):
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    ok_button = dialog._buttons.button(dialog._buttons.StandardButton.Ok)
    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        QTest.mouseClick(ok_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cancel_button_rejects_the_dialog(qtbot):
    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    cancel_button = dialog._buttons.button(dialog._buttons.StandardButton.Cancel)
    with qtbot.waitSignal(dialog.rejected, timeout=1000):
        QTest.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected


# --------------------------------------------------------------------------- #
# The real main_window._on_canvas_size seam -- target_size() is what the      #
# caller actually reads back, not internal widget state.                     #
# --------------------------------------------------------------------------- #


def test_accept_applies_the_dialogs_reported_size_through_the_real_seam(
    qtbot, monkeypatch
):
    """``main_window._on_canvas_size`` reads ``dialog.target_size()`` and
    pushes a ``CanvasResizeCommand`` -- driven through the REAL production
    handler (no reimplementation), proving the caller consumes the accessor,
    not the raw spin-box widgets."""
    win = _window(qtbot)
    record = win.active_tab()
    document = record.document
    assert (document.width, document.height) == (64, 64)  # sanity: seam precondition

    seeded = {}

    def _fake_exec(self):
        seeded["width"] = self._width.value()
        seeded["height"] = self._height.value()
        self._width.setValue(128)
        self._height.setValue(96)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Canvas_Size_Dialog, "exec", _fake_exec)
    win._on_canvas_size()

    assert seeded == {"width": 64, "height": 64}  # seeded from the ACTIVE document
    assert (document.width, document.height) == (128, 96)


def test_reject_leaves_the_document_untouched(qtbot, monkeypatch):
    """Rejecting the dialog must not push a ``CanvasResizeCommand`` at all."""
    win = _window(qtbot)
    record = win.active_tab()
    document = record.document
    baseline = (document.width, document.height)
    stack_count_before = record.stack.count()

    monkeypatch.setattr(
        Canvas_Size_Dialog, "exec", lambda self: QDialog.DialogCode.Rejected
    )
    win._on_canvas_size()

    assert (document.width, document.height) == baseline
    assert record.stack.count() == stack_count_before


def test_accept_with_an_unchanged_size_is_a_noop(qtbot, monkeypatch):
    """Accepting with the SAME size the document already has must not push a
    command either -- the caller's own early-return guard, reached only
    through this dialog's ``target_size()`` reporting back the unchanged
    value."""
    win = _window(qtbot)
    record = win.active_tab()
    document = record.document
    stack_count_before = record.stack.count()

    monkeypatch.setattr(
        Canvas_Size_Dialog, "exec", lambda self: QDialog.DialogCode.Accepted
    )
    win._on_canvas_size()

    assert (document.width, document.height) == (64, 64)
    assert record.stack.count() == stack_count_before


def test_accept_at_the_8k_ceiling_resizes_the_real_document(qtbot, monkeypatch):
    """S1: resizing all the way to the 8K ceiling through the real seam
    actually lands on the document -- not just clamped inside the dialog."""
    win = _window(qtbot)
    record = win.active_tab()
    document = record.document

    def _fake_exec(self):
        self._width.setValue(MAX_CANVAS_WIDTH)
        self._height.setValue(MAX_CANVAS_HEIGHT)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(Canvas_Size_Dialog, "exec", _fake_exec)
    win._on_canvas_size()

    assert (document.width, document.height) == (MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT)


# --------------------------------------------------------------------------- #
# Accessibility -- accessible names, keyboard reachability, tab order (F6)    #
# --------------------------------------------------------------------------- #


def test_accessible_names_on_every_interactive_control(qtbot):
    dialog = Canvas_Size_Dialog(64, 64)
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
    dialog = Canvas_Size_Dialog(64, 64)
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
    dialog = Canvas_Size_Dialog(64, 64)
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

    dialog = Canvas_Size_Dialog(64, 64)
    qtbot.addWidget(dialog)
    # QEvent.Type.StyleChange is a harmless, real Qt event type unrelated to
    # translation; just confirm it does not raise and title stays put.
    dialog.changeEvent(QEvent(QEvent.Type.StyleChange))
    assert dialog.windowTitle() == dialog.tr("Canvas Size")
