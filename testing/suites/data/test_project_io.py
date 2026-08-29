"""Tests for pixelart_creator.data.project_io."""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.logic import constants
from pixelart_creator.logic.doc_transform import (
    DocumentTransformRun,
    enumerate_targets,
    make_document_transform_command,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.rotsprite import rotsprite
from pixelart_creator.logic.transform import (
    flip_horizontal,
    rotate_90_cw,
    scale_nearest,
)

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


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
    # Schema tracks the FORMAT_VERSION constant, not a literal (v5 adds
    # Document.ppi, ADR-0025; v6 adds the optional "asset_refs" root array,
    # ADR-0058; earlier versions still load back-compat). Pinning to the
    # constant, and only the constant, stops this assertion going stale on the
    # next bump (the redundant `assert pio.FORMAT_VERSION == <N>` this line
    # used to carry alongside it was dropped 2026-08-21 for exactly that
    # reason -- T19 addendum).
    assert payload["version"] == pio.FORMAT_VERSION
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


# =========================================================================
# REQ-CSD-DATA-001..004: whole-document geometry round-trips
# (canvas-scale-defects spec.md / tasks.md T17)
#
# Every scenario here asserts PIXEL IDENTITY, never merely the absence of
# a ProjectIOError -- rotate-90 preserves the byte count of a 64x48 RGBA
# buffer (64*48*4 == 48*64*4 == 12,288), so a round-trip asserting only
# "no exception" PASSES against a document whose sibling layers were
# reshaped at the wrong row stride while the active layer alone was
# rotated. `data/project_io.py` is not edited by this batch (plan.md
# Section 4.1); these prove a consequence of the doc_transform fix, not a
# format change.
# =========================================================================


def _fill_distinct(buf: PixelBuffer, seed: int) -> None:
    """Fill every pixel with a value unique to (x, y, seed) -- so a wrong row
    stride or a cross-layer mixup shows up as a pixel-identity failure."""
    for y in range(buf.height):
        for x in range(buf.width):
            buf.set_pixel(
                x,
                y,
                (
                    (x * 7 + seed) % 256,
                    (y * 13 + seed) % 256,
                    (x + y + seed * 3) % 256,
                    255,
                ),
            )


def _document_two_frames_two_layers(width: int = 64, height: int = 48) -> Document:
    doc = Document(width, height)
    doc.add_layer(frame_index=0)
    doc.add_frame()
    doc.add_layer(frame_index=1)
    seed = 0
    for frame in doc.frames:
        for layer in frame.layers:
            _fill_distinct(layer.buffer, seed)
            seed += 1
    return doc


def _apply_whole_document_transform(
    doc: Document, transform, new_width: int, new_height: int
) -> None:
    """Drive the fixed doc_transform engine exactly as the UI action does:
    enumerate every target, resample each with `transform`, then commit."""
    run = DocumentTransformRun(enumerate_targets(doc))
    while not run.finished:
        run.step(transform)
    make_document_transform_command(doc, run, new_width, new_height).execute()


class TestScCsdD001Scale:
    """SC-CSD-D001-1: a scaled document round-trips through pxproj.

    DEFECT: proven to fail pre-fix in a scratch reconstruction (AGT-04
    report) -- "layer payload is 12288 bytes, expected 49152" -- because the
    pre-fix seam resampled only the active layer while declaring the new
    document dimensions for all of them. Not re-provable here without
    editing product code: the whole-document engine this test drives did
    not exist pre-fix.
    """

    def test_sc_csd_d001_1_save_load_after_scale_is_pixel_identical(self, tmp_path):
        doc = _document_two_frames_two_layers(64, 48)
        for frame in doc.frames:
            for layer in frame.layers:
                assert layer.buffer.width == 64 and layer.buffer.height == 48
                assert layer.buffer.data.nbytes == 12_288

        expected_by_layer = [
            [layer.buffer.copy() for layer in frame.layers] for frame in doc.frames
        ]

        _apply_whole_document_transform(
            doc, lambda buf: scale_nearest(buf, 128, 96), 128, 96
        )
        for frame_idx, frame in enumerate(doc.frames):
            for layer_idx, layer in enumerate(frame.layers):
                expected = scale_nearest(
                    expected_by_layer[frame_idx][layer_idx], 128, 96
                )
                assert layer.buffer == expected

        path = pio.save_project(doc, tmp_path / "scaled")
        loaded = pio.load_project(path)  # must raise no ProjectIOError

        assert loaded.width == 128 and loaded.height == 96
        for frame_idx, frame in enumerate(loaded.frames):
            for layer_idx, layer in enumerate(frame.layers):
                assert layer.buffer.width == 128 and layer.buffer.height == 96
                assert layer.buffer == doc.frames[frame_idx].layers[layer_idx].buffer


class TestScCsdD002Rotate90:
    """SC-CSD-D002-1: a rotated document round-trips through pxproj, PIXEL-identical.

    DEFECT: proven to fail pre-fix in a scratch reconstruction (AGT-04
    report). Against the pre-fix seam the load SUCCEEDS (64*48*4 ==
    48*64*4 == 12,288 bytes, so the decoder's length check cannot catch
    it) while the sibling layers are silently scrambled -- only the
    pixel-identity assertions below would have failed. An "assert no
    ProjectIOError" test alone is explicitly insufficient (spec.md Section 1.4).
    """

    def test_sc_csd_d002_1_save_load_after_rotate_90_is_pixel_identical(self, tmp_path):
        doc = Document(64, 48)
        doc.add_layer(frame_index=0)
        doc.add_frame()
        doc.add_layer(frame_index=1)
        _fill_distinct(doc.frames[0].layers[0].buffer, 1)
        _fill_distinct(doc.frames[0].layers[1].buffer, 2)
        # the non-active layer of frame 2 (index 1): fully transparent except
        # one marker pixel, so "exactly one non-transparent pixel" is checkable.
        sibling = doc.frames[1].layers[1].buffer
        for y in range(sibling.height):
            for x in range(sibling.width):
                sibling.set_pixel(x, y, TRANSPARENT)
        sibling.set_pixel(63, 0, BLUE)
        _fill_distinct(doc.frames[1].layers[0].buffer, 4)

        expected_by_layer = [
            [layer.buffer.copy() for layer in frame.layers] for frame in doc.frames
        ]

        _apply_whole_document_transform(doc, rotate_90_cw, 48, 64)

        path = pio.save_project(doc, tmp_path / "rotated")
        loaded = pio.load_project(path)  # must raise no ProjectIOError

        assert loaded.width == 48 and loaded.height == 64
        for frame_idx, frame in enumerate(loaded.frames):
            for layer_idx, layer in enumerate(frame.layers):
                assert layer.buffer.width == 48 and layer.buffer.height == 64
                expected = rotate_90_cw(expected_by_layer[frame_idx][layer_idx])
                assert layer.buffer == expected

        loaded_sibling = loaded.frames[1].layers[1].buffer
        non_transparent = [
            (x, y)
            for y in range(loaded_sibling.height)
            for x in range(loaded_sibling.width)
            if loaded_sibling.get_pixel(x, y) != TRANSPARENT
        ]
        assert len(non_transparent) == 1
        assert loaded_sibling.get_pixel(*non_transparent[0]) == BLUE


class TestScCsdD003RotSprite:
    """SC-CSD-D003-1: RotSprite continues to round-trip through pxproj.

    GUARD -- passes today, must keep passing. RotSprite was already applied
    per-layer (dimension-preserving) and never depended on the shared
    single-buffer geometry seam this batch fixes, so its round-trip is
    unaffected; no pre-fix failure is manufactured for it.
    """

    def test_sc_csd_d003_1_save_load_after_rotsprite_is_pixel_identical(self, tmp_path):
        doc = _document_two_frames_two_layers(64, 48)
        for frame in doc.frames:
            for layer in frame.layers:
                layer.buffer = rotsprite(layer.buffer, 30.0)

        expected_by_layer = [
            [layer.buffer.copy() for layer in frame.layers] for frame in doc.frames
        ]

        path = pio.save_project(doc, tmp_path / "rotsprited")
        loaded = pio.load_project(path)  # must raise no ProjectIOError

        assert loaded.width == 64 and loaded.height == 48
        for frame_idx, frame in enumerate(loaded.frames):
            for layer_idx, layer in enumerate(frame.layers):
                assert layer.buffer.width == 64 and layer.buffer.height == 48
                assert layer.buffer == expected_by_layer[frame_idx][layer_idx]


class TestScCsdD004Flip:
    """SC-CSD-D004-1: a flipped document round-trips through pxproj, pixel-identical.

    GUARD -- passes today. A flip preserves every payload length at every
    aspect ratio, so the decoder's length check can never be tripped here;
    there is no corruption to prove absent, and no pre-fix failure is
    manufactured for this row.
    """

    def test_sc_csd_d004_1_save_load_after_flip_is_pixel_identical(self, tmp_path):
        doc = _document_two_frames_two_layers(64, 48)
        expected_by_layer = [
            [layer.buffer.copy() for layer in frame.layers] for frame in doc.frames
        ]

        _apply_whole_document_transform(doc, flip_horizontal, 64, 48)

        path = pio.save_project(doc, tmp_path / "flipped")
        loaded = pio.load_project(path)  # must raise no ProjectIOError

        assert loaded.width == 64 and loaded.height == 48
        for frame_idx, frame in enumerate(loaded.frames):
            for layer_idx, layer in enumerate(frame.layers):
                assert layer.buffer.width == 64 and layer.buffer.height == 48
                expected = flip_horizontal(expected_by_layer[frame_idx][layer_idx])
                assert layer.buffer == expected
