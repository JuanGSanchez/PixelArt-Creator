# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Palette import/export encode/decode (defensive, zero Qt, S11).

Pure, Qt-free text transforms between a
:class:`~pixelart_creator.logic.palette.Palette` and three common palette
formats — GIMP ``.gpl``, JASC ``.pal``, and a plain ``hex`` list — reusing
:func:`~pixelart_creator.logic.color.to_hex` / ``from_hex``. Parsing is
**defensive**: no ``eval``/``exec``, and malformed input raises
:class:`PaletteIOError` (Article VII). Disk read/write is a thin UI/data concern
(REQ-P3-UI-002), not here. ``encode ∘ decode`` round-trips a palette for the
supported formats (SC-L016-1). REQ-P3-LOGIC-016.
"""

from __future__ import annotations

from typing import List

from pixelart_creator.logic.color import (
    CHANNEL_MAX,
    CHANNEL_MIN,
    RGBA,
    from_hex,
    to_hex,
)
from pixelart_creator.logic.palette import MAX_PALETTE_SIZE, Palette

__all__ = ["PaletteIOError", "encode", "decode"]

_FORMATS = ("gpl", "pal", "hex")
_GPL_HEADER = "GIMP Palette"
_PAL_HEADER = "JASC-PAL"
_PAL_VERSION = "0100"


class PaletteIOError(ValueError):
    """Raised when a palette cannot be encoded or a file is malformed on decode."""


def _check_fmt(fmt: str) -> str:
    if fmt not in _FORMATS:
        raise PaletteIOError(f"unknown format {fmt!r}; expected one of {_FORMATS}")
    return fmt


def encode(palette: Palette, fmt: str) -> str:
    """Encode ``palette`` to the text of ``fmt`` (``'gpl'`` / ``'pal'`` / ``'hex'``).

    ``gpl`` and ``pal`` carry RGB only (alpha is dropped); ``hex`` carries full
    ``#RRGGBBAA``. Deterministic (SC-L016-3).

    Raises:
        PaletteIOError: If ``fmt`` is unknown.
    """
    _check_fmt(fmt)
    colors = palette.colors()
    if fmt == "hex":
        return "\n".join(to_hex(c) for c in colors)
    if fmt == "gpl":
        lines = [_GPL_HEADER, "Name: PixelArt Creator", "Columns: 0", "#"]
        lines.extend(f"{c[0]} {c[1]} {c[2]}" for c in colors)
        return "\n".join(lines)
    # JASC-PAL
    lines = [_PAL_HEADER, _PAL_VERSION, str(len(colors))]
    lines.extend(f"{c[0]} {c[1]} {c[2]}" for c in colors)
    return "\n".join(lines)


def _parse_rgb_line(line: str) -> RGBA:
    parts = line.split()
    if len(parts) < 3:
        raise PaletteIOError(f"expected at least 3 channels, got {line!r}")
    try:
        channels = [int(parts[i]) for i in range(3)]
    except ValueError as exc:
        raise PaletteIOError(f"non-integer channel in {line!r}") from exc
    for value in channels:
        if not (CHANNEL_MIN <= value <= CHANNEL_MAX):
            raise PaletteIOError(f"channel {value} out of range in {line!r}")
    return (channels[0], channels[1], channels[2], CHANNEL_MAX)


def _decode_hex(text: str) -> List[RGBA]:
    colors: List[RGBA] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") and len(line.lstrip("#")) not in (3, 6, 8):
            # A bare "#" comment / blank line is skipped; a real colour has digits.
            continue
        try:
            colors.append(from_hex(line))
        except ValueError as exc:
            raise PaletteIOError(f"invalid hex colour {line!r}") from exc
    return colors


def _decode_gpl(text: str) -> List[RGBA]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != _GPL_HEADER:
        raise PaletteIOError("not a GIMP palette (missing 'GIMP Palette' header)")
    colors: List[RGBA] = []
    for raw in lines[1:]:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith(("name:", "columns:")):
            continue
        colors.append(_parse_rgb_line(line))
    return colors


def _decode_pal(text: str) -> List[RGBA]:
    lines = [ln.strip() for ln in text.splitlines()]
    if len(lines) < 3 or lines[0] != _PAL_HEADER:
        raise PaletteIOError("not a JASC palette (missing 'JASC-PAL' header)")
    if lines[1] != _PAL_VERSION:
        raise PaletteIOError(f"unsupported JASC-PAL version {lines[1]!r}")
    try:
        count = int(lines[2])
    except ValueError as exc:
        raise PaletteIOError(f"invalid JASC-PAL count {lines[2]!r}") from exc
    if count < 0:
        raise PaletteIOError(f"negative JASC-PAL count {count}")
    body = [ln for ln in lines[3:] if ln]
    if len(body) < count:
        raise PaletteIOError(f"JASC-PAL declares {count} colours but has {len(body)}")
    return [_parse_rgb_line(body[i]) for i in range(count)]


def decode(text: str, fmt: str) -> Palette:
    """Decode ``text`` in ``fmt`` to a :class:`Palette` (defensive, no eval/exec).

    ``encode ∘ decode`` round-trips a palette for supported formats (SC-L016-1).

    Raises:
        PaletteIOError: If ``fmt`` is unknown or the text is malformed
            (SC-L016-2), including exceeding ``MAX_PALETTE_SIZE``.
    """
    _check_fmt(fmt)
    if not isinstance(text, str):
        raise PaletteIOError(f"palette text must be a string, got {text!r}")
    if fmt == "hex":
        colors = _decode_hex(text)
    elif fmt == "gpl":
        colors = _decode_gpl(text)
    else:
        colors = _decode_pal(text)
    if len(colors) > MAX_PALETTE_SIZE:
        raise PaletteIOError(
            f"palette has {len(colors)} colours, exceeds {MAX_PALETTE_SIZE}"
        )
    return Palette(colors)
