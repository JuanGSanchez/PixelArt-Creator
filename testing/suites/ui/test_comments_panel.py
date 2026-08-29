"""Comments panel acceptance (REQ-P10-UI-010, Gherkin SC-UI-010-1).

Slice B: the user adds, views, threads, and resolves comments on a shared project.
Comment text is untrusted, validated input (Article VII): the per-comment
``MAX_COMMENT_BYTES`` cap is enforced at the UI edge on the **UTF-8 byte length** with a
live byte counter + feedback, and the per-project ``MAX_COMMENTS_PER_PROJECT`` cap is
surfaced when the adapter reports it. Threading nests a reply under the selected parent.

Every test runs under BOTH light and dark themes (autouse ``theme`` fixture). The
session is the synchronous loopback seam — read-back follows the call with no wait.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.constants import MAX_COMMENT_BYTES
from pixelart_creator.ui.collaboration_actions import Collaboration_Session
from pixelart_creator.ui.comments_panel import Comments_Panel


@pytest.fixture
def shared(qtbot):
    """A ``Comments_Panel`` bound to a session with one active shared project."""
    session = Collaboration_Session()
    session.share("proj", [("alice", "owner")])
    widget = Comments_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget._author_edit.setText("alice")
    return widget, session


def _add_comment(widget, text: str) -> None:
    """Type ``text`` into the editor and press Add (drives the real handler)."""
    widget._editor.setPlainText(text)
    widget._add_button.click()


def test_sc_ui_010_add_view_and_resolve_a_comment(shared):
    """SC-UI-010-1: an added comment is shown Open, then Resolve marks it Resolved."""
    widget, session = shared
    _add_comment(widget, "needs more contrast")

    tree = widget._tree
    assert tree.topLevelItemCount() == 1
    item = tree.topLevelItem(0)
    assert item.text(0) == "alice"
    assert item.text(1) == "needs more contrast"
    assert item.text(2) == widget.tr("Open")

    # Select the comment and resolve it.
    tree.setCurrentItem(item)
    widget._resolve_button.click()
    resolved = session.comments("proj")
    assert resolved[0].resolved is True
    assert widget._tree.topLevelItem(0).text(2) == widget.tr("Resolved")


def test_sc_ui_010_reply_is_threaded_under_parent(shared):
    """SC-UI-010-1: a reply to the selected comment nests under it (parent_id)."""
    widget, session = shared
    _add_comment(widget, "top-level")
    widget._tree.setCurrentItem(widget._tree.topLevelItem(0))
    widget._reply_check.setChecked(True)
    _add_comment(widget, "a reply")

    # One top-level comment with one nested child. The tree is rebuilt on refresh,
    # so re-query the (fresh) parent item rather than reuse the pre-reply handle.
    assert widget._tree.topLevelItemCount() == 1
    parent_item = widget._tree.topLevelItem(0)
    assert parent_item.childCount() == 1
    assert parent_item.child(0).text(1) == "a reply"
    # The domain model recorded the parent link.
    comments = {c.text: c for c in session.comments("proj")}
    assert comments["a reply"].parent_id == comments["top-level"].comment_id


def test_live_byte_counter_uses_utf8_length(shared):
    """The counter reflects the live UTF-8 byte length, not character count."""
    widget, _session = shared
    widget._editor.setPlainText("aé")  # 'é' is 2 bytes in UTF-8 -> 3 bytes total
    assert str(3) in widget._counter.text()
    assert str(MAX_COMMENT_BYTES) in widget._counter.text()


def test_sc_ui_010_byte_cap_measured_on_utf8_not_chars(shared, mute_message_boxes):
    """SC-UI-010-1 edge: text whose UTF-8 length > cap is refused (byte, not char)."""
    widget, session = shared
    # Multi-byte payload: char count is under the cap but the UTF-8 byte length is
    # over it, proving the edge check measures encoded bytes (matches the adapter).
    chars = MAX_COMMENT_BYTES // 2 + 1
    text = "é" * chars
    assert len(text) <= MAX_COMMENT_BYTES  # char count alone would pass
    assert len(text.encode("utf-8")) > MAX_COMMENT_BYTES  # bytes exceed the cap
    _add_comment(widget, text)
    assert session.comments("proj") == ()  # nothing stored
    assert any(c[0] == "warning" for c in mute_message_boxes)


def test_comment_at_the_byte_cap_is_accepted(shared):
    """A comment exactly at ``MAX_COMMENT_BYTES`` (ASCII) is accepted (boundary)."""
    widget, session = shared
    _add_comment(widget, "a" * MAX_COMMENT_BYTES)
    assert len(session.comments("proj")) == 1


def test_sc_ui_010_project_comment_cap_rejection_is_surfaced(
    shared, monkeypatch, mute_message_boxes
):
    """SC-UI-010-1 edge: the adapter's ``MAX_COMMENTS_PER_PROJECT`` cap is surfaced."""
    widget, session = shared
    # Shrink the per-project cap on the adapter so the second add trips it; the panel
    # surfaces the adapter's SharedProjectError as a warning (defence in depth).
    monkeypatch.setattr(
        "pixelart_creator.data.cloud.shared_adapter.MAX_COMMENTS_PER_PROJECT", 1
    )
    _add_comment(widget, "first")
    _add_comment(widget, "second")  # over the (patched) project cap
    assert len(session.comments("proj")) == 1
    assert any(c[0] == "warning" for c in mute_message_boxes)


def test_comment_before_project_open_is_guarded(qtbot, mute_message_boxes):
    """Commenting with no active shared project informs the user and stores nothing."""
    session = Collaboration_Session()
    widget = Comments_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget._author_edit.setText("alice")
    _add_comment(widget, "orphan comment")
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_comment_without_author_is_guarded(shared, mute_message_boxes):
    """Commenting with no member id informs the user and stores nothing."""
    widget, session = shared
    widget._author_edit.clear()
    _add_comment(widget, "who am I")
    assert session.comments("proj") == ()
    assert any(c[0] == "information" for c in mute_message_boxes)


def test_resolve_and_reply_disabled_without_selection(shared):
    """Resolve + Reply are disabled until a comment is selected (unambiguous target)."""
    widget, _session = shared
    _add_comment(widget, "top")
    widget._tree.setCurrentItem(None)
    assert not widget._resolve_button.isEnabled()
    assert not widget._reply_check.isEnabled()
    widget._tree.setCurrentItem(widget._tree.topLevelItem(0))
    assert widget._resolve_button.isEnabled()
    assert widget._reply_check.isEnabled()
