#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: derive_app_icons  (standalone product tooling script)
# =============================================================================
# PURPOSE: Regenerate the whole application-icon raster family from the one
#   committed provenance master, pixelart_creator/icons/app/logo-source-64.png
#   (a byte-identical copy of the maintainer's own pixel art). Every derived
#   raster is produced by an integer nearest-neighbour crop-and-scale of that
#   master's own pixels — never a redraw, never a non-integer resample, and
#   never a change to the source file itself.
#
# USAGE:
#   python scripts/derive_app_icons.py            # (re)write every member
#   python scripts/derive_app_icons.py --check     # verify committed == derived
#
# RUNTIME: Python 3.8+, Pillow only (already a shipped dependency). No other
#   third-party import. Deterministic: run twice on a clean tree, get the same
#   bytes both times (nearest-neighbour scaling and flat-fill plate drawing
#   are exact, reproducible integer operations with no random or
#   platform-dependent component).
#
# THE VISUAL SYSTEM (decided once, applied to every member):
#   - Three source marks are cropped straight out of the 64x64 master, at
#     their native resolution, with no pixel altered:
#       * the full lockup   -- bbox (14, 17, 49, 44), 35x27 px, "P" + easel
#       * the easel alone   -- bbox (33, 27, 49, 44), 16x17 px
#       * the "P" alone     -- bbox (14, 17, 31, 44), 17x27 px, used at
#         32/64 px in place of the easel since 2026-09-01 as a fill-ratio
#         remedy -- see the member notes on those two Members below
#     A fourth mark is a crop OF the easel crop, trimming its 2-row top peg,
#     used only for the 16 px member (see EASEL_CROPPED_BBOX below and the
#     app-icon-16.png member note).
#   - Every scale factor is a whole number, applied with PIL's NEAREST
#     resampling only. No other filter appears anywhere in this file,
#     including inside the .ico/.icns assembly (see _render_ico/_render_icns).
#   - The "plate" is a flat, single-fill, hard-edged (no anti-aliasing) white
#     rounded square drawn full-bleed across the whole canvas, UNDER the
#     artwork -- the plate is a ground composited behind the artwork, never
#     drawn on top of it.
#     Corner radius is a fixed 20% of the canvas size. Members too small to
#     carry a plate with any real margin ship plateless instead.
#   - FILL is part of correctness, added 2026-09-01: every PLATED
#     member's artwork must occupy >= 70% of its canvas in the larger
#     dimension, enforced by --check (see FILL_RATIO_MIN/fill_ratio/
#     fill_exempt below). The mark-per-size assignment above exists BECAUSE
#     of this rule -- the original 32/64 px members (easel/lockup at their
#     only fitting whole-number scale) measured 53%/55% fill, a defect that
#     passed every prior structural/provenance/contrast check because none
#     of them measured fill.
#   - `--check` compares DECODED PIXELS, not raw bytes, for every re-encoded
#     PNG/.ico/.icns member -- fixed 2026-09-01 after CI's Linux leg caught
#     what the maintainer's own Windows-only local runs could not: the same
#     NEAREST-scaled pixels compress to a different zlib/libpng byte stream
#     depending on the platform's Pillow/libpng build (one member even came
#     out SMALLER on Linux while every other came out larger -- a compressor
#     difference, never a content one). Byte-identity of a re-encoded PNG is
#     not a promise this repository can keep across platforms; pixel-identity
#     is the promise every acceptance criterion here was actually reaching
#     for. The ONE exception is `logo-source-64.png`: it is copied verbatim,
#     never re-encoded, so its byte-identity (pinned as SOURCE_SHA256 above)
#     is a real, portable guarantee and `--check` still asserts it exactly.
# =============================================================================

from __future__ import annotations

import argparse
import hashlib
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from PIL import Image, ImageChops, ImageDraw

# --- the provenance master --------------------------------------------------

SOURCE_NAME: Final[str] = "logo-source-64.png"
SOURCE_SIZE: Final[tuple[int, int]] = (64, 64)

#: sha256 of the committed master, copied verbatim from the maintainer's own
#: file and never re-encoded by this script (see the "--check compares
#: decoded pixels" note below: this ONE file is the exception, because it is
#: the one guarantee this repository can actually keep bytewise -- there is
#: no encoder in the loop to make non-portable).
SOURCE_SHA256: Final[str] = (
    "b8ff4705e89232ad1cda1379c6118fe45dc29c21a3fb6adc45f7d80fbc3adf69"
)

# --- mark geometry, measured against the committed master (do not guess -
#     re-derive with Image.getbbox()/getcolors() if the master ever changes) -

#: The full lockup: black "P" beside the pale-green easel, tight alpha crop.
FULL_LOCKUP_BBOX: Final[tuple[int, int, int, int]] = (14, 17, 49, 44)  # 35x27

#: The easel sub-mark alone, native crop.
EASEL_BBOX: Final[tuple[int, int, int, int]] = (33, 27, 49, 44)  # 16x17

#: The easel sub-mark with its 2-row top peg trimmed (rows y=27..28 of the
#: source dropped), used ONLY for the 16 px member -- see the app-icon-16.png
#: member note below: at 16 px no row-crop can create the horizontal margin
#: a rounded plate needs, because the easel is exactly 16 px wide at scale 1.
EASEL_CROPPED_BBOX: Final[tuple[int, int, int, int]] = (33, 29, 49, 44)  # 16x15

#: The "P" sub-mark alone, tight alpha crop within the lockup's own x-range
#: (measured with Image.getbbox() restricted to x in [14, 31) against the
#: committed master -- opaque pixels only, black (0,0,0,255) core plus its
#: (64,64,64,255) anti-aliasing rim). Used at 32/64 px (a fill-ratio remedy
#: added 2026-09-01): the black "P" carries the strongest contrast of any
#: element against the white plate, and a white plate is now guaranteed at
#: every size that carries one.
P_MARK_BBOX: Final[tuple[int, int, int, int]] = (14, 17, 31, 44)  # 17x27

#: The "P" sub-mark's x-range in source coordinates. No opaque pixel of the
#: 16/24 px (easel-only) members may originate from this range -- that is
#: what would make them "the lockup mis-scaled" instead of "the easel alone".
P_REGION_X: Final[tuple[int, int]] = (14, 31)

_MARK_BBOX: Final[dict[str, tuple[int, int, int, int]]] = {
    "lockup": FULL_LOCKUP_BBOX,
    "easel": EASEL_BBOX,
    "easel_cropped": EASEL_CROPPED_BBOX,
    "p_mark": P_MARK_BBOX,
}

# --- the plate ---------------------------------------------------------------

PLATE_COLOR: Final[tuple[int, int, int, int]] = (255, 255, 255, 255)
PLATE_RADIUS_RATIO: Final[float] = 0.20  # corner radius, as a fraction of B


@dataclass(frozen=True)
class Member:
    """One raster member of the family: its name, canvas size, which mark it
    carries, at what integer scale, and whether it sits on the white plate."""

    name: str
    size: int  # B: the square canvas, in px
    mark: str  # "lockup" | "easel" | "easel_cropped" | "p_mark"
    scale: int  # integer nearest-neighbour factor k
    plate: bool
    note: str = ""


#: The declared family, in the ruled directory pixelart_creator/icons/app/.
#: This IS the construction table: every field the table is asked to name
#: is a field of Member, and construction_table_text() below renders
#: it to the committed CONSTRUCTION-TABLE.md verbatim from this data - the
#: table can never drift from what the deriver actually produces.
FAMILY: Final[tuple[Member, ...]] = (
    Member(
        "app-icon-16.png",
        16,
        "easel_cropped",
        1,
        False,
        "Plateless. At k=1 the easel is exactly 16 px wide, matching "
        "the box width with ZERO horizontal margin at any crop depth - no "
        "amount of vertical cropping can create the side margin a plate "
        "needs to read as a rounded square rather than a flush-edge fill. "
        "The 2-row top peg (source y=27-28) is trimmed so the mark's 17 px "
        "height fits the 16 px box; this is a real, recorded crop, "
        "not the plate-margin crop that was rejected.",
    ),
    Member("app-icon-24.png", 24, "easel", 1, True),
    Member(
        "app-icon-32.png",
        32,
        "p_mark",
        1,
        True,
        "Amendment made 2026-09-01 to meet the fill-ratio requirement: the "
        "lockup (35px) and the easel (17px tall, 53% fill) both under-fill "
        "this box. The 'P' sub-mark at k=1 gives 27px art (84% fill) and, "
        "now that the white plate guarantees a light ground at every size "
        "that carries one, is also the highest-contrast element available "
        "(black on white) - the easel's dark-taskbar rationale no longer "
        "applies.",
    ),
    Member("app-icon-48.png", 48, "lockup", 1, True),
    Member(
        "app-icon-64.png",
        64,
        "p_mark",
        2,
        True,
        "Amendment made 2026-09-01 to meet the fill-ratio requirement: the "
        "lockup at k=1 gave 35px art, 55% fill. The 'P' sub-mark at k=2 "
        "gives 34x54 art (84% fill) and the same plate-guarantees-contrast "
        "reasoning as app-icon-32.png. k=2 is the only whole-number factor "
        "that both improves fill and keeps the art inside the 64px box "
        "(k=3 would give 51x81, taller than the canvas).",
    ),
    Member("app-icon-128.png", 128, "lockup", 3, True),
    Member("app-icon-256.png", 256, "lockup", 6, True),
    Member("app-icon-512.png", 512, "lockup", 12, True),
    Member(
        "app-icon-1024.png",
        1024,
        "lockup",
        24,
        True,
        "ICNS-container-only member: not part of the OS-requested "
        "small/mid/large size ask. Pillow's ICNS writer's internal size "
        "table (PIL.IcnsImagePlugin._save) always includes a 1024 px "
        "entry; a size not supplied to it explicitly is produced by its "
        "own im.resize() call, which defaults to a non-nearest filter -- "
        "a BICUBIC resample, confirmed by measuring this deriver's own "
        "output directly. Supplying this member as an explicit "
        "append_images entry makes that resize call unreachable for every "
        "required ICNS size.",
    ),
)

#: The AppImage's expected filename, same construction as the 256 px
#: family member (same mark, same scale, same plate) but shipped under the
#: name build_appimage.sh/the .desktop entry look for.
APPIMAGE_MEMBER: Final[Member] = Member(
    "pixelart-creator.png",
    256,
    "lockup",
    6,
    True,
    "Identical construction to app-icon-256.png; a separate file "
    "because the AppImage packaging path names it explicitly.",
)

ALL_MEMBERS: Final[tuple[Member, ...]] = FAMILY + (APPIMAGE_MEMBER,)

ICO_NAME: Final[str] = "pixelart-creator.ico"
ICNS_NAME: Final[str] = "pixelart-creator.icns"

#: Windows .ico member sizes (Pillow's own ICO default list - named
#: explicitly here so a future change to that default cannot silently change
#: what ships).
ICO_SIZES: Final[tuple[int, ...]] = (16, 24, 32, 48, 64, 128, 256)

#: macOS .icns member sizes actually read by PIL.IcnsImagePlugin.IcnsFile.SIZES
#: (the widths of {ic07, ic08, ic09, ic10, ic11, ic12, ic13, ic14}).
ICNS_SIZES: Final[tuple[int, ...]] = (32, 64, 128, 256, 512, 1024)

_ICO_MEMBER_NAMES: Final[dict[int, str]] = {s: f"app-icon-{s}.png" for s in ICO_SIZES}
_ICNS_MEMBER_NAMES: Final[dict[int, str]] = {s: f"app-icon-{s}.png" for s in ICNS_SIZES}


# --- geometry helpers ---------------------------------------------------------


def art_box(member: Member) -> tuple[int, int]:
    """The scaled artwork's (width, height) in px, before it is centred."""
    x0, y0, x1, y1 = _MARK_BBOX[member.mark]
    return (x1 - x0) * member.scale, (y1 - y0) * member.scale


def art_offset(member: Member) -> tuple[int, int]:
    """Where the artwork's top-left lands on the BxB canvas (centred)."""
    aw, ah = art_box(member)
    return (member.size - aw) // 2, (member.size - ah) // 2


def plate_radius(member: Member) -> int:
    return round(member.size * PLATE_RADIUS_RATIO)


#: Every PLATED member's artwork must occupy at least this fraction of
#: its canvas in the LARGER dimension. Fill is part of correctness, not
#: taste - a mark that reads as a speck on a large white card fails the
#: maintainer's own request ("the icon should be bigger to fit correctly
#: the space") even though it passes every provenance/sharpness/contrast
#: check (those checks measured only that and nothing else, and passed
#: 60/60 while two members sat at 53% and 55% fill).
FILL_RATIO_MIN: Final[float] = 0.70


def fill_ratio(member: Member) -> float:
    """The artwork's larger dimension as a fraction of the canvas size."""
    aw, ah = art_box(member)
    return max(aw, ah) / member.size


def fill_exempt(member: Member) -> bool:
    """A PLATELESS member has no plate margin to under-fill in the first
    place - it is drawn full-bleed against the canvas edge by construction
    (see app-icon-16.png's own note). The exemption is expressed on that
    real property, `member.plate is False`, rather than as a special case
    on the number 16 - a differently-sized future plateless member is
    exempt for the same reason, and a differently-sized future PLATED
    member at 16 px would NOT be silently exempted just because it shares
    that size."""
    return not member.plate


# --- rendering -----------------------------------------------------------------


def load_source(app_dir: Path) -> Image.Image:
    path = app_dir / SOURCE_NAME
    with open(path, "rb") as fh:  # binary: this is an image, never text-mode
        data = fh.read()
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    if im.size != SOURCE_SIZE:
        raise SystemExit(
            f"derive_app_icons: source master is {im.size}, expected "
            f"{SOURCE_SIZE} - geometry constants in this file were measured "
            f"against a different master and must be re-derived"
        )
    return im


def render_member(source: Image.Image, member: Member) -> Image.Image:
    """Crop the mark straight from the source (no resample), scale it by the
    declared integer factor with NEAREST only, draw the plate (if any) flat
    and hard-edged straight onto the canvas, and composite the art on top."""
    bbox = _MARK_BBOX[member.mark]
    mark = source.crop(bbox)  # exact integer crop - not a resize
    aw, ah = art_box(member)
    art = mark.resize((aw, ah), Image.Resampling.NEAREST)

    canvas = Image.new("RGBA", (member.size, member.size), (0, 0, 0, 0))
    if member.plate:
        draw = ImageDraw.Draw(canvas)
        b = member.size - 1
        draw.rounded_rectangle(
            [(0, 0), (b, b)], radius=plate_radius(member), fill=PLATE_COLOR
        )
    left, top = art_offset(member)
    canvas.alpha_composite(art, (left, top))
    return canvas


def _png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _render_ico(rendered: dict[str, Image.Image]) -> bytes:
    """Assemble the .ico from an explicit member list. Every size
    Pillow's ICO writer will ask for is supplied pre-rendered and pre-sized,
    so PIL.IcoImagePlugin._save's own LANCZOS thumbnail() fallback path
    (taken only for a size with no matching provided image) is never
    reached.

    The base image MUST be the LARGEST member: PIL.IcoImagePlugin._save
    takes its size gate from the base image alone (`width, height =
    im.size`) and silently DROPS any requested size bigger than it
    (`if size[0] > width: continue`) before ever consulting append_images,
    so the image passed to save() must be the largest member or the
    larger sizes are dropped without warning."""
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


def _render_icns(rendered: dict[str, Image.Image]) -> bytes:
    """Assemble the .icns from an explicit member list. Every
    width PIL.IcnsImagePlugin._save's internal `sizes` table can ask for is
    supplied via append_images, keyed by width, so its own im.resize() blur
    fallback -- a BICUBIC resample, not nearest-neighbour -- is never
    reached for any of the 6 required sizes."""
    images = [rendered[_ICNS_MEMBER_NAMES[s]] for s in ICNS_SIZES]
    base, rest = images[0], images[1:]
    buf = io.BytesIO()
    base.save(buf, format="ICNS", append_images=rest)
    return buf.getvalue()


# --- the construction table ----------------------------------------------------

CONSTRUCTION_TABLE_NAME: Final[str] = "CONSTRUCTION-TABLE.md"


def construction_table_text() -> str:
    lines = [
        "# Application icon family - construction table",
        "",
        "Generated by `scripts/derive_app_icons.py` from this file's own",
        "`FAMILY` data - do not hand-edit; regenerate with the deriver.",
        "",
        "Every member is an integer nearest-neighbour crop-and-scale of",
        "`logo-source-64.png` (never a resample, never a redrawn pixel;",
        "see the module docstring for the declared visual system).",
        "",
        "Fill is the artwork's larger dimension as a fraction of the canvas",
        f"size; every PLATED member must be >= {FILL_RATIO_MIN:.0%}",
        "or the deriver's own `--check` fails it by name. Plateless members",
        "are exempt (full-bleed by construction, no plate margin to under-fill).",
        "",
        "| File | Canvas | Mark | Scale k | Art box | Fill | Plate "
        "| Margin (l,t) | Note |",
        "|---|---|---|---|---|---|---|---|---|---|"[:-1],
    ]
    for m in ALL_MEMBERS:
        aw, ah = art_box(m)
        left, top = art_offset(m)
        plate = (
            f"white rounded square, r={plate_radius(m)}px"
            if m.plate
            else "none (plateless)"
        )
        fill = f"{fill_ratio(m):.0%}" + (" (exempt)" if fill_exempt(m) else "")
        note = m.note or ""
        lines.append(
            f"| {m.name} | {m.size}x{m.size} | {m.mark} | {m.scale} | "
            f"{aw}x{ah} | {fill} | {plate} | {left}px, {top}px | {note} |"
        )
    lines.append("")
    lines.append("## Container assembly")
    lines.append("")
    lines.append(
        f"- `{ICO_NAME}` (Windows): members {', '.join(str(s) for s in ICO_SIZES)} px, "
        "assembled explicitly - no size is left for Pillow's own resize fallback."
    )
    lines.append(
        f"- `{ICNS_NAME}` (macOS): members {', '.join(str(s) for s in ICNS_SIZES)} px, "
        "assembled explicitly for the same reason (the 1024 px member exists only "
        "for this container - see its row above)."
    )
    lines.append("")
    return "\n".join(lines)


# --- driver ----------------------------------------------------------------


def _open_rgba(path: Path) -> Image.Image:
    """Read ``path`` in BINARY and decode it to RGBA -- the same load path
    ``load_source`` uses, so a committed file is decoded identically here and
    when the family is regenerated."""
    with open(path, "rb") as fh:
        data = fh.read()
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    return im


def _pixel_diff(committed: Image.Image, derived: Image.Image) -> Optional[str]:
    """Describe the first difference between two RGBA images, or ``None`` if
    they are pixel-for-pixel identical -- size AND every channel of every
    pixel, no tolerance: every mark in this family is an exact integer
    nearest-neighbour crop-and-scale or a flat fill, so an exact match is
    always the right bar, unlike the re-encoded byte stream a PNG/.ico/.icns
    container wraps it in (see the module docstring's 2026-09-01 note).

    ``ImageChops.difference().getbbox()`` is a fast all-pass short-circuit
    for the common (CI-green) case; the per-pixel scan below only runs once a
    real difference is already known to exist, to name the differing-pixel
    COUNT and the first differing COORDINATE rather than merely "they
    differ".
    """
    if committed.size != derived.size:
        cw, ch = committed.size
        dw, dh = derived.size
        return f"{cw}x{ch} committed != {dw}x{dh} re-derived"

    if ImageChops.difference(committed, derived).getbbox() is None:
        return None

    c_px = committed.load()
    d_px = derived.load()
    w, h = committed.size
    differing = 0
    first = None
    for y in range(h):
        for x in range(w):
            cv = c_px[x, y]
            dv = d_px[x, y]
            if cv != dv:
                differing += 1
                if first is None:
                    first = (x, y, cv, dv)
    assert first is not None  # getbbox() already proved a difference exists
    x, y, cv, dv = first
    return (
        f"{differing} pixel(s) differ (of {w * h}), first at ({x}, {y}): "
        f"committed {cv} != re-derived {dv}"
    )


def _compare_png(path: Path, derived: Image.Image, mismatches: list[str]) -> bool:
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False
    diff = _pixel_diff(_open_rgba(path), derived)
    if diff is not None:
        mismatches.append(f"{path.name}: {diff}")
        return False
    return True


def _compare_bytes(path: Path, data: bytes, mismatches: list[str]) -> bool:
    """Byte comparison, kept ONLY for the generated construction table -- a
    deterministic text file with no encoder in the loop to make
    non-portable."""
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
    """The Pillow-documented way to read a SPECIFIC size out of a
    multi-image .ico: reopen the file and set ``.size`` before ``.load()``
    -- the same extraction path
    ``testing/suites/scripts/test_derive_app_icons.py`` uses in its own
    pixel-identity proof, so the CLI check and the test suite trust one
    mechanism."""
    frame = Image.open(path)
    frame.size = (size, size)
    frame.load()
    return frame.convert("RGBA")


def _compare_ico(
    path: Path, rendered: dict[str, Image.Image], mismatches: list[str]
) -> bool:
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False
    ok = True
    for size in ICO_SIZES:
        intended = rendered[_ICO_MEMBER_NAMES[size]]
        try:
            extracted = _extract_ico_frame(path, size)
        except Exception as exc:  # a genuinely corrupt/foreign .ico
            mismatches.append(f"{path.name} [{size}px member]: could not read - {exc}")
            ok = False
            continue
        diff = _pixel_diff(extracted, intended)
        if diff is not None:
            mismatches.append(f"{path.name} [{size}px member]: {diff}")
            ok = False
    return ok


def _extract_icns_frames(path: Path) -> dict[int, Image.Image]:
    with Image.open(path) as icns:
        by_physical_size: dict[int, Image.Image] = {}
        for entry in icns.info["sizes"]:
            frame = icns.icns.getimage(entry)
            by_physical_size.setdefault(frame.size[0], frame.convert("RGBA"))
        return by_physical_size


def _compare_icns(
    path: Path, rendered: dict[str, Image.Image], mismatches: list[str]
) -> bool:
    if not path.exists():
        mismatches.append(f"{path.name}: missing on disk")
        return False
    try:
        frames = _extract_icns_frames(path)
    except Exception as exc:  # a genuinely corrupt/foreign .icns
        mismatches.append(f"{path.name}: could not read - {exc}")
        return False
    ok = True
    for size in ICNS_SIZES:
        intended = rendered[_ICNS_MEMBER_NAMES[size]]
        frame = frames.get(size)
        if frame is None:
            mismatches.append(f"{path.name} [{size}px member]: missing from container")
            ok = False
            continue
        diff = _pixel_diff(frame, intended)
        if diff is not None:
            mismatches.append(f"{path.name} [{size}px member]: {diff}")
            ok = False
    return ok


def _compare_source_hash(app_dir: Path, mismatches: list[str]) -> bool:
    """``logo-source-64.png`` is never re-derived -- it IS the master, copied
    verbatim by the maintainer, never re-encoded by this script. Its
    guarantee is real byte-identity (a sha256 pin), not pixel-identity: a
    portable guarantee a re-encoded PNG cannot make (see the module
    docstring), and the one this file can actually keep."""
    path = app_dir / SOURCE_NAME
    if not path.exists():
        mismatches.append(f"{SOURCE_NAME}: missing on disk")
        return False
    with open(path, "rb") as fh:
        data = fh.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        mismatches.append(
            f"{SOURCE_NAME}: sha256 {digest} != expected {SOURCE_SHA256} "
            "(the provenance master itself has changed)"
        )
        return False
    return True


def _check(app_dir: Path, rendered: dict[str, Image.Image]) -> int:
    """Re-derive every member in memory and compare it against the committed
    tree: DECODED PIXELS for every re-encoded PNG/.ico/.icns member (a
    PNG/.ico/.icns byte stream is not portable across platforms/encoder
    versions -- see the module docstring), real BYTES for the generated
    construction table and for the provenance master's sha256 (neither has an
    encoder in the loop), plus the minimum-fill floor."""
    mismatches: list[str] = []
    identical = 0
    total = 0

    for member in ALL_MEMBERS:
        total += 1
        if _compare_png(app_dir / member.name, rendered[member.name], mismatches):
            identical += 1

    total += 1
    if _compare_ico(app_dir / ICO_NAME, rendered, mismatches):
        identical += 1

    total += 1
    if _compare_icns(app_dir / ICNS_NAME, rendered, mismatches):
        identical += 1

    total += 1
    construction_data = construction_table_text().encode("utf-8")
    if _compare_bytes(app_dir / CONSTRUCTION_TABLE_NAME, construction_data, mismatches):
        identical += 1

    if total == 0:
        print("derive_app_icons --check: FAILED - compared zero files", file=sys.stderr)
        return 1

    print(
        f"derive_app_icons --check: compared {total} files, {identical} identical "
        "(decoded pixels for PNG/.ico/.icns members; re-encoded byte streams "
        "are not compared - see the module docstring)"
    )
    if mismatches:
        for line in mismatches:
            print(f"  MISMATCH: {line}")

    provenance_mismatches: list[str] = []
    provenance_ok = _compare_source_hash(app_dir, provenance_mismatches)
    print(
        f"derive_app_icons --check: provenance master - {SOURCE_NAME} "
        f"{'sha256 matches' if provenance_ok else 'CHANGED, sha256 mismatch'} "
        f"(expected {SOURCE_SHA256})"
    )
    if provenance_mismatches:
        for line in provenance_mismatches:
            print(f"  MISMATCH: {line}")

    # Fill is part of correctness. Every PLATED member's larger
    # dimension must be >= FILL_RATIO_MIN of its canvas; plateless
    # members are exempt because they carry no plate margin to
    # under-fill (fill_exempt() docstring). Checked over ALL_MEMBERS
    # (not just FAMILY) so pixelart-creator.png is covered too.
    checked = [m for m in ALL_MEMBERS if not fill_exempt(m)]
    fill_failures: list[str] = []
    for m in checked:
        ratio = fill_ratio(m)
        if ratio < FILL_RATIO_MIN:
            fill_failures.append(
                f"{m.name}: {m.size}px canvas, fill {ratio:.0%} "
                f"< required {FILL_RATIO_MIN:.0%}"
            )
    print(
        f"derive_app_icons --check: minimum-fill check - "
        f"{len(checked)} plated members checked, "
        f"{len(checked) - len(fill_failures)} pass, "
        f"{len(fill_failures)} below {FILL_RATIO_MIN:.0%}"
    )
    if fill_failures:
        for line in fill_failures:
            print(f"  FILL FAIL: {line}")

    if mismatches or provenance_mismatches or fill_failures:
        return 1
    return 0


def run(app_dir: Path, check: bool) -> int:
    source = load_source(app_dir)

    rendered: dict[str, Image.Image] = {}
    for member in ALL_MEMBERS:
        rendered[member.name] = render_member(source, member)

    if check:
        return _check(app_dir, rendered)

    outputs: list[tuple[str, bytes]] = [
        (m.name, _png_bytes(rendered[m.name])) for m in ALL_MEMBERS
    ]
    outputs.append((ICO_NAME, _render_ico(rendered)))
    outputs.append((ICNS_NAME, _render_icns(rendered)))
    outputs.append((CONSTRUCTION_TABLE_NAME, construction_table_text().encode("utf-8")))

    written = 0
    for name, data in outputs:
        with open(
            app_dir / name, "wb"
        ) as fh:  # binary write - these are images/generated text
            fh.write(data)
        written += 1

    print(f"derive_app_icons: wrote {written} files under {app_dir}")
    if written == 0:
        print("derive_app_icons: FAILED - wrote zero files", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    default_app_dir = (
        Path(__file__).resolve().parent.parent / "pixelart_creator" / "icons" / "app"
    )
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--app-dir",
        default=str(default_app_dir),
        help="directory holding logo-source-64.png and the derived family "
        "(default: pixelart_creator/icons/app/ next to this script)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="re-derive into memory and compare against the committed files "
        "(decoded pixels for PNG/.ico/.icns members, real bytes for the "
        "construction table and the provenance master's sha256); exit "
        "non-zero on any mismatch (does not write)",
    )
    args = ap.parse_args(argv)

    app_dir = Path(args.app_dir)
    if not app_dir.is_dir():
        print(f"derive_app_icons: not a directory: {app_dir}", file=sys.stderr)
        return 2

    return run(app_dir, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
