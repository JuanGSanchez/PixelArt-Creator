"""Nifen Art glyph-source library.

Parses the text-grid sources, resolves every codepoint to a bitmap in either
weight (drawn, aliased or composed by recipe, with the Bold rule and hand
overlays), and converts bitmaps to rectilinear outlines.

Pure Python 3, standard library only. The font build (fontTools) lives in
build_nifen_art.py; nothing here imports it.

Coordinate convention: a pixel is (x, y) with y counted upward from the
baseline; pixel (x, y) covers the square [x, x+1) x [y, y+1).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

Pixel = Tuple[int, int]
PixelSet = FrozenSet[Pixel]

ROW_RE = re.compile(r"^[#.]+$")
CP_RE = re.compile(r"^U\+([0-9A-Fa-f]{4,6})$")


class SourceError(Exception):
    """Raised when a source file cannot be parsed or resolved."""


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------


@dataclass
class Record:
    """One parsed source record (glyph, mark, bold overlay, ...)."""

    kind: str
    key: object  # int codepoint, or str (glyph name / mark name)
    attrs: Dict[str, str]
    rows: List[str]
    path: str
    line: int

    def attr_int(self, name: str, default: Optional[int] = None) -> int:
        if name in self.attrs:
            return int(self.attrs[name])
        if default is None:
            raise SourceError(f"{self.path}:{self.line}: missing {name}=")
        return default

    def has_flag(self, name: str) -> bool:
        return name in self.attrs

    def pixels(self) -> PixelSet:
        top = self.attr_int("top")
        xoff = self.attr_int("x", 0)
        out: Set[Pixel] = set()
        for i, row in enumerate(self.rows):
            y = top - 1 - i
            for j, ch in enumerate(row):
                if ch == "#":
                    out.add((j + xoff, y))
        return frozenset(out)

    def grid_width(self) -> int:
        return max((len(r) for r in self.rows), default=0) + self.attr_int("x", 0)


@dataclass
class Alias:
    target_cp: int
    source_cp: int
    path: str
    line: int


@dataclass
class Recipe:
    target_cp: int
    op: str
    args: List[str]
    opts: Dict[str, str]
    path: str
    line: int


@dataclass
class Sources:
    metrics: Dict[str, str] = field(default_factory=dict)
    glyphs: Dict[object, Record] = field(default_factory=dict)
    marks: Dict[str, Record] = field(default_factory=dict)
    bold_glyphs: Dict[object, Record] = field(default_factory=dict)
    bold_marks: Dict[str, Record] = field(default_factory=dict)
    aliases: List[Alias] = field(default_factory=list)
    recipes: List[Recipe] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


def parse_cp(token: str, where: str = "") -> int:
    m = CP_RE.match(token)
    if not m:
        raise SourceError(f"{where}: bad codepoint {token!r}")
    return int(m.group(1), 16)


def _strip_comment(line: str) -> str:
    idx = line.find(" #")
    if idx >= 0:
        line = line[:idx]
    return line.strip()


def _parse_attrs(tokens: List[str], where: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for tok in tokens:
        if "=" in tok:
            k, v = tok.split("=", 1)
            attrs[k] = v
        else:
            attrs[tok] = "1"
    return attrs


def parse_metrics(path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SourceError(f"{path}:{n}: expected key = value")
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_sources(src_dir: str) -> Sources:
    """Parse metrics.txt and every other *.txt file in src_dir (sorted)."""
    srcs = Sources()
    srcs.metrics = parse_metrics(os.path.join(src_dir, "metrics.txt"))
    names = sorted(
        n for n in os.listdir(src_dir) if n.endswith(".txt") and n != "metrics.txt"
    )
    for name in names:
        path = os.path.join(src_dir, name)
        srcs.files.append(name)
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
        _parse_file(text, name, srcs)
    return srcs


def _flush(cur: Optional[Record], srcs: Sources) -> None:
    if cur is None:
        return
    bucket: Dict
    if cur.kind == "glyph":
        bucket = srcs.glyphs
    elif cur.kind == "mark":
        bucket = srcs.marks
    elif cur.kind == "bold":
        bucket = srcs.bold_glyphs
    elif cur.kind == "boldmark":
        bucket = srcs.bold_marks
    else:
        raise SourceError(f"{cur.path}:{cur.line}: unknown record kind {cur.kind}")
    if cur.key in bucket:
        srcs.duplicates.append(
            f"{cur.path}:{cur.line}: duplicate {cur.kind} {cur.key!r}"
        )
        return
    bucket[cur.key] = cur


def _parse_file(text: str, name: str, srcs: Sources) -> None:
    cur: Optional[Record] = None
    for n, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r")
        if cur is not None and ROW_RE.match(line):
            cur.rows.append(line)
            continue
        if not line.strip():
            _flush(cur, srcs)
            cur = None
            continue
        if line.startswith("# ") or line.strip() == "#":
            continue
        body = _strip_comment(line)
        toks = body.split()
        head = toks[0]
        if head in ("glyph", "bold"):
            _flush(cur, srcs)
            key: object = toks[1]
            if toks[1].startswith("U+"):
                key = parse_cp(toks[1], f"{name}:{n}")
            cur = Record(head, key, _parse_attrs(toks[2:], f"{name}:{n}"), [], name, n)
        elif head in ("mark", "boldmark"):
            _flush(cur, srcs)
            cur = Record(
                head, toks[1], _parse_attrs(toks[2:], f"{name}:{n}"), [], name, n
            )
        elif head == "alias":
            _flush(cur, srcs)
            cur = None
            if len(toks) != 4 or toks[2] != "=":
                raise SourceError(f"{name}:{n}: alias syntax is 'alias U+X = U+Y'")
            srcs.aliases.append(
                Alias(
                    parse_cp(toks[1], f"{name}:{n}"),
                    parse_cp(toks[3], f"{name}:{n}"),
                    name,
                    n,
                )
            )
        elif head == "recipe":
            _flush(cur, srcs)
            cur = None
            if len(toks) < 5 or toks[2] != "=":
                raise SourceError(
                    f"{name}:{n}: recipe syntax is 'recipe U+X = op args'"
                )
            op = toks[3]
            args = [t for t in toks[4:] if "=" not in t]
            opts = {
                t.split("=", 1)[0]: t.split("=", 1)[1] for t in toks[4:] if "=" in t
            }
            srcs.recipes.append(
                Recipe(parse_cp(toks[1], f"{name}:{n}"), op, args, opts, name, n)
            )
        else:
            raise SourceError(f"{name}:{n}: unrecognised line {line!r}")
    _flush(cur, srcs)


# --------------------------------------------------------------------------
# Bitmaps
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Bmp:
    px: PixelSet
    adv: int
    width: int  # grid width in columns


def shift(px: Iterable[Pixel], dx: int, dy: int) -> PixelSet:
    return frozenset((x + dx, y + dy) for x, y in px)


def embolden(px: PixelSet, by: int = 1) -> PixelSet:
    out: Set[Pixel] = set(px)
    for k in range(1, by + 1):
        out |= {(x + k, y) for x, y in px}
    return frozenset(out)


def bbox(px: PixelSet) -> Optional[Tuple[int, int, int, int]]:
    """(xmin, ymin, xmax, ymax) over lit pixels, or None when empty."""
    if not px:
        return None
    xs = [p[0] for p in px]
    ys = [p[1] for p in px]
    return min(xs), min(ys), max(xs), max(ys)


def anchor_col(px: PixelSet) -> int:
    b = bbox(px)
    if b is None:
        raise SourceError("cannot anchor an empty glyph")
    return (b[0] + b[2]) // 2


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

WEIGHTS = ("regular", "bold")


class Font:
    """All codepoints of the sources, resolved on demand in either weight."""

    def __init__(self, srcs: Sources):
        self.srcs = srcs
        self.alias_by_cp: Dict[int, Alias] = {}
        for a in srcs.aliases:
            self.alias_by_cp.setdefault(a.target_cp, a)
        self.recipe_by_cp: Dict[int, Recipe] = {}
        for r in srcs.recipes:
            self.recipe_by_cp.setdefault(r.target_cp, r)
        self._cache: Dict[Tuple[int, str], Bmp] = {}

    # classification ---------------------------------------------------------
    def codepoints(self) -> List[int]:
        cps: Set[int] = set(k for k in self.srcs.glyphs if isinstance(k, int))
        cps |= set(self.alias_by_cp)
        cps |= set(self.recipe_by_cp)
        return sorted(cps)

    def classify(self, cp: int) -> str:
        """drawn / override / aliased / composed."""
        drawn = cp in self.srcs.glyphs
        recipe = cp in self.recipe_by_cp
        alias = cp in self.alias_by_cp
        if drawn and recipe:
            return "override"
        if drawn:
            return "drawn"
        if alias:
            return "aliased"
        if recipe:
            return "composed"
        raise SourceError(f"U+{cp:04X} is not defined")

    # glyphs -----------------------------------------------------------------
    def bmp(self, cp: object, weight: str, _stack: Tuple = ()) -> Bmp:
        if cp in _stack:
            raise SourceError(f"recursive definition at {cp!r}")
        key = (cp, weight)
        if key in self._cache:
            return self._cache[key]
        stack = _stack + (cp,)
        s = self.srcs
        if weight == "bold" and cp in s.bold_glyphs:
            rec = s.bold_glyphs[cp]
            res = Bmp(rec.pixels(), rec.attr_int("adv"), rec.grid_width())
        elif cp in s.glyphs:
            rec = s.glyphs[cp]
            px = rec.pixels()
            adv = rec.attr_int("adv")
            if weight == "bold":
                full = rec.has_flag("cell")
                px = embolden(px, int(s.metrics.get("bold_shift_px", "1")))
                adv = adv if full else adv + int(s.metrics.get("bold_shift_px", "1"))
                res = Bmp(px, adv, rec.grid_width() + (0 if full else 1))
            else:
                res = Bmp(px, adv, rec.grid_width())
        elif cp in self.alias_by_cp:
            a = self.alias_by_cp[cp]
            res = self.bmp(a.source_cp, weight, stack)
        elif cp in self.recipe_by_cp:
            res = self._recipe(self.recipe_by_cp[cp], weight, stack)
        else:
            raise SourceError(f"U+{cp:04X} has no drawing, alias or recipe")
        self._cache[key] = res
        return res

    def mark_bmp(self, name: str, weight: str) -> Tuple[PixelSet, int, int]:
        """(pixels, attach column, grid width) of a mark in a weight."""
        s = self.srcs
        if name not in s.marks:
            raise SourceError(f"unknown mark {name!r}")
        if weight == "bold" and name in s.bold_marks:
            rec = s.bold_marks[name]
            return rec.pixels(), rec.attr_int("attach"), rec.grid_width()
        rec = s.marks[name]
        px = rec.pixels()
        attach = rec.attr_int("attach", 0)
        width = rec.grid_width()
        if weight == "bold":
            px = embolden(px, int(s.metrics.get("bold_shift_px", "1")))
            width += 1
        return px, attach, width

    @staticmethod
    def _mark_dx(base_px: PixelSet, mark_px: PixelSet, attach: int, r: Recipe) -> int:
        """Horizontal offset of a mark: on the anchor column, or flush to one side."""
        if r.opts.get("align") == "left":
            return bbox(base_px)[0] - min(p[0] for p in mark_px)
        if r.opts.get("align") == "right":
            return bbox(base_px)[2] - max(p[0] for p in mark_px)
        return anchor_col(base_px) - attach + int(r.opts.get("dx", "0"))

    @staticmethod
    def trimmed(
        base_px: PixelSet, other_px: PixelSet, r: Recipe, weight: str = "regular"
    ) -> PixelSet:
        """The base of an overlay with trim=N: every base pixel within N pixels of
        the other part is dropped.

        The clearance is measured from the mark as it is drawn in Bold (its widest
        form) in both weights, so the cut leaves the same shape of base in Regular
        and in Bold.

        What the cut leaves behind is tidied by rule: in Bold a pixel left without
        a horizontal neighbour (a stroke narrower than two pixels) is dropped, in
        either weight a pixel left on its own that was not a lone pixel of the base
        is dropped. The lint checks that the part count of the base survives.
        """
        n = int(r.opts.get("trim", "0"))
        if n <= 0:
            return base_px
        halo = {
            (x + dx, y + dy)
            for (x, y) in other_px
            for dx in range(-n, n + 1)
            for dy in range(-n, n + 1)
        }
        keep = {p for p in base_px if p not in halo}
        lone0 = {
            p
            for p in base_px
            if not any((p[0] + dx, p[1] + dy) in base_px for dx, dy in N8)
        }
        changed = True
        while changed:
            changed = False
            for p in sorted(keep):
                x, y = p
                if (
                    weight == "bold"
                    and (x - 1, y) not in keep
                    and (x + 1, y) not in keep
                ):
                    keep.discard(p)
                    changed = True
                elif p not in lone0 and not any(
                    (x + dx, y + dy) in keep for dx, dy in N8
                ):
                    keep.discard(p)
                    changed = True
        return frozenset(keep)

    def _recipe(self, r: Recipe, weight: str, stack: Tuple) -> Bmp:
        where = f"{r.path}:{r.line}"
        if r.op == "mark":
            base = self.bmp(parse_cp(r.args[0], where), weight, stack)
            mpx, attach, _w = self.mark_bmp(r.args[1], weight)
            mk = shift(
                mpx,
                self._mark_dx(base.px, mpx, attach, r),
                int(r.opts.get("rise", "0")),
            )
            minx = min(p[0] for p in mk)
            bshift = max(0, -minx)
            px = shift(base.px, bshift, 0) | shift(mk, bshift, 0)
            right = max(p[0] for p in mk) + bshift
            adv = max(base.adv + bshift, right + 2)
            return Bmp(frozenset(px), adv, adv)
        if r.op == "rot180":
            base = self.bmp(parse_cp(r.args[0], where), weight, stack)
            lo, hi = (int(v) for v in r.opts["rows"].split(".."))
            b = bbox(base.px)
            if b is None or b[1] < lo or b[3] > hi:
                raise SourceError(f"{where}: ink outside rows {lo}..{hi}")
            sx = b[0] + b[2]
            px = frozenset((sx - x, lo + hi - y) for x, y in base.px)
            return Bmp(px, base.adv, base.width)
        if r.op == "cat":
            a = self.bmp(parse_cp(r.args[0], where), weight, stack)
            b2 = self.bmp(parse_cp(r.args[1], where), weight, stack)
            ra = self.bmp(parse_cp(r.args[0], where), "regular", stack)
            rb = self.bmp(parse_cp(r.args[1], where), "regular", stack)
            offset = ra.adv + int(r.opts.get("gap", "0"))
            extra = (
                int(self.srcs.metrics.get("bold_shift_px", "1"))
                if weight == "bold"
                else 0
            )
            px = a.px | shift(b2.px, offset, 0)
            adv = offset + rb.adv + extra
            return Bmp(frozenset(px), adv, adv)
        if r.op == "overlay":
            a = self.bmp(parse_cp(r.args[0], where), weight, stack)
            b2 = self.bmp(parse_cp(r.args[1], where), weight, stack)
            halo_src = (
                self.bmp(parse_cp(r.args[1], where), "bold", stack).px
                if "trim" in r.opts
                else b2.px
            )
            return Bmp(
                frozenset(self.trimmed(a.px, halo_src, r, weight) | b2.px),
                a.adv,
                max(a.width, b2.width),
            )
        raise SourceError(f"{where}: unknown recipe op {r.op!r}")

    # components for the lint ----------------------------------------------------
    def recipe_components(self, r: Recipe, weight: str) -> List[PixelSet]:
        """Pixel sets of the parts a recipe combined, placed as in the result."""
        where = f"{r.path}:{r.line}"
        if r.op == "mark":
            base = self.bmp(parse_cp(r.args[0], where), weight)
            mpx, attach, _w = self.mark_bmp(r.args[1], weight)
            mk = shift(
                mpx,
                self._mark_dx(base.px, mpx, attach, r),
                int(r.opts.get("rise", "0")),
            )
            bshift = max(0, -min(p[0] for p in mk))
            return [shift(base.px, bshift, 0), shift(mk, bshift, 0)]
        if r.op == "overlay":
            a = self.bmp(parse_cp(r.args[0], where), weight).px
            o = self.bmp(parse_cp(r.args[1], where), weight).px
            halo_src = (
                self.bmp(parse_cp(r.args[1], where), "bold").px
                if "trim" in r.opts
                else o
            )
            return [self.trimmed(a, halo_src, r, weight), o]
        return []


# --------------------------------------------------------------------------
# Connectivity helpers (shared by the lint and the specimen code)
# --------------------------------------------------------------------------

N8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
N4 = [(0, -1), (-1, 0), (1, 0), (0, 1)]


def components(px: PixelSet, eight: bool = True) -> List[PixelSet]:
    seen: Set[Pixel] = set()
    out: List[PixelSet] = []
    nb = N8 if eight else N4
    for p in sorted(px):
        if p in seen:
            continue
        stack = [p]
        comp: Set[Pixel] = set()
        seen.add(p)
        while stack:
            q = stack.pop()
            comp.add(q)
            for dx, dy in nb:
                r = (q[0] + dx, q[1] + dy)
                if r in px and r not in seen:
                    seen.add(r)
                    stack.append(r)
        out.append(frozenset(comp))
    return out


def counter_regions(px: PixelSet) -> List[FrozenSet[Pixel]]:
    """Enclosed background regions (4-connected), outside excluded, as cell sets."""
    b = bbox(px)
    if b is None:
        return []
    x0, y0, x1, y1 = b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1
    empty = {
        (x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if (x, y) not in px
    }
    seen: Set[Pixel] = set()
    regions: List[FrozenSet[Pixel]] = []
    for p in sorted(empty):
        if p in seen:
            continue
        stack = [p]
        seen.add(p)
        cells: Set[Pixel] = set()
        touches_border = False
        while stack:
            q = stack.pop()
            cells.add(q)
            if q[0] in (x0, x1) or q[1] in (y0, y1):
                touches_border = True
            for dx, dy in N4:
                r = (q[0] + dx, q[1] + dy)
                if r in empty and r not in seen:
                    seen.add(r)
                    stack.append(r)
        if not touches_border:
            regions.append(frozenset(cells))
    return regions


def counters(px: PixelSet) -> int:
    """Number of enclosed background regions (4-connected), outside excluded."""
    return len(counter_regions(px))


def lost_counters(regular: PixelSet, bold: PixelSet) -> int:
    """Regular counters that have no empty, still-enclosed cell left in the Bold bitmap.

    Counting counters can agree by coincidence while an eye has filled in and a
    different gap has closed elsewhere; this compares the regions themselves.
    The two bitmaps must share coordinates (a plain derivation of the Regular).
    """
    enclosed: Set[Pixel] = set()
    for reg in counter_regions(bold):
        enclosed |= reg
    return sum(1 for reg in counter_regions(regular) if not (reg & enclosed))


# --------------------------------------------------------------------------
# Outlines
# --------------------------------------------------------------------------

Point = Tuple[int, int]


def contours(px: PixelSet) -> List[List[Point]]:
    """Rectilinear contours of a pixel set, outer loops clockwise (y up).

    Pixels that touch only at a corner stay separate loops. Collinear
    vertices are removed. Start vertex of each loop is its lowest-leftmost
    corner and loops are ordered by that vertex, so output is deterministic.
    """
    out_edges: Dict[Point, List[Point]] = {}

    def add(a: Point, b: Point) -> None:
        out_edges.setdefault(a, []).append(b)

    for x, y in sorted(px):
        if (x, y + 1) not in px:
            add((x, y + 1), (x + 1, y + 1))
        if (x + 1, y) not in px:
            add((x + 1, y + 1), (x + 1, y))
        if (x, y - 1) not in px:
            add((x + 1, y), (x, y))
        if (x - 1, y) not in px:
            add((x, y), (x, y + 1))

    used: Set[Tuple[Point, Point]] = set()
    loops: List[List[Point]] = []
    for start in sorted(out_edges):
        for end in sorted(out_edges[start]):
            if (start, end) in used:
                continue
            first = (start, end)
            loop = [start]
            used.add(first)
            a, b = first
            while True:
                loop.append(b)
                d = (b[0] - a[0], b[1] - a[1])
                allout = sorted(out_edges[b])
                right = (d[1], -d[0])
                pick = None
                for e in allout:
                    if (e[0] - b[0], e[1] - b[1]) == right:
                        pick = e
                if pick is None:
                    pick = allout[0]
                if (b, pick) == first:
                    break
                used.add((b, pick))
                a, b = b, pick
            if loop[-1] == loop[0]:
                loop.pop()
            loops.append(_simplify(loop))
    loops = [lp for lp in loops if len(lp) >= 4]
    loops = [_rotate(lp) for lp in loops]
    loops.sort(key=lambda lp: (lp[0][1], lp[0][0]))
    return loops


def _simplify(loop: List[Point]) -> List[Point]:
    n = len(loop)
    out = []
    for i in range(n):
        p, c, q = loop[i - 1], loop[i], loop[(i + 1) % n]
        if (c[0] - p[0], c[1] - p[1]) == (q[0] - c[0], q[1] - c[1]):
            continue
        if (c[0] - p[0]) * (q[1] - c[1]) - (c[1] - p[1]) * (q[0] - c[0]) == 0:
            continue
        out.append(c)
    return out


def _rotate(loop: List[Point]) -> List[Point]:
    i = min(range(len(loop)), key=lambda k: (loop[k][1], loop[k][0]))
    return loop[i:] + loop[:i]


def fill_from_contours(loops: List[List[Point]]) -> PixelSet:
    """Even-odd re-rasterisation of contours (used to prove the outline)."""
    if not loops:
        return frozenset()
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    out: Set[Pixel] = set()
    for y in range(min(ys), max(ys)):
        for x in range(min(xs), max(xs)):
            cx, cy = x + 0.5, y + 0.5
            wn = 0
            for lp in loops:
                n = len(lp)
                for i in range(n):
                    a, b = lp[i], lp[(i + 1) % n]
                    if a[0] == b[0] and a[0] > cx:
                        lo, hi = sorted((a[1], b[1]))
                        if lo <= cy < hi:
                            wn += 1 if b[1] < a[1] else -1
            if wn != 0:
                out.add((x, y))
    return frozenset(out)


# --------------------------------------------------------------------------
# Text layout (pixel truth, no kerning)
# --------------------------------------------------------------------------


def layout(font: Font, text: str, weight: str) -> Tuple[PixelSet, int]:
    """Pixels of a line of text with the baseline at y=0, pen starting at x=0."""
    px: Set[Pixel] = set()
    pen = 0
    for ch in text:
        b = font.bmp(ord(ch), weight)
        px |= {(x + pen, y) for x, y in b.px}
        pen += b.adv
    return frozenset(px), pen
