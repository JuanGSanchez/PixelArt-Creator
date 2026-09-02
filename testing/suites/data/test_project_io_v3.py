"""Tests for the .pixproj schema-v3 animation persistence.

Covers :mod:`pixelart_creator.data.project_io`: the v3 round-trip of document
``frame_tags`` (native :class:`PlaybackMode` value strings), per-node stable
``layer_id`` and per-frame ``duration_ms``; v1/v2 back-compat (tagless projects
load with an empty tag collection + synthesised ``layer_id`` s); and the
defensive tag-load rejections that each raise :class:`ProjectIOError` (unknown
mode, out-of-range / inverted range, bad colour, malformed tag, non-list
container, bad repeat) with no eval/exec.

Maps to REQ-P5-DATA-001..003 and Gherkin SC-D001-1 / SC-D002-1 / SC-D003-1.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.document import Document

RED = (255, 0, 0, 255)


def _tagged_document(frames: int = 6) -> Document:
    doc = Document(4, 4)
    for _ in range(frames - 1):
        doc.add_frame()
    doc.frames[1].layers[0].buffer.set_pixel(0, 0, RED)
    doc.frames[2].duration_ms = 250
    doc.make_add_tag_command(
        "walk", 1, 4, mode=PlaybackMode.PING_PONG, repeat=0
    ).execute()
    doc.make_add_tag_command("idle", 0, 0, mode=PlaybackMode.ONCE, repeat=3).execute()
    return doc


def _valid_payload(frames: int = 6) -> Dict[str, Any]:
    return pio.serialize(_tagged_document(frames))


# --------------------------------------------------------------------------- #
# v3 serialise shape.                                                          #
# --------------------------------------------------------------------------- #


def test_serialize_declares_version_3():
    payload = pio.serialize(Document(2, 2))
    # Saving always writes the current schema (the FORMAT_VERSION constant, not a
    # literal); v3 still loads back-compat.
    assert payload["version"] == pio.FORMAT_VERSION
    assert payload["frame_tags"] == []


def test_serialize_writes_native_playback_mode_strings():
    payload = _valid_payload()
    modes = {t["name"]: t["mode"] for t in payload["frame_tags"]}
    assert modes == {"walk": "ping_pong", "idle": "once"}


def test_serialize_includes_layer_id_per_node():
    payload = _valid_payload()
    node = payload["frames"][0]["layers"][0]
    assert isinstance(node["layer_id"], int) and node["layer_id"] > 0


# --------------------------------------------------------------------------- #
# REQ-P5-DATA-001 — frame tags round-trip (SC-D001-1)                          #
# --------------------------------------------------------------------------- #


def test_frame_tags_round_trip_identically(tmp_path):
    doc = _tagged_document()
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "tagged"))
    assert loaded.frame_tags == doc.frame_tags


def test_frame_tags_preserve_order_modes_and_repeat(tmp_path):
    doc = _tagged_document()
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "order"))
    assert [t.name for t in loaded.frame_tags] == ["walk", "idle"]
    assert loaded.frame_tags[0].mode is PlaybackMode.PING_PONG
    assert loaded.frame_tags[1].mode is PlaybackMode.ONCE
    assert loaded.frame_tags[1].repeat == 3


def test_layer_id_round_trips(tmp_path):
    doc = _tagged_document()
    before = [n.layer_id for f in doc.frames for n in f.layers]
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "ids"))
    after = [n.layer_id for f in loaded.frames for n in f.layers]
    assert after == before


# --------------------------------------------------------------------------- #
# REQ-P5-DATA-002 — frames + per-frame durations round-trip (SC-D002-1)        #
# --------------------------------------------------------------------------- #


def test_per_frame_durations_round_trip(tmp_path):
    doc = Document(4, 4)
    doc.add_frame(duration_ms=250)
    doc.add_frame(duration_ms=500)
    doc.add_frame(duration_ms=100)
    before = [f.duration_ms for f in doc.frames]
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "dur"))
    assert [f.duration_ms for f in loaded.frames] == before
    assert len(loaded.frames) == len(doc.frames)


# --------------------------------------------------------------------------- #
# REQ-P5-DATA-003 — back-compat: v1/v2 tagless load (SC-D003-1)                #
# --------------------------------------------------------------------------- #


def test_v2_tagless_loads_with_empty_tags_and_minted_ids():
    payload = _valid_payload()
    payload["version"] = 2
    del payload["frame_tags"]  # a tagless (older) project
    for frame in payload["frames"]:
        for node in frame["layers"]:
            node.pop("layer_id", None)  # unminted -> synthesised on load
    loaded = pio.deserialize(payload)
    assert loaded.frame_tags == []
    ids = [n.layer_id for f in loaded.frames for n in f.layers]
    assert all(i > 0 for i in ids)
    assert len(ids) == len(set(ids))


def test_v1_flat_loads_with_empty_tags():
    payload = pio.serialize(Document(3, 3))
    payload["version"] = 1
    payload.pop("frame_tags", None)
    loaded = pio.deserialize(payload)
    assert loaded.frame_tags == []
    assert loaded.frames[0].layers[0].layer_id > 0


def test_missing_frame_tags_key_defaults_to_empty():
    payload = pio.serialize(Document(2, 2))
    payload.pop("frame_tags")
    loaded = pio.deserialize(payload)
    assert loaded.frame_tags == []


# --------------------------------------------------------------------------- #
# REQ-P5-DATA-003 — defensive validated tag load (SC-D003-1)                   #
# --------------------------------------------------------------------------- #


def _payload_with_tag(tag: Any) -> Dict[str, Any]:
    payload = _valid_payload()
    payload["frame_tags"] = [tag]
    return payload


@pytest.mark.parametrize(
    "tag",
    [
        {"name": "x", "from": 4, "to": 1, "mode": "loop"},  # inverted range
        {"name": "x", "from": 0, "to": 99, "mode": "loop"},  # out of range
        {"name": "x", "from": -1, "to": 2, "mode": "loop"},  # negative
        {"name": "x", "from": 0, "to": 1, "mode": "spin"},  # unknown mode
        {"name": "x", "from": 0, "to": 1, "mode": "loop", "repeat": -1},  # bad repeat
        {
            "name": "x",
            "from": 0,
            "to": 1,
            "mode": "loop",
            "repeat": True,
        },  # bool repeat
        {
            "name": "x",
            "from": 0,
            "to": 1,
            "mode": "loop",
            "color": "not-a-color",
        },  # bad colour
        {"name": "x", "from": 0, "mode": "loop"},  # missing 'to'
        {"name": 123, "from": 0, "to": 1, "mode": "loop"},  # bad name type
    ],
)
def test_defensive_tag_load_rejects_bad_tag(tag):
    with pytest.raises(ProjectIOError):
        pio.deserialize(_payload_with_tag(tag))


def test_malformed_tag_object_rejected():
    with pytest.raises(ProjectIOError):
        pio.deserialize(_payload_with_tag("not-a-dict"))


def test_non_list_frame_tags_container_rejected():
    payload = _valid_payload()
    payload["frame_tags"] = {"walk": [1, 4]}
    with pytest.raises(ProjectIOError):
        pio.deserialize(payload)


def test_load_does_not_clamp_out_of_range_tag(tmp_path):
    # Load rejects out-of-range tags rather than silently clamping them.
    payload = _payload_with_tag({"name": "x", "from": 0, "to": 10, "mode": "loop"})
    path = tmp_path / "bad.pixproj"
    import json

    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProjectIOError):
        pio.load_project(path)
