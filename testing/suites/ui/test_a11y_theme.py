"""Accessibility + theming acceptance tests (REQ-P1-UI-024, -025).

Scenarios SC-UI-024-1 (accessible names), SC-UI-024-2 (keyboard reachable +
visible focus), SC-UI-024-3 (tool shortcuts — A11Y-1 fix), SC-UI-025-1 (both
themes correct, role-based colours), SC-UI-025-2 (text-on-accent contrast ≥
4.5:1 in both themes — A11Y-2 fix). Every test also runs under both themes via
the autouse fixture; this module adds the explicit theme-parity assertions.
Findings feed the a11y-audit report.

Visible focus (SC-UI-024-2) is proven by a RENDERED check -- focus-role pixels
present on the focused control, absent when unfocused (``focus_helpers``) -- not
by the substring ``":focus"`` in the stylesheet, which is withdrawn as evidence
(spec A-4, ADR-0069). The role-pair contrast uses ``logic.contrast`` (the one
implementation), over every style x mode the catalogue ships.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from pixelart_creator.logic.contrast import TEXT_MIN_RATIO, contrast_ratio
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.theme import (
    THEME_DARK,
    THEME_LIGHT,
    available_styles,
    available_themes,
    build_qss,
    canvas_roles,
    role_map,
)
from testing.suites.ui.focus_helpers import assert_focus_rendered

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

#: Every style x mode the catalogue ships (four today, six when the third style lands).
_COMBOS = [(style, mode) for style in available_styles() for mode in available_themes()]


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
    """SC-UI-024-2: controls are keyboard-reachable and focus is visible.

    Visible focus is a RENDERED check (spec A-4): the canvas view, once given
    keyboard focus, shows focus-role pixels around it and none when it is not
    focused. The stylesheet-substring proxy is withdrawn.
    """
    win = _window(qtbot)
    record = win.active_tab()
    # Canvas view accepts keyboard focus (tab-reachable, StrongFocus).
    assert record.view.focusPolicy() == Qt.FocusPolicy.StrongFocus
    # Core actions are keyboard-operable via shortcuts.
    assert not win._undo_action.shortcut().isEmpty()
    assert not win._redo_action.shortcut().isEmpty()
    assert not win._new_action.shortcut().isEmpty()
    assert not win._save_action.shortcut().isEmpty()
    # A visible focus indicator: rendered focus-role pixels on the focused canvas view.
    assert_focus_rendered(qtbot, record.view)


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


@pytest.mark.parametrize("style, mode", _COMBOS)
def test_sc_ui_025_2_text_on_accent_contrast_meets_aa(style, mode):
    """SC-UI-025-2 (A11Y-2): text-on-accent contrast >= 4.5:1 in EVERY style x mode.

    Computed from the combination's own role colours (accent vs accent_text) through
    ``logic.contrast`` -- the one contrast implementation -- so the assertion tracks
    the QSS the widgets actually render. Re-verifies the accent recolour."""
    roles = role_map(mode, style)
    ratio = contrast_ratio(roles["accent_text"], roles["accent"])
    assert ratio >= TEXT_MIN_RATIO, (
        f"{style}/{mode}: accent {roles['accent']} on {roles['accent_text']} "
        f"= {ratio:.2f}:1 (< {TEXT_MIN_RATIO}:1)"
    )


def test_sc_ui_025_1_both_themes_role_based_and_distinct(qtbot, theme):
    """SC-UI-025-1: every combination renders via role colours and the modes differ legibly."""
    _window(qtbot)
    # The active theme applied a non-empty role-based stylesheet.
    assert QApplication.instance().styleSheet() != ""
    for style in available_styles():
        # Light and dark are distinct in every style and both are role-based (no
        # per-widget hard-coded colour): the QSS differs but shares role structure.
        light_qss = build_qss(THEME_LIGHT, style)
        dark_qss = build_qss(THEME_DARK, style)
        assert light_qss != dark_qss
        assert "background-color" in light_qss and "background-color" in dark_qss
        # The canvas checker/grid role colours also differ between modes.
        assert canvas_roles(THEME_LIGHT, style) != canvas_roles(THEME_DARK, style)
    # ... and the styles differ from one another in the same mode.
    for mode in available_themes():
        sheets = {build_qss(mode, style) for style in available_styles()}
        assert len(sheets) == len(available_styles())
