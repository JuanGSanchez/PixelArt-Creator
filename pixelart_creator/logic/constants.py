"""Centralised numeric parameters (S12). No magic numbers elsewhere.

Every numeric tuning value used across ui/, logic/, and data/ is defined here
and imported by name, so a change is made in exactly one place (S12, Dossier §1).
"""

from typing import Tuple

MAX_CANVAS_WIDTH = 7680  # 8K UHD width  (S1, F7)
MAX_CANVAS_HEIGHT = 4320  # 8K UHD height (S1, F7)
TILE_SIZE = 64  # viewport tile-culling tile edge, px (S1)
TILE_BUFFER = 1  # extra tile ring drawn around the exposed viewport
PARALLAX_FACTOR = 30.0  # background parallax divisor
SCALE_FACTOR = 0.15  # zoom step factor
FPS_TARGET = 60  # target frames per second (S12)
FRAME_BUDGET_MS = 16  # per-frame render budget, ms (1000/FPS_TARGET, S12)
MAX_PALETTE_SIZE = 256  # indexed-palette entry cap (8-bit index space) (S12-1)
DEFAULT_FRAME_DURATION_MS = 100  # default animation frame duration, ms (S12-2)
PROJECT_ZLIB_LEVEL = 9  # .pixproj pixel-data compression level (S12-6)

# --- UI canvas tuning (phase-1-ui-canvas T1; Article II single-source) ---------
# Pure-Python numerics consumed by the ui/ layer; defined here so the UI inlines
# no magic numbers. Zero Qt (this stays a leaf module).

GRID_MIN_PIXEL_EDGE_PX: int = 8
"""Per-pixel grid overlay is drawn only when a pixel's on-screen edge is at
least this many device px (render-strategy §10; CL-4)."""

ISO_GRID_MIN_ON_SCREEN_EDGE_PX: int = 32
"""Isometric analogue of :data:`GRID_MIN_PIXEL_EDGE_PX`: the LOD threshold for
the isometric grid overlay. When a tile's on-screen edge (``tile_width * zoom``)
falls below this many device px, the iso grid overlay skips painting — preventing
the 722 ms fine-grid zoom-out blowup AGT-10 measured. Larger than the per-pixel
grid floor (=8) because an iso tile carries far more overlay geometry per cell
(AGT-10 overlay-perf directive; DIR-1)."""

OPENGL_VIEWPORT_ENABLED: bool = True
"""Use a QOpenGLWidget viewport for the canvas; raster fallback applies when
OpenGL is unavailable/headless (render-strategy §10; D6)."""

ZOOM_MAX: float = 64.0
"""Deep-zoom ceiling as a scale factor (6400 %); fit-to-view lower bound is
computed, not a literal (CL-1)."""

ZOOM_MIN: float = 1.0
"""ZOOM_MIN is the floor for a document small enough that zooming below 1:1
is pointless. It is NOT an absolute floor. The view's lower clamp is
`min(ZOOM_MIN, fit_zoom)` so that a very large document (up to the 8K
canvas) can always be zoomed out far enough to show the whole grid, which a
flat 1.0 floor would make unreachable. User ruling, 2026-08-24."""

ZOOM_PRESET_STOPS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
"""Discrete keyboard zoom preset stops, 100 %..6400 % (CL-2). The geometric
zoom step reuses SCALE_FACTOR as `1.0 + SCALE_FACTOR` (BF-3)."""

CANVAS_PANE_WIDTH_RATIO: float = 0.80
"""Fraction of the main window's width the central canvas pane occupies at
first launch, with the remainder going to the right-hand docks. Applies only
to the first-launch default layout; it does not override a restored user
arrangement."""

DEFAULT_CANVAS_WIDTH: int = 64
"""Default width, px, for a new document (8K still supported) (CL-7)."""

DEFAULT_CANVAS_HEIGHT: int = 64
"""Default height, px, for a new document (8K still supported) (CL-7)."""

# --- Phase-2 advanced-drawing tuning (phase-2 T1; Article II single-source) -----
# Numeric parameters consumed by the new logic/ modules (selection, transform,
# rotsprite, tiled). Defined here so no call site inlines a magic number (S12).
# This module stays a leaf (no intra-package imports).

ROTSPRITE_UPSCALE_FACTOR: int = 8
"""RotSprite upscale factor = three similarity-Scale2x passes (2x2x2 = 8x)
(ROADMAP Phase 2; research Topic 1; ADR-0002; SC-L013-5)."""

ROTSPRITE_SIMILARITY_THRESHOLD: int = 100
"""Scale2x "similar, not equal" test: two pixels are similar when
``color.distance_sq(a, b) <= ROTSPRITE_SIMILARITY_THRESHOLD`` (squared-RGBA units,
the same metric as flood_fill / magic-wand). Sqrt(100) = 10 ~ a modest per-channel
delta (ADR-0002 pin #1; plan §5)."""

MAGIC_WAND_DEFAULT_TOLERANCE: int = 0
"""Default magic-wand colour tolerance: exact match, parity with flood_fill /
Aseprite (CL-1; plan §8)."""

TILED_PREVIEW_REPEAT: int = 3
"""Tiled-mode repeating preview arrangement: TILED_PREVIEW_REPEAT x
TILED_PREVIEW_REPEAT tiles (3x3, centre tile editable) (CL-13; plan §8)."""

SCALE_MIN_FACTOR: float = 0.01
"""Lower bound on the nearest-neighbour scale factor (guards pathological
near-zero factors below the MAX_CANVAS_* hard bound) (plan §8, PL-D5)."""

SCALE_MAX_FACTOR: float = 64.0
"""Upper bound on the nearest-neighbour scale factor; the hard pixel ceiling
remains MAX_CANVAS_WIDTH / MAX_CANVAS_HEIGHT (plan §8, PL-D5)."""

# --- Phase-3 colour & palette tuning (phase-3 T1; Article II single-source) -----
# Tuning scalars consumed by the new logic/ colour modules. The ΔE00 formula
# magic numbers, sRGB/Lab constants, Bayer matrix values, and Floyd–Steinberg
# coefficients are intrinsic → local to their module (plan §5, ADR-0001); the
# NES/GB palette tables are module-local data in hardware_palette.py (ADR-0003).
# This module stays a leaf (no intra-package imports).

HARMONY_COMPLEMENTARY_DEG: int = 180
"""Hue rotation for the complementary harmony, degrees
(research F9 Topic 1.1; spec REQ-P3-LOGIC-002; SC-L002-1)."""

HARMONY_ANALOGOUS_DEG: int = 30
"""Hue offset (±) for the analogous harmony neighbours, degrees
(research F9 Topic 1.1; spec REQ-P3-LOGIC-002; SC-L002-2)."""

HARMONY_TRIADIC_DEG: int = 120
"""Hue offset (±) for the triadic harmony, degrees
(research F9 Topic 1.1; spec REQ-P3-LOGIC-002; SC-L002-3)."""

HARMONY_SPLIT_COMPLEMENTARY_DEG: int = 150
"""Hue offset (±) for the split-complementary harmony, degrees
(research F9 Topic 1.1; spec REQ-P3-LOGIC-002; SC-L002-4)."""

RAMP_STEP_COUNT: int = 5
"""Number of steps in a shade/tint/tone ramp (Aseprite ramp norm; odd count
keeps the base centred) (plan §8; spec REQ-P3-LOGIC-003; SC-L003-1)."""

BAYER_MATRIX_SIZE: int = 4
"""Default ordered-dither Bayer matrix edge (4×4). The matrix *values* are
intrinsic-local to dither.py (research F9 Topic 5.1; SC-L006-2)."""

PALETTE_EXTRACT_DEFAULT_N: int = 16
"""Default auto-extract colour count (common 4-bit palette default)
(plan §8; spec REQ-P3-LOGIC-010; SC-L010-2)."""

CIEDE2000_KL: float = 1.0
"""ΔE00 parametric lightness weight k_L (Sharma et al. 2005; SC-L004-4)."""

CIEDE2000_KC: float = 1.0
"""ΔE00 parametric chroma weight k_C (Sharma et al. 2005; SC-L004-4)."""

CIEDE2000_KH: float = 1.0
"""ΔE00 parametric hue weight k_H (Sharma et al. 2005; SC-L004-4)."""

KMEANS_SEED: int = 0
"""Deterministic k-means RNG seed for reproducible extraction
(P2; research F9 Topic 3.2; spec REQ-P3-LOGIC-011; CL-8)."""

CYCLE_DEFAULT_FPS: int = 10
"""Default colour-cycling preview rate, frames per second (UI-driven; a numeric
value lives here per Article II) (plan §8; spec REQ-P3-UI-012)."""

FAVOURITES_MAX: int = 64
"""Soft cap on the persisted Favourites list (defensive bound, Article VII; suits
a hub swatch grid) (plan §8; spec REQ-P3-LOGIC-015)."""

# --- Phase-4 layer & canvas tuning (phase-4 T1; Article II single-source) --------
# Tuning scalars consumed by the new logic/blend.py compositor and the extended
# logic/document.py layer model. The 13-member BlendMode enum is an enumerated
# *vocabulary* and lives in logic/blend.py (BF-2); the W3C blend-formula magic
# numbers (/255, 0.5, 0.25, the 16/12/4 Horner cubic coefficients, 2*Cs factors)
# are *intrinsic* to the algorithm and stay module-local in blend.py (ADR-0001,
# ADR-0005) — none go here. This module stays a leaf (no intra-package imports).

DEFAULT_LAYER_OPACITY: float = 1.0
"""Opacity a new layer / group starts at, in ``0.0..1.0`` (CL-2; matches the
shipped ``Layer(opacity=1.0)``) (plan §8; spec REQ-P4-LOGIC-015; SC-L015-2)."""

MAX_LAYERS_PER_FRAME: int = 256
"""Defensive cap on the number of layer leaves in a single frame (Article VII;
CL-7 — generous for hand-drawn pixel art) (plan §8; spec REQ-P4-LOGIC-015;
SC-L015-1)."""

MAX_GROUP_NESTING_DEPTH: int = 8
"""Defensive cap on layer-group nesting depth (Article VII; CL-6 — generous for
pixel-art work) (plan §8; spec REQ-P4-LOGIC-011/015; SC-L011-3)."""

# --- FU-15 compositor performance-gate tuning (Article II single-source) ---------
# Ceiling for the region-recomposite CI perf gate. Consumed by
# scripts/perf_profile.py --composite and .github/workflows/ci.yml.

COMPOSITE_REGION_CEILING_MS: int = 200
"""FU-15 catastrophic-regression ceiling for the region-recomposite path, ms.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps *render* budget): this
is a deliberately *loose* order-of-magnitude bound, ~400x above the correct
region-path p95 (~0.5 ms, dev-measured) yet orders of magnitude below the eager
full-canvas / O(full-canvas) region regression class (hundreds of ms to tens of
seconds). It catches the SC-UI-015-1 regression class on a noisy 2-core CI runner
without flaking on scheduler jitter — the wrong altitude for the 16 ms budget.
(ADR / AGT-10 rendering-performance directive; S12 single-source.)"""

# --- Phase-5 animation tuning (phase-5 T5A-01; Article II single-source) ---------
# Named bounds/defaults consumed by logic/animation.py (playback + onion) and the
# reversible frame ops in logic/document.py. DEFAULT_FRAME_DURATION_MS (above) is
# REUSED for per-frame timing (FR-2). The PlaybackMode enum is an enumerated
# *vocabulary* (like BlendMode) and lives in logic/animation.py, NOT here (BF-2,
# plan §8). Onion tint colours are content-overlay RGBA constants, not theme roles
# (REQ-P5-UI-018). This module stays a leaf (no intra-package imports).

MAX_FRAMES: int = 4096
"""Defensive cap on the number of frames in a document (Article VII; parallels
:data:`MAX_LAYERS_PER_FRAME`, generous for hand-drawn animation)
(plan §8; spec REQ-P5-LOGIC-014; SC-L014-1)."""

MAX_ONION_SKIN_FRAMES: int = 8
"""Maximum onion-skin previous/next frame count per side (0..8 per side)
(research Q1 — *medium reliability*; plan §8; spec REQ-P5-LOGIC-012/014;
SC-L012-2)."""

DEFAULT_ONION_PREV: int = 1
"""Default number of previous frames shown by onion skinning (Aseprite default
1/1) (CL-4; plan §8; spec REQ-P5-LOGIC-014; SC-L014-2)."""

DEFAULT_ONION_NEXT: int = 1
"""Default number of next frames shown by onion skinning (Aseprite default 1/1)
(CL-4; plan §8; spec REQ-P5-LOGIC-014; SC-L014-2)."""

ONION_TINT_PREV: tuple[int, int, int, int] = (255, 0, 0, 255)
"""RGBA tint applied to *previous* onion ghosts (red = previous, Aseprite
mapping). The alpha channel is the tint *strength* used to blend the ghost toward
this colour (CL-4; plan §8; spec REQ-P5-LOGIC-012/014; SC-L012-1/L014-2)."""

ONION_TINT_NEXT: tuple[int, int, int, int] = (0, 0, 255, 255)
"""RGBA tint applied to *next* onion ghosts (blue = next, Aseprite mapping). The
alpha channel is the tint *strength* used to blend the ghost toward this colour
(CL-4; plan §8; spec REQ-P5-LOGIC-012/014; SC-L012-1/L014-2)."""

ONION_SKIN_OPACITY: float = 0.5
"""Onion ghost opacity for the *nearest* neighbour, in ``0.0..1.0`` (farther
ghosts fade linearly toward :data:`ONION_SKIN_OPACITY_MIN`) (research Q1 —
*medium reliability*; plan §8; spec REQ-P5-LOGIC-012; SC-L012-1)."""

ONION_SKIN_OPACITY_MIN: float = 0.15
"""Onion ghost opacity for the *farthest* neighbour, in ``0.0..1.0`` (linear
distance falloff floor from :data:`ONION_SKIN_OPACITY`) (research Q1 — *medium
reliability*; plan §8; spec REQ-P5-LOGIC-012)."""

# --- Phase-6 tilemap & level-design tuning (phase-6 T6A-01; Article II) ----------
# Named bounds/defaults consumed by logic/tileset.py, logic/tilemap.py and
# logic/autotile.py. BF-2 (spec §8 / ADR-0015): these are DISTINCT from the
# shipped TILE_SIZE (=64, the viewport-culling *rendering* edge) and TILE_BUFFER —
# Phase 6 NEVER reuses those as the tileset tile dimension. The Tiled GID flag
# masks stay module-local in tilemap.py and the Blob-47 bit weights + 256->47 LUT
# stay module-local in autotile.py (algorithm-intrinsic tables, ADR-0001 exemption
# / ADR-0013 / ADR-0015). This module stays a leaf (no intra-package imports).

DEFAULT_TILE_WIDTH: int = 16
"""Default tileset tile width, px (CL-1; common pixel-art tile — Tiled/Aseprite
user-set). DISTINCT from :data:`TILE_SIZE` (=64, the viewport-cull edge)
(plan §8; spec REQ-P6-LOGIC-014; SC-L014-2)."""

DEFAULT_TILE_HEIGHT: int = 16
"""Default tileset tile height, px (CL-1). DISTINCT from :data:`TILE_SIZE`
(plan §8; spec REQ-P6-LOGIC-014; SC-L014-2)."""

DEFAULT_TILE_MARGIN: int = 0
"""Default border offset, px, before the first tile in a tileset image (CL-2;
Tiled packed default) (plan §8; spec REQ-P6-LOGIC-014)."""

DEFAULT_TILE_SPACING: int = 0
"""Default gap, px, between adjacent tiles in a tileset image (CL-2; Tiled
packed default) (plan §8; spec REQ-P6-LOGIC-014)."""

MAX_TILE_DIMENSION: int = 1024
"""Defensive cap on a tileset tile edge, px (Article VII; generous vs pixel-art
tile sizes) (plan §8; spec REQ-P6-LOGIC-001/014; SC-L001-2)."""

MAX_TILESET_TILES: int = 65536
"""Defensive cap on the number of tiles in a single tileset (Article VII; ample
local-id space under the 28-bit gid range) (plan §8; spec REQ-P6-LOGIC-014)."""

MAX_TILEMAP_LAYERS: int = 256
"""Defensive cap on the number of layers in a tilemap (Article VII; parallels
:data:`MAX_LAYERS_PER_FRAME`) (plan §8; spec REQ-P6-LOGIC-008/014; SC-L008-1)."""

TILEMAP_CHUNK_SIZE: int = 16
"""Edge, in tiles, of a chunked-sparse tilemap-layer storage chunk (16x16, the
Tiled default; research §2.5) (plan §8; spec REQ-P6-LOGIC-009; ADR-0015)."""

MAX_TILEMAP_COORD: int = 1048576
"""Defensive coordinate-magnitude guard (2^20) for infinite-map cell addressing
(Article VII) (plan §8; spec REQ-P6-LOGIC-009; SC-L009-1)."""

# --- Phase-6 tilemap-viewport performance-gate tuning (Article II single-source) --
# Ceiling for the catastrophic full-8K tilemap-viewport CI perf gate (part-2 of the
# tilemap perf gate). Consumed by scripts/perf_profile.py --tilemap (passed as
# --budget-ms by .github/workflows/ci.yml, mirroring the FU-15 composite gate).

TILEMAP_VIEWPORT_CEILING_MS: int = 3000
"""Catastrophic-regression ceiling for the full-8K tilemap-viewport render path, ms.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps interactive *render*
budget used by part-1 of the tilemap perf gate — ``perf_profile.py --tilemap``
against the default budget): this is the deliberately *loose* order-of-magnitude
ceiling for part-2, the catastrophic full-8K tilemap-viewport CI gate. Like
:data:`COMPOSITE_REGION_CEILING_MS` (FU-15), it sits far above the correct
tilemap-viewport p95 yet orders of magnitude below the O(full-canvas) regression
class, so it never flakes on a noisy 2-core CI runner yet always catches a
catastrophic viewport-render regression. AGT-09 wires ci.yml to pass this value as
``perf_profile.py --tilemap --budget-ms``.
(AGT-10 rendering-performance re-profile / perf-gate spec; S12 single-source.)"""

# --- Phase-7 export & pipeline tuning (phase-7 T7A-01; Article II single-source) --
# Named bounds/defaults consumed by logic/export.py (raster/sprite-sheet pipeline)
# and logic/atlas.py (MaxRects atlas over CP-1). BF-1 (plan §8 / ADR-0019): every
# name is DISTINCT from every shipped constant — notably PNG_EXPORT_COMPRESS_LEVEL
# (=6, Pillow's documented default, pinned) is DISTINCT from the shipped
# PROJECT_ZLIB_LEVEL (=9, .pixproj pixel-data compression — a different concern).
# The ExportFormat/EnginePreset enums are enumerated *vocabulary* (like BlendMode /
# PlaybackMode) and live in logic/export.py, NOT here (BF-2). Pillow enum values
# (Dither.NONE), format strings, and the Aseprite/Unity/Godot wire-format version
# strings stay module-local to their module (ADR-0001). The atlas caller passes
# MAX_ATLAS_DIMENSION explicitly to compactor.compact (CP-1 imports no constants).
# This module stays a leaf (no intra-package imports).

DEFAULT_SPRITE_SHEET_COLUMNS: int = 8
"""Default sprite-sheet grid width, in frames (deterministic row-major layout)
(CL-5; plan §8; spec REQ-P7-LOGIC-005/012; SC-L005-1/SC-L012-1)."""

DEFAULT_ATLAS_PADDING: int = 0
"""Default inter-sprite padding, px, on a sheet/atlas (no gap → lossless, exact
coordinate/pixel round-trip) (CL-15; plan §8; spec REQ-P7-LOGIC-005/006/012)."""

MAX_ATLAS_DIMENSION: int = MAX_CANVAS_WIDTH
"""Defensive bound, px, on an atlas edge — passed explicitly to
:func:`~pixelart_creator.logic.compactor.compact` (CP-1 imports no constants).

ALIGNED TO THE PLATFORM 8K CEILING (Article VI). The packed atlas is built as a
:class:`~pixelart_creator.logic.pixel_buffer.PixelBuffer`, whose buildable maximum
is :data:`MAX_CANVAS_WIDTH` (=7680) x :data:`MAX_CANVAS_HEIGHT` (=4320). A former
value of 8192 EXCEEDED that width ceiling, so a sheet packed wider/taller than the
buildable buffer raised :class:`PixelBufferError` (a DIFFERENT class than
:class:`~pixelart_creator.logic.atlas.AtlasError`) when the sheet was allocated —
an inconsistency (S2 defect, found by AGT-10). Defining the atlas edge bound AS the
canvas width ceiling makes the default un-exceedable by the buffer. Note the height
axis is further clamped to :data:`MAX_CANVAS_HEIGHT` inside
:func:`~pixelart_creator.logic.atlas.pack_atlas` (the buffer is not square), so the
effective per-axis atlas ceiling is ``min(max_dimension, MAX_CANVAS_WIDTH)`` x
``min(max_dimension, MAX_CANVAS_HEIGHT)`` — see that function. Article VII/VI;
plan §8; spec REQ-P7-LOGIC-006/012; SC-L012-1; ADR-0017/0019."""

MAX_BATCH_TARGETS: int = 256
"""Defensive cap on the number of targets in one batch export (Article VII;
parallels :data:`MAX_LAYERS_PER_FRAME`) (CL-10; plan §8; spec
REQ-P7-LOGIC-010/012; SC-L010-1/SC-L012-1)."""

MAX_EXPORT_FRAMES: int = 4096
"""Defensive cap on frames per sprite-sheet / GIF (Article VII; parallels the
shipped :data:`MAX_FRAMES`) (plan §8; spec REQ-P7-LOGIC-005/012; SC-L012-1)."""

PNG_EXPORT_COMPRESS_LEVEL: int = 6
"""ZLIB level for byte-reproducible PNG export, pinned to Pillow's documented
default. DISTINCT from :data:`PROJECT_ZLIB_LEVEL` (=9, .pixproj pixel-data
compression — a different concern) (ADR-0019; plan §8; spec REQ-P7-LOGIC-003;
SC-L003-1)."""

GIF_DEFAULT_LOOP_COUNT: int = 0
"""Default GIF loop count; ``0`` = loop forever (Aseprite / GIF norm) (ADR-0019;
plan §8; spec REQ-P7-LOGIC-004; SC-L004-1)."""

GIF_FRAME_DISPOSAL: int = 2
"""GIF per-frame disposal method; ``2`` = restore-to-background — the safe
per-frame pixel-art default (ADR-0019; plan §8; spec REQ-P7-LOGIC-004;
SC-L004-1)."""

# --- Phase-8 automation & extensibility tuning (phase-8 T8A-01; Article II) ------
# Named bounds/defaults consumed by logic/scripting.py (DSL dispatcher),
# logic/macro.py (record/replay), logic/plugins.py (plugin host), logic/procgen.py
# (seeded generators) and logic/batch_ops.py (batch recolour). BF-1 (plan §8 /
# ADR-0022): every name is DISTINCT from every shipped constant — notably
# MAX_BATCH_RECOLOUR_TARGETS is DISTINCT from the shipped Phase-7 MAX_BATCH_TARGETS
# (=256, batch *export* — a different concern). The DSL op-name vocabulary, the
# macro schema_version string, and the plugin Capability enum are module-local
# enumerated vocabulary / format-intrinsic and live in their modules, NOT here
# (ADR-0001 / BF-2, the BlendMode/PlaybackMode precedent). This module stays a
# leaf (no intra-package imports).

MAX_MACRO_STEPS: int = 4096
"""Defensive cap on the number of ordered steps in one recorded macro
(Article VII; parallels the shipped :data:`MAX_FRAMES` / :data:`MAX_EXPORT_FRAMES`
= 4096) (plan §8; spec REQ-P8-LOGIC-004/013; SC-L004-1/SC-L013-1)."""

MAX_SCRIPT_OPS: int = 100000
"""Defensive per-run op ceiling for the DSL dispatcher — a runaway script fails
safely before resource exhaustion (Article VII; CL-16) (plan §8; spec
REQ-P8-LOGIC-001/003/013; SC-L001-1/SC-L013-1)."""

MAX_PLUGINS_LOADED: int = 64
"""Defensive cap on concurrently loaded plugins (Article VII; parallels the
shipped :data:`FAVOURITES_MAX` = 64) (plan §8; spec REQ-P8-LOGIC-010/013;
SC-L010-1/SC-L013-1)."""

MAX_BATCH_RECOLOUR_TARGETS: int = 256
"""Defensive cap on the number of targets in one batch recolour (Article VII;
parallels :data:`MAX_LAYERS_PER_FRAME`). DISTINCT from the Phase-7
:data:`MAX_BATCH_TARGETS` (=256, batch *export* — a different concern) (plan §8;
spec REQ-P8-LOGIC-011/013; SC-L011-1/SC-L013-1)."""

MAX_PROCGEN_DIMENSION: int = 7680
"""Per-axis output bound, px, for procedural generation — aligned to the
buildable 8K ceiling (``= MAX_CANVAS_WIDTH``; the ADR-0020 atlas-clamp precedent)
(Article VII/VI) (plan §8; spec REQ-P8-LOGIC-012/013; SC-L012-1/SC-L013-1)."""

DEFAULT_PROCGEN_SEED: int = 0
"""Deterministic default seed for procedural generation (P2; parallels the shipped
:data:`KMEANS_SEED` = 0) (plan §8; spec REQ-P8-LOGIC-012; SC-L012-1)."""

# --- Phase-9 visual-aids tuning (phase-9 T9A-01; Article II single-source) --------
# Named bounds/defaults consumed by the new pure-geometry logic modules
# (logic/grids.py, logic/guides.py, logic/preview.py, logic/timelapse.py) and the
# document-PPI field. BF-1 (plan §8 / ADR-0023/0024): every name is DISTINCT from
# every shipped constant — notably DISTINCT from the shipped GRID_MIN_PIXEL_EDGE_PX
# (=8, the per-pixel grid-overlay device-px threshold — a rendering concern), from
# TILE_SIZE (=64, the viewport-cull edge) and DEFAULT_TILE_WIDTH/HEIGHT (=16, the
# tileset tile dimension). GuideOrientation and the timelapse-session
# schema_version string are module-local enumerated vocabulary / format-intrinsic
# and live in their modules, NOT here (ADR-0001 / BF-2, the BlendMode/PlaybackMode
# precedent). This module stays a leaf (no intra-package imports).

DEFAULT_ISO_GRID_RATIO: float = 2.0
"""Default isometric tile aspect ratio W:H — 2:1 dimetric (26.565° = ``atan(0.5)``),
the pixel-art standard (integer math, crisp grid lines). True-isometric (30°) stays
a configurable ratio, not the default; the invertible transform contract is
ratio-independent (ADR-0023 §1; research §1.1; spec REQ-P9-LOGIC-001; SC-L001-1)."""

DEFAULT_SNAP_TOLERANCE_PX: int = 8
"""Default snap "stickiness" in *screen* px; divided by zoom to act in document
space so perceived stickiness is constant at every zoom (research §3.3 6–8 px)
(ADR-0023 §3; spec REQ-P9-LOGIC-004/005; SC-L004-1/SC-L005-1)."""

MIN_GRID_SPACING: int = 2
"""Minimum isometric tile width, px — avoids sub-pixel grids; ``grids`` clamps
``tile_width`` to ``[MIN_GRID_SPACING, MAX_GRID_SPACING]`` (ADR-0024; spec
REQ-P9-LOGIC-008/011; SC-L011-1)."""

MAX_GRID_SPACING: int = 1024
"""Maximum isometric tile width, px — bounded config, ``grids`` clamps to this
(ADR-0024; spec REQ-P9-LOGIC-008/011; SC-L011-1)."""

MAX_GUIDES: int = 256
"""Defensive cap on the number of guides considered in one snap (Article VII;
parallels the shipped :data:`MAX_BATCH_RECOLOUR_TARGETS` = 256) (ADR-0024; spec
REQ-P9-LOGIC-005/011; SC-L011-1)."""

MAX_PERSPECTIVE_VANISHING_POINTS: int = 3
"""Maximum simultaneous vanishing points — 1-/2-/3-point perspective (ADR-0023 §2;
spec REQ-P9-LOGIC-003/004/011; SC-L003-1/SC-L004-1)."""

MAX_REFERENCE_IMAGES: int = 256
"""Defensive cap on the number of reference images in one board (Article VII;
parallels :data:`MAX_GUIDES`) (ADR-0024; spec REQ-P9-DATA-002; SC-UI-006-1)."""

MAX_TIMELAPSE_FRAMES: int = 4096
"""Defensive cap on the number of frames in one timelapse session (Article VII;
parallels the shipped :data:`MAX_FRAMES` / :data:`MAX_MACRO_STEPS` = 4096)
(ADR-0024; spec REQ-P9-LOGIC-010/011; SC-L010-1)."""

# --- Phase-9 historical-replay playback/payload tuning (D-12; Article II
# single-source) ------------------------------------------------------------------

TIMELAPSE_PLAYBACK_FPS_DEFAULT: int = CYCLE_DEFAULT_FPS
"""Default historical-timelapse playback cadence, fps (DEP-12a).

Reused rather than invented: :data:`CYCLE_DEFAULT_FPS` (=10, cited above) is the
product's only shipped non-animation frame-sequence playback cadence, so the
replay control surface (``ui/timelapse_controls.py``) plays back at the same
default rate a user already knows from onion-skin/cycle playback (spec
REQ-P9-LOGIC-018; DEP-12a)."""

TIMELAPSE_PLAYBACK_SPEEDS: Tuple[float, ...] = (0.25, 0.5, 1.0, 2.0, 4.0)
"""Selectable historical-timelapse playback-speed multipliers (DEP-12a).

Doubling steps bracketing ``1.0``, bounded above so the fastest speed cannot
outrun the frame budget: ``FPS_TARGET // CYCLE_DEFAULT_FPS = 60 // 10 = 6``, so
``4.0`` is the largest doubling step below that bound and the low end (``0.25``)
mirrors it. The derivation is the citation (spec REQ-P9-LOGIC-018; DEP-12a)."""

TIMELAPSE_PAYLOAD_MAX_BYTES: int = 2_821_573 * (MAX_TIMELAPSE_FRAMES // 256)
"""Hard cap on one serialised ``.pixtimelapse`` payload, bytes (REQ-P9-DATA-004;
DEP-12e; Article II).

Valued at ``2_821_573 * (4096 // 256) = 2_821_573 * 16 = 45_145_168`` bytes
(43.054 MiB). ``2_821_573`` is P4's measured **schema-3** file size —
1280x720, 256 frames, byte-identical across all 5 repeat runs — the largest
of the T43 re-measurement campaign's four points
(``design-docs/reports/perf-timelapse-payload-campaign-schema3-20260818.md``
§3), extended to the shipped :data:`MAX_TIMELAPSE_FRAMES` (= 4096) frame cap
by the unchanged ``* (MAX_TIMELAPSE_FRAMES // 256)`` step (plan §11.1). Never
inlined: every consumer reads this name, never the literal.

Superseded value (2026-08-17): ``2_397_487`` (-> a ``38_359_792``-byte bound),
P4's **schema-2** file size measured by the original T19 campaign
(``design-docs/reports/perf-timelapse-payload-campaign-20260817.md`` §3).
That campaign's fixture-generator script was ephemeral (per AGT-10's role
contract) and could not be re-invoked, so the schema-3 anchor above is a
FRESH measurement on a freshly-generated fixture with its own stroke
placement — it is **not** the old anchor plus identity's cost, and the two
anchors are not directly comparable (plan §11.2). In particular: the anchor
moved, but the movement may **not** be characterised as "identity" or
"schema 3" making payloads larger by that margin — that reading is false.
The only measured, attributable cost of identity is the campaign's
**within-payload** figure of +0.55% at P4 (same dict, re-serialised with the
identity fields stripped, campaign §6), which is immune to the fixture
confound; the rest of the anchor's movement is a content-profile artifact of
the new fixture, not an earned or measured cost of anything this constant
guards.

ANCHOR INVARIANT: any future change to ``data/timelapse_io.py``'s
serialisation that moves the bytes ``serialize_payload`` produces —
separators, key order, field addition/removal, encoding — invalidates this
anchor and requires the full re-measure -> re-value -> re-write chain
(mirroring T43 -> T44 -> T45's shape) in the same unit of review as that
change. Patching this constant by arithmetic instead of re-measuring is
forbidden (plan §11.3)."""

TIMELAPSE_RECORDING_ID_BYTES: int = 16
"""Byte width of a timelapse recording's per-recording random half (Q-21,
REQ-P9-LOGIC-022(b); REQ-P9-DATA-005; plan §10.4).

128 bits is a **uniqueness** width, not a security one — deliberately
narrower than the shipped ``secrets.token_urlsafe(24)`` at
``data/cloud/providers/base.py:181``, because that token must resist an
adversary and this one only has to not collide, while being paid on every
frame minted in a recording session (``ui/timelapse_controls.py``, T34)."""

TIMELAPSE_FRAME_ID_MAX_LEN: int = 2 * TIMELAPSE_RECORDING_ID_BYTES + 1 + 19
"""Maximum length of one frame's stable identity string (Q-21,
REQ-P9-LOGIC-022(b); REQ-P9-DATA-005; plan §10.4).

``2 * TIMELAPSE_RECORDING_ID_BYTES`` is the hex width of the per-recording
random half, ``+ 1`` is the ``":"`` separator, and ``19`` is the decimal
width of a 64-bit ordinal. **The ordinal is NOT bounded by
:data:`MAX_TIMELAPSE_FRAMES`** — it is monotone across discards while the
session's live frame count is not (T34: a discard-and-rewrite never resets
or rewinds the ordinal)."""

MAX_DOCUMENT_VIEWS: int = 8
"""Defensive cap on simultaneous views of one shared document (bounded UI
resource; parallels :data:`MAX_ONION_SKIN_FRAMES` = 8) (ADR-0024; spec
REQ-P9-LOGIC-012/UI-007; SC-UI-007-1)."""

DEFAULT_DOCUMENT_PPI: float = 72.0
"""Default document pixels-per-inch for real-size preview — the screen/print
baseline (BF-3). Real-size is a *document* property: ``real_size_scale`` sources
``doc_ppi`` from this field. Validated ``> 0``/finite by the ``Document`` setter;
persisted in ``.pixproj`` v5 (v1–v4 load with this default) (ADR-0023 §4; ADR-0025
§1; spec REQ-P9-LOGIC-007; SC-L007-1)."""

# --- Phase-9 overlay/multi-view performance-gate tuning (Article II single-source)
# Ceiling for the Phase-9 overlay/multi-view frame perf gate. Consumed by
# scripts/perf_profile.py --overlay (passed as --budget-ms by
# .github/workflows/ci.yml, mirroring the FU-15 composite / tilemap-viewport gates).

OVERLAY_FRAME_CEILING_MS: int = 48
"""Catastrophic-regression ceiling for the Phase-9 overlay/multi-view frame path, ms.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps interactive *render*
budget): this is the deliberately *loose* CI ceiling for the ``--overlay`` frame
perf gate. Like :data:`COMPOSITE_REGION_CEILING_MS` (FU-15) and
:data:`TILEMAP_VIEWPORT_CEILING_MS`, it sits far above the correct overlay/multi-view
p95 yet well below the O(full-canvas) fine-grid regression class (the 722 ms
zoom-out blowup AGT-10 measured), so it never flakes on a noisy 2-core CI runner
yet always catches a catastrophic overlay-render regression. AGT-09 wires ci.yml to
pass this value as ``perf_profile.py --overlay --budget-ms``.
(AGT-10 overlay-perf directive; S12 single-source.)"""

# --- Phase-9 8K iso-overlay cache-miss gate tuning (WP-6.4 D-29; Article II
# single-source) ------------------------------------------------------------------
# Ceiling for the missing literal-8K overlay-viewport CI scenario
# (``--overlay --ov-viewport 7680 4320 --ov-tile 32``), distinct from the
# 1920x1080 scenario every wired ``--overlay`` step exercises today (perf-model
# governance record `design-docs/auxiliary/perf-model-governance-20260816.md`
# §7, D-29). Consumed by scripts/perf_profile.py --overlay (passed as
# --budget-ms by .github/workflows/ci.yml, mirroring the FU-15 overlay/tilemap
# ceilings above).

OVERLAY_8K_CEILING_MS: int = 2000
"""Catastrophic-regression ceiling for the 8K iso-overlay CPU-raster cache-miss
path, ms — NOT a per-frame budget.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps interactive *render*
budget) and from :data:`OVERLAY_FRAME_CEILING_MS` (48 ms, the FHD 1920x1080
overlay scenario): this is the deliberately *loose* Tier-2 ceiling (perf-model
governance §3) for the literal 8K overlay viewport
(``--overlay --ov-viewport 7680 4320 --ov-tile 32``), the scenario the
governance record's D-29 forward pointer names as missing entirely — no wired
job exercised the CPU-raster fallback risk at 8K before this. Derived from
AGT-10's 2026-08-16 measurement: worst local p95 297.5 ms, scaled for the
2-core CI runner per the Phase-12 spec's CI-scaling factor to ~744 ms, leaving
~2.7x headroom to this 2000 ms bound — loose enough to never flake on a noisy
runner yet well below the O(full-canvas) regression class it must catch. AGT-09
wires ci.yml to pass this value as ``perf_profile.py --overlay --budget-ms``.
(AGT-10 D-29 measurement; perf-model governance §3 rule 3; S12 single-source.)"""

# --- Phase-10 Slice-A cloud/sync tuning (phase-10 T10A-01; Article II) ------------
# Named bounds/defaults consumed by the new zero-Qt cloud/sync models
# (logic/sync_state.py, logic/autosave.py, logic/version_history.py) and the
# data/cloud/ port + fake adapter. BF-1 (plan §8 / ADR-0026): every name is DISTINCT
# from every shipped constant. The SyncState enum is module-local enumerated
# vocabulary and lives in logic/sync_state.py, NOT here (ADR-0001 / BF-2, the
# BlendMode/PlaybackMode precedent). This module stays a leaf (no intra-package
# imports). Slice-B/C cloud constants (MAX_SHARED_MEMBERS, MAX_COMMENT_BYTES,
# MAX_COMMENTS_PER_PROJECT, CRDT_TILE_SIZE_PX, MAX_CRDT_UPDATE_BYTES) land with
# their slices (plan §8), not here.

AUTOSAVE_INTERVAL_MS: int = 120000
"""Autosave cadence, ms — 2 minutes, the editor norm. Consumed by
:func:`pixelart_creator.logic.autosave.should_autosave` as the default elapsed
threshold between autosaves (BF-1; Researcher §3.2; plan §8; spec REQ-P10-LOGIC-002;
SC-L002-1)."""

MAX_CLOUD_VERSIONS: int = 100
"""Version-history retention cap — the maximum number of ordered
:class:`~pixelart_creator.logic.version_history.CloudVersion` entries a
:class:`~pixelart_creator.logic.version_history.VersionHistory` may hold before
``append`` raises ``VersionHistoryError``. Aligns the Dropbox 100-revision limit
(Researcher §1.2). Retention *policy* beyond the bound is an AGT-01 HOW (plan §8;
spec REQ-P10-DATA-003/LOGIC-003/005; SC-L003-1)."""

MAX_CLOUD_PROJECT_BYTES: int = 268435456
"""Defensive ceiling, bytes, on a cloud-fetched ``.pixproj`` / version / recovery
blob — 256 MiB (an 8K RGBA layer resident is ~126 MB; this leaves headroom for
multi-layer/animation payloads). A blob exceeding this is rejected with
``CloudDataError`` *before* it is decoded, so a tampered/oversized cloud file can
never exhaust memory or reach ``eval``/``exec`` (Article VII untrusted-input cap;
plan §8; spec REQ-P10-DATA-006; SC-D006-1)."""

CLOUD_RETRY_LIMIT: int = 3
"""Ceiling on transient-failure retries for a single cloud operation before it
fails to the caller (BF-1; bounds a provider adapter's retry loop; the fake adapter
never fails transiently) (plan §8; spec REQ-P10-LOGIC-005; SC-L005-1)."""

# --- Phase-10 Slice-B/C collaboration tuning (phase-10 T10B-01/T10C-01; Article II)
# Named bounds/defaults consumed by the new zero-Qt collaboration models
# (logic/cloud_validation.py, logic/convergence.py) and the data/cloud/ shared
# adapter — and, in Slice C, by the client transport port and the sync_backend/
# validation caps (which reuse these SAME named bounds, ADR-0027 §6 / ADR-0028 §5).
# BF-3 (plan §8 / ADR-0028 §5): every name is DISTINCT from every shipped constant —
# notably CRDT_TILE_SIZE_PX is DISTINCT from the shipped TILE_SIZE (=64, the
# viewport-culling *render* edge) and DEFAULT_TILE_WIDTH/HEIGHT (=16, the tileset
# tile dimension): it is the raster tile/region-LWW *partition* edge (LOGIC-006).
# The CRDT message-kind vocabulary is module-local enumerated vocabulary and lives in
# logic/cloud_validation.py, NOT here (ADR-0001 / BF-2, the BlendMode/PlaybackMode
# precedent). This module stays a leaf (no intra-package imports).

MAX_SHARED_MEMBERS: int = 32
"""Defensive ceiling on the number of members of one shared project (Article VII;
BF-3 — generous for a collaborating pixel-art team). A membership payload exceeding
this is rejected with a defensive error before it can exhaust memory
(plan §8; spec REQ-P10-DATA-009; SC-D009-1)."""

MAX_COMMENT_BYTES: int = 4096
"""Defensive per-comment UTF-8 byte cap (Article VII). Comment text is untrusted
input; a comment whose encoded size exceeds this is rejected before decode, so a
tampered/oversized payload can never exhaust memory or reach ``eval``/``exec``
(plan §8; spec REQ-P10-DATA-009/UI-010; SC-D009-1)."""

MAX_COMMENTS_PER_PROJECT: int = 1024
"""Defensive ceiling on the number of comments stored against one shared project
(Article VII; BF-3 — parallels the shipped 1024-scale bounds). Exceeding it raises a
defensive error rather than degrading silently (plan §8; spec REQ-P10-DATA-009;
SC-D009-1)."""

MAX_CRDT_UPDATE_BYTES: int = 1048576
"""Defensive ceiling, bytes, on a single CRDT-update blob — 1 MiB (Article VII).
A CRDT update is untrusted input on both the client ``data/cloud/`` transport and the
``sync_backend/`` relay (which reuse this SAME named bound); a blob exceeding it is
rejected *before* any decode, so a malicious/broken client cannot exhaust memory or
reach ``eval``/``exec`` (plan §8; spec REQ-P10-DATA-010/BACKEND-002/LOGIC-006/-007;
SC-D010-1/SC-BK-002-1)."""

CRDT_TILE_SIZE_PX: int = 64
"""Raster tile/region last-writer-wins partition edge, px (REQ-P10-LOGIC-006).

The hybrid convergence model (ADR-0028 §2) partitions a layer's raster buffer into
``CRDT_TILE_SIZE_PX`` x ``CRDT_TILE_SIZE_PX`` tiles, each an LWW-Register keyed by
``(logical_clock, site_id)`` — concurrent edits to *different* tiles both survive,
same-tile edits resolve by the tiebreak. Tile partitioning (not per-pixel CRDT
metadata) is what makes the model **8K-scalable** (spec REQ-P10-LOGIC-006). DISTINCT
from the shipped :data:`TILE_SIZE` (=64, the viewport-cull *render* edge — a different
concern that happens to share the value) and from :data:`DEFAULT_TILE_WIDTH` /
:data:`DEFAULT_TILE_HEIGHT` (=16, the tileset tile dimension) (plan §8; ADR-0028 §5;
BF-3)."""

REALTIME_APPLY_CEILING_MS: int = 10
"""Sub-frame ceiling, ms, for applying one inbound real-time CRDT patch
(REQ-P10-LOGIC-007; Article VI split, plan §7 / ADR-0027 §7).

Slice C real-time remote-patch application RE-ENTERS the 16 ms per-frame budget
(:data:`FRAME_BUDGET_MS`), unlike the batch Slice-A/B sync path. This is the
DELIBERATELY TIGHTER per-patch sub-budget AGT-10 specified for the ``--realtime`` CI
perf gate: applying a single remote patch (validate + converge) must finish inside
``REALTIME_APPLY_CEILING_MS`` so that patch-apply plus the live-cursor overlay draw
(REQ-P10-UI-013) still leave headroom within the 16 ms frame. Sourced by
``scripts/perf_profile.py --realtime`` (passed as ``--budget-ms`` by
``.github/workflows/ci.yml``) — DISTINCT from :data:`FRAME_BUDGET_MS` (the whole-frame
render budget) and from the loose catastrophic-regression ceilings
(:data:`COMPOSITE_REGION_CEILING_MS` / :data:`TILEMAP_VIEWPORT_CEILING_MS` /
:data:`OVERLAY_FRAME_CEILING_MS`): this one is a genuine sub-frame apply target, not an
order-of-magnitude catch-all. (AGT-10 FLAG-PERFRAME / DEP-3; S12 single-source.)"""

# --- In-app User Guide tuning (user-guide T-UG-03; Article II single-source) ------
# Named numerics consumed by logic/guide_model.py, logic/guide_search.py and
# data/guide_content.py (the offline bundled-content User Guide). BF (plan §3.4 /
# ADR-0029 §1): every name is DISTINCT from every shipped constant. Section/topic
# ids and locale codes (e.g. DEFAULT_GUIDE_LOCALE) are STRING identifiers, NOT
# numeric tuning values (Article II governs numerics) — they are homed module-local
# in guide_model.py, NOT here (ADR-0001; spec §9). This module stays a leaf.

GUIDE_SEARCH_RESULT_CAP: int = 50
"""Maximum number of topics one :func:`pixelart_creator.logic.guide_search.query`
call returns — a defensive bound on the in-guide search result list (Article VII;
a filter that narrows, generous for the shipped ToC) (ADR-0029 §6; plan §3.2/§3.4;
spec REQ-UG-LOGIC-003/NFR-6; SC-L003-1..3)."""

GUIDE_MAX_CONTENT_BYTES: int = 1048576
"""Defensive per-topic content-size ceiling, bytes — 1 MiB. A bundled Markdown
resource whose byte length exceeds this is rejected with ``GuideContentError``
*before* decode, so a malformed/oversized file can never exhaust memory (Article VII
defensive-load posture, the PIO-1 / MAX_CLOUD_PROJECT_BYTES precedent) (ADR-0029 §5;
plan §3.3/§3.4; spec REQ-UG-DATA-001/003/NFR-4; SC-D001-2)."""

GUIDE_MAX_TOC_DEPTH: int = 3
"""Ceiling on the discovered ToC tree depth (section -> topic -> sub-topic). The
shipped model is 2 levels (sections -> topics); ``build_model`` validates the
achieved depth stays ``<= GUIDE_MAX_TOC_DEPTH`` so a future nested manifest cannot
grow an unbounded tree (Article VII; Article XI extensibility bound) (ADR-0029 §6;
plan §3.4; spec REQ-UG-LOGIC-001/002/NFR-6)."""
# --- Phase-11 team & asset-management tuning (phase-11 T11-1-01; Article II) -------
# Named bounds/defaults consumed by the new zero-Qt asset models
# (logic/asset_catalog.py, logic/asset_tags.py, logic/asset_query.py) and the new
# zero-Qt asset stores (data/asset_cas.py, data/asset_catalog_io.py). BF-1 (plan §8 /
# ADR-0030 / ADR-0032): every name is DISTINCT from every shipped constant. The
# AssetKind enum is a module-local enumerated *vocabulary* and lives in
# logic/asset_catalog.py, NOT here (ADR-0001 / BF-2, the BlendMode/PlaybackMode/
# SyncState precedent). MAX_DEPENDENCY_DEPTH (Slice 2) and MAX_ASSET_VERSIONS (Slice 3)
# land with their slices (plan §8), not here. This module stays a leaf (no intra-package
# imports).

MAX_CATALOG_ASSETS: int = 65536
"""Defensive cap on the number of asset entries in one catalog (Article VII).

:meth:`~pixelart_creator.logic.asset_catalog.AssetCatalog.add` and the defensive catalog
loader (:func:`~pixelart_creator.data.asset_catalog_io.load_catalog`) reject a catalog
exceeding this, so a tampered/oversized index can never exhaust memory. Parallels the
shipped :data:`MAX_TILESET_TILES` (=65536) local-id scale — a DISTINCT named concern
(plan §8; spec REQ-P11-LOGIC-007; ADR-0030 §7)."""

MAX_TAGS_PER_ASSET: int = 64
"""Defensive cap on the number of tags attached to one asset (Article VII).

A tag add that would exceed it raises ``AssetTagError`` rather than truncating silently
(REQ-P11-DATA-003 acceptance). Parallels the shipped :data:`FAVOURITES_MAX` (=64), a
DISTINCT named concern (plan §8; spec REQ-P11-LOGIC-002/-007; ADR-0030)."""

MAX_TAG_BYTES: int = 128
"""Defensive per-tag UTF-8 byte cap (Article VII) — a short label.

Tag text is untrusted input; a tag whose encoded size exceeds this is rejected with
``AssetTagError`` / ``AssetCatalogError`` before it is stored, so a tampered/oversized
tag can never exhaust memory or reach ``eval``/``exec`` (plan §8; spec
REQ-P11-DATA-003/LOGIC-002/-007)."""

MAX_METADATA_BYTES: int = 4096
"""Defensive per-asset metadata UTF-8 byte cap (Article VII).

Measured over the canonical JSON encoding of the metadata mapping. Asset metadata is
untrusted input; a metadata bag whose canonical size exceeds this is rejected before it
is stored. Parallels the shipped :data:`MAX_COMMENT_BYTES` (=4096), a DISTINCT named
concern (plan §8; spec REQ-P11-DATA-002/LOGIC-007)."""

MAX_BLOB_BYTES: int = 268435456
"""Defensive per-CAS-blob ceiling, bytes — 256 MiB (Article VII).

A blob offered to :meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.put`
whose size exceeds this is rejected with ``CasError`` *before* it is stored, and an
oversized fetched blob is rejected before decode, so a tampered/oversized asset payload
can never exhaust memory or reach ``eval``/``exec`` (an 8K RGBA layer resident is
~126 MB; this leaves headroom for multi-layer/animation payloads). SHARES THE VALUE of
the shipped :data:`MAX_CLOUD_PROJECT_BYTES` (=268435456) but is a DISTINCT named concern
— the CAS blob ceiling, not the cloud project ceiling (plan §8; spec
REQ-P11-DATA-004/-005/LOGIC-007; ADR-0030 §4)."""

# --- Phase-11 Slice-2 dependency-graph tuning (phase-11 T11-2-01; Article II) -----
# Named bound consumed by the new zero-Qt dependency-graph model
# (logic/dependency_graph.py) and, through it, the break-detection pass
# (logic/break_detection.py). BF-1 (plan §8 / ADR-0031): the name is DISTINCT from
# every shipped constant — notably from MAX_GROUP_NESTING_DEPTH (=8, the layer-group
# nesting cap) and GUIDE_MAX_TOC_DEPTH (=3, the User-Guide ToC depth) — this is the
# asset-dependency *traversal* depth guard. The reason-string vocabulary of the break
# pass ("missing" / "hash-mismatch") is module-local enumerated vocabulary and lives in
# break_detection.py, NOT here (ADR-0001 / BF-2, the BlendMode/PlaybackMode precedent).
# This module stays a leaf (no intra-package imports).

MAX_DEPENDENCY_DEPTH: int = 64
"""Defensive cap on asset-dependency transitive-traversal depth (Article VII).

:meth:`~pixelart_creator.logic.dependency_graph.DependencyGraph.dependencies_of` /
:meth:`~pixelart_creator.logic.dependency_graph.DependencyGraph.dependents_of` raise
``DependencyGraphError`` when a transitive walk would exceed this many levels — a
belt-and-braces guard alongside the white/grey/black cycle rejection so a pathological
or malformed graph can never spin unbounded (the graph is kept acyclic by ``add_edge``,
but the depth bound backstops any deep legitimate chain). Parallels the shipped
``1024``/``256``-scale defensive bounds; a DISTINCT named concern from the layer-nesting
``MAX_GROUP_NESTING_DEPTH`` (=8) (plan §8; spec REQ-P11-LOGIC-004/-007; ADR-0031 §2)."""

# --- Phase-11 Slice-3 asset-version tuning (phase-11 T11-3-01; Article II) ---------
# Named bound consumed by the new zero-Qt asset-version model
# (logic/asset_version.py) and, through it, the append-only revision store
# (data/asset_revision_store.py). BF-1 (plan §8 / ADR-0030 §6): the name is DISTINCT
# from every shipped constant — most pointedly from MAX_CLOUD_VERSIONS (=100, the
# Phase-10 cloud project-version retention cap, a DIFFERENT concern). This is the
# per-asset revision-history cap of the content-hash-addressed asset-revision DAG. The
# reason/marker vocabulary of the version model lives module-local (ADR-0001 / BF-2).
# This module stays a leaf (no intra-package imports).

MAX_ASSET_VERSIONS: int = 256
"""Defensive cap on the revisions in one asset's version history (Article VII).

:meth:`~pixelart_creator.logic.asset_version.AssetVersionHistory.append` raises
``AssetVersionError`` when appending would exceed this many revisions, so a
tampered/oversized revision history can never exhaust memory. DISTINCT from the shipped
:data:`MAX_CLOUD_VERSIONS` (=100, the Phase-10 cloud project-version retention cap) — a
separate concern: this bounds the per-asset content-hash-addressed revision DAG, not a
cloud project's version history. Parallels the shipped ``256``-scale defensive bounds
(e.g. :data:`MAX_LAYERS_PER_FRAME`) (plan §8; spec REQ-P11-LOGIC-006/-007;
ADR-0030 §6)."""

# --- Phase-12 Slice-A full-frame flatten tuning (phase-12 T12-A-01; Article II) ---
# Named ceiling + working-set tuning consumed by the optimised full-frame flatten
# path in logic/blend.py (composite_stack(region=None)) and by
# scripts/perf_profile.py --full-frame (passed as --budget-ms by
# .github/workflows/ci.yml, mirroring the FU-15 composite / tilemap-viewport gates).
# BF (plan §8 / ADR-0033 §5): every name is DISTINCT from every shipped ceiling
# (COMPOSITE_REGION_CEILING_MS / TILEMAP_VIEWPORT_CEILING_MS / OVERLAY_FRAME_CEILING_MS
# / REALTIME_APPLY_CEILING_MS). This module stays a leaf (no intra-package imports).

COMPOSITE_FULL_CEILING_MS: int = 15000
"""LOOSE catastrophic-regression ceiling for the realistic-content full-frame
8K flatten gate on the 2-core CI runner, ms — NOT a per-frame budget.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps interactive *render*
budget) and from every other shipped ceiling. The cold full-frame
``blend.composite_stack(region=None)`` over the full ``(4320, 7680, 4)`` canvas is
a **batch / on-demand** op (flatten, export, merge-visible), **not** a per-frame
render path — so Article VI's 16 ms budget does not govern it and is neither
applied nor relaxed here (spec §5; ADR-0033 §5; FU-15). This is a deliberately
*loose* order-of-magnitude bound RE-PROFILE-confirmed by AGT-10 against the
**realistic-content 8-layer** flatten (≈2.7 s on a fast desktop; ≈5–8 s on the
slow 2-core CI runner). The former 3000 ms mirror of the full-8K
:data:`TILEMAP_VIEWPORT_CEILING_MS` was too tight for that realistic gate and
would flake on healthy code on the 2-core runner (the FU-15 loose-ceiling
caution / failure mode). 15000 ms gives ~1.85–2.5x margin over realistic content
while staying ~2.5–4x **below** the ~38–63 s catastrophic-regression cost it must
catch (the measured 20 244 ms (4L) / 42 669 ms (8L) class scales worse on the
2-core runner). AGT-09 wires ci.yml to pass this value as
``perf_profile.py --full-frame --budget-ms`` (the ``--full-frame`` gate already
reads this constant as its default ceiling)
(AGT-10 RE-PROFILE + FU-15 loose-ceiling caution; plan §8;
spec REQ-P12-LOGIC-001/-003; ADR-0033; baseline §6; S12 single-source)."""

FLATTEN_TILE_EDGE_PX: int = 1024
"""Edge, px, of a disjoint working tile for the blocked full-frame flatten.

The optimised full-frame ``composite_stack(region=None)`` splits the canvas into
disjoint ``FLATTEN_TILE_EDGE_PX`` x ``FLATTEN_TILE_EDGE_PX`` blocks and composites
each block through the existing bit-exact region compositor, blitting the result at
the tile origin. Because the tiles are disjoint and the blend primitives are
strictly per-pixel (no cross-tile state), the tiled result is **byte-identical** to
the single-shot whole-canvas composite (REQ-P12-LOGIC-002; ADR-0033 §2). The edge
bounds each block's working set (an 8K frame = 8x5 = 40 tiles at this edge), cutting
the full-canvas temporary churn that dominates the cold flatten while leaving enough
tiles to fan across a thread pool. A power-of-two edge below the 8K axes
(:data:`MAX_CANVAS_WIDTH` / :data:`MAX_CANVAS_HEIGHT`) (ADR-0033 §2; plan §3;
spec REQ-P12-LOGIC-001)."""

FLATTEN_MAX_WORKERS: int = 8
"""Upper bound on worker threads for the blocked full-frame flatten.

The disjoint tiles are fanned across at most
``min(FLATTEN_MAX_WORKERS, os.cpu_count(), tile_count)`` threads; NumPy releases the
GIL inside the vectorised blend, so disjoint-tile fan-out yields multi-core speedup
without perturbing the output (each tile is composited by the same bit-exact region
compositor and blitted by the main thread into a disjoint slice — the reduction is
order-independent, so the result stays deterministic and byte-exact, ADR-0033 §2).
Bounding by ``os.cpu_count()`` avoids oversubscription on small hosts; the cap
matches the 8-way parallelism the baseline measured on (baseline §environment;
plan §3; spec REQ-P12-LOGIC-001)."""

# --- Phase-12 Slice-B opacity-drag / viewport-recomposite tuning (phase-12 T12-B;
# Article II single-source) -------------------------------------------------------
# Named ceiling + preview LOD budget consumed by the Slice-B split-cache seam in
# logic/blend.py (composite_range + the NN LOD helpers) and by
# scripts/perf_profile.py --viewport-recomposite (passed as --budget-ms by
# .github/workflows/ci.yml, mirroring the FU-15 composite / full-frame gates).
# BF (AGT-10 Slice-B directive §6.1 / ADR-0034): both names are DISTINCT from every
# shipped ceiling (COMPOSITE_REGION_CEILING_MS / TILEMAP_VIEWPORT_CEILING_MS /
# OVERLAY_FRAME_CEILING_MS / REALTIME_APPLY_CEILING_MS / COMPOSITE_FULL_CEILING_MS)
# and from every shipped working-set/pixel constant. This module stays a leaf (no
# intra-package imports).

VIEWPORT_RECOMPOSITE_CEILING_MS: int = 3000
"""LOOSE catastrophic-regression ceiling for the whole-viewport recomposite / opacity
-drag COMMIT path on the 2-core CI runner, ms — NOT a per-frame budget.

DISTINCT from :data:`FRAME_BUDGET_MS` (16 ms, the 60-fps interactive *render* budget)
and from every other shipped ceiling. The full-resolution whole-viewport recomposite
that a live opacity-slider drag commits on release (up to ~1920², ≥ 12 layers) is a
**batch / on-commit** op — **not** the per-frame render loop — so Article VI's 16 ms
budget does not govern it and is neither applied nor relaxed here (spec §5; ADR-0034
§3/§4; FU-15). Only the *during-drag downsampled preview* (REQ-P12-UI-001) holds the
16 ms budget; this ceiling gates the *commit*.

**AGT-10 RAISED the plan's candidate 2000 ms to 3000 ms** (Slice-B directive §5.1): the
naive full 12-layer recomposite is already measured **2191 ms @ 1080²** and ~7000 ms @
1920² on a fast 8-core desktop, and the 2-core CI runner is ~1.5–2.5× slower — so a
2000 ms bound is **unmeetable** and would flake on healthy code (the FU-15 loose-ceiling
caution / failure mode). The split-cache commit (2–3 full-resolution blends over the
culled viewport for realistic predominantly-NORMAL content) is sub-second to ~1 s on
8-core → ~1–2.5 s on 2-core; a loose 3000 ms clears that with headroom yet sits far
below the ~7 s (8-core) / ~14–17 s (2-core) naive-recomposite catastrophe it must catch
— exactly the Slice-A precedent (:data:`COMPOSITE_FULL_CEILING_MS` was likewise raised
from a too-tight mirror to a loose RE-PROFILE-confirmed bound). The value is a candidate
until AGT-10's RE-PROFILE ship gate measures the optimised 2-core split-cache commit and
finalises it; it must stay well below the catastrophe so the gate still bites. AGT-09
wires ci.yml to pass this value as
``perf_profile.py --viewport-recomposite --budget-ms`` (AGT-10 Slice-B directive §5.1;
ADR-0034 §4; FU-15; plan §8; spec REQ-P12-LOGIC-004/-005; S12 single-source)."""

OPACITY_PREVIEW_MAX_PX: int = 16384
"""Bounded per-tick working-pixel budget for the opacity-drag downsampled LOD preview.

The during-drag preview must hold :data:`FRAME_BUDGET_MS` (16 ms) with 2-core headroom
(REQ-P12-UI-001; Article VI §1 — the budget APPLIES to this one per-frame path and is
held, not relaxed). Rather than hard-code a downsample factor (Article II), the factor
is *derived* from this single-source pixel budget over the culled viewport rect ``V``:
``D = max(1, ceil(sqrt(area(V) / OPACITY_PREVIEW_MAX_PX)))``. Halving the working set
(a 128×128 set) halves the downsampled re-blend + upsample cost, so the ~2-blend
preview holds the 16 ms budget up to a LARGER viewport before the low-zoom Slice-A
handoff. Grounded in AGT-10's on-box measurement (≈183 ms/layer/1080²): a 2-blend
re-blend over ≤16 384 px costs ≈ few ms per tick and holds 16 ms up to ~1080–1280²
viewports on the 2-core runner, degrading gracefully beyond (the low-zoom Slice-A
handoff).

The value was LOWERED 65536 → 16384 by AGT-10's Slice-B RE-PROFILE (directive §1.3):
the former 65 536-px working set held 16 ms at 1080² but exceeded it at 1920² (the
float64 re-blend floor over the preview budget + upsample cost); halving the
downsampled working set restores 16 ms headroom up to ~1080–1280² on the 2-core runner.
This ONLY affects PREVIEW fidelity/speed — the preview is already a deliberately
*approximate* during-drag LOD view — and does NOT affect the byte-exact COMMIT
recomposite (REQ-P12-LOGIC-004; ADR-0034 §3). DISTINCT from every shipped pixel/edge
constant (:data:`FLATTEN_TILE_EDGE_PX`, :data:`TILE_SIZE`, the MAX_*_DIMENSION bounds)
— this is the *preview LOD working-set budget*, a different concern (AGT-10 Slice-B
RE-PROFILE / directive §1.3; ADR-0034 §2; FU-15; plan §8; spec REQ-P12-UI-001;
S12 single-source)."""

# --- Phase-13 Slice-13B portable-bundle caps (phase-13 T13B-01; Article II) --------
# Named defensive caps consumed by the single-file portable-bundle export/import
# functions on data/asset_export.py (export_project_bundle / import_project_bundle).
# BF (ADR-0037 §2 / plan §8): every name is DISTINCT from every shipped constant.
# The .pixbundle is UNTRUSTED input on import (Article VII); these three caps are the
# zip-bomb / oversized-archive defence — enforced against the zip header AND during
# streamed extraction (a lying header must not exhaust memory/disk, ADR-0037 §2). The
# bundle format marker + schema_version strings are format-intrinsic and live
# module-local on asset_export.py, NOT here (ADR-0001 / BF-2, the PIO-1 FORMAT_NAME /
# CATALOG_SCHEMA_VERSION precedent). This module stays a leaf (no intra-package
# imports).

MAX_BUNDLE_BYTES: int = MAX_BLOB_BYTES
"""Defensive ceiling, bytes, on a whole ``.pixbundle`` archive file — 256 MiB.

MIRRORS the shipped :data:`MAX_BLOB_BYTES` (=268435456) sizing (ADR-0037 §2 sanctions
this) but is a DISTINCT named concern — the total on-disk size of the compressed
single-file portable bundle, not a single CAS blob. The ``.pixbundle`` is untrusted
input on import: :func:`~pixelart_creator.data.asset_export.import_project_bundle`
rejects an archive whose on-disk size exceeds this *before* it opens/extracts anything,
so an oversized/zip-bomb container can never begin to exhaust disk. Because bundle
members are deflate-compressed, a 256 MiB compressed ceiling already carries a very
large project + its referenced blobs (REQ-P13-DATA-006/-008; ADR-0037 §2; plan §8)."""

MAX_BUNDLE_ENTRIES: int = 262144
"""Defensive cap on the number of members in one ``.pixbundle`` archive (Article VII).

A bundle embeds the project payload + a manifest + the catalog index + one sidecar and
one CAS blob per referenced asset, so member count scales at ~2 per asset; this bound is
4 × the shipped :data:`MAX_CATALOG_ASSETS` (=65536) asset ceiling, leaving generous
headroom while staying finite.
:func:`~pixelart_creator.data.asset_export.import_project_bundle` rejects an archive
whose entry count exceeds this (checked against the zip directory) *before* streamed
extraction, so a container padded with a colossal number of tiny members cannot exhaust
memory/inodes. DISTINCT from every shipped count cap (REQ-P13-DATA-008; ADR-0037 §2;
plan §8)."""

MAX_BUNDLE_ENTRY_BYTES: int = MAX_BLOB_BYTES
"""Ceiling, bytes, on a single **uncompressed** ``.pixbundle`` member — 256 MiB.

MIRRORS the shipped :data:`MAX_BLOB_BYTES` (=268435456) because the largest legitimate
member is a referenced CAS blob (already bounded by that same cap on
:meth:`~pixelart_creator.data.asset_cas.ContentAddressableStore.put`) or the
``.pixproj`` payload; a DISTINCT named concern — the per-member uncompressed ceiling.
:func:`~pixelart_creator.data.asset_export.import_project_bundle` enforces this against
the zip header **and** during streamed extraction (accumulating the decompressed byte
count per member and aborting the moment it is exceeded), so a member whose header
under-reports its size (a zip bomb) cannot exhaust memory/disk (REQ-P13-DATA-008;
ADR-0037 §2 — "enforced during streamed extraction so a lying header cannot exhaust
memory/disk"; plan §8)."""

# --- Phase-13 Slice-13E web-viewer share-token cap (phase-13 T13E-B01; Article II) --
# Named lifetime cap consumed by the pure share-link-token seam
# (logic/share_token.py) and, through it, the sync_backend/ handshake extension
# (sync_backend/server.py process_request). BF (ADR-0036 §1 / plan §8): the name is
# DISTINCT from every shipped constant — notably from AUTOSAVE_INTERVAL_MS and the
# per-frame *_CEILING_MS / *_BUDGET_MS render ceilings (which are millisecond render
# budgets, an unrelated concern) — this is a SECONDS token-lifetime bound. The
# token header/scope/type string vocabulary ("HS256", "share+jwt", "view") is
# format-intrinsic and lives module-local on share_token.py, NOT here (ADR-0001 /
# BF-2, the sync_protocol/cloud_validation enumerated-vocabulary precedent). This
# module stays a leaf (no intra-package imports).

SHARE_TOKEN_MAX_TTL_S: int = 14400
"""Maximum lifetime, seconds, of a signed web-viewer share-link token — 4 hours.

The web viewer (ADR-0036, Phase-13 Slice-13E) is gated by a per-project **short-lived**
signed share-link bearer token (spec §10 D2; researcher ``a4c7da21`` D2 — "short-lived
signed bearer token over HTTPS"). :func:`~pixelart_creator.logic.share_token.verify`
rejects a token whose ``exp - iat`` exceeds this bound (and any token whose ``exp`` is
not in the future), so a token minted with an over-long lifetime can never be honoured
and a leaked share link's exposure window stays bounded (ADR-0036 §1 lifetime clause;
Addendum A.2 mitigation (4) — short TTL bounds query-string-token leak exposure). A few
hours comfortably spans a review/viewing session while staying far below a login-session
lifetime; the token model is a link-share view, **not** full OAuth (ADR-0036 §1;
a4c7da21 D2). Article VII: the bound is validated on untrusted input before the token is
trusted; the signing secret is operator-provided and never committed. DISTINCT SECONDS
concern from every shipped millisecond render budget/ceiling (spec REQ-P13-WEB-005;
SC-P13-WEB-005-1/-2; plan §8; ADR-0036 §1)."""

SHARE_TOKEN_MAX_CHARS: int = 8192
"""Defensive ceiling on the character length of a signed share-link token (Article VII).

A share-link token is **untrusted input** presented on the WS handshake query string
(ADR-0036 Addendum A.1). :func:`~pixelart_creator.logic.share_token.verify` rejects a
token whose length exceeds this bound **before** any base64/JSON decode, so a hostile
mega-string can never begin to exhaust CPU/memory or reach the parser (ADR-0036 §1
"max-length cap before decode"; Addendum A.8). The value carries a legitimate compact
``header.payload.sig`` token even when the ``project_id``/``sub`` claims approach the
shipped id length (~1024 chars each, base64url ~1.33x JSON expansion) with generous
headroom, while staying finite. DISTINCT named concern from the shipped byte caps
(:data:`MAX_CRDT_UPDATE_BYTES`, :data:`MAX_COMMENT_BYTES`) — this bounds a *character*
count of a compact bearer token before decode (spec REQ-P13-WEB-005; plan §8;
ADR-0036 §1 / Addendum A.8)."""

# --- Phase-14 Slice-14C assistant agentic-loop caps (phase-14 T14C-01; Article II) --
# Named bounds consumed by the pure-``logic`` agentic conversation loop + tiered-safety
# gate + prompt-injection / untrusted-tool-result defence (logic/assistant.py, ADR-0041
# §4). BF-1 (ADR-0041 §4 / plan §8): every name below is DISTINCT from every shipped
# constant — most pointedly MAX_TOOL_RESULT_BYTES is a DIFFERENT concern from the
# shipped
# byte caps (MAX_CLOUD_PROJECT_BYTES=268435456, MAX_BLOB_BYTES=268435456,
# MAX_CRDT_UPDATE_BYTES=1048576, MAX_COMMENT_BYTES=4096,
# GUIDE_MAX_CONTENT_BYTES=1048576):
# it bounds ONE untrusted *tool-result* fed back to the model, not a project/blob/CRDT/
# comment/guide payload. ASSISTANT_REQUEST_TIMEOUT_S is a SECONDS network-request
# timeout,
# DISTINCT from SHARE_TOKEN_MAX_TTL_S (=14400, a token lifetime) and from every
# millisecond render budget/ceiling (*_BUDGET_MS / *_CEILING_MS). These reuse the
# ``cloud_validation``-style size/count bounding rationale (ADR-0026 §6, CLD-1) — a
# breach raises a domain error (AssistantError) rather than degrading silently or
# looping
# unbounded. This module stays a leaf (no intra-package imports).

MAX_ASSISTANT_TURNS: int = 16
"""Ceiling on model round-trips (turns) in one bounded agentic run (Article II/VII).

The agentic loop (:func:`~pixelart_creator.logic.assistant.run_turn`, ADR-0041 §1)
iterates model→tool→model until a final assistant message; this bounds that iteration so
a run-away or adversarial loop that never emits a final message HALTS with an
:class:`~pixelart_creator.logic.assistant.AssistantError` rather than looping forever
(bounded-halt — SC-L005-2). 16 comfortably spans a legitimate multi-step creative task
(select→recolour→procgen→summarise) while capping run-away cost. DISTINCT named concern
from every shipped constant (spec REQ-P14-LOGIC-005/-007; ADR-0041 §4; SC-L005-2)."""

MAX_TOOL_CALLS_PER_TURN: int = 8
"""Ceiling on tool-calls the model may request in a SINGLE turn (Article II/VII).

Supports parallel/multi-tool turns (Researcher ``ad2616c7`` R2.3) while bounding one
turn's fan-out; the loop rejects a turn requesting more with an
:class:`~pixelart_creator.logic.assistant.AssistantError` (bounded-halt). Each call in a
permitted turn still re-runs the full validate + tiered-safety gate independently — this
is a *count* bound, not an authority grant. DISTINCT named concern from every shipped
constant (spec REQ-P14-LOGIC-005/-006/-007; ADR-0041 §4; SC-L006-*)."""

MAX_TOOL_RESULT_BYTES: int = 65536
"""Defensive ceiling, bytes (64 KiB), on ONE untrusted tool-result fed back to the
model.

A tool-result (a dispatched op's summary, an error string, or any content carried back
as
a ``Role.TOOL`` message) is **untrusted input** — the prompt-injection surface (OWASP
LLM
2026 #1; Researcher ``ad2616c7`` R5.2).
:func:`~pixelart_creator.logic.assistant.bound_tool_result`
truncates any result exceeding this bound to a UTF-8-safe prefix **before** it re-enters
the conversation, so a malicious/oversized result cannot exhaust memory/context
(SC-L006-3). Bounding is the *secondary* defence; the primary is structural — a result
is
inert data and can never invoke a non-whitelisted op or bypass the tiered gate (§2/§3).
DISTINCT named byte concern from the shipped MAX_CLOUD_PROJECT_BYTES / MAX_BLOB_BYTES
(=268435456), MAX_CRDT_UPDATE_BYTES (=1048576), GUIDE_MAX_CONTENT_BYTES (=1048576) and
MAX_COMMENT_BYTES (=4096) — this bounds one tool-result, reusing the ADR-0026 §6 / CLD-1
untrusted-size posture (spec REQ-P14-LOGIC-006/-007; ADR-0041 §3/§4; SC-L006-3)."""

MAX_CONVERSATION_MESSAGES: int = 256
"""Ceiling on the total messages in one assistant :class:`Conversation` transcript.

Bounds the growing transcript (user + assistant + tool-result messages) across a bounded
run; the loop raises :class:`~pixelart_creator.logic.assistant.AssistantError` if a turn
would push the transcript past this bound (bounded-halt — SC-L005-2). DISTINCT named
concern from every shipped constant (spec REQ-P14-LOGIC-005/-007; ADR-0041 §4)."""

ASSISTANT_REQUEST_TIMEOUT_S: int = 60
"""Per-request network timeout, seconds, for a real provider adapter round-trip.

Consumed by the Slice-14D stdlib-``urllib`` OpenAI-compatible + Anthropic adapters
(``data/llm/``) so a hung provider connection cannot block indefinitely; the pure loop
and the fake adapter make no network call, so this does not gate them. DISTINCT SECONDS
concern from SHARE_TOKEN_MAX_TTL_S (=14400, a token lifetime) and from every millisecond
render budget/ceiling (spec REQ-P14-LOGIC-007 / REQ-P14-DATA-004..007; ADR-0041 §4)."""

# --- Phase-14 Slice-14D real-adapter transport tuning (phase-14 T14D-01; Article II) --
# Named bounds consumed ONLY by the Slice-14D real stdlib-``urllib`` provider adapters
# (data/llm/openai_compatible.py + data/llm/anthropic_translator.py). BF-1: both names
# are DISTINCT from every shipped constant. The pure loop and the fake adapter make no
# network call, so neither gates them. This module stays a leaf (no intra-package
# imports).

ASSISTANT_REQUEST_MAX_RETRIES: int = 2
"""Bounded transient-failure retry count for one real provider round-trip.

The stdlib-``urllib`` adapters hand-roll a bounded retry (``urllib`` gives no retry
niceties, Researcher ``ad2616c7`` R4.1): a request is attempted at most
``ASSISTANT_REQUEST_MAX_RETRIES + 1`` times (this many *retries* after the first try) on
a timeout / transient transport error / retryable 5xx, each attempt bounded by
:data:`ASSISTANT_REQUEST_TIMEOUT_S`; on exhaustion the adapter raises
``LLMResponseError`` rather than hanging or looping. DISTINCT named concern from the
Phase-10 :data:`CLOUD_RETRY_LIMIT` (=3, a cloud-sync op's retry ceiling — a different
transport surface): this bounds ONE assistant provider HTTP request (spec
REQ-P14-DATA-004/-005/-007; Researcher ``ad2616c7`` R4.1)."""

ASSISTANT_MAX_OUTPUT_TOKENS: int = 4096
"""Default ``max_tokens`` request ceiling for the native-Anthropic Messages adapter.

Anthropic's ``/v1/messages`` wire REQUIRES a ``max_tokens`` field (unlike the
OpenAI-compatible ``/v1/chat/completions`` wire, where it is optional) — this is the
default the :class:`~pixelart_creator.data.llm.anthropic_translator.AnthropicTranslator`
sends when the caller supplies none (a caller may override per-construction). It bounds
one reply's generated length so a single round-trip cannot run away. DISTINCT named
concern from every shipped constant — it is an output-token count, not a byte cap
(cf. :data:`MAX_TOOL_RESULT_BYTES`) nor a message/turn count (spec REQ-P14-DATA-005;
Researcher ``ad2616c7`` R1.4)."""

UI_NOTICE_DURATION_MS: int = 6000
"""Transient UI notice/toast display duration, ms (S12 single-source).

Formerly an inline literal in the UI layer; centralised here so a change is made
in exactly one place. Pure numeric tuning only — the UI widget that shows/hides
the notice remains ui/'s concern (S11)."""
