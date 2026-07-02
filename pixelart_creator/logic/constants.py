"""Centralised numeric parameters (S12). No magic numbers elsewhere.

Every numeric tuning value used across ui/, logic/, and data/ is defined here
and imported by name, so a change is made in exactly one place (S12, Dossier §1).
"""

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

OPENGL_VIEWPORT_ENABLED: bool = True
"""Use a QOpenGLWidget viewport for the canvas; raster fallback applies when
OpenGL is unavailable/headless (render-strategy §10; D6)."""

ZOOM_MAX: float = 64.0
"""Deep-zoom ceiling as a scale factor (6400 %); fit-to-view lower bound is
computed, not a literal (CL-1)."""

ZOOM_PRESET_STOPS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
"""Discrete keyboard zoom preset stops, 100 %..6400 % (CL-2). The geometric
zoom step reuses SCALE_FACTOR as `1.0 + SCALE_FACTOR` (BF-3)."""

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
