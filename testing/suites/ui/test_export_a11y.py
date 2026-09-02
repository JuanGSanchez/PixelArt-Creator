"""Export UI accessibility + both-theme acceptance (REQ-P7-UI-011, -012).

SC-UI-011-1 — every interactive export control exposes a non-empty accessible name,
is keyboard-reachable, and the app themes a visible focus indicator; the Export menu
action is keyboard-operable (Ctrl+Shift+E). SC-UI-012-1 — the export dialog + batch
panel render under a role-based stylesheet in BOTH themes. Every test also runs
twice via the autouse ``theme`` fixture, so the assertions below hold in light and
dark. Findings feed the ``a11y-audit`` report; the UI layer owns any fix.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.batch_export_panel import Batch_Export_Panel
from pixelart_creator.ui.export_dialog import Export_Dialog
from pixelart_creator.ui.main_window import Main_Window
from testing.suites.ui._export_helpers import animation_document


def _dialog(qtbot):
    dialog = Export_Dialog(animation_document(frames=3, tag=True))
    qtbot.addWidget(dialog)
    return dialog


def test_sc_ui_011_dialog_controls_expose_accessible_names(qtbot):
    """SC-UI-011-1: every interactive dialog control has a non-empty accessible name."""
    dialog = _dialog(qtbot)
    controls = [
        dialog._format_combo,
        dialog._preset_combo,
        dialog._path_edit,
        dialog._browse_button,
        dialog._gif_source_combo,
        dialog._gif_loop_spin,
        dialog._columns_spin,
        dialog._sheet_padding_spin,
        dialog._sheet_json_check,
        dialog._atlas_padding_spin,
        dialog._atlas_maxdim_spin,
        dialog._atlas_json_check,
    ]
    for control in controls:
        assert control.accessibleName() != "", control


def test_sc_ui_011_dialog_controls_are_keyboard_focusable(qtbot):
    """SC-UI-011-1: interactive controls accept keyboard focus (tab-reachable)."""
    dialog = _dialog(qtbot)
    for control in (
        dialog._format_combo,
        dialog._preset_combo,
        dialog._path_edit,
        dialog._browse_button,
        dialog._columns_spin,
    ):
        assert control.focusPolicy() != Qt.FocusPolicy.NoFocus, control
    # A visible focus indicator is themed once by role (a :focus QSS rule).
    assert ":focus" in QApplication.instance().styleSheet()


def test_sc_ui_011_batch_panel_controls_expose_accessible_names(qtbot):
    """SC-UI-011-1: the batch dock's list, progress + buttons expose accessible names."""
    panel = Batch_Export_Panel()
    qtbot.addWidget(panel)
    assert panel.accessibleName() != ""
    for control in (
        panel._list,
        panel._progress,
        panel._add_button,
        panel._remove_button,
        panel._export_button,
        panel._cancel_button,
    ):
        assert control.accessibleName() != "", control


def test_sc_ui_011_export_menu_action_is_keyboard_operable(qtbot):
    """SC-UI-011-1: the Export action carries a label + the Ctrl+Shift+E shortcut."""
    win = Main_Window()
    qtbot.addWidget(win)
    action = win._export_action
    assert action.text() != ""
    assert not action.shortcut().isEmpty()
    assert action.shortcut() == QKeySequence(
        Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_E
    )


def test_sc_ui_012_export_ui_renders_role_based_in_both_themes(qtbot, theme):
    """SC-UI-012-1: under each theme the app applies a non-empty role-based QSS and
    the export widgets build cleanly (no per-widget hard-coded colour)."""
    dialog = _dialog(qtbot)
    panel = Batch_Export_Panel()
    qtbot.addWidget(panel)
    # The active theme applied a non-empty, role-based stylesheet (same one both
    # widgets inherit — no widget sets its own colour).
    assert QApplication.instance().styleSheet() != ""
    assert dialog.styleSheet() == ""  # inherits app QSS, no per-widget override
    assert panel.styleSheet() == ""
