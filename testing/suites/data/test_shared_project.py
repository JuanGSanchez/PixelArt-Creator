"""Tests for pixelart_creator.data.cloud.shared_adapter (Phase-10 Slice B, no Qt).

REQ-P10-DATA-009: shared-project storage + membership roster/roles + comments
(attach/list/thread/resolve) + ephemeral presence, all over the in-memory/loopback
path (a controlled ``CloudPort`` is injected; no real network). Validator failures
surface as ``SharedProjectError`` (a ``CloudError``); the bounds are the imported
constants (``MAX_SHARED_MEMBERS`` / ``MAX_COMMENTS_PER_PROJECT`` / ``MAX_COMMENT_BYTES``),
and presence never leaks into a stored ``.pixproj`` blob.
"""

from __future__ import annotations

import pytest

from pixelart_creator.data.cloud import (
    FakeCloudAdapter,
    PresenceEntry,
    ProjectComment,
    RemoteMember,
    SharedProjectAdapter,
    SharedProjectError,
)
from pixelart_creator.data.cloud.port import serialize_project
from pixelart_creator.logic.constants import (
    MAX_COMMENT_BYTES,
    MAX_COMMENTS_PER_PROJECT,
    MAX_SHARED_MEMBERS,
)
from pixelart_creator.logic.document import Document

PID = "shared-1"


class _SpyPort(FakeCloudAdapter):
    """A controlled CloudPort that records the blob passthrough calls."""

    def __init__(self):
        super().__init__()
        self.put_calls = []
        self.get_calls = []

    def put(self, project_id, blob, *, parent_version=None):
        self.put_calls.append((project_id, blob))
        return super().put(project_id, blob, parent_version=parent_version)

    def get(self, project_id, version_id):
        self.get_calls.append((project_id, version_id))
        return super().get(project_id, version_id)


def _membership(n=2, project_id=PID):
    return {
        "project_id": project_id,
        "members": [{"member_id": f"m{i}", "role": "editor"} for i in range(n)],
    }


def _comment(cid="c1", **over):
    payload = {"comment_id": cid, "author_id": "a1", "text": "hi"}
    payload.update(over)
    return payload


# --- construction + port injection ------------------------------------------- #


def test_defaults_to_fake_adapter_no_network():
    adapter = SharedProjectAdapter()
    assert isinstance(adapter.port, FakeCloudAdapter)


def test_injected_port_is_used():
    port = _SpyPort()
    adapter = SharedProjectAdapter(port=port)
    assert adapter.port is port


# --- .pixproj blob passthrough (delegates to the injected port) -------------- #


def test_put_and_get_project_delegate_to_port():
    port = _SpyPort()
    adapter = SharedProjectAdapter(port=port)
    blob = serialize_project(Document(8, 8))
    adapter.put_project(PID, blob)
    assert port.put_calls == [(PID, blob)]
    version = port.latest(PID)
    assert adapter.get_project(PID, version.version_id) == blob
    assert port.get_calls == [(PID, version.version_id)]


def test_put_project_rejects_empty_project_id():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.put_project("", b"blob")


# --- membership roster / roles ----------------------------------------------- #


def test_share_returns_normalized_roster_in_order():
    adapter = SharedProjectAdapter()
    roster = adapter.share(PID, _membership(n=3))
    assert roster == (
        RemoteMember("m0", "editor"),
        RemoteMember("m1", "editor"),
        RemoteMember("m2", "editor"),
    )
    assert adapter.members(PID) == roster


def test_share_at_member_cap_boundary_accepted():
    adapter = SharedProjectAdapter()
    roster = adapter.share(PID, _membership(n=MAX_SHARED_MEMBERS))
    assert len(roster) == MAX_SHARED_MEMBERS


def test_share_over_member_cap_raises_shared_project_error():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.share(PID, _membership(n=MAX_SHARED_MEMBERS + 1))


def test_share_project_id_mismatch_raises():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.share(PID, _membership(project_id="other"))


def test_share_malformed_payload_reraised_as_shared_project_error():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.share(PID, {"project_id": PID, "members": "nope"})


def test_members_of_unshared_project_raises():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.members("never-shared")


# --- comments: attach / list / thread / resolve ------------------------------ #


def test_add_and_list_comments_in_insertion_order():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.add_comment(PID, _comment("c1", text="first"))
    adapter.add_comment(PID, _comment("c2", text="second"))
    listed = adapter.comments(PID)
    assert [c.comment_id for c in listed] == ["c1", "c2"]
    assert isinstance(listed[0], ProjectComment)


def test_add_comment_to_unshared_project_raises():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.add_comment("nope", _comment())


def test_add_comment_threaded_reply_via_parent_id():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.add_comment(PID, _comment("root"))
    reply = adapter.add_comment(PID, _comment("reply", parent_id="root"))
    assert reply.parent_id == "root"


def test_add_comment_unknown_parent_raises():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    with pytest.raises(SharedProjectError):
        adapter.add_comment(PID, _comment("reply", parent_id="ghost"))


def test_add_duplicate_comment_id_raises():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.add_comment(PID, _comment("dup"))
    with pytest.raises(SharedProjectError):
        adapter.add_comment(PID, _comment("dup"))


def test_add_oversized_comment_reraised_as_shared_project_error():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    with pytest.raises(SharedProjectError):
        adapter.add_comment(PID, _comment(text="x" * (MAX_COMMENT_BYTES + 1)))


def test_comment_count_cap_enforced_from_constant():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    for i in range(MAX_COMMENTS_PER_PROJECT):
        adapter.add_comment(PID, _comment(f"c{i}"))
    assert len(adapter.comments(PID)) == MAX_COMMENTS_PER_PROJECT
    with pytest.raises(SharedProjectError):
        adapter.add_comment(PID, _comment("one-too-many"))


def test_resolve_comment_marks_resolved():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.add_comment(PID, _comment("c1"))
    updated = adapter.resolve_comment(PID, "c1")
    assert updated.resolved is True
    assert adapter.comments(PID)[0].resolved is True


def test_resolve_unknown_comment_raises():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    with pytest.raises(SharedProjectError):
        adapter.resolve_comment(PID, "ghost")


# --- presence: set / get (sorted) / clear, and ephemerality ------------------ #


def test_set_and_get_presence_sorted_by_member_id():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.set_presence(PID, {"member_id": "mz", "cursor": {"x": 1}})
    adapter.set_presence(PID, {"member_id": "ma", "selection": {"a": 2}})
    entries = adapter.presence(PID)
    assert [e.member_id for e in entries] == ["ma", "mz"]  # deterministic sort
    assert isinstance(entries[0], PresenceEntry)


def test_set_presence_overwrites_same_member():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.set_presence(PID, {"member_id": "m", "cursor": {"x": 1}})
    adapter.set_presence(PID, {"member_id": "m", "cursor": {"x": 9}})
    entries = adapter.presence(PID)
    assert len(entries) == 1
    assert entries[0].cursor == {"x": 9}


def test_clear_presence_removes_entry():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    adapter.set_presence(PID, {"member_id": "m"})
    adapter.clear_presence(PID, "m")
    assert adapter.presence(PID) == ()
    # clearing an absent member is a no-op (does not raise)
    adapter.clear_presence(PID, "absent")


def test_set_presence_malformed_reraised_as_shared_project_error():
    adapter = SharedProjectAdapter()
    adapter.share(PID, _membership())
    with pytest.raises(SharedProjectError):
        adapter.set_presence(PID, {"cursor": {"x": 1}})  # missing member_id


def test_set_presence_on_unshared_project_raises():
    adapter = SharedProjectAdapter()
    with pytest.raises(SharedProjectError):
        adapter.set_presence("nope", {"member_id": "m"})


def test_presence_is_ephemeral_never_written_to_stored_blob():
    """Presence lives in memory only — it never appears in the stored .pixproj bytes."""
    port = _SpyPort()
    adapter = SharedProjectAdapter(port=port)
    blob = serialize_project(Document(8, 8))
    adapter.put_project(PID, blob)
    adapter.share(PID, _membership())
    secret_member = "presence-only-member"
    adapter.set_presence(PID, {"member_id": secret_member, "cursor": {"x": 42}})

    # The stored blob is unchanged and carries no presence trace.
    version = port.latest(PID)
    stored = adapter.get_project(PID, version.version_id)
    assert stored == blob
    assert secret_member.encode("utf-8") not in stored
    # And nothing new was pushed to the port by set_presence.
    assert port.put_calls == [(PID, blob)]
