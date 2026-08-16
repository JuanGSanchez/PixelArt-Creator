"""Automation UI accessibility + both themes — SC-UI-012-1, SC-UI-013-1.

SC-UI-012-1 (REQ-P8-UI-012, R-25 annotation, AGT-06 audit) — every interactive
automation control (macro record/run/list, script runner, plugin manager list +
install/enable/disable + permission display, batch-recolour editors + list,
procgen parameter/seed fields) exposes a non-empty accessible name, is
keyboard-reachable, and the app themes a visible focus indicator. SC-UI-013-1 —
the panels render under a role-based stylesheet in BOTH themes (no per-widget
hard-coded colour). Every test also runs twice via the autouse ``theme``
fixture. Findings feed the ``a11y-audit`` report; AGT-05 fixes.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.main_window import Main_Window


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_012_macro_controls_expose_accessible_names(qtbot):
    """SC-UI-012-1: every interactive macro control has a non-empty accessible name."""
    c = _window(qtbot)._macro_controls
    assert c.accessibleName() != ""
    for control in (
        c._record_button,
        c._status,
        c._list,
        c._replay_button,
        c._save_button,
        c._load_button,
        c._remove_button,
    ):
        assert control.accessibleName() != "", control


def test_sc_ui_012_script_runner_exposes_accessible_names(qtbot):
    """SC-UI-012-1: the script editor + run control expose accessible names."""
    p = _window(qtbot)._script_runner_panel
    assert p.accessibleName() != ""
    for control in (p._editor, p._run_button):
        assert control.accessibleName() != "", control


def test_sc_ui_012_plugin_manager_exposes_accessible_names(qtbot):
    """SC-UI-012-1: the plugin list, permission display + buttons expose names."""
    p = _window(qtbot)._plugin_manager_panel
    assert p.accessibleName() != ""
    for control in (
        p._list,
        p._permissions,
        p._refresh_button,
        p._install_button,
        p._enable_button,
        p._disable_button,
    ):
        assert control.accessibleName() != "", control


def test_sc_ui_012_batch_recolour_exposes_accessible_names(qtbot):
    """SC-UI-012-1: the batch-recolour editors, list + apply expose accessible names."""
    p = _window(qtbot)._batch_recolour_panel
    assert p.accessibleName() != ""
    for control in (
        p._mode_combo,
        p._frame_spin,
        p._src_index,
        p._dst_index,
        p._src_colour_button,
        p._dst_colour_button,
        p._list,
        p._add_button,
        p._remove_button,
        p._apply_button,
    ):
        assert control.accessibleName() != "", control


def test_sc_ui_012_procgen_exposes_accessible_names_and_units(qtbot):
    """SC-UI-012-1: the procgen algorithm/seed/region fields expose names (+ px units)."""
    p = _window(qtbot)._procgen_panel
    assert p.accessibleName() != ""
    for control in (
        p._algorithm_combo,
        p._seed_spin,
        p._width_spin,
        p._height_spin,
        p._frequency_spin,
        p._octaves_spin,
        p._generate_button,
    ):
        assert control.accessibleName() != "", control
    assert p._width_spin.suffix().strip() == "px"  # translatable unit


def test_sc_ui_012_controls_are_keyboard_focusable(qtbot):
    """SC-UI-012-1: representative controls accept keyboard focus; focus is themed."""
    win = _window(qtbot)
    for control in (
        win._macro_controls._record_button,
        win._macro_controls._list,
        win._script_runner_panel._editor,
        win._plugin_manager_panel._enable_button,
        win._procgen_panel._seed_spin,
        win._batch_recolour_panel._apply_button,
    ):
        assert control.focusPolicy() != Qt.FocusPolicy.NoFocus, control
    assert ":focus" in QApplication.instance().styleSheet()


def test_sc_ui_012_automation_menu_is_populated(qtbot):
    """SC-UI-012-1: the &Automation menu surfaces every automation dock (discoverable)."""
    win = _window(qtbot)
    assert win._automation_menu.title() != ""
    assert len(win._automation_menu.actions()) >= 5


def test_sc_ui_013_panels_render_role_based_in_both_themes(qtbot, theme):
    """SC-UI-013-1: under each theme a non-empty role-based QSS applies; no per-widget colour."""
    win = _window(qtbot)
    assert QApplication.instance().styleSheet() != ""
    for panel in (
        win._macro_controls,
        win._script_runner_panel,
        win._plugin_manager_panel,
        win._batch_recolour_panel,
        win._procgen_panel,
    ):
        assert panel.styleSheet() == ""  # inherits the app QSS, no hard-coded override
