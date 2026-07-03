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
