"""Read/write the ``.pixproj`` project format (zero Qt, S11).

The on-disk format is JSON with zlib+base64-compressed pixel data. Loading is
defensive per the security gate: every field is type- and bounds-checked, pixel
payloads are size-validated against the declared geometry, and nothing is
``eval``/``exec``'d. Paths are built with :mod:`pathlib` for portability.
"""

from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path
from typing import Any, Dict, List, Union

import numpy as np

from pixelart_creator.logic.color import from_hex, to_hex
from pixelart_creator.logic.constants import MAX_CANVAS_HEIGHT, MAX_CANVAS_WIDTH
from pixelart_creator.logic.document import Document, Frame, Layer
from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer

FORMAT_NAME = "pixproj"
FORMAT_VERSION = 1
FILE_SUFFIX = ".pixproj"

#: Hard cap on a decoded pixel payload (bytes) — a full 8K RGBA layer plus slack.
_MAX_DECOMPRESSED_BYTES = MAX_CANVAS_WIDTH * MAX_CANVAS_HEIGHT * 4


class ProjectIOError(ValueError):
    """Raised when a project cannot be serialised or is malformed on load."""


# --------------------------------------------------------------------------- #
# Serialisation                                                               #
# --------------------------------------------------------------------------- #


def _encode_buffer(buffer: PixelBuffer) -> str:
    raw = np.ascontiguousarray(buffer.data).tobytes()
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def _serialise_layer(layer: Layer) -> Dict[str, Any]:
    return {
        "name": layer.name,
        "opacity": layer.opacity,
        "visible": layer.visible,
        "locked": layer.locked,
        "data": _encode_buffer(layer.buffer),
    }


def serialize(document: Document) -> Dict[str, Any]:
    """Serialise a :class:`Document` to a plain JSON-ready dict."""
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "canvas": {
            "width": document.width,
            "height": document.height,
            "mode": document.mode.value,
        },
        "palette": [to_hex(c) for c in document.palette],
        "metadata": dict(document.metadata),
        "frames": [
            {
                "duration_ms": frame.duration_ms,
                "layers": [_serialise_layer(layer) for layer in frame.layers],
            }
            for frame in document.frames
        ],
    }


def save_project(document: Document, path: Union[str, Path]) -> Path:
    """Serialise ``document`` and write it to ``path`` (adds ``.pixproj``)."""
    target = Path(path)
    if target.suffix != FILE_SUFFIX:
        target = target.with_suffix(FILE_SUFFIX)
    payload = serialize(document)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Deserialisation (defensive)                                                 #
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectIOError(message)


def _get(mapping: Any, key: str, expected: type) -> Any:
    _require(isinstance(mapping, dict), "expected a JSON object")
    _require(key in mapping, f"missing required key {key!r}")
    value = mapping[key]
    _require(
        (
            isinstance(value, expected) and not isinstance(value, bool)
            if expected is int
            else isinstance(value, expected)
        ),
        f"key {key!r} must be {expected.__name__}",
    )
    return value


def _decode_buffer(
    encoded: str, width: int, height: int, mode: ColorMode
) -> PixelBuffer:
    _require(isinstance(encoded, str), "layer data must be a base64 string")
    try:
        compressed = base64.b64decode(encoded, validate=True)
        raw = zlib.decompress(compressed, bufsize=_MAX_DECOMPRESSED_BYTES)
    except (ValueError, zlib.error) as exc:
        raise ProjectIOError(f"corrupt layer data: {exc}") from exc
    _require(
        len(raw) <= _MAX_DECOMPRESSED_BYTES,
        "layer payload exceeds the maximum allowed size",
    )
    channels = 4 if mode is ColorMode.RGBA else 1
    expected = width * height * channels
    _require(
        len(raw) == expected,
        f"layer payload is {len(raw)} bytes, expected {expected}",
    )
    array = np.frombuffer(raw, dtype=np.uint8).copy()
    buffer = PixelBuffer(width, height, mode)
    if mode is ColorMode.RGBA:
        buffer.data[:, :] = array.reshape((height, width, 4))
    else:
        buffer.data[:, :] = array.reshape((height, width))
    return buffer


def _parse_layer(data: Any, width: int, height: int, mode: ColorMode) -> Layer:
    _require(isinstance(data, dict), "each layer must be a JSON object")
    name = data.get("name", "Layer")
    _require(isinstance(name, str), "layer name must be a string")
    opacity = data.get("opacity", 1.0)
    _require(
        isinstance(opacity, (int, float)) and not isinstance(opacity, bool),
        "layer opacity must be a number",
    )
    buffer = _decode_buffer(_get(data, "data", str), width, height, mode)
    return Layer(
        buffer,
        name,
        opacity=float(opacity),
        visible=bool(data.get("visible", True)),
        locked=bool(data.get("locked", False)),
    )


def deserialize(payload: Dict[str, Any]) -> Document:
    """Reconstruct a :class:`Document` from a parsed ``.pixproj`` dict.

    Raises:
        ProjectIOError: If any field is missing, mistyped, or out of bounds.
    """
    _require(isinstance(payload, dict), "project root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixproj file")
    version = payload.get("version")
    _require(version == FORMAT_VERSION, f"unsupported version {version!r}")

    canvas = _get(payload, "canvas", dict)
    width = _get(canvas, "width", int)
    height = _get(canvas, "height", int)
    _require(
        1 <= width <= MAX_CANVAS_WIDTH and 1 <= height <= MAX_CANVAS_HEIGHT,
        f"canvas {width}x{height} outside bounds",
    )
    mode_name = _get(canvas, "mode", str)
    try:
        mode = ColorMode(mode_name)
    except ValueError as exc:
        raise ProjectIOError(f"unknown colour mode {mode_name!r}") from exc

    palette_hex = payload.get("palette", [])
    _require(isinstance(palette_hex, list), "palette must be a list")
    _require(len(palette_hex) <= MAX_PALETTE_SIZE, "palette exceeds 256 colours")
    try:
        palette = Palette(from_hex(h) for h in palette_hex)
    except Exception as exc:  # noqa: BLE001 - normalise to ProjectIOError
        raise ProjectIOError(f"invalid palette entry: {exc}") from exc

    metadata_raw = payload.get("metadata", {})
    _require(isinstance(metadata_raw, dict), "metadata must be an object")
    metadata = {str(k): str(v) for k, v in metadata_raw.items()}

    frames_raw = _get(payload, "frames", list)
    _require(len(frames_raw) >= 1, "project must have at least one frame")

    document = Document(width, height, mode=mode, palette=palette, metadata=metadata)
    frames: List[Frame] = []
    for fdata in frames_raw:
        _require(isinstance(fdata, dict), "each frame must be a JSON object")
        duration = fdata.get("duration_ms", 100)
        _require(
            isinstance(duration, int)
            and not isinstance(duration, bool)
            and duration > 0,
            "frame duration must be a positive int",
        )
        layers_raw = _get(fdata, "layers", list)
        _require(len(layers_raw) >= 1, "each frame needs at least one layer")
        layers = [_parse_layer(ld, width, height, mode) for ld in layers_raw]
        frames.append(Frame(layers, duration_ms=duration))
    document.frames = frames
    return document


def load_project(path: Union[str, Path]) -> Document:
    """Read and validate a ``.pixproj`` file into a :class:`Document`."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectIOError(f"{target} is not valid JSON: {exc}") from exc
    return deserialize(payload)
