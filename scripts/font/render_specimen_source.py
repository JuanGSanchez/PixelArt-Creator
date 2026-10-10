"""Pixel-exact Nifen Art specimen sheets rendered from the glyph SOURCES.

Every sheet is drawn into the product's PixelBuffer and written by the
product's own export path (the pixelart-export entry point), at 1x and at an
integer scale, so what the sheet shows is the grid itself, not a rasteriser's
opinion of it.

Usage:
    python scripts/font/render_specimen_source.py --out <folder> --palette <roles>
        [--src <sources>] [--ts-dir <catalogues>] [--work <scratch>] [--label <text>]

Run from the repository root (the product package is imported from there,
read-only; NIFEN_PRODUCT_ROOT overrides the root).
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_SRC = os.path.join(REPO, "fonts-src", "nifen-art")
DEFAULT_TS = os.path.join(REPO, "pixelart_creator", "i18n")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import specimen_common as sc  # noqa: E402
import specimen_content as content_mod  # noqa: E402
import specimen_mock as mock  # noqa: E402
from nifen_src import Font, make_console_safe, parse_sources  # noqa: E402

SCALE_HI = 4
KANA_TABLES = [
    ("Hiragana", content_mod.HIRAGANA_TABLE),
    ("Katakana", content_mod.KATAKANA_TABLE),
    (
        "Hiragana, voiced and semi-voiced (composed by recipe)",
        content_mod.HIRAGANA_VOICED,
    ),
    (
        "Katakana, voiced and semi-voiced (composed by recipe)",
        content_mod.KATAKANA_VOICED,
    ),
]


class Sheet:
    """A PixelBuffer plus a scale: drawing calls take 1x source coordinates."""

    def __init__(self, w, h, scale, theme):
        from pixelart_creator.logic.pixel_buffer import PixelBuffer

        self.scale = scale
        self.w, self.h = w, h
        self.theme = sc.THEMES[theme]
        self.buf = PixelBuffer(w * scale, h * scale, fill=self.theme["bg"])

    def rect(self, x, y, w, h, color):
        s = self.scale
        self.buf.fill_rect(
            x * s,
            y * s,
            w * s,
            h * s,
            self.theme[color] if isinstance(color, str) else color,
        )

    def pixel(self, x, y, color):
        self.rect(x, y, 1, 1, color)

    def glyph(self, px, ox, baseline, color="ink"):
        """Draw source pixels, pen origin at ox and the baseline at row `baseline`."""
        for x, y in px:
            self.pixel(ox + x, baseline - 1 - y, color)

    def tiny(self, x, y, text, color="ink", mult=1):
        pts, _w = sc.tiny_pixels(text)
        s = self.scale
        col = self.theme[color]
        for px_, py_ in pts:
            self.buf.fill_rect(
                (x + px_ * mult) * s, (y + py_ * mult) * s, mult * s, mult * s, col
            )


def zone_tints(sheet, x, w, baseline):
    """Tint the 12-row em box in three zones so baseline and x-height read."""
    for y in range(-2, 10):
        if y < 0:
            color = "tint2"
        elif y < 5:
            color = "tint3"
        else:
            color = "tint"
        sheet.rect(x, baseline - 1 - y, w, 1, color)


SYMBOL_RANGES = [
    (0x21, 0x2F),
    (0x3A, 0x40),
    (0x5B, 0x60),
    (0x7B, 0x7E),
    (0xA1, 0xBF),
    (0xD7, 0xD7),
    (0xF7, 0xF7),
    (0x2C6, 0x2DD),
    (0x2000, 0x2BFF),
    (0x394, 0x394),
]


def is_symbol(cp):
    return any(lo <= cp <= hi for lo, hi in SYMBOL_RANGES)


def chart(font, theme, scale, label, only_symbols=False, cols=36):
    cps = [cp for cp in font.codepoints() if (not only_symbols or is_symbol(cp))]
    cell_w, band_h, label_h = 20, 15, 8
    cell_h = band_h * 2 + label_h + 2
    rows = (len(cps) + cols - 1) // cols
    head = 10
    sheet = Sheet(cols * cell_w + 2, head + rows * cell_h + 2, scale, theme)
    if only_symbols:
        title = "NIFEN ART %s   SYMBOLS   REGULAR OVER BOLD" % label
    else:
        title = (
            "NIFEN ART %s   ALL CHARACTERS   REGULAR OVER BOLD   EM BOX 12 ROWS   "
            "TICKS MARK THE ADVANCE" % label
        )
    sheet.tiny(3, 2, title)
    for i, cp in enumerate(cps):
        cx = 1 + (i % cols) * cell_w
        cy = head + (i // cols) * cell_h
        for k, weight in enumerate(("regular", "bold")):
            band_top = cy + k * band_h
            baseline = band_top + 12  # rows y=11 .. y=-3 fit in 15 rows
            zone_tints(sheet, cx, cell_w - 2, baseline)
            b = font.bmp(cp, weight)
            sheet.glyph(b.px, cx + 2, baseline)
            sheet.pixel(cx + 2, baseline + 2, "accent")
            sheet.pixel(cx + 2 + b.adv, baseline + 2, "accent")
        code = "%04X" % cp
        _pts, lw = sc.tiny_pixels(code)
        sheet.tiny(cx + (cell_w - 2 - lw) // 2, cy + band_h * 2 + 2, code)
    return sheet


def scene_sheet(scene, w, h):
    """Paint a scene's ops into a PixelBuffer (device pixels, scale in the ops)."""
    from pixelart_creator.logic.pixel_buffer import PixelBuffer

    k = scene.k
    buf = PixelBuffer(w * k, h * k, fill=(0, 0, 0, 255))
    for op in scene.ops:
        if op[0] == "fill":
            _t, x, y, fw, fh, col = op
            buf.fill_rect(x, y, fw, fh, col + (255,))
        else:
            _t, x, base, text, weight, col = op
            pen = 0
            for ch in text:
                b = scene.font.bmp(ord(ch), weight)
                for gx, gy in b.px:
                    buf.fill_rect(
                        x + (pen + gx) * k, base - (gy + 1) * k, k, k, col + (255,)
                    )
                pen += b.adv
    return buf


def contract_diagram(font, theme, s=12):
    """The grid contract drawn at s device pixels per source pixel."""
    left = 190  # legend column, device pixels
    glyphs = "HngdÁÑЁΆあガ"
    placed, pen = [], 0
    for ch in glyphs:
        b = font.bmp(ord(ch), "regular")
        placed.append((pen, b))
        pen += b.adv + 2
    top_y, bot_y = 12, -4
    width = left + pen * s + 24
    height = (top_y - bot_y + 1) * s + 16
    sheet = Sheet(width, height, 1, theme)
    org = 8  # top margin

    def row_top(y):  # device y of the top edge of pixel row y
        return org + (top_y - y) * s

    gx0 = left
    # zone tints
    for y in range(bot_y, top_y + 1):
        if -3 <= y < 0:
            color = "tint2"
        elif 0 <= y < 5:
            color = "tint3"
        elif 5 <= y < 11:
            color = "tint"
        else:
            color = None
        if color:
            sheet.rect(gx0, row_top(y), pen * s + 8, s, color)
    # ink
    for off, b in placed:
        for x, y in b.px:
            sheet.rect(gx0 + 4 + (off + x) * s, row_top(y), s, s, "ink")
    # rules at row boundaries, with labels (boundary above row y is row_top(y))
    rules = [
        (11, "LINE TOP 11"),
        (10, "EM TOP 10"),
        (8, "ASC 8"),
        (7, "CAP 7"),
        (5, "X 5"),
        (0, "BASELINE 0"),
        (-2, "EM BOTTOM -2"),
        (-3, "LINE BOTTOM -3"),
    ]
    for boundary, text in rules:
        dy = org + (top_y + 1 - boundary) * s
        sheet.rect(left - 14, dy, pen * s + 22 + 14, 1, "rule")
        sheet.tiny(4, dy - 5, text, mult=2)
    sheet.tiny(4, height - 10, "ROWS COUNT UP FROM THE BASELINE", mult=1)
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--work",
        default=None,
        help="scratch folder (default: a new system temporary folder)",
    )
    ap.add_argument("--ts-dir", default=DEFAULT_TS)
    ap.add_argument("--palette", required=True)
    ap.add_argument("--label", default="")
    args = ap.parse_args()
    make_console_safe()
    if not args.work:
        import tempfile

        args.work = tempfile.mkdtemp(prefix="nifen-sheet-")
    sc.add_product_path()
    sc.set_palette(args.palette)

    font = Font(parse_sources(args.src))
    roles = sc.load_roles(args.palette)
    contents = {lang: content_mod.build(args.ts_dir, lang) for lang in ("en", "es")}
    os.makedirs(args.out, exist_ok=True)
    rc_total = 0
    made = []

    def emit(buf, name):
        nonlocal rc_total
        out = os.path.join(args.out, name)
        rc = sc.export_png(buf, out, args.work)
        rc_total += rc
        made.append((name, buf.width, buf.height, rc))

    for scale in (1, SCALE_HI):
        tag = "%dx" % scale
        for mode in ("light", "dark"):
            emit(
                chart(font, mode, scale, args.label).buf,
                "source-chart-%s-%s.png" % (mode, tag),
            )
            emit(
                chart(font, mode, scale, args.label, only_symbols=True, cols=12).buf,
                "source-symbol-chart-%s-%s.png" % (mode, tag),
            )
            en, es = contents["en"], contents["es"]
            r = roles[mode]
            scenes = [
                ("ui-en", mock.scene_ui(font, scale, r, en)),
                ("ui-es", mock.scene_ui(font, scale, r, es)),
                (
                    "text-es",
                    mock.scene_text(
                        font,
                        scale,
                        r,
                        es,
                        en,
                        content_mod.SPECIMEN_ES,
                        content_mod.MIXED_LINES,
                    ),
                ),
                (
                    "text-en",
                    mock.scene_text(
                        font,
                        scale,
                        r,
                        en,
                        es,
                        content_mod.SPECIMEN_EN,
                        content_mod.MIXED_LINES,
                    ),
                ),
                (
                    "alphabet",
                    mock.scene_alphabet(font, scale, r, content_mod.ALPHABET_LINES),
                ),
                ("european", mock.scene_euro(font, scale, r, content_mod.EURO_LINES)),
                (
                    "symbols",
                    mock.scene_symbols(
                        font,
                        scale,
                        r,
                        content_mod.SYMBOL_LINES,
                        content_mod.SYMBOL_CONTEXT,
                    ),
                ),
                ("ui-ru", mock.scene_ui(font, scale, r, content_mod.RUSSIAN_UI)),
                (
                    "cyrillic",
                    mock.scene_euro(font, scale, r, content_mod.CYRILLIC_LINES),
                ),
                ("greek", mock.scene_euro(font, scale, r, content_mod.GREEK_LINES)),
                (
                    "french-german",
                    mock.scene_euro(font, scale, r, content_mod.FRENCH_GERMAN_LINES),
                ),
                ("ui-ja", mock.scene_ui(font, scale, r, content_mod.JAPANESE_UI)),
                (
                    "kana-tables",
                    mock.scene_kana_table(
                        font, scale, r, KANA_TABLES, content_mod.KANA_SMALL_ROWS
                    ),
                ),
                (
                    "kana-words",
                    mock.scene_euro(font, scale, r, content_mod.JAPANESE_LINES),
                ),
                (
                    "kana-latin",
                    mock.scene_euro(font, scale, r, content_mod.MIXED_JA_LINES),
                ),
            ]
            for name, (scene, w, h) in scenes:
                emit(
                    scene_sheet(scene, w, h), "source-%s-%s-%s.png" % (name, mode, tag)
                )
    emit(contract_diagram(font, "light", 12).buf, "grid-contract-diagram.png")
    for name, w, h, rc in made:
        print("%-40s %5d x %-5d export exit %d" % (name, w, h, rc))
    print(
        "sheets written: %d, export failures: %d"
        % (len(made), sum(1 for m in made if m[3] != 0))
    )
    return 0 if rc_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
