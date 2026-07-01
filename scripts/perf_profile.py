#!/usr/bin/env python
# =============================================================================
# SCRIPT: perf_profile  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Measure the frame render time of the 8K-grid tiled drawBackground
#   scenario HEADLESS and compare the median frame time to FRAME_BUDGET_MS
#   (16 ms => 60 fps, S12). Produces the profiling report AGT-10 uses to issue
#   optimization directives; AGT-05 implements them.
# FLAVOUR: standalone
# LOCATION: scripts/perf_profile.py
# INVOKED BY: AGT-10 Rendering & Performance (frame-budget profiling).
# RUNTIME: Python 3.12 target (3.8+ ok) + PySide6 (Qt6). Runs under
#   QT_QPA_PLATFORM=offscreen so it needs no display (CI-safe).
# ENTRYPOINT: python scripts/perf_profile.py [--width 7680] [--height 4320]
#             [--tile 64] [--zoom 1.0] [--viewport 1920 1080] [--frames 30]
#             [--budget-ms 16.0]
# INPUTS: all CLI args optional; defaults come from logic.constants when
#   importable (MAX_CANVAS_WIDTH/HEIGHT, TILE_SIZE, FRAME_BUDGET_MS), else the
#   literal fallbacks above.
# OUTPUTS:
#   stdout: JSON {"median_ms","p95_ms","budget_ms","frames","tiles_per_frame",
#                 "within_budget", "scenario":{...}}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 within budget -> COMPLETED ; 1 over budget -> FAILED (over-budget
#   is a real, actionable result, not a crash) ; 2 error / PySide6 unavailable
#   -> BLOCKED.
# PRECONDITIONS: PySide6 importable; offscreen platform available.
# DETERMINISM NOTE: timings are inherently machine-dependent (NOT bit-reproducible)
#   — this is a *measurement* script; the SCENARIO it measures is fully
#   deterministic (fixed geometry, fixed tile fill, fixed frame count, median +
#   p95 over a fixed sample). No random/network. Timing method is normalized to
#   per-frame drawBackground of the exposed viewport rect.
#
# ## Principles Applied
# Inherited: P1 (grounded F2/F3/F4/F7, FRAME_BUDGET_MS S12), P2 (deterministic
#   scenario; measurement variance disclosed), P3, P4, P6 (declares PySide6 dep +
#   fallback), P7, P9 (one job: frame-budget profiling), P10 (exit->status),
#   P11, P12 (median + p95 + tiles/frame reported), P13.
# Custom:
#   CP1 — Measurement-not-computation: outputs are timings, so bit-for-bit
#     reproducibility is not claimed; the measured scenario is deterministic and
#     the pass/fail rule (median <= budget) is fixed. (Rationale: perf profiling
#     is inherently host-sensitive; P2 applies to the scenario + decision rule.)
#
# SOURCES: Dossier §2 F2/F3/F4/F7, §6.5/§8 (owner AGT-10); User req S12
#   (FRAME_BUDGET_MS=16, FPS_TARGET=60); Qt QGraphicsScene.drawBackground /
#   QGraphicsView docs (grounded via Researcher); asset-templates.md §Script.
# =============================================================================
import argparse
import json
import os
import sys
import time

# Defaults from the centralised constants (S12) when the package is importable.
try:
    from pixelart_creator.logic import constants as _c

    D_W, D_H = _c.MAX_CANVAS_WIDTH, _c.MAX_CANVAS_HEIGHT
    D_TILE, D_BUDGET = _c.TILE_SIZE, float(_c.FRAME_BUDGET_MS)
except Exception:  # pragma: no cover - fallback when package not on path
    D_W, D_H, D_TILE, D_BUDGET = 7680, 4320, 64, 16.0


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def main():
    ap = argparse.ArgumentParser(description="Headless frame-budget profiler (S12).")
    ap.add_argument("--width", type=int, default=D_W)
    ap.add_argument("--height", type=int, default=D_H)
    ap.add_argument("--tile", type=int, default=D_TILE)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--viewport", type=int, nargs=2, default=[1920, 1080])
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--budget-ms", type=float, default=D_BUDGET)
    args = ap.parse_args()

    if min(args.width, args.height, args.tile) <= 0 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid geometry/frames.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
    except Exception as exc:  # PySide6 not installed -> BLOCKED, not a crash.
        sys.stderr.write("perf_profile: PySide6 unavailable: %r\n" % exc)
        print(json.dumps({"error": "pyside6-unavailable", "detail": repr(exc)}))
        return 2

    vw, vh = args.viewport
    # Exposed scene rect at this zoom (what drawBackground would receive).
    scene_w = vw / max(args.zoom, 1e-6)
    scene_h = vh / max(args.zoom, 1e-6)
    tile = args.tile

    def draw_background_tiles(painter, rect):
        # Mirror the scene.drawBackground(painter, rect) tiling (F2): only the
        # exposed tiles are painted (viewport culling), not the full 8K grid.
        left = int(rect.left()) - (int(rect.left()) % tile)
        top = int(rect.top()) - (int(rect.top()) % tile)
        count = 0
        y = top
        c0 = QColor(40, 40, 40)
        c1 = QColor(56, 56, 56)
        while y < rect.bottom():
            x = left
            while x < rect.right():
                painter.fillRect(
                    QRectF(x, y, tile, tile),
                    c0 if ((x // tile + y // tile) % 2 == 0) else c1,
                )
                x += tile
                count += 1
            y += tile
        return count

    try:
        img = QImage(vw, vh, QImage.Format_ARGB32_Premultiplied)
        samples = []
        tiles_per_frame = 0
        # Warm-up frame (JIT/first-paint costs excluded from the sample).
        painter = QPainter(img)
        draw_background_tiles(painter, QRectF(0, 0, scene_w, scene_h))
        painter.end()
        for i in range(args.frames):
            offset = (i % 8) * tile  # pan a little each frame (dirty-rect realism)
            rect = QRectF(offset, offset, scene_w, scene_h)
            painter = QPainter(img)
            t0 = time.perf_counter()
            tiles_per_frame = draw_background_tiles(painter, rect)
            t1 = time.perf_counter()
            painter.end()
            samples.append((t1 - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: render error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    within = median <= args.budget_ms
    report = {
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "budget_ms": args.budget_ms,
        "frames": args.frames,
        "tiles_per_frame": tiles_per_frame,
        "within_budget": within,
        "scenario": {
            "width": args.width,
            "height": args.height,
            "tile": tile,
            "zoom": args.zoom,
            "viewport": [vw, vh],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: OVER budget (median %.3f ms > %.1f ms).\n"
            % (median, args.budget_ms)
        )
        return 1
    sys.stderr.write("perf_profile: within budget (median %.3f ms).\n" % median)
    return 0


if __name__ == "__main__":
    sys.exit(main())
