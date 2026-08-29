"""Tests for pixelart_creator.data.export_io (REQ-P7-DATA-001, -002, -004).

The portable, deterministic ``data/`` writers: :func:`write_export` writes the
engine's exact bytes + JSON verbatim (no re-encode — SC-D001-1), and
:func:`write_engine_preset` writes engine-ready Unity ``.meta`` and Godot ``.tres``
artifacts deterministically (SC-D002-1) whose structure a named engine's importer
consumes. Zero Qt; deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelart_creator.data.export_io import (
    ExportWriteError,
    write_engine_preset,
    write_export,
)
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportFormat,
    ExportRequest,
    SheetMetadata,
    SpriteRect,
    TagInfo,
    export_document,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def make_doc(colors, *, tag=None) -> Document:
    doc = Document(4, 4)
    doc.frames[0].layers[0].buffer.fill(colors[0])
    for color in colors[1:]:
        doc.add_frame().layers[0].buffer.fill(color)
    if tag is not None:
        name, lo, hi, mode = tag
        doc.make_add_tag_command(name, lo, hi, mode=mode).execute()
    return doc


def sheet_result(colors, *, tag=None):
    doc = make_doc(colors, tag=tag)
    return export_document(doc, ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=8))


# --------------------------------------------------------------------------- #
# SC-D001-1 — verbatim bytes + JSON, no re-encode                              #
# --------------------------------------------------------------------------- #


def test_write_export_writes_image_and_json_verbatim(tmp_path: Path) -> None:
    """REQ-P7-DATA-001: image bytes + JSON are written exactly as produced."""
    result = sheet_result([RED, GREEN])
    out = tmp_path / "sheet.png"
    write_export(result, out)
    assert out.read_bytes() == result.image_bytes
    json_path = out.with_suffix(".json")
    assert json_path.read_text(encoding="utf-8") == result.metadata_json


def test_write_export_png_has_no_json(tmp_path: Path) -> None:
    """REQ-P7-DATA-001: a PNG result (no metadata) writes only the image."""
    doc = make_doc([RED])
    result = export_document(doc, ExportRequest(fmt=ExportFormat.PNG))
    out = tmp_path / "sprite.png"
    write_export(result, out)
    assert out.read_bytes() == result.image_bytes
    assert not out.with_suffix(".json").exists()


def test_write_export_creates_missing_parent_dirs(tmp_path: Path) -> None:
    """REQ-P7-DATA-001: missing parent directories are created."""
    result = sheet_result([RED, GREEN])
    out = tmp_path / "nested" / "deep" / "sheet.png"
    write_export(result, out)
    assert out.exists() and out.read_bytes() == result.image_bytes


def test_write_export_accepts_str_path(tmp_path: Path) -> None:
    """REQ-P7-DATA-001: a str path works (portable pathlib handling)."""
    result = sheet_result([RED, GREEN])
    out = tmp_path / "sheet.png"
    write_export(result, str(out))
    assert out.read_bytes() == result.image_bytes


def test_write_export_is_byte_reproducible(tmp_path: Path) -> None:
    """REQ-P7-DATA-001: writing the same result twice yields identical files."""
    result = sheet_result([RED, GREEN, BLUE])
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    write_export(result, a)
    write_export(result, b)
    assert a.read_bytes() == b.read_bytes()
    assert a.with_suffix(".json").read_bytes() == b.with_suffix(".json").read_bytes()


# --------------------------------------------------------------------------- #
# SC-D002-1 — Unity .meta artifact                                             #
# --------------------------------------------------------------------------- #


def test_write_unity_meta_structure(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: the Unity .meta is Multiple-mode, Point filter, ppu=100."""
    result = sheet_result([RED, GREEN, BLUE])
    image_path = tmp_path / "spritesheet.png"
    write_export(result, image_path)
    write_engine_preset(EnginePreset.UNITY, result.metadata, image_path)

    meta_path = Path(str(image_path) + ".meta")
    text = meta_path.read_text(encoding="utf-8")
    assert "TextureImporter:" in text
    assert "spriteMode: 2" in text  # Multiple
    assert "filterMode: 0" in text  # Point
    assert "spritePixelsToUnits: 100" in text
    assert "textureCompression: 0" in text
    # One sprite rect per frame + a pivot.
    assert text.count("serializedVersion: 2") >= len(result.metadata.frames)
    assert "pivot: {x: 0.5, y: 0.5}" in text
    assert text.startswith("fileFormatVersion: 2")


def test_write_unity_meta_is_deterministic(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: the Unity .meta is byte-reproducible (content-hash GUID)."""
    result = sheet_result([RED, GREEN])
    p1 = tmp_path / "one.png"
    p2 = tmp_path / "two.png"
    write_engine_preset(EnginePreset.UNITY, result.metadata, p1)
    write_engine_preset(EnginePreset.UNITY, result.metadata, p2)
    assert Path(str(p1) + ".meta").read_text(encoding="utf-8") == Path(
        str(p2) + ".meta"
    ).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# SC-D002-1 — Godot SpriteFrames .tres artifact                                #
# --------------------------------------------------------------------------- #


def test_write_godot_tres_structure(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: the Godot .tres is a valid SpriteFrames with AtlasTextures."""
    result = sheet_result([RED, GREEN, BLUE])
    image_path = tmp_path / "spritesheet.png"
    write_export(result, image_path)
    write_engine_preset(EnginePreset.GODOT, result.metadata, image_path)

    tres = image_path.with_suffix(".tres")
    text = tres.read_text(encoding="utf-8")
    assert text.startswith('[gd_resource type="SpriteFrames"')
    assert "format=3" in text
    assert '[ext_resource type="Texture2D"' in text
    assert 'path="res://spritesheet.png"' in text
    assert text.count('[sub_resource type="AtlasTexture"') == len(
        result.metadata.frames
    )
    assert "region = Rect2(" in text
    assert "[resource]" in text and "animations = [" in text


def test_write_godot_tres_groups_by_tag(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: Phase-5 frameTags become named Godot animations."""
    result = sheet_result([RED, GREEN, BLUE], tag=("walk", 0, 2, PlaybackMode.LOOP))
    image_path = tmp_path / "spritesheet.png"
    write_engine_preset(EnginePreset.GODOT, result.metadata, image_path)
    text = image_path.with_suffix(".tres").read_text(encoding="utf-8")
    assert '&"walk"' in text


def test_write_godot_tres_synthetic_default_animation(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: with no tags a synthetic 'default' animation is emitted."""
    result = sheet_result([RED, GREEN])
    image_path = tmp_path / "spritesheet.png"
    write_engine_preset(EnginePreset.GODOT, result.metadata, image_path)
    text = image_path.with_suffix(".tres").read_text(encoding="utf-8")
    assert '&"default"' in text


def test_write_godot_tres_is_deterministic(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: the Godot .tres is byte-reproducible for identical inputs.

    The .tres embeds the image *filename* (res://<name>), so determinism is
    asserted for the same filename written in two separate directories."""
    result = sheet_result([RED, GREEN, BLUE])
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    p1 = tmp_path / "a" / "spritesheet.png"
    p2 = tmp_path / "b" / "spritesheet.png"
    write_engine_preset(EnginePreset.GODOT, result.metadata, p1)
    write_engine_preset(EnginePreset.GODOT, result.metadata, p2)
    assert p1.with_suffix(".tres").read_text(encoding="utf-8") == p2.with_suffix(
        ".tres"
    ).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Preset dispatch edge cases                                                   #
# --------------------------------------------------------------------------- #


def test_write_godot_tres_tolerates_tag_index_beyond_frames(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: a tag range overrunning the frame set is skipped safely.

    The Godot writer only emits frame entries for indices that exist in the sheet
    (a defensive guard) — an out-of-range index is skipped, not a crash."""
    meta = SheetMetadata(
        image_name="spritesheet.png",
        width=4,
        height=4,
        frames=(SpriteRect("0", 0, 0, 4, 4, 4, 4, 0, 0, 100),),
        tags=(TagInfo("over", 0, 3, "forward"),),  # 1..3 do not exist
    )
    image_path = tmp_path / "spritesheet.png"
    write_engine_preset(EnginePreset.GODOT, meta, image_path)
    text = image_path.with_suffix(".tres").read_text(encoding="utf-8")
    assert '&"over"' in text
    # Only the single existing frame's AtlasTexture is referenced.
    assert text.count("SubResource(") == 1


def test_write_engine_preset_none_writes_nothing(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: the NONE preset produces no artifact."""
    result = sheet_result([RED, GREEN])
    image_path = tmp_path / "spritesheet.png"
    write_engine_preset(EnginePreset.NONE, result.metadata, image_path)
    assert not Path(str(image_path) + ".meta").exists()
    assert not image_path.with_suffix(".tres").exists()


def test_write_engine_preset_unknown_raises(tmp_path: Path) -> None:
    """REQ-P7-DATA-002: an unknown preset value is a domain error."""
    result = sheet_result([RED, GREEN])
    with pytest.raises(ExportWriteError, match="unknown engine preset"):
        write_engine_preset("bogus", result.metadata, tmp_path / "x.png")  # type: ignore[arg-type]
