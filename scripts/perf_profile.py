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

# Tilemap-mode defaults (AGT-10 DEP-3 Phase-6 render-seam profiling). Qt-FREE:
# times logic/tilemap.render_region — the single tunable call the tilemap
# drawBackground seam issues per exposed rect (AGT-05 report, DEP-3). Distinct
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
    rect (AGT-05 render-seam report). Qt-FREE: numpy + logic only, so it runs in
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
# (AGT-05 tilemap_canvas._draw_map), NOT a cold full re-render. The GUI-thread
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
# if absent. AGT-10 render-perf profiling; the report feeds AGT-05 directives.
_OV_WARMUP = 2


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
        choices=["iso", "perspective", "guides", "multiview", "preview", "combined"],
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
    args = ap.parse_args()

    if args.overlay:
        return _run_overlay(args)
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
