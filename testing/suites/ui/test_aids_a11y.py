"""Visual-aids accessibility acceptance tests (REQ-P9-UI-012).

Scenario SC-UI-012-1: every interactive visual-aids control exposes a non-empty
accessible name (and description where non-obvious), and is keyboard-reachable
with a visible focus indicator. Feeds the a11y-audit report. Both themes via the
autouse fixture.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.guides import GuideOrientation
from pixelart_creator.ui.guides_rulers_overlay import Ruler_Strip
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.real_size_preview_window import Real_Size_Preview_Window
from pixelart_creator.ui.reference_board import Reference_Board
from pixelart_creator.ui.timelapse_controls import Timelapse_Controls


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_012_1_aid_menu_actions_have_labels(qtbot):
    """SC-UI-012-1: every Aids-menu action carries a non-empty accessible label."""
    win = _window(qtbot)
    for action in (
        win._guides_action,
        win._iso_action,
        win._perspective_action,
        win._new_view_action,
        win._reference_board_action,
    ):
        assert action.text() != ""
    assert win._aids_menu.title() != ""


def test_sc_ui_012_1_preview_window_accessible_names(qtbot, make_scene):
    """SC-UI-012-1: the preview window + its view expose accessible names."""
    win = Real_Size_Preview_Window(make_scene(16, 16))
    qtbot.addWidget(win)
    assert win.accessibleName() != ""
    assert win._view.accessibleName() != ""
    assert win._calibrate_button.text() != ""


def test_sc_ui_012_1_reference_board_accessible_names(qtbot):
    """SC-UI-012-1: the reference board controls expose accessible names."""
    board = Reference_Board()
    qtbot.addWidget(board)
    assert board.accessibleName() != ""
    assert board._view.accessibleName() != ""
    assert board._add_button.text() != ""


def test_sc_ui_012_1_timelapse_controls_accessible_names(qtbot):
    """SC-UI-012-1: the timelapse controls expose an accessible name + labels."""
    controls = Timelapse_Controls()
    qtbot.addWidget(controls)
    assert controls.accessibleName() != ""
    assert controls._record_button.text() != ""
    assert controls._save_button.text() != ""
    assert controls._load_button.text() != ""


def test_sc_ui_012_1_rulers_expose_names_and_descriptions(qtbot, make_view):
    """SC-UI-012-1: ruler strips expose an accessible name AND a description."""
    view, _scene, _stack = make_view(16, 16)
    for orientation in (GuideOrientation.HORIZONTAL, GuideOrientation.VERTICAL):
        ruler = Ruler_Strip(orientation, view)
        qtbot.addWidget(ruler)
        assert ruler.accessibleName() != ""
        assert ruler.accessibleDescription() != ""


def test_sc_ui_012_1_focus_indicator_defined_by_role(qtbot):
    """SC-UI-012-1: a visible focus indicator is themed once by role (:focus QSS)."""
    _win = _window(qtbot)
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss
