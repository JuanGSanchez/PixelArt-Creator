# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Portable, deterministic writers for export bytes + engine-preset artifacts.

This is the Qt-free ``data/`` file layer for Phase-7 export (REQ-P7-DATA-001/-002).
It performs **no re-encoding**: :func:`write_export` writes the exact bytes the
``logic/`` engine produced (byte-reproducibility is preserved from ``logic/``
through the write), and :func:`write_engine_preset` builds + writes the
engine-ready **artifact files** — a Unity 2022.3 LTS ``.meta`` YAML or a Godot 4.2
``SpriteFrames`` ``.tres`` — deterministically from the ``logic/``-computed
:class:`~pixelart_creator.logic.export.SheetMetadata` (the Phase-6 ``tiled_io.py``
precedent: a wire-format serialiser in ``data/`` over a ``logic/`` model, ADR-0018,
ADR-0020).

Paths are built with :mod:`pathlib` for portability (``path_portability_check``);
imports go **downward** (``data -> logic``) only — never ``logic -> data``. The
Unity/Godot format-version strings are module-local wire-format identifiers
(ADR-0001, like the Tiled ``tiledversion`` in ``tiled_io.py``). Deterministic
GUID/UID values are derived from a content hash of the layout, never from the
wall clock (ADR-0018/-0019).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Union

from pixelart_creator.logic.export import (
    EnginePreset,
    ExportResult,
    SheetMetadata,
    TagInfo,
)

__all__ = [
    "ExportWriteError",
    "write_export",
    "write_engine_preset",
]

PathLike = Union[str, Path]

# --- Engine wire-format identifiers (module-local, ADR-0001 / ADR-0018) ----------
_UNITY_TARGET_VERSION = "2022.3"  # Unity LTS the .meta schema targets (F-4 pin)
_UNITY_META_FILE_FORMAT = 2
_UNITY_SPRITE_IMPORT_MODE_MULTIPLE = 2
_UNITY_FILTER_MODE_POINT = 0
_UNITY_TEXTURE_COMPRESSION_NONE = 0
_UNITY_PIXELS_PER_UNIT = 100
_UNITY_SPRITE_CLASS_FILEID = 213  # Unity's classID for a Sprite sub-asset
_GODOT_TARGET_VERSION = "4.2"  # Godot minor the .tres header targets (F-5 pin)
_GODOT_TRES_FORMAT = 3
_GODOT_DEFAULT_ANIMATION = "default"
_GODOT_DEFAULT_FPS = 10.0


class ExportWriteError(ValueError):
    """Raised when an export artifact cannot be written (e.g. a bad preset)."""


# --------------------------------------------------------------------------- #
# Byte / JSON writer (no re-encode — byte-reproducibility preserved)           #
# --------------------------------------------------------------------------- #


def write_export(result: ExportResult, out_path: PathLike) -> None:
    """Write ``result.image_bytes`` (+ metadata JSON, if any) verbatim to disk.

    The image bytes are written **exactly** as the engine produced them — no
    re-encode or transformation that could add nondeterminism (REQ-P7-DATA-001).
    When ``result.metadata_json`` is present it is written to ``out_path`` with a
    ``.json`` suffix. Parent directories are created if missing. Paths use
    :mod:`pathlib` (portable).

    Raises:
        OSError: If the file(s) cannot be written (surfaced to the caller — the
            CLI maps it to a non-zero exit, the GUI to a user-facing message).

    REQ-P7-DATA-004.
    """
    target = Path(out_path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result.image_bytes)
    if result.metadata_json is not None:
        json_path = target.with_suffix(".json")
        json_path.write_text(result.metadata_json, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Engine-preset artifact writers (deterministic, ADR-0018)                     #
# --------------------------------------------------------------------------- #


def write_engine_preset(
    preset: EnginePreset, meta: SheetMetadata, image_path: PathLike
) -> None:
    """Write the engine-ready artifact for ``preset`` beside the exported image.

    - ``UNITY`` → a Unity 2022.3 ``.meta`` YAML (``<image>.meta``): Multiple sprite
      mode, Point filter, uncompressed, a populated ``spriteSheet.sprites[]`` with
      explicit y-up ``rect`` per frame (Unity's origin is bottom-left).
    - ``GODOT`` → a Godot 4.2 ``SpriteFrames`` ``.tres`` (``<image>.tres``): one
      ``AtlasTexture`` per frame (top-left ``region``, no y-flip) grouped into
      ``animations`` by the Phase-5 ``frameTags``.
    - ``NONE`` → no artifact (returns immediately).

    Both artifacts are deterministic and rotation-free (REQ-P7-DATA-002, ADR-0018).

    Raises:
        ExportWriteError: On an unknown preset.
        OSError: If the artifact cannot be written.
    """
    if preset is EnginePreset.NONE:
        return
    if preset is EnginePreset.UNITY:
        path = Path(str(image_path) + ".meta")
        # newline="\n": pin LF so the multi-line artifact is byte-identical on every
        # OS (no Windows CRLF translation) — cross-OS determinism (REQ-P13-DATA-003).
        path.write_text(_build_unity_meta(meta), encoding="utf-8", newline="\n")
        return
    if preset is EnginePreset.GODOT:
        path = Path(image_path).with_suffix(".tres")
        path.write_text(
            _build_godot_tres(meta, Path(image_path).name),
            encoding="utf-8",
            newline="\n",
        )
        return
    raise ExportWriteError(f"unknown engine preset {preset!r}")


def _content_hash(meta: SheetMetadata) -> str:
    """Return a stable 32-hex digest of the layout (deterministic GUID/UID seed)."""
    parts: List[str] = [
        _UNITY_TARGET_VERSION,
        _GODOT_TARGET_VERSION,
        meta.image_name,
        f"{meta.width}x{meta.height}",
    ]
    for r in meta.frames:
        parts.append(f"{r.name}:{r.x},{r.y},{r.w},{r.h}:{r.duration_ms}")
    for t in meta.tags:
        parts.append(f"tag:{t.name}:{t.from_index}-{t.to_index}:{t.direction}")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def _sprite_file_id(base: str, name: str) -> int:
    """Derive a stable positive Unity fileID for a sprite sub-asset."""
    digest = hashlib.sha256(f"{base}:{name}".encode("utf-8")).hexdigest()
    return int(digest[:15], 16)  # < 2^60, comfortably positive


def _build_unity_meta(meta: SheetMetadata) -> str:
    """Build a deterministic Unity 2022.3 ``.meta`` YAML for a Multiple-mode sheet.

    REQ-P7-LOGIC-011.
    """
    guid = _content_hash(meta)
    sprite_ids = {r.name: _sprite_file_id(guid, r.name) for r in meta.frames}

    lines: List[str] = []
    lines.append(f"fileFormatVersion: {_UNITY_META_FILE_FORMAT}")
    lines.append(f"guid: {guid}")
    lines.append(f"# pixelart-creator export; target Unity {_UNITY_TARGET_VERSION} LTS")
    lines.append("TextureImporter:")
    lines.append("  internalIDToNameTable:")
    for r in meta.frames:
        lines.append("  - first:")
        lines.append(f"      {_UNITY_SPRITE_CLASS_FILEID}: {sprite_ids[r.name]}")
        lines.append(f"    second: {r.name}")
    lines.append("  externalObjects: {}")
    lines.append("  mipmaps:")
    lines.append("    mipMapMode: 0")
    lines.append("    enableMipMap: 0")
    lines.append(f"  spriteMode: {_UNITY_SPRITE_IMPORT_MODE_MULTIPLE}")
    lines.append(f"  spritePixelsToUnits: {_UNITY_PIXELS_PER_UNIT}")
    lines.append(f"  filterMode: {_UNITY_FILTER_MODE_POINT}")
    lines.append(f"  textureCompression: {_UNITY_TEXTURE_COMPRESSION_NONE}")
    lines.append("  spriteSheet:")
    lines.append("    serializedVersion: 2")
    lines.append("    sprites:")
    for r in meta.frames:
        # Unity origin is bottom-left: flip y so the rect matches the top-left blit.
        rect_y = meta.height - r.y - r.h
        lines.append("    - serializedVersion: 2")
        lines.append(f"      name: {r.name}")
        lines.append("      rect:")
        lines.append("        serializedVersion: 2")
        lines.append(f"        x: {r.x}")
        lines.append(f"        y: {rect_y}")
        lines.append(f"        width: {r.w}")
        lines.append(f"        height: {r.h}")
        lines.append("      alignment: 0")
        lines.append("      pivot: {x: 0.5, y: 0.5}")
        lines.append("      border: {x: 0, y: 0, z: 0, w: 0}")
        lines.append(f"      internalID: {sprite_ids[r.name]}")
    lines.append("  nameFileIdTable:")
    for r in meta.frames:
        lines.append(f"    {r.name}: {sprite_ids[r.name]}")
    lines.append("  userData: ")
    lines.append("  assetBundleName: ")
    return "\n".join(lines) + "\n"


def _fmt_fps(value: float) -> str:
    """Format an fps float deterministically (fixed precision, trimmed)."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _tag_ranges(meta: SheetMetadata) -> List[TagInfo]:
    """Return the tags to emit as Godot animations (a synthetic default if none)."""
    if meta.tags:
        return list(meta.tags)
    last = len(meta.frames) - 1
    return [TagInfo(_GODOT_DEFAULT_ANIMATION, 0, max(last, 0), "forward")]


def _godot_loop(direction: str) -> str:
    """Map an Aseprite direction token to a Godot ``loop`` bool literal."""
    return "false" if direction == "" else "true"


def _build_godot_tres(meta: SheetMetadata, image_filename: str) -> str:
    """Build a deterministic Godot 4.2 ``SpriteFrames`` ``.tres`` for the sheet.

    REQ-P7-LOGIC-011.
    """
    uid = _content_hash(meta)
    ext_id = f"1_{uid[:8]}"
    sub_ids = {r.name: f"AtlasTexture_{r.name}" for r in meta.frames}
    load_steps = len(meta.frames) + 2

    lines: List[str] = []
    lines.append(
        f'[gd_resource type="SpriteFrames" load_steps={load_steps} '
        f'format={_GODOT_TRES_FORMAT} uid="uid://{uid[:13]}"]'
    )
    lines.append(f"; pixelart-creator export; target Godot {_GODOT_TARGET_VERSION}")
    lines.append("")
    lines.append(
        f'[ext_resource type="Texture2D" '
        f'path="res://{image_filename}" id="{ext_id}"]'
    )
    lines.append("")
    for r in meta.frames:
        lines.append(f'[sub_resource type="AtlasTexture" id="{sub_ids[r.name]}"]')
        lines.append(f'atlas = ExtResource("{ext_id}")')
        lines.append(f"region = Rect2({r.x}, {r.y}, {r.w}, {r.h})")
        lines.append("")

    frames_by_name = {r.name: r for r in meta.frames}
    animations: List[str] = []
    for tag in _tag_ranges(meta):
        frame_entries: List[str] = []
        durations: List[int] = []
        for idx in range(tag.from_index, tag.to_index + 1):
            name = str(idx)
            if name not in sub_ids:
                continue
            durations.append(frames_by_name[name].duration_ms)
            frame_entries.append(
                '{"duration": 1.0, "texture": ' f'SubResource("{sub_ids[name]}")}}'
            )
        mean_ms = sum(durations) / len(durations) if durations else 0
        fps = 1000.0 / mean_ms if mean_ms > 0 else _GODOT_DEFAULT_FPS
        animations.append(
            "{\n"
            '"frames": [' + ", ".join(frame_entries) + "],\n"
            f'"loop": {_godot_loop(tag.direction)},\n'
            f'"name": &"{tag.name}",\n'
            f'"speed": {_fmt_fps(fps)}\n'
            "}"
        )
    lines.append("[resource]")
    lines.append("animations = [" + ", ".join(animations) + "]")
    return "\n".join(lines) + "\n"
