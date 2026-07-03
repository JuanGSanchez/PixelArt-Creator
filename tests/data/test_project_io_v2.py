"""Tests for the .pixproj schema-v2 layer model + v1 back-compat (T7/T8).

Covers pixelart_creator.data.project_io: the v2 round-trip (per-node attributes,
nested groups, mask bytes, smart-source index-path links), v1 back-compat (flat
NORMAL layers), and the defensive rejections that each raise
:class:`ProjectIOError`. No eval/exec paths.

Maps to REQ-P4-DATA-001..004 (serialisation + defensive load).
"""

from __future__ import annotations

import pytest

from pixelart_creator.data import project_io as pio
from pixelart_creator.logic.blend import BlendMode
from pixelart_creator.logic.constants import (
    MAX_GROUP_NESTING_DEPTH,
    MAX_LAYERS_PER_FRAME,
)
from pixelart_creator.logic.document import Document, Layer, LayerGroup
from pixelart_creator.logic.palette import Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
BLUE = (0, 0, 255, 255)


def _rich_document() -> Document:
    """A document exercising every v2 feature: attrs, group, mask, smart link."""
    doc = Document(4, 4, palette=Palette([RED, BLUE]), metadata={"author": "juan"})
    base = doc.frames[0].layers[0]
    base.buffer.set_pixel(1, 1, RED)
    base.opacity = 0.5
    base.blend_mode = BlendMode.MULTIPLY
    base.visible = False
    base.locked = True
    base.reference = True
    mask = PixelBuffer(4, 4)
    mask.set_pixel(0, 0, (10, 20, 30, 200))
    base.mask = mask

    # A nested group carrying its own blend mode.
    inner = Layer(PixelBuffer(4, 4), "inner")
    inner.buffer.set_pixel(2, 2, BLUE)
    group = LayerGroup("G", [inner], opacity=0.75, blend_mode=BlendMode.SCREEN)
    doc.frames[0].layers.append(group)

    # A smart layer mirroring the base layer (index path [0]).
    smart = Layer(PixelBuffer(4, 4), "smart", smart_source=base)
    doc.frames[0].layers.append(smart)
    return doc


# --------------------------------------------------------------------------- #
# v2 serialise shape + round-trip.                                            #
# --------------------------------------------------------------------------- #


def test_serialize_declares_version_2():
    payload = pio.serialize(Document(2, 2))
    assert payload["format"] == "pixproj"
    assert payload["version"] == 2
    node = payload["frames"][0]["layers"][0]
    assert node["type"] == "layer"
    assert node["blend_mode"] == "normal"


def test_v2_roundtrip_preserves_attributes(tmp_path):
    loaded = pio.load_project(pio.save_project(_rich_document(), tmp_path / "rich"))
    base = loaded.frames[0].layers[0]
    assert isinstance(base, Layer)
    assert base.opacity == 0.5
    assert base.blend_mode is BlendMode.MULTIPLY
    assert base.visible is False and base.locked is True and base.reference is True
    assert base.buffer.get_pixel(1, 1) == RED


def test_v2_roundtrip_preserves_nested_group(tmp_path):
    loaded = pio.load_project(pio.save_project(_rich_document(), tmp_path / "grp"))
    group = loaded.frames[0].layers[1]
    assert isinstance(group, LayerGroup)
    assert group.name == "G"
    assert group.opacity == 0.75 and group.blend_mode is BlendMode.SCREEN
    assert isinstance(group.children[0], Layer)
    assert group.children[0].buffer.get_pixel(2, 2) == BLUE


def test_v2_roundtrip_preserves_mask_bytes(tmp_path):
    loaded = pio.load_project(pio.save_project(_rich_document(), tmp_path / "mask"))
    base = loaded.frames[0].layers[0]
    assert base.mask is not None
    assert base.mask.get_pixel(0, 0) == (10, 20, 30, 200)


def test_v2_roundtrip_relinks_smart_source(tmp_path):
    loaded = pio.load_project(pio.save_project(_rich_document(), tmp_path / "smart"))
    base = loaded.frames[0].layers[0]
    smart = loaded.frames[0].layers[2]
    assert isinstance(smart, Layer)
    # The link is restored to the actual reconstructed base layer object.
    assert smart.smart_source is base


def test_v2_indexed_roundtrip(tmp_path):
    doc = Document(3, 3, mode=ColorMode.INDEXED, palette=Palette([RED]))
    doc.frames[0].layers[0].buffer.set_pixel(0, 0, 7)
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "idx"))
    assert loaded.mode is ColorMode.INDEXED
    assert loaded.frames[0].layers[0].buffer.get_pixel(0, 0) == 7


# --------------------------------------------------------------------------- #
# v1 back-compat.                                                             #
# --------------------------------------------------------------------------- #


def _v1_payload() -> dict:
    """Hand-build a legacy v1 payload: flat layers, no type/blend_mode/groups."""
    v2 = pio.serialize(Document(2, 2))
    layer = v2["frames"][0]["layers"][0]
    return {
        "format": "pixproj",
        "version": 1,
        "canvas": v2["canvas"],
        "palette": [],
        "metadata": {},
        "frames": [
            {
                "duration_ms": 100,
                "layers": [
                    {"name": "Old", "opacity": 0.5, "data": layer["data"]},
                ],
            }
        ],
    }


def test_v1_loads_flat_layers_as_normal_with_defaults():
    doc = pio.deserialize(_v1_payload())
    layer = doc.frames[0].layers[0]
    assert isinstance(layer, Layer)
    assert layer.name == "Old"
    assert layer.opacity == 0.5
    assert layer.blend_mode is BlendMode.NORMAL  # v1 has no blend mode
    assert layer.mask is None and layer.reference is False
    assert layer.visible is True and layer.locked is False


def test_v1_rejects_bad_opacity_type():
    payload = _v1_payload()
    payload["frames"][0]["layers"][0]["opacity"] = "high"
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


# --------------------------------------------------------------------------- #
# Defensive rejections (v2 path) — each raises ProjectIOError.                #
# --------------------------------------------------------------------------- #


def _valid_v2() -> dict:
    return pio.serialize(_rich_document())


@pytest.mark.parametrize(
    "mutate, _label",
    [
        (lambda p: p.update(version=3), "unknown version"),
        (lambda p: p.update(version="two"), "non-int version"),
        (lambda p: p["frames"][0]["layers"][0].update(type="doodad"), "bad node type"),
        (
            lambda p: p["frames"][0]["layers"][0].update(blend_mode="glow"),
            "non-BlendMode string",
        ),
        (
            lambda p: p["frames"][0]["layers"][0].update(blend_mode=5),
            "non-string blend mode",
        ),
        (lambda p: p["frames"][0]["layers"][0].update(opacity=1.5), "opacity > 1"),
        (lambda p: p["frames"][0]["layers"][0].update(opacity=-0.1), "opacity < 0"),
    ],
)
def test_v2_defensive_rejects(mutate, _label):
    payload = _valid_v2()
    mutate(payload)
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_dangling_smart_source():
    payload = _valid_v2()
    # Point the smart layer at a non-existent index path.
    smart = payload["frames"][0]["layers"][2]
    assert smart["smart_source"] is not None
    smart["smart_source"] = [99]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_smart_source_referencing_a_group():
    payload = _valid_v2()
    # Index 1 is the group node; a smart layer may not mirror a group.
    payload["frames"][0]["layers"][2]["smart_source"] = [1]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_non_list_smart_source():
    payload = _valid_v2()
    payload["frames"][0]["layers"][2]["smart_source"] = "layer0"
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_oversized_payload():
    payload = _valid_v2()
    # A wrong-size (too short) but valid base64 buffer for a 4x4 layer.
    small = pio.serialize(Document(2, 2))["frames"][0]["layers"][0]["data"]
    payload["frames"][0]["layers"][0]["data"] = small
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_over_max_nesting_depth():
    payload = _valid_v2()

    def _nested(depth: int) -> dict:
        node = {
            "type": "layer",
            "name": "leaf",
            "opacity": 1.0,
            "visible": True,
            "locked": False,
            "blend_mode": "normal",
            "reference": False,
            "mask": None,
            "data": payload["frames"][0]["layers"][0]["data"],
            "smart_source": None,
        }
        for _ in range(depth):
            node = {
                "type": "group",
                "name": "g",
                "opacity": 1.0,
                "visible": True,
                "locked": False,
                "blend_mode": "normal",
                "reference": False,
                "mask": None,
                "children": [node],
            }
        return node

    payload["frames"][0]["layers"] = [_nested(MAX_GROUP_NESTING_DEPTH + 1)]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_over_max_layers():
    payload = _valid_v2()
    one = payload["frames"][0]["layers"][0]
    # Reuse a plain leaf (drop the smart link) MAX+1 times.
    leaf = dict(one)
    leaf["smart_source"] = None
    payload["frames"][0]["layers"] = [
        dict(leaf) for _ in range(MAX_LAYERS_PER_FRAME + 1)
    ]
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_bad_mask_object():
    payload = _valid_v2()
    payload["frames"][0]["layers"][0]["mask"] = {"mode": "cmyk", "data": "AA=="}
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_v2_rejects_group_without_children_list():
    payload = _valid_v2()
    payload["frames"][0]["layers"][1].pop("children")
    with pytest.raises(pio.ProjectIOError):
        pio.deserialize(payload)


def test_no_eval_or_exec_in_source():
    # Security gate: the loader must never eval/exec untrusted project data.
    import inspect

    src = inspect.getsource(pio)
    assert "eval(" not in src
    assert "exec(" not in src


def test_load_roundtrip_deep_group_at_limit(tmp_path):
    # A group tree exactly at MAX_GROUP_NESTING_DEPTH round-trips cleanly.
    doc = Document(2, 2)
    node: LayerGroup = LayerGroup("g", [Layer(PixelBuffer(2, 2), "leaf")])
    for _ in range(MAX_GROUP_NESTING_DEPTH - 1):
        node = LayerGroup("g", [node])
    doc.frames[0].layers.append(node)
    loaded = pio.load_project(pio.save_project(doc, tmp_path / "deep"))
    assert isinstance(loaded.frames[0].layers[1], LayerGroup)
