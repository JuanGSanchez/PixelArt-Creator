#!/usr/bin/env python
# =============================================================================
# SCRIPT (importable library): maxrects_compactor
#   pixelart_creator/logic/compactor.py  — PixelArt Creator system
# =============================================================================
# PURPOSE: Deterministic MaxRects bin-packing of sprite rectangles into a single
#   atlas, rotation disabled (FIX-13, F8). Pure-Python, zero Qt (logic/ layer,
#   S11). Importable library: callers use the return value, not a process exit.
# FLAVOUR: standalone (importable library; not a CLI)
# LOCATION: pixelart_creator/logic/compactor.py
# INVOKED BY: AGT-03 (logic; primary owner) and AGT-05 (ui) via import
#   `from pixelart_creator.logic.compactor import compact, CompactionError`.
# RUNTIME: Python 3.8+ (CPython, stdlib only). No Qt, no NumPy required.
# ENTRYPOINT (library): compact(rects, max_width, max_height) -> Packing
#   Optional CLI for smoke test: python -m pixelart_creator.logic.compactor
# INPUTS:
#   rects: list[Rect] or list of (id, w, h); non-negative int dimensions.
#   max_width, max_height: atlas bounds — REQUIRED explicit positive-int args.
#     This module imports no constants; callers pass the bounds they want (e.g.
#     MAX_CANVAS_WIDTH/HEIGHT from logic.constants) explicitly.
# OUTPUTS:
#   Return value: Packing(placements=[Placement(id,x,y,w,h)], width, height).
#   Raises CompactionError on invalid input or when a rect cannot fit.
# EXIT / ERROR MAPPING (for a caller translating to agent exit status):
#   normal return -> COMPLETED ; CompactionError(reason="does-not-fit") ->
#   PARTIAL/BLOCKED (caller decides) ; CompactionError(reason="invalid-input")
#   -> FAILED. The `-m` smoke test exits 0 ok / 1 CompactionError / 2 bad args.
# PRECONDITIONS: every rect fits within (max_width, max_height) individually.
# DETERMINISM NOTE: fully deterministic — inputs are sorted by (area desc, id)
#   before placement; Best-Short-Side-Fit heuristic with a fixed tie-break;
#   no time/random/network. Identical input -> identical Packing.
#
# ## Principles Applied
# Inherited: P1 (grounded F8/FIX-13 MaxRects, rotation=False), P2 (deterministic
#   ordering + tie-breaks), P3 (documented procedure), P4, P6 (stdlib only),
#   P7, P9 (one job: rectangle packing), P10 (error->status mapping documented),
#   P11 (deterministic library vehicle), P12 (fit + free-rect split + prune),
#   P13.
# Custom: (none)
#
# SOURCES: Dossier §2 F8 (MaxRects), §9 C-none, §6.5/§8 (owner AGT-03/05);
#   Jukka Jylanki, "A Thousand Ways to Pack the Bin" (MaxRects BSSF, standard);
#   User req S11 (pure logic, zero Qt).
# =============================================================================
"""Deterministic MaxRects (BSSF, rotation=False) sprite compaction library."""

from __future__ import annotations

import sys
from typing import Iterable, List, NamedTuple, Sequence, Tuple, Union


class CompactionError(ValueError):
    """Raised when packing cannot proceed. `reason` is a stable machine token."""

    def __init__(self, message: str, reason: str = "invalid-input"):
        """Store `reason`, the stable machine token, alongside the ValueError text."""
        super().__init__(message)
        self.reason = reason


class Rect(NamedTuple):
    """An input sprite rectangle: a stable `id` plus its width/height in pixels."""

    id: str
    w: int
    h: int


class Placement(NamedTuple):
    """A packed `Rect`'s position and size within the atlas."""

    id: str
    x: int
    y: int
    w: int
    h: int


class Packing(NamedTuple):
    """The compaction result: every `Placement` plus the atlas `width`/`height`."""

    placements: List[Placement]
    width: int
    height: int


class _Free(NamedTuple):
    x: int
    y: int
    w: int
    h: int


InputRect = Union[Rect, Tuple[str, int, int]]


def _coerce(rects: Iterable[InputRect]) -> List[Rect]:
    out: List[Rect] = []
    for i, r in enumerate(rects):
        if isinstance(r, Rect):
            rid, w, h = r.id, r.w, r.h
        else:
            try:
                rid, w, h = r
            except (ValueError, TypeError):
                raise CompactionError("rect %d is not (id, w, h)" % i, "invalid-input")
        if not isinstance(w, int) or not isinstance(h, int) or w < 0 or h < 0:
            raise CompactionError(
                "rect %r has non-int/negative size" % (rid,), "invalid-input"
            )
        out.append(Rect(str(rid), w, h))
    return out


def _split_free(free: _Free, p: Placement) -> List[_Free]:
    # Guillotine-free MaxRects split: return sub-rects of `free` not covered by p.
    if (
        p.x >= free.x + free.w
        or p.x + p.w <= free.x
        or p.y >= free.y + free.h
        or p.y + p.h <= free.y
    ):
        return [free]  # no overlap
    out: List[_Free] = []
    if p.x > free.x:
        out.append(_Free(free.x, free.y, p.x - free.x, free.h))
    if p.x + p.w < free.x + free.w:
        out.append(_Free(p.x + p.w, free.y, free.x + free.w - (p.x + p.w), free.h))
    if p.y > free.y:
        out.append(_Free(free.x, free.y, free.w, p.y - free.y))
    if p.y + p.h < free.y + free.h:
        out.append(_Free(free.x, p.y + p.h, free.w, free.y + free.h - (p.y + p.h)))
    return out


def _contained(a: _Free, b: _Free) -> bool:
    return (
        a.x >= b.x and a.y >= b.y and a.x + a.w <= b.x + b.w and a.y + a.h <= b.y + b.h
    )


def _prune(frees: List[_Free]) -> List[_Free]:
    kept: List[_Free] = []
    for i, a in enumerate(frees):
        if a.w <= 0 or a.h <= 0:
            continue
        if any(
            j != i and _contained(a, b) and (a != b or j < i)
            for j, b in enumerate(frees)
            if b.w > 0 and b.h > 0
        ):
            continue
        kept.append(a)
    # Deterministic ordering.
    return sorted(set(kept))


def compact(rects: Sequence[InputRect], max_width: int, max_height: int) -> Packing:
    """Pack `rects` into a (max_width x max_height) atlas. Deterministic."""
    if (
        not isinstance(max_width, int)
        or not isinstance(max_height, int)
        or max_width <= 0
        or max_height <= 0
    ):
        raise CompactionError("atlas bounds must be positive ints", "invalid-input")
    items = _coerce(rects)
    for r in items:
        if r.w > max_width or r.h > max_height:
            raise CompactionError(
                "rect %r exceeds atlas bounds" % (r.id,), "does-not-fit"
            )
    # Sort: largest area first, id tie-break -> stable, deterministic.
    order = sorted(items, key=lambda r: (-(r.w * r.h), r.id))
    frees: List[_Free] = [_Free(0, 0, max_width, max_height)]
    placements: List[Placement] = []
    used_w = used_h = 0
    for r in order:
        best = None  # (short_side, long_side, y, x, free_index)
        for idx, f in enumerate(frees):
            if f.w >= r.w and f.h >= r.h:
                leftover_h = f.h - r.h
                leftover_w = f.w - r.w
                short = min(leftover_w, leftover_h)
                long_ = max(leftover_w, leftover_h)
                cand = (short, long_, f.y, f.x, idx)
                if best is None or cand < best:
                    best = cand
        if best is None:
            raise CompactionError(
                "rect %r does not fit remaining space" % (r.id,), "does-not-fit"
            )
        _s, _l, y, x, _idx = best
        p = Placement(r.id, x, y, r.w, r.h)
        placements.append(p)
        used_w = max(used_w, x + r.w)
        used_h = max(used_h, y + r.h)
        new_frees: List[_Free] = []
        for f in frees:
            new_frees.extend(_split_free(f, p))
        frees = _prune(new_frees)
    placements.sort(key=lambda p: p.id)
    return Packing(placements=placements, width=used_w, height=used_h)


def _smoke() -> int:
    try:
        demo = [("a", 64, 64), ("b", 32, 128), ("c", 100, 20), ("d", 40, 40)]
        pk = compact(demo, 256, 256)
        assert len({p.id for p in pk.placements}) == 4
        print(
            "compactor smoke ok: %dx%d, %d placements"
            % (pk.width, pk.height, len(pk.placements))
        )
        return 0
    except CompactionError as exc:
        sys.stderr.write("CompactionError(%s): %s\n" % (exc.reason, exc))
        return 1
    except AssertionError:
        sys.stderr.write("smoke assertion failed\n")
        return 2


if __name__ == "__main__":
    sys.exit(_smoke())
