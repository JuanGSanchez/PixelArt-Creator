"""Shared-projects panel acceptance (REQ-P10-UI-009, Gherkin SC-UI-009-1).

Slice B: the user shares the current project, builds a ``(member_id, role)`` roster,
and sees the normalized members read back through the port's provider-agnostic
membership surface — naming NO provider (DATA-007). Covers roster editing (add /
remove / role), the ``MAX_SHARED_MEMBERS`` UI edge-cap with feedback, the duplicate /
empty-name / empty-roster guards, and the ``SharedProjectError`` surfacing path (the
adapter's defensive rejection shown as a warning, never a crash).

Every test runs under BOTH light and dark themes via the autouse ``theme`` fixture.
The session is the injectable, synchronous loopback seam the UI layer gave — no worker, so a
read-back assertion follows the call immediately with no ``qtbot.wait``.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.cloud import SharedProjectError
from pixelart_creator.logic.constants import MAX_SHARED_MEMBERS
from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.shared_projects_panel import Shared_Projects_Panel


@pytest.fixture
def panel(qtbot):
    """A bound ``Shared_Projects_Panel`` over a fresh loopback session."""
    session = Collaboration_Session()
    widget = Shared_Projects_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    return widget, session


def _add_member(widget, member_id: str, role: str = "editor") -> None:
    """Type a member id, pick a role, and press Add (drives the real handler)."""
    widget._member_edit.setText(member_id)
    index = widget._role_combo.findData(role)
    assert index >= 0, f"role {role!r} not offered by the combo"
    widget._role_combo.setCurrentIndex(index)
    widget._add_button.click()


def test_sc_ui_009_share_lists_members_through_membership_surface(panel):
    """SC-UI-009-1: sharing invites members and the roster is read back + shown."""
    widget, session = panel
    widget._project_edit.setText("team-sprite")
    _add_member(widget, "alice", "owner")
    _add_member(widget, "bob", "editor")
    widget._share_button.click()

    # The session became active on the shared project (no provider named anywhere).
    assert session.active_project_id() == "team-sprite"
    roster = session.members("team-sprite")
    assert {(m.member_id, m.role) for m in roster} == {
        ("alice", "owner"),
        ("bob", "editor"),
    }
    # The committed-members view reflects the normalized roster read back.
    view = widget._members_view
    shown = {
        (view.topLevelItem(i).text(0), view.topLevelItem(i).text(1))
        for i in range(view.topLevelItemCount())
    }
    assert ("alice", widget._role_text("owner")) in shown
    assert ("bob", widget._role_text("editor")) in shown


def test_draft_roster_add_and_role_recorded(panel):
    """A drafted member shows in the editable roster tree with its role."""
    widget, _session = panel
    _add_member(widget, "carol", "viewer")
    assert widget._draft == [("carol", "viewer")]
    tree = widget._roster_tree
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).text(0) == "carol"
    assert tree.topLevelItem(0).text(1) == widget._role_text("viewer")


def test_remove_selected_draft_member(panel):
    """Selecting a draft member and pressing Remove drops it from the roster."""
    widget, _session = panel
    _add_member(widget, "alice")
    _add_member(widget, "bob")
    widget._roster_tree.setCurrentItem(widget._roster_tree.topLevelItem(0))
    widget._remove_button.click()
    assert [m for m, _ in widget._draft] == ["bob"]


def test_share_button_disabled_until_roster_has_a_member(panel):
    """The Share button is disabled while the draft roster is empty (UI edge)."""
    widget, _session = panel
    assert not widget._share_button.isEnabled()
    _add_member(widget, "alice")
    assert widget._share_button.isEnabled()


def test_max_shared_members_edge_cap_refuses_with_warning(
    panel, monkeypatch, mute_message_boxes
):
    """SC-UI-009-1 edge: adding past ``MAX_SHARED_MEMBERS`` is refused with feedback."""
    widget, _session = panel
    # Shrink the cap so the edge is cheap to hit (a single named constant, no literal
    # duplicated in the panel — the panel reads MAX_SHARED_MEMBERS live).
    monkeypatch.setattr(
        "pixelart_creator.ui.shared_projects_panel.MAX_SHARED_MEMBERS", 2
    )
    _add_member(widget, "alice")
    _add_member(widget, "bob")
    _add_member(widget, "carol")  # over the (patched) cap
    assert [m for m, _ in widget._draft] == ["alice", "bob"]
    warnings = [c for c in mute_message_boxes if c[0] == "warning"]
    assert warnings, "adding past the member cap must warn the user"


def test_real_constant_is_a_positive_bound():
    """The member cap is a real positive named constant (Article II sanity)."""
    assert isinstance(MAX_SHARED_MEMBERS, int) and MAX_SHARED_MEMBERS > 0


def test_duplicate_member_is_refused_with_feedback(panel, mute_message_boxes):
    """Adding a member id already in the roster informs the user and is a no-op."""
    widget, _session = panel
    _add_member(widget, "alice")
    _add_member(widget, "alice")
    assert [m for m, _ in widget._draft] == ["alice"]
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_share_without_name_is_guarded(panel, mute_message_boxes):
    """Sharing with no project name informs the user and does not activate."""
    widget, session = panel
    _add_member(widget, "alice")
    widget._project_edit.setText("   ")  # whitespace only
    widget._share_button.click()
    assert session.active_project_id() is None
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_share_error_is_surfaced_not_crashed(panel, monkeypatch, mute_message_boxes):
    """A ``SharedProjectError`` from the adapter surfaces as a warning, not a crash."""
    widget, session = panel

    def _boom(*_a, **_k):
        raise SharedProjectError("adapter rejected the roster")

    monkeypatch.setattr(session, "share", _boom)
    widget._project_edit.setText("team-sprite")
    _add_member(widget, "alice")
    widget._share_button.click()  # must not raise
    assert any(c[0] == "warning" for c in mute_message_boxes)


def test_reshare_replaces_roster(panel):
    """Re-sharing an active project updates the committed roster (no incremental add)."""
    widget, session = panel
    widget._project_edit.setText("team-sprite")
    _add_member(widget, "alice", "owner")
    widget._share_button.click()
    # Rebuild the draft with a different roster and re-share.
    widget._draft.clear()
    _add_member(widget, "bob", "editor")
    widget._share_button.click()
    roster = session.members("team-sprite")
    assert [m.member_id for m in roster] == ["bob"]
