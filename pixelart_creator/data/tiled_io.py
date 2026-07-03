"""Tiled 1.12.2 JSON map export / lossless import (zero Qt, S11; ADR-0014).

Exports a :class:`~pixelart_creator.logic.tilemap.Tilemap` to a Tiled-compatible
JSON *map object* and re-imports it losslessly (REQ-P6-DATA-001/-002) behind a
defensive validated load (REQ-P6-DATA-003) reusing the ``project_io`` posture
(IO-3): every field is type/bounds-checked, gids are range-checked, layer payload
sizes are validated against the declared geometry, and nothing is
``eval``/``exec``'d.

Encodings (ADR-0014 / research §2.3): emit **CSV by default** (human-diffable,
always lossless) or **base64** with ``gzip``/``zlib`` (both stdlib); import
accepts CSV + base64-none/gzip/zlib. **``zstd`` is rejected** (needs a non-stdlib
dependency, S8) and **external ``.tsx`` (XML)** tilesets are rejected — both with
a clear :class:`ProjectIOError`. Import accepts embedded tilesets and external
``.tsj`` (JSON) references. The full 4-bit GID flag set is preserved through
round-trip; the base tile id strips **all four** flag bits (incl. the diagonal
``0x20000000`` — the documented Tiled gotcha, research §2.6) via
:data:`~pixelart_creator.logic.tilemap.GID_MASK` at resolve time. Unknown/extra
fields (``properties``/``wangsets``/object layers/counters/unknown keys) are
preserved verbatim on ``Tilemap.tiled_passthrough`` for a byte-tolerant lossless
round-trip.

The canonical GID masks live in ``logic/tilemap`` and are imported **downward**
(``data -> logic``, permitted); a forbidden ``logic -> data`` edge never appears.
Paths are built with :mod:`pathlib` for portability.
"""

from __future__ import annotations

import base64
import gzip
import json
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from pixelart_creator.data.project_io import ProjectIOError
from pixelart_creator.logic.constants import (
    MAX_CANVAS_HEIGHT,
    MAX_CANVAS_WIDTH,
    MAX_TILE_DIMENSION,
    MAX_TILEMAP_COORD,
    TILEMAP_CHUNK_SIZE,
)
from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
from pixelart_creator.logic.tilemap import (
    GID_MASK,
    Tilemap,
    TilemapError,
    TilemapLayer,
)
from pixelart_creator.logic.tileset import Tileset

__all__ = [
    "export_tilemap",
    "write_tiled_json",
    "import_tilemap",
    "read_tiled_json",
]

# --- Tiled format identifiers (module-local, ADR-0001 — like blend version) ---
_JSON_VERSION = "1.10"
_TILED_VERSION = "1.12.2"
_ORIENTATION = "orthogonal"
_RENDER_ORDER = "right-down"
_DEFAULT_COMPRESSION_LEVEL = -1
_CUSTOM_SOURCE_KEY = "pixelartcreator:source"  # our lossless pixel embed
_LE_U32 = "<u4"

#: Hard cap on a decoded layer/chunk GID payload (bytes) — guards a zip-bomb.
_MAX_LAYER_BYTES = MAX_CANVAS_WIDTH * MAX_CANVAS_HEIGHT * 4

# Top-level map keys the model owns (everything else is verbatim passthrough).
_KNOWN_MAP_KEYS = frozenset(
    {
        "type",
        "version",
        "tiledversion",
        "orientation",
        "renderorder",
        "infinite",
        "tilewidth",
        "tileheight",
        "width",
        "height",
        "nextlayerid",
        "nextobjectid",
        "compressionlevel",
        "tilesets",
        "layers",
    }
)
_KNOWN_TILESET_KEYS = frozenset(
    {
        "firstgid",
        "source",
        "name",
        "tilewidth",
        "tileheight",
        "tilecount",
        "columns",
        "margin",
        "spacing",
        "image",
        "imagewidth",
        "imageheight",
        _CUSTOM_SOURCE_KEY,
    }
)
_KNOWN_TILELAYER_KEYS = frozenset(
    {
        "type",
        "id",
        "name",
        "width",
        "height",
        "x",
        "y",
        "opacity",
        "visible",
        "data",
        "chunks",
        "encoding",
        "compression",
    }
)


# --------------------------------------------------------------------------- #
# GID payload encode / decode                                                 #
# --------------------------------------------------------------------------- #


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectIOError(message)


def _encode_gids(gids: np.ndarray, encoding: str, compression: Optional[str]) -> Any:
    """Encode a row-major uint32 GID array as CSV (list) or a base64 string."""
    flat = np.ascontiguousarray(gids, dtype=_LE_U32).reshape(-1)
    if encoding == "csv":
        return [int(v) for v in flat]
    if encoding == "base64":
        raw = flat.tobytes()
        if compression in (None, ""):
            payload = raw
        elif compression == "gzip":
            payload = gzip.compress(raw)
        elif compression == "zlib":
            payload = zlib.compress(raw)
        else:
            raise ProjectIOError(f"unsupported compression {compression!r}")
        return base64.b64encode(payload).decode("ascii")
    raise ProjectIOError(f"unsupported encoding {encoding!r}")


def _decode_gids(
    data: Any, encoding: str, compression: Optional[str], count: int
) -> np.ndarray:
    """Decode a GID payload to a length-``count`` uint32 array (defensive)."""
    if encoding == "csv":
        _require(isinstance(data, list), "csv layer data must be a list")
        _require(
            len(data) == count,
            f"csv layer data holds {len(data)} gids, expected {count}",
        )
        for value in data:
            _require(
                isinstance(value, int)
                and not isinstance(value, bool)
                and 0 <= value <= 0xFFFFFFFF,
                "csv gid must be a uint32",
            )
        return np.asarray(data, dtype=_LE_U32)
    if encoding == "base64":
        _require(isinstance(data, str), "base64 layer data must be a string")
        if compression == "zstd":
            raise ProjectIOError(
                "zstd-compressed layer data is unsupported (needs a non-stdlib "
                "dependency, S8)"
            )
        try:
            payload = base64.b64decode(data, validate=True)
        except (ValueError, TypeError) as exc:
            raise ProjectIOError(f"corrupt base64 layer data: {exc}") from exc
        try:
            if compression in (None, ""):
                raw = payload
            elif compression == "gzip":
                raw = gzip.decompress(payload)
            elif compression == "zlib":
                raw = zlib.decompress(payload, bufsize=_MAX_LAYER_BYTES)
            else:
                raise ProjectIOError(f"unsupported compression {compression!r}")
        except (OSError, zlib.error) as exc:
            raise ProjectIOError(f"corrupt compressed layer data: {exc}") from exc
        _require(
            len(raw) <= _MAX_LAYER_BYTES,
            "layer payload exceeds the maximum allowed size",
        )
        _require(
            len(raw) == count * 4,
            f"layer payload is {len(raw)} bytes, expected {count * 4}",
        )
        return np.frombuffer(raw, dtype=_LE_U32).copy()
    raise ProjectIOError(f"unknown layer encoding {encoding!r}")


def _extra_fields(obj: Dict[str, Any], known: frozenset) -> Dict[str, Any]:
    """Return the fields of ``obj`` not in ``known`` (verbatim passthrough)."""
    return {k: v for k, v in obj.items() if k not in known}


# --------------------------------------------------------------------------- #
# Custom lossless source-pixel embed (our own round-trip fidelity)            #
# --------------------------------------------------------------------------- #


def _encode_source(source: PixelBuffer) -> Dict[str, Any]:
    raw = np.ascontiguousarray(source.data).tobytes()
    return {
        "mode": source.mode.value,
        "width": source.width,
        "height": source.height,
        "data": base64.b64encode(zlib.compress(raw)).decode("ascii"),
    }


def _decode_source(blob: Any) -> Optional[PixelBuffer]:
    if not isinstance(blob, dict):
        return None
    try:
        mode = ColorMode(blob["mode"])
        width = int(blob["width"])
        height = int(blob["height"])
        raw = zlib.decompress(base64.b64decode(blob["data"], validate=True))
    except (KeyError, ValueError, TypeError, zlib.error):
        return None
    channels = 4 if mode is ColorMode.RGBA else 1
    if len(raw) != width * height * channels:
        return None
    buffer = PixelBuffer(width, height, mode)
    array = np.frombuffer(raw, dtype=np.uint8).copy()
    if mode is ColorMode.RGBA:
        buffer.data[:, :] = array.reshape((height, width, 4))
    else:
        buffer.data[:, :] = array.reshape((height, width))
    return buffer


# --------------------------------------------------------------------------- #
# Content bounds                                                              #
# --------------------------------------------------------------------------- #


def _content_bounds(
    tilemap: Tilemap,
) -> Optional[Tuple[int, int, int, int]]:
    """Return ``(min_x, min_y, max_x, max_y)`` over all display cells, or ``None``."""
    found = False
    min_x = min_y = max_x = max_y = 0
    for layer in tilemap.layers:
        for x, y, _gid in layer.cells():
            if not found:
                min_x, min_y, max_x, max_y = x, y, x, y
                found = True
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if not found:
        return None
    return (min_x, min_y, max_x, max_y)


# --------------------------------------------------------------------------- #
# Export                                                                      #
# --------------------------------------------------------------------------- #


def _export_tileset(tileset: Tileset, extra: Dict[str, Any]) -> Dict[str, Any]:
    obj: Dict[str, Any] = dict(extra)
    source = tileset.source
    obj.update(
        {
            "firstgid": tileset.first_gid,
            "name": tileset.name,
            "tilewidth": tileset.tile_width,
            "tileheight": tileset.tile_height,
            "tilecount": tileset.tile_count,
            "columns": tileset.columns,
            "margin": tileset.margin,
            "spacing": tileset.spacing,
            "image": obj.get("image", ""),
            "imagewidth": source.width,
            "imageheight": source.height,
            _CUSTOM_SOURCE_KEY: _encode_source(source),
        }
    )
    return obj


def _export_tile_layer(
    tilemap: Tilemap,
    layer: TilemapLayer,
    layer_id: int,
    bounds: Optional[Tuple[int, int, int, int]],
    encoding: str,
    compression: Optional[str],
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    obj: Dict[str, Any] = dict(extra)
    obj.update(
        {
            "type": "tilelayer",
            "id": layer_id,
            "name": layer.name,
            "x": 0,
            "y": 0,
            "opacity": layer.opacity,
            "visible": layer.visible,
        }
    )
    if tilemap.infinite:
        chunks: List[Dict[str, Any]] = []
        for (cx, cy), chunk in layer._display_chunk_items():
            chunk_obj: Dict[str, Any] = {
                "x": cx * TILEMAP_CHUNK_SIZE,
                "y": cy * TILEMAP_CHUNK_SIZE,
                "width": TILEMAP_CHUNK_SIZE,
                "height": TILEMAP_CHUNK_SIZE,
                "data": _encode_gids(chunk, encoding, compression),
            }
            chunks.append(chunk_obj)
        obj["chunks"] = chunks
        if bounds is None:
            obj["width"] = 0
            obj["height"] = 0
        else:
            min_x, min_y, max_x, max_y = bounds
            obj["width"] = max_x - min_x + 1
            obj["height"] = max_y - min_y + 1
    else:
        width, height = (0, 0) if bounds is None else (bounds[2] + 1, bounds[3] + 1)
        grid = np.zeros((max(height, 0), max(width, 0)), dtype=_LE_U32)
        for x, y, gid in layer.cells():
            if 0 <= x < width and 0 <= y < height:
                grid[y, x] = gid
        obj["width"] = width
        obj["height"] = height
        obj["data"] = _encode_gids(grid, encoding, compression)
    obj["encoding"] = encoding
    if encoding == "base64" and compression not in (None, ""):
        obj["compression"] = compression
    return obj


def export_tilemap(
    tilemap: Tilemap,
    *,
    encoding: str = "csv",
    compression: Optional[str] = None,
) -> Dict[str, Any]:
    """Serialise ``tilemap`` to a Tiled 1.12.2 JSON map object (REQ-P6-DATA-001).

    Emits ``version``/``tiledversion``/``orientation``/``renderorder``/``infinite``
    /``nextlayerid``/``nextobjectid``, embedded tilesets (each with ``firstgid``
    and a lossless pixel embed), and per-layer tile data — ``chunks[]`` (16x16)
    for infinite maps, a dense ``data`` block for fixed maps. GIDs carry the full
    flip-flag nibble. Verbatim passthrough fields captured on import are
    re-emitted.

    Args:
        tilemap: The tilemap to export.
        encoding: ``"csv"`` (default) or ``"base64"``.
        compression: ``None`` (default), ``"gzip"`` or ``"zlib"`` — only with
            ``base64``.

    Raises:
        ProjectIOError: On an unsupported encoding/compression combination.
    """
    if not isinstance(tilemap, Tilemap):
        raise ProjectIOError(f"expected a Tilemap, got {tilemap!r}")
    if encoding not in ("csv", "base64"):
        raise ProjectIOError(f"unsupported encoding {encoding!r}")
    if encoding == "csv" and compression not in (None, ""):
        raise ProjectIOError("csv encoding does not support compression")
    if compression not in (None, "", "gzip", "zlib"):
        raise ProjectIOError(
            f"unsupported compression {compression!r} (emit none/gzip/zlib)"
        )

    passthrough = tilemap.tiled_passthrough or {}
    map_extra = dict(passthrough.get("map_extra", {}))
    tileset_extra = passthrough.get("tileset_extra", [])
    layer_records = passthrough.get("layers", None)

    bounds = _content_bounds(tilemap)
    map_obj: Dict[str, Any] = dict(map_extra)
    map_obj.update(
        {
            "type": "map",
            "version": _JSON_VERSION,
            "tiledversion": _TILED_VERSION,
            "orientation": _ORIENTATION,
            "renderorder": _RENDER_ORDER,
            "infinite": tilemap.infinite,
            "tilewidth": tilemap.tile_width,
            "tileheight": tilemap.tile_height,
            "compressionlevel": map_extra.get(
                "compressionlevel", _DEFAULT_COMPRESSION_LEVEL
            ),
        }
    )
    if bounds is None:
        map_obj["width"] = map_obj.get("width", 0)
        map_obj["height"] = map_obj.get("height", 0)
    else:
        map_obj["width"] = bounds[2] - bounds[0] + 1
        map_obj["height"] = bounds[3] - bounds[1] + 1

    tilesets_out: List[Dict[str, Any]] = []
    for i, ts in enumerate(tilemap.tilesets):
        extra = dict(tileset_extra[i]) if i < len(tileset_extra) else {}
        tilesets_out.append(_export_tileset(ts, extra))
    map_obj["tilesets"] = tilesets_out

    # Layers: interleave preserved non-tile layers (verbatim) with our tile
    # layers, honouring the original order captured on import when present.
    tile_layer_objs: List[Dict[str, Any]] = []
    for i, layer in enumerate(tilemap.layers):
        extra = {}
        if isinstance(layer_records, list):
            for rec in layer_records:
                if (
                    isinstance(rec, dict)
                    and rec.get("kind") == "tile"
                    and rec.get("index") == i
                ):
                    extra = dict(rec.get("extra", {}))
                    break
        tile_layer_objs.append(
            _export_tile_layer(
                tilemap, layer, i + 1, bounds, encoding, compression, extra
            )
        )

    if isinstance(layer_records, list):
        ordered: List[Dict[str, Any]] = []
        for rec in layer_records:
            if not isinstance(rec, dict):
                continue
            if rec.get("kind") == "other":
                ordered.append(dict(rec.get("raw", {})))
            elif rec.get("kind") == "tile":
                idx = rec.get("index")
                if isinstance(idx, int) and 0 <= idx < len(tile_layer_objs):
                    ordered.append(tile_layer_objs[idx])
        map_obj["layers"] = ordered
    else:
        map_obj["layers"] = tile_layer_objs

    map_obj["nextlayerid"] = map_extra.get("nextlayerid", len(tilemap.layers) + 1)
    map_obj["nextobjectid"] = map_extra.get("nextobjectid", 1)
    return map_obj


def write_tiled_json(
    path: Union[str, Path],
    tilemap: Tilemap,
    *,
    encoding: str = "csv",
    compression: Optional[str] = None,
) -> Path:
    """Export ``tilemap`` and write it as Tiled JSON to ``path`` (portable path)."""
    target = Path(path)
    payload = export_tilemap(tilemap, encoding=encoding, compression=compression)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


# --------------------------------------------------------------------------- #
# Import (defensive)                                                          #
# --------------------------------------------------------------------------- #


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


def _check_tile_dim(name: str, value: int) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and 1 <= value,
        f"{name} must be a positive int",
    )
    _require(
        value <= MAX_TILE_DIMENSION,
        f"{name} {value} exceeds MAX_TILE_DIMENSION ({MAX_TILE_DIMENSION})",
    )
    return value


def _check_coord(name: str, value: int) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{name} must be an int",
    )
    _require(
        abs(value) <= MAX_TILEMAP_COORD,
        f"{name} {value} exceeds MAX_TILEMAP_COORD ({MAX_TILEMAP_COORD})",
    )
    return value


def _import_tileset(
    entry: Any, base_dir: Optional[Path]
) -> Tuple[Tileset, Dict[str, Any]]:
    _require(isinstance(entry, dict), "each tileset entry must be a JSON object")
    firstgid = _get(entry, "firstgid", int)
    _require(firstgid >= 1, f"firstgid must be >= 1, got {firstgid}")

    source_ref = entry.get("source")
    if source_ref is not None:
        _require(isinstance(source_ref, str), "tileset source must be a string")
        if source_ref.lower().endswith(".tsx"):
            raise ProjectIOError(
                "external .tsx (XML) tilesets are unsupported; use embedded or "
                "external .tsj"
            )
        if not source_ref.lower().endswith(".tsj"):
            raise ProjectIOError(
                f"unsupported external tileset {source_ref!r} (only .tsj)"
            )
        if base_dir is None:
            raise ProjectIOError(
                "external .tsj tileset requires a base directory "
                "(use read_tiled_json)"
            )
        resolved = (base_dir / source_ref).resolve()
        try:
            external = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectIOError(
                f"cannot read external tileset {source_ref!r}: {exc}"
            ) from exc
        _require(isinstance(external, dict), "external tileset must be a JSON object")
        merged = dict(external)
        merged["firstgid"] = firstgid
        entry = merged

    tile_width = _check_tile_dim("tilewidth", _get(entry, "tilewidth", int))
    tile_height = _check_tile_dim("tileheight", _get(entry, "tileheight", int))
    margin = entry.get("margin", 0)
    spacing = entry.get("spacing", 0)
    _require(
        isinstance(margin, int) and not isinstance(margin, bool) and margin >= 0,
        "margin must be a non-negative int",
    )
    _require(
        isinstance(spacing, int) and not isinstance(spacing, bool) and spacing >= 0,
        "spacing must be a non-negative int",
    )
    name = entry.get("name", "Tileset")
    _require(isinstance(name, str), "tileset name must be a string")

    source = _decode_source(entry.get(_CUSTOM_SOURCE_KEY))
    if source is None:
        image_w = entry.get("imagewidth", 0)
        image_h = entry.get("imageheight", 0)
        _require(
            isinstance(image_w, int)
            and not isinstance(image_w, bool)
            and 1 <= image_w <= MAX_CANVAS_WIDTH,
            "imagewidth must be a positive int within canvas bounds",
        )
        _require(
            isinstance(image_h, int)
            and not isinstance(image_h, bool)
            and 1 <= image_h <= MAX_CANVAS_HEIGHT,
            "imageheight must be a positive int within canvas bounds",
        )
        source = PixelBuffer(image_w, image_h, ColorMode.RGBA)

    tileset = Tileset(
        source,
        tile_width=tile_width,
        tile_height=tile_height,
        margin=margin,
        spacing=spacing,
        name=name,
        first_gid=firstgid,
    )
    return tileset, _extra_fields(entry, _KNOWN_TILESET_KEYS)


def _set_cells(
    tilemap: Tilemap,
    layer: TilemapLayer,
    gids: np.ndarray,
    origin_x: int,
    origin_y: int,
    width: int,
    height: int,
) -> None:
    """Validate then place a decoded GID block onto ``layer`` (defensive)."""
    grid = gids.reshape((height, width))
    nz = np.argwhere(grid != 0)
    for row, col in nz:
        gid = int(grid[row, col])
        base = gid & GID_MASK
        # gid-in-tileset-range (strip ALL flag bits incl. diagonal, research §2.6)
        if base != 0:
            try:
                tilemap.resolve(base)
            except TilemapError as exc:
                raise ProjectIOError(f"gid out of tileset range: {exc}") from exc
        x = origin_x + int(col)
        y = origin_y + int(row)
        _check_coord("cell x", x)
        _check_coord("cell y", y)
        layer._display.set(x, y, gid)


def _import_tile_layer(
    tilemap: Tilemap, entry: Dict[str, Any]
) -> Tuple[TilemapLayer, Dict[str, Any]]:
    name = entry.get("name", "Layer")
    _require(isinstance(name, str), "layer name must be a string")
    opacity = entry.get("opacity", 1.0)
    _require(
        isinstance(opacity, (int, float)) and not isinstance(opacity, bool),
        "layer opacity must be a number",
    )
    _require(0.0 <= float(opacity) <= 1.0, "layer opacity out of range 0.0..1.0")
    visible = entry.get("visible", True)
    _require(isinstance(visible, bool), "layer visible must be a bool")
    encoding = entry.get("encoding", "csv")
    _require(isinstance(encoding, str), "layer encoding must be a string")
    compression = entry.get("compression")
    _require(
        compression is None or isinstance(compression, str),
        "layer compression must be a string or absent",
    )

    layer = TilemapLayer(name, visible=visible, opacity=float(opacity))

    if tilemap.infinite:
        chunks = _get(entry, "chunks", list)
        for chunk in chunks:
            _require(isinstance(chunk, dict), "each chunk must be a JSON object")
            cw = _get(chunk, "width", int)
            ch = _get(chunk, "height", int)
            _require(1 <= cw and 1 <= ch, "chunk size must be positive")
            _require(
                cw * ch <= _MAX_LAYER_BYTES // 4,
                "chunk payload exceeds the maximum allowed size",
            )
            ox = _check_coord("chunk x", _get(chunk, "x", int))
            oy = _check_coord("chunk y", _get(chunk, "y", int))
            gids = _decode_gids(chunk.get("data"), encoding, compression, cw * ch)
            _set_cells(tilemap, layer, gids, ox, oy, cw, ch)
    else:
        width = _get(entry, "width", int)
        height = _get(entry, "height", int)
        _require(0 <= width and 0 <= height, "layer size must be non-negative")
        _require(
            width * height <= _MAX_LAYER_BYTES // 4,
            "layer payload exceeds the maximum allowed size",
        )
        if width * height > 0:
            gids = _decode_gids(
                entry.get("data"), encoding, compression, width * height
            )
            _set_cells(tilemap, layer, gids, 0, 0, width, height)

    return layer, _extra_fields(entry, _KNOWN_TILELAYER_KEYS)


def import_tilemap(
    data: Dict[str, Any], *, base_dir: Optional[Union[str, Path]] = None
) -> Tilemap:
    """Reconstruct a :class:`Tilemap` from a Tiled JSON map object (defensive).

    Validates the map/tile geometry, orientation, tilesets and per-layer payloads
    (REQ-P6-DATA-002/-003), preserving unknown fields verbatim on
    ``Tilemap.tiled_passthrough`` for a lossless round-trip. Only ``orthogonal``
    maps are accepted; ``zstd`` compression and external ``.tsx`` tilesets raise
    :class:`ProjectIOError`.

    Args:
        data: A parsed Tiled JSON map dict.
        base_dir: Directory used to resolve external ``.tsj`` tileset references.

    Raises:
        ProjectIOError: On any malformed / out-of-bounds / unsupported field.
    """
    _require(isinstance(data, dict), "Tiled map must be a JSON object")
    _require(data.get("type", "map") == "map", "not a Tiled map object")
    orientation = data.get("orientation", _ORIENTATION)
    _require(isinstance(orientation, str), "orientation must be a string")
    if orientation != _ORIENTATION:
        raise ProjectIOError(
            f"unsupported orientation {orientation!r} (only {_ORIENTATION!r})"
        )
    infinite = data.get("infinite", False)
    _require(isinstance(infinite, bool), "infinite must be a bool")
    tile_width = _check_tile_dim("tilewidth", _get(data, "tilewidth", int))
    tile_height = _check_tile_dim("tileheight", _get(data, "tileheight", int))

    name = data.get("name")
    tilemap = Tilemap(
        name=name if isinstance(name, str) else "Tilemap",
        infinite=infinite,
        tile_width=tile_width,
        tile_height=tile_height,
    )

    resolved_dir = Path(base_dir) if base_dir is not None else None
    tilesets_raw = _get(data, "tilesets", list)
    tileset_extra: List[Dict[str, Any]] = []
    for entry in tilesets_raw:
        tileset, extra = _import_tileset(entry, resolved_dir)
        tilemap.tilesets.append(tileset)
        tileset_extra.append(extra)

    layers_raw = _get(data, "layers", list)
    layer_records: List[Dict[str, Any]] = []
    for entry in layers_raw:
        _require(isinstance(entry, dict), "each layer must be a JSON object")
        if entry.get("type") == "tilelayer":
            layer, extra = _import_tile_layer(tilemap, entry)
            index = len(tilemap.layers)
            tilemap.layers.append(layer)
            layer_records.append({"kind": "tile", "index": index, "extra": extra})
        else:
            # Object/image/group layers are not modelled: preserve verbatim.
            layer_records.append({"kind": "other", "raw": entry})

    tilemap.tiled_passthrough = {
        "map_extra": _extra_fields(data, _KNOWN_MAP_KEYS),
        "tileset_extra": tileset_extra,
        "layers": layer_records,
    }
    return tilemap


def read_tiled_json(path: Union[str, Path]) -> Tilemap:
    """Read and validate a Tiled JSON map file into a :class:`Tilemap`.

    External ``.tsj`` tileset references are resolved relative to ``path``'s
    directory. A malformed file raises :class:`ProjectIOError` (never a crash).
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectIOError(f"cannot read {target}: {exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProjectIOError(f"{target} is not valid JSON: {exc}") from exc
    return import_tilemap(payload, base_dir=target.parent)
