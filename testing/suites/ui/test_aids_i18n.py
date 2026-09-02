"""Visual-aids i18n retranslate tests (REQ-P9-UI-014, behavioural).

Scenario SC-UI-014-1 is enforced at ship by the localisation owner's ``string_audit_check`` (no
bare literals). This module verifies the *behavioural* half this suite owns: the
hand-built aid widgets re-set their user-visible text on ``QEvent.LanguageChange``
without error and never expose an empty label. Both themes via the autouse fixture.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls


def _send_language_change(widget) -> None:
    QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))


def test_sc_ui_014_1_preview_retranslates_without_error(qtbot, make_scene):
    """SC-UI-014-1: the preview re-sets its title/labels on LanguageChange."""
    win = Real_Size_Preview_Window(make_scene(16, 16))
    qtbot.addWidget(win)
    _send_language_change(win)
    assert win.windowTitle() != ""
    assert win.accessibleName() != ""
    assert win._calibrate_button.text() != ""


def test_sc_ui_014_1_timelapse_retranslates_without_error(qtbot):
    """SC-UI-014-1: the timelapse controls re-set their labels on LanguageChange."""
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    _send_language_change(controls)
    assert controls._record_button.text() != ""
    assert controls._save_button.text() != ""
    assert controls._load_button.text() != ""


def test_sc_ui_014_1_reference_board_retranslates_without_error(qtbot):
    """SC-UI-014-1: the reference board re-sets its labels on LanguageChange."""
    board = Reference_Board()
    qtbot.addWidget(board)
    _send_language_change(board)
    assert board.windowTitle() != ""
    assert board._add_button.text() != ""
