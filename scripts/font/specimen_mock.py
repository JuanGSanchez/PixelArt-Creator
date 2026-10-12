"""Interface-like specimen scenes for Nifen Art, built as a list of drawing ops.

A scene is a list of ops, in device pixels at a scale factor k (k = size / 12):

    ("fill", x, y, w, h, rgb)
    ("text", x, baseline_y, string, weight, rgb)

The same ops are painted twice: by Qt from the built fonts, and by a numpy
canvas straight from the glyph-grid sources. Layout decisions (widths for
centring, right alignment and wrapping) come from the source advances, so the
two paintings can be compared pixel for pixel.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np
from nifen_src import Font

RGB = Tuple[int, int, int]
Op = tuple


def rgb(c) -> RGB:
    return (int(c[0]), int(c[1]), int(c[2]))


class Scene:
    """Collects ops; geometry arguments are in design pixels (multiplied by k)."""

    def __init__(self, font: Font, k: int):
        self.font = font
        self.k = k
        self.ops: List[Op] = []

    # geometry in design pixels ------------------------------------------------
    def fill(self, x, y, w, h, color):
        k = self.k
        self.ops.append(("fill", x * k, y * k, w * k, h * k, rgb(color)))

    def frame(self, x, y, w, h, color, t=1):
        self.fill(x, y, w, t, color)
        self.fill(x, y + h - t, w, t, color)
        self.fill(x, y, t, h, color)
        self.fill(x + w - t, y, t, h, color)

    def text(self, x, top, s, weight, color):
        """Draw a line whose line box starts at design row `top` (ascent 11)."""
        k = self.k
        self.ops.append(("text", x * k, (top + 11) * k, s, weight, rgb(color)))

    # source-based measures, in design pixels -----------------------------------
    def width(self, s: str, weight: str) -> int:
        return sum(self.font.bmp(ord(ch), weight).adv for ch in s)

    def wrap(self, s: str, limit: int, weight: str) -> List[str]:
        words = s.split(" ")
        lines, cur = [], ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if cur and self.width(trial, weight) > limit:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        return lines

    def wrap_mixed(self, s: str, limit: int, weight: str) -> List[str]:
        """Wrap text that mixes Latin words with kana: a line may break after any
        full-width character (code point U+3000 and above) and at a space; a Latin
        word is never split."""
        tokens: List[str] = []
        word = ""
        for ch in s:
            if ord(ch) >= 0x3000:
                if word:
                    tokens.append(word)
                    word = ""
                tokens.append(ch)
            elif ch == " ":
                tokens.append(word + ch)
                word = ""
            else:
                word += ch
        if word:
            tokens.append(word)
        lines, cur = [], ""
        for t in tokens:
            if cur and self.width((cur + t).rstrip(" "), weight) > limit:
                lines.append(cur.rstrip(" "))
                cur = t
            else:
                cur += t
        if cur:
            lines.append(cur.rstrip(" "))
        return lines

    def wrap_chars(self, s: str, limit: int, weight: str) -> List[str]:
        lines, cur = [], ""
        for ch in s:
            if self.width(cur + ch, weight) > limit and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines


# --------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------


def scene_ui(font: Font, k: int, roles: Dict, content: Dict) -> Tuple[Scene, int, int]:
    """Menu bar with an open menu, two docks, a dialog and a status bar."""
    W, H = 520, 316
    sc = Scene(font, k)
    R = "regular"
    B = "bold"
    sc.fill(0, 0, W, H, roles["background"])
    # menu bar
    sc.fill(0, 0, W, 18, roles["surface"])
    sc.fill(0, 17, W, 1, roles["border"])
    x = 6
    spans = []
    for i, title in enumerate(content["menu_titles"]):
        w = sc.width(title, R)
        spans.append((x, w))
        if i == 0:
            sc.fill(x - 4, 1, w + 8, 16, roles["pressed"])
        sc.text(x, 2, title, R, roles["text"])
        x += w + 12
    # open menu under the first title
    items = content["file_menu"]
    keys = content["file_shortcuts"]
    inner = (
        max(sc.width(t, R) for t in items if t)
        + 18
        + max(sc.width(t, R) for t in keys if t)
    )
    pw = inner + 14
    ph = 4 + sum(16 if t else 5 for t in items) + 2
    sc.fill(2, 18, pw, ph, roles["surface"])
    sc.frame(2, 18, pw, ph, roles["frame_edge"])
    y = 20
    for idx, (t, kc) in enumerate(zip(items, keys)):
        if t is None:
            sc.fill(6, y + 2, pw - 8, 1, roles["border"])
            y += 5
            continue
        selected = idx == 1
        disabled = idx == 4
        if selected:
            sc.fill(4, y, pw - 4, 16, roles["accent"])
        col = (
            roles["accent_text"]
            if selected
            else (roles["disabled_text"] if disabled else roles["text"])
        )
        sc.text(8, y + 1, t, R, col)
        if kc:
            sc.text(2 + pw - 6 - sc.width(kc, R), y + 1, kc, R, col)
        y += 16
    # docks on the right
    dx, dw = 330, 184
    sc.fill(dx, 24, dw, 16, roles["title_fill"])
    sc.text(dx + 6, 25, content["dock_layers"], B, roles["title_text"])
    sc.fill(dx, 40, dw, 70, roles["surface"])
    sc.frame(dx, 24, dw, 86, roles["frame_edge"])
    ry = 44
    for i, t in enumerate(content["layer_rows"]):
        if i == 0:
            sc.fill(dx + 2, ry - 1, dw - 4, 16, roles["hover"])
        sc.text(dx + 8, ry, t, R, roles["text"] if i == 0 else roles["disabled_text"])
        ry += 18
    sc.text(dx + 8, ry, content["dock_timeline"], R, roles["text"])
    # palette dock
    sc.fill(dx, 118, dw, 16, roles["title_fill"])
    sc.text(dx + 6, 119, content["dock_palette"], B, roles["title_text"])
    sc.fill(dx, 134, dw, 40, roles["surface"])
    sc.frame(dx, 118, dw, 56, roles["frame_edge"])
    sw = [
        "accent",
        "focus",
        "frame_hi",
        "frame_mid",
        "frame_lo",
        "title_fill",
        "border",
        "canvas_checker_dark",
    ]
    for i, name in enumerate(sw):
        sc.fill(dx + 8 + i * 21, 142, 16, 16, roles[name])
        sc.frame(dx + 8 + i * 21, 142, 16, 16, roles["frame_edge"])
    # dialog
    gx, gy, gw, gh = 20, 118, 290, 124
    gy = 130
    sc.fill(gx, gy, gw, gh, roles["surface"])
    sc.fill(gx, gy, gw, 16, roles["title_fill"])
    sc.text(gx + 6, gy + 1, content["dialog_title"], B, roles["title_text"])
    sc.frame(gx, gy, gw, gh, roles["frame_edge"], 2)
    wrapper = sc.wrap_mixed if content.get("wrap") == "chars" else sc.wrap
    body = wrapper(content["dialog_body"], gw - 24, R)
    by = gy + 24
    for ln in body:
        sc.text(gx + 10, by, ln, R, roles["text"])
        by += 15
    by += 4
    sc.frame(gx + 10, by + 2, 10, 10, roles["border"])
    sc.fill(gx + 12, by + 4, 6, 6, roles["accent"])
    sc.text(gx + 26, by, content["dialog_check"], R, roles["text"])
    # buttons
    bw1 = sc.width(content["dialog_ok"], B) + 20
    bw2 = sc.width(content["dialog_cancel"], R) + 20
    byb = gy + gh - 26
    x2 = gx + gw - 10 - bw2
    x1 = x2 - 8 - bw1
    sc.fill(x1, byb, bw1, 18, roles["accent"])
    sc.frame(x1, byb, bw1, 18, roles["frame_edge"])
    sc.text(x1 + 10, byb + 2, content["dialog_ok"], B, roles["accent_text"])
    sc.fill(x2, byb, bw2, 18, roles["surface"])
    sc.frame(x2, byb, bw2, 18, roles["border"])
    sc.text(x2 + 10, byb + 2, content["dialog_cancel"], R, roles["text"])
    # focus ring on the default button (overlay ring, 2 px, in the focus role)
    sc.frame(x1 - 3, byb - 3, bw1 + 6, 24, roles["focus"], 2)
    # status bar
    sc.fill(0, H - 18, W, 18, roles["surface"])
    sc.fill(0, H - 18, W, 1, roles["border"])
    sc.text(6, H - 16, content["status_left"], R, roles["disabled_text"])
    sr = content["status_right"]
    sc.text(W - 6 - sc.width(sr, R), H - 16, sr, R, roles["text"])
    return sc, W, H


def scene_text(
    font: Font,
    k: int,
    roles: Dict,
    content: Dict,
    other: Dict,
    specimen: str,
    mixed: Sequence[str],
) -> Tuple[Scene, int, int]:
    """Paragraphs: long sentences in Regular and Bold, a specimen line, scripts."""
    W = 520
    sc = Scene(font, k)
    R, B = "regular", "bold"
    lim = W - 24
    blocks = []  # (weight, text)
    for key in ("recovery_body", "unsaved_body", "asset_body"):
        blocks.append((R, content[key]))
    blocks.append((B, content["recovery_body"]))
    blocks.append((R, specimen))
    blocks.append((B, specimen))
    for key in ("recovery_body",):
        blocks.append((R, other[key]))
    heights = []
    lines_all = []
    for weight, txt in blocks:
        ls = sc.wrap(txt, lim, weight)
        lines_all.append((weight, ls))
        heights.append(len(ls) * 15 + 8)
    mixed_h = len(mixed) * 2 * 16 + 8
    H = 10 + sum(heights) + mixed_h + 10
    sc.fill(0, 0, W, H, roles["surface"])
    y = 10
    for weight, ls in lines_all:
        for ln in ls:
            sc.text(12, y, ln, weight, roles["text"])
            y += 15
        y += 8
    sc.fill(12, y - 4, W - 24, 1, roles["border"])
    for ln in mixed:
        sc.text(12, y, ln, R, roles["text"])
        y += 16
        sc.text(12, y, ln, B, roles["text"])
        y += 16
    return sc, W, H


def scene_alphabet(
    font: Font, k: int, roles: Dict, lines: Sequence[str]
) -> Tuple[Scene, int, int]:
    """The character set, each line in Regular and then Bold."""
    W = 520
    sc = Scene(font, k)
    R, B = "regular", "bold"
    rows = []
    for ln in lines:
        for weight in (R, B):
            parts = sc.wrap_chars(ln, W - 24, B)
            rows.append((weight, parts))
    H = 10 + sum(len(p) * 15 for _w, p in rows) + len(lines) * 8 + 10
    sc.fill(0, 0, W, H, roles["surface"])
    y = 10
    for i, (weight, parts) in enumerate(rows):
        for ln in parts:
            sc.text(12, y, ln, weight, roles["text"])
            y += 15
        if weight == B:
            y += 8
    return sc, W, H


def scene_kana_table(
    font: Font,
    k: int,
    roles: Dict,
    tables: Sequence[Tuple[str, Sequence[str]]],
    rows: Sequence[str],
) -> Tuple[Scene, int, int]:
    """Kana tables (cells, Regular left and Bold right) and extra small-kana rows."""
    W = 520
    sc = Scene(font, k)
    R, B = "regular", "bold"
    pad_after = 10
    heights = 0
    for _label, tab in tables:
        heights += 15 + len(tab) * 16 + pad_after
    heights += 15 + len(rows) * 2 * 16 + pad_after
    H = 10 + heights + 10
    sc.fill(0, 0, W, H, roles["surface"])
    y = 10
    for label, tab in tables:
        sc.text(12, y, label, B, roles["accent"])
        y += 15
        for row in tab:
            x_reg, x_bold = 12, 12 + 12 * 11 + 6 * 11 + 14
            for ci, ch in enumerate(row):
                gx = ci * (12 + 6)
                if ch != chr(0x3000):
                    sc.text(x_reg + gx, y, ch, R, roles["text"])
                    sc.text(x_bold + gx, y, ch, B, roles["text"])
            y += 16
        y += pad_after
    sc.text(
        12,
        y,
        "Small kana, rare forms, marks, punctuation: Regular above Bold",
        B,
        roles["accent"],
    )
    y += 15
    for row in rows:
        for weight in (R, B):
            x = 12
            for ch in row:
                sc.text(x, y, ch, weight, roles["text"])
                x += 12 + 6
            y += 16
    return sc, W, H


def scene_euro(
    font: Font, k: int, roles: Dict, lines: Sequence[Tuple[str, str]]
) -> Tuple[Scene, int, int]:
    """Sample lines in languages written with Latin Extended-A: label, Regular, Bold."""
    W = 520
    sc = Scene(font, k)
    R, B = "regular", "bold"
    lim = W - 24
    blocks = []
    for label, text in lines:
        wrap = sc.wrap_mixed if any(ord(ch) >= 0x3000 for ch in text) else sc.wrap
        blocks.append((label, wrap(text, lim, R), wrap(text, lim, B)))
    H = 10 + sum(15 + (len(a) + len(b)) * 15 + 8 for _l, a, b in blocks) + 10
    sc.fill(0, 0, W, H, roles["surface"])
    y = 10
    for label, reg, bold in blocks:
        sc.text(12, y, label, B, roles["accent"])
        y += 15
        for ln in reg:
            sc.text(12, y, ln, R, roles["text"])
            y += 15
        for ln in bold:
            sc.text(12, y, ln, B, roles["text"])
            y += 15
        y += 8
    return sc, W, H


def scene_symbols(
    font: Font, k: int, roles: Dict, lines: Sequence[str], context: Sequence[str]
) -> Tuple[Scene, int, int]:
    """Symbol families (Regular, Bold) and in-context lines on an interface surface."""
    W = 520
    sc = Scene(font, k)
    R, B = "regular", "bold"
    rows = []
    for ln in lines:
        for weight in (R, B):
            rows.append((weight, sc.wrap_chars(ln, W - 24, B)))
    H = (
        10
        + sum(len(p) * 15 for _w, p in rows)
        + len(lines) * 8
        + 14
        + len(context) * 2 * 18
        + 10
    )
    sc.fill(0, 0, W, H, roles["surface"])
    y = 10
    for weight, parts in rows:
        for ln in parts:
            sc.text(12, y, ln, weight, roles["text"])
            y += 15
        if weight == B:
            y += 8
    sc.fill(12, y - 4, W - 24, 1, roles["border"])
    y += 6
    for ln in context:
        sc.fill(8, y - 2, W - 16, 17, roles["hover"])
        sc.text(12, y, ln, R, roles["text"])
        y += 18
        sc.text(12, y, ln, B, roles["text"])
        y += 18
    return sc, W, H


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------


def paint_grid(scene: Scene, W: int, H: int) -> np.ndarray:
    """Paint the ops from the glyph sources; returns an (H*k, W*k, 3) uint8 array."""
    k = scene.k
    img = np.zeros((H * k, W * k, 3), dtype=np.uint8)
    for op in scene.ops:
        if op[0] == "fill":
            _t, x, y, w, h, col = op
            img[y : y + h, x : x + w] = col
        else:
            _t, x, base, s, weight, col = op
            pen = 0
            for ch in s:
                b = scene.font.bmp(ord(ch), weight)
                for gx, gy in b.px:
                    px_x = x + (pen + gx) * k
                    px_y = base - (gy + 1) * k
                    img[px_y : px_y + k, px_x : px_x + k] = col
                pen += b.adv
    return img
