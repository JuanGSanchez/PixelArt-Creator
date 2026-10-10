#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: derive_app_icons  (standalone product tooling script)
# =============================================================================
# PURPOSE: Regenerate the whole application-icon family from the five
#   committed, hand-drawn "Kikko Badge" masters
#   pixelart_creator/icons/app/logo-master-{16,24,32,48,64}.png. The badge is a
#   hexagon plate with its own ring (and, at 48 and 64 px, a gold hairline), so
#   there is no separate plate to draw and nothing is cropped: every member is
#   the whole master, or a whole-number nearest-neighbour upscale of one.
#
# THE RULE (applied to every member, checked by --check):
#   A member is a committed master of the SAME size at 1x, or a master of a
#   WHOLE-DIVISOR size scaled by an integer factor k with nearest-neighbour
#   sampling only. No other filter appears anywhere in this file, including in
#   the .ico and .icns assembly: nothing is left to a library's own resize
#   fallback, because every size those containers carry is supplied
#   explicitly. No tool redraws or resamples a pixel.
#
#     16, 24, 32, 48, 64 px    the master of that size, k = 1
#     128, 256, 512, 1024 px   the 64 px master, k = 2, 4, 8, 16
#     pixelart-creator.png     256 px, the same pixels as app-icon-256.png
#     favicon.png              the 32 px master, k = 1 (web viewer page icon)
#     .ico  members 16, 24, 32, 48, 64, 128, 256
#     .icns members 16, 32, 64, 128, 256, 512, 1024 px (11 entries: the 1x and
#           2x pairs of 16, 32, 128, 256 and 512, listed in ICNS_ENTRIES)
#
# USAGE:
#   python scripts/derive_app_icons.py             # (re)write every member
#   python scripts/derive_app_icons.py --check     # verify committed == derived
#   --app-dir DIR       the folder holding the masters and the PNG/.ico/.icns
#                       members (default: pixelart_creator/icons/app)
#   --favicon FILE      where favicon.png lives (default: web_viewer/static/
#                       favicon.png; when --app-dir is given without --favicon
#                       it is DIR/favicon.png, so a scratch run can never touch
#                       the web viewer's folder)
#
# WHAT --check VERIFIES (exit 1 on any failure, naming the file):
#   * the five masters exist and match their pinned sha256 (a master is copied
#     verbatim, never re-encoded, so byte identity is a real, portable promise);
#   * each master has the declared size, binary alpha, and only colours of the
#     declared palette (MASTER_PALETTE);
#   * border adjacency: with the 8-neighbourhood, no pixel of the C object
#     (easel wood, canvas, the painted C) touches the ring or the gold
#     hairline in any master. The P is NOT subject to this rule; its contact
#     with the border is printed as information and never fails the check;
#   * every PNG member, the favicon, every .ico frame and every .icns entry
#     equals the re-derived pixels. DECODED PIXELS are compared, never raw
#     bytes: a re-encoded PNG's byte stream depends on the platform's zlib and
#     libpng, so byte identity is not a promise this repository can keep across
#     operating systems, while pixel identity is;
#   * the generated construction table matches (deterministic text);
#   * the fill floor: the opaque artwork occupies at least FILL_RATIO_MIN of
#     the canvas in its larger dimension, measured on the derived pixels;
#   * the numbers examined are printed, and a run that examined nothing fails.
#
# RUNTIME: Python 3.8+, Pillow only (already a shipped dependency). Deterministic:
#   nearest-neighbour scaling and PNG/.ico/.icns assembly have no random or
#   clock-dependent component.
# =============================================================================

from __future__ import annotations

import argparse
import hashlib
import io
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Final, FrozenSet, List, Optional, Tuple

from PIL import Image

Rgb = Tuple[int, int, int]

# --- the masters -------------------------------------------------------------

#: The sizes (px) a master is drawn at. Each is hand-drawn at its own size.
MASTER_SIZES: Final[Tuple[int, ...]] = (16, 24, 32, 48, 64)


def master_name(size: int) -> str:
    """File name of the master drawn at ``size`` px."""
    return f"logo-master-{size}.png"


#: sha256 of each committed master, read from the committed files. A master is
#: copied verbatim and never re-encoded by this script, so byte identity is a
#: portable guarantee. After the user retouches a master, record the new value
#: here in the same change (the check names the master that moved).
MASTER_SHA256: Final[Dict[int, str]] = {
    16: "7bee151a235c7e12197c3dd2a0849882181fd03db20234f361d00c1aec163cca",
    24: "f044120628670a960f0b0c537e0570ca613bc21db8ad10fd5855a8c308310db6",
    32: "2f618d876abea1bd83c7cc05f97a885ffb0ff0de72f221e8fb8b10992b12f7eb",
    48: "72dc0f565cd8748c65d60eb797ebb830e38ef18dfe5dd0d5ea9300edec637359",
    64: "3562add912f8f6e681a47385504cc9857778ff1c7a4f5cde353edcea0bade4c1",
}

#: The opaque bounding box (x0, y0, x1, y1; x1/y1 exclusive) of each master,
#: measured with Image.getbbox() on the committed files - re-measure it if a
#: master is retouched. The 16 and 24 px badges fill their canvas edge to
#: edge; the larger ones keep a 2 px transparent margin. ``--check`` verifies
#: every entry against the loaded master, so this table cannot drift.
MASTER_OPAQUE_BBOX: Final[Dict[int, Tuple[int, int, int, int]]] = {
    16: (0, 0, 16, 16),
    24: (0, 0, 24, 24),
    32: (2, 2, 30, 30),
    48: (2, 2, 46, 46),
    64: (2, 2, 62, 62),
}

# --- the declared palette, by role (measured from the committed masters with
#     Image.getcolors(); the union of the five masters' opaque colours is
#     exactly the union of these four groups) ---------------------------------

#: The hexagon border: the ring, and the gold hairline (48 and 64 px only).
BORDER_COLORS: Final[FrozenSet[Rgb]] = frozenset(
    {
        (226, 55, 77),  # ring
        (255, 226, 122),  # hairline, lit
        (255, 197, 58),  # hairline, mid
        (201, 138, 16),  # hairline, shade
    }
)
#: The C object: easel wood (lit, mid, shade), the canvas (pale green and its
#: sheen) and the painted C (and its lit edge).
C_OBJECT_COLORS: Final[FrozenSet[Rgb]] = frozenset(
    {
        (224, 165, 95),
        (176, 108, 46),
        (112, 64, 31),
        (183, 235, 166),
        (227, 249, 208),
        (31, 107, 71),
        (62, 155, 102),
    }
)
#: The P: ink and its highlight. Reported against the border, never gated.
P_COLORS: Final[FrozenSet[Rgb]] = frozenset({(27, 20, 38), (90, 74, 130)})
#: The cream plate and its cast shade.
PLATE_COLORS: Final[FrozenSet[Rgb]] = frozenset({(255, 244, 214), (235, 215, 166)})

MASTER_PALETTE: Final[FrozenSet[Rgb]] = (
    BORDER_COLORS | C_OBJECT_COLORS | P_COLORS | PLATE_COLORS
)

#: Alpha values a master may carry (binary transparency).
ALPHA_OPAQUE: Final[int] = 255
ALPHA_CLEAR: Final[int] = 0

# --- the family --------------------------------------------------------------


@dataclass(frozen=True)
class Member:
    """One raster member: its name, canvas size, the master it is derived from
    and the integer factor.

    ``plate`` is True when the member carries the hexagon plate - every member
    does, because the plate is part of each master - and is what the fill floor
    applies to (see ``fill_exempt``).
    """

    name: str
    size: int  # B: the square canvas, in px
    master: int  # the master's size, a whole divisor of ``size``
    scale: int  # integer nearest-neighbour factor k = size // master
    plate: bool = True
    note: str = ""


#: The declared family, in the ruled directory pixelart_creator/icons/app/.
#: This IS the construction table: the committed CONSTRUCTION-TABLE.md is
#: rendered from this data and from the masters' own measured pixels.
FAMILY: Final[Tuple[Member, ...]] = (
    Member("app-icon-16.png", 16, 16, 1),
    Member("app-icon-24.png", 24, 24, 1),
    Member("app-icon-32.png", 32, 32, 1),
    Member("app-icon-48.png", 48, 48, 1),
    Member("app-icon-64.png", 64, 64, 1),
    Member(
        "app-icon-128.png",
        128,
        64,
        2,
        note="Also the in-app guide logo.",
    ),
    Member("app-icon-256.png", 256, 64, 4),
    Member("app-icon-512.png", 512, 64, 8),
    Member(
        "app-icon-1024.png",
        1024,
        64,
        16,
        note="Container-only member: the .icns 1024 px entry (a library's own "
        "internal resize would be a blur, so it is supplied explicitly).",
    ),
)

#: The AppImage's expected filename: the same pixels as the 256 px member,
#: under the name the AppImage build and the .desktop entry look for.
APPIMAGE_MEMBER: Final[Member] = Member(
    "pixelart-creator.png",
    256,
    64,
    4,
    note="Same construction as app-icon-256.png; a separate file because the "
    "AppImage packaging path names it explicitly.",
)

#: The web viewer's page icon. Lives outside the icons folder (see --favicon).
FAVICON_MEMBER: Final[Member] = Member(
    "favicon.png",
    32,
    32,
    1,
    note="Written to web_viewer/static/favicon.png.",
)

ALL_MEMBERS: Final[Tuple[Member, ...]] = FAMILY + (APPIMAGE_MEMBER, FAVICON_MEMBER)

#: Members whose files live in ``--app-dir`` (everything but the favicon).
APP_DIR_MEMBERS: Final[Tuple[Member, ...]] = FAMILY + (APPIMAGE_MEMBER,)

ICO_NAME: Final[str] = "pixelart-creator.ico"
ICNS_NAME: Final[str] = "pixelart-creator.icns"
CONSTRUCTION_TABLE_NAME: Final[str] = "CONSTRUCTION-TABLE.md"
FAVICON_DEFAULT_RELATIVE: Final[Tuple[str, ...]] = (
    "web_viewer",
    "static",
    "favicon.png",
)

#: Windows .ico member sizes (named explicitly so a future change to a library
#: default cannot silently change what ships).
ICO_SIZES: Final[Tuple[int, ...]] = (16, 24, 32, 48, 64, 128, 256)

#: macOS .icns entries: (OSType, pixel size). The 2x entries carry twice the
#: logical size in pixels - ic11 is 16 px @2x (32 px), ic12 32 px @2x (64 px),
#: ic13 128 px @2x (256 px), ic14 256 px @2x (512 px), ic10 512 px @2x (1024 px).
#: Every entry is a PNG stream of a family member of exactly that pixel size.
ICNS_ENTRIES: Final[Tuple[Tuple[str, int], ...]] = (
    ("icp4", 16),
    ("icp5", 32),
    ("icp6", 64),
    ("ic07", 128),
    ("ic08", 256),
    ("ic09", 512),
    ("ic10", 1024),
    ("ic11", 32),
    ("ic12", 64),
    ("ic13", 256),
    ("ic14", 512),
)

#: The distinct pixel sizes the .icns carries.
ICNS_SIZES: Final[Tuple[int, ...]] = tuple(sorted({s for _t, s in ICNS_ENTRIES}))

_ICO_MEMBER_NAMES: Final[Dict[int, str]] = {s: f"app-icon-{s}.png" for s in ICO_SIZES}
_ICNS_MEMBER_NAMES: Final[Dict[int, str]] = {s: f"app-icon-{s}.png" for s in ICNS_SIZES}

#: The artwork must fill at least this fraction of its canvas in the LARGER
#: dimension, for every member that carries the plate. Fill is part of
#: correctness: a mark that reads as a speck on a large card fails the intent
#: even when every provenance and sharpness check passes.
FILL_RATIO_MIN: Final[float] = 0.70


# --- family arithmetic -------------------------------------------------------


def family_problems() -> List[str]:
    """Return every way the declared family breaks the derivation rule.

    The rule: each member's master is one of the committed masters, its size is
    a whole multiple of the master's size, and ``scale`` is exactly that
    multiple.
    """
    problems: List[str] = []
    seen = set()
    for m in ALL_MEMBERS:
        if m.name in seen:
            problems.append(f"{m.name}: declared twice")
        seen.add(m.name)
        if m.master not in MASTER_SIZES:
            problems.append(f"{m.name}: master {m.master} is not a committed master")
            continue
        if m.size % m.master != 0:
            problems.append(
                f"{m.name}: size {m.size} is not a whole multiple of master {m.master}"
            )
        elif m.scale != m.size // m.master:
            problems.append(
                f"{m.name}: scale {m.scale} != {m.size} // {m.master} "
                f"= {m.size // m.master}"
            )
    for s in ICO_SIZES:
        if _ICO_MEMBER_NAMES[s] not in {m.name for m in FAMILY}:
            problems.append(f".ico size {s}: no family member app-icon-{s}.png")
    for s in ICNS_SIZES:
        if _ICNS_MEMBER_NAMES[s] not in {m.name for m in FAMILY}:
            problems.append(f".icns size {s}: no family member app-icon-{s}.png")
    return problems


def fill_ratio(member: Member) -> float:
    """The artwork's larger dimension as a fraction of the canvas, from the
    master's measured opaque box (``MASTER_OPAQUE_BBOX``) and the scale."""
    x0, y0, x1, y1 = MASTER_OPAQUE_BBOX[member.master]
    return max(x1 - x0, y1 - y0) * member.scale / member.size


def fill_exempt(member: Member) -> bool:
    """A member with no plate has no plate margin to under-fill. The exemption is
    expressed on that real property (``member.plate is False``), not on a size:
    a differently-sized plated member would not be silently exempted."""
    return not member.plate


def image_fill_ratio(im: Image.Image) -> float:
    """The opaque artwork's larger dimension over the canvas side, MEASURED on
    ``im`` (0.0 for a fully transparent image)."""
    box = im.getchannel("A").point(lambda a: 255 if a else 0).getbbox()
    if box is None:
        return 0.0
    return max(box[2] - box[0], box[3] - box[1]) / im.size[0]


# --- loading and rendering ---------------------------------------------------


def _open_rgba(path: Path) -> Image.Image:
    """Read ``path`` in BINARY and decode it to RGBA - the same path is used for a
    master and for a committed member, so both decode identically."""
    with open(path, "rb") as fh:
        data = fh.read()
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    return im


def load_masters(app_dir: Path) -> Dict[int, Image.Image]:
    """Load the five masters; refuse a missing file or a wrong size.

    Raises:
        SystemExit: A master is absent or not of its declared size.
    """
    masters: Dict[int, Image.Image] = {}
    for size in MASTER_SIZES:
        path = app_dir / master_name(size)
        if not path.is_file():
            raise SystemExit(f"derive_app_icons: master missing: {path}")
        im = _open_rgba(path)
        if im.size != (size, size):
            raise SystemExit(
                f"derive_app_icons: {path.name} is {im.size}, expected "
                f"{(size, size)}"
            )
        masters[size] = im
    return masters


def render_member(masters: Dict[int, Image.Image], member: Member) -> Image.Image:
    """The member's pixels: its master at 1x, or scaled by the integer ``scale``
    with NEAREST only. No crop, no plate, no composite: the master is the art."""
    master = masters[member.master]
    if member.scale == 1:
        return master.copy()
    side = member.master * member.scale
    return master.resize((side, side), Image.Resampling.NEAREST)


def render_all(masters: Dict[int, Image.Image]) -> Dict[str, Image.Image]:
    """Render every member by name."""
    return {m.name: render_member(masters, m) for m in ALL_MEMBERS}


def _png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


# --- container assembly ------------------------------------------------------


def _render_ico(rendered: Dict[str, Image.Image]) -> bytes:
    """Assemble the .ico from an explicit member list. Every size the writer will
    ask for is supplied pre-rendered, so its own thumbnail fallback (a LANCZOS
    resample, taken only for a size with no provided image) is never reached.

    The base image MUST be the LARGEST member: the writer takes its size gate
    from the base image alone and silently DROPS any requested size bigger than
    it before ever consulting ``append_images``."""
    images_desc = [
        rendered[_ICO_MEMBER_NAMES[s]] for s in sorted(ICO_SIZES, reverse=True)
    ]
    base, rest = images_desc[0], images_desc[1:]
    buf = io.BytesIO()
    base.save(
        buf,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=rest,
    )
    return buf.getvalue()


_ICNS_MAGIC: Final[bytes] = b"icns"
_ICNS_TOC: Final[bytes] = b"TOC "
_ICNS_HEADER: Final[int] = 8  # four-byte type + four-byte big-endian length


def _render_icns(rendered: Dict[str, Image.Image]) -> bytes:
    """Assemble the .icns by writing its container directly: a header, a table of
    contents, then one PNG stream per entry of ``ICNS_ENTRIES``.

    The container is written here (not by a library) so that every entry is a
    member of the family at exactly its own pixel size - there is no resize
    fallback to reach - and so that the 16 and 32 px entries at 1x can exist at
    all (the library's writer has no slot for them)."""
    streams = [
        (ostype, _png_bytes(rendered[_ICNS_MEMBER_NAMES[size]]))
        for ostype, size in ICNS_ENTRIES
    ]
    toc_len = _ICNS_HEADER + 8 * len(streams)
    body = b"".join(
        ostype.encode("ascii") + struct.pack(">I", _ICNS_HEADER + len(data)) + data
        for ostype, data in streams
    )
    toc = _ICNS_TOC + struct.pack(">I", toc_len)
    for ostype, data in streams:
        toc += ostype.encode("ascii") + struct.pack(">I", _ICNS_HEADER + len(data))
    total = _ICNS_HEADER + toc_len + len(body)
    return _ICNS_MAGIC + struct.pack(">I", total) + toc + body


def parse_icns(data: bytes) -> List[Tuple[str, bytes]]:
    """Return ``(OSType, payload)`` for every entry of an .icns, in file order
    (the table of contents is skipped).

    Raises:
        ValueError: The magic or an entry length is wrong.
    """
    if data[:4] != _ICNS_MAGIC:
        raise ValueError("not an icns file (bad magic)")
    total = struct.unpack(">I", data[4:8])[0]
    if total != len(data):
        raise ValueError(f"declared length {total} != actual {len(data)}")
    entries: List[Tuple[str, bytes]] = []
    pos = _ICNS_HEADER
    while pos < len(data):
        ostype = data[pos : pos + 4]
        length = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        if length < _ICNS_HEADER or pos + length > len(data):
            raise ValueError(f"bad entry length {length} at offset {pos}")
        if ostype != _ICNS_TOC:
            entries.append(
                (ostype.decode("ascii"), data[pos + _ICNS_HEADER : pos + length])
            )
        pos += length
    return entries


# --- the construction table --------------------------------------------------


def construction_table_text(
    masters: Dict[int, Image.Image], rendered: Dict[str, Image.Image]
) -> str:
    """Render CONSTRUCTION-TABLE.md from the family data and the measured pixels."""
    lines = [
        "# Application icon family - construction table",
        "",
        "Generated by `scripts/derive_app_icons.py` from its own `FAMILY` data and",
        "from the committed masters' measured pixels - do not hand-edit; regenerate",
        "with the deriver.",
        "",
        "Every member is a committed master of the same size (k = 1) or of a",
        "whole-divisor size scaled by an integer factor k with nearest-neighbour",
        "sampling only. Nothing is cropped, resampled or redrawn by a tool.",
        "",
        "## Masters (hand-drawn, one per shipped size)",
        "",
        "| File | Size | Opaque box (x0,y0,x1,y1) | Colours | sha256 |",
        "|---|---|---|---|---|",
    ]
    for size in MASTER_SIZES:
        im = masters[size]
        box = im.getchannel("A").point(lambda a: 255 if a else 0).getbbox()
        colours = sum(1 for _n, c in im.getcolors(maxcolors=100000) if c[3] == 255)
        lines.append(
            f"| {master_name(size)} | {size}x{size} | {box} | {colours} | "
            f"{MASTER_SHA256[size]} |"
        )
    lines += [
        "",
        "## Members",
        "",
        "Fill is the opaque artwork's larger dimension as a fraction of the canvas,",
        f"measured on the derived pixels; every member must be >= {FILL_RATIO_MIN:.0%}",
        "or the deriver's own `--check` fails it by name.",
        "",
        "| File | Canvas | Master | Scale k | Opaque box (w x h) | Fill | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in ALL_MEMBERS:
        im = rendered[m.name]
        box = im.getchannel("A").point(lambda a: 255 if a else 0).getbbox()
        assert box is not None
        bw, bh = box[2] - box[0], box[3] - box[1]
        lines.append(
            f"| {m.name} | {m.size}x{m.size} | {m.master} | {m.scale} | "
            f"{bw}x{bh} | {image_fill_ratio(im):.1%} | {m.note} |"
        )
    lines += [
        "",
        "## Container assembly",
        "",
        f"- `{ICO_NAME}` (Windows): members "
        f"{', '.join(str(s) for s in ICO_SIZES)} px, assembled explicitly - no size "
        "is left for a library's own resize fallback.",
        f"- `{ICNS_NAME}` (macOS): {len(ICNS_ENTRIES)} entries, each a PNG of a "
        "family member at exactly its pixel size, written by this script:",
    ]
    lines += [
        f"  - `{ostype}`: {size}x{size} px (`app-icon-{size}.png`)"
        for ostype, size in ICNS_ENTRIES
    ]
    lines.append("")
    return "\n".join(lines)


# --- comparison --------------------------------------------------------------


def _pixel_diff(committed: Image.Image, derived: Image.Image) -> Optional[str]:
    """Describe the first difference between two RGBA images, or ``None`` if they
    are pixel-for-pixel identical - size AND every channel of every pixel, no
    tolerance: every member is an exact integer nearest-neighbour scale of a
    master, so an exact match is the right bar (unlike the re-encoded byte
    stream a PNG/.ico/.icns container wraps it in)."""
    if committed.size != derived.size:
        cw, ch = committed.size
        dw, dh = derived.size
        return f"{cw}x{ch} committed != {dw}x{dh} re-derived"
    # Compare the raw RGBA buffers. (Not ``ImageChops.difference(...).getbbox()``:
    # on an RGBA image getbbox() looks at the ALPHA channel only, so a changed
    # colour on an opaque pixel - alpha 255 on both sides - would read as
    # "identical".)
    if committed.tobytes() == derived.tobytes():
        return None
    c_px = committed.load()
    d_px = derived.load()
    w, h = committed.size
    differing = 0
    first = None
    for y in range(h):
        for x in range(w):
            if c_px[x, y] != d_px[x, y]:
                differing += 1
                if first is None:
                    first = (x, y, c_px[x, y], d_px[x, y])
    assert first is not None  # the buffers differ, so some pixel does
    x, y, cv, dv = first
    return (
        f"{differing} pixel(s) differ (of {w * h}), first at ({x}, {y}): "
        f"committed {cv} != re-derived {dv}"
    )


def _compare_png(path: Path, derived: Image.Image, mismatches: List[str]) -> bool:
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False
    diff = _pixel_diff(_open_rgba(path), derived)
    if diff is not None:
        mismatches.append(f"{path.name}: {diff}")
        return False
    return True


def _compare_bytes(path: Path, data: bytes, mismatches: List[str]) -> bool:
    """Byte comparison, kept ONLY for deterministic text (the construction table)."""
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False
    with open(path, "rb") as fh:
        existing = fh.read()
    if existing != data:
        mismatches.append(
            f"{path.name}: {len(existing)} bytes committed != "
            f"{len(data)} bytes re-derived"
        )
        return False
    return True


def _extract_ico_frame(path: Path, size: int) -> Image.Image:
    """The documented way to read a SPECIFIC size out of a multi-image .ico:
    reopen the file and set ``.size`` before ``.load()``."""
    frame = Image.open(path)
    frame.size = (size, size)
    frame.load()
    return frame.convert("RGBA")


def _compare_ico(
    path: Path, rendered: Dict[str, Image.Image], mismatches: List[str]
) -> Tuple[bool, int]:
    """Compare every .ico frame; return (all identical, frames examined)."""
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False, 0
    ok = True
    examined = 0
    for size in ICO_SIZES:
        intended = rendered[_ICO_MEMBER_NAMES[size]]
        try:
            extracted = _extract_ico_frame(path, size)
        except Exception as exc:  # a genuinely corrupt/foreign .ico
            mismatches.append(f"{path.name} [{size}px member]: could not read - {exc}")
            ok = False
            continue
        examined += 1
        diff = _pixel_diff(extracted, intended)
        if diff is not None:
            mismatches.append(f"{path.name} [{size}px member]: {diff}")
            ok = False
    return ok, examined


def _compare_icns(
    path: Path, rendered: Dict[str, Image.Image], mismatches: List[str]
) -> Tuple[bool, int]:
    """Compare every .icns entry; return (all identical, entries examined)."""
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False, 0
    try:
        entries = parse_icns(path.read_bytes())
    except ValueError as exc:  # a genuinely corrupt/foreign .icns
        mismatches.append(f"{path.name}: could not read - {exc}")
        return False, 0
    found = {ostype: payload for ostype, payload in entries}
    ok = True
    examined = 0
    if len(found) != len(entries):
        mismatches.append(f"{path.name}: duplicate entry type(s)")
        ok = False
    unexpected = sorted(set(found) - {t for t, _s in ICNS_ENTRIES})
    if unexpected:
        mismatches.append(f"{path.name}: unexpected entry type(s) {unexpected}")
        ok = False
    for ostype, size in ICNS_ENTRIES:
        label = f"{path.name} [{ostype} {size}px entry]"
        payload = found.get(ostype)
        if payload is None:
            mismatches.append(f"{label}: missing from container")
            ok = False
            continue
        try:
            im = Image.open(io.BytesIO(payload))
            im.load()
            frame = im.convert("RGBA")
        except Exception as exc:
            mismatches.append(f"{label}: could not decode - {exc}")
            ok = False
            continue
        examined += 1
        diff = _pixel_diff(frame, rendered[_ICNS_MEMBER_NAMES[size]])
        if diff is not None:
            mismatches.append(f"{label}: {diff}")
            ok = False
    return ok, examined


# --- the master checks -------------------------------------------------------


def _sha256(path: Path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def check_master_pins(app_dir: Path) -> List[str]:
    """Return a mismatch line for every master whose sha256 is not its pin."""
    problems: List[str] = []
    for size in MASTER_SIZES:
        path = app_dir / master_name(size)
        if not path.exists():
            problems.append(f"{path.name}: missing on disk")
            continue
        digest = _sha256(path)
        if digest != MASTER_SHA256[size]:
            problems.append(
                f"{path.name}: sha256 {digest} != pinned {MASTER_SHA256[size]} "
                "(the master has changed; record its new sha256 deliberately)"
            )
    return problems


def master_palette_problems(masters: Dict[int, Image.Image]) -> List[str]:
    """Binary alpha, the declared opaque colours only, and the measured box."""
    problems: List[str] = []
    for size, im in masters.items():
        name = master_name(size)
        colours = im.getcolors(maxcolors=100000)
        assert colours is not None
        for _n, (r, g, b, a) in colours:
            if a not in (ALPHA_CLEAR, ALPHA_OPAQUE):
                problems.append(f"{name}: partial alpha {a} on colour {(r, g, b)}")
            elif a == ALPHA_OPAQUE and (r, g, b) not in MASTER_PALETTE:
                problems.append(f"{name}: colour {(r, g, b)} is not in the palette")
        box = im.getchannel("A").point(lambda a: 255 if a else 0).getbbox()
        if box != MASTER_OPAQUE_BBOX[size]:
            problems.append(
                f"{name}: opaque box {box} != declared {MASTER_OPAQUE_BBOX[size]}"
            )
    return problems


@dataclass(frozen=True)
class Adjacency:
    """Border adjacency of one group of pixels in one master."""

    group_pixels: int
    border_pixels: int
    touching: Tuple[Tuple[int, int], ...]


def adjacency(
    im: Image.Image, group: FrozenSet[Rgb], border: FrozenSet[Rgb] = BORDER_COLORS
) -> Adjacency:
    """Pixels of ``group`` (opaque colours) 8-adjacent to a pixel of ``border``.

    The 8-neighbourhood is the four edge neighbours and the four diagonals.
    """
    rgba = im.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size

    def colour(x: int, y: int) -> Optional[Rgb]:
        r, g, b, a = px[x, y]
        return (r, g, b) if a == ALPHA_OPAQUE else None

    group_px = border_px = 0
    touching: List[Tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            c = colour(x, y)
            if c in border:
                border_px += 1
            if c not in group:
                continue
            group_px += 1
            hit = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if (dx or dy) and 0 <= nx < w and 0 <= ny < h:
                        if colour(nx, ny) in border:
                            hit = True
            if hit:
                touching.append((x, y))
    return Adjacency(group_px, border_px, tuple(touching))


# --- the check ---------------------------------------------------------------


def _check(
    app_dir: Path,
    favicon: Path,
    masters: Dict[int, Image.Image],
    rendered: Dict[str, Image.Image],
) -> int:
    """Re-derive every member in memory and compare it against the committed tree."""
    mismatches: List[str] = []
    identical = 0
    examined = 0  # files that exist and were actually compared
    declared = len(APP_DIR_MEMBERS) + 4  # + favicon, .ico, .icns, table

    for problem in family_problems():
        mismatches.append(f"family: {problem}")

    targets = [(app_dir / m.name, m.name) for m in APP_DIR_MEMBERS]
    targets.append((favicon, FAVICON_MEMBER.name))
    for path, name in targets:
        examined += 1 if path.exists() else 0
        if _compare_png(path, rendered[name], mismatches):
            identical += 1

    ico_ok, ico_frames = _compare_ico(app_dir / ICO_NAME, rendered, mismatches)
    examined += 1 if ico_frames else 0
    identical += 1 if ico_ok else 0

    icns_ok, icns_entries = _compare_icns(app_dir / ICNS_NAME, rendered, mismatches)
    examined += 1 if icns_entries else 0
    identical += 1 if icns_ok else 0

    table_path = app_dir / CONSTRUCTION_TABLE_NAME
    table = construction_table_text(masters, rendered).encode("utf-8")
    examined += 1 if table_path.exists() else 0
    if _compare_bytes(table_path, table, mismatches):
        identical += 1

    if examined == 0:
        for line in mismatches:
            print(f"  MISMATCH: {line}")
        print("derive_app_icons --check: FAILED - compared zero files", file=sys.stderr)
        return 1

    print(
        f"derive_app_icons --check: compared {examined} of {declared} files, "
        f"{identical} identical (decoded pixels; plus {ico_frames} .ico frames and "
        f"{icns_entries} .icns entries; re-encoded byte streams are not compared - "
        "see the header)"
    )
    for line in mismatches:
        print(f"  MISMATCH: {line}")

    pin_problems = check_master_pins(app_dir)
    print(
        f"derive_app_icons --check: masters - {len(MASTER_SIZES)} examined, "
        f"{len(MASTER_SIZES) - len(pin_problems)} sha256 match"
    )
    for line in pin_problems:
        print(f"  MISMATCH: {line}")

    palette_problems = master_palette_problems(masters)
    print(
        f"derive_app_icons --check: master palette - {len(masters)} masters "
        f"examined, binary alpha, {len(MASTER_PALETTE)} declared colours, "
        f"{len(palette_problems)} problem(s)"
    )
    for line in palette_problems:
        print(f"  MISMATCH: {line}")

    adjacency_failures: List[str] = []
    c_examined: List[str] = []
    p_info: List[str] = []
    blind = False
    for size in MASTER_SIZES:
        c = adjacency(masters[size], C_OBJECT_COLORS)
        p = adjacency(masters[size], P_COLORS)
        c_examined.append(f"{size}:{c.group_pixels}")
        p_info.append(f"{size}:{len(p.touching)}")
        if c.group_pixels == 0 or c.border_pixels == 0:
            blind = True
            adjacency_failures.append(
                f"{master_name(size)}: examined no C-object pixels "
                f"({c.group_pixels}) or no border pixels ({c.border_pixels})"
            )
        if c.touching:
            adjacency_failures.append(
                f"{master_name(size)}: {len(c.touching)} C-object pixel(s) touch "
                f"the hexagon border, first at {c.touching[0]}"
            )
    touching_total = sum(
        len(adjacency(masters[size], C_OBJECT_COLORS).touching) for size in MASTER_SIZES
    )
    print(
        f"derive_app_icons --check: border adjacency (8-neighbourhood) - "
        f"{len(MASTER_SIZES)} masters examined, C-object pixels examined "
        f"{' '.join(c_examined)}, C-object pixels touching the border: "
        f"{touching_total} (gate: 0)"
    )
    print(
        "derive_app_icons --check: info (not gated) - P pixels touching the "
        f"border, by master: {' '.join(p_info)}"
    )
    for line in adjacency_failures:
        print(f"  ADJACENCY FAIL: {line}")

    # Fill is part of correctness. Measured on the DERIVED pixels, and
    # cross-checked against the figure the declared bbox table gives.
    checked = [m for m in ALL_MEMBERS if not fill_exempt(m)]
    fill_failures: List[str] = []
    for m in checked:
        measured = image_fill_ratio(rendered[m.name])
        if abs(measured - fill_ratio(m)) > 1e-9:
            fill_failures.append(
                f"{m.name}: measured fill {measured:.3f} != declared "
                f"{fill_ratio(m):.3f} (MASTER_OPAQUE_BBOX is out of date)"
            )
        if measured < FILL_RATIO_MIN:
            fill_failures.append(
                f"{m.name}: {m.size}px canvas, fill {measured:.0%} "
                f"< required {FILL_RATIO_MIN:.0%}"
            )
    print(
        f"derive_app_icons --check: minimum-fill check - "
        f"{len(checked)} plated members checked, "
        f"{len(checked) - len(fill_failures)} pass, "
        f"{len(fill_failures)} problem(s) against {FILL_RATIO_MIN:.0%}"
    )
    for line in fill_failures:
        print(f"  FILL FAIL: {line}")

    if blind or checked == []:
        return 1
    if (
        mismatches
        or pin_problems
        or palette_problems
        or adjacency_failures
        or fill_failures
    ):
        return 1
    return 0


# --- the driver --------------------------------------------------------------


def run(app_dir: Path, favicon: Path, check: bool) -> int:
    pin_problems = check_master_pins(app_dir)
    if pin_problems and not check:
        for line in pin_problems:
            print(f"  MISMATCH: {line}", file=sys.stderr)
        print(
            "derive_app_icons: refusing to derive from an unpinned master",
            file=sys.stderr,
        )
        return 1
    masters = load_masters(app_dir)
    rendered = render_all(masters)

    if check:
        return _check(app_dir, favicon, masters, rendered)

    outputs: List[Tuple[Path, bytes]] = [
        (app_dir / m.name, _png_bytes(rendered[m.name])) for m in APP_DIR_MEMBERS
    ]
    outputs.append((favicon, _png_bytes(rendered[FAVICON_MEMBER.name])))
    outputs.append((app_dir / ICO_NAME, _render_ico(rendered)))
    outputs.append((app_dir / ICNS_NAME, _render_icns(rendered)))
    outputs.append(
        (
            app_dir / CONSTRUCTION_TABLE_NAME,
            construction_table_text(masters, rendered).encode("utf-8"),
        )
    )

    written = 0
    for path, data in outputs:
        with open(path, "wb") as fh:  # binary write - images and generated text
            fh.write(data)
        written += 1

    print(f"derive_app_icons: wrote {written} files under {app_dir} (and {favicon})")
    if written == 0:
        print("derive_app_icons: FAILED - wrote zero files", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    repo = Path(__file__).resolve().parent.parent
    default_app_dir = repo / "pixelart_creator" / "icons" / "app"
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--app-dir",
        default=None,
        help="directory holding the five masters and the derived family "
        "(default: pixelart_creator/icons/app/ next to this script)",
    )
    ap.add_argument(
        "--favicon",
        default=None,
        help="path of favicon.png (default: web_viewer/static/favicon.png; with "
        "--app-dir and no --favicon, DIR/favicon.png)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="re-derive into memory and compare against the committed files "
        "(decoded pixels for PNG/.ico/.icns members, real bytes for the "
        "construction table and the masters' sha256); exit non-zero on any "
        "mismatch (does not write)",
    )
    args = ap.parse_args(argv)

    app_dir = Path(args.app_dir) if args.app_dir else default_app_dir
    if args.favicon:
        favicon = Path(args.favicon)
    elif args.app_dir:
        favicon = app_dir / FAVICON_MEMBER.name
    else:
        favicon = repo.joinpath(*FAVICON_DEFAULT_RELATIVE)

    if not app_dir.is_dir():
        print(f"derive_app_icons: not a directory: {app_dir}", file=sys.stderr)
        return 2
    if not favicon.parent.is_dir():
        print(
            f"derive_app_icons: favicon folder does not exist: {favicon.parent}",
            file=sys.stderr,
        )
        return 2

    return run(app_dir, favicon, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
