---
name: numpy-buffer-ops
description: >
  NumPy RGBA pixel-buffer operations skill for the PixelArt Creator platform.
  Use it (invoked by AGT-03 Python Dev) to read, write, blend, and index the 8K
  canvas buffer as a NumPy uint8 array of shape (H, W, 4) — bounded, vectorised,
  Qt-free — covering region set/get, alpha compositing, and index math against
  logic/constants.py (S1, S12, F7). The buffer stays resident (≈126 MB at 8K);
  only Qt rendering is culled (AGT-10), never the pixel data.
principles_applied:
  inherited:
    - P1 — Source-of-Truth Grounding
    - P2 — Full Determinism
    - P3 — Systematicity (workflow required)
    - P4 — Consistency
    - P6 — Self-Containment
    - P7 — Reference Hygiene
    - P9 — Role Separation (declares OUT-OF-SCOPE)
    - P11 — Programmatic Determinism
    - P12 — Maximal-Effort Completeness
    - P13 — Token Economy
    # P5 inherits AGT-03's context discipline; P10 inherits AGT-03's exit status.
  custom:
    - id: C1
      name: uint8 RGBA, resident, Qt-free
      requires: The buffer is a (H,W,4) uint8 ndarray held resident; all ops clip back to uint8; no PySide6/Qt import in this logic/ code.
      rationale: User req S1/S11/S12; Dossier §2 F7 (8K RGBA ≈126 MB, cheap to keep resident).
---

SKILL: numpy-buffer-ops
================================================================================

PURPOSE:
  Provide the canonical, deterministic array operations for the pixel canvas:
  allocate/validate the (H,W,4) uint8 buffer, set/get rectangular regions, set a
  single pixel, alpha-composite a source over the buffer, and convert to/from a
  format ui/ can hand to Qt — all vectorised and bounds-checked against
  constants.py.

SELF-CONTAINMENT CHECK:
  Can this skill execute with only its own content and declared inputs?  YES —
  given NumPy + logic/constants.py it produces the buffer-op module unaided.

INPUTS:
  - The operation (allocate / set-region / get-region / set-pixel / blend / index).
  - logic/constants.py: MAX_CANVAS_WIDTH (7680), MAX_CANVAS_HEIGHT (4320), etc.

OUTPUTS:
  - A pixelart_creator/logic/ module (Qt-free) with typed, docstring'd functions
    over a NumPy uint8 (H,W,4) array; each op clips results to [0,255] uint8 and
    validates coordinates against the canvas bounds.

PRECONDITIONS:
  - NumPy is available; logic/constants.py exists; placement decided (layer-audit).

PROCEDURE:
  1. Allocate the buffer as `np.zeros((H, W, 4), dtype=np.uint8)` with H/W bounded
     by the constants; treat axis 0 = rows (y/height), axis 1 = cols (x/width),
     axis 2 = RGBA channels.
  2. Region write: `buf[y0:y1, x0:x1] = [r, g, b, a]` (validate the slice is in
     bounds first); region read returns a view/copy per the caller's need.
  3. Single pixel: `buf[y, x] = [r, g, b, a]`; the alpha channel alone is `buf[:, :, 3]`.
  4. Alpha composite src over dst: compute in float —
     `out = src[...,:3]*a + dst[...,:3]*(1-a)` with `a = src[...,3:]/255` — then
     `np.clip(...).astype(np.uint8)` (never leave a float dtype in the buffer).
  5. Return bounds/typed results; expose reversible slices for reversible-op.

DECISION POINTS:
  - Decision NB-D1:
    Condition: a requested region exceeds the canvas bounds (from constants.py).
    Branch A: raise a domain error (out-of-bounds) — do not silently clip the
      region extent (only channel VALUES are clipped, not coordinates).
    Default: A (P2 — explicit failure over silent corruption).
  - Decision NB-D2:
    Condition: an op returns a view that the caller may mutate.
    Branch A: return a copy when the caller needs an independent inverse (for
      reversible-op capture); a view only for read-only access.
    Default: A when the result feeds undo capture.

ERROR HANDLING:
  - Error NB-E1: dtype drifts to float/int64 → clip + astype(np.uint8) before return.
  - Error NB-E2: shape mismatch on a blend → raise a domain error naming the shapes.

DEPENDENCIES:
  - NumPy (runtime dep, declared in pyproject.toml). Fallback: block if absent.
  - logic/constants.py for bounds. reversible-op consumes region get/set.

BUNDLED RESOURCES:
  - None.

BUNDLED SCRIPTS:
  - None.

BUNDLED TOOLS:
  - None.

OUT-OF-SCOPE (P9):
  - Rendering the buffer to screen / QGraphicsPixmapItem culling → AGT-10 strategy,
    AGT-05 implements (canvas-view). This skill never imports Qt (C1).
  - Colour-theory harmony math → AGT-03 harmony logic (grounded F9; colour-hub UI is AGT-05).
  - Sprite bin-packing → maxrects_compactor library.

SOURCES:
  - User requirements: Dossier §1 (S1, S11, S12), §2 (F7 — 8K RGBA ≈126 MB resident),
    §6.1 (AGT-03), §6.2 (numpy-buffer-ops), §8.
  - Official docs (via The Researcher, P1): NumPy image-array indexing/slicing and
    alpha-compositing (pythoninformer numpy-and-images; note.nkmk.me alpha blend).
  - Inner assets: asset-templates.md §Skill, principles.md §3 (skill row).
