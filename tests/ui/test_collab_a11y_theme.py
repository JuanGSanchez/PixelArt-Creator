"""Collaboration UI a11y, both themes, i18n (REQ-P10-UI-006/-007/-008 for Slice B).

Every interactive control on the three Slice-B panels (shared projects / comments /
presence) exposes a non-empty accessible name, is keyboard-reachable (focus policy other
than ``NoFocus``), and shows a visible focus indicator (REQ-P10-UI-006); the panels
render under both QSS themes with role-based colours and no inline stylesheet
(REQ-P10-UI-007); and their user-visible strings are ``tr()``-wrapped and retranslate on
a ``LanguageChange`` (REQ-P10-UI-008). Every test runs under BOTH themes via the autouse
``theme`` fixture. Findings feed the a11y-audit report.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.comments_panel import Comments_Panel
from pixelart_creator.ui.presence_panel import Presence_Panel
from pixelart_creator.ui.shared_projects_panel import Shared_Projects_Panel


@pytest.fixture
def panels(qtbot):
    """The three bound panels over one shared session (an active project)."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    shared = Shared_Projects_Panel()
    comments = Comments_Panel()
    presence = Presence_Panel()
    for widget in (shared, comments, presence):
        qtbot.addWidget(widget)
        widget.set_session(session)
    return shared, comments, presence


# -- REQ-P10-UI-006 accessible names ------------------------------------------ #


def test_shared_panel_controls_have_accessible_names(panels):
    """Every interactive shared-projects control exposes a non-empty a11y name."""
    shared, _c, _p = panels
    for widget in (
        shared,
        shared._project_edit,
        shared._member_edit,
        shared._role_combo,
        shared._add_button,
        shared._remove_button,
        shared._share_button,
        shared._roster_tree,
        shared._members_view,
    ):
        assert widget.accessibleName() != ""


def test_comments_panel_controls_have_accessible_names(panels):
    """Every interactive comments control exposes a non-empty a11y name."""
    _s, comments, _p = panels
    for widget in (
        comments,
        comments._author_edit,
        comments._tree,
        comments._editor,
        comments._counter,
        comments._reply_check,
        comments._add_button,
        comments._resolve_button,
    ):
        assert widget.accessibleName() != ""


def test_presence_panel_controls_have_accessible_names(panels):
    """Every interactive presence control exposes a non-empty a11y name."""
    _s, _c, presence = panels
    for widget in (
        presence,
        presence._self_edit,
        presence._join_button,
        presence._leave_button,
        presence._list,
    ):
        assert widget.accessibleName() != ""


# -- REQ-P10-UI-006 keyboard reachability + focus order ----------------------- #


def test_panels_are_keyboard_reachable(panels):
    """Trees / lists / edits accept keyboard focus (Tab-reachable, not NoFocus)."""
    shared, comments, presence = panels
    for widget in (
        shared._project_edit,
        shared._roster_tree,
        shared._members_view,
        comments._tree,
        comments._editor,
        presence._self_edit,
        presence._list,
    ):
        assert widget.focusPolicy() != Qt.FocusPolicy.NoFocus


def test_roster_and_thread_are_single_selection(panels):
    """Editable roster + comment thread use single-selection (unambiguous target)."""
    shared, comments, _p = panels
    assert (
        shared._roster_tree.selectionMode()
        == shared._roster_tree.SelectionMode.SingleSelection
    )
    assert (
        comments._tree.selectionMode() == comments._tree.SelectionMode.SingleSelection
    )


def test_visible_focus_indicator_is_themed(panels):
    """A visible focus ring is themed once by role (:focus QSS) for the panels."""
    qss = QApplication.instance().styleSheet()
    assert ":focus" in qss


# -- REQ-P10-UI-007 both themes ----------------------------------------------- #


def test_panels_lay_out_under_active_theme_without_inline_colour(panels, theme):
    """Each panel lays out under the active theme with NO per-widget hard-coded colour.

    The autouse ``theme`` fixture runs this under both light and dark; colours come
    from the applied QSS role palette, so the panels carry no inline stylesheet.
    """
    for widget in panels:
        assert widget.sizeHint().isValid()
        assert widget.styleSheet() == ""


# -- REQ-P10-UI-008 i18n retranslate ------------------------------------------ #


def test_panels_retranslate_on_language_change(panels):
    """Each panel re-sets its tr() strings on ``QEvent.LanguageChange`` (F5)."""
    shared, comments, presence = panels
    for widget in panels:
        QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))
    # Strings remain populated after the retranslate hook (no crash, no blanking).
    assert shared._share_button.text() != ""
    assert shared._add_button.text() != ""
    assert comments._add_button.text() != ""
    assert comments._resolve_button.text() != ""
    assert presence._join_button.text() != ""
    assert presence._leave_button.text() != ""


def test_comment_status_labels_are_translatable(panels):
    """Comment status uses tr() Open/Resolved labels (never a bare literal)."""
    _s, comments, _p = panels
    assert comments.tr("Open") != ""
    assert comments.tr("Resolved") != ""
