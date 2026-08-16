"""Deterministic, headless export engine — PNG / GIF / sprite-sheet / atlas + JSON.

This is the pure, Qt-free (S11, Article I) export pipeline the GUI and the CLI
**both** call, so their output is byte-identical (REQ-P7-LOGIC-009/-013). Every
stage is a deterministic function of its inputs — no wall-clock, no randomness, no
locale-dependent formatting, frames iterated in explicit index order
(REQ-P7-LOGIC-002, ADR-0019) — which is what makes the raster/JSON output
byte-reproducible for a fixed input.

Composition, not re-implementation (Article I): frames are flattened via
:func:`~pixelart_creator.logic.blend.composite_stack` (CO-4, non-destructive over
the source :class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`, PB-1); the
GIF shared palette is built by :func:`~pixelart_creator.logic.quantize.median_cut`
(shipped, deterministic); the atlas is packed by
:func:`~pixelart_creator.logic.atlas.pack_atlas` over CP-1. The metadata builder
lives here (never in ``atlas``) so ``atlas`` needs no ``export`` import — the
import graph stays one-way and acyclic (``export -> atlas -> compactor``,
``export -> blend``/``document``/``quantize``/``animation``, PL7-D3).

Encoder options are pinned for byte-reproducibility per ADR-0019 (PNG:
``optimize=False`` + a pinned ``PNG_EXPORT_COMPRESS_LEVEL``,
no volatile chunks; GIF: fixed shared palette + ``dither=NONE`` + ``optimize=False``
+ per-frame ``duration`` from ``Frame.duration_ms``). The JSON is the Aseprite
*Array* layout (ADR-0017), rotation-free, trim-off. Pillow enum values, format
strings, and the app version are module-local wire-format identifiers (ADR-0001).
All numeric bounds/defaults come from ``logic/constants.py`` (S12).
"""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, replace
from io import BytesIO
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from pixelart_creator import __version__
from pixelart_creator.logic.animation import PlaybackMode
from pixelart_creator.logic.atlas import AtlasError, pack_atlas
from pixelart_creator.logic.blend import composite_stack
from pixelart_creator.logic.constants import (
    DEFAULT_ATLAS_PADDING,
    DEFAULT_SPRITE_SHEET_COLUMNS,
    GIF_DEFAULT_LOOP_COUNT,
    GIF_FRAME_DISPOSAL,
    MAX_ATLAS_DIMENSION,
    MAX_BATCH_TARGETS,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_EXPORT_FRAMES,
    MAX_PALETTE_SIZE,
    PNG_EXPORT_COMPRESS_LEVEL,
)
from pixelart_creator.logic.document import Document, Frame
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.quantize import median_cut

__all__ = [
    "ExportError",
    "ExportFormat",
    "EnginePreset",
    "SpriteRect",
    "TagInfo",
    "SheetMetadata",
    "ExportRequest",
    "ExportResult",
    "flatten_frame",
    "encode_png",
    "encode_gif",
    "build_sprite_sheet",
    "build_metadata_json",
    "export_document",
    "run_batch",
]

# --- Wire-format identifiers (module-local, ADR-0001 — like the Tiled version) ---
_JSON_APP = "pixelart-creator"
_JSON_FORMAT = "RGBA8888"
_JSON_SCALE = "1"
_ROTATED = False
_TRIMMED = False

#: Canonical output filenames per format (deterministic; referenced by the JSON
#: ``meta.image`` field and by the engine-preset writers so GUI==CLI bytes agree).
_IMAGE_NAME_PNG = "sprite.png"
_IMAGE_NAME_GIF = "animation.gif"
_IMAGE_NAME_SHEET = "spritesheet.png"
_IMAGE_NAME_ATLAS = "atlas.png"

#: PlaybackMode -> Aseprite frameTags ``direction`` token (ADR-0017).
_DIRECTION_BY_MODE: Dict[PlaybackMode, str] = {
    PlaybackMode.LOOP: "forward",
    PlaybackMode.ONCE: "forward",
    PlaybackMode.REVERSE: "reverse",
    PlaybackMode.PING_PONG: "pingpong",
}


class ExportError(ValueError):
    """Raised on an invalid export request, bound breach, or encode failure."""


class ExportFormat(enum.Enum):
    """The supported export formats (module-local enumerated vocabulary, BF-2)."""

    PNG = "png"
    GIF = "gif"
    SPRITE_SHEET = "sprite-sheet"
    ATLAS = "atlas"


class EnginePreset(enum.Enum):
    """The supported engine presets (module-local vocabulary, BF-2).

    REQ-P7-LOGIC-011.
    """

    NONE = "none"
    UNITY = "unity"
    GODOT = "godot"


@dataclass(frozen=True)
class SpriteRect:
    """One frame/sprite's rect on the sheet/atlas plus its source geometry.

    Coordinates are integers (byte-reproducible JSON, ADR-0017). With trim OFF
    (this phase) ``offset_x``/``offset_y`` are ``0`` and ``source_w``/``source_h``
    equal ``w``/``h`` — so the coordinate/pixel round-trip is exact.
    """

    name: str
    x: int
    y: int
    w: int
    h: int
    source_w: int
    source_h: int
    offset_x: int
    offset_y: int
    duration_ms: int


@dataclass(frozen=True)
class TagInfo:
    """A named animation range mapped into the exported frame sequence.

    ``from_index``/``to_index`` are indices into :attr:`SheetMetadata.frames`;
    ``direction`` is the Aseprite token derived from the tag's ``PlaybackMode``.
    """

    name: str
    from_index: int
    to_index: int
    direction: str


@dataclass(frozen=True)
class SheetMetadata:
    """Structured sprite-sheet / atlas metadata (fed to the engine-preset writers).

    REQ-P7-LOGIC-011.
    """

    image_name: str
    width: int
    height: int
    frames: Tuple[SpriteRect, ...]
    tags: Tuple[TagInfo, ...]


@dataclass(frozen=True)
class ExportRequest:
    """An immutable export request: a format + parameters + a frame source."""

    fmt: ExportFormat
    preset: EnginePreset = EnginePreset.NONE
    columns: int = DEFAULT_SPRITE_SHEET_COLUMNS
    padding: int = DEFAULT_ATLAS_PADDING
    max_dimension: int = MAX_ATLAS_DIMENSION
    loop: int = GIF_DEFAULT_LOOP_COUNT
    tag: Optional[str] = None
    emit_json: bool = True
    frame_index: int = 0


@dataclass(frozen=True)
class ExportResult:
    """The exact exported bytes plus (for sheet/atlas) the metadata."""

    image_bytes: bytes
    image_name: str
    metadata_json: Optional[str]
    metadata: Optional[SheetMetadata]


# --------------------------------------------------------------------------- #
# Flatten (CO-4 reuse, non-destructive)                                        #
# --------------------------------------------------------------------------- #


def flatten_frame(frame: Frame, width: int, height: int) -> PixelBuffer:
    """Flatten one frame's visible layer stack to a single RGBA buffer (CO-4).

    Delegates to :func:`~pixelart_creator.logic.blend.composite_stack` — the
    export engine never re-implements compositing (Article I) and never mutates
    the frame's source buffers (non-destructive, REQ-P7-LOGIC-001).

    Raises:
        BlendError: If a layer buffer geometry is wrong (propagated from CO-4).
    """
    return composite_stack(frame.layers, width, height)


# --------------------------------------------------------------------------- #
# Raster encoders (byte-reproducible, ADR-0019)                                #
# --------------------------------------------------------------------------- #


def _require_rgba(image: PixelBuffer, what: str) -> None:
    if image.mode is not ColorMode.RGBA:
        raise ExportError(f"{what} requires an RGBA buffer, got {image.mode.value}")


def encode_png(image: PixelBuffer) -> bytes:
    """Encode a flat RGBA image to byte-reproducible PNG bytes (ADR-0019).

    Pins ``optimize=False`` + :data:`PNG_EXPORT_COMPRESS_LEVEL` and passes no
    ``pnginfo``/``exif``/``icc_profile``/``dpi`` — so there is no ``tIME`` or other
    volatile chunk and the same image encodes to identical bytes every run
    (REQ-P7-LOGIC-003).

    Raises:
        ExportError: If ``image`` is not RGBA.
    """
    _require_rgba(image, "PNG export")
    pil = Image.fromarray(np.ascontiguousarray(image.data), "RGBA")
    buffer = BytesIO()
    pil.save(
        buffer,
        format="PNG",
        optimize=False,
        compress_level=PNG_EXPORT_COMPRESS_LEVEL,
    )
    return buffer.getvalue()


def _shared_gif_palette(frames: Sequence[PixelBuffer]) -> List[Tuple[int, int, int]]:
    """Build one fixed, deterministic RGB palette shared by every GIF frame.

    Reuses the shipped :func:`~pixelart_creator.logic.quantize.median_cut` (Article
    I) over the whole animation's pixels so the palette — and therefore every
    frame's P-mode conversion — is deterministic (ADR-0019). Frequency is
    preserved by feeding all pixels (not just unique colours).

    Raises:
        ExportError: If the animation has too many pixels to build a palette
            buffer within the canvas bounds.
    """
    pixels = np.concatenate(
        [np.ascontiguousarray(f.data).reshape(-1, 4) for f in frames], axis=0
    )
    total = int(pixels.shape[0])
    cols = min(total, MAX_CANVAS_WIDTH)
    rows = (total + cols - 1) // cols
    if rows > MAX_CANVAS_HEIGHT:
        raise ExportError("animation too large to build a deterministic GIF palette")
    pad = rows * cols - total
    if pad:
        pixels = np.concatenate([pixels, np.repeat(pixels[-1:], pad, axis=0)], axis=0)
    source = PixelBuffer(cols, rows, ColorMode.RGBA)
    source.data[:, :] = pixels.reshape(rows, cols, 4)
    palette = median_cut(source, MAX_PALETTE_SIZE)
    return [(c[0], c[1], c[2]) for c in palette.colors()]


def _gif_palette_bytes(rgb: Sequence[Tuple[int, int, int]]) -> bytes:
    """Return a 768-byte (256x3) GIF palette, zero-padded, from RGB triplets."""
    flat: List[int] = []
    for r, g, b in rgb:
        flat.extend((r, g, b))
    flat = flat[: MAX_PALETTE_SIZE * 3]
    flat.extend([0] * (MAX_PALETTE_SIZE * 3 - len(flat)))
    return bytes(flat)


def encode_gif(
    frames: Sequence[PixelBuffer],
    durations: Sequence[int],
    *,
    loop: int = GIF_DEFAULT_LOOP_COUNT,
) -> bytes:
    """Encode a byte-reproducible animated GIF from frames + per-frame durations.

    Builds one fixed shared palette (``median_cut``), converts every frame with
    ``dither=NONE`` against that palette, and saves with ``optimize=False`` and an
    explicit per-frame ``duration`` list (from ``Frame.duration_ms``, FR-1) — so
    the bytes are deterministic and the delays are duration-faithful
    (REQ-P7-LOGIC-004, ADR-0019). A single-frame source yields a single-image GIF.
    Alpha is dropped (frames are treated as opaque RGB) this phase — GIF
    transparency is a deferred extension (Article XI).

    Raises:
        ExportError: On an empty/ragged frame set, a non-RGBA frame, an invalid
            ``loop``, or a non-positive duration.
    """
    if not frames:
        raise ExportError("GIF export needs at least one frame")
    if len(frames) != len(durations):
        raise ExportError("frames and durations must have equal length")
    if len(frames) > MAX_EXPORT_FRAMES:
        raise ExportError(
            f"frame count exceeds MAX_EXPORT_FRAMES ({MAX_EXPORT_FRAMES})"
        )
    if not isinstance(loop, int) or isinstance(loop, bool) or loop < 0:
        raise ExportError(f"loop must be a non-negative int, got {loop!r}")
    delays: List[int] = []
    for d in durations:
        if not isinstance(d, int) or isinstance(d, bool) or d <= 0:
            raise ExportError(f"frame duration must be a positive int, got {d!r}")
        delays.append(int(d))
    for f in frames:
        _require_rgba(f, "GIF export")

    palette_bytes = _gif_palette_bytes(_shared_gif_palette(frames))
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette_bytes)

    p_frames: List[Image.Image] = []
    for f in frames:
        rgb = np.ascontiguousarray(f.data[:, :, :3])
        pil = Image.fromarray(rgb, "RGB")
        p_frames.append(pil.quantize(palette=palette_image, dither=Image.Dither.NONE))

    buffer = BytesIO()
    p_frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=p_frames[1:],
        duration=delays,
        loop=int(loop),
        disposal=GIF_FRAME_DISPOSAL,
        optimize=False,
    )
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Sprite-sheet layout (deterministic row-major grid)                           #
# --------------------------------------------------------------------------- #


def build_sprite_sheet(
    frames: Sequence[PixelBuffer],
    *,
    columns: int = DEFAULT_SPRITE_SHEET_COLUMNS,
    padding: int = DEFAULT_ATLAS_PADDING,
) -> Tuple[PixelBuffer, SheetMetadata]:
    r"""Lay frames out row-major into one flat sheet image + :class:`SheetMetadata`.

    Placement is deterministic: frame ``k`` sits at column ``k % columns`` / row
    ``k // columns`` with ``padding`` px between cells (no outer margin). Every
    frame is the canvas size, so the sheet is a uniform grid (REQ-P7-LOGIC-005).
    The returned metadata carries per-frame :class:`SpriteRect`\\ s with
    ``duration_ms == 0`` (placeholder) and an empty ``image_name``/``tags`` —
    :func:`export_document` fills the durations, canonical image name, and tags.

    Raises:
        ExportError: On an empty frame set, out-of-range ``columns``/``padding``,
            or exceeding :data:`MAX_EXPORT_FRAMES`.
    """
    if not frames:
        raise ExportError("sprite sheet needs at least one frame")
    if len(frames) > MAX_EXPORT_FRAMES:
        raise ExportError(
            f"frame count exceeds MAX_EXPORT_FRAMES ({MAX_EXPORT_FRAMES})"
        )
    if not isinstance(columns, int) or isinstance(columns, bool) or columns < 1:
        raise ExportError(f"columns must be a positive int, got {columns!r}")
    if not isinstance(padding, int) or isinstance(padding, bool) or padding < 0:
        raise ExportError(f"padding must be a non-negative int, got {padding!r}")
    for f in frames:
        _require_rgba(f, "sprite sheet")

    cell_w = frames[0].width
    cell_h = frames[0].height
    count = len(frames)
    cols_used = min(count, columns)
    rows = (count + columns - 1) // columns
    stride_x = cell_w + padding
    stride_y = cell_h + padding
    sheet_w = cols_used * stride_x - padding
    sheet_h = rows * stride_y - padding

    sheet = PixelBuffer(sheet_w, sheet_h, ColorMode.RGBA)
    rects: List[SpriteRect] = []
    for k, frame in enumerate(frames):
        x = (k % columns) * stride_x
        y = (k // columns) * stride_y
        sheet.blit(frame, x, y)
        rects.append(
            SpriteRect(
                name=str(k),
                x=x,
                y=y,
                w=frame.width,
                h=frame.height,
                source_w=frame.width,
                source_h=frame.height,
                offset_x=0,
                offset_y=0,
                duration_ms=0,
            )
        )
    meta = SheetMetadata(
        image_name="", width=sheet_w, height=sheet_h, frames=tuple(rects), tags=()
    )
    return sheet, meta


# --------------------------------------------------------------------------- #
# Aseprite Array JSON metadata (deterministic, ADR-0017)                       #
# --------------------------------------------------------------------------- #


def build_metadata_json(meta: SheetMetadata) -> str:
    """Serialise :class:`SheetMetadata` to the Aseprite *Array* JSON (ADR-0017).

    Emits ``frames[]`` (each ``filename``/``frame``/``rotated``=false/``trimmed``=
    false/``spriteSourceSize``/``sourceSize``/``duration``) + a ``meta`` block
    (``app``/``version``/``image``/``format``/``size``/``scale``/``frameTags``).
    Serialised with ``json.dumps(..., sort_keys=True, ensure_ascii=False,
    separators=(",", ":"))`` over integer coordinates and a fixed ``version`` — no
    timestamp — so it is byte-reproducible (REQ-P7-LOGIC-007/-008).

    REQ-P7-DATA-004.
    """
    frames_out = [
        {
            "filename": r.name,
            "frame": {"x": r.x, "y": r.y, "w": r.w, "h": r.h},
            "rotated": _ROTATED,
            "trimmed": _TRIMMED,
            "spriteSourceSize": {
                "x": r.offset_x,
                "y": r.offset_y,
                "w": r.source_w,
                "h": r.source_h,
            },
            "sourceSize": {"w": r.source_w, "h": r.source_h},
            "duration": r.duration_ms,
        }
        for r in meta.frames
    ]
    obj = {
        "frames": frames_out,
        "meta": {
            "app": _JSON_APP,
            "version": __version__,
            "image": meta.image_name,
            "format": _JSON_FORMAT,
            "size": {"w": meta.width, "h": meta.height},
            "scale": _JSON_SCALE,
            "frameTags": [
                {
                    "name": t.name,
                    "from": t.from_index,
                    "to": t.to_index,
                    "direction": t.direction,
                }
                for t in meta.tags
            ],
        },
    }
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


# --------------------------------------------------------------------------- #
# Frame selection + tag mapping (deterministic)                                #
# --------------------------------------------------------------------------- #


def _select(document: Document, tag: Optional[str]) -> Tuple[List[int], List[TagInfo]]:
    """Return the selected frame indices + the tags mapped into that selection.

    ``tag=None`` selects every frame in index order and maps all document tags
    verbatim (their ``from``/``to`` are frame indices == positions). A named tag
    selects its inclusive range; the single mapped tag spans ``0..count-1``.
    """
    count = len(document.frames)
    if tag is None:
        indices = list(range(count))
        tags = [
            TagInfo(t.name, t.from_frame, t.to_frame, _DIRECTION_BY_MODE[t.mode])
            for t in document.frame_tags
        ]
        return indices, tags
    match = next((t for t in document.frame_tags if t.name == tag), None)
    if match is None:
        raise ExportError(f"unknown tag {tag!r}")
    indices = list(range(match.from_frame, match.to_frame + 1))
    tags = [TagInfo(match.name, 0, len(indices) - 1, _DIRECTION_BY_MODE[match.mode])]
    return indices, tags


def _flatten_selection(
    document: Document, indices: Sequence[int]
) -> Tuple[List[PixelBuffer], List[int]]:
    """Flatten the selected frames (CO-4) and collect their durations, in order."""
    frames = [
        flatten_frame(document.frames[i], document.width, document.height)
        for i in indices
    ]
    durations = [document.frames[i].duration_ms for i in indices]
    return frames, durations


# --------------------------------------------------------------------------- #
# The single shared orchestrator (GUI + CLI both call this)                    #
# --------------------------------------------------------------------------- #


def _validate_request(request: ExportRequest) -> None:
    if not isinstance(request.fmt, ExportFormat):
        raise ExportError(f"fmt must be an ExportFormat, got {request.fmt!r}")
    if not isinstance(request.preset, EnginePreset):
        raise ExportError(f"preset must be an EnginePreset, got {request.preset!r}")


def export_document(document: Document, request: ExportRequest) -> ExportResult:
    """Export ``document`` per ``request`` — the single shared pure orchestrator.

    Both the GUI and the CLI call this identical function, so their output is
    byte-identical (REQ-P7-LOGIC-009/-013). It flattens (CO-4) → encodes/lays out
    → builds metadata, all deterministically (REQ-P7-LOGIC-002).

    - **PNG:** ``document.frames[request.frame_index]`` (default ``0``, the first
      frame, preserving single-frame output byte-for-byte), composited flat (CL-13).
    - **GIF:** the selected frame sequence honouring per-frame durations.
    - **SPRITE_SHEET:** a deterministic row-major grid + Aseprite JSON.
    - **ATLAS:** MaxRects-packed sprites (CP-1) + Aseprite JSON with matching coords.

    Raises:
        ExportError: On an invalid request, a bound breach, an out-of-range
            ``frame_index``, or an unknown tag.
        AtlasError: If an atlas cannot be packed (REQ-P7-LOGIC-006).
    """
    _validate_request(request)
    width, height = document.width, document.height

    if request.fmt is ExportFormat.PNG:
        if not 0 <= request.frame_index < len(document.frames):
            raise ExportError(
                f"frame_index {request.frame_index!r} out of range for "
                f"{len(document.frames)} frame(s)"
            )
        image = flatten_frame(document.frames[request.frame_index], width, height)
        return ExportResult(encode_png(image), _IMAGE_NAME_PNG, None, None)

    if request.fmt is ExportFormat.GIF:
        indices, _tags = _select(document, request.tag)
        frames, durations = _flatten_selection(document, indices)
        image_bytes = encode_gif(frames, durations, loop=request.loop)
        return ExportResult(image_bytes, _IMAGE_NAME_GIF, None, None)

    if request.fmt is ExportFormat.SPRITE_SHEET:
        indices, tags = _select(document, request.tag)
        frames, durations = _flatten_selection(document, indices)
        sheet, meta0 = build_sprite_sheet(
            frames, columns=request.columns, padding=request.padding
        )
        rects = tuple(
            replace(r, duration_ms=durations[k]) for k, r in enumerate(meta0.frames)
        )
        meta = SheetMetadata(
            image_name=_IMAGE_NAME_SHEET,
            width=meta0.width,
            height=meta0.height,
            frames=rects,
            tags=tuple(tags),
        )
        image_bytes = encode_png(sheet)
        metadata_json = build_metadata_json(meta) if request.emit_json else None
        return ExportResult(image_bytes, _IMAGE_NAME_SHEET, metadata_json, meta)

    if request.fmt is ExportFormat.ATLAS:
        indices, tags = _select(document, request.tag)
        frames, durations = _flatten_selection(document, indices)
        if len(frames) > MAX_EXPORT_FRAMES:
            raise ExportError(
                f"frame count exceeds MAX_EXPORT_FRAMES ({MAX_EXPORT_FRAMES})"
            )
        sprites = [(str(k), frames[k]) for k in range(len(frames))]
        atlas = pack_atlas(
            sprites, padding=request.padding, max_dimension=request.max_dimension
        )
        by_name = {p.name: p for p in atlas.placements}
        rects = tuple(
            SpriteRect(
                name=str(k),
                x=by_name[str(k)].x,
                y=by_name[str(k)].y,
                w=by_name[str(k)].w,
                h=by_name[str(k)].h,
                source_w=by_name[str(k)].w,
                source_h=by_name[str(k)].h,
                offset_x=0,
                offset_y=0,
                duration_ms=durations[k],
            )
            for k in range(len(frames))
        )
        meta = SheetMetadata(
            image_name=_IMAGE_NAME_ATLAS,
            width=atlas.width,
            height=atlas.height,
            frames=rects,
            tags=tuple(tags),
        )
        image_bytes = encode_png(atlas.image)
        metadata_json = build_metadata_json(meta) if request.emit_json else None
        return ExportResult(image_bytes, _IMAGE_NAME_ATLAS, metadata_json, meta)

    raise ExportError(f"unsupported format {request.fmt!r}")  # pragma: no cover


def run_batch(
    document: Document, requests: Sequence[ExportRequest]
) -> Tuple[ExportResult, ...]:
    """Export several targets in order; each result equals its single export.

    A pure, ordered iteration over :func:`export_document` (no shared mutable
    state), so each :class:`ExportResult`'s bytes are byte-identical to the
    one-at-a-time export of that same request (REQ-P7-LOGIC-010). Bounded by
    :data:`MAX_BATCH_TARGETS`. Because each target is computed independently, a
    failing target never corrupts the others' bytes; the failure surfaces as an
    :class:`ExportError`/:class:`AtlasError` identifying the target index (the
    per-target *continue-on-failure* isolation is the batch UI/CLI's concern,
    which calls :func:`export_document` per target).

    Raises:
        ExportError: On too many targets, or wrapping a per-target failure with
            its index.
        AtlasError: If a target's atlas cannot be packed.
    """
    if len(requests) > MAX_BATCH_TARGETS:
        raise ExportError(f"batch exceeds MAX_BATCH_TARGETS ({MAX_BATCH_TARGETS})")
    results: List[ExportResult] = []
    for i, request in enumerate(requests):
        try:
            results.append(export_document(document, request))
        except AtlasError:
            raise
        except ExportError as exc:
            raise ExportError(f"batch target {i} failed: {exc}") from exc
    return tuple(results)
