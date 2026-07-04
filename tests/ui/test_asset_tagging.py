"""Asset-tagging + tag undo/redo acceptance (REQ-P11-UI-002, Gherkin: Tagging assets).

Slice 1: the tagging panel adds / removes tags on the selected asset through
``AddTagCommand`` / ``RemoveTagCommand`` pushed on the shared ``QUndoStack`` the
``Asset_Library_Session`` owns — so a tag edit is UNDOABLE and, when undone, restores
the exact prior tag set (and REDO re-applies). The reversible maths lives in the Qt-free
``logic/asset_tags`` do/undo pair; the panel only bridges it. Covers add, remove, undo,
redo, idempotence, and the over-cap rejection.

The over-cap-tag caveat (AGT-05 §7): a bound-exceeding tag raises ``AssetTagError`` at
the ``asset_tags`` factory BEFORE any command is built, so no command enters the stack.
The panel surfaces it as a blocking ``QMessageBox.warning`` — which would hang
headless — so this suite drives the panel path ONLY under ``mute_message_boxes`` (which
patches the modal to record-and-return), and additionally asserts the rejection directly
at the factory (``make_add_tag(desc, oversized)`` raising) per AGT-05's directive.

Every test runs under BOTH themes via the autouse ``theme`` fixture; the session is
synchronous and worker-free, so undo/redo read-backs are immediate.
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.asset_catalog import (
    AssetCatalog,
    AssetDescriptor,
    AssetKind,
)
from pixelart_creator.logic.asset_tags import AssetTagError, make_add_tag
from pixelart_creator.logic.constants import MAX_TAG_BYTES, MAX_TAGS_PER_ASSET
from pixelart_creator.ui.asset_library_actions import Asset_Library_Session
from pixelart_creator.ui.asset_tagging_panel import Asset_Tagging_Panel
from pixelart_creator.ui.commands import AddTagCommand, RemoveTagCommand


def _desc(asset_id: str, name: str = "Hero", tags=()) -> AssetDescriptor:
    return AssetDescriptor(
        asset_id=asset_id,
        kind=AssetKind.SPRITE,
        name=name,
        content_hash=f"hash-{asset_id}",
        tags=frozenset(tags),
    )


@pytest.fixture
def tagging(qtbot):
    """A bound ``Asset_Tagging_Panel`` over a session holding one selected asset."""
    session = Asset_Library_Session(
        catalog=AssetCatalog(descriptors=(_desc("a1", "Hero", ("hero",)),))
    )
    widget = Asset_Tagging_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    widget.set_asset("a1")
    return widget, session


def _tags_of(session, asset_id: str):
    return set(session.catalog().get(asset_id).tags)


def _shown_tags(widget):
    return {widget._tag_list.item(i).text() for i in range(widget._tag_list.count())}


# -- REQ-P11-UI-002: add a tag (undoable) ------------------------------------- #


def test_add_tag_pushes_command_and_updates_catalog_and_list(tagging):
    """Adding a tag mutates the catalog, pushes ONE command, and shows in the list."""
    widget, session = tagging
    widget._tag_edit.setText("player")
    widget._on_add_tag()
    assert _tags_of(session, "a1") == {"hero", "player"}
    assert "player" in _shown_tags(widget)
    assert session.undo_stack().count() == 1
    # The command is the tag-add bridge.
    assert isinstance(session.undo_stack().command(0), AddTagCommand)
    # The edit box is cleared after a successful add.
    assert widget._tag_edit.text() == ""


def test_add_tag_undo_restores_prior_set_then_redo_re_adds(tagging):
    """Undo returns the EXACT prior tag set; redo re-adds (REQ-P11-UI-002 core)."""
    widget, session = tagging
    widget._tag_edit.setText("player")
    widget._on_add_tag()
    assert _tags_of(session, "a1") == {"hero", "player"}

    session.undo_stack().undo()
    assert _tags_of(session, "a1") == {"hero"}
    assert "player" not in _shown_tags(widget)

    session.undo_stack().redo()
    assert _tags_of(session, "a1") == {"hero", "player"}
    assert "player" in _shown_tags(widget)


def test_add_tag_via_return_key(tagging, qtbot):
    """The tag edit's returnPressed drives the same add handler (keyboard path)."""
    widget, session = tagging
    widget._tag_edit.setText("enemy")
    widget._tag_edit.returnPressed.emit()
    assert "enemy" in _tags_of(session, "a1")


def test_add_blank_tag_is_a_noop(tagging):
    """A whitespace-only tag is ignored — no command, no catalog change."""
    widget, session = tagging
    widget._tag_edit.setText("   ")
    widget._on_add_tag()
    assert _tags_of(session, "a1") == {"hero"}
    assert session.undo_stack().count() == 0


def test_add_duplicate_tag_is_idempotent(tagging):
    """Re-adding a present tag leaves the set unchanged (idempotent do())."""
    widget, session = tagging
    widget._tag_edit.setText("hero")  # already present
    widget._on_add_tag()
    assert _tags_of(session, "a1") == {"hero"}


# -- REQ-P11-UI-002: remove a tag (undoable) ---------------------------------- #


def test_remove_tag_pushes_command_and_undo_restores(tagging):
    """Removing a selected tag is undoable and restores the exact prior set."""
    widget, session = tagging
    # Select the 'hero' tag then remove it.
    widget._tag_list.setCurrentRow(0)
    widget._on_remove_tag()
    assert _tags_of(session, "a1") == set()
    assert isinstance(session.undo_stack().command(0), RemoveTagCommand)

    session.undo_stack().undo()
    assert _tags_of(session, "a1") == {"hero"}


def test_remove_with_no_tag_selected_is_a_noop(tagging):
    """Pressing Remove with no tag selected does nothing (no command)."""
    widget, session = tagging
    widget._tag_list.setCurrentItem(None)
    widget._on_remove_tag()
    assert _tags_of(session, "a1") == {"hero"}
    assert session.undo_stack().count() == 0


# -- REQ-P11-UI-002: over-cap tag rejection (the AGT-05 §7 caveat) ------------ #


def test_over_byte_tag_rejected_at_factory_without_command(tagging, mute_message_boxes):
    """An over-``MAX_TAG_BYTES`` tag is rejected at the factory (no command pushed).

    Driven through the panel handler ONLY under ``mute_message_boxes`` so the blocking
    ``QMessageBox.warning`` (which would hang headless — AGT-05 §7) records instead. The
    factory raises before a command is built, so the stack stays empty.
    """
    widget, session = tagging
    widget._tag_edit.setText("x" * (MAX_TAG_BYTES + 1))
    widget._on_add_tag()
    assert session.undo_stack().count() == 0  # never pushed
    assert _tags_of(session, "a1") == {"hero"}  # unchanged
    warnings = [c for c in mute_message_boxes if c[0] == "warning"]
    assert warnings, "an over-cap tag must surface a translatable warning"


def test_over_byte_tag_raises_at_the_factory_directly(tagging):
    """AGT-05 §7 directive: assert the rejection at the pure factory, not the modal."""
    _widget, session = tagging
    descriptor = session.catalog().get("a1")
    with pytest.raises(AssetTagError):
        make_add_tag(descriptor, "x" * (MAX_TAG_BYTES + 1))


def test_remove_tag_factory_error_is_surfaced_not_pushed(
    tagging, monkeypatch, mute_message_boxes
):
    """A remove-tag factory ``AssetTagError`` surfaces as a warning, never pushed.

    The listed tags are always valid, so ``make_remove_tag`` cannot raise on them
    naturally; patch it to raise to exercise the panel's defensive surfacing branch
    (mirrors the add-tag over-cap path) under the muted modal.
    """
    widget, session = tagging

    def _boom(*_a, **_k):
        raise AssetTagError("rejected removal")

    monkeypatch.setattr(
        "pixelart_creator.ui.asset_tagging_panel.make_remove_tag", _boom
    )
    widget._tag_list.setCurrentRow(0)
    widget._on_remove_tag()  # must not raise
    assert session.undo_stack().count() == 0
    assert _tags_of(session, "a1") == {"hero"}
    assert any(c[0] == "warning" for c in mute_message_boxes)


def test_over_count_cap_rejected_at_factory(tagging):
    """Adding past ``MAX_TAGS_PER_ASSET`` raises ``AssetTagError`` at the factory."""
    _widget, session = tagging
    full = _desc("full", "Full", tuple(f"t{i}" for i in range(MAX_TAGS_PER_ASSET)))
    with pytest.raises(AssetTagError):
        make_add_tag(full, "one-too-many")


# -- Guard branches: unbound / no-selection handlers -------------------------- #


def test_add_and_remove_are_noops_without_a_session(qtbot):
    """An unbound tagging panel ignores add/remove (session-None guard)."""
    widget = Asset_Tagging_Panel()
    qtbot.addWidget(widget)
    widget._tag_edit.setText("x")
    widget._on_add_tag()  # must not raise
    widget._on_remove_tag()  # must not raise


def test_add_and_remove_are_noops_with_no_asset_selected(qtbot):
    """A bound panel with no asset selected ignores add/remove (descriptor-None)."""
    session = Asset_Library_Session(catalog=AssetCatalog(descriptors=(_desc("a1"),)))
    widget = Asset_Tagging_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    # No set_asset -> _asset_id is "" -> _current_descriptor is None.
    widget._tag_edit.setText("x")
    widget._on_add_tag()
    widget._on_remove_tag()
    assert session.undo_stack().count() == 0


def test_controls_disabled_until_an_asset_is_selected(qtbot):
    """Add/edit controls are disabled with no asset; enabled once one is selected."""
    session = Asset_Library_Session(
        catalog=AssetCatalog(descriptors=(_desc("a1", "Hero", ("hero",)),))
    )
    widget = Asset_Tagging_Panel()
    qtbot.addWidget(widget)
    widget.set_session(session)
    assert not widget._add_button.isEnabled()
    assert not widget._tag_edit.isEnabled()
    widget.set_asset("a1")
    assert widget._add_button.isEnabled()
    assert widget._tag_edit.isEnabled()
    # Remove stays disabled until a tag row is selected.
    assert not widget._remove_button.isEnabled()
    widget._tag_list.setCurrentRow(0)
    assert widget._remove_button.isEnabled()
