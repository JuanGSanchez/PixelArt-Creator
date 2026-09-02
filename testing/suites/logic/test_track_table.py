"""Tests for pixelart_creator.logic.track_table (REQ-P5-LOGIC-015).

Covers ``SC-L015-1``..``-5``: a duplicated frame shares the source's tracks
(``make_duplicate_frame_command`` preserves ``layer_id``); a frame missing a
track yields an empty cell, never an error or a substituted blank layer; row
order is deterministic for the same document + active frame; group nodes
appear as rows in tree order; and the module's own boundary/error surface
(bad ``active_frame``, the ``EMPTY_CELL`` singleton contract).

No Qt import (S11).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import PixelBuffer
from pixelart_creator.logic.track_table import (
    EMPTY_CELL,
    EmptyCell,
    TrackTable,
    TrackTableError,
    track_table,
)


def _doc_two_layers() -> Document:
    """A one-frame document with two tracks: Background then Ink."""
    doc = Document(4, 4)
    doc.add_layer("Ink")
    return doc


# --------------------------------------------------------------------------- #
# SC-L015-1 — duplicated frame shares the source's tracks                     #
# --------------------------------------------------------------------------- #


def test_duplicated_frame_shares_source_tracks():
    doc = _doc_two_layers()
    source_ids = [layer.layer_id for layer in doc.frames[0].layers]
    doc.make_duplicate_frame_command(0).execute()
    assert len(doc.frames) == 2

    table = track_table(doc, active_frame=0)
    assert [row.layer_id for row in table.rows] == source_ids
    for row in table.rows:
        # Both frames carry every track — no empty cells anywhere.
        assert row.cells[0] is not EMPTY_CELL
        assert row.cells[1] is not EMPTY_CELL
        assert row.cells[0].layer_id == row.cells[1].layer_id == row.layer_id
        # The duplicate is an independent node, not the same object.
        assert row.cells[0] is not row.cells[1]


# --------------------------------------------------------------------------- #
# SC-L015-2 — a frame missing a track yields an empty cell                    #
# --------------------------------------------------------------------------- #


def test_frame_missing_track_yields_empty_cell_not_error():
    doc = _doc_two_layers()
    doc.add_frame()  # a fresh frame with its own, unrelated new track

    table = track_table(doc, active_frame=0)
    assert len(table.rows) == 3  # Background, Ink, and the new frame's track

    by_id = {row.layer_id: row for row in table.rows}
    background_id = doc.frames[0].layers[0].layer_id
    ink_id = doc.frames[0].layers[1].layer_id
    new_id = doc.frames[1].layers[0].layer_id

    assert by_id[background_id].cells[1] is EMPTY_CELL
    assert by_id[ink_id].cells[1] is EMPTY_CELL
    assert isinstance(by_id[background_id].cells[1], EmptyCell)
    assert by_id[new_id].cells[0] is EMPTY_CELL
    assert by_id[new_id].cells[1] is doc.frames[1].layers[0]


def test_active_frame_without_a_track_present_in_other_frames():
    # Symmetric direction: viewing from the frame that lacks the track.
    doc = _doc_two_layers()
    doc.add_frame()
    table = track_table(doc, active_frame=1)
    new_id = doc.frames[1].layers[0].layer_id
    by_id = {row.layer_id: row for row in table.rows}
    # The active frame's own track comes first (row order), but cells are
    # always indexed by document frame position, not by active-frame offset.
    assert table.rows[0].layer_id == new_id
    assert by_id[new_id].cells[1] is doc.frames[1].layers[0]
    assert by_id[new_id].cells[0] is EMPTY_CELL
    # Tracks absent from the active frame still appear, empty in it.
    background_id = doc.frames[0].layers[0].layer_id
    assert by_id[background_id].cells[1] is EMPTY_CELL
    assert by_id[background_id].cells[0] is doc.frames[0].layers[0]


# --------------------------------------------------------------------------- #
# SC-L015-3 — row order is deterministic for the same document + frame        #
# --------------------------------------------------------------------------- #


def test_row_order_is_deterministic_for_same_inputs():
    doc = _doc_two_layers()
    doc.add_frame()
    doc.add_layer("Extra", frame_index=1)

    first = track_table(doc, active_frame=0)
    second = track_table(doc, active_frame=0)
    assert first == second
    assert [row.layer_id for row in first.rows] == [row.layer_id for row in second.rows]


def test_absent_tracks_ordered_by_earliest_carrying_frame_then_tree_position():
    doc = Document(4, 4)
    background_id = doc.frames[0].layers[0].layer_id
    doc.add_frame()
    frame1_extra = doc.add_layer("F1-Extra", frame_index=1)
    doc.add_frame()
    frame2_extra = doc.add_layer("F2-Extra", frame_index=2)

    # active_frame=0 has only "Background"; the other two tracks are absent
    # and must be ordered by (earliest frame carrying them, tree position).
    table = track_table(doc, active_frame=0)
    ids = [row.layer_id for row in table.rows]
    assert ids == [
        background_id,
        doc.frames[1].layers[0].layer_id,
        frame1_extra.layer_id,
        doc.frames[2].layers[0].layer_id,
        frame2_extra.layer_id,
    ]


def test_first_seen_frame_wins_and_does_not_reorder_on_later_frames():
    # A track present in frame 1 and frame 2 (but absent from active frame 0)
    # must be ordered by frame 1's position, not reshuffled by frame 2.
    doc = Document(4, 4)
    doc.add_frame()
    frame1_base_id = doc.frames[1].layers[0].layer_id
    shared = doc.add_layer("Shared", frame_index=1)
    doc.make_duplicate_frame_command(1).execute()  # frame 2 also carries `shared`
    # Frame 2 (the duplicate) now sits at index 2, ahead of this new track,
    # but frame 1 saw `shared` first, so `shared` must not move after it.
    doc.add_layer("Frame1Only", frame_index=1)

    table = track_table(doc, active_frame=0)
    ids = [
        row.layer_id
        for row in table.rows
        if row.layer_id != doc.frames[0].layers[0].layer_id
    ]
    assert ids == [frame1_base_id, shared.layer_id, doc.frames[1].layers[2].layer_id]


# --------------------------------------------------------------------------- #
# SC-L015-4 — group nodes appear as rows in tree order                        #
# --------------------------------------------------------------------------- #


def test_group_nodes_appear_as_rows_in_tree_order():
    doc = Document(4, 4)
    background = doc.frames[0].layers[0]
    child_a = Layer(PixelBuffer(4, 4), "ChildA")
    child_a.layer_id = 101
    child_b = Layer(PixelBuffer(4, 4), "ChildB")
    child_b.layer_id = 102
    group = LayerGroup("Group", [child_a, child_b])
    group.layer_id = 100
    doc.frames[0].layers = [background, group]

    table = track_table(doc, active_frame=0)
    ids = [row.layer_id for row in table.rows]
    assert ids == [background.layer_id, 100, 101, 102]
    labels = [row.label for row in table.rows]
    assert labels == ["Background", "Group", "ChildA", "ChildB"]
    # The group's own row carries the group node as its occupant.
    group_row = table.rows[1]
    assert group_row.cells[0] is group


def test_nested_group_children_appear_depth_first():
    doc = Document(4, 4)
    inner_child = Layer(PixelBuffer(4, 4), "Inner")
    inner_child.layer_id = 202
    inner_group = LayerGroup("Inner group", [inner_child])
    inner_group.layer_id = 201
    outer_child = Layer(PixelBuffer(4, 4), "OuterChild")
    outer_child.layer_id = 203
    outer_group = LayerGroup("Outer", [inner_group, outer_child])
    outer_group.layer_id = 200
    doc.frames[0].layers = [outer_group]

    table = track_table(doc, active_frame=0)
    assert [row.layer_id for row in table.rows] == [200, 201, 202, 203]


# --------------------------------------------------------------------------- #
# SC-L015-5 / boundary + error surface                                        #
# --------------------------------------------------------------------------- #


def test_rejects_out_of_range_active_frame():
    doc = Document(4, 4)
    with pytest.raises(TrackTableError):
        track_table(doc, active_frame=1)
    with pytest.raises(TrackTableError):
        track_table(doc, active_frame=-1)


def test_rejects_non_int_active_frame():
    doc = Document(4, 4)
    with pytest.raises(TrackTableError):
        track_table(doc, active_frame="0")  # type: ignore[arg-type]


def test_rejects_bool_active_frame():
    # bool is an int subclass in Python; the module explicitly refuses it.
    doc = Document(4, 4)
    with pytest.raises(TrackTableError):
        track_table(doc, active_frame=True)


def test_track_table_does_not_mutate_document():
    doc = _doc_two_layers()
    doc.add_frame()
    before_frame_count = len(doc.frames)
    before_ids = [[n.layer_id for n in f.layers] for f in doc.frames]

    track_table(doc, active_frame=0)

    assert len(doc.frames) == before_frame_count
    assert [[n.layer_id for n in f.layers] for f in doc.frames] == before_ids


def test_single_frame_single_layer_table_shape():
    doc = Document(4, 4)
    table = track_table(doc, active_frame=0)
    assert isinstance(table, TrackTable)
    assert len(table.rows) == 1
    row = table.rows[0]
    assert row.label == "Background"
    assert len(row.cells) == 1
    assert row.cells[0] is doc.frames[0].layers[0]


def test_empty_cell_singleton_identity_and_repr():
    assert EMPTY_CELL is EMPTY_CELL
    assert isinstance(EMPTY_CELL, EmptyCell)
    assert repr(EMPTY_CELL) == "EMPTY_CELL"
    # A freshly constructed EmptyCell is a distinct instance from the shared
    # singleton — callers must compare with `is EMPTY_CELL`, never `==`
    # against a second instance (module contract).
    assert EmptyCell() is not EMPTY_CELL
