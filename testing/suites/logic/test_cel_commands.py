"""Tests for the reversible cross-frame cel operations on
pixelart_creator.logic.document (REQ-P5-LOGIC-016): make_move_cel_command,
make_copy_cel_command and make_create_cel_command.

Covers ``SC-L016-1``..``-7``. The load-bearing assertions: undo after an
overwriting move restores the destination's prior drawing exactly; a copy is
independent; a copy into an existing track shares that track's ``layer_id``;
a cross-track operation does not merge; a drop on the source's own cell
pushes nothing; an out-of-bounds operation is refused totally, changing
nothing; "create a cel here" joins an existing track and refuses on an
occupied destination and at ``MAX_LAYERS_PER_FRAME``.

No Qt import (S11).
"""

from __future__ import annotations

import pytest

from pixelart_creator.logic.constants import MAX_LAYERS_PER_FRAME
from pixelart_creator.logic.document import Document, DocumentError, Layer, LayerGroup
from pixelart_creator.logic.pixel_buffer import PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
GREEN = (0, 255, 0, 255)


def _two_frame_two_track_doc() -> Document:
    """Frame 0: [Background, Track2]. Frame 1: [F1Layer] (its own new track)."""
    doc = Document(4, 4)
    doc.add_layer("Track2")
    doc.add_frame()
    return doc


# --------------------------------------------------------------------------- #
# SC-L016-1 — undo after an overwriting move restores the prior drawing       #
# --------------------------------------------------------------------------- #


def test_undo_after_overwriting_move_restores_destination_exactly():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    dest_track_id = doc.frames[1].layers[0].layer_id
    dest_node_before = doc.frames[1].layers[0]
    dest_node_before.buffer.set_pixel(0, 0, BLUE)

    cmd = doc.make_move_cel_command(
        source_frame_index=0,
        source_track_id=background_id,
        dest_frame_index=1,
        dest_track_id=dest_track_id,
    )
    cmd.execute()
    assert len(doc.frames[1].layers) == 1
    assert doc.frames[1].layers[0].layer_id == background_id

    cmd.undo()
    assert len(doc.frames[1].layers) == 1
    restored = doc.frames[1].layers[0]
    assert restored is dest_node_before
    assert restored.layer_id == dest_track_id
    assert restored.buffer.get_pixel(0, 0) == BLUE
    # And the source cell is restored too.
    assert doc.frames[0].layers[0].layer_id == background_id


def test_move_into_empty_destination_and_undo_round_trip():
    doc = _two_frame_two_track_doc()
    track2 = doc.frames[0].layers[1]
    track2_id = track2.layer_id

    cmd = doc.make_move_cel_command(
        source_frame_index=0,
        source_track_id=track2_id,
        dest_frame_index=1,
        dest_track_id=track2_id,  # not yet present in frame 1 -> empty dest
    )
    cmd.execute()
    assert len(doc.frames[0].layers) == 1  # removed from source
    assert len(doc.frames[1].layers) == 2  # appended to destination
    assert doc.frames[1].layers[-1] is track2

    cmd.undo()
    assert len(doc.frames[0].layers) == 2
    assert doc.frames[0].layers[1] is track2
    assert len(doc.frames[1].layers) == 1


# --------------------------------------------------------------------------- #
# SC-L016-2 — a copy is independent                                           #
# --------------------------------------------------------------------------- #


def test_copy_is_independent_editing_one_does_not_change_the_other():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    source_node = doc.frames[0].layers[0]
    source_node.buffer.set_pixel(0, 0, RED)
    dest_track_id = doc.frames[1].layers[0].layer_id

    doc.make_copy_cel_command(
        source_frame_index=0,
        source_track_id=background_id,
        dest_frame_index=1,
        dest_track_id=dest_track_id,
    ).execute()

    copy_node = doc.frames[1].layers[0]
    assert copy_node is not source_node
    assert copy_node.buffer.get_pixel(0, 0) == RED  # copied faithfully

    # Editing the source afterwards does not touch the copy.
    source_node.buffer.set_pixel(0, 0, GREEN)
    assert copy_node.buffer.get_pixel(0, 0) == RED

    # Editing the copy afterwards does not touch the source.
    copy_node.buffer.set_pixel(1, 1, BLUE)
    assert source_node.buffer.get_pixel(1, 1) != BLUE


# --------------------------------------------------------------------------- #
# SC-L016-3 — a copy into an existing track shares that track's layer_id      #
# --------------------------------------------------------------------------- #


def test_copy_joins_destination_track_id_not_a_freshly_minted_one():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    dest_track_id = doc.frames[1].layers[0].layer_id
    assert dest_track_id != background_id

    doc.make_copy_cel_command(
        source_frame_index=0,
        source_track_id=background_id,
        dest_frame_index=1,
        dest_track_id=dest_track_id,
    ).execute()

    copy_node = doc.frames[1].layers[0]
    assert copy_node.layer_id == dest_track_id
    assert copy_node.layer_id != background_id


def test_copy_undo_removes_the_copy_and_restores_prior_occupant():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    dest_track_id = doc.frames[1].layers[0].layer_id
    prior = doc.frames[1].layers[0]

    cmd = doc.make_copy_cel_command(
        source_frame_index=0,
        source_track_id=background_id,
        dest_frame_index=1,
        dest_track_id=dest_track_id,
    )
    cmd.execute()
    cmd.undo()
    assert doc.frames[1].layers[0] is prior
    assert len(doc.frames[1].layers) == 1
    # Source is untouched throughout (copy never removes the source).
    assert doc.frames[0].layers[0].layer_id == background_id


# --------------------------------------------------------------------------- #
# SC-L016-4 — a cross-track operation does not merge                          #
# --------------------------------------------------------------------------- #


def test_cross_track_move_keeps_the_moved_nodes_own_layer_id():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    dest_track_id = doc.frames[1].layers[0].layer_id
    assert background_id != dest_track_id

    doc.make_move_cel_command(
        source_frame_index=0,
        source_track_id=background_id,
        dest_frame_index=1,
        dest_track_id=dest_track_id,
    ).execute()

    moved = doc.frames[1].layers[0]
    # The moved node keeps its OWN id -- a cross-track move is a move, not a
    # merge into the destination track.
    assert moved.layer_id == background_id
    assert moved.layer_id != dest_track_id


# --------------------------------------------------------------------------- #
# SC-L016-5 — a drop on the source's own cell pushes nothing                  #
# --------------------------------------------------------------------------- #


def test_move_onto_own_cell_is_refused_totally():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    before = [layer.layer_id for frame in doc.frames for layer in frame.layers]

    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=background_id,
            dest_frame_index=0,
            dest_track_id=background_id,
        )
    after = [layer.layer_id for frame in doc.frames for layer in frame.layers]
    assert before == after


def test_copy_onto_own_cell_is_refused_totally():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    with pytest.raises(DocumentError):
        doc.make_copy_cel_command(
            source_frame_index=0,
            source_track_id=background_id,
            dest_frame_index=0,
            dest_track_id=background_id,
        )


# --------------------------------------------------------------------------- #
# SC-L016-6 — an out-of-bounds operation is refused totally, changing nothing #
# --------------------------------------------------------------------------- #


def test_move_out_of_range_frame_index_refused():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    before_frame_count = len(doc.frames)
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=background_id,
            dest_frame_index=99,
            dest_track_id=background_id,
        )
    assert len(doc.frames) == before_frame_count


def test_move_unknown_source_track_refused():
    doc = _two_frame_two_track_doc()
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=999999,
            dest_frame_index=1,
            dest_track_id=999999,
        )


def test_copy_unknown_source_track_refused():
    doc = _two_frame_two_track_doc()
    with pytest.raises(DocumentError):
        doc.make_copy_cel_command(
            source_frame_index=1,
            source_track_id=999999,
            dest_frame_index=0,
            dest_track_id=999999,
        )


def test_move_source_is_a_group_refused():
    doc = _two_frame_two_track_doc()
    group = LayerGroup("G", [Layer(PixelBuffer(4, 4), "child")])
    group.layer_id = 12345
    doc.frames[0].layers.append(group)
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=12345,
            dest_frame_index=1,
            dest_track_id=12345,
        )


def test_move_destination_is_a_group_refused():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    group = LayerGroup("G", [Layer(PixelBuffer(4, 4), "child")])
    group.layer_id = 54321
    doc.frames[1].layers.append(group)
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=background_id,
            dest_frame_index=1,
            dest_track_id=54321,
        )


def test_move_last_layer_of_source_frame_refused_cf89():
    # A single-layer frame's only layer can never be removed (CF-89/D-25) --
    # the same invariant applies to a move that would empty the source frame.
    doc = Document(4, 4)
    doc.add_frame()
    only_id = doc.frames[0].layers[0].layer_id
    dest_id = doc.frames[1].layers[0].layer_id
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=only_id,
            dest_frame_index=1,
            dest_track_id=dest_id,
        )
    assert len(doc.frames[0].layers) == 1


def test_move_into_empty_destination_exceeding_max_layers_refused():
    doc = _two_frame_two_track_doc()
    track2 = doc.frames[0].layers[1]
    track2_id = track2.layer_id
    # Fill frame 1 up to the cap so an empty-destination insert would exceed it.
    while len(doc.frames[1].layers) < MAX_LAYERS_PER_FRAME:
        doc.add_layer(frame_index=1)
    with pytest.raises(DocumentError):
        doc.make_move_cel_command(
            source_frame_index=0,
            source_track_id=track2_id,
            dest_frame_index=1,
            dest_track_id=track2_id,
        )
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME


def test_copy_into_empty_destination_exceeding_max_layers_refused():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    while len(doc.frames[1].layers) < MAX_LAYERS_PER_FRAME:
        doc.add_layer(frame_index=1)
    with pytest.raises(DocumentError):
        doc.make_copy_cel_command(
            source_frame_index=0,
            source_track_id=background_id,
            dest_frame_index=1,
            dest_track_id=background_id,
        )


# --------------------------------------------------------------------------- #
# SC-L016-7 — "create a cel here" joins an existing track; refusal paths      #
# --------------------------------------------------------------------------- #


def test_create_cel_joins_existing_track_not_a_freshly_minted_one():
    doc = _two_frame_two_track_doc()
    track2_id = doc.frames[0].layers[1].layer_id  # exists in frame 0, absent in frame 1

    cmd = doc.make_create_cel_command(frame_index=1, track_id=track2_id, name="New cel")
    cmd.execute()
    assert len(doc.frames[1].layers) == 2
    created = doc.frames[1].layers[-1]
    assert created.layer_id == track2_id
    assert created.name == "New cel"
    # Freshly created buffer is empty (default colour), not copied from anywhere.
    assert created.buffer.get_pixel(0, 0) in ((0, 0, 0, 0), 0)

    cmd.undo()
    assert len(doc.frames[1].layers) == 1


def test_create_cel_refuses_occupied_destination():
    doc = _two_frame_two_track_doc()
    background_id = doc.frames[0].layers[0].layer_id
    with pytest.raises(DocumentError):
        doc.make_create_cel_command(frame_index=0, track_id=background_id)
    assert len(doc.frames[0].layers) == 2


def test_create_cel_refuses_at_max_layers_per_frame():
    doc = _two_frame_two_track_doc()
    while len(doc.frames[1].layers) < MAX_LAYERS_PER_FRAME:
        doc.add_layer(frame_index=1)
    with pytest.raises(DocumentError):
        doc.make_create_cel_command(frame_index=1, track_id=999999)
    assert len(doc.frames[1].layers) == MAX_LAYERS_PER_FRAME


def test_create_cel_out_of_range_frame_refused():
    doc = _two_frame_two_track_doc()
    with pytest.raises(DocumentError):
        doc.make_create_cel_command(frame_index=99, track_id=1)


def test_create_cel_is_the_same_operation_as_copy_with_empty_prior_state():
    # "Create a cel here" and copy-into-empty-cell are one factory family with
    # two entry points: both join the destination track and both undo to an
    # empty cell.
    doc = _two_frame_two_track_doc()
    track2_id = doc.frames[0].layers[1].layer_id

    create_cmd = doc.make_create_cel_command(frame_index=1, track_id=track2_id)
    create_cmd.execute()
    created = doc.frames[1].layers[-1]
    assert created.layer_id == track2_id
    create_cmd.undo()
    assert all(layer.layer_id != track2_id for layer in doc.frames[1].layers)
