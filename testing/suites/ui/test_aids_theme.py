"""Visual-aids theming acceptance tests (REQ-P9-UI-013).

Scenario SC-UI-013-1: the overlays / preview / reference board / views / timelapse
controls render in both themes with role-based colours (never hard-coded per
widget). Every test in the suite already runs under both themes via the autouse
``theme`` fixture; this module adds explicit theme-parity assertions on the aid
overlay colours.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import canvas_roles


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_013_1_overlay_colours_come_from_theme_role(qtbot):
    """SC-UI-013-1: the iso overlay colour is the window theme's grid role colour."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.iso_overlay is not None
    # The tab aids were themed at creation via the window's active theme role
    # colour (not hard-coded per widget) — assert against the window's own theme.
    _checker_light, _checker_dark, grid = canvas_roles(win._theme)
    assert record.iso_overlay._line == QColor(grid)


def test_sc_ui_013_1_theme_roles_distinct_light_vs_dark():
    """SC-UI-013-1: light and dark define distinct role colours (legibility)."""
    assert canvas_roles("light") != canvas_roles("dark")


def test_sc_ui_013_1_reapplying_theme_repushes_overlay_colours(qtbot):
    """SC-UI-013-1: switching theme re-pushes role colours to the tab overlays."""
    win = _window(qtbot)
    record = win.active_tab()
    # Force the other theme's roles onto the tab and confirm the overlay tracks it.
    for name in ("light", "dark"):
        win._theme = name
        win._apply_aid_theme(record)
        _cl, _cd, grid = canvas_roles(name)
        assert record.iso_overlay._line == QColor(grid)
        assert record.perspective_overlay._line == QColor(grid)
