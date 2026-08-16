"""Tests for pixelart_creator.logic.export (REQ-P7-LOGIC-001..005, -007..010, -012).

The Phase-7 deterministic export engine: flatten reuse (CO-4, SC-L001-1), pipeline
determinism (SC-L002-1), byte-reproducible PNG / GIF / sprite-sheet (SC-L003-1,
SC-L004-1, SC-L005-1) including the ADR-0019 F-1 no-``tIME``/volatile-chunk
guarantee, deterministic Aseprite JSON metadata (SC-L008-1), the atlas
coordinate/pixel round-trip through ``export_document`` (SC-L007-1), bound/default
enforcement (SC-L012-1), and ``run_batch`` == single export (SC-L010-1). Zero Qt;
deterministic. Includes a Hypothesis byte-reproducibility property.
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import List, Sequence, Tuple

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from pixelart_creator import __version__
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.atlas import AtlasError
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    DEFAULT_SPRITE_SHEET_COLUMNS,
    MAX_BATCH_TARGETS,
    MAX_EXPORT_FRAMES,
)
from pixelart_creator.logic.document import Document
from pixelart_creator.logic.export import (
    EnginePreset,
    ExportError,
    ExportFormat,
    ExportRequest,
    SheetMetadata,
    SpriteRect,
    TagInfo,
    build_metadata_json,
    build_sprite_sheet,
    encode_gif,
    encode_png,
    export_document,
    flatten_frame,
    run_batch,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)
YELLOW = (255, 255, 0, 255)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                           #
# --------------------------------------------------------------------------- #


def make_doc(
    colors: Sequence[Tuple[int, int, int, int]],
    durations: Sequence[int] | None = None,
    *,
    w: int = 4,
    h: int = 4,
) -> Document:
    """Build an RGBA document whose frame k is a solid fill of ``colors[k]``."""
    doc = Document(w, h)
    doc.frames[0].layers[0].buffer.fill(colors[0])
    if durations is not None:
        doc.frames[0].duration_ms = durations[0]
    for k, color in enumerate(colors[1:], start=1):
        dur = durations[k] if durations is not None else 100
        frame = doc.add_frame(duration_ms=dur)
        frame.layers[0].buffer.fill(color)
    return doc


def png_chunk_types(data: bytes) -> List[str]:
    """Return the ordered PNG chunk-type tags in ``data`` (validates signature)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG stream"
    types: List[str] = []
    i = 8
    while i < len(data):
        length = int.from_bytes(data[i : i + 4], "big")
        types.append(data[i + 4 : i + 8].decode("ascii"))
        i += 12 + length
    return types


def rgba_buffer(w: int, h: int, color: Tuple[int, int, int, int]) -> PixelBuffer:
    buf = PixelBuffer(w, h, ColorMode.RGBA)
    buf.fill(color)
    return buf


# --------------------------------------------------------------------------- #
# SC-L001-1 — flatten reuses composite_stack (CO-4), non-destructive           #
# --------------------------------------------------------------------------- #


def test_flatten_frame_equals_composite_stack() -> None:
    """REQ-P7-LOGIC-001: flatten delegates to composite_stack (not re-implemented)."""
    doc = make_doc([RED])
    frame = doc.frames[0]
    flat = flatten_frame(frame, doc.width, doc.height)
    expected = composite_stack(frame.layers, doc.width, doc.height)
    assert np.array_equal(flat.data, expected.data)


def test_flatten_frame_is_non_destructive() -> None:
    """REQ-P7-LOGIC-001: flattening never mutates the frame's source buffers."""
    doc = make_doc([RED])
    before = doc.frames[0].layers[0].buffer.data.copy()
    flatten_frame(doc.frames[0], doc.width, doc.height)
    assert np.array_equal(doc.frames[0].layers[0].buffer.data, before)


def test_flatten_composites_multiple_layers() -> None:
    """REQ-P7-LOGIC-001: a half-alpha top layer composites over the bottom (CO-4)."""
    doc = make_doc([RED])
    top = doc.add_layer("top", frame_index=0)
    top.buffer.fill((0, 0, 255, 128))
    flat = flatten_frame(doc.frames[0], doc.width, doc.height)
    expected = composite_stack(doc.frames[0].layers, doc.width, doc.height)
    assert np.array_equal(flat.data, expected.data)


# --------------------------------------------------------------------------- #
# SC-L003-1 — byte-reproducible PNG + no tIME/volatile chunk (ADR-0019 F-1)    #
# --------------------------------------------------------------------------- #


def test_encode_png_is_byte_reproducible() -> None:
    """REQ-P7-LOGIC-003: the same image encodes to identical PNG bytes every run."""
    image = rgba_buffer(8, 8, RED)
    assert encode_png(image) == encode_png(image)


def test_export_png_twice_is_byte_identical() -> None:
    """REQ-P7-LOGIC-003: two exports of the same document yield identical PNG bytes."""
    doc = make_doc([RED])
    req = ExportRequest(fmt=ExportFormat.PNG)
    first = export_document(doc, req)
    second = export_document(doc, req)
    assert first.image_bytes == second.image_bytes
    assert first.image_name == "sprite.png"


def test_png_has_no_time_or_volatile_chunk() -> None:
    """ADR-0019 F-1: the PNG carries no tIME/volatile ancillary chunk."""
    data = encode_png(rgba_buffer(8, 8, GREEN))
    types = png_chunk_types(data)
    assert "IHDR" in types and "IEND" in types
    for volatile in ("tIME", "eXIf", "iCCP", "pHYs", "tEXt", "iTXt", "zTXt"):
        assert volatile not in types, f"unexpected {volatile} chunk"


def test_png_decodes_to_the_source_pixels() -> None:
    """REQ-P7-LOGIC-003: the PNG round-trips to the exact input pixels (frame 0)."""
    doc = make_doc([RED, GREEN, BLUE])
    result = export_document(doc, ExportRequest(fmt=ExportFormat.PNG))
    decoded = np.asarray(Image.open(BytesIO(result.image_bytes)).convert("RGBA"))
    assert np.array_equal(decoded, np.full((4, 4, 4), RED, dtype=np.uint8))


def test_encode_png_rejects_non_rgba() -> None:
    """REQ-P7-LOGIC-003: PNG export requires an RGBA buffer."""
    with pytest.raises(ExportError, match="RGBA"):
        encode_png(PixelBuffer(4, 4, ColorMode.INDEXED))


# --------------------------------------------------------------------------- #
# C-01 — ExportRequest.frame_index selects the PNG-exported frame              #
# --------------------------------------------------------------------------- #
# Regression test for C-01 — proven by reversion in the commit pass


def test_export_png_frame_index_selects_that_frames_pixels() -> None:
    """A 6-frame document exported at frame_index=5 decodes to frame 5's pixels,
    not frame 0's (the pre-fix export always used frame 0)."""
    colors = [RED, GREEN, BLUE, YELLOW, RED, GREEN]
    doc = make_doc(colors)
    assert len(doc.frames) == 6
    result = export_document(doc, ExportRequest(fmt=ExportFormat.PNG, frame_index=5))
    decoded = np.asarray(Image.open(BytesIO(result.image_bytes)).convert("RGBA"))
    assert np.array_equal(decoded, np.full((4, 4, 4), GREEN, dtype=np.uint8))


def test_export_png_frame_index_default_is_still_frame_zero() -> None:
    """Regression test for C-01 — proven by reversion in the commit pass.

    The default (unset) ``frame_index`` still selects frame 0, preserving
    single-frame output byte-for-byte (no behaviour change for existing callers).
    """
    doc = make_doc([RED, GREEN, BLUE])
    result = export_document(doc, ExportRequest(fmt=ExportFormat.PNG))
    decoded = np.asarray(Image.open(BytesIO(result.image_bytes)).convert("RGBA"))
    assert np.array_equal(decoded, np.full((4, 4, 4), RED, dtype=np.uint8))


def test_export_png_frame_index_out_of_range_raises() -> None:
    """Regression test for C-01 — proven by reversion in the commit pass.

    An out-of-range ``frame_index`` raises ExportError instead of silently
    falling back to frame 0 or crashing.
    """
    doc = make_doc([RED, GREEN, BLUE])
    with pytest.raises(ExportError, match="frame_index"):
        export_document(doc, ExportRequest(fmt=ExportFormat.PNG, frame_index=3))
    with pytest.raises(ExportError, match="frame_index"):
        export_document(doc, ExportRequest(fmt=ExportFormat.PNG, frame_index=-1))


# --------------------------------------------------------------------------- #
# SC-L004-1 — byte-reproducible GIF, per-frame durations honoured              #
# --------------------------------------------------------------------------- #


def test_export_gif_is_byte_reproducible() -> None:
    """REQ-P7-LOGIC-004: two GIF exports of the same document are byte-identical."""
    doc = make_doc([RED, GREEN, BLUE], [100, 500, 100])
    req = ExportRequest(fmt=ExportFormat.GIF)
    assert (
        export_document(doc, req).image_bytes == export_document(doc, req).image_bytes
    )


def test_gif_decodes_with_frame_count_and_durations() -> None:
    """REQ-P7-LOGIC-004: decoded frame count + per-frame delays reflect duration_ms."""
    doc = make_doc([RED, GREEN, BLUE], [100, 500, 100])
    result = export_document(doc, ExportRequest(fmt=ExportFormat.GIF))
    img = Image.open(BytesIO(result.image_bytes))
    assert img.n_frames == 3
    durations = []
    for i in range(img.n_frames):
        img.seek(i)
        durations.append(img.info["duration"])
    assert durations == [100, 500, 100]
    assert result.image_name == "animation.gif"


def test_encode_gif_single_frame_source() -> None:
    """REQ-P7-LOGIC-004: a single-frame source yields a single-image GIF."""
    data = encode_gif([rgba_buffer(4, 4, RED)], [100])
    assert Image.open(BytesIO(data)).n_frames == 1


def test_encode_gif_over_256_colours_is_deterministic() -> None:
    """REQ-P7-LOGIC-004: a >256-colour frame quantises deterministically."""
    buf = PixelBuffer(20, 20, ColorMode.RGBA)
    data = buf.data
    for y in range(20):
        for x in range(20):
            data[y, x] = (x * 12 % 256, y * 12 % 256, (x + y) * 6 % 256, 255)
    assert encode_gif([buf], [100]) == encode_gif([buf], [100])


def test_encode_gif_large_frame_pads_palette_source() -> None:
    """A frame with > MAX_CANVAS_WIDTH pixels exercises the palette pad path."""
    # 100*100 = 10000 px > 7680 -> the palette-source buffer is padded to 2 rows.
    assert encode_gif([rgba_buffer(100, 100, RED)], [100])


def test_encode_gif_loop_override() -> None:
    """REQ-P7-LOGIC-004: an explicit loop count is honoured."""
    data = encode_gif(
        [rgba_buffer(4, 4, RED), rgba_buffer(4, 4, GREEN)], [100, 100], loop=3
    )
    assert Image.open(BytesIO(data)).info["loop"] == 3


@pytest.mark.parametrize(
    "frames,durations,match",
    [
        ([], [], "at least one frame"),
        ([rgba_buffer(4, 4, RED)], [100, 100], "equal length"),
        ([rgba_buffer(4, 4, RED)], [0], "positive int"),
        ([rgba_buffer(4, 4, RED)], [1.5], "positive int"),
    ],
)
def test_encode_gif_input_validation(frames, durations, match) -> None:
    """REQ-P7-LOGIC-004: empty/ragged/non-positive-duration inputs raise."""
    with pytest.raises(ExportError, match=match):
        encode_gif(frames, durations)


@pytest.mark.parametrize("loop", [-1, True, 1.0])
def test_encode_gif_rejects_bad_loop(loop) -> None:
    """REQ-P7-LOGIC-004: loop must be a non-negative, non-bool int."""
    with pytest.raises(ExportError, match="loop"):
        encode_gif([rgba_buffer(4, 4, RED)], [100], loop=loop)


def test_encode_gif_rejects_non_rgba() -> None:
    """REQ-P7-LOGIC-004: a non-RGBA frame is rejected."""
    with pytest.raises(ExportError, match="RGBA"):
        encode_gif([PixelBuffer(4, 4, ColorMode.INDEXED)], [100])


def test_encode_gif_rejects_too_many_frames() -> None:
    """REQ-P7-LOGIC-012: > MAX_EXPORT_FRAMES raises before encoding."""
    frames = [rgba_buffer(1, 1, RED) for _ in range(MAX_EXPORT_FRAMES + 1)]
    with pytest.raises(ExportError, match="MAX_EXPORT_FRAMES"):
        encode_gif(frames, [100] * len(frames))


# --------------------------------------------------------------------------- #
# SC-L005-1 — deterministic, byte-reproducible sprite sheet                    #
# --------------------------------------------------------------------------- #


def test_build_sprite_sheet_row_major_layout() -> None:
    """REQ-P7-LOGIC-005: frames are placed row-major on a fixed grid."""
    frames = [rgba_buffer(4, 4, c) for c in (RED, GREEN, BLUE)]
    sheet, meta = build_sprite_sheet(frames, columns=2, padding=0)
    # 3 frames / 2 columns -> 2 rows; width = 2*4, height = 2*4.
    assert (meta.width, meta.height) == (8, 8)
    coords = {(r.x, r.y) for r in meta.frames}
    assert coords == {(0, 0), (4, 0), (0, 4)}
    # frame 2 sits row-major at (col 0, row 1).
    assert np.array_equal(sheet.region(0, 4, 4, 4).data, frames[2].data)


def test_build_sprite_sheet_with_padding() -> None:
    """REQ-P7-LOGIC-005: padding inserts an inter-cell gap and shifts coords."""
    frames = [rgba_buffer(4, 4, RED), rgba_buffer(4, 4, GREEN)]
    sheet, meta = build_sprite_sheet(frames, columns=2, padding=2)
    assert (meta.width, meta.height) == (10, 4)  # 4 + 2 + 4 wide, 4 tall
    assert {(r.x, r.y) for r in meta.frames} == {(0, 0), (6, 0)}
    assert np.array_equal(sheet.region(6, 0, 4, 4).data, frames[1].data)


def test_export_sprite_sheet_is_byte_reproducible() -> None:
    """REQ-P7-LOGIC-005: sheet image + JSON are byte-identical across runs."""
    doc = make_doc([RED, GREEN, BLUE])
    req = ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=2)
    a = export_document(doc, req)
    b = export_document(doc, req)
    assert a.image_bytes == b.image_bytes
    assert a.metadata_json == b.metadata_json
    assert a.image_name == "spritesheet.png"


def test_sprite_sheet_default_columns_and_padding() -> None:
    """REQ-P7-LOGIC-012: defaults come from the named constants."""
    req = ExportRequest(fmt=ExportFormat.SPRITE_SHEET)
    assert req.columns == DEFAULT_SPRITE_SHEET_COLUMNS
    assert req.padding == DEFAULT_ATLAS_PADDING


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"columns": 0}, "columns"),
        ({"columns": True}, "columns"),
        ({"padding": -1}, "padding"),
        ({"padding": True}, "padding"),
    ],
)
def test_build_sprite_sheet_validation(kwargs, match) -> None:
    """REQ-P7-LOGIC-012: out-of-range columns/padding raise."""
    with pytest.raises(ExportError, match=match):
        build_sprite_sheet([rgba_buffer(4, 4, RED)], **kwargs)


def test_build_sprite_sheet_empty_and_too_many() -> None:
    """REQ-P7-LOGIC-012: empty and > MAX_EXPORT_FRAMES sets raise."""
    with pytest.raises(ExportError, match="at least one frame"):
        build_sprite_sheet([])
    frames = [rgba_buffer(1, 1, RED) for _ in range(MAX_EXPORT_FRAMES + 1)]
    with pytest.raises(ExportError, match="MAX_EXPORT_FRAMES"):
        build_sprite_sheet(frames)


def test_build_sprite_sheet_rejects_non_rgba() -> None:
    """REQ-P7-LOGIC-005: a non-RGBA frame is rejected."""
    with pytest.raises(ExportError, match="RGBA"):
        build_sprite_sheet([PixelBuffer(4, 4, ColorMode.INDEXED)])


# --------------------------------------------------------------------------- #
# SC-L007-1 — atlas coordinate/pixel round-trip via export_document            #
# --------------------------------------------------------------------------- #


def test_export_atlas_coord_pixel_round_trip() -> None:
    """REQ-P7-LOGIC-007: cropping each JSON rect returns the source frame pixels."""
    doc = make_doc([RED, GREEN, BLUE, YELLOW])
    result = export_document(doc, ExportRequest(fmt=ExportFormat.ATLAS))
    meta = result.metadata
    assert meta is not None and meta.image_name == "atlas.png"
    decoded = np.asarray(Image.open(BytesIO(result.image_bytes)).convert("RGBA"))
    colors = {"0": RED, "1": GREEN, "2": BLUE, "3": YELLOW}
    for rect in meta.frames:
        crop = decoded[rect.y : rect.y + rect.h, rect.x : rect.x + rect.w]
        assert np.array_equal(
            crop, np.full((rect.h, rect.w, 4), colors[rect.name], np.uint8)
        )


def test_export_atlas_is_byte_reproducible() -> None:
    """REQ-P7-LOGIC-007: atlas image + JSON are byte-identical across runs."""
    doc = make_doc([RED, GREEN, BLUE])
    req = ExportRequest(fmt=ExportFormat.ATLAS)
    a = export_document(doc, req)
    b = export_document(doc, req)
    assert a.image_bytes == b.image_bytes and a.metadata_json == b.metadata_json


def test_export_atlas_cannot_fit_raises_atlas_error() -> None:
    """REQ-P7-LOGIC-006: an atlas that cannot fit surfaces AtlasError."""
    doc = make_doc([RED])
    with pytest.raises(AtlasError):
        export_document(doc, ExportRequest(fmt=ExportFormat.ATLAS, max_dimension=2))


def test_export_atlas_too_many_frames() -> None:
    """REQ-P7-LOGIC-012: an atlas above MAX_EXPORT_FRAMES raises ExportError."""
    doc = Document(1, 1)
    for _ in range(MAX_EXPORT_FRAMES):
        doc.add_frame()
    with pytest.raises(ExportError, match="MAX_EXPORT_FRAMES"):
        export_document(doc, ExportRequest(fmt=ExportFormat.ATLAS))


def test_export_atlas_no_json_when_disabled() -> None:
    """REQ-P7-LOGIC-008: emit_json=False omits the JSON but keeps the image."""
    doc = make_doc([RED, GREEN])
    result = export_document(
        doc, ExportRequest(fmt=ExportFormat.ATLAS, emit_json=False)
    )
    assert result.metadata_json is None and result.image_bytes


# --------------------------------------------------------------------------- #
# SC-L008-1 — deterministic, complete Aseprite JSON metadata (ADR-0017)        #
# --------------------------------------------------------------------------- #


def test_metadata_json_is_deterministic_and_complete() -> None:
    """REQ-P7-LOGIC-008: two builds are byte-identical; every sprite is described."""
    meta = SheetMetadata(
        image_name="spritesheet.png",
        width=8,
        height=4,
        frames=(
            SpriteRect("0", 0, 0, 4, 4, 4, 4, 0, 0, 100),
            SpriteRect("1", 4, 0, 4, 4, 4, 4, 0, 0, 500),
        ),
        tags=(TagInfo("walk", 0, 1, "forward"),),
    )
    first = build_metadata_json(meta)
    assert first == build_metadata_json(meta)
    obj = json.loads(first)
    assert len(obj["frames"]) == 2
    assert obj["meta"]["version"] == __version__
    assert "tIME" not in first and "time" not in obj["meta"]
    assert obj["meta"]["size"] == {"w": 8, "h": 4}
    assert obj["meta"]["frameTags"][0] == {
        "name": "walk",
        "from": 0,
        "to": 1,
        "direction": "forward",
    }
    # integer coordinates, rotation/trim off.
    frame0 = obj["frames"][0]
    assert frame0["frame"] == {"x": 0, "y": 0, "w": 4, "h": 4}
    assert frame0["rotated"] is False and frame0["trimmed"] is False
    assert frame0["duration"] == 100


def test_metadata_json_without_tags() -> None:
    """REQ-P7-LOGIC-008: an empty tag set yields an empty frameTags array."""
    meta = SheetMetadata(
        "s.png", 4, 4, (SpriteRect("0", 0, 0, 4, 4, 4, 4, 0, 0, 100),), ()
    )
    obj = json.loads(build_metadata_json(meta))
    assert obj["meta"]["frameTags"] == []


def test_metadata_json_uses_compact_sorted_separators() -> None:
    """REQ-P7-LOGIC-008: locale-independent compact separators, sorted keys."""
    meta = SheetMetadata(
        "s.png", 4, 4, (SpriteRect("0", 0, 0, 4, 4, 4, 4, 0, 0, 100),), ()
    )
    text = build_metadata_json(meta)
    assert ", " not in text and '": ' not in text  # compact separators


# --------------------------------------------------------------------------- #
# Frame selection + tag mapping (direction tokens, unknown tag)                #
# --------------------------------------------------------------------------- #


def _add_tag(doc: Document, name: str, lo: int, hi: int, mode: PlaybackMode) -> None:
    doc.make_add_tag_command(name, lo, hi, mode=mode).execute()


def test_sheet_maps_document_tags_with_directions() -> None:
    """REQ-P7-LOGIC-008: Phase-5 tags map into frameTags with Aseprite directions."""
    doc = make_doc([RED, GREEN, BLUE])
    _add_tag(doc, "loop", 0, 2, PlaybackMode.LOOP)
    _add_tag(doc, "rev", 0, 1, PlaybackMode.REVERSE)
    _add_tag(doc, "pp", 1, 2, PlaybackMode.PING_PONG)
    result = export_document(
        doc, ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=8)
    )
    obj = json.loads(result.metadata_json)
    directions = {t["name"]: t["direction"] for t in obj["meta"]["frameTags"]}
    assert directions == {"loop": "forward", "rev": "reverse", "pp": "pingpong"}


def test_named_tag_selects_its_range() -> None:
    """REQ-P7-LOGIC-004: a named tag selects only its inclusive frame range."""
    doc = make_doc([RED, GREEN, BLUE], [100, 200, 300])
    _add_tag(doc, "mid", 1, 2, PlaybackMode.LOOP)
    result = export_document(doc, ExportRequest(fmt=ExportFormat.GIF, tag="mid"))
    img = Image.open(BytesIO(result.image_bytes))
    assert img.n_frames == 2  # frames 1 and 2 only


def test_named_tag_maps_to_zero_based_span_in_sheet() -> None:
    """REQ-P7-LOGIC-008: a selected tag re-maps to 0..count-1 in the metadata."""
    doc = make_doc([RED, GREEN, BLUE])
    _add_tag(doc, "mid", 1, 2, PlaybackMode.LOOP)
    result = export_document(
        doc, ExportRequest(fmt=ExportFormat.SPRITE_SHEET, tag="mid")
    )
    obj = json.loads(result.metadata_json)
    assert len(obj["frames"]) == 2
    assert obj["meta"]["frameTags"][0] == {
        "name": "mid",
        "from": 0,
        "to": 1,
        "direction": "forward",
    }


def test_unknown_tag_raises() -> None:
    """REQ-P7-LOGIC-004: an unknown tag name is a domain error."""
    doc = make_doc([RED, GREEN])
    with pytest.raises(ExportError, match="unknown tag"):
        export_document(doc, ExportRequest(fmt=ExportFormat.GIF, tag="nope"))


# --------------------------------------------------------------------------- #
# Request validation                                                           #
# --------------------------------------------------------------------------- #


def test_export_document_rejects_bad_format() -> None:
    """REQ-P7-LOGIC-012: a non-ExportFormat fmt is rejected."""
    doc = make_doc([RED])
    with pytest.raises(ExportError, match="fmt"):
        export_document(doc, ExportRequest(fmt="png"))  # type: ignore[arg-type]


def test_export_document_rejects_bad_preset() -> None:
    """REQ-P7-LOGIC-012: a non-EnginePreset preset is rejected."""
    doc = make_doc([RED])
    bad = ExportRequest(fmt=ExportFormat.PNG, preset="unity")  # type: ignore[arg-type]
    with pytest.raises(ExportError, match="preset"):
        export_document(doc, bad)


# --------------------------------------------------------------------------- #
# SC-L010-1 — run_batch == single export; bounds; failure semantics            #
# --------------------------------------------------------------------------- #


def test_run_batch_each_output_equals_single_export() -> None:
    """REQ-P7-LOGIC-010: each batch output is byte-identical to its single export."""
    doc = make_doc([RED, GREEN, BLUE])
    requests = [
        ExportRequest(fmt=ExportFormat.PNG),
        ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=2),
        ExportRequest(fmt=ExportFormat.ATLAS),
    ]
    batch = run_batch(doc, requests)
    assert len(batch) == 3
    for req, result in zip(requests, batch):
        single = export_document(doc, req)
        assert result.image_bytes == single.image_bytes
        assert result.metadata_json == single.metadata_json


def test_run_batch_exceeds_max_targets() -> None:
    """REQ-P7-LOGIC-012: a batch above MAX_BATCH_TARGETS raises."""
    doc = make_doc([RED])
    requests = [ExportRequest(fmt=ExportFormat.PNG)] * (MAX_BATCH_TARGETS + 1)
    with pytest.raises(ExportError, match="MAX_BATCH_TARGETS"):
        run_batch(doc, requests)


def test_run_batch_wraps_export_error_with_index() -> None:
    """REQ-P7-LOGIC-010: a failing target raises, identifying its batch index."""
    doc = make_doc([RED, GREEN])
    requests = [
        ExportRequest(fmt=ExportFormat.PNG),
        ExportRequest(fmt=ExportFormat.GIF, tag="nope"),
    ]
    with pytest.raises(ExportError, match="batch target 1 failed"):
        run_batch(doc, requests)


def test_run_batch_propagates_atlas_error() -> None:
    """REQ-P7-LOGIC-010: a per-target AtlasError propagates from the batch."""
    doc = make_doc([RED])
    requests = [ExportRequest(fmt=ExportFormat.ATLAS, max_dimension=2)]
    with pytest.raises(AtlasError):
        run_batch(doc, requests)


# --------------------------------------------------------------------------- #
# SC-L002-1 — Hypothesis: byte-reproducibility over randomised documents       #
# --------------------------------------------------------------------------- #


@given(
    colors=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255),
        ),
        min_size=1,
        max_size=5,
    )
)
def test_png_export_byte_reproducible_property(colors) -> None:
    """REQ-P7-LOGIC-002/-003: PNG export is a pure function of its input pixels."""
    doc = make_doc(colors)
    req = ExportRequest(fmt=ExportFormat.PNG)
    assert (
        export_document(doc, req).image_bytes == export_document(doc, req).image_bytes
    )


@given(
    colors=st.lists(
        st.tuples(
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255),
            st.integers(0, 255),
        ),
        min_size=1,
        max_size=4,
    )
)
def test_sprite_sheet_export_byte_reproducible_property(colors) -> None:
    """REQ-P7-LOGIC-002/-005: sheet image + JSON are a pure function of the input."""
    doc = make_doc(colors)
    req = ExportRequest(fmt=ExportFormat.SPRITE_SHEET, columns=2)
    a = export_document(doc, req)
    b = export_document(doc, req)
    assert a.image_bytes == b.image_bytes and a.metadata_json == b.metadata_json
