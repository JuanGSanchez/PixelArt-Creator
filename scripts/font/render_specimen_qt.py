"""Nifen Art interface specimens rendered from the BUILT fonts through Qt.

For each size (12 and 24 px), mode (Light, Dark) and scene, the scene's ops are
painted twice: by Qt (QFont with NoAntialias and PreferNoHinting, the setting
the application will use) and by a numpy canvas straight from the glyph-grid
sources. The two images are compared pixel for pixel; the Qt image is saved as
the specimen. Two negative controls (text moved one pixel, antialiasing left
on) must produce mismatches, otherwise the comparison cannot be trusted.

    python scripts/font/render_specimen_qt.py --out <folder> --palette <roles>
        [--font-dir <built fonts>] [--src <sources>] [--ts-dir <catalogues>]

Run from the repository root; the defaults are the repository's own folders.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DEFAULT_SRC = os.path.join(REPO, "fonts-src", "nifen-art")
DEFAULT_FONTS = os.path.join(REPO, "pixelart_creator", "fonts")
DEFAULT_TS = os.path.join(REPO, "pixelart_creator", "i18n")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import specimen_common as sc  # noqa: E402
import specimen_content as content_mod  # noqa: E402
import specimen_mock as mock  # noqa: E402
from nifen_src import Font, make_console_safe, parse_sources  # noqa: E402

SIZES = (12, 24)
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
MODES = ("light", "dark")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", default=DEFAULT_FONTS)
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ts-dir", default=DEFAULT_TS)
    ap.add_argument("--palette", required=True)
    ap.add_argument("--platform", default=None)
    args = ap.parse_args()
    make_console_safe()
    if args.platform:
        os.environ["QT_QPA_PLATFORM"] = args.platform

    import PySide6
    from PySide6.QtCore import QPointF, Qt, qVersion
    from PySide6.QtGui import (
        QColor,
        QFont,
        QFontDatabase,
        QFontMetrics,
        QGuiApplication,
        QImage,
        QPainter,
    )

    app = QGuiApplication(sys.argv[:1])
    ids = {}
    for w, name in (("regular", "NifenArt-Regular.ttf"), ("bold", "NifenArt-Bold.ttf")):
        fid = QFontDatabase.addApplicationFont(os.path.join(args.font_dir, name))
        ids[w] = fid
        print(
            "addApplicationFont %-22s -> id %d families %s"
            % (name, fid, QFontDatabase.applicationFontFamilies(fid))
        )
        if fid < 0:
            return 1
    family = QFontDatabase.applicationFontFamilies(ids["regular"])[0]
    print(
        "Qt %s, PySide6 %s, platform plugin %s"
        % (qVersion(), PySide6.__version__, app.platformName())
    )

    font = Font(parse_sources(args.src))
    palette = sc.load_roles(args.palette)
    contents = {lang: content_mod.build(args.ts_dir, lang) for lang in ("en", "es")}
    os.makedirs(args.out, exist_ok=True)

    def make_font(weight, px, antialias=False):
        f = QFont(family)
        f.setPixelSize(px)
        f.setWeight(QFont.Weight.Bold if weight == "bold" else QFont.Weight.Normal)
        f.setStyleStrategy(
            QFont.StyleStrategy.NoAntialias
            if not antialias
            else QFont.StyleStrategy.PreferAntialias
        )
        f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        return f

    def paint_qt(scene, W, H, k, shift=0, antialias=False):
        img = QImage(W * k, H * k, QImage.Format.Format_RGB32)
        img.fill(QColor(0, 0, 0))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, antialias)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        fonts = {w: make_font(w, 12 * k, antialias) for w in ("regular", "bold")}
        for op in scene.ops:
            if op[0] == "fill":
                _t, x, y, w, h, col = op
                p.fillRect(x, y, w, h, QColor(*col))
            else:
                _t, x, base, s, weight, col = op
                p.setFont(fonts[weight])
                p.setPen(QColor(*col))
                p.drawText(QPointF(x + shift, base), s)
        p.end()
        return img

    def to_array(img):
        w, h = img.width(), img.height()
        buf = np.frombuffer(img.constBits(), dtype=np.uint8)
        return (
            buf.reshape(h, img.bytesPerLine())[:, : w * 4]
            .reshape(h, w, 4)[:, :, [2, 1, 0]]
            .copy()
        )

    # Qt's own advance against the source advance, for every distinct line drawn
    advance_checked, advance_bad = 0, []

    def check_advances(scene, k):
        nonlocal advance_checked
        fm = {w: QFontMetrics(make_font(w, 12 * k)) for w in ("regular", "bold")}
        seen = set()
        for op in scene.ops:
            if op[0] != "text":
                continue
            _t, _x, _b, s, weight, _c = op
            if (s, weight) in seen:
                continue
            seen.add((s, weight))
            advance_checked += 1
            want = sum(font.bmp(ord(ch), weight).adv for ch in s) * k
            got = fm[weight].horizontalAdvance(s)
            if got != want:
                advance_bad.append((s[:30], weight, k, want, got))

    def scenes_for(mode, k):
        roles = palette[mode]
        en, es = contents["en"], contents["es"]
        out = []
        out.append(("ui-en", mock.scene_ui(font, k, roles, en)))
        out.append(("ui-es", mock.scene_ui(font, k, roles, es)))
        out.append(
            (
                "text-es",
                mock.scene_text(
                    font,
                    k,
                    roles,
                    es,
                    en,
                    content_mod.SPECIMEN_ES,
                    content_mod.MIXED_LINES,
                ),
            )
        )
        out.append(
            (
                "text-en",
                mock.scene_text(
                    font,
                    k,
                    roles,
                    en,
                    es,
                    content_mod.SPECIMEN_EN,
                    content_mod.MIXED_LINES,
                ),
            )
        )
        out.append(
            (
                "alphabet",
                mock.scene_alphabet(font, k, roles, content_mod.ALPHABET_LINES),
            )
        )
        out.append(
            ("european", mock.scene_euro(font, k, roles, content_mod.EURO_LINES))
        )
        out.append(
            (
                "symbols",
                mock.scene_symbols(
                    font, k, roles, content_mod.SYMBOL_LINES, content_mod.SYMBOL_CONTEXT
                ),
            )
        )
        out.append(("ui-ru", mock.scene_ui(font, k, roles, content_mod.RUSSIAN_UI)))
        out.append(
            ("cyrillic", mock.scene_euro(font, k, roles, content_mod.CYRILLIC_LINES))
        )
        out.append(("greek", mock.scene_euro(font, k, roles, content_mod.GREEK_LINES)))
        out.append(
            (
                "french-german",
                mock.scene_euro(font, k, roles, content_mod.FRENCH_GERMAN_LINES),
            )
        )
        out.append(("ui-ja", mock.scene_ui(font, k, roles, content_mod.JAPANESE_UI)))
        out.append(
            (
                "kana-tables",
                mock.scene_kana_table(
                    font, k, roles, KANA_TABLES, content_mod.KANA_SMALL_ROWS
                ),
            )
        )
        out.append(
            ("kana-words", mock.scene_euro(font, k, roles, content_mod.JAPANESE_LINES))
        )
        out.append(
            ("kana-latin", mock.scene_euro(font, k, roles, content_mod.MIXED_JA_LINES))
        )
        return out

    total_px = 0
    total_bad = 0
    sheets = 0
    ctrl_shift_ok = ctrl_aa_ok = True
    ctrl_rows = []
    for px in SIZES:
        k = px // 12
        for mode in MODES:
            for name, (scene, W, H) in scenes_for(mode, k):
                check_advances(scene, k)
                twin = mock.paint_grid(scene, W, H)
                img = paint_qt(scene, W, H, k)
                got = to_array(img)
                bad = int(np.any(got != twin, axis=2).sum())
                n = int(twin.shape[0] * twin.shape[1])
                total_px += n
                total_bad += bad
                sheets += 1
                fname = "ttf-qt-%s-%dpx-%s.png" % (mode, px, name)
                img.save(os.path.join(args.out, fname), "PNG")
                print(
                    "%-34s %5d x %-5d pixels %9d  mismatching vs source grid %d"
                    % (fname, W * k, H * k, n, bad)
                )
                if px == 12:
                    big = img.scaled(
                        W * k * 4,
                        H * k * 4,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                    big.save(
                        os.path.join(
                            args.out, "ttf-qt-%s-%dpx-%s-view4x.png" % (mode, px, name)
                        ),
                        "PNG",
                    )
                if mode == "light":
                    shifted = int(
                        np.any(
                            to_array(paint_qt(scene, W, H, k, shift=1)) != twin, axis=2
                        ).sum()
                    )
                    aa = int(
                        np.any(
                            to_array(paint_qt(scene, W, H, k, antialias=True)) != twin,
                            axis=2,
                        ).sum()
                    )
                    ctrl_rows.append((name, px, shifted, aa))
                    ctrl_shift_ok &= shifted > 0
                    ctrl_aa_ok &= aa > 0
    print()
    print(
        "sheets compared: %d, pixels compared: %d, mismatching pixels: %d"
        % (sheets, total_px, total_bad)
    )
    print(
        "advance check: %d distinct (line, weight, size) combinations, Qt advance "
        "differs from the source advance in %d" % (advance_checked, len(advance_bad))
    )
    for row in advance_bad[:10]:
        print("  ADVANCE MISMATCH", row)
    print("negative controls (Light sheets, the comparison must report mismatches):")
    for name, px, shifted, aa in ctrl_rows:
        print(
            "  %-9s %2dpx  text moved 1 px: %7d mismatching | antialiasing left on: "
            "%7d mismatching" % (name, px, shifted, aa)
        )
    print("CONTROLS %s" % ("OK" if (ctrl_shift_ok and ctrl_aa_ok) else "FAILED"))
    # provenance of the strings
    prov = {lang: contents[lang]["provenance"] for lang in contents}
    with open(
        os.path.join(args.out, "ui-strings-provenance.json"),
        "w",
        encoding="utf-8",
        newline="\n",
    ) as fh:
        json.dump(
            {lang: [list(t) for t in prov[lang]] for lang in prov},
            fh,
            indent=1,
            ensure_ascii=False,
            sort_keys=True,
        )
        fh.write("\n")
    m = {
        "qt": qVersion(),
        "pyside6": PySide6.__version__,
        "platform": app.platformName(),
        "family": family,
        "sizes": {},
    }
    for px in SIZES:
        for w in ("regular", "bold"):
            fm = QFontMetrics(make_font(w, px))
            m["sizes"].setdefault(str(px), {})[w] = {
                "ascent": fm.ascent(),
                "descent": fm.descent(),
                "height": fm.height(),
                "leading": fm.leading(),
                "lineSpacing": fm.lineSpacing(),
            }
    with open(
        os.path.join(args.out, "ttf-qt-metrics.json"),
        "w",
        encoding="utf-8",
        newline="\n",
    ) as fh:
        json.dump(m, fh, indent=1, sort_keys=True)
        fh.write("\n")
    ok = (
        total_bad == 0
        and not advance_bad
        and ctrl_shift_ok
        and ctrl_aa_ok
        and sheets > 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
