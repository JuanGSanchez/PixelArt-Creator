"""Collaboration session seam acceptance (REQ-P10-UI-009/-010/-011 wiring).

``Collaboration_Session`` is the provider-agnostic, synchronous loopback seam the three
Slice-B panels drive. These tests exercise it directly: the injectable adapter factory,
the four change signals (``sharedProjectChanged`` / ``membersChanged`` /
``commentsChanged`` / ``presenceChanged``) the panels refresh from, empty reads before a
share, and the ``SharedProjectError`` propagation the panels catch. Synchronous over the
loopback adapter — assertions follow the call with no ``qtbot.wait``.

Runs under BOTH themes via the autouse fixture (the seam is theme-invariant; the
parametrisation simply keeps the session lifecycle exercised in each theme context).
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.cloud import SharedProjectAdapter, SharedProjectError
from pixelart_creator.ui.collaboration_actions import Collaboration_Session


def test_injectable_factory_is_used(qtbot):
    """The session builds its adapter through the injected factory (test seam)."""
    built = []

    def _factory() -> SharedProjectAdapter:
        adapter = SharedProjectAdapter()
        built.append(adapter)
        return adapter

    session = Collaboration_Session(factory=_factory)
    assert session.adapter() is None  # lazily built on first use
    session.share("proj", [("alice", "owner")])
    assert built and session.adapter() is built[0]


def test_default_factory_is_loopback(qtbot):
    """With no factory the session defaults to an in-memory loopback adapter."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    assert isinstance(session.adapter(), SharedProjectAdapter)


def test_share_emits_shared_and_members_signals(qtbot):
    """Sharing a new project emits ``sharedProjectChanged`` + ``membersChanged``."""
    session = Collaboration_Session()
    with qtbot.waitSignals(
        [session.sharedProjectChanged, session.membersChanged],
        timeout=1000,
    ):
        session.share("proj", [("alice", "owner")])
    assert session.active_project_id() == "proj"


def test_reshare_same_project_emits_members_only(qtbot):
    """Re-sharing an already-active project emits ``membersChanged`` (roster update)."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    with qtbot.waitSignal(session.membersChanged, timeout=1000):
        session.share("proj", [("alice", "owner"), ("bob", "editor")])
    assert [m.member_id for m in session.members("proj")] == ["alice", "bob"]


def test_add_comment_emits_comments_changed(qtbot):
    """Adding a comment emits ``commentsChanged`` and returns the normalized comment."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    with qtbot.waitSignal(session.commentsChanged, timeout=1000):
        comment = session.add_comment("proj", "alice", "hi")
    assert comment.text == "hi" and comment.resolved is False


def test_resolve_comment_emits_comments_changed(qtbot):
    """Resolving a comment emits ``commentsChanged`` with the updated state."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    comment = session.add_comment("proj", "alice", "hi")
    with qtbot.waitSignal(session.commentsChanged, timeout=1000):
        updated = session.resolve_comment("proj", comment.comment_id)
    assert updated.resolved is True


def test_presence_announce_and_clear_emit_presence_changed(qtbot):
    """Announce + clear both emit ``presenceChanged``."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    with qtbot.waitSignal(session.presenceChanged, timeout=1000):
        session.announce_presence("proj", "alice")
    assert [e.member_id for e in session.presence("proj")] == ["alice"]
    with qtbot.waitSignal(session.presenceChanged, timeout=1000):
        session.clear_presence("proj", "alice")
    assert session.presence("proj") == ()


def test_empty_reads_before_any_share(qtbot):
    """Members / comments / presence read empty before the first share (no adapter)."""
    session = Collaboration_Session()
    assert session.members("proj") == ()
    assert session.comments("proj") == ()
    assert session.presence("proj") == ()
    assert not session.is_active()


def test_resolve_before_share_raises_shared_project_error(qtbot):
    """Resolving before any share raises the ``data/cloud`` error the panel catches."""
    session = Collaboration_Session()
    with pytest.raises(SharedProjectError):
        session.resolve_comment("proj", "c1")


def test_announce_before_share_raises_shared_project_error(qtbot):
    """Announcing presence before any share raises ``SharedProjectError``."""
    session = Collaboration_Session()
    with pytest.raises(SharedProjectError):
        session.announce_presence("proj", "alice")


def test_leave_emits_deactivating_signal(qtbot):
    """Leave clears the active id and emits ``sharedProjectChanged('')``."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    with qtbot.waitSignal(session.sharedProjectChanged, timeout=1000) as blocker:
        session.leave()
    assert blocker.args == [""]
    assert session.active_project_id() is None


def test_threaded_comment_ids_are_unique(qtbot):
    """Successive comments get distinct UI-side ids so replies can target a parent."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    first = session.add_comment("proj", "alice", "one")
    second = session.add_comment("proj", "alice", "two", parent_id=first.comment_id)
    assert first.comment_id != second.comment_id
    assert second.parent_id == first.comment_id
