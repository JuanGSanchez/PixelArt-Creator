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
