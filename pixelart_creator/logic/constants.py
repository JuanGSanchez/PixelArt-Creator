"""Centralised numeric parameters (S12). No magic numbers elsewhere.

Every numeric tuning value used across ui/, logic/, and data/ is defined here
and imported by name, so a change is made in exactly one place (S12, Dossier §1).
"""

MAX_CANVAS_WIDTH = 7680   # 8K UHD width  (S1, F7)
MAX_CANVAS_HEIGHT = 4320  # 8K UHD height (S1, F7)
TILE_SIZE = 64            # viewport tile-culling tile edge, px (S1)
TILE_BUFFER = 1           # extra tile ring drawn around the exposed viewport
PARALLAX_FACTOR = 30.0    # background parallax divisor
SCALE_FACTOR = 0.15       # zoom step factor
FPS_TARGET = 60           # target frames per second (S12)
FRAME_BUDGET_MS = 16      # per-frame render budget, ms (1000/FPS_TARGET, S12)
