#!/usr/bin/env python
# Copyright 2026 Juan Garcia Sanchez
# SPDX-License-Identifier: Apache-2.0
# =============================================================================
# SCRIPT: perf_profile  (standalone P11 script — PixelArt Creator system)
# =============================================================================
# PURPOSE: Two profiling modes over the 8K canvas, HEADLESS.
#   (default) tiling: measure per-frame render time of the REAL, SHIPPED
#     ui.canvas_scene.CanvasScene.drawBackground (D-32, REQ-P1-UI-023) vs
#     FRAME_BUDGET_MS (16 ms => 60 fps, S12, unrelaxed Tier-1 interactive
#     budget); the report render-optimisation directives are issued from (the
#     UI layer implements them). --width/--height build a real Document of that
#     geometry and are LIVE: the exposed rect is intersected with the real
#     scene's own sceneRect (what a QGraphicsView does), so tiles/frame
#     tracks the scene geometry, not just the viewport (D-32 fixes the audit's
#     CF-06 finding that these flags were previously inert — a 7680x4320 and a
#     64x64 canvas both reported 510 tiles/frame). Requires PySide6.
#   --composite: FU-15 compositor regression gate. Measure the region
#     recomposite path — blend.composite_stack(region=(x, y, r, r)) — on an 8K
#     multi-layer document, comparing median ms to COMPOSITE_REGION_CEILING_MS
#     (200 ms, a loose catastrophic-regression bound, NOT the 16 ms frame
#     budget). This branch is Qt-FREE: numpy + pixelart_creator.logic only, NO
#     PySide6 import (per the rendering-performance directive).
#   --full-frame: Slice-A (FU-P5-PERF) cold full-frame flatten regression gate.
#     Measure the WHOLE-CANVAS flatten path — blend.composite_stack(region=None)
#     over the full (H, W, 4) 8K canvas — the path the 16-px --composite gate is
#     structurally blind to. --content realistic (sparse, predominantly NORMAL —
#     the CI gate) is compared to the loose COMPOSITE_FULL_CEILING_MS; --content
#     dense (pathological, every-pixel-every-layer non-normal) is profiled for
#     the record and is deliberately NOT gated (accepted off-thread cold cost,
#     spec REQ-P12-LOGIC-001). Qt-FREE: numpy + logic only, NO PySide6.
# FLAVOUR: standalone
# LOCATION: scripts/perf_profile.py
# INVOKED BY: render-performance work, for frame-budget profiling; the
#   --composite gate runs in CI (.github/workflows/ci.yml).
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
#   deterministic (fixed geometry, fixed pan offsets, fixed frame count, median +
#   p95 over a fixed sample). No random/network. Timing method is normalized to
#   per-frame CanvasScene.drawBackground of the exposed viewport rect, clamped
#   to the scene's own sceneRect (D-32).
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
# SOURCES: Dossier §2 F2/F3/F4/F7, §6.5/§8; User req S12
#   (FRAME_BUDGET_MS=16, FPS_TARGET=60); Qt QGraphicsScene.drawBackground /
#   QGraphicsView docs (grounded via Researcher); asset-templates.md §Script.
# =============================================================================
import argparse
import json
import math
import os
import sys
import time

# Ceiling/threshold constant names this profiler REQUIRES from the single
# source of truth (S12) once the package is importable at all. C-08: a
# missing attribute on an otherwise-importable ``logic.constants`` module
# used to be silently patched over by a ``getattr(_c, "<NAME>", <literal>)``
# fallback -- and for VIEWPORT_RECOMPOSITE_CEILING_MS that literal (3000)
# happens to EQUAL the real shipped value, so a broken/regressed constants
# import could leave that gate passing at a coincidentally-identical number
# with Article II silently defeated. Below, each of these is read directly
# off the imported module; if any is missing, the failure is loud (named,
# actionable, non-zero exit) instead of a guessed literal standing in.
_REQUIRED_CEILING_ATTRS = (
    "REALTIME_APPLY_CEILING_MS",
    "MAX_SHARED_MEMBERS",
    "OVERLAY_FRAME_CEILING_MS",
    "COMPOSITE_FULL_CEILING_MS",
    "VIEWPORT_RECOMPOSITE_CEILING_MS",
)

# Defaults from the centralised constants (S12) when the package is importable.
try:
    from pixelart_creator.logic import constants as _c

    D_W, D_H = _c.MAX_CANVAS_WIDTH, _c.MAX_CANVAS_HEIGHT
    D_TILE, D_BUDGET = _c.TILE_SIZE, float(_c.FRAME_BUDGET_MS)
    D_FRAME_BUDGET = int(_c.FRAME_BUDGET_MS)
    D_CEILING = float(_c.COMPOSITE_REGION_CEILING_MS)

    _missing = [name for name in _REQUIRED_CEILING_ATTRS if not hasattr(_c, name)]
    if _missing:
        # NOT the "package not on PYTHONPATH" case (that is the except-Exception
        # branch below, with its documented literal fallbacks) -- this is a
        # module that DID import but has regressed, or a stale/partial
        # constants module shadowing the real one. Refuse to substitute a
        # hard-coded literal that could coincidentally match (and therefore
        # mask) the real value (C-08).
        sys.stderr.write(
            "perf_profile: logic.constants is importable but is missing the "
            "following required ceiling constant(s): %s -- refusing to "
            "silently fall back to a literal.\n" % ", ".join(_missing)
        )
        print(json.dumps({"error": "missing-constants", "missing": _missing}))
        sys.exit(2)

    # Realtime apply sub-frame ceiling (Slice C, FLAG-PERFRAME). Distinct from
    # FRAME_BUDGET_MS: apply_remote is only PART of the interactive frame (the
    # dirty-rect redraw + live-cursor draw share the same 16 ms), so the apply
    # gets a sub-budget partition.
    D_RT_CEILING = float(_c.REALTIME_APPLY_CEILING_MS)
    # Live-cursor overlay roster bound (Slice C, REQ-P10-UI-013). The overlay
    # draw is bounded by this many cursors (Article VII), so the worst-case
    # per-frame paint profiles at MAX_SHARED_MEMBERS visible cursors.
    D_MAX_CURSORS = int(_c.MAX_SHARED_MEMBERS)
    D_OVERLAY_CEILING = int(_c.OVERLAY_FRAME_CEILING_MS)
    # Full-frame flatten loose catastrophic ceiling (Slice A, FU-P5-PERF).
    D_FULL_CEILING = float(_c.COMPOSITE_FULL_CEILING_MS)
    # Viewport-recomposite / opacity-drag COMMIT loose catastrophic ceiling
    # (Slice B, FU-16b / ADR-0034 §4), single-source (S12).
    D_VP_CEILING = float(_c.VIEWPORT_RECOMPOSITE_CEILING_MS)
except Exception:  # pragma: no cover - fallback when package not on path
    # SystemExit (raised by the loud sys.exit(2) above) is a BaseException, NOT
    # an Exception, so it is never caught here -- the loud path always
    # propagates instead of silently landing on these fallbacks (C-08).
    D_W, D_H, D_TILE, D_BUDGET = 7680, 4320, 64, 16.0
    D_FRAME_BUDGET, D_CEILING = 16, 200.0
    D_RT_CEILING = 10.0
    D_MAX_CURSORS = 32
    D_OVERLAY_CEILING = 48
    D_FULL_CEILING = 3000.0
    D_VP_CEILING = 3000.0

# Viewport-recomposite (Slice B split-cache COMMIT) gate defaults (ADR-0034 §4/§5).
D_VP_LAYERS = 12
D_VP_REGION_SIZE = 1920
D_VP_NONNORMAL = 1

# Composite-mode defaults (render-performance directive §3a).
D_LAYERS = 8
D_REGION_SIZE = 16

# Tilemap-mode defaults (DEP-3 Phase-6 render-seam profiling). Qt-FREE:
# times logic/tilemap.render_region — the single tunable call the tilemap
# drawBackground seam issues per exposed rect (the DEP-3 report). Distinct
# from the composite gate: this measures the tilemap per-cell resolve+blit+
# composite cost against FRAME_BUDGET_MS (16 ms), not the region-recomposite
# catastrophic ceiling.
D_TM_TILE = 16  # default tileset tile edge (DEFAULT_TILE_WIDTH) — NOT TILE_SIZE
D_TM_LAYERS = 1
_TM_ATLAS_EDGE_TILES = 8  # 8x8 = 64 tiles >= 47 blob frames for the autotile case


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


# --------------------------------------------------------------------------- #
# Full-frame mode (Slice A, FU-P5-PERF) — Qt-FREE cold full-canvas flatten gate #
# --------------------------------------------------------------------------- #
# Times the OPTIMISED full-frame flatten — blend.composite_stack(region=None) over
# the whole (H, W, 4) canvas — the path today's 16-px --composite gate is
# structurally blind to (it only composites a square sub-region). Qt-FREE: numpy +
# pixelart_creator.logic only, NO PySide6. Compares the median to a LOOSE
# catastrophic-regression ceiling (COMPOSITE_FULL_CEILING_MS), NOT the 16 ms frame
# budget — the flatten is a batch / on-demand op, never a 60-fps path (spec §5).
#
# Two content models (spec REQ-P12-LOGIC-001 "realistic vs pathological"):
#   * realistic (the GATE scenario): a typical finished pixel-art stack — one full
#     OPAQUE background layer (alpha 255, NORMAL) + sparse OPAQUE content layers
#     (a tile-aligned coverage band at alpha 255, the rest transparent) + a MINORITY
#     of sparse non-normal separable layers. Every layer is opacity-1 / unmasked, so
#     the uint8 fast-paths carry the majority byte-exactly: a fully-opaque tile takes
#     the ``acc = src.copy()`` path; a fully-transparent (alpha-0) tile is skipped;
#     only the one/few non-normal layers hit the float32 separable path. The band is
#     aligned to the flatten tile edge so NORMAL layers produce NO mixed (part-alpha)
#     tiles — the honest fast-path-dominant realistic cost. This passes the loose
#     ceiling with comfortable margin yet still balloons to the old ~20–43 s if the
#     Slice-A optimisation (tiling + fast-path + fan-out) is reverted, because
#     without the fast-path every NORMAL layer costs a full-canvas float pass
#     regardless of sparsity → the gate catches the regression.
#   * dense (the pathological worst case — NOT gated): every pixel painted on every
#     layer AND every layer in a non-normal separable mode → forces full-canvas
#     float promotion across all 33 M px × every layer. Its cold cost is an ACCEPTED
#     off-thread cost (spec REQ-P12-LOGIC-001), profiled here for the record only —
#     it is deliberately run with --content dense and is NOT the CI gate config.
_FF_WARMUP = 1  # one cold warm-up call excluded (numpy/thread-pool first-touch)


def _run_full_frame(args):
    """Run the Slice-A cold full-frame flatten perf gate (Qt-free).

    Builds ``args.layers`` full-canvas RGBA leaves per the chosen ``--content``
    model, then times ``args.frames`` cold ``composite_stack(region=None)`` calls
    over the whole ``(height, width, 4)`` canvas and compares the median to
    ``args.ceiling_ms`` (the loose ``COMPOSITE_FULL_CEILING_MS``, NOT 16 ms).

    Returns the process exit code: 0 (median <= ceiling), 1 (over ceiling),
    2 (construction/geometry/logic-import error).
    """
    width, height = args.width, args.height
    layers = args.layers
    ceiling = args.ceiling_ms
    content = args.content
    coverage = args.ff_coverage
    nonnormal = args.ff_nonnormal

    if layers < 1 or width <= 0 or height <= 0 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid full-frame geometry/layers.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2
    if not (0.0 < coverage <= 1.0) or nonnormal < 0 or nonnormal > layers:
        sys.stderr.write("perf_profile: invalid full-frame coverage/nonnormal.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    # Qt-FREE imports: numpy + logic only (NO PySide6 on this branch).
    try:
        import numpy as np  # noqa: F401 (used via PixelBuffer.data slicing)

        from pixelart_creator.logic import blend as _blend
        from pixelart_creator.logic.blend import BlendMode, composite_stack
        from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
    except Exception as exc:  # logic unavailable -> construction error, not Qt.
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    # The eleven non-normal separable modes (NORMAL excluded — the fast path).
    non_normal = [m for m in BlendMode if m is not BlendMode.NORMAL]

    # Flatten tuning read from logic (single-source) — also used to align the
    # realistic coverage band to the tile edge so NORMAL layers stay pure fast-path
    # (no mixed part-alpha tiles), and to report the fan-out for 2-core reasoning.
    cpu = os.cpu_count() or 1
    max_workers = int(getattr(_blend, "FLATTEN_MAX_WORKERS", 8))
    tile_edge = int(getattr(_blend, "FLATTEN_TILE_EDGE_PX", 1024))
    tiles = ((width + tile_edge - 1) // tile_edge) * (
        (height + tile_edge - 1) // tile_edge
    )
    effective_workers = min(max_workers, cpu, tiles)

    def _tile_aligned_band(index, cov):
        """A ``(y0, band)`` sparse band, tile-edge-aligned, covering ~``cov`` height.

        Both the band height and its origin snap to ``tile_edge`` so a NORMAL layer
        is fully opaque or fully transparent on every flatten tile (no mixed tiles →
        pure uint8 fast-path). The origin steps per layer (deterministic, no RNG) so
        layers sit at different bands (varied, realistic), staying in bounds.
        """
        rows = max(tile_edge, (int(round(height * cov)) // tile_edge) * tile_edge)
        rows = min(rows, (height // tile_edge) * tile_edge or height)
        free_tiles = max(1, (height - rows) // tile_edge + 1)
        y0 = ((index * 2) % free_tiles) * tile_edge
        return y0, rows

    try:
        nodes = []
        blend_modes = []
        for i in range(layers):
            # Deterministic per-layer colour (P2 — no RNG at gate time).
            base = (
                (i * 40 + 20) % 256,
                (i * 70 + 30) % 256,
                (i * 110 + 60) % 256,
            )
            if content == "dense":
                # Pathological: every pixel painted, every layer non-normal — full
                # float promotion over all 33 M px × every layer (baseline #1b).
                buffer = PixelBuffer(
                    width, height, ColorMode.RGBA, fill=(base[0], base[1], base[2], 180)
                )
                mode = non_normal[i % len(non_normal)]
            elif i == 0:
                # Realistic: layer 0 is a full OPAQUE background (alpha 255, NORMAL).
                # Fully opaque → every tile takes the ``acc = src.copy()`` fast path.
                buffer = PixelBuffer(
                    width, height, ColorMode.RGBA, fill=(base[0], base[1], base[2], 255)
                )
                mode = BlendMode.NORMAL
            else:
                # Realistic content / effects layer: a tile-aligned sparse OPAQUE
                # band (alpha 255), the rest transparent. The last ``nonnormal``
                # layers take a non-normal separable mode (the minority); the rest
                # stay NORMAL (pure fast-path over their opaque/transparent tiles).
                buffer = PixelBuffer(width, height, ColorMode.RGBA)  # transparent
                y0, band = _tile_aligned_band(i, coverage)
                buffer.data[y0 : y0 + band, :] = (base[0], base[1], base[2], 255)
                if i >= layers - nonnormal:
                    mode = non_normal[i % len(non_normal)]
                else:
                    mode = BlendMode.NORMAL
            nodes.append(_Leaf(buffer, mode))
            blend_modes.append(mode.value)
    except Exception as exc:
        sys.stderr.write("perf_profile: full-frame construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    try:
        for _ in range(_FF_WARMUP):
            composite_stack(nodes, width, height, region=None)
        samples = []
        for _ in range(args.frames):
            t0 = time.perf_counter()
            composite_stack(nodes, width, height, region=None)
            samples.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: full-frame flatten error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    # The pathological dense case is an ACCEPTED off-thread cold cost, NOT gated
    # (spec REQ-P12-LOGIC-001). Only the realistic content model gates in CI.
    gated = content != "dense"
    within = (median <= ceiling) if gated else True
    report = {
        "mode": "full-frame",
        "content": content,
        "gated": gated,
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
            "coverage": coverage if content != "dense" else 1.0,
            "nonnormal_layers": (layers if content == "dense" else nonnormal),
            "blend_modes": blend_modes,
            "flatten_tile_edge_px": tile_edge,
            "flatten_tiles": tiles,
            "cpu_count": cpu,
            "flatten_max_workers": max_workers,
            "effective_workers": effective_workers,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not gated:
        sys.stderr.write(
            "perf_profile: full-frame[dense] median %.1f ms — ACCEPTED off-thread "
            "cold cost, NOT gated against the ceiling (record only).\n" % median
        )
        return 0
    if not within:
        sys.stderr.write(
            "perf_profile: full-frame OVER ceiling (median %.1f ms > %.1f ms) — "
            "FU-P5-PERF cold full-frame flatten regression.\n" % (median, ceiling)
        )
        return 1
    sys.stderr.write(
        "perf_profile: full-frame within ceiling (median %.1f ms <= %.1f ms; "
        "%d workers over %d tiles).\n" % (median, ceiling, effective_workers, tiles)
    )
    return 0


# --------------------------------------------------------------------------- #
# Tilemap mode (DEP-3) — Qt-FREE render-seam frame-budget profiler             #
# --------------------------------------------------------------------------- #
# Origin sweep strides (coprime with tile/chunk edges) so a pan scenario reads
# a fresh set of chunks each frame rather than short-circuiting on identity.
_TM_STRIDE_X = 37
_TM_STRIDE_Y = 23
_TM_WARMUP = 2


def _run_tilemap(args):
    """Profile ``logic/tilemap.render_region`` against FRAME_BUDGET_MS (DEP-3).

    Builds a populated tilemap (a real RGBA tileset atlas + ``args.tm_layers``
    chunked-sparse layers, optionally auto-tiled) and times ``args.frames``
    ``render_region(x, y, rw, rh)`` calls over an ``rw`` x ``rh`` pixel region —
    the exact viewport-cull seam the tilemap ``drawBackground`` issues per exposed
    rect (the render-seam report). Qt-FREE: numpy + logic only, so it runs in
    CI under no display. Compares the median to ``args.budget_ms`` (16 ms, S12).

    Returns 0 (median <= budget), 1 (over budget), 2 (construction error).
    """
    rw, rh = args.tm_region
    tw = args.tm_tile
    layers = args.tm_layers
    budget = args.budget_ms

    if rw <= 0 or rh <= 0 or tw <= 0 or layers < 1 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid tilemap geometry/layers.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2
    if rw > D_W or rh > D_H:
        sys.stderr.write("perf_profile: tilemap region exceeds canvas bounds.\n")
        print(json.dumps({"error": "region-larger-than-canvas"}))
        return 2

    # Qt-FREE imports: numpy + logic only (NO PySide6 on this branch).
    try:
        from pixelart_creator.logic.autotile import (
            BLOB_TILE_COUNT,
            AutotileRuleset,
        )
        from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
        from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
        from pixelart_creator.logic.tileset import Tileset
    except Exception as exc:  # logic unavailable -> construction error, not Qt.
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    try:
        # A real RGBA tileset atlas: 8x8 = 64 tiles (>= 47 blob frames). Each tile
        # gets a distinct semi-opaque fill so blit actually alpha-composites (the
        # per-cell blend cost is on the critical path — no fully-opaque shortcut).
        atlas_edge = _TM_ATLAS_EDGE_TILES
        source = PixelBuffer(
            atlas_edge * tw, atlas_edge * tw, ColorMode.RGBA, fill=(90, 140, 200, 200)
        )
        tileset = Tileset(source, tile_width=tw, tile_height=tw, first_gid=1)
        tilemap = Tilemap(tile_width=tw, tile_height=tw)
        tilemap.tilesets.append(tileset)

        # Cell range covering the region plus a margin so a pan scenario can slide
        # the origin over genuinely populated chunks each frame (culling realism).
        margin_cells = max(2, (max(_TM_STRIDE_X, _TM_STRIDE_Y) // tw) + 2)
        cols = rw // tw + margin_cells
        rows = rh // tw + margin_cells
        terrain_gid = 1

        for li in range(layers):
            layer = TilemapLayer(name=f"L{li}")
            if args.tm_autotile:
                frame_gids = list(range(terrain_gid, terrain_gid + BLOB_TILE_COUNT))
                layer.autotile = AutotileRuleset(
                    terrain_gid=terrain_gid, frame_gids=frame_gids
                )
            tilemap.layers.append(layer)
            # Populate the full cell block (worst case: every cell occupied).
            cmd = tilemap.make_fill_rect_command(li, 0, 0, cols, rows, terrain_gid)
            cmd.execute()
    except Exception as exc:
        sys.stderr.write("perf_profile: tilemap construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    # Slide the origin over the populated margin so each frame reads fresh cells.
    span_x = max(1, margin_cells * tw)
    span_y = max(1, margin_cells * tw)

    def _origin(i):
        return ((i * _TM_STRIDE_X) % span_x, (i * _TM_STRIDE_Y) % span_y)

    try:
        for w in range(_TM_WARMUP):
            ox, oy = _origin(w)
            tilemap.render_region(ox, oy, rw, rh)
        samples = []
        for i in range(args.frames):
            ox, oy = _origin(i + _TM_WARMUP)
            t0 = time.perf_counter()
            tilemap.render_region(ox, oy, rw, rh)
            t1 = time.perf_counter()
            samples.append((t1 - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: tilemap render error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    within = median <= budget
    cells = (rw // tw + 1) * (rh // tw + 1) * layers
    report = {
        "mode": "tilemap",
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "budget_ms": budget,
        "within_budget": within,
        "frames": args.frames,
        "cells_per_frame": cells,
        "scenario": {
            "region": [rw, rh],
            "tile": tw,
            "layers": layers,
            "autotile": bool(args.tm_autotile),
            "region_cells": [rw // tw, rh // tw],
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: tilemap OVER budget (median %.3f ms > %.1f ms).\n"
            % (median, budget)
        )
        return 1
    sys.stderr.write(
        "perf_profile: tilemap within budget (median %.3f ms <= %.1f ms).\n"
        % (median, budget)
    )
    return 0


# --------------------------------------------------------------------------- #
# Tilemap CACHE mode (DEP-3 loop-back) — the ACTUAL interactive per-frame slice #
# --------------------------------------------------------------------------- #
# Models the shipped drawBackground path WITH the D1 chunk-pixmap cache in place
# (ui/tilemap_canvas._draw_map), NOT a cold full re-render. The GUI-thread
# per-frame cost is:
#   * up to _SYNC_CHUNK_BUDGET (8) COLD chunks rendered INLINE via render_region
#     (each a chunk-sized region == TILEMAP_CHUNK_SIZE*tile px square); the rest
#     of a cold viewport streams OFF-THREAD (not on this frame's GUI slice), plus
#   * N WARM cached-chunk QPixmap blits (drawPixmap) for chunks already resident.
# COLD first-paint  == cold=_SYNC_CHUNK_BUDGET renders + already-cached blits.
# WARM steady-state == cold=0 renders (pure blits, all cache hits).
# The render slice is Qt-FREE (render_region); the blit slice uses Qt when
# PySide6 is importable (guarded) and degrades to a structural 0 otherwise.
_TM_CHUNK_CELLS_FALLBACK = 16  # TILEMAP_CHUNK_SIZE fallback


def _run_tilemap_cache(args):
    """Profile the cache-in-place GUI-thread per-frame slice (DEP-3 loop-back).

    Per timed frame: render ``args.tm_cold`` cold chunks inline (bounded by the
    _SYNC_CHUNK_BUDGET model) via ``render_region`` over a chunk-sized region,
    then blit ``args.tm_warm`` cached chunk pixmaps (Qt, guarded). Reports the
    per-chunk render cost, the combined GUI-thread frame cost (median + p95), and
    compares the median to ``args.budget_ms`` (16 ms, S12).

    Returns 0 (median <= budget), 1 (over budget), 2 (construction error).
    """
    tw = args.tm_tile
    layers = args.tm_layers
    budget = args.budget_ms
    cold = args.tm_cold
    warm = args.tm_warm
    if tw <= 0 or layers < 1 or args.frames <= 0 or cold < 0 or warm < 0:
        sys.stderr.write("perf_profile: invalid tilemap-cache geometry.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    try:
        from pixelart_creator.logic.autotile import BLOB_TILE_COUNT, AutotileRuleset
        from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
        from pixelart_creator.logic.tilemap import Tilemap, TilemapLayer
        from pixelart_creator.logic.tileset import Tileset

        try:
            from pixelart_creator.logic.constants import TILEMAP_CHUNK_SIZE as _CC
        except Exception:
            _CC = _TM_CHUNK_CELLS_FALLBACK
    except Exception as exc:
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    chunk_cells = _CC
    chunk_px = chunk_cells * tw
    if chunk_px <= 0 or chunk_px > D_W or chunk_px > D_H:
        sys.stderr.write("perf_profile: chunk px exceeds canvas bounds.\n")
        print(json.dumps({"error": "chunk-larger-than-canvas"}))
        return 2

    # Populate a block of chunks large enough to sweep the cold-chunk origins over
    # genuinely-filled chunks (worst case: every cell occupied).
    need_chunks = max(cold, warm, 16)
    grid = 1
    while grid * grid < need_chunks:
        grid += 1
    # Cap the block so it stays within the 8K canvas.
    grid = min(grid, D_W // chunk_px, D_H // chunk_px)
    if grid < 1:
        grid = 1
    block_cells = grid * chunk_cells

    try:
        atlas_edge = _TM_ATLAS_EDGE_TILES
        source = PixelBuffer(
            atlas_edge * tw, atlas_edge * tw, ColorMode.RGBA, fill=(90, 140, 200, 200)
        )
        tileset = Tileset(source, tile_width=tw, tile_height=tw, first_gid=1)
        tilemap = Tilemap(tile_width=tw, tile_height=tw)
        tilemap.tilesets.append(tileset)
        terrain_gid = 1
        for li in range(layers):
            layer = TilemapLayer(name=f"L{li}")
            if args.tm_autotile:
                frame_gids = list(range(terrain_gid, terrain_gid + BLOB_TILE_COUNT))
                layer.autotile = AutotileRuleset(
                    terrain_gid=terrain_gid, frame_gids=frame_gids
                )
            tilemap.layers.append(layer)
            cmd = tilemap.make_fill_rect_command(
                li, 0, 0, block_cells, block_cells, terrain_gid
            )
            cmd.execute()
    except Exception as exc:
        sys.stderr.write("perf_profile: tilemap-cache construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    total_chunks = grid * grid

    def _chunk_origin(idx):
        cxi = idx % grid
        cyi = (idx // grid) % grid
        return cxi * chunk_px, cyi * chunk_px

    # --- Qt blit setup (guarded; warm slice). Degrades to structural 0. -------
    # Uses QImage + QPainter.drawImage (NOT QPixmap): needs no QGuiApplication and
    # runs fully headless. An offscreen/raster QPixmap is a QImage internally, so
    # drawImage of a premultiplied ARGB image is a faithful proxy for the shipped
    # drawPixmap blit cost (a GL viewport uploads to a texture, typically cheaper).
    qt_ok = False
    warm_images = []
    painter_img = None
    _QPainter = _QImage = None
    if warm > 0:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtGui import QImage, QPainter

            _QPainter, _QImage = QPainter, QImage
            qt_ok = True
        except Exception as exc:  # pragma: no cover - Qt absent -> structural 0
            sys.stderr.write(
                "perf_profile: PySide6 unavailable, warm-blit modelled as 0: %r\n" % exc
            )

    try:
        # Per-chunk render cost (Qt-free) — the inline-miss building block.
        per_chunk = []
        for w in range(_TM_WARMUP):
            ox, oy = _chunk_origin(w)
            tilemap.render_region(ox, oy, chunk_px, chunk_px)
        for i in range(args.frames):
            ox, oy = _chunk_origin(i + _TM_WARMUP)
            t0 = time.perf_counter()
            tilemap.render_region(ox, oy, chunk_px, chunk_px)
            per_chunk.append((time.perf_counter() - t0) * 1000.0)

        # Build the warm cache once (render -> premultiplied QImage) for the blit.
        if warm > 0 and qt_ok:
            for k in range(min(warm, total_chunks)):
                ox, oy = _chunk_origin(k)
                buf = tilemap.render_region(ox, oy, chunk_px, chunk_px)
                arr = buf.data  # (H, W, 4) uint8, RGBA
                img = _QImage(
                    arr.tobytes(),
                    chunk_px,
                    chunk_px,
                    chunk_px * 4,
                    _QImage.Format.Format_RGBA8888,
                ).convertToFormat(_QImage.Format.Format_ARGB32_Premultiplied)
                warm_images.append(img)
            # Tile the (possibly fewer) built images up to `warm` blits/frame.
            vw = min(D_W, grid * chunk_px)
            vh = min(D_H, grid * chunk_px)
            painter_img = _QImage(vw, vh, _QImage.Format.Format_ARGB32_Premultiplied)

        # Timed frames: cold inline renders + warm blits (the GUI-thread slice).
        samples = []
        for i in range(args.frames):
            t0 = time.perf_counter()
            for c in range(cold):
                ox, oy = _chunk_origin((i * max(cold, 1) + c) % max(total_chunks, 1))
                tilemap.render_region(ox, oy, chunk_px, chunk_px)
            if warm > 0 and qt_ok and warm_images:
                p = _QPainter(painter_img)
                np_ = len(warm_images)
                cols = max(1, painter_img.width() // chunk_px)
                for b in range(warm):
                    im = warm_images[b % np_]
                    dx = (b % cols) * chunk_px
                    dy = (b // cols) * chunk_px
                    p.drawImage(dx, dy, im)
                p.end()
            samples.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: tilemap-cache render error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    per_chunk.sort()
    samples.sort()
    pc_median = _percentile(per_chunk, 0.5)
    pc_p95 = _percentile(per_chunk, 0.95)
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    within = median <= budget
    report = {
        "mode": "tilemap-cache",
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "per_chunk_median_ms": round(pc_median, 4),
        "per_chunk_p95_ms": round(pc_p95, 4),
        "budget_ms": budget,
        "within_budget": within,
        "frames": args.frames,
        "warm_blit_measured": bool(warm > 0 and qt_ok),
        "scenario": {
            "tile": tw,
            "chunk_cells": chunk_cells,
            "chunk_px": chunk_px,
            "layers": layers,
            "autotile": bool(args.tm_autotile),
            "cold_chunks_inline": cold,
            "warm_blits": warm,
            "sync_chunk_budget": args.tm_sync_budget,
            "block_chunks": total_chunks,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: tilemap-cache OVER budget (median %.3f ms > %.1f ms).\n"
            % (median, budget)
        )
        return 1
    sys.stderr.write(
        "perf_profile: tilemap-cache within budget (median %.3f ms <= %.1f ms; "
        "per-chunk %.3f ms).\n" % (median, budget, pc_median)
    )
    return 0


# --------------------------------------------------------------------------- #
# Overlay mode (Phase-9 REQ-P9-UI-011) — visual-aids per-frame paint profiler  #
# --------------------------------------------------------------------------- #
# Article VI APPLIES to Phase 9: the iso/perspective/guide overlays, the N
# multi-views, and the real-size preview mirror are on the per-frame render loop.
# This mode times the REAL shipped overlay classes' paint() over a configurable
# exposedRect (the faithful cost paid whenever DeviceCoordinateCache is invalid —
# i.e. a zoom / config change / first paint), and models the dirty-rect per-view
# and preview repaint cost of an active edit. Needs PySide6 (offscreen) -> exit 2
# if absent. Render-perf profiling; the report feeds the UI render directives.
_OV_WARMUP = 2


def _populate_cursors(item, n, ew, eh, with_selection, rect_cls):
    """Seat ``n`` collaborator cursors on a grid inside the exposed rect (worst case).

    All cursors are placed strictly inside ``(0, 0, ew, eh)`` so none are exposedRect-
    culled (the maximum draw). ``item.set_cursor`` caps the roster at
    MAX_SHARED_MEMBERS, so the drawn count is ``min(n, MAX_SHARED_MEMBERS)``. Each
    cursor gets a small selection rect (intersecting the exposed rect) unless
    ``with_selection`` is False, so the selection-fill path is on the critical path too.
    """
    import math

    cols = max(1, int(math.ceil(math.sqrt(max(n, 1)))))
    for i in range(n):
        cxi = i % cols
        cyi = i // cols
        x = (cxi + 0.5) / cols * ew
        y = (cyi + 0.5) / cols * eh
        sel = rect_cls(x, y, 24.0, 24.0) if with_selection else None
        item.set_cursor(f"peer-{i:02d}", x, y, sel)


def _run_overlay(args):
    """Profile the Phase-9 visual-aids paint path vs FRAME_BUDGET_MS (16 ms).

    Kinds:
      iso/perspective/guides -> time the REAL overlay item's ``paint()`` over the
        exposed rect at the given density (the cache-miss / zoom frame cost).
      multiview -> time an active-edit dirty-rect composite blit repeated across
        N views (the shipped MinimalViewportUpdate per-view slice).
      preview   -> the real-size preview dirty-rect mirror blit (scaled).
      combined  -> the worst active-edit frame: dirty-rect x (N views + preview)
        with the overlay caches WARM (config unchanged during an edit -> blits, not
        re-strokes), reported alongside the worst single overlay paint frame.
      cursors   -> time the REAL shipped Live_Cursors_Overlay.paint() (Slice C,
        REQ-P10-UI-013) with ``--ov-cursors`` collaborators (capped at
        MAX_SHARED_MEMBERS) all inside the exposed rect (worst case: nothing culled),
        each with a selection rect unless ``--ov-no-selection``. No item cache — the
        faithful per-frame move-cursor redraw cost.
      cursors-rt -> the COMBINED Slice-C interactive frame: one realtime_apply.
        apply_remote (a remote CRDT patch folded onto the live 8K Document) PLUS the
        live-cursor overlay paint(), timed together vs FRAME_BUDGET_MS (16 ms) — the
        real per-frame cost when a peer edit + a peer cursor land in the same frame.

    Returns 0 (median <= budget), 1 (over budget), 2 (PySide6/construction error).
    """
    budget = args.budget_ms
    if args.frames <= 0:
        sys.stderr.write("perf_profile: invalid frames.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import (
            QApplication,
            QStyleOptionGraphicsItem,
        )
    except Exception as exc:  # PySide6 absent -> BLOCKED, not a crash.
        sys.stderr.write("perf_profile: PySide6 unavailable: %r\n" % exc)
        print(json.dumps({"error": "pyside6-unavailable", "detail": repr(exc)}))
        return 2

    app = QApplication.instance() or QApplication([])  # noqa: F841 (keep alive)

    sw, sh = args.ov_scene
    ew, eh = args.ov_exposed if args.ov_exposed else (sw, sh)
    vw, vh = args.ov_viewport
    # Zoom that fits the exposed rect into the viewport (worst case: full canvas
    # zoomed out -> the densest visible-line count for the iso grid).
    zoom = min(vw / max(ew, 1), vh / max(eh, 1)) if args.ov_zoom <= 0 else args.ov_zoom
    scene_rect = QRectF(0.0, 0.0, float(sw), float(sh))
    exposed_rect = QRectF(0.0, 0.0, float(ew), float(eh))

    def _time_item_paint(item):
        """Time item.paint() over the exposed rect at ``zoom`` into a vw x vh image."""
        img = QImage(vw, vh, QImage.Format.Format_ARGB32_Premultiplied)
        opt = QStyleOptionGraphicsItem()
        opt.exposedRect = exposed_rect
        # Warm-up (JIT / first-paint) excluded.
        for _ in range(_OV_WARMUP):
            p = QPainter(img)
            p.scale(zoom, zoom)
            item.paint(p, opt, None)
            p.end()
        samples = []
        for _ in range(args.frames):
            p = QPainter(img)
            p.scale(zoom, zoom)
            t0 = time.perf_counter()
            item.paint(p, opt, None)
            t1 = time.perf_counter()
            p.end()
            samples.append((t1 - t0) * 1000.0)
        return samples

    kind = args.ov_kind
    extra = {}
    try:
        if kind == "iso":
            from pixelart_creator.logic.grids import IsoGridConfig
            from pixelart_creator.ui.iso_grid_overlay import Iso_Grid_Overlay

            cfg = IsoGridConfig(origin=(0.0, 0.0), tile_width=args.ov_tile, ratio=2.0)
            item = Iso_Grid_Overlay(scene_rect, cfg)
            item.setVisible(True)
            samples = _time_item_paint(item)
            extra = {"tile_width": args.ov_tile}
        elif kind == "perspective":
            from pixelart_creator.logic.grids import (
                PerspectiveConfig,
                VanishingPoint,
            )
            from pixelart_creator.ui.perspective_grid_overlay import (
                Perspective_Grid_Overlay,
            )

            vps = tuple(
                VanishingPoint(position=(sw * (k + 1) / 4.0, sh * 0.4))
                for k in range(min(3, args.ov_vps))
            )
            cfg = PerspectiveConfig(
                mode=min(3, args.ov_vps),
                vanishing_points=vps,
                horizon_y=sh * 0.4,
            )
            item = Perspective_Grid_Overlay(scene_rect, cfg, samples=args.ov_samples)
            item.setVisible(True)
            samples = _time_item_paint(item)
            extra = {"vps": len(vps), "samples": args.ov_samples}
        elif kind == "guides":
            from pixelart_creator.logic.guides import GuideOrientation
            from pixelart_creator.ui.guides_rulers_overlay import Guides_Overlay

            item = Guides_Overlay(scene_rect)
            n = args.ov_guides
            for gi in range(n):
                if gi % 2 == 0:
                    item.add_guide(GuideOrientation.VERTICAL, (gi / n) * sw)
                else:
                    item.add_guide(GuideOrientation.HORIZONTAL, (gi / n) * sh)
            item.setVisible(True)
            samples = _time_item_paint(item)
            # Rulers: the tick-generation cost (the only per-frame logic call) +
            # note the drawText count is nice-number bounded (small).
            from pixelart_creator.logic.guides import ruler_ticks

            t0 = time.perf_counter()
            ticks = ruler_ticks(float(vw), zoom, 0.0, axis_pixels=vw)
            t1 = time.perf_counter()
            extra = {
                "guides": n,
                "ruler_ticks_count": len(ticks),
                "ruler_ticks_ms": round((t1 - t0) * 1000.0, 5),
            }
        elif kind in ("multiview", "preview", "combined"):
            # Model an active-edit dirty-rect composite. MinimalViewportUpdate means
            # each view repaints only the dirty sub-rect (not the full 8K), so cost
            # scales with dirty-rect area x (views + preview), NOT canvas x N.
            dw, dh = args.ov_dirty
            n_views = args.ov_views if kind != "preview" else 0
            has_preview = kind in ("preview", "combined")
            pscale = args.ov_preview_scale
            # A resident buffer sub-region (the dirty rect) as a premultiplied image.
            src = QImage(dw, dh, QImage.Format.Format_ARGB32_Premultiplied)
            src.fill(0x8033AAFF)
            target = QImage(vw, vh, QImage.Format.Format_ARGB32_Premultiplied)

            def _one_frame():
                p = QPainter(target)
                # Primary + N extra views each blit the dirty sub-rect (1:1).
                for _v in range(n_views + 1):
                    p.drawImage(0, 0, src)
                # Preview mirrors the same dirty rect scaled by real_size_scale.
                if has_preview:
                    p.scale(pscale, pscale)
                    p.drawImage(0, 0, src)
                p.end()

            for _ in range(_OV_WARMUP):
                _one_frame()
            samples = []
            for _ in range(args.frames):
                t0 = time.perf_counter()
                _one_frame()
                samples.append((time.perf_counter() - t0) * 1000.0)
            extra = {
                "views": n_views + 1,
                "preview": has_preview,
                "dirty_rect": [dw, dh],
                "preview_scale": pscale,
            }
        elif kind in ("cursors", "cursors-rt"):
            from PySide6.QtCore import QRectF as _QRectF

            from pixelart_creator.ui.live_cursors_overlay import Live_Cursors_Overlay

            n_req = args.ov_cursors
            with_sel = not args.ov_no_selection
            item = Live_Cursors_Overlay(scene_rect)
            _populate_cursors(item, n_req, float(ew), float(eh), with_sel, _QRectF)
            item.setVisible(True)
            n_drawn = item.cursor_count()

            if kind == "cursors":
                samples = _time_item_paint(item)
                extra = {
                    "cursors_requested": n_req,
                    "cursors_drawn": n_drawn,
                    "with_selection": with_sel,
                    "note": "worst case: all cursors inside exposed rect (no cull)",
                }
            else:  # cursors-rt — combined apply_remote + overlay paint frame
                try:
                    from pixelart_creator.logic.constants import CRDT_TILE_SIZE_PX
                    from pixelart_creator.logic.convergence import RasterOp
                    from pixelart_creator.logic.document import Document
                    from pixelart_creator.logic.pixel_buffer import ColorMode
                    from pixelart_creator.logic.realtime_apply import (
                        RealtimeState,
                        apply_remote,
                        encode_update,
                    )
                except Exception as exc:
                    sys.stderr.write("perf_profile: logic unavailable: %r\n" % exc)
                    print(
                        json.dumps({"error": "logic-unavailable", "detail": repr(exc)})
                    )
                    return 2
                tsize = CRDT_TILE_SIZE_PX
                document = Document(sw, sh, mode=ColorMode.RGBA)
                bg_layer_id = document.frames[0].layers[0].layer_id
                tile_bytes = bytes((i * 7 + 11) % 256 for i in range(tsize * tsize * 4))
                blob = encode_update(
                    [
                        RasterOp(
                            frame_index=0,
                            layer_id=bg_layer_id,
                            tile_x=0,
                            tile_y=0,
                            pixels=tile_bytes,
                            tile_width=tsize,
                            tile_height=tsize,
                            logical_clock=1,
                            site_id=0,
                        )
                    ]
                )
                img = QImage(vw, vh, QImage.Format.Format_ARGB32_Premultiplied)
                opt = QStyleOptionGraphicsItem()
                opt.exposedRect = exposed_rect

                def _combined_frame():
                    apply_remote(document, blob, site_id=0, state=RealtimeState())
                    p = QPainter(img)
                    p.scale(zoom, zoom)
                    item.paint(p, opt, None)
                    p.end()

                for _ in range(_OV_WARMUP):
                    _combined_frame()
                samples = []
                for _ in range(args.frames):
                    t0 = time.perf_counter()
                    _combined_frame()
                    samples.append((time.perf_counter() - t0) * 1000.0)
                extra = {
                    "cursors_drawn": n_drawn,
                    "with_selection": with_sel,
                    "apply_tiles": 1,
                    "blob_bytes": len(blob),
                    "note": "combined apply_remote + overlay paint per frame",
                }
        else:
            sys.stderr.write("perf_profile: unknown overlay kind %r.\n" % kind)
            print(json.dumps({"error": "unknown-kind"}))
            return 2
    except Exception as exc:  # construction/paint failure
        sys.stderr.write("perf_profile: overlay error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    within = median <= budget
    report = {
        "mode": "overlay",
        "kind": kind,
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "budget_ms": budget,
        "within_budget": within,
        "frames": args.frames,
        "scenario": {
            "scene": [sw, sh],
            "exposed": [ew, eh],
            "viewport": [vw, vh],
            "zoom": round(zoom, 5),
            **extra,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: overlay[%s] OVER budget (median %.3f ms > %.1f ms).\n"
            % (kind, median, budget)
        )
        return 1
    sys.stderr.write(
        "perf_profile: overlay[%s] within budget (median %.3f ms <= %.1f ms).\n"
        % (kind, median, budget)
    )
    return 0


# --------------------------------------------------------------------------- #
# Realtime mode (Phase-10 Slice C, FLAG-PERFRAME) — Qt-FREE remote-patch apply  #
# --------------------------------------------------------------------------- #
# Article VI RE-ENTERS cloud scope in Slice C (ADR-0027 §7): a remote CRDT patch
# is folded onto the LIVE Document on the interactive loop. This mode times a
# SINGLE realtime_apply.apply_remote(document, blob, site_id=...) call — validate
# + decode (eval-free, Article VII) + LWW stale-drop + dirty-region-scoped
# apply_operations (NO 8K deep copy) — against FRAME_BUDGET_MS (16 ms, S12).
# Qt-FREE: numpy + logic only (NO PySide6), so it runs headless in CI. The blob
# is pre-encoded once (the transport hands the GUI thread bytes); each timed frame
# applies it fresh (default RealtimeState => full work every frame, the faithful
# per-apply cost). Distinct from the composite/tilemap/overlay modes: this
# measures the logic-side remote-patch apply, NOT a render/blit.
_RT_WARMUP = 2


def _run_realtime(args):
    """Profile a single ``realtime_apply.apply_remote`` vs FRAME_BUDGET_MS (Slice C).

    Builds a document at ``args.rt_width`` x ``args.rt_height`` (default 8K) and a
    CRDT-update blob carrying ``args.rt_meta`` metadata ops, ``args.rt_attrs`` layer-
    attr ops, and ``args.rt_tiles`` raster tile ops (``CRDT_TILE_SIZE_PX`` tiles onto
    the background layer). Times ``args.frames`` ``apply_remote`` calls and compares
    the median to ``args.budget_ms`` (16 ms). The pre-encoded blob's byte size is
    reported and rejected if it exceeds ``MAX_CRDT_UPDATE_BYTES`` (the trust cap the
    transport/decoder enforce), so a scenario can never claim an apply the runtime
    would reject at the boundary.

    Returns 0 (median <= budget), 1 (over budget), 2 (construction error).
    """
    budget = args.rt_ceiling_ms
    if args.frames <= 0 or args.rt_width <= 0 or args.rt_height <= 0:
        sys.stderr.write("perf_profile: invalid realtime geometry/frames.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2
    if args.rt_tiles < 0 or args.rt_meta < 0 or args.rt_attrs < 0:
        sys.stderr.write("perf_profile: negative realtime op count.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    # Qt-FREE imports: numpy + logic only (NO PySide6 on this branch).
    try:
        from pixelart_creator.logic.constants import (
            CRDT_TILE_SIZE_PX,
            MAX_CRDT_UPDATE_BYTES,
        )
        from pixelart_creator.logic.convergence import (
            LayerAttrOp,
            MetadataOp,
            RasterOp,
        )
        from pixelart_creator.logic.document import Document
        from pixelart_creator.logic.pixel_buffer import ColorMode
        from pixelart_creator.logic.realtime_apply import (
            RealtimeState,
            apply_remote,
            dirty_regions,
            encode_update,
        )
    except Exception as exc:  # logic unavailable -> construction error, not Qt.
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    indexed = args.rt_mode == "indexed"
    mode = ColorMode.INDEXED if indexed else ColorMode.RGBA
    channels = 1 if indexed else 4
    tsize = CRDT_TILE_SIZE_PX

    try:
        document = Document(args.rt_width, args.rt_height, mode=mode)
        # Background layer minted id 1, frame 0 — the raster apply target.
        bg_layer_id = document.frames[0].layers[0].layer_id

        cols = max(1, args.rt_width // tsize)
        rows = max(1, args.rt_height // tsize)
        if args.rt_tiles > cols * rows:
            sys.stderr.write(
                "perf_profile: rt-tiles %d exceeds the %dx%d tile grid.\n"
                % (args.rt_tiles, cols, rows)
            )
            print(json.dumps({"error": "too-many-tiles"}))
            return 2

        # Deterministic per-tile fill (P2 — no RNG); one full interior tile each.
        tile_bytes = bytes((i * 7 + 11) % 256 for i in range(tsize * tsize * channels))

        ops = []
        for i in range(args.rt_meta):
            ops.append(
                MetadataOp(key=f"k{i}", value=f"v{i}", logical_clock=1, site_id=0)
            )
        for i in range(args.rt_attrs):
            ops.append(
                LayerAttrOp(
                    frame_index=0,
                    layer_id=bg_layer_id,
                    attr="opacity",
                    value=(i % 100) / 100.0,
                    logical_clock=1 + i,
                    site_id=0,
                )
            )
        for i in range(args.rt_tiles):
            tx = i % cols
            ty = i // cols
            ops.append(
                RasterOp(
                    frame_index=0,
                    layer_id=bg_layer_id,
                    tile_x=tx,
                    tile_y=ty,
                    pixels=tile_bytes,
                    tile_width=tsize,
                    tile_height=tsize,
                    logical_clock=1,
                    site_id=0,
                )
            )

        blob = encode_update(ops)
        blob_bytes = len(blob)
        if blob_bytes > MAX_CRDT_UPDATE_BYTES:
            sys.stderr.write(
                "perf_profile: blob %d B exceeds MAX_CRDT_UPDATE_BYTES %d B — the "
                "transport/decoder would reject this at the trust boundary.\n"
                % (blob_bytes, MAX_CRDT_UPDATE_BYTES)
            )
            print(json.dumps({"error": "blob-over-cap", "blob_bytes": blob_bytes}))
            return 2
        n_regions = len(dirty_regions(blob))
    except Exception as exc:
        sys.stderr.write("perf_profile: realtime construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    try:
        # Warm-up (JIT / pycrdt-init / first-call) excluded, matching the tiler.
        for _ in range(_RT_WARMUP):
            apply_remote(document, blob, site_id=0, state=RealtimeState())
        samples = []
        for _ in range(args.frames):
            t0 = time.perf_counter()
            # Fresh state => the full patch applies every frame (faithful single-
            # apply cost); a persistent-state session does the same accept() work.
            apply_remote(document, blob, site_id=0, state=RealtimeState())
            samples.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: realtime apply error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    worst = samples[-1] if samples else 0.0
    within = median <= budget
    report = {
        "mode": "realtime",
        "median_ms": round(median, 4),
        "p95_ms": round(p95, 4),
        "worst_ms": round(worst, 4),
        "budget_ms": budget,
        "frame_budget_ms": args.frame_budget_ms,
        "within_budget": within,
        "frames": args.frames,
        "blob_bytes": blob_bytes,
        "max_update_bytes": MAX_CRDT_UPDATE_BYTES,
        "dirty_regions": n_regions,
        "scenario": {
            "doc": [args.rt_width, args.rt_height],
            "mode": args.rt_mode,
            "tiles": args.rt_tiles,
            "meta_ops": args.rt_meta,
            "attr_ops": args.rt_attrs,
            "crdt_tile_px": tsize,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not within:
        sys.stderr.write(
            "perf_profile: realtime OVER budget (median %.3f ms > %.1f ms).\n"
            % (median, budget)
        )
        return 1
    sys.stderr.write(
        "perf_profile: realtime within budget (median %.3f ms <= %.1f ms; "
        "p95 %.3f ms; blob %d B; %d dirty regions).\n"
        % (median, budget, p95, blob_bytes, n_regions)
    )
    return 0


# --------------------------------------------------------------------------- #
# Viewport-recomposite mode (Slice B, FU-16b / ADR-0034 §4) — Qt-FREE opacity-  #
# drag COMMIT gate over the culled viewport                                     #
# --------------------------------------------------------------------------- #
# Times the SHIPPED byte-exact opacity-drag COMMIT — NOT the naive full
# recomposite — the path ui/canvas_scene._commit_opacity_drag runs on slider
# release (ADR-0034 §3, amendment 2026-07-07):
#     below_full = composite_range(nodes, 0, k, region=V)
#     result     = composite_range(nodes, k, N, region=V, base=below_full.data)
# i.e. the exact suffix re-blend over the cached ``below`` prefix, which is
# byte-identical to composite_stack(region=V) for NORMAL and all 11 separable
# modes (verified inline via the ``byte_exact`` report field). Qt-FREE: numpy +
# pixelart_creator.logic only, NO PySide6.
#
# Content models (mirroring the Slice-A --full-frame realistic/dense split):
#   * realistic (the GATE): a finished pixel-art viewport — one full OPAQUE
#     background + full-cover OPAQUE NORMAL fills (uint8 ``acc = src.copy()``
#     fast path over V) + content-OUTSIDE-V layers (alpha-0 over V -> skipped
#     byte-exactly) + a MINORITY (``--vp-nonnormal``, default 1) of non-normal
#     separable layers PRESENT over V (the one/few float32 passes). This is the
#     honest fast-path-dominant realistic commit; it clears VIEWPORT_RECOMPOSITE
#     _CEILING_MS with comfortable 2-core margin (measured ~0.6 s @ 1920² / 12
#     layers on 8-core -> ~1.3-1.6 s on 2-core, vs the 3000 ms ceiling), yet a
#     regression that reverts the split-cache/fast-path to the naive all-float
#     recomposite balloons to ~6-7 s (8-core) / ~14-17 s (2-core) and TRIPS it.
#     NOTE (why the region path is content-sensitive): the region commit is a
#     SINGLE-SHOT composite (NOT tile-fanned like --full-frame), so a layer that
#     only PARTIALLY covers V takes the float path over the whole region -> such
#     content is the pathological witness, not the gate config.
#   * mixed (record, NOT gated): every layer full-cover partial-alpha + a
#     non-normal separable mode -> every layer hits the float32 path (the
#     catastrophe the split-cache avoids). Profiled with --vp-content mixed for
#     the record; it is deliberately NOT the CI gate config.
_VP_WARMUP = 2


def _run_viewport_recomposite(args):
    """Run the Slice-B opacity-drag split-cache COMMIT perf gate (Qt-free).

    Builds ``args.vp_layers`` full-canvas RGBA leaves per ``--vp-content``, picks
    a mid-stack dragged index ``k`` (``--vp-index``, default ``layers // 2``), and
    times ``args.frames`` byte-exact commits — ``below = composite_range(0, k)``
    then ``composite_range(k, N, base=below)`` — over a square viewport region of
    edge ``args.vp_region_size``. Verifies the commit is byte-identical to
    ``composite_stack(region=V)`` (the ADR-0034 invariant) and compares the median
    to ``args.ceiling_ms`` (the loose ``VIEWPORT_RECOMPOSITE_CEILING_MS``, NOT 16 ms).

    Returns 0 (median <= ceiling), 1 (over ceiling), 2 (construction/geometry/
    byte-exactness error).
    """
    width, height = args.width, args.height
    layers = args.vp_layers
    rsize = args.vp_region_size
    nonnormal = args.vp_nonnormal
    ceiling = args.ceiling_ms
    content = args.vp_content
    k = args.vp_index if args.vp_index is not None else layers // 2

    if layers < 1 or rsize < 1 or width <= 0 or height <= 0 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid viewport-recomposite geometry.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2
    if rsize > width or rsize > height:
        sys.stderr.write("perf_profile: region-size exceeds canvas.\n")
        print(json.dumps({"error": "region-larger-than-canvas"}))
        return 2
    if not (0 <= k < layers) or nonnormal < 0 or nonnormal > layers:
        sys.stderr.write("perf_profile: invalid vp-index/vp-nonnormal.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    # Qt-FREE imports: numpy + logic only (NO PySide6 on this branch).
    try:
        from pixelart_creator.logic.blend import (
            BlendMode,
            composite_range,
            composite_stack,
        )
        from pixelart_creator.logic.pixel_buffer import ColorMode, PixelBuffer
    except Exception as exc:  # logic unavailable -> construction error, not Qt.
        sys.stderr.write("perf_profile: logic package unavailable: %r\n" % exc)
        print(json.dumps({"error": "logic-unavailable", "detail": repr(exc)}))
        return 2

    # Fixed viewport origin (deterministic); centred-ish, in bounds.
    vx = min(max(0, (width - rsize) // 2), width - rsize)
    vy = min(max(0, (height - rsize) // 2), height - rsize)
    region = (vx, vy, rsize, rsize)
    non_modes = [BlendMode.MULTIPLY, BlendMode.SCREEN, BlendMode.OVERLAY]
    mixed_cycle = [
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
            base = (
                (i * 40 + 20) % 256,
                (i * 70 + 30) % 256,
                (i * 110 + 60) % 256,
            )
            if content == "mixed":
                # Pathological witness: every layer full-cover partial-alpha +
                # a non-normal mode -> every layer takes the float32 path.
                buffer = PixelBuffer(
                    width, height, ColorMode.RGBA, fill=(base[0], base[1], base[2], 180)
                )
                mode = mixed_cycle[i % len(mixed_cycle)]
            elif i >= layers - nonnormal:
                # Realistic minority: a non-normal separable layer PRESENT over V
                # (fully covering) — the one/few unavoidable float32 passes. Placed
                # in the suffix (i >= k) so it exercises the suffix re-blend.
                buffer = PixelBuffer(
                    width, height, ColorMode.RGBA, fill=(base[0], base[1], base[2], 200)
                )
                mode = non_modes[i % len(non_modes)]
            elif i == 0 or i % 2 == 0:
                # Full-cover OPAQUE NORMAL fill -> uint8 ``acc = src.copy()`` over V.
                buffer = PixelBuffer(
                    width, height, ColorMode.RGBA, fill=(base[0], base[1], base[2], 255)
                )
                mode = BlendMode.NORMAL
            else:
                # OPAQUE content placed OUTSIDE V -> transparent over V -> skipped
                # byte-exactly (the ``clear`` fast path). Deterministic band origin.
                buffer = PixelBuffer(width, height, ColorMode.RGBA)  # transparent
                oy = (vy + rsize + 200 + i * 50) % max(1, height - 300)
                buffer.data[oy : oy + 100, :] = (base[0], base[1], base[2], 255)
                mode = BlendMode.NORMAL
            nodes.append(_Leaf(buffer, mode))
            blend_modes.append(mode.value)
    except Exception as exc:
        sys.stderr.write(
            "perf_profile: viewport-recomposite construction error: %r\n" % exc
        )
        print(json.dumps({"error": repr(exc)}))
        return 2

    def _commit():
        # The shipped byte-exact commit (ui/canvas_scene._commit_opacity_drag).
        below_full = composite_range(nodes, width, height, 0, k, region=region)
        return composite_range(
            nodes, width, height, k, layers, region=region, base=below_full.data
        )

    try:
        # Byte-exactness guard: the commit MUST equal composite_stack over V
        # (ADR-0034 §3). A gate that passed on a wrong result would be worthless.
        committed = _commit()
        reference = composite_stack(nodes, width, height, region=region)
        import numpy as _np

        byte_exact = bool(_np.array_equal(committed.data, reference.data))
        if not byte_exact:
            sys.stderr.write(
                "perf_profile: viewport-recomposite commit is NOT byte-exact vs "
                "composite_stack — ADR-0034 §3 invariant violated.\n"
            )
            print(json.dumps({"error": "not-byte-exact"}))
            return 2

        for _ in range(_VP_WARMUP):
            _commit()
        samples = []
        for _ in range(args.frames):
            t0 = time.perf_counter()
            _commit()
            samples.append((time.perf_counter() - t0) * 1000.0)
    except Exception as exc:
        sys.stderr.write("perf_profile: viewport-recomposite commit error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    samples.sort()
    median = _percentile(samples, 0.5)
    p95 = _percentile(samples, 0.95)
    # Only the realistic content model gates in CI; mixed is profiled for record.
    gated = content != "mixed"
    within = (median <= ceiling) if gated else True
    report = {
        "mode": "viewport-recomposite",
        "content": content,
        "gated": gated,
        "byte_exact": byte_exact,
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
            "drag_index": k,
            "region": list(region),
            "region_size": rsize,
            "nonnormal_over_v": (layers if content == "mixed" else nonnormal),
            "blend_modes": blend_modes,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not gated:
        sys.stderr.write(
            "perf_profile: viewport-recomposite[mixed] median %.1f ms — pathological "
            "witness, NOT gated against the ceiling (record only).\n" % median
        )
        return 0
    if not within:
        sys.stderr.write(
            "perf_profile: viewport-recomposite OVER ceiling (median %.1f ms > %.1f "
            "ms) — FU-16b split-cache commit regression.\n" % (median, ceiling)
        )
        return 1
    sys.stderr.write(
        "perf_profile: viewport-recomposite within ceiling (median %.1f ms <= %.1f "
        "ms; byte-exact; %d layers, %d non-normal over V).\n"
        % (median, ceiling, layers, nonnormal)
    )
    return 0


# --------------------------------------------------------------------------- #
# Tiling mode (default; REQ-P1-UI-023, D-32) — the REAL CanvasScene.drawBackground #
# --------------------------------------------------------------------------- #
# Drives ui.canvas_scene.CanvasScene.drawBackground directly instead of a
# parallel re-implementation of its checker loop (D-32 — the audit's CF-06
# finding, "imports no product UI module", is the defect this fixes).
# --width/--height now build a real Document of that geometry and are LIVE:
# the exposed rect this function passes to drawBackground is intersected with
# the real scene's own sceneRect (0, 0, W, H) — exactly what a QGraphicsView
# does (it never asks the scene to paint background outside its own bounds) —
# so a narrow/short document measurably shrinks tiles_per_frame relative to an
# 8K one. CF-06's repro (7680x4320 and 64x64 both reporting 510 tiles/frame)
# must no longer reproduce after this change. Tile geometry for the REPORTED
# tiles_per_frame count is read from the same logic.constants.TILE_SIZE /
# TILE_BUFFER the shipped drawBackground itself consumes (Article II single
# source) and computed with the identical formula _paint_checker_tiles uses —
# a read-only count for the record, not a second render pass. --tile is kept
# for CLI-contract compatibility (existing callers/tests pass it) but no
# longer drives real tiling since the shipped scene reads TILE_SIZE directly;
# a mismatched --tile is noted on stderr, never silently honoured.
_TILING_WARMUP = 1  # pays CanvasScene's deferred first-composite once (D1 guard)


def _tile_count(rect, tile_size, tile_buffer):
    """Count the checker cells the real ``_paint_checker_tiles`` would fill.

    Same formula, same constants (``TILE_SIZE``/``TILE_BUFFER``) the shipped
    ``CanvasScene`` uses — a read-only report of what the real call just did,
    not a parallel render (D-32).
    """
    left = math.floor(rect.left() / tile_size) - tile_buffer
    top = math.floor(rect.top() / tile_size) - tile_buffer
    right = math.ceil(rect.right() / tile_size) + tile_buffer
    bottom = math.ceil(rect.bottom() / tile_size) + tile_buffer
    return max(0, bottom - top) * max(0, right - left)


def _run_tiling(args):
    """Profile the REAL ``CanvasScene.drawBackground`` vs ``FRAME_BUDGET_MS`` (D-32).

    Builds a real ``Document``/``CanvasScene`` at ``args.width`` x
    ``args.height`` and times ``args.frames`` ``drawBackground`` calls over an
    exposed rect sized by ``args.viewport``/``args.zoom`` and panned a little
    each frame (dirty-rect realism), clamped to the scene's own ``sceneRect``
    (the live width/height effect, D-32). Compares the median to
    ``args.budget_ms`` (``FRAME_BUDGET_MS`` by default, S12, unrelaxed Tier-1).

    Returns 0 (median <= budget), 1 (over budget), 2 (PySide6/construction
    error).
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # PySide6 not installed -> BLOCKED, not a crash.
        sys.stderr.write("perf_profile: PySide6 unavailable: %r\n" % exc)
        print(json.dumps({"error": "pyside6-unavailable", "detail": repr(exc)}))
        return 2

    try:
        from pixelart_creator.logic.constants import TILE_BUFFER, TILE_SIZE
        from pixelart_creator.logic.document import Document
        from pixelart_creator.ui.canvas_scene import CanvasScene
    except Exception as exc:  # product UI/logic unavailable -> construction error.
        sys.stderr.write("perf_profile: CanvasScene unavailable: %r\n" % exc)
        print(json.dumps({"error": "canvas-scene-unavailable", "detail": repr(exc)}))
        return 2

    if args.tile != TILE_SIZE:
        sys.stderr.write(
            "perf_profile: --tile %d is IGNORED by the real CanvasScene -- "
            "TILE_SIZE (%d, logic.constants) is single-sourced and drives the "
            "shipped drawBackground (Article II); --tile is retained only for "
            "CLI-contract compatibility.\n" % (args.tile, TILE_SIZE)
        )

    app = QApplication.instance() or QApplication([])  # noqa: F841 (keep alive)

    vw, vh = args.viewport
    # Exposed scene rect at this zoom (what a QGraphicsView would pass in).
    scene_w = vw / max(args.zoom, 1e-6)
    scene_h = vh / max(args.zoom, 1e-6)

    try:
        document = Document(args.width, args.height)
        scene = CanvasScene(document)
    except Exception as exc:
        sys.stderr.write("perf_profile: CanvasScene construction error: %r\n" % exc)
        print(json.dumps({"error": repr(exc)}))
        return 2

    scene_rect = scene.sceneRect()  # D3: fixed once at init from the document

    try:
        img = QImage(vw, vh, QImage.Format.Format_ARGB32_Premultiplied)
        samples = []
        tiles_per_frame = 0
        # Warm-up: pays CanvasScene's deferred first full composite (D1 guard)
        # once, plus any Qt JIT/first-paint cost, excluded from the timed sample.
        for _ in range(_TILING_WARMUP):
            painter = QPainter(img)
            if args.zoom != 1.0:
                painter.scale(args.zoom, args.zoom)
            warm_rect = QRectF(0.0, 0.0, scene_w, scene_h).intersected(scene_rect)
            scene.drawBackground(painter, warm_rect)
            painter.end()
        for i in range(args.frames):
            offset = (i % 8) * TILE_SIZE  # pan a little each frame (dirty-rect realism)
            rect = QRectF(offset, offset, scene_w, scene_h).intersected(scene_rect)
            tiles_per_frame = _tile_count(rect, TILE_SIZE, TILE_BUFFER)
            painter = QPainter(img)
            if args.zoom != 1.0:
                painter.scale(args.zoom, args.zoom)
            t0 = time.perf_counter()
            scene.drawBackground(painter, rect)
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
            "tile": TILE_SIZE,
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
    # --- Slice-A full-frame mode (Qt-free cold full-canvas flatten gate) ------
    ap.add_argument(
        "--full-frame",
        action="store_true",
        help="run the Slice-A cold full-frame flatten gate "
        "(composite_stack(region=None), Qt-free)",
    )
    ap.add_argument(
        "--content",
        choices=["realistic", "dense"],
        default="realistic",
        help="full-frame content model: realistic (sparse, mostly NORMAL — the "
        "GATE) or dense (pathological worst case — profiled, NOT gated)",
    )
    ap.add_argument(
        "--ff-coverage",
        type=float,
        default=0.6,
        help="realistic content: fraction of canvas height painted per layer "
        "(the rest is transparent, whole tiles skipped byte-exactly)",
    )
    ap.add_argument(
        "--ff-nonnormal",
        type=int,
        default=1,
        help="realistic content: how many of the layers take a non-normal "
        "separable blend mode (the minority; the rest are NORMAL)",
    )
    # --- Slice-B viewport-recomposite mode (opacity-drag split-cache COMMIT) --
    ap.add_argument(
        "--viewport-recomposite",
        action="store_true",
        help="run the Slice-B opacity-drag split-cache COMMIT gate "
        "(composite_range suffix re-blend, Qt-free) vs "
        "VIEWPORT_RECOMPOSITE_CEILING_MS",
    )
    ap.add_argument("--vp-layers", type=int, default=D_VP_LAYERS)
    ap.add_argument(
        "--vp-region-size",
        type=int,
        default=D_VP_REGION_SIZE,
        help="square culled-viewport edge in px (default 1920 — worst Slice-B V)",
    )
    ap.add_argument(
        "--vp-index",
        type=int,
        default=None,
        help="dragged layer index k (default: layers // 2, mid-stack)",
    )
    ap.add_argument(
        "--vp-nonnormal",
        type=int,
        default=D_VP_NONNORMAL,
        help="realistic content: non-normal separable layers PRESENT over V "
        "(the float32 minority; the rest are fast-path copies/skips)",
    )
    ap.add_argument(
        "--vp-content",
        choices=["realistic", "mixed"],
        default="realistic",
        help="viewport-recomposite content: realistic (fast-path-dominant — the "
        "GATE) or mixed (every-layer float32 pathological witness — NOT gated)",
    )
    # --- DEP-3 tilemap mode (Qt-free render_region frame-budget profiler) ----
    ap.add_argument(
        "--tilemap",
        action="store_true",
        help="profile logic/tilemap.render_region vs FRAME_BUDGET_MS (Qt-free)",
    )
    ap.add_argument(
        "--tm-region",
        type=int,
        nargs=2,
        default=[D_W, D_H],
        metavar=("W", "H"),
        help="render-region size in pixels (default: full 8K)",
    )
    ap.add_argument("--tm-tile", type=int, default=D_TM_TILE)
    ap.add_argument("--tm-layers", type=int, default=D_TM_LAYERS)
    ap.add_argument("--tm-autotile", action="store_true")
    # --- DEP-3 loop-back tilemap-CACHE mode (cache-in-place per-frame slice) --
    ap.add_argument(
        "--tm-cache",
        action="store_true",
        help="profile the cache-in-place per-frame GUI slice (cold renders + blits)",
    )
    ap.add_argument(
        "--tm-cold",
        type=int,
        default=8,
        help="cold chunks rendered inline per frame (GUI slice; <= sync budget)",
    )
    ap.add_argument(
        "--tm-warm",
        type=int,
        default=0,
        help="cached-chunk pixmap blits per frame (Qt, guarded)",
    )
    ap.add_argument("--tm-sync-budget", type=int, default=8)
    # --- Phase-9 overlay mode (visual-aids per-frame paint profiler) ---------
    ap.add_argument(
        "--overlay",
        action="store_true",
        help="profile the Phase-9 visual-aids paint path vs FRAME_BUDGET_MS",
    )
    ap.add_argument(
        "--ov-kind",
        choices=[
            "iso",
            "perspective",
            "guides",
            "multiview",
            "preview",
            "combined",
            "cursors",
            "cursors-rt",
        ],
        default="iso",
    )
    ap.add_argument("--ov-scene", type=int, nargs=2, default=[D_W, D_H])
    ap.add_argument(
        "--ov-exposed",
        type=int,
        nargs=2,
        default=None,
        help="exposed rect px (default: full scene = worst case)",
    )
    ap.add_argument("--ov-viewport", type=int, nargs=2, default=[1920, 1080])
    ap.add_argument(
        "--ov-zoom",
        type=float,
        default=0.0,
        help="paint zoom; <=0 => fit exposed rect into viewport",
    )
    ap.add_argument("--ov-tile", type=int, default=2, help="iso tile_width (px)")
    ap.add_argument("--ov-samples", type=int, default=12)
    ap.add_argument("--ov-vps", type=int, default=3)
    ap.add_argument("--ov-guides", type=int, default=256)
    ap.add_argument("--ov-views", type=int, default=7)
    ap.add_argument("--ov-dirty", type=int, nargs=2, default=[64, 64])
    ap.add_argument("--ov-preview-scale", type=float, default=1.389)
    ap.add_argument(
        "--ov-cursors",
        type=int,
        default=D_MAX_CURSORS,
        help="live-cursor count for --ov-kind cursors / cursors-rt "
        "(capped at MAX_SHARED_MEMBERS by the overlay)",
    )
    ap.add_argument(
        "--ov-no-selection",
        action="store_true",
        help="cursors kind: draw crosshair+label only (no selection rect fill)",
    )
    # --- Phase-10 Slice C realtime mode (FLAG-PERFRAME apply profiler) --------
    ap.add_argument(
        "--realtime",
        action="store_true",
        help="profile realtime_apply.apply_remote vs FRAME_BUDGET_MS (Qt-free)",
    )
    ap.add_argument("--rt-width", type=int, default=D_W)
    ap.add_argument("--rt-height", type=int, default=D_H)
    ap.add_argument(
        "--rt-tiles", type=int, default=1, help="raster tile ops in the update"
    )
    ap.add_argument("--rt-meta", type=int, default=0, help="metadata ops in the update")
    ap.add_argument(
        "--rt-attrs", type=int, default=0, help="layer-attr ops in the update"
    )
    ap.add_argument("--rt-mode", choices=["rgba", "indexed"], default="rgba")
    ap.add_argument(
        "--rt-ceiling-ms",
        type=float,
        default=D_RT_CEILING,
        help="realtime apply sub-frame ceiling ms (default REALTIME_APPLY_CEILING_MS)",
    )
    args = ap.parse_args()

    if args.realtime:
        return _run_realtime(args)
    if args.overlay:
        return _run_overlay(args)
    if args.full_frame:
        # --ceiling-ms shares the composite-region default (D_CEILING); when the
        # caller does not override it for the full-frame gate, resolve to the
        # full-frame loose ceiling COMPOSITE_FULL_CEILING_MS (D_FULL_CEILING).
        if args.ceiling_ms == D_CEILING:
            args.ceiling_ms = D_FULL_CEILING
        return _run_full_frame(args)
    if args.viewport_recomposite:
        # --ceiling-ms shares the composite-region default (D_CEILING); when the
        # caller does not override it, resolve to the Slice-B loose ceiling
        # VIEWPORT_RECOMPOSITE_CEILING_MS (D_VP_CEILING) — single-source (S12), so
        # the CI step needs no literal: `--viewport-recomposite` alone gates
        # against the constant.
        if args.ceiling_ms == D_CEILING:
            args.ceiling_ms = D_VP_CEILING
        return _run_viewport_recomposite(args)
    if args.composite:
        return _run_composite(args)
    if args.tm_cache:
        return _run_tilemap_cache(args)
    if args.tilemap:
        return _run_tilemap(args)

    if min(args.width, args.height, args.tile) <= 0 or args.frames <= 0:
        sys.stderr.write("perf_profile: invalid geometry/frames.\n")
        print(json.dumps({"error": "invalid-input"}))
        return 2

    return _run_tiling(args)


if __name__ == "__main__":
    sys.exit(main())
