"""Shared pieces of the Nifen Art specimen renderers.

Holds the 3x5 label face used for sheet annotations (an original throwaway
face, separate from the typeface under test), the palette starting points the
specimens use, and the read-only bridge to the product package.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Tuple


# --- palette roles ------------------------------------------------------------------
def hex_rgb(value: str) -> Tuple[int, int, int, int]:
    """#RRGGBB to an opaque RGBA tuple."""
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError("expected #RRGGBB, got %r" % value)
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), 255)


def load_roles(path: str) -> Dict[str, Dict[str, Tuple[int, int, int, int]]]:
    """Read a palette roles file; returns {"light": {role: rgba}, "dark": {...}}."""
    import json

    with open(path, "rb") as fh:
        data = json.loads(fh.read().decode("utf-8"))
    out = {}
    for mode in ("light", "dark"):
        out[mode] = {k: hex_rgb(v) for k, v in data[mode].items() if len(v) == 7}
    return out


# Sheet colours derived from the roles: the chart cells use the surface as the
# ground and tint the em-box zones with the hover, pressed and background roles.
def sheet_theme(
    roles: Dict[str, Tuple[int, int, int, int]],
) -> Dict[str, Tuple[int, int, int, int]]:
    return {
        "bg": roles["surface"],
        "ink": roles["text"],
        "accent": roles["accent"],
        "tint": roles["hover"],
        "tint2": roles["pressed"],
        "tint3": roles["surface"],
        "rule": roles["focus"],
    }


THEMES: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {}


def set_palette(path: str) -> None:
    """Load the palette roles file and fill THEMES for both modes."""
    for mode, roles in load_roles(path).items():
        THEMES[mode] = sheet_theme(roles)


TINY: Dict[str, List[str]] = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "##.", ".##"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", ".#.", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"],
    "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "##."],
    "-": ["...", "...", "###", "...", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    ":": ["...", ".#.", "...", ".#.", "..."],
    ".": ["...", "...", "...", "...", ".#."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "(": [".#.", "#..", "#..", "#..", ".#."],
    ")": [".#.", "..#", "..#", "..#", ".#."],
    "=": ["...", "###", "...", "###", "..."],
    "x": ["...", "#.#", ".#.", "#.#", "..."],
    " ": ["..", "..", "..", "..", ".."],
}


def tiny_pixels(text: str) -> Tuple[List[Tuple[int, int]], int]:
    """Pixels (x, row) of the label face, row 0 at the top; and the width."""
    out: List[Tuple[int, int]] = []
    pen = 0
    for ch in text.upper():
        glyph = TINY.get(ch)
        if glyph is None:
            glyph = TINY[" "]
        for r, row in enumerate(glyph):
            for c, v in enumerate(row):
                if v == "#":
                    out.append((pen + c, r))
        pen += len(glyph[0]) + 1
    return out, max(pen - 1, 0)


def add_product_path() -> None:
    """Make the product package importable (read-only use, no bytecode)."""
    sys.dont_write_bytecode = True
    root = os.environ.get("NIFEN_PRODUCT_ROOT") or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if root not in sys.path:
        sys.path.insert(0, root)


def export_png(buffer, out_png: str, work_dir: str) -> int:
    """Write a PixelBuffer through the product's own export CLI; return exit code."""
    add_product_path()
    from pixelart_creator.data.export_cli import main as export_main
    from pixelart_creator.data.project_io import save_project
    from pixelart_creator.logic.document import Document

    os.makedirs(work_dir, exist_ok=True)
    doc = Document.from_buffer(buffer, name="Sheet")
    pix = save_project(doc, os.path.join(work_dir, "sheet.pixproj"))
    return export_main(
        ["--input", str(pix), "--format", "png", "--output", out_png, "--no-json"]
    )
