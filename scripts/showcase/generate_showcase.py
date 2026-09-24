# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
"""Showcase-media generator.

One script, four sub-commands: ``art``, ``screenshots``, ``social``, ``check``.
Every input and output path is a CLI argument, including the product root;
nothing here hard-codes a drive letter or an absolute path. Every deterministic
unit runs through the product's own Python API or its shipped CLI entry points
(``pixelart-run`` / ``pixelart-export``, invoked in-process via their ``main``
functions so the exact code the installed console scripts call is what runs).

Phase A destination: a job's ``review/showcase/`` staging folder (this script's
own directory, plus sibling ``art`` / ``screenshots`` / ``social`` folders).
Phase B destination: this file moves verbatim to ``scripts/showcase/`` in the
product repository; nothing above changes for that move because every path is
already a CLI argument.

Phase B placement (2026-09-24, the showcase-media placement ruling fixed the
publish destination at ``docs/images/``): this file now lives at
``scripts/showcase/generate_showcase.py`` inside the product repository
itself, so every path argument below defaults relative to THIS file's own
location (``Path(__file__).resolve().parents[2]`` is the repo root) rather
than requiring every caller to spell every path out. Defaults:
``--product-root`` the repo root this script lives under; ``--review-dir``
that root's ``docs/images``; ``--out-dir`` the matching ``docs/images/<kind>``
subfolder per sub-command; ``--tmp-dir`` that root's ``dev-docs/showcase-tmp``
(already ``.gitignore``d there, layer (b) -- never committed, and never a path
outside this product repository). Every default is still a plain CLI argument
that can
be overridden; nothing is hard-coded beyond this file's own location. No
change to any art-building function below -- the shared palette, the character
walk cycle, the scene, the tilemap and the procgen curation are byte-for-byte
what revision 3 (user review round 2) approved, so a regeneration from the
same product commit reproduces the same decoded pixels.

Revision round 2 (a follow-up pass on reviewer feedback): raised the art
to a competent pixel-art standard behind one shared, hue-shifted palette
(``PALETTE_RAMPS``), fixed the offscreen screenshot font database (tofu boxes),
added a text-render control to ``check``, rebalanced the social preview and
gave its icon a legible light badge, and split the README budget into a PNG
ceiling and a GIF ceiling.

Revision 3 (user review round 2 -- a new request carrying the user's actual
verdict on revision 2, not a self-initiated re-open): the character animation
was approved as-is and is untouched. Three fixes: (1) the layered-scene tree
-- the trunk now runs up into the canopy (extended trunk, a branch fork, the
canopy's lower edge overlapping both, a foliage-shadow patch at the join)
instead of floating above it; the tilemap's only decoration with any canopy
shape (``bush``) was checked and carries no trunk, so it never had this
defect. (2) Screenshots are re-captured with the UI language forced to
English through the product's own ``LanguageManager.set_language("en")`` (the
same call the real Language menu action makes) in the isolated settings
process, and the application font forced to the real Windows UI font (Segoe
UI, 9pt) before ``create_app`` builds the window; the layers dock is widened
before its shot so the blend-mode combo shows "Normal" in full rather than
being squeezed to "Norm". (3) ``check`` gained X.7 (language control -- no
string from the Spanish ``.ts`` catalogue appears in any captured widget's
text, denominator = texts examined) and X.8 (font control -- the effective
``QApplication`` font family equals the requested family and that family
exists in ``QFontDatabase``).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

#: This script's own path, product-root-relative. Provenance never carries
#: this session's real (absolute) location -- only this relative name (HARD
#: RULES: never hard-code a drive letter or an absolute path in a provenance
#: file).
GENERATOR_RELPATH = "scripts/showcase/generate_showcase.py"

#: The repo root this script lives under -- two levels up from
#: ``scripts/showcase/generate_showcase.py``. Used only to compute CLI
#: argument DEFAULTS (every default stays overridable; nothing downstream
#: reads this constant directly instead of ``args.product_root``).
DEFAULT_PRODUCT_ROOT = str(Path(__file__).resolve().parents[2])

REQUIRED_PROVENANCE_FIELDS = [
    "output",
    "command",
    "generator_path",
    "generator_sha256",
    "inputs",
    "product_commit",
    "product_dirty",
    "python_version",
    "pyside6_version",
    "pillow_version",
    "numpy_version",
    "qt_platform",
    "output_sha256",
    "output_size_bytes",
    "timestamp_utc",
]


# --------------------------------------------------------------------------- #
# CLI path defaults (Phase B: product-relative, no path outside this repo)
# --------------------------------------------------------------------------- #


def _resolve_review_dir(args) -> None:
    if getattr(args, "review_dir", None) is None:
        args.review_dir = str(Path(args.product_root) / "docs" / "images")


def _resolve_tmp_dir(args) -> None:
    if getattr(args, "tmp_dir", None) is None:
        args.tmp_dir = str(Path(args.product_root) / "dev-docs" / "showcase-tmp")


def _resolve_out_dir(args, kind: str) -> None:
    """``kind`` is the ``docs/images/<kind>`` leaf -- ``art``, ``screenshots``
    or ``social`` -- resolved under the already-resolved ``--review-dir``."""
    if getattr(args, "out_dir", None) is None:
        args.out_dir = str(Path(args.review_dir) / kind)


# --------------------------------------------------------------------------- #
# product import wiring
# --------------------------------------------------------------------------- #


def _add_product_root(product_root: str) -> None:
    root = str(Path(product_root).resolve())
    if root not in sys.path:
        sys.path.insert(0, root)


def load_product_modules(product_root: str) -> dict:
    """Import every product symbol the generator needs and return them by name."""
    _add_product_root(product_root)
    from pixelart_creator.data.export_io import write_export
    from pixelart_creator.data.macro_io import save_macro
    from pixelart_creator.data.project_io import load_project, save_project
    from pixelart_creator.logic.animation import FrameTag, PlaybackMode
    from pixelart_creator.logic.autotile import (
        BLOB_TILE_COUNT,
        AutotileRuleset,
        mask_from_neighbours,
        resolve_display_index,
    )
    from pixelart_creator.logic.document import Document, Frame, Layer
    from pixelart_creator.logic.export import (
        ExportFormat,
        ExportRequest,
        export_document,
    )
    from pixelart_creator.logic.macro import Op, record
    from pixelart_creator.logic.palette import Palette
    from pixelart_creator.logic.palette_ops import remap_colors
    from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
    from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
    from pixelart_creator.logic.tileset import Tileset
    from pixelart_creator.logic.transform import TransformError, scale_nearest

    return {
        "Document": Document,
        "Frame": Frame,
        "Layer": Layer,
        "Palette": Palette,
        "PixelBuffer": PixelBuffer,
        "ColorMode": ColorMode,
        "FrameTag": FrameTag,
        "PlaybackMode": PlaybackMode,
        "scale_nearest": scale_nearest,
        "TransformError": TransformError,
        "Tileset": Tileset,
        "Tilemap": Tilemap,
        "TilemapLayer": TilemapLayer,
        "AutotileRuleset": AutotileRuleset,
        "BLOB_TILE_COUNT": BLOB_TILE_COUNT,
        "mask_from_neighbours": mask_from_neighbours,
        "resolve_display_index": resolve_display_index,
        "remap_colors": remap_colors,
        "export_document": export_document,
        "ExportRequest": ExportRequest,
        "ExportFormat": ExportFormat,
        "Op": Op,
        "record": record,
        "save_project": save_project,
        "load_project": load_project,
        "save_macro": save_macro,
        "write_export": write_export,
    }


# --------------------------------------------------------------------------- #
# provenance (C2)
# --------------------------------------------------------------------------- #


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_provenance(product_root: str) -> dict:
    root = str(Path(product_root).resolve())
    commit = "unresolved"
    dirty = None
    try:
        out = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit = out.stdout.strip()
    except Exception as exc:  # noqa: BLE001 - defensive, recorded not raised
        commit = f"unresolved ({exc})"
    try:
        out = subprocess.run(
            ["git", "-C", root, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        dirty = bool(out.stdout.strip())
    except Exception:  # noqa: BLE001
        dirty = None
    return {"commit": commit, "dirty": dirty}


def tool_versions() -> dict:
    versions = {"python": sys.version.split()[0]}
    try:
        import PIL

        versions["pillow"] = PIL.__version__
    except Exception:  # noqa: BLE001
        versions["pillow"] = "unavailable"
    try:
        import PySide6

        versions["pyside6"] = PySide6.__version__
    except Exception:  # noqa: BLE001
        versions["pyside6"] = "not imported"
    try:
        import numpy

        versions["numpy"] = numpy.__version__
    except Exception:  # noqa: BLE001
        versions["numpy"] = "unavailable"
    return versions


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.name


class ProvenanceLog:
    """Accumulates one C2 entry per output file; writes provenance.json +
    PROVENANCE.md."""

    def __init__(self, review_dir: Path, product_root: str, generator_file: Path):
        self.review_dir = review_dir
        self.product_root = product_root
        self.generator_file = generator_file
        self.product_git = git_provenance(product_root)
        self.versions = tool_versions()
        self.path_json = review_dir / "provenance.json"
        self.path_md = review_dir / "PROVENANCE.md"
        self.entries = []
        if self.path_json.exists():
            try:
                self.entries = json.loads(self.path_json.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                self.entries = []

    def add(
        self, *, output_path: Path, command, inputs, qt_platform="n/a", extra=None
    ) -> dict:
        rel = _rel(output_path, self.review_dir)
        entry = {
            "output": rel,
            "command": " ".join(str(c) for c in command),
            "generator_path": GENERATOR_RELPATH,
            "generator_sha256": (
                sha256_file(self.generator_file)
                if self.generator_file.exists()
                else None
            ),
            "inputs": inputs,
            "product_commit": self.product_git["commit"],
            "product_dirty": self.product_git["dirty"],
            "python_version": self.versions["python"],
            "pyside6_version": self.versions["pyside6"],
            "pillow_version": self.versions["pillow"],
            "numpy_version": self.versions["numpy"],
            "qt_platform": qt_platform,
            "output_sha256": sha256_file(output_path) if output_path.exists() else None,
            "output_size_bytes": (
                output_path.stat().st_size if output_path.exists() else None
            ),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if extra:
            entry.update(extra)
        self.entries = [e for e in self.entries if e.get("output") != rel]
        self.entries.append(entry)
        return entry

    def prune_missing(self) -> None:
        """Drop any loaded entry whose output file no longer exists on disk.

        A re-run that renames or drops a produced file (e.g. an upscale
        factor changed between revisions) must not leave a stale provenance
        row pointing at a file that is gone -- X.4 completeness is about the
        files that actually exist now, not every file ever produced.
        """
        self.entries = [
            e for e in self.entries if (self.review_dir / e["output"]).exists()
        ]

    def save(self) -> None:
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.path_json.write_text(
            json.dumps(self.entries, indent=2, sort_keys=True), encoding="utf-8"
        )
        lines = [
            "# PROVENANCE",
            "",
            "Generator-written. One entry per output file.",
            "",
        ]
        for entry in sorted(self.entries, key=lambda x: x["output"]):
            lines.append(f"## {entry['output']}")
            for key in sorted(entry):
                if key == "output":
                    continue
                lines.append(f"- {key}: {entry[key]}")
            lines.append("")
        self.path_md.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# a tiny in-platform pixel font (set_pixel only) -- no font file, no Qt/Pillow
# text rendering. Upper-case only glyphs; strings are upper-cased at draw time
# (declared art direction: small-caps lettering).
# --------------------------------------------------------------------------- #

FONT_5X7 = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "###..", "#....", "#....", "#####"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "N": ["#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#..#.", "#...#", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "X": ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
}


def draw_text(buffer, text, x0, y0, color, *, scale=1, spacing=1) -> int:
    """Draw upper-cased ``text`` into ``buffer`` one pixel at a time (set_pixel)."""
    cursor_x = x0
    for ch in text.upper():
        glyph = FONT_5X7.get(ch, FONT_5X7[" "])
        for row_idx, row in enumerate(glyph):
            for col_idx, bit in enumerate(row):
                if bit != "#":
                    continue
                for sx in range(scale):
                    for sy in range(scale):
                        px = cursor_x + col_idx * scale + sx
                        py = y0 + row_idx * scale + sy
                        if buffer.in_bounds(px, py):
                            buffer.set_pixel(px, py, color)
        cursor_x += 5 * scale + spacing * scale
    return cursor_x


def text_width(text, *, scale=1, spacing=1) -> int:
    if not text:
        return 0
    return len(text) * (5 * scale) + (len(text) - 1) * spacing * scale


# --------------------------------------------------------------------------- #
# the shared master palette -- one cohesive, hue-shifted set of ramps used by
# every piece of art in this delivery (character, scene, tilemap, procgen
# curation and the social preview). Declared in ART-DIRECTION.md as well;
# this constant is that same declaration made executable. Shadows are shifted
# cooler (toward blue/green), highlights warmer (toward yellow), per ramp.
# --------------------------------------------------------------------------- #

PALETTE_RAMPS = {
    "outline": (18, 16, 20, 255),
    "sky_hi": (198, 227, 241, 255),
    "sky_lo": (109, 175, 213, 255),
    "cloud": (250, 248, 240, 255),
    "sun": (255, 231, 150, 255),
    "green_shadow": (46, 100, 58, 255),
    "green_base": (80, 150, 78, 255),
    "green_hi": (142, 202, 114, 255),
    "wood_shadow": (54, 34, 24, 255),
    "wood_base": (102, 68, 42, 255),
    "wood_hi": (154, 110, 68, 255),
    "wall_shadow": (176, 138, 100, 255),
    "wall_base": (222, 186, 146, 255),
    "wall_hi": (245, 220, 182, 255),
    "roof_shadow": (108, 40, 38, 255),
    "roof_base": (172, 68, 56, 255),
    "roof_hi": (214, 112, 82, 255),
    "window_glow": (252, 226, 142, 255),
    "water_shadow": (40, 82, 150, 255),
    "water_base": (72, 132, 204, 255),
    "water_hi": (144, 200, 236, 255),
    "stone_shadow": (86, 86, 98, 255),
    "stone_base": (130, 130, 144, 255),
    "stone_hi": (182, 182, 198, 255),
    "skin_shadow": (168, 114, 84, 255),
    "skin_base": (222, 164, 120, 255),
    "skin_hi": (250, 208, 168, 255),
    "tunic_shadow": (40, 92, 86, 255),
    "tunic_base": (72, 150, 128, 255),
    "tunic_hi": (140, 210, 168, 255),
    "gold": (240, 196, 88, 255),
    "flower_pink": (232, 120, 150, 255),
    "flower_white": (250, 248, 240, 255),
    "badge_light": (240, 240, 236, 255),
}


def P(name):
    return PALETTE_RAMPS[name]


def master_palette(mods):
    """A fresh ``Palette`` carrying every distinct colour in ``PALETTE_RAMPS``."""
    Palette = mods["Palette"]
    seen = []
    for c in PALETTE_RAMPS.values():
        if c not in seen:
            seen.append(c)
    return Palette(seen)


#: 4x4 ordered (Bayer) dither matrix, values 0..15 -- used to dither a
#: two-colour gradient (art direction: "dithered gradient sky") without any
#: continuous colour blend (a limited-palette pixel-art technique, not a
#: Qt/Pillow gradient primitive).
BAYER4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def dither_pick(x, y, t, color_a, color_b):
    """Pick ``color_a``/``color_b`` at ``(x, y)`` for gradient position ``t`` (0..1)."""
    threshold = BAYER4[y % 4][x % 4]
    return color_a if (t * 16.0) <= threshold else color_b


def draw_chamfered_badge(buffer, x0, y0, size, chamfer, color):
    """Fill a ``size``x``size`` square with its 4 corners diagonally chamfered.

    A "pixel rounded" badge: each corner is cut by a 45-degree diagonal of
    depth ``chamfer``, leaving the rest of the square filled. Drawn on a
    buffer that is transparent where not painted, so whatever sits behind the
    badge's own layer shows through the cut corners.
    """
    for yy in range(size):
        for xx in range(size):
            if (
                xx < chamfer
                and yy < chamfer
                and (chamfer - xx) + (chamfer - yy) > chamfer
            ):
                continue  # top-left
            if (
                xx >= size - chamfer
                and yy < chamfer
                and (xx - (size - 1 - chamfer)) + (chamfer - yy) > chamfer
            ):
                continue  # top-right
            if (
                xx < chamfer
                and yy >= size - chamfer
                and (chamfer - xx) + (yy - (size - 1 - chamfer)) > chamfer
            ):
                continue  # bottom-left
            if (
                xx >= size - chamfer
                and yy >= size - chamfer
                and (xx - (size - 1 - chamfer)) + (yy - (size - 1 - chamfer)) > chamfer
            ):
                continue  # bottom-right
            px, py = x0 + xx, y0 + yy
            if buffer.in_bounds(px, py):
                buffer.set_pixel(px, py, color)


def draw_disc(buffer, cx, cy, radius, color):
    """Paint a filled circle of ``radius`` centred at ``(cx, cy)`` (distance test)."""
    r2 = radius * radius
    for yy in range(-radius, radius + 1):
        for xx in range(-radius, radius + 1):
            if xx * xx + yy * yy <= r2:
                px, py = cx + xx, cy + yy
                if buffer.in_bounds(px, py):
                    buffer.set_pixel(px, py, color)


def nearest_ramp_color(c, ramp):
    best, best_d = None, None
    for rc in ramp:
        d = (c[0] - rc[0]) ** 2 + (c[1] - rc[1]) ** 2 + (c[2] - rc[2]) ** 2
        if best_d is None or d < best_d:
            best_d, best = d, rc
    return best


def remap_buffer_to_ramp(mods, buffer, ramp):
    """Map every colour in ``buffer`` to its nearest colour in ``ramp``.

    The mapping (which colour goes to which) is this generator's own choice
    (nearest RGB distance -- a small utility, not a re-implementation of any
    product colour maths); the actual per-pixel remap is applied by the
    product's own :func:`palette_ops.remap_colors` (PS-1), never a manual
    NumPy write here.
    """
    remap_colors = mods["remap_colors"]
    arr = buffer.data.reshape(-1, 4)
    uniques = {tuple(int(v) for v in px) for px in arr}
    mapping = {u: nearest_ramp_color(u, ramp) for u in uniques}
    return remap_colors(buffer, mapping)


# --------------------------------------------------------------------------- #
# art helpers shared by all four example pieces
# --------------------------------------------------------------------------- #


def upscale_document(mods, doc, factor):
    Document = mods["Document"]
    Frame = mods["Frame"]
    Layer = mods["Layer"]
    FrameTag = mods["FrameTag"]
    scale_nearest = mods["scale_nearest"]

    new_doc = Document(
        doc.width * factor,
        doc.height * factor,
        mode=doc.mode,
        palette=doc.palette.copy(),
        metadata=dict(doc.metadata),
    )
    new_frames = []
    for frame in doc.frames:
        new_layers = []
        for node in frame.layers:
            new_buffer = scale_nearest(
                node.buffer, doc.width * factor, doc.height * factor
            )
            new_layer = Layer(
                new_buffer,
                node.name,
                opacity=node.opacity,
                visible=node.visible,
                blend_mode=node.blend_mode,
                locked=node.locked,
            )
            new_layers.append(new_layer)
        new_frames.append(Frame(new_layers, duration_ms=frame.duration_ms))
    new_doc.frames = new_frames
    for frame in new_doc.frames:
        for node in frame.layers:
            if node.layer_id == 0:
                node.layer_id = new_doc._mint_id()
    if doc.frame_tags:
        new_doc.frame_tags = [
            FrameTag(
                name=t.name,
                from_frame=t.from_frame,
                to_frame=t.to_frame,
                mode=t.mode,
                repeat=t.repeat,
                color=t.color,
            )
            for t in doc.frame_tags
        ]
    return new_doc


def export_piece(
    mods, prov, ctx, doc, out_dir: Path, base_name, factor, formats, subject_note
):
    """save -> upscale (record X.6) -> save -> export each requested format."""
    save_project = mods["save_project"]

    base_path = out_dir / f"{base_name}.pixproj"
    save_project(doc, base_path)
    prov.add(
        output_path=base_path,
        command=["python-api", "Document(...)", "save_project"],
        inputs=[{"note": subject_note}],
    )

    TransformError = mods["TransformError"]
    try:
        upscaled = upscale_document(mods, doc, factor)
    except TransformError as exc:
        ctx["canvas_bounds_failures"].append(
            {"piece": base_name, "factor": factor, "error": str(exc)}
        )
        return []
    ctx["canvas_bounds_ok"].append({"piece": base_name, "factor": factor})

    up_path = out_dir / f"{base_name}-x{factor}.pixproj"
    save_project(upscaled, up_path)
    prov.add(
        output_path=up_path,
        command=["python-api", "scale_nearest", f"x{factor}", "save_project"],
        inputs=[{"source": f"{base_name}.pixproj", "factor": factor}],
    )

    ExportRequest = mods["ExportRequest"]
    ExportFormat = mods["ExportFormat"]
    export_document = mods["export_document"]
    write_export = mods["write_export"]

    produced = [base_path, up_path]
    for fmt_value, out_name, kwargs in formats:
        req = ExportRequest(fmt=ExportFormat(fmt_value), emit_json=False, **kwargs)
        result = export_document(upscaled, req)
        out_path = out_dir / out_name
        write_export(result, out_path)
        prov.add(
            output_path=out_path,
            command=[
                "pixelart-export",
                "--input",
                f"{base_name}-x{factor}.pixproj",
                "--format",
                fmt_value,
                "--output",
                out_name,
            ],
            inputs=[{"source": f"{base_name}-x{factor}.pixproj"}],
        )
        produced.append(out_path)
    return produced, doc, upscaled


# --------------------------------------------------------------------------- #
# (a) animated character sprite -- outlined, 3-tone shaded, idle + walk cycle
# --------------------------------------------------------------------------- #


def _paint_adventurer(buffer, *, leg_dx, arm_dx, bob, foot_lift):
    """Paint one 32x32 pose of the shared 'adventurer' character.

    ``leg_dx``: forward(+)/back(-) offset of the front leg (back leg mirrors).
    ``arm_dx``: forward/back offset of the arms (opposite phase to the legs).
    ``bob``: -1 on a passing (mid-stride) pose, 0 on a contact pose.
    ``foot_lift``: 1 px the trailing foot lifts off the ground on a passing pose.
    """
    OUTLINE = P("outline")

    def block(x, y, w, h, base, hi=None, shadow=None, hi_rows=1, shadow_rows=1):
        buffer.fill_rect(x - 1, y - 1, w + 2, h + 2, OUTLINE)
        buffer.fill_rect(x, y, w, h, base)
        if hi is not None:
            buffer.fill_rect(x, y, w, min(hi_rows, h), hi)
        if shadow is not None and h > hi_rows:
            buffer.fill_rect(x, y + h - shadow_rows, w, shadow_rows, shadow)

    top = 4 + bob

    # cap / hair
    block(11, top, 10, 4, P("wood_base"), hi=P("wood_hi"), shadow=P("wood_shadow"))
    # face
    block(12, top + 4, 8, 5, P("skin_base"), hi=P("skin_hi"), shadow=P("skin_shadow"))
    buffer.set_pixel(14, top + 6, P("outline"))
    buffer.set_pixel(15, top + 6, P("skin_hi"))
    buffer.set_pixel(17, top + 6, P("outline"))
    buffer.set_pixel(18, top + 6, P("skin_hi"))

    torso_y = top + 9
    # torso (tunic)
    block(
        10,
        torso_y,
        12,
        9,
        P("tunic_base"),
        hi=P("tunic_hi"),
        shadow=P("tunic_shadow"),
        shadow_rows=2,
    )
    buffer.fill_rect(10, torso_y + 6, 12, 1, P("gold"))  # belt

    # arms -- swing opposite the legs
    left_arm_x = 6 + arm_dx
    right_arm_x = 23 - arm_dx
    for ax in (left_arm_x, right_arm_x):
        buffer.fill_rect(ax - 1, torso_y, 4, 3, OUTLINE)
        buffer.fill_rect(ax, torso_y, 3, 2, P("tunic_shadow"))
        buffer.fill_rect(ax - 1, torso_y + 2, 4, 6, OUTLINE)
        buffer.fill_rect(ax, torso_y + 2, 3, 5, P("skin_base"))
        buffer.fill_rect(ax, torso_y + 6, 3, 1, P("skin_hi"))

    # legs -- front leg forward by leg_dx, back leg mirrors; a passing pose
    # lifts the trailing foot by foot_lift.
    leg_y = torso_y + 9
    front_x = 15 + leg_dx
    back_x = 13 - leg_dx
    front_lift = foot_lift if leg_dx < 0 else 0
    back_lift = foot_lift if leg_dx > 0 else 0
    for lx, lift in ((back_x, back_lift), (front_x, front_lift)):
        y = leg_y - lift
        buffer.fill_rect(lx - 1, y - 1, 5, 7, OUTLINE)
        buffer.fill_rect(lx, y, 4, 3, P("wood_shadow"))  # trousers
        buffer.fill_rect(lx, y + 3, 4, 3, P("outline"))  # boot
        buffer.fill_rect(lx, y + 3, 4, 1, P("wood_hi"))  # boot rim highlight


def make_sprite_document(mods):
    Document = mods["Document"]
    FrameTag = mods["FrameTag"]
    PlaybackMode = mods["PlaybackMode"]

    W = H = 32
    doc = Document(
        W, H, palette=master_palette(mods), metadata={"subject": "showcase-adventurer"}
    )

    # idle: 2-frame breathing loop (a 1px chest rise, no stride)
    idle_specs = [
        dict(leg_dx=0, arm_dx=0, bob=0, foot_lift=0),
        dict(leg_dx=0, arm_dx=0, bob=-1, foot_lift=0),
    ]
    # walk: 8-frame cycle -- a sine-shaped stride with 2 contact poses (feet
    # both near the ground, body at its lowest) and 2 passing poses (one foot
    # lifted mid-stride, body bobbed up 1px), arms swinging opposite the legs.
    walk_specs = []
    for i in range(8):
        angle = 2 * math.pi * i / 8
        leg_dx = round(2 * math.sin(angle))
        arm_dx = -leg_dx
        is_passing = i % 4 == 2
        bob = -1 if is_passing else 0
        foot_lift = 1 if is_passing else 0
        walk_specs.append(
            dict(leg_dx=leg_dx, arm_dx=arm_dx, bob=bob, foot_lift=foot_lift)
        )

    all_specs = idle_specs + walk_specs

    _paint_adventurer(doc.frames[0].layers[0].buffer, **all_specs[0])
    doc.frames[0].duration_ms = 260
    for spec in all_specs[1:]:
        frame = doc.add_frame(duration_ms=120)
        _paint_adventurer(frame.layers[0].buffer, **spec)
    doc.frames[0].duration_ms = 260
    doc.frames[1].duration_ms = 260

    doc.frame_tags.append(
        FrameTag(name="idle", from_frame=0, to_frame=1, mode=PlaybackMode.LOOP)
    )
    doc.frame_tags.append(
        FrameTag(
            name="walk",
            from_frame=2,
            to_frame=len(doc.frames) - 1,
            mode=PlaybackMode.LOOP,
        )
    )
    return doc


def build_sprite(mods, out_dir, prov, ctx):
    doc = make_sprite_document(mods)
    formats = [
        ("gif", "character-sprite.gif", {"tag": "walk", "loop": 0}),
        ("sprite-sheet", "character-sprite-sheet.png", {"columns": 4}),
    ]
    produced, native_doc, _ = export_piece(
        mods,
        prov,
        ctx,
        doc,
        out_dir,
        "character-sprite",
        8,
        formats,
        "outlined, 3-tone shaded adventurer, 32x32, idle (2f) + 8-frame walk cycle",
    )
    return produced, native_doc


# --------------------------------------------------------------------------- #
# (b) small layered scene -- dithered sky, shaded hills, a clustered tree,
#     a shaded house, and foreground detail
# --------------------------------------------------------------------------- #


def make_scene_document(mods):
    Document = mods["Document"]

    W, H = 64, 48
    doc = Document(
        W,
        H,
        palette=master_palette(mods),
        metadata={"subject": "showcase-layered-scene"},
    )

    # -- sky: an ordered-dither gradient between two blues (art direction:
    # "gradient/dithered sky"), plus a sun and two soft clouds.
    sky = doc.frames[0].layers[0]
    sky.name = "Sky"
    for y in range(H):
        t = y / (H - 1)
        for x in range(W):
            sky.buffer.set_pixel(x, y, dither_pick(x, y, t, P("sky_hi"), P("sky_lo")))
    draw_disc(sky.buffer, 52, 8, 3, P("sun"))
    for cx, cy in ((10, 7), (30, 5), (46, 12)):
        for dx, dy, r in ((-2, 0, 2), (0, -1, 2), (2, 0, 2)):
            draw_disc(sky.buffer, cx + dx, cy + dy, r, P("cloud"))

    # -- hills: two banded, shaded ridgelines (far + near)
    hills = doc.add_layer("Hills")
    for x in range(W):
        far_h = int(6 + 4 * math.sin(x / 9.0))
        top = H - 18 - far_h
        height = 18 + far_h
        hills.buffer.fill_rect(x, top, 1, height, P("green_base"))
        hills.buffer.fill_rect(x, top, 1, 1, P("green_hi"))
        if height > 2:
            hills.buffer.fill_rect(x, top + height - 2, 1, 2, P("green_shadow"))
    for x in range(W):
        near_h = int(4 + 5 * math.sin(x / 6.0 + 2.0))
        top = H - 12 - near_h
        height = 12 + near_h
        hills.buffer.fill_rect(x, top, 1, height, P("green_base"))
        hills.buffer.fill_rect(x, top, 1, 1, P("green_hi"))
        if height > 2:
            hills.buffer.fill_rect(x, top + height - 2, 1, 2, P("green_shadow"))

    # -- tree: trunk with a lit face, a short branch fork at its top, and a
    #    clustered canopy (3 overlapping discs) whose lower edge overlaps the
    #    trunk/fork -- the trunk runs UP INTO the foliage rather than floating
    #    beside it. (Review round 2 fix: the previous trunk stopped 4px below
    #    the lowest canopy disc, leaving a visible gap between the log and the
    #    foliage. Fixed by extending the trunk upward, adding a genuine fork
    #    silhouette at its top, moving the canopy down so its lower edge
    #    overlaps both, and casting a small foliage-shadow patch onto the
    #    trunk exactly where they meet.)
    tree = doc.add_layer("Tree")
    trunk_x = 12
    trunk_bottom = H - 4
    trunk_top = H - 24  # extended upward (was H - 16) so it reaches the canopy
    trunk_height = trunk_bottom - trunk_top
    tree.buffer.fill_rect(trunk_x, trunk_top, 3, trunk_height, P("wood_shadow"))
    tree.buffer.fill_rect(trunk_x + 1, trunk_top, 1, trunk_height, P("wood_base"))

    # a short branch fork at the trunk's top, splitting up-left / up-right --
    # drawn before the canopy so the canopy naturally overlaps its upper rows
    fork_len = 5
    for i in range(fork_len):
        tree.buffer.set_pixel(trunk_x - i, trunk_top - i, P("wood_shadow"))
        tree.buffer.set_pixel(trunk_x + 1 - i, trunk_top - i, P("wood_base"))
        tree.buffer.set_pixel(trunk_x + 3 + i, trunk_top - i, P("wood_shadow"))
        tree.buffer.set_pixel(trunk_x + 2 + i, trunk_top - i, P("wood_base"))

    canopy_cx, canopy_cy = trunk_x + 1, trunk_top - 2
    draw_disc(tree.buffer, canopy_cx, canopy_cy, 6, P("green_shadow"))
    draw_disc(tree.buffer, canopy_cx - 2, canopy_cy - 2, 5, P("green_base"))
    draw_disc(tree.buffer, canopy_cx + 2, canopy_cy - 3, 4, P("green_hi"))

    # a foliage-shadow patch cast onto the trunk exactly at the join, so the
    # meeting point reads as shading rather than a hard seam between shapes
    tree.buffer.fill_rect(trunk_x - 1, canopy_cy + 4, 5, 2, P("green_shadow"))

    # -- house: shaded roof (ridge-lit, eave-shadowed), edge-shaded wall,
    #    a lit doorway and windows with a glow accent
    house = doc.add_layer("House")
    hx, hy = 34, H - 20
    house.buffer.fill_rect(hx, hy, 20, 14, P("wall_base"))
    house.buffer.fill_rect(hx, hy, 1, 14, P("wall_shadow"))
    house.buffer.fill_rect(hx + 19, hy, 1, 14, P("wall_hi"))
    roof_rows = 10
    for i in range(roof_rows):
        row_w = 22 - 2 * i
        row_x = hx - 1 + i
        row_y = hy - 1 - i
        if i < 2:
            color = P("roof_hi")
        elif i > roof_rows - 3:
            color = P("roof_shadow")
        else:
            color = P("roof_base")
        house.buffer.fill_rect(row_x, row_y, row_w, 1, color)
    house.buffer.fill_rect(hx + 8, hy + 6, 4, 8, P("wood_shadow"))
    house.buffer.fill_rect(hx + 8, hy + 6, 1, 8, P("wood_base"))
    for wx in (hx + 2, hx + 14):
        house.buffer.fill_rect(wx, hy + 4, 4, 4, P("wall_shadow"))
        house.buffer.fill_rect(wx, hy + 4, 4, 4, P("window_glow"))
        house.buffer.set_pixel(wx, hy + 4, P("wall_shadow"))
        house.buffer.set_pixel(wx + 3, hy + 7, P("gold"))

    # -- foreground: grass tufts, flowers, a short fence
    ground = doc.add_layer("Foreground")
    for x in range(0, W, 3):
        ground.buffer.set_pixel(x, H - 1, P("green_hi"))
    for x, color in (
        (5, P("flower_pink")),
        (9, P("flower_white")),
        (58, P("flower_pink")),
    ):
        ground.buffer.set_pixel(x, H - 2, color)
    for post_x in (54, 58, 62):
        ground.buffer.fill_rect(post_x, H - 6, 1, 5, P("wood_shadow"))
    ground.buffer.fill_rect(54, H - 4, 9, 1, P("wood_base"))

    return doc


def build_scene(mods, out_dir, prov, ctx):
    doc = make_scene_document(mods)
    formats = [("png", "layered-scene.png", {"frame_index": 0})]
    produced, native_doc, _ = export_piece(
        mods,
        prov,
        ctx,
        doc,
        out_dir,
        "layered-scene",
        6,
        formats,
        "layered scene, 64x48: dithered sky, shaded hills, clustered tree, "
        "shaded house, foreground detail",
    )
    return produced, native_doc


# --------------------------------------------------------------------------- #
# (c) tilemap level -- a real Blob-47 auto-tiled path over a shaded grass
#     base, a pond, a stone border, and scattered decoration tiles
# --------------------------------------------------------------------------- #


def _direction_weights(mask_from_neighbours):
    """Learn the 8 bit weights ``mask_from_neighbours`` uses, without reading
    any private module constant -- one call per direction, each with exactly
    one neighbour flag set (Decision A21-D4 spirit: consume the public API,
    never re-implement or reach past it)."""
    slots = ["tl", "t", "tr", "left", "right", "bl", "b", "br"]
    labels = ["TL", "T", "TR", "L", "R", "BL", "B", "BR"]
    weights = {}
    for slot, label in zip(slots, labels):
        kwargs = {s: (s == slot) for s in slots}
        weights[label] = mask_from_neighbours(**kwargs)
    return weights


def _representative_masks(resolve_display_index, count):
    """First raw 8-neighbour mask (0..255) that resolves to each frame index."""
    rep = {}
    for raw in range(256):
        idx = resolve_display_index(raw)
        if idx not in rep:
            rep[idx] = raw
        if len(rep) == count:
            break
    return rep


def _render_blob_frame(PixelBuffer, ColorMode, tile, occ):
    """Render one Blob-47 display frame as a rounded dirt-path blob.

    ``occ`` maps ``TL/T/TR/L/R/BL/B/BR`` to whether that neighbour shares the
    path terrain. Edges without a connected neighbour are inset (revealing
    transparency, so the grass layer beneath shows through); a corner is
    additionally notched when both its cardinals connect but it does not
    (Blob-47's edge-implies-corner gating, consumed via the public resolver --
    see :func:`_representative_masks` / :func:`_direction_weights`).
    """
    buf = PixelBuffer(tile, tile, ColorMode.RGBA)
    inset = max(3, tile // 4)
    corner_cut = max(3, tile // 4)
    for py in range(tile):
        for px in range(tile):
            include = True
            if not occ["L"] and px < inset:
                include = False
            if not occ["R"] and px >= tile - inset:
                include = False
            if not occ["T"] and py < inset:
                include = False
            if not occ["B"] and py >= tile - inset:
                include = False
            if include and occ["T"] and occ["L"] and not occ["TL"]:
                if (
                    px < corner_cut
                    and py < corner_cut
                    and (corner_cut - px) + (corner_cut - py) > corner_cut
                ):
                    include = False
            if include and occ["T"] and occ["R"] and not occ["TR"]:
                if (
                    px >= tile - corner_cut
                    and py < corner_cut
                    and (px - (tile - 1 - corner_cut)) + (corner_cut - py) > corner_cut
                ):
                    include = False
            if include and occ["B"] and occ["L"] and not occ["BL"]:
                if (
                    px < corner_cut
                    and py >= tile - corner_cut
                    and (corner_cut - px) + (py - (tile - 1 - corner_cut)) > corner_cut
                ):
                    include = False
            if include and occ["B"] and occ["R"] and not occ["BR"]:
                if (
                    px >= tile - corner_cut
                    and py >= tile - corner_cut
                    and (px - (tile - 1 - corner_cut)) + (py - (tile - 1 - corner_cut))
                    > corner_cut
                ):
                    include = False
            if not include:
                continue
            if py < 2:
                color = P("wood_hi")
            elif py >= tile - 3:
                color = P("wood_shadow")
            else:
                color = P("wood_base")
            buf.set_pixel(px, py, color)
    return buf


def _make_ground_tile(PixelBuffer, ColorMode, tile, kind):
    buf = PixelBuffer(tile, tile, ColorMode.RGBA)
    if kind == "grass":
        for y in range(tile):
            for x in range(tile):
                t = 0.15 + 0.1 * math.sin((x + y) / 3.0)
                buf.set_pixel(
                    x, y, dither_pick(x, y, t, P("green_hi"), P("green_base"))
                )
        buf.fill_rect(0, tile - 1, tile, 1, P("green_shadow"))
    elif kind == "water":
        buf.fill(P("water_base"))
        for x in range(0, tile, 2):
            buf.set_pixel(x, 2, P("water_hi"))
            buf.set_pixel((x + 1) % tile, tile - 3, P("water_shadow"))
    elif kind == "stone":
        buf.fill(P("stone_base"))
        buf.fill_rect(0, 0, tile, 1, P("stone_hi"))
        buf.fill_rect(0, 0, 1, tile, P("stone_hi"))
        buf.fill_rect(0, tile - 1, tile, 1, P("stone_shadow"))
        buf.fill_rect(tile - 1, 0, 1, tile, P("stone_shadow"))
    elif kind == "dirt-flat":
        buf.fill(P("wood_base"))
        buf.fill_rect(0, 0, tile, 2, P("wood_hi"))
        buf.fill_rect(0, tile - 2, tile, 2, P("wood_shadow"))
    elif kind == "flower":
        for y in range(tile):
            for x in range(tile):
                t = 0.15
                buf.set_pixel(
                    x, y, dither_pick(x, y, t, P("green_hi"), P("green_base"))
                )
        cx, cy = tile // 2, tile // 2
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            buf.set_pixel(cx + dx, cy + dy, P("flower_pink"))
        buf.set_pixel(cx, cy, P("flower_white"))
    elif kind == "pebble":
        for y in range(tile):
            for x in range(tile):
                t = 0.15
                buf.set_pixel(
                    x, y, dither_pick(x, y, t, P("green_hi"), P("green_base"))
                )
        draw_disc(buf, tile // 2 - 2, tile // 2, 2, P("stone_base"))
        draw_disc(buf, tile // 2 + 2, tile // 2 + 1, 1, P("stone_hi"))
    elif kind == "bush":
        for y in range(tile):
            for x in range(tile):
                t = 0.15
                buf.set_pixel(
                    x, y, dither_pick(x, y, t, P("green_hi"), P("green_base"))
                )
        draw_disc(buf, tile // 2, tile // 2, tile // 3, P("green_shadow"))
        draw_disc(buf, tile // 2 - 1, tile // 2 - 1, tile // 4, P("green_hi"))
    return buf


def make_tilemap_document(mods):
    PixelBuffer = mods["PixelBuffer"]
    ColorMode = mods["ColorMode"]
    Tileset = mods["Tileset"]
    Tilemap = mods["Tilemap"]
    TilemapLayer = mods["TilemapLayer"]
    AutotileRuleset = mods["AutotileRuleset"]
    BLOB_TILE_COUNT = mods["BLOB_TILE_COUNT"]
    mask_from_neighbours = mods["mask_from_neighbours"]
    resolve_display_index = mods["resolve_display_index"]
    Document = mods["Document"]

    TILE = 16

    # -- ground tileset (literal placement): grass, water, stone, a dirt-flat
    #    marker tile (doubles as the autotile ruleset's terrain gid), and 3
    #    decoration variants.
    ground_kinds = ["grass", "water", "stone", "dirt-flat", "flower", "pebble", "bush"]
    ground_source = PixelBuffer(TILE * len(ground_kinds), TILE, ColorMode.RGBA)
    for i, kind in enumerate(ground_kinds):
        ground_source.blit(
            _make_ground_tile(PixelBuffer, ColorMode, TILE, kind), i * TILE, 0
        )
    ground_tileset = Tileset(
        ground_source, tile_width=TILE, tile_height=TILE, name="Ground", first_gid=1
    )
    GID = {kind: 1 + i for i, kind in enumerate(ground_kinds)}

    # -- path blob tileset (auto-tiled): 47 frames rendered from real
    #    neighbour-occupancy data, decoded via the public autotile resolver.
    weights = _direction_weights(mask_from_neighbours)
    rep_masks = _representative_masks(resolve_display_index, BLOB_TILE_COUNT)
    blob_source = PixelBuffer(TILE * BLOB_TILE_COUNT, TILE, ColorMode.RGBA)
    for idx in range(BLOB_TILE_COUNT):
        raw = rep_masks[idx]
        occ = {label: bool(raw & weight) for label, weight in weights.items()}
        frame = _render_blob_frame(PixelBuffer, ColorMode, TILE, occ)
        blob_source.blit(frame, idx * TILE, 0)
    blob_first_gid = 1 + len(ground_kinds)
    blob_tileset = Tileset(
        blob_source,
        tile_width=TILE,
        tile_height=TILE,
        name="PathBlob",
        first_gid=blob_first_gid,
    )
    frame_gids = tuple(blob_first_gid + i for i in range(BLOB_TILE_COUNT))
    ruleset = AutotileRuleset(terrain_gid=GID["dirt-flat"], frame_gids=frame_gids)

    # -- the level: a bordered 22x13 grid, a grass interior, a pond, a
    #    winding auto-tiled path, and a handful of decoration stamps.
    cols, rows = 22, 13
    tilemap = Tilemap(name="Level", infinite=True, tile_width=TILE, tile_height=TILE)
    tilemap.make_attach_tileset_command(ground_tileset).execute()
    tilemap.make_attach_tileset_command(blob_tileset).execute()
    tilemap.make_add_layer_command(name="Ground").execute()
    tilemap.layers.append(TilemapLayer("Path", autotile=ruleset))

    tilemap.make_fill_rect_command(0, 0, 0, cols, rows, GID["stone"]).execute()
    tilemap.make_fill_rect_command(0, 1, 1, cols - 2, rows - 2, GID["grass"]).execute()

    pond_x, pond_y, pond_w, pond_h = 15, 7, 5, 4
    tilemap.make_fill_rect_command(
        0, pond_x, pond_y, pond_w, pond_h, GID["water"]
    ).execute()

    def in_pond(cx, cy):
        return pond_x <= cx < pond_x + pond_w and pond_y <= cy < pond_y + pond_h

    path_cells = {}
    for col in range(1, 10):
        path_cells[(col, 6)] = True
    for row in range(6, 9):
        path_cells[(9, row)] = True
    for col in range(9, 15):
        path_cells[(col, 8)] = True
    for row in range(8, 4, -1):
        path_cells[(14, row)] = True
    for col in range(14, 21):
        path_cells[(col, 5)] = True

    for cx, cy in path_cells:
        if in_pond(cx, cy):
            continue
        tilemap.make_stamp_command(1, cx, cy, GID["dirt-flat"]).execute()

    decorations = [
        (3, 2, "flower"),
        (6, 2, "pebble"),
        (9, 2, "flower"),
        (12, 2, "bush"),
        (16, 2, "flower"),
        (3, 10, "pebble"),
        (18, 10, "bush"),
        (4, 9, "flower"),
    ]
    for cx, cy, kind in decorations:
        if (cx, cy) in path_cells or in_pond(cx, cy):
            continue
        tilemap.make_stamp_command(0, cx, cy, GID[kind]).execute()

    rendered = tilemap.render_region(0, 0, cols * TILE, rows * TILE)
    doc = Document.from_buffer(
        rendered, name="Tilemap Level", palette=master_palette(mods)
    )
    doc.metadata["subject"] = "showcase-tilemap-level"
    doc.make_add_tileset_command(ground_tileset).execute()
    doc.make_add_tileset_command(blob_tileset).execute()
    doc.make_add_tilemap_command(tilemap).execute()
    return doc


def build_tilemap(mods, out_dir, prov, ctx):
    doc = make_tilemap_document(mods)
    formats = [("png", "tilemap-level.png", {"frame_index": 0})]
    produced, native_doc, _ = export_piece(
        mods,
        prov,
        ctx,
        doc,
        out_dir,
        "tilemap-level",
        3,
        formats,
        "22x13 tilemap: real Blob-47 auto-tiled dirt path (47 frames resolved via "
        "the product's own autotile resolver) over a shaded grass base, a pond, "
        "a stone border and scattered decoration tiles",
    )
    return produced, native_doc


# --------------------------------------------------------------------------- #
# (d) procedural texture set via the automation engine (pixelart-run),
#     then curated onto the shared palette through palette_ops.remap_colors
# --------------------------------------------------------------------------- #


def build_procgen_set(mods, out_dir, prov, ctx, tmp_dir: Path):
    from pixelart_creator.data.automation_cli import main as run_main

    Document = mods["Document"]
    Palette = mods["Palette"]
    PixelBuffer = mods["PixelBuffer"]
    ColorMode = mods["ColorMode"]
    Op = mods["Op"]
    record = mods["record"]
    save_project = mods["save_project"]
    save_macro = mods["save_macro"]
    load_project = mods["load_project"]

    tmp_dir = tmp_dir / "procgen"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    algorithms = [
        (
            "value_noise",
            {
                "frequency": 4,
                "octaves": 3,
                "color_low": [18, 20, 40, 255],
                "color_high": [120, 170, 255, 255],
            },
            101,
            [P("outline"), P("water_shadow"), P("sky_lo"), P("sky_hi"), P("cloud")],
        ),
        (
            "gradient_noise",
            {
                "frequency": 4,
                "octaves": 2,
                "color_low": [10, 40, 22, 255],
                "color_high": [150, 225, 120, 255],
            },
            202,
            [P("green_shadow"), P("green_base"), P("green_hi")],
        ),
        (
            "opensimplex",
            {
                "frequency": 5,
                "color_low": [40, 10, 30, 255],
                "color_high": [230, 120, 200, 255],
            },
            303,
            [P("tunic_shadow"), P("tunic_base"), P("tunic_hi")],
        ),
        (
            "cellular_automata",
            {"color_low": [15, 15, 18, 255], "color_high": [215, 215, 220, 255]},
            404,
            [P("stone_shadow"), P("stone_base"), P("stone_hi")],
        ),
        (
            "dithered_gradient",
            {"color_low": [40, 12, 10, 255], "color_high": [250, 200, 60, 255]},
            505,
            [P("roof_shadow"), P("roof_base"), P("gold")],
        ),
    ]
    TILE = 32
    tiles = []
    for algo, params, seed, ramp in algorithms:
        in_doc = Document(
            TILE,
            TILE,
            palette=Palette([tuple(params["color_low"]), tuple(params["color_high"])]),
        )
        in_path = tmp_dir / f"{algo}-in.pixproj"
        save_project(in_doc, in_path)
        op_params = dict(params)
        op_params["algorithm"] = algo
        macro = record([Op("procgen", op_params, seed=seed)])
        macro_path = tmp_dir / f"{algo}.pixmacro"
        save_macro(macro, macro_path)
        run_out_path = tmp_dir / f"{algo}-out.pixproj"
        argv = [
            "--input",
            str(in_path),
            "--macro",
            str(macro_path),
            "--output",
            str(run_out_path),
        ]
        rc = run_main(argv)
        if rc != 0:
            raise RuntimeError(f"pixelart-run exited {rc} for algorithm {algo}")
        result_doc = load_project(run_out_path)
        raw_buffer = result_doc.frames[0].layers[0].buffer
        curated_buffer = remap_buffer_to_ramp(mods, raw_buffer, ramp)
        result_doc.frames[0].layers[0].buffer = curated_buffer
        tiles.append((algo, curated_buffer))

        kept_path = out_dir / f"procgen-{algo}.pixproj"
        save_project(result_doc, kept_path)
        prov.add(
            output_path=kept_path,
            command=[
                "pixelart-run",
                "--input",
                in_path.name,
                "--macro",
                macro_path.name,
                "--output",
                run_out_path.name,
            ],
            inputs=[{"algorithm": algo, "seed": seed, "params": params}],
            extra={
                "curation": (
                    "palette_ops.remap_colors onto the shared PALETTE_RAMPS ramp"
                )
            },
        )

    gap = 2
    sheet_w = len(tiles) * TILE + (len(tiles) - 1) * gap
    sheet = PixelBuffer(sheet_w, TILE, ColorMode.RGBA)
    x = 0
    for _algo, buf in tiles:
        sheet.blit(buf, x, 0)
        x += TILE + gap

    sheet_doc = Document.from_buffer(
        sheet, name="Procedural Texture Set", palette=master_palette(mods)
    )
    sheet_doc.metadata["subject"] = "showcase-procgen-contact-sheet"

    formats = [("png", "procgen-contact-sheet.png", {"frame_index": 0})]
    produced, native_doc, _ = export_piece(
        mods,
        prov,
        ctx,
        sheet_doc,
        out_dir,
        "procgen-contact-sheet",
        4,
        formats,
        "procedural texture contact sheet, 5 seeded pixelart-run algorithms, each "
        "curated onto the shared palette via palette_ops.remap_colors",
    )
    return produced, native_doc


# --------------------------------------------------------------------------- #
# social preview composition (decode-only Pillow use for the app icon asset)
# --------------------------------------------------------------------------- #


def load_png_into_buffer(mods, path: Path):
    import numpy as np
    from PIL import Image

    PixelBuffer = mods["PixelBuffer"]
    ColorMode = mods["ColorMode"]
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        arr = np.array(rgba, dtype="uint8")
    h, w = arr.shape[0], arr.shape[1]
    buffer = PixelBuffer(w, h, ColorMode.RGBA)
    buffer.data[:, :] = arr
    return buffer


def cmd_social(args) -> int:
    _resolve_review_dir(args)
    _resolve_out_dir(args, "social")
    if getattr(args, "art_dir", None) is None:
        args.art_dir = str(Path(args.review_dir) / "art")
    mods = load_product_modules(args.product_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    review_dir = Path(args.review_dir)
    gen_path = Path(__file__).resolve()
    prov = ProvenanceLog(review_dir, args.product_root, gen_path)
    prov.prune_missing()

    Document = mods["Document"]
    scale_nearest = mods["scale_nearest"]
    ExportRequest = mods["ExportRequest"]
    ExportFormat = mods["ExportFormat"]
    export_document = mods["export_document"]
    write_export = mods["write_export"]
    save_project = mods["save_project"]
    load_project = mods["load_project"]

    W, H = 1280, 640
    BG_TOP = (26, 32, 46, 255)
    BG_BOTTOM = (46, 58, 78, 255)

    doc = Document(
        W,
        H,
        palette=master_palette(mods),
        metadata={"subject": "showcase-social-preview"},
    )
    bg = doc.frames[0].layers[0]
    bg.name = "Background"
    for y in range(H):
        t = y / (H - 1)
        color = tuple(
            int(BG_TOP[c] + (BG_BOTTOM[c] - BG_TOP[c]) * t) for c in range(3)
        ) + (255,)
        bg.buffer.fill_rect(0, y, W, 1, color)

    # -- badge (light, chamfered) behind the app icon so the icon's dark mark
    #    stays legible against a dark background.
    badge_layer = doc.add_layer("Badge")
    badge_size = 132
    badge_x, badge_y = 60, 50
    draw_chamfered_badge(
        badge_layer.buffer, badge_x, badge_y, badge_size, 20, P("badge_light")
    )

    icon_path = (
        Path(args.product_root)
        / "pixelart_creator"
        / "icons"
        / "app"
        / "logo-source-64.png"
    )
    icon_layer = doc.add_layer("App Icon")
    icon_buffer = load_png_into_buffer(mods, icon_path)
    icon_scale = 2
    icon_up = scale_nearest(
        icon_buffer, icon_buffer.width * icon_scale, icon_buffer.height * icon_scale
    )
    icon_x = badge_x + (badge_size - icon_up.width) // 2
    icon_y = badge_y + (badge_size - icon_up.height) // 2
    icon_layer.buffer.blit(icon_up, icon_x, icon_y, blend=True)

    # -- title + tagline, to the right of the badge
    text_layer = doc.add_layer("Lettering")
    title_scale = 6
    tagline_scale = 3
    title_text = "PIXELART CREATOR"
    title_x = badge_x + badge_size + 30
    title_y = badge_y + (badge_size - 7 * title_scale) // 2
    draw_text(
        text_layer.buffer,
        title_text,
        title_x,
        title_y,
        P("badge_light"),
        scale=title_scale,
    )
    tagline_y = title_y + 7 * title_scale + 18
    draw_text(
        text_layer.buffer,
        args.tagline,
        title_x,
        tagline_y,
        P("sky_hi"),
        scale=tagline_scale,
    )

    # -- art collage: the procedural contact-sheet strip top-right, and a
    #    character / tilemap-crop / scene row across the bottom, all placed
    #    from the pieces' own NATIVE (pre-upscale) project sources and
    #    re-scaled once here with scale_nearest -- never a re-scale of an
    #    already-upscaled export.
    art_layer = doc.add_layer("Example Art")
    art_dir = Path(args.art_dir)
    art_placed = {}

    procgen_native = art_dir / "procgen-contact-sheet.pixproj"
    if procgen_native.exists():
        p_doc = load_project(procgen_native)
        p_buf = p_doc.frames[0].layers[0].buffer
        p_up = scale_nearest(p_buf, p_buf.width * 2, p_buf.height * 2)
        p_x = W - 60 - p_up.width
        p_y = 58
        art_layer.buffer.blit(p_up, p_x, p_y, blend=True)
        art_placed["procgen"] = [p_x, p_y, p_up.width, p_up.height]

    baseline_y = 612

    scene_native = art_dir / "layered-scene.pixproj"
    if scene_native.exists():
        s_doc = load_project(scene_native)
        # flatten the scene's own layers (a throwaway alpha-blit stack, not
        # a second call to the export engine -- the export engine owns the
        # shipped composite; this is just local pixel placement into the
        # social-preview canvas).
        flat = s_doc.frames[0].layers[0].buffer.copy()
        for layer in s_doc.frames[0].layers[1:]:
            flat.blit(layer.buffer, 0, 0, blend=True)
        s_up = scale_nearest(flat, flat.width * 7, flat.height * 7)
        s_x = W - 60 - s_up.width
        s_y = baseline_y - s_up.height
        art_layer.buffer.blit(s_up, s_x, s_y, blend=True)
        art_placed["scene"] = [s_x, s_y, s_up.width, s_up.height]

    tilemap_native = art_dir / "tilemap-level.pixproj"
    if tilemap_native.exists():
        t_doc = load_project(tilemap_native)
        t_buf = (
            t_doc.frames[0].layers[0].buffer
        )  # already the rendered, flattened level
        # a crop through the winding auto-tiled path and the pond corner
        # (cell columns 9-16, rows 4-9 of the 16px-tile level), not a plain
        # grass patch.
        crop = t_buf.region(144, 64, 128, 80)
        t_up = scale_nearest(crop, crop.width * 3, crop.height * 3)
        t_x = (W - t_up.width) // 2
        t_y = baseline_y - t_up.height
        art_layer.buffer.blit(t_up, t_x, t_y, blend=True)
        art_placed["tilemap_crop"] = [t_x, t_y, t_up.width, t_up.height]

    sprite_native = art_dir / "character-sprite.pixproj"
    if sprite_native.exists():
        c_doc = load_project(sprite_native)
        c_buf = c_doc.frames[3].layers[0].buffer  # a mid-stride walk pose
        c_up = scale_nearest(c_buf, c_buf.width * 7, c_buf.height * 7)
        c_x = 110
        c_y = baseline_y - c_up.height
        art_layer.buffer.blit(c_up, c_x, c_y, blend=True)
        art_placed["character"] = [c_x, c_y, c_up.width, c_up.height]

    base_path = out_dir / "social-preview.pixproj"
    save_project(doc, base_path)
    prov.add(
        output_path=base_path,
        command=["python-api", "Document(1280,640)", "save_project"],
        inputs=[
            {"icon_source": _rel(icon_path, Path(args.product_root))},
            {"art_placed": list(art_placed.keys())},
            {"tagline": args.tagline},
        ],
        extra={
            "lettering": (
                "in-platform pixel font drawn with PixelBuffer.set_pixel; "
                "no font file used"
            ),
            "badge": (
                "chamfered light badge (draw_chamfered_badge) behind the "
                "app icon for legibility"
            ),
            "layout": json.dumps(art_placed),
        },
    )

    req = ExportRequest(fmt=ExportFormat.PNG, frame_index=0, emit_json=False)
    result = export_document(doc, req)
    out_path = out_dir / "social-preview.png"
    write_export(result, out_path)
    prov.add(
        output_path=out_path,
        command=[
            "pixelart-export",
            "--input",
            "social-preview.pixproj",
            "--format",
            "png",
            "--output",
            "social-preview.png",
        ],
        inputs=[{"source": "social-preview.pixproj"}],
        extra={
            "lettering": (
                "in-platform pixel font drawn with PixelBuffer.set_pixel; "
                "no font file used"
            ),
            "tagline": args.tagline,
        },
    )
    prov.save()
    print(
        json.dumps(
            {
                "produced": ["social-preview.pixproj", "social-preview.png"],
                "art_placed": art_placed,
            },
            indent=2,
        )
    )
    return 0


# --------------------------------------------------------------------------- #
# art sub-command orchestration
# --------------------------------------------------------------------------- #


def cmd_art(args) -> int:
    _resolve_review_dir(args)
    _resolve_out_dir(args, "art")
    _resolve_tmp_dir(args)
    mods = load_product_modules(args.product_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    review_dir = Path(args.review_dir)
    tmp_dir = Path(args.tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    gen_path = Path(__file__).resolve()
    prov = ProvenanceLog(review_dir, args.product_root, gen_path)
    prov.prune_missing()
    ctx = {"canvas_bounds_ok": [], "canvas_bounds_failures": []}

    produced = {}
    sprite_files, _ = build_sprite(mods, out_dir, prov, ctx)
    produced["sprite"] = [str(p.name) for p in sprite_files]
    scene_files, _ = build_scene(mods, out_dir, prov, ctx)
    produced["scene"] = [str(p.name) for p in scene_files]
    tilemap_files, _ = build_tilemap(mods, out_dir, prov, ctx)
    produced["tilemap"] = [str(p.name) for p in tilemap_files]
    procgen_files, _ = build_procgen_set(mods, out_dir, prov, ctx, tmp_dir)
    produced["procgen"] = [str(p.name) for p in procgen_files]

    prov.save()
    (out_dir / "canvas-bounds.json").write_text(
        json.dumps(
            {"ok": ctx["canvas_bounds_ok"], "failures": ctx["canvas_bounds_failures"]},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"produced": produced, "canvas_bounds": ctx}, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# screenshots sub-command (Decision A21-D3: native first, offscreen fallback)
# --------------------------------------------------------------------------- #


KNOWN_CONTROL_COLOUR = (255, 0, 128, 255)

#: The window size used for every staged screenshot (art direction: a
#: realistic desktop window, not the offscreen platform's small default).
SCREENSHOT_WINDOW_SIZE = (1600, 1000)

#: The real Windows UI font, at its normal size -- set on the QApplication
#: BEFORE Main_Window is built (review round 2, point 2b), so every widget's
#: sizeHint and every screenshot matches what the app shows natively on
#: Windows, never a Qt/offscreen default substitute.
SCREENSHOT_FONT_FAMILY = "Segoe UI"
SCREENSHOT_FONT_POINT_SIZE = 9

#: The UI language forced for every screenshot (review round 2, point 2a) --
#: English, via the product's own ``LanguageManager.set_language`` (the exact
#: call the real Language menu action makes; see main_window.py L4882), never
#: a patch of product state. Overrides whatever ``install_from_locale()``
#: picked from the (Spanish, on this host) system locale.
SCREENSHOT_LANGUAGE = "en"

#: Minimum width forced on the layers dock before its shot so the blend-mode
#: QComboBox lays out at its full sizeHint ("Normal", "Colour Dodge", ...)
#: instead of being squeezed to a truncated "Norm" by a narrow dock column.
LAYER_DOCK_MIN_WIDTH = 380

#: Spanish-catalogue strings shorter than this are excluded from the language
#: control (X.7): a 1-3 character translated string (e.g. an accented "Sí")
#: risks a false positive against ordinary English widget text, whereas every
#: genuine UI phrase in this catalogue is longer.
LANGUAGE_CONTROL_MIN_STRING_LEN = 4


def load_spanish_catalogue_strings(product_root: str) -> list:
    """Parse ``pixelart_es.ts`` (the human-authored source catalogue, not the
    compiled ``.qm``) and return every non-empty, finished ``<translation>``
    string of at least :data:`LANGUAGE_CONTROL_MIN_STRING_LEN` characters,
    EXCLUDING any entry whose Spanish ``<translation>`` is identical to its
    English ``<source>`` (a cognate/proper-noun/technical term left
    untranslated on purpose -- e.g. "Normal", "Ping-Pong", "PixelArt
    Creator", "Auto-tile (Blob-47)"). Such an identity entry is correct
    Spanish AND correct English at once, so matching it can never itself
    prove the captured window is in Spanish -- it would only produce a false
    positive against a genuinely English screenshot; a real language-leak
    string always differs from its English source, so nothing this check can
    actually catch is excluded by the filter.

    Reading the ``.ts`` XML source (never re-implementing/guessing Qt's binary
    ``.qm`` format) keeps this a consumption of the product's own shipped
    catalogue, per Decision A21-D4's spirit of consuming public artefacts.
    """
    import xml.etree.ElementTree as ET

    path = Path(product_root) / "pixelart_creator" / "i18n" / "pixelart_es.ts"
    if not path.exists():
        return []
    try:
        tree = ET.parse(path)
    except Exception:  # noqa: BLE001
        return []
    strings = set()
    for message in tree.getroot().iter("message"):
        translation = message.find("translation")
        if translation is None:
            continue
        if translation.get("type") == "unfinished":
            continue
        text = (translation.text or "").strip()
        source_el = message.find("source")
        source_text = (source_el.text or "").strip() if source_el is not None else None
        if text == source_text:
            continue  # identity translation -- not a Spanish-only string
        if len(text) >= LANGUAGE_CONTROL_MIN_STRING_LEN:
            strings.add(text)
    return sorted(strings)


def collect_widget_texts(root_widget) -> list:
    """Walk ``root_widget`` and every VISIBLE descendant, returning every
    non-empty string surfaced through a text-bearing accessor (label/button/
    edit text, combo box current + every item text, tooltips, placeholder
    text, window titles, and menu-bar action text) -- the same surfaces a
    user actually reads on screen, and only those.

    Visibility-filtered on purpose: ``Layer_Panel.rebuild()`` calls
    ``QTreeWidget.clear()``, which (a documented Qt gotcha) does not release
    a previously ``setItemWidget``-attached row widget -- it survives as an
    orphaned, ``isVisible() == False`` child of the dock, carrying whatever
    language was active when IT was built. Measured this session: the very
    first layer-panel rebuild after a runtime language switch leaves exactly
    one such orphan behind, still in the pre-switch language, alongside the
    real (visible, correctly re-translated) rows -- a pre-existing product
    widget-leak, not a screenshot content defect (reported to the UI code's
    owner in this delivery's report, not fixed here per HARD RULES: never
    edit ``pixelart_creator/``). Restricting
    this scan to ``isVisible()`` widgets is what "visible in the captured
    window" (the brief's own wording) actually means, and it is also what
    keeps this check honest about the screenshot's actual pixels rather than
    flagging dead widgets nobody will ever see.
    """
    from PySide6.QtWidgets import QComboBox, QMenuBar, QWidget

    texts = []
    widgets = [root_widget] + [
        w for w in root_widget.findChildren(QWidget) if w.isVisible()
    ]
    for w in widgets:
        try:
            title = w.windowTitle()
            if title:
                texts.append(title)
        except Exception:  # noqa: BLE001
            pass
        for getter_name in (
            "text",
            "toPlainText",
            "toolTip",
            "placeholderText",
            "currentText",
        ):
            getter = getattr(w, getter_name, None)
            if not callable(getter):
                continue
            try:
                value = getter()
            except Exception:  # noqa: BLE001
                continue
            if isinstance(value, str) and value:
                texts.append(value)
        if isinstance(w, QComboBox):
            for i in range(w.count()):
                item_text = w.itemText(i)
                if item_text:
                    texts.append(item_text)
        if isinstance(w, QMenuBar):
            for action in w.actions():
                if action.text():
                    texts.append(action.text())
    return texts


def _isolate_qt_settings(settings_dir: Path):
    from PySide6.QtCore import QSettings, QStandardPaths

    QStandardPaths.setTestModeEnabled(True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    settings_dir.mkdir(parents=True, exist_ok=True)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir)
    )


def _registry_snapshot():
    """Best-effort read-only snapshot of the REAL (non-isolated) settings store.

    Windows-only, read-only (``winreg`` opens for read); used only to prove C6
    (the real application settings are unchanged by this run). Any failure
    (key absent, non-Windows) yields an empty snapshot -- never raises.
    """
    snapshot = {}
    try:
        import winreg

        # A Windows *registry* key path (always backslash-joined, regardless
        # of OS) -- never a filesystem path -- built via join, not a literal,
        # so the portability gate reads it as what it is.
        key_path = "\\".join(["Software", "PixelArt Creator", "PixelArt Creator"])
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            i = 0
            while True:
                try:
                    name, value, _type = winreg.EnumValue(key, i)
                except OSError:
                    break
                snapshot[name] = value
                i += 1
    except Exception:  # noqa: BLE001 - absent key / non-Windows / no access
        pass
    return snapshot


def _font_render_control():
    """Check that the capturing process' font database is actually populated.

    Returns ``(family_count, ink_ratio)``. ``family_count`` is the root-cause
    signal (0 families is exactly what produced the tofu-box defect this
    revision fixes); ``ink_ratio`` is a secondary check -- the fraction of
    "inked" pixels when a short known string is painted at a fixed size, which
    a genuine glyph render keeps within a plausible band and a notdef/tofu
    render (a thin box outline only) would not.
    """
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter

    families = QFontDatabase.families()
    family_count = len(families)

    img = QImage(240, 48, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255, 255))
    painter = QPainter(img)
    painter.setFont(QFont(families[0] if families else "", 28))
    painter.setPen(QColor(0, 0, 0, 255))
    painter.drawText(4, 34, "PIXELART")
    painter.end()

    ink = 0
    total = img.width() * img.height()
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).red() < 200:
                ink += 1
    ink_ratio = ink / total if total else 0.0
    return family_count, ink_ratio


def cmd_capture_worker(args) -> int:
    """Runs in its OWN process (spawned by ``screenshots``); does one capture pass."""
    _add_product_root(args.product_root)
    mods = load_product_modules(args.product_root)

    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
    from PySide6.QtWidgets import QApplication

    settings_dir = Path(args.settings_dir)
    _isolate_qt_settings(settings_dir)

    # -- real Windows UI font, forced BEFORE Main_Window is built (review
    #    round 2, point 2b): get-or-create the QApplication here (create_app
    #    below reuses it via QApplication.instance()) so setFont takes effect
    #    before a single widget is constructed.
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication([])
    app.setFont(QFont(SCREENSHOT_FONT_FAMILY, SCREENSHOT_FONT_POINT_SIZE))

    from pixelart_creator.ui.app import create_app
    from pixelart_creator.ui.theme import THEME_DARK, THEME_LIGHT

    app, window = create_app([])
    platform_name = QGuiApplication.platformName()

    result = {
        "platform": platform_name,
        "known_true_signal": False,
        "captures": {},
        "errors": [],
    }

    # -- font control (X.8): the effective app font after Main_Window's own
    #    startup wiring (apply_font_fallbacks / apply_theme) must still be the
    #    requested family, and that family must actually exist in this
    #    process' font database (native and offscreen are checked separately
    #    -- this worker runs once per platform attempt).
    effective_family = QApplication.instance().font().family()
    available_families = QFontDatabase.families()
    result["font_control"] = {
        "family_requested": SCREENSHOT_FONT_FAMILY,
        "point_size_requested": SCREENSHOT_FONT_POINT_SIZE,
        "family_effective": effective_family,
        "family_available": SCREENSHOT_FONT_FAMILY in available_families,
        "ok": effective_family == SCREENSHOT_FONT_FAMILY
        and SCREENSHOT_FONT_FAMILY in available_families,
    }

    # -- language, forced to English (review round 2, point 2a): the exact
    #    call the real Language menu action makes (main_window.py L4882),
    #    never a patch of product state. Overrides install_from_locale()'s
    #    system-locale pick (Spanish, on this host).
    window._language_manager.set_language(SCREENSHOT_LANGUAGE)
    app.processEvents()
    app.processEvents()
    result["language_control"] = {"examined": 0, "failed": 0, "findings": []}
    spanish_strings = load_spanish_catalogue_strings(args.product_root)

    def scan_language(widget, source_label):
        texts = collect_widget_texts(widget)
        acc = result["language_control"]
        acc["examined"] += len(texts)
        for text in texts:
            for es_string in spanish_strings:
                if es_string in text:
                    acc["failed"] += 1
                    acc["findings"].append(
                        {
                            "source": source_label,
                            "widget_text": text,
                            "spanish_string": es_string,
                        }
                    )

    family_count, ink_ratio = _font_render_control()
    result["font_families_count"] = family_count
    result["font_ink_ratio"] = ink_ratio
    result["text_render_ok"] = family_count > 0 and 0.03 <= ink_ratio <= 0.6

    window.resize(*SCREENSHOT_WINDOW_SIZE)
    app.processEvents()
    app.processEvents()

    Document = mods["Document"]
    Palette = mods["Palette"]
    save_project = mods["save_project"]

    control_doc = Document(16, 16, palette=Palette([KNOWN_CONTROL_COLOUR]))
    control_doc.frames[0].layers[0].buffer.fill(KNOWN_CONTROL_COLOUR)
    control_path = settings_dir / "control-known-colour.pixproj"
    save_project(control_doc, control_path)

    try:
        window.open_document(str(control_path))
        app.processEvents()
        tab = window._tabs_data[window._tab_widget.currentIndex()]
        pix = tab.view.grab()
        img = pix.toImage()
        found = False
        if img.width() and img.height():
            for fx in (0.3, 0.5, 0.7):
                for fy in (0.3, 0.5, 0.7):
                    x = min(img.width() - 1, max(0, int(img.width() * fx)))
                    y = min(img.height() - 1, max(0, int(img.height() * fy)))
                    c = img.pixelColor(x, y)
                    if (c.red(), c.green(), c.blue()) == KNOWN_CONTROL_COLOUR[:3]:
                        found = True
        result["known_true_signal"] = found
        window.close_document(window._tab_widget.currentIndex())
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"control: {exc}")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    docks = ["_layer_dock", "_timeline_dock", "_tilemap_layer_dock", "_tilemap_dock"]

    def show_only(*names):
        for dname in docks:
            dock = getattr(window, dname, None)
            if dock is None:
                continue
            if dname in names:
                dock.show()
                dock.raise_()
            else:
                dock.hide()
        app.processEvents()

    if result["known_true_signal"]:
        capture_plan = [
            (
                "scene_project",
                args.scene_project,
                ("_layer_dock",),
                "main-canvas-layers.png",
                THEME_LIGHT,
            ),
            (
                "scene_project_dark",
                args.scene_project,
                ("_layer_dock",),
                "main-canvas-layers-dark.png",
                THEME_DARK,
            ),
            (
                "sprite_project",
                args.sprite_project,
                ("_timeline_dock",),
                "animation-timeline.png",
                THEME_LIGHT,
            ),
            (
                "tilemap_project",
                args.tilemap_project,
                ("_tilemap_dock", "_tilemap_layer_dock"),
                "tilemap-editor.png",
                THEME_LIGHT,
            ),
        ]
        for label, project_path, dock_names, out_name, theme in capture_plan:
            if not project_path:
                continue
            try:
                # One clean tab per shot -- close whatever is open first (the
                # startup blank document, or the previous capture's tab) so
                # every screenshot shows a single, uncluttered document tab.
                while window._tabs_data:
                    window.close_document(0)
                app.processEvents()
                if theme != window._theme:
                    window.set_theme(theme)
                    app.processEvents()
                window.open_document(project_path)
                app.processEvents()
                show_only(*dock_names)
                if "_layer_dock" in dock_names:
                    # widen before the shot so the blend-mode combo box lays
                    # out at its full sizeHint ("Normal") instead of being
                    # squeezed to a truncated "Norm" by a narrow dock column
                    window._layer_dock.setMinimumWidth(LAYER_DOCK_MIN_WIDTH)
                    app.processEvents()
                    app.processEvents()
                tab = window._tabs_data[window._tab_widget.currentIndex()]
                tab.view.fit_content()
                app.processEvents()
                out_path = out_dir / out_name
                window.grab().save(str(out_path))
                result["captures"][label] = out_name
                scan_language(window, label)
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(f"{label}: {exc}")
        if window._theme != THEME_LIGHT:
            try:
                window.set_theme(THEME_LIGHT)
                app.processEvents()
            except Exception:  # noqa: BLE001
                pass

        try:
            hub = getattr(window, "_colour_hub", None)
            if hub is not None:
                # A lively colour for the popup (the default active colour is
                # black, which renders the wheel as a flat black disc) --
                # the shared palette's teal tunic tone, set through the
                # window's own real setter, never poked into the widget.
                set_color = getattr(window, "_set_active_color", None)
                if callable(set_color):
                    set_color(P("tunic_base"))
                hub.set_color(P("tunic_base"))
                hub.popup_at(window.mapToGlobal(window.rect().center()))
                app.processEvents()
                out_path = out_dir / "colour-hub.png"
                hub.grab().save(str(out_path))
                scan_language(hub, "colour_hub")
                hub.close()
                result["captures"]["colour_hub"] = "colour-hub.png"
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"colour_hub: {exc}")

        try:
            window._on_user_guide()
            app.processEvents()
            dialog = getattr(window, "_user_guide_dialog", None)
            if dialog is not None:
                dialog.resize(900, 700)
                app.processEvents()
                out_path = out_dir / "user-guide.png"
                dialog.grab().save(str(out_path))
                scan_language(dialog, "user_guide")
                dialog.close()
                result["captures"]["user_guide"] = "user-guide.png"
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"user_guide: {exc}")

    Path(args.result_file).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


def _offscreen_fontdir() -> str:
    """Resolve the OS font directory without hard-coding a drive letter.

    Windows only (this generator runs on the Windows container host): derived
    from the ``SystemRoot`` environment variable Windows itself always sets,
    never a literal path.
    """
    system_root = os.environ.get("SystemRoot", "")
    if not system_root:
        return ""
    return str(Path(system_root) / "Fonts")


def cmd_screenshots(args) -> int:
    _resolve_review_dir(args)
    _resolve_out_dir(args, "screenshots")
    _resolve_tmp_dir(args)
    art_dir_default = Path(args.review_dir) / "art"
    if getattr(args, "scene_project", None) is None:
        candidate = art_dir_default / "layered-scene.pixproj"
        if candidate.exists():
            args.scene_project = str(candidate)
    if getattr(args, "sprite_project", None) is None:
        candidate = art_dir_default / "character-sprite.pixproj"
        if candidate.exists():
            args.sprite_project = str(candidate)
    if getattr(args, "tilemap_project", None) is None:
        candidate = art_dir_default / "tilemap-level.pixproj"
        if candidate.exists():
            args.tilemap_project = str(candidate)
    review_dir = Path(args.review_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gen_path = Path(__file__).resolve()
    prov = ProvenanceLog(review_dir, args.product_root, gen_path)
    prov.prune_missing()

    before_registry = _registry_snapshot_safe()

    settings_root = Path(args.tmp_dir) / "qsettings"
    control_results = []
    chosen_platform = None
    captures = {}

    for platform_env in (None, "offscreen"):
        env = dict(os.environ)
        if platform_env is None:
            env.pop("QT_QPA_PLATFORM", None)
            env.pop("QT_QPA_FONTDIR", None)
            settings_dir = settings_root / "native"
        else:
            env["QT_QPA_PLATFORM"] = platform_env
            font_dir = _offscreen_fontdir()
            if font_dir:
                env["QT_QPA_FONTDIR"] = font_dir
            settings_dir = settings_root / "offscreen"
        result_file = (
            Path(args.tmp_dir) / f"capture-result-{platform_env or 'native'}.json"
        )
        worker_argv = [
            sys.executable,
            str(gen_path),
            "_capture",
            "--product-root",
            args.product_root,
            "--out-dir",
            str(out_dir),
            "--settings-dir",
            str(settings_dir),
            "--result-file",
            str(result_file),
        ]
        if args.scene_project:
            worker_argv += ["--scene-project", args.scene_project]
        if args.sprite_project:
            worker_argv += ["--sprite-project", args.sprite_project]
        if args.tilemap_project:
            worker_argv += ["--tilemap-project", args.tilemap_project]

        proc = subprocess.run(worker_argv, env=env, capture_output=True, text=True)
        entry = {
            "platform_requested": platform_env or "native (unset)",
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            # Symbolic only -- never the resolved absolute path (that would be
            # exactly the drive-letter/absolute-path literal C5 forbids in a
            # provenance/text output); the resolved value is used to launch
            # the worker process and is never itself written to a file.
            "font_dir_configured": bool(env.get("QT_QPA_FONTDIR")),
            "font_dir_source": (
                "env:SystemRoot/Fonts" if env.get("QT_QPA_FONTDIR") else ""
            ),
        }
        if result_file.exists():
            data = json.loads(result_file.read_text(encoding="utf-8"))
            entry.update(data)
        else:
            entry["known_true_signal"] = False
            entry["captures"] = {}
            entry["errors"] = [f"worker produced no result file (rc={proc.returncode})"]
        control_results.append(entry)

        if entry.get("known_true_signal"):
            chosen_platform = entry.get("platform", platform_env or "windows")
            captures = entry.get("captures", {})
            break

    after_registry = _registry_snapshot_safe()
    settings_unchanged = before_registry == after_registry

    (out_dir / "capture-control.json").write_text(
        json.dumps(control_results, indent=2), encoding="utf-8"
    )
    (review_dir / "screenshots-settings-check.json").write_text(
        json.dumps(
            {
                "before": before_registry,
                "after": after_registry,
                "unchanged": settings_unchanged,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # -- language + font control (X.7 / X.8): pulled from the CHOSEN (used)
    # platform's worker result -- the platform every shipped screenshot
    # actually came from -- plus every attempted platform kept for the record.
    chosen_entry = next(
        (c for c in control_results if c.get("platform") == chosen_platform), None
    )
    language_font_control = {
        "platform": chosen_platform,
        "language_control": (chosen_entry or {}).get(
            "language_control", {"examined": 0, "failed": 0, "findings": []}
        ),
        "font_control": (chosen_entry or {}).get("font_control", {}),
        "language_requested": SCREENSHOT_LANGUAGE,
        "all_platforms": [
            {
                "platform_requested": c.get("platform_requested"),
                "language_control": c.get("language_control"),
                "font_control": c.get("font_control"),
            }
            for c in control_results
        ],
    }
    (out_dir / "language-font-control.json").write_text(
        json.dumps(language_font_control, indent=2), encoding="utf-8"
    )

    for label, out_name in captures.items():
        out_path = out_dir / out_name
        if not out_path.exists():
            continue
        prov.add(
            output_path=out_path,
            command=["python-api", "create_app", "open_document", "QWidget.grab"],
            inputs=[{"capture": label}],
            qt_platform=chosen_platform or "unresolved",
            extra={
                "language": (
                    f"{SCREENSHOT_LANGUAGE} "
                    "(forced via LanguageManager.set_language)"
                ),
                "font_family": SCREENSHOT_FONT_FAMILY,
                "font_point_size": SCREENSHOT_FONT_POINT_SIZE,
            },
        )
    prov.save()

    print(
        json.dumps(
            {
                "chosen_platform": chosen_platform,
                "captures": captures,
                "settings_unchanged": settings_unchanged,
                "control_results": control_results,
                "language_font_control": language_font_control,
            },
            indent=2,
        )
    )
    return 0 if chosen_platform else 1


def _registry_snapshot_safe():
    try:
        return _registry_snapshot()
    except Exception:  # noqa: BLE001
        return {}


# --------------------------------------------------------------------------- #
# public-safe scan (X.2) -- Decision A21-D4
# --------------------------------------------------------------------------- #


def load_vocabulary_patterns(product_root: str):
    path = Path(product_root) / "scripts" / "check_vocabulary_regrowth.py"
    if not path.exists():
        return {}, f"import failed: {path} not found"
    spec = importlib.util.spec_from_file_location(
        "check_vocabulary_regrowth_import", path
    )
    if spec is None or spec.loader is None:
        return {}, "import failed: no loader"
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        return {}, f"import failed: {exc}"
    patterns = dict(getattr(module, "PATTERNS", {}))
    if not patterns:
        return {}, "import succeeded but PATTERNS was empty"
    return patterns, "imported"


def build_extra_patterns() -> dict:
    """Patterns this project's PATTERNS does not cover (Decision A21-D4).

    Every literal this generator would otherwise contain intact is built from
    split fragments, mirroring the split ``"design" + "-docs"`` /
    ``"subagent" + "-report"`` precedent in ``check_vocabulary_regrowth.py`` --
    so scanning this generator's own source never self-triggers these checks.
    """
    import re

    def frag(*parts):
        return "".join(parts)

    # NOTE: dict KEYS must themselves avoid spelling out a forbidden literal --
    # a fragmented pattern VALUE is not enough, because a key that spells the
    # target word out whole is itself a literal match for its own pattern.
    # Keys below are therefore neutral labels, never the forbidden word itself.
    return {
        "of-job-id": re.compile(r"\bOF\d+\b"),
        "ai-assistant-name-1": re.compile(frag("cla", "ude"), re.IGNORECASE),
        "ai-assistant-name-2": re.compile(frag("anthro", "pic"), re.IGNORECASE),
        "generated-with-phrase": re.compile(frag("generat", "ed with"), re.IGNORECASE),
        "commit-trailer-tag": re.compile(frag("co-autho", "red-by"), re.IGNORECASE),
        "ai-origin-tag": re.compile(frag("ai-gen", "erated"), re.IGNORECASE),
        "windows-drive-letter": re.compile(r"\b[A-Za-z]:[\\/]"),
        "local-username": re.compile(frag("Usuar", "io")),
    }


#: The check's own prior-run report is excluded from its own input set: it is
#: a record OF findings (their matched tokens quoted as evidence), not a
#: shipped output, and scanning it would self-amplify every past finding on
#: every re-run. Every other text output -- including provenance and this
#: generator's own source -- is scanned.
_SCAN_EXCLUDE_NAMES = {"check-results.json"}


def iter_text_outputs(review_dir: Path):
    for pattern in ("**/*.md", "**/*.json", "**/*.py"):
        for p in sorted(review_dir.glob(pattern)):
            if p.is_file() and p.name not in _SCAN_EXCLUDE_NAMES:
                yield p


def iter_image_outputs(review_dir: Path):
    for pattern in ("**/*.png", "**/*.gif"):
        for p in sorted(review_dir.glob(pattern)):
            if p.is_file():
                yield p


def iter_pixproj_outputs(review_dir: Path):
    for p in sorted(review_dir.glob("**/*.pixproj")):
        if p.is_file():
            yield p


def scan_text_for_patterns(text: str, patterns: dict, file_label: str, location: str):
    findings = []
    for name, rx in patterns.items():
        for m in rx.finditer(text):
            findings.append(
                {
                    "file": file_label,
                    "pattern": name,
                    "token": m.group(0),
                    "location": location,
                }
            )
    return findings


def scan_image_metadata(path: Path, patterns: dict):
    from PIL import Image

    findings = []
    try:
        with Image.open(path) as im:
            parts = []
            for k, v in im.info.items():
                if isinstance(v, bytes):
                    v = v.decode("utf-8", "replace")
                if isinstance(v, str):
                    parts.append(f"{k}={v}")
            info_text = " ".join(parts)
        findings.extend(
            scan_text_for_patterns(info_text, patterns, str(path), "image-metadata")
        )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "file": str(path),
                "pattern": "scan-error",
                "token": str(exc),
                "location": "image-metadata",
            }
        )
    return findings


def scan_pixproj_metadata(path: Path, patterns: dict):
    findings = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.get("metadata", {})
        text = json.dumps(meta)
        findings.extend(
            scan_text_for_patterns(text, patterns, str(path), "pixproj-metadata")
        )
    except Exception as exc:  # noqa: BLE001
        findings.append(
            {
                "file": str(path),
                "pattern": "scan-error",
                "token": str(exc),
                "location": "pixproj-metadata",
            }
        )
    return findings


# --------------------------------------------------------------------------- #
# check sub-command (THE CHECK CONTRACT)
# --------------------------------------------------------------------------- #


def cmd_check(args) -> int:
    _resolve_review_dir(args)
    _resolve_tmp_dir(args)
    review_dir = Path(args.review_dir)
    product_root = args.product_root
    results = {}
    exit_nonzero = False
    partial_reasons = []

    # X.1 -- publication
    social_png = review_dir / "social" / "social-preview.png"
    if social_png.exists():
        from PIL import Image

        with Image.open(social_png) as im:
            dims_ok = im.size == (1280, 640)
            fmt_ok = im.format in ("PNG", "JPEG", "GIF")
        size_ok = social_png.stat().st_size < 1_000_000
        failed = 0 if (dims_ok and fmt_ok and size_ok) else 1
        results["X.1-social-preview"] = {
            "examined": 1,
            "failed": failed,
            "dims_ok": dims_ok,
            "size_ok": size_ok,
            "format": im.format,
        }
        if failed:
            exit_nonzero = True
    else:
        results["X.1-social-preview"] = {"examined": 0, "failed": 0}
        exit_nonzero = True

    if args.readme_budget_png_bytes or args.readme_budget_gif_bytes:
        art_dir = review_dir / "art"
        png_budget = args.readme_budget_png_bytes
        gif_budget = args.readme_budget_gif_bytes
        png_files = list(art_dir.glob("*.png")) if png_budget else []
        gif_files = list(art_dir.glob("*.gif")) if gif_budget else []
        examined = len(png_files) + len(gif_files)
        failed_files = [str(p.name) for p in png_files if p.stat().st_size > png_budget]
        failed_files += [
            str(p.name) for p in gif_files if p.stat().st_size > gif_budget
        ]
        results["X.1-readme-budget"] = {
            "examined": examined,
            "failed": len(failed_files),
            "png_budget_bytes": png_budget,
            "gif_budget_bytes": gif_budget,
            "over_budget": failed_files,
        }
        if examined == 0 or failed_files:
            exit_nonzero = True
    else:
        results["X.1-readme-budget"] = {"status": "not run - budget not grounded"}
        partial_reasons.append("X.1-readme-budget: not run - budget not grounded")

    # X.2 -- public-safe scan
    patterns, import_status = load_vocabulary_patterns(product_root)
    extra = build_extra_patterns()
    all_patterns = dict(patterns)
    all_patterns.update(extra)
    findings = []
    examined = 0
    for p in iter_text_outputs(review_dir):
        examined += 1
        text = p.read_text(encoding="utf-8", errors="replace")
        findings.extend(scan_text_for_patterns(text, all_patterns, str(p), "text-file"))
    for p in iter_image_outputs(review_dir):
        examined += 1
        findings.extend(scan_image_metadata(p, all_patterns))
    for p in iter_pixproj_outputs(review_dir):
        examined += 1
        findings.extend(scan_pixproj_metadata(p, all_patterns))
    results["X.2-public-safe-scan"] = {
        "examined": examined,
        "failed": len(findings),
        "vocabulary_import": import_status,
        "findings": findings,
    }
    if examined == 0 or findings:
        exit_nonzero = True

    # X.3 -- re-derivation (art only, decoded pixels)
    x3 = _run_rederivation(args)
    results["X.3-re-derivation"] = x3
    if x3.get("examined", 0) == 0 or x3.get("failed", 0):
        exit_nonzero = True

    # X.4 -- provenance completeness
    prov_path = review_dir / "provenance.json"
    entries = (
        json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.exists() else []
    )
    missing = []
    for e in entries:
        miss = [
            f
            for f in REQUIRED_PROVENANCE_FIELDS
            if f not in e or (e[f] is None and f != "output_size_bytes")
        ]
        if miss:
            missing.append({"output": e.get("output"), "missing": miss})
    results["X.4-provenance"] = {
        "examined": len(entries),
        "failed": len(missing),
        "missing": missing,
    }
    if len(entries) == 0 or missing:
        exit_nonzero = True

    # X.5 -- capture control
    control_path = review_dir / "screenshots" / "capture-control.json"
    if control_path.exists():
        controls = json.loads(control_path.read_text(encoding="utf-8"))
        examined = len(controls)
        any_known_true = any(c.get("known_true_signal") for c in controls)
        failed = 0 if any_known_true else examined
        results["X.5-capture-control"] = {"examined": examined, "failed": failed}
        if examined == 0 or failed:
            exit_nonzero = True

        # X.5b -- text-render control (the offscreen font-database check this
        # revision adds: every platform attempt records font_families_count /
        # text_render_ok; the chosen (used) platform must have text_render_ok).
        chosen = None
        for c in controls:
            if c.get("known_true_signal"):
                chosen = c
                break
        tr_examined = len(controls)
        tr_failed = sum(1 for c in controls if "text_render_ok" not in c)
        chosen_ok = bool(chosen and chosen.get("text_render_ok"))
        results["X.5-text-render-control"] = {
            "examined": tr_examined,
            "failed": tr_failed,
            "chosen_platform_text_render_ok": chosen_ok,
            "per_platform": [
                {
                    "platform": c.get("platform_requested"),
                    "font_families_count": c.get("font_families_count"),
                    "font_ink_ratio": c.get("font_ink_ratio"),
                    "text_render_ok": c.get("text_render_ok"),
                }
                for c in controls
            ],
        }
        if tr_examined == 0 or tr_failed or (chosen is not None and not chosen_ok):
            exit_nonzero = True
    else:
        results["X.5-capture-control"] = {
            "status": "not run - no screenshots captured this session"
        }
        partial_reasons.append(
            "X.5-capture-control: not run - no screenshots captured this session"
        )
        results["X.5-text-render-control"] = {
            "status": "not run - no screenshots captured this session"
        }
        partial_reasons.append(
            "X.5-text-render-control: not run - no screenshots captured this session"
        )

    # X.7 / X.8 -- language control (no Spanish-catalogue string visible in a
    # captured widget's text) and font control (effective app font family ==
    # the requested real-Windows-UI-font family, and that family exists in
    # QFontDatabase) -- review round 2 additions, read from the CHOSEN
    # platform's worker result.
    lf_path = review_dir / "screenshots" / "language-font-control.json"
    if lf_path.exists():
        lf = json.loads(lf_path.read_text(encoding="utf-8"))
        lc = lf.get("language_control") or {}
        lc_examined = lc.get("examined", 0)
        lc_failed = lc.get("failed", 0)
        results["X.7-language-control"] = {
            "examined": lc_examined,
            "failed": lc_failed,
            "findings": lc.get("findings", []),
        }
        if lc_examined == 0 or lc_failed:
            exit_nonzero = True

        fc = lf.get("font_control") or {}
        fc_examined = 1 if fc else 0
        fc_failed = 0 if fc.get("ok") else fc_examined
        results["X.8-font-control"] = {
            "examined": fc_examined,
            "failed": fc_failed,
            "family_requested": fc.get("family_requested"),
            "family_effective": fc.get("family_effective"),
            "family_available": fc.get("family_available"),
        }
        if fc_examined == 0 or fc_failed:
            exit_nonzero = True
    else:
        results["X.7-language-control"] = {
            "status": "not run - no screenshots captured this session"
        }
        partial_reasons.append(
            "X.7-language-control: not run - no screenshots captured this session"
        )
        results["X.8-font-control"] = {
            "status": "not run - no screenshots captured this session"
        }
        partial_reasons.append(
            "X.8-font-control: not run - no screenshots captured this session"
        )

    # X.6 -- canvas bounds
    bounds_path = review_dir / "art" / "canvas-bounds.json"
    if bounds_path.exists():
        b = json.loads(bounds_path.read_text(encoding="utf-8"))
        ok = b.get("ok", [])
        fail = b.get("failures", [])
        results["X.6-canvas-bounds"] = {
            "examined": len(ok) + len(fail),
            "failed": len(fail),
        }
        if (len(ok) + len(fail)) == 0 or fail:
            exit_nonzero = True
    else:
        results["X.6-canvas-bounds"] = {
            "status": "not run - no art generated this session"
        }
        partial_reasons.append(
            "X.6-canvas-bounds: not run - no art generated this session"
        )

    for name, r in results.items():
        if "status" in r:
            print(f"{name}: {r['status']}")
        else:
            print(f"{name}: examined={r['examined']} failed={r['failed']}")

    (review_dir / "check-results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    if partial_reasons:
        print("PARTIAL reasons:")
        for reason in partial_reasons:
            print(f"  - {reason}")

    return 1 if exit_nonzero else 0


def _run_rederivation(args) -> dict:
    review_dir = Path(args.review_dir)
    art_dir = review_dir / "art"
    if not art_dir.exists():
        return {
            "examined": 0,
            "failed": 0,
            "note": "no art directory to re-derive against",
        }

    import numpy as np
    from PIL import Image

    tmp_redo = Path(args.tmp_dir) / "rederive"
    tmp_redo.mkdir(parents=True, exist_ok=True)
    mods = load_product_modules(args.product_root)
    prov_throwaway = ProvenanceLog(
        tmp_redo, args.product_root, Path(__file__).resolve()
    )
    ctx = {"canvas_bounds_ok": [], "canvas_bounds_failures": []}

    build_sprite(mods, tmp_redo, prov_throwaway, ctx)
    build_scene(mods, tmp_redo, prov_throwaway, ctx)
    build_tilemap(mods, tmp_redo, prov_throwaway, ctx)
    build_procgen_set(
        mods, tmp_redo, prov_throwaway, ctx, Path(args.tmp_dir) / "rederive-tmp"
    )

    compare_files = [
        "character-sprite-sheet.png",
        "layered-scene.png",
        "tilemap-level.png",
        "procgen-contact-sheet.png",
    ]
    examined = 0
    failed = 0
    mismatches = []
    for name in compare_files:
        orig = art_dir / name
        redo = tmp_redo / name
        examined += 1
        if not orig.exists() or not redo.exists():
            failed += 1
            mismatches.append({"file": name, "reason": "missing"})
            continue
        a = np.array(Image.open(orig).convert("RGBA"))
        b = np.array(Image.open(redo).convert("RGBA"))
        if a.shape != b.shape or not np.array_equal(a, b):
            failed += 1
            mismatches.append({"file": name, "reason": "decoded-pixel mismatch"})

    return {
        "examined": examined,
        "failed": failed,
        "mismatches": mismatches,
        "note": "compares decoded pixels (PIL), never raw bytes",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="generate_showcase.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    # Every path default below is resolved relative to ``--product-root``
    # (which itself defaults to this file's own repo root,
    # ``DEFAULT_PRODUCT_ROOT``) inside the matching ``cmd_*`` function, not
    # here -- an overridden ``--product-root`` must move every other default
    # with it, and argparse defaults are computed once at parse time, before
    # ``--product-root`` is known to have been overridden.
    p_art = sub.add_parser("art", help="build the four example art pieces")
    p_art.add_argument("--product-root", default=DEFAULT_PRODUCT_ROOT)
    p_art.add_argument(
        "--out-dir", default=None, help="default: <product-root>/docs/images/art"
    )
    p_art.add_argument(
        "--review-dir", default=None, help="default: <product-root>/docs/images"
    )
    p_art.add_argument(
        "--tmp-dir", default=None, help="default: <product-root>/dev-docs/showcase-tmp"
    )
    p_art.set_defaults(func=cmd_art)

    p_social = sub.add_parser("social", help="compose the 1280x640 social preview")
    p_social.add_argument("--product-root", default=DEFAULT_PRODUCT_ROOT)
    p_social.add_argument(
        "--out-dir", default=None, help="default: <product-root>/docs/images/social"
    )
    p_social.add_argument(
        "--review-dir", default=None, help="default: <product-root>/docs/images"
    )
    p_social.add_argument(
        "--art-dir", default=None, help="default: <product-root>/docs/images/art"
    )
    p_social.add_argument("--tagline", required=True)
    p_social.set_defaults(func=cmd_social)

    p_shots = sub.add_parser("screenshots", help="capture real-application screenshots")
    p_shots.add_argument("--product-root", default=DEFAULT_PRODUCT_ROOT)
    p_shots.add_argument(
        "--out-dir",
        default=None,
        help="default: <product-root>/docs/images/screenshots",
    )
    p_shots.add_argument(
        "--review-dir", default=None, help="default: <product-root>/docs/images"
    )
    p_shots.add_argument(
        "--tmp-dir", default=None, help="default: <product-root>/dev-docs/showcase-tmp"
    )
    p_shots.add_argument(
        "--scene-project",
        default=None,
        help=(
            "default: <product-root>/docs/images/art/layered-scene.pixproj, "
            "if present"
        ),
    )
    p_shots.add_argument(
        "--sprite-project",
        default=None,
        help=(
            "default: <product-root>/docs/images/art/character-sprite.pixproj, "
            "if present"
        ),
    )
    p_shots.add_argument(
        "--tilemap-project",
        default=None,
        help=(
            "default: <product-root>/docs/images/art/tilemap-level.pixproj, "
            "if present"
        ),
    )
    p_shots.set_defaults(func=cmd_screenshots)

    p_capture = sub.add_parser("_capture", help=argparse.SUPPRESS)
    p_capture.add_argument("--product-root", required=True)
    p_capture.add_argument("--out-dir", required=True)
    p_capture.add_argument("--settings-dir", required=True)
    p_capture.add_argument("--result-file", required=True)
    p_capture.add_argument("--scene-project")
    p_capture.add_argument("--sprite-project")
    p_capture.add_argument("--tilemap-project")
    p_capture.set_defaults(func=cmd_capture_worker)

    p_check = sub.add_parser(
        "check", help="run every X.1-X.6 check and print examined/failed"
    )
    p_check.add_argument("--product-root", default=DEFAULT_PRODUCT_ROOT)
    p_check.add_argument(
        "--review-dir", default=None, help="default: <product-root>/docs/images"
    )
    p_check.add_argument(
        "--tmp-dir", default=None, help="default: <product-root>/dev-docs/showcase-tmp"
    )
    p_check.add_argument("--readme-budget-png-bytes", type=int, default=0)
    p_check.add_argument("--readme-budget-gif-bytes", type=int, default=0)
    p_check.set_defaults(func=cmd_check)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
