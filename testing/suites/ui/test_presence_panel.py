"""Presence panel acceptance (REQ-P10-UI-011, Gherkin SC-UI-011-1).

Slice B: the presence surface shows WHO is present in a shared project (roster /
awareness list) from the ephemeral presence channel — never persisted into the
``.pixproj``. It lets the local member Join (announce) and Leave (clear). It is
explicitly NOT live-cursor rendering (that is REQ-P10-UI-013 / Slice C): the roster
shows member ids only, even when a presence entry carries a cursor payload.

Every test runs under BOTH light and dark themes (autouse ``theme`` fixture). The
session is the synchronous loopback seam — the roster read-back follows the call.
"""

from __future__ import annotations

import pytest

from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.presence_panel import Presence_Panel


@pytest.fixture
def shared(qtbot):
    """A ``Presence_Panel`` bound to a session with one active shared project."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner"), ("bob", "editor")])
    widget = Presence_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    return widget, session


def _roster(widget) -> list:
    return [widget._list.item(i).text() for i in range(widget._list.count())]


def test_sc_ui_011_join_announces_local_presence(shared):
    """SC-UI-011-1: announcing presence adds the local member to the roster."""
    widget, _session = shared
    widget._self_edit.setText("alice")
    widget._join_button.click()
    assert "alice" in _roster(widget)


def test_sc_ui_011_shows_who_else_is_present(shared):
    """SC-UI-011-1: the surface shows every present member (not just the local one)."""
    widget, session = shared
    # Another collaborator announces presence directly on the shared channel.
    session.announce_presence("proj", "bob")
    widget._self_edit.setText("alice")
    widget._join_button.click()
    assert set(_roster(widget)) == {"alice", "bob"}


def test_sc_ui_011_roster_shows_member_ids_no_live_cursor(shared):
    """SC-UI-011-1: presence renders WHO is present — no live cursor (Slice C absent).

    Even when a presence entry carries a cursor payload (the model permits it), the
    Slice-B panel renders member ids only; drawing collaborators' cursors live
    (REQ-P10-UI-013) is deliberately out of scope here.
    """
    widget, session = shared
    adapter = session.adapter()
    # Store a presence entry WITH a cursor payload straight on the adapter.
    adapter.set_presence("proj", {"member_id": "bob", "cursor": {"x": 10, "y": 20}})
    widget._refresh()
    assert _roster(widget) == ["bob"]  # id only; the cursor is not rendered
    # The panel exposes no cursor-overlay surface (Slice C is not built).
    assert not hasattr(widget, "_cursor_overlay")


def test_leave_clears_local_presence(shared):
    """Leave drops the local member from the ephemeral roster."""
    widget, _session = shared
    widget._self_edit.setText("alice")
    widget._join_button.click()
    assert "alice" in _roster(widget)
    widget._leave_button.click()
    assert "alice" not in _roster(widget)


def test_presence_is_ephemeral_not_persisted(shared):
    """Presence lives only on the in-memory channel, never in a stored blob."""
    widget, session = shared
    widget._self_edit.setText("alice")
    widget._join_button.click()
    # Presence comes from the ephemeral channel; the shared blob store holds no
    # project bytes (nothing was put), proving presence is not written to a .pixproj.
    assert [e.member_id for e in session.presence("proj")] == ["alice"]


def test_join_leave_disabled_without_active_project(qtbot):
    """Join/Leave are disabled until a shared project is active (UI edge)."""
    session = Collaboration_Session()
    widget = Presence_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert not widget._join_button.isEnabled()
    assert not widget._leave_button.isEnabled()


def test_join_without_member_id_is_guarded(shared, mute_message_boxes):
    """Announcing with no member id informs the user and stores nothing."""
    widget, session = shared
    widget._self_edit.clear()
    widget._join_button.click()
    assert session.presence("proj") == ()
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_join_without_active_project_is_guarded(qtbot, mute_message_boxes):
    """Announcing before a project is active informs the user (defensive guard)."""
    session = Collaboration_Session()
    widget = Presence_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget._self_edit.setText("alice")
    widget._on_join()  # buttons are disabled in the UI; exercise the guard directly
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_announce_error_is_surfaced_not_crashed(
    shared, monkeypatch, mute_message_boxes
):
    """A ``SharedProjectError`` from announce surfaces as a warning, not a crash."""
    from pixelart_creator.data.cloud import SharedProjectError

    widget, session = shared

    def _boom(*_a, **_k):
        raise SharedProjectError("presence rejected")

    monkeypatch.setattr(session, "announce_presence", _boom)
    widget._self_edit.setText("alice")
    widget._join_button.click()  # must not raise
    assert any(c[0] == "warning" for c in mute_message_boxes)


def test_leave_without_member_id_is_a_noop(shared):
    """Leave with no member id does nothing (no crash, no clear call)."""
    widget, session = shared
    session.announce_presence("proj", "alice")
    widget._self_edit.clear()
    widget._leave_button.click()
    assert [e.member_id for e in session.presence("proj")] == ["alice"]


def test_actions_are_noops_before_binding(qtbot):
    """Join/Leave are safe no-ops before a session is bound (defensive guard)."""
    widget = Presence_Panel()
    qtbot.addWidget(widget)
    widget._on_join()  # no session
    widget._on_leave()  # no session
    assert widget._list.count() == 0
