"""Tests for pixelart_creator.data.reference_board_io — .pixboard persistence.

REQ-P9-DATA-002 (SC-UI-006-1): save_board -> load_board round-trips a
ReferenceBoardLayout to an equal layout ({image ref, transform, crop, z-order} +
pan/zoom). Defensive load (IO-3): malformed / unknown-version / oversized /
mistyped files raise ReferenceBoardIOError (never eval, never crash). The board
model is pure (no Qt). Zero Qt.
"""

from __future__ import annotations

import json

import pytest

from pixelart_creator.data import reference_board_io as rio
from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.data.reference_board_io import (
    REFERENCE_BOARD_SCHEMA_VERSION,
    ReferenceBoardIOError,
    ReferenceBoardLayout,
    ReferenceImageEntry,
)
from pixelart_creator.logic import constants


def _entry(z=0, image="ref.png"):
    return ReferenceImageEntry(
        image=image,
        transform=(1.0, 0.0, 0.0, 1.0, 10.0, 20.0),
        crop=(0.0, 0.0, 100.0, 80.0),
        z_order=z,
    )


def _layout(n=2):
    return ReferenceBoardLayout(
        pan=(5.0, -3.0),
        zoom=1.5,
        images=tuple(_entry(z=k, image=f"img{k}.png") for k in range(n)),
    )


# --------------------------------------------------------------------------- #
# Model validation                                                            #
# --------------------------------------------------------------------------- #


def test_entry_coerces_floats():
    e = ReferenceImageEntry(
        image="a.png",
        transform=(1, 0, 0, 1, 0, 0),
        crop=(0, 0, 10, 10),
        z_order=3,
    )
    assert all(isinstance(v, float) for v in e.transform)
    assert all(isinstance(v, float) for v in e.crop)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"image": ""},  # empty
        {"image": 123},  # not a str
        {"transform": (1.0, 0.0, 0.0)},  # wrong length
        {"transform": (1, 0, 0, 1, 0, "x")},  # non-numeric
        {"crop": (0.0, 0.0, -1.0, 10.0)},  # negative width
        {"crop": (0.0, 0.0, 10.0, -1.0)},  # negative height
        {"z_order": 1.5},  # not int
        {"z_order": True},  # bool
    ],
)
def test_entry_rejects_invalid(kwargs):
    base = dict(
        image="a.png",
        transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        crop=(0.0, 0.0, 10.0, 10.0),
        z_order=0,
    )
    base.update(kwargs)
    with pytest.raises(ReferenceBoardIOError):
        ReferenceImageEntry(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"schema_version": 1},  # not a str
        {"pan": (0.0,)},  # wrong length
        {"zoom": 0.0},  # not > 0
        {"zoom": -1.0},
        {"zoom": "x"},  # not a number
    ],
)
def test_layout_rejects_invalid(kwargs):
    with pytest.raises(ReferenceBoardIOError):
        ReferenceBoardLayout(**kwargs)  # type: ignore[arg-type]


def test_layout_rejects_too_many_images():
    images = tuple(_entry(z=k) for k in range(constants.MAX_REFERENCE_IMAGES + 1))
    with pytest.raises(ReferenceBoardIOError):
        ReferenceBoardLayout(images=images)


def test_layout_rejects_non_entry():
    with pytest.raises(ReferenceBoardIOError):
        ReferenceBoardLayout(images=("nope",))  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Round-trip identity                                                          #
# --------------------------------------------------------------------------- #


def test_save_then_load_round_trips(tmp_path):
    layout = _layout(3)
    written = rio.save_board(layout, tmp_path / "b")
    assert written.suffix == rio.FILE_SUFFIX
    assert written.exists()
    loaded = rio.load_board(written)
    assert loaded == layout


def test_round_trip_preserves_transform_crop_zorder(tmp_path):
    layout = ReferenceBoardLayout(
        images=(
            ReferenceImageEntry(
                image="hero.png",
                transform=(2.0, 0.5, -0.5, 2.0, 100.0, 200.0),
                crop=(4.0, 5.0, 64.0, 48.0),
                z_order=7,
            ),
        )
    )
    loaded = rio.load_board(rio.save_board(layout, tmp_path / "t"))
    e = loaded.images[0]
    assert e.image == "hero.png"
    assert e.transform == (2.0, 0.5, -0.5, 2.0, 100.0, 200.0)
    assert e.crop == (4.0, 5.0, 64.0, 48.0)
    assert e.z_order == 7


def test_empty_board_round_trips(tmp_path):
    layout = ReferenceBoardLayout()
    loaded = rio.load_board(rio.save_board(layout, tmp_path / "empty"))
    assert loaded == layout


def test_save_accepts_str_path(tmp_path):
    assert rio.save_board(_layout(1), str(tmp_path / "s")).exists()


def test_serialize_shape():
    payload = rio.serialize(_layout(1))
    assert payload["format"] == rio.FORMAT_NAME
    assert payload["schema_version"] == REFERENCE_BOARD_SCHEMA_VERSION
    assert payload["pan"] == [5.0, -3.0]
    assert payload["images"][0]["z_order"] == 0


def test_serialize_rejects_non_layout():
    with pytest.raises(ReferenceBoardIOError):
        rio.serialize({"not": "a layout"})  # type: ignore[arg-type]


def test_error_is_a_project_io_error():
    assert issubclass(ReferenceBoardIOError, ProjectIOError)


# --------------------------------------------------------------------------- #
# Defensive deserialise                                                        #
# --------------------------------------------------------------------------- #


def _valid_payload():
    return {
        "format": rio.FORMAT_NAME,
        "schema_version": REFERENCE_BOARD_SCHEMA_VERSION,
        "pan": [0.0, 0.0],
        "zoom": 1.0,
        "images": [
            {
                "image": "a.png",
                "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
                "crop": [0.0, 0.0, 10.0, 10.0],
                "z_order": 0,
            }
        ],
    }


def test_deserialize_accepts_valid_payload():
    layout = rio.deserialize(_valid_payload())
    assert layout.images[0].image == "a.png"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: "not a dict",
        lambda p: p.pop("format"),
        lambda p: p.update(format="other"),
        lambda p: p.pop("schema_version"),
        lambda p: p.update(schema_version=1),
        lambda p: p.update(schema_version="999"),  # unsupported
        lambda p: p.update(pan="nope"),
        lambda p: p.update(pan=[0.0]),  # wrong length
        lambda p: p.update(zoom="x"),
        lambda p: p.update(images="not a list"),
        lambda p: p.update(images=["not a dict"]),
        lambda p: p["images"][0].update(image=""),  # empty image
        lambda p: p["images"][0].update(transform=[1.0, 0.0]),  # bad transform
        lambda p: p["images"][0].update(crop=[0.0, 0.0, 10.0]),  # bad crop
        lambda p: p["images"][0].update(z_order="x"),  # bad z-order
        lambda p: p["images"][0].update(z_order=True),  # bool z-order
    ],
)
def test_deserialize_rejects_malformed(mutate):
    payload = _valid_payload()
    mutated = mutate(payload)
    target = mutated if mutated is not None else payload
    with pytest.raises(ReferenceBoardIOError):
        rio.deserialize(target)


def test_deserialize_rejects_oversized_image_list():
    payload = _valid_payload()
    payload["images"] = [
        {
            "image": f"img{k}.png",
            "transform": [1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            "crop": [0.0, 0.0, 10.0, 10.0],
            "z_order": k,
        }
        for k in range(constants.MAX_REFERENCE_IMAGES + 1)
    ]
    with pytest.raises(ReferenceBoardIOError):
        rio.deserialize(payload)


def test_load_rejects_invalid_json(tmp_path):
    path = tmp_path / "bad.pixboard"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ReferenceBoardIOError):
        rio.load_board(path)


def test_load_rejects_missing_file(tmp_path):
    with pytest.raises(ReferenceBoardIOError):
        rio.load_board(tmp_path / "nope.pixboard")


def test_load_never_evals_payload(tmp_path):
    path = tmp_path / "evil.pixboard"
    path.write_text(
        json.dumps("__import__('os').system('echo pwned')"), encoding="utf-8"
    )
    with pytest.raises(ReferenceBoardIOError):
        rio.load_board(path)
