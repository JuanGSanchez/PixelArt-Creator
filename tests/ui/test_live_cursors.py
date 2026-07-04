"""Live collaborator-cursor overlay acceptance (REQ-P10-UI-013).

Phase-10 Slice C. The ``Live_Cursors_Overlay`` renders OTHER collaborators' cursors +
selection live on the shared scene from the ephemeral presence channel, never persisted.
These tests prove the acceptance surface:

* other collaborators' cursors render (roster grows from ``apply_presence`` /
  ``set_cursor``; the item paints without error under both themes);
* the roster is BOUNDED by ``MAX_SHARED_MEMBERS`` (a presence flood cannot make the draw
  unbounded — Article VII);
* a disconnect / a cursor-less presence removes a cursor;
* the local member never renders its own echo;
* the ``Main_Window`` presence route + disconnect-clear + visibility toggle wire the
  overlay correctly (integration).

Every test runs under BOTH themes via the autouse ``theme`` fixture.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from pixelart_creator.logic.constants import MAX_SHARED_MEMBERS
from pixelart_creator.ui.live_cursors_overlay import Live_Cursors_Overlay


@pytest.fixture
def overlay():
    """A fresh overlay spanning a 128x128 scene rect (tracked + disposed by conftest)."""
    return Live_Cursors_Overlay(QRectF(0, 0, 128, 128))


# -- other collaborators' cursors render -------------------------------------- #


def test_apply_presence_adds_a_collaborator_cursor(overlay):
    """A presence payload with a cursor adds that collaborator to the roster."""
    overlay.apply_presence({"member_id": "alice", "cursor": {"x": 10, "y": 20}})
    assert overlay.cursor_count() == 1
    assert overlay.cursor_ids() == ("alice",)


def test_set_cursor_and_multiple_collaborators(overlay):
    """Several collaborators render simultaneously (deterministic id order)."""
    overlay.set_cursor("bob", 1, 2)
    overlay.set_cursor("carol", 3, 4)
    assert overlay.cursor_count() == 2
    assert overlay.cursor_ids() == ("bob", "carol")


def test_presence_with_selection_is_accepted(overlay):
    """A presence payload carrying a selection rect is stored (drawn behind the mark)."""
    overlay.apply_presence(
        {
            "member_id": "dave",
            "cursor": {"x": 5, "y": 5},
            "selection": {"x": 0, "y": 0, "width": 16, "height": 16},
        }
    )
    assert overlay.cursor_ids() == ("dave",)


# -- bounded roster (Article VII) --------------------------------------------- #


def test_roster_is_bounded_by_max_shared_members(overlay):
    """A presence flood cannot grow the roster past ``MAX_SHARED_MEMBERS``."""
    for i in range(MAX_SHARED_MEMBERS + 25):
        overlay.set_cursor(f"member-{i}", i, i)
    assert overlay.cursor_count() == MAX_SHARED_MEMBERS


def test_existing_member_still_updates_at_capacity(overlay):
    """At capacity an already-present member's cursor still refreshes (no new slot)."""
    for i in range(MAX_SHARED_MEMBERS):
        overlay.set_cursor(f"member-{i}", i, i)
    overlay.set_cursor("member-0", 99, 99)  # update, not a new member
    assert overlay.cursor_count() == MAX_SHARED_MEMBERS


# -- removal: disconnect / idle / clear --------------------------------------- #


def test_remove_cursor_drops_a_collaborator(overlay):
    """Removing a collaborator (they left) drops their marker."""
    overlay.set_cursor("alice", 1, 1)
    overlay.set_cursor("bob", 2, 2)
    overlay.remove_cursor("alice")
    assert overlay.cursor_ids() == ("bob",)


def test_presence_without_cursor_removes_marker(overlay):
    """A presence payload without a cursor removes that member (present but idle)."""
    overlay.set_cursor("alice", 1, 1)
    overlay.apply_presence({"member_id": "alice"})  # idle -> remove marker
    assert overlay.cursor_count() == 0


def test_clear_removes_every_cursor(overlay):
    """``clear`` empties the roster (on disconnect / document switch)."""
    overlay.set_cursor("alice", 1, 1)
    overlay.set_cursor("bob", 2, 2)
    overlay.clear()
    assert overlay.cursor_count() == 0


def test_local_member_echo_is_not_drawn(overlay):
    """The local member's own presence echo never renders as a cursor."""
    overlay.set_local_member("me")
    overlay.set_cursor("me", 1, 1)
    overlay.apply_presence({"member_id": "me", "cursor": {"x": 2, "y": 2}})
    assert overlay.cursor_count() == 0


def test_malformed_presence_is_ignored(overlay):
    """A presence payload with no valid member id is a safe no-op (Article VII)."""
    overlay.apply_presence({"cursor": {"x": 1, "y": 1}})  # no member_id
    overlay.apply_presence({"member_id": "", "cursor": {"x": 1, "y": 1}})
    assert overlay.cursor_count() == 0


# -- the item paints without error (both themes, exposedRect-culled) ---------- #


def _paint_overlay(item: Live_Cursors_Overlay) -> None:
    """Render the overlay's own paint path onto an offscreen image (both themes)."""
    from PySide6.QtWidgets import QGraphicsScene, QStyleOptionGraphicsItem

    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, 128, 128)
    scene.addItem(item)
    image = QImage(128, 128, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    option = QStyleOptionGraphicsItem()
    option.exposedRect = QRectF(0, 0, 128, 128)
    try:
        item.paint(painter, option, None)
    finally:
        painter.end()
        scene.removeItem(item)


def test_overlay_paints_cursors_and_selection_without_error(overlay, theme):
    """The per-frame paint runs under the active theme with cursors + a selection."""
    overlay.set_cursor("alice", 10, 20)
    overlay.apply_presence(
        {
            "member_id": "bob",
            "cursor": {"x": 30, "y": 40},
            "selection": {"x": 5, "y": 5, "width": 20, "height": 20},
        }
    )
    _paint_overlay(overlay)  # must not raise in either theme


def test_empty_overlay_paint_is_a_noop(overlay):
    """Painting an empty overlay early-returns (no cursors to draw)."""
    _paint_overlay(overlay)


# -- Main_Window integration: presence route + clear + visibility toggle ------ #


def test_window_routes_presence_to_active_tab_overlay(qtbot):
    """``_on_presence_received`` applies a presence payload to the active tab overlay."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    assert record.live_cursors is not None

    win._on_presence_received({"member_id": "alice", "cursor": {"x": 3, "y": 3}})
    assert record.live_cursors.cursor_ids() == ("alice",)


def test_window_disconnect_clears_live_cursors(qtbot):
    """Leaving the relay clears the active tab's live cursors."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    record.live_cursors.set_cursor("alice", 1, 1)
    win._on_realtime_disconnect()
    assert record.live_cursors.cursor_count() == 0


def test_window_live_cursor_toggle_sets_overlay_visibility(qtbot):
    """The 'Show Live Cursors' action toggles the active overlay's visibility."""
    from pixelart_creator.ui.main_window import Main_Window

    win = Main_Window()
    qtbot.addWidget(win)
    record = win.active_tab()
    win._live_cursors_action.setChecked(True)
    assert record.live_cursors.isVisible() is True
    win._live_cursors_action.setChecked(False)
    assert record.live_cursors.isVisible() is False
