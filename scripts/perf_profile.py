#!/usr/bin/env python
# =============================================================================
# SCRIPT: perf_profile  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Two profiling modes over the 8K canvas, HEADLESS.
#   (default) tiling: measure per-frame drawBackground tiling time vs
#     FRAME_BUDGET_MS (16 ms => 60 fps, S12); the report AGT-10 uses to issue
#     render directives (AGT-05 implements them). Requires PySide6.
#   --composite: FU-15 compositor regression gate. Measure the region
#     recomposite path — blend.composite_stack(region=(x, y, r, r)) — on an 8K
#     multi-layer document, comparing median ms to COMPOSITE_REGION_CEILING_MS
#     (200 ms, a loose catastrophic-regression bound, NOT the 16 ms frame
#     budget). This branch is Qt-FREE: numpy + pixelart_creator.logic only, NO
#     PySide6 import (per AGT-10 rendering-performance directive).
# FLAVOUR: standalone
# LOCATION: scripts/perf_profile.py
# INVOKED BY: AGT-10 Rendering & Performance (frame-budget profiling); the
#   --composite gate runs in CI (AGT-09 wires .github/workflows/ci.yml).
# RUNTIME: Python 3.12 target (3.8+ ok). Tiling mode needs PySide6 (Qt6) under
#   QT_QPA_PLATFORM=offscreen (no display, CI-safe); composite mode needs only
#   numpy + the logic package (no Qt).
# ENTRYPOINT (tiling): python scripts/perf_profile.py [--width 7680]
#             [--height 4320] [--tile 64] [--zoom 1.0] [--viewport 1920 1080]
#             [--frames 30] [--budget-ms 16.0]
# ENTRYPOINT (composite): python scripts/perf_profile.py --composite
#             [--layers 8] [--region-size 16] [--ceiling-ms 200.0]
#             [--width 7680] [--height 4320] [--frames 30]
# INPUTS: all CLI args optional; defaults come from logic.constants when
#   importable (MAX_CANVAS_WIDTH/HEIGHT, TILE_SIZE, FRAME_BUDGET_MS,
#   COMPOSITE_REGION_CEILING_MS), else the literal fallbacks above.
# OUTPUTS:
#   stdout (tiling): JSON {"median_ms","p95_ms","budget_ms","frames",
#                 "tiles_per_frame","within_budget", "scenario":{...}}.
#   stdout (composite): JSON {"mode":"composite","median_ms","p95_ms",
#                 "ceiling_ms","frame_budget_ms","within_ceiling","frames",
#                 "layers","scenario":{...}}.
#   stderr: human summary. exit code per EXIT CODES.
# EXIT CODES: 0 within budget/ceiling -> COMPLETED ; 1 over budget/ceiling ->
#   FAILED (an over-limit result is real and actionable, not a crash) ; 2 error
#   / PySide6 unavailable (tiling only) -> BLOCKED. Composite mode has no
#   PySide6 branch, so it never exits 2 for a missing-Qt reason.
# PRECONDITIONS: tiling — PySide6 importable + offscreen platform; composite —
#   numpy + pixelart_creator.logic importable.
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
    D_FRAME_BUDGET = int(_c.FRAME_BUDGET_MS)
    D_CEILING = float(_c.COMPOSITE_REGION_CEILING_MS)
except Exception:  # pragma: no cover - fallback when package not on path
    D_W, D_H, D_TILE, D_BUDGET = 7680, 4320, 64, 16.0
    D_FRAME_BUDGET, D_CEILING = 16, 200.0

# Composite-mode defaults (AGT-10 directive §3a).
D_LAYERS = 8
D_REGION_SIZE = 16


def _percentile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


# --------------------------------------------------------------------------- #
# Composite mode (FU-15) — Qt-FREE region-recomposite regression gate          #
# --------------------------------------------------------------------------- #
# Origin-variation strides (coprime with common canvas dims) so the region
# origin sweeps the canvas each frame -> group flatten cache is cold every call
# (a realistic fresh brush dab), not a cache short-circuit. Fixed => deterministic.
_ORIGIN_STRIDE_X = 613
_ORIGIN_STRIDE_Y = 409
_COMPOSITE_WARMUP = 2  # warm-up calls excluded from the timed sample


class _Leaf:
    """Minimal duck ``blend.CompositeNode`` leaf for the composite scenario.

    Exposes exactly the structural surface the compositor reads for a leaf
    (``opacity``, ``visible``, ``blend_mode``, ``mask``, ``effective_buffer``)
    and *no* ``children`` attribute, so ``blend._composite_region`` treats it as
    a leaf. Keeps the gate Qt-free — it never touches ``document.Layer``.
    """

    __slots__ = ("opacity", "visible", "blend_mode", "mask", "_buffer")

    def __init__(self, buffer, blend_mode):
        self.opacity = 1.0
        self.visible = True
        self.blend_mode = blend_mode
        self.mask = None
        self._buffer = buffer

    def effective_buffer(self):
        """Return this leaf's resident RGBA buffer (read-only to the compositor)."""
        return self._buffer


def _run_composite(args):
    """Run the FU-15 region-recomposite regression gate (Qt-free).

    Builds ``args.layers`` deterministically-filled 8K RGBA leaves with mixed
    blend modes (>=1 non-NORMAL), then times ``args.frames`` region recomposite
    calls with the region origin varied each frame (cache-cold). Reports median
    + p95 ms and compares the median to ``args.ceiling_ms``.

    Returns the process exit code: 0 (median <= ceiling), 1 (over ceiling),
    2 (construction/geometry error).
    """
    width, height = args.width, args.height
    layers = args.layers
    rsize = args.region_size
    ceiling = args.ceiling_ms

    if layers < 1 or rsize < 1 or width <= 0 or height <= 0 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid composite geometry/layers.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2
    if rsize > width or rsize > height:
        sys.stderr.write("perf_profile: region-size exceeds canvas.\n")
        print(json.dumps({"error": "region-larger-than-canvas"}))
        return 2

    # Qt-FREE imports: numpy + logic only (NO PySide6 on this branch).
    try:
        from pixelart_creator.logic.blend import BlendMode, composite_stack
        from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
    except Exception as exc:  # logic unavailable -> construction error, not Qt.
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    # Mixed blend modes across the stack: >=1 non-NORMAL so the float32
    # separable path is exercised, not just the source-over fast path.
    mode_cycle = [
        BlendMode.NORMAL,
        BlendMode.MULTIPLY,
        BlendMode.SCREEN,
        BlendMode.OVERLAY,
        BlendMode.SOFT_LIGHT,
        BlendMode.DIFFERENCE,
        BlendMode.LIGHTEN,
        BlendMode.COLOR_DODGE,
    ]

    try:
        nodes = []
        blend_modes = []
        for i in range(layers):
            # Deterministic per-layer fill (P2 — no RNG at gate time); alpha < 255
            # so every layer actually composites rather than fully occluding.
            fill = (
                (i * 40 + 20) % 256,
                (i * 70 + 30) % 256,
                (i * 110 + 60) % 256,
                180,
            )
            buffer = PixelBuffer(width, height, ColorMode.RGBA, fill=fill)
            mode = mode_cycle[i % len(mode_cycle)]
            nodes.append(_Leaf(buffer, mode))
            blend_modes.append(mode.value)
    except Exception as exc:
        sys.stderr.write("perf_profile: composite construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    span_x = max(1, width - rsize)
    span_y = max(1, height - rsize)

    def _origin(frame_index):
        x = (frame_index * _ORIGIN_STRIDE_X) % span_x
        y = (frame_index * _ORIGIN_STRIDE_Y) % span_y
        return x, y

    try:
        # Warm-up calls excluded (numpy/first-call cost), matching the tiler.
        for w in range(_COMPOSITE_WARMUP):
            wx, wy = _origin(w)
            composite_stack(nodes, width, height, region=(wx, wy, rsize, rsize))

        samples = []
        for i in range(args.frames):
            # Offset past the warm-up frames so the origin is cold each timed call.
            ox, oy = _origin(i + _COMPOSITE_WARMUP)
            t0 = time.perf_counter()
            composite_stack(nodes, width, height, region=(ox, oy, rsize, rsize))
            t1 = time.perf_counter()
            samples.append((t1 - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: composite error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    within = median <= ceiling
    report = {
        "mode": "composite",
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "ceiling_ms": ceiling,
        "frame_budget_ms": args.frame_budget_ms,
        "within_ceiling": within,
        "frames": args.frames,
        "layers": layers,
        "scenario": {
            "width": width,
            "height": height,
            "layers": layers,
            "region_size": rsize,
            "blend_modes": blend_modes,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: OVER ceiling (median %.3f ms > %.1f ms) — FU-15 "
            "region-recomposite regression.\n" % (median, ceiling)
        )
        return 1
    sys.stderr.write(
        "perf_profile: within ceiling (median %.3f ms <= %.1f ms).\n"
        % (median, ceiling)
    )
    return 0


def main():
    ap = argparse.ArgumentParser(description="Headless frame-budget profiler (S12).")
    ap.add_argument("--width", type=int, default=D_W)
    ap.add_argument("--height", type=int, default=D_H)
    ap.add_argument("--tile", type=int, default=D_TILE)
    ap.add_argument("--zoom", type=float, default=1.0)
    ap.add_argument("--viewport", type=int, nargs=2, default=[1920, 1080])
    ap.add_argument("--frames", type=int, default=30)
    ap.add_argument("--budget-ms", type=float, default=D_BUDGET)
    # --- FU-15 composite mode (Qt-free region-recomposite regression gate) ---
    ap.add_argument(
        "--composite",
        action="store_true",
        help="run the FU-15 region-recomposite regression gate (Qt-free)",
    )
    ap.add_argument("--layers", type=int, default=D_LAYERS)
    ap.add_argument("--region-size", type=int, default=D_REGION_SIZE)
    ap.add_argument("--ceiling-ms", type=float, default=D_CEILING)
    ap.add_argument("--frame-budget-ms", type=int, default=D_FRAME_BUDGET)
    args = ap.parse_args()

    if args.composite:
        return _run_composite(args)

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
