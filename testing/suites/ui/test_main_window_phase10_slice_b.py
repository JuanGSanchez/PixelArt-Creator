"""Main_Window Slice-B collaboration wiring (REQ-P10-UI-009/-010/-011 integration).

The window builds one provider-agnostic ``Collaboration_Session`` and the three dock
panels (shared projects / comments / presence), binds each panel to that session, docks
them via the workflow-dock helper, and exposes their toggle actions under the Cloud
menu. The dock titles are translatable and retranslate on a language change. This is the
end-to-end integration seam the panels' unit tests build on. Runs under BOTH themes.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent

from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.comments_panel import Comments_Panel
from pixelart_creator.ui.main_window import Main_Window
from pixelart_creator.ui.presence_panel import Presence_Panel
from pixelart_creator.ui.shared_projects_panel import Shared_Projects_Panel


def _window(qtbot) -> Main_Window:
    win = Main_Window()
    qtbot.addWidget(win)
    return win


def test_window_builds_one_session_and_three_panels(qtbot):
    """The window owns a session + the three collaboration panels."""
    win = _window(qtbot)
    assert isinstance(win._collab_session, Collaboration_Session)
    assert isinstance(win._shared_projects_panel, Shared_Projects_Panel)
    assert isinstance(win._comments_panel, Comments_Panel)
    assert isinstance(win._presence_panel, Presence_Panel)


def test_all_three_panels_bound_to_the_same_session(qtbot):
    """Every panel drives the ONE window session (a shared collaboration seam)."""
    win = _window(qtbot)
    session = win._collab_session
    assert win._shared_projects_panel._session is session
    assert win._comments_panel._session is session
    assert win._presence_panel._session is session


def test_panels_are_docked(qtbot):
    """The three panels live in dock widgets holding exactly their panel."""
    win = _window(qtbot)
    assert win._shared_dock.widget() is win._shared_projects_panel
    assert win._comments_dock.widget() is win._comments_panel
    assert win._presence_dock.widget() is win._presence_panel


def test_cloud_menu_exposes_dock_toggles(qtbot):
    """Each dock's toggle view action is available under the Cloud menu."""
    win = _window(qtbot)
    menu_actions = set(win._cloud_menu.actions())
    for dock in (win._shared_dock, win._comments_dock, win._presence_dock):
        assert dock.toggleViewAction() in menu_actions


def test_dock_titles_are_populated_and_retranslate(qtbot):
    """Dock titles are non-empty tr() labels and survive a LanguageChange (F5)."""
    win = _window(qtbot)
    for dock in (win._shared_dock, win._comments_dock, win._presence_dock):
        assert dock.windowTitle() != ""
    win.changeEvent(QEvent(QEvent.Type.LanguageChange))
    # Titles remain populated after the retranslate hook (no blanking, no crash).
    assert win._shared_dock.windowTitle() != ""
    assert win._comments_dock.windowTitle() != ""
    assert win._presence_dock.windowTitle() != ""


def test_end_to_end_share_flows_through_the_window_session(qtbot):
    """Sharing via the window's panel updates the window session + the members view."""
    win = _window(qtbot)
    panel = win._shared_projects_panel
    panel._project_edit.setText("team-sprite")
    panel._member_edit.setText("alice")
    idx = panel._role_combo.findData("owner")
    panel._role_combo.setCurrentIndex(idx)
    panel._add_button.click()
    panel._share_button.click()
    assert win._collab_session.active_project_id() == "team-sprite"
    members = win._collab_session.members("team-sprite")
    assert [m.member_id for m in members] == ["alice"]
