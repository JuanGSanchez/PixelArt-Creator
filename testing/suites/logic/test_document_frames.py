"""Tests for the Phase-5 reversible frame + tag ops of logic.document (Slice 5A).

Covers :mod:`pixelart_creator.logic.document`: the reversible frame commands
(add / remove-refuses-last / move / duplicate-deep-copy / set-duration), the
document-level frame-tag CRUD (create / edit / delete), the tag-range clamp on
structural frame changes with exact undo restore, and stable additive
``layer_id`` behaviour (fresh on layer-dup, preserved on frame-dup, unique).

Every command asserts ``apply ∘ undo == identity`` and never mutates the
original state until executed. Maps to REQ-P5-LOGIC-004..010 and Gherkin
SC-L004-1 / SC-L005-1..2 / SC-L006-1 / SC-L007-1 / SC-L008-1 / SC-L009-1 /
SC-L010-1..2.
"""

from __future__ import annotations

from typing import List

import pytest

from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.constants import MAX_FRAMES
from pixelart_creator.logic.document import (
    Document,
    DocumentError,
    Layer,
    LayerGroup,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _doc(frames: int = 1) -> Document:
    doc = Document(4, 4)
    for _ in range(frames - 1):
        doc.add_frame()
    return doc


def _all_ids(doc: Document) -> List[int]:
    ids: List[int] = []
    for frame in doc.frames:
        for node in _walk(frame.layers):
            ids.append(node.layer_id)
    return ids


def _walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node, LayerGroup):
            yield from _walk(node.children)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-004 — reversible add-frame (SC-L004-1)                          #
# --------------------------------------------------------------------------- #


def test_add_frame_command_is_reversible():
    doc = _doc(2)
    cmd = doc.make_add_frame_command(after_index=0)
    assert len(doc.frames) == 2  # unapplied until executed
    cmd.execute()
    assert len(doc.frames) == 3
    cmd.undo()
    assert len(doc.frames) == 2


def test_add_frame_inserts_after_index():
    doc = _doc(2)
    original = list(doc.frames)
    cmd = doc.make_add_frame_command(after_index=0)
    cmd.execute()
    assert doc.frames[0] is original[0]
    assert doc.frames[2] is original[1]


def test_add_frame_uses_given_duration():
    doc = _doc(1)
    cmd = doc.make_add_frame_command(after_index=0, duration_ms=250)
    cmd.execute()
    assert doc.frames[1].duration_ms == 250


@pytest.mark.parametrize(
    "kwargs",
    [
        {"after_index": True},
        {"after_index": 5},
        {"after_index": 0, "duration_ms": 0},
        {"after_index": 0, "duration_ms": -5},
    ],
)
def test_add_frame_rejects_invalid(kwargs):
    with pytest.raises(DocumentError):
        _doc(1).make_add_frame_command(**kwargs)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-005 — reversible remove-frame, refuses last (SC-L005-1..2)      #
# --------------------------------------------------------------------------- #


def test_remove_frame_restores_contents_index_and_duration():
    doc = _doc(3)
    doc.frames[1].duration_ms = 250
    doc.frames[1].layers[0].buffer.set_pixel(1, 1, RED)
    middle = doc.frames[1]
    cmd = doc.make_remove_frame_command(1)
    cmd.execute()
    assert len(doc.frames) == 2 and middle not in doc.frames
    cmd.undo()
    assert doc.frames[1] is middle
    assert doc.frames[1].duration_ms == 250
    assert doc.frames[1].layers[0].buffer.get_pixel(1, 1) == RED


def test_remove_last_frame_is_refused():
    doc = _doc(1)
    with pytest.raises(DocumentError):
        doc.make_remove_frame_command(0)
    assert len(doc.frames) == 1


def test_remove_frame_rejects_out_of_range():
    with pytest.raises(DocumentError):
        _doc(2).make_remove_frame_command(9)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-006 — reversible reorder-frame (SC-L006-1)                      #
# --------------------------------------------------------------------------- #


def test_move_frame_is_reversible():
    doc = _doc(3)
    a, b, c = doc.frames
    cmd = doc.make_move_frame_command(1, 0)  # move B before A
    cmd.execute()
    assert doc.frames == [b, a, c]
    cmd.undo()
    assert doc.frames == [a, b, c]


def test_move_frame_does_not_alter_layers_or_duration():
    doc = _doc(3)
    doc.frames[2].duration_ms = 400
    cmd = doc.make_move_frame_command(2, 0)
    cmd.execute()
    assert doc.frames[0].duration_ms == 400


@pytest.mark.parametrize("args", [(9, 0), (0, 9)])
def test_move_frame_rejects_out_of_range(args):
    with pytest.raises(DocumentError):
        _doc(3).make_move_frame_command(*args)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-007 — reversible duplicate-frame, deep copy (SC-L007-1)         #
# --------------------------------------------------------------------------- #


def test_duplicate_frame_deep_copies_pixels_and_duration():
    doc = _doc(1)
    doc.frames[0].duration_ms = 200
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, RED)
    cmd = doc.make_duplicate_frame_command(0)
    cmd.execute()
    assert len(doc.frames) == 2
    copy = doc.frames[1]
    assert copy.duration_ms == 200
    assert copy.layers[0].buffer.get_pixel(0, 0) == RED


def test_duplicate_frame_copy_is_independent():
    doc = _doc(1)
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, RED)
    doc.make_duplicate_frame_command(0).execute()
    doc.frames[1].layers[0].buffer.set_pixel(0, 0, BLUE)
    # Editing the copy leaves the source unchanged.
    assert doc.frames[0].layers[0].buffer.get_pixel(0, 0) == RED


def test_duplicate_frame_is_reversible():
    doc = _doc(1)
    cmd = doc.make_duplicate_frame_command(0)
    cmd.execute()
    assert len(doc.frames) == 2
    cmd.undo()
    assert len(doc.frames) == 1


def test_duplicate_frame_rejects_out_of_range():
    with pytest.raises(DocumentError):
        _doc(1).make_duplicate_frame_command(3)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-008 — reversible set-frame-duration (SC-L008-1)                 #
# --------------------------------------------------------------------------- #


def test_set_frame_duration_is_reversible():
    doc = _doc(1)
    assert doc.frames[0].duration_ms != 400
    original = doc.frames[0].duration_ms
    cmd = doc.make_set_frame_duration_command(0, 400)
    cmd.execute()
    assert doc.frames[0].duration_ms == 400
    cmd.undo()
    assert doc.frames[0].duration_ms == original


@pytest.mark.parametrize("bad", [0, -10, True, 3.5])
def test_set_frame_duration_rejects_non_positive_int(bad):
    with pytest.raises(DocumentError):
        _doc(1).make_set_frame_duration_command(0, bad)


def test_set_frame_duration_rejects_bad_index():
    with pytest.raises(DocumentError):
        _doc(1).make_set_frame_duration_command(5, 100)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-014 — MAX_FRAMES bound                                          #
# --------------------------------------------------------------------------- #


def test_add_frame_bounded_by_max_frames():
    doc = _doc(1)
    doc.frames = [doc.frames[0]] * MAX_FRAMES  # simulate a full document
    with pytest.raises(DocumentError):
        doc.make_add_frame_command(after_index=0)


def test_duplicate_frame_bounded_by_max_frames():
    doc = _doc(1)
    doc.frames = [doc.frames[0]] * MAX_FRAMES
    with pytest.raises(DocumentError):
        doc.make_duplicate_frame_command(0)


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-009/010 — frame tags CRUD + reversibility (SC-L009-1/SC-L010-1) #
# --------------------------------------------------------------------------- #


def test_add_tag_command_is_reversible():
    doc = _doc(6)
    cmd = doc.make_add_tag_command("walk", 1, 4, mode=PlaybackMode.PING_PONG)
    assert doc.frame_tags == []
    cmd.execute()
    assert len(doc.frame_tags) == 1
    tag = doc.frame_tags[0]
    assert tag.name == "walk"
    assert (tag.from_frame, tag.to_frame) == (1, 4)
    assert tag.mode is PlaybackMode.PING_PONG
    cmd.undo()
    assert doc.frame_tags == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "t", "from_frame": 4, "to_frame": 1},  # inverted
        {"name": "t", "from_frame": 0, "to_frame": 9},  # out of range
        {"name": "t", "from_frame": 0, "to_frame": 1, "mode": "loop"},
        {"name": "t", "from_frame": 0, "to_frame": 1, "repeat": -1},
        {"name": "t", "from_frame": 0, "to_frame": 1, "color": "not-a-color"},
        {"name": 123, "from_frame": 0, "to_frame": 1},
    ],
)
def test_add_tag_rejects_invalid(kwargs):
    with pytest.raises(DocumentError):
        _doc(6).make_add_tag_command(**kwargs)


def test_edit_tag_command_is_reversible():
    doc = _doc(6)
    doc.make_add_tag_command("walk", 1, 4).execute()
    cmd = doc.make_edit_tag_command(0, name="run", from_frame=0, to_frame=2)
    cmd.execute()
    tag = doc.frame_tags[0]
    assert tag.name == "run" and (tag.from_frame, tag.to_frame) == (0, 2)
    cmd.undo()
    tag = doc.frame_tags[0]
    assert tag.name == "walk" and (tag.from_frame, tag.to_frame) == (1, 4)


def test_edit_tag_rejects_invalid_result():
    doc = _doc(6)
    doc.make_add_tag_command("walk", 1, 4).execute()
    with pytest.raises(DocumentError):
        doc.make_edit_tag_command(0, from_frame=5, to_frame=1)


def test_edit_tag_rejects_bad_index():
    with pytest.raises(DocumentError):
        _doc(6).make_edit_tag_command(0, name="x")


def test_remove_tag_command_is_reversible():
    doc = _doc(6)
    doc.make_add_tag_command("walk", 1, 4).execute()
    cmd = doc.make_remove_tag_command(0)
    cmd.execute()
    assert doc.frame_tags == []
    cmd.undo()
    assert len(doc.frame_tags) == 1
    assert doc.frame_tags[0].name == "walk"


def test_remove_tag_rejects_bad_index():
    with pytest.raises(DocumentError):
        _doc(6).make_remove_tag_command(0)


def test_overlapping_tags_preserve_creation_order():
    doc = _doc(6)
    doc.make_add_tag_command("a", 0, 3).execute()
    doc.make_add_tag_command("b", 2, 5).execute()  # overlaps "a"
    assert [t.name for t in doc.frame_tags] == ["a", "b"]


# --------------------------------------------------------------------------- #
# REQ-P5-LOGIC-010 — tag ranges clamp on frame remove, restore on undo (L010-2)#
# --------------------------------------------------------------------------- #


def test_tag_range_clamped_on_frame_remove_and_restored_on_undo():
    doc = _doc(6)
    doc.make_add_tag_command("run", 2, 5).execute()
    cmd = doc.make_remove_frame_command(5)
    cmd.execute()
    tag = doc.frame_tags[0]
    assert (tag.from_frame, tag.to_frame) == (2, 4)  # clamped into 5 frames
    cmd.undo()
    tag = doc.frame_tags[0]
    assert (tag.from_frame, tag.to_frame) == (2, 5)  # exact restore
    assert len(doc.frames) == 6


def test_tag_range_stable_when_adding_frame():
    doc = _doc(4)
    doc.make_add_tag_command("t", 1, 3).execute()
    cmd = doc.make_add_frame_command(after_index=3)
    cmd.execute()
    tag = doc.frame_tags[0]
    assert (tag.from_frame, tag.to_frame) == (1, 3)
    cmd.undo()
    assert (tag.from_frame, tag.to_frame) == (1, 3)


# --------------------------------------------------------------------------- #
# Stable layer_id — additive, unique, minted / preserved (research Q4)         #
# --------------------------------------------------------------------------- #


def test_fresh_document_mints_positive_layer_id():
    doc = _doc(1)
    assert doc.frames[0].layers[0].layer_id > 0


def test_layer_ids_are_unique_within_a_frame():
    doc = _doc(1)
    doc.add_layer("second")
    doc.add_layer("third")
    ids = [n.layer_id for n in doc.frames[0].layers]
    assert len(ids) == len(set(ids))
    assert all(i > 0 for i in ids)


def test_add_layer_omitting_id_is_unaffected_additive():
    # An existing call site that builds a Layer without an id stays valid (id 0).
    buffer = Document(2, 2).frames[0].layers[0].buffer
    bare = Layer(buffer, "x")
    assert bare.layer_id == 0


def test_duplicate_layer_mints_fresh_id():
    doc = _doc(1)
    src = doc.frames[0].layers[0]
    doc.make_duplicate_layer_command(0).execute()
    copy = doc.frames[0].layers[1]
    assert copy.layer_id != src.layer_id
    assert copy.layer_id > 0


def test_duplicate_frame_preserves_layer_ids():
    # Frame-dup shares the predecessor's layer *tracks* (ids preserved).
    doc = _doc(1)
    src_ids = [n.layer_id for n in doc.frames[0].layers]
    doc.make_duplicate_frame_command(0).execute()
    copy_ids = [n.layer_id for n in doc.frames[1].layers]
    assert copy_ids == src_ids


def test_layer_id_persists_across_operations():
    doc = _doc(1)
    original = doc.frames[0].layers[0].layer_id
    doc.make_add_frame_command(after_index=0).execute()
    assert doc.frames[0].layers[0].layer_id == original
