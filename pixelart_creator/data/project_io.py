"""Read/write the ``.pixproj`` project format (zero Qt, S11).

The on-disk format is JSON with zlib+base64-compressed pixel data. Loading is
defensive per the security gate: every field is type- and bounds-checked, pixel
payloads are size-validated against the declared geometry, and nothing is
``eval``/``exec``'d. Paths are built with :mod:`pathlib` for portability.
"""

from __future__ import annotations

import base64
import json
import math
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from pixelart_creator.logic.animation import (
    AnimationError,
    FrameTag,
    PlaybackMode,
    validate_tag_range,
)
from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
from pixelart_creator.logic.blend import BlendMode
from pixelart_creator.logic.color import ColorError, from_hex, to_hex
from pixelart_creator.logic.constants import (
    DEFAULT_DOCUMENT_PPI,
    DEFAULT_FRAME_DURATION_MS,
    DEFAULT_LAYER_OPACITY,
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_GROUP_NESTING_DEPTH,
    MAX_LAYERS_PER_FRAME,
    MAX_TILE_DIMENSION,
    MAX_TILEMAP_COORD,
    MAX_TILEMAP_LAYERS,
    PROJECT_ZLIB_LEVEL,
    TILEMAP_CHUNK_SIZE,
)
from pixelart_creator.logic.document import (
    Document,
    Frame,
    Layer,
    LayerGroup,
    LayerNode,
)
from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.project_prefs import REGISTRY as PREFS_REGISTRY
from pixelart_creator.logic.project_prefs import (
    ProjectPrefs,
    ProjectPrefsError,
)
from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
from pixelart_creator.logic.tileset import Tileset

FORMAT_NAME = "pixproj"
#: Current schema version (ADR-0025). v5 adds the first-class ``Document.ppi`` field
#: (real-size preview, BF-3); v4 adds document-level ``tilesets`` + ``tilemaps``
#: (Phase-6 tileset/tilemap model — source-image ref + slicing; chunked-sparse layer
#: stack + linked instances + auto-tile logical placement); v3 adds ``frame_tags`` +
#: per-node ``layer_id``; v2 the richer layer model; v1 flat NORMAL layers.
#: v1–v4 load unchanged: absent ``ppi`` -> :data:`DEFAULT_DOCUMENT_PPI`; v1/v2/v3
#: also load with empty tileset/tilemap collections; v1/v2 with an empty tag
#: collection + minted ``layer_id`` s. Saving always writes v5.
FORMAT_VERSION = 5
_SUPPORTED_VERSIONS = (1, 2, 3, 4, 5)
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
    return base64.b64encode(zlib.compress(raw, PROJECT_ZLIB_LEVEL)).decode("ascii")


def _serialise_buffer(buffer: PixelBuffer) -> Dict[str, Any]:
    """Serialise a buffer (e.g. a mask) with its own storage mode."""
    return {"mode": buffer.mode.value, "data": _encode_buffer(buffer)}


def _node_paths(nodes: Sequence[LayerNode]) -> Dict[int, List[int]]:
    """Map each node's ``id()`` to its index path in the tree (for smart links)."""
    mapping: Dict[int, List[int]] = {}

    def _walk(ns: Sequence[LayerNode], prefix: Tuple[int, ...]) -> None:
        for i, node in enumerate(ns):
            path = prefix + (i,)
            mapping[id(node)] = list(path)
            if isinstance(node, LayerGroup):
                _walk(node.children, path)

    _walk(nodes, ())
    return mapping


def _serialise_node(node: LayerNode, paths: Dict[int, List[int]]) -> Dict[str, Any]:
    common: Dict[str, Any] = {
        "name": node.name,
        "opacity": node.opacity,
        "visible": node.visible,
        "locked": node.locked,
        "blend_mode": node.blend_mode.value,
        "reference": node.reference,
        "layer_id": node.layer_id,
        "mask": _serialise_buffer(node.mask) if node.mask is not None else None,
    }
    if isinstance(node, LayerGroup):
        common["type"] = "group"
        common["children"] = [_serialise_node(c, paths) for c in node.children]
    else:
        common["type"] = "layer"
        common["data"] = _encode_buffer(node.buffer)
        common["smart_source"] = (
            paths.get(id(node.smart_source)) if node.smart_source is not None else None
        )
    return common


def _serialise_tag(tag: FrameTag) -> Dict[str, Any]:
    """Serialise a :class:`FrameTag` (native ``PlaybackMode`` value string)."""
    return {
        "name": tag.name,
        "from": tag.from_frame,
        "to": tag.to_frame,
        "mode": tag.mode.value,
        "repeat": tag.repeat,
        "color": tag.color,
    }


def _encode_u32(array: np.ndarray) -> str:
    """Encode a uint32 array (little-endian) as zlib+base64 (native cell data)."""
    raw = np.ascontiguousarray(array, dtype="<u4").tobytes()
    return base64.b64encode(zlib.compress(raw, PROJECT_ZLIB_LEVEL)).decode("ascii")


def _serialise_tileset(tileset: Tileset) -> Dict[str, Any]:
    """Serialise a :class:`Tileset` (source-image ref + slicing config)."""
    source = tileset.source
    return {
        "name": tileset.name,
        "mode": source.mode.value,
        "source_width": source.width,
        "source_height": source.height,
        "source": _encode_buffer(source),
        "tile_width": tileset.tile_width,
        "tile_height": tileset.tile_height,
        "margin": tileset.margin,
        "spacing": tileset.spacing,
        "first_gid": tileset.first_gid,
    }


def _serialise_tilemap_layer(layer: TilemapLayer) -> Dict[str, Any]:
    """Serialise one tilemap layer (display + logical chunks; auto-tile ruleset)."""
    out: Dict[str, Any] = {
        "name": layer.name,
        "visible": layer.visible,
        "opacity": layer.opacity,
        "display_chunks": [
            {"cx": cx, "cy": cy, "data": _encode_u32(chunk)}
            for (cx, cy), chunk in layer._display_chunk_items()
        ],
    }
    if layer.autotile is not None:
        out["autotile"] = {
            "terrain_gid": layer.autotile.terrain_gid,
            "frame_gids": list(layer.autotile.frame_gids),
        }
        out["logical_chunks"] = [
            {"cx": cx, "cy": cy, "data": _encode_u32(chunk)}
            for (cx, cy), chunk in layer._logical_chunk_items()
        ]
    return out


def _serialise_tilemap(
    tilemap: Tilemap, tileset_index: Dict[int, int]
) -> Dict[str, Any]:
    """Serialise a :class:`Tilemap` (tileset refs by document index + layers).

    REQ-P6-DATA-004.
    """
    refs: List[int] = []
    for tileset in tilemap.tilesets:
        idx = tileset_index.get(id(tileset))
        if idx is None:
            raise ProjectIOError(
                "tilemap references a tileset not attached to the document"
            )
        refs.append(idx)
    return {
        "name": tilemap.name,
        "infinite": tilemap.infinite,
        "tile_width": tilemap.tile_width,
        "tile_height": tilemap.tile_height,
        "tilesets": refs,
        "layers": [_serialise_tilemap_layer(layer) for layer in tilemap.layers],
    }


def serialize(document: Document) -> Dict[str, Any]:
    """Serialise a :class:`Document` to a plain JSON-ready dict (schema v4)."""
    frames_out: List[Dict[str, Any]] = []
    for frame in document.frames:
        paths = _node_paths(frame.layers)
        frames_out.append(
            {
                "duration_ms": frame.duration_ms,
                "layers": [_serialise_node(node, paths) for node in frame.layers],
            }
        )
    tileset_index = {id(ts): i for i, ts in enumerate(document.tilesets)}
    payload: Dict[str, Any] = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "canvas": {
            "width": document.width,
            "height": document.height,
            "mode": document.mode.value,
        },
        "ppi": document.ppi,
        "palette": [to_hex(c) for c in document.palette],
        "metadata": dict(document.metadata),
        "frames": frames_out,
        "frame_tags": [_serialise_tag(tag) for tag in document.frame_tags],
        "tilesets": [_serialise_tileset(ts) for ts in document.tilesets],
        "tilemaps": [_serialise_tilemap(tm, tileset_index) for tm in document.tilemaps],
    }
    # One optional root key (REQ-P5-DATA-004, ADR-0056): omitted entirely when
    # no preference has been explicitly set, so a project that never touches
    # a preference serialises exactly as it did before this field existed.
    prefs_mapping = document.prefs.to_mapping()
    if prefs_mapping:
        payload["prefs"] = prefs_mapping
    return payload


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


def _parse_ppi(value: Any) -> float:
    """Parse the optional ``ppi`` field defensively (v5; ADR-0025 §1).

    An absent field (v1–v4 files) defaults to :data:`DEFAULT_DOCUMENT_PPI`; a
    present value must be a finite number ``> 0`` — anything else (wrong type,
    ``0``, negative, NaN, infinity) raises :class:`ProjectIOError` (IO-3).
    """
    if value is None:
        return DEFAULT_DOCUMENT_PPI
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        "ppi must be a number",
    )
    _require(math.isfinite(value) and value > 0.0, "ppi must be finite and > 0")
    return float(value)


def _parse_prefs(value: Any) -> ProjectPrefs:
    """Parse the optional ``prefs`` root object (v5+; ``REQ-P5-DATA-004``, ADR-0056).

    An absent object, and an absent key within a present object, both read as
    that key's default (``ask``, for this slice's boolean-shaped preference) —
    ``FORMAT_VERSION`` stays 5, so a v1–v4 project without this field loads
    unchanged. A recognised key holding a value outside its declared domain is
    **refused** with :class:`ProjectIOError`, never coerced (a coerced
    preference is one the user did not set). A key this build does not
    recognise (a newer build's preference, added by a later slice through
    ``logic/project_prefs.py``'s ``register`` seam) is **ignored**, matching
    this format's established forward-tolerance: an unknown key is dropped,
    not refused (``data/project_io.py`` reads every field by name, "no
    unknown-key rejection").
    """
    _require(isinstance(value, dict), "prefs must be an object")
    resolved: Dict[str, str] = {}
    for key_name, raw_value in value.items():
        _require(isinstance(key_name, str), "prefs key must be a string")
        key = PREFS_REGISTRY.get(key_name)
        if key is None:
            continue  # forward-tolerant: an unrecognised preference is dropped
        _require(isinstance(raw_value, str), f"prefs[{key_name!r}] must be a string")
        try:
            resolved[key_name] = key.validate(raw_value)
        except ProjectPrefsError as exc:
            raise ProjectIOError(str(exc)) from exc
    return ProjectPrefs(resolved)


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
    """Parse a legacy v1 flat layer (NORMAL blend, no mask/groups) — back-compat."""
    _require(isinstance(data, dict), "each layer must be a JSON object")
    name = data.get("name", "Layer")
    _require(isinstance(name, str), "layer name must be a string")
    opacity = data.get("opacity", DEFAULT_LAYER_OPACITY)
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


def _parse_blend_mode(value: Any) -> BlendMode:
    _require(isinstance(value, str), "blend_mode must be a string")
    try:
        return BlendMode(value)
    except ValueError as exc:
        raise ProjectIOError(f"unknown blend mode {value!r}") from exc


def _parse_mask(value: Any, width: int, height: int) -> Optional[PixelBuffer]:
    if value is None:
        return None
    _require(isinstance(value, dict), "mask must be an object or null")
    mode_name = _get(value, "mode", str)
    try:
        mask_mode = ColorMode(mode_name)
    except ValueError as exc:
        raise ProjectIOError(f"unknown mask mode {mode_name!r}") from exc
    return _decode_buffer(_get(value, "data", str), width, height, mask_mode)


def _parse_node_v2(
    data: Any,
    width: int,
    height: int,
    mode: ColorMode,
    depth: int,
    leaf_counter: List[int],
    smart_links: List[Tuple[Layer, Tuple[int, ...]]],
) -> LayerNode:
    """Parse a v2 layer/group node recursively (defensive, bounds-checked)."""
    _require(isinstance(data, dict), "each layer node must be a JSON object")
    node_type = data.get("type", "layer")
    _require(node_type in ("layer", "group"), f"unknown node type {node_type!r}")
    name = data.get("name", "Layer")
    _require(isinstance(name, str), "node name must be a string")
    opacity = data.get("opacity", DEFAULT_LAYER_OPACITY)
    _require(
        isinstance(opacity, (int, float)) and not isinstance(opacity, bool),
        "opacity must be a number",
    )
    _require(0.0 <= float(opacity) <= 1.0, "opacity out of range 0.0..1.0")
    blend_mode = _parse_blend_mode(data.get("blend_mode", BlendMode.NORMAL.value))
    mask = _parse_mask(data.get("mask"), width, height)
    reference = bool(data.get("reference", False))
    visible = bool(data.get("visible", True))
    locked = bool(data.get("locked", False))
    layer_id = data.get("layer_id", 0)
    _require(
        isinstance(layer_id, int) and not isinstance(layer_id, bool) and layer_id >= 0,
        "layer_id must be a non-negative int",
    )

    if node_type == "group":
        _require(
            depth + 1 <= MAX_GROUP_NESTING_DEPTH,
            "group nesting exceeds MAX_GROUP_NESTING_DEPTH "
            f"({MAX_GROUP_NESTING_DEPTH})",
        )
        children_raw = _get(data, "children", list)
        children = [
            _parse_node_v2(c, width, height, mode, depth + 1, leaf_counter, smart_links)
            for c in children_raw
        ]
        return LayerGroup(
            name,
            children,
            opacity=float(opacity),
            visible=visible,
            locked=locked,
            blend_mode=blend_mode,
            mask=mask,
            reference=reference,
            layer_id=layer_id,
        )

    leaf_counter[0] += 1
    _require(
        leaf_counter[0] <= MAX_LAYERS_PER_FRAME,
        f"frame exceeds MAX_LAYERS_PER_FRAME ({MAX_LAYERS_PER_FRAME})",
    )
    buffer = _decode_buffer(_get(data, "data", str), width, height, mode)
    layer = Layer(
        buffer,
        name,
        opacity=float(opacity),
        visible=visible,
        locked=locked,
        blend_mode=blend_mode,
        mask=mask,
        reference=reference,
        layer_id=layer_id,
    )
    smart = data.get("smart_source")
    if smart is not None:
        _require(
            isinstance(smart, list)
            and all(isinstance(i, int) and not isinstance(i, bool) for i in smart),
            "smart_source must be a list of ints",
        )
        smart_links.append((layer, tuple(smart)))
    return layer


def _node_at_path(nodes: List[LayerNode], path: Tuple[int, ...]) -> LayerNode:
    _require(bool(path), "smart-source reference is empty")
    container = nodes
    node: Optional[LayerNode] = None
    for depth, idx in enumerate(path):
        _require(0 <= idx < len(container), "dangling smart-source reference")
        node = container[idx]
        if depth < len(path) - 1:
            _require(isinstance(node, LayerGroup), "dangling smart-source reference")
            container = node.children  # type: ignore[union-attr]
    assert node is not None
    return node


def _resolve_smart_links(
    frame_layers: List[LayerNode],
    smart_links: List[Tuple[Layer, Tuple[int, ...]]],
) -> None:
    for layer, path in smart_links:
        source = _node_at_path(frame_layers, path)
        _require(isinstance(source, Layer), "smart_source must reference a layer")
        layer.smart_source = source  # type: ignore[assignment]


def _parse_frame_v2(fdata: Any, width: int, height: int, mode: ColorMode) -> Frame:
    _require(isinstance(fdata, dict), "each frame must be a JSON object")
    duration = fdata.get("duration_ms", DEFAULT_FRAME_DURATION_MS)
    _require(
        isinstance(duration, int) and not isinstance(duration, bool) and duration > 0,
        "frame duration must be a positive int",
    )
    layers_raw = _get(fdata, "layers", list)
    _require(len(layers_raw) >= 1, "each frame needs at least one layer")
    leaf_counter = [0]
    smart_links: List[Tuple[Layer, Tuple[int, ...]]] = []
    nodes = [
        _parse_node_v2(nd, width, height, mode, 0, leaf_counter, smart_links)
        for nd in layers_raw
    ]
    _require(leaf_counter[0] >= 1, "each frame needs at least one layer")
    _resolve_smart_links(nodes, smart_links)
    return Frame(nodes, duration_ms=duration)


def _parse_frame_v1(fdata: Any, width: int, height: int, mode: ColorMode) -> Frame:
    _require(isinstance(fdata, dict), "each frame must be a JSON object")
    duration = fdata.get("duration_ms", DEFAULT_FRAME_DURATION_MS)
    _require(
        isinstance(duration, int) and not isinstance(duration, bool) and duration > 0,
        "frame duration must be a positive int",
    )
    layers_raw = _get(fdata, "layers", list)
    _require(len(layers_raw) >= 1, "each frame needs at least one layer")
    layers: List[LayerNode] = [
        _parse_layer(ld, width, height, mode) for ld in layers_raw
    ]
    return Frame(layers, duration_ms=duration)


def _parse_tags(raw: Any, frame_count: int) -> List[FrameTag]:
    """Parse and validate the document ``frame_tags`` array (v3, defensive).

    Rejects a non-list container, a malformed tag object, an unknown
    :class:`PlaybackMode`, a non-int/negative repeat, a malformed colour, or an
    inverted/out-of-range frame range — each with :class:`ProjectIOError`
    (Article VII / REQ-P5-DATA-003). No clamping on load (clamping is a runtime
    frame-op concern, REQ-P5-LOGIC-010).
    """
    _require(isinstance(raw, list), "frame_tags must be a list")
    tags: List[FrameTag] = []
    for entry in raw:
        _require(isinstance(entry, dict), "each frame tag must be a JSON object")
        name = _get(entry, "name", str)
        from_frame = _get(entry, "from", int)
        to_frame = _get(entry, "to", int)
        mode_name = _get(entry, "mode", str)
        try:
            mode = PlaybackMode(mode_name)
        except ValueError as exc:
            raise ProjectIOError(f"unknown playback mode {mode_name!r}") from exc
        repeat = entry.get("repeat", 0)
        _require(
            isinstance(repeat, int) and not isinstance(repeat, bool) and repeat >= 0,
            "tag repeat must be a non-negative int",
        )
        color = entry.get("color", "#ff0000ff")
        _require(isinstance(color, str), "tag color must be a string")
        try:
            from_hex(color)
        except ColorError as exc:
            raise ProjectIOError(f"invalid tag color {color!r}: {exc}") from exc
        try:
            validate_tag_range(from_frame, to_frame, frame_count)
        except AnimationError as exc:
            raise ProjectIOError(str(exc)) from exc
        tags.append(
            FrameTag(name, from_frame, to_frame, mode=mode, repeat=repeat, color=color)
        )
    return tags


def _assign_loaded_ids(document: Document) -> None:
    """Preserve loaded stable ``layer_id`` s and mint fresh ones for unset nodes.

    v3 nodes carry an explicit ``layer_id``; v1/v2 nodes have ``0`` (unminted).
    The document's monotonic counter is advanced past the highest loaded id so
    later mints never collide, then any unset node is assigned a fresh id.
    """
    max_id = 0
    stack: List[LayerNode] = []
    for frame in document.frames:
        stack.extend(frame.layers)
    while stack:
        node = stack.pop()
        max_id = max(max_id, node.layer_id)
        if isinstance(node, LayerGroup):
            stack.extend(node.children)
    document._next_layer_id = max_id + 1
    for frame in document.frames:
        document._assign_ids(frame.layers)


def _decode_u32(encoded: str, count: int) -> np.ndarray:
    """Decode a native zlib+base64 uint32 chunk payload (defensive)."""
    _require(isinstance(encoded, str), "chunk data must be a base64 string")
    try:
        raw = zlib.decompress(
            base64.b64decode(encoded, validate=True), bufsize=count * 4
        )
    except (ValueError, TypeError, zlib.error) as exc:
        raise ProjectIOError(f"corrupt chunk data: {exc}") from exc
    _require(len(raw) == count * 4, f"chunk payload is {len(raw)} bytes")
    return np.frombuffer(raw, dtype="<u4").copy()


def _parse_tileset(data: Any) -> Tileset:
    """Parse and validate one v4 tileset object (defensive, bounds-checked)."""
    _require(isinstance(data, dict), "each tileset must be a JSON object")
    name = data.get("name", "Tileset")
    _require(isinstance(name, str), "tileset name must be a string")
    mode_name = _get(data, "mode", str)
    try:
        mode = ColorMode(mode_name)
    except ValueError as exc:
        raise ProjectIOError(f"unknown tileset mode {mode_name!r}") from exc
    width = _get(data, "source_width", int)
    height = _get(data, "source_height", int)
    _require(
        1 <= width <= MAX_CANVAS_WIDTH and 1 <= height <= MAX_CANVAS_HEIGHT,
        f"tileset source {width}x{height} outside bounds",
    )
    source = _decode_buffer(_get(data, "source", str), width, height, mode)
    for key in ("tile_width", "tile_height"):
        value = _get(data, key, int)
        _require(
            1 <= value <= MAX_TILE_DIMENSION,
            f"tileset {key} {value} outside 1..{MAX_TILE_DIMENSION}",
        )
    margin = _get(data, "margin", int)
    spacing = _get(data, "spacing", int)
    _require(margin >= 0 and spacing >= 0, "tileset margin/spacing must be >= 0")
    first_gid = _get(data, "first_gid", int)
    _require(first_gid >= 1, "tileset first_gid must be >= 1")
    try:
        return Tileset(
            source,
            tile_width=data["tile_width"],
            tile_height=data["tile_height"],
            margin=margin,
            spacing=spacing,
            name=name,
            first_gid=first_gid,
        )
    except ValueError as exc:  # TilesetError subclasses ValueError
        raise ProjectIOError(f"invalid tileset: {exc}") from exc


def _parse_autotile(data: Any) -> AutotileRuleset:
    _require(isinstance(data, dict), "autotile must be a JSON object")
    terrain = _get(data, "terrain_gid", int)
    frames = _get(data, "frame_gids", list)
    _require(
        len(frames) == BLOB_TILE_COUNT,
        f"autotile frame_gids must hold {BLOB_TILE_COUNT} entries",
    )
    for gid in frames:
        _require(
            isinstance(gid, int) and not isinstance(gid, bool) and gid >= 0,
            "autotile frame gid must be a non-negative int",
        )
    try:
        return AutotileRuleset(terrain, frames)
    except ValueError as exc:  # AutotileError subclasses ValueError
        raise ProjectIOError(f"invalid autotile ruleset: {exc}") from exc


def _apply_chunks(grid: Any, chunk_entries: Any) -> None:
    """Decode chunk entries onto a ``_ChunkGrid`` (defensive, coord-bounded)."""
    _require(isinstance(chunk_entries, list), "chunks must be a list")
    cell_count = TILEMAP_CHUNK_SIZE * TILEMAP_CHUNK_SIZE
    for chunk in chunk_entries:
        _require(isinstance(chunk, dict), "each chunk must be a JSON object")
        cx = _get(chunk, "cx", int)
        cy = _get(chunk, "cy", int)
        origin_x = cx * TILEMAP_CHUNK_SIZE
        origin_y = cy * TILEMAP_CHUNK_SIZE
        _require(
            abs(origin_x) <= MAX_TILEMAP_COORD and abs(origin_y) <= MAX_TILEMAP_COORD,
            "chunk origin exceeds MAX_TILEMAP_COORD",
        )
        values = _decode_u32(_get(chunk, "data", str), cell_count).reshape(
            (TILEMAP_CHUNK_SIZE, TILEMAP_CHUNK_SIZE)
        )
        for row, col in np.argwhere(values != 0):
            grid.set(origin_x + int(col), origin_y + int(row), int(values[row, col]))


def _parse_tilemap_layer(data: Any) -> TilemapLayer:
    _require(isinstance(data, dict), "each tilemap layer must be a JSON object")
    name = data.get("name", "Layer")
    _require(isinstance(name, str), "layer name must be a string")
    visible = data.get("visible", True)
    _require(isinstance(visible, bool), "layer visible must be a bool")
    opacity = data.get("opacity", 1.0)
    _require(
        isinstance(opacity, (int, float)) and not isinstance(opacity, bool),
        "layer opacity must be a number",
    )
    _require(0.0 <= float(opacity) <= 1.0, "layer opacity out of range 0.0..1.0")
    autotile_raw = data.get("autotile")
    ruleset = _parse_autotile(autotile_raw) if autotile_raw is not None else None
    layer = TilemapLayer(
        name, visible=visible, opacity=float(opacity), autotile=ruleset
    )
    _apply_chunks(layer._display, data.get("display_chunks", []))
    if ruleset is not None:
        _apply_chunks(layer._logical, data.get("logical_chunks", []))
    return layer


def _parse_tilemap(data: Any, tilesets: List[Tileset]) -> Tilemap:
    _require(isinstance(data, dict), "each tilemap must be a JSON object")
    name = data.get("name", "Tilemap")
    _require(isinstance(name, str), "tilemap name must be a string")
    infinite = data.get("infinite", True)
    _require(isinstance(infinite, bool), "tilemap infinite must be a bool")
    for key in ("tile_width", "tile_height"):
        value = _get(data, key, int)
        _require(
            1 <= value <= MAX_TILE_DIMENSION,
            f"tilemap {key} {value} outside 1..{MAX_TILE_DIMENSION}",
        )
    tilemap = Tilemap(
        name=name,
        infinite=infinite,
        tile_width=data["tile_width"],
        tile_height=data["tile_height"],
    )
    refs = _get(data, "tilesets", list)
    for ref in refs:
        _require(
            isinstance(ref, int)
            and not isinstance(ref, bool)
            and 0 <= ref < len(tilesets),
            "tilemap tileset reference out of range",
        )
        tilemap.tilesets.append(tilesets[ref])
    layers_raw = _get(data, "layers", list)
    _require(
        len(layers_raw) <= MAX_TILEMAP_LAYERS,
        f"tilemap exceeds MAX_TILEMAP_LAYERS ({MAX_TILEMAP_LAYERS})",
    )
    for layer_data in layers_raw:
        tilemap.layers.append(_parse_tilemap_layer(layer_data))
    return tilemap


def _parse_tilesets(raw: Any) -> List[Tileset]:
    _require(isinstance(raw, list), "tilesets must be a list")
    return [_parse_tileset(entry) for entry in raw]


def _parse_tilemaps(raw: Any, tilesets: List[Tileset]) -> List[Tilemap]:
    _require(isinstance(raw, list), "tilemaps must be a list")
    return [_parse_tilemap(entry, tilesets) for entry in raw]


def deserialize(payload: Dict[str, Any]) -> Document:
    """Reconstruct a :class:`Document` from a parsed ``.pixproj`` dict.

    Raises:
        ProjectIOError: If any field is missing, mistyped, or out of bounds.
    """
    _require(isinstance(payload, dict), "project root must be a JSON object")
    _require(payload.get("format") == FORMAT_NAME, "not a pixproj file")
    version = payload.get("version")
    _require(
        version in _SUPPORTED_VERSIONS,
        f"unsupported version {version!r}",
    )

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

    ppi = _parse_ppi(payload.get("ppi"))
    prefs = _parse_prefs(payload.get("prefs", {}))

    frames_raw = _get(payload, "frames", list)
    _require(len(frames_raw) >= 1, "project must have at least one frame")

    document = Document(
        width,
        height,
        mode=mode,
        palette=palette,
        metadata=metadata,
        ppi=ppi,
        prefs=prefs,
    )
    parse_frame = _parse_frame_v1 if version == 1 else _parse_frame_v2
    document.frames = [parse_frame(fdata, width, height, mode) for fdata in frames_raw]
    _assign_loaded_ids(document)
    document.frame_tags = _parse_tags(
        payload.get("frame_tags", []), len(document.frames)
    )
    # v4 tileset/tilemap collections; v1/v2/v3 omit them -> empty (back-compat).
    document.tilesets = _parse_tilesets(payload.get("tilesets", []))
    document.tilemaps = _parse_tilemaps(payload.get("tilemaps", []), document.tilesets)
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
