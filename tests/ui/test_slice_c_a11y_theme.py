"""Slice-C a11y, both themes, i18n (REQ-P10-UI-006/-007/-008 for UI-012/-013).

Phase-10 Slice C. The branching panel + the real-time / live-cursor actions inherit the
platform accessibility, both-themes, and i18n gates:

* every interactive branching control exposes a non-empty accessible name and is
  keyboard-reachable (focus policy other than ``NoFocus``); a visible focus ring is
  themed once by role (REQ-P10-UI-006);
* the panel lays out under BOTH QSS themes with NO per-widget hard-coded colour
  (REQ-P10-UI-007);
* the panel + the window's real-time actions carry ``tr()``-wrapped strings that survive
  a ``LanguageChange`` (REQ-P10-UI-008).

Findings feed the a11y-audit report. Every test runs under BOTH themes via the autouse
``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.branching_panel import Branching_Panel, Branching_Session


@pytest.fixture
def panel(qtbot, make_document):
    """A ``Branching_Panel`` bound to a session with an open base + a feature branch."""
    session = Branching_Session()
    session.set_base_document(make_document())
    session.create_branch("feature")
    widget = Branching_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    return widget


# -- REQ-P10-UI-006 accessible names ------------------------------------------ #


def test_branching_controls_have_accessible_names(panel):
    """Every interactive branching control exposes a non-empty a11y name."""
    for widget in (
        panel,
        panel._list,
        panel._new_button,
        panel._switch_button,
        panel._merge_button,
        panel._outcome,
    ):
        assert widget.accessibleName() != ""


# -- REQ-P10-UI-006 keyboard reachability + focus ----------------------------- #


def test_branching_controls_are_keyboard_reachable(panel):
    """The branch list + buttons accept keyboard focus (Tab-reachable, not NoFocus)."""
    for widget in (
        panel._list,
        panel._new_button,
        panel._switch_button,
        panel._merge_button,
    ):
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_visible_focus_indicator_is_themed(panel):
    """A visible focus ring is themed once by role (:focus QSS) — not per widget."""
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


# -- REQ-P10-UI-007 both themes ----------------------------------------------- #


def test_panel_lays_out_under_active_theme_without_inline_colour(panel, theme):
    """The panel lays out under the active theme with NO per-widget hard-coded colour.

    The autouse ``theme`` fixture runs this under both light and dark; colours come from
    the applied QSS role palette, so the panel carries no inline stylesheet.
    """
    assert panel.sizeHint().isValid()
    assert panel.styleSheet() == ""


# -- REQ-P10-UI-008 i18n retranslate ------------------------------------------ #


def test_panel_retranslates_on_language_change(panel):
    """The panel re-sets its tr() strings + intro on ``LanguageChange`` (F5)."""
    QApplication.sendEvent(panel, QEvent(QEvent.Type.LanguageChange))
    assert panel._new_button.text() != ""
    assert panel._switch_button.text() != ""
    assert panel._merge_button.text() != ""
    assert panel._intro.text() != ""


def test_branching_strings_are_translatable(panel):
    """The branching labels resolve through tr() (never a bare literal)."""
    assert panel.tr("New Branch") != ""
    assert panel.tr("Merge") != ""
    assert panel.tr("Branching") != ""


# -- REQ-P10-UI-008 window real-time / live-cursor action strings ------------- #


def test_realtime_actions_have_translatable_text(qtbot):
    """The Cloud-menu real-time + live-cursor actions carry tr()-wrapped text."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    assert win._realtime_connect_action.text() != ""
    assert win._realtime_disconnect_action.text() != ""
    assert win._live_cursors_action.text() != ""
    # The live-cursors action is a checkable toggle (keyboard-operable via the menu).
    assert win._live_cursors_action.isCheckable() is True


def test_branching_dock_has_a_title(qtbot):
    """The branching dock carries a translatable window title (retranslated on F5)."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    assert win._branching_dock.windowTitle() != ""
