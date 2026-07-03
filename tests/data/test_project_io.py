"""Tests for pixelart_creator.data.project_io."""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.logic import constants
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def test_tuning_constants_single_sourced_from_constants():
    # Regression (T4, S12): project_io imports its tuning values from
    # logic.constants (no inlined zlib level 9 / duration 100 / palette cap 256).
    assert pio.PROJECT_ZLIB_LEVEL is constants.PROJECT_ZLIB_LEVEL
    assert pio.DEFAULT_FRAME_DURATION_MS is constants.DEFAULT_FRAME_DURATION_MS
    assert pio.MAX_PALETTE_SIZE == constants.MAX_PALETTE_SIZE
    assert constants.PROJECT_ZLIB_LEVEL == 9
    assert constants.DEFAULT_FRAME_DURATION_MS == 100
    assert constants.MAX_PALETTE_SIZE == 256


def test_missing_duration_defaults_to_constant():
    # Regression (T4): a frame with no "duration_ms" key falls back to the
    # single-sourced DEFAULT_FRAME_DURATION_MS on load.
    payload = pio.serialize(_sample_document())
    for frame in payload["frames"]:
        frame.pop("duration_ms", None)
    loaded = pio.deserialize(payload)
    assert loaded.frames[0].duration_ms == constants.DEFAULT_FRAME_DURATION_MS


def _sample_document():
    doc = Document(4, 3, palette=Palette([RED, BLUE]), metadata={"author": "juan"})
    doc.frames[0].layers[0].buffer.set_pixel(1, 1, RED)
    doc.add_layer("Ink")
    doc.add_frame(duration_ms=250)
    return doc


def test_roundtrip_preserves_everything(tmp_path):
    doc = _sample_document()
    path = pio.save_project(doc, tmp_path / "proj")
    assert path.suffix == ".pixproj"
    loaded = pio.load_project(path)
    assert loaded.width == 4 and loaded.height == 3
    assert loaded.mode is ColorMode.RGBA
    assert loaded.palette.colors() == [RED, BLUE]
    assert loaded.metadata["author"] == "juan"
    assert len(loaded.frames) == 2
    assert loaded.frames[1].duration_ms == 250
    assert loaded.frames[0].layers[0].buffer.get_pixel(1, 1) == RED
    assert loaded.frames[0].layers[1].name == "Ink"


def test_indexed_roundtrip(tmp_path):
    doc = Document(3, 3, mode=ColorMode.INDEXED, palette=Palette([RED]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, 5)
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "idx"))
    assert loaded.mode is ColorMode.INDEXED
    assert loaded.frames[0].layers[0].buffer.get_pixel(0, 0) == 5


def test_save_keeps_existing_suffix(tmp_path):
    doc = Document(2, 2)
    path = pio.save_project(doc, tmp_path / "keep.pixproj")
    assert path.name == "keep.pixproj"


def test_serialize_shape():
    payload = pio.serialize(Document(2, 2))
    assert payload["format"] == "pixproj"
    # Schema is now v4 (Phase-6 tilesets/tilemaps, ADR-0016); v1/v2/v3 still
    # load (back-compat).
    assert payload["version"] == 4
    assert payload["canvas"] == {"width": 2, "height": 2, "mode": "rgba"}


def _valid_payload():
    return pio.serialize(_sample_document())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.pop("format"),
        lambda p: p.update(format="other"),
        lambda p: p.update(version=99),
        lambda p: p.pop("canvas"),
        lambda p: p["canvas"].update(width=0),
        lambda p: p["canvas"].update(width=999999),
        lambda p: p["canvas"].update(mode="cmyk"),
        lambda p: p.update(palette="notalist"),
        lambda p: p.update(frames=[]),
        lambda p: p["frames"][0].update(layers=[]),
        lambda p: p["frames"][0].update(duration_ms=0),
        lambda p: p["frames"][0]["layers"][0].update(data="!!!notbase64"),
    ],
)
def test_deserialize_rejects_malformed(mutate):
    payload = _valid_payload()
    mutate(payload)
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_deserialize_rejects_wrong_payload_size():
    payload = _valid_payload()
    # Corrupt one layer's data to a valid-but-too-short buffer.
    other = pio.serialize(Document(2, 2))
    payload["frames"][0]["layers"][0]["data"] = other["frames"][0]["layers"][0]["data"]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_deserialize_rejects_bad_palette_entry():
    payload = _valid_payload()
    payload["palette"] = ["#GGGGGG"]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_deserialize_too_many_palette_colors():
    payload = _valid_payload()
    payload["palette"] = ["#FFFFFFFF"] * 300
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_load_missing_file(tmp_path):
    with pytest.raises(pio.ProjectIOError):
        pio.load_project(tmp_path / "nope.pixproj")


def test_load_invalid_json(tmp_path):
    bad = tmp_path / "bad.pixproj"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(pio.ProjectIOError):
        pio.load_project(bad)


def test_load_non_object_json(tmp_path):
    bad = tmp_path / "arr.pixproj"
    bad.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(pio.ProjectIOError):
        pio.load_project(bad)


def test_defaults_applied_for_optional_fields():
    payload = _valid_payload()
    del payload["metadata"]
    payload["frames"][0]["layers"][0].pop("visible", None)
    doc = pio.deserialize(payload)
    assert doc.metadata == {}
    assert doc.frames[0].layers[0].visible is True
