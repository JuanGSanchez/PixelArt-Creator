"""Accessibility + theming acceptance tests (REQ-P1-UI-024, -025).

Scenarios SC-UI-024-1 (accessible names), SC-UI-024-2 (keyboard reachable +
visible focus), SC-UI-024-3 (tool shortcuts — A11Y-1 fix), SC-UI-025-1 (both
themes correct, role-based colours), SC-UI-025-2 (text-on-accent contrast ≥
4.5:1 in both themes — A11Y-2 fix). Every test also runs under both themes via
the autouse fixture; this module adds the explicit theme-parity assertions.
Findings feed the a11y-audit report.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui import theme as theme_module
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    build_qss,
    canvas_roles,
)

#: Home-row single-key tool shortcuts (REQ-IS-UI-001/-028; input-scheme remap).
#: All eleven shipped tool_ids, matching main_window._build_actions()'s own
#: tool_shortcuts mapping exactly -- not a subset -- so a future tool added
#: to _tools without a shortcut entry fails HERE (missing key -> KeyError in
#: the completeness test below) rather than silently shipping unreachable.
_EXPECTED_TOOL_SHORTCUTS = {
    "pencil": "A",
    "picker": "Shift+A",
    "eraser": "Q",
    "rectangle": "S",
    "line": "W",
    "ellipse": "Shift+W",
    "select_rect": "D",
    "fill": "F",
    "dither": "Shift+F",
    "select_lasso": "E",
    "select_wand": "Shift+E",
}

#: WCAG 2.1 AA minimum contrast ratio for normal-size text.
_WCAG_AA_NORMAL = 4.5


def _relative_luminance(hex_color: str) -> float:
    """Return WCAG 2.1 relative luminance of an ``#rrggbb`` colour."""
    h = hex_color.lstrip("#")[:6]
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))

    def _chan(value: int) -> float:
        cs = value / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4

    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return the WCAG contrast ratio between two ``#rrggbb`` colours."""
    l1, l2 = _relative_luminance(fg_hex), _relative_luminance(bg_hex)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_sc_ui_024_1_interactive_widgets_expose_accessible_names(qtbot):
    """SC-UI-024-1: interactive widgets expose non-empty accessible names."""
    win = _window(qtbot)
    record = win.active_tab()
    assert record.view.accessibleName() != ""  # canvas view
    assert win._palette_panel.accessibleName() != ""  # palette panel
    assert win._tab_widget.accessibleName() != ""  # document tabs
    # Every tool action carries a label (its accessible name for AT).
    for action in win._tool_actions.values():
        assert action.text() != ""
    assert win._undo_action.text() != ""
    assert win._redo_action.text() != ""


def test_sc_ui_024_2_keyboard_reachable_with_visible_focus(qtbot):
    """SC-UI-024-2: controls are keyboard-reachable and focus is visible."""
    win = _window(qtbot)
    record = win.active_tab()
    # Canvas view accepts keyboard focus (tab-reachable, StrongFocus).
    assert record.view.focusPolicy() == Qt.FocusPolicy.StrongFocus
    # Core actions are keyboard-operable via shortcuts.
    assert not win._undo_action.shortcut().isEmpty()
    assert not win._redo_action.shortcut().isEmpty()
    assert not win._new_action.shortcut().isEmpty()
    assert not win._save_action.shortcut().isEmpty()
    # A visible focus indicator is themed once by role (a :focus QSS rule).
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


@pytest.mark.parametrize("tool_id,key", sorted(_EXPECTED_TOOL_SHORTCUTS.items()))
def test_sc_ui_024_3_tool_actions_expose_shortcuts(qtbot, tool_id, key):
    """SC-UI-024-3 (A11Y-1): each tool action carries its expected QKeySequence.

    Re-verifies the home-row remap (REQ-IS-UI-001/-028): Pencil=A, Picker=Shift+A,
    Eraser=Q, Rectangle=S, Line=W, Ellipse=Shift+W, Select-Rect=D, Fill=F,
    Dither=Shift+F, Lasso=E, Magic-Wand=Shift+E. Runs under both themes via the
    autouse ``theme`` fixture (shortcut binding is theme-invariant).
    """
    win = _window(qtbot)
    action = win._tool_actions[tool_id]
    assert not action.shortcut().isEmpty()
    assert action.shortcut() == QKeySequence(key)
    # The assigned key is surfaced in the tooltip so it is discoverable.
    assert key in action.toolTip()


def test_sc_ui_024_3_every_shipped_tool_is_tracked_and_bound(qtbot):
    """SC-UI-024-3 (A11Y-1, strengthened): no shipped tool is silently unreachable.

    The parametrized test above only proves each tracked tool_id's shortcut is
    CORRECT; it says nothing about a tool that is missing from
    ``_EXPECTED_TOOL_SHORTCUTS`` entirely. A tool present in the running app
    but absent from that dict would never be parametrized, so a future
    binding loss could ship invisibly to sighted testing -- exactly the
    accessibility gap SC-UI-024-3 exists to close. This test instead walks
    the window's OWN ``_tool_actions`` registry (the source of truth) and
    fails on either direction of drift: a live tool this module does not
    track, or a tracked entry that no longer names a live tool -- plus a
    direct non-empty-shortcut check on every live action, so a tool that
    exposes NO shortcut at all fails here even before the per-key assertion
    above would catch a WRONG one.
    """
    win = _window(qtbot)
    live_tool_ids = set(win._tool_actions.keys())
    assert live_tool_ids == set(_EXPECTED_TOOL_SHORTCUTS.keys()), (
        f"tool registry drift: live={live_tool_ids!r} "
        f"tracked={set(_EXPECTED_TOOL_SHORTCUTS.keys())!r}"
    )
    for tool_id, action in win._tool_actions.items():
        assert (
            not action.shortcut().isEmpty()
        ), f"tool {tool_id!r} exposes no keyboard shortcut at all"


@pytest.mark.parametrize("theme_name", [THEME_LIGHT, THEME_DARK])
def test_sc_ui_025_2_text_on_accent_contrast_meets_aa(theme_name):
    """SC-UI-025-2 (A11Y-2): text-on-accent contrast ≥ 4.5:1 in BOTH themes.

    Computed from the theme's own role colours (accent vs accent_text), so the
    assertion tracks the QSS the widgets actually render. Re-verifies the AGT-05
    accent recolour (light 5.28:1, dark 4.92:1)."""
    roles = theme_module._ROLES[theme_name]
    ratio = _contrast_ratio(roles["accent"], roles["accent_text"])
    assert ratio >= _WCAG_AA_NORMAL, (
        f"{theme_name}: accent {roles['accent']} on {roles['accent_text']} "
        f"= {ratio:.2f}:1 (< {_WCAG_AA_NORMAL}:1)"
    )


def test_sc_ui_025_1_both_themes_role_based_and_distinct(qtbot, theme):
    """SC-UI-025-1: both themes render via role colours and differ legibly."""
    win = _window(qtbot)
    # The active theme applied a non-empty role-based stylesheet.
    assert QApplication.instance().styleSheet() != ""
    # Light and dark are distinct and both define the same roles (no per-widget
    # hard-coded colour): the QSS templates differ but share role structure.
    light_qss = build_qss(THEME_LIGHT)
    dark_qss = build_qss(THEME_DARK)
    assert light_qss != dark_qss
    assert "background-color" in light_qss and "background-color" in dark_qss
    # The canvas checker/grid role colours also differ between themes.
    assert canvas_roles(THEME_LIGHT) != canvas_roles(THEME_DARK)
